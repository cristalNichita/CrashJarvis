from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Thread
from time import perf_counter

import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro


MODEL_PATH = Path("models/tts/kokoro-v1.0.onnx")
VOICES_PATH = Path("models/tts/voices-v1.0.bin")

VOICE = "am_michael"
LANGUAGE = "en-us"
SPEED = 1.0

WARMUP_TEXT = "Ready."
TEST_TEXT = (
    "The task is complete. I found the newest video and moved it "
    "to the Recording folder."
)

_PLAYBACK_END = object()


class StreamingTtsDiagnosticError(RuntimeError):
    """Raised when the streaming TTS diagnostic cannot run."""


@dataclass(slots=True)
class PlaybackMetrics:
    first_write_started_at: float | None = None
    finished_at: float | None = None
    underflow_count: int = 0


class AudioChunkPlayer:
    """Writes generated audio chunks to one continuous output stream."""

    def __init__(self, sample_rate: int) -> None:
        self._sample_rate = sample_rate
        self._queue: Queue[np.ndarray | object] = Queue()
        self._errors: list[Exception] = []
        self._thread = Thread(
            target=self._run,
            name="crashjarvis-tts-playback",
            daemon=True,
        )
        self.metrics = PlaybackMetrics()

    def start(self) -> None:
        self._thread.start()

    def enqueue(self, audio: np.ndarray) -> None:
        self._queue.put(audio)

    def finish(self) -> None:
        self._queue.put(_PLAYBACK_END)
        self._thread.join()

        if self._errors:
            raise StreamingTtsDiagnosticError(
                f"Audio playback failed: {self._errors[0]}"
            ) from self._errors[0]

    def _run(self) -> None:
        try:
            with sd.OutputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
            ) as stream:
                while True:
                    item = self._queue.get()

                    if item is _PLAYBACK_END:
                        break

                    if not isinstance(item, np.ndarray):
                        raise StreamingTtsDiagnosticError(
                            "Playback queue received invalid audio data."
                        )

                    if self.metrics.first_write_started_at is None:
                        self.metrics.first_write_started_at = perf_counter()

                    underflowed = stream.write(
                        item.reshape(-1, 1)
                    )

                    if underflowed:
                        self.metrics.underflow_count += 1

                stream.stop()

            self.metrics.finished_at = perf_counter()

        except Exception as error:
            self._errors.append(error)


def require_file(path: Path) -> Path:
    resolved_path = path.resolve()

    if not resolved_path.is_file():
        raise StreamingTtsDiagnosticError(
            f"Required model file was not found: {resolved_path}"
        )

    return resolved_path


def output_device_name() -> str:
    try:
        device = sd.query_devices(kind="output")
    except Exception as error:
        raise StreamingTtsDiagnosticError(
            f"Windows audio output device is unavailable: {error}"
        ) from error

    return str(device["name"])


async def run_streaming_test(kokoro: Kokoro) -> None:
    print(f'Streaming: "{TEST_TEXT}"')

    response_started_at = perf_counter()
    first_chunk_at: float | None = None
    generation_finished_at: float | None = None
    player: AudioChunkPlayer | None = None
    expected_sample_rate: int | None = None
    chunk_count = 0
    total_samples = 0

    async for samples, sample_rate in kokoro.create_stream(
        TEST_TEXT,
        voice=VOICE,
        speed=SPEED,
        lang=LANGUAGE,
    ):
        chunk_received_at = perf_counter()
        audio = np.asarray(samples, dtype=np.float32).squeeze()

        if audio.ndim != 1 or audio.size == 0:
            raise StreamingTtsDiagnosticError(
                f"Kokoro returned an invalid audio shape: {audio.shape}"
            )

        if first_chunk_at is None:
            first_chunk_at = chunk_received_at
            expected_sample_rate = sample_rate
            player = AudioChunkPlayer(sample_rate)
            player.start()

        if sample_rate != expected_sample_rate:
            raise StreamingTtsDiagnosticError(
                "Kokoro changed the sample rate during one response."
            )

        chunk_count += 1
        total_samples += audio.size

        if player is None:
            raise StreamingTtsDiagnosticError(
                "Audio player was not initialized."
            )

        player.enqueue(audio)
        print(
            f"[CHUNK {chunk_count}] "
            f"{audio.size / sample_rate:.2f} s of audio"
        )

    generation_finished_at = perf_counter()

    if (
        player is None
        or first_chunk_at is None
        or expected_sample_rate is None
        or chunk_count == 0
    ):
        raise StreamingTtsDiagnosticError(
            "Kokoro completed without producing audio."
        )

    player.finish()

    first_write_at = player.metrics.first_write_started_at
    playback_finished_at = player.metrics.finished_at

    if first_write_at is None or playback_finished_at is None:
        raise StreamingTtsDiagnosticError(
            "Playback timing information is incomplete."
        )

    first_chunk_ms = (
        first_chunk_at - response_started_at
    ) * 1000.0
    first_playback_dispatch_ms = (
        first_write_at - response_started_at
    ) * 1000.0
    total_generation_ms = (
        generation_finished_at - response_started_at
    ) * 1000.0
    total_wall_ms = (
        playback_finished_at - response_started_at
    ) * 1000.0
    audio_duration_seconds = (
        total_samples / float(expected_sample_rate)
    )

    print()
    print(f"First chunk: {first_chunk_ms:.1f} ms")
    print(
        "First playback dispatch: "
        f"{first_playback_dispatch_ms:.1f} ms"
    )
    print(f"Stream generation: {total_generation_ms:.1f} ms")
    print(f"Playback completed: {total_wall_ms:.1f} ms")
    print(f"Chunks: {chunk_count}")
    print(f"Audio duration: {audio_duration_seconds:.2f} s")
    print(f"Sample rate: {expected_sample_rate} Hz")
    print(f"Playback underflows: {player.metrics.underflow_count}")


async def main() -> None:
    print("CrashJarvis streaming Kokoro TTS test")
    print("Mode: warm local CPU model")
    print("Network use: none")

    model_path = require_file(MODEL_PATH)
    voices_path = require_file(VOICES_PATH)
    device_name = output_device_name()

    print(f"Voice: {VOICE}")
    print(f"Output: {device_name}")
    print()

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
        raise StreamingTtsDiagnosticError(
            "Kokoro did not select CPUExecutionProvider. "
            f"Active providers: {providers}"
        )

    print(f"Kokoro loaded in {load_ms:.1f} ms.")
    print(f"ONNX providers: {', '.join(providers)}")

    print("Warming up the loaded model...")
    warmup_started_at = perf_counter()
    kokoro.create(
        WARMUP_TEXT,
        voice=VOICE,
        speed=SPEED,
        lang=LANGUAGE,
    )
    warmup_ms = (perf_counter() - warmup_started_at) * 1000.0
    print(f"Warm-up: {warmup_ms:.1f} ms")
    print()

    await run_streaming_test(kokoro)
    print("Streaming Kokoro TTS test completed successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except StreamingTtsDiagnosticError as error:
        raise SystemExit(f"TTS diagnostic error: {error}") from error
    except KeyboardInterrupt:
        raise SystemExit("TTS diagnostic stopped by the user.") from None