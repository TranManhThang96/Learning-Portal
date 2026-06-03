# Day 17 Exercises — Kafka Connect + CDC

## Lab Checklist

- Dựng compose KRaft + PostgreSQL + Connect.
- Verify plugin PostgreSQL connector bằng `/connector-plugins`.
- Register source connector và đọc topic CDC bằng `kafka-console-consumer`.
- Insert/update/delete row và quan sát before/after payload.
- Tạo outbox event và verify event routing theo aggregate/event type.

## Design Drills

1. Khi replication slot lag tăng liên tục, bạn phân biệt source DB issue với sink issue thế nào?
2. Outbox table nên partition/cleanup theo tiêu chí nào ở hệ thống 10k events/s?
3. Khi connector restart và emit duplicate, consumer cần contract idempotency gì?
