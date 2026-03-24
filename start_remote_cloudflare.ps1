param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$UvicornOutLog = Join-Path $RuntimeDir "uvicorn.out.log"
$UvicornErrLog = Join-Path $RuntimeDir "uvicorn.err.log"
$TunnelOutLog = Join-Path $RuntimeDir "cloudflared.out.log"
$TunnelErrLog = Join-Path $RuntimeDir "cloudflared.err.log"
$UvicornPidFile = Join-Path $RuntimeDir "uvicorn.pid"
$TunnelPidFile = Join-Path $RuntimeDir "cloudflared.pid"

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

function Get-LiveProcessFromPidFile {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return $null
    }

    $rawPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $rawPid) {
        return $null
    }

    try {
        $process = Get-Process -Id ([int]$rawPid) -ErrorAction Stop
        return $process
    }
    catch {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Start-ManagedProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$OutLogPath,
        [string]$ErrLogPath,
        [string]$PidFile
    )

    $existing = Get-LiveProcessFromPidFile -PidFile $PidFile
    if ($existing) {
        return $existing
    }

    foreach ($logPath in @($OutLogPath, $ErrLogPath)) {
        if (Test-Path $logPath) {
            Remove-Item $logPath -Force
        }
    }

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $OutLogPath `
        -RedirectStandardError $ErrLogPath `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path $PidFile -Value $process.Id
    return $process
}

function Test-PortAvailable {
    param(
        [string]$HostAddress,
        [int]$TestPort
    )

    $listener = $null

    try {
        $ipAddress = [System.Net.IPAddress]::Parse($HostAddress)
        $listener = [System.Net.Sockets.TcpListener]::new($ipAddress, $TestPort)
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Get-AvailablePort {
    param(
        [string]$HostAddress,
        [int]$PreferredPort,
        [int]$SearchSpan = 20
    )

    foreach ($candidate in $PreferredPort..($PreferredPort + $SearchSpan)) {
        if (Test-PortAvailable -HostAddress $HostAddress -TestPort $candidate) {
            return $candidate
        }
    }

    throw "No free TCP port found between $PreferredPort and $($PreferredPort + $SearchSpan)."
}

function Wait-ForUrl {
    param(
        [string[]]$LogPaths,
        [int]$TimeoutSeconds = 45
    )

    $pattern = 'https://[-a-z0-9]+\.trycloudflare\.com'
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        foreach ($logPath in $LogPaths) {
            if (Test-Path $logPath) {
                $content = Get-Content $logPath -Raw -ErrorAction SilentlyContinue
                if ($content -match $pattern) {
                    return $matches[0]
                }
            }
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Cloudflare tunnel URL not found within $TimeoutSeconds seconds. Check $TunnelOutLog and $TunnelErrLog"
}

function Test-LocalEndpoint {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            return
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    throw "Local app did not answer on $Url within $TimeoutSeconds seconds. Check $UvicornOutLog and $UvicornErrLog"
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available in PATH."
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    throw "cloudflared is not available in PATH."
}

$SelectedPort = Get-AvailablePort -HostAddress $BindHost -PreferredPort $Port

$uvicornArgs = @(
    "-m", "uvicorn",
    "app:app",
    "--host", $BindHost,
    "--port", "$SelectedPort"
)

$uvicorn = Start-ManagedProcess -FilePath "python" -ArgumentList $uvicornArgs -OutLogPath $UvicornOutLog -ErrLogPath $UvicornErrLog -PidFile $UvicornPidFile
Test-LocalEndpoint -Url "http://$BindHost`:$SelectedPort"

$tunnelArgs = @(
    "tunnel",
    "--url", "http://$BindHost`:$SelectedPort",
    "--no-autoupdate"
)

$tunnel = Start-ManagedProcess -FilePath $cloudflared.Source -ArgumentList $tunnelArgs -OutLogPath $TunnelOutLog -ErrLogPath $TunnelErrLog -PidFile $TunnelPidFile
$publicUrl = Wait-ForUrl -LogPaths @($TunnelOutLog, $TunnelErrLog)

Write-Host ""
Write-Host "Local app:       http://$BindHost`:$SelectedPort"
Write-Host "Cloudflare URL:  $publicUrl"
Write-Host "Uvicorn PID:     $($uvicorn.Id)"
Write-Host "Cloudflared PID: $($tunnel.Id)"
Write-Host "Logs:"
Write-Host "  $UvicornOutLog"
Write-Host "  $UvicornErrLog"
Write-Host "  $TunnelOutLog"
Write-Host "  $TunnelErrLog"
