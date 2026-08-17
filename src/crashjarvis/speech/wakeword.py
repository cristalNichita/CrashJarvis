from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np
from numpy.typing import NDArray
from openwakeword.model import Model


AudioBlock = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class WakeWordPrediction:
    score: float
    inference_ms: float
    detected: bool


class WakeWordDetector:
    SAMPLE_RATE = 16_000
    FRAME_DURATION_MS = 80
    FRAME_SAMPLES = SAMPLE_RATE * FRAME_DURATION_MS // 1_000

    def __init__(
        self,
        model_directory: Path,
        threshold: float = 0.5,
        cooldown_seconds: float = 1.5,
    ) -> None:
        if not 0.0 < threshold < 1.0:
            raise ValueError("Wake-word threshold must be between 0 and 1.")

        if cooldown_seconds < 0.0:
            raise ValueError("Wake-word cooldown cannot be negative.")

        self._threshold = threshold
        self._cooldown_seconds = cooldown_seconds
        self._pending_audio = np.empty(0, dtype=np.float32)
        self._last_detection_at: float | None = None

        wake_word_model = model_directory / "hey_jarvis_v0.1.onnx"
        melspectrogram_model = model_directory / "melspectrogram.onnx"
        embedding_model = model_directory / "embedding_model.onnx"

        for model_path in (
            wake_word_model,
            melspectrogram_model,
            embedding_model,
        ):
            if not model_path.is_file():
                raise FileNotFoundError(
                    f"Required wake-word model was not found: "
                    f"{model_path.resolve()}"
                )

        self._model = Model(
            wakeword_models=[str(wake_word_model)],
            inference_framework="onnx",
            melspec_model_path=str(melspectrogram_model),
            embedding_model_path=str(embedding_model),
            ncpu=1,
            device="cpu",
        )

        self._model_name = next(iter(self._model.models))

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def threshold(self) -> float:
        return self._threshold

    def process(
        self,
        audio: AudioBlock,
    ) -> tuple[WakeWordPrediction, ...]:
        if audio.size == 0:
            return ()

        normalized_audio = np.asarray(
            audio,
            dtype=np.float32,
        ).reshape(-1)

        self._pending_audio = np.concatenate(
            (self._pending_audio, normalized_audio)
        )

        predictions: list[WakeWordPrediction] = []

        while self._pending_audio.size >= self.FRAME_SAMPLES:
            frame = self._pending_audio[:self.FRAME_SAMPLES]
            self._pending_audio = self._pending_audio[
                self.FRAME_SAMPLES:
            ]

            pcm16_frame = np.rint(
                np.clip(frame, -1.0, 1.0) * 32767.0
            ).astype(np.int16)

            inference_started = perf_counter()
            scores = self._model.predict(pcm16_frame)
            inference_ms = (
                perf_counter() - inference_started
            ) * 1000.0

            score = float(scores[self._model_name])
            detected = self._should_activate(score)

            predictions.append(
                WakeWordPrediction(
                    score=score,
                    inference_ms=inference_ms,
                    detected=detected,
                )
            )

        return tuple(predictions)

    def _should_activate(self, score: float) -> bool:
        if score < self._threshold:
            return False

        now = perf_counter()

        if self._last_detection_at is not None:
            elapsed = now - self._last_detection_at

            if elapsed < self._cooldown_seconds:
                return False

        self._last_detection_at = now
        return True

    def reset(self) -> None:
        self._pending_audio = np.empty(0, dtype=np.float32)
        self._last_detection_at = None
        self._model.reset()