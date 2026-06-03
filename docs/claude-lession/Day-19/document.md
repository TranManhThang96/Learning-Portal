# Document — Day 19

## Tóm tắt kiến thức

Claude Code làm việc tốt nhất khi context sạch, đúng phạm vi và có cấu trúc. Task dài tốn token vì prompt, replies, file contents, command output, `CLAUDE.md`, auto memory, loaded skills, system instructions và lịch sử sửa sai đều có thể đi vào context.

Cost không chỉ là số tiền. Nó gồm thời gian chờ, vòng sửa lại, khả năng model quên instruction cũ và rủi ro sửa lan. Vì vậy Day 19 xem context window như tài nguyên cần quản lý chủ động.

Nguyên tắc:

- Task không liên quan: dùng `/clear`.
- Task dài nhưng cùng mạch: dùng `/compact <instructions>`.
- Cần đo token/activity: dùng `/usage`; `/cost` và `/stats` là alias.
- Cần xem phần nào đang phình context: dùng `/context` hoặc `/context all`.
- Câu hỏi nhanh: dùng `/btw`.
- Sai hướng: dùng `Esc`, sau đó `Esc + Esc` hoặc `/rewind`.
- Muốn chuyển session: tạo `CONTEXT_SUMMARY.md`.
- Muốn Claude ít đọc file: yêu cầu nêu file cần đọc và lý do trước khi mở file.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Nhận feature
  -> có liên quan task cũ?
      -> không: /clear
      -> có: /context
  -> ghi baseline?
      -> /usage + /context
  -> context gần đầy?
      -> có: /compact với instructions
      -> không: scope prompt
  -> Claude liệt kê file cần đọc
  -> approve plan hẹp
  -> implement narrow change
  -> git diff --stat
  -> sai scope?
      -> có: Esc + Esc hoặc /rewind
      -> không: run focused test
  -> đo lại /usage + /context
  -> tạo CONTEXT_SUMMARY.md
```

## Bảng so sánh

| Chủ đề | Nên dùng | Khi nào | Rủi ro nếu dùng sai |
| --- | --- | --- | --- |
| `/clear` | Reset context | Chuyển task không liên quan | Mất history nếu chưa summary |
| `/compact <instructions>` | Nén context | Task dài vẫn tiếp tục | Summary thiếu chi tiết nếu mơ hồ |
| `/usage` | Xem token/activity stats | Trước/sau task hoặc khi thấy chậm | Số tiền session có thể không phản ánh bill với Pro/Max |
| `/context all` | Xem breakdown đầy đủ | Context phình, Claude quên instruction | Dễ chỉ nhìn số mà không xử lý root cause |
| `/btw` | Hỏi nhanh | Câu hỏi không cần lưu history | Không dùng cho task dài |
| `/rewind` | Quay checkpoint hoặc summarize một phần | Claude sửa sai/lệch scope/context quá dài | Không thay thế git; Bash command changes không được checkpoint theo cùng cách |
| `CONTEXT_SUMMARY.md` | Tóm tắt thủ công | Chuyển session/bàn giao | Summary dài lại thành noise |
| `CLAUDE.md` | Rule bền vững | Commands, style, testing, security | File quá dài tốn context |
| Context rộng | Discovery ban đầu | Chưa biết kiến trúc | Tốn token, dễ sửa ngoài scope |
| Context hẹp | Implement feature | Đã biết file liên quan | Có thể bỏ sót dependency |
| Subagent | Investigation riêng context | Đọc nhiều file/log/test output | Cần summary tốt, có thể tăng tổng token nếu dùng quá nhiều |

## Lỗi thường gặp

1. Yêu cầu đọc toàn bộ repo cho feature nhỏ.
2. Paste nguyên stack trace/log dài vào prompt.
3. Để Claude tự quyết định phạm vi sửa mà không có plan.
4. Dùng `/compact` không có instruction.
5. Dùng `/clear` trước khi tạo summary cho task dang dở.
6. Nhồi tài liệu dài vào `CLAUDE.md`.
7. Không kiểm tra `git diff --stat`.
8. Cho Claude đọc `.env`, logs, build output hoặc coverage.
9. Tiếp tục sửa trong session đã có nhiều lần correction thất bại.
10. Rollback bằng git quá rộng, làm mất thay đổi của người khác.
11. Không ghi metric `/usage`/`/context`, nên không biết prompt hẹp có thật sự tiết kiệm hơn không.
12. Dùng subagent cho việc nhỏ, làm tổng token tăng mà không đem lại lợi ích.

## Cách debug

Kiểm tra context:

```text
/usage
/context
/context all
```

`/usage` cho biết token/activity stats của session. `/context all` mở rộng breakdown để biết messages, file contents, memory, skills hoặc tools đang chiếm nhiều chỗ.

Kiểm tra file đã sửa, chạy ở root `taskflow-ai`:

```bash
git diff --stat
```

Output kỳ vọng: chỉ vài file liên quan Task List/filter/test. Nếu thấy auth, routing, migration hoặc config ngoài scope, dừng lại và review trước khi tiếp tục.

Tìm file liên quan mà không đọc cả repo:

```bash
rg -n "TaskList|TaskFilter|status|priority" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**" --glob "!.git/**"
```

Output kỳ vọng: path và dòng match của component/type/test liên quan. Nếu output quá dài, refine keyword thay vì paste toàn bộ vào prompt.

Kiểm tra secret trước khi đưa context:

```bash
rg -n "SECRET|TOKEN|API_KEY|PASSWORD|PRIVATE_KEY|DATABASE_URL" . --glob "!node_modules/**" --glob "!dist/**" --glob "!coverage/**" --glob "!.git/**"
```

Rủi ro: output có thể chứa secret thật; không paste nguyên output vào chat.

Kiểm tra test script trước khi chạy:

```bash
npm pkg get scripts
```

Output kỳ vọng là JSON chứa script như `test`, `test:unit`, `test:e2e`, `lint` hoặc `typecheck`. Nếu project dùng `pnpm`/`yarn`, dùng package manager đang có trong repo thay vì tự đổi toolchain.

Rollback file cụ thể:

```bash
git restore -- path/to/file
```

Lệnh này bỏ thay đổi chưa commit của file chỉ định. Chỉ dùng sau khi đã đọc diff.

## Link tài liệu nên đọc

- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code Commands: https://code.claude.com/docs/en/commands
- Claude Code Costs: https://code.claude.com/docs/en/costs
- Claude Code Context Window: https://code.claude.com/docs/en/context-window
- How Claude Code Works: https://code.claude.com/docs/en/how-claude-code-works
- Claude Code Memory: https://code.claude.com/docs/en/memory
- Claude Code Checkpointing: https://code.claude.com/docs/en/checkpointing
- Claude Code Error Reference: https://code.claude.com/docs/en/errors
