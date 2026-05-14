Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Profile = if ($env:LARK_PROFILE) { $env:LARK_PROFILE } else { "cs-support" }
function Resolve-PythonBin {
  if ($env:PYTHON_BIN) { return $env:PYTHON_BIN }
  $venvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  return "python"
}
$PythonBin = Resolve-PythonBin

Write-Output "[preflight] root=$RootDir"
Write-Output "[preflight] profile=$Profile"

if (-not $env:SUPERSET_PASS) {
  throw "[preflight][error] SUPERSET_PASS is required in environment"
}

if (-not (Get-Command lark-cli -ErrorAction SilentlyContinue)) {
  throw "[preflight][error] lark-cli not found"
}

if (-not (Get-Command $PythonBin -ErrorAction SilentlyContinue)) {
  throw "[preflight][error] $PythonBin not found"
}

Write-Output "[preflight] check lark auth/keychain"
$null = & lark-cli --profile $Profile auth status 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "[preflight][error] lark auth/keychain unavailable for profile=$Profile"
}

Write-Output "[preflight] check superset auth/query"
Set-Location $RootDir
$py = @"
import json
from pathlib import Path
from superset_client import SupersetClient
cfg=json.loads(Path('config/production.json').read_text(encoding='utf-8'))
sc=cfg['superset']
auth=sc['auth']
ds=sc['dataset_ids']['dispute_primary']
c=SupersetClient(host=sc['host'], username=auth['username'], password_env=auth['password_secret_ref'])
c.query(datasource_id=ds, columns=[], metrics=[{'expressionType':'SQL','label':'disputes_distinct','sqlExpression':'uniqExact(disputes_key)'}], row_limit=1)
print("ok")
"@
& $PythonBin -c $py | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "[preflight][error] superset auth/query failed"
}

Write-Output "[preflight] check singleton process"
$running = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*main.py normal-mode*" } |
  Measure-Object |
  Select-Object -ExpandProperty Count
if ($running -gt 0) {
  throw "[preflight][error] existing normal-mode process count=$running"
}

Write-Output "[preflight] OK"
