; SolaSub — trinh cai dat. Mot script, hai ban:
;   ISCC.exe installer\solasub.iss              -> SolaSub_Setup_CPU.exe
;   ISCC.exe /DGPU installer\solasub.iss        -> SolaSub_Setup_GPU.exe
; Hai ban chua CUNG bo file; ban GPU chi khac o cho tai them torch CUDA
; (~2,5 GB) o buoc cuoi. Khong dong goi san CUDA vi phan lon may khong co
; card NVIDIA, dong vao thi ai cung phai tai thua 2,5 GB.

#define MyAppName      "SolaSub"
#define MyAppVersion   "1.1.0"
#define MyAppPublisher "SOLATECH"
#define MyAppExeName   "SolaSub.exe"
#define SrcDir         "..\build\SolaSub"
; Ghim dung ban torch dang dung: torchaudio 2.11.0 di kem duoc build cho
; torch 2.14.1, lay ban moi hon se loi khi import.
#define TorchPin       "torch==2.14.1"
#define CudaIndex      "https://download.pytorch.org/whl/cu126"
; --no-cache-dir: khong giu lai ban wheel 2,4 GB trong %LocalAppData%\pip\Cache
#define PipFlags       "--no-cache-dir --upgrade --force-reinstall"

#ifdef GPU
  #define Flavor    "GPU"
#else
  #define Flavor    "CPU"
#endif

[Setup]
AppId={{B7E4F1A2-9C3D-4E58-A1F6-2D8B5C0E7A41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright={#MyAppPublisher}

VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup

SetupIconFile=..\assets\solasub.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Cai PER-USER, khong can admin. Bat buoc phai vay: buoc nang cap GPU chay
; "pip install torch" ghi thang vao {app}\python\Lib\site-packages — neu cai
; vao Program Files thi pip se bi tu choi quyen ghi.
PrivilegesRequired=lowest

OutputDir=Output
OutputBaseFilename=SolaSub_Setup_{#Flavor}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

#ifdef GPU
; Trang chon thu muc nam TRUOC trang chon tac vu, nen luc bao dung luong Inno
; chua biet nguoi dung co tick CUDA hay khong -> bao luon muc da nhat.
; torch CUDA chiem 4.050 MB, thay cho ban CPU 506 MB => doi thêm ~3.550 MB.
; Con can them ~2,4 GB tam luc pip giai nen (da --no-cache-dir nen khong giu lai).
ExtraDiskSpaceRequired=3722444800
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo lối tắt ngoài màn hình"; GroupDescription: "Lối tắt:"
#ifdef GPU
; Van de tick duoc: nguoi dung tai nham bản GPU mà máy không có NVIDIA thi
; bo tick la xong, khong phai tai lai bo cai khac.
Name: "cuda"; Description: "Tải gói tăng tốc CUDA ngay bây giờ — tải ~2,4 GB, chiếm thêm ~3,5 GB đĩa"; GroupDescription: "Tăng tốc GPU (cần card NVIDIA + mạng):"
#endif

[Files]
; KHONG loai __pycache__: build.ps1 da bien dich san .pyc (Python nhung khong tu ghi .pyc ->
; thieu thi moi lan mo app phai bien dich lai ~1.000 file, cham vai giay).
#ifdef GPU
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.pdb,*.log"
#else
; Ban CPU Only thi khong kem script GPU — co trong thu muc ma khong co loi tat
; chi lam nguoi dung tuong la chay duoc GPU.
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.pdb,*.log,Cai-dat-GPU.bat,Go-bo-GPU.bat"
#endif

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Gỡ {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
#ifdef GPU
; De san loi tat cho nguoi bo tick luc cai, sau nay doi y
Name: "{group}\Cài gói tăng tốc GPU (NVIDIA)"; Filename: "{app}\Cai-dat-GPU.bat"; IconFilename: "{app}\assets\solasub.ico"
Name: "{group}\Gỡ gói GPU, quay về bản CPU"; Filename: "{app}\Go-bo-GPU.bat"; IconFilename: "{app}\assets\solasub.ico"
#endif

[Run]
#ifdef GPU
; Tai torch ban CUDA o BUOC CUOI. Hien cua so console de theo doi tien do,
; vi tai 2,5 GB co the mat vai chuc phut va nguoi dung can thay no dang chay.
Filename: "{app}\python\python.exe"; \
  Parameters: "-m pip install {#PipFlags} {#TorchPin} --index-url {#CudaIndex}"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Đang tải gói tăng tốc GPU (~2,5 GB) — có thể mất vài chục phút..."; \
  Tasks: cuda; Flags: waituntilterminated
#endif

Filename: "{app}\{#MyAppExeName}"; Description: "Mở {#MyAppName} ngay"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; pip sinh them file sau khi cai; khong xoa thi thu muc {app} con sot lai
Type: filesandordirs; Name: "{app}\python\Lib\site-packages"
Type: filesandordirs; Name: "{app}\python\Scripts"
Type: filesandordirs; Name: "{app}\solasub\__pycache__"
Type: filesandordirs; Name: "{app}\solasub\ui\__pycache__"

[Code]
#ifdef GPU
var
  WarnedNoNvidia: Boolean;

// Driver NVIDIA cai vao la co nvidia-smi.exe trong System32. Khong co file do
// thi gan nhu chac chan may khong dung duoc CUDA.
function HasNvidia: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\nvidia-smi.exe'));
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpSelectTasks) and (not WarnedNoNvidia) and (not HasNvidia) then
  begin
    WarnedNoNvidia := True;
    MsgBox('Không tìm thấy driver NVIDIA trên máy này.' + #13#10#13#10 +
           'Gói tăng tốc CUDA sẽ không dùng được — bạn nên bỏ tick mục ' +
           '"Tải gói tăng tốc CUDA" để khỏi tải thừa 2,5 GB.' + #13#10#13#10 +
           'SolaSub vẫn chạy bình thường bằng CPU.',
           mbInformation, MB_OK);
  end;
end;
#endif

// Dong app dang chay truoc khi ghi de — khong thi se "Access denied".
// Chi giet pythonw.exe NAM TRONG thu muc cai: nguoi dung co the dang chay
// chuong trinh Python khac, khong duoc dung toi.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /T /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('powershell.exe',
       '-NoProfile -WindowStyle Hidden -Command "Get-Process pythonw -ErrorAction SilentlyContinue |' +
       ' Where-Object { $_.Path -like ''' + ExpandConstant('{app}') + '*'' } | Stop-Process -Force"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
  Result := '';
end;
