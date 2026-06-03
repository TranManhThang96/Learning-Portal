# Exercise — Day 16

## Bài 1 — Cơ bản

Mục tiêu: tạo feature branch đúng cách từ `main` mới nhất trong `taskflow-ai`.

Thư mục chạy: root `taskflow-ai`.

```bash
git status --short
git branch --show-current
git checkout main
git pull origin main
git checkout -b feature/github-workflow-pr-template
git branch --show-current
```

Output kỳ vọng:

```text
feature/github-workflow-pr-template
```

`git status --short` nên không in gì trước khi tạo branch. Nếu có output như:

```text
 M frontend/src/pages/tasks.tsx
?? notes.md
```

chưa nên tạo branch ngay. Hỏi Claude:

```text
Hãy đọc output `git status --short` của tôi và phân loại:
- Thay đổi nào thuộc task hiện tại
- Thay đổi nào ngoài phạm vi
- Có file secret, `.env`, log, build artifact hoặc generated file không
- Tôi có nên tạo branch mới bây giờ không
- Nếu chưa nên, đề xuất bước xử lý an toàn

Không chỉnh file, không stage, không commit.
```

Rủi ro:

- Branch mới có thể mang theo thay đổi ngoài phạm vi nếu working tree bẩn.
- `git pull` có thể tạo conflict nếu local `main` lệch remote.

Rollback nếu tạo nhầm branch nhưng chưa commit:

```bash
git checkout main
git branch -D feature/github-workflow-pr-template
```

Rollback nếu `git pull` tạo conflict:

```bash
git merge --abort
```

Nếu team dùng pull rebase:

```bash
git rebase --abort
```

## Bài 2 — Thực tế

Mục tiêu: dùng Claude Code tạo thay đổi nhỏ, kiểm tra diff, viết commit message và Pull Request description dựa trên diff thật.

Yêu cầu:

1. Trong `taskflow-ai`, tạo hoặc cập nhật đúng 2 file:
   - `.github/pull_request_template.md`
   - `docs/github-workflow.md`
2. PR template phải có: Summary, Changes, Test Plan, Risk, Rollback, Security, Performance / Cost / Context, Maintainability.
3. Workflow guide phải có: branch strategy, commit message, PR description, Claude Code read-only review, human review, protected branch/rulesets, rollback.
4. Không thêm GitHub Actions workflow trong bài này.
5. Không commit secret, `.env`, token hoặc production data.

Thư mục chạy: root `taskflow-ai`.

```bash
mkdir -p .github docs
```

Trên Windows PowerShell có thể dùng:

```powershell
New-Item -ItemType Directory -Force .github, docs
```

Prompt implement:

```text
Trong repo taskflow-ai, hãy tạo hoặc cập nhật đúng 2 file:
- .github/pull_request_template.md
- docs/github-workflow.md

Nội dung cần có:
- PR template gồm Summary, Changes, Test Plan, Risk, Rollback, Security, Performance / Cost / Context, Maintainability
- docs/github-workflow.md mô tả branch strategy, commit message, PR description, Claude Code review advisory, human review, protected branch/rulesets, rollback
- Ghi rõ Claude Code review không thay thế human review
- Không thêm workflow tự động, không cài GitHub App, không sửa file khác

Sau khi sửa, dừng lại và tóm tắt file đã thay đổi. Không stage, không commit, không push.
```

Kiểm tra diff:

```bash
git diff --stat
git diff --name-only
git diff --check
```

Output kỳ vọng:

```text
.github/pull_request_template.md
docs/github-workflow.md
```

`git diff --check` không in gì nếu không có whitespace error.

Prompt review trước commit:

```text
Review git diff hiện tại ở chế độ read-only.

Tập trung vào:
- Nội dung có đúng mục tiêu GitHub workflow cho taskflow-ai không
- PR template có đủ sections không
- Có nhầm Claude Code review thành human approval không
- Có thiếu risk, rollback, security, maintainability, performance/cost/context không
- Có command nào nguy hiểm hoặc thiếu thư mục chạy/output kỳ vọng không
- Có file ngoài phạm vi không

Trả về Findings, Suggested fixes, Questions.
Không chỉnh file, không stage, không commit.
```

Validation:

```bash
git diff --check
```

Nếu bài của bạn có đổi code runtime ngoài yêu cầu, phải chạy thêm script phù hợp của repo, ví dụ:

```bash
npm run lint
npm test
npm run typecheck
```

Stage đúng file:

```bash
git status --short
git add .github/pull_request_template.md docs/github-workflow.md
git diff --cached --stat
```

Prompt commit message:

```text
Dựa trên staged diff, đề xuất 3 commit message theo Conventional Commits.
Ràng buộc:
- Dưới 72 ký tự nếu có thể
- Không dùng từ mơ hồ như update, changes, fix stuff
- Không commit giúp tôi
```

Commit:

```bash
git commit -m "docs(github): add pull request workflow guide"
```

Push:

```bash
git push -u origin feature/github-workflow-pr-template
```

Prompt PR body:

```text
Dựa trên diff `main...HEAD`, hãy viết PR description cho GitHub.

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
- Ngắn gọn, cụ thể
- Không nói đã chạy test nếu chưa có bằng chứng
- Nếu chỉ đổi tài liệu/template, ghi rõ documentation-only/workflow-only
- Có command validation cụ thể
- Không tự claim CI pass hoặc human review approve
```

Tạo PR draft bằng GitHub CLI:

```bash
gh auth status
gh pr create \
  --base main \
  --head feature/github-workflow-pr-template \
  --title "docs(github): add pull request workflow guide" \
  --body-file pr-body.md \
  --draft
```

Expected PR body:

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

- Claude có thể sửa file ngoài phạm vi.
- `git add .` có thể stage nhầm file khác; bài này yêu cầu stage exact files.
- PR draft có thể kích hoạt automation nếu repo đã bật GitHub Actions hoặc Claude Code Code Review.

Rollback:

```bash
git reset --soft HEAD~1
```

Dùng nếu đã commit nhưng chưa push và muốn sửa lại commit.

```bash
gh pr close --delete-branch
```

Dùng nếu PR tạo nhầm và branch không còn cần thiết.

## Bài 3 — Nâng cao

Mục tiêu: dùng Claude Code review PR diff trước merge nhưng human vẫn là owner cuối.

Nếu đã có PR:

```bash
gh pr view
gh pr diff
gh pr checks
```

Nếu chưa có PR:

```bash
git diff main...HEAD --stat
git diff main...HEAD
```

Prompt:

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
- Có dấu hiệu bypass protected branch/rulesets không

Output bắt buộc:
## Findings
- Severity, file, vấn đề, lý do

## Questions
- Câu hỏi cần hỏi author hoặc reviewer

## Recommendation
Chọn một:
- Ready after human approval
- Needs changes before merge
- Blocked

Không merge, không push, không sửa file.
```

Expected nếu PR ổn:

```md
## Findings

No blocking findings.

## Questions

- Has a human reviewer checked that the PR template matches the team's actual workflow?

## Recommendation

Ready after human approval.
```

Expected nếu PR có vấn đề:

```md
## Findings

- Medium, `.github/pull_request_template.md`: Test Plan text says all tests passed by default. This can create false evidence when no tests were run. Change it to ask authors to list real commands or mark Not run with a reason.

## Questions

- Should the PR remain draft until the template is corrected?

## Recommendation

Needs changes before merge.
```

Nếu team có Claude Code Code Review hoặc Claude Code GitHub Actions:

1. Kiểm tra trigger có phải manual, PR open hay every push.
2. Kiểm tra repo có lưu API key bằng GitHub Secrets, không hardcode trong workflow.
3. So sánh finding tự động với review thủ công.
4. Ghi lại ít nhất một điểm AI giúp ích và một điểm human vẫn phải quyết định.

Prompt so sánh:

```text
So sánh review tự động của Claude trên PR với review thủ công của tôi.
Chỉ ra:
- Finding nào hữu ích
- Finding nào là false positive hoặc thiếu context
- Điểm nào AI bỏ sót
- Việc merge có cần human approval và checks pass không

Không sửa file, không merge.
```

Rollback nếu PR đã merge và cần revert:

```bash
git checkout main
git pull origin main
git checkout -b revert/github-workflow-pr-template
git revert <merge_or_squash_commit_sha>
git push -u origin revert/github-workflow-pr-template
gh pr create --base main --head revert/github-workflow-pr-template --title "revert: GitHub workflow guide" --body "Reverts the GitHub workflow guide change."
```

Rủi ro:

- Revert PR cũng cần review nếu `main` được bảo vệ.
- Nếu merge đã lộ secret, revert không đủ; phải rotate secret.

## Bài 4 — Review & Reflection

Viết reflection 10-15 dòng:

1. Vì sao không nên làm trực tiếp trên `main`?
2. Claude Code giúp ích ở bước nào trong workflow?
3. Claude Code không nên được phép làm gì nếu chưa có human review?
4. Protected branch hoặc rulesets nên chặn những hành động nào?
5. Nếu Claude nói `Ready after human approval`, bạn còn cần kiểm tra gì?
6. Nếu PR đã merge sai, khi nào dùng revert PR?
7. Nếu diff có secret, vì sao rollback không đủ?

Prompt tự kiểm tra:

```text
Đọc reflection của tôi và đánh giá:
- Tôi có hiểu đúng vai trò advisory của Claude Code không?
- Có chỗ nào đang giao quá nhiều quyền quyết định cho Claude không?
- Có thiếu protected branch/rulesets, human review, checks, rollback hoặc secret rotation không?
Trả feedback ngắn gọn, không viết lại toàn bộ.
```

Expected reflection:

```text
Không nên làm trực tiếp trên main vì main nên đại diện cho trạng thái ổn định của project. Feature branch giúp cô lập thay đổi, review dễ hơn và rollback rõ hơn. Claude Code hữu ích khi tóm tắt git status, đề xuất commit message, viết PR description và review diff trước commit hoặc trước merge. Tuy nhiên Claude không nên tự push, approve hoặc merge nếu human chưa đọc diff và checks chưa pass. Protected branch hoặc rulesets nên yêu cầu PR, approving review, required status checks, conversation resolution, chặn force push và chặn delete branch. Nếu Claude nói Ready after human approval, tôi vẫn phải kiểm tra PR diff, CI checks, test plan, reviewer approval, security risk và PR description có đúng với thay đổi thật không. Nếu PR đã merge sai, tôi nên tạo revert PR để giữ audit trail. Nếu diff có secret, revert không đủ vì secret có thể đã lộ trong remote, CI log hoặc session; cần rotate secret ngay.
```

## Tiêu chí hoàn thành

- [ ] Tạo được feature branch từ `main` mới nhất trong `taskflow-ai`.
- [ ] Biết kiểm tra repo bằng `git status --short`.
- [ ] Biết dùng `git diff --stat`, `git diff --name-only`, `git diff`, `git diff --check`.
- [ ] Chỉ stage đúng `.github/pull_request_template.md` và `docs/github-workflow.md`.
- [ ] Có commit message rõ theo Conventional Commits.
- [ ] Có PR description đủ Summary, Changes, Test Plan, Risk, Rollback, Security, Performance / Cost / Context, Maintainability.
- [ ] Biết dùng `gh auth status`, `gh pr create`, `gh pr diff`, `gh pr checks`, `gh pr view`.
- [ ] Có prompt Claude Code review diff read-only.
- [ ] Hiểu Claude review không thay thế human review.
- [ ] Biết protected branch/rulesets nên có guardrails nào.
- [ ] Biết rollback khi branch, commit, PR hoặc merge có vấn đề.
- [ ] Biết secret leakage cần rotate secret, không chỉ revert.

## Gợi ý nếu bí

Không biết repo đang ở trạng thái nào:

```bash
git status --short
git branch --show-current
git log --oneline -5
```

Không biết diff có gì:

```bash
git diff --stat
git diff --name-only
git diff
```

Không biết command validation:

```bash
git diff --check
```

Nếu có code change:

```bash
npm run lint
npm test
npm run typecheck
```

Không biết commit message:

```text
Dựa trên staged diff, đề xuất 3 commit message theo Conventional Commits. Không commit giúp tôi.
```

Không biết PR body:

```text
Viết PR description dựa trên diff hiện tại, có Summary, Changes, Test Plan, Risk, Rollback, Security, Performance / Cost / Context, Maintainability. Không nói đã chạy test nếu chưa có bằng chứng.
```

Checks fail:

```bash
gh pr checks
```

Sau đó:

```text
Đây là output checks fail. Hãy giải thích nguyên nhân có thể, command local nên chạy, và hướng fix nhỏ nhất. Không sửa file.
```

File ngoài phạm vi:

```bash
git diff --name-only
git restore --staged path/to/file
```

Chỉ dùng lệnh sau nếu chắc chắn muốn bỏ thay đổi local ở file đó:

```bash
git restore path/to/file
```

## Đáp án tham khảo hoặc expected result

Branch:

```bash
git branch --show-current
```

Expected:

```text
feature/github-workflow-pr-template
```

Changed files:

```text
.github/pull_request_template.md
docs/github-workflow.md
```

Commit message tốt:

```text
docs(github): add pull request workflow guide
```

PR Test Plan tốt cho documentation/workflow-only:

```md
## Test Plan

- [x] Ran `git diff --check`.
- [ ] Not run: application tests because this is documentation-only/workflow-only.
```

Protected branch hoặc rulesets expected configuration:

```text
Require a pull request before merging: enabled
Require approvals: enabled
Require status checks to pass: enabled
Require conversation resolution before merging: enabled
Block force pushes: enabled
Restrict deletions / do not allow deletion of main: enabled
```

Với team nghiêm túc hơn:

```text
Dismiss stale pull request approvals when new commits are pushed: enabled
Require branches to be up to date before merging: enabled
Require linear history: enabled
Require Code Owners review for sensitive paths: enabled
Restrict who can bypass rules: enabled
```

Claude Code review expected recommendation:

```md
## Recommendation

Ready after human approval.
```

Không chấp nhận recommendation dạng:

```md
Approved. Merge now.
```

Lý do: Claude Code không phải human approver cuối và không được tự quyết merge.
