Bạn là main coordinator.

Nhiệm vụ:
1. Đọc plan khóa học trước: ./message-broker-learning-plan-updated
2. Fix các vấn đề còn lại Not Fully Fixed trong ./fix-summary.md

Quy trình bắt buộc:
PHASE 1 — FIX
- Dựa trên ./fix-summary.md, fix các vấn đề còn lại Not Fully Fixed. Spawn subagents song song nếu cần thiết.
- Mỗi subagent chỉ làm một phần việc, không chồng chéo
- Không agent nào được sửa ./review.md.
- Không agent nào được sửa file config, README, package, hoặc file chung nếu chưa được main agent cho phép.
- Mỗi fix agent phải trả về:
  1. Danh sách file đã sửa
  2. Issue đã fix
  3. Issue chưa fix và lý do
  4. Rủi ro còn lại

PHASE 2 — FINAL CHECK
- Main agent kiểm tra lại toàn bộ Not Fully Fixed trong ./fix-summary.md đã được fix đủ hay chưa. Nếu chưa hãy tiếp tục
- Nếu có lỗi do conflict hoặc sửa chồng chéo, main agent tự resolve.