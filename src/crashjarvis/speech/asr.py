from dataclasses import dataclass
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from crashjarvis.config import (
    AsrConfig,
    WhisperModelConfig,
)
from crashjarvis.infrastructure.cuda_runtime import (
    configure_cuda_runtime,
)


AudioBlock = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    model_name: str
    audio_duration_seconds: float
    inference_ms: float
    language: str
    language_probability: float


class WhisperTranscriber:
    def __init__(
        self,
        config: AsrConfig,
        model_config: WhisperModelConfig,
    ) -> None:
        self._config = config
        self._model_config = model_config

        configure_cuda_runtime()

        from faster_whisper import WhisperModel

        config.model_cache.mkdir(parents=True, exist_ok=True)

        self._model = WhisperModel(
            model_config.name,
            device="cuda",
            compute_type=model_config.compute_type,
            download_root=str(config.model_cache),
        )

    def transcribe(
        self,
        audio: AudioBlock,
    ) -> TranscriptionResult:
        prepared_audio = np.ascontiguousarray(
            audio,
            dtype=np.float32,
        )

        started_at = perf_counter()

        segments, information = self._model.transcribe(
            prepared_audio,
            language=self._config.language,
            task="transcribe",
            beam_size=self._config.beam_size,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
            word_timestamps=False,
        )

        recognized_segments = list(segments)

        inference_ms = (
            perf_counter() - started_at
        ) * 1000.0

        text = " ".join(
            segment.text.strip()
            for segment in recognized_segments
            if segment.text.strip()
        ).strip()

        return TranscriptionResult(
            text=text,
            model_name=self._model_config.name,
            audio_duration_seconds=(
                prepared_audio.size / self._config.sample_rate
            ),
            inference_ms=inference_ms,
            language=information.language,
            language_probability=(
                information.language_probability
            ),
        )