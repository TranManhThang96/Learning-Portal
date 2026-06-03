# Day 08 — Backend CRUD với plan-first workflow

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Dùng Claude Code theo workflow `plan-first` để xây dựng backend CRUD mà không để AI tự ý đổi architecture.
- Chuyển yêu cầu mơ hồ như "thêm task CRUD" thành API contract rõ ràng: endpoint, request, response, status code, validation, error shape và logging.
- Yêu cầu Claude Code đọc đúng module trong `taskflow-ai`, lập plan có bằng chứng, rồi mới implement.
- Viết hoặc yêu cầu Claude Code viết unit test và integration test có assertion thật, không chỉ test happy path.
- Review diff như senior backend reviewer: kiểm tra contract drift, behavior ngoài ý muốn, security, maintainability và rollback.
- Quản lý permission, command và context để giảm rủi ro khi Claude Code được quyền sửa nhiều file backend.

## 2. Bối cảnh thực tế

Backend CRUD nhìn đơn giản nhưng trong project thật lại dễ bị AI làm quá tay. Với một prompt ngắn kiểu "create task CRUD API", Claude Code có thể tự thêm framework mới, đổi folder structure, tạo generic repository, đổi error format, viết route khác convention, hoặc thêm migration/schema ngoài scope. Nếu project `taskflow-ai` đã có pattern route/service/repository, hành vi đó làm code khó maintain và gây tranh chấp với các worker khác.

Vấn đề thường gặp trong team:

- API contract chưa rõ nên mỗi endpoint trả lỗi một kiểu.
- Validation nằm rải rác: lúc ở route, lúc ở service, lúc dựa vào database constraint.
- Logging quá ít để debug, hoặc quá nhiều làm lộ PII/token.
- Test chỉ kiểm tra status code, không kiểm tra body, validation, quyền truy cập hoặc error mapping.
- Claude Code sửa nhiều file ngoài phạm vi vì developer không khóa architecture và file boundary.

Claude Code hữu ích khi bạn buộc nó đi theo vòng lặp có kiểm soát:

```text
observe -> propose contract -> plan -> implement small slice -> test -> review diff -> adjust
```

Không nên dùng Claude Code để tự động implement CRUD khi:

- Team chưa thống nhất API contract hoặc error format.
- Module liên quan tới auth, billing, permission, production data hoặc migration phá dữ liệu.
- Working tree đang có thay đổi của người khác mà bạn chưa hiểu.
- Bạn chưa có cách verify: test command, database test, hoặc ít nhất contract checklist.
- Bạn muốn quyết định kiến trúc lớn, ví dụ đổi Fastify sang NestJS, đổi ORM, đổi logging stack. Những việc này cần RFC/ADR riêng, không gộp vào CRUD.

## 3. Kiến thức nền

`Plan-first workflow` nghĩa là không bắt Claude Code sửa code trong prompt đầu tiên. Trước hết Claude phải đọc code liên quan, nêu bằng chứng, đề xuất contract và plan nhỏ. Developer duyệt plan, chỉnh scope, rồi mới cho implement. Đây là cách biến Claude Code từ "người viết code tự do" thành "pair engineer làm trong boundary".

Trong `taskflow-ai`, một API task CRUD tối thiểu thường có các phần sau. Tên file chỉ là ví dụ; hãy yêu cầu Claude đọc project thật trước khi dùng:

| Thành phần | Trách nhiệm | Điều cần khóa trong plan |
| --- | --- | --- |
| Route/controller | Nhận HTTP request, parse input, gọi service, map response | Không tự đổi framework hoặc route prefix hiện có |
| Validation schema | Kiểm tra input tại boundary | Không tin client; reject input sai trước khi vào business logic |
| Service/use case | Áp dụng business rule: trim title, status transition, ownership | Không nhét SQL hoặc HTTP detail vào service nếu project không làm vậy |
| Repository/data access | Đọc/ghi database hoặc in-memory store theo pattern hiện có | Không đổi ORM/query builder ngoài scope |
| Error handler | Map lỗi domain/validation/not found thành response thống nhất | Không leak stack trace hoặc database detail |
| Logger | Ghi event đủ debug: request id, task id, user id nếu có, latency | Không log token, password, raw secret, payload nhạy cảm |
| Test | Unit test business rule, integration test route contract | Không chỉ snapshot hoặc status code chung chung |

API contract là tài liệu nhỏ mô tả hành vi public của API trước khi code. Contract không cần dài, nhưng phải đủ để review:

| Endpoint | Ý nghĩa | Request chính | Response thành công | Lỗi cần có |
| --- | --- | --- | --- | --- |
| `POST /tasks` | Tạo task | `title`, optional `description`, optional `priority` | `201` + task mới | `400` validation |
| `GET /tasks` | Danh sách task | optional filter/pagination theo pattern hiện có | `200` + list | `400` filter sai |
| `GET /tasks/:id` | Chi tiết task | path `id` | `200` + task | `404` not found |
| `PATCH /tasks/:id` | Cập nhật một phần | fields được phép update | `200` + task mới | `400`, `404`, conflict nếu có |
| `DELETE /tasks/:id` | Xóa task | path `id` | `204` hoặc `200` theo convention hiện có | `404` |

Điểm quan trọng: contract phải bám convention hiện có. Nếu `taskflow-ai` đang dùng `200` cho delete với body `{ success: true }`, đừng để Claude tự đổi sang `204` chỉ vì phổ biến hơn. Nếu project đang dùng centralized error handler, không để Claude trả lỗi thủ công ở từng route.

Validation nên đặt ở HTTP boundary hoặc schema layer nếu project đã có. Business rule vẫn nên được test ở service. Ví dụ `title` sau khi trim không được rỗng là rule có thể kiểm tra ở schema và service tùy architecture, nhưng không nên để database là lớp đầu tiên phát hiện lỗi.

Error handling cần phân biệt:

- Validation error: input sai, client có thể sửa.
- Not found: task id không tồn tại hoặc không thuộc user hiện tại.
- Conflict: trạng thái không hợp lệ, ví dụ reopen task đã archived nếu domain cấm.
- Internal error: lỗi không mong muốn; response không leak stack trace, log nội bộ có correlation id.

Logging tốt cho CRUD không phải log mọi thứ. Log nên trả lời được: request nào, user nào nếu có, task id nào, action nào, kết quả gì, mất bao lâu. Không log raw authorization header, cookie, secret, hoặc payload dài có dữ liệu nhạy cảm.

## 4. Step-by-step thực hành

Mục tiêu thực hành: dùng Claude Code để tạo hoặc hoàn thiện API task CRUD trong backend `taskflow-ai` theo contract rõ ràng, có validation, error handling, logging và test. Nếu project của bạn chưa có backend hoặc module tasks, yêu cầu Claude Code đề xuất slice nhỏ nhất theo architecture hiện có, không tự dựng lại toàn bộ app.

### Bước 1: Kiểm tra trạng thái và phạm vi repo

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này hiển thị working tree ở dạng ngắn. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có thay đổi của worker khác hoặc thay đổi chưa review, bạn có thể nhầm diff của mình với diff của họ.

Nếu cần biết backend nằm ở đâu, chạy trong thư mục gốc `taskflow-ai`:

```bash
find . -maxdepth 3 -name package.json
```

Lệnh này tìm các package Node trong repo. Output kỳ vọng có thể là `./package.json` hoặc `./backend/package.json`. Rủi ro thấp vì đây là read-only, nhưng trên Windows PowerShell có thể cần lệnh tương đương như `Get-ChildItem -Recurse -Filter package.json -Depth 3`.

Nếu repo dùng Git branch, kiểm tra branch hiện tại:

```bash
git branch --show-current
```

Lệnh này in tên branch. Output kỳ vọng là branch feature, ví dụ `feature/day-08-task-crud`, không phải `main`. Rủi ro: làm trực tiếp trên branch chính khiến rollback và review khó hơn.

### Bước 2: Mở Claude Code ở plan mode để đọc trước

Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude Code ở mode phù hợp cho đọc, hiểu và lập plan trước khi sửa. Output kỳ vọng là session Claude Code sẵn sàng nhận prompt. Rủi ro thấp hơn implement mode, nhưng plan vẫn có thể sai nếu Claude đọc thiếu file hoặc suy diễn architecture.

Prompt khám phá:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát backend để tìm module hoặc convention liên quan tới tasks/todos, route, validation, error handling, logger và test.

Ràng buộc:
- Chưa sửa file.
- Chỉ đọc file cần thiết.
- Nêu rõ file đã đọc và bằng chứng từ code.
- Không đề xuất đổi framework, ORM, folder structure, logger hoặc error format.
- Nếu project chưa có module tasks, hãy chỉ ra nơi nhỏ nhất nên thêm module mới theo convention hiện có.
```

Kỳ vọng: Claude liệt kê file đã đọc, vẽ luồng request hiện tại, chỉ ra test framework và command dự kiến. Nếu Claude chưa đọc `package.json`, route registration hoặc test setup mà đã lập plan, yêu cầu đọc bổ sung.

### Bước 3: Chốt API contract trước khi implement

Gửi prompt trong cùng session:

```text
Từ các file đã đọc, hãy đề xuất API contract cho task CRUD.

Yêu cầu output:
- Bảng endpoint, method, path, request, response, status code.
- Validation rule cho title, description, status/priority nếu có.
- Error shape phải bám pattern hiện có; nếu chưa có pattern, đề xuất một format tối thiểu và nêu rõ trade-off.
- Logging event cần có và field không được log.
- Test cases unit và integration tối thiểu.
- Chưa sửa file.
```

Kỳ vọng: contract đủ cụ thể để reviewer bắt lỗi trước khi code. Nếu Claude đề xuất thêm pagination, auth, assignee, audit log hoặc status workflow phức tạp ngoài yêu cầu, yêu cầu cắt scope về CRUD task cơ bản.

### Bước 4: Lập plan file-by-file

Prompt lập plan:

```text
Lập plan implement API task CRUD theo contract đã duyệt.

Ràng buộc:
- Plan tối đa 7 bước.
- Mỗi bước ghi file dự kiến sửa hoặc tạo.
- Không đổi architecture hiện có.
- Không thêm dependency nếu chưa có lý do rõ và chưa được approve.
- Không tạo migration trong Day 08 nếu project chưa học Day 09; nếu cần data layer, dùng pattern test/dev hiện có hoặc ghi TODO rõ.
- Chờ tôi approve trước khi edit.
```

Plan tốt thường có dạng:

```text
1. Thêm/hoàn thiện validation schema cho task request.
2. Thêm route handlers CRUD theo route registration hiện có.
3. Thêm service method với business rule tối thiểu.
4. Dùng repository/data access hiện có; không đổi database contract.
5. Map lỗi validation/not found bằng error handler hiện có.
6. Thêm unit test cho service validation và not found.
7. Thêm integration test cho route contract.
```

Nếu plan chạm quá nhiều file, yêu cầu Claude chia thành slice:

```text
Plan này quá rộng. Hãy chia thành slice 1 chỉ gồm POST /tasks và GET /tasks/:id, có test. Không implement.
```

### Bước 5: Cho implement với permission và boundary hẹp

Sau khi duyệt plan, mở Claude Code ở mode kiểm soát. Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)"
```

Lệnh này giới hạn built-in tool family vào `Read`, `Write`, `Edit`, `Bash`, đồng thời auto-approve riêng `git status` và `git diff`. Output kỳ vọng là session sẵn sàng. Rủi ro: `--allowedTools` không deny Bash command khác; command ngoài pattern sẽ phải hỏi theo `default` mode. Nếu mở rộng thành `Bash(*)` hoặc auto-approve quá rộng, Claude có thể chạy install, migration hoặc command tốn thời gian ngoài plan.

Prompt implement:

```text
Implement theo plan đã duyệt cho API task CRUD.

Ràng buộc bắt buộc:
- Chỉ sửa/tạo các file đã liệt kê trong plan.
- Không đổi framework, architecture, folder convention, error format hoặc logger format.
- Không thêm dependency mới.
- Không chạy npm install, migration, docker command, git add, git commit, git reset, git clean hoặc lệnh xóa file.
- Nếu gặp thiếu thông tin, dừng và hỏi thay vì tự quyết.
- Sau khi edit, tóm tắt diff theo file và nêu test command tôi nên chạy.
```

Kỳ vọng: Claude tạo patch theo plan, không tự commit, không đổi scope. Nếu Claude muốn sửa `README`, config global, schema database hoặc file ngoài plan, từ chối và yêu cầu giải thích.

### Bước 6: Chạy test có kiểm soát

Trước khi chạy test, đọc `package.json` để biết script thật. Các command dưới đây là ví dụ phổ biến; chạy trong folder có `package.json` của backend, có thể là `taskflow-ai/backend` hoặc root nếu backend package nằm ở root.

```bash
npm run test -- --run
```

Lệnh này thường chạy test một lần thay vì watch mode nếu project dùng Vitest. Output kỳ vọng là các test pass và process exit code `0`. Rủi ro: nếu script test trỏ vào database local, hãy chắc chắn đang dùng database dev/test, không phải production.

```bash
npm run test:unit -- tasks
```

Lệnh này là ví dụ cho unit test tập trung vào module tasks nếu project có script tương ứng. Output kỳ vọng là test service/validation pass. Rủi ro: script có thể không tồn tại; không để Claude tự thêm script chỉ để command này chạy nếu project đã có convention khác.

```bash
npm run test:integration -- tasks
```

Lệnh này là ví dụ cho integration test route contract nếu project có script tương ứng. Output kỳ vọng là request `POST`, `GET`, `PATCH`, `DELETE` trả đúng status/body. Rủi ro: integration test có thể cần database test, Docker hoặc seed data; không chạy nếu môi trường chưa rõ.

Nếu test fail, không cho Claude sửa ngay. Đưa failure output vào prompt review:

```text
Test fail như sau. Hãy phân tích nguyên nhân trước, chưa sửa file.
Phân loại: bug trong implementation, test sai contract, thiếu setup, hay môi trường.
Đề xuất patch nhỏ nhất và file cần sửa.
```

### Bước 7: Review diff như reviewer

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này cho biết số file và số dòng thay đổi. Output kỳ vọng khớp file list trong plan. Rủi ro: `--stat` không cho thấy logic, chỉ dùng để phát hiện patch rộng bất thường.

```bash
git diff
```

Lệnh này hiển thị patch chi tiết. Output kỳ vọng: route contract đúng, validation rõ, error mapping bám convention, logging không lộ secret, test có assertion meaningful. Rủi ro: diff dài dễ bỏ sót behavior change; hãy xem theo file nếu cần.

Ví dụ xem một file:

```bash
git diff -- backend/src/tasks/task.routes.ts
```

Lệnh này giới hạn diff vào file route ví dụ. Output kỳ vọng chỉ có route CRUD theo plan. Rủi ro thấp vì read-only; thay path theo file thật trong repo.

Prompt review:

```text
Review diff hiện tại như senior backend reviewer.

Tập trung:
- API contract có bị đổi ngoài plan không.
- Validation có reject input xấu nhưng không duplicate quá mức không.
- Error response có thống nhất với project không.
- Logging có đủ debug nhưng không lộ secret/PII không.
- Test có kiểm tra body, edge case và error path không.
- Có file nào ngoài plan bị chạm không.

Không sửa file trong bước review này.
```

### Bước 8: Rollback an toàn nếu patch sai

Trước khi rollback, luôn xem file nào bị thay đổi:

```bash
git status --short
```

Lệnh này giúp xác định file đang modified/untracked. Output kỳ vọng chỉ gồm file của Day 08 hoặc task hiện tại. Rủi ro: nếu có file của người khác, không rollback toàn repo.

Rollback một file đã review:

```bash
git restore -- backend/src/tasks/task.routes.ts
```

Lệnh này đưa file tracked về trạng thái trong Git. Chạy ở root repo. Output thường rỗng nếu thành công. Rủi ro: mất toàn bộ thay đổi chưa commit trong file đó, kể cả thay đổi bạn tự viết.

Xóa file mới tạo sai chỉ khi chắc chắn file đó do bạn/Claude tạo trong task này:

```bash
git clean -f -- backend/src/tasks/task.routes.ts
```

Lệnh này xóa untracked file cụ thể. Chạy ở root repo. Output kỳ vọng là tên file bị remove. Rủi ro cao hơn `git restore` vì xóa file chưa tracked; không dùng dạng rộng như `git clean -fd` trong repo có nhiều worker.

Không chạy các lệnh này theo đề xuất tự động của Claude nếu chưa tự quyết định:

```bash
git reset --hard
git clean -fd
docker compose down -v
rm -rf backend/src
```

Các lệnh này có thể làm mất thay đổi của bạn hoặc worker khác, xóa volume database, hoặc xóa source. Với repo nhiều worker, rollback phải theo file, không rollback toàn working tree.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```text
Hãy đọc backend taskflow-ai để hiểu convention trước khi thêm task CRUD.

Yêu cầu:
- Chỉ đọc file, chưa sửa.
- Nêu rõ file đã đọc và bằng chứng.
- Tìm route registration, validation pattern, error handler, logger, test setup.
- Nếu chưa có module tasks, tìm module tương tự nhất để bắt chước.
- Không đề xuất đổi framework hoặc architecture.
```

### Prompt lập API contract

```text
Hãy viết API contract cho task CRUD theo convention hiện có.

Output cần có:
- Endpoint/method/path.
- Request body/query/path params.
- Response success và status code.
- Error cases: validation, not found, conflict nếu có.
- Validation rule cụ thể cho title/description/status.
- Logging event và field không được log.
- Test cases tối thiểu.

Chưa implement.
```

### Prompt lập plan file-by-file

```text
Tạo implementation plan cho contract đã duyệt.

Ràng buộc:
- Tối đa 7 bước.
- Mỗi bước ghi file sẽ sửa/tạo.
- Không thêm dependency.
- Không đổi architecture, folder structure, error format hoặc logger.
- Nếu cần thay đổi database schema, dừng lại và đề xuất chuyển sang Day 09.
- Chờ tôi approve trước khi sửa.
```

### Prompt implement

```text
Implement task CRUD theo plan đã approve.

Giới hạn:
- Chỉ chạm file trong plan.
- Không chạy install, migration, docker, git add/commit/reset/clean, hoặc lệnh xóa file.
- Bám API contract đã duyệt.
- Viết unit test cho business rule và integration test cho route contract theo pattern hiện có.
- Nếu không chắc convention, hỏi lại trước.
- Sau khi xong, tóm tắt diff và test command cần chạy.
```

### Prompt review diff

```text
Review diff hiện tại như senior backend reviewer, không sửa file.

Kiểm tra:
- Contract drift.
- Validation edge cases: title rỗng, title chỉ có khoảng trắng, id sai format, update body rỗng.
- Error handling có thống nhất không.
- Logging có leak dữ liệu nhạy cảm không.
- Test có meaningful assertion không.
- Có thay đổi architecture hoặc dependency ngoài scope không.

Kết luận theo format: Blocker, Should fix, Nice to have, Test gaps.
```

### Prompt viết test trước khi sửa tiếp

```text
Hãy đề xuất test bổ sung cho task CRUD trước khi sửa code tiếp.

Ràng buộc:
- Đọc pattern test hiện có.
- Chỉ đề xuất test cases và file cần sửa.
- Ưu tiên assertion về contract: status code, response body, error code, database side effect.
- Không tạo snapshot rộng.
- Chưa edit file.
```

## 6. Trade-offs

Plan-first chậm hơn implement-first vì phải tách các bước đọc, contract, plan và implement. Đổi lại, nó giảm rủi ro Claude sửa nhầm architecture, đặc biệt khi CRUD chạm nhiều lớp backend.

Contract-first buộc bạn quyết định status code và error shape trước. Nhược điểm là phải suy nghĩ nhiều hơn trước khi code. Lợi ích là test rõ hơn, frontend ít bị đổi bất ngờ, và reviewer có tiêu chuẩn khách quan để bắt lỗi.

Viết cả unit test và integration test tốn thời gian hơn chỉ viết route test. Unit test giúp khóa business rule như trim title, update body rỗng, status transition. Integration test giúp khóa HTTP contract và error mapping. Với feature CRUD public, cả hai loại test đều đáng có.

Không thêm dependency mới làm implementation có thể dài hơn một chút, nhưng giữ maintainability. Với Day 08, mục tiêu là dùng pattern hiện có; đổi validation library, logger hoặc ORM là quyết định architecture, không phải chi tiết CRUD.

Logging nhiều giúp debug production, nhưng tăng rủi ro lộ dữ liệu và tăng noise. Log event cấp cao, id và metadata đủ truy vết; không log raw request body nếu body có thể chứa secret hoặc dữ liệu cá nhân.

## 7. Best practices

- Luôn bắt đầu bằng `plan` mode cho CRUD mới vì task chạm route, validation, service, data access và test.
- Bắt Claude nêu "file đã đọc" và "bằng chứng từ code"; không accept plan dựa trên suy đoán.
- Chốt API contract trước khi implement, kể cả khi contract chỉ là bảng ngắn trong chat.
- Ghi rõ "không đổi architecture" trong prompt implement. Cấm tự thêm dependency, đổi framework, đổi ORM, đổi logger hoặc đổi error format.
- Dùng `CLAUDE.md` để giữ convention lâu dài: folder structure, scripts, test rules, error response, logging rule, command bị cấm.
- Với command quyền cao, dùng permission mode `default`, `--tools` để giới hạn tool family và `--allowedTools` chỉ cho command thật sự muốn auto-approve. Không dùng `bypassPermissions` trên repo thật.
- Không đưa `.env`, token, production credential, customer payload hoặc database dump vào prompt.
- Với CRUD có auth/tenant boundary, test bắt buộc phải có case "user không được đọc/sửa task của user khác".
- Sau mỗi patch, chạy `git diff --stat` trước, rồi review diff chi tiết. Nếu file ngoài plan bị chạm, dừng implement.
- Rollback theo file. Không dùng `git reset --hard` hoặc `git clean -fd` trong repo nhiều worker.
- Không để Claude tự commit. Commit message và PR description có thể nhờ Claude soạn sau khi human review.

## 8. Performance / cost / context

CRUD backend dễ làm phình context vì Claude có thể đọc route, schema, service, repository, tests, config, migration và docs. Tối ưu không phải là nhồi toàn repo vào prompt, mà là ép Claude đọc đúng file.

Cách giảm token và chi phí:

- Prompt khám phá chỉ yêu cầu module liên quan: route registration, validation, error handler, logger, test setup.
- Yêu cầu Claude tóm tắt contract và plan ngắn trước khi edit; không để nó tạo bài giải dài trong mỗi lượt.
- Chia feature thành slice nếu module lớn: `POST + GET detail` trước, sau đó `LIST + PATCH + DELETE`.
- Khi test fail, chỉ đưa failure output liên quan, không paste toàn bộ log nếu log quá dài.
- Dùng `/compact` hoặc summary thủ công khi session dài: giữ contract, file list, test command, quyết định đã duyệt.
- Dùng custom slash command cho review/test nếu team lặp lại workflow, ví dụ command read-only để review diff với `allowed-tools: Read, Bash(git status *), Bash(git diff *)`.

Performance runtime của API cũng cần được nhắc trong contract:

- `GET /tasks` nên có pagination hoặc limit theo convention nếu danh sách có thể lớn.
- Không log payload lớn trong loop hoặc mỗi row.
- Không gọi database nhiều lần trong route list nếu repository có thể query một lần.
- Integration test không nên phụ thuộc timing hoặc sleep dài; dùng setup/teardown rõ.

## 9. Checklist cuối bài

- [ ] Tôi đã kiểm tra `git status --short` trước khi cho Claude Code sửa.
- [ ] Tôi đã dùng `plan` mode để Claude đọc backend và nêu file đã đọc.
- [ ] Tôi có API contract cho task CRUD trước khi implement.
- [ ] Tôi đã khóa scope: không đổi architecture, không thêm dependency, không đổi error/logger format.
- [ ] Tôi đã yêu cầu validation cho title rỗng/whitespace, id sai format và update body rỗng nếu phù hợp.
- [ ] Tôi đã yêu cầu error handling thống nhất với project.
- [ ] Tôi đã yêu cầu logging đủ debug nhưng không log secret/PII.
- [ ] Tôi có unit test cho business rule và integration test cho route contract.
- [ ] Tôi đã review `git diff --stat` và `git diff`.
- [ ] Tôi biết rollback theo file và tránh lệnh phá working tree của người khác.

## 10. Bài tập

Bài cơ bản: mở `taskflow-ai` ở `claude --permission-mode plan`, yêu cầu Claude khảo sát backend và viết API contract cho task CRUD. Không cho sửa file. Kết quả cần có: file đã đọc, contract, validation rule, error shape, logging rule và test plan.

Bài nâng cao: sau khi duyệt contract, cho Claude implement slice nhỏ đầu tiên: `POST /tasks` và `GET /tasks/:id` kèm unit/integration test. Giới hạn file theo plan, không thêm dependency, không migration. Review diff và ghi lại ít nhất 3 điểm bạn reject hoặc yêu cầu sửa.

Bài áp dụng project cá nhân: chọn một CRUD nhỏ trong repo cá nhân hoặc repo sandbox. Viết prompt theo format Context, Goal, Contract, Constraints, Acceptance Criteria, Verification. So sánh output khi prompt có contract và khi prompt chỉ nói "create CRUD API". Ghi lại khác biệt về số file sửa, chất lượng test và contract drift.
