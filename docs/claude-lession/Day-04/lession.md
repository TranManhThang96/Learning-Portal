# Day 04 — Permission modes và an toàn khi cho AI sửa code

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Giải thích được permission mode trong Claude Code là gì và vì sao nó là guardrail quan trọng khi AI có quyền đọc file, sửa file, và chạy lệnh.
- Chọn đúng chế độ `default`, `plan`, `acceptEdits`, `auto`, `dontAsk`, hoặc `bypassPermissions` theo mức rủi ro của task.
- Thiết kế workflow plan-first: yêu cầu Claude Code khảo sát, lập plan, xin xác nhận, rồi mới sửa code.
- Cho phép Claude Code sửa một file nhỏ trong project `taskflow-ai` và review diff trước khi accept hoặc commit.
- Nhận diện rủi ro của auto-approve command, đặc biệt với lệnh destructive như xóa file, reset Git, migration phá dữ liệu, hoặc thao tác production data.

## 2. Bối cảnh thực tế

Khi dùng Claude Code, developer không chỉ hỏi đáp với chatbot. Claude Code có thể đọc repo, đề xuất patch, chỉnh file, và chạy command trong terminal. Đây là điểm mạnh, nhưng cũng là điểm làm tăng rủi ro: một prompt mơ hồ có thể dẫn tới thay đổi rộng, chạy test tốn thời gian, sửa nhầm file, hoặc thực thi command không nên chạy.

Trong project `taskflow-ai`, giả sử bạn đang muốn thêm validation nhỏ cho task title. Nếu cho AI quyền sửa toàn repo ngay từ đầu, nó có thể đổi schema, đổi API contract, hoặc viết lại module tasks quá rộng. Workflow tốt hơn là yêu cầu Claude Code đọc file liên quan trong `plan` mode, trình bày plan, sau đó chỉ cho phép sửa đúng một file nhỏ.

Không nên dùng Claude Code để tự động sửa khi:

- Bạn đang làm việc trên branch có thay đổi chưa commit mà chưa hiểu rõ trạng thái.
- Task liên quan tới production credential, dữ liệu thật, migration nguy hiểm, billing, hoặc auth/security boundary.
- Bạn chưa có test hoặc chưa biết cách verify behavior sau khi sửa.
- Bạn cần quyết định kiến trúc lớn nhưng chưa thống nhất acceptance criteria với team.

## 3. Kiến thức nền

Permission mode là cách Claude Code quyết định tool call nào được chạy ngay, tool call nào cần hỏi bạn, và tool call nào bị từ chối. Tool call có thể là đọc file, sửa file, chạy shell command, dùng MCP tool, hoặc thao tác filesystem.

Các mode cần nhớ:

| Mode | Ý nghĩa | Khi nên dùng | Rủi ro chính |
| --- | --- | --- | --- |
| `default` | Hỏi quyền khi tool được dùng lần đầu hoặc khi cần xác nhận. | Học hằng ngày, task chưa rõ phạm vi, repo cá nhân hoặc team repo. | Dễ bấm approve theo thói quen nếu không đọc kỹ. |
| `plan` | Cho phép đọc file và chạy shell lệnh read-only để khảo sát, không sửa code. | Bắt đầu mọi task có rủi ro: refactor, bug fix, migration, security. | Plan có thể thiếu file nếu prompt không yêu cầu Claude chỉ rõ bằng chứng. |
| `acceptEdits` | Tự approve file edits và một số command filesystem phổ biến trong working directory. | Task nhỏ, file rõ, branch sạch, đã có test, đang trong sandbox/dev repo. | AI có thể sửa/tạo/di chuyển file nhiều hơn mong muốn nếu prompt không giới hạn. |
| `auto` | Tự approve theo safety checks nền; docs hiện hành mô tả đây là research preview. | Task lặp lại, repo đã có guardrails, môi trường dev không chứa dữ liệu nhạy cảm. | Safety check không thay thế review của developer. |
| `dontAsk` | Tự deny tool call cần hỏi quyền, trừ các rule đã pre-approved hoặc read-only Bash command. | Môi trường cần khóa chặt, demo read-only, audit repo, hoặc khi muốn ép Claude chỉ đề xuất. | Claude có thể không hoàn thành task nếu thiếu quyền cần thiết. |
| `bypassPermissions` | Bỏ qua gần như toàn bộ prompt permission. Chỉ cân nhắc trong sandbox cô lập như container/VM throwaway, tốt nhất không có secret và không có network nhạy cảm. | CI sandbox, container throwaway, repo copy, workshop lab có thể reset. | Rất nguy hiểm trên máy thật hoặc repo có secret/data thật; circuit breaker không thay thế sandbox. |

Một nguyên tắc thực tế: permission mode không thay thế Git hygiene. Trước khi để AI sửa code, bạn vẫn cần biết branch nào đang active, working tree có gì, và rollback bằng cách nào.

Với team, đừng ghi nhớ mode theo truyền miệng. Trước khi chuẩn hóa `auto`, `dontAsk`, hoặc `bypassPermissions`, hãy kiểm tra official docs và CLI đang dùng:

```bash
claude --version
claude --help
```

Chạy ở terminal bất kỳ. `claude --version` in phiên bản Claude Code, còn `claude --help` liệt kê flag và mode hiện có. Rủi ro: nếu team dùng nhiều phiên bản CLI khác nhau, cùng một rule trong tài liệu nội bộ có thể không còn đúng. Với cấu hình lâu dài, dùng `.claude/settings.json` để đặt `permissions.defaultMode` hoặc rule `allow`/`ask`/`deny`, và dùng `CLAUDE.md` hoặc `.claude/CLAUDE.md` để ghi coding standards, testing requirements, common commands. Prompt và `CLAUDE.md` là hướng dẫn hành vi; permission settings mới là lớp enforce.

## 4. Step-by-step thực hành

Mục tiêu thực hành: dùng Claude Code để thêm rule validation nhỏ cho `taskflow-ai`: task title không được rỗng sau khi trim. Nếu project của bạn chưa có đúng file ví dụ, hãy yêu cầu Claude Code tìm file tương đương trước, không tự tạo kiến trúc mới.

### Bước 1: Kiểm tra trạng thái repo

Chạy trong thư mục gốc project `taskflow-ai`:

```bash
git status --short
```

Lệnh này hiển thị các file đang thay đổi ở dạng ngắn. Kết quả kỳ vọng là rỗng hoặc chỉ có những file bạn hiểu rõ. Nếu thấy file lạ, dừng lại và đọc trước khi cho Claude Code sửa. Rủi ro: nếu working tree đã bẩn, bạn có thể nhầm thay đổi của mình với thay đổi do AI tạo ra.

Nếu muốn xem branch hiện tại:

```bash
git branch --show-current
```

Lệnh này in ra tên branch đang dùng. Kết quả kỳ vọng là branch feature, ví dụ `feature/task-validation`, không phải `main`. Rủi ro: làm trực tiếp trên protected branch khiến review và rollback khó hơn.

### Bước 2: Mở Claude Code ở `plan` mode

Nếu chưa ở đúng thư mục project, chạy:

```bash
cd /path/to/your/project
claude
```

`cd` đưa terminal vào đúng project, còn `claude` mở session tương tác mặc định. Trong bài này, `/path/to/your/project` là thư mục gốc `taskflow-ai`. Trong session, dùng `/help` để xem command đang có. Đây là flow khởi động cơ bản trước khi bạn chọn mode nâng cao.

Để vào thẳng `plan` mode, chạy:

```bash
claude --permission-mode plan
```

Lệnh này mở session Claude Code với quyền ưu tiên đọc và khảo sát. Kết quả kỳ vọng là giao diện Claude Code sẵn sàng nhận prompt. Rủi ro thấp vì mode này không cho sửa file, nhưng Claude vẫn có thể đưa plan sai nếu chưa đọc đủ file.

Prompt đầu tiên:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát module quản lý tasks và lập plan để thêm validation: task title sau khi trim không được rỗng.

Ràng buộc:
- Chưa sửa file.
- Chỉ đọc file cần thiết.
- Nêu rõ file nào đã đọc và bằng chứng từ code.
- Đề xuất tối đa 1 file production và 1 file test cần sửa.
- Nếu thiếu thông tin, hỏi lại trước.
```

Kỳ vọng: Claude Code liệt kê file đã đọc, mô tả flow hiện tại, và đề xuất plan nhỏ. Nếu Claude đề xuất sửa quá nhiều file, yêu cầu thu hẹp phạm vi.

Nếu bạn phải tạm dừng, có hai cách quay lại:

```bash
claude --continue
claude --resume
```

`claude --continue` tiếp tục session gần nhất trong thư mục hiện tại. `claude --resume` mở lựa chọn session để bạn chọn đúng cuộc hội thoại; trong session tương tác cũng có thể dùng `/resume`. Rủi ro: resume nhầm session có thể mang context cũ vào task mới, nên luôn yêu cầu Claude tóm tắt trạng thái trước khi cho sửa tiếp.

### Bước 3: Chỉ cho phép sửa một file nhỏ

Sau khi đồng ý plan, mở session mới hoặc tiếp tục session nhưng giữ ràng buộc rõ:

```bash
claude --permission-mode default --allowedTools "Read,Bash(git status *)"
```

Lệnh này chạy Claude Code ở `default` mode và chỉ pre-approve quyền đọc file cùng command bắt đầu bằng `git status`. Edit vẫn phải xin phép; bạn chỉ accept nếu đúng file đã thống nhất trong plan. Rủi ro: `--allowedTools` quá rộng như `"Bash,Read,Edit"` có thể cho AI chạy nhiều command hơn mức cần thiết hoặc auto-approve edit rộng; chỉ dùng rộng trong sandbox.

Prompt implement:

```text
Thực hiện plan đã thống nhất.

Giới hạn:
- Chỉ sửa file production nhỏ nhất cần thiết.
- Không đổi API contract nếu không bắt buộc.
- Không chạy npm install, migration, git add, git commit, git reset, hoặc lệnh xóa file.
- Sau khi sửa, tóm tắt diff và nêu command test tôi nên tự chạy.
```

Kỳ vọng: Claude chỉ sửa một file nhỏ, ví dụ handler/service validation. Nếu Claude xin chạy lệnh không nằm trong phạm vi, đọc kỹ trước khi approve.

### Bước 4: Review diff trước khi accept

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này cho biết có bao nhiêu file và bao nhiêu dòng thay đổi. Kết quả kỳ vọng là 1 file production, hoặc tối đa thêm 1 file test nếu bạn đã cho phép. Rủi ro: nếu số file tăng bất thường, bạn cần dừng và review từng file.

Xem diff chi tiết:

```bash
git diff
```

Lệnh này hiển thị toàn bộ thay đổi chưa staged. Kết quả kỳ vọng là patch nhỏ, đúng acceptance criteria, không có đổi format hàng loạt, không chạm secret, không đổi config nhạy cảm. Rủi ro: diff dài làm bạn dễ bỏ sót behavior change; dùng `git diff -- path/to/file` để xem từng file nếu cần.

Nếu chỉ muốn xem một file:

```bash
git diff -- backend/src/tasks/task.service.ts
```

Lệnh này giới hạn diff vào file cụ thể. Hãy thay path theo file thật trong repo của bạn. Kết quả kỳ vọng là thay đổi validation nhỏ. Rủi ro thấp, vì đây là lệnh read-only.

### Bước 5: Chạy test do bạn kiểm soát

Ví dụ nếu backend dùng npm script:

```bash
npm test -- --runInBand
```

Lệnh này chạy test suite theo cấu hình project. Chạy ở thư mục package chứa `package.json`, có thể là root hoặc `backend`. Kết quả kỳ vọng là test pass. Rủi ro: test có thể tốn thời gian hoặc phụ thuộc service ngoài; đọc script trong `package.json` trước nếu chưa chắc.

Nếu project dùng Vitest:

```bash
npm run test -- --run
```

Lệnh này chạy Vitest một lần thay vì watch mode. Kết quả kỳ vọng là danh sách test pass và exit code 0. Rủi ro: nếu test chạm database local, cần chắc chắn đang dùng database dev/test, không phải production.

### Bước 6: Rollback nếu Claude Code làm sai

Trước khi rollback, xem lại file nào bị thay đổi:

```bash
git status --short
```

Nếu chắc chắn muốn bỏ thay đổi trong một file:

```bash
git restore -- backend/src/tasks/task.service.ts
```

Lệnh này đưa file về trạng thái trong Git index/HEAD. Chạy ở root repo. Kết quả thường không có gì nếu thành công. Rủi ro: mất toàn bộ thay đổi chưa commit trong file đó, kể cả thay đổi do bạn tự viết. Không chạy lệnh này nếu bạn chưa đọc diff.

Không dùng các lệnh sau theo đề xuất tự động của AI nếu chưa tự quyết định:

```bash
rm -rf node_modules
git reset --hard
git clean -fd
docker compose down -v
```

Những lệnh này có thể xóa file, mất thay đổi local, hoặc xóa volume database. Nếu cần chạy, developer phải tự đọc, tự hiểu, và tự chạy.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```text
Hãy đọc module tasks trong taskflow-ai để hiểu luồng tạo task.

Yêu cầu:
- Chỉ đọc file, chưa sửa gì.
- Nêu rõ file đã đọc.
- Vẽ luồng request từ route/controller tới service/repository nếu có.
- Chỉ ra nơi validation title nên đặt và vì sao.
```

### Prompt lập plan

```text
Lập plan thêm validation: task title sau khi trim không được rỗng.

Ràng buộc:
- Plan tối đa 5 bước.
- Mỗi bước ghi file dự kiến chạm vào.
- Không đổi schema database.
- Không đổi response format trừ khi code hiện tại đã có pattern lỗi validation.
- Chờ tôi approve trước khi sửa.
```

### Prompt implement

```text
Implement theo plan đã duyệt.

Chỉ sửa file: backend/src/tasks/task.service.ts.
Không sửa file khác.
Không chạy lệnh destructive.
Sau khi sửa, báo diff summary và đề xuất test command, nhưng không tự commit.
```

### Prompt review

```text
Review diff hiện tại như senior backend reviewer.

Tập trung:
- Behavior có đúng acceptance criteria không.
- Có đổi contract ngoài ý muốn không.
- Edge case: title là khoảng trắng, null, undefined, chuỗi dài.
- Test nào còn thiếu.
Không sửa file trong bước review này.
```

### Prompt viết test

```text
Đề xuất test tối thiểu cho validation title.

Ràng buộc:
- Đọc test pattern hiện có trước.
- Chỉ đề xuất test case và file cần sửa.
- Không viết test cho đến khi tôi approve.
```

## 6. Trade-offs

`plan` mode chậm hơn vì bạn tách bước khảo sát khỏi bước implement, nhưng đổi lại giảm rủi ro sửa nhầm. Với repo team hoặc task chưa rõ, đây là trade-off đáng chọn.

`default` mode cân bằng giữa tốc độ và kiểm soát. Bạn vẫn phải đọc prompt xin quyền, nhưng Claude không bị khóa quá chặt. Đây là mode phù hợp nhất cho phần lớn công việc hằng ngày.

`acceptEdits` tăng tốc khi bạn đã có phạm vi hẹp và test rõ. Đổi lại, edit và một số thao tác filesystem trong working directory có thể được approve tự động, nên bạn có thể nhận patch nhiều hơn dự kiến nếu prompt không giới hạn file. Chỉ dùng khi branch sạch và bạn sẵn sàng review diff ngay.

`auto` và `bypassPermissions` tối ưu tốc độ nhưng tăng trách nhiệm của môi trường chạy. `auto` vẫn cần review vì classifier/safety check có thể hiểu sai intent. `bypassPermissions` chỉ nên là lựa chọn cho sandbox cô lập, đã xác minh official docs và `claude --version`/`claude --help`; nếu môi trường không sandbox, không có backup, hoặc có secret thật, lợi ích tốc độ không đáng với rủi ro.

`dontAsk` phù hợp khi bạn muốn Claude đóng vai trò reviewer hoặc planner, không phải implementer. Điểm bất tiện là Claude có thể bị chặn khi cần thao tác hợp lý, nên prompt phải nói rõ: nếu thiếu quyền, hãy mô tả command để tôi tự chạy.

## 7. Best practices

- Bắt đầu task bằng `plan` mode khi scope chưa rõ, khi sửa module quan trọng, hoặc khi có nhiều file liên quan.
- Trước khi cho AI sửa, chạy `git status --short` và hiểu toàn bộ working tree.
- Giới hạn bằng prompt: file nào được sửa, file nào không được sửa, lệnh nào không được chạy.
- Với `--allowedTools`, ưu tiên rule hẹp như `Bash(git status *)` hoặc `Bash(git diff *)` thay vì cho toàn bộ `Bash`.
- Giữ destructive commands ở chế độ manual: `rm`, `git reset --hard`, `git clean`, `docker compose down -v`, migration drop table, force push, hoặc lệnh chạm production data.
- Không đưa `.env`, token, private key, production credential, customer data vào prompt hoặc file training context.
- Ghi rule lặp lại vào `CLAUDE.md` hoặc `.claude/CLAUDE.md`, nhưng dùng `.claude/settings.json`/managed settings nếu team cần enforce permission thật.
- Với team repo, cân nhắc deny rule cho file nhạy cảm như `Read(./.env)` và command nguy hiểm như `Bash(git reset *)`, `Bash(git clean *)`, `Bash(docker compose down -v*)`.
- Review diff trước khi accept hoặc commit. AI có thể viết code hợp lý nhưng vẫn sai architecture, sai convention, hoặc thiếu edge case.
- Với team workflow, yêu cầu Claude tạo summary dạng PR note, nhưng human vẫn review patch cuối.

## 8. Performance / cost / context

Permission mode ảnh hưởng trực tiếp tới thời gian và token. `plan` mode thường tốn thêm lượt hội thoại vì Claude phải khảo sát và giải thích trước, nhưng tiết kiệm chi phí sửa sai. Một patch sai trên 8 file thường tốn nhiều token để debug hơn một plan cẩn thận ban đầu.

Cách tối ưu:

- Đưa context hẹp: nêu module, file nghi ngờ, acceptance criteria, test command.
- Yêu cầu Claude liệt kê file đã đọc thay vì đọc toàn repo.
- Chia task thành 3 lượt: explore, plan, implement. Không gộp refactor, feature, test, docs vào một prompt.
- Dùng `dontAsk` hoặc `plan` cho audit/read-only để tránh tool call sửa file không cần thiết.
- Sau khi implement, dùng `git diff --stat` trước rồi mới xem diff chi tiết để tiết kiệm thời gian review.

## 9. Checklist cuối bài

- [ ] Tôi giải thích được từng permission mode và rủi ro của nó.
- [ ] Tôi biết khi nào nên dùng `plan` trước khi sửa code.
- [ ] Tôi đã chạy `git status --short` trước khi cho Claude Code edit.
- [ ] Tôi đã yêu cầu Claude Code chỉ sửa một file nhỏ trong `taskflow-ai`.
- [ ] Tôi đã review `git diff --stat` và `git diff` trước khi accept.
- [ ] Tôi không auto-approve destructive commands.
- [ ] Tôi biết cách rollback một file bằng `git restore -- path`, và hiểu rủi ro mất thay đổi chưa commit.
- [ ] Tôi có thể viết prompt giới hạn file, command, và acceptance criteria.
- [ ] Tôi biết kiểm tra `claude --version`, `claude --help`, và official docs trước khi đề xuất mode rủi ro cho team.

## 10. Bài tập

Bài 1 - Cơ bản: mở `taskflow-ai` bằng `claude --permission-mode plan`, yêu cầu Claude Code khảo sát module tasks và lập plan cho validation title. Không cho sửa file.

Bài 2 - Thực tế: chuyển sang `default` với `--allowedTools` hẹp, cho phép sửa đúng một file nhỏ. Sau đó dùng `git diff --stat` và `git diff` để review. Nếu patch quá rộng, rollback file đó và yêu cầu plan lại.

Bài 3 - Nâng cao: trong repo copy hoặc sandbox, so sánh `default`, `dontAsk`, và `acceptEdits` cho cùng một task nhỏ. Không chạy `bypassPermissions`; chỉ mô tả điều kiện an toàn nếu team thật sự cần.

Bài 4 - Review & Reflection: chọn một bug nhỏ trong repo cá nhân, viết prompt theo format Context, Goal, Constraints, Acceptance Criteria, Verification. Từ trải nghiệm đó, soạn rule đưa vào `CLAUDE.md` hoặc `.claude/CLAUDE.md`: plan trước, sửa nhỏ, review diff, chạy test, không commit tự động.
