# Day 41: Logging Architecture — Loki vs ELK vs Splunk

---

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt được 3 hệ thống logging phổ biến** (Loki, ELK, Splunk) — hiểu kiến trúc, điểm mạnh/yếu, và use case phù hợp cho từng hệ thống.
2. **Triển khai được Loki stack** (Loki + Promtail/Grafana Agent + Grafana) để thu thập và query logs từ nhiều nguồn trong môi trường local.
3. **Viết được LogQL queries** để filter, aggregate, và correlate logs theo labels, level, request ID, correlation ID.
4. **Thiết lập được retention policy và cost optimization** — cân bằng giữa log retention và chi phí lưu trữ.
5. **Xử lý được sensitive data trong logs** — nhận diện PII, áp dụng techniques để redact/encrypt trước khi gửi log.

---

## 2. Bối cảnh & Động lực

### Vì sao logging quan trọng?

Day 38 ta đã phân biệt metrics vs logs vs traces. Logs là "bản ghi sự kiện" — chúng cho biết **chuyện gì đã xảy ra, ở đâu, khi nào, và tại sao**. Metrics cho ta biết hệ thống "khỏe" hay "yếu"; logs cho ta biết **tại sao** nó yếu.

```
Metric:  Error rate = 5%    ← Alert "có vấn đề"
Log:     "Connection refused to DB at 10.23.45.67:5432" ← Debug được ngay
```

**Hậu quả khi logging tệ:**

| Hậu quả | Tác động |
|---|---|
| Không có logs | Incident MTTR tăng 10x, team debug bằng guesswork |
| Logs quá nhiều / noise | Signal bị chìm, engineer bỏ qua log alerts |
| Logs thiếu context (không có request ID) | Không correlate được distributed requests |
| Sensitive data trong logs | GDPR violation, token leak, security breach |
| Không có retention policy | Chi phí lưu trữ tăng phi mã, hoặc logs bị xóa quá sớm |

**Bài toán thực tế:** Một request từ user đi qua API Gateway → Auth Service → Order Service → Payment Service → Database. Khi có lỗi, bạn cần trace toàn bộ chuỗi đó. Không có correlation ID = debugging bằng cảm tính.

---

## 3. Kiến thức nền tảng

### 3.1. Structured Logging là gì?

**Unstructured log** (legacy):
```
[2026-05-12 10:00:00] User 12345 logged in from IP 192.168.1.1
[2026-05-12 10:00:01] Order created for user 12345, amount=150.00 USD
```

**Structured log** (JSON):
```json
{"timestamp":"2026-05-12T10:00:00Z","level":"info","service":"order-service","user_id":"12345","action":"login","ip":"192.168.1.1","duration_ms":45}
```

Structured logging cho phép:
- **Query bằng field** (WHERE user_id = '12345') thay vì regex
- **Index theo field** → query nhanh hơn nhiều
- **Dashboard/visualize** theo field cụ thể
- **Correlate** logs với traces và metrics qua shared labels

> **Developer analogy:** Unstructured log giống như viết mọi thứ vào một cuốn sổ tay chung. Structured log giống như dùng database có schema — tìm kiếm bằng index, không phải đọc từng dòng.

### 3.2. Log Aggregation Pipeline

```
[App] → [Shipper/Agent] → [Buffer/Queue] → [Log Aggregator] → [Storage] → [Query UI]
```

- **App**: Generate logs (stdout, file, journald)
- **Shipper/Agent**: Promtail, Filebeat, Fluentd, Grafana Agent — đọc và gửi logs
- **Buffer/Queue**: Kafka, Redis — giảm load, chịu được burst
- **Log Aggregator**: Loki, Elasticsearch, Splunk — indexing và lưu trữ
- **Query UI**: Grafana, Kibana, Splunk Web — truy vấn và visualize

### 3.3. Log Levels

```
DEBUG → INFO → WARN → ERROR → FATAL/PANIC
```

- **DEBUG**: Chi tiết bên trong flow (dev/staging thôi)
- **INFO**: Business events bình thường
- **WARN**: Abnormal nhưng không break — retry succeeded, degraded mode
- **ERROR**: Operation failed nhưng service còn sống
- **FATAL/PANIC**: Service chết — cần immediate action

> **Thực tế:** DEBUG logs ở production = noise khủng khiếp. Production = INFO/WARN/ERROR. Có team còn dùng sampling cho DEBUG để giảm volume.

### 3.4. Correlation ID / Trace ID

```
User Request
  ↓
API Gateway: tạo correlation_id = "abc-123"
  ↓
Auth Service: log với correlation_id = "abc-123" ✅
  ↓
Order Service: log với correlation_id = "abc-123" ✅
  ↓
Payment Service: log với correlation_id = "abc-123" ✅
  ↓
Tất cả logs query bằng: {correlation_id="abc-123"} ← ONE query!
```

Bằng cách truyền `correlation_id` qua HTTP headers (`X-Request-ID`, `X-Correlation-ID`) và gắn vào mọi log entry, ta có thể trace một request qua toàn bộ distributed system.

---

## 4. Deep Dive

### 4.1. Loki Architecture

Loki được thiết kế theo nguyên tắc **"like Prometheus, but for logs"** — chỉ index labels, không index nội dung log. Điều này làm Loki rẻ hơn ELK/Splunk rất nhiều.

```
┌─────────────────────────────────────────────────────────────┐
│                      Grafana UI                              │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP (GET /loki/api/v1/query_range)
┌──────────────────────▼──────────────────────────────────────┐
│                   Loki Distributor                           │
│  - Validate streams, push to ingesters via gRPC             │
└──┬───────────────────┬─────────────────────┬────────────────┘
   │ (replicated)      │                     │
┌──▼───────┐    ┌──────▼──────┐    ┌─────────▼───────┐
│ Ingester │    │  Ingester   │    │   Ingester      │
│ (WAL)    │    │  (WAL)      │    │   (WAL)         │
│ :9095    │    │  :9095      │    │   :9095          │
└────┬─────┘    └──────┬──────┘    └─────────┬───────┘
     │                 │                     │
     └────────┬────────┴─────────────────────┘
              │  gRPC (write chunks)
     ┌────────▼────────┐
     │  Object Store  │  ← S3 / GCS / Azure Blob / Filesystem
     │  (chunks/)      │    chunk data
     └────────┬────────┘
              │  metadata queries
     ┌────────▼────────┐
     │    Index Store  │  ← DynamoDB / BigTable / Cassandra
     │  (index/)       │    label → chunk ID mapping
     └─────────────────┘
```

**Các component:**

| Component | Role |
|---|---|
| Distributor | Nhận log streams, hash theo labels, route tới đúng ingesters |
| Ingester | Nhận log chunks, ghi vào WAL, flush xuống object store |
| Query Frontend | Tiếp nhận query, split range, schedule, cache results |
| Querier | Thực hiện query thực sự — đọc index + chunks |
| Ruler | Evaluates recording rules & alerting rules (logs-based alerts!) |

**Loki's secret sauce:**
- **No full-text index** → Loki không lưu index cho nội dung log
- Chỉ index **labels** (metadata): `{job="api-gateway",env="prod",status="error"}`
- Nội dung log được chunk và ghi dạng binary (lưu ở object store)
- Khi query: Loki tìm chunks chứa labels phù hợp → đọc nội dung → filter bằng regex/LogQL

**Chunk format:** Loki dùng **Parquet-like columnar format** — nén tốt, scan nhanh theo column.

**Failure modes:**
- Ingester crash: WAL đảm bảo không mất logs (được ghi trước khi ack)
- Object store down: Loki tiếp tục serve reads từ cache, writes queue lại
- Distributor overload: bật load balancing phù hợp, scale horizontal distributor/ingester, và kiểm tra `ring` health trước khi tăng traffic

### 4.2. ELK Stack Architecture

ELK = Elasticsearch + Logstash + Kibana (+ Beats là lightweight shipper).

```
┌──────────────────────────────────────────────────────────────────┐
│                        Kibana (Query UI)                          │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP / DSL
┌────────────────────────────▼─────────────────────────────────────┐
│                  Elasticsearch Cluster                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐   (sharded, replicated)    │
│  │ Node 1  │  │ Node 2  │  │ Node 3  │                           │
│  │ Primary │  │ Replica │  │ Primary │                           │
│  └─────────┘  └─────────┘  └─────────┘                           │
└──┬──────────────────┬────────────────────────────────────────────┘
   │ Beats/Agent push  │  (lưu trữ full-text indexed documents)
┌──▼────────────────────────────────────────────────────────────────┐
│              Beats / Logstash Pipeline                            │
│                                                                  │
│  [Filebeat] ──┐                                                  │
│  [Metricbeat] ├──→ [Logstash] ──→ [Elasticsearch]               │
│  [Packetbeat] ┘   (parse, enrich, transform)                     │
│                                                                  │
│  Input → Filter → Output                                          │
│  (beats)    (grok,    (ES output)                                │
│              mutate,                                          │
│              geoip)                                             │
└──────────────────────────────────────────────────────────────────┘
```

**Elasticsearch inverted index:**
- Mỗi document được tokenize thành terms
- Inverted index map: term → list of documents chứa term đó
- Khi query "error timeout" → tìm docs chứa "error" OR "timeout" → rank → return

**Logstash vs Beats:**
- **Filebeat**: Nhẹ, đọc file logs, gửi tới Logstash hoặc trực tiếp ES. Dùng cho log files.
- **Metricbeat**: Thu thập metrics định kỳ.
- **Logstash**: Nặng hơn, có full ETL pipeline — parse JSON, Grok filter, geoip enrichment. Cần khi cần transform phức tạp.

**Failure modes:**
- Elasticsearch cluster overload: Query latency tăng → giải pháp: increase replicas, add warm/cold tiers, use data tiering
- Logstash bottleneck: Filter quá phức tạp, JVM heap đầy → profile filters, tối ưu Grok patterns
- Disk full: Elasticsearch ngừng write → monitor disk + setup ILM (Index Lifecycle Management)

### 4.3. Splunk Architecture

Splunk là proprietary solution. Splunk Cloud hoặc Splunk Enterprise.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Splunk Web / CLI / API                     │
└──────────────────────────────┬───────────────────────────────────┘
                               │ SPL queries
┌──────────────────────────────▼───────────────────────────────────┐
│                   Search Head Cluster                            │
│  - Distributed search, KV store, DMC (Distributed Management     │
│    Console)                                                       │
└──┬───────────────────────┬──────────────────────────────────────┘
   │                        │
┌──▼───────────┐    ┌──────▼────────────┐
│  Indexer 1    │    │    Indexer N       │
│  (hot/warm/  │    │  (hot/warm/cold/   │
│   cold/bucket│    │   frozen)          │
└──┬───────────┘    └──────┬────────────┘
   │  Replication (RF=2)   │
┌──▼───────────┐    ┌──────▼────────────┐
│  Indexer 2   │    │    Indexer 3       │
│  (replica)   │    │  (replica)         │
└──────────────┘    └────────────────────┘
```

**Splunk's data flow:**
1. **Universal Forwarder (UF)** hoặc **Heavy Forwarder (HF)**: Thu thập logs từ app/servers
2. **Indexer**: Parse, extract fields, store data. Tạo **index** (like a database table).
3. **Search Head**: Giao diện truy vấn bằng SPL (Splunk Processing Language)

**Điểm mạnh của Splunk:**
- **SPL**: Mạnh mẽ, có thể làm thống kê phức tạp ngay trong query
- **KV Store**: Lưu lookup tables, session data
- **CIM (Common Information Model)**: Normalize data thành standardized models
- **Licensing**: Per-GB ingested data → đắt đỏ, nhưng mạnh

---

## 5. Trade-offs & Best Practices ⭐

### 5.1. So sánh toàn diện

| Tiêu chí | Loki | ELK (Elasticsearch) | Splunk |
|---|---|---|---|
| **Chi phí** | Rẻ nhất (object store + index nhỏ) | Trung bình (nhiều disk + memory) | Đắt (per-GB license) |
| **Full-text search** | Không (chỉ label search) | Có (mạnh) | Có (rất mạnh) |
| **Query language** | LogQL | KQL / Query DSL | SPL |
| **Scalability** | Horizontal (label-based) | Horizontal (sharding) | Horizontal (cluster) |
| **Log volume support** | Rất cao (Petabyte scale) | Cao | Rất cao |
| **Learning curve** | Thấp (Prometheus-style) | Trung bình | Trung bình-Cao |
| **Integration ecosystem** | Grafana-native | Beats, Logstash, Elastic Agent | Heavy forwarder, many integrations |
| **Alerting on logs** | Có (Ruler + Grafana Alerting) | Có (Watcher, Kibana Alerting) | Có (Splunk ES, Phantom) |
| **TCO (100GB/day)** | ~$200-400/tháng (S3) | ~$800-1500/tháng | ~$3000-8000/tháng |
| **Use case tốt nhất** | High-volume, label-known queries | Complex full-text + analytics | Enterprise + compliance-heavy |
| **Setup phức tạp** | Đơn giản (single binary + config) | Phức tạp (nhiều components) | Đơn giản (appliance-like) |
| **Retention policy** | Table configs đơn giản | ILM (Index Lifecycle Management) | Retention policy per index |

### 5.2. Decision Framework

```
Start here
  │
  ├─ "Cần full-text search phức tạp?"
  │     ├─ YES + budget cao + enterprise → Splunk
  │     └─ YES + budget trung bình → ELK
  │
  ├─ "100GB+ logs/ngày, budget thấp?"
  │     └─ Loki (chỉ index labels, object store rẻ)
  │
  ├─ "Đã dùng Prometheus/Grafana?"
  │     └─ Loki (native integration, same UI)
  │
  ├─ "Cần compliance (PCI-DSS, SOC2, HIPAA)?"
  │     └─ Splunk (built-in audit, role-based access)
  │
  └─ "Team nhỏ, cần quick setup?"
        └─ Loki (single binary, hours vs days)
```

### 5.3. Best solution theo scenario

| Scenario | Recommend | Lý do |
|---|---|---|
| Startup, < 50GB/day, cost-sensitive | Loki | Chi phí thấp, Grafana native |
| Mid-size, cần full-text search | ELK | Cân bằng giữa feature và cost |
| Enterprise, compliance, nhiều data sources | Splunk | Ecosystem phong phú, hỗ trợ enterprise |
| High-volume microservices (>1TB/day) | Loki + S3/GCS | Scale không giới hạn với chi phí predictable |
| Kubernetes environment | Loki + Grafana Agent | Native k8s service discovery |
| Security/SIEM use case | Splunk hoặc Elastic Security | Built-in SIEM, threat detection |

### 5.4. Anti-patterns cần tránh

```yaml
# ❌ Anti-pattern 1: Ghi mọi thứ ở DEBUG level vào production
app:
  log_level: DEBUG  # → Noise khủng khiếp, bill tăng, query chậm

# ✅ Đúng: Chỉ INFO/WARN/ERROR ở production
app:
  log_level: INFO

# ❌ Anti-pattern 2: Không có retention policy
loki:
  # Không set retention → logs lưu mãi mãi → bill S3 tăng vô hạn

# ✅ Đúng: Set retention rõ ràng
loki:
  compactor:
    retention_enabled: true
    retention_delete_worker_count: 4
  limits_config:
    retention_period: 15d  # 15 ngày cho hot data, chuyển sang cold sau đó

# ❌ Anti-pattern 3: Log toàn bộ request/response body
logger.info("Request body:", req.Body)  # → Passwords, tokens bị log!

# ✅ Đúng: Redact sensitive fields
logger.info("Request received", zap.Object("headers", sanitizeHeaders(req.Headers)))

# ❌ Anti-pattern 4: Mỗi service ghi log riêng không có correlation ID
# Service A: "Order processed"
# Service B: "Payment failed"
# → Không biết 2 event này liên quan gì

# ✅ Đúng: Correlation ID xuyên suốt
# {correlation_id="xyz-123"} xuất hiện trong mọi log entry của request đó
```

---

## 6. Performance & Scalability ⭐

### 6.1. Loki Performance

**Loki's bottleneck:** Khi query không có label filter cụ thể → phải scan toàn bộ chunks.

```
# ❌ Chậm: Query toàn bộ logs không filter
{job="~".*"} |= "error"

# ✅ Nhanh: Filter theo labels trước
{job="api-gateway", env="prod"} |= "error"

# ⚡ Tối ưu: Chỉ query time range cần thiết
{job="api-gateway"} |= "error" | __error__!="JSON"
  [5m]  ← chỉ query 5 phút gần nhất
```

**Ingester write throughput:**
- Mỗi Ingester handle ~1-2MB/s writes
- Scale: thêm ingesters, Loki tự hash labels → distribute load
- Benchmark: 10 ingesters → ~15MB/s write throughput

**Querier memory:**
- Query large time ranges → high memory
- Giải pháp: `query_timeout`, `max_query_length`, use **sharded queries**

### 6.2. Elasticsearch Performance

**Sharding strategy:**
- Index nhỏ (< 50GB): 1 shard là đủ
- Index lớn (> 100GB): nên split thành nhiều shards
- Số shards = `data_size / shard_size` (recommend 30-50GB/shard)

```json
// ❌ Shard quá nhỏ → too many shards overhead
{ "settings": { "number_of_shards": 50, "number_of_replicas": 1 } }

// ✅ Shard size 30-50GB
{ "settings": { "number_of_shards": 5, "number_of_replicas": 1 } }
```

**Mapping explosion:**
- Elasticsearch index mỗi field mới → mapping tăng
- Fix: Set `dynamic: strict` hoặc `dynamic: false`

### 6.3. Splunk Performance

- **Search factor (SF)**: Số search copies của mỗi bucket (recommend 2)
- **Replication factor (RF)**: Số replicas của mỗi bucket (recommend 3 cho production)
- **Hot pool**: SSDs cho hot buckets → I/O không phải bottleneck
- **Concurrent searches**: License determines max concurrent searches

### 6.4. Common Bottlenecks & Detection

| Bottleneck | Symptom | Detection Command |
|---|---|---|
| Loki: Query không có label filter | Querier CPU 100%, query timeout | `loki_query_queue_length` metric |
| ELK: Too many indices | Indexing thất bại, disk full | `_cat/indices?v` → count indices |
| ELK: Shard imbalance | Một node disk full, node khác còn trống | `_cluster/health` → unassigned shards |
| Loki: Ingester OOM | Logs bị dropped, `ingester_OOM_total` ↑ | `loki_ingester_sent_bytes_total` vs received |
| All: Network saturation | Log agent queue tăng | `promtail_encoded_bytes` backlog |

### 6.5. Scaling Strategies

```
Vertical scaling (quick fix):
  - Tăng disk IOPs, memory cho queriers
  - ✅: Đơn giản
  - ❌: Giới hạn vật lý, downtime

Horizontal scaling (proper fix):
  - Loki: Thêm queriers, distributors, ingesters
  - ELK: Thêm data nodes, optimize shard distribution
  - ✅: Linear scale
  - ❌: Cần re-index hoặc re-routing

Sampling (cost saving):
  - Chỉ index 10% DEBUG logs ở production
  - Error logs: 100% capture
  - Access logs: sampling 1%

Tiered storage (cost optimization):
  - Hot (SSD): 1-7 ngày → query frequent
  - Warm (HDD): 8-30 ngày → query occasional
  - Cold (Object store): 31-365 ngày → compliance only
```

---

## 7. Security & Reliability Considerations

### 7.1. Sensitive Data trong Logs — PII Handling

**Những gì KHÔNG BAO GIỜ được log:**

```
1. Passwords / Secrets / API Keys
   ❌ logger.info("Login", "password", password)
   ✅ logger.info("Login attempt", "user", userId)

2. JWT Tokens (full)
   ❌ logger.info("Auth header", req.headers["Authorization"])
   ✅ logger.info("Auth", "user", userId, "method", "jwt")

3. Credit Card / SSN / PII
   ❌ logger.info("Payment", "card", "4111111111111111")
   ✅ logger.info("Payment", "card_last4", "1111")

4. Full Request/Response bodies
   ❌ logger.info("Request", "body", JSON.stringify(req.body))
   ✅ logger.info("Request", "method", req.method, "path", req.path)

5. Health / Medical data
   ❌ logger.info("Patient record", record)
   ✅ logger.info("Access patient record", "record_id", recordId)
```

### 7.2. Techniques để Protect Sensitive Data

**Technique 1: Structured redaction (best practice)**

```go
// Go — dùng logger library hỗ trợ redaction
import "github.com/rs/zerolog"

log := zerolog.New(os.Stdout).With().Timestamp().Logger()
log.Info().
  Str("user_id", user.ID).
  Str("email", sanitizeEmail(user.Email)). // user@domain.com → u***r@domain.com
  Str("card_last4", user.CardLast4).
  Msg("Payment processed")
```

**Technique 2: Grafana Agent / Promtail redaction**

```yaml
# promtail.yaml — redact before sending to Loki
scrape_configs:
  - job_name: api-service
    static_configs:
      - targets: [localhost]
        labels:
          job: api-service
          __path__: /var/log/api-service/*.log
    pipeline_stages:
      - json:
          expressions:
            password: password
            token: token
            credit_card: credit_card
      - labels:
          level: level
          service: service
      - replace:
          expression: '"(token|password|credit_card)":"[^"]*"'
          replace: '"$1":"[REDACTED]"'
```

**Technique 3: Elasticsearch masking pipeline**

```json
{
  "description": "Mask sensitive fields",
  "processors": [
    {
      "mask": {
        "field": "password",
        "target_field": "password_masked",
        "mask": "****"
      }
    },
    {
      "remove": {
        "field": ["password", "token", "credit_card"],
        "ignore_failure": true
      }
    }
  ]
}
```

### 7.3. Secret Management — Don't Leak in Logs

```bash
# ❌ Sai: Log toàn bộ env vars (bao gồm secrets!)
echo "Starting app with env: $ENV"

# ✅ Đúng: Chỉ log non-sensitive config
echo "Starting app with workers=$WORKERS, log_level=$LOG_LEVEL"

# ✅ Hoặc dùng service mesh để inject secrets
# Kubernetes: secrets được mount từ Vault/SM, không bao giờ là env vars
```

### 7.4. Access Control & Audit

| System | Access Control | Audit |
|---|---|---|
| Loki | No native RBAC (cần Grafana Enterprise or auth proxy) | Logs tất cả queries trong access logs |
| ELK | Role-based, field-level security, spaces | Elastic SIEM, audit logs |
| Splunk | Built-in RBAC, capability-based | Native audit trail, Splunk ES |

**Loki access control workaround:**

```nginx
# nginx reverse proxy với basic auth cho Loki
location /loki/ {
  auth_basic "Restricted Access";
  auth_basic_user_file /etc/nginx/.htpasswd;
  proxy_pass http://loki:3100;
}
```

### 7.5. Failure Isolation

```yaml
# Loki: Cấu hình circuit breaker để tránh cascade failure
loki:
  limits_config:
    reject_old_samples: true
    reject_old_samples_max_age: 168h
    ingestion_rate_strategy: global
    max_global_streams_per_user: 5000  # prevent one user overwhelming the system

# Promtail: Graceful shutdown, không drop logs khi Loki unavailable
promtail:
  clients:
    - url: http://loki:3100/loki/api/v1/push
      backoff_config:
        min_period: 100ms
        max_period: 5s
        max_retries: 10
      batchwait: 3s  # batch logs, giảm request count
      batchsize: 102400
```

---

## 8. Hands-on Example

### Scenario
Deploy Loki + Grafana Agent (Promtail) + Grafana trên local với `docker-compose`. Sau đó deploy một service Go đơn giản, generate logs, và query chúng bằng LogQL.

### 8.1. Directory Structure

```bash
day-41-logging-architecture/
├── docker-compose.yaml
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── loki.yaml
│       └── dashboards/
│           └── logs-dashboard.json
├── loki-config.yaml
├── promtail-config.yaml
├── api-service/
│   ├── main.go
│   ├── go.mod
│   └── Dockerfile
└── queries/
    └── logql-examples.sh
```

### 8.2. Docker Compose Setup

```yaml
# docker-compose.yaml
version: "3.8"

services:
  loki:
    image: grafana/loki:3.2.1
    container_name: loki
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml:ro
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3100/ready"]
      interval: 10s
      timeout: 5s
      retries: 3

  promtail:
    image: grafana/promtail:3.2.1
    container_name: promtail
    volumes:
      - ./promtail-config.yaml:/etc/promtail/config.yaml:ro
      - /var/log:/var/log:ro        # đọc system logs
      - ./api-service/logs:/var/log/api-service:ro  # đọc app logs
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command: -config.file=/etc/promtail/config.yaml
    depends_on:
      - loki

  grafana:
    image: grafana/grafana:11.5.2
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - loki
    restart: unless-stopped

  # Sample API service để generate logs
  api-service:
    build: ./api-service
    container_name: api-service
    ports:
      - "8080:8080"
    volumes:
      - ./api-service/logs:/app/logs
    environment:
      - LOG_LEVEL=info
      - LOG_OUTPUT=/app/logs/app.log
    restart: unless-stopped

volumes:
  loki-data:
  grafana-data:

networks:
  default:
    name: logging-network
```

### 8.3. Loki Config

```yaml
# loki-config.yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9095

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 50
  max_streams_per_user: 0
  retention_period: 15d

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  deletion_mode: filter-only

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

ruler:
  alertmanager_url: http://localhost:9093
```

### 8.4. Promtail Config

```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/log/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push
    tenant_id: workshop
    batchwait: 1s
    batchsize: 102400
    timeout: 10s
    backoff_config:
      min_period: 500ms
      max_period: 5m
      max_retries: 10

scrape_configs:
  # Scrape system logs
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: system
          host: ${HOSTNAME}
          __path__: /var/log/syslog
        pipeline_stages:
          - regex:
              expression: '^(?P<timestamp>\w+\s+\d+\s+\d+:\d+:\d+)\s+(?P<hostname>\S+)\s+(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?\s+(?P<message>.*)$'

  # Scrape API service logs
  - job_name: api-service
    static_configs:
      - targets:
          - localhost
        labels:
          job: api-service
          env: workshop
          __path__: /var/log/api-service/*.log
    pipeline_stages:
      - json:
          expressions:
            timestamp: timestamp
            level: level
            service: service
            message: message
            request_id: request_id
            user_id: user_id
            duration_ms: duration_ms
            status_code: status_code
            path: path
            method: method
            error: error
            stack: stack
      - labels:
          level: level
          service: service
          job: job
          env: env
      - timestamp:
          source: timestamp
          format: RFC3339
      - replace:
          expression: '(password|token|secret|key|authorization)["\s:=]+[^\s,"}]+'
          replace: '$1=[REDACTED]'
```

### 8.5. API Service (Go)

```go
// api-service/main.go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"time"

	"github.com/google/uuid"
)

type logEntry struct {
	Timestamp   string `json:"timestamp"`
	Level       string `json:"level"`
	Service     string `json:"service"`
	Message     string `json:"message"`
	RequestID   string `json:"request_id"`
	UserID      string `json:"user_id,omitempty"`
	Path        string `json:"path,omitempty"`
	Method      string `json:"method,omitempty"`
	StatusCode  int    `json:"status_code,omitempty"`
	DurationMs  int64  `json:"duration_ms,omitempty"`
	Error       string `json:"error,omitempty"`
	Stack       string `json:"stack,omitempty"`
}

func init() {
	// Ensure log directory exists
	os.MkdirAll("/app/logs", 0755)
}

func writeLog(level, msg string, attrs map[string]string) {
	entry := logEntry{
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Level:     level,
		Service:   "api-service",
		Message:   msg,
	}
	for k, v := range attrs {
		switch k {
		case "request_id":
			entry.RequestID = v
		case "user_id":
			entry.UserID = v
		case "path":
			entry.Path = v
		case "method":
			entry.Method = v
		case "status_code":
			fmt.Sscanf(v, "%d", &entry.StatusCode)
		case "duration_ms":
			fmt.Sscanf(v, "%d", &entry.DurationMs)
		case "error":
			entry.Error = v
		}
	}

	data, _ := json.Marshal(entry)
	f, _ := os.OpenFile("/app/logs/app.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	fmt.Fprintln(f, string(data))
	f.Close()
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		requestID := r.Header.Get("X-Request-ID")
		if requestID == "" {
			requestID = uuid.New().String()
		}
		w.Header().Set("X-Request-ID", requestID)

		// Simulate user authentication
		userID := fmt.Sprintf("user-%d", rand.Intn(100)+1)

		// Call next handler
		next.ServeHTTP(w, r)

		duration := time.Since(start).Milliseconds()
		statusCode := http.StatusOK
		level := "info"
		message := fmt.Sprintf("%s %s completed", r.Method, r.URL.Path)

		// Simulate occasional errors
		if rand.Float32() < 0.1 {
			statusCode = http.StatusInternalServerError
			level = "error"
			message = fmt.Sprintf("%s %s failed: connection timeout", r.Method, r.URL.Path)
			writeLog(level, message, map[string]string{
				"request_id":  requestID,
				"user_id":     userID,
				"path":        r.URL.Path,
				"method":      r.Method,
				"status_code": fmt.Sprintf("%d", statusCode),
				"duration_ms": fmt.Sprintf("%d", duration),
				"error":       "connection timeout",
			})
			return
		}

		if r.URL.Path == "/health" {
			level = "debug"
			message = "Health check"
		}

		writeLog(level, message, map[string]string{
			"request_id":  requestID,
			"user_id":     userID,
			"path":        r.URL.Path,
			"method":      r.Method,
			"status_code": fmt.Sprintf("%d", statusCode),
			"duration_ms": fmt.Sprintf("%d", duration),
		})
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeLog("debug", "Health check endpoint", map[string]string{
			"request_id": r.Header.Get("X-Request-ID"),
		})
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})
	mux.HandleFunc("/api/users", func(w http.ResponseWriter, r *http.Request) {
		writeLog("info", "Listing users", map[string]string{
			"request_id": r.Header.Get("X-Request-ID"),
			"user_id":    "admin",
			"path":       "/api/users",
			"method":     r.Method,
		})
		json.NewEncoder(w).Encode(map[string][]map[string]string{
			{"users": []map[string]string{
				{"id": "1", "name": "Alice"},
				{"id": "2", "name": "Bob"},
			}},
		})
	})
	mux.HandleFunc("/api/orders", func(w http.ResponseWriter, r *http.Request) {
		writeLog("info", "Creating order", map[string]string{
			"request_id": r.Header.Get("X-Request-ID"),
			"user_id":    fmt.Sprintf("user-%d", rand.Intn(100)+1),
			"path":       "/api/orders",
			"method":     r.Method,
		})
		json.NewEncoder(w).Encode(map[string]string{"order_id": uuid.New().String()})
	})

	handler := loggingMiddleware(mux)
	log.Println("API service starting on :8080")
	if err := http.ListenAndServe(":8080", handler); err != nil {
		log.Fatal(err)
	}
}
```

```dockerfile
# api-service/Dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY *.go .
RUN CGO_ENABLED=0 GOOS=linux go build -o api-service .

FROM alpine:3.20
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/api-service .
RUN mkdir -p logs
CMD ["./api-service"]
```

```makefile
# api-service/go.mod
module api-service

go 1.23

require github.com/google/uuid v1.6.0
```

### 8.6. Start Everything

```bash
# Create directories
mkdir -p api-service/logs

# Build and start all services
docker-compose up -d --build

# Wait for services to be healthy
sleep 10

# Check Loki is running
curl http://localhost:3100/ready
# Expected: OK

# Check Grafana is running
curl http://localhost:3000/api/health
# Expected: {"commit":"...","database":"ok","version":"..."}
```

### 8.7. Generate Traffic

```bash
# Generate some API traffic
for i in {1..20}; do
  curl -s http://localhost:8080/api/users > /dev/null
  curl -s http://localhost:8080/api/orders > /dev/null
  curl -s http://localhost:8080/health > /dev/null
  sleep 0.2
done

# Check the log file was created
cat api-service/logs/app.log | head -5
# Expected: JSON log entries with fields: timestamp, level, service, message, request_id, etc.
```

### 8.8. Query via Grafana UI

```
1. Open http://localhost:3000 (admin / admin123)
2. Go to Connections → Data Sources → Loki
   URL: http://loki:3100
   Save & Test → "Data source is working"
3. Go to Explore → Select Loki data source
4. Run LogQL queries (see section 8.9)
```

### 8.9. LogQL Queries

```bash
# Save to queries/logql-examples.sh

# --- Query 1: Xem tất cả logs từ api-service ---
echo '{job="api-service"}'
# Trong Grafana: {job="api-service"}
# Expected: List of JSON log entries

# --- Query 2: Filter theo ERROR level ---
echo '{job="api-service"} |= "error"'
# Trong Grafana: {job="api-service"} |= "error"
# Expected: Chỉ các dòng chứa "error"

# --- Query 3: Filter theo level label ---
echo '{job="api-service", level="error"}'
# Expected: Logs có label level=error (Promtail gắn label từ JSON field)

# --- Query 4: Count errors per minute ---
echo 'sum by (level) (count_over_time({job="api-service"}[1m]))'
# Expected: Table với count theo level mỗi phút

# --- Query 5: Parse JSON fields (unwrap) ---
echo '{job="api-service"} | json | status_code >= 500'
# Expected: Requests có status_code >= 500

# --- Query 6: Trace one request by correlation ID ---
# First get a request_id from a log entry
echo '{job="api-service"} | json | request_id == "COPY-REQUEST-ID-HERE"'
# Expected: Tất cả log entries cho request đó

# --- Query 7: Latency distribution ---
echo 'quantile_over_time(0.99,
  {job="api-service"} | json | unwrap duration_ms [5m]
) by (path)'
# Expected: P99 latency theo endpoint

# --- Query 8: Error rate per minute ---
echo 'sum(rate({job="api-service"} |= "error"[1m])) by (job)'
# Expected: Error events per second

# --- Query 9: Show unique users making requests ---
echo 'count by (user_id) ({job="api-service"} | json | user_id != "")'
# Expected: Unique user count

# --- Query 10: Log volume over time (rate) ---
echo 'sum(rate({job="api-service"}[5m])) by (job)'
# Expected: Log lines per second
```

### 8.9. Verify Setup

```bash
# 1. Verify Loki API
curl -s "http://localhost:3100/loki/api/v1/label/job/values" | jq .
# Expected: {"status":"success","data":["system","api-service"]}

# 2. Verify recent log entries
curl -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={job="api-service"}' \
  --data-urlencode 'limit=5' \
  --data-urlencode 'start=0' | jq '.data.result | length'
# Expected: >= 0 (depends on traffic generated)

# 3. Count log entries per level
curl -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query=sum by (level) (count_over_time({job="api-service"}[5m]))' \
  | jq '.data.result'
# Expected: [{"metric":{"level":"info"},"value":[...]}]

# 4. Check Promtail is scraping
docker logs promtail 2>&1 | grep -i "target" | head -5
# Expected: "target='api-service'" logs
```

### 8.10. Cleanup

```bash
# Stop all services and remove volumes
docker-compose down -v

# Remove log files
rm -rf api-service/logs

# Remove build artifacts
rm -rf api-service/api-service

echo "Cleanup complete. All containers, volumes, and logs removed."
```

---

## 9. Common Pitfalls & Debugging

### 9.1. Loki Common Issues

| Issue | Cause | Fix |
|---|---|---|
| **Query timeout** | Query quá rộng (không có label filter) | Thêm label filter: `{job="api", level="error"}` |
| **Logs bị dropped** | Ingester OOM | Tăng memory cho ingesters, giảm `ingestion_rate_mb` |
| **Promtail không scrape** | File path sai, permission denied | Check `__path__` labels, verify file exists |
| **Log entries bị deduplicated** | `stream_labels` giống nhau | Đảm bảo mỗi stream có unique label set |
| **Query returns no data** | Wrong time range | Check `from`/`to` range, logs chưa được ingested |
| **"too many outstanding requests"** | Querier overloaded | Scale queriers, enable caching |

### 9.2. Debugging Commands

```bash
# 1. Check Loki ingester status
curl -s http://localhost:3100/ingester/shutdown

# 2. Check Promtail targets
curl -s http://promtail:9080/targets | jq .

# 3. Check Promtail positions file (what's been scraped)
docker exec promtail cat /var/log/positions.yaml

# 4. Loki storage stats
curl -s http://localhost:3100/loki/storage/stats | jq .

# 5. Loki ingester memory
curl -s http://localhost:3100/ingester/ring_status | jq '.shards'

# 6. Check Elasticsearch cluster health (ELK alternative)
curl -s http://localhost:9200/_cluster/health?pretty | jq '.status'
# green = all shards allocated, yellow = 1 replica unassigned, red = primary lost

# 7. Elasticsearch index stats
curl -s http://localhost:9200/_cat/indices?v | head -20

# 8. Check Splunk search head (Splunk alternative)
# Via Splunk Web or CLI:
# ./splunk search 'index=_internal | head 10'
# ./splunk show servername

# 9. Loki rule evaluation errors
curl -s http://localhost:3100/ruler/ring | jq '.instances[].lastEval'

# 10. End-to-end log pipeline test
echo '{"streams":[{"labels":"{job=\"test\"}","entries":[{"ts":"2026-05-12T10:00:00Z","line":"test log"}]}]}' \
  | curl -s -H "Content-Type: application/json" -d @- \
  http://localhost:3100/loki/api/v1/push

# Verify it appears
curl -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={job="test"}' | jq '.data.result | length'
# Expected: 1
```

### 9.3. Case Study: Debugging a 500 Error Storm

**Bối cảnh:**
```
Ngày 12/05/2026, 14:23 UTC
On-call nhận alert: Error rate API service = 15% (threshold: 5%)
Dashboard Grafana: P99 latency = 8s (normal: 200ms)
```

**Debug steps:**

```bash
# Step 1: Tìm logs error gần đây
{job="api-service", level="error"} | json
# → Thấy: "Connection refused to db:5432"

# Step 2: Xem thời điểm bắt đầu
{job="api-service", level="error"} | json | line_format "{{.timestamp}} {{.error}}"
# → Thấy: Bắt đầu lúc 14:20, tăng dần

# Step 3: Correlate với metrics
# Query Prometheus: db_connection_pool_available
# → Thấy: Pool giảm từ 100 → 0 tại 14:19

# Step 4: Trace với correlation ID
# Lấy request_id từ error logs
# Query: {request_id="COPY-ID"} |= ""
# → Thấy: 
#   14:19:00 - Connection opened ✓
#   14:19:01 - Query "SELECT *" executed (slow) ✓
#   14:19:30 - Query timeout
#   14:20:00 - Connection pool exhausted

# Root cause: Một query "SELECT * FROM orders" chạy trên 30s,
# chiếm hết connection pool → tất cả requests sau đó bị refused

# Step 5: Fix
# a) Kill the slow query
# b) Add query timeout: SET statement_timeout = '30s'
# c) Add connection pool limit: max_connections=50
# d) Add index on orders.created_at

# Step 6: Verify
# Error rate về 0% sau 2 phút
# Monitor: {job="api-service", level="error"} rate = 0
```

**Postmortem:**
- Root cause: Slow query không có timeout → connection pool exhaustion
- Contributing: Không có query monitoring → slow query không được phát hiện sớm
- Action items: Add slow query log, connection pool metrics, query timeout enforcement

---

## 10. Kết nối với bài trước & bài sau

### Kết nối với Day 40 (Grafana Dashboard & Alerting)

Day 40 ta đã học cách tạo dashboard metrics và alert. Logs là **bổ sung cho metrics** trong observability stack:

```
Metrics (Day 39-40):      "Error rate = 15%"  ← WHAT happened? (quantitative)
Logs (Day 41):            "DB connection refused at 14:19"  ← WHY? (context)
Traces (Day 42):          Full request flow across services  ← HOW? (causality)
SLOs/Error Budget (Day 43): "Still within budget?"  ← SHOULD we panic?
```

Grafana Alerting có thể dùng **logs-based alerts** (via Loki Ruler hoặc Grafana Alerting):

```yaml
# Loki ruler: Alert khi error rate từ logs vượt ngưỡng
groups:
  - name: api-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({job="api-service"} |= "error"[5m])) by (job)
          / sum(rate({job="api-service"}[5m])) by (job) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "API error rate > 5%"
          runbook: "https://wiki.internal/runbooks/high-error-rate"
```

### Kết nối với Day 42 (OpenTelemetry & Distributed Tracing)

Day 42 sẽ học về **Distributed Tracing** — correlation ID trong logs chính là `trace_id`/`span_id` trong OpenTelemetry:

```
Day 41 - Logs:
  {request_id="abc-123", correlation_id="abc-123"}

Day 42 - OpenTelemetry:
  span.trace_id = "abc-123" (maps to correlation_id)
  span.attributes["user.id"] = "12345"
  span.events[] = log entries gắn với span
```

**Key connection:** Structured logging với correlation ID = foundation để integrate với OpenTelemetry traces. OTEL SDK tự động gắn `trace_id` vào logs nếu logger được instrumented:

```go
// OpenTelemetry + structured logging integration
import "go.opentelemetry.io/otel/log"
import "github.com/rs/zerolog"

func init() {
    // Zerolog with OTEL trace context
    zerolog.TimeFieldFormat = time.RFC3339Nano
    logger = zerolog.New(os.Stdout).With().
        Timestamp().
        Str("service", "api-service").
        Logger()
}

// In request handler — trace_id tự động được gắn
span.AddEvent("log", log.Int("status", 200), log.Int("duration_ms", latency))
```

**3 Pillars unified in Grafana:**
- Metrics Panel → Prometheus
- Logs Panel → Loki (with trace_id link)
- Traces Panel → Tempo (Day 42)

Grafana Explore cho phép drill-down từ **metric** → **log** → **trace** trong một giao diện duy nhất.

---

## 11. Tài liệu tham khảo

### Must-read

1. **Grafana Loki Documentation** — https://grafana.com/docs/loki/latest/
   - Official docs cho Loki. Đọc sections: Architecture, LogQL, Operations
   - Quan trọng: phân biệt `|=` vs `|~` trong LogQL

2. **Prometheus Operator / Promtail** — https://grafana.com/docs/loki/latest/send-data/promtail/
   - Pipeline stages: cách transform logs trước khi gửi Loki

3. **Elasticsearch: The Definitive Guide** — https://www.elastic.co/guide/en/elasticsearch/guide/current/index.html
   - Mapping, inverted index, sharding — hiểu bên trong ELK

4. **Splunk Documentation: Search Processing Language (SPL)** — https://docs.splunk.com/Documentation/SPLX/latest
   - SPL là ngôn ngữ mạnh nhất trong 3 hệ thống

### Nice-to-have

5. **Loki Architecture Deep Dive (Grafana blog)** — https://grafana.com/blog/2024/xx/loki-deep-dive/
   - Chi tiết về chunk format, compaction, retention

6. **Elasticsearch ILM (Index Lifecycle Management)** — https://www.elastic.co/guide/en/elasticsearch/reference/current/ilm-overview.html
   - Hot-warm-cold tier, cách tiết kiệm chi phí

7. **Splunk Architecture — Splunk Enterprise Clustering** — https://docs.splunk.com/Documentation/Splunk/latest/Clustering/UCNEXT
   - Indexer clustering, search head pooling

8. **OWASP Logging Cheat Sheet** — https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
   - Security best practices cho logging

### Deep-dive

9. **Parquet Format & Columnar Storage** — https://parquet.apache.org/docs/
   - Hiểu tại sao Loki (Parquet-like) nhanh hơn pure text search

10. **Google Dapper / Distributed Tracing Paper** — https://research.google/pubs/large-scale-distributed-systems-tracing-infrastructure/
    - Nền tảng lý thuyết cho correlation ID và distributed tracing

11. **The Economics of Logging** — https://www.datawire.io/blog/the-economics-of-logging/
    - Phân tích chi phí thực tế của ELK vs Loki vs Splunk

12. **Elasticsearch in Production: Lessons Learned** — https://www.elastic.co/blog/found-elasticsearch-in-production
    - Common pitfalls khi vận hành Elasticsearch cluster

---

*Time allocation: 20min concepts + 25min deep-dive/trade-offs + 50min hands-on + 15min debugging/checklist + 10min reflection*

