from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

from crashjarvis.config import VadConfig


AudioBlock = NDArray[np.float32]


class SpeechEventKind(StrEnum):
    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True)
class SpeechEvent:
    kind: SpeechEventKind
    boundary_sample: int
    detected_sample: int
    inference_ms: float

    def boundary_seconds(self, sample_rate: int) -> float:
        return self.boundary_sample / sample_rate

    def detection_delay_ms(self, sample_rate: int) -> float:
        return (
            self.detected_sample - self.boundary_sample
        ) / sample_rate * 1000.0


class VoiceActivityDetector:
    def __init__(self, config: VadConfig) -> None:
        self._config = config

        if not config.model_path.is_file():
            raise FileNotFoundError(
                f"Silero VAD model was not found: {config.model_path}"
            )

        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = 1
        session_options.inter_op_num_threads = 1
        session_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        self._session = ort.InferenceSession(
            str(config.model_path),
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )

        self._audio_buffer = np.empty(0, dtype=np.float32)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)

        self._current_sample = 0
        self._temporary_end_sample = 0
        self._speech_active = False

        self._processed_frames = 0
        self._total_inference_ms = 0.0
        self._last_inference_ms = 0.0
        self._last_probability = 0.0

    @property
    def speech_active(self) -> bool:
        return self._speech_active

    @property
    def last_probability(self) -> float:
        return self._last_probability

    @property
    def last_inference_ms(self) -> float:
        return self._last_inference_ms

    @property
    def processed_frames(self) -> int:
        return self._processed_frames

    @property
    def average_inference_ms(self) -> float:
        if self._processed_frames == 0:
            return 0.0

        return self._total_inference_ms / self._processed_frames

    def _predict(self, frame: AudioBlock) -> float:
        frame_batch = frame.reshape(1, -1)
        model_input = np.concatenate(
            (self._context, frame_batch),
            axis=1,
        )

        started_at = perf_counter()

        output, new_state = self._session.run(
            ["output", "stateN"],
            {
                "input": model_input,
                "state": self._state,
                "sr": np.array(
                    self._config.sample_rate,
                    dtype=np.int64,
                ),
            },
        )

        inference_ms = (perf_counter() - started_at) * 1000.0

        self._state = new_state
        self._context = model_input[:, -64:].copy()

        self._last_inference_ms = inference_ms
        self._total_inference_ms += inference_ms
        self._processed_frames += 1

        return float(output.squeeze())

    def _create_event(
        self,
        probability: float,
    ) -> SpeechEvent | None:
        self._last_probability = probability
        self._current_sample += self._config.frame_size

        speech_padding_samples = (
            self._config.sample_rate
            * self._config.speech_padding_ms
            // 1000
        )
        minimum_silence_samples = (
            self._config.sample_rate
            * self._config.minimum_silence_ms
            // 1000
        )

        if (
            probability >= self._config.speech_threshold
            and self._temporary_end_sample
        ):
            self._temporary_end_sample = 0

        if (
            probability >= self._config.speech_threshold
            and not self._speech_active
        ):
            self._speech_active = True

            boundary_sample = max(
                0,
                self._current_sample
                - speech_padding_samples
                - self._config.frame_size,
            )

            return SpeechEvent(
                kind=SpeechEventKind.START,
                boundary_sample=boundary_sample,
                detected_sample=self._current_sample,
                inference_ms=self._last_inference_ms,
            )

        if (
            probability < self._config.silence_threshold
            and self._speech_active
        ):
            if self._temporary_end_sample == 0:
                self._temporary_end_sample = self._current_sample

            silence_length = (
                self._current_sample
                - self._temporary_end_sample
            )

            if silence_length >= minimum_silence_samples:
                boundary_sample = max(
                    0,
                    self._temporary_end_sample
                    + speech_padding_samples
                    - self._config.frame_size,
                )

                self._temporary_end_sample = 0
                self._speech_active = False

                return SpeechEvent(
                    kind=SpeechEventKind.END,
                    boundary_sample=boundary_sample,
                    detected_sample=self._current_sample,
                    inference_ms=self._last_inference_ms,
                )

        return None

    def process(self, block: AudioBlock) -> list[SpeechEvent]:
        audio = np.asarray(block, dtype=np.float32)

        if audio.ndim != 1:
            raise ValueError("Silero VAD expects mono audio.")

        if audio.size == 0:
            return []

        combined = np.concatenate((self._audio_buffer, audio))
        complete_frame_count = combined.size // self._config.frame_size
        complete_sample_count = (
            complete_frame_count * self._config.frame_size
        )

        self._audio_buffer = combined[complete_sample_count:].copy()
        events: list[SpeechEvent] = []

        for frame_index in range(complete_frame_count):
            start = frame_index * self._config.frame_size
            end = start + self._config.frame_size
            frame = combined[start:end].copy()

            probability = self._predict(frame)
            event = self._create_event(probability)

            if event is not None:
                events.append(event)

        return events

    def reset(self) -> None:
        self._audio_buffer = np.empty(0, dtype=np.float32)
        self._state.fill(0.0)
        self._context.fill(0.0)

        self._current_sample = 0
        self._temporary_end_sample = 0
        self._speech_active = False
        self._last_probability = 0.0