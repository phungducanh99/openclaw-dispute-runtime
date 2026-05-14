from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests

from contracts import SnapshotPayload
from superset_client import SupersetClient, superset_time_range


class SupersetMonitorAgent:
    def __init__(self, config: dict[str, Any]) -> None:
        superset = config["superset"]
        auth = superset["auth"]
        self.client = SupersetClient(
            host=superset["host"],
            username=auth["username"],
            password_env=auth["password_secret_ref"],
        )
        self.superset = superset
        self.finance_dataset_ids = {
            "order_line_items": superset.get("dataset_ids", {}).get("order_line_items", 19),
        }

    def run(
        self,
        run_time: str,
        period_start: datetime,
        period_end: datetime,
        extra_rolling_days: list[int] | None = None,
    ) -> SnapshotPayload:
        dispute_dataset_id = self.superset["dataset_ids"]["dispute_primary"]
        orders_dataset_id = self.superset["dataset_ids"]["orders_reference"]
        ticket_dataset_id = self.superset["dataset_ids"]["ticket_queue"]
        time_range = superset_time_range(period_start, period_end)

        current_period_metrics = self._fetch_period_metrics(
            dispute_dataset_id=dispute_dataset_id,
            orders_dataset_id=orders_dataset_id,
            ticket_dataset_id=ticket_dataset_id,
            time_range=time_range,
        )

        # Add yesterday snapshot for daily operational reading in report content.
        yesterday_end = period_end.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = yesterday_end - timedelta(days=1)
        yesterday_range = superset_time_range(yesterday_start, yesterday_end)
        yesterday_metrics = self._fetch_period_metrics(
            dispute_dataset_id=dispute_dataset_id,
            orders_dataset_id=orders_dataset_id,
            ticket_dataset_id=ticket_dataset_id,
            time_range=yesterday_range,
        )
        rolling_days = {2, 3}
        if extra_rolling_days:
            rolling_days.update(day for day in extra_rolling_days if day >= 2)
        rolling_metrics: dict[str, Any] = {}
        for day in sorted(rolling_days):
            range_start = period_end - timedelta(days=day)
            range_value = superset_time_range(range_start, period_end)
            rolling_metrics[f"last_{day}_days_metrics"] = self._fetch_period_metrics(
                dispute_dataset_id=dispute_dataset_id,
                orders_dataset_id=orders_dataset_id,
                ticket_dataset_id=ticket_dataset_id,
                time_range=range_value,
            )

        by_store_rows = self.client.query(
            datasource_id=dispute_dataset_id,
            columns=["shop_code"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "disputes_distinct",
                    "sqlExpression": "uniqExact(disputes_key)",
                },
                {
                    "aggregate": "SUM",
                    "column": {"column_name": "dispute_amount"},
                    "expressionType": "SIMPLE",
                    "label": "amount_at_risk",
                    "optionName": "amount_at_risk",
                },
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            orderby=[["disputes_distinct", False]],
            row_limit=10,
        )
        by_reason_rows = self.client.query(
            datasource_id=dispute_dataset_id,
            columns=["reason_normalize"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "disputes_distinct",
                    "sqlExpression": "uniqExact(disputes_key)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            orderby=[["disputes_distinct", False]],
            row_limit=10,
        )
        by_status_rows = self.client.query(
            datasource_id=dispute_dataset_id,
            columns=["status_normalize"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "disputes_distinct",
                    "sqlExpression": "uniqExact(disputes_key)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            orderby=[["disputes_distinct", False]],
            row_limit=10,
        )
        dispute_by_gateway = self._query_dispute_gateway_rows(
            dispute_dataset_id=dispute_dataset_id,
            time_range=time_range,
        )
        dispute_by_shop_gateway = self._query_dispute_shop_gateway_rows(
            dispute_dataset_id=dispute_dataset_id,
            time_range=time_range,
        )
        ticket_by_status_rows = self.client.query(
            datasource_id=ticket_dataset_id,
            columns=["status_normalize"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "tickets_distinct",
                    "sqlExpression": "COUNT(DISTINCT id)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            orderby=[["tickets_distinct", False]],
            row_limit=10,
        )
        ticket_by_priority_rows = self.client.query(
            datasource_id=ticket_dataset_id,
            columns=["priority"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "tickets_distinct",
                    "sqlExpression": "COUNT(DISTINCT id)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            orderby=[["tickets_distinct", False]],
            row_limit=10,
        )
        ticket_by_intent_rows = self.client.query(
            datasource_id=ticket_dataset_id,
            columns=["cf_ai_intent"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "tickets_distinct",
                    "sqlExpression": "COUNT(DISTINCT id)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            orderby=[["tickets_distinct", False]],
            row_limit=10,
        )
        ticket_by_group_rows = self.client.query(
            datasource_id=ticket_dataset_id,
            columns=["group_id"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "tickets_distinct",
                    "sqlExpression": "COUNT(DISTINCT id)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            orderby=[["tickets_distinct", False]],
            row_limit=10,
        )
        ticket_intent_trend_rows = self.client.query(
            datasource_id=ticket_dataset_id,
            columns=["date_us", "cf_ai_intent"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "tickets_distinct",
                    "sqlExpression": "COUNT(DISTINCT id)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            row_limit=5000,
        )
        ticket_intent_shop_trend_rows = self.client.query(
            datasource_id=ticket_dataset_id,
            columns=["date_us", "cf_ai_intent", "shop_code"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "tickets_distinct",
                    "sqlExpression": "COUNT(DISTINCT id)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            row_limit=10000,
        )
        dispute_reason_trend_rows = self.client.query(
            datasource_id=dispute_dataset_id,
            columns=["date_us", "reason_normalize"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "disputes_distinct",
                    "sqlExpression": "uniqExact(disputes_key)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            row_limit=5000,
        )
        dispute_shop_trend_rows = self.client.query(
            datasource_id=dispute_dataset_id,
            columns=["date_us", "shop_code"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "disputes_distinct",
                    "sqlExpression": "uniqExact(disputes_key)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            row_limit=5000,
        )
        try:
            finance_30d = self._build_finance_shop_window(
                dispute_dataset_id=dispute_dataset_id,
                orders_dataset_id=orders_dataset_id,
                period_end=period_end,
                window_days=30,
            )
        except requests.RequestException:
            finance_30d = {"window_days": 30, "rows": [], "status": "unavailable"}
        try:
            finance_7d = self._build_finance_shop_window(
                dispute_dataset_id=dispute_dataset_id,
                orders_dataset_id=orders_dataset_id,
                period_end=period_end,
                window_days=7,
            )
        except requests.RequestException:
            finance_7d = {"window_days": 7, "rows": [], "status": "unavailable"}
        finance_sku_60d = {"status": "disabled"}

        payload = SnapshotPayload(
            status="success",
            summary="snapshot fetched from Superset",
            next_actions=["pass_to_analyst"],
            artifacts=[],
            run_time=run_time,
            source={
                "superset_host": self.superset["host"],
                "dashboard_id": self.superset["dashboard_id"],
                "dataset_ids": self.superset["dataset_ids"],
            },
            period_current={
                "label": "weekly",
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            metrics={
                "ticket_count": current_period_metrics.get("ticket_count"),
                "dispute_count": current_period_metrics.get("dispute_count"),
                "orders_count": current_period_metrics.get("orders_count"),
                "dispute_rate": current_period_metrics.get("dispute_rate"),
                "amount_at_risk": current_period_metrics.get("amount_at_risk"),
            },
            dimensions={
                "by_store": by_store_rows,
                "by_reason": by_reason_rows,
                "by_status": by_status_rows,
                "dispute_by_gateway": dispute_by_gateway,
                "dispute_by_shop_gateway": dispute_by_shop_gateway,
                "ticket_by_status": ticket_by_status_rows,
                "ticket_by_priority": ticket_by_priority_rows,
                "ticket_by_intent": ticket_by_intent_rows,
                "ticket_by_group": ticket_by_group_rows,
                "ticket_intent_trend": ticket_intent_trend_rows,
                "ticket_intent_shop_trend": ticket_intent_shop_trend_rows,
                "dispute_reason_trend": dispute_reason_trend_rows,
                "dispute_shop_trend": dispute_shop_trend_rows,
                "top_skus": [],
                "yesterday_metrics": yesterday_metrics,
                **rolling_metrics,
                "finance_shop_30d": finance_30d,
                "finance_shop_7d": finance_7d,
                "finance_sku_60d": finance_sku_60d,
            },
            source_refs=[self.superset["dashboard_url"]],
        )
        return payload

    def _fetch_period_metrics(
        self,
        *,
        dispute_dataset_id: int,
        orders_dataset_id: int,
        ticket_dataset_id: int,
        time_range: str,
    ) -> dict[str, Any]:
        dispute_rows = self.client.query(
            datasource_id=dispute_dataset_id,
            columns=[],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "disputes_distinct",
                    "sqlExpression": "uniqExact(disputes_key)",
                },
                {
                    "aggregate": "SUM",
                    "column": {"column_name": "dispute_amount"},
                    "expressionType": "SIMPLE",
                    "label": "amount_at_risk",
                    "optionName": "amount_at_risk",
                },
            ],
            granularity_sqla="date_us",
            time_range=time_range,
        )
        orders_rows = self.client.query(
            datasource_id=orders_dataset_id,
            columns=[],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "orders_distinct",
                    "sqlExpression": "uniqExact(id)",
                }
            ],
            granularity_sqla="created_at_us",
            time_range=time_range,
        )
        ticket_rows = self.client.query(
            datasource_id=ticket_dataset_id,
            columns=[],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "tickets_distinct",
                    "sqlExpression": "COUNT(DISTINCT id)",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
        )

        dispute_metrics = dispute_rows[0] if dispute_rows else {}
        orders_metrics = orders_rows[0] if orders_rows else {}
        ticket_metrics = ticket_rows[0] if ticket_rows else {}
        disputes = dispute_metrics.get("disputes_distinct")
        orders = orders_metrics.get("orders_distinct")
        dispute_rate = None
        if disputes is not None and orders not in (None, 0):
            dispute_rate = round((disputes / orders) * 100, 4)

        return {
            "ticket_count": ticket_metrics.get("tickets_distinct"),
            "dispute_count": disputes,
            "orders_count": orders,
            "dispute_rate": dispute_rate,
            "amount_at_risk": dispute_metrics.get("amount_at_risk"),
        }

    def _build_finance_shop_window(
        self,
        *,
        dispute_dataset_id: int,
        orders_dataset_id: int,
        period_end: datetime,
        window_days: int,
    ) -> dict[str, Any]:
        period_start = period_end - timedelta(days=window_days)
        time_range = superset_time_range(period_start, period_end)
        disputes_rows = self.client.query(
            datasource_id=dispute_dataset_id,
            columns=["shop_code"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "disputes_distinct",
                    "sqlExpression": "uniqExact(disputes_key)",
                },
                {
                    "aggregate": "SUM",
                    "column": {"column_name": "dispute_amount"},
                    "expressionType": "SIMPLE",
                    "label": "chargeback_amount",
                    "optionName": "chargeback_amount",
                }
            ],
            granularity_sqla="date_us",
            time_range=time_range,
            row_limit=2000,
        )
        orders_rows = self.client.query(
            datasource_id=self.finance_dataset_ids["order_line_items"],
            columns=["shop_code"],
            metrics=[
                {
                    "expressionType": "SQL",
                    "label": "orders_distinct",
                    "sqlExpression": "uniqExact(order_id)",
                }
            ],
            granularity_sqla="created_at_us",
            time_range=time_range,
            row_limit=2000,
        )
        order_amount_rows = self._query_order_amount_rows(
            datasource_id=orders_dataset_id,
            time_range=time_range,
        )

        shop_data: dict[str, dict[str, Any]] = {}
        for row in orders_rows:
            shop = row.get("shop_code")
            if not shop:
                continue
            shop_data[shop] = {"shop_code": shop, "orders_count": row.get("orders_distinct")}
        for row in disputes_rows:
            shop = row.get("shop_code")
            if not shop:
                continue
            shop_data.setdefault(shop, {"shop_code": shop, "orders_count": None})
            shop_data[shop]["dispute_count"] = row.get("disputes_distinct")
            shop_data[shop]["chargeback_amount"] = row.get("chargeback_amount")
        for row in order_amount_rows:
            shop = row.get("shop_code")
            if not shop:
                continue
            shop_data.setdefault(shop, {"shop_code": shop, "orders_count": None})
            shop_data[shop]["order_amount"] = row.get("order_amount")
        rows: list[dict[str, Any]] = []
        for shop, values in shop_data.items():
            orders = values.get("orders_count")
            disputes = values.get("dispute_count")
            chargeback_amount = values.get("chargeback_amount")
            order_amount = values.get("order_amount")
            dispute_rate = None
            chargeback_rate = None
            chargeback_amount_over_order_amount = None
            if isinstance(disputes, (int, float)) and isinstance(orders, (int, float)) and orders:
                dispute_rate = round((disputes / orders) * 100, 4)
            if isinstance(chargeback_amount, (int, float)) and isinstance(orders, (int, float)) and orders:
                chargeback_rate = round(chargeback_amount / orders, 4)
            if isinstance(chargeback_amount, (int, float)) and isinstance(order_amount, (int, float)) and order_amount:
                chargeback_amount_over_order_amount = round((chargeback_amount / order_amount) * 100, 4)
            rows.append(
                {
                    "shop_code": shop,
                    "orders_count": orders,
                    "order_amount": order_amount,
                    "dispute_count": disputes,
                    "dispute_rate": dispute_rate,
                    "chargeback_amount": chargeback_amount,
                    "chargeback_rate": chargeback_rate,
                    "chargeback_amount_over_order_amount": chargeback_amount_over_order_amount,
                }
            )
        rows.sort(
            key=lambda r: (
                r.get("dispute_rate") if isinstance(r.get("dispute_rate"), (int, float)) else -1
            ),
            reverse=True,
        )
        return {
            "window_days": window_days,
            "order_base": "orders_count",
            "rows": rows,
            "chargeback_source": "dispute_amount",
            "chargeback_available": True,
        }

    def _query_order_amount_rows(self, *, datasource_id: int, time_range: str) -> list[dict[str, Any]]:
        metric_candidates = [
            "total_price",
            "current_total_price",
            "subtotal_price",
            "total_line_items_price",
            "gross_collected",
            "gross_sale",
        ]
        last_error: Exception | None = None
        for col in metric_candidates:
            try:
                return self.client.query(
                    datasource_id=datasource_id,
                    columns=["shop_code"],
                    metrics=[
                        {
                            "aggregate": "SUM",
                            "column": {"column_name": col},
                            "expressionType": "SIMPLE",
                            "label": "order_amount",
                            "optionName": "order_amount",
                        }
                    ],
                    granularity_sqla="created_at_us",
                    time_range=time_range,
                    row_limit=2000,
                )
            except requests.RequestException as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return []

    def _query_dispute_gateway_rows(self, *, dispute_dataset_id: int, time_range: str) -> dict[str, Any]:
        gateway_cols = ["gateway", "gateway_normalize", "payment_gateway", "gateway_name"]
        for col in gateway_cols:
            try:
                rows = self.client.query(
                    datasource_id=dispute_dataset_id,
                    columns=[col],
                    metrics=[
                        {
                            "expressionType": "SQL",
                            "label": "disputes_distinct",
                            "sqlExpression": "uniqExact(disputes_key)",
                        },
                        {
                            "aggregate": "SUM",
                            "column": {"column_name": "dispute_amount"},
                            "expressionType": "SIMPLE",
                            "label": "amount_at_risk",
                            "optionName": "amount_at_risk",
                        },
                    ],
                    granularity_sqla="date_us",
                    time_range=time_range,
                    orderby=[["disputes_distinct", False]],
                    row_limit=50,
                )
                norm_rows: list[dict[str, Any]] = []
                for row in rows:
                    norm_rows.append(
                        {
                            "gateway": row.get(col),
                            "disputes_distinct": row.get("disputes_distinct"),
                            "amount_at_risk": row.get("amount_at_risk"),
                        }
                    )
                return {"status": "ok", "field": col, "rows": norm_rows}
            except requests.RequestException:
                continue
        return {"status": "unavailable", "field": None, "rows": []}

    def _query_dispute_shop_gateway_rows(self, *, dispute_dataset_id: int, time_range: str) -> dict[str, Any]:
        gateway_cols = ["gateway", "gateway_normalize", "payment_gateway", "gateway_name"]
        for col in gateway_cols:
            try:
                rows = self.client.query(
                    datasource_id=dispute_dataset_id,
                    columns=["shop_code", col],
                    metrics=[
                        {
                            "expressionType": "SQL",
                            "label": "disputes_distinct",
                            "sqlExpression": "uniqExact(disputes_key)",
                        },
                        {
                            "aggregate": "SUM",
                            "column": {"column_name": "dispute_amount"},
                            "expressionType": "SIMPLE",
                            "label": "amount_at_risk",
                            "optionName": "amount_at_risk",
                        },
                    ],
                    granularity_sqla="date_us",
                    time_range=time_range,
                    orderby=[["disputes_distinct", False]],
                    row_limit=200,
                )
                norm_rows: list[dict[str, Any]] = []
                for row in rows:
                    norm_rows.append(
                        {
                            "shop_code": row.get("shop_code"),
                            "gateway": row.get(col),
                            "disputes_distinct": row.get("disputes_distinct"),
                            "amount_at_risk": row.get("amount_at_risk"),
                        }
                    )
                return {"status": "ok", "field": col, "rows": norm_rows}
            except requests.RequestException:
                continue
        return {"status": "unavailable", "field": None, "rows": []}
