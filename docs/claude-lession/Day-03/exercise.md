# Exercise — Day 03

## Bài 1 — Cơ bản
Mục tiêu: tạo session riêng và yêu cầu Claude Code phân tích `taskflow-ai` ở chế độ read-only.

Thực hiện:

1. Mở terminal ở thư mục chứa project `taskflow-ai`.
2. Chạy:

```bash
cd taskflow-ai
```

Lệnh làm gì: vào project thực hành.

Kết quả kỳ vọng: terminal đang đứng trong thư mục `taskflow-ai`.

Rủi ro: nếu vào sai project, session và context sẽ sai.

3. Chạy:

```bash
git status --short
```

Lệnh làm gì: kiểm tra working tree trước khi bắt đầu.

Kết quả kỳ vọng: repo sạch hoặc bạn biết rõ các file đang thay đổi.

Rủi ro: nếu có file lạ, không yêu cầu Claude sửa hoặc rollback trước khi hiểu nguồn gốc.

4. Chạy:

```bash
claude
```

Lệnh làm gì: mở Claude Code interactive session trong đúng thư mục `taskflow-ai`.

Kết quả kỳ vọng: Claude Code interactive session mở trong terminal.

Rủi ro: nếu CLI chưa setup, quay lại Day 02.

Nếu không chắc command nào có sẵn trong Claude Code, nhập:

```text
/help
```

Lệnh làm gì: xem danh sách command hiện có trong interactive session.

Kết quả kỳ vọng: bạn thấy các command liên quan như resume, clear, compact tùy phiên bản CLI.

Rủi ro: không có rủi ro ghi file.

5. Nhập prompt:

```text
Hãy phân tích repo taskflow-ai ở mức tổng quan để tạo mental model ban đầu.
Không sửa file, không chạy lệnh destructive.

Trả lời theo format:
- Stack đã xác minh
- Folder/file quan trọng đã đọc
- Điều đang suy luận nhưng chưa xác minh
- Rủi ro context nếu tiếp tục task lớn
- Summary dưới 20 dòng
```

Kết quả cần có: Claude nêu được stack/folder chính và phân biệt rõ phần đã đọc với phần chưa xác minh.

## Bài 2 — Thực tế
Mục tiêu: tạo summary context đủ dùng để resume sau này.

Trong cùng session vừa mở, nhập:

```text
Hãy tạo "Context Summary — Day 03" cho taskflow-ai.

Yêu cầu:
1. Tối đa 30 dòng.
2. Không chứa secret, token, credential, hoặc dữ liệu thật.
3. Gồm goal, repo mental model, file đã đọc, constraint, câu hỏi còn mở, và next step.
4. Đánh dấu rõ nội dung nào "đã xác minh" và nội dung nào "chưa xác minh".
```

Sau khi Claude trả lời, tự review summary:

- Có path cụ thể không?
- Có assumption nào cần sửa không?
- Có nhắc lại constraint read-only không?
- Có next step nhỏ và kiểm chứng được không?

Tùy chọn: nếu muốn lưu lại trong repo học tập cá nhân, yêu cầu Claude tạo file trong project của bạn, ví dụ `docs/context-summary-day03.md`. Trước khi cho tạo file, kiểm tra đây có phải repo cá nhân và không ảnh hưởng worker khác.

Kết quả cần có: một summary ngắn có thể dùng để khởi động lại context mà không cần paste toàn bộ transcript.

Không bật `claude --permission-mode acceptEdits` cho bài này nếu mục tiêu vẫn là read-only. Mode đó cho phép tạo/sửa file và auto-approve các filesystem command phổ biến trong working directory, nên chỉ phù hợp khi bạn đã chốt write scope.

## Bài 3 — Nâng cao
Mục tiêu: thực hành compact, resume, và kiểm tra Claude còn hiểu đúng không.

1. Trong Claude Code, chạy:

```text
/compact Giữ lại goal Day 03, repo mental model của taskflow-ai, file đã đọc, phần chưa xác minh, constraint an toàn, lệnh đã chạy, và next step. Bỏ trao đổi ngoài lề.
```

Lệnh làm gì: compact session với instruction cụ thể.

Chạy ở đâu: trong Claude Code interactive prompt.

Kết quả kỳ vọng: session tiếp tục với context gọn hơn.

Rủi ro: summary sau compact có thể thiếu chi tiết; cần kiểm tra lại ngay.

2. Ngay sau compact, nhập:

```text
Không đọc thêm file. Hãy trả lời 6 câu:
1. Goal hiện tại là gì?
2. Stack nào đã xác minh?
3. File/folder nào đã đọc thật sự?
4. Điều gì chưa xác minh?
5. Constraint an toàn nào đang áp dụng?
6. Next step nhỏ nhất nếu muốn thêm GET /tasks là gì?
```

3. Thoát Claude Code, vẫn đứng trong thư mục `taskflow-ai`, rồi chạy:

```bash
claude --continue
```

Lệnh làm gì: resume session gần nhất trong thư mục `taskflow-ai`.

Kết quả kỳ vọng: mở lại đúng session vừa compact.

Rủi ro: nếu session gần nhất không phải session Day 03 vừa dùng, bạn có thể resume nhầm.

4. Nếu nghi ngờ resume nhầm, chạy:

```bash
claude --resume
```

Lệnh làm gì: mở danh sách session để chọn đúng conversation.

Kết quả kỳ vọng: thấy session hoặc nội dung liên quan Day 03.

Rủi ro: chọn nhầm session sẽ làm task mới bị nhiễu bởi context cũ.

5. Sau khi resume, nhập:

```text
Chúng ta vừa resume. Hãy tự kiểm tra context:
- Bạn có chắc đây là session Day 03 không?
- Bạn nhớ goal và constraint nào?
- Bạn cần đọc lại file nào để xác minh trước khi implement?
Không sửa file.
```

Kết quả cần có: Claude nhận diện đúng goal, không bịa file đã đọc, và đề xuất bước xác minh hợp lý.

## Bài 4 — Review & Reflection
Mục tiêu: rèn thói quen đánh giá context như đánh giá code.

Trả lời ngắn trong notes cá nhân:

- Context của session có bị nhiễu ở điểm nào không?
- Prompt nào làm Claude trả lời tốt nhất? Vì sao?
- Prompt nào quá rộng hoặc tạo output dài?
- Khi nào bạn sẽ dùng `/clear` thay vì `/compact`?
- Khi nào bạn sẽ dùng `claude --resume` thay vì `claude --continue`?
- Nếu làm việc trong team, bạn sẽ ghi ownership file cho Claude như thế nào?

Sau đó yêu cầu Claude review chính session:

```text
Hãy review workflow Day 03 của tôi như một senior engineer.
Tập trung vào rủi ro context, assumption chưa xác minh, command có thể nguy hiểm, và cách chia task.
Không khen chung chung. Hãy đưa finding cụ thể và cách sửa.
```

Kết quả cần có: ít nhất 3 finding cụ thể về cách bạn quản lý context.

## Tiêu chí hoàn thành
- Tạo được session Claude Code trong đúng thư mục `taskflow-ai`.
- Biết kiểm tra repo trước khi mở Claude bằng `git status --short`.
- Có summary context cho `taskflow-ai` gồm goal, mental model, file đã đọc, constraint, câu hỏi còn mở.
- Đã dùng `/compact` với instruction cụ thể.
- Đã thử resume bằng `claude --continue` hoặc `claude --resume`.
- Sau resume, kiểm tra được Claude còn hiểu đúng project hay không.
- Biết khi nào dùng `/clear` cho task không liên quan.
- Không đưa secret, production data, hoặc log quá dài vào context.
- Không để Claude sửa file khi bài tập chỉ yêu cầu phân tích read-only.
- Không dùng `acceptEdits` cho bài read-only nếu chưa có write scope rõ.

## Gợi ý nếu bí
- Nếu Claude trả lời quá chung, yêu cầu: "Hãy dẫn path cụ thể và nói rõ đã đọc file nào".
- Nếu Claude muốn sửa code, nhắc lại: "Read-only. Không edit file trong bài này".
- Nếu không thấy session đúng khi resume, dùng `claude --resume` thay vì `claude --continue`.
- Nếu summary quá dài, yêu cầu rút xuống 20-30 dòng và bỏ log chi tiết.
- Nếu Claude quên constraint sau compact, compact instruction của bạn chưa đủ rõ; hãy tạo summary thủ công trước.
- Nếu repo chưa có nhiều file vì Day 02 chưa hoàn thành, dùng chính cấu trúc hiện có và đánh dấu phần còn thiếu là "chưa xác minh".
- Nếu không chắc command slash nào đúng, dùng `/help` trong Claude Code trước khi thao tác.

## Đáp án tham khảo hoặc kết quả kỳ vọng
Kết quả kỳ vọng cho summary context:

```text
Context Summary — Day 03
- Goal: học session/context management trên taskflow-ai, chưa implement feature mới.
- Repo mental model: backend, frontend, test/devops nếu đã có; chi tiết nào chưa đọc thì đánh dấu chưa xác minh.
- File đã đọc: package/config/folder chính, kèm path cụ thể.
- Constraint: read-only trong bài Day 03; không sửa README; không chạy lệnh destructive; không đưa secret vào context.
- Đã xác minh: chỉ các điểm có file/path hoặc command output.
- Chưa xác minh: API routes, database schema, test setup nếu Claude chưa đọc file tương ứng.
- Lệnh đã chạy: git status --short; các command khác nếu có.
- Next step: trước khi thêm GET /tasks, đọc entrypoint backend, route registration, test setup, và data model hiện có.
```

Kết quả kỳ vọng sau `/compact`:

- Claude vẫn nhớ goal Day 03 là quản lý session/context, không phải implement feature.
- Claude nêu được file/folder đã đọc thật sự.
- Claude không khẳng định stack hoặc schema nếu chưa xác minh.
- Claude nhắc lại constraint an toàn.
- Claude đề xuất next step nhỏ, ví dụ đọc backend entrypoint trước khi lập plan API.

Kết quả kỳ vọng sau resume:

- `claude --continue` mở lại session gần nhất nếu bạn không tạo session khác sau đó.
- `claude --resume` cho phép chọn đúng session nếu có nhiều session.
- Claude trả lời được goal, constraint, điều đã xác minh, và điều cần xác minh tiếp.

Nếu kết quả không đạt, không cố implement tiếp. Hãy dùng `/clear` cho task mới hoặc tạo lại summary context ngắn, chính xác hơn.
