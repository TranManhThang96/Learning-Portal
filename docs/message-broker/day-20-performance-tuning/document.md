# Day 20 Document — Benchmark Methodology Notes

## Mục đích

File này tách benchmark methodology và caveat để `lesson.md` tập trung vào thao tác đo.

## Methodology

- Luôn tách test 1 partition và N partition; nếu không, bạn đang trộn ordering limit với broker throughput.
- Single-broker chỉ đo relative impact, không chứng minh durability.
- Với durability benchmark, dùng tối thiểu 3 brokers, RF=3, `min.insync.replicas=2`, producer `acks=all`.
- Đo p95/p99 latency cùng throughput; average latency thường che giấu tail.
- Ghi lại broker CPU, disk I/O, network, request queue và GC pause trong cùng thời điểm.

## Common Mistakes

- Tăng partition mà không tăng consumer parallelism.
- Tăng heap quá lớn làm giảm page cache.
- Benchmark qua laptop Wi-Fi rồi suy diễn production capacity.
- Bật compression nhưng không đo CPU producer.
