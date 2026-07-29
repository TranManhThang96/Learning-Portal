# Day 20: Sentinel & High Availability

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Giải thích được Redis Sentinel architecture: gossip protocol, quorum mechanism, leader election (Raft-like), automatic failover sequence từ SDOWN → ODOWN → election → promote → reconfigure.
- Phân tích được tại sao tối thiểu 3 Sentinel node là baseline production, tại sao 2 node không chịu được Sentinel failure, vì sao 3/5 odd topology dễ vận hành hơn 4 node, và cách spread Sentinel across availability zones (AZ).
- Triển khai được production-grade Sentinel topology bằng Docker Compose (1 master + 2 replica + 3 Sentinel) và kết nối application bằng ioredis Sentinel support.
- Phân tích trade-off giữa Sentinel vs manual failover, Sentinel vs Cluster, quorum cao vs thấp, automatic vs operational control — đưa ra recommendation theo từng use case (cache, session, primary store).
- Thiết kế được Sentinel topology cho multi-AZ deployment, chọn đúng quorum và `parallel-syncs`, viết failover runbook, phân tích split-brain risk.
- Monitor failover time, client reconnect storm, Sentinel network overhead, và đặt alert threshold phù hợp.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: Manual Failover Thảm Hoạ — Stack Overflow (2016)

Stack Overflow từng vận hành Redis master mà không có automated failover. Khi master crash lúc 14:00 (giờ cao điểm), team phải:

1. Phát hiện crash qua monitoring (mất ~2 phút)
2. SSH vào một replica, chạy `redis-cli SLAVEOF NO ONE` thủ công (mất ~3 phút)
3. Cập nhật DNS / config hardcoded master IP cho tất cả application instances (mất ~10-15 phút)
4. Restart tất cả application pods để reconnect

**Kết quả**: 20-30 phút downtime, 10K+ requests thất bại, postmortem dài 5 trang.

**Bài học**: Manual failover là phương án không scale. Khi hệ thống > 100K users, mỗi phút downtime = real business loss.

### Incident 2: Twitter — Từ Sentinel Sang Cluster

Twitter ban đầu dùng Redis với Sentinel-driven replication. Ở quy mô hàng triệu ops/sec, họ gặp vấn đề:

- Sentinel failover vẫn là single-master (1 master writes, replicas read-only)
- Mỗi failover mất 15-30 giây, ảnh hưởng timeline fan-out
- Sharding thủ công không scale

Twitter chuyển sang **Redis Cluster** để horizontal scaling (Day 22-24 sẽ cover chi tiết). Nhưng với hệ thống vừa và nhỏ, Sentinel vẫn là giải pháp đúng.

### Incident 3: GitHub — Sentinel Misconfiguration Gây Split-Brain

Một pattern incident phổ biến là cấu hình Sentinel quorum quá thấp và master không có write guard. Cần phân biệt rõ: `quorum=1` có thể khiến ODOWN quá nhạy, nhưng failover vẫn cần majority authorization từ Sentinel set. Split-brain thực tế thường xảy ra khi majority partition promote replica thành master, trong khi old master ở partition còn lại vẫn accept writes vì Redis server không cấu hình `min-replicas-to-write` / `min-replicas-max-lag`.

**Lesson**: Quorum nên đặt theo majority (2/3 hoặc 3/5), và split-brain write phải được giảm bằng Redis server config trên master, không phải bằng Sentinel config giả định.

### Bottom Line

Redis không có Sentinel = single point of failure. Sentinel misconfigured = split-brain và data corruption. Senior developer phải hiểu cả 2 failure modes để thiết kế đúng.

---

## 3. Kiến thức nền cần có

- **Day 19 Replication Internals**: async replication, PSYNC, replica lag, `replicaof no one`, `WAIT` command, replication backlog. Hiểu master-replica là nền tảng mà Sentinel đứng trên.
- **Day 12 Connection Pooling**: client reconnect behavior, timeout strategy — khi master thay đổi, tất cả clients phải reconnect.
- **Day 13 Latency**: failover time impact lên p99 latency.

---

## 4. Lý thuyết chi tiết

### 4.1. Redis Sentinel Architecture

Redis Sentinel là **distributed system** độc lập với Redis server process. Mỗi Sentinel process chạy song song với Redis instance, và các Sentinels giao tiếp với nhau qua **gossip protocol** (TCP port 26379 mặc định).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Redis Sentinel High Availability Topology              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Application Layer (TypeScript / Go / Java)           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │   │
│  │  │ Sentinel-aware│  │Sentinel-aware│  │Sentinel-aware│          │   │
│  │  │    Client     │  │    Client     │  │    Client     │          │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │   │
│  └─────────┼─────────────────┼─────────────────┼────────────────────┘   │
│            │                 │                 │                           │
│            │    SENTINEL get-master-addr-by-name    │                     │
│            │                 │                 │                           │
│  ┌─────────┴─────────────────┴─────────────────┴───────────────────┐  │
│  │               Sentinel Plane (port 26379)                            │  │
│  │                                                                   │  │
│  │  ┌─────────┐     gossip (TCP)    ┌─────────┐                   │  │
│  │  │Sentinel-1│◄──────────────────►│Sentinel-2│                    │  │
│  │  │AZ: us-east-1a│                 │AZ: us-east-1b│                 │  │
│  │  └────┬──────┘     gossip        └────┬──────┘                   │  │
│  │       │                               │                            │  │
│  │       └──────────────┬────────────────┘                            │  │
│  │                      gossip                                          │  │
│  │                      ┌────┴────┐                                    │  │
│  │                      │Sentinel-3│                                    │  │
│  │                      │AZ: eu-1a │                                    │  │
│  │                      └──────────┘                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                  Redis Data Plane (port 6379)                       │  │
│  │                                                                     │  │
│  │  ┌─────────────────┐                                               │  │
│  │  │  Redis Master   │◄── PSYNC ──► ┌─────────────────────────┐   │  │
│  │  │  (AZ: us-east-1a)│             │   Redis Replica-1        │   │  │
│  │  │  port: 6379      │◄── PSYNC ──►│   (AZ: us-east-1b)     │   │  │
│  │  └─────────────────┘             └───────────┬─────────────┘   │  │
│  │                                              │                   │  │
│  │                                              │                   │  │
│  │                                        ┌─────┴──────────────┐   │  │
│  │                                        │  Redis Replica-2   │   │  │
│  │                                        │  (AZ: eu-west-1)  │   │  │
│  │                                        └───────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

**5 chức năng cốt lõi của Sentinel** (theo Redis docs):

1. **Monitor**: Sentinel liên tục ping master và replicas, phát hiện `SDOWN` (Subjective Down) và `ODOWN` (Objective Down).
2. **Notification**: Khi phát hiện vấn đề, Sentinel gửi alert qua Pub/Sub channel (`+sdown`, `+odown`, `+switch-master`).
3. **Automatic failover**: Khi master fail, Sentinel bầu leader và orchestrate failover tự động.
4. **Configuration provider**: Clients query Sentinel để lấy địa chỉ master hiện tại (`SENTINEL get-master-addr-by-name`).
5. **Provider**: Cung cấp thông tin về master và replicas qua `SENTINEL masters`, `SENTINEL replicas`.

### 4.2. Quorum — `sentinel monitor` và `sentinel down-after-milliseconds`

```
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
```

**`sentinel monitor <name> <ip> <port> <quorum>`**:

- `<quorum>` = số Sentinel phải đồng ý rằng master là DOWN trước khi trigger failover.
- Quorum = 2 trên 3 Sentinel → cần 2/3 Sentinels đồng ý SDOWN → ODOWN.

**`sentinel down-after-milliseconds <name> <ms>`**:

- Thời gian (ms) một Sentinel chờ không nhận PING reply từ master trước khi mark là SDOWN.
- 5000ms = 5 giây → master không reply 5 lần → SDOWN.
- Quá ngắn (1000ms): false-positive network glitch → flapping.
- Quá dài (30000ms): failover chậm, downtime kéo dài.

**Quorum không phải là toàn bộ điều kiện để failover thành công**. Quorum là số Sentinel cần để **mark ODOWN**. Sau đó, Sentinel muốn thực hiện failover còn phải lấy failover authorization từ **majority của known Sentinels**. Vì vậy:

- `quorum=1` trên 3 Sentinels có thể làm ODOWN quá nhạy, nhưng 1 Sentinel bị cô lập không tự failover nếu không lấy được majority vote.
- `ckquorum` phải OK cả về configured quorum và majority authorization thì failover mới đáng tin cậy.
- Split-brain write prevention không nằm ở Sentinel alone; old master phải được cấu hình `min-replicas-to-write` và `min-replicas-max-lag` ở Redis server để tự reject writes khi bị cô lập khỏi replicas.

Failover được thực hiện bởi **1 Sentinel leader** được bầu qua epoch/vote. Điều kiện chính:

```
conditions for ODOWN:
  1. quorum Sentinels mark SDOWN
  2. SDOWN reports còn fresh trong Sentinel view

conditions for leader election:
  1. ODOWN đã declared
  2. Candidate nhận vote từ majority của known Sentinels trong current epoch
  3. Mỗi Sentinel chỉ vote một lần mỗi epoch; không dựa vào "highest runid"
```

**Critical misconception**: Quorum = số Sentinels CẦN THAM GIA failover. Thực tế, chỉ 1 Sentinel thực hiện failover, nhưng nó cần cả ODOWN quorum và majority authorization.

### 4.3. Leader Election — Raft-like Algorithm

Redis Sentinel dùng epoch-based voting tương tự Raft ở mức ý tưởng: một failover chỉ có một leader hợp lệ trong một epoch, và mỗi Sentinel chỉ cấp một vote trong epoch đó.

```
Election process (khi ODOWN declared):

Step 1: Khi ODOWN declared, một Sentinel candidate tăng current epoch
        và yêu cầu authorization từ các Sentinel khác

Step 2: Candidate gửi vote request
        Gửi: SENTINEL is-master-down-by-addr <master-ip> <port> <quorum> <runid>

Step 3: Sentinel nhận vote request:
        - Chưa vote cho ai trong epoch này → có thể vote cho requester
        - Đã vote rồi → reject
        - Chưa có quorum SDOWN → reject (vì chưa ODOWN)

Step 4: Requester nhận majority votes → trở thành leader
        Leader tiến hành failover

Step 5: Failover hoàn tất → leader gửi RECONF指令 tới replicas
        → replicas SLAVEOF new-master
        → master cũ (nếu hồi phục) trở thành replica của new master
```

`runid` giúp định danh Sentinel process trong gossip/vote request, nhưng không nên dạy như "highest runid wins". Operational point quan trọng hơn: phải có majority Sentinels reachable để authorize failover.

### 4.4. Automatic Failover Sequence — SDOWN → ODOWN → Election → Promote → Reconfigure

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Redis Sentinel Failover Sequence Diagram                 │
│                                                                         │
│  Timeline ────────────────────────────────────────────────────────────  │
│                                                                         │
│  [T=0]   Master goes down (crash, network partition)                    │
│              │                                                           │
│              │ PING timeout (down-after-ms exceeded)                    │
│              ▼                                                           │
│  [T=5s]  Sentinel-1: MASTER mymaster SDOWN                            │
│          Sentinel-2: MASTER mymaster SDOWN                              │
│          Sentinel-3: still receiving PING (ok)                          │
│                                                                         │
│              │  SENTINEL is-master-down-by-addr (gossip)               │
│              ▼                                                           │
│  [T=7s]  ODOWN reached: 2/3 Sentinels agree = quorum=2                 │
│                                                                         │
│              │  Leader election requests (gossip)                       │
│              ▼                                                           │
│  [T=8s]  One Sentinel obtains majority authorization and becomes LEADER │
│                                                                         │
│              │  Leader sends SENTINEL failover <master-name>           │
│              ▼                                                           │
│  [T=9s]  LEADER: SELECT BEST REPLICA                                    │
│              Criteria:                                                  │
│              1. Replica priority (replica-priority config)             │
│              2. Replication lag (info replication → master_link_period)  │
│              3. runid tiebreaker                                         │
│                                                                         │
│              │  Leader: SLAVEOF NO ONE (promote replica to master)       │
│              ▼                                                           │
│  [T=9.5s] Replica-1: promoted to MASTER                               │
│            Replica-1: starts accepting writes                           │
│                                                                         │
│              │  Leader: SENTINEL REPLICATE new-master-ip               │
│              ▼                                                           │
│  [T=10s]  Replica-2: SLAVEOF new-master (config update)                 │
│           Replica-2: starts PSYNC from new master                       │
│                                                                         │
│              │  Old master (if recovered): auto-reconfigured           │
│              │  OLD-MASTER sẽ nhận REPLICA OF new-master                │
│              ▼                                                           │
│  [T=12s]  Failover complete. New topology propagated.                   │
│                                                                         │
│              │  Sentinel publishes +switch-master event (Pub/Sub)       │
│              ▼                                                           │
│  [T=12s]  Clients receive +switch-master notification                   │
│           Clients: close old connection, SENTINEL get-master-addr       │
│           Clients: connect to new master                                │
│                                                                         │
└──────────────────────────────────────────────────────────────────────────┘
```

**Total time: ~10-30 giây** (tùy `down-after-milliseconds` và `failover-timeout`).

**Key timing parameters**:
```
down-after-milliseconds = 5000ms  (chờ 5s trước khi SDOWN)
failover-timeout = 180000ms       (18 giây — timeout cho toàn bộ failover)
parallel-syncs = 1                 (replicas sync one-by-one, tránh overload)
```

### 4.5. Split-Brain Write Reduction — Redis Server `min-replicas-to-write`

Split-brain xảy ra khi **2 master cùng tồn tại** (network partition tách đôi hệ thống). Sentinel giúp quyết định promotion ở majority partition, nhưng **không tự làm old master reject writes**. Write guard nằm trong Redis server config trên master:

```
min-replicas-to-write 1
min-replicas-max-lag 10
```

**Cơ chế**:
- Master **từ chối writes** nếu số replicas healthy (lag <= 10 giây) nhỏ hơn `min-replicas-to-write`.
- Với 1 master + 2 replicas, `min-replicas-to-write 1` thường là balance tốt: old master bị cô lập khỏi cả replicas sẽ reject writes, nhưng hệ thống vẫn chịu được 1 replica down.
- `min-replicas-to-write 2` với đúng 2 replicas là strict hơn nhưng dễ làm outage khi chỉ 1 replica lag/down.

```
Scenario: Network partition (2 nodes mỗi bên)

Zone A (majority): Sentinel-1, Sentinel-2, Replica-1
Zone B (minority): Sentinel-3, Old-master

Zone B: Old-master không có Sentinel majority để authorize failover
         Old-master vẫn nhận writes (nếu clients remain connected)
         → Writes bị REJECTED nếu không còn đủ healthy replicas theo Redis server config

Zone A: ODOWN declared → failover → Replica-1 promoted
         Writes tiếp tục ở Zone A với new master

Result: Writes chỉ đi đến 1 master duy nhất nếu write guard được đặt đúng
        Zone B bị "frozen" (writes blocked) thay vì divergence
```

**Lưu ý**: `min-replicas-to-write` không đảm bảo strong consistency tuyệt đối và không thay thế durable database. Nó giảm cửa sổ old-master writes khi partition, đổi lại có thể gây **unavailability** khi replicas lag.

### 4.6. Sentinel Topology — Tại Sao Tối Thiểu 3, Không Phải 2

**Tại sao KHÔNG phải 2 Sentinel**:

```
2 Sentinel + quorum = 2:
  - Cần cả 2 Sentinels cùng mark SDOWN để ODOWN

  Nếu 1 Sentinel crash hoàn toàn:
  - 1 Sentinel còn lại: quorum = 1/2 → NOT enough for ODOWN
  - Majority authorization cũng không đạt
  - Failover không xảy ra → Sentinel layer có single point of failure
  → 2 Sentinel: NO HIGH AVAILABILITY
```

**Vì sao 4 Sentinel ít được chọn hơn 3 hoặc 5**:

```
4 Sentinel + quorum = 2:
  - ODOWN quá nhạy vì chỉ cần 50% Sentinels report SDOWN
  - Failover authorization vẫn cần majority, nên ODOWN có thể noisy

4 Sentinel + quorum = 3:
  - An toàn hơn
  - Có thể chịu 1 Sentinel crash: còn 3 live, quorum=3 và majority=3 vẫn đạt
  - Không chịu được 2 Sentinel crash: còn 2 live, no majority

  Tổng quát: với quorum = N/2 + 1 (majority):
  - 3 nodes: majority = 2/3
  - 4 nodes: majority = 3/4
  - 5 nodes: majority = 3/5
  → 3 và 5 thường tốt hơn về cost/fault-tolerance ratio
  → 4 nodes không sai tuyệt đối, nhưng hiếm khi đáng thêm node so với 3; nếu cần hơn, lên 5.
```

**Recommended topology**:

```
3 Sentinel:
  quorum = 2 (majority of 3)
  - Any 2 Sentinels agree → ODOWN
  - Can tolerate 1 Sentinel failure → failover still works

5 Sentinel:
  quorum = 3 (majority of 5)
  - Any 3 Sentinels agree → ODOWN
  - Can tolerate 2 Sentinel failures → failover still works
  - Better fault tolerance than 3 (can lose 2 vs 1)

Minimum 3 nodes, spread across AZs:
  - Sentinel-1: AZ us-east-1a (co-located with master)
  - Sentinel-2: AZ us-east-1b (different AZ)
  - Sentinel-3: AZ us-west-2a (different region if needed)
```

### 4.7. App Client Discovery — SENTINEL get-master-addr-by-name

Application không bao giờ kết nối trực tiếp đến hardcoded master IP. Thay vào đó, dùng Sentinel client library để discover master.

```
┌────────────────────────────────────────────────────────────┐
│           Redis Sentinel Client Discovery Flow              │
│                                                            │
│  1. Client starts                                          │
│     │                                                      │
│     │  SENTINEL get-master-addr-by-name mymaster           │
│     ▼                                                      │
│  2. Sentinel returns current master IP:port               │
│     Example: ["127.0.0.1", "6379"]                        │
│                                                            │
│     │                                                      │
│     │  Client connects to master directly                  │
│     ▼                                                      │
│  3. Client SUBSCRIBE to Sentinel Pub/Sub channel          │
│     SUBSCRIBE +switch-master                               │
│                                                            │
│  4. Normal operation: reads/writes to master              │
│                                                            │
│  5. Failover happens (Sentinel orchestrates)              │
│                                                            │
│     │                                                      │
│     │  Sentinel publishes: +switch-master mymaster        │
│     │  Old-ip Old-port -> New-ip New-port                  │
│     ▼                                                      │
│  6. Client receives +switch-master event                   │
│     Client: closes old connection to old master            │
│     Client: SENTINEL get-master-addr-by-name mymaster      │
│     Client: connects to new master                         │
│     Client: resumes writes                                 │
│                                                            │
│  7. Old master (if recovered) becomes replica            │
│     No client points to it anymore                         │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Hardcoded master IP = anti-pattern**:
- Master thay đổi sau failover → application dùng IP cũ → connection refused → downtime.
- Phải restart tất cả application instances → cascading failure.

### 4.8. Production Deployment Best Practices

```
┌────────────────────────────────────────────────────────────────┐
│           Production Sentinel Deployment Checklist               │
│                                                                 │
│  Topology:                                                      │
│  ✅ 3 hoặc 5 Sentinel nodes (KHÔNG phải 2 hoặc 4)             │
│  ✅ Spread across availability zones (AZ)                       │
│  ✅ KHÔNG co-locate Sentinel với Redis trên cùng host          │
│  ✅ Mỗi Redis node (master + replicas) có ít nhất 1 Sentinel  │
│                                                                 │
│  Configuration:                                                 │
│  ✅ quorum = majority (2/3 hoặc 3/5)                             │
│  ✅ down-after-milliseconds = 5000-10000 (tùy network jitter)  │
│  ✅ failover-timeout = 180000 (3 phút)                           │
│  ✅ parallel-syncs = 1 (default, an toàn cho replication lag)   │
│  ✅ min-replicas-to-write = 2 (cho primary store)               │
│  ✅ min-replicas-max-lag = 10 (tùy SLA)                         │
│  ✅ auth-pass nếu dùng requirepass trên Redis                    │
│  ✅ sentinel announce-ip nếu Sentinel chạy trong container     │
│                                                                 │
│  Monitoring:                                                    │
│  ✅ Monitor sentinel:master:mymaster:state (ok/odown/sdown)     │
│  ✅ Monitor last_ok_ping_reply (latency từ Sentinel đến master) │
│  ✅ Alert on: odown events, failover frequency > threshold      │
│  ✅ Alert on: replica lag > 30s (sentinel:replica:lag)           │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

**Container deployment (Docker/Kubernetes)**:
```yaml
# IMPORTANT: Sentinel cần announce-ip khác với container IP
# Nếu không, clients bên ngoài sẽ nhận container-internal IP
sentinel announce-ip <external-routable-ip>
sentinel announce-port 26379
```

---

## 5. Trade-off Analysis

### Sentinel vs Manual Failover

| Dimension | Sentinel Automatic | Manual Failover |
|---|---|---|
| **Failover time** | ~10-30s (automatic) | ~5-30 min (human + process) |
| **Downtime** | Minimal | Significant (5-30 min incident) |
| **Human error** | None (deterministic) | High (wrong replica, wrong IP, typo) |
| **Monitoring required** | Yes (Sentinel itself) | Yes (external monitor) |
| **Ops burden** | Low (set-and-forget) | High (runbook, on-call) |
| **Complexity** | Medium (3+ Sentinel processes) | Low (just Redis) |
| **Split-brain risk** | Managed via quorum | Very high (humans make mistakes) |
| **Use when** | Production (any scale > 1 instance) | Dev/test, toy projects |

### Sentinel vs Redis Cluster

| Dimension | Sentinel | Redis Cluster |
|---|---|---|
| **Scaling** | Vertical only (single master) | Horizontal (multiple masters) |
| **Sharding** | None (single keyspace) | 16384 hash slots auto-sharded |
| **Failover** | Master → best replica | Per-shard master → replica |
| **Client complexity** | Sentinel-aware client needed | Cluster-aware client needed |
| **Operations** | Simple | Complex (resharding, slot migration) |
| **Data volume** | Single node memory limit | Sum of all shard memory |
| **Write throughput** | Single master bottleneck | Multiple masters in parallel |
| **Use when** | < 100K ops/sec, single keyspace | > 100K ops/sec, need horizontal scale |
| **Complexity** | Medium | High |

> **Preview Day 22**: Sentinel quản lý 1 master và replicas của nó. Cluster quản lý nhiều master shards. Chọn Sentinel cho đơn giản, chọn Cluster khi cần scale.

### Quorum Cao vs Thấp — Failover Sensitivity

| Quorum Setting | 3 Sentinels, quorum=1 | 3 Sentinels, quorum=2 | 3 Sentinels, quorum=3 |
|---|---|---|---|
| **False positive risk** | Rất cao (1 Sentinel có thể declare ODOWN) | Thấp (2/3 required) | Thấp nhưng dễ stuck |
| **Tolerable Sentinel failures** | ODOWN vẫn xảy ra với 1 node, nhưng failover authorization vẫn cần majority | 1 | 0 (1 fail = no failover) |
| **Failover speed** | Noisy/unstable, không đáng tin | Normal (2/3) | Slow / impossible |
| **Split-brain write risk** | Cao nếu old master không có `min-replicas-to-write` | Low nếu có write guard | Không failover nhưng outage cao |
| **Recommended for** | Dev/test only | **PRODUCTION DEFAULT** | Never (anti-pattern) |
| **Network glitch sensitivity** | High | Medium | N/A |

### Automatic Failover vs Operational Control

| Aspect | Automatic Failover | Manual Failover (on-call) |
|---|---|---|
| **Speed** | Fast (~10-30s) | Slow (~5-30 min) |
| **24/7 availability** | Yes | No (depends on human) |
| **Business continuity** | Better | Worse |
| **Risk** | False positive failover | Human error in judgment |
| **Audit trail** | Automatic in Sentinel logs | Depends on on-call discipline |
| **Use when** | Primary store, critical path | Non-critical cache, batch jobs |

### 3 Sentinel vs 5 Sentinel

| Dimension | 3 Sentinels | 5 Sentinels |
|---|---|---|
| **Quorum** | 2 | 3 |
| **Tolerable failures** | 1 Sentinel | 2 Sentinels |
| **Infrastructure cost** | 3 VMs/containers | 5 VMs/containers |
| **AZ distribution** | 2 AZs possible | 3 AZs possible (ideal) |
| **Failover reliability** | Good | Better |
| **Recommended for** | Standard production | Multi-region, critical infra |
| **Consensus speed** | Faster (fewer nodes) | Slightly slower |

---

## 6. Best Solution & Best Practices

### Scenario 1: Redis as Cache (non-critical, high throughput)

```
Configuration:
  - Sentinel: 3 nodes, spread across 2-3 AZs
  - Quorum: 2 (majority of 3)
  - down-after-milliseconds: 10000 (10s — tolerate brief network hiccup)
  - min-replicas-to-write: 0 (cache không cần durability, chấp nhận data loss)
  - parallel-syncs: 1
  - failover-timeout: 180000

Rationale:
  - Cache miss → re-populate from DB → không cần strong durability
  - Ngắn hơn down-after-milliseconds = quá nhạy, false failover
  - min-replicas-to-write = 0 vì cache loss không phải incident
  - Tối thiểu hóa ops: dùng Sentinel chỉ để auto-recovery
```

### Scenario 2: Redis as Session Store

```
Configuration:
  - Sentinel: 3 nodes, spread across 2-3 AZs
  - Quorum: 2
  - down-after-milliseconds: 5000 (5s — sessions are user-visible)
  - min-replicas-to-write: 2 (session data important)
  - min-replicas-max-lag: 10 (10s lag acceptable)
  - parallel-syncs: 1
  - AOF everysec on all nodes

Rationale:
  - Session loss → user logged out → bad UX
  - min-replicas-to-write: 2 đảm bảo session được replicated trước khi ACK
  - AOF everysec: acceptable session loss window (1s)
  - Cân nhắc: nếu 1 replica lag > 10s → writes bị blocked
    → Có thể dùng min-replicas-to-write = 1 nếu availability > consistency
```

### Scenario 3: Redis as Primary Store (source of truth)

```
Configuration:
  - Sentinel: 5 nodes (spread across 3 AZs in 2 regions)
  - Quorum: 3 (majority of 5)
  - down-after-milliseconds: 5000
  - min-replicas-to-write: 3 (must have majority replicas)
  - min-replicas-max-lag: 5 (strict, data-critical)
  - parallel-syncs: 1
  - failover-timeout: 180000
  - AOF always on all nodes (fsync everysec insufficient)
  - replica-priority: đặt cao hơn cho replica-1 (candidate for promotion)

Rationale:
  - Primary store: data loss = business loss → maximize durability
  - 5 Sentinels + quorum=3: tolerate 2 Sentinel failures
  - min-replicas-to-write=3: writes require 3 replicas confirmed
  - AOF always: durability SLO < 1s

Trade-off:
  - Write latency cao hơn (cần 3 replicas confirm)
  - Nếu 2 replicas lag > 5s → writes blocked
  → Nếu availability SLA > write latency SLA: giảm xuống min-replicas-to-write=2
```

### Anti-patterns cần tránh

1. **2 Sentinel nodes**: Không đủ cho quorum động khi 1 node fail → failover không bao giờ xảy ra.
2. **Sentinel cùng host với Redis master**: Khi host fail, cả master và Sentinel-1 cùng down → nếu Sentinel-2 cũng trên cùng host → 2/3 Sentinels down → no failover.
3. **Hardcoded master IP trong application**: Sau failover, app vẫn connect đến IP cũ → connection refused → downtime.
4. **Không SUBSCRIBE +switch-master event**: App không biết master đã đổi → tiếp tục write đến IP cũ → failures.
5. **Quorum = 1 trên 3 nodes**: Bất kỳ Sentinel nào cũng trigger failover → false positive, split-brain.
6. **Không set replica-priority**: Khi failover, Sentinel chọn replica "ngẫu nhiên" (theo runid) → không kiểm soát được replica nào promoted.
7. **`min-replicas-to-write` block writes**: Nếu replicas lag → writes bị từ chối → application errors → nên đặt thấp hoặc = 0 cho non-critical use cases.
8. **Không monitor Sentinel health**: Nếu Sentinel processes die, app vẫn "running" nhưng không có failover capability.

---

## 7. Performance Considerations

### Failover Time Breakdown

```
Failover time = down-after + ODOWN detection + leader election + promotion + reconfigure

down-after-milliseconds:     5000ms    (configurable)
ODOWN detection + gossip:      ~500ms  (network RTT, gossip propagation)
Leader election:               ~100ms  (runid comparison, vote gathering)
Replica promotion (SLAVEOF NO ONE): ~100ms
Replica reconfigure:           ~500ms  (SENTINEL REPLICATE sent to remaining replicas)
Pub/Sub notification:          ~100ms  (Sentinel publishes +switch-master)
Client reconnect:              ~1000ms (connection close + SENTINEL query + new connect)

Total typical:                  ~7-12 seconds (best case)
Total worst case:              ~20-35 seconds (network issues, slow replicas)
```

### Client Reconnect Storm

```
Khi master failover:
  - Sentinel publishes +switch-master
  - Tất cả connected clients (ví dụ: 5000 clients) nhận event
  - Tất cả 5000 clients gọi SENTINEL get-master-addr-by-name ĐỒNG THỜI
  - Tất cả 5000 clients connect đến new master ĐỒNG THỜI

Risk: New master nhận 5000 connections cùng lúc → connection limit exceeded
     → New master REJECT connections → clients retry → reconnect storm → overload

Mitigation:
  - Redis: maxclients = 10000+ (default là 10000)
  - Application: jittered reconnect delay (random 0-2s backoff)
  - Connection pool: reuse connections, không tạo mới mỗi request
  - Sentinel-aware client: tự động handle +switch-master event
```

### Sentinel Network Overhead

```
Per Sentinel: gửi PING đến master + replicas mỗi second (1 PING/second)
Gossip: mỗi Sentinel gửi/ nhận ~10 messages/second (gossip với các Sentinel khác)
→ Negligible: < 1% CPU trên Sentinel node

Network per Sentinel (worst case, 100 clients):
  - PING to master:     ~100 bytes × 1/s × 1 = ~0.1 KB/s
  - PING to replicas:   ~100 bytes × 1/s × 2 = ~0.2 KB/s
  - Gossip to peers:    ~200 bytes × 10/s × 2 = ~4 KB/s
  Total: ~4.3 KB/s per Sentinel (hoàn toàn negligible)
```

### Monitoring Interval và Sensitivity

```
Sentinel ping interval: 1000ms (1 second)
down-after-milliseconds: 5000ms (5× ping interval)

Detection timeline:
  T=0:    Master stops responding to PING
  T=1s:   Sentinel ping timeout, retry
  T=2s:   Retry 2
  T=3s:   Retry 3
  T=4s:   Retry 4
  T=5s:   Retry 5, exceeds down-after-ms → SDOWN declared
  T=6s:   Gossip propagates SDOWN to other Sentinels
  T=7s:   ODOWN declared (2/3 Sentinels agree)

Alert threshold recommendations:
  - sentinel_ping_latency_ms > 1000ms sustained: WARNING
  - sentinel_ping_latency_ms > 5000ms: CRITICAL (SDOWN imminent)
  - failover events > 1/week: WARNING (investigate flapping)
  - replica_replication_lag_seconds > 30s: WARNING
  - replica_replication_lag_seconds > 120s: CRITICAL
```

---

## 8. Production Failure Modes

### 8.1. Split-Brain với Network Partition

```
Symptom: 2 masters cùng accept writes, data divergence
Cause:
  - Majority Sentinel partition promote replica thành new master
  - Old master trong partition khác vẫn accept writes vì min-replicas-to-write = 0
  - Quorum quá thấp làm ODOWN/flapping nhạy hơn, nhưng failover authorization vẫn cần majority
Detection:
  - Alert on: +switch-master events > 1/hour (flapping indicator)
  - Alert on: 2 masters cùng IP range trong Sentinel config
  - Check: redis-cli INFO replication trên cả 2 masters
Fix:
  - Quorum = majority (2/3 hoặc 3/5)
  - Redis master: đặt min-replicas-to-write phù hợp (thường 1 với 2 replicas, 2 chỉ khi chấp nhận availability loss)
  - Sau partition hồi phục: check redis-cli ROLE trên tất cả nodes
  - Nếu data divergence: stop writes, manually reconcile, restart
Prevention:
  - LUÔN dùng quorum = majority và kiểm tra ckquorum
  - Dùng Redis server `min-replicas-to-write` để old master bị cô lập không tiếp tục accept writes
  - Test network partition bằng chaos engineering
```

### 8.2. Sentinel Quorum Không Đạt — Failover Không Xảy Ra

```
Symptom: Master down nhưng failover không trigger, system unavailable
Cause:
  - 2 Sentinel processes bị stop/crash → chỉ 1 Sentinel còn lại
  - Quorum = 2/3 → 1 Sentinel không đủ → no failover
  - Application tiếp tục connect đến dead master → all requests fail
Detection:
  - Alert on: Sentinel process not running
  - Alert on: sentinel ckquorum <master-name> returns non-OK
  - Check: redis-cli SENTINEL master mymaster → flags should include "odown"
Fix:
  - Restore Sentinel processes immediately
  - Nếu không kịp: manual failover tạm thời
  - Add replacement Sentinel node
Prevention:
  - Monitor Sentinel processes (not just Redis)
  - Spread Sentinel across VMs/hosts, không co-locate trên cùng machine
  - Luôn có at least 3 Sentinel nodes running
```

### 8.3. Flapping Master — Master Down → Up → Down Liên Tục

```
Symptom: Nhiều failover liên tiếp trong thời gian ngắn, +switch-master event spam
Cause:
  - down-after-milliseconds quá ngắn (1000ms) → network jitter gây false SDOWN
  - Master CPU spike → PING response chậm → SDOWN giả
  - Network không stable (cloud environment với occasional latency spikes)
Detection:
  - Alert on: > 2 failover events trong 1 giờ
  - Alert on: +sdown/+odown events spam trong Sentinel logs
Fix:
  - Tăng down-after-milliseconds lên 5000-10000ms
  - Thêm sentinel down-after-milliseconds jitter:
    Sentinel tự động add 10% randomization để tránh synchronized flapping
  - Check master network latency: redis-cli INFO commandstats
Prevention:
  - down-after-milliseconds = 5000ms (default, không thay đổi nếu không cần thiết)
  - Monitor master CPU, network: đằng sau network spike → preemptive alert
```

### 8.4. Replica Lag Cao Tại Thời Điểm Failover — Data Loss

```
Symptom: Replica promoted nhưng thiếu data so với original master, data loss
Cause:
  - Failover trigger khi replica chưa fully synced
  - Original master: 100K ops/s, replica lag: 60 giây tại failover time
  - Replica promoted: thiếu 60 giây data ≈ 6M operations ≈ significant data loss
  - `min-replicas-to-write` không đủ cao để prevent write trong this window
Detection:
  - Monitor: info replication → master_link_status (should be "up")
  - Monitor: master_link_down_since_seconds (> 30s = WARNING)
  - Check: sau failover, so sánh last_save của new master vs old master
Fix:
  - Dùng WAIT command cho critical writes:
    WAIT 2 5000 → đợi 2 replicas acknowledge trong 5 giây
  - Chỉ promote replica có lag < threshold
  - Đặt replica-priority cao hơn cho replica có better connectivity
Prevention:
  - Monitor replica lag continuously (alert at 10s, critical at 30s)
  - Dùng Sentinel's parallel-syncs = 1 (để replicas sync one-by-one, không overload)
  - Đặt min-replicas-max-lag = 10 để block writes khi lag > 10s
```

### 8.5. `min-replicas-to-write` Block Writes — Availability Loss

```
Symptom: Writes bị REJECTED, application errors, nhưng master vẫn "up"
Cause:
  - Replica lag > min-replicas-max-lag (10s default)
  - Hoặc 1 replica down → chỉ 1 replica remaining nhưng min-replicas-to-write=2
  - Master từ chối writes với error: "N replica(s) not reachable"
Detection:
  - Alert on: +min-slave-replica-limit (Sentinel publishes this event)
  - Check: redis-cli CONFIG GET min-replicas-to-write
  - Monitor: replica_replication_lag từ redis_exporter
Fix:
  - Giảm min-replicas-max-lag (nếu lag ổn định > 10s trong peak hours)
  - Giảm min-replicas-to-write (nếu availability > consistency cho use case)
  - Hoặc tắt tạm thời: CONFIG SET min-replicas-to-write 0
Prevention:
  - Đặt min-replicas-to-write = 0 cho cache use case
  - Đặt min-replicas-to-write = 1 cho session (đủ balance consistency/availability)
  - Đặt = 2 hoặc 3 chỉ khi primary store với strict durability requirement
```

### 8.6. False-Positive ODOWN Do Network Glitch

```
Symptom: ODOWN declared, failover triggered, nhưng master thực tế vẫn chạy
Cause:
  - Giao thức PING trên UDP/TCP bị drop trong brief network glitch
  - 2/3 Sentinels không nhận PING → quorum reached → ODOWN declared
  - Master thực tế vẫn healthy → giờ có 2 masters
Detection:
  - Alert on: +odown event khi không có actual incident
  - Check: redis-cli SENTINEL master mymaster sau khi +odown
  - Nếu master vẫn reachable → false positive
Fix:
  - Tăng down-after-milliseconds (5s → 10s)
  - Kiểm tra network infrastructure (load balancer, firewall, kernel params)
  - Reset Sentinel state: SENTINEL reset mymaster (force reconfiguration)
Prevention:
  - down-after-milliseconds = 5000ms là sweet spot (nhạy nhưng không quá sensitive)
  - Spread Sentinels on different network segments để network glitch không affect tất cả
  - Monitor network latency p95/p99: nếu p99 > 1s → alert
```

---

## 9. Real-world Examples

### GitHub: Redis Sentinel for GitHub Actions Cache

GitHub dùng Redis Sentinel để quản lý cache infrastructure cho GitHub Actions. Với hàng triệu concurrent workflows, GitHub deploys Redis clusters với 3 Sentinel nodes mỗi cluster, spread trên multiple availability zones.

Configuration pattern:
```
- 1 master + 2 replicas per cluster
- 3 Sentinel nodes, quorum = 2
- down-after-milliseconds = 5000
- min-replicas-to-write = 1
- AOF everysec
```

Lý do dùng Sentinel: Actions cache là non-critical (workflow re-run được), nhưng downtime = developers blocked. Sentinel cung cấp automatic recovery mà không cần manual intervention.

**Kết quả**: Failover < 15s p95, zero manual interventions trong 2 năm.

### Stack Exchange: Sentinel-Driven Redis Cho Tag Engine

Stack Exchange dùng Redis cho tag engine (similarity calculations, trending tags). Trước đây họ dùng manual failover, sau nhiều incident đã chuyển sang Sentinel.

Key lessons từ Stack Overflow 2016 incident:
1. Manual failover mất 20-30 phút khi on-call cần SSH, run commands, restart apps.
2. Với Sentinel: failover tự động < 15s.
3. Tuy nhiên: application phải dùng Sentinel-aware client, không phải hardcoded IP.

**Architecture**:
```
Application (Stack Overflow .NET + ASP.NET Core)
  → StackExchange.Redis library (built-in Sentinel support)
  → SENTINEL get-master-addr-by-name
  → Auto reconnect on +switch-master
```

### Twitter/X: Từ Sentinel Sang Redis Cluster

Twitter là case study quan trọng vì họ đã dùng Sentinel ở quy mô lớn và phát hiện ra giới hạn:

**Sentinel limitations Twitter encountered**:
1. **Single master bottleneck**: 1 master cho tất cả writes → CPU/Network saturation ở peak
2. **Failover time ~15-30s**: Với timeline fan-out, 30s delay = users không thấy notifications
3. **No horizontal scaling**: Sharding thủ công không scale với hàng nghìn engineers

**Migration path**:
- Phase 1: Keep Sentinel cho metadata, use client-side sharding
- Phase 2: Migrate to Redis Cluster (Day 22-24) cho data plane
- Phase 3: Phased rollout — cluster cho new features, keep Sentinel for legacy

**Lesson**: Sentinel đủ cho hầu hết use cases. Chỉ chuyển sang Cluster khi gặp actual scaling limits — không nên premature optimization.

### Shopify: Sentinel Cho Session Store

Shopify dùng Redis Sentinel cho session storage của millions merchants. Critical path: merchant login, checkout sessions.

**Sentinel deployment pattern**:
```
3 Sentinel nodes spread:
  - Sentinel-1: US East (same AZ as master)
  - Sentinel-2: US West (cross-AZ)
  - Sentinel-3: EU West (cross-region)

Configuration:
  - down-after-milliseconds: 5000
  - min-replicas-to-write: 1
  - min-replicas-max-lag: 10
  - replica-priority: 100 (primary candidate), 50 (secondary)
```

**Challenge**: Session TTL = 30 days. Replica lag không được exceed 10s (để min-replicas-to-write works). Redis replication lag phải < 10s even during peak → requires dedicated network segment.

---

## 10. Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| 2 Sentinel nodes | Quorum không đạt khi 1 fail → no failover | Luôn dùng 3 hoặc 5 |
| Sentinel cùng host với master | Host fail = master + Sentinel đều down | Spread across hosts/AZs |
| Hardcoded master IP | App vẫn connect IP cũ sau failover | Dùng Sentinel client library |
| Không SUBSCRIBE +switch-master | Client không biết master đổi | Sentinel-aware client tự handle |
| Quorum = 1 | ODOWN quá nhạy; dễ flapping, dễ promote khi majority partition thấy master down | Quorum = majority |
| Quorum = 3 trên 3 nodes | 1 Sentinel fail = no failover possible | Quorum = 2 (majority of 3) |
| `min-replicas-to-write` = 2 khi có 2 replicas | Writes luôn bị block khi 1 replica lag | Đặt = 1 hoặc = 0 nếu availability > consistency |
| Không monitor Sentinel health | Sentinel processes die không biết | Monitor sentinel process + ckquorum |
| Replica promotion không deterministic | Không biết replica nào promoted | Set `replica-priority` trên replicas |
| `parallel-syncs` = all | Failover overload new master | Giữ = 1 (default, an toàn) |
| Không test failover | Không biết failover works cho đến incident | Regular chaos testing |

---

## 11. Câu hỏi tự kiểm tra

### Câu 1: Quorum Calculation

Bạn có 5 Sentinel nodes. Quorum được đặt = 3. Khi nào ODOWN được declared? Nếu 2 Sentinel bị crash, failover có xảy ra không?

> **Đáp án**: ODOWN declared khi ≥ 3/5 Sentinels đồng ý master là SDOWN. Nếu 2 Sentinel crashed → 3 còn lại → quorum = 3/5 → **vẫn đủ để ODOWN → failover vẫn xảy ra**. Failover được thực hiện bởi leader (1 Sentinel) với votes từ remaining 2 Sentinels = 3 votes total (≥ quorum). Với 3 Sentinel crashed → chỉ 2 còn lại → quorum = 2/5 → **không đủ → no failover**.

### Câu 2: Failover Time Estimate

Với `down-after-milliseconds = 10000`, `failover-timeout = 180000`, `parallel-syncs = 1`, ước tính failover time tối thiểu và tối đa.

> **Đáp án**:
> - **Minimum**: 10s (down-after) + ~2s (ODOWN detection + election) + ~1s (promotion + reconfigure) + ~1s (client reconnect) = **~14 giây**
> - **Maximum**: 10s (down-after) + 180s (failover-timeout) = **~190 giây** (nếu replica promotion fail, Sentinel retry)
> - **Typical**: 15-30 giây
> - `parallel-syncs = 1` không ảnh hưởng đến failover time, chỉ ảnh hưởng đến thời gian replicas sync sau failover

### Câu 3: Split-Brain Scenario

Giải thích chính xác vì sao `quorum = 1` trên 3 Sentinel là nguy hiểm, và vì sao split-brain write vẫn cần xét thêm `min-replicas-to-write`. Vẽ timeline.

> **Đáp án**:
> ```
> Network partition: Sentinels-1+2 + Replica-1 (Zone A) vs Sentinel-3 + Old master (Zone B)
>
> Zone A: 2 Sentinels reach quorum/majority, master không reachable
>   → ODOWN declared
>   → 1 Sentinel lấy majority authorization
>   → Replica-1 promoted thành new master
>
> Zone B: Old master vẫn đang chạy và vẫn có clients local
>   Nếu Redis server min-replicas-to-write=0:
>     old master vẫn accept writes
>     new master cũng accept writes ở Zone A
>     → split-brain writes, data divergence
>   Nếu min-replicas-to-write=1 và old master mất cả 2 replicas:
>     old master reject writes
>     → availability loss ở Zone B, nhưng tránh divergence
>
> Fix: quorum = 2 (majority of 3) + Redis server min-replicas-to-write phù hợp.
> ```

### Câu 4: Trade-off Decision

Hệ thống e-commerce. Redis dùng cho:
- Session store (30 ngày TTL)
- Cart data (persistent, không được mất)
- Hot product cache (rebuild from DB được)

Đề xuất Sentinel config cho TỪNG use case. Giải thích trade-off.

> **Đáp án**:
>
> | Use Case | Quorum | min-replicas-to-write | down-after-ms | Lý do |
> |---|---|---|---|---|
> | Cart data | 2 | 2 | 5000 | Primary store — data loss = order loss → max durability |
> | Session store | 2 | 1 | 5000 | Important but re-login acceptable → balance |
> | Hot product cache | 2 | 0 | 10000 | Cache loss = slow query, not failure → maximize availability |
>
> Trade-off: Cart với min-replicas-to-write=2 → writes bị block nếu 1 replica lag > 10s. Nếu availability SLA quan trọng hơn → đặt = 1 và dùng `WAIT 1 5000` cho critical cart updates.

### Câu 5: Sentinel vs Cluster Decision

Một startup có 20K ops/sec, dùng Redis cho caching. Development team nhỏ (3 engineers). ops/sec dự kiến tăng 50% mỗi năm. Chọn Sentinel hay Cluster? Tại sao?

> **Đáp án**:
> - **Chọn Sentinel** vì:
>   1. 20K ops/sec << 100K ops/sec single-master limit → Sentinel đủ
>   2. Team nhỏ → Cluster operational complexity không worth it
>   3. 50% growth/year → cần ~3 năm để đạt 67K ops/sec → vẫn dưới single-master limit
>   4. Caching → data loss acceptable → Sentinel + cache = perfect match
>   5. Failover tự động + simple setup = phù hợp với team nhỏ
>
> - **Cluster only khi**: ops/sec > 100K, cần sharding vì memory, hoặc team có capacity cho ops

### Câu 6: Failover Runbook

Mô tả step-by-step runbook để xử lý khi `SENTINEL ckquorum mymaster` trả về `QUORUM 1/2` (không đủ quorum cho failover). Đây là incident nghiêm trọng.

> **Đáp án**:
> ```
> Step 1: Assess — kiểm tra Sentinel processes
>   redis-cli -p 26379 SENTINEL masters
>   redis-cli -p 26380 SENTINEL masters
>   redis-cli -p 26381 SENTINEL masters
>   → Xác định Sentinel nào down và lý do
>
> Step 2: Restore Sentinel (ưu tiên cao nhất)
>   - Nếu Sentinel process crash: restart
>   - Nếu host down: start Sentinel trên host khác
>   - Emergency: restore/start replacement Sentinel trước. Nếu bắt buộc manual failover, chỉ làm sau khi xác nhận old master đã stop hoặc bị cô lập khỏi clients.
>
> Step 3: Verify failover capability
>   redis-cli -p 26379 SENTINEL ckquorum mymaster
>   → Phải trả về OK + số Sentinels >= quorum
>
> Step 4: Check master health
>   redis-cli INFO replication
>   → Xác nhận master up, replicas connected
>
> Step 5: Document incident
>   - Tại sao Sentinel down?
>   - Failover có bị impact không?
>   - Prevention: spread Sentinel better, add monitoring
> ```

### Câu 7: min-replicas-to-write vs min-replicas-max-lag

Giải thích sự khác nhau giữa `min-replicas-to-write` và `min-replicas-max-lag`. Khi nào nên dùng cái nào? Có thể dùng cả 2 cùng lúc không?

> **Đáp án**:
> - `min-replicas-to-write N`: Master **reject writes** nếu số replica healthy nhỏ hơn N.
> - `min-replicas-max-lag N`: Replica chỉ được tính là healthy nếu lag/ACK age <= N giây.
>
> **Hai config hoạt động cùng nhau**: ví dụ `min-replicas-to-write 2` + `min-replicas-max-lag 10` → master reject writes nếu có ít hơn 2 replicas đang connected và ACK trong 10 giây gần nhất. Không phải cứ "any replica lag > 10s" là reject nếu vẫn còn đủ N replica healthy.
>
> **Use case**:
> - `min-replicas-to-write 0` = always accept writes based on replica health (pure availability; `min-replicas-max-lag` effectively irrelevant)
> - `min-replicas-to-write 2` + `min-replicas-max-lag 10` = strict durability (primary store)
> - `min-replicas-to-write 1` + `min-replicas-max-lag 30` = moderate durability (session store)
