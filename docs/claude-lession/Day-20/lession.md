# Day 20 — Capstone: build feature end-to-end

## 1. Mục tiêu bài học

Sau Day 20, học viên có thể dùng Claude Code để đi hết một feature thật trong `taskflow-ai` theo workflow:

```text
clarify -> plan -> implement -> test -> review -> document
```

Kết quả cần đạt:

- Tổng hợp project memory (`CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/`), permissions, hooks, skills, subagents, MCP/docs search, GitHub workflow, testing, security và context summary.
- Thêm feature `task comments` end-to-end.
- Đánh giá output của Claude Code bằng acceptance criteria, test evidence và review diff.
- Viết PR description và postmortem trung thực.
- Biết rollback khi Claude sửa sai.

## 2. Bối cảnh thực tế

Feature nhỏ như “comment trong task” thường chạm nhiều lớp:

- Database/schema hoặc storage.
- Backend API.
- Authorization.
- Validation.
- Frontend UI.
- Unit/integration/e2e tests.
- GitHub PR, review, docs, rollback.

Claude Code mạnh ở đọc codebase, đi theo pattern có sẵn, sinh test và sửa lỗi lặp. Nhưng Claude có thể đoán sai architecture, bỏ sót authorization, viết test happy path quá mỏng hoặc sửa lan sang module không liên quan. Human vẫn chịu trách nhiệm review và merge.

## 3. Kiến thức nền

### Acceptance criteria cho `task comments`

API:

- `GET /api/tasks/:taskId/comments`: liệt kê comments theo task, sort ổn định.
- `POST /api/tasks/:taskId/comments`: thêm comment, trim content, reject rỗng, max 1000 ký tự.
- `DELETE /api/tasks/:taskId/comments/:commentId`: xóa comment.
- Nếu dùng database thật, comment có foreign key tới task và index phục vụ query theo `taskId` + `createdAt`.

Security/authorization:

- Chỉ user có quyền xem task được list/create comment.
- Delete chỉ cho comment author hoặc task owner.
- Nếu chưa có auth thật, dùng `x-user-id` trong dev/test helper, không hard-code user trong service.

Frontend:

- Task detail có comments section.
- Có loading, error, empty state.
- Form add comment có validation client-side.
- Delete action chỉ hiện khi user có quyền.
- Sau add/delete, UI cập nhật bằng refetch hoặc optimistic update có kiểm soát.

Tests:

- Backend integration tests cho list/create/delete/validation/auth.
- Test case phải bắt lỗi comment-task mismatch, ví dụ gọi `DELETE /tasks/A/comments/commentOfTaskB`.
- UI/component tests cho render, submit, validation, delete.
- E2E flow nếu project đã có setup.

### Kỹ năng Claude Code nối lại

- Project memory: `CLAUDE.md` hoặc `.claude/CLAUDE.md`; project rules trong `.claude/rules/`; personal rules trong `~/.claude/rules/`.
- Permissions/settings: dùng `/permissions`, permission mode và `.claude/settings.json` để giới hạn tool, command, protected paths và command nguy hiểm.
- Hooks: auto check hoặc chặn hành vi nhạy cảm qua các event như `PreToolUse`, `PostToolUse`, `UserPromptSubmit`.
- Skills/subagents: tách backend, frontend, reviewer, tester; project skills nằm trong `.claude/skills/<skill-name>/SKILL.md`, project subagents nằm trong `.claude/agents/`.
- MCP/docs search: tra docs framework/API hiện hành khi cần.
- Context/session commands: `/plan`, `/context`, `/compact`, `/clear`, `/rewind`, `/usage`.
- GitHub workflow: branch, PR, review, checks.

## 4. Step-by-step thực hành

### Bước 0: Chuẩn bị branch

Chạy ở root `taskflow-ai`.

```bash
git status --short
git switch -c feature/task-comments
```

Thông tin lệnh:

| Command | Mục đích | Output kỳ vọng | Rủi ro / lưu ý |
| --- | --- | --- | --- |
| `git status --short` | Kiểm tra working tree trước khi giao Claude sửa code | Không có output hoặc chỉ có thay đổi đã hiểu rõ | Nếu có file bẩn của người khác, không dùng rollback diện rộng |
| `git switch -c feature/task-comments` | Tạo branch riêng cho capstone | Git báo đã chuyển sang branch mới | Nếu branch đã tồn tại, dùng `git switch feature/task-comments` sau khi kiểm tra đúng branch |

### Bước 1: Khám phá codebase

Chạy ở root `taskflow-ai`.

```bash
rg -n "task|tasks|Task|route|controller|spec|test" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**"
```

Lệnh tìm code liên quan task, route, UI và tests. Output kỳ vọng là các file ứng viên như route/controller/service, component task detail và test files. Rủi ro: output lớn; chỉ đưa path liên quan vào prompt, không paste toàn bộ kết quả nếu có nhiều dòng.

Prompt:

```text
Bạn đang ở repo taskflow-ai. Trước khi code, hãy đọc cấu trúc liên quan đến task detail, task API, auth hiện có và test setup. Không chỉnh file.

Trả lời:
1. Stack backend/frontend/test đang dùng.
2. Các file nhiều khả năng cần sửa.
3. Convention API và error response hiện tại.
4. Những câu hỏi cần clarify trước khi implement.
```

### Bước 2: Clarify

Prompt:

```text
Clarify feature task comments cho taskflow-ai.

Yêu cầu bắt buộc:
- add/list/delete comments theo task
- validate content: trim, required, max 1000 chars
- link comment với task
- auth giả lập bằng x-user-id nếu chưa có auth thật
- delete chỉ author hoặc task owner
- test backend + UI + e2e
- PR description + postmortem

Hãy hỏi tối đa 7 câu cần thiết. Nếu repo đã có convention rõ, tự chọn theo convention và ghi assumption. Chưa sửa file.
```

### Bước 3: Plan

Prompt:

```text
Dựa trên câu trả lời clarify và codebase taskflow-ai, lập implementation plan cho feature task comments.

Plan phải có:
- data model/schema thay đổi nếu cần
- backend endpoints
- frontend components/state
- test plan backend/UI/e2e
- security/authorization checks
- migration hoặc seed nếu cần
- rollback plan
- danh sách file dự kiến sửa

Không code. Đánh dấu việc nào cần human confirm.
```

Review plan: có auth không, validation server-side không, tests có forbidden path không, file list có ngoài scope không.
Nếu plan đề xuất tạo framework mới, đổi response shape cũ hoặc sửa file không liên quan đến task comments, yêu cầu Claude thu hẹp lại trước khi implement.

### Bước 4: Implement backend

Prompt:

```text
Implement backend cho task comments theo plan đã duyệt.

Ràng buộc:
- Đi theo pattern route/controller/service/repository hiện có.
- Không đổi response shape API cũ.
- Nếu chưa có auth thật, đọc user id từ header x-user-id trong test/dev helper.
- Validate content server-side: trim, required, max 1000 chars.
- Delete chỉ cho comment author hoặc task owner.
- Thêm integration tests cho list, create, validation, task not found, unauthorized, delete by author, delete by task owner, reject delete by other user.

Sau khi sửa, chạy đúng lệnh test backend đã có. Với mỗi lệnh, báo cwd, command, mục đích, expected output, risk.
```

Command thường dùng, chạy ở root `taskflow-ai` hoặc backend workspace nếu repo tách package:

```bash
npm run test:backend
git diff --stat
```

| Command | Mục đích | Output kỳ vọng | Rủi ro / rollback |
| --- | --- | --- | --- |
| `npm run test:backend` | Kiểm tra API/service/repository và validation/auth | Test runner pass; nếu fail, log chỉ rõ test case | Có thể cần test DB/env; không tự sửa config lớn khi chưa đọc docs repo |
| `git diff --stat` | Xem blast radius sau backend phase | Chỉ các file backend/schema/test liên quan | Nếu diff lan rộng, dừng và dùng `/rewind` hoặc `git restore -- path/to/file` cho từng file |

### Bước 5: Implement frontend

Prompt:

```text
Implement frontend UI cho task comments.

Yêu cầu:
- Tìm task detail page/component hiện có.
- Thêm comments section theo design hiện tại.
- Có loading, error, empty state.
- Form add comment: textarea, submit disabled khi rỗng/loading, lỗi max length.
- Delete button chỉ hiện với user có quyền.
- Sau add/delete cập nhật list.
- Không đổi layout lớn.
- Thêm UI/component tests theo stack hiện có.
```

Command thường dùng, chạy ở root `taskflow-ai` hoặc frontend workspace nếu repo tách package:

```bash
npm run test:frontend
npm run lint
npm run typecheck
```

| Command | Mục đích | Output kỳ vọng | Rủi ro / lưu ý |
| --- | --- | --- | --- |
| `npm run test:frontend` | Kiểm tra component/UI behavior | UI tests pass, có coverage cho empty/loading/error/add/delete | Script có thể tên khác; đọc `package.json` trước khi đổi |
| `npm run lint` | Bắt lint/style issue | Không còn lint error | Lint autofix có thể tạo diff format lớn, review `git diff --stat` |
| `npm run typecheck` | Bắt type error giữa API client và UI | Typecheck pass | Nếu fail do generated types, tìm command generate đã có trong repo |

### Bước 6: E2E hoặc test thay thế

Prompt:

```text
Thêm e2e test cho task comments nếu project đã có setup.

Flow:
1. Mở task detail.
2. Thấy empty state hoặc list comments.
3. Add comment "Ship review notes".
4. Comment xuất hiện.
5. Reload/refetch, comment vẫn còn.
6. Delete comment.
7. User khác không thấy delete hoặc API từ chối.

Nếu chưa có e2e setup, đề xuất integration/component test thay thế và ghi rõ gap.
```

Command, chạy ở root `taskflow-ai` hoặc workspace e2e nếu repo tách package:

```bash
npm run e2e
```

Output kỳ vọng: browser test pass cho flow add/delete comment. Rủi ro: cần dev server/test DB/seed ổn định; nếu chưa có setup, không dựng framework lớn chỉ cho một bài mà ghi rõ gap và tăng integration/component coverage.

### Bước 7: Review diff

Chạy ở root `taskflow-ai`.

```bash
git diff --stat
git diff
git status --short
```

| Command | Mục đích | Output kỳ vọng | Rủi ro / lưu ý |
| --- | --- | --- | --- |
| `git diff --stat` | Xem phạm vi thay đổi | Chỉ file liên quan feature, test, migration/docs cần thiết | Diff quá rộng là dấu hiệu phải chia lại phase |
| `git diff` | Review logic cụ thể | Dễ đọc, không có formatting churn lớn | Output dài; review theo từng file hoặc path |
| `git status --short` | Bắt untracked/changed files | Không có file lạ ngoài plan | Không dùng `git restore .` trong repo có nhiều người cùng sửa |

Prompt:

```text
Review toàn bộ diff như senior reviewer.

Tập trung:
- security/authz bug
- validation gap
- stale UI state
- consistency với pattern hiện có
- test có thật sự bắt bug không
- migration/seed risk
- breaking change với API cũ
- file ngoài phạm vi feature hoặc ngoài file list trong plan

Trả findings trước, severity cao đến thấp, có file/line. Không sửa file.
```

### Bước 8: PR description và postmortem

Prompt PR:

```text
Viết PR description cho feature task comments.

Format:
## Summary
## Acceptance Criteria
## Implementation Notes
## Tests
## Security / Authorization
## Screenshots hoặc UI Notes
## Rollback Plan
## Postmortem

Dựa trên diff hiện tại và test output đã chạy. Không phóng đại. Nếu test nào chưa chạy, ghi rõ Not run và lý do.
```

Prompt postmortem:

```text
Viết postmortem ngắn cho lần dùng Claude Code implement task comments:
- Claude làm tốt gì
- Claude sai/suýt sai gì
- Guardrail cần thêm vào CLAUDE.md/settings/hooks/tests
- Điều human phải review thủ công trước merge
```

### Bước 9: Rollback khi Claude làm sai

Ưu tiên `/rewind` hoặc `Esc + Esc` trong Claude Code để mở checkpoint menu. Chọn restore code, restore conversation, hoặc summarize tùy lỗi. Lưu ý: checkpointing chỉ theo dõi file Claude sửa bằng tool edit; thay đổi do Bash command, migration tự chạy hoặc thao tác ngoài Claude Code có thể không được undo bởi `/rewind`.

Nếu cần git, rollback từng file:

```bash
git diff -- path/to/file
git restore -- path/to/file
```

`git restore -- path/to/file` mất toàn bộ thay đổi chưa commit của file đó. Không dùng với `.` nếu workspace có thay đổi của người khác. Nếu đã thêm migration, cần rollback migration theo cơ chế của stack hiện có và xác nhận test database không còn schema dư.

## 5. Prompt mẫu nên dùng

Clarify:

```text
Trước khi code, hãy clarify feature task comments. Hỏi tối đa 7 câu. Nếu repo có convention rõ thì tự chọn và ghi assumption. Không sửa file.
```

Plan:

```text
Lập plan end-to-end cho task comments: backend API, UI, tests, auth, validation, rollback, file list. Không code.
```

Backend:

```text
Implement backend task comments theo pattern hiện có. Thêm API list/create/delete, validation server-side, owner/author authorization, integration tests.
```

Frontend:

```text
Implement comments section trong task detail. Có list, empty/loading/error, add form, delete action, refetch hoặc optimistic update.
```

Tests:

```text
Audit test coverage cho task comments. Bổ sung validation, auth, UI state, e2e happy path và forbidden path. Không viết test chỉ kiểm tra implementation detail.
```

Review:

```text
Review diff như senior reviewer. Findings trước, severity cao đến thấp, file/line cụ thể. Tập trung auth, validation, API compatibility, stale UI, missing tests.
```

PR:

```text
Viết PR description từ diff và test output hiện tại. Ghi rõ test chưa chạy.
```

## 6. Trade-offs

| Quyết định | Option A | Option B | Chọn khi |
| --- | --- | --- | --- |
| Delete comment | Hard delete | Soft delete | Hard delete cho capstone đơn giản; soft delete nếu cần audit |
| Sort comments | `createdAt ASC` | `createdAt DESC` | ASC cho thread đọc tự nhiên; DESC nếu ưu tiên activity mới |
| Auth | Auth thật | `x-user-id` giả lập | Dùng auth thật nếu có; giả lập chỉ cho học/test |
| UI update | Refetch sau mutate | Optimistic update | Refetch ít bug hơn; optimistic khi UX cần nhanh |
| E2E | Full browser | API + component | Full browser nếu setup sẵn; không dựng framework lớn chỉ cho 1 bài |
| Context | Một session dài | Chia theo phase | Chia phase nếu repo lớn hoặc context gần đầy |
| Pagination | List hết comments | Cursor/page limit | List hết chỉ ổn cho capstone nhỏ; thêm limit/cursor nếu task có thể có nhiều comments |
| Query performance | Không index | Index `taskId, createdAt` | Index khi comments lưu DB và list theo task thường xuyên |

## 7. Best practices

- Bắt Claude clarify trước khi sửa.
- Yêu cầu Claude đọc pattern hiện có, không tự tạo architecture mới.
- Viết acceptance criteria trước implementation.
- Test auth và validation trước UI polish.
- Review diff theo file, không chỉ đọc summary của Claude.
- Dùng `/compact` với focus khi session dài.
- Dùng `/context` để xem context đang bị tiêu hao bởi phần nào trước khi compact.
- Dùng `/clear` khi chuyển task.
- Đưa rule bền vững vào `CLAUDE.md`.
- Scope MCP tools và permissions tối thiểu.
- Không dùng `bypassPermissions` ngoài container/VM cô lập; với capstone, ưu tiên `plan` hoặc `acceptEdits` rồi review diff.
- Không render comment bằng raw HTML. Nếu sau này hỗ trợ Markdown, sanitize output và test XSS.
- Human chịu trách nhiệm cuối cùng với security, migration và merge.

## 8. Performance / cost / context

- Không paste toàn bộ repo vào prompt; dùng `rg` và file liên quan.
- Tách backend, frontend, tests, review thành phase riêng.
- Dùng subagent cho review/docs search khi có lợi.
- Dùng docs search/MCP khi đụng framework/API thay vì đoán; ưu tiên official docs và ghi nguồn nếu quyết định phụ thuộc API/tooling hiện hành.
- Dùng `/usage` hoặc `/cost` nếu cần kiểm tra mức tiêu thụ, và lưu test evidence ngắn thay vì paste log dài vào context.
- Dùng `/compact` trước khi context đầy và ghi rõ focus.
- Sau compact, xác nhận lại API shape, auth rule, files changed, tests run.
- Với command output dài, chỉ giữ phần fail liên quan.

## 9. Checklist cuối bài

- [ ] Có branch riêng cho `task comments`.
- [ ] Có acceptance criteria rõ.
- [ ] Backend API list/create/delete hoạt động.
- [ ] Server-side validation có test.
- [ ] Authorization owner/author có test.
- [ ] UI task detail có comments section.
- [ ] UI xử lý loading/error/empty.
- [ ] E2E hoặc test thay thế được ghi rõ.
- [ ] Lint/type/test đã chạy hoặc có lý do chưa chạy.
- [ ] Diff không chạm file ngoài phạm vi feature hoặc ngoài file list đã duyệt.
- [ ] PR description có rollback plan.
- [ ] Postmortem có guardrail cụ thể.
- [ ] Human review trước merge.

## 10. Bài tập

Hoàn thành feature `task comments` trong `taskflow-ai` bằng workflow chuẩn.

Deliverables:

- Backend API + tests.
- Frontend UI + tests.
- E2E hoặc ghi rõ gap.
- PR description.
- Postmortem 10-15 dòng.
- Một update nhỏ cho `CLAUDE.md` hoặc `.claude/CLAUDE.md` rút ra từ bài học.
