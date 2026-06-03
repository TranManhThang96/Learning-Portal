# Document — Day 18

## Tóm tắt kiến thức

Security review với Claude Code gồm hai lớp:

1. Review sản phẩm `taskflow-ai`: source, config, scripts, dependency, logs, docs.
2. Review cách dùng Claude Code: permission modes, allow/ask/deny, hooks, MCP scope, managed settings, telemetry/data usage, PR review.

Nhóm rủi ro chính:

- Secret leakage.
- Prompt injection trong repo/docs/comments/test fixtures.
- Dependency và supply-chain risk.
- Command execution risk.
- Data privacy/logging.
- MCP và permission quá rộng.

## Sơ đồ tư duy hoặc luồng xử lý

```text
Security review
├── Baseline
│   ├── git status
│   └── plan/default permission mode
├── Audit read-only
│   ├── secrets
│   ├── prompt injection
│   ├── dependency
│   ├── command execution
│   └── privacy/logging
├── Prioritize
│   ├── Critical: leaked secret, RCE, prod data exposure
│   ├── High: auth bypass, dangerous scripts
│   └── Medium/Low: weak config, docs hygiene
├── Fix small
│   ├── issue 1
│   ├── issue 2
│   └── issue 3
├── Guardrails
│   ├── allow/ask/deny + deny .env
│   ├── hooks
│   ├── MCP scope
│   └── PR review
└── Verify
    ├── diff review
    ├── lint/test/audit
    └── rotation note
```

## Bảng so sánh

| Chủ đề | Dấu hiệu rủi ro | Cách audit | Guardrail |
| --- | --- | --- | --- |
| Secrets | API key, JWT, `.env` thật | `rg`, secret scan, review history | `.gitignore`, `.env.example`, rotation |
| Prompt injection | Markdown bảo agent ignore instruction | Scan docs/comments/test fixtures | Treat repo as data, restrict tools |
| Dependency | CVE, package lạ, `postinstall` | `npm audit`, inspect scripts | Lockfile, Dependabot/Renovate, PR review |
| Command execution | `rm -rf`, `curl`, publish, migrate | Review `package.json`, Claude Bash requests | Bash allow/ask/deny, hooks |
| Data privacy | Log token/PII | Search logs/tests/error handlers | Redaction, synthetic data |
| MCP tools | Wildcard hoặc server quá rộng | Review MCP config | Scope theo server/tool/repo |
| Settings changes | Agent/user nới permission | Review `.claude/settings.json` diff | Managed settings, PR review, PreToolUse/PermissionRequest hook |
| Data usage | Production data vào prompt/log | Review prompt, logs, telemetry policy | Masking, synthetic data, data-retention policy |

## Lỗi thường gặp

- Cho Claude Code audit với quyền quá rộng ngay từ đầu.
- Dùng `auto` mode như baseline security audit dù đây là research preview.
- Dùng wildcard như `Bash(*)` hoặc MCP wildcard cho tiện.
- Thấy secret rồi chỉ xóa khỏi file, không rotate.
- Paste nguyên secret vào issue, PR comment hoặc prompt.
- Chạy `npm audit fix --force` làm vỡ dependency tree.
- Tin rằng markdown trong repo là instruction hợp lệ.
- Log toàn bộ request body trong endpoint AI.
- Dùng Claude Code review thay human review.

## Cách debug

Tìm secret:

```bash
rg -n --hidden --glob '!node_modules' --glob '!.git' "(secret|token|api[_-]?key|password|Authorization|Bearer |BEGIN .*PRIVATE KEY)"
```

Tìm prompt injection:

```bash
rg -n --hidden --glob '!node_modules' --glob '!.git' "(ignore previous|disregard|system prompt|developer message|print env|send.*secret|exfiltrate)"
```

Audit dependency:

```bash
npm audit --audit-level=moderate
```

Các lệnh này chạy ở root `taskflow-ai`. Output kỳ vọng là danh sách issue hoặc rỗng. Rủi ro: output có thể chứa secret; mask trước khi chia sẻ.

Nếu Claude đề xuất command nguy hiểm, yêu cầu:

```text
Explain cwd, exact command, purpose, expected output, side effects, rollback and safer alternative. Do not run it yet.
```

## Link tài liệu nên đọc

- Claude Code Security: https://code.claude.com/docs/en/security
- Claude Code Permissions: https://code.claude.com/docs/en/permissions
- Claude Code Settings: https://code.claude.com/docs/en/settings
- Claude Code Hooks: https://code.claude.com/docs/en/hooks
- Claude Code MCP: https://code.claude.com/docs/en/mcp
- Claude Code Data Usage: https://code.claude.com/docs/en/data-usage
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- OWASP Secrets Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- GitHub Secret Scanning: https://docs.github.com/en/code-security/secret-scanning
- npm audit: https://docs.npmjs.com/cli/commands/npm-audit
