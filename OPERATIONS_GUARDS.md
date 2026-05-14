# Operations Guards

## Risk stance

Zero operational risk is not realistic. Target is controlled risk with fast detection + recovery.

## Top risks and controls

0. **Trả lời khi bot thực tế đang off**
- Guard: trước mọi xác nhận "đã chạy/đã fix", bắt buộc chạy health gate theo hành vi thật.
- Action: chạy `SUPERSET_PASS=... ./health_gate.sh` và chỉ chốt khi script trả `[health-gate][pass]`.

1. **Old process still running old code**
- Guard: only one polling process at a time.
- Action: before start, kill old PIDs; verify with `ps aux | rg "main.py normal-mode"`.

2. **Lark CLI/keychain transient failures**
- Guard: polling loop must not crash on one failed read.
- Action: keep loop alive, retry next cycle, monitor `logs/normal-mode/normal_mode.log`.

3. **Missing Superset data for requested time window**
- Guard: auto-refresh query on demand for `N-day` questions.
- Action: orchestrator refreshes state before final reply.

4. **Wrong intent routing (user asks X, bot answers Y)**
- Guard: specialized intents have higher priority than generic report intent.
- Action: keep keyword tests in `group_bot_qa.py`; add regression examples after each incident.

5. **Unreadable report format**
- Guard: enforce compact report template with:
  - `Period: from ... to ...`
  - `As at: YYMMDD HHMM`
- Action: reject freeform fallback for reporting intents.

6. **Bot loop running in wrong environment (reads 0 message continuously)**
- Guard: fail fast with `lark_list_failed` when Lark API is unavailable, do not report fake `no messages`.
- Action: run normal-mode in environment that can access Lark keychain; verify with real message count on first cycle.

7. **Mention trong thread không được trả lời**
- Root cause: chỉ quét message gốc, bỏ qua `thread_replies` nên bỏ sót `@CS support` trong thread.
- Guard: vòng poll phải duyệt cả `message` và `thread_replies` (mỗi reply có `message_id` riêng).
- Action: sau mọi patch luồng mention, bắt buộc chạy `main.py mention-loop --page-size 10` để xác nhận `replied > 0` khi có mention trong thread.
- Side effect cần biết: lần đầu fix có thể trả lời dồn backlog các mention thread cũ chưa được đánh dấu processed.

8. **Follow-up ngắn (tổng/total) bị fail ngữ cảnh**
- Guard: nhận diện `tổng/tong/total` như intent hợp lệ, không xem là out-of-scope.
- Action: dùng thread context để suy ra chủ đề (ví dụ: theo nguyên nhân dispute) và trả tổng tương ứng.

9. **Snapshot thiếu dữ liệu block 30 ngày**
- Guard: với câu hỏi shop 30 ngày, nếu snapshot rỗng/unavailable thì auto-query lại trước khi trả lời.
- Action: nếu query lại vẫn lỗi nguồn, trả thông báo kỹ thuật rõ: `đã query lại nhưng nguồn tạm unavailable`.

## Minimal runbook

1. Health check:
- `lark-cli --profile cs-support auth status`
- `python3 main.py qa-reply --question "@CS support gửi báo cáo 2 ngày vừa qua"`
- `python3 main.py mention-loop --page-size 5` (must not return `lark_list_failed`)
- `python3 main.py mention-loop --page-size 10` with a known thread mention sample (must process thread replies)
- `SUPERSET_PASS=... ./health_gate.sh` (must pass all checks)

2. Restart clean:
- kill old process IDs
- start one loop:
  - `python3 main.py normal-mode --page-size 20 --interval-sec 30`

3. Hot fix reply:
- fetch last message id with `+chat-messages-list`
- reply directly with `+messages-reply --message-id <id> --reply-in-thread`
