# Document — Day 13

## Tóm tắt kiến thức

Skill trong Claude Code là một gói instruction tái sử dụng. Một Skill thường nằm ở:

```text
~/.claude/skills/<skill-name>/SKILL.md
.claude/skills/<skill-name>/SKILL.md
```

Với `taskflow-ai`, ưu tiên project Skill trong `.claude/skills` khi Skill phụ thuộc convention của repo. Skill có thể được Claude tự chọn qua `description` hoặc được gọi trực tiếp bằng `/skill-name`.

Một Skill tốt có:

- Frontmatter rõ: `name`, `description`, `when_to_use`, `argument-hint`, `disable-model-invocation` khi cần gọi thủ công, `paths` khi cần giới hạn theo file, và `allowed-tools` khi thật sự cần pre-approve tool.
- Instruction ngắn và cụ thể.
- Output format đoán được.
- Guardrail về quyền sửa file, command, secret, và scope.
- Supporting files cho tài liệu dài.

Hai Skill chính của Day 13:

```text
.claude/skills/api-reviewer/SKILL.md
.claude/skills/test-writer/SKILL.md
```

`allowed-tools` chỉ pre-approve tool khi Skill active. Nó không cấm các tool khác theo nghĩa deny-list; permission settings vẫn là lớp kiểm soát chính.

Về context, phần mô tả Skill giúp Claude biết Skill có tồn tại, còn nội dung đầy đủ của `SKILL.md` chỉ được đưa vào conversation khi Skill được invoke. Sau đó nội dung này có thể ở lại các turn sau, vì vậy `SKILL.md` nên ngắn, còn checklist dài nên để supporting files.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Workflow lặp lại nhiều lần?
  |
  +-- Không --> Dùng prompt trực tiếp
  |
  +-- Có
       |
       v
  Checklist đã ổn định?
       |
       +-- Không --> Dùng prompt tạm, refine thêm
       |
       +-- Có
            |
            v
      Tạo Skill
            |
            v
  .claude/skills/<name>/SKILL.md
            |
            v
  Viết description có điều kiện dùng cụ thể
            |
            v
  Viết process + output format
            |
            v
  Test bằng task nhỏ trong taskflow-ai
            |
            v
  Điều chỉnh scope, allowed-tools, context cost
```

Luồng dùng `api-reviewer`:

```text
API diff
  -> /api-reviewer
  -> xác định route/method/request/response/auth
  -> check contract/security/maintainability/tests
  -> findings theo severity
  -> fix hoặc gọi /test-writer
```

Luồng dùng `test-writer`:

```text
Behavior cần test
  -> /test-writer
  -> inspect nearby tests
  -> chọn test level nhỏ nhất
  -> viết happy path + failure path + edge case
  -> chạy narrow test
  -> báo coverage và gaps
```

## Bảng so sánh

| Tiêu chí | Prompt trực tiếp | `.claude/commands/*.md` | Skills |
| --- | --- | --- | --- |
| Phù hợp | Việc ngắn, một lần | Shortcut thủ công | Workflow lặp lại có checklist |
| Tự động chọn theo ngữ cảnh | Không | Hạn chế | Có, qua `description` |
| Gọi trực tiếp | Không có tên cố định | Có | Có, bằng `/skill-name` |
| Supporting files | Không | Hạn chế | Có |
| Context cost | Mỗi lần paste lại | Tùy command | Chỉ tốn khi invoked |
| Rủi ro | Thiếu ý, lệch chuẩn | Command quá cứng | Skill dài hoặc auto-invoke sai |

| Skill | Mục đích | Khi dùng | Output tốt |
| --- | --- | --- | --- |
| `api-reviewer` | Review API readiness | Route, controller, service, schema, auth | Findings theo severity |
| `test-writer` | Viết test tập trung | Feature, bug fix, API, service, component | Test cases, command, result |
| `security-reviewer` | Review security risk | Auth, input, secrets, logging | Risk, exploit scenario, fix |
| `ui-reviewer` | Review UI workflow | Form, list, dashboard, responsive | UX/accessibility findings |

## Lỗi thường gặp

1. `description` quá chung
Ví dụ `description: Helps with code.` làm Claude khó chọn đúng. Nên viết rõ use case, project, và tiêu chí.

2. Skill quá dài
Copy toàn bộ coding standard vào `SKILL.md` làm context phình. Chuyển ví dụ dài sang supporting files.

3. Hiểu nhầm `allowed-tools`
`allowed-tools` không phải deny-list. Nếu cần cấm hành động, dùng permission settings hoặc hook.

4. Review Skill tự sửa file
Với Skill review, thêm câu: `Do not edit files unless the user explicitly asks for fixes.`

5. Skill không theo project convention
`test-writer` phải đọc nearby tests trước, không tự thêm test framework mới khi repo đã có Jest/Vitest.

6. Tạo quá nhiều Skill trùng vai trò
`api-reviewer`, `backend-reviewer`, `route-reviewer` dễ làm Claude chọn không nhất quán. Gộp hoặc phân định rõ scope.

## Cách debug

Kiểm tra Skill có đúng vị trí:

```bash
find .claude/skills -maxdepth 3 -type f -name SKILL.md
```

PowerShell:

```powershell
Get-ChildItem .claude/skills -Recurse -Filter SKILL.md
```

Chạy ở root `taskflow-ai`. Lệnh liệt kê các file `SKILL.md` trong `.claude/skills`; output kỳ vọng có đường dẫn tới `api-reviewer/SKILL.md` và `test-writer/SKILL.md`. Rủi ro thấp vì đây là lệnh đọc, nhưng nếu chạy sai thư mục sẽ báo không thấy `.claude/skills` hoặc trả về danh sách của repo khác.

Kiểm tra frontmatter:

```bash
sed -n '1,40p' .claude/skills/api-reviewer/SKILL.md
```

PowerShell:

```powershell
Get-Content .claude/skills/api-reviewer/SKILL.md -TotalCount 40
```

Chạy ở root `taskflow-ai`. Lệnh in 40 dòng đầu để kiểm tra cặp `---`, `description`, `argument-hint`, `allowed-tools`, và heading của Skill. Rủi ro thấp vì đây là lệnh đọc; không paste output có secret nếu Skill vô tình chứa thông tin nhạy cảm.

Nếu Skill không được auto-invoke, sửa `description` cho cụ thể hơn, hoặc gọi trực tiếp:

```text
/api-reviewer Review PATCH /api/tasks/:id.
```

Nếu Skill bị gọi quá thường xuyên, thu hẹp:

```yaml
description: Review only taskflow-ai backend API-facing changes or API tests. Do not use for UI-only, docs-only, or unrelated scripts.
paths: ["apps/api/**", "packages/api/**", "server/**"]
```

Nếu output quá dài:

```md
Report only actionable findings. Limit low-priority cleanup suggestions.
```

Nếu test do `test-writer` viết bị fail:

```text
/test-writer The new task tests fail. Identify the failing assertion, root cause, and smallest fix. Do not rewrite the whole file.
```

## Link tài liệu nên đọc

- Claude Code Skills: https://code.claude.com/docs/en/skills
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Settings: https://code.claude.com/docs/en/settings
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
