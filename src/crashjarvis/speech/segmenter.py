from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from crashjarvis.audio.vad import (
    SpeechEvent,
    SpeechEventKind,
)


AudioBlock = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class SpeechSegment:
    audio: AudioBlock
    start_sample: int
    end_sample: int
    endpoint_delay_ms: float
    forced: bool = False

    def duration_seconds(self, sample_rate: int) -> float:
        return self.audio.size / sample_rate


class SpeechSegmentCollector:
    def __init__(
        self,
        sample_rate: int,
        pre_roll_ms: int,
        maximum_utterance_seconds: int,
    ) -> None:
        self._sample_rate = sample_rate
        self._pre_roll_samples = (
            sample_rate * pre_roll_ms // 1000
        )
        self._maximum_utterance_samples = (
            sample_rate * maximum_utterance_seconds
        )

        self._history = np.empty(0, dtype=np.float32)
        self._active_chunks: list[AudioBlock] = []

        self._total_received_samples = 0
        self._utterance_start_sample: int | None = None

    @property
    def is_active(self) -> bool:
        return self._utterance_start_sample is not None

    def active_audio_snapshot(self) -> AudioBlock | None:
        if not self._active_chunks:
            return None

        return np.concatenate(self._active_chunks).copy()

    def _append_history(self, block: AudioBlock) -> None:
        self._history = np.concatenate((self._history, block))

        if self._history.size > self._pre_roll_samples:
            self._history = self._history[
                -self._pre_roll_samples:
            ].copy()

    def _start_utterance(self, event: SpeechEvent) -> None:
        history_start_sample = (
            self._total_received_samples - self._history.size
        )
        start_sample = max(
            event.boundary_sample,
            history_start_sample,
        )
        history_offset = start_sample - history_start_sample

        self._utterance_start_sample = start_sample
        self._active_chunks = [
            self._history[history_offset:].copy()
        ]

    def _finish_utterance(
        self,
        end_sample: int,
        endpoint_delay_ms: float,
        forced: bool,
    ) -> SpeechSegment | None:
        if self._utterance_start_sample is None:
            return None

        combined = np.concatenate(self._active_chunks)
        segment_length = max(
            0,
            end_sample - self._utterance_start_sample,
        )
        segment_length = min(segment_length, combined.size)

        segment_audio = combined[:segment_length].copy()
        trailing_audio = combined[segment_length:].copy()

        segment = SpeechSegment(
            audio=segment_audio,
            start_sample=self._utterance_start_sample,
            end_sample=(
                self._utterance_start_sample
                + segment_audio.size
            ),
            endpoint_delay_ms=endpoint_delay_ms,
            forced=forced,
        )

        self._utterance_start_sample = None
        self._active_chunks = []
        self._history = trailing_audio[
            -self._pre_roll_samples:
        ].copy()

        if segment.audio.size == 0:
            return None

        return segment

    def process(
        self,
        block: AudioBlock,
        events: list[SpeechEvent],
    ) -> list[SpeechSegment]:
        audio = np.asarray(block, dtype=np.float32)

        if audio.ndim != 1:
            raise ValueError(
                "SpeechSegmentCollector expects mono audio."
            )

        self._total_received_samples += audio.size

        if self._utterance_start_sample is None:
            self._append_history(audio)
        else:
            self._active_chunks.append(audio.copy())

        completed_segments: list[SpeechSegment] = []

        for event in events:
            if (
                event.kind is SpeechEventKind.START
                and self._utterance_start_sample is None
            ):
                self._start_utterance(event)

            elif (
                event.kind is SpeechEventKind.END
                and self._utterance_start_sample is not None
            ):
                segment = self._finish_utterance(
                    end_sample=event.boundary_sample,
                    endpoint_delay_ms=event.detection_delay_ms(
                        self._sample_rate
                    ),
                    forced=False,
                )

                if segment is not None:
                    completed_segments.append(segment)

        if self._utterance_start_sample is not None:
            utterance_length = (
                self._total_received_samples
                - self._utterance_start_sample
            )

            if utterance_length >= self._maximum_utterance_samples:
                segment = self._finish_utterance(
                    end_sample=self._total_received_samples,
                    endpoint_delay_ms=0.0,
                    forced=True,
                )

                if segment is not None:
                    completed_segments.append(segment)

        return completed_segments