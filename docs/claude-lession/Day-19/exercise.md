# Exercise — Day 19

## Bài 1 — Cơ bản

Mục tiêu: viết lại prompt rộng thành prompt hẹp.

Prompt ban đầu:

```text
Đọc toàn bộ taskflow-ai, thêm filter status + priority cho task list, sửa mọi thứ cần thiết và test toàn bộ.
```

Yêu cầu prompt mới:

1. Bắt Claude chỉ đọc file liên quan.
2. Bắt Claude liệt kê file cần đọc và lý do trước khi edit.
3. Bắt Claude chờ approve plan.
4. Loại trừ `.env`, logs, `node_modules`, `dist`, `coverage`.
5. Có acceptance criteria và test command dự kiến.

Chạy ở root `taskflow-ai`:

```bash
rg -n "TaskList|TaskFilter|status|priority" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**" --glob "!.git/**"
```

Lệnh tìm file ứng viên. Output kỳ vọng: vài file liên quan Task List/filter. Rủi ro: output dài; refine keyword và chỉ gửi path liên quan, không paste toàn bộ vào Claude.

## Bài 2 — Thực tế

Mục tiêu: so sánh output khi context rộng và context hẹp.

Thực hiện:

1. Mở Claude Code tại repo `taskflow-ai`.
2. Chạy baseline trong Claude Code: `/usage` và `/context`.
3. Chạy prompt rộng nhưng chỉ yêu cầu lập plan, không sửa file.
4. Ghi lại `/usage` và `/context` sau prompt rộng.
5. Chạy `/rename task-filter-wide-plan`, sau đó `/clear`.
6. Chạy prompt hẹp từ Bài 1.
7. Ghi lại `/usage` và `/context` sau prompt hẹp.
8. So sánh hai plan theo số file muốn đọc, số bước, assumption, rủi ro sửa lan và metric context/token tương đối.

Prompt rộng:

```text
Đọc toàn bộ project taskflow-ai và lập plan thêm filter status + priority cho task list. Không sửa file.
```

Prompt hẹp:

```text
Scope: thêm filter status + priority cho Task List.

Không đọc toàn bộ repo. Chỉ đọc file liên quan trực tiếp tới UI task list, model/type Task, state/filter hiện có và test trực tiếp nếu có.

Trước khi đọc file:
- Liệt kê file/path pattern cần kiểm tra.
- Nêu lý do từng file.
- Lập plan tối đa 5 bước.
- Không sửa file cho tới khi tôi approve.
```

Mẫu bảng so sánh:

| Tiêu chí | Prompt rộng | Prompt hẹp |
| --- | --- | --- |
| File/path Claude muốn đọc | ... | ... |
| Module ngoài scope | ... | ... |
| Số bước plan | ... | ... |
| Test command đề xuất | ... | ... |
| Context/token sau plan | ... | ... |
| Rủi ro security/maintainability | ... | ... |

Kiểm tra trước và sau:

```bash
git status --short
```

Lệnh đảm bảo bài so sánh plan không tạo thay đổi. Output kỳ vọng rỗng hoặc không có thay đổi mới. Rủi ro: nếu có file đổi, Claude đã vượt scope.

## Bài 3 — Nâng cao

Mục tiêu: tạo `CONTEXT_SUMMARY.md`.

Yêu cầu file:

```md
# CONTEXT_SUMMARY.md

## Goal
...

## Current State
...

## Files Read
...

## Files Changed
...

## Decisions
...

## Commands Run
...

## Test Result
...

## Risks
...

## Next Prompt
...
```

Ràng buộc:

- Dưới 120 dòng.
- Không chứa secret, raw log dài, `.env`, token, password.
- Có đủ files read/changed, decisions, commands, test result, risks.
- Có `Next Prompt` để session mới tiếp tục với context hẹp.
- Nêu rõ summary này dành cho task filter, không phải tài liệu kiến trúc toàn repo.

Trước khi tạo summary, kiểm tra secret keyword ở root `taskflow-ai`:

```bash
rg -n "SECRET|TOKEN|API_KEY|PASSWORD|PRIVATE_KEY|DATABASE_URL" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**" --glob "!.git/**"
```

Output kỳ vọng: không có secret thật trong file sẽ đưa vào context. Rủi ro: command có thể in ra secret nếu repo đã chứa secret; không paste nguyên output vào Claude, chỉ ghi “đã kiểm tra, không đưa secret vào summary” hoặc redact giá trị nhạy cảm.

Kiểm tra:

```bash
git diff -- CONTEXT_SUMMARY.md
```

Lệnh xem summary trước khi dùng làm context. Rủi ro: nếu lỡ ghi thông tin nhạy cảm, diff sẽ hiển thị; cần redact trước.

## Bài 4 — Review & Reflection

Trả lời ngắn:

1. Prompt rộng khiến Claude muốn đọc thêm file nào?
2. Prompt hẹp loại bỏ được nhánh khám phá nào?
3. Khi nào chọn `/clear` thay vì `/compact`?
4. `/usage` và `/context` cho thấy khác biệt gì giữa hai cách prompt?
5. Summary có đủ để mở session mới không?
6. Có thông tin nào không nên đưa vào context vì security?
7. Nếu Claude sửa sai, rollback bằng `/rewind` hay `git restore -- path`? Vì sao?
8. Với investigation đọc nhiều file, bạn có dùng subagent không? Vì sao?

Review diff:

```bash
git diff --stat
```

Lệnh xác nhận phạm vi thay đổi cuối cùng. Output kỳ vọng chỉ có `CONTEXT_SUMMARY.md` hoặc file filter nếu đã implement.

## Tiêu chí hoàn thành

- [ ] Có prompt hẹp thay thế prompt rộng.
- [ ] Có so sánh output context rộng vs hẹp.
- [ ] Có ghi `/usage` và `/context` trước/sau để đánh giá token/context tương đối.
- [ ] Có `CONTEXT_SUMMARY.md` đúng cấu trúc.
- [ ] Biết dùng `/clear`, `/compact <instructions>`, `/btw`, `/rewind`.
- [ ] Không đưa secret/log dài vào summary.
- [ ] Diff cuối không có thay đổi ngoài scope.
- [ ] Có command test hoặc review phù hợp.

## Gợi ý nếu bí

Prompt scope tối thiểu:

```text
Bạn chỉ được đọc file liên quan trực tiếp tới Task List và filter. Nếu cần mở file ngoài danh sách, hãy dừng và hỏi trước. Không implement trước khi plan được approve.
```

Instruction compact tốt:

```text
/compact Preserve goal, touched files, decisions, test commands, current failures, next step. Drop raw logs, repeated failed attempts, unrelated discussion.
```

Next prompt cho session mới:

```text
Read CONTEXT_SUMMARY.md first. Continue only from the files listed there. Do not scan the whole repo. If summary is insufficient, ask one clarifying question before reading more files.
```

## Đáp án tham khảo hoặc expected result

Prompt hẹp đạt yêu cầu:

```text
Scope: thêm filter status + priority cho Task List trong taskflow-ai.

Trước khi edit:
1. Dùng search để tìm file liên quan tới Task List, Task type/model, filter state và test trực tiếp.
2. Liệt kê file cần đọc và lý do.
3. Lập plan tối đa 5 bước.
4. Chờ tôi approve.

Giới hạn:
- Không đọc toàn bộ repo.
- Không đọc .env, logs, node_modules, dist, coverage.
- Không sửa auth, routing, config, billing, migration hoặc unrelated styles.
- Nếu cần mở rộng scope, dừng và hỏi.

Acceptance criteria:
- UI có filter status và priority.
- Filter kết hợp đúng với search/sort hiện có nếu có.
- Có test nhỏ nhất cho filter.
- Test command dự kiến: npm test hoặc focused test sau khi đọc package.json.
```

Expected result cho bảng so sánh:

```md
| Tiêu chí | Prompt rộng | Prompt hẹp |
| --- | --- | --- |
| File/path Claude muốn đọc | Nhiều folder, có thể gồm backend/config | Component Task List, Task type, filter state, test liên quan |
| Module ngoài scope | Có nguy cơ auth/routing/API rộng | Bị loại trừ rõ |
| Số bước plan | Dài, có discovery chung | Tối đa 5 bước |
| Test command đề xuất | Full test suite | Focused test trước, full test trước PR nếu cần |
| Context/token sau plan | Cao hơn | Thấp hơn |
| Rủi ro | Tốn token, sửa lan | Có thể thiếu dependency ẩn nếu search thiếu |
```
