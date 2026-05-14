# Analytics Phase 1 Spec (Dispute + Ticket)

## 1) Mục tiêu

Nâng bot từ mức "báo cáo số liệu" lên "phân tích có hành động", với tiêu chí:
- Trả lời đúng intent nghiệp vụ.
- Có ngữ cảnh thời gian rõ (`Period`, `As at`).
- Có xu hướng so sánh chu kỳ trước.
- Có gợi ý hành động theo vai trò người hỏi.

Phase 1 tập trung tính ổn định vận hành, không mở rộng quá nhiều insight cùng lúc.

## 2) Phạm vi triển khai Phase 1

### 2.1 Dispute (3 insight)
1. Driver decomposition
- Mục tiêu: xác định nguyên nhân dispute đóng góp tăng/giảm nhiều nhất.

2. Shop risk ranking
- Mục tiêu: xếp hạng shop theo mức rủi ro dispute, có phân tách theo payment gateway.

3. Status pressure
- Mục tiêu: phát hiện status đang phình (điểm nghẽn xử lý).

### 2.2 Ticket (3 insight)
1. Flow health
- Mục tiêu: theo dõi created/resolved/open_start/open_end và backlog delta.

2. Intent pressure
- Mục tiêu: intent nào tăng mạnh và kéo backlog.

3. Ops focus list
- Mục tiêu: danh sách ưu tiên xử lý theo cụm `intent x status x shop`.

## 3) Time semantics (chuẩn hóa)

Các cụm thời gian cần hỗ trợ:
- `hôm qua` / `yesterday`
- `N ngày vừa qua` / `N days`
- `tuần này` / `this week`
- `tháng này` / `this month`
- `từ <ngày>` / `from <date>`

Quy tắc:
- `this month` = từ ngày 01 tháng hiện tại đến hiện tại.
- `this week` = từ thứ Hai tuần hiện tại đến hiện tại.
- `N days` = từ `today-(N-1)` đến hiện tại.
- Khi parse được time intent, orchestrator phải refresh snapshot theo kỳ đó trước khi trả lời.

## 4) Trend layer bắt buộc

Mỗi insight phải có lớp xu hướng:
- DoD (hôm qua vs hôm kia) khi phù hợp.
- WoW (kỳ hiện tại vs kỳ trước cùng độ dài).
- MoM (tháng này vs tháng trước) khi phù hợp.
- Rolling 4 kỳ gần nhất (nếu có đủ dữ liệu).

Output chuẩn:
- `current`
- `previous`
- `delta_abs`
- `delta_pct`
- `trend_label`: `tăng`, `giảm`, `đi ngang`
- `signal_strength`: `mạnh`, `vừa`, `yếu`

Ngưỡng mặc định:
- `|delta_pct| < 3%` -> `đi ngang`
- `3% <= |delta_pct| <= 10%` -> `tăng/giảm nhẹ`
- `|delta_pct| > 10%` -> `tăng/giảm mạnh`

## 5) Metric contract (khóa định nghĩa)

### 5.1 Dispute
- `dispute_count`: số dispute distinct trong kỳ.
- `orders_count`: số order distinct trong kỳ (GP: paid_order = order).
- `dispute_rate_pct = dispute_count / orders_count * 100`.
- `amount_at_risk`: tổng dispute_amount.
- `gateway_dispute_rate_pct = dispute_count_by_gateway / orders_count_by_gateway * 100`.

### 5.2 Ticket
- `ticket_created`: số ticket tạo mới trong kỳ.
- `ticket_resolved`: số ticket resolved trong kỳ.
- `open_start`: tồn đầu kỳ.
- `open_end`: tồn cuối kỳ.
- `backlog_delta = open_end - open_start`.

### 5.3 Nguyên tắc
- Không đổi công thức theo ngữ cảnh câu hỏi.
- Nếu thiếu metric source thì trả rõ metric nào thiếu và query lại nếu có thể.

## 6) Data contract (field phụ thuộc tối thiểu)

### 6.1 Dispute
- `reason_normalize`
- `status_normalize`
- `shop_code`
- `gateway` (hoặc field normalize tương đương payment gateway)
- `disputes_distinct`
- `dispute_amount`
- `orders_distinct` (hoặc equivalent)

### 6.2 Ticket
- `status_normalize`
- `priority`
- `cf_ai_intent`
- `cf_assigned_group_norm`
- `tickets_distinct`
- trường phục vụ open_start/open_end trong ticket summary

Nếu thiếu field:
1. Query lại snapshot theo kỳ người dùng hỏi.
2. Nếu vẫn thiếu do dataset không có field, fallback rõ ràng + gợi ý câu hỏi thay thế.

## 7) Intent commands (Phase 1)

### 7.1 Dispute
1. `phân tích dispute theo nguyên nhân`
2. `phân tích risk dispute theo shop`
3. `phân tích dispute theo payment gateway`
4. `phân tích risk dispute theo shop và gateway`
5. `phân tích pressure dispute theo status`
6. `xu hướng dispute tuần này so với tuần trước`
7. `xu hướng dispute tháng này so với tháng trước`

### 7.2 Ticket
1. `phân tích flow ticket`
2. `phân tích intent ticket`
3. `ops focus ticket`
4. `xu hướng ticket tuần này so với tuần trước`
5. `xu hướng ticket tháng này so với tháng trước`

### 7.3 List/Find (đã triển khai)
- `list/liệt kê dispute|ticket`
- `find/tìm dispute|ticket <keyword>`

## 8) Output template

Mọi câu trả lời phân tích phải theo khung:
1. Header insight
2. `Period: from YYMMDD to YYMMDD`
3. KPI block (current)
4. Trend block (previous + delta + label)
5. Top drivers/top entities (shop, gateway, hoặc shop x gateway tùy intent)
6. Action hint (1-3 dòng)
7. `As at: YYMMDD HHMM`

Không dùng nhãn cứng `Weekly` khi kỳ do user chỉ định.

## 9) Role-aware response

### 9.1 Finance
- Ưu tiên: `rate`, `amount`, `delta`, top shop impact.

### 9.2 CS Manager
- Ưu tiên: driver change, trend, ưu tiên xử lý theo tuần/tháng.

### 9.3 CS Ops
- Ưu tiên: queue pressure, status nghẽn, list hành động cụ thể.

## 10) Fallback policy

Quy tắc bắt buộc:
1. Nếu câu hỏi có time window mà snapshot chưa có: query lại ngay.
2. Không trả `em không biết` cho case query được.
3. Chỉ dùng fallback khi thiếu field/dataset thật sự.
4. Fallback phải nêu rõ thiếu gì + gợi ý câu hỏi phù hợp vai trò người hỏi.

## 11) Run-time reliability gates

Trước khi xác nhận "bot chạy bình thường", bắt buộc:
1. Check process thật (`ps`).
2. Chạy `mention-loop` không có `reply_errors`.
3. Verify có reply thực trên Lark thread mục tiêu.

Không dùng `status pid file` đơn lẻ làm bằng chứng pass.

## 12) Test plan (phải pass trước go-live)

### 12.1 Intent happy path
- Mỗi lệnh ở mục 7: ít nhất 1 test pass.

### 12.2 Time parser
- `hôm qua`, `2 ngày`, `7 ngày`, `tháng này`, `this month`, `từ 1Mar 2026`.

### 12.3 Robustness
- typo phổ biến (`itent`, thiếu dấu tiếng Việt).
- follow-up thread ngắn (`tổng`, `chi tiết theo intent`).

### 12.4 Runtime
- mention-loop pass không lỗi send.
- test case có reply thực vào đúng thread.

## 13) Tiêu chí nghiệm thu

Pass khi đồng thời thỏa:
1. Đúng intent + đúng kỳ thời gian.
2. Có trend block chuẩn hóa.
3. Có action hint theo role.
4. Không fallback mơ hồ.
5. Runtime pass theo behavior thật trên Lark.
