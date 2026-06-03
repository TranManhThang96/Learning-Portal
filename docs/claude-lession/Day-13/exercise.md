# Exercise — Day 13

## Bài 1 — Cơ bản

Mục tiêu: tạo project Skill `api-reviewer`.

Chạy ở root `taskflow-ai`:

```bash
mkdir -p .claude/skills/api-reviewer
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force .claude/skills/api-reviewer
```

Chạy ở root `taskflow-ai`. Lệnh tạo thư mục Skill nếu chưa có; output kỳ vọng là thư mục `.claude/skills/api-reviewer` tồn tại sau khi chạy. Rủi ro thấp, nhưng nếu chạy sai repo sẽ tạo Skill ở nhầm project.

Tạo `.claude/skills/api-reviewer/SKILL.md` với các yêu cầu:

- Có YAML frontmatter.
- Có `name: api-reviewer`.
- Có `description` rõ về API review trong `taskflow-ai`.
- Có `argument-hint`.
- Có `description` nêu rõ khi nào dùng Skill và khi nào không dùng.
- Có `allowed-tools: Read Grep Glob Bash`.
- Có output format findings theo severity.
- Có guardrail `Do not edit files unless the user explicitly asks for fixes.`

Prompt kiểm thử:

```text
/api-reviewer Review POST /api/tasks for validation, auth, response contract, and missing tests.
Do not edit files. Return findings only.
```

Output kỳ vọng:

```text
Findings
- Severity:
- File:
- Issue:
- Risk:
- Suggested fix:
- Test to add:
```

Rollback:

```bash
rm -rf .claude/skills/api-reviewer
```

PowerShell:

```powershell
Remove-Item -Recurse -Force .claude/skills/api-reviewer
```

Chạy rollback ở root `taskflow-ai` và chỉ xóa thư mục Skill vừa tạo. Output kỳ vọng là thư mục `api-reviewer` biến mất. Rủi ro cao hơn lệnh tạo vì đây là lệnh xóa đệ quy; kiểm tra kỹ path trước khi chạy, không xóa cả `.claude`.

## Bài 2 — Thực tế

Mục tiêu: tạo Skill `test-writer` và dùng cho một behavior thật.

Tạo thư mục:

```bash
mkdir -p .claude/skills/test-writer
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force .claude/skills/test-writer
```

Chạy ở root `taskflow-ai`. Lệnh tạo thư mục cho Skill `test-writer`; output kỳ vọng là `.claude/skills/test-writer` tồn tại. Rủi ro thấp, tương tự Bài 1: sai thư mục thì tạo file cấu hình ở nhầm repo.

Tạo `.claude/skills/test-writer/SKILL.md` với yêu cầu:

- Có `name: test-writer`.
- Có `description` nói rõ Skill viết test theo behavior hiện có.
- Có `description` nêu rõ dùng khi thêm hoặc cải thiện test cho `taskflow-ai`.
- Có `allowed-tools: Read Grep Glob Bash Edit`.
- Bắt buộc inspect nearby tests trước khi viết test mới.
- Ưu tiên behavior assertion thay vì implementation detail.
- Chạy narrow test command trước.
- Báo command, result và remaining gaps.

Prompt áp dụng:

```text
/test-writer Add or propose focused tests for task creation validation in taskflow-ai.
Inspect existing tests first.
Cover valid creation, missing title, unauthorized request, and invalid due date if applicable.
Run the narrowest relevant test command if files are edited.
```

Command test tham khảo:

```bash
npm run test -- tasks
npm test
npm run test:api
```

Chạy ở root `taskflow-ai`. Ưu tiên lệnh hẹp nhất có trong `package.json`: filter theo `tasks` nếu test runner hỗ trợ, rồi mới tới `test:api`, cuối cùng mới chạy `npm test`. Output kỳ vọng là pass/fail rõ ràng kèm tên test hoặc assertion lỗi. Rủi ro: full suite có thể chậm, cần database/cache, hoặc fail do môi trường local chứ không phải do Skill.

Nếu không biết command, đọc `package.json`:

```bash
cat package.json
```

PowerShell:

```powershell
Get-Content package.json
```

Chạy ở root `taskflow-ai`. Lệnh chỉ đọc script npm để chọn command test đúng; output kỳ vọng có mục `scripts`. Rủi ro thấp, nhưng không nên copy nội dung có token/private registry nếu dự án vô tình đặt secret trong file này.

## Bài 3 — Nâng cao

Mục tiêu: thêm supporting file cho `api-reviewer`.

Tạo:

```bash
mkdir -p .claude/skills/api-reviewer/checklists
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force .claude/skills/api-reviewer/checklists
```

Chạy ở root `taskflow-ai`. Lệnh tạo thư mục supporting files cho `api-reviewer`; output kỳ vọng là thư mục `checklists` tồn tại dưới đúng Skill. Rủi ro thấp, nhưng cần tránh tạo checklist rời khỏi Skill vì Claude sẽ khó tìm đúng tài liệu hỗ trợ.

Tạo `.claude/skills/api-reviewer/checklists/security.md`:

```md
# API Security Checklist

Check:

- Authentication is required where needed.
- Authorization verifies ownership or role.
- User input is validated before use.
- Error responses do not leak internals.
- Secrets are not logged or returned.
- Query filters cannot expose another user's data.
- Expensive endpoints consider rate limit or abuse risk.
```

Cập nhật `SKILL.md`:

```md
If the API change touches auth, user ownership, sensitive data, or external input, consult `checklists/security.md`.
```

Prompt kiểm thử:

```text
/api-reviewer Review DELETE /api/tasks/:id.
Pay special attention to ownership checks and data exposure.
Use the security checklist if relevant.
```

Expected result: findings có nhắc ownership, auth, error behavior, test gaps hoặc nói rõ không có high-confidence findings.

## Bài 4 — Review & Reflection

Review hai Skill như review code:

```text
Review my Day 13 Skills:
- .claude/skills/api-reviewer/SKILL.md
- .claude/skills/test-writer/SKILL.md

Focus on description precision, context efficiency, allowed-tools risk, output format, and maintainability.
Do not edit files. Return findings and suggested improvements.
```

Trả lời ngắn:

1. Skill nào giúp giảm prompt lặp lại nhiều nhất?
2. `description` có đủ rõ không?
3. Skill có bị gọi sai ngữ cảnh không?
4. `SKILL.md` có quá dài không?
5. Có phần nào nên chuyển sang supporting file không?
6. `allowed-tools` có tool nào không cần thiết không?
7. Skill có làm Claude tự sửa file khi bạn chỉ muốn review không?
8. Output có đủ actionable không?
9. Có command hoặc test nào nên đưa vào instruction không?
10. Nếu team cùng dùng, cần thêm convention nào?

## Tiêu chí hoàn thành

- [ ] Có `.claude/skills/api-reviewer/SKILL.md`.
- [ ] Có `.claude/skills/test-writer/SKILL.md`.
- [ ] Cả hai Skill có frontmatter hợp lệ.
- [ ] `api-reviewer` có output findings theo severity.
- [ ] `test-writer` inspect nearby tests trước khi viết test.
- [ ] Đã gọi thử `/api-reviewer` trên một endpoint thật.
- [ ] Đã gọi thử `/test-writer` cho một behavior hoặc bug cụ thể.
- [ ] Có command test hoặc lý do rõ nếu chưa chạy được test.
- [ ] Có ghi chú rủi ro security, maintainability, context, permission.
- [ ] Biết rollback bằng cách xóa thư mục Skill vừa tạo.

## Gợi ý nếu bí

Nếu không biết viết `description`:

```yaml
description: Review taskflow-ai API changes for routes, controllers, services, schemas, auth, validation, response contracts, errors, security, tests, rollback risk, and maintainability.
```

Nếu Skill review tự sửa file, thêm:

```md
Do not edit files unless the user explicitly asks for fixes.
```

Nếu output quá dài:

```md
Report only actionable findings. Order findings by severity. Limit low-priority cleanup suggestions.
```

Nếu Skill không trigger, gọi trực tiếp:

```text
/api-reviewer Review PATCH /api/tasks/:id.
```

## Đáp án tham khảo hoặc expected result

Project structure:

```text
.claude/
  skills/
    api-reviewer/
      SKILL.md
      checklists/
        security.md
    test-writer/
      SKILL.md
```

Expected reflection:

```text
api-reviewer giúp chuẩn hóa review API và giảm prompt lặp lại. test-writer hữu ích khi biến review findings thành regression tests. Điểm cần cải thiện là thu hẹp description để không bị gọi cho docs/UI-only changes và chuyển checklist security dài sang supporting file.
```
