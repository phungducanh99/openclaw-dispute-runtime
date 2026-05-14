from __future__ import annotations

import re
from datetime import datetime
from typing import Any


class GroupBotQAAgent:
    def __init__(self, config: dict[str, Any]) -> None:
        self.refusal_style = config["lark"]["refusal_style"]
        self.prefix = "CS support: "
        self.role_hints = {
            "finance": (
                "Goi y cho Finance: "
                "1) ty le dispute theo shop 30 ngay, "
                "2) chargeback (dispute amount) theo shop 30 ngay, "
                "3) amount at risk theo tuan."
            ),
            "cs_manager": (
                "Goi y cho CS Manager: "
                "1) bao cao dispute ngay hom qua, "
                "2) bao cao dispute 2/3 ngay vua qua, "
                "3) compare tuan nay vs tuan truoc, "
                "4) top driver theo reason."
            ),
            "cs_ops": (
                "Goi y cho CS Ops: "
                "1) top shop dispute rate 30 ngay, "
                "2) top status backlog, "
                "3) canh bao dispute rate tang, "
                "4) amount at risk theo ngay/tuan."
            ),
            "general": (
                "Goi y: "
                "1) bao cao dispute ngay hom qua, "
                "2) bao cao dispute N ngay vua qua, "
                "3) ty le dispute theo shop 30 ngay, "
                "4) compare tuan nay vs tuan truoc."
            ),
        }
        self.topic_keywords = {
            "dispute": [
                "dispute",
                "chargeback",
                "nguyen nhan",
                "nguyên nhân",
                "shop",
                "amount at risk",
                "rate",
            ],
            "intent": [
                "intent",
                "cf_ai_intent",
                "refund_return_request",
                "phan tich",
                "phân tích",
                "xu huong",
                "xu hướng",
                "trend",
            ],
        }

    def run(
        self,
        question: str,
        latest_analysis: dict[str, Any] | None,
        asker_context: dict[str, Any] | None = None,
        dialog_context: dict[str, Any] | None = None,
        thread_context_text: str | None = None,
    ) -> dict[str, Any]:
        asker_role = self._infer_role(question, asker_context or {})
        if not latest_analysis:
            return {
                "status": "warning",
                "summary": "no analysis available yet",
                "next_actions": [],
                "artifacts": [],
                "question_type": "unknown",
                "answer_scope": "out_of_boundary",
                "reply_text": self._build_guided_reply(asker_role),
                "source_refs": [],
                "confidence": "low",
            }

        reply_text = self._build_guided_reply(asker_role)
        question_lower = question.lower()
        question_lower = self._merge_with_thread_context_if_followup(question_lower, thread_context_text)
        pending_context = dialog_context or {}
        resolved_question = self._merge_with_pending_context(question_lower, pending_context)
        if resolved_question != question_lower:
            question_lower = resolved_question
        top_n = self._extract_top_n(question_lower)
        needs_refresh_days = None
        next_dialog_context: dict[str, Any] | None = None
        multi_reply = self._build_multi_intent_reply(question_lower, question, latest_analysis, top_n)
        if multi_reply:
            reply_text = multi_reply
            return {
                "status": "success",
                "summary": "qa stub reply generated",
                "next_actions": [],
                "artifacts": [],
                "question_type": "basic_metric_lookup",
                "answer_scope": "within_boundary",
                "reply_text": reply_text,
                "source_refs": latest_analysis.get("source_refs", []),
                "confidence": "medium",
                "needs_refresh_days": needs_refresh_days,
                "next_dialog_context": next_dialog_context,
            }
        if self._is_chargeback_shop_30d_request(question_lower):
            reply_text = self._build_chargeback_shop_30d_reply(latest_analysis, top_n)
        elif self._is_dispute_shop_30d_7d_request(question_lower):
            reply_text = self._build_dispute_shop_30d_7d_reply(latest_analysis, question)
        elif self._is_dispute_shop_30d_request(question_lower):
            reply_text = self._build_dispute_shop_30d_reply(latest_analysis, top_n)
        elif self._is_trend_ticket_intent_shop_request(question_lower):
            reply_text = self._build_trend_ticket_intent_shop_reply(latest_analysis, top_n)
        elif self._is_ticket_intent_shop_request(question_lower):
            reply_text = self._build_trend_ticket_intent_shop_reply(latest_analysis, top_n)
        elif self._is_trend_specific_intent_request(question_lower) or self._has_specific_intent_in_question(
            question, latest_analysis
        ):
            reply_text = self._build_trend_specific_intent_reply(latest_analysis, question)
        elif self._is_trend_ticket_intent_request(question_lower):
            reply_text = self._build_trend_ticket_intent_reply(latest_analysis, top_n)
        elif self._is_trend_dispute_reason_request(question_lower):
            reply_text = self._build_trend_dispute_reason_reply(latest_analysis, top_n)
        elif self._is_trend_dispute_shop_request(question_lower):
            reply_text = self._build_trend_dispute_shop_reply(latest_analysis, top_n)
        elif self._is_dispute_status_request(question_lower):
            reply_text = self._build_dispute_status_reply(latest_analysis, top_n)
        elif self._is_dispute_shop_gateway_request(question_lower):
            reply_text = self._build_dispute_shop_gateway_reply(latest_analysis, top_n)
        elif self._is_dispute_gateway_request(question_lower):
            reply_text = self._build_dispute_gateway_reply(latest_analysis, top_n)
        elif self._is_find_request(question_lower):
            reply_text = self._build_find_reply(latest_analysis, question_lower)
        elif self._is_list_request(question_lower):
            reply_text = self._build_list_reply(latest_analysis, question_lower, top_n)
        elif self._is_help_request(question_lower):
            reply_text = self._build_help_reply()
        elif self._is_total_request(question_lower):
            reply_text = self._build_total_reply(latest_analysis, question_lower)
        elif self._is_ticket_status_request(question_lower):
            reply_text = self._build_ticket_status_reply(latest_analysis, top_n)
        elif self._is_ops_status_actionable_request(question_lower):
            reply_text = self._build_ops_status_actionable_reply(latest_analysis, top_n)
        elif self._is_ticket_priority_request(question_lower):
            reply_text = self._build_ticket_priority_reply(latest_analysis, top_n)
        elif self._is_ticket_intent_request(question_lower):
            reply_text = self._build_ticket_intent_reply(latest_analysis, top_n)
        elif self._is_ticket_open_end_request(question_lower):
            reply_text = self._build_ticket_open_end_reply(latest_analysis)
        elif self._is_ticket_resolved_request(question_lower):
            reply_text = self._build_ticket_resolved_reply(latest_analysis)
        elif self._is_backlog_request(question_lower):
            reply_text = self._build_backlog_reply(latest_analysis)
        elif self._is_compare_dispute_ticket_request(question_lower):
            reply_text = self._build_compare_dispute_ticket_reply(latest_analysis)
        elif self._is_risk_where_request(question_lower):
            reply_text = self._build_risk_where_reply(latest_analysis)
        elif self._is_ticket_report_request(question_lower):
            reply_text = self._build_ticket_report_reply(latest_analysis)
        elif self._is_reason_report_request(question_lower):
            reply_text = self._build_reason_report_reply(latest_analysis, question_lower, top_n)
        else:
            last_n_days = self._extract_last_n_days(question_lower)
            if last_n_days:
                reply_text, needs_refresh_days = self._build_last_n_days_reply(latest_analysis, last_n_days)
            elif self._is_yesterday_report_request(question_lower):
                reply_text = self._build_yesterday_reply(latest_analysis)
            elif self._is_report_request(question_lower):
                reply_text = self._build_report_reply(latest_analysis)
            elif "dispute" in question_lower:
                metrics = latest_analysis.get("metrics_current", {})
                reply_text = (
                    f"{self.prefix}Disputes hien tai: {metrics.get('dispute_count')}. "
                    f"Data as of: {latest_analysis.get('period_current', {}).get('end', '')}"
                )
            else:
                inferred_topic = self._infer_topic(question_lower)
                if inferred_topic:
                    reply_text = self._build_clarify_reply(inferred_topic)
                    next_dialog_context = {"topic": inferred_topic, "pending": True}
                else:
                    reply_text = self._build_clarify_reply("general")
                    next_dialog_context = {"topic": "general", "pending": True}

        return {
            "status": "success",
            "summary": "qa stub reply generated",
            "next_actions": [],
            "artifacts": [],
            "question_type": "basic_metric_lookup",
            "answer_scope": "within_boundary",
            "reply_text": reply_text,
            "source_refs": latest_analysis.get("source_refs", []),
            "confidence": "medium",
            "needs_refresh_days": needs_refresh_days,
            "next_dialog_context": next_dialog_context,
        }

    def _build_guided_reply(self, role: str) -> str:
        hints = self.role_hints.get(role, self.role_hints["general"])
        return f"{self.prefix}Yêu cầu này hiện chưa đủ điều kiện trả lời trực tiếp. {hints}"

    def _build_clarify_reply(self, topic: str) -> str:
        if topic == "dispute":
            return (
                f"{self.prefix}Mình cần làm rõ để trả lời chính xác. "
                "Bạn muốn báo cáo dispute theo khoảng nào (hôm qua / N ngày / tuần), và theo chiều nào "
                "(tổng quan / theo shop / theo nguyên nhân)?"
            )
        if topic == "intent":
            return (
                f"{self.prefix}Mình cần làm rõ để trả lời đúng phần intent. "
                "Bạn muốn theo tuần hay theo khoảng từ ngày nào, và cần top N hay một intent cụ thể?"
            )
        return (
            f"{self.prefix}Mình chưa rõ yêu cầu cụ thể. "
            "Bạn cho mình biết chủ đề (dispute / ticket / intent), khoảng thời gian, và dạng báo cáo muốn xem."
        )

    def _infer_topic(self, question_lower: str) -> str | None:
        score: dict[str, int] = {"dispute": 0, "intent": 0}
        for topic, keywords in self.topic_keywords.items():
            for kw in keywords:
                if kw in question_lower:
                    score[topic] += 1
        if score["dispute"] == 0 and score["intent"] == 0:
            return None
        if score["intent"] >= score["dispute"] and score["intent"] > 0:
            return "intent"
        return "dispute"

    def _merge_with_pending_context(self, question_lower: str, dialog_context: dict[str, Any]) -> str:
        if not dialog_context.get("pending"):
            return question_lower
        topic = str(dialog_context.get("topic") or "").strip().lower()
        if not topic:
            return question_lower
        if topic in question_lower:
            return question_lower
        if question_lower.startswith("@cs support"):
            return f"{question_lower} {topic}"
        return f"@cs support {question_lower} {topic}"

    def _merge_with_thread_context_if_followup(self, question_lower: str, thread_context_text: str | None) -> str:
        if not thread_context_text:
            return question_lower
        if not self._is_followup_short_question(question_lower):
            return question_lower
        context = thread_context_text.lower()
        # Enrich only with high-signal topic hints from thread to avoid noisy routing.
        hints: list[str] = []
        if "dispute" in context:
            hints.append("dispute")
        if any(k in context for k in ["nguyên nhân", "nguyen nhan", "lý do", "ly do", "reason"]):
            hints.extend(["dispute", "nguyên nhân"])
        if "ticket" in context:
            hints.append("ticket")
        if "intent" in context or "ý định" in context or "y dinh" in context:
            hints.append("intent")
        if "shop" in context:
            hints.append("shop")
        if "chargeback" in context:
            hints.append("chargeback")
        if "gateway" in context or "payment gateway" in context or "cổng thanh toán" in context or "cong thanh toan" in context:
            hints.append("gateway")
        if not hints:
            return question_lower
        return f"{question_lower} {' '.join(hints)}"

    def _is_followup_short_question(self, question_lower: str) -> bool:
        compact = re.sub(r"\s+", " ", question_lower).strip()
        words = [w for w in compact.split(" ") if w]
        followup_keywords = [
            "tong",
            "tổng",
            "total",
            "bao nhieu",
            "bao nhiêu",
            "con bao nhieu",
            "còn bao nhiêu",
            "the ticket",
            "thế ticket",
            "the dispute",
            "thế dispute",
        ]
        return len(words) <= 8 or any(k in compact for k in followup_keywords)

    def _infer_role(self, question: str, asker_context: dict[str, Any]) -> str:
        role_text = f"{asker_context.get('role', '')} {asker_context.get('department', '')}".lower()
        if any(token in role_text for token in ["finance", "fin"]):
            return "finance"
        if any(token in role_text for token in ["manager", "lead", "head"]):
            return "cs_manager"
        if any(token in role_text for token in ["ops", "operation", "cs"]):
            return "cs_ops"
        question_lower = question.lower()
        if any(token in question_lower for token in ["chargeback", "p&l", "sku", "80%", "5%"]):
            return "finance"
        if any(token in question_lower for token in ["backlog", "status", "ops"]):
            return "cs_ops"
        return "general"

    def _is_report_request(self, question_lower: str) -> bool:
        report_keywords = [
            "bao cao",
            "báo cáo",
            "gui bao cao",
            "gửi báo cáo",
            "report",
            "chi tiet",
            "chi tiết",
        ]
        return any(keyword in question_lower for keyword in report_keywords)

    def _is_yesterday_report_request(self, question_lower: str) -> bool:
        yesterday_keywords = [
            "hom qua",
            "hôm qua",
            "ngay hom qua",
            "ngày hôm qua",
            "yesterday",
        ]
        has_report_signal = self._is_report_request(question_lower) or "dispute" in question_lower
        has_yesterday_signal = any(keyword in question_lower for keyword in yesterday_keywords)
        return has_report_signal and has_yesterday_signal

    def _is_chargeback_shop_30d_request(self, question_lower: str) -> bool:
        return "chargeback" in question_lower and "shop" in question_lower and "30" in question_lower

    def _is_dispute_shop_30d_request(self, question_lower: str) -> bool:
        return "dispute" in question_lower and "shop" in question_lower and "30" in question_lower

    def _is_dispute_shop_30d_7d_request(self, question_lower: str) -> bool:
        return "dispute" in question_lower and "shop" in question_lower and "30" in question_lower and "7" in question_lower

    def _is_help_request(self, question_lower: str) -> bool:
        return "help" in question_lower or "tro giup" in question_lower or "trợ giúp" in question_lower

    def _is_list_request(self, question_lower: str) -> bool:
        list_keywords = ["list", "liet ke", "liệt kê", "lietkê", "danh sach", "danh sách"]
        return any(k in question_lower for k in list_keywords) and any(
            t in question_lower for t in ["dispute", "ticket"]
        )

    def _is_find_request(self, question_lower: str) -> bool:
        find_keywords = ["find", "tim", "tìm", "search", "tra cuu", "tra cứu"]
        return any(k in question_lower for k in find_keywords) and any(
            t in question_lower for t in ["dispute", "ticket"]
        )

    def _is_total_request(self, question_lower: str) -> bool:
        return any(
            k in question_lower
            for k in ["total", "tong", "tổng", "tong so", "tổng số", "so tong", "số tổng"]
        )

    def _is_ticket_report_request(self, question_lower: str) -> bool:
        return "ticket" in question_lower and (
            self._is_report_request(question_lower) or any(k in question_lower for k in ["bao cao", "báo cáo"])
        )

    def _is_ticket_status_request(self, question_lower: str) -> bool:
        return "ticket" in question_lower and any(k in question_lower for k in ["status", "trang thai", "trạng thái"])

    def _is_dispute_status_request(self, question_lower: str) -> bool:
        has_dispute = "dispute" in question_lower
        has_status = any(k in question_lower for k in ["status", "trang thai", "trạng thái"])
        has_reason = any(k in question_lower for k in ["nguyen nhan", "nguyên nhân", "reason"])
        return has_dispute and has_status and not has_reason

    def _is_dispute_gateway_request(self, question_lower: str) -> bool:
        has_dispute = "dispute" in question_lower
        has_gateway = any(k in question_lower for k in ["gateway", "payment gateway", "cổng thanh toán", "cong thanh toan"])
        has_shop = "shop" in question_lower
        has_ticket = "ticket" in question_lower
        has_report_or_analysis = self._is_report_request(question_lower) or any(
            k in question_lower for k in ["phan tich", "phân tích", "analysis", "bao cao", "báo cáo"]
        )
        return (has_dispute or has_report_or_analysis) and has_gateway and not has_shop and not has_ticket

    def _is_dispute_shop_gateway_request(self, question_lower: str) -> bool:
        has_dispute = "dispute" in question_lower
        has_gateway = any(k in question_lower for k in ["gateway", "payment gateway", "cổng thanh toán", "cong thanh toan"])
        has_shop = "shop" in question_lower
        has_report_or_analysis = self._is_report_request(question_lower) or any(
            k in question_lower for k in ["phan tich", "phân tích", "analysis", "bao cao", "báo cáo"]
        )
        return (has_dispute or has_report_or_analysis) and has_gateway and has_shop

    def _is_ticket_priority_request(self, question_lower: str) -> bool:
        return "ticket" in question_lower and any(
            k in question_lower for k in ["priority", "uu tien", "ưu tiên", "muc do uu tien", "mức độ ưu tiên"]
        )

    def _is_ops_status_actionable_request(self, question_lower: str) -> bool:
        return "status" in question_lower and any(k in question_lower for k in ["can xu ly", "cần xử lý", "xu ly", "xử lý"])

    def _is_ticket_intent_request(self, question_lower: str) -> bool:
        has_intent = any(
            k in question_lower for k in ["intent", "itent", "intet", "y dinh", "ý định", "ý định"]
        )
        has_ticket = "ticket" in question_lower
        has_analysis_phrase = any(
            k in question_lower
            for k in ["phan tich", "phân tích", "theo intent", "intent analysis", "phan tich theo intent"]
        )
        return has_intent and (has_ticket or has_analysis_phrase)

    def _is_ticket_intent_shop_request(self, question_lower: str) -> bool:
        return any(k in question_lower for k in ["intent", "itent", "intet", "y dinh", "ý định", "ý định"]) and (
            "shop" in question_lower
        )

    def _is_trend_ticket_intent_request(self, question_lower: str) -> bool:
        return self._is_trend_request(question_lower) and any(
            k in question_lower for k in ["intent", "itent", "intet", "y dinh", "ý định", "ý định"]
        )

    def _is_trend_ticket_intent_shop_request(self, question_lower: str) -> bool:
        return self._is_trend_ticket_intent_request(question_lower) and "shop" in question_lower

    def _is_trend_specific_intent_request(self, question_lower: str) -> bool:
        if not self._is_trend_request(question_lower):
            return False
        # Accept explicit intent tokens like REFUND_RETURN_REQUEST without requiring the word "intent".
        return bool(re.search(r"\b[A-Z0-9]+_[A-Z0-9_]+\b", question_lower.upper()))

    def _has_specific_intent_in_question(self, question: str, latest_analysis: dict[str, Any]) -> bool:
        if not self._is_trend_request(question.lower()):
            return False
        rows = latest_analysis.get("snapshot_dimensions", {}).get("ticket_intent_trend", [])
        return self._extract_intent_token(question, rows) is not None

    def _is_trend_dispute_reason_request(self, question_lower: str) -> bool:
        return self._is_trend_request(question_lower) and "dispute" in question_lower and any(
            k in question_lower for k in ["nguyen nhan", "nguyên nhân", "reason"]
        )

    def _is_trend_dispute_shop_request(self, question_lower: str) -> bool:
        return self._is_trend_request(question_lower) and "dispute" in question_lower and "shop" in question_lower

    def _is_trend_request(self, question_lower: str) -> bool:
        return any(k in question_lower for k in ["xu huong", "xu hướng", "trend", "xu the", "xu thế"])

    def _is_reason_report_request(self, question_lower: str) -> bool:
        has_reason = any(k in question_lower for k in ["nguyen nhan", "nguyên nhân", "reason", "ly do", "lý do"])
        has_dispute_signal = "dispute" in question_lower or self._is_report_request(question_lower)
        return has_reason and has_dispute_signal

    def _is_ticket_open_end_request(self, question_lower: str) -> bool:
        return ("open cuoi ky" in question_lower or "open cuối kỳ" in question_lower) and (
            "ticket" in question_lower or "open" in question_lower
        )

    def _is_ticket_resolved_request(self, question_lower: str) -> bool:
        return "resolved" in question_lower and any(k in question_lower for k in ["tuan", "tuần", "week"])

    def _is_backlog_request(self, question_lower: str) -> bool:
        return "backlog" in question_lower and any(k in question_lower for k in ["tang", "tăng", "giam", "giảm"])

    def _is_compare_dispute_ticket_request(self, question_lower: str) -> bool:
        return (
            ("so sanh" in question_lower or "so sánh" in question_lower or "compare" in question_lower)
            and "dispute" in question_lower
            and "ticket" in question_lower
        )

    def _is_risk_where_request(self, question_lower: str) -> bool:
        return "risk" in question_lower and any(k in question_lower for k in ["o dau", "ở đâu", "nam o dau", "nằm ở đâu"])


    def _extract_last_n_days(self, question_lower: str) -> int | None:
        has_report_signal = self._is_report_request(question_lower) or "dispute" in question_lower
        if not has_report_signal:
            return None
        match = re.search(r"(\d+)\s*(ngay|ngày|day|days)", question_lower)
        if not match:
            return None
        days = int(match.group(1))
        if days < 2:
            return None
        return days

    def _extract_top_n(self, question_lower: str) -> int | None:
        match = re.search(r"\btop\s*(\d+)\b", question_lower)
        if not match:
            return None
        n = int(match.group(1))
        if n <= 0:
            return None
        return min(n, 30)

    def _extract_find_keyword(self, question_lower: str) -> str | None:
        m = re.search(r"(?:find|tim|tìm|search|tra cuu|tra cứu)\s+(.*)", question_lower)
        if not m:
            return None
        raw = m.group(1).strip()
        raw = re.sub(r"^(dispute|ticket)\s+", "", raw).strip()
        raw = re.sub(r"\s+(trong|trong ky|trong kỳ|30 ngay|30 ngày|7 ngay|7 ngày|thang nay|tháng này|this month)$", "", raw)
        if not raw:
            return None
        return raw

    def _build_report_reply(self, latest_analysis: dict[str, Any]) -> str:
        metrics = latest_analysis.get("metrics_current", {})
        deltas = latest_analysis.get("deltas", {})
        dims = latest_analysis.get("snapshot_dimensions", {})
        yesterday = dims.get("yesterday_metrics", {})
        drivers = latest_analysis.get("top_drivers", [])
        top_driver = "n/a"
        if drivers:
            d = drivers[0]
            top_driver = f"{d.get('name')} ({d.get('delta_abs')})"

        amount = metrics.get("amount_at_risk")
        amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
        y_amount = yesterday.get("amount_at_risk")
        y_amount_text = f"{y_amount:,.2f}" if isinstance(y_amount, (int, float)) else "n/a"

        period_text = self._format_period(latest_analysis.get("period_current", {}))
        as_at_text = self._format_as_at(latest_analysis.get("period_current", {}).get("end"))
        return "\n".join(
            [
                f"{self.prefix}Báo cáo dispute",
                period_text,
                f"Current: disputes={metrics.get('dispute_count')} | rate={metrics.get('dispute_rate')}% | amount={amount_text}",
                f"WoW: delta={deltas.get('dispute_count_pct')}% | top_driver={top_driver}",
                "Yesterday:",
                f"- disputes={yesterday.get('dispute_count')} | orders={yesterday.get('orders_count')}",
                f"- rate={yesterday.get('dispute_rate')}% | amount={y_amount_text}",
                as_at_text,
            ]
        )

    def _build_list_reply(self, latest_analysis: dict[str, Any], question_lower: str, top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        period_text = self._format_period(latest_analysis.get("period_current", {}))
        as_at_text = self._format_as_at(latest_analysis.get("period_current", {}).get("end"))
        limit = top_n or 10

        if "dispute" in question_lower:
            by_reason = sorted(
                dims.get("by_reason", []),
                key=lambda r: (r.get("disputes_distinct") if isinstance(r.get("disputes_distinct"), (int, float)) else -1),
                reverse=True,
            )[:limit]
            by_status = sorted(
                dims.get("by_status", []),
                key=lambda r: (r.get("disputes_distinct") if isinstance(r.get("disputes_distinct"), (int, float)) else -1),
                reverse=True,
            )[:limit]
            lines = [f"{self.prefix}List dispute (chi tiết)", period_text, "Theo nguyên nhân:"]
            for row in by_reason:
                lines.append(f"- {row.get('reason_normalize')}: {row.get('disputes_distinct')}")
            lines.append("Theo status:")
            for row in by_status:
                lines.append(f"- {row.get('status_normalize')}: {row.get('disputes_distinct')}")
            by_gateway_block = dims.get("dispute_by_gateway", {})
            by_gateway_rows = by_gateway_block.get("rows", []) if isinstance(by_gateway_block, dict) else []
            if by_gateway_rows:
                lines.append("Theo payment gateway:")
                ranked_gw = sorted(
                    by_gateway_rows,
                    key=lambda r: (
                        r.get("disputes_distinct") if isinstance(r.get("disputes_distinct"), (int, float)) else -1
                    ),
                    reverse=True,
                )[:limit]
                for row in ranked_gw:
                    lines.append(f"- {row.get('gateway') or 'Unknown'}: {row.get('disputes_distinct')}")
            lines.append(as_at_text)
            return "\n".join(lines)

        ticket_status = sorted(
            dims.get("ticket_by_status", []),
            key=lambda r: (r.get("tickets_distinct") if isinstance(r.get("tickets_distinct"), (int, float)) else -1),
            reverse=True,
        )[:limit]
        ticket_priority = sorted(
            dims.get("ticket_by_priority", []),
            key=lambda r: (r.get("tickets_distinct") if isinstance(r.get("tickets_distinct"), (int, float)) else -1),
            reverse=True,
        )[:limit]
        ticket_intent = sorted(
            dims.get("ticket_by_intent", []),
            key=lambda r: (r.get("tickets_distinct") if isinstance(r.get("tickets_distinct"), (int, float)) else -1),
            reverse=True,
        )[:limit]
        lines = [f"{self.prefix}List ticket (chi tiết)", period_text, "Theo status:"]
        for row in ticket_status:
            lines.append(f"- {row.get('status_normalize')}: {row.get('tickets_distinct')}")
        lines.append("Theo priority:")
        for row in ticket_priority:
            lines.append(f"- {row.get('priority')}: {row.get('tickets_distinct')}")
        lines.append("Theo intent:")
        for row in ticket_intent:
            lines.append(f"- {row.get('cf_ai_intent') or 'Unknown'}: {row.get('tickets_distinct')}")
        lines.append(as_at_text)
        return "\n".join(lines)

    def _build_find_reply(self, latest_analysis: dict[str, Any], question_lower: str) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        keyword = self._extract_find_keyword(question_lower)
        if not keyword:
            return (
                f"{self.prefix}Mình cần từ khóa để tìm. "
                "Ví dụ: `@CS support find dispute Product Not Received` hoặc `@CS support tìm ticket REFUND_RETURN_REQUEST`."
            )
        kw = keyword.lower().strip()
        period_text = self._format_period(latest_analysis.get("period_current", {}))
        as_at_text = self._format_as_at(latest_analysis.get("period_current", {}).get("end"))

        if "dispute" in question_lower:
            rows: list[str] = []
            for r in dims.get("by_reason", []):
                v = str(r.get("reason_normalize") or "")
                if kw in v.lower():
                    rows.append(f"- reason={v}: {r.get('disputes_distinct')}")
            for r in dims.get("by_status", []):
                v = str(r.get("status_normalize") or "")
                if kw in v.lower():
                    rows.append(f"- status={v}: {r.get('disputes_distinct')}")
            for r in dims.get("by_store", []):
                v = str(r.get("shop_code") or "")
                if kw in v.lower():
                    rows.append(f"- shop={v}: disputes={r.get('disputes_distinct')}, amount={r.get('amount_at_risk')}")
            by_gateway_block = dims.get("dispute_by_gateway", {})
            for r in (by_gateway_block.get("rows", []) if isinstance(by_gateway_block, dict) else []):
                v = str(r.get("gateway") or "")
                if kw in v.lower():
                    amount = r.get("amount_at_risk")
                    amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
                    rows.append(f"- gateway={v}: disputes={r.get('disputes_distinct')}, amount={amount_text}")
            by_shop_gateway_block = dims.get("dispute_by_shop_gateway", {})
            for r in (by_shop_gateway_block.get("rows", []) if isinstance(by_shop_gateway_block, dict) else []):
                shop = str(r.get("shop_code") or "")
                gateway = str(r.get("gateway") or "")
                target = f"{shop} {gateway}".strip().lower()
                if kw in target:
                    amount = r.get("amount_at_risk")
                    amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
                    rows.append(
                        f"- shop={shop or 'Unknown'}, gateway={gateway or 'Unknown'}: disputes={r.get('disputes_distinct')}, amount={amount_text}"
                    )
            if not rows:
                return f"{self.prefix}Không tìm thấy dispute theo từ khóa `{keyword}` trong kỳ hiện tại."
            return "\n".join([f"{self.prefix}Find dispute: `{keyword}`", period_text, *rows[:20], as_at_text])

        rows = []
        for r in dims.get("ticket_by_intent", []):
            v = str(r.get("cf_ai_intent") or "")
            if kw in v.lower():
                rows.append(f"- intent={v or 'Unknown'}: {r.get('tickets_distinct')}")
        for r in dims.get("ticket_by_status", []):
            v = str(r.get("status_normalize") or "")
            if kw in v.lower():
                rows.append(f"- status={v}: {r.get('tickets_distinct')}")
        for r in dims.get("ticket_by_priority", []):
            v = str(r.get("priority") or "")
            if kw in v.lower():
                rows.append(f"- priority={v}: {r.get('tickets_distinct')}")
        for r in dims.get("ticket_by_group", []):
            v = str(r.get("cf_assigned_group_norm") or "")
            if kw in v.lower():
                rows.append(f"- group={v}: {r.get('tickets_distinct')}")
        if not rows:
            return f"{self.prefix}Không tìm thấy ticket theo từ khóa `{keyword}` trong kỳ hiện tại."
        return "\n".join([f"{self.prefix}Find ticket: `{keyword}`", period_text, *rows[:20], as_at_text])

    def _build_yesterday_reply(self, latest_analysis: dict[str, Any]) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        yesterday = dims.get("yesterday_metrics", {})
        y_amount = yesterday.get("amount_at_risk")
        y_amount_text = f"{y_amount:,.2f}" if isinstance(y_amount, (int, float)) else "n/a"
        period_text = self._format_period(latest_analysis.get("period_current", {}))
        as_at_text = self._format_as_at(latest_analysis.get("period_current", {}).get("end"))
        return "\n".join(
            [
                f"{self.prefix}Báo cáo dispute | Hôm qua",
                period_text,
                f"disputes={yesterday.get('dispute_count')} | orders={yesterday.get('orders_count')}",
                f"rate={yesterday.get('dispute_rate')}% | amount={y_amount_text}",
                as_at_text,
            ]
        )

    def _build_last_n_days_reply(self, latest_analysis: dict[str, Any], days: int) -> tuple[str, int | None]:
        dims = latest_analysis.get("snapshot_dimensions", {})
        key = f"last_{days}_days_metrics"
        period_metrics = dims.get(key, {})
        if not period_metrics:
            return (f"{self.prefix}Đang cập nhật dữ liệu {days} ngày, vui lòng đợi một chút.", days)

        amount = period_metrics.get("amount_at_risk")
        amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
        period_text = self._format_period(latest_analysis.get("period_current", {}))
        as_at_text = self._format_as_at(latest_analysis.get("period_current", {}).get("end"))
        return (
            "\n".join(
                [
                    f"{self.prefix}Báo cáo dispute | {days} ngày vừa qua",
                    period_text,
                    f"disputes={period_metrics.get('dispute_count')} | orders={period_metrics.get('orders_count')}",
                    f"rate={period_metrics.get('dispute_rate')}% | amount={amount_text}",
                    as_at_text,
                ]
            ),
            None,
        )

    def _build_chargeback_shop_30d_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        block = dims.get("finance_shop_30d", {})
        rows = block.get("rows", [])
        if block.get("status") == "unavailable":
            return (
                f"{self.prefix}Em đã chạy query lại nhưng nguồn dữ liệu shop 30 ngày đang tạm unavailable. "
                "Vui lòng thử lại sau ít phút."
            )
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu chargeback theo shop 30 ngày."
        ranked = sorted(
            rows,
            key=lambda r: (r.get("chargeback_rate") if isinstance(r.get("chargeback_rate"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        if not block.get("chargeback_available", False):
            return (
                f"{self.prefix}Chưa map được field chargeback trong dataset hiện tại. "
                "Có thể trả dispute_rate theo shop 30 ngày, hoặc cập nhật mapping field chargeback."
            )
        lines = [
            f"{self.prefix}Chargeback theo shop | 30 ngày gần nhất",
            self._format_period(latest_analysis.get("period_current", {})),
            "Định nghĩa: Chargeback = dispute_amount",
            "Cột: CB Amount | CB/Order | CB/GMV",
        ]
        ranked = [r for r in ranked if isinstance(r.get("chargeback_rate"), (int, float))]
        if not ranked:
            return f"{self.prefix}Chưa có chargeback (dispute amount) hợp lệ theo shop trong 30 ngày gần nhất."
        for row in ranked:
            amount = row.get("chargeback_amount")
            amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
            order_amount = row.get("order_amount")
            order_amount_text = f"{order_amount:,.2f}" if isinstance(order_amount, (int, float)) else "n/a"
            cb_order = row.get("chargeback_rate")
            cb_order_text = f"{cb_order:.2f}" if isinstance(cb_order, (int, float)) else "n/a"
            cb_gmv = row.get("chargeback_amount_over_order_amount")
            cb_gmv_text = f"{cb_gmv:.2f}%" if isinstance(cb_gmv, (int, float)) else "n/a"
            lines.append(
                f"- {row.get('shop_code')}: {amount_text} | {cb_order_text} | {cb_gmv_text}"
            )
            lines.append(
                f"  volume: orders={row.get('orders_count')}, GMV={order_amount_text}"
            )
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_dispute_shop_30d_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        block = dims.get("finance_shop_30d", {})
        rows = block.get("rows", [])
        if block.get("status") == "unavailable":
            return (
                f"{self.prefix}Em đã chạy query lại nhưng nguồn dữ liệu shop 30 ngày đang tạm unavailable. "
                "Vui lòng thử lại sau ít phút."
            )
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu dispute theo shop 30 ngày."
        ranked = sorted(
            [
                r
                for r in rows
                if isinstance(r.get("dispute_rate"), (int, float))
                and isinstance(r.get("orders_count"), (int, float))
                and r.get("orders_count") > 0
            ],
            key=lambda r: (r.get("dispute_rate") if isinstance(r.get("dispute_rate"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        lines = [
            f"{self.prefix}Tỷ lệ dispute theo shop (rolling 30 ngày, mẫu số=orders):",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            lines.append(
                f"- {row.get('shop_code')}: {row.get('dispute_rate')}% "
                f"(disputes={row.get('dispute_count')}, orders={row.get('orders_count')})"
            )
        total_disputes = sum(
            float(r.get("dispute_count", 0))
            for r in rows
            if isinstance(r.get("dispute_count"), (int, float))
        )
        lines.append(f"total_disputes={int(total_disputes)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_dispute_shop_30d_7d_reply(self, latest_analysis: dict[str, Any], question: str) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        b30 = dims.get("finance_shop_30d", {})
        b7 = dims.get("finance_shop_7d", {})
        shop_hint = self._extract_shop_from_question(question)

        if b30.get("status") == "unavailable" and b7.get("status") == "unavailable":
            return (
                f"{self.prefix}Em đã chạy query lại nhưng nguồn dữ liệu shop 30/7 ngày đang tạm unavailable. "
                "Vui lòng thử lại sau ít phút."
            )

        row30 = self._pick_shop_row(b30.get("rows", []), shop_hint)
        row7 = self._pick_shop_row(b7.get("rows", []), shop_hint)
        shop_name = (row30 or row7 or {}).get("shop_code") or (shop_hint or "shop yêu cầu")
        lines = [
            f"{self.prefix}Tỷ lệ dispute theo shop | 30 ngày vs 7 ngày",
            self._format_period(latest_analysis.get("period_current", {})),
            f"shop={shop_name}",
        ]
        if row30:
            lines.append(
                f"30d: rate={row30.get('dispute_rate')}% (disputes={row30.get('dispute_count')}, orders={row30.get('orders_count')})"
            )
        else:
            lines.append("30d: unavailable")
        if row7:
            lines.append(
                f"7d: rate={row7.get('dispute_rate')}% (disputes={row7.get('dispute_count')}, orders={row7.get('orders_count')})"
            )
        else:
            lines.append("7d: unavailable")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_reason_report_reply(
        self, latest_analysis: dict[str, Any], question_lower: str, top_n: int | None
    ) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("by_reason", [])
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu theo nguyên nhân."

        direction = self._resolve_sort_direction(question_lower)
        ranked = sorted(
            rows,
            key=lambda r: (r.get("disputes_distinct") if isinstance(r.get("disputes_distinct"), (int, float)) else -1),
            reverse=(direction == "desc"),
        )
        if top_n:
            ranked = ranked[:top_n]

        direction_text = "cao đến thấp" if direction == "desc" else "thấp đến cao"
        lines = [
            f"{self.prefix}Báo cáo dispute theo nguyên nhân | sắp xếp {direction_text}",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            lines.append(f"- {row.get('reason_normalize')}: {row.get('disputes_distinct')}")
        total_disputes = sum(
            float(r.get("disputes_distinct", 0))
            for r in rows
            if isinstance(r.get("disputes_distinct"), (int, float))
        )
        lines.append(f"total_disputes={int(total_disputes)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_ticket_report_reply(self, latest_analysis: dict[str, Any]) -> str:
        metrics = latest_analysis.get("metrics_current", {})
        deltas = latest_analysis.get("deltas", {})
        ticket_summary = latest_analysis.get("narrative_blocks", {}).get("ticket_summary", {})
        return "\n".join(
            [
                f"{self.prefix}Báo cáo ticket",
                self._format_period(latest_analysis.get("period_current", {})),
                f"created={ticket_summary.get('ticket_created', metrics.get('ticket_count'))} | "
                f"resolved={ticket_summary.get('ticket_resolved')}",
                f"open_start={ticket_summary.get('open_start')} | open_end={ticket_summary.get('open_end')}",
                f"WoW={deltas.get('ticket_count_pct')}%",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _build_ticket_status_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("ticket_by_status", [])
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu ticket theo status."
        ranked = sorted(
            rows,
            key=lambda r: (r.get("tickets_distinct") if isinstance(r.get("tickets_distinct"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        lines = [
            f"{self.prefix}Ticket theo status",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            lines.append(f"- {row.get('status_normalize')}: {row.get('tickets_distinct')}")
        total_tickets = sum(
            float(r.get("tickets_distinct", 0))
            for r in rows
            if isinstance(r.get("tickets_distinct"), (int, float))
        )
        lines.append(f"total_tickets={int(total_tickets)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_dispute_status_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("by_status", [])
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu dispute theo status."
        ranked = sorted(
            rows,
            key=lambda r: (r.get("disputes_distinct") if isinstance(r.get("disputes_distinct"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        lines = [
            f"{self.prefix}Dispute theo status",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            lines.append(f"- {row.get('status_normalize')}: {row.get('disputes_distinct')}")
        total_disputes = sum(
            float(r.get("disputes_distinct", 0))
            for r in rows
            if isinstance(r.get("disputes_distinct"), (int, float))
        )
        lines.append(f"total_disputes={int(total_disputes)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_dispute_gateway_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        block = dims.get("dispute_by_gateway", {})
        rows = block.get("rows", []) if isinstance(block, dict) else []
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu dispute theo payment gateway."
        ranked = sorted(
            rows,
            key=lambda r: (r.get("disputes_distinct") if isinstance(r.get("disputes_distinct"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        lines = [
            f"{self.prefix}Dispute theo payment gateway",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            amount = row.get("amount_at_risk")
            amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
            lines.append(f"- {row.get('gateway') or 'Unknown'}: disputes={row.get('disputes_distinct')} | amount={amount_text}")
        total_disputes = sum(
            float(r.get("disputes_distinct", 0)) for r in rows if isinstance(r.get("disputes_distinct"), (int, float))
        )
        lines.append(f"total_disputes={int(total_disputes)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_dispute_shop_gateway_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        block = dims.get("dispute_by_shop_gateway", {})
        rows = block.get("rows", []) if isinstance(block, dict) else []
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu risk dispute theo shop và gateway."
        ranked = sorted(
            rows,
            key=lambda r: (r.get("disputes_distinct") if isinstance(r.get("disputes_distinct"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        lines = [
            f"{self.prefix}Risk dispute theo shop và gateway",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            amount = row.get("amount_at_risk")
            amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
            lines.append(
                f"- shop={row.get('shop_code') or 'Unknown'}, gateway={row.get('gateway') or 'Unknown'}: "
                f"disputes={row.get('disputes_distinct')} | amount={amount_text}"
            )
        total_disputes = sum(
            float(r.get("disputes_distinct", 0)) for r in rows if isinstance(r.get("disputes_distinct"), (int, float))
        )
        lines.append(f"total_disputes={int(total_disputes)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_ops_status_actionable_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        return self._build_ticket_status_reply(latest_analysis, top_n or 3).replace(
            "Ticket theo status", "Top status cần xử lý"
        )

    def _build_ticket_priority_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("ticket_by_priority", [])
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu ticket theo priority."
        ranked = sorted(
            rows,
            key=lambda r: (r.get("tickets_distinct") if isinstance(r.get("tickets_distinct"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        lines = [
            f"{self.prefix}Ticket theo priority",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            lines.append(f"- {row.get('priority')}: {row.get('tickets_distinct')}")
        total_tickets = sum(
            float(r.get("tickets_distinct", 0))
            for r in rows
            if isinstance(r.get("tickets_distinct"), (int, float))
        )
        lines.append(f"total_tickets={int(total_tickets)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_ticket_intent_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("ticket_by_intent", [])
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu ticket theo intent."
        ranked = sorted(
            rows,
            key=lambda r: (r.get("tickets_distinct") if isinstance(r.get("tickets_distinct"), (int, float)) else -1),
            reverse=True,
        )
        if top_n:
            ranked = ranked[:top_n]
        lines = [
            f"{self.prefix}Ticket theo intent",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for row in ranked:
            intent_name = row.get("cf_ai_intent") or "Unknown"
            lines.append(f"- {intent_name}: {row.get('tickets_distinct')}")
        total_tickets = sum(
            float(r.get("tickets_distinct", 0))
            for r in rows
            if isinstance(r.get("tickets_distinct"), (int, float))
        )
        lines.append(f"total_tickets={int(total_tickets)}")
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _build_trend_ticket_intent_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("ticket_intent_trend", [])
        return self._build_trend_reply(
            latest_analysis=latest_analysis,
            title="Xu hướng ticket theo intent",
            rows=rows,
            key_builder=lambda r: str(r.get("cf_ai_intent") or "Unknown"),
            value_field="tickets_distinct",
            top_n=top_n,
        )

    def _build_trend_ticket_intent_shop_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("ticket_intent_shop_trend", [])
        return self._build_trend_reply(
            latest_analysis=latest_analysis,
            title="Xu hướng ticket theo intent theo shop",
            rows=rows,
            key_builder=lambda r: f"{r.get('shop_code') or 'Unknown'} | {r.get('cf_ai_intent') or 'Unknown'}",
            value_field="tickets_distinct",
            top_n=top_n,
        )

    def _build_trend_specific_intent_reply(self, latest_analysis: dict[str, Any], question: str) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("ticket_intent_trend", [])
        target_intent = self._extract_intent_token(question, rows)
        if not target_intent:
            return f"{self.prefix}Chưa nhận diện được mã intent cụ thể."
        filtered = [r for r in rows if str(r.get("cf_ai_intent") or "").upper() == target_intent]
        if not filtered:
            return (
                f"{self.prefix}Không có dữ liệu xu hướng cho intent {target_intent} trong kỳ hiện tại. "
                f"{self._format_period(latest_analysis.get('period_current', {}))}\n"
                f"{self._format_as_at(latest_analysis.get('period_current', {}).get('end'))}"
            )
        summary = self._summarize_trend(
            filtered,
            key_builder=lambda r: str(r.get("cf_ai_intent") or "Unknown"),
            value_field="tickets_distinct",
        )
        if not summary:
            return f"{self.prefix}Chưa đủ dữ liệu để phân tích xu hướng cho {target_intent}."
        item = summary[0]
        return "\n".join(
            [
                f"{self.prefix}Xu hướng intent {target_intent}",
                self._format_period(latest_analysis.get("period_current", {})),
                f"- {item['key']}: {item['start']} -> {item['end']} (Δ={item['delta']}, {item['direction']})",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _extract_intent_token(self, question: str, rows: list[dict[str, Any]]) -> str | None:
        candidates = re.findall(r"[A-Z][A-Z0-9_]{4,}", question.upper())
        if not candidates:
            return None
        blocked = {"CS", "SUPPORT", "DISPUTE", "TREND", "WEEKLY", "FROM"}
        filtered = [c for c in candidates if c not in blocked]
        if not filtered:
            return None
        valid_intents = {str(r.get("cf_ai_intent") or "").upper() for r in rows if r.get("cf_ai_intent")}
        for c in filtered:
            if "_" in c and c in valid_intents:
                return c
        for c in filtered:
            if c in valid_intents:
                return c
        for c in filtered:
            if "_" in c:
                return c
        # Support free-text intent phrase: "refund return request" -> "REFUND_RETURN_REQUEST".
        normalized_words = re.sub(r"[^a-z0-9\\s]", " ", question.lower()).split()
        if normalized_words:
            phrase = "_".join(normalized_words).upper()
            for intent in valid_intents:
                if intent and intent in phrase:
                    return intent
        return filtered[0]

    def _build_trend_dispute_reason_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("dispute_reason_trend", [])
        return self._build_trend_reply(
            latest_analysis=latest_analysis,
            title="Xu hướng dispute theo nguyên nhân",
            rows=rows,
            key_builder=lambda r: str(r.get("reason_normalize") or "Unknown"),
            value_field="disputes_distinct",
            top_n=top_n,
        )

    def _build_trend_dispute_shop_reply(self, latest_analysis: dict[str, Any], top_n: int | None) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        rows = dims.get("dispute_shop_trend", [])
        return self._build_trend_reply(
            latest_analysis=latest_analysis,
            title="Xu hướng dispute theo shop",
            rows=rows,
            key_builder=lambda r: str(r.get("shop_code") or "Unknown"),
            value_field="disputes_distinct",
            top_n=top_n,
        )

    def _build_trend_reply(
        self,
        *,
        latest_analysis: dict[str, Any],
        title: str,
        rows: list[dict[str, Any]],
        key_builder,
        value_field: str,
        top_n: int | None,
    ) -> str:
        if not rows:
            return f"{self.prefix}Chưa có dữ liệu {title.lower()}."
        summary = self._summarize_trend(rows, key_builder, value_field)
        limit = top_n or 5
        summary = summary[:limit]
        lines = [
            f"{self.prefix}{title}",
            self._format_period(latest_analysis.get("period_current", {})),
        ]
        for item in summary:
            lines.append(
                f"- {item['key']}: {item['start']} -> {item['end']} (Δ={item['delta']}, {item['direction']})"
            )
        lines.append(self._format_as_at(latest_analysis.get("period_current", {}).get("end")))
        return "\n".join(lines)

    def _summarize_trend(self, rows: list[dict[str, Any]], key_builder, value_field: str) -> list[dict[str, Any]]:
        grouped: dict[str, list[tuple[str, float]]] = {}
        for row in rows:
            key = key_builder(row)
            date_value = str(row.get("date_us") or "")
            metric = row.get(value_field)
            if not isinstance(metric, (int, float)) or not date_value:
                continue
            grouped.setdefault(key, []).append((date_value, float(metric)))

        result: list[dict[str, Any]] = []
        for key, series in grouped.items():
            series.sort(key=lambda x: x[0])
            start = series[0][1]
            end = series[-1][1]
            delta = round(end - start, 2)
            direction = "tăng" if delta > 0 else ("giảm" if delta < 0 else "đi ngang")
            result.append({"key": key, "start": start, "end": end, "delta": delta, "direction": direction})

        result.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return result

    def _resolve_sort_direction(self, question_lower: str) -> str:
        if any(k in question_lower for k in ["thap den cao", "thấp đến cao", "it den nhieu", "ít đến nhiều"]):
            return "asc"
        if any(k in question_lower for k in ["cao den thap", "cao đến thấp", "nhieu den it", "nhiều đến ít"]):
            return "desc"
        # phrase like "tu it ... den cao" tends to mean increasing order
        if "tu it" in question_lower or "từ ít" in question_lower:
            return "asc"
        return "desc"

    def _build_help_reply(self) -> str:
        return "\n".join(
            [
                f"{self.prefix}Danh mục câu hỏi em trả lời được:",
                "- Báo cáo dispute: weekly / hôm qua / N ngày vừa qua",
                "- Báo cáo dispute theo nguyên nhân (cao đến thấp | thấp đến cao)",
                "- Tỷ lệ dispute theo shop 30 ngày (có hỗ trợ top N)",
                "- Chargeback theo shop 30 ngày (dispute_amount, có hỗ trợ top N)",
                "- Báo cáo ticket weekly: created, resolved, open_start, open_end, WoW",
                "- Ticket theo status/priority/intent (có hỗ trợ top N)",
                "- Backlog tăng/giảm, open cuối kỳ, resolved tuần này",
                "- So sánh dispute và ticket tuần này; risk tuần này nằm ở đâu",
                "- Follow-up tổng/total: trả tổng số tương ứng theo ngữ cảnh hiện có",
                "Gợi ý: @CS support báo cáo ticket | @CS support top 5 tỷ lệ dispute theo shop trong 30 ngày gần nhất",
            ]
        )

    def _build_total_reply(self, latest_analysis: dict[str, Any], question_lower: str) -> str:
        dims = latest_analysis.get("snapshot_dimensions", {})
        metrics = latest_analysis.get("metrics_current", {})
        by_reason = dims.get("by_reason", [])
        ticket_by_status = dims.get("ticket_by_status", [])

        total_disputes_reason = sum(
            float(r.get("disputes_distinct", 0))
            for r in by_reason
            if isinstance(r.get("disputes_distinct"), (int, float))
        )
        total_tickets_status = sum(
            float(r.get("tickets_distinct", 0))
            for r in ticket_by_status
            if isinstance(r.get("tickets_distinct"), (int, float))
        )
        total_disputes = metrics.get("dispute_count")
        total_tickets = metrics.get("ticket_count")

        if any(k in question_lower for k in ["nguyen nhan", "nguyên nhân", "ly do", "lý do", "reason", "dispute"]):
            return "\n".join(
                [
                    f"{self.prefix}Tổng dispute theo nguyên nhân",
                    self._format_period(latest_analysis.get("period_current", {})),
                    f"total_disputes={int(total_disputes_reason)}",
                    self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
                ]
            )
        if "ticket" in question_lower:
            return "\n".join(
                [
                    f"{self.prefix}Tổng ticket",
                    self._format_period(latest_analysis.get("period_current", {})),
                    f"total_tickets={int(total_tickets_status) if total_tickets_status else total_tickets}",
                    self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
                ]
            )
        return "\n".join(
            [
                f"{self.prefix}Tổng số hiện có",
                self._format_period(latest_analysis.get("period_current", {})),
                f"total_disputes={int(total_disputes_reason) if total_disputes_reason else total_disputes}",
                f"total_tickets={int(total_tickets_status) if total_tickets_status else total_tickets}",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _build_ticket_open_end_reply(self, latest_analysis: dict[str, Any]) -> str:
        ticket_summary = latest_analysis.get("narrative_blocks", {}).get("ticket_summary", {})
        return "\n".join(
            [
                f"{self.prefix}Open cuối kỳ",
                self._format_period(latest_analysis.get("period_current", {})),
                f"open_end={ticket_summary.get('open_end')}",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _build_ticket_resolved_reply(self, latest_analysis: dict[str, Any]) -> str:
        ticket_summary = latest_analysis.get("narrative_blocks", {}).get("ticket_summary", {})
        return "\n".join(
            [
                f"{self.prefix}Resolved trong kỳ",
                self._format_period(latest_analysis.get("period_current", {})),
                f"resolved={ticket_summary.get('ticket_resolved')}",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _build_backlog_reply(self, latest_analysis: dict[str, Any]) -> str:
        ticket_summary = latest_analysis.get("narrative_blocks", {}).get("ticket_summary", {})
        open_start = ticket_summary.get("open_start")
        open_end = ticket_summary.get("open_end")
        delta_text = "n/a"
        trend_text = "không rõ"
        if isinstance(open_start, (int, float)) and isinstance(open_end, (int, float)):
            delta = int(open_end - open_start)
            delta_text = f"{delta:+d}"
            trend_text = "tăng" if delta > 0 else ("giảm" if delta < 0 else "đi ngang")
        return "\n".join(
            [
                f"{self.prefix}Backlog tuần này",
                self._format_period(latest_analysis.get("period_current", {})),
                f"open_start={open_start} | open_end={open_end} | delta={delta_text} ({trend_text})",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _build_compare_dispute_ticket_reply(self, latest_analysis: dict[str, Any]) -> str:
        metrics = latest_analysis.get("metrics_current", {})
        deltas = latest_analysis.get("deltas", {})
        ticket_summary = latest_analysis.get("narrative_blocks", {}).get("ticket_summary", {})
        amount = metrics.get("amount_at_risk")
        amount_text = f"{amount:,.2f}" if isinstance(amount, (int, float)) else "n/a"
        return "\n".join(
            [
                f"{self.prefix}So sánh dispute và ticket",
                self._format_period(latest_analysis.get("period_current", {})),
                f"Dispute: count={metrics.get('dispute_count')} | rate={metrics.get('dispute_rate')}% | amount={amount_text} | WoW={deltas.get('dispute_count_pct')}%",
                f"Ticket: created={ticket_summary.get('ticket_created')} | resolved={ticket_summary.get('ticket_resolved')} | open_start={ticket_summary.get('open_start')} | open_end={ticket_summary.get('open_end')} | WoW={deltas.get('ticket_count_pct')}%",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _build_risk_where_reply(self, latest_analysis: dict[str, Any]) -> str:
        drivers = latest_analysis.get("top_drivers", [])
        top_driver = drivers[0].get("name") if drivers else "n/a"
        top_status = self._top_ticket_status(latest_analysis)
        return "\n".join(
            [
                f"{self.prefix}Risk tuần này nằm ở đâu",
                self._format_period(latest_analysis.get("period_current", {})),
                f"- Dispute driver chính: {top_driver}",
                f"- Ticket status chính: {top_status}",
                self._format_as_at(latest_analysis.get("period_current", {}).get("end")),
            ]
        )

    def _top_ticket_status(self, latest_analysis: dict[str, Any]) -> str:
        rows = latest_analysis.get("snapshot_dimensions", {}).get("ticket_by_status", [])
        if not rows:
            return "n/a"
        ranked = sorted(
            rows,
            key=lambda r: (r.get("tickets_distinct") if isinstance(r.get("tickets_distinct"), (int, float)) else -1),
            reverse=True,
        )
        top = ranked[0]
        return f"{top.get('status_normalize')}: {top.get('tickets_distinct')}"

    def _build_multi_intent_reply(
        self, question_lower: str, question: str, latest_analysis: dict[str, Any], top_n: int | None
    ) -> str | None:
        blocks: list[str] = []
        if self._is_trend_specific_intent_request(question_lower) or self._has_specific_intent_in_question(
            question, latest_analysis
        ):
            blocks.append(self._build_trend_specific_intent_reply(latest_analysis, question))
        if self._is_reason_report_request(question_lower):
            blocks.append(self._build_reason_report_reply(latest_analysis, question_lower, top_n))
        if self._is_chargeback_shop_30d_request(question_lower):
            blocks.append(self._build_chargeback_shop_30d_reply(latest_analysis, top_n))
        if self._is_ticket_priority_request(question_lower):
            blocks.append(self._build_ticket_priority_reply(latest_analysis, top_n))
        if self._is_ticket_intent_request(question_lower):
            blocks.append(self._build_ticket_intent_reply(latest_analysis, top_n))

        if len(blocks) <= 1:
            return None
        deduped: list[str] = []
        seen: set[str] = set()
        for b in blocks:
            if b not in seen:
                deduped.append(b)
                seen.add(b)
        return "\n\n".join(deduped)

    def _extract_shop_from_question(self, question: str) -> str | None:
        q = question.lower()
        m = re.search(r"([a-z0-9][a-z0-9\-.]*\.myshopify\.com)", q)
        if m:
            return m.group(1)
        # fallback: short shop code token like "silveryprinting"
        m2 = re.search(r"\b([a-z0-9][a-z0-9\-_]{2,})\b", q)
        if m2 and m2.group(1) not in {"support", "dispute", "ticket", "ngay", "ngày", "total", "tong", "tổng"}:
            return m2.group(1)
        return None

    def _pick_shop_row(self, rows: list[dict[str, Any]], shop_hint: str | None) -> dict[str, Any] | None:
        if not rows:
            return None
        if shop_hint:
            for row in rows:
                code = str(row.get("shop_code") or "").lower()
                if shop_hint in code or code in shop_hint:
                    return row
        return rows[0]

    def _format_period(self, period: dict[str, Any]) -> str:
        start = self._to_ymd(period.get("start"))
        end = self._to_ymd(period.get("end"))
        if start == "n/a" or end == "n/a":
            return "Period: n/a"
        return f"Period: from {start} to {end}"

    def _format_as_at(self, iso_dt: Any) -> str:
        return f"As at: {self._to_ymd_hm(iso_dt)}"

    def _to_ymd_hm(self, iso_dt: Any) -> str:
        if not iso_dt or not isinstance(iso_dt, str):
            return "n/a"
        try:
            dt = datetime.fromisoformat(iso_dt)
            return dt.strftime("%y%m%d %H%M")
        except ValueError:
            return "n/a"

    def _to_ymd(self, iso_dt: Any) -> str:
        if not iso_dt or not isinstance(iso_dt, str):
            return "n/a"
        try:
            dt = datetime.fromisoformat(iso_dt)
            return dt.strftime("%y%m%d")
        except ValueError:
            return "n/a"
