# Day 19: Replication Internals

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Giải thích được cơ chế async replication của Redis: PSYNC2 handshake, full sync vs partial sync, replication backlog circular buffer, và tại sao Redis chọn eventual consistency thay vì synchronous.
- Monitor được replica lag bằng `master_repl_offset - slave_repl_offset`, hiểu nguyên nhân lag tăng (network, heavy write, full resync), và đặt alert threshold phù hợp cho từng SLA.
- Phân tích được trade-off giữa read-from-replica và read-your-writes consistency — biết khi nào stale read chấp nhận được, khi nào không.
- Thiết kế được replication topology production: backlog sizing, diskless replication, fan-out write overhead, và `min-replicas-to-write` cho durability-sensitive workloads.
- Simulate và debug được các failure mode phổ biến: desync, full resync storm, backlog overflow, replication loop sau failover.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: Read-Replica Trả Về Dữ Liệu Đã Xóa

Một e-commerce service đọc session từ replica để giảm load lên master. Flow:

1. User login → `SET session:user123 "{...}"` → master
2. User logout → `DEL session:user123` → master
3. Ngay sau đó, user request tiếp → đọc từ replica → replica chưa nhận `DEL` → **session vẫn còn** → unauthorized access.

Root cause: async replication lag ~50-200ms; sau DELETE, replica chưa apply command. Đội dev không monitor replica lag, không có fallback logic.

**Lesson**: Read-from-replica không bao giờ đảm bảo read-your-writes. Nếu ứng dụng cần đọc dữ liệu vừa ghi, phải đọc từ master hoặc implement sequence number tracking.

### Incident 2: Full Resync Storm Sau Network Partition

Một master gặp network partition 30 giây với tất cả replica. Khi network khôi phục:

1. Replica reconnect → gửi `PSYNC replid offset`
2. Master backlog (mặc định chỉ 1MB) không chứa đủ 30 giây writes → partial sync fail
3. Tất cả replica yêu cầu full sync → `BGSAVE` trên master
4. Master có 50GB dataset → `BGSAVE` tạo 50GB RDB file → disk I/O spike → master unresponsive 90 giây
5. Replication lag tăng vọt → replicas queue commands → backlog overflow → lại full sync

Đây là **full resync storm**: chain reaction bắt đầu từ backlog size quá nhỏ.

**Lesson**: `repl-backlog-size` phải đủ lớn để chứa peak write burst trong expected disconnection time.

### Incident 3: Twitter/X — Read From Replica Cho Trending Topic

Twitter từng dùng Redis replica để scale read cho trending topics và search. Problem: khi một hashtag trending, master nhận hàng triệu writes/giây. Replica lag tăng lên 5-10 giây. Người dùng thấy "trending" hashtag không khớp với thực tế. Team phải disable replica read cho trending feature, quay về đọc từ master, gây hot key problem.

**Lesson**: Read-from-replica chỉ an toàn khi write throughput thấp và SLA chấp nhận lag. Hot write workload cần read-from-master hoặc cluster sharding.

### Incident 4: Chained Replication Gây Loop

Một team setup: master → replica1 → replica2. Gặp bug khi replica1 promoted thành master (do failover). replica2 vẫn nghĩ replica1 là master. Khi replica1 (now master) gửi replication stream đến replica2, replica2 gửi lại commands đến replica1 (giờ là master) → **replication loop**. Kết quả: CPU spike, memory explosion, cluster down.

**Lesson**: Sau failover, tất cả replicas phải được redirect đến new master. Chained replication (master → replica → replica) là anti-pattern trong production. Dùng Redis Sentinel hoặc Cluster để quản lý topology tự động.

---

## 3. Kiến thức nền cần có

- **Day 6 Persistence (RDB & AOF)**: `BGSAVE`, `fork()`, COW (copy-on-write) — vì full sync dựa trên RDB snapshot
- **Day 10 Capacity Planning**: replica memory overhead, network bandwidth estimation — để tính toán replication cost
- **Day 11 Pipelining**: RTT concept — để hiểu tại sao async replication giảm latency
- **Day 14 Hot Key & Big Key**: big key trên master làm replication chậm hơn vì mỗi command được gửi đến replica
- **Day 15 Transactions**: Redis atomicity model — để hiểu replicated commands cũng atomic trên replica

---

## 4. Lý thuyết chi tiết

### 4.1. Master-Replica Replication — First Principles

Redis replication là **single-leader, async, push-based**. Master chủ động push commands đến replicas qua long-lived TCP connection.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Redis Replication Topology                     │
│                                                                  │
│   Master (primary)                                               │
│     │                                                            │
│     │  TCP connection #1 (commands stream)                       │
│     ├─────────────────────────────────────▶  Replica 1 (read)   │
│     │  TCP connection #2                                          │
│     ├─────────────────────────────────────▶  Replica 2 (read)   │
│     │  TCP connection #3                                          │
│     └─────────────────────────────────────▶  Replica N (HA backup)│
│                                                                  │
│   Writes: Master only                                             │
│   Reads:  Master + all replicas (configurable)                   │
│   Async:  Master không blocking chờ replica confirm              │
└─────────────────────────────────────────────────────────────────┘
```

**Tại sao async, không phải sync?**

Sync replication (đợi replica confirm trước khi trả response) giải quyết được durability nhưng tăng latency. Với RTT (Round Trip Time) 1ms:

- Sync: mỗi write chịu thêm 1ms+ latency
- Async: write latency không bị ảnh hưởng, replica nhận command trong background

Redis chọn eventual consistency: write đến master, replica eventually nhận. Redis cung cấp `WAIT` command để request acknowledgment từ replica khi cần (partial sync acknowledgment), nhưng không enforce sync mặc định.

### 4.2. PSYNC2 Handshake — Mermaid Sequence Diagram

```
sequenceDiagram
    participant R as Replica
    participant M as Master

    Note over R: State: DISCONNECTED

    R->>M: TCP connect()
    R->>M: PING
    M-->>R: PONG

    Note over R: Initial handshake
    R->>M: REPLCONF listening-port 6380
    M-->>R: OK
    R->>M: REPLCONF ip-address 10.0.1.20
    M-->>R: OK
    R->>M: REPLCONF ACK 0
    M-->>R: OK

    Note over R,M: Determine sync type
    R->>M: PSYNC ? -1
    Note right of M: ? = unknown replid<br/>-1 = full sync

    alt FULL SYNC (first time or partial sync impossible)
        M-->>R: FULLRESYNC <replid> 0
        Note over M: BGSAVE RDB → disk or socket
        M->>R: <RDB file or streaming>
        Note over R: Load RDB into memory
        R->>M: REPLCONF ACK <offset>

    else PARTIAL SYNC (Redis 4+)
        M-->>R: CONTINUE
        Note over M: Send only missing commands
        M->>R: <command stream from offset>
    end

    Note over R: State: CONNECTED, STREAMING
    Note over M: Replication stream ongoing
    loop Every replconf-timeout
        R->>M: REPLCONF ACK <slave_repl_offset>
        M-->>R: OK
    end
```

**PSYNC2 command format**: `PSYNC <replid> <offset>`

- `? -1`: full sync (don't know replid, want all data)
- `<replid> <offset>`: partial sync attempt (continue from this offset)
- Master response: `FULLRESYNC <new_replid> <offset>` hoặc `CONTINUE <replid>` hoặc `ERR`

### 4.3. Full Sync vs Partial Sync

#### Full Sync (Full Resynchronization)

```
┌──────────────┐         ┌──────────────┐
│    Master    │         │   Replica    │
│              │         │              │
│  BGSAVE      │──RDB──▶ │  LOAD RDB    │
│  (fork+COW)  │         │  (blocking)   │
│              │         │              │
│  Ongoing     │─────────▶ Stream cmds  │
│  writes      │ cmds    │  (catch-up)   │
└──────────────┘         └──────────────┘
```

Steps:
1. Replica gửi `PSYNC ? -1`
2. Master gọi `BGSAVE` (background) → tạo RDB snapshot
3. Trong khi `BGSAVE` chạy, master tiếp tục nhận writes → ghi vào **replication backlog**
4. RDB xong → gửi đến replica (disk mode: từ disk; diskless mode: streaming qua socket)
5. Replica load RDB → xóa toàn bộ data cũ → đồng bộ với RDB
6. Tiếp tục apply commands từ replication backlog để catch up

**Cost**:
- `BGSAVE`: tốn CPU, disk I/O (nếu `save` enabled)
- RDB transfer: network bandwidth (等于 dataset size lần đầu)
- Replica OOM risk: nếu replica có ít memory hơn master (xảy ra khi replica đọc replica có bigger dataset)

#### Partial Sync (PSYNC2 — Redis 4+)

```
┌──────────────┐         ┌──────────────┐
│    Master    │         │   Replica    │
│              │         │              │
│  Backlog     │──cmds──▶│  Apply cmds  │
│  (circular)  │ only    │  (catch-up)  │
│              │ missing │              │
└──────────────┘         └──────────────┘
```

Redis 4+ cải tiến từ PSYNC (Redis 2.8) thành PSYNC2:
- Master lưu **2 replication ID**: `replid` (current) và `replid2` (previous after failover)
- Replica lưu `master_repl_offset` (last offset đã nhận)
- Khi replica reconnect, master kiểm tra: offset có trong backlog? → gửi CONTINUE → partial sync
- Khi failover xảy ra và replica nhận new master: old replid được lưu vào `replid2`, partial sync vẫn khả thi nếu new master có shared history

**Khi nào full sync thay vì partial?**

| Trigger | Action |
|---|---|
| Replica cold start (first time) | Full sync |
| `repl-backlog-size` overflow | Full sync (partial sync impossible) |
| Replica gửi wrong `replid` hoặc offset nằm ngoài backlog | Full sync |
| `replication timeout` exceeded | Full sync on reconnect |
| Master restart (nếu không dùng `replica-read-only yes` + Sentinel) | Full sync |

### 4.4. Replication Backlog — Circular Buffer

Replication backlog là **fixed-size circular buffer** (trong memory) trên master, lưu bytes của replication stream để replica có thể partial sync sau khi reconnect. Nó không unbounded: khi vượt `repl-backlog-size`, bytes cũ bị overwrite và replica quá xa phía sau sẽ phải full sync.

```
Replication Backlog (circular buffer, size = repl-backlog-size)
═══════════════════════════════════════════════════════════════

  head (newest command)                                    tail (oldest)
      │                                                         │
      ▼                                                         ▼
  ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
  │ C │ C │ C │ C │ C │ C │ C │ C │ C │ C │ C │ C │ C │ C │   │ ...
  │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │ 9 │10 │11 │12 │13 │14 │   │
  └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
                                                              ▲
                                                      WRAP AROUND
                                                      (old entries
                                                       overwritten)

  master_repl_offset = 14    ← absolute offset of last command
  repl_backlog_histlen = 14  ← how many commands currently in backlog

  Replica gap formula:
    replica_lag = master_repl_offset - slave_repl_offset
               = 14 - 9
               = 5 commands behind
```

**Backlog overflow scenario** (partial sync impossible):

```
Backlog size: 10 commands (example)

T=0:  Commands 1-10 in backlog. Replica at offset 1.
T=1:  Commands 11-15 added. Oldest commands 1-5 overwritten.
T=2:  Replica disconnected at offset 5.
T=3:  Replica reconnects at offset 5.
T=4:  Master backlog starts at command 6 (offset 6).
      Offset 5 is GONE from backlog.
T=5:  Partial sync IMPOSSIBLE → Full sync required!
```

**Sizing formula**:

```
repl-backlog-size = peak_write_rate_cmd/s × avg_command_size_B × max_disconnect_duration_s × safety_margin
```

Ví dụ:
- Peak write: 50K commands/sec
- Avg command size: 500 bytes
- Expected network partition: 60 giây
- Safety margin: 1.2
- Backlog = 50,000 × 500 × 60 × 1.2 = **1,800,000,000 bytes ≈ 1.8 GB**

Thực tế production: **100MB chỉ là baseline nhỏ** cho workload write thấp. Với write-heavy service, tính theo công thức trên; vài trăm MB đến vài GB backlog là bình thường nếu muốn tránh full resync sau partition dài.

**`repl-backlog-ttl`**: thời gian (seconds) backlog được giữ sau khi tất cả replicas disconnect. Mặc định: 3600 (1 giờ). Sau khoảng thời gian này, backlog bị freed (nếu không có replica nào connected). Giá trị hợp lý: `max_reconnect_time × 2`.

### 4.5. Replica Lag — Measurement & Alerting

Replica lag được tính bằng offset difference giữa master và replica:

```
replica_lag = master_repl_offset − slave_repl_offset
           (measured in bytes, NOT seconds)
```

Để convert sang seconds:

```
lag_seconds = replica_lag_bytes / master_write_throughput_Bps
```

Ví dụ:
- `master_repl_offset = 1,234,567`
- `slave_repl_offset = 1,234,000`
- `replica_lag = 567 bytes`
- Master write throughput: 10,000 bytes/sec
- `lag_seconds = 567 / 10,000 = 0.057s ≈ 57ms`

**Monitor bằng `INFO replication`**:

```bash
# Trên replica:
redis-cli INFO replication
# role:slave
# master_repl_offset:1234567
# slave_repl_offset:1234000
# master_last_io_seconds_ago:1  ← giây từ lần cuối replica nhận data từ master
# Lưu ý: `lag` trong dòng `slave0:...lag=1` ở master là seconds kể từ ACK gần nhất,
# không phải offset lag bytes. Offset lag phải tự tính bằng master_repl_offset - slave_repl_offset.

# Trên master:
redis-cli INFO replication
# connected_slaves:3
# slave0:ip=10.0.1.20,port=6380,state=online,offset=1234567,...
# slave1:ip=10.0.1.21,port=6381,state=online,offset=1234560,...
```

**Alert thresholds** (tùy SLA):

| SLA | Replica Lag Threshold | Action |
|---|---|---|
| Real-time (< 100ms) | > 100ms | Alert, fallback to master |
| Near real-time (< 1s) | > 1s | Alert, investigate |
| Background sync (< 10s) | > 10s | Alert, potential full resync |
| Backup-only replica | > 1min | Alert, check backlog |

**Script đo lag thực tế**:

```bash
# Đo replica lag (bytes)
MASTER_OFFSET=$(redis-cli -h master-host -p 6379 INFO replication | grep master_repl_offset | awk -F: '{print $2}')
REPLICA_OFFSET=$(redis-cli INFO replication | grep slave_repl_offset | awk -F: '{print $2}')
LAG_BYTES=$((MASTER_OFFSET - REPLICA_OFFSET))
echo "Replica lag: $LAG_BYTES bytes"
```

### 4.6. Read From Replica — Replica Read-Only Config

Replica mặc định chỉ chấp nhận **read commands** (GET, HGET, LRANGE, v.v.). Write commands bị reject với error `READONLY You can't write against a read only replica`.

**Cấu hình liên quan**:

```txt
# redis.conf hoặc CONFIG SET trên replica:
replica-read-only yes  # default: reject writes on replica
```

`READONLY`/`READWRITE` là command cho Redis Cluster client khi muốn đọc từ replica node trong cluster, không phải cách bật/tắt write trên replica standalone/Sentinel. Với master-replica thông thường, dùng `replica-read-only yes|no`.

**Stale read semantics**:

```
Master: SET key "v1" → SET key "v2" → SET key "v3"
                    ↑         ↑          ↑
                    │         │          │
Replicas receive:  v1        v2         v3
                  └─────────┴──────────┴── timeline
                  lag: 0ms   lag: 50ms   lag: 100ms

T=0ms:    Master has "v3". All replicas have "v3" (in sync).
T=50ms:   Write "v4" on master. Replica-1 lag=50ms → still has "v3".
T=100ms:  Write "v5". Replica-1 still at "v3". Replica-2 at "v4".

READ YOUR WRITES VIOLATED:
  User writes key="v4", immediately reads from replica → gets stale "v3"
```

**Consistency guarantees** (none for async replica reads):

| Property | Master | Replica |
|---|---|---|
| Read-your-writes | ✓ Guaranteed | ✗ Not guaranteed |
| Monotonic reads | ✓ (single node) | ✗ Can jump backward |
| causal consistency | ✓ (single node) | ✗ Not guaranteed |

**Khi nào dùng read-from-replica**:

| Use Case | Stale Acceptable? | Recommendation |
|---|---|---|
| Content feeds, timelines | ✓ Yes (seconds lag OK) | Read from replica |
| User profile (after login) | ✗ No (just wrote) | Read from master |
| Leaderboard, real-time scores | ✗ No | Read from master |
| Analytics, dashboards | ✓ Yes | Read from replica |
| Configuration data | ✗ No | Read from master |
| Rate limiting | ✗ No (must read-your-writes) | Read from master |
| Session store | Conditional | Depends on session TTL vs lag |
| Search results | ✓ Yes (if lag < SLA) | Read from replica |

### 4.7. Consistency Implications — Read-Your-Writes Breakage

**Scenario gây violation**:

1. User A viết `SET user:100:profile {...}` → master
2. Ngay sau đó (trong 50ms), user A đọc từ replica → replica chưa nhận SET
3. User A thấy profile cũ → confusion, potential bug

**Solution patterns**:

**Pattern A — Always read from master for user-specific data**:

```go
// Go: Read-your-writes via master
func GetUserProfile(ctx context.Context, userID string) (*UserProfile, error) {
    // Always read from master for user's own data
    return masterClient.Get(ctx, "user:"+userID+":profile")
}
```

**Pattern B — Session-based routing**:

```go
// TypeScript: Route based on data type
async function getData(key: string, userID: string): Promise<string | null> {
    const isUserOwnData = key.includes(userID) // heuristic
    const client = isUserOwnData ? masterClient : replicaClient
    return client.get(key)
}
```

**Pattern C — Sequence number tracking** (strongest, most complex):

```go
// Go: Track read-your-writes via replication offset
type ReadYourWritesSession struct {
    masterClient *redis.Client
    replicaClient *redis.Client
    lastWriteOffset int64
}

func (s *ReadYourWritesSession) Write(ctx context.Context, key, value string) error {
    err := s.masterClient.Set(ctx, key, value, 0).Err()
    if err != nil {
        return err
    }
    // Get current master offset after write
    info, _ := s.masterClient.Info(ctx, "replication").Result()
    s.lastWriteOffset = parseMasterReplOffset(info)
    return nil
}

func (s *ReadYourWritesSession) Read(ctx context.Context, key string) (string, error) {
    // Loop until replica catches up to write offset
    for {
        info, _ := s.replicaClient.Info(ctx, "replication").Result()
        replicaOffset := parseSlaveReplOffset(info)
        if replicaOffset >= s.lastWriteOffset {
            return s.replicaClient.Get(ctx, key).Result()
        }
        time.Sleep(10 * time.Millisecond)
    }
}
```

**Monotonic reads break scenario**:

```
T=0:   Read X from replica-A → "v1"
T=1:   replica-A lag increases (slow)
T=2:   Read X from replica-B (fast) → "v2" ← jumps forward (OK)
T=3:   Read X from replica-A again → "v1" ← jumps BACKWARD (BROKEN!)
```

Monotonic reads yêu cầu: **sticky routing** — mỗi user session luôn đọc từ cùng một replica.

### 4.8. Diskless Replication

Mặc định, Redis master tạo RDB file trên disk → gửi file đến replica. `repl-diskless-sync` cho phép streaming RDB trực tiếp qua TCP socket, không qua disk.

```
Disk Mode:
  Master BGSAVE → RDB file (disk) → read from disk → send to replica
                 └─ blocking I/O
                 └─ if replica slow → RDB file stays on disk

Diskless Mode:
  Master BGSAVE → RDB stream (memory) → TCP socket → replica
                 └─ no disk I/O
                 └─ faster, no disk space issue
                 └─ if replica disconnects during stream → FULL RESYNC (no RDB on disk to resume)
```

**Configuration**:

```txt
# redis.conf
repl-diskless-sync yes
repl-diskless-sync-delay 5   # seconds to wait for more replicas before starting
```

**Trade-off**:

| Aspect | Disk Mode | Diskless Mode |
|---|---|---|
| Disk I/O | High (save + read) | None during sync |
| Disk space needed | Yes (equal to dataset) | No |
| Resume on replica disconnect | ✓ Yes (RDB on disk) | ✗ No (must full resync) |
| Multiple replica sync | Slower (each reads disk) | Faster (stream once) |
| Best for | Slow network, many replicas | Fast network, few replicas |
| Risk | Disk full during BGSAVE | Replica disconnect → full resync |

**`repl-diskless-sync-delay`**: thời gian master chờ để collect thêm replicas trước khi bắt đầu diskless sync. Nếu có 10 replicas connect nearly simultaneously, delay 5 giây → sync 1 lần thay vì 10 lần. Default: 5 seconds.

### 4.9. Replication ID (`replid` vs `replid2`) & Failover Chain

Mỗi Redis instance có 2 replication IDs:

```
replid:  (41-char hex string) — current replication identity
replid2: (41-char hex string) — previous identity (kept after failover)
```

**Why 2 IDs?**

Khi master failover (promoted replica becomes new master):
1. Old master down
2. Replica-1 promoted to new master
3. Replica-1 gets **new `replid`** (generated)
4. Old `replid` of old master is saved as `replid2` on new master
5. Other replicas that were connected to old master can still partial sync from new master if they share history (via `replid2`)

```
Before failover:
  Master-A: replid=A1, replid2=nil
    └── Replica-1: master_replid=A1
    └── Replica-2: master_replid=A1

After failover (Replica-1 promoted):
  New Master-1: replid=A2 (new), replid2=A1 (old)
    └── Replica-2 reconnects: PSYNC A1 12345
    └── New Master checks: is offset 12345 in backlog of A2?
                          → If A1 history is part of A2's log, CONTINUE
                          → Else FULLRESYNC
```

**Primary replica concept** (Redis 5+): Trong topology có nhiều replica, có thể đánh dấu 1 replica là "primary replica" (dùng `REPLICAOF NO ONE` để promote). Các replicas khác sẽ partial sync từ primary replica thay vì từ master (chained replication — anti-pattern).

### 4.10. WAIT Command — Semi-Sync Acknowledgment

Redis cung cấp `WAIT` để request acknowledgment từ replicas, nhưng **không phải full synchronous replication**:

```txt
SET mykey value
WAIT 1 5000
```

- Arg 1: số lượng replicas cần acknowledge
- Arg 2: timeout milliseconds

```
Semantics:
  WAIT 1 5000 → đợi ít nhất 1 replica acknowledge trong 5000ms
  - If 1+ replicas acknowledge → return số replicas đã ack
  - If timeout → return số replicas đã ack (có thể = 0)

  WAIT 0 0 → không đợi (acknowledgment optional)
  WAIT 3 0 → đợi đến khi có 3 replicas (có thể block forever)
```

**Chú ý quan trọng**: `WAIT` chỉ đảm bảo replicas **đã nhận** command trong buffer, không đảm bảo đã **apply** command. Replica có thể crash sau khi nhận nhưng trước khi apply. `WAIT` không thay thế fsync-based durability.

**Use case**: Tăng durability confidence cho critical operations (financial, order confirmation) mà không cần full sync.

---

## 5. Trade-off Analysis

### Read from Master vs Read from Replica

| Aspect | Read from Master | Read from Replica |
|---|---|---|
| **Consistency** | Read-your-writes guaranteed | Stale data possible |
| **Latency** | Higher under load (single node bottleneck) | Lower (spread across nodes) |
| **Throughput** | Limited by master single-thread | Horizontally scalable reads |
| **Cross-AZ latency** | 1× RTT | + cross-AZ RTT if replica in other AZ |
| **Hot key risk** | High (all reads hit same key on master) | Reduced (spread across replicas) |
| **Best for** | User-specific writes, rate limiting, sessions | Content feeds, analytics, search |
| **SLA** | Requires < 100ms reads | Stale lag < SLA acceptable |

### Async vs Sync Replication

| Aspect | Async (Redis default) | Sync (via WAIT) | True Sync (not in Redis) |
|---|---|---|---|
| **Write latency** | ~1 RTT (local) | ~1 RTT + replica ACK | ~1 RTT + fsync on replica |
| **Durability** | Master down = last N commands lost | Some replicas confirmed | All replicas confirmed |
| **Availability** | High (no blocking) | Medium (WAIT can timeout) | Low (network partition blocks writes) |
| **Throughput** | 100% (unlimited) | Degraded if replicas slow | Severely degraded |
| **Data loss window** | ~1 RTT (worst case) | Reduced to ~ACK time | ~0 (if fsync before ACK) |
| **Use case** | General cache, session | Financial confirmations | Distributed consensus (not Redis) |

### Replica Count vs Write Overhead

| Replica Count | Write Fan-out | Memory Overhead (master) | Network (master egress) |
|---|---|---|---|
| 0 | 0× | 0 | 0 |
| 1 | 1× | Backlog + state | 1× write throughput |
| 2 | 2× | Backlog + state | 2× write throughput |
| 5 | 5× | Backlog + state | 5× write throughput |
| 10 | 10× | Backlog + state | 10× write throughput |

**Network bandwidth formula**:

```
master_egress_bandwidth = write_throughput_ops × avg_command_size × replica_count
```

Ví dụ:
- Write throughput: 10,000 commands/sec
- Avg command size: 500 bytes
- 3 replicas
- Egress = 10,000 × 500 × 3 = **15 MB/s ≈ 120 Mbps**

Cần đảm bảo network interface đủ bandwidth.

### Replication Backlog Size vs Memory

| Backlog Size | Memory Cost | Covers Disconnection | When to Use |
|---|---|---|---|
| 1 MB (default) | ~1 MB | ~10s at 100K ops/s | Development only |
| 10 MB | ~10 MB | ~100s at 100K ops/s | Small production |
| 100 MB | ~100 MB | ~1000s at 100K ops/s | Recommended default |
| 1 GB | ~1 GB | Extreme cases | Large datasets, slow disks |

**Memory overhead on master**:

```
Master memory ≈ dataset_size + repl_backlog_size + client_buffers + overhead
```

Với dataset 10GB và backlog 100MB: overhead chỉ 1%. **Backlog size không phải bottleneck — set it and forget it.**

### Diskless vs Disk-Based Replication

| Aspect | Diskless | Disk-Based |
|---|---|---|
| **Sync speed** | Faster (no disk I/O) | Slower (disk read) |
| **Disk space** | Not needed | Need space = dataset size |
| **Resume capability** | No (if replica disconnects mid-stream) | Yes (RDB on disk) |
| **Master disk load** | None during sync | High (BGSAVE + disk read) |
| **Best for** | Fast network, ephemeral infra | Slow/expensive network, critical replicas |
| **Risk** | Replica drop → full resync | Disk full → replication failure |

---

## 6. Best Solution & Best Practices

### Best Practices Checklist

- [ ] **`repl-backlog-size` = 100MB minimum** (or calculated per workload)
- [ ] Monitor replica lag: `master_repl_offset - slave_repl_offset`, alert at SLA threshold
- [ ] Read from master for write-dependent data (user's own data, rate limiting, sessions)
- [ ] Read from replica for immutable/analytics data (feeds, reports, search)
- [ ] Use `WAIT N TIMEOUT` cho critical writes cần replication confidence
- [ ] Enable `replica-read-only yes` (default) để prevent accidental writes on replica
- [ ] Never use chained replication (master → replica → replica) — use star topology
- [ ] Set `repl-diskless-sync yes` nếu disk I/O là bottleneck
- [ ] Set `repl-diskless-sync-delay 5-10` để batch replica sync requests
- [ ] Alert khi replica lag > SLA × 2 (early warning trước khi breach)
- [ ] Backup replicas nên có `replica-read-only yes` + `save ""` (disable RDB saves, chỉ replicate)
- [ ] Test full resync impact trước production — `BGSAVE` trên master với large dataset

### Scenario-Based Recommendations

**Scenario 1: Cache layer (Redis as L1/L2 cache)**

```
Architecture: 1 master + 2 replicas
Use case: API response cache, 95% reads, 5% writes
Read strategy: Replica reads (stale OK for cache)
Write strategy: Master write-through
Lag threshold: < 2 seconds acceptable
Config:
  repl-backlog-size: 50MB
  replica-read-only: yes
  maxmemory-policy: allkeys-lru
```

**Scenario 2: Session store (user sessions, shopping cart)**

```
Architecture: 1 master + 2 replicas
Use case: User sessions with 30-minute TTL
Read strategy: MASTER for user's own session (read-your-writes critical)
Write strategy: Master write
Lag threshold: < 500ms (TTL is 30 min, lag 500ms negligible)
Anti-pattern: Read-from-replica for user sessions
Config:
  repl-backlog-size: 100MB
  min-replicas-to-write: 1  (sessions must persist)
  min-replicas-max-lag: 5   (seconds)
```

**Scenario 3: Analytics dashboard (read-heavy, stale < 30s OK)**

```
Architecture: 1 master + 3 replicas
Use case: Aggregated metrics, reports
Read strategy: All replicas (`replica-read-only yes`, stale reads acceptable)
Write strategy: Master only
Lag threshold: < 30 seconds acceptable
Config:
  repl-backlog-size: 200MB
  replica-read-only: yes
  appendonly: no  (replicas don't need AOF, saves disk)
```

**Scenario 4: Financial-like idempotency store**

```
Architecture: 1 master + 2 replicas (HA)
Use case: Idempotency keys, deduplication tokens
Read strategy: Master only (must see recent writes)
Write strategy: Master write + WAIT 1 5000
Lag threshold: < 100ms
Config:
  repl-backlog-size: 100MB
  min-replicas-to-write: 1
  min-replicas-max-lag: 1   (seconds — tight constraint)
  appendonly: yes
  appendfsync: everysec
```

### Anti-patterns

1. **Dùng replica làm primary backup storage**: Replica không phải backup — nó là hot standby. Muốn backup → dùng `BGSAVE` trên master hoặc replica đặc biệt với `save ""` (no RDB persistence).
2. **`min-replicas-to-write` mà không set `min-replicas-max-lag`**: `WAIT` command sẽ block forever nếu replica quá chậm.
3. **`repl-backlog-size` bằng default 1MB**: Default quá nhỏ cho production. Full resync storm sẽ xảy ra khi network partition > 10 giây.
4. **Chained replication**: master → replica → replica → replica. Mỗi hop tăng lag và risk of loop. Dùng star topology.
5. **Đọc từ replica mà không monitor lag**: Replica lag có thể tăng âm thầm → stale data mà không ai biết.
6. **Tắt `appendonly` trên replica mà không hiểu impact**: Replica không ghi AOF → nếu replica promoted thành master, durability giảm.

---

## 7. Performance Considerations

### Full Sync Cost

```
Full sync cost = BGSAVE_time + RDB_transfer_time + replica_load_time

Example (50GB dataset, 100 Mbps network):
  BGSAVE time:       ~30-120 seconds (depends on dataset complexity)
  RDB transfer:      50GB / 100 Mbps = ~70 minutes (!)
  RDB transfer:      50GB / 1 Gbps = ~7 minutes
  RDB transfer:      50GB / 10 Gbps = ~40 seconds
  Replica load time: ~10-30 seconds (loading 50GB into memory)

Conclusion:
  - Network is the bottleneck for large datasets
  - Diskless sync helps only if network is faster than disk
  - 10 Gbps network essential for large dataset replication
```

### Replication Stream Throughput

```
Master-to-replica throughput formula:
  available_bandwidth = total_egress - (replication_commands × replica_count)

Example:
  Network: 1 Gbps = 125 MB/s
  Commands: 10K/sec, avg size 500B → 5 MB/s replication stream per replica
  With 3 replicas: 15 MB/s egress for replication
  Remaining for client traffic: 110 MB/s
  Headroom: 110 MB/s - client_traffic << 125 MB/s (safe)
```

### Fork Overhead (BGSAVE)

```
BGSAVE fork() creates child process:
  - Uses copy-on-write (COW) for memory pages
  - Parent process continues serving traffic
  - Child process writes RDB

Overhead:
  - Fork time: ~50-500ms (depends on process size, OS)
  - COW overhead: ~1-5% memory increase during BGSAVE
  - Disk I/O: sequential write of dataset

Dangerous scenario:
  - Dataset: 50GB
  - COW pages: every write during BGSAVE → copy page (~4KB each)
  - Heavy write load during BGSAVE → many COW pages → memory spike
  - Result: OOM on master if memory headroom insufficient

Prevention:
  - Avoid write bursts during BGSAVE windows
  - Use `BGSAVE` scheduling (e.g., every 1-6 hours during low traffic)
  - Use diskless replication to eliminate disk I/O
```

### Partial Sync Cost

```
Partial sync cost = (offset_distance × avg_command_size) + network_latency

Example:
  Offset distance: 1000 commands
  Avg command size: 500 bytes
  Network RTT: 1ms
  Transfer: 1000 × 500B = 500KB
  Time: 500KB / 1 Gbps + 1ms RTT ≈ 5ms + 1ms = 6ms

Partial sync is orders of magnitude faster than full sync.
```

### Replica Lag Impact on Throughput

```
At what write rate does replica lag become problematic?

lag_seconds = backlog_bytes / (write_rate × avg_cmd_size)

Rearranging:
  max_write_rate_for_lag_threshold =
    backlog_bytes / (lag_threshold_seconds × avg_cmd_size)

Example:
  backlog = 100 MB = 104,857,600 bytes
  lag_threshold = 1 second
  avg_cmd_size = 500 bytes
  max_write_rate = 104,857,600 / (1 × 500) = 209,715 commands/sec

At 209,715 commands/sec, backlog maintains 1-second lag.
  Below this: lag < 1 second
  Above this: lag grows, backlog fills up
```

---

## 8. Production Failure Modes

### 8.1. Replica Desync — Lag Growing Without Alert

```
Symptom: replica_lag tăng dần, không có alert, đến khi breach SLA mới phát hiện
Cause:
  - Write spike vượt bandwidth capacity
  - Slow replica (CPU-bound, I/O-bound, or network-constrained)
  - Big command (e.g., LPUSH with 100K items) blocking replication stream
Detection:
  - Alert: replica_lag > SLA_threshold sustained > 30 seconds
  - Monitor: replication_bytes_per_second metric
Fix:
  1. Identify slow replica: INFO commandstats on replica
  2. Check network: iperf3 between master and replica
  3. If big command: split into smaller chunks
  4. If bandwidth saturated: reduce replica count or upgrade network
  5. If replica hardware constrained: upgrade or redistribute
Prevention:
  - Capacity test: simulate peak write rate + measure lag
  - Alert at 50% of SLA threshold
  - Separate replication network from client traffic network
```

### 8.2. Full Resync Storm

```
Symptom: Multiple replicas trigger full sync simultaneously → master OOM or unresponsive
Cause:
  - Network partition heals, all replicas reconnect at same time
  - repl-backlog-size too small → all partial sync attempts fail
  - Master restart → all replicas require full sync
Timeline:
  T=0: Network partition (30s)
  T=30: Network heals, 5 replicas reconnect simultaneously
  T=30: All replicas send PSYNC with old offset
  T=30: Master backlog doesn't have old offset → FULLRESYNC for all
  T=30: Master starts 5 concurrent BGSAVE or 5 diskless streams
  T=30+: Master CPU/disk/network spike → clients experience latency
  T=60+: Master recovers
Prevention:
  - repl-backlog-size ≥ peak_write_rate × max_partition_duration × 1.5
  - Staggered replica reconnection (use replica-priority in Sentinel)
  - Set repl-diskless-sync-delay to batch sync requests
  - Test: simulate network partition and measure recovery behavior
```

### 8.3. Backlog Overflow → Forced Full Sync

```
Symptom: Periodic full resyncs even without network partition
Cause:
  - repl-backlog-size too small for sustained write rate
  - A single replica consistently slower than write rate
  - Write burst > backlog size
Detection:
  - Alert on: "fullsync" in master logs
  - Monitor: INFO replication → look for "fullsync" counter
Fix:
  1. Increase repl-backlog-size: repl-backlog-size 104857600 (100MB)
  2. Identify slow replica: check replica's commandstats
  3. If replica hardware constrained: upgrade or replace
Prevention:
  - Calculate backlog based on write rate, not dataset size
  - Budget: backlog_size = write_rate × max_allowed_lag × 1.2
  - Default repl-backlog-size in production: 100MB minimum
```

### 8.4. Replica Memory Blow-up

```
Symptom: Replica uses more memory than master, eventually OOM
Cause:
  - Replica loaded with full dataset + replication buffer + client buffers
  - Big key on master (500MB) replicated as single item
  - Replica has less memory than master (misprovisioned)
  - COW overhead during replica's internal reorganization
Detection:
  - Monitor replica used_memory vs master used_memory
  - Alert: replica_memory > 80% of master_memory
Fix:
  1. Ensure replica has same or more memory than master
  2. If big keys: split them before replication (e.g., hash slotting)
  3. For read-heavy: use replica with read-only workloads
  4. If OOM: reduce replica count or use replication to a larger instance
Prevention:
  - Provision replicas with 1.2× master memory (headroom for COW)
  - Test with BGSAVE on master and monitor replica memory spike
```

### 8.5. Read-Your-Writes Inconsistency (Silent Data Loss)

```
Symptom: User writes data, immediately reads, gets old data
Cause:
  - Application reads from replica immediately after write to master
  - Replica lag is non-zero (always in async replication)
  - This is expected behavior, not a bug — but teams don't expect it
Detection:
  - Hard to detect — it happens, is fixed by next read
  - Only visible in logs if you track read-after-write patterns
  - User complaints: "I just updated my profile, why do I see old data?"
Fix:
  1. Read from master for user-owned data
  2. Implement sticky routing (same user → same replica)
  3. Use WAIT for critical writes + read from master until WAIT returns
  4. Add "last modified timestamp" to data and check freshness
Prevention:
  - Document which data types are read-from-replica vs read-from-master
  - Add consistency checks in application: read-after-write verification
  - Set strict replica lag SLO and alert on breach
```

### 8.6. Replication Loop After Failover

```
Symptom: CPU spike on master after failover, replication traffic loop
Cause:
  - Chained replication (master → replica → replica)
  - After failover, replica tries to replicate to its downstream replica
  - Downstream replica's "master" is now a peer, not a master
  - Commands loop between nodes
Detection:
  - Redis logs: "Connection reset by peer" repeatedly
  - Network traffic: unusually high replication egress
  - CPU: one core at 100% (replication loop consuming CPU)
Fix:
  1. IMMEDIATE: REPLICAOF NO ONE on the loop endpoint
  2. Reconfigure all replicas to point to new master
  3. Verify with INFO replication
Prevention:
  - Never use chained replication (star topology only)
  - Use Redis Sentinel/Cluster to manage topology automatically
  - After failover: verify all replicas' "master_link_status" = "connected"
```

### 8.7. Slow Replica Causing WAIT Timeout

```
Symptom: WRITE commands timeout when using WAIT, even with replicas online
Cause:
  - Replica nhận replication stream chậm hơn write rate hoặc network RTT tăng
  - `WAIT N timeout` yêu cầu nhiều ACK hơn số replica healthy trong timeout
  - Application interprets WAIT timeout as write failure
Detection:
  - WAIT command returns < N acknowledgments
  - Logs: "N replica acknowledged, required M"
Fix:
  1. Tăng timeout của `WAIT` theo p99 replication ACK latency thực tế
  2. Giảm số ACK yêu cầu nếu use case không cần strict durability
  3. Identify slow replica: check replication delay
  4. If replica hardware-constrained: upgrade or reduce replica count
  5. If write burst: rate-limit writes or increase backlog
Prevention:
  - Test WAIT behavior under peak load before production
  - Set WAIT timeout = 2× p99 replica ACK latency under normal load
  - Have fallback: if WAIT returns < N, log warning but don't fail write
```

---

## 9. Real-world Examples

### GitHub: Redis Backed by Replicas for Sharding

GitHub từng sử dụng Redis với hàng trăm replicas để serve read traffic. Mỗi master có 3-5 replicas spread across datacenters. Read traffic đọc từ nearest replica. Problem: khi thực hiện major DB migration (renaming keys), migration script phải disable replica read để đảm bảo consistency, gây load spike trên master.

GitHub đã viết blog chi tiết về cách họ dùng Redis replication để scale read và giải quyết hot key problem. Key insight: **sharding by key prefix** (vd: `github:issues:{id}`) để spread reads across replica sets.

### Twitter/X: Timeline Caching with Replica Lag Budget

Twitter/X dùng Redis cluster với replica read cho timeline caching. User timeline là read-heavy (95% reads, 5% writes). Mỗi tweet write → master, timeline reads → replica. Acceptable lag: 30-60 giây (user won't notice timeline being 30 seconds behind). Strategy: timeline data có TTL ngắn (5 phút), staleness acceptable within TTL budget.

Khi một celebrity tweet (hot key), write rate tăng vọt → replica lag spike. Twitter giải quyết bằng: **degrade gracefully** — temporarily read from master for trending hashtags, then switch back.

### Shopify: Redis Replication for Zero-Downtime Failover

Shopify chạy Redis as service for merchants (Redis Cloud). Multi-AZ replication với Sentinel tự động promote replica khi master fails. Critical lesson: **backlog sizing for peak traffic**. Trong Black Friday/Cyber Monday (BFCM), write rate tăng 10-50×. Nếu backlog chỉ có 10MB, partition 30 giây → full resync. Shopify set `repl-backlog-size = 1GB` và test failover under BFCM load simulation.

### Stack Exchange: "It's Always DNS" Incident

Stack Exchange (operator of Stack Overflow) gặp incident nổi tiếng: Redis master down, replica promoted. Clients không detect promotion kịp → tiếp tục write đến old master. Sau khi DNS cache expire, clients redirect đến new master. Nhưng một số client có DNS cache stale lâu → write đến wrong node → data inconsistency.

**Lesson**: Client-side discovery (Sentinel/Cluster SDK) cần short DNS TTL + retry logic. Static IP configuration for Redis nodes is a recipe for disaster.

### Discord: Redis at Scale for Presence

Discord dùng Redis replication để store user presence (online/offline/idle). Khi user goes online → write to master → replicas propagate → friends see online status. Lag budget: < 1 giây. Nếu replica lag > 1s, Discord fallback to master read (accepting higher load). Presence data là **soft consistency** — user might appear online 1 second late, acceptable.

---

## 10. Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Read from replica + write-your-reads data | User sees stale data after write | Route write-dependent reads to master |
| `repl-backlog-size` default 1MB | Full resync storm after any partition | Set to 100MB+ or calculate per workload |
| `min-replicas-to-write` without `min-replicas-max-lag` | Writes block forever if replica slow | Always set both together |
| Chained replication (A → B → C) | Replication loop after failover | Use star topology (A → B, A → C) |
| Replica promoted but clients not redirected | Split-brain writes | Use Sentinel/Cluster for automatic redirect |
| Replica memory < master memory | Replica OOM during sync | Provision replica with 1.2× master memory |
| Using replica as backup | Data loss on replica corruption | Use `BGSAVE` snapshot on replica with `save ""` disabled |
| No monitoring on replica lag | Silent staleness growing | Alert on `replica_lag_bytes > threshold` |
| Big key causing slow replication | Single command takes minutes to replicate | Split big keys; monitor `commandstats` |
| Network bandwidth not calculated | Replication starves client traffic | Measure and provision separate network if needed |
| `appendonly no` on promoted master | Reduced durability after failover | Always AOF on master; replicas can be RDB-only |

---

## 11. Câu hỏi tự kiểm tra

### Câu 1: Backlog Sizing Calculation

Hệ thống của bạn có peak write rate 20,000 commands/sec, avg command size 600 bytes. SLA yêu cầu replica lag < 2 giây. Network partition dự kiến có thể kéo dài tối đa 5 phút (300 giây). Tính `repl-backlog-size` tối thiểu. Giải thích.

> **Đáp án**:
>
> - Backlog cần cover cả lag threshold (2s) và partition duration (300s), lấy cái lớn hơn
> - Lag SLA: `20,000 × 600 × 2 = 24,000,000 bytes ≈ 24 MB`
> - Partition window: `20,000 × 600 × 300 × 1.5 = 5,400,000,000 bytes ≈ 5.4 GB`
> - **Recommendation**: `repl-backlog-size 6442450944` (6 GB) nếu thật sự muốn partial sync sau partition 5 phút ở peak write.
> - Lesson: backlog sizing dựa trên write_rate × avg command size × time_window, không phải dataset size.

### Câu 2: Full Sync vs Partial Sync Trigger

Khi nào replica sẽ yêu cầu full sync thay vì partial sync? Liệt kê ít nhất 3 scenarios.

> **Đáp án**:
> 1. Replica cold start (first time connecting) — không có replid/offset
> 2. Replica gửi offset nằm ngoài backlog buffer — backlog đã overwrite offset đó
> 3. Replica gửi wrong `replid` (không match master `replid` hoặc `replid2`)
> 4. `replication timeout` exceeded (replica disconnected too long)
> 5. Master restart (nếu không có Sentinel quản lý)
> 6. Backlog bị freed do `repl-backlog-ttl` expired và replica reconnect

### Câu 3: Read-Your-Writes Violation

Một user profile service đọc từ replica. User A cập nhật display name trên master. Ngay sau đó, User A đọc profile từ replica. Giải thích kết quả và đề xuất fix.

> **Đáp án**:
>
> **Result**: User A có thể đọc được **old display name** (stale read). Async replication có lag tự nhiên 10-100ms+.
>
> **Fix options**:
>
> 1. **Read from master for user-owned data**: Profile là user-owned data → read từ master
> 2. **Sequence number tracking**: Sau write, poll replica cho đến khi `slave_repl_offset >= write_offset`
> 3. **Write-through cache invalidation**: Sau write trên master, `DEL` cache key → next read from master
> 4. **Monotonic read routing**: Mỗi user session sticky đến 1 replica, nhưng vẫn có thể stale
>
> **Never acceptable for**: authentication, authorization, financial operations, inventory
> **Acceptable for**: immutable content (blog posts, product catalog), analytics

### Câu 4: WAIT Command Semantics

Giải thích output của các lệnh sau. Trong scenario nào `WAIT` không đảm bảo durability thực sự?

```txt
SET order:123 status "confirmed"
WAIT 1 5000
```

```txt
WAIT 0 0
```

> **Đáp án**:
>
> `WAIT 1 5000`:
> - Đợi ít nhất 1 replica acknowledge trong 5000ms
> - Return: số replicas đã ack (1 hoặc 0 nếu timeout)
> - Nếu timeout: write vẫn thành công trên master, nhưng có 0 ack
>
> `WAIT 0 0`:
> - Không đợi bất kỳ replica nào (fire-and-forget)
> - Return: 0 (luôn luôn)
>
> **WAIT không đảm bảo durability thực sự** khi:
> - Replica nhận command nhưng chưa apply (replica crash trước khi apply → data lost)
> - Replica dùng `appendfsync no` (command buffered, not synced to disk)
> - Network partition sau ACK nhưng trước disk sync
>
> WAIT chỉ đảm bảo replication stream acknowledgment, không phải fsync-based durability.

### Câu 5: Diskless Replication Risk

Bạn enable `repl-diskless-sync yes` trên master có 3 replicas. Một replica bị network issue và disconnect giữa chừng khi đang nhận RDB stream. Điều gì xảy ra? Làm thế nào để mitigate?

> **Đáp án**:
>
> **Xảy ra**:
> - Replica disconnect mid-stream
> - Master không có RDB file trên disk (diskless mode)
> - 2 replicas còn lại tiếp tục sync
> - Disconnected replica reconnect → gửi `PSYNC` với old offset
> - Master backlog có offset đó? Nếu có → partial sync. Nếu backlog đã overwrite → **full resync**
>
> **Mitigation**:
> 1. Đặt `repl-diskless-sync-delay 5-10` để batch replicas trước khi sync → giảm chance of mid-sync disconnect
> 2. Đảm bảo network ổn định (dedicated replication network)
> 3. Hoặc quay về disk-based sync nếu reliability > speed: `repl-diskless-sync no`
> 4. Monitor: alert khi fullsync count tăng → có replica bị disconnect/slow

### Câu 6: Chained Replication Bug

Team setup: master → replica1 → replica2 (chained). replica1 promoted to master. Chuyện gì xảy ra với replica2?

> **Đáp án**:
>
> **Sau failover**:
> - replica1 promoted → `REPLICAOF NO ONE` → becomes new master
> - replica2 vẫn nghĩ replica1 là master của nó
> - replica2 gửi replication stream đến replica1 (giờ là master)
> - replica1 gửi commands đến replica2
> - replica2 có thể gửi lại commands đến replica1 → **replication loop**
>
> **Result**:
> - CPU spike on both nodes
> - Memory spike (commands queued in both directions)
> - Eventually OOM or max connection limit
>
> **Fix**:
> - Ngay sau failover: `REPLICAOF new-master 6379` trên tất cả replicas
> - Dùng Sentinel/Cluster để tự động redirect replicas
> - Không bao giờ dùng chained replication trong production

### Câu 7: Memory Estimation with Replicas

Bạn có master với dataset 8GB RAM. Muốn add 2 replicas (read scale). RAM estimation cho infrastructure team?

> **Đáp án**:
>
> ```
> Per-replica memory:
>   Data:              8 GB     (full dataset copy)
>   Replication buf:   0.1 GB  (replication stream buffer)
>   COW overhead:      0.5 GB  (1.2× headroom for fork/COW)
>   Client buffers:   0.05 GB (connected clients)
>   OS overhead:       0.1 GB  (kernel buffers, stack)
>   ─────────────────────────────────────────────────
>   Total per replica:  ~8.8 GB
>
> Infrastructure recommendation:
>   - Master:  12 GB RAM (8 GB data + 4 GB headroom)
>   - Replica: 12 GB RAM each (8.8 GB estimated + 3.2 GB headroom)
>
> For 2 replicas + 1 master:
>   Total Redis memory: ~36 GB
>
> Note: COW overhead only significant during BGSAVE.
>       With diskless replication: COW overhead is minimal.
> ```
