# Day 16 — GitHub workflow với Claude Code

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Tạo feature branch từ `main` mới nhất và giữ PR nhỏ, đúng phạm vi.
- Dùng Claude Code để đọc `git status`, `git diff`, staged diff và PR diff mà không giao quyền quyết định merge cho AI.
- Viết commit message rõ ràng theo Conventional Commits.
- Dùng Claude Code tạo Pull Request description trung thực với diff và test evidence.
- Dùng Claude Code review diff trước commit và trước merge, nhưng vẫn bắt buộc human review.
- Phân biệt manual Claude Code trong terminal, Claude Code GitHub Actions và Claude Code Code Review.
- Thiết kế guardrails cho protected branch hoặc GitHub rulesets: required PR, approving review, status checks, conversation resolution, block force push, block deletion.
- Biết rollback khi branch, commit, PR hoặc merge có vấn đề.

## 2. Bối cảnh thực tế

Khi `taskflow-ai` bắt đầu có backend, frontend, database migration, test và CI, làm trực tiếp trên `main` sẽ tạo nhiều rủi ro:

- Dễ đưa code lỗi vào branch chính.
- Khó biết thay đổi nào thuộc feature nào.
- PR quá lớn làm reviewer bỏ sót bug.
- Commit message mơ hồ làm rollback chậm.
- PR description nói quá so với test evidence.
- AI có thể tóm tắt sai diff nếu context thiếu hoặc diff quá rộng.

Workflow GitHub an toàn dùng branch riêng, Pull Request, automated checks và human review. Claude Code hữu ích ở các bước có tính phân tích và tổng hợp:

- Đọc `git status --short` và phân loại file.
- Tóm tắt `git diff --stat` trước khi review sâu.
- Review diff tìm bug, thiếu test, security risk, maintainability risk.
- Đề xuất commit message.
- Viết PR body theo template.
- So sánh PR description với diff để tránh nói quá.

Claude Code không phải người chịu trách nhiệm cuối cùng. Human vẫn phải đọc diff, hiểu requirement, kiểm tra test evidence, đánh giá risk và quyết định merge. Nếu team dùng Claude Code GitHub Actions hoặc Claude Code Code Review, đó vẫn là reviewer phụ trợ; không được thay thế required human approval.

Không nên dùng Claude Code để tự động push, approve hoặc merge khi:

- Diff có thay đổi security, auth, permission, billing hoặc migration.
- Working tree đang có file ngoài phạm vi task.
- Có secret hoặc production credential trong diff.
- CI fail, checks pending hoặc chưa có test evidence.
- PR description chưa khớp với diff thực tế.

## 3. Kiến thức nền

### Branch strategy

Với `taskflow-ai`, dùng workflow đơn giản:

```text
main
  -> feature/github-workflow-pr-template
```

Quy tắc:

- `main` chỉ chứa code đã hoàn thành, đã review và đã pass checks bắt buộc.
- Mỗi feature, fix hoặc tài liệu lớn dùng branch riêng.
- Branch nhỏ và tập trung vào một mục tiêu.
- Không gom docs, refactor, config và feature không liên quan vào cùng PR.
- Không push trực tiếp vào `main`.
- Không force push lên branch dùng chung. Nếu cần sửa history trên branch cá nhân, ưu tiên `--force-with-lease` thay vì `--force`.

Tên branch tốt:

```text
feature/github-workflow-pr-template
feature/task-priority-filter
fix/task-filter-empty-state
docs/pr-template
chore/update-ci-lint
```

Tên branch kém:

```text
test
update
new-code
final-final
```

### Commit message

Format khuyến nghị:

```text
type(scope): short description
```

Ví dụ:

```text
docs(github): add pull request template
feat(tasks): add priority filter
fix(api): reject empty task title
ci(test): run lint on pull requests
```

Commit message tốt giúp reviewer hiểu thay đổi và giúp rollback đúng commit. Không dùng message như `update`, `changes`, `fix stuff`.

### Pull Request description

PR description tốt trả lời:

- Thay đổi gì?
- Vì sao cần?
- Đã test gì?
- Rủi ro gì?
- Rollback thế nào?
- Có ảnh hưởng security, performance, cost, context hoặc maintainability không?

Template khuyến nghị cho `taskflow-ai`:

```md
## Summary

## Changes

## Test Plan

## Risk

## Rollback

## Security

## Performance / Cost / Context

## Maintainability
```

Không viết “All tests passed” nếu chưa chạy test. Nếu chỉ đổi markdown/template, có thể ghi `git diff --check` và nói rõ application tests không chạy vì documentation-only hoặc workflow-only.

### Claude Code trong GitHub workflow

Có ba cách dùng thường gặp:

| Cách dùng | Khi dùng | Guardrail |
| --- | --- | --- |
| Claude Code trong terminal | Developer muốn phân tích diff, viết PR body, review trước commit | Yêu cầu read-only khi review; developer tự chạy command và kiểm tra diff |
| Claude Code GitHub Actions | Team muốn gọi Claude từ issue/PR hoặc workflow CI | Dùng GitHub Secrets cho API key, giới hạn permission, review output trước merge |
| Claude Code Code Review | Team/Enterprise có bật review tự động hoặc manual bằng comment | Xem là reviewer phụ trợ; không coi finding của AI là approval hoặc block duy nhất |

Với khóa học này, thực hành chính dùng Claude Code trong terminal vì dễ kiểm soát quyền, dễ quan sát diff và không cần cài GitHub App. Claude Code GitHub Actions và Code Review là phần mở rộng cho team thật, cần kiểm tra docs chính thức trước khi bật vì permission, trigger, pricing và availability có thể thay đổi.

### Protected branch và rulesets

Protected branch hoặc GitHub rulesets giúp bảo vệ `main`:

- Require a pull request before merging.
- Require approving reviews.
- Dismiss stale approvals khi diff thay đổi, nếu team cần review lại sau push mới.
- Require status checks to pass before merging.
- Require branches to be up to date before merging, nếu team muốn giảm rủi ro merge trên base cũ.
- Require conversation resolution before merging.
- Require linear history nếu team chọn squash/rebase.
- Block force pushes.
- Restrict deletions hoặc không bật allow deletion cho branch chính.
- Restrict who can push hoặc bypass nếu repo quan trọng.

Lưu ý quan trọng: yêu cầu “Pull Request before merging” không tự động đồng nghĩa với “có approval”. Nếu cần human review, phải bật required approvals hoặc Code Owners riêng.

Mục tiêu của guardrails không phải làm chậm team, mà là giảm rủi ro merge nhầm, bỏ qua review hoặc mất lịch sử.

## 4. Step-by-step thực hành

Thực hành trên project `taskflow-ai`. Giả định repo nằm ở:

```text
taskflow-ai/
  backend/
  frontend/
  .github/
  docs/
```

Nếu repo của bạn đặt ở thư mục khác, thay `taskflow-ai` bằng path thực tế. Mỗi block lệnh bên dưới ghi rõ thư mục chạy, output kỳ vọng, rủi ro và rollback.

### Bước 1: Kiểm tra trạng thái repo

Thư mục chạy: root `taskflow-ai`.

```bash
git status --short
git branch --show-current
```

Lệnh làm gì:

- `git status --short` hiển thị file modified, added, deleted, untracked.
- `git branch --show-current` xác nhận branch hiện tại.

Output kỳ vọng nếu working tree sạch:

```text
main
```

`git status --short` sạch sẽ không in gì. Nếu có thay đổi:

```text
 M frontend/src/pages/tasks.tsx
?? notes.md
```

Rủi ro:

- Tạo branch khi working tree bẩn có thể kéo theo thay đổi ngoài phạm vi.
- File untracked như `.env`, log hoặc notes cá nhân có thể bị stage nhầm.

Prompt cho Claude Code:

```text
Hãy đọc output `git status --short` và branch hiện tại.
Phân loại:
- File nào thuộc task hiện tại
- File nào có vẻ ngoài phạm vi
- Có dấu hiệu secret, `.env`, log hoặc build artifact không
- Tôi có nên tạo branch/commit bây giờ không
- Nếu chưa nên, bước xử lý an toàn là gì

Không chỉnh file, không chạy git command thay tôi.
```

Rollback:

- Nếu chỉ mới phát hiện working tree bẩn, chưa cần rollback.
- Nếu đã stage nhầm file, dùng `git restore --staged <path>` sau khi chắc chắn file đó không thuộc commit.

### Bước 2: Đồng bộ `main`

Thư mục chạy: root `taskflow-ai`.

```bash
git checkout main
git pull origin main
```

Lệnh làm gì:

- `git checkout main` chuyển về branch chính.
- `git pull origin main` lấy commit mới nhất từ remote.

Output kỳ vọng:

```text
Already up to date.
```

Hoặc fast-forward nếu remote có commit mới.

Rủi ro:

- Nếu đang có local change chưa commit, `git checkout main` có thể bị chặn hoặc mang thay đổi sang `main`.
- Nếu `git pull` tạo conflict, không chọn đại `ours` hoặc `theirs`.

Rollback:

```bash
git merge --abort
```

Dùng khi `git pull` tạo merge conflict. Nếu team dùng pull rebase:

```bash
git rebase --abort
```

### Bước 3: Tạo feature branch

Thư mục chạy: root `taskflow-ai`.

```bash
git checkout -b feature/github-workflow-pr-template
git branch --show-current
```

Output kỳ vọng:

```text
feature/github-workflow-pr-template
```

Rủi ro:

- Branch name quá chung làm khó hiểu PR.
- Branch tạo từ `main` cũ tạo diff hoặc conflict không cần thiết.

Rollback nếu tạo nhầm và chưa commit:

```bash
git checkout main
git branch -D feature/github-workflow-pr-template
```

### Bước 4: Tạo thay đổi nhỏ trong `taskflow-ai`

Mục tiêu: thêm PR template và ghi chú workflow cho repo.

Thư mục chạy: root `taskflow-ai`.

```bash
mkdir -p .github docs
```

Output kỳ vọng: lệnh không in gì nếu tạo thư mục thành công.

Rủi ro:

- Lệnh chỉ tạo thư mục, rủi ro thấp.
- Trên Windows PowerShell, có thể dùng `New-Item -ItemType Directory -Force .github, docs`.

Rollback nếu tạo nhầm và thư mục còn rỗng:

```bash
rmdir .github docs
```

Prompt implement cho Claude Code:

```text
Trong repo taskflow-ai, hãy tạo hoặc cập nhật đúng 2 file:
- .github/pull_request_template.md
- docs/github-workflow.md

Nội dung cần có:
- PR template gồm Summary, Changes, Test Plan, Risk, Rollback, Security, Performance / Cost / Context, Maintainability
- docs/github-workflow.md mô tả branch strategy, commit message, PR review, protected branch guardrails
- Ghi rõ Claude Code review không thay thế human review
- Không thêm workflow tự động, không cài GitHub App, không sửa file khác

Sau khi sửa, dừng lại và tóm tắt file đã thay đổi. Không commit, không push.
```

Output kỳ vọng sau khi Claude sửa:

```text
 M .github/pull_request_template.md
 M docs/github-workflow.md
```

Rủi ro:

- Claude có thể sửa thêm file ngoài phạm vi.
- Claude có thể viết PR template nói quá như “All tests passed”.
- Claude có thể thêm workflow `.github/workflows/*` dù chưa được yêu cầu.

Rollback nếu Claude sửa sai:

```bash
git diff --name-only
git restore .github/pull_request_template.md docs/github-workflow.md
```

Chỉ chạy `git restore` khi chắc chắn muốn bỏ toàn bộ thay đổi local ở các file đó.

### Bước 5: Kiểm tra phạm vi diff

Thư mục chạy: root `taskflow-ai`.

```bash
git diff --stat
git diff --name-only
git diff --check
```

Lệnh làm gì:

- `git diff --stat` cho biết file nào đổi và mức độ đổi.
- `git diff --name-only` xác nhận phạm vi file.
- `git diff --check` tìm trailing whitespace hoặc whitespace error.

Output kỳ vọng:

```text
.github/pull_request_template.md
docs/github-workflow.md
```

`git diff --check` không in gì khi không có lỗi whitespace.

Rủi ro:

- Có file ngoài phạm vi như `.env`, lockfile hoặc generated file.
- Whitespace error trong markdown có thể làm CI hoặc review khó đọc.

Prompt review scope:

```text
Review output `git diff --stat`, `git diff --name-only`, và `git diff --check`.
Tập trung vào:
1. Có đúng 2 file dự kiến không
2. Có file secret, `.env`, generated file, lockfile hoặc build artifact không
3. Có whitespace error không
4. Có nên tiếp tục review diff sâu không

Không chỉnh file.
```

Rollback:

- Nếu có file ngoài phạm vi đã bị sửa nhầm, xem diff từng file trước khi restore.
- Nếu file chứa secret, không chỉ restore; rotate secret ngay vì secret có thể đã vào terminal/session/log.

### Bước 6: Dùng Claude Code review diff trước commit

Thư mục chạy: root `taskflow-ai`.

```bash
git diff
```

Prompt:

```text
Review git diff hiện tại ở chế độ read-only.

Tập trung vào:
1. PR template có đủ Summary, Changes, Test Plan, Risk, Rollback, Security, Performance / Cost / Context, Maintainability không
2. docs/github-workflow.md có đúng workflow cho taskflow-ai không
3. Có nhầm lẫn giữa Claude Code review và human review không
4. Có guardrail cho protected branch/rulesets không
5. Có command hoặc hướng dẫn nào nguy hiểm, thiếu rollback, hoặc gây hiểu nhầm không
6. Có security risk như secret, token, production data không

Output theo format:
## Findings
## Suggested fixes
## Questions

Không chỉnh file, không stage, không commit.
```

Output kỳ vọng:

```md
## Findings

No blocking findings.

## Suggested fixes

- ...

## Questions

- ...
```

Rủi ro:

- Claude có thể bỏ sót vấn đề nếu diff dài.
- Claude có thể đưa suggestion không phù hợp với team convention.

Rollback:

- Không cần rollback nếu Claude chỉ review read-only.
- Nếu Claude tự sửa dù prompt cấm, chạy lại `git diff --name-only` và xử lý như Bước 5.

### Bước 7: Chạy validation

Thư mục chạy: root `taskflow-ai`.

Nếu chỉ đổi markdown/template:

```bash
git diff --check
```

Output kỳ vọng: không in gì.

Nếu thay đổi code frontend/backend:

```bash
npm run lint
npm test
npm run typecheck
```

Output kỳ vọng:

```text
... no lint errors
... tests passed
... typecheck passed
```

Rủi ro:

- Chạy full test suite có thể tốn thời gian.
- Không chạy test nhưng ghi “passed” trong PR là sai sự thật.
- Nếu repo dùng workspace như `backend/` và `frontend/`, cần chạy đúng package manager script thực tế.

Rollback:

- Không rollback vì test fail; đọc lỗi trước.
- Nếu validation fail do thay đổi của bạn, sửa nhỏ nhất và chạy lại.

Prompt debug khi check fail:

```text
Đây là output validation fail.
Hãy giải thích:
- Nguyên nhân gốc có thể là gì
- File nào liên quan
- Fix nhỏ nhất là gì
- Test nào cần chạy lại

Không sửa file cho đến khi tôi xác nhận.
```

### Bước 8: Stage và commit

Thư mục chạy: root `taskflow-ai`.

```bash
git status --short
git add .github/pull_request_template.md docs/github-workflow.md
git diff --cached --stat
```

Lệnh làm gì:

- `git status --short` kiểm tra working tree trước khi stage.
- `git add ...` chỉ stage 2 file đúng phạm vi.
- `git diff --cached --stat` kiểm tra staged diff.

Output kỳ vọng:

```text
 .github/pull_request_template.md | ...
 docs/github-workflow.md          | ...
```

Prompt đề xuất commit message:

```text
Dựa trên staged diff, đề xuất 3 commit message theo Conventional Commits.
Ràng buộc:
- Dưới 72 ký tự nếu có thể
- Không dùng từ mơ hồ như update, changes, fix stuff
- Scope phù hợp với taskflow-ai GitHub workflow
- Không commit giúp tôi
```

Commit:

```bash
git commit -m "docs(github): add pull request workflow guide"
```

Output kỳ vọng:

```text
[feature/github-workflow-pr-template <sha>] docs(github): add pull request workflow guide
```

Rủi ro:

- Stage nhầm file ngoài phạm vi.
- Commit message nói sai nội dung.

Rollback commit nếu chưa push:

```bash
git reset --soft HEAD~1
```

Lệnh này bỏ commit cuối nhưng giữ thay đổi trong working tree. Không dùng `git reset --hard` trừ khi bạn chắc chắn muốn xóa thay đổi local.

### Bước 9: Push branch

Thư mục chạy: root `taskflow-ai`.

```bash
git push -u origin feature/github-workflow-pr-template
```

Output kỳ vọng:

```text
branch 'feature/github-workflow-pr-template' set up to track 'origin/feature/github-workflow-pr-template'
```

Rủi ro:

- Push lên remote sai nếu branch name nhầm.
- Nếu token/credential GitHub cấu hình sai, push fail.

Rollback nếu push nhầm branch:

```bash
git push origin --delete feature/github-workflow-pr-template
```

Chỉ xóa remote branch khi chắc chắn branch chưa được người khác dùng.

### Bước 10: Viết PR description bằng Claude Code

Thư mục chạy: root `taskflow-ai`.

```bash
git diff main...HEAD --stat
git log --oneline main..HEAD
```

Prompt:

```text
Viết Pull Request description cho branch hiện tại dựa trên diff `main...HEAD`.

Template bắt buộc:
## Summary
## Changes
## Test Plan
## Risk
## Rollback
## Security
## Performance / Cost / Context
## Maintainability

Ràng buộc:
- Không nói đã chạy test nếu chưa có bằng chứng
- Nếu chỉ đổi tài liệu/template, ghi rõ documentation-only/workflow-only
- Test Plan phải liệt kê command thực tế đã chạy hoặc ghi Not run kèm lý do
- Rollback phải cụ thể
- Không tự tạo claim về approval, CI pass hoặc human review
```

PR body tốt:

```md
## Summary

Adds a GitHub workflow guide and pull request template for `taskflow-ai`.

## Changes

- Adds `.github/pull_request_template.md` with required review sections.
- Adds `docs/github-workflow.md` covering branch strategy, commit messages, PR review, and protected branch guardrails.
- Documents that Claude Code review is advisory and does not replace human review.

## Test Plan

- [x] Ran `git diff --check`.
- [ ] Not run: application tests because this is documentation-only/workflow-only.

## Risk

Low. The change does not modify application runtime behavior.

## Rollback

Revert this PR, or remove `.github/pull_request_template.md` and `docs/github-workflow.md` in a follow-up PR.

## Security

No secrets, tokens, credentials, or production data added.

## Performance / Cost / Context

No runtime performance impact. The PR template may slightly increase review effort but improves review evidence.

## Maintainability

Keeps PR expectations explicit for future contributors.
```

Rủi ro:

- Claude có thể viết PR body quá lạc quan.
- Claude có thể nói test đã pass dù chỉ thấy command gợi ý.

Rollback:

- Sửa PR body trước khi tạo PR hoặc cập nhật PR description sau khi tạo.

### Bước 11: Tạo PR bằng GitHub CLI

Điều kiện: đã cài và đăng nhập GitHub CLI.

Thư mục chạy: root `taskflow-ai`.

```bash
gh auth status
```

Output kỳ vọng:

```text
Logged in to github.com account ...
```

Tạo PR draft:

```bash
gh pr create \
  --base main \
  --head feature/github-workflow-pr-template \
  --title "docs(github): add pull request workflow guide" \
  --body-file pr-body.md \
  --draft
```

Output kỳ vọng:

```text
https://github.com/owner/taskflow-ai/pull/123
```

Nếu cần reviewer:

```bash
gh pr create \
  --base main \
  --head feature/github-workflow-pr-template \
  --title "docs(github): add pull request workflow guide" \
  --body-file pr-body.md \
  --reviewer username
```

Rủi ro:

- `pr-body.md` có thể chứa text nháp chưa review.
- Tạo PR không draft khi chưa sẵn sàng có thể kích hoạt CI hoặc auto review tốn cost.
- Nếu repo có Claude Code GitHub Actions hoặc Code Review bật auto trigger, mỗi PR/push có thể tạo chi phí và comment tự động.

Rollback:

```bash
gh pr close --delete-branch
```

Chỉ dùng khi PR tạo nhầm và branch không còn cần thiết.

### Bước 12: Review PR trước merge

Thư mục chạy: root `taskflow-ai`.

```bash
gh pr view
gh pr diff
gh pr checks
```

Lệnh làm gì:

- `gh pr view` xem metadata, reviewer, status.
- `gh pr diff` xem diff thực tế trên PR.
- `gh pr checks` xem CI/status checks.

Output kỳ vọng:

```text
All checks were successful
```

Hoặc danh sách check đang pass/fail/pending.

Prompt review trước merge:

```text
Review PR diff hiện tại trước merge ở chế độ read-only.

Tập trung vào:
- Bug hoặc behavior regression
- Thiếu test hoặc validation
- Security risk
- Maintainability risk
- Performance/cost/context impact
- File ngoài phạm vi
- PR description có trung thực với diff không
- Rủi ro rollback
- Protected branch guardrails có bị bypass không

Output bắt buộc:
## Findings
## Questions
## Recommendation

Recommendation phải là một trong ba:
- Ready after human approval
- Needs changes before merge
- Blocked

Không merge, không push, không sửa file.
```

Chỉ merge khi:

- Human reviewer approve.
- Required checks pass.
- Branch không conflict.
- PR body trung thực với diff và test evidence.
- Không có secret hoặc production data trong diff.
- Protected branch/ruleset không bị bypass.

Rủi ro:

- Claude nói “Ready” nhưng chưa thấy business context hoặc reviewer expectation.
- Checks có thể pass nhưng manual test hoặc security review vẫn thiếu.

Rollback sau merge:

```bash
git checkout main
git pull origin main
git checkout -b revert/github-workflow-pr-template
git revert <merge_or_squash_commit_sha>
git push -u origin revert/github-workflow-pr-template
gh pr create --base main --head revert/github-workflow-pr-template --title "revert: GitHub workflow guide" --body "Reverts the GitHub workflow guide change."
```

Nếu `main` được bảo vệ, dùng revert PR thay vì push trực tiếp.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase và Git state

```text
Hãy khảo sát repo taskflow-ai ở chế độ read-only.
Đọc:
- git status --short
- git branch --show-current
- git diff --stat
- package scripts hoặc README nếu cần biết validation command

Trả lời:
- Repo đang ở branch nào
- Working tree sạch hay bẩn
- File nào thuộc phạm vi task GitHub workflow
- File nào có vẻ ngoài phạm vi hoặc có rủi ro secret/generated artifact
- Command validation phù hợp nhất là gì

Không chỉnh file, không stage, không commit, không push.
```

### Prompt lập plan

```text
Lập plan cho PR nhỏ thêm GitHub workflow guide vào taskflow-ai.

Ràng buộc:
- Chỉ sửa `.github/pull_request_template.md` và `docs/github-workflow.md`
- Không thêm GitHub Actions workflow
- Không cài GitHub App
- Phải có branch strategy, commit message, PR description, Claude Code review advisory, protected branch/rulesets, rollback
- Mỗi bước nêu command, thư mục chạy, output kỳ vọng, rủi ro

Chỉ lập plan, chưa implement.
```

### Prompt implement

```text
Implement plan đã thống nhất.

Chỉ được tạo/sửa:
- .github/pull_request_template.md
- docs/github-workflow.md

Nội dung phải cụ thể cho taskflow-ai, có security, maintainability, performance/cost/context, rollback.
Không stage, không commit, không push.
Sau khi sửa, chạy `git diff --name-only` và báo cáo nếu có file ngoài phạm vi.
```

### Prompt review

```text
Review git diff hiện tại trước commit.
Tìm bug, regression, thiếu test, security issue, maintainability issue, performance/cost/context issue, command nguy hiểm, claim không có bằng chứng.
Chỉ ra file, vấn đề, failure mode, severity và suggested fix.
Không chỉnh file.
```

### Prompt viết test/validation và PR evidence

```text
Dựa trên staged diff, hãy đề xuất validation tối thiểu trước PR.

Yêu cầu:
- Nếu documentation-only, nêu vì sao `git diff --check` là đủ và app tests có thể Not run
- Nếu có code/runtime change, nêu lint/test/typecheck cụ thể theo script trong repo
- Viết Test Plan trung thực cho PR description
- Đề xuất 3 commit message theo Conventional Commits

Không chạy command, không commit.
```

## 6. Trade-offs

| Lựa chọn | Ưu điểm | Nhược điểm | Khi dùng |
| --- | --- | --- | --- |
| Branch nhỏ | Dễ review, dễ test, dễ rollback | Nhiều PR hơn | Mặc định cho team |
| Branch lớn | Ít PR hơn | Review khó, conflict nhiều, Claude dễ bỏ sót | Prototype tạm hoặc spike |
| Squash merge | Lịch sử `main` gọn, revert một commit dễ | Mất commit nhỏ trên branch | Feature nhỏ, course repo |
| Merge commit | Giữ lịch sử branch | Lịch sử phức tạp hơn | Team cần audit chi tiết |
| Rebase merge | Linear history | Cần Git discipline | Team quen rebase |
| Manual Claude review | Rẻ hơn, kiểm soát context tốt | Cần developer tự chạy prompt | Cá nhân/khóa học |
| Claude Code GitHub Actions | Tự động hóa issue/PR workflow | Cần secrets, permission, chi phí CI/API | Team đã có guardrails |
| Claude Code Code Review | Feedback nhanh trên PR | Availability/cost thay đổi, không thay human approval | Team muốn second reviewer tự động |

Claude review nhanh và tốt cho checklist, nhưng human review hiểu business context, release timing và risk appetite. Không dùng Claude để auto-approve hoặc auto-merge.

Protected branch/rulesets chặt giảm rủi ro production nhưng có thể làm prototype chậm hơn. Với repo học cá nhân, tối thiểu nên yêu cầu PR và block force push/delete trên `main`. Với repo team, thêm required approvals, required checks, conversation resolution và Code Owners cho khu vực nhạy cảm.

## 7. Best practices

- Luôn chạy `git status --short` trước branch, commit, push, merge.
- Tạo branch từ `main` mới nhất.
- Đặt tên branch rõ nghĩa và gắn với một mục tiêu.
- Giữ diff nhỏ, tập trung.
- Review diff bằng mắt trước khi hỏi Claude.
- Dùng Claude Code review read-only trước commit và trước merge.
- Không để Claude tự push, approve hoặc merge nếu human chưa đọc diff.
- Không commit secret, token, `.env`, log chứa credential hoặc production data.
- PR description phải trung thực với test evidence.
- Với UI change, thêm screenshot hoặc manual test notes nếu phù hợp.
- Với logic change, có test hoặc test plan rõ.
- Nếu conflict, resolve có chủ đích; không chọn đại `ours`/`theirs`.
- Sau merge, delete branch đã merge nếu team không cần giữ.
- Không bypass protected branch trừ incident rõ ràng và có audit note.
- Nếu dùng Claude Code GitHub Actions, lưu API key trong GitHub Secrets, giới hạn workflow permissions và review output trước merge.
- Nếu dùng Claude Code settings cho repo, deny đọc file nhạy cảm.

Ví dụ `.claude/settings.json` cho repo có secret local:

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ],
    "ask": [
      "Bash(git push *)",
      "Bash(gh pr merge *)"
    ]
  }
}
```

Nếu lỡ commit secret:

1. Dừng push/merge.
2. Rotate secret ngay.
3. Xóa secret khỏi repo.
4. Audit log, CI output và nơi secret có thể đã lộ.
5. Thêm `.gitignore`, secret scanning hoặc pre-commit guard.

Rollback chưa đủ cho secret leakage vì secret có thể đã bị ghi vào remote, CI log hoặc AI session.

## 8. Performance / cost / context

Claude Code review diff lớn có thể tốn context và bỏ sót chi tiết. Tối ưu bằng cách review theo lớp:

```bash
git diff --stat
git diff --name-only main...HEAD
git diff -- path/to/file
git diff --check
```

Prompt tiết kiệm context:

```text
Trước tiên chỉ đọc `git diff --stat` và `git diff --name-only main...HEAD`.
Cho biết file nào cần review sâu, file nào có thể bỏ qua vì generated hoặc ít rủi ro.
Sau đó chờ tôi chọn file để review chi tiết.
```

Không paste lockfile, generated file hoặc build artifact dài nếu không cần. Nếu có secret trong diff, xem là blocking issue và rotate secret.

Cost cần chú ý:

- Claude Code trong terminal tốn token theo lượng context, diff và số vòng sửa.
- Claude Code GitHub Actions tốn GitHub Actions minutes và API/subscription usage tùy cấu hình.
- Claude Code Code Review có thể chạy theo trigger PR/push/manual; review mỗi push trên PR lớn sẽ tốn hơn.
- `@claude review once` phù hợp khi chỉ cần second opinion một lần, còn auto review every push phù hợp với repo có guardrails và budget rõ.

Cách giảm cost/context:

- Chia PR nhỏ.
- Review `--stat` trước khi review full diff.
- Không yêu cầu Claude đọc toàn repo nếu chỉ cần 2 file.
- Dùng `CLAUDE.md` ngắn gọn cho quy tắc ổn định, không nhồi tutorial dài.
- Dùng `REVIEW.md` nếu team có Claude Code Code Review và muốn rule review riêng, nhưng giữ file này ngắn.

Rollback sau merge bằng squash commit:

```bash
git revert <squash_commit_sha>
```

Nếu protected branch không cho push trực tiếp, tạo revert PR.

## 9. Checklist cuối bài

- [ ] Tôi hiểu vì sao không làm trực tiếp trên `main`.
- [ ] Tôi tạo được feature branch từ `main` mới nhất.
- [ ] Tôi dùng `git status --short` trước commit.
- [ ] Tôi xem `git diff --stat`, `git diff --name-only`, `git diff --check`.
- [ ] Tôi dùng Claude Code review diff ở chế độ read-only.
- [ ] Tôi chạy validation phù hợp và không ghi test evidence giả.
- [ ] Tôi viết commit message rõ theo Conventional Commits.
- [ ] Tôi push branch lên remote đúng tên.
- [ ] Tôi dùng Claude Code viết PR description có Summary, Changes, Test Plan, Risk, Rollback, Security, Performance / Cost / Context, Maintainability.
- [ ] Tôi biết dùng `gh pr create`, `gh pr diff`, `gh pr checks`, `gh pr view`.
- [ ] Tôi hiểu Claude review không thay thế human review.
- [ ] Tôi biết protected branch/rulesets nên chặn gì.
- [ ] Tôi biết rollback branch, commit, PR và merge có vấn đề.
- [ ] Tôi biết secret leakage cần rotate secret, không chỉ revert.

## 10. Bài tập

Bài cơ bản: trong `taskflow-ai`, tạo feature branch `feature/github-workflow-pr-template` từ `main` mới nhất và xác nhận bằng `git branch --show-current`.

Bài thực tế: thêm `.github/pull_request_template.md` và `docs/github-workflow.md`, chạy `git diff --check`, commit bằng message rõ, viết PR description bằng Claude Code.

Bài nâng cao: dùng `gh pr diff` và `gh pr checks`, sau đó yêu cầu Claude review PR read-only trước merge. Nếu team có Claude Code Code Review, so sánh finding của Claude trên PR với review thủ công và ghi điểm AI bỏ sót.

Bài reflection: viết 10-15 dòng giải thích Claude Code giúp gì trong GitHub workflow, điều gì Claude không được tự quyết, protected branch/rulesets cần guardrail nào, và khi nào nên dùng revert PR.
