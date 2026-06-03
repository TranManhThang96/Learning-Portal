# Day 13 — Skills tái sử dụng

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Giải thích Skill trong Claude Code là gì và khác gì với prompt dài, `CLAUDE.md`, hoặc `.claude/commands/*.md`.
- Nhận biết khi nào nên tạo Skill thay vì tiếp tục copy một prompt dài qua nhiều task.
- Tạo project Skill ở `.claude/skills/<skill-name>/SKILL.md`.
- Viết `SKILL.md` có frontmatter rõ, instruction ngắn, output format đoán được, và guardrail phù hợp.
- Tạo 2 Skill thực tế cho `taskflow-ai`: `api-reviewer` và `test-writer`.
- Dùng Skill trong workflow review API, viết test, và cải thiện chất lượng output của Claude Code.
- Kiểm soát rủi ro context bloat, tool permission quá rộng, secret leakage, và Skill bị auto-invoke sai ngữ cảnh.

## 2. Bối cảnh thực tế

Khi làm `taskflow-ai`, có nhiều quy trình lặp lại:

- Review endpoint trước khi merge.
- Viết regression test cho bug vừa sửa.
- Kiểm tra auth, authorization, validation, error shape.
- Review UI theo design system và accessibility.
- Refactor nhưng vẫn giữ behavior cũ.

Nếu mỗi lần đều paste một prompt dài, workflow sẽ không ổn định. Người học dễ quên một phần checklist, team prompt mỗi người một kiểu, Claude nhận nhiều nội dung lặp lại và context bị nhiễu. Skill giải quyết vấn đề này bằng cách đóng gói instruction thành một đơn vị tái sử dụng. Claude có thể tự chọn Skill dựa trên `description`, hoặc người dùng gọi trực tiếp bằng `/skill-name`.

Ví dụ thay vì paste prompt review API 30 dòng, dùng:

```text
/api-reviewer Review PATCH /api/tasks/:id. Focus on ownership, validation, response contract, and missing tests.
```

Không nên tạo Skill khi task chỉ làm một lần, checklist chưa ổn định, hoặc instruction chỉ 2-3 dòng. Skill có giá trị nhất khi nó biến một workflow lặp lại thành chuẩn vận hành có thể dùng lại.

## 3. Kiến thức nền

Skill là một thư mục có file `SKILL.md` làm entrypoint. Vị trí quyết định phạm vi áp dụng:

```text
~/.claude/skills/<skill-name>/SKILL.md
.claude/skills/<skill-name>/SKILL.md
```

`~/.claude/skills` phù hợp với workflow cá nhân dùng trên nhiều repo. `.claude/skills` phù hợp với project Skill phụ thuộc convention của `taskflow-ai` và có thể commit cho team.

Một `SKILL.md` thường có YAML frontmatter và phần instruction:

```md
---
name: api-reviewer
description: Review taskflow-ai backend API routes, controllers, services, schemas, auth middleware, or API tests for validation, auth, response contract, errors, security, tests, rollback risk, and maintainability.
argument-hint: "[endpoint-or-files]"
allowed-tools: Read Grep Glob Bash
---

# API Reviewer

Review API-facing changes. Return findings first, ordered by severity.
```

Các field quan trọng:

| Field | Ý nghĩa |
| --- | --- |
| `name` | Tên hiển thị; nếu bỏ qua, Claude dùng tên thư mục |
| `description` | Tín hiệu chính để Claude tự quyết định có dùng Skill không; nên ghi cả khi nào dùng |
| `when_to_use` | Bổ sung điều kiện kích hoạt nếu `description` đã quá dài |
| `argument-hint` | Gợi ý tham số khi gọi trực tiếp bằng `/skill-name` |
| `disable-model-invocation` | `true` nghĩa là chỉ user gọi, Claude không tự kích hoạt |
| `allowed-tools` | Tool được pre-approve khi Skill active; không phải deny-list |
| `paths` | Giới hạn auto-invocation theo glob path, hữu ích trong monorepo hoặc repo nhiều package |

Không tự thêm field frontmatter không có trong tài liệu hiện hành chỉ để mô tả ý tưởng. Nếu cần thu hẹp điều kiện dùng, ưu tiên viết rõ trong `description`, `when_to_use`, hoặc `paths` thay vì nhét thêm instruction mơ hồ vào thân file. Nếu muốn Skill chỉ chạy khi gọi trực tiếp, dùng `disable-model-invocation: true`.

Điểm cần nhớ: khi Skill được invoke, nội dung render của `SKILL.md` đi vào conversation và có thể ở lại trong context. Vì vậy, Skill phải ngắn và tập trung. Nội dung dài như checklist security chi tiết, ví dụ output, template test plan nên đặt ở supporting files và chỉ reference khi cần.

## 4. Step-by-step thực hành

Mục tiêu thực hành: trong `taskflow-ai`, tạo 2 project Skill:

```text
.claude/skills/api-reviewer/SKILL.md
.claude/skills/test-writer/SKILL.md
```

### Bước 1: Kiểm tra repo và tạo thư mục

Chạy ở root `taskflow-ai`:

```bash
git status --short
```

Lệnh này kiểm tra working tree. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu repo đang có thay đổi của người khác, đừng để bài thực hành lẫn vào diff đó.

Tạo thư mục Skill:

```bash
mkdir -p .claude/skills/api-reviewer .claude/skills/test-writer
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force .claude/skills/api-reviewer, .claude/skills/test-writer
```

Output kỳ vọng: thư mục được tạo hoặc đã tồn tại.

### Bước 2: Tạo Skill `api-reviewer`

Tạo `.claude/skills/api-reviewer/SKILL.md`:

```md
---
name: api-reviewer
description: Review taskflow-ai API routes, controllers, services, request or response schemas, auth middleware, database-facing API logic, or API tests for request validation, auth, response contract, error handling, security, tests, rollback risk, and maintainability.
argument-hint: "[endpoint-or-files]"
allowed-tools: Read Grep Glob Bash
---

# API Reviewer

Review API changes in `taskflow-ai` with a production-readiness mindset.

Do not edit files unless the user explicitly asks for fixes.

## Process

1. Identify the changed API surface: route, method, request shape, response shape, auth requirements.
2. Check contract risk: renamed fields, removed fields, changed status codes, inconsistent error format.
3. Check security: missing auth, missing ownership checks, unsafe user input, leaked internal errors, over-broad data exposure.
4. Check maintainability: unclear boundaries, duplicated validation, hidden side effects, weak naming.
5. Check tests: success, validation failure, unauthorized, forbidden, not found, service/database failure.

## Output Format

Return findings first, ordered by severity.

- Severity: Critical | High | Medium | Low
- File:
- Issue:
- Risk:
- Suggested fix:
- Test to add:

If no issues are found, say that clearly and list remaining test gaps or residual risk.
```

Kiểm tra file:

```bash
sed -n '1,120p' .claude/skills/api-reviewer/SKILL.md
```

PowerShell:

```powershell
Get-Content .claude/skills/api-reviewer/SKILL.md -TotalCount 120
```

Output kỳ vọng có frontmatter `---`, `name: api-reviewer`, `description`, và heading `# API Reviewer`.

### Bước 3: Tạo Skill `test-writer`

Tạo `.claude/skills/test-writer/SKILL.md`:

```md
---
name: test-writer
description: Write or improve focused tests for taskflow-ai services, API routes, UI components, hooks, utilities, or bug fixes by preserving existing behavior, following local test patterns, and covering realistic edge cases.
argument-hint: "[code-path-or-behavior]"
allowed-tools: Read Grep Glob Bash Edit
---

# Test Writer

Write tests for `taskflow-ai` that protect behavior without overfitting implementation details.

## Process

1. Inspect nearby tests before writing new tests.
2. Identify the behavior under test.
3. Choose the smallest useful test level: unit, service, API, component, or e2e.
4. Cover happy path, important failure path, and boundary or permission case.
5. Run the narrowest relevant test command first.
6. Report what was covered and what remains untested.

## Rules

- Prefer behavior assertions, clear test names, stable fixtures, and minimal mocking.
- Avoid snapshot-only logic tests, over-mocking, brittle timing assumptions, and generated tests with unclear intent.
- Do not change production behavior just to make a weak test pass.

## Output Format

- Test file path:
- Test cases added or proposed:
- Command run:
- Result:
- Remaining gaps:
```

Kiểm tra:

```bash
sed -n '1,140p' .claude/skills/test-writer/SKILL.md
```

### Bước 4: Gọi Skill trực tiếp

Trong Claude Code:

```text
/api-reviewer Review POST /api/tasks for validation, auth, response contract, and missing tests. Do not edit files.
```

Output kỳ vọng:

```text
Findings
- Severity: ...
- File: ...
- Issue: ...
- Risk: ...
- Suggested fix: ...
- Test to add: ...
```

Gọi `test-writer`:

```text
/test-writer Add focused tests for task creation validation and unauthorized access. Follow existing test patterns.
```

Output kỳ vọng có test file path, test cases, command, result hoặc proposed command.

### Bước 5: Áp dụng vào `taskflow-ai`

Ví dụ review `PATCH /api/tasks/:id`:

```text
/api-reviewer Review the current PATCH /api/tasks/:id implementation in taskflow-ai.
Check ownership, validation, partial update behavior, error status codes, response shape, and tests.
Do not edit files. Return findings first.
```

Sau khi có findings:

```text
/test-writer Based on the API review findings for PATCH /api/tasks/:id, add focused tests.
Follow existing test patterns. Run the narrowest relevant test command and report the exact result.
```

Command test tham khảo:

```bash
npm run test -- tasks
npm test
npm run test:api
```

Chạy các command này ở root `taskflow-ai`. `npm run test -- tasks` nên chỉ chạy nhóm test liên quan tới task nếu test runner hỗ trợ filter; `npm test` thường chạy suite mặc định; `npm run test:api` chỉ dùng khi script này có thật trong `package.json`. Output kỳ vọng là test pass hoặc lỗi cụ thể để Claude sửa tiếp. Rủi ro: chạy full suite có thể tốn thời gian, chạm service phụ thuộc database/cache, hoặc fail do môi trường local chưa sẵn sàng.

Nếu project không có command đó, đọc `package.json` trước thay vì đoán.

### Bước 6: Rollback khi Skill gây nhiễu

Nếu Skill quá rộng hoặc sai:

```text
Do not use any Skill for the next answer. Answer directly.
```

Nếu muốn xóa Skill thử nghiệm:

```bash
rm -rf .claude/skills/api-reviewer .claude/skills/test-writer
```

PowerShell:

```powershell
Remove-Item -Recurse -Force .claude/skills/api-reviewer, .claude/skills/test-writer
```

Chỉ rollback thư mục bạn vừa tạo. Không xóa `.claude` toàn bộ vì có thể chứa settings, hooks, agents hoặc memory khác.

## 5. Prompt mẫu nên dùng

Tạo Skill mới:

```text
Create a project-level Claude Code Skill named api-reviewer for taskflow-ai.
It should live at .claude/skills/api-reviewer/SKILL.md.
Do not edit files yet. Return the full SKILL.md content.
The skill must focus on API contract, validation, auth, security, error handling, tests, rollback risk, and maintainability.
Keep the instruction concise to avoid context bloat.
```

Cải thiện Skill hiện có:

```text
Review .claude/skills/api-reviewer/SKILL.md.
Make the description more precise, reduce unnecessary text, and keep the output format actionable.
Return a patch proposal only.
```

Review API bằng Skill:

```text
/api-reviewer Review the current git diff for API-facing changes.
Prioritize breaking API contract, missing authorization, unsafe input, inconsistent errors, and missing tests.
Do not fix yet. Findings first, ordered by severity.
```

Viết test bằng Skill:

```text
/test-writer Write focused tests for task deletion.
Cover success, unauthorized, forbidden ownership, and not found.
Follow existing test style.
Run the narrowest relevant test command and report the exact result.
```

Khi Skill bị gọi sai:

```text
Use /api-reviewer only. Ignore test-writing unless the review finds missing coverage.
```

## 6. Trade-offs

| Lựa chọn | Lợi ích | Rủi ro |
| --- | --- | --- |
| Prompt trực tiếp | Nhanh, linh hoạt | Dễ thiếu checklist, khó chuẩn hóa |
| `.claude/commands/*.md` | Gọi thủ công dễ | Ít linh hoạt hơn Skills |
| Skill | Tái sử dụng tốt, có auto-invocation, supporting files | Có thể phình context hoặc bị gọi sai |
| Supporting files | Giữ `SKILL.md` gọn | Cần thêm quản lý file |
| `allowed-tools` | Giảm friction khi Skill chạy | Không thay thế permission policy |

Best solution cho `taskflow-ai`: tạo Skill cho workflow lặp lại có checklist rõ, ví dụ API review, test writing, security review. Không tạo Skill cho mọi việc nhỏ.

Rủi ro thực tế:

- `description` quá rộng làm Claude tự dùng Skill không cần thiết.
- `SKILL.md` quá dài làm tốn context.
- `allowed-tools` quá rộng làm tăng rủi ro command/edit ngoài ý muốn.
- Skill review nhưng lại tự sửa file vì instruction không cấm rõ.
- Skill cũ không còn khớp architecture mới.

## 7. Best practices

- Đặt tên Skill theo workflow: `api-reviewer`, `test-writer`, `security-reviewer`.
- Viết `description` bằng câu cụ thể, đưa use case chính lên đầu.
- Đưa điều kiện dùng cụ thể vào `description`; ví dụ nói rõ chỉ dùng cho backend API-facing changes, không dùng cho docs/UI-only changes.
- Dùng `disable-model-invocation: true` cho Skill chỉ nên chạy khi user gọi trực tiếp.
- Với Skill review, ghi rõ `Do not edit files unless explicitly asked`.
- Output format nên cố định cho review và test.
- Giữ `SKILL.md` ngắn; chuyển ví dụ dài sang supporting files.
- Không đưa secret, private endpoint, credential, hoặc production data vào Skill.
- Không pre-approve tool không cần thiết.
- Review Skill như review code: scope, permissions, maintainability, security.
- Khi commit project Skill, giải thích trong PR vì sao team cần Skill đó.

## 8. Performance / cost / context

Skill tiết kiệm token khi thay thế prompt dài lặp lại, nhưng chỉ khi Skill ngắn và đúng phạm vi. Trong session thường, Claude chỉ cần thấy metadata như `description` để biết Skill tồn tại; nội dung đầy đủ của `SKILL.md` chỉ vào context khi Skill được invoke. Sau khi invoked, nội dung đó có thể ở lại các turn sau và được mang qua compact theo ngân sách context, nên Skill dài sẽ làm workflow nặng hơn.

Cách tối ưu:

- Giữ phần chính của `SKILL.md` khoảng 80-150 dòng nếu có thể.
- Không copy nguyên docs framework vào Skill.
- Không liệt kê mọi edge case hiếm.
- Dùng supporting files cho checklist dài.
- Dùng `disable-model-invocation: true` cho workflow có side effect hoặc cần user chủ động gọi.
- Dùng `paths` khi Skill chỉ nên tự kích hoạt trong một vùng file cụ thể.
- Với test, yêu cầu chạy narrow test trước full suite.
- Với review, yêu cầu findings theo severity và bỏ advice chung chung.

Prompt tiết kiệm context:

```text
/api-reviewer Review only the current git diff. Inspect related files only if needed to validate a concrete finding.
```

Prompt tốn context:

```text
/api-reviewer Review the whole backend and tell me everything that can be improved.
```

## 9. Checklist cuối bài

- [ ] Tôi hiểu Skill là gì và nằm ở đâu.
- [ ] Tôi phân biệt được Skill với prompt dài, `CLAUDE.md`, và `.claude/commands`.
- [ ] Tôi biết gọi Skill bằng `/skill-name`.
- [ ] Tôi biết `description` ảnh hưởng tới auto-invocation.
- [ ] Tôi đã tạo `.claude/skills/api-reviewer/SKILL.md`.
- [ ] Tôi đã tạo `.claude/skills/test-writer/SKILL.md`.
- [ ] `api-reviewer` có checklist API contract, auth, validation, security, tests, rollback.
- [ ] `test-writer` inspect nearby tests trước khi viết test mới.
- [ ] Tôi hiểu `allowed-tools` không phải deny-list.
- [ ] Tôi biết Skill content có thể ở lại context sau khi invoked.
- [ ] Tôi biết rollback hoặc disable Skill khi nó gây nhiễu.

## 10. Bài tập

Bài cơ bản: tạo Skill `api-reviewer` và dùng nó review một endpoint thật trong `taskflow-ai`.

Bài thực tế: tạo Skill `test-writer`, dùng nó đề xuất hoặc thêm test cho endpoint vừa review, rồi chạy command test liên quan.

Bài nâng cao: thêm supporting file `checklists/security.md` cho `api-reviewer`, sau đó yêu cầu Skill dùng checklist này khi API chạm auth, ownership hoặc sensitive data.

Bài áp dụng cá nhân: chọn một workflow bạn hay lặp lại như UI review, refactor, migration review hoặc release notes. Viết nháp một `SKILL.md`, rồi review frontmatter, permission và context cost trước khi dùng.
