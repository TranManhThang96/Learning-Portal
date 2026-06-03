# Day 18 Exercises — Kafka Streams Basics

## Lab Checklist

- Dựng KRaft compose và tạo topics trong `lesson.md`.
- Chạy producer tạo order mẫu.
- Chạy Streams app và verify routing high-value/standard.
- Thêm malformed JSON và xác nhận handler không crash app.
- Viết test `TopologyTestDriver` cho một branch/filter chính.

## Design Drills

1. Vì sao key sai làm join/window ở các ngày sau khó debug?
2. Khi nào dùng Kafka Streams thay vì consumer thường + database?
3. Nếu output topic lag tăng nhưng input lag ổn, bạn kiểm tra gì trước?
