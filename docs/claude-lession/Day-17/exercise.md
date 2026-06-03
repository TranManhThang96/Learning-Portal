# Exercise — Day 17

Nguyên tắc chung: mọi lệnh chạy ở root `taskflow-ai`. Không dùng production data, secret, customer payload hoặc log thật làm fixture. Sau mỗi bài, đọc diff trước khi để Claude sửa tiếp.

## Bài 1 — Cơ bản

Mục tiêu: tạo legacy module giả lập và characterization tests.

Yêu cầu:

- Tạo `src/legacy/legacyTaskSummary.ts`.
- Function chính: `buildLegacyTaskSummary(tasks, nowIso)`.
- Có `TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`, `HIGH`, due date quá hạn.
- Viết `src/legacy/legacyTaskSummary.test.ts`.
- Không refactor implementation trong bài này.

Prompt:

```text
Tạo module legacy giả lập và characterization tests cho taskflow-ai.

Giới hạn:
- Chỉ sửa src/legacy/legacyTaskSummary.ts và src/legacy/legacyTaskSummary.test.ts.
- Test behavior hiện tại qua public API.
- Dùng nowIso cố định, ví dụ "2026-01-15T00:00:00.000Z".
- Không dùng dữ liệu production, secret hoặc customer payload trong fixture.
- Không sửa package/config/call site.
```

Chạy ở root `taskflow-ai`:

```bash
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
```

Lệnh chạy test legacy. Output kỳ vọng: Vitest báo pass cho `legacyTaskSummary.test.ts`, không có test phụ thuộc thời gian hiện tại. Rủi ro: nếu test dùng `new Date()` trực tiếp, kết quả overdue có thể flaky.

Rollback nếu Claude tạo sai:

```bash
git restore src/legacy/legacyTaskSummary.ts src/legacy/legacyTaskSummary.test.ts
```

Nếu hai file là untracked, chạy `git clean -n src/legacy` để preview trước; chỉ xóa thật khi danh sách đúng file bài tập.

## Bài 2 — Thực tế

Mục tiêu: refactor từng lát cắt nhỏ mà không đổi behavior.

Yêu cầu:

1. Extract helper xác định task còn open.
2. Extract helper tính overdue.
3. Extract helper format label.
4. Chạy targeted test sau mỗi lát cắt.
5. Không sửa expectation test để che regression.

Prompt:

```text
Refactor legacyTaskSummary theo một lát cắt nhỏ.

Ràng buộc:
- Extract đúng một helper.
- Không đổi public API.
- Không đổi output.
- Chỉ sửa src/legacy/legacyTaskSummary.ts.
- Dừng sau khi hoàn thành và tóm tắt diff.
```

Sau mỗi lát cắt, chạy:

```bash
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
git diff --name-only
```

Output kỳ vọng: targeted test pass; `git diff --name-only` không phát sinh file ngoài `src/legacy/legacyTaskSummary.ts` và test đã tạo ở Bài 1. Rủi ro: nếu Claude sửa expectation test để làm pass, đó là regression bị che giấu; rollback lát cắt và yêu cầu phân tích expected vs actual.

Trade-off: nhiều lát cắt làm bài lâu hơn, nhưng reviewer nhìn được đúng ý nghĩa từng diff và rollback không kéo theo thay đổi khác.

## Bài 3 — Nâng cao

Mục tiêu: dùng Strangler Fig để tạo implementation mới mà không phá caller cũ.

Yêu cầu:

- Tạo `src/tasks/taskSummary.ts`.
- Giữ `buildLegacyTaskSummary` làm facade hoặc adapter.
- Chuyển một case đơn giản sang implementation mới.
- Không xóa legacy code ngay.
- Characterization tests vẫn pass.

Prompt:

```text
Áp dụng Strangler Fig cho legacy task summary.

Yêu cầu:
- Tạo src/tasks/taskSummary.ts làm implementation mới.
- Giữ public API buildLegacyTaskSummary cho caller cũ.
- Chỉ route một case đơn giản sang implementation mới.
- Không đổi output đã được tests khóa.
- Nếu cần behavior change, tạo TODO và dừng.
```

Chạy:

```bash
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
git diff --check
```

Output kỳ vọng: characterization tests vẫn pass; `git diff --check` không in gì. `git diff --check` bắt whitespace/conflict marker, nhưng không thay thế test logic.

Maintainability cần đạt: `taskSummary.ts` có type rõ hơn, nhưng `buildLegacyTaskSummary` vẫn giữ contract cũ. Performance/cost cần lưu ý: đừng yêu cầu Claude đọc toàn repo nếu chỉ cần call site và test liên quan.

Rollback nếu hướng Strangler Fig sai:

```bash
git restore src/legacy/legacyTaskSummary.ts src/tasks/taskSummary.ts
```

Nếu `src/tasks/taskSummary.ts` chưa tracked, preview bằng `git clean -n src/tasks` trước khi xóa.

## Bài 4 — Review & Reflection

Prompt review:

```text
Review diff Day 17 ở chế độ read-only.

Tập trung:
- Có characterization tests trước refactor chưa
- Có behavior regression không
- Có trộn behavior change với refactor không
- Có file ngoài phạm vi không
- Có security/privacy risk trong fixture không
- Có performance/context cost nào do đọc quá rộng hoặc chạy full suite quá sớm không
- Maintainability có tốt hơn hay chỉ đổi tên/đổi chỗ code
- Có rollback rõ không
```

Chạy:

```bash
git status --short
git diff --name-only
git diff --stat
npm test
```

Output kỳ vọng: `git status --short` và `git diff --name-only` chỉ hiển thị file thực hành legacy của Day 17; `git diff --stat` cho blast radius nhỏ; `npm test` pass nếu project đã có script. Rủi ro: full suite có thể fail vì lỗi nền; cần phân loại trước khi sửa, không để Claude tự ý cleanup file ngoài phạm vi.

Reflection 10-15 dòng, trả lời:

- Characterization test nào quan trọng nhất?
- Claude có đề xuất refactor quá rộng không?
- Bạn đã reject hoặc rollback gì?
- Lát cắt nào dễ review nhất?
- Human reviewer cần chú ý phần nào?
- Context/cost được kiểm soát ra sao?
- Trade-off nào chấp nhận được và trade-off nào cần task riêng?

## Tiêu chí hoàn thành

- [ ] Có `src/legacy/legacyTaskSummary.ts`.
- [ ] Có `src/legacy/legacyTaskSummary.test.ts`.
- [ ] Characterization tests pass trước refactor.
- [ ] Có ít nhất 2 lát cắt refactor nhỏ.
- [ ] Có thử facade/adapter theo Strangler Fig.
- [ ] Không sửa expectation test để che regression.
- [ ] Có review diff read-only bằng Claude Code.
- [ ] Có rollback plan cụ thể.
- [ ] Không có secret/customer data trong fixture.
- [ ] Có ghi nhận trade-off về safety, maintainability, performance/cost/context.

## Gợi ý nếu bí

- Bắt đầu từ input/output đơn giản nhất: empty array.
- Dùng `nowIso = "2026-01-15T00:00:00.000Z"` để tránh flaky test.
- Nếu Claude muốn rewrite toàn bộ, dừng và yêu cầu chỉ implement lát cắt đầu tiên.
- Nếu diff quá lớn, dùng `/rewind` rồi chia task nhỏ hơn.
- Nếu Claude cứ đọc file không liên quan, dùng prompt nêu rõ file scope và yêu cầu plan mode/read-only.
- Nếu fixture có dữ liệu nhạy cảm, thay bằng synthetic data trước khi viết test.

## Đáp án tham khảo hoặc expected result

Expected structure:

```text
src/
  legacy/
    legacyTaskSummary.ts
    legacyTaskSummary.test.ts
  tasks/
    taskSummary.ts
```

Expected behavior:

```text
empty input -> total = 0
DONE task -> done tăng
BLOCKED task -> blocked tăng
open HIGH task -> highPriorityOpen tăng
dueDate trước nowIso và chưa DONE -> overdue tăng
label -> giữ đúng format legacy hiện tại
```
