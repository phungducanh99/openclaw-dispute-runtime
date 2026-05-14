from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class AgentEnvelope:
    status: str
    summary: str
    next_actions: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotPayload(AgentEnvelope):
    run_time: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    period_current: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    dimensions: dict[str, Any] = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)


@dataclass
class AnalysisPayload(AgentEnvelope):
    compare_mode: str = ""
    period_current: dict[str, Any] = field(default_factory=dict)
    period_previous: dict[str, Any] = field(default_factory=dict)
    metrics_current: dict[str, Any] = field(default_factory=dict)
    metrics_previous: dict[str, Any] = field(default_factory=dict)
    deltas: dict[str, Any] = field(default_factory=dict)
    top_drivers: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    narrative_blocks: dict[str, Any] = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)
    snapshot_dimensions: dict[str, Any] = field(default_factory=dict)
