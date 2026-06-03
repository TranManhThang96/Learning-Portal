# Day 20 Exercises — Performance Tuning

## Lab Checklist

- Chạy benchmark 1p, 4p, 12p.
- So sánh producer throughput với `linger.ms`, `batch.size`, compression.
- So sánh consumer throughput với `fetch.min.bytes` và `max.poll.records`.
- Chạy optional 3-broker compose và test ISR shrink.
- Ghi kết quả vào bảng: throughput, p95 latency, CPU, disk I/O, network.

## Design Drills

1. Khi p99 latency tăng nhưng throughput không đổi, bạn kiểm tra broker metric nào trước?
2. Vì sao RF=1 benchmark không đủ cho production sizing?
3. Workload nhiều key hot cần đổi partitioning strategy hay tăng partition?
