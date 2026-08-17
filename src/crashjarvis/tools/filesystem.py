import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class SandboxedFilesystemTool(AgentTool):
    def __init__(
        self,
        allowed_root: Path,
    ) -> None:
        self._allowed_root = allowed_root.resolve()

        self._allowed_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _resolve_safe_path(
        self,
        relative_path: str,
    ) -> Path:
        requested_path = Path(relative_path)

        if requested_path.is_absolute():
            raise ToolExecutionError(
                "Absolute paths are not allowed."
            )

        try:
            resolved_path = (
                self._allowed_root / requested_path
            ).resolve()
        except OSError as error:
            raise ToolExecutionError(
                f"Could not resolve path: {error}"
            ) from error

        if not resolved_path.is_relative_to(
            self._allowed_root
        ):
            raise ToolExecutionError(
                "Access outside the test directory is blocked."
            )

        return resolved_path


class ListDirectoryTool(SandboxedFilesystemTool):
    def __init__(
        self,
        allowed_root: Path,
        maximum_entries: int,
    ) -> None:
        super().__init__(allowed_root)

        self._maximum_entries = maximum_entries

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": (
                    "List files and subdirectories inside the "
                    "CrashJarvis test directory. Returns names, "
                    "types, sizes, and modification times. "
                    "The path must be relative to the test directory."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Relative directory path inside "
                                "the test directory. Use '.' for "
                                "the root."
                            ),
                        },
                    },
                    "required": ["path"],
                },
            },
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        relative_path = arguments.get("path")

        if not isinstance(relative_path, str):
            raise ToolExecutionError(
                "The 'path' argument must be a string."
            )

        target_directory = self._resolve_safe_path(
            relative_path
        )

        if not target_directory.exists():
            raise ToolExecutionError(
                f"Directory does not exist: {relative_path}"
            )

        if not target_directory.is_dir():
            raise ToolExecutionError(
                f"Path is not a directory: {relative_path}"
            )

        try:
            paths = sorted(
                target_directory.iterdir(),
                key=lambda path: (
                    not path.is_dir(),
                    path.name.casefold(),
                ),
            )
        except OSError as error:
            raise ToolExecutionError(
                f"Could not read directory: {error}"
            ) from error

        truncated = len(paths) > self._maximum_entries

        visible_paths = paths[
            :self._maximum_entries
        ]

        entries = [
            self._create_entry(path)
            for path in visible_paths
        ]

        return {
            "success": True,
            "root": str(self._allowed_root),
            "requested_path": relative_path,
            "resolved_path": str(target_directory),
            "entry_count": len(entries),
            "truncated": truncated,
            "entries": entries,
        }

    @staticmethod
    def _create_entry(
        path: Path,
    ) -> dict[str, Any]:
        try:
            statistics = path.stat()
        except OSError as error:
            raise ToolExecutionError(
                f"Could not inspect '{path.name}': {error}"
            ) from error

        modified_at = datetime.fromtimestamp(
            statistics.st_mtime,
            tz=timezone.utc,
        ).isoformat()

        return {
            "name": path.name,
            "type": (
                "directory"
                if path.is_dir()
                else "file"
            ),
            "size_bytes": (
                None
                if path.is_dir()
                else statistics.st_size
            ),
            "modified_at_utc": modified_at,
        }


class CreateDirectoryTool(SandboxedFilesystemTool):
    @property
    def name(self) -> str:
        return "create_directory"

    @property
    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": (
                    "Create exactly one new directory inside "
                    "an existing parent directory in the "
                    "controlled CrashJarvis test environment. "
                    "Always provide the parent directory and "
                    "the new directory name separately."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_directory": {
                            "type": "string",
                            "description": (
                                "Relative path of the existing "
                                "parent directory. For example, "
                                "use 'Downloads' when the user "
                                "wants a new folder inside Downloads."
                            ),
                        },
                        "directory_name": {
                            "type": "string",
                            "description": (
                                "Name of the single new directory, "
                                "without slashes. For example, "
                                "'FinalRecording'."
                            ),
                        },
                    },
                    "required": [
                        "parent_directory",
                        "directory_name",
                    ],
                },
            },
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        parent_directory = arguments.get(
            "parent_directory"
        )
        directory_name = arguments.get(
            "directory_name"
        )

        if not isinstance(parent_directory, str):
            raise ToolExecutionError(
                "The 'parent_directory' argument "
                "must be a string."
            )

        if not isinstance(directory_name, str):
            raise ToolExecutionError(
                "The 'directory_name' argument "
                "must be a string."
            )

        parent_directory = parent_directory.strip()
        directory_name = directory_name.strip()

        if not parent_directory:
            raise ToolExecutionError(
                "A parent directory is required."
            )

        if not directory_name:
            raise ToolExecutionError(
                "A directory name is required."
            )

        if directory_name in {".", ".."}:
            raise ToolExecutionError(
                "Invalid directory name."
            )

        if (
            "/" in directory_name
            or "\\" in directory_name
        ):
            raise ToolExecutionError(
                "The directory name must not "
                "contain path separators."
            )

        resolved_parent = self._resolve_safe_path(
            parent_directory
        )

        if not resolved_parent.exists():
            raise ToolExecutionError(
                "Parent directory does not exist."
            )

        if not resolved_parent.is_dir():
            raise ToolExecutionError(
                "The parent path is not a directory."
            )

        unresolved_target = (
            resolved_parent / directory_name
        )

        if unresolved_target.is_symlink():
            raise ToolExecutionError(
                "Symbolic-link targets are not allowed."
            )

        try:
            target_directory = (
                unresolved_target.resolve()
            )
        except OSError as error:
            raise ToolExecutionError(
                f"Could not resolve target path: {error}"
            ) from error

        if not target_directory.is_relative_to(
            self._allowed_root
        ):
            raise ToolExecutionError(
                "Target escaped the test directory."
            )

        if target_directory.exists():
            if target_directory.is_dir():
                return {
                    "success": True,
                    "created": False,
                    "parent_directory": (
                        parent_directory
                    ),
                    "directory_name": directory_name,
                    "path": str(
                        target_directory.relative_to(
                            self._allowed_root
                        )
                    ),
                    "message": (
                        "Directory already exists."
                    ),
                }

            raise ToolExecutionError(
                "A file already exists at the target path."
            )

        try:
            target_directory.mkdir()
        except OSError as error:
            raise ToolExecutionError(
                f"Could not create directory: {error}"
            ) from error

        if not target_directory.is_dir():
            raise ToolExecutionError(
                "Directory verification failed."
            )

        return {
            "success": True,
            "created": True,
            "parent_directory": parent_directory,
            "directory_name": directory_name,
            "path": str(
                target_directory.relative_to(
                    self._allowed_root
                )
            ),
            "message": "Directory created successfully.",
        }


class MoveFileTool(SandboxedFilesystemTool):
    @property
    def name(self) -> str:
        return "move_file"

    @property
    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": (
                    "Move one file from its current location "
                    "to an existing destination directory inside "
                    "the controlled CrashJarvis test directory. "
                    "The original file name is preserved. "
                    "Existing files are never overwritten."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_path": {
                            "type": "string",
                            "description": (
                                "Relative path of the file to move, "
                                "for example "
                                "'Downloads/video.mp4'."
                            ),
                        },
                        "destination_directory": {
                            "type": "string",
                            "description": (
                                "Relative path of the existing "
                                "destination directory, for example "
                                "'Downloads/Recording'."
                            ),
                        },
                    },
                    "required": [
                        "source_path",
                        "destination_directory",
                    ],
                },
            },
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        source_path = arguments.get("source_path")
        destination_directory = arguments.get(
            "destination_directory"
        )

        if not isinstance(source_path, str):
            raise ToolExecutionError(
                "The 'source_path' argument must be a string."
            )

        if not isinstance(destination_directory, str):
            raise ToolExecutionError(
                "The 'destination_directory' argument "
                "must be a string."
            )

        source_path = source_path.strip()
        destination_directory = (
            destination_directory.strip()
        )

        if not source_path:
            raise ToolExecutionError(
                "A source file path is required."
            )

        if not destination_directory:
            raise ToolExecutionError(
                "A destination directory is required."
            )

        unresolved_source = (
            self._allowed_root / Path(source_path)
        )

        unresolved_destination = (
            self._allowed_root
            / Path(destination_directory)
        )

        if unresolved_source.is_symlink():
            raise ToolExecutionError(
                "Moving symbolic links is not allowed."
            )

        if unresolved_destination.is_symlink():
            raise ToolExecutionError(
                "Symbolic-link destinations are not allowed."
            )

        resolved_source = self._resolve_safe_path(
            source_path
        )

        resolved_destination_directory = (
            self._resolve_safe_path(
                destination_directory
            )
        )

        if not resolved_source.exists():
            raise ToolExecutionError(
                f"Source file does not exist: {source_path}"
            )

        if not resolved_source.is_file():
            raise ToolExecutionError(
                "The source path is not a regular file."
            )

        if not resolved_destination_directory.exists():
            raise ToolExecutionError(
                "Destination directory does not exist."
            )

        if not resolved_destination_directory.is_dir():
            raise ToolExecutionError(
                "The destination path is not a directory."
            )

        destination_file = (
            resolved_destination_directory
            / resolved_source.name
        )

        if not destination_file.is_relative_to(
            self._allowed_root
        ):
            raise ToolExecutionError(
                "Destination escaped the test directory."
            )

        if destination_file.exists():
            raise ToolExecutionError(
                "A file with the same name already exists "
                "in the destination directory. "
                "Overwriting is not allowed."
            )

        try:
            shutil.move(
                str(resolved_source),
                str(destination_file),
            )
        except OSError as error:
            raise ToolExecutionError(
                f"Could not move file: {error}"
            ) from error

        source_still_exists = resolved_source.exists()
        destination_exists = (
            destination_file.exists()
            and destination_file.is_file()
        )

        if source_still_exists or not destination_exists:
            raise ToolExecutionError(
                "Move verification failed."
            )

        return {
            "success": True,
            "source_path": source_path,
            "destination_directory": (
                destination_directory
            ),
            "destination_path": str(
                destination_file.relative_to(
                    self._allowed_root
                )
            ),
            "file_name": destination_file.name,
            "source_removed": True,
            "destination_verified": True,
            "message": "File moved successfully.",
        }


class FindFilesTool(SandboxedFilesystemTool):
    def __init__(
        self,
        allowed_root: Path,
        maximum_results: int,
        maximum_scanned_entries: int,
    ) -> None:
        super().__init__(allowed_root)

        self._maximum_results = maximum_results
        self._maximum_scanned_entries = (
            maximum_scanned_entries
        )

    @property
    def name(self) -> str:
        return "find_files"

    @property
    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": (
                    "Search for files inside a directory in the "
                    "controlled CrashJarvis test environment. "
                    "Can filter by file extensions, search "
                    "recursively, sort results, and limit how "
                    "many files are returned."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": (
                                "Relative directory in which to "
                                "search, for example 'Downloads'."
                            ),
                        },
                        "extensions": {
                            "type": "array",
                            "items": {
                                "type": "string",
                            },
                            "description": (
                                "Optional file extensions such as "
                                "['.mp4', '.mov']. An empty list "
                                "matches every extension."
                            ),
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": (
                                "Whether subdirectories should "
                                "also be searched."
                            ),
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": [
                                "name",
                                "size",
                                "created_at",
                                "modified_at",
                            ],
                            "description": (
                                "File property used for sorting."
                            ),
                        },
                        "sort_order": {
                            "type": "string",
                            "enum": [
                                "ascending",
                                "descending",
                            ],
                            "description": (
                                "Sorting direction. Use descending "
                                "to get newest or largest files first."
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "description": (
                                "Maximum number of matching files "
                                "to return."
                            ),
                        },
                    },
                    "required": [
                        "directory",
                    ],
                },
            },
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        directory = arguments.get("directory")

        extensions = arguments.get(
            "extensions",
            [],
        )
        recursive = arguments.get(
            "recursive",
            False,
        )
        sort_by = arguments.get(
            "sort_by",
            "name",
        )
        sort_order = arguments.get(
            "sort_order",
            "ascending",
        )
        limit = arguments.get(
            "limit",
            self._maximum_results,
        )

        if not isinstance(directory, str):
            raise ToolExecutionError(
                "The 'directory' argument must be a string."
            )

        if not isinstance(extensions, list):
            raise ToolExecutionError(
                "The 'extensions' argument must be an array."
            )

        if not all(
            isinstance(extension, str)
            for extension in extensions
        ):
            raise ToolExecutionError(
                "Every extension must be a string."
            )

        if not isinstance(recursive, bool):
            raise ToolExecutionError(
                "The 'recursive' argument must be boolean."
            )

        if sort_by not in {
            "name",
            "size",
            "created_at",
            "modified_at",
        }:
            raise ToolExecutionError(
                f"Unsupported sort property: {sort_by}"
            )

        if sort_order not in {
            "ascending",
            "descending",
        }:
            raise ToolExecutionError(
                f"Unsupported sort order: {sort_order}"
            )

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
        ):
            raise ToolExecutionError(
                "The 'limit' argument must be "
                "a positive integer."
            )

        requested_limit = min(
            limit,
            self._maximum_results,
        )

        normalized_extensions = {
            self._normalize_extension(extension)
            for extension in extensions
            if extension.strip()
        }

        target_directory = self._resolve_safe_path(
            directory
        )

        if not target_directory.exists():
            raise ToolExecutionError(
                f"Search directory does not exist: {directory}"
            )

        if not target_directory.is_dir():
            raise ToolExecutionError(
                "The search path is not a directory."
            )

        try:
            iterator = (
                target_directory.rglob("*")
                if recursive
                else target_directory.iterdir()
            )

            matching_files: list[dict[str, Any]] = []
            scanned_entries = 0
            scan_truncated = False

            for path in iterator:
                scanned_entries += 1

                if (
                    scanned_entries
                    > self._maximum_scanned_entries
                ):
                    scan_truncated = True
                    break

                if path.is_symlink():
                    continue

                if not path.is_file():
                    continue

                if (
                    normalized_extensions
                    and path.suffix.casefold()
                    not in normalized_extensions
                ):
                    continue

                matching_files.append(
                    self._create_file_result(path)
                )

        except OSError as error:
            raise ToolExecutionError(
                f"File search failed: {error}"
            ) from error

        reverse_sort = (
            sort_order == "descending"
        )

        matching_files.sort(
            key=lambda entry: self._sort_value(
                entry,
                sort_by,
            ),
            reverse=reverse_sort,
        )

        results_truncated = (
            len(matching_files) > requested_limit
        )

        results = matching_files[
            :requested_limit
        ]

        return {
            "success": True,
            "directory": directory,
            "recursive": recursive,
            "extensions": sorted(
                normalized_extensions
            ),
            "sort_by": sort_by,
            "sort_order": sort_order,
            "requested_limit": limit,
            "applied_limit": requested_limit,
            "scanned_entries": scanned_entries,
            "matched_files": len(matching_files),
            "returned_files": len(results),
            "scan_truncated": scan_truncated,
            "results_truncated": results_truncated,
            "files": results,
        }

    def _create_file_result(
        self,
        path: Path,
    ) -> dict[str, Any]:
        try:
            statistics = path.stat()
        except OSError as error:
            raise ToolExecutionError(
                f"Could not inspect '{path.name}': {error}"
            ) from error

        created_timestamp = getattr(
            statistics,
            "st_birthtime",
            statistics.st_ctime,
        )

        return {
            "name": path.name,
            "relative_path": str(
                path.relative_to(
                    self._allowed_root
                )
            ),
            "extension": path.suffix.casefold(),
            "size_bytes": statistics.st_size,
            "created_timestamp": created_timestamp,
            "modified_timestamp": statistics.st_mtime,
            "created_at_utc": datetime.fromtimestamp(
                created_timestamp,
                tz=timezone.utc,
            ).isoformat(),
            "modified_at_utc": datetime.fromtimestamp(
                statistics.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
        }

    @staticmethod
    def _normalize_extension(
        extension: str,
    ) -> str:
        normalized = extension.strip().casefold()

        if not normalized:
            return ""

        if not normalized.startswith("."):
            normalized = "." + normalized

        return normalized

    @staticmethod
    def _sort_value(
        entry: dict[str, Any],
        sort_by: str,
    ) -> object:
        if sort_by == "name":
            return entry["name"].casefold()

        if sort_by == "size":
            return entry["size_bytes"]

        if sort_by == "created_at":
            return entry["created_timestamp"]

        return entry["modified_timestamp"]


class RenamePathTool(SandboxedFilesystemTool):
    @property
    def name(self) -> str:
        return "rename_path"

    @property
    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": (
                    "Rename one existing file or directory "
                    "inside the controlled CrashJarvis test "
                    "environment. The item remains in its current "
                    "parent directory. Existing items are never "
                    "overwritten."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Current relative path of the "
                                "file or directory to rename."
                            ),
                        },
                        "new_name": {
                            "type": "string",
                            "description": (
                                "New file or directory name only, "
                                "without a parent path or slashes."
                            ),
                        },
                    },
                    "required": [
                        "path",
                        "new_name",
                    ],
                },
            },
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        relative_path = arguments.get("path")
        new_name = arguments.get("new_name")

        if not isinstance(relative_path, str):
            raise ToolExecutionError(
                "The 'path' argument must be a string."
            )

        if not isinstance(new_name, str):
            raise ToolExecutionError(
                "The 'new_name' argument must be a string."
            )

        relative_path = relative_path.strip()
        new_name = new_name.strip()

        if not relative_path:
            raise ToolExecutionError(
                "A source path is required."
            )

        if not new_name:
            raise ToolExecutionError(
                "A new name is required."
            )

        if new_name in {".", ".."}:
            raise ToolExecutionError(
                "Invalid new name."
            )

        if "/" in new_name or "\\" in new_name:
            raise ToolExecutionError(
                "The new name must not contain "
                "path separators."
            )

        unresolved_source = (
            self._allowed_root / Path(relative_path)
        )

        if unresolved_source.is_symlink():
            raise ToolExecutionError(
                "Renaming symbolic links is not allowed."
            )

        source = self._resolve_safe_path(
            relative_path
        )

        if source == self._allowed_root:
            raise ToolExecutionError(
                "Renaming the test root is not allowed."
            )

        if not source.exists():
            raise ToolExecutionError(
                f"Source path does not exist: {relative_path}"
            )

        if source.name == new_name:
            return {
                "success": True,
                "renamed": False,
                "old_path": relative_path,
                "new_path": relative_path,
                "item_type": (
                    "directory"
                    if source.is_dir()
                    else "file"
                ),
                "message": (
                    "The item already has the requested name."
                ),
            }

        unresolved_destination = (
            source.parent / new_name
        )

        if unresolved_destination.is_symlink():
            raise ToolExecutionError(
                "Symbolic-link destinations are not allowed."
            )

        try:
            destination = (
                unresolved_destination.resolve()
            )
        except OSError as error:
            raise ToolExecutionError(
                f"Could not resolve destination: {error}"
            ) from error

        if not destination.is_relative_to(
            self._allowed_root
        ):
            raise ToolExecutionError(
                "Destination escaped the test directory."
            )

        if destination.exists():
            raise ToolExecutionError(
                "An item with the requested name "
                "already exists. Overwriting is not allowed."
            )

        item_type = (
            "directory"
            if source.is_dir()
            else "file"
        )

        try:
            source.rename(destination)
        except OSError as error:
            raise ToolExecutionError(
                f"Could not rename item: {error}"
            ) from error

        if source.exists():
            raise ToolExecutionError(
                "Rename verification failed: "
                "the old path still exists."
            )

        if not destination.exists():
            raise ToolExecutionError(
                "Rename verification failed: "
                "the new path does not exist."
            )

        return {
            "success": True,
            "renamed": True,
            "old_path": relative_path,
            "new_path": str(
                destination.relative_to(
                    self._allowed_root
                )
            ),
            "item_type": item_type,
            "old_name": source.name,
            "new_name": destination.name,
            "old_path_removed": True,
            "new_path_verified": True,
            "message": "Item renamed successfully.",
        }