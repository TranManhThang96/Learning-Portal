# Day 07 — Khám phá codebase lớn

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Dùng Claude Code để khám phá một repo lớn theo hướng có bằng chứng, không hỏi chung chung kiểu "giải thích toàn bộ codebase".
- Yêu cầu Claude map architecture của `taskflow-ai`: frontend, backend, database, cache, test, tooling, và luồng runtime chính.
- Tạo dependency map ở mức module: module nào gọi module nào, phụ thuộc qua import, API, database table, queue, cache, hoặc config.
- Tìm entrypoint quan trọng: server bootstrap, route registration, frontend bootstrap, test setup, migration/seed, Docker Compose.
- Nhận diện bounded context trong project: tasks, users/auth, comments, notifications, reporting, shared infrastructure.
- Phân biệt hot path với code ít dùng để ưu tiên đọc đúng file trước khi sửa feature.
- Nhận diện và giảm rủi ro hallucination khi Claude chưa đọc đủ file nhưng vẫn tự tin kết luận.
- Cho Claude Code tạo `ARCHITECTURE.md` trong `taskflow-ai` và yêu cầu Claude chỉ ra module cần đọc trước khi sửa một feature mới.

## 2. Bối cảnh thực tế

Ở repo nhỏ, bạn có thể đọc vài file là hiểu flow. Ở repo team sau vài tháng, `taskflow-ai` có thể đã có backend TypeScript, frontend React, database migration, Redis cache, test integration, GitHub workflow, và nhiều convention nằm rải rác trong code. Khi nhận task "thêm comments cho task" hoặc "thêm rule SLA", lỗi phổ biến là nhảy thẳng vào file có tên gần đúng rồi sửa. Với AI, lỗi này còn nguy hiểm hơn vì Claude Code có thể viết patch rất nhanh dựa trên giả định chưa kiểm chứng.

Claude Code hữu ích nhất ở giai đoạn này khi bạn dùng nó như một architectural scout: đọc có mục tiêu, ghi lại bằng chứng, hỏi lại khi thiếu thông tin, và tạo artifact để team dùng lại. Artifact tốt không chỉ là mô tả đẹp; nó phải trả lời được câu hỏi thực dụng: "Trước khi sửa feature này, cần đọc file/module nào, theo thứ tự nào, và vì sao?"

Không nên dùng Claude Code để tự động khám phá codebase khi:

- Repo chứa secret, production dump, log khách hàng, hoặc file nhạy cảm chưa được loại khỏi context.
- Bạn đang ở incident production cần thao tác khẩn cấp và chưa có người chịu trách nhiệm review.
- Codebase có nhiều thay đổi local chưa commit, khó phân biệt artifact của AI với thay đổi của developer khác.
- Bạn muốn Claude "đọc toàn bộ repo" mà không có câu hỏi cụ thể; cách này tốn token, nhiễu context, và dễ tạo kết luận sai.

## 3. Kiến thức nền

Khám phá codebase lớn nên đi theo hướng evidence-first. Claude Code có thể suy luận nhanh, nhưng mọi kết luận quan trọng phải gắn với file đã đọc, symbol đã thấy, hoặc command read-only đã chạy. Nếu Claude nói "module tasks dùng repository pattern", bạn cần yêu cầu nó chỉ ra file nào chứng minh điều đó.

Các khái niệm cần dùng trong Day 07:

| Khái niệm | Ý nghĩa thực tế trong `taskflow-ai` | Câu hỏi cần Claude trả lời |
| --- | --- | --- |
| Architecture map | Bản đồ các phần chính của hệ thống và cách chúng tương tác. | Backend, frontend, database, cache, test, Docker nằm ở đâu? |
| Dependency map | Quan hệ phụ thuộc giữa module, package, route, service, repository, table, hoặc external service. | Nếu sửa module tasks, module nào có thể bị ảnh hưởng? |
| Entrypoint | Điểm code bắt đầu chạy một luồng. | Request vào backend từ file nào? UI mount ở đâu? Test setup chạy ở đâu? |
| Bounded context | Ranh giới nghiệp vụ tương đối độc lập. | Tasks, users/auth, comments, notifications có tách rõ không? |
| Hot path | Luồng chạy thường xuyên hoặc có impact cao. | Tạo task, cập nhật status, list board, auth middleware đi qua file nào? |
| Hallucination risk | Claude kết luận vượt quá bằng chứng đã đọc. | Kết luận nào là fact, kết luận nào chỉ là inference? |

Trong một repo TypeScript phổ biến, entrypoint có thể là `backend/src/main.ts`, `backend/src/server.ts`, `frontend/src/main.tsx`, `docker-compose.yml`, hoặc script trong `package.json`. Nhưng bạn không được hardcode giả định này vào prompt. Hãy yêu cầu Claude tìm bằng `rg --files`, `package.json`, import graph, route registration, và script test/build thật.

Dependency map có nhiều lớp:

- Compile-time dependency: import/export giữa file TypeScript.
- Runtime dependency: route gọi service, service gọi repository, repository gọi database.
- Data dependency: module phụ thuộc table, enum, migration, cache key.
- Operational dependency: Docker service, environment variable, CI workflow, test database.
- Ownership dependency: module nào có convention riêng trong `CLAUDE.md` hoặc tài liệu team.

Claude Code docs hiện hành khuyến nghị dùng plan mode để đọc và hiểu codebase trước khi sửa. Slash commands như `/context` và `/compact` có thể hỗ trợ quản lý session khi exploration dài. Project memory trong `CLAUDE.md` giúp giữ conventions qua session mới. Permissions nên được hạn chế khi mới exploration: ưu tiên đọc, grep, list file, diff; chưa cấp quyền edit hoặc command nguy hiểm. Subagents/agents có thể dùng để tách context cho backend, frontend, security review, nhưng Day 07 chỉ nhắc ở mức chiến lược; phần triển khai sâu dành cho Day 14.

## 4. Step-by-step thực hành

Mục tiêu thực hành: cho Claude Code khám phá `taskflow-ai`, tạo `ARCHITECTURE.md`, và sinh danh sách module cần đọc trước khi sửa feature `task comments`.

### Bước 1: Kiểm tra trạng thái repo

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này kiểm tra working tree. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu repo đang có thay đổi của bạn hoặc đồng đội, artifact `ARCHITECTURE.md` có thể lẫn với diff khác, làm review khó hơn.

Xem cấu trúc file ở mức cao:

```bash
rg --files -g "package.json" -g "docker-compose*.yml" -g "CLAUDE.md" -g "README.md"
```

Chạy ở root `taskflow-ai`. Lệnh này liệt kê các file định hướng project. Output kỳ vọng có `package.json`, có thể có `backend/package.json`, `frontend/package.json`, `docker-compose.yml`, `CLAUDE.md`. Rủi ro thấp vì read-only; nếu không có `rg`, dùng công cụ tìm file tương đương của môi trường.

### Bước 2: Mở Claude Code ở plan mode

Chạy trong root `taskflow-ai`:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude Code ở mode phù hợp để đọc và lập plan trước khi sửa. Output kỳ vọng là session Claude sẵn sàng nhận prompt. Rủi ro chính không nằm ở command, mà ở prompt quá rộng khiến Claude đọc lan man và tốn context.

Prompt exploration:

```text
Bạn đang ở repo taskflow-ai. Hãy khám phá codebase để tạo bản đồ architecture, nhưng chưa sửa file.

Mục tiêu:
- Tìm entrypoint backend, frontend, test, migration/seed, Docker/local dev nếu có.
- Xác định bounded context chính: tasks, users/auth, comments, notifications, shared infrastructure.
- Tạo dependency map cấp module: route/controller -> service -> repository/data/cache/external.
- Chỉ ra hot path cho các luồng: tạo task, cập nhật task status, list task board.
- Với mỗi kết luận quan trọng, ghi file đã đọc và bằng chứng ngắn.

Ràng buộc:
- Chỉ dùng read-only exploration.
- Không đọc file secret như .env, private key, production dump, log khách hàng.
- Không chạy install, build, migration, test dài, Docker, Git command destructive.
- Nếu thiếu thông tin, ghi rõ "chưa đủ bằng chứng" thay vì đoán.
- Trước khi tạo tài liệu, hãy đề xuất outline ARCHITECTURE.md để tôi duyệt.
```

Kết quả tốt: Claude liệt kê file đã đọc, phân nhóm module, nêu rõ entrypoint, và đánh dấu phần chưa chắc. Kết quả chưa đạt: Claude mô tả kiến trúc chung chung mà không có path file.

### Bước 3: Ép Claude phân biệt fact và inference

Gửi tiếp trong session plan:

```text
Hãy chuyển kết quả exploration thành bảng gồm 4 cột:
1. Claim
2. Evidence file/path
3. Confidence: high/medium/low
4. What to read next before editing

Không thêm claim nếu chưa có evidence. Với claim medium/low, nêu file hoặc command read-only cần kiểm chứng tiếp.
```

Bước này giảm hallucination. Với senior developer, đây là phần quan trọng hơn bản đồ đẹp: bạn cần biết Claude chắc ở đâu, đang đoán ở đâu, và phải đọc gì trước khi cho sửa code.

### Bước 4: Tạo `ARCHITECTURE.md`

Sau khi duyệt outline, mở session có quyền ghi rất hẹp:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)"
```

Chạy ở root `taskflow-ai`. Lệnh này giới hạn built-in tool family vào `Read`, `Write`, `Edit`, `Bash`, đồng thời auto-approve riêng các Bash command khớp `git status *` hoặc `git diff *`. Output kỳ vọng là session sẵn sàng. Rủi ro: `--allowedTools` không khóa toàn bộ Bash command khác, nó chỉ cho phép chạy không cần hỏi với pattern đã nêu; `Write`/`Edit` cũng không tự khóa theo path, nên prompt phải nêu rõ chỉ được tạo hoặc cập nhật `ARCHITECTURE.md` và vẫn phải review diff.

Prompt tạo tài liệu:

```text
Tạo file ARCHITECTURE.md ở root taskflow-ai dựa trên exploration đã duyệt.

Giới hạn:
- Chỉ tạo hoặc sửa ARCHITECTURE.md.
- Không sửa source code, config, package lock, test, migration, README, CLAUDE.md.
- Mỗi section phải ghi source file/path đã dùng làm bằng chứng.
- Tách rõ "Fact from code" và "Inference / needs verification".
- Có section "Before editing a feature, read these modules first".
- Có section "Hot paths and risk areas".
- Có section "Rollback and verification commands".
- Sau khi ghi file, chạy git diff -- ARCHITECTURE.md và tóm tắt.
```

Output kỳ vọng: `ARCHITECTURE.md` có cấu trúc hữu ích cho team, không chỉ là văn mô tả. Nếu Claude sửa file khác, dừng lại và rollback file ngoài phạm vi sau khi review.

### Bước 5: Kiểm tra artifact

Chạy trong root `taskflow-ai`:

```bash
git diff --stat -- ARCHITECTURE.md
```

Lệnh này cho biết file architecture có thay đổi bao nhiêu. Output kỳ vọng là chỉ `ARCHITECTURE.md`. Rủi ro thấp; đây là command read-only.

Xem nội dung diff:

```bash
git diff -- ARCHITECTURE.md
```

Kết quả kỳ vọng:

- Có entrypoint thật, không đoán tên file.
- Có dependency map module dựa trên file đã đọc.
- Có hot path tạo task/cập nhật status/list board.
- Có danh sách "read before editing" theo feature.
- Có phần "unknowns" hoặc "needs verification".

### Bước 6: Yêu cầu danh sách module cần đọc trước feature

Gửi prompt:

```text
Giả sử task tiếp theo là thêm feature task comments.

Hãy đề xuất module/file cần đọc trước khi sửa, theo thứ tự ưu tiên.
Với mỗi mục, ghi:
- Vì sao cần đọc.
- Bằng chứng từ architecture map hoặc source file.
- Rủi ro nếu bỏ qua.
- File nào tuyệt đối chưa được sửa trước khi hiểu rõ contract.

Chưa implement feature. Chỉ lập reading plan và risk map.
```

Kết quả tốt không phải là "sửa backend rồi frontend". Kết quả tốt phải nêu được đọc route/controller tasks, service/repository/data model, auth/current user, migration pattern, API client frontend, component task detail/list, test pattern, và Docker/test setup nếu feature cần database.

### Bước 7: Rollback khi tài liệu sai hoặc quá rộng

Nếu `ARCHITECTURE.md` là file đã tracked và bạn muốn bỏ toàn bộ thay đổi:

```bash
git restore -- ARCHITECTURE.md
```

Lệnh này đưa file về trạng thái trong Git. Rủi ro: mất toàn bộ thay đổi chưa commit trong file đó, kể cả chỉnh sửa thủ công của bạn.

Nếu `ARCHITECTURE.md` là file mới chưa tracked, trước tiên kiểm tra:

```bash
git status --short -- ARCHITECTURE.md
```

Nếu output là `?? ARCHITECTURE.md` và bạn chắc chắn muốn bỏ, có thể xóa file thủ công hoặc dùng:

```bash
git clean -f -- ARCHITECTURE.md
```

Lệnh này xóa file untracked được chỉ định. Rủi ro: `git clean` là destructive; chỉ dùng với path cụ thể sau khi `git status` xác nhận đúng file. Không chạy `git clean -fd` ở root repo nếu chưa hiểu toàn bộ file untracked.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```text
Hãy khám phá repo taskflow-ai theo hướng evidence-first.

Chưa sửa file.
Tìm entrypoint backend/frontend/test/devops.
Map bounded context chính và dependency giữa các module.
Mỗi claim phải kèm file/path đã đọc.
Nếu chưa có bằng chứng, ghi "unknown" thay vì suy đoán.
```

### Prompt lập plan

```text
Lập plan tạo ARCHITECTURE.md cho taskflow-ai.

Plan tối đa 6 bước:
- Bước nào đọc file nào.
- Bước nào tạo dependency map.
- Bước nào kiểm tra hallucination risk.
- Bước nào viết tài liệu.

Không sửa file trước khi tôi approve outline.
```

### Prompt implement

```text
Tạo ARCHITECTURE.md theo outline đã duyệt.

Giới hạn:
- Chỉ sửa ARCHITECTURE.md.
- Không sửa source code, README, CLAUDE.md, package files, migration, test.
- Tách Fact, Inference, Unknown.
- Thêm section "Read before editing feature".
- Sau khi ghi, tóm tắt diff và command verify.
```

### Prompt review

```text
Review ARCHITECTURE.md như senior engineer onboarding vào repo.

Tập trung:
- Claim nào thiếu evidence file/path.
- Dependency nào có vẻ suy đoán.
- Hot path nào thiếu test hoặc thiếu observability.
- Phần nào có thể làm developer mới sửa nhầm module.

Không sửa file trong bước review này. Trả về findings theo severity.
```

### Prompt viết test

```text
Từ architecture map hiện tại, đề xuất test cần đọc trước khi sửa feature task comments.

Yêu cầu:
- Chỉ đọc test pattern hiện có.
- Không viết test mới.
- Chỉ ra test unit/integration/e2e nào đang bảo vệ hot path tasks.
- Nếu chưa có test cho hot path, ghi rõ rủi ro và đề xuất test tối thiểu.
```

## 6. Trade-offs

Exploration rộng giúp bạn hiểu kiến trúc tổng thể, nhưng tốn token và dễ nhiễu context. Exploration hẹp tiết kiệm hơn, nhưng có thể bỏ sót dependency ngầm như auth middleware, cache key, hoặc migration convention. Cách cân bằng là bắt đầu bằng map cấp cao, sau đó zoom vào bounded context liên quan tới feature.

Tạo `ARCHITECTURE.md` giúp session sau nhanh hơn và hỗ trợ onboarding, nhưng tài liệu có thể stale. Nếu team không cập nhật khi architecture đổi, Claude và developer mới có thể bị dẫn sai. Vì vậy artifact phải ghi "last verified" hoặc ít nhất ghi source path, để người đọc biết cần kiểm chứng lại.

Yêu cầu Claude nêu "fact vs inference" làm output dài hơn, nhưng giảm rủi ro hallucination. Với codebase lớn, một kết luận sai về dependency có thể dẫn tới patch đúng cú pháp nhưng sai behavior.

Subagents/agents có thể tách exploration backend/frontend/security để giảm context collision, nhưng thêm orchestration cost và có thể tạo kết quả mâu thuẫn. Day 07 chỉ nên dùng khi repo lớn rõ rệt; nếu `taskflow-ai` còn nhỏ, một session plan mode là đủ.

Slash commands như `/compact` giúp giữ summary khi context dài, nhưng compact sai trọng tâm sẽ làm mất chi tiết quan trọng. Trước khi compact, hãy yêu cầu Claude giữ lại entrypoint, hot path, unknowns, accepted decisions, và file scope.

## 7. Best practices

- Luôn bắt đầu bằng `plan` mode hoặc quyền read-only khi khám phá repo lớn.
- Yêu cầu Claude liệt kê file đã đọc; không accept architecture claim không có evidence.
- Tách rõ `Fact from code`, `Inference`, và `Unknown / needs verification`.
- Không đọc `.env`, private key, production dump, customer log, hoặc file chứa credential.
- Không cho Claude chạy `npm install`, migration, Docker, test dài, hoặc command destructive trong phase exploration.
- Dependency map nên nói rõ loại dependency: import, runtime call, database, cache, config, CI, hoặc ownership.
- Với bounded context, ghi cả boundary và leak: module nào đang phụ thuộc chéo, shared helper nào dễ thành God module.
- Với hot path, ưu tiên đọc test và observability trước khi sửa logic.
- Đưa convention bền vững vào `CLAUDE.md`, nhưng để chi tiết architecture thay đổi thường xuyên trong `ARCHITECTURE.md`.
- Sau khi tạo architecture artifact, review như code: diff nhỏ, evidence rõ, không biến tài liệu thành nơi chứa suy đoán.

## 8. Performance / cost / context

Khám phá codebase lớn có thể đốt context nhanh hơn implement một bug nhỏ. Lockfile, generated file, build output, snapshot, log, và `node_modules` là nguồn nhiễu lớn. Prompt tốt phải hướng Claude dùng công cụ tìm kiếm file/symbol trước, rồi chỉ đọc file có liên quan.

Cách tối ưu:

- Bắt đầu bằng file định hướng: `package.json`, `README.md`, `CLAUDE.md`, `docker-compose.yml`, route/module index.
- Yêu cầu Claude đọc theo lớp: entrypoint -> route/module registration -> service -> data access -> test.
- Dùng `/context` để kiểm tra tình trạng context khi session dài.
- Dùng `/compact` sau khi đã có summary có cấu trúc, không compact khi Claude vẫn đang lẫn fact và inference.
- Chia exploration thành backend, frontend, devops/test nếu repo lớn. Có thể dùng agents/subagents về sau để tách context, nhưng không cần áp dụng sớm.
- Không yêu cầu "đọc toàn repo". Thay bằng "đọc đủ để trả lời câu hỏi X, nêu phần chưa đủ bằng chứng".
- Lưu artifact tốt vào `ARCHITECTURE.md` để session sau không phải khám phá lại từ đầu.

Chi phí thật không chỉ là token. Một architecture map sai có thể làm bạn sửa nhầm bounded context, tạo dependency vòng, hoặc bỏ qua authorization hot path. Vì vậy trả thêm vài phút cho evidence-first exploration thường rẻ hơn rollback một patch lớn.

## 9. Checklist cuối bài

- [ ] Tôi đã chạy `git status --short` trước khi cho Claude Code khám phá repo.
- [ ] Tôi dùng `plan` mode hoặc quyền read-only ở phase exploration.
- [ ] Tôi yêu cầu Claude tìm entrypoint backend, frontend, test, migration/seed, Docker/local dev.
- [ ] Tôi có dependency map phân biệt import, runtime, data, cache, config.
- [ ] Tôi xác định được bounded context chính trong `taskflow-ai`.
- [ ] Tôi xác định được hot path cho tạo task, cập nhật status, list board.
- [ ] Tôi yêu cầu Claude tách `Fact`, `Inference`, và `Unknown`.
- [ ] Tôi tạo hoặc review được `ARCHITECTURE.md` chỉ từ bằng chứng đã đọc.
- [ ] Tôi có reading plan trước khi sửa feature `task comments`.
- [ ] Tôi biết rollback `ARCHITECTURE.md` nếu tài liệu sai hoặc quá rộng.

## 10. Bài tập

Bài cơ bản: mở `taskflow-ai` bằng `claude --permission-mode plan`, yêu cầu Claude tìm entrypoint backend/frontend/test/devops và trả về bảng evidence.

Bài nâng cao: cho Claude tạo `ARCHITECTURE.md` với giới hạn chỉ sửa đúng file này, rồi review `git diff -- ARCHITECTURE.md` để tìm claim thiếu bằng chứng.

Bài áp dụng project cá nhân: chọn một repo thật có ít nhất backend hoặc frontend. Yêu cầu Claude tạo reading plan trước khi sửa một feature nhỏ. Không implement feature cho đến khi bạn có danh sách module cần đọc và rủi ro nếu bỏ qua.
