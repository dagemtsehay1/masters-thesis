# Multimodal Robot Control (Voice + Gesture)

Offline voice- and hand-gesture-controlled robot teleoperation, simulated in
CoppeliaSim. A Master's thesis prototype: multilingual offline speech
recognition (Whisper), hand-gesture recognition (MediaPipe), an optional
local-LLM intent fallback (Ollama/Qwen), a configurable multimodal fusion
layer, a safety layer, and a PySide6 desktop interface — all running offline
on an average laptop.

See [`CLAUDE.md`](CLAUDE.md) for the internal architecture, [`docs/`](docs/)
for the subsystem and thesis-evaluation documentation, and
`.claude/plans/read-the-prompt-from-cheerful-hearth.md` for the full
multi-phase plan this codebase was built against.

## Setup

1. Install dependencies (Python >= 3.12, managed with [uv](https://github.com/astral-sh/uv)):

   ```bash
   uv sync
   ```

2. **Download the hand-gesture model.** The gesture pipeline needs MediaPipe's
   hand landmark model, which is *not* checked into this repo. Download
   `hand_landmarker.task` from
   [MediaPipe's model index](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models)
   and place it at `model/hand_landmarker.task`. Voice-only presets don't
   need it.

3. **Whisper weights** download automatically on first run (a one-time network
   step; runtime operation is fully offline afterward).

4. **Optional — Qwen intent fallback.** Only if you enable it
   (`intent.qwen.enabled`): install [Ollama](https://ollama.com) and
   `ollama pull qwen3:0.6b`. It's disabled by default and never required.

5. Open CoppeliaSim, load `scene/scene01.ttt` (must contain a `/youBot`
   object), enable the ZeroMQ remote API server, and start the simulation.
   The app connects to `localhost:23000` by default.

## Running

```bash
python3 main.py               # opens the PySide6 desktop interface (default)
python3 main.py --headless    # runs the console loop instead
```

Useful flags:

```bash
python3 main.py --preset low_resource     # named config preset, see config/presets/
python3 main.py --config path/to/my.yaml  # extra overrides layered on top
python3 main.py --log-level DEBUG
```

Presets: `low_resource`, `balanced`, `high_accuracy`, `voice_only`,
`gesture_only`, `multimodal`. They're diffs over `config/presets/default.yaml`;
`src/config/schema.py` documents every setting.

## Interface

The desktop app has a sidebar with: Dashboard, Camera & Gestures, Voice
Commands, Robot Control, Configuration, Logs, Performance, Diagnostics, and
Experiments. The header carries live component status badges and an
always-visible **EMERGENCY STOP** button that bypasses the whole recognition
pipeline and stops the robot directly.

## Commands

Five commands, recognized by voice (English or Amharic) or gesture:

| Command | Voice (EN) | Gesture |
|---|---|---|
| forward | "go forward" / "advance" | 3+ fingers raised above the wrist |
| turn left | "turn left" | index finger pointing left |
| turn right | "turn right" | index finger pointing right |
| turn around | "go back" | 3+ fingers below the wrist |
| stop | "stop" / "halt" | open palm, four fingers up |

## Safety

Every recognized command (voice, gesture, or manual) is validated against a
whitelist and speed/duration limits before reaching the robot. A dead-man
timeout stops the robot if no fresh command arrives within
`safety.dead_man_timeout_s` (default 3s) while it's moving. Emergency stop is
independent of every recognition component.

## Tests

```bash
uv sync --group dev
uv run pytest              # unit tests: config, commands, safety, gesture, fusion, intent, monitoring, UI state
```

Latency benchmarks (not part of the unit suite) live in `tests/benchmarks/`;
a manual CoppeliaSim smoke script is at `tests/manual/smoke_coppelia.py`.
Tests requiring live hardware/models use mocks and don't need a
microphone/camera/simulator/Ollama.
