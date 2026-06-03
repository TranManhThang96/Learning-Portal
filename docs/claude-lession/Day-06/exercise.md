# Exercise — Day 06

## Bài 1 — Cơ bản

Mục tiêu: viết prompt khám phá codebase theo format 5 phần, chưa cho Claude sửa file.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.
2. Kiểm tra working tree:

```bash
git status --short
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu bỏ qua file lạ, bạn có thể nhầm patch của Claude với thay đổi sẵn có.

3. Mở Claude Code ở `plan mode`:

```bash
claude --permission-mode plan
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là Claude Code sẵn sàng nhận prompt và chưa sửa file. Rủi ro: plan vẫn có thể thiếu nếu prompt không yêu cầu đọc file cụ thể và nêu bằng chứng.

4. Viết prompt theo format:

```text
Context:
- Repo là taskflow-ai.
- Tôi cần hiểu backend API convention trước khi thêm tasks CRUD.
- Tôi chưa chắc project dùng Fastify hay NestJS.

Goal:
- Khảo sát backend và xác định nơi phù hợp để thêm tasks CRUD API.

Constraints:
- Chỉ đọc file.
- Không sửa file.
- Không chạy command ghi dữ liệu.
- Không tự giả định framework hoặc database layer nếu chưa đọc config.

Acceptance Criteria:
- Liệt kê file đã đọc.
- Xác định framework backend, route/controller pattern, service/repository pattern, validation pattern, test pattern.
- Nêu thông tin còn thiếu để implement an toàn.

Verification:
- Không có file thay đổi sau bước này.
- Nếu thiếu thông tin, hỏi lại trước khi lập plan implement.
```

Kết quả cần có:

- Claude liệt kê file đã đọc.
- Claude nêu evidence từ codebase, không chỉ suy đoán.
- Claude hỏi lại nếu thiếu schema, auth, test command hoặc module tasks chưa tồn tại.

## Bài 2 — Thực tế

Mục tiêu: viết prompt tạo API CRUD task cho `taskflow-ai` có constraints, acceptance criteria, verification rõ.

Yêu cầu:

1. Dựa trên output Bài 1, viết prompt feature CRUD. Prompt phải có đủ 5 phần.
2. Prompt phải bao gồm tối thiểu các acceptance criteria sau:

- Create task reject title rỗng sau khi trim.
- List tasks trả dữ liệu theo convention hiện có.
- Get/update/delete task không tồn tại trả 404 theo error format hiện có.
- Update không cho title toàn khoảng trắng.
- Không thêm dependency mới.
- Không tự tạo migration nếu chưa được approve.

3. Mở Claude Code bằng default mode với tool hẹp:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)" "Bash(npm run test *)" "Bash(npm run typecheck *)"
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là session Claude Code sẵn sàng. `--tools` giới hạn nhóm tool khả dụng; `--allowedTools` chỉ auto-approve các Bash pattern đã nêu, không deny mọi command khác. Rủi ro: `npm run test` có thể chạy lâu hoặc phụ thuộc database test; nếu chưa rõ script, yêu cầu Claude đọc `package.json` trước.

4. Gửi prompt feature. Ví dụ:

```text
Context:
- Dựa trên plan đã duyệt từ Bài 1.
- Repo taskflow-ai dùng convention backend hiện có; không tạo architecture mới.

Goal:
- Implement tasks CRUD API tối thiểu cho backend.

Constraints:
- Chỉ sửa file trong module tasks hoặc file đăng ký route/module bắt buộc.
- Không thêm dependency.
- Không tạo migration nếu chưa có quyết định schema rõ; nếu cần, dừng và hỏi.
- Không tự thêm auth nếu project chưa có pattern auth.
- Không chạy git add, git commit, git reset, git clean, rm, hoặc docker compose down -v.

Acceptance Criteria:
- Create validate title sau khi trim không được rỗng.
- List/get/update/delete hoạt động theo API convention hiện có.
- Not found trả 404 theo error format hiện có.
- Update reject title toàn khoảng trắng.
- Không đổi behavior module khác.

Verification:
- Trước khi sửa, nhắc lại file dự kiến chạm vào.
- Sau khi sửa, chạy hoặc đề xuất test command hẹp.
- Báo diff summary theo file.
- Nếu thiếu thông tin, hỏi lại trước thay vì tự giả định.
```

5. Sau khi Claude sửa, tự kiểm tra:

```bash
git diff --stat
```

Output kỳ vọng là số file thay đổi khớp plan. Rủi ro: nếu thấy file ngoài scope, dừng và không approve thêm edit.

6. Xem chi tiết:

```bash
git diff
```

Output kỳ vọng là API CRUD đúng criteria, không có secret, không có dependency mới, không đổi config production.

## Bài 3 — Nâng cao

Mục tiêu: viết prompt yêu cầu test trước khi implement và dùng test fail/pass để kiểm soát behavior.

Yêu cầu:

1. Reset hoặc dùng branch sạch nếu bạn đã làm Bài 2 trên cùng repo. Không dùng lệnh destructive nếu chưa hiểu diff.
2. Viết prompt test-first:

```text
Context:
- Tôi muốn thêm tasks CRUD API trong taskflow-ai.
- Trước khi implement production code, tôi muốn có test mô tả API contract.

Goal:
- Viết test cho tasks CRUD theo convention hiện có.

Constraints:
- Đọc test pattern hiện có trước.
- Chỉ sửa hoặc tạo file test.
- Không sửa production code.
- Không thêm dependency.
- Không dùng snapshot lớn nếu assertion cụ thể đủ rõ.
- Nếu chưa rõ test runner hoặc setup database test, hỏi lại.

Acceptance Criteria:
- Test create task thành công.
- Test reject title rỗng hoặc chỉ gồm khoảng trắng.
- Test list/get/update/delete theo contract dự kiến.
- Test get/update/delete id không tồn tại trả 404.
- Test data độc lập giữa test cases.

Verification:
- Chạy test file mới nếu command rõ.
- Expected result ban đầu có thể fail vì production code chưa implement.
- Nếu fail do setup, phân tích setup trước khi sửa production code.
```

3. Sau khi Claude tạo test, chạy command phù hợp ở package backend. Nếu dùng Vitest:

```bash
npm run test -- --run
```

Output kỳ vọng: test mới fail vì endpoint chưa implement, hoặc pass nếu production code đã có sẵn behavior. Rủi ro: nếu test đang dùng database thật, dừng và kiểm tra config.

Nếu dùng Jest:

```bash
npm test -- --runInBand
```

Output kỳ vọng: test chạy tuần tự và báo failure rõ. Rủi ro: command có thể chậm hơn, nhưng hữu ích khi integration test dùng database shared.

4. Viết prompt implement sau test:

```text
Context:
- Test tasks CRUD đã được viết theo convention hiện có.
- Một số test đang fail vì production code chưa implement.

Goal:
- Implement production code nhỏ nhất để test tasks CRUD pass.

Constraints:
- Không sửa test trừ khi test sai rõ ràng và phải hỏi trước.
- Chỉ sửa file production trong plan.
- Không thêm dependency.
- Không đổi API contract đã khóa trong test.

Acceptance Criteria:
- Test tasks CRUD pass.
- Typecheck pass nếu command có sẵn.
- Không đổi behavior module khác.

Verification:
- Chạy lại test tasks.
- Báo test output summary, diff summary, và rủi ro còn lại.
```

5. Nếu cần rollback một file test hoặc production đã đọc kỹ:

```bash
git restore -- path/to/file
```

Chạy ở root `taskflow-ai`, thay `path/to/file` bằng file thật. Output kỳ vọng thường trống. Rủi ro: mất thay đổi chưa commit trong file đó.

## Bài 4 — Review & Reflection

Mục tiêu: viết prompt review API và rút ra rule dùng lại cho team.

Yêu cầu:

1. Sau khi có diff tasks CRUD hoặc diff test-first, gửi prompt review read-only:

```text
Context:
- Đây là diff tasks CRUD API trong taskflow-ai.
- Tôi muốn review trước khi commit.

Goal:
- Review như senior backend reviewer.

Constraints:
- Không sửa file.
- Chỉ đọc diff và file cần thiết.
- Không chạy command destructive.
- Không nitpick style nếu formatter xử lý được.

Acceptance Criteria:
- Finding phải phân loại theo correctness, security, maintainability, performance, test gap.
- Mỗi finding có file/path, mô tả rủi ro behavior, và đề xuất fix.
- Chỉ block merge với issue có impact thực tế.

Verification:
- Kết luận: có thể merge, cần fix nhỏ, hay cần redesign.
- Nêu test command nên chạy trước khi commit.
```

2. Dựa trên review, viết 5 rule đưa vào `CLAUDE.md` cho project `taskflow-ai`. Rule phải cụ thể, ví dụ:

- Luôn dùng format 5 phần cho task backend từ mức trung bình trở lên.
- Với API mới, test-first trước khi implement nếu API contract chưa ổn định.
- Không tự thêm dependency, migration hoặc auth pattern mới nếu chưa hỏi.
- Không chạy destructive command.
- Sau mọi edit, báo diff summary và command verify.

3. Viết một ý tưởng custom slash command trong `.claude/commands/`, ví dụ `/api-review` hoặc `/api-plan`. Chỉ cần nội dung prompt, không bắt buộc tạo file.
   Nếu viết thành file thật, dùng Markdown và có thể thêm frontmatter như `description` và `allowed-tools` để command dễ hiểu và ít quyền hơn.

4. Trả lời reflection:

- Prompt nào của bạn khiến Claude hỏi lại đúng lúc?
- Prompt nào còn quá rộng?
- Acceptance criteria nào giúp review diff dễ nhất?
- Verification command nào có rủi ro môi trường?
- Nếu dùng prompt này trong repo công ty, bạn sẽ thêm guardrail security nào?

## Tiêu chí hoàn thành

- Có đủ 3 prompt: tạo API CRUD task, review API, test trước khi implement.
- Mỗi prompt dùng đủ `Context -> Goal -> Constraints -> Acceptance Criteria -> Verification`.
- Prompt có câu yêu cầu Claude hỏi lại khi thiếu thông tin.
- Đã dùng `plan mode` cho bước đọc codebase hoặc giải thích được vì sao chưa chạy.
- Đã kiểm tra `git status --short` trước khi edit.
- Đã review `git diff --stat` và `git diff` sau khi Claude sửa.
- Có command verify kèm thư mục chạy, output kỳ vọng và rủi ro.
- Có rollback strategy bằng `git restore -- path/to/file`.
- Có ít nhất 3 guardrail về security/permission/destructive command.
- Có nhận xét về performance/cost/context khi prompt quá rộng hoặc test quá lớn.

## Gợi ý nếu bí

Nếu không biết project dùng framework nào:

```text
Hãy đọc package.json và entrypoint backend để xác định framework.
Chỉ đọc file.
Không implement.
Nếu có nhiều package.json, liệt kê từng package và vai trò.
```

Nếu Claude không hỏi lại dù thiếu thông tin:

```text
Dừng lại.
Liệt kê những giả định bạn vừa dùng.
Với mỗi giả định, nêu file nào chứng minh hoặc nói rõ chưa có bằng chứng.
Sau đó hỏi tôi tối đa 5 câu cần trả lời trước khi implement.
```

Nếu Claude muốn tạo migration:

```text
Chưa tạo migration.
Hãy giải thích schema hiện tại, dữ liệu có thể bị ảnh hưởng, rollback plan, và test database nào sẽ dùng.
Chỉ sau khi tôi approve mới được đề xuất file migration.
```

Nếu diff quá rộng:

```text
Patch vượt scope.
Không sửa thêm.
Hãy đề xuất cách tách thành 2-3 PR nhỏ hơn và file nào nên rollback.
```

Nếu test command không rõ:

```text
Đọc package.json và test config liên quan.
Không sửa file.
Đề xuất command test hẹp nhất cho module tasks, kèm thư mục chạy và rủi ro môi trường.
```

## Đáp án tham khảo hoặc expected result

Expected result cho Bài 1:

- Prompt có đủ 5 phần.
- Claude đọc `package.json`, entrypoint backend, module API tương tự hoặc module tasks nếu có.
- Claude nêu rõ file đã đọc và không sửa file.
- Claude hỏi lại nếu chưa rõ schema, auth hoặc test command.

Expected result cho Bài 2:

- Prompt feature không chỉ nói "CRUD" mà có endpoint behavior, validation, 404, dependency, migration, auth và verification.
- Diff sau implement chỉ chạm file đúng plan.
- Không có `npm install`, không có dependency mới, không có migration tự phát, không có commit tự động.
- Claude báo command test nên chạy và diff summary.

Expected result cho Bài 3:

- Test được viết trước production code hoặc ít nhất prompt thể hiện test-first rõ ràng.
- Test cover create/list/get/update/delete, validation title, 404.
- Failure ban đầu được phân loại đúng: expected fail do chưa implement, setup issue, hoặc regression.
- Production implement sau đó không sửa test tùy tiện để làm pass.

Expected result cho Bài 4:

- Prompt review là read-only và phân loại finding theo impact.
- Reflection chỉ ra prompt nào quá rộng và cách thu hẹp.
- Có rule cụ thể để đưa vào `CLAUDE.md`.
- Có ý tưởng slash command có thể dùng lại, ví dụ:

```md
---
description: Review API diff hiện tại với tiêu chí senior backend
allowed-tools: Read, Bash(git diff *), Bash(git status *)
---

Context:
- Repo taskflow-ai. Đọc CLAUDE.md trước nếu có.

Goal:
- Review API diff hiện tại như senior backend reviewer.

Constraints:
- Không sửa file.
- Không chạy command destructive.
- Chỉ đọc diff và file cần thiết.

Acceptance Criteria:
- Finding phân loại correctness, security, maintainability, performance, test gap.
- Mỗi finding có file/path, impact, đề xuất fix.

Verification:
- Kết luận merge/fix/redesign và test command cần chạy.
```
