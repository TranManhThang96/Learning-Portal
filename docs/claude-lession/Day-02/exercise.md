# Exercise — Day 02

## Bài 1 — Cơ bản

Mục tiêu: kiểm tra môi trường local và mở Claude Code đúng thư mục.

Thời gian: 20-25 phút.

Yêu cầu:

1. Tạo thư mục sandbox cho project `taskflow-ai`.
2. Chạy `git init`.
3. Kiểm tra `git --version`, `node --version`, `claude --version`.
4. Chạy `claude` từ root `taskflow-ai`.
5. Trong Claude Code, chạy `/help`.
6. Hỏi Claude: "Bạn đang thấy project boundary nào? Chỉ đọc và trả lời, không sửa file."

Lệnh gợi ý trên macOS/Linux:

```bash
mkdir -p ~/work/taskflow-ai
cd ~/work/taskflow-ai
git init
git --version
node --version
claude --version
claude
```

Lệnh gợi ý trên Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path D:\my-source\taskflow-ai
Set-Location D:\my-source\taskflow-ai
git init
git --version
node --version
claude --version
claude
```

Cần ghi lại:

- Đường dẫn root project.
- Phiên bản Git, Node.js, Claude Code.
- Claude có xác nhận đúng repo `taskflow-ai` không.

## Bài 2 — Thực tế

Mục tiêu: dùng Claude Code tạo guideline và scaffold project tối thiểu.

Thời gian: 40-50 phút.

Trong Claude Code, chạy:

```txt
/init
```

Sau đó dùng prompt:

```txt
Project này là taskflow-ai, app quản lý task mini cho team kỹ thuật.

Hãy lập plan tạo scaffold Day 02. Phạm vi được phép:
- CLAUDE.md
- README.md
- .gitignore
- apps/api/
- apps/web/
- docs/
- infra/

Ràng buộc:
- Không cài dependency.
- Không tạo .env thật.
- Không thêm secret hoặc credential.
- Không tạo business logic phức tạp.
- Backend chỉ là skeleton Node.js + TypeScript + Fastify.
- Frontend chỉ là skeleton React + Vite + TypeScript.

Trước khi edit, hãy liệt kê file sẽ tạo/sửa và chờ tôi xác nhận.
```

Sau khi duyệt plan, yêu cầu Claude implement:

```txt
Thực hiện plan đã duyệt. Sau khi sửa, tóm tắt file đã tạo và nhắc tôi command cần chạy để review diff. Không chạy install.
```

Kiểm tra ngoài terminal:

```bash
git status
git diff --stat
git diff
```

Yêu cầu kết quả:

- Có `CLAUDE.md`.
- Có `README.md`.
- Có `.gitignore`.
- Có `apps/api` và `apps/web`.
- Có `docs` và `infra`.
- Không có `.env`.
- Không có `node_modules`.
- Không có secret thật.

## Bài 3 — Nâng cao

Mục tiêu: so sánh workflow "Claude skeleton trước" và "generator trước" mà không làm hỏng repo chính.

Thời gian: 35-45 phút.

Tạo branch thử nghiệm:

```bash
git checkout -b experiment/vite-generator
```

Nếu bạn muốn thử generator, chạy trong root `taskflow-ai`:

```bash
npm create vite@latest apps/web-generated -- --template react-ts
```

Giải thích:

- Branch `experiment/vite-generator` cô lập thử nghiệm.
- `apps/web-generated` tránh overwrite `apps/web` đã scaffold.
- Generator có thể tải package từ npm và tạo file theo phiên bản hiện tại.

Sau đó hỏi Claude:

```txt
So sánh apps/web và apps/web-generated.

Tập trung vào:
- File nào generator tạo thêm?
- File nào nên học theo?
- File nào không cần cho Day 02?
- Nếu muốn thay apps/web bằng output generator, cần plan migration nào?

Chỉ đọc và phân tích. Không sửa file.
```

Kết thúc bài:

```bash
git diff --stat
git checkout main
```

Nếu branch chính của bạn không tên `main`, thay bằng tên branch đang dùng, kiểm tra bằng:

```bash
git branch --show-current
```

Yêu cầu kết quả:

- Có bảng so sánh ngắn giữa skeleton và generator.
- Không merge thử nghiệm nếu chưa review.
- Không overwrite scaffold chính.

Rủi ro:

- `npm create vite@latest` cần internet.
- Generator có thể hỏi xác nhận nếu folder tồn tại.
- Không chạy trong `apps/web` nếu bạn chưa muốn overwrite.

## Bài 4 — Review & Reflection

Mục tiêu: rèn thói quen review AI output trước khi commit.

Thời gian: 25-30 phút.

Yêu cầu Claude review:

```txt
Review diff hiện tại cho Day 02.

Hãy phân loại finding theo mức:
- Critical: secret, lệnh destructive, file ngoài phạm vi.
- High: README sai trạng thái, .gitignore thiếu rule quan trọng.
- Medium: scaffold khó maintain, script gây hiểu nhầm.
- Low: naming hoặc wording.

Không sửa file. Chỉ đưa finding và đề xuất.
```

Sau đó tự trả lời các câu hỏi:

- Claude đã tạo file đúng phạm vi chưa?
- Có lệnh nào Claude đề xuất nhưng bạn chưa hiểu không?
- `.gitignore` có chặn secret chưa?
- README có trung thực về trạng thái scaffold không?
- Bạn sẽ dùng phiên mặc định hay `claude --permission-mode acceptEdits` ở Day 03, và vì sao?

Nếu mọi thứ ổn, tạo commit:

```bash
git add README.md .gitignore CLAUDE.md apps docs infra
git commit -m "chore: scaffold taskflow ai project"
```

Không dùng `git add .` trong bài này. Mục tiêu là tập add path rõ ràng.

## Tiêu chí hoàn thành

Bạn hoàn thành Day 02 khi có đủ:

- `claude --version` chạy được.
- Repo `taskflow-ai` đã `git init`.
- Claude Code được mở từ root project.
- `/help` và `/init` đã được dùng hoặc đã được kiểm tra.
- `CLAUDE.md` có guideline ban đầu.
- `README.md` mô tả project và trạng thái scaffold.
- `.gitignore` chặn `.env`, `.env.*`, `node_modules/`, `dist/`, `coverage/`.
- Folder `apps/api`, `apps/web`, `docs`, `infra`.
- Không có secret thật trong prompt, file, diff hoặc commit.
- Đã review `git diff`.
- Có commit checkpoint hoặc ghi chú lý do chưa commit.

## Gợi ý nếu bí

- Nếu `claude` không chạy, đọc lại quickstart và kiểm tra terminal đã nhận `PATH` mới chưa.
- Nếu Claude tạo quá nhiều file, yêu cầu dừng và thu hẹp phạm vi: "Chỉ giữ README.md, .gitignore, CLAUDE.md, apps, docs, infra."
- Nếu sợ mất kiểm soát, yêu cầu Claude chỉ đọc/lập plan và không edit; chưa bật `acceptEdits`.
- Nếu không biết `.gitignore` đủ chưa, hỏi Claude review riêng `.gitignore` theo stack Node.js.
- Nếu generator Vite hỏi overwrite, chọn không overwrite và tạo folder khác để thử.
- Nếu lỡ tạo `.env`, xóa khỏi staging, thêm rule `.env` vào `.gitignore`, và không commit.

## Đáp án tham khảo hoặc kết quả kỳ vọng

Cấu trúc tối thiểu sau Day 02:

```txt
taskflow-ai/
  .git/
  .gitignore
  CLAUDE.md
  README.md
  apps/
    api/
      package.json
      tsconfig.json
      src/
        app.ts
        server.ts
        routes/
          health.ts
    web/
      package.json
      index.html
      src/
        App.tsx
        main.tsx
        styles.css
  docs/
    .gitkeep
  infra/
    .gitkeep
```

`README.md` nên thể hiện:

- Tên project: `taskflow-ai`.
- Mục tiêu: app quản lý task mini cho team kỹ thuật.
- Stack dự kiến: Node.js, TypeScript, Fastify, React, Vite, PostgreSQL, Redis, Docker Compose.
- Trạng thái: Day 02 scaffold only.
- Cảnh báo: không commit `.env` hoặc secret.

`.gitignore` tối thiểu:

```gitignore
node_modules/
dist/
build/
coverage/
.env
.env.*
!.env.example
*.log
.DS_Store
```

`CLAUDE.md` tối thiểu:

```md
# CLAUDE.md

## Project

taskflow-ai is a mini task management app for engineering teams.

## Stack kỳ vọng

- Backend: Node.js, TypeScript, Fastify.
- Frontend: React, Vite, TypeScript.
- Data: PostgreSQL, Redis.
- Infra: Docker Compose.

## Safety rules

- Do not read, create, or commit real secrets.
- Do not create `.env`; use `.env.example` only.
- Ask before running install, migration, delete, reset, or other destructive commands.
- Plan before editing multiple files.
- Summarize changed files after each task.
```

Kết quả kỳ vọng của `git status` trước commit:

```txt
Untracked files:
  .gitignore
  CLAUDE.md
  README.md
  apps/
  docs/
  infra/
```

Kết quả kỳ vọng sau commit:

```txt
nothing to commit, working tree clean
```

Nếu bạn chưa commit vì muốn review thêm, vẫn đạt yêu cầu nếu có `git diff --stat`, không có secret, và có ghi chú rõ phần còn cần kiểm tra.
