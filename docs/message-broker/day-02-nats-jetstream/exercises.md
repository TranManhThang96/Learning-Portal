# Day 2 Exercises: Poison Message Advisory và DLQ-like Stream

## Mục tiêu

Thực hành quan sát message chạm `MaxDeliver` và route advisory sang một stream riêng để operator có nơi điều tra. Đây là DLQ-like pattern, không phải DLQ tự động như RabbitMQ.

## Exercise 1: Tạo stream bắt advisory

```bash
# Preflight: đảm bảo stream chính tồn tại để consumer lab không fail.
# Nếu đã tạo ORDERS trong lesson.md thì lệnh này có thể báo stream exists; bỏ qua và tiếp tục.
nats stream add ORDERS \
  --subjects 'orders.>' \
  --retention limits \
  --max-msgs 10000 \
  --max-age 24h \
  --storage file \
  --defaults

nats stream add JS_ADVISORIES \
  --subjects '$JS.EVENT.ADVISORY.>' \
  --retention limits \
  --max-msgs 10000 \
  --max-age 24h \
  --storage file \
  --defaults
```

## Exercise 2: Tạo consumer có `max_deliver=3`

```bash
nats consumer add ORDERS poison-demo \
  --pull \
  --filter orders.poison \
  --ack explicit \
  --max-deliver 3 \
  --ack-wait 5s \
  --deliver all \
  --defaults
```

Publish một message lỗi:

```bash
nats pub orders.poison '{"order_id":"BAD-001","reason":"invalid-json-for-consumer"}'
```

Fetch nhưng không ack hoặc `nak` đủ 3 lần:

```bash
nats consumer next ORDERS poison-demo --count 1
nats consumer next ORDERS poison-demo --count 1
nats consumer next ORDERS poison-demo --count 1
```

## Exercise 3: Quan sát advisory

```bash
nats consumer add JS_ADVISORIES inspect --pull --deliver all --ack none --defaults
nats consumer next JS_ADVISORIES inspect --count 5
```

Kỳ vọng: thấy advisory liên quan đến delivery attempts của consumer. Từ advisory này, app/operator có thể publish bản sao sang stream `ORDERS_DLQ`, alert Slack/PagerDuty, hoặc delete message gốc sau khi đã lưu bằng chứng.

## Cleanup

```bash
nats consumer rm ORDERS poison-demo
nats stream rm JS_ADVISORIES
```
