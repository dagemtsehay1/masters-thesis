# Architecture

A layered pipeline. Each stage produces a typed object the next stage
consumes; nothing reaches the robot except a validated `RobotCommand`.

```
 Hardware/OS         Perception              Understanding            Decision           Actuation
 microphone ─▶ audio.capture + audio.vad ─▶ speech.transcriber ─▶ intent.intent_engine ─┐
                                                                                          ├▶ fusion.engine ─▶ commands.validator ─▶ robot.safety ─▶ robot.controller ─▶ robot.coppelia_client ─▶ CoppeliaSim
 camera ─────▶ gesture.camera + landmarks + classifier + smoothing ───────────────────────┘
 manual UI ────────────────────────────────────────────────────────────────────────────┘

 monitoring (logging, metrics, health) runs alongside every stage.
 config (typed, validated, presets) parameterizes everything.
 ui (PySide6 workers + panels) consumes state snapshots, forwards user actions.
```

## Package map

| Package | Responsibility |
|---|---|
| `src/app` | CLI parsing, lifecycle/signals, `Application` (owns services, runs headless or GUI) |
| `src/config` | Typed `AppConfig` schema + YAML loader with preset merging and env overrides |
| `src/audio` | Microphone capture (bounded queue) and VAD gating (audio-time, not wall-clock) |
| `src/speech` | faster-whisper transcription, per-language normalization, `VoicePipeline` |
| `src/intent` | Canonical vocabulary, alias/fuzzy rule parser, optional Qwen fallback, `IntentEngine` |
| `src/gesture` | Threaded camera worker, MediaPipe landmarks, rule classifier, temporal smoothing, `GesturePipeline` |
| `src/fusion` | One configurable engine (9 modes), policy filters, emergency-stop override |
| `src/commands` | Canonical `RobotCommand`, whitelist registry, validator, legacy-string adapter |
| `src/robot` | `RobotController` state machine, `SafetyController`, `CoppeliaClient` |
| `src/monitoring` | Structured logging, bounded metrics, health checks, experiment log |
| `src/ui` | PySide6 shell: state snapshots, QThread workers, panels, custom widgets |

## Key invariants

- **Single command gate**: voice, gesture, and manual input all become a
  `RobotCommand` and pass `commands.validator` + `robot.safety` before the
  controller sees them. There is no other path to the robot.
- **One fusion implementation**: `fusion.engine.FusionEngine` is used by both
  the headless loop and the GUI. Modes are config-selected, not code-forked.
- **Emergency stop is independent**: it flows straight to `SafetyController`,
  bypassing Whisper/Qwen/MediaPipe/fusion, and is checked first on every
  `RobotController.step()`.
- **Models load once**: Whisper, MediaPipe, and the Ollama client are each
  constructed a single time in `start_services()` and reused.
- **Bounded everything**: camera queue (size 1, drop-oldest), audio queue,
  metrics history, and the UI log buffer are all bounded — no unbounded
  growth over a long session.
- **Inference off the UI thread**: every model call runs in a QThread worker;
  the UI only renders immutable state snapshots delivered via Qt signals.
