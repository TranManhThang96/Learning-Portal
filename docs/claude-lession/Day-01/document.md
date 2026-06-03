# Document — Day 01

## Tóm tắt kiến thức

Day 01 đặt nền tảng mindset cho toàn khóa học: Claude Code không phải chatbot. Claude Code là agentic terminal tool làm việc trong repo, có thể đọc codebase, chỉnh file, chạy command và hỗ trợ Git workflow nếu bạn cấp quyền.

Ba cách dùng AI trong coding:

- AI chat: hỏi đáp, giải thích, sinh snippet dựa trên nội dung bạn cung cấp.
- Autocomplete: gợi ý code tiếp theo trong editor.
- Agentic coding: agent quan sát repo, lập plan, hành động và verify bằng command/diff/test.

Loop cần ghi nhớ:

```txt
observe -> plan -> act -> verify
```

Vai trò của developer:

- `Owner`: chịu trách nhiệm về thay đổi cuối cùng.
- `Reviewer`: đọc diff, kiểm tra edge cases, phát hiện hallucination hoặc test yếu.
- `Architect`: giữ architecture, convention, security boundary và maintainability.

Nguyên tắc Day 01:

- Bắt đầu bằng observe, chưa sửa file.
- Yêu cầu plan trước khi act.
- Dùng acceptance criteria rõ.
- Verify sau mỗi thay đổi.
- Không auto-approve command có side effect khi chưa hiểu rủi ro.

## Sơ đồ tư duy hoặc luồng xử lý

Luồng làm việc khuyến nghị:

```txt
Developer xác định task
        |
        v
Prompt có context + constraints + acceptance criteria
        |
        v
Claude Code observe repo
        |
        v
Claude Code đề xuất plan
        |
        v
Developer review plan
        |
        +---- plan sai/thiếu ---> yêu cầu sửa plan
        |
        v
Approve hành động nhỏ, đúng scope
        |
        v
Claude Code act: edit file/chạy command
        |
        v
Verify: git diff/test/lint/build/checklist
        |
        +---- fail ---> quay lại observe/plan
        |
        v
Developer accept hoặc rollback
```

Luồng quyết định permission:

```txt
Chưa hiểu repo?
  -> dùng plan/default, chỉ read-only

Plan đã rõ và thay đổi nhỏ?
  -> approve edit cụ thể

Lệnh có side effect?
  -> đọc mục đích, output kỳ vọng, rủi ro trước

Môi trường sandbox cô lập?
  -> có thể cân nhắc quyền mạnh hơn, vẫn review diff

Repo production/công ty?
  -> không bypass, không auto-approve lệnh destructive
```

## Bảng so sánh

### AI chat, autocomplete và Claude Code

| Tiêu chí | AI chat | Autocomplete | Claude Code |
|---|---|---|---|
| Nơi chạy | Web/app chat | Editor | Terminal trong repo |
| Context mặc định | Nội dung bạn paste | File đang mở và context editor | Codebase, file, command, Git theo quyền |
| Khả năng hành động | Thường chỉ trả lời | Chèn/gợi ý code | Đọc file, edit file, chạy command, hỗ trợ Git |
| Rủi ro chính | Trả lời thiếu context | Gợi ý sai local logic | Sửa nhầm file, chạy command có side effect |
| Cách kiểm soát | Đặt câu hỏi rõ | Review code gợi ý | Plan, permission, diff, test, rollback |
| Phù hợp | Giải thích, brainstorming | Viết nhanh đoạn code nhỏ | Task coding có workflow và verify |

### Prompt mơ hồ và prompt có acceptance criteria

| Tiêu chí | Prompt mơ hồ | Prompt có acceptance criteria |
|---|---|---|
| Ví dụ | "Tạo project taskflow-ai" | "Lập plan Day 02, chưa sửa file, tối đa 7 bước, mỗi bước có verify" |
| Scope | Mở, dễ phình to | Giới hạn rõ |
| Kết quả | Khó review | Có thể đối chiếu |
| Rủi ro | Agent tự quyết định quá nhiều | Developer giữ quyền quyết định |
| Khi dùng | Prototype nhanh trong sandbox | Team workflow, repo thật, task cần chất lượng |

### Permission nên hiểu sớm

| Cơ chế | Ý nghĩa ngắn | Nên dùng khi | Guardrail |
|---|---|---|---|
| Hỏi trước khi hành động | Claude hỏi trước khi edit hoặc chạy tool có side effect | Mới bắt đầu, repo chưa quen, task rủi ro | Bắt agent nêu file/command trước khi approve |
| `claude --permission-mode acceptEdits` | Cho phép tạo/sửa file và auto-approve một số filesystem command thông dụng trong working directory | Sandbox nhỏ, scope đã rõ, đã có Git diff để review | Không dùng cho repo có secret, production data hoặc task chưa có acceptance criteria |
| `.claude/settings.json` với `permissions.defaultMode: "auto"` | Đặt default permission mode ở cấp project | Team đã thống nhất guardrails và repo đủ an toàn | Review config trong PR; không để `auto` thành mặc định vô thức |
| Prompt read-only | Ràng buộc bằng prompt: chỉ đọc, không sửa file, không chạy command ghi file | Khám phá repo, lập plan, review architecture | Nếu Claude muốn act, dừng và yêu cầu plan lại |

## Lỗi thường gặp

- Mở Claude Code sai thư mục, khiến agent đọc nhầm repo.
- Yêu cầu "làm giúp tôi" nhưng không nói file nào được sửa.
- Không bắt agent liệt kê file đã đọc, nên khó phát hiện hallucination.
- Để agent implement trước khi có plan.
- Không chạy `git diff` sau khi edit.
- Accept output vì nhìn hợp lý, không đối chiếu acceptance criteria.
- Trộn nhiều task không liên quan trong cùng session làm context bị nhiễu.
- Để secret hoặc credential trong repo sandbox rồi cho agent scan.
- Bật `acceptEdits` hoặc `auto` ngoài sandbox khi chưa có guardrails.
- Xem Claude Code như junior developer tự trị, thay vì agent cần owner/reviewer/architect.

## Cách debug

### Khi Claude Code hiểu sai repo

Kiểm tra:

```bash
pwd
git status --short
```

Chạy ở đâu:

- Chạy trong terminal của project `taskflow-ai`.

Lệnh làm gì:

- `pwd` cho biết thư mục hiện tại.
- `git status --short` cho biết file nào đang thay đổi.

Kết quả kỳ vọng:

- `pwd` kết thúc bằng `taskflow-ai`.
- `git status --short` chỉ hiện file bạn mong đợi hoặc trống nếu chưa sửa gì.

Rủi ro:

- `git status --short` không kiểm tra logic, chỉ kiểm tra trạng thái file.

### Khi Claude Code nói về file không tồn tại

Hỏi lại:

```txt
Hãy chỉ ra bằng chứng trong repo: path file, đoạn nội dung liên quan, và command/read operation nào đã dùng. Nếu không có bằng chứng, hãy sửa lại kết luận.
```

Kiểm tra thủ công:

```bash
git ls-files
```

Lệnh làm gì:

- Liệt kê file đang được Git track.

Kết quả kỳ vọng:

- Chỉ có các file thật trong repo.

Rủi ro:

- File mới chưa track sẽ không xuất hiện. Nếu cần xem cả file chưa track, dùng `git status --short`.

### Khi agent sửa ngoài scope

Kiểm tra diff:

```bash
git diff --stat
git diff
```

Chạy ở đâu:

- Chạy trong root repo `taskflow-ai`.

Lệnh làm gì:

- `git diff --stat` tóm tắt file nào bị sửa và số dòng thay đổi.
- `git diff` hiển thị chi tiết thay đổi.

Kết quả kỳ vọng:

- Chỉ có file nằm trong scope của prompt.

Rủi ro:

- Diff dài dễ bỏ sót. Nếu diff quá lớn, dừng lại và chia task nhỏ hơn.

Rollback file cụ thể:

```bash
git restore -- path/to/file
```

Lệnh làm gì:

- Hủy thay đổi chưa commit của file được chỉ định.

Kết quả kỳ vọng:

- Thường không có output nếu thành công.

Rủi ro:

- Mất thay đổi chưa commit của file đó. Không dùng với file người khác đang sửa nếu làm trong repo chung.

### Khi cần quay lại session

Tiếp tục session gần nhất trong thư mục hiện tại:

```bash
claude --continue
```

Chọn session cụ thể:

```bash
claude --resume
```

Hoặc dùng trong Claude Code:

```txt
/resume
```

Kết quả kỳ vọng:

- Claude Code quay lại đúng conversation liên quan đến `taskflow-ai`.
- Bạn vẫn có thể yêu cầu nó tóm tắt context trước khi làm tiếp.

Rủi ro:

- Resume nhầm session có thể kéo theo context cũ không liên quan. Hãy kiểm tra `pwd`, `git status --short` và yêu cầu Claude tóm tắt current assumptions.

### Khi context bị nhiễu

Dùng trong Claude Code:

```txt
/clear
```

Dùng khi:

- Chuyển sang task không liên quan.
- Agent liên tục đưa thông tin cũ vào câu trả lời.

Dùng trong Claude Code:

```txt
/compact Tóm tắt các quyết định quan trọng về taskflow-ai, giữ lại stack, scope Day 01, file đã tạo và acceptance criteria đang dùng.
```

Dùng khi:

- Session dài nhưng vẫn cần giữ một số quyết định.

Rủi ro:

- Compact quá chung chung có thể làm mất chi tiết quan trọng. Hãy đưa instructions cụ thể.

## Link tài liệu nên đọc

- Claude Code Quickstart: https://code.claude.com/docs/en/quickstart
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code Permissions: https://code.claude.com/docs/en/permissions

Gợi ý cách đọc:

- Đọc Quickstart để nắm cách `cd /path/to/your/project`, chạy `claude`, dùng `/help`, `claude --continue`, `claude --resume` và `/resume`.
- Đọc Best Practices để nắm cách quản lý context, dùng `/clear` cho task không liên quan và `/compact <instructions>` khi cần tóm tắt session.
- Đọc Permissions để hiểu `claude --permission-mode acceptEdits`, `.claude/settings.json`, `permissions.defaultMode: "auto"`, và vì sao permission mạnh phải đi kèm scope nhỏ, Git diff và review.
