# Chay BEN TRONG Windows Sandbox (test-nang-cap.wsb). File nay phai la ASCII thuan.
#
# Kich ban: nguoi dung da tai goi CUDA (torch +cu126) roi cai de ban moi.
# Truoc ban sua: [Files] chep torch CPU de len nhung KHONG xoa file chi CUDA moi co
# (torch_cuda.dll, cudnn...) -> torch nap MOI *.dll trong torch\lib -> loi.
# Khong tai that 2,4 GB: GIA LAP bang file .dll rac + thu muc dist-info +cu126.
#
#   1. cai sach ban CPU, import torch phai OK
#   2. gai file CUDA gia -> import torch phai VO (tai hien loi)
#   3. cai de bang CPU, KHONG suppress hop thoai, bam "No" -> phai huy, khong dung gi toi file
#   4. cai de bang CPU (/SUPPRESSMSGBOXES = bam Yes) -> file CUDA gia phai bi xoa, import OK
#   5. gai lai, cai de bang GPU khong tick CUDA (/TASKS="") -> nhu tren
#   6. can chinh that sau khi nang cap

$ErrorActionPreference = "Continue"
$Out = "C:\kichban\ketqua-nangcap"
Remove-Item $Out -Recurse -Force -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Log = "$Out\ketqua.txt"
$App = "C:\Users\WDAGUtilityAccount\AppData\Local\Programs\SolaSub"
$Site = "$App\python\Lib\site-packages"
$Lib = "$Site\torch\lib"
$Cpu = "C:\bocai\SolaSub_Setup_CPU.exe"
$Gpu = "C:\bocai\SolaSub_Setup_GPU.exe"

function Ghi($m) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $m
    Write-Host $line
    Add-Content $Log $line -Encoding utf8
}
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class W { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
"@
[void][W]::SetProcessDPIAware()

function ShotScreen($name) {
    $b = [Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object Drawing.Bitmap $b.Width, $b.Height
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
    $bmp.Save("$Out\$name", [Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Ghi "     da chup $name"
}

$code = @'
try:
    import torch
    print("OK  torch " + torch.__version__ + "  tinh thu: " + str(float(torch.ones(3).sum())))
except Exception as e:
    print("VO  " + type(e).__name__ + ": " + str(e)[:200])
'@
$code | Set-Content "$Out\imp.py" -Encoding utf8
function ImportTorch { (& "$App\python\python.exe" -I "$Out\imp.py" 2>&1 | Select-Object -Last 1) -as [string] }

function Gai {
    # DLL rac: LoadLibrary tra loi 193 -> y het cach torch vo khi lan DLL CUDA cu voi torch_cpu moi
    $rnd = New-Object byte[] 65536; (New-Object Random 7).NextBytes($rnd)
    foreach ($f in "torch_cuda.dll", "cudnn64_9.dll", "cublas64_12.dll") { [IO.File]::WriteAllBytes("$Lib\$f", $rnd) }
    $di = "$Site\torch-2.14.1+cu126.dist-info"
    New-Item -ItemType Directory -Force -Path $di | Out-Null
    "Metadata-Version: 2.1`nName: torch`nVersion: 2.14.1+cu126" | Set-Content "$di\METADATA" -Encoding ascii
}
function TrangThai {
    $con = @("torch_cuda.dll", "cudnn64_9.dll", "cublas64_12.dll" | Where-Object { Test-Path "$Lib\$_" })
    $di = @(Get-ChildItem $Site -Directory -Filter "torch-*.dist-info" | ForEach-Object Name)
    "file CUDA gia con lai: $($con.Count)/3  |  dist-info: $($di -join ', ')"
}
function CaiIm($exe, $tasks) {
    $t0 = Get-Date
    $p = Start-Process $exe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NOICONS", "/TASKS=`"$tasks`"" -Wait -PassThru
    "exit=$($p.ExitCode)  mat $([int]((Get-Date)-$t0).TotalSeconds)s"
}

Set-Content $Log "" -Encoding utf8
foreach ($f in $Cpu, $Gpu) { if (-not (Test-Path $f)) { Ghi "!! Khong thay $f"; "LOI" | Set-Content "$Out\XONG.txt"; exit 1 } }

Ghi "1/6  Cai sach ban CPU..."
Ghi "     $(CaiIm $Cpu '')"
Ghi "     $(ImportTorch)"
Ghi "     $(TrangThai)"

Ghi ""
Ghi "2/6  Gai file CUDA gia (nhu may da tai goi GPU)..."
Gai
Ghi "     $(TrangThai)"
Ghi "     $(ImportTorch)   <- phai VO (tai hien loi)"

Ghi ""
Ghi "3/6  Cai de bang CPU, hop thoai hien that, bam No..."
$t0 = Get-Date
$p = Start-Process $Cpu -ArgumentList "/SILENT", "/NOICONS" -PassThru
$tmp = $null
for ($i = 0; $i -lt 60 -and -not $tmp; $i++) {
    Start-Sleep 1
    $tmp = Get-Process -EA SilentlyContinue | Where-Object { $_.Path -like "*SolaSub_Setup_CPU.tmp" } | Select-Object -First 1
}
Start-Sleep 4
ShotScreen "3_hop_thoai_cpu.png"
$wsh = New-Object -ComObject WScript.Shell
if ($tmp) { [void]$wsh.AppActivate($tmp.Id) }
Start-Sleep -Milliseconds 500
[Windows.Forms.SendKeys]::SendWait("n")
if (-not $p.WaitForExit(60000)) { Ghi "     !! bo cai khong thoat sau khi bam No"; $p | Stop-Process -Force }
Ghi "     exit=$($p.ExitCode)  mat $([int]((Get-Date)-$t0).TotalSeconds)s  (khac 0 = da huy)"
Ghi "     $(TrangThai)   <- phai con nguyen 3/3"

Ghi ""
Ghi "4/6  Cai de bang CPU (dong y)..."
Ghi "     $(CaiIm $Cpu '')"
Ghi "     $(TrangThai)   <- phai 0/3, chi 1 dist-info +cpu"
Ghi "     $(ImportTorch)"

Ghi ""
Ghi "5/6  Gai lai, cai de bang GPU KHONG tick CUDA..."
Gai
Ghi "     truoc: $(TrangThai)"
Ghi "     $(CaiIm $Gpu '')"
Ghi "     sau:   $(TrangThai)"
Ghi "     $(ImportTorch)"
Ghi "     Cai-dat-GPU.bat co mat: $(Test-Path "$App\Cai-dat-GPU.bat")"

Ghi ""
$mau = "C:\kichban\mau"
if ((Test-Path "$mau\short.mp3") -and (Test-Path "$mau\short.txt")) {
    Ghi "6/6  Can chinh that sau khi nang cap..."
    Push-Location $App
    $t0 = Get-Date
    & "$App\python\python.exe" cli.py --audio "$mau\short.mp3" --text "$mau\short.txt" --lang ja --out "$Out\sau_nang_cap.srt" 2>&1 |
        Where-Object { $_ -match '^\[|cue|SRT' } | Select-Object -Last 2 | ForEach-Object { Ghi "     $_" }
    Pop-Location
    Ghi "     mat $([int]((Get-Date)-$t0).TotalSeconds)s  |  co SRT: $(Test-Path "$Out\sau_nang_cap.srt")"
} else { Ghi "6/6  BO QUA - khong co file mau" }

Ghi ""
Ghi "===== XONG ====="
"XONG" | Set-Content "$Out\XONG.txt" -Encoding utf8
