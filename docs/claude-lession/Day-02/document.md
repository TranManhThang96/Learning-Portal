# Document — Day 02

## Tóm tắt kiến thức

Day 02 tập trung vào setup môi trường và workflow cơ bản với Claude Code. Điểm chính:

- Cài hoặc kiểm tra Claude Code CLI trước khi làm việc.
- Luôn vào đúng thư mục project rồi chạy `claude`.
- Dùng `/help` để xem khả năng hiện có.
- Dùng `/init` để tạo guideline project như `CLAUDE.md`.
- Dùng `claude --continue` để tiếp tục session gần nhất trong thư mục hiện tại.
- Dùng `claude --resume` hoặc `/resume` để chọn session cần mở lại.
- Tạo repo sandbox `taskflow-ai`, không thao tác trên production.
- Scaffold backend/frontend theo lát cắt nhỏ, review diff sau mỗi bước.
- Không đưa secret, production credential, customer data hoặc token vào prompt.

## Sơ đồ tư duy hoặc luồng xử lý

```txt
Chuẩn bị máy
  |
  +-- kiểm tra git/node/claude
  |
  v
Tạo repo taskflow-ai
  |
  +-- git init
  +-- kiểm tra git status
  |
  v
Mở Claude Code từ root project
  |
  +-- claude
  +-- /help
  +-- /init
  |
  v
Tạo guideline và scaffold
  |
  +-- CLAUDE.md
  +-- README.md
  +-- .gitignore
  +-- apps/api
  +-- apps/web
  +-- docs
  +-- infra
  |
  v
Review và checkpoint
  |
  +-- git diff --stat
  +-- git diff
  +-- git add path rõ ràng
  +-- git commit
```

Luồng an toàn khi làm với Claude Code:

```txt
Prompt rõ mục tiêu
  -> Claude lập plan
  -> Developer duyệt phạm vi
  -> Claude edit hoặc đề xuất command
  -> Developer review diff/output
  -> Commit checkpoint
```

## Bảng so sánh

### Cách chạy Claude Code

| Tình huống | Cách làm | Khi nào dùng | Rủi ro |
| --- | --- | --- | --- |
| Mở trong root project | `cd taskflow-ai` rồi `claude` | Cách mặc định | Ít rủi ro nếu root đúng |
| Mở ở thư mục cha | `cd ~/work` rồi `claude` | Hầu như không nên dùng cho khóa học | Claude có thể thấy nhiều repo không liên quan |
| Mở trong subfolder | `cd apps/api` rồi `claude` | Khi chỉ làm backend hẹp | Claude có thể thiếu context root, README, CLAUDE.md |

### Permission mode giai đoạn setup

| Cách dùng | Mục đích | Nên dùng Day 02? | Ghi chú |
| --- | --- | --- | --- |
| Phiên mặc định với `claude` | Claude hỏi quyền khi cần sửa file hoặc chạy command | Có | Phù hợp khi mới học và repo còn lạ |
| Prompt "chỉ đọc/lập plan, không sửa file" | Khám phá và lập kế hoạch trước khi edit | Có | Đây là ràng buộc workflow, không phải thay thế permission |
| `claude --permission-mode acceptEdits` | Cho phép tạo/sửa file và auto-approve common filesystem commands trong working directory | Có, trong sandbox | Chỉ dùng khi phạm vi file rõ và review diff ngay sau đó |
| `.claude/settings.json` với `permissions.defaultMode: auto` | Đặt default permission cho project | Hạn chế | Cần thống nhất team vì ảnh hưởng mọi session dùng setting này |

### Scaffold strategy

| Chiến lược | Lợi ích | Chi phí/rủi ro | Phù hợp khi |
| --- | --- | --- | --- |
| Claude tạo skeleton, chưa install | Diff nhỏ, dễ học review | Scripts chưa chạy được ngay | Học workflow, repo mới |
| Dùng generator như Vite | Chuẩn tool, chạy nhanh sau install | Diff dài, kết quả thay đổi theo phiên bản | Team đã quen stack |
| Tự viết thủ công không dùng Claude | Kiểm soát cao nhất | Mất thời gian, ít học agent workflow | Khi policy chưa cho dùng AI |

### File cần có sau Day 02

| File/folder | Vai trò | Điều cần kiểm tra |
| --- | --- | --- |
| `CLAUDE.md` | Guideline cho Claude Code | Có rule secret, command nguy hiểm, workflow plan-first |
| `README.md` | Onboarding cho human | Không nói app đã hoàn chỉnh nếu chỉ scaffold |
| `.gitignore` | Chặn artifact và secret | Có `.env`, `.env.*`, `!.env.example`, `node_modules/`, `dist/`, `coverage/` |
| `apps/api/` | Backend scaffold | Không có database credential thật |
| `apps/web/` | Frontend scaffold | Không gọi API production |
| `docs/` | Tài liệu project | Có placeholder hoặc note rõ |
| `infra/` | Docker/infra sau này | Chưa cần compose thật nếu chưa học Docker |

## Lỗi thường gặp

### Chạy `claude` ở sai thư mục

Dấu hiệu:

- Claude nói về file không thuộc project.
- `/init` tạo guideline ở repo khác.
- `git status` không giống bạn kỳ vọng.

Cách tránh:

- Trước khi chạy `claude`, kiểm tra `pwd` hoặc `Get-Location`.
- Chạy `git rev-parse --show-toplevel` nếu repo đã có Git.

### Prompt quá rộng

Ví dụ xấu:

```txt
Hãy tạo app task management đầy đủ.
```

Vấn đề:

- Claude có thể tự thêm auth, database, UI, test, Docker.
- Diff lớn và khó review.
- Dễ sinh command install ngoài ý muốn.

Cách sửa:

```txt
Chỉ scaffold Day 02. Được phép tạo README.md, .gitignore, CLAUDE.md, apps/api, apps/web, docs, infra. Không cài dependency. Trước khi edit hãy lập plan.
```

### Commit nhầm `.env`

Dấu hiệu:

- `git status` thấy `.env`.
- `git diff` có credential hoặc connection string thật.

Cách tránh:

- Tạo `.gitignore` sớm.
- Chỉ dùng `.env.example`.
- Chạy `git status` trước `git add`.

### README nói quá trạng thái thật

Dấu hiệu:

- README ghi "run production" hoặc "fully functional" trong khi mới scaffold.
- Lệnh trong README chưa chạy được vì dependency chưa cài.

Cách sửa:

- Ghi rõ "Day 02 scaffold only".
- Tách "planned commands" và "verified commands".

### Cho Claude install quá sớm

Dấu hiệu:

- Có `node_modules/`, lockfile, nhiều package trước khi thống nhất stack.
- Lỗi network hoặc registry làm session lệch sang debugging môi trường.

Cách tránh:

- Day 02 ưu tiên skeleton trước.
- Nếu install, ghi rõ command, thư mục chạy, rủi ro và output kỳ vọng.

## Cách debug

### Kiểm tra CLI

```bash
claude --version
```

Nếu lỗi:

- Đóng mở lại terminal.
- Kiểm tra installer đã hoàn tất chưa.
- Kiểm tra `PATH`.
- Đọc lại quickstart official.

### Kiểm tra đang ở đúng repo

```bash
pwd
git status
git rev-parse --show-toplevel
```

Windows PowerShell:

```powershell
Get-Location
git status
git rev-parse --show-toplevel
```

Nếu `git rev-parse` báo lỗi, thư mục hiện tại chưa nằm trong Git repo hoặc bạn đang ở nhầm nơi.

### Kiểm tra file Claude vừa tạo

```bash
git diff --stat
git diff
```

Nếu diff quá lớn:

- Dừng implement.
- Yêu cầu Claude tóm tắt file đã sửa.
- Revert file không mong muốn bằng `git restore <path>` nếu chưa commit.

### Kiểm tra secret trước commit

```bash
git status
git diff -- . ':!package-lock.json'
```

Đọc kỹ các file:

- `.env`
- `README.md`
- `CLAUDE.md`
- file config trong `apps/api`
- file config trong `infra`

Nếu thấy secret:

1. Không commit.
2. Xóa khỏi file.
3. Nếu secret thật đã xuất hiện trong Git history, rotate secret theo policy nội bộ.

### Khi `/init` tạo guideline không đúng

Cách xử lý:

- Yêu cầu Claude sửa lại theo format ngắn hơn.
- Hoặc bỏ thay đổi:

```bash
git restore CLAUDE.md
```

Chỉ dùng `git restore` khi chắc chắn muốn mất thay đổi chưa commit trong file đó.

## Link tài liệu nên đọc

- Claude Code Quickstart: <https://code.claude.com/docs/en/quickstart>
- Claude Code Permissions: <https://code.claude.com/docs/en/permissions>
- GitHub Docs - About Git: <https://docs.github.com/en/get-started/using-git/about-git>
- Docker Compose Docs: <https://docs.docker.com/compose/>

Gợi ý đọc:

- Đọc quickstart trước khi cài hoặc khi `claude` không chạy.
- Đọc permissions trước khi bật `acceptEdits` hoặc đặt `permissions.defaultMode: auto`.
- Đọc Git basics nếu chưa quen `git status`, `git diff`, `git add`, `git commit`.
- Docker Compose chỉ cần đọc khái niệm ở Day 02; các ngày sau mới dùng sâu cho PostgreSQL/Redis.
