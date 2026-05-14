from __future__ import annotations

from typing import Any

from contracts import AnalysisPayload


class ComparativeAnalystAgent:
    def __init__(self, config: dict[str, Any]) -> None:
        self.compare_mode = config["superset"]["compare_mode"]

    def run(self, current_snapshot: dict[str, Any], previous_snapshot: dict[str, Any] | None) -> AnalysisPayload:
        current_metrics = current_snapshot.get("metrics", {})
        previous_metrics = previous_snapshot.get("metrics", {}) if previous_snapshot else {}

        def delta(key: str) -> dict[str, Any]:
            current_value = current_metrics.get(key)
            previous_value = previous_metrics.get(key)
            if current_value is None or previous_value in (None, 0):
                return {"abs": None, "pct": None}
            return {
                "abs": round(current_value - previous_value, 4),
                "pct": round(((current_value - previous_value) / previous_value) * 100, 2),
            }

        ticket_delta = delta("ticket_count")
        dispute_delta = delta("dispute_count")
        orders_delta = delta("orders_count")
        rate_delta = delta("dispute_rate")
        amount_delta = delta("amount_at_risk")

        headline = "Weekly dispute update ready"
        if dispute_delta["pct"] is not None:
            headline = f"Weekly disputes changed {dispute_delta['pct']}% vs previous week"

        top_drivers = self._build_top_drivers(current_snapshot, previous_snapshot or {})
        alerts = self._build_alerts(
            dispute_delta_pct=dispute_delta["pct"],
            dispute_rate_delta_abs=rate_delta["abs"],
            amount_delta_pct=amount_delta["pct"],
        )
        ticket_summary = self._build_ticket_summary(current_snapshot, previous_snapshot or {})

        payload = AnalysisPayload(
            status="success",
            summary="comparison completed",
            next_actions=["pass_to_publisher"],
            artifacts=[],
            compare_mode=self.compare_mode,
            period_current=current_snapshot.get("period_current", {}),
            period_previous=previous_snapshot.get("period_current", {}) if previous_snapshot else {},
            metrics_current=current_metrics,
            metrics_previous=previous_metrics,
            deltas={
                "ticket_count_abs": ticket_delta["abs"],
                "ticket_count_pct": ticket_delta["pct"],
                "dispute_count_abs": dispute_delta["abs"],
                "dispute_count_pct": dispute_delta["pct"],
                "orders_count_abs": orders_delta["abs"],
                "orders_count_pct": orders_delta["pct"],
                "dispute_rate_abs": rate_delta["abs"],
                "dispute_rate_pct": rate_delta["pct"],
                "amount_at_risk_abs": amount_delta["abs"],
                "amount_at_risk_pct": amount_delta["pct"],
            },
            top_drivers=top_drivers,
            alerts=alerts,
            narrative_blocks={
                "headline": headline,
                "summary": "Core weekly comparison generated from normalized snapshot data.",
                "risks": [a["message"] for a in alerts if a["severity"] in ("high", "medium")],
                "actions": [
                    "Review top reason and top store dispute clusters first.",
                    "Prioritize backlog statuses with high unresolved volume.",
                ],
                "ticket_summary": ticket_summary,
            },
            source_refs=current_snapshot.get("source_refs", []),
            snapshot_dimensions=current_snapshot.get("dimensions", {}),
        )
        return payload

    def _build_ticket_summary(self, current_snapshot: dict[str, Any], previous_snapshot: dict[str, Any]) -> dict[str, Any]:
        current_metrics = current_snapshot.get("metrics", {})
        current_dims = current_snapshot.get("dimensions", {})
        previous_dims = previous_snapshot.get("dimensions", {})
        created = current_metrics.get("ticket_count")
        resolved = self._sum_status(current_dims.get("ticket_by_status", []), ["Closed", "Resolved"])
        open_end = self._sum_status(current_dims.get("ticket_by_status", []), ["Open", "Pending", "Re-open", "Waiting"])
        open_start = self._sum_status(previous_dims.get("ticket_by_status", []), ["Open", "Pending", "Re-open", "Waiting"])
        return {
            "ticket_created": created,
            "ticket_resolved": resolved,
            "open_start": open_start,
            "open_end": open_end,
        }

    def _sum_status(self, rows: list[dict[str, Any]], keywords: list[str]) -> int:
        total = 0
        for row in rows:
            name = str(row.get("status_normalize") or "")
            count = row.get("tickets_distinct")
            if not isinstance(count, (int, float)):
                continue
            if any(keyword.lower() in name.lower() for keyword in keywords):
                total += int(count)
        return total

    def _build_top_drivers(self, current_snapshot: dict[str, Any], previous_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        current_dimensions = current_snapshot.get("dimensions", {})
        previous_dimensions = previous_snapshot.get("dimensions", {})

        current_reason = self._index_by_key(current_dimensions.get("by_reason", []), "reason_normalize")
        previous_reason = self._index_by_key(previous_dimensions.get("by_reason", []), "reason_normalize")
        deltas: list[dict[str, Any]] = []
        for reason, current_row in current_reason.items():
            current_count = current_row.get("disputes_distinct")
            previous_count = previous_reason.get(reason, {}).get("disputes_distinct", 0)
            if current_count is None:
                continue
            delta_abs = current_count - (previous_count or 0)
            deltas.append(
                {
                    "driver_type": "reason",
                    "name": reason,
                    "current_disputes": current_count,
                    "previous_disputes": previous_count,
                    "delta_abs": delta_abs,
                }
            )

        deltas.sort(key=lambda item: item["delta_abs"], reverse=True)
        return deltas[:3]

    def _index_by_key(self, rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for row in rows:
            name = row.get(key)
            if name is None:
                continue
            indexed[str(name)] = row
        return indexed

    def _build_alerts(
        self,
        *,
        dispute_delta_pct: float | None,
        dispute_rate_delta_abs: float | None,
        amount_delta_pct: float | None,
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if dispute_delta_pct is not None and dispute_delta_pct > 20:
            alerts.append(
                {
                    "severity": "high",
                    "code": "DISPUTE_COUNT_SPIKE",
                    "message": f"Dispute count increased {dispute_delta_pct}%.",
                }
            )
        if dispute_rate_delta_abs is not None and dispute_rate_delta_abs > 0.2:
            alerts.append(
                {
                    "severity": "medium",
                    "code": "DISPUTE_RATE_UP",
                    "message": f"Dispute rate increased {dispute_rate_delta_abs} points.",
                }
            )
        if amount_delta_pct is not None and amount_delta_pct > 15:
            alerts.append(
                {
                    "severity": "high",
                    "code": "EXPOSURE_UP",
                    "message": f"Exposure amount increased {amount_delta_pct}%.",
                }
            )
        return alerts
