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
$serviceName = "PDFToolbox"

Function Invoke-Native {
    # Executa um comando externo e aborta se o codigo de saida for diferente de zero.
    param([string]$Description, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: $Description failed (exit code $LASTEXITCODE)"
        exit 1
    }
}

# Parar o servico antes de atualizar dependencias: no Windows os .pyd/.dll carregados
# ficam bloqueados e o pip falha ao substitui-los.
$existing = Get-Service $serviceName -ErrorAction SilentlyContinue
if ($existing -and $existing.Status -ne "Stopped") {
    Write-Host "Stopping existing service: $serviceName"
    Stop-Service $serviceName -Force
    $existing.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(60))
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "Creating virtual environment..."
    Invoke-Native "venv creation" { python -m venv $venvPath }
}

Write-Host "Installing pip dependencies..."
$env:PIP_REQUIRE_VIRTUALENV = "false"
Invoke-Native "pip upgrade" { & $pythonExe -m pip install --upgrade pip --disable-pip-version-check }
Invoke-Native "pip install" { & $pythonExe -m pip install -r (Join-Path $AppDir "requirements.txt") --disable-pip-version-check }
Invoke-Native "dependency check" { & $pythonExe -c "import fastapi, uvicorn, fitz, pikepdf, img2pdf, pdf2docx, numpy, PIL" }
Write-Host "Pip dependencies installed."

$uploadsDir = Join-Path $AppDir "uploads"
$logsDir = Join-Path $AppDir "logs"
New-Item -ItemType Directory -Force -Path $uploadsDir, $logsDir | Out-Null

$uvicornArgs = "-m uvicorn app.main:app --host $BindHost --port $Port --workers $Workers --proxy-headers"

# Variaveis extras da aplicacao: app.env na pasta do app (KEY=VALUE por linha, fora do Git).
# Reaplicadas a cada deploy, para nao se perderem quando o servico e reconfigurado.
$appEnv = @("HOST=$BindHost", "PORT=$Port", "WORKERS=$Workers")
$appEnvFile = Join-Path $AppDir "app.env"
if (Test-Path $appEnvFile) {
    foreach ($line in Get-Content $appEnvFile) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        if ($line -notmatch '^[A-Za-z_][A-Za-z0-9_]*=') {
            Write-Host "WARNING: ignorando linha invalida em app.env: $line"
            continue
        }
        $name = $line.Split("=", 2)[0]
        if ($name -in @("HOST", "PORT", "WORKERS")) { continue }
        $appEnv += $line
    }
    Write-Host "app.env: $($appEnv.Count - 3) variavel(is) extra(s)"
}

if ($InstallService) {
    if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: NSSM not found. Run with -InstallDeps or install from https://nssm.cc/download"
        exit 1
    }

    if (-not (Get-Service $serviceName -ErrorAction SilentlyContinue)) {
        Invoke-Native "nssm install" { nssm install $serviceName "$pythonExe" }
    }
    # Sempre reaplica a configuracao, para que um redeploy atualize porta/workers/caminhos
    Invoke-Native "nssm set Application" { nssm set $serviceName Application "$pythonExe" }
    Invoke-Native "nssm set AppParameters" { nssm set $serviceName AppParameters $uvicornArgs }
    Invoke-Native "nssm set AppDirectory" { nssm set $serviceName AppDirectory $AppDir }
    Invoke-Native "nssm set AppEnvironmentExtra" { nssm set $serviceName AppEnvironmentExtra @appEnv }
    Invoke-Native "nssm set Start" { nssm set $serviceName Start SERVICE_AUTO_START }
    Invoke-Native "nssm set AppStdout" { nssm set $serviceName AppStdout (Join-Path $logsDir "service.log") }
    Invoke-Native "nssm set AppStderr" { nssm set $serviceName AppStderr (Join-Path $logsDir "service.log") }
    Invoke-Native "nssm set AppRotateFiles" { nssm set $serviceName AppRotateFiles 1 }
    Invoke-Native "nssm set AppRotateOnline" { nssm set $serviceName AppRotateOnline 1 }
    Invoke-Native "nssm set AppRotateBytes" { nssm set $serviceName AppRotateBytes 10485760 }
    Invoke-Native "nssm set AppExit" { nssm set $serviceName AppExit Default Restart }

    Start-Service $serviceName

    # Health check: espera o servidor responder
    $healthHost = if ($BindHost -eq "0.0.0.0") { "127.0.0.1" } else { $BindHost }
    $healthUrl = "http://${healthHost}:${Port}/health"
    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        try {
            $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { $healthy = $true; break }
        } catch {}
    }

    Write-Host ""
    if ($healthy) {
        Write-Host "Service '$serviceName' is running and healthy."
        Write-Host "http://${BindHost}:${Port}"
    } else {
        Write-Host "ERROR: Service '$serviceName' did not respond at $healthUrl"
        Write-Host "  Check logs: $(Join-Path $logsDir 'service.log')"
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "=== To run the app ==="
    Write-Host "  & `"$pythonExe`" $uvicornArgs"
    Write-Host ""
    Write-Host "=== To install as Windows Service ==="
    Write-Host "  .\deploy.ps1 -InstallService"
    Write-Host ""
    Write-Host "=== First-time complete setup ==="
    Write-Host "  .\deploy.ps1 -InstallDeps -InstallService"
    Write-Host ""
    Write-Host "After service install, access: http://${BindHost}:${Port}"
}
