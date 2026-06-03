# Day 17 — Refactor legacy code an toàn

## 1. Mục tiêu bài học

Sau khoảng 2 giờ, học viên có thể:

- Dùng Claude Code để khám phá legacy module ở chế độ read-only trước khi sửa.
- Viết characterization tests để khóa behavior hiện tại.
- Refactor theo lát cắt nhỏ, có test và rollback sau từng bước.
- Áp dụng Strangler Fig pattern khi cần thay dần implementation cũ bằng implementation mới.
- Nhận diện lúc Claude Code đang refactor quá rộng và biết dừng lại.
- Ghi guardrails vào `CLAUDE.md` hoặc `.claude/rules/` để team dùng lại.

## 2. Bối cảnh thực tế

Trong `taskflow-ai`, giả sử có module `src/legacy/legacyTaskSummary.ts` xử lý thống kê task. Module này có một function dài trộn parsing, business rule và format output. Không ai dám sửa vì không chắc client đang phụ thuộc behavior nào.

Claude Code có thể đọc nhanh và đề xuất rewrite toàn bộ. Với legacy code, đó là hướng rủi ro. Việc đầu tiên không phải làm code đẹp hơn, mà là khóa behavior hiện tại bằng test. Sau đó mới tách từng phần nhỏ.

Không nên dùng Claude Code để refactor legacy khi:

- Chưa có test hoặc chưa biết public API.
- Diff dự kiến chạm nhiều module cùng lúc.
- Có production data, secret hoặc customer payload trong fixture.
- Team chưa review được rollback plan.

## 3. Kiến thức nền

### Refactor theo lát cắt nhỏ

Một lát cắt tốt chỉ đổi một ý tưởng: extract helper, tách formatter, đổi tên biến, hoặc thêm adapter. Test phải pass trước và sau lát cắt.

Thứ tự khuyến nghị:

```text
observe -> characterization tests -> small refactor -> targeted test -> review diff -> repeat
```

Không trộn behavior change với structural refactor. Nếu phát hiện behavior cũ là bug, ghi lại thành task riêng.

### Characterization test

Characterization test mô tả behavior đang tồn tại, kể cả behavior chưa đẹp. Mục tiêu là biết refactor có làm đổi output hay không.

Ví dụ:

```text
Input: task due yesterday, status TODO
Expected hiện tại: overdue = 1
```

Nếu behavior có vẻ kỳ lạ, thêm comment `Characterization: khóa behavior hiện tại, chưa khẳng định đây là behavior đúng`.

### Strangler Fig pattern

Khi legacy module lớn, đừng rewrite một lần. Tạo facade hoặc adapter để caller cũ vẫn gọi API cũ, sau đó chuyển từng case sang implementation mới.

```text
caller -> legacy facade -> legacy implementation
caller -> legacy facade -> new implementation for migrated cases
```

## 4. Step-by-step thực hành

Trong phần này, mọi lệnh đều chạy ở root `taskflow-ai` trừ khi ghi rõ khác. Với Windows, học viên có thể chạy trong Git Bash, WSL hoặc PowerShell; nếu dùng PowerShell thì giữ nguyên ý nghĩa lệnh và kiểm tra output tương đương.

### Bước 1: Kiểm tra repo

Chạy ở root `taskflow-ai`.

```bash
git status --short
```

Lệnh này kiểm tra working tree. Output kỳ vọng là rỗng. Nếu có file modified/untracked, phân loại trước. Rủi ro khi bỏ qua: trộn refactor với thay đổi khác và rollback khó.

### Bước 2: Tạo branch riêng

Chạy ở root `taskflow-ai`.

```bash
git checkout -b refactor/day-17-legacy-task-summary
```

Lệnh tạo branch cho bài học. Output kỳ vọng: `Switched to a new branch ...`. Rủi ro: nếu branch tạo từ `main` cũ, PR có thể chứa diff lạ.

### Bước 3: Thêm guardrail cho Claude Code

Thêm vào `CLAUDE.md` hoặc `.claude/rules/refactor.md`. `CLAUDE.md` và `.claude/rules/` là memory/rules giúp Claude làm đúng ý hơn, còn permission trong `.claude/settings.json` mới là lớp enforce bằng tool:

```md
## Legacy refactor guardrails

- Không refactor diện rộng nếu chưa có characterization tests.
- Luôn bắt đầu bằng observe/read-only trước khi edit.
- Mỗi lần chỉ refactor một lát cắt nhỏ.
- Không đổi public API và behavior trong cùng một diff.
- Sau mỗi lát cắt phải chạy targeted test.
- Không dùng production data, secret hoặc customer data trong fixture.
- Nếu cần behavior change, tạo task riêng thay vì trộn vào refactor.
```

Nếu dùng `.claude/settings.json`, allow các command test/diff cần thiết và deny destructive commands. Ví dụ tham khảo:

```json
{
  "permissions": {
    "allow": [
      "Bash(git status --short)",
      "Bash(git diff *)",
      "Bash(npm exec vitest -- run *)"
    ],
    "deny": [
      "Bash(git reset --hard*)",
      "Bash(git clean -fdx*)",
      "Bash(rm -rf *)",
      "Bash(npm publish*)",
      "Bash(* deploy *)",
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  }
}
```

Output kỳ vọng khi mở `/permissions`: các rule allow/deny xuất hiện đúng scope project. Rủi ro: rule Bash dạng pattern có thể quá rộng hoặc quá hẹp; với command nguy hiểm, ưu tiên deny rõ ràng và vẫn review prompt trước khi approve. Không dùng `bypassPermissions` cho refactor legacy ngoài container/VM cô lập.

### Bước 4: Tạo legacy module giả lập

Prompt:

```text
Tạo module legacy giả lập cho taskflow-ai.

File:
- src/legacy/legacyTaskSummary.ts

Yêu cầu:
- Export function buildLegacyTaskSummary(tasks, nowIso).
- Cố tình trộn parsing, business rule và formatting trong một function.
- Có status TODO, IN_PROGRESS, DONE, BLOCKED.
- Có priority LOW, MEDIUM, HIGH.
- Output gồm total, done, overdue, blocked, highPriorityOpen, label.
- Không tạo test ở bước này.
- Không sửa file ngoài src/legacy/legacyTaskSummary.ts.
```

### Bước 5: Viết characterization tests

Prompt:

```text
Đọc src/legacy/legacyTaskSummary.ts và viết characterization tests cho behavior hiện tại.

File:
- src/legacy/legacyTaskSummary.test.ts

Ràng buộc:
- Test qua public API hiện tại.
- Cover empty input, DONE, BLOCKED, overdue, high priority open.
- Không refactor implementation.
- Nếu behavior kỳ lạ, giữ expectation hiện tại và thêm comment Characterization.
```

Chạy ở root `taskflow-ai`.

```bash
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
```

Lệnh chạy riêng test legacy. Output kỳ vọng: test file pass. Rủi ro: nếu test dùng thời gian hiện tại thay vì `nowIso` cố định, test dễ flaky.

### Bước 6: Refactor lát cắt đầu tiên

Prompt:

```text
Refactor lát cắt nhỏ số 1.

Mục tiêu:
- Extract helper isOpenTask hoặc tương đương.
- Không đổi public API.
- Không đổi output.
- Không sửa test expectation.
- Chỉ sửa src/legacy/legacyTaskSummary.ts.
- Dừng sau khi hoàn thành và tóm tắt diff.
```

Chạy lại targeted test sau khi Claude sửa:

```bash
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
```

Nếu fail, yêu cầu Claude phân tích expected vs actual trước khi sửa tiếp.

### Bước 7: Tách formatter

Prompt:

```text
Refactor lát cắt nhỏ số 2.

Mục tiêu:
- Extract phần tạo label thành formatSummaryLabel.
- Không đổi data shape.
- Không đổi behavior đã được tests khóa.
- Không sửa call site.
```

Chạy lại targeted test:

```bash
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
```

Output kỳ vọng: toàn bộ test legacy vẫn pass, không có snapshot hoặc expectation bị cập nhật. Nếu Claude muốn sửa nhiều file, dừng và hỏi lý do.

### Bước 8: Áp dụng Strangler Fig

Prompt:

```text
Áp dụng Strangler Fig cho legacy task summary.

File mới:
- src/tasks/taskSummary.ts

Yêu cầu:
- Tạo implementation mới rõ type hơn.
- Giữ buildLegacyTaskSummary làm facade cho caller cũ.
- Chỉ chuyển một case đơn giản sang implementation mới.
- Không xóa legacy implementation.
- Không đổi output đã được characterization tests khóa.
```

Chạy ở root `taskflow-ai`:

```bash
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
git diff --name-only
```

Output kỳ vọng: targeted test pass; `git diff --name-only` chỉ có `src/legacy/legacyTaskSummary.ts`, `src/legacy/legacyTaskSummary.test.ts`, `src/tasks/taskSummary.ts` và optional guardrail file như `CLAUDE.md` hoặc `.claude/rules/refactor.md`. Rủi ro: Strangler Fig thêm một lớp indirection tạm thời, nên phải ghi rõ case nào đã migrate và case nào vẫn đi qua legacy implementation.

### Bước 9: Review diff

Prompt:

```text
Review diff hiện tại ở chế độ read-only.

Tập trung:
- Behavior regression so với characterization tests
- Public API có bị đổi không
- Refactor có trộn behavior change không
- Diff có quá rộng không
- Fixture có chứa secret/customer data không
- Test coverage còn thiếu case nào
- Rollback có rõ không
```

### Bước 10: Kiểm tra và rollback

Chạy ở root `taskflow-ai`.

```bash
git diff --name-only
git diff --check
```

`git diff --name-only` cho biết file nào thay đổi. Output kỳ vọng chỉ gồm file trong phạm vi bài thực hành: legacy module/test, implementation mới và guardrail đã chủ động thêm. `git diff --check` bắt whitespace/conflict marker; output kỳ vọng rỗng.

Nếu Claude sửa sai, ưu tiên `/rewind` trong Claude Code. Nếu cần rollback một file:

```bash
git restore src/legacy/legacyTaskSummary.ts
```

Lệnh này bỏ toàn bộ thay đổi chưa commit của file đó. Rủi ro: mất mọi chỉnh sửa local trong file, nên chỉ chạy sau khi đọc `git diff`.

Nếu Claude tạo file mới chưa được Git track, preview trước:

```bash
git clean -n src/legacy src/tasks
```

Output kỳ vọng: Git liệt kê đúng file untracked dự định xóa. Chỉ chạy lệnh xóa thật sau khi chắc chắn không có file của người khác. `/rewind` chỉ phục hồi thay đổi do Claude Code snapshot trong session, không thay thế Git và không rollback được side effect như database, deploy hoặc API call.

## 5. Prompt mẫu nên dùng

Khám phá:

```text
Khám phá module legacy task summary ở chế độ read-only. Tìm public API, call sites, test hiện có và rủi ro refactor. Không chỉnh file.
```

Lập plan:

```text
Lập plan refactor legacy module theo lát cắt nhỏ. Bước đầu phải là characterization tests. Ghi file dự kiến sửa, test command và rollback cho từng bước. Không implement.
```

Implement:

```text
Implement đúng một lát cắt refactor đã duyệt. Không đổi public API, không đổi test expectation, không sửa file ngoài danh sách. Dừng sau lát cắt này.
```

Review:

```text
Review diff hiện tại như code reviewer. Tìm regression, security risk, performance risk, maintainability risk, test gap và file ngoài phạm vi. Không sửa file.
```

Test/debug:

```text
Test legacy refactor đang fail. Phân loại lỗi: test sai characterization, refactor đổi behavior, hay setup lỗi. Đề xuất fix nhỏ nhất, chưa edit.
```

## 6. Trade-offs

- Characterization tests có thể khóa cả behavior xấu, nhưng giúp refactor an toàn.
- Lát cắt nhỏ tạo nhiều vòng lặp hơn, nhưng diff dễ review và rollback.
- Strangler Fig tăng complexity tạm thời, nhưng giảm blast radius khi module lớn.
- Claude Code tăng tốc đọc và extract code, nhưng dễ over-refactor nếu prompt thiếu giới hạn.

## 7. Best practices

- Luôn bắt đầu bằng `git status --short`.
- Dùng `/clear` trước task refactor mới nếu context cũ không liên quan.
- Dùng `/compact <instructions>` khi task dài, giữ behavior đã khóa, file scope và test command.
- Dùng `/rewind` ngay khi Claude đi sai hướng.
- Dùng plan mode cho observe/plan vì mode này chỉ đọc file và chạy read-only shell command; chuyển sang default hoặc accept edits khi plan đã được duyệt.
- Ghi guardrail quan trọng vào `CLAUDE.md` hoặc `.claude/rules/`, nhưng dùng `permissions.deny`/hook cho ranh giới security cần enforce.
- Không đưa production data hoặc secret vào fixture.
- Không trộn refactor, feature và cleanup style trong cùng PR.
- Human vẫn phải đọc diff và quyết định merge.

## 8. Performance / cost / context

Legacy refactor dễ tốn context vì Claude muốn đọc nhiều file. Giảm chi phí bằng cách:

- Cho Claude đọc entrypoint, call sites và test liên quan trước, không đọc toàn repo.
- Dùng prompt có phạm vi file rõ.
- Chạy targeted tests sau từng lát cắt.
- Chỉ chạy full suite trước PR hoặc khi blast radius lớn.
- Không paste log dài; đưa failure chính và command đã chạy.

## 9. Checklist cuối bài

- [ ] Có branch riêng cho Day 17.
- [ ] Có module legacy giả lập.
- [ ] Có characterization tests pass trước refactor.
- [ ] Đã refactor ít nhất 2 lát cắt nhỏ.
- [ ] Đã chạy targeted tests sau mỗi lát cắt.
- [ ] Có facade/adapter theo Strangler Fig.
- [ ] Có review diff read-only bằng Claude Code.
- [ ] Có rollback plan.
- [ ] Không có secret/customer data trong fixture.
- [ ] Không có refactor diện rộng chưa được test khóa.

## 10. Bài tập

- Bài cơ bản: tạo legacy module và characterization tests.
- Bài thực tế: extract 2 helper nhỏ, chạy test sau mỗi lát cắt.
- Bài nâng cao: thêm facade/adapter theo Strangler Fig cho một case.
- Bài áp dụng cá nhân: chọn một legacy function trong project cá nhân và viết plan refactor có test, rollback, file scope.
