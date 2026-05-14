#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT_DIR/state/normal_mode.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "normal-mode is not running (no pid file)"
  exit 0
fi

PID="$(cat "$PID_FILE" || true)"
if [[ -z "${PID:-}" ]]; then
  rm -f "$PID_FILE"
  echo "normal-mode pid file was empty; cleaned"
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "normal-mode stopped (pid=$PID)"
else
  echo "normal-mode process not found (pid=$PID); cleaned pid file"
fi

rm -f "$PID_FILE"
