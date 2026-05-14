#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${LARK_PROFILE:-cs-support}"
CHAT_ID="${LARK_CHAT_ID:-oc_ae3254d5860b01981b81f90f085cd416}"
PAGE_SIZE="${PAGE_SIZE:-20}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

echo "[health-gate] step1: process liveness"
SUPERVISOR_COUNT="$(ps aux | grep 'run_normal_mode_supervisor.sh' | grep -v grep | wc -l | tr -d ' ' || true)"
WORKER_COUNT="$(ps aux | grep 'main.py normal-mode' | grep -v grep | wc -l | tr -d ' ' || true)"
SUPERVISOR_COUNT="${SUPERVISOR_COUNT:-0}"
WORKER_COUNT="${WORKER_COUNT:-0}"
if [[ "$SUPERVISOR_COUNT" -lt 1 || "$WORKER_COUNT" -lt 1 ]]; then
  echo "[health-gate][fail] process not alive (supervisor=$SUPERVISOR_COUNT, worker=$WORKER_COUNT)"
  exit 1
fi
echo "[health-gate][ok] process alive (supervisor=$SUPERVISOR_COUNT, worker=$WORKER_COUNT)"

echo "[health-gate] step2: mention-loop send path"
if [[ -z "${SUPERSET_PASS:-}" ]]; then
  echo "[health-gate][fail] SUPERSET_PASS missing"
  exit 1
fi
LOOP_JSON="$($PYTHON_BIN main.py mention-loop --page-size "$PAGE_SIZE")"
echo "$LOOP_JSON"
if echo "$LOOP_JSON" | grep -q '"reply_errors": \[[^]]'; then
  echo "[health-gate][fail] mention-loop has reply_errors"
  exit 1
fi
echo "[health-gate][ok] mention-loop reply path healthy"

echo "[health-gate] step3: lark read sanity"
LIST_JSON="$(lark-cli --profile "$PROFILE" im +chat-messages-list --as user --chat-id "$CHAT_ID" --page-size 1 --sort desc --format json)"
if ! echo "$LIST_JSON" | grep -q '"ok": true'; then
  echo "[health-gate][fail] lark list sanity failed"
  echo "$LIST_JSON"
  exit 1
fi
echo "[health-gate][ok] lark read sanity pass"

echo "[health-gate][pass] all checks passed"
