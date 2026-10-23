# PyInstaller spec for ATCS Monitor (one-folder build).
# Build with: ./scripts/build.sh (Linux) or scripts\build.ps1 (Windows)
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = SPECPATH + "/.."

datas = collect_data_files("ultralytics")  # tracker/model yaml configs, assets

hiddenimports = collect_submodules("ultralytics.trackers") + ["lap"]
if sys.platform == "win32":
    # DirectShow camera names: bundle the comtypes wrappers that build.ps1 generates
    # beforehand, so the frozen app never writes them to %TEMP% at runtime.
    hiddenimports += collect_submodules("pygrabber") + collect_submodules("comtypes.gen")

a = Analysis(
    [ROOT + "/app/main.py"],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "IPython", "jupyter", "notebook", "tensorboard", "pytest", "PyInstaller",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
        "PySide6.QtQml", "PySide6.QtMultimedia", "PyQt5", "PyQt6",
    ],
    noarchive=False,
)
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
