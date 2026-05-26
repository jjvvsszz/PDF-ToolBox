param(
    [string]$Host = $env:HOST,
    [string]$Port = $env:PORT,
    [string]$Workers = $env:WORKERS,
    [string]$AppDir = $PSScriptRoot,
    [switch]$InstallService,
    [switch]$InstallDeps
)

Function Get-PackageManager {
    if (Get-Command winget -ErrorAction SilentlyContinue) { return "winget" }
    if (Get-Command choco -ErrorAction SilentlyContinue) { return "choco" }
    return $null
}

Function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Function Install-Chocolatey {
    Write-Host "Installing Chocolatey (required for dependency management)..."
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    $env:ChocolateyInstall = "$env:ProgramData\chocolatey"
    New-Item -ItemType Directory -Force -Path $env:ChocolateyInstall | Out-Null
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:Path = "$env:Path;$env:ChocolateyInstall\bin"
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Failed to install Chocolatey. Install manually: https://chocolatey.org/install"
        exit 1
    }
    Write-Host "Chocolatey installed."
}

Function Install-Python {
    Write-Host "[Python] Installing..."
    $pm = Get-PackageManager

    if ($pm -eq "winget") {
        winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    }
    elseif ($pm -eq "choco") {
        choco install python311 -y --limit-output
    }
    else {
        Write-Host "  No package manager found. Downloading from python.org..."
        $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $installer = "$env:TEMP\python-installer.exe"
        Invoke-WebRequest -Uri $pythonUrl -OutFile $installer -UseBasicParsing
        Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -NoNewWindow
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
    }

    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    refreshenv -ErrorAction SilentlyContinue

    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Host "ERROR: Python installation failed. Install manually: https://www.python.org/downloads/"
        exit 1
    }
    Write-Host "[Python] $(python --version)"
}

Function Install-LibreOffice {
    Write-Host "[LibreOffice] Installing..."
    $pm = Get-PackageManager

    $libreOfficePath = "$env:ProgramFiles\LibreOffice\program\soffice.exe"
    if (Test-Path $libreOfficePath) {
        Write-Host "[LibreOffice] Already installed at $libreOfficePath"
        return
    }

    if ($pm -eq "winget") {
        winget install --id TheDocumentFoundation.LibreOffice --silent --accept-package-agreements --accept-source-agreements
    }
    elseif ($pm -eq "choco") {
        choco install libreoffice-fresh -y --limit-output
    }
    else {
        Write-Host "  No package manager found. Downloading from libreoffice.org..."
        $loUrl = "https://download.documentfoundation.org/libreoffice/stable/24.8.4/win/x86_64/LibreOffice_24.8.4_Win_x86-64.msi"
        $installer = "$env:TEMP\libreoffice-installer.msi"
        Invoke-WebRequest -Uri $loUrl -OutFile $installer -UseBasicParsing
        Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$installer`" /qn /norestart" -Wait -NoNewWindow
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
    }

    if (-not (Test-Path $libreOfficePath)) {
        Write-Host "WARNING: LibreOffice installation may have failed. Office-to-PDF conversion will not work."
    } else {
        Write-Host "[LibreOffice] Installed at $libreOfficePath"
    }
}

Function Install-NSSM {
    Write-Host "[NSSM] Installing..."
    $pm = Get-PackageManager

    if (Get-Command nssm -ErrorAction SilentlyContinue) {
        Write-Host "[NSSM] Already installed."
        return
    }

    if ($pm -eq "winget") {
        winget install --id NSSM.NSSM --silent --accept-package-agreements --accept-source-agreements
    }
    elseif ($pm -eq "choco") {
        choco install nssm -y --limit-output
    }
    else {
        Write-Host "  No package manager found. Downloading from nssm.cc..."
        $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
        $nssmZip = "$env:TEMP\nssm.zip"
        $nssmDir = "$env:ProgramFiles\nssm"
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing
        Expand-Archive -Path $nssmZip -DestinationPath $nssmDir -Force
        Remove-Item $nssmZip -Force -ErrorAction SilentlyContinue
        $nssmExe = Get-ChildItem -Path $nssmDir -Filter nssm.exe -Recurse | Select-Object -First 1
        if ($nssmExe) {
            $targetDir = "$env:windir\system32"
            Copy-Item $nssmExe.FullName $targetDir -Force
        }
    }

    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    refreshenv -ErrorAction SilentlyContinue

    if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
        Write-Host "WARNING: NSSM installation may have failed. Service registration will not work."
    } else {
        Write-Host "[NSSM] Installed."
    }
}

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
    if (-not (Test-IsAdmin)) {
        Write-Host "ERROR: -InstallDeps requires Administrator privileges. Run PowerShell as Admin."
        exit 1
    }

    Write-Host "=== Installing system dependencies ==="

    if (-not (Get-PackageManager)) {
        Install-Chocolatey
    }

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Install-Python
    } else {
        Write-Host "[Python] $(python --version)"
    }

    if (-not (Test-Path "$env:ProgramFiles\LibreOffice\program\soffice.exe")) {
        Install-LibreOffice
    } else {
        Write-Host "[LibreOffice] Already installed."
    }

    if ($InstallService) {
        if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
            Install-NSSM
        } else {
            Write-Host "[NSSM] Already installed."
        }
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
