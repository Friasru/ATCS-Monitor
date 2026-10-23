"""ATCS Monitor entry point."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
import traceback
from pathlib import Path

if __package__ in (None, ""):  # allow `python app/main.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import APP_NAME, __version__, paths  # noqa: E402

log = logging.getLogger("atcs_monitor")


def setup_logging(verbose: bool = False) -> Path:
    log_file = paths.logs_dir() / "atcs_monitor.log"
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"))
    console = logging.StreamHandler()
    console.setLevel(logging.INFO if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(console)
    logging.getLogger("ultralytics").setLevel(logging.ERROR)  # silence per-frame chatter
    return log_file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="atcs-monitor", description=f"{APP_NAME} {__version__}")
    ap.add_argument("--video", help="pre-select a video file as source")
    ap.add_argument("--start", action="store_true", help="start monitoring immediately")
    ap.add_argument("--record", action="store_true", help="with --start: begin recording as soon as detection runs")
    ap.add_argument("--quit-after", type=int, default=0, metavar="MS",
                    help="close the window after MS milliseconds (launch checks)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    paths.configure_third_party_dirs()
    log_file = setup_logging(args.verbose)
    log.info("%s %s starting (root=%s)", APP_NAME, __version__, paths.project_root())

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.settings import load_settings
    from app.storage.repository import Repository, StorageError
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)

    def excepthook(exc_type, exc, tb):
        log.critical("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        QMessageBox.critical(None, APP_NAME, f"Unexpected error: {exc}\n\nDetails were written to {log_file}")

    sys.excepthook = excepthook

    try:
        repo = Repository(paths.database_path())
        n = repo.mark_interrupted_sessions()
        if n:
            log.warning("%d session(s) from a previous run were not closed and are now marked 'interrupted'", n)
    except StorageError as exc:
        QMessageBox.critical(None, APP_NAME, f"Cannot open the local database:\n{exc}")
        return 2

    win = MainWindow(load_settings(), repo)
    win.show()
    if args.video:
        win.add_video_source(args.video)
        if args.start:
            QTimer.singleShot(300, win.start_monitoring)
            if args.record:
                from app.services.monitoring import State

                def record_when_ready():
                    if win.state == State.DETECTING:
                        win.start_recording()
                    elif win.state in (State.INITIALIZING, State.IDLE):
                        QTimer.singleShot(200, record_when_ready)

                QTimer.singleShot(500, record_when_ready)
    if args.quit_after > 0:
        QTimer.singleShot(args.quit_after, win.close)
    rc = app.exec()
    # Destroy Qt objects deterministically before the interpreter tears down
    # (otherwise PySide6 may finalize widgets after QApplication is gone).
    win.deleteLater()
    del win
    app.processEvents()
    repo.close()
    log.info("%s exited with code %s", APP_NAME, rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
