# Document — Day 15

## Tóm tắt kiến thức

MCP (`Model Context Protocol`) là open standard giúp AI agents kết nối external tools và data sources. Trong Claude Code, MCP mở rộng khả năng từ đọc/sửa code sang tương tác với browser, database, GitHub, docs, logs hoặc internal APIs.

Thành phần:

- MCP client: Claude Code.
- MCP server: process/service expose tools/resources.
- Tool: hành động Claude có thể gọi, ví dụ mở browser hoặc click button.
- Resource: dữ liệu server cung cấp.
- Transport: cách client và server giao tiếp.

Command cốt lõi:

macOS/Linux/WSL:

```bash
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest --browser chrome --isolated
claude mcp list
claude mcp get playwright
claude mcp remove playwright
```

Windows native PowerShell/CMD:

```bash
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

Theo Playwright MCP CLI hiện tại, `--browser` nhận các giá trị như `chrome`, `firefox`, `webkit`, hoặc `msedge`; lab này dùng `chrome` kèm `--isolated`.

Trong Claude Code:

```text
/mcp
```

Ví dụ `.mcp.json` cho project scope:

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

Không hard-code secret vào `.mcp.json`. Nếu cần token, dùng environment variable hoặc config local an toàn.

## Sơ đồ tư duy hoặc luồng xử lý

Luồng kết nối:

```text
User prompt
  -> Claude Code
  -> MCP config
  -> start/connect MCP server
  -> Playwright tools
  -> Chromium browser
  -> taskflow-ai UI
  -> observations/tool result
  -> Claude bug report
```

Luồng kiểm tra UI:

```text
Start app local
  -> Add MCP server
  -> Verify with claude mcp list + /mcp
  -> Open APP_URL
  -> Inspect page state
  -> Execute workflow: create/edit/filter task
  -> Check visible result + console/network
  -> Record findings
  -> Keep or rollback MCP config
```

Security decision flow:

```text
MCP server cần secret?
  |
  +-- Không -> local/project có thể dùng nếu command tin cậy
  |
  +-- Có -> không commit secret
           dùng env var / --env
           giới hạn scope
           review output/log
```

## Bảng so sánh

| Chủ đề | Lựa chọn | Ưu điểm | Nhược điểm | Khuyến nghị |
| --- | --- | --- | --- | --- |
| Transport | `stdio` | Dễ chạy local | Phụ thuộc máy dev | Lab Playwright |
| Transport | `http` | Phù hợp remote service | Cần auth/service ổn định | Remote MCP mới |
| Transport | `sse` | Chạy được với server legacy chỉ expose SSE | Deprecated cho setup mới | Chỉ dùng khi tài liệu server yêu cầu |
| Scope | `local` | An toàn để thử | Không share | Mặc định Day 15 |
| Scope | `project` | Team dùng chung | Dễ commit config sai | Chỉ khi review kỹ |
| Scope | `user` | Tiện cho cá nhân | Áp dụng rộng | Dùng cẩn thận |
| Version | `@latest` | Nhanh cho lab | Không reproducible | Học thử |
| Version | pinned | Ổn định | Cần update có chủ đích | Team/CI |
| Browser state | profile thật | Có sẵn login | Rủi ro leak cookie/data | Tránh |
| Browser state | `--isolated` | Sạch, ít rủi ro | Phải login lại nếu cần | Nên dùng |

## Lỗi thường gặp

1. Đặt option sai vị trí
Sai: `claude mcp add playwright -- npx -y @playwright/mcp@latest --scope local`
Đúng: `claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest`
Lý do: `--scope local` phải là option của Claude Code, không phải argument truyền cho MCP server.

2. Windows native chạy `npx` bị connection closed
Nguyên nhân: Windows không chạy trực tiếp `npx` theo cách MCP server local cần. Dùng wrapper:

```bash
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

3. MCP server không xuất hiện trong `/mcp`
Nguyên nhân: add sai scope, mở Claude Code sai project, `npx` lỗi, network chặn download, server startup fail.

4. App local chưa chạy
Browser báo connection refused. Cần chạy `npm run dev` và dùng đúng port.

5. Dùng `@latest` cho team
Version thay đổi làm kết quả khác nhau. Pin version khi chuyển sang project scope.

6. Lộ secret trong `.mcp.json`
Không ghi token thật vào file shared. Dùng `${ENV_VAR}` hoặc `--env`.

7. Tool output quá lớn
DOM/log dài làm context nhiễu. Yêu cầu không dump DOM, chỉ tóm tắt evidence liên quan.

8. Mở URL không tin cậy
External content có thể chứa prompt injection. Trong lab, chỉ dùng localhost và dữ liệu giả.

## Cách debug

Kiểm tra cấu hình:

```bash
claude mcp list
claude mcp get playwright
```

Remove và add lại:

macOS/Linux/WSL:

```bash
claude mcp remove playwright
claude mcp add --scope local playwright -- npx -y @playwright/mcp@latest --browser chrome --isolated
```

Windows native PowerShell/CMD:

```bash
claude mcp remove playwright
claude mcp add --scope local playwright -- cmd /c npx -y @playwright/mcp@latest --browser chrome --isolated
```

Kiểm tra Node/npm:

```bash
node --version
npm --version
npx -y @playwright/mcp@latest --help
```

Kiểm tra app:

```bash
npm run dev -- --host 127.0.0.1
```

Prompt debug UI:

```text
Dùng MCP Playwright mở APP_URL và chỉ debug vì sao create task không thành công.
Kiểm tra button submit, validation message, console error, network request liên quan submit, và task có xuất hiện sau reload không.
Không sửa code, chỉ báo cáo evidence.
```

Prompt debug security:

```text
Trước khi bật MCP server mới, đánh giá server này có đọc file local, gửi dữ liệu ra network, cần token, hoặc lấy external content không.
Đề xuất scope thấp nhất và rollback plan.
```

## Link tài liệu nên đọc

- Claude Code MCP: https://code.claude.com/docs/en/mcp
- Model Context Protocol: https://modelcontextprotocol.io/
- Playwright MCP: https://github.com/microsoft/playwright-mcp
- Playwright: https://playwright.dev/
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
