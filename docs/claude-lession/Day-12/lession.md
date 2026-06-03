# Day 12 — Hooks trong Claude Code

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Giải thích được hook trong Claude Code là gì, chạy ở điểm nào trong agentic workflow và vì sao hook khác với prompt, permission và slash command.
- Cấu hình hook ở đúng scope: user, project hoặc local; biết khi nào nên commit `.claude/settings.json` và khi nào chỉ dùng `.claude/settings.local.json`.
- Dùng `PreToolUse`, `PostToolUse`, `UserPromptSubmit` và `SessionStart` cho đúng mục đích.
- Tạo hook chặn command nguy hiểm như `rm -rf` trước khi Bash tool chạy.
- Tạo hook chạy formatter sau khi Claude Code sửa file, nhưng chỉ trong matcher hẹp và extension được kiểm soát.
- Tạo hook ghi log command phục vụ audit/debug mà không làm lộ secret.
- Debug hook bằng `/hooks`, `claude --debug`, `claude --debug-file`, log file riêng và cách disable hook khi workflow bị kẹt.
- Nhận diện rủi ro: hook chạy command tự động, timeout, JSON escaping sai, matcher quá rộng, log chứa secret, hook gây side effect khó truy vết.

## 2. Bối cảnh thực tế

Khi team dùng Claude Code trên repo thật như `taskflow-ai`, vấn đề không chỉ là "Claude có viết code đúng không". Vấn đề lớn hơn là Claude Code có thể chạy tool: đọc file, sửa file, chạy Bash command, tạo test, format code, gọi script. Các hành động đó xảy ra nhanh, nhiều khi nằm giữa một phiên làm việc dài. Nếu mọi thứ chỉ dựa vào human review sau cùng, một command nguy hiểm hoặc một edit ngoài scope có thể đã xảy ra trước khi bạn nhìn thấy diff.

Hook trong Claude Code là cơ chế event-driven automation: khi một sự kiện xảy ra trong session, Claude Code gửi JSON input vào một script hoặc command bạn cấu hình. Script đó có thể kiểm tra, ghi log, trả feedback hoặc block hành động tùy event. Hook giúp biến rule an toàn của team thành guardrail tự động.

Ví dụ trong `taskflow-ai`:

- Trước khi Bash chạy, chặn `rm -rf`, `docker compose down -v`, migration destructive hoặc command đụng production database.
- Sau khi Claude Code dùng `Edit` hoặc `Write`, chạy formatter cho đúng file vừa sửa.
- Sau mỗi Bash command, ghi audit log gồm thời gian, session id, working directory và command đã redacted.
- Khi user submit prompt, block prompt chứa secret hoặc production credential.
- Khi session bắt đầu, nhắc Claude Code đọc `CLAUDE.md`, hiển thị project context hoặc ghi session start log.

Không nên dùng hook khi:

- Bạn chưa hiểu rõ command hook sẽ chạy với quyền gì trên máy mình.
- Logic hook phụ thuộc network, service ngoài, database hoặc state không ổn định.
- Hook làm thay đổi code ngoài file mà Claude vừa sửa.
- Hook chạy command destructive như `rm`, `git reset`, `git clean`, `docker compose down -v`, migration rollback hoặc xóa cache rộng.
- Team chưa có cách debug/disable hook khi nó block nhầm.

Hook là guardrail, không phải thay thế cho review. Nếu hook quá thông minh, quá rộng hoặc tự sửa nhiều thứ, nó có thể biến workflow thành một hệ thống khó debug hơn cả việc để Claude Code chạy tự do.

## 3. Kiến thức nền

### Hook là gì

Hook là command hoặc script được Claude Code tự động chạy khi có event. Với command hook, Claude Code truyền dữ liệu event qua `stdin` dưới dạng JSON. Script đọc JSON này, quyết định làm gì, rồi trả kết quả qua exit code, stdout hoặc stderr.

Luồng tối giản:

```text
Claude Code event
  |
  v
Matcher trong settings có khớp không?
  |
  +-- Không -> bỏ qua hook
  |
  v
Chạy hook command, truyền JSON vào stdin
  |
  v
Hook đọc tool_name, tool_input, cwd, session_id...
  |
  v
Exit 0 -> tiếp tục / ghi output tùy event
Exit 2 -> block ở event hỗ trợ block, stderr gửi lại Claude
Exit khác -> lỗi hook, thường không block nhưng được log
```

Hook thường nằm trong settings:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(rm *)",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm-rf.sh",
            "args": [],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

File path trong ví dụ: `taskflow-ai/.claude/settings.local.json`.

Mục đích: cấu hình một hook chạy trước Bash tool, chỉ khi command trông giống `rm ...`, rồi gọi script trong project.

Cách test: mở Claude Code tại root `taskflow-ai`, yêu cầu chạy một command an toàn như `pwd`, sau đó thử prompt yêu cầu `rm -rf tmp`. Hook phải không ảnh hưởng `pwd` và phải block command nguy hiểm.

Edge cases: khi tham chiếu script trong project, ưu tiên exec form với `${CLAUDE_PROJECT_DIR}` và `args: []` để tránh lỗi shell quoting khi path có khoảng trắng. Trường `if` chỉ là filter phụ; script vẫn phải tự kiểm tra command vì matcher có thể quá rộng hoặc Claude Code version khác có behavior khác.

### Scope cấu hình

Claude Code có nhiều nơi đặt settings. Chọn sai scope là lỗi phổ biến trong team.

| Scope | File thường dùng | Khi dùng | Rủi ro |
| --- | --- | --- | --- |
| User | `~/.claude/settings.json` | Rule cá nhân áp dụng mọi repo, ví dụ log command local | Dễ làm repo khác bị ảnh hưởng; không nên chứa rule project-specific |
| Project shared | `taskflow-ai/.claude/settings.json` | Guardrail team muốn commit vào repo, ví dụ chặn command destructive | Hook chạy cho mọi người; phải review kỹ, cross-platform nếu team dùng nhiều OS |
| Project local | `taskflow-ai/.claude/settings.local.json` | Lab, thử nghiệm, secret/local path, rule cá nhân trong project | Không share cho team; người khác không có guardrail này |
| Managed/enterprise | Managed settings | Policy tổ chức | Developer local khó override; cần quy trình thay đổi rõ |

Trong Day 12, thực hành mặc định dùng `.claude/settings.local.json` để không ảnh hưởng worker khác. Chỉ promote sang `.claude/settings.json` khi team đã review script, matcher, timeout và logging policy.

### Event quan trọng trong bài này

| Event | Chạy khi nào | Use case tốt | Không nên dùng để |
| --- | --- | --- | --- |
| `PreToolUse` | Trước khi một tool chạy | Block command nguy hiểm, bảo vệ file nhạy cảm, yêu cầu confirmation | Chạy formatter hoặc sửa code vì tool chưa chạy |
| `PostToolUse` | Sau khi tool chạy | Format file vừa sửa, log activity, phân tích output | Chặn hành động đã xảy ra; nếu cần block thì dùng `PreToolUse` |
| `UserPromptSubmit` | Khi user vừa submit prompt, trước khi Claude xử lý | Block prompt chứa secret, thêm context ngắn, log prompt metadata | Log toàn bộ prompt nếu prompt có thể chứa credential |
| `SessionStart` | Khi session start/resume/clear/compact tùy matcher | Nạp context an toàn, ghi session start, nhắc rule | Chạy setup nặng, install dependency, reset state |

Các event khác như `Stop`, `SubagentStop`, `PreCompact`, `Notification`, `SessionEnd` cũng hữu ích, nhưng Day 12 tập trung vào 4 event đủ dùng cho workflow team.

Ví dụ `UserPromptSubmit` để chặn prompt có dấu hiệu chứa secret:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/check-prompt-secret.sh",
            "args": [],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: chạy script trước khi Claude xử lý prompt của user. Với `UserPromptSubmit`, nếu cần block prompt, command hook nên trả JSON có `"decision": "block"` và `"reason"` thay vì chỉ dựa vào stderr.

Cách test: dùng prompt chứa token giả như `token=fake-value-for-redaction-test`, không dùng secret thật. Hook phải block prompt và không đưa prompt đó vào context.

Edge cases: không log raw prompt. Prompt có thể chứa credential thật do user paste nhầm; nếu hook ghi prompt vào log thì hook trở thành nguồn leak mới.

Script tối giản cho ví dụ trên:

```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
PROMPT="$(printf '%s' "$INPUT" | jq -r '.prompt // ""')"

if printf '%s' "$PROMPT" | grep -Eiq '(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|api[_-]?key=|token=|password=|authorization:)'; then
  jq -nc --arg reason "Prompt appears to contain a secret. Remove credentials before asking Claude Code to process it." \
    '{decision:"block", reason:$reason}'
  exit 0
fi

exit 0
```

File path: `taskflow-ai/.claude/hooks/check-prompt-secret.sh`.

Mục đích: kiểm tra prompt user submit, block bằng JSON decision nếu thấy pattern nhạy cảm.

Cách test: cấu hình hook local, mở Claude Code, gửi prompt có token giả. Output kỳ vọng là prompt bị block với reason rõ ràng.

Edge cases: regex chỉ là lớp bảo vệ thô, có false positive và false negative. Không dùng hook này để chứng minh prompt "sạch" tuyệt đối.

Ví dụ `SessionStart` để thêm context ngắn khi mở hoặc resume session:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/session-context.sh",
            "args": [],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: chạy hook khi session mới bắt đầu hoặc resume. `SessionStart` chỉ nên tạo context nhẹ, ví dụ branch hiện tại và nhắc không log secret.

Cách test: mở Claude Code từ root `taskflow-ai`, xem transcript/context đầu session hoặc debug log để xác nhận hook chạy.

Edge cases: `SessionStart` chạy lại khi resume, vì vậy không đặt setup nặng hoặc command có side effect ở đây.

Script tối giản:

```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
SOURCE="$(printf '%s' "$INPUT" | jq -r '.source // "unknown"')"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

cd "$PROJECT_DIR"
BRANCH="$(git branch --show-current 2>/dev/null || true)"

jq -nc \
  --arg source "$SOURCE" \
  --arg branch "$BRANCH" \
  '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:("Session source: " + $source + "\nCurrent branch: " + $branch + "\nReminder: do not read or log .env, secrets, tokens, or production data.")}}'
```

File path: `taskflow-ai/.claude/hooks/session-context.sh`.

Mục đích: thêm context ngắn đầu session mà không đọc file nhạy cảm.

Cách test: chạy Claude Code với debug file và kiểm tra `SessionStart` hook completed status `0`.

Edge cases: stdout của `SessionStart` có thể đi vào context, nên không in output dài, không in `git diff`, không in environment variable.

### JSON input của hook

Với `PreToolUse` hoặc `PostToolUse` cho Bash, hook nhận input tương tự:

```json
{
  "session_id": "abc123",
  "transcript_path": "/home/user/.claude/projects/.../transcript.jsonl",
  "cwd": "/home/user/taskflow-ai",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test"
  }
}
```

File path: input này không phải file bạn tạo; nó là payload Claude Code truyền vào script qua `stdin`.

Mục đích: script dùng `tool_name`, `tool_input.command`, `tool_input.file_path`, `cwd`, `session_id` để quyết định.

Cách test: trong script hook, tạm log payload đã redacted vào `.claude/logs/hook-input.sample.jsonl`, rồi xóa log sau khi hiểu schema. Không log payload thật lâu dài nếu nó có thể chứa secret.

Edge cases: mỗi tool có `tool_input` khác nhau. `Bash` có `command`; `Edit` và `Write` có `file_path`; `MultiEdit` cũng có `file_path` nhưng khác shape về edits. Script phải dùng fallback như `.tool_input.file_path // empty` thay vì giả định field luôn tồn tại.

### Matcher và `if`

`matcher` lọc hook theo tool hoặc source. Với `PreToolUse` và `PostToolUse`, matcher thường là tên tool:

```json
{
  "matcher": "Edit|Write|MultiEdit",
  "hooks": [
    {
      "type": "command",
      "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/format-after-edit.sh",
      "args": [],
      "timeout": 20
    }
  ]
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: hook chạy sau các tool edit/write.

Cách test: yêu cầu Claude Code sửa một file `.ts` nhỏ, rồi kiểm tra formatter log.

Edge cases: matcher quá rộng như `"*"` làm hook chạy trên mọi tool, dễ chậm và khó debug. Nếu dùng `if`, hãy coi nó là lớp lọc phụ, không phải lớp bảo mật duy nhất.

Claude Code hỗ trợ filter `if` trong hook để thu hẹp theo cú pháp permission rule, ví dụ:

```json
{
  "type": "command",
  "if": "Bash(rm *)",
  "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm-rf.sh",
  "args": [],
  "timeout": 5
}
```

Rủi ro: nếu Claude Code version cũ không hỗ trợ `if` hoặc cú pháp không khớp như bạn nghĩ, hook có thể chạy nhiều hơn dự kiến. Vì vậy script vẫn phải tự validate input.

### Exit code và output

Với command hook:

| Exit code | Ý nghĩa thực tế | Dùng khi |
| --- | --- | --- |
| `0` | Hook chạy thành công; Claude Code tiếp tục. Tùy event, stdout có thể được hiển thị hoặc đưa vào context. | Log thành công, format thành công, không có vi phạm |
| `2` | Blocking error ở event hỗ trợ block; stderr được đưa lại cho Claude làm feedback. | Chặn `rm -rf`, chặn prompt chứa secret, chặn sửa file protected |
| Khác `0`/`2` | Lỗi hook không block trong phần lớn event, nhưng được log/debug. | Bug trong hook; cần sửa script |

Với `PreToolUse`, exit `2` là cách đơn giản để chặn tool call. Nếu cần kiểm soát tinh hơn như allow/deny/ask/defer hoặc sửa `tool_input`, dùng JSON `hookSpecificOutput.permissionDecision` và exit `0`; không trộn JSON control với exit `2` vì Claude Code chỉ parse JSON khi hook thành công. Với `PostToolUse`, hành động tool đã xảy ra, nên exit `2` chỉ gửi stderr làm feedback cho Claude, không undo được file edit hoặc command đã chạy. Nếu cần ngăn việc xảy ra, đặt rule ở `PreToolUse`.

### Timeout

Command hook, HTTP hook và MCP tool hook thường có timeout mặc định `600` giây; riêng `UserPromptSubmit` hạ default của các loại này xuống `30` giây. Prompt hook mặc định `30` giây, agent hook mặc định `60` giây. Các default này đủ để tránh treo vô hạn, nhưng trong project thật không nên dựa vào default vì session sẽ bị chậm hoặc khó hiểu khi hook kẹt. Hãy đặt timeout ngắn theo mục đích:

- Block command: `3-5` giây.
- Log activity: `3-5` giây.
- Formatter sau edit: `15-30` giây cho file đơn lẻ, không format cả repo.
- SessionStart context: `5-10` giây.

Hook càng lâu, Claude Code session càng chậm vì hook đồng bộ sẽ block Claude cho tới khi hoàn tất. Claude Code có hỗ trợ `async` cho command hook, nhưng async hook không thể block hoặc điều khiển quyết định; dùng async cho job quan sát dài, không dùng cho safety gate. Hook formatter chạy `npm run format` trên toàn repo sau mỗi edit là ví dụ tệ: nó vừa tốn thời gian, vừa có thể sửa rất nhiều file ngoài scope, vừa làm diff khó review.

## 4. Step-by-step thực hành

Mục tiêu thực hành: trong project `taskflow-ai`, tạo 3 hook local:

1. `PreToolUse` chặn `rm -rf`.
2. `PostToolUse` chạy formatter sau khi Claude Code sửa file.
3. `PostToolUse` ghi log Bash command đã redacted.

Tất cả lab dùng `.claude/settings.local.json` để tránh commit nhầm hook thử nghiệm. Nếu team muốn dùng chung, review xong mới copy phần ổn định sang `.claude/settings.json`.

### Bước 1: Kiểm tra trạng thái repo và tool cần có

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này hiển thị working tree dạng ngắn. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu repo có thay đổi của worker khác, việc tạo hook hoặc format sau edit có thể làm diff chồng lên công việc của họ.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --version
```

Lệnh này in version Claude Code đang dùng. Output kỳ vọng là version hiện tại của Claude Code CLI. Rủi ro thấp; nếu version quá cũ, field như `if` có thể không hoạt động như tài liệu mới, nên script hook phải tự kiểm tra input.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
jq --version
```

Lệnh này kiểm tra `jq`, tool dùng để đọc JSON input của hook. Output kỳ vọng giống `jq-1.6` hoặc `jq-1.7`. Rủi ro thấp; nếu chưa có `jq`, đừng để Claude tự cài bằng command global, hãy cài theo quy trình máy dev hoặc dùng script Node/PowerShell tương đương.

### Bước 2: Tạo thư mục hook local

Chạy trong thư mục gốc `taskflow-ai`:

```bash
mkdir -p .claude/hooks .claude/logs
```

Lệnh này tạo thư mục chứa script hook và log local. Output kỳ vọng thường rỗng. Rủi ro: tạo thư mục trong repo; hãy đảm bảo `.claude/logs/` không bị commit nếu log có metadata nhạy cảm.

Nếu dùng PowerShell thay vì Bash, chạy ở root `taskflow-ai`:

```powershell
New-Item -ItemType Directory -Force .claude/hooks, .claude/logs
```

Lệnh này làm cùng việc trên Windows PowerShell. Output kỳ vọng là thông tin directory được tạo hoặc đã tồn tại. Rủi ro tương tự: không commit log local.

### Bước 3: Tạo hook chặn `rm -rf`

Tạo file `taskflow-ai/.claude/hooks/block-rm-rf.sh` bằng editor hoặc yêu cầu Claude Code tạo file đúng nội dung sau:

```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')"

if [[ "$COMMAND" =~ (^|[[:space:];\|\&])rm[[:space:]] ]] && \
   { [[ "$COMMAND" =~ -[A-Za-z]*r[A-Za-z]*f ]] || \
     [[ "$COMMAND" =~ -[A-Za-z]*f[A-Za-z]*r ]] || \
     { [[ "$COMMAND" =~ -[A-Za-z]*r ]] && [[ "$COMMAND" =~ -[A-Za-z]*f ]]; }; }; then
  echo "Blocked by taskflow-ai hook: rm -rf style command is not allowed. Use a narrow, reviewed cleanup command instead." >&2
  exit 2
fi

exit 0
```

File path: `taskflow-ai/.claude/hooks/block-rm-rf.sh`.

Mục đích: đọc command Claude Code định chạy, phát hiện command dạng `rm -rf`, `rm -fr`, `rm -r -f` hoặc biến thể flag gộp, rồi block bằng exit `2`.

Cách test: sau khi cấu hình settings, yêu cầu Claude Code chạy command giả lập nguy hiểm trong repo sandbox. Hook phải trả stderr "Blocked by taskflow-ai hook..." và tool call không được thực thi.

Edge cases: script này không phát hiện mọi command destructive, ví dụ `find . -delete`, `python -c '...'`, alias shell hoặc script tự xóa file. Vì vậy vẫn cần permission `deny`, human review và rule không chạy cleanup rộng.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
chmod +x .claude/hooks/block-rm-rf.sh
```

Lệnh này cấp quyền execute cho script hook trên Unix/macOS/Linux/Git Bash. Output kỳ vọng rỗng. Rủi ro thấp, nhưng không làm script an toàn hơn; quyền execute chỉ cho phép Claude Code chạy script.

Tạo hoặc cập nhật `taskflow-ai/.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(rm *)",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm-rf.sh",
            "args": [],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: đăng ký hook trước Bash tool. `matcher: "Bash"` lọc theo tool; `if: "Bash(rm *)"` lọc thêm theo command; script là lớp kiểm tra thật.

Cách test: chạy `claude --debug-file .claude/logs/hooks-debug.log` ở root repo, sau đó yêu cầu Claude chạy một command an toàn và một command `rm -rf tmp`. Xem debug log để xác nhận hook nào matched.

Edge cases: đây là JSON, không được có comment hoặc trailing comma. Dấu nháy trong `command` phải escape đúng. Nếu file JSON sai, Claude Code có thể không load settings hoặc báo lỗi hook.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
jq empty .claude/settings.local.json
```

Lệnh này validate JSON settings. Output kỳ vọng rỗng và exit code `0`. Rủi ro thấp; nếu fail, sửa JSON trước khi mở Claude Code.

### Bước 4: Tạo hook formatter sau edit

Tạo file `taskflow-ai/.claude/hooks/format-after-edit.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
FILE_PATH="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

case "$FILE_PATH" in
  *.ts|*.tsx|*.js|*.jsx|*.json|*.md|*.css)
    ;;
  *)
    exit 0
    ;;
esac

cd "$PROJECT_DIR"

if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

if [[ -x "node_modules/.bin/prettier" ]]; then
  "node_modules/.bin/prettier" --write "$FILE_PATH" >/dev/null
  echo "Formatted $FILE_PATH with local Prettier"
else
  echo "Skipped formatter: local node_modules/.bin/prettier not found" >&2
fi
```

File path: `taskflow-ai/.claude/hooks/format-after-edit.sh`.

Mục đích: sau khi Claude Code sửa một file, format đúng file đó nếu extension nằm trong allowlist và project đã có local Prettier.

Cách test: yêu cầu Claude Code sửa một file `.ts` nhỏ, rồi chạy `git diff` để xem file đã format. Kiểm tra `.claude/logs/hooks-debug.log` nếu hook không chạy.

Edge cases: script cố tình không chạy `npx prettier` vì `npx` có thể download package nếu dependency chưa có. Script cũng không chạy `npm run format` toàn repo để tránh sửa nhiều file ngoài scope.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
chmod +x .claude/hooks/format-after-edit.sh
```

Lệnh này cấp quyền execute cho formatter hook. Output kỳ vọng rỗng. Rủi ro: hook sẽ có quyền chạy formatter local, nên script phải giới hạn extension và file path.

Cập nhật `taskflow-ai/.claude/settings.local.json` để thêm `PostToolUse`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(rm *)",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm-rf.sh",
            "args": [],
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/format-after-edit.sh",
            "args": [],
            "timeout": 20
          }
        ]
      }
    ]
  }
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: chạy formatter sau khi Claude Code dùng tool sửa file.

Cách test: validate JSON bằng `jq empty .claude/settings.local.json`, mở Claude Code, yêu cầu chỉnh một file `.ts`, kiểm tra debug log và diff.

Edge cases: `PostToolUse` xảy ra sau edit, nên formatter có thể tạo diff bổ sung. Nếu formatter làm thay đổi quá nhiều, dừng và đổi script để chỉ format file vừa sửa hoặc disable hook.

### Bước 5: Tạo hook ghi log Bash command

Tạo file `taskflow-ai/.claude/hooks/log-bash-command.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG_DIR="$PROJECT_DIR/.claude/logs"
LOG_FILE="$LOG_DIR/command-log.jsonl"

mkdir -p "$LOG_DIR"

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""')"
SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // "unknown"')"
CWD_VALUE="$(printf '%s' "$INPUT" | jq -r '.cwd // ""')"
EVENT_NAME="$(printf '%s' "$INPUT" | jq -r '.hook_event_name // ""')"

REDACTED_COMMAND="$(printf '%s' "$COMMAND" | sed -E 's/((api[_-]?key|token|password|passwd|secret|authorization)=)[^[:space:]]+/\1<redacted>/Ig')"

jq -nc \
  --arg ts "$(date -Iseconds)" \
  --arg session_id "$SESSION_ID" \
  --arg cwd "$CWD_VALUE" \
  --arg event "$EVENT_NAME" \
  --arg command "$REDACTED_COMMAND" \
  '{ts:$ts, session_id:$session_id, cwd:$cwd, event:$event, command:$command}' \
  >> "$LOG_FILE"

exit 0
```

File path: `taskflow-ai/.claude/hooks/log-bash-command.sh`.

Mục đích: append một dòng JSONL cho mỗi Bash tool call sau khi chạy xong, đủ audit nhưng không log stdout/stderr hoặc full transcript.

Cách test: mở Claude Code, yêu cầu chạy `pwd` hoặc `git status --short`, sau đó xem `.claude/logs/command-log.jsonl`.

Edge cases: redaction bằng regex không hoàn hảo. Không log toàn bộ prompt, `.env`, header, cookie hoặc transcript. Nếu command chứa secret ở dạng khác, log vẫn có thể leak; vì vậy log file phải local và không commit.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
chmod +x .claude/hooks/log-bash-command.sh
```

Lệnh này cấp quyền execute cho log hook. Output kỳ vọng rỗng. Rủi ro: hook có quyền ghi log vào repo; cần `.gitignore` hoặc quy ước không commit log.

Cập nhật `PostToolUse` để có cả formatter và logger:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(rm *)",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm-rf.sh",
            "args": [],
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/format-after-edit.sh",
            "args": [],
            "timeout": 20
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/log-bash-command.sh",
            "args": [],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: kết hợp 3 guardrail local: block trước Bash nguy hiểm, format sau edit, log sau Bash.

Cách test: validate JSON, mở Claude Code với debug file, chạy command an toàn, sửa file nhỏ và thử command bị block.

Edge cases: thứ tự hook trong cùng event có thể ảnh hưởng workflow nếu script này phụ thuộc output script khác. Không thiết kế hook phụ thuộc nhau trừ khi thật cần.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
jq empty .claude/settings.local.json
```

Lệnh này validate JSON sau khi merge nhiều hook. Output kỳ vọng rỗng. Rủi ro thấp; nếu JSON lỗi, Claude Code không load đúng hook.

### Bước 6: Mở Claude Code với debug log

Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --debug-file .claude/logs/hooks-debug.log
```

Lệnh này mở Claude Code và ghi debug log vào file local. Output kỳ vọng là Claude Code session sẵn sàng. Rủi ro: debug log có thể chứa command, path, stderr/stdout của hook; không commit hoặc chia sẻ nếu có dữ liệu nhạy cảm.

Trong Claude Code, dùng slash command:

```text
/hooks
```

Lệnh slash này hiển thị/cấu hình hook đang load trong Claude Code. Output kỳ vọng là danh sách hook theo event hoặc UI quản lý hook. Rủi ro thấp, nhưng nếu nhiều scope cùng khai báo hook, cần xem kỹ hook đến từ file nào.

Prompt test command an toàn:

```text
Hãy chạy `pwd` và `git status --short` trong repo taskflow-ai. Không sửa file.
Sau đó tóm tắt command đã chạy.
```

Kỳ vọng: command chạy bình thường, `log-bash-command.sh` ghi log.

Prompt test block:

```text
Hãy thử chạy command `rm -rf tmp/day-12-hook-test` để xác nhận hook safety.
Nếu bị block, hãy giải thích vì sao và đề xuất command cleanup an toàn hơn nhưng chưa chạy.
```

Kỳ vọng: `PreToolUse` hook block tool call, Claude nhận feedback từ stderr. Rủi ro: không dùng path thật có dữ liệu; dù hook đang chặn, test command vẫn nên dùng path sandbox.

Prompt test formatter:

```text
Hãy tạo hoặc sửa một file TypeScript nhỏ trong phạm vi branch hiện tại để kiểm tra formatter hook.
Chỉ sửa file test/sandbox nếu project đã có, không đụng business logic.
Sau khi edit, báo file đã sửa và không commit.
```

Kỳ vọng: `PostToolUse` hook chạy formatter cho file vừa sửa. Rủi ro: formatter có thể làm đổi style nhiều dòng nếu file đang chưa format; review `git diff` trước khi giữ lại.

### Bước 7: Debug khi hook làm workflow khó hiểu

Chạy trong thư mục gốc `taskflow-ai`:

```bash
tail -n 80 .claude/logs/hooks-debug.log
```

Lệnh này xem 80 dòng cuối debug log. Output kỳ vọng có event, matcher, command hook, exit code, stdout/stderr. Rủi ro: log có thể chứa thông tin nhạy cảm; không paste toàn bộ lên chat nếu chưa redact.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
tail -n 20 .claude/logs/command-log.jsonl
```

Lệnh này xem 20 command gần nhất mà Bash log hook ghi. Output kỳ vọng là JSONL gồm `ts`, `session_id`, `cwd`, `event`, `command`. Rủi ro: command có thể chứa secret nếu redaction không bắt được; kiểm tra trước khi chia sẻ.

Nếu cần disable toàn bộ hook local tạm thời, tạo hoặc sửa `taskflow-ai/.claude/settings.local.json`:

```json
{
  "disableAllHooks": true
}
```

File path: `taskflow-ai/.claude/settings.local.json`.

Mục đích: tắt toàn bộ hook trong scope local để khôi phục workflow khi hook block nhầm hoặc timeout liên tục.

Cách test: mở lại Claude Code và chạy `/hooks`; danh sách hook local không còn thực thi.

Edge cases: nếu project shared hoặc managed settings cũng có hook, cần kiểm tra precedence bằng `/hooks` và debug log. Khi bật lại, xóa `disableAllHooks` hoặc restore settings trước đó.

Không dùng command destructive để "debug hook", ví dụ:

```bash
git reset --hard
git clean -fd
rm -rf .claude
docker compose down -v
```

Các lệnh này chạy ở root repo hoặc môi trường dev và có thể xóa thay đổi của bạn, worker khác, hook config hoặc database volume. Output kỳ vọng không quan trọng vì không nên chạy trong bài này. Nếu cần rollback, rollback từng file đã review.

## 5. Prompt mẫu nên dùng

### Prompt khám phá hook hiện có

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát cấu hình Claude Code hook hiện có.

Ràng buộc:
- Chỉ đọc file, chưa sửa.
- Kiểm tra các file .claude/settings.json và .claude/settings.local.json nếu tồn tại.
- Liệt kê event, matcher, command, timeout, scope và rủi ro từng hook.
- Không đọc hoặc in secret, .env, token, command log đầy đủ.
- Nếu thấy hook destructive hoặc matcher quá rộng, phân loại Blocker/Should fix/Nice to have.
```

### Prompt lập plan tạo hook safety

```text
Lập plan tạo hook local cho taskflow-ai để:
1. Block rm -rf trước khi Bash tool chạy.
2. Format file sau Edit/Write/MultiEdit.
3. Log Bash command đã redacted.

Yêu cầu:
- Dùng .claude/settings.local.json, chưa promote sang settings.json.
- Mỗi hook có file script riêng trong .claude/hooks.
- Matcher hẹp, timeout rõ, script tự validate JSON input.
- Không chạy command destructive, không format toàn repo, không log secret.
- Chờ tôi approve trước khi tạo hoặc sửa file.
```

### Prompt implement hook

```text
Implement hook theo plan đã duyệt.

Giới hạn:
- Chỉ tạo/sửa file trong .claude/hooks và .claude/settings.local.json.
- Không sửa README, source business logic, package.json, lockfile hoặc .env.
- Không chạy npm install, git add, git commit, git reset, git clean, rm, docker volume command hoặc migration.
- Mọi script phải set -euo pipefail, đọc JSON từ stdin, dùng fallback khi field thiếu.
- Log không được chứa secret, token, cookie, authorization header, password hoặc raw prompt.
- Sau khi xong, báo file đã tạo, hook event/matcher/timeout và command test an toàn.
```

### Prompt review hook

```text
Review diff hook hiện tại như senior developer, không sửa file.

Tập trung:
- Scope có đúng local/project/user không.
- Matcher có quá rộng không.
- JSON escaping trong settings có đúng không.
- timeout có hợp lý không.
- Hook có chạy command destructive hoặc format toàn repo không.
- Log có thể leak secret không.
- Có cách debug/disable rõ không.

Kết luận theo format: Blocker, Should fix, Nice to have, Test gaps.
```

### Prompt test hook

```text
Hãy giúp tôi test hook Day 12 bằng các bước an toàn.

Yêu cầu:
- Trước hết kiểm tra /hooks và debug log.
- Chạy command an toàn như pwd hoặc git status --short.
- Thử command rm -rf chỉ trên path sandbox và kỳ vọng bị block.
- Sửa một file sandbox nhỏ để kiểm tra formatter.
- Không commit, không xóa file, không chạy cleanup destructive.
- Nếu test fail, phân tích nguyên nhân trước, chưa sửa.
```

## 6. Trade-offs

Hook giúp automation nhất quán hơn prompt vì nó chạy tự động tại đúng event. Nhưng chính vì tự động, hook cũng dễ tạo side effect không ai nhớ đã bật. Một formatter hook chạy sau mọi edit có thể tiết kiệm thời gian, nhưng nếu nó format cả repo, reviewer sẽ thấy diff lớn và khó phân biệt thay đổi logic với thay đổi style.

`PreToolUse` là nơi tốt nhất để block hành động nguy hiểm. Trade-off là block nhầm làm Claude Code bị kẹt. Vì vậy matcher phải hẹp, message lỗi phải actionable, và luôn có cách disable/debug.

`PostToolUse` phù hợp cho log và formatter vì tool đã chạy. Trade-off là không thể ngăn hành động đã xảy ra. Nếu bạn dùng `PostToolUse` để phát hiện command nguy hiểm, bạn đã quá muộn.

`UserPromptSubmit` hữu ích để chặn prompt có secret hoặc thêm context nhỏ. Trade-off là prompt của user có thể chứa dữ liệu nhạy cảm; nếu hook log nguyên prompt, bạn vừa tạo thêm điểm rò rỉ.

`SessionStart` tiện để nạp context hoặc ghi audit, nhưng không nên chạy setup nặng. Một hook start session mà gọi dependency install, build hoặc database introspection sẽ làm mọi session chậm và khó phân biệt lỗi môi trường với lỗi Claude Code.

Project shared hooks giúp team có guardrail đồng nhất, nhưng yêu cầu review kỹ hơn local hook. Local hook nhanh để thử nghiệm, nhưng không bảo vệ đồng đội. User global hook tiện cho thói quen cá nhân, nhưng có thể phá repo khác nếu matcher hoặc path quá project-specific.

## 7. Best practices

- Dùng `.claude/settings.local.json` cho lab và thử nghiệm; chỉ commit `.claude/settings.json` khi script đã được review như production code.
- Matcher càng hẹp càng tốt. Tránh `"*"` nếu không có lý do rõ.
- Dùng `if` để giảm số lần hook chạy, nhưng script vẫn phải tự validate input.
- Luôn đặt `timeout` ngắn theo use case. Hook block/log không nên chạy quá vài giây.
- Tách script ra file riêng thay vì nhồi pipeline dài trong JSON settings; JSON escaping sai là nguồn lỗi phổ biến.
- Validate settings bằng `jq empty .claude/settings.local.json`.
- Script hook phải chịu được field thiếu: dùng `.tool_input.command // ""`, `.tool_input.file_path // empty`.
- Không log secret, token, cookie, authorization header, password, raw `.env`, raw prompt hoặc full transcript.
- Không chạy command destructive trong hook: không `rm`, không `git reset`, không `git clean`, không `docker compose down -v`, không migration destructive.
- Formatter hook chỉ format file vừa sửa và extension trong allowlist. Không format toàn repo sau mỗi edit.
- Log hook chỉ append metadata đã redacted. Log file phải local, không commit.
- Message block phải nói rõ vì sao bị block và gợi ý cách làm an toàn hơn.
- Có runbook debug: `/hooks`, `claude --debug`, `claude --debug-file`, kiểm tra exit code/stdout/stderr, disable bằng `disableAllHooks`.
- Hook không thay thế permission. Với command chắc chắn nguy hiểm, dùng cả permission `deny` và hook nếu cần rule động.
- Review hook script như review code security: input parsing, quoting, path traversal, command injection, timeout, log retention.

## 8. Performance / cost / context

Hook không trực tiếp tiêu token như prompt dài, nhưng output của hook có thể đi vào transcript hoặc context tùy event. Nếu hook in quá nhiều stdout, Claude có thêm noise và session khó đọc. Với `UserPromptSubmit` và `SessionStart`, stdout có thể trở thành context cho Claude; vì vậy chỉ output nội dung ngắn, có giá trị.

Hook ảnh hưởng performance theo thời gian chạy:

- `PreToolUse` chạy trước tool nên làm mọi command matched bị delay.
- `PostToolUse` chạy sau edit nên formatter chậm sẽ làm Claude Code có vẻ "đơ".
- `UserPromptSubmit` chạy trước mỗi prompt nên logic phức tạp làm mọi lượt chat chậm.
- `SessionStart` chạy khi mở/resume session nên command nặng làm startup chậm.

Cách tối ưu:

- Dùng matcher và `if` hẹp để hook không chạy vô ích.
- Dùng script local, deterministic, không gọi network.
- Formatter chỉ chạy trên file vừa sửa; tránh `npm run format` toàn repo.
- Log append JSONL đơn giản, không parse transcript lớn.
- Timeout ngắn; nếu hook cần xử lý dài, cân nhắc chuyển sang job ngoài Claude Code thay vì blocking hook.
- Giữ stdout ngắn; log chi tiết vào file local nếu cần debug.
- Không để hook tạo output chứa diff dài hoặc test log dài; yêu cầu Claude tự chạy test có chủ đích khi cần.

Chi phí maintainability cũng đáng kể. Hook là automation ẩn, nên phải có tài liệu trong `CLAUDE.md` hoặc docs team: hook nào tồn tại, vì sao, cách debug, cách disable, ai owner. Nếu không, developer sẽ mất thời gian tìm vì sao Claude Code không chạy được command tưởng như bình thường.

## 9. Checklist cuối bài

- [ ] Tôi hiểu hook chạy theo event và nhận JSON input qua `stdin`.
- [ ] Tôi phân biệt được `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SessionStart`.
- [ ] Tôi biết chọn scope user/project/local và ưu tiên `.claude/settings.local.json` khi thử nghiệm.
- [ ] Tôi đã tạo hook chặn `rm -rf` bằng `PreToolUse` với matcher/if hẹp và exit `2`.
- [ ] Tôi đã tạo hook formatter sau edit, chỉ format file vừa sửa và extension allowlist.
- [ ] Tôi đã tạo hook log Bash command đã redacted vào file local.
- [ ] Tôi đã validate JSON settings bằng `jq empty`.
- [ ] Tôi đã đặt timeout cho từng hook.
- [ ] Tôi không log secret, prompt raw, `.env`, token, cookie, authorization header hoặc full transcript.
- [ ] Tôi biết dùng `/hooks`, `claude --debug-file`, hook log và `disableAllHooks` để debug/disable.
- [ ] Tôi không chạy command destructive trong hook.
- [ ] Tôi đã review diff và chắc chắn không chạm file ngoài phạm vi hook.

## 10. Bài tập

Bài cơ bản: trong `taskflow-ai`, tạo local hook `PreToolUse` chặn `rm -rf`. Dùng `.claude/settings.local.json`, script riêng trong `.claude/hooks`, timeout `5` giây. Test bằng command an toàn và command sandbox bị block. Nộp settings, script, debug log đã redacted và nhận xét vì sao `PostToolUse` không phù hợp để chặn command này.

Bài nâng cao: tạo `PostToolUse` formatter hook cho `Edit|Write|MultiEdit`. Script chỉ format extension `.ts`, `.tsx`, `.js`, `.jsx`, `.json`, `.md`, `.css` và chỉ dùng local `node_modules/.bin/prettier` nếu có. Nộp diff trước/sau khi Claude sửa một file sandbox, giải thích cách tránh formatter làm đổi cả repo.

Bài áp dụng team: tạo `PostToolUse` log hook cho Bash command. Log vào `.claude/logs/command-log.jsonl`, redacted token/password/secret, không log stdout/stderr/prompt/transcript. Nộp 3 dòng log mẫu đã kiểm tra không chứa secret, và đề xuất rule `.gitignore` hoặc retention.

Bài reflection: viết runbook 10 dòng cho team `taskflow-ai`: hook nào đang bật, scope, owner, cách debug, cách disable, command bị cấm, chính sách log, khi nào promote từ local sang project shared. Yêu cầu Claude Code review runbook ở chế độ read-only trước khi đưa vào team docs.
