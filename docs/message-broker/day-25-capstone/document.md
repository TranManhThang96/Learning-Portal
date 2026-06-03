# Day 25 Document — Capstone Architecture Notes

## Mục đích

File này tách architecture/runbook khỏi `lesson.md` và đi kèm scaffold runnable trong thư mục Day 25.

## Scaffold Boundaries

- Scaffold chạy 4 services thật: order, payment, inventory và notification.
- Kafka dùng KRaft single-broker để phù hợp local lab; production cần 3+ brokers, RF=3 và `min.insync.replicas=2`.
- PostgreSQL dùng shared database để giảm setup; production nên tách ownership/schema theo service.
- Order service dùng outbox poller; các consumer dùng inbox table để minh họa idempotency.
- Notification service là sink/log observer, chưa gửi email/SMS thật.

## Runbook

1. `docker compose up -d --build`.
2. Gửi `POST /orders`.
3. Xem logs 4 services theo `correlationId`.
4. Nếu order kẹt `PENDING`, kiểm tra outbox unpublished, payment consumer và inventory events.
5. Sau lab, chạy `docker compose down`.
