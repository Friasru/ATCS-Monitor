# PyInstaller spec for ATCS Monitor (one-folder build).
# Build with: ./scripts/build.sh (Linux) or scripts\build.ps1 (Windows)
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = SPECPATH + "/.."

datas = collect_data_files("ultralytics")  # tracker/model yaml configs, assets

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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="atcs-monitor",
    console=False,
    strip=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="atcs-monitor")
