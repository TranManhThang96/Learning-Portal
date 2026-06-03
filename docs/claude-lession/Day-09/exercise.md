# Exercise — Day 09

## Bài 1 — Cơ bản

Mục tiêu: dùng Claude Code ở `plan` mode để khảo sát database layer của `taskflow-ai` và thiết kế schema `users/tasks`, chưa sửa file.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.

2. Kiểm tra working tree:

```bash
git status --short
```

Lệnh này chạy ở root repo để xem file đang thay đổi. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có file của worker khác, bạn có thể tạo migration trên nền code chưa ổn định; dừng lại và đọc diff trước.

3. Tìm migration/seed script:

```bash
rg "\"(migrate|migration|seed|db):" -n package.json backend/package.json apps
```

Lệnh này chạy ở root repo để tìm script database trong các package phổ biến. Output kỳ vọng có script migration/seed hoặc không có gì nếu project chưa thiết lập. Rủi ro thấp vì read-only; nếu path không tồn tại, đọc `package.json` thật thay vì đoán.

4. Xác nhận DB target nếu đã có `DATABASE_URL`:

```bash
psql "$DATABASE_URL" -c "select current_database(), current_user, inet_server_addr(), inet_server_port();"
```

Lệnh này chạy ở root hoặc backend nơi env dev/test được load. Output kỳ vọng cho thấy DB dev/test, ví dụ `taskflow_ai_dev` hoặc `taskflow_ai_test`. Rủi ro: nếu hiện ra DB production/staging không mong muốn, dừng toàn bộ migration task.

5. Mở Claude Code:

```bash
claude --permission-mode plan
```

Lệnh này chạy ở root repo để mở Claude ở mode đọc/lập plan. Output kỳ vọng là session sẵn sàng. Rủi ro: Claude vẫn có thể suy diễn nếu không bị yêu cầu nêu bằng chứng.

6. Gửi prompt khám phá:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát database layer cho Day 09.

Ràng buộc:
- Chỉ đọc file, chưa sửa.
- Tìm migration tool, migration folder, seed mechanism, database client/ORM, test DB setup và script package.json.
- Nêu rõ file đã đọc và bằng chứng từ code.
- Không chạy migration, seed, Docker command hoặc Git command destructive.
- Không đề xuất thêm dependency nếu project đã có migration tool.
```

7. Gửi prompt thiết kế schema:

```text
Thiết kế data model users/tasks cho Day 09.

Output cần có:
- Bảng columns cho users và tasks: name, type, nullable, default.
- Constraint: primary key, unique, foreign key, check.
- Index và query pattern tương ứng.
- Delete behavior cho foreign key.
- Seed data plan idempotent.
- Migration safety review: destructive risk, transaction, lock, rollback/forward-only.

Chưa implement.
```

Kết quả cần nộp:

- File list Claude đã đọc.
- Migration tool và seed mechanism tìm được.
- Schema proposal cho `users` và `tasks`.
- Danh sách constraint/index kèm lý do.
- 5 rủi ro nếu chạy migration mà không review.

## Bài 2 — Thực tế

Mục tiêu: tạo migration và seed idempotent cho `users/tasks` bằng Claude Code, nhưng human mới là người chạy migration trên dev/test.

Yêu cầu:

1. Yêu cầu Claude lập plan file-by-file:

```text
Lập plan implement migration và seed Day 09 cho users/tasks.

Ràng buộc:
- Tối đa 7 bước.
- Mỗi bước ghi file sẽ tạo/sửa.
- Chỉ dùng migration tool/convention hiện có.
- Không đổi API, service, frontend hoặc README.
- Không thêm dependency nếu chưa được approve.
- Không chạy migration, seed, reset DB, Docker command, git add, git commit, git reset hoặc git clean.
- Seed phải idempotent.
- Chờ tôi approve trước khi edit.
```

2. Sau khi approve plan, mở session edit:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)"
```

Lệnh này chạy ở root `taskflow-ai` để giới hạn tool family vào đọc/sửa file và Bash, đồng thời auto-approve riêng Git read-only. Output kỳ vọng là session sẵn sàng. Rủi ro: migration không được auto-approve nhưng Claude vẫn có thể xin quyền chạy; chỉ approve sau khi xác nhận DB dev/test và review diff. Nếu bạn mở rộng thành `Bash(*)`, AI có thể chạy command ngoài plan.

3. Gửi prompt implement:

```text
Implement migration users/tasks và seed dev/test theo plan đã duyệt.

Ràng buộc:
- Chỉ chạm file trong plan.
- Không chạy command.
- Không dùng DROP, TRUNCATE, DELETE không điều kiện, reset DB, Docker volume command hoặc destructive rollback.
- users phải có id, email, name, created_at, updated_at.
- tasks phải có id, user_id, title, description, status, priority, due_at, created_at, updated_at.
- tasks.user_id tham chiếu users.id với delete behavior đã duyệt.
- title không được rỗng sau trim, status thuộc tập hợp hợp lệ, priority trong range.
- Index phải có query pattern cụ thể.
- Seed dùng ID cố định và chạy lại không duplicate.
- Sau khi edit, tóm tắt diff, SQL chính, command human nên chạy và rủi ro.
```

4. Review phạm vi patch:

```bash
git diff --stat
```

Lệnh này chạy ở root repo để xem file changed. Output kỳ vọng chỉ có migration, seed và file manifest/test nếu plan có. Rủi ro: không thấy logic SQL, chỉ dùng để phát hiện patch rộng.

5. Review chi tiết:

```bash
git diff
```

Lệnh này chạy ở root repo để xem toàn bộ patch. Output kỳ vọng không có destructive SQL, seed idempotent, constraint/index đúng plan. Rủi ro: diff dài dễ bỏ sót, cần review keyword rủi ro.

6. Tìm keyword nguy hiểm:

```bash
git diff | rg -n "DROP|TRUNCATE|DELETE FROM|CASCADE|ALTER COLUMN|SET NOT NULL|TYPE|RENAME|down|rollback"
```

Lệnh này chạy ở root repo để lọc từ khóa rủi ro trong diff. Output kỳ vọng rỗng hoặc có dòng đã được giải thích và approve. Rủi ro thấp vì read-only; không thay thế review thủ công.

7. Human tự chạy migration trên dev/test bằng script thật. Ví dụ nếu project có script:

```bash
npm run db:migrate:dev
```

Lệnh này chạy trong folder backend có `package.json` và env dev/test. Output kỳ vọng báo migration Day 09 applied thành công. Rủi ro cao nếu env trỏ production; phải xác nhận DB target trước.

8. Chạy seed hai lần:

```bash
npm run db:seed
```

Lệnh này chạy trong folder backend để tạo seed dev/test. Output kỳ vọng seed thành công. Rủi ro: nếu seed không idempotent sẽ duplicate.

```bash
npm run db:seed
```

Lệnh này chạy lại để kiểm tra idempotency. Output kỳ vọng vẫn thành công và số row không tăng ngoài dự kiến. Rủi ro giống lần đầu.

Kết quả cần nộp:

- Diff summary.
- Migration file path và seed file path.
- Command migration/seed thật đã chạy.
- Output chính.
- Kết quả chạy seed hai lần.
- Issue còn lại nếu có.

## Bài 3 — Nâng cao

Mục tiêu: verify constraint, foreign key, index và seed bằng command/test cụ thể; yêu cầu Claude Code review nhưng không tự sửa.

Yêu cầu:

1. Kiểm tra schema sau migration:

```bash
psql "$DATABASE_URL" -c "\d users"
```

Lệnh này chạy ở root hoặc backend nơi env dev/test được load. Output kỳ vọng thấy column, primary key và unique index email. Rủi ro thấp nếu DB là dev/test.

```bash
psql "$DATABASE_URL" -c "\d tasks"
```

Lệnh này chạy ở cùng nơi để xem bảng `tasks`. Output kỳ vọng thấy foreign key tới `users`, check constraint và index. Rủi ro thấp nếu read-only trên dev/test.

2. Kiểm tra index:

```bash
psql "$DATABASE_URL" -c "select tablename, indexname from pg_indexes where tablename in ('users', 'tasks') order by tablename, indexname;"
```

Lệnh này chạy trên DB dev/test để liệt kê index. Output kỳ vọng có unique email và index phục vụ list task. Rủi ro thấp vì read-only.

3. Kiểm tra foreign key bằng insert cố tình fail:

```bash
psql "$DATABASE_URL" -c "insert into tasks (id, user_id, title, status, priority) values ('00000000-0000-4000-8000-000000009999', '00000000-0000-4000-8000-000000009998', 'Invalid FK', 'todo', 3);"
```

Lệnh này chạy trên DB dev/test để thử tạo task tham chiếu user không tồn tại. Output kỳ vọng là lỗi foreign key violation. Rủi ro: đây là write command cố tình fail; không chạy trên production.

4. Kiểm tra duplicate seed:

```bash
psql "$DATABASE_URL" -c "select email, count(*) from users group by email having count(*) > 1;"
```

Lệnh này chạy trên DB dev/test để tìm email duplicate. Output kỳ vọng là 0 row. Rủi ro thấp vì read-only.

5. Chạy test liên quan:

```bash
npm run test -- --run tasks
```

Lệnh này chạy trong folder backend có `package.json` để chạy test liên quan tasks nếu test runner hỗ trợ filter. Output kỳ vọng test pass. Rủi ro: filter syntax phụ thuộc project; nếu không hỗ trợ, dùng script test chuẩn.

6. Yêu cầu Claude review kết quả:

```text
Review kết quả verify migration Day 09, không sửa file.

Input:
- Schema output users/tasks.
- Index list.
- Kết quả seed chạy hai lần.
- Test output.

Hãy phân loại:
- Blocker.
- Should fix.
- Nice to have.
- Test gaps.

Không đề xuất destructive rollback. Nếu cần sửa, đề xuất patch nhỏ hoặc forward-only migration.
```

Kết quả cần nộp:

- Evidence rằng constraint hoạt động.
- Evidence rằng seed idempotent.
- Evidence rằng index tồn tại đúng mục tiêu.
- Review của Claude và quyết định accept/reject của bạn.

## Bài 4 — Review & Reflection

Mục tiêu: biến kinh nghiệm Day 09 thành rule vận hành cho team khi dùng Claude Code với database.

Trả lời các câu hỏi:

1. Data model cuối cùng có những bảng, constraint và index nào?
2. Constraint nào bạn đặt ở database thay vì chỉ ở app? Vì sao?
3. Index nào có query pattern rõ? Index nào bạn quyết định không thêm?
4. Seed có idempotent không? Bạn chứng minh bằng cách nào?
5. Nếu migration này chạy nhầm production, rủi ro lớn nhất là gì?
6. Claude Code có cố chạy migration hoặc đề xuất command nguy hiểm không? Bạn chặn thế nào?
7. Với migration production trong tương lai, bạn sẽ yêu cầu backup, lock analysis và forward-only plan ra sao?
8. Bạn sẽ thêm rule gì vào `CLAUDE.md` để Claude không tự chạy destructive migration?

Gợi ý prompt reflection:

```text
Dựa trên Day 09, hãy giúp tôi viết rule database workflow cho CLAUDE.md của taskflow-ai.

Yêu cầu:
- Rule phải cụ thể cho migration, seed, constraint, index, transaction và production data.
- Có danh sách command/SQL bị cấm nếu chưa được human approve.
- Có rule xác nhận DB target dev/test trước khi migrate.
- Có rule seed idempotent.
- Có rule review diff trước khi chạy command.
- Không viết chung chung.
```

Kết quả cần nộp:

- Reflection 10-15 dòng.
- Rule đề xuất cho `CLAUDE.md`.
- Một checklist cá nhân trước khi chạy migration.

## Tiêu chí hoàn thành

- Đã dùng `claude --permission-mode plan` để khảo sát database layer trước khi sửa.
- Claude nêu rõ file đã đọc và bằng chứng.
- Có data model `users/tasks` với column, type, nullable, default, constraint và index rõ ràng.
- Có migration tạo bảng, foreign key, check constraint và index theo plan.
- Có seed dev/test idempotent, chạy lại không duplicate.
- Không có `DROP`, `TRUNCATE`, `DELETE` không điều kiện, reset DB, Docker volume delete hoặc destructive rollback.
- Đã xác nhận DB target là dev/test trước khi chạy migration.
- Đã review `git diff --stat` và `git diff`.
- Đã chạy migration bằng script thật của project trên dev/test.
- Đã verify table, constraint, index và seed bằng command hoặc test.
- Đã chạy test liên quan hoặc ghi rõ lý do nếu project chưa có test setup.
- Biết phân biệt rollback file, rollback dev DB và forward-only production fix.

## Gợi ý nếu bí

Nếu Claude không tìm được migration tool:

```text
Hãy đọc package.json, database client setup, docker-compose.yml, env example và các folder db/prisma/drizzle/migrations nếu có.
Chỉ đọc file.
Không thêm dependency.
Nêu 2 phương án tối thiểu và trade-off.
```

Nếu Claude đề xuất migration destructive:

```text
Từ chối phần destructive.
Hãy viết lại plan Day 09 chỉ gồm tạo bảng users/tasks, constraint, index và seed idempotent.
Không DROP, TRUNCATE, DELETE, reset DB, CASCADE nguy hiểm hoặc rollback destructive.
Chưa sửa file.
```

Nếu không chắc DB target:

```text
Tôi chưa xác nhận DB target.
Hãy dừng mọi đề xuất chạy migration.
Chỉ liệt kê các bước read-only để xác nhận môi trường dev/test mà không lộ credential.
```

Nếu seed duplicate:

```text
Seed chạy hai lần tạo duplicate.
Hãy phân tích nguyên nhân, chưa sửa file.
Kiểm tra seed dùng fixed ID/upsert chưa, unique constraint email có chưa, và conflict target có đúng không.
Đề xuất patch nhỏ nhất.
```

Nếu migration applied trên dev/test nhưng schema sai:

```text
Migration đã applied trên dev/test và schema sai.
Không đề xuất production rollback.
Hãy đề xuất 2 phương án:
1. Sửa bằng rollback/reset chỉ cho dev/test disposable.
2. Sửa bằng forward-only migration mới.
Nêu rủi ro từng phương án.
Chưa sửa file.
```

## Đáp án tham khảo hoặc expected result

Kết quả tốt cho Bài 1:

- Claude đọc đúng `package.json`, migration folder, database client/ORM, seed setup và test DB setup.
- Data model có `users` và `tasks` rõ ràng.
- `tasks.user_id` có foreign key tới `users.id`.
- `users.email` unique.
- `tasks.title`, `tasks.status`, `tasks.priority` có check constraint.
- Index được giải thích bằng query pattern.
- Không có đề xuất chạy migration hoặc reset DB.

Kết quả tốt cho Bài 2:

- Có migration file theo convention thật của project.
- Có seed file hoặc seed script theo convention thật của project.
- Seed dùng ID cố định và upsert/`ON CONFLICT`.
- `git diff --stat` chỉ có file trong plan.
- `git diff` không có destructive SQL.
- Migration chạy thành công trên dev/test.
- Seed chạy hai lần không duplicate.

Ví dụ diff summary chấp nhận được:

```text
2 files changed, 95 insertions(+)
```

Con số chỉ là ví dụ. Quan trọng là file list khớp plan và không có thay đổi ngoài scope.

Kết quả tốt cho Bài 3:

- `\d users` cho thấy primary key và unique email.
- `\d tasks` cho thấy foreign key, check constraint và index.
- Insert task với `user_id` không tồn tại fail bằng foreign key violation.
- Query duplicate email trả 0 row.
- Test liên quan tasks pass hoặc test gap được ghi rõ.
- Claude review không phát hiện blocker.

Kết quả tốt cho Bài 4:

Rule mẫu có thể đưa vào `CLAUDE.md`:

```text
- Với database migration, luôn bắt đầu bằng read-only exploration và nêu file đã đọc.
- Không chạy migration, seed, reset DB, Docker volume command hoặc rollback destructive nếu chưa được human approve.
- Trước khi migrate, human phải xác nhận DB target là dev/test hoặc có production checklist riêng.
- Không dùng DROP, TRUNCATE, DELETE không điều kiện, CASCADE nguy hiểm, ALTER COLUMN TYPE hoặc SET NOT NULL trên bảng có data nếu chưa có plan.
- Mọi seed dev/test phải idempotent, dùng ID cố định và không chứa production data.
- Mỗi index mới phải có query pattern cụ thể.
- Mỗi constraint mới phải có edge case/test tương ứng.
- Sau khi edit migration, báo file changed, SQL chính, command verify và known risks; human review diff trước khi chạy.
- Production fix ưu tiên forward-only migration, backup và monitoring.
```
