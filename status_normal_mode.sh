#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT_DIR/state/normal_mode.pid"
LOG_FILE="$ROOT_DIR/logs/normal-mode/normal_mode.log"

if [[ ! -f "$PID_FILE" ]]; then
  echo "normal-mode status: stopped"
  exit 0
fi

PID="$(cat "$PID_FILE" || true)"
if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
  echo "normal-mode status: running (pid=$PID)"
  echo "log file: $LOG_FILE"
  exit 0
fi

echo "normal-mode status: stale pid file (pid=${PID:-unknown})"
echo "log file: $LOG_FILE"
exit 0
