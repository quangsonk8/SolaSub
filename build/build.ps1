# Dung ban SolaSub di dong: Python nhung + thu vien CPU + ma nguon.
# KHONG dung PyInstaller vi ban dong bang khong cho pip install CUDA ve sau.
# Luu y: file nay phai la ASCII thuan - PowerShell 5.1 doc script khong BOM theo ANSI.

$ErrorActionPreference = "Stop"
$Build   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root    = Split-Path -Parent $Build
$Out     = "$Build\SolaSub"
$Py      = "$Out\python"
$SitePkg = "$Py\Lib\site-packages"

function Say($m) { Write-Host $m -ForegroundColor Cyan }

# --- 1. Don cho cu ---
if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Py | Out-Null

# --- 2. Bung Python nhung ---
Say "1/6  Bung Python nhung..."
Expand-Archive "$Build\py-embed.zip" -DestinationPath $Py -Force

# Mo khoa import tu site-packages (ban nhung mac dinh KHOA)
$pth = Get-ChildItem "$Py\python*._pth" | Select-Object -First 1
# Duong dan trong ._pth tinh tu thu muc chua python.exe, nen ".." la goc ban cai
# (noi co app.py va goi solasub) - thieu dong nay se ModuleNotFoundError: solasub
@"
python311.zip
.
..
Lib\site-packages

# Bat site de pip va cac goi hoat dong
import site
"@ | Set-Content $pth.FullName -Encoding ascii
New-Item -ItemType Directory -Force -Path $SitePkg | Out-Null

# --- 3. Cai pip (can cho buoc nang cap CUDA sau nay) ---
Say "2/6  Cai pip..."
if (-not (Test-Path "$Build\get-pip.py")) {
    Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile "$Build\get-pip.py" -UseBasicParsing
}
& "$Py\python.exe" "$Build\get-pip.py" --no-warn-script-location | Select-Object -Last 1

# --- 4. Chep thu vien tu venv CPU (khoi tai lai ~600 MB) ---
Say "3/6  Chep thu vien tu venv-cpu..."
$src = "$Root\venv-cpu\Lib\site-packages"
# Chi bo thu that su khong duoc import. torch 2.14 nap torchgen/sympy/networkx
# ngay tu "import torch" nen KHONG duoc bo (da thu, gay ModuleNotFoundError).
$skip = @("setuptools", "pkg_resources", "wheel", "_distutils_hack", "pip")
Get-ChildItem $src | Where-Object {
    $n = $_.Name -replace '-[\d.]+\.dist-info$', ''
    $skip -notcontains $n -and $skip -notcontains $_.Name
} | ForEach-Object {
    Copy-Item $_.FullName -Destination $SitePkg -Recurse -Force
}

# --- 5. Ma nguon + tai nguyen ---
Say "4/6  Chep ma nguon..."
Copy-Item "$Root\app.py"   $Out -Force
Copy-Item "$Root\cli.py"   $Out -Force
Copy-Item "$Root\solasub"  $Out -Recurse -Force
Copy-Item "$Root\assets"   $Out -Recurse -Force
Get-ChildItem $Out -Recurse -Include __pycache__ -Directory | Remove-Item -Recurse -Force -EA SilentlyContinue
Remove-Item "$Out\assets\solasub_src.webp" -Force -EA SilentlyContinue

# ffmpeg: whisper goi thang "ffmpeg" tu PATH, may nguoi dung khong co san
Say "5/6  Chep ffmpeg + model base..."
New-Item -ItemType Directory -Force -Path "$Out\tools", "$Out\models" | Out-Null
# Lay ffmpeg.exe tu tools\ cua du an, khong co thi lay ban dang trong PATH
$ff = if (Test-Path "$Root\tools\ffmpeg.exe") { "$Root\tools\ffmpeg.exe" }
      else { (Get-Command ffmpeg -EA SilentlyContinue).Source }
if (-not $ff) { throw "Khong tim thay ffmpeg.exe - dat vao $Root\tools\ hoac them vao PATH" }
Copy-Item $ff "$Out\tools\ffmpeg.exe" -Force
# Dong goi san base.pt de lan chay dau khong phai tai 139 MB
Copy-Item "$env:USERPROFILE\.cache\whisper\base.pt" "$Out\models\base.pt" -Force

# --- 5a. Visual C++ Runtime dat canh pythonw.exe ---
# May phat trien nao cung co san VC++ Redist trong System32 nen chay thu o nha
# luon thanh cong; may nguoi dung sach thi KHONG co -> "DLL load failed" khi
# import torch. torch\lib can msvcp140.dll ma trong goi chi PyQt6\Qt6\bin moi
# co, ma thu muc do chi vao duong tim DLL SAU khi import PyQt6.
# Thu muc chua file .exe cua tien trinh (= python\) thi LUC NAO cung duoc tim,
# nen dat o day la chac an nhat.
Say "5a/7 Chep Visual C++ Runtime..."
$qtbin = "$SitePkg\PyQt6\Qt6\bin"
$vcNames = @("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
             "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll",
             "vcruntime140.dll", "vcruntime140_1.dll", "vcruntime140_threads.dll",
             "concrt140.dll")
foreach ($n in $vcNames) {
    if (Test-Path "$qtbin\$n") { Copy-Item "$qtbin\$n" "$Py\$n" -Force }
    elseif (Test-Path "$env:WINDIR\System32\$n") { Copy-Item "$env:WINDIR\System32\$n" "$Py\$n" -Force }
    else { Write-Warning "  thieu $n" }
}
# vcomp140.dll: OpenMP runtime, numba\np\ufunc\omppool.pyd can. Khong co thi
# numba tut ve luong 'workqueue' - van chay nhung cham hon.
if (Test-Path "$env:WINDIR\System32\vcomp140.dll") {
    Copy-Item "$env:WINDIR\System32\vcomp140.dll" "$Py\vcomp140.dll" -Force
}

# --- 5b. SolaSub.exe: launcher (man hinh khoi dong + goi pythonw.exe app.py) ---
# /codepage:65001: launcher.cs co chu tieng Viet, luu UTF-8 khong BOM -> thieu co nay csc doc theo ANSI.
Say "5b/7 Build SolaSub.exe..."
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:winexe /optimize+ /platform:anycpu /codepage:65001 /win32icon:"$Root\assets\solasub.ico" `
       /reference:System.Windows.Forms.dll /reference:System.Drawing.dll `
       /out:"$Out\SolaSub.exe" "$Build\launcher.cs"
if ($LASTEXITCODE -ne 0) { throw "csc loi khi build launcher" }
if (-not (Test-Path "$Out\SolaSub.exe")) { throw "Build launcher that bai" }

# --- 6. Cat bot thu khong dung (~120 MB) ---
# Chi cat thu da kiem chung la khong anh huong: app chi dung QtWidgets +
# QtMultimedia (phat audio), khong dung QML/Quick/3D; torch khong can header C++.
Say "6/7  Cat bot thu khong dung..."
$qt = "$SitePkg\PyQt6\Qt6"
Remove-Item "$qt\qml" -Recurse -Force -EA SilentlyContinue
# Plugin mo coi: tro vao Qt6Quick/Qml/3D/Pdf da bi cat o tren. De lai thi Qt
# van quet va nap thu tung cai -> loi im lang + cham luc khoi dong.
# sqldrivers thi doi DLL cua Oracle/Postgres/Firebird, may nao cung thieu.
Remove-Item "$qt\plugins\qmltooling", "$qt\plugins\designer", "$qt\plugins\qmllint", `
            "$qt\plugins\sqldrivers", "$qt\plugins\assetimporters", "$qt\plugins\sceneparsers", `
            "$qt\plugins\geometryloaders", "$qt\plugins\renderers", "$qt\plugins\renderplugins", `
            "$qt\plugins\scxmldatamodel", "$qt\plugins\webview", "$qt\plugins\qmlls" `
            -Recurse -Force -EA SilentlyContinue
Remove-Item "$qt\plugins\imageformats\qpdf.dll" -Force -EA SilentlyContinue
Get-ChildItem "$qt\bin" -File |
    Where-Object { $_.Name -match '^Qt6(Quick|Qml|Labs|Designer|ShaderTools|Spatial|Pdf|3D|WebEngine|WebView|Scxml|Bluetooth|Nfc|SerialPort|Sql|Test|Help|Charts|DataVisualization|Sensors|TextToSpeech|RemoteObjects|StateMachine)' } |
    Remove-Item -Force -EA SilentlyContinue
Get-ChildItem "$SitePkg\PyQt6" -Filter "*.pyd" |
    Where-Object { $_.BaseName -notmatch '^(QtCore|QtGui|QtWidgets|QtMultimedia|QtNetwork|sip)' } |
    Remove-Item -Force -EA SilentlyContinue
Remove-Item "$SitePkg\torch\include", "$SitePkg\torch\test" -Recurse -Force -EA SilentlyContinue

# --- 6b. Bien dich san .pyc ---
# Python nhung chay theo ._pth thi KHONG BAO GIO ghi .pyc (sys.dont_write_bytecode = True) -> moi lan mo app
# phai bien dich lai ~1.000 file .py tu dau (do duoc 1,5 giay luc may "am", lan dau sau khi bat may lau hon
# nhieu; ca luc bam can chinh lan dau cung vay vi torch nap tu nguon).
# unchecked-hash: Python dung thang .pyc, khong so thoi gian sua file -> trinh cai chep lam doi gio van dung duoc.
# Mot vai file test trong site-packages bien dich loi (cu phap cu) -> compileall tra ma loi, bo qua.
Say "6b/7 Bien dich san .pyc..."
& "$Py\python.exe" -m compileall -q -j 0 --invalidation-mode unchecked-hash "$Out\solasub" "$SitePkg" | Out-Null

# --- 7. Script nang cap GPU (chay sau khi cai, neu may co NVIDIA) ---
Say "7/7  Tao script GPU..."
$gpu = @'
@echo off
chcp 65001 >nul
echo.
echo  ====================================================
echo   SolaSub - Cai goi tang toc GPU (NVIDIA)
echo  ====================================================
echo.
echo  Chi lam neu may co card NVIDIA.
echo.
echo    - Tai ve      : khoang 2,4 GB
echo    - Chiem them  : khoang 3,5 GB o dia
echo    - Doi lai     : 2 tieng audio xu ly nhanh hon khoang 10 lan
echo.
pause
"%~dp0python\python.exe" -m pip install --no-cache-dir --upgrade --force-reinstall torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
echo.
if errorlevel 1 (echo  CAI THAT BAI - xem thong bao loi ben tren.) else (echo  XONG. Mo lai SolaSub de dung GPU.)
pause
'@
[IO.File]::WriteAllText("$Out\Cai-dat-GPU.bat", $gpu, [Text.Encoding]::UTF8)

$cpu = @'
@echo off
echo Go goi GPU, quay ve ban CPU (giai phong khoang 3,5 GB)...
"%~dp0python\python.exe" -m pip install --no-cache-dir --upgrade --force-reinstall torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
pause
'@
[IO.File]::WriteAllText("$Out\Go-bo-GPU.bat", $cpu, [Text.Encoding]::UTF8)

$mb = [math]::Round(((Get-ChildItem $Out -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 0)
Say ""
Say "XONG - $Out ($mb MB)"
