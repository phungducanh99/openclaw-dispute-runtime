Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RootDir "logs\normal-mode"
$StateDir = Join-Path $RootDir "state"
$PidFile = Join-Path $StateDir "normal_mode.pid"
$LogFile = Join-Path $LogDir "normal_mode.log"
$SkipPreflight = if ($env:SKIP_PREFLIGHT) { [int]$env:SKIP_PREFLIGHT } else { 0 }
function Resolve-PythonBin {
  if ($env:PYTHON_BIN) { return $env:PYTHON_BIN }
  $venvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  return "python"
}

New-Item -Path $LogDir -ItemType Directory -Force | Out-Null
New-Item -Path $StateDir -ItemType Directory -Force | Out-Null

if (Test-Path $PidFile) {
  $existingPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
  if ($existingPid) {
    $existingProc = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
    if ($existingProc) {
      Write-Output "normal-mode is already running (pid=$existingPid)"
      exit 0
    }
  }
}

if (-not $env:SUPERSET_PASS) {
  throw "SUPERSET_PASS is required in environment"
}

Set-Location $RootDir
if ($SkipPreflight -ne 1) {
  $env:PYTHON_BIN = Resolve-PythonBin
  & "$RootDir\security_preflight.ps1"
}

$runner = "Set-Location '$RootDir'; `$env:PYTHON_BIN='$(Resolve-PythonBin)'; & '$RootDir\run_normal_mode_supervisor.ps1' *>> '$LogFile'"
$proc = Start-Process -FilePath "powershell.exe" `
  -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $runner
  ) `
  -PassThru `
  -WindowStyle Hidden

Set-Content -Path $PidFile -Value $proc.Id -NoNewline
Write-Output "normal-mode started (pid=$($proc.Id))"
Write-Output "log file: $LogFile"
