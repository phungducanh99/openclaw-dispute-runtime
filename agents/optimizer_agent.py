from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OptimizationFinding:
    severity: str
    issue: str
    evidence: str
    fix_suggestion: str


class OptimizerAgent:
    """
    Reusable optimizer agent.
    Reads Q&A outputs and returns findings + patch plan candidates.
    """

    def review(self, qa_rows: list[dict[str, Any]], *, expected_prefix: str | None = None) -> dict[str, Any]:
        findings: list[OptimizationFinding] = []
        prefix = expected_prefix.strip() if isinstance(expected_prefix, str) else ""
        for row in qa_rows:
            q = str(row.get("question", ""))
            a = str(row.get("answer", ""))
            if prefix and not a.startswith(prefix):
                findings.append(
                    OptimizationFinding(
                        severity="high",
                        issue="Missing bot prefix",
                        evidence=f"Q={q} | A={a[:120]} | expected_prefix={prefix}",
                        fix_suggestion="Enforce unified response prefix in formatter.",
                    )
                )
            if "Yêu cầu này hiện chưa đủ điều kiện" in a and self._looks_in_scope(q):
                findings.append(
                    OptimizationFinding(
                        severity="high",
                        issue="In-scope request was rejected",
                        evidence=f"Q={q}",
                        fix_suggestion="Add keyword routing for this pattern or proactive query refresh.",
                    )
                )
            if self._expects_period(q) and "Period:" not in a:
                findings.append(
                    OptimizationFinding(
                        severity="medium",
                        issue="Missing period context",
                        evidence=f"Q={q}",
                        fix_suggestion="Attach period block for metric/report responses.",
                    )
                )
            if self._expects_as_at(q) and "As at:" not in a:
                findings.append(
                    OptimizationFinding(
                        severity="medium",
                        issue="Missing as-at timestamp",
                        evidence=f"Q={q}",
                        fix_suggestion="Attach as-at line for metric/report responses.",
                    )
                )

        summary = {
            "total_cases": len(qa_rows),
            "findings": len(findings),
            "high": sum(1 for f in findings if f.severity == "high"),
            "medium": sum(1 for f in findings if f.severity == "medium"),
            "low": sum(1 for f in findings if f.severity == "low"),
        }
        return {
            "summary": summary,
            "findings": [f.__dict__ for f in findings],
            "recommended_next_step": self._next_step(summary),
        }

    def _looks_in_scope(self, q: str) -> bool:
        ql = q.lower()
        scope_words = [
            "dispute",
            "ticket",
            "chargeback",
            "intent",
            "status",
            "priority",
            "báo cáo",
            "bao cao",
            "top",
            "trend",
            "xu hướng",
        ]
        return any(w in ql for w in scope_words)

    def _expects_period(self, q: str) -> bool:
        ql = q.lower()
        return any(w in ql for w in ["báo cáo", "bao cao", "trend", "xu hướng", "top", "rate", "chargeback"])

    def _expects_as_at(self, q: str) -> bool:
        return self._expects_period(q)

    def _next_step(self, summary: dict[str, int]) -> str:
        if summary["high"] > 0:
            return "Patch routing/coverage first, then rerun same test pack."
        if summary["medium"] > 0:
            return "Patch format consistency, then rerun same test pack."
        return "No blocker. Promote this test pack to regression baseline for other bots."
