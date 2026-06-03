# Document — Day 07

## Tóm tắt kiến thức

Khám phá codebase lớn bằng Claude Code không phải là hỏi "repo này làm gì?". Mục tiêu là tạo hiểu biết có thể kiểm chứng: entrypoint ở đâu, bounded context nào tồn tại, dependency giữa module ra sao, hot path nào có rủi ro cao, và trước khi sửa feature cần đọc file nào.

Nguyên tắc Day 07:

- Dùng `plan` mode hoặc quyền read-only ở phase exploration.
- Yêu cầu Claude ghi rõ file/path đã đọc cho từng claim.
- Tách `Fact from code`, `Inference`, và `Unknown / needs verification`.
- Tạo `ARCHITECTURE.md` như artifact onboarding và context cache cho session sau.
- Không để Claude đọc secret, production data, generated output, lockfile dài, hoặc thư mục build nếu không cần.
- Trước khi sửa feature, yêu cầu Claude tạo reading plan theo module và rủi ro.

`ARCHITECTURE.md` tốt nên có:

- System overview.
- Entrypoints.
- Bounded contexts.
- Dependency map.
- Hot paths.
- Data and external dependencies.
- Testing and verification map.
- Read-before-editing guide.
- Unknowns and stale-risk notes.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Nhận task trên codebase lớn
  |
  v
Kiểm tra Git state
  |
  v
Mở Claude Code bằng plan/read-only mode
  |
  v
Tìm file định hướng
  |-- README.md / CLAUDE.md
  |-- package.json / workspace config
  |-- docker-compose.yml
  |-- backend/frontend entrypoint
  |
  v
Map architecture cấp cao
  |
  +-- Entrypoint
  +-- Bounded context
  +-- Dependency map
  +-- Hot path
  +-- Test/verification map
  |
  v
Phân loại claim
  |
  +-- Fact from code
  +-- Inference
  +-- Unknown
  |
  v
Tạo hoặc cập nhật ARCHITECTURE.md
  |
  v
Review diff và evidence
  |
  v
Tạo reading plan trước khi sửa feature
```

Luồng đọc cho feature `task comments` trong `taskflow-ai`:

```text
Feature request
  |
  v
Đọc architecture map
  |
  v
Đọc bounded context tasks
  |
  v
Đọc auth/current user contract
  |
  v
Đọc data model + migration pattern
  |
  v
Đọc API route/service/repository
  |
  v
Đọc frontend API client + task detail/list UI
  |
  v
Đọc test pattern unit/integration/e2e
  |
  v
Mới lập plan implement
```

## Bảng so sánh

| Output của Claude | Dấu hiệu tốt | Dấu hiệu rủi ro |
| --- | --- | --- |
| Architecture map | Có path file, entrypoint thật, boundary rõ | Mô tả generic, không có evidence |
| Dependency map | Nêu loại dependency: import/runtime/data/cache/config | Nói "module A phụ thuộc B" nhưng không chỉ ra bằng chứng |
| Hot path | Gắn với luồng user/API cụ thể và test liên quan | Chỉ liệt kê file "quan trọng" theo tên |
| Reading plan | Có thứ tự đọc, lý do, rủi ro nếu bỏ qua | Nhảy thẳng sang implement |
| `ARCHITECTURE.md` | Có Fact/Inference/Unknown và last verified source | Trộn suy đoán với fact |
| Session summary | Giữ decisions, file scope, unknowns | Chỉ tóm tắt chung chung, mất chi tiết cần verify |

| Mục cần tìm | Cách hỏi Claude | Output kỳ vọng |
| --- | --- | --- |
| Backend entrypoint | "Tìm file bootstrap server và route registration" | `main.ts/server.ts/app.ts` hoặc tương đương, kèm evidence |
| Frontend entrypoint | "Tìm nơi React app mount và routing setup" | `main.tsx/App.tsx/router` hoặc tương đương |
| Bounded context | "Nhóm module theo nghiệp vụ, không theo folder thuần túy" | tasks, users/auth, comments, notifications, shared |
| Hot path | "Trace luồng tạo task từ API/UI tới database" | Route/controller -> service -> repository/table -> test |
| Risk area | "Module nào sửa dễ gây regression?" | Auth, validation, transaction, cache, migration, shared types |

| Command | Chạy ở đâu | Dùng để làm gì | Rủi ro |
| --- | --- | --- | --- |
| `git status --short` | Root `taskflow-ai` | Kiểm tra working tree trước exploration | Bỏ sót diff có sẵn nếu không đọc |
| `rg --files -g "package.json" -g "CLAUDE.md" -g "README.md"` | Root `taskflow-ai` | Tìm file định hướng | Không thấy file nếu repo dùng tên khác |
| `claude --permission-mode plan` | Root `taskflow-ai` | Mở session exploration an toàn | Plan vẫn có thể sai nếu thiếu evidence |
| `git diff --stat -- ARCHITECTURE.md` | Root `taskflow-ai` | Xem phạm vi artifact | Không thấy nội dung claim |
| `git diff -- ARCHITECTURE.md` | Root `taskflow-ai` | Review chi tiết tài liệu | Diff dài cần đọc kỹ |
| `git restore -- ARCHITECTURE.md` | Root `taskflow-ai` | Rollback file tracked | Mất thay đổi chưa commit trong file |
| `git clean -f -- ARCHITECTURE.md` | Root `taskflow-ai` | Xóa file mới untracked đã xác nhận | Destructive nếu path sai |

## Lỗi thường gặp

1. Hỏi Claude "giải thích toàn bộ repo"  
   Output thường dài, chung chung, tốn token, và không hướng tới task cụ thể.

2. Tin architecture claim không có evidence  
   Claude có thể suy luận theo pattern phổ biến của Node.js/React, nhưng repo thật có thể dùng convention khác.

3. Đọc quá nhiều file generated hoặc lockfile  
   Context bị nhiễu bởi `dist`, coverage, snapshot, lockfile lớn, hoặc code generated.

4. Bỏ qua auth và authorization path  
   Feature tasks thường phụ thuộc current user, team membership, permission, audit log. Nếu chỉ đọc service tasks, patch có thể lộ data.

5. Nhầm bounded context với folder  
   Một folder `shared` có thể chứa validation, types, error, config. Đó không phải bounded context nghiệp vụ, nhưng có thể là dependency quan trọng.

6. Tạo `ARCHITECTURE.md` quá tự tin  
   Tài liệu không có `Unknown` làm người sau tưởng mọi thứ đã được kiểm chứng.

7. Compact session quá sớm  
   Nếu chưa chốt fact/inference, `/compact` có thể giữ lại kết luận sai và bỏ mất bằng chứng cần kiểm tra.

8. Cho quyền edit trong phase exploration  
   Claude có thể "dọn dẹp" hoặc sửa docs/source khi bạn chỉ muốn đọc. Với repo lớn, đây là blast radius không cần thiết.

## Cách debug

Khi Claude đưa architecture map chung chung:

```text
Output này thiếu evidence. Hãy viết lại thành bảng Claim / Evidence file / Confidence / Next file to read.
Không thêm claim mới nếu chưa đọc file chứng minh.
```

Khi Claude đề xuất sửa feature trước khi đọc đủ module:

```text
Chưa implement. Hãy tạo reading plan trước.
Với mỗi file/module cần đọc, ghi vì sao, rủi ro nếu bỏ qua, và claim nào cần kiểm chứng.
```

Khi `ARCHITECTURE.md` có claim nghi ngờ:

1. Chạy:

```bash
git diff -- ARCHITECTURE.md
```

2. Tìm claim không có path file.
3. Prompt lại:

```text
Trong ARCHITECTURE.md, hãy tìm mọi câu không có evidence file/path.
Phân loại:
- Có thể bổ sung evidence bằng file đã đọc.
- Cần đọc thêm file.
- Nên xóa vì suy đoán.
Không sửa file, chỉ báo cáo.
```

Khi context bắt đầu dài:

- Dùng `/context` để xem tình trạng context nếu phiên bản Claude Code của bạn hỗ trợ.
- Trước khi `/compact`, yêu cầu Claude tạo summary có cấu trúc:

```text
Chuẩn bị compact session. Hãy tạo summary giữ lại:
- Entrypoints đã xác minh.
- Bounded contexts và evidence.
- Dependency map quan trọng.
- Hot paths.
- Unknowns.
- Decisions đã approve.
- File tuyệt đối không sửa.
```

Khi muốn rollback artifact:

```bash
git status --short -- ARCHITECTURE.md
```

Nếu file tracked:

```bash
git restore -- ARCHITECTURE.md
```

Nếu file untracked và bạn chắc chắn muốn xóa:

```bash
git clean -f -- ARCHITECTURE.md
```

Không dùng `git reset --hard` hoặc `git clean -fd` để rollback một file tài liệu nhỏ.

## Link tài liệu nên đọc

- Claude Code Quickstart: https://code.claude.com/docs/en/quickstart
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Memory: https://code.claude.com/docs/en/memory
- Claude Code Slash Commands: https://code.claude.com/docs/en/slash-commands
- Claude Code Subagents: https://code.claude.com/docs/en/sub-agents
- Git diff documentation: https://git-scm.com/docs/git-diff
- Git clean documentation: https://git-scm.com/docs/git-clean
