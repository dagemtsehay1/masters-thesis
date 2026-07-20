You are a senior robotics, machine learning, Python, and software architecture engineer.
Review my existing project for controlling a robot using voice commands and hand gestures. The system must work fully offline on an average local laptop and should remain lightweight, fast, stable, modular, and easy to use.
My planned core technologies are:
Python
Whisper small v2 for offline speech recognition
MediaPipe Hands v0.10 for gesture recognition
Ollama with qwen3:0.6b for understanding the intent and context of voice commands
A rule-based multimodal fusion layer
CoppeliaSim for robot simulation and testing
Your first task is to inspect the entire existing codebase and create a detailed implementation plan. Do not modify the code yet.
Main goals
Improve the project structure.
Reduce unnecessary dependencies and duplicated logic.
Improve runtime speed, memory usage, stability, and maintainability.
Make the application easy to configure and run.
Improve voice-command recognition and contextual understanding.
Improve gesture detection accuracy and stability.
Add a flexible multimodal fusion and priority system.
Ensure the application can run offline on an average laptop.
Add support for both English and Amharic voice commands when technically practical.
Keep the system suitable for a Master’s thesis, with clear architecture, measurable results, and reproducible experiments.
Codebase review
Inspect all folders and files and identify:
Current architecture and data flow
Entry points
Voice recognition pipeline
Gesture recognition pipeline
Robot command execution
CoppeliaSim communication
Configuration handling
Logging and error handling
Threading, multiprocessing, asynchronous tasks, queues, or blocking operations
Model loading and unloading
Repeated or tightly coupled code
Performance bottlenecks
Stability risks
Missing tests
Unused files, dependencies, and functions
Security and privacy concerns
Parts that will be difficult to maintain or extend
Explain what should be retained, refactored, replaced, moved, or removed.
Proposed architecture
Create a clean modular architecture. Consider separating the project into components such as:
• app
application startup and lifecycle
• audio
microphone capture
voice activity detection
audio preprocessing
• speech
Whisper model loading
transcription
language detection
English and Amharic normalization
• intent
rule-based command matching
Qwen intent interpretation
confidence scoring
command validation
• gesture
camera capture
MediaPipe hand tracking
gesture classification
temporal smoothing
• fusion
voice and gesture event fusion
modality priority
conflict resolution
timeout handling
• commands
canonical robot command definitions
command validation
command registry
• robot
robot controller interface
CoppeliaSim adapter
safety controller
• config
settings models and configuration loading
• monitoring
logging
performance metrics
debug information
• tests
unit, integration, and simulation tests
You may suggest a better structure based on the current codebase.
Use interfaces or abstract base classes where they provide a clear benefit, but avoid unnecessary abstractions and overengineering.
Voice-command pipeline
Design an efficient offline voice pipeline.
Consider:
Voice activity detection so Whisper runs only when speech is detected.
Configurable recording duration and silence timeout.
Audio resampling and noise normalization.
Reusing the loaded Whisper model instead of loading it for each command.
Supporting configurable Whisper models, while using small or small.en only when appropriate.
Automatic language detection or a manually selected language.
English and Amharic transcription.
Text normalization for spelling, punctuation, numbers, and common command variations.
Command aliases and synonyms.
Confidence thresholds.
Rejection of unclear or unsupported commands.
Avoiding repeated execution of the same command.
Caching repeated intent results where useful.
Measuring transcription latency and command-recognition accuracy.
The final system should convert speech into a canonical command object rather than passing raw text directly to the robot.
Example canonical command:
RobotCommand(
    action="move",
    direction="forward",
    speed=0.5,
    duration=None,
    source="voice",
    confidence=0.91,
    language="en",
    timestamp=...
)
Qwen integration through Ollama
Use the local Ollama model qwen3:0.6b only for contextual intent understanding when the rule-based parser cannot confidently resolve the command.
The intent-processing order should preferably be:
Normalize the transcript.
Try exact command and alias matching.
Try rule-based or pattern-based parsing.
Use qwen3:0.6b only when earlier stages are uncertain.
Validate the model response against an allowed command schema.
Reject invalid, unsafe, or unsupported output.
Do not allow Qwen to directly execute robot actions.
Require Qwen to return strict structured JSON, for example:
{
  "action": "move",
  "direction": "left",
  "speed": 0.4,
  "duration": null,
  "confidence": 0.86,
  "reason": "The user requested the robot to move slightly to the left."
}
Add:
JSON-schema or Pydantic validation
A short system prompt
Low output-token limits
Configurable timeout
Configurable temperature, preferably deterministic
Retry limits
Graceful fallback when Ollama is unavailable
Health check during application startup
Protection against unsupported commands
Logging of latency without storing sensitive audio
An option to disable Qwen completely
Evaluate whether qwen3:0.6b is accurate enough for this task. If it is too weak for reliable intent understanding, keep it as an optional fallback and explain suitable lightweight alternatives without changing the offline requirement.
English and Amharic support
Investigate practical support for both English and Amharic.
The system should support configurations such as:
speech:
  languages:
    enabled:
      - en
      - am
    mode: auto
    default_language: en
For Amharic:
Use multilingual Whisper, not an English-only model.
Test Amharic transcription quality using real command recordings.
Create Amharic command aliases mapped to the same canonical commands as English.
Support Amharic script and practical transliterations where useful.
Normalize common transcription variations.
Keep the robot’s internal command vocabulary language-independent.
Add tests for English, Amharic, mixed-language, and unclear commands.
Clearly explain expected limitations of Amharic speech recognition on lightweight local hardware.
Example mappings:
commands:
  move_forward:
    english:
      - "move forward"
      - "go forward"
      - "advance"
    amharic:
      - "ወደፊት ሂድ"
      - "ወደ ፊት ተንቀሳቀስ"
Do not invent a large Amharic command dataset without validation. Propose a process for recording and evaluating a small custom command dataset.
Gesture detection improvements
Review and improve the MediaPipe gesture pipeline.
Consider:
Running camera capture separately from gesture inference
Processing only the newest frame and dropping stale frames
Configurable frame resolution
Configurable inference frame rate
Region-of-interest cropping where appropriate
Handedness detection
Landmark normalization
Scale, rotation, and position invariance
Finger-state and landmark-angle features
Temporal smoothing across multiple frames
Minimum consecutive-frame confirmation
Cooldown after command activation
Gesture start, hold, and release states
Unknown-gesture rejection
Confidence thresholds
Prevention of accidental repeated commands
Lighting and camera-quality checks
Single-hand and two-hand gesture handling
A clear neutral or stop gesture
Debug visualization that can be disabled
Collection of gesture accuracy, precision, recall, confusion matrix, and latency
Do not trigger a robot command from one unstable frame.
Design a gesture event object such as:
GestureEvent(
    gesture="move_left",
    confidence=0.93,
    hand="right",
    state="confirmed",
    timestamp=...
)
Consider whether the existing rule-based gesture classifier is sufficient. Recommend a lightweight trained classifier only if it provides a meaningful improvement and can run offline on average laptops.
Multimodal fusion and priority configuration
Create a configurable fusion layer that receives normalized voice and gesture events.
Support modes such as:
Voice only
Gesture only
Either modality
Voice priority
Gesture priority
Latest command wins
Highest confidence wins
Confirmation mode, where one modality confirms another
Combined mode, where voice supplies the action and gesture supplies direction or parameters
Emergency commands that always override normal commands
Example configuration:
fusion:
  mode: voice_priority
  event_window_ms: 1500
  conflict_policy: highest_confidence
  minimum_confidence:
    voice: 0.70
    gesture: 0.80
  priority:
    emergency_stop: 100
    stop: 90
    gesture: 60
    voice: 50
  require_confirmation_for:
    - high_speed
    - continuous_motion
  duplicate_command_cooldown_ms: 1200
  stale_event_timeout_ms: 2000
Define clear behavior for:
Matching voice and gesture commands
Complementary commands
Contradicting commands
Low-confidence commands
Commands arriving outside the fusion window
Repeated commands
Emergency stop
Loss of camera, microphone, simulator, or Ollama connection
The emergency-stop command must not depend on Qwen.
Configuration system
Use a typed configuration system with sensible defaults. YAML or TOML may be used for user-facing settings, with environment variables only for machine-specific values.
Include settings for:
Application mode
Debug mode
Camera device
Microphone device
Camera resolution
Camera frame rate
Gesture inference rate
MediaPipe confidence thresholds
Gesture smoothing window
Gesture confirmation frames
Gesture cooldown
Whisper model
Whisper compute device
Whisper language
Voice activity detection
Audio sample rate
Silence timeout
Maximum recording length
Voice confidence threshold
Ollama URL
Ollama model
Ollama timeout
Qwen enabled or disabled
Fusion mode
Modality priorities
Conflict policy
Command cooldown
Robot speed limits
CoppeliaSim connection settings
Logging level
Metrics collection
Whether video preview is enabled
Whether transcripts are stored
Test and benchmark modes
Validate configuration during startup and report clear errors.
Provide at least these presets:
low_resource.yaml
balanced.yaml
high_accuracy.yaml
voice_only.yaml
gesture_only.yaml
multimodal.yaml
Performance and resource requirements
Optimize the system for average laptops.
Plan for:
CPU-only execution
Optional GPU acceleration
Lazy loading where appropriate
Loading each model only once
Bounded queues
Dropping old video frames
Avoiding busy loops
Avoiding unnecessary copies
Reducing camera resolution when required
Configurable inference frequency
Minimal Qwen calls
Short prompts and outputs
Graceful component shutdown
Thread-safe communication
Resource cleanup for microphone, camera, Ollama requests, and CoppeliaSim
Monitoring CPU usage, memory usage, frame rate, and command latency
Create target performance goals, for example:
Application startup under a reasonable time
Gesture response latency below 300 ms where hardware permits
Voice command processing within a practical offline latency
Stable memory usage during long sessions
No unlimited queue growth
No repeated model initialization
No robot command execution from stale events
Explain how each target should be measured.
Stability and safety
Add a safety layer before robot execution.
Include:
Allowed-command whitelist
Speed and duration limits
Workspace or movement constraints
Emergency stop
Dead-man timeout for continuous movement
Rejection of malformed commands
Prevention of duplicate execution
Simulator connection checks
Automatic stop after component failure
Clear degraded modes
Graceful handling when one modality is unavailable
Centralized exception handling
Structured logs
Clean shutdown on keyboard interrupt or system signal
The robot controller should accept only validated canonical command objects.
Usability
Make the project easy to install, configure, run, and test.
Add clear startup status messages showing:
Camera status
Microphone status
Whisper status
Ollama status
CoppeliaSim status
Enabled languages
Active fusion mode
Active safety limits
Suggest a simple optional local interface for selecting devices, configuration presets, and testing commands. Do not add a heavy user interface unless it provides clear value.
Testing and evaluation
Create a testing strategy containing:
Unit tests for command parsing
Unit tests for English aliases
Unit tests for Amharic aliases
Qwen-response validation tests
Fusion conflict tests
Priority tests
Gesture temporal-smoothing tests
Duplicate-command prevention tests
Emergency-stop tests
CoppeliaSim integration tests
Component-failure tests
Long-running stability tests
Offline verification
Performance benchmarks
For thesis evaluation, define measurable metrics:
Voice transcription accuracy
Voice command intent accuracy
Gesture classification accuracy
Multimodal command accuracy
False activation rate
Command rejection rate
End-to-end latency
CPU usage
Memory usage
Performance by language
Performance by modality
Performance under noise and poor lighting
Required planning output
Create a detailed implementation plan with the following sections:
Current codebase assessment
Main problems found
Proposed architecture
Proposed folder structure
Component responsibilities
Updated data flow
Voice-command improvement plan
Qwen and Ollama integration plan
English and Amharic support plan
Gesture-detection improvement plan
Multimodal fusion and priority plan
Configuration design
Performance optimization plan
Stability and safety plan
Testing and evaluation plan
Documentation plan
Migration strategy from the current code
Files to create
Files to modify
Files to remove or deprecate
Ordered implementation phases
Validation commands for every phase
Risks, trade-offs, and limitations
Final acceptance criteria
For every implementation phase, include:
Goal
Tasks
Files affected
Dependencies
Expected result
Tests
Performance checks
Risks
Completion criteria

Application entry point
The main and required application entry point must remain:
python3 main.py
The root-level main.py should remain small and should only be responsible for:
Loading command-line arguments
Loading and validating configuration
Initializing the application
Starting the UI
Starting required background services
Handling startup failures
Handling graceful shutdown
Returning an appropriate exit code
Move business logic out of main.py and into dedicated modules.

Running the following without arguments should open the main graphical interface using the default configuration:
python3 main.py

Graphical user interface
Create a clean, modern, lightweight, and easy-to-use desktop interface.
The UI must work fully offline and must not require a browser, cloud service, or internet connection.
Choose a lightweight Python UI framework suitable for an average laptop. Prefer a native desktop framework such as:
PySide6
PyQt6
CustomTkinter
Standard Tkinter when dependency size is a major concern
Evaluate the options and select the one that provides the best balance between:
Low resource consumption
Clean appearance
Camera rendering support
Real-time chart support
Thread-safe updates
Configuration controls
Cross-platform compatibility
Long-term maintainability
Avoid Electron, a local web server, or other heavy UI technologies unless the existing project already depends on them and there is a strong technical reason to retain them.
The UI must remain responsive while Whisper, MediaPipe, Ollama, microphone capture, camera capture, and CoppeliaSim communication are running. Never run model inference or blocking hardware operations on the main UI thread.
Use background workers, thread-safe signals, bounded queues, and controlled refresh rates.
Main UI layout
Design the interface with clear sections.
1. Header and system status
The header should display:
Application name
Current application mode
Active configuration preset
Offline status
Current language
Current fusion mode
Start or stop system button
Emergency stop button
The emergency stop button must:
Always remain visible
Use a clear warning style
Immediately stop robot movement
Bypass Whisper, Qwen, gesture classification, and normal fusion rules
Remain functional when another component fails
Display compact status indicators for:
Camera
Microphone
Whisper
MediaPipe
Ollama
Qwen model
CoppeliaSim
Robot controller
Possible states should include:
Ready
Starting
Active
Disabled
Degraded
Error
Disconnected
2. Camera panel
Add a live camera preview panel showing:
Current camera frame
Detected hand landmarks
Handedness
Detected gesture
Gesture confidence
Gesture state
Frame rate
Gesture inference latency
Provide UI controls to:
Enable or disable the camera
Select the camera device
Enable or disable preview
Enable or disable landmark rendering
Mirror the camera
Select resolution
Set gesture inference rate
Change confidence threshold
Change confirmation frame count
Change smoothing-window size
Change command cooldown
Do not update the UI for every captured frame if this wastes resources. Use a controlled preview refresh rate such as 15 to 30 FPS while gesture inference may run at a separate configurable rate.
The camera panel should show a clear placeholder when:
The camera is disabled
No camera exists
Permission is denied
The camera disconnects
Preview is disabled to save resources
3. Voice and audio panel
Add a voice-command panel containing:
Microphone state
Selected microphone
Current listening state
Detected language
Partial transcript when available
Final transcript
Normalized transcript
Recognized command
Voice confidence
Whisper processing latency
Qwen fallback status
Add a real-time audio waveform or voice-level visualizer.
The voice visualizer should:
Show microphone amplitude while listening
Use a low refresh rate sufficient for smooth feedback
Avoid storing raw audio unless explicitly enabled
Stop updating when the microphone is disabled
Indicate silence, speech detection, recording, and processing states
Use bounded audio buffers to avoid memory growth
Use a lightweight waveform implementation. Do not add a heavy plotting dependency only for the waveform if it can be rendered using the selected UI framework.
Provide voice controls for:
Enable or disable microphone
Start or stop listening
Push-to-talk mode
Continuous listening mode
Voice activity detection
Microphone selection
Language mode
Default language
Whisper model
Silence timeout
Maximum recording duration
Voice confidence threshold
Noise-normalization setting
Qwen fallback enabled or disabled
Support these language options:
Automatic language detection
English
Amharic
The UI should correctly render Amharic Unicode text.
4. Command and fusion panel
Show the command-processing pipeline clearly:
Input
→ Recognition
→ Normalization
→ Intent
→ Fusion
→ Safety validation
→ Robot execution
Display the most recent:
Voice event
Gesture event
Parsed intent
Fusion decision
Validated robot command
Rejected command
Rejection reason
Robot execution result
Show modality badges such as:
Voice
Gesture
Combined
Emergency
Manual
Provide configuration controls for:
Fusion mode
Voice priority
Gesture priority
Conflict policy
Event fusion window
Minimum voice confidence
Minimum gesture confidence
Duplicate-command cooldown
Stale-event timeout
Confirmation requirements
Maximum robot speed
Maximum command duration
Supported fusion modes should include:
Voice only
Gesture only
Either modality
Voice priority
Gesture priority
Latest command
Highest confidence
Confirmation mode
Combined mode
Use appropriate UI elements such as:
Dropdown menus
Toggle switches
Sliders
Numeric input fields
Checkboxes
Radio buttons
Tooltips
Reset buttons
Prevent invalid combinations through UI validation.
5. Robot control panel
Add a simple manual robot-control panel for testing.
Possible controls include:
Forward
Backward
Left
Right
Rotate left
Rotate right
Stop
Emergency stop
Speed slider
Manual commands must pass through the same command validation and safety layers as voice and gesture commands.
Do not allow the UI to directly call low-level robot movement functions.
Display:
Robot connection status
Simulation state
Last command
Current movement state
Current speed
Safety state
Command execution latency
6. Configuration interface
Add a dedicated configuration view.
Allow the user to:
Select a configuration preset
View all current settings
Modify supported settings
Search settings
Reset one setting
Reset one section
Reset all settings
Save settings
Save settings as a new preset
Import a configuration
Export a configuration
Reload configuration
Validate configuration before applying it
Group settings into clear categories:
General
Performance
Camera
Gesture
Microphone
Speech recognition
Languages
Ollama and Qwen
Multimodal fusion
Robot control
CoppeliaSim
Safety
Logging
Privacy
Testing
Changes that can be applied during runtime should be applied safely.
Changes that require restart or model reloading should be marked clearly. Ask for confirmation before restarting a model or service.
Provide these presets:
Low resource
Balanced
High accuracy
Voice only
Gesture only
Multimodal
Custom
The low-resource preset should reduce:
Camera resolution
Camera preview frame rate
Gesture inference rate
Debug rendering
Log verbosity
Whisper model size when appropriate
Qwen usage
UI refresh frequency
7. Log viewer
Add a structured log viewer inside the UI.
The log viewer should support:
Timestamp
Log level
Component
Message
Event type
Processing latency
Command source
Command result
Provide log filters for:
All
Debug
Information
Warning
Error
Critical
Voice
Gesture
Fusion
Robot
CoppeliaSim
Ollama
Performance
Safety
Add:
Search field
Pause auto-scroll
Resume auto-scroll
Clear visible logs
Copy selected log
Export logs
Maximum visible log count
Automatic removal of old UI log entries
Do not let the UI log viewer grow without a limit.
Keep the full application log separate from the UI’s bounded visible-log buffer.
Sensitive information should not be logged by default. Do not store:
Raw microphone audio
Camera frames
Full transcripts when transcript storage is disabled
Personal information
Allow transcript logging to be enabled explicitly for research experiments.
8. Performance dashboard
Add a lightweight performance view showing:
CPU usage
Memory usage
Camera FPS
Gesture inference FPS
Gesture latency
Whisper latency
Qwen latency
Fusion latency
Robot command latency
Queue sizes
Dropped camera frames
Rejected commands
Commands per modality
Application uptime
Use small, efficient charts or recent-value indicators.
Do not redraw large charts continuously. Keep a bounded history, such as the latest 60 to 300 samples, depending on the update frequency.
Allow performance monitoring to be disabled in the low-resource configuration.
9. Testing and diagnostics panel
Add UI actions for:
Test camera
Test microphone
Test audio waveform
Test Whisper
Test English command
Test Amharic command
Test Ollama connection
Test Qwen response schema
Test gesture detector
Test CoppeliaSim connection
Test robot stop command
Run system health check
Run short benchmark
Display clear pass, warning, or failure results.
The health check should not move the robot unless the user explicitly runs a robot movement test.
10. Experiment and thesis mode
Add an optional experiment mode for thesis evaluation.
This mode may provide:
Experiment name
Participant or session identifier
Enabled modalities
Selected language
Environment condition
Noise condition
Lighting condition
Expected command
Recognized command
Correct or incorrect result
Latency
Confidence
Notes
Do not enable participant tracking by default.
Experiment results should be exportable to CSV or JSON without storing video or audio unless explicitly enabled.
UI navigation
Use a simple navigation structure such as:
Dashboard
Camera and gestures
Voice commands
Robot control
Configuration
Logs
Performance
Diagnostics
Experiments
A sidebar or tab-based interface is acceptable.
Keep the most important information on the dashboard:
System state
Camera preview
Voice waveform
Current transcript
Current gesture
Current command
Robot status
Emergency stop
Recent warnings
Avoid placing every setting on the main dashboard.
UI state management
Use one central application-state model as the source of truth for the UI.
The UI should receive immutable status events or safe state snapshots from the application services.
Do not allow components to modify each other directly.
Define UI-facing models such as:
ComponentStatus(
    name="whisper",
    state="ready",
    message="Model loaded",
    latency_ms=0,
    timestamp=...
)
VoiceUIState(
    listening=True,
    speech_detected=True,
    language="am",
    transcript="ወደፊት ሂድ",
    normalized_text="ወደፊት ሂድ",
    confidence=0.88,
    processing_state="complete"
)
GestureUIState(
    camera_active=True,
    hand_detected=True,
    handedness="right",
    gesture="move_forward",
    confidence=0.92,
    confirmation_progress=4,
    confirmation_required=5
)
CommandUIState(
    source="combined",
    action="move",
    direction="forward",
    confidence=0.90,
    status="validated",
    rejection_reason=None
)
UI performance requirements
The UI must not significantly reduce recognition performance.
Include these requirements:
Keep all inference outside the main UI thread.
Use bounded queues between services and the UI.
Drop outdated camera preview frames.
Process only the newest available camera frame.
Limit waveform update frequency.
Limit metric update frequency.
Limit the number of visible logs.
Avoid unnecessary image conversions.
Reuse UI image objects where possible.
Do not rebuild full views for small status changes.
Shut down all UI workers cleanly.
Handle camera and microphone disconnection.
Handle Ollama and CoppeliaSim timeouts.
Prevent background workers from remaining active after the UI closes.
Suggested update limits:
ui:
  enabled: true
  theme: system
  camera_preview_fps: 20
  waveform_fps: 20
  metrics_refresh_ms: 1000
  status_refresh_ms: 250
  maximum_visible_logs: 1000
  chart_history_samples: 120
  show_landmarks: true
  show_performance_monitor: true
  confirm_before_exit: true
These values should remain configurable.
Clean visual design
The UI should have:
Consistent spacing
Clear typography
Accessible text sizes
Light and dark themes
Clear status colors
Responsive resizing
Tooltips for technical settings
Disabled states for unavailable controls
Confirmation dialogs for risky actions
Clear error messages
Clear empty states
Clear loading states
Avoid:
Excessive animations
Very bright colors
Too many panels on one screen
Large decorative elements
Constantly moving charts
Unnecessary dependencies
Blocking popups for minor events
Use subtle visual feedback for:
Listening
Speech detected
Processing voice
Gesture detected
Gesture confirmation progress
Command accepted
Command rejected
Robot moving
Emergency stop active

Do not write or change code during this first step.
Base the plan on the actual files you inspect. Do not assume a module exists unless it is present in the codebase. When information is missing, state the assumption clearly.
Prefer simple, lightweight, proven solutions. Avoid cloud services, large models, unnecessary frameworks, and architecture that would make the project harder to run locally.
At the end, provide a recommended implementation order that allows the project to remain runnable after every major phase.

