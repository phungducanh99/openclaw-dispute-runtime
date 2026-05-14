from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class TestQuestion:
    role: str
    difficulty: str
    question: str
    source: str


class TesterAgent:
    """
    Reusable tester agent.
    - Input: playbook markdown or explicit scenarios.
    - Output: ordered questions from easy -> hard, specific -> ambiguous.
    """

    def build_questions(
        self,
        *,
        bot_name: str,
        playbook_markdown: str,
        max_per_role: int = 6,
    ) -> list[TestQuestion]:
        role_examples = self._extract_typical_asks(playbook_markdown)
        results: list[TestQuestion] = []
        for role, examples in role_examples.items():
            base = examples[:max_per_role]
            results.extend(
                self._expand_difficulty(
                    bot_name=bot_name,
                    role=role,
                    examples=base,
                )
            )
        return results

    def _extract_typical_asks(self, markdown: str) -> dict[str, list[str]]:
        role_blocks = re.split(r"^##\s+", markdown, flags=re.MULTILINE)
        out: dict[str, list[str]] = {}
        for blk in role_blocks:
            blk = blk.strip()
            if not blk or "\n" not in blk:
                continue
            role_name, body = blk.split("\n", 1)
            m = re.search(r"### Typical asks(.*?)(?:\n### |\Z)", body, flags=re.DOTALL)
            if not m:
                continue
            sec = m.group(1)
            asks = re.findall(r"-\s+`([^`]+)`", sec)
            if asks:
                out[role_name.strip()] = asks
        return out

    def _expand_difficulty(self, *, bot_name: str, role: str, examples: list[str]) -> list[TestQuestion]:
        rows: list[TestQuestion] = []
        for ex in examples:
            q = ex.strip()
            # easy: canonical exact ask.
            rows.append(TestQuestion(role=role, difficulty="easy", question=q, source="playbook"))
            # medium: paraphrase with same intent.
            rows.append(
                TestQuestion(
                    role=role,
                    difficulty="medium",
                    question=self._paraphrase(q),
                    source="playbook-paraphrase",
                )
            )
            # hard: partial context / ambiguous ask.
            rows.append(
                TestQuestion(
                    role=role,
                    difficulty="hard",
                    question=self._make_ambiguous(bot_name, q),
                    source="playbook-ambiguous",
                )
            )
        return rows

    def _paraphrase(self, q: str) -> str:
        repl = q
        repl = repl.replace("báo cáo", "cho mình báo cáo")
        repl = repl.replace("tuần này", "trong tuần này")
        repl = repl.replace("top 5", "top5")
        repl = repl.replace("so sánh", "compare")
        return repl

    def _make_ambiguous(self, bot_name: str, q: str) -> str:
        core = q.lower()
        core = re.sub(r"@[^ ]+\s+support", f"@{bot_name}", core)
        # keep only keywords to stress routing quality.
        tokens = [t for t in re.split(r"[\s,]+", core) if t]
        keep = tokens[: min(5, len(tokens))]
        return " ".join(keep)
