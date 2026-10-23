#!/usr/bin/env bash
# Build a self-contained one-folder executable in dist/atcs-monitor/.
# The model weights are copied next to the executable (see README > Licensing).
set -euo pipefail
cd "$(dirname "$0")/.."
export YOLO_CONFIG_DIR="$PWD/data/lib_config/ultralytics" MPLCONFIGDIR="$PWD/data/lib_config/matplotlib"
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
PY="${ATCS_BUILD_PYTHON:-.venv/bin/python}"
PYINSTALLER="${ATCS_BUILD_PYINSTALLER:-.venv/bin/pyinstaller}"  # overridable for tests/test_build_preservation.py
DIST="${ATCS_BUILD_DIST:-dist}"
OUT="$DIST/atcs-monitor"
# PyInstaller replaces the whole output folder, but the packaged app keeps its sessions,
# settings, recordings and exports inside it: move those aside and put them back.
KEEP="$DIST/preserved-$(date +%Y%m%d-%H%M%S)"
"$PY" scripts/preserve_runtime_data.py stash "$OUT" "$KEEP"
"$PYINSTALLER" --noconfirm --clean --distpath "$DIST" --workpath build/work packaging/atcs_monitor.spec \
  || { echo "PyInstaller failed; the previous build's data (if any) is in $KEEP" >&2; exit 1; }
"$PY" scripts/preserve_runtime_data.py restore "$OUT" "$KEEP"
mkdir -p "$OUT/models" "$OUT/recordings" "$OUT/exports" "$OUT/data"
cp -n models/*.pt "$OUT/models/" 2>/dev/null || echo "warning: no weights in models/ - run scripts/download_model.py"
cp LICENSE "$OUT/" 2>/dev/null || true
du -sh "$OUT"
echo "Built $OUT/atcs-monitor"
