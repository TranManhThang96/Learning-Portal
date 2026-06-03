Bạn là main coordinator, một ai expert engineer.

Nhiệm vụ: review 5 bài học về AI từ bài 46 đến bài 50

Tôi là người học nhìn qua vài bài học thì tôi đánh giá sau:
- Tất cả nội dung đều là tiếng Việt không dấu, hãy sửa lại thành tiếng Việt có dấu, chỉ giữ lại thuật ngữ chuyên ngành bằng tiếng Anh
- Nội dung bài học rất sơ sài. Tôi muốn nó thật đầy đủ, chi tiết, step by step để tôi ít phải search internet nhất có thể. 
- Mỗi bài học hãy tạo một folder, folder có tên bài học, folder bao gồm ít nhất file lession.md. Nếu có document hoặc exercise thì hãy tạo file riêng cho document.md và exercise.md


Tôi nhấn mạnh lại các yêu cầu của khóa học:
1. Giải thích dễ hiểu, đi từ cơ bản đến chi tiết.
2. Ưu tiên thực hành và ứng dụng thực tế.
3. Luôn nhấn mạnh trade-off, best solution theo context và performance.
4. Code example phải gần production, không chỉ toy example.
5. Mỗi bài phải trả lời câu hỏi: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"


Quy trình bắt buộc:
0. Đọc plan khóa học trước: ./lo_trinh_50_ngay_senior_se_to_ai_engineer.md
1. Main agent đọc danh sách file và chia thành 5 bài.
2. Spawn 5 subagents song song, mỗi subagent xử lý 1 bài.
3. Subagents review thật kỹ theo các yêu cầu trên và tự review thêm theo plan của bài học. Sau khi review xong thì tự sửa lỗi. Sau đó trả kết quả review về main agent. 
4. Main agent chờ đủ 5 kết quả.
5. Main agent tự tổng hợp toàn bộ và chỉ main agent được cập nhật file review-and-fixed-checklist.md

Tiêu chí review:
- Độ đầy đủ và chính xác kỹ thuật (sử dụng context7 mcp nếu cần)
- Tính logic giữa các bài
- Độ dễ hiểu với người học
- đánh giá xem đã tách rõ ràng document.md và exercise.md (nếu cần)
- Thiếu ví dụ/thực hành
- Bài quá dài/quá ngắn
- Nội dung trùng lặp
- Thuật ngữ chưa giải thích
- Chỗ cần thêm diagram, checklist, quiz hoặc exercise
- Mức độ phù hợp với mục tiêu course
