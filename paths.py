from __future__ import annotations

from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parent
CONFIG_ROOT = RUNTIME_ROOT / "config"
STATE_ROOT = RUNTIME_ROOT / "state"
LOG_ROOT = RUNTIME_ROOT / "logs"
RUN_LOG_ROOT = LOG_ROOT / "runs"
INCIDENT_LOG_ROOT = LOG_ROOT / "incidents"
ARTIFACT_ROOT = RUNTIME_ROOT / "artifacts"
SNAPSHOT_ROOT = ARTIFACT_ROOT / "snapshots"
ANALYSIS_ROOT = ARTIFACT_ROOT / "analysis"


def ensure_runtime_dirs() -> None:
    for path in [
        STATE_ROOT,
        RUN_LOG_ROOT,
        INCIDENT_LOG_ROOT,
        SNAPSHOT_ROOT,
        ANALYSIS_ROOT,
    ]:
        path.mkdir(parents=True, exist_ok=True)
