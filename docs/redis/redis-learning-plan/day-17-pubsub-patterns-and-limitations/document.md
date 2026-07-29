# Day 17: Pub/Sub - Reference Document

---

## 1. Pub/Sub Commands Cheat Sheet

### 1.1. Classic Pub/Sub Commands

```bash
# SUBSCRIBE - Đăng ký nhận message từ channel(s)
SUBSCRIBE channel1 channel2 channel3
# Return: subscribe message confirm + pushed messages

# UNSUBSCRIBE - Hủy đăng ký từ channel(s), không argument = unsubscribe all
UNSUBSCRIBE channel1 channel2
UNSUBSCRIBE  # Hủy tất cả

# PUBLISH - Gửi message tới channel
PUBLISH channel1 "Hello World"
# Return: số subscriber nhận được message

# PSUBSCRIBE - Đăng ký theo pattern (regex)
PSUBSCRIBE "news:*" "events:*" "user:*"
# Return: psubscribe message confirm + pushed messages

# PUNSUBSCRIBE - Hủy pattern subscription
PUNSUBSCRIBE "news:*"
PUNSUBSCRIBE  # Hủy tất cả pattern

# PUBSUB CHANNELS - Liệt kê active channels
PUBSUB CHANNELS               # Tất cả
PUBSUB CHANNELS "news:*"      # Filter theo pattern
PUBSUB CHANNELS               # Return: list of channel names

# PUBSUB NUMSUB - Đếm subscriber count của channel(s)
PUBSUB NUMSUB channel1 channel2
# Return: channel1 -> 5, channel2 -> 3

# PUBSUB NUMPAT - Đếm pattern subscription count
PUBSUB NUMPAT
# Return: số pattern subscription (important: CPU overhead indicator)
```

### 1.2. Sharded Pub/Sub Commands (Redis 7.0+)

```bash
# SPUBLISH - Sharded publish (gửi tới đúng shard slot)
SPUBLISH channel1 "Hello from shard"
# Return: số subscriber nhận được

# SSUBSCRIBE - Sharded subscribe
SSUBSCRIBE channel1 channel2
# Return: ssubscribe message confirm + pushed messages

# SUNSUBSCRIBE - Sharded unsubscribe
SUNSUBSCRIBE channel1

# PUBSUB SHARDCHANNELS - List shard channels (Redis 7.0+)
PUBSUB SHARDCHANNELS
# Return: danh sách shard channels

# PUBSUB SHARDNUMSUB - Subscriber count cho shard channel(s)
PUBSUB SHARDNUMSUB channel1 channel2
```

### 1.3. Keyspace Notification (liên quan)

```bash
# Enable keyspace notifications cho key events
CONFIG SET notify-keyspace-events KElsg

# K = Keyspace events
# E = Keyevent events
# l = List commands
# s = Set commands
# g = String commands

# Subscribe keyspace events
SUBSCRIBE __keyevent@0__:set          # Bất kỳ SET command nào trên db 0
SUBSCRIBE __keyevent@0__:del          # Bất kỳ DEL command nào trên db 0
PSUBSCRIBE __key*__:expired           # Bất kỳ key expired nào

# Monitor thực tế (debugging)
redis-cli --subscribe __keyevent@0__:*
```

---

## 2. Comparison Table: Pub/Sub vs Alternatives

| Feature | Pub/Sub | Streams | Kafka | NATS | RabbitMQ |
|---|---|---|---|---|---|
| **Delivery** | At-most-once | At-least-once | At-least-once / Exactly-once | At-most-once / At-least-once | At-least-once |
| **Persistence** | No | Yes (in-memory) | Yes (disk) | Yes (JetStream) | Yes (memory + disk) |
| **Replay** | No | Yes | Yes | Yes | No (basic) |
| **Consumer Group** | No | Yes | Yes | Yes | Yes |
| **Dead Letter Queue** | No | No | Yes | Yes | Yes |
| **Message Retention** | 0 sec | Until XACK/XTRIM | Configurable | Configurable | Configurable |
| **Throughput** | Highest | Very High | Very High | Very High | Medium |
| **Latency** | < 1ms | < 1ms | 5-20ms | < 1ms | 1-5ms |
| **Cluster** | Broadcast / Sharded | Hash-slot | Native partition | Super Cluster | Cluster |
| **Schema Registry** | No | No | Yes | No | No |
| **Exactly-once** | No | No | Yes (with idempotent producer) | No | Yes (with confirms) |
| **Message Priority** | No | No | No | No | Yes |
| **Operations** | Trivial | Simple | Complex | Simple | Medium |

---

## 3. Go Code Examples

### 3.1. go-redis PubSub (v9)

```go
package main

import (
    "context"
    "fmt"
    "log"
    "sync"
    "time"

    "github.com/redis/go-redis/v9"
)

func main() {
    rdb := redis.NewClient(&redis.Options{
        Addr:         "localhost:6379",
        PoolSize:     10,
        MinIdleConns: 5,
    })

    ctx := context.Background()

    // === SEPARATE CONNECTIONS: cmdConn vs subConn ===
    cmdConn := rdb
    subConn := rdb.duplicate() // Tạo connection riêng cho subscribe

    // Publisher goroutine
    go func() {
        for i := 0; i < 10; i++ {
            msg := fmt.Sprintf("message-%d", i)
            count, err := cmdConn.Publish(ctx, "notifications", msg).Result()
            if err != nil {
                log.Printf("Publish error: %v", err)
            } else {
                fmt.Printf("[PUBLISHER] Sent: %s (subscribers: %d)\n", msg, count)
            }
            time.Sleep(100 * time.Millisecond)
        }
    }()

    // Subscriber goroutine
    var wg sync.WaitGroup
    wg.Add(1)
    go func() {
        defer wg.Done()

        pubsub := subConn.Subscribe(ctx, "notifications")

        // Đợi SUBSCRIBE confirm
        _, err := pubsub.Receive(ctx)
        if err != nil {
            log.Fatalf("Subscribe error: %v", err)
        }
        fmt.Println("[SUBSCRIBER] Subscribed to 'notifications'")

        // Channel mode (non-blocking)
        ch := pubsub.Channel()

        for msg := range ch {
            fmt.Printf("[SUBSCRIBER] Received: %s (channel: %s)\n", msg.Payload, msg.Channel)
        }
    }()

    // Simulate subscriber disconnect sau 500ms
    go func() {
        time.Sleep(500 * time.Millisecond)
        fmt.Println("[SUBSCRIBER] Simulating disconnect...")
        subConn.Close()
    }()

    time.Sleep(2 * time.Second)

    // === RECONNECT với REPLAY (dùng Streams hybrid) ===
    // Xem Day 18: Streams consumer group cho replay capability
}

func subscriberWithReconnect(ctx context.Context, rdb *redis.Client, channel string) {
    for {
        select {
        case <-ctx.Done():
            return
        default:
            subConn := rdb.duplicate()
            pubsub := subConn.Subscribe(ctx, channel)

            _, err := pubsub.Receive(ctx)
            if err != nil {
                log.Printf("Reconnect error: %v, retrying...", err)
                time.Sleep(time.Second)
                continue
            }

            fmt.Println("[SUBSCRIBER] Reconnected, resuming...")

            for msg := range pubsub.Channel() {
                fmt.Printf("[SUBSCRIBER] Received: %s\n", msg.Payload)
            }

            subConn.Close()
            time.Sleep(time.Second) // Backoff trước reconnect
        }
    }
}
```

### 3.2. Handling Slow Consumer

```go
package main

import (
    "context"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

func slowConsumerDemo() {
    rdb := redis.NewClient(&redis.Options{
        Addr: "localhost:6379",
    })

    ctx := context.Background()

    // Slow subscriber: xử lý message chậm
    subConn := rdb.duplicate()
    pubsub := subConn.Subscribe(ctx, "slow-channel")

    _, err := pubsub.Receive(ctx)
    if err != nil {
        log.Fatal(err)
    }

    // Xử lý message với timeout
    go func() {
        for msg := range pubsub.Channel() {
            go func(m *redis.Message) {
                ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
                defer cancel()

                select {
                case <-ctx.Done():
                    log.Printf("Message processing timeout: %s", m.Payload)
                default:
                    // Simulate slow processing
                    time.Sleep(10 * time.Second)
                    log.Printf("Processed: %s", m.Payload)
                }
            }(msg)
        }
    }()

    // Publisher: gửi nhiều message nhanh
    for i := 0; i < 100; i++ {
        rdb.Publish(ctx, "slow-channel", "msg-"+string(rune(i)))
    }

    // Monitor output buffer
    // redis-cli CLIENT LIST | grep omem
    // redis-cli PUBSUB NUMSUB slow-channel
}
```

---

## 4. TypeScript Code Examples (ioredis)

### 4.1. Basic PubSub với ioredis

```typescript
import Redis from 'ioredis';

// TẠO 2 CONNECTION RIÊNG BIỆT
const redis = new Redis({ host: 'localhost', port: 6379, lazyConnect: true });
const subscriber = new Redis({ host: 'localhost', port: 6379, lazyConnect: true });

async function main() {
    await redis.connect();
    await subscriber.connect();

    // === SUBSCRIBER SETUP ===
    // Option 1: Event-based
    subscriber.subscribe('notifications', 'alerts', (err, count) => {
        if (err) {
            console.error('Subscribe error:', err);
            return;
        }
        console.log(`Subscribed to ${count} channel(s)`);
    });

    subscriber.on('message', (channel: string, message: string) => {
        console.log(`[${channel}] ${message}`);
    });

    // Option 2: PSUBSCRIBE pattern
    subscriber.psubscribe('user:*', 'order:*', (err, count) => {
        if (err) console.error('PSubscribe error:', err);
        console.log(`PSubscribed to ${count} pattern(s)`);
    });

    subscriber.on('pmessage', (pattern: string, channel: string, message: string) => {
        console.log(`[pattern:${pattern}][${channel}] ${message}`);
    });

    // === PUBLISHER ===
    // Publisher dùng connection thường, KHÔNG phải subscriber connection
    await redis.publish('notifications', 'Hello from publisher!');
    await redis.publish('user:123:login', 'User 123 logged in');
    await redis.publish('order:456:status', 'Order 456 shipped');

    // === MONITORING ===
    // PUBSUB NUMSUB
    const numsubs = await redis.pubsub('NUMSUB', 'notifications', 'alerts');
    console.log('Subscriber counts:', numsubs);

    // PUBSUB CHANNELS
    const channels = await redis.pubsub('CHANNELS');
    console.log('Active channels:', channels);

    // PUBSUB NUMPAT
    const numpat = await redis.pubsub('NUMPAT');
    console.log('Pattern count:', numpat);
}

main().catch(console.error);
```

### 4.2. Reconnect Handler

```typescript
import Redis from 'ioredis';

class RedisPubSubManager {
    private publisher: Redis;
    private subscriber: Redis;
    private subscribedChannels: Set<string> = new Set();
    private messageHandler: (channel: string, message: string) => void;

    constructor(
        private host: string,
        private port: number,
        messageHandler: (channel: string, message: string) => void
    ) {
        this.messageHandler = messageHandler;

        this.publisher = new Redis({ host, port, lazyConnect: true });
        this.subscriber = new Redis({ host, port, lazyConnect: true, maxRetriesPerRequest: null });

        this.setupSubscriberHandlers();
    }

    private setupSubscriberHandlers() {
        this.subscriber.on('message', (channel, message) => {
            this.messageHandler(channel, message);
        });

        this.subscriber.on('pmessage', (pattern, channel, message) => {
            this.messageHandler(channel, message);
        });

        // === CRITICAL: RECONNECT HANDLER ===
        this.subscriber.on('end', () => {
            console.warn('[SUBSCRIBER] Connection ended, reconnecting...');
            this.reconnectWithBackoff();
        });

        this.subscriber.on('error', (err) => {
            console.error('[SUBSCRIBER] Error:', err.message);
        });

        this.subscriber.on('reconnecting', () => {
            console.log('[SUBSCRIBER] Reconnecting...');
        });
    }

    private async reconnectWithBackoff(attempt = 1) {
        const maxAttempts = 10;
        const baseDelay = 1000; // 1 second
        const maxDelay = 30000; // 30 seconds

        if (attempt > maxAttempts) {
            console.error('[SUBSCRIBER] Max reconnect attempts reached');
            return;
        }

        // Exponential backoff với jitter
        const delay = Math.min(baseDelay * Math.pow(2, attempt - 1), maxDelay);
        const jitter = Math.random() * 1000;
        const waitTime = delay + jitter;

        await new Promise((resolve) => setTimeout(resolve, waitTime));

        try {
            await this.subscriber.connect();

            // === RE-SUBSCRIBE SAU KHI RECONNECT ===
            if (this.subscribedChannels.size > 0) {
                await this.subscriber.subscribe(...Array.from(this.subscribedChannels));
            }

            console.log(`[SUBSCRIBER] Reconnected successfully after ${attempt} attempt(s)`);
        } catch (err) {
            console.error(`[SUBSCRIBER] Reconnect failed (attempt ${attempt}):`, err);
            await this.reconnectWithBackoff(attempt + 1);
        }
    }

    async subscribe(...channels: string[]) {
        channels.forEach((ch) => this.subscribedChannels.add(ch));
        await this.subscriber.subscribe(...channels);
    }

    async psubscribe(...patterns: string[]) {
        await this.subscriber.psubscribe(...patterns);
    }

    async publish(channel: string, message: string): Promise<number> {
        return this.publisher.publish(channel, message);
    }

    async close() {
        await this.publisher.quit();
        await this.subscriber.quit();
    }
}

// Usage
const manager = new RedisPubSubManager(
    'localhost',
    6379,
    (channel, message) => {
        console.log(`[HANDLER] ${channel}: ${message}`);
    }
);

await manager.subscribe('notifications', 'alerts');
await manager.psubscribe('user:*');
await manager.publish('notifications', 'Test message');
```

---

## 5. Configuration Reference

### 5.1. Slow Consumer Buffer Protection

```bash
# Cấu hình output buffer limit cho pubsub connections
# Syntax: client-output-buffer-limit <class> <hard_limit> <soft_limit> <soft_seconds>
CONFIG SET client-output-buffer-limit pubsub 32mb 8mb 60

# Giải thích:
# - 32mb hard_limit: Disconnect ngay lập tức khi buffer >= 32MB
# - 8mb soft_limit: Bắt đầu count sau 8MB
# - 60 seconds: Grace period trước khi disconnect (nếu buffer > soft_limit)

# Kiểm tra cấu hình hiện tại
CONFIG GET client-output-buffer-limit

# Monitoring buffer usage per client
redis-cli CLIENT LIST | awk '{print $1, $NF}' | grep omem
# Output: id=5 omem=1234567 id=6 omem=0 id=7 omem=8388608
```

### 5.2. Pub/Sub Related Configs

```bash
# Max pattern subscriptions (prevent CPU abuse)
CONFIG GET maxpattern  # default: 32768

# Client name (useful for monitoring)
CLIENT SETNAME subscriber-1
CLIENT GETNAME

# Liệt kê pubsub clients
redis-cli CLIENT LIST | grep sub=
# id=5 sub=3 psub=1 ... -> subscribed 3 channels, 1 pattern
```

### 5.3. Docker Compose cho Pub/Sub Testing

```yaml
# docker-compose.yaml
version: '3.8'

services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    command: >
      redis-server
      --client-output-buffer-limit pubsub 32mb 8mb 60
      --loglevel notice
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # Publisher service
  publisher:
    image: golang:1.22-alpine
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./publisher:/app
    working_dir: /app
    command: go run main.go

  # Subscriber service (3 instances)
  subscriber-1:
    image: golang:1.22-alpine
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./subscriber:/app
    working_dir: /app
    command: go run main.go

  subscriber-2:
    image: golang:1.22-alpine
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./subscriber:/app
    working_dir: /app
    command: go run main.go
```

---

## 6. Links & Resources

### Official Redis Documentation

- [Redis Pub/Sub](https://redis.io/docs/interact/pubsub/)
- [Sharded Pub/Sub (Redis 7.0+)](https://redis.io/docs/interact/pubsub/sharded-pubsub/)
- [PUBSUB command reference](https://redis.io/commands/?group=pubsub)
- [Client output buffer limit](https://redis.io/docs/management/optimization/resource-limits/#client-output-buffer-limits)
- [Keyspace notifications](https://redis.io/docsmanagement/notifications/)

### Redis Internals

- [Redis internals: Pub/Sub implementation](https://github.com/redis/redis/blob/unstable/src/pubsub.c)
- [antirez blog: Redis Pub/Sub design](http://antirez.com/latest/2010/04/14/redis-pubsub-is-on steroids/)
- [Redis client output buffer management](https://redis.io/docs/management/optimization/resource-limits/)

### Blog & Articles

- [Redis Pub/Sub vs Redis Streams - Real-world comparison](https://redis.com/blog/redis-streams-vs-pubsub/)
- [How Discord uses Redis Pub/Sub](https://discord.com/blog/using-rust-to-scale-redis-for-discord-s-chat-system)
- [GitLab: Caching architecture with Redis Pub/Sub](https://about.gitlab.com/handbook/engineering/architecture_guidelines/redis.html)
- [Why Kafka is not a replacement for Pub/Sub](https://www.confluent.io/blog/when-to-use-apache-kafka-vs-websocket/)

### Related Days

- **Day 12** (Connection Pooling): Connection management, why separate connection for subscribe
- **Day 18** (Redis Streams): Persistence, consumer groups, XACK — the Streams alternative to Pub/Sub
- **Day 22** (Redis Cluster): Cluster PUBLISH broadcast behavior vs sharded SPUBLISH
