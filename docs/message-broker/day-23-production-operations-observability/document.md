# Day 23 Document — Observability & Incident Notes

## Mục đích

File này tách runbook vận hành khỏi `lesson.md`, nhất là khi cần dùng trong on-call.

## Golden Signals

- Broker: request latency, under-replicated partitions, ISR shrink, disk usage, network saturation.
- Consumer: lag trend, processing latency, rebalance count, commit latency.
- Producer: error rate, retry rate, record queue time, batch size, compression ratio.
- End-to-end: correlation ID, causation ID, event age, DLQ/replay count.

## Incident Triage

1. Xác định blast radius: một topic, một group, hay toàn cluster.
2. So sánh produce rate với consume rate.
3. Kiểm tra hot partition trước khi scale consumer mù.
4. Nếu under-replicated partitions tăng, ưu tiên broker/disk/network health.
5. Sau mitigation, thêm dashboard/alert cho symptom đã bỏ sót.
