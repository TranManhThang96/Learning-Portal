# Exercise — Day 04

## Bài 1 — Cơ bản

Mục tiêu: hiểu permission mode bằng thao tác read-only.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.
2. Chạy:

```bash
git status --short
```

Lệnh này kiểm tra working tree. Kết quả kỳ vọng là rỗng hoặc chỉ gồm file bạn biết rõ. Nếu có file lạ, ghi lại và không cho Claude sửa code.

3. Mở Claude Code:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude Code ở mode lập plan, phù hợp để đọc và phân tích trước khi edit.

4. Gửi prompt:

```text
Hãy đọc cấu trúc taskflow-ai và tìm module liên quan tới tasks.
Chưa sửa file.
Nêu rõ file đã đọc, entrypoint của luồng tạo task, và nơi phù hợp để validate title.
```

Kết quả cần có: danh sách file Claude đã đọc, mô tả luồng xử lý, và đề xuất điểm đặt validation.

## Bài 2 — Thực tế

Mục tiêu: cho Claude Code sửa một file nhỏ dưới sự kiểm soát của developer.

Yêu cầu:

1. Từ kết quả Bài 1, chọn một thay đổi nhỏ: task title sau khi trim không được rỗng.
2. Mở Claude Code bằng mode kiểm soát:

```bash
claude --permission-mode default --allowedTools "Read,Bash(git status *)"
```

Lệnh này pre-approve quyền đọc và command bắt đầu bằng `git status`; edit vẫn phải xin phép trong `default` mode. Kết quả kỳ vọng là session Claude Code sẵn sàng. Rủi ro: nếu thêm `Edit` hoặc mở rộng `Bash` quá nhiều, Claude có thể tự động làm nhiều hơn phạm vi bạn muốn.

3. Gửi prompt:

```text
Implement validation title theo plan.

Ràng buộc:
- Chỉ sửa đúng một file production mà plan đã chọn.
- Không đổi schema database.
- Không sửa file test trong bài này.
- Không chạy npm install, migration, git add, git commit, git reset, git clean, hoặc lệnh xóa file.
- Sau khi sửa, tóm tắt thay đổi và đề xuất test command.
```

4. Sau khi Claude sửa, tự chạy:

```bash
git diff --stat
```

Kết quả kỳ vọng: chỉ một file production thay đổi. Nếu nhiều hơn, dừng lại và chuyển sang phần debug trong `document.md`.

5. Xem chi tiết:

```bash
git diff
```

Kết quả kỳ vọng: validation nhỏ, đúng acceptance criteria, không đổi behavior ngoài phạm vi.

## Bài 3 — Nâng cao

Mục tiêu: so sánh `default`, `acceptEdits`, và `dontAsk` trong cùng một task.

Thực hiện trên branch dev hoặc repo copy, không làm trên branch chính.

Trước khi so sánh mode, kiểm tra CLI đang dùng:

```bash
claude --version
claude --help
```

`claude --version` in phiên bản Claude Code. `claude --help` cho biết `--permission-mode` hiện hỗ trợ những giá trị nào. Kết quả kỳ vọng là bạn xác nhận mode đang dùng tồn tại trong CLI hiện tại; rủi ro là tài liệu nội bộ có thể lệch nếu team dùng nhiều version khác nhau.

Phần A: `dontAsk`

```bash
claude --permission-mode dontAsk
```

Prompt:

```text
Review diff hiện tại và chỉ đề xuất rủi ro. Nếu cần chạy command hoặc sửa file, hãy mô tả để tôi tự quyết định. Không tự sửa.
```

Kỳ vọng: Claude đóng vai reviewer, không tự sửa các tool call cần quyền.

Phần B: `acceptEdits`

Chỉ làm nếu working tree sạch hoặc bạn đang ở repo copy:

```bash
claude -p "Apply a minimal lint-only cleanup to the task validation file. Do not change behavior." --permission-mode acceptEdits
```

Lệnh này chạy prompt một lần và auto-approve edits/common filesystem commands theo mode `acceptEdits`. Kết quả kỳ vọng là patch nhỏ hoặc thông báo không cần sửa. Rủi ro: nếu prompt không đủ hẹp, AI có thể đổi nhiều hơn lint-only.

Sau đó kiểm tra:

```bash
git diff --stat
git diff
```

Nếu patch không đúng:

```bash
git restore -- path/to/file
```

Chỉ thay `path/to/file` bằng file đã review và chắc chắn muốn rollback. Rủi ro: mất toàn bộ thay đổi chưa commit trong file đó.

Viết nhận xét ngắn: mode nào giúp bạn kiểm soát tốt nhất, mode nào nhanh nhất, và mode nào bạn sẽ cấm trong repo thật.

Phần C: `bypassPermissions`

Không chạy mode này trong bài tập trên repo thật. Chỉ viết một đoạn đánh giá ngắn:

```text
Tôi chỉ chấp nhận bypassPermissions khi:
- chạy trong container/VM throwaway hoặc CI sandbox cô lập;
- không có secret, production credential, customer data;
- không có network nhạy cảm hoặc đã chặn outbound không cần thiết;
- đã kiểm official docs và claude --version/--help của team;
- có cách reset môi trường sau bài lab.
```

## Bài 4 — Review & Reflection

Mục tiêu: biến trải nghiệm Day 04 thành rule làm việc cho team.

Trả lời các câu hỏi:

1. Trong `taskflow-ai`, loại task nào bắt buộc dùng `plan` trước khi sửa?
2. Lệnh nào bạn không bao giờ auto-approve? Liệt kê ít nhất 5 command hoặc nhóm command.
3. Khi Claude đề xuất sửa 6 file cho một bug nhỏ, bạn sẽ phản hồi bằng prompt nào?
4. Khi nào `bypassPermissions` có thể chấp nhận được, và điều kiện nào bắt buộc phải có trước khi dùng trong team?
5. Bạn sẽ viết rule gì vào `CLAUDE.md` hoặc `.claude/CLAUDE.md` ở Day 05 để kiểm soát permission và destructive commands?

Gợi ý prompt reflection:

```text
Dựa trên workflow hôm nay, hãy giúp tôi soạn 8 rule an toàn cho CLAUDE.md của taskflow-ai.
Không thêm rule chung chung.
Mỗi rule phải có ví dụ command hoặc hành vi cụ thể.
Phân biệt rule hướng dẫn trong CLAUDE.md với permission rule enforce trong .claude/settings.json.
```

## Tiêu chí hoàn thành

- Đã chạy `git status --short` trước khi cho Claude Code sửa.
- Đã dùng `plan` mode để yêu cầu Claude khảo sát và lập plan.
- Đã implement một thay đổi nhỏ với file scope rõ ràng.
- Đã review `git diff --stat` và `git diff` trước khi accept.
- Đã ghi lại ít nhất 5 destructive commands không auto-approve.
- Đã rollback được một file trong repo copy hoặc giải thích được chính xác khi nào dùng `git restore -- path`.
- Không có commit tự động do Claude Code tạo ra.
- Đã giải thích được vì sao không chạy `bypassPermissions` ngoài sandbox cô lập.

## Gợi ý nếu bí

Nếu không tìm được module tasks, dùng prompt:

```text
Hãy tìm file định nghĩa route/controller/service liên quan tới task hoặc todo.
Chỉ đọc file.
Nếu project chưa có module tasks, hãy nói rõ trạng thái hiện tại và đề xuất một file nhỏ nhất để thêm validation demo, nhưng chưa tạo file.
```

Nếu Claude muốn sửa nhiều file, dùng prompt:

```text
Phạm vi này quá rộng. Hãy thu hẹp về thay đổi nhỏ nhất.
Chỉ chọn 1 file production.
Không implement.
Giải thích trade-off nếu không sửa test trong bước này.
```

Nếu Claude xin chạy command nguy hiểm, dùng phản hồi:

```text
Không chạy command đó. Hãy giải thích command làm gì, rủi ro là gì, và có lệnh read-only nào thay thế để kiểm tra trạng thái không.
```

Nếu diff quá dài, chạy:

```bash
git diff --stat
```

Sau đó xem từng file:

```bash
git diff -- path/to/file
```

## Đáp án tham khảo hoặc kết quả kỳ vọng

Kết quả kỳ vọng cho Bài 1:

- Claude xác định được file/module liên quan tới tasks.
- Claude chưa sửa file.
- Plan nêu đúng điểm đặt validation và lý do.

Kết quả kỳ vọng cho Bài 2:

- Diff chỉ chạm một file production.
- Logic validation xử lý được title rỗng sau khi trim.
- Claude không chạy `npm install`, migration, Git lệnh destructive, hoặc commit.

Ví dụ diff summary chấp nhận được:

```text
1 file changed, 4 insertions(+)
```

Ví dụ behavior mong muốn:

```text
Input title: "   "
Kết quả kỳ vọng: request bị reject bằng lỗi validation hiện có của project.
```

Kết quả kỳ vọng cho Bài 3:

- Bạn phân biệt được `dontAsk` là phù hợp cho review/read-only.
- Bạn thấy `acceptEdits` nhanh hơn nhưng cần prompt hẹp và branch sạch.
- Bạn không dùng `bypassPermissions` ngoài sandbox cô lập, và biết phải kiểm docs/CLI version trước khi đề xuất cho team.

Kết quả kỳ vọng cho Bài 4:

Rule mẫu có thể đưa vào `CLAUDE.md` hoặc `.claude/CLAUDE.md` Day 05:

```text
- Luôn lập plan trước khi sửa code production.
- Không chạy destructive commands như rm -rf, git reset --hard, git clean -fd, docker compose down -v, migration drop/truncate nếu chưa có xác nhận thủ công.
- Với bug nhỏ, chỉ sửa tối đa 1 file production trước khi review diff.
- Sau mọi edit, báo git diff summary và test command đề xuất; không tự commit.
- Không dùng bypassPermissions trên máy làm việc chính; chỉ dùng trong sandbox throwaway đã xác minh version/docs.
```

Permission rule enforce tương ứng có thể đặt trong `.claude/settings.json`:

```json
{
  "permissions": {
    "defaultMode": "default",
    "deny": [
      "Read(./.env)",
      "Bash(git reset *)",
      "Bash(git clean *)",
      "Bash(docker compose down -v*)"
    ]
  }
}
```
