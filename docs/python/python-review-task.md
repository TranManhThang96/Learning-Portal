Bạn là main coordinator, một expert developer python, có nhiều kinh nghiệm về AI. 

Nhiệm vụ: review  chương trình học python trong 35 ngày theo plan: ./mega-prompt.md và ./update-prompt.md

Quy trình bắt buộc:
1. Đọc trước plan: ./mega-prompt.md và ./update-prompt.md
2. Spawn 7 subagents song song, mỗi subagent review nội dung của 5 ngày học. 
   - Nội dung luôn luôn bám sát theo yêu cầu của plan. Hãy review thận theo các tiêu chí: đúng đủ chưa, thời gian phân bổ hợp lí chưa. 
   - Sau khi review xong, subagent có thể chỉnh sửa, bổ sung luôn nếu thiếu, sửa nếu sai. 
   - Về môi trường sử dụng thì tập xuyên suốt môi trường chạy với pyenv và uv nhé. 
   - Luôn sử dụng context7 để bổ sung tài liệu kỹ thuật hiện tại. 
   - Mỗi bài học đang đánh tên là day01, day02,... Hãy bổ sung nội dung bài học vào tên folder kiểu như là day01-{noi-dung-bai-hoc}.Ví dụ day01-cai-dat-moi-truong
3. Main agent tự tổng hợp 7 subagents và đánh giá.