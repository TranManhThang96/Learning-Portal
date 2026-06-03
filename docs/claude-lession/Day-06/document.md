# Document — Day 06

## Tóm tắt kiến thức

Prompt engineering cho coding task là cách biến yêu cầu mơ hồ thành một contract có thể thực thi và review. Với Claude Code, prompt tốt cần chỉ rõ Claude phải đọc gì, sửa gì, không được làm gì, và kiểm chứng bằng command nào.

Format chuẩn:

```text
Context -> Goal -> Constraints -> Acceptance Criteria -> Verification
```

Ý nghĩa từng phần:

- `Context`: repo, module, stack, trạng thái hiện tại, file liên quan nếu biết, convention cần giữ.
- `Goal`: kết quả cần đạt ở mức behavior hoặc technical outcome.
- `Constraints`: giới hạn file, command, dependency, architecture, permission, security.
- `Acceptance Criteria`: điều kiện cụ thể để coi task xong, có thể review bằng diff/test.
- `Verification`: command kiểm tra, thư mục chạy, output kỳ vọng, rủi ro khi chạy.

Nguyên tắc vận hành:

- Dùng `plan mode` cho bước đọc codebase và lập plan trước khi edit.
- Có thể vào `plan mode` bằng `Shift+Tab`, prefix prompt với `/plan`, hoặc chạy `claude --permission-mode plan`.
- Yêu cầu Claude nêu file đã đọc và bằng chứng trước khi đề xuất fix.
- Với thiếu dữ kiện, prompt phải ghi rõ: hỏi lại trước, không tự giả định.
- Dùng `CLAUDE.md` hoặc `.claude/CLAUDE.md` cho project memory: commands, architecture, conventions, security rules.
- Dùng `/init` để khởi tạo memory rồi chỉnh lại thủ công theo team.
- Dùng custom slash commands trong `.claude/commands/` cho prompt lặp lại như API plan, API review, test-first.
- Permission/default mode cần được kiểm soát khi cho Claude chạy command hoặc edit file.

## Sơ đồ tư duy hoặc luồng xử lý

Luồng prompt cho coding task:

```text
Nhận yêu cầu
  |
  v
Viết Context
  |
  v
Xác định Goal
  |
  v
Đặt Constraints
  |
  v
Viết Acceptance Criteria
  |
  v
Gắn Verification
  |
  v
Chạy Claude ở plan mode
  |
  v
Claude đọc file + nêu bằng chứng
  |
  +-- Thiếu thông tin -> Claude hỏi lại
  |
  +-- Đủ thông tin -> Developer duyệt plan
  |
  v
Implement bằng default mode/tool hẹp
  |
  v
Review git diff + chạy test
  |
  v
Accept / sửa tiếp / rollback
```

Luồng áp dụng cho `taskflow-ai`:

```text
Prompt khám phá backend
  -> xác định framework + module/API pattern
  -> prompt test-first CRUD tasks
  -> tạo test theo convention
  -> prompt implement production code nhỏ nhất
  -> npm run test -- --run
  -> git diff --stat
  -> prompt review API
  -> fix nhỏ nếu cần
```

Luồng ép Claude hỏi lại:

```text
Prompt có "Nếu thiếu thông tin, hỏi lại trước"
  |
  v
Claude gặp thiếu API contract/auth/schema/test command
  |
  +-- Hỏi lại cụ thể -> developer trả lời -> tiếp tục
  |
  +-- Tự giả định -> developer dừng -> yêu cầu plan lại với bằng chứng
```

## Bảng so sánh

| Loại task | Prompt nên nhấn mạnh | Acceptance Criteria tốt | Verification tốt |
| --- | --- | --- | --- |
| Feature | API contract, file scope, dependency, auth, validation | Endpoint/behavior cụ thể, error format, test pass | Test module, typecheck, diff summary |
| Bug fix | Reproduction, failing test, root cause, minimal change | Bug không còn, behavior cũ không đổi, regression test | Test case fail trước/pass sau |
| Refactor | Behavior lock, public contract, từng bước nhỏ | Không đổi response/status/schema, code dễ maintain hơn | Test trước/sau, diff nhỏ |
| Review | Impact thực tế, severity, file/path, test gap | Finding có correctness/security/performance/maintainability | Kết luận merge/block/redesign |
| Test-first | Test convention, contract, data setup, expected fail | Test mô tả behavior, không phụ thuộc order | Test fail đúng lý do trước implement |

| Prompt section | Dấu hiệu viết tốt | Dấu hiệu viết kém |
| --- | --- | --- |
| Context | Nêu repo, module, stack, convention, trạng thái hiện tại | "Dự án của tôi..." nhưng không nêu framework/module |
| Goal | Nêu behavior cần đạt | "Làm CRUD" nhưng không nói endpoint/validation |
| Constraints | Có giới hạn file, command, dependency, security | "Code clean nhé" |
| Acceptance Criteria | Review được bằng checklist | "Hoạt động tốt" |
| Verification | Có command, thư mục chạy, output kỳ vọng | "Test kỹ giúp tôi" |

| Command | Thư mục chạy | Dùng để làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `git status --short` | Root `taskflow-ai` | Kiểm tra working tree trước khi Claude sửa | Rỗng hoặc file đã hiểu rõ | Bỏ qua file lạ làm diff bị trộn |
| `claude --permission-mode plan` | Root `taskflow-ai` | Cho Claude đọc và lập plan | Session sẵn sàng, chưa edit | Plan sai nếu không yêu cầu bằng chứng |
| `git diff --stat` | Root `taskflow-ai` | Xem phạm vi patch | File thay đổi khớp plan | Không thấy logic chi tiết |
| `git diff` | Root `taskflow-ai` | Review patch chi tiết | Không có đổi ngoài scope | Diff dài dễ bỏ sót |
| `npm run test -- --run` | Package backend hoặc root có script | Chạy Vitest một lần | Test pass hoặc fail đúng lý do test-first | Có thể chạm DB test hoặc chạy lâu |
| `npm run typecheck` | Package có TypeScript config | Kiểm tra type error | Exit code 0 | Có thể lộ lỗi cũ ngoài scope |
| `git restore -- path/to/file` | Root `taskflow-ai` | Rollback một file | Không output nếu thành công | Mất thay đổi chưa commit trong file đó |

## Lỗi thường gặp

1. Prompt thiếu acceptance criteria  
   Claude có thể tạo endpoint nhưng thiếu validation, thiếu 404, hoặc response shape lệch convention.

2. Prompt feature nhưng thực chất là feature + refactor + migration + test + docs  
   Task quá rộng làm context dài, diff khó review, rollback khó.

3. Không yêu cầu Claude đọc code trước  
   Claude dễ tạo pattern mới thay vì dùng convention hiện có của `taskflow-ai`.

4. Không ép Claude hỏi lại  
   Khi thiếu auth rule, database schema hoặc test command, Claude có thể tự quyết định sai.

5. Verification mơ hồ  
   "Chạy test" không đủ. Cần biết chạy ở đâu, command nào, output kỳ vọng, rủi ro môi trường.

6. Dùng prompt review nhưng cho phép edit  
   Review nên là read-only trước. Nếu vừa review vừa sửa, finding dễ bị che bởi patch mới.

7. Quên rollback strategy  
   Khi patch rộng hoặc sai, developer mất thời gian gỡ từng thay đổi.

8. Đưa secret hoặc log nhạy cảm vào prompt  
   Prompt có thể trở thành rủi ro bảo mật. Nên sanitize `.env`, token, customer data, production log.

## Cách debug

Khi Claude tự giả định thay vì hỏi lại:

```text
Bạn vừa giả định thông tin chưa được xác nhận.
Dừng implement.
Liệt kê các giả định bạn đã dùng, file nào chứng minh hoặc không chứng minh được từng giả định.
Sau đó hỏi tôi tối đa 5 câu cần thiết để tiếp tục.
```

Khi patch quá rộng:

```bash
git diff --stat
```

Chạy ở root `taskflow-ai`. Nếu số file vượt plan, dừng edit. Tiếp theo:

```text
Patch hiện tại vượt scope.
Không sửa thêm.
Hãy phân loại từng file trong diff: cần giữ, cần bỏ, cần hỏi lại.
Đề xuất rollback từng file bằng git restore, nhưng không tự chạy.
```

Khi test fail:

```text
Test đang fail. Chưa sửa code.
Hãy phân tích failure output theo 3 nhóm:
1. Test setup/environment.
2. Behavior chưa implement.
3. Regression do patch mới.
Với mỗi nhóm, nêu bằng chứng từ log và file liên quan.
```

Khi Claude đề xuất command nguy hiểm:

```text
Không chạy command đó.
Giải thích command làm gì, dữ liệu nào có thể mất, và đề xuất command read-only thay thế để kiểm tra trạng thái.
```

Ví dụ thay `docker compose down -v` bằng command đọc trạng thái:

```bash
docker compose ps
```

Chạy ở root repo có `docker-compose.yml`. Lệnh này xem container đang chạy. Output kỳ vọng là danh sách service. Rủi ro thấp hơn vì không xóa volume, nhưng vẫn cần đảm bảo Docker context đang trỏ đúng môi trường local.

Khi cần rollback một file:

```bash
git restore -- backend/src/tasks/task.service.ts
```

Chạy ở root `taskflow-ai`. Output kỳ vọng thường trống. Rủi ro: mất mọi thay đổi chưa commit trong file đó. Nếu trong file có cả thay đổi của bạn, dùng `git diff -- backend/src/tasks/task.service.ts` trước và cân nhắc rollback thủ công.

## Link tài liệu nên đọc

- Claude Code overview: https://code.claude.com/docs/en/overview
- Claude Code common workflows: https://code.claude.com/docs/en/common-workflows
- Claude Code best practices: https://code.claude.com/docs/en/best-practices
- Claude Code memory: https://code.claude.com/docs/en/memory
- Claude Code slash commands: https://code.claude.com/docs/en/slash-commands
- Claude Code permissions: https://code.claude.com/docs/en/permissions
- Claude Code settings: https://code.claude.com/docs/en/settings
- Git diff documentation: https://git-scm.com/docs/git-diff
- Git restore documentation: https://git-scm.com/docs/git-restore
- Vitest CLI: https://vitest.dev/guide/cli
- Jest CLI options: https://jestjs.io/docs/cli
