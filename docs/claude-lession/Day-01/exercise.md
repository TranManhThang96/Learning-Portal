# Exercise — Day 01

## Bài 1 — Cơ bản

Mục tiêu: dùng Claude Code để observe repo `taskflow-ai` mà không sửa file.

Thời gian: 20-25 phút.

### Yêu cầu

1. Mở terminal tại thư mục học tập.
2. Tạo hoặc vào sandbox `taskflow-ai`.
3. Mở Claude Code trong thư mục đó.
4. Yêu cầu Claude Code đọc repo và báo cáo trạng thái hiện tại.

### Lệnh

Chạy trong thư mục học tập, ví dụ `D:\my-source\learning` hoặc `~/learning`:

```bash
mkdir taskflow-ai
cd taskflow-ai
git init
claude
```

Lệnh làm gì:

- `mkdir taskflow-ai`: tạo sandbox cho project xuyên suốt.
- `cd taskflow-ai`: vào đúng context project.
- `git init`: bật Git để có diff/rollback.
- `claude`: mở Claude Code trong repo.

Kết quả kỳ vọng:

- Git repo mới được khởi tạo.
- Claude Code mở interactive session.

Nếu đóng terminal và muốn làm tiếp đúng session gần nhất trong `taskflow-ai`, chạy:

```bash
claude --continue
```

Nếu muốn chọn session cụ thể, chạy:

```bash
claude --resume
```

Hoặc dùng trong Claude Code:

```txt
/resume
```

Rủi ro:

- Nếu `taskflow-ai` đã tồn tại, không xóa thư mục. Hãy `cd taskflow-ai` và kiểm tra `git status --short`.
- Nếu `claude` báo lỗi chưa cài đặt hoặc chưa đăng nhập, ghi lại lỗi. Phần setup sẽ xử lý kỹ hơn ở Day 02.
- Chỉ resume khi terminal đang đứng đúng root `taskflow-ai`; nếu không chắc, kiểm tra thư mục trước.

### Prompt

Nhập trong Claude Code:

```txt
Hãy observe repo hiện tại.

Rules:
- Chỉ đọc file và chạy lệnh read-only nếu cần.
- Không sửa file.
- Không tạo file.
- Không chạy install/build/test.

Kết quả:
- Repo đang ở trạng thái nào?
- File nào đã đọc?
- Có dấu hiệu stack/framework nào chưa?
- 3 câu hỏi cần làm rõ trước khi khởi tạo taskflow-ai ở Day 02.
```

### Sản phẩm cần nộp

- Ghi lại output của Claude Code vào note cá nhân.
- Đánh dấu Claude có nói rõ file đã đọc hay không.
- Nếu Claude bịa file, ghi lại ví dụ đó.

## Bài 2 — Thực tế

Mục tiêu: so sánh prompt mơ hồ với prompt có acceptance criteria.

Thời gian: 30 phút.

### Yêu cầu

Trong cùng session Claude Code, chạy hai prompt sau. Không accept bất kỳ edit nào.

Prompt A:

```txt
Tạo giúp tôi project taskflow-ai.
```

Prompt B:

```txt
Context:
Tôi đang học Day 01 về mindset Claude Code. Project xuyên suốt là taskflow-ai, nhưng hôm nay chưa khởi tạo full stack.

Goal:
Lập plan cho Day 02 để khởi tạo project taskflow-ai.

Constraints:
- Không sửa file.
- Không chạy command ghi file.
- Stack mặc định: Node.js + TypeScript + Fastify, React + Vite, PostgreSQL, Redis.
- Nếu thiếu thông tin, hỏi lại trước.

Acceptance criteria:
- Plan tối đa 7 bước.
- Mỗi bước có: mục tiêu, file/folder dự kiến, command dự kiến, output kỳ vọng, rủi ro.
- Có phần non-goals cho những việc chưa làm ở Day 02.
```

### Bảng đánh giá

Điền bảng sau vào note cá nhân:

| Tiêu chí | Prompt A | Prompt B |
|---|---|---|
| Có hỏi lại khi thiếu context không? |  |  |
| Có giới hạn scope không? |  |  |
| Có nói file/command dự kiến không? |  |  |
| Có cách verify không? |  |  |
| Có rủi ro agent tự ý làm quá nhiều không? |  |  |

### Sản phẩm cần nộp

- Một đoạn nhận xét 5-7 dòng: prompt nào tốt hơn và vì sao.
- Một phiên bản Prompt B do bạn tự cải tiến thêm.

## Bài 3 — Nâng cao

Mục tiêu: thực hành đầy đủ `observe -> plan -> act -> verify` với một thay đổi nhỏ, có rollback nếu cần.

Thời gian: 40-45 phút.

### Yêu cầu

Cho Claude Code tạo file `LEARNING_NOTES.md` trong sandbox `taskflow-ai`.

Phạm vi được phép:

- Chỉ tạo hoặc sửa `LEARNING_NOTES.md`.
- Không sửa file khác.
- Không install package.
- Không tạo backend/frontend.

### Prompt

Nhập trong Claude Code:

```txt
Task:
Tạo file LEARNING_NOTES.md để ghi lại bài học Day 01.

Agentic loop bắt buộc:
1. Observe: đọc trạng thái repo và nói file nào đã đọc.
2. Plan: đề xuất outline file LEARNING_NOTES.md, chưa edit.
3. Act: chỉ sau khi tôi đồng ý, tạo file LEARNING_NOTES.md.
4. Verify: chạy git diff -- LEARNING_NOTES.md và đối chiếu với acceptance criteria.

Scope:
- Chỉ được sửa LEARNING_NOTES.md.
- Không tạo file khác.

Acceptance criteria:
- File có 4 heading: Mindset, Agentic loop, Prompt lessons, Risks.
- Nội dung bằng tiếng Việt.
- Không quá 80 dòng.
- Có ít nhất 1 ví dụ prompt mơ hồ và 1 prompt cải thiện.
- Không chứa secret, credential, thông tin công ty.
```

Sau khi Claude đưa plan, nếu đúng thì trả lời:

```txt
Plan đúng. Hãy thực hiện đúng scope và verify bằng git diff -- LEARNING_NOTES.md.
```

### Lệnh kiểm tra thủ công

Chạy trong root `taskflow-ai`:

```bash
git diff --stat
git diff -- LEARNING_NOTES.md
git status --short
```

Lệnh làm gì:

- `git diff --stat`: xem danh sách file thay đổi và quy mô thay đổi.
- `git diff -- LEARNING_NOTES.md`: đọc chi tiết thay đổi của file bài tập.
- `git status --short`: xem file mới/chưa commit.

Kết quả kỳ vọng:

- Chỉ có `LEARNING_NOTES.md` trong diff.
- Nội dung có đủ 4 heading.
- Không có file khác bị sửa.

Rủi ro:

- Nếu `git diff --stat` hiện file khác, dừng lại. Yêu cầu Claude giải thích và rollback file ngoài scope.
- Nếu bạn chạy `git restore` với file mới chưa track, Git có thể không xóa file đó. Với file mới chưa track, cần xóa thủ công sau khi chắc chắn không cần nữa.

### Rollback nếu agent làm sai

Nếu file đã được Git track:

```bash
git restore -- LEARNING_NOTES.md
```

Nếu file mới chưa được Git track và bạn chắc chắn muốn xóa:

```bash
rm LEARNING_NOTES.md
```

Trên Windows PowerShell có thể dùng:

```powershell
Remove-Item .\LEARNING_NOTES.md
```

Lệnh làm gì:

- `git restore -- LEARNING_NOTES.md`: hủy thay đổi của file đã track.
- `rm LEARNING_NOTES.md` hoặc `Remove-Item .\LEARNING_NOTES.md`: xóa file mới chưa track.

Kết quả kỳ vọng:

- Thường không có output khi thành công.
- `git status --short` không còn hiện `LEARNING_NOTES.md` nếu đã rollback/xóa.

Rủi ro:

- Đây là thao tác xóa/hủy thay đổi. Chỉ chạy sau khi đọc diff và chắc chắn không cần giữ nội dung.
- Không dùng lệnh xóa hàng loạt như `rm -rf` trong bài này.

## Bài 4 — Review & Reflection

Mục tiêu: đánh giá lại cách bạn điều khiển agent và vai trò của mình trong workflow.

Thời gian: 20 phút.

### Yêu cầu

Trả lời ngắn gọn các câu hỏi sau trong note cá nhân hoặc trong `LEARNING_NOTES.md` nếu bạn đã tạo file:

1. Trong bài hôm nay, lúc nào Claude Code đang observe, plan, act, verify?
2. Có lúc nào Claude muốn làm quá scope không? Bạn xử lý thế nào?
3. Nếu đưa Prompt A vào repo công ty, rủi ro lớn nhất là gì?
4. Bạn sẽ đóng vai owner như thế nào khi dùng Claude Code?
5. Bạn sẽ đóng vai reviewer như thế nào?
6. Bạn sẽ đóng vai architect như thế nào?

### Prompt review gợi ý

Nhập trong Claude Code:

```txt
Review workflow Day 01 của tôi dựa trên diff và ghi chú hiện tại.

Yêu cầu:
- Không sửa file.
- Chỉ ra chỗ tôi đã kiểm soát scope tốt.
- Chỉ ra rủi ro còn lại.
- Đề xuất 3 quy tắc cá nhân trước khi tôi dùng Claude Code cho Day 02.
```

## Tiêu chí hoàn thành

Bạn hoàn thành Day 01 khi:

- Đã mở Claude Code trong đúng thư mục `taskflow-ai`.
- Đã yêu cầu Claude observe repo mà không sửa file.
- Đã so sánh ít nhất 1 prompt mơ hồ và 1 prompt có acceptance criteria.
- Đã thực hành hoặc mô phỏng được loop `observe -> plan -> act -> verify`.
- Đã xem diff bằng Git sau khi có thay đổi.
- Đã biết cách rollback file cụ thể nếu agent làm sai.
- Đã viết reflection về vai trò owner/reviewer/architect.

Không bắt buộc phải commit trong Day 01. Nếu commit, commit message nên rõ:

```bash
git add LEARNING_NOTES.md
git commit -m "docs: add day 01 learning notes"
```

Lệnh làm gì:

- `git add LEARNING_NOTES.md`: đưa file vào staging area.
- `git commit -m "...":` tạo commit với message ngắn.

Kết quả kỳ vọng:

- Git báo tạo commit mới.

Rủi ro:

- Chỉ commit sau khi đã review diff. Không dùng `git add .` nếu repo có file ngoài scope.

## Gợi ý nếu bí

- Nếu Claude Code bắt đầu sửa file ngay: nhập "Stop. Do not continue. First show the plan and touched files."
- Nếu Claude nói về file không có thật: yêu cầu "Show evidence: exact path and quote a short relevant line."
- Nếu output quá dài: yêu cầu "Summarize in 10 bullets, keep only decisions and risks."
- Nếu plan quá lớn: yêu cầu "Split into Day 01 observe-only and Day 02 setup. Today do not implement."
- Nếu không biết verify: bắt đầu bằng `git status --short`, `git diff --stat`, `git diff -- <file>`.
- Nếu lỡ đóng session: vào lại root `taskflow-ai`, dùng `claude --continue` cho session gần nhất hoặc `claude --resume`/`/resume` để chọn session.
- Nếu context bị nhiễu: dùng `/clear` cho task mới không liên quan hoặc `/compact <instructions>` nếu cần giữ tóm tắt.

## Đáp án tham khảo hoặc kết quả kỳ vọng

### Kết quả kỳ vọng Bài 1

Claude Code nên báo cáo theo hướng:

```txt
Repo hiện tại đang rỗng hoặc chỉ có một vài file tài liệu.
Tôi đã đọc: PRODUCT_BRIEF.md nếu tồn tại.
Chưa thấy package.json, src/, test/, docker-compose.yml nên chưa thể kết luận app đã được setup.
Trước Day 02 cần quyết định package manager, backend framework, frontend folder layout.
```

Nếu Claude khẳng định đã có API/frontend trong khi repo không có file tương ứng, kết quả không đạt.

### Kết quả kỳ vọng Bài 2

Nhận xét hợp lý:

```txt
Prompt A tạo rủi ro scope creep vì không nói rõ hôm nay chỉ cần plan, không nói stack, không có acceptance criteria và không cấm edit file.
Prompt B tốt hơn vì giới hạn hành động, yêu cầu plan nhỏ, buộc nêu command/output/rủi ro và tạo cơ sở để review trước Day 02.
```

### Kết quả kỳ vọng Bài 3

`git diff --stat` chỉ nên hiện:

```txt
LEARNING_NOTES.md | <số dòng> +++++++++++++++++
```

`LEARNING_NOTES.md` nên có cấu trúc:

```md
# Learning Notes - Day 01

## Mindset
...

## Agentic loop
...

## Prompt lessons
...

## Risks
...
```

Nếu diff có file khác như `package.json`, `src/`, `README.md`, bài tập chưa đạt vì agent đã vượt scope.

### Kết quả kỳ vọng Bài 4

Reflection đạt yêu cầu nếu có các ý:

- Developer vẫn là owner của kết quả, không giao trách nhiệm cho AI.
- Reviewer phải đọc diff và kiểm tra acceptance criteria.
- Architect phải giữ scope, stack, module boundary và security rules.
- Prompt tốt cần có context, goal, constraints, acceptance criteria, verification.
- Permission mạnh như `acceptEdits` hoặc default `auto` trong `.claude/settings.json` chỉ hợp lý khi scope nhỏ, có Git diff và repo không chứa dữ liệu nhạy cảm.
