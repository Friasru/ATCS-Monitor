# Build the native Windows one-folder executable: dist\windows\atcs-monitor\atcs-monitor.exe
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1
# Output goes under dist\windows\ so it never overwrites the Linux build in dist\atcs-monitor\.
# The model weights are copied next to the executable (see README > Licensing).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Py = Join-Path $Root ".venv-win\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "run scripts\setup.ps1 first (.venv-win not found)" }

$env:YOLO_CONFIG_DIR = Join-Path $Root "data\lib_config\ultralytics"
$env:MPLCONFIGDIR = Join-Path $Root "data\lib_config\matplotlib"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $Root "build\pyinstaller-cache-win"

# Generate the comtypes DirectShow wrappers inside .venv-win so the spec can bundle them.
& $Py -c "import sys; sys.path.insert(0, '.'); from app.camera.sources import _windows_camera_names as n; print('DirectShow devices:', n())"
if ($LASTEXITCODE -ne 0) { throw "could not prepare the DirectShow (comtypes) wrappers" }

& $Py -m PyInstaller --noconfirm --clean --distpath dist\windows --workpath build\windows-work packaging\atcs_monitor.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

$Out = Join-Path $Root "dist\windows\atcs-monitor"
foreach ($d in @("models", "recordings", "exports", "data")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Out $d) | Out-Null
}
$weights = Get-ChildItem -Path (Join-Path $Root "models") -Filter *.pt -ErrorAction SilentlyContinue
if ($weights) {
    foreach ($w in $weights) {
        $dest = Join-Path $Out "models\$($w.Name)"
        if (-not (Test-Path $dest)) { Copy-Item $w.FullName $dest }
    }
} else {
    Write-Warning "no weights in models\ - run scripts\download_model.py"
}
if (Test-Path (Join-Path $Root "LICENSE")) { Copy-Item (Join-Path $Root "LICENSE") $Out -Force }
$size = (Get-ChildItem $Out -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB
Write-Host ("Built {0}\atcs-monitor.exe ({1:N2} GB)" -f $Out, $size)
