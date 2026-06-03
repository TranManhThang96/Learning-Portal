Tôi có rất nhiều khóa học đã được generate dưới dạng file markdown. Mục tiêu chuyển đổi các khóa học lên learning-portal, một trang web viết bang vitepress.

Thứ tự thực hiện:
- copy folder raw/${xxx} sang docs/${xxx}. Sau đó tạo trang index.md tổng quan cho khóa học phù hợp với tiêu chuẩn vitepress. File sẽ có đường dẫn docs/${xxx}/index.md. Để đạt được hiệu quả cao nhất hãy sử dụng prompt trong file 80-20-prompt.md lấy tổng hợp kiến thức quan trọng nhất sau đó cập nhật vào file docs/${xxx}/index.md
- Cập nhật file index.md trong thư mục docs để bổ sung khóa học ${xxx} vào actions. Sửa lại tagline cho phù hợp với số lượng khóa học hiện có.
- Cập nhật config.mts trong docs/.vitepress để cập nhật sidebar. Tham khảo cấu trúc sidebar đã có sẵn. Mỗi khóa học sẽ tạo sidebar riêng config trong docs/.vitepress/sidebars rồi import vào docs/.vitepress/config.mts
- 