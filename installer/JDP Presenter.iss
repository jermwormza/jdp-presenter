#define MyAppName "JDP Presenter"
#ifndef MyAppVersion
#define MyAppVersion "0.1.1"
#endif
#define MyAppPublisher "JDP"
#define MyAppExeName "JDP Presenter.exe"

[Setup]
AppId={{D87829B8-2998-482A-A378-2378543433C4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JDP Presenter
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=JDP-Presenter-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Dirs]
Name: "{commonappdata}\jdp-presenter"; Permissions: users-modify
Name: "{commonappdata}\jdp-presenter\bibles"
Name: "{commonappdata}\jdp-presenter\songs"
Name: "{commonappdata}\jdp-presenter\services"
Name: "{commonappdata}\jdp-presenter\media"
Name: "{commonappdata}\jdp-presenter\recordings"
Name: "{commonappdata}\jdp-presenter\import"

[Files]
Source: "..\dist\JDP Presenter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
	FFmpegDownloadUrl = 'https://ffmpeg.org/download.html';

var
	FFmpegPage: TWizardPage;

function IsFFmpegAvailable: Boolean;
begin
	Result := FileSearch('ffmpeg.exe', GetEnv('PATH')) <> '';
end;

procedure OpenFFmpegDownload(Sender: TObject);
var
	ErrorCode: Integer;
begin
	ShellExec('open', FFmpegDownloadUrl, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure InitializeWizard;
var
	InformationLabel: TNewStaticText;
	DownloadLink: TNewStaticText;
begin
	if IsFFmpegAvailable then
		Exit;

	FFmpegPage := CreateCustomPage(
		wpSelectDir,
		'FFmpeg Not Found',
		'Install standalone FFmpeg to enable MP3 and M4A recording conversion.'
	);

	InformationLabel := TNewStaticText.Create(FFmpegPage);
	InformationLabel.Parent := FFmpegPage.Surface;
	InformationLabel.AutoSize := False;
	InformationLabel.WordWrap := True;
	InformationLabel.SetBounds(0, 0, FFmpegPage.SurfaceWidth, 72);
	InformationLabel.Caption :=
		'JDP Presenter can record WAV files without FFmpeg. For MP3 or M4A output, ' +
		'install FFmpeg and ensure ffmpeg.exe is available on PATH. Open the official ' +
		'download page below, then restart JDP Presenter after installation.';

	DownloadLink := TNewStaticText.Create(FFmpegPage);
	DownloadLink.Parent := FFmpegPage.Surface;
	DownloadLink.Top := 88;
	DownloadLink.Caption := FFmpegDownloadUrl;
	DownloadLink.Font.Color := clBlue;
	DownloadLink.Font.Style := [fsUnderline];
	DownloadLink.Cursor := crHand;
	DownloadLink.OnClick := @OpenFFmpegDownload;
end;