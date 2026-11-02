; =============================================================================
;  Gela PM System - Inno Setup Installer
;  Gela Dairy Co. | Developer: Mehrshad Ziari
;
;  BUILD INPUT
;    dist\PM_System\PM_System.exe
;    dist\PM_System\_internal\*
;
;  DEPLOYMENT MODEL
;    - Windows x64-compatible client PCs
;    - Application itself is fully bundled; no Python installation required
;    - Clients do NOT need Internet access
;    - Clients DO need access to the company SQL Server over the LAN:
;        192.168.0.1:1433
; =============================================================================

#define AppName      "PM System"
; Version: pass /DAppVersion=x.y.z to ISCC (build_release.bat does this from
; version.txt). The default below is used when compiling from the IDE.
#ifndef AppVersion
  #define AppVersion "2.4.0"
#endif
#define AppPublisher "Gela Dairy Co."
#define AppExeName   "PM_System.exe"
#define AppDBServer  "192.168.0.1"

; Update share account, built into the installer so nobody has to type it.
; release.py passes the password with /DSharePass=... from the local file
; updater_account.local (never stored in the source code).
#ifndef SharePath
  #define SharePath "\\192.168.0.1\PM_System_Updates"
#endif
#ifndef ShareUser
  #define ShareUser "GELAAMOL\pm_update_reader"
#endif
#ifndef SharePass
  #define SharePass ""
#endif
#define SharePassQ StringChange(SharePass, "'", "''")
#define ShareUserQ StringChange(ShareUser, "'", "''")
#define SharePathQ StringChange(SharePath, "'", "''")
#define BuildDate    GetDateTimeString("yyyy-mm-dd", "-", ":")

[Setup]
AppId                           = {{A3F2C1D4-7B8E-4F9A-BC3D-E1F2A3B4C5D6}
AppName                         = {#AppName}
AppVersion                      = {#AppVersion}
AppVerName                      = {#AppName} v{#AppVersion}
AppPublisher                    = {#AppPublisher}
AppCopyright                    = Copyright (C) 2026 {#AppPublisher}

; The application is built from 64-bit Python and is packaged as an x64 EXE.
DefaultDirName                  = {autopf}\PM_System
DefaultGroupName                = {#AppName}
DisableProgramGroupPage         = yes
UsePreviousAppDir               = yes
; Prevents two installers (manual + scheduled updater) from running at once.
SetupMutex                      = GelaPMSystemSetupMutex

; Installer output
OutputDir                       = installer_output
OutputBaseFilename              = PM_System_Setup_v{#AppVersion}
SetupIconFile                   = gela-logo.ico
UninstallDisplayIcon            = {app}\{#AppExeName}
UninstallDisplayName            = {#AppName} v{#AppVersion}

; Modern installer UI
WizardStyle                     = modern
WizardResizable                 = no
DisableWelcomePage              = no
DisableReadyPage                = no
DisableFinishedPage             = no
ShowLanguageDialog              = no

; Compression
Compression                     = lzma2/ultra64
SolidCompression                = yes
LZMAUseSeparateProcess          = yes

; Installation privileges / architecture
PrivilegesRequired              = admin
ArchitecturesAllowed            = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible

; IMPORTANT:
; Python 3.13 supports Windows 8.1 and newer. Therefore Windows 7
; (6.1) must not be advertised as a supported client OS.
; Windows 8.1 = 6.3.
MinVersion                      = 6.3

; Upgrade / application shutdown behavior
CloseApplications               = yes
; The SYSTEM updater gives users a 2-minute countdown first; Setup then closes
; any PM_System.exe still running. updater\relaunch.cmd (started by the app
; as the user) re-opens the application after Setup finishes.
CloseApplicationsFilter         = *{#AppExeName}
RestartApplications             = no
ChangesEnvironment              = no

; Uninstaller
CreateUninstallRegKey           = yes
Uninstallable                   = yes

; Keep installer file version aligned with AppVersion.
VersionInfoVersion              = {#AppVersion}
VersionInfoCompany              = {#AppPublisher}
VersionInfoDescription          = {#AppName} Installer v{#AppVersion}
VersionInfoProductName          = {#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to {#AppName} Setup
WelcomeLabel2=This will install {#AppName} v{#AppVersion} on your computer.%n%nDeveloped for {#AppPublisher}.%n%nIMPORTANT: This application is offline-capable and does not require Internet access, but this PC must be connected to the company LAN and able to reach the SQL Server ({#AppDBServer}) before using the application.%n%nClick Next to continue.
FinishedLabel=Setup has finished installing {#AppName} on your computer.%n%nBefore launching, ensure this PC is connected to the company LAN and can reach the SQL Server ({#AppDBServer}).

[CustomMessages]
english.InstallingVCRedist=Installing Visual C++ Redistributable (required runtime)...
english.LaunchAfterInstall=Launch {#AppName} now

[Files]
; -----------------------------------------------------------------------------
; PyInstaller onedir output
; -----------------------------------------------------------------------------
Source: "dist\PM_System\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\PM_System\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; -----------------------------------------------------------------------------
; Optional Visual C++ runtime installer.
; The application is already packaged, but the redistributable is retained as
; an offline safety net for native Python/Pillow/matplotlib extensions.
; -----------------------------------------------------------------------------
Source: "VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

; Build/version marker (read by the app for the "updated" notice)
Source: "version.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; -----------------------------------------------------------------------------
; Silent updater (scheduled task running as SYSTEM). See updater\README.
; -----------------------------------------------------------------------------
Source: "updater\PMUpdater.ps1";    DestDir: "{app}\updater"; Flags: ignoreversion
Source: "updater\install_task.ps1"; DestDir: "{app}\updater"; Flags: ignoreversion
Source: "updater\relaunch.cmd";     DestDir: "{app}\updater"; Flags: ignoreversion
Source: "updater\selftest.ps1";    DestDir: "{app}\updater"; Flags: ignoreversion
Source: "updater\test_autoupdate.ps1"; DestDir: "{app}\updater"; Flags: ignoreversion
Source: "updater\test_autoupdate.cmd"; DestDir: "{app}\updater"; Flags: ignoreversion
Source: "updater\update_progress.ps1"; DestDir: "{app}\updater"; Flags: ignoreversion

; -----------------------------------------------------------------------------
; User documentation
; -----------------------------------------------------------------------------
Source: "PM_System_Manual.pdf"; DestDir: "{app}\docs"; DestName: "User_Manual.pdf"; Flags: ignoreversion skipifsourcedoesntexist
Source: "PM_System_Manual.pdf"; DestDir: "{commondesktop}"; DestName: "PM_System_Manual.pdf"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\_internal\gela-logo.ico"; Comment: "Launch PM System - Gela Dairy Co."
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\_internal\gela-logo.ico"; Comment: "Launch PM System"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Full test of the automatic updates on this PC (asks for administrator rights).
Name: "{group}\Test automatic updates"; Filename: "{app}\updater\test_autoupdate.cmd"; WorkingDir: "{app}\updater"; Comment: "Check that PM System updates itself automatically on this PC"

[Run]
; The bundled redist is optional. If it is absent, Inno skips this entry.
; No Internet download is attempted.
; IMPORTANT: skipifsourcedoesntexist belongs to [Files]; [Run] uses
; skipifdoesntexist to avoid an error if the temporary EXE is absent.
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "{cm:InstallingVCRedist}"; Check: VCRedistNeedsInstall; Flags: skipifdoesntexist runhidden waituntilterminated

; Register / refresh the SYSTEM updater task and its ProgramData folder.
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\updater\install_task.ps1"" -AppDir ""{app}"" {code:UpdaterConfigArg}"; StatusMsg: "Configuring automatic updates..."; BeforeInstall: WriteUpdaterConfig; Flags: runhidden waituntilterminated

; FULL test of the automatic updates after EVERY install (first install, manual
; reinstall and silent automatic updates). It runs as the SYSTEM account with
; the same code as a real update: settings, scheduled task, status folder
; rights, share login, release manifest, download of the whole installer into
; the cache with SHA-256 check, version compare. Interactive installs show the
; result on the last page (and a message box if it failed); the result is also
; kept in ProgramData for the app (it warns users) and in updater.log.
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\updater\selftest.ps1"" -AppDir ""{app}"" -ResultFile ""{tmp}\update_check.txt"""; StatusMsg: "Testing automatic updates (up to 4 minutes)..."; Flags: runhidden waituntilterminated

; Launch is explicitly unchecked so the installer never forces an immediate
; first run against a client that may not yet be connected to the LAN.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchAfterInstall}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden skipifdoesntexist; RunOnceId: "KillApp"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""\GelaPM\PM System Updater"" /F"; Flags: runhidden skipifdoesntexist; RunOnceId: "DelUpdaterTask"

[UninstallDelete]
; Only remove known generated cache/document artifacts explicitly.
; Inno automatically removes files installed through [Files].
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
Type: filesandordirs; Name: "{app}\_internal\PIL\__pycache__"
Type: filesandordirs; Name: "{app}\_internal\matplotlib\__pycache__"

[Registry]
; Installer metadata is kept for local diagnostics / inventory.
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "DBServer"; ValueData: "{#AppDBServer}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "BuildDate"; ValueData: "{#BuildDate}"; Flags: uninsdeletekey

; Auto-start for EVERY Windows user at logon (machine-wide Run key).
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue
; v2.3 wrote the entry only for the user who ran Setup; remove that copy so
; this user does not get two windows at logon.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#AppName}"; ValueType: none; Flags: deletevalue

[Code]
var
  ShareQueryPage: TInputQueryWizardPage;

function UpdaterConfigPath: String;
begin
  Result := ExpandConstant('{commonappdata}\GelaDairy\PMSystem\updater\config.json');
end;

function BuiltInPassword: String;
begin
  Result := '{#SharePassQ}';
end;

function HasBuiltInAccount: Boolean;
begin
  Result := BuiltInPassword <> '';
end;

function JsonEscape(const S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure InitializeWizard;
begin
  { Asked only on the first interactive install on a PC. Silent upgrades keep
    the existing config. /SHAREUSER= /SHAREPASS= /SHAREPATH= work for silent
    first installs. }
  ShareQueryPage := CreateInputQueryPage(wpSelectDir,
    'Automatic updates',
    'Read-only account for the update share',
    'PM System installs new versions automatically from the company update share. ' +
    'Enter the Windows account of the UPDATE FOLDER on the server (pm_update_reader). ' +
    'This is NOT the database login (pm_app) - the database login is built into the program.');
  ShareQueryPage.Add('Update share:', False);
  ShareQueryPage.Add('User name:', False);
  ShareQueryPage.Add('Password:', True);
  ShareQueryPage.Values[0] := ExpandConstant('{param:SHAREPATH|}');
  if ShareQueryPage.Values[0] = '' then ShareQueryPage.Values[0] := '{#SharePathQ}';
  ShareQueryPage.Values[1] := ExpandConstant('{param:SHAREUSER|}');
  if ShareQueryPage.Values[1] = '' then ShareQueryPage.Values[1] := '{#ShareUserQ}';
  ShareQueryPage.Values[2] := ExpandConstant('{param:SHAREPASS|}');
  if ShareQueryPage.Values[2] = '' then ShareQueryPage.Values[2] := BuiltInPassword;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { The account is built in: the page is never needed. }
  Result := (PageID = ShareQueryPage.ID) and (HasBuiltInAccount or FileExists(UpdaterConfigPath));
end;

function UpdaterConfigWanted: Boolean;
begin
  { New config only on a first install, or when given on the command line. }
  { Always refresh it when the account is built in, so a PC that was set up
    with a wrong account repairs itself with the next install. }
  Result := HasBuiltInAccount or (not FileExists(UpdaterConfigPath)) or
            (ExpandConstant('{param:SHAREUSER|}') <> '');
end;

function UpdaterTempConfig: String;
begin
  Result := ExpandConstant('{tmp}\updater_config.json');
end;

procedure WriteUpdaterConfig;
var
  Lines: TArrayOfString;
begin
  if not UpdaterConfigWanted then
    Exit;
  SetArrayLength(Lines, 1);
  Lines[0] := '{ "share": "' + JsonEscape(Trim(ShareQueryPage.Values[0])) + '", ' +
              '"user": "' + JsonEscape(Trim(ShareQueryPage.Values[1])) + '", ' +
              '"password": "' + JsonEscape(ShareQueryPage.Values[2]) + '", ' +
              '"grace_seconds": 120, "enabled": true }';
  SaveStringsToUTF8File(UpdaterTempConfig, Lines, False);
end;

function UpdaterConfigArg(Param: String): String;
begin
  if UpdaterConfigWanted then
    Result := '-ConfigFile "' + UpdaterTempConfig + '"'
  else
    Result := '';
end;

function VCRedistNeedsInstall: Boolean;
var
  Installed: Cardinal;
begin
  Result := True;

  { x64 installer only. }
  if not IsWin64 then
  begin
    Result := False;
    Exit;
  end;

  { The current v14 redistributable keeps using the VisualStudio\14.0\VC\Runtimes\x64 key. }
  if RegQueryDWordValue(
       HKLM,
       'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
       'Installed',
       Installed) then
  begin
    if Installed = 1 then
      Result := False;
  end;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  { Make sure an older copy is not holding files under _internal. }
  Exec(
    ExpandConstant('{sys}\taskkill.exe'),
    '/f /im {#AppExeName}',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );

  Sleep(800);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  OldInternal: String;
begin
  if CurStep = ssInstall then
  begin
    { PyInstaller onedir upgrades can otherwise leave DLLs/modules from an
      older build. The application does not store database records in _internal,
      so replacing the packaged runtime tree is intentional. }
    OldInternal := ExpandConstant('{app}\_internal');
    if DirExists(OldInternal) then
      DelTree(OldInternal, True, True, True);
  end;
end;

procedure AddFinishedText(const S: String);
begin
  WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 + S;
end;

{ Shows the result of the FULL automatic-update test (selftest.ps1, run as
  SYSTEM by the [Run] section). File format: first line "OK|summary",
  "WARN|..." or "FAIL|...", then one "- [OK|WARN|FAIL] ..." line per check. }
procedure CurPageChanged(CurPageID: Integer);
var
  Lines: TArrayOfString;
  I, P, N: Integer;
  Head, State, Summary, Problems, LastCheck: String;
begin
  if CurPageID <> wpFinished then
    Exit;
  if (not LoadStringsFromFile(ExpandConstant('{tmp}\update_check.txt'), Lines)) or
     (GetArrayLength(Lines) = 0) then
  begin
    AddFinishedText('Automatic updates: NOT TESTED' + #13#10 +
      'The automatic-update test gave no result. Run this installer again.');
    Exit;
  end;
  N := GetArrayLength(Lines);
  Head := Trim(Lines[0]);
  P := Pos('|', Head);
  if P > 0 then
  begin
    State := Copy(Head, 1, P - 1);
    Summary := Copy(Head, P + 1, Length(Head));
  end
  else
  begin
    State := 'FAIL';
    Summary := Head;
  end;
  { tolerate a byte-order mark in front of the state word }
  if Pos('FAIL', State) > 0 then
    State := 'FAIL'
  else if Pos('WARN', State) > 0 then
    State := 'WARN'
  else if Pos('OK', State) > 0 then
    State := 'OK'
  else
    State := 'FAIL';
  Problems := '';
  LastCheck := '';
  for I := 1 to N - 1 do
  begin
    if (Pos('[FAIL]', Lines[I]) > 0) or (Pos('[WARN]', Lines[I]) > 0) then
      Problems := Problems + #13#10 + Trim(Lines[I]);
    if Trim(Lines[I]) <> '' then
      LastCheck := Trim(Lines[I]);
  end;
  if Problems = '' then
    Problems := #13#10 + Summary;
  if State = 'OK' then
  begin
    if LastCheck <> '' then
      AddFinishedText('Automatic updates: OK - fully tested' + #13#10 + Summary + #13#10 + LastCheck)
    else
      AddFinishedText('Automatic updates: OK - fully tested' + #13#10 + Summary);
  end
  else if State = 'WARN' then
    AddFinishedText('Automatic updates: work, but could not be fully tested' + Problems)
  else
  begin
    AddFinishedText('Automatic updates: NOT WORKING' + Problems);
    MsgBox('PM System is installed, but automatic updates do NOT work on this PC:' + #13#10 +
      Problems + #13#10#13#10 +
      'The program itself works. Fix the problem and run this installer again.' + #13#10 +
      'To test again later: Start menu > PM System > Test automatic updates.',
      mbError, MB_OK);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := MsgBox(
    'Are you sure you want to uninstall {#AppName}?' + #13#10 + #13#10 +
    'Your database on the SQL Server ({#AppDBServer}) will NOT be removed.' + #13#10 +
    'All maintenance records remain safe on the server.' + #13#10 + #13#10 +
    'Only this client installation will be removed.',
    mbConfirmation,
    MB_YESNO
  ) = IDYES;
end;
