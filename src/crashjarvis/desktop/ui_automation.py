import hashlib
import re
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError,
)
from dataclasses import dataclass
from threading import get_ident
from typing import Any

import win32gui

from crashjarvis.config import UiAutomationConfig


UI_AUTOMATION_REVISION = "click-control-v1"


class UiAutomationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class UiControlClickResult:
    window_handle: int
    window_title: str
    control_ref: str
    name: str
    control_type: str
    click_dispatched: bool
    focused_after_click: bool | None
    worker_thread_id: int

    def to_dict(self) -> dict[str, object]:
        return {
            "success": True,
            "window_handle": self.window_handle,
            "window_title": self.window_title,
            "control_ref": self.control_ref,
            "name": self.name,
            "control_type": self.control_type,
            "click_dispatched": self.click_dispatched,
            "focused_after_click": self.focused_after_click,
            "worker_thread_id": self.worker_thread_id,
        }


@dataclass(frozen=True, slots=True)
class _CachedUiControl:
    window_handle: int
    control_ref: str
    name: str
    control_type: str
    runtime_id: object
    wrapper: Any


@dataclass(frozen=True, slots=True)
class UiControlInformation:
    control_ref: str
    name: str
    control_type: str
    automation_id: str
    class_name: str
    enabled: bool
    visible: bool
    bounds: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "control_ref": self.control_ref,
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "class_name": self.class_name,
            "enabled": self.enabled,
            "visible": self.visible,
            "bounds": self.bounds,
        }


@dataclass(frozen=True, slots=True)
class UiWindowInspection:
    window_handle: int
    window_title: str
    controls: list[UiControlInformation]
    total_controls_seen: int
    matching_controls_seen: int
    truncated: bool
    worker_thread_id: int

    def to_dict(self) -> dict[str, object]:
        return {
            "success": True,
            "window_handle": self.window_handle,
            "window_title": self.window_title,
            "control_count": len(self.controls),
            "total_controls_seen": self.total_controls_seen,
            "matching_controls_seen": (
                self.matching_controls_seen
            ),
            "truncated": self.truncated,
            "worker_thread_id": self.worker_thread_id,
            "controls": [
                control.to_dict()
                for control in self.controls
            ],
        }


class UiAutomationInspector:
    _USEFUL_CONTROL_TYPES = {
        "Button",
        "CheckBox",
        "ComboBox",
        "DataItem",
        "Edit",
        "Hyperlink",
        "List",
        "ListItem",
        "Menu",
        "MenuBar",
        "MenuItem",
        "RadioButton",
        "ScrollBar",
        "Slider",
        "Spinner",
        "Tab",
        "TabItem",
        "Text",
        "ToolBar",
        "Tree",
        "TreeItem",
    }

    def __init__(
        self,
        config: UiAutomationConfig,
    ) -> None:
        self._config = config
        self._desktop: Any | None = None
        self._worker_thread_id: int | None = None
        self._cached_controls: dict[str, _CachedUiControl] = {}

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="crashjarvis-uia",
        )

        initialization = self._executor.submit(
            self._initialize_worker
        )

        try:
            initialization.result(
                timeout=config.operation_timeout_seconds
            )
        except TimeoutError as error:
            self._executor.shutdown(
                wait=False,
                cancel_futures=True,
            )
            raise UiAutomationError(
                "UI Automation worker initialization timed out."
            ) from error
        except Exception as error:
            self._executor.shutdown(
                wait=False,
                cancel_futures=True,
            )
            raise UiAutomationError(
                f"Could not initialize UI Automation: {error}"
            ) from error

    def inspect_window(
        self,
        handle: int,
        query: str = "",
        control_types: list[str] | None = None,
        visible_only: bool = True,
        limit: int | None = None,
    ) -> UiWindowInspection:
        if isinstance(handle, bool) or not isinstance(handle, int):
            raise UiAutomationError(
                "Window handle must be an integer."
            )

        if not win32gui.IsWindow(handle):
            raise UiAutomationError(
                f"Window handle does not exist: {handle}"
            )

        if not isinstance(query, str):
            raise UiAutomationError(
                "Control query must be a string."
            )

        query = query.strip()

        if len(query) > 200:
            raise UiAutomationError(
                "Control query cannot exceed 200 characters."
            )

        selected_limit = (
            self._config.maximum_controls
            if limit is None
            else limit
        )

        if (
            isinstance(selected_limit, bool)
            or not isinstance(selected_limit, int)
            or selected_limit < 1
            or selected_limit
            > self._config.maximum_controls
        ):
            raise UiAutomationError(
                "Control limit must be between 1 and "
                f"{self._config.maximum_controls}."
            )

        normalized_types: tuple[str, ...] = ()

        if control_types:
            if not all(
                isinstance(value, str)
                for value in control_types
            ):
                raise UiAutomationError(
                    "Every control type must be a string."
                )

            normalized_types = tuple(
                value.strip().casefold()
                for value in control_types
                if value.strip()
            )

        query_terms = tuple(
            re.findall(
                r"\w+",
                query.casefold(),
                flags=re.UNICODE,
            )
        )

        future = self._executor.submit(
            self._inspect_window_on_worker,
            handle,
            query_terms,
            normalized_types,
            visible_only,
            selected_limit,
        )

        try:
            return future.result(
                timeout=self._config.operation_timeout_seconds
            )
        except TimeoutError as error:
            future.cancel()
            raise UiAutomationError(
                "UI Automation inspection exceeded "
                f"{self._config.operation_timeout_seconds:.1f} "
                "seconds."
            ) from error
        except Exception as error:
            raise UiAutomationError(
                f"UI Automation inspection failed: {error}"
            ) from error

    def click_control(
        self,
        handle: int,
        control_ref: str,
    ) -> UiControlClickResult:
        if isinstance(handle, bool) or not isinstance(handle, int):
            raise UiAutomationError(
                "Window handle must be an integer."
            )

        if not win32gui.IsWindow(handle):
            raise UiAutomationError(
                f"Window handle does not exist: {handle}"
            )

        if not isinstance(control_ref, str):
            raise UiAutomationError(
                "Control reference must be a string."
            )

        normalized_ref = control_ref.strip().casefold()

        if re.fullmatch(r"[0-9a-f]{16}", normalized_ref) is None:
            raise UiAutomationError(
                "Control reference must be the 16-character "
                "identifier returned by inspect_window_controls."
            )

        future = self._executor.submit(
            self._click_control_on_worker,
            handle,
            normalized_ref,
        )

        try:
            return future.result(
                timeout=self._config.operation_timeout_seconds
            )
        except TimeoutError as error:
            future.cancel()
            raise UiAutomationError(
                "UI Automation click exceeded "
                f"{self._config.operation_timeout_seconds:.1f} "
                "seconds."
            ) from error
        except UiAutomationError:
            raise
        except Exception as error:
            raise UiAutomationError(
                f"UI Automation click failed: {error}"
            ) from error

    def close(self) -> None:
        self._executor.shutdown(
            wait=True,
            cancel_futures=True,
        )

    def _initialize_worker(self) -> None:
        import pythoncom

        pythoncom.CoInitializeEx(
            pythoncom.COINIT_MULTITHREADED
        )

        from pywinauto import Desktop

        self._desktop = Desktop(
            backend="uia"
        )
        self._worker_thread_id = get_ident()

    def _inspect_window_on_worker(
        self,
        handle: int,
        query_terms: tuple[str, ...],
        normalized_types: tuple[str, ...],
        visible_only: bool,
        limit: int,
    ) -> UiWindowInspection:
        if self._desktop is None:
            raise UiAutomationError(
                "UI Automation worker is not initialized."
            )

        if get_ident() != self._worker_thread_id:
            raise UiAutomationError(
                "UI Automation operation entered the wrong thread."
            )

        window = self._desktop.window(
            handle=handle
        )

        wrapper = window.wrapper_object()
        descendants = wrapper.descendants()

        # A control_ref is intentionally valid only for the most
        # recent inspection. This prevents stale UI references from
        # being reused after the interface changes.
        self._cached_controls.clear()

        controls: list[UiControlInformation] = []
        matching_controls_seen = 0

        for index, control in enumerate(descendants):
            information = self._read_control(
                window_handle=handle,
                index=index,
                control=control,
                query_terms=query_terms,
                normalized_types=normalized_types,
                visible_only=visible_only,
            )

            if information is None:
                continue

            runtime_id = self._safe_value(
                lambda: control.element_info.runtime_id,
                default=None,
            )

            self._cached_controls[information.control_ref] = (
                _CachedUiControl(
                    window_handle=handle,
                    control_ref=information.control_ref,
                    name=information.name,
                    control_type=information.control_type,
                    runtime_id=runtime_id,
                    wrapper=control,
                )
            )

            matching_controls_seen += 1

            if len(controls) < limit:
                controls.append(information)

        return UiWindowInspection(
            window_handle=handle,
            window_title=win32gui.GetWindowText(handle),
            controls=controls,
            total_controls_seen=len(descendants),
            matching_controls_seen=(
                matching_controls_seen
            ),
            truncated=matching_controls_seen > len(controls),
            worker_thread_id=int(
                self._worker_thread_id or 0
            ),
        )

    def _click_control_on_worker(
        self,
        handle: int,
        control_ref: str,
    ) -> UiControlClickResult:
        if get_ident() != self._worker_thread_id:
            raise UiAutomationError(
                "UI Automation operation entered the wrong thread."
            )

        cached = self._cached_controls.get(control_ref)

        if cached is None:
            raise UiAutomationError(
                "Control reference is unknown or expired. Call "
                "inspect_window_controls immediately before clicking."
            )

        if cached.window_handle != handle:
            raise UiAutomationError(
                "Control reference belongs to a different window."
            )

        control = cached.wrapper
        element = control.element_info

        current_runtime_id = self._safe_value(
            lambda: element.runtime_id,
            default=None,
        )
        current_name = self._safe_string(
            lambda: element.name
        )
        current_control_type = self._safe_string(
            lambda: element.control_type
        )

        if (
            current_runtime_id != cached.runtime_id
            or current_name != cached.name
            or current_control_type != cached.control_type
        ):
            raise UiAutomationError(
                "The UI element changed after inspection. Inspect the "
                "window again before clicking."
            )

        if not self._safe_bool(lambda: control.is_enabled()):
            raise UiAutomationError(
                "The selected UI control is disabled."
            )

        if not self._safe_bool(lambda: control.is_visible()):
            raise UiAutomationError(
                "The selected UI control is no longer visible."
            )

        rectangle = self._safe_value(
            lambda: control.rectangle(),
            default=None,
        )

        if (
            rectangle is None
            or int(rectangle.right) <= int(rectangle.left)
            or int(rectangle.bottom) <= int(rectangle.top)
        ):
            raise UiAutomationError(
                "The selected UI control has no clickable bounds."
            )

        control.click_input(button="left")

        focused_after_click = self._safe_value(
            lambda: bool(control.has_keyboard_focus()),
            default=None,
        )

        return UiControlClickResult(
            window_handle=handle,
            window_title=win32gui.GetWindowText(handle),
            control_ref=control_ref,
            name=cached.name,
            control_type=cached.control_type,
            click_dispatched=True,
            focused_after_click=focused_after_click,
            worker_thread_id=int(
                self._worker_thread_id or 0
            ),
        )

    def _read_control(
        self,
        window_handle: int,
        index: int,
        control: Any,
        query_terms: tuple[str, ...],
        normalized_types: tuple[str, ...],
        visible_only: bool,
    ) -> UiControlInformation | None:
        element = control.element_info

        name = self._safe_string(
            lambda: element.name
        )
        control_type = self._safe_string(
            lambda: element.control_type
        )
        automation_id = self._safe_string(
            lambda: element.automation_id
        )
        class_name = self._safe_string(
            lambda: element.class_name
        )

        if (
            control_type
            not in self._USEFUL_CONTROL_TYPES
            and not name
        ):
            return None

        if (
            normalized_types
            and control_type.casefold()
            not in normalized_types
        ):
            return None

        if (
            query_terms
            and not self._matches_query(
                name=name,
                control_type=control_type,
                automation_id=automation_id,
                class_name=class_name,
                query_terms=query_terms,
            )
        ):
            return None

        enabled = self._safe_bool(
            lambda: control.is_enabled()
        )
        visible = self._safe_bool(
            lambda: control.is_visible()
        )

        if visible_only and not visible:
            return None

        rectangle = self._safe_value(
            lambda: control.rectangle(),
            default=None,
        )

        if rectangle is None:
            bounds = {
                "left": 0,
                "top": 0,
                "right": 0,
                "bottom": 0,
                "width": 0,
                "height": 0,
            }
        else:
            left = int(rectangle.left)
            top = int(rectangle.top)
            right = int(rectangle.right)
            bottom = int(rectangle.bottom)

            bounds = {
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
            }

        runtime_id = self._safe_value(
            lambda: element.runtime_id,
            default=None,
        )

        reference_source = (
            f"{window_handle}\0"
            f"{runtime_id!r}\0"
            f"{automation_id}\0"
            f"{control_type}\0"
            f"{name}\0"
            f"{index}"
        )

        control_ref = hashlib.sha256(
            reference_source.encode("utf-8")
        ).hexdigest()[:16]

        return UiControlInformation(
            control_ref=control_ref,
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            class_name=class_name,
            enabled=enabled,
            visible=visible,
            bounds=bounds,
        )

    @staticmethod
    def _matches_query(
        name: str,
        control_type: str,
        automation_id: str,
        class_name: str,
        query_terms: tuple[str, ...],
    ) -> bool:
        searchable_text = " ".join(
            [
                name,
                control_type,
                automation_id,
                class_name,
            ]
        ).casefold()

        return all(
            term in searchable_text
            for term in query_terms
        )

    @staticmethod
    def _safe_value(
        getter: Any,
        default: Any,
    ) -> Any:
        try:
            return getter()
        except Exception:
            return default

    def _safe_string(self, getter: Any) -> str:
        value = self._safe_value(
            getter,
            default="",
        )

        return str(value or "").strip()

    def _safe_bool(self, getter: Any) -> bool:
        value = self._safe_value(
            getter,
            default=False,
        )

        return bool(value)
