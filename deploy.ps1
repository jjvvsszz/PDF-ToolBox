param(
    [string]$BindHost = $env:HOST,
    [string]$Port = $env:PORT,
    [string]$Workers = $env:WORKERS,
    [string]$AppDir = $PSScriptRoot,
    [switch]$InstallService,
    [switch]$InstallDeps
)

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072

Function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Function Invoke-Download {
    param([string]$Url, [string]$OutFile)
    Write-Host "  Downloading $Url ..."
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
    if (-not (Test-Path $OutFile)) {
        throw "Download failed: $OutFile not found"
    }
}

Function Install-Python {
    Write-Host "[Python] Installing..."

    # Python 3.11.9 standalone installer (self-contained, includes everything)
    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $installer = "$env:TEMP\python-installer.exe"

    $installed = $false
    $errors = @()

    # Method 1: direct download (most reliable on all Windows versions)
    try {
        Write-Host "  Downloading from python.org..."
        Invoke-Download -Url $pythonUrl -OutFile $installer
        Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -NoNewWindow
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
        $installed = $true
    } catch {
        $errors += "Direct download: $_"
    }

    # Method 2: winget
    if (-not $installed -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "  Trying winget..."
        try {
            winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
            $installed = $true
        } catch {
            $errors += "winget: $_"
        }
    }

    # Method 3: choco
    if (-not $installed -and (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "  Trying chocolatey..."
        try {
            choco install python311 -y --limit-output --ignore-dependencies
            $installed = $true
        } catch {
            $errors += "choco: $_"
        }
    }

    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    refreshenv -ErrorAction SilentlyContinue

    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Host "ERROR: All Python installation methods failed:"
        $errors | ForEach-Object { Write-Host "  $_" }
        Write-Host "Install Python 3.11 manually: https://www.python.org/downloads/"
        exit 1
    }
    Write-Host "[Python] $(python --version)"
}

Function Install-LibreOffice {
    Write-Host "[LibreOffice] Installing..."
    $libreOfficePath = "$env:ProgramFiles\LibreOffice\program\soffice.exe"
    if (Test-Path $libreOfficePath) {
        Write-Host "[LibreOffice] Already installed at $libreOfficePath"
        return
    }

    $loUrl = "https://download.documentfoundation.org/libreoffice/stable/24.8.4/win/x86_64/LibreOffice_24.8.4_Win_x86-64.msi"
    $installer = "$env:TEMP\libreoffice-installer.msi"
    $installed = $false

    # Method 1: direct download
    try {
        Write-Host "  Downloading from libreoffice.org..."
        Invoke-Download -Url $loUrl -OutFile $installer
        Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$installer`" /qn /norestart" -Wait -NoNewWindow
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
        $installed = $true
    } catch {
        Write-Host "  Direct download failed: $_"
    }

    # Method 2: winget
    if (-not $installed -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "  Trying winget..."
        try {
            winget install --id TheDocumentFoundation.LibreOffice --silent --accept-package-agreements --accept-source-agreements
            $installed = $true
        } catch {}
    }

    # Method 3: choco
    if (-not $installed -and (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "  Trying chocolatey..."
        try {
            choco install libreoffice-fresh -y --limit-output
            $installed = $true
        } catch {}
    }

    if (Test-Path $libreOfficePath) {
        Write-Host "[LibreOffice] Installed at $libreOfficePath"
    } else {
        Write-Host "WARNING: LibreOffice installation failed. Office-to-PDF will not work."
        Write-Host "  Install manually: https://www.libreoffice.org/download/"
    }
}

Function Install-NSSM {
    Write-Host "[NSSM] Installing..."

    if (Get-Command nssm -ErrorAction SilentlyContinue) {
        Write-Host "[NSSM] Already installed."
        return
    }

    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $nssmZip = "$env:TEMP\nssm.zip"
    $nssmDir = "$env:ProgramFiles\nssm"
    $installed = $false

    # Method 1: direct download (NSSM is just a zip with an exe, no installer needed)
    try {
        Write-Host "  Downloading from nssm.cc..."
        Invoke-Download -Url $nssmUrl -OutFile $nssmZip
        Expand-Archive -Path $nssmZip -DestinationPath $nssmDir -Force
        Remove-Item $nssmZip -Force -ErrorAction SilentlyContinue
        $nssmExe = Get-ChildItem -Path $nssmDir -Filter nssm.exe -Recurse | Select-Object -First 1
        if ($nssmExe) {
            Copy-Item $nssmExe.FullName "$env:windir\system32" -Force
        }
        $installed = $true
    } catch {
        Write-Host "  Direct download failed: $_"
    }

    # Method 2: winget
    if (-not $installed -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "  Trying winget..."
        try {
            winget install --id NSSM.NSSM --silent --accept-package-agreements --accept-source-agreements
            $installed = $true
        } catch {}
    }

    # Method 3: choco
    if (-not $installed -and (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "  Trying chocolatey..."
        try {
            choco install nssm -y --limit-output
            $installed = $true
        } catch {}
    }

    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    refreshenv -ErrorAction SilentlyContinue

    if (Get-Command nssm -ErrorAction SilentlyContinue) {
        Write-Host "[NSSM] Installed."
    } else {
        Write-Host "WARNING: NSSM installation failed. Service registration will not work."
        Write-Host "  Install manually: https://nssm.cc/download"
    }
}

if (-not $BindHost) { $BindHost = "0.0.0.0" }
if (-not $Port) { $Port = "8000" }
if (-not $Workers) { $Workers = "4" }

$ErrorActionPreference = "Stop"

Write-Host "=== PDF Toolbox Deploy ==="
Write-Host "AppDir: $AppDir"
Write-Host "Host:   $BindHost"
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

    nssm install $serviceName "$uvicornExe" "app.main:app --host $BindHost --port $Port --workers $Workers" 2>$null
    nssm set $serviceName AppDirectory $AppDir
    nssm set $serviceName AppEnvironmentExtra "HOST=$BindHost`nPORT=$Port`nWORKERS=$Workers"
    nssm set $serviceName Start SERVICE_AUTO_START
    nssm start $serviceName

    Write-Host ""
    Write-Host "Service '$serviceName' installed and started."
    Write-Host "http://${BindHost}:${Port}"
} else {
    Write-Host ""
    Write-Host "=== To run the app ==="
    Write-Host "  & `"$uvicornExe`" app.main:app --host $BindHost --port $Port --workers $Workers"
    Write-Host ""
    Write-Host "=== To install as Windows Service ==="
    Write-Host "  .\deploy.ps1 -InstallService"
    Write-Host ""
    Write-Host "=== First-time complete setup ==="
    Write-Host "  .\deploy.ps1 -InstallDeps -InstallService"
    Write-Host ""
    Write-Host "After service install, access: http://${BindHost}:${Port}"
}
