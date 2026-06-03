# Day 16 Exercises — Schema Registry

## Lab Checklist

- Dựng compose KRaft + Schema Registry trong `lesson.md`.
- Register schema v1 cho `orders-value`.
- Thêm field optional có default và verify compatibility pass.
- Thử xóa field required để compatibility fail.
- Chạy producer/consumer Go và xác nhận consumer deserialize được payload cũ và mới.

## Design Drills

1. Một team muốn đổi `amount` từ `double` sang `string`. Bạn yêu cầu migration thế nào để không phá consumer cũ?
2. Khi nào nên dùng subject strategy theo topic, record name, hoặc topic-record name?
3. Nếu Schema Registry down 5 phút, producer/consumer nào còn chạy được nhờ cache, và case nào fail?
