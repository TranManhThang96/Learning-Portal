# Exercise — Day 15

## Bài 1 — Cơ bản

Mục tiêu: cấu hình MCP Playwright và xác nhận Claude Code nhìn thấy server.

Mở project:

```bash
cd claude-code-course/taskflow-ai
```

Nếu đang dùng layout repo có thư mục bọc `claude-lession`, đường dẫn tương ứng là `claude-lession/claude-code-course/taskflow-ai`.

Add Playwright MCP ở scope local:

macOS/Linux/WSL:

```bash
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest --browser chrome --isolated
```

Windows native PowerShell/CMD:

```bash
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

Kiểm tra:

```bash
claude mcp list
claude mcp get playwright
```

Mở Claude Code:

```bash
claude
```

Trong Claude Code:

```text
/mcp
```

Output kỳ vọng:

- `claude mcp list` có server `playwright`.
- `claude mcp get playwright` hiển thị command `npx`.
- `/mcp` hiển thị `playwright` connected/available.

Rủi ro cần ghi chú:

- `npx -y @playwright/mcp@latest` tải package từ npm.
- `@latest` không ổn định cho team.
- `--isolated` giúp tránh profile/cookie cá nhân.
- Trên Windows native, thiếu `cmd /c` có thể làm MCP server qua `npx` bị `Connection closed`.

Rollback:

```bash
claude mcp remove playwright
```

Giải thích lệnh:

| Lệnh | Thư mục chạy | Làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `cd claude-code-course/taskflow-ai` | Thư mục cha của `claude-code-course` | Vào root project thực hành | Terminal đổi sang `taskflow-ai` | Sai path nếu bạn đang ở layout repo khác |
| `claude mcp add ... playwright ...` | Root `taskflow-ai` | Đăng ký Playwright MCP cho project hiện tại ở scope local | Thông báo đã add server `playwright` | `npx` tải package từ npm; `@latest` có thể đổi behavior |
| `claude mcp list` | Root `taskflow-ai` | Liệt kê MCP server đã cấu hình | Có dòng `playwright` | Nếu chạy sai project có thể không thấy server |
| `claude mcp get playwright` | Root `taskflow-ai` | Xem chi tiết command/args của server | Thấy command `npx` hoặc `cmd /c npx` | Có thể lộ config nhạy cảm nếu bạn hard-code secret |
| `claude` rồi `/mcp` | Root `taskflow-ai` | Mở Claude Code và kiểm tra trạng thái MCP trong session | `playwright` connected/available | Server fail nếu Node/npm/npx lỗi |
| `claude mcp remove playwright` | Root `taskflow-ai` | Gỡ server khỏi scope local của project | `playwright` không còn trong `claude mcp list` | Gỡ nhầm tên server thì cần add lại |

## Bài 2 — Thực tế

Mục tiêu: dùng Claude Code + MCP Playwright kiểm tra UI `taskflow-ai`.

Chạy app từ root `taskflow-ai`:

```bash
npm install
npm run dev -- --host 127.0.0.1
```

Hoặc nếu Next.js:

```bash
npm install
npm run dev
```

Ghi URL thực tế, ví dụ:

```text
http://127.0.0.1:5173
```

Giải thích lệnh:

| Lệnh | Thư mục chạy | Làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `npm install` | Root `taskflow-ai` | Cài dependency theo `package.json`/lockfile | Tạo/cập nhật `node_modules` không lỗi | Chỉ chạy khi tin dependency; có thể tốn thời gian/network |
| `npm run dev -- --host 127.0.0.1` | Root `taskflow-ai` | Chạy Vite dev server chỉ bind localhost | URL local như `http://127.0.0.1:5173` | Terminal bị chiếm foreground; port có thể trùng |
| `npm run dev` | Root `taskflow-ai` | Chạy dev server theo script project, thường dùng cho Next.js | URL local như `http://localhost:3000` | Cần đọc output thực tế vì port có thể khác |

Prompt:

```text
Dùng MCP Playwright kiểm tra taskflow-ai tại http://127.0.0.1:5173.
Không sửa file.
Hãy thực hiện:
1. Mở trang.
2. Mô tả các vùng UI chính.
3. Tạo task mới với title "Day 15 MCP smoke test".
4. Nếu có status/priority/due date, chọn giá trị hợp lệ.
5. Submit form.
6. Xác nhận task xuất hiện trong danh sách.
7. Kiểm tra console error và network error nếu tool hỗ trợ.
8. Trả kết quả dạng pass/fail checklist và bug report nếu có lỗi.
```

Output kỳ vọng:

```text
Workflow: Create task
Result: Pass/Fail
Evidence:
- Page loaded: yes/no
- Create form found: yes/no
- Submit completed: yes/no
- Task visible after submit: yes/no
- Console/network errors: none/list
```

Bug report nếu fail:

```text
ID: UI-001
Severity: Medium
Area: Create task
Environment: local, Chromium via Playwright MCP
Steps to reproduce:
1. Open APP_URL
2. Click New Task
3. Enter title
4. Submit
Actual result:
...
Expected result:
...
Evidence:
...
Suggested fix:
...
```

Security rule:

- Chỉ dùng dữ liệu giả.
- Không nhập token/password thật.
- Không mở site ngoài localhost nếu chưa được phép.

## Bài 3 — Nâng cao

Mục tiêu: đề xuất MCP config an toàn hơn cho team.

Viết đề xuất `.mcp.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "-y",
        "@playwright/mcp@<PINNED_VERSION>",
        "--browser",
        "chrome",
        "--isolated"
      ]
    }
  }
}
```

Yêu cầu:

1. Thay `<PINNED_VERSION>` bằng version cụ thể team chọn.
2. Giải thích vì sao không dùng `@latest` cho team.
3. Giải thích vì sao dùng `--isolated`.
4. Nêu khi nào nên dùng `local` thay vì `project`.
5. Nêu rollback plan nếu MCP server gây lỗi.

Prompt review:

```text
Đọc cấu hình MCP Playwright dưới đây và review dưới góc security/maintainability.
Hãy chỉ ra rủi ro, rollback plan, và đề xuất chỉnh sửa.
Không sửa file.
```

Expected result:

- Có recommendation pin version.
- Không hard-code secret.
- Không dùng browser profile thật.
- Có rollback command `claude mcp remove playwright`.
- Có note: nếu `.mcp.json` được commit, team cần hiểu server nào sẽ chạy.

## Bài 4 — Review & Reflection

Trả lời:

1. MCP khác gì so với việc Claude Code chỉ đọc file trong repo?
2. Vì sao external content từ MCP server có prompt injection risk?
3. Khi nào dùng `local`, `project`, `user` scope?
4. Vì sao không nên đưa secret vào `.mcp.json` shared?
5. Khi browser automation trả về DOM/log quá dài, bạn giảm context bằng cách nào?
6. Một bug report UI tốt cần những trường nào?
7. Nếu Playwright MCP làm Claude Code chậm hoặc lỗi, rollback thế nào?

Expected answer ngắn:

```text
MCP cho Claude Code quyền dùng external tools/data, không chỉ repo. External content là untrusted input và có thể chứa chỉ dẫn độc hại nhằm bẻ hướng agent. local dùng để thử cá nhân, project dùng cho config đã review và share qua repo, user dùng cho tool cá nhân ở nhiều project. Không đưa secret vào .mcp.json vì có thể bị commit/leak. Khi output lớn, giới hạn workflow, không dump DOM, tóm tắt log và dừng nếu context quá lớn. Bug report cần severity, area, environment, steps, actual, expected, evidence, suggested fix. Rollback bằng claude mcp remove playwright hoặc revert .mcp.json.
```

## Tiêu chí hoàn thành

- [ ] Đã add MCP Playwright.
- [ ] Có kết quả `claude mcp list`.
- [ ] Có kết quả `claude mcp get playwright`.
- [ ] `/mcp` thấy server `playwright`.
- [ ] App `taskflow-ai` chạy local.
- [ ] Claude Code mở được app qua MCP Playwright.
- [ ] Đã kiểm tra ít nhất một workflow UI.
- [ ] Có pass/fail checklist.
- [ ] Có bug report nếu phát hiện lỗi hoặc ghi rõ phạm vi nếu không phát hiện lỗi.
- [ ] Có ghi chú security risk.
- [ ] Có rollback plan.

## Gợi ý nếu bí

Nếu `claude mcp list` không thấy server:

macOS/Linux/WSL:

```bash
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest --browser chrome --isolated
```

Windows native PowerShell/CMD:

```bash
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

Nếu add nhầm:

```bash
claude mcp remove playwright
```

Nếu `/mcp` không connected:

- Thoát Claude Code.
- Chạy `claude mcp get playwright`.
- Kiểm tra `node`, `npm`, `npx`.
- Mở lại Claude Code trong đúng project.

Nếu app không mở được:

- Kiểm tra dev server còn chạy không.
- Kiểm tra đúng port không.
- Thử mở URL bằng browser thường.
- Đọc terminal output của `npm run dev`.

Nếu Claude trả lời quá dài:

```text
Dừng lại. Tóm tắt chỉ các lỗi liên quan workflow create task.
Không paste DOM. Mỗi lỗi tối đa 10 dòng.
```

## Đáp án tham khảo hoặc expected result

Ví dụ command log:

macOS/Linux/WSL:

```text
cd claude-code-course/taskflow-ai
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest --browser chrome --isolated
claude mcp list
claude mcp get playwright
npm run dev -- --host 127.0.0.1
claude
/mcp
```

Windows native PowerShell/CMD thay dòng add MCP bằng:

```text
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

Ví dụ smoke test pass:

```text
Workflow: Create task
Result: Pass
Environment:
- App URL: http://127.0.0.1:5173
- Browser: Chromium via Playwright MCP
- Viewport: desktop
Checklist:
- Page loaded: pass
- Main task list visible: pass
- Create task action visible: pass
- Task title entered: pass
- Submit completed: pass
- New task visible: pass
- Console error: none observed
Notes:
No issue found within create task desktop smoke test scope.
```

Ví dụ security note:

```text
MCP Playwright is configured as local scope for lab use.
It uses npx with @latest, acceptable for a short exercise but should be pinned before sharing with a team.
The server is launched with --isolated to avoid personal browser state.
No secrets are stored in .mcp.json.
Rollback command: claude mcp remove playwright
```
