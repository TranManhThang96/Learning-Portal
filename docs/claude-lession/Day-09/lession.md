# Day 09 — Database migration và data model

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Dùng Claude Code để thiết kế data model cho `taskflow-ai` theo workflow có kiểm soát, không để AI tự suy diễn schema hoặc migration tool.
- Tạo migration cho bảng `users` và `tasks` với constraint, foreign key, index và timestamp hợp lý.
- Phân biệt thay đổi schema an toàn và thay đổi destructive: `DROP`, `TRUNCATE`, `DELETE` không điều kiện, đổi type có rewrite lớn, xóa column, rename phá backward compatibility.
- Review migration như reviewer production: lock, transaction, rollback strategy, forward-only plan, seed idempotent, dev/test DB và backup.
- Viết seed data có thể chạy lại nhiều lần mà không duplicate dữ liệu.
- Yêu cầu Claude Code lập plan, implement, review và test migration mà không được chạy destructive migration trên dữ liệu thật.

## 2. Bối cảnh thực tế

Day 08 tạo API CRUD ở tầng backend. Day 09 đi xuống tầng database, nơi lỗi nhỏ thường có hậu quả lớn hơn nhiều so với lỗi route handler. Một endpoint sai có thể rollback bằng patch. Một migration sai có thể lock bảng, mất dữ liệu, phá deploy, hoặc làm production outage.

Vấn đề thường gặp khi dùng AI cho database:

- Claude Code tạo migration theo "schema lý tưởng" nhưng không đọc domain và query pattern hiện có.
- AI thêm `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, `DELETE FROM` hoặc migration rollback phá dữ liệu vì nghĩ đang ở môi trường dev.
- Migration chạy trên database thật do `.env` trỏ nhầm.
- Seed chạy nhiều lần tạo duplicate user/task.
- Index được thêm theo cảm tính, không gắn với query thực tế.
- Constraint quá lỏng khiến data bẩn lọt vào database, hoặc quá chặt khiến migration fail khi có dữ liệu cũ.
- Tool migration wrap mọi thứ trong transaction, nhưng một số lệnh như `CREATE INDEX CONCURRENTLY` của PostgreSQL không chạy được trong transaction block.

Claude Code hữu ích khi bạn dùng nó để đọc codebase, đề xuất schema, sinh migration và test. Nhưng với database, developer phải giữ quyền quyết định cuối cùng. Rule quan trọng nhất của bài này:

```text
AI có thể soạn migration. Human quyết định DB target, review SQL, backup, chạy migration và giám sát kết quả.
```

Không nên dùng Claude Code để tự động chạy migration khi:

- Database target chưa xác nhận là dev/test.
- Migration có `DROP`, `TRUNCATE`, `DELETE`, `ALTER COLUMN TYPE`, `SET NOT NULL` trên bảng lớn, backfill lớn, hoặc index build trên bảng production.
- Chưa có backup hoặc rollback/forward-fix plan.
- Working tree có thay đổi của worker khác.
- Bạn chưa biết project dùng migration tool nào: Prisma, Drizzle, Knex, TypeORM, node-pg-migrate, SQL thuần, Flyway, Liquibase hoặc custom script.

## 3. Kiến thức nền

Data model tốt bắt đầu từ behavior của sản phẩm, không bắt đầu từ ORM. Với `taskflow-ai`, domain tối thiểu là team kỹ thuật quản lý task. Day 09 chỉ tạo nền tảng cho user và task, chưa đi vào auth đầy đủ, role phức tạp hoặc multi-tenant nâng cao.

Một model tối thiểu:

| Entity | Vai trò | Field cốt lõi | Ràng buộc quan trọng |
| --- | --- | --- | --- |
| `users` | Người sở hữu hoặc được giao task | `id`, `email`, `name`, `created_at`, `updated_at` | `id` primary key, `email` unique, email không rỗng |
| `tasks` | Công việc trong hệ thống | `id`, `user_id`, `title`, `description`, `status`, `priority`, `due_at`, `created_at`, `updated_at` | `user_id` foreign key, `title` không rỗng, `status` thuộc tập hợp hợp lệ |

### Schema design

Schema không chỉ là danh sách column. Một schema production-ready cần trả lời:

- Entity nào sở hữu entity nào? `tasks.user_id` phải tham chiếu `users.id`.
- Field nào là identity? Dùng `uuid` giúp seed/test ổn định và dễ merge dữ liệu, nhưng cần app hoặc database tạo ID. Dùng `bigserial` đơn giản hơn nhưng khó seed cố định giữa môi trường.
- Constraint nào thuộc database? Database nên giữ invariant không thể bị bypass: `title` không rỗng, `status` hợp lệ, `priority` trong range.
- Index nào phục vụ query thật? Ví dụ list task theo user và status nên có index `(user_id, status, created_at DESC)`.
- Delete behavior là gì? `ON DELETE RESTRICT` an toàn hơn `CASCADE` nếu chưa có product decision rõ về xóa user kéo theo xóa task.
- Timestamp dùng timezone hay không? Với PostgreSQL, ưu tiên `TIMESTAMPTZ` cho thời điểm tuyệt đối.

### Migration safety

Migration an toàn là migration có thể review, test, chạy lặp trong pipeline, quan sát được, và có chiến lược sửa khi sai.

Các cấp độ rủi ro:

| Thay đổi | Rủi ro | Ghi chú |
| --- | --- | --- |
| Tạo bảng mới chưa có dữ liệu | Thấp | Phù hợp cho Day 09 nếu chạy dev/test |
| Thêm nullable column | Thấp đến vừa | Ít phá app cũ hơn |
| Thêm index thường trên bảng lớn | Vừa đến cao | Có thể lock/write-block tùy DB và tool |
| Thêm `NOT NULL` khi có dữ liệu cũ | Vừa đến cao | Cần backfill và validate trước |
| Rename column/table | Cao | Có thể phá app phiên bản cũ đang chạy |
| Drop column/table, truncate, delete data | Rất cao | Không để AI chạy trên production |

Pattern phổ biến cho thay đổi production là `expand -> backfill -> contract`:

1. Expand: thêm column/table/index tương thích ngược.
2. Deploy app ghi cả field cũ và mới nếu cần.
3. Backfill dữ liệu theo batch, có giám sát.
4. Validate constraint.
5. Contract: xóa field cũ sau khi chắc chắn không còn consumer.

Day 09 chỉ thực hành migration tạo bảng mới. Nhưng bạn phải học guardrail ngay từ đầu, vì thói quen này quyết định an toàn ở Day 16 đến Day 20.

### Transaction

Transaction giúp migration hoặc seed thành công toàn bộ hoặc fail toàn bộ. Với PostgreSQL, nhiều DDL có thể chạy trong transaction, nhưng không phải tất cả. `CREATE INDEX CONCURRENTLY` và `DROP INDEX CONCURRENTLY` không được chạy trong transaction block. Vì vậy:

- Migration tạo bảng mới thường nên chạy trong transaction nếu tool hỗ trợ.
- Migration tạo index concurrently cần tách riêng và cấu hình tool để không wrap transaction.
- Seed data nên chạy trong transaction nếu seed nhiều bảng liên quan.
- Không assume mọi migration tool xử lý transaction giống nhau. Bắt Claude Code đọc docs/config/script thật của project.

### Index

Index không phải "thêm càng nhiều càng tốt". Index tăng tốc read nhưng làm write chậm hơn, tốn disk, tăng thời gian migration và tăng chi phí maintenance.

Với `taskflow-ai`, index hợp lý cho Day 09:

- `users.email` unique index để đảm bảo không có hai user cùng email.
- `tasks(user_id, status, created_at DESC)` cho màn list task theo user và trạng thái.
- Partial index `tasks(due_at) WHERE due_at IS NOT NULL` nếu UI có filter task sắp đến hạn.

Không thêm index cho mọi column như `title`, `description`, `priority` nếu chưa có query pattern. Full-text search hoặc fuzzy search là feature riêng, không gộp vào migration nền tảng.

### Constraint

Constraint là tuyến phòng thủ cuối cùng cho data integrity. App validation giúp trả lỗi đẹp, nhưng database constraint giữ dữ liệu sạch kể cả khi có bug, script thủ công hoặc service khác ghi vào DB.

Constraint nên có trong Day 09:

- Primary key cho `users.id` và `tasks.id`.
- Foreign key `tasks.user_id -> users.id`.
- Unique constraint hoặc unique index cho `users.email`.
- Check constraint cho `tasks.status`.
- Check constraint cho `tasks.priority`.
- Check constraint cho `tasks.title` sau trim không rỗng.

Trade-off: constraint làm migration fail sớm nếu seed hoặc app ghi data sai. Đó là lợi ích, không phải nhược điểm, miễn là error được hiểu và test bắt được.

### Seed data idempotent

Seed data dùng để dev/test có dữ liệu mẫu. Seed tốt phải:

- Chạy được nhiều lần không duplicate.
- Dùng ID cố định để test ổn định.
- Không chứa secret thật, email khách hàng thật, access token, production dump.
- Tách seed dev/test khỏi seed production.
- Có transaction và `ON CONFLICT` hoặc upsert theo migration tool.

Ví dụ SQL seed idempotent cho PostgreSQL:

```sql
INSERT INTO users (id, email, name)
VALUES
  ('00000000-0000-4000-8000-000000000001', 'alice@example.test', 'Alice Nguyen')
ON CONFLICT (id) DO UPDATE
SET email = EXCLUDED.email,
    name = EXCLUDED.name,
    updated_at = now();
```

File path ví dụ: `backend/db/seeds/001_dev_seed.sql` hoặc path seed theo tool thật của project. Mục đích là tạo dữ liệu dev/test ổn định. Cách test là chạy seed hai lần rồi kiểm tra số row không tăng. Edge case cần kiểm tra: conflict theo `id`, conflict theo `email`, task tham chiếu user chưa tồn tại, seed chạy trong transaction và rollback khi một row fail.

## 4. Step-by-step thực hành

Mục tiêu thực hành: dùng Claude Code để tạo migration bảng `users`, `tasks` và seed data trong project `taskflow-ai`. Học viên phải chạy trên dev/test DB, không chạy trên production DB. Tên command migration phụ thuộc project thật, nên bài này luôn yêu cầu Claude đọc `package.json` và thư mục migration trước khi đề xuất command.

### Bước 1: Kiểm tra working tree và phạm vi

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này kiểm tra file đang thay đổi. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có thay đổi của worker khác, migration của bạn có thể chồng lên patch chưa review. Không rollback toàn repo; chỉ làm việc với file thuộc task của bạn.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
find . -maxdepth 4 -name package.json
```

Lệnh này tìm package Node để biết backend nằm ở root, `backend`, `apps/api` hay workspace khác. Output kỳ vọng có ít nhất một `package.json`. Rủi ro thấp vì read-only; trên Windows PowerShell có thể dùng lệnh tương đương `Get-ChildItem -Recurse -Filter package.json -Depth 4`.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
rg "\"(migrate|migration|seed|db):" -n package.json backend/package.json apps
```

Lệnh này tìm script liên quan tới migration và seed. Output kỳ vọng là các script như `db:migrate`, `db:migrate:status`, `db:seed` hoặc tên tương tự. Rủi ro thấp vì read-only; nếu path không tồn tại, `rg` có thể báo lỗi, khi đó đọc `package.json` thật trước.

### Bước 2: Xác nhận database target là dev/test

Không paste full `DATABASE_URL` vào prompt vì có thể chứa credential. Hãy kiểm tra database bằng query metadata.

Chạy trong thư mục backend hoặc root nơi env dev/test được load:

```bash
psql "$DATABASE_URL" -c "select current_database(), current_user, inet_server_addr(), inet_server_port();"
```

Lệnh này kết nối bằng `DATABASE_URL` hiện tại và in database name, user, host, port. Output kỳ vọng cho thấy database dev/test, ví dụ `taskflow_ai_dev` hoặc `taskflow_ai_test`, không phải database production. Rủi ro: nếu `DATABASE_URL` trỏ nhầm production, chỉ riêng lệnh select này vẫn read-only, nhưng bạn phải dừng ngay và sửa env trước khi migrate.

Nếu project dùng Docker Compose local, chạy trong root `taskflow-ai`:

```bash
docker compose ps
```

Lệnh này hiển thị container database local đang chạy. Output kỳ vọng có service PostgreSQL local, ví dụ `postgres` hoặc `db`, trạng thái `running`. Rủi ro: Docker command read-only này an toàn, nhưng không chạy các command xóa volume như `docker compose down -v` nếu chưa chắc chắn vì có thể mất dữ liệu dev của người khác.

### Bước 3: Mở Claude Code ở plan mode để khảo sát database layer

Chạy trong root `taskflow-ai`:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude Code ở mode đọc/lập plan. Output kỳ vọng là session sẵn sàng nhận prompt. Rủi ro thấp hơn edit mode, nhưng Claude vẫn có thể suy diễn nếu bạn không bắt nó nêu file đã đọc.

Prompt khám phá:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát database layer để chuẩn bị migration Day 09.

Ràng buộc:
- Chưa sửa file.
- Chỉ đọc file cần thiết.
- Tìm migration tool, seed mechanism, database client/ORM, test DB setup và script trong package.json.
- Nêu rõ file đã đọc và bằng chứng từ code.
- Không đề xuất chạy migration.
- Không đề xuất DROP, TRUNCATE, DELETE không điều kiện, reset database hoặc xóa Docker volume.
- Nếu không tìm thấy migration tool, đề xuất 2 phương án tối thiểu nhưng chưa implement.
```

Kỳ vọng: Claude cho biết project dùng tool nào, migration folder ở đâu, command nào tồn tại, seed chạy bằng gì, test DB setup ra sao. Nếu Claude không đọc `package.json`, `docker-compose.yml`, `.env.example`, migration folder hoặc database client, yêu cầu đọc bổ sung.

### Bước 4: Chốt data model trước khi tạo migration

Gửi prompt trong cùng session:

```text
Dựa trên file đã đọc, hãy đề xuất data model Day 09 cho bảng users và tasks.

Output bắt buộc:
- Bảng column cho users và tasks: name, type, nullable, default, constraint.
- Foreign key và delete behavior.
- Index đề xuất, mỗi index phải gắn với query pattern cụ thể.
- Constraint đề xuất và lỗi dữ liệu mà constraint chặn.
- Migration safety review: lock risk, destructive risk, transaction, rollback/forward-only.
- Seed data plan idempotent.
- Chưa sửa file và chưa chạy command.
```

Một schema SQL tham khảo cho PostgreSQL:

```sql
CREATE TABLE users (
  id uuid PRIMARY KEY,
  email text NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT users_email_non_empty CHECK (length(btrim(email)) > 0),
  CONSTRAINT users_name_non_empty CHECK (length(btrim(name)) > 0)
);

CREATE UNIQUE INDEX users_email_unique_idx ON users (email);

CREATE TABLE tasks (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'todo',
  priority smallint NOT NULL DEFAULT 3,
  due_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tasks_title_non_empty CHECK (length(btrim(title)) > 0),
  CONSTRAINT tasks_title_length CHECK (char_length(title) <= 200),
  CONSTRAINT tasks_status_valid CHECK (status IN ('todo', 'in_progress', 'done', 'archived')),
  CONSTRAINT tasks_priority_range CHECK (priority BETWEEN 1 AND 5)
);

CREATE INDEX tasks_user_status_created_idx ON tasks (user_id, status, created_at DESC);
CREATE INDEX tasks_due_at_idx ON tasks (due_at) WHERE due_at IS NOT NULL;
```

File path sẽ phụ thuộc tool thật, ví dụ `backend/db/migrations/20260514090000_create_users_tasks.sql`. Mục đích của đoạn SQL là tạo schema nền tảng cho dev/test. Cách test là chạy migration trên database dev/test sạch, kiểm tra table, constraint, index, sau đó chạy API/test. Edge case cần xem: email trùng, title chỉ có khoảng trắng, status không hợp lệ, priority ngoài range, task tham chiếu user không tồn tại.

### Bước 5: Lập plan file-by-file

Prompt lập plan:

```text
Lập plan implement migration Day 09.

Ràng buộc:
- Tối đa 7 bước.
- Mỗi bước ghi file sẽ sửa/tạo.
- Chỉ tạo migration cho users/tasks và seed dev/test idempotent.
- Không đổi API route, service hoặc frontend trong Day 09 nếu không cần cho test.
- Không thêm dependency nếu project đã có migration tool.
- Không chạy migration, seed, reset DB hoặc Docker command.
- Nếu cần command để verify, chỉ liệt kê command, ghi rõ môi trường dev/test và rủi ro.
- Chờ tôi approve trước khi edit.
```

Plan tốt thường có:

```text
1. Tạo migration create_users_tasks theo convention hiện có.
2. Thêm seed dev/test idempotent cho user và task mẫu.
3. Nếu project có migration index/manifest, cập nhật đúng file manifest.
4. Thêm hoặc cập nhật test migration/seed nếu project đã có pattern.
5. Không chạy migration; chỉ ghi command verify để human chạy.
```

Nếu Claude đề xuất sửa API CRUD Day 08, đổi ORM, đổi `.env`, thêm dependency, hoặc tạo auth system, yêu cầu thu hẹp scope.

### Bước 6: Cho Claude Code implement với boundary hẹp

Sau khi duyệt plan, mở session edit trong root `taskflow-ai`:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)"
```

Lệnh này giới hạn built-in tool family vào đọc/sửa file và Bash, đồng thời auto-approve riêng Git read-only. Output kỳ vọng là session sẵn sàng. Rủi ro: command migration không được auto-approve nhưng Claude vẫn có thể đề xuất và xin quyền chạy; hãy từ chối cho đến khi review diff, xác nhận DB dev/test và kiểm tra rollback path. Nếu bạn thêm `Bash(*)`, Claude có thể chạy command ngoài ý muốn, gồm migration hoặc reset DB.

Prompt implement:

```text
Implement migration Day 09 theo plan đã approve.

Ràng buộc bắt buộc:
- Chỉ chạm file trong plan.
- Không chạy migration, seed, docker, npm install, git add, git commit, git reset, git clean hoặc command xóa dữ liệu.
- Migration chỉ tạo users/tasks, constraint, foreign key và index đã duyệt.
- Không dùng DROP, TRUNCATE, DELETE không điều kiện, reset DB hoặc destructive rollback.
- Seed phải idempotent, chạy lại không duplicate dữ liệu.
- Nếu migration tool yêu cầu transaction config, ghi chú rõ. Không tự đoán nếu chưa thấy pattern.
- Sau khi edit, tóm tắt file changed, SQL chính, command human nên chạy và rủi ro còn lại.
```

Kỳ vọng: Claude tạo migration và seed đúng pattern. Nếu Claude muốn chạy command migration, từ chối và yêu cầu chỉ liệt kê command.

### Bước 7: Review diff migration trước khi chạy

Chạy trong root `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này cho biết phạm vi patch. Output kỳ vọng chỉ có file migration, seed và test/manifest liên quan nếu plan có. Rủi ro: `--stat` không cho thấy SQL nguy hiểm, chỉ dùng để phát hiện patch rộng bất thường.

Chạy trong root `taskflow-ai`:

```bash
git diff
```

Lệnh này hiển thị patch chi tiết. Output kỳ vọng không có thay đổi ngoài plan, không có command destructive, seed idempotent, constraint/index đúng contract. Rủi ro: diff SQL dài dễ bỏ sót; reviewer nên tìm thủ công các từ khóa rủi ro.

Chạy trong root `taskflow-ai`:

```bash
git diff -- backend/db/migrations
```

Lệnh này giới hạn review vào migration folder ví dụ. Output kỳ vọng chỉ có migration Day 09. Rủi ro thấp vì read-only; thay path bằng migration folder thật của project.

Prompt review migration:

```text
Review diff migration hiện tại như senior database reviewer, không sửa file.

Tập trung:
- Có DROP, TRUNCATE, DELETE không điều kiện, reset DB, CASCADE nguy hiểm hoặc destructive rollback không.
- Constraint có đúng domain không và có fail với seed không.
- Foreign key delete behavior có an toàn không.
- Index có gắn với query pattern thật không.
- Migration có transaction phù hợp không.
- Có command nào có thể chạy nhầm production không.
- Seed có idempotent không.
- Có file ngoài plan bị chạm không.

Kết luận theo format: Blocker, Should fix, Nice to have, Test gaps.
```

### Bước 8: Chạy migration trên dev/test DB

Chỉ chạy sau khi đã xác nhận database target là dev/test. Đọc `package.json` để dùng script thật. Các command dưới đây là ví dụ script phổ biến, không phải bắt buộc tồn tại.

Chạy trong folder có `package.json` backend:

```bash
npm run db:migrate:status
```

Lệnh này kiểm tra migration đã applied/chưa applied nếu project có script status. Output kỳ vọng thấy migration Day 09 ở trạng thái pending. Rủi ro: script có thể không tồn tại hoặc có thể kết nối nhầm DB nếu env sai; kiểm tra DB target trước.

Chạy trong folder có `package.json` backend:

```bash
npm run db:migrate:dev
```

Lệnh này chạy migration trên database dev nếu project định nghĩa script này. Output kỳ vọng báo applied thành công migration Day 09. Rủi ro cao nếu env trỏ production; không để Claude tự chạy, human phải xác nhận dev/test và backup trước.

Nếu project chỉ có một script migrate chung, chạy trong folder backend sau khi xác nhận env:

```bash
npm run db:migrate
```

Lệnh này chạy migration theo script thật của project. Output kỳ vọng là migration applied, exit code `0`. Rủi ro: tên script chung không nói rõ môi trường, nên phải xác nhận `DATABASE_URL`, `.env`, Docker service và branch trước.

### Bước 9: Verify schema, index và constraint

Chạy trong folder backend hoặc root nơi `DATABASE_URL` dev/test được load:

```bash
psql "$DATABASE_URL" -c "\d users"
```

Lệnh này mô tả bảng `users`. Output kỳ vọng có column `id`, `email`, `name`, timestamp, primary key và unique index email. Rủi ro thấp nếu DB target dev/test; nếu không có quyền hoặc env sai, dừng và không tự sửa bằng quyền production.

Chạy trong cùng nơi:

```bash
psql "$DATABASE_URL" -c "\d tasks"
```

Lệnh này mô tả bảng `tasks`. Output kỳ vọng có foreign key tới `users`, check constraint cho `status`, `priority`, `title`, và index liên quan. Rủi ro thấp nếu read-only trên dev/test.

Chạy trong cùng nơi:

```bash
psql "$DATABASE_URL" -c "select tablename, indexname from pg_indexes where tablename in ('users', 'tasks') order by tablename, indexname;"
```

Lệnh này liệt kê index của `users` và `tasks`. Output kỳ vọng có unique index email, index list task theo user/status và partial index due date nếu đã duyệt. Rủi ro thấp vì read-only.

Chạy trong cùng nơi:

```bash
psql "$DATABASE_URL" -c "insert into tasks (id, user_id, title, status, priority) values ('00000000-0000-4000-8000-000000009999', '00000000-0000-4000-8000-000000009998', 'Invalid FK', 'todo', 3);"
```

Lệnh này cố tình insert task với `user_id` không tồn tại để kiểm tra foreign key trên dev/test. Output kỳ vọng là lỗi foreign key violation. Rủi ro: đây là lệnh ghi dữ liệu và cố tình fail; chỉ chạy trên dev/test, không chạy production.

### Bước 10: Chạy seed idempotent

Chạy trong folder backend nếu project có script seed:

```bash
npm run db:seed
```

Lệnh này chạy seed theo script project. Output kỳ vọng báo seed thành công, tạo user/task mẫu. Rủi ro: nếu seed không idempotent sẽ tạo duplicate; nếu env sai có thể ghi vào database không mong muốn. Chỉ chạy dev/test.

Chạy lại cùng lệnh trong folder backend:

```bash
npm run db:seed
```

Lệnh này kiểm tra seed có idempotent không. Output kỳ vọng vẫn thành công và không tăng số row ngoài dự kiến. Rủi ro giống lần chạy đầu; nếu row tăng, seed chưa đạt yêu cầu.

Chạy trong folder backend hoặc root:

```bash
psql "$DATABASE_URL" -c "select count(*) as users_count from users; select count(*) as tasks_count from tasks;"
```

Lệnh này kiểm tra số row seed. Output kỳ vọng số lượng ổn định sau hai lần seed. Rủi ro thấp nếu read-only trên dev/test.

### Bước 11: Chạy test liên quan

Chạy trong folder backend có `package.json`:

```bash
npm run test -- --run tasks
```

Lệnh này chạy test liên quan tới tasks nếu test runner hỗ trợ filter. Output kỳ vọng test pass và exit code `0`. Rủi ro: cú pháp filter phụ thuộc Vitest/Jest script; nếu không hỗ trợ, dùng script test chuẩn của project.

Chạy trong folder backend:

```bash
npm run test -- --run
```

Lệnh này chạy test một lần nếu project dùng Vitest hoặc script tương đương. Output kỳ vọng toàn bộ backend test pass. Rủi ro: integration test có thể ghi DB; chỉ dùng DB test/dev đã xác nhận.

Nếu test fail, dùng prompt:

```text
Test migration/seed fail như sau. Hãy phân tích nguyên nhân trước, chưa sửa file.

Phân loại:
- Schema bug.
- Seed không idempotent.
- Test setup sai DB.
- Constraint quá chặt hoặc quá lỏng.
- Migration tool/transaction config sai.

Đề xuất patch nhỏ nhất và file cần sửa. Không chạy command.
```

### Bước 12: Rollback hoặc forward-fix khi migration sai

Nếu migration chưa được applied, rollback file bằng Git là an toàn hơn rollback DB.

Chạy trong root `taskflow-ai`:

```bash
git restore -- backend/db/migrations/path-to-day-09-migration.sql backend/db/seeds/path-to-seed.sql
```

Lệnh này rollback các tracked file ví dụ về trạng thái Git. Output thường rỗng nếu thành công. Rủi ro: mất thay đổi chưa commit trong các file đó; chỉ dùng với file bạn vừa tạo/sửa và đã review.

Nếu migration đã applied trên dev/test disposable DB, bạn có thể dùng rollback command của tool nếu project có và bạn hiểu nó.

Chạy trong folder backend, chỉ trên dev/test:

```bash
npm run db:migrate:rollback
```

Lệnh này rollback migration gần nhất nếu project có script. Output kỳ vọng báo reverted migration. Rủi ro cao: rollback có thể drop table hoặc mất data dev/test; tuyệt đối không để Claude tự chạy và không dùng trên production.

Với production, ưu tiên forward-only fix:

```text
Không rollback destructive trên production.
Tạo migration mới để sửa trạng thái về phía trước, sau khi có backup, review và maintenance plan.
```

Đây không phải shell command mà là rule vận hành. Với production data, "quay lại" thường là migration mới, restore backup có kiểm soát hoặc hotfix app, không phải để AI tự undo.

## 5. Prompt mẫu nên dùng

### Prompt khám phá database layer

```text
Hãy khảo sát database layer của taskflow-ai để chuẩn bị migration Day 09.

Yêu cầu:
- Chỉ đọc file, chưa sửa.
- Tìm migration tool, seed mechanism, database client/ORM, migration folder, test DB setup và script package.json.
- Nêu file đã đọc và bằng chứng.
- Không chạy migration, seed, reset DB hoặc Docker command.
- Không đề xuất destructive SQL.
```

### Prompt lập data model

```text
Thiết kế data model users/tasks cho taskflow-ai theo convention hiện có.

Output:
- Column table cho users và tasks.
- Constraint, foreign key, index và query pattern tương ứng.
- Quyết định delete behavior.
- Seed data idempotent.
- Migration safety: transaction, lock, rollback/forward-only, dev/test DB.

Chưa implement.
```

### Prompt lập plan migration

```text
Lập plan implement migration và seed Day 09.

Ràng buộc:
- Tối đa 7 bước.
- Mỗi bước ghi file sẽ tạo/sửa.
- Không đổi API/frontend.
- Không thêm dependency nếu project đã có migration tool.
- Không chạy migration, seed, reset DB, Docker volume command hoặc Git destructive command.
- Chờ tôi approve trước khi edit.
```

### Prompt implement migration

```text
Implement migration users/tasks và seed dev/test theo plan đã approve.

Giới hạn:
- Chỉ chạm file trong plan.
- Không chạy command.
- Không dùng DROP, TRUNCATE, DELETE không điều kiện, CASCADE nguy hiểm hoặc destructive rollback.
- Seed phải idempotent và dùng ID cố định.
- Constraint phải chặn title rỗng/whitespace, status không hợp lệ, priority ngoài range.
- Index phải đúng query pattern đã duyệt.
- Sau khi edit, tóm tắt SQL chính, file changed, command human cần chạy và rủi ro.
```

### Prompt review migration

```text
Review diff migration hiện tại như senior database reviewer, không sửa file.

Kiểm tra:
- Destructive SQL hoặc rollback nguy hiểm.
- DB target và command có nguy cơ production không.
- Transaction có phù hợp không, đặc biệt nếu có index concurrently.
- Constraint có đúng domain và có test được không.
- Index có cần thiết không, có ảnh hưởng write không.
- Seed có idempotent không.
- Có file ngoài plan không.

Kết luận: Blocker, Should fix, Nice to have, Test gaps.
```

### Prompt viết test và verify

```text
Hãy đề xuất test/verification cho migration Day 09, chưa sửa file.

Yêu cầu:
- Test schema: table, constraint, foreign key, index.
- Test seed chạy hai lần không duplicate.
- Test API task CRUD sau migration nếu project có integration test.
- Ghi command cần chạy, chạy ở folder nào, output kỳ vọng và rủi ro.
- Không đề xuất reset DB hoặc dùng production data.
```

## 6. Trade-offs

Dùng database constraint làm hệ thống cứng hơn nhưng lỗi sẽ xuất hiện ở tầng DB nếu app validation thiếu. Đây là trade-off tốt cho data integrity, nhưng API vẫn cần map lỗi DB thành response rõ ràng.

UUID giúp seed/test dễ ổn định và tránh phụ thuộc sequence. Đổi lại, index lớn hơn `bigint`, insert locality kém hơn nếu UUID random, và cần thống nhất cách generate ID. Với Day 09, dùng UUID cố định trong seed là hợp lý, nhưng production có thể dùng app-generated UUID, database extension hoặc sequence tùy team.

Unique index trên `email` đảm bảo invariant quan trọng. Nhưng nếu email cần case-insensitive, bạn phải quyết định dùng normalized email lower-case, `citext`, hoặc unique index trên expression. Day 09 nên chọn phương án đơn giản: normalize email ở app/seed và giữ unique index trên `email`.

`ON DELETE RESTRICT` bảo vệ task khỏi bị xóa dây chuyền khi user bị xóa nhầm. Nhược điểm là xóa user khó hơn, cần flow archive/anonymize riêng. `ON DELETE CASCADE` tiện hơn cho test và demo, nhưng nguy hiểm nếu domain chưa quyết định.

Index giúp list task nhanh hơn nhưng làm insert/update chậm hơn và migration nặng hơn. Chỉ thêm index cho query đã có hoặc chắc chắn sắp có. Không thêm index chỉ vì column "có vẻ hay filter".

Migration trong transaction dễ rollback khi fail. Nhưng một số operation cần chạy ngoài transaction, ví dụ `CREATE INDEX CONCURRENTLY` trong PostgreSQL. Tool migration có thể wrap transaction mặc định, nên reviewer phải biết behavior của tool trước khi dùng operation đặc biệt.

Rollback migration nghe có vẻ an toàn nhưng với production thường không đơn giản. Nếu migration đã làm app phiên bản mới ghi dữ liệu theo schema mới, rollback schema có thể mất dữ liệu. Forward-only migration thường an toàn hơn: tạo migration sửa lỗi, giữ dữ liệu, deploy tiếp.

Seed idempotent tốn công hơn seed insert thẳng. Đổi lại, developer có thể chạy lại seed sau mỗi reset hoặc test mà không tạo duplicate. Với team thật, đây là tiêu chuẩn tối thiểu.

## 7. Best practices

- Luôn bắt đầu bằng read-only exploration. Bắt Claude Code đọc migration tool, folder convention, seed script và test setup trước khi thiết kế.
- Không cho Claude Code chạy migration trên database thật. AI có thể viết SQL và command, human chạy sau khi xác nhận môi trường.
- Không paste production credential, `.env` thật hoặc database dump vào prompt.
- Trước khi chạy migration, xác nhận DB target bằng query metadata, không chỉ nhìn tên terminal.
- Với production migration, cần backup, review SQL, estimated lock time, deploy order, rollback hoặc forward-fix plan.
- Dùng forward-only mindset. Rollback file Git khác rollback dữ liệu đã applied.
- Với bảng có dữ liệu lớn, tránh migration rewrite toàn bảng trong giờ cao điểm.
- Thêm `NOT NULL` hoặc constraint mới trên dữ liệu cũ theo nhiều bước: add nullable, backfill, validate, enforce.
- Index production trên bảng lớn cần chiến lược riêng. Với PostgreSQL, cân nhắc `CONCURRENTLY`, nhưng nhớ command này không chạy trong transaction block.
- Constraint nên có tên rõ, ví dụ `tasks_status_valid`, để log lỗi dễ debug.
- Seed dev/test phải idempotent, dùng ID cố định, không dùng data khách hàng thật.
- Không dùng `CASCADE` trong migration nếu chưa có lý do rõ và reviewer approve.
- Không tự đổi migration history đã merge hoặc đã applied ở môi trường chung. Tạo migration mới.
- Review diff tìm từ khóa rủi ro: `DROP`, `TRUNCATE`, `DELETE`, `CASCADE`, `ALTER COLUMN`, `SET NOT NULL`, `TYPE`, `RENAME`, `down`, `rollback`.
- Trong repo nhiều worker, chỉ rollback theo file bạn sở hữu. Không dùng `git reset --hard`, `git clean -fd` hoặc command xóa rộng.

## 8. Performance / cost / context

Database task thường làm Claude Code đọc nhiều file: migration folder, ORM schema, database client, route/service, test setup, Docker Compose và env example. Nếu không kiểm soát, context sẽ phình nhanh và Claude dễ lẫn giữa app schema, test schema và production assumptions.

Cách giảm token và chi phí:

- Bắt đầu bằng câu hỏi hẹp: "tìm migration tool và seed mechanism", không yêu cầu đọc toàn repo.
- Yêu cầu Claude nêu file đã đọc và bằng chứng, không viết essay dài.
- Chốt data model trong bảng ngắn trước khi implement.
- Chia migration thành một slice: tạo bảng mới `users/tasks`; không gộp auth, roles, comments, audit log.
- Khi test fail, chỉ đưa failure output liên quan và schema diff, không paste toàn bộ log Docker.
- Dùng summary khi session dài: tool migration, file list, schema đã duyệt, command verify, constraint/index.

Performance runtime của database:

- Index tăng tốc read nhưng làm write chậm hơn. Với task CRUD nhỏ, 2-3 index có chủ đích là đủ.
- Unique email check cần index; nếu không có index, kiểm tra uniqueness không khả thi ở scale.
- Foreign key cũng có chi phí write nhưng bảo vệ data integrity. Với `tasks.user_id`, index query theo `user_id` thường cũng giúp join/list.
- `CREATE INDEX` trên bảng lớn có thể lock write; `CREATE INDEX CONCURRENTLY` giảm lock nhưng chạy lâu hơn, không chạy trong transaction block và cần giám sát.
- Backfill lớn nên chạy theo batch, không viết migration một transaction khổng lồ nếu bảng production lớn.

Cost của lỗi database lớn hơn cost token. Đừng tiết kiệm một lượt review để rồi chạy migration sai. Với DB, review SQL thủ công là bước bắt buộc.

## 9. Checklist cuối bài

- [ ] Tôi đã kiểm tra `git status --short` trước khi cho Claude Code sửa file.
- [ ] Tôi đã xác nhận migration chỉ chạy trên dev/test DB.
- [ ] Tôi không paste credential hoặc full production `DATABASE_URL` vào prompt.
- [ ] Claude Code đã đọc migration tool, seed mechanism và script thật trước khi đề xuất command.
- [ ] Data model `users/tasks` có column, type, nullable, default và constraint rõ.
- [ ] Foreign key `tasks.user_id -> users.id` có delete behavior được duyệt.
- [ ] Index được gắn với query pattern cụ thể, không thêm theo cảm tính.
- [ ] Seed data idempotent, chạy lại không duplicate.
- [ ] Migration không có `DROP`, `TRUNCATE`, `DELETE` không điều kiện, reset DB hoặc `CASCADE` nguy hiểm.
- [ ] Tôi đã review `git diff --stat` và `git diff` trước khi chạy migration.
- [ ] Tôi biết command migration chạy ở đâu, làm gì, output kỳ vọng và rủi ro.
- [ ] Tôi đã verify table, constraint, index và seed sau khi chạy dev/test migration.
- [ ] Tôi không để Claude Code tự chạy destructive migration trên data thật.
- [ ] Với production, tôi ưu tiên backup, forward-only fix và maintenance plan.

## 10. Bài tập

Bài cơ bản: mở `taskflow-ai` ở `claude --permission-mode plan`, yêu cầu Claude khảo sát database layer và viết data model `users/tasks`. Không cho sửa file. Kết quả cần có: file đã đọc, migration tool, seed mechanism, schema proposal, constraint, index, risk review.

Bài thực tế: sau khi duyệt data model, cho Claude Code tạo migration và seed idempotent trong dev/test. Không cho Claude chạy migration. Human review diff, xác nhận DB target, rồi tự chạy migration bằng script thật của project. Ghi lại command, output chính và rủi ro.

Bài nâng cao: thêm verification test cho seed idempotent và constraint quan trọng. Test phải chứng minh chạy seed hai lần không duplicate, task không thể tham chiếu user không tồn tại, title whitespace bị reject và status ngoài enum bị reject.

Bài áp dụng project cá nhân: chọn một migration từng làm ở project thật hoặc repo sandbox. Viết lại theo format: schema contract, migration safety, forward-only plan, seed idempotency, verification command. Yêu cầu Claude review migration cũ và chỉ ra ít nhất 5 rủi ro production.
