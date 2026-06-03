# Exercise — Day 08

## Bài 1 — Cơ bản

Mục tiêu: dùng Claude Code ở `plan` mode để khảo sát backend và viết API contract cho task CRUD, chưa sửa file.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.
2. Kiểm tra working tree:

```bash
git status --short
```

Lệnh này chạy ở root repo để xem file đang thay đổi. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có file lạ, bạn có thể chồng diff lên thay đổi của người khác; dừng lại và đọc trước.

3. Mở Claude Code ở plan mode:

```bash
claude --permission-mode plan
```

Lệnh này chạy ở root repo để mở Claude Code trong workflow đọc/lập plan. Output kỳ vọng là session sẵn sàng. Rủi ro thấp hơn implement mode, nhưng Claude vẫn có thể suy diễn nếu đọc thiếu file.

4. Gửi prompt:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát backend để chuẩn bị API task CRUD.

Ràng buộc:
- Chỉ đọc file, chưa sửa.
- Nêu rõ file đã đọc và bằng chứng.
- Tìm route registration, validation pattern, error handler, logger và test setup.
- Nếu project chưa có module tasks, tìm module tương tự nhất để bắt chước.
- Không đề xuất đổi framework, ORM, folder structure, logger hoặc error format.
```

5. Yêu cầu Claude viết contract:

```text
Hãy viết API contract cho task CRUD dựa trên convention vừa đọc.

Contract phải có:
- Endpoint/method/path.
- Request body/query/path params.
- Response success và status code.
- Error cases: validation, not found, conflict nếu phù hợp.
- Validation rule cho title, description, status/priority nếu có.
- Logging event và field không được log.
- Unit test và integration test tối thiểu.

Chưa implement.
```

Kết quả cần nộp: bảng API contract, file list Claude đã đọc, test cases dự kiến, và 3 rủi ro nếu implement ngay không có plan.

## Bài 2 — Thực tế

Mục tiêu: implement slice đầu tiên của task CRUD với boundary rõ, có validation/error/logging/test.

Phạm vi đề xuất: `POST /tasks` và `GET /tasks/:id`. Nếu project đã có hai endpoint này, chọn `PATCH /tasks/:id` và `DELETE /tasks/:id`.

Yêu cầu:

1. Từ contract ở Bài 1, yêu cầu Claude lập plan file-by-file:

```text
Lập plan implement slice đầu tiên của task CRUD: POST /tasks và GET /tasks/:id.

Ràng buộc:
- Tối đa 6 bước.
- Mỗi bước ghi file sẽ sửa/tạo.
- Không thêm dependency.
- Không đổi architecture, folder structure, error format hoặc logger.
- Không tạo migration trong bài này.
- Chờ tôi approve trước khi edit.
```

2. Sau khi approve plan, mở session implement:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)"
```

Lệnh này chạy ở root `taskflow-ai` để giới hạn tool family vào đọc/sửa file và Bash, đồng thời auto-approve riêng Git read-only. Output kỳ vọng là session sẵn sàng. Rủi ro: nếu allowlist mở rộng quá mức, Claude có thể chạy command ngoài plan mà không hỏi.

3. Gửi prompt implement:

```text
Implement theo plan đã duyệt.

Ràng buộc bắt buộc:
- Chỉ chạm file trong plan.
- Bám API contract đã duyệt.
- Không thêm dependency.
- Không chạy npm install, migration, docker command, git add, git commit, git reset, git clean hoặc lệnh xóa file.
- Validation: title sau khi trim không được rỗng.
- Error handling phải theo pattern hiện có.
- Logging không được log token, cookie, password, secret hoặc raw request body nhạy cảm.
- Viết unit test cho business rule và integration test cho route contract nếu project đã có pattern test.
- Nếu thiếu thông tin, dừng và hỏi.
```

4. Review phạm vi patch:

```bash
git diff --stat
```

Lệnh này chạy ở root repo để xem số file/dòng thay đổi. Output kỳ vọng khớp file trong plan. Rủi ro: nếu xuất hiện file ngoài plan, dừng lại và yêu cầu Claude giải thích.

5. Review chi tiết:

```bash
git diff
```

Lệnh này chạy ở root repo để xem patch chi tiết. Output kỳ vọng: endpoint đúng contract, validation rõ, error response thống nhất, log không lộ dữ liệu nhạy cảm, test có assertion cụ thể. Rủi ro: diff dài dễ bỏ sót; xem từng file nếu cần.

6. Chạy test theo script thật trong backend. Ví dụ nếu backend package dùng Vitest:

```bash
npm run test -- --run
```

Lệnh này chạy ở folder có `package.json` backend. Output kỳ vọng là test pass và exit code `0`. Rủi ro: test có thể phụ thuộc database test; kiểm tra `.env.test` hoặc setup tương đương, không dùng production credential.

Kết quả cần nộp: diff summary, test command đã chạy, output chính, và danh sách issue còn lại nếu có.

## Bài 3 — Nâng cao

Mục tiêu: hoàn thiện CRUD còn lại, thêm integration test quan trọng và review contract drift.

Yêu cầu:

1. Yêu cầu Claude chỉ review trạng thái hiện tại:

```text
Review task CRUD hiện tại so với API contract Day 08.
Chưa sửa file.
Liệt kê endpoint đã đủ, endpoint thiếu, validation thiếu, error handling thiếu, logging thiếu và test gap.
Phân loại theo Blocker, Should fix, Nice to have.
```

2. Chọn phần thiếu có giá trị nhất, ví dụ `PATCH /tasks/:id` và `DELETE /tasks/:id`. Yêu cầu plan:

```text
Lập plan bổ sung PATCH /tasks/:id và DELETE /tasks/:id.

Ràng buộc:
- Không đổi contract endpoint đã có.
- Không đổi schema database.
- Không thêm dependency.
- Không refactor rộng.
- Thêm integration test cho success và not found.
- Thêm validation cho update body rỗng và title whitespace nếu update title.
- Chờ tôi approve trước khi sửa.
```

3. Cho implement sau khi approve, vẫn giữ `--tools` và `--allowedTools` hẹp như Bài 2.

4. Chạy test tập trung nếu project hỗ trợ filter:

```bash
npm run test -- --run tasks
```

Lệnh này chạy ở folder backend có `package.json` để chạy test liên quan tới tasks nếu script hỗ trợ filter. Output kỳ vọng là test task CRUD pass. Rủi ro: cú pháp filter phụ thuộc test runner/script; nếu không hỗ trợ, dùng script test chuẩn của project.

5. Yêu cầu Claude review diff read-only:

```text
Review diff hiện tại, không sửa file.

Tập trung:
- Có contract drift không.
- Có endpoint nào trả status/body khác contract không.
- Có logging nào leak dữ liệu không.
- Có test nào chỉ kiểm tra happy path không.
- Có thay đổi architecture/dependency ngoài scope không.
```

6. Nếu patch sai, rollback theo file đã review:

```bash
git restore -- path/to/tracked-file
```

Lệnh này chạy ở root repo để rollback một tracked file. Output thường rỗng nếu thành công. Rủi ro: mất thay đổi chưa commit trong file đó; không dùng nếu file có thay đổi của người khác.

Nếu có file mới tạo sai và chắc chắn là của task này:

```bash
git clean -f -- path/to/new-file
```

Lệnh này chạy ở root repo để xóa một untracked file cụ thể. Output kỳ vọng là file bị remove. Rủi ro: xóa vĩnh viễn file chưa tracked; không dùng dạng rộng.

Kết quả cần nộp: endpoint còn thiếu đã hoàn thiện, test bổ sung, review diff read-only và quyết định accept/reject.

## Bài 4 — Review & Reflection

Mục tiêu: biến bài CRUD thành rule làm việc cho team.

Trả lời các câu hỏi:

1. API contract cuối cùng của task CRUD gồm endpoint nào, status code nào, error shape nào?
2. Claude Code có đề xuất đổi architecture, thêm dependency hoặc sửa file ngoài plan không? Bạn xử lý thế nào?
3. Test nào có giá trị nhất trong bài này: unit hay integration? Vì sao?
4. Logging hiện tại có đủ debug chưa? Có field nào bạn cấm log không?
5. Nếu frontend Day 10 dùng API này, contract nào cần ổn định nhất?
6. Bạn sẽ thêm rule gì vào `CLAUDE.md` để các task backend sau không bị patch rộng?

Gợi ý prompt reflection:

```text
Dựa trên Day 08, hãy giúp tôi viết 10 rule backend workflow cho CLAUDE.md của taskflow-ai.

Yêu cầu:
- Rule phải cụ thể cho CRUD/API.
- Có rule về plan-first, API contract, validation, error handling, logging, test và rollback.
- Có danh sách command không được tự chạy.
- Không viết chung chung.
```

Kết quả cần nộp: reflection ngắn 10-15 dòng và rule đề xuất cho `CLAUDE.md`.

## Tiêu chí hoàn thành

- Đã dùng `claude --permission-mode plan` để khảo sát trước khi sửa.
- Có API contract rõ cho task CRUD.
- Plan implement có file list, không đổi architecture, không thêm dependency ngoài duyệt.
- Có validation cho title rỗng/whitespace và các edge case phù hợp với contract.
- Error handling bám pattern hiện có của project.
- Logging đủ truy vết nhưng không log secret/PII/raw payload nhạy cảm.
- Có unit test cho business rule và integration test cho route contract, hoặc có lý do rõ nếu project chưa có test setup.
- Đã chạy test command phù hợp và ghi lại output chính.
- Đã review `git diff --stat` và `git diff`.
- Biết rollback theo file, không dùng command phá toàn working tree.

## Gợi ý nếu bí

Nếu Claude không tìm được backend:

```text
Hãy tìm các file package.json, route entrypoint, server bootstrap hoặc module tương tự todo/task.
Chỉ đọc file.
Nếu repo chưa có backend, hãy đề xuất cấu trúc tối thiểu theo README hiện có, chưa tạo file.
```

Nếu Claude đề xuất đổi architecture:

```text
Không đổi architecture trong Day 08.
Hãy viết lại plan bằng cách bắt chước module gần nhất trong project.
Chỉ nêu file cần sửa/tạo và lý do.
Không implement.
```

Nếu contract chưa rõ:

```text
Trước khi implement, hãy đưa ra 3 phương án status code/error shape và chọn phương án bám convention hiện có nhất.
Nêu trade-off ngắn.
Chưa sửa file.
```

Nếu test fail:

```text
Test fail như sau. Hãy phân tích nguyên nhân, chưa sửa file.
Phân loại lỗi: implementation bug, test sai contract, thiếu setup, hay môi trường.
Đề xuất patch nhỏ nhất.
```

Nếu diff quá rộng:

```text
Diff đang rộng hơn plan. Hãy dừng implement.
Liệt kê file ngoài plan, lý do bị chạm, và cách rollback hoặc thu hẹp.
Không sửa file.
```

## Đáp án tham khảo hoặc expected result

Kết quả tốt cho Bài 1:

- Claude đọc đúng file backend liên quan, không sửa file.
- Contract có đủ endpoint CRUD, status code, request/response, validation, error và logging.
- Contract ghi rõ không đổi architecture, không thêm dependency, không migration trong Day 08.

Kết quả tốt cho Bài 2:

- `POST /tasks` reject title rỗng hoặc chỉ có khoảng trắng.
- `GET /tasks/:id` trả task đúng contract hoặc not found theo error format hiện có.
- Unit test kiểm tra business rule như trim title hoặc reject title rỗng.
- Integration test kiểm tra status code và response body, không chỉ kiểm tra request không crash.
- `git diff --stat` chỉ gồm file trong plan.

Ví dụ diff summary chấp nhận được:

```text
4 files changed, 120 insertions(+), 8 deletions(-)
```

Con số này chỉ là ví dụ. Quan trọng là file list khớp plan và không có config/dependency/architecture drift.

Kết quả tốt cho Bài 3:

- `PATCH /tasks/:id` xử lý update một phần, reject body rỗng hoặc title whitespace nếu update title.
- `DELETE /tasks/:id` bám convention status code của project.
- Integration test có ít nhất success và not found.
- Review diff phát hiện được mọi thay đổi ngoài contract.

Kết quả tốt cho Bài 4:

Rule mẫu có thể đưa vào `CLAUDE.md`:

```text
- Với backend API, luôn bắt đầu bằng contract trước khi implement.
- Không đổi framework, ORM, logger, error format hoặc folder structure trong task CRUD.
- Mọi endpoint mới phải có validation rule, error case và test case tương ứng.
- Không log authorization header, cookie, password, token, secret hoặc raw request body nhạy cảm.
- Không chạy npm install, migration, docker volume command, git reset, git clean dạng rộng hoặc commit tự động.
- Sau mỗi patch, báo file changed, test command và known risks; human review diff trước khi commit.
```
