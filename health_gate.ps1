Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Profile = if ($env:LARK_PROFILE) { $env:LARK_PROFILE } else { "cs-support" }
$ChatId = if ($env:LARK_CHAT_ID) { $env:LARK_CHAT_ID } else { "oc_ae3254d5860b01981b81f90f085cd416" }
$PageSize = if ($env:PAGE_SIZE) { [int]$env:PAGE_SIZE } else { 20 }
function Resolve-PythonBin {
  if ($env:PYTHON_BIN) { return $env:PYTHON_BIN }
  $venvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  return "python"
}
$PythonBin = Resolve-PythonBin

Set-Location $RootDir

Write-Output "[health-gate] step1: process liveness"
$supervisorCount = (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_normal_mode_supervisor.ps1*" } | Measure-Object).Count
$workerCount = (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*main.py normal-mode*" } | Measure-Object).Count
if ($supervisorCount -lt 1 -or $workerCount -lt 1) {
  throw "[health-gate][fail] process not alive (supervisor=$supervisorCount, worker=$workerCount)"
}
Write-Output "[health-gate][ok] process alive (supervisor=$supervisorCount, worker=$workerCount)"

Write-Output "[health-gate] step2: mention-loop send path"
if (-not $env:SUPERSET_PASS) {
  throw "[health-gate][fail] SUPERSET_PASS missing"
}
$loopJson = & $PythonBin "main.py" "mention-loop" "--page-size" "$PageSize"
Write-Output $loopJson
if ($LASTEXITCODE -ne 0) {
  throw "[health-gate][fail] mention-loop execution failed"
}
$loopObj = $loopJson | ConvertFrom-Json
if ($loopObj.reply_errors -and $loopObj.reply_errors.Count -gt 0) {
  throw "[health-gate][fail] mention-loop has reply_errors"
}
Write-Output "[health-gate][ok] mention-loop reply path healthy"

Write-Output "[health-gate] step3: lark read sanity"
$listJson = & lark-cli --profile $Profile im +chat-messages-list --as user --chat-id $ChatId --page-size 1 --sort desc --format json
if ($LASTEXITCODE -ne 0) {
  throw "[health-gate][fail] lark list sanity failed"
}
$listObj = $listJson | ConvertFrom-Json
if (-not $listObj.ok) {
  throw "[health-gate][fail] lark list sanity failed"
}
Write-Output "[health-gate][ok] lark read sanity pass"
Write-Output "[health-gate][pass] all checks passed"
