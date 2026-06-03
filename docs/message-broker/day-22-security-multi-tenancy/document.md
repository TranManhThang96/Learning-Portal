# Day 22 Document — Security Operations Notes

## Mục đích

File này tách security runbook và policy note khỏi bài học chính.

## Policy Notes

- Deny-by-default là baseline; `allow.everyone.if.no.acl.found=false` cần được test trước rollout.
- SASL/PLAIN chỉ chấp nhận được khi có TLS; nếu không credential đi plaintext.
- `super.users` phải tối thiểu và không dùng `User:ANONYMOUS`.
- KRaft dùng `StandardAuthorizer`; tránh hướng dẫn ZooKeeper ACL legacy cho lab hiện đại.
- Quotas phải gắn với tenant/client-id rõ ràng để tránh một tenant làm nghẽn cluster chung.

## Runbook

1. Client auth fail: kiểm tra mechanism, JAAS, cert/truststore và listener name.
2. Authz fail: dùng principal trong log để kiểm tra ACL đúng resource/pattern chưa.
3. Tenant noisy: kiểm tra request quota, byte-rate quota và client-id.
