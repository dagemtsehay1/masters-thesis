# Thesis metrics & how to reproduce them

Every metric below is tied to a concrete, runnable artifact, so results are
reproducible by re-running the repo rather than trusting a one-off number.

## Latency benchmarks

| Benchmark | Command | Measures |
|---|---|---|
| Fusion decision | `python tests/benchmarks/bench_fusion_latency.py` | `FusionEngine.resolve()` latency (p50/p95). Expected sub-millisecond — confirms fusion is never the bottleneck. |
| Whisper transcription | `python tests/benchmarks/bench_whisper_latency.py [model]` | Real CPU transcription latency for a short clip. Run on the **actual target laptop** — this is the number to check against the offline-latency goal. |

## Accuracy metrics

| Metric | How measured |
|---|---|
| Voice transcription accuracy (WER) | Labeled EN/AM clips through `WhisperTranscriber`, compared to ground truth (see `docs/amharic_dataset_protocol.md` for the AM set). |
| Voice command intent accuracy | Same clips through `IntentEngine`, per-tier (alias / fuzzy / Qwen) reported separately. |
| Gesture classification accuracy | Labeled gesture clip set through `GestureClassifier` → confusion matrix, precision/recall per gesture. |
| Multimodal command accuracy | Scripted dual-modality scenarios through `FusionEngine` (matching / contradicting / complementary), compared to expected resolution. |
| False activation rate | Fraction of resolved commands from ambient-noise / idle-camera segments. |
| Command rejection rate | Fraction of `CommandValidator`/`SafetyController` rejections over a fixed run. |

## Resource metrics

- CPU % and RSS memory are sampled by `src/monitoring/metrics.py` (psutil) and
  shown live in the Performance panel; the same collector backs a soak run.
- Per-language and per-modality breakdowns come from tagging each trial in the
  Experiment panel (`src/monitoring/experiment_log.py`) with its language and
  modality, then exporting to CSV/JSON.

## Experiment sessions

The GUI's **Experiments** panel records per-trial expected-vs-recognized
results with modality, language, confidence, latency, and noise/lighting
conditions, and exports to CSV or JSON — **without** storing any audio or
video. Participant tracking is off unless a session id is entered.

## Stated limitations to report honestly

- **Amharic** accuracy will be meaningfully below English on CPU hardware
  (low-resource language). Measure and report it; don't over-tune a tiny set.
- **qwen3:0.6b** reliability as an intent fallback is genuinely uncertain at
  that size — it's optional and English-only by default. Report its measured
  fallback resolution rate before relying on it.
- **CPU-only latency** has a real floor for Whisper `small`; all latency
  targets are goals to validate on the real hardware, not guarantees.
