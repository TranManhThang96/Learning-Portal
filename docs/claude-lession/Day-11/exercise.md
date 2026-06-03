# Exercise — Day 11

## Bài 1 — Cơ bản

Mục tiêu: dùng Claude Code ở `plan` mode để khảo sát test setup của `taskflow-ai` và lập test matrix cho flow tạo task, chưa sửa file.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.

2. Kiểm tra working tree:

```bash
git status --short
```

Lệnh này chạy ở root repo để xem file đang thay đổi. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có thay đổi của worker khác, không sửa hoặc rollback các file đó.

3. Tìm package Node:

```bash
find . -maxdepth 3 -name package.json
```

Lệnh này chạy ở root repo để tìm package backend/frontend/root. Output kỳ vọng là một hoặc nhiều path `package.json`. Rủi ro thấp vì read-only; trên Windows PowerShell có thể dùng `Get-ChildItem -Recurse -Filter package.json -Depth 3`.

4. Đọc scripts trong package nghi là backend:

```bash
npm pkg get scripts
```

Lệnh này chạy trong folder có `package.json` backend hoặc root package. Output kỳ vọng là JSON script có `test` hoặc script liên quan. Rủi ro: chạy nhầm package sẽ dẫn tới test command sai.

5. Mở Claude Code ở plan mode:

```bash
claude --permission-mode plan
```

Lệnh này chạy ở root `taskflow-ai` để mở session khảo sát/lập plan. Output kỳ vọng là Claude sẵn sàng nhận prompt. Rủi ro: plan vẫn có thể sai nếu Claude đọc thiếu file.

6. Gửi prompt:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát test setup cho flow tạo task.

Ràng buộc:
- Chưa sửa file.
- Tìm test runner backend đang dùng: Vitest hay Jest.
- Tìm test commands thật, test config, test helpers, database test setup.
- Tìm Playwright config hoặc e2e setup nếu có.
- Đọc route/service/schema liên quan tới create task và UI flow tạo task nếu có.
- Nêu rõ file đã đọc và bằng chứng từ code.
- Không đề xuất đổi test runner hoặc thêm dependency.
- Output gồm test gaps, rủi ro flaky, và test matrix unit/integration/e2e.
```

Kết quả cần nộp:

- Danh sách file Claude đã đọc.
- Test runner backend đang dùng và command test thật.
- Playwright đã có hay chưa.
- Test matrix cho create task flow.
- 3 rủi ro nếu cho Claude viết test ngay mà chưa review matrix.

## Bài 2 — Thực tế

Mục tiêu: dùng Claude Code implement backend tests cho flow tạo task bằng Vitest hoặc Jest hiện có.

Yêu cầu:

1. Từ test matrix ở Bài 1, chọn tối thiểu 3 test backend:

- Unit: reject title rỗng hoặc chỉ có khoảng trắng.
- Unit: normalize/default field khi tạo task.
- Integration: `POST /tasks` success hoặc validation error theo contract hiện có.

2. Yêu cầu Claude lập plan file-by-file:

```text
Lập plan implement backend tests cho create task flow.

Ràng buộc:
- Dùng test runner hiện có trong backend: Vitest hoặc Jest.
- Không thêm dependency.
- Chỉ sửa/tạo file test và test helper nếu plan nêu rõ.
- Không sửa production code trong bước này.
- Mỗi test case phải ghi setup, assertion chính, negative path nếu có.
- Test data phải isolated và deterministic.
- Chờ tôi approve trước khi edit.
```

3. Sau khi approve, mở session implement:

```bash
claude --permission-mode default --allowedTools "Read" "Edit" "Bash(git status *)" "Bash(git diff *)" "Bash(npm run test*)" "Bash(npm test *)"
```

Lệnh này chạy ở root `taskflow-ai` để Claude được đọc, edit và chạy một số command test/Git read-only. Mỗi permission rule được truyền riêng để tránh nhập nhằng với cú pháp `--allowedTools`; nếu CLI local khác, kiểm tra `claude --help` trước. Output kỳ vọng là session sẵn sàng. Rủi ro: script test có thể chạm test database hoặc chạy lâu; không mở rộng allowlist sang install/migration nếu chưa duyệt.

4. Gửi prompt implement:

```text
Implement backend tests theo plan đã approve.

Ràng buộc bắt buộc:
- Không thêm test runner mới.
- Không sửa production code nếu test chưa chứng minh bug; nếu cần sửa, dừng và hỏi.
- Assertion phải meaningful: status code, response body, error shape, side effect.
- Có negative path cho invalid title.
- Test data unique hoặc cleanup bằng helper hiện có.
- Không snapshot rộng.
- Không phụ thuộc thứ tự chạy test.
- Sau khi edit, tóm tắt diff và command verify.
```

5. Review phạm vi patch:

```bash
git diff --stat
```

Lệnh này chạy ở root repo để xem file/dòng thay đổi. Output kỳ vọng chỉ gồm file test/test helper trong plan. Rủi ro: nếu production code hoặc lockfile bị sửa ngoài plan, dừng lại và review.

6. Chạy test backend theo runner thật.

Nếu backend dùng Vitest:

```bash
npm run test -- --run
```

Lệnh này chạy trong folder backend có `package.json` để chạy Vitest một lần. Output kỳ vọng là test pass và exit code `0`. Rủi ro: nếu script không phải Vitest hoặc không nhận `--run`, command fail; đọc script trước.

Nếu backend dùng Jest:

```bash
npm test -- --runInBand
```

Lệnh này chạy trong folder backend có `package.json` để chạy Jest tuần tự. Output kỳ vọng là test pass và exit code `0`. Rủi ro: chạy tuần tự chậm hơn và có thể không phát hiện vấn đề parallel isolation.

7. Gửi prompt review:

```text
Review diff backend tests hiện tại, không sửa file.

Tập trung:
- Assertion có bắt đúng behavior quan trọng không.
- Negative path đủ chưa.
- Setup có deterministic không.
- Test data có isolated không.
- Có mock quá sâu hoặc test implementation detail không.
- Có snapshot rộng không.

Kết luận theo Blocker, Should fix, Nice to have, Test gaps.
```

Kết quả cần nộp:

- File test đã tạo/sửa.
- Test command đã chạy và output chính.
- Ít nhất 3 nhận xét review assertion.
- Quyết định giữ, sửa, hoặc bỏ test nào.

## Bài 3 — Nâng cao

Mục tiêu: thêm Playwright e2e cho flow tạo task trên UI của `taskflow-ai`.

Yêu cầu:

1. Kiểm tra Playwright setup:

```bash
npm pkg get devDependencies
```

Lệnh này chạy trong root package hoặc package frontend/e2e theo repo. Nó đọc dependency để xem có `@playwright/test` không. Output kỳ vọng có package này nếu e2e đã setup. Rủi ro: chạy nhầm package sẽ đọc sai dependency.

2. Nếu có Playwright config, liệt kê test:

```bash
npx playwright test --list
```

Lệnh này chạy ở package có `playwright.config.*`. Output kỳ vọng là danh sách test hiện có. Rủi ro: một số config có global setup tốn thời gian.

3. Nếu chưa có Playwright, không tự cài ngay. Yêu cầu Claude đề xuất setup:

```text
Repo chưa thấy Playwright setup rõ ràng. Hãy đề xuất plan thêm Playwright e2e cho taskflow-ai.

Ràng buộc:
- Chưa chạy install.
- Nêu package nào sẽ bị sửa, command nào cần chạy, file config/spec nào sẽ tạo.
- Nêu rủi ro với lockfile, CI, app server, test database.
- Chờ tôi approve.
```

Nếu team approve setup mới, command phổ biến là:

```bash
npm init playwright@latest
```

Lệnh này chạy ở root package hoặc frontend/e2e package theo plan. Output kỳ vọng là wizard tạo Playwright config và example. Rủi ro: sửa `package.json`, lockfile và tạo file mẫu; chỉ chạy sau khi approve, đặc biệt trong repo có nhiều worker.

4. Yêu cầu Claude lập plan e2e:

```text
Lập plan Playwright e2e cho create task flow.

Ràng buộc:
- Dùng Playwright config hiện có nếu có.
- Chỉ tạo/sửa spec e2e trong plan.
- Test data phải unique.
- Nếu có API/helper cleanup, dùng helper đó; nếu không, ghi rõ cleanup thủ công hoặc reset test DB.
- Locator phải dùng getByRole/getByLabel/getByText khi có accessible name.
- Không dùng waitForTimeout.
- Assertion chính: task mới xuất hiện trong list sau submit.
- Chờ tôi approve trước khi edit.
```

5. Cho Claude implement:

```text
Implement Playwright create task e2e theo plan đã approve.

Ràng buộc:
- Không snapshot toàn page.
- Không selector CSS brittle nếu có role/label/text.
- Không dùng waitForTimeout.
- Không sửa UI chỉ để test pass nếu chưa hỏi.
- Nếu phát hiện thiếu accessible label, dừng và đề xuất patch nhỏ thay vì tự đổi rộng.
- Sau khi edit, tóm tắt file changed và command verify.
```

6. Chạy spec tập trung:

```bash
npx playwright test e2e/create-task.spec.ts --project=chromium
```

Lệnh này chạy ở package có Playwright config. Output kỳ vọng là spec pass, hoặc failure có trace/screenshot nếu config bật. Rủi ro: cần frontend/backend server, test database và port đúng.

7. Nếu fail, debug:

```bash
npx playwright test e2e/create-task.spec.ts --project=chromium --headed --debug
```

Lệnh này chạy ở package Playwright để mở browser và inspector. Output kỳ vọng là bạn thấy bước fail. Rủi ro: không dùng trong CI, có thể treo session nếu không tương tác.

8. Nếu có trace:

```bash
npx playwright show-trace trace.zip
```

Lệnh này chạy ở nơi có `trace.zip`. Output kỳ vọng là Trace Viewer. Rủi ro: trace có thể chứa dữ liệu nhập trong test; không chia sẻ public nếu có thông tin nhạy cảm.

Kết quả cần nộp:

- Spec e2e đã tạo.
- Locator chính đã dùng và lý do ổn định.
- Cách tạo/cleanup test data.
- Output test hoặc phân tích failure.

## Bài 4 — Review & Reflection

Mục tiêu: đánh giá chất lượng test do Claude Code tạo và biến kết quả thành rule làm việc cho team.

Yêu cầu:

1. Chạy coverage như tín hiệu phụ.

Nếu backend dùng Vitest:

```bash
npm run test -- --run --coverage
```

Lệnh này chạy trong backend package để tạo coverage report nếu config hỗ trợ. Output kỳ vọng là bảng coverage. Rủi ro: coverage có thể cần provider/config; không thêm dependency chỉ để làm đẹp số nếu team chưa duyệt.

Nếu backend dùng Jest:

```bash
npm test -- --coverage
```

Lệnh này chạy trong backend package để tạo coverage report. Output kỳ vọng là bảng coverage. Rủi ro: coverage chậm hơn và có thể fail vì threshold, không nhất thiết do test mới sai.

2. Gửi prompt review chất lượng:

```text
Review toàn bộ test mới của Day 11, không sửa file.

Với từng test, hãy trả lời:
- Behavior nào được bảo vệ.
- Bug nào test này sẽ bắt được.
- Assertion chính có meaningful không.
- Có negative path không.
- Setup có deterministic và isolated không.
- Test có duplicate tầng khác hoặc brittle không.
- Nếu coverage tăng, tăng đó có giá trị hay chỉ là chạy qua code.

Kết luận: test nên giữ, test nên sửa, test nên xóa.
```

3. Trả lời reflection:

- Test nào có giá trị nhất trong backend? Vì sao?
- Test nào dễ flaky nhất? Bạn đã giảm rủi ro như thế nào?
- Claude Code đề xuất assertion yếu nào? Bạn sửa ra sao?
- Coverage sau khi thêm test nói gì và không nói gì?
- Bạn sẽ thêm rule gì vào `CLAUDE.md` cho các task test sau?

4. Viết 8-10 rule đề xuất cho team. Prompt gợi ý:

```text
Dựa trên Day 11, hãy đề xuất rule testing cho CLAUDE.md của taskflow-ai.

Yêu cầu:
- Rule phải cụ thể cho Vitest/Jest backend và Playwright e2e.
- Có rule về meaningful assertion, negative path, deterministic setup, data isolation, không snapshot rộng, không waitForTimeout.
- Có rule về coverage là tín hiệu phụ.
- Có rule về việc Claude không được sửa production code khi test fail nếu chưa hỏi.
```

Kết quả cần nộp:

- Coverage summary và nhận xét ngắn.
- Danh sách test giữ/sửa/xóa.
- Reflection 10-15 dòng.
- Rule testing đề xuất cho `CLAUDE.md`.

## Tiêu chí hoàn thành

- Đã dùng `claude --permission-mode plan` để khảo sát test setup trước khi sửa.
- Xác định đúng backend dùng Vitest hay Jest, không thêm runner mới.
- Có test matrix rõ cho unit, integration và e2e của flow tạo task.
- Backend test có meaningful assertion, không chỉ kiểm tra không crash.
- Có negative path cho input invalid, tối thiểu title rỗng/whitespace hoặc case tương đương theo contract.
- Integration test assert status code, response body, error shape và side effect quan trọng.
- Playwright e2e dùng locator ổn định theo role/label/text khi có thể.
- Không dùng snapshot rộng hoặc `waitForTimeout` để che flaky.
- Test data deterministic và isolated; có cleanup/reset hoặc unique data strategy.
- Đã chạy test command phù hợp và ghi lại output chính.
- Đã review diff và phân loại test gaps.
- Coverage được dùng để tìm vùng mù, không dùng làm thước đo chất lượng duy nhất.
- Không đưa secret, token, production data hoặc trace/screenshot chứa dữ liệu nhạy cảm vào prompt hay artifact public.
- Test mới dễ bảo trì: tên test mô tả behavior, helper/fixture rõ ràng, không khóa implementation detail không thuộc contract.

## Gợi ý nếu bí

Nếu Claude không tìm được test runner:

```text
Hãy đọc package.json liên quan, lockfile, vitest.config.*, jest.config.*, và các file *.test.* hoặc *.spec.* gần nhất.
Chưa sửa file. Kết luận repo đang dùng runner nào và command nào chạy test.
```

Nếu Claude sinh assertion yếu:

```text
Assertion này quá yếu. Hãy viết lại test để assertion fail khi contract sai.
Với API, kiểm tra status code, response body, error shape và side effect.
Với UI, kiểm tra element người dùng nhìn thấy và trạng thái form/error cụ thể.
```

Nếu integration test cần database nhưng setup chưa rõ:

```text
Chưa rõ database test setup. Hãy đọc test helper/setup hiện có và đề xuất 2 phương án isolation:
1. transaction/reset helper hiện có
2. repository fake hoặc in-memory store nếu project đã dùng pattern đó
Chưa sửa file.
```

Nếu Playwright test flaky:

```text
Test e2e đang flaky. Hãy phân tích nguyên nhân, chưa sửa file.
Kiểm tra locator, wait strategy, data isolation, server readiness, network race.
Không đề xuất waitForTimeout trừ khi có lý do bất khả kháng.
```

Nếu coverage cao nhưng bạn không tin test:

```text
Coverage tăng nhưng tôi muốn đánh giá test quality.
Hãy map từng test tới behavior và bug mà test bắt được.
Test nào không có assertion meaningful thì đề xuất sửa hoặc xóa.
Không sửa file.
```

## Đáp án tham khảo hoặc expected result

Kết quả tốt cho Bài 1:

- Claude đọc đúng `package.json`, test config, test helper, route/service task và Playwright config nếu có.
- Test runner backend được xác định rõ: Vitest hoặc Jest.
- Test matrix có đủ unit, integration và e2e, không trộn mục tiêu.
- Có rủi ro flaky và data isolation được nêu trước khi implement.

Kết quả tốt cho Bài 2:

- Có unit test reject title rỗng/whitespace.
- Có unit test cho normalize/default field hoặc business rule tương đương.
- Có integration test `POST /tasks` success hoặc invalid input.
- Assertion kiểm tra status/body/error/side effect cụ thể.
- Test data unique hoặc cleanup rõ.
- `git diff --stat` chỉ gồm file test/helper trong plan.

Ví dụ assertion backend chấp nhận được:

```ts
// File ví dụ: backend/src/tasks/task.service.test.ts
// Mục đích: khóa business rule title sau trim không được rỗng.
// Cách test: chạy unit test backend bằng Vitest/Jest script hiện có.
// Edge case: title chỉ gồm khoảng trắng phải bị reject.
await expect(service.createTask({ title: "   " })).rejects.toMatchObject({
  code: "TASK_TITLE_REQUIRED",
});
```

Đoạn code trên chỉ là ví dụ minh họa. Trong repo thật, error shape phải bám convention hiện có của `taskflow-ai`.

Kết quả tốt cho Bài 3:

- Playwright spec tạo task bằng UI thật hoặc flow dev/test tương đương.
- Locator dùng `getByRole`, `getByLabel` hoặc `getByText` với name cụ thể.
- Không có `waitForTimeout`.
- Title task unique theo test run.
- Assertion chính kiểm tra task mới xuất hiện trong list.

Ví dụ Playwright assertion chấp nhận được:

```ts
// File ví dụ: e2e/create-task.spec.ts
// Mục đích: khóa flow người dùng tạo task từ UI.
// Cách test: chạy npx playwright test e2e/create-task.spec.ts --project=chromium.
// Edge case: locator dựa trên role/label để tránh phụ thuộc layout CSS.
await page.getByRole("textbox", { name: /task title/i }).fill(title);
await page.getByRole("button", { name: /create task/i }).click();
await expect(page.getByRole("listitem", { name: new RegExp(title) })).toBeVisible();
```

Kết quả tốt cho Bài 4:

- Coverage summary được ghi lại nhưng không dùng để tuyên bố test tốt.
- Reflection chỉ ra ít nhất một test meaningful và một test cần sửa/xóa.
- Rule đề xuất cho `CLAUDE.md` có thể dùng ngay, ví dụ:

```text
- Khi viết test backend, dùng test runner hiện có; không thêm Vitest/Jest mới nếu repo đã chọn runner.
- Mỗi API test phải assert status code, response body, error shape và side effect quan trọng.
- Mỗi feature test phải có ít nhất một negative path có giá trị.
- Test data phải deterministic và isolated; không phụ thuộc seed data cũ hoặc thứ tự test.
- Không dùng snapshot rộng cho response/page.
- Playwright test ưu tiên getByRole/getByLabel/getByText; không dùng waitForTimeout để che flaky.
- Coverage là tín hiệu phụ để tìm vùng mù, không thay thế review assertion.
- Khi test fail, Claude phải diagnose trước; không sửa production code nếu chưa được approve.
```
