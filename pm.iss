[Setup]
AppName=PM System
AppVersion=1.0.0
AppPublisher=Your Company
DefaultDirName={pf}\PM_System
DefaultGroupName=PM System
UninstallDisplayIcon={app}\PM_System.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.
OutputBaseFilename=PM_System_Setup
SetupIconFile=logo.ico
PrivilegesRequired=admin
DisableDirPage=no

[Files]
Source: "dist\PM_System\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PM System"; Filename: "{app}\PM_System.exe"; IconFilename: "{app}\logo.ico"
Name: "{group}\Uninstall PM System"; Filename: "{uninstallexe}"
Name: "{commondesktop}\PM System"; Filename: "{app}\PM_System.exe"; IconFilename: "{app}\logo.ico"

[Run]
Filename: "{app}\PM_System.exe"; Description: "Launch PM System"; Flags: postinstall nowait