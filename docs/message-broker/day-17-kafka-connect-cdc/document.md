# Day 17 Document — CDC Operations Notes

## Mục đích

File này gom phần vận hành CDC/outbox để `lesson.md` không phải chứa mọi runbook chi tiết.

## Operational Notes

- Debezium PostgreSQL cần logical replication, replication slot và WAL retention đủ lớn cho outage window.
- Slot lag tăng nghĩa là source DB đang giữ WAL; cần alert trước khi đầy disk.
- Outbox cleanup không do Debezium tự làm. Cleanup phải dựa trên connector lag, retention và replay policy.
- Distributed Connect cần internal topics ổn định: config, offset và status topic không được xóa thủ công.
- Sink connector optional phải được verify bằng `/connector-plugins` trước khi register config.

## Incident Runbook

1. Connector stopped: kiểm tra `/connectors/{name}/status`.
2. Task failed: đọc trace trong task status, không restart mù.
3. Slot lag tăng: giảm batch pressure, scale Connect nếu phù hợp, kiểm tra downstream sink.
4. Duplicate event: kiểm tra outbox idempotency key và consumer inbox.
