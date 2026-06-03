# Exercise — Day 14

## Bài 1 — Cơ bản

Mục tiêu: tạo 2 project subagents:

```text
.claude/agents/code-reviewer.md
.claude/agents/test-engineer.md
```

Tạo thư mục:

```bash
mkdir -p .claude/agents
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force .claude/agents
```

Giải thích lệnh:

- Thư mục chạy: root `taskflow-ai`.
- `mkdir -p` hoặc `New-Item -Force`: tạo `.claude/agents` nếu chưa có.
- Output kỳ vọng: thư mục được tạo, không có lỗi.
- Rủi ro: thấp; nếu chạy nhầm repo sẽ tạo thư mục `.claude` nhầm chỗ.

`code-reviewer` phải có:

- `name: code-reviewer`.
- `description` rõ khi nào dùng.
- `tools: Read, Grep, Glob, Bash`.
- Không đưa `Write`, `Edit`, hoặc tool ghi file vào allowlist.
- Prompt yêu cầu review theo severity.
- Guardrail không sửa file.

`test-engineer` phải có:

- `name: test-engineer`.
- `description` rõ khi nào dùng.
- `tools` gồm `Bash`.
- Prompt yêu cầu chạy test có command cụ thể.
- Phân biệt product bug, test bug, environment issue.
- Guardrail không sửa file nếu chưa được yêu cầu.

Kiểm tra:

```bash
git status --short
```

Output kỳ vọng:

```text
?? .claude/agents/code-reviewer.md
?? .claude/agents/test-engineer.md
```

Giải thích lệnh:

- Thư mục chạy: root `taskflow-ai`.
- `git status --short`: xác nhận chỉ có 2 agent files mới hoặc modified.
- Output kỳ vọng: không xuất hiện file ngoài phạm vi bài tập.
- Rủi ro: thấp; đây là lệnh read-only. Nếu thấy thay đổi của người khác, không rollback toàn repo.

Rollback:

```bash
rm .claude/agents/code-reviewer.md .claude/agents/test-engineer.md
```

PowerShell:

```powershell
Remove-Item .claude/agents/code-reviewer.md, .claude/agents/test-engineer.md
```

Giải thích rollback:

- Chỉ chạy nếu muốn xóa 2 agent tạo trong bài tập.
- Thư mục chạy: root `taskflow-ai`.
- Output kỳ vọng: 2 file bị xóa, `git status --short` không còn hiển thị chúng nếu chưa commit.
- Rủi ro: mất nội dung agent nếu bạn đã chỉnh tay. Không dùng wildcard như `Remove-Item .claude/agents/*` khi team đã có agent khác.

## Bài 2 — Thực tế

Mục tiêu: dùng subagents trong workflow thật.

Chọn một feature nhỏ:

```text
Add task priority with low, medium, high.
```

hoặc:

```text
Add due date to tasks and show overdue state.
```

Workflow:

1. Plan.
2. Implement.
3. Review bằng `code-reviewer`.
4. Fix findings hợp lý.
5. Test bằng `test-engineer`.
6. Tổng hợp kết quả.

Prompt plan:

```text
Plan adding task priority to taskflow-ai. Split the plan into data model, API changes, UI changes, tests, migration or compatibility concerns, rollback risks, and acceptance criteria. Do not edit files yet.
```

Prompt review:

```text
@"code-reviewer (agent)" review the current git diff. Focus on correctness, maintainability, security risks, regressions, and missing tests. Return findings ordered by severity. Do not edit files.
```

Prompt test:

```text
@"test-engineer (agent)" validate the current changes. Run the smallest relevant tests first, then broader checks if useful. Report exact commands, exit status, important output, and whether this blocks merge.
```

Command nên chạy:

```bash
git diff --stat
git diff
npm run
npm test
npm run lint
npm run typecheck
```

Nếu repo dùng `pnpm`:

```bash
pnpm test
pnpm lint
pnpm typecheck
```

Giải thích command:

| Command | Thư mục chạy | Làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `git diff --stat` | Root `taskflow-ai` | Tóm tắt file thay đổi | Danh sách file và số dòng đổi | Thấp; read-only |
| `git diff` | Root `taskflow-ai` | Xem chi tiết diff để reviewer/tester hiểu scope | Patch của feature hiện tại | Có thể lộ secret nếu diff chứa secret; không paste bừa ra ngoài |
| `npm run` | Package hoặc root có `package.json` | Liệt kê scripts khả dụng | Có `test`, `lint`, `typecheck` nếu project đã cấu hình | Thấp |
| `npm test` / `pnpm test` | Package liên quan | Chạy test mặc định | Exit code `0` hoặc failure rõ | Có thể cần service local như PostgreSQL/Redis |
| `npm run lint` / `pnpm lint` | Package liên quan | Chạy lint/static checks | Không có error | Có thể fail do lỗi cũ; ghi rõ nếu không liên quan feature |
| `npm run typecheck` / `pnpm typecheck` | Package TypeScript | Chạy kiểm tra type | Không có TypeScript error | Có thể chậm ở monorepo |

Không chạy migration, seed hoặc command xóa dữ liệu nếu prompt/tester chưa giải thích rõ environment. Với bài này, ưu tiên local/dev database.

## Bài 3 — Nâng cao

Mục tiêu: tạo `security-auditor`.

Tạo `.claude/agents/security-auditor.md`:

```md
---
name: security-auditor
description: Use this agent to audit security-sensitive changes involving authentication, authorization, user data, external APIs, secrets, file access, or shell commands.
model: sonnet
tools: Read, Grep, Glob, Bash
color: red
---

You are a security auditor for taskflow-ai.

Audit code without editing files.

Focus areas:
1. Authentication and authorization bypass.
2. Injection: SQL, NoSQL, command, prompt, HTML/XSS.
3. Secrets committed to code or logs.
4. Unsafe file access or shell execution.
5. Sensitive data exposure.
6. Insecure error handling.
7. Missing validation on user-controlled input.

For each finding, include severity, file, exploit scenario, impact, recommended fix, and whether it blocks merge.
If there are no high-confidence findings, say so clearly.
```

Prompt chạy audit:

```text
@"security-auditor (agent)" audit the current git diff for security issues. Focus on user-controlled input, authorization, secrets, unsafe shell usage, and sensitive data exposure. Do not edit files.
```

Expected result:

```text
Findings
- High: No high-confidence findings.
- Medium: ...

Residual risk
- ...
```

## Bài 4 — Review & Reflection

Trả lời:

1. Subagent khác main agent ở điểm nào?
2. Vì sao reviewer nên có context window riêng?
3. Khi nào không nên dùng subagent?
4. Vì sao không nên cho `code-reviewer` quyền `Edit`?
5. `test-engineer` cần `Bash` để làm gì?
6. Rủi ro của việc cấp tools quá rộng cho subagent là gì?
7. Project subagents nên đặt ở đâu?
8. User subagents nên đặt ở đâu?
9. Vì sao project subagents nên commit nếu team dùng chung?
10. Trong workflow `plan -> implement -> review -> test`, bước nào giảm bias nhất?

Expected answer ngắn:

```text
Subagent có prompt, context và tools riêng. Reviewer nên có context riêng để review độc lập hơn, ít bị ảnh hưởng bởi reasoning của implementer. Không nên dùng subagent cho thay đổi quá nhỏ hoặc task một bước. code-reviewer không nên có Edit vì reviewer cần giữ vai trò review. test-engineer cần Bash để chạy test/lint/typecheck. Cấp tools quá rộng có thể làm subagent vượt vai trò, sửa file hoặc chạy command không cần thiết. Project subagents đặt ở .claude/agents, user subagents đặt ở ~/.claude/agents. Nếu team dùng chung, project subagents nên commit để cùng tiêu chuẩn. Bước review bằng subagent sau implementation giảm bias nhất.
```

## Tiêu chí hoàn thành

- [ ] Có `.claude/agents/code-reviewer.md`.
- [ ] Có `.claude/agents/test-engineer.md`.
- [ ] Mỗi file có frontmatter hợp lệ.
- [ ] `code-reviewer` không có quyền edit file.
- [ ] `test-engineer` có quyền chạy command test.
- [ ] Đã chạy ít nhất một workflow `plan -> implement -> review -> test`.
- [ ] Có ghi lại prompt đã dùng.
- [ ] Có output review theo severity.
- [ ] Có output test với command và kết quả rõ.
- [ ] Có rollback plan.
- [ ] Có ghi chú security và maintainability risk.

## Gợi ý nếu bí

Nếu Claude không nhận subagent:

```bash
ls .claude/agents
```

Trong Claude Code, mở `/agents`. Nếu vừa tạo file markdown thủ công mà chưa thấy agent, restart Claude Code session.

Kiểm tra `name`:

```yaml
name: code-reviewer
```

Nếu chỉ nhắc `code-reviewer` trong câu nhưng Claude không delegate:

```text
Use the code-reviewer subagent defined in .claude/agents/code-reviewer.md to review the current git diff. Do not edit files.
```

Hoặc dùng cú pháp mention thủ công:

```text
@agent-code-reviewer review the current git diff. Do not edit files.
```

Nếu tester không chạy được test:

```yaml
tools: Read, Grep, Glob, Bash
```

Nếu không biết test command:

```bash
npm run
```

Nếu review quá chung chung:

```text
For each finding, include severity, file, line, failure mode, recommended fix, and merge blocking status.
```

## Đáp án tham khảo hoặc expected result

Expected workflow summary:

```text
Change:
- Added task priority with low, medium, high.

Review:
- No high-confidence correctness issues.
- Medium test gap: invalid priority value should be covered.
- Low maintainability concern: priority constants should be reused across UI and validation.

Tests:
- npm test: passed.
- npm run lint: passed.
- npm run typecheck: passed.

Security:
- Server-side validation exists for priority.
- No secrets or unsafe shell usage added.

Rollback:
- Before commit: git restore .
- After commit: git revert <commit-sha>

Decision:
- Ready to merge after adding invalid priority regression test.
```
