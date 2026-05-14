Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $RootDir "state\normal_mode.pid"

if (-not (Test-Path $PidFile)) {
  Write-Output "normal-mode is not running (no pid file)"
  exit 0
}

$pidText = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not $pidText) {
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  Write-Output "normal-mode pid file was empty; cleaned"
  exit 0
}

$pidNum = [int]$pidText
$proc = Get-Process -Id $pidNum -ErrorAction SilentlyContinue
if ($proc) {
  Stop-Process -Id $pidNum -Force -ErrorAction SilentlyContinue
  Write-Output "normal-mode stopped (pid=$pidNum)"
} else {
  Write-Output "normal-mode process not found (pid=$pidNum); cleaned pid file"
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
