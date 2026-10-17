# Chay BEN TRONG Windows Sandbox. Dung Windows sach: khong Python, khong
# VC++ Redistributable, khong driver NVIDIA.
#
# Kiem 4 thu, cai nao fail thi bao ngay:
#   1. cai dat im lang co xong khong
#   2. import torch / PyQt6 / whisper co nap duoc DLL khong   <- cho de vo nhat
#   3. align that tren file mau co ra SRT khong
#   4. cua so GUI co hien khong (kem anh chup)

$ErrorActionPreference = "Continue"
$Out = "C:\kichban\ketqua"
Remove-Item $Out -Recurse -Force -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Log = "$Out\ketqua.txt"
$App = "C:\Users\WDAGUtilityAccount\AppData\Local\Programs\SolaSub"

function Ghi($m) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $m
    Write-Host $line
    Add-Content $Log $line -Encoding utf8
}

Set-Content $Log "" -Encoding utf8
Ghi "Windows: $((Get-CimInstance Win32_OperatingSystem).Caption) build $([Environment]::OSVersion.Version.Build)"
Ghi "VC++ Redist trong System32:  msvcp140=$(Test-Path C:\Windows\System32\msvcp140.dll)  vcomp140=$(Test-Path C:\Windows\System32\vcomp140.dll)  vcruntime140=$(Test-Path C:\Windows\System32\vcruntime140.dll)"
Ghi "icuuc.dll: $(Test-Path C:\Windows\System32\icuuc.dll)   mscoree.dll: $(Test-Path C:\Windows\System32\mscoree.dll)"
Ghi "Python he thong: $(if (Get-Command python -EA SilentlyContinue) {'CO'} else {'KHONG'})"
Ghi "ffmpeg he thong: $(if (Get-Command ffmpeg -EA SilentlyContinue) {'CO'} else {'KHONG'})"
Ghi ""

# --- 1. Cai dat ---
$setup = Get-Item "C:\bocai\SolaSub_Setup_CPU.exe" -EA SilentlyContinue
if (-not $setup) { Ghi "!! Khong thay bo cai"; "LOI" | Set-Content "$Out\XONG.txt"; exit 1 }

Ghi "1/4  Dang cai (im lang)..."
$t0 = Get-Date
$p = Start-Process $setup.FullName -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NOICONS","/TASKS=`"`"" -Wait -PassThru
Ghi "     exit=$($p.ExitCode)  mat $([int]((Get-Date)-$t0).TotalSeconds)s  SolaSub.exe=$(Test-Path "$App\SolaSub.exe")"
if (-not (Test-Path "$App\SolaSub.exe")) { Ghi "!! CAI THAT BAI"; "LOI" | Set-Content "$Out\XONG.txt"; exit 1 }

# --- 2. Nap thu vien (cho de vo nhat tren may sach) ---
Ghi ""
Ghi "2/4  Thu import torch / PyQt6 / whisper..."
$code = @'
for m in ("torch", "PyQt6.QtWidgets", "PyQt6.QtMultimedia", "whisper",
          "stable_whisper", "numba", "torchaudio", "numpy", "llvmlite.binding"):
    try:
        __import__(m)
        print("   OK   " + m)
    except Exception as e:
        print("   VO   " + m + "  ->  " + type(e).__name__ + ": " + str(e)[:300])
import torch
print("   torch " + torch.__version__ + "   cuda=" + str(torch.cuda.is_available()))
'@
$code | Set-Content "$Out\imp.py" -Encoding utf8
& "$App\python\python.exe" -I "$Out\imp.py" 2>&1 | ForEach-Object { Ghi $_ }

# --- 3. Align that (chi khi co file mau) ---
Ghi ""
$mau = "C:\kichban\mau"
if ((Test-Path "$mau\short.mp3") -and (Test-Path "$mau\short.txt")) {
    Ghi "3/4  Chay align that tren file mau..."
    Push-Location $App
    $t0 = Get-Date
    & "$App\python\python.exe" cli.py --audio "$mau\short.mp3" --text "$mau\short.txt" `
        --lang ja --out "$Out\sandbox.srt" 2>&1 |
        Where-Object { $_ -notmatch 'Align:|Adjustment:' } | ForEach-Object { Ghi "     $_" }
    Pop-Location
    Ghi "     mat $([int]((Get-Date)-$t0).TotalSeconds)s  |  co file SRT: $(Test-Path "$Out\sandbox.srt")"
} else {
    Ghi "3/4  BO QUA — chua co build\sandbox\mau\short.mp3 + short.txt"
}

# --- 4. GUI + anh chup ---
Ghi ""
Ghi "4/4  Mo giao dien..."
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)]
public struct RECT { public int Left, Top, Right, Bottom; }
public static class W {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@
[void][W]::SetProcessDPIAware()

Start-Process "$App\SolaSub.exe"
$win = $null
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep 4
    $win = Get-Process pythonw -EA SilentlyContinue | Where-Object { $_.MainWindowTitle } | Select-Object -First 1
    if ($win) { break }
}
if ($win) {
    Ghi "     cua so: '$($win.MainWindowTitle)'   RAM $([math]::Round($win.WorkingSet64/1MB,0)) MB"
    Start-Sleep 3
    [void][W]::SetForegroundWindow($win.MainWindowHandle)
    Start-Sleep 2
    $r = New-Object RECT
    [void][W]::GetWindowRect($win.MainWindowHandle, [ref]$r)
    $cw = $r.Right - $r.Left; $ch = $r.Bottom - $r.Top
    if ($cw -gt 0 -and $ch -gt 0) {
        $bmp = New-Object Drawing.Bitmap $cw, $ch
        $g = [Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
        $bmp.Save("$Out\gui.png", [Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
        Ghi "     da chup gui.png ($cw x $ch)"
    }
} else {
    Ghi "     !! CUA SO KHONG HIEN"
}

Ghi ""
Ghi "===== XONG ====="
"XONG" | Set-Content "$Out\XONG.txt" -Encoding utf8
