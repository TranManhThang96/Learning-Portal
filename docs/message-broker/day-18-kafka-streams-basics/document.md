# Day 18 Document — Kafka Streams Basics Notes

## Mục đích

File này tách phần reference cho topology, serde và local testing khỏi bài học chính.

## Reference Notes

- `KStream` phù hợp event stream; `KTable` phù hợp latest state theo key.
- Stateless operator không cần state store, nhưng vẫn cần serde đúng cho key/value.
- Topology nên được đặt tên processor/state store rõ ràng để metrics dễ đọc.
- Deserialization exception handler không thay thế schema governance; nó chỉ giúp app không chết vì record xấu.
- `TopologyTestDriver` giúp test logic deterministically, nhưng không thay thế integration test với broker thật.

## Debug Checklist

1. Verify topic input có key đúng.
2. Verify serde class khớp type thực tế.
3. In topology description trước khi chạy.
4. Kiểm tra consumer lag và app logs theo `application.id`.
