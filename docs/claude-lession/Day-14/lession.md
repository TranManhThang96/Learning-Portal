# Day 14 — Subagents cho workflow chuyên biệt

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Giải thích subagent là gì và vì sao context window riêng giúp giảm nhiễu trong workflow agentic coding.
- Phân biệt vai trò của main agent, planner, implementer, code reviewer, test engineer, security auditor.
- Tạo project subagent trong `.claude/agents/<name>.md`.
- Viết frontmatter và system prompt cho subagent có scope rõ.
- Giới hạn tools để subagent không vượt vai trò.
- Chạy workflow `plan -> implement -> review -> test` trên `taskflow-ai`.
- Nhận diện khi nào không nên dùng subagent vì overhead lớn hơn lợi ích.

## 2. Bối cảnh thực tế

Khi `taskflow-ai` lớn dần, một session Claude Code duy nhất dễ trộn nhiều việc:

- Lập plan feature.
- Sửa code.
- Review diff.
- Viết test.
- Chạy test và đọc log.
- Kiểm tra security.
- Viết summary hoặc PR description.

Nếu cùng một agent vừa implement vừa review, nó dễ bị ảnh hưởng bởi reasoning của chính nó. Nó có thể bảo vệ lựa chọn đã làm trước đó, bỏ sót test gap, hoặc review quá nhẹ. Subagent giúp tách vai trò: reviewer chỉ tập trung tìm lỗi, test engineer chỉ tập trung evidence, security auditor chỉ tập trung rủi ro bảo mật.

Workflow thực tế:

```text
Main agent nhận yêu cầu
  -> planner chia nhỏ việc
  -> main agent hoặc implementer sửa code
  -> code-reviewer review diff
  -> main agent sửa finding được chấp nhận
  -> test-engineer chạy test và phân tích output
  -> main agent tổng hợp quyết định merge/rollback
```

Không nên dùng subagent cho thay đổi quá nhỏ như sửa typo, đổi text một dòng, hoặc task chưa rõ mục tiêu. Khi đó overhead context, latency và coordination lớn hơn lợi ích.

## 3. Kiến thức nền

Subagent là AI assistant chuyên biệt, chạy với context riêng. Mỗi subagent có thể có:

- System prompt riêng.
- Tool access riêng.
- Model riêng hoặc kế thừa main session.
- Màu hiển thị riêng trong UI.

Vị trí phổ biến:

```text
.claude/agents/<name>.md
~/.claude/agents/<name>.md
```

`.claude/agents` là project scope, phù hợp với workflow team và nên commit nếu cả team dùng chung. `~/.claude/agents` là user scope, phù hợp thói quen cá nhân. Nếu trùng `name`, project subagent có ưu tiên cao hơn user subagent. Danh tính agent lấy từ field `name`, không nhất thiết lấy từ tên file.

Có 2 cách tạo subagent:

- Dùng `/agents` trong Claude Code: cách an toàn nhất vì UI giúp chọn scope, tools, model và có hiệu lực ngay.
- Tạo file markdown thủ công trong `.claude/agents/`: phù hợp khi muốn review/commit như code. Nếu tạo hoặc sửa file trực tiếp trên disk, restart Claude Code session để agent mới được load.

Một subagent file có YAML frontmatter và markdown prompt:

```md
---
name: code-reviewer
description: Use this agent after implementation to review code quality, maintainability, security risks, regressions, and missing tests before merge.
model: sonnet
tools: Read, Grep, Glob, Bash
color: blue
---

You are a senior code reviewer for taskflow-ai.
Review changes. Do not edit files.
```

Body sau frontmatter là system prompt của subagent. Subagent không nhận nguyên default Claude Code system prompt như main session, nên prompt phải tự nói rõ vai trò, phạm vi, output format, guardrails và cách xử lý khi thiếu dữ kiện. Subagent bắt đầu ở current working directory của main conversation, nhưng `cd` trong mỗi lệnh shell không nên được xem là state bền vững giữa các tool call.

Các field thường gặp:

| Field | Ý nghĩa |
| --- | --- |
| `name` | Tên định danh duy nhất, nên dùng lowercase và hyphen như `code-reviewer` |
| `description` | Khi nào nên dùng agent; ảnh hưởng auto-delegation |
| `model` | Model override như `sonnet`, `opus`, `haiku`, full model ID, hoặc `inherit`; nếu bỏ trống thường kế thừa model của session chính |
| `tools` | Allowlist tools agent được dùng; nếu bỏ field này agent có thể inherit toàn bộ tools từ main conversation, gồm cả MCP tools |
| `disallowedTools` | Denylist tools cần chặn khi muốn inherit phần lớn tools nhưng loại vài tool nguy hiểm |
| `permissionMode` | Permission mode riêng của agent; vẫn chịu ảnh hưởng mode của parent session |
| `maxTurns` | Giới hạn số lượt agentic để tránh agent chạy quá lâu |
| `effort` | Effort level riêng cho agent khi cần cân bằng chất lượng và latency |
| `background` | Cho phép agent chạy nền khi tác vụ dài hoặc có thể song song |
| `memory` | Persistent memory theo scope `user`, `project`, hoặc `local`; lưu ý bật memory tự động cần quyền đọc/ghi memory files |
| `mcpServers` | MCP servers riêng cho agent, hữu ích khi muốn browser/database tools chỉ nằm trong subagent |
| `isolation` | Có thể đặt `worktree` để chạy trong temporary git worktree khi cần cô lập thay đổi |
| `color` | Màu hiển thị trong UI |

Cách gọi phổ biến:

```text
Use the code-reviewer agent to review the recent changes.
```

```text
@"code-reviewer (agent)" review the auth changes.
```

Nếu nhập thủ công mà không dùng typeahead, dùng dạng local agent:

```text
@agent-code-reviewer review the current git diff. Do not edit files.
```

Có thể chạy cả session với system prompt của agent:

```bash
claude --agent code-reviewer
```

Lưu ý: cấu hình an toàn nhất trong bài này là dùng `tools` như allowlist. Nếu reviewer/tester không cần sửa file, không đưa `Write`, `Edit`, `MultiEdit`, hoặc tool ghi file tương đương vào danh sách tools. Không dựa vào prompt tự nguyện "do not edit files" như guardrail duy nhất. `Bash` vẫn là tool mạnh: reviewer có thể chạy `git diff`, `npm test`, `npm run lint`, nhưng cần guardrail/hook nếu team muốn chặn command ghi file hoặc thao tác destructive.

## 4. Step-by-step thực hành

Mục tiêu: tạo 2 project subagents cho `taskflow-ai`:

```text
.claude/agents/code-reviewer.md
.claude/agents/test-engineer.md
```

### Bước 1: Tạo thư mục agents

Chạy ở root `taskflow-ai`:

```bash
mkdir -p .claude/agents
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force .claude/agents
```

Giải thích:

- Thư mục chạy: root của project `taskflow-ai`, nơi có `package.json`, `backend/`, `frontend/` hoặc cấu trúc tương đương.
- Bash `mkdir -p .claude/agents`: tạo thư mục agent nếu chưa tồn tại; nếu đã tồn tại thì không lỗi.
- PowerShell `New-Item -ItemType Directory -Force .claude/agents`: tương đương trên Windows.
- Output kỳ vọng: có thể không in gì hoặc in metadata thư mục vừa tạo.
- Rủi ro: thấp; không ghi đè nội dung file agent hiện có. Vẫn cần kiểm tra đúng thư mục để không tạo `.claude` nhầm repo.

Kiểm tra:

```bash
ls .claude/agents
```

PowerShell:

```powershell
Get-ChildItem .claude/agents
```

Output kỳ vọng ban đầu là thư mục rỗng hoặc danh sách agent đã có. Nếu thấy agent cũ, đọc trước khi sửa để không phá workflow của team.

### Bước 2: Tạo `code-reviewer`

Tạo `.claude/agents/code-reviewer.md`:

```md
---
name: code-reviewer
description: Use this agent after implementation to review code quality, maintainability, security risks, regressions, and missing tests before merge.
model: sonnet
tools: Read, Grep, Glob, Bash
color: blue
---

You are a senior code reviewer for the taskflow-ai project.

Your job is to review changes, not to edit files.

Review priorities:
1. Correctness bugs and behavioral regressions.
2. Security risks: auth, authorization, injection, secrets, unsafe file or shell usage.
3. Missing or weak tests.
4. Maintainability: duplication, unclear boundaries, brittle abstractions, confusing names.
5. Performance and context/cost issues.

When reviewing:
- Start with findings ordered by severity.
- Use file paths and line references when possible.
- Explain the concrete failure mode.
- Suggest the smallest practical fix.
- If no issue is found, say that clearly and mention residual risks.
- Do not modify files.
- Do not run destructive commands.
```

Vì reviewer cần xem diff và có thể chạy command read-only như `git diff`, cho phép `Bash`, nhưng không đưa `Write` hoặc `Edit` vào `tools` để giữ vai trò review độc lập. Trong prompt vẫn nhắc "Do not edit files" để tăng rõ ràng về hành vi.

### Bước 3: Tạo `test-engineer`

Tạo `.claude/agents/test-engineer.md`:

```md
---
name: test-engineer
description: Use this agent to design, run, and analyze tests for taskflow-ai after a feature or bug fix is implemented.
model: sonnet
tools: Read, Grep, Glob, Bash
color: green
---

You are a test engineer for the taskflow-ai project.

Your job is to validate behavior through focused tests and clear evidence.

Responsibilities:
1. Identify the behavior that changed.
2. Select the smallest useful test scope first.
3. Run existing tests before suggesting new tests.
4. Analyze failures with concrete hypotheses.
5. Recommend missing tests, edge cases, and regression coverage.
6. Avoid editing files unless the main agent explicitly asks for test implementation.

Testing strategy:
- Start with targeted tests if available.
- Then run broader test suites.
- Capture exact commands and important output.
- Separate product bug, test bug, and environment issue.
- Call out flaky or slow tests.
```

Nếu project dùng `pnpm` hoặc `yarn`, test engineer cần đọc `package.json` trước khi chạy command.

### Bước 4: Kiểm tra agent files

Chạy:

```bash
git status --short
```

Output kỳ vọng:

```text
?? .claude/agents/code-reviewer.md
?? .claude/agents/test-engineer.md
```

Giải thích:

- Thư mục chạy: root `taskflow-ai`.
- `git status --short`: chỉ đọc trạng thái Git, không sửa file.
- Output kỳ vọng: 2 file agent mới ở trạng thái untracked hoặc modified nếu đã tồn tại.
- Rủi ro: thấp. Nếu output có file ngoài `.claude/agents`, không động vào vì có thể là thay đổi của người khác.

Trong Claude Code, mở `/agents` để xác nhận agent đã được nhận diện. Nếu tạo file thủ công nhưng không thấy agent, restart Claude Code session rồi kiểm tra lại.

Nếu team dùng chung, commit các file này. Nếu chỉ thử nghiệm cá nhân, cân nhắc dùng `~/.claude/agents`.

### Bước 5: Chạy workflow `plan -> implement -> review -> test`

Chọn feature nhỏ:

```text
Add task priority with values low, medium, high.
```

Prompt plan:

```text
Plan adding task priority to taskflow-ai.
Split the plan into data model, API changes, UI changes, tests, migration or compatibility concerns, rollback risks, and acceptance criteria.
Do not edit files yet.
```

Sau khi approve plan:

```text
Implement the approved task priority plan with minimal scope.
Preserve existing behavior, avoid unrelated refactors, and run relevant checks if available.
```

Gọi reviewer:

```text
@"code-reviewer (agent)" review the current git diff.
Focus on correctness, maintainability, security risks, regressions, and missing tests.
Return findings ordered by severity. Do not edit files.
```

Nếu không dùng typeahead, prompt tương đương:

```text
@agent-code-reviewer review the current git diff.
Focus on correctness, maintainability, security risks, regressions, and missing tests.
Return findings ordered by severity. Do not edit files.
```

Gọi tester:

```text
@"test-engineer (agent)" validate the current changes.
Run the smallest relevant tests first, then broader checks if useful.
Report exact commands, exit status, important output, and whether this blocks merge.
```

Các command tester thường kiểm tra trước khi chạy:

| Command | Thư mục chạy | Làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `npm run` | Root package liên quan hoặc root monorepo `taskflow-ai` | Liệt kê scripts trong `package.json` | Danh sách script như `test`, `lint`, `typecheck` | Thấp; chỉ đọc scripts |
| `npm test` hoặc `pnpm test` | Package có test | Chạy test suite mặc định | Exit code `0`, test pass; hoặc failure có stack trace rõ | Có thể tốn thời gian, cần DB/test service nếu integration test |
| `npm run lint` hoặc `pnpm lint` | Package có lint config | Kiểm tra style/static analysis | Không có error | Có thể fail vì lỗi cũ không liên quan; cần phân biệt baseline |
| `npm run typecheck` hoặc `pnpm typecheck` | Package TypeScript | Kiểm tra type | Không có TypeScript error | Có thể chậm ở repo lớn |

Không để subagent tự ý chạy migration, seed hoặc command ghi dữ liệu nếu chưa hiểu environment. Với `taskflow-ai`, mọi command dùng database nên chạy trên local/dev database, không dùng production credential.

### Bước 6: Rollback khi review/test phát hiện lỗi lớn

Xem diff:

```bash
git diff --stat
git diff
```

Rollback một file:

```bash
git restore path/to/file
```

Rollback staged changes:

```bash
git restore --staged .
```

Giải thích rollback:

- Thư mục chạy: root `taskflow-ai`.
- `git diff --stat` tóm tắt file thay đổi; `git diff` hiển thị nội dung diff để quyết định rollback.
- `git restore path/to/file` khôi phục một file về trạng thái HEAD. Rủi ro: mất toàn bộ sửa đổi chưa commit trong file đó.
- `git restore --staged .` chỉ bỏ staged changes khỏi index, không xóa nội dung working tree.
- Không dùng `git reset --hard` nếu chưa chắc chắn toàn bộ thay đổi chưa commit đều có thể mất, đặc biệt khi nhiều agent đang sửa các phần khác nhau của repo.

## 5. Prompt mẫu nên dùng

Prompt gọi planner:

```text
Use a planner-style workflow to break down this change before implementation.
Output phases, affected files, acceptance criteria, test plan, risks, and rollback.
Do not edit files.
```

Prompt gọi reviewer:

```text
@"code-reviewer (agent)" review only the current git diff.
For each finding, include severity, file path, line reference if possible, failure mode, and smallest fix.
If there are no high-confidence findings, say so clearly.
Do not edit files.
```

Prompt gọi tester:

```text
@"test-engineer (agent)" run the smallest relevant checks for the recent changes.
Report exact commands, exit status, key output lines, and whether each result blocks merge.
Do not edit files.
```

Prompt gọi security auditor nếu có:

```text
@"security-auditor (agent)" audit the current diff for auth, authorization, injection, secrets, unsafe shell usage, and sensitive data exposure.
Report only high-confidence findings. Put speculative concerns under residual risks.
Do not edit files.
```

Prompt tổng hợp:

```text
Summarize the plan, implementation, review findings, test results, unresolved risks, and rollback steps.
Conclude with: ready to merge, needs changes, or blocked.
```

## 6. Trade-offs

Subagent có lợi khi:

- Task có vai trò rõ ràng.
- Cần review độc lập sau implementation.
- Cần tách output lớn như test logs khỏi context chính.
- Cần tool scope khác nhau cho từng vai trò.
- Cần chạy phân tích song song.

Chi phí:

- Tốn thêm token vì mỗi subagent có context riêng.
- Tốn thời gian đọc lại diff/file.
- Dễ tạo quá nhiều agent.
- Prompt agent mơ hồ dẫn tới output chung chung.
- Permission quá rộng làm tăng rủi ro.

| Tình huống | Nên dùng subagent? | Lý do |
| --- | --- | --- |
| Sửa typo trong README | Không | Overhead lớn hơn lợi ích |
| Thêm field ảnh hưởng API, UI, test | Có | Cần review và test độc lập |
| Debug test flaky | Có | Test engineer giữ context riêng về test |
| Review auth middleware | Có | Cần security lens |
| Đổi tên biến cục bộ | Không | Main agent xử lý nhanh hơn |

## 7. Best practices

- Đặt subagent theo vai trò ổn định: `code-reviewer`, `test-engineer`, `security-auditor`.
- Không đặt theo task quá hẹp như `fix-priority-bug-agent`.
- Giữ `description` cụ thể vì Claude dùng field này để quyết định delegation.
- Reviewer mặc định read-only, không có `Edit`/`Write`.
- Tester có `Bash` để chạy test, nhưng không nên tự sửa file nếu nhiệm vụ chỉ validate.
- Security auditor dùng allowlist tools tối thiểu; không cấp tool ghi file hoặc command nguy hiểm nếu chỉ audit.
- Project subagents nên commit nếu team dùng chung.
- Tạo hoặc chỉnh agent bằng `/agents` khi có thể; nếu sửa file markdown thủ công, restart Claude Code để tránh dùng agent definition cũ.
- Khi cần chắc chắn agent chạy, dùng `@` typeahead hoặc dạng thủ công `@agent-<name>` thay vì chỉ nhắc tên trong câu.
- Permission mode của parent session vẫn quan trọng. Nếu session chính đang auto-approve hoặc bypass permission, subagent không phải sandbox bảo mật tuyệt đối.
- Output của reviewer/tester phải có evidence, command hoặc file reference.
- Main agent vẫn là coordinator: quyết định finding nào chấp nhận, sửa gì, test gì, và khi nào merge.

## 8. Performance / cost / context

Subagent giúp context chính sạch hơn, nhưng tổng chi phí có thể tăng. Dùng subagent khi lợi ích từ isolation lớn hơn token/latency.

Cách tối ưu:

- Gọi subagent sau khi có diff rõ.
- Giới hạn scope: `review current git diff`, không phải `review whole project`.
- Yêu cầu output concise.
- Không gọi 4-5 subagents cho thay đổi nhỏ.
- Dùng tools tối thiểu.
- Đặt `maxTurns` cho agent dễ lan man như reviewer toàn repo hoặc log analyzer.
- Dùng `model: inherit` hoặc model rẻ hơn cho task lặp lại nếu chất lượng vẫn đủ; dùng model mạnh hơn cho audit phức tạp.
- Nếu test log dài, yêu cầu test engineer trả key lines và root cause, không paste toàn bộ log.
- Subagent transcripts tách khỏi main conversation; main context sạch hơn, nhưng tổng token vẫn tăng vì mỗi agent phải đọc lại diff/file cần thiết.

Prompt tiết kiệm context:

```text
@"code-reviewer (agent)" review only files changed in git diff. Inspect related files only to validate a concrete finding.
```

Prompt tốn context:

```text
@"code-reviewer (agent)" review the whole project and list everything that can be improved.
```

## 9. Checklist cuối bài

- [ ] Tôi giải thích được subagent là gì.
- [ ] Tôi biết subagent có context, prompt và tools riêng.
- [ ] Tôi tạo được `.claude/agents/code-reviewer.md`.
- [ ] Tôi tạo được `.claude/agents/test-engineer.md`.
- [ ] `code-reviewer` không có quyền edit file.
- [ ] `test-engineer` có quyền chạy command test.
- [ ] Tôi chạy được workflow `plan -> implement -> review -> test`.
- [ ] Tôi biết khi nào không nên dùng subagent.
- [ ] Tôi hiểu rủi ro của việc cấp tools quá rộng cho subagent.
- [ ] Tôi có rollback plan nếu review/test phát hiện lỗi.

## 10. Bài tập

Bài cơ bản: tạo `code-reviewer` và `test-engineer` trong `.claude/agents`.

Bài thực tế: chọn feature nhỏ như `task priority` hoặc `due date`, chạy workflow `plan -> implement -> review -> test`, lưu prompt và kết quả.

Bài nâng cao: tạo `security-auditor` read-only cho diff có auth, input validation hoặc sensitive data.

Bài reflection: so sánh chất lượng review giữa main agent tự review và subagent `code-reviewer`. Ghi rõ subagent phát hiện thêm gì, bỏ sót gì, và overhead có đáng không.
