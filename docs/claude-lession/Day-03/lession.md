# Day 03 — Session, context window, resume/continue

## 1. Mục tiêu bài học
- Hiểu `session` trong Claude Code là gì và vì sao session không giống một terminal command thông thường.
- Phân biệt `context window` với toàn bộ codebase trên disk.
- Nhận biết khi context bị nhiễu: Claude trả lời lệch, quên constraint, nhầm file, hoặc lặp lại hướng cũ đã bị bác bỏ.
- Biết dùng `/help` để kiểm tra command trong session, và dùng đúng `claude --continue`, `claude --resume`, `/resume`, `/clear`, `/compact`.
- Biết chia task lớn thành các phần nhỏ để Claude Code làm việc ổn định hơn.
- Tạo được summary context cho project `taskflow-ai` và dùng summary đó để kiểm tra Claude còn hiểu project sau khi resume.

Thời lượng gợi ý: 2 tiếng.

- 20 phút: lý thuyết session và context window.
- 35 phút: cho Claude Code phân tích repo `taskflow-ai`.
- 35 phút: tạo summary context, compact, resume.
- 20 phút: kiểm tra hiểu biết của Claude bằng câu hỏi và diff nhỏ.
- 10 phút: ghi lại checklist và reflection.

## 2. Bối cảnh thực tế
Khi dùng Claude Code trên một feature dài, bạn thường bắt đầu bằng việc cho Claude đọc repo, giải thích architecture, lập plan, sửa code, chạy test, rồi review diff. Vấn đề là tất cả hoạt động đó tạo ra rất nhiều context: prompt, file đã đọc, command output, lỗi test, quyết định kỹ thuật, và cả những nhánh suy nghĩ đã bị loại bỏ.

Claude Code giúp bạn tiếp tục công việc qua nhiều lần mở terminal nhờ session được lưu lại. Bạn có thể resume conversation trước đó thay vì giải thích lại từ đầu. Nhưng nếu cứ nhồi mọi việc vào một session, Claude có thể bị nhiễu context: nhớ nhầm mục tiêu cũ, ưu tiên file không liên quan, hoặc giữ lại assumption đã sai.

Khi nên dùng session dài:
- Task có cùng mục tiêu, ví dụ thiết kế rồi implement API `tasks`.
- Claude cần giữ các quyết định đã thống nhất, ví dụ stack, naming convention, cấu trúc folder.
- Bạn đang debug một lỗi có nhiều bước thử và cần lịch sử điều tra.

Khi không nên dùng session dài:
- Chuyển sang task không liên quan, ví dụ từ backend CRUD sang viết nội dung marketing.
- Session đã chứa log dài, nhiều lỗi cũ, nhiều hướng bị bỏ.
- Bạn vừa đổi yêu cầu lớn, ví dụ bỏ Fastify để sang NestJS.
- Bạn chuẩn bị làm thao tác rủi ro như migration hoặc xóa file, cần context sạch và plan rõ.

## 3. Kiến thức nền
### Session là gì
`Session` là một cuộc hội thoại làm việc giữa bạn và Claude Code trong một project. Claude Code lưu transcript cục bộ liên tục khi bạn làm việc, nên bạn có thể quay lại conversation trước bằng `claude --continue`, `claude --resume`, hoặc `/resume`.

Điểm quan trọng: session lưu lịch sử hội thoại, nhưng không thay thế Git. Nếu Claude sửa code sai, nguồn sự thật vẫn là working tree và diff của Git.

### Context window là gì
`Context window` là vùng trí nhớ làm việc mà model có thể dùng tại một thời điểm. Nó bao gồm prompt của bạn, phản hồi của Claude, file đã đọc, output lệnh, plan, lỗi test, và các summary sau compact.

Context window không phải toàn bộ repo `taskflow-ai`. Nếu bạn hỏi về file Claude chưa đọc, Claude có thể suy luận đúng một phần, nhưng vẫn có rủi ro hallucination. Với repo thật, hãy yêu cầu Claude nói rõ file nào đã đọc và file nào chỉ đang suy đoán.

### Context bị nhiễu là gì
Context bị nhiễu khi thông tin trong session làm Claude mất trọng tâm hoặc ưu tiên sai. Một số dấu hiệu:

- Claude nhắc lại requirement đã bị thay đổi.
- Claude sửa file ngoài phạm vi bạn yêu cầu.
- Claude đề xuất chạy lại lệnh đã chứng minh là sai.
- Claude quên constraint quan trọng như "không sửa README.md" hoặc "không đổi database schema".
- Claude trả lời tự tin nhưng không dẫn được file/path cụ thể.
- Claude trộn backend và frontend decision trong cùng một plan.

Nguyên nhân thường gặp:

- Task quá rộng: "build full app" thay vì "tạo route GET /tasks".
- Kết quả test/log quá dài được đưa vào context.
- Bạn hỏi nhiều câu ngoài lề trong cùng session.
- Claude đọc quá nhiều file không cần thiết.
- Session chứa nhiều lần đổi hướng kiến trúc.

### Resume, continue, clear, compact
Các thao tác cần nhớ:

| Thao tác | Dùng khi nào | Ý nghĩa thực tế |
| --- | --- | --- |
| `/help` | Muốn kiểm tra command có sẵn trong Claude Code | Xem hướng dẫn ngay trong interactive session |
| `claude --continue` | Muốn quay lại session gần nhất trong thư mục hiện tại | Resume nhanh conversation gần nhất |
| `claude --resume` | Có nhiều session và muốn chọn | Mở session picker |
| `/resume` | Đang ở trong Claude Code và muốn chuyển session | Chọn hoặc mở lại conversation trước |
| `/clear` | Chuyển sang task không liên quan | Reset context làm việc để giảm nhiễu |
| `/compact [instructions]` | Session dài nhưng vẫn cùng task | Thay history bằng summary có định hướng |

`/compact` không phải "xóa hết". Nó tóm tắt lịch sử để giải phóng context. Nếu không đưa instruction, summary có thể bỏ sót chi tiết bạn quan tâm. Vì vậy với task code, hãy nói rõ cần giữ lại: mục tiêu, file đã sửa, lệnh đã chạy, lỗi còn mở, quyết định kỹ thuật, và constraint.

### Chia task nhỏ
Một task tốt cho Claude Code nên có:

- Mục tiêu hẹp: một endpoint, một component, một test suite.
- Phạm vi file dự kiến.
- Acceptance criteria rõ.
- Lệnh verify cụ thể.
- Quy tắc rollback hoặc dừng khi gặp rủi ro.

Ví dụ không tốt:

```text
Hãy hoàn thiện toàn bộ taskflow-ai.
```

Ví dụ tốt:

```text
Trong backend của taskflow-ai, hãy chỉ phân tích cấu trúc hiện tại và đề xuất plan để thêm GET /tasks.
Không sửa file. Hãy liệt kê file cần đọc, assumption, rủi ro, và lệnh test dự kiến.
```

## 4. Step-by-step thực hành
### Bước 1: Mở project và kiểm tra trạng thái Git
Chạy trong terminal tại thư mục cha chứa project `taskflow-ai`.

```bash
cd taskflow-ai
```

Lệnh làm gì: chuyển terminal vào project xuyên suốt khóa học.

Kết quả kỳ vọng: terminal đang ở thư mục `taskflow-ai`. Nếu thư mục không tồn tại, bạn cần hoàn thành Day 02 hoặc tạo project trước khi học tiếp.

Rủi ro: nếu vào nhầm repo, Claude Code sẽ đọc và sửa nhầm codebase.

```bash
git status --short
```

Lệnh làm gì: xem working tree có file đang sửa không.

Kết quả kỳ vọng: có thể trống nếu repo sạch, hoặc hiện danh sách file đã thay đổi.

Rủi ro: nếu có thay đổi của người khác hoặc thay đổi bạn chưa hiểu, không yêu cầu Claude rollback. Hãy ghi lại trạng thái trước khi bắt đầu.

### Bước 2: Mở session trong đúng repo
Chạy trong thư mục `taskflow-ai`.

```bash
claude
```

Lệnh làm gì: mở Claude Code interactive session trong đúng thư mục project.

Kết quả kỳ vọng: Claude Code mở interactive session trong terminal.

Rủi ro: nếu chạy ở sai thư mục, session sẽ gắn với context repo sai. Kiểm tra lại `pwd` hoặc đường dẫn terminal trước khi chạy.

Nếu CLI báo chưa đăng nhập hoặc thiếu quyền, dừng lại và xử lý setup từ Day 02 trước.

Trong Claude Code, nếu không chắc cú pháp command, nhập:

```text
/help
```

Lệnh làm gì: xem danh sách command hiện có ngay trong interactive session.

Kết quả kỳ vọng: Claude Code hiển thị các command có thể dùng như resume, clear, compact tùy phiên bản CLI.

Rủi ro: không có rủi ro ghi file. Đây là cách kiểm tra lại cú pháp khi tài liệu hoặc CLI thay đổi.

Không chạy `claude --permission-mode acceptEdits` cho bài phân tích read-only này. Mode đó cho phép Claude tạo/sửa file và auto-approve các filesystem command phổ biến trong working directory; phù hợp hơn khi write scope đã rõ và sẽ học kỹ ở Day 04.

### Bước 3: Cho Claude phân tích repo nhưng giới hạn phạm vi
Trong Claude Code, nhập prompt:

```text
Bạn đang ở project taskflow-ai. Mục tiêu hôm nay là học session và context management, chưa implement feature mới.

Hãy phân tích repo ở mức tổng quan:
1. Xác định stack backend/frontend/test/devops hiện có.
2. Liệt kê 5-8 file hoặc folder quan trọng nhất và vì sao.
3. Chỉ rõ phần nào bạn đã đọc từ file thật, phần nào là suy luận.
4. Không sửa file.
5. Không chạy lệnh destructive.

Sau khi phân tích, hãy tạo một "project mental model" ngắn dưới 20 dòng.
```

Kết quả kỳ vọng:
- Claude đọc một số file như `package.json`, folder backend/frontend, config test nếu có.
- Claude trả lời có phân biệt "đã đọc" và "suy luận".
- Không có diff code.

Rủi ro:
- Prompt quá mở có thể khiến Claude đọc quá nhiều file.
- Nếu Claude muốn sửa code, nhắc lại "analysis only".

### Bước 4: Yêu cầu tạo summary context thủ công
Trong cùng session, nhập:

```text
Hãy tạo summary context cho session này để dùng sau khi resume.

Format bắt buộc:
- Goal hiện tại
- Repo mental model
- File/folder đã đọc
- Quyết định đã thống nhất
- Constraint an toàn
- Câu hỏi còn mở
- Lệnh verify đã/chưa chạy

Không thêm nội dung không chắc chắn. Nếu thiếu thông tin, ghi "chưa xác minh".
```

Kết quả kỳ vọng: một summary đủ ngắn để copy vào prompt sau này hoặc dùng làm instruction cho `/compact`.

Rủi ro: nếu summary chứa assumption sai, lần resume sau sẽ tiếp tục sai. Review summary như review code.

### Bước 5: Compact có định hướng
Trong Claude Code, chạy:

```text
/compact Giữ lại goal Day 03, mental model của taskflow-ai, file/folder đã đọc, constraint an toàn, câu hỏi còn mở, và lệnh verify. Bỏ các trao đổi ngoài lề.
```

Lệnh làm gì: thay history dài bằng summary tập trung vào phần cần giữ.

Chạy ở đâu: trong interactive prompt của Claude Code, không chạy ở shell bên ngoài.

Kết quả kỳ vọng: Claude Code compact session và tiếp tục conversation với context gọn hơn.

Rủi ro:
- Nếu instruction quá mơ hồ, compact có thể bỏ mất decision quan trọng.
- Nếu session đang chứa lỗi chưa debug xong, hãy yêu cầu giữ lại lỗi, command, và output ngắn.

### Bước 6: Kiểm tra Claude còn hiểu project không
Sau compact, nhập:

```text
Không đọc thêm file ngay. Dựa trên context hiện tại, hãy trả lời:
1. Project taskflow-ai đang dùng stack gì?
2. Những file/folder nào bạn đã thật sự đọc?
3. Những điểm nào bạn chưa xác minh?
4. Nếu task tiếp theo là thêm API list tasks, bạn cần đọc thêm file nào trước?
```

Kết quả kỳ vọng:
- Claude không bịa rằng đã đọc file chưa đọc.
- Claude nêu được giới hạn hiểu biết.
- Claude đề xuất bước đọc file tiếp theo hợp lý.

Rủi ro: nếu Claude trả lời quá tự tin nhưng thiếu file/path, context summary đang yếu. Hãy yêu cầu Claude tự kiểm tra bằng cách đọc file cụ thể.

### Bước 7: Thoát và resume session
Thoát khỏi Claude Code theo cách bạn thường dùng trong terminal. Sau đó chạy trong thư mục `taskflow-ai`:

```bash
claude --continue
```

Lệnh làm gì: resume session gần nhất trong thư mục hiện tại.

Kết quả kỳ vọng: quay lại conversation Day 03 gần nhất.

Rủi ro: nếu bạn vừa mở session khác trong cùng repo, `--continue` có thể không phải session bạn muốn.

Nếu muốn chọn đúng session:

```bash
claude --resume
```

Lệnh làm gì: mở danh sách session để chọn.

Kết quả kỳ vọng: thấy session hoặc nội dung gần nhất liên quan đến Day 03.

Rủi ro: chọn nhầm session sẽ đưa context cũ vào task mới. Đọc vài dòng summary trước khi tiếp tục.

### Bước 8: Dùng `/clear` khi đổi task
Trong Claude Code, nếu bạn muốn chuyển sang task khác không liên quan, nhập:

```text
/clear
```

Lệnh làm gì: reset context làm việc để bắt đầu task mới sạch hơn.

Chạy ở đâu: trong Claude Code interactive prompt.

Kết quả kỳ vọng: conversation mới không còn bị kéo bởi history cũ.

Rủi ro: nếu dùng `/clear` khi chưa lưu summary, bạn mất lợi thế của context vừa xây. Trước khi clear, hãy yêu cầu Claude xuất summary ngắn nếu còn cần dùng lại.

### Bước 9: Rollback khi Claude Code làm sai
Luôn kiểm tra diff trước khi giữ thay đổi:

```bash
git diff --stat
```

Lệnh làm gì: xem những file nào đã thay đổi và mức độ thay đổi.

Kết quả kỳ vọng: chỉ có file thuộc task hiện tại.

Rủi ro: nếu thấy file ngoài phạm vi, dừng lại review từng diff. Không rollback file của người khác trong repo dùng chung.

```bash
git diff
```

Lệnh làm gì: xem nội dung thay đổi chi tiết.

Kết quả kỳ vọng: diff khớp acceptance criteria.

Rủi ro: output dài có thể làm nhiễu context nếu paste toàn bộ vào Claude. Chỉ đưa phần liên quan hoặc yêu cầu Claude đọc file/diff cần thiết.

Nếu cần hủy thay đổi do chính bạn vừa tạo trong file cụ thể:

```bash
git restore path/to/file
```

Lệnh làm gì: đưa file về trạng thái Git hiện tại.

Rủi ro: mất thay đổi chưa commit trong file đó. Không chạy với file có thay đổi của người khác hoặc thay đổi bạn chưa kiểm tra.

## 5. Prompt mẫu nên dùng
### Prompt khám phá codebase
```text
Hãy phân tích repo taskflow-ai ở mức architecture. Trước khi kết luận, hãy liệt kê file/folder bạn cần đọc và lý do.
Chỉ đọc các file cần thiết cho mental model ban đầu. Không sửa file.
Khi trả lời, phân tách rõ "đã xác minh từ file" và "suy luận".
```

### Prompt lập plan
```text
Mục tiêu tiếp theo là thêm API list tasks, nhưng hiện tại chỉ lập plan.
Hãy dùng context hiện có, sau đó đề xuất:
1. File cần đọc thêm
2. Các bước implement nhỏ
3. Test cần có
4. Rủi ro context hoặc assumption
5. Điểm cần tôi xác nhận trước khi sửa code
Không chỉnh sửa file.
```

### Prompt implement có giới hạn
```text
Hãy implement bước nhỏ đầu tiên trong plan: chỉ thêm route GET /tasks ở backend.
Không sửa frontend, không đổi database schema, không thay đổi README.
Trước khi edit, nhắc lại file bạn sẽ sửa và acceptance criteria.
Sau khi edit, chạy đúng lệnh test liên quan và báo kết quả.
```

### Prompt review context sau resume
```text
Chúng ta vừa resume session. Trước khi làm tiếp, hãy kiểm tra hiểu biết hiện tại:
- Goal của session là gì?
- Những quyết định nào đã thống nhất?
- File nào đã đọc thật sự?
- Điều gì chưa xác minh?
Không đọc thêm file cho tới khi trả lời xong.
```

### Prompt viết test
```text
Dựa trên thay đổi hiện tại, hãy đề xuất test nhỏ nhất có ý nghĩa.
Chỉ viết test cho behavior đã implement, không mở rộng scope.
Nêu rõ lệnh chạy test, output kỳ vọng, và failure nào test này bắt được.
```

## 6. Trade-offs
Session dài giúp Claude giữ được mạch làm việc, nhưng cũng làm tăng rủi ro nhiễu context. Với `taskflow-ai`, một session dài phù hợp khi bạn đang theo một feature xuyên suốt như `tasks CRUD`. Nhưng nếu chuyển từ backend route sang UI design hoặc DevOps, nên dùng `/clear` hoặc session mới.

`claude --continue` rất nhanh, nhưng phụ thuộc vào session gần nhất trong thư mục hiện tại. Nếu đang làm nhiều nhánh song song, dùng `claude --resume` và kiểm tra nội dung summary/session trước khi tiếp tục sẽ an toàn hơn.

`/compact` tiết kiệm context và giúp session gọn hơn, nhưng summary là một dạng mất mát thông tin. Nếu summary bỏ sót lỗi test hoặc constraint bảo mật, Claude có thể đi sai. Với task quan trọng, tự review summary trước khi tiếp tục.

Chia task nhỏ tạo thêm overhead giao tiếp, nhưng giảm lỗi lớn. Senior workflow thường không tối ưu số prompt ít nhất; nó tối ưu khả năng kiểm soát diff, test, và rollback.

## 7. Best practices
- Ghi dấu mốc session bằng summary rõ ràng: ngày học, branch, goal, file đã đọc, constraint và next step.
- Dùng `/clear` giữa các task không liên quan.
- Dùng `/compact <instructions>` trước khi session quá dài, nhất là sau khi đã có plan hoặc sau một vòng debug dài.
- Dùng `/help` trong session khi cần xác minh command thay vì dựa vào trí nhớ hoặc tài liệu cũ.
- Yêu cầu Claude nói rõ file đã đọc thật và phần đang suy luận.
- Không paste log dài nguyên khối; đưa đoạn lỗi chính, lệnh đã chạy, và môi trường.
- Giữ secret, token, production credential ngoài prompt và ngoài file summary.
- Khi repo có nhiều người cùng sửa, luôn nói rõ ownership file trước khi Claude edit.
- Trước khi implement, yêu cầu Claude nhắc lại scope và file dự kiến sửa.
- Sau khi resume, luôn kiểm tra mental model trước khi cho Claude tiếp tục sửa code.
- Nếu team đặt `.claude/settings.json` với `permissions.defaultMode` là `auto`, ghi rõ trong workflow và tránh dùng cho bài read-only nếu chưa có write scope.

## 8. Performance / cost / context
Context càng lớn thì Claude càng phải xử lý nhiều thông tin hơn. Hệ quả thường thấy là phản hồi chậm hơn, chi phí/tài nguyên cao hơn tùy gói sử dụng, và chất lượng suy luận có thể giảm nếu context chứa nhiều thông tin nhiễu.

Cách tối ưu:

- Bắt đầu task bằng scope hẹp và acceptance criteria rõ.
- Không yêu cầu Claude đọc toàn repo nếu chỉ cần sửa một module.
- Dùng summary context thay vì giữ toàn bộ log.
- Compact sau các mốc tự nhiên: sau khi map repo, sau khi thống nhất plan, sau khi fix xong một lỗi.
- Clear khi đổi chủ đề.
- Đưa command output ngắn: lỗi chính, stack trace liên quan, test name fail.
- Với rule bền vững của project, đưa vào tài liệu project như `CLAUDE.md` hoặc `.claude/CLAUDE.md` ở Day 05, không phụ thuộc vào trí nhớ session.

Mẫu compact instruction tốt:

```text
/compact Giữ lại goal, quyết định kiến trúc, file đã sửa, file đã đọc, test đã chạy, lỗi còn mở, constraint bảo mật, và next step. Bỏ log dài và trao đổi ngoài lề.
```

## 9. Checklist cuối bài
- [ ] Tôi giải thích được session và context window khác nhau thế nào.
- [ ] Tôi biết khi nào dùng `claude --continue` và khi nào dùng `claude --resume`.
- [ ] Tôi đã mở session trong đúng thư mục `taskflow-ai`.
- [ ] Tôi đã yêu cầu Claude phân biệt thông tin đã đọc từ file và thông tin suy luận.
- [ ] Tôi đã tạo summary context cho `taskflow-ai`.
- [ ] Tôi đã thử `/compact` với instruction cụ thể.
- [ ] Tôi đã resume session và kiểm tra Claude còn hiểu project không.
- [ ] Tôi biết dùng `/clear` khi đổi task không liên quan.
- [ ] Tôi biết không paste secret hoặc log quá dài vào context.
- [ ] Tôi đã kiểm tra `git diff` trước khi giữ thay đổi.

## 10. Bài tập
### Bài tập cơ bản
Mở `taskflow-ai`, tạo một session mới, yêu cầu Claude phân tích repo ở mức tổng quan và xuất summary context dưới 20 dòng. Không cho Claude sửa file.

### Bài tập nâng cao
Trong session vừa tạo, dùng `/compact` với instruction riêng của bạn. Sau đó hỏi Claude 5 câu kiểm tra mental model:

- Stack backend/frontend là gì?
- File/folder nào đã đọc?
- Điều gì chưa xác minh?
- Nếu thêm GET `/tasks`, cần đọc file nào tiếp?
- Constraint an toàn của session là gì?

Ghi lại câu trả lời nào đúng, câu nào cần kiểm chứng lại.

### Bài tập áp dụng vào project cá nhân
Chọn một repo cá nhân hoặc repo công ty không chứa secret. Tạo session mới, yêu cầu Claude map architecture trong phạm vi read-only, tạo summary context, compact, resume, rồi kiểm tra Claude còn hiểu đúng repo không.

Không dùng repo có production credential, customer data, hoặc thông tin nội bộ nhạy cảm nếu bạn chưa được phép.
