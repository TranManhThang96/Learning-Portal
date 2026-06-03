# Day 23 Exercises — Operations & Observability

## Lab Checklist

- Dựng monitoring stack KRaft + Prometheus + Grafana.
- Produce/consume events có correlation ID.
- Quan sát consumer lag bằng kafka-exporter.
- Simulate consumer stop và verify lag alert condition.
- Simulate hot partition bằng key cố định.
- Viết runbook ngắn cho incident bạn vừa tạo.

## Design Drills

1. Alert consumer lag nên dùng absolute threshold hay trend?
2. Trace context qua Kafka header cần field nào để debug saga?
3. Khi lag tăng nhưng CPU consumer thấp, bạn điều tra gì?
