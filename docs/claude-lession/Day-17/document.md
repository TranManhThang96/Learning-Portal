# Document — Day 17

## Tóm tắt kiến thức

Workflow refactor legacy an toàn:

```text
observe -> public API -> characterization tests -> small slice -> targeted test -> review diff -> repeat
```

Nguyên tắc chính:

- Test behavior hiện tại trước khi sửa cấu trúc.
- Không rewrite toàn bộ bằng AI khi chưa có characterization tests.
- Không trộn behavior change với refactor.
- Dùng Strangler Fig khi module lớn hoặc có nhiều call site.
- Dùng `CLAUDE.md` hoặc `.claude/rules/` để ghi memory/rules, dùng `.claude/settings.json` hoặc hook để enforce permission.
- Dùng `/clear`, `/compact <instructions>` và `/rewind` để quản lý context/checkpoint, nhưng Git vẫn là nguồn rollback chính.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Legacy refactor
├── Guardrails
│   ├── CLAUDE.md hoặc .claude/rules/
│   ├── permissions.deny/hooks
│   └── no broad refactor without tests
├── Characterization tests
│   ├── public API
│   ├── edge cases
│   └── no production data
├── Small slices
│   ├── extract helper
│   ├── split formatter
│   └── keep behavior stable
├── Strangler Fig
│   ├── facade
│   ├── legacy implementation
│   └── new implementation
└── Verification
    ├── targeted tests
    ├── git diff review
    └── human approval
```

## Bảng so sánh

| Cách làm | Ưu điểm | Rủi ro | Khi dùng |
| --- | --- | --- | --- |
| Big rewrite | Code mới sạch nhanh trên giấy | Regression lớn, khó review | Chỉ khi module cô lập và test rất mạnh |
| Small-slice refactor | Dễ review, dễ rollback | Nhiều vòng lặp hơn | Mặc định cho legacy production |
| Characterization test trước | Khóa behavior thật | Có thể khóa cả bug cũ | Khi chưa hiểu đủ rule |
| Test sau refactor | Ít việc ban đầu | Không biết lỗi do đâu | Tránh dùng với legacy |
| Strangler Fig | Migrate dần, giảm blast radius | Tăng complexity tạm thời | Module lớn, nhiều call site |

| Claude Code hỗ trợ | Nên dùng | Không nên dùng |
| --- | --- | --- |
| Khám phá code | Tìm call site, public API | Tin hoàn toàn vào kết luận mà không đọc diff |
| Viết tests | Sinh characterization cases | Để Claude sửa behavior theo ý nó |
| Refactor | Extract helper nhỏ | Rewrite nhiều file một lần |
| Review | Tìm bug/test gap | Thay human reviewer |

| Guardrail | Vai trò | Lưu ý |
| --- | --- | --- |
| `CLAUDE.md` | Memory chung cho project | Nên ngắn, chứa command/test rule thật sự cần |
| `.claude/rules/*.md` | Rule theo chủ đề hoặc theo path | Phù hợp cho quy tắc refactor/testing/security |
| `.claude/settings.json` | Enforce permissions, hooks, environment | `deny` nên dùng cho secret/destructive command |
| Plan mode | Explore/plan read-only | Không dùng để implement |
| `/rewind` | Quay lại checkpoint trong session | Không thay thế Git; không rollback side effect bên ngoài |

## Lỗi thường gặp

1. Refactor trước khi có characterization tests.
2. Để Claude đổi implementation, API và tests cùng lúc.
3. Diff quá lớn khiến reviewer không biết regression đến từ đâu.
4. Dùng fixture từ production, gây rủi ro secret/privacy.
5. Không cố định thời gian trong test due date.
6. Dùng `/compact` không có instruction nên mất decision quan trọng.
7. Không rollback sớm khi Claude đi sai hướng.
8. Tin rằng prompt guardrail đủ bảo vệ secret; thực tế cần `permissions.deny`, hook hoặc sandbox.

## Cách debug

Khi test fail sau refactor:

```text
1. Đọc test fail.
2. So sánh expected vs actual.
3. Kiểm tra condition, null handling, timezone, sort order.
4. Nếu test characterization sai, sửa test và ghi lý do.
5. Nếu refactor đổi behavior, rollback lát cắt đó.
```

Chạy ở root `taskflow-ai`:

```bash
git diff --name-only
git diff --check
npm exec vitest -- run src/legacy/legacyTaskSummary.test.ts
```

Các lệnh trên lần lượt kiểm tra file đổi, lỗi diff cơ bản và targeted tests. Output kỳ vọng: danh sách file chỉ gồm legacy module/test, implementation mới và guardrail chủ động thêm; `git diff --check` không in gì; Vitest báo pass cho test file legacy. Rủi ro: `git diff` có thể hiển thị nội dung nhạy cảm nếu fixture chứa secret.

Rollback một file:

```bash
git restore src/legacy/legacyTaskSummary.ts
```

Chỉ dùng sau khi đã đọc diff vì lệnh này mất toàn bộ thay đổi local của file.

Nếu cần kiểm tra file mới chưa tracked:

```bash
git clean -n src/legacy src/tasks
```

Output kỳ vọng: chỉ liệt kê file bài tập Day 17 dự định xóa. Đây là preview, chưa xóa gì; không chạy biến thể xóa thật nếu chưa chắc chắn file không thuộc người khác.

## Link tài liệu nên đọc

- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code Memory: https://code.claude.com/docs/en/memory
- Claude Code .claude directory: https://code.claude.com/docs/en/claude-directory
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Settings: https://code.claude.com/docs/en/settings
- Claude Code Slash Commands: https://code.claude.com/docs/en/slash-commands
- Claude Code Hooks: https://code.claude.com/docs/en/hooks
- Martin Fowler — Characterization Test: https://martinfowler.com/bliki/CharacterizationTest.html
- Martin Fowler — Strangler Fig Application: https://martinfowler.com/bliki/StranglerFigApplication.html
