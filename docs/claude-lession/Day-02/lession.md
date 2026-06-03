# Day 02 — Setup môi trường và workflow cơ bản

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Cài hoặc kiểm tra Claude Code CLI trên máy local.
- Mở Claude Code đúng cách từ thư mục project bằng lệnh `claude`.
- Dùng `/help`, `/init` và biết cách tiếp tục session bằng `claude --continue`, `claude --resume` hoặc `/resume`.
- Tạo repo thực hành `taskflow-ai` bằng Git.
- Scaffold backend và frontend ở mức an toàn, chưa đụng production data.
- Yêu cầu Claude Code tạo `README.md`, `.gitignore`, cấu trúc folder và guideline ban đầu.
- Biết dùng permission mode phù hợp cho giai đoạn setup.
- Biết không đưa secret, production credential, token, private key hoặc dữ liệu khách hàng vào prompt.

Kết quả cuối bài là một repo `taskflow-ai` có cấu trúc ban đầu rõ ràng, có Git, có README, có `.gitignore`, có scaffold backend/frontend tối thiểu, và có thể mở lại bằng Claude Code.

## 2. Bối cảnh thực tế

Setup môi trường là phần dễ bị xem nhẹ. Developer thường mở AI coding tool trong một thư mục lộn xộn, prompt quá rộng, để AI tự chạy lệnh install hoặc sửa nhiều file không kiểm soát. Sau 30 phút, repo đã có nhiều dependency, nhiều file sinh ra, nhưng không ai biết quyết định kiến trúc nào là chủ ý của team và quyết định nào là do AI đoán.

Claude Code giải quyết tốt phần setup khi bạn cho nó một project boundary rõ:

- Project đang nằm ở đâu.
- Stack nào được phép dùng.
- File nào được phép tạo.
- Lệnh nào được phép chạy.
- Tiêu chí scaffold ban đầu là gì.
- Việc nào cần hỏi lại trước khi thực hiện.

Không nên dùng Claude Code để setup nếu bạn đang ở máy production, đang có secret thật trong terminal, đang mở repo công ty có dữ liệu nhạy cảm mà chưa có policy, hoặc chưa biết cách review diff và rollback.

Trong khóa học này, mọi thao tác thực hành nằm trong repo sandbox `taskflow-ai`. Mục tiêu không phải tạo app hoàn chỉnh ngay Day 02, mà là dựng nền móng đủ sạch để các ngày sau build tiếp.

## 3. Kiến thức nền

### Claude Code CLI

Claude Code là agentic coding tool chạy trong terminal. Workflow cơ bản là:

1. Bạn vào thư mục project.
2. Chạy `claude`.
3. Claude đọc ngữ cảnh được phép đọc.
4. Bạn giao task bằng prompt.
5. Claude đề xuất plan, đọc file, sửa file hoặc chạy command tùy quyền bạn cấp.
6. Bạn review output, diff, command result rồi mới tiếp tục.

Điểm quan trọng: Claude Code làm việc theo thư mục hiện tại. Nếu bạn chạy `claude` ở nhầm nơi, nó có thể hiểu sai project boundary. Luôn kiểm tra `pwd` hoặc `Get-Location` trước khi mở session.

### Slash command và resume cơ bản

- `/help`: xem command và khả năng hiện có trong Claude Code.
- `/init`: yêu cầu Claude đọc project và tạo guideline như `CLAUDE.md` hoặc `.claude/CLAUDE.md`. File này có thể chứa coding standards, command thường dùng, testing requirements, security rules.
- `claude --continue`: chạy từ terminal trong thư mục project để tiếp tục session gần nhất của thư mục hiện tại.
- `claude --resume` hoặc `/resume`: chọn một session cụ thể để mở lại khi bạn có nhiều session.

Day 02 chỉ dùng các command này ở mức nhập môn. Các ngày sau sẽ học kỹ session, context, permission và CLAUDE.md.

### Permission mode cần biết sớm

Day 02 không cần học hết hệ permission. Cần nắm các điểm thực tế sau:

Trong Day 02, ưu tiên:

- Phiên mặc định: phù hợp khi mới setup, vì Claude sẽ hỏi trước các thao tác cần quyền.
- Prompt chỉ đọc hoặc chỉ lập plan: dùng khi chưa chắc nên scaffold kiểu gì. Đây là ràng buộc trong prompt, không thay thế review diff.
- `claude --permission-mode acceptEdits`: dùng được trong sandbox khi bạn đã giới hạn rõ file được phép tạo/sửa. Mode này cho phép Claude tạo/sửa file và auto-approve các common filesystem commands trong working directory.
- `.claude/settings.json` có thể đặt `permissions.defaultMode` là `auto`, nhưng chỉ nên làm sau khi team thống nhất rule và hiểu rủi ro.

Không bật mode tự động hơn trong repo thật nếu bạn chưa biết Claude sắp sửa file nào, chạy command nào, và rollback ra sao.

### Secret và dữ liệu nhạy cảm

Không đưa các nội dung sau vào prompt:

- API key, database password, OAuth secret, SSH private key.
- Production credential.
- Token trong `.env`.
- Log có chứa user data, email, số điện thoại, payment data.
- Connection string thật.

Trong project học, nếu cần biến môi trường, chỉ tạo `.env.example` với giá trị giả như `DATABASE_URL=postgresql://user:password@localhost:5432/taskflow_ai`.

### Project xuyên suốt `taskflow-ai`

`taskflow-ai` là app quản lý task mini cho team kỹ thuật. Day 02 tạo nền:

```txt
taskflow-ai/
  apps/
    api/
    web/
  docs/
  infra/
  README.md
  .gitignore
```

Backend và frontend chỉ scaffold tối thiểu. Chưa cần database thật, authentication, deployment hoặc business logic phức tạp.

## 4. Step-by-step thực hành

### Tổng thời lượng đề xuất

- 15 phút: kiểm tra tool local.
- 20 phút: tạo repo `taskflow-ai`.
- 35 phút: mở Claude Code, chạy `/init`, tạo guideline.
- 35 phút: scaffold backend/frontend an toàn.
- 15 phút: review diff, commit checkpoint.

### Bước 1: Kiểm tra terminal, Git và Claude Code

Chạy ở terminal bất kỳ.

macOS/Linux:

```bash
pwd
git --version
node --version
claude --version
```

Windows PowerShell:

```powershell
Get-Location
git --version
node --version
claude --version
```

Giải thích:

- `pwd` hoặc `Get-Location`: in ra thư mục hiện tại để tránh chạy nhầm nơi.
- `git --version`: kiểm tra Git đã cài.
- `node --version`: kiểm tra Node.js, cần cho stack Node.js + TypeScript.
- `claude --version`: kiểm tra Claude Code CLI đã cài và nhận được trong `PATH`.

Kết quả kỳ vọng:

- Git in ra phiên bản, ví dụ `git version ...`.
- Node in ra phiên bản, ví dụ `v20...` hoặc mới hơn tùy máy.
- Claude in ra phiên bản Claude Code CLI.

Rủi ro:

- Nếu `claude` không được nhận diện, terminal chưa thấy CLI trong `PATH` hoặc Claude Code chưa cài.
- Nếu `node` quá cũ, scaffold frontend/backend có thể lỗi.
- Không paste token hay credential vào terminal để "test nhanh".

### Bước 2: Cài Claude Code nếu máy chưa có

Nếu `claude --version` chưa chạy được, mở Claude Code Quickstart chính thức và chọn installer phù hợp với hệ điều hành. Không copy lệnh cài đặt từ blog, gist hoặc output AI cũ nếu chưa đối chiếu official docs.

Sau khi cài xong, đóng mở lại terminal rồi kiểm tra:

```bash
claude --version
```

Giải thích:

- `claude --version`: xác nhận Claude Code CLI đã có trong `PATH`.
- Chạy ở terminal người dùng, không chạy trong repo production.
- Nếu công ty quản lý máy bằng policy riêng, dùng hướng dẫn nội bộ thay vì tự cài.

Kết quả kỳ vọng:

- `claude --version` trả về phiên bản.

Rủi ro:

- Installer có thể thay đổi theo thời điểm, nên Day 02 không nên hard-code lệnh cài nếu chưa kiểm tra official docs.
- Không dùng `sudo` hoặc quyền admin nếu installer không yêu cầu.
- Không paste token, credential hoặc private key vào terminal để "fix cài đặt".

### Bước 3: Tạo repo `taskflow-ai`

Chọn một thư mục sandbox, ví dụ `~/work` hoặc `D:\my-source`.

macOS/Linux:

```bash
mkdir -p ~/work/taskflow-ai
cd ~/work/taskflow-ai
git init
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path D:\my-source\taskflow-ai
Set-Location D:\my-source\taskflow-ai
git init
```

Giải thích:

- `mkdir -p` hoặc `New-Item -Force`: tạo thư mục project nếu chưa có.
- `cd` hoặc `Set-Location`: vào đúng thư mục project.
- `git init`: biến thư mục này thành Git repo local.

Kết quả kỳ vọng:

- Git báo đã tạo repository, thường là `.git/`.
- `git status` sẽ thấy repo chưa có commit.

Kiểm tra:

```bash
git status
```

Rủi ro:

- Nếu chạy `git init` trong nhầm thư mục, bạn có thể tạo repo ở nơi không mong muốn.
- Không tạo project trong thư mục chứa credential hoặc dump production.

### Bước 4: Mở Claude Code trong project

Chạy trong thư mục gốc `taskflow-ai`.

```bash
claude
```

Giải thích:

- Lệnh này mở Claude Code session cho thư mục hiện tại.
- Claude sẽ làm việc dựa trên project boundary này.

Kết quả kỳ vọng:

- Terminal chuyển sang Claude Code interactive session.
- Bạn có thể nhập prompt hoặc slash command.

Rủi ro:

- Nếu mở ở thư mục cha quá rộng, Claude có thể thấy nhiều repo không liên quan.
- Nếu project có file nhạy cảm, hãy dừng lại, kiểm tra `.gitignore`, `.env`, policy trước khi tiếp tục.

Trong Claude Code, chạy:

```txt
/help
```

Mục tiêu:

- Xem command có sẵn.
- Kiểm tra môi trường hoạt động.
- Làm quen với cách Claude hiển thị quyền đọc/sửa/chạy lệnh.

Nếu đây là repo sandbox và bạn muốn giảm số lần approve thao tác tạo/sửa file, có thể thoát session rồi mở lại bằng:

```bash
claude --permission-mode acceptEdits
```

Giải thích:

- `--permission-mode acceptEdits`: cho phép Claude tạo/sửa file và auto-approve các common filesystem commands trong working directory.
- Chỉ dùng khi bạn đang ở đúng root `taskflow-ai`, phạm vi file đã rõ, và sẽ review `git diff` ngay sau mỗi cụm thay đổi.

Không đặt `.claude/settings.json` với `permissions.defaultMode: auto` ngay trong bài đầu nếu bạn chưa có rule team và chưa quen review diff.

### Bước 5: Dùng `/init` để tạo guideline project

Trong Claude Code, nhập:

```txt
/init
```

Mục tiêu:

- Cho Claude đọc cấu trúc project hiện tại.
- Tạo hoặc cập nhật guideline như `CLAUDE.md`.
- Ghi lại coding standards, command thường dùng, testing requirements, security rules.

Vì repo đang trống, sau `/init` hãy dùng prompt này:

```txt
Project này là taskflow-ai, app quản lý task mini cho team kỹ thuật.

Hãy tạo CLAUDE.md ngắn gọn cho project mới, chỉ gồm:
- Mục tiêu project.
- Stack dự kiến: Node.js, TypeScript, Fastify cho backend; React, Vite cho frontend; PostgreSQL, Redis, Docker Compose cho infra.
- Quy tắc an toàn: không đọc hoặc ghi secret thật, không tạo .env có credential thật, không chạy lệnh destructive.
- Các lệnh phổ biến dự kiến, đánh dấu là sẽ cập nhật sau khi package.json tồn tại.
- Workflow: luôn plan trước khi sửa nhiều file, luôn yêu cầu review diff.

Chỉ tạo hoặc sửa CLAUDE.md. Không tạo code app ở bước này.
```

Kết quả kỳ vọng:

- Claude đề xuất tạo `CLAUDE.md`.
- Nội dung ngắn, có guideline rõ.
- Không có secret thật.

Rủi ro:

- Nếu prompt quá rộng, Claude có thể tạo quá nhiều file ngay từ đầu.
- Nếu Claude tự thêm dependency hoặc command chưa kiểm chứng, yêu cầu nó đánh dấu là "dự kiến" thay vì "đã có".

Rollback khi sai:

```bash
git status
git diff
git restore CLAUDE.md
```

Giải thích:

- `git status`: xem file nào đã thay đổi.
- `git diff`: xem nội dung thay đổi.
- `git restore CLAUDE.md`: bỏ thay đổi ở `CLAUDE.md` nếu chưa commit.

Rủi ro:

- `git restore` xóa thay đổi chưa commit của file được chỉ định. Chỉ chạy khi đã chắc chắn muốn bỏ.

### Bước 6: Tạo cấu trúc folder bằng Claude Code

Trong Claude Code, dùng prompt:

```txt
Hãy tạo cấu trúc folder ban đầu cho taskflow-ai.

Phạm vi được phép tạo:
- apps/api/
- apps/web/
- docs/
- infra/
- README.md
- .gitignore

Yêu cầu:
- Chưa cài dependency.
- Chưa tạo secret thật.
- README.md mô tả mục tiêu, stack dự kiến, cách chạy sau khi scaffold hoàn chỉnh.
- .gitignore cho Node.js, logs, build output, .env, editor files.
- Tạo file placeholder cần thiết để Git giữ folder, ví dụ .gitkeep nếu folder chưa có code.

Trước khi sửa file, hãy tóm tắt plan và danh sách file sẽ tạo.
```

Kết quả kỳ vọng:

- Claude đưa plan trước.
- Claude tạo đúng các folder/file được phép.
- `.gitignore` có `.env`, `node_modules/`, `dist/`, `coverage/`.
- `README.md` chưa chứa command giả khẳng định "đã chạy được" nếu chưa có scaffold.

Kiểm tra ngoài terminal:

```bash
find . -maxdepth 3 -type f | sort
git diff --stat
git diff
```

Windows PowerShell tương đương:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
git diff --stat
git diff
```

Giải thích:

- `find` hoặc `Get-ChildItem`: liệt kê file đã tạo.
- `git diff --stat`: xem tóm tắt số file và số dòng thay đổi.
- `git diff`: review nội dung chi tiết.

Rủi ro:

- `git diff` có thể dài nếu Claude tạo quá nhiều file. Khi đó hãy yêu cầu Claude thu hẹp scaffold.

### Bước 7: Scaffold backend ở mức an toàn

Bạn có hai lựa chọn. Day 02 khuyến nghị lựa chọn A nếu muốn giữ tốc độ và giảm rủi ro.

Lựa chọn A: để Claude tạo scaffold file tối thiểu, chưa cài package.

Prompt trong Claude Code:

```txt
Scaffold backend tối thiểu trong apps/api cho Node.js + TypeScript + Fastify.

Phạm vi:
- apps/api/package.json
- apps/api/tsconfig.json
- apps/api/src/server.ts
- apps/api/src/app.ts
- apps/api/src/routes/health.ts
- apps/api/src/config/env.example.ts hoặc docs ghi chú env, nhưng không tạo .env thật.

Yêu cầu:
- Chỉ tạo code skeleton health check.
- Không cài dependency.
- Không thêm database connection thật.
- package.json có scripts dự kiến: dev, build, test, typecheck.
- Nếu lệnh nào chưa chạy được vì dependency chưa cài, ghi rõ trong README hoặc comment ngắn.
- Trước khi edit, liệt kê file sẽ tạo.
```

Kết quả kỳ vọng:

- Có skeleton backend rõ ràng.
- Không có `.env`.
- Không có connection string thật.

Lựa chọn B: dùng package manager để cài dependency ngay.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
npm init -y
npm pkg set private=true
npm pkg set "workspaces[0]=apps/*"
mkdir -p apps/api
cd apps/api
npm init -y
npm install fastify @fastify/cors
npm install -D typescript tsx vitest @types/node
```

Giải thích:

- `npm init -y`: tạo `package.json`.
- `npm pkg set private=true`: đánh dấu root workspace không publish.
- `npm pkg set "workspaces[0]=apps/*"`: khai báo workspace.
- `mkdir -p apps/api`: tạo backend folder.
- `npm install`: tải dependency runtime và dev dependency.

Kết quả kỳ vọng:

- Có `package.json`, `package-lock.json`, `node_modules/`.
- `apps/api/package.json` có dependency.

Rủi ro:

- Lệnh install tải code từ npm registry, cần internet và policy cho phép.
- Phiên bản dependency có thể khác theo thời điểm.
- Không nên dùng B nếu đang dạy workflow kiểm soát diff lần đầu hoặc mạng công ty có proxy.

### Bước 8: Scaffold frontend ở mức an toàn

Lựa chọn A: Claude tạo skeleton tối thiểu, chưa cài package.

Prompt trong Claude Code:

```txt
Scaffold frontend tối thiểu trong apps/web cho React + Vite + TypeScript.

Phạm vi:
- apps/web/package.json
- apps/web/index.html
- apps/web/src/main.tsx
- apps/web/src/App.tsx
- apps/web/src/styles.css

Yêu cầu:
- UI chỉ có màn hình placeholder Taskflow AI và trạng thái "frontend scaffold".
- Không gọi API thật.
- Không cài dependency.
- package.json có scripts dự kiến: dev, build, test, lint.
- Không thêm asset nặng.
- Trước khi edit, liệt kê file sẽ tạo.
```

Lựa chọn B: dùng Vite generator.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
npm create vite@latest apps/web -- --template react-ts
```

Giải thích:

- `npm create vite@latest`: tải và chạy generator Vite mới nhất.
- `apps/web`: nơi tạo frontend app.
- `--template react-ts`: dùng React + TypeScript.

Kết quả kỳ vọng:

- Có `apps/web/package.json`.
- Có `apps/web/src/`.
- Có hướng dẫn `npm install` và `npm run dev`.

Rủi ro:

- Generator có thể thay đổi output theo phiên bản Vite.
- Nếu folder `apps/web` đã có file, generator có thể hỏi overwrite. Không chọn overwrite nếu chưa review.

### Bước 9: Tạo `.gitignore` và README bằng Claude Code

Nếu chưa có, dùng prompt:

```txt
Review README.md và .gitignore hiện tại.

Yêu cầu README.md:
- Mô tả taskflow-ai.
- Ghi stack dự kiến.
- Ghi cấu trúc folder.
- Ghi setup status: Day 02 scaffold only.
- Ghi nguyên tắc không commit .env hoặc secret.

Yêu cầu .gitignore:
- node_modules/
- dist/
- build/
- coverage/
- .env
- .env.*
- !.env.example
- logs và file editor phổ biến.

Chỉ sửa README.md và .gitignore. Không sửa code app.
```

Kết quả kỳ vọng:

- README trung thực, không nói app đã production-ready.
- `.gitignore` chặn secret và build artifact.

Rủi ro:

- Pattern `.env.*` có thể ignore cả `.env.example`; cần có `!.env.example` để giữ example.

### Bước 10: Review diff và tạo commit checkpoint

Chạy trong root `taskflow-ai`.

```bash
git status
git diff --stat
git diff
```

Giải thích:

- `git status`: xem file mới/thay đổi.
- `git diff --stat`: xem tổng quan thay đổi.
- `git diff`: đọc từng thay đổi trước khi commit.

Kết quả kỳ vọng:

- Chỉ có file scaffold Day 02.
- Không có `.env`, secret, credential.
- Không có file ngoài `taskflow-ai`.

Nếu ổn, commit:

```bash
git add README.md .gitignore CLAUDE.md apps docs infra
git commit -m "chore: scaffold taskflow ai project"
```

Giải thích:

- `git add`: đưa file scaffold vào staging area.
- `git commit`: tạo checkpoint để các ngày sau có thể rollback.

Rủi ro:

- `git add .` dễ thêm nhầm file. Day 02 nên add rõ path.
- Trước commit luôn chạy `git status` để đảm bảo không có secret.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```txt
Bạn đang ở repo taskflow-ai mới khởi tạo.

Hãy đọc cấu trúc hiện tại và trả lời:
- Repo đang có những folder/file nào?
- File nào là guideline cho Claude Code?
- Backend và frontend đã ở mức scaffold nào?
- Có dấu hiệu secret hoặc file không nên commit không?

Chỉ đọc và phân tích. Không sửa file.
```

### Prompt lập plan

```txt
Mục tiêu: scaffold project taskflow-ai cho khóa học Claude Code Day 02.

Ràng buộc:
- Chỉ tạo file trong README.md, .gitignore, CLAUDE.md, apps/, docs/, infra/.
- Không cài dependency nếu chưa hỏi lại.
- Không tạo .env thật.
- Không chạy lệnh destructive.

Hãy lập plan theo từng bước và liệt kê file dự kiến tạo/sửa. Dừng lại chờ tôi xác nhận trước khi edit.
```

### Prompt implement

```txt
Thực hiện plan đã được duyệt.

Chỉ tạo scaffold tối thiểu:
- apps/api với Node.js + TypeScript + Fastify skeleton.
- apps/web với React + Vite + TypeScript skeleton.
- README.md và .gitignore.
- docs/ và infra/ có placeholder.

Sau khi sửa, tóm tắt file đã tạo và lệnh nào tôi cần tự chạy để kiểm tra.
```

### Prompt review

```txt
Review toàn bộ diff hiện tại của taskflow-ai.

Tập trung vào:
- Có secret hoặc credential nào bị commit nhầm không?
- README có nói quá trạng thái thực tế không?
- .gitignore đã chặn .env, node_modules, dist, coverage chưa?
- Scaffold backend/frontend có vượt quá phạm vi Day 02 không?
- Có file nào nên bỏ khỏi commit không?

Không sửa file. Trả lời theo mức độ nghiêm trọng.
```

### Prompt viết test hoặc verification

```txt
Với scaffold hiện tại, hãy đề xuất verification tối thiểu cho Day 02.

Yêu cầu:
- Không giả định dependency đã install nếu package-lock chưa có.
- Nếu chưa chạy được test, nói rõ vì sao.
- Đưa ra checklist command an toàn để tôi tự chạy.
- Không cài package và không sửa file.
```

## 6. Trade-offs

### Scaffold bằng Claude Code trước, install sau

Lợi ích:

- Diff nhỏ, dễ review.
- Ít rủi ro dependency thay đổi theo thời điểm.
- Phù hợp để học cách kiểm soát agent trước khi cho chạy command.

Rủi ro:

- Scripts trong `package.json` có thể chưa chạy được cho đến khi install dependency.
- Có thể cần chỉnh lại sau khi dùng generator thật.

Nên dùng khi:

- Team mới bắt đầu dùng Claude Code.
- Bạn muốn dạy workflow plan-first.
- Repo đang ở giai đoạn kiến trúc ban đầu.

### Dùng generator như Vite ngay

Lợi ích:

- Có cấu trúc chuẩn từ tool chính thức.
- Scripts thường chạy được nhanh sau `npm install`.
- Ít phải tự viết boilerplate.

Rủi ro:

- Generator tạo nhiều file hơn, diff dài hơn.
- Version mới có thể đổi cấu trúc.
- Claude có thể hiểu nhầm file generator tạo là quyết định kiến trúc của team.

Nên dùng khi:

- Bạn đã quen với Vite.
- Team chấp nhận dependency install trong setup.
- Có internet và policy package registry rõ ràng.

### Permission chặt hay mở

Chặt hơn với phiên mặc định và prompt chỉ đọc/lập plan:

- An toàn hơn.
- Chậm hơn vì cần duyệt nhiều thao tác.
- Tốt cho ngày đầu setup và repo lạ.

Mở hơn với `claude --permission-mode acceptEdits` hoặc `permissions.defaultMode: auto` trong `.claude/settings.json`:

- Nhanh hơn trong sandbox.
- Rủi ro tạo/sửa nhiều file ngoài ý muốn.
- Chỉ dùng khi phạm vi file rất rõ, working directory đúng, và bạn review diff ngay sau đó.
- Với setting `auto`, cần thống nhất trong team vì nó ảnh hưởng mặc định của project, không chỉ một session.

## 7. Best practices

- Luôn mở Claude Code từ root project, không mở từ thư mục cha chứa nhiều repo.
- Bắt đầu bằng prompt đọc hiểu hoặc plan, nhất là khi repo mới.
- Ghi rõ file/folder được phép sửa.
- Yêu cầu Claude liệt kê file sẽ tạo trước khi edit.
- Không cho Claude chạy install, migration, delete, reset Git nếu chưa nêu rõ rủi ro.
- Tạo `.gitignore` trước khi tạo `.env` hoặc chạy tool sinh artifact.
- Chỉ dùng `.env.example` với giá trị giả.
- Không paste secret vào prompt để Claude "kiểm tra giúp".
- Sau mỗi cụm thay đổi, chạy `git diff --stat` và `git diff`.
- Commit checkpoint nhỏ sau khi scaffold ổn.
- README phải phản ánh đúng trạng thái: scaffold, chưa production-ready.
- Với project team, đưa rule quan trọng vào `CLAUDE.md` để session sau có context chuẩn.

## 8. Performance / cost / context

Setup project mới tưởng rẻ nhưng có thể tốn context nếu prompt mơ hồ. Ví dụ "hãy tạo app quản lý task đầy đủ" khiến Claude phải tự quyết định backend, frontend, database, auth, test, deployment. Kết quả thường là nhiều file, nhiều dependency, khó review.

Cách tối ưu:

- Chia task thành bước nhỏ: guideline, folder, backend, frontend, README, review.
- Cho Claude đọc ít file cần thiết. Repo mới thì context nhẹ, nhưng vẫn cần boundary rõ.
- Dùng prompt yêu cầu "chỉ đọc và lập plan, không sửa file" khi chỉ cần phân tích.
- Dùng prompt có acceptance criteria thay vì yêu cầu chung chung.
- Không yêu cầu Claude giải thích lại toàn bộ official docs trong session coding nếu chỉ cần thực hành.
- Sau scaffold, commit checkpoint để ngày sau không cần mô tả lại mọi quyết định.

Chi phí thời gian hợp lý cho Day 02:

- Nếu không install dependency: 60-90 phút là đủ để có scaffold sạch.
- Nếu dùng generator và install: thêm 20-30 phút cho lỗi môi trường, network, package manager.

Nguyên tắc context:

- `CLAUDE.md` là memory project, không phải nơi nhồi mọi thứ.
- README dành cho human và onboarding.
- Prompt trong session chỉ nên chứa mục tiêu hiện tại, ràng buộc, acceptance criteria.

## 9. Checklist cuối bài

- [ ] Tôi chạy được `claude --version`.
- [ ] Tôi biết cài Claude Code bằng installer phù hợp hệ điều hành.
- [ ] Tôi tạo được repo Git `taskflow-ai`.
- [ ] Tôi mở Claude Code từ root `taskflow-ai` bằng `claude`.
- [ ] Tôi dùng được `/help`.
- [ ] Tôi biết dùng `claude --continue` cho session gần nhất và `claude --resume` hoặc `/resume` khi cần chọn session.
- [ ] Tôi dùng được `/init` hoặc tạo được `CLAUDE.md` guideline ban đầu.
- [ ] Tôi tạo được `README.md` trung thực về trạng thái scaffold.
- [ ] Tôi tạo được `.gitignore` chặn `.env`, `node_modules`, build output, coverage.
- [ ] Tôi có folder `apps/api`, `apps/web`, `docs`, `infra`.
- [ ] Tôi không đưa secret hoặc production credential vào prompt.
- [ ] Tôi review `git diff` trước khi commit.
- [ ] Tôi có commit checkpoint đầu tiên cho Day 02.

## 10. Bài tập

### Bài 1 — Cơ bản

Tạo repo `taskflow-ai`, chạy `git init`, mở Claude Code bằng `claude`, chạy `/help`, sau đó yêu cầu Claude giải thích project boundary hiện tại mà không sửa file.

Kết quả cần có:

- Screenshot hoặc ghi chú kết quả `claude --version`.
- Ghi chú thư mục root project.
- Không có file nào bị tạo ngoài ý muốn.

### Bài 2 — Thực tế

Dùng Claude Code tạo `CLAUDE.md`, `README.md`, `.gitignore` và cấu trúc folder `apps/api`, `apps/web`, `docs`, `infra`.

Ràng buộc:

- Claude phải lập plan trước.
- Không cài dependency.
- Không tạo `.env`.
- Sau khi xong, bạn phải review `git diff`.

Kết quả cần có:

- `git diff --stat`.
- Nội dung `.gitignore` có rule cho `.env`.
- README ghi rõ "Day 02 scaffold only" hoặc nội dung tương đương.

### Bài 3 — Nâng cao

Tạo branch thử nghiệm và so sánh scaffold thủ công với output từ generator như Vite, nhưng không overwrite `apps/web` chính.

Ràng buộc:

- Tạo branch riêng trước khi thử.
- Nếu chạy generator, tạo vào folder khác như `apps/web-generated`.
- Không merge branch thử nghiệm nếu chưa review.
- Ghi lại file nào generator tạo thêm và file nào không cần cho Day 02.

Kết quả cần có:

- Bảng so sánh ngắn giữa skeleton và generator.
- Ghi chú rủi ro về dependency install, output thay đổi theo version, và overwrite folder.
- Quyết định giữ scaffold hiện tại hay lên plan migration.

### Bài 4 — Review & Reflection

Yêu cầu Claude review diff hiện tại nhưng không sửa file.

Checklist review:

- Có secret, `.env`, credential hoặc production data không?
- File tạo ra có đúng phạm vi Day 02 không?
- README có nói đúng trạng thái scaffold không?
- `.gitignore` có chặn `.env`, `node_modules`, `dist`, `coverage` không?
- Bạn sẽ dùng phiên mặc định hay `claude --permission-mode acceptEdits` ở Day 03, và vì sao?

Kết quả cần có:

- Danh sách finding theo mức Critical/High/Medium/Low.
- Ghi chú rollback nếu cần dùng `git restore <path>`.
- Commit checkpoint hoặc lý do chưa commit.
- Một ghi chú áp dụng cho project cá nhân: rule nào sẽ đưa vào `CLAUDE.md`, rule nào chặn secret, rule nào yêu cầu hỏi lại trước command nguy hiểm.
