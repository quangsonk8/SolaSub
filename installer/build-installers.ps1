# Dung ca hai bo cai tu build\SolaSub.
# Chay sau khi da chay build\build.ps1.
#
# Luu y ve Kaspersky: Inno ghi icon vao file .exe vua tao bang EndUpdateResource.
# Neu Kaspersky dang quet file do thi bi "Resource update error ... (32)" va
# compile abort — gap that nhieu lan. Cach vong: dung /O cho ISCC ghi ra mot
# thu muc MOI TINH roi moi chuyen file ve Output.

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
$Out  = "$Here\Output"
$Iss  = "$Here\solasub.iss"

if (-not (Test-Path $Iscc)) { throw "Khong thay ISCC.exe: $Iscc" }
if (-not (Test-Path "$Here\..\build\SolaSub\SolaSub.exe")) {
    throw "Chua co ban dong goi — chay build\build.ps1 truoc."
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
    Move-Item $exe.FullName "$Out\$($exe.Name)" -Force
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
    "  -> $Out\$($exe.Name)  ($([math]::Round($exe.Length/1MB,0)) MB)"
}

Dung "CPU" $null
Dung "GPU" "/DGPU"

Write-Host ""
Get-ChildItem $Out -Filter "*.exe" |
    Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,0)}}, LastWriteTime
