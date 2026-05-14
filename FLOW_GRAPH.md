# OpenClaw Agent Graph

## End-to-end graph

```mermaid
flowchart TD
    A["Trigger: 08:00 daily"] --> B["Orchestrator.scheduled_run()"]
    B --> C["SupersetMonitorAgent<br/>weekly snapshot + dimensions"]
    B --> D["SupersetMonitorAgent<br/>previous week snapshot"]
    C --> E["ComparativeAnalystAgent<br/>WoW deltas + top drivers"]
    D --> E
    E --> F["ReportPublisherAgent<br/>post to Lark group"]
    E --> G["State store<br/>latest_snapshot/latest_analysis"]

    H["Trigger: @CS support mention"] --> I["Orchestrator.mention_loop_once()"]
    I --> J["Read recent messages (Lark CLI)"]
    J --> K["GroupBotQAAgent<br/>intent detect + response format"]
    K --> L["If missing time-window data<br/>refresh Superset state"]
    L --> K
    K --> M["Reply in thread (Lark CLI)"]
    M --> N["mentions_state.json dedup"]
```

## Agent nodes

- `superset_monitor`: fetch metrics/dimensions from Superset.
- `comparative_analyst`: current vs previous weekly comparison.
- `report_publisher`: publish scheduled report to group chat.
- `group_bot_qa`: mention intent routing + structured reply.
- `orchestrator`: controls trigger flow, state, and retries/refresh.

