# Day 28: Distributed Locking & Coordination

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Implement được safe distributed lock bằng `SET NX PX` + token + Lua script — hiểu chính xác từng thành phần và tại sao mỗi phần tử là bắt buộc.
- Phân tích được Redlock algorithm: quorum, clock drift, retry strategy, và tại sao Martin Kleppmann phản đối nó trong các scenario cụ thể.
- Hiểu được fencing token (Lamport clock hoặc monotonic counter) và tại sao lock không đủ để đảm bảo correctness trong tất cả use cases.
- Quyết định được khi nào Redis lock là safe, khi nào cần ZooKeeper/etcd/Consul, và khi nào dùng idempotency hoặc queue-based serialization thay vì lock.
- So sánh được Redis lock vs DB lock, Redlock vs single Redis lock, lock vs idempotency, lock vs queue-based serialization.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: Safe unlock bug giết production 3 giờ — mất 12K USD inventory

Một team implement distributed lock cho payment processing:

```
# Lock acquisition
SET payment:lock:order123 <client_id> NX PX 30000

# Unlock (BUG: unsafe!)
DEL payment:lock:order123
```

Giả sử:
1. Client A acquire lock cho order123 (token A)
2. Client A crash sau khi acquire nhưng chưa xử lý xong
3. Lock tự expire sau 30 giây
4. Client B acquire lock (token B, cùng key)
5. Client A "hồi sinh", gọi `DEL payment:lock:order123`
6. **Client B mất lock giữa chừng** — Client B đang xử lý payment nhưng lock đã bị xóa bởi A
7. Client C acquire lock, process order 123 lần 2

Kết quả: **double payment, 12K USD**. Root cause: DEL không kiểm tra token, xóa lock của bất kỳ ai đang giữ.

### Incident 2: Redlock trên 5 nodes — clock drift làm lock không đáng tin

Một team dùng Redlock trên 5 Redis instances geographic distribution (Singapore, Tokyo, Sydney, US-West, EU-Central). Quorum = 3.

```
Client A:
  - SET on SG: OK   (t1=0ms)
  - SET on TK: OK   (t2=5ms)
  - SET on SY: OK   (t3=20ms)
  - Quorum achieved in 20ms
  - Lock TTL = 10s
  - Operation starts at t=20ms

Client B (concurrent):
  - SET on US: OK   (t1=0ms)
  - SET on EU: OK   (t2=3ms)
  - SET on TK: OK   (t3=8ms)
  - Quorum achieved in 8ms
  - Lock TTL = 10s
  - Operation starts at t=8ms

Result: Client B acquires lock BEFORE A (t=8ms < t=20ms)
        But A started its operation at t=20ms thinking it held the lock!
        A và B cùng access shared resource.
```

Nguyên nhân: Redlock không đảm bảo linearizability. Clock drift giữa các nodes (thậm chí 10-50ms NTP offset) có thể khiến 2 clients cùng tin rằng mình hold lock.

### Incident 3: Lock cho financial transaction — wrong tool for the job

Một payment service dùng Redis lock để serialize debit operations:

```
SET finance:lock:account123 <token> NX PX 5000
# ... debit 1000 USD ...
DEL finance:lock:account123
```

Vấn đề: Redis lock không có fencing token. Nếu operation mất > 5 giây (DB call chậm), lock expire, client khác acquire lock và debit cùng account. Khi client A hoàn thành operation, nó không biết lock đã expire. Double debit xảy ra.

Giải pháp đúng: Database serializable transaction hoặc ZooKeeper với fencing token.

**Bottom line**: Distributed lock là một trong những concept dễ hiểu sai nhất trong distributed systems. SET NX PX trông đơn giản nhưng safe lock production-ready đòi hỏi token + Lua + careful TTL + fencing token + understanding khi nào lock không phải tool phù hợp.

---

## 3. Kiến thức nền cần có

- Redis single-threaded model và event loop (Day 1)
- Lua scripting (Day 16) — đặc biệt `redis.call` và atomic execution model
- TTL và key expiration (Day 4, Day 8)
- WATCH + MULTI/EXEC (Day 15) — hiểu Redis không có rollback
- Redis Cluster và cross-slot limitation (Day 22)
- Retry strategy và exponential backoff (Day 12)

---

## 4. Lý thuyết chi tiết

### 4.1. First Principles: Lock là gì và tại sao cần nó trong distributed system

Trong single-process system, mutex lock giải quyết race condition vì OS kernel đảm bảo atomicity của test-and-set instruction. Trong distributed system, không có shared memory — mỗi node có RAM riêng. Để serialize access vào shared resource, cần một **shared coordination primitive**.

```
Single Process (single machine):
  Thread A:  [ read x ] [ x = x - 100 ] [ write x ]
              ^ OS guarantees atomicity via kernel lock
              ^
  Thread B:  [ read x ] [ x = x - 50  ] [ write x ]
              ^ blocks until A finishes with x

Distributed System (multiple machines):
  Node A:  [ read x from DB ] [ x = x - 100 ] [ write x to DB ]
  Node B:  [ read x from DB ] [ x = x - 50  ] [ write x to DB ]
           ^ No OS to block. Both read x=1000, both write x=900
           ^ Need coordination via external lock service

  Solution: Shared lock service (Redis, ZooKeeper, etcd)
    Node A:  SET lock NX PX 30000  -> OK
    Node B:  SET lock NX PX 30000  -> nil (lock held)
    Node A:  [ process critical section ]
    Node A:  DEL lock
```

### 4.2. SET NX PX — Cơ chế acquisition

`SET key value NX PX milliseconds` là atomic single command kết hợp 3 thành phần:

```
SET lock:resource <token> NX PX 30000

Phân tích:
  - SET: ghi giá trị
  - NX (Not eXists): chỉ set nếu key không tồn tại
  - PX milliseconds: set TTL = 30000ms

Return values:
  - OK           -> lock acquired
  - nil          -> lock already held by another client
```

```
Timeline — Lock Acquisition

Client A                          Redis
  |                                  |
  |--- SET lock NX PX 30000 ------->|
  |    [key does not exist]          |
  |<-- OK ---------------------------|
  |    [lock held for 30s]           |

Client B                          Redis
  |                                  |
  |--- SET lock NX PX 30000 ------->|
  |    [key already exists]          |
  |<-- nil --------------------------|
  |    [lock not acquired]           |
```

**Tại sao không dùng SETNX + EXPIRE riêng?**

```
# WRONG approach (2 commands — NOT atomic!)
SETNX lock:resource token     -- returns 1 if acquired
EXPIRE lock:resource 30      -- set TTL

Race condition window:
  1. Client A: SETNX -> 1 (acquired)
  2. Client A crashes BEFORE EXPIRE runs
  3. Lock key has NO TTL
  4. Deadlock: lock never expires, no one can acquire

# RIGHT approach (1 command — atomic)
SET lock:resource token NX PX 30000

Atomic: SET + NX + PX executed as one operation.
        No window between acquisition and TTL setting.
```

### 4.3. Lock Token — Tại sao cần và làm sao generate

**Problem**: Lock key có TTL. Khi lock expire, bất kỳ client nào cũng có thể acquire. Nhưng nếu client cũ chưa finish operation?

```
Client A:
  t=0ms:    Acquire lock (TTL=10s)
  t=8s:     Lock auto-expires (TTL reached)
  t=8.1s:   Client B acquires lock
  t=9s:     Client A finishes operation (thinking it still held lock)

Result: Client A operated on shared resource AFTER lock expired.
        Client B was also operating at the same time.
```

**Giải pháp**: Lock token (còn gọi là lock value, unique identifier). Mỗi client tạo một token unique (UUID, random bytes) khi acquire. Token được lưu trong lock value.

```
Client A:
  token_A = uuid()  # e.g., "550e8400-e29b-41d4-a716-446655440000"
  SET lock:resource token_A NX PX 30000

Client B:
  token_B = uuid()  # e.g., "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
  SET lock:resource token_B NX PX 30000  -> nil (A holds)

Unlock Client A:
  # WRONG: DEL lock:resource
  # RIGHT: chỉ xóa nếu token match

  # But: GET and DEL are 2 separate commands!
  # Solution: Lua script (atomic check-and-delete)
```

### 4.4. Safe Unlock bằng Lua — Atomic Check-and-Delete

```lua
-- Safe unlock script
-- KEYS[1] = lock key
-- ARGV[1] = lock token (client's token)

local token = redis.call('GET', KEYS[1])
if token == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
```

```
Tại sao Lua atomic?

Redis event loop:
  [GET token] -> [compare] -> [DEL]
  |___________________________________|
        Single atomic step
        No other command can run in between

Nếu dùng 2 commands riêng:
  1. GET lock:resource     -> token_A
  2. Client B acquires lock (token_B)  <- THIS CAN HAPPEN!
  3. DEL lock:resource     -> Deletes B's lock!

Lua prevents this by being atomic.
```

### 4.5. Complete Lock Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│              SAFE DISTRIBUTED LOCK LIFECYCLE                     │
│                                                                  │
│  1. ACQUIRE                                                     │
│     token = UUID.randomUUID()                                    │
│     result = SET lock:resource token NX PX 30000                │
│     if result == OK:                                            │
│         # Lock acquired                                          │
│         go do_critical_section(token)                           │
│                                                                  │
│  2. EXTEND (optional, for long operations)                       │
│     # Check token still ours, extend TTL                         │
│     Lua: if GET == token then EXPIRE new_ttl else 0             │
│                                                                  │
│  3. RELEASE (on success, failure, or timeout)                   │
│     Lua: if GET == token then DEL else skip                     │
│                                                                  │
│  4. CRASH HANDLING                                              │
│     # Lock auto-expires after TTL (30s)                         │
│     # No manual cleanup needed                                   │
│     # But: operations in progress may overlap with new owner     │
│                                                                  │
│  5. FENCING (for resources requiring correctness)               │
│     # After acquiring lock, increment fencing token from storage │
│     # Pass fencing token with each resource operation            │
│     # Resource checks: if fencing_token < last_seen: REJECT      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.6. Lock Extension (TTL Renegotiation)

Nếu critical section cần thời gian không xác định, có thể extend lock:

```lua
-- Extend lock TTL (only if we still own it)
-- KEYS[1] = lock key
-- ARGV[1] = token
-- ARGV[2] = new TTL in seconds

local current = redis.call('GET', KEYS[1])
if current == ARGV[1] then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 1
end
return 0
```

```
Caveat: Extension không phải là magic bullet.
  - Nếu operation mất quá lâu (ví dụ: > lock TTL * N),
    có thể lock bị expire giữa chừng
  - Tốt hơn: thiết kế operation để fit trong TTL
  - Hoặc: break long operation thành nhiều bước nhỏ
```

### 4.7. Redlock Algorithm

**Purpose**: Giảm risk của single Redis failure bằng cách acquire lock trên nhiều independent Redis instances.

**Algorithm** (5 nodes):

```
Client A wants lock on resource "order123"

Phase 1: Acquisition
  1. Get current time in ms (t1)
  2. Try SET on N independent Redis nodes sequentially:
       For i = 1 to 5:
         SET lock:order123 token_A NX PX 30000
         If OK: increment success count
  3. Get current time again (t2)
  4. Calculate elapsed: elapsed = t2 - t1

Phase 2: Validation
  5. Lock is valid only if:
       - success_count >= (N/2 + 1) = 3/5 quorum
       - AND elapsed < TTL
       - AND elapsed < (TTL - drift)
     Where drift = lock_validity_time * clock_drift_factor + ms_to_send_command

Phase 3: Release (on all nodes)
  For i = 1 to 5:
    Lua: if GET == token then DEL
```

```
Timeline — Redlock Acquisition

Node 1 (SG):  t=5ms   SET OK
Node 2 (TK):  t=12ms  SET OK
Node 3 (SY):  t=25ms  SET OK   <- quorum=3 achieved
Node 4 (US):  t=40ms  SET OK   <- more success but we already have quorum
Node 5 (EU):  t=55ms  SET OK

Total elapsed = 55ms
TTL = 10000ms (10s)
Valid = (elapsed < TTL) AND (success >= 3) -> TRUE

Clock drift factor: 0.01 (1% of TTL)
Drift = (TTL - elapsed) * 0.01 + msg_latency
     = (10000 - 55) * 0.01 + ~20ms = ~119ms

Lock validity = TTL - elapsed - drift = 10000 - 55 - 119 = 9826ms
```

### 4.8. Martin Kleppmann's Redlock Criticism

Năm 2016, Martin Kleppmann (tác giả "Designing Data-Intensive Applications") công bố phân tích chi tiết về Redlock. Tóm tắt các điểm chính:

**Criticism 1: Clock Drift và Non-Linearizable Execution**

Redlock giả định các Redis nodes có synchronized clocks. Nhưng:

```
Scenario:
  Node 1 (SG): clock runs fast, TTL expires 100ms early
  Node 2 (TK): clock runs slow, TTL still valid
  Node 3 (SY): clock accurate

Client A acquired lock on 3 nodes at t=0 (local time)
Lock TTL = 10s

Due to clock drift:
  - Node 1 TTL expires at t=9900ms (100ms early)
  - Node 2 TTL expires at t=10100ms (100ms late)
  - Node 3 TTL expires at t=10000ms (accurate)

At t=9900ms: Node 1 lock expires
At t=9910ms: Client B tries to acquire lock
  - SET on Node 1: OK (expired)
  - SET on Node 2: nil (still held)
  - SET on Node 3: nil (still held)
  - Quorum = 1 (not enough for Redlock)

So far OK. But if message to Node 2 is delayed 200ms:
  - At t=10000ms: Node 2 receives B's SET NX request
  - But Node 3 hasn't heard from A in a while...
  - This gets complex with partial failures
```

**Criticism 2: No Fencing Token**

Redlock không cung cấp fencing token. Nếu lock holder crash sau khi acquire nhưng trước khi hoàn thành operation, và lock auto-expires, new holder có thể overlap với old holder's operation.

```
Client A:
  t=0ms:     Acquire lock (valid for 10s)
  t=100ms:   Read data from DB (x = 100)
  t=200ms:   Compute new value (x = x - 100 = 0)
  t=8s:      Crash (network partition)

  Lock expires at t=10s

Client B:
  t=10s:     Acquire lock
  t=10.1s:   Read data from DB (x = 0, stale!)
  t=10.2s:   Compute new value (x = x - 50 = -50)
  t=10.3s:   Write x = -50

Client A (before crash):
  t=8.5s:    Write x = 0  <- overwrites B's write!

Both A and B thought they had exclusive access.
Fencing token (sequence number from linearizable store)
prevents this: B's token < A's token, resource rejects B's write.
```

**Criticism 3: Lock Validity Time là Approximation**

Trong Redlock, lock validity time = TTL - elapsed - drift. Đây là approximation, không phải guarantee. Với network latency variation (p95 vs p99 có thể chênh 10x), drift calculation có thể inaccurate.

**Criticism 4: Single-host clock rollback**

Redlock giả định `CLOCK` command trả về monotonic time. Nhưng virtual machines và cloud environments có clockrollback khi NTP sync hoặc VM migration. Redis không có wall clock monotonicity guarantee.

### 4.9. Fencing Token — Giải pháp cho Correctness

Fencing token là một monotonic counter tăng mỗi khi lock được acquire. Mọi operation trên shared resource phải kèm token, và resource service từ chối operation nếu token <= last seen token.

```
Sequence với Fencing Token:

Lock Service (Redis, ZooKeeper, etcd):
  - Maintain monotonic counter per resource
  - Return token on lock acquisition
  - Token must be linearizable

Client A:                    Token Service           Shared Resource (DB)
  |                               |                         |
  |-- Acquire lock -------------->|                         |
  |<-- Token #42 (fencing) ------|                         |
  |                               |                         |
  |-- Process, include token=42 -->|                         |
  |                               |  if token > last_token: |
  |                               |    last_token = 42     |
  |                               |    accept operation     |
  |<-- Success -------------------|                         |
  |                               |                         |
  A crashes                       |                         |
  Lock expires                    |                         |
                                 |                         |
Client B:                        |                         |
  |-- Acquire lock -------------->|                         |
  |<-- Token #43 (fencing) ------|                         |
  |                               |                         |
  |-- Process, include token=43 -->|                        |
  |                               |  token 43 > 42: OK      |
  |                               |  accept operation       |
```

**Redis không có built-in fencing token service.** Để implement fencing token với Redis, cần một linearizable store riêng (ZooKeeper, etcd) hoặc dùng database với `SELECT FOR UPDATE`.

### 4.10. Khi nào Redis Lock AN TOÀN

Redis lock an toàn khi:

1. **Operation là idempotent**: Nếu operation chạy 2 lần với cùng input, kết quả giống nhau. Lock chỉ để prevent duplicate execution, không phải correctness.

   Ví dụ: Gửi notification email, writing to idempotency-key-protected endpoint.

2. **TTL >> operation duration + clock_drift**: Nếu operation 100ms nhưng lock TTL = 30s, lock expiry trong operation không xảy ra (với margin an toàn).

   ```
   Safe: operation_duration + max_retry_time + clock_drift < TTL * 0.5
   Example: op=500ms, max_retry=1s, drift=100ms -> TTL >= 3.2s -> use 10s
   ```

3. **Single Redis instance đủ**: Không cần Redlock. Single Redis với `SET NX PX` an toàn hơn Redlock vì không có cross-node clock drift issue.

4. **Accept eventual overlap acceptable**: Nếu 2 clients overlap trong 100ms và điều này chấp nhận được cho business logic.

5. **Lock không làm source of truth**: Redis lock chỉ là coordination mechanism, không phải data store.

### 4.11. Khi nào KHÔNG nên dùng Redis Lock

1. **Financial transactions, double-entry bookkeeping**: Cần linearizability. Redis không đảm bảo.

2. **Multi-resource locking (A + B must be locked together)**: Redis lock chỉ lock một key. Multi-resource lock với Redis = multiple locks = deadlock risk. Dùng ZooKeeper sequential node hoặc etcd transaction.

3. **Long-running operations**: Lock TTL quá rủi ro. Dùng queue-based serialization thay vì lock.

4. **Distributed transactions (2-phase commit style)**: Redis lock không support 2PC. Dùng database transaction hoặc Saga pattern.

5. **Read-then-write với correctness requirement**: Lock đảm bảo mutual exclusion, không đảm bảo read-your-writes không stale. Fencing token cần thiết.

6. **Systems requiring strict ordering**: Redis lock không guarantee ordering. Dùng message queue (Kafka, Redis Streams).

### 4.12. Alternatives — Chi tiết từng tool

#### Database Lock (SELECT FOR UPDATE, advisory lock)

```
PostgreSQL:  BEGIN;
             SELECT balance FROM accounts WHERE id = 123 FOR UPDATE;
             -- balance locked until COMMIT/ROLLBACK
             UPDATE accounts SET balance = balance - 100 WHERE id = 123;
             COMMIT;

MySQL:       SELECT ... FOR UPDATE (InnoDB row lock)
             GET_LOCK('resource_name', timeout)
             RELEASE_LOCK('resource_name')

Advantages:
  - ACID: strong consistency
  - Rollback on failure
  - Fencing token (automatic with MVCC)
  - No clock drift issue
  - Works across any database-backed resource

Disadvantages:
  - Latency: 5-50ms vs Redis 0.1-0.5ms
  - Connection pool exhaustion
  - Database is single point of failure (unless HA config)
  - Not suitable for non-DB resources (file system, external API)
```

#### ZooKeeper (ZAB protocol, linearizable)

```
Sequential znode approach:
  1. Create ephemeral sequential node: /locks/resource-
     Gets path like /locks/resource-0000000123
  2. Get all children of /locks/resource
  3. If my sequence number is lowest -> I hold the lock
  4. Otherwise: watch the node with next lower sequence number
  5. When that node disappears -> check again

Advantages:
  - Linearizable (ZAB protocol)
  - Fencing token (sequence number is monotonic)
  - Session-based ephemeral nodes (auto-cleanup on client crash)
  - Proven consensus protocol (Paxos-like)
  - No clock sync issue (ZAB doesn't rely on wall clocks)

Disadvantages:
  - Operational complexity: ZooKeeper cluster setup/maintenance
  - Latency: 5-20ms (JVM + network)
  - 3-node minimum for quorum
  - Requires dedicated infrastructure
```

#### etcd (Raft consensus, linearizable)

```
Go:  cli, _ := clientv3.New(clientv3.Config{Endpoints: []string{"localhost:2379"}})
     // Acquire
     txn := cli.Txn(ctx)
     txn.If(clientv3.Compare(clientv3.Version(key), "=", 0))
     txn.Then(clientv3.OpPut(key, val, clientv3.WithLease(leaseID)))
     _, err := txn.Commit()
     // Fencing: version number from etcd is monotonic

Advantages:
  - Linearizable (Raft consensus)
  - Built-in fencing token (mod_revision)
  - HTTP/JSON API (easy integration)
  - Distributed lock via concurrency API
  - Smaller footprint than ZooKeeper

Disadvantages:
  - Latency: 5-30ms (depends on cluster distance)
  - Operational complexity
  - Learning curve for Raft
```

#### Consul (Raft consensus + service mesh)

```
KV API:
  session = consul.Session.Create()
  consul.KV.Acquire(&KV{Key: "lock", Value: []byte(token), Session: session})

Advantages:
  - Service mesh + distributed lock in one tool
  - HTTP API
  - Health checks integrated
  - Lock with automatic renewal

Disadvantages:
  - Latency: 10-50ms
  - Can be heavyweight if only need lock
  - Less mature lock API than ZooKeeper
```

#### Idempotency Pattern

```
Pattern: Thay vì lock, dùng idempotency key

Payment API example:
  1. Client generates idempotency key: "idem:order123:retry1"
  2. Server: SET idem:order123:retry1 processing NX EX 3600
  3. Server: Process payment
  4. Server: SET idem:order123:retry1 completed
  5. Client retries with same key
  6. Server: GET idem:order123:retry1 -> "completed" -> return cached result

Advantages:
  - No lock needed
  - Natural retry support
  - Works at scale
  - Simpler than distributed lock

Disadvantages:
  - Only works if operation is truly idempotent
  - Not suitable for non-idempotent operations
  - Need storage for idempotency keys
```

#### Queue-Based Serialization

```
Kafka approach:
  Producer: Send message to partition keyed by resource ID
           Messages for same resource go to same partition
           Kafka guarantees ordering within partition
  Consumer: Process messages in order per resource
           Lock not needed — ordering ensures serialization

Redis Streams approach:
  XADD payments:queue * order_id=123 amount=1000
  Consumer group processes in order
  XACK after successful processing

Advantages:
  - No lock needed
  - Natural ordering
  - Can be replayed
  - Works across restarts

Disadvantages:
  - Added latency (queuing)
  - Operational complexity
  - Not real-time (there is delay)
  - If consumer crashes mid-processing, need careful redelivery handling
```

---

## 5. Trade-off Analysis

### Redis Lock vs DB Lock

| Tiêu chí | Redis Lock (`SET NX PX`) | DB Lock (`SELECT FOR UPDATE`) |
|---|---|---|
| Consistency | Eventual (not linearizable) | Strong (ACID) |
| Latency | 0.1–0.5ms | 5–50ms |
| Throughput | Very high (50K–100K locks/sec) | Lower (1K–10K locks/sec) |
| Fencing token | None (must implement separately) | Automatic (MVCC version) |
| Durability | Optional (AOF/RDB) | Always durable (WAL) |
| Crash handling | Lock auto-expires (risk of overlap) | Lock held until COMMIT/ROLLBACK |
| Rollback | No | Yes (automatic) |
| Multi-resource | Requires multiple locks (deadlock risk) | Single transaction locks all |
| Scope | Any resource (file, API, DB) | DB resources only |
| Single point of failure | Redis can fail (use Sentinel/Cluster) | DB can fail (needs HA config) |
| Best for | Idempotent operations, short critical sections | Financial transactions, DB consistency |
| Not for | When correctness > availability | Low-latency coordination |

### Redlock vs Single Redis Lock

| Tiêu chí | Single Redis Lock | Redlock (5 nodes) |
|---|---|---|
| Availability | Lower (single point of failure) | Higher (majority survives) |
| Clock drift risk | None (single node) | Real risk across geographic nodes |
| Complexity | Simple | Complex (quorum, drift calculation, release all nodes) |
| Latency | 0.1–0.5ms | 5–50ms (sequential SET to N nodes) |
| Correctness | Better (no cross-node issues) | Worse (Kleppmann's criticisms) |
| Recommended for | Most production scenarios | Only when Redis HA is insufficient |
| Failure mode | Redis down = no locks | Partial network partition = lock race |

### Lock vs Idempotency

| Tiêu chí | Distributed Lock | Idempotency Key |
|---|---|---|
| Mechanism | Serialize access (mutual exclusion) | Prevent duplicate execution |
| Non-idempotent ops | Works | Does not work |
| Idempotent ops | Overkill | Perfect fit |
| Complexity | Medium (token management, TTL, Lua) | Low (SET NX + check-and-set) |
| Latency | 0.5–5ms (including network) | 0.1–0.5ms |
| Retry friendliness | Must handle lock expiry during retry | Natural retry support |
| Best for | Non-idempotent critical sections | API endpoints, payment retries, async jobs |
| Data loss risk | Lock expiry = operation may be lost | No risk (result cached) |

### Lock vs Queue-Based Serialization

| Tiêu chí | Distributed Lock | Queue (Kafka/Streams) |
|---|---|---|
| Real-time | Yes (lock acquisition immediate) | No (queuing delay) |
| Latency | p50=0.5ms, p99=5ms | p50=50ms, p99=500ms (depends on consumer) |
| Complexity | Medium | High (queue infrastructure) |
| Ordering guarantee | No (lock doesn't guarantee order) | Yes (partition key = ordering) |
| Crash recovery | Lock expires, other clients wait | Message redelivered to another consumer |
| Backpressure | Lock blocks, no queue buildup | Queue absorbs, consumer can catch up |
| Best for | Short critical sections (< 5s) | Long-running workflows, async processing |
| Lock expiry issue | Real (operation may overlap with new lock holder) | None (message not processed until ACKed) |

### Availability vs Correctness

| Tiêu chí | Strong Correctness | High Availability |
|---|---|---|
| Trade-off | Lock expiry causes unavailability | Lock expiry may cause inconsistency |
| Financial data | Use DB lock (correctness > availability) | No (unacceptable data loss) |
| Cache warming | Redis lock OK (availability > correctness) | N/A |
| Job scheduling | Redis lock OK (retry-on-fail) | N/A |
| Leader election | Redis lock OK if idempotent (retry) | Better with ZooKeeper/etcd |
| Configuration | Redis lock OK (can reload) | N/A |
| Inventory | Redis lock with fencing token | Only if overstock acceptable |
| Payment | Database serializable transaction | Never Redis lock |

---

## 6. Best Solution & Best Practices

### Decision Tree: Khi nào dùng gì

```
Bạn cần coordination cho resource R?

1. Operation idempotent?
   No  -> Đến câu 2
   Yes -> Dùng Idempotency Key (SET NX + check result)
          -> Không cần lock

2. Operation chạm vào financial data hoặc cần linearizability?
   Yes -> Dùng Database transaction (SELECT FOR UPDATE)
          -> Không cần Redis lock

3. Operation cần multi-resource locking?
   Yes -> Dùng ZooKeeper sequential node hoặc etcd
          -> Redis không phù hợp

4. Operation dài (> 30 giây)?
   Yes -> Dùng Queue-based serialization
          -> Lock expiry risk cao quá

5. Redis lock phù hợp khi:
   - Single resource
   - Operation ngắn (< TTL/2)
   - Idempotent operation OR acceptable overlap
   - Low latency requirement
   - Single Redis (không Redlock trừ khi có lý do đặc biệt)
```

### Production Lock Implementation Checklist

```go
// ✅ Đúng: Complete safe lock implementation
type DistributedLock struct {
    rdb *redis.Client
}

type LockResult struct {
    Acquired bool
    Token    string
}

// Acquire with retry and backoff
func (l *DistributedLock) Acquire(
    ctx context.Context,
    key string,
    ttl time.Duration,
    retryDelay time.Duration,
    maxRetries int,
) (*LockResult, error) {
    token := generateToken() // UUID v4

    for attempt := 0; attempt <= maxRetries; attempt++ {
        if attempt > 0 {
            select {
            case <-ctx.Done():
                return nil, ctx.Err()
            case <-time.After(retryDelay * time.Duration(1<<uint(attempt-1))):
                // Exponential backoff
            }
        }

        acquired, err := l.rdb.SetNX(ctx, key, token, ttl).Result()
        if err != nil {
            return nil, fmt.Errorf("redis error: %w", err)
        }

        if acquired {
            return &LockResult{Acquired: true, Token: token}, nil
        }
    }

    return &LockResult{Acquired: false}, nil
}

// Release: atomic check-and-delete via Lua
func (l *DistributedLock) Release(ctx context.Context, key, token string) error {
    const releaseScript = `
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
    `
    _, err := l.rdb.Eval(ctx, releaseScript, []string{key}, token).Result()
    return err
}

// Extend: atomic check-and-extend via Lua
func (l *DistributedLock) Extend(ctx context.Context, key, token string, ttl time.Duration) error {
    const extendScript = `
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("PEXPIRE", KEYS[1], ARGV[2])
        else
            return 0
        end
    `
    _, err := l.rdb.Eval(ctx, extendScript, []string{key}, token, ttl.Milliseconds()).Result()
    return err
}
```

### Anti-Patterns

1. **DEL without token check**: Xóa lock của người khác → double execution.
2. **SETNX + EXPIRE riêng**: Race window có thể gây deadlock.
3. **Lock TTL quá nhỏ**: Operation không kịp finish → overlap.
4. **Redlock cho local deployment**: Clock drift không đáng kể giữa local VMs; Redlock thêm complexity không cần thiết.
5. **Dùng lock cho non-idempotent operation mà không có fencing token**: Correctness không đảm bảo.
6. **Lock không có retry với backoff**: Immediate retry = contention spike.
7. **Dùng lock thay vì queue cho long-running operation**: Lock expiry trong operation = inconsistency.
8. **Quên handle lock not acquired case**: Luôn kiểm tra `Acquired == false` và có fallback plan.

---

## 7. Performance Considerations

### Latency Numbers

| Operation | p50 | p95 | p99 | Notes |
|---|---|---|---|---|
| SET NX PX (local) | 0.1ms | 0.3ms | 0.5ms | Single Redis |
| SET NX PX (cross-DC) | 2ms | 10ms | 50ms | Cross-datacenter |
| Safe unlock Lua (local) | 0.15ms | 0.4ms | 0.7ms | GET+DEL atomic |
| Redlock acquire (5 nodes) | 5ms | 15ms | 50ms | Sequential, worst path |
| Redlock release (5 nodes) | 8ms | 20ms | 80ms | Parallel release |
| ZooKeeper lock acquire | 5ms | 15ms | 30ms | ZAB protocol |
| etcd lock acquire | 3ms | 10ms | 25ms | Raft consensus |
| DB SELECT FOR UPDATE | 5ms | 20ms | 50ms | Depends on DB load |

### Throughput

```
Redis Lock Throughput (single node):
  - Acquire: ~80K ops/sec (local network)
  - Release: ~80K ops/sec
  - Combined with retry: ~10K–50K ops/sec depending on contention

Redlock Throughput:
  - 5 nodes, sequential acquire: ~5K ops/sec max
  - 5 nodes, parallel acquire: ~3K ops/sec (network overhead)
  - Lock validity: TTL determines sustainable rate

Contention Impact:
  - 0% contention: 80K ops/sec
  - 10% contention: 72K ops/sec (retry overhead)
  - 50% contention: 40K ops/sec
  - 90% contention: 8K ops/sec (heavy retry storm)
```

### TTL Selection

```
Rule of thumb: TTL = operation_duration * 3 + safety_margin

Examples:
  - Quick lock (< 100ms): TTL = 1s
  - Medium lock (1–5s): TTL = 15s
  - Long lock (5–30s): TTL = 90s, consider queue instead
  - Very long (> 30s): Use queue, not lock

Never set TTL to lock_duration exactly.
Always have margin for:
  - GC pause (Java/Go can pause 100ms+)
  - Network jitter
  - DB query spikes
  - Clock drift
```

---

## 8. Production Failure Modes

### Failure Mode 1: Lock Token Mismatch — Unlock Removes Wrong Lock

**Dấu hiệu nhận biết**:
- Two clients cùng process shared resource
- Duplicate operations (double payment, double order, double email)
- Không có error logs (DEL trả về 1 = success)
- Problem xảy ra sau crash/restart của một client

**Nguyên nhân**: `DEL` không kiểm tra token. Client A (crashed, lock expired) hoặc Client A (slower) gọi `DEL` và xóa Client B's lock.

**Debug**:
```bash
# Check lock history (requires monitoring)
redis-cli DEBUG SLEEP 1  # not useful here
# Pattern: look for DEL commands on lock keys in slowlog
redis-cli SLOWLOG GET | grep DEL
```

**Fix**: Luôn dùng Lua script cho unlock. Never call `DEL` directly on lock key.

```lua
-- Always use this for unlock
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
```

### Failure Mode 2: Lock Expiry During Critical Section

**Dấu hiệu nhận biết**:
- Operations overlap giữa old holder và new holder
- Data inconsistency (e.g., balance goes negative)
- Partial writes (only one client's writes visible)

**Nguyên nhân**: Operation dài hơn lock TTL. Lock expire trong khi operation đang chạy.

**Debug**:
```bash
# Check lock TTL vs operation duration
redis-cli DEBUG OBJECT ENCODING lock:resource
# Not directly available, need application logging
```

**Fix**:
1. Đo operation duration, set TTL = duration * 3 + margin
2. Implement TTL extension trong Lua nếu cần
3. Nếu operation quá dài (> 30s), dùng queue thay vì lock
4. Implement fencing token để resource từ chối stale operations

### Failure Mode 3: Redlock Quorum không đủ

**Dấu hiệu nhận biết**:
- Lock acquired với 3/5 quorum
- 1-2 nodes bị network partition hoặc slow
- Lock không thực sự held vì clock drift

**Debug**:
```bash
# Check each node's lock state
redis-cli -h node1 GET lock:resource
redis-cli -h node2 GET lock:resource
# If different tokens -> quorum issue
```

**Fix**: Monitor lock acquisition time. If elapsed > TTL/2, reject lock. Use single Redis with Sentinel instead of Redlock for most cases.

### Failure Mode 4: Lock Not Released on Panic/Error

**Dấu hiệu nhận biết**:
- Lock không released sau khi operation fail
- Các request tiếp theo fail với "lock not acquired"
- Lock eventually expires (after TTL), nhưng có delay

**Nguyên nhân**: `return` hoặc `panic` trước khi gọi `Release()`. Trong Go: defer không được gọi nếu goroutine bị kill.

**Fix**:
```go
// ✅ Đúng: defer release
func processWithLock(ctx context.Context, key string) error {
    lock := acquireLock(ctx, key)
    if !lock.Acquired {
        return errors.New("lock not acquired")
    }
    defer func() {
        if lock.Acquired {
            lock.Release(ctx, key, lock.Token)
        }
    }()

    // ... process ...
    return nil
}

// Also: handle context cancellation
func (l *DistributedLock) AcquireWithContext(ctx context.Context, ...) {
    // If ctx cancelled, don't hold lock
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }
    // proceed with acquire
}
```

### Failure Mode 5: Single Redis Point of Failure

**Dấu hiệu nhận biết**:
- Redis down → toàn bộ distributed lock unavailable
- System offline hoặc fallback to unsafe mode

**Fix**:
1. Dùng Redis Sentinel (1 master + 2 replicas) — automatic failover
2. Không dùng Redlock — Sentinel đủ cho hầu hết cases
3. Implement lock retry với exponential backoff across failover

---

## 9. Real-world Examples

### Stripe: Idempotency Key Pattern

Stripe không dùng distributed lock cho payment processing. Thay vào đó, họ dùng idempotency key với Redis:

```
Pattern: SETNX cho idempotency + status tracking

1. Client sends: POST /payments { ..., Idempotency-Key: "order-123-retry" }
2. Server:
   EXISTS idem:order-123-retry
   if exists:
     GET idem:order-123-retry -> return cached result
   else:
     SET idem:order-123-retry "processing" EX 86400 NX
     process_payment()
     SET idem:order-123-retry "success:result" EX 86400

Why not lock? Payment processing is idempotent with idempotency key.
Lock would add latency without benefit.
```

### Uber: ZooKeeper cho distributed coordination

Uber dùng ZooKeeper (thông qua Mesos) cho leader election và distributed locking. Đặc biệt cho task scheduling, ZooKeeper sequential node pattern đảm bảo:

- FIFO ordering of lock requests
- Automatic lock release on client disconnect (ephemeral node)
- Monotonic sequence number = fencing token

Redis lock không đủ cho Uber's task scheduling vì correctness requirement cao.

### GitHub: Redis lock cho job scheduling (limited)

GitHub dùng Redis lock cho background job scheduling với `SET NX PX` + token. Nhưng họ chỉ dùng nó cho:

- Prevent duplicate job execution (idempotent jobs)
- Short-lived jobs (< 30s)
- Jobs có built-in retry mechanism

Họ không dùng Redis lock cho jobs cần correctness guarantees — những jobs đó dùng database-backed job queue.

### Shopify: Redis lock + Redlock hybrid

Shopify dùng Redlock variant (3 nodes trong cùng datacenter, không phải multi-region) cho bulk operations. Lý do:

- Redundancy for Redis node failure
- Trong cùng datacenter, clock drift < 5ms, Kleppmann's criticisms less relevant
- Operation là idempotent (retry safe)

Không dùng Redlock cho cross-datacenter vì clock drift không predictable.

---

## 10. Common Pitfalls

1. **DEL without Lua check**: Phổ biến nhất. `DEL` xóa lock của bất kỳ ai → double execution. Fix: Lua script bắt buộc.

2. **SETNX + EXPIRE riêng**: Race window gây deadlock. Fix: `SET key token NX PX ttl` (single command).

3. **TTL quá nhỏ cho operation**: Lock expire trong operation. Fix: TTL = operation_time * 3 + margin. Đo operation time trước khi set.

4. **Không handle lock not acquired**: Coi lock acquisition luôn thành công. Fix: luôn check `Acquired == false`, có fallback.

5. **Dùng Redlock cho single-datacenter**: Thêm complexity không cần thiết. Clock drift trong cùng datacenter không đáng kể. Dùng Redis Sentinel.

6. **Dùng Redis lock cho financial data**: Wrong tool. Redis không linearizable. Dùng DB transaction hoặc ZooKeeper/etcd.

7. **Dùng lock cho long-running operation**: Lock expiry trong operation = overlap. Dùng queue (Kafka, Redis Streams) thay vì lock.

8. **Không có fencing token khi cần correctness**: Lock không đủ để guarantee resource access correctness. Implement fencing token hoặc dùng linearizable store.

9. **Lock không có retry với backoff**: Immediate retry gây contention spike. Fix: exponential backoff.

10. **Client crash không release lock**: Lock expire sau TTL. Nhưng nếu TTL quá lớn → unavailable quá lâu. Fix: TTL nhỏ + extension mechanism.

---

## 11. Câu hỏi tự kiểm tra

### Câu 1
Tại sao `DEL lock:resource` không an toàn để unlock? Minh họa scenario gây double execution.

**Đáp án**: `DEL` là command không có điều kiện. Nếu Client A acquire lock (token_A, TTL=30s), crash, lock auto-expire, Client B acquire (token_B), sau đó Client A "hồi sinh" và gọi `DEL lock:resource`, nó sẽ xóa Client B's lock. Client C acquire lock tiếp, cùng access resource với B. Double execution xảy ra mà không có error. Safe unlock phải dùng Lua script: `if GET == token then DEL`.

### Câu 2
Bạn cần implement lock cho "send notification email" (idempotent operation). Dùng Redis lock hay idempotency key? Tại sao?

**Đáp án**: Idempotency key. Operation "send notification email" là idempotent — gửi email 2 lần với cùng message_id không gây problem (email client deduplicate). Redis lock thêm latency không cần thiết và có expiry risk. Idempotency key approach: `SETNX idem:notif:msg123 processing NX PX 3600` → process → `SET idem:notif:msg123 done`. Retry → check result → return cached. Lower latency, simpler, works with retries naturally.

### Câu 3
Martin Kleppmann phản đối Redlock. Nêu 2 lý do chính và giải pháp thay thế.

**Đáp án**:
1. **Clock drift**: Redlock giả định synchronized clocks, nhưng NTP drift, VM migration, VM pause có thể gây lock race. Trong multi-region Redlock, đặc biệt nguy hiểm. Giải pháp: dùng single Redis (không clock drift) hoặc ZooKeeper/etcd (linearizable, không rely on wall clock).
2. **No fencing token**: Redlock không cung cấp monotonic sequence number. Lock holder crash → lock expire → new holder acquire → overlap operation → potential data inconsistency. Giải pháp: implement fencing token riêng hoặc dùng ZooKeeper sequential node.

### Câu 4
Một payment system debit tài khoản. Nhân viên A đọc balance (1000), nhân viên B cũng đọc balance (1000), cả hai cùng debit 500 và 300. Balance cuối cùng là 700 thay vì 200. Đây là vấn đề gì? Redis lock giải quyết được không? Fencing token có cần thiết không?

**Đáp án**:
- Đây là classic lost update problem (race condition trên shared resource).
- Redis lock giải quyết được nếu: (a) dùng SET NX PX + token, (b) TTL đủ lớn, (c) dùng Lua script để atomic read-check-write.
- Fencing token CẦN THIẾT nếu: operation không idempotent và correctness bắt buộc. Với payment, lock không đủ vì lock expiry + operation overlap có thể gây double debit. Fencing token đảm bảo resource từ chối operation từ stale lock holder.
- Giải pháp tốt nhất cho financial: DB serializable transaction (SELECT FOR UPDATE) — linearizable, automatic fencing.

### Câu 5
So sánh ZooKeeper vs Redis lock cho leader election. Khi nào chọn cái nào?

**Đáp án**:
- **Redis lock cho leader election**: Khi latency quan trọng, hệ thống có Redis sẵn, acceptable để lose leadership briefly on Redis failure. Redis lock leader election: `SET leader:<service> <node_id> NX PX 15000` → renewal mỗi 10s. Simple, fast.
- **ZooKeeper cho leader election**: Khi correctness bắt buộc, hệ thống cần guarantee không có split-brain, đã có ZooKeeper infrastructure. ZK sequential ephemeral node đảm bảo FIFO ordering + automatic cleanup + fencing token.
- Redis lock leader election có split-brain risk nếu Redis fail: 2 nodes cùng tin mình là leader. ZooKeeper không có risk này (ZAB consensus).

### Câu 6
TTL của lock = 10 giây. Operation A mất 8 giây (network call chậm). Tại t=8s, lock expire. Operation B acquire lock. Tại t=9s, Operation A hoàn thành và write data. Tình huống gì xảy ra? Cách fix?

**Đáp án**:
- Tình huống: Operation A và B overlap trong 1 giây. Nếu A và B đều modify cùng data → inconsistency. A không biết lock đã expire. B không biết A đang chạy.
- Fix options:
  1. **Increase TTL**: Set TTL = 10 * 3 = 30s → safety margin lớn. Operation A (8s) fit trong margin.
  2. **Extend lock during operation**: Go rút kinh nghiệm từ ZooKeeper. Gọi Lua extend mỗi 5s nếu operation còn chạy.
  3. **Break long operation**: chia operation thành nhiều step, mỗi step acquire lock riêng.
  4. **Use queue instead**: Không dùng lock. Kafka/Redis Streams serialize operations. Message không được process cho đến khi consumer ready.

### Câu 7
Bạn có 100 concurrent workers cùng muốn process 1 task (chỉ 1 worker được assign). Dùng Redis lock với TTL 30s. Mỗi worker retry immediately nếu lock fail. Điều gì xảy ra?

**Đáp án**:
- 100 workers cùng gọi `SET NX` → 1 thành công, 99 fail.
- 99 workers retry immediately → lock chưa expire → 99 fail lại → immediate retry → ... → retry storm.
- Redis CPU spike, latency p99 tăng 50-100x.
- Giải pháp:
  1. Exponential backoff: `sleep(2^attempt * 100ms)` trước retry.
  2. Random jitter: `sleep(random(0, 100ms) * 2^attempt)`.
  3. Worker chọn random delay trước khi acquire: tránh thundering herd ngay từ đầu.
  4. Dùng Lua script để implement blocking pop trên queue: `BLPOP task:queue 10` — Redis blocking, không retry loop ở application layer.
