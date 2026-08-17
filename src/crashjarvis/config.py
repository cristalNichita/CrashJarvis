from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AudioConfig:
    device_name: str = "SteelSeries Sonar - Microphone"
    host_api_name: str = "Windows WASAPI"

    capture_sample_rate: int = 48_000
    processing_sample_rate: int = 16_000

    channels: int = 1
    block_duration_ms: int = 20
    queue_capacity: int = 100

    @property
    def block_size(self) -> int:
        return (
            self.capture_sample_rate
            * self.block_duration_ms
            // 1000
        )


@dataclass(frozen=True, slots=True)
class VadConfig:
    model_path: Path = Path("models/silero_vad.onnx")

    sample_rate: int = 16_000
    frame_duration_ms: int = 32

    speech_threshold: float = 0.5
    silence_threshold: float = 0.35

    minimum_silence_ms: int = 300
    speech_padding_ms: int = 30

    @property
    def frame_size(self) -> int:
        return (
            self.sample_rate
            * self.frame_duration_ms
            // 1000
        )


@dataclass(frozen=True, slots=True)
class WakeWordConfig:
    model_directory: Path = Path("models/wakeword")

    threshold: float = 0.5
    cooldown_seconds: float = 1.5
    command_timeout_seconds: float = 8.0


@dataclass(frozen=True, slots=True)
class WhisperModelConfig:
    name: str
    compute_type: str


@dataclass(frozen=True, slots=True)
class AsrConfig:
    final_model: WhisperModelConfig = WhisperModelConfig(
        name="large-v3-turbo",
        compute_type="float16",
    )
    partial_model: WhisperModelConfig = WhisperModelConfig(
        name="small.en",
        compute_type="int8_float16",
    )

    model_cache: Path = Path("models/asr")
    sample_rate: int = 16_000
    language: str = "en"
    beam_size: int = 1

    pre_roll_ms: int = 500
    maximum_utterance_seconds: int = 30

    partial_minimum_audio_ms: int = 900
    partial_interval_ms: int = 600


@dataclass(frozen=True, slots=True)
class TtsConfig:
    model_path: Path = Path(
        "models/tts/kokoro-v1.0.onnx"
    )
    voices_path: Path = Path(
        "models/tts/voices-v1.0.bin"
    )

    voice: str = "am_michael"
    language: str = "en-us"
    speed: float = 1.0
    volume: float = 0.9

    warmup_text: str = "Ready."
    maximum_text_characters: int = 500
    post_playback_silence_ms: int = 250


@dataclass(frozen=True, slots=True)
class LlmConfig:
    host: str = "http://127.0.0.1:11434"
    model: str = "qwen3.5:4b"

    context_length: int = 8_192
    temperature: float = 0.0
    maximum_output_tokens: int = 128

    keep_alive: str = "30m"
    request_timeout_seconds: float = 120.0


@dataclass(frozen=True, slots=True)
class SafetyConfig:
    test_directory: Path = Path("sandbox")
    operation_log_path: Path = Path(
        "logs/operations.jsonl"
    )

    maximum_directory_entries: int = 200
    maximum_search_results: int = 100
    maximum_scanned_entries: int = 10_000


@dataclass(frozen=True, slots=True)
class WindowConfig:
    inventory_backend: str = "win32"
    automation_backend: str = "uia"

    maximum_windows: int = 100


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    launch_verification_timeout_seconds: float = 5.0
    launch_verification_poll_interval_ms: int = 100


@dataclass(frozen=True, slots=True)
class InputConfig:
    maximum_text_characters: int = 2_000
    focus_settle_ms: int = 50
    send_chunk_utf16_units: int = 128


@dataclass(frozen=True, slots=True)
class ScreenConfig:
    default_monitor_index: int = 1
    screenshot_directory: Path = Path(
        "captures/screenshots"
    )
    diagnostic_directory: Path = Path(
        "captures/diagnostics"
    )


@dataclass(frozen=True, slots=True)
class VisionConfig:
    maximum_question_characters: int = 500
    maximum_response_tokens: int = 160


@dataclass(frozen=True, slots=True)
class UiAutomationConfig:
    maximum_controls: int = 150
    operation_timeout_seconds: float = 8.0