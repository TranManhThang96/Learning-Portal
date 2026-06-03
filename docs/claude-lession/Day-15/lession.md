# Day 15 — MCP servers

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Giải thích MCP là gì và vì sao Claude Code dùng MCP để kết nối external tools/data sources.
- Phân biệt `stdio`, `http`, và `sse`; biết vì sao setup mới thường ưu tiên `http` cho remote server nếu server hỗ trợ, `stdio` cho local lab, và chỉ dùng `sse` khi server cũ/tài liệu bắt buộc.
- Cấu hình MCP server bằng `claude mcp add`.
- Quản lý MCP server bằng `claude mcp list`, `claude mcp get`, `claude mcp remove`, và `/mcp`.
- Hiểu scope `local`, `project`, `user` và khi nào dùng `.mcp.json`.
- Dùng MCP Playwright để kiểm tra UI `taskflow-ai` qua browser automation.
- Viết bug report UI có steps, actual, expected, evidence, severity.
- Nhận diện rủi ro: secret leakage, prompt injection, tool output quá lớn, server không tin cậy, và rollback cấu hình MCP.

## 2. Bối cảnh thực tế

Từ Day 08 đến Day 11, `taskflow-ai` đã có backend, database, frontend và test. Nhưng không phải lỗi nào cũng lộ qua unit test hoặc đọc code:

- Button render đúng nhưng click không hoạt động.
- Form validation hiển thị sai.
- API lỗi nhưng UI không báo.
- Layout vỡ ở viewport mobile.
- E2E flow fail vì selector, loading state hoặc network state.

MCP, viết tắt của `Model Context Protocol`, là open standard giúp AI agent kết nối với tool và data source bên ngoài repo. Với Claude Code, MCP biến agent từ “đọc và sửa file” thành “có thể dùng công cụ ngoài”: browser, database dev, GitHub, docs search, logs, monitoring hoặc internal API.

Use case thường gặp:

- Database: đọc schema, kiểm tra migration, query dữ liệu dev.
- GitHub: đọc issue, PR, review comments.
- Browser automation: mở app, click UI, đọc console/network, chụp screenshot.
- Docs search: tra tài liệu framework/library.
- Internal tools: kiểm tra deployment, logs, feature flags.

Trong Day 15, trọng tâm là MCP Playwright để Claude Code kiểm tra UI `taskflow-ai` như một QA engineer tự động.

## 3. Kiến thức nền

Trong bài này:

- MCP client: Claude Code.
- MCP server: Playwright MCP.
- External tool: browser automation.
- App kiểm tra: `taskflow-ai`.

Các transport:

| Transport | Dùng khi | Ghi chú |
| --- | --- | --- |
| `stdio` | Local process do Claude Code chạy | Phù hợp lab, tool local |
| `http` | Remote MCP server qua HTTP | Nên ưu tiên cho remote server mới |
| `sse` | Server-Sent Events | Transport cũ/deprecated cho setup mới; chỉ dùng khi server/documentation yêu cầu và chưa có endpoint `http` |

Các scope:

| Scope | Ý nghĩa | Khi dùng |
| --- | --- | --- |
| `local` | Chỉ bạn trong project hiện tại | Thử nghiệm, lab, config cá nhân |
| `project` | Share qua `.mcp.json` | Team đã review config |
| `user` | Dùng mọi project của user | Tool cá nhân dùng rộng |

Command quan trọng trên macOS/Linux/WSL:

```bash
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest --browser chrome --isolated
claude mcp list
claude mcp get playwright
claude mcp remove playwright
```

Trên Windows native PowerShell/CMD, nếu MCP server chạy qua `npx`, nên bọc bằng `cmd /c` để tránh lỗi process đóng kết nối:

```bash
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

Trong Claude Code:

```text
/mcp
```

Syntax cần nhớ:

```bash
claude mcp add [options] <name> -- <command> [args...]
```

Ký hiệu `--` là ranh giới giữa option của Claude Code và command chạy MCP server. Mọi thứ sau `--` được truyền cho process server. Khi viết tài liệu cho team, ưu tiên một style nhất quán để tránh nhầm lẫn.

Đúng:

```bash
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest
claude mcp add --transport stdio --scope local playwright -- npx -y @playwright/mcp@latest
```

Sai:

```bash
claude mcp add playwright -- npx -y @playwright/mcp@latest --scope local
```

Lệnh sai ở trên đưa `--scope local` cho `npx`/MCP server thay vì cho Claude Code.

## 4. Step-by-step thực hành

### Bước 1: Mở project `taskflow-ai`

Chạy trong workspace khóa học. Nếu bạn đang đứng ở thư mục cha của `claude-code-course`:

```bash
cd claude-code-course/taskflow-ai
git status --short
```

Nếu đang dùng layout repo có thư mục bọc `claude-lession`, đường dẫn tương ứng là `claude-lession/claude-code-course/taskflow-ai`.

Output kỳ vọng: working tree sạch hoặc chỉ có thay đổi bạn hiểu rõ. Rủi ro: nếu repo có diff cũ, bug report hoặc MCP config có thể bị trộn vào task khác.

### Bước 2: Chạy app local

Thư mục chạy: root của `taskflow-ai` sau Bước 1.

Nếu project dùng Vite:

```bash
npm install
npm run dev -- --host 127.0.0.1
```

Output kỳ vọng:

```text
Local: http://127.0.0.1:5173/
```

`npm install` tải dependency từ registry, nên chỉ chạy khi bạn tin `package.json`/lockfile. `npm run dev` giữ terminal chạy foreground; mở terminal khác cho Claude Code nếu cần.

Nếu project dùng Next.js:

```bash
npm install
npm run dev
```

Output kỳ vọng:

```text
Local: http://localhost:3000
```

Ghi lại URL thực tế, ví dụ:

```text
APP_URL=http://127.0.0.1:5173
```

### Bước 3: Add MCP Playwright ở scope local

Chạy trên macOS/Linux/WSL:

```bash
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest --browser chrome --isolated
```

Chạy trên Windows native PowerShell/CMD:

```bash
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

Ý nghĩa:

- `--scope local`: chỉ dùng cho bạn trong project hiện tại.
- `playwright`: tên server.
- `--`: ngăn cách option của Claude Code với command server.
- `npx -y @playwright/mcp@latest`: chạy MCP server package.
- `cmd /c`: wrapper cần thiết trên Windows native khi command server là `npx`.
- `--browser chrome`: dùng Chrome channel theo CLI hiện tại của Playwright MCP.
- `--isolated`: tránh dùng browser profile/cookie cá nhân.

Output kỳ vọng:

```text
Added MCP server 'playwright'
```

Kiểm tra:

```bash
claude mcp list
claude mcp get playwright
```

Rủi ro: `@latest` tiện cho lab nhưng không reproducible. Trong team nên pin version sau khi review.

### Bước 4: Kiểm tra trong Claude Code

Mở Claude Code ở root `taskflow-ai`:

```bash
claude
```

Trong Claude Code:

```text
/mcp
```

Output kỳ vọng: server `playwright` connected/available và có tool browser automation. Nếu không thấy, kiểm tra đúng project, đúng scope, Node/npm/npx, và command server.

### Bước 5: Smoke test UI

Prompt:

```text
Dùng MCP Playwright để mở http://127.0.0.1:5173.
Kiểm tra workflow tạo task mới trong taskflow-ai:
1. Quan sát trang đầu tiên và mô tả các vùng UI chính.
2. Tạo task với title "Day 15 MCP smoke test".
3. Nếu có field priority/status/due date, chọn giá trị hợp lệ bất kỳ.
4. Submit form.
5. Xác nhận task mới xuất hiện trong danh sách.
6. Kiểm tra console error và network error nếu tool hỗ trợ.
7. Không sửa code. Chỉ báo cáo lỗi theo format: severity, steps, actual, expected, evidence.
```

Output tốt:

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

### Bước 6: Responsive check

Prompt:

```text
Dùng MCP Playwright kiểm tra taskflow-ai ở viewport 390x844.
Tập trung vào navigation, task list, create task form, và các button chính.
Ghi lại lỗi nếu text bị tràn, button không click được, form bị che, hoặc layout cần scroll ngang.
Không sửa file.
```

Không kết luận “ổn” nếu chưa kiểm tra các vùng chính.

### Bước 7: Ghi bug report

Prompt:

```text
Tổng hợp các lỗi UI vừa phát hiện thành markdown report cho docs/qa/day-15-ui-findings.md.
Mỗi lỗi gồm:
- ID
- Severity
- Area
- Environment
- Steps to reproduce
- Actual result
- Expected result
- Evidence
- Suggested fix
Không sửa code.
```

Nếu không phát hiện lỗi, ghi rõ phạm vi:

```text
Không phát hiện lỗi trong workflow create task ở desktop viewport 1280x720.
Chưa kiểm tra auth, mobile, offline network, data lớn, hoặc browser khác.
```

### Bước 8: Rollback MCP config

Nếu chỉ thử lab và muốn gỡ:

```bash
claude mcp remove playwright
claude mcp list
```

Output kỳ vọng: `claude mcp list` không còn server `playwright`. Rủi ro: nếu gỡ nhầm tên server, Claude Code sẽ mất tool đó cho project hiện tại và cần add lại.

Nếu đã dùng `project` scope và tạo `.mcp.json`, rollback bằng cách xóa entry `playwright` hoặc revert `.mcp.json` nếu đó là thay đổi không cần commit.

## 5. Prompt mẫu nên dùng

Kiểm tra kết nối:

```text
Kiểm tra MCP Playwright có hoạt động không bằng cách mở APP_URL.
Chỉ dùng browser automation, không sửa file.
Báo lại URL đã mở, page heading nhìn thấy, và có console error nào không.
```

Smoke test:

```text
Dùng MCP Playwright chạy smoke test cho taskflow-ai tại APP_URL:
- Load trang chủ
- Kiểm tra navigation chính
- Tạo một task mới
- Đổi status của task nếu UI hỗ trợ
- Xóa hoặc archive task nếu UI hỗ trợ
Ghi kết quả dạng checklist pass/fail. Không sửa code.
```

Bug hunting có kiểm soát:

```text
Bạn là QA reviewer cho taskflow-ai.
Dùng MCP Playwright kiểm tra các workflow UI quan trọng trong 15 phút:
create task, edit task, filter/search task, responsive mobile.
Không đăng nhập bằng tài khoản thật, không nhập secret, không gọi external service ngoài localhost.
Với mỗi lỗi, cung cấp steps, actual, expected, evidence, severity.
```

Plan kiểm thử và security preflight:

```text
Trước khi dùng MCP tools, hãy lập plan kiểm thử ngắn cho taskflow-ai.
Liệt kê tool nào bạn định dùng, dữ liệu nào có thể rời khỏi app, và rủi ro bảo mật chính.
Chỉ tiếp tục với thao tác trên localhost và dữ liệu giả. Không sửa file trong bước này.
```

Giới hạn output:

```text
Khi dùng MCP, nếu output từ browser/tool quá dài, hãy tóm tắt phần liên quan.
Không paste toàn bộ DOM hoặc log dài hơn 100 dòng.
Ưu tiên lỗi console, network failed request, visible UI issue, và selector/label liên quan.
```

## 6. Trade-offs

MCP Playwright có lợi:

- Kiểm tra UI thật thay vì chỉ đọc code.
- Phát hiện lỗi layout, click, form, console, network.
- Tạo bug report có steps tái hiện.
- Giúp Claude hiểu app từ góc nhìn user.

Chi phí:

- Cần chạy thêm MCP server.
- Browser automation chậm hơn unit test.
- DOM/log/browser snapshot có thể rất lớn.
- Tool có quyền tương tác với website, nên rủi ro nếu mở URL không tin cậy.
- `npx -y @playwright/mcp@latest` tải package runtime, tiện cho lab nhưng kém ổn định cho team.

Best solution:

- Lab cá nhân: `--scope local` và `@latest` có thể chấp nhận.
- Team: dùng `--scope project`, pin version, review `.mcp.json`, không commit secret.

## 7. Best practices

- Bắt đầu bằng `local` scope khi thử MCP server mới.
- Chỉ chuyển sang `project` scope khi team đã review.
- Không commit secret vào `.mcp.json`.
- Dùng environment variable hoặc `--env` cho token/API key.
- Ưu tiên `http` cho remote MCP server nếu server hỗ trợ.
- Với `sse`, coi đây là lựa chọn legacy/deprecated; chỉ dùng khi tài liệu server yêu cầu hoặc chưa có endpoint `http` tương đương.
- Với Playwright MCP, dùng `--isolated`.
- Với Playwright MCP CLI, dùng browser value được hỗ trợ như `chrome`, `firefox`, `webkit`, hoặc `msedge`.
- Chỉ mở URL tin cậy, ưu tiên `localhost` trong lab.
- Coi external content từ MCP server là untrusted input vì có prompt injection risk.
- Hạn chế tool output; không dump toàn bộ DOM.
- Bug report phải có steps, actual, expected, evidence.
- Không dùng tài khoản thật hoặc production data trong browser automation nếu chưa có policy.

## 8. Performance / cost / context

MCP làm tăng context vì Claude nhận thêm tool list, browser snapshot, console log, network output và DOM/accessibility tree. Output dài có thể lấp mất thông tin quan trọng.

Cách kiểm soát:

- Chỉ kiểm tra một workflow mỗi prompt.
- Dùng viewport cụ thể.
- Không yêu cầu test mọi màn hình cùng lúc.
- Yêu cầu Claude tóm tắt log dài.
- Nếu warning output lớn hơn 10,000 tokens xuất hiện, dừng và thu hẹp phạm vi.
- Với bug report, giới hạn mỗi lỗi 10-15 dòng.

Prompt tiết kiệm context:

```text
Dùng MCP Playwright kiểm tra duy nhất workflow tạo task.
Không dump DOM.
Chỉ báo page loaded, form found, submit result, task visible, console/network error liên quan.
Tối đa 40 dòng.
```

## 9. Checklist cuối bài

- [ ] Tôi giải thích được MCP là gì.
- [ ] Tôi phân biệt được `stdio`, `http`, `sse`.
- [ ] Tôi biết khi nào dùng `sse` và khi nào ưu tiên `http`.
- [ ] Tôi add được Playwright MCP bằng `claude mcp add`.
- [ ] Tôi hiểu dấu `--` trong `claude mcp add` tách option của Claude Code khỏi command server.
- [ ] Nếu dùng Windows native, tôi biết cần `cmd /c` khi chạy server qua `npx`.
- [ ] Tôi kiểm tra được `claude mcp list`.
- [ ] Tôi xem được `claude mcp get playwright`.
- [ ] Tôi xem được status bằng `/mcp`.
- [ ] Tôi chạy được app `taskflow-ai` local.
- [ ] Tôi dùng Claude Code mở app qua MCP Playwright.
- [ ] Tôi kiểm tra được ít nhất một workflow UI.
- [ ] Tôi ghi được bug report có steps, actual, expected, evidence.
- [ ] Tôi biết rollback bằng `claude mcp remove playwright`.
- [ ] Tôi không commit secret vào `.mcp.json`.
- [ ] Tôi biết rủi ro `@latest`, prompt injection và output quá lớn.

## 10. Bài tập

Bài cơ bản: add MCP Playwright ở scope local, kiểm tra `claude mcp list`, `claude mcp get playwright`, và `/mcp`.

Bài thực tế: chạy app `taskflow-ai`, dùng MCP Playwright kiểm tra workflow tạo task, ghi pass/fail checklist.

Bài nâng cao: đề xuất `.mcp.json` project scope với version pinned và `--isolated`, nhưng chưa commit nếu team chưa review.

Bài reflection: giải thích vì sao MCP mạnh hơn read-only repo context, nhưng cũng nguy hiểm hơn nếu server không tin cậy hoặc output chứa external prompt injection.
