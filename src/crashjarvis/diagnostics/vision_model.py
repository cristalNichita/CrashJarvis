from time import perf_counter

from ollama import (
    Client,
    ResponseError,
)

from crashjarvis.config import (
    LlmConfig,
    ScreenConfig,
)
from crashjarvis.desktop.screen_capture import (
    ScreenCaptureError,
    ScreenCaptureService,
)


def nanoseconds_to_ms(
    nanoseconds: int | None,
) -> float:
    return float(nanoseconds or 0) / 1_000_000.0


def main() -> None:
    llm_config = LlmConfig()
    screen_config = ScreenConfig()

    print("CrashJarvis local vision test")
    print(f"Model: {llm_config.model}")
    print(f"Host: {llm_config.host}")
    print("Network use: none")
    print()

    client = Client(
        host=llm_config.host
    )

    print("Checking model capabilities...")

    try:
        model_information = client.show(
            llm_config.model
        )
    except ResponseError as error:
        print(f"[OLLAMA ERROR] {error}")
        return

    capabilities = list(
        model_information.capabilities or []
    )

    print(
        "Capabilities: "
        + ", ".join(capabilities)
    )

    if "vision" not in capabilities:
        print(
            "[VISION ERROR] The installed model does not "
            "report vision capability."
        )
        return

    print("Capturing the configured monitor...")

    capture_service = ScreenCaptureService(
        config=screen_config
    )

    try:
        capture_result = (
            capture_service.capture_monitor()
        )
    except ScreenCaptureError as error:
        print(f"[SCREEN ERROR] {error}")
        return

    print(
        f"Screenshot: {capture_result.output_path}"
    )
    print(
        f"Resolution: "
        f"{capture_result.monitor.width}x"
        f"{capture_result.monitor.height}"
    )
    print(
        f"Capture: {capture_result.capture_ms:.1f} ms"
    )
    print(
        f"File size: "
        f"{capture_result.file_size_bytes} bytes"
    )
    print()
    print("Sending the screenshot to local Qwen...")

    prompt = (
        "Analyze this Windows desktop screenshot. "
        "Briefly describe the visible applications, the major "
        "interface regions, and any clearly readable important "
        "text. Do not guess content that is hidden, too small, "
        "blurred, or not visible. Respond in concise English."
    )

    request_started_at = perf_counter()

    try:
        response = client.chat(
            model=llm_config.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [
                        capture_result.output_path
                    ],
                },
            ],
            think=False,
            options={
                "temperature": 0,
                "num_predict": 256,
            },
            keep_alive="30m",
        )
    except ResponseError as error:
        print(f"[VISION ERROR] {error}")
        return

    wall_time_ms = (
        perf_counter() - request_started_at
    ) * 1000.0

    text = response.message.content.strip()

    print()
    print("[VISION RESPONSE]")
    print(text or "<empty response>")
    print()
    print(f"Wall time: {wall_time_ms:.1f} ms")
    print(
        f"Model load: "
        f"{nanoseconds_to_ms(response.load_duration):.1f} ms"
    )
    print(
        f"Prompt evaluation: "
        f"{nanoseconds_to_ms(response.prompt_eval_duration):.1f} ms"
    )
    print(
        f"Generation: "
        f"{nanoseconds_to_ms(response.eval_duration):.1f} ms"
    )
    print(
        f"Generated tokens: "
        f"{response.eval_count or 0}"
    )
    print()
    print(
        "[VERIFIED] The installed Qwen model accepted "
        "and analyzed a local screenshot."
    )


if __name__ == "__main__":
    main()