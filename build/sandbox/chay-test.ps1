# Chay BEN TRONG Windows Sandbox. Windows sach: khong Python, khong VC++ Redistributable, khong driver NVIDIA.
# File nay phai la ASCII thuan (PowerShell 5.1 doc script khong BOM theo ANSI).
#
#   1. cai dat im lang
#   2. go font Inter khoi sandbox (sandbox dung chung C:\Windows\Fonts voi may that) -> chung minh app dung font dong goi
#   3. nap thu vien (torch / PyQt6 / whisper) + dem file .pyc bien dich san
#   4. MO LAN DAU (may lanh): man hinh khoi dong hien sau bao lau, cua so chinh sau bao lau; bam lan 2 khong mo them
#   5. giao dien che do sang + toi (anh chup)
#   6. can chinh that bang .txt va bang Word .docx -> 2 file SRT phai giong het

$ErrorActionPreference = "Continue"
$Out = "C:\kichban\ketqua"
Remove-Item $Out -Recurse -Force -EA SilentlyContinue
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Log = "$Out\ketqua.txt"
$App = "C:\Users\WDAGUtilityAccount\AppData\Local\Programs\SolaSub"
$Exe = "$App\SolaSub.exe"
$PyW = "$App\python\pythonw.exe"
$Cfg = "$env:LOCALAPPDATA\SolaSub"

function Ghi($m) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $m
    Write-Host $line
    Add-Content $Log $line -Encoding utf8
}

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
public static class W {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r);
  [DllImport("gdi32.dll", CharSet=CharSet.Unicode)] public static extern bool RemoveFontResource(string f);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr h, uint m, IntPtr w, IntPtr l, uint f, uint t, out IntPtr r);
}
"@
[void][W]::SetProcessDPIAware()

function Shot($hwnd, $name) {
    $r = New-Object RECT
    [void][W]::GetWindowRect($hwnd, [ref]$r)
    $cw = $r.Right - $r.Left; $ch = $r.Bottom - $r.Top
    if ($cw -le 0 -or $ch -le 0) { Ghi "     (khong chup duoc $name)"; return }
    $bmp = New-Object Drawing.Bitmap $cw, $ch
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
    $bmp.Save("$Out\$name", [Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Ghi "     da chup $name ($cw x $ch)"
}
function SplashHwnd {
    $p = Get-Process SolaSub -EA SilentlyContinue | Where-Object { $_.Path -eq $Exe -and $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
    if ($p) { return $p.MainWindowHandle } else { return [IntPtr]::Zero }
}
function MainProc { Get-Process pythonw -EA SilentlyContinue | Where-Object { $_.Path -eq $PyW -and $_.MainWindowTitle -like "SolaSub*" } | Select-Object -First 1 }
function AppProcs { @(Get-Process pythonw -EA SilentlyContinue | Where-Object { $_.Path -eq $PyW }) }
function StopApp { Get-Process pythonw, SolaSub -EA SilentlyContinue | Where-Object { $_.Path -like "$App\*" } | Stop-Process -Force; Start-Sleep 2 }

Set-Content $Log "" -Encoding utf8
Ghi "Windows: $((Get-CimInstance Win32_OperatingSystem).Caption) build $([Environment]::OSVersion.Version.Build)"
Ghi "Python he thong: $(if (Get-Command python -EA SilentlyContinue) {'CO'} else {'KHONG'})   VC++ msvcp140: $(Test-Path C:\Windows\System32\msvcp140.dll)"

# --- 1. Cai dat ---
$setup = Get-Item "C:\bocai\SolaSub_Setup_CPU.exe" -EA SilentlyContinue
if (-not $setup) { Ghi "!! Khong thay bo cai"; "LOI" | Set-Content "$Out\XONG.txt"; exit 1 }
Ghi ""
Ghi "1/6  Cai im lang ($([math]::Round($setup.Length/1MB,0)) MB)..."
$t0 = Get-Date
# Sandbox ban moi BAT Smart App Control: bo cai chua ky so + chua co "uy tin" bi chan ngay, khong chay duoc
# -> ghi ro ly do (truoc day chi thay "exit=" rong).
$sac = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -EA SilentlyContinue).VerifiedAndReputablePolicyState
try {
    $p = Start-Process $setup.FullName -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NOICONS","/TASKS=`"`"" -Wait -PassThru -ErrorAction Stop
} catch {
    Ghi "     !! Windows chan bo cai: $($_.Exception.Message)"
    if ($sac -eq 1) { Ghi "     (Smart App Control dang BAT trong sandbox - chan file .exe chua ky so. Khong phai loi bo cai.)" }
    "LOI" | Set-Content "$Out\XONG.txt"; exit 1
}
Ghi "     exit=$($p.ExitCode)  mat $([int]((Get-Date)-$t0).TotalSeconds)s  SolaSub.exe=$(Test-Path $Exe)"
if (-not (Test-Path $Exe)) { Ghi "!! CAI THAT BAI"; "LOI" | Set-Content "$Out\XONG.txt"; exit 1 }
$pyc = @(Get-ChildItem $App -Recurse -Filter *.pyc -EA SilentlyContinue).Count
Ghi "     .pyc bien dich san: $pyc file   font dong goi: $((Get-ChildItem "$App\assets\fonts" -EA SilentlyContinue | ForEach-Object Name) -join ', ')"

# --- 2. Go Inter khoi sandbox ---
Ghi ""
Ghi "2/6  Go font Inter khoi sandbox (chi trong sandbox)..."
$key = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'
foreach ($v in ((Get-ItemProperty $key).PSObject.Properties | Where-Object Name -match '^Inter')) {
    $f = $v.Value; if ($f -notmatch '\\') { $f = Join-Path 'C:\Windows\Fonts' $f }
    [void][W]::RemoveFontResource($f); Remove-ItemProperty -Path $key -Name $v.Name -EA SilentlyContinue
}
Stop-Service FontCache -Force -EA SilentlyContinue
Remove-Item 'C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache\*' -Force -Recurse -EA SilentlyContinue
Start-Service FontCache -EA SilentlyContinue
$r0 = [IntPtr]::Zero; [void][W]::SendMessageTimeout([IntPtr]0xffff, 0x001D, [IntPtr]::Zero, [IntPtr]::Zero, 2, 3000, [ref]$r0)
$left = @((Get-ItemProperty $key).PSObject.Properties | Where-Object Name -match '^Inter').Count
$gdi = @((New-Object System.Drawing.Text.InstalledFontCollection).Families | Where-Object Name -match '^Inter').Count
Ghi "     Inter con lai: registry $left, GDI $gdi"

# --- 3. Nap thu vien ---
Ghi ""
Ghi "3/6  Nap thu vien..."
$code = @'
import time
for m in ("torch", "PyQt6.QtWidgets", "PyQt6.QtMultimedia", "whisper", "stable_whisper", "numba", "numpy"):
    t = time.perf_counter()
    try:
        __import__(m); print("   OK   %-20s %.1fs" % (m, time.perf_counter() - t))
    except Exception as e:
        print("   VO   " + m + "  ->  " + type(e).__name__ + ": " + str(e)[:300])
'@
$code | Set-Content "$Out\imp.py" -Encoding utf8
& "$App\python\python.exe" -I "$Out\imp.py" 2>&1 | ForEach-Object { Ghi $_ }

# --- 4. Mo lan dau (may lanh) ---
Ghi ""
Ghi "4/6  Mo app LAN DAU qua SolaSub.exe (nhu bam loi tat)..."
StopApp
$sw = [Diagnostics.Stopwatch]::StartNew()
Start-Process $Exe -WorkingDirectory $App
$tSplash = $null
while ($sw.Elapsed.TotalSeconds -lt 20) { if ((SplashHwnd) -ne [IntPtr]::Zero) { $tSplash = $sw.Elapsed.TotalSeconds; break }; Start-Sleep -Milliseconds 20 }
Ghi ("     man hinh khoi dong hien sau: {0:N2}s" -f $tSplash)
Start-Sleep -Milliseconds 500
$h = SplashHwnd; if ($h -ne [IntPtr]::Zero) { Shot $h "1_khoi_dong.png" }
Start-Process $Exe -WorkingDirectory $App      # bam lan 2 khi dang khoi dong
$tMain = $null; $mp = $null
while ($sw.Elapsed.TotalSeconds -lt 120) { $mp = MainProc; if ($mp) { $tMain = $sw.Elapsed.TotalSeconds; break }; Start-Sleep -Milliseconds 100 }
Ghi ("     cua so chinh hien sau: {0:N1}s" -f $tMain)
Start-Sleep 3
Ghi "     bam lan 2 luc dang khoi dong -> so tien trinh SolaSub: $((AppProcs).Count) (phai la 1)"
Start-Process $Exe -WorkingDirectory $App; Start-Sleep 3        # bam khi app da mo
Ghi "     bam khi app da mo -> so tien trinh SolaSub: $((AppProcs).Count) (phai la 1)"
if (Test-Path "$Cfg\startup.log") { Copy-Item "$Cfg\startup.log" "$Out\startup.log" }

# --- 5. Giao dien sang + toi ---
Ghi ""
Ghi "5/6  Giao dien..."
foreach ($mode in "light", "dark") {
    StopApp
    New-Item -ItemType Directory -Force -Path $Cfg | Out-Null
    # Ghi CO BOM (Set-Content -Encoding utf8 cua PowerShell 5.1 luon them BOM) -> kiem luon app doc duoc file co BOM
    ('{"theme": "' + $mode + '"}') | Set-Content "$Cfg\settings.json" -Encoding utf8
    $sw2 = [Diagnostics.Stopwatch]::StartNew()
    Start-Process $Exe -WorkingDirectory $App
    $mp = $null
    while ($sw2.Elapsed.TotalSeconds -lt 60) { $mp = MainProc; if ($mp) { break }; Start-Sleep -Milliseconds 100 }
    if (-not $mp) { Ghi "     !! cua so ($mode) khong hien"; continue }
    Ghi ("     [$mode] mo lan sau (may da am): cua so hien sau {0:N1}s" -f $sw2.Elapsed.TotalSeconds)
    Start-Sleep 3
    [void][W]::MoveWindow($mp.MainWindowHandle, 20, 20, 1320, 820, $true); Start-Sleep 1
    [void][W]::SetForegroundWindow($mp.MainWindowHandle); Start-Sleep 1
    Shot $mp.MainWindowHandle "2_giao_dien_$mode.png"
}
StopApp

# --- 6. Can chinh that: .txt va .docx ---
Ghi ""
$mau = "C:\kichban\mau"
if ((Test-Path "$mau\short.mp3") -and (Test-Path "$mau\short.txt")) {
    Push-Location $App
    foreach ($src in "short.txt", "short.docx") {
        if (-not (Test-Path "$mau\$src")) { Ghi "6/6  bo qua $src (khong co file mau)"; continue }
        Ghi "6/6  Can chinh that tu $src..."
        $t0 = Get-Date
        & "$App\python\python.exe" cli.py --audio "$mau\short.mp3" --text "$mau\$src" --lang ja --out "$Out\from_$src.srt" 2>&1 |
            Where-Object { $_ -match '^\[|cue|SRT' } | Select-Object -Last 3 | ForEach-Object { Ghi "     $_" }
        Ghi "     mat $([int]((Get-Date)-$t0).TotalSeconds)s  |  co SRT: $(Test-Path "$Out\from_$src.srt")"
    }
    Pop-Location
    if ((Test-Path "$Out\from_short.txt.srt") -and (Test-Path "$Out\from_short.docx.srt")) {
        $same = (Get-Content "$Out\from_short.txt.srt" -Raw -Encoding UTF8) -eq (Get-Content "$Out\from_short.docx.srt" -Raw -Encoding UTF8)
        Ghi "     SRT tu .docx giong het SRT tu .txt: $same"
    }
} else {
    Ghi "6/6  BO QUA - chua co build\sandbox\mau\short.mp3 + short.txt"
}

Ghi ""
Ghi "===== XONG ====="
"XONG" | Set-Content "$Out\XONG.txt" -Encoding utf8
