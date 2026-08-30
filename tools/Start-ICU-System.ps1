[CmdletBinding()]
param(
    [switch]$StartMobile
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$mobileDir = Join-Path $projectRoot 'mobile'
$postgresData = Join-Path $projectRoot '.local-pilot-postgres'
$postgresBin = 'C:\Program Files\PostgreSQL\17\bin'
$postgres = Join-Path $postgresBin 'postgres.exe'
$pgReady = Join-Path $postgresBin 'pg_isready.exe'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'
$backendRunner = Join-Path $PSScriptRoot 'Run-ICU-Backend.cmd'
$frontendRunner = Join-Path $PSScriptRoot 'Run-ICU-Frontend.cmd'
$node = 'C:\Program Files\nodejs\node.exe'
$vite = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
$apiRoot = 'http://127.0.0.1:8001'
$frontendUrl = 'http://127.0.0.1:5174'
$frontendOrigin = $frontendUrl
$databaseUrl = 'postgresql+psycopg2://pilot_app@127.0.0.1:55432/nurse_schedule_pilot_v2'

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Write-Status([string]$message, [string]$color = 'Cyan') {
    Write-Host "[ICU System] $message" -ForegroundColor $color
}

function Test-Listening([int]$port) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Wait-Until([scriptblock]$condition, [int]$seconds, [string]$label) {
    $deadline = (Get-Date).AddSeconds($seconds)
    do {
        if (& $condition) { return $true }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    Write-Status "$label ไม่พร้อมภายใน $seconds วินาที" 'Red'
    return $false
}

function Test-Api {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "$apiRoot/"
        return $response.StatusCode -eq 200
    } catch { return $false }
}

function Test-CorsPreflight {
    try {
        $headers = @{
            Origin = $frontendOrigin
            'Access-Control-Request-Method' = 'POST'
            'Access-Control-Request-Headers' = 'content-type'
        }
        $response = Invoke-WebRequest -UseBasicParsing -Method Options -TimeoutSec 3 -Uri "$apiRoot/api/v1/auth/login" -Headers $headers
        $allowedOrigin = [string]$response.Headers['Access-Control-Allow-Origin']
        return $response.StatusCode -eq 200 -and $allowedOrigin -eq $frontendOrigin
    } catch { return $false }
}

function Test-ExpoServer {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri 'http://127.0.0.1:8081/status'
        $content = if ($response.Content -is [byte[]]) {
            [System.Text.Encoding]::UTF8.GetString($response.Content)
        } else {
            [string]$response.Content
        }
        return $response.StatusCode -eq 200 -and $content.Trim() -eq 'packager-status:running'
    } catch { return $false }
}

function Get-PreferredMobileHost {
    try {
        $configurations = @(Get-NetIPConfiguration -ErrorAction Stop | Where-Object {
            $_.NetAdapter.Status -eq 'Up' -and $_.IPv4Address -and $_.IPv4DefaultGateway
        })
        $preferred = $configurations | Where-Object {
            $_.InterfaceAlias -match '(?i)wi-?fi|wireless|wlan' -or
            $_.NetAdapter.InterfaceDescription -match '(?i)wi-?fi|wireless|wlan'
        } | Select-Object -First 1
        if ($null -eq $preferred) {
            $preferred = $configurations | Where-Object {
                $_.NetAdapter.InterfaceDescription -notmatch '(?i)virtual|remote ndis|internet sharing|loopback'
            } | Select-Object -First 1
        }
        if ($null -ne $preferred) { return [string]$preferred.IPv4Address.IPAddress }
    } catch { }
    return $null
}

function Test-ManagedExpoProcess([int]$processId) {
    if ($processId -le 0) { return $false }
    try {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop
        if ($null -eq $processInfo) { return $false }
        $commandLine = [string]$processInfo.CommandLine
        return $commandLine -match '(?i)expo\s+start' -and $commandLine -match '(?i)--port\s+8081'
    } catch { return $false }
}

function Stop-ManagedExpo {
    $pidFile = Join-Path $runtimeDir 'expo.pid'
    if (-not (Test-Path $pidFile)) { return $false }
    $expoPid = 0
    if (-not [int]::TryParse((Get-Content $pidFile -Raw).Trim(), [ref]$expoPid)) { return $false }
    if (-not (Test-ManagedExpoProcess $expoPid)) { return $false }
    & taskkill.exe /PID $expoPid /T /F 2>$null | Out-Null
    return Wait-Until { -not (Test-ExpoServer) } 10 'หยุด Expo เดิม'
}

function Get-BackendListenerPid {
    try {
        return [int](Get-NetTCPConnection -State Listen -LocalPort 8001 -ErrorAction Stop | Select-Object -First 1 -ExpandProperty OwningProcess)
    } catch { return 0 }
}

function Test-ManagedBackendProcess([int]$processId) {
    if ($processId -le 0) { return $false }
    try {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop
        if ($null -eq $processInfo) { return $false }
        $commandLine = [string]$processInfo.CommandLine
        $executable = [string]$processInfo.ExecutablePath
        $runnerMatch = $commandLine.IndexOf($backendRunner, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        $uvicornMatch = (
            $executable.Equals($python, [System.StringComparison]::OrdinalIgnoreCase) -and
            $commandLine -match '(?i)-m\s+uvicorn\s+app\.main:app'
        )
        return $runnerMatch -or $uvicornMatch
    } catch { return $false }
}

function Stop-ManagedBackend {
    $candidatePids = [System.Collections.Generic.List[int]]::new()
    $pidFile = Join-Path $runtimeDir 'backend.log.pid'
    if (Test-Path $pidFile) {
        $savedPid = 0
        if ([int]::TryParse((Get-Content $pidFile -Raw).Trim(), [ref]$savedPid) -and $savedPid -gt 0) {
            $candidatePids.Add($savedPid)
        }
    }
    $listenerPid = Get-BackendListenerPid
    if ($listenerPid -gt 0 -and -not $candidatePids.Contains($listenerPid)) {
        $candidatePids.Add($listenerPid)
    }

    $managedPids = @($candidatePids | Where-Object { Test-ManagedBackendProcess $_ })
    if ($managedPids.Count -eq 0) {
        Write-Status 'ไม่สามารถยืนยันว่า Backend บนพอร์ต 8001 เป็นโปรเซสของโปรเจกต์ จึงไม่ปิดโปรเซสโดยอัตโนมัติ' 'Red'
        return $false
    }

    foreach ($managedPid in $managedPids) {
        & taskkill.exe /PID $managedPid /T /F 2>$null | Out-Null
    }
    return Wait-Until { -not (Test-Api) } 10 'หยุด Backend เดิม'
}

function Set-FrontendOrigins {
    $origins = [System.Collections.Generic.List[string]]::new()
    $origins.Add('http://127.0.0.1:5174')
    $origins.Add('http://localhost:5174')
    try {
        $addresses = Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred -ErrorAction Stop |
            Where-Object { -not $_.IPAddress.StartsWith('127.') -and -not $_.IPAddress.StartsWith('169.254.') } |
            Select-Object -ExpandProperty IPAddress -Unique
        foreach ($address in $addresses) {
            $origin = "http://${address}:5174"
            if (-not $origins.Contains($origin)) { $origins.Add($origin) }
        }
    } catch {
        Write-Status 'ไม่สามารถอ่าน IP เครือข่ายได้ — จะอนุญาตเฉพาะหน้าเว็บในเครื่องนี้' 'Yellow'
    }
    $env:FRONTEND_ORIGINS = $origins -join ','
}

function Test-Postgres {
    & $pgReady -h 127.0.0.1 -p 55432 -q
    return $LASTEXITCODE -eq 0
}

function Start-Background([string]$file, [string]$arguments, [string]$workingDirectory, [string]$logName) {
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = $file
    $processInfo.Arguments = $arguments
    $processInfo.WorkingDirectory = $workingDirectory
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $process = [System.Diagnostics.Process]::Start($processInfo)
    $process.Id | Set-Content -Encoding ascii (Join-Path $runtimeDir "$logName.pid")
    return $process
}

Write-Status 'เริ่มตรวจสอบระบบ ICU…'
Set-FrontendOrigins

foreach ($required in @($python, $postgres, $pgReady, $node, $vite, $backendRunner, $frontendRunner, (Join-Path $frontendDir 'node_modules'), (Join-Path $mobileDir 'node_modules'))) {
    if (-not (Test-Path $required)) { throw "ไม่พบองค์ประกอบที่จำเป็น: $required" }
}

if (-not (Test-Postgres)) {
    Write-Status 'ฐานข้อมูลยังไม่ทำงาน — กำลังเปิดให้…' 'Yellow'
    Start-Background $postgres "-D `"$postgresData`" -p 55432 -h 127.0.0.1" $projectRoot 'postgres.log' | Out-Null
}
if (-not (Wait-Until { Test-Postgres } 15 'PostgreSQL')) { exit 1 }
Write-Status 'PostgreSQL พร้อม'

$apiReady = Test-Api
if ($apiReady -and -not (Test-CorsPreflight)) {
    Write-Status 'Backend ทำงานอยู่ แต่ไม่อนุญาต CORS สำหรับหน้าเว็บ — กำลังแก้โดยรีสตาร์ต Backend ของโปรเจกต์…' 'Yellow'
    if (-not (Stop-ManagedBackend)) {
        throw 'ตรวจพบ CORS ผิด แต่ไม่สามารถรีสตาร์ต Backend อย่างปลอดภัยได้ กรุณาปิด Backend เดิมของโปรเจกต์แล้วเปิด OPEN_ICU_SYSTEM.cmd อีกครั้ง'
    }
    $apiReady = $false
}

if (-not $apiReady) {
    if (Test-Listening 8001) {
        throw 'พอร์ต 8001 ถูกใช้งาน แต่ Backend ICU ไม่ตอบ health check เพื่อความปลอดภัยจึงไม่ปิดโปรแกรมอื่นอัตโนมัติ'
    }
    Write-Status 'Backend ยังไม่ทำงาน — กำลังเปิดให้…' 'Yellow'
    Start-Background 'cmd.exe' "/d /c `"$backendRunner`"" $projectRoot 'backend.log' | Out-Null
}
if (-not (Wait-Until { Test-Api } 30 'Backend')) { exit 1 }
Write-Status 'Backend พร้อม: http://127.0.0.1:8001'
if (-not (Wait-Until { Test-CorsPreflight } 10 'ตรวจสอบ CORS ของ Backend')) {
    throw "Backend ไม่อนุญาตให้หน้าเว็บ $frontendOrigin เรียก API กรุณาตรวจ FRONTEND_ORIGINS"
}
Write-Status "CORS พร้อมสำหรับหน้าเว็บ: $frontendOrigin" 'Green'

if (-not (Test-Listening 5174)) {
    Write-Status 'เว็บยังไม่ทำงาน — กำลังเปิดให้…' 'Yellow'
    Start-Background 'cmd.exe' "/d /c `"$frontendRunner`"" $projectRoot 'frontend.log' | Out-Null
}
if (-not (Wait-Until { try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri $frontendUrl).StatusCode -eq 200 } catch { $false } } 30 'Frontend')) { exit 1 }
Write-Status "หน้าเว็บพร้อม: $frontendUrl" 'Green'

if ($StartMobile) {
    $mobileHost = Get-PreferredMobileHost
    if ([string]::IsNullOrWhiteSpace($mobileHost)) {
        throw 'ไม่พบ IPv4 ของ Wi-Fi สำหรับ Expo กรุณาเชื่อมคอมพิวเตอร์และโทรศัพท์กับ Wi-Fi เดียวกัน'
    }
    $expoHostFile = Join-Path $runtimeDir 'expo-host.txt'
    $previousExpoHost = if (Test-Path $expoHostFile) { (Get-Content $expoHostFile -Raw).Trim() } else { '' }
    $expoNeedsRestart = (Test-Listening 8081) -and ((-not (Test-ExpoServer)) -or $previousExpoHost -ne $mobileHost)
    if ($expoNeedsRestart) {
        Write-Status "Expo เดิมใช้เครือข่ายไม่ตรงกับ Wi-Fi ปัจจุบัน ($mobileHost) — กำลังรีสตาร์ต…" 'Yellow'
        if (-not (Stop-ManagedExpo)) {
            throw 'ไม่สามารถยืนยันว่าโปรเซสบนพอร์ต 8081 เป็น Expo ของโปรเจกต์ กรุณาปิดหน้าต่าง Expo เดิมแล้วเปิด OPEN_ICU_SYSTEM.cmd อีกครั้ง'
        }
    }
    if (-not (Test-Listening 8081)) {
        Write-Status "กำลังเปิด Expo ผ่าน Wi-Fi $mobileHost…" 'Yellow'
        $env:REACT_NATIVE_PACKAGER_HOSTNAME = $mobileHost
        $expoProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', 'title ICU Schedule Expo & npx.cmd expo start --lan --port 8081 --clear' -WorkingDirectory $mobileDir -PassThru
        $expoProcess.Id | Set-Content -Encoding ascii (Join-Path $runtimeDir 'expo.pid')
        $mobileHost | Set-Content -Encoding ascii $expoHostFile
    }
    if (-not (Wait-Until { Test-ExpoServer } 30 'Expo/Metro')) { exit 1 }
    Write-Status "Expo พร้อมสำหรับโทรศัพท์: exp://${mobileHost}:8081" 'Green'
}

Start-Process $frontendUrl
Write-Host ''
Write-Status 'ระบบพร้อมใช้งานแล้ว' 'Green'
Write-Host "เว็บ: $frontendUrl"
Write-Host 'Backend: http://127.0.0.1:8001/docs'
if ($StartMobile) {
    Write-Host "มือถือ: สแกน QR ที่หน้าต่าง Expo (Wi-Fi host: $mobileHost)"
    Write-Host 'Expo Go บนโทรศัพท์ต้องรองรับ SDK 54'
}
