Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$IntervalSec = if ($env:INTERVAL_SEC) { [int]$env:INTERVAL_SEC } else { 30 }
$PageSize = if ($env:PAGE_SIZE) { [int]$env:PAGE_SIZE } else { 20 }
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

Set-Location $RootDir

while ($true) {
  & $PythonBin "main.py" "normal-mode" "--page-size" "$PageSize" "--interval-sec" "$IntervalSec" "--watch-restart"
  $exitCode = $LASTEXITCODE
  if ($exitCode -eq 0) {
    exit 0
  }
  Write-Output "{""status"":""restarting"",""reason"":""normal-mode exited"",""exit_code"":$exitCode}"
  Start-Sleep -Seconds 2
}
