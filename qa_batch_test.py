from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.group_bot_qa import GroupBotQAAgent
from config_loader import load_config
from json_store import read_json, write_json


@dataclass
class TestCase:
    question: str
    expected_tags: list[str]
    forbidden_tags: list[str]
    must_include: list[str]
    required_intents: list[str] | None = None
    min_lines: int = 1


def _detect_tags(reply: str) -> set[str]:
    lower = reply.lower()
    tags: set[str] = set()
    if "yêu cầu này hiện chưa đủ điều kiện" in lower:
        tags.add("fallback_guided")
    if "mình cần làm rõ" in lower or "mình chưa rõ yêu cầu cụ thể" in lower:
        tags.add("clarify")
    if "xu hướng intent" in lower:
        tags.add("trend_intent")
    if "ticket theo intent" in lower:
        tags.add("ticket_intent")
    if "xu hướng ticket theo intent theo shop" in lower:
        tags.add("trend_intent_shop")
    if "báo cáo dispute theo nguyên nhân" in lower:
        tags.add("reason_report")
    if "ticket theo priority" in lower:
        tags.add("ticket_priority")
    if "chargeback theo shop" in lower:
        tags.add("chargeback_shop")
    if "period: from " in lower:
        tags.add("has_period")
    if "as at:" in lower:
        tags.add("has_as_at")
    if reply.startswith("CS support:"):
        tags.add("has_prefix")
    return tags


def _score_case(reply: str, test: TestCase) -> dict[str, Any]:
    tags = _detect_tags(reply)
    pass_expected = all(tag in tags for tag in test.expected_tags)
    pass_forbidden = all(tag not in tags for tag in test.forbidden_tags)
    pass_include = all(s.lower() in reply.lower() for s in test.must_include)
    line_count = len([ln for ln in reply.splitlines() if ln.strip()])
    pass_min_lines = line_count >= test.min_lines
    pass_required_intents = True
    if test.required_intents:
        q = test.question.lower()
        for intent in test.required_intents:
            if intent == "trend_intent" and any(k in q for k in ["trend", "xu huong", "xu hướng"]):
                pass_required_intents = pass_required_intents and ("trend_intent" in tags)
            elif intent == "reason_report" and any(k in q for k in ["lý do", "ly do", "nguyên nhân", "nguyen nhan"]):
                pass_required_intents = pass_required_intents and ("reason_report" in tags)
            elif intent == "chargeback_shop" and "chargeback" in q:
                pass_required_intents = pass_required_intents and ("chargeback_shop" in tags)
            elif intent == "ticket_priority" and any(k in q for k in ["priority", "ưu tiên", "uu tien"]):
                pass_required_intents = pass_required_intents and ("ticket_priority" in tags)
            elif intent == "ticket_intent" and any(k in q for k in ["ý định", "y dinh", "intent"]):
                pass_required_intents = pass_required_intents and (
                    "trend_intent" in tags or "trend_intent_shop" in tags or "ticket_intent" in tags
                )
    score = 0
    score += 25 if pass_expected else 0
    score += 20 if pass_forbidden else 0
    score += 15 if pass_include else 0
    score += 20 if pass_required_intents else 0
    score += 10 if pass_min_lines else 0
    score += 10 if "has_prefix" in tags else 0
    verdict = "pass" if (score >= 80 and pass_required_intents) else "fail"
    findings: list[str] = []
    if not pass_expected:
        findings.append(f"Missing expected tags: {test.expected_tags}")
    if not pass_forbidden:
        findings.append(f"Contains forbidden tags: {test.forbidden_tags}")
    if not pass_include:
        findings.append(f"Missing must-include tokens: {test.must_include}")
    if not pass_required_intents:
        findings.append(f"Missing required intent coverage: {test.required_intents}")
    if not pass_min_lines:
        findings.append(f"Reply too short: line_count={line_count}, min_lines={test.min_lines}")
    return {
        "score": score,
        "verdict": verdict,
        "tags": sorted(tags),
        "findings": findings,
    }


def _default_cases() -> list[TestCase]:
    return [
        TestCase(
            question="@CS support phân tích xu hướng của REFUND_RETURN_REQUEST từ 1Mar 2026",
            expected_tags=["trend_intent", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["REFUND_RETURN_REQUEST", "Period: from"],
        ),
        TestCase(
            question="@CS support top 5 lý do dispute",
            expected_tags=["reason_report", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["Báo cáo dispute theo nguyên nhân"],
        ),
        TestCase(
            question="@CS support ticket theo mức độ ưu tiên",
            expected_tags=["ticket_priority", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided", "clarify"],
            must_include=["Ticket theo priority"],
        ),
        TestCase(
            question="@CS support intent theo shop top 3",
            expected_tags=["trend_intent_shop", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided", "clarify"],
            must_include=["Xu hướng ticket theo intent theo shop"],
        ),
        TestCase(
            question="@CS support tôi muốn xem tình hình",
            expected_tags=["clarify"],
            forbidden_tags=["fallback_guided"],
            must_include=["Mình chưa rõ yêu cầu cụ thể"],
        ),
    ]


def _batch2_cases() -> list[TestCase]:
    return [
        TestCase(
            question="@CS support cho mình trend refund return request từ 15Apr 2026",
            expected_tags=["trend_intent", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["REFUND_RETURN_REQUEST", "Period: from"],
        ),
        TestCase(
            question="@CS support cho top 3 shop chargeback cao nhất 30 ngày",
            expected_tags=["chargeback_shop", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided", "clarify"],
            must_include=["Chargeback theo shop"],
        ),
        TestCase(
            question="@CS support dispute theo nguyên nhân từ thấp đến cao",
            expected_tags=["reason_report", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["thấp đến cao"],
        ),
        TestCase(
            question="@CS support ticket theo status top 5",
            expected_tags=["has_period", "has_as_at"],
            forbidden_tags=["fallback_guided", "clarify"],
            must_include=["Ticket theo status"],
        ),
        TestCase(
            question="@CS support phân tích giúp em",
            expected_tags=["clarify"],
            forbidden_tags=["fallback_guided"],
            must_include=["Mình cần làm rõ"],
        ),
    ]


def _batch3_cases() -> list[TestCase]:
    return [
        TestCase(
            question="@CS support vừa cho trend REFUND_RETURN_REQUEST từ 1Mar 2026 vừa cho top 5 lý do dispute",
            expected_tags=["trend_intent", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["REFUND_RETURN_REQUEST"],
            required_intents=["trend_intent", "reason_report"],
            min_lines=5,
        ),
        TestCase(
            question="@CS support tỷ lệ chargeback top 3 shop 30 ngay va ticket theo priority",
            expected_tags=["chargeback_shop", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["Chargeback theo shop"],
            required_intents=["chargeback_shop", "ticket_priority"],
            min_lines=5,
        ),
        TestCase(
            question="@CS support phan tich xu huong refund return request tu 1/3/2026",
            expected_tags=["trend_intent", "has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["REFUND_RETURN_REQUEST"],
            required_intents=["trend_intent"],
            min_lines=4,
        ),
        TestCase(
            question="@CS support cho em ticket theo ý định top 5",
            expected_tags=[],
            forbidden_tags=["fallback_guided"],
            must_include=[],
            required_intents=["ticket_intent"],
            min_lines=4,
        ),
        TestCase(
            question="@CS support cho báo cáo với",
            expected_tags=["has_period", "has_as_at"],
            forbidden_tags=["fallback_guided"],
            must_include=["Báo cáo dispute"],
            required_intents=None,
            min_lines=4,
        ),
    ]


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# QA Batch Test Report",
        "",
        f"- Run at: {report['run_at']}",
        f"- Batch size: {report['batch_size']}",
        f"- Pass: {report['summary']['pass_count']}",
        f"- Fail: {report['summary']['fail_count']}",
        f"- Avg score: {report['summary']['avg_score']}",
        "",
        "## Results",
    ]
    for idx, item in enumerate(report["results"], 1):
        lines.extend(
            [
                f"### Case {idx}",
                f"- Question: {item['question']}",
                f"- Verdict: {item['verdict']} (score={item['score']})",
                f"- Reply: {item['reply_first_line']}",
                f"- Tags: {', '.join(item['tags'])}",
            ]
        )
        if item["findings"]:
            lines.append(f"- Findings: {' | '.join(item['findings'])}")
        lines.append("")
    lines.extend(
        [
            "## Rebuttal",
            f"- Main weakness: {report['rebuttal']['main_weakness']}",
            f"- Optimization: {report['rebuttal']['optimization']}",
            f"- Next action: {report['rebuttal']['next_action']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    cfg = load_config("production.json")
    qa = GroupBotQAAgent(cfg)
    latest = read_json(Path("state/latest_analysis.json"))
    if not latest:
        raise SystemExit("Missing state/latest_analysis.json. Run scheduled-run first.")

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="1", choices=["1", "2", "3"])
    args = parser.parse_args()

    if args.batch == "1":
        cases = _default_cases()
    elif args.batch == "2":
        cases = _batch2_cases()
    else:
        cases = _batch3_cases()
    results: list[dict[str, Any]] = []
    for case in cases:
        payload = qa.run(case.question, latest, asker_context={"role": "cs_ops"})
        reply = payload.get("reply_text", "")
        scored = _score_case(reply, case)
        results.append(
            {
                "question": case.question,
                "reply": reply,
                "reply_first_line": reply.splitlines()[0] if reply else "",
                **scored,
            }
        )

    pass_count = sum(1 for r in results if r["verdict"] == "pass")
    fail_count = len(results) - pass_count
    avg_score = round(sum(r["score"] for r in results) / len(results), 2)
    weak = "none"
    opt = "No blocker found. Keep regression batch and monitor live mentions."
    next_action = "Wait for user approval before next batch."
    if fail_count > 0:
        weak = results[0]["findings"][0] if results[0]["findings"] else "Routing/format mismatch"
        opt = "Adjust routing keyword rules and add intent normalization aliases; rerun same 5-case batch."
        next_action = "Patch failing routes, rerun batch-1, then request approval for batch-2."

    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": args.batch,
        "batch_size": len(cases),
        "summary": {"pass_count": pass_count, "fail_count": fail_count, "avg_score": avg_score},
        "results": results,
        "rebuttal": {"main_weakness": weak, "optimization": opt, "next_action": next_action},
    }

    out_dir = Path("logs") / "qa-tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"batch_report_{stamp}.json"
    md_path = out_dir / f"batch_report_{stamp}.md"
    write_json(json_path, report)
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "summary": report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
