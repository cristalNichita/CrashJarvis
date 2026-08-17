import json
import re
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from time import perf_counter

from crashjarvis.audio.capture import (
    AudioCapture,
    AudioCaptureError,
)
from crashjarvis.audio.resampler import StreamingAudioResampler
from crashjarvis.audio.vad import (
    SpeechEventKind,
    VoiceActivityDetector,
)
from crashjarvis.config import (
    ApplicationConfig,
    AsrConfig,
    AudioConfig,
    InputConfig,
    LlmConfig,
    SafetyConfig,
    ScreenConfig,
    TtsConfig,
    UiAutomationConfig,
    VadConfig,
    VisionConfig,
    WakeWordConfig,
    WindowConfig,
)
from crashjarvis.intelligence.agent import (
    AgentError,
    AgentResult,
    LocalToolCallingAgent,
)
from crashjarvis.intelligence.ollama_client import (
    LanguageModelError,
    OllamaLanguageModel,
)
from crashjarvis.speech.asr import (
    TranscriptionResult,
    WhisperTranscriber,
)
from crashjarvis.speech.segmenter import (
    SpeechSegment,
    SpeechSegmentCollector,
)
from crashjarvis.speech.wakeword import WakeWordDetector
from crashjarvis.speech.tts import (
    KokoroSpeechSynthesizer,
    SpeechSynthesisError,
    SpeechSynthesisResult,
)
from crashjarvis.tools.filesystem import (
    CreateDirectoryTool,
    FindFilesTool,
    ListDirectoryTool,
    MoveFileTool,
    RenamePathTool,
)
from crashjarvis.tools.registry import ToolRegistry

from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)

from crashjarvis.desktop.window_manager import (
    WindowManager,
)

from crashjarvis.tools.windows import (
    FocusWindowTool,
    ListWindowsTool,
    SetWindowStateTool,
)

from crashjarvis.desktop.application_catalog import (
    ApplicationCatalog,
)

from crashjarvis.tools.applications import (
    LaunchApplicationTool,
    SearchApplicationsTool,
)

from crashjarvis.desktop.input_controller import (
    TextInputController,
)
from crashjarvis.desktop.keyboard_controller import (
    KeyboardController,
)

from crashjarvis.tools.input import TypeTextTool
from crashjarvis.tools.keyboard import (
    PressHotkeyTool,
    PressKeyTool,
)

from crashjarvis.intelligence.vision import (
    ScreenVisionAnalyzer,
)
from crashjarvis.tools.screen import InspectScreenTool
from crashjarvis.desktop.screenshot_service import ScreenshotService
from crashjarvis.tools.screenshot import TakeScreenshotTool

from crashjarvis.desktop.ui_automation import (
    UiAutomationInspector,
)
from crashjarvis.tools.ui_automation import (
    ClickWindowControlTool,
    InspectWindowControlsTool,
)
from crashjarvis.runtime import (
    NullRuntimeEventSink,
    RuntimeControl,
    RuntimeEventSink,
)


MAIN_REVISION = "take-screenshot-tool-v1"


_WAKE_WORD_PREFIX = re.compile(
    r"^\s*(?:(?:hey|hi)\s+)?jarvis\b[\s,.:;!?-]*",
    flags=re.IGNORECASE,
)


class AssistantState(Enum):
    SLEEPING = "sleeping"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"


@dataclass(frozen=True, slots=True)
class PendingFinalTranscription:
    segment: SpeechSegment
    submitted_at: float


def clear_status_line() -> None:
    print("\r" + " " * 180 + "\r", end="")


def remove_wake_word(text: str) -> str:
    return _WAKE_WORD_PREFIX.sub(
        "",
        text,
        count=1,
    ).strip()


def submit_final_transcription(
    segment: SpeechSegment,
    executor: ThreadPoolExecutor,
    transcriber: WhisperTranscriber,
    pending: dict[
        Future[TranscriptionResult],
        PendingFinalTranscription,
    ],
) -> None:
    future = executor.submit(
        transcriber.transcribe,
        segment.audio,
    )

    pending[future] = PendingFinalTranscription(
        segment=segment,
        submitted_at=perf_counter(),
    )


def print_agent_result(
    result: AgentResult,
    pipeline_duration_ms: float,
) -> None:
    for index, tool_call in enumerate(
        result.tool_calls,
        start=1,
    ):
        arguments_text = json.dumps(
            tool_call.arguments,
            ensure_ascii=False,
        )

        success = tool_call.result.get(
            "success",
            False,
        )

        print(
            f"[TOOL {index}] {tool_call.name} "
            f"{arguments_text} | "
            f"{tool_call.duration_ms:.3f} ms"
        )

        if success:
            entry_count = tool_call.result.get(
                "entry_count"
            )
            control_count = tool_call.result.get(
                "control_count"
            )

            if control_count is not None:
                print(
                    f"[TOOL RESULT] success | "
                    f"controls: {control_count}"
                )
            elif entry_count is not None:
                print(
                    f"[TOOL RESULT] success | "
                    f"entries: {entry_count}"
                )
            else:
                print("[TOOL RESULT] success")

        else:
            error = tool_call.result.get(
                "error",
                "Unknown tool error",
            )
            print(f"[TOOL RESULT] failed | {error}")

    print(f'[JARVIS] "{result.text}"')

    print(
        f"Agent timing: "
        f"{pipeline_duration_ms:.1f} ms | "
        f"internal: {result.total_duration_ms:.1f} ms | "
        f"model: {result.model_duration_ms:.1f} ms | "
        f"tools: {result.tool_duration_ms:.3f} ms | "
        f"iterations: {result.iterations}"
    )


def main(
    event_sink: RuntimeEventSink | None = None,
    runtime_control: RuntimeControl | None = None,
) -> None:
    event_sink = event_sink or NullRuntimeEventSink()
    runtime_control = runtime_control or RuntimeControl()

    event_sink.state_changed(
        AssistantState.SLEEPING.value,
        "Loading local AI models…",
    )

    audio_config = AudioConfig()
    vad_config = VadConfig()
    wake_word_config = WakeWordConfig()
    asr_config = AsrConfig()
    tts_config = TtsConfig()
    llm_config = LlmConfig()
    safety_config = SafetyConfig()
    window_config = WindowConfig()
    application_config = ApplicationConfig()
    input_config = InputConfig()
    screen_config = ScreenConfig()
    vision_config = VisionConfig()
    ui_automation_config = UiAutomationConfig()

    capture = AudioCapture(audio_config)

    resampler = StreamingAudioResampler(
        source_sample_rate=audio_config.capture_sample_rate,
        target_sample_rate=audio_config.processing_sample_rate,
    )

    vad = VoiceActivityDetector(vad_config)

    collector = SpeechSegmentCollector(
        sample_rate=audio_config.processing_sample_rate,
        pre_roll_ms=asr_config.pre_roll_ms,
        maximum_utterance_seconds=(
            asr_config.maximum_utterance_seconds
        ),
    )

    print("Loading Hey Jarvis wake-word model on CPU...")
    event_sink.event_logged("Loading Hey Jarvis wake-word model")

    wake_word_detector = WakeWordDetector(
        model_directory=wake_word_config.model_directory,
        threshold=wake_word_config.threshold,
        cooldown_seconds=wake_word_config.cooldown_seconds,
    )

    print("Loading final Whisper model...")
    event_sink.event_logged("Loading final Whisper model on GPU")

    final_transcriber = WhisperTranscriber(
        asr_config,
        asr_config.final_model,
    )

    print("Loading partial Whisper model...")
    event_sink.event_logged("Loading partial Whisper model on GPU")

    partial_transcriber = WhisperTranscriber(
        asr_config,
        asr_config.partial_model,
    )

    print("Loading Kokoro voice on CPU...")
    event_sink.event_logged("Loading Kokoro voice on CPU")

    try:
        speech_synthesizer = KokoroSpeechSynthesizer(
            tts_config
        )
        tts_warmup_ms = speech_synthesizer.warm_up()

    except SpeechSynthesisError as error:
        print(f"TTS startup error: {error}")
        event_sink.error_reported(f"TTS startup error: {error}")
        return

    print(
        f"Kokoro ready in "
        f"{speech_synthesizer.load_time_ms:.1f} ms | "
        f"warm-up: {tts_warmup_ms:.1f} ms | "
        f"voice: {tts_config.voice}"
    )

    print("Connecting to local Qwen model...")
    event_sink.event_logged("Connecting to local Qwen model")

    language_model = OllamaLanguageModel(llm_config)

    print("Creating safe tool registry...")
    event_sink.event_logged("Creating safe tool registry")

    operation_journal = OperationJournal(
        safety_config.operation_log_path
    )

    list_directory_tool = ListDirectoryTool(
        allowed_root=safety_config.test_directory,
        maximum_entries=(
            safety_config.maximum_directory_entries
        ),
    )

    create_directory_tool = CreateDirectoryTool(
        allowed_root=safety_config.test_directory,
    )

    move_file_tool = MoveFileTool(
        allowed_root=safety_config.test_directory,
    )

    find_files_tool = FindFilesTool(
        allowed_root=safety_config.test_directory,
        maximum_results=(
            safety_config.maximum_search_results
        ),
        maximum_scanned_entries=(
            safety_config.maximum_scanned_entries
        ),
    )

    rename_path_tool = RenamePathTool(
        allowed_root=safety_config.test_directory,
    )

    window_manager = WindowManager(
        config=window_config
    )

    text_input_controller = TextInputController(
        config=input_config,
        window_manager=window_manager,
    )

    keyboard_controller = KeyboardController()

    print("Building local application catalog...")
    event_sink.event_logged("Building local application catalog")
    application_catalog = ApplicationCatalog()

    application_catalog_started_at = perf_counter()
    application_count = application_catalog.refresh()
    application_catalog_ms = (
        perf_counter() - application_catalog_started_at
    ) * 1000.0

    print(
        f"Application catalog ready: "
        f"{application_count} applications in "
        f"{application_catalog_ms:.1f} ms."
    )

    screen_vision_analyzer = ScreenVisionAnalyzer(
        llm_config=llm_config,
        screen_config=screen_config,
        vision_config=vision_config,
    )

    screenshot_service = ScreenshotService(
        screen_config.screenshot_directory,
    )

    ui_automation_inspector = UiAutomationInspector(
        config=ui_automation_config,
    )

    list_windows_tool = ListWindowsTool(
        window_manager=window_manager,
        backend_name=window_config.inventory_backend,
    )

    focus_window_tool = FocusWindowTool(
        window_manager=window_manager,
    )

    set_window_state_tool = SetWindowStateTool(
        window_manager=window_manager
    )

    type_text_tool = TypeTextTool(
        controller=text_input_controller
    )

    press_key_tool = PressKeyTool(
        controller=keyboard_controller
    )

    press_hotkey_tool = PressHotkeyTool(
        controller=keyboard_controller
    )

    inspect_screen_tool = InspectScreenTool(
        analyzer=screen_vision_analyzer
    )

    take_screenshot_tool = TakeScreenshotTool(
        service=screenshot_service,
        default_monitor_index=(
            screen_config.default_monitor_index
        ),
    )

    inspect_window_controls_tool = (
        InspectWindowControlsTool(
            inspector=ui_automation_inspector,
        )
    )

    click_window_control_tool = ClickWindowControlTool(
        inspector=ui_automation_inspector,
    )

    search_application_tool = SearchApplicationsTool(
        catalog=application_catalog
    )
    launch_application_tool = LaunchApplicationTool(
        catalog=application_catalog,
        window_manager=window_manager,
        config=application_config,
    )

    tool_registry = ToolRegistry(
        tools=[
            list_directory_tool,
            find_files_tool,
            create_directory_tool,
            move_file_tool,
            rename_path_tool,
            list_windows_tool,
            focus_window_tool,
            set_window_state_tool,
            type_text_tool,
            press_key_tool,
            press_hotkey_tool,
            inspect_window_controls_tool,
            click_window_control_tool,
            take_screenshot_tool,
            inspect_screen_tool,
            search_application_tool,
            launch_application_tool,
        ],
        journal=operation_journal,
    )

    agent = LocalToolCallingAgent(
        language_model=language_model,
        tool_registry=tool_registry,
        maximum_iterations=7,
    )

    print("Warming up Qwen...")
    event_sink.event_logged("Warming up Qwen")

    try:
        warm_up_result = language_model.complete(
            user_prompt=(
                "Reply with exactly the single word READY."
            ),
            system_prompt=(
                "Follow the instruction exactly. "
                "Do not explain your reasoning."
            ),
        )

    except LanguageModelError as error:
        print(f"LLM startup error: {error}")
        event_sink.error_reported(f"LLM startup error: {error}")
        print(
            "Make sure Ollama is running and "
            f"{llm_config.model} is installed."
        )
        ui_automation_inspector.close()
        return

    print(
        f"Qwen ready in "
        f"{warm_up_result.wall_time_ms:.1f} ms."
    )
    print(
        "Available tools: "
        + ", ".join(tool_registry.names)
    )
    print(
        f"Operation journal: "
        f"{operation_journal.log_path}"
    )
    print("All local AI models loaded.")
    print('Say "Hey Jarvis", followed by an English command.')
    print("Press Ctrl+C to stop.")

    final_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="crashjarvis-final-asr",
    )

    partial_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="crashjarvis-partial-asr",
    )

    agent_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="crashjarvis-agent",
    )

    tts_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="crashjarvis-tts",
    )

    pending_final: dict[
        Future[TranscriptionResult],
        PendingFinalTranscription,
    ] = {}

    partial_future: Future[TranscriptionResult] | None = None
    agent_future: Future[AgentResult] | None = None
    tts_future: Future[SpeechSynthesisResult] | None = None

    partial_session_id = 0
    active_session_id = 0
    last_partial_submitted_at = 0.0
    agent_submitted_at = 0.0
    speaking_cooldown_until: float | None = None

    state = AssistantState.SLEEPING

    def transition(
        new_state: AssistantState,
        detail: str = "",
    ) -> None:
        nonlocal state
        state = new_state
        event_sink.state_changed(new_state.value, detail)

    transition(
        AssistantState.SLEEPING,
        "Local models ready. Waiting for wake word.",
    )
    event_sink.event_logged("All local AI models loaded")
    command_deadline: float | None = None
    queued_segment: SpeechSegment | None = None

    last_wake_score = 0.0
    wake_activations = 0

    try:
        with capture:
            print(f"Input: {capture.device_description}")
            event_sink.event_logged(
                f"Microphone ready: {capture.device_description}"
            )

            while True:
                captured_block = capture.read()

                if runtime_control.stop_requested.is_set():
                    clear_status_line()
                    print("Stop requested from the user interface.")
                    event_sink.event_logged("Runtime stop acknowledged")
                    break

                if (
                    runtime_control.microphone_muted.is_set()
                    and state in {
                        AssistantState.SLEEPING,
                        AssistantState.LISTENING,
                    }
                ):
                    if state is AssistantState.LISTENING:
                        transition(
                            AssistantState.SLEEPING,
                            "Microphone muted",
                        )
                        command_deadline = None
                        queued_segment = None
                        wake_word_detector.reset()
                    continue

                if state is AssistantState.SPEAKING:
                    now = perf_counter()

                    if (
                        tts_future is not None
                        and tts_future.done()
                    ):
                        clear_status_line()

                        try:
                            voice_result = tts_future.result()

                            print(
                                f"[VOICE] generation: "
                                f"{voice_result.generation_ms:.1f} ms | "
                                f"response start: "
                                f"{voice_result.response_to_playback_ms:.1f} ms | "
                                f"audio: "
                                f"{voice_result.audio_duration_seconds:.2f} s | "
                                f"total: "
                                f"{voice_result.total_duration_ms:.1f} ms"
                            )
                            event_sink.latency_measured(
                                "voice",
                                voice_result.response_to_playback_ms,
                            )
                            event_sink.event_logged(
                                "Voice response completed"
                            )

                        except SpeechSynthesisError as error:
                            print(f"[TTS ERROR] {error}")
                            event_sink.error_reported(
                                f"TTS error: {error}"
                            )

                        except Exception as error:
                            print(
                                "[UNEXPECTED TTS ERROR] "
                                f"{error}"
                            )
                            event_sink.error_reported(
                                f"Unexpected TTS error: {error}"
                            )

                        tts_future = None
                        speaking_cooldown_until = (
                            perf_counter()
                            + tts_config.post_playback_silence_ms
                            / 1000.0
                        )

                    if (
                        tts_future is None
                        and speaking_cooldown_until is not None
                        and now >= speaking_cooldown_until
                    ):
                        transition(
                            AssistantState.SLEEPING,
                            "Waiting for wake word",
                        )
                        speaking_cooldown_until = None
                        wake_word_detector.reset()

                        clear_status_line()
                        print(
                            'Task completed. Say "Hey Jarvis" '
                            "for the next command."
                        )

                    print(
                        "\r"
                        f"State: {state.value.upper():<12} | "
                        f"wake: {last_wake_score:.3f} | "
                        "VAD: 0.000 | "
                        "partial: 0 | final: 0 | agent: 0 | "
                        f"tts: {1 if tts_future else 0} | "
                        f"activations: {wake_activations}",
                        end="",
                        flush=True,
                    )
                    continue

                processing_block = resampler.process(
                    captured_block
                )

                if state is AssistantState.SLEEPING:
                    wake_predictions = (
                        wake_word_detector.process(
                            processing_block
                        )
                    )

                    for prediction in wake_predictions:
                        last_wake_score = prediction.score

                        if not prediction.detected:
                            continue

                        wake_activations += 1
                        transition(
                            AssistantState.LISTENING,
                            "Wake word detected. Listening for a command.",
                        )

                        command_deadline = (
                            perf_counter()
                            + wake_word_config.command_timeout_seconds
                        )

                        last_partial_submitted_at = 0.0

                        clear_status_line()

                        print(
                            f'[ACTIVATED] "Hey Jarvis" | '
                            f"score: {prediction.score:.3f} | "
                            f"inference: "
                            f"{prediction.inference_ms:.3f} ms"
                        )
                        event_sink.event_logged(
                            "Wake word detected "
                            f"({prediction.inference_ms:.1f} ms)"
                        )
                        print("Listening for a command...")
                        break

                events = vad.process(processing_block)

                for event in events:
                    if event.kind is SpeechEventKind.START:
                        active_session_id += 1
                        last_partial_submitted_at = 0.0

                        if state is AssistantState.LISTENING:
                            command_deadline = None

                segments = collector.process(
                    processing_block,
                    events,
                )

                for segment in segments:
                    if state in {
                        AssistantState.SLEEPING,
                        AssistantState.THINKING,
                    }:
                        continue

                    clear_status_line()

                    print(
                        f"[UTTERANCE] "
                        f"{segment.duration_seconds(asr_config.sample_rate):.2f} s | "
                        f"endpoint: "
                        f"{segment.endpoint_delay_ms:.1f} ms"
                    )

                    if state is AssistantState.LISTENING:
                        submit_final_transcription(
                            segment=segment,
                            executor=final_executor,
                            transcriber=final_transcriber,
                            pending=pending_final,
                        )

                        transition(
                            AssistantState.TRANSCRIBING,
                            "Preparing the final transcript",
                        )

                    elif (
                        state is AssistantState.TRANSCRIBING
                        and queued_segment is None
                    ):
                        queued_segment = segment

                if (
                    partial_future is not None
                    and partial_future.done()
                ):
                    try:
                        partial_result = (
                            partial_future.result()
                        )

                        if (
                            state is AssistantState.LISTENING
                            and collector.is_active
                            and partial_session_id
                            == active_session_id
                            and partial_result.text
                        ):
                            clear_status_line()

                            print(
                                f'[PARTIAL] "{partial_result.text}" '
                                f"({partial_result.inference_ms:.1f} ms)"
                            )
                            event_sink.partial_transcript(
                                partial_result.text
                            )

                    except Exception as error:
                        clear_status_line()
                        print(f"[PARTIAL ASR ERROR] {error}")

                    partial_future = None

                now = perf_counter()
                active_audio = (
                    collector.active_audio_snapshot()
                )

                if (
                    state is AssistantState.LISTENING
                    and active_audio is not None
                    and partial_future is None
                ):
                    active_duration_ms = (
                        active_audio.size
                        / asr_config.sample_rate
                        * 1000.0
                    )

                    interval_elapsed_ms = (
                        now - last_partial_submitted_at
                    ) * 1000.0

                    if (
                        active_duration_ms
                        >= asr_config.partial_minimum_audio_ms
                        and interval_elapsed_ms
                        >= asr_config.partial_interval_ms
                    ):
                        partial_future = (
                            partial_executor.submit(
                                partial_transcriber.transcribe,
                                active_audio,
                            )
                        )

                        partial_session_id = (
                            active_session_id
                        )
                        last_partial_submitted_at = now

                completed_futures = [
                    future
                    for future in pending_final
                    if future.done()
                ]

                for future in completed_futures:
                    metadata = pending_final.pop(future)
                    clear_status_line()

                    try:
                        result = future.result()

                    except Exception as error:
                        print(f"[FINAL ASR ERROR] {error}")

                        transition(
                            AssistantState.LISTENING,
                            "Recognition failed. Listening again.",
                        )
                        command_deadline = (
                            perf_counter()
                            + wake_word_config.command_timeout_seconds
                        )
                        continue

                    time_after_endpoint_ms = (
                        perf_counter()
                        - metadata.submitted_at
                    ) * 1000.0

                    estimated_after_speech_ms = (
                        metadata.segment.endpoint_delay_ms
                        + time_after_endpoint_ms
                    )

                    displayed_text = (
                        result.text
                        or "<no speech recognized>"
                    )

                    print(f'[FINAL] "{displayed_text}"')
                    event_sink.final_transcript(displayed_text)
                    event_sink.latency_measured(
                        "endpoint",
                        metadata.segment.endpoint_delay_ms,
                    )
                    event_sink.latency_measured(
                        "asr",
                        result.inference_ms,
                    )

                    print(
                        f"Audio: "
                        f"{result.audio_duration_seconds:.2f} s | "
                        f"ASR: {result.inference_ms:.1f} ms | "
                        f"estimated after speech: "
                        f"{estimated_after_speech_ms:.1f} ms"
                    )

                    command_text = remove_wake_word(
                        result.text
                    )

                    if command_text:
                        print(f'[COMMAND] "{command_text}"')
                        event_sink.command_received(command_text)
                        print("Agent is deciding what to do...")

                        queued_segment = None
                        command_deadline = None
                        transition(
                            AssistantState.THINKING,
                            "Planning and selecting safe tools",
                        )

                        agent_submitted_at = perf_counter()

                        agent_future = agent_executor.submit(
                            agent.run,
                            command_text,
                        )

                    else:
                        print(
                            "Wake phrase captured without a command."
                        )
                        print("Still listening for a command...")

                        transition(
                            AssistantState.LISTENING,
                            "Wake phrase received. Waiting for the command.",
                        )

                        command_deadline = (
                            perf_counter()
                            + wake_word_config.command_timeout_seconds
                        )

                        if queued_segment is not None:
                            segment = queued_segment
                            queued_segment = None

                            submit_final_transcription(
                                segment=segment,
                                executor=final_executor,
                                transcriber=final_transcriber,
                                pending=pending_final,
                            )

                            transition(
                                AssistantState.TRANSCRIBING,
                                "Preparing the final transcript",
                            )
                            command_deadline = None

                if (
                    agent_future is not None
                    and agent_future.done()
                ):
                    clear_status_line()

                    pipeline_duration_ms = (
                        perf_counter() - agent_submitted_at
                    ) * 1000.0

                    try:
                        agent_result = (
                            agent_future.result()
                        )

                        print_agent_result(
                            result=agent_result,
                            pipeline_duration_ms=(
                                pipeline_duration_ms
                            ),
                        )
                        event_sink.response_ready(agent_result.text)
                        event_sink.latency_measured(
                            "decision",
                            agent_result.model_duration_ms,
                        )
                        event_sink.latency_measured(
                            "action",
                            agent_result.tool_duration_ms,
                        )

                        for tool_call in agent_result.tool_calls:
                            success = tool_call.result.get(
                                "success",
                                False,
                            )
                            outcome = "success" if success else "failed"
                            event_sink.event_logged(
                                f"{tool_call.name} → {outcome} "
                                f"({tool_call.duration_ms:.1f} ms)"
                            )

                        print("Generating voice response...")
                        tts_future = tts_executor.submit(
                            speech_synthesizer.speak,
                            agent_result.text,
                        )
                        transition(
                            AssistantState.SPEAKING,
                            "Playing the local voice response",
                        )
                        speaking_cooldown_until = None

                    except (
                        AgentError,
                        LanguageModelError,
                    ) as error:
                        print(f"[AGENT ERROR] {error}")
                        event_sink.error_reported(
                            f"Agent error: {error}"
                        )

                    except Exception as error:
                        print(
                            "[UNEXPECTED AGENT ERROR] "
                            f"{error}"
                        )
                        event_sink.error_reported(
                            f"Unexpected agent error: {error}"
                        )

                    agent_future = None
                    command_deadline = None
                    queued_segment = None

                    if state is not AssistantState.SPEAKING:
                        transition(
                            AssistantState.SLEEPING,
                            "Waiting for wake word",
                        )
                        wake_word_detector.reset()

                        print(
                            'Task completed. Say "Hey Jarvis" '
                            "for the next command."
                        )

                if (
                    state is AssistantState.LISTENING
                    and command_deadline is not None
                    and not collector.is_active
                    and perf_counter() >= command_deadline
                ):
                    clear_status_line()

                    print(
                        "Command timeout. Returning to sleep."
                    )

                    transition(
                        AssistantState.SLEEPING,
                        "Command timed out. Waiting for wake word.",
                    )
                    command_deadline = None
                    queued_segment = None

                    wake_word_detector.reset()

                print(
                    "\r"
                    f"State: {state.value.upper():<12} | "
                    f"wake: {last_wake_score:.3f} | "
                    f"VAD: {vad.last_probability:.3f} | "
                    f"partial: "
                    f"{1 if partial_future else 0} | "
                    f"final: {len(pending_final)} | "
                    f"agent: {1 if agent_future else 0} | "
                    f"tts: {1 if tts_future else 0} | "
                    f"activations: {wake_activations}",
                    end="",
                    flush=True,
                )

    except KeyboardInterrupt:
        clear_status_line()
        print("CrashJarvis stopped.")

    except AudioCaptureError as error:
        clear_status_line()
        print(f"Audio error: {error}")
        event_sink.error_reported(f"Audio error: {error}")

    finally:
        event_sink.state_changed(
            AssistantState.SLEEPING.value,
            "Stopping local services…",
        )
        speech_synthesizer.stop()
        partial_executor.shutdown(wait=True)
        final_executor.shutdown(wait=True)
        agent_executor.shutdown(wait=True)
        tts_executor.shutdown(wait=True)
        ui_automation_inspector.close()

        print(
            f"Dropped audio blocks: "
            f"{capture.dropped_blocks}"
        )
        event_sink.event_logged(
            "Runtime stopped | dropped audio blocks: "
            f"{capture.dropped_blocks}"
        )


if __name__ == "__main__":
    main()