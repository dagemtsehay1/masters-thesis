# Amharic command dataset & evaluation protocol

This is a reproducible protocol for collecting a small, real Amharic command
dataset and using it to (a) validate/extend the alias table in
[`src/speech/languages/am.py`](../src/speech/languages/am.py) and (b) report
measured Amharic recognition accuracy for the thesis. It is deliberately
sized for one person to complete in a short session — **do not** fabricate a
large synthetic Amharic corpus; the value here is in real transcription
behavior on the target hardware, which cannot be guessed.

## Why this is needed

Whisper's Amharic training data is comparatively sparse (a low-resource
language), so its real transcription of a spoken command frequently differs
from textbook orthography — spacing, gemination, and vowel choices vary. The
alias table shipped in `am.py` is a *seed* of standard imperative forms; this
protocol is how you turn it into something backed by evidence.

## 1. Command set

The five canonical commands, with their seed Amharic phrasings:

| Canonical      | Amharic (Ge'ez)        | Gloss             |
|----------------|------------------------|-------------------|
| `move_forward` | ወደፊት ሂድ / ወደ ፊት ተንቀሳቀስ | "go forward"      |
| `turn_left`    | ወደ ግራ ታጠፍ              | "turn left"       |
| `turn_right`   | ወደ ቀኝ ታጠፍ              | "turn right"      |
| `turn_around`  | ወደ ኋላ ተመለስ             | "turn back"       |
| `stop`         | ቁም / አቁም               | "stop"            |

## 2. Recording plan

Target ≈ **120–240 short clips**:

- 5 commands × 2 phrasing variants × 10 repetitions × 1–2 speakers.
- Recorded on **the actual target laptop microphone** (not a studio mic) —
  the point is to measure the deployment condition.
- In **at least two acoustic conditions**: a quiet room and a mildly noisy
  one (background TV/fan). Optionally a third with a played-back noise track
  for the "performance under noise" metric.
- 16 kHz mono WAV, one command per clip, ≤ ~3 s each.

Label every clip with its intended canonical command and the condition:
`am_<speaker>_<command>_<variant>_<take>_<condition>.wav`, plus a
`labels.csv` mapping filename → canonical command.

## 3. Evaluation procedure

For each clip, run it through the same pipeline the app uses:

1. `WhisperTranscriber.transcribe_pcm16` → raw transcript + confidence.
2. `normalize_text(transcript, "am")` → normalized text.
3. `RuleBasedParser(language="am").parse(...)` → resolved canonical command.

Record, per clip: raw transcript, normalized text, resolved canonical
command, whether it matched the label, transcription confidence, and latency.

## 4. What to compute (feeds the thesis metrics table)

- **Transcription behavior**: for each command, the set of distinct raw
  transcripts Whisper actually produced. New/frequent forms that the seed
  aliases miss are added to `am.py` — this is the alias-table validation step.
- **Command intent accuracy**: fraction of clips whose resolved canonical
  command equals the label, reported per command, per condition, and overall.
- **Confusion matrix** across the 5 commands.
- **Confidence** and **latency** distributions, reported alongside the English
  numbers so the per-language comparison in `docs/thesis_metrics.md` is direct.

## 5. Regression fixture

Freeze a labeled subset (e.g. 2–3 clean clips per command) as a fixed set and
keep it for regression checks whenever the alias table or normalizer changes.
Because raw audio is involved, store it **outside** the repo (it's not source),
and keep only the derived `labels.csv` + the resulting alias additions in
version control.

## Expected limitations (state these honestly in the thesis)

- Amharic accuracy will be **meaningfully lower** than English on the same
  CPU hardware, especially for spontaneous (non-scripted) speech, noise, and
  non-native pronunciation. This is an inherent low-resource limitation, not a
  bug to engineer away.
- Mitigations are limited to keeping the command set small and leaning on
  alias/fuzzy matching rather than free-form understanding. The Qwen fallback
  is intentionally **English-only** for now (`intent.qwen.languages: [en]`),
  because a 0.6B model's Amharic reasoning is even less reliable than its
  English.
