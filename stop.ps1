<#
.SYNOPSIS
    Stop the running Screen OCR tray app.

.DESCRIPTION
    Finds every python/pythonw process running this repo's screen_ocr.py
    (the venv launcher and its child interpreter) and stops them.

    Note: the process is terminated, not asked to quit, so the tray icon may
    linger until the mouse hovers over it. Use the tray menu's Exit for a clean shutdown.

.EXAMPLE
    .\stop.ps1
#>

$ErrorActionPreference = 'Stop'

$script = Join-Path $PSScriptRoot 'screen_ocr.py'

$running = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*$script*" }

if (-not $running) {
    Write-Host "Screen OCR is not running."
    exit 0
}

foreach ($p in $running) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped PID $($p.ProcessId) ($($p.Name))"
    }
    catch {
        # The child interpreter may already be gone after its launcher was stopped
        if (Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue) {
            Write-Warning "Failed to stop PID $($p.ProcessId): $_"
        }
    }
}
