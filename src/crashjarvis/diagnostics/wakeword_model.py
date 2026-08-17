from pathlib import Path
from statistics import mean
from time import perf_counter

import numpy as np
from openwakeword.model import Model


MODEL_DIRECTORY = Path("models/wakeword")
MELSPECTROGRAM_MODEL = MODEL_DIRECTORY / "melspectrogram.onnx"
EMBEDDING_MODEL = MODEL_DIRECTORY / "embedding_model.onnx"
WAKE_WORD_MODEL = MODEL_DIRECTORY / "hey_jarvis_v0.1.onnx"

SAMPLE_RATE = 16_000
FRAME_DURATION_MS = 80
FRAME_SAMPLES = SAMPLE_RATE * FRAME_DURATION_MS // 1_000


def require_model(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"Required wake-word model was not found: {path.resolve()}"
        )


def main() -> None:
    required_models = (
        MELSPECTROGRAM_MODEL,
        EMBEDDING_MODEL,
        WAKE_WORD_MODEL,
    )

    for model_path in required_models:
        require_model(model_path)

    print("Loading Hey Jarvis ONNX model on CPU...")

    load_started = perf_counter()

    model = Model(
        wakeword_models=[str(WAKE_WORD_MODEL)],
        inference_framework="onnx",
        melspec_model_path=str(MELSPECTROGRAM_MODEL),
        embedding_model_path=str(EMBEDDING_MODEL),
        ncpu=1,
        device="cpu",
    )

    load_ms = (perf_counter() - load_started) * 1_000

    print(f"Model loaded in {load_ms:.1f} ms")
    print(f"Loaded classifiers: {', '.join(model.models.keys())}")
    print(f"Input frame: {FRAME_SAMPLES} samples / {FRAME_DURATION_MS} ms")

    silence = np.zeros(FRAME_SAMPLES, dtype=np.int16)
    inference_times_ms: list[float] = []
    prediction: dict[str, float] = {}

    for frame_index in range(25):
        inference_started = perf_counter()
        prediction = model.predict(silence)
        inference_ms = (perf_counter() - inference_started) * 1_000

        if frame_index >= 5:
            inference_times_ms.append(inference_ms)

    model_name, score = next(iter(prediction.items()))

    print(f"Average inference: {mean(inference_times_ms):.3f} ms")
    print(f"Silence score for {model_name}: {score:.6f}")
    print("Wake-word model test completed successfully.")


if __name__ == "__main__":
    main()