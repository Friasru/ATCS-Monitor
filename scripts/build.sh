#!/usr/bin/env bash
# Build a self-contained one-folder executable in dist/atcs-monitor/.
# The model weights are copied next to the executable (see README > Licensing).
set -euo pipefail
cd "$(dirname "$0")/.."
export YOLO_CONFIG_DIR="$PWD/data/lib_config/ultralytics" MPLCONFIGDIR="$PWD/data/lib_config/matplotlib"
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
.venv/bin/pyinstaller --noconfirm --clean --distpath dist --workpath build/work packaging/atcs_monitor.spec
OUT=dist/atcs-monitor
mkdir -p "$OUT/models" "$OUT/recordings" "$OUT/exports" "$OUT/data"
cp -n models/*.pt "$OUT/models/" 2>/dev/null || echo "warning: no weights in models/ - run scripts/download_model.py"
cp LICENSE "$OUT/" 2>/dev/null || true
du -sh "$OUT"
echo "Built $OUT/atcs-monitor"
