# Document — Day 14

## Tóm tắt kiến thức

Subagent trong Claude Code là assistant chuyên biệt chạy trong context window riêng. Mục tiêu là tách vai trò và giảm nhiễu: planner lập kế hoạch, implementer sửa code, code reviewer tìm lỗi, test engineer tạo evidence, security auditor kiểm tra rủi ro bảo mật.

Vị trí:

```text
.claude/agents/<name>.md
~/.claude/agents/<name>.md
```

Project subagents trong `.claude/agents` nên commit nếu team dùng chung. User subagents trong `~/.claude/agents` phù hợp workflow cá nhân.

Ví dụ invoke:

```text
@"code-reviewer (agent)" review the current git diff. Do not edit files.
```

Nếu không dùng typeahead:

```text
@agent-code-reviewer review the current git diff. Do not edit files.
```

Subagent nên có tool scope tối thiểu. Reviewer thường chỉ cần `Read`, `Grep`, `Glob`, `Bash`; không cần `Edit`, `Write`, hoặc `MultiEdit`. Tester cần `Bash` để chạy test và đọc output. Theo cấu trúc frontmatter hiện hành, dùng `tools` như allowlist; nếu không khai báo `tools`, subagent có thể inherit nhiều tool hơn từ main conversation, gồm cả MCP tools. `Bash` không phải read-only tuyệt đối, nên team production nên dùng permission rules hoặc hook để chặn command destructive.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Subagents
├── Vì sao dùng?
│   ├── Tách context window
│   ├── Tách vai trò
│   ├── Giảm bias sau implementation
│   └── Scope tools theo allowlist
├── Nơi định nghĩa
│   ├── .claude/agents/<name>.md
│   └── ~/.claude/agents/<name>.md
├── Cách gọi
│   ├── Natural language: Use the code-reviewer agent...
│   ├── @ typeahead: @"code-reviewer (agent)"
│   ├── Manual mention: @agent-code-reviewer
│   └── Session-wide: claude --agent code-reviewer
├── Vai trò tốt
│   ├── planner
│   ├── code-reviewer
│   ├── test-engineer
│   └── security-auditor
├── Rủi ro
│   ├── Token/latency tăng
│   ├── Permission quá rộng
│   ├── Agent prompt mơ hồ
│   └── Tools allowlist quá rộng
└── Khi không nên dùng
    ├── Thay đổi nhỏ
    ├── Task một bước
    └── Không cần review độc lập
```

Luồng đề xuất:

```text
User request
  -> Main agent clarify scope
  -> Planner creates plan
  -> Main/implementer edits code
  -> code-reviewer reviews diff
  -> Main fixes accepted findings
  -> test-engineer runs targeted tests
  -> Main summarizes risk and merge decision
```

## Bảng so sánh

| Tiêu chí | Main agent | Subagent |
| --- | --- | --- |
| Context | Chứa toàn bộ cuộc trò chuyện chính | Context riêng |
| Vai trò | Điều phối, tổng hợp, sửa trực tiếp | Chuyên biệt |
| Tool access | Theo session chính | Có thể giới hạn riêng |
| Bias | Dễ bị ảnh hưởng bởi implementation trước đó | Ít hơn nếu prompt tốt |
| Chi phí | Ít overhead | Tốn thêm token/latency |
| Phù hợp | Task đơn giản, orchestration | Review, test, audit, planning |

| Agent | Khi dùng | Tools gợi ý | Không nên cho |
| --- | --- | --- | --- |
| `planner` | Trước feature lớn | Read, Grep, Glob | Edit, Write |
| `code-reviewer` | Sau implementation | Read, Grep, Glob, Bash | Write, Edit |
| `test-engineer` | Sau fix/feature | Read, Grep, Glob, Bash | Edit nếu chỉ validate |
| `security-auditor` | Auth, data, shell, secrets | Read, Grep, Glob, Bash | Write, Edit, tools ghi file |

## Lỗi thường gặp

1. `description` quá mơ hồ
`description: Helps with code` không đủ để Claude chọn đúng agent. Viết use case cụ thể.

2. Reviewer có quyền edit
Reviewer tự sửa code làm mất tính độc lập. Chặn `Write`, `Edit`, `MultiEdit`.

3. Cấp tools quá rộng cho agent chưa kiểm soát
Nếu reviewer hoặc auditor có `Write`, `Edit`, hoặc command shell không giới hạn, agent có thể vượt vai trò phân tích. Tránh trong lab.

4. Gọi quá nhiều subagents cho thay đổi nhỏ
Tốn token và thời gian, nhưng không tăng chất lượng.

5. Không yêu cầu output có cấu trúc
Prompt `what do you think?` thường cho review chung chung. Yêu cầu severity, file, failure mode, smallest fix.

6. Quên commit project subagents
Nếu team cần workflow chung mà không commit `.claude/agents`, mỗi người sẽ có agent khác nhau.

7. Không đặt đúng thư mục agent
Project agents nên đặt trong `.claude/agents/<name>.md` để Claude Code auto-discover trong project. User agents đặt trong `~/.claude/agents/<name>.md`.

8. Tạo file thủ công nhưng không restart Claude Code
Nếu không dùng `/agents` mà tự tạo file markdown, Claude Code có thể chưa load agent mới trong session hiện tại. Restart session rồi kiểm tra lại.

9. Dùng cú pháp `@code-reviewer` như text thường
Cú pháp chắc chắn hơn là chọn agent từ typeahead hoặc nhập thủ công `@agent-code-reviewer`. Nếu chỉ viết tên agent trong câu, Claude vẫn có thể tự quyết định có delegate hay không.

## Cách debug

Kiểm tra file agent:

```bash
ls .claude/agents
```

PowerShell:

```powershell
Get-ChildItem .claude/agents
```

Giải thích: chạy ở root `taskflow-ai`; lệnh chỉ liệt kê file agent, output kỳ vọng có `code-reviewer.md` và `test-engineer.md`; rủi ro thấp.

Trong Claude Code, dùng `/agents` để xem agent đã được nhận diện chưa. Nếu không thấy, restart Claude Code session.

Kiểm tra frontmatter:

```bash
sed -n '1,60p' .claude/agents/code-reviewer.md
```

PowerShell:

```powershell
Get-Content .claude/agents/code-reviewer.md -TotalCount 60
```

Giải thích: chạy ở root `taskflow-ai`; lệnh chỉ đọc 60 dòng đầu để kiểm tra YAML frontmatter; output kỳ vọng có `name`, `description`, `tools`, `model`; rủi ro thấp, nhưng không paste nội dung chứa secret vào chat nếu prompt agent vô tình ghi secret.

Nếu agent không chạy, gọi rõ:

```text
Use the code-reviewer subagent defined in .claude/agents/code-reviewer.md to review the current git diff. Do not edit files.
```

Nếu tester không chạy được test, kiểm tra `tools` có `Bash` không:

```yaml
tools: Read, Grep, Glob, Bash
```

Nếu reviewer có nguy cơ sửa file ngoài ý muốn, kiểm tra allowlist không có tool ghi file:

```yaml
tools: Read, Grep, Glob, Bash
```

Nếu output review chung chung:

```text
@"code-reviewer (agent)" review only files changed in git diff. For each finding, include severity, file path, line reference if possible, failure mode, and smallest fix.
```

Nếu output test thiếu evidence:

```text
@"test-engineer (agent)" rerun the relevant checks and include exact commands, exit status, key output lines, and whether the result blocks merge.
```

## Link tài liệu nên đọc

- Claude Code Subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code Settings: https://code.claude.com/docs/en/settings
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code Hooks: https://code.claude.com/docs/en/hooks
- Claude Agent SDK Subagents: https://code.claude.com/docs/en/agent-sdk/subagents
