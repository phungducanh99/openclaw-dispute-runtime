from __future__ import annotations

import json
import re
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

from agents.comparative_analyst import ComparativeAnalystAgent
from agents.group_bot_qa import GroupBotQAAgent
from agents.report_publisher import ReportPublisherAgent
from agents.superset_monitor import SupersetMonitorAgent
from config_loader import load_config
from json_store import read_json, write_json
from paths import ANALYSIS_ROOT, RUN_LOG_ROOT, SNAPSHOT_ROOT, STATE_ROOT, ensure_runtime_dirs
from time_utils import current_period_weekly, isoformat, now_in_timezone, previous_period_weekly


class Orchestrator:
    def __init__(self, config_name: str = "production.json") -> None:
        self.config = load_config(config_name)
        ensure_runtime_dirs()
        self.monitor: SupersetMonitorAgent | None = None
        self.analyst = ComparativeAnalystAgent(self.config)
        self.publisher = ReportPublisherAgent(self.config)
        self.qa = GroupBotQAAgent(self.config)

    def scheduled_run(self) -> dict[str, Any]:
        current_snapshot, analysis, run_time, now = self._refresh_state()
        self._enforce_retention(days=30)
        publish_result = self.publisher.run(analysis)

        run_log_path = RUN_LOG_ROOT / f"run_{now.strftime('%Y%m%dT%H%M%S')}.json"
        write_json(
            run_log_path,
            {
                "run_time": run_time,
                "snapshot_status": current_snapshot["status"],
                "analysis_status": analysis["status"],
                "publish_status": publish_result["status"],
            },
        )

        return {
            "snapshot": current_snapshot,
            "analysis": analysis,
            "publish_result": publish_result,
        }

    def maybe_scheduled_run(self, now: Any | None = None) -> dict[str, Any]:
        superset_cfg = self.config.get("superset", {})
        openclaw_cfg = self.config.get("openclaw", {})
        timezone_name = str(superset_cfg.get("timezone", "Asia/Ho_Chi_Minh"))
        schedule_text = str(superset_cfg.get("schedule_local_time", "08:00"))
        scheduler_enabled = bool(openclaw_cfg.get("scheduler_enabled", False))
        if not scheduler_enabled:
            return {"status": "disabled", "summary": "scheduler is disabled"}

        current_now = now if now is not None else now_in_timezone(timezone_name)
        hour = 8
        minute = 0
        try:
            hh, mm = schedule_text.split(":", 1)
            hour = int(hh)
            minute = int(mm)
        except (ValueError, TypeError):
            pass

        schedule_dt = current_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        today_key = current_now.date().isoformat()
        scheduler_state_path = STATE_ROOT / "scheduler_state.json"
        scheduler_state = read_json(scheduler_state_path) or {}
        last_success_date = str(scheduler_state.get("last_success_date", ""))

        if current_now < schedule_dt:
            return {
                "status": "waiting",
                "summary": "before schedule window",
                "schedule_local_time": schedule_text,
                "now_local": isoformat(current_now),
            }
        if last_success_date == today_key:
            return {
                "status": "already_ran",
                "summary": "scheduled report already sent today",
                "last_success_date": last_success_date,
            }

        run_result = self.scheduled_run()
        publish_status = str((run_result.get("publish_result") or {}).get("status", ""))
        is_success = publish_status in {"success", "skipped"}
        next_state = {
            "last_attempt_at": isoformat(current_now),
            "last_attempt_date": today_key,
            "last_publish_status": publish_status,
        }
        if is_success:
            next_state["last_success_date"] = today_key
        else:
            next_state["last_success_date"] = last_success_date
        write_json(scheduler_state_path, next_state)

        return {
            "status": "ran" if is_success else "error",
            "summary": "scheduled run executed" if is_success else "scheduled run failed",
            "publish_status": publish_status,
            "scheduled_run": run_result,
        }

    def qa_run(self, question: str) -> dict[str, Any]:
        latest_analysis = self._load_latest_analysis()
        if not latest_analysis:
            _, latest_analysis, _, _ = self._refresh_state()
        if self._needs_snapshot_refresh(question, latest_analysis):
            _, latest_analysis, _, _ = self._refresh_state()
        since_dt = self._extract_since_date(question)
        if since_dt is not None:
            _, latest_analysis, _, _ = self._refresh_state(period_override_start=since_dt)
        qa_payload = self.qa.run(question, latest_analysis, asker_context={"role": "general"}, dialog_context=None)
        days = qa_payload.get("needs_refresh_days")
        if isinstance(days, int) and days >= 2:
            _, refreshed_analysis, _, _ = self._refresh_state(extra_rolling_days=[days])
            qa_payload = self.qa.run(question, refreshed_analysis, asker_context={"role": "general"}, dialog_context=None)
        if self._needs_snapshot_refresh_from_reply(question, qa_payload):
            _, latest_analysis, _, _ = self._refresh_state()
            qa_payload = self.qa.run(question, latest_analysis, asker_context={"role": "general"}, dialog_context=None)
        return qa_payload

    def mention_loop_once(self, page_size: int = 20) -> dict[str, Any]:
        lark = self.config["lark"]
        openclaw_cfg = self.config.get("openclaw", {})
        max_mentions_per_cycle = int(openclaw_cfg.get("mention_max_per_cycle", 5))
        chat_id = lark.get("target_chat_id")
        profile = lark.get("cli_profile", "default")
        if not chat_id:
            return {
                "status": "pending",
                "summary": "missing target_chat_id",
                "processed": 0,
                "replied": 0,
            }

        messages_payload = self._list_recent_messages(profile=profile, chat_id=chat_id, page_size=page_size)
        if messages_payload.get("error"):
            return {
                "status": "warning",
                "summary": "lark_list_failed",
                "processed": 0,
                "replied": 0,
                "error": messages_payload.get("error"),
            }
        messages = messages_payload.get("data", {}).get("messages", [])
        if not messages:
            return {"status": "success", "summary": "no messages", "processed": 0, "replied": 0}
        thread_context_map = self._build_thread_context_map(messages)

        mentions_state_path = STATE_ROOT / "mentions_state.json"
        dialog_state_path = STATE_ROOT / "qa_dialog_state.json"
        mentions_state = read_json(mentions_state_path) or {}
        dialog_state = read_json(dialog_state_path) or {}
        processed_id_list = mentions_state.get("processed_message_ids", [])
        replied_id_list = mentions_state.get("replied_message_ids", [])
        acked_id_list = mentions_state.get("acked_message_ids", [])
        processed_ids = set(processed_id_list)
        replied_ids = set(replied_id_list)
        acked_ids = set(acked_id_list)
        latest_analysis = self._load_latest_analysis()
        if not latest_analysis:
            _, latest_analysis, _, _ = self._refresh_state()

        processed = 0
        replied = 0
        acked = 0
        mention_processed = 0
        refresh_count = 0
        reply_errors: list[dict[str, Any]] = []
        newest_seen = messages[0].get("message_id")

        # Build a stable queue snapshot of pending mentions for queue-position ACK.
        pending_mentions: list[str] = []
        for msg in reversed(messages):
            candidates = [msg, *(msg.get("thread_replies", []) or [])]
            for cand in candidates:
                mid = cand.get("message_id")
                if not mid or mid in processed_ids:
                    continue
                if self._is_mention_to_bot(cand):
                    pending_mentions.append(mid)

        # API returns desc order; process oldest -> newest for stable state transitions.
        stop_due_to_budget = False
        for message in reversed(messages):
            candidates = [message, *(message.get("thread_replies", []) or [])]
            for candidate in candidates:
                message_id = candidate.get("message_id")
                if not message_id:
                    continue
                if message_id in processed_ids:
                    continue

                processed += 1
                if not self._is_mention_to_bot(candidate):
                    processed_ids.add(message_id)
                    if message_id not in processed_id_list:
                        processed_id_list.append(message_id)
                    continue
                if mention_processed >= max_mentions_per_cycle:
                    stop_due_to_budget = True
                    break
                mention_processed += 1

                if message_id not in acked_ids and message_id not in replied_ids:
                    try:
                        queue_before = 0
                        if message_id in pending_mentions:
                            queue_before = pending_mentions.index(message_id)
                        ack_text = "CS support: Em đã nhận yêu cầu, đang xử lý..."
                        if queue_before > 0:
                            ack_text = (
                                f"CS support: Em đã nhận yêu cầu, đang xử lý... "
                                f"(còn {queue_before} yêu cầu trước)"
                            )
                        self._reply_message(
                            profile=profile,
                            message_id=message_id,
                            reply_text=ack_text,
                        )
                        acked_ids.add(message_id)
                        if message_id not in acked_id_list:
                            acked_id_list.append(message_id)
                        acked += 1
                    except subprocess.CalledProcessError:
                        # ACK best-effort; continue to processing reply.
                        pass

                question = candidate.get("content", "")
                if self._needs_snapshot_refresh(question, latest_analysis):
                    if refresh_count < 1:
                        _, latest_analysis, _, _ = self._refresh_state()
                        refresh_count += 1
                since_dt = self._extract_since_date(question)
                if since_dt is not None:
                    _, latest_analysis, _, _ = self._refresh_state(period_override_start=since_dt)
                    refresh_count += 1
                sender = candidate.get("sender", {}) or {}
                sender_key = str(sender.get("id") or sender.get("name") or "unknown")
                sender_dialog_context = dialog_state.get(sender_key)
                asker_context = {
                    "display_name": sender.get("name"),
                    "role": self._infer_role_from_message(candidate),
                }
                thread_id = str(candidate.get("thread_id") or message.get("thread_id") or "")
                qa_payload = self.qa.run(
                    question,
                    latest_analysis,
                    asker_context=asker_context,
                    dialog_context=sender_dialog_context,
                    thread_context_text=thread_context_map.get(thread_id, ""),
                )
                days = qa_payload.get("needs_refresh_days")
                if isinstance(days, int) and days >= 2:
                    if refresh_count < 2:
                        _, latest_analysis, _, _ = self._refresh_state(extra_rolling_days=[days])
                        refresh_count += 1
                    qa_payload = self.qa.run(
                        question,
                        latest_analysis,
                        asker_context=asker_context,
                        dialog_context=sender_dialog_context,
                        thread_context_text=thread_context_map.get(thread_id, ""),
                    )
                if self._needs_snapshot_refresh_from_reply(question, qa_payload):
                    if refresh_count < 2:
                        _, latest_analysis, _, _ = self._refresh_state()
                        refresh_count += 1
                    qa_payload = self.qa.run(
                        question,
                        latest_analysis,
                        asker_context=asker_context,
                        dialog_context=sender_dialog_context,
                        thread_context_text=thread_context_map.get(thread_id, ""),
                    )
                try:
                    if message_id in replied_ids:
                        processed_ids.add(message_id)
                        if message_id not in processed_id_list:
                            processed_id_list.append(message_id)
                        continue
                    self._reply_message(
                        profile=profile,
                        message_id=message_id,
                        reply_text=qa_payload.get("reply_text", lark.get("refusal_style", "out of scope")),
                    )
                except subprocess.CalledProcessError as exc:
                    # Keep loop alive; message remains unprocessed so next cycle can retry.
                    reply_errors.append(
                        {
                            "message_id": message_id,
                            "returncode": exc.returncode,
                            "stderr": (exc.stderr or "").strip(),
                        }
                    )
                    continue
                next_dialog_context = qa_payload.get("next_dialog_context")
                if next_dialog_context:
                    dialog_state[sender_key] = next_dialog_context
                else:
                    dialog_state.pop(sender_key, None)
                processed_ids.add(message_id)
                replied_ids.add(message_id)
                if message_id not in processed_id_list:
                    processed_id_list.append(message_id)
                if message_id not in replied_id_list:
                    replied_id_list.append(message_id)
                replied += 1
            if stop_due_to_budget:
                break

        if newest_seen:
            kept_ids = processed_id_list[-200:]
            kept_reply_ids = replied_id_list[-300:]
            kept_acked_ids = acked_id_list[-400:]
            write_json(
                mentions_state_path,
                {
                    "last_processed_message_id": newest_seen,
                    "processed_message_ids": kept_ids,
                    "replied_message_ids": kept_reply_ids,
                    "acked_message_ids": kept_acked_ids,
                },
            )
            write_json(dialog_state_path, dialog_state)

        return {
            "status": "warning" if reply_errors else "success",
            "summary": "mention loop completed with reply errors" if reply_errors else "mention loop completed",
            "processed": processed,
            "replied": replied,
            "acked": acked,
            "mention_processed": mention_processed,
            "refresh_count": refresh_count,
            "budget": max_mentions_per_cycle,
            "deferred_due_to_budget": stop_due_to_budget,
            "last_processed_message_id": newest_seen,
            "reply_errors": reply_errors[:5],
        }

    def _build_thread_context_map(self, messages: list[dict[str, Any]]) -> dict[str, str]:
        out: dict[str, str] = {}
        for msg in messages:
            thread_id = str(msg.get("thread_id") or "")
            if not thread_id:
                continue
            chunks: list[str] = []
            base = str(msg.get("content", "")).strip()
            if base:
                chunks.append(base)
            for rep in msg.get("thread_replies", []) or []:
                c = str(rep.get("content", "")).strip()
                if c:
                    chunks.append(c)
            if not chunks:
                continue
            existing = out.get(thread_id, "")
            combined = "\n".join(chunks)
            out[thread_id] = f"{existing}\n{combined}".strip() if existing else combined
        return out

    def _load_latest_analysis(self) -> dict[str, Any] | None:
        latest_analysis = read_json(STATE_ROOT / "latest_analysis.json")
        if latest_analysis:
            return latest_analysis
        latest_analysis = read_json(ANALYSIS_ROOT / "latest_analysis.json")
        if latest_analysis:
            write_json(STATE_ROOT / "latest_analysis.json", latest_analysis)
            return latest_analysis
        return None

    def _list_recent_messages(self, *, profile: str, chat_id: str, page_size: int) -> dict[str, Any]:
        as_identity = str(self.config.get("lark", {}).get("read_as", "user"))
        cmd = [
            "lark-cli",
            "--profile",
            profile,
            "im",
            "+chat-messages-list",
            "--as",
            as_identity,
            "--chat-id",
            chat_id,
            "--page-size",
            str(page_size),
            "--sort",
            "desc",
            "--format",
            "json",
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as exc:
            return {
                "data": {"messages": []},
                "error": {
                    "code": "lark_list_failed",
                    "returncode": exc.returncode,
                    "stderr": (exc.stderr or "").strip(),
                },
            }

    def _reply_message(self, *, profile: str, message_id: str, reply_text: str) -> None:
        as_identity = str(self.config.get("lark", {}).get("reply_as", "bot"))
        cmd = [
            "lark-cli",
            "--profile",
            profile,
            "im",
            "+messages-reply",
            "--as",
            as_identity,
            "--message-id",
            message_id,
            "--reply-in-thread",
            "--text",
            reply_text,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def _is_mention_to_bot(self, message: dict[str, Any]) -> bool:
        if message.get("msg_type") != "text":
            return False
        content = str(message.get("content", "")).lower()
        # Restrict trigger to explicit mention form only.
        return "@cs support" in content

    def _refresh_state(
        self,
        extra_rolling_days: list[int] | None = None,
        period_override_start: Any | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], str, Any]:
        if self.monitor is None:
            self.monitor = SupersetMonitorAgent(self.config)

        tz_name = self.config["superset"]["timezone"]
        now = now_in_timezone(tz_name)
        run_time = isoformat(now)
        current_start, current_end = current_period_weekly(now)
        previous_start, previous_end = previous_period_weekly(now)
        if period_override_start is not None:
            current_start = period_override_start
            current_end = now
            duration = current_end - current_start
            if duration.total_seconds() <= 0:
                duration = timedelta(days=7)
            previous_end = current_start
            previous_start = previous_end - duration

        current_snapshot = self.monitor.run(
            run_time, current_start, current_end, extra_rolling_days=extra_rolling_days
        ).to_dict()
        previous_snapshot = self.monitor.run(
            run_time, previous_start, previous_end, extra_rolling_days=extra_rolling_days
        ).to_dict()
        analysis = self.analyst.run(current_snapshot, previous_snapshot).to_dict()

        write_json(SNAPSHOT_ROOT / "latest_snapshot.json", current_snapshot)
        write_json(ANALYSIS_ROOT / "latest_analysis.json", analysis)
        write_json(STATE_ROOT / "latest_snapshot.json", current_snapshot)
        write_json(STATE_ROOT / "latest_analysis.json", analysis)
        self._enforce_retention(days=30)
        return current_snapshot, analysis, run_time, now

    def _infer_role_from_message(self, message: dict[str, Any]) -> str:
        sender = message.get("sender", {}) or {}
        display = str(sender.get("name", "")).lower()
        content = str(message.get("content", "")).lower()
        if any(token in display for token in ["finance", "fin"]):
            return "finance"
        if "ops" in display:
            return "cs_ops"
        if any(token in content for token in ["chargeback", "sku", "80%", "5%"]):
            return "finance"
        return "cs_ops"

    def _extract_since_date(self, text: str):
        lower = text.lower()
        tz_name = self.config["superset"]["timezone"]
        now_tz = now_in_timezone(tz_name)

        # This month / trong tháng này => from first day of current month to now.
        if any(
            k in lower
            for k in [
                "thang nay",
                "tháng này",
                "trong thang nay",
                "trong tháng này",
                "this month",
                "current month",
                "month to date",
                "mtd",
            ]
        ):
            return now_tz.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # This week / tuần này => from Monday of current week to now.
        if any(k in lower for k in ["tuan nay", "tuần này", "this week", "current week", "week to date", "wtd"]):
            week_start = now_tz - timedelta(days=now_tz.weekday())
            return week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        # Last month / tháng trước => full previous month.
        if any(k in lower for k in ["thang truoc", "tháng trước", "last month", "previous month"]):
            first_this_month = now_tz.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_month_end = first_this_month - timedelta(seconds=1)
            return prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        m0 = re.search(r"(\d+)\s*(ngay|ngày|day|days)\s*(vua roi|vừa rồi|gan nhat|gần nhất|tro lai day|trở lại đây)?", lower)
        if m0:
            days = int(m0.group(1))
            if days >= 2:
                start_dt = now_tz - timedelta(days=days - 1)
                return start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        m1 = re.search(r"(?:tu|từ)\s*(\d{1,2})([a-z]{3,9})\s*(\d{4})", lower)
        if m1:
            day = int(m1.group(1))
            month_name = m1.group(2)
            year = int(m1.group(3))
            month_map = {
                "jan": 1,
                "january": 1,
                "feb": 2,
                "february": 2,
                "mar": 3,
                "march": 3,
                "apr": 4,
                "april": 4,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "aug": 8,
                "august": 8,
                "sep": 9,
                "sept": 9,
                "september": 9,
                "oct": 10,
                "october": 10,
                "nov": 11,
                "november": 11,
                "dec": 12,
                "december": 12,
            }
            month = month_map.get(month_name)
            if month:
                try:
                    return now_tz.replace(
                        year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0
                    )
                except ValueError:
                    return None

        m2 = re.search(r"(?:tu|từ)\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", lower)
        if m2:
            day = int(m2.group(1))
            month = int(m2.group(2))
            year = int(m2.group(3))
            if year < 100:
                year += 2000
            try:
                return now_tz.replace(
                    year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0
                )
            except ValueError:
                return None
        return None

    def _needs_snapshot_refresh(self, question: str, latest_analysis: dict[str, Any] | None) -> bool:
        if not latest_analysis:
            return True
        q = question.lower()
        is_finance_30d_query = ("shop" in q) and ("30" in q) and ("chargeback" in q or "dispute" in q)
        is_dispute_record_list_query = ("dispute" in q) and any(k in q for k in ["list", "danh sach", "danh sách", "liet ke", "liệt kê"])
        if is_dispute_record_list_query:
            dims = latest_analysis.get("snapshot_dimensions", {})
            records = dims.get("dispute_records", []) if isinstance(dims, dict) else []
            return not records
        if not is_finance_30d_query:
            return False
        dims = latest_analysis.get("snapshot_dimensions", {})
        block = dims.get("finance_shop_30d", {}) if isinstance(dims, dict) else {}
        rows = block.get("rows", []) if isinstance(block, dict) else []
        status = block.get("status") if isinstance(block, dict) else None
        return (not rows) or status == "unavailable"

    def _needs_snapshot_refresh_from_reply(self, question: str, qa_payload: dict[str, Any]) -> bool:
        q = question.lower()
        is_finance_30d_query = ("shop" in q) and ("30" in q) and ("chargeback" in q or "dispute" in q)
        is_dispute_record_list_query = ("dispute" in q) and any(k in q for k in ["list", "danh sach", "danh sách", "liet ke", "liệt kê"])
        reply = str(qa_payload.get("reply_text", "")).lower()
        if is_dispute_record_list_query and "chưa có record-level dispute" in reply:
            return True
        if not is_finance_30d_query:
            return False
        return "chưa có dữ liệu chargeback theo shop 30 ngày" in reply or "chưa có dữ liệu dispute theo shop 30 ngày" in reply

    def _enforce_retention(self, *, days: int = 30) -> None:
        ttl_seconds = days * 24 * 60 * 60
        targets = [RUN_LOG_ROOT, SNAPSHOT_ROOT, ANALYSIS_ROOT]
        for root in targets:
            self._cleanup_old_files(root, ttl_seconds)

    def _cleanup_old_files(self, root: Path, ttl_seconds: int) -> None:
        if not root.exists():
            return
        now_ts = now_in_timezone(self.config["superset"]["timezone"]).timestamp()
        for file_path in root.glob("*.json"):
            if file_path.name.startswith("latest_"):
                continue
            try:
                age = now_ts - file_path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > ttl_seconds:
                try:
                    file_path.unlink()
                except FileNotFoundError:
                    continue
