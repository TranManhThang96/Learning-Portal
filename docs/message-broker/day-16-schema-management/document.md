# Day 16 Document — Schema Governance Notes

## Mục đích

File này tách phần deep-dive khỏi `lesson.md` để bài học chính vẫn tập trung vào flow 2 giờ. Dùng nó khi cần review production policy trước khi áp dụng Schema Registry trong nhiều team.

## Governance Checklist

- Mỗi event public phải có owner, subject naming convention và compatibility level rõ ràng.
- Default nên là `BACKWARD` hoặc `FULL_TRANSITIVE` tùy mức strictness; không đổi global compatibility chỉ để unblock một service.
- CI nên chạy compatibility check trước khi merge schema mới và nên deserialize sample payload để bắt lỗi mapping thực tế.
- Không xóa subject/version trong giờ làm việc nếu chưa kiểm tra consumer lag, retention và replay requirement.
- Schema ID cache là tối ưu client-side, không phải nguồn truth; source of truth vẫn là `_schemas` topic.

## Runbook Ngắn

Khi producer fail do incompatible schema:

1. Xác định subject và version fail trong log producer.
2. Gọi `/config/{subject}` và `/subjects/{subject}/versions/latest`.
3. So sánh field bị xóa/đổi type/default.
4. Rollback producer hoặc phát hành version tương thích.
5. Sau sự cố, thêm contract test cho case vừa fail.
