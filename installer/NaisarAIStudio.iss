#define AppName "Naisar AI Studio"
#define AppVersion "0.1.0"
[Setup]
AppId={{A20C3135-0834-42C5-BB9A-CE9DF2A1BBA1}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\Naisar AI Studio
DefaultGroupName=Naisar AI Studio
OutputDir=..\output
OutputBaseFilename=NaisarAIStudio-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
[Files]
Source: "..\dist\NaisarAIStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\Naisar AI Studio"; Filename: "{app}\NaisarAIStudio.exe"
Name: "{autodesktop}\Naisar AI Studio"; Filename: "{app}\NaisarAIStudio.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"
[Run]
Filename: "{app}\NaisarAIStudio.exe"; Description: "Запустить Naisar AI Studio"; Flags: nowait postinstall skipifsilent
