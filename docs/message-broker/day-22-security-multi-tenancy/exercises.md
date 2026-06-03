# Day 22 Exercises — Security & Multi-tenancy

## Lab Checklist

- Dựng KRaft + StandardAuthorizer baseline.
- Tạo SCRAM users cho admin và app.
- Gán ACL tối thiểu cho producer/consumer.
- Verify happy path produce/consume.
- Verify failure path khi thiếu ACL hoặc sai credential.
- Set quota và quan sát throttling metric/log.

## Design Drills

1. Một tenant cần read-only vào topic prefix `audit.*`; ACL nên viết ra sao?
2. Bạn rotate SCRAM password không downtime bằng quy trình nào?
3. Khi bật mTLS, bạn map certificate principal sang ACL thế nào?
