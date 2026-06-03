# Exercise — Day 12

## Bài 1 — Cơ bản

Mục tiêu: tạo `PreToolUse` hook local để chặn `rm -rf` trong project `taskflow-ai`.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.

2. Kiểm tra working tree:

```bash
git status --short
```

Lệnh này chạy ở root repo để xem file đang thay đổi. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có thay đổi của worker khác, đừng để hook formatter/logging làm nhiễu diff của họ.

3. Kiểm tra Claude Code và `jq`:

```bash
claude --version
```

Lệnh này chạy ở root repo hoặc terminal bất kỳ để xem version Claude Code. Output kỳ vọng là version hiện tại. Rủi ro thấp; nếu version cũ, kiểm tra kỹ field `if`.

```bash
jq --version
```

Lệnh này kiểm tra tool parse JSON cho hook script. Output kỳ vọng là `jq-...`. Rủi ro thấp; nếu thiếu `jq`, dùng script Node/PowerShell thay thế hoặc cài theo quy trình máy dev, không để Claude tự chạy cài đặt global.

4. Tạo thư mục hook local:

```bash
mkdir -p .claude/hooks .claude/logs
```

Lệnh này chạy ở root `taskflow-ai` để tạo nơi đặt script và log. Output kỳ vọng rỗng. Rủi ro: `.claude/logs` không được commit nếu chứa log thật.

5. Tạo file `taskflow-ai/.claude/hooks/block-rm-rf.sh`:

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

File path: `.claude/hooks/block-rm-rf.sh`.

Mục đích: block command dạng `rm -rf` bằng exit `2` trước khi Bash tool chạy.

Cách test: dùng Claude Code thử command sandbox có `rm -rf`; hook phải block. Không test trên path thật có dữ liệu.

Edge cases: không bắt mọi command destructive như `find -delete`; đây là guardrail bổ sung, không thay thế review và permission deny.

6. Cấp quyền execute:

```bash
chmod +x .claude/hooks/block-rm-rf.sh
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng rỗng. Rủi ro thấp; nếu dùng Windows thuần không có Bash, cần PowerShell script tương đương.

7. Tạo `taskflow-ai/.claude/settings.local.json`:

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

File path: `.claude/settings.local.json`.

Mục đích: cấu hình hook local cho repo, không commit vào team config.

Cách test: validate JSON rồi mở Claude Code với debug log.

Edge cases: JSON không có comment/trailing comma; dùng `${CLAUDE_PROJECT_DIR}` và `args: []` để tránh lỗi shell quoting khi project path có khoảng trắng.

8. Validate settings:

```bash
jq empty .claude/settings.local.json
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng rỗng. Rủi ro thấp; nếu có lỗi, sửa JSON trước khi mở Claude Code.

9. Mở Claude Code với debug:

```bash
claude --debug-file .claude/logs/hooks-debug.log
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là session Claude Code sẵn sàng. Rủi ro: debug log có thể chứa command/path; không commit.

10. Trong Claude Code, test bằng prompt:

```text
Hãy chạy `pwd` để xác nhận command an toàn vẫn chạy.
Sau đó thử chạy `rm -rf tmp/day-12-hook-test` để xác nhận hook block command nguy hiểm.
Không sửa file và không chạy cleanup khác.
```

Kết quả cần nộp: nội dung settings, nội dung script, đoạn debug log đã redacted chứng minh hook matched, và giải thích vì sao exit `2` được dùng.

## Bài 2 — Thực tế

Mục tiêu: tạo `PostToolUse` hook chạy formatter sau khi Claude Code sửa file trong `taskflow-ai`.

Yêu cầu:

1. Từ trạng thái sau Bài 1, tạo file `taskflow-ai/.claude/hooks/format-after-edit.sh`:

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

File path: `.claude/hooks/format-after-edit.sh`.

Mục đích: format file vừa được Claude Code sửa, chỉ với extension allowlist, chỉ dùng local Prettier.

Cách test: cho Claude Code sửa một file sandbox `.ts` hoặc `.md`, rồi kiểm tra diff.

Edge cases: nếu `node_modules/.bin/prettier` chưa tồn tại, hook skip thay vì dùng `npx` để tránh download bất ngờ.

2. Cấp quyền execute:

```bash
chmod +x .claude/hooks/format-after-edit.sh
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng rỗng. Rủi ro: hook sẽ chạy formatter tự động, nên phải giữ script hẹp.

3. Cập nhật `.claude/settings.local.json` để có thêm `PostToolUse`:

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

File path: `.claude/settings.local.json`.

Mục đích: chạy formatter sau edit/write/multiedit.

Cách test: validate JSON và dùng `/hooks` để xem event `PostToolUse`.

Edge cases: `PostToolUse` không undo edit; nếu formatter gây diff lớn, phải rollback theo file hoặc disable hook rồi sửa.

4. Validate settings:

```bash
jq empty .claude/settings.local.json
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng rỗng. Rủi ro thấp.

5. Mở Claude Code:

```bash
claude --debug-file .claude/logs/hooks-debug.log
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là session sẵn sàng. Rủi ro: debug log có thể chứa file path và hook stderr.

6. Gửi prompt test formatter:

```text
Hãy tạo hoặc sửa một file sandbox nhỏ để kiểm tra formatter hook.

Ràng buộc:
- Chỉ dùng file trong test/sandbox hoặc thư mục tạm đã tồn tại trong taskflow-ai.
- Nếu chưa có nơi sandbox, hãy đề xuất path trước, chưa tạo.
- Không sửa business logic.
- Sau edit, báo file đã sửa, hook formatter có chạy không, và command test/read-only tôi nên chạy.
```

7. Review diff:

```bash
git diff --stat
```

Lệnh này chạy ở root `taskflow-ai` để xem phạm vi thay đổi. Output kỳ vọng chỉ có file sandbox và hook config/script. Rủi ro: `--stat` không cho thấy logic, chỉ phát hiện patch rộng bất thường.

```bash
git diff
```

Lệnh này chạy ở root `taskflow-ai` để xem patch chi tiết. Output kỳ vọng không có business logic bị chạm ngoài bài. Rủi ro: diff có thể chứa log hoặc formatting noise; không commit log.

Kết quả cần nộp: settings đã cập nhật, script formatter, diff summary và phân tích vì sao hook không format toàn repo.

## Bài 3 — Nâng cao

Mục tiêu: tạo `PostToolUse` hook log Bash command đã redacted, phục vụ audit/debug mà không leak secret.

Yêu cầu:

1. Tạo file `taskflow-ai/.claude/hooks/log-bash-command.sh`:

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

File path: `.claude/hooks/log-bash-command.sh`.

Mục đích: log metadata của Bash tool call dưới dạng JSONL. Không log stdout/stderr/prompt/transcript.

Cách test: chạy command an toàn qua Claude Code, sau đó xem `.claude/logs/command-log.jsonl`.

Edge cases: regex redaction không hoàn hảo; command có secret dạng khác vẫn có thể leak. Không commit log.

2. Cấp quyền execute:

```bash
chmod +x .claude/hooks/log-bash-command.sh
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng rỗng. Rủi ro: hook ghi log local; cần kiểm soát `.gitignore` và log retention.

3. Cập nhật `.claude/settings.local.json`:

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

File path: `.claude/settings.local.json`.

Mục đích: kết hợp block hook, formatter hook và command log hook.

Cách test: validate JSON, mở Claude Code debug, chạy command an toàn.

Edge cases: nhiều hook cùng event không nên phụ thuộc lẫn nhau; mỗi hook phải tự đủ dữ liệu và fail an toàn.

4. Validate settings:

```bash
jq empty .claude/settings.local.json
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng rỗng. Rủi ro thấp.

5. Test logging bằng Claude Code:

```text
Hãy chạy `pwd` và `git status --short`.
Không sửa file.
Sau đó cho biết command nào đã chạy.
```

6. Xem log:

```bash
tail -n 5 .claude/logs/command-log.jsonl
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là 5 dòng JSONL gần nhất, có `ts`, `session_id`, `cwd`, `event`, `command`. Rủi ro: log có thể chứa secret nếu redaction chưa đủ; kiểm tra và redact trước khi nộp.

7. Test redaction bằng prompt an toàn:

```text
Hãy mô phỏng một command echo chứa token giả: `echo token=fake-value-for-redaction-test`.
Không dùng token thật.
Sau đó kiểm tra log command có redacted không.
```

Kỳ vọng: log command chứa `token=<redacted>` hoặc ít nhất không chứa secret thật. Rủi ro: không bao giờ dùng secret thật để test redaction.

Kết quả cần nộp: script logger, settings, 2-3 dòng log mẫu đã redacted, và chính sách không commit `.claude/logs/`.

## Bài 4 — Review & Reflection

Mục tiêu: review hook như code production và viết runbook debug cho team `taskflow-ai`.

Yêu cầu:

1. Yêu cầu Claude Code review hook read-only:

```text
Review hook Day 12 hiện tại như senior developer, không sửa file.

Tập trung:
- Hook nào thuộc PreToolUse/PostToolUse/UserPromptSubmit/SessionStart nếu có.
- Scope local/project/user có phù hợp không.
- Matcher và if có quá rộng không.
- JSON escaping có đúng không.
- timeout có hợp lý không.
- Script có thể leak secret không.
- Hook có chạy command destructive hoặc format toàn repo không.
- Có cách debug/disable rõ không.

Kết luận theo format: Blocker, Should fix, Nice to have, Test gaps.
```

2. Kiểm tra debug log:

```bash
tail -n 80 .claude/logs/hooks-debug.log
```

Lệnh này chạy ở root `taskflow-ai` để xem hook gần nhất. Output kỳ vọng có hook command, exit status, stdout/stderr. Rủi ro: log có thể chứa thông tin nhạy cảm; redact trước khi đưa vào Claude.

3. Kiểm tra command log:

```bash
tail -n 20 .claude/logs/command-log.jsonl
```

Lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là JSONL đã redacted. Rủi ro: nếu thấy secret, dừng lại, xóa log local theo quy trình an toàn và sửa redaction trước khi dùng tiếp.

4. Viết runbook ngắn:

```text
Dựa trên hook Day 12, hãy viết runbook 10-15 dòng cho team taskflow-ai.

Runbook phải có:
- Hook đang bật và scope.
- Owner hoặc nơi review.
- Cách test an toàn.
- Cách debug bằng /hooks và claude --debug-file.
- Cách disable bằng disableAllHooks.
- Command bị cấm.
- Chính sách log không chứa secret.
- Khi nào được promote từ settings.local.json sang settings.json.
```

5. Thử disable local hook bằng cách thay `.claude/settings.local.json` thành:

```json
{
  "disableAllHooks": true
}
```

File path: `.claude/settings.local.json`.

Mục đích: xác nhận bạn có đường thoát khi hook block nhầm. Cách test: mở lại Claude Code, chạy `/hooks`, xác nhận hook local không execute. Edge cases: đừng commit settings này nếu team cần hook shared.

6. Restore settings hook sau khi test disable bằng editor hoặc Git theo file nếu file đã tracked. Nếu dùng Git rollback, chạy ở root `taskflow-ai` và chỉ với file bạn sở hữu:

```bash
git restore -- .claude/settings.local.json
```

Lệnh này rollback tracked local settings về trạng thái Git. Output kỳ vọng rỗng. Rủi ro: mất thay đổi chưa commit trong file đó; không dùng nếu file có thay đổi của người khác hoặc chưa tracked.

Kết quả cần nộp: review findings, runbook, bằng chứng biết disable/debug hook, và quyết định có promote hook nào sang project shared không.

## Tiêu chí hoàn thành

- Đã tạo hook `PreToolUse` chặn `rm -rf` bằng script riêng, matcher/if hẹp, timeout `5` giây.
- Đã tạo hook `PostToolUse` formatter chỉ format file vừa sửa và extension allowlist.
- Đã tạo hook `PostToolUse` log Bash command đã redacted vào `.claude/logs/command-log.jsonl`.
- Dùng `.claude/settings.local.json` cho lab, không tự promote sang `.claude/settings.json`.
- Settings JSON validate được bằng `jq empty`.
- Hook script đọc JSON từ `stdin`, dùng fallback khi field thiếu.
- Không hook nào chạy command destructive, install dependency, migration, reset Git hoặc format toàn repo.
- Log không chứa secret thật, prompt raw, `.env`, stdout/stderr dài hoặc transcript.
- Đã test bằng command an toàn và command sandbox bị block.
- Biết debug bằng `/hooks`, `claude --debug-file`, `hooks-debug.log`, `command-log.jsonl`.
- Biết disable bằng `disableAllHooks` và hiểu rủi ro khi disable.
- Có review read-only theo Blocker/Should fix/Nice to have/Test gaps.

## Gợi ý nếu bí

Nếu Claude Code không nhận hook:

```text
Hãy kiểm tra vì sao hook không load.
Chỉ đọc file.
Kiểm tra .claude/settings.local.json có valid JSON không, path command có đúng không, script có executable không, matcher có khớp event không.
Không sửa file cho đến khi phân loại nguyên nhân.
```

Nếu JSON settings lỗi:

```bash
jq empty .claude/settings.local.json
```

Lệnh này chạy ở root `taskflow-ai` để chỉ ra lỗi JSON. Output kỳ vọng khi lỗi là line/column. Rủi ro thấp; sửa JSON rồi chạy lại.

Nếu formatter không chạy:

```text
Formatter hook không chạy. Hãy phân tích debug log đã redacted.
Kiểm tra:
- PostToolUse có matched Edit/Write/MultiEdit không.
- tool_input.file_path có tồn tại không.
- file extension có nằm trong allowlist không.
- node_modules/.bin/prettier có tồn tại không.
- hook có timeout hoặc permission error không.
Chưa sửa file.
```

Nếu log có secret:

```text
Command log có nguy cơ chứa secret. Hãy đề xuất patch redaction tối thiểu.
Không in lại secret.
Không đọc .env.
Không sửa file cho đến khi tôi approve.
```

Nếu hook block nhầm:

```text
Hook block nhầm command an toàn. Hãy phân tích matcher, if và script regex.
Chưa sửa file.
Đề xuất test cases cho command nên block và command nên allow.
```

Nếu workflow bị kẹt:

```json
{
  "disableAllHooks": true
}
```

Đặt tạm trong `.claude/settings.local.json`, mở lại Claude Code, dùng `/hooks` kiểm tra. Rủi ro: tắt cả guardrail local; chỉ dùng để debug và bật lại sau.

## Đáp án tham khảo hoặc expected result

Kết quả tốt cho Bài 1:

- `.claude/settings.local.json` có `PreToolUse` matcher `Bash`, `if: Bash(rm *)`, command trỏ tới `block-rm-rf.sh` bằng `${CLAUDE_PROJECT_DIR}`, có `args: []`, timeout `5`.
- Script đọc `.tool_input.command // ""`, phát hiện `rm -rf` style, ghi message rõ ràng vào stderr và `exit 2`.
- Command `pwd` chạy bình thường.
- Command sandbox `rm -rf tmp/day-12-hook-test` bị block trước khi thực thi.

Ví dụ debug log mong đợi đã redacted:

```text
[DEBUG] Executing hooks for PreToolUse:Bash
[DEBUG] Executing hook command: <project>/.claude/hooks/block-rm-rf.sh with timeout 5000ms
[DEBUG] Hook command completed with status 2
```

Kết quả tốt cho Bài 2:

- `.claude/settings.local.json` có `PostToolUse` matcher `Edit|Write|MultiEdit`.
- `format-after-edit.sh` chỉ format extension allowlist và chỉ dùng local `node_modules/.bin/prettier`.
- Nếu local Prettier không có, hook skip và báo stderr ngắn; không chạy `npx` download package.
- `git diff --stat` không xuất hiện hàng loạt file do format toàn repo.

Kết quả tốt cho Bài 3:

- `log-bash-command.sh` ghi JSONL vào `.claude/logs/command-log.jsonl`.
- Mỗi dòng có `ts`, `session_id`, `cwd`, `event`, `command`.
- Command có `token=fake-value-for-redaction-test` được redacted.
- Log không chứa stdout/stderr, prompt raw, `.env`, transcript hoặc secret thật.

Ví dụ log mẫu:

```json
{"ts":"2026-05-14T10:20:30+07:00","session_id":"abc123","cwd":"/path/to/taskflow-ai","event":"PostToolUse","command":"git status --short"}
{"ts":"2026-05-14T10:21:10+07:00","session_id":"abc123","cwd":"/path/to/taskflow-ai","event":"PostToolUse","command":"echo token=<redacted>"}
```

Kết quả tốt cho Bài 4:

- Review phát hiện được ít nhất các rủi ro: matcher rộng, JSON escaping, timeout, formatter toàn repo, log leak secret, thiếu disable path.
- Runbook có cách debug bằng `/hooks` và `claude --debug-file`.
- Biết dùng `disableAllHooks` nhưng hiểu đây là giải pháp tạm.
- Có quyết định rõ:
  - `block-rm-rf` có thể promote sang `.claude/settings.json` sau team review.
  - formatter hook nên giữ local nếu team chưa thống nhất formatter.
  - command log hook nên giữ local hoặc có policy retention/redaction rõ trước khi share.
