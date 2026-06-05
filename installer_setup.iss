; Inno Setup Script for IDM Ultimate Pro
; Built by Antigravity AI for Jaber0the0great

[Setup]
AppId={{D8F9A6C2-3B47-4921-99A1-A1E4FF4B8C1D}
AppName=IDM Ultimate Pro
AppVersion=1.3
AppPublisher=Jaber mohamed
AppPublisherURL=https://github.com/Jaber0the0great/idm-ultimate-pro
AppSupportURL=https://github.com/Jaber0the0great/idm-ultimate-pro/issues
AppUpdatesURL=https://github.com/Jaber0the0great/idm-ultimate-pro/releases
DefaultDirName={autopf}\IDM Ultimate Pro
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=IDM_Ultimate_Pro_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
ShowLanguageDialog=yes
VersionInfoVersion=1.3.0.0
VersionInfoCompany=Jaber mohamed
VersionInfoDescription=IDM Ultimate Pro Installer
VersionInfoTextVersion=1.3



[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"


[Files]
Source: "dist\IDM_Ultimate_Pro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme


[Icons]
Name: "{autoprograms}\IDM Ultimate Pro"; Filename: "{app}\IDM_Ultimate_Pro.exe"
Name: "{userdesktop}\IDM Ultimate Pro"; Filename: "{app}\IDM_Ultimate_Pro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\IDM_Ultimate_Pro.exe"; Description: "{cm:LaunchProgram,IDM Ultimate Pro}"; Flags: nowait postinstall skipifsilent
