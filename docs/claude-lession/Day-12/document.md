# Document — Day 12

## Tóm tắt kiến thức

Hook trong Claude Code là automation chạy theo event trong session. Hook nhận JSON input qua `stdin`, đọc các field như `session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input.command`, `tool_input.file_path`, rồi quyết định log, format, thêm context hoặc block hành động.

Day 12 tập trung vào 4 event:

- `PreToolUse`: chạy trước tool. Dùng để block risky command, bảo vệ file nhạy cảm, yêu cầu policy check. Đây là nơi đúng để chặn `rm -rf`.
- `PostToolUse`: chạy sau tool. Dùng để format file vừa sửa, log activity, phân tích output. Không dùng để ngăn hành động đã xảy ra.
- `UserPromptSubmit`: chạy khi user submit prompt, trước khi Claude xử lý. Dùng để chặn prompt chứa secret hoặc thêm context ngắn. Không log raw prompt.
- `SessionStart`: chạy khi session start/resume/clear/compact theo matcher. Dùng để nạp context an toàn hoặc ghi audit nhẹ.

Các điểm cần nhớ:

- Dùng đúng scope: `~/.claude/settings.json` cho user, `taskflow-ai/.claude/settings.json` cho team shared, `taskflow-ai/.claude/settings.local.json` cho lab/local.
- Hook command nên nằm ở file script riêng trong `.claude/hooks` để tránh JSON escaping phức tạp.
- `matcher` phải hẹp. Với `PreToolUse`/`PostToolUse`, matcher thường là `Bash`, `Edit|Write|MultiEdit`.
- `if` giúp filter thêm theo tool input, ví dụ `Bash(rm *)`, nhưng script vẫn phải tự validate.
- Exit `0` nghĩa là hook thành công; exit `2` là blocking error ở event hỗ trợ block như `PreToolUse`; nếu dùng JSON control thì hook phải exit `0`. Với `PreToolUse`, JSON control hiện tại nằm trong `hookSpecificOutput.permissionDecision`; với `UserPromptSubmit`, dùng `{ "decision": "block", "reason": "..." }` để block prompt rõ ràng.
- Luôn set `timeout`. Hook block/log nên rất ngắn; formatter chỉ format file vừa sửa.
- Timeout mặc định trong docs hiện tại: command/HTTP/MCP hook thường là `600` giây; riêng `UserPromptSubmit` hạ default của các loại này xuống `30` giây; prompt hook là `30` giây; agent hook là `60` giây. Đây là fallback, không phải best practice cho repo team.
- Log không được chứa secret, token, cookie, authorization header, raw prompt, `.env`, transcript hoặc stdout/stderr dài.
- Hook không được chạy command destructive như `rm`, `git reset`, `git clean`, `docker compose down -v`, migration destructive.

## Sơ đồ tư duy hoặc luồng xử lý

```text
User prompt / Claude action
  |
  v
Claude Code event
  |
  +-- UserPromptSubmit
  |     |
  |     +-- kiểm tra prompt có secret?
  |     +-- thêm context ngắn nếu cần
  |
  +-- SessionStart
  |     |
  |     +-- ghi session start
  |     +-- nạp context an toàn
  |
  +-- PreToolUse
  |     |
  |     +-- matcher tool: Bash, Edit, Write...
  |     +-- if filter: Bash(rm *), Edit(*.ts)...
  |     +-- script đọc JSON stdin
  |     +-- exit 2 -> block tool call
  |     +-- exit 0 -> cho tool chạy
  |
  +-- Tool executes
  |
  +-- PostToolUse
        |
        +-- formatter file vừa sửa
        +-- log Bash command đã redacted
        +-- feedback ngắn cho Claude
```

Luồng triển khai hook an toàn:

```text
Xác định use case
  |
  v
Chọn event đúng
  |
  v
Chọn scope local trước
  |
  v
Viết matcher hẹp + timeout
  |
  v
Tách script riêng trong .claude/hooks
  |
  v
Script đọc JSON, validate field, không destructive
  |
  v
jq empty settings.local.json
  |
  v
claude --debug-file .claude/logs/hooks-debug.log
  |
  v
Test command an toàn
  |
  v
Review diff, logs, secret leakage
  |
  +-- ổn định -> cân nhắc promote sang .claude/settings.json
  |
  +-- lỗi/block nhầm -> disableAllHooks, sửa matcher/script
```

## Bảng so sánh

| Event | Chạy trước/sau | Có thể block trước hành động? | Input quan trọng | Use case tốt | Rủi ro chính |
| --- | --- | --- | --- | --- | --- |
| `PreToolUse` | Trước tool | Có, dùng exit `2` | `tool_name`, `tool_input` | Block `rm -rf`, bảo vệ `.env`, policy check | Block nhầm, matcher rộng làm chậm mọi tool |
| `PostToolUse` | Sau tool | Không ngăn được hành động đã xảy ra | `tool_name`, `tool_input`, tool result tùy schema | Format file, log command, feedback sau edit | Formatter tạo diff lớn, log lộ secret |
| `UserPromptSubmit` | Trước Claude xử lý prompt | Có thể block prompt | prompt/user input và session metadata | Chặn secret trong prompt, thêm context ngắn | Log raw prompt, làm mọi lượt chat chậm |
| `SessionStart` | Khi start/resume | Không phải event tool | source/session metadata | Nạp context, ghi audit start | Startup chậm, context noise |

| Scope | File | Nên chứa | Không nên chứa |
| --- | --- | --- | --- |
| User | `~/.claude/settings.json` | Rule cá nhân, path user-local | Hook phụ thuộc project `taskflow-ai` |
| Project shared | `.claude/settings.json` | Guardrail team đã review | Secret, path máy cá nhân, log local |
| Project local | `.claude/settings.local.json` | Lab, thử nghiệm, local override | Policy duy nhất team dựa vào |
| Managed | Managed settings | Policy tổ chức | Experiment chưa review |

| Hook use case | Event nên dùng | Matcher gợi ý | Timeout gợi ý | Ghi chú |
| --- | --- | --- | --- | --- |
| Chặn `rm -rf` | `PreToolUse` | `Bash` + `if: Bash(rm *)` | `5` giây | Dùng cả permission `deny` nếu command pattern rõ |
| Formatter sau edit | `PostToolUse` | `Edit|Write|MultiEdit` | `15-30` giây | Chỉ format file vừa sửa, không toàn repo |
| Log command | `PostToolUse` | `Bash` | `3-5` giây | Redact secret, append JSONL local |
| Chặn prompt chứa secret | `UserPromptSubmit` | Event này thường không cần matcher tool | `3-5` giây | Không log raw prompt |
| Nạp context đầu session | `SessionStart` | `startup|resume|clear|compact` nếu cần | `5-10` giây | Output ngắn, không gọi network |

| Chủ đề safety | Nên làm | Không nên làm |
| --- | --- | --- |
| Matcher | Hẹp theo tool và command/file pattern | Dùng `"*"` cho mọi event |
| JSON | Validate bằng `jq empty`, escape quote trong `command` | Nhồi pipeline dài có nhiều quote vào settings |
| Script | `set -euo pipefail`, fallback field thiếu, quote path | Tin rằng field luôn tồn tại |
| Formatter | Chỉ format file vừa sửa, extension allowlist | Chạy `npm run format` toàn repo sau mọi edit |
| Logging | Log metadata đã redacted vào `.claude/logs` | Log `.env`, prompt, transcript, stdout/stderr dài |
| Command | Đọc input, append log, chạy formatter local | `rm`, `git reset`, `git clean`, volume delete, migration destructive |
| Debug | `/hooks`, `claude --debug-file`, hook log, exit code | Xóa cả `.claude` hoặc reset repo để hết lỗi |

## Lỗi thường gặp

1. Dùng `PostToolUse` để chặn command nguy hiểm  
   Lúc này command đã chạy. Cách sửa: chuyển policy block sang `PreToolUse`.

2. Matcher quá rộng  
   Ví dụ matcher `"*"` làm script chạy trên mọi tool. Workflow chậm và debug khó. Cách sửa: dùng `Bash`, `Edit|Write|MultiEdit`, hoặc `if` hẹp hơn.

3. Script phụ thuộc field luôn tồn tại  
   `jq -r '.tool_input.command'` có thể trả `null` với tool không phải Bash. Cách sửa: dùng `.tool_input.command // ""` hoặc `.tool_input.file_path // empty`.

4. JSON escaping sai trong settings  
   Command có quote hoặc path có khoảng trắng dễ làm JSON invalid. Cách sửa: tách script riêng, dùng exec form `"command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/script.sh"` kèm `"args": []`, validate bằng `jq empty`.

5. Formatter hook format toàn repo  
   Sau một edit nhỏ, diff biến thành hàng trăm file. Cách sửa: chỉ format `tool_input.file_path` và extension allowlist.

6. Log chứa secret  
   Bash command có thể chứa `TOKEN=...`, header, password, cookie. Cách sửa: redact trước khi ghi log, không log stdout/stderr/prompt/transcript, đưa `.claude/logs/` vào ignore.

7. Hook gọi network hoặc service ngoài  
   Network chậm hoặc fail làm Claude Code session kẹt. Cách sửa: hook phải local, deterministic; việc nặng chuyển sang command user chủ động chạy.

8. Không có timeout  
   Hook treo làm Claude Code treo theo. Cách sửa: set `timeout` cho từng hook, thường `3-30` giây tùy use case.

9. Không biết hook đến từ scope nào  
   User, project, local, managed settings có thể cùng tồn tại. Cách sửa: dùng `/hooks` và debug log để xem hook matched và command nào chạy.

10. Disable bằng cách xóa bừa file  
   Xóa `.claude` hoặc reset repo có thể mất rule team hoặc thay đổi của người khác. Cách sửa: dùng `disableAllHooks` trong local settings hoặc tắt bằng `/hooks` nếu phù hợp.

## Cách debug

Kiểm tra settings JSON. Chạy ở root `taskflow-ai`:

```bash
jq empty .claude/settings.local.json
```

Lệnh này validate JSON local settings. Output kỳ vọng rỗng, exit code `0`. Rủi ro thấp; nếu file không tồn tại, command báo lỗi file missing.

Mở Claude Code với debug file. Chạy ở root `taskflow-ai`:

```bash
claude --debug-file .claude/logs/hooks-debug.log
```

Lệnh này ghi log debug hook vào file local. Output kỳ vọng là session Claude Code sẵn sàng. Rủi ro: debug log có thể chứa command, path, stdout/stderr; không commit hoặc paste raw log.

Trong Claude Code, chạy:

```text
/hooks
```

Slash command này hiển thị hook đang cấu hình. Output kỳ vọng cho thấy event, matcher, command và scope. Rủi ro thấp; cần kiểm tra kỹ nếu nhiều scope cùng có hook.

Xem debug log. Chạy ở root `taskflow-ai`:

```bash
tail -n 80 .claude/logs/hooks-debug.log
```

Lệnh này xem 80 dòng cuối debug log. Output kỳ vọng có event, hook command, timeout, exit status, stdout/stderr. Rủi ro: log có thể chứa dữ liệu nhạy cảm; redact trước khi đưa vào prompt.

Xem command log. Chạy ở root `taskflow-ai`:

```bash
tail -n 20 .claude/logs/command-log.jsonl
```

Lệnh này xem 20 dòng log Bash gần nhất. Output kỳ vọng là JSONL đã redacted. Rủi ro: nếu redaction chưa đủ, log vẫn có thể chứa secret; không commit.

Kiểm tra hook script có executable. Chạy ở root `taskflow-ai`:

```bash
ls -l .claude/hooks
```

Lệnh này liệt kê file script và permission. Output kỳ vọng script `.sh` có quyền execute trên Unix-like shell. Rủi ro thấp; trên Windows PowerShell, permission execute có thể không phản ánh giống Linux.

Disable toàn bộ hook local khi bị kẹt bằng settings:

```json
{
  "disableAllHooks": true
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: tắt hook trong scope local để tiếp tục làm việc và debug. Cách test: mở lại Claude Code, chạy `/hooks`, xác nhận hook không còn execute. Edge case: hook ở project shared/managed có thể vẫn tồn tại tùy precedence, cần xem debug log.

Prompt debug nên dùng:

```text
Hook đang block workflow. Hãy phân tích từ settings và debug log đã redacted.

Ràng buộc:
- Chưa sửa file.
- Xác định hook nào matched, event nào, command nào, exit code nào.
- Phân loại lỗi: JSON invalid, matcher sai, script bug, timeout, permission, secret redaction, hay logic block nhầm.
- Đề xuất patch nhỏ nhất.
```

## Link tài liệu nên đọc

- Claude Code Hooks: https://code.claude.com/docs/en/hooks
- Claude Code Hooks Guide: https://code.claude.com/docs/en/hooks-guide
- Claude Code Settings / `.claude` directory: https://code.claude.com/docs/en/claude-directory
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Troubleshooting: https://code.claude.com/docs/en/troubleshooting
- jq Manual: https://jqlang.github.io/jq/manual/
- Git Ignore documentation: https://git-scm.com/docs/gitignore
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
