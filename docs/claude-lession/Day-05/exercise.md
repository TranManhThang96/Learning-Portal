# Exercise — Day 05

## Bài 1 — Cơ bản

Mục tiêu: tạo draft `CLAUDE.md` cho `taskflow-ai` và hiểu vì sao không được accept mù quáng.

Yêu cầu:

1. Mở terminal tại root `taskflow-ai`.
2. Kiểm tra trạng thái repo:

```bash
git status --short
```

Lệnh này hiển thị working tree. Output kỳ vọng là rỗng hoặc chỉ gồm file bạn hiểu rõ. Nếu có file lạ, không chạy `/init` vội vì Claude có thể hiểu state tạm thời là convention của project.

3. Mở Claude Code:

```bash
cd /path/to/taskflow-ai
claude
```

Lệnh này chuyển vào project rồi mở session tại thư mục hiện tại. Output kỳ vọng là Claude sẵn sàng nhận prompt. Có thể dùng `/help` để xem slash commands của CLI version hiện tại. Rủi ro: mở sai thư mục sẽ tạo `CLAUDE.md` sai vị trí.

4. Chạy slash command:

```text
/init
```

Kết quả kỳ vọng: Claude đọc repo và tạo hoặc cập nhật `CLAUDE.md`.

Nếu CLI version đang dùng không có `/init`, dùng prompt tạo thủ công:

```text
Hãy tạo CLAUDE.md cho taskflow-ai như project instructions cho Claude Code.
Chỉ ghi thông tin có bằng chứng từ repo; nếu không chắc command nào đúng, đánh dấu "verify before use".
Chỉ sửa CLAUDE.md hoặc .claude/CLAUDE.md theo convention của project.
Không đưa secret, endpoint production, hoặc dữ liệu nhạy cảm.
```

5. Xem diff:

```bash
git diff -- CLAUDE.md
```

Output kỳ vọng: một file instruction Markdown có mô tả project, commands, architecture, conventions. Nếu project chọn `.claude/CLAUDE.md`, dùng `git diff -- .claude/CLAUDE.md`. Nếu file có command không chắc đúng, đánh dấu để sửa.

Ghi lại ít nhất 5 điểm cần review:

- Command nào cần xác nhận từ `package.json`.
- Folder nào Claude mô tả đúng hoặc sai.
- Rule nào quá chung chung.
- Có thông tin nhạy cảm không.
- File có quá dài không.

## Bài 2 — Thực tế

Mục tiêu: chỉnh `CLAUDE.md` thành onboarding document cho AI dùng được trong team.

Yêu cầu:

1. Dùng prompt sau trong Claude Code:

```text
Review và chỉnh CLAUDE.md cho taskflow-ai.

Mục tiêu:
- Đây là onboarding document cho Claude Code, không phải README.
- Giữ ngắn, target dưới 200 dòng, ưu tiên rule Claude cần trong mọi session.
- Chỉ giữ thông tin có bằng chứng từ repo hoặc cần tôi xác nhận.
- Có đủ section: Project, Structure, Commands, Coding Conventions, Testing, Security, Workflow.
- Mỗi command phải ghi thư mục chạy, output kỳ vọng, và rủi ro nếu có.

Giới hạn:
- Chỉ sửa `CLAUDE.md` hoặc `.claude/CLAUDE.md` nếu project đã chọn convention đó.
- Không sửa README.md, source code, test, package.json, hoặc config khác.
- Không chạy npm install, migration, git add, git commit, git reset, git clean, hoặc lệnh xóa file.
```

2. Sau khi Claude sửa, kiểm tra phạm vi:

```bash
git diff --stat
```

Output kỳ vọng: chỉ `CLAUDE.md` hoặc `.claude/CLAUDE.md` thay đổi. Nếu có file khác, dừng lại và review.

3. Xem chi tiết:

```bash
git diff -- CLAUDE.md
```

Output kỳ vọng: file có nội dung tương tự cấu trúc sau, nhưng phải khớp repo thật:

```md
# CLAUDE.md

## Project
- taskflow-ai is a task management app for engineering teams.
- Use TypeScript for backend and frontend.

## Structure
- apps/api: backend API.
- apps/web: React + Vite frontend.
- packages/shared: shared types and validation helpers.

## Commands
- Install from repo root: `pnpm install`
- API dev from repo root: `pnpm --filter api dev`
- Web dev from repo root: `pnpm --filter web dev`
- Typecheck from repo root: `pnpm typecheck`
- Unit tests from repo root: `pnpm test`

## Coding Conventions
- Read existing module patterns before adding files.
- Keep validation near API boundary or existing validation layer.
- Avoid new abstractions until at least two call sites need them.

## Testing
- Add or update tests for behavior changes.
- Do not weaken assertions just to make tests pass.

## Security
- Do not read or print `.env` values.
- Do not use production data.
- Do not run destructive Git, Docker, or database commands without explicit confirmation.

## Workflow
- Start risky changes with a plan.
- Keep diffs small.
- Summarize changed files and verification commands.
- Do not commit or push unless explicitly asked.
```

4. Tự sửa lại nếu sample không đúng với repo thật. Ví dụ nếu project dùng `npm` thì không giữ `pnpm`.

## Bài 3 — Nâng cao

Mục tiêu: kiểm tra session mới có load đúng project instructions hay không.

Yêu cầu:

1. Thoát session Claude hiện tại.
2. Mở session mới tại root `taskflow-ai`:

```bash
cd /path/to/taskflow-ai
claude
```

Lệnh này mở Claude Code từ đúng project root. Output kỳ vọng là Claude sẵn sàng nhận prompt. Không dùng `claude --continue` cho bài test này vì nó tiếp tục session gần nhất trong thư mục hiện tại; dùng `claude --resume` hoặc `/resume` chỉ khi bạn muốn chọn một session cũ. Rủi ro: nếu mở sai directory, kết quả test context không có giá trị.

Không bật `claude --permission-mode acceptEdits` chỉ để kiểm tra context. Theo docs hiện hành, chế độ này cho phép tạo/sửa file và auto-approve một số command filesystem phổ biến trong working directory; chỉ dùng khi bạn thật sự muốn Claude edit và đã có guardrails.

3. Gửi prompt:

```text
Không sửa file và không chạy command.
Hãy trả lời dựa trên project instructions đã load:

1. taskflow-ai dùng stack gì?
2. Các thư mục chính và trách nhiệm của từng thư mục là gì?
3. 5 command quan trọng nhất là gì, chạy ở đâu, output kỳ vọng là gì?
4. Khi sửa backend task API, workflow an toàn phải làm theo là gì?
5. Command hoặc hành động nào không được tự chạy?

Nếu bạn không thấy CLAUDE.md hoặc không chắc instruction đã load, nói rõ thay vì đoán.
```

4. Chấm kết quả:

- Đạt nếu Claude trả lời đúng nội dung từ `CLAUDE.md`.
- Chưa đạt nếu Claude nói chung chung, sai package manager, sai folder, hoặc không nhắc security rules.

5. Nếu chưa đạt, debug bằng các lệnh:

```bash
pwd
ls CLAUDE.md .claude/CLAUDE.md
git diff -- CLAUDE.md
git diff -- .claude/CLAUDE.md
```

`pwd` xác nhận thư mục hiện tại. `ls` xác nhận file instruction tồn tại. `git diff` xác nhận nội dung chưa commit có đúng không. Rủi ro thấp vì đều là read-only; nếu một trong hai path không tồn tại, `git diff` có thể không in gì hoặc báo path không có trong repo tùy shell/Git version.

## Bài 4 — Review & Reflection

Mục tiêu: biến `CLAUDE.md` thành artifact có thể bảo trì lâu dài, không chỉ là file tạo cho xong.

Trả lời các câu hỏi:

1. Rule nào trong `CLAUDE.md` giúp Claude không sửa quá rộng?
2. Rule nào giúp giảm rủi ro security?
3. Command nào trong file có khả năng stale cao nhất khi repo đổi?
4. Nếu chuyển test runner từ Jest sang Vitest, bạn cần cập nhật những dòng nào?
5. Nếu team muốn Claude hỏi ít hơn khi sửa file, khi nào nên dùng prompt/workflow rule trong `CLAUDE.md`, khi nào mới cân nhắc `claude --permission-mode acceptEdits` hoặc `permissions.defaultMode: "auto"` trong `.claude/settings.json`?
6. Có rule nào đang quá chung chung không? Viết lại thành rule có thể kiểm tra được.

Prompt reflection gợi ý:

```text
Review CLAUDE.md như artifact bảo trì lâu dài.

Hãy chỉ ra:
- 5 rule có giá trị cao nhất.
- 5 dòng có nguy cơ stale.
- 3 rule nên viết cụ thể hơn.
- 3 security guardrail còn thiếu.
- Cách rút gọn file để giảm context cost nhưng không mất rule quan trọng.

Không sửa file trong bước này.
```

## Tiêu chí hoàn thành

- Đã tạo hoặc cập nhật `CLAUDE.md` cho `taskflow-ai`.
- File có đủ section Project, Structure, Commands, Coding Conventions, Testing, Security, Workflow.
- Commands ghi rõ thư mục chạy, output kỳ vọng, và rủi ro chính.
- Security rules không cho đọc/in secret, không dùng production data, không tự chạy destructive command, không tự commit/push.
- `git diff --stat` cho thấy chỉ `CLAUDE.md` hoặc `.claude/CLAUDE.md` thay đổi trong bài thực hành này.
- Đã mở session mới và kiểm tra Claude có load đúng project instructions.
- Đã ghi lại ít nhất 3 dòng có nguy cơ stale và cách bảo trì.
- Không sửa README.md, source code, Day khác, hoặc file ngoài phạm vi bài thực hành.

## Gợi ý nếu bí

Nếu `/init` tạo file quá dài, dùng prompt:

```text
CLAUDE.md hiện tại quá dài. Hãy rút gọn xuống dưới 200 dòng và giữ dạng cheat sheet dễ scan.
Giữ lại stack, structure, commands, conventions, testing, security, workflow.
Xóa phần giải thích chung chung và task tạm thời.
Không sửa file nào khác.
```

Nếu Claude bịa command, dùng prompt:

```text
Không được đoán command.
Hãy đọc package.json liên quan và chỉ ghi command có script thật.
Nếu chưa chắc command chạy từ root hay package con, đánh dấu "verify before use".
```

Nếu Claude không nhận context ở session mới, kiểm tra:

```bash
pwd
ls CLAUDE.md
ls .claude/CLAUDE.md
```

Nếu cả hai vị trí đều không có file, bạn đã tạo sai chỗ. Nếu có file nhưng Claude trả lời sai, mở session mới ở đúng root và hỏi lại bằng prompt kiểm tra context.

Nếu diff chạm file ngoài `CLAUDE.md`, dùng:

```bash
git diff --stat
git diff -- path/to/unexpected-file
```

Đọc diff trước. Nếu file đó có thể là thay đổi của đồng đội hoặc thay đổi bạn cần giữ, không rollback. Nếu chắc chắn file ngoài phạm vi là do bạn vừa tạo/sửa nhầm và muốn bỏ:

```bash
git restore -- path/to/unexpected-file
```

Rủi ro: mất thay đổi chưa commit trong file đó, kể cả thay đổi do bạn tự viết hoặc người khác vừa tạo trong cùng working tree.

## Đáp án tham khảo hoặc expected result

Kết quả kỳ vọng cho Bài 1:

- Có draft `CLAUDE.md`.
- Bạn xác định được ít nhất 5 điểm cần review.
- Không có secret hoặc dữ liệu nhạy cảm trong file.

Kết quả kỳ vọng cho Bài 2:

- `CLAUDE.md` ngắn, có section rõ ràng, không phải README dài.
- Commands khớp `package.json` thật.
- Security và workflow rules đủ cụ thể để Claude làm theo.
- Diff chỉ chạm `CLAUDE.md`.

Ví dụ rule tốt:

```md
- Do not run `git reset --hard`, `git clean -fd`, `docker compose down -v`, database drop/truncate, or force push without explicit confirmation.
- For risky backend changes, first read the route, service, repository, and test files, then present a plan before editing.
- After edits, summarize changed files and suggest verification commands; do not commit or push.
```

Ví dụ rule yếu cần sửa:

```md
- Be careful.
- Write good code.
- Run tests.
```

Kết quả kỳ vọng cho Bài 3:

- Session mới trả lời đúng stack, structure, commands, testing, security, workflow từ `CLAUDE.md`.
- Claude nói rõ nếu không thấy instruction thay vì đoán.
- Bạn phát hiện được lỗi nếu mở sai directory hoặc file đặt sai vị trí.

Kết quả kỳ vọng cho Bài 4:

- Có danh sách rule giá trị cao, rule dễ stale, và rule cần viết cụ thể hơn.
- Bạn phân biệt được nội dung nên nằm trong `CLAUDE.md` với cấu hình nên cân nhắc trong `.claude/settings.json`, và hiểu rủi ro của `acceptEdits`/`defaultMode: "auto"`.
- Bạn có kế hoạch cập nhật `CLAUDE.md` khi architecture, commands, hoặc testing strategy thay đổi.
