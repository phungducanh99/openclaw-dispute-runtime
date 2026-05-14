#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
INTERVAL_SEC="${INTERVAL_SEC:-5}"
PAGE_SIZE="${PAGE_SIZE:-20}"

CHILD_PID=""
cleanup() {
  if [[ -n "${CHILD_PID:-}" ]] && kill -0 "$CHILD_PID" 2>/dev/null; then
    kill "$CHILD_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup INT TERM

cd "$ROOT_DIR"
while true; do
  python3 main.py normal-mode --page-size "$PAGE_SIZE" --interval-sec "$INTERVAL_SEC" --watch-restart &
  CHILD_PID=$!
  set +e
  wait "$CHILD_PID"
  EXIT_CODE=$?
  set -e
  CHILD_PID=""
  if [[ "$EXIT_CODE" -eq 0 ]]; then
    exit 0
  fi
  echo "{\"status\":\"restarting\",\"reason\":\"normal-mode exited\",\"exit_code\":$EXIT_CODE}"
  sleep 2
done
