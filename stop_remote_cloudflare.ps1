param()

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$PidFiles = @(
    (Join-Path $RuntimeDir "cloudflared.pid"),
    (Join-Path $RuntimeDir "uvicorn.pid")
)

foreach ($pidFile in $PidFiles) {
    if (-not (Test-Path $pidFile)) {
        continue
    }

    $rawPid = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $rawPid) {
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        continue
    }

    try {
        Stop-Process -Id ([int]$rawPid) -Force -ErrorAction Stop
    }
    catch {
    }

    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "Cloudflare tunnel and local backend stopped."
