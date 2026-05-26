param(
    [string]$Host = $env:HOST,
    [string]$Port = $env:PORT,
    [string]$Workers = $env:WORKERS,
    [string]$AppDir = $PSScriptRoot,
    [switch]$InstallService,
    [switch]$InstallDeps
)

if (-not $Host) { $Host = "0.0.0.0" }
if (-not $Port) { $Port = "8000" }
if (-not $Workers) { $Workers = "4" }

$ErrorActionPreference = "Stop"

Write-Host "=== PDF Toolbox Deploy ==="
Write-Host "AppDir: $AppDir"
Write-Host "Host:   $Host"
Write-Host "Port:   $Port"
Write-Host "Workers: $Workers"

if (-not (Test-Path $AppDir)) {
    Write-Host "ERROR: App directory not found: $AppDir"
    exit 1
}

if ($InstallDeps) {
    Write-Host "=== Installing system dependencies ==="

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "Python not found. Installing via winget..."
        winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        refreshenv -ErrorAction SilentlyContinue
        Write-Host "Python installed."
    } else {
        Write-Host "Python: $(python --version)"
    }

    $libreOfficePath = "$env:ProgramFiles\LibreOffice\program\soffice.exe"
    if (-not (Test-Path $libreOfficePath)) {
        Write-Host "LibreOffice not found. Installing via winget..."
        winget install --id TheDocumentFoundation.LibreOffice --silent --accept-package-agreements --accept-source-agreements
        Write-Host "LibreOffice installed."
    } else {
        Write-Host "LibreOffice: found at $libreOfficePath"
    }

    if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
        Write-Host "NSSM not found. Installing via winget..."
        winget install --id NSSM.NSSM --silent --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        refreshenv -ErrorAction SilentlyContinue
        Write-Host "NSSM installed."
    } else {
        Write-Host "NSSM: found"
    }

    Write-Host "=== System dependencies done ==="
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Run with -InstallDeps or install manually."
    exit 1
}

$venvPath = Join-Path $AppDir "venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$uvicornExe = Join-Path $venvPath "Scripts\uvicorn.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venvPath
}

Write-Host "Installing pip dependencies..."
$env:PIP_REQUIRE_VIRTUALENV = "false"
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $AppDir "requirements.txt")
Write-Host "Pip dependencies installed."

if ($InstallService) {
    if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: NSSM not found. Run with -InstallDeps or install from https://nssm.cc/download"
        exit 1
    }

    $serviceName = "PDFToolbox"
    $existing = Get-Service $serviceName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Stopping existing service: $serviceName"
        nssm stop $serviceName
    }

    nssm install $serviceName "$uvicornExe" "app.main:app --host $Host --port $Port --workers $Workers" 2>$null
    nssm set $serviceName AppDirectory $AppDir
    nssm set $serviceName AppEnvironmentExtra "HOST=$Host`nPORT=$Port`nWORKERS=$Workers"
    nssm set $serviceName Start SERVICE_AUTO_START
    nssm start $serviceName

    Write-Host ""
    Write-Host "Service '$serviceName' installed and started."
    Write-Host "http://${Host}:${Port}"
} else {
    Write-Host ""
    Write-Host "=== To run the app ==="
    Write-Host "  & `"$uvicornExe`" app.main:app --host $Host --port $Port --workers $Workers"
    Write-Host ""
    Write-Host "=== To install as Windows Service ==="
    Write-Host "  .\deploy.ps1 -InstallService"
    Write-Host ""
    Write-Host "=== First-time complete setup ==="
    Write-Host "  .\deploy.ps1 -InstallDeps -InstallService"
    Write-Host ""
    Write-Host "After service install, access: http://${Host}:${Port}"
}
