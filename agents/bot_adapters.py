from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from orchestrator import Orchestrator


@dataclass
class BotReply:
    text: str
    raw: dict


class BotAdapter(Protocol):
    def ask(self, question: str) -> BotReply:
        ...


class OpenClawQABotAdapter:
    """
    Default adapter for this runtime.
    Any new project can implement the same ask() contract and reuse eval pipeline.
    """

    def __init__(self, orchestrator: Orchestrator | None = None) -> None:
        self.orchestrator = orchestrator or Orchestrator()

    def ask(self, question: str) -> BotReply:
        payload = self.orchestrator.qa_run(question)
        return BotReply(text=str(payload.get("reply_text", "")), raw=payload)
