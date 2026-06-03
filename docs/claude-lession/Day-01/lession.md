# Day 01 — Mindset: Claude Code không phải chatbot

## 1. Mục tiêu bài học

Sau khoảng 2 tiếng, học viên cần làm được các việc sau:

- Hiểu Claude Code là một `agentic terminal tool` làm việc trong repo, không phải chatbot để hỏi đáp rời rạc.
- Phân biệt AI chat, autocomplete và agentic coding.
- Áp dụng vòng lặp `observe -> plan -> act -> verify` cho một task nhỏ trong project xuyên suốt `taskflow-ai`.
- Viết prompt có context, constraints và acceptance criteria thay vì prompt mơ hồ.
- Nhìn đúng vai trò của developer: owner, reviewer, architect.
- Biết khi nào chỉ cho Claude Code đọc/lập plan, khi nào mới cho phép sửa file hoặc chạy command.

Kết quả cuối ngày: bạn có một workflow có kiểm soát để bắt đầu dùng Claude Code. Mục tiêu không phải tạo thật nhiều file, mà là biết giao việc, kiểm chứng và giữ quyền quyết định kỹ thuật.

## 2. Bối cảnh thực tế

Nhiều developer mới dùng AI coding assistant theo kiểu chatbot:

- "Viết giúp tôi app quản lý task."
- "Fix bug này."
- "Tối ưu code này."

Các prompt này tạo cảm giác nhanh, nhưng trong repo thật chúng thường dẫn đến scope phình to, code khó review, thiếu test, hoặc agent tự ý sửa file không liên quan. Vấn đề không chỉ là AI đúng hay sai; vấn đề là developer chưa thiết kế workflow đủ rõ.

Claude Code khác chatbot ở chỗ nó chạy trong terminal và làm việc trực tiếp với codebase. Khi được cấp quyền, nó có thể đọc file, tìm conventions, sửa code, chạy command và hỗ trợ Git workflow. Vì vậy, bạn không nên dùng nó như nơi hỏi đáp. Bạn cần dùng nó như một agent có khả năng hành động, còn bạn là người sở hữu kết quả.

Nên dùng Claude Code khi:

- Cần đọc nhanh một repo mới.
- Cần lập plan cho feature, bug fix, refactor nhỏ.
- Cần tạo thay đổi có scope rõ và có cách verify.
- Cần viết test, review diff, giải thích architecture.
- Cần tự động hóa thao tác lặp lại trong sandbox.

Không nên dùng Claude Code khi:

- Repo có secret, production credential hoặc dữ liệu khách hàng chưa được xử lý an toàn.
- Task liên quan auth, payment, migration phá dữ liệu, security boundary mà chưa có reviewer.
- Bạn chưa biết acceptance criteria nhưng vẫn muốn agent implement ngay.
- Bạn không có thời gian đọc diff, chạy test hoặc rollback.

Trong Day 01, project `taskflow-ai` chỉ đóng vai trò sandbox để luyện mindset. Việc setup full backend/frontend sẽ để sang Day 02.

## 3. Kiến thức nền

### Claude Code là gì

Claude Code là công cụ agentic chạy trong terminal. Bạn mở nó trong thư mục project bằng lệnh `claude`, sau đó giao việc bằng ngôn ngữ tự nhiên. Điểm khác biệt quan trọng là Claude Code có thể quan sát repo và thực hiện hành động nếu bạn cho phép.

So sánh ngắn:

- AI chat: trả lời dựa trên nội dung bạn nhập hoặc paste vào.
- Autocomplete: gợi ý đoạn code tiếp theo trong editor.
- Claude Code: đọc codebase, lập plan, sửa file, chạy command, verify bằng diff/test.

### Agentic coding là gì

Agentic coding là cách dùng AI theo vòng lặp:

```txt
observe -> plan -> act -> verify
```

- `observe`: đọc file, xem cấu trúc repo, xem README, xem command, xem lỗi.
- `plan`: đề xuất hướng làm, file sẽ chạm vào, rủi ro, cách verify.
- `act`: sửa file hoặc chạy command trong phạm vi đã được duyệt.
- `verify`: chạy test/lint/build, xem diff, đối chiếu acceptance criteria.

Nếu bỏ qua `observe`, agent dễ đoán sai architecture. Nếu bỏ qua `plan`, developer khó kiểm soát scope. Nếu bỏ qua `verify`, output chỉ là "có vẻ đúng".

### Vai trò của developer

Developer không biến mất khỏi workflow. Vai trò của bạn rõ hơn:

- `Owner`: chịu trách nhiệm cuối cùng về thay đổi được merge.
- `Reviewer`: đọc diff, kiểm tra edge cases, phát hiện hallucination hoặc test yếu.
- `Architect`: giữ module boundary, convention, security rule và maintainability.

Một cách nghĩ thực tế: Claude Code có thể là người thực hiện nhiều thao tác, nhưng không phải người ký duyệt architecture.

### Vibe Coding và Vibe Engineering

`Vibe Coding` là đưa yêu cầu mơ hồ rồi accept output vì "nhìn có vẻ ổn". Cách này có thể dùng cho prototype rất nhỏ, nhưng nguy hiểm trong codebase thật.

`Vibe Engineering` là dùng AI để tăng tốc nhưng vẫn giữ kỷ luật engineering:

- Task có context và mục tiêu rõ.
- Scope có giới hạn.
- Có constraints và non-goals.
- Có acceptance criteria có thể kiểm chứng.
- Có diff, test, rollback.

Trong khóa học này, ta chọn Vibe Engineering.

### Prompt mơ hồ và prompt có acceptance criteria

Prompt mơ hồ:

```txt
Tạo giúp tôi app quản lý task cho team.
```

Vấn đề:

- Không nói stack.
- Không nói hôm nay chỉ cần scope nào.
- Không nói file nào được sửa.
- Không nói output kỳ vọng.
- Không nói cách verify.
- Không chặn agent tự ý tạo architecture lớn.

Prompt tốt hơn:

```txt
Context:
Tôi đang ở Day 01 của khóa học Claude Code. Project xuyên suốt là taskflow-ai, nhưng hôm nay chỉ học mindset và agentic loop.

Goal:
Hãy đọc trạng thái repo hiện tại và đề xuất plan ngắn cho việc khởi tạo taskflow-ai ở Day 02.

Constraints:
- Không sửa file.
- Không chạy command ghi file.
- Stack mặc định: Node.js + TypeScript + Fastify, React + Vite, PostgreSQL, Redis.
- Nếu thiếu thông tin, hỏi lại trước.

Acceptance criteria:
- Trả lời gồm current state, proposed modules, commands dự kiến, risks.
- Nêu rõ file nào đã đọc.
- Không bịa file chưa tồn tại.
```

Prompt này buộc Claude Code observe trước, giới hạn quyền act, và tạo output để developer review.

## 4. Step-by-step thực hành

Thời lượng gợi ý:

- 15 phút: chuẩn bị sandbox và mở Claude Code.
- 25 phút: yêu cầu Claude Code observe repo.
- 25 phút: so sánh prompt mơ hồ và prompt có acceptance criteria.
- 35 phút: thực hành agentic loop với một thay đổi tài liệu nhỏ.
- 20 phút: review diff, thử rollback, ghi reflection.

### Bước 1 — Chuẩn bị thư mục học tập

Chạy trong terminal tại thư mục bạn muốn đặt project học tập, ví dụ `D:\my-source\learning` trên Windows hoặc `~/learning` trên macOS/Linux.

```bash
mkdir taskflow-ai
cd taskflow-ai
git init
```

Lệnh làm gì:

- `mkdir taskflow-ai`: tạo thư mục sandbox cho project xuyên suốt.
- `cd taskflow-ai`: chuyển terminal vào đúng thư mục project.
- `git init`: khởi tạo Git để có thể xem diff và rollback.

Kết quả kỳ vọng:

- Thư mục `taskflow-ai` tồn tại.
- `git init` báo đã khởi tạo repository mới.
- Terminal đang đứng trong `taskflow-ai`.

Rủi ro:

- Nếu thư mục đã tồn tại, `mkdir` có thể báo lỗi. Khi đó chỉ cần `cd taskflow-ai`.
- Không chạy trong repo công ty nếu bạn chỉ đang học.
- Không xóa thư mục cũ chỉ để làm lại nếu chưa kiểm tra bên trong có gì.

Nếu muốn có context tối thiểu, tạo thủ công file `PRODUCT_BRIEF.md`:

```md
# taskflow-ai

taskflow-ai là ứng dụng quản lý task mini cho team kỹ thuật.

Stack dự kiến:
- Backend: Node.js + TypeScript + Fastify
- Frontend: React + Vite
- Database: PostgreSQL
- Cache: Redis
- Test: Vitest, Playwright
```

Đây chỉ là file học tập. Day 02 mới bắt đầu setup project có cấu trúc.

### Bước 2 — Mở Claude Code trong project

Chạy tại root của `taskflow-ai`:

```bash
claude
```

Lệnh làm gì:

- Mở Claude Code interactive session trong project hiện tại.
- Claude Code sẽ dùng thư mục đang đứng làm context làm việc.

Kết quả kỳ vọng:

- Giao diện Claude Code xuất hiện trong terminal.
- Bạn có thể nhập prompt hoặc slash command.

Rủi ro:

- Nếu chạy `claude` ngoài thư mục project, agent có thể observe nhầm context.
- Nếu CLI chưa cài hoặc chưa đăng nhập, lệnh sẽ báo lỗi. Ghi lại lỗi và xử lý kỹ hơn ở Day 02.

Trong Claude Code, thử:

```txt
/help
```

`/help` giúp xem slash command có sẵn. Day 01 chưa cần khởi tạo convention hay memory cho project; mục tiêu là mở đúng thư mục, quan sát repo và giữ quyền quyết định trước khi agent sửa file.

Nếu đóng terminal và muốn quay lại:

```bash
claude --continue
```

Lệnh làm gì:

- Tiếp tục session gần nhất trong thư mục hiện tại.
- Phù hợp khi bạn đang làm tiếp đúng project `taskflow-ai`.

Nếu muốn chọn session cụ thể:

```bash
claude --resume
```

Hoặc dùng trong Claude Code:

```txt
/resume
```

Rủi ro:

- Chỉ resume khi terminal đang ở đúng root `taskflow-ai`; nếu đứng sai thư mục, context có thể lệch.
- Nếu session cũ chứa task không liên quan, hãy cân nhắc bắt đầu session mới hoặc dùng `/clear`.

### Bước 3 — Yêu cầu observe, chưa cho sửa file

Nhập prompt:

```txt
Hãy observe repo hiện tại trước.

Yêu cầu:
- Chỉ đọc file và chạy lệnh read-only nếu cần.
- Không sửa file.
- Không tạo file mới.
- Liệt kê file đã đọc.
- Kết luận repo hiện đang ở trạng thái nào.
- Đề xuất 3 bước tiếp theo cho project taskflow-ai, nhưng chưa thực hiện.
```

Kết quả kỳ vọng:

- Claude Code nói rõ repo rỗng hay có file nào.
- Nếu có `PRODUCT_BRIEF.md`, nó tóm tắt đúng nội dung.
- Nó đề xuất bước tiếp theo nhưng chưa sửa file.

Rủi ro:

- Nếu prompt không ghi "không sửa file", agent có thể tự tạo file.
- Nếu agent nói về file không tồn tại, đó là dấu hiệu hallucination. Hãy yêu cầu bằng chứng: path file, nội dung liên quan, lệnh đã dùng.

### Bước 4 — So sánh prompt mơ hồ và prompt có acceptance criteria

Lần 1, thử prompt mơ hồ:

```txt
Tạo giúp tôi project taskflow-ai.
```

Không accept bất kỳ thay đổi nào nếu Claude muốn sửa file. Chỉ đọc plan/output.

Đánh giá:

- Claude có hỏi lại stack không?
- Claude có nói file sẽ sửa không?
- Claude có nêu cách verify không?
- Scope có quá lớn cho Day 01 không?

Lần 2, thử prompt có acceptance criteria:

```txt
Context:
Tôi đang ở Day 01 của khóa học Claude Code. Project xuyên suốt là taskflow-ai, nhưng hôm nay chỉ học mindset và agentic loop.

Goal:
Hãy tạo một plan ngắn cho việc khởi tạo taskflow-ai ở Day 02, chưa sửa file.

Constraints:
- Không edit file.
- Không chạy command ghi file.
- Stack mặc định: Node.js + TypeScript + Fastify, React + Vite, PostgreSQL, Redis.
- Plan phải chia thành các bước nhỏ có thể review.

Acceptance criteria:
- Có tối đa 7 bước.
- Mỗi bước có mục tiêu, file/folder dự kiến, command dự kiến, cách verify.
- Nêu rủi ro permission/security nếu để agent tự chạy toàn bộ.
```

So sánh:

- Prompt thứ hai có output dễ review hơn không?
- Claude có tôn trọng non-goal "chưa sửa file" không?
- Bạn có thể đưa plan này vào Day 02 không?

### Bước 5 — Thực hành agentic loop với thay đổi nhỏ

Nếu muốn cho Claude Code thực hiện một `act` nhỏ trong Day 01, chỉ dùng với file tài liệu sandbox, ví dụ `LEARNING_NOTES.md`.

Prompt:

```txt
Observe:
Đọc PRODUCT_BRIEF.md nếu có và tóm tắt trạng thái repo.

Plan:
Đề xuất nội dung file LEARNING_NOTES.md để ghi lại mindset Day 01.

Act:
Sau khi tôi đồng ý, tạo hoặc cập nhật LEARNING_NOTES.md. Không sửa file khác.

Verify:
Sau khi sửa, chạy git diff -- LEARNING_NOTES.md và đối chiếu với acceptance criteria.

Acceptance criteria:
- File có 4 mục: mindset, agentic loop, prompt lessons, risks.
- Không quá 80 dòng.
- Không chứa secret hoặc thông tin công ty.
- Nội dung bằng tiếng Việt.
```

Chỉ approve khi plan đúng. Sau khi Claude sửa file, chạy:

```bash
git diff -- LEARNING_NOTES.md
```

Lệnh làm gì:

- Hiển thị thay đổi của riêng file `LEARNING_NOTES.md`.
- Giúp bạn review đúng phạm vi trước khi commit.

Kết quả kỳ vọng:

- Diff chỉ có `LEARNING_NOTES.md`.
- Nội dung khớp 4 mục trong acceptance criteria.

Rủi ro:

- Nếu diff có file khác, dừng lại và yêu cầu Claude giải thích vì sao chạm file ngoài scope.
- Không commit nếu bạn chưa đọc diff.

### Bước 6 — Rollback khi Claude Code làm sai

Nếu thay đổi chưa commit và bạn muốn hủy riêng file đã được Git track:

```bash
git restore -- LEARNING_NOTES.md
```

Lệnh làm gì:

- Đưa file `LEARNING_NOTES.md` về trạng thái gần nhất trong Git.

Kết quả kỳ vọng:

- Thường không có output nếu thành công.
- `git diff -- LEARNING_NOTES.md` không còn hiển thị thay đổi.

Rủi ro:

- Lệnh này xóa thay đổi chưa commit của file đó. Chỉ chạy khi chắc chắn không cần giữ nội dung.
- Không chạy `git restore .` trong repo có nhiều thay đổi nếu chưa kiểm tra diff.

Kiểm tra trạng thái:

```bash
git status --short
```

Lệnh làm gì:

- Liệt kê file đang thay đổi ở dạng ngắn gọn.

Kết quả kỳ vọng:

- Nếu đã rollback hết, output trống.
- Nếu giữ file mới, có thể thấy `?? LEARNING_NOTES.md`.

Rủi ro:

- Kết quả trống không có nghĩa logic đúng; nó chỉ nói Git không còn thấy thay đổi.

## 5. Prompt mẫu nên dùng

### Prompt khám phá codebase

```txt
Hãy khám phá repo hiện tại như một senior engineer mới join team.

Constraints:
- Chỉ đọc file và chạy lệnh read-only.
- Không sửa file.
- Không suy đoán nếu chưa có bằng chứng trong repo.

Kết quả:
- Entry points nếu có.
- Cấu trúc folder chính.
- Build/test commands nếu tìm thấy.
- Rủi ro hoặc điểm thiếu context.
- Danh sách file đã đọc.
```

### Prompt lập plan

```txt
Từ context repo hiện tại, hãy lập plan cho bước khởi tạo taskflow-ai ở Day 02.

Constraints:
- Chưa implement.
- Mỗi bước phải nhỏ, review được.
- Ghi rõ file/folder dự kiến sẽ tạo.
- Ghi rõ command dự kiến sẽ chạy và rủi ro của từng command.

Acceptance criteria:
- Plan tối đa 7 bước.
- Có phần verify cho từng bước.
- Có non-goals để tránh scope creep.
```

### Prompt implement

```txt
Hãy thực hiện đúng plan đã được duyệt.

Scope:
- Chỉ tạo/cập nhật LEARNING_NOTES.md.
- Không sửa file khác.

Rules:
- Trước khi edit, nhắc lại nội dung sẽ thay đổi.
- Sau khi edit, chạy git diff -- LEARNING_NOTES.md.
- Nếu cần sửa ngoài scope, dừng lại và hỏi.

Acceptance criteria:
- File có các mục mindset, agentic loop, prompt lessons, risks.
- Nội dung ngắn, bằng tiếng Việt.
```

### Prompt review

```txt
Review diff hiện tại như code reviewer.

Yêu cầu:
- Chỉ nhận xét dựa trên diff.
- Ưu tiên bug, rủi ro, thiếu test, lệch scope.
- Nếu không có issue nghiêm trọng, nói rõ.
- Trích path file cụ thể.

Không sửa file trong lượt này.
```

### Prompt viết test hoặc verification

```txt
Đề xuất cách verify thay đổi hiện tại.

Context:
Day 01 chỉ có tài liệu học tập, chưa có app runtime.

Kết quả cần có:
- Lệnh Git để xem diff.
- Checklist đọc nội dung.
- Tiêu chí pass/fail.
- Rủi ro còn lại nếu chưa có test tự động.
```

## 6. Trade-offs

Lợi ích khi dùng Claude Code như agent:

- Đọc repo nhanh hơn, nhất là khi mới join codebase.
- Giảm thời gian viết boilerplate, test skeleton, tài liệu.
- Giúp lập plan và review diff có cấu trúc.
- Giữ workflow gần terminal, Git và command thật.

Rủi ro:

- Agent có thể sửa file ngoài ý muốn nếu scope mơ hồ.
- Agent có thể chạy command tốn thời gian hoặc có side effect.
- Kết quả có vẻ hợp lý nhưng sai architecture.
- Context dài làm Claude bám vào thông tin cũ, không còn liên quan.
- Developer dễ bị automation bias: thấy AI tự tin thì tin theo.

Khi nên chọn cách khác:

- Task là quyết định sản phẩm chưa rõ: nói chuyện với stakeholder trước.
- Task là production incident: ưu tiên runbook, log, rollback, human review.
- Task liên quan security/payment/auth: dùng Claude Code để phân tích hoặc review, không auto-approve implement.
- Repo có secret hoặc data nhạy cảm: làm sạch môi trường trước khi mở agent.

Quy tắc thực dụng: cho Claude Code làm nhanh, nhưng bắt nó để lại bằng chứng. Bằng chứng gồm file đã đọc, plan, diff, test output và mapping với acceptance criteria.

## 7. Best practices

- Bắt đầu bằng observe. Dùng prompt "chỉ đọc, không sửa file" khi chưa hiểu repo.
- Yêu cầu plan trước khi act. Plan phải nói rõ file nào sẽ chạm vào và lệnh nào sẽ chạy.
- Dùng acceptance criteria cụ thể. Nếu không verify được, agent cũng không biết thế nào là xong.
- Chia task nhỏ. Một prompt không nên yêu cầu tạo full backend, frontend, database, auth và deploy.
- Review diff như review code của đồng nghiệp. Không accept vì "AI viết".
- Không đưa secret, token, production credential hoặc customer data vào prompt/repo sandbox.
- Với Day 01, ưu tiên để Claude hỏi trước khi edit file hoặc chạy tool có side effect.
- Khi đang ở sandbox `taskflow-ai`, scope nhỏ và đã có Git, có thể mở bằng `claude --permission-mode acceptEdits`; mode này cho phép tạo/sửa file và tự approve một số filesystem command thông dụng trong working directory, nên vẫn phải review diff.
- Nếu team muốn đặt mặc định ở cấp project, dùng `.claude/settings.json` với `permissions.defaultMode` là `auto` có kiểm soát; không áp dụng cho repo có secret, production data hoặc scope chưa rõ.
- Ghi lại prompt tốt và prompt tệ. Đây là tài sản workflow của team.
- Khi context bị nhiễu, dùng `/clear` cho task không liên quan hoặc `/compact <instructions>` để tóm tắt có định hướng.
- Nếu Claude nói "có thể", "thường là", "có lẽ", hãy yêu cầu bằng chứng trong repo hoặc docs.

Guardrails cho team:

- Mỗi task AI phải có owner là developer.
- Mọi thay đổi cần diff review.
- Mọi command có side effect cần nêu mục đích và rủi ro.
- Không cho agent tự ý chạy lệnh destructive.
- Không để agent sửa nhiều module khi acceptance criteria chỉ yêu cầu một module.

## 8. Performance / cost / context

Claude Code có context window. Mọi thông tin đưa vào context đều có chi phí về token, thời gian và độ tập trung của model.

Các thói quen làm tốn context:

- Bảo agent đọc toàn bộ repo khi chỉ cần một module.
- Paste log dài nhưng không chỉ ra error chính.
- Trộn nhiều task không liên quan trong cùng session.
- Giữ lịch sử tranh luận cũ sau khi task đã kết thúc.

Cách tối ưu:

- Nói rõ file/folder cần đọc trước.
- Yêu cầu agent tóm tắt những gì đã observe thành bullet ngắn.
- Dùng `/clear` khi chuyển sang task không liên quan.
- Dùng `/compact <instructions>` khi session dài nhưng vẫn cần giữ quyết định quan trọng.
- Sau này ghi project rules vào `CLAUDE.md` hoặc `.claude/CLAUDE.md`; Day 01 chỉ cần hiểu đây là nơi lưu coding standards, testing requirements và common commands cho Claude Code.

Prompt tiết kiệm context:

```txt
Chỉ đọc PRODUCT_BRIEF.md và git status. Không scan toàn repo. Mục tiêu là xác định Day 01 cần ghi chú gì, không khởi tạo app.
```

Prompt tốn context:

```txt
Đọc hết repo và cho tôi biết nên làm gì tiếp theo.
```

Trong `taskflow-ai`, mỗi ngày nên bắt đầu bằng context nhỏ: mục tiêu ngày học, file được chạm vào, command verify. Cách này giúp chi phí thấp hơn và output dễ review hơn.

## 9. Checklist cuối bài

- [ ] Tôi hiểu Claude Code là agentic terminal tool, không phải chatbot.
- [ ] Tôi giải thích được `observe -> plan -> act -> verify`.
- [ ] Tôi biết bắt Claude Code liệt kê file đã đọc.
- [ ] Tôi đã thử một prompt mơ hồ và nhận ra rủi ro.
- [ ] Tôi đã viết một prompt có context, constraints, acceptance criteria.
- [ ] Tôi biết xem diff bằng `git diff`.
- [ ] Tôi biết rollback file cụ thể bằng `git restore -- <path>`.
- [ ] Tôi biết dùng `claude --continue` để tiếp tục session gần nhất và `claude --resume` hoặc `/resume` để chọn session.
- [ ] Tôi hiểu `acceptEdits`/`auto` chỉ nên dùng khi scope rõ, có Git diff và không có dữ liệu nhạy cảm.
- [ ] Tôi không để Claude Code chạm vào secret, production data hoặc file ngoài scope.
- [ ] Tôi biết khi nào dùng `/clear` và `/compact <instructions>` ở mức khái niệm.
- [ ] Tôi có ghi chú riêng về cách mình sẽ đóng vai owner/reviewer/architect.

## 10. Bài tập

Bài tập chi tiết nằm trong `exercise.md`. Tóm tắt:

- Bài 1: dùng Claude Code observe `taskflow-ai` và báo cáo repo state.
- Bài 2: so sánh prompt mơ hồ với prompt có acceptance criteria cho việc chuẩn bị Day 02.
- Bài 3: cho Claude Code tạo `LEARNING_NOTES.md` theo agentic loop và review diff.
- Bài 4: viết reflection ngắn về vai trò owner/reviewer/architect và rủi ro cá nhân khi dùng AI coding.

Điều quan trọng nhất của Day 01 không phải có nhiều file được tạo. Điều quan trọng là bạn bắt đầu hình thành kỷ luật: agent có thể act, nhưng developer phải own.
