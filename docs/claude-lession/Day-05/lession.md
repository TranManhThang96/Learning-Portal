# Day 05 — CLAUDE.md chuẩn cho project

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Giải thích được vì sao Claude Code có thể "quên" convention, command, kiến trúc, hoặc quyết định đã thống nhất giữa các session.
- Xem `CLAUDE.md` như onboarding document cho AI: ngắn, chính xác, dễ cập nhật, và được dùng lại trong session mới.
- Biết đặt project instructions ở `CLAUDE.md` hoặc `.claude/CLAUDE.md` theo tài liệu Claude Code hiện hành.
- Biết dùng `/init` nếu CLI version đang dùng hỗ trợ, hoặc tạo thủ công `CLAUDE.md` bằng prompt có kiểm soát, sau đó review như một artifact của team.
- Viết `CLAUDE.md` cho project `taskflow-ai` gồm stack, architecture, commands, coding conventions, testing rules, security rules, và workflow an toàn.
- Kiểm tra session mới có load đúng project context hay không, không chỉ tin rằng file đã tồn tại là đủ.

## 2. Bối cảnh thực tế

Trong công việc thật, vấn đề thường không phải Claude Code không biết viết code. Vấn đề là Claude không luôn có cùng mental model với team ở mọi session. Hôm nay bạn giải thích `taskflow-ai` dùng Fastify, route nằm trong `apps/api`, test chạy bằng Vitest, không dùng Jest. Ngày mai mở session mới, nếu không có project memory rõ ràng, Claude có thể lại đề xuất `npm test`, tạo thư mục `src/controllers`, hoặc thêm convention không tồn tại.

Claude Code có context window lớn nhưng context không phải trí nhớ vĩnh viễn. Một session mới cần được nạp lại chỉ dẫn quan trọng. Session dài có thể bị nhiễu bởi prompt cũ, diff cũ, log lỗi, hoặc các hướng đi đã bị loại. `CLAUDE.md` giải quyết phần này bằng cách đóng vai onboarding document cho AI: khi mở repo, Claude biết các rule cốt lõi trước khi lập plan hoặc sửa code.

Trong `taskflow-ai`, một `CLAUDE.md` tốt giúp Claude trả lời nhanh các câu hỏi như:

- Backend nằm ở đâu, frontend nằm ở đâu.
- Lệnh nào dùng để chạy dev server, typecheck, unit test, e2e test.
- Validation nên đặt ở service, route schema, hay component.
- Không được chạy command nào nếu chưa có xác nhận thủ công.
- Khi implement feature, phải plan trước, sửa nhỏ, chạy test, và không tự commit.

Không nên dùng `CLAUDE.md` để:

- Lưu secret, token, connection string, production credential, hoặc dữ liệu khách hàng.
- Nhét toàn bộ architecture document dài nhiều trang vào context mặc định.
- Ghi task tạm thời như "hôm nay sửa bug X" rồi quên xóa.
- Thay thế README, ADR, test, code review, hoặc security policy chính thức của team.
- Ép Claude làm theo rule chưa được team thống nhất.

## 3. Kiến thức nền

Claude Code hỗ trợ project memory thông qua file instruction. Theo tài liệu hiện hành, project instructions có thể nằm ở `./CLAUDE.md` hoặc `./.claude/CLAUDE.md`. Hai vị trí này đều phù hợp cho nội dung chia sẻ trong team và có thể commit vào source control. Nếu có cấu hình local hoặc plugin riêng cho từng developer, nên dùng file local trong `.claude` và đưa pattern local vào `.gitignore`.

Điểm cần phân biệt:

- `CLAUDE.md`: chỉ dẫn ngắn cho Claude về project. Đây là cheat sheet cho AI.
- `README.md`: tài liệu cho người mới, setup rộng hơn, có thể dài hơn và public hơn.
- `.claude/settings.json`: cấu hình hành vi Claude Code như permission mode mặc định hoặc tool permission. Đây không phải nơi viết architecture dài.
- Prompt trong session: chỉ dẫn cho task hiện tại. Không nên nhét rule lâu dài vào prompt lặp lại mỗi ngày.

Một `CLAUDE.md` chuẩn cho `taskflow-ai` nên trả lời 6 nhóm câu hỏi:

1. **Stack**: project dùng Node.js, TypeScript, backend Fastify hoặc NestJS, React + Vite, PostgreSQL, Redis, Vitest/Jest, Playwright, Docker Compose.
2. **Architecture**: thư mục chính, module boundary, flow request, nơi đặt validation, nơi đặt test.
3. **Commands**: lệnh dev, build, lint, typecheck, unit test, e2e test, migration, seed; ghi rõ chạy ở root hay package nào.
4. **Coding conventions**: style TypeScript, error handling, naming, dependency injection, component boundary, không tạo abstraction nếu chưa cần.
5. **Testing rules**: test nào bắt buộc trước khi đổi behavior, khi nào cần integration/e2e, không sửa test để hợp thức hóa bug.
6. **Security rules**: không đọc hoặc in `.env`, không dùng production data, không chạy destructive command, không tự commit, không tự push.

`/init` là điểm bắt đầu tốt nếu có trong CLI version đang dùng. Khi chạy trong repo, Claude Code có thể đọc cấu trúc project và viết `CLAUDE.md` với build commands, architecture, và conventions. Nhưng bản sinh tự động chỉ là draft. Developer vẫn phải review vì Claude có thể suy luận sai command, bỏ sót package, hoặc viết rule quá chung. Nếu slash command hoặc hành vi memory thay đổi, kiểm tra official docs hoặc chạy `/help` trong Claude Code thay vì dựa vào ghi nhớ cũ.

Lưu ý thêm: một số phiên bản Claude Code có khái niệm auto memory ngoài `CLAUDE.md`. Không nên viết bài học như thể auto memory luôn hoạt động giống nhau ở mọi môi trường. Với course này, coi `CLAUDE.md` hoặc `.claude/CLAUDE.md` là project instructions do team kiểm soát; mọi tính năng auto memory nên được xác nhận theo official docs và CLI version trước khi đưa vào workflow team.

Nguyên tắc thiết kế: `CLAUDE.md` nên ngắn như cheat sheet, không phải tài liệu tổng hợp. Tài liệu Claude Code khuyến nghị instruction cụ thể, có cấu trúc, và target dưới 200 dòng cho mỗi file. Nếu dài hơn hoặc phải cuộn quá nhiều, hãy chuyển phần mô tả sâu sang `docs/architecture.md`, `docs/testing.md`, hoặc ADR, rồi trong `CLAUDE.md` chỉ link tới tài liệu đó.

Ví dụ skeleton phù hợp cho `taskflow-ai`:

```md
# CLAUDE.md

## Project
- `taskflow-ai` is a task management app for engineering teams.
- Use TypeScript across backend and frontend.

## Structure
- `apps/api`: backend API.
- `apps/web`: React + Vite frontend.
- `packages/shared`: shared types and validation helpers.
- `docker-compose.yml`: local PostgreSQL and Redis.

## Commands
- Root install: `pnpm install`
- API dev: `pnpm --filter api dev`
- Web dev: `pnpm --filter web dev`
- Typecheck: `pnpm typecheck`
- Unit tests: `pnpm test`
- E2E tests: `pnpm e2e`

## Workflow Rules
- Start risky tasks by asking for a written plan before editing.
- Read relevant files before editing.
- Keep changes small and explain diff after editing.
- Do not run destructive Git, Docker, or database commands without explicit confirmation.
- Do not commit or push unless the user asks.
```

Hãy xem skeleton trên là ví dụ, không phải chân lý. `CLAUDE.md` phải phản ánh repo thật. Nếu `taskflow-ai` dùng `npm` thay vì `pnpm`, hoặc dùng NestJS thay vì Fastify, file phải nói đúng điều đó.

## 4. Step-by-step thực hành

Mục tiêu thực hành: tạo `CLAUDE.md` cho `taskflow-ai`, review nội dung như senior developer, rồi mở session mới để kiểm tra Claude Code có load đúng context không.

### Bước 1: Kiểm tra repo trước khi để Claude đọc

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này cho biết working tree đang sạch hay có thay đổi chưa commit. Output kỳ vọng là rỗng hoặc chỉ gồm file bạn hiểu rõ. Rủi ro: nếu repo đang có thay đổi của bạn hoặc đồng đội, Claude có thể đọc và mô tả state tạm thời như convention chính thức.

Kiểm tra nhanh cấu trúc:

```bash
ls
```

Lệnh này liệt kê file và thư mục ở root. Output kỳ vọng có các file như `package.json`, `apps`, `packages`, `docker-compose.yml`, hoặc cấu trúc tương đương. Rủi ro thấp, đây là lệnh read-only.

Nếu dùng PowerShell:

```powershell
Get-ChildItem
```

Lệnh này tương đương `ls` trên Windows PowerShell. Output kỳ vọng là danh sách entry ở root `taskflow-ai`.

### Bước 2: Tạo draft bằng `/init` hoặc prompt thủ công

Mở Claude Code tại root `taskflow-ai`:

```bash
cd /path/to/taskflow-ai
claude
```

Lệnh này chuyển vào project rồi mở session Claude Code trong repo hiện tại. Output kỳ vọng là giao diện Claude sẵn sàng nhận prompt. Có thể dùng `/help` để xem slash commands được CLI version hiện tại hỗ trợ. Rủi ro: nếu mở nhầm thư mục cha hoặc thư mục con, `CLAUDE.md` có thể được tạo sai vị trí.

Trong Claude Code, chạy slash command:

```text
/init
```

`/init` yêu cầu Claude đọc repo và tạo hoặc cập nhật `CLAUDE.md`, nếu slash command này có trong CLI version đang dùng. Output kỳ vọng là file instruction được tạo với commands, architecture, và conventions Claude suy luận từ repo. Rủi ro: bản draft có thể sai command hoặc quá dài; chưa được xem là approved.

Nếu muốn kiểm soát kỹ hơn, hoặc nếu `/init` không có trong CLI version hiện tại, dùng prompt tạo thủ công:

```text
Hãy tạo CLAUDE.md cho taskflow-ai như một onboarding document cho AI.

Ràng buộc:
- Chỉ ghi thông tin có bằng chứng từ file trong repo.
- Nếu không chắc command nào đúng, ghi "verify before use" thay vì bịa.
- Giữ ngắn, target dưới 200 dòng, ưu tiên chỉ chứa rule Claude cần trong mọi session.
- Không đưa secret, endpoint production, hoặc dữ liệu nhạy cảm.
- Sau khi tạo, liệt kê file đã đọc và điểm nào còn cần tôi xác nhận.
```

### Bước 3: Review draft như review code

Chạy trong root `taskflow-ai`:

```bash
git diff -- CLAUDE.md
```

Lệnh này chỉ xem diff của `CLAUDE.md`. Output kỳ vọng là một file Markdown ngắn, có section rõ ràng, không chứa secret, không chứa rule mơ hồ. Rủi ro: nếu chỉ đọc bản render trong editor mà không xem diff, bạn có thể bỏ sót đoạn Claude thêm quá rộng hoặc sai command.

Checklist review:

- Stack có đúng repo thật không.
- Commands có đúng package manager và thư mục chạy không.
- Architecture mô tả theo module hiện có, không bịa folder chưa tồn tại.
- Coding conventions có actionable rule, không chỉ "write clean code".
- Testing rules nêu đúng test runner và test scope.
- Security rules chặn secret, production data, destructive command, auto commit/push.
- File đủ ngắn để session mới không tốn context quá nhiều.

### Bước 4: Chỉnh `CLAUDE.md` thành cheat sheet

Prompt chỉnh sửa gợi ý:

```text
Review CLAUDE.md hiện tại như senior maintainer.

Mục tiêu:
- Giữ lại rule quan trọng cho Claude Code khi làm việc trong taskflow-ai.
- Xóa phần chung chung hoặc suy đoán không có bằng chứng.
- Chuẩn hóa thành các section: Project, Structure, Commands, Coding Conventions, Testing, Security, Workflow.
- Mỗi command phải ghi thư mục chạy và output kỳ vọng ngắn.
- Không sửa file nào ngoài `CLAUDE.md` hoặc `.claude/CLAUDE.md` nếu team đã chọn convention đó.
```

Sau khi Claude chỉnh, xem lại:

```bash
git diff --stat
```

Lệnh này cho biết tổng số file và dòng thay đổi. Output kỳ vọng: chỉ `CLAUDE.md` thay đổi. Rủi ro: nếu thấy file khác, dừng lại và review vì Day 05 chỉ cần sửa project instruction.

Nếu team chọn lưu project instructions ở `.claude/CLAUDE.md`, thay các lệnh diff tương ứng bằng path đó, ví dụ `git diff -- .claude/CLAUDE.md`.

### Bước 5: Kiểm tra session mới có load context

Thoát session hiện tại, mở session mới ở root `taskflow-ai`:

```bash
cd /path/to/taskflow-ai
claude
```

Lệnh này mở Claude Code tại đúng project directory. Output kỳ vọng là Claude sẵn sàng chat; dùng `/help` nếu cần xác nhận commands hiện có. Rủi ro: nếu bạn mở sai directory, Claude sẽ không load đúng `CLAUDE.md`.

Không dùng `claude --continue` để kiểm tra một context mới sạch, vì lệnh này tiếp tục session gần nhất trong thư mục hiện tại và có thể mang theo hội thoại cũ. Dùng `claude --resume` hoặc `/resume` khi mục tiêu là chọn lại một session cũ cụ thể.

Không cần bật `claude --permission-mode acceptEdits` cho bước kiểm tra context. Theo docs hiện hành, `acceptEdits` cho phép Claude tạo/sửa file và auto-approve một số command filesystem phổ biến trong working directory. `.claude/settings.json` có thể đặt `permissions.defaultMode` là `auto`, nhưng chỉ nên làm sau khi team thống nhất guardrails và đã kiểm tra official docs/CLI version đang dùng.

Gửi prompt kiểm tra:

```text
Không sửa file.
Hãy cho biết bạn đang hiểu gì về project taskflow-ai từ project instructions.

Trả lời ngắn:
- Stack chính.
- 5 command quan trọng và thư mục chạy.
- 5 rule workflow/security bắt buộc.
- Nếu không thấy CLAUDE.md hoặc không chắc, nói rõ thay vì đoán.
```

Kết quả tốt: Claude nhắc đúng stack, đúng command, đúng rule security/workflow từ `CLAUDE.md`. Kết quả chưa đạt: Claude trả lời chung chung, sai package manager, không biết command, hoặc không nói được rule security. Khi đó kiểm tra lại vị trí file, độ dài file, và session có mở đúng root không.

### Bước 6: Rollback nếu draft sai

Nếu `CLAUDE.md` đã được Git track và bạn muốn bỏ toàn bộ thay đổi trong file đó:

```bash
git restore -- CLAUDE.md
```

Lệnh này đưa `CLAUDE.md` về trạng thái trong commit hiện tại. Output thường không có gì nếu thành công. Rủi ro: mất toàn bộ thay đổi chưa commit trong file, kể cả phần bạn tự sửa. Chỉ dùng khi bạn chắc thay đổi trong file này là của mình hoặc đã được đồng đội xác nhận.

Nếu `CLAUDE.md` là file mới chưa track và bạn chắc chắn muốn xóa:

```bash
rm CLAUDE.md
```

Lệnh này xóa file ở thư mục hiện tại. Chỉ chạy sau khi `git status --short` xác nhận đúng file mới do bạn tạo. Rủi ro: xóa nhầm nếu bạn đang đứng sai thư mục hoặc xóa file người khác vừa tạo.

Trên PowerShell:

```powershell
Remove-Item -LiteralPath .\CLAUDE.md
```

Lệnh này xóa đúng file theo literal path. Rủi ro tương tự: chỉ dùng khi bạn chắc đang ở root `taskflow-ai`.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát repo để chuẩn bị viết CLAUDE.md.

Yêu cầu:
- Chỉ đọc file, chưa sửa gì.
- Nêu rõ file đã đọc.
- Xác định stack, cấu trúc thư mục, command trong package.json, test runner, Docker Compose nếu có.
- Nếu thông tin nào không có bằng chứng, đánh dấu "cần xác nhận".
```

### Prompt lập plan

```text
Lập plan tạo CLAUDE.md cho taskflow-ai.

Ràng buộc:
- Không implement trong bước này.
- Đề xuất section và nội dung chính cho từng section.
- Mỗi section phải có lý do tồn tại.
- Chỉ đưa rule hữu ích cho session Claude Code mới.
- Giữ file dưới 200 dòng và dễ scan như cheat sheet.
```

### Prompt implement

```text
Tạo hoặc cập nhật CLAUDE.md theo plan đã duyệt.

Giới hạn:
- Chỉ sửa file CLAUDE.md ở root repo.
- Không sửa README.md, package.json, source code, test, hoặc config.
- Không chạy npm install, migration, git add, git commit, git reset, git clean, hoặc lệnh xóa file.
- Sau khi sửa, tóm tắt diff và liệt kê điểm nào cần tôi xác nhận thủ công.
```

### Prompt review

```text
Review CLAUDE.md hiện tại như senior engineer chuẩn bị dùng trong team.

Tập trung:
- Có command nào sai hoặc thiếu thư mục chạy không.
- Có rule nào quá chung chung hoặc không actionable không.
- Có thông tin nhạy cảm, endpoint production, hoặc secret pattern không.
- Có làm tăng context/cost quá mức không.
- Có rule nào dễ khiến Claude sửa quá rộng không.
Không sửa file trong bước review này.
```

### Prompt kiểm tra session mới

```text
Đây là session mới trong taskflow-ai. Không đọc thêm file nếu chưa cần.

Hãy trả lời dựa trên project instructions đã load:
- Project này dùng stack gì?
- Khi sửa backend task API, workflow an toàn là gì?
- Command typecheck/test nào nên chạy và chạy ở đâu?
- Command nào không được tự chạy nếu chưa có xác nhận?
- Nếu bạn không thấy hoặc không chắc CLAUDE.md đã load, nói rõ.
```

## 6. Trade-offs

Đặt `CLAUDE.md` ở root dễ thấy với cả người và AI, phù hợp khi team muốn instruction là một phần chính thức của repo. Đặt ở `.claude/CLAUDE.md` giúp gom các artifact dành cho Claude Code vào một thư mục riêng. Cách nào cũng được, nhưng team nên chọn một convention nhất quán.

Dùng `/init` nhanh hơn viết từ đầu nếu CLI version hỗ trợ vì Claude có thể đọc repo và đề xuất draft. Đổi lại, draft cần review kỹ vì AI có thể suy luận nhầm package manager, test command, hoặc architecture boundary. Với repo production, `/init` nên là bước tạo nháp, không phải nguồn chân lý.

`CLAUDE.md` càng chi tiết thì Claude càng có nhiều chỉ dẫn, nhưng token/context cost tăng và nguy cơ stale cao hơn. File quá dài còn làm rule quan trọng bị chìm. File quá ngắn thì session mới vẫn phải hỏi lại nhiều. Điểm cân bằng là cheat sheet ngắn, có command chính xác và link tới tài liệu sâu.

Rule security nghiêm ngặt làm Claude chậm hơn vì phải hỏi trước khi chạy lệnh rủi ro. Đây là trade-off đáng chấp nhận trong team repo. Với sandbox workshop, bạn có thể nới lỏng một số rule, nhưng vẫn không nên đưa secret hoặc production data vào context.

Team-shared instruction giúp consistency giữa developer, nhưng có thể xung đột với thói quen cá nhân. Nội dung nào thuộc team policy thì commit vào `CLAUDE.md`; nội dung cá nhân hoặc local environment nên để trong local settings và không commit.

## 7. Best practices

- Giữ `CLAUDE.md` như onboarding checklist cho AI, không biến thành wiki.
- Viết command theo format: command, thư mục chạy, output kỳ vọng, rủi ro nếu có.
- Ưu tiên rule cụ thể: "không tự chạy `git reset --hard`" tốt hơn "hãy cẩn thận với Git".
- Không ghi secret, sample token thật, database URL thật, customer data, hoặc nội dung `.env`.
- Khi architecture thay đổi, cập nhật `CLAUDE.md` cùng PR để tránh project memory bị stale.
- Bắt Claude nêu file đã đọc trước khi sửa code production.
- Với task rủi ro, yêu cầu plan trước rồi mới edit. Nếu team muốn giảm prompt xác nhận, có thể cân nhắc `claude --permission-mode acceptEdits` hoặc `permissions.defaultMode: "auto"` trong `.claude/settings.json`, nhưng phải hiểu rằng chế độ này cho phép sửa file và auto-approve một số command filesystem phổ biến trong working directory.
- Không để Claude tự commit, push, chạy migration phá dữ liệu, drop table, xóa Docker volume, hoặc xóa file hàng loạt.
- Sau mỗi lần cập nhật `CLAUDE.md`, mở session mới để kiểm tra rule quan trọng có được load đúng không.
- Review `CLAUDE.md` như code: chính xác, ngắn, có owner, và có dấu hiệu khi stale.

## 8. Performance / cost / context

`CLAUDE.md` được nạp vào context của session, nên nội dung càng dài thì mỗi task càng tốn token hơn. Chi phí không chỉ là tiền; còn là độ nhiễu. Nếu file chứa lịch sử quyết định cũ, task đã xong, hoặc mô tả quá dài, Claude có thể ưu tiên sai thông tin khi lập plan.

Cách tối ưu:

- Giữ file dưới 200 dòng và tránh đoạn văn dài.
- Dùng bảng command ngắn thay vì đoạn văn dài.
- Chỉ ghi architecture boundary ổn định, không ghi chi tiết implementation dễ đổi.
- Link tới docs sâu thay vì paste toàn bộ vào `CLAUDE.md`.
- Tách rule global và task-specific: rule lâu dài ở `CLAUDE.md`, yêu cầu tạm thời ở prompt.
- Khi session dài bị nhiễu, mở session mới để kiểm tra lại `CLAUDE.md` thay vì tiếp tục chồng thêm prompt sửa sai.
- Nếu Claude phải đọc toàn repo ở mỗi task, `CLAUDE.md` đang thiếu command hoặc architecture map quan trọng.

Về performance thực thi, `CLAUDE.md` tốt giúp giảm số lần Claude chạy command thăm dò sai. Ví dụ biết chính xác `pnpm --filter api test` sẽ rẻ hơn việc Claude thử `npm test`, thất bại, đọc `package.json`, rồi thử lại.

## 9. Checklist cuối bài

- [ ] Tôi giải thích được vì sao Claude Code không nên được xem là có trí nhớ project vĩnh viễn.
- [ ] Tôi biết `CLAUDE.md` và `.claude/CLAUDE.md` dùng để lưu project instructions.
- [ ] Tôi đã dùng hoặc biết cách dùng `/init` để tạo draft `CLAUDE.md`.
- [ ] Tôi biết dùng `claude` để mở session tại project root, dùng `/help` để kiểm tra commands, và phân biệt `--continue`/`--resume` với session mới.
- [ ] Tôi biết review draft để loại bỏ suy đoán, command sai, rule chung chung, và thông tin nhạy cảm.
- [ ] Tôi có `CLAUDE.md` cho `taskflow-ai` gồm stack, architecture, commands, conventions, testing, security, workflow.
- [ ] Mỗi command quan trọng có thư mục chạy và output kỳ vọng.
- [ ] Security rules chặn secret, production data, destructive command, auto commit/push.
- [ ] Tôi đã mở session mới và kiểm tra Claude có load đúng instruction không.
- [ ] Tôi biết rollback `CLAUDE.md` bằng `git restore -- CLAUDE.md` hoặc xóa file mới một cách có kiểm soát.
- [ ] Tôi hiểu tác động của `CLAUDE.md` tới token, context, maintainability, và cost.

## 10. Bài tập

Bài cơ bản: chạy `/init` trong `taskflow-ai` để tạo draft `CLAUDE.md` nếu CLI version hỗ trợ; nếu không, dùng prompt tạo thủ công trong bài. Không accept nội dung ngay. Dùng `git diff -- CLAUDE.md` hoặc `git diff -- .claude/CLAUDE.md` để review và đánh dấu ít nhất 5 điểm cần xác nhận hoặc sửa.

Bài nâng cao: chỉnh `CLAUDE.md` thành cheat sheet ngắn, target dưới 200 dòng. File phải có đủ section Project, Structure, Commands, Coding Conventions, Testing, Security, Workflow. Mỗi command quan trọng phải ghi rõ chạy ở root, `apps/api`, `apps/web`, hoặc package tương ứng.

Bài áp dụng vào project cá nhân: chọn một repo bạn đang làm và viết `CLAUDE.md` tối giản cho repo đó. Sau đó mở session Claude Code mới, yêu cầu Claude tóm tắt project instructions đã load, rồi so sánh với file bạn viết.

Bài reflection: ghi lại 3 rule trong `CLAUDE.md` có tác động lớn nhất tới chất lượng code, 3 rule giúp giảm rủi ro security, và 3 rule giúp giảm token/context cost. Nếu rule nào không đo được hiệu quả, viết lại cho cụ thể hơn.
