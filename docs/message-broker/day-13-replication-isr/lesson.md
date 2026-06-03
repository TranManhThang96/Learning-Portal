# Day 13: Kafka Replication & ISR — Leader/Follower, In-Sync Replicas, Availability vs Durability

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** mô hình replication của Kafka — leader/follower, tại sao không dùng quorum-based replication
2. **Nắm vững** ISR (In-Sync Replicas) — cơ chế hoạt động, điều kiện vào/ra ISR, ảnh hưởng đến durability
3. **Phân tích được** trade-off giữa availability vs durability thông qua `min.insync.replicas` và `unclean.leader.election.enable`
4. **Hiểu rõ** leader election — khi nào xảy ra, preferred leader, unclean leader election và hậu quả
5. **Thực hành** observe replication, kill broker, quan sát ISR shrink/expand, test data loss scenarios

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10 (topic, partition, broker, replication factor overview)
- Đã hoàn thành Day 11 (producer `acks` — đặc biệt `acks=all` và `min.insync.replicas`)
- Đã hoàn thành Day 12 (consumer group, offset management)
- Docker Compose Kafka cluster 3 brokers đang chạy

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Leader/follower replication model — fetch-based, không phải push-based
- ISR: định nghĩa, cách follower tham gia/bị loại khỏi ISR
- `min.insync.replicas` — quan hệ với `acks=all`, failure scenarios
- `unclean.leader.election.enable` — availability vs durability trade-off
- Leader election khi leader crash
- Hands-on: kill broker, quan sát ISR shrink, test data durability

### 🟡 Should Learn (nếu còn thời gian)
- High Watermark (HW) và Log End Offset (LEO) — commit semantics
- Preferred leader election và auto leader rebalance
- Replica lag monitoring và alerting
- Under-replicated partitions troubleshooting

### 🟢 Optional Deep Dive
- Replication protocol chi tiết (Fetch request/response, epoch-based fencing)
- ISR shrink/expand race conditions
- KRaft metadata replication (khác ISR-based replication)
- Kafka source code: ReplicaManager.scala, Partition.scala

---

## 4. Lý thuyết (Theory)

### 4.1 Replication Model — Tại sao Kafka không dùng Quorum?

#### WHY — Replication giải quyết vấn đề gì?

Một broker chạy trên 1 machine. Machine hỏng = data mất. Replication = giữ **nhiều bản sao** (replicas) của cùng data trên **nhiều machines**.

```
KHÔNG có replication:
  Broker 1: [P0] ← ghi tất cả vào đây
  
  Broker 1 hỏng → P0 MẤT HOÀN TOÀN → SERVICE DOWN

CÓ replication (factor=3):
  Broker 1: [P0-Leader]   ← producer ghi vào đây
  Broker 2: [P0-Follower] ← copy từ leader
  Broker 3: [P0-Follower] ← copy từ leader
  
  Broker 1 hỏng → P0-Follower trên Broker 2 hoặc 3 trở thành leader mới
  → KHÔNG MẤT DATA, service vẫn chạy
```

#### WHAT — Leader/Follower Model

Kafka dùng **single-leader replication** cho mỗi partition:

- **Leader**: nhận TẤT CẢ writes (từ producer) và serves reads (cho consumer)
- **Followers**: KHÔNG nhận writes trực tiếp, chỉ **replicate** (copy) data từ leader
- Mỗi partition có **đúng 1 leader** và **0+ followers**

```
Topic "orders", Partition 0, Replication Factor = 3:

  ┌─────────────────────────┐
  │    Broker 1              │
  │    P0 — LEADER           │◄── Producer writes here
  │    Log: [0][1][2][3][4]  │──► Consumer reads here
  └────────────┬─────────────┘
               │ FetchRequest
  ┌────────────▼─────────────┐
  │    Broker 2              │
  │    P0 — FOLLOWER         │
  │    Log: [0][1][2][3][4]  │  ← replicated (in-sync)
  └──────────────────────────┘
               │
  ┌────────────▼─────────────┐
  │    Broker 3              │
  │    P0 — FOLLOWER         │
  │    Log: [0][1][2][3]     │  ← replicated (1 record behind)
  └──────────────────────────┘
```

**Quan trọng**: Followers **pull** data từ leader (gửi FetchRequest), KHÔNG phải leader **push** data xuống followers. Giống consumer, followers là "consumers đặc biệt" luôn fetch latest data.

#### Kafka vs Quorum-based (Raft/Paxos)

```
Quorum-based replication (Raft):
  3 nodes → cần 2/3 (majority) đồng ý mới commit
  5 nodes → cần 3/5 majority
  
  Pro: Consistent — nếu majority commit, data safe
  Con: Throughput = throughput của node CHẬM NHẤT trong majority
       (vì phải đợi majority ACK)

Kafka ISR-based replication:
  3 replicas, ISR = {1, 2, 3}
  → Tất cả replica đang trong ISR phải ACK (khi acks=all)
  → Nhưng ISR có thể SHRINK! Slow replica bị loại ra
  
  Pro: Throughput không bị giới hạn bởi slow replica
       (slow replica bị đá ra khỏi ISR → không phải đợi nó)
  Con: Không còn clean leader candidate + unclean election bật = có thể mất data
```

**Insight**: Kafka chọn **ISR model** thay vì **quorum model** vì:
1. **Throughput cao hơn**: không bị bound bởi slow replica
2. **Linh hoạt hơn**: `f+1` replicas chịu được `f` failures (quorum cần `2f+1`)
3. **Trade-off linh hoạt**: admin chọn giữa availability vs durability qua config

### 4.2 ISR (In-Sync Replicas) — Ai "đủ" sync?

#### WHAT — ISR là gì?

ISR = tập hợp các replicas (bao gồm leader) đang **"sufficiently caught up"** với leader. Một follower được coi là in-sync khi nó không bị lag quá mức.

```
ISR = {Broker1(Leader), Broker2, Broker3}

Broker 1 (Leader):  [0][1][2][3][4][5][6][7]   LEO=8
Broker 2 (Follower): [0][1][2][3][4][5][6][7]   LEO=8  ← in-sync ✓
Broker 3 (Follower): [0][1][2][3][4][5]         LEO=6  ← lagging...

replica.lag.time.max.ms = 30000 (30 giây)

Nếu Broker 3 không fetch mới trong 30s:
  ISR = {Broker1, Broker2}  ← Broker3 bị loại!
  
Khi Broker 3 catch up lại:
  ISR = {Broker1, Broker2, Broker3}  ← Broker3 quay lại ISR
```

#### HOW — Điều kiện vào/ra ISR

```
Follower BỊ LOẠI khỏi ISR khi:
  1. Không gửi FetchRequest trong replica.lag.time.max.ms (30s mặc định)
     → Nguyên nhân: broker crash, GC pause, network partition, disk slow
  
  2. (Kafka cũ < 0.9) Lag > replica.lag.max.messages
     → Đã bị LOẠI BỎ vì gây ISR thrashing khi produce burst

Follower QUAY LẠI ISR khi:
  1. Catch up đến LEO (Log End Offset) của leader
  2. Đang gửi FetchRequests đều đặn
  → Controller thêm lại vào ISR
```

```properties
# Thời gian tối đa follower được phép lag trước khi bị đá khỏi ISR
replica.lag.time.max.ms=30000   # 30 giây (mặc định)

# Quá nhỏ (5s) → ISR thrashing (follower bị đá ra/vào liên tục khi GC pause)
# Quá lớn (120s) → Follower chậm vẫn ở ISR → acks=all phải đợi lâu
```

### 4.3 High Watermark (HW) & Log End Offset (LEO)

#### WHY — Consumer có thể đọc đến đâu?

Consumer KHÔNG thể đọc tất cả records mà leader có. Chỉ đọc được đến **High Watermark** — offset mà TẤT CẢ ISR replicas đã replicate.

```
Leader (Broker 1):    [0][1][2][3][4][5][6][7]
                                          ↑ LEO = 8
Follower (Broker 2):  [0][1][2][3][4][5][6]
                                        ↑ LEO = 7
Follower (Broker 3):  [0][1][2][3][4][5]
                                      ↑ LEO = 6

High Watermark = min(LEO of all ISR replicas) = 6

  [0][1][2][3][4][5] | [6][7]
  ← committed →        ← uncommitted →
  Consumer đọc được     Consumer KHÔNG đọc được
                        (chưa đủ replicas replicate)
```

**Tại sao cần High Watermark?**

```
Nếu consumer đọc được offset 7 (chưa replicate xong):
  → Leader crash → Broker 2 trở thành leader mới
  → Broker 2 chỉ có đến offset 6
  → Consumer đã đọc offset 7 nhưng new leader không có nó
  → DATA INCONSISTENCY!

Với High Watermark:
  → Consumer chỉ đọc đến offset 5 (committed)
  → Leader crash → Broker 2 thành leader
  → Consumer tiếp tục từ offset 6 → CONSISTENT!
```

#### HW Propagation Flow

```
Step 1: Producer gửi record (offset 8) đến Leader
  Leader:   [..][7][8]     LEO=9
  Follower: [..][7]        LEO=8
  HW = 8

Step 2: Follower fetch → nhận record 8
  Leader:   [..][7][8]     LEO=9
  Follower: [..][7][8]     LEO=9
  HW vẫn = 8 (follower chưa report LEO mới)

Step 3: Follower fetch TIẾP → kèm theo LEO=9
  Leader biết tất cả ISR đã LEO=9
  → HW tăng lên 9
  → Consumer bây giờ đọc được offset 8

→ HW LUÔN lag 1 fetch cycle so với actual replication
→ Đây là lý do Kafka có "replication latency"
```

### 4.4 `min.insync.replicas` — Cầu chì an toàn

#### WHAT — Kết hợp với `acks=all`

`min.insync.replicas` = số ISR replicas TỐI THIỂU cần có để broker chấp nhận write khi `acks=all`.

```
replication.factor = 3
min.insync.replicas = 2
acks = all

Scenario 1: 3 brokers healthy, ISR = {B1, B2, B3}
  Producer write → Leader (B1) ghi → B2, B3 ack
  → ISR size (3) >= min.insync (2) → WRITE SUCCESS ✓

Scenario 2: 1 broker down, ISR = {B1, B2}
  Producer write → Leader (B1) ghi → B2 ack
  → ISR size (2) >= min.insync (2) → WRITE SUCCESS ✓
  → Data safe trên 2 brokers

Scenario 3: 2 brokers down, ISR = {B1}
  Producer write → Leader (B1) ghi → chỉ 1 ISR
  → ISR size (1) < min.insync (2)
  → NotEnoughReplicasException → WRITE REJECTED ✗
  → Producer KHÔNG thể ghi → committed data trước đó không mất nếu unclean election vẫn tắt

  Trade-off: Chọn SAFETY (reject writes) thay vì RISK (ghi chỉ 1 copy)
```

#### Configuration Matrix — Chọn đúng cho production

| Replication Factor | min.insync.replicas | Chịu được failures | Trade-off |
|-------------------|--------------------|--------------------|-----------|
| 1 | 1 | 0 broker | ❌ Data loss khi broker chết |
| 2 | 1 | 1 broker (nhưng có thể mất data) | Risky — data chỉ trên 1 broker |
| 2 | 2 | 0 broker (1 chết → unavailable) | ❌ Over-protective |
| **3** | **2** | **1 broker** | **✅ Recommended production** |
| 3 | 3 | 0 broker | ❌ 1 chết → unavailable |
| 5 | 3 | 2 brokers | High durability, tốn resources |

**Production recommendation:**
```properties
# Topic-level config (hoặc broker default)
replication.factor=3
min.insync.replicas=2

# Producer config
acks=all   # Kết hợp với min.insync.replicas
```

**Tại sao `RF=3, min.insync=2` là sweet spot?**
- Chịu được 1 broker failure → writes vẫn thành công
- 2 copies tối thiểu trên 2 machines khác nhau → data safe
- Nếu 2 brokers chết → writes bị reject (safety) chứ không mất data
- Cost: 3x storage — chấp nhận được cho hầu hết production workloads

### 4.5 Leader Election — Ai thay thế Leader?

#### WHY — Leader chết thì sao?

Khi leader broker crash hoặc bị shutdown, partition cần leader mới để tiếp tục phục vụ reads và writes.

```
TRƯỚC khi leader crash:
  ISR = {B1(Leader), B2, B3}

  B1 crash! ✗

SAU leader election:
  Controller chọn leader mới TỪ ISR

  Option 1: B2 trở thành leader (B2 có data đầy đủ vì nằm trong ISR)
  ISR = {B2(Leader), B3}     ← NO DATA LOSS ✓

  Khi B1 restart:
    → B1 trở thành follower
    → B1 truncate log đến HW → fetch data mới từ B2 (leader mới)
    → B1 catch up → quay lại ISR
  ISR = {B2(Leader), B1, B3}
```

#### Clean vs Unclean Leader Election

```
Clean leader election (mặc định):
  ISR = {B1(Leader), B2, B3}
  B1 crash → chọn leader từ ISR → B2 hoặc B3
  → NO DATA LOSS ✓

Vấn đề: Nếu ISR = {B1(Leader)} (chỉ còn leader!)
  B1 crash → ISR rỗng → KHÔNG AI để chọn làm leader
  → Partition OFFLINE!
  → Reads và writes ĐỀU FAIL

Unclean leader election (mặc định OFF từ Kafka 0.11+):
  ISR = {B1(Leader)}
  B1 crash → ISR rỗng → KHÔNG có clean candidate
  
  Nếu unclean.leader.election.enable=true:
    → Chọn 1 follower NGOÀI ISR làm leader (ví dụ B3 dù nó lag behind)
    → B3 chỉ có data đến offset 100, leader cũ có đến offset 200
    → Records 101-200 MẤT VĨNH VIỄN!
    → Nhưng partition available lại → writes/reads tiếp tục
    
  Nếu unclean.leader.election.enable=false (mặc định):
    → Partition OFFLINE cho đến khi B1 quay lại
    → KHÔNG MẤT DATA nhưng SERVICE DOWN
```

```properties
# Mặc định: false (ưu tiên durability over availability)
unclean.leader.election.enable=false

# Set true CHỈ khi availability > durability:
# ví dụ: metrics, logs không critical
unclean.leader.election.enable=true
```

#### Preferred Leader Election

```
Khi tạo topic, Kafka chọn "preferred leader" cho mỗi partition:
  Partition 0: preferred leader = Broker 1
  Partition 1: preferred leader = Broker 2
  Partition 2: preferred leader = Broker 3
  → Leaders phân tải đều

Sau nhiều lần failover:
  Partition 0: leader = Broker 2 (B1 crash & recover, nhưng leader vẫn ở B2)
  Partition 1: leader = Broker 2
  Partition 2: leader = Broker 2
  → Broker 2 overloaded! (3 leaders)

Auto leader rebalance:
  auto.leader.rebalance.enable=true   (mặc định)
  leader.imbalance.check.interval.seconds=300
  leader.imbalance.per.broker.percentage=10

  → Controller kiểm tra: B2 có 3 leaders, expected 1 → imbalance > 10%
  → Di chuyển leader P0 về B1, leader P2 về B3
  → Leaders phân tải đều lại ✓
```

### 4.6 Replication Flow Chi Tiết

```
Producer          Leader (B1)              Follower (B2)           Follower (B3)
   │                  │                        │                       │
   │ ProduceRequest   │                        │                       │
   │ acks=all         │                        │                       │
   │─────────────────►│                        │                       │
   │                  │ Append to local log     │                       │
   │                  │ LEO = 8                │                       │
   │                  │                        │                       │
   │                  │◄───FetchRequest────────│ (follower pulls)      │
   │                  │────FetchResponse──────►│                       │
   │                  │    (data + leader HW)  │ Append to local log   │
   │                  │                        │ LEO = 8               │
   │                  │                        │                       │
   │                  │◄─────────────FetchRequest─────────────────────│
   │                  │──────────────FetchResponse───────────────────►│
   │                  │                        │                 LEO = 8│
   │                  │                        │                       │
   │                  │ All ISR caught up      │                       │
   │                  │ HW = 8                 │                       │
   │◄─────ACK─────────│                        │                       │
   │ (success!)       │                        │                       │
```

**Key insight**: Replication xảy ra qua **FetchRequest** — cùng mechanism mà consumer dùng. Followers là "internal consumers" luôn fetch latest data.

---

## 5. Trade-off Analysis

### Availability vs Durability — "CAP at the Partition Level"

| Config | Availability | Durability | Khi nào dùng |
|--------|-------------|-----------|-------------|
| `RF=3, min.insync=1, unclean=true` | ✅ Cao nhất | ❌ Thấp | Metrics, non-critical logs |
| `RF=3, min.insync=2, unclean=false` | ✅ Tốt | ✅ Tốt | **Production default** |
| `RF=3, min.insync=3, unclean=false` | ❌ Fragile | ✅ Cao nhất | Không recommend |
| `RF=5, min.insync=3, unclean=false` | ✅ Tốt | ✅ Rất cao | Financial, regulatory |

### Acks + Replication Matrix

```
                    ┌─────────────────────────────────────────────────┐
                    │           min.insync.replicas                    │
                    │     1              2              3              │
  ┌─────────────┬──┼───────────────┼──────────────┼──────────────────┤
  │ acks=0      │  │ No guarantee  │ No guarantee │ No guarantee     │
  │             │  │ (acks=0 bỏ    │ (min.insync  │ (acks=0 = fire   │
  │             │  │  qua acks)    │  IGNORED)    │  and forget)     │
  ├─────────────┤  ├───────────────┼──────────────┼──────────────────┤
  │ acks=1      │  │ Leader ack    │ Leader ack   │ Leader ack       │
  │             │  │ Có thể mất    │ (min.insync  │ (min.insync      │
  │             │  │ nếu leader    │  IGNORED     │  IGNORED cho     │
  │             │  │ crash         │  cho acks=1) │  acks=1)         │
  ├─────────────┤  ├───────────────┼──────────────┼──────────────────┤
  │ acks=all    │  │ All ISR ack   │ All ISR ack  │ All ISR ack      │
  │             │  │ ISR có thể    │ Cần ≥2 ISR   │ Cần ≥3 ISR      │
  │             │  │ chỉ có 1      │ → rejects    │ → rất dễ bị     │
  │             │  │ → single      │ nếu chỉ 1    │ unavailable      │
  │             │  │ point of fail │ ✅ RECOMMEND  │ ❌ Don't use     │
  └─────────────┘  └───────────────┴──────────────┴──────────────────┘
```

### Replication Factor Cost

| RF | Storage Overhead | Network Overhead | Failure Tolerance | Latency (acks=all) |
|----|-----------------|------------------|-------------------|--------------------|
| 1 | 1x | 0 | 0 brokers | ~2ms |
| 2 | 2x | 1x produce throughput | 1 broker (nhưng risky) | ~5ms |
| **3** | **3x** | **2x produce throughput** | **1 broker (safe)** | **~10-15ms** |
| 5 | 5x | 4x produce throughput | 2 brokers | ~15-25ms |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Production baseline: `RF=3, min.insync=2, acks=all`, `unclean.leader.election.enable=false`**. Đây là sweet spot cho hầu hết workloads: chịu 1 broker failure mà writes vẫn có thể thành công nếu ISR còn ít nhất 2 replicas và còn clean leader candidate. Durability chỉ được claim trong boundary đó; nếu ISR shrink dưới `min.insync`, Kafka sẽ từ chối write thay vì nhận rủi ro mất committed data.

2. **Giữ `unclean.leader.election.enable=false`** (mặc định). Data loss vĩnh viễn nguy hiểm hơn temporary unavailability. Chỉ bật cho topics thực sự expendable.

3. **Monitor under-replicated partitions**: Alert khi `UnderReplicatedPartitions > 0`. Đây là dấu hiệu đầu tiên của cluster health issue.

4. **`replica.lag.time.max.ms` phù hợp**: Mặc định 30s thường OK. Tăng lên 60s nếu brokers có occasional GC pauses lâu. Giảm xuống 10s nếu cần detect failure nhanh hơn.

5. **Spread replicas across racks/AZs**: Dùng `broker.rack` config để Kafka tự động phân bổ replicas qua các rack/availability zones khác nhau.

```properties
# Broker config
broker.rack=us-east-1a   # trên broker 1
broker.rack=us-east-1b   # trên broker 2
broker.rack=us-east-1c   # trên broker 3
# → Kafka tự động đặt replicas trên các racks khác nhau
```

6. **Preferred leader election**: Giữ `auto.leader.rebalance.enable=true` để leaders phân tải đều across brokers. Nếu tắt, phải chạy `kafka-leader-election.sh` thủ công.

### Common Pitfalls

1. **❌ `min.insync.replicas = replication.factor`**: Nếu `RF=3, min.insync=3`, chỉ cần 1 broker chết → writes fail TOÀN BỘ. Luôn set `min.insync < RF`.

2. **❌ `acks=all` mà `min.insync.replicas=1`**: Vô nghĩa! `acks=all` chỉ cần TẤT CẢ ISR ack. Nếu ISR chỉ còn leader (1 replica), `acks=all` = `acks=1`. Phải kết hợp `min.insync=2` để có ý nghĩa.

3. **❌ Quên monitor ISR shrink**: ISR shrink = follower bị lag. Nếu không monitor, ISR dần chỉ còn leader, `acks=all` không còn bảo vệ gì. Alert trên metric `IsrShrinksPerSec`.

4. **❌ Tất cả replicas trên cùng rack/machine**: 1 rack mất điện → mất TẤT CẢ replicas → data loss. Phải dùng `broker.rack` để spread.

5. **❌ Restart tất cả brokers cùng lúc**: Rolling restart (1 broker at a time) để luôn có đủ ISR. Restart cùng lúc = tất cả partitions offline.

6. **❌ `replica.lag.time.max.ms` quá nhỏ (< 10s)**: Follower bị đá khỏi ISR chỉ vì minor GC pause → ISR thrashing → `acks=all` latency spike.

---

## 7. Performance Considerations

### Replication Metrics Quan Trọng

| Metric | Ý nghĩa | Alert Threshold |
|--------|---------|----------------|
| `UnderReplicatedPartitions` | Partitions có ISR < RF | > 0 |
| `UnderMinIsrPartitionCount` | Partitions có ISR < min.insync | > 0 (CRITICAL) |
| `IsrShrinksPerSec` | Tốc độ ISR shrink | > 0 sustained |
| `IsrExpandsPerSec` | Tốc độ ISR expand | Should follow shrinks |
| `FailedIsrUpdatesPerSec` | ISR update failures | > 0 |
| `ReplicaMaxLag` | Max offset lag of follower | > 1000 |
| `ActiveControllerCount` | Số active controllers | != 1 |
| `LeaderElectionRateAndTimeMs` | Leader election frequency + time | Tăng đột ngột |

### Replication Impact trên Performance

```
Replication factor ảnh hưởng:

1. Network bandwidth:
   RF=1: Producer → Broker (1 copy)
   RF=3: Producer → Broker (1 copy) + Broker → 2 Followers (2 copies)
   → Network OUT tăng RF-1 lần cho mỗi byte produced
   → Cluster tổng bandwidth = produce_bandwidth × RF

2. Latency (acks=all):
   RF=1: Producer → Leader ack → ~2ms
   RF=3: Producer → Leader → wait followers → ~10-15ms
   → Latency tăng do đợi followers replicate

3. Disk:
   RF=3: 3x disk space so với RF=1
   → Plan disk capacity = data_size × RF × (1 + overhead)

4. CPU:
   Minimal impact — replication chủ yếu I/O bound

Rule of thumb:
  Produce bandwidth 100 MB/s, RF=3:
  → Total disk write: 300 MB/s across cluster
  → Total internal network: 200 MB/s (follower fetches)
  → Latency (acks=all): +5-10ms so với acks=1
```

### Tuning Replication Performance

```properties
# Follower fetch tuning
replica.fetch.max.bytes=1048576        # 1MB max per fetch (mặc định)
replica.fetch.wait.max.ms=500          # Max đợi trước khi trả response rỗng
replica.socket.receive.buffer.bytes=65536

# Số threads dùng cho replication
num.replica.fetchers=1                 # Default 1, tăng nếu nhiều partitions
# Rule: 1 fetcher per 1000-2000 partitions per broker

# ISR sensitivity
replica.lag.time.max.ms=30000          # 30s (production default)
```

---

## 8. Hands-on Lab

### 8.1 Setup — Sử dụng cluster từ Day 10

```bash
# Đảm bảo 3-broker cluster đang chạy
docker compose ps

# Tạo topic cho lab với RF=3
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic replication-lab \
  --partitions 3 \
  --replication-factor 3 \
  --config min.insync.replicas=2

# Verify topic config
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --describe --topic replication-lab
```

Output mong đợi:
```
Topic: replication-lab  Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3
Topic: replication-lab  Partition: 1  Leader: 2  Replicas: 2,3,1  Isr: 2,3,1
Topic: replication-lab  Partition: 2  Leader: 3  Replicas: 3,1,2  Isr: 3,1,2
```

### 8.2 Go Lab Setup

```bash
mkdir -p day-13-lab && cd day-13-lab
go mod init day13-replication-isr
go get github.com/segmentio/kafka-go
```

### 8.3 Replication Observer — Xem ISR realtime

```go
// isr_observer.go — Monitor ISR changes in real-time
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sort"
	"strings"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
)

func main() {
	topic := "replication-lab"
	brokers := []string{"localhost:9092"}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; cancel() }()

	fmt.Println("=== ISR Observer ===")
	fmt.Println("Monitoring ISR changes. Kill a broker to see ISR shrink!")
	fmt.Println("Press Ctrl+C to stop.\n")

	prevState := ""

	ticker := time.NewTicker(3 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			fmt.Println("Observer stopped.")
			return
		case <-ticker.C:
			conn, err := kafka.Dial("tcp", brokers[0])
			if err != nil {
				log.Printf("Dial error: %v", err)
				continue
			}

			partitions, err := conn.ReadPartitions(topic)
			conn.Close()
			if err != nil {
				log.Printf("ReadPartitions error: %v", err)
				continue
			}

			var state strings.Builder
			for _, p := range partitions {
				isrIDs := make([]int, len(p.Isr))
				for i, b := range p.Isr {
					isrIDs[i] = b.ID
				}
				sort.Ints(isrIDs)

				replicaIDs := make([]int, len(p.Replicas))
				for i, b := range p.Replicas {
					replicaIDs[i] = b.ID
				}
				sort.Ints(replicaIDs)

				isrStatus := "✅"
				if len(p.Isr) < len(p.Replicas) {
					isrStatus = "⚠️  UNDER-REPLICATED"
				}

				line := fmt.Sprintf("  P%d: Leader=%d | Replicas=%v | ISR=%v %s\n",
					p.ID, p.Leader.ID, replicaIDs, isrIDs, isrStatus)
				state.WriteString(line)
			}

			currentState := state.String()
			if currentState != prevState {
				fmt.Printf("[%s] ISR Changed!\n%s\n",
					time.Now().Format("15:04:05"), currentState)
				prevState = currentState
			}
		}
	}
}
```

### 8.4 Durability Test — Kill Broker, Test Data Loss

```go
// durability_demo.go — Send messages, kill broker, verify no data loss
// Không đặt tên file là *_test.go nếu muốn chạy bằng `go run`.
package main

import (
	"context"
	"fmt"
	"log"
	"os/exec"
	"time"

	"github.com/segmentio/kafka-go"
)

func main() {
	topic := "durability-test"
	brokers := []string{"localhost:9092"}

	// Tạo topic
	conn, err := kafka.Dial("tcp", brokers[0])
	if err != nil {
		log.Fatal(err)
	}
	conn.CreateTopics(kafka.TopicConfig{
		Topic:             topic,
		NumPartitions:     1,
		ReplicationFactor: 3,
		ConfigEntries: []kafka.ConfigEntry{
			{ConfigName: "min.insync.replicas", ConfigValue: "2"},
		},
	})
	conn.Close()
	time.Sleep(2 * time.Second)

	// Phase 1: Gửi 100 messages với acks=all
	fmt.Println("=== Phase 1: Sending 100 messages with acks=all ===")
	writer := &kafka.Writer{
		Addr:         kafka.TCP(brokers[0]),
		Topic:        topic,
		Balancer:     &kafka.RoundRobin{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 1 * time.Millisecond,
	}

	sentCount := 0
	for i := 0; i < 100; i++ {
		err := writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(fmt.Sprintf("key-%03d", i)),
			Value: []byte(fmt.Sprintf("critical-data-%03d", i)),
		})
		if err != nil {
			fmt.Printf("Send error at msg %d: %v\n", i, err)
			continue
		}
		sentCount++
	}
	writer.Close()
	fmt.Printf("Sent: %d/100 messages\n\n", sentCount)

	// Phase 2: Kill leader broker
	fmt.Println("=== Phase 2: Killing a broker ===")
	fmt.Println("Stopping kafka-3...")
	exec.Command("docker", "stop", "kafka-3").Run()
	time.Sleep(5 * time.Second)

	// Phase 3: Gửi thêm 50 messages (ISR giảm nhưng >= min.insync=2)
	fmt.Println("=== Phase 3: Sending 50 more messages (1 broker down) ===")
	writer2 := &kafka.Writer{
		Addr:         kafka.TCP(brokers[0]),
		Topic:        topic,
		Balancer:     &kafka.RoundRobin{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 1 * time.Millisecond,
	}

	sentAfterKill := 0
	for i := 100; i < 150; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		err := writer2.WriteMessages(ctx, kafka.Message{
			Key:   []byte(fmt.Sprintf("key-%03d", i)),
			Value: []byte(fmt.Sprintf("critical-data-%03d", i)),
		})
		cancel()
		if err != nil {
			fmt.Printf("Send error at msg %d: %v\n", i, err)
			continue
		}
		sentAfterKill++
	}
	writer2.Close()
	fmt.Printf("Sent after kill: %d/50 messages\n\n", sentAfterKill)

	// Phase 4: Restart broker và verify data
	fmt.Println("=== Phase 4: Restarting broker and verifying data ===")
	exec.Command("docker", "start", "kafka-3").Run()
	fmt.Println("Waiting 15s for broker to rejoin cluster...")
	time.Sleep(15 * time.Second)

	// Đọc lại tất cả messages
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  brokers,
		Topic:    topic,
		GroupID:  fmt.Sprintf("durability-checker-%d", time.Now().UnixNano()),
		MaxBytes: 10e6,
	})
	defer reader.Close()

	receivedCount := 0
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		_, err := reader.FetchMessage(ctx)
		cancel()
		if err != nil {
			break
		}
		receivedCount++
	}

	totalSent := sentCount + sentAfterKill
	fmt.Printf("\n=== Results ===\n")
	fmt.Printf("Total sent:     %d\n", totalSent)
	fmt.Printf("Total received: %d\n", receivedCount)
	fmt.Printf("Data loss:      %d messages\n", totalSent-receivedCount)

	if receivedCount >= totalSent {
		fmt.Println("\n✅ No data loss observed in this lab failure mode.")
		fmt.Println("   Guarantee depends on acks=all + min.insync.replicas=2 + unclean election disabled + a clean ISR leader remaining.")
	} else {
		fmt.Println("\n❌ DATA LOSS detected!")
	}
}
```

Run và cleanup:

```bash
go run durability_demo.go

# Sau lab, đảm bảo broker bị stop đã quay lại và topic test được xóa nếu không dùng nữa.
docker start kafka-2 kafka-3 2>/dev/null || true
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --delete --topic durability-test
```

### 8.5 Unclean Leader Election Demo

Đây là lab **nguy hiểm** và chỉ chạy trên throwaway cluster/topic. Không dùng code Go copy-paste kiểu stop vài broker rồi kết luận "data loss": với KRaft combined broker/controller, stop 2 containers có thể làm mất controller quorum trước khi chứng minh được unclean election.

Mục tiêu proof đúng:
1. Bật `unclean.leader.election.enable=true` chỉ trên throwaway topic.
2. Tạo một replica ngoài ISR bằng cách làm nó lag rồi ghi thêm records.
3. Làm mất toàn bộ clean ISR nhưng vẫn giữ controller quorum sống.
4. Chứng minh leader mới là replica ngoài ISR và log end offset thấp hơn marker đã ghi.
5. Restore config/topic sau lab.

```bash
# 1. Tạo throwaway topic cho unclean proof
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --if-not-exists \
  --topic unclean-demo \
  --partitions 1 \
  --replication-factor 3 \
  --config min.insync.replicas=1 \
  --config unclean.leader.election.enable=true

docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --describe --topic unclean-demo

# 2. Từ output trên, ghi lại Leader, Replicas, Isr.
# Chọn một follower làm LAGGING_REPLICA, stop đúng container broker đó để nó rời ISR.
# Ví dụ nếu follower lagging là broker 3:
docker stop kafka-3

# 3. Ghi marker sau khi lagging replica đã rời ISR.
docker exec kafka-1 kafka-producer-perf-test.sh \
  --topic unclean-demo \
  --num-records 100 \
  --record-size 100 \
  --throughput -1 \
  --producer-props bootstrap.servers=localhost:9094 acks=all

docker exec kafka-1 kafka-get-offsets.sh \
  --bootstrap-server localhost:9094 --topic unclean-demo

# 4. Proof unclean election chỉ hợp lệ nếu controller quorum vẫn sống.
# Trên cluster production-like, dùng dedicated controllers và chỉ stop broker replicas.
# Stop leader + remaining in-sync replica để chỉ còn lagging replica là candidate.
# Sau đó start lagging replica nếu nó đang stop và describe topic.
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --describe --topic unclean-demo

# Acceptance criteria:
# - Topic config có unclean.leader.election.enable=true.
# - Leader mới không nằm trong ISR trước khi failure.
# - Log end offset sau unclean election < log end offset marker trước failure.
# Nếu không đủ 3 điều này, lab chỉ mới chứng minh ISR shrink/offline partition, chưa chứng minh data loss.

# 5. Cleanup/restore bắt buộc
docker start kafka-1 kafka-2 kafka-3 2>/dev/null || true
docker exec kafka-1 kafka-configs.sh --bootstrap-server localhost:9094 \
  --entity-type topics --entity-name unclean-demo \
  --alter --delete-config unclean.leader.election.enable
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --delete --topic unclean-demo
```

### 8.6 Monitoring Commands

```bash
# Xem ISR cho tất cả topics
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --describe --under-replicated-partitions

# Xem chi tiết replication cho 1 topic
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --describe --topic replication-lab

# Xem log dirs (disk usage per partition per broker)
docker exec kafka-1 kafka-log-dirs.sh --bootstrap-server localhost:9094 \
  --describe --topic-list replication-lab

# Preferred leader election (thủ công)
docker exec kafka-1 kafka-leader-election.sh --bootstrap-server localhost:9094 \
  --election-type preferred --all-topic-partitions

# Thay đổi min.insync.replicas runtime
docker exec kafka-1 kafka-configs.sh --bootstrap-server localhost:9094 \
  --entity-type topics --entity-name replication-lab \
  --alter --add-config min.insync.replicas=2
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **ISR = {B1(Leader), B2}. Kafka có RF=3, min.insync=2, acks=all. B2 crash. Producer write có thành công không?** Giải thích chi tiết. (Hint: ISR size sau khi B2 crash)

2. **Giải thích sự khác biệt giữa High Watermark (HW) và Log End Offset (LEO).** Tại sao consumer chỉ đọc được đến HW? Cho scenario data inconsistency nếu consumer đọc beyond HW. (Hint: leader crash before replication)

3. **Tại sao Kafka dùng ISR-based replication thay vì quorum (Raft)?** So sánh trade-off cụ thể. Khi nào bạn muốn quorum thay vì ISR? (Hint: throughput vs consistency)

4. **`min.insync.replicas=3` với `replication.factor=3` — tại sao đây là config TỆ?** Cho scenario cụ thể. (Hint: 1 broker maintenance = unavailable)

5. **Unclean leader election: availability vs durability trade-off.** Khi nào bạn BẬT unclean leader election? Khi nào TUYỆT ĐỐI KHÔNG? (Hint: financial data vs metric data)

6. **Broker 1 là leader cho 80% partitions của cluster. Điều gì xảy ra?** Làm thế nào để fix? (Hint: preferred leader election, broker.rack)

7. **Tại sao `replica.lag.time.max.ms` à time-based chứ không phải offset-based?** Kafka cũ dùng offset-based (`replica.lag.max.messages`) — nó có vấn đề gì? (Hint: produce burst)

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Replication Design](https://kafka.apache.org/documentation/#replication) — Official replication docs
- [Kafka Broker Configuration — Replication](https://kafka.apache.org/documentation/#brokerconfigs_replica.lag.time.max.ms)
- [KIP-101: Alter Replication Protocol to use Leader Epoch](https://cwiki.apache.org/confluence/display/KAFKA/KIP-101+-+Alter+Replication+Protocol+to+use+Leader+Epoch+rather+than+High+Watermark+for+Truncation)

### Blog Posts Chất Lượng
- [Kafka Replication: The Complete Guide](https://www.conduktor.io/kafka/kafka-topic-replication/) — Conduktor
- [In-Sync Replicas (ISR) in Apache Kafka](https://www.confluent.io/blog/hands-free-kafka-replication-a-lesson-in-operational-simplicity/) — Confluent
- [Kafka Data Durability and Availability](https://strimzi.io/blog/2022/03/08/kafka-data-durability/) — Strimzi
- [ISR, OSR, and Under-Replicated Partitions](https://www.conduktor.io/kafka/kafka-topic-replication/) — Conduktor

### Videos
- [Apache Kafka Replication Deep Dive](https://www.youtube.com/watch?v=yINVPV2TJ8E) — Kafka Summit
- [Understanding Kafka ISR](https://www.youtube.com/watch?v=Ki2D2o-IVLk) — Confluent
- [When Kafka Fails: Lessons from Production](https://www.youtube.com/watch?v=AJRHhBdO4wA) — Kafka Summit
