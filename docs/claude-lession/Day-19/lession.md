# Day 19 — Performance, token, cost, context optimization

## 1. Mục tiêu bài học

Sau khoảng 2 giờ, học viên có thể:

- Giải thích vì sao task dài trong Claude Code tốn token, chậm hơn và dễ lệch hướng.
- Chia một feature thành các task nhỏ để giảm context noise.
- Biết khi nào dùng `/usage`, `/context`, `/clear`, `/compact <instructions>`, `/btw`, `Esc + Esc` hoặc `/rewind`.
- Tạo `CONTEXT_SUMMARY.md` đủ ngắn nhưng vẫn giữ quyết định kỹ thuật quan trọng.
- Viết prompt giới hạn phạm vi đọc file, tránh Claude đọc cả repo không cần thiết.
- So sánh chất lượng output khi context rộng và context hẹp trên `taskflow-ai`.

## 2. Bối cảnh thực tế

Một prompt kiểu “đọc toàn bộ `taskflow-ai`, thêm filter cho task list, sửa API, sửa UI, thêm test, review toàn bộ” nghe tiện nhưng làm Claude Code phải:

- Đọc nhiều file không liên quan.
- Mang theo log, diff, output test và quyết định cũ sang task mới.
- Tăng token input/output và thời gian chạy.
- Dễ sửa lan sang module ngoài scope.
- Có nguy cơ đọc `.env`, logs, backup file hoặc dữ liệu nhạy cảm.

Context rộng không chỉ tốn tiền. Nó còn làm giảm khả năng review, khiến prompt khó tái sử dụng và tăng rủi ro maintainability.

## 3. Kiến thức nền

Token là đơn vị text model xử lý. Prompt, câu trả lời, file đã đọc, command output, `CLAUDE.md`, auto memory, loaded skills, system instructions và lịch sử sửa sai đều có thể đi vào context. Context càng lớn thì mỗi lượt trả lời càng tốn token, chậm hơn và dễ bị nhiễu bởi quyết định cũ.

Context window là vùng Claude có thể “nhìn thấy” trong một session. Khi gần đầy, Claude Code có thể compact tự động: dọn bớt tool output cũ và tóm tắt conversation history. Cơ chế này hữu ích nhưng không thay thế kỷ luật scope task, vì instruction nằm ở đầu hội thoại hoặc log dài có thể bị tóm tắt mất chi tiết. Với task quan trọng, hãy compact có hướng dẫn hoặc tạo summary thủ công trước.

Các lệnh nên nhớ:

- `/usage`: xem token usage, plan usage và activity stats của session. `/cost` và `/stats` là alias.
- `/context` hoặc `/context all`: xem phần nào đang chiếm context và gợi ý tối ưu.
- `/clear [name]`: bắt đầu conversation mới với context rỗng cho task không liên quan; conversation cũ vẫn có thể tìm qua `/resume`.
- `/compact <instructions>`: nén hội thoại có định hướng khi vẫn tiếp tục cùng một task.
- `/btw`: hỏi nhanh không cần đưa câu hỏi/câu trả lời vào conversation history chính.
- `Esc`: dừng Claude giữa chừng để redirect.
- `Esc + Esc` hoặc `/rewind`: mở rewind menu để restore code/conversation hoặc summarize một phần hội thoại.

`CLAUDE.md` nên ngắn, human-readable, ưu tiên dưới 200 dòng, chứa commands, style, testing, security và gotchas. Không nhồi tài liệu dài, API docs có thể tra lại hoặc workflow chỉ dùng đôi khi; các nội dung đó nên chuyển sang skill hoặc link tài liệu.

## 4. Step-by-step thực hành

Feature dùng trong bài: thêm filter `status` và `priority` cho Task List trong `taskflow-ai`.

### Bước 1: Kiểm tra trạng thái repo

Chạy ở root `taskflow-ai`.

```bash
git status --short
```

Lệnh kiểm tra working tree. Output kỳ vọng rỗng hoặc danh sách file đang sửa. Rủi ro: nếu có thay đổi sẵn, không rollback bừa vì có thể là việc của người khác.

### Bước 2: Đo usage và context hiện tại

Trong Claude Code:

```text
/usage
/context
```

`/usage` cho biết token usage và activity stats của session. Với Pro/Max, số tiền trong session không nhất thiết phản ánh hóa đơn vì usage nằm trong subscription; với API/team, dùng nó như tín hiệu vận hành và đối chiếu billing ở Console khi cần.

`/context` cho biết phần nào đang chiếm context: messages, file contents, memory, skills, tools, MCP. Nếu cần breakdown đầy đủ:

```text
/context all
```

Nếu session đang chứa task cũ không liên quan, đặt tên session cũ rồi clear:

```text
/rename task-filter-context-wide
/clear
```

Dùng `/clear` khi chuyển task. Không dùng nếu task đang dang dở và chưa có `CONTEXT_SUMMARY.md` hoặc chưa compact phần cần giữ.

### Bước 3: So sánh prompt rộng

Prompt rộng:

```text
Đọc toàn bộ project taskflow-ai và lập plan thêm filter status + priority cho task list. Không sửa file.
```

Chỉ yêu cầu Claude lập plan, chưa implement. Quan sát số file Claude muốn đọc, số bước plan, assumption và rủi ro sửa lan. Sau khi Claude trả lời, chạy lại:

```text
/usage
/context
```

Ghi lại token/context ở mức tương đối. Nếu không muốn giữ plan rộng trong task thật, dùng `/clear` trước khi chuyển sang prompt hẹp.

### Bước 4: Tìm file liên quan trước

Chạy ở root `taskflow-ai`.

```bash
rg -n "TaskList|TaskItem|TaskFilter|priority|status|createTask|updateTask" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**" --glob "!.git/**"
```

Lệnh tìm file liên quan tới task list, status, priority. Output kỳ vọng là path + dòng match. Rủi ro: output có thể dài; chỉ đưa file liên quan cho Claude, không paste toàn bộ.

### Bước 5: Prompt hẹp để lập plan

```text
Scope task: thêm filter status + priority cho Task List trong taskflow-ai.

Chỉ đọc các file liên quan tới:
- UI render danh sách task
- type/model của Task
- state/query/filter hiện có
- test trực tiếp của Task List nếu có

Không đọc toàn bộ repo. Không sửa auth, routing, billing, config, migration, hoặc unrelated styles.

Trước khi edit:
1. Liệt kê file bạn cần đọc và lý do.
2. Đưa plan tối đa 5 bước.
3. Chờ tôi approve.
```

Điểm quan trọng: bắt Claude khai báo phạm vi đọc file trước khi đọc sâu.

Sau khi có plan hẹp, so sánh với plan rộng theo bảng:

| Tiêu chí | Context rộng | Context hẹp |
| --- | --- | --- |
| Số file/path muốn đọc | ... | ... |
| Module ngoài scope xuất hiện | ... | ... |
| Test đề xuất | ... | ... |
| Token/context sau plan | ... | ... |
| Rủi ro maintainability | ... | ... |

### Bước 6: Implement narrow change

Sau khi approve plan:

```text
Implement theo plan đã duyệt.

Giới hạn:
- Chỉ sửa các file đã liệt kê.
- Nếu phát hiện cần file mới, dừng lại và giải thích vì sao.
- Giữ behavior hiện có của search/sort nếu có.
- Thêm hoặc cập nhật test nhỏ nhất chứng minh filter status + priority hoạt động.
- Không refactor ngoài phạm vi.

Sau khi sửa xong, trả về:
- File changed
- Behavior changed
- Test command nên chạy
- Rủi ro còn lại
```

### Bước 7: Kiểm tra diff

Chạy ở root `taskflow-ai`.

```bash
git diff --stat
git diff
```

`git diff --stat` xem blast radius. `git diff` xem chi tiết. Output kỳ vọng chỉ có file Task List/filter/test. Rủi ro: diff có thể chứa secret nếu workspace đang có file nhạy cảm.

### Bước 8: Chạy test phù hợp

Chạy ở root `taskflow-ai`.

```bash
npm pkg get scripts
npm test
```

`npm pkg get scripts` kiểm tra script thật trước khi chạy. `npm test` chạy test theo npm script. Output kỳ vọng là test pass hoặc failure rõ. Rủi ro: project có thể dùng `pnpm`/`yarn`, monorepo workspace hoặc cần service local như PostgreSQL/Redis; đọc `package.json` và `README.md` trước nếu chưa chắc. Nếu chỉ sửa frontend, ưu tiên focused test như `npm run test -- --run TaskList`.

### Bước 9: Tạo `CONTEXT_SUMMARY.md`

Prompt:

```text
Tạo CONTEXT_SUMMARY.md cho task hiện tại.

Yêu cầu:
- Dưới 120 dòng.
- Không chứa secret, raw log dài, token, .env.
- Giữ: goal, files read, files changed, decisions, commands run, test result, risks, next prompt.
- Viết để session mới có thể tiếp tục mà không cần đọc lại toàn bộ repo.
```

Template:

```md
# CONTEXT_SUMMARY.md

## Goal
Thêm filter status + priority cho Task List.

## Files Read
- `path/to/file`: lý do đọc

## Files Changed
- `path/to/file`: thay đổi chính

## Decisions
- Filter xử lý ở UI/client state vì ...

## Commands Run
- `git status --short`: kết quả ...
- `npm test`: kết quả ...

## Risks
- Chưa test dataset lớn.

## Next Prompt
Read this summary first. Only inspect listed files unless a failing test proves another file is needed.
```

### Bước 10: Compact có điều khiển

Trong Claude Code:

```text
/compact Preserve: goal, files read, files changed, decisions, test commands, known risks. Drop: raw logs, failed exploratory paths, unrelated discussion.
```

Dùng `/compact` khi task còn tiếp tục. Nếu chuyển sang task khác, dùng `/clear`.

### Bước 11: Rollback khi Claude làm sai

Ưu tiên:

```text
Esc + Esc
/rewind
```

Nếu cần rollback bằng git, chạy ở root `taskflow-ai`:

```bash
git status --short
git restore -- path/to/file
```

`git restore -- path/to/file` hoàn tác thay đổi chưa commit của file cụ thể. Rủi ro: mất toàn bộ thay đổi local trong file đó, nên chỉ dùng sau khi đọc diff.

## 5. Prompt mẫu nên dùng

Scope context:

```text
Trước khi đọc file, hãy đề xuất danh sách file cần đọc và lý do. Không đọc toàn bộ repo. Ưu tiên rg theo keyword, sau đó chỉ mở file match trực tiếp. Không đọc .env, logs, coverage, dist, node_modules.
```

Plan:

```text
Lập plan cho feature [X]. Tối đa 5 bước, nêu file dự kiến sửa, test command, assumption cần xác nhận. Không implement cho tới khi approve.
```

Implement narrow change:

```text
Implement đúng plan đã approve. Không sửa file ngoài danh sách. Nếu cần mở rộng scope, dừng lại hỏi. Không refactor unrelated code.
```

Review:

```text
Review only the current diff. Tập trung bug, regression, edge case, test thiếu, security/data exposure và thay đổi ngoài scope. Không rewrite code vì preference.
```

Context summary:

```text
Tạo CONTEXT_SUMMARY.md ngắn hơn 120 dòng, không chứa secret/log dài, giữ goal, files read/changed, decisions, commands, test result, risks và next prompt.
```

## 6. Trade-offs

| Lựa chọn | Lợi ích | Chi phí |
| --- | --- | --- |
| Context rộng | Có nhiều thông tin khi chưa biết repo | Tốn token, chậm, dễ đọc secret/log, dễ sửa ngoài scope |
| Context hẹp | Nhanh, rẻ, dễ review, dễ rollback | Có thể thiếu dependency ẩn nếu search ban đầu kém |
| `/compact` | Tiếp tục task dài mà không mất mạch | Summary có thể mất chi tiết nếu instruction mơ hồ |
| `/clear` | Reset sạch cho task mới | Mất history trong context nếu chưa summary hoặc chưa rename session |
| `CONTEXT_SUMMARY.md` | Bàn giao session có kiểm soát | Cần kỷ luật cập nhật |
| Subagent riêng | Giữ main context sạch | Cần tổng hợp kết quả tốt |
| Focused test | Nhanh và ít output | Có thể bỏ sót regression ngoài module |
| Full test suite | Tăng confidence trước PR | Chậm, nhiều output, cần tóm tắt lỗi trước khi đưa vào context |

## 7. Best practices

- Dùng `/clear` giữa các task không liên quan.
- Dùng `/compact <instructions>` thay vì chờ auto compact cho task dài.
- Dùng `/usage` và `/context` để đo trước/sau thay vì chỉ cảm giác “Claude đang chậm”.
- Dùng `/btw` cho câu hỏi nhanh.
- Giữ `CLAUDE.md` ngắn, cụ thể; nếu vượt khoảng 200 dòng, chuyển workflow ít dùng sang skill hoặc tài liệu link ngoài.
- Luôn yêu cầu Claude liệt kê file cần đọc trước khi đọc sâu.
- Không paste raw log dài; tóm tắt phần lỗi chính.
- Loại trừ `node_modules`, `dist`, `coverage`, `.git`, logs, `.env`.
- Dừng Claude bằng `Esc` nếu thấy nó đi sai hướng.
- Review `git diff --stat` trước khi cho Claude chạy tiếp.
- Với investigation đọc nhiều file, cân nhắc subagent để giữ main context sạch.
- Không đưa production data, token, API key, connection string hoặc log chứa PII vào prompt hay `CONTEXT_SUMMARY.md`.

## 8. Performance / cost / context

Một prompt tốt phải giới hạn vùng làm việc. Tối ưu bằng:

- Input ít hơn: chỉ đưa file/path liên quan.
- Output ngắn hơn: yêu cầu format cụ thể.
- Ít vòng sửa hơn: plan trước, implement sau.
- Ít đọc file hơn: dùng `rg` trước, mở file sau.
- Ít context cũ hơn: `/clear` hoặc `/compact` đúng lúc.
- Ít rủi ro hơn: tránh secret/log/unrelated files.
- Ít background cost hơn: tắt MCP server không dùng, tránh nhiều subagent chạy song song khi không cần.

Metric nên ghi trong bài:

| Metric | Cách lấy | Dùng để quyết định |
| --- | --- | --- |
| Token/session usage | `/usage` | Có cần chia task, đổi model/effort hoặc dừng exploration không |
| Context breakdown | `/context` hoặc `/context all` | Phần nào đang phình: messages, file contents, memory, skills, tools |
| Blast radius | `git diff --stat` | Có sửa đúng phạm vi không |
| Test signal | Focused test + summary lỗi | Có đủ confidence để tiếp tục không |

Dấu hiệu cần compact hoặc clear:

- Claude nhắc lại quyết định cũ không còn đúng.
- Claude sửa lỗi đã sửa ở vòng trước.
- `/context` cho thấy messages/tool output quá lớn.
- Bạn đã đổi sang feature khác.
- Bạn phải sửa Claude hơn 2 lần cùng một vấn đề.
- Auto mode hoặc compaction báo context quá lớn.

## 9. Checklist cuối bài

- [ ] Tôi giải thích được vì sao task dài tốn token.
- [ ] Tôi biết phân biệt `/clear` và `/compact`.
- [ ] Tôi đã dùng `/usage` và `/context` để ghi metric trước/sau.
- [ ] Tôi đã viết prompt rộng và prompt hẹp cho cùng một feature.
- [ ] Tôi đã dùng `rg` để giới hạn file liên quan.
- [ ] Tôi đã tạo template `CONTEXT_SUMMARY.md`.
- [ ] Tôi biết rollback bằng `Esc + Esc`, `/rewind` hoặc `git restore -- path`.
- [ ] Tôi không đưa secret/log dài vào context.
- [ ] Tôi biết giữ `CLAUDE.md` ngắn và có cấu trúc.

## 10. Bài tập

- Bài cơ bản: rewrite prompt rộng thành prompt hẹp.
- Bài thực tế: so sánh plan từ context rộng và context hẹp.
- Bài nâng cao: tạo `CONTEXT_SUMMARY.md`.
- Bài áp dụng cá nhân: audit `CLAUDE.md` hiện tại và rút gọn nó còn các rule thực sự cần.
