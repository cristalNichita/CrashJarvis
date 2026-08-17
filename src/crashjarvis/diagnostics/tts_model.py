from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter

import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro


MODEL_PATH = Path("models/tts/kokoro-v1.0.onnx")
VOICES_PATH = Path("models/tts/voices-v1.0.bin")

VOICE = "am_michael"
LANGUAGE = "en-us"
SPEED = 1.0
TEXT = "Good evening. CrashJarvis is online and ready to assist."


class TtsDiagnosticError(RuntimeError):
    """Raised when the standalone TTS diagnostic cannot run."""


def require_file(path: Path) -> Path:
    resolved_path = path.resolve()

    if not resolved_path.is_file():
        raise TtsDiagnosticError(
            f"Required model file was not found: {resolved_path}"
        )

    return resolved_path


def output_device_name() -> str:
    try:
        device = sd.query_devices(kind="output")
    except Exception as error:
        raise TtsDiagnosticError(
            f"Windows audio output device is unavailable: {error}"
        ) from error

    return str(device["name"])


def main() -> None:
    print("CrashJarvis Kokoro TTS test")
    print("Mode: local CPU")
    print("Network use: none")

    model_path = require_file(MODEL_PATH)
    voices_path = require_file(VOICES_PATH)
    device_name = output_device_name()

    print(f"Model: {model_path}")
    print(f"Voices: {voices_path}")
    print(f"Voice: {VOICE}")
    print(f"Output: {device_name}")
    print()

    # kokoro-onnx reads this variable while creating its ONNX session.
    # Setting it here keeps TTS on the CPU even if onnxruntime-gpu is present.
    os.environ["ONNX_PROVIDER"] = "CPUExecutionProvider"

    print("Loading Kokoro on CPU...")
    load_started_at = perf_counter()
    kokoro = Kokoro(
        str(model_path),
        str(voices_path),
    )
    load_ms = (perf_counter() - load_started_at) * 1000.0

    providers = kokoro.sess.get_providers()

    if providers[0] != "CPUExecutionProvider":
        raise TtsDiagnosticError(
            "Kokoro did not select CPUExecutionProvider. "
            f"Active providers: {providers}"
        )

    print(f"Kokoro loaded in {load_ms:.1f} ms.")
    print(f"ONNX providers: {', '.join(providers)}")
    print()

    print(f'Synthesizing: "{TEXT}"')
    response_started_at = perf_counter()
    generation_started_at = perf_counter()

    samples, sample_rate = kokoro.create(
        TEXT,
        voice=VOICE,
        speed=SPEED,
        lang=LANGUAGE,
    )

    generation_finished_at = perf_counter()
    generation_ms = (
        generation_finished_at - generation_started_at
    ) * 1000.0

    audio = np.asarray(samples, dtype=np.float32).squeeze()

    if audio.ndim != 1 or audio.size == 0:
        raise TtsDiagnosticError(
            f"Kokoro returned an invalid audio shape: {audio.shape}"
        )

    audio_duration_seconds = audio.size / float(sample_rate)
    real_time_factor = (
        generation_ms / 1000.0 / audio_duration_seconds
    )

    print("Starting playback...")
    sd.play(audio, samplerate=sample_rate, blocking=False)
    playback_dispatched_at = perf_counter()

    response_to_playback_ms = (
        playback_dispatched_at - response_started_at
    ) * 1000.0

    print()
    print(f"Load: {load_ms:.1f} ms")
    print(f"Generation: {generation_ms:.1f} ms")
    print(f"Playback dispatch: {response_to_playback_ms:.1f} ms")
    print(f"Audio duration: {audio_duration_seconds:.2f} s")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Real-time factor: {real_time_factor:.3f}")
    print("Waiting for playback to finish...")

    sd.wait()
    print("Kokoro TTS test completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except TtsDiagnosticError as error:
        raise SystemExit(f"TTS diagnostic error: {error}") from error
    except KeyboardInterrupt:
        raise SystemExit("TTS diagnostic stopped by the user.") from None