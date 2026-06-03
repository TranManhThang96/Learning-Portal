# Day 19 Document — Stateful Streams Notes

## Mục đích

File này gom deep-dive về state store, windowing, joins và recovery để `lesson.md` giữ nhịp học chính.

## Reference Notes

- Window close theo stream-time, không theo wall-clock thuần túy.
- Grace period càng dài càng giữ state lâu và tăng disk/RocksDB pressure.
- Changelog topic là phần durability của state store; đừng xóa nếu chưa hiểu recovery impact.
- Interactive Queries hữu ích cho local state lookup, nhưng cần routing metadata khi scale nhiều instance.
- EOS trong Kafka Streams bảo vệ read-process-write trong Kafka, không tự đảm bảo side effect ngoài Kafka.

## Recovery Checklist

1. Xác định state store và changelog topic tương ứng.
2. Kiểm tra consumer group rebalance và restoration lag.
3. Kiểm tra disk local state dir có đủ dung lượng.
4. Nếu restore chậm, kiểm tra changelog retention và broker throughput.
