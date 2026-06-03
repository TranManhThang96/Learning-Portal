# Day 14: ZooKeeper vs KRaft — Metadata Management, Controller Architecture, Migration

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** vai trò của metadata management trong Kafka — tại sao cần "bộ não" điều phối cluster
2. **Nắm vững** kiến trúc ZooKeeper-based Kafka ở vai trò legacy — controller election, metadata flow, limitations
3. **Phân tích được** KRaft architecture — tại sao Kafka loại bỏ ZooKeeper, Raft consensus, quorum controller
4. **So sánh** ZooKeeper mode vs KRaft mode — operational complexity, scalability, failure modes
5. **Thực hành** chạy Kafka cluster ở KRaft mode, quan sát metadata, controller failover

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-13 (topic, partition, broker, replication, ISR, leader election)
- Hiểu leader/follower replication model từ Day 13
- Hiểu tại sao cần leader election khi broker crash
- Docker Compose Kafka cluster đang chạy (đã dùng KRaft mode từ Day 10)

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Metadata trong Kafka: những gì cần quản lý (topic configs, partition leaders, ISR, ACLs)
- ZooKeeper mode legacy: controller role, znodes, split-brain problem, limitations
- KRaft mode: Raft consensus basics, quorum controller, metadata topic `__cluster_metadata`
- Tại sao migration: Kafka 4.x chỉ hỗ trợ KRaft, ZooKeeper cluster phải migrate trước khi upgrade lên 4.x
- So sánh operational complexity: ZooKeeper vs KRaft
- Hands-on: inspect KRaft metadata, controller failover test

### 🟡 Should Learn (nếu còn thời gian)
- Raft consensus protocol chi tiết (leader election, log replication, safety)
- KRaft metadata snapshots và log compaction
- Migration path từ ZooKeeper sang KRaft
- Controller quorum voters config

### 🟢 Optional Deep Dive
- ZooKeeper internals: ZAB protocol, session management, watches
- KRaft source code: RaftClient.java, QuorumController.java
- Performance comparison benchmarks (KRaft vs ZooKeeper)
- KRaft trong multi-datacenter deployments

---

## 4. Lý thuyết (Theory)

### 4.1 Metadata trong Kafka — "Bộ não" của Cluster

#### WHY — Kafka cần quản lý những gì?

Một Kafka cluster có hàng trăm brokers, hàng nghìn topics, hàng triệu partitions. Cần có "nguồn sự thật duy nhất" (single source of truth) cho:

```
Metadata cần quản lý:
├── Cluster membership
│   ├── Broker nào đang alive?
│   ├── Broker nào vừa join/leave?
│   └── Broker ID, host, port, rack
│
├── Topic & Partition metadata
│   ├── Topic configs (retention, min.insync.replicas, ...)
│   ├── Partition → Leader mapping (P0 leader = Broker 1)
│   ├── Partition → Replicas mapping (P0 replicas = [1,2,3])
│   ├── ISR list per partition
│   └── Partition reassignment state
│
├── Controller state
│   ├── Ai là active controller?
│   └── Controller epoch (fencing token)
│
├── Consumer group offsets (lưu trong __consumer_offsets, KHÔNG trong metadata)
│
└── Security
    ├── ACLs (Access Control Lists)
    ├── SCRAM credentials
    └── Delegation tokens
```

**Vấn đề core**: Tất cả brokers phải **đồng thuận** (agree) về metadata. Nếu Broker 1 nghĩ P0 leader là mình, nhưng Broker 2 nghĩ P0 leader là Broker 3 → **split-brain** → data corruption.

### 4.2 ZooKeeper Mode — Kiến trúc cũ

#### WHAT — ZooKeeper là gì trong Kafka?

ZooKeeper là một **distributed coordination service** riêng biệt, chạy bên ngoài Kafka, dùng để:
- Lưu trữ cluster metadata
- Bầu controller (1 broker đặc biệt quản lý partition assignments)
- Phát hiện broker failure (ephemeral nodes)
- Lưu topic configs và ACLs

```
ZooKeeper-based Kafka Architecture:

┌──────────────────────────────────┐
│        ZooKeeper Ensemble         │
│  ┌────────┐ ┌────────┐ ┌────────┐│
│  │ ZK-1   │ │ ZK-2   │ │ ZK-3   ││
│  │(Leader)│ │(Follow) │ │(Follow)││
│  └───┬────┘ └───┬────┘ └───┬────┘│
│      │          │          │      │
│  znodes: /kafka/brokers,          │
│          /kafka/controller,       │
│          /kafka/topics, ...       │
└──────┬───────────┬─────────┬──────┘
       │           │         │
  ┌────▼────┐ ┌────▼────┐ ┌─▼──────┐
  │Broker 1 │ │Broker 2 │ │Broker 3│
  │(Control-│ │         │ │        │
  │  ler)   │ │         │ │        │
  └─────────┘ └─────────┘ └────────┘
  
  Controller = 1 broker được bầu qua ZooKeeper
  Controller quản lý: partition assignment, leader election, ISR updates
```

#### ZooKeeper znodes cho Kafka

```
ZooKeeper tree structure:

/kafka
├── /brokers
│   ├── /ids
│   │   ├── /1    ← ephemeral node (biến mất khi broker 1 disconnect)
│   │   ├── /2    ← {host, port, rack, ...}
│   │   └── /3
│   └── /topics
│       ├── /orders
│       │   └── /partitions
│       │       ├── /0 → {"leader": 1, "isr": [1,2,3]}
│       │       ├── /1 → {"leader": 2, "isr": [2,3,1]}
│       │       └── /2 → {"leader": 3, "isr": [3,1,2]}
│       └── /payments
│           └── ...
├── /controller → {"brokerid": 1, "epoch": 42}
│                  ↑ ephemeral node, biến mất khi controller crash
├── /config
│   ├── /topics/orders → {retention.ms: 604800000}
│   └── /brokers/1 → {...}
└── /admin
    └── /reassign_partitions → {...}
```

#### Controller trong ZooKeeper Mode

```
Controller election flow:

1. Tất cả brokers cố tạo ephemeral node /controller
   B1: create /controller → SUCCESS (B1 là controller!)
   B2: create /controller → FAIL (node exists)
   B3: create /controller → FAIL
   B2, B3: watch /controller (đợi nó biến mất)

2. Controller (B1) chịu trách nhiệm:
   ├── Watch /brokers/ids → phát hiện broker join/leave
   ├── Leader election cho partitions khi broker crash
   ├── ISR updates → ghi /brokers/topics/.../partitions
   ├── Topic creation/deletion
   └── Partition reassignment

3. Controller crash:
   B1 crash → ephemeral /controller biến mất
   B2 và B3 nhận watch notification
   B2: create /controller → SUCCESS (B2 là controller mới!)
   B3: create /controller → FAIL
   B2: đọc TOÀN BỘ metadata từ ZK → rebuild in-memory state
                                      ↑ CHẬM! (hàng phút nếu cluster lớn)
```

#### Vấn đề của ZooKeeper Mode

```
1. OPERATIONAL COMPLEXITY:
   ┌─────────────┐     ┌─────────────┐
   │  ZooKeeper  │     │   Kafka     │
   │  Cluster    │     │   Cluster   │
   │  (3-5 nodes)│     │  (N nodes)  │
   └─────────────┘     └─────────────┘
   
   → 2 distributed systems phải vận hành, monitor, upgrade ĐỘC LẬP
   → ZK cần riêng: JVM tuning, disk tuning, monitoring, backup
   → Kafka upgrade phải coordinate với ZK version compatibility
   → Debugging issues đòi hỏi hiểu CẢ Kafka VÀ ZooKeeper

2. CONTROLLER BOTTLENECK:
   Cluster lớn (10,000+ partitions):
   ┌────────────────────────────────────┐
   │   Controller (1 broker)            │
   │                                    │
   │   Quản lý TẤT CẢ partition state  │
   │   ├── ISR updates: hàng nghìn/s   │
   │   ├── Leader elections: khi fail   │
   │   ├── ZK writes: ĐỒNG BỘ          │
   │   └── Metadata push đến N brokers  │
   │                                    │
   │   Single thread xử lý tất cả!     │
   │   → BOTTLENECK khi cluster lớn    │
   └────────────────────────────────────┘

3. CONTROLLER FAILOVER CHẬM:
   Controller crash → new controller phải:
   ├── Đọc TẤT CẢ metadata từ ZK
   ├── Rebuild in-memory state
   ├── Hàng nghìn ZK reads
   └── Thời gian: VÀI PHÚT cho cluster lớn!
   
   Trong thời gian này:
   → KHÔNG có leader election
   → Broker crash → partitions OFFLINE
   → Cluster "mất não"

4. METADATA INCONSISTENCY:
   ZK là source of truth, nhưng mỗi broker cache metadata
   → ZK update → Controller nhận → Controller push đến brokers
   → Window of inconsistency giữa các brokers
   → Đặc biệt tệ khi network partition
   
5. SCALABILITY LIMIT:
   ZK watch mechanism: 1 watch per client per znode
   100 brokers × 50,000 partitions = hàng triệu watches
   → ZK session timeout, reconnection storm
   → Practical limit: ~200K partitions per cluster
```

### 4.3 KRaft Mode — Kiến trúc mới

#### WHY — Tại sao loại bỏ ZooKeeper?

```
ZooKeeper pain points         →    KRaft solution
─────────────────────────────────────────────────────
2 systems to operate          →    1 system (Kafka only)
Controller failover: minutes  →    Controller failover: seconds
Metadata in ZK + cache        →    Metadata in Kafka log
Single controller thread      →    Quorum of controllers
~200K partition limit          →    Millions of partitions
ZK-specific expertise needed  →    Only Kafka expertise
```

Version scope: với Kafka 4.x, KRaft là mode duy nhất. ZooKeeper mode chỉ còn là kiến thức để hiểu legacy clusters và migration; cluster mới không nên bắt đầu bằng ZooKeeper.

#### WHAT — KRaft Architecture

KRaft = **K**afka **Raft** — Kafka sử dụng Raft consensus protocol để quản lý metadata, KHÔNG cần ZooKeeper.

```
KRaft-based Kafka Architecture:

┌───────────────────────────────────────────────────┐
│                 Kafka Cluster                      │
│                                                    │
│  Controller Quorum (Raft):                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Node 1   │  │ Node 2   │  │ Node 3   │        │
│  │ ROLES:   │  │ ROLES:   │  │ ROLES:   │        │
│  │ controller│  │ controller│  │ controller│       │
│  │ + broker  │  │ + broker  │  │ + broker  │       │
│  │           │  │           │  │           │       │
│  │ [Active   │  │ [Follower │  │ [Follower │       │
│  │  Leader]  │  │  ctrl]    │  │  ctrl]    │       │
│  └──────────┘  └──────────┘  └──────────┘        │
│       │              │              │              │
│       └──────────────┼──────────────┘              │
│              Raft consensus                        │
│              __cluster_metadata topic              │
│                                                    │
│  Broker-only nodes (optional, larger clusters):    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Node 4   │  │ Node 5   │  │ Node 6   │        │
│  │ ROLE:    │  │ ROLE:    │  │ ROLE:    │        │
│  │ broker   │  │ broker   │  │ broker   │        │
│  └──────────┘  └──────────┘  └──────────┘        │
│       ↑              ↑              ↑              │
│       └──────────────┼──────────────┘              │
│           Fetch metadata từ controllers             │
└───────────────────────────────────────────────────┘
```

#### Process Roles — Phân chia vai trò

```
process.roles config:

process.roles=broker,controller
  → Node vừa là broker (serve data) vừa là controller (manage metadata)
  → Phù hợp cluster nhỏ-trung (3-10 nodes)
  → Tiết kiệm hardware

process.roles=controller
  → Node CHỈ quản lý metadata, KHÔNG serve data
  → Phù hợp cluster lớn (dedicated controllers)
  → Controller không bị ảnh hưởng bởi data I/O load

process.roles=broker
  → Node CHỉ serve data, KHÔNG tham gia controller quorum
  → Phổ biến trong cluster lớn (nhiều broker-only nodes)
```

**Deployment patterns:**

```
Small cluster (3-5 nodes):
  Node 1: broker + controller
  Node 2: broker + controller
  Node 3: broker + controller
  → Tất cả nodes vừa serve data vừa quản lý metadata
  → Đơn giản, tiết kiệm

Large cluster (50+ nodes):
  Node 1-3: controller ONLY (dedicated)
  Node 4-53: broker ONLY
  → Controllers không bị data I/O ảnh hưởng
  → Broker failure không ảnh hưởng controller quorum
```

### 4.4 Raft Consensus trong KRaft — Cốt lõi

#### Raft Basics (Simplified)

```
Raft giải quyết: làm sao N nodes ĐỒNG THUẬN về 1 log?

3 controller nodes:
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │ Node 1  │  │ Node 2  │  │ Node 3  │
  │ LEADER  │  │FOLLOWER │  │FOLLOWER │
  │ epoch=5 │  │ epoch=5 │  │ epoch=5 │
  └────┬────┘  └────┬────┘  └────┬────┘
       │            │            │
       │ Metadata changes:       │
       │  "topic X created"      │
       │  "P0 leader = B2"       │
       │  "ISR P1 = [1,3]"      │
       │            │            │
       │ Replicate  │            │
       ├───────────►│            │
       ├────────────┼───────────►│
       │            │            │
       │ Majority   │            │
       │ (2/3) ack  │            │
       │◄───────────│            │
       │            │            │
       │ COMMITTED! │            │
       │            │            │

Raft guarantees:
  1. Leader election: chỉ 1 leader per epoch (term)
  2. Log replication: entries committed khi majority ACK
  3. Safety: committed entry KHÔNG BAO GIỜ bị mất
  4. Liveness: hệ thống tiến triển khi majority alive
```

#### `__cluster_metadata` Topic

```
Metadata trong KRaft được lưu trong 1 internal topic đặc biệt:

__cluster_metadata (1 partition, no replication — Raft handles durability)

Records trong metadata log:
  ┌─────────────────────────────────────────────────┐
  │ Offset 0: RegisterBrokerRecord(id=1, ...)       │
  │ Offset 1: RegisterBrokerRecord(id=2, ...)       │
  │ Offset 2: RegisterBrokerRecord(id=3, ...)       │
  │ Offset 3: TopicRecord(name="orders", id=abc)    │
  │ Offset 4: PartitionRecord(topic=abc, P0,        │
  │           leader=1, replicas=[1,2,3], isr=[1,2,3])│
  │ Offset 5: PartitionRecord(topic=abc, P1, ...)   │
  │ Offset 6: ConfigRecord(topic=abc,               │
  │           retention.ms=604800000)                │
  │ Offset 7: IsrChangeRecord(topic=abc, P0,        │
  │           isr=[1,2])                             │
  │ ...                                              │
  └─────────────────────────────────────────────────┘

Brokers đọc metadata log giống consumer đọc topic:
  Broker 4: "tôi đang ở metadata offset 100, fetch tiếp"
  → Active controller trả về records 101-150
  → Broker 4 apply changes: cập nhật in-memory metadata cache
```

#### Controller Failover trong KRaft

```
ZooKeeper mode failover:
  Controller crash
  → ZK detects (session timeout ~30s)
  → New controller election
  → New controller reads ALL metadata from ZK (minutes!)
  → Total downtime: 1-5 MINUTES

KRaft mode failover:
  Active controller crash
  → Raft detects (heartbeat timeout ~500ms-2s)
  → Raft elects new leader from quorum (epoch increment)
  → New leader ALREADY HAS all metadata (replicated via Raft!)
  → New leader immediately active
  → Total downtime: 1-10 SECONDS
  
  Tại sao nhanh hơn?
  → Raft follower controllers đã có TOÀN BỘ metadata log
  → Không cần đọc lại từ external store
  → Chỉ cần xử lý nốt uncommitted entries
```

### 4.5 So sánh Chi Tiết: ZooKeeper vs KRaft

| Tiêu chí | ZooKeeper Mode | KRaft Mode |
|----------|---------------|-----------|
| **Dependencies** | Kafka + ZooKeeper cluster | Kafka only |
| **Metadata store** | ZooKeeper znodes | `__cluster_metadata` topic |
| **Controller** | 1 broker được bầu qua ZK | Quorum (3+ controllers via Raft) |
| **Controller failover** | Minutes (rebuild from ZK) | Seconds (Raft leader election) |
| **Partition limit** | ~200K (ZK watches bottleneck) | Millions (metadata log) |
| **Operational complexity** | Cao (2 systems) | Thấp hơn (1 system) |
| **Monitoring** | ZK metrics + Kafka metrics | Kafka metrics only |
| **Upgrade** | ZK + Kafka version coordination | Kafka only |
| **Split-brain protection** | ZK ephemeral nodes + fencing | Raft epoch-based fencing |
| **Metadata consistency** | Eventual (ZK → controller → brokers) | Event log (ordered, reliable) |
| **Maturity** | Rất mature, battle-tested | Production-ready từ Kafka 3.3+ |
| **Kafka version support** | Tất cả versions | Kafka 2.8+ (preview), 3.3+ (production) |
| **ZK deprecation** | Deprecated từ 3.5 | N/A |
| **ZK removal** | Kafka 4.0 loại bỏ hoàn toàn | N/A |

### 4.6 Migration Path: ZooKeeper → KRaft

```
Version timeline:

Kafka 2.8:   KRaft early access, không dùng production
Kafka 3.3+:  KRaft production-ready
Kafka 3.5+:  ZooKeeper mode deprecated
Kafka 4.x:   KRaft-only; ZooKeeper mode đã bị loại bỏ

Rule bắt buộc:
  Nếu đang chạy ZooKeeper-based cluster, phải migrate sang KRaft khi còn ở Kafka 3.x
  rồi mới upgrade lên Kafka 4.x.
```

Migration không phải là "export metadata từ ZooKeeper rồi import một lần vào KRaft log". Migration production là rolling bridge mode theo official guide:

```text
Phase 0: Preflight
  - Upgrade cluster ZooKeeper-based lên version Kafka 3.x có hỗ trợ ZK→KRaft migration.
  - Backup configs, ACLs, SCRAM credentials, topic configs, broker configs.
  - Verify controller/broker health, under-replicated partitions = 0.
  - Test full migration trên staging với bản copy config gần production.

Phase 1: Add KRaft controller quorum
  - Provision 3 hoặc 5 controller-only nodes.
  - Cấu hình controller quorum voters và metadata log dirs.
  - Controllers tham gia migration nhưng cluster vẫn phục vụ traffic qua ZooKeeper metadata path.

Phase 2: Rolling broker migration
  - Rolling restart từng broker với migration configs theo official guide.
  - Trong giai đoạn bridge, broker/controller phải đọc/ghi metadata nhất quán giữa ZooKeeper và KRaft.
  - Sau mỗi broker: verify topic describe, controller quorum status, ISR, consumer lag.

Phase 3: Finalize migration
  - Khi tất cả broker đã migrate và metadata đã sync, finalize sang KRaft.
  - Sau finalize, không rollback đơn giản về ZooKeeper được nữa.

Phase 4: Remove ZooKeeper dependency
  - Rolling restart để loại bỏ ZooKeeper configs.
  - Decommission ZooKeeper ensemble sau khi cluster KRaft healthy.
  - Chỉ sau bước này mới plan upgrade Kafka 4.x.
```

Trong lesson này, lab chỉ inspect KRaft cluster mới. Migration thật là operational project riêng, không nên làm như một bài lab 2 giờ.

---

## 5. Trade-off Analysis

### Khi nào vẫn gặp ZooKeeper Mode?

| Scenario | Recommendation | Lý do |
|----------|---------------|-------|
| Cluster Kafka mới (greenfield) | **KRaft** | Không lý do nào để dùng ZK cho cluster mới |
| Cluster Kafka < 3.3 legacy | ZooKeeper tạm thời | KRaft chưa production-ready ở các version cũ, nhưng cần plan upgrade/migration |
| Cluster Kafka 3.3+ legacy đang chạy ZK | **Migrate sang KRaft** | KRaft production-ready, ZK deprecated |
| Cluster rất lớn (> 200K partitions) | **KRaft** | ZK không scale |
| Team chưa quen KRaft | Training/staging với KRaft | Không tạo cluster ZK mới chỉ vì quen hơn |
| Kafka 4.0+ | **KRaft** bắt buộc | ZooKeeper bị loại bỏ |

### Combined vs Dedicated Controllers

| Tiêu chí | Combined (broker+controller) | Dedicated (controller only) |
|----------|-----------------------------|-----------------------------|
| Hardware | Ít nodes | Thêm 3 nodes riêng |
| Isolation | Controller bị ảnh hưởng bởi data I/O | Controller isolated |
| Failure domain | Broker crash = controller loss | Tách biệt |
| Cluster size | < 10 brokers | > 10 brokers |
| Cost | Thấp | Cao hơn (thêm 3 machines) |
| **Recommendation** | **Dev, staging, small prod** | **Large production** |

### Raft Quorum Size

| Controllers | Chịu failures | Lý do |
|------------|---------------|-------|
| 1 | 0 | ❌ Single point of failure |
| **3** | 1 | **✅ Recommended minimum** |
| 5 | 2 | Higher availability, more resources |
| 7 | 3 | Overkill cho hầu hết cases |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Cluster mới: LUÔN dùng KRaft**. Không có lý do nào để dùng ZooKeeper cho cluster tạo mới sau Kafka 3.3. ZooKeeper đã deprecated.

2. **3 controller nodes cho production**: Minimum quorum size cho fault tolerance. 5 nodes nếu cần chịu 2 failures đồng thời.

3. **Dedicated controllers cho cluster lớn (> 10 nodes)**: Tách `process.roles=controller` riêng để controller không bị ảnh hưởng bởi data I/O của broker.

4. **Monitor controller metrics**: `active-controller-count`, `metadata-log-offset`, `metadata-apply-offset`, `last-committed-offset`. Alert khi controller lag.

5. **Plan migration sớm**: Nếu đang dùng ZooKeeper, migrate khi còn ở Kafka 3.x và trước khi upgrade lên Kafka 4.x. Test migration trên staging trước production.

6. **Controller quorum voters phải odd number**: 3? hoặc 5 — KHÔNG dùng 2 hoặc 4 (split-brain risk khi network partition chia đôi).

### Common Pitfalls

1. **❌ Chạy KRaft với 1 controller**: Single point of failure. Controller crash → cluster mất metadata → TẤT CẢ operations fail.

2. **❌ Lẫn lộn controller quorum với data replication**: Controller quorum (Raft) quản lý METADATA. Data replication (ISR) quản lý DATA. Hai cơ chế KHÁC NHAU chạy SONG SONG.

3. **❌ Đặt controller trên cùng disk với data-intensive broker**: Controller ghi metadata log. Nếu disk I/O saturated bởi data → metadata writes chậm → controller timeout → election → instability.

4. **❌ Quên set `controller.quorum.voters` trên tất cả nodes**: Mọi node (cả broker-only) cần biết controller quorum voters để kết nối đúng.

5. **❌ Migration "big bang" (tất cả cùng lúc)**: Luôn rolling migration. Convert từng broker one-at-a-time. Verify cluster health sau mỗi bước.

6. **❌ Dùng ZooKeeper cho cluster mới vì "quen hơn"**: Kafka 4.x là KRaft-only. Đầu tư vào ZK cho greenfield cluster là technical debt.

---

## 7. Performance Considerations

### KRaft Performance Improvements

```
Controller failover time:
  ZooKeeper:  30s - 300s (phụ thuộc cluster size)
  KRaft:      1s - 10s   (30x faster)

Partition creation:
  ZooKeeper:  ~5 partitions/sec per controller
  KRaft:      ~50 partitions/sec per controller (10x faster)

Partition limit:
  ZooKeeper:  ~200,000 partitions per cluster (practical)
  KRaft:      ~1,000,000+ partitions per cluster

Metadata propagation:
  ZooKeeper:  Controller → ZK → Controller → push to all brokers (3 hops)
  KRaft:      Controller → Raft log → brokers fetch (2 hops, event-driven)
```

### Controller Metrics

| Metric | Ý nghĩa | Alert Threshold |
|--------|---------|----------------|
| `active-controller-count` | Số active controllers | != 1 |
| `metadata-commit-latency` | Latency commit metadata | > 500ms |
| `metadata-log-size` | Size of metadata log | Growing unbounded |
| `controller-state` | Controller state machine | != ACTIVE |
| `quorum-voters-count` | Number of voters | != configured |
| `last-applied-offset` | Last applied metadata offset | Lagging |

### KRaft Tuning

```properties
# Controller config
controller.quorum.election.timeout.ms=1000    # Election timeout
controller.quorum.fetch.timeout.ms=2000       # Fetch timeout from followers
controller.quorum.election.backoff.max.ms=1000

# Metadata log retention
metadata.log.max.record.bytes.between.snapshots=20971520  # 20MB
metadata.log.segment.bytes=1073741824                      # 1GB

# Controller network threads
controller.socket.timeout.ms=30000
```

---

## 8. Hands-on Lab

### 8.1 Lab Setup — Cluster từ Day 10 đã chạy KRaft mode

```bash
# Verify cluster đang chạy KRaft mode
docker exec kafka-1 kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9094 describe --status

# Xem controller quorum status
docker exec kafka-1 kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9094 describe --replication
```

### 8.2 Inspect Metadata Records

```bash
# Dump metadata log — tìm file dynamically, không hardcode cluster id/path
docker exec kafka-1 sh -lc 'LOG=$(find /bitnami/kafka/data -path "*__cluster_metadata-0*" -name "*.log" | sort | tail -1); echo "$LOG"; kafka-dump-log.sh --files "$LOG" --print-data-log | head -50'

# Xem brokers registered
docker exec kafka-1 kafka-broker-api-versions.sh \
  --bootstrap-server localhost:9094

# Xem toàn bộ cluster metadata summary
docker exec kafka-1 kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9094 describe --status
```

### 8.3 Controller Failover Test

```go
// controller_failover_demo.go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"time"

	"github.com/segmentio/kafka-go"
)

func getControllerAndPartitions(broker string, topic string) int {
	conn, err := kafka.Dial("tcp", broker)
	if err != nil {
		fmt.Printf("  Cannot connect to %s: %v\n", broker, err)
		return -1
	}
	defer conn.Close()

	controller, err := conn.Controller()
	if err != nil {
		fmt.Printf("  Controller info unavailable: %v\n", err)
		return -1
	}
	controllerID := controller.ID
	fmt.Printf("  Active Controller: Broker %d (%s:%d)\n",
		controller.ID, controller.Host, controller.Port)

	partitions, err := conn.ReadPartitions(topic)
	if err != nil {
		fmt.Printf("  Cannot read partitions: %v\n", err)
		return controllerID
	}
	for _, p := range partitions {
		isrIDs := make([]int, len(p.Isr))
		for i, b := range p.Isr {
			isrIDs[i] = b.ID
		}
		fmt.Printf("  Partition %d: Leader=%d, ISR=%v\n", p.ID, p.Leader.ID, isrIDs)
	}
	return controllerID
}

func containerForBrokerID(id int) string {
	if id <= 0 {
		return ""
	}
	// Lab mặc định của Day 10 dùng node.id 1,2,3 tương ứng kafka-1,kafka-2,kafka-3.
	// Nếu compose của bạn đặt tên khác, set KAFKA_CONTAINER_PREFIX trước khi chạy,
	// ví dụ: KAFKA_CONTAINER_PREFIX=broker- go run controller_failover_demo.go
	prefix := os.Getenv("KAFKA_CONTAINER_PREFIX")
	if prefix == "" {
		prefix = "kafka-"
	}
	return fmt.Sprintf("%s%d", prefix, id)
}

func canProduce(broker, topic string) bool {
	writer := &kafka.Writer{
		Addr:         kafka.TCP(broker),
		Topic:        topic,
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 100 * time.Millisecond,
	}
	defer writer.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := writer.WriteMessages(ctx, kafka.Message{
		Key:   []byte("test"),
		Value: []byte(fmt.Sprintf("failover-test-%d", time.Now().UnixNano())),
	})
	return err == nil
}

func main() {
	topic := "controller-failover-test"
	brokers := []string{"localhost:9092", "localhost:9093", "localhost:9094"}

	// Tạo topic
	conn, _ := kafka.Dial("tcp", brokers[0])
	conn.CreateTopics(kafka.TopicConfig{
		Topic:             topic,
		NumPartitions:     3,
		ReplicationFactor: 3,
	})
	conn.Close()
	time.Sleep(3 * time.Second)

	// Phase 1: Check current state
	fmt.Println("=== Phase 1: Current cluster state ===")
	controllerID := getControllerAndPartitions(brokers[0], topic)
	controllerContainer := containerForBrokerID(controllerID)
	if controllerContainer == "" {
		log.Fatal("cannot detect active controller; abort failover test")
	}

	// Phase 2: Kill active controller broker, không assume kafka-1 luôn là controller.
	fmt.Printf("\n=== Phase 2: Killing active controller Broker %d (%s) ===\n", controllerID, controllerContainer)
	start := time.Now()
	exec.Command("docker", "stop", controllerContainer).Run()

	// Phase 3: Wait and check failover
	fmt.Println("Waiting for controller failover...")
	time.Sleep(5 * time.Second)

	fmt.Println("\n=== Phase 3: After failover ===")
	for _, b := range brokers {
		fmt.Printf("\nChecking via %s:\n", b)
		getControllerAndPartitions(b, topic)
	}

	// Phase 4: Test produce capability
	fmt.Println("\n=== Phase 4: Testing produce after failover ===")
	for _, b := range brokers {
		if canProduce(b, topic) {
			elapsed := time.Since(start)
			fmt.Printf("  ✅ Produce SUCCESS via %s (failover took ~%v)\n", b, elapsed.Round(time.Second))
			break
		} else {
			fmt.Printf("  ❌ Produce FAILED via %s\n", b)
		}
	}

	// Phase 5: Restart and verify recovery
	fmt.Printf("\n=== Phase 5: Restarting %s ===\n", controllerContainer)
	exec.Command("docker", "start", controllerContainer).Run()
	fmt.Println("Waiting 15s for rejoin...")
	time.Sleep(15 * time.Second)

	fmt.Println("\n=== Phase 6: Final state ===")
	getControllerAndPartitions(brokers[0], topic)

	fmt.Println("\n→ Quan sát KRaft controller failover:")
	fmt.Println("  1. Controller failover nhanh (vài giây)")
	fmt.Println("  2. Produce tiếp tục hoạt động sau failover")
	fmt.Println("  3. Broker restart → rejoin cluster tự động")
}
```

### 8.4 Metadata Event Listener

```go
// metadata_watcher.go — Watch metadata changes in real-time
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
)

func main() {
	brokers := []string{"localhost:9092"}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; cancel() }()

	fmt.Println("=== Metadata Watcher ===")
	fmt.Println("Watching cluster metadata changes every 5s...")
	fmt.Println("Try: create/delete topics, kill brokers, etc.")
	fmt.Println()

	prevTopicCount := -1
	prevBrokerCount := -1

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			conn, err := kafka.Dial("tcp", brokers[0])
			if err != nil {
				log.Printf("Connection error: %v", err)
				continue
			}

			// Get brokers
			brokersInfo, err := conn.Brokers()
			if err != nil {
				log.Printf("Brokers error: %v", err)
				conn.Close()
				continue
			}

			// Get controller
			controller, _ := conn.Controller()

			// Get topics
			partitions, err := conn.ReadPartitions()
			conn.Close()
			if err != nil {
				log.Printf("Partitions error: %v", err)
				continue
			}

			topics := make(map[string]int)
			for _, p := range partitions {
				topics[p.Topic]++
			}

			brokerCount := len(brokersInfo)
			topicCount := len(topics)

			if brokerCount != prevBrokerCount || topicCount != prevTopicCount {
				fmt.Printf("[%s] CHANGE DETECTED!\n", time.Now().Format("15:04:05"))
				fmt.Printf("  Brokers: %d (was %d)\n", brokerCount, prevBrokerCount)
				fmt.Printf("  Topics:  %d (was %d)\n", topicCount, prevTopicCount)
				if controller.ID > 0 {
					fmt.Printf("  Controller: Broker %d\n", controller.ID)
				}
				fmt.Printf("  Topics: ")
				for t, pCount := range topics {
					fmt.Printf("%s(%dP) ", t, pCount)
				}
				fmt.Println()
				fmt.Println()

				prevBrokerCount = brokerCount
				prevTopicCount = topicCount
			}
		}
	}
}
```

### 8.5 KRaft CLI Commands

```bash
# Lab setup
mkdir -p day-14-lab && cd day-14-lab
go mod init day14-zk-vs-kraft
go get github.com/segmentio/kafka-go

# Chạy các Go programs
go run controller_failover_demo.go
go run metadata_watcher.go

# Describe cluster — KRaft metadata
docker exec kafka-1 kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9094 describe --status

# Show broker configs (xem process.roles)
docker exec kafka-1 kafka-configs.sh --bootstrap-server localhost:9094 \
  --describe --entity-type brokers --all | grep process.roles

# Feature flags — kiểm tra KRaft features enabled
docker exec kafka-1 kafka-features.sh --bootstrap-server localhost:9094 describe

# Tạo topic và quan sát metadata thay đổi
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic new-topic --partitions 6 --replication-factor 3

docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --describe --topic new-topic

# Delete topic
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --delete --topic new-topic
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **ZooKeeper đóng vai trò gì trong Kafka cũ?** Liệt kê 5 responsibilities chính. Cái nào gây bottleneck nhất khi cluster scale lên? (Hint: metadata management, controller election, broker registration)

2. **Tại sao controller failover trong ZooKeeper mode mất vài PHÚT nhưng KRaft chỉ vài GIÂY?** Giải thích bước nào mất thời gian nhất. (Hint: rebuild state from ZK vs already-replicated metadata)

3. **Process roles `broker,controller` vs `controller` vs `broker` — khi nào dùng pattern nào?** Vẽ architecture cho cluster 3 nodes vs 50 nodes. (Hint: isolation, failure domain)

4. **Raft quorum cần odd number (3, 5, 7). Tại sao KHÔNG bao giờ dùng even number (2, 4)?** Cho scenario split-brain khi network partition chia cluster thành 2 nửa bằng nhau. (Hint: majority = n/2 + 1)

5. **`__cluster_metadata` topic vs `__consumer_offsets` topic — giống/khác nhau thế nào?** Cả hai đều là internal topics, nhưng dùng Raft hay ISR replication? (Hint: metadata vs data replication)

6. **Team bạn đang chạy Kafka 3.2 với ZooKeeper. Manager yêu cầu plan migration sang KRaft. Bạn sẽ recommend gì?** Steps và risks. (Hint: upgrade Kafka first, then migrate)

7. **KRaft giải quyết "200K partition limit" của ZooKeeper bằng cách nào?** Technical reason cụ thể. (Hint: ZK watches vs event log)

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [KIP-500: Replace ZooKeeper with a Self-Managed Metadata Quorum](https://cwiki.apache.org/confluence/display/KAFKA/KIP-500%3A+Replace+ZooKeeper+with+a+Self-Managed+Metadata+Quorum) — The original proposal
- [KIP-833: Mark KRaft as Production Ready](https://cwiki.apache.org/confluence/display/KAFKA/KIP-833%3A+Mark+KRaft+as+Production+Ready)
- [Kafka KRaft Documentation](https://kafka.apache.org/documentation/#kraft)
- [ZooKeeper to KRaft Migration](https://kafka.apache.org/documentation/#kraft_zk_migration)

### Blog Posts Chất Lượng
- [Apache Kafka Made Simple: A First Glimpse of a Kafka Without ZooKeeper](https://www.confluent.io/blog/kafka-without-zookeeper-a-sneak-peek/) — Confluent
- [Why ZooKeeper Was Replaced with KRaft](https://www.conduktor.io/kafka/kafka-kraft-mode/) — Conduktor
- [KRaft: Apache Kafka Without ZooKeeper](https://developer.confluent.io/learn/kraft/) — Confluent Developer
- [The Evolution of Kafka Architecture](https://www.confluent.io/blog/removing-zookeeper-dependency-in-apache-kafka/) — Confluent

### Videos
- [The Last Zookeeper: KRaft and the Future of Kafka](https://www.youtube.com/watch?v=F9dMOCFxRFo) — Kafka Summit
- [Apache Kafka's Road to KRaft Mode](https://www.youtube.com/watch?v=YjXGNzjLYuA) — Confluent
- [KRaft: Kafka Without ZooKeeper Deep Dive](https://www.youtube.com/watch?v=dRxE_kLsWOc) — Kafka Summit
