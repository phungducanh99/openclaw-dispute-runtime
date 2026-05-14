Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RootDir "logs\auto-heal"
$OpsLog = Join-Path $RootDir "deploy_log.md"

New-Item -Path $LogDir -ItemType Directory -Force | Out-Null
Set-Location $RootDir

function Write-OpsLog([string]$action, [string]$result, [string]$notes) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $line = @"
Time: $ts
Operator: auto-heal-task
Action: $action
Version: auto
Result: $result
Health gate: $result
Notes: $notes

"@
  Add-Content -Path $OpsLog -Value $line
}

try {
  $healthOutput = & "$RootDir\health_gate.ps1" 2>&1 | Out-String
  if ($LASTEXITCODE -eq 0 -and $healthOutput -match "\[health-gate\]\[pass\]") {
    Write-Output "[auto-heal] healthy, no action"
    exit 0
  }
} catch {
  # Continue to remediation.
}

Write-Output "[auto-heal] unhealthy detected -> restart sequence"

try {
  & "$RootDir\stop_normal_mode.ps1" | Out-Null
} catch {
  # Ignore stop errors; next start may still succeed.
}

Start-Sleep -Seconds 2

& "$RootDir\start_normal_mode.ps1" | Out-Null
Start-Sleep -Seconds 8

$postOutput = & "$RootDir\health_gate.ps1" 2>&1 | Out-String
if ($LASTEXITCODE -eq 0 -and $postOutput -match "\[health-gate\]\[pass\]") {
  Write-Output "[auto-heal] recovered"
  Write-OpsLog "incident-auto-heal" "PASS" "Auto restart succeeded."
  exit 0
}

Write-Output "[auto-heal] recovery failed"
Write-OpsLog "incident-auto-heal" "FAIL" "Auto restart failed. Manual intervention required."
exit 1
