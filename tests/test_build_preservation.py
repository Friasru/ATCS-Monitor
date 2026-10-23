"""Rebuilding the portable app must never delete its sessions, settings, recordings or exports.

PyInstaller removes its whole output folder on every build. These tests run the
real build scripts (build.sh on Linux, build.ps1 on Windows) with a stand-in for
PyInstaller that deletes and recreates the output folder the same way - inside
a temporary directory, never the real dist/ folder.
"""

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("preserve_runtime_data", ROOT / "scripts" / "preserve_runtime_data.py")
assert spec is not None and spec.loader is not None
prd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prd)

STUB = '''
import os, shutil, sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--distpath") + 1]) / "atcs-monitor"
shutil.rmtree(out, ignore_errors=True)  # what PyInstaller --noconfirm does
if os.environ.get("STUB_FAIL"):
    sys.exit(3)
(out / "_internal").mkdir(parents=True)
for exe in ("atcs-monitor", "atcs-monitor.exe"):
    (out / exe).write_text("new build")
'''


def make_build(out: Path) -> dict[str, str]:
    """A previous portable build with user data; returns {relative path: sha256}."""
    files = {
        "data/atcs_monitor.sqlite3": os.urandom(4096),
        "data/settings.json": b'{"model_name": "yolo26n.pt"}',
        "data/logs/atcs_monitor.log": b"log line\n",
        "recordings/atcs_20261023-120000_abcd1234.mp4": os.urandom(100_000),
        "exports/session_abcd1234.json": b"{}",
        "_internal/old_program_file.dll": b"old build",
    }
    for rel, content in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(content)
    return {rel: hashlib.sha256(c).hexdigest() for rel, c in files.items() if not rel.startswith("_internal")}


def digests(base: Path, rels) -> dict[str, str]:
    return {rel: hashlib.sha256((base / rel).read_bytes()).hexdigest() for rel in rels if (base / rel).is_file()}


# --------------------------------------------------------------- the helper


def test_stash_and_restore_keep_every_file(tmp_path):
    out, keep = tmp_path / "atcs-monitor", tmp_path / "keep"
    want = make_build(out)
    assert prd.stash(out, keep) == ["data", "recordings", "exports"]
    shutil.rmtree(out)  # the build replaces the folder
    (out / "_internal").mkdir(parents=True)
    assert prd.restore(out, keep) == []
    assert digests(out, want) == want
    assert not keep.exists()


def test_empty_runtime_folders_are_left_alone(tmp_path):
    out, keep = tmp_path / "atcs-monitor", tmp_path / "keep"
    for d in ("data", "recordings", "exports"):
        (out / d).mkdir(parents=True)
    assert prd.stash(out, keep) == []
    assert not keep.exists()


def test_restore_never_overwrites_and_reports_leftovers(tmp_path):
    out, keep = tmp_path / "atcs-monitor", tmp_path / "keep"
    want = make_build(out)
    prd.stash(out, keep)
    (out / "data").mkdir(parents=True)
    (out / "data" / "settings.json").write_text("new build default")
    left = prd.restore(out, keep)
    assert left == [keep / "data" / "settings.json"]
    assert (out / "data" / "settings.json").read_text() == "new build default"
    assert hashlib.sha256((keep / "data" / "settings.json").read_bytes()).hexdigest() == want["data/settings.json"]
    rest = {k: v for k, v in want.items() if k != "data/settings.json"}
    assert digests(out, rest) == rest


def test_stash_refuses_to_mix_two_builds(tmp_path):
    out, keep = tmp_path / "atcs-monitor", tmp_path / "keep"
    make_build(out)
    (keep / "recordings").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        prd.stash(out, keep)
    assert (out / "recordings").is_dir()  # nothing was moved half-way


# ------------------------------------------------------- the build scripts


def run_build(tmp_path, fail=False):
    dist = tmp_path / "dist"
    stub = tmp_path / "stub_pyinstaller.py"
    stub.write_text(STUB)
    env = {**os.environ, "STUB_FAIL": "1" if fail else ""}
    if sys.platform == "win32":
        out = dist / "atcs-monitor"
        env["ATCS_BUILD_PYINSTALLER"] = str(stub)
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "build.ps1"),
               "-Venv", sys.prefix, "-Dist", str(dist)]
    else:
        if not shutil.which("bash"):
            pytest.skip("bash not available")
        out = dist / "atcs-monitor"
        wrapper = tmp_path / "pyinstaller"
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@"\n')
        wrapper.chmod(0o755)
        env.update(ATCS_BUILD_PYINSTALLER=str(wrapper), ATCS_BUILD_PYTHON=sys.executable, ATCS_BUILD_DIST=str(dist))
        cmd = ["bash", str(ROOT / "scripts" / "build.sh")]
    want = make_build(out)
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    return res, dist, out, want


def test_rebuild_keeps_user_data(tmp_path):
    res, dist, out, want = run_build(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    assert (out / "atcs-monitor").read_text() == "new build"
    assert not (out / "_internal" / "old_program_file.dll").exists()  # the program itself was replaced
    assert digests(out, want) == want  # every recording, database, setting and export is intact
    assert not list(dist.glob("preserved-*"))


def test_failed_build_keeps_user_data_aside(tmp_path):
    res, dist, _, want = run_build(tmp_path, fail=True)
    assert res.returncode != 0
    kept = list(dist.glob("preserved-*"))
    assert len(kept) == 1
    assert digests(kept[0], want) == want
    assert "preserved-" in res.stdout + res.stderr  # the message says where the data is
