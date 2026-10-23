"""Project-local path resolution.

All runtime writes go below the project root (or, for a frozen build, below the
directory containing the executable). The root can be overridden with the
ATCS_MONITOR_HOME environment variable, which the test-suite uses to isolate
its writes in a temporary directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    override = os.environ.get("ATCS_MONITOR_HOME")
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        # PyInstaller onedir: <root>/dist/atcs-monitor/atcs-monitor -> use the
        # folder holding the executable so data stays next to the program.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_root() -> Path:
    """Location of read-only resources shipped with the program."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def models_dir() -> Path:
    return _ensure(project_root() / "models")


def recordings_dir() -> Path:
    return _ensure(project_root() / "recordings")


def data_dir() -> Path:
    return _ensure(project_root() / "data")


def exports_dir() -> Path:
    return _ensure(project_root() / "exports")


def logs_dir() -> Path:
    return _ensure(data_dir() / "logs")


def database_path() -> Path:
    return data_dir() / "atcs_monitor.sqlite3"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def configure_third_party_dirs() -> None:
    """Keep library config/cache writes inside the project.

    Must run before ultralytics / matplotlib are imported.
    """
    cfg = _ensure(data_dir() / "lib_config")
    os.environ.setdefault("YOLO_CONFIG_DIR", str(_ensure(cfg / "ultralytics")))
    os.environ.setdefault("MPLCONFIGDIR", str(_ensure(cfg / "matplotlib")))
    # Ultralytics must never try to pip-install anything at runtime.
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    os.environ.setdefault("YOLO_OFFLINE", "true")
