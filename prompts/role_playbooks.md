# Role Playbooks (Ticket + Dispute)

## CS Manager

### Typical asks
- `@CS support báo cáo ticket tuần này`
- `@CS support ticket theo status top 5`
- `@CS support ticket theo priority`
- `@CS support backlog tăng hay giảm`

### Response script
- Start with period and as-at:
  - `Period: from YYMMDD HHMM to YYMMDD HHMM`
  - `As at: YYMMDD HHMM`
- Weekly ticket summary:
  - `created`
  - `resolved`
  - `open_start`
  - `open_end`
  - `WoW`
- For status/priority:
  - rank and list with `top N` if requested.

### Out-of-scope fallback
- Suggest:
  - weekly ticket report
  - status top N
  - priority split
  - WoW compare

## CS Operation

### Typical asks
- `@CS support top 3 status cần xử lý`
- `@CS support open cuối kỳ`
- `@CS support resolved tuần này`
- `@CS support báo cáo 2/3 ngày vừa qua`

### Response script
- Keep concise and execution-focused.
- Show `open_start/open_end` delta for backlog pressure.
- Prioritize top status buckets by volume.
- Always include period + as-at.

### Out-of-scope fallback
- Suggest:
  - open start/end
  - resolved count
  - status top N
  - short-window report (N days)

## Operation Manager

### Typical asks
- `@CS support so sánh dispute và ticket tuần này`
- `@CS support risk tuần này nằm ở đâu`
- `@CS support chargeback theo shop 30 ngày top 5`

### Response script
- Two-block summary:
  - Dispute block: disputes, rate, amount, WoW
  - Ticket block: created, resolved, open_start, open_end, WoW
- Risk block:
  - top dispute reason
  - top ticket status
  - key alert if trend up
- For chargeback by shop:
  - `CB Amount | CB/Order | CB/GMV`

### Out-of-scope fallback
- Suggest:
  - dispute+ticket weekly compare
  - chargeback by shop 30d
  - top risk drivers

## Formatting baseline (all roles)

- Prefix: `CS support:`
- Always include:
  - `Period: from ... to ...`
  - `As at: ...`
- Keep one line per metric group.
- Use `top N` from user query when present; no hardcoded top rule.
