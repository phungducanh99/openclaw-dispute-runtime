from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from agents.bot_adapters import OpenClawQABotAdapter
from agents.optimizer_agent import OptimizerAgent
from agents.tester_agent import TesterAgent


def _render_report(payload: dict) -> str:
    lines = [
        "# Bot Eval Report",
        "",
        f"- Bot: {payload['bot_name']}",
        f"- Run at: {payload['run_at']}",
        f"- Cases: {len(payload['qa_rows'])}",
        "",
        "## Tester Output",
    ]
    for idx, row in enumerate(payload["qa_rows"], 1):
        lines.extend(
            [
                f"### Case {idx}",
                f"- Role: {row['role']}",
                f"- Difficulty: {row['difficulty']}",
                f"- Question: {row['question']}",
                f"- Answer: {row['answer']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Optimizer Output",
            f"- Summary: {json.dumps(payload['optimizer']['summary'], ensure_ascii=False)}",
            f"- Recommended next step: {payload['optimizer']['recommended_next_step']}",
            "",
        ]
    )
    if payload["optimizer"]["findings"]:
        lines.append("### Findings")
        for f in payload["optimizer"]["findings"]:
            lines.append(
                f"- [{f['severity']}] {f['issue']} | evidence={f['evidence']} | fix={f['fix_suggestion']}"
            )
    else:
        lines.append("- No findings.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-name", default="CS support")
    parser.add_argument("--expected-prefix", default="CS support:")
    parser.add_argument("--playbook", default="prompts/role_playbooks.md")
    parser.add_argument("--max-per-role", type=int, default=3)
    args = parser.parse_args()

    playbook = Path(args.playbook).read_text(encoding="utf-8")
    tester = TesterAgent()
    optimizer = OptimizerAgent()
    adapter = OpenClawQABotAdapter()

    questions = tester.build_questions(
        bot_name=args.bot_name,
        playbook_markdown=playbook,
        max_per_role=args.max_per_role,
    )
    qa_rows = []
    for q in questions:
        reply = adapter.ask(q.question)
        answer = reply.text
        qa_rows.append(
            {
                "role": q.role,
                "difficulty": q.difficulty,
                "question": q.question,
                "answer": answer,
                "source": q.source,
                "raw": reply.raw,
            }
        )

    optimizer_out = optimizer.review(qa_rows, expected_prefix=args.expected_prefix)
    payload = {
        "bot_name": args.bot_name,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "qa_rows": qa_rows,
        "optimizer": optimizer_out,
    }

    out_dir = Path("logs") / "qa-tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"bot_eval_{stamp}.json"
    md_path = out_dir / f"bot_eval_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_report(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "cases": len(qa_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
