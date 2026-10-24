# Dung ca hai bo cai tu build\SolaSub.
# Chay sau khi da chay build\build.ps1.
#
# Luu y ve phan mem diet virus (truoc day Kaspersky, nay la Microsoft Defender): Inno ghi icon vao file .exe vua tao bang EndUpdateResource.
# Neu phan mem diet virus dang quet file do thi bi "Resource update error ... (32)" va
# compile abort - gap that nhieu lan. Cach vong: dung /O cho ISCC ghi ra mot
# thu muc MOI TINH roi moi chuyen file ve Output.

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
$Out  = "$Here\Output"
$Iss  = "$Here\solasub.iss"

if (-not (Test-Path $Iscc)) { throw "Khong thay ISCC.exe: $Iscc" }
if (-not (Test-Path "$Here\..\build\SolaSub\SolaSub.exe")) {
    throw "Chua co ban dong goi - chay build\build.ps1 truoc."
}
New-Item -ItemType Directory -Force -Path $Out | Out-Null

function Dung($ten, $dinhNghia) {
    $tmp = "$Here\_tmpout_$ten"
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null

    Write-Host "Dang dung ban $ten..." -ForegroundColor Cyan
    $args = @()
    if ($dinhNghia) { $args += $dinhNghia }
    $args += "/O$tmp"
    $args += $Iss
    & $Iscc @args | Select-Object -Last 2
    if ($LASTEXITCODE -ne 0) { throw "Compile ban $ten that bai" }

    $exe = Get-ChildItem $tmp -Filter "*.exe" | Select-Object -First 1
    $dst = "$Out\$($exe.Name)"
    # Phan mem diet virus (Microsoft Defender) co the khoa file .exe vua tao de quet (va Windows Sandbox con mo co the giu file cu trong Output)
    # -> Move-Item bao "being used by another process". Da tung mat ca 2 bo cai vi xoa thu muc tam ngay sau
    # lan chuyen hong. Gio: CHEP + thu lai toi 3 phut, kiem dung dung luong roi moi xoa thu muc tam;
    # khong chep duoc thi DUNG va GIU ban vua dong trong thu muc tam.
    $ok = $false
    for ($i = 0; $i -lt 90 -and -not $ok; $i++) {
        try {
            Copy-Item $exe.FullName $dst -Force -ErrorAction Stop
            if ((Get-Item $dst).Length -eq $exe.Length) { $ok = $true }
        } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ok) { throw "Khong chep duoc $($exe.Name) sang Output (file van bi khoa). Ban vua dong van con o: $tmp" }
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
    "  -> $dst  ($([math]::Round($exe.Length/1MB,0)) MB)"
}

Dung "CPU" $null
Dung "GPU" "/DGPU"

Write-Host ""
Get-ChildItem $Out -Filter "*.exe" |
    Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,0)}}, LastWriteTime
