from pathlib import Path

from crashjarvis.audio.capture import (
    AudioCapture,
    AudioCaptureError,
)
from crashjarvis.audio.resampler import StreamingAudioResampler
from crashjarvis.config import AudioConfig
from crashjarvis.speech.wakeword import WakeWordDetector


def clear_status_line() -> None:
    print("\r" + " " * 110 + "\r", end="")


def main() -> None:
    audio_config = AudioConfig()

    capture = AudioCapture(audio_config)
    resampler = StreamingAudioResampler(
        source_sample_rate=audio_config.capture_sample_rate,
        target_sample_rate=audio_config.processing_sample_rate,
    )

    print("Loading Hey Jarvis wake-word model on CPU...")

    detector = WakeWordDetector(
        model_directory=Path("models/wakeword"),
        threshold=0.5,
        cooldown_seconds=1.5,
    )

    print(f"Wake-word model loaded: {detector.model_name}")
    print(f"Activation threshold: {detector.threshold:.2f}")
    print('Say "Hey Jarvis".')
    print("Press Ctrl+C to stop.")

    peak_score = 0.0
    activation_count = 0
    last_score = 0.0
    last_inference_ms = 0.0

    try:
        with capture:
            print(f"Input: {capture.device_description}")

            while True:
                captured_block = capture.read()
                processing_block = resampler.process(captured_block)

                predictions = detector.process(processing_block)

                for prediction in predictions:
                    last_score = prediction.score
                    last_inference_ms = prediction.inference_ms
                    peak_score = max(peak_score, prediction.score)

                    if prediction.detected:
                        activation_count += 1
                        clear_status_line()
                        print(
                            f'[WAKE WORD] "Hey Jarvis" detected | '
                            f"score: {prediction.score:.3f} | "
                            f"inference: {prediction.inference_ms:.3f} ms"
                        )

                print(
                    "\r"
                    f"Score: {last_score:.3f} | "
                    f"peak: {peak_score:.3f} | "
                    f"inference: {last_inference_ms:.3f} ms | "
                    f"activations: {activation_count}",
                    end="",
                    flush=True,
                )

    except KeyboardInterrupt:
        clear_status_line()
        print("Wake-word test stopped.")

    except AudioCaptureError as error:
        clear_status_line()
        print(f"Audio error: {error}")

    finally:
        print(f"Peak score: {peak_score:.3f}")
        print(f"Successful activations: {activation_count}")
        print(f"Dropped audio blocks: {capture.dropped_blocks}")


if __name__ == "__main__":
    main()