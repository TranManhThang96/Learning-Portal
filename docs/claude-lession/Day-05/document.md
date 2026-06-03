# Document — Day 05

## Tóm tắt kiến thức

`CLAUDE.md` là project instructions, thường được xem như project memory do team kiểm soát cho Claude Code. Nó giúp session mới có cùng hiểu biết nền về repo: stack, architecture, commands, conventions, testing, security, và workflow. Theo tài liệu Claude Code hiện hành, project instructions có thể nằm ở `CLAUDE.md` hoặc `.claude/CLAUDE.md`.

Ý tưởng cốt lõi: `CLAUDE.md` không phải README thứ hai. Nó là cheat sheet cho AI, được tối ưu để Claude ra quyết định đúng hơn khi đọc code, lập plan, edit file, và đề xuất command.

Không nên đồng nhất `CLAUDE.md` với mọi tính năng auto memory. Nếu CLI version đang dùng có auto memory, hãy kiểm tra official docs để biết scope, giới hạn, và cách bật/tắt trước khi đưa vào workflow team. Trong Day 05, nguồn chân lý vẫn là file instruction được review và commit có chủ đích.

Nội dung nên có:

- Project summary: `taskflow-ai` là ứng dụng quản lý task cho team kỹ thuật.
- Stack: Node.js, TypeScript, backend Fastify hoặc NestJS, React + Vite, PostgreSQL, Redis, Vitest/Jest, Playwright, Docker Compose.
- Structure: root, backend, frontend, shared packages, test, scripts, infra.
- Commands: dev, build, lint, typecheck, unit test, integration test, e2e, Docker Compose.
- Coding conventions: module boundary, validation, error handling, naming, component boundary.
- Testing rules: test bắt buộc cho behavior change, không sửa test để hợp thức hóa bug.
- Security rules: không đọc secret, không in `.env`, không dùng production data, không chạy destructive command, không tự commit/push.
- Workflow: plan trước với task rủi ro, sửa nhỏ, tóm tắt diff, đề xuất verification.

Nội dung không nên có:

- Secret, token, private key, connection string thật.
- Log dài, transcript, task tạm thời, hoặc todo cá nhân.
- Toàn bộ architecture document nhiều trang.
- Rule chung chung như "write clean code" mà không có hành vi cụ thể.
- Command chưa verify nhưng viết như chắc chắn đúng.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Mở repo taskflow-ai
  |
  v
Kiểm tra Git state
  |
  v
Chạy `claude` từ project root
  |
  v
`/init` nếu CLI hỗ trợ hoặc prompt khám phá repo
  |
  v
Claude tạo draft CLAUDE.md
  |
  v
Developer review như review code
  |
  +-- Sai command -> sửa hoặc đánh dấu cần xác nhận
  +-- Quá dài -> rút gọn thành cheat sheet
  +-- Có secret/rủi ro -> xóa ngay
  +-- Rule mơ hồ -> viết lại thành hành vi cụ thể
  |
  v
Commit CLAUDE.md khi đạt chuẩn team
  |
  v
Mở session mới ở root repo bằng `claude`
  |
  v
Hỏi Claude tóm tắt project instructions đã load
  |
  +-- Đúng stack/command/rule -> đạt
  +-- Trả lời chung chung/sai -> debug vị trí file, nội dung, session root
```

Luồng cập nhật khi repo thay đổi:

```text
PR đổi architecture hoặc command
  -> cập nhật code/config
  -> cập nhật README nếu cần cho human
  -> cập nhật CLAUDE.md nếu ảnh hưởng Claude workflow
  -> mở session mới kiểm tra context
```

## Bảng so sánh

| Artifact | Dùng để làm gì | Commit vào repo? | Nội dung phù hợp | Không nên chứa |
| --- | --- | --- | --- | --- |
| `CLAUDE.md` | Project instructions cho Claude Code | Có, nếu là rule team | Commands, architecture map, conventions, testing, security | Secret, log dài, task tạm |
| `.claude/CLAUDE.md` | Project instructions trong thư mục riêng của Claude | Có, nếu team chọn convention này | Nội dung tương tự `CLAUDE.md` | Config local cá nhân |
| `.claude/settings.json` | Cấu hình hành vi Claude Code | Tùy team | Permission defaults như `permissions.defaultMode: "auto"`, allowed/denied tools | Architecture dài |
| `README.md` | Onboarding cho developer | Có | Setup, mục tiêu project, usage, contribution | Rule quá chi tiết cho AI |
| Prompt session | Chỉ dẫn cho task hiện tại | Không | Goal, constraints, acceptance criteria, verification | Rule lâu dài phải lặp lại mãi |
| ADR/docs | Quyết định kiến trúc sâu | Có | Rationale, trade-off, migration plan | Instruction ngắn cần luôn nạp vào context |

| Section trong `CLAUDE.md` | Câu hỏi cần trả lời | Ví dụ tốt | Ví dụ yếu |
| --- | --- | --- | --- |
| Project | Repo này là gì? | `taskflow-ai` manages engineering tasks for small teams | This is a good app |
| Structure | Sửa file ở đâu? | `apps/api` for backend, `apps/web` for frontend | Source code is in src |
| Commands | Chạy gì để verify? | `pnpm --filter api test` from repo root | Run tests |
| Conventions | Code nên theo pattern nào? | Put request validation at route schema before service logic | Write clean code |
| Testing | Khi nào cần test? | Add unit test for service behavior and e2e for create-task flow | Add tests if needed |
| Security | Không được làm gì? | Do not read `.env` or run `docker compose down -v` without confirmation | Be secure |
| Workflow | Claude phải làm việc ra sao? | Plan first, edit small, summarize diff, do not commit | Help me code fast |

| Vấn đề | Giải pháp trong `CLAUDE.md` | Trade-off |
| --- | --- | --- |
| Claude dùng sai package manager | Ghi rõ command và thư mục chạy | Cần cập nhật khi scripts đổi |
| Claude sửa quá nhiều file | Ghi workflow "small diff, plan first" | Có thể chậm hơn |
| Claude quên test runner | Ghi test command chính xác | Tốn vài dòng context |
| Claude đề xuất command nguy hiểm | Ghi denied commands cụ thể | Cần developer xác nhận thủ công |
| Session mới trả lời chung chung | Kiểm tra vị trí file và nội dung quá dài | Mất thêm vài phút debug |

## Lỗi thường gặp

1. Biến `CLAUDE.md` thành README dài  
   Hậu quả là session nào cũng phải nạp nhiều context không cần thiết, trong khi rule quan trọng bị chìm.

2. Tin tuyệt đối vào `/init`  
   `/init` có thể tạo draft hữu ích nhưng vẫn có thể sai command, sai folder, hoặc suy luận architecture chưa đủ bằng chứng.

3. Ghi command không có thư mục chạy  
   `npm test` chạy ở root có thể fail nếu test thật nằm trong `apps/api`. Claude cần biết cwd.

4. Ghi rule chung chung  
   "Use best practices" không giúp Claude ra quyết định. Hãy viết "Do not add a new abstraction unless two call sites need it".

5. Đưa secret vào project memory  
   Đây là lỗi nghiêm trọng. `CLAUDE.md` có thể được commit và được nạp vào nhiều session. Không ghi `.env`, token, private key, production URL nhạy cảm.

6. Không cập nhật khi repo đổi  
   Nếu chuyển từ Jest sang Vitest nhưng `CLAUDE.md` vẫn ghi Jest, Claude sẽ tiếp tục đề xuất test sai.

7. Không kiểm tra session mới  
   File tồn tại không đảm bảo Claude đang ở đúng root repo hoặc đang load đúng instruction. Nếu dùng `claude --continue`, bạn có thể đang kiểm tra context cũ của session gần nhất chứ không phải một session mới sạch.

8. Trộn rule local cá nhân vào rule team  
   Ví dụ path tool local, port riêng, hoặc alias shell cá nhân nên để trong local settings, không ép toàn team.

## Cách debug

Khi Claude không load đúng `CLAUDE.md`:

1. Xác nhận đang ở root `taskflow-ai`:

```bash
pwd
```

Lệnh này in thư mục hiện tại. Output kỳ vọng kết thúc bằng `taskflow-ai`. Rủi ro thấp, read-only.

2. Kiểm tra file tồn tại:

```bash
ls CLAUDE.md .claude/CLAUDE.md
```

Lệnh này kiểm tra hai vị trí project instructions phổ biến. Output kỳ vọng có ít nhất một file tồn tại. Rủi ro thấp. Nếu shell báo file không tồn tại, kiểm tra lại vị trí file.

Trên PowerShell:

```powershell
Test-Path .\CLAUDE.md
Test-Path .\.claude\CLAUDE.md
```

Output kỳ vọng là `True` cho vị trí bạn dùng.

3. Mở session mới:

```bash
cd /path/to/taskflow-ai
claude
```

Lệnh này mở Claude Code từ đúng project root. Output kỳ vọng là Claude sẵn sàng nhận prompt; có thể dùng `/help` để xem commands của CLI version hiện tại.

Không dùng `claude --continue` nếu mục tiêu là kiểm tra session mới sạch, vì nó resume session gần nhất trong thư mục hiện tại. Dùng `claude --resume` hoặc `/resume` khi mục tiêu là chọn session cũ để tiếp tục.

Không cần dùng `claude --permission-mode acceptEdits` trong bước debug context. Chế độ này cho phép tạo/sửa file và auto-approve một số command filesystem phổ biến trong working directory, nên chỉ phù hợp khi bạn thật sự muốn Claude edit sau khi guardrails đã rõ.

4. Hỏi kiểm tra context:

```text
Không sửa file. Hãy tóm tắt project instructions đã load từ CLAUDE.md hoặc .claude/CLAUDE.md.
Nếu không thấy file instruction, nói rõ.
```

Nếu Claude trả lời sai, kiểm tra:

- Có mở nhầm thư mục cha hoặc package con không.
- File quá dài hoặc chứa nhiều thông tin mâu thuẫn không.
- Có cả `CLAUDE.md` và `.claude/CLAUDE.md` với rule xung đột không.
- Nội dung có ghi command cũ không.
- Session hiện tại có prompt trước đó ép Claude làm ngược rule không.

Khi command trong `CLAUDE.md` sai:

```bash
git diff -- CLAUDE.md
```

Review patch và sửa command theo `package.json` thật. Không để Claude đoán nếu script chưa tồn tại.

Khi file quá dài:

```text
Rút gọn CLAUDE.md xuống dưới 200 dòng và dễ scan như cheat sheet.
Giữ lại commands, architecture boundary, testing/security/workflow rules.
Chuyển phần giải thích dài thành link tới docs, không paste nguyên văn.
```

Khi cần rollback:

```bash
git restore -- CLAUDE.md
```

Chỉ dùng nếu file đã được Git track và bạn muốn bỏ toàn bộ thay đổi chưa commit trong file đó. Rủi ro: mất phần bạn tự sửa trong cùng file. Trong repo có nhiều người cùng làm, chỉ restore file bạn chắc là do mình tạo/sửa hoặc đã được xác nhận không chứa thay đổi của người khác.

## Link tài liệu nên đọc

- Claude Code Memory: https://code.claude.com/docs/en/memory
- Claude Code Best Practices: https://code.claude.com/docs/en/best-practices
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Settings: https://code.claude.com/docs/en/settings
- Claude Code Slash Commands: https://code.claude.com/docs/en/slash-commands
- Git ignore documentation: https://git-scm.com/docs/gitignore
- Git restore documentation: https://git-scm.com/docs/git-restore
