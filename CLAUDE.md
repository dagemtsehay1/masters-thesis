# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Master's thesis project: offline multimodal (voice + hand-gesture) control of a simulated youBot robot in CoppeliaSim. Voice commands are recognized offline via multilingual Whisper (faster-whisper); hand gestures via MediaPipe's HandLandmarker; an optional local-LLM fallback (Ollama/qwen3:0.6b) handles ambiguous transcripts. A single configurable fusion layer merges the two modalities, everything passes a canonical-command validator and a safety layer, and a PySide6 desktop interface drives it all. English and Amharic are both supported. Runs offline on an average CPU laptop.

The full build history is in `.claude/plans/read-the-prompt-from-cheerful-hearth.md` (9 phases). This describes the current, fully-evolved state.

## Entry point

`python3 main.py` is the single entry point. [main.py](main.py) is thin — argument parsing, config loading, then delegating to `src/app/application.py`.

```bash
uv sync
python3 main.py                    # opens the PySide6 GUI (default)
python3 main.py --headless         # console loop instead
python3 main.py --preset voice_only
python3 main.py --config path/to/extra.yaml
python3 main.py --log-level DEBUG
```

Both modes are driven by the same `Application` (`src/app/application.py`): it owns the shared services (`SafetyController`, `CommandValidator`, `FusionEngine`, `MetricsCollector`) and `start_services()` builds the hardware/model components. `run_headless()` calls `start_services()` directly; `run_gui()` builds the PySide6 `MainWindow`, whose `RobotWorker` calls `start_services()` on a background thread so a slow CoppeliaSim connection or model load never blocks the UI. `stop()` is the single cleanup path either mode ends up calling.

## Architecture

Layered pipeline — each stage produces a typed object the next consumes; nothing reaches the robot except a validated `RobotCommand`. See [docs/architecture.md](docs/architecture.md) for the full diagram.

```
src/app/            Application (owns services + lifecycle), cli.py (argparse), lifecycle.py (signals)
src/config/         AppConfig pydantic schema + loader (default.yaml -> preset -> --config -> env)
src/audio/          capture.py (mic, bounded queue), vad.py (utterance gating in audio-time)
src/speech/         transcriber.py (faster-whisper, load-once), normalizer.py, languages/{en,am}.py,
                    pipeline.py (VoicePipeline.poll() -> VoiceEvent | None)
src/intent/         aliases.py (canonical vocabulary), rule_parser.py (exact/alias/rapidfuzz),
                    qwen_client.py + schemas.py (optional Ollama fallback), intent_engine.py
src/gesture/        camera.py (threaded, newest-frame-only), landmarks.py (MediaPipe), classifier.py
                    (normalized rule-based), smoothing.py (confirmation state machine),
                    pipeline.py (GesturePipeline.poll() -> GestureEvent, frame)
src/fusion/         engine.py (the ONE fusion impl, 9 modes), modes.py, policy.py
src/commands/       schema.py (RobotCommand), registry.py (whitelist), validator.py, adapters.py
src/robot/          controller.py (state machine, RobotCommand-only), safety.py, coppelia_client.py
src/monitoring/     logging_setup.py, metrics.py (bounded), health.py, experiment_log.py
src/ui/             state.py (snapshots), workers.py (QThread workers), main_window.py,
                    panels/*.py (9 panels), widgets/*.py (waveform, sparkline, status badge)
```

## Key invariants (don't break these)

- **Single command gate.** Voice (`VoiceEvent`), gesture (`GestureEvent`), and manual UI input all become a `RobotCommand` and pass `commands/validator.py` + `robot/safety.py` before `RobotController` sees them. `command_from_legacy_string` (`src/commands/adapters.py`) is the one place the shared 5-word legacy vocabulary (`go/back/left/right/stop`) becomes a canonical command.
- **One fusion implementation.** `src/fusion/engine.py::FusionEngine` is used by both the headless loop and the GUI. The 9 modes (`voice_only`, `gesture_only`, `either`, `voice_priority`, `gesture_priority`, `latest_wins`, `highest_confidence`, `confirmation`, `combined`) are selected by `config.fusion.mode`, not code-forked. `"stop"` from either modality overrides the active mode; low-confidence/stale/duplicate events are filtered in `policy.py`.
- **Emergency stop is independent.** It flows straight to `SafetyController.trigger_emergency_stop()`, bypassing Whisper/Qwen/MediaPipe/fusion, and is checked first on every `RobotController.step()`. A dead-man timeout (`safety.dead_man_timeout_s`) also force-stops continuous motion if no fresh command arrives — so a single "go" no longer moves the robot forever.
- **Models load once.** Whisper (`WhisperTranscriber`), MediaPipe (`HandLandmarkerWrapper`), and the Ollama client are each constructed a single time in `start_services()` and reused.
- **Bounded everything.** Camera queue (size 1, drop-oldest), audio queue, metrics history, and the UI log buffer are all bounded — no unbounded growth over a long session.
- **Inference never on the UI thread.** Every model call runs in a `QThread` worker (`src/ui/workers.py`); panels only render immutable state snapshots (`src/ui/state.py`) delivered via Qt signals, and forward user actions back through queued signal connections — never by touching a worker's `QTimer` cross-thread or calling `RobotController` directly.

## Intent resolution order (voice)

`IntentEngine.resolve()`: normalize (per detected language) → exact/alias match → `rapidfuzz` fuzzy match → (only if still unresolved and enabled) Qwen fallback → confidence gate (`speech.confidence_threshold`, rejected below it) → `VoiceEvent`. Qwen is disabled by default, English-only, strict-JSON-validated (`src/intent/schemas.py`), health-checked at startup, and never a required dependency. The canonical vocabulary (`src/intent/aliases.py`) is language-independent: English and Amharic alias tables (`src/speech/languages/{en,am}.py`) both map to the same canonical names, then to the legacy word for fusion.

## Models and assets

- `model/hand_landmarker.task` — MediaPipe hand model. **Not in the repo** (see [README.md](README.md) for the download step); `model/` is gitignored. Voice-only presets don't need it.
- Whisper weights download on first run (one-time network step; runtime is offline).
- The old Vosk model that used to live in `model/` is **gone** — Whisper replaced it in Phase 5.

## Config

`src/config/schema.py` is the source of truth (pydantic, `extra="forbid"` — typos in preset files fail loudly). Six presets in `config/presets/` diff over `default.yaml`. `camera.resolution`/`preview_fps` are accepted but not yet enforced anywhere.

## Amharic

Both languages run through the same multilingual Whisper model (never a `.en` variant). `docs/amharic_dataset_protocol.md` is the reproducible recording/evaluation protocol — the `am.py` alias table is a *seed* to validate against real recordings, not validated ground truth. Amharic accuracy on CPU is an expected, reportable limitation, not a bug.

## Tests

```bash
uv sync --group dev
uv run pytest              # tests/unit/ — no live hardware/models/Ollama needed (mocks + stubs)
```

Benchmarks (`tests/benchmarks/`, run from the CLI) and a manual CoppeliaSim smoke script (`tests/manual/smoke_coppelia.py`) are separate from the unit suite. When adding a fusion mode, gesture, or intent tier, add its unit test alongside — the suite covers command validation, safety, gesture classification/smoothing, all fusion modes + policy, EN/AM intent aliases, Qwen schema, monitoring, and UI state.
