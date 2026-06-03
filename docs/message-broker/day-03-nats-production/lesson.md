# Day 3: NATS Production — Clustering, Security & Monitoring

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu** kiến trúc NATS clustering và tại sao cần cluster cho production
2. **Phân biệt** được full mesh cluster, leaf nodes, và super-cluster — khi nào dùng topology nào
3. **Cấu hình** được authentication và phân quyền cơ bản; hiểu TLS encryption cần cấu hình ở client, route, leaf-node scope nào
4. **Setup** monitoring với HTTP endpoints, Prometheus exporter, và NATS CLI
5. **Đánh giá** được khi nào chọn NATS và khi nào KHÔNG nên chọn NATS (decision framework)

## 2. Kiến thức nền (Prerequisites)

- Day 1: NATS core (subject, pub/sub, queue groups, request-reply)
- Day 2: JetStream (stream, consumer, ack, retention)
- Hiểu cơ bản về TLS/SSL, authentication concepts
- Docker Compose cho multi-container setup

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- NATS Clustering: full mesh, route-based discovery
- JetStream trong cluster: Raft consensus, replication
- Authentication cơ bản: token, user/password, NKeys
- Monitoring: HTTP endpoints, NATS CLI, metrics quan trọng
- Decision framework: khi nào chọn / không chọn NATS

### 🟡 Should Learn (nếu còn thời gian)
- Leaf nodes architecture
- TLS encryption: config và certificate lifecycle
- JWT/NKey decentralized auth
- Prometheus + Grafana monitoring setup
- Graceful shutdown & rolling upgrades

### 🟢 Optional Deep Dive
- Super-cluster (gateway) cho multi-region
- NATS account system và multi-tenancy
- Operator mode (nsc tool)
- NATS vs service mesh (Istio, Linkerd)

---

## 4. Lý thuyết (Theory)

### 4.1 NATS Clustering — WHY?

#### Vấn đề của single node

```
┌──────────┐        ┌──────────┐
│ Service A│──────> │ NATS ❌   │ <────── Service B
│          │        │ (crash)  │
└──────────┘        └──────────┘
     ↓
 Toàn bộ messaging dừng hoạt động
 → Single point of failure
```

**Production yêu cầu:**
- ✅ High availability — 1 node chết, hệ thống vẫn chạy
- ✅ Horizontal scaling — thêm node để tăng throughput
- ✅ Fault tolerance — tự động failover
- ✅ JetStream replication — data không mất khi node chết

#### HOW — Full Mesh Clustering

NATS cluster là **full mesh** — mỗi node kết nối trực tiếp với tất cả nodes khác:

```
┌──────────┐      route      ┌──────────┐
│  NATS-1  │◄──────────────►│  NATS-2  │
│  :4222   │                 │  :4223   │
└────┬─────┘                 └────┬─────┘
     │    ╲                  ╱    │
     │     ╲    route       ╱     │
     │      ╲              ╱      │
     │       ╲            ╱       │
     │        ▼          ▼        │
     │       ┌──────────┐        │
     │       │  NATS-3  │        │
     │       │  :4224   │        │
     │       └──────────┘        │
     │                            │
  clients                     clients
  connect                     connect
  to any node                 to any node
```

**Đặc điểm:**
- Client kết nối vào **bất kỳ node nào** — các node tự route messages theo subscription interest
- Subscribe trên node 1, publish trên node 2 → message vẫn đến subscriber
- Node chết → client tự động reconnect sang node khác (client library built-in)
- **Gossip protocol**: Nodes tự discover nhau, thêm node mới chỉ cần point đến 1 node có sẵn

**Routing nuance:** NATS core là interest-based routing. Cluster propagate subscription interest giữa nodes, rồi chỉ forward message qua route có subscriber match. Không phải mọi publish đều bị broadcast đến mọi node. JetStream replication là luồng riêng: stream leader replicate data đến replicas theo Raft, không đồng nghĩa với core message routing.

#### JetStream trong Cluster — Raft Consensus

Khi cluster có JetStream, mỗi stream được replicate qua **Raft consensus**:

```
Stream "ORDERS" (replicas: 3)
┌──────────┐     ┌──────────┐     ┌──────────┐
│  NATS-1  │     │  NATS-2  │     │  NATS-3  │
│  LEADER  │────>│ FOLLOWER │     │ FOLLOWER │
│ [data]   │     │ [data]   │     │ [data]   │
└──────────┘     └──────────┘     └──────────┘
     ↑
  Writes go
  to leader
```

- **Leader** nhận writes, replicate đến followers
- **Majority phải ack** trước khi write thành công (2/3 nodes cho cluster 3 nodes)
- Leader chết → Raft bầu leader mới tự động (~500ms-2s)
- **Rule of thumb**: cluster nên có **số lẻ nodes** (3, 5) để tránh split-brain

#### Cluster Size Trade-offs

| Cluster size | Fault tolerance | Write latency | Consistency |
|-------------|----------------|---------------|-------------|
| **1 node** | ❌ Không | Thấp nhất | N/A |
| **3 nodes** | 1 node fail OK | Trung bình (+1 RTT) | Recommended cho production |
| **5 nodes** | 2 nodes fail OK | Cao hơn (+1-2 RTT) | Critical systems, multi-AZ |

---

### 4.2 Leaf Nodes — Edge Computing & Multi-region

#### WHY — Khi nào cần Leaf Nodes?

Full mesh cluster có giới hạn:
- Subscription interest phải được propagate trong cluster; nếu topology trải rộng nhiều region, route table và đường WAN trở thành chi phí vận hành đáng kể
- Cross-region full mesh → latency cao, bandwidth tốn kém
- Không phải mọi region cần nhận mọi subject

#### WHAT — Leaf Node là gì?

Leaf node kết nối vào cluster nhưng **chỉ forward messages khi cần** (có subscriber match):

```
                    ┌─ Hub Cluster ──────────────┐
                    │ NATS-1 ◄──► NATS-2 ◄──► NATS-3 │
                    └──────┬──────────┬─────────┘
                           │          │
                    ┌──────┘          └──────┐
                    │                        │
              ┌─────┴─────┐           ┌─────┴─────┐
              │ Leaf Node │           │ Leaf Node │
              │ (Edge/VN) │           │ (Edge/US) │
              │ local     │           │ local     │
              │ clients   │           │ clients   │
              └───────────┘           └───────────┘
```

**Đặc điểm:**
- Leaf node chỉ forward subscription interest → tiết kiệm bandwidth
- Clients ở edge kết nối vào leaf node local → latency thấp
- Leaf node có thể hoạt động **offline** (nếu clients chỉ giao tiếp local)
- Reconnect tự động khi network phục hồi

#### Use cases

| Use case | Topology |
|----------|----------|
| **Microservices trong 1 DC** | 3-node full mesh cluster |
| **Multi-region** | Hub cluster + leaf nodes per region |
| **Edge/IoT** | Hub cluster + leaf nodes ở edge locations |
| **Development** | Leaf node local kết nối staging cluster |

---

### 4.3 Security — Authentication & Encryption

#### Authentication Methods

NATS hỗ trợ nhiều phương thức auth, từ đơn giản đến enterprise-grade:

**1. Token Authentication (đơn giản nhất)**
```
Server config:
  authorization {
    token: "s3cr3t-t0k3n"
  }

Client connect:
  nats://s3cr3t-t0k3n@localhost:4222
```
- ✅ Đơn giản, nhanh
- ❌ Tất cả clients dùng chung 1 token, không phân quyền

**2. User/Password**
```
Server config:
  authorization {
    users = [
      {user: "order-svc", password: "pass1", permissions: {
        publish: {allow: ["orders.>"]}
        subscribe: {allow: ["orders.>", "payments.>"]}
      }}
      {user: "payment-svc", password: "pass2", permissions: {
        publish: {allow: ["payments.>"]}
        subscribe: {allow: ["orders.created"]}
      }}
    ]
  }
```
- ✅ Per-user permissions (publish/subscribe restrictions)
- ❌ Passwords trong config file (nếu dùng, cần encrypt)

**JetStream permission nuance:** JetStream management và publish ack đi qua request-reply subjects. Client thường cần:
- `publish` đến `$JS.API.>` để gọi JetStream API.
- `subscribe` đến `_INBOX.>` để nhận reply từ server.
- Quyền publish/subscribe domain subjects riêng, ví dụ `orders.>`.

Không nên cấp `$JS.API.>` vào `subscribe` như một cách "mở JetStream"; đó là API subject mà client publish request đến. Với production, tách quyền admin stream/consumer khỏi quyền app publish event.

**3. NKeys (recommended cho production)**
```
NKey = Ed25519 public/private key pair
- Server chỉ biết public key
- Client dùng private key để authenticate (challenge-response)
- Không bao giờ truyền secret qua network
```
- ✅ Secure — private key không bao giờ rời client
- ✅ Không cần shared secrets
- ❌ Complex hơn user/password

**4. JWT + NKeys (enterprise)**
```
Operator → Account → User
- Operator: tổ chức quản lý cluster
- Account: tenant/team isolation
- User: individual client identity
- JWTs signed bằng NKeys, decentralized verification
```
- ✅ Multi-tenancy, zero-trust, decentralized
- ❌ Phức tạp — cần nsc tool, resolver, account server

#### Production Recommendation

| Environment | Auth method |
|-------------|-------------|
| **Development/Local** | Token hoặc no auth |
| **Staging** | User/Password + TLS |
| **Production (single team)** | NKeys + TLS |
| **Production (multi-tenant)** | JWT + NKeys + TLS |

#### TLS Encryption

```
Mọi traffic giữa client↔server và server↔server PHẢI encrypted trong production.

Client ──TLS──> NATS Server ──TLS──> NATS Server (cluster route)
```

**Tại sao bắt buộc TLS trong production:**
- NATS protocol là text-based → dễ sniff nếu không encrypt
- Message payload có thể chứa PII, credentials, business data
- Compliance requirements (SOC2, HIPAA, GDPR)

---

### 4.4 Monitoring & Observability

#### HTTP Monitoring Endpoints (built-in)

NATS server expose HTTP endpoints mặc định trên port 8222:

| Endpoint | Mục đích | Key metrics |
|----------|---------|-------------|
| `/varz` | Server info | connections, mem, cpu, msgs_in/out |
| `/connz` | Connections | per-client info, subscriptions |
| `/subsz` | Subscriptions | subscription routing tree |
| `/routez` | Cluster routes | cluster topology, route health |
| `/jsz` | JetStream | streams, consumers, storage |
| `/healthz` | Health check | server health status |

#### Key Metrics cần Monitor

**Server-level:**
- `connections`: số active connections (alert khi đột ngột giảm)
- `in_msgs` / `out_msgs`: throughput (rate)
- `in_bytes` / `out_bytes`: bandwidth
- `slow_consumers`: số slow consumers (alert > 0)
- `mem` / `cpu`: resource usage

**JetStream:**
- `streams`: số streams
- `consumers`: số consumers
- `messages` / `bytes`: total stored
- `consumer_num_pending`: consumer lag (alert khi tăng liên tục)
- `consumer_num_ack_pending`: messages chờ ack

#### NATS CLI Monitoring

```bash
# Real-time server events
nats events

# JetStream advisories (consumer delivery failures, etc.)
nats events --js-advisory

# Stream report (tất cả streams)
nats stream report

# Consumer report (lag tất cả consumers)
nats consumer report ORDERS

# Server stats
nats server report connections
nats server report jetstream
```

#### Prometheus + Grafana

NATS cung cấp **nats-exporter** (Prometheus exporter):

```yaml
# docker-compose.yml bổ sung
services:
  nats-exporter:
    image: natsio/prometheus-nats-exporter:latest
    command: ["-varz", "-jsz=all", "-connz", "-routez", "http://nats:8222"]
    ports:
      - "7777:7777"
    depends_on:
      - nats
```

---

### 4.5 Decision Framework — Khi nào chọn NATS?

#### ✅ Chọn NATS khi:

1. **Cần messaging đơn giản, nhanh, ít operational overhead**
   - Single binary, zero dependencies, setup trong 5 phút
   - Ít config knobs → ít cơ hội misconfigure

2. **Microservices communication (service-to-service)**
   - Request-reply thay HTTP nội bộ
   - Pub/sub cho event notification
   - Queue groups cho load balancing

3. **IoT / Edge computing**
   - Lightweight (~15MB binary)
   - Hỗ trợ hàng triệu connections
   - Leaf nodes cho edge architecture

4. **Cần cả pub/sub + persistence + KV store trong 1 hệ thống**
   - NATS core + JetStream + KV Store + Object Store = 1 binary

5. **Team nhỏ, không muốn operational complexity của Kafka**
   - Kafka cần ZooKeeper/KRaft, topic management, partition tuning
   - NATS: đơn giản hơn nhiều bậc

#### ❌ KHÔNG chọn NATS khi:

1. **Cần ecosystem lớn cho data pipeline**
   - Kafka có Connect (200+ connectors), Streams, ksqlDB, Schema Registry
   - NATS ecosystem nhỏ hơn nhiều

2. **Cần complex routing logic (exchange types)**
   - RabbitMQ có direct, fanout, topic, headers exchange với binding rules
   - NATS chỉ có subject-based routing

3. **Cần throughput >1M msg/s sustained với large messages**
   - Kafka optimized cho batching large messages (sequential I/O, zero-copy)
   - NATS tối ưu cho small messages, high connection count

4. **Cần processing guarantee có transaction boundary rõ trong Kafka ecosystem**
   - Kafka Streams có transactional processing cho Kafka input/output và offset trong phạm vi framework
   - Với external side effects, cả Kafka và JetStream vẫn cần idempotent consumer/inbox/outbox

5. **Cần long-term storage / event sourcing with compaction**
   - Kafka có log compaction (giữ latest value per key indefinitely)
   - JetStream có limits nhưng không có compaction concept

#### Decision Matrix tổng hợp

| Criteria | NATS | RabbitMQ | Kafka |
|----------|------|----------|-------|
| **Setup complexity** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Operations overhead** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Throughput (small msg)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Throughput (large msg)** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Latency** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Routing flexibility** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Persistence/Replay** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Ecosystem** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Delivery semantics scope** | At-least-once + publisher dedup window | At-least-once với ack/confirm | Transactional semantics trong Kafka scope |
| **Multi-tenancy** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

---

## 5. Trade-off Analysis

### Cluster Size

| | 1 Node | 3 Nodes | 5 Nodes |
|---|--------|---------|---------|
| **Availability** | ❌ SPOF | 1 failure OK | 2 failures OK |
| **Write latency** | Lowest | +1 RTT | +1-2 RTT |
| **JetStream replicas** | Max 1 | Max 3 | Max 5 |
| **Network traffic** | None | Moderate | High |
| **Cost** | $ | $$$ | $$$$$ |
| **Recommended** | Dev only | ✅ Production | Critical systems |

### Auth method complexity vs security

```
Token ──────► User/Pass ──────► NKeys ──────► JWT+NKeys
  │              │                │              │
  ▼              ▼                ▼              ▼
Simple        Moderate         Secure        Enterprise
Dev/Test      Small team      Production    Multi-tenant
No isolation  Basic perms     Key-based     Full isolation
```

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Production cluster: luôn chạy 3+ nodes với JetStream replicas: 3**
   - 1 node chết → cluster vẫn hoạt động bình thường
   - JetStream data replicated, không mất

2. **TLS everywhere trong production**
   - Client↔Server: bắt buộc
   - Server↔Server (routes): bắt buộc
   - Dùng mTLS nếu cần verify client identity

3. **Client reconnection: tin tưởng client library**
   - Go/TypeScript NATS clients tự động reconnect
   - Set `nats.MaxReconnects(-1)` cho unlimited reconnect
   - Set `nats.ReconnectWait(2 * time.Second)` cho backoff

4. **Graceful shutdown: drain trước khi stop**
   ```go
   // Drain = xử lý hết messages đang pending, rồi disconnect
   nc.Drain()
   // KHÔNG dùng nc.Close() trực tiếp — có thể mất messages đang xử lý
   ```

5. **Monitoring: alert trên 3 metrics quan trọng nhất**
   - `slow_consumers > 0` → consumer không kịp xử lý
   - `consumer_num_pending` tăng liên tục → consumer lag
   - `connections` drop đột ngột → network issue hoặc server issue

### Common Pitfalls

1. **Pitfall: Cluster chẵn số nodes (2, 4)**
   - Raft cần majority → 2 nodes chỉ chịu 0 failure (cần 2/2 = 100%)
   - 4 nodes chịu 1 failure (cần 3/4) — lãng phí 1 node so với 3 nodes
   - Fix: Luôn dùng số lẻ (3, 5)

2. **Pitfall: Không set TLS cho cluster routes**
   - Data và metadata giữa nodes truyền plaintext
   - Fix: TLS cho cả client connections và routes

3. **Pitfall: Dùng token auth trong production**
   - 1 token leak = tất cả clients bị compromised
   - Fix: NKeys hoặc JWT — mỗi client có key riêng

4. **Pitfall: Không monitor JetStream storage**
   - Stream grow → disk full → server crash → data loss
   - Fix: Alert khi disk usage > 80%, set stream limits

5. **Pitfall: Quên configure client reconnection**
   ```go
   // ❌ Mặc định reconnect 60 lần, sau đó disconnect vĩnh viễn
   nc, _ := nats.Connect(url)
   
   // ✅ Unlimited reconnect với callbacks
   nc, _ := nats.Connect(url,
       nats.MaxReconnects(-1),
       nats.ReconnectWait(2*time.Second),
       nats.DisconnectErrHandler(func(nc *nats.Conn, err error) {
           log.Printf("Disconnected: %v", err)
       }),
       nats.ReconnectHandler(func(nc *nats.Conn) {
           log.Printf("Reconnected to %s", nc.ConnectedUrl())
       }),
   )
   ```

---

## 7. Performance Considerations

### Cluster Performance Impact

| Metric | Single node | 3-node cluster | Impact |
|--------|------------|----------------|--------|
| **Pub throughput** | ~10M msg/s | ~3-5M msg/s | Route overhead |
| **JetStream write** | ~500K msg/s | ~200-300K msg/s | Raft replication |
| **Latency (pub/sub)** | ~100μs | ~200-500μs | Route hop |
| **Latency (JetStream)** | ~500μs | ~1-3ms | Raft quorum |

### Tuning cho Production

**Server-level config:**
```
# nats-server.conf
max_connections: 64000        # connection limit per server
max_payload: 1048576          # 1MB max message size
write_deadline: "10s"         # slow client detection

jetstream {
    max_mem_store: 1073741824   # 1GB memory storage
    max_file_store: 10737418240 # 10GB file storage
    store_dir: "/data/jetstream"
}
```

**OS-level tuning:**
```bash
# File descriptors — mỗi connection cần 1 fd
ulimit -n 65535

# TCP tuning
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# Swap — tắt swap cho NATS server
swapoff -a
```

### Monitoring Thresholds (baseline)

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| **CPU** | >70% | >90% | Scale horizontally |
| **Memory** | >70% | >85% | Check memory streams, reduce replicas |
| **Disk** | >70% | >85% | Reduce retention, add storage |
| **Slow consumers** | >0 | >5 | Check consumer health, increase capacity |
| **Consumer lag** | >10K | >100K | Scale consumers, check processing bottleneck |
| **Connections** | >80% limit | >90% limit | Increase limit hoặc add nodes |

---

## 8. Hands-on Lab

### 8.1 Lab 1: 3-Node NATS Cluster với Docker Compose

Tạo file `docker-compose-cluster.yml`:

```yaml
version: "3.8"

services:
  nats-1:
    image: nats:2.10-alpine
    ports:
      - "4222:4222"
      - "8222:8222"
    volumes:
      - ./config/nats-1.conf:/etc/nats/nats.conf
      - nats-1-data:/data
    command: ["-c", "/etc/nats/nats.conf"]

  nats-2:
    image: nats:2.10-alpine
    ports:
      - "4223:4222"
      - "8223:8222"
    volumes:
      - ./config/nats-2.conf:/etc/nats/nats.conf
      - nats-2-data:/data
    command: ["-c", "/etc/nats/nats.conf"]

  nats-3:
    image: nats:2.10-alpine
    ports:
      - "4224:4222"
      - "8224:8222"
    volumes:
      - ./config/nats-3.conf:/etc/nats/nats.conf
      - nats-3-data:/data
    command: ["-c", "/etc/nats/nats.conf"]

volumes:
  nats-1-data:
  nats-2-data:
  nats-3-data:
```

Tạo config files:

```bash
mkdir -p config
```

**File `config/nats-1.conf`:**
```
server_name: nats-1
listen: 0.0.0.0:4222
http_port: 8222

jetstream {
  store_dir: /data/jetstream
  max_mem: 256MB
  max_file: 1GB
}

cluster {
  name: nats-cluster
  listen: 0.0.0.0:6222
  routes: [
    nats-route://nats-2:6222
    nats-route://nats-3:6222
  ]
}

# Basic auth cho lab
authorization {
  users = [
    {user: "admin", password: "admin123", permissions: {
      publish: {allow: [">"]}
      subscribe: {allow: [">"]}
    }}
    {user: "order-svc", password: "order-pass", permissions: {
      publish: {allow: ["orders.>", "$JS.API.>"]}
      subscribe: {allow: ["orders.>", "_INBOX.>"]}
    }}
    {user: "payment-svc", password: "payment-pass", permissions: {
      publish: {allow: ["payments.>", "$JS.API.>"]}
      subscribe: {allow: ["orders.created", "payments.>", "_INBOX.>"]}
    }}
  ]
}
```

**File `config/nats-2.conf`:**
```
server_name: nats-2
listen: 0.0.0.0:4222
http_port: 8222

jetstream {
  store_dir: /data/jetstream
  max_mem: 256MB
  max_file: 1GB
}

cluster {
  name: nats-cluster
  listen: 0.0.0.0:6222
  routes: [
    nats-route://nats-1:6222
    nats-route://nats-3:6222
  ]
}

authorization {
  users = [
    {user: "admin", password: "admin123", permissions: {
      publish: {allow: [">"]}
      subscribe: {allow: [">"]}
    }}
    {user: "order-svc", password: "order-pass", permissions: {
      publish: {allow: ["orders.>", "$JS.API.>"]}
      subscribe: {allow: ["orders.>", "_INBOX.>"]}
    }}
    {user: "payment-svc", password: "payment-pass", permissions: {
      publish: {allow: ["payments.>", "$JS.API.>"]}
      subscribe: {allow: ["orders.created", "payments.>", "_INBOX.>"]}
    }}
  ]
}
```

**File `config/nats-3.conf`:**
```
server_name: nats-3
listen: 0.0.0.0:4222
http_port: 8222

jetstream {
  store_dir: /data/jetstream
  max_mem: 256MB
  max_file: 1GB
}

cluster {
  name: nats-cluster
  listen: 0.0.0.0:6222
  routes: [
    nats-route://nats-1:6222
    nats-route://nats-2:6222
  ]
}

authorization {
  users = [
    {user: "admin", password: "admin123", permissions: {
      publish: {allow: [">"]}
      subscribe: {allow: [">"]}
    }}
    {user: "order-svc", password: "order-pass", permissions: {
      publish: {allow: ["orders.>", "$JS.API.>"]}
      subscribe: {allow: ["orders.>", "_INBOX.>"]}
    }}
    {user: "payment-svc", password: "payment-pass", permissions: {
      publish: {allow: ["payments.>", "$JS.API.>"]}
      subscribe: {allow: ["orders.created", "payments.>", "_INBOX.>"]}
    }}
  ]
}
```

Khởi động và verify:
```bash
# Start cluster
docker compose -f docker-compose-cluster.yml up -d

# Verify cluster đã form
nats --user admin --password admin123 server report connections

# Kiểm tra cluster routes
curl -s http://localhost:8222/routez | jq '.routes[] | {remote_id, ip, port}'

# Kiểm tra JetStream
nats --user admin --password admin123 account info
```

### 8.2 Lab 2: Test Cluster HA — Fault Tolerance

```bash
# Tạo stream với replicas: 3
nats --user admin --password admin123 stream add ORDERS \
  --subjects "orders.>" \
  --retention limits \
  --max-msgs 10000 \
  --max-age 1h \
  --storage file \
  --replicas 3 \
  --defaults

# Publish messages
for i in $(seq 1 20); do
  nats --user admin --password admin123 pub orders.created "{\"id\":\"ORD-$i\"}"
done

# Verify stream info — xem leader và replicas
nats --user admin --password admin123 stream info ORDERS

# Kill 1 node
docker compose -f docker-compose-cluster.yml stop nats-2

# Cluster vẫn hoạt động — publish vẫn OK
nats --user admin --password admin123 pub orders.created '{"id":"ORD-after-kill"}'

# Xem stream info — leader đã chuyển sang node khác
nats --user admin --password admin123 stream info ORDERS

# Restart node
docker compose -f docker-compose-cluster.yml start nats-2

# Verify node rejoin và sync data
sleep 5
nats --user admin --password admin123 stream info ORDERS
# → replicas trở lại 3/3
```

### 8.3 Lab 3: Permission Testing

Lab này kiểm tra auth/permissions và JetStream API subject scope. Nó không bật TLS để giữ lab 2 giờ gọn; trong production, áp dụng TLS cho client listener, cluster routes và leaf-node connections như phần 4.3. Nếu muốn thực hành TLS đầy đủ, tách thành lab riêng với CA/server/client certs và hostname verification.

```bash
# order-svc có thể publish orders.>
nats --user order-svc --password order-pass pub orders.created '{"test":"ok"}'
# → OK

# order-svc KHÔNG thể publish payments.>
nats --user order-svc --password order-pass pub payments.process '{"test":"denied"}'
# → Error: Permissions Violation for Publish

# payment-svc có thể subscribe orders.created
nats --user payment-svc --password payment-pass sub orders.created
# → OK (chờ messages)

# payment-svc KHÔNG thể subscribe orders.shipped
nats --user payment-svc --password payment-pass sub orders.shipped
# → Error: Permissions Violation for Subscription
```

### 8.4 Lab 4: Go Client với Cluster Reconnection

**File `cluster_client.go`:**
```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nats-io/nats.go"
)

func main() {
	// Kết nối cluster — liệt kê tất cả nodes
	// Client tự động failover sang node khác khi 1 node chết
	urls := "nats://admin:admin123@localhost:4222,nats://admin:admin123@localhost:4223,nats://admin:admin123@localhost:4224"

	nc, err := nats.Connect(urls,
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2*time.Second),
		nats.ReconnectBufSize(5*1024*1024), // 5MB buffer khi reconnecting
		nats.DisconnectErrHandler(func(nc *nats.Conn, err error) {
			log.Printf("⚠️  Disconnected: %v", err)
		}),
		nats.ReconnectHandler(func(nc *nats.Conn) {
			log.Printf("✅ Reconnected to %s", nc.ConnectedUrl())
		}),
		nats.ClosedHandler(func(nc *nats.Conn) {
			log.Printf("❌ Connection closed: %v", nc.LastError())
		}),
	)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Drain() // Graceful shutdown — drain trước khi close

	js, err := nc.JetStream()
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("Connected to %s", nc.ConnectedUrl())

	// Tạo pull consumer
	sub, err := js.PullSubscribe("orders.>", "cluster-demo",
		nats.ManualAck(),
		nats.AckWait(10*time.Second),
	)
	if err != nil {
		log.Fatal(err)
	}

	// Consumer goroutine
	go func() {
		for {
			msgs, err := sub.Fetch(5, nats.MaxWait(5*time.Second))
			if err != nil {
				if err == nats.ErrTimeout {
					continue
				}
				log.Printf("Fetch error: %v", err)
				time.Sleep(time.Second)
				continue
			}

			for _, msg := range msgs {
				var data map[string]interface{}
				json.Unmarshal(msg.Data, &data)
				log.Printf("Received on [%s]: %v", msg.Subject, data)
				msg.Ack()
			}
		}
	}()

	// Publisher goroutine
	go func() {
		i := 0
		for {
			i++
			data := fmt.Sprintf(`{"order_id":"ORD-%04d","timestamp":"%s"}`, i, time.Now().Format(time.RFC3339))

			ack, err := js.Publish("orders.created", []byte(data),
				nats.MsgId(fmt.Sprintf("order-%d", i)),
			)
			if err != nil {
				log.Printf("Publish error: %v (will retry on reconnect)", err)
				time.Sleep(2 * time.Second)
				continue
			}

			log.Printf("Published ORD-%04d → seq=%d stream=%s", i, ack.Sequence, ack.Stream)
			time.Sleep(3 * time.Second)
		}
	}()

	log.Println("Running... Try killing a NATS node to test failover!")
	log.Println("  docker compose -f docker-compose-cluster.yml stop nats-1")

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	log.Println("Shutting down gracefully...")
}
```

**Test failover:**
```bash
# Terminal 1 — Run client
go run cluster_client.go

# Terminal 2 — Kill node mà client đang connected
docker compose -f docker-compose-cluster.yml stop nats-1

# Quan sát Terminal 1:
# ⚠️  Disconnected: ...
# ✅ Reconnected to nats://localhost:4223
# Published ORD-XXXX → seq=... (tiếp tục hoạt động)

# Restart node
docker compose -f docker-compose-cluster.yml start nats-1
```

### 8.5 Lab 5: Monitoring Dashboard

```bash
# Server report
nats --user admin --password admin123 server report connections
nats --user admin --password admin123 server report jetstream

# Stream report — xem tất cả streams, leaders, replicas
nats --user admin --password admin123 stream report

# Consumer report — xem lag
nats --user admin --password admin123 consumer report ORDERS

# Monitor real-time events (advisories, disconnects, etc.)
nats --user admin --password admin123 events

# JetStream metrics từ HTTP endpoint
curl -s http://localhost:8222/jsz | jq '{streams, consumers, messages, bytes}'

# Health check (dùng cho load balancer / k8s readiness probe)
curl -s http://localhost:8222/healthz
# → {"status":"ok"}
```

### 8.6 Lab 6: Cleanup

```bash
# Xóa stream
nats --user admin --password admin123 stream rm ORDERS --force

# Stop cluster
docker compose -f docker-compose-cluster.yml down -v
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Tại sao NATS cluster nên dùng số lẻ nodes?** Giải thích bằng Raft consensus — 3 nodes vs 4 nodes chịu được bao nhiêu failures? Tại sao 4 nodes không tốt hơn 3 nodes đáng kể?

2. **Leaf node khác full mesh cluster member ở điểm nào?** Cho scenario: bạn có 3 teams ở 3 regions (US, EU, Asia). Mỗi team có 5 microservices giao tiếp local, nhưng cần publish events đến central analytics. Bạn thiết kế topology thế nào?

3. **So sánh 4 auth methods (Token, User/Password, NKeys, JWT+NKeys).** Cho scenario: startup 10 developers, 20 microservices, 1 cluster. Bạn recommend auth method nào? Khi nào cần upgrade lên method phức tạp hơn?

   *Hint: Complexity vs security trade-off. Đừng over-engineer sớm.*

4. **Bạn đang monitor production NATS cluster và thấy `slow_consumers: 3` tăng liên tục. Quy trình troubleshoot của bạn là gì?**

   *Hint: Identify consumer → check processing time → check backpressure config → scale hoặc optimize.*

5. **Design question — khi nào chọn NATS over Kafka?** Cho 3 scenarios: (a) Real-time chat backend, (b) Payment processing pipeline, (c) Data warehouse ingestion. Recommend tool cho mỗi scenario kèm giải thích.

6. **Tại sao Drain() quan trọng hơn Close() khi shutdown?** Cho scenario: consumer đang xử lý 50 messages (chưa ack). Gọi Close() vs Drain() — chuyện gì xảy ra với 50 messages đó?

7. **Challenge question:** Bạn có hệ thống NATS cluster 3 nodes, stream "ORDERS" replicas 3. Cả 3 nodes restart cùng lúc (data center power outage). Khi nodes quay lại, điều gì xảy ra? Data có mất không? Tại sao?

   *Hint: Raft log on disk, storage type file vs memory.*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [NATS Clustering](https://docs.nats.io/running-a-nats-service/configuration/clustering)
- [Leaf Nodes](https://docs.nats.io/running-a-nats-service/configuration/leafnodes)
- [NATS Security](https://docs.nats.io/running-a-nats-service/configuration/securing_nats)
- [NKeys & JWT](https://docs.nats.io/running-a-nats-service/configuration/securing_nats/auth_intro/nkey_auth)
- [Monitoring](https://docs.nats.io/running-a-nats-service/nats_admin/monitoring)

### Operations & Production
- [Synadia Blog — Running NATS in Production](https://www.synadia.com/blog)
- [NATS Prometheus Exporter](https://github.com/nats-io/prometheus-nats-exporter)
- [NATS Grafana Dashboard](https://grafana.com/grafana/dashboards/2279-nats/)

### Architecture Decisions
- [NATS Comparison](https://docs.nats.io/compare) — Official comparison with Kafka, RabbitMQ, Pulsar
- [When to use NATS](https://nats.io/about/)

### Videos
- [NATS Clustering Deep Dive — KubeCon](https://www.youtube.com/watch?v=_TyQf_sfpBQ)
- [NATS Security Best Practices — NATS Community](https://www.youtube.com/watch?v=RqE3mM6VD3E)
- [Scaling NATS to 1M connections — GopherCon](https://www.youtube.com/watch?v=21QRGF4FEJw)

---

## Tổng kết Phase 1 (Day 1-3)

Sau 3 ngày, bạn đã nắm được:

| Concept | Day | Status |
|---------|-----|--------|
| Sync vs Async communication | Day 1 | ✅ |
| Queue vs Pub/Sub vs Stream | Day 1 | ✅ |
| Broker vs Distributed Log | Day 1 | ✅ |
| NATS Core: subjects, wildcards, pub/sub | Day 1 | ✅ |
| Queue groups, request-reply | Day 1 | ✅ |
| JetStream: streams, consumers, ack | Day 2 | ✅ |
| Retention policies, delivery policies | Day 2 | ✅ |
| Push vs Pull consumer, backpressure | Day 2 | ✅ |
| Publisher deduplication với `Nats-Msg-Id` | Day 2 | ✅ |
| Clustering: full mesh, Raft, HA | Day 3 | ✅ |
| Leaf nodes architecture | Day 3 | ✅ |
| Security: auth, TLS, permissions | Day 3 | ✅ |
| Monitoring & observability | Day 3 | ✅ |
| NATS decision framework | Day 3 | ✅ |

**Tiếp theo:** Day 4-9 — RabbitMQ (smart broker, AMQP protocol, routing phức tạp, reliability, clustering).
