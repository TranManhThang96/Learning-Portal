Bạn là main coordinator.

Nhiệm vụ:
1. Đọc plan khóa học trước: ./message-broker-learning-plan-updated
2. Fix các vấn đề đã review được trong ./review.md

Quy trình bắt buộc:
PHASE 1 — FIX
- Dựa trên ./review.md, spawn tiếp 5 subagents song song.
- Mỗi subagent chỉ được sửa đúng 5 bài trong batch của mình:
  - Fix Agent 1: lesson 01-05
  - Fix Agent 2: lesson 06-10
  - Fix Agent 3: lesson 11-15
  - Fix Agent 4: lesson 16-20
  - Fix Agent 5: lesson 21-25
- Không agent nào được sửa file ngoài batch.
- Không agent nào được sửa ./review.md.
- Không agent nào được sửa file config, README, package, hoặc file chung nếu chưa được main agent cho phép.
- Mỗi fix agent phải trả về:
  1. Danh sách file đã sửa
  2. Issue đã fix
  3. Issue chưa fix và lý do
  4. Rủi ro còn lại

PHASE 2 — FINAL CHECK
- Main agent kiểm tra lại toàn bộ 25 bài.
- Cập nhật hoặc tạo ./fix-summary.md.
- Chạy format/lint/test nếu repo có command phù hợp.
- Nếu có lỗi do conflict hoặc sửa chồng chéo, main agent tự resolve.