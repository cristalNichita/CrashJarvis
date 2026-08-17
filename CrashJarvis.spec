from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs


datas = []
binaries = []
hiddenimports = []

for package in (
    "ctranslate2",
    "faster_whisper",
    "kokoro_onnx",
    "ollama",
    "onnxruntime",
    "openwakeword",
    "pywinauto",
    "sounddevice",
    "soxr",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

for package in ("nvidia.cublas", "nvidia.cudnn"):
    binaries += collect_dynamic_libs(package)


a = Analysis(
    ["src/crashjarvis/ui/runtime_app.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CrashJarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CrashJarvis",
)
