# Exercise — Day 10

## Bài 1 — Cơ bản

Mục tiêu: dùng Claude Code ở `plan` mode để khảo sát frontend React và viết UI contract cho task list, chưa sửa file.

Yêu cầu:

1. Mở terminal tại thư mục gốc `taskflow-ai`.
2. Kiểm tra working tree:

```bash
git status --short
```

Lệnh này chạy ở root repo để xem file đang thay đổi. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có file lạ, bạn có thể chồng diff lên thay đổi của người khác; dừng lại và đọc trước.

3. Tìm frontend package:

```bash
find . -maxdepth 3 -name package.json
```

Lệnh này chạy ở root repo trên bash để tìm các package Node. Output kỳ vọng có path frontend, ví dụ `./frontend/package.json`. Rủi ro thấp vì read-only; nếu dùng PowerShell, dùng lệnh ở bước 4.

4. Nếu dùng PowerShell:

```powershell
Get-ChildItem -Recurse -Filter package.json -Depth 3
```

Lệnh này chạy ở root repo để tìm `package.json`. Output kỳ vọng liệt kê frontend/backend package. Rủi ro thấp; repo lớn có thể mất vài giây.

5. Mở Claude Code ở plan mode:

```bash
claude --permission-mode plan
```

Lệnh này chạy ở root repo để mở Claude Code trong workflow đọc/lập plan. Output kỳ vọng là session sẵn sàng. Rủi ro thấp hơn implement mode, nhưng Claude vẫn có thể suy diễn nếu đọc thiếu file.

6. Gửi prompt:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát frontend React để chuẩn bị tạo task list UI.

Ràng buộc:
- Chỉ đọc file, chưa sửa.
- Nêu rõ file đã đọc và bằng chứng.
- Tìm React entrypoint, routing/page, component pattern, styling pattern, API client/fetch wrapper, env config và test setup.
- Tìm API contract tasks từ Day 08/09 hoặc backend routes/schema hiện có.
- Không đề xuất landing page, không đổi state library, không thêm UI framework, không sửa backend.
```

7. Yêu cầu Claude viết UI contract:

```text
Hãy viết UI contract cho task list React dựa trên convention vừa đọc.

Contract phải có:
- Component boundary: page/container, API client/hook nếu cần, TaskList, TaskItem, TaskForm.
- Data contract: endpoint, request, response, error shape và field render.
- UI states: loading, error, empty, list/success, submitting, validation error.
- Accessibility: semantic HTML, label, keyboard, focus, aria-live/aria-busy nếu phù hợp.
- Responsive behavior.
- Test cases tối thiểu.

Chưa implement.
```

Kết quả cần nộp: file list Claude đã đọc, UI contract, component boundary, data contract, UI state matrix, test cases dự kiến và 3 rủi ro nếu implement ngay không có plan.

## Bài 2 — Thực tế

Mục tiêu: implement slice đầu tiên của task list UI: fetch `GET /tasks`, render loading/error/empty/list state và bám component pattern hiện có.

Phạm vi đề xuất: chỉ đọc task list, chưa cần create/update/delete. Nếu project đã có list, chọn slice create task với validation/submitting state.

Yêu cầu:

1. Từ UI contract ở Bài 1, yêu cầu Claude lập plan file-by-file:

```text
Lập plan implement slice đầu tiên: fetch GET /tasks và render task list UI.

Ràng buộc:
- Tối đa 6 bước.
- Mỗi bước ghi file sẽ sửa/tạo.
- Chỉ chạm frontend.
- Không thêm dependency.
- Không đổi architecture, routing lớn, styling system, state library hoặc API contract.
- Không tạo landing page.
- Không sửa backend, migration, seed, README hoặc file Day khác.
- Chờ tôi approve trước khi edit.
```

2. Sau khi approve plan, mở session implement:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)" "Bash(npm run lint *)" "Bash(npm run test *)" "Bash(npm run build *)"
```

Lệnh này chạy ở root `taskflow-ai` để giới hạn tool family vào đọc/sửa file và Bash, đồng thời auto-approve command kiểm tra trong phạm vi hẹp. Output kỳ vọng là session sẵn sàng. Rủi ro: nếu allowlist mở rộng quá mức, Claude có thể chạy install, dev server dài hạn hoặc command ngoài plan mà không hỏi.

3. Gửi prompt implement:

```text
Implement theo plan đã duyệt cho slice GET /tasks.

Ràng buộc bắt buộc:
- Chỉ chạm file trong plan.
- Bám API contract Day 08/09; nếu response shape chưa rõ, dừng và hỏi.
- Không thêm dependency.
- Không tạo landing page.
- Không đổi state library, styling system hoặc routing lớn.
- Có loading, error, empty và list state visible.
- List dùng key ổn định từ task.id.
- Error state có action retry nếu phù hợp.
- Accessibility: heading đúng, list semantic, button thật, aria-busy hoặc status text nếu phù hợp.
- Không chạy npm install, git add, git commit, git reset, git clean, docker hoặc command xóa file.
- Sau khi edit, tóm tắt diff và test command cần chạy.
```

4. Review phạm vi patch:

```bash
git diff --stat
```

Lệnh này chạy ở root repo để xem số file/dòng thay đổi. Output kỳ vọng khớp file trong plan. Rủi ro: nếu xuất hiện file ngoài plan, dừng lại và yêu cầu Claude giải thích.

5. Review chi tiết:

```bash
git diff
```

Lệnh này chạy ở root repo để xem patch chi tiết. Output kỳ vọng: component boundary rõ, API contract đúng, loading/error/empty/list state có UI, không thêm dependency. Rủi ro: diff dài dễ bỏ sót; xem từng file nếu cần.

6. Chạy verify trong folder frontend có `package.json`:

```bash
npm run lint
```

Lệnh này chạy lint frontend. Output kỳ vọng không có error. Rủi ro: có thể fail vì lỗi cũ ngoài scope; ghi rõ nếu không liên quan.

```bash
npm run test -- --run
```

Lệnh này chạy test một lần nếu test runner hỗ trợ. Output kỳ vọng test pass và exit code `0`. Rủi ro: cú pháp `--run` phụ thuộc runner/script; nếu không hỗ trợ, dùng script test chuẩn của project.

```bash
npm run build
```

Lệnh này build frontend production. Output kỳ vọng build thành công. Rủi ro: build có thể cần env hoặc fail vì type issue cũ; không sửa ngoài scope.

Kết quả cần nộp: diff summary, test command đã chạy, output chính, screenshot hoặc mô tả UI states đã kiểm tra, và danh sách issue còn lại nếu có.

## Bài 3 — Nâng cao

Mục tiêu: bổ sung create task form kết nối `POST /tasks`, có validation, submitting state, focus behavior và review accessibility.

Yêu cầu:

1. Yêu cầu Claude review trạng thái hiện tại:

```text
Review task list UI hiện tại so với UI contract Day 10.
Chưa sửa file.
Liệt kê phần đã đủ, phần thiếu, validation thiếu, accessibility issue, responsive issue và test gap.
Phân loại theo Blocker, Should fix, Nice to have.
```

2. Yêu cầu plan cho create form:

```text
Lập plan bổ sung create task form kết nối POST /tasks.

Ràng buộc:
- Không đổi slice GET /tasks đã ổn nếu không cần.
- Không đổi API contract.
- Không thêm dependency.
- Không refactor rộng.
- Form phải có controlled input, label, validation title trim không rỗng, submitting state, error state và focus behavior sau success/error.
- Thêm test hoặc test plan cho validation và submit.
- Chờ tôi approve trước khi sửa.
```

3. Cho implement sau khi approve:

```text
Implement create task form theo plan đã duyệt.

Giới hạn:
- Chỉ chạm file trong plan.
- Bám POST /tasks contract từ Day 08/09.
- Không thêm dependency.
- Không dùng optimistic update nếu chưa có rollback/error behavior rõ; mặc định update UI sau API success.
- Disable submit khi title rỗng hoặc đang submitting.
- Error phải visible và không chỉ console.log.
- Sau success, clear input và xử lý focus theo UX đã nêu.
- Không sửa backend, migration, seed, README hoặc file Day khác.
```

4. Chạy test tập trung nếu project hỗ trợ filter trong folder frontend:

```bash
npm run test -- --run tasks
```

Lệnh này chạy test liên quan tasks nếu script/runner hỗ trợ filter. Output kỳ vọng test task UI pass. Rủi ro: cú pháp filter phụ thuộc runner; nếu không hỗ trợ, dùng `npm run test -- --run` hoặc script thật trong `package.json`.

5. Chạy app để kiểm tra thủ công trong folder frontend:

```bash
npm run dev -- --host 127.0.0.1
```

Lệnh này mở dev server local. Output kỳ vọng có URL localhost. Rủi ro: process dài hạn; dừng bằng `Ctrl+C`; không expose ra mạng nếu không cần.

6. Yêu cầu Claude review accessibility read-only:

```text
Review accessibility và keyboard của diff hiện tại, không sửa file.

Tập trung:
- Heading và landmark có hợp lý không.
- Input có label và error association không.
- Button có accessible name không.
- Có div clickable không.
- Submit bằng Enter hoạt động không.
- Focus sau submit success/error có hợp lý không.
- Loading/error message có được screen reader nhận biết không.
- Responsive có overflow hoặc text vỡ không.
```

7. Nếu patch sai, rollback theo file đã review:

```bash
git restore -- frontend/src/tasks/TaskListPage.tsx
```

Lệnh này chạy ở root repo để rollback một tracked file ví dụ. Output thường rỗng nếu thành công. Rủi ro: mất thay đổi chưa commit trong file đó; không dùng nếu file có thay đổi của người khác.

Nếu có file mới tạo sai và chắc chắn là của task này:

```bash
git clean -f -- frontend/src/tasks/TaskForm.tsx
```

Lệnh này chạy ở root repo để xóa một untracked file cụ thể. Output kỳ vọng là file bị remove. Rủi ro: xóa vĩnh viễn file chưa tracked; không dùng dạng rộng.

Kết quả cần nộp: form behavior, validation behavior, accessibility review, test output và quyết định accept/reject.

## Bài 4 — Review & Reflection

Mục tiêu: biến bài frontend thành rule làm việc cho team.

Trả lời các câu hỏi:

1. Component boundary cuối cùng của task list gồm những component/hook/client nào?
2. API contract nào từ Day 08/09 frontend đang phụ thuộc vào?
3. Claude Code có đề xuất tạo landing page, đổi state library, thêm dependency hoặc sửa file ngoài plan không? Bạn xử lý thế nào?
4. UI có đủ loading, error, empty, submitting và validation state chưa?
5. Accessibility issue quan trọng nhất bạn phát hiện là gì?
6. State nào bạn đã loại bỏ vì có thể derive từ state khác?
7. Nếu Day 11 viết Playwright e2e cho flow tạo task, selector/role nào sẽ ổn định nhất?
8. Bạn sẽ thêm rule gì vào `CLAUDE.md` để các task frontend sau không bị patch rộng?

Gợi ý prompt reflection:

```text
Dựa trên Day 10, hãy giúp tôi viết 10 rule frontend workflow cho CLAUDE.md của taskflow-ai.

Yêu cầu:
- Rule phải cụ thể cho React UI.
- Có rule về đọc component pattern, không tạo landing page, không đổi state library, API contract Day 08/09, UI states, accessibility, responsive, test và rollback.
- Có danh sách command không được tự chạy.
- Không viết chung chung.
```

Kết quả cần nộp: reflection ngắn 10-15 dòng và rule đề xuất cho `CLAUDE.md`.

## Tiêu chí hoàn thành

- Đã dùng `claude --permission-mode plan` để khảo sát frontend trước khi sửa.
- Có UI contract rõ cho task list.
- Component boundary có file list, không đổi architecture, không đổi state library, không thêm dependency ngoài duyệt.
- API integration bám contract Day 08/09, không bịa endpoint/response shape.
- Task list có loading, error, empty và list state.
- Create form nếu làm Bài 3 có controlled input, validation title, submitting state, error visible và focus behavior.
- Accessibility đạt mức tối thiểu: semantic HTML, label, keyboard, button thật, accessible status/error.
- Responsive không vỡ layout trên mobile/desktop cơ bản.
- Có test hoặc test plan cho render state và interaction chính.
- Đã chạy lint/test/build phù hợp và ghi lại output chính.
- Đã review `git diff --stat` và `git diff`.
- Biết rollback theo file, không dùng command phá toàn working tree.

## Gợi ý nếu bí

Nếu Claude không tìm được frontend:

```text
Hãy tìm các package.json, React entrypoint, Vite config, src/main.*, App.*, route/page và component folder.
Chỉ đọc file.
Nếu repo chưa có frontend, hãy đề xuất cấu trúc tối thiểu theo README hiện có, chưa tạo file.
```

Nếu Claude đề xuất landing page:

```text
Không tạo landing page trong Day 10.
Đây là task list UI cho app vận hành taskflow-ai.
Hãy viết lại plan bằng cách bám component/layout pattern hiện có, ưu tiên thông tin dense, action rõ và responsive.
Chưa implement.
```

Nếu Claude đề xuất thêm dependency:

```text
Không thêm dependency trong bài này nếu chưa có approval.
Hãy implement bằng component, state và styling pattern hiện có.
Nếu dependency thật sự cần, nêu trade-off và chờ quyết định, chưa sửa file.
```

Nếu API response shape chưa rõ:

```text
Trước khi implement, hãy đọc contract Day 08/09 hoặc backend route/schema liên quan.
Liệt kê endpoint, request, response, error shape và assumptions còn thiếu.
Không sửa file cho tới khi contract rõ.
```

Nếu test fail:

```text
Test fail như sau. Hãy phân tích nguyên nhân, chưa sửa file.
Phân loại lỗi: implementation bug, test sai expectation, thiếu mock API, jsdom/setup thiếu, hay môi trường.
Đề xuất patch nhỏ nhất.
```

Nếu accessibility chưa rõ:

```text
Hãy review task list UI theo accessibility checklist, không sửa file:
- semantic elements
- label/name
- keyboard
- focus
- aria-live/aria-busy
- error association
- disabled state
Phân loại Blocker/Should fix/Nice to have.
```

## Đáp án tham khảo hoặc expected result

Kết quả tốt cho Bài 1:

- Claude đọc đúng file frontend liên quan và API contract tasks, không sửa file.
- UI contract có component boundary, data contract, UI states, accessibility requirement, responsive behavior và test plan.
- Contract ghi rõ không landing page, không state library mới, không dependency mới, không sửa backend.

Kết quả tốt cho Bài 2:

- `GET /tasks` được gọi qua API client/fetch wrapper theo pattern hiện có.
- Loading state visible khi request đang chạy.
- Empty state visible khi danh sách rỗng.
- Error state visible khi request fail, có retry nếu phù hợp.
- List render task từ API, dùng `task.id` làm key.
- `git diff --stat` chỉ gồm file frontend trong plan.

Ví dụ diff summary chấp nhận được:

```text
5 files changed, 180 insertions(+), 20 deletions(-)
```

Con số này chỉ là ví dụ. Quan trọng là file list khớp plan, không có dependency/config/state-library drift và không chạm backend.

Kết quả tốt cho Bài 3:

- Form tạo task có label, controlled input và validation title sau khi trim.
- Submit bị disable khi title rỗng hoặc đang submitting.
- API error hiển thị trên UI.
- Sau success, input được clear và focus behavior hợp lý.
- Test hoặc manual verification bao phủ validation, submitting và success/error path.

Kết quả tốt cho Bài 4:

Rule mẫu có thể đưa vào `CLAUDE.md`:

```text
- Với React UI, luôn đọc component pattern, styling pattern, routing và API client trước khi implement.
- Không tạo landing page cho màn hình vận hành taskflow-ai.
- Không thêm state library, UI framework hoặc dependency mới nếu chưa được approve.
- Frontend phải bám API contract Day 08/09; nếu response shape chưa rõ, dừng và hỏi.
- Mọi list UI phải có loading, error, empty và success state visible.
- Form phải có label, controlled input, validation, submitting state và error visible.
- Dùng key ổn định từ id của data, không dùng index hoặc random key.
- Test UI theo behavior user thấy được, ưu tiên query theo role/name nếu dùng Testing Library.
- Không chạy npm install, git reset, git clean dạng rộng, docker command hoặc commit tự động.
- Sau mỗi patch, báo file changed, test command và known risks; human review diff trước khi commit.
```
