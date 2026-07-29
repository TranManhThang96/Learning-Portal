# Day 18: Redis Streams & Consumer Groups — Reference Document

---

## 1. Command Cheat Sheet

### Core Stream Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `XADD` | `XADD key [MAXLEN ~N \| MAXLEN N \| MINID id \| NOMKSTREAM] <id \| *> [field value ...]` | Thêm entry vào stream. `*` = auto ID. |
| `XREAD` | `XREAD [COUNT n] [BLOCK ms] STREAMS key [id \| $]` | Đọc entries từ stream(s) theo ID range. `$` = chỉ messages mới. |
| `XREADGROUP` | `XREADGROUP GROUP name consumer [COUNT n] [BLOCK ms] [NOACK] STREAMS key <id \| >` | `>` = message mới chưa delivered cho group; ID cụ thể = pending của chính consumer đó. |
| `XACK` | `XACK key group id [id ...]` | Acknowledge entry đã xử lý xong. |
| `XPENDING` | `XPENDING key group [start end count] [consumer]` | Liệt kê PEL entries chưa ACK. |
| `XCLAIM` | `XCLAIM key group consumer min-idle-time id [id ...] [JUSTID]` | Claim entry từ consumer khác. |
| `XAUTOCLAIM` | `XAUTOCLAIM key group consumer min-idle-time start [COUNT n] [JUSTID]` | Auto-claim tất cả entries idle > threshold. |
| `XTRIM` | `XTRIM key [MAXLEN ~N \| MAXLEN N \| MINID id]` | Trim stream về max length hoặc min ID. |
| `XDEL` | `XDEL key id [id ...]` | Xóa specific entries khỏi stream. |
| `XLEN` | `XLEN key` | Số entries trong stream. |
| `XRANGE` | `XRANGE key start end [COUNT n]` | Đọc entries theo ID range. |
| `XREVRANGE` | `XREVRANGE key end start [COUNT n]` | Đọc ngược. |

### Consumer Group Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `XGROUP CREATE` | `XGROUP CREATE key group id [MKSTREAM] [ENTRIESREAD n]` | Tạo consumer group. `MKSTREAM` = tạo stream nếu chưa có. |
| `XGROUP DESTROY` | `XGROUP DESTROY key group` | Xóa group và PEL. |
| `XGROUP CREATECONSUMER` | `XGROUP CREATECONSUMER key group consumer` | Register consumer vào group. |
| `XGROUP DELCONSUMER` | `XGROUP DELCONSUMER key group consumer` | Xóa consumer khỏi group. |
| `XGROUP SETID` | `XGROUP SETID key group id` | Cập nhật last-delivered-ID. |

### Info Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `XINFO STREAM` | `XINFO STREAM key [FULL]` | Stream metadata, length, radix tree size, groups. |
| `XINFO GROUPS` | `XINFO GROUPS key` | Consumer groups list với PEL size, last-delivered. |
| `XINFO CONSUMERS` | `XINFO CONSUMERS key group` | Consumers trong group với idle time, pending count. |

---

## 2. Comparison Tables

### Streams vs Kafka vs RabbitMQ vs SQS vs Pub/Sub

| Dimension | Redis Streams | Apache Kafka | RabbitMQ | AWS SQS | Redis Pub/Sub |
|---|---|---|---|---|---|
| **Delivery guarantee** | At-least-once | At-least-once / Exactly-once | At-least-once | At-least-once / Exactly-once | At-most-once |
| **Persistence** | In-memory + AOF/RDB | Disk (page cache) | RAM + disk | Managed multi-AZ | None |
| **Retention** | Hours (memory-bound) | Days/weeks/months | Configurable | Infinite | None |
| **Throughput** | ~50-100K msg/s | ~1M+ msg/s | ~50K msg/s | ~300/queue/s | ~100K msg/s |
| **Consumer groups** | Native | Native | Via sharded queue | Via message group | No |
| **Replay** | By ID range | By offset | Partial | No | No |
| **Multi-DC** | Via Cluster/Sentinel | Native MirrorMaker | Federation | Cross-region | No |
| **Ordering** | Per stream (ID order) | Per partition | Per queue | Per group | None |
| **Ops complexity** | Low (use existing Redis) | High (brokers, ZK/KRaft) | Medium | Zero | Low |
| **Storage cost** | RAM | Disk (cheap) | RAM + disk | Pay-per-use | Zero |
| **Best for** | < 50K/s, short retention | High vol, long retention, multi-DC | AMQP routing | AWS-native, zero ops | Real-time fanout |

### Key Parameters Quick Reference

| Parameter | Values | Effect |
|---|---|---|
| `BLOCK ms` | 0 = infinite, 100-10000ms | Blocking wait time. Too short = CPU spin. Too long = message latency. |
| `COUNT n` | 1-10000 | Batch size per read. Too small = overhead. Too large = memory + latency spike. |
| `MAXLEN ~N` | Integer N | Approximate trim. O(1) amortized. ~5% overage. |
| `MAXLEN N` | Integer N | Exact trim. O(N) scan. For compliance. |
| `MINID id` | Entry ID | Trim entries < ID (time-based). |
| `NOACK` | Flag | Skip adding to PEL (fire-and-forget). Useful for monitoring/non-critical. |
| `NOMKSTREAM` | Flag | Fail XADD if stream doesn't exist. |
| `MKSTREAM` | Flag | Create stream when creating group. |
| `min-idle-time` | Milliseconds | Idle time before XAUTOCLAIM claims. Set = 2× p99 process time. |
| `JUSTID` | Flag | Return only IDs, not payloads. Reduces bandwidth. |

---

## 3. Config Templates

### Docker Compose — Redis 7.2+ for Streams

```yaml
# docker-compose.streams.yml
version: "3.8"
services:
  redis:
    image: redis:7.2-alpine
    container_name: redis-streams
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
      --save 900 1
      --save 300 10
      --save 60 10000
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

### Producer Config Template

```typescript
// stream-producer.ts
import Redis from "ioredis";

const redis = new Redis({
  host: "localhost",
  port: 6379,
  maxRetriesPerRequest: 3,
});

const STREAM = "orders:stream";
const GROUP = "order-processors";
const MAXLEN = 100_000; // Safety cap
const RETENTION_MS = 2 * 60 * 60 * 1000; // 2 hours

async function publishOrder(order: {
  id: string;
  customer_id: string;
  amount: number;
}) {
  // XADD with MAXLEN ~N for approximate trimming
  const id = await redis.xadd(
    STREAM,
    "MAXLEN",
    "~",
    String(MAXLEN),
    "*", // auto-generate ID
    "order_id", order.id,
    "customer_id", order.customer_id,
    "amount", String(order.amount),
    "created_at", String(Date.now()),
  );
  console.log(`Published order ${order.id} with ID ${id}`);
  return id;
}
```

### Consumer Group Init Template

```typescript
// stream-consumer.ts
import Redis from "ioredis";

const redis = new Redis({ host: "localhost", port: 6379 });

const STREAM = "orders:stream";
const GROUP = "order-processors";
const CONSUMER = `consumer-${process.pid}`;
const BLOCK_MS = 3000;
const COUNT = 10;
const MIN_IDLE_MS = 60_000; // 1 min — must be > 2× p99 process time

async function initGroup() {
  try {
    // MKSTREAM: create stream if not exists
    // $: start from new entries only (not from beginning)
    await redis.xgroup(
      "CREATE",
      STREAM,
      GROUP,
      "$",
      "MKSTREAM",
    );
    console.log(`Consumer group ${GROUP} created`);
  } catch (err: any) {
    if (err.message.includes("BUSYGROUP")) {
      console.log(`Group ${GROUP} already exists, continuing...`);
    } else {
      throw err;
    }
  }
}

async function processMessage(id: string, fields: string[]): Promise<void> {
  // Parse fields into object
  const data: Record<string, string> = {};
  for (let i = 0; i < fields.length; i += 2) {
    data[fields[i]] = fields[i + 1];
  }
  console.log(`Processing order ${data.order_id} (${id})`);
  // Simulate processing
  await new Promise((r) => setTimeout(r, 500));
}

async function consume() {
  await initGroup();

  while (true) {
    try {
      // XREADGROUP: BLOCK wait for new messages
      const result = await redis.xreadgroup(
        "GROUP", GROUP, CONSUMER,
        "BLOCK", String(BLOCK_MS),
        "COUNT", String(COUNT),
        "STREAMS", STREAM, ">", // ">" = only new messages
      );

      if (!result) {
        console.log(`[${CONSUMER}] No new messages, waiting...`);
        continue;
      }

      const [, messages] = result[0] as [string, [string, string[]][]];
      let acknowledged = 0;

      for (const [id, fields] of messages) {
        try {
          await processMessage(id, fields);
          await redis.xack(STREAM, GROUP, id);
          acknowledged++;
        } catch (err) {
          console.error(`Error processing ${id}:`, err);
          // Don't XACK → stays in PEL for redelivery
          // After MAX_RETRY, push to DLQ (see DLQ pattern)
        }
      }

      console.log(
        `[${CONSUMER}] Processed ${messages.length}, ACKed ${acknowledged}`,
      );
    } catch (err) {
      console.error("Consumer error:", err);
      await new Promise((r) => setTimeout(r, 5000)); // Backoff on error
    }
  }
}

// Run periodic XAUTOCLAIM to recover stalled messages
async function autoClaimRecover() {
  const INTERVAL_MS = 30_000;
  setInterval(async () => {
    try {
      const result = await redis.xautoclaim(
        STREAM, GROUP, CONSUMER,
        String(MIN_IDLE_MS),
        "0-0", // start from beginning of PEL
        "COUNT", "100",
      );
      // result: [nextStartId, claimedIds, messages]
      const [, claimedIds, messages] = result as [string, string[], any[]];

      if (claimedIds.length > 0) {
        console.log(
          `[${CONSUMER}] XAUTOCLAIM recovered ${claimedIds.length} messages`,
        );
        for (const [id, fields] of messages) {
          try {
            await processMessage(id, fields);
            await redis.xack(STREAM, GROUP, id);
          } catch {
            // Already in DLQ logic
          }
        }
      }
    } catch (err) {
      console.error("XAUTOCLAIM error:", err);
    }
  }, INTERVAL_MS);
}

consume().then(() => autoClaimRecover());
```

---

## 4. Go Code Snippets (go-redis)

```go
// stream-producer.go
package main

import (
    "context"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

var rdb = redis.NewClient(&redis.Options{
    Addr: "localhost:6379",
})

func publishOrder(ctx context.Context, orderID, customerID string, amount int64) (string, error) {
    return rdb.XAdd(ctx, &redis.XAddArgs{
        Stream: "orders:stream",
        MaxLen: 100_000, // Approximate
        Approx: true,   // Use ~MAXLEN, not exact
        ID:     "*",     // Auto-generate
        Values: map[string]interface{}{
            "order_id":    orderID,
            "customer_id": customerID,
            "amount":      amount,
            "created_at": time.Now().UnixMilli(),
        },
    }).Result()
}

func initConsumerGroup(ctx context.Context) error {
    err := rdb.XGroupCreateMkStream(ctx, "orders:stream", "order-processors", "$").Err()
    if err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
        return err
    }
    return nil
}
```

```go
// stream-consumer.go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

const (
    stream    = "orders:stream"
    group     = "order-processors"
    minIdleMs = 60_000
)

func consume(ctx context.Context, consumerName string) {
    for {
        // XREADGROUP with BLOCK
        streams, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
            Group:    group,
            Consumer: consumerName,
            Streams:  []string{stream, ">"},
            Block:    time.Second * 3,
            Count:    10,
        }).Result()

        if err == redis.Nil {
            continue
        }
        if err != nil {
            log.Printf("XREADGROUP error: %v", err)
            time.Sleep(time.Second)
            continue
        }

        for _, streamResult := range streams {
            for _, msg := range streamResult.Messages {
                processAndAck(ctx, msg)
            }
        }
    }
}

func processAndAck(ctx context.Context, msg redis.XMessage) {
    orderID := msg.Values["order_id"]
    log.Printf("Processing order: %s", orderID)

    // Process...
    time.Sleep(500 * time.Millisecond)

    // XACK
    rdb.XAck(ctx, stream, group, msg.ID)
    log.Printf("ACKed: %s", msg.ID)
}

func autoClaim(ctx context.Context, consumerName string) {
    ticker := time.NewTicker(30 * time.Second)
    for range ticker.C {
        result, err := rdb.XAutoClaim(ctx, &redis.XAutoClaimArgs{
            Stream:   stream,
            Group:    group,
            Consumer: consumerName,
            MinIdle:  minIdleMs,
            Start:    "0-0",
            Count:    100,
        }).Result()
        if err != nil {
            log.Printf("XAUTOCLAIM error: %v", err)
            continue
        }
        if len(result.Messages) > 0 {
            log.Printf("Recovered %d messages via XAUTOCLAIM", len(result.Messages))
            for _, msg := range result.Messages {
                processAndAck(ctx, msg)
            }
        }
    }
}
```

---

## 5. Dead Letter Queue (DLQ) Pattern

### DLQ Flow

```
Producer ──XADD──▶ Stream ──XREADGROUP──▶ Consumer
                                            │
                                            ├── Process OK  ──XACK──▶ Done
                                            ├── Process Fail ── Retry N times ──┐
                                            │                                    │
                                            └── Retry exhausted ──XADD──▶ DLQ ──┤
                                                                                  │
                                                              Monitor ── Human review
```

### DLQ Implementation (TypeScript)

```typescript
// dlq-handler.ts
const MAX_RETRIES = 5;
const RETRY_HASH = "orders:retry-count";
const DLQ_STREAM = "orders:dlq";

async function processWithRetry(
  redis: any,
  stream: string,
  group: string,
  consumer: string,
  entryId: string,
  fields: string[],
): Promise<boolean> {
  const retryCount = await redis.hincrby(RETRY_HASH, entryId, 1);

  if (retryCount >= MAX_RETRIES) {
    // Move to DLQ
    const payload: string[] = [];
    for (let i = 0; i < fields.length; i += 2) {
      payload.push(fields[i], fields[i + 1]);
    }
    await redis.xadd(
      DLQ_STREAM,
      "*",
      "original-id", entryId,
      "original-stream", stream,
      "retry-count", String(retryCount),
      "failed-at", String(Date.now()),
      ...payload,
    );
    // Remove retry tracking
    await redis.hdel(RETRY_HASH, entryId);
    // ACK original to remove from PEL
    await redis.xack(stream, group, entryId);
    console.warn(`[DLQ] Entry ${entryId} moved after ${retryCount} retries`);
    return true; // Handled (as DLQ)
  }

  // Retry: don't XACK, let it sit in PEL
  console.log(
    `[Retry ${retryCount}/${MAX_RETRIES}] Entry ${entryId} failed, will be redelivered`,
  );
  return false;
}

// Periodic DLQ monitoring
async function monitorDLQ(redis: any) {
  const info = await redis.xinfoStream(DLQ_STREAM);
  console.log(`DLQ size: ${info.length}`);
  if (info.length > 100) {
    console.warn("DLQ backlog growing — manual intervention needed");
  }
}
```

---

## 6. Monitoring Queries

```bash
# Stream length
XLEN orders:stream

# All consumer groups and their pending counts
XINFO GROUPS orders:stream

# PEL per consumer (detailed)
XINFO CONSUMERS orders:stream order-processors

# Pending summary
XPENDING orders:stream order-processors

# Stream memory info
XINFO STREAM orders:stream FULL

# Check for streams without trimming (growth rate)
XLEN orders:stream
# Run before/after to see growth rate

# XPENDING with idle time info
XPENDING orders:stream order-processors - + 10
# Shows up to 10 pending entries with idle time and delivery count
```

---

## 7. Links & References

- [Redis Streams Documentation](https://redis.io/docs/data-types/streams/)
- [Redis Streams Tutorial](https://redis.io/docs/data-types/streams-tutorial/)
- [Consumer Groups in Redis Streams](https://redis.io/docs/data-types/streams/#consumer-groups)
- [XAUTOCLAIM Documentation](https://redis.io/commands/xautoclaim/)
- [Redis Streams internals — radix tree (antirez blog)](http://oldblog.antirez.com)
- [XADD with MAXLEN — performance notes](https://redis.io/commands/xadd/)
- [go-redis v9 Streams API](https://redis.uptrace.dev/guide/go-redis-streams.html)
- [ioredis Streaming](https://github.com/redis/ioredis/blob/main/lib/commands/Streams.js)
