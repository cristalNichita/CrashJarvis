from __future__ import annotations

import os
import re
from dataclasses import dataclass
from threading import Lock
from time import perf_counter

import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro

from crashjarvis.config import TtsConfig


_MARKDOWN_LINK = re.compile(r"\[([^\]]+)]\([^)]+\)")
_WHITESPACE = re.compile(r"\s+")


class SpeechSynthesisError(RuntimeError):
    """Raised when the local voice response cannot be produced."""


@dataclass(frozen=True, slots=True)
class SpeechSynthesisResult:
    spoken_text: str
    generation_ms: float
    response_to_playback_ms: float
    audio_duration_seconds: float
    total_duration_ms: float
    sample_rate: int


class KokoroSpeechSynthesizer:
    """Persistent, CPU-only Kokoro speech synthesizer."""

    def __init__(self, config: TtsConfig) -> None:
        self._config = config
        self._lock = Lock()

        self._validate_config()

        model_path = config.model_path.resolve()
        voices_path = config.voices_path.resolve()

        if not model_path.is_file():
            raise SpeechSynthesisError(
                f"Kokoro model was not found: {model_path}"
            )

        if not voices_path.is_file():
            raise SpeechSynthesisError(
                f"Kokoro voices were not found: {voices_path}"
            )

        previous_provider = os.environ.get("ONNX_PROVIDER")
        os.environ["ONNX_PROVIDER"] = "CPUExecutionProvider"

        load_started_at = perf_counter()

        try:
            self._kokoro = Kokoro(
                str(model_path),
                str(voices_path),
            )
        except Exception as error:
            raise SpeechSynthesisError(
                f"Kokoro could not be loaded: {error}"
            ) from error
        finally:
            if previous_provider is None:
                os.environ.pop("ONNX_PROVIDER", None)
            else:
                os.environ["ONNX_PROVIDER"] = previous_provider

        self.load_time_ms = (
            perf_counter() - load_started_at
        ) * 1000.0

        self.providers = tuple(
            self._kokoro.sess.get_providers()
        )

        if (
            not self.providers
            or self.providers[0] != "CPUExecutionProvider"
        ):
            raise SpeechSynthesisError(
                "Kokoro did not select CPUExecutionProvider. "
                f"Active providers: {self.providers}"
            )

        available_voices = self._kokoro.get_voices()

        if config.voice not in available_voices:
            raise SpeechSynthesisError(
                f"Kokoro voice is unavailable: {config.voice}"
            )

    def warm_up(self) -> float:
        """Run one silent synthesis so later requests are warm."""

        started_at = perf_counter()

        with self._lock:
            try:
                self._kokoro.create(
                    self._config.warmup_text,
                    voice=self._config.voice,
                    speed=self._config.speed,
                    lang=self._config.language,
                )
            except Exception as error:
                raise SpeechSynthesisError(
                    f"Kokoro warm-up failed: {error}"
                ) from error

        return (perf_counter() - started_at) * 1000.0

    def speak(self, text: str) -> SpeechSynthesisResult:
        """Generate and play one short response synchronously."""

        spoken_text = self._prepare_text(text)
        response_started_at = perf_counter()

        with self._lock:
            generation_started_at = perf_counter()

            try:
                samples, sample_rate = self._kokoro.create(
                    spoken_text,
                    voice=self._config.voice,
                    speed=self._config.speed,
                    lang=self._config.language,
                )
            except Exception as error:
                raise SpeechSynthesisError(
                    f"Kokoro synthesis failed: {error}"
                ) from error

            generation_finished_at = perf_counter()
            generation_ms = (
                generation_finished_at - generation_started_at
            ) * 1000.0

            audio = np.asarray(
                samples,
                dtype=np.float32,
            ).squeeze()

            if audio.ndim != 1 or audio.size == 0:
                raise SpeechSynthesisError(
                    "Kokoro returned invalid audio with shape "
                    f"{audio.shape}."
                )

            audio = np.clip(
                audio * self._config.volume,
                -1.0,
                1.0,
            )

            try:
                sd.play(
                    audio,
                    samplerate=sample_rate,
                    blocking=False,
                )
                playback_dispatched_at = perf_counter()
                sd.wait()
            except Exception as error:
                sd.stop()
                raise SpeechSynthesisError(
                    f"Voice playback failed: {error}"
                ) from error

        finished_at = perf_counter()

        return SpeechSynthesisResult(
            spoken_text=spoken_text,
            generation_ms=generation_ms,
            response_to_playback_ms=(
                playback_dispatched_at - response_started_at
            ) * 1000.0,
            audio_duration_seconds=(
                audio.size / float(sample_rate)
            ),
            total_duration_ms=(
                finished_at - response_started_at
            ) * 1000.0,
            sample_rate=sample_rate,
        )

    def stop(self) -> None:
        """Stop current playback if one is active."""

        sd.stop()

    def _prepare_text(self, text: str) -> str:
        if not isinstance(text, str):
            raise SpeechSynthesisError(
                "The voice response must be a string."
            )

        prepared = _MARKDOWN_LINK.sub(r"\1", text)
        prepared = prepared.replace("`", "")
        prepared = prepared.replace("*", "")
        prepared = prepared.replace("#", "")
        prepared = prepared.replace("_", " ")
        prepared = _WHITESPACE.sub(" ", prepared).strip()

        if not prepared:
            raise SpeechSynthesisError(
                "The voice response is empty."
            )

        return prepared[
            : self._config.maximum_text_characters
        ].rstrip()

    def _validate_config(self) -> None:
        if not 0.5 <= self._config.speed <= 2.0:
            raise SpeechSynthesisError(
                "TTS speed must be between 0.5 and 2.0."
            )

        if not 0.0 < self._config.volume <= 1.0:
            raise SpeechSynthesisError(
                "TTS volume must be greater than 0 and at most 1."
            )

        if self._config.maximum_text_characters < 1:
            raise SpeechSynthesisError(
                "maximum_text_characters must be positive."
            )