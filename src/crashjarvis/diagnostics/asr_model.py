import argparse
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np

from crashjarvis.infrastructure.cuda_runtime import (
    configure_cuda_runtime,
)


MODEL_CACHE = Path("models/asr")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark a faster-whisper model on CUDA.",
    )
    parser.add_argument(
        "--model",
        default="large-v3-turbo",
        help="faster-whisper model name or Hugging Face ID.",
    )
    parser.add_argument(
        "--compute-type",
        default="float16",
        choices=(
            "float16",
            "int8_float16",
            "int8",
        ),
    )

    return parser.parse_args()


def get_gpu_memory_mb() -> int | None:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return None

    first_line = result.stdout.strip().splitlines()[0]

    try:
        return int(first_line)
    except ValueError:
        return None


def run_silence_inference(model: object) -> float:
    silence = np.zeros(16_000, dtype=np.float32)
    started_at = perf_counter()

    segments, _information = model.transcribe(
        silence,
        language="en",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=False,
        word_timestamps=False,
    )

    list(segments)

    return (perf_counter() - started_at) * 1000.0


def main() -> None:
    arguments = parse_arguments()

    print("Configuring CUDA runtime...")
    configure_cuda_runtime()

    from faster_whisper import WhisperModel

    MODEL_CACHE.mkdir(parents=True, exist_ok=True)

    memory_before = get_gpu_memory_mb()

    print(f"Model: {arguments.model}")
    print(f"Compute type: {arguments.compute_type}")
    print("The first run may download the model.")

    load_started_at = perf_counter()

    model = WhisperModel(
        arguments.model,
        device="cuda",
        compute_type=arguments.compute_type,
        download_root=str(MODEL_CACHE),
    )

    load_ms = (perf_counter() - load_started_at) * 1000.0
    memory_after = get_gpu_memory_mb()

    print(f"Model ready in: {load_ms:.1f} ms")

    if memory_before is not None and memory_after is not None:
        print(f"GPU memory before: {memory_before} MB")
        print(f"GPU memory after:  {memory_after} MB")
        print(
            f"Approximate model increase: "
            f"{memory_after - memory_before} MB"
        )

    print("Running warm-up inference...")
    warmup_ms = run_silence_inference(model)
    print(f"Warm-up inference: {warmup_ms:.1f} ms")

    print("Running second inference...")
    second_ms = run_silence_inference(model)
    print(f"Second inference: {second_ms:.1f} ms")

    print("Running third inference...")
    third_ms = run_silence_inference(model)
    print(f"Third inference: {third_ms:.1f} ms")

    print("ASR model test completed successfully.")


if __name__ == "__main__":
    main()