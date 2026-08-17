import json

from crashjarvis.config import (
    LlmConfig,
    SafetyConfig,
)
from crashjarvis.intelligence.agent import (
    AgentError,
    LocalToolCallingAgent,
)
from crashjarvis.intelligence.ollama_client import (
    LanguageModelError,
    OllamaLanguageModel,
)
from crashjarvis.tools.filesystem import (
    ListDirectoryTool,
)
from crashjarvis.tools.registry import ToolRegistry


def main() -> None:
    llm_config = LlmConfig()
    safety_config = SafetyConfig()

    language_model = OllamaLanguageModel(llm_config)

    list_directory_tool = ListDirectoryTool(
        allowed_root=safety_config.test_directory,
        maximum_entries=(
            safety_config.maximum_directory_entries
        ),
    )

    registry = ToolRegistry(
        tools=[
            list_directory_tool,
        ]
    )

    agent = LocalToolCallingAgent(
        language_model=language_model,
        tool_registry=registry,
        maximum_iterations=4,
    )

    command = (
        "List all files in my Downloads directory "
        "and tell me which video file was modified most recently."
    )

    print("CrashJarvis native tool-calling test")
    print(f"Model: {llm_config.model}")
    print(f"Allowed root: {safety_config.test_directory.resolve()}")
    print(f"Available tools: {', '.join(registry.names)}")
    print()
    print(f'[USER] "{command}"')
    print()

    try:
        result = agent.run(command)

    except (AgentError, LanguageModelError) as error:
        print(f"[AGENT ERROR] {error}")
        return

    if not result.tool_calls:
        print(
            "[TEST FAILED] The model answered without "
            "calling a tool."
        )
        return

    for index, tool_call in enumerate(
        result.tool_calls,
        start=1,
    ):
        print(
            f"[TOOL CALL {index}] {tool_call.name}"
        )
        print(
            "Arguments: "
            + json.dumps(
                tool_call.arguments,
                ensure_ascii=False,
            )
        )
        print(
            "Result: "
            + json.dumps(
                tool_call.result,
                indent=2,
                ensure_ascii=False,
            )
        )
        print(
            f"Tool duration: "
            f"{tool_call.duration_ms:.3f} ms"
        )
        print()

    print(f'[JARVIS] "{result.text}"')
    print()
    print(
        f"Iterations: {result.iterations} | "
        f"total: {result.total_duration_ms:.1f} ms | "
        f"model: {result.model_duration_ms:.1f} ms | "
        f"tools: {result.tool_duration_ms:.3f} ms"
    )
    print()
    print("Native tool-calling test completed successfully.")


if __name__ == "__main__":
    main()