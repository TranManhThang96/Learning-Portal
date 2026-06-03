# Day 11 — Testing với Claude Code

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Dùng Claude Code để khảo sát test setup hiện có trong `taskflow-ai` trước khi thêm test mới.
- Phân biệt rõ `unit test`, `integration test`, `e2e test` và biết test nào thuộc tầng nào trong `test pyramid`.
- Yêu cầu Claude sinh test cho backend bằng Vitest hoặc Jest nhưng vẫn review assertion như reviewer chịu trách nhiệm production.
- Viết test backend có giá trị: meaningful assertion, negative path, deterministic setup, test data isolation, không phụ thuộc thứ tự chạy.
- Viết Playwright e2e cho flow tạo task trên UI, dùng locator ổn định và web-first assertion thay vì sleep thủ công.
- Hiểu vì sao coverage chỉ là tín hiệu phụ: coverage cao không đồng nghĩa behavior quan trọng đã được kiểm chứng.
- Thiết kế workflow Claude Code cho testing: explore -> test plan -> implement tests -> run -> diagnose -> review.

## 2. Bối cảnh thực tế

Sau Day 08, Day 09 và Day 10, `taskflow-ai` bắt đầu có đủ backend CRUD, database model và frontend task UI. Đây là lúc dễ rơi vào hai cực đoan:

- Không có test, chỉ chạy app thủ công rồi tin rằng mọi thứ ổn.
- Có nhiều test do AI sinh ra nhưng assertion yếu, chủ yếu kiểm tra "không crash", snapshot rộng, hoặc mock quá sâu khiến test pass dù behavior sai.

Claude Code rất hữu ích khi cần tạo test nhanh vì nó có thể đọc route, service, schema, component và luồng UI. Nhưng test là nơi developer không được giao quyền quyết định hoàn toàn cho AI. Lý do: một test sai assertion có thể tạo cảm giác an toàn giả. Test tệ còn nguy hiểm hơn không có test vì team bắt đầu tin vào pipeline.

Trong project thật, lỗi testing thường không nằm ở cú pháp Vitest/Jest/Playwright mà nằm ở chất lượng câu hỏi:

- Test đang bảo vệ behavior nào?
- Assertion có bắt được bug thật không?
- Test có deterministic không, hay phụ thuộc thời gian, thứ tự chạy, network, seed data cũ?
- Test data có bị leak giữa test cases không?
- Negative path có được test không?
- E2E test có kiểm tra đúng outcome người dùng nhìn thấy không?
- Coverage tăng vì test có ý nghĩa, hay chỉ vì chạm dòng code?

Claude Code nên được dùng như một `test assistant`: đọc code, đề xuất test matrix, tạo boilerplate, chạy test, phân tích failure. Developer vẫn là người duyệt test intent, assertion và trade-off.

Không nên dùng Claude Code để tự động "tăng coverage lên 90%" mà không có test plan. Mục tiêu coverage kiểu đó thường đẩy AI tạo test nông, mock implementation detail, hoặc snapshot toàn bộ response/UI. Hãy bắt đầu từ risk: code nào quan trọng nhất, bug nào đắt nhất, contract nào cần khóa lại.

## 3. Kiến thức nền

`Test pyramid` là cách phân bổ test theo chi phí và độ tin cậy:

| Tầng | Mục tiêu | Ví dụ trong `taskflow-ai` | Tốc độ | Rủi ro nếu lạm dụng |
| --- | --- | --- | --- | --- |
| Unit | Kiểm tra business rule nhỏ, không phụ thuộc I/O thật | `createTask` reject title rỗng, trim title, validate status transition | Rất nhanh | Mock quá sâu, test implementation detail |
| Integration | Kiểm tra nhiều lớp cùng chạy với boundary thật hơn | `POST /tasks` qua Fastify/Nest route, validation, service, repository test DB | Trung bình | Setup database phức tạp, test chậm nếu không isolate data |
| E2E | Kiểm tra flow người dùng qua browser/API thật | User mở task page, nhập title, bấm Create, thấy task mới | Chậm hơn | Flaky nếu locator yếu, data không sạch, phụ thuộc timing |

Pyramid không có nghĩa là "chỉ viết thật nhiều unit test". Nó nghĩa là dùng đúng tầng cho đúng rủi ro. Với `taskflow-ai`, flow tạo task có giá trị ở cả ba tầng:

- Unit test: service không cho tạo task với title chỉ có khoảng trắng.
- Integration test: API `POST /tasks` trả `201`, response body đúng contract, database có task mới.
- E2E test: user tạo task từ UI và thấy task xuất hiện trong list.

### Vitest và Jest cho backend

Vitest phù hợp với Node.js + TypeScript hiện đại, đặc biệt nếu repo đã dùng Vite hoặc ESM. Vitest hỗ trợ API quen thuộc như `describe`, `it`, `expect`, mocking qua `vi.fn`, chạy một lần bằng `vitest run`, và coverage bằng `vitest run --coverage`.

Jest vẫn phổ biến trong backend Node.js, đặc biệt trong NestJS hoặc repo đã có setup Jest. Jest có CLI như `jest`, `jest --watch`, `jest --coverage`, `jest --runInBand`, hỗ trợ async test qua `async/await`, `.resolves`, `.rejects`, và mock function.

Không chọn framework test theo sở thích của Claude. Hãy đọc `package.json`, config và test hiện có. Nếu backend đã dùng Jest, đừng để Claude thêm Vitest chỉ vì ví dụ mới hơn. Nếu backend đã dùng Vitest, đừng thêm Jest cho một file test đơn lẻ.

### Playwright cho e2e

Playwright Test phù hợp để kiểm tra browser flow vì có locator theo role/text/label, auto-wait và web-first assertion. Với flow tạo task, test nên tương tác như user:

- Mở trang task.
- Điền title vào textbox có accessible name rõ.
- Bấm button Create.
- Kiểm tra task mới xuất hiện.
- Kiểm tra request/API hoặc database state nếu project đã có fixture phù hợp.

Tránh `page.waitForTimeout(1000)` như mặc định. Playwright assertion như `await expect(locator).toBeVisible()` tự retry trong timeout nên ổn định hơn sleep thủ công.

### Meaningful assertion

Assertion có giá trị là assertion sẽ fail khi behavior quan trọng sai. Ví dụ:

| Assertion yếu | Assertion tốt hơn |
| --- | --- |
| `expect(response.status).toBeLessThan(500)` | `expect(response.status).toBe(201)` |
| `expect(body).toBeDefined()` | `expect(body).toMatchObject({ title: "Ship Day 11", status: "open" })` |
| `expect(tasks.length).toBeGreaterThan(0)` | `expect(tasks).toContainEqual(expect.objectContaining({ id: created.id, title }))` |
| Snapshot toàn bộ page | Check heading, form state, new task row, error message cụ thể |

Với Claude Code, prompt phải nói rõ: "không chỉ kiểm tra happy path; phải có negative path và assertion cụ thể về contract".

### Coverage là tín hiệu phụ

Coverage trả lời câu hỏi "dòng code nào đã được chạy", không trả lời "behavior nào đã được kiểm chứng". Một test có thể chạy qua 95% code nhưng không assert đúng gì quan trọng. Ngược lại, coverage 70% nhưng khóa được critical path có thể đáng tin hơn coverage 95% bằng snapshot nông.

Coverage hữu ích để tìm vùng mù:

- File quan trọng không có test.
- Branch validation/error chưa chạy.
- Code mới không được chạm tới.

Coverage không nên là KPI duy nhất. Hãy kết hợp coverage với test review checklist: assertion, negative path, deterministic setup, data isolation và failure signal.

## 4. Step-by-step thực hành

Mục tiêu thực hành: dùng Claude Code để bổ sung test backend bằng Vitest hoặc Jest và Playwright e2e cho flow tạo task trong `taskflow-ai`, không phá scope của các worker khác.

### Bước 1: Kiểm tra working tree và xác định test setup

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này hiển thị file đang thay đổi ở dạng ngắn. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có thay đổi của worker khác, đừng rollback hoặc sửa chồng; hãy ghi lại và tránh chạm file đó.

Tìm package Node liên quan:

```bash
find . -maxdepth 3 -name package.json
```

Lệnh này chạy ở root `taskflow-ai` để tìm `package.json` trong monorepo. Output kỳ vọng có thể là `./package.json`, `./backend/package.json`, `./frontend/package.json`. Rủi ro thấp vì read-only; trên Windows PowerShell có thể dùng `Get-ChildItem -Recurse -Filter package.json -Depth 3`.

Đọc script test thật trước khi chạy:

```bash
npm pkg get scripts
```

Lệnh này chạy trong thư mục có `package.json` của backend hoặc root package. Nó in ra các script như `test`, `test:unit`, `test:integration`, `test:e2e`. Output kỳ vọng giúp xác định repo đang dùng Vitest hay Jest. Rủi ro: nếu chạy nhầm folder, output có thể là script frontend hoặc root, không phải backend.

### Bước 2: Mở Claude Code ở plan mode để khảo sát test hiện có

Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude Code ở mode đọc và lập plan trước khi sửa. Output kỳ vọng là session Claude sẵn sàng nhận prompt. Rủi ro thấp hơn implement mode, nhưng Claude vẫn có thể suy đoán nếu chưa đọc đủ file.

Prompt khám phá:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát test setup hiện có trước khi đề xuất test mới.

Ràng buộc:
- Chưa sửa file.
- Chỉ đọc file cần thiết.
- Tìm backend package, test runner đang dùng là Vitest hay Jest, config test, test helpers, database test setup, API route tasks và frontend task flow nếu có.
- Nêu rõ file đã đọc và bằng chứng từ code.
- Không đề xuất thêm dependency hoặc đổi test runner.
- Output gồm: test commands thật, test gaps, rủi ro flaky, và đề xuất test matrix cho flow tạo task.
```

Kỳ vọng: Claude liệt kê `package.json`, config như `vitest.config.ts` hoặc `jest.config.*`, test helper, route/service task, Playwright config nếu có. Nếu Claude chưa đọc test setup mà đã đề xuất file test, yêu cầu đọc bổ sung.

### Bước 3: Chốt test matrix trước khi viết test

Gửi prompt trong cùng session:

```text
Dựa trên code đã đọc, hãy lập test matrix cho flow tạo task.

Yêu cầu:
- Tách rõ unit, integration, e2e.
- Mỗi test case ghi behavior cần bảo vệ, fixture/setup, assertion chính, negative path nếu có.
- Với backend, ưu tiên meaningful assertion về status code, response body, error code/message, database side effect.
- Với e2e Playwright, ưu tiên locator theo role/label/text và web-first assertion.
- Ghi rõ test nào không nên viết vì quá brittle hoặc trùng tầng.
- Chưa sửa file.
```

Test matrix tốt nên có dạng:

| Tầng | Case | Assertion chính |
| --- | --- | --- |
| Unit | `createTask` reject title whitespace | throw/return validation error cụ thể |
| Unit | `createTask` normalize title | title trong result đã trim, status default đúng |
| Integration | `POST /tasks` success | `201`, body có `id`, `title`, `status`, database có row |
| Integration | `POST /tasks` invalid title | `400`, error code đúng, database không tạo row |
| E2E | User tạo task từ UI | form submit thành công, task mới hiển thị trong list |

Nếu Claude đề xuất snapshot toàn response hoặc toàn page, yêu cầu thay bằng assertion cụ thể.

### Bước 4: Implement backend test bằng Vitest hoặc Jest

Sau khi duyệt test matrix, mở session implement có boundary hẹp. Chạy trong root `taskflow-ai`:

```bash
claude --permission-mode default --allowedTools "Read" "Edit" "Bash(git status *)" "Bash(git diff *)" "Bash(npm run test*)" "Bash(npm test *)"
```

Lệnh này cho Claude đọc, edit và chạy một số command test/Git read-only. Mỗi rule trong `--allowedTools` được truyền riêng để bám cú pháp CLI hiện tại; nếu version Claude Code của bạn khác, kiểm tra lại bằng `claude --help` hoặc official CLI reference trước khi dùng. Output kỳ vọng là session sẵn sàng. Rủi ro: allowlist vẫn có thể chạy script test tốn thời gian hoặc chạm database test; không thêm `npm install`, migration, docker destructive command nếu chưa duyệt.

Prompt implement backend test:

```text
Implement backend tests cho flow tạo task theo test matrix đã approve.

Ràng buộc:
- Dùng test runner hiện có trong backend: Vitest hoặc Jest. Không thêm test runner mới.
- Chỉ sửa/tạo file test và test helper đã nằm trong plan.
- Không sửa production code trừ khi test phát hiện bug rõ và phải hỏi tôi trước.
- Không mock quá sâu qua service/repository nếu integration test cần kiểm tra route contract.
- Unit test phải có negative path cho title rỗng/whitespace.
- Integration test phải assert status code, response body, error shape và database side effect hoặc repository call phù hợp với setup hiện có.
- Test data phải isolated: unique title/id per test, cleanup bằng helper hiện có hoặc transaction/reset test DB.
- Không dùng snapshot rộng.
- Sau khi edit, tóm tắt file changed và command test nên chạy.
```

Ví dụ nếu backend dùng Vitest, lệnh chạy một lần thường là:

```bash
npm run test -- --run
```

Lệnh này chạy trong folder backend có `package.json`. Nó thường buộc Vitest chạy một lần thay vì watch mode. Output kỳ vọng là test pass và exit code `0`. Rủi ro: nếu script `test` không trỏ tới Vitest hoặc không nhận `--run`, command có thể fail; đọc script thật trước.

Ví dụ nếu backend dùng Jest:

```bash
npm test -- --runInBand
```

Lệnh này chạy trong folder backend có `package.json` để chạy Jest tuần tự, hữu ích khi debug test có database hoặc shared resource. Output kỳ vọng là test pass và exit code `0`. Rủi ro: chạy tuần tự chậm hơn; nếu test phụ thuộc thứ tự thì pass tuần tự chưa chắc pass khi parallel trong CI.

Chạy coverage như tín hiệu phụ, không phải mục tiêu chính. Với Vitest:

```bash
npm run test -- --run --coverage
```

Lệnh này chạy trong folder backend nếu script hỗ trợ Vitest và coverage provider đã được cài/config. Output kỳ vọng là bảng coverage gồm statements/branches/functions/lines. Rủi ro: coverage có thể yêu cầu dependency provider hoặc config; đừng để Claude thêm dependency chỉ để đạt số đẹp nếu team chưa duyệt.

Với Jest:

```bash
npm test -- --coverage
```

Lệnh này chạy trong folder backend để tạo coverage report bằng Jest. Output kỳ vọng là bảng coverage và exit code theo ngưỡng hiện có. Rủi ro: coverage chạy chậm hơn và có thể fail vì threshold cũ, không nhất thiết vì test mới sai.

### Bước 5: Implement Playwright e2e cho flow tạo task

Trước tiên kiểm tra Playwright đã có trong project chưa. Chạy trong root `taskflow-ai` hoặc frontend package nếu repo tách package:

```bash
npm pkg get devDependencies
```

Lệnh này đọc `devDependencies` để xem có `@playwright/test` không. Output kỳ vọng có package này nếu e2e đã setup. Rủi ro: nếu chạy nhầm package, bạn có thể tưởng Playwright chưa có dù nó nằm ở root hoặc package khác.

Nếu project đã có Playwright config, chạy danh sách test:

```bash
npx playwright test --list
```

Lệnh này chạy ở package có `playwright.config.*` để liệt kê test mà không mở browser chạy thật. Output kỳ vọng là danh sách spec/test names. Rủi ro thấp; nếu config có global setup nặng, vẫn có thể tốn thời gian.

Nếu chưa có Playwright và team đã duyệt thêm dependency, command setup phổ biến là:

```bash
npm init playwright@latest
```

Lệnh này chạy ở root package hoặc package frontend theo kiến trúc repo. Nó tạo/cập nhật Playwright config, e2e folder và cài dependency theo prompt tương tác. Output kỳ vọng là wizard setup hoàn tất. Rủi ro: command có thể sửa `package.json`, lockfile và tạo example tests; chỉ chạy sau khi plan được approve, không chạy trong repo nhiều worker nếu chưa thống nhất.

Prompt implement e2e:

```text
Implement Playwright e2e test cho flow tạo task.

Ràng buộc:
- Dùng Playwright setup hiện có; nếu chưa có, chỉ đề xuất setup, chưa chạy install.
- Test phải dùng locator ổn định: getByRole, getByLabel, getByText có name cụ thể. Không dùng selector CSS brittle nếu UI có accessible name.
- Không dùng page.waitForTimeout.
- Setup test data deterministic: unique title theo timestamp/test id, cleanup bằng API/helper nếu có.
- Nếu app cần backend/frontend server, dùng webServer trong playwright config hiện có hoặc ghi rõ command cần chạy.
- Assertion chính: user submit task thành công và task mới hiển thị trong list; nếu API error, UI hiển thị error message rõ.
- Không snapshot toàn page.
- Chỉ sửa/tạo file e2e trong plan.
```

Chạy e2e tập trung:

```bash
npx playwright test e2e/create-task.spec.ts --project=chromium
```

Lệnh này chạy ở package có `playwright.config.*` để chạy riêng spec tạo task trên Chromium. Output kỳ vọng là test pass, kèm trace/screenshot nếu config bật khi fail. Rủi ro: cần app server, test database và port đúng; nếu chạy trên data dev không sạch, test có thể flaky.

Debug e2e bằng headed mode:

```bash
npx playwright test e2e/create-task.spec.ts --project=chromium --headed --debug
```

Lệnh này chạy ở package có Playwright config, mở browser thật và dừng cho debug. Output kỳ vọng là Playwright Inspector hoặc browser headed. Rủi ro: không phù hợp CI; có thể treo session nếu không tương tác.

Xem trace khi test fail:

```bash
npx playwright show-trace trace.zip
```

Lệnh này chạy ở nơi có file `trace.zip` do Playwright tạo. Output kỳ vọng là Trace Viewer mở lên để xem action, DOM snapshot, network. Rủi ro: trace có thể chứa dữ liệu form hoặc token test; không upload public nếu có thông tin nhạy cảm.

### Bước 6: Review test do Claude sinh

Chạy trong root `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này cho biết phạm vi thay đổi. Output kỳ vọng chỉ gồm file test, test helper, config Playwright nếu đã approve. Rủi ro: nếu production code hoặc lockfile bị sửa ngoài plan, dừng lại và review trước.

Xem diff chi tiết:

```bash
git diff
```

Lệnh này hiển thị patch chi tiết. Output kỳ vọng: test có assertion cụ thể, negative path, setup/teardown rõ, không snapshot rộng, không sleep. Rủi ro: diff test dài dễ bỏ sót assertion yếu; review theo từng test case.

Prompt review:

```text
Review diff test hiện tại như senior test reviewer, không sửa file.

Tập trung:
- Test case có bảo vệ behavior quan trọng không.
- Assertion có meaningful không hay chỉ kiểm tra không crash.
- Có negative path cho validation/error không.
- Setup có deterministic không, có phụ thuộc thời gian/network/data cũ không.
- Test data có isolated không.
- Có mock quá sâu làm mất giá trị integration test không.
- Playwright locator có ổn định và accessible không.
- Có snapshot rộng hoặc waitForTimeout không.
- Coverage tăng có đi kèm chất lượng assertion không.

Kết luận theo format: Blocker, Should fix, Nice to have, Test gaps.
```

### Bước 7: Diagnose failure trước khi sửa

Nếu test fail, không cho Claude sửa ngay. Gửi failure ngắn:

```text
Test fail như sau. Hãy phân tích nguyên nhân trước, chưa sửa file.

Yêu cầu:
- Phân loại: bug production code, test sai contract, setup thiếu, data isolation lỗi, timing/flaky, hoặc environment.
- Chỉ ra assertion nào fail và behavior mong đợi là gì.
- Đề xuất patch nhỏ nhất.
- Nếu cần sửa production code, hỏi lại tôi trước.
```

Nếu failure do data cũ, ưu tiên sửa fixture/setup thay vì nới assertion. Nếu failure do UI locator yếu, ưu tiên cải thiện accessible name hoặc locator theo role, không chuyển sang CSS selector dài nếu có lựa chọn tốt hơn.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```text
Hãy khảo sát test setup trong taskflow-ai.

Ràng buộc:
- Chưa sửa file.
- Tìm backend package, frontend package, test runner, Playwright config, test helper, database test setup và command test thật.
- Nêu file đã đọc và bằng chứng.
- Không đề xuất đổi Vitest sang Jest hoặc ngược lại.
- Output gồm test matrix sơ bộ cho flow tạo task và rủi ro flaky.
```

### Prompt lập test plan

```text
Lập test plan cho flow tạo task.

Yêu cầu:
- Chia unit/integration/e2e.
- Mỗi test ghi behavior, setup, assertion chính, negative path.
- Chỉ chọn test có giá trị regression rõ.
- Ghi test nào không nên viết vì trùng tầng hoặc brittle.
- Không implement.
```

### Prompt implement backend test

```text
Implement backend tests theo test plan đã approve.

Giới hạn:
- Dùng test runner hiện có: Vitest hoặc Jest.
- Chỉ sửa file test/test helper trong plan.
- Unit test business rule; integration test API contract.
- Assertion phải kiểm tra status, body, error shape và side effect.
- Có negative path cho invalid title.
- Test data isolated, không phụ thuộc thứ tự chạy.
- Không snapshot rộng, không mock quá sâu.
- Không sửa production code nếu chưa hỏi.
```

### Prompt implement Playwright e2e

```text
Implement Playwright e2e cho create task flow.

Giới hạn:
- Dùng Playwright config hiện có.
- Locator theo role/label/text; không waitForTimeout.
- Unique test data và cleanup nếu có helper.
- Assertion: task mới xuất hiện, form/error state đúng.
- Nếu cần server command, dùng script hiện có và ghi rõ.
- Chỉ sửa file e2e trong plan.
```

### Prompt review

```text
Review diff test hiện tại, không sửa file.

Kiểm tra:
- Assertion có bắt đúng bug không.
- Negative path đủ chưa.
- Setup deterministic chưa.
- Data isolation có sạch không.
- Test có phụ thuộc implementation detail không.
- Playwright locator có accessible và ổn định không.
- Coverage có tăng nhờ test meaningful hay chỉ do gọi hàm.

Trả lời theo Blocker, Should fix, Nice to have, Test gaps.
```

### Prompt test/diagnose

```text
Đây là output test fail. Hãy diagnose, chưa sửa file.

Phân loại lỗi:
- production bug
- test sai contract
- setup thiếu
- data isolation
- flaky/timing
- environment

Sau đó đề xuất patch nhỏ nhất và command verify lại.
```

## 6. Trade-offs

Viết nhiều unit test nhanh và rẻ, nhưng không chứng minh route wiring, validation HTTP boundary, serialization hay database side effect đúng. Với task creation, unit test chỉ nên khóa rule cốt lõi như trim/reject title, status default, permission rule nếu có.

Integration test đắt hơn vì cần app instance, database hoặc repository fake có chủ đích. Đổi lại, nó bắt được contract drift: status code sai, error shape sai, route không đăng ký, validation không chạy, database không ghi. Với backend API, integration test thường có ROI cao hơn unit test mock quá sâu.

E2E test chậm và dễ flaky hơn, nhưng là test duy nhất bảo vệ workflow người dùng thực sự: UI form, API call, loading state, success state, list refresh. Không nên e2e mọi edge case. Hãy chọn một happy path critical và một vài negative path UI quan trọng, còn phần validation chi tiết để unit/integration test.

Snapshot có thể hữu ích cho output nhỏ, ổn định và có chủ đích. Snapshot rộng cho response lớn hoặc toàn DOM thường tạo noise: reviewer không đọc kỹ, AI update snapshot cho pass, bug lọt qua. Với Day 11, mặc định tránh snapshot rộng.

Coverage threshold giúp ngăn vùng code mới không test, nhưng dễ bị game. Team nên dùng coverage như guardrail mềm: xem branch quan trọng chưa được cover, không dùng nó thay thế review test intent.

Cho Claude tự chạy test giúp nhanh hơn, nhưng command test có thể tốn thời gian, chạm test database hoặc tạo artifact. Dùng allowlist hẹp, đọc script trước và không để Claude chạy install/migration khi chưa duyệt.

## 7. Best practices

- Bắt đầu bằng test matrix, không bắt đầu bằng "write tests for this file".
- Review assertion trước khi review style. Test đẹp nhưng assertion yếu vẫn là test tệ.
- Mỗi bug fix quan trọng nên có regression test fail trước hoặc ít nhất test case mô tả rõ bug.
- Unit test không nên mock chính function đang cần kiểm tra. Mock ở boundary, không mock behavior trung tâm.
- Integration test nên kiểm tra contract public: status code, response body, error code/message, database side effect hoặc event side effect.
- Playwright test ưu tiên `getByRole`, `getByLabel`, `getByText` với accessible name cụ thể. Locator càng giống cách user hiểu UI càng bền.
- Không dùng `waitForTimeout` để chữa flaky. Dùng web-first assertion, chờ network/state đúng hoặc cải thiện UI signal.
- Test data phải unique và cleanup được. Với task title, dùng prefix như `e2e-create-task-${testInfo.workerIndex}-${Date.now()}` hoặc helper tương đương.
- Không chạy test trên production credential, production database hoặc shared staging data nếu test có ghi dữ liệu.
- Không đưa secret, token, connection string thật hoặc dữ liệu khách hàng vào prompt, trace, screenshot hay test fixture. Nếu cần debug trace, coi trace như artifact nhạy cảm.
- Không để Claude tự update snapshot hoặc coverage threshold chỉ để pipeline xanh.
- Khi test fail, diagnose nguyên nhân trước. Không nới assertion cho pass nếu behavior chưa đúng.
- Giữ test maintainable: tên test mô tả behavior, helper dùng lại cho setup lặp lại, fixture ngắn và rõ, không assert vào implementation detail dễ đổi.
- Nếu test buộc phải sửa production code, yêu cầu Claude nêu rõ bug, contract bị vi phạm, patch nhỏ nhất và test regression đi kèm trước khi edit.
- Với repo nhiều worker, không rollback toàn repo. Chỉ rollback file test bạn tạo/sửa và đã xác nhận không thuộc worker khác.

## 8. Performance / cost / context

Testing task dễ tốn context vì Claude cần đọc production code, test config, fixtures, helpers, scripts và đôi khi UI. Giảm chi phí bằng cách buộc Claude đọc theo lớp:

1. `package.json` và test config.
2. Test helper/setup hiện có.
3. Code production liên quan tới create task.
4. Test tương tự gần nhất.
5. Playwright config và page/component liên quan.

Không yêu cầu Claude đọc toàn repo để "hiểu test". Với backend, chỉ cần route/service/repository/schema/test helper liên quan. Với e2e, chỉ cần page flow, component labels, Playwright config và seed/cleanup helper.

Runtime cũng cần kiểm soát:

- Unit test nên chạy nhanh, không cần database thật.
- Integration test nên dùng test database/transaction/reset helper, không sleep.
- E2E test nên ít nhưng chất lượng, chạy song song được nếu data isolated.
- Coverage chỉ chạy khi cần review vùng mù hoặc trong CI, không nhất thiết mỗi vòng local.
- Khi dùng Claude, đưa failure output ngắn và đúng phần fail; không paste toàn bộ log nếu log dài hàng nghìn dòng.

Context summary hữu ích sau khi đã chốt test matrix:

```text
Context summary cho session tiếp theo:
- Backend test runner: Vitest/Jest theo package thật.
- Test command: ...
- Files approved to edit: ...
- Create task contract: ...
- Test cases approved: ...
- Không được: thêm dependency, sửa production code nếu chưa hỏi, snapshot rộng, waitForTimeout.
```

## 9. Checklist cuối bài

- [ ] Tôi đã kiểm tra `git status --short` trước khi cho Claude sửa test.
- [ ] Tôi đã yêu cầu Claude đọc test runner/config/script thật trước khi đề xuất test.
- [ ] Tôi biết backend đang dùng Vitest hay Jest và không để Claude thêm runner mới.
- [ ] Tôi có test matrix cho unit, integration và e2e của flow tạo task.
- [ ] Unit test có negative path cho title rỗng/whitespace hoặc business rule tương đương.
- [ ] Integration test assert status code, response body, error shape và side effect quan trọng.
- [ ] Playwright e2e dùng locator ổn định và web-first assertion.
- [ ] Không có snapshot rộng hoặc `waitForTimeout` không có lý do.
- [ ] Test data isolated, deterministic và có cleanup/reset phù hợp.
- [ ] Coverage được xem như tín hiệu phụ, không thay thế review assertion.
- [ ] Tôi đã review `git diff --stat` và `git diff`.
- [ ] Tôi đã diagnose failure trước khi sửa hoặc nới assertion.

## 10. Bài tập

Bài cơ bản: mở `taskflow-ai` bằng `claude --permission-mode plan`, yêu cầu Claude khảo sát test setup và lập test matrix cho flow tạo task. Không cho sửa file. Kết quả cần có: test runner thật, command test thật, file đã đọc, test gaps và test matrix unit/integration/e2e.

Bài nâng cao: cho Claude implement backend tests cho create task bằng test runner hiện có. Phải có ít nhất một unit test cho business rule và một integration test cho API contract. Review assertion và ghi lại ít nhất 3 điểm bạn yêu cầu Claude sửa.

Bài áp dụng e2e: thêm Playwright spec cho flow tạo task từ UI. Test phải dùng locator theo role/label/text, không dùng sleep, có unique test data và assertion rằng task mới hiển thị sau submit. Chạy spec tập trung và xem trace nếu fail.

Bài áp dụng vào project cá nhân: chọn một flow quan trọng trong repo cá nhân. Viết test matrix trước khi nhờ Claude code. Sau khi Claude sinh test, phân loại từng test: meaningful, weak, duplicate, brittle. Xóa hoặc sửa test yếu thay vì giữ để tăng coverage.
