# Day 06 — Prompt engineering cho coding task

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Viết prompt coding task theo cấu trúc `Context -> Goal -> Constraints -> Acceptance Criteria -> Verification`.
- Tách prompt cho 4 loại việc thường gặp: bug fix, refactor, feature, review.
- Ép Claude Code hỏi lại khi thiếu thông tin thay vì tự đoán architecture, API contract hoặc test strategy.
- Dùng `plan mode` để yêu cầu Claude Code đọc codebase, nêu bằng chứng, lập plan, rồi mới sửa code.
- Thiết kế prompt thực tế cho `taskflow-ai`: tạo API CRUD task, review API, và yêu cầu viết test trước khi implement.
- Kiểm soát security, maintainability, performance, cost và context khi giao task cho Claude Code.

## 2. Bối cảnh thực tế

Prompt mơ hồ là nguyên nhân phổ biến khiến AI tạo code "có vẻ đúng" nhưng không dùng được trong repo thật. Ví dụ prompt:

```text
Add CRUD API for tasks.
```

Prompt này thiếu gần như mọi thông tin quan trọng: module nào, framework nào, API contract ra sao, validation ở đâu, test command nào, file nào được sửa, có migration không, có auth không, có rollback không. Claude Code có thể tự tạo architecture mới, đổi convention hiện có, thêm dependency không cần thiết, hoặc sửa nhiều file ngoài scope.

Trong `taskflow-ai`, một task CRUD API nhỏ vẫn có nhiều quyết định kỹ thuật:

- Endpoint dùng Fastify route hay NestJS controller?
- DTO/validation dùng schema nào?
- Task có `assigneeId`, `status`, `dueDate`, `createdBy` chưa?
- Database đã có migration chưa hay chỉ đang dùng in-memory repository?
- Test là unit, integration hay e2e?
- Response error format hiện tại là gì?
- Có yêu cầu authorization không?

Claude Code giải quyết tốt việc đọc codebase, lập plan, chỉnh file và chạy test khi prompt đủ rõ. Nhưng Claude Code không nên bị giao quyền quyết định mọi thứ khi yêu cầu chưa đủ. Với task có blast radius lớn, prompt tốt phải làm Claude dừng lại và hỏi lại.

Không nên dùng Claude Code để implement ngay khi:

- Bạn chưa biết acceptance criteria.
- Bạn chưa biết file/module nào liên quan.
- Repo đang có thay đổi chưa review.
- Task liên quan tới auth, permission, billing, secret, migration, production data hoặc data deletion.
- Bạn chưa có command verify tối thiểu.

## 3. Kiến thức nền

Một prompt coding task tốt không phải là câu lệnh dài. Nó là một contract ngắn giữa developer và agent.

Format nên dùng:

```text
Context:
- Repo, module, stack, trạng thái hiện tại, file liên quan nếu biết.

Goal:
- Kết quả business/technical cần đạt, không chỉ "sửa code".

Constraints:
- Giới hạn file, command, dependency, architecture, security, permission.

Acceptance Criteria:
- Điều kiện để coi task hoàn thành. Viết như checklist có thể review.

Verification:
- Command kiểm tra, thư mục chạy, output kỳ vọng, và khi nào phải dừng.
```

Trong Claude Code, format này hiệu quả vì nó khớp với agentic loop:

```text
Observe -> Plan -> Act -> Verify
```

`Context` giúp Claude biết cần quan sát gì. `Goal` giúp Claude chọn hướng. `Constraints` chặn thay đổi ngoài phạm vi. `Acceptance Criteria` giúp review diff khách quan. `Verification` ép Claude hoặc developer kiểm tra kết quả bằng command cụ thể.

Điểm khác giữa prompt cho coding task và prompt hỏi đáp thông thường:

| Loại prompt | Mục tiêu | Rủi ro nếu viết mơ hồ |
| --- | --- | --- |
| Hỏi đáp | Nhận giải thích hoặc gợi ý | Câu trả lời sai có thể bỏ qua |
| Coding task | Tạo patch thật trong repo | Patch sai có thể phá behavior, test, security |
| Review | Tìm rủi ro trong diff | Bỏ sót bug nếu không nêu tiêu chí review |
| Refactor | Đổi cấu trúc nhưng giữ behavior | Dễ đổi contract hoặc tạo abstraction thừa |

Nguyên tắc quan trọng: yêu cầu Claude đọc file liên quan trước khi đề xuất edit. Tài liệu Claude Code hiện hành khuyến nghị dùng `plan mode` để đọc và hiểu codebase trước khi sửa; có thể vào bằng `Shift+Tab`, prefix prompt với `/plan`, hoặc mở CLI bằng `claude --permission-mode plan`. Với task lặp lại, có thể đóng gói prompt thành custom slash command trong `.claude/commands/`. Với context dài hạn, project memory nên nằm trong `CLAUDE.md` hoặc `.claude/CLAUDE.md`; lệnh `/init` có thể hỗ trợ sinh `CLAUDE.md` chứa commands, architecture và conventions. Permission mode vẫn phải được kiểm soát khi cho Claude chạy command hoặc edit file.

## 4. Step-by-step thực hành

Mục tiêu thực hành: viết prompt để Claude Code lập plan và implement API CRUD cho tasks trong `taskflow-ai`, nhưng không để Claude tự ý đổi architecture hoặc chạy command nguy hiểm.

### Bước 1: Kiểm tra trạng thái repo

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này hiển thị working tree ở dạng ngắn. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu working tree đang có thay đổi của bạn hoặc đồng đội, patch do Claude tạo ra có thể bị trộn lẫn và khó rollback.

Nếu muốn biết branch hiện tại:

```bash
git branch --show-current
```

Lệnh này in tên branch đang active. Output kỳ vọng là branch feature như `feature/tasks-crud-api`, không phải `main`. Rủi ro: làm trực tiếp trên branch chính khiến review và rollback khó hơn.

### Bước 2: Mở Claude Code ở `plan mode`

Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude Code ở chế độ ưu tiên đọc và lập plan trước khi sửa. Output kỳ vọng là Claude Code sẵn sàng nhận prompt. Rủi ro thấp hơn implement trực tiếp, nhưng plan vẫn có thể sai nếu prompt không yêu cầu Claude nêu bằng chứng từ file đã đọc.

Gửi prompt khám phá:

```text
Context:
- Repo hiện tại là taskflow-ai.
- Mục tiêu dài hạn là backend API quản lý tasks cho team kỹ thuật.
- Tôi chưa chắc module tasks hiện đã có route/service/repository hay chưa.

Goal:
- Khảo sát codebase để xác định cách project hiện tại tổ chức backend API.
- Lập plan cho CRUD tasks nhưng chưa sửa file.

Constraints:
- Chỉ đọc file cần thiết.
- Không edit file.
- Không chạy npm install, migration, git command destructive, hoặc command ghi dữ liệu.
- Không tự giả định framework nếu chưa đọc config/package.

Acceptance Criteria:
- Liệt kê file đã đọc và bằng chứng chính từ từng file.
- Xác định framework backend đang dùng.
- Xác định nơi nên đặt route/controller, service, repository, validation, test.
- Nêu rõ thông tin còn thiếu cần hỏi lại.

Verification:
- Không có file thay đổi sau bước này.
- Nếu thiếu thông tin, hỏi tôi trước thay vì tự thiết kế.
```

Kết quả kỳ vọng: Claude nêu file đã đọc, architecture hiện tại, plan ngắn, và câu hỏi còn thiếu. Nếu Claude đưa plan nhưng không nêu file đã đọc, phản hồi:

```text
Plan chưa đủ bằng chứng. Hãy đọc file liên quan và cập nhật lại plan.
Không implement.
Mỗi nhận định architecture phải gắn với file đã đọc.
```

### Bước 3: Viết prompt feature CRUD có giới hạn rõ

Sau khi Claude đã khảo sát và bạn đồng ý hướng đi, chuyển sang session implement có permission kiểm soát:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)" "Bash(npm run test *)" "Bash(npm run typecheck *)"
```

Chạy ở thư mục gốc `taskflow-ai`. Lệnh này giới hạn built-in tool family vào `Read`, `Write`, `Edit`, `Bash`, đồng thời auto-approve một số command verify hẹp. Output kỳ vọng là session Claude Code mới hoặc tiếp tục sẵn sàng. Rủi ro: `--allowedTools` chỉ bỏ bước hỏi quyền cho pattern đã nêu, không deny mọi command khác; command ngoài pattern sẽ hỏi theo `default` mode. Pattern `Bash(npm run test *)` vẫn có thể chạy script test tốn thời gian hoặc chạm database test; đọc `package.json` trước nếu repo chưa tin cậy.

Prompt implement feature:

```text
Context:
- Bạn đã khảo sát backend taskflow-ai và có plan được duyệt.
- Hãy dùng convention hiện có của project, không tạo architecture mới.
- API cần phục vụ task management nội bộ cho team kỹ thuật.

Goal:
- Implement API CRUD tasks tối thiểu: create, list, get by id, update, delete.

Constraints:
- Chỉ sửa các file trong backend module tasks hoặc file đăng ký route/module bắt buộc.
- Không thêm dependency mới.
- Không đổi format lỗi chung của project.
- Không tạo migration nếu schema/database chưa được plan rõ; nếu cần migration, dừng và hỏi.
- Không xử lý auth nếu project chưa có pattern auth; ghi rõ TODO bảo mật thay vì tự chế.
- Không chạy git add, git commit, git reset, git clean, rm, hoặc docker compose down -v.

Acceptance Criteria:
- Create validate title sau khi trim không được rỗng.
- List hỗ trợ pagination cơ bản nếu project đã có pattern; nếu chưa có, trả danh sách theo pattern hiện tại.
- Get/update/delete trả 404 theo error format hiện có khi task không tồn tại.
- Update không cho title toàn khoảng trắng.
- Delete idempotency phải theo convention hiện có; nếu chưa rõ, hỏi lại.
- Không đổi public contract ngoài endpoints tasks mới.

Verification:
- Trước khi sửa, nhắc lại file dự kiến chạm vào.
- Sau khi sửa, chạy hoặc đề xuất command test phù hợp.
- Tóm tắt diff theo file.
- Nếu test fail, dừng lại và phân tích nguyên nhân trước khi sửa tiếp.
```

Kỳ vọng: Claude chỉ sửa file liên quan, không cài package, không tự tạo migration nguy hiểm, không commit. Nếu Claude đề xuất thêm dependency, yêu cầu giải thích vì sao dependency hiện tại không đủ.

### Bước 4: Viết prompt yêu cầu test trước khi implement

Với task có rủi ro behavior, bắt Claude viết hoặc cập nhật test trước. Prompt:

```text
Context:
- Repo taskflow-ai đang chuẩn bị thêm CRUD tasks.
- Tôi muốn dùng test-first workflow để khóa API contract trước khi implement.

Goal:
- Viết test mô tả behavior mong muốn cho tasks CRUD trước.

Constraints:
- Đọc test pattern hiện có trước.
- Chỉ sửa file test hoặc tạo file test theo convention hiện có.
- Không sửa production code trong lượt này.
- Không snapshot large response nếu assertion cụ thể đủ dùng.
- Không mock quá sâu khiến test không phát hiện lỗi integration quan trọng.

Acceptance Criteria:
- Có test create task thành công.
- Có test reject title rỗng hoặc chỉ có khoảng trắng.
- Có test get/update/delete task không tồn tại trả 404 theo convention hiện có.
- Test name mô tả behavior, không mô tả implementation.

Verification:
- Chạy test command hẹp cho file test nếu có thể.
- Output kỳ vọng ban đầu có thể fail vì production code chưa implement.
- Nếu test fail do setup, phân biệt rõ setup lỗi hay behavior chưa implement.
```

Sau khi test được tạo, chạy trong package backend, ví dụ `taskflow-ai/backend` nếu `package.json` nằm ở đó:

```bash
npm run test -- --run
```

Lệnh này chạy test một lần với Vitest nếu project dùng Vitest. Output kỳ vọng ở bước test-first có thể là fail đúng behavior chưa implement. Rủi ro: nếu script test dùng database thật hoặc service ngoài, cần kiểm tra `.env.test` và Docker Compose trước.

Nếu project dùng Jest:

```bash
npm test -- --runInBand
```

Lệnh này chạy Jest tuần tự, hữu ích cho integration test dùng database test. Output kỳ vọng là danh sách test fail/pass rõ ràng. Rủi ro: chạy lâu hơn, và nếu config sai có thể dùng nhầm database dev.

### Bước 5: Review diff và rollback

Sau khi Claude edit, tự chạy trong root `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này cho biết số file và số dòng thay đổi. Output kỳ vọng khớp với plan, ví dụ file route/service/test của tasks. Rủi ro: diff stat không cho thấy logic sai, chỉ giúp phát hiện patch quá rộng.

Xem diff chi tiết:

```bash
git diff
```

Output kỳ vọng:

- Không có file ngoài module tasks nếu prompt đã giới hạn.
- Không có secret, credential, `.env` hoặc config production.
- Không có dependency mới nếu constraints cấm.
- Test hoặc command verify được cập nhật hợp lý.

Nếu Claude sửa sai một file và bạn chắc chắn muốn bỏ:

```bash
git restore -- backend/src/tasks/task.service.ts
```

Chạy ở root `taskflow-ai`, thay path bằng file thật. Lệnh này rollback file về trạng thái trong Git. Rủi ro: mất toàn bộ thay đổi chưa commit trong file đó, kể cả thay đổi bạn tự viết. Không chạy nếu chưa đọc diff.

Nếu patch quá rộng, phản hồi Claude:

```text
Patch quá rộng so với constraints.
Không sửa thêm.
Hãy phân loại các thay đổi hiện tại thành: cần giữ, cần bỏ, cần hỏi lại.
Đề xuất rollback từng file bằng command cụ thể, nhưng không tự chạy command destructive.
```

### Bước 6: Đóng gói prompt lặp lại bằng custom slash command

Khi team đã thống nhất format prompt, có thể tạo custom slash command trong project thật ở `.claude/commands/`. Ví dụ file `.claude/commands/api-plan.md` có thể chứa prompt lập plan API.

Command tạo thư mục trên macOS/Linux/Git Bash, chạy ở root `taskflow-ai`:

```bash
mkdir -p .claude/commands
```

Lệnh này tạo thư mục chứa slash command nếu chưa có. Output kỳ vọng thường không có gì. Rủi ro thấp, nhưng vẫn là thay đổi filesystem; chỉ tạo trong repo bạn muốn version control hoặc đã thống nhất với team.

Nội dung slash command tham khảo. Frontmatter giúp mô tả command và giới hạn tool ngay trong file command:

```md
---
description: Lập plan API có bằng chứng trước khi sửa code
allowed-tools: Read, Bash(git status *), Bash(git diff *)
---

Context:
- Repo này là taskflow-ai.
- Đọc CLAUDE.md trước nếu có.
- Luôn đọc file liên quan trước khi đề xuất edit.

Goal:
- Lập plan cho một API task do user mô tả.

Constraints:
- Chưa sửa file.
- Nêu file đã đọc và bằng chứng.
- Hỏi lại nếu thiếu API contract, validation, auth, database, hoặc test command.

Acceptance Criteria:
- Plan tối đa 6 bước.
- Mỗi bước có file dự kiến chạm vào.
- Chỉ rõ rủi ro security, maintainability, performance.

Verification:
- Đề xuất test command và thư mục chạy.
```

Sau này trong Claude Code, team có thể gọi slash command này thay vì copy prompt dài. Vẫn cần review nội dung command vì nó trở thành project convention cho AI.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```text
Context:
- Repo taskflow-ai.
- Tôi cần hiểu backend API convention trước khi giao task CRUD.

Goal:
- Map luồng request cho module tasks hoặc module API tương tự nhất.

Constraints:
- Chỉ đọc file.
- Không sửa file.
- Không tự giả định nếu project chưa có module tasks.

Acceptance Criteria:
- Liệt kê file đã đọc.
- Chỉ ra entrypoint, route/controller, service, repository/database layer, validation, error handling, test pattern.
- Nêu 3 rủi ro nếu implement CRUD khi chưa có thêm thông tin.

Verification:
- Không có diff sau prompt này.
- Nếu thiếu thông tin, hỏi lại bằng câu hỏi cụ thể.
```

### Prompt lập plan

```text
Context:
- Dựa trên file bạn đã đọc trong taskflow-ai.
- Tính năng cần thêm là tasks CRUD API.

Goal:
- Lập plan implement nhỏ, dễ review.

Constraints:
- Chưa implement.
- Không thêm dependency.
- Không tạo migration nếu chưa xác nhận schema.
- Plan phải tách test và production code.

Acceptance Criteria:
- Plan tối đa 6 bước.
- Mỗi bước ghi file dự kiến chạm vào và lý do.
- Nêu rollback strategy nếu patch sai.
- Nêu command verify và thư mục chạy.

Verification:
- Tôi sẽ approve hoặc yêu cầu chỉnh plan trước khi bạn sửa.
```

### Prompt implement feature

```text
Context:
- Plan tasks CRUD đã được duyệt.
- Backend dùng convention hiện có của taskflow-ai.

Goal:
- Implement phần production code nhỏ nhất để test tasks CRUD pass.

Constraints:
- Chỉ sửa file đã nêu trong plan.
- Không thêm dependency.
- Không đổi error format chung.
- Không tự commit.
- Nếu cần sửa file ngoài plan, dừng và hỏi.

Acceptance Criteria:
- CRUD behavior đúng test đã viết.
- Validation title trim rỗng bị reject.
- 404 nhất quán với convention hiện có.
- Không có logic duplicate lớn.

Verification:
- Chạy test command hẹp nếu được phép.
- Báo test pass/fail và diff summary.
```

### Prompt bug fix

```text
Context:
- Bug: update task với title toàn khoảng trắng vẫn được lưu.
- Repo: taskflow-ai.
- Tôi chưa chắc validation nằm ở route schema hay service.

Goal:
- Sửa bug bằng thay đổi nhỏ nhất.

Constraints:
- Đọc file liên quan trước.
- Không đổi API response thành công.
- Không đổi database schema.
- Không refactor module tasks trong lượt này.

Acceptance Criteria:
- `"   "` bị reject giống title rỗng.
- Title hợp lệ vẫn được trim hoặc xử lý theo convention hiện có.
- Test regression được thêm hoặc cập nhật.

Verification:
- Chạy test liên quan tới tasks.
- Nếu không tìm được test command, đọc package.json và đề xuất command.
- Nếu thiếu convention trim, hỏi lại trước khi sửa.
```

### Prompt refactor

```text
Context:
- Module tasks trong taskflow-ai đã có CRUD nhưng service đang chứa validation, mapping response và database call trong cùng một hàm dài.

Goal:
- Refactor để code dễ maintain hơn nhưng giữ nguyên behavior public API.

Constraints:
- Không đổi endpoint, status code, response shape, database schema.
- Phải có characterization test hoặc test hiện có pass trước khi refactor.
- Refactor theo từng bước nhỏ, không viết lại toàn module.
- Không tạo abstraction nếu chỉ dùng một lần.

Acceptance Criteria:
- Diff thể hiện tách trách nhiệm rõ hơn.
- Test trước và sau refactor pass.
- Không tăng số query database cho hot path list tasks.

Verification:
- Chạy test tasks trước khi sửa nếu có thể.
- Sau mỗi bước refactor, báo diff summary.
- Nếu test coverage không đủ, dừng để đề xuất test trước.
```

### Prompt review

```text
Context:
- Tôi đã có diff cho tasks CRUD API trong taskflow-ai.

Goal:
- Review như senior backend reviewer, không sửa file.

Constraints:
- Chỉ đọc diff và file cần thiết để hiểu context.
- Không edit.
- Không chạy command destructive.
- Ưu tiên finding có impact thực tế, không nitpick style nếu formatter xử lý được.

Acceptance Criteria:
- Phân loại finding theo: correctness, security, maintainability, performance, test gap.
- Mỗi finding có file/path, behavior rủi ro, và đề xuất fix.
- Nêu rõ phần nào đủ tốt không cần đổi.

Verification:
- Kết luận diff có thể merge, cần sửa trước khi merge, hay cần redesign.
```

### Prompt viết test

```text
Context:
- Tôi muốn thêm tasks CRUD API theo test-first workflow.

Goal:
- Viết test mô tả API contract trước khi implement.

Constraints:
- Đọc test convention hiện có.
- Chỉ sửa file test.
- Không sửa production code.
- Không tạo mock sâu nếu integration test hiện có phù hợp hơn.

Acceptance Criteria:
- Test cover create/list/get/update/delete.
- Test cover validation title rỗng sau trim.
- Test cover 404 cho id không tồn tại.
- Test data độc lập, không phụ thuộc thứ tự chạy.

Verification:
- Chạy test file mới.
- Nếu fail vì production chưa có endpoint, ghi rõ đó là expected fail của test-first.
```

## 6. Trade-offs

Prompt có cấu trúc dài hơn prompt tự nhiên, nhưng giảm chi phí sửa sai. Với task một dòng như rename biến local, format đầy đủ có thể quá nặng. Với API, refactor, review hoặc bug production-like, format này đáng dùng.

`plan mode` làm workflow chậm hơn ở bước đầu, nhưng giúp Claude đọc codebase trước khi sửa. Điều này đặc biệt quan trọng trong repo có convention riêng, module nhiều tầng hoặc test setup phức tạp.

Test-first prompt có thể làm Claude mất thêm thời gian, nhưng khóa API contract sớm. Trade-off là bạn phải chấp nhận test fail ban đầu và phân biệt fail do behavior chưa implement với fail do setup sai.

Custom slash command giúp team tái sử dụng prompt chuẩn. Rủi ro là prompt lỗi sẽ được lặp lại nhiều lần. Slash command nên được review như code: version control, pull request, và cập nhật khi architecture đổi.

Ràng buộc quá chặt có thể làm Claude không hoàn thành task. Ràng buộc quá lỏng làm Claude tự quyết định ngoài phạm vi. Điểm cân bằng tốt là giới hạn file/command/dependency rõ, nhưng cho phép Claude hỏi lại khi cần mở rộng scope.

## 7. Best practices

- Luôn yêu cầu Claude đọc file liên quan và nêu bằng chứng trước khi đề xuất edit.
- Mọi task từ mức trung bình trở lên nên bắt đầu bằng prompt `Context -> Goal -> Constraints -> Acceptance Criteria -> Verification`.
- Với yêu cầu thiếu dữ kiện, thêm câu: "Nếu thiếu thông tin, hỏi lại trước; không tự giả định."
- Không giao chung một prompt cho feature, refactor, test, docs và performance tuning cùng lúc.
- Với bug fix, yêu cầu reproduction hoặc failing test trước khi sửa.
- Với refactor, yêu cầu behavior lock bằng test trước và không đổi public contract.
- Với review, yêu cầu finding có impact và file/path cụ thể, tránh nhận xét chung chung.
- Không đưa secret, `.env`, token, production credential, customer data hoặc log nhạy cảm vào prompt.
- Không cho Claude tự chạy command destructive: `rm -rf`, `git reset --hard`, `git clean -fd`, `docker compose down -v`, migration drop/truncate, force push.
- Ghi rules quan trọng vào `CLAUDE.md` hoặc `.claude/CLAUDE.md` để session mới có project memory ổn định. Có thể dùng `/init` để khởi tạo rồi chỉnh lại thủ công.
- Những prompt lặp lại như API plan, API review, test-first có thể đưa vào `.claude/commands/` thành custom slash command sau khi team review.

## 8. Performance / cost / context

Prompt engineering tốt không chỉ để code đúng hơn, mà còn giảm token và context waste.

Các nguyên nhân tốn context:

- Bắt Claude đọc toàn repo khi chỉ cần module tasks.
- Gộp feature, refactor và review vào một session dài.
- Không nêu acceptance criteria, khiến Claude sửa đi sửa lại.
- Để Claude chạy test suite toàn repo khi chỉ cần test file/module.
- Không dùng `CLAUDE.md`, khiến session nào cũng phải giải thích lại architecture, commands và conventions.

Cách tối ưu:

- Bắt đầu bằng prompt khám phá hẹp: module, file nghi ngờ, command cần đọc.
- Yêu cầu Claude tóm tắt file đã đọc và quyết định kỹ thuật quan trọng, không paste toàn bộ code.
- Sau plan, chuyển sang implement prompt hẹp với danh sách file được sửa.
- Chạy test hẹp trước, test rộng sau. Ví dụ test module tasks trước rồi mới full backend suite.
- Dùng custom slash command cho prompt lặp lại để giảm thời gian nhập và giảm sai lệch giữa các developer.
- Khi context dài, yêu cầu Claude tạo summary tập trung vào decisions, files touched, commands run, remaining risks. Không giữ log dài không cần thiết.

Ví dụ verify theo tầng:

```bash
npm run test -- --run backend/src/tasks
```

Chạy trong package backend nếu script hỗ trợ path filter. Output kỳ vọng là test tasks pass. Rủi ro: path filter có thể khác giữa Vitest/Jest; nếu command fail vì syntax, đọc `package.json` và test config trước khi kết luận code sai.

```bash
npm run typecheck
```

Chạy trong package có TypeScript config. Output kỳ vọng là exit code 0, không có type error. Rủi ro: typecheck toàn project có thể lộ lỗi cũ không liên quan; cần phân biệt regression mới với nợ kỹ thuật có sẵn.

## 9. Checklist cuối bài

- [ ] Tôi viết được prompt theo format `Context -> Goal -> Constraints -> Acceptance Criteria -> Verification`.
- [ ] Tôi biết khi nào dùng prompt bug fix, refactor, feature, review, test-first.
- [ ] Tôi biết ép Claude hỏi lại khi thiếu API contract, auth rule, database schema hoặc test command.
- [ ] Tôi đã dùng `plan mode` để yêu cầu Claude đọc code trước khi sửa.
- [ ] Tôi biết giới hạn file, command, dependency và permission mode trong prompt.
- [ ] Tôi biết review `git diff --stat` và `git diff` sau khi Claude edit.
- [ ] Tôi có rollback strategy bằng `git restore -- path/to/file` và hiểu rủi ro mất thay đổi local.
- [ ] Tôi biết khi nào nên đưa prompt lặp lại vào `.claude/commands/`.
- [ ] Tôi biết rule nào nên đưa vào `CLAUDE.md` để giảm context lặp lại.
- [ ] Tôi đã cân nhắc security, maintainability, performance, cost và context trước khi cho Claude implement.

## 10. Bài tập

Bài cơ bản: viết prompt khám phá backend `taskflow-ai` theo format 5 phần. Prompt phải yêu cầu Claude chỉ đọc file, liệt kê bằng chứng, và hỏi lại nếu chưa rõ module tasks.

Bài nâng cao: viết prompt test-first cho tasks CRUD API. Prompt phải cấm sửa production code, yêu cầu đọc test convention, tạo test cho create/list/get/update/delete, validation title, và 404.

Bài áp dụng project cá nhân: chọn một bug thật trong repo cá nhân. Viết 2 prompt: prompt bug diagnosis trong `plan mode`, và prompt bug fix sau khi plan được duyệt. Mỗi prompt phải có rollback, command verify và điều kiện dừng khi thiếu thông tin.
