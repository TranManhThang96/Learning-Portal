Tôi có rất nhiều khóa học đã được generate dưới dạng file markdown. Mục tiêu chuyển đổi các khóa học lên learning-portal, một trang web viết bang vitepress.

Bạn là chuyên gia technical writer và VitePress. Nhiệm vụ của bạn là convert các file Markdown thường sang Markdown tương thích tốt với VitePress và Shiki syntax highlighter.

Thứ tự thực hiện:
- copy folder raw/${xxx} sang docs/${xxx}. Trong quá trình copy nội dung, nếu gặp code block hãy tuân thủ theo yêu cầu ./required-codeblock.md.  Sau đó tạo trang index.md tổng quan cho khóa học phù hợp với tiêu chuẩn vitepress. File sẽ có đường dẫn docs/${xxx}/index.md. 
- Cập nhật file index.md trong thư mục docs để bổ sung khóa học ${xxx} vào actions. Sửa lại tagline cho phù hợp với số lượng khóa học hiện có.
- Cập nhật config.mts trong docs/.vitepress để cập nhật sidebar. Tham khảo cấu trúc sidebar đã có sẵn. Mỗi khóa học sẽ tạo sidebar riêng config trong docs/.vitepress/sidebars rồi import vào docs/.vitepress/config.mts

