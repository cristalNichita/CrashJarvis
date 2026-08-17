import ctypes
import os
import sys
from pathlib import Path

_DLL_DIRECTORY_HANDLES: list[object] = []
_LOADED_LIBRARIES: list[ctypes.CDLL] = []
_CONFIGURED_DIRECTORIES: tuple[Path, ...] = ()

class CudaRuntimeError(RuntimeError):
    """Raised when required CUDA runtime libraries cannot be loaded"""

def configure_cuda_runtime() -> tuple[Path, ...]:
    global _CONFIGURED_DIRECTORIES

    if _CONFIGURED_DIRECTORIES:
        return _CONFIGURED_DIRECTORIES

    if os.name != "nt":
        return ()

    site_packages = (
        Path(sys.prefix)
        / "Lib"
        / "site-packages"
    )

    runtime_directories = (
        site_packages / "nvidia" / "cublas" / "bin",
        site_packages / "nvidia" / "cudnn" / "bin",
    )

    missing_directories = [
        directory
        for directory in runtime_directories
        if not directory.is_dir()
    ]

    if missing_directories:
        missing = "\n".join(map(str, missing_directories))
        raise CudaRuntimeError(
            f"Required CUDA directories were not found:\n{missing}"
        )

    existing_path = os.environ.get("PATH", "")
    runtime_path = os.pathsep.join(
        str(directory) for directory in runtime_directories
    )
    os.environ["PATH"] = f"{runtime_path}{os.pathsep}{existing_path}"

    for directory in runtime_directories:
        handle = os.add_dll_directory(str(directory))
        _DLL_DIRECTORY_HANDLES.append(handle)

    for library_name in ("cublas64_12.dll", "cudnn64_9.dll"):
        try:
            library = ctypes.WinDLL(library_name)
            _LOADED_LIBRARIES.append(library)
        except OSError as error:
            raise CudaRuntimeError(
                f"Could not load {library_name}: {error}"
            ) from error

    _CONFIGURED_DIRECTORIES = runtime_directories

    return runtime_directories