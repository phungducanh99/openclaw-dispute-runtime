#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${LARK_PROFILE:-cs-support}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[preflight] root=$ROOT_DIR"
echo "[preflight] profile=$PROFILE"

if [[ -z "${SUPERSET_PASS:-}" ]]; then
  echo "[preflight][error] SUPERSET_PASS is required in environment"
  exit 1
fi

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "[preflight][error] lark-cli not found"
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[preflight][error] $PYTHON_BIN not found"
  exit 1
fi

echo "[preflight] check lark auth/keychain"
if ! lark-cli --profile "$PROFILE" auth status >/dev/null 2>&1; then
  echo "[preflight][error] lark auth/keychain unavailable for profile=$PROFILE"
  echo "[preflight][hint] run bot outside sandbox/escalated, then retry"
  exit 1
fi

echo "[preflight] check superset auth/query"
cd "$ROOT_DIR"
"$PYTHON_BIN" -c "import json; from pathlib import Path; from superset_client import SupersetClient; cfg=json.loads(Path('config/production.json').read_text()); sc=cfg['superset']; auth=sc['auth']; ds=sc['dataset_ids']['dispute_primary']; c=SupersetClient(host=sc['host'], username=auth['username'], password_env=auth['password_secret_ref']); c.query(datasource_id=ds, columns=[], metrics=[{'expressionType':'SQL','label':'disputes_distinct','sqlExpression':'uniqExact(disputes_key)'}], row_limit=1)"

echo "[preflight] check singleton process"
RUNNING_COUNT="$(ps aux | grep 'main.py normal-mode' | grep -v grep | wc -l | tr -d ' ' || true)"
if [[ -z "${RUNNING_COUNT:-}" ]]; then
  RUNNING_COUNT="0"
fi
if [[ "${RUNNING_COUNT:-0}" != "0" ]]; then
  echo "[preflight][error] existing normal-mode process count=$RUNNING_COUNT"
  echo "[preflight][hint] run ./stop_normal_mode.sh (or pkill old process) before start"
  exit 1
fi

echo "[preflight] OK"
