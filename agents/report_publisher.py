from __future__ import annotations

import json
import subprocess
from typing import Any

from json_store import read_json, write_json
from paths import STATE_ROOT


class ReportPublisherAgent:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.chat_id = config["lark"]["target_chat_id"]
        self.profile = config["lark"].get("cli_profile", "default")
        self.state_path = STATE_ROOT / "publisher_state.json"

    def render_text(self, analysis: dict[str, Any]) -> str:
        metrics = analysis.get("metrics_current", {})
        deltas = analysis.get("deltas", {})
        snapshot_dimensions = analysis.get("snapshot_dimensions", {})
        yesterday_metrics = snapshot_dimensions.get("yesterday_metrics", {})
        period_end = analysis.get("period_current", {}).get("end", "")
        top_drivers = analysis.get("top_drivers", [])
        top_driver_line = "n/a"
        if top_drivers:
            top = top_drivers[0]
            top_driver_line = f"{top.get('name')} ({top.get('delta_abs')})"

        dispute_count = metrics.get("dispute_count")
        dispute_rate = metrics.get("dispute_rate")
        amount_at_risk = metrics.get("amount_at_risk")
        dispute_delta = deltas.get("dispute_count_pct")
        ticket_count = metrics.get("ticket_count")
        ticket_delta = deltas.get("ticket_count_pct")
        ticket_summary = analysis.get("narrative_blocks", {}).get("ticket_summary", {})
        trend_ticket_intent = self._top_trend_line(
            rows=snapshot_dimensions.get("ticket_intent_trend", []),
            key_field="cf_ai_intent",
            value_field="tickets_distinct",
        )
        trend_dispute_reason = self._top_trend_line(
            rows=snapshot_dimensions.get("dispute_reason_trend", []),
            key_field="reason_normalize",
            value_field="disputes_distinct",
        )

        amount_text = "n/a"
        if isinstance(amount_at_risk, (int, float)):
            amount_text = f"{amount_at_risk:,.2f}"
        yesterday_amount = yesterday_metrics.get("amount_at_risk")
        yesterday_amount_text = "n/a"
        if isinstance(yesterday_amount, (int, float)):
            yesterday_amount_text = f"{yesterday_amount:,.2f}"

        # Keep formula text explicit for operational traceability in chat.
        formula_block = [
            "Formula:",
            "- Disputes = uniqExact(disputes_key)",
            "- Orders = uniqExact(id)",
            "- Dispute rate (%) = 100 * Disputes / Orders",
            "- Amount at risk = SUM(dispute_amount)",
            "- Weekly dispute delta (%) = (Current - Previous) / Previous * 100",
        ]
        meaning_block = [
            "Meaning:",
            "- Disputes: total unique dispute cases in selected week.",
            "- Dispute rate: dispute pressure relative to order volume.",
            "- Amount at risk: financial exposure from disputes.",
            "- Weekly dispute delta: week-over-week change of dispute volume.",
            "- Top driver: reason with largest week-over-week increase.",
        ]

        return "\n".join(
            [
                "Dispute Monitor Update",
                f"- Disputes: {dispute_count}",
                f"- Dispute rate: {dispute_rate}%",
                f"- Amount at risk: {amount_text}",
                f"- Weekly dispute delta: {dispute_delta}%",
                f"- Top driver: {top_driver_line}",
                f"- Data as of: {period_end}",
                "",
                "Ticket Monitor Update",
                f"- Ticket created: {ticket_summary.get('ticket_created', ticket_count)}",
                f"- Ticket resolved: {ticket_summary.get('ticket_resolved')}",
                f"- Open start: {ticket_summary.get('open_start')}",
                f"- Open end: {ticket_summary.get('open_end')}",
                f"- Weekly ticket delta: {ticket_delta}%",
                f"- Data as of: {period_end}",
                "",
                "Trend Highlights",
                f"- Ticket intent trend: {trend_ticket_intent}",
                f"- Dispute reason trend: {trend_dispute_reason}",
                "",
                "Yesterday:",
                f"- Disputes: {yesterday_metrics.get('dispute_count')}",
                f"- Orders: {yesterday_metrics.get('orders_count')}",
                f"- Dispute rate: {yesterday_metrics.get('dispute_rate')}%",
                f"- Amount at risk: {yesterday_amount_text}",
                "",
                *formula_block,
                "",
                *meaning_block,
            ]
        )

    def _top_trend_line(self, *, rows: list[dict[str, Any]], key_field: str, value_field: str) -> str:
        grouped: dict[str, list[tuple[str, float]]] = {}
        for row in rows:
            key = str(row.get(key_field) or "Unknown")
            date_value = str(row.get("date_us") or "")
            metric = row.get(value_field)
            if not date_value or not isinstance(metric, (int, float)):
                continue
            grouped.setdefault(key, []).append((date_value, float(metric)))
        if not grouped:
            return "n/a"
        best_key = "n/a"
        best_delta = None
        best_start = 0.0
        best_end = 0.0
        for key, series in grouped.items():
            series.sort(key=lambda x: x[0])
            start = series[0][1]
            end = series[-1][1]
            delta = end - start
            if best_delta is None or abs(delta) > abs(best_delta):
                best_delta = delta
                best_key = key
                best_start = start
                best_end = end
        direction = "up" if (best_delta or 0) > 0 else ("down" if (best_delta or 0) < 0 else "flat")
        return f"{best_key}: {best_start} -> {best_end} (Δ={round(best_delta or 0, 2)}, {direction})"

    def _idempotency_key(self, analysis: dict[str, Any]) -> str:
        period_end = analysis.get("period_current", {}).get("end", "")
        report_day = period_end[:10] if period_end else "unknown-day"
        return f"dispute-report-{report_day}"

    def _was_sent(self, key: str) -> bool:
        state = read_json(self.state_path) or {}
        return state.get("last_idempotency_key") == key

    def _mark_sent(self, key: str, send_output: dict[str, Any]) -> None:
        write_json(
            self.state_path,
            {
                "last_idempotency_key": key,
                "last_send_output": send_output,
            },
        )

    def run(self, analysis: dict[str, Any]) -> dict[str, Any]:
        message_text = self.render_text(analysis)
        idempotency_key = self._idempotency_key(analysis)

        if not self.chat_id:
            return {
                "status": "pending",
                "summary": "publisher waiting for target_chat_id",
                "next_actions": ["configure_chat_id", "test_lark_send"],
                "artifacts": [],
                "target_chat_id": self.chat_id,
                "message_type": "text",
                "message_preview": message_text,
                "idempotency_key": idempotency_key,
            }

        if self._was_sent(idempotency_key):
            return {
                "status": "skipped",
                "summary": "message already sent for this idempotency key",
                "next_actions": [],
                "artifacts": [],
                "target_chat_id": self.chat_id,
                "message_type": "text",
                "message_preview": message_text,
                "idempotency_key": idempotency_key,
            }

        cmd = [
            "lark-cli",
            "--profile",
            self.profile,
            "im",
            "+messages-send",
            "--as",
            "user",
            "--chat-id",
            self.chat_id,
            "--text",
            message_text,
        ]

        try:
            completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
            stdout = completed.stdout.strip()
            parsed_output: dict[str, Any]
            try:
                parsed_output = json.loads(stdout) if stdout else {}
            except json.JSONDecodeError:
                parsed_output = {"raw_stdout": stdout}

            self._mark_sent(idempotency_key, parsed_output)
            return {
                "status": "success",
                "summary": "report sent to Lark chat",
                "next_actions": [],
                "artifacts": [],
                "target_chat_id": self.chat_id,
                "message_type": "text",
                "idempotency_key": idempotency_key,
                "send_output": parsed_output,
            }
        except subprocess.CalledProcessError as exc:
            return {
                "status": "error",
                "summary": "failed to send report to Lark chat",
                "next_actions": ["check_chat_id", "check_lark_permissions", "retry"],
                "artifacts": [],
                "target_chat_id": self.chat_id,
                "message_type": "text",
                "idempotency_key": idempotency_key,
                "error_stdout": exc.stdout,
                "error_stderr": exc.stderr,
            }

    def preview(self, analysis: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ready",
            "summary": "publisher preview ready",
            "next_actions": [],
            "artifacts": [],
            "target_chat_id": self.chat_id,
            "message_type": "text",
            "message_preview": self.render_text(analysis),
            "idempotency_key": self._idempotency_key(analysis),
        }
