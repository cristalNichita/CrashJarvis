# Building CrashJarvis for Windows

CrashJarvis is distributed as a PyInstaller **one-folder** build. A one-file
executable would unpack the large CUDA and AI runtime on every start, so it is
not appropriate for this project.

## Requirements

- Windows 11 x64
- Python 3.13 x64
- NVIDIA GPU with a compatible driver
- PowerShell
- Ollama installed separately
- All local model files already present in `models/`

## Build

From the project root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
.\scripts\build.ps1
```

The script installs the locked project dependencies, runs PyInstaller, copies
the local models into the portable directory, and creates:

```text
dist\CrashJarvis\
dist\CrashJarvis-v0.1.0-windows-x64.zip
```

## Test before publishing

1. Start Ollama and make sure `ollama list` contains `qwen3.5:4b`.
2. Open `dist\CrashJarvis`.
3. Run `Start CrashJarvis.bat`.
4. Test wake word, transcription, one safe file operation, screenshot capture,
   TTS, microphone mute, and emergency stop.
5. Extract the ZIP to a different directory and repeat the launch test.

Do not publish a build containing personal screenshots, logs, or sandbox data.
The build script copies these folders, so clean them before building a release.
