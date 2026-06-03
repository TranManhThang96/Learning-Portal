# Document — Day 03

## Tóm tắt kiến thức
`Session` là cuộc hội thoại làm việc được Claude Code lưu cục bộ liên tục để bạn có thể quay lại sau. Với project `taskflow-ai`, session giúp giữ mạch phân tích repo, quyết định kỹ thuật, plan, test output, và các constraint đã thống nhất.

`Context window` là vùng thông tin model đang dùng để suy luận tại một thời điểm. Nó không phải toàn bộ repo. Claude chỉ hiểu chắc những gì đã đọc hoặc những gì bạn cung cấp rõ ràng. Khi context chứa quá nhiều file, log, hướng sai, hoặc câu hỏi ngoài lề, session dễ bị nhiễu.

Các command quan trọng:

- `claude`: mở Claude Code trong thư mục project hiện tại.
- `/help`: xem command hiện có ngay trong interactive session.
- `claude --continue`: tiếp tục session gần nhất trong thư mục hiện tại.
- `claude --resume`: mở session picker để chọn session.
- `/resume`: resume hoặc chuyển session từ bên trong Claude Code.
- `/clear`: reset context giữa các task không liên quan.
- `/compact [instructions]`: thay history bằng summary, có thể kèm instruction để giữ đúng phần quan trọng.

Nguyên tắc chính: context là tài nguyên cần quản lý chủ động. Không để Claude Code kéo theo mọi thứ từ một ngày làm việc dài vào một task nhỏ.

Lưu ý về permission: bài Day 03 ưu tiên phân tích read-only bằng prompt và review thủ công. `claude --permission-mode acceptEdits` cho phép tạo/sửa file và auto-approve các filesystem command phổ biến trong working directory, nên chỉ dùng khi write scope đã rõ. Rule bền vững của project nên đặt trong `CLAUDE.md` hoặc `.claude/CLAUDE.md`, không trộn với summary tạm thời của session.

## Sơ đồ tư duy hoặc luồng xử lý
Luồng làm việc khuyến nghị cho Day 03:

```text
Vào taskflow-ai
  |
  v
git status --short
  |
  v
claude
  |
  v
/help nếu cần kiểm tra command
  |
  v
Prompt phân tích repo read-only
  |
  v
Tạo project mental model
  |
  v
Tạo summary context
  |
  v
/compact với instruction cụ thể
  |
  v
Hỏi lại để kiểm tra Claude còn hiểu project không
  |
  v
Thoát session
  |
  v
claude --continue hoặc claude --resume
  |
  v
Kiểm tra goal, file đã đọc, assumption, next step
```

Mental model cần giữ sau compact:

```text
Goal hiện tại
Repo stack
Folder/file quan trọng
File đã đọc thật
Quyết định đã thống nhất
Constraint an toàn
Test/lệnh đã chạy
Lỗi hoặc câu hỏi còn mở
Next step nhỏ nhất
```

## Bảng so sánh
| Khái niệm/lệnh | Mục đích | Khi dùng | Rủi ro nếu dùng sai |
| --- | --- | --- | --- |
| Session | Lưu mạch hội thoại và công việc | Làm một task có nhiều bước | Kéo theo quyết định cũ không còn đúng |
| Context window | Vùng thông tin model đang xử lý | Mọi lần Claude suy luận | Quá đầy hoặc nhiễu làm Claude quên constraint |
| `/help` | Xem command hiện có | Khi không chắc cú pháp | Bỏ qua bước này dễ dùng nhầm command đã thay đổi |
| `claude --continue` | Resume session gần nhất | Muốn quay lại nhanh | Có thể resume nhầm nếu vừa mở session khác |
| `claude --resume` | Chọn session từ danh sách | Có nhiều session song song | Chọn nhầm session gây nhiễu task |
| `/clear` | Reset context | Đổi sang task không liên quan | Mất mạch nếu chưa lưu summary |
| `/compact [instructions]` | Tóm tắt history | Session dài nhưng vẫn cùng task | Summary thiếu chi tiết quan trọng |
| `claude --permission-mode acceptEdits` | Cho phép edit và auto-approve common filesystem commands trong working directory | Khi task có write scope rõ | Dùng cho task read-only dễ tạo diff ngoài ý muốn |

| Tình huống | Nên làm | Không nên làm |
| --- | --- | --- |
| Bắt đầu feature mới | Session mới hoặc `/clear` | Dùng tiếp session đã debug lỗi khác |
| Context dài nhưng cùng goal | `/compact` có instruction | Paste lại toàn bộ log cũ |
| Resume sau nghỉ giữa chừng | Hỏi Claude nhắc lại goal và assumption | Cho Claude sửa code ngay |
| Claude trả lời mơ hồ | Yêu cầu nêu file đã đọc và chưa đọc | Tin vào kết luận không có path cụ thể |
| Log test dài | Đưa lỗi chính và command | Paste toàn bộ output không lọc |

## Lỗi thường gặp
1. Dùng `claude --continue` trong sai thư mục.
   - Hậu quả: Claude resume session của repo khác hoặc không tìm được session đúng.
   - Cách tránh: kiểm tra `pwd` hoặc tên thư mục trước khi chạy.

2. Không lưu dấu mốc session.
   - Hậu quả: khó phân biệt nhiều conversation giống nhau khi resume.
   - Cách tránh: tạo context summary ngắn có ngày học, branch, goal, file đã đọc và next step trước khi thoát.

3. Compact quá muộn.
   - Hậu quả: Claude đã bị nhiễu bởi log dài và quyết định cũ.
   - Cách tránh: compact sau mỗi mốc tự nhiên như map repo, chốt plan, fix xong lỗi.

4. Compact không có instruction.
   - Hậu quả: summary có thể bỏ mất constraint quan trọng.
   - Cách tránh: yêu cầu giữ goal, file, decision, test, lỗi còn mở, next step.

5. Nhầm `/clear` với rollback code.
   - Hậu quả: context sạch hơn nhưng file trên disk vẫn giữ thay đổi.
   - Cách tránh: dùng Git để xem hoặc hủy diff khi cần.

6. Tin rằng Claude đã hiểu toàn repo.
   - Hậu quả: Claude đưa plan dựa trên assumption.
   - Cách tránh: bắt Claude nói rõ file nào đã đọc thật.

7. Đưa secret hoặc production data vào summary.
   - Hậu quả: thông tin nhạy cảm nằm trong transcript/session.
   - Cách tránh: redact secret, dùng sample value, không paste credential.

8. Bật `acceptEdits` cho bài chỉ cần phân tích.
   - Hậu quả: Claude có thể tạo/sửa file hoặc chạy filesystem command phổ biến mà bạn chưa review từng bước.
   - Cách tránh: dùng session thường cho Day 03; chỉ dùng mode này khi đã có write scope và acceptance criteria rõ.

## Cách debug
Khi Claude trả lời lệch mục tiêu:

```text
Hãy dừng lại và tự audit context hiện tại:
1. Goal mới nhất là gì?
2. Constraint nào đang áp dụng?
3. File nào bạn đã đọc thật sự?
4. Bạn đang suy luận điểm nào mà chưa xác minh?
5. Có thông tin cũ nào có thể đang gây nhiễu không?
Không sửa file trong câu trả lời này.
```

Khi Claude quên constraint:

```text
Constraint quan trọng: chỉ làm trong backend, không sửa frontend, không đổi schema, không sửa README.
Hãy nhắc lại constraint này, sau đó cập nhật plan với phạm vi file dự kiến.
```

Khi session quá dài:

```text
/compact Giữ lại goal hiện tại, constraint an toàn, quyết định kỹ thuật, file đã sửa, file đã đọc, test đã chạy, lỗi còn mở, và next step. Bỏ log dài, trao đổi ngoài lề, và hướng đã bị loại bỏ.
```

Khi resume và chưa chắc Claude còn hiểu đúng:

```text
Chúng ta vừa resume. Không đọc file mới ngay.
Hãy tóm tắt mental model hiện tại của taskflow-ai và đánh dấu từng ý là "đã xác minh" hoặc "chưa xác minh".
```

Khi cần kiểm tra file trên disk:

```bash
git status --short
```

Chạy ở đâu: trong thư mục `taskflow-ai`.

Lệnh làm gì: xem file nào đang thay đổi.

Kết quả kỳ vọng: danh sách ngắn các file modified/untracked hoặc trống nếu repo sạch.

Rủi ro: không có rủi ro ghi file, nhưng nếu bạn không hiểu file nào đang thay đổi thì không nên cho Claude rollback.

```bash
git diff --stat
```

Chạy ở đâu: trong thư mục `taskflow-ai`.

Lệnh làm gì: xem tổng quan số dòng thay đổi theo file.

Kết quả kỳ vọng: chỉ thấy file thuộc task hiện tại.

Rủi ro: không hiển thị đủ chi tiết logic; cần `git diff` để review sâu.

```bash
git diff
```

Chạy ở đâu: trong thư mục `taskflow-ai`.

Lệnh làm gì: xem nội dung thay đổi cụ thể.

Kết quả kỳ vọng: diff khớp scope và acceptance criteria.

Rủi ro: output dài; nếu đưa nguyên vào Claude có thể làm nhiễu context. Chọn đoạn liên quan.

## Link tài liệu nên đọc
- Claude Code Sessions: https://code.claude.com/docs/en/sessions
- Claude Code Best practices: https://code.claude.com/docs/en/best-practices
- Claude Code Quickstart: https://code.claude.com/docs/en/quickstart

Đọc theo thứ tự:

1. Quickstart để nắm cách mở Claude Code trong project và dùng `/help`, `/resume`.
2. Sessions để hiểu resume, session picker và compact.
3. Best practices để quản lý context bằng `/clear`, `/compact`, summary thủ công, và kiểm tra lại command bằng `/help` khi cần.
