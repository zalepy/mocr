<#
.SYNOPSIS
    Start the Screen OCR tray app.

.DESCRIPTION
    By default the app runs in the background (pythonw, no console window).
    With -DebugMode it runs in the current console with --debug output;
    stop it with Ctrl+C or the tray menu's Exit.

    Refuses to start a second instance. Use stop.ps1 to stop a background instance.

.EXAMPLE
    .\start.ps1
.EXAMPLE
    .\start.ps1 -DebugMode
#>
param(
    [switch]$DebugMode
)

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$script = Join-Path $root 'screen_ocr.py'
$venvScripts = Join-Path $root '.venv\Scripts'
$python = Join-Path $venvScripts 'python.exe'
$pythonw = Join-Path $venvScripts 'pythonw.exe'

if (-not (Test-Path $python)) {
    Write-Error "Virtual environment not found at $venvScripts. Create it with: uv sync"
    exit 1
}

# The venv's python.exe/pythonw.exe is a launcher that spawns the real
# interpreter as a child, so match on the command line rather than a PID.
$running = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*$script*" }

if ($running) {
    $ids = ($running | ForEach-Object { $_.ProcessId }) -join ', '
    Write-Host "Screen OCR is already running (PID $ids). Use .\stop.ps1 to stop it."
    exit 0
}

if ($DebugMode) {
    Write-Host "Starting Screen OCR in debug mode (Ctrl+C or tray Exit to stop)..."
    # Run from the repo root so last_capture.png lands where eval_last.py expects it
    Push-Location $root
    try {
        & $python $script --debug
    }
    finally {
        Pop-Location
    }
}
else {
    $proc = Start-Process -FilePath $pythonw -ArgumentList "`"$script`"" -WorkingDirectory $root -PassThru
    Write-Host "Screen OCR started in background (PID $($proc.Id)). Look for the blue tray icon."
}
