import hashlib
import json
import os
import subprocess
import winreg
from dataclasses import dataclass
from pathlib import Path

import win32api
import win32con


@dataclass(frozen=True, slots=True)
class ApplicationInformation:
    application_id: str
    name: str
    source: str
    launch_target: str

    def to_dict(self) -> dict[str, str]:
        return {
            "application_id": self.application_id,
            "name": self.name,
            "source": self.source,
            "launch_target": self.launch_target,
        }


@dataclass(frozen=True, slots=True)
class ApplicationSearchResult:
    applications: list[ApplicationInformation]
    total_catalog_entries: int
    truncated: bool


class ApplicationCatalogError(RuntimeError):
    pass


class ApplicationLaunchError(RuntimeError):
    pass


class ApplicationCatalog:
    _SUPPORTED_SHORTCUT_SUFFIXES = {
        ".lnk",
        ".appref-ms",
    }

    def __init__(self) -> None:
        self._applications: dict[
            str,
            ApplicationInformation,
        ] = {}

    def refresh(self) -> int:
        discovered: list[ApplicationInformation] = []

        for start_menu_directory in self._start_menu_directories():
            discovered.extend(
                self._discover_start_menu_applications(
                    start_menu_directory
                )
            )

        discovered.extend(
            self._discover_registry_applications()
        )

        discovered.extend(
            self._discover_windows_start_applications()
        )

        source_priority = {
            "start_menu": 0,
            "windows_start_apps": 1,
            "registry_current_user": 2,
            "registry_local_machine": 3,
            "registry_local_machine_32bit": 4,
        }

        applications_by_name: dict[
            str,
            ApplicationInformation,
        ] = {}

        for application in discovered:
            normalized_name = application.name.casefold()
            existing = applications_by_name.get(
                normalized_name
            )

            if existing is None:
                applications_by_name[normalized_name] = (
                    application
                )
                continue

            existing_priority = source_priority.get(
                existing.source,
                100,
            )
            new_priority = source_priority.get(
                application.source,
                100,
            )

            if new_priority < existing_priority:
                applications_by_name[normalized_name] = (
                    application
                )

        self._applications = {
            application.application_id: application
            for application in applications_by_name.values()
        }

        return len(self._applications)

    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> ApplicationSearchResult:
        normalized_query = query.strip().casefold()

        if not normalized_query:
            raise ApplicationCatalogError(
                "Application search query cannot be empty."
            )

        if limit < 1 or limit > 100:
            raise ApplicationCatalogError(
                "Application search limit must be between 1 and 100."
            )

        query_tokens = normalized_query.split()
        compact_query = self._compact_text(
            normalized_query
        )
        ranked_matches: list[
            tuple[int, str, ApplicationInformation]
        ] = []

        for application in self._applications.values():
            normalized_name = application.name.casefold()

            if normalized_name == normalized_query:
                rank = 0
            elif normalized_name.startswith(normalized_query):
                rank = 1
            elif normalized_query in normalized_name:
                rank = 2
            elif all(
                token in normalized_name
                for token in query_tokens
            ):
                rank = 3
            elif (
                len(compact_query) >= 4
                and self._is_ordered_subsequence(
                    compact_query,
                    self._compact_text(normalized_name),
                )
            ):
                rank = 4
            else:
                continue

            ranked_matches.append(
                (
                    rank,
                    normalized_name,
                    application,
                )
            )

        ranked_matches.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2].application_id,
            )
        )

        matches = [
            item[2]
            for item in ranked_matches
        ]

        return ApplicationSearchResult(
            applications=matches[:limit],
            total_catalog_entries=len(self._applications),
            truncated=len(matches) > limit,
        )

    def get(
        self,
        application_id: str,
    ) -> ApplicationInformation:
        try:
            return self._applications[application_id]
        except KeyError as error:
            raise ApplicationCatalogError(
                "Unknown application ID. Refresh and search the "
                "application catalog before launching an application."
            ) from error

    def launch(
        self,
        application_id: str,
    ) -> dict[str, object]:
        application = self.get(application_id)

        try:
            shell_result = win32api.ShellExecute(
                0,
                "open",
                application.launch_target,
                None,
                None,
                win32con.SW_SHOWNORMAL,
            )
        except Exception as error:
            raise ApplicationLaunchError(
                f"Windows could not launch "
                f"{application.name!r}: {error}"
            ) from error

        result_code = int(shell_result)

        if result_code <= 32:
            raise ApplicationLaunchError(
                f"Windows rejected the launch request for "
                f"{application.name!r}. "
                f"ShellExecute code: {result_code}."
            )

        return {
            "success": True,
            "launch_request_accepted": True,
            "application": application.to_dict(),
            "shell_execute_code": result_code,
        }

    def _start_menu_directories(self) -> list[Path]:
        directories: list[Path] = []

        app_data = os.environ.get("APPDATA")

        if app_data:
            directories.append(
                Path(app_data)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
            )

        program_data = os.environ.get("PROGRAMDATA")

        if program_data:
            directories.append(
                Path(program_data)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
            )

        return directories

    def _discover_start_menu_applications(
        self,
        directory: Path,
    ) -> list[ApplicationInformation]:
        if not directory.is_dir():
            return []

        applications: list[ApplicationInformation] = []

        try:
            entries = directory.rglob("*")

            for entry in entries:
                if not entry.is_file():
                    continue

                if (
                    entry.suffix.casefold()
                    not in self._SUPPORTED_SHORTCUT_SUFFIXES
                ):
                    continue

                name = entry.stem.strip()

                if not name:
                    continue

                launch_target = str(entry.resolve())

                applications.append(
                    self._create_application(
                        name=name,
                        source="start_menu",
                        launch_target=launch_target,
                    )
                )

        except OSError:
            return applications

        return applications

    def _discover_registry_applications(
        self,
    ) -> list[ApplicationInformation]:
        locations = [
            (
                winreg.HKEY_CURRENT_USER,
                (
                    r"Software\Microsoft\Windows"
                    r"\CurrentVersion\App Paths"
                ),
                "registry_current_user",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                (
                    r"Software\Microsoft\Windows"
                    r"\CurrentVersion\App Paths"
                ),
                "registry_local_machine",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                (
                    r"Software\WOW6432Node\Microsoft\Windows"
                    r"\CurrentVersion\App Paths"
                ),
                "registry_local_machine_32bit",
            ),
        ]

        applications: list[ApplicationInformation] = []

        for root, registry_path, source in locations:
            applications.extend(
                self._read_registry_location(
                    root=root,
                    registry_path=registry_path,
                    source=source,
                )
            )

        return applications

    def _read_registry_location(
        self,
        root: int,
        registry_path: str,
        source: str,
    ) -> list[ApplicationInformation]:
        applications: list[ApplicationInformation] = []

        try:
            parent_key = winreg.OpenKey(
                root,
                registry_path,
                0,
                winreg.KEY_READ,
            )
        except OSError:
            return applications

        with parent_key:
            index = 0

            while True:
                try:
                    subkey_name = winreg.EnumKey(
                        parent_key,
                        index,
                    )
                except OSError:
                    break

                index += 1

                try:
                    with winreg.OpenKey(
                        parent_key,
                        subkey_name,
                        0,
                        winreg.KEY_READ,
                    ) as application_key:
                        raw_target, _ = winreg.QueryValueEx(
                            application_key,
                            None,
                        )
                except OSError:
                    continue

                if not isinstance(raw_target, str):
                    continue

                launch_target = os.path.expandvars(
                    raw_target.strip().strip('"')
                )

                if not launch_target:
                    continue

                name = Path(subkey_name).stem.strip()

                if not name:
                    continue

                applications.append(
                    self._create_application(
                        name=name,
                        source=source,
                        launch_target=launch_target,
                    )
                )

        return applications

    def _discover_windows_start_applications(
        self,
    ) -> list[ApplicationInformation]:
        powershell_script = (
            "[Console]::OutputEncoding = "
            "[System.Text.UTF8Encoding]::new(); "
            "Get-StartApps | "
            "Select-Object Name, AppID | "
            "ConvertTo-Json -Compress"
        )

        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )

        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    powershell_script,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8-sig",
                errors="replace",
                timeout=10,
                check=False,
                creationflags=creation_flags,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ):
            return []

        if completed.returncode != 0:
            return []

        raw_output = completed.stdout.strip()

        if not raw_output:
            return []

        try:
            decoded = json.loads(raw_output)
        except json.JSONDecodeError:
            return []

        if isinstance(decoded, dict):
            entries = [decoded]
        elif isinstance(decoded, list):
            entries = decoded
        else:
            return []

        applications: list[ApplicationInformation] = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            name = entry.get("Name")
            app_id = entry.get("AppID")

            if not isinstance(name, str):
                continue

            if not isinstance(app_id, str):
                continue

            name = name.strip()
            app_id = app_id.strip()

            if not name or not app_id:
                continue

            applications.append(
                self._create_application(
                    name=name,
                    source="windows_start_apps",
                    launch_target=(
                        f"shell:AppsFolder\\{app_id}"
                    ),
                )
            )

        return applications

    @staticmethod
    def _compact_text(value: str) -> str:
        return "".join(
            character
            for character in value.casefold()
            if character.isalnum()
        )

    @staticmethod
    def _is_ordered_subsequence(
        query: str,
        candidate: str,
    ) -> bool:
        candidate_iterator = iter(candidate)

        return all(
            character in candidate_iterator
            for character in query
        )

    def _create_application(
        self,
        name: str,
        source: str,
        launch_target: str,
    ) -> ApplicationInformation:
        identifier_source = (
            f"{source}\0"
            f"{os.path.normcase(launch_target)}"
        )

        application_id = hashlib.sha256(
            identifier_source.encode("utf-8")
        ).hexdigest()[:16]

        return ApplicationInformation(
            application_id=application_id,
            name=name,
            source=source,
            launch_target=launch_target,
        )