# Day 19 Exercises — Stateful Streams

## Lab Checklist

- Chạy app stateful từ `lesson.md`.
- Produce customers/payments/orders có cùng key.
- Verify join output và hourly revenue.
- Stop app, xóa local state dir, start lại và quan sát restore.
- Thử late event ngoài grace period và xác nhận bị drop/late metric tăng.

## Design Drills

1. Chọn grace period cho payment reconciliation dựa trên SLA nào?
2. Khi state store lớn hơn disk local, bạn refactor topology hay scale broker thế nào?
3. Interactive Queries cần load balancer/routing metadata ra sao?
