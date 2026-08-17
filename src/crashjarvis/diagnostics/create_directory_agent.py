import json

from crashjarvis.config import (
    LlmConfig,
    SafetyConfig,
)
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
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
    CreateDirectoryTool,
    ListDirectoryTool,
)
from crashjarvis.tools.registry import ToolRegistry


def main() -> None:
    llm_config = LlmConfig()
    safety_config = SafetyConfig()

    language_model = OllamaLanguageModel(
        llm_config
    )

    journal = OperationJournal(
        safety_config.operation_log_path
    )

    registry = ToolRegistry(
        tools=[
            ListDirectoryTool(
                allowed_root=(
                    safety_config.test_directory
                ),
                maximum_entries=(
                    safety_config
                    .maximum_directory_entries
                ),
            ),
            CreateDirectoryTool(
                allowed_root=(
                    safety_config.test_directory
                ),
            ),
        ],
        journal=journal,
    )

    agent = LocalToolCallingAgent(
        language_model=language_model,
        tool_registry=registry,
        maximum_iterations=6,
    )

    command = (
        "Create a folder called AgentTestFolder inside "
        "my Downloads directory and verify that it exists."
    )

    print("CrashJarvis modifying agent test")
    print(f"Model: {llm_config.model}")
    print(
        f"Allowed root: "
        f"{safety_config.test_directory.resolve()}"
    )
    print(
        f"Available tools: "
        f"{', '.join(registry.names)}"
    )
    print(f"Journal: {journal.log_path}")
    print()
    print(f'[USER] "{command}"')
    print()

    try:
        result = agent.run(command)

    except (
        AgentError,
        LanguageModelError,
    ) as error:
        print(f"[AGENT ERROR] {error}")
        return

    for index, tool_call in enumerate(
        result.tool_calls,
        start=1,
    ):
        print(
            f"[TOOL CALL {index}] "
            f"{tool_call.name}"
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
            f"Duration: "
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

    creation_calls = [
        tool_call
        for tool_call in result.tool_calls
        if tool_call.name == "create_directory"
    ]

    verification_calls = [
        tool_call
        for tool_call in result.tool_calls
        if (
            tool_call.name == "list_directory"
            and tool_call.arguments.get("path")
            == "Downloads"
        )
    ]

    if not creation_calls:
        raise RuntimeError(
            "Test failed: the agent did not call "
            "create_directory."
        )

    if not verification_calls:
        raise RuntimeError(
            "Test failed: the agent did not verify "
            "the Downloads directory."
        )

    print()
    print(
        "[VERIFIED] The agent created the directory "
        "and performed a separate verification."
    )
    print(
        "Modifying agent test completed successfully."
    )


if __name__ == "__main__":
    main()