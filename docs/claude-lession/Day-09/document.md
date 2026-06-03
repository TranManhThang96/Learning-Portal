# Document — Day 09

## Tóm tắt kiến thức

Day 09 tập trung vào database migration và data model cho `taskflow-ai`. Trọng tâm không phải chỉ là tạo bảng `users` và `tasks`, mà là cách dùng Claude Code để làm việc với database có guardrail rõ ràng.

Nguyên tắc chính:

- Claude Code được phép đọc codebase, đề xuất schema, soạn migration và seed.
- Human phải xác nhận database target, review SQL, quyết định backup và chạy migration.
- Không cho AI chạy destructive migration trên production data.
- Migration tạo bảng mới là rủi ro thấp, nhưng vẫn cần review constraint, index, foreign key và seed.
- Seed dev/test phải idempotent: chạy nhiều lần không duplicate.
- Index phải xuất phát từ query pattern, không thêm theo cảm tính.
- Constraint giữ data integrity ở tầng database, bổ sung cho app validation.
- Production migration nên theo tư duy forward-only: sửa bằng migration mới thay vì rollback phá dữ liệu.

Data model Day 09 tham khảo:

| Bảng | Mục đích | Field chính | Constraint chính |
| --- | --- | --- | --- |
| `users` | Người sở hữu/giao task | `id`, `email`, `name`, `created_at`, `updated_at` | primary key, unique email, email/name không rỗng |
| `tasks` | Công việc trong hệ thống | `id`, `user_id`, `title`, `description`, `status`, `priority`, `due_at`, timestamps | foreign key, title không rỗng, status hợp lệ, priority trong range |

Migration an toàn cần trả lời được 6 câu hỏi:

1. Chạy trên DB nào: dev, test, staging hay production?
2. Có backup chưa nếu không phải DB disposable?
3. Có destructive SQL không?
4. Có lock hoặc table rewrite đáng kể không?
5. Rollback là rollback file, rollback DB dev/test, hay forward-only fix?
6. Verify bằng command và test nào?

## Sơ đồ tư duy hoặc luồng xử lý

```text
Yêu cầu Day 09
  |
  v
Kiểm tra Git state
  |
  +-- Có thay đổi lạ -> dừng, đọc diff, không rollback toàn repo
  |
  v
Xác định DB target
  |
  +-- Không chắc dev/test -> dừng, không migrate
  |
  v
Claude Code plan mode
  |
  v
Đọc database layer
  |
  +-- package.json scripts
  +-- migration folder
  +-- ORM/database client
  +-- seed mechanism
  +-- docker/test DB setup
  |
  v
Thiết kế schema contract
  |
  +-- users columns
  +-- tasks columns
  +-- constraints
  +-- foreign keys
  +-- indexes
  +-- seed idempotent
  |
  v
Migration safety review
  |
  +-- destructive SQL?
  +-- transaction?
  +-- lock risk?
  +-- rollback/forward-only?
  +-- backup?
  |
  v
Developer approve
  |
  v
Claude implement file migration/seed
  |
  v
git diff --stat -> git diff
  |
  v
Human chạy migration trên dev/test
  |
  v
Verify schema + seed + tests
  |
  +-- Đạt -> commit/PR
  |
  +-- Sai -> patch nhỏ hoặc forward-only migration mới
```

Luồng prompt nên dùng:

```text
Explore database layer
  -> Data model proposal
  -> Migration safety review
  -> Plan file-by-file
  -> Implement migration/seed without running commands
  -> Review diff
  -> Human-run dev/test migration
  -> Verify
```

## Bảng so sánh

| Chủ đề | Nên làm | Không nên làm |
| --- | --- | --- |
| DB target | Xác nhận bằng metadata query trước khi migrate | Tin vào tên terminal hoặc giả định `.env` đúng |
| Migration | Tạo migration nhỏ, review được, forward-only | Gộp schema, backfill, refactor, seed production trong một patch |
| Destructive SQL | Chặn `DROP`, `TRUNCATE`, `DELETE` không điều kiện nếu chưa có RFC/backup | Để Claude tự chạy rollback hoặc reset DB |
| Constraint | Đặt constraint cho invariant quan trọng | Chỉ rely vào app validation |
| Index | Gắn với query pattern cụ thể | Index mọi column để "phòng xa" |
| Seed | Idempotent, ID cố định, dev/test only | Dùng production dump hoặc tạo duplicate mỗi lần chạy |
| Transaction | Dùng transaction cho migration/seed phù hợp | Assume mọi DDL đều chạy được trong transaction |
| Production | Backup, review SQL, plan deploy, monitoring | Chạy trực tiếp từ prompt của AI |

| Thay đổi schema | Mức rủi ro | Cách xử lý |
| --- | --- | --- |
| Tạo bảng mới | Thấp | Phù hợp Day 09, vẫn cần review constraint/index |
| Thêm nullable column | Thấp đến vừa | Deploy app tương thích ngược |
| Thêm unique constraint trên data cũ | Vừa | Kiểm tra duplicate trước, clean/backfill |
| Thêm `NOT NULL` | Vừa đến cao | Backfill trước, validate sau |
| Tạo index trên bảng lớn | Vừa đến cao | Cân nhắc concurrent/index window |
| Rename column/table | Cao | Expand/contract, tránh phá app cũ |
| Drop data/schema | Rất cao | Không để AI chạy; cần backup/RFC |

| Command | Chạy ở đâu | Dùng để làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `git status --short` | Root `taskflow-ai` | Kiểm tra working tree | Rỗng hoặc file đã hiểu | Chồng lên thay đổi worker khác nếu bỏ qua |
| `find . -maxdepth 4 -name package.json` | Root `taskflow-ai` | Tìm package backend | Danh sách `package.json` | Read-only, rủi ro thấp |
| `rg "\"(migrate|migration|seed|db):" -n package.json backend/package.json apps` | Root `taskflow-ai` | Tìm script migration/seed | Script liên quan DB | Path sai có thể báo lỗi, cần đọc package thật |
| `psql "$DATABASE_URL" -c "select current_database(), current_user, inet_server_addr(), inet_server_port();"` | Root/backend có env dev/test | Xác nhận DB target | Tên DB dev/test, user, host, port | Nếu ra production thì dừng ngay |
| `claude --permission-mode plan` | Root `taskflow-ai` | Cho Claude đọc/lập plan | Session sẵn sàng | Plan sai nếu Claude đọc thiếu file |
| `claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)"` | Root `taskflow-ai` | Giới hạn tool family và auto-approve Git read-only | Session sẵn sàng | Command migration vẫn có thể được Claude đề xuất và xin quyền, không approve trước khi xác nhận DB dev/test |
| `git diff --stat` | Root `taskflow-ai` | Xem phạm vi patch | File list khớp plan | Không thấy SQL nguy hiểm |
| `git diff` | Root `taskflow-ai` | Review patch chi tiết | SQL/seed đúng plan | Diff dài dễ bỏ sót |
| `npm run db:migrate:status` | Folder backend có script | Xem migration pending/applied | Day 09 pending trước khi chạy | Script/env sai có thể trỏ DB khác |
| `npm run db:migrate:dev` | Folder backend có script | Chạy migration dev | Applied thành công | Nguy hiểm nếu env trỏ production |
| `npm run db:seed` | Folder backend có script | Chạy seed dev/test | Thành công, không duplicate khi chạy lại | Ghi DB sai nếu env sai |
| `npm run test -- --run tasks` | Folder backend | Chạy test liên quan tasks | Test pass | Filter phụ thuộc test runner |

| Index/constraint | Lý do | Rủi ro nếu thiếu |
| --- | --- | --- |
| `users.email` unique | Không cho duplicate user email | App có thể tạo user trùng |
| `tasks.user_id` foreign key | Task phải thuộc user tồn tại | Orphan task, join sai |
| `tasks.status` check | Status thuộc workflow hợp lệ | Data bẩn làm UI/API lỗi |
| `tasks.priority` check | Priority trong range | Sort/filter thiếu nhất quán |
| `tasks.title` non-empty | Task phải có nội dung | API có task rỗng |
| `tasks(user_id, status, created_at)` index | List task theo user/status | Query list chậm khi data tăng |

## Lỗi thường gặp

1. Để Claude tự chọn migration tool  
   Claude có thể thêm Prisma/Drizzle/Knex mới dù project đã có tool. Cách sửa: bắt Claude đọc `package.json`, migration folder và database client trước.

2. Chạy migration khi chưa xác nhận DB target  
   `.env` có thể trỏ staging hoặc production. Cách sửa: chạy query metadata và chỉ migrate dev/test.

3. Seed không idempotent  
   Chạy seed hai lần tạo duplicate user/task. Cách sửa: dùng fixed ID và `ON CONFLICT` hoặc upsert theo tool.

4. Index không có query pattern  
   Index dư làm write chậm, migration lâu, disk tăng. Cách sửa: mỗi index phải có query cụ thể.

5. Constraint quá lỏng  
   App validation có thể bị bypass. Cách sửa: những invariant cốt lõi phải nằm ở DB.

6. Constraint quá chặt khi có data cũ  
   Migration fail ở staging/prod. Cách sửa: kiểm tra data trước, backfill, validate theo bước.

7. Rollback nhầm nghĩa  
   `git restore` chỉ rollback file. Rollback DB sau khi migration applied có thể mất dữ liệu. Cách sửa: phân biệt rollback file, rollback dev DB, forward-only production fix.

8. Dùng `CASCADE` cho nhanh  
   `DROP ... CASCADE` hoặc foreign key cascade có thể xóa dây chuyền. Cách sửa: chỉ dùng khi domain và reviewer approve rõ.

9. Tạo index concurrently trong migration transaction  
   PostgreSQL không cho `CREATE INDEX CONCURRENTLY` trong transaction block. Cách sửa: tách migration hoặc cấu hình tool đúng.

10. Dùng production dump làm seed  
    Có thể lộ dữ liệu khách hàng. Cách sửa: seed synthetic data bằng domain `.example.test`, ID cố định, không chứa secret.

## Cách debug

Khi không biết project dùng migration tool nào, chạy trong root `taskflow-ai`:

```bash
rg "\"(migrate|migration|seed|db):" -n package.json backend/package.json apps
```

Lệnh này tìm script liên quan database. Output kỳ vọng là tên script migration/seed thật. Rủi ro thấp vì read-only; nếu không ra kết quả, yêu cầu Claude đọc thêm folder backend và docs nội bộ.

Prompt tiếp theo:

```text
Không tìm thấy script migration rõ ràng.
Hãy đọc package.json, database client setup và folder db/migrations nếu có.
Chỉ đọc file, không đề xuất thêm dependency ngay.
Nêu 2 phương án tối thiểu và trade-off.
```

Khi nghi ngờ env trỏ nhầm DB, chạy trong folder backend hoặc root có env:

```bash
psql "$DATABASE_URL" -c "select current_database(), current_user, inet_server_addr(), inet_server_port();"
```

Lệnh này xác nhận database đang kết nối. Output kỳ vọng là DB dev/test. Rủi ro thấp vì read-only; nếu output không rõ, dừng migration và hỏi team.

Khi migration fail do constraint, chạy trong DB dev/test:

```bash
psql "$DATABASE_URL" -c "select conname, contype from pg_constraint where conrelid in ('users'::regclass, 'tasks'::regclass) order by conname;"
```

Lệnh này liệt kê constraint của `users` và `tasks`. Output kỳ vọng có constraint đã đặt tên rõ. Rủi ro thấp vì read-only; nếu table chưa tồn tại, query báo lỗi và cần kiểm tra migration applied.

Đưa lỗi vào Claude:

```text
Migration fail với lỗi constraint sau. Hãy phân tích, chưa sửa file.

Hãy xác định:
- Constraint nào fail.
- Data hoặc seed nào vi phạm.
- Schema sai hay seed sai.
- Patch nhỏ nhất là gì.
- Có cần thay đổi data model đã duyệt không.
```

Khi seed bị duplicate, chạy trong DB dev/test:

```bash
psql "$DATABASE_URL" -c "select email, count(*) from users group by email having count(*) > 1;"
```

Lệnh này tìm email duplicate. Output kỳ vọng là 0 row. Rủi ro thấp vì read-only. Nếu có row, seed chưa idempotent hoặc unique constraint thiếu.

Khi cần review SQL nguy hiểm, chạy trong root `taskflow-ai`:

```bash
git diff | rg -n "DROP|TRUNCATE|DELETE FROM|CASCADE|ALTER COLUMN|SET NOT NULL|TYPE|RENAME|down|rollback"
```

Lệnh này tìm từ khóa rủi ro trong diff. Output kỳ vọng rỗng hoặc chỉ có nội dung đã được giải thích. Rủi ro thấp vì read-only; đây không thay thế review thủ công.

Khi muốn rollback file trước khi applied, chạy trong root `taskflow-ai`:

```bash
git restore -- backend/db/migrations/path-to-day-09-migration.sql backend/db/seeds/path-to-seed.sql
```

Lệnh này rollback file tracked ví dụ. Output thường rỗng. Rủi ro: mất thay đổi trong file đó; chỉ dùng cho file bạn sở hữu trong task.

## Link tài liệu nên đọc

- Claude Code Quickstart: https://docs.anthropic.com/en/docs/claude-code/quickstart
- Claude Code Settings: https://docs.anthropic.com/en/docs/claude-code/settings
- Claude Code Hooks: https://docs.anthropic.com/en/docs/claude-code/hooks
- Claude Code Best Practices: https://www.anthropic.com/engineering/claude-code-best-practices
- PostgreSQL CREATE TABLE: https://www.postgresql.org/docs/current/sql-createtable.html
- PostgreSQL ALTER TABLE: https://www.postgresql.org/docs/current/sql-altertable.html
- PostgreSQL CREATE INDEX: https://www.postgresql.org/docs/current/sql-createindex.html
- PostgreSQL INSERT và `ON CONFLICT`: https://www.postgresql.org/docs/current/sql-insert.html
- PostgreSQL Constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Git diff documentation: https://git-scm.com/docs/git-diff
- Git restore documentation: https://git-scm.com/docs/git-restore
- OWASP Database Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html
- Prisma Migrate docs nếu project dùng Prisma: https://www.prisma.io/docs/orm/prisma-migrate
- Drizzle migrations docs nếu project dùng Drizzle: https://orm.drizzle.team/docs/migrations
- Knex migrations docs nếu project dùng Knex: https://knexjs.org/guide/migrations.html
