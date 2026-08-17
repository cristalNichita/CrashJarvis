from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ollama import ChatResponse, Client, ResponseError

from crashjarvis.config import LlmConfig


class LanguageModelError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LanguageModelResponse:
    text: str

    wall_time_ms: float
    load_time_ms: float
    prompt_evaluation_ms: float
    generation_ms: float

    prompt_tokens: int
    generated_tokens: int
    tokens_per_second: float


class OllamaLanguageModel:
    def __init__(self, config: LlmConfig) -> None:
        self._config = config

        self._client = Client(
            host=config.host,
            timeout=config.request_timeout_seconds,
        )

    def chat(
        self,
        messages: list[Any],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        try:
            return self._client.chat(
                model=self._config.model,
                messages=messages,
                tools=tools,
                stream=False,
                think=False,
                keep_alive=self._config.keep_alive,
                options={
                    "num_ctx": self._config.context_length,
                    "temperature": self._config.temperature,
                    "num_predict": (
                        self._config.maximum_output_tokens
                    ),
                },
            )

        except ResponseError as error:
            status_code = getattr(
                error,
                "status_code",
                "unknown",
            )

            raise LanguageModelError(
                "Ollama rejected the request "
                f"(status {status_code}): {error}"
            ) from error

        except Exception as error:
            raise LanguageModelError(
                "Could not communicate with local Ollama: "
                f"{error}"
            ) from error

    def complete(
        self,
        user_prompt: str,
        system_prompt: str,
    ) -> LanguageModelResponse:
        started_at = perf_counter()

        response = self.chat(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ]
        )

        wall_time_ms = (
            perf_counter() - started_at
        ) * 1000.0

        load_time_ms = self._nanoseconds_to_milliseconds(
            response.load_duration
        )

        prompt_evaluation_ms = (
            self._nanoseconds_to_milliseconds(
                response.prompt_eval_duration
            )
        )

        generation_ms = self._nanoseconds_to_milliseconds(
            response.eval_duration
        )

        prompt_tokens = response.prompt_eval_count or 0
        generated_tokens = response.eval_count or 0

        generation_seconds = generation_ms / 1000.0

        tokens_per_second = (
            generated_tokens / generation_seconds
            if generation_seconds > 0.0
            else 0.0
        )

        return LanguageModelResponse(
            text=(response.message.content or "").strip(),
            wall_time_ms=wall_time_ms,
            load_time_ms=load_time_ms,
            prompt_evaluation_ms=prompt_evaluation_ms,
            generation_ms=generation_ms,
            prompt_tokens=prompt_tokens,
            generated_tokens=generated_tokens,
            tokens_per_second=tokens_per_second,
        )

    @staticmethod
    def _nanoseconds_to_milliseconds(
        duration: int | None,
    ) -> float:
        if duration is None:
            return 0.0

        return duration / 1_000_000.0