# Build the Windows installer (Inno Setup): dist\installer\ATCS-Monitor-<version>-Setup-<CPU|CUDA>.exe
#   powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1                 CPU-only installer (default)
#   powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 -Flavor cuda    NVIDIA CUDA installer
#   ... -Rebuild                                                                          rebuild the PyInstaller folder first
# Needs the matching environment: .venv-win-cpu (setup.ps1 -Cpu -Venv .venv-win-cpu) or .venv-win (setup.ps1).
# Inno Setup is downloaded once (pinned version, SHA-256 checked) into build\tools\ - nothing is installed system-wide.
param(
    [ValidateSet("cpu", "cuda")] [string]$Flavor = "cpu",
    [switch]$Rebuild
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$InnoVersion = "6.7.3"
$InnoUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
$InnoSha256 = "9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732"
$InnoDir = Join-Path $Root "build\tools\innosetup-$InnoVersion"
$Iscc = Join-Path $InnoDir "ISCC.exe"

if ($Flavor -eq "cuda") { $Venv = ".venv-win"; $Dist = "dist\windows" } else { $Venv = ".venv-win-cpu"; $Dist = "dist\windows-cpu" }
$Src = Join-Path $Root "$Dist\atcs-monitor"

# 1. The PyInstaller folder for this flavour.
if ($Rebuild -or -not (Test-Path (Join-Path $Src "atcs-monitor.exe"))) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build.ps1") -Venv $Venv -Dist $Dist
    if ($LASTEXITCODE -ne 0) { throw "build.ps1 failed" }
}
$weights = Get-ChildItem (Join-Path $Src "models") -Filter *.pt -ErrorAction SilentlyContinue
if (-not $weights) { throw "no model weights in $Src\models - run scripts\download_model.py, then build with -Rebuild" }
$py = Join-Path $Root "$Venv\Scripts\python.exe"
$torch = & $py -c "import torch; print('cuda' if torch.version.cuda else 'cpu')"
if ("$torch".Trim() -ne $Flavor) { throw "$Venv has a $torch PyTorch, but a $Flavor installer was requested" }

# 2. Inno Setup (portable copy under build\tools).
if (-not (Test-Path $Iscc)) {
    $tools = Join-Path $Root "build\tools"
    New-Item -ItemType Directory -Force -Path $tools | Out-Null
    $setup = Join-Path $tools "innosetup-$InnoVersion.exe"
    if (-not (Test-Path $setup)) { Invoke-WebRequest -Uri $InnoUrl -OutFile $setup -UseBasicParsing }
    $hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $InnoSha256) { Remove-Item $setup; throw "Inno Setup download has an unexpected SHA-256 ($hash)" }
    $p = Start-Process -FilePath $setup -Wait -PassThru -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/PORTABLE=1", "/NOICONS", "/DIR=`"$InnoDir`"")
    if ($p.ExitCode -ne 0 -or -not (Test-Path $Iscc)) { throw "unpacking Inno Setup failed ($($p.ExitCode))" }
}

# 3. Compile.
$version = ([regex]'__version__ = "([^"]+)"').Match((Get-Content (Join-Path $Root "app\__init__.py") -Raw)).Groups[1].Value
$out = Join-Path $Root "dist\installer"
New-Item -ItemType Directory -Force -Path $out | Out-Null
& $Iscc "/Qp" "/DFlavor=$Flavor" "/DAppVersion=$version" "/DSrcDir=$Src" "/DOutputDir=$out" (Join-Path $Root "packaging\installer\atcs_monitor.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed ($LASTEXITCODE)" }
Write-Host ""  # ISCC /Qp leaves its progress line open

$suffix = $Flavor.ToUpper()
$files = Get-ChildItem $out -Filter "ATCS-Monitor-$version-Setup-$suffix*"
foreach ($f in $files) {
    Write-Host ("{0}  {1:N0} MB  sha256 {2}" -f $f.FullName, ($f.Length / 1MB), (Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower())
}
