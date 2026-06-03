# Exercise — Day 20

## Bài 1 — Cơ bản

Mục tiêu: clarify và plan feature `task comments`, chưa code.

Yêu cầu:

- Chạy Claude Code trong repo `taskflow-ai`.
- Yêu cầu Claude đọc code liên quan task, API, UI, test.
- Tạo acceptance criteria cho list, add, delete, validation, authorization, tests.
- Tạo implementation plan có file list dự kiến.
- Không sửa file trong bài này.

Chạy ở root `taskflow-ai`:

```bash
git status --short
rg -n "task|tasks|Task" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**"
```

Chi tiết lệnh:

| Command | Mục đích | Output kỳ vọng | Rủi ro / lưu ý |
| --- | --- | --- | --- |
| `git status --short` | Đảm bảo biết rõ trạng thái repo trước khi nhờ Claude đọc/sửa | Không có output hoặc chỉ có thay đổi đã hiểu rõ | Nếu có file bẩn của người khác, không dùng rollback diện rộng |
| `rg -n "task|tasks|Task" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**"` | Tìm code task liên quan đến API, UI, test | Danh sách path và line ứng viên | Output có thể lớn; lọc thêm theo `routes`, `components`, `spec`, `test` nếu cần |

Prompt:

```text
Bạn là planning agent. Hãy đọc code liên quan đến task trong taskflow-ai, không sửa file. Tạo acceptance criteria và implementation plan cho feature task comments. Ghi rõ assumption, file dự kiến sửa, test plan và câu hỏi cần human confirm.
```

## Bài 2 — Thực tế

Mục tiêu: implement backend + frontend.

Backend:

- `GET /api/tasks/:taskId/comments`
- `POST /api/tasks/:taskId/comments`
- `DELETE /api/tasks/:taskId/comments/:commentId`
- Validate `content`: trim, required, max 1000 chars.
- Gắn comment với task.
- Delete chỉ `comment.authorId` hoặc `task.ownerId`.

Frontend:

- Comments section trong task detail.
- List, empty/loading/error state.
- Form add comment.
- Delete button theo quyền.
- UI cập nhật sau add/delete.

Prompt:

```text
Implement feature task comments theo plan đã duyệt. Làm backend trước, test backend pass rồi mới làm frontend. Bám pattern repo hiện có. Không đổi API cũ. Sau mỗi phase, báo file đã sửa, test đã chạy, lỗi còn lại.
```

Commands:

```bash
npm run test:backend
npm run test:frontend
npm run lint
git diff --stat
```

Các lệnh chạy ở root `taskflow-ai` hoặc workspace tương ứng nếu repo tách `apps/api`, `apps/web`, `packages/*`.

| Command | Mục đích | Output kỳ vọng | Rủi ro / lưu ý |
| --- | --- | --- | --- |
| `npm run test:backend` | Kiểm tra backend API/service/repository cho comments | Pass các case list/create/delete/validation/auth | Script có thể tên khác; kiểm tra `package.json`, test DB và env |
| `npm run test:frontend` | Kiểm tra component/UI comments section | Pass các state empty/loading/error/add/delete | Mock quá sâu có thể bỏ sót lỗi API integration |
| `npm run lint` | Bắt lỗi lint/style | Không còn lint error | Autofix có thể tạo diff lớn, cần review lại |
| `git diff --stat` | Kiểm tra phạm vi thay đổi sau mỗi phase | Chỉ file liên quan feature/test/migration | Nếu diff lan sang module không liên quan, dừng và review |

## Bài 3 — Nâng cao

Mục tiêu: hoàn thiện test, review, rollback và guardrail.

Thêm backend tests cho:

- Add/list/delete happy path.
- Empty content.
- Too long content.
- Task not found.
- Comment-task mismatch: không xóa được comment của task khác qua URL hiện tại.
- Unauthorized user.
- Delete by author.
- Delete by task owner.
- Reject delete by other user.

Thêm UI tests cho:

- Render empty state.
- Submit valid comment.
- Show validation error.
- Delete allowed comment.
- Hide/disable delete for unauthorized user.

Nếu có e2e setup, thêm flow browser. Nếu không, ghi rõ gap và tăng integration/component coverage.

Prompt review:

```text
Review diff hiện tại như senior reviewer. Findings trước, có severity và file/line. Tập trung security, validation, stale UI state, test gap, API compatibility. Không sửa file.
```

Prompt guardrail:

```text
Từ lỗi hoặc rủi ro phát hiện trong feature task comments, đề xuất một rule ngắn để thêm vào CLAUDE.md. Rule phải cụ thể, kiểm chứng được, không chung chung.
```

Commands:

```bash
npm run test
npm run e2e
git diff
```

Chạy ở root `taskflow-ai` hoặc workspace tương ứng.

| Command | Mục đích | Output kỳ vọng | Rủi ro / rollback |
| --- | --- | --- | --- |
| `npm run test` | Chạy suite chính sau khi backend + frontend hoàn tất | Pass hoặc fail rõ test case | Có thể lâu; nếu fail unrelated, ghi rõ evidence và không sửa lan |
| `npm run e2e` | Kiểm tra browser flow add/delete comment | Pass với seed/test DB ổn định | Có thể cần dev server/test DB; nếu chưa có setup, ghi gap |
| `git diff` | Review logic thật trước khi viết PR | Diff đọc được, không có formatting churn lớn | Output dài; review theo path hoặc yêu cầu Claude review từng nhóm file |

Rollback nếu Claude đi sai hướng:

- Dùng `/rewind` hoặc `Esc + Esc` trong Claude Code để mở checkpoint menu cho thay đổi do Claude edit.
- Nếu thay đổi đến từ Bash command hoặc migration, checkpoint có thể không undo được; dùng `git diff -- path/to/file`, `git restore -- path/to/file` và rollback migration theo tool của repo.
- Không dùng `git restore .` nếu workspace có thay đổi của người khác.

## Bài 4 — Review & Reflection

Viết PR description dựa trên diff và test evidence:

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

Dựa trên diff và test output đã chạy. Test nào chưa chạy thì ghi rõ Not run và lý do.
```

Viết postmortem 10-15 dòng:

- Claude làm tốt gì?
- Claude sai hoặc suýt sai gì?
- Prompt nào giúp cải thiện chất lượng?
- Test nào bắt được bug?
- Guardrail nào nên thêm?
- Phần nào human bắt buộc review trước merge?
- Nếu làm lại, bạn sẽ chia phase khác không?

Prompt:

```text
Dựa trên toàn bộ session và diff feature task comments, viết postmortem ngắn. Không tô hồng. Nêu rõ Claude làm tốt gì, sai gì, test/guardrail nào cần thêm, và human phải review gì trước merge.
```

## Tiêu chí hoàn thành

- [ ] Feature `task comments` hoạt động end-to-end.
- [ ] API list/add/delete có validation và authorization.
- [ ] UI task detail có comments section đầy đủ state.
- [ ] Backend tests pass.
- [ ] UI tests pass.
- [ ] E2E pass hoặc ghi rõ gap.
- [ ] Diff được review thủ công.
- [ ] PR description có test evidence và rollback plan.
- [ ] Postmortem có guardrail cụ thể.
- [ ] Không có file ngoài phạm vi feature hoặc ngoài plan bị sửa không giải thích được.

## Gợi ý nếu bí

- Nếu không biết stack, yêu cầu Claude đọc `package.json`, routes, test files trước.
- Nếu test command fail vì thiếu env, yêu cầu Claude tìm test setup, không tự tạo config mới ngay.
- Nếu auth chưa có, dùng `x-user-id` trong helper/middleware test/dev, không rải trong controller.
- Nếu UI state rối, dùng refetch sau mutate trước, optimistic update sau.
- Nếu hiển thị comment rich text/Markdown, yêu cầu sanitize; mặc định dùng text rendering, không raw HTML.
- Nếu e2e chưa có, ghi gap và tăng integration/component test.
- Nếu Claude sửa quá nhiều file, dừng, `git diff --stat`, `/rewind`, chia lại backend-only.
- Nếu dùng docs search/MCP, yêu cầu Claude ưu tiên official docs cho Fastify/NestJS, React, Vitest/Jest, Playwright, PostgreSQL và Claude Code.

## Đáp án tham khảo hoặc expected result

Expected API:

```text
GET /api/tasks/:taskId/comments
- 200: [{ id, taskId, authorId, content, createdAt }]
- 403/404 nếu user không có quyền hoặc task không tồn tại

POST /api/tasks/:taskId/comments
- 201/200: comment mới
- 400/422 nếu content rỗng hoặc quá 1000 ký tự

DELETE /api/tasks/:taskId/comments/:commentId
- 204/200 khi author hoặc task owner xóa
- 403 nếu user không có quyền
- 404 nếu comment/task không tồn tại hoặc không thuộc task
```

Expected UI:

```text
Task detail hiển thị Comments.
User submit comment hợp lệ thì comment xuất hiện.
Content rỗng/quá dài hiển thị lỗi.
Author hoặc task owner thấy delete action.
User khác không thấy delete hoặc API từ chối.
Reload trang vẫn thấy comment đã tạo.
```

Expected PR:

```text
## Summary
- Added task comments API for list/create/delete.
- Added comments UI on task detail.
- Added validation and owner/author delete checks.

## Tests
- npm run test:backend
- npm run test:frontend
- npm run e2e

## Security / Authorization
- Create/list requires task access.
- Delete requires comment author or task owner.

## Rollback Plan
- Revert PR.
- Roll back migration if one was added.
```
