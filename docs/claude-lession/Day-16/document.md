# Document — Day 16

## Tóm tắt kiến thức

GitHub workflow an toàn cho `taskflow-ai`:

```text
latest main
  -> feature branch
  -> focused change
  -> local validation
  -> Claude Code read-only review
  -> commit
  -> push
  -> Pull Request
  -> checks
  -> Claude Code PR diff review
  -> human review
  -> merge
  -> delete branch or create revert PR if needed
```

Nguyên tắc cốt lõi:

- `main` là branch ổn định, được bảo vệ bằng protected branch hoặc rulesets.
- Mỗi thay đổi nằm trong branch riêng, nhỏ và đúng phạm vi.
- Commit message rõ, dễ tìm và dễ rollback.
- PR description phải trung thực với diff và test evidence.
- Claude Code hỗ trợ review, tóm tắt, viết PR body và kiểm tra checklist; không thay thế human review.
- Claude Code GitHub Actions hoặc Claude Code Code Review là automation phụ trợ, cần kiểm soát secrets, permission, trigger và cost.
- Protected branch/rulesets nên yêu cầu PR, approving review, status checks, conversation resolution, block force push và block deletion.

Command cốt lõi, chạy ở root `taskflow-ai`:

```bash
git status --short
git checkout main
git pull origin main
git checkout -b feature/github-workflow-pr-template
git diff --stat
git diff --name-only
git diff --check
git add .github/pull_request_template.md docs/github-workflow.md
git diff --cached --stat
git commit -m "docs(github): add pull request workflow guide"
git push -u origin feature/github-workflow-pr-template
gh pr create --base main --head feature/github-workflow-pr-template --title "..." --body-file pr-body.md --draft
gh pr view
gh pr diff
gh pr checks
```

Expected output quan trọng:

- `git status --short` không in gì khi working tree sạch.
- `git branch --show-current` in đúng branch hiện tại.
- `git diff --check` không in gì khi không có whitespace error.
- `gh pr create` trả về URL PR.
- `gh pr checks` hiển thị trạng thái pass/fail/pending của checks.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Start
  -> git status --short
  -> classify existing changes
  -> checkout main
  -> pull origin main
  -> create feature branch
  -> implement focused change
  -> git diff --stat + git diff --name-only + git diff --check
  -> Claude read-only review
  -> run validation
  -> stage exact files
  -> inspect staged diff
  -> commit
  -> push branch
  -> Claude writes PR description
  -> create draft PR
  -> gh pr checks + gh pr diff
  -> Claude read-only PR review
  -> human review
  -> merge only if approved and checks pass
  -> delete branch or revert via PR if needed
```

Mind map:

```text
GitHub workflow với Claude Code
├── Branch strategy
│   ├── main ổn định
│   ├── feature branch nhỏ
│   ├── branch name rõ nghĩa
│   └── không push trực tiếp vào main
├── Commit
│   ├── Conventional Commits
│   ├── staged diff trước commit
│   └── message dễ rollback
├── Pull Request
│   ├── Summary
│   ├── Changes
│   ├── Test Plan
│   ├── Risk
│   ├── Rollback
│   ├── Security
│   ├── Performance / Cost / Context
│   └── Maintainability
├── Claude Code
│   ├── summarize git status
│   ├── review diff read-only
│   ├── write PR body
│   ├── compare PR body with diff
│   └── không approve hoặc merge thay human
└── Guardrails
    ├── require PR
    ├── required approvals
    ├── required checks
    ├── conversation resolution
    ├── block force push
    └── restrict deletion
```

## Bảng so sánh

| Tiêu chí | Làm trực tiếp trên `main` | Feature branch + PR |
| --- | --- | --- |
| Tốc độ ban đầu | Nhanh | Chậm hơn một chút |
| Rủi ro hỏng branch chính | Cao | Thấp hơn |
| Review | Khó hoặc không có | Rõ qua PR diff |
| Test evidence | Dễ bị bỏ qua | Gắn vào PR |
| Rollback | Khó nếu nhiều thay đổi lẫn nhau | Dễ hơn qua revert commit/PR |
| Phù hợp team | Không | Có |
| Phù hợp production | Không | Có |

| Tiêu chí | Claude Code review | Human review |
| --- | --- | --- |
| Tốc độ | Nhanh | Chậm hơn |
| Checklist consistency | Tốt | Tùy reviewer |
| Hiểu business context | Giới hạn | Tốt |
| Đánh giá release risk | Giới hạn | Tốt hơn |
| Chịu trách nhiệm approval | Không | Có |
| Làm gate cuối | Không | Có |

| Cách dùng Claude | Ưu điểm | Rủi ro | Khuyến nghị |
| --- | --- | --- | --- |
| Terminal read-only review | Dễ kiểm soát, ít automation | Phụ thuộc prompt và context | Mặc định cho khóa học |
| GitHub Actions | Có thể tự động trên issue/PR | Cần secrets, permission, CI/API cost | Chỉ bật khi team có guardrails |
| Code Review | Feedback inline trên PR | Availability/cost/trigger thay đổi, finding không thay approval | Dùng như reviewer phụ trợ |

| Guardrail | Tác dụng | Khuyến nghị |
| --- | --- | --- |
| Require PR before merging | Chặn push/merge thiếu PR vào branch chính | Nên bật |
| Require approving reviews | Bắt buộc human review | Nên bật với team |
| Dismiss stale approvals | Review lại khi diff thay đổi | Bật cho repo quan trọng |
| Require status checks | Chỉ merge khi CI/checks pass | Nên bật |
| Require conversation resolution | Chặn merge khi thread chưa xử lý | Nên bật |
| Require linear history | Lịch sử dễ đọc, revert dễ hơn | Tùy team |
| Block force pushes | Tránh mất lịch sử | Nên bật |
| Restrict deletions | Tránh xóa nhầm branch chính | Nên bật |

## Lỗi thường gặp

1. Tạo branch khi working tree bẩn

`git status --short` có file cũ, rồi branch mới mang theo thay đổi ngoài phạm vi.

2. Branch tạo từ `main` cũ

Không `git pull origin main` trước khi tạo branch, dẫn tới conflict muộn hoặc PR diff lạ.

3. Stage quá rộng

Dùng `git add .` làm stage cả `.env`, notes cá nhân, generated files hoặc thay đổi của task khác.

4. Commit message mơ hồ

`update`, `fix`, `changes` không giúp review hoặc rollback.

5. PR description nói quá

Ghi “All tests passed” dù chưa chạy test. Cách đúng: ghi command đã chạy hoặc `Not run` kèm lý do.

6. Claude tự tin nhưng thiếu context

Claude không biết toàn bộ business intent, history hoặc production impact. Human vẫn đọc diff.

7. Merge khi checks pending/fail

`gh pr checks` còn fail hoặc pending thì chưa merge.

8. Force push sai

Dùng `--force` làm mất commit người khác. Nếu thật cần trên branch cá nhân, dùng `--force-with-lease`.

9. Nhầm “required PR” với “required approval”

Yêu cầu PR không tự động bắt buộc có approving review. Cần bật required reviews riêng.

10. Lỡ đưa secret vào diff

Không chỉ revert. Phải rotate secret và audit nơi secret có thể đã lộ.

## Cách debug

PR diff có file lạ:

```bash
git diff --name-only main...HEAD
git log --oneline main..HEAD
```

Unstage file không liên quan:

```bash
git restore --staged path/to/file
```

Bỏ thay đổi local ở file không liên quan:

```bash
git restore path/to/file
```

Chỉ dùng `git restore path/to/file` khi chắc chắn muốn bỏ thay đổi local ở file đó.

PR conflict:

```bash
git fetch origin
git diff HEAD...origin/main --stat
git rebase origin/main
```

Nếu rebase sai:

```bash
git rebase --abort
```

Checks fail:

```bash
gh pr checks
gh pr view
npm run lint
npm test
npm run build
```

Prompt debug:

```text
Checks đang fail. Dựa trên log lỗi này, hãy giải thích nguyên nhân gốc, file liên quan, và đề xuất fix nhỏ nhất. Không sửa file cho đến khi tôi xác nhận.
```

PR description không khớp diff:

```text
So sánh PR description với `gh pr diff`.
Chỉ ra câu nào không đúng, thiếu bằng chứng, hoặc cần sửa để trung thực hơn.
Không sửa file.
```

Lỡ commit secret:

1. Dừng push/merge.
2. Rotate secret ngay.
3. Xóa secret khỏi code.
4. Audit terminal output, CI log, PR diff và nơi secret có thể đã lộ.
5. Thêm `.gitignore`, secret scanning, pre-commit guard hoặc `.claude/settings.json` deny rules.

Ví dụ deny rule cho Claude Code:

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  }
}
```

Rollback commit chưa push:

```bash
git reset --soft HEAD~1
```

Rollback PR đã merge:

```bash
git checkout main
git pull origin main
git checkout -b revert/github-workflow-pr-template
git revert <merge_or_squash_commit_sha>
git push -u origin revert/github-workflow-pr-template
gh pr create --base main --head revert/github-workflow-pr-template --title "revert: GitHub workflow guide" --body "Reverts the GitHub workflow guide change."
```

## Link tài liệu nên đọc

- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code settings và permissions: https://code.claude.com/docs/en/settings
- Claude Code GitHub Actions: https://code.claude.com/docs/en/github-actions
- Claude Code Code Review: https://code.claude.com/docs/en/code-review
- GitHub CLI `gh pr`: https://cli.github.com/manual/gh_pr
- GitHub Pull Requests: https://docs.github.com/en/pull-requests
- Creating a pull request: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request
- Managing protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- GitHub rulesets available rules: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- About status checks: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks
