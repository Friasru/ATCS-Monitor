#!/usr/bin/env python3
"""Keep a portable build's runtime data safe while the build is replaced.

PyInstaller deletes its whole output folder (dist/.../atcs-monitor) on every
build, but a portable build keeps its sessions database, settings, logs,
recordings and exports inside that folder. build.sh and build.ps1 call

  preserve_runtime_data.py stash   OUT KEEP   before PyInstaller runs
  preserve_runtime_data.py restore OUT KEEP   after it succeeded

`stash` moves OUT/data, OUT/recordings and OUT/exports (if not empty) into
KEEP. `restore` moves them back. Nothing is ever deleted or overwritten: if a
file already exists in the new build it stays in KEEP, KEEP is kept and the
exit code is 1. If the build fails, the data simply stays in KEEP.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

RUNTIME_DIRS = ("data", "recordings", "exports")


def stash(out: Path, keep: Path) -> list[str]:
    moved = []
    for name in RUNTIME_DIRS:
        src = out / name
        if src.is_dir() and any(src.iterdir()):
            if (keep / name).exists():
                raise FileExistsError(f"{keep / name} already exists; refusing to mix two builds' data")
            keep.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(keep / name))
            moved.append(name)
    return moved


def _merge(src: Path, dst: Path, left: list[Path]) -> None:
    """Move src into dst without overwriting; record anything that could not move."""
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return
    if src.is_dir() and dst.is_dir():
        for child in list(src.iterdir()):
            _merge(child, dst / child.name, left)
        if not any(src.iterdir()):
            src.rmdir()
        return
    left.append(src)  # an existing file (or a file/folder clash): never overwrite it


def restore(out: Path, keep: Path) -> list[Path]:
    """Return the paths that are still in KEEP (empty list = everything restored)."""
    left: list[Path] = []
    if not keep.is_dir():
        return left
    for name in RUNTIME_DIRS:
        if (keep / name).exists():
            _merge(keep / name, out / name, left)
    if not any(keep.iterdir()):
        keep.rmdir()
    return left


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in ("stash", "restore"):
        print(__doc__, file=sys.stderr)
        return 2
    action, out, keep = argv[0], Path(argv[1]), Path(argv[2])
    if action == "stash":
        moved = stash(out, keep)
        if moved:
            print(f"Kept existing {', '.join(moved)} of the previous build in {keep}")
        return 0
    left = restore(out, keep)
    if left:
        print(f"Restored the previous build's data into {out}, except {len(left)} item(s) that already exist "
              f"there; they are still in {keep}:", *left, sep="\n  ", file=sys.stderr)
        return 1
    print(f"Restored the previous build's data into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
