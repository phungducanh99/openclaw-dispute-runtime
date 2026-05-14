# Security Runbook (Normal Mode Outside Sandbox)

## Scope

Runbook này áp dụng cho bot `CS support` khi chạy `normal-mode` ngoài sandbox để dùng được Lark keychain.

## Risk model

- Chạy ngoài sandbox có quyền rộng hơn với filesystem/network theo user hiện tại.
- Rủi ro chính: lộ secret, chạy nhầm nhiều process, sai quyền Lark scope, lỗi keychain bị hiểu nhầm thành lỗi data.

## Mandatory controls

1. Runtime identity
- Chạy bằng service user riêng (khuyến nghị `openclawsvc`).
- Không chạy bằng user cá nhân cho môi trường vận hành dài hạn.

2. Secret hygiene
- Không hardcode `SUPERSET_PASS`, token Lark trong code.
- Chỉ nạp secret từ environment/keychain.
- Không log raw token/password.

3. Process hygiene
- Chỉ duy nhất 1 process `normal-mode` active.
- Start qua `./start_normal_mode.sh`, stop qua `./stop_normal_mode.sh`.
- Không start tay nhiều terminal song song.

4. Preflight gate (bắt buộc)
- `./security_preflight.sh` phải pass trước khi start.
- Script này kiểm tra:
  - `SUPERSET_PASS` có tồn tại
  - `lark-cli` auth/keychain dùng được
  - Superset query test chạy được
  - cảnh báo nếu đã có process `normal-mode`

5. Least privilege
- Scope Lark chỉ cấp quyền cần dùng cho bot.
- Định kỳ review và gỡ scope không còn dùng.

6. Auditability
- Theo dõi log: `logs/normal-mode/normal_mode.log`.
- Khi có incident, lưu timestamp + symptom + root cause + action vào `lessons_learned.md`.

## Operating commands

```bash
cd "2026 Dispute/openclaw_runtime"
SUPERSET_PASS='<redacted>' ./security_preflight.sh
SUPERSET_PASS='<redacted>' ./start_normal_mode.sh
./status_normal_mode.sh
./stop_normal_mode.sh
```

## Incident triage

1. Bot không trả lời chat
- Check `./status_normal_mode.sh`.
- Check log có `keychain not initialized` không.
- Nếu có: restart ngoài sandbox/escalated, không gán nhầm lỗi Superset.

2. Bot báo `unavailable` cho câu hỏi có dữ liệu
- Chạy lại `./security_preflight.sh`.
- Nếu Superset test fail: xử lý theo class data/metric.
- Nếu Superset pass: kiểm tra intent parsing/routing.

3. Bot trả lời trùng lặp
- Khả năng có >1 process đang poll.
- Dừng toàn bộ process cũ, start lại 1 process duy nhất.

## Rotation policy

- Rotate token Lark/Superset định kỳ (ví dụ mỗi 30 ngày) hoặc ngay sau incident.
- Sau rotation: chạy lại preflight + QA câu chuẩn trước khi mở cho user.
