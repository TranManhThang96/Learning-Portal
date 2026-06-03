# Day 7 Exercises: DLQ Replay, Retry Jitter, Error Classification

## Exercise 1: DLQ Replay Tool

Build a small Go command `dlq_replay.go` with three modes:

```bash
go run dlq_replay.go inspect
go run dlq_replay.go replay --limit 10
go run dlq_replay.go discard --message-id ORD-123
```

Requirements:
- Read from `orders.dead-letter` with manual ack.
- Preserve `message_id`, `correlation_id`, tracing headers and original payload.
- Add headers `x-replayed=true`, `x-replayed-at`, and increment `x-replay-count`.
- Publish to the original exchange before acking the DLQ message.
- Use publisher confirms; if publish is nacked or confirm times out, do not ack the DLQ message.

## Exercise 2: Retry Backoff With Jitter

Replace fixed retry delays with exponential backoff plus jitter:

```text
delay = min(base * 2^attempt, maxDelay) + random(0, base)
```

Validate:
- Transient errors do not retry all at the same second.
- `x-retry-count` is still capped.
- Final failure is routed to DLQ.

## Exercise 3: Error Classification

Create a function:

```go
func Classify(err error) ErrorClass
```

Classes:
- `Permanent`: malformed JSON, schema mismatch, invalid business state.
- `Transient`: timeout, connection reset, 429/rate limit, temporary downstream outage.
- `Unknown`: retry once or twice, then DLQ.

Expected action:
- `Permanent` -> `nack(requeue=false)`.
- `Transient` -> publish to retry queue, then ack original after confirm.
- `Unknown` -> short retry budget, then DLQ.

## Exercise 4: Idempotency Key

Add idempotency to the retry pipeline:

- Prefer `MessageId` when present.
- Fall back to a domain key such as `order_id + event_type`.
- Store processed keys in Redis or an in-memory map for the lab.
- Demonstrate duplicate replay does not double-apply side effects.

## Exercise 5: Quorum DLX Policy

Configure quorum at-least-once dead-lettering by policy:

```bash
rabbitmqctl set_policy qq-dlx "^orders\." \
  '{"dead-letter-exchange":"orders.dlx","dead-letter-strategy":"at-least-once","overflow":"reject-publish","delivery-limit":5}' \
  --apply-to quorum_queues
```

Explain why `overflow=reject-publish` is required and what can happen with `drop-head`.
