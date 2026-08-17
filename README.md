# CrashJarvis

CrashJarvis is a local voice AI agent for Windows built for the Crashbyt YouTube
channel. It listens for **вЂњHey JarvisвЂќ**, transcribes speech locally, lets a
local Qwen model choose tools, controls desktop applications, and answers with
a local Kokoro voice.

> CrashJarvis v0.1 is an experimental prototype, not a production security
> product. Review the code and use it only on a machine where you understand
> the consequences of desktop automation.

## Features

- Wake-word activation with openWakeWord
- Voice activity detection with Silero VAD
- GPU speech recognition with faster-whisper
- Local reasoning and tool calling through Ollama and Qwen
- Application launching and window management
- Windows UI Automation, keyboard shortcuts, clicking, and text input
- Sandboxed file operations with an operation journal
- Local screen inspection and screenshot capture
- Local Kokoro ONNX text-to-speech
- PySide6 interface with live state, transcript, logs, and latency metrics
- Microphone mute and emergency stop controls

## Requirements

- Windows 11 x64
- Python 3.13 x64 (source installation)
- NVIDIA GPU and current NVIDIA driver
- [Ollama](https://ollama.com/) with the `qwen3.5:4b` model
- A microphone available through Windows WASAPI

The project intentionally does not commit AI model files. They belong under
`models/` and are ignored by Git.

## Expected model layout

```text
models/
в”њв”Ђв”Ђ asr/
в”њв”Ђв”Ђ silero_vad.onnx
в”њв”Ђв”Ђ tts/
в”‚   в”њв”Ђв”Ђ kokoro-v1.0.onnx
в”‚   в””в”Ђв”Ђ voices-v1.0.bin
в””в”Ђв”Ђ wakeword/
    в”њв”Ђв”Ђ embedding_model.onnx
    в”њв”Ђв”Ђ hey_jarvis_v0.1.onnx
    в””в”Ђв”Ђ melspectrogram.onnx
```

## Source setup

```powershell
git clone https://github.com/cristalNichita/CrashJarvis.git
cd CrashJarvis
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --editable .
ollama pull qwen3.5:4b
python -m crashjarvis.ui.runtime_app
```

The current v0.1 microphone configuration targets `SteelSeries Sonar -
Microphone` through Windows WASAPI. If you use another microphone, change
`AudioConfig.device_name` in `src/crashjarvis/config.py` before running from
source or creating a build.

## Safety model

File tools are restricted to the local `sandbox/` directory and operations are
recorded in `logs/operations.jsonl`. Desktop automation can still interact with
visible applications and type into the focused window. CrashJarvis explicitly
rejects using its text-input tool for passwords, authentication codes, API
keys, payment information, and other secrets.

Keep the emergency-stop button accessible while testing. Do not run the agent
with elevated administrator privileges.

## Build

See [BUILDING.md](BUILDING.md) or run:

```powershell
.\scripts\build.ps1
```

## Project status

This repository contains the v0.1 prototype made for a YouTube experiment.
Issues and pull requests are welcome, but there is no guarantee of production
support or compatibility with every Windows setup.

## License

MIT вЂ” see [LICENSE](LICENSE).

