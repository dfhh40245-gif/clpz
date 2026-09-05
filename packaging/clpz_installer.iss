; CLPZ Windows installer — Inno Setup 6
; Build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\clpz_installer.iss
; Produces: packaging\out\ClipForge-1.0.0-Windows-x64.exe

#define AppName "CLPZ"
#define AppVersion "1.0.0"
#define AppPublisher "CLPZ"
#define AppExe "CLPZ.exe"

[Setup]
AppId={{7C1B3812-9A4E-4E7D-8B31-CLPZDESKTOP1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\CLPZ
DefaultGroupName=CLPZ
DisableProgramGroupPage=yes
OutputDir=out
OutputBaseFilename=ClipForge-{#AppVersion}-Windows-x64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExe}
; user data (data\ = accounts/credits/jobs) is preserved on uninstall
UninstallFilesDir={app}\unins

[Files]
; everything from the assembled package except user data dirs
Source: "out\CLPZ\CLPZ.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "out\CLPZ\clpz_server\*"; DestDir: "{app}\clpz_server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "out\CLPZ\bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "out\CLPZ\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "out\CLPZ\frontend-app-dist\*"; DestDir: "{app}\frontend-app-dist"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "out\CLPZ\models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CLPZ"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall CLPZ"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CLPZ"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; nothing: data\ (accounts, credits, jobs, clips) intentionally preserved
