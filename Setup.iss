; =============================================================================
;  PM System - Inno Setup Script
;  Gela Dairy Co. | Developer: Mehrshad Ziadri
;  dist\PM_System\PM_System.exe + dist\PM_System\_internal\*
;  Client PCs are OFFLINE
; =============================================================================

#define AppName      "PM System"
#define AppVersion   "1.0.2"
#define AppPublisher "Gela Dairy Co."
#define AppExeName   "PM_System.exe"
#define AppDBServer  "192.168.0.1"
#define BuildDate    "20/5/2026"

[Setup]
AppId                           = {{A3F2C1D4-7B8E-4F9A-BC3D-E1F2A3B4C5D6}
AppName                         = {#AppName}
AppVersion                      = {#AppVersion}
AppVerName                      = {#AppName} v{#AppVersion}
AppPublisher                    = {#AppPublisher}
AppCopyright                    = Copyright (C) 2026 {#AppPublisher}
DefaultDirName                  = {autopf}\PM_System
DefaultGroupName                = {#AppName}
DisableProgramGroupPage         = yes
OutputDir                       = installer_output
OutputBaseFilename              = PM_System_Setup_v{#AppVersion}
SetupIconFile                   = gela-logo.ico
UninstallDisplayIcon            = {app}\{#AppExeName}
UninstallDisplayName            = {#AppName} v{#AppVersion}
WizardStyle                     = modern
WizardResizable                 = no
Compression                     = lzma2/ultra64
SolidCompression                = yes
LZMAUseSeparateProcess          = yes
PrivilegesRequired              = admin
ArchitecturesAllowed            = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible
MinVersion                      = 6.1            
CloseApplications               = yes
CloseApplicationsFilter         = *{#AppExeName}
RestartApplications             = no
ChangesEnvironment              = no
DisableWelcomePage              = no
DisableReadyPage                = no
DisableFinishedPage             = no
ShowLanguageDialog              = no
UsePreviousAppDir               = yes
CreateUninstallRegKey           = yes
Uninstallable                   = yes
VersionInfoVersion              = 1.0.0.0
VersionInfoCompany              = {#AppPublisher}
VersionInfoDescription          = {#AppName} Installer
VersionInfoProductName          = {#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to {#AppName} Setup
WelcomeLabel2=This will install {#AppName} v{#AppVersion} on your computer.%n%nDeveloped for {#AppPublisher}.%n%nIMPORTANT: This PC must be connected to the company network ({#AppDBServer}) before using the application.%n%nClick Next to continue.
FinishedLabel=Setup has finished installing {#AppName} on your computer.%n%nEnsure this PC is connected to the company LAN (server: {#AppDBServer}) before launching.

[CustomMessages]
english.InstallingVCRedist=Installing Visual C++ Redistributable (required)...
english.LaunchAfterInstall=Launch {#AppName} now

[Files]
Source: "dist\PM_System\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\PM_System\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist
Source: "version.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; ── User Manual PDF ─────────────────────────────────────────────────────
Source: "PM_System_Manual.pdf"; DestDir: "{app}\docs"; DestName: "User_Manual.pdf"; Flags: ignoreversion skipifsourcedoesntexist
Source: "PM_System_Manual.pdf"; DestDir: "{commondesktop}"; DestName: "PM_System_Manual.pdf"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\_internal\gela-logo.ico"; Comment: "Launch PM System - Gela Dairy Co."
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\_internal\gela-logo.ico"; Comment: "Launch PM System"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "{cm:InstallingVCRedist}"; Check: VCRedistNeedsInstall; Flags: skipifdoesntexist runhidden waituntilterminated
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchAfterInstall}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden skipifdoesntexist; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
Type: filesandordirs; Name: "{app}\_internal\PIL\__pycache__"
Type: filesandordirs; Name: "{app}\_internal\matplotlib\__pycache__"
Type: files; Name: "{commondesktop}\PM_System_Manual.pdf"

[Registry]
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "DBServer"; ValueData: "{#AppDBServer}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "BuildDate"; ValueData: "{#BuildDate}"; Flags: uninsdeletekey

; Auto‑start with Windows for the current user
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"""; \
    Flags: uninsdeletevalue

[Code]
function VCRedistNeedsInstall: Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
    if Installed = 1 then
      Result := False;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  Exec('taskkill.exe', '/f /im {#AppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(800);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  OldInternal: String;
begin
  if CurStep = ssInstall then
  begin
    OldInternal := ExpandConstant('{app}\_internal');
    if DirExists(OldInternal) then
      DelTree(OldInternal, True, True, True);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := MsgBox(
    'Are you sure you want to uninstall {#AppName}?' + #13#10 + #13#10 +
    'Your database on the SQL Server ({#AppDBServer}) will NOT be removed.' + #13#10 +
    'All maintenance records remain safe on the server.',
    mbConfirmation, MB_YESNO) = IDYES;
end;