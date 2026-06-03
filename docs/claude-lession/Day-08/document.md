# Document — Day 08

## Tóm tắt kiến thức

Day 08 tập trung vào backend CRUD nhưng trọng tâm thật sự là workflow kiểm soát Claude Code. CRUD là bài test tốt vì nó chạm nhiều lớp: route, validation, service, repository, error handling, logging và test. Nếu không có plan-first, Claude dễ tạo patch rộng, đổi architecture hoặc tự chọn API contract khác với project.

Nguyên tắc chính:

- Bắt đầu bằng `plan` mode để Claude đọc và hiểu trước khi sửa.
- Chốt API contract trước khi implement: endpoint, request, response, status code, error shape, validation và logging.
- Không để Claude tự thêm dependency, đổi framework, đổi ORM, đổi logger, đổi error format hoặc tạo migration nếu chưa được approve.
- Implement theo slice nhỏ, có file list rõ.
- Unit test khóa business rule; integration test khóa HTTP contract.
- Review diff trước khi accept; rollback theo file nếu patch sai.

Contract tham khảo cho `taskflow-ai`:

| Endpoint | Thành công | Validation/error tối thiểu | Ghi chú maintainability |
| --- | --- | --- | --- |
| `POST /tasks` | `201` + task mới theo convention | title required, trim không rỗng, body field lạ xử lý theo pattern hiện có | Không tự thêm field ngoài contract |
| `GET /tasks` | `200` + danh sách | filter/pagination sai trả validation error nếu có filter | Có limit/pagination nếu project đã có pattern |
| `GET /tasks/:id` | `200` + task | id sai format hoặc task không tồn tại | Không leak thông tin task của user khác nếu có auth |
| `PATCH /tasks/:id` | `200` + task đã update | update body rỗng, field không được phép, title whitespace | Không cho update id/owner/system field |
| `DELETE /tasks/:id` | `204` hoặc response hiện có | not found | Bám convention hiện có, không đổi tùy ý |

## Sơ đồ tư duy hoặc luồng xử lý

```text
Yêu cầu CRUD
  |
  v
Git state sạch?
  |
  +-- Không -> dừng, đọc diff, tách thay đổi người khác
  |
  v
Claude Code plan mode
  |
  v
Đọc backend convention
  |
  +-- route registration
  +-- validation schema
  +-- error handler
  +-- logger
  +-- test setup
  |
  v
API contract
  |
  +-- endpoints
  +-- request/response
  +-- status codes
  +-- validation
  +-- error shape
  +-- logging fields
  |
  v
Plan file-by-file
  |
  v
Developer approve
  |
  v
Implement slice nhỏ
  |
  v
Unit test + integration test
  |
  v
git diff --stat -> git diff
  |
  v
Review: contract, security, maintainability, performance
  |
  +-- Đạt -> commit thủ công / PR
  |
  +-- Sai -> rollback theo file hoặc yêu cầu patch nhỏ
```

Luồng prompt nên dùng:

```text
Explore/read-only
  -> Contract
  -> Plan file-by-file
  -> Implement with boundaries
  -> Test diagnosis
  -> Diff review
```

## Bảng so sánh

| Cách làm | Lợi ích | Rủi ro | Khi dùng |
| --- | --- | --- | --- |
| Implement-first | Nhanh ở demo nhỏ | Contract drift, patch rộng, đổi architecture | Chỉ dùng trong sandbox throwaway |
| Plan-first | Kiểm soát scope và file list | Tốn thêm lượt chat | Default cho repo team |
| Contract-first | Test và frontend rõ ràng | Cần quyết định trước | API public hoặc có nhiều consumer |
| Test-after | Dễ bắt đầu | Có thể test theo implementation sai | Task nhỏ, contract đã rõ |
| Test-first hoặc test-plan-first | Khóa behavior trước | Tốn công thiết kế assertion | CRUD quan trọng, bug fix, regression |

| Chủ đề | Nên làm | Không nên làm |
| --- | --- | --- |
| Validation | Validate ở boundary theo schema/convention hiện có; service giữ business rule quan trọng | Để database là nơi đầu tiên báo lỗi input |
| Error handling | Dùng centralized error handler hoặc pattern hiện có | Mỗi route tự format lỗi một kiểu |
| Logging | Log action, id, request id, user id nếu có, duration, outcome | Log raw token, password, cookie, secret hoặc body nhạy cảm |
| Architecture | Bắt chước module tương tự trong project | Thêm framework/ORM/repository pattern mới |
| Test | Unit test rule, integration test contract | Chỉ snapshot hoặc chỉ kiểm tra status code |
| Rollback | `git restore -- path` cho tracked file, `git clean -f -- path` cho file mới đã review | `git reset --hard`, `git clean -fd` trong repo có nhiều worker |

| Command | Chạy ở đâu | Dùng để làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `git status --short` | Root `taskflow-ai` | Kiểm tra working tree | Rỗng hoặc file đã hiểu | Bỏ sót thay đổi của worker khác nếu không đọc |
| `claude --permission-mode plan` | Root `taskflow-ai` | Mở session đọc/lập plan | Claude sẵn sàng nhận prompt | Plan sai nếu đọc thiếu file |
| `git diff --stat` | Root `taskflow-ai` | Xem phạm vi patch | File list khớp plan | Không thấy logic chi tiết |
| `git diff` | Root `taskflow-ai` | Review patch | Diff đúng contract | Diff dài dễ bỏ sót |
| `npm run test -- --run` | Folder có `package.json` backend | Chạy test một lần nếu script hỗ trợ | Test pass, exit code `0` | Có thể phụ thuộc database/test env |
| `git restore -- path/to/file` | Root `taskflow-ai` | Rollback tracked file | Không output nếu thành công | Mất thay đổi chưa commit trong file đó |

## Lỗi thường gặp

1. Prompt "create CRUD API" quá rộng  
   Claude có thể tự tạo architecture mới, đổi route prefix hoặc thêm dependency. Cách sửa: yêu cầu đọc module tương tự và lập plan file-by-file trước.

2. Không chốt error shape  
   Endpoint này trả `{ error: "..." }`, endpoint khác trả `{ message, code }`. Cách sửa: bắt Claude tìm error handler hiện có và bám pattern.

3. Validation chỉ có happy path  
   Test tạo task thành công nhưng không test title whitespace, body rỗng, id sai format, field không được phép. Cách sửa: contract phải liệt kê negative cases.

4. Logging lộ dữ liệu  
   Claude có thể log raw request body để debug. Cách sửa: prompt rõ field được log và field bị cấm; review diff tìm `authorization`, `cookie`, `password`, `token`, `secret`.

5. Integration test phụ thuộc database thật  
   Test có thể dùng connection string từ `.env` dev hoặc production. Cách sửa: đọc test setup trước, yêu cầu Claude không chạm production data, không chạy migration destructive.

6. Patch vượt scope nhưng test vẫn pass  
   Test pass không có nghĩa architecture đúng. Cách sửa: review `git diff --stat`, so với file list trong plan.

7. Rollback toàn repo  
   Trong môi trường nhiều worker, `git reset --hard` có thể xóa thay đổi của người khác. Cách sửa: rollback theo file đã review.

## Cách debug

Khi Claude Code tạo patch quá rộng:

```bash
git diff --stat
```

Chạy ở root `taskflow-ai`. Lệnh này cho biết file nào bị chạm. Nếu output có file ngoài plan, dừng implement và yêu cầu Claude giải thích trước khi sửa tiếp.

```text
Patch đang chạm file ngoài plan. Hãy giải thích vì sao từng file cần thay đổi.
Không sửa thêm. Đề xuất cách thu hẹp patch về contract ban đầu.
```

Khi test fail:

1. Chạy test tập trung trong folder backend có `package.json`, ví dụ:

```bash
npm run test -- --run tasks
```

Lệnh này cố gắng chạy test liên quan tới tasks nếu test runner hỗ trợ filter. Output kỳ vọng là danh sách test pass/fail liên quan. Rủi ro: syntax filter phụ thuộc script; đọc `package.json` trước nếu không chắc.

2. Đưa failure ngắn vào Claude:

```text
Đây là failure output. Hãy phân tích nguyên nhân, chưa sửa file.
Phân loại: implementation bug, test sai contract, thiếu setup, hay môi trường.
Chỉ đề xuất patch nhỏ nhất.
```

3. Nếu lỗi do contract không rõ, quay lại bước contract. Không vá test cho pass nếu behavior chưa đúng.

Khi nghi ngờ contract drift:

- So sánh diff với bảng endpoint/status code đã duyệt.
- Kiểm tra response body của success và error.
- Tìm các thay đổi ở file config, dependency, route prefix hoặc global error handler.
- Yêu cầu Claude review read-only:

```text
So sánh diff hiện tại với API contract đã duyệt.
Liệt kê mọi điểm drift, phân loại blocker/should fix/nice to have.
Không sửa file.
```

Khi cần rollback:

```bash
git restore -- path/to/tracked-file
```

Chạy ở root `taskflow-ai`. Lệnh này rollback một tracked file. Rủi ro: mất thay đổi chưa commit trong file đó.

```bash
git clean -f -- path/to/new-file
```

Chạy ở root `taskflow-ai`. Lệnh này xóa một untracked file cụ thể. Chỉ dùng sau khi chắc chắn file đó do task hiện tại tạo và không phải file của worker khác.

## Link tài liệu nên đọc

- Claude Code Quickstart: https://code.claude.com/docs/en/quickstart
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code Memory: https://code.claude.com/docs/en/memory
- Claude Code Slash Commands: https://code.claude.com/docs/en/slash-commands
- Git diff documentation: https://git-scm.com/docs/git-diff
- Git restore documentation: https://git-scm.com/docs/git-restore
- Fastify documentation: https://fastify.dev/docs/latest/
- Vitest guide: https://vitest.dev/guide/
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
