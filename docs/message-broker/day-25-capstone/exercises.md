# Day 25 Exercises — Capstone Acceptance Drills

## Lab Checklist

- Build images: `docker compose build`.
- Start stack: `docker compose up -d`.
- Tạo order hợp lệ và xác nhận status cuối là `CONFIRMED`.
- Tạo order vượt stock và xác nhận status cuối là `CANCELLED`.
- Dừng payment-service, tạo order, quan sát order kẹt `PENDING`, bật lại service và verify flow tiếp tục.
- Kiểm tra logs có `correlationId` xuyên suốt các service.

## Design Drills

1. Nếu tách database mỗi service, outbox/inbox thay đổi ra sao?
2. Mode B thêm RabbitMQ/NATS giải quyết vấn đề gì mà Kafka-only chưa tối ưu?
3. Với 10k orders/sec, bạn tăng partition, consumer instances và DB indexes thế nào?
