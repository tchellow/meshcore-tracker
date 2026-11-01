; Instalador do Windows. Compile com: iscc /DVersao=0.1.0 instalador\windows.iss
; Espera o programa compilado em dist\meshcore-tracker.

#ifndef Versao
  #define Versao "0.0.0"
#endif

[Setup]
AppId={{7E2B6A61-3C6F-4C7E-9B59-5D7D3F0A9C14}
AppName=Meshcore Tracker
AppVersion={#Versao}
AppPublisher=tchellow
AppPublisherURL=https://github.com/tchellow/meshcore-tracker
AppSupportURL=https://github.com/tchellow/meshcore-tracker/issues
DefaultDirName={autopf}\Meshcore Tracker
DefaultGroupName=Meshcore Tracker
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
OutputDir=..\instalador-saida
OutputBaseFilename=MeshcoreTracker-{#Versao}-windows-x64-setup
SetupIconFile=..\assets\icone.ico
UninstallDisplayIcon={app}\meshcore-tracker.exe
UninstallDisplayName=Meshcore Tracker
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "atalho"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\meshcore-tracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Meshcore Tracker"; Filename: "{app}\meshcore-tracker.exe"
Name: "{autodesktop}\Meshcore Tracker"; Filename: "{app}\meshcore-tracker.exe"; Tasks: atalho

[Run]
Filename: "{app}\meshcore-tracker.exe"; Description: "{cm:LaunchProgram,Meshcore Tracker}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM meshcore-tracker.exe"; Flags: runhidden; RunOnceId: "EncerrarPrograma"

[Code]
// O programa roda em segundo plano, sem janela: precisa ser encerrado antes de atualizar.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM meshcore-tracker.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;
