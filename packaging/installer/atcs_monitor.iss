; Inno Setup script for the ATCS Monitor Windows installer.
; Build with scripts\build_installer.ps1 (it passes the defines below), e.g.
;   powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1              CPU-only (default)
;   powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 -Flavor cuda NVIDIA GPU build
;
; The installed program keeps its writable data (database, settings, logs, recordings,
; exports, downloaded models) in %LOCALAPPDATA%\ATCS Monitor - see app/paths.py. The
; uninstaller removes the program only; that folder is never deleted.

#ifndef Flavor
  #define Flavor "cpu"
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SrcDir
  #error SrcDir (the PyInstaller output folder) must be defined
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist\installer"
#endif
#if Flavor == "cuda"
  #define FlavorLabel "NVIDIA CUDA"
  #define FlavorSuffix "CUDA"
#else
  #define FlavorLabel "CPU"
  #define FlavorSuffix "CPU"
#endif
#define AppName "ATCS Monitor"
#define AppExe "atcs-monitor.exe"
#define AppUserModelID "ATCSMonitor.Desktop"

[Setup]
; One AppId for both flavours: installing one replaces the other.
AppId={{D635F925-B97B-4831-A1CE-387D2AA7F872}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion} ({#FlavorLabel})
AppPublisher={#AppName}
AppComments=Detects, tracks, counts and records people and vehicles from a camera or video file. Runs locally.
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup ({#FlavorLabel})
; Per-user install without administrator rights by default ({autopf} becomes
; %LOCALAPPDATA%\Programs); the wizard also offers an all-users install.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=ATCS-Monitor-{#AppVersion}-Setup-{#FlavorSuffix}
SetupIconFile=..\..\app\resources\atcs_monitor.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
; A running ATCS Monitor is asked to close by the [Code] below (it finishes any
; recording first); the Restart Manager is not relied on.
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Remove the previous program files first: PyTorch loads every DLL in its folder, so
; leftovers from the other flavour (CUDA <-> CPU) must not stay behind. User data is
; not in {app} and is not touched.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; data, recordings and exports are runtime folders of the portable build (they may
; hold someone's sessions and videos) and are never packaged.
Source: "{#SrcDir}\*"; DestDir: "{app}"; Excludes: "\data,\recordings,\exports"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installed.marker"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"; Comment: "Detect, track, count and record people and vehicles"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"; Comment: "Detect, track, count and record people and vehicles"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  { Shared with app/main.py: the app holds the mutex while it runs and closes
    itself normally (finishing any recording) when the event is set. }
  AppRunningMutex = 'ATCSMonitor.Running';
  AppCloseEvent = 'ATCSMonitor.CloseRequest';
  EVENT_MODIFY_STATE = $0002;

function OpenEventW(Access: DWORD; Inherit: BOOL; Name: String): THandle;
  external 'OpenEventW@kernel32.dll stdcall';
function SetEvent(Handle: THandle): BOOL;
  external 'SetEvent@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): BOOL;
  external 'CloseHandle@kernel32.dll stdcall';

{ Ask a running ATCS Monitor to close and wait up to 60 s for it to exit. }
function CloseRunningApp(): Boolean;
var
  Event: THandle;
  I: Integer;
begin
  Result := True;
  if not CheckForMutexes(AppRunningMutex) then
    Exit;
  Log('ATCS Monitor is running; asking it to close');
  Event := OpenEventW(EVENT_MODIFY_STATE, False, AppCloseEvent);
  if Event <> 0 then
  begin
    SetEvent(Event);
    CloseHandle(Event);
  end;
  I := 0;
  while CheckForMutexes(AppRunningMutex) and (I < 120) do
  begin
    Sleep(500);
    I := I + 1;
  end;
  Result := not CheckForMutexes(AppRunningMutex);
  if Result then
    Sleep(1000);  { let the process release its files }
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not CloseRunningApp() then
    Result := '{#AppName} is still running. Close it, then run Setup again.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  while not CloseRunningApp() do
  begin
    if UninstallSilent then
    begin
      Log('ATCS Monitor is still running; uninstall cancelled');
      Result := False;
      Exit;
    end;
    if MsgBox('{#AppName} is still running. Close it, then click OK to continue.', mbError, MB_OKCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    MsgBox('{#AppName} has been removed.' + #13#10#13#10 +
           'Your recordings, session history, exports and settings were kept in:' + #13#10 +
           ExpandConstant('{localappdata}') + '\{#AppName}' + #13#10#13#10 +
           'Delete that folder yourself if you no longer need them.', mbInformation, MB_OK);
end;
