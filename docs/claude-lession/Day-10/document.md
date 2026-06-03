# Document — Day 10

## Tóm tắt kiến thức

Day 10 chuyển workflow plan-first từ backend sang frontend React. Mục tiêu không phải để Claude Code "vẽ UI đẹp", mà là để nó tạo UI vận hành đúng contract, đúng component pattern và dễ review.

Nguyên tắc chính:

- Đọc design/component pattern trước khi sửa: entrypoint, routing, shared component, styling, API client, env config và test setup.
- Không tạo landing page cho task list. Đây là màn hình app nội bộ của `taskflow-ai`, cần scan nhanh, thao tác nhanh, responsive và ổn định.
- Component boundary phải rõ: container/page giữ data fetching và UI state; list/item/form là presentational hoặc interaction nhỏ; API client xử lý request/response/error.
- State management tối giản: local state trước, custom hook khi có lợi, không thêm state library nếu project chưa dùng.
- UI phải có loading, error, empty, list/success, submitting và validation state.
- API contract lấy từ Day 08/09 hoặc backend route/schema hiện có. Frontend không được tự bịa endpoint, field hoặc error shape.
- Accessibility là acceptance criteria: semantic HTML, label, keyboard, focus, `aria-live`/`aria-busy` khi phù hợp.
- Review diff frontend không chỉ nhìn UI: kiểm tra scope, dependency, state duplication, component size, API error handling, testability và responsive behavior.

Contract task list tham khảo, phải điều chỉnh theo project thật:

| UI phần | Data/behavior | Điều kiện đạt |
| --- | --- | --- |
| Initial loading | Fetch `GET /tasks` | Có loading visible, không màn hình trắng |
| Empty state | API trả list rỗng | Có thông điệp và hành động tạo task |
| Error state | API fail hoặc response không hợp lệ | Có message, retry, không chỉ `console.error` |
| Task list | Render tasks từ API | Dùng key ổn định từ `task.id` |
| Create form | `POST /tasks` theo contract | Controlled input, validation title, submitting state |
| Success create | API trả task mới hoặc list mới | UI cập nhật, clear input, focus hợp lý |
| Accessibility | Keyboard và screen reader | Button/input/list có semantics đúng |

## Sơ đồ tư duy hoặc luồng xử lý

```text
Yêu cầu Day 10
  |
  v
Kiểm tra git status
  |
  +-- Có thay đổi lạ -> dừng, đọc diff, không chạm file người khác
  |
  v
Claude Code plan mode
  |
  v
Đọc frontend convention
  |
  +-- package scripts
  +-- React entrypoint/routing
  +-- shared components
  +-- styling pattern
  +-- API client/fetch wrapper
  +-- env config
  +-- test setup
  |
  v
Đọc API contract Day 08/09
  |
  +-- endpoint
  +-- response shape
  +-- error shape
  +-- fields/status
  |
  v
UI contract
  |
  +-- component boundary
  +-- UI states
  +-- accessibility
  +-- responsive behavior
  +-- test cases
  |
  v
Plan file-by-file
  |
  v
Developer approve
  |
  v
Implement slice nhỏ
  |
  v
lint/test/build/manual check
  |
  v
git diff --stat -> git diff
  |
  v
Review component quality
  |
  +-- Đạt -> commit/PR thủ công
  |
  +-- Sai -> patch nhỏ hoặc rollback theo file
```

Luồng prompt nên dùng:

```text
Explore/read-only
  -> UI contract
  -> Plan file-by-file
  -> Implement with boundaries
  -> Verify lint/test/build
  -> Component quality review
```

## Bảng so sánh

| Cách làm | Lợi ích | Rủi ro | Khi dùng |
| --- | --- | --- | --- |
| Prompt "make a nice UI" | Nhanh ở demo | Landing page, mock data, đổi design system, thiếu state lỗi | Chỉ dùng sandbox |
| UI contract trước | Dễ review, bám API, ít drift | Tốn thêm một lượt plan | Default cho repo team |
| Local state | Đơn giản, patch nhỏ | Tự quản cache/refetch | Một page task list |
| Global/server-state library | Cache/invalidation tốt | Dependency và convention mới | Chỉ khi project đã dùng hoặc có nhu cầu rõ |
| Fetch trong page | Ít abstraction | Component dễ phình | Slice nhỏ ban đầu |
| API client/custom hook | Tách responsibility, dễ test | Có thể over-engineer | Khi nhiều component dùng tasks hoặc state transition phức tạp |

| Chủ đề | Nên làm | Không nên làm |
| --- | --- | --- |
| Component | Container giữ data, child nhận props/callback | Một component 500 dòng làm mọi thứ |
| State | Lưu state gốc, derive giá trị đơn giản | Lưu `taskCount`, `hasTasks`, `filteredTasks` không cần thiết |
| List key | Dùng `task.id` từ API | Dùng index, `Math.random()` hoặc key đổi mỗi render |
| Loading/error | Hiển thị trên UI, có retry khi phù hợp | Chỉ log console hoặc màn hình trắng |
| Form | Controlled input, label, validation, disabled submitting | Input không label, submit được nhiều lần |
| Accessibility | Button thật, label, focus, `aria-live`/`aria-busy` khi phù hợp | `div onClick`, icon button không name |
| API | Bám Day 08/09 contract | Hard-code mock response hoặc tự đổi endpoint |
| Env | Dùng `VITE_*` cho public config | Đưa secret vào client bundle |
| Review | So file list với plan, review behavior | Chỉ nhìn screenshot đẹp |

| Command | Chạy ở đâu | Dùng để làm gì | Output kỳ vọng | Rủi ro |
| --- | --- | --- | --- | --- |
| `git status --short` | Root `taskflow-ai` | Kiểm tra working tree trước/sau khi sửa | Rỗng hoặc file đã hiểu | Bỏ sót thay đổi worker khác nếu không đọc |
| `find . -maxdepth 3 -name package.json` | Root `taskflow-ai` trên bash | Tìm frontend package | Path package frontend/backend | Không chạy được trên một số PowerShell |
| `Get-ChildItem -Recurse -Filter package.json -Depth 3` | Root `taskflow-ai` trên PowerShell | Tìm frontend package | Path package frontend/backend | Repo lớn có thể mất vài giây |
| `npm pkg get scripts` | Folder frontend có `package.json` | Xem script thật | JSON scripts | Không phù hợp nếu repo dùng package manager khác |
| `claude --permission-mode plan` | Root `taskflow-ai` | Mở session đọc/lập plan | Claude sẵn sàng nhận prompt | Plan sai nếu đọc thiếu file |
| `npm run lint` | Folder frontend | Kiểm tra lint | Exit code `0` | Có thể fail vì lỗi cũ ngoài scope |
| `npm run test -- --run` | Folder frontend | Chạy test một lần nếu runner hỗ trợ | Test pass, exit code `0` | Có thể vào watch mode nếu script khác |
| `npm run build` | Folder frontend | Build production | Build thành công, thường ra `dist/` | Có thể thiếu env hoặc type issue cũ |
| `npm run dev -- --host 127.0.0.1` | Folder frontend | Chạy app local để kiểm tra UI | URL localhost | Process dài hạn, cần dừng bằng `Ctrl+C` |
| `git diff --stat` | Root `taskflow-ai` | Xem phạm vi patch | File list khớp plan | Không thấy logic |
| `git diff` | Root `taskflow-ai` | Review patch chi tiết | Diff đúng contract | Diff dài dễ bỏ sót |
| `git restore -- path/to/file` | Root `taskflow-ai` | Rollback tracked file cụ thể | Thường không output | Mất thay đổi chưa commit trong file đó |

## Lỗi thường gặp

1. Claude tạo landing page thay vì app UI  
   Dấu hiệu: hero section, marketing copy, gradient background, card minh họa, CTA không liên quan task workflow. Cách sửa: prompt rõ "không tạo landing page", yêu cầu bám route/component hiện có và task list vận hành.

2. Tự thêm dependency hoặc state library  
   Dấu hiệu: `package.json`/lockfile bị sửa, thêm Redux/Zustand/TanStack Query/UI kit. Cách sửa: reject nếu chưa approve; yêu cầu implement bằng pattern hiện có.

3. Component phình quá lớn  
   Dấu hiệu: một file chứa fetch, transform, form, list item, modal, style và error mapping. Cách sửa: tách boundary theo trách nhiệm, nhưng không refactor rộng ngoài scope.

4. State bị duplicate  
   Dấu hiệu: lưu cả `tasks`, `taskCount`, `hasTasks`, `visibleTasks` dù không có filter phức tạp. Cách sửa: derive từ `tasks`, chỉ lưu state có lifecycle riêng.

5. Missing UI state  
   Dấu hiệu: API fail thì console error, loading là màn hình trắng, list rỗng không có message. Cách sửa: UI contract phải liệt kê loading/error/empty/submitting trước khi implement.

6. API contract drift  
   Dấu hiệu: frontend gọi `/api/todos` trong khi backend là `/tasks`, hoặc giả định response là array trong khi backend trả `{ data }`. Cách sửa: yêu cầu Claude đọc Day 08/09/backend route trước, không đoán.

7. Accessibility bị xem là polish  
   Dấu hiệu: input không label, icon button không accessible name, dùng `div onClick`, focus mất sau submit. Cách sửa: đưa accessibility vào acceptance criteria, test bằng role/name nếu có Testing Library.

8. Env secret leak  
   Dấu hiệu: đưa token/API secret vào `.env` với prefix `VITE_`. Cách sửa: chỉ dùng `VITE_API_BASE_URL` hoặc public config; secret phải ở backend.

9. Test chỉ snapshot toàn page  
   Dấu hiệu: test pass nhưng không kiểm tra loading/error/form behavior. Cách sửa: test theo behavior user thấy được.

10. Rollback toàn repo  
   Dấu hiệu: dùng `git reset --hard` hoặc `git clean -fd`. Cách sửa: rollback theo file đã review để không xóa thay đổi của worker khác.

## Cách debug

Khi UI không hiển thị task:

1. Kiểm tra API contract và endpoint thực tế. Chạy trong terminal backend hoặc root đúng theo project:

```bash
curl -i http://localhost:3000/tasks
```

Lệnh này gọi endpoint tasks, thay port/path theo contract Day 08/09. Output kỳ vọng là status `200` và body đúng shape, hoặc lỗi auth/dev rõ ràng. Rủi ro: endpoint/port có thể khác; không sửa frontend theo URL đoán mò.

2. Yêu cầu Claude phân tích trước, chưa sửa:

```text
UI không hiển thị tasks. Hãy phân tích nguyên nhân, chưa sửa file.
Kiểm tra khả năng: endpoint sai, response shape sai, CORS, env API base URL, loading state kẹt, render condition sai, key/list bug.
Nêu file cần đọc và bằng chứng.
```

Khi loading/error state hoạt động sai:

```text
Review state machine của TaskList UI hiện tại, chưa sửa file.
Liệt kê mọi transition: initial -> loading -> success/empty/error, submit -> success/error, retry -> loading.
Chỉ ra state nào bị duplicate, state nào không reset đúng, và patch nhỏ nhất.
```

Khi component quá lớn:

```text
Review component boundary của diff hiện tại, không sửa file.
Đề xuất tách trách nhiệm tối thiểu mà không refactor rộng:
- data fetching
- API client
- form
- list
- item
- error/empty state
```

Khi test fail, chạy trong folder frontend có `package.json`:

```bash
npm run test -- --run
```

Lệnh này chạy test một lần nếu runner hỗ trợ. Output kỳ vọng là danh sách pass/fail và exit code rõ. Rủi ro: runner có thể không hỗ trợ `--run`; đọc script thật trước.

Đưa failure ngắn cho Claude:

```text
Test fail như sau. Hãy phân tích nguyên nhân trước, chưa sửa file.
Phân loại: implementation bug, test sai expectation, thiếu mock API, thiếu jsdom setup, hay môi trường.
Đề xuất patch nhỏ nhất và file cần sửa.
```

Khi diff quá rộng, chạy ở root `taskflow-ai`:

```bash
git diff --stat
```

Lệnh này hiển thị file list và số dòng thay đổi. Output kỳ vọng khớp plan. Rủi ro: không thấy logic chi tiết; sau đó vẫn phải review `git diff`.

Prompt thu hẹp:

```text
Diff đang rộng hơn plan. Hãy dừng implement.
Liệt kê file ngoài plan, lý do bị chạm, và cách thu hẹp patch về task list UI.
Không sửa file.
```

Khi cần rollback một file tracked, chạy ở root `taskflow-ai`:

```bash
git restore -- frontend/src/tasks/TaskListPage.tsx
```

Lệnh này rollback file cụ thể. Output thường rỗng nếu thành công. Rủi ro: mất thay đổi chưa commit trong file đó; không dùng nếu file chứa thay đổi của người khác.

## Link tài liệu nên đọc

- Claude Code overview: https://docs.anthropic.com/en/docs/claude-code/overview
- Claude Code common workflows: https://docs.anthropic.com/en/docs/claude-code/tutorials
- Claude Code settings và permissions: https://docs.anthropic.com/en/docs/claude-code/settings
- Claude Code team permissions: https://docs.anthropic.com/en/docs/claude-code/team
- Claude Code slash commands: https://docs.anthropic.com/en/docs/claude-code/slash-commands
- React — Thinking in React: https://react.dev/learn/thinking-in-react
- React — Managing State: https://react.dev/learn/managing-state
- React — Conditional Rendering: https://react.dev/learn/conditional-rendering
- React — Rendering Lists: https://react.dev/learn/rendering-lists
- Vite — Env Variables and Modes: https://vite.dev/guide/env-and-mode/
- MDN Web Accessibility: https://developer.mozilla.org/en-US/docs/Web/Accessibility
- WAI-ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/
- Testing Library guiding principles: https://testing-library.com/docs/guiding-principles
- Playwright locators: https://playwright.dev/docs/locators
