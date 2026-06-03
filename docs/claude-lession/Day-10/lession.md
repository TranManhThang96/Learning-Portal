# Day 10 — Frontend workflow với React

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên có thể:

- Dùng Claude Code để tạo UI React theo workflow có kiểm soát, không để AI tự biến task list thành landing page hoặc đổi design system.
- Yêu cầu Claude đọc component pattern, routing, styling, API client và test setup trước khi sửa file.
- Thiết kế component boundary rõ giữa container, presentational component, form, list item, API client và state hook nếu project đã có pattern tương ứng.
- Giữ state management tối giản: ưu tiên local state, derived state và custom hook nhỏ; không tự thêm Redux, Zustand, TanStack Query hoặc form library nếu project chưa dùng.
- Kết nối task list UI với API contract từ Day 08/09 mà không tự bịa response shape.
- Bắt buộc có loading, error, empty, submitting và retry state thay vì chỉ render happy path.
- Review accessibility: semantic HTML, label, keyboard, focus, `aria-live`, disabled state và responsive layout.
- Review diff frontend như senior reviewer: component size, prop contract, state duplication, API error handling, testability, maintainability và scope drift.

## 2. Bối cảnh thực tế

Frontend là nơi Claude Code dễ "làm đẹp quá tay". Một prompt ngắn như "create task list UI" có thể làm Claude tự tạo hero section, gradient background, card layout marketing, mock data cố định, state library mới, CSS framework mới hoặc endpoint giả không khớp backend. Với project `taskflow-ai`, điều đó gây hỏng workflow vì Day 08 đã định API contract, Day 09 đang xử lý data model, còn Day 10 chỉ nên nối UI vào contract hiện có.

Vấn đề thường gặp trong team:

- Component quá lớn: vừa fetch API, vừa transform data, vừa render list, vừa xử lý form, vừa format error.
- State bị duplicate: `tasks`, `filteredTasks`, `taskCount`, `hasTasks`, `isEmpty` đều lưu trong state dù có thể derive.
- Loading/error state chỉ có trong console, không hiện trên UI.
- Empty state bị bỏ quên nên màn hình trắng khi chưa có task.
- Button dùng `<div onClick>` hoặc icon không có accessible name.
- Form không có `label`, không quản lý focus sau khi submit lỗi hoặc tạo task thành công.
- Claude tự đổi endpoint, response shape hoặc thêm mock server thay vì đọc API contract Day 08/09.
- Patch chạm file global như theme, router, package manager, ESLint config hoặc README ngoài scope.

Claude Code hữu ích khi bạn buộc nó đi theo vòng lặp:

```text
observe design/API -> define UI state -> component boundary -> plan file-by-file -> implement small slice -> verify -> review diff
```

Không nên dùng Claude Code để tự động build UI khi:

- Chưa biết frontend hiện dùng React thuần, Vite, Next.js, CSS module, Tailwind hay component library nào.
- API contract backend chưa ổn định hoặc Day 09 migration đang thay đổi field quan trọng.
- Designer chưa chốt layout nhưng bạn lại yêu cầu Claude "make it beautiful".
- Bạn chưa có test command, lint command, build command hoặc cách chạy app local.
- Working tree đang có thay đổi của worker khác, đặc biệt trong `frontend/src`, `package.json`, routing hoặc shared component.

## 3. Kiến thức nền

React UI có kiểm soát nghĩa là Claude Code không được "sáng tạo tự do" trên toàn frontend. Developer phải đưa boundary: UI cần hiển thị dữ liệu gì, lấy từ API nào, component nào được sửa, state nào được phép thêm, interaction nào phải có, accessibility rule nào bắt buộc, command nào được chạy và command nào bị cấm.

### Component boundary

Một task list UI trong `taskflow-ai` nên được chia theo trách nhiệm, không theo cảm hứng của AI:

| Boundary | Trách nhiệm | Điều cần khóa với Claude Code |
| --- | --- | --- |
| Page/container | Fetch data, giữ trạng thái `loading/error/tasks/submitting`, truyền callback | Không nhét toàn bộ JSX và logic form vào một component khổng lồ |
| API client | Gọi `GET/POST/PATCH/DELETE /tasks`, parse response, map error | Không tự bịa endpoint hoặc response shape; đọc contract Day 08/09 |
| Task list | Render danh sách, empty state, keyboard-friendly structure | Dùng key ổn định từ `task.id`, không dùng array index |
| Task item | Hiển thị title/status/priority, action complete/delete/edit nếu có | Không tự thêm field ngoài API contract |
| Task form | Controlled input, validation client-side tối thiểu, submitting state | Có `label`, error text, disabled state và focus behavior |
| Shared UI component | Button, input, alert, spinner nếu project đã có | Không tạo design system mới nếu đã có component pattern |

Component boundary tốt giúp review dễ hơn: container test API state, presentational component test render state, API client test request/response, form test validation/focus. Nếu project đã có custom hook như `useTasks`, hãy bám pattern đó. Nếu chưa có, chỉ tạo custom hook khi nó giảm complexity thật sự; không tạo abstraction chỉ để "trông chuyên nghiệp".

### State management tối giản

React khuyến khích mô tả UI theo state. Với task list, state tối thiểu thường là:

| State | Nên lưu? | Lý do |
| --- | --- | --- |
| `tasks` | Có | Dữ liệu từ API |
| `status` hoặc `isLoading` | Có | Biểu diễn request lifecycle |
| `error` | Có | Hiển thị lỗi và retry |
| `newTitle` | Có | Controlled input |
| `isSubmitting` | Có | Tránh double submit |
| `taskCount` | Không | Derive từ `tasks.length` |
| `hasTasks` | Không | Derive từ `tasks.length > 0` |
| `filteredTasks` | Tùy | Derive nếu filter rẻ; memoize nếu expensive và có bằng chứng |

Không thêm global state library nếu bài toán chỉ có một page task list. Redux/Zustand/TanStack Query chỉ hợp lý khi project đã dùng hoặc có nhu cầu rõ: cache cross-page, invalidation phức tạp, optimistic update nhiều nơi, offline state hoặc shared server state. Trong Day 10, default là local state + API client nhỏ.

### UI state phải có

Task list UI không đạt nếu chỉ render danh sách thành công. Tối thiểu cần:

- Loading state khi lần đầu fetch task.
- Empty state khi API trả danh sách rỗng.
- Error state khi fetch fail, có thông điệp rõ và nút retry.
- Submitting state khi tạo task, disable submit để tránh double request.
- Validation state khi title rỗng hoặc chỉ có khoảng trắng.
- Refreshing state nếu đang refetch nhưng vẫn giữ danh sách cũ.

React docs nhấn mạnh conditional rendering và list rendering bằng `map()` với key ổn định. Với dữ liệu từ database/API, `task.id` là key đúng. Không dùng `Math.random()` hoặc array index vì insert/delete/reorder sẽ làm React mất track item, gây bug focus hoặc input state.

### API contract Day 08/09

Frontend không được tự quyết định contract. Trước khi code, yêu cầu Claude đọc:

- Route/API contract đã tạo ở Day 08.
- Data model/migration từ Day 09 nếu đã có.
- API client hoặc fetch wrapper hiện có.
- `.env.example` hoặc cách frontend cấu hình API base URL.
- Existing error format, ví dụ `{ error: { code, message } }`, `{ message }` hoặc `{ code, details }`.

Nếu Day 09 chưa hoàn tất, Day 10 nên dùng contract Day 08 và ghi rõ assumptions trong plan. Không sửa migration, seed hoặc backend trong bài này.

### Accessibility, keyboard và focus

Task list là UI vận hành hằng ngày, không phải demo. Claude Code phải xử lý các điểm sau:

- Dùng `<main>`, heading đúng cấp, `<form>`, `<label>`, `<input>`, `<button>`, `<ul>/<li>` khi phù hợp.
- Button phải là `<button>` thật để có keyboard interaction mặc định.
- Input có label visible hoặc accessible name rõ.
- Error message liên kết với input bằng `aria-describedby` nếu project có pattern.
- Loading vùng danh sách có `aria-busy` hoặc status text phù hợp.
- Error/success message dùng `aria-live="polite"` khi cần thông báo sau submit.
- Sau khi tạo task thành công, clear input và đưa focus về input hoặc item mới theo UX đã chọn.
- Trạng thái disabled phải có lý do rõ, không làm mất khả năng đọc lỗi bằng screen reader.
- Responsive không phải thêm hero. Với SaaS/task tool, layout nên gọn, dense, scan được trên desktop và mobile.

## 4. Step-by-step thực hành

Mục tiêu thực hành: dùng Claude Code để tạo task list UI trong frontend React của `taskflow-ai`, kết nối API tasks, có loading/error/empty/submitting state, accessibility cơ bản, responsive layout và review component quality. Không sửa README, không sửa backend, không sửa Day 09.

### Bước 1: Kiểm tra working tree và vị trí frontend

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git status --short
```

Lệnh này hiển thị working tree dạng ngắn. Output kỳ vọng là rỗng hoặc chỉ có file bạn hiểu rõ. Rủi ro: nếu có thay đổi của worker khác trong frontend, bạn có thể ghi đè hoặc review nhầm diff; dừng lại và đọc trước.

Chạy trong thư mục gốc `taskflow-ai` nếu dùng shell kiểu bash:

```bash
find . -maxdepth 3 -name package.json
```

Lệnh này tìm các package Node để xác định frontend nằm ở root, `frontend/`, `apps/web/` hay tên khác. Output kỳ vọng có ít nhất một `package.json`. Rủi ro thấp vì read-only; trên Windows PowerShell có thể không có `find` kiểu Unix.

Nếu dùng PowerShell, chạy trong thư mục gốc `taskflow-ai`:

```powershell
Get-ChildItem -Recurse -Filter package.json -Depth 3
```

Lệnh này là bản PowerShell để tìm `package.json`. Output kỳ vọng liệt kê path frontend/backend. Rủi ro thấp vì read-only; nếu repo lớn, command có thể mất vài giây.

Chạy trong thư mục frontend có `package.json`, ví dụ `taskflow-ai/frontend`:

```bash
npm pkg get scripts
```

Lệnh này đọc script hiện có như `dev`, `build`, `lint`, `test`. Output kỳ vọng là JSON chứa scripts. Rủi ro thấp; nếu package manager không phải npm, dùng lệnh tương ứng sau khi đọc repo, không tự đổi package manager.

### Bước 2: Mở Claude Code ở plan mode để đọc trước

Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --permission-mode plan
```

Lệnh này mở Claude Code ở mode đọc/lập plan trước khi sửa. Output kỳ vọng là session Claude Code sẵn sàng nhận prompt. Rủi ro: plan vẫn có thể sai nếu Claude đọc thiếu file hoặc suy diễn design/API contract.

Prompt khám phá:

```text
Bạn đang ở repo taskflow-ai. Hãy khảo sát frontend React để chuẩn bị tạo task list UI.

Ràng buộc:
- Chưa sửa file.
- Chỉ đọc file cần thiết.
- Nêu rõ file đã đọc và bằng chứng từ code.
- Tìm frontend entrypoint, routing/page hiện có, component pattern, styling pattern, API client/fetch wrapper, env config, test setup.
- Tìm API contract tasks từ Day 08/09 hoặc backend route/schema hiện có.
- Không đề xuất landing page, không đổi state library, không thêm UI framework, không sửa backend.
```

Kỳ vọng: Claude liệt kê file đã đọc, chỉ ra frontend package, cách chạy dev/build/test, component pattern hiện có và contract API tasks. Nếu Claude chưa đọc `package.json`, route/page entry, component folder hoặc API client mà đã lập plan, yêu cầu đọc bổ sung.

### Bước 3: Chốt UI contract và component boundary

Gửi prompt trong cùng session:

```text
Từ các file đã đọc, hãy đề xuất UI contract cho task list React.

Output cần có:
- Component boundary: container/page, API client/hook nếu cần, TaskList, TaskItem, TaskForm, shared component nếu dùng.
- Data contract lấy từ API tasks: endpoint, request, response, error shape, field được render.
- UI states bắt buộc: loading, error, empty, success/list, submitting, validation error.
- Accessibility checklist: semantic HTML, label, keyboard, focus, aria-live hoặc aria-busy nếu phù hợp.
- Responsive behavior cho mobile/desktop.
- Test cases nên có.
- Chưa sửa file.
```

Kỳ vọng: UI contract đủ cụ thể để review trước khi code. Nếu Claude đề xuất tạo dashboard rộng, analytics, auth, filter phức tạp, drag-and-drop hoặc theme mới, yêu cầu cắt scope về task list UI cơ bản nối API.

### Bước 4: Lập plan file-by-file

Prompt lập plan:

```text
Lập plan implement task list UI theo UI contract đã duyệt.

Ràng buộc:
- Plan tối đa 7 bước.
- Mỗi bước ghi file dự kiến sửa hoặc tạo.
- Chỉ chạm frontend.
- Không đổi architecture, routing lớn, styling system, package manager hoặc state library.
- Không thêm dependency nếu chưa có lý do rõ và chưa được approve.
- Không tạo landing page.
- Không sửa backend, migration, seed, README hoặc file của Day khác.
- Chờ tôi approve trước khi edit.
```

Plan tốt thường có dạng:

```text
1. Đọc/hoàn thiện API client tasks theo fetch wrapper hiện có.
2. Tạo hoặc cập nhật component TaskListPage/container để fetch tasks và giữ UI state.
3. Tạo TaskForm với controlled input, validation và submitting state.
4. Tạo TaskList/TaskItem presentational component bám design pattern hiện có.
5. Thêm loading/error/empty state và retry behavior.
6. Thêm accessibility attributes/focus behavior theo pattern hiện có.
7. Thêm test hoặc update test hiện có cho render state và interaction chính.
```

Nếu plan chạm quá nhiều file, yêu cầu Claude chia slice:

```text
Plan này quá rộng. Hãy chia slice 1 chỉ gồm GET /tasks render danh sách với loading/error/empty state.
Chưa implement.
```

### Bước 5: Cho implement với permission và boundary hẹp

Sau khi duyệt plan, mở Claude Code ở mode kiểm soát. Chạy trong thư mục gốc `taskflow-ai`:

```bash
claude --permission-mode default --tools "Read,Write,Edit,Bash" --allowedTools "Bash(git status *)" "Bash(git diff *)" "Bash(npm run lint *)" "Bash(npm run test *)" "Bash(npm run build *)"
```

Lệnh này giới hạn built-in tool family vào đọc/sửa file và Bash, đồng thời auto-approve một số command kiểm tra. Output kỳ vọng là session sẵn sàng. Rủi ro: `--allowedTools` không deny Bash command khác; command ngoài pattern sẽ phải hỏi theo `default` mode. Nếu mở rộng thành `Bash(*)`, Claude có thể chạy install, dev server dài hạn, migration hoặc command ngoài plan.

Prompt implement:

```text
Implement task list UI theo plan đã approve.

Ràng buộc bắt buộc:
- Chỉ sửa/tạo các file frontend đã liệt kê trong plan.
- Không sửa backend, migration, seed, README, package lock, config global hoặc file Day khác.
- Không thêm dependency mới.
- Không đổi state library, routing lớn, styling system hoặc component convention.
- Không tạo landing page; đây là UI vận hành cho taskflow-ai.
- Kết nối API theo contract Day 08/09; nếu response shape chưa rõ, dừng và hỏi.
- Có loading, error, empty, list/success, submitting và validation state.
- Dùng key ổn định từ task id, không dùng array index hoặc Math.random().
- Form có label, keyboard submit, disabled state hợp lý và không mất focus vô lý.
- Error/status message phải hiển thị trên UI, không chỉ console.log.
- Không chạy npm install, git add, git commit, git reset, git clean, docker hoặc command xóa file.
- Sau khi edit, tóm tắt diff theo file và nêu test command cần chạy.
```

Kỳ vọng: Claude tạo patch nhỏ, theo component boundary đã duyệt. Nếu Claude muốn sửa `package.json` để thêm UI library, đổi CSS framework hoặc tạo route marketing mới, từ chối và yêu cầu giải thích.

### Bước 6: Verify bằng lint/test/build và chạy app

Chạy trong thư mục frontend có `package.json`:

```bash
npm run lint
```

Lệnh này chạy lint theo script của frontend. Output kỳ vọng là không có error; warning phải được đọc, không tự động bỏ qua. Rủi ro: script có thể chưa tồn tại hoặc lint toàn repo chạm lỗi cũ; nếu vậy ghi rõ test gap thay vì sửa ngoài scope.

Chạy trong thư mục frontend có `package.json` nếu project có test runner:

```bash
npm run test -- --run
```

Lệnh này thường chạy test một lần nếu dùng Vitest. Output kỳ vọng là test pass và exit code `0`. Rủi ro: script có thể chạy watch mode hoặc cú pháp `--run` không phù hợp với runner; đọc `package.json` trước.

Chạy trong thư mục frontend có `package.json`:

```bash
npm run build
```

Lệnh này build frontend production. Output kỳ vọng có thư mục build như `dist/` và exit code `0`. Rủi ro: build có thể fail vì TypeScript/type issue cũ hoặc env thiếu; không sửa file ngoài Day 10 scope nếu lỗi không liên quan.

Chạy trong thư mục frontend có `package.json` khi cần kiểm tra thủ công:

```bash
npm run dev -- --host 127.0.0.1
```

Lệnh này mở Vite dev server chỉ trên localhost. Output kỳ vọng có URL local như `http://127.0.0.1:5173/`. Rủi ro: đây là process dài hạn; giữ terminal riêng, dừng bằng `Ctrl+C`, không dùng `--host 0.0.0.0` nếu không cần expose ra mạng.

Nếu cần kiểm tra backend API trước khi debug frontend, chạy trong terminal khác ở root hoặc backend folder đúng theo project:

```bash
curl -i http://localhost:3000/tasks
```

Lệnh này gọi thử endpoint tasks, thay port/path theo contract thực tế Day 08/09. Output kỳ vọng là status `200` và body đúng shape hoặc lỗi auth/dev rõ ràng. Rủi ro: port/path có thể khác; không sửa frontend để khớp một endpoint đoán mò.

### Bước 7: Review diff như frontend reviewer

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này cho biết phạm vi patch. Output kỳ vọng chỉ gồm file frontend trong plan. Rủi ro: `--stat` không nói logic đúng sai; dùng để phát hiện patch rộng bất thường.

Chạy trong thư mục gốc `taskflow-ai`:

```bash
git diff
```

Lệnh này hiển thị patch chi tiết. Output kỳ vọng: không có file ngoài plan, component boundary rõ, API contract đúng, UI state đầy đủ, accessibility không bị bỏ quên, test có assertion meaningful. Rủi ro: diff dài dễ bỏ sót; xem từng file nếu cần.

Ví dụ xem một file cụ thể, chạy ở root repo và thay path theo file thật:

```bash
git diff -- frontend/src/tasks/TaskListPage.tsx
```

Lệnh này giới hạn diff vào một component. Output kỳ vọng chỉ có thay đổi liên quan task list UI. Rủi ro thấp vì read-only.

Prompt review:

```text
Review diff hiện tại như senior React reviewer, không sửa file.

Tập trung:
- Component boundary có rõ không hay component bị phình quá lớn.
- State có tối giản không, có duplicate derived state không.
- API contract có bám Day 08/09 không, có hard-code mock response không.
- Loading/error/empty/submitting state có đủ và visible không.
- Accessibility: semantic HTML, label, keyboard, focus, aria-live/aria-busy.
- Responsive layout có ổn không, có tạo landing page hoặc UI marketing ngoài scope không.
- Có file ngoài plan, dependency mới hoặc state library mới không.
- Test có meaningful assertion cho state và interaction không.

Kết luận theo format: Blocker, Should fix, Nice to have, Test gaps.
```

### Bước 8: Rollback an toàn nếu patch sai

Trước khi rollback, chạy trong root `taskflow-ai`:

```bash
git status --short
```

Lệnh này xác định file đang modified/untracked. Output kỳ vọng chỉ gồm file của task hiện tại. Rủi ro: nếu có file của worker khác, không rollback toàn repo.

Rollback một tracked file đã review, chạy ở root `taskflow-ai`:

```bash
git restore -- frontend/src/tasks/TaskListPage.tsx
```

Lệnh này đưa file tracked về trạng thái trong Git. Output thường rỗng nếu thành công. Rủi ro: mất toàn bộ thay đổi chưa commit trong file đó, kể cả phần bạn muốn giữ.

Xóa file mới tạo sai chỉ khi chắc chắn file đó do bạn/Claude tạo trong task này, chạy ở root `taskflow-ai`:

```bash
git clean -f -- frontend/src/tasks/TaskListPage.tsx
```

Lệnh này xóa untracked file cụ thể. Output kỳ vọng là tên file bị remove. Rủi ro cao hơn `git restore` vì xóa file chưa tracked; không dùng dạng rộng như `git clean -fd`.

Không chạy các lệnh này trong repo nhiều worker nếu chưa chủ động tách thay đổi:

```bash
git reset --hard
git clean -fd
npm install
docker compose down -v
rm -rf frontend/src
```

Các lệnh này có thể xóa thay đổi của người khác, đổi lockfile ngoài scope, xóa volume database hoặc phá source tree.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```text
Hãy đọc frontend taskflow-ai để hiểu convention trước khi tạo task list UI.

Yêu cầu:
- Chỉ đọc file, chưa sửa.
- Nêu rõ file đã đọc và bằng chứng.
- Tìm React entrypoint, routing/page, component pattern, styling pattern, API client/fetch wrapper, env config, test setup.
- Tìm API contract tasks từ Day 08/09 hoặc backend routes/schema hiện có.
- Không đề xuất landing page, không đổi state library, không thêm UI framework.
```

### Prompt lập UI contract

```text
Hãy viết UI contract cho task list React theo convention hiện có.

Output cần có:
- Component boundary và prop/callback chính.
- Endpoint tasks sẽ gọi, request/response/error shape lấy từ contract Day 08/09.
- UI states: loading, error, empty, list, submitting, validation error.
- Accessibility requirement: semantic HTML, label, keyboard, focus, aria-live/aria-busy.
- Responsive behavior.
- Test cases tối thiểu.

Chưa implement.
```

### Prompt lập plan file-by-file

```text
Tạo implementation plan cho task list UI theo UI contract đã duyệt.

Ràng buộc:
- Tối đa 7 bước.
- Mỗi bước ghi file sẽ sửa/tạo.
- Chỉ chạm frontend.
- Không thêm dependency.
- Không đổi routing lớn, state library, styling system, package manager hoặc API contract.
- Không sửa backend, migration, seed, README hoặc file Day khác.
- Chờ tôi approve trước khi sửa.
```

### Prompt implement

```text
Implement task list UI theo plan đã approve.

Giới hạn:
- Chỉ chạm file trong plan.
- Không tạo landing page.
- Bám component pattern và styling pattern hiện có.
- Bám API contract Day 08/09; nếu chưa rõ response shape, dừng và hỏi.
- State management tối giản; không thêm Redux/Zustand/TanStack Query/form library.
- Có loading/error/empty/list/submitting/validation state.
- Có accessibility: label, semantic button/form/list, keyboard, focus, aria-live/aria-busy nếu phù hợp.
- Không chạy npm install, git add/commit/reset/clean, docker hoặc command xóa file.
- Sau khi xong, tóm tắt diff và test command cần chạy.
```

### Prompt review component quality

```text
Review diff hiện tại như senior React reviewer, không sửa file.

Kiểm tra:
- Component có quá lớn hoặc trộn data fetching với presentational logic quá mức không.
- State có duplicate derived value không.
- API error/loading/empty/submitting state có visible và testable không.
- Form có controlled input, validation, disabled state và focus behavior hợp lý không.
- Accessibility có lỗi blocker không: thiếu label, div clickable, button không name, focus trap, aria sai.
- Responsive có bị vỡ text, overflow, hoặc tạo layout marketing ngoài scope không.
- Có dependency, state library, config hoặc file ngoài plan không.
- Test gaps còn lại.

Kết luận theo format: Blocker, Should fix, Nice to have, Test gaps.
```

### Prompt viết test

```text
Hãy đề xuất test cho task list UI trước khi sửa tiếp.

Ràng buộc:
- Đọc pattern test hiện có.
- Chỉ đề xuất test cases và file cần sửa.
- Ưu tiên behavior user thấy được: loading, error retry, empty state, render list, create task validation/submitting.
- Dùng accessible query nếu project dùng Testing Library.
- Không snapshot rộng.
- Chưa edit file.
```

## 6. Trade-offs

Local state nhanh và dễ review cho một page task list. Nhược điểm là khi nhiều page cùng dùng tasks, bạn phải tự quản cache, invalidation và stale data. Với Day 10, local state là lựa chọn mặc định vì scope nhỏ và dễ kiểm soát.

Custom hook như `useTasks` giúp tách data fetching khỏi JSX. Nhược điểm là nếu hook quá sớm, bạn có thêm abstraction mà chưa có reuse. Tạo hook khi component bắt đầu phình hoặc test state transition riêng có lợi.

Native `fetch` đủ cho bài này nếu project chưa có client. Nhược điểm là bạn phải tự map error, abort request và handle base URL. Nếu project đã có fetch wrapper, dùng wrapper đó để giữ error/auth convention.

Optimistic update tạo cảm giác nhanh khi create/complete task, nhưng tăng complexity rollback nếu API fail. Với bài đầu, refetch hoặc append sau khi API success thường an toàn hơn. Optimistic update chỉ nên thêm khi contract và test đã chắc.

Không thêm state library giữ patch nhỏ, nhưng có thể thiếu cache/server-state feature. Nếu team đã dùng TanStack Query hoặc Redux Toolkit, bám convention hiện có; nếu chưa dùng, đừng biến Day 10 thành migration state management.

Accessibility upfront mất thêm thời gian nhưng rẻ hơn sửa sau. Nếu bỏ qua label, focus và keyboard, UI có thể "trông ổn" nhưng fail review production.

## 7. Best practices

- Luôn bắt đầu bằng `plan` mode và yêu cầu Claude đọc component/design/API pattern trước khi sửa.
- Ghi rõ "không tạo landing page" trong prompt implement. Taskflow là app vận hành, không phải homepage marketing.
- Chỉ dùng component library, icon library, CSS pattern và state library đã có trong repo.
- Chốt UI contract trước khi code: data shape, component boundary, UI states, accessibility, responsive behavior và test cases.
- Không để Claude tự đổi API contract. Nếu backend trả `{ data: tasks }`, frontend phải adapt đúng; nếu không rõ, dừng và hỏi.
- Không lưu derived state nếu có thể tính từ state gốc.
- Với list, dùng `task.id` làm key; không dùng index hoặc random key.
- Form phải là controlled input, có validation client-side nhẹ, nhưng backend vẫn là nguồn truth cuối cùng.
- Mọi request fail phải có UI visible: message, retry hoặc action cụ thể.
- Không log token, cookie, authorization header, secret hoặc payload nhạy cảm ở browser console.
- Với Vite, chỉ biến `VITE_*` được expose ra client; không đặt secret vào biến có prefix này.
- Review diff theo file list trong plan. Nếu Claude sửa `package.json`, lockfile, router global hoặc theme ngoài plan, dừng lại.
- Test theo behavior, không snapshot toàn page. Ưu tiên query theo role/name để ép accessibility tốt hơn.
- Rollback theo file, không dùng `git reset --hard` trong repo có nhiều worker.

## 8. Performance / cost / context

Frontend task có thể làm phình context vì Claude muốn đọc toàn bộ `src`, style, router, test, backend contract và docs. Cách tối ưu là yêu cầu đọc đúng entrypoint, component pattern, API client, package scripts và route/schema tasks. Không cần đọc toàn bộ app.

Cách giảm token và chi phí:

- Yêu cầu Claude output file list đã đọc và bằng chứng ngắn.
- Chia task thành slice: render `GET /tasks` trước, sau đó create task, sau đó update/delete nếu còn thời gian.
- Không paste toàn bộ design spec dài; tóm tắt component token, spacing, existing components và acceptance criteria.
- Khi test fail, chỉ đưa failure liên quan, không paste toàn bộ log dev server.
- Sau một session dài, dùng `/compact` với focus: API contract, file list, UI states, decisions đã approve và test command.

Performance runtime của UI:

- Không generate key mới mỗi render; dùng id ổn định.
- Không filter/sort list lớn trong render nếu đã có bằng chứng list lớn; derive đơn giản thì không cần `useMemo` sớm.
- Tránh refetch toàn bộ danh sách sau mỗi keystroke.
- Dùng `AbortController` hoặc cleanup pattern nếu project đã có để tránh set state sau unmount.
- Đừng log mỗi render hoặc mỗi item trong production bundle.
- Giữ bundle nhỏ: không thêm UI/state/date library chỉ cho một task list.

Chi phí maintainability:

- Component lớn làm Claude dễ sửa lẫn logic và UI ở vòng sau.
- API client không tách riêng làm error handling lặp lại.
- Missing loading/error/empty state làm QA phải phát hiện bằng tay.
- Accessibility không test bằng role/name khiến regression khó bắt.

## 9. Checklist cuối bài

- [ ] Tôi đã kiểm tra `git status --short` trước khi cho Claude Code sửa.
- [ ] Tôi đã yêu cầu Claude đọc frontend entrypoint, routing/page, component pattern, styling pattern, API client, env config và test setup.
- [ ] Tôi đã yêu cầu Claude đọc API contract tasks từ Day 08/09 hoặc backend route/schema hiện có.
- [ ] Tôi có UI contract trước khi implement.
- [ ] Component boundary rõ, không dồn mọi thứ vào một component lớn.
- [ ] Không thêm state library, UI framework hoặc dependency mới nếu chưa approve.
- [ ] Không tạo landing page, không đổi design system hoặc route lớn.
- [ ] Task list có loading, error, empty, list/success, submitting và validation state.
- [ ] Form có label, keyboard submit, disabled state và focus behavior hợp lý.
- [ ] List dùng key ổn định từ `task.id`.
- [ ] API base URL dùng env/config hiện có; không đưa secret vào client.
- [ ] Tôi đã chạy lint/test/build phù hợp hoặc ghi rõ test gap.
- [ ] Tôi đã review `git diff --stat` và `git diff`.
- [ ] Tôi biết rollback theo file và tránh command phá working tree của người khác.

## 10. Bài tập

Bài cơ bản: mở `taskflow-ai` ở `claude --permission-mode plan`, yêu cầu Claude khảo sát frontend React và API contract tasks. Không cho sửa file. Kết quả cần có: file đã đọc, component pattern, styling pattern, API client, scripts, data contract và UI states.

Bài nâng cao: sau khi duyệt UI contract, cho Claude implement slice đầu tiên: fetch `GET /tasks` và render task list với loading/error/empty/list state. Giới hạn file theo plan, không thêm dependency, không sửa backend. Review diff và ghi lại ít nhất 3 điểm bạn yêu cầu sửa.

Bài áp dụng project cá nhân: chọn một list UI đang có API thật. Viết prompt theo format Context, Goal, UI Contract, Constraints, Acceptance Criteria, Verification. So sánh output khi prompt có component boundary và khi prompt chỉ nói "build a nice list UI". Ghi lại khác biệt về số file sửa, state duplication, accessibility và testability.
