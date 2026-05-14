from __future__ import annotations

import argparse
import atexit
import fcntl
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw dispute runtime")
    parser.add_argument("mode", choices=["scheduled-run", "qa-reply", "mention-loop", "normal-mode"])
    parser.add_argument("--question", default="")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--interval-sec", type=int, default=30)
    parser.add_argument("--watch-restart", action="store_true")
    args = parser.parse_args()

    orchestrator = Orchestrator()
    if args.mode == "scheduled-run":
        result = orchestrator.scheduled_run()
    elif args.mode == "mention-loop":
        result = orchestrator.mention_loop_once(page_size=args.page_size)
    elif args.mode == "normal-mode":
        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        lock_file = Path("state/normal_mode.lock")
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_fp = lock_file.open("w")
        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fp.seek(0)
            lock_fp.truncate()
            lock_fp.write(str(os.getpid()))
            lock_fp.flush()
        except BlockingIOError:
            print(
                json.dumps(
                    {
                        "status": "already_running",
                        "mode": "normal-mode",
                        "lock_file": str(lock_file),
                    },
                    ensure_ascii=True,
                )
            )
            return

        def _release_lock() -> None:
            try:
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                lock_fp.close()
            except OSError:
                pass

        atexit.register(_release_lock)
        watch_paths = [
            Path("main.py"),
            Path("orchestrator.py"),
            Path("config/production.json"),
            Path("agents/group_bot_qa.py"),
            Path("agents/superset_monitor.py"),
        ]
        file_state = _snapshot_files(watch_paths)
        try:
            while True:
                scheduled = orchestrator.maybe_scheduled_run()
                result = orchestrator.mention_loop_once(page_size=args.page_size)
                event = {
                    "ts": datetime.now(tz).isoformat(timespec="seconds"),
                    "mode": "normal-mode",
                    "interval_sec": args.interval_sec,
                    "scheduled": scheduled,
                    "result": result,
                }
                print(json.dumps(event, ensure_ascii=True))
                if args.watch_restart:
                    next_state = _snapshot_files(watch_paths)
                    if next_state != file_state:
                        print(
                            json.dumps(
                                {
                                    "status": "restart_required",
                                    "reason": "runtime files changed",
                                    "mode": "normal-mode",
                                },
                                ensure_ascii=True,
                            )
                        )
                        raise SystemExit(75)
                time.sleep(args.interval_sec)
        except KeyboardInterrupt:
            print(json.dumps({"status": "stopped", "mode": "normal-mode"}, ensure_ascii=True))
            return
    else:
        result = orchestrator.qa_run(args.question)
    print(json.dumps(result, ensure_ascii=True, indent=2))


def _snapshot_files(paths: list[Path]) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for path in paths:
        try:
            snapshot[str(path)] = path.stat().st_mtime
        except FileNotFoundError:
            snapshot[str(path)] = -1.0
    return snapshot


if __name__ == "__main__":
    main()
