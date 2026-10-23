# PyInstaller spec for ATCS Monitor (one-folder build).
# Build with: ./scripts/build.sh (Linux) or scripts\build.ps1 (Windows)
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = SPECPATH + "/.."
VERSION = re.search(r'__version__ = "([^"]+)"', open(ROOT + "/app/__init__.py", encoding="utf-8").read()).group(1)
ICON = ROOT + "/app/resources/atcs_monitor.ico"

datas = collect_data_files("ultralytics")  # tracker/model yaml configs, assets
datas += [(ROOT + "/app/resources", "app/resources")]  # window/taskbar icon

hiddenimports = collect_submodules("ultralytics.trackers") + ["lap"]
excludes = [
    "tkinter", "IPython", "jupyter", "notebook", "tensorboard", "pytest", "PyInstaller",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
    "PySide6.QtQml", "PySide6.QtMultimedia", "PyQt5", "PyQt6",
]
# Windows size trimming (docs/windows.md#executable-size). Each item was verified
# unused: the modules are never imported while monitoring, and with the DLLs
# removed the CUDA pipeline gives bit-identical detections at the same speed.
UNUSED_TORCH_DLLS = set()
if sys.platform == "win32":
    # DirectShow camera names: bundle the comtypes wrappers that build.ps1 generates
    # beforehand, so the frozen app never writes them to %TEMP% at runtime.
    hiddenimports += collect_submodules("pygrabber") + collect_submodules("comtypes.gen")
    excludes += ["polars", "matplotlib"]  # optional Ultralytics extras (165 MB + 15 MB)
    UNUSED_TORCH_DLLS = {
        "cusolvermg64_11.dll",  # multi-GPU dense solver, 150 MB
        "curand64_10.dll",  # cuRAND, 69 MB (torch has its own GPU RNG)
        "nvperf_host.dll",  # profiler, 21 MB
        "cudnn_adv64_9.dll",  # cuDNN RNN/attention kernels, 257 MB (YOLO uses convolution kernels)
    }

a = Analysis(
    [ROOT + "/app/main.py"],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
a.binaries = [b for b in a.binaries if b[0].replace("\\", "/").rsplit("/", 1)[-1].lower() not in UNUSED_TORCH_DLLS]
pyz = PYZ(a.pure)

version_info = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                     VarFileInfo, VarStruct, VSVersionInfo)

    nums = tuple(int(x) for x in (VERSION.split(".") + ["0"] * 4)[:4])
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "ATCS Monitor"),
                StringStruct("FileDescription", "ATCS Monitor"),
                StringStruct("FileVersion", VERSION),
                StringStruct("InternalName", "atcs-monitor"),
                StringStruct("OriginalFilename", "atcs-monitor.exe"),
                StringStruct("ProductName", "ATCS Monitor"),
                StringStruct("ProductVersion", VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="atcs-monitor",
    console=False,
    strip=False,
    upx=False,
    icon=ICON if sys.platform == "win32" else None,
    version=version_info,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="atcs-monitor")
