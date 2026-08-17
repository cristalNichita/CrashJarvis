from crashjarvis.config import LlmConfig
from crashjarvis.intelligence.ollama_client import (
    LanguageModelError,
    LanguageModelResponse,
    OllamaLanguageModel,
)


def print_result(
    request_number: int,
    result: LanguageModelResponse,
) -> None:
    print()
    print(f"Request {request_number}:")
    print(f'Response: "{result.text}"')
    print(f"Wall time: {result.wall_time_ms:.1f} ms")
    print(f"Model load: {result.load_time_ms:.1f} ms")
    print(
        "Prompt evaluation: "
        f"{result.prompt_evaluation_ms:.1f} ms "
        f"({result.prompt_tokens} tokens)"
    )
    print(
        "Generation: "
        f"{result.generation_ms:.1f} ms "
        f"({result.generated_tokens} tokens)"
    )
    print(
        "Generation speed: "
        f"{result.tokens_per_second:.1f} tokens/s"
    )


def main() -> None:
    config = LlmConfig()
    model = OllamaLanguageModel(config)

    system_prompt = (
        "You are CrashJarvis, a local Windows assistant. "
        "Follow the user's instruction precisely. "
        "Do not explain your reasoning."
    )
    user_prompt = (
        "Reply with exactly the single word READY."
    )

    print("CrashJarvis local LLM test")
    print(f"Host: {config.host}")
    print(f"Model: {config.model}")
    print(f"Context: {config.context_length}")
    print("Thinking: disabled")
    print()

    try:
        for request_number in range(1, 3):
            print(f"Running request {request_number}...")

            result = model.complete(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
            )

            print_result(request_number, result)

    except LanguageModelError as error:
        print()
        print(f"LLM error: {error}")
        print(
            "Make sure Ollama is running and "
            f"{config.model} is installed."
        )
        return

    print()
    print("Local LLM test completed successfully.")


if __name__ == "__main__":
    main()