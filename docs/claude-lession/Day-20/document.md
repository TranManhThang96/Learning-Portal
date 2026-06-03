# Document — Day 20

## Tóm tắt kiến thức

Day 20 là capstone: dùng Claude Code build feature `task comments` end-to-end trong `taskflow-ai`.

Workflow chuẩn:

```text
clarify -> acceptance criteria -> plan -> backend -> frontend -> tests -> review -> PR -> postmortem
```

Các năng lực cần nối lại:

- Project memory: `CLAUDE.md` hoặc `.claude/CLAUDE.md`; project rules trong `.claude/rules/`; personal rules trong `~/.claude/rules/`.
- Permissions/settings/hooks, gồm `/permissions`, permission mode, `.claude/settings.json` và hook events như `PreToolUse`, `PostToolUse`.
- Skills/subagents cho backend, frontend, reviewer, tester; project skill nằm trong `.claude/skills/<skill-name>/SKILL.md`, project subagent nằm trong `.claude/agents/`.
- MCP/docs search khi cần API/framework docs hiện hành.
- GitHub workflow: branch, PR, checks, review.
- Context/session commands: `/plan`, `/context`, `/compact`, `/clear`, `/rewind`, `/usage`.
- Human review/merge là bắt buộc.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Clarify requirement
  -> write acceptance criteria
  -> plan files and tests
  -> backend API
  -> backend tests
  -> frontend UI
  -> UI tests
  -> e2e or documented gap
  -> review diff
  -> PR description
  -> postmortem and guardrails
```

Luồng feature:

```text
User opens task detail
  -> UI calls GET /api/tasks/:taskId/comments
  -> API checks task access
  -> user submits comment
  -> API validates content and user
  -> DB/storage creates comment
  -> UI refetches or updates list
  -> user deletes comment
  -> API checks author or task owner
```

## Bảng so sánh

| Chủ đề | Cách yếu | Cách tốt trong capstone |
| --- | --- | --- |
| Requirement | “Thêm comment” | Acceptance criteria rõ |
| Prompt | Một prompt dài làm hết | Chia clarify, plan, backend, frontend, tests, review |
| Context | Đọc lan toàn repo | Dùng `rg`, file liên quan, compact có focus |
| Auth | Bỏ qua vì project học | Auth thật nếu có, fallback `x-user-id` có test |
| Validation | Chỉ validate frontend | Validate server-side |
| Test | Chỉ happy path | Có validation, forbidden, not found |
| Data integrity | Comment chỉ có `commentId` | Comment luôn scoped bởi `taskId` và FK/index nếu có DB |
| Performance | List không giới hạn mãi mãi | Capstone có thể đơn giản, nhưng ghi rõ khi cần limit/cursor |
| Review | Tin Claude nói done | Đọc diff, chạy test, review security |
| Rollback | Revert cả branch | `/rewind` cho checkpoint Claude edit, hoặc restore từng file |
| Docs | PR chung chung | PR có test evidence, risk, rollback |

## Lỗi thường gặp

- Claude tạo API route khác convention.
- Response shape không giống API cũ.
- Comment không kiểm tra task tồn tại.
- Comment của task A bị xóa qua URL task B.
- Thiếu index theo `taskId, createdAt`, list comment chậm khi dữ liệu tăng.
- Không đặt giới hạn số comments trả về dù product có thể dùng lâu dài.
- Chỉ author được xóa, quên task owner.
- Validate client-side nhưng backend vẫn nhận content rỗng.
- Render comment bằng raw HTML hoặc Markdown không sanitize, tạo XSS risk.
- UI không xử lý loading/error/empty.
- Test mock quá sâu, không bắt bug route/service thật.
- E2E phụ thuộc dữ liệu local không seed ổn định.
- Claude sửa formatting lớn làm diff khó review.
- Compact làm mất decision vì không có summary tốt.

## Cách debug

Chạy ở root `taskflow-ai`:

```bash
git status --short
git diff --stat
git diff -- path/to/file
npm run lint
npm run test
npm run e2e
```

Ý nghĩa:

- `git status --short`: xem file changed/untracked.
- `git diff --stat`: xem blast radius.
- `git diff -- path/to/file`: review một file.
- `npm run lint`: bắt lint/style issue.
- `npm run test`: chạy suite chính nếu có.
- `npm run e2e`: kiểm tra flow browser nếu setup sẵn.

Rủi ro: script có thể tên khác hoặc cần service/test DB. Đọc `package.json` và docs repo trước khi chạy.

Debug theo triệu chứng:

- API `404`: kiểm tra task seed, route param, comment-task relation.
- API `403`: kiểm tra user hiện tại, `x-user-id`, owner/author logic.
- Add comment thành công nhưng UI không đổi: kiểm tra cache/refetch/state update.
- Delete biến mất rồi reload lại xuất hiện: optimistic update đang che lỗi API.
- Test pass nhưng manual fail: test mock sai layer hoặc thiếu integration.
- Claude đi sai hướng: dừng, `/rewind`, chia lại backend-only.
- `/rewind` không undo được thay đổi do Bash command tạo ra: kiểm tra `git diff` và rollback bằng Git/migration tool nếu cần.

Checklist debug nhanh:

| Cwd | Command | Mục đích | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| Root `taskflow-ai` | `git status --short` | Xác nhận file changed/untracked | Chỉ file feature đã biết | Không dùng restore diện rộng khi có thay đổi của người khác |
| Root `taskflow-ai` | `git diff --stat` | Xem blast radius | File list khớp plan | Diff lớn dễ che bug logic |
| Root hoặc workspace backend | `npm run test:backend` hoặc script tương đương | Kiểm tra API/auth/validation | Pass hoặc fail rõ test case | Có thể cần test DB/env |
| Root hoặc workspace frontend | `npm run test:frontend` hoặc script tương đương | Kiểm tra UI states | Pass | Test mock sai layer vẫn có thể bỏ sót integration bug |
| Root hoặc workspace e2e | `npm run e2e` | Kiểm tra browser flow | Pass với seed ổn định | Có thể cần dev server/test DB |

## Link tài liệu nên đọc

- Claude Code Overview: https://code.claude.com/docs/en/overview
- Claude Code Memory: https://code.claude.com/docs/en/memory
- Claude Code Commands: https://code.claude.com/docs/en/commands
- Claude Code Checkpointing: https://code.claude.com/docs/en/checkpointing
- Claude Code Permission Modes: https://code.claude.com/docs/en/permission-modes
- Claude Code Settings: https://code.claude.com/docs/en/settings
- Claude Code Hooks: https://code.claude.com/docs/en/hooks
- Claude Code Skills: https://code.claude.com/docs/en/skills
- Claude Code Subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code MCP: https://code.claude.com/docs/en/mcp
- Claude Code GitHub Actions: https://code.claude.com/docs/en/github-actions
- GitHub Pull Requests: https://docs.github.com/en/pull-requests
- Fastify Docs: https://fastify.dev/docs/latest/
- PostgreSQL Docs: https://www.postgresql.org/docs/
- Vitest Docs: https://vitest.dev/guide/
- React Docs: https://react.dev/
- Playwright Docs: https://playwright.dev/docs/intro
