# Exercise — Day 07

## Bài 1 — Cơ bản

Mục tiêu: dùng Claude Code khám phá `taskflow-ai` ở chế độ read-only và tạo bản đồ evidence.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.
2. Kiểm tra trạng thái repo:

```bash
git status --short
```

Lệnh này giúp biết có file nào đang thay đổi trước khi bắt đầu. Kết quả kỳ vọng là rỗng hoặc chỉ gồm file bạn hiểu rõ. Nếu có file lạ, dừng lại và đọc diff trước.

3. Mở Claude Code:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude ở mode phù hợp để đọc và lập plan. Không cấp quyền edit trong bài này.

4. Gửi prompt:

```text
Hãy khám phá repo taskflow-ai ở mức architecture, chưa sửa file.

Tìm và trả về bảng:
- Entrypoint backend.
- Entrypoint frontend.
- Test setup.
- Migration/seed setup nếu có.
- Docker/local dev setup nếu có.
- Bounded context chính.

Mỗi dòng phải có:
- Claim.
- Evidence file/path.
- Confidence high/medium/low.
- File cần đọc tiếp nếu confidence chưa high.

Không đọc secret, .env, production dump, customer log, hoặc generated output.
```

Kết quả cần có: bảng evidence rõ ràng, không chỉ mô tả chung chung. Nếu Claude không ghi path file, yêu cầu làm lại.

## Bài 2 — Thực tế

Mục tiêu: tạo `ARCHITECTURE.md` như artifact dùng lại cho team.

Yêu cầu:

1. Từ kết quả Bài 1, yêu cầu Claude đề xuất outline:

```text
Dựa trên exploration vừa rồi, đề xuất outline ARCHITECTURE.md cho taskflow-ai.

Outline phải có:
- System overview.
- Entrypoints.
- Bounded contexts.
- Dependency map.
- Hot paths.
- Testing and verification map.
- Read before editing feature.
- Unknowns / needs verification.

Chưa tạo file. Chờ tôi approve.
```

2. Sau khi duyệt outline, mở Claude Code với quyền ghi hẹp:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)"
```

Lệnh này giới hạn built-in tool family vào đọc file, tạo/sửa file và Bash, đồng thời auto-approve riêng các Bash command khớp `git status *` hoặc `git diff *`. Rủi ro: nếu prompt không khóa phạm vi, Claude vẫn có thể sửa nhầm file khác bằng `Write`/`Edit`; vì vậy prompt tiếp theo phải khóa phạm vi vào `ARCHITECTURE.md` và vẫn cần review diff.

3. Gửi prompt:

```text
Tạo ARCHITECTURE.md ở root taskflow-ai theo outline đã duyệt.

Giới hạn bắt buộc:
- Chỉ tạo hoặc sửa ARCHITECTURE.md.
- Không sửa source code, README, CLAUDE.md, package files, lockfile, migration, test, workflow.
- Mỗi section phải có evidence file/path.
- Tách rõ Fact from code, Inference, Unknown.
- Không tự commit.
- Sau khi ghi file, chạy git diff --stat -- ARCHITECTURE.md và git diff -- ARCHITECTURE.md, rồi tóm tắt.
```

4. Tự kiểm tra:

```bash
git diff --stat -- ARCHITECTURE.md
```

Kết quả kỳ vọng: chỉ `ARCHITECTURE.md` thay đổi.

5. Xem chi tiết:

```bash
git diff -- ARCHITECTURE.md
```

Kết quả kỳ vọng: tài liệu có path file cụ thể, có unknowns, không khẳng định quá mức.

## Bài 3 — Nâng cao

Mục tiêu: dùng architecture map để lập reading plan trước khi sửa feature.

Feature giả định: thêm `task comments` cho `taskflow-ai`.

Yêu cầu:

1. Gửi prompt cho Claude:

```text
Dựa trên ARCHITECTURE.md và source code hiện tại, hãy lập reading plan trước khi implement feature task comments.

Chưa sửa file.
Trả về bảng:
- Thứ tự đọc.
- File/module cần đọc.
- Vì sao cần đọc.
- Bounded context liên quan.
- Hot path bị ảnh hưởng.
- Rủi ro nếu bỏ qua.
- Claim cần verify.

Đặc biệt kiểm tra auth/current user, task ownership, database migration pattern, API contract, frontend API client, UI task detail/list, và test pattern.
```

2. Yêu cầu Claude tạo dependency map cho feature:

```text
Hãy vẽ dependency map dạng text cho feature task comments:

Frontend UI -> API client -> Backend route/controller -> Service -> Repository/database -> Test layers.

Ghi rõ dependency nào đã có evidence và dependency nào chỉ là expected design.
Không implement.
```

3. Chọn 3 claim có confidence thấp và yêu cầu Claude đọc thêm đúng file cần thiết:

```text
Chọn 3 claim confidence thấp nhất trong reading plan.
Với mỗi claim, chỉ đọc file tối thiểu để verify.
Sau đó cập nhật confidence và giải thích bằng evidence.
Không sửa file.
```

Kết quả cần có: trước khi implement, bạn biết chính xác module nào cần đọc và rủi ro nếu bỏ qua.

## Bài 4 — Review & Reflection

Mục tiêu: đánh giá chất lượng exploration và biến nó thành rule làm việc.

Trả lời các câu hỏi:

1. Trong `ARCHITECTURE.md`, claim nào có evidence mạnh nhất? Vì sao?
2. Claim nào có vẻ là inference và cần đọc thêm file?
3. Hot path nào của `taskflow-ai` rủi ro nhất khi thêm `task comments`: tạo task, cập nhật status, list board, hay auth/current user?
4. Nếu Claude đề xuất implement ngay sau exploration, bạn sẽ phản hồi bằng prompt nào?
5. Bạn sẽ thêm rule gì vào `CLAUDE.md` để buộc Claude tách Fact, Inference, Unknown khi khám phá codebase lớn?

Prompt reflection gợi ý:

```text
Review quá trình exploration Day 07.

Hãy giúp tôi soạn 8 rule ngắn cho CLAUDE.md về khám phá codebase lớn:
- Evidence required.
- Không đọc secret.
- Không implement trước reading plan.
- Giới hạn permissions.
- Cách dùng /context và /compact.
- Cách cập nhật ARCHITECTURE.md.

Chỉ draft rule, chưa sửa file.
```

## Tiêu chí hoàn thành

- Đã chạy `git status --short` trước khi exploration.
- Đã dùng `claude --permission-mode plan` cho phase đọc codebase.
- Có bảng entrypoint, bounded context, dependency map, hot path kèm evidence file/path.
- Có `ARCHITECTURE.md` hoặc draft đủ chi tiết để tạo file.
- `ARCHITECTURE.md` tách rõ Fact, Inference, Unknown.
- Đã review `git diff --stat -- ARCHITECTURE.md` và `git diff -- ARCHITECTURE.md`.
- Có reading plan cho feature `task comments`.
- Reading plan nêu rõ module cần đọc trước khi sửa, rủi ro nếu bỏ qua, và claim cần verify.
- Không sửa source code, migration, config, README, hoặc Day khác trong bài tập này.

## Gợi ý nếu bí

Nếu Claude trả lời quá chung:

```text
Output này chưa đủ. Hãy viết lại thành bảng Claim / Evidence file / Confidence / Next file to read.
Không có evidence thì chuyển sang Unknown.
```

Nếu không tìm được entrypoint:

```text
Hãy dùng read-only search để tìm package.json scripts, file bootstrap server, route registration, React mount point, và test config.
Liệt kê command hoặc file đã đọc.
Không sửa file.
```

Nếu Claude muốn đọc `.env`:

```text
Không đọc .env hoặc secret file. Hãy suy luận từ .env.example, config schema, README, hoặc code validation nếu có.
Nếu không đủ bằng chứng, ghi Unknown.
```

Nếu Claude muốn implement feature:

```text
Chưa implement. Quay lại reading plan.
Hãy chỉ ra module cần đọc, risk map, và acceptance criteria cần xác nhận trước khi sửa code.
```

Nếu `ARCHITECTURE.md` sai hoặc quá rộng:

```bash
git status --short -- ARCHITECTURE.md
git diff -- ARCHITECTURE.md
```

Nếu file đã tracked và muốn bỏ thay đổi:

```bash
git restore -- ARCHITECTURE.md
```

Nếu file mới untracked và chắc chắn muốn xóa:

```bash
git clean -f -- ARCHITECTURE.md
```

Chỉ dùng lệnh rollback sau khi đã xác nhận đúng path. Không dùng `git reset --hard` để xử lý một file tài liệu.

## Đáp án tham khảo hoặc expected result

Kết quả kỳ vọng cho Bài 1:

```text
Claim: Backend entrypoint is backend/src/main.ts
Evidence: backend/src/main.ts imports createServer from ...
Confidence: high
Next file to read: backend/src/app.ts for route registration
```

Nếu repo của bạn dùng tên khác, path khác vẫn đúng miễn là có evidence thật.

Kết quả kỳ vọng cho Bài 2:

`ARCHITECTURE.md` có outline tương tự:

```text
# Architecture — taskflow-ai

## Last verified source files
## System overview
## Entrypoints
## Bounded contexts
## Dependency map
## Hot paths
## Testing and verification map
## Read before editing feature
## Unknowns / needs verification
```

Mỗi section có file/path. Ví dụ tốt:

```text
Fact from code:
- The tasks API is registered from backend/src/tasks/tasks.routes.ts.

Inference / needs verification:
- Comments likely belong near the tasks bounded context, but no comments module exists yet.
```

Kết quả kỳ vọng cho Bài 3:

Reading plan cho `task comments` nên bao gồm ít nhất:

- Tasks route/controller hoặc tương đương.
- Tasks service/domain logic.
- Data access layer hoặc ORM model/migration pattern.
- Auth/current user middleware.
- Shared API types/validation schema nếu có.
- Frontend API client.
- Task detail/list component.
- Unit/integration/e2e test pattern.

Dependency map mẫu:

```text
TaskComments UI
  -> task API client
  -> comments route/controller
  -> comments service
  -> task ownership/auth check
  -> comments table/repository
  -> integration tests
  -> e2e task detail flow
```

Kết quả kỳ vọng cho Bài 4:

Rule mẫu có thể đưa vào `CLAUDE.md`:

```text
- Khi khám phá codebase lớn, mọi architecture claim phải có evidence file/path.
- Tách Fact from code, Inference, và Unknown trước khi lập plan sửa code.
- Không implement feature mới trước khi có reading plan theo bounded context.
- Không đọc .env, secret, production dump, customer log, generated output nếu không được yêu cầu rõ.
- Với session dài, dùng /context để kiểm tra context và chỉ /compact sau khi đã tạo summary có entrypoint, hot path, unknowns, file scope.
```
