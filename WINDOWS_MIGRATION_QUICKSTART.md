# Windows Migration Quickstart

## 1) Copy runtime

Copy full folder to Windows, recommended path:

`C:\openclaw_runtime`

## 2) Prepare environment

Open PowerShell in `C:\openclaw_runtime`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set secret:

```powershell
setx SUPERSET_PASS "YOUR_REAL_PASSWORD"
```

Restart PowerShell after `setx`.

## 3) Verify Lark CLI

```powershell
lark-cli auth status --verify
```

If needed, login with your profile (default `cs-support`).

## 4) Edit XML path once

Open and replace `C:\openclaw_runtime` if your path is different:

- `windows_task_normal_mode_startup.xml`
- `windows_task_scheduled_run_0805.xml`

Also ensure `SUPERSET_PASS` exists in the same Windows user/account that runs Task Scheduler.

## 5) Import task(s)

```powershell
schtasks /Create /TN "OpenClaw-NormalMode" /XML ".\windows_task_normal_mode_startup.xml" /F
schtasks /Create /TN "OpenClaw-ScheduledRun-0805" /XML ".\windows_task_scheduled_run_0805.xml" /F
```

Run once to verify:

```powershell
schtasks /Run /TN "OpenClaw-NormalMode"
schtasks /Run /TN "OpenClaw-ScheduledRun-0805"
```

## 6) Start now (first run)

```powershell
.\start_normal_mode.ps1
```

## 7) Health check

```powershell
.\health_gate.ps1
```

Expected: all checks passed.

## 8) Operations

```powershell
.\stop_normal_mode.ps1
.\start_normal_mode.ps1
Get-Content .\logs\normal-mode\normal_mode.log -Tail 100
```

## Notes

- Internal scheduler in `normal-mode` already handles daily 08:00.
- The 08:05 task is a backup trigger to reduce missed delivery risk.
