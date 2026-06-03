# Document — Day 04

## Tóm tắt kiến thức

Permission mode trong Claude Code là lớp kiểm soát quyền cho agentic coding. Nó quyết định Claude được đọc gì, sửa gì, chạy lệnh nào, và khi nào phải hỏi developer.

Các điểm quan trọng:

- `default`: mode cân bằng cho công việc thường ngày, có prompt xin quyền khi cần.
- `plan`: mode an toàn để khảo sát codebase, đọc file, chạy lệnh read-only, và lập plan trước khi edit.
- `acceptEdits`: tự approve edits và một số common filesystem commands trong working directory, phù hợp task nhỏ trong branch sạch.
- `auto`: tự approve dựa trên safety checks, hiện được docs mô tả là research preview; cần môi trường dev có guardrails và vẫn phải review diff.
- `dontAsk`: tự deny các tool call cần hỏi quyền, trừ rule đã pre-approved hoặc read-only Bash command.
- `bypassPermissions`: bỏ qua gần như toàn bộ prompt permission, chỉ nên dùng trong sandbox/container/VM throwaway đã cô lập và không chứa secret.
- `.claude/settings.json`: có thể đặt `permissions.defaultMode`, ví dụ `auto`, nhưng team nên thống nhất policy và xác minh official docs/CLI version trước khi áp dụng.
- `CLAUDE.md` hoặc `.claude/CLAUDE.md`: nơi lưu coding standards, testing requirements, common commands, và rule review; đây là hướng dẫn cho Claude, không phải enforcement permission.

Nguyên tắc cốt lõi của Day 04: Claude Code có thể act nhanh, nhưng developer vẫn là owner của code. Permission mode chỉ giảm rủi ro, không thay thế review, test, Git hygiene, và judgment của team.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Nhận task
  |
  v
Mở đúng project: cd /path/to/project -> claude -> /help khi cần
  |
  v
Kiểm tra Git state
  |
  v
Chọn permission mode
  |
  +-- Scope chưa rõ / rủi ro cao -> plan
  |
  +-- Scope nhỏ / branch sạch -> default
  |
  +-- Sửa nhỏ đã duyệt / sandbox -> acceptEdits
  |
  +-- Audit read-only / khóa quyền -> dontAsk
  |
  +-- Sandbox throwaway -> bypassPermissions
  |
  v
Yêu cầu Claude lập plan
  |
  v
Developer approve phạm vi
  |
  v
Claude sửa file nhỏ
  |
  v
git diff --stat -> git diff
  |
  v
Chạy test phù hợp
  |
  v
Accept / chỉnh tiếp / rollback
  |
  v
Ghi rule lặp lại vào CLAUDE.md hoặc .claude/CLAUDE.md
```

Luồng an toàn nên dùng trong `taskflow-ai`:

```text
plan mode
  -> đọc module tasks
  -> plan validation title
  -> developer duyệt
default mode với tool hẹp như Bash(git status *)
  -> edit 1 file
  -> Claude tóm tắt diff
developer terminal
  -> git diff
  -> npm test hoặc npm run test
  -> commit thủ công nếu đạt
```

## Bảng so sánh

| Tình huống | Mode nên dùng | Vì sao | Không nên làm |
| --- | --- | --- | --- |
| Mới mở repo, chưa hiểu architecture | `plan` | Cho Claude đọc và giải thích trước khi sửa | Dùng `acceptEdits` ngay |
| Sửa bug nhỏ, biết file cần sửa | `default` | Vẫn kiểm soát được tool call | Cho phép toàn bộ `Bash` nếu không cần |
| Format/lint fix nhỏ trong branch sạch | `acceptEdits` | Tăng tốc thao tác edit phổ biến | Chạy trên repo có thay đổi chưa review |
| Audit security/read-only | `dontAsk` | Ép Claude không tự sửa hoặc chạy tool ngoài rule | Kỳ vọng Claude tự fix mọi thứ |
| Workshop trong container/VM có thể reset | `bypassPermissions` | Tốc độ cao, môi trường có thể bỏ đi | Dùng trên máy thật, repo có secret, hoặc network nhạy cảm |
| Migration database hoặc xóa dữ liệu | `plan` + manual command | Developer phải tự chạy command nguy hiểm | Auto-approve migration/drop/reset |
| PR review | `plan` hoặc `dontAsk` | Claude đóng vai reviewer, không edit | Để Claude commit thay reviewer |
| Chuẩn hóa policy cho team | `default`/`plan` + settings | Dễ enforce và audit hơn prompt miệng | Bật `auto`/`bypassPermissions` mà chưa kiểm docs/version |

| Lệnh | Dùng để làm gì | Kết quả kỳ vọng | Rủi ro |
| --- | --- | --- | --- |
| `cd /path/to/your/project` | Chuyển terminal vào đúng project trước khi mở Claude | Prompt đang ở root repo cần làm | Mở sai thư mục làm Claude đọc/sửa sai repo |
| `claude` | Mở session Claude Code tương tác mặc định | Welcome screen hoặc prompt Claude Code | Nếu đang ở thư mục sai, context sai ngay từ đầu |
| `claude --continue` | Tiếp tục session gần nhất trong thư mục hiện tại | Quay lại đúng hội thoại gần nhất | Có thể nối nhầm context nếu thư mục có nhiều session |
| `claude --resume` | Chọn session để resume | Danh sách session hoặc picker | Chọn nhầm session đưa yêu cầu cũ vào task mới |
| `claude --version` | Xem version CLI đang dùng | In phiên bản Claude Code | Team dùng version khác nhau có thể khác behavior |
| `git status --short` | Xem working tree trước khi AI sửa | Rỗng hoặc danh sách file đã hiểu | Bỏ sót thay đổi của người khác |
| `git diff --stat` | Xem phạm vi patch | Số file/dòng thay đổi nhỏ | Không thấy logic chi tiết |
| `git diff` | Review patch chi tiết | Diff đúng acceptance criteria | Diff dài dễ bỏ sót |
| `git restore -- path/to/file` | Rollback một file | Không có output nếu thành công | Mất thay đổi chưa commit trong file đó |
| `claude --permission-mode plan` | Mở Claude Code read-only planning | Session Claude sẵn sàng | Plan vẫn cần kiểm chứng |
| `claude -p "Apply the lint fixes" --permission-mode acceptEdits` | Chạy prompt một lần với auto-approve edits | Patch lint nhỏ | Không dùng cho thay đổi chưa rõ phạm vi |

## Lỗi thường gặp

1. Dùng `acceptEdits` khi chưa có plan  
   Hậu quả là Claude có thể sửa nhiều file, đổi style, hoặc thêm abstraction không cần thiết.

2. Bấm approve command theo thói quen  
   Một số command trông vô hại nhưng có thể xóa dữ liệu local, ví dụ `git clean -fd` hoặc `docker compose down -v`.

3. Cho `--allowedTools "Bash,Read,Edit"` quá sớm  
   Broad permission làm giảm giá trị của permission mode. Nên cấp tool theo task, càng hẹp càng tốt.

4. Không review diff trước khi accept  
   AI có thể pass test nhưng vẫn đổi API contract, bỏ validation cũ, hoặc sửa file ngoài scope.

5. Dùng `bypassPermissions` trên máy làm việc chính  
   Mode này chỉ hợp lý trong sandbox cô lập như container/VM throwaway. Nếu repo có secret, config thật, data local quan trọng, hoặc network có thể chạm dịch vụ nội bộ, rủi ro quá cao. Trước khi đưa vào workflow team, kiểm official docs và `claude --version`/`claude --help`.

6. Không phân biệt read-only command và lệnh destructive  
   `git diff` là read-only. `git reset --hard` là destructive. Hai lệnh đều thuộc Git nhưng mức rủi ro hoàn toàn khác.

7. Tin rằng `CLAUDE.md` có thể chặn tool thật
   `CLAUDE.md` giúp Claude làm theo convention, nhưng không enforce permission. Muốn chặn thật, dùng permission rule trong `.claude/settings.json`, managed settings, hoặc hook.

Ví dụ policy tối thiểu trong `.claude/settings.json` cho repo team:

```json
{
  "permissions": {
    "defaultMode": "default",
    "deny": [
      "Read(./.env)",
      "Read(./secrets/**)",
      "Bash(git reset *)",
      "Bash(git clean *)",
      "Bash(docker compose down -v*)"
    ],
    "ask": [
      "Bash(git push *)",
      "Bash(npm install *)"
    ]
  }
}
```

File này đặt ở root project, path `.claude/settings.json`. Mục đích là enforce deny/ask rule tối thiểu; vẫn cần human review vì Bash pattern là prefix/glob rule chứ không phải security sandbox hoàn chỉnh.

## Cách debug

Khi Claude Code sửa sai hoặc phạm vi patch quá rộng:

1. Dừng session implement và không approve thêm tool call.
2. Chạy trong root `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này giúp xác định patch rộng tới đâu. Nếu thấy nhiều file ngoài scope, không tiếp tục implement.

3. Xem diff chi tiết:

```bash
git diff
```

Đọc theo thứ tự: file bị chạm, public API change, logic change, test change, config change.

4. Nếu chỉ một file sai và bạn chắc chắn muốn bỏ:

```bash
git restore -- path/to/file
```

Thay `path/to/file` bằng file thật. Lệnh này mất thay đổi chưa commit trong file đó, nên chỉ chạy sau khi đã review.

5. Quay lại `plan` mode và prompt lại:

```text
Patch vừa rồi quá rộng. Hãy lập lại plan nhỏ hơn.
Chỉ đề xuất một file cần sửa, không implement.
Nêu rõ vì sao file đó là điểm thay đổi tối thiểu.
```

Khi Claude Code bị chặn permission:

- Kiểm tra mode hiện tại có phải `dontAsk` hoặc `plan` không.
- Nếu task chỉ cần đọc, giữ mode hiện tại và yêu cầu Claude mô tả command để bạn tự chạy.
- Nếu task cần sửa, mở session `default` với tool hẹp thay vì chuyển thẳng sang `acceptEdits`.

Khi test thất bại sau patch:

- Yêu cầu Claude review failure output, nhưng chưa cho edit.
- Hỏi Claude failure đến từ bug mới, test cũ không phù hợp, hay môi trường.
- Chỉ cho sửa tiếp sau khi có diagnosis và file scope rõ.

## Link tài liệu nên đọc

- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Settings: https://code.claude.com/docs/en/settings
- Claude Code Quickstart: https://code.claude.com/docs/en/quickstart
- Claude Code CLI reference: https://code.claude.com/docs/en/cli-reference
- Claude Code Memory / CLAUDE.md: https://code.claude.com/docs/en/memory
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Git diff documentation: https://git-scm.com/docs/git-diff
