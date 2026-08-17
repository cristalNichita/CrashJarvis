from queue import Empty, Full, Queue
from typing import Any

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray

from crashjarvis.config import AudioConfig

AudioBlock = NDArray[np.float32]

class AudioCaptureError(RuntimeError):
    """Raised when the requested audio input cannot be used."""

class AudioCapture:
    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._blocks: Queue[AudioBlock] = Queue(
            maxsize=config.queue_capacity
        )

        self._stream: sd.InputStream | None = None
        self._device_index: int | None = None
        self._device_description: str | None = None
        self._dropped_blocks = 0

    @property
    def device_description(self) -> str:
        if self._device_description is None:
            return "Audio device has not been resolved yet."

        return self._device_description

    @property
    def dropped_blocks(self) -> int:
        return self._dropped_blocks

    def _resolve_device(self) -> int:
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()

        expected_device = self._config.device_name.casefold()
        expected_api = self._config.host_api_name.casefold()

        for index, device in enumerate(devices):
            if int(device["max_input_channels"]) < self._config.channels:
                continue

            host_api = host_apis[int(device["hostapi"])]
            device_name = str(device["name"])
            host_api_name = str(host_api["name"])

            if (
                expected_device in device_name.casefold()
                and expected_api in host_api_name.casefold()
            ):
                self._device_description = (
                    f"{device_name} via {host_api_name}, "
                    f"{self._config.capture_sample_rate} Hz"
                )
                return index

        raise AudioCaptureError(
            "Could not find the SteelSeries Sonar microphone "
            "through Windows WASAPI."
        )

    def _audio_callback(
        self,
        input_data: AudioBlock,
        _frame_count: int,
        _time_info: Any,
        _status: sd.CallbackFlags,
    ) -> None:
        block = input_data[:, 0].copy()

        try:
            self._blocks.put_nowait(block)
        except Full:
            self._dropped_blocks += 1

    def start(self) -> None:
        if self._stream is not None:
            return

        self._device_index = self._resolve_device()

        try:
            self._stream = sd.InputStream(
                device=self._device_index,
                samplerate=self._config.capture_sample_rate,
                channels=self._config.channels,
                dtype="float32",
                blocksize=self._config.block_size,
                latency="low",
                callback=self._audio_callback,
            )
            self._stream.start()
        except sd.PortAudioError as error:
            self._stream = None
            raise AudioCaptureError(
                f"Could not start the microphone stream: {error}"
            ) from error

    def read(self, timeout: float = 1.0) -> AudioBlock:
        try:
            return self._blocks.get(timeout=timeout)
        except Empty as error:
            raise AudioCaptureError(
                "No audio block was received within the timeout."
            ) from error

    def stop(self) -> None:
        if self._stream is None:
            return

        self._stream.stop()
        self._stream.close()
        self._stream = None

    def __enter__(self) -> "AudioCapture":
        self.start()
        return self

    def __exit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        self.stop()