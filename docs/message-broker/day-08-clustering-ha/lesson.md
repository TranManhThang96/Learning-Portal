# Day 8: Clustering & High Availability — Quorum Queues, Federation, Network Partitions

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** RabbitMQ clustering architecture — metadata replication, queue ownership, node types
2. **Nắm vững** quorum queues vs classic mirrored queues — tại sao quorum queues thắng
3. **Biết cách** xử lý network partitions — partition handling strategies và trade-offs
4. **Hiểu** federation và shovel — khi nào dùng cross-datacenter replication
5. **Thực hành** setup 3-node cluster với Docker, test failover scenarios

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 4-7 (AMQP model, exchange types, reliability, DLX/retry)
- Hiểu quorum queues cơ bản từ Day 6 (Raft consensus, leader/follower)
- Hiểu distributed systems basics: consensus, partition tolerance, CAP theorem
- Docker và Docker Compose

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- RabbitMQ cluster architecture — metadata vs data replication
- Classic mirrored queues: vấn đề và tại sao deprecated
- Quorum queues deep dive — Raft, leader election, delivery guarantees
- Network partition handling — ignore, pause-minority, autoheal
- Hands-on: 3-node cluster + failover test

### 🟡 Should Learn (nếu còn thời gian)
- Federation plugin — cross-datacenter message forwarding
- Shovel plugin — point-to-point message transfer
- Cluster sizing guidelines

### 🟢 Optional Deep Dive
- Raft protocol internals trong RabbitMQ
- Stream queues cho high-throughput
- Blue-green deployment với RabbitMQ

---

## 4. Lý thuyết (Theory)

### 4.1 RabbitMQ Cluster Architecture

#### WHY — Tại sao cần Cluster?

Single-node RabbitMQ có 2 vấn đề chính:
1. **Single point of failure** — node crash = toàn bộ messaging system down
2. **Capacity limit** — 1 node chỉ handle ~50K msg/s, memory/disk giới hạn

Cluster giải quyết:
- **High availability** — node crash → traffic tự chuyển sang node khác
- **Horizontal scaling** — thêm nodes để tăng capacity (nhưng không đơn giản — xem phần trade-off)

#### WHAT — Cluster hoạt động thế nào?

RabbitMQ cluster KHÔNG replicate tất cả data. Nó phân biệt rõ **metadata** và **message data**:

```
┌─────────────────── RabbitMQ Cluster ───────────────────┐
│                                                         │
│  Data replicated ACROSS ALL nodes (metadata):           │
│  ├── Exchange definitions                               │
│  ├── Queue definitions (name, args, bindings)           │
│  ├── Vhost definitions                                  │
│  ├── User/permission definitions                        │
│  └── Policies                                           │
│                                                         │
│  Data NOT replicated by default (message data):         │
│  ├── Queue contents (messages) → lives on OWNER node    │
│  └── Queue state (unacked, ready counts)                │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │  Node 1  │    │  Node 2  │    │  Node 3  │          │
│  │          │    │          │    │          │          │
│  │ [Queue A]│    │ [Queue B]│    │ [Queue C]│          │
│  │ messages │    │ messages │    │ messages │          │
│  │ here     │    │ here     │    │ here     │          │
│  └──────────┘    └──────────┘    └──────────┘          │
│                                                         │
│  Client → connect bất kỳ node → cluster auto-proxy     │
│  nếu queue ở node khác                                  │
└─────────────────────────────────────────────────────────┘
```

**Key insight:** Mặc định, messages trong classic queue chỉ nằm trên **1 node** (owner node). Node đó crash → queue unavailable + messages mất (nếu non-durable).

**Cluster proxy mechanism:**

```
Client connect Node 2, consume Queue A (lives on Node 1):

Client ──AMQP──> Node 2 ──internal──> Node 1 ──deliver msg──> Node 2 ──> Client
                    │                    │
                    └── proxy request ───┘

Performance impact: +1 hop latency (~0.5ms thêm)
```

Client có thể connect bất kỳ node nào trong cluster. Nếu queue ở node khác, cluster tự proxy. Nhưng đây là overhead — production nên kết nối node chứa queue khi có thể (dùng load balancer).

#### HOW — Node Discovery và Joining

```bash
# Node 1 starts → forms cluster alone
# Node 2 joins:
rabbitmqctl join_cluster rabbit@node1

# Cluster status:
rabbitmqctl cluster_status

# Node types:
# - Disc node: metadata lưu cả RAM và disk (survive restart)
# - RAM node: metadata chỉ trong RAM (faster, mất khi restart)
# Rule: ít nhất 1 disc node, còn lại có thể RAM
# Recommendation: ALL disc nodes cho production
```

---

### 4.2 Classic Mirrored Queues — Vấn đề và Deprecation

#### WHY — Tại sao deprecated?

Classic mirrored queues (ha-policy) là cách cũ để replicate message data across nodes. RabbitMQ team đã **officially deprecated** từ v3.13 và khuyến cáo dùng quorum queues.

#### WHAT — Cách hoạt động (và vấn đề)

```
Classic Mirrored Queue (ha-mode=all):

┌──────────┐    ┌──────────┐    ┌──────────┐
│  Node 1  │    │  Node 2  │    │  Node 3  │
│ ┌──────┐ │    │ ┌──────┐ │    │ ┌──────┐ │
│ │Master│ │───>│ │Mirror│ │───>│ │Mirror│ │
│ │Queue │ │    │ │Queue │ │    │ │Queue │ │
│ └──────┘ │    │ └──────┘ │    │ └──────┘ │
└──────────┘    └──────────┘    └──────────┘

Publish: Client → Master → async replicate to Mirrors
Consume: Client → Master → deliver message
```

**5 vấn đề nghiêm trọng:**

| # | Vấn đề | Hậu quả |
|---|---------|---------|
| 1 | **Async replication** | Master crash trước replicate xong → messages mất |
| 2 | **Sync blocking** | Mirror mới join → sync toàn bộ queue → **BLOCK queue** (không publish/consume được) |
| 3 | **Split-brain** | Network partition → 2 masters → data inconsistency, duplicate messages |
| 4 | **Performance** | Mirror overhead ~40-50% throughput reduction |
| 5 | **Promote uncertainty** | Mirror promote thành master → in-flight messages có thể mất hoặc duplicate |

```
Sync blocking scenario (vấn đề nghiêm trọng nhất):

Queue có 10M messages, mirror mới join:
1. RabbitMQ bắt đầu sync 10M messages đến mirror mới
2. TRONG KHI SYNC → queue bị BLOCK
3. Publishers: "Connection blocked" → messages bị buffer/drop
4. Consumers: Không nhận được messages
5. Sync 10M messages ở 10K msg/s = ~17 phút DOWNTIME

Production incident: Queue sync gây outage 30+ phút
```

---

### 4.3 Quorum Queues Deep Dive — Production Standard

#### WHY — Quorum Queues giải quyết tất cả vấn đề trên

| Vấn đề Classic Mirrored | Quorum Queue giải pháp |
|-------------------------|----------------------|
| Async replication → data loss | **Raft consensus** → quorum commit trước khi confirm |
| Sync blocking | **Incremental replication** → không block queue |
| Split-brain | **Raft leader election** → chỉ 1 leader, majority quyết định |
| Performance overhead | **Optimized Raft** → chỉ ~20-30% overhead (vs 40-50%) |
| Promote uncertainty | **Deterministic** → leader election rõ ràng, không mất data |

#### WHAT — Raft Consensus trong RabbitMQ

```
Quorum Queue — Raft Protocol Flow:

1. WRITE (Publish):
   Client ──publish──> Leader (Node 1)
                          │
                          ├── Write to local WAL (Write-Ahead Log)
                          ├── Replicate to Follower (Node 2) ──> Write WAL ──> ACK
                          ├── Replicate to Follower (Node 3) ──> Write WAL ──> ACK
                          │
                          ├── 2/3 ACKs received (quorum!) ✅
                          └── Confirm to Client

2. LEADER ELECTION (Node 1 crash):
   Node 2: "Tôi không nhận heartbeat từ Leader"
   Node 2: "Tôi đề cử mình làm Leader mới" (RequestVote)
   Node 3: "Đồng ý" (VoteGranted)
   Node 2: Becomes new Leader (2/3 votes = quorum) ✅
   
   Timeline:
   t=0:     Node 1 crash
   t=5s:    Heartbeat timeout (election timeout: 5-10s)
   t=5.5s:  Election starts
   t=6s:    New leader elected
   t=6.5s:  Client reconnects to Node 2/3 → resume operations
   
   Total downtime: ~5-10 seconds (acceptable cho hầu hết use cases)

3. READ (Consume):
   Client ──consume──> Leader
   Leader ──deliver msg──> Client
   Client ──ack──> Leader
   Leader ──commit ack──> Followers (replicate ack)
```

#### HOW — Configuration chi tiết

```go
// Declare quorum queue với full configuration
ch.QueueDeclare("orders.reliable", true, false, false, false, amqp.Table{
    "x-queue-type":                "quorum",
    "x-quorum-initial-group-size": 3,     // Số replicas (thường = cluster size)
    "x-delivery-limit":            5,     // Max deliveries trước khi dead-letter
    "x-dead-letter-exchange":      "orders.dlx",
})
```

Quản trị các key vận hành như `delivery-limit`, `dead-letter-strategy`, `overflow`, `max-length` bằng policy sẽ an toàn hơn hard-code trong app vì có thể đổi mà không redeclare queue:

```bash
rabbitmqctl set_policy qq-orders "^orders\." \
  '{"delivery-limit":5,"dead-letter-exchange":"orders.dlx","dead-letter-strategy":"at-least-once","overflow":"reject-publish"}' \
  --apply-to quorum_queues
```

**Quorum queue storage architecture:**

```
Quorum Queue Data Flow:

Message arrives at Leader:
  1. Write to WAL (Write-Ahead Log) — sequential disk write
  2. Replicate WAL entry to Followers
  3. On quorum → commit
  4. Periodically: compact WAL → segment files

Storage layout:
/var/lib/rabbitmq/quorum/
├── rabbit@node1/
│   ├── wal/          # Write-Ahead Log (recent writes)
│   ├── segments/     # Compacted message segments
│   └── snapshots/    # Periodic state snapshots
```

**Key difference từ classic queue:**
- Classic queue: messages trong memory (RAM-first), overflow vào disk
- Quorum queue: messages trong WAL (disk-first), hot messages cached in memory
- Quorum queue sử dụng **ít memory hơn** vì disk-first design

#### Quorum Queue — Feature Matrix

| Feature | Classic Queue | Quorum Queue | Lưu ý |
|---------|-------------|-------------|-------|
| Durable | Optional | Always | Quorum = always durable |
| Exclusive | ✅ | ❌ | Quorum không cho exclusive |
| Auto-delete | ✅ | ❌ | Quorum không tự xóa |
| Priority | ✅ (x-max-priority) | ✅ | Benchmark trước khi dùng rộng |
| Message TTL | ✅ | ✅ | TTL tăng overhead per-message |
| Lazy queue | Legacy/ignored ở bản mới | N/A | Quorum đã disk-first |
| Poison message handling | Manual (headers) | Built-in (x-delivery-limit) | Quorum tốt hơn |
| Dead-letter strategy | at-most-once | at-least-once | Quorum reliable hơn |
| Max length | ✅ | ✅ | Cả hai hỗ trợ |
| Single Active Consumer | ✅ | ✅ | Từ RabbitMQ 3.11 |

---

### 4.4 Network Partitions — Kẻ thù số 1 của Distributed Systems

#### WHY — Network Partitions xảy ra thường xuyên hơn bạn nghĩ

Network partition = nodes trong cluster **không thể communicate** với nhau nhưng **vẫn đang chạy**:

```
BEFORE partition:
  Node 1 ←──OK──→ Node 2 ←──OK──→ Node 3

DURING partition:
  [Node 1] ←─X─→ [Node 2, Node 3]
     │                    │
     │   Network break    │
     │  (switch failure,  │
     │   firewall rule,   │
     │   GC pause)        │

  Node 1 vẫn chạy, vẫn có clients
  Node 2/3 vẫn chạy, vẫn có clients
  → Split-brain potential!
```

**Nguyên nhân phổ biến:**
- Network switch failure
- Firewall rule changes
- VM live migration
- Long GC pauses (Erlang VM under memory pressure)
- Cloud provider network issues
- DNS failures

#### WHAT — 3 Partition Handling Strategies

RabbitMQ cung cấp 3 strategies qua config `cluster_partition_handling`:

**Strategy 1: `ignore` (default)**

```
Partition xảy ra → RabbitMQ KHÔNG làm gì

  [Node 1: "Tôi vẫn là cluster member"]
  [Node 2: "Tôi cũng vẫn là cluster member"]
  
  → Cả 2 sides tiếp tục accept connections
  → Classic queues: cả 2 sides có bản copy riêng (diverge!)
  → Quorum queues: minority side STOP serving (Raft quorum)
  → Khi network heal: phải MANUAL resolve

Ưu điểm: Không tự động shutdown nodes
Nhược điểm: Data inconsistency cho classic queues, manual intervention
Use case: Development, testing
```

**Strategy 2: `pause_minority`**

```
Partition xảy ra → Minority side TỰ PAUSE

3-node cluster: [Node 1] | [Node 2, Node 3]
  Node 1 = minority (1/3) → PAUSE (stop serving, disconnect clients)
  Node 2 + 3 = majority (2/3) → continue serving
  
  Khi network heal:
  Node 1 tự unpause, rejoin cluster, sync lại data

5-node cluster: [Node 1, Node 2] | [Node 3, Node 4, Node 5]
  Node 1+2 = minority (2/5) → PAUSE
  Node 3+4+5 = majority (3/5) → continue

Even split: [Node 1, Node 2] | [Node 3, Node 4]
  CẢ 2 SIDES PAUSE! → entire cluster down
  → Đây là lý do nên dùng ODD number nodes (3, 5, 7)

Ưu điểm: Tự động, không split-brain
Nhược điểm: Minority side clients bị disconnect, even split = total outage
Use case: PRODUCTION RECOMMENDED cho hầu hết
```

**Strategy 3: `autoheal`**

```
Partition xảy ra → khi network heal, LOSING side tự restart

  [Node 1: 3 clients] | [Node 2: 7 clients, Node 3: 5 clients]
  
  Network heals:
  → Node 1 = "losing side" (ít connections hơn) → RESTART
  → Node 1 mất tất cả non-durable data, rejoin fresh
  → Clients trên Node 1 bị disconnect → reconnect

Ưu điểm: Tự động heal, không cần manual intervention
Nhược điểm: Losing side MẤT DATA (non-replicated), non-deterministic
Use case: Khi data loss acceptable, high automation requirement
```

#### Trade-off: Partition Strategies

| Strategy | Data Safety | Availability | Automation | Recommendation |
|----------|-----------|-------------|-----------|----------------|
| **ignore** | ⚠️ Split-brain risk | ✅ Both sides serve | ❌ Manual fix | Development only |
| **pause_minority** | ✅ No split-brain | ⚠️ Minority down | ✅ Auto recover | **Production default** |
| **autoheal** | ⚠️ Losing side data loss | ✅ Auto recover | ✅ Fully auto | Non-critical data |

**Production recommendation:** `pause_minority` + **quorum queues**. Lý do:
- `pause_minority` ngăn split-brain
- Quorum queues bản thân đã dùng Raft (minority side stop serving quorum queues)
- Kết hợp cả 2 = double protection

#### Quorum Queues + Network Partitions

Quorum queues xử lý partitions **tốt hơn nhiều** so với classic queues:

```
3-node cluster, partition: [Node 1] | [Node 2, Node 3]

Classic Queue (owner = Node 1):
  Node 1 side: Queue accessible (owner here)
  Node 2/3 side: Queue INACCESSIBLE (owner on other side)
  → If Node 1 dies, queue data LOST

Classic Mirrored Queue:
  Node 1 side: Master here → continues serving
  Node 2/3 side: Mirror promotes to master → ALSO serving
  → SPLIT-BRAIN: 2 masters, data diverges! 💀

Quorum Queue (leader was Node 1):
  Node 1 side: Leader nhưng KHÔNG CÓ quorum (1/3 < majority)
        → STOP serving (read-only tại node level, nhưng queue operations fail)
  Node 2/3 side: Elect new leader (2/3 = quorum) ✅
        → Continue serving with new leader
  → Không split-brain; dữ liệu đã được majority commit vẫn được bảo toàn.
    Message chưa được confirm hoặc chưa replicate đủ quorum vẫn có thể mất.
```

---

### 4.5 Federation Plugin (Should Learn)

#### WHY — Khi nào cần Federation?

Cluster yêu cầu **low-latency, reliable network** giữa nodes (same datacenter). Khi bạn cần:
- Cross-datacenter message forwarding (US → EU)
- WAN links (high latency, unreliable)
- Separate admin domains

Federation cho phép **forward messages** giữa RabbitMQ instances qua unreliable network.

#### WHAT — Federation vs Clustering

```
Clustering (same datacenter):
  [Node1] ←──LAN (0.1ms)──→ [Node2] ←──LAN──→ [Node3]
  → Shared metadata, quorum queues, single cluster

Federation (cross-datacenter):
  [Cluster US]                              [Cluster EU]
  [Node1, Node2, Node3] ──WAN (50ms)──→ [Node4, Node5, Node6]
  
  Exchange federation: messages published to US exchange 
                       → forwarded to EU exchange
  Queue federation: messages in US queue 
                    → consumed from EU (like remote consumer)
```

| Tiêu chí | Clustering | Federation |
|----------|-----------|-----------|
| **Network** | LAN (low latency, reliable) | WAN OK (high latency, unreliable) |
| **Topology** | Single flat cluster | Multiple independent clusters |
| **Admin** | Single admin domain | Separate admin domains |
| **Data replication** | Quorum queues (Raft) | Message forwarding (no consensus) |
| **Failure mode** | Node failure → auto failover | Link failure → queue, retry later |
| **Latency** | +0.5ms per hop | +WAN latency |
| **Use case** | HA within datacenter | Geo-distribution, multi-region |

#### HOW — Federation Setup

```bash
# Enable federation plugin
rabbitmq-plugins enable rabbitmq_federation
rabbitmq-plugins enable rabbitmq_federation_management

# Configure upstream (source cluster)
rabbitmqctl set_parameter federation-upstream my-upstream \
  '{"uri":"amqp://admin:admin123@us-rabbitmq:5672","expires":3600000}'

# Create policy to federate exchanges matching "events.*"
rabbitmqctl set_policy federate-events "^events\." \
  '{"federation-upstream-set":"all"}' \
  --apply-to exchanges
```

```
Federation Exchange Flow:

US Cluster:                            EU Cluster:
Publisher ──> [events.orders] ──────────> [events.orders] ──> Consumer EU
                    │          WAN link         │
              Consumer US                  (federated copy)

Messages published to US exchange → automatically forwarded to EU exchange.
EU consumers get messages without connecting to US cluster.
```

---

### 4.6 Shovel Plugin (Should Learn)

#### WHAT — Shovel vs Federation

Shovel là **simpler** alternative — point-to-point message transfer giữa queues.

```
Shovel: Queue A (Cluster 1) ──consume + publish──> Queue B (Cluster 2)

Federation: Exchange A (Cluster 1) ──forward──> Exchange A (Cluster 2)
```

| Feature | Shovel | Federation |
|---------|--------|-----------|
| **Granularity** | Queue-to-queue | Exchange-to-exchange |
| **Direction** | Unidirectional | Bidirectional possible |
| **Complexity** | Simpler | More features |
| **Use case** | Data migration, specific queue forwarding | Geo-distribution |

**Khi nào dùng Shovel?**
- Migrate data giữa clusters (upgrade, datacenter move)
- Forward specific queue tới cluster khác
- Bridge giữa RabbitMQ và non-RabbitMQ (AMQP-compliant) brokers

---

## 5. Trade-off Analysis

### Cluster Sizing Guidelines

| Cluster Size | Quorum | Tolerate Failures | Throughput | Cost | Recommendation |
|-------------|--------|-------------------|-----------|------|----------------|
| **1 node** | N/A | 0 | Baseline | $ | Development only |
| **3 nodes** | 2 | 1 node | -10% vs single | $$$ | **Production minimum** |
| **5 nodes** | 3 | 2 nodes | -20% vs single | $$$$$ | Mission-critical |
| **7 nodes** | 4 | 3 nodes | -30% vs single | $$$$$$$ | Overkill |

**Rule of thumb:**
- **Always odd number** (3, 5, 7) — even splits cause total outage
- **3 nodes** cho 95% production workloads
- **5 nodes** chỉ khi cần tolerate 2 simultaneous failures
- **Mỗi node thêm = latency tăng** (more replication overhead)

### CAP Theorem Applied to RabbitMQ

```
CAP Theorem: trong network partition, chọn Consistency hoặc Availability

RabbitMQ Quorum Queues: CP (Consistency + Partition tolerance)
  - Network partition → minority side STOP (sacrifice Availability)
  - Majority side → consistent data (no split-brain)
  - This is the RIGHT choice cho message brokers (data integrity > availability)

RabbitMQ Classic Mirrored: tries to be AP → gets neither
  - Network partition → both sides serve → inconsistency
  - Manual resolution needed → actually loses availability too
  - This is WHY it's deprecated

Comparison:
  Kafka: CP (similar to quorum queues — ISR, min.insync.replicas)
  NATS JetStream: CP (Raft consensus)
  Redis Pub/Sub: AP (best-effort, no persistence guarantee)
```

### When to Use What

```
Single Datacenter HA:
  → RabbitMQ Cluster (3-5 nodes) + Quorum Queues
  → pause_minority partition handling
  → Load balancer (HAProxy/Nginx) in front

Multi-Datacenter:
  → 2 separate clusters + Federation
  → Active-active: both clusters serve local traffic
  → Active-passive: federation for disaster recovery

Data Migration:
  → Shovel for queue-to-queue migration
  → Federation for ongoing replication
```

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Luôn dùng odd number nodes (3, 5)**
   ```
   ❌ 2 nodes: partition → both sides = minority → total outage
   ❌ 4 nodes: partition 2|2 → both sides = minority → total outage
   ✅ 3 nodes: partition 1|2 → minority pauses, majority serves
   ✅ 5 nodes: partition 2|3 → minority pauses, majority serves
   ```

2. **Quorum queues cho tất cả production queues**
   ```
   Chỉ dùng classic queues cho:
   - Exclusive reply queues (RPC pattern)
   - Priority queues (quorum chưa hỗ trợ)
   - Temporary/non-critical queues
   ```

3. **`pause_minority` cho production clusters**
   ```ini
   # rabbitmq.conf
   cluster_partition_handling = pause_minority
   ```

4. **Clients phải có reconnect logic + nhiều node endpoints**
   ```go
   // ❌ Single endpoint
   conn, _ := amqp.Dial("amqp://node1:5672/")
   
   // ✅ Multiple endpoints qua load balancer
   conn, _ := amqp.Dial("amqp://rabbitmq-lb:5672/")
   
   // ✅ Hoặc client-side failover
   endpoints := []string{
       "amqp://node1:5672/",
       "amqp://node2:5672/",
       "amqp://node3:5672/",
   }
   ```

5. **Monitoring cluster health**
   ```bash
   # Cluster status
   rabbitmqctl cluster_status
   
   # Check network partitions
   rabbitmqctl cluster_status | grep partitions
   
   # Alert on:
   # - Node down
   # - Network partitions detected
   # - Quorum queue leader changes
   # - Under-replicated queues
   ```

6. **Đặt tất cả nodes trong cùng availability zone hoặc ensure low-latency**
   ```
   ✅ Same datacenter, same rack switch: latency ~0.1ms
   ⚠️ Same datacenter, different racks: latency ~0.5ms (OK)
   ❌ Cross-datacenter: latency ~5-50ms (TOO HIGH for cluster)
      → Dùng Federation thay vì Cluster
   ```

### Common Pitfalls

1. **Pitfall: Cluster cross-datacenter**
   ```
   ❌ 3 nodes: DC-A (Node1, Node2), DC-B (Node3)
      DC link down → Node3 paused (minority)
      → Node3 luôn là minority → useless
   
   ❌ 3 nodes: DC-A (Node1), DC-B (Node2), DC-C (Node3)
      Any DC down → 1 node paused → OK
      BUT: Raft replication latency = cross-DC latency
      → Throughput giảm 80-90%
   
   ✅ Cluster within 1 DC + Federation to other DCs
   ```

2. **Pitfall: Even number nodes**
   ```
   4-node cluster, partition 2|2:
   - pause_minority: CẢ 2 SIDES PAUSE → total outage!
   - autoheal: non-deterministic winner
   - ignore: split-brain
   
   → LUÔN dùng 3 hoặc 5 nodes
   ```

3. **Pitfall: Không tune Erlang VM cho cluster**
   ```bash
   # Default: Erlang scheduler tự detect CPU
   # Cluster: cần tune thêm
   
   # /etc/rabbitmq/rabbitmq-env.conf
   RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS="-rabbit cluster_formation.peer_discovery_backend rabbit_peer_discovery_classic_config"
   
   # Increase net_ticktime cho WAN-ish networks
   # Default 60s — node không respond trong 60s * 4 = 240s → consider down
   # rabbitmq.conf
   cluster_formation.net_ticktime = 60
   ```

4. **Pitfall: Classic mirrored queues vẫn đang dùng**
   ```
   ❌ Ha-policy trên classic queues (deprecated)
   rabbitmqctl set_policy ha-all ".*" '{"ha-mode":"all"}'
   
   ✅ Migrate sang quorum queues
   # 1. Tạo quorum queue mới
   # 2. Shovel messages từ classic → quorum
   # 3. Update clients để dùng quorum queue
   # 4. Xóa classic queue + ha-policy
   ```

5. **Pitfall: Quorum queue trên single node**
   ```
   Quorum queue trên 1-node cluster:
   - Hoạt động (1/1 = quorum)
   - NHƯNG không có HA (node crash = unavailable)
   - Development OK, production KHÔNG
   
   → Production: cluster >= 3 nodes cho quorum queues
   ```

---

## 7. Performance Considerations

### Cluster Performance Impact

```
Benchmark: 1KB messages, persistent, async confirms

Single node:              ~45,000 msg/s (baseline)
3-node cluster:
  - Classic queue:        ~45,000 msg/s (queue chỉ ở 1 node)
  - Classic mirrored:     ~25,000 msg/s (-44%) 
  - Quorum queue:         ~32,000 msg/s (-29%) ✅

5-node cluster:
  - Quorum queue:         ~28,000 msg/s (-38%)
  - Quorum write latency: ~3-5ms (vs ~1ms single node)
```

### Network Requirements

| Metric | Minimum | Recommended | Notes |
|--------|---------|------------|-------|
| **Latency** | < 5ms | < 1ms | Inter-node latency |
| **Bandwidth** | 100 Mbps | 1 Gbps | Message replication traffic |
| **Packet loss** | < 0.1% | 0% | Raft sensitive to packet loss |
| **Jitter** | < 5ms | < 1ms | Consistent latency important |

### Quorum Queue Tuning cho Cluster

```
Key settings:

1. wal_max_batch_size (default: 32768)
   - Số bytes tối đa trước khi flush WAL
   - Tăng → higher throughput, higher latency
   - Giảm → lower latency, lower throughput

2. wal_max_entries (default: 32768) 
   - Số WAL entries trước khi snapshot
   - Tăng → ít snapshots, recovery chậm hơn
   - Giảm → nhiều snapshots, recovery nhanh hơn

3. x-max-in-memory-length / x-max-in-memory-bytes
   - Giới hạn messages cached in-memory
   - Quorum queues disk-first → set limit để tránh memory spike
```

### Key Cluster Metrics

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| **Cluster nodes** | All running | 1 node down | Majority down |
| **Network partitions** | 0 | N/A | > 0 (always critical) |
| **Queue leader changes** | 0/hour | 1-5/hour | > 5/hour |
| **Under-replicated queues** | 0 | > 0 | > 50% queues |
| **Inter-node latency** | < 1ms | 1-5ms | > 5ms |
| **Erlang distribution connections** | All established | Intermittent drops | Connection failures |

---

## 8. Hands-on Lab

### 8.1 Setup: 3-Node Cluster với Docker Compose

**File `docker-compose-cluster.yml`:**
```yaml
version: "3.8"

services:
  rabbitmq1:
    image: rabbitmq:3.13-management-alpine
    container_name: rabbitmq1
    hostname: rabbitmq1
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin123
      RABBITMQ_ERLANG_COOKIE: "CLUSTER_SECRET_COOKIE"
      RABBITMQ_NODENAME: rabbit@rabbitmq1
    volumes:
      - rabbitmq1-data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    networks:
      - rabbitmq-cluster
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  rabbitmq2:
    image: rabbitmq:3.13-management-alpine
    container_name: rabbitmq2
    hostname: rabbitmq2
    ports:
      - "5673:5672"
      - "15673:15672"
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin123
      RABBITMQ_ERLANG_COOKIE: "CLUSTER_SECRET_COOKIE"
      RABBITMQ_NODENAME: rabbit@rabbitmq2
    volumes:
      - rabbitmq2-data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    networks:
      - rabbitmq-cluster
    depends_on:
      rabbitmq1:
        condition: service_healthy

  rabbitmq3:
    image: rabbitmq:3.13-management-alpine
    container_name: rabbitmq3
    hostname: rabbitmq3
    ports:
      - "5674:5672"
      - "15674:15672"
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin123
      RABBITMQ_ERLANG_COOKIE: "CLUSTER_SECRET_COOKIE"
      RABBITMQ_NODENAME: rabbit@rabbitmq3
    volumes:
      - rabbitmq3-data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    networks:
      - rabbitmq-cluster
    depends_on:
      rabbitmq1:
        condition: service_healthy

volumes:
  rabbitmq1-data:
  rabbitmq2-data:
  rabbitmq3-data:

networks:
  rabbitmq-cluster:
    driver: bridge
```

**File `rabbitmq.conf`:**
```ini
cluster_partition_handling = pause_minority

# Dùng khi tất cả nodes phụ thuộc một tập "anchor" nodes đáng tin cậy hơn
# (ví dụ multi-AZ có 2 nodes anchor). Không bật cùng lúc với pause_minority.
# cluster_partition_handling = pause_if_all_down
# cluster_partition_handling.pause_if_all_down.nodes.1 = rabbit@rabbitmq1
# cluster_partition_handling.pause_if_all_down.nodes.2 = rabbit@rabbitmq2
# cluster_partition_handling.pause_if_all_down.recover = autoheal
```

```bash
# Start cluster
cd day-08-clustering-ha/lab
docker compose -f docker-compose-cluster.yml up -d

# Wait for all nodes to start
sleep 30

# Join node 2 and 3 to cluster
docker exec rabbitmq2 rabbitmqctl stop_app
docker exec rabbitmq2 rabbitmqctl join_cluster rabbit@rabbitmq1
docker exec rabbitmq2 rabbitmqctl start_app

docker exec rabbitmq3 rabbitmqctl stop_app
docker exec rabbitmq3 rabbitmqctl join_cluster rabbit@rabbitmq1
docker exec rabbitmq3 rabbitmqctl start_app

# Verify cluster
docker exec rabbitmq1 rabbitmqctl cluster_status

# Partition handling đã được cấu hình persistent trong rabbitmq.conf.
# Không dùng rabbitmqctl eval cho lab này vì setting đó transient và mất sau restart.

# Management UI: 
# Node 1: http://localhost:15672
# Node 2: http://localhost:15673
# Node 3: http://localhost:15674
```

### 8.2 Lab 1: Quorum Queue Failover

```bash
# Init Go project
mkdir -p day-08-clustering-ha/lab && cd day-08-clustering-ha/lab
go mod init cluster-lab
go get github.com/rabbitmq/amqp091-go
```

**File `failover_demo.go`:**
```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

var nodes = []string{
	"amqp://admin:admin123@localhost:5672/",
	"amqp://admin:admin123@localhost:5673/",
	"amqp://admin:admin123@localhost:5674/",
}

type Event struct {
	ID        int       `json:"id"`
	Message   string    `json:"message"`
	Timestamp time.Time `json:"timestamp"`
	Node      string    `json:"connected_node"`
}

func main() {
	mode := "demo"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	switch mode {
	case "setup":
		setup()
	case "publish":
		publishContinuous()
	case "consume":
		consumeContinuous()
	default:
		setup()
		go consumeContinuous()
		time.Sleep(time.Second)
		publishContinuous()
	}
}

func connectWithFailover() (*amqp.Connection, string) {
	for _, node := range nodes {
		conn, err := amqp.Dial(node)
		if err == nil {
			log.Printf("Connected to: %s", node)
			return conn, node
		}
		log.Printf("Failed to connect to %s: %v", node, err)
	}
	log.Fatal("All nodes unreachable!")
	return nil, ""
}

func setup() {
	conn, _ := connectWithFailover()
	defer conn.Close()
	ch, _ := conn.Channel()
	defer ch.Close()

	// Declare durable exchange
	ch.ExchangeDeclare("cluster.events", "direct", true, false, false, false, nil)

	// Declare quorum queue — replicated across cluster
	_, err := ch.QueueDeclare("cluster.orders", true, false, false, false, amqp.Table{
		"x-queue-type":     "quorum",
		"x-delivery-limit": 5,
	})
	if err != nil {
		log.Printf("Queue declare: %v", err)
	}

	ch.QueueBind("cluster.orders", "order", "cluster.events", false, nil)
	log.Println("Quorum queue 'cluster.orders' created on cluster")
}

func publishContinuous() {
	var conn *amqp.Connection
	var ch *amqp.Channel
	var connNode string
	var confirmCh <-chan amqp.Confirmation
	var msgCount int64

	reconnect := func() {
		if conn != nil && !conn.IsClosed() {
			conn.Close()
		}
		conn, connNode = connectWithFailover()
		var err error
		ch, err = conn.Channel()
		if err != nil {
			log.Printf("Channel error: %v", err)
			return
		}
		ch.Confirm(false)
		confirmCh = ch.NotifyPublish(make(chan amqp.Confirmation, 1))
	}

	reconnect()
	defer conn.Close()

	// Monitor connection
	go func() {
		for {
			closeCh := make(chan *amqp.Error, 1)
			conn.NotifyClose(closeCh)
			amqpErr := <-closeCh
			if amqpErr != nil {
				log.Printf("CONNECTION LOST: %v — reconnecting...", amqpErr)
				time.Sleep(2 * time.Second)
				reconnect()
			}
		}
	}()

	ctx := context.Background()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	log.Println("Publishing every 1s. Try: docker stop rabbitmq1")

	for {
		select {
		case <-sig:
			log.Printf("Publisher stopped. Total messages: %d", atomic.LoadInt64(&msgCount))
			return
		case <-ticker.C:
			id := int(atomic.AddInt64(&msgCount, 1))
			event := Event{
				ID:        id,
				Message:   fmt.Sprintf("Order event #%d", id),
				Timestamp: time.Now(),
				Node:      connNode,
			}
			body, _ := json.Marshal(event)

			err := ch.PublishWithContext(ctx, "cluster.events", "order", false, false,
				amqp.Publishing{
					DeliveryMode: amqp.Persistent,
					ContentType:  "application/json",
					MessageId:    fmt.Sprintf("msg-%d", id),
					Body:         body,
				},
			)
			if err != nil {
				log.Printf("PUBLISH FAILED (msg %d): %v — will retry after reconnect", id, err)
				atomic.AddInt64(&msgCount, -1) // Revert counter
				continue
			}

			select {
			case confirm := <-confirmCh:
				if !confirm.Ack {
					log.Printf("PUBLISH NACKED (msg %d) — will retry", id)
					atomic.AddInt64(&msgCount, -1)
					continue
				}
				log.Printf("PUBLISHED+CONFIRMED: #%d via %s", id, connNode)
			case <-time.After(5 * time.Second):
				log.Printf("CONFIRM TIMEOUT (msg %d) — delivery state unknown, retry idempotently", id)
				atomic.AddInt64(&msgCount, -1)
			}
		}
	}
}

func consumeContinuous() {
	var conn *amqp.Connection
	var ch *amqp.Channel

	connect := func() {
		if conn != nil && !conn.IsClosed() {
			conn.Close()
		}
		conn, _ = connectWithFailover()
		ch, _ = conn.Channel()
		ch.Qos(5, 0, false)
	}

	connect()
	defer conn.Close()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	for {
		msgs, err := ch.Consume("cluster.orders", "cluster-consumer", false, false, false, false, nil)
		if err != nil {
			log.Printf("Consume error: %v — reconnecting...", err)
			time.Sleep(2 * time.Second)
			connect()
			continue
		}

		log.Println("Consumer started. Waiting for messages...")

		done := make(chan bool)
		go func() {
			for msg := range msgs {
				var event Event
				json.Unmarshal(msg.Body, &event)
				log.Printf("CONSUMED: #%d — %s (published via: %s)", event.ID, event.Message, event.Node)
				msg.Ack(false)
			}
			done <- true
		}()

		select {
		case <-sig:
			log.Println("Consumer stopped")
			return
		case <-done:
			log.Println("Channel closed — reconnecting...")
			time.Sleep(2 * time.Second)
			connect()
		}
	}
}
```

```bash
# Run demo
go run failover_demo.go setup
go run failover_demo.go consume  # Terminal 1
go run failover_demo.go publish  # Terminal 2

# === FAILOVER TEST ===
# Terminal 3: Identify quorum leader first, then stop exactly that node
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F/cluster.orders | jq .leader

# Example: if leader is rabbit@rabbitmq1
docker stop rabbitmq1

# Observe:
# - Publisher/Consumer briefly disconnect
# - Auto-reconnect to node2 or node3
# - Quorum queue elects new leader
# - Messages continue flowing after publisher confirms are received

# Bring node 1 back
docker start rabbitmq1
# Node 1 rejoins cluster, catches up
```

### 8.3 Lab 2: Cluster Status & Queue Distribution

```bash
# Cluster overview
docker exec rabbitmq1 rabbitmqctl cluster_status

# Quorum queue member info
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F/cluster.orders | jq '{
  name: .name,
  type: .type,
  leader: .leader,
  members: .members,
  online: .online,
  state: .state
}'

# All queues across cluster
curl -s -u admin:admin123 http://localhost:15672/api/queues | jq '.[] | {
  name: .name,
  type: .type,
  node: .node,
  state: .state,
  messages: .messages
}'

# Node health check
for port in 15672 15673 15674; do
  echo "=== Node on port $port ==="
  curl -s -u admin:admin123 "http://localhost:$port/api/healthchecks/node" | jq .status
done
```

### 8.4 Lab 3: Simulate Network Partition

```bash
# Isolate node 1 from the cluster network
NET=$(docker inspect rabbitmq1 --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}')
docker network disconnect "$NET" rabbitmq1 2>/dev/null || \
  docker exec rabbitmq1 iptables -A INPUT -p tcp --dport 25672 -j DROP 2>/dev/null || \
  echo "Note: network isolation may require --privileged containers"

# Alternative: just stop the node (simpler but not a true partition)
docker stop rabbitmq1

# Check cluster status from remaining nodes
docker exec rabbitmq2 rabbitmqctl cluster_status

# Observe: quorum queues on node2/3 continue serving
# Node 1 queues → leader migrated to node2 or node3

# Heal: bring node 1 back
docker start rabbitmq1
sleep 10
docker exec rabbitmq1 rabbitmqctl cluster_status
# Node 1 should rejoin and catch up
```

### 8.5 Cleanup

```bash
docker compose -f docker-compose-cluster.yml down -v
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **RabbitMQ cluster replicate metadata nhưng KHÔNG replicate message data mặc định. Tại sao thiết kế như vậy?** Nếu replicate tất cả messages đến tất cả nodes → vấn đề gì?

   *Hint: Bandwidth, disk I/O, throughput impact. Không phải tất cả queues đều cần replication. Quorum queues cho lựa chọn per-queue.*

2. **So sánh 3 partition handling strategies: ignore, pause_minority, autoheal.** Cho production e-commerce system, bạn chọn strategy nào và tại sao?

   *Hint: pause_minority — no split-brain, auto-recover when partition heals. E-commerce cần data consistency hơn 100% availability.*

3. **Tại sao RabbitMQ cluster nên dùng odd number nodes?** Cho scenario cụ thể khi even number (4 nodes) gây total outage mà odd number (3 nodes) không.

   *Hint: 4 nodes partition 2|2 → cả 2 sides = minority → total outage. 3 nodes partition 1|2 → minority pauses, majority serves.*

4. **Quorum queues xử lý network partition khác classic mirrored queues thế nào?** Tại sao quorum queues an toàn hơn?

   *Hint: Quorum = Raft = minority stops. Mirrored = async replication = both sides serve = split-brain.*

5. **Design question:** Bạn có RabbitMQ serving traffic từ 2 datacenters (US và EU). Thiết kế HA strategy:
   - Cluster hay Federation?
   - Bao nhiêu nodes mỗi DC?
   - Partition handling?
   - Client failover?

   *Hint: Cluster within DC (3 nodes each) + Federation between DCs. Low latency within cluster, WAN-tolerant federation.*

6. **Federation vs Shovel: khi nào dùng cái nào?** Cho 2 scenarios cụ thể.

   *Hint: Federation cho ongoing geo-replication. Shovel cho one-time migration hoặc specific queue forwarding.*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [RabbitMQ Clustering Guide](https://www.rabbitmq.com/clustering.html)
- [Quorum Queues](https://www.rabbitmq.com/quorum-queues.html)
- [Network Partitions](https://www.rabbitmq.com/partitions.html)
- [Federation Plugin](https://www.rabbitmq.com/federation.html)
- [Shovel Plugin](https://www.rabbitmq.com/shovel.html)

### Architecture & Design
- [RabbitMQ Cluster Sizing & Optimization — CloudAMQP](https://www.cloudamqp.com/blog/part4-rabbitmq-best-practice.html)
- [Quorum Queues and Why They Matter](https://blog.rabbitmq.com/posts/2020/04/quorum-queues-and-why-they-matter/)
- [Running RabbitMQ in Production — Pivotal](https://tanzu.vmware.com/developer/guides/rabbitmq-production/)

### Deep Dive
- [Raft Consensus Visualization](https://raft.github.io/)
- [CAP Theorem and RabbitMQ — CloudAMQP](https://www.cloudamqp.com/blog/cap-theorem-and-rabbitmq.html)
- [RabbitMQ Clustering — Under the Hood](https://www.youtube.com/watch?v=FzqjtU2x6YA)

### Videos
- [RabbitMQ Clustering Deep Dive — RabbitMQ Summit](https://www.youtube.com/watch?v=y4wTmLfbNJo)
- [Network Partitions in RabbitMQ — CloudAMQP](https://www.youtube.com/watch?v=FqBWGMH7e3Y)
- [Running Production RabbitMQ — GOTO Conference](https://www.youtube.com/watch?v=XjuiZM7JzPw)
