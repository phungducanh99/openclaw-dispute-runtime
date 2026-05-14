#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs/normal-mode"
PID_FILE="$ROOT_DIR/state/normal_mode.pid"
LOG_FILE="$LOG_DIR/normal_mode.log"

INTERVAL_SEC="${INTERVAL_SEC:-5}"
PAGE_SIZE="${PAGE_SIZE:-20}"

mkdir -p "$LOG_DIR" "$ROOT_DIR/state"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" || true)"
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "normal-mode is already running (pid=$PID)"
    exit 0
  fi
fi

if [[ -z "${SUPERSET_PASS:-}" ]]; then
  echo "SUPERSET_PASS is required in environment"
  exit 1
fi

cd "$ROOT_DIR"
if [[ "${SKIP_PREFLIGHT:-0}" != "1" ]]; then
  ./security_preflight.sh
fi
nohup ./run_normal_mode_supervisor.sh >>"$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"
echo "normal-mode started (pid=$PID)"
echo "log file: $LOG_FILE"
