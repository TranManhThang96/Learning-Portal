Bạn là main coordinator.

Nhiệm vụ: review 25 bài học trong ./message-broker và tạo ./review.md.

Quy trình bắt buộc:
0. Đọc plan khóa học trước: ./message-broker-learning-plan-updated
1. Main agent đọc danh sách file và chia thành 5 batch, mỗi batch 5 bài.
2. Spawn 5 subagents song song, mỗi subagent xử lý 1 batch.
3. Subagents chỉ được đọc file và trả kết quả review về main thread. Không subagent nào được ghi/sửa file.
4. Main agent chờ đủ 5 kết quả.
5. Main agent tự tổng hợp toàn bộ và chỉ main agent được tạo file ./review.md.

Tiêu chí review:
- Độ chính xác kỹ thuật (sử dụng context7 mcp nếu cần)
- Tính logic giữa các bài
- Độ dễ hiểu với người học
- đánh giá xem đã tách rõ ràng document.md và exercise.md nếu cần chưa
- Thiếu ví dụ/thực hành
- Bài quá dài/quá ngắn
- Nội dung trùng lặp
- Thuật ngữ chưa giải thích
- Chỗ cần thêm diagram, checklist, quiz hoặc exercise
- Mức độ phù hợp với mục tiêu course

Output trong ./review.md:
# Course Review

## Executive Summary
## Score Table
| Lesson | Title | Score | Main Issues | Priority |
## Cross-Lesson Issues
## Detailed Review
### Lesson 01 ...
## Recommended Fix Plan
## Final Checklist