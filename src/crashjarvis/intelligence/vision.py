from dataclasses import dataclass
from time import perf_counter

from ollama import (
    Client,
    ResponseError,
)

from crashjarvis.config import (
    LlmConfig,
    ScreenConfig,
    VisionConfig,
)
from crashjarvis.desktop.screen_capture import (
    ScreenCaptureError,
    ScreenCaptureService,
)


class VisionAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VisionAnalysisResult:
    description: str
    monitor_index: int
    width: int
    height: int
    capture_ms: float
    wall_time_ms: float
    model_load_ms: float
    prompt_evaluation_ms: float
    generation_ms: float
    generated_tokens: int
    temporary_screenshot_deleted: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "success": True,
            "description": self.description,
            "monitor": {
                "index": self.monitor_index,
                "width": self.width,
                "height": self.height,
            },
            "timing": {
                "capture_ms": self.capture_ms,
                "wall_time_ms": self.wall_time_ms,
                "model_load_ms": self.model_load_ms,
                "prompt_evaluation_ms": (
                    self.prompt_evaluation_ms
                ),
                "generation_ms": self.generation_ms,
            },
            "generated_tokens": self.generated_tokens,
            "temporary_screenshot_deleted": (
                self.temporary_screenshot_deleted
            ),
        }


class ScreenVisionAnalyzer:
    def __init__(
        self,
        llm_config: LlmConfig,
        screen_config: ScreenConfig,
        vision_config: VisionConfig,
    ) -> None:
        self._llm_config = llm_config
        self._vision_config = vision_config

        self._capture_service = ScreenCaptureService(
            config=screen_config
        )
        self._client = Client(
            host=llm_config.host
        )

    def analyze(
        self,
        question: str,
    ) -> VisionAnalysisResult:
        question = self._validate_question(question)

        try:
            capture_result = (
                self._capture_service.capture_monitor()
            )
        except ScreenCaptureError as error:
            raise VisionAnalysisError(str(error)) from error

        screenshot_path = capture_result.output_path
        screenshot_deleted = False

        prompt = (
            "You are the visual observation component of a "
            "local Windows agent. Inspect only what is visibly "
            "present in this screenshot. Do not guess hidden "
            "content or unsupported details. Answer the specific "
            "question concisely in plain English.\n\n"
            f"Question: {question}"
        )

        request_started_at = perf_counter()

        try:
            response = self._client.chat(
                model=self._llm_config.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [screenshot_path],
                    },
                ],
                think=False,
                options={
                    "temperature": 0,
                    "num_predict": (
                        self._vision_config
                        .maximum_response_tokens
                    ),
                },
                keep_alive="30m",
            )

            wall_time_ms = (
                perf_counter() - request_started_at
            ) * 1000.0

            description = (
                response.message.content or ""
            ).strip()

            if not description:
                raise VisionAnalysisError(
                    "The vision model returned an empty response."
                )

            model_load_ms = self._nanoseconds_to_ms(
                response.load_duration
            )
            prompt_evaluation_ms = (
                self._nanoseconds_to_ms(
                    response.prompt_eval_duration
                )
            )
            generation_ms = self._nanoseconds_to_ms(
                response.eval_duration
            )
            generated_tokens = int(
                response.eval_count or 0
            )

        except ResponseError as error:
            raise VisionAnalysisError(
                f"Ollama vision request failed: {error}"
            ) from error

        finally:
            try:
                screenshot_path.unlink(missing_ok=True)
                screenshot_deleted = (
                    not screenshot_path.exists()
                )
            except OSError:
                screenshot_deleted = False

        return VisionAnalysisResult(
            description=description,
            monitor_index=capture_result.monitor.index,
            width=capture_result.monitor.width,
            height=capture_result.monitor.height,
            capture_ms=capture_result.capture_ms,
            wall_time_ms=wall_time_ms,
            model_load_ms=model_load_ms,
            prompt_evaluation_ms=prompt_evaluation_ms,
            generation_ms=generation_ms,
            generated_tokens=generated_tokens,
            temporary_screenshot_deleted=screenshot_deleted,
        )

    def _validate_question(self, question: str) -> str:
        if not isinstance(question, str):
            raise VisionAnalysisError(
                "Vision question must be a string."
            )

        question = question.strip()

        if not question:
            raise VisionAnalysisError(
                "Vision question cannot be empty."
            )

        if (
            len(question)
            > self._vision_config.maximum_question_characters
        ):
            raise VisionAnalysisError(
                "Vision question exceeds the maximum of "
                f"{self._vision_config.maximum_question_characters} "
                "characters."
            )

        return question

    @staticmethod
    def _nanoseconds_to_ms(
        value: int | None,
    ) -> float:
        return float(value or 0) / 1_000_000.0