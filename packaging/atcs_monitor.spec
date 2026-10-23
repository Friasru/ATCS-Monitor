# PyInstaller spec for ATCS Monitor (one-folder build).
# Build with: ./scripts/build.sh
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = SPECPATH + "/.."

datas = collect_data_files("ultralytics")  # tracker/model yaml configs, assets

hiddenimports = collect_submodules("ultralytics.trackers") + ["lap"]

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
