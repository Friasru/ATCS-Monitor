# ATCS Monitor on Windows

Native Windows 10/11 (x64) support: the app runs on the Windows Python, captures from the webcam
through DirectShow or Media Foundation, and can be packaged as a Windows `.exe`. The Linux/WSL2
setup (`.venv`, `setup.sh`, `start.sh`, `build.sh`) is unchanged. Windows uses its own
environment, `.venv-win`, so one checkout can hold both environments.

> Run everything below in **PowerShell** on Windows (not inside WSL). WSL2 cannot see a laptop's
> built-in webcam without `usbipd`, while native Windows uses it directly.

## 1. Requirements

| | |
|---|---|
| OS | Windows 10 or 11, 64-bit |
| Python | 64-bit CPython 3.10 or newer (validated with **3.14.7**). All pinned packages ship native wheels for it. |
| GPU | Optional. With an NVIDIA driver installed (`nvidia-smi` works), setup installs the CUDA 12.8 build of PyTorch. No separate CUDA toolkit is needed because the wheel bundles its runtime. |
| Disk | About 6 GB for `.venv-win` with CUDA PyTorch (about 1 GB with `-Cpu`), plus about 5 GB for a CUDA `.exe` build |
| Git | Optional (only to clone) |

Install Python if `py --list` shows nothing: `winget install Python.Python.3.14`, or use the
installer from python.org (tick *Add python.exe to PATH*, or rely on the `py` launcher).

## 2. Get the code onto a Windows drive

Clone or copy the repository to a normal Windows folder, for example `C:\dev\ATCS-Monitor`.
Do **not** create `.venv-win` inside a `\\wsl$\...` path. It works, but installing and starting
PyTorch over the WSL file share is very slow, and `cmd.exe` cannot use a UNC working directory.

```powershell
git clone https://github.com/Friasru/ATCS-Monitor.git C:\dev\ATCS-Monitor
cd C:\dev\ATCS-Monitor
```

## 3. Install

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # CUDA PyTorch if an NVIDIA GPU is found
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Cpu     # force the small CPU-only PyTorch
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Python C:\Path\to\python.exe   # pick an interpreter
```

`-ExecutionPolicy Bypass` applies only to that one command and leaves the machine policy unchanged.
`setup.ps1` does the following:
1. creates `.venv-win` (it picks the newest `py -3.x` from 3.14 down to 3.10, then `python`)
2. installs `torch==2.11.0` and `torchvision==0.26.0` from the `cu128` index (or `cpu`)
3. installs `requirements-dev.txt`, which includes the Windows-only `pygrabber` used for camera names
4. replaces `opencv-python` with `opencv-python-headless`, as on Linux
5. downloads `models/yolo26n.pt`
6. prints whether CUDA is available

Confirm the GPU build:

```powershell
.venv-win\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## 4. Launch

```powershell
.\start.cmd                                                  # or double-click start.cmd in Explorer
.\start.cmd --video data\test_media\street_cebu.mp4 --start  # open a file and start immediately
```

`start.cmd` runs `start.ps1` with the execution policy bypassed for that script only. If your
policy already allows local scripts, you can run `.\start.ps1` directly. The launcher checks
`.venv-win` and the imports, keeps third-party config inside `data\lib_config\`, and starts
`python -m app.main`. Logs are written to `data\logs\atcs_monitor.log`.

## 5. Cameras on Windows

Capture APIs are tried in this order: **DirectShow** (`CAP_DSHOW`), then **Media Foundation** (`CAP_MSMF`).
Each API is used only if the installed OpenCV can load it.

> **Media Foundation is not available with the pinned `opencv-python-headless==5.0.0.93`.** Its
> Windows wheel is built with DirectShow only. MSMF is registered as an optional plugin, but no plugin
> DLL is shipped, so `cv2.videoio_registry.hasBackend(cv2.CAP_MSMF)` is `False`. The app detects this and
> uses DirectShow alone. The MSMF path becomes active automatically with an OpenCV build that includes it.
> The pin was kept so Linux and Windows run the same, tested OpenCV.

* **Find Cameras** reads the DirectShow device names (for example "Integrated Camera") and keeps only
  the devices that actually deliver a frame. A virtual camera such as "OBS Virtual Camera" is
  skipped while OBS is not running. If DirectShow finds no camera, Media Foundation is probed
  instead, when it is available.
* The API that worked during discovery is the one used when you press **Start** and when the app
  reconnects after a disconnect.
* To force an API, set `ATCS_CAMERA_BACKEND` to `dshow`, `msmf` or `any` before launching:
  `$env:ATCS_CAMERA_BACKEND = "msmf"; .\start.cmd`
* When MSMF is available, its hardware transforms are switched off
  (`OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0`), because otherwise each open can take several seconds.
* DirectShow reports the camera frame rate as `-1` (unknown). The app treats this as unknown and
  records at *Max processed FPS* (15 by default), or at 15 FPS when that setting is 0 (unlimited).

**Windows camera privacy settings:** *Settings → Privacy & security → Camera* must allow
*Camera access* and *Let desktop apps access your camera*. Otherwise the camera opens but returns no frames.
Only one program can use a webcam at a time, so close Teams, Zoom or the Camera app first.

## 6. Validate the webcam (headless)

`scripts\camera_check.py` checks the whole camera path without the GUI:

```powershell
.venv-win\Scripts\python.exe scripts\camera_check.py --probe-only        # discovery + backend/resolution matrix
.venv-win\Scripts\python.exe scripts\camera_check.py --seconds 30        # + full pipeline with recording
.venv-win\Scripts\python.exe scripts\camera_check.py --index 0 --backend msmf --width 640 --height 480
```

It does the following:
1. lists the cameras
2. opens the camera with each capture API at 640×480, 1280×720 and 1920×1080, and measures the
   resolution and FPS actually delivered
3. runs the real engine (detection, tracking, counting with a vertical line through the image
   centre, annotated recording, SQLite) for `--seconds`. Walk across the frame during this run to
   produce line crossings.
4. checks the results independently: it re-opens and counts the frames of the MP4, compares the
   database totals with the JSON and CSV exports, and compares crossing totals with crossing events

The full report goes to `data\camera_check\camera_check_<time>.json`, and exit code 0 means every
check passed. The session also appears in the app's **History**.

The opt-in pytest hardware tests use the same camera:

```powershell
$env:ATCS_TEST_CAMERA = "1"; .venv-win\Scripts\python.exe -m pytest tests\test_camera_hw.py -v; Remove-Item Env:ATCS_TEST_CAMERA
```

### Manual GUI check
1. Run `.\start.cmd`, then **Find Cameras** and select the camera. **Settings** lets you pick 1280×720.
2. Press **Start**. The status bar should read `Device: CUDA` on an NVIDIA machine, and the boxes should follow you.
3. Press **Counting Lines**, drag the line across the frame and walk across it. The *Line crossings* row should increase.
4. Press **Record**, wait at least 10 s, then **End Recording** and **Stop**. The camera LED must turn off.
5. In **History**, select the session. Recording status should be `ok`. Use **View Recording** and **Export CSV / JSON**.

## 7. Tests

```powershell
.venv-win\Scripts\python.exe -m pytest                       # whole suite
.venv-win\Scripts\python.exe -m pytest -m "not model and not gui"
powershell -ExecutionPolicy Bypass -File scripts\fetch_test_media.ps1   # videos for the media tests
```

`fetch_test_media.ps1` transcodes the two Wikimedia clips with ffmpeg if it is on `PATH`.
Otherwise it uses the project's OpenCV.

## 8. Build the Windows executable

There are two builds. Both have every feature: camera, video files, detection, tracking, counting,
recording, history and export. They differ only in whether inference can use an NVIDIA GPU.

| Build | Command | Size | Inference |
|---|---|---|---|
| **CUDA (accelerated)** | `scripts\build.ps1` (from `.venv-win`) | **3.82 GB** | NVIDIA GPU, or CPU when no GPU is usable |
| **CPU-only (lightweight)** | `scripts\build.ps1 -Venv .venv-win-cpu -Dist dist\windows-cpu` | **0.62 GB** | CPU |

```powershell
# CUDA build (needs .venv-win from setup.ps1 on a machine with an NVIDIA driver)
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
# CPU-only build: separate CPU environment, then build from it (works on any x64 PC)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Cpu -Venv .venv-win-cpu
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Venv .venv-win-cpu -Dist dist\windows-cpu

dist\windows\atcs-monitor\atcs-monitor.exe
dist\windows\atcs-monitor\atcs-monitor.exe --video C:\path\clip.mp4 --start --record --quit-after 20000
dist\windows\atcs-monitor\atcs-monitor.exe --camera 0 --start --record --quit-after 30000
```

`--camera INDEX` selects a discovered camera, and it also works with `start.cmd`. It is a windowed app,
so to see the exit code, use
`(Start-Process dist\windows\atcs-monitor\atcs-monitor.exe -ArgumentList '--camera','0','--start','--quit-after','20000' -Wait -PassThru).ExitCode`.

`build.ps1` first generates the comtypes DirectShow wrappers in the environment, and the build bundles them,
so the frozen app does not generate code at runtime. comtypes still creates an **empty** folder
`%TEMP%\comtypes_cache\atcs-monitor-314` when it is imported. No files are written there.

The build goes to `dist\windows\atcs-monitor\` so that it never overwrites the Linux build in
`dist\atcs-monitor\`. Copy the whole folder, not just the `.exe`. The packaged app keeps `data\`,
`recordings\`, `exports\` and `models\` next to `atcs-monitor.exe`. It is a windowed app with no
console, so check `data\logs\atcs_monitor.log` next to the `.exe` for diagnostics.

### Executable size

The first CUDA build was **4.48 GB**. About 90 % of that is PyTorch, mostly NVIDIA libraries:

| Component (first CUDA build) | MB |
|---|---|
| `torch` total | 4,083 |
| `torch_cuda.dll` | 774 |
| `cublasLt64_12.dll` | 643 |
| `cudnn_engines_precompiled64_9.dll` | 459 |
| `cusparse64_12.dll` | 362 |
| `cufft64_11.dll` | 263 |
| `cudnn_adv64_9.dll` | 257 |
| `torch_cpu.dll` | 254 |
| `cusolver64_11.dll` | 215 |
| `polars` (optional Ultralytics dependency) | 165 |
| `cusolverMg64_11.dll` | 150 |
| OpenCV / PySide6 | 112 / 74 |

What was removed from the CUDA build (−0.66 GB, in `packaging/atcs_monitor.spec`, Windows only):
* `polars` and `matplotlib` (180 MB). They are never imported while the app runs; checked with `sys.modules` after full GPU runs.
* `cusolverMg64_11`, `curand64_10`, `nvperf_host` and `cudnn_adv64_9` (497 MB). No other DLL links against them
  (checked with the PE import tables). With them removed, the GPU pipeline produced **bit-identical detections on
  every frame** of two test clips at the same speed. Repeated full runs are also bit-identical, so the comparison is exact.

What was kept, and why:
* `torch_cuda`, cuBLAS, cuSPARSE, cuFFT, cuSOLVER and nvJitLink are linked directly by PyTorch (2.7 GB).
* The NVRTC libraries: PyTorch fails to start without them (`caffe2_nvrtc.dll` depends on them).
* The cuDNN convolution libraries (`cudnn_ops`, `cudnn_engines_*`, `cudnn_heuristic`): YOLO runs on them.

The trimming was validated on an RTX 5060 (Blackwell). The libraries removed are not specific to a GPU
architecture, but other GPUs were not tested. Further reduction needs a smaller PyTorch, which is what the CPU
build is: `torch_cpu.dll` (254 MB) instead of 3.6 GB.

Performance (`scripts\benchmark.py micro`, Core Ultra 9 275HX + RTX 5060 Laptop, `yolo26n.pt`, detect + track per frame):

| Input | Device | Inference size | Mean ms | p95 ms | FPS |
|---|---|---|---|---|---|
| 1280×720 | CUDA | 960 (GPU default) | 11.8 | 15.8 | 75 |
| 1280×720 | CUDA | 640 | 10.5 | 16.7 | 84 |
| 1280×720 | CPU | 640 (CPU default) | 19.7 | 22.5 | 48 |
| 1280×720 | CPU | 960 | 29.9 | 32.7 | 32 |
| 640×480 | CUDA | 960 | 12.3 | 18.0 | 79 |
| 640×480 | CPU | 640 | 22.6 | 24.4 | 43 |

Both builds are far faster than the camera's frame rate (15 FPS is processed by default). The CPU build uses
roughly 8 cores while running, versus about 2 for the CUDA build, and at its default 640 px it finds fewer
small or distant objects. On `street_slovenska.mp4`: 60 unique people on CPU at 640 px versus 86 on the GPU at 960 px.
Set *Inference size* to 960 in the CPU build if accuracy matters more than CPU load.

## 9. Validation results (2026-10-23)

Machine: Windows 11 (build 26300), Python 3.14.7, RTX 5060 Laptop GPU (driver 616.56), built-in
"Integrated Camera". Everything below ran natively on Windows, not in WSL.

| Check | Result |
|---|---|
| `setup.ps1` | `.venv-win` created. `torch 2.11.0+cu128`, CUDA available on the RTX 5060 |
| Camera discovery | "Integrated Camera" (#0) via DirectShow in 1.5–2.1 s. "OBS Virtual Camera" correctly excluded (no frames) |
| DirectShow probe | 640×480, 1280×720 and 1920×1080 all delivered at the requested size, at about 26–27 FPS (open about 1.7 s) |
| Media Foundation | Not available in the pinned OpenCV wheel (see section 5) |
| `camera_check.py --seconds 30` (1280×720, CUDA) | **pass**. All 13 checks passed: capture about 30 FPS, about 10.5 FPS processed, 11–20 ms latency. Person detected and tracked. 2 line crossings saved and exported. Recording 1280×720 / 15 FPS, 429 frames, 28.6 s, all decodable. DB, JSON and CSV consistent |
| `pytest` (whole suite) | **180 passed**, 5 skipped (the opt-in camera tests). With `ATCS_TEST_CAMERA=1`: **185 passed** (after the counting changes; it was 165 before them) |
| `ATCS_TEST_CAMERA=1 pytest tests\test_camera_hw.py` | **5 passed** on the Integrated Camera |
| `start.cmd --video … --start --record --quit-after 20000` | GUI launched, camera listed, CUDA, recording saved, exit 0 |
| `build.ps1` | First build 4.48 GB (CUDA). Trimmed CUDA build **3.82 GB**, CPU-only build **0.62 GB** |
| Trimmed CUDA `.exe`, full `street_slovenska.mp4` | counts identical to the development environment (unique 86/21/43/2/1, 2 bus crossings), CUDA, exit 0 |
| CPU `.exe`, full `street_slovenska.mp4` | counts identical to the CPU environment (unique 60/11/33/6/1, 1 bus crossing), CPU, exit 0 |
| Both `.exe`, `--camera 0 --start --record` (45 s) | person detected and tracked, 0 false crossings, recording fully decodable (534 / 590 frames), DB integrity ok, exports consistent, exit 0 |
| `.exe --camera 0 --start --record` (run from `%TEMP%`) | Camera opened via DirectShow, session `completed`, recording 214 frames / 14.3 s, all decodable. DB integrity ok, exports consistent, exit 0. No person was in view, so this run had 0 detections |
| `.exe --video street_slovenska.mp4 --start --record` | 118 unique objects detected on CUDA, recording 537 frames / 35.8 s, all decodable, exit 0 |

Notes:
* **Crossings:** the two webcam crossings in the first run came from one track straddling the centre line
  (opposite directions, 94 ms apart). This was investigated and fixed; see
  [counting_accuracy.md](counting_accuracy.md). To validate counting live, walk across the line several
  times during `camera_check.py --event-log all` and compare the result with your own count.
* **Processing rate:** with the default *Max processed FPS* of 15 and a 30 FPS camera, about 10 FPS
  is processed, because frames arrive every 33 ms and the throttle accepts one only after a full
  66.7 ms. The same happens on Linux. Inference itself takes about 11 ms.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `running scripts is disabled on this system` | Use `start.cmd`, or `powershell -ExecutionPolicy Bypass -File ...` as shown above. |
| "No camera detected" | Check the camera privacy settings, close other apps that use the camera, then try `$env:ATCS_CAMERA_BACKEND="msmf"`. |
| Camera found but "delivers no frames" | Usually the privacy toggle for desktop apps, or another app is holding the camera. |
| Generic names such as "Camera 0" | `pygrabber` is missing or COM failed. Re-run `setup.ps1`. Capture still works. |
| `torch.cuda.is_available()` is False | Update the NVIDIA driver (R570 or newer for CUDA 12.8), then re-run `setup.ps1` (it reinstalls from `cu128`). |
| `DLL load failed` importing torch | Install the latest *Microsoft Visual C++ Redistributable (x64)*. |
| Symlink errors in tests | Not expected: the test fixture falls back to hard links without Developer Mode. |
| Want Media Foundation | Not in the pinned OpenCV wheel (section 5). Use `ATCS_CAMERA_BACKEND=dshow` (the default) |
