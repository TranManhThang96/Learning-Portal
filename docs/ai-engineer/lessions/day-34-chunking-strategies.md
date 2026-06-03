# Day 34: Chunking Strategies

Chunking là bước biến tài liệu dài thành các đơn vị có thể embedding, search, rerank, cite và audit trong hệ thống RAG. Bài này tập trung vào cách chọn chiến lược chunking theo loại tài liệu, chất lượng citation, latency, chi phí index và khả năng dùng trong production.

## Nội dung

- [Bài học chính](./day-34-chunking-strategies/lession.md)
- [Tài liệu thực hành](./day-34-chunking-strategies/document.md)
- [Bài tập và hướng dẫn đánh giá](./day-34-chunking-strategies/exercise.md)

## Mục tiêu sau bài học

- Hiểu fixed-size, recursive, semantic, markdown-aware, PDF, code và parent-child chunking.
- Biết chọn `chunk_size`, `overlap`, metadata và parser theo context.
- Biết rủi ro citation sai page/source, table bị mất nghĩa, code bị cắt giữa symbol và PDF bị sai layout.
- Tự chạy thí nghiệm so sánh 3 chiến lược chunking trên cùng một document.
- Trả lời được: dùng chunking strategy nào trong production, với điều kiện gì.
