import numpy as np
import soxr
from numpy.typing import NDArray

AudioBlock = NDArray[np.float32]

class AudioResamplerError(ValueError):
    """Raised when an invalid audio block is passed to the resampler."""

class StreamingAudioResampler:
    def __init__(
        self,
        source_sample_rate: int,
        target_sample_rate: int,
    ) -> None:
        if source_sample_rate <= 0 or target_sample_rate <= 0:
            raise ValueError("Sample rates must be positive.")

        self._target_sample_rate = target_sample_rate
        self._stream = soxr.ResampleStream(
            source_sample_rate,
            target_sample_rate,
            1,
            dtype="float32",
            quality="LQ",
        )

    @property
    def pending_output_samples(self) -> float:
        return float(self._stream.delay())

    @property
    def pending_delay_ms(self) -> float:
        return (
            self.pending_output_samples
            / self._target_sample_rate
            * 1000.0
        )

    def process(self, block: AudioBlock) -> AudioBlock:
        audio = np.asarray(block, dtype=np.float32)

        if audio.ndim != 1:
            raise AudioResamplerError(
                "The streaming resampler expects mono one-dimensional audio."
            )

        if audio.size == 0:
            return np.empty(0, dtype=np.float32)

        contiguous_audio = np.ascontiguousarray(audio)

        return self._stream.resample_chunk(
            contiguous_audio,
            last=False
        )

    def reset(self) -> None:
        self._stream.clear()