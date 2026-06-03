# Document — Day 11

## Tóm tắt kiến thức

Day 11 tập trung vào testing với Claude Code, nhưng trọng tâm không phải là "AI viết test thật nhanh". Trọng tâm là dùng Claude để tăng tốc phần cơ học của testing trong khi developer vẫn kiểm soát test intent, assertion và rủi ro flaky.

Các nguyên tắc chính:

- `Test pyramid` giúp phân tầng test theo chi phí và mục tiêu: unit nhanh và hẹp, integration khóa contract giữa nhiều lớp, e2e kiểm tra flow người dùng.
- Unit test nên bảo vệ business rule nhỏ: validate input, normalize dữ liệu, status transition, permission rule.
- Integration test nên bảo vệ API contract: status code, response body, error shape, database side effect, route wiring.
- E2E test nên bảo vệ flow quan trọng từ góc nhìn user: tạo task từ UI, thấy task mới xuất hiện, lỗi validation hiển thị đúng.
- Claude Code có thể sinh boilerplate test tốt, nhưng developer phải review assertion. Assertion yếu tạo cảm giác an toàn giả.
- Coverage chỉ cho biết code đã được chạy, không chứng minh behavior đã được kiểm chứng. Coverage là tín hiệu phụ để tìm vùng mù.
- Test chất lượng cần có meaningful assertion, negative path, deterministic setup, test data isolation, và tránh snapshot rộng.

Với `taskflow-ai`, flow tạo task nên được bảo vệ ở ba tầng:

| Tầng | Behavior nên test | Assertion chính |
| --- | --- | --- |
| Unit | Title sau trim không được rỗng | trả validation error cụ thể hoặc throw domain error |
| Unit | Task mới có default status đúng | result có `status: "open"` hoặc value theo contract |
| Integration | `POST /tasks` tạo task thành công | `201`, body có `id/title/status`, database/repository có task |
| Integration | `POST /tasks` reject title invalid | `400`, error shape đúng, không tạo dữ liệu |
| E2E | User tạo task từ UI | task mới hiển thị trong list, form state đúng |

Claude Code nên đi theo workflow:

```text
Explore test setup
  -> Test matrix
  -> Plan file-by-file
  -> Implement tests
  -> Run focused tests
  -> Diagnose failure
  -> Review assertions
```

## Sơ đồ tư duy hoặc luồng xử lý

```text
Yêu cầu: testing create task flow
  |
  v
Kiểm tra git status
  |
  v
Claude Code plan mode
  |
  +-- đọc package.json
  +-- đọc Vitest/Jest config
  +-- đọc test helper/setup
  +-- đọc task route/service/schema
  +-- đọc Playwright config/UI flow
  |
  v
Test matrix
  |
  +-- Unit: business rule
  +-- Integration: API contract
  +-- E2E: user flow
  |
  v
Developer review matrix
  |
  +-- assertion có meaningful?
  +-- negative path đủ chưa?
  +-- setup deterministic chưa?
  +-- data isolation rõ chưa?
  |
  v
Implement test bằng Claude
  |
  v
Run focused tests
  |
  +-- Pass -> review diff + coverage như tín hiệu phụ
  |
  +-- Fail -> diagnose trước khi sửa
            |
            +-- production bug
            +-- test sai contract
            +-- setup thiếu
            +-- data isolation
            +-- flaky/timing
            +-- environment
```

Luồng quyết định chọn tầng test:

```text
Behavior là pure business rule?
  -> Unit test

Behavior cần route/validation/error/database cùng chạy?
  -> Integration test

Behavior chỉ có giá trị khi user thao tác qua browser?
  -> E2E test

Behavior đã được test ở tầng thấp và e2e chỉ lặp lại chi tiết?
  -> Không viết e2e, giữ test thấp hơn
```

## Bảng so sánh

| Tiêu chí | Unit test | Integration test | E2E test |
| --- | --- | --- | --- |
| Mục tiêu | Khóa rule nhỏ | Khóa contract giữa nhiều lớp | Khóa workflow user |
| Ví dụ | `createTask` reject title whitespace | `POST /tasks` trả `400` và không ghi DB | User nhập title, submit, thấy task |
| Tốc độ | Nhanh nhất | Trung bình | Chậm nhất |
| Flaky risk | Thấp nếu không dùng time/random không kiểm soát | Trung bình nếu test DB/setup kém | Cao hơn nếu locator/data/timing kém |
| Claude hỗ trợ tốt ở đâu | Sinh case matrix, boilerplate, mocks | Đọc route/test helper, sinh request assertions | Sinh spec, locator, debug trace |
| Developer phải review gì | Mock boundary, assertion, edge cases | Contract, database side effect, cleanup | Locator, wait strategy, test data, real user outcome |

| Chủ đề | Nên làm | Không nên làm |
| --- | --- | --- |
| Assertion | Kiểm tra status/body/error/side effect cụ thể | `toBeDefined`, `not.toThrow` cho mọi thứ |
| Negative path | Test invalid title, empty body, not found, permission nếu có | Chỉ test happy path |
| Data isolation | Unique data per test, cleanup/reset rõ | Dùng seed data cũ hoặc title cố định dễ đụng |
| Mocking | Mock ở boundary ngoài hệ thống cần test | Mock chính service đang muốn kiểm chứng |
| Snapshot | Snapshot nhỏ, ổn định, có chủ đích | Snapshot toàn response/page rộng |
| Playwright wait | Web-first assertion, locator ổn định | `waitForTimeout` để che flaky |
| Coverage | Dùng để tìm vùng mù | Dùng làm mục tiêu duy nhất |
| Security | Dùng test DB/credential riêng, giữ trace/screenshot như artifact nhạy cảm | Chạy test ghi dữ liệu bằng production credential hoặc paste secret vào prompt |
| Maintainability | Tên test theo behavior, helper setup rõ, assertion bám public contract | Test implementation detail, fixture quá lớn, helper che mất intent |

| Command | Chạy ở đâu | Dùng để làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `git status --short` | Root `taskflow-ai` | Kiểm tra working tree trước khi sửa | Rỗng hoặc file đã hiểu rõ | Có thể thấy thay đổi của worker khác; không rollback |
| `npm pkg get scripts` | Folder có `package.json` backend/root | Xem script test thật | JSON scripts có `test`, `test:unit`, `test:e2e` nếu có | Chạy nhầm package sẽ đọc sai script |
| `claude --permission-mode plan` | Root `taskflow-ai` | Mở Claude ở mode khảo sát/lập plan | Session sẵn sàng nhận prompt | Claude vẫn có thể suy đoán nếu đọc thiếu file |
| `npm run test -- --run` | Backend package dùng Vitest | Chạy Vitest một lần | Test pass, exit code `0` | Script có thể không nhận `--run` nếu không phải Vitest |
| `npm test -- --runInBand` | Backend package dùng Jest | Chạy Jest tuần tự để debug | Test pass, exit code `0` | Chậm hơn, không đại diện parallel CI |
| `npm run test -- --run --coverage` | Backend package dùng Vitest | Xem coverage Vitest | Bảng coverage | Có thể thiếu coverage provider/config |
| `npm test -- --coverage` | Backend package dùng Jest | Xem coverage Jest | Bảng coverage | Dễ bị dùng sai như KPI duy nhất |
| `npx playwright test --list` | Package có Playwright config | Liệt kê test | Danh sách spec/test | Có thể tốn thời gian nếu global setup nặng |
| `npx playwright test e2e/create-task.spec.ts --project=chromium` | Package có Playwright config | Chạy riêng create task e2e | Spec pass, trace nếu fail | Cần app server/test DB/port đúng |
| `npx playwright show-trace trace.zip` | Nơi có file trace | Debug e2e failure | Trace Viewer mở được | Trace có thể chứa dữ liệu nhạy cảm |

## Lỗi thường gặp

1. Để Claude viết test trước khi đọc test setup  
   Kết quả thường là thêm runner mới, import sai helper, hoặc tạo test không chạy trong CI. Cách sửa: bắt Claude đọc `package.json`, config và test tương tự trước.

2. Assertion quá yếu  
   Test kiểu `expect(response).toBeDefined()` pass dù status/body sai. Cách sửa: yêu cầu assertion về status code, response body, error code/message và side effect.

3. Chỉ test happy path  
   Flow tạo task pass với title hợp lệ nhưng không test title rỗng, whitespace, body thiếu field. Cách sửa: test matrix bắt buộc có negative path.

4. Mock quá sâu  
   Integration test mock route, service và repository đến mức không còn kiểm tra integration. Cách sửa: mock external boundary, không mock lớp trung tâm của behavior đang cần kiểm chứng.

5. Test data không isolated  
   E2E dùng title cố định `Test task`, test pass/fail tùy data cũ. Cách sửa: unique title, cleanup bằng API/helper, hoặc reset test DB.

6. Playwright locator brittle  
   Selector như `.container > div:nth-child(3) button` dễ vỡ khi UI đổi layout. Cách sửa: dùng `getByRole`, `getByLabel`, `getByText` với accessible name rõ.

7. Dùng sleep để chữa flaky  
   `waitForTimeout` làm test chậm mà không giải quyết race condition. Cách sửa: dùng web-first assertion hoặc đợi state cụ thể.

8. Snapshot rộng  
   Snapshot toàn DOM/response khiến reviewer update snapshot cho pass mà không hiểu thay đổi. Cách sửa: assertion cụ thể vào field/element quan trọng.

9. Coverage cao nhưng behavior thấp  
   AI có thể gọi function để tăng dòng chạy nhưng không assert gì đáng kể. Cách sửa: review test intent trước khi nhìn coverage.

10. Sửa production code vì test fail mà chưa diagnose  
   Có thể test sai contract hoặc setup thiếu. Cách sửa: phân loại failure trước, chỉ sửa production code khi xác định bug thật.

## Cách debug

Khi không biết backend dùng Vitest hay Jest, chạy:

```bash
npm pkg get scripts
```

Chạy trong folder backend có `package.json`. Lệnh này in script test thật. Output kỳ vọng cho thấy `vitest`, `jest`, `test:unit`, `test:integration` hoặc script tương đương. Rủi ro: nếu backend nằm trong subfolder mà bạn chạy ở root, output có thể không phản ánh package backend.

Nếu muốn tìm config test:

```bash
find . -maxdepth 4 \( -name "vitest.config.*" -o -name "jest.config.*" -o -name "playwright.config.*" \)
```

Chạy ở root `taskflow-ai`. Lệnh này tìm các file config test thường gặp. Output kỳ vọng là path tới config hiện có. Rủi ro thấp vì read-only; trên Windows PowerShell dùng `Get-ChildItem -Recurse -Include vitest.config.*,jest.config.*,playwright.config.*`.

Khi backend test fail, chạy tập trung vào test file hoặc pattern nếu script hỗ trợ:

```bash
npm run test -- --run tasks
```

Chạy trong backend package dùng Vitest. Lệnh này cố chạy test liên quan `tasks` một lần. Output kỳ vọng là danh sách test task pass/fail. Rủi ro: filter syntax phụ thuộc runner/script; nếu không chắc, đọc docs hoặc script trước.

Với Jest:

```bash
npm test -- tasks --runInBand
```

Chạy trong backend package dùng Jest để lọc test path/name liên quan `tasks` và chạy tuần tự. Output kỳ vọng là failure tập trung hơn. Rủi ro: pattern có thể match quá rộng hoặc quá hẹp; không kết luận coverage tổng thể từ lệnh lọc.

Khi E2E fail, chạy headed/debug:

```bash
npx playwright test e2e/create-task.spec.ts --project=chromium --headed --debug
```

Chạy ở package có Playwright config. Lệnh này mở browser để quan sát flow. Output kỳ vọng là browser/inspector cho thấy bước fail. Rủi ro: debug mode không phù hợp CI và có thể treo nếu bạn không đóng session.

Khi cần xem trace:

```bash
npx playwright show-trace trace.zip
```

Chạy ở nơi có `trace.zip` từ failure. Output kỳ vọng là Trace Viewer. Rủi ro: trace có thể chứa dữ liệu nhập vào form hoặc token test; không chia sẻ public.

Prompt debug nên dùng với Claude:

```text
Đây là failure output rút gọn. Hãy diagnose, chưa sửa file.

Phân loại lỗi:
- production bug
- test sai contract
- setup thiếu
- data isolation
- flaky/timing
- environment

Chỉ ra assertion fail, nguyên nhân có khả năng nhất, và patch nhỏ nhất để verify lại.
```

Khi nghi ngờ test do Claude viết không có giá trị:

```text
Review các test mới theo tiêu chí test quality.

Với từng test, hãy cho biết:
- Behavior được bảo vệ là gì.
- Bug nào test này sẽ bắt được.
- Assertion nào là assertion chính.
- Test có deterministic không.
- Có trùng tầng hoặc brittle không.

Không sửa file.
```

## Link tài liệu nên đọc

- Claude Code Quickstart: https://code.claude.com/docs/en/quickstart
- Claude Code CLI Reference: https://code.claude.com/docs/en/cli-reference
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Security: https://code.claude.com/docs/en/security
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Vitest Guide: https://vitest.dev/guide/
- Vitest Coverage: https://vitest.dev/guide/coverage
- Jest Getting Started: https://jestjs.io/docs/getting-started
- Jest CLI Options: https://jestjs.io/docs/cli
- Playwright Test Introduction: https://playwright.dev/docs/intro
- Playwright Locators: https://playwright.dev/docs/locators
- Playwright Assertions: https://playwright.dev/docs/test-assertions
- Playwright Trace Viewer: https://playwright.dev/docs/trace-viewer
- Testing Trophy: https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications
