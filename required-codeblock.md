Yêu cầu convert code block:
- Chuẩn hóa code fence language để tránh warning khi chạy `vitepress build`.
- Không dùng các language id lạ mà Shiki/VitePress có thể không load được.
- Nếu không chắc language đó được Shiki hỗ trợ, hãy đổi sang `txt`.


## Quy tắc quan trọng khi xử lý code block

Với mọi code fence dạng:

\`\`\`language
...
\`\`\`

hãy kiểm tra `language` và thay theo bảng sau:

| Language cũ | Language mới nên dùng |
|---|---|
| `gitignore` | `ignore` |
| `dockerignore` | `ignore` |
| `.gitignore` | `ignore` |
| `.dockerignore` | `ignore` |
| `env` | `dotenv` hoặc `txt` |
| `.env` | `dotenv` hoặc `txt` |
| `shell` | `bash` |
| `sh` | `bash` |
| `zsh` | `bash` |
| `powershell` | `powershell` |
| `ps1` | `powershell` |
| `cmd` | `bat` |
| `batch` | `bat` |
| `yml` | `yaml` |
| `dockerfile` | `docker` |
| `Dockerfile` | `docker` |
| `gotemplate` | `go-template` hoặc `txt` |
| `gohtml` | `go-template` hoặc `html` |
| `jinja2` | `html` nếu có HTML, nếu không thì `txt` |
| `jinja` | `html` nếu có HTML, nếu không thì `txt` |
| `promql` | `sql` hoặc `txt` |
| `rego` | `txt` |
| `toml` | `toml` |
| `ini` | `ini` |
| `conf` | `ini` hoặc `txt` |
| `config` | `txt` |
| `log` | `txt` |
| `text` | `txt` |
| không có language | giữ nguyên hoặc thêm `txt` nếu là output/log/plain text |

## Quy tắc chọn language

1. Nếu là command terminal:
   - Linux/macOS command → dùng `bash`
   - Windows PowerShell → dùng `powershell`
   - Windows CMD/batch → dùng `bat`

2. Nếu là output terminal, log, error stacktrace:
   - Dùng `txt`
   - Không dùng `bash`, vì đó không phải command.

3. Nếu là file config:
   - YAML → `yaml`
   - JSON → `json`
   - TOML → `toml`
   - INI → `ini`
   - ENV → `dotenv` hoặc `txt`
   - Unknown config → `txt`

4. Nếu là ignore file:
   - `.gitignore`, `.dockerignore`, `.npmignore` → dùng `ignore`

5. Nếu là template:
   - HTML có Jinja/Nunjucks syntax → ưu tiên `html`
   - Go template → dùng `go-template` nếu build không warning, nếu không dùng `txt`
   - Template khó nhận diện → dùng `txt`

6. Nếu là policy hoặc DSL ít phổ biến:
   - `rego`, `promql`, `hcl`, `terraform`, `nginx`, `apache`, `graphql`:
   - Chỉ giữ language gốc nếu chắc VitePress/Shiki hỗ trợ.
   - Nếu không chắc, đổi sang `txt`.

## Quy tắc riêng cho VitePress

- Không dùng heading cấp 1 nhiều lần trong cùng một file nếu không cần thiết.
- Giữ cấu trúc heading rõ ràng:
  - `#` cho tiêu đề bài
  - `##` cho phần lớn
  - `###` cho phần nhỏ
- Không để HTML/script nguy hiểm trong Markdown nếu không cần.
- Với code block quá dài, log quá dài, JSON/YAML quá dài:
  - đổi language thành `txt`
  - hoặc rút gọn bằng comment như:
    `# ... phần còn lại được lược bỏ`

## Không được làm

- Không tự ý sửa logic code.
- Không dịch code/comment nếu không được yêu cầu.
- Không đổi nội dung command.
- Không xóa code block.
- Không thêm giải thích dài vào file nếu người dùng chỉ yêu cầu convert.
- Không dùng language id lạ như `dockerignore`, `gitignore`, `jinja2`, `gotemplate`, `promql`, `rego` nếu mục tiêu là build sạch warning.