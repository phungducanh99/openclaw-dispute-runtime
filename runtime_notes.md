# OpenClaw Runtime Notes

- `production.yaml` remains the human-readable source config.
- `production.json` is the execution config used by the Python runtime because `PyYAML` is not available in the current environment.
- Do not store raw Superset query payloads in runtime artifacts.

## Normal Mode Launcher

- Start:
- `SUPERSET_PASS='<your-pass>' ./start_normal_mode.sh`
  - mặc định có chạy preflight bảo mật trước khi start
  - cần bỏ qua preflight (không khuyến nghị): `SKIP_PREFLIGHT=1 SUPERSET_PASS='<your-pass>' ./start_normal_mode.sh`
- Stop:
  - `./stop_normal_mode.sh`
- Status:
  - `./status_normal_mode.sh`
- Health gate (bắt buộc trước khi chốt "bot chạy bình thường"):
  - `SUPERSET_PASS='<your-pass>' ./health_gate.sh`

Log path:

- `logs/normal-mode/normal_mode.log`
- `SECURITY_RUNBOOK.md`

## Quick Views

- Graph view:
  - `FLOW_GRAPH.md`
- Operational guards:
  - `OPERATIONS_GUARDS.md`
- Role playbooks:
  - `prompts/role_playbooks.md`

## Data Retention

- Runtime enforces auto-cleanup for old JSON artifacts:
  - `logs/runs/*.json`
  - `artifacts/snapshots/*.json`
  - `artifacts/analysis/*.json`
- TTL: 30 days.
- `latest_*.json` files are always kept.
