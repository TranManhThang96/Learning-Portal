# Day 39: Prometheus & PromQL

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Hiểu sâu Prometheus architecture** — pull model, TSDB, service discovery, và vì sao Prometheus trở thành de facto standard cho Kubernetes monitoring.
2. **Viết được PromQL queries** cho production use cases: RPS, error rate, p50/p90/p99 latency, saturation — không chỉ copy-paste mà hiểu cơ chế.
3. **Phân biệt và sử dụng đúng 4 metric types**: Counter, Gauge, Histogram, Summary — biết khi nào dùng loại nào.
4. **Thiết kế được recording rules và alert rules** giảm query load và cung cấp alert kịp thời.
5. **Hiểu được cardinality explosion** — nguyên nhân #1 gây Prometheus OOM — và cách phòng tránh.
6. **So sánh được Thanos vs Mimir** cho long-term storage và multi-cluster monitoring.

---

## 2. Bối cảnh & Động lực

### Vì sao Prometheus?

Prometheus ra đời năm 2012 tại SoundCloud, lấy cảm hứng từ Borgmon (hệ thống monitoring nội bộ của Google). Năm 2016, Prometheus trở thành project CNCF thứ 2 (sau Kubernetes).

**Vì sao Prometheus thắng?**

| Yếu tố | Prometheus | Alternatives (trước đó) |
|--------|-----------|------------------------|
| **Model** | Pull-based, dimensional | Push-based (StatsD, Graphite) |
| **Data model** | Labels (multi-dimensional) | Dot-separated names (`server.cpu.usage`) |
| **Query** | PromQL (powerful) | Graphite query (limited) |
| **Integration** | Native Kubernetes | Phải custom |
| **Ecosystem** | Exporters, Grafana, AlertManager | Fragmented |

### Pull vs Push model

```
Pull Model (Prometheus):
  ┌──────────┐     scrape /metrics     ┌──────────┐
  │Prometheus │ ──────────────────────► │   App    │
  │  Server   │     every 15s          │ :8080    │
  └──────────┘                          └──────────┘
  
  ✅ Prometheus biết target nào UP/DOWN
  ✅ Không cần cấu hình phía app gửi đi đâu
  ✅ Backpressure tự nhiên (Prometheus control tốc độ)
  ❌ App phải expose HTTP endpoint
  ❌ Khó scrape qua firewall/NAT

Push Model (StatsD/Datadog Agent):
  ┌──────────┐     push metrics        ┌──────────┐
  │   App    │ ──────────────────────► │ Collector│
  │ :8080    │     on each event       │ :8125    │
  └──────────┘                          └──────────┘
  
  ✅ Hoạt động qua firewall
  ✅ Phù hợp short-lived jobs (Lambda, batch)
  ❌ Collector không biết target nào down
  ❌ Push storm có thể overwhelm collector
```

### Liên hệ với developer

- **Prometheus data model** giống column-oriented database: mỗi metric name = table, labels = columns, value = data.
- **PromQL** giống SQL cho time series: `SELECT`, `WHERE`, `GROUP BY`, `aggregation functions`.
- **Pull model** giống health check pattern: hệ thống chủ động kiểm tra thay vì chờ báo cáo.
- **Recording rules** giống database materialized views: pre-compute expensive queries.
- **Cardinality** giống database index explosion: thêm 1 index (label) = multiply storage.

---

## 3. Kiến thức nền tảng

### 3.1 Prometheus Data Model

Mỗi time series được định danh bởi:
- **Metric name**: Tên metric (vd: `http_requests_total`).
- **Labels**: Key-value pairs mô tả dimensions (vd: `{method="GET", status="200"}`).
- **Timestamp**: Thời điểm ghi nhận (milliseconds).
- **Value**: Giá trị số (float64).

```
http_requests_total{method="GET", path="/api/orders", status="200"} 1234 1705312425000
│                   │                                                │    │
metric name         labels                                          value timestamp
```

**Naming convention**:
```
# Counter: noun_verb_total
http_requests_total
errors_total
bytes_sent_total

# Histogram: noun_unit (auto _bucket, _sum, _count)
http_request_duration_seconds
response_size_bytes

# Gauge: noun_unit hoặc noun_status
temperature_celsius
active_connections
queue_size
```

### 3.2 Metric Types chi tiết

**Counter** — chỉ tăng, reset khi restart:
```
# t=0:  http_requests_total = 0
# t=1:  http_requests_total = 5    (+5 requests)
# t=2:  http_requests_total = 12   (+7 requests)
# t=3:  RESTART → http_requests_total = 0
# t=4:  http_requests_total = 3    (+3 requests)
#
# rate() xử lý reset tự động:
# rate(http_requests_total[1m]) = ~requests/second
```

**Gauge** — giá trị hiện tại, tăng hoặc giảm:
```
# t=0:  active_connections = 10
# t=1:  active_connections = 15   (+5 new connections)
# t=2:  active_connections = 8    (-7 connections closed)
#
# Không dùng rate() cho gauge
# Dùng trực tiếp: active_connections
# Hoặc: avg_over_time(active_connections[5m])
```

**Histogram** — đo distribution, chia vào buckets:
```
# Request durations: 50ms, 120ms, 200ms, 80ms, 500ms, 150ms

http_request_duration_seconds_bucket{le="0.05"}  1    # 1 request ≤ 50ms
http_request_duration_seconds_bucket{le="0.1"}   2    # 2 requests ≤ 100ms
http_request_duration_seconds_bucket{le="0.25"}  5    # 5 requests ≤ 250ms
http_request_duration_seconds_bucket{le="0.5"}   6    # 6 requests ≤ 500ms
http_request_duration_seconds_bucket{le="+Inf"}  6    # All requests
http_request_duration_seconds_sum   1.1              # Tổng duration
http_request_duration_seconds_count 6                # Tổng requests
```

### 3.3 Scrape & Service Discovery

```yaml
# prometheus.yml
global:
  scrape_interval: 15s       # Mặc định scrape mỗi 15s
  scrape_timeout: 10s        # Timeout cho mỗi scrape
  evaluation_interval: 15s   # Evaluation rules mỗi 15s

scrape_configs:
  # Static targets
  - job_name: 'my-app'
    static_configs:
      - targets: ['app:8080']
    metrics_path: /metrics

  # Kubernetes Service Discovery
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: $1
```

---

## 4. Deep Dive

### 4.1 Prometheus Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Prometheus Server                         │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Retrieval    │  │   TSDB       │  │  HTTP Server      │  │
│  │              │  │              │  │                   │  │
│  │  - Scrape    │  │  - WAL       │  │  - PromQL query  │  │
│  │  - SD        │──►│  - Blocks    │──►│  - API          │  │
│  │  - Relabel   │  │  - Compaction │  │  - Federation   │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
│         │                                      │              │
│         │              ┌───────────────┐       │              │
│         │              │  Rule Engine  │       │              │
│         │              │               │       │              │
│         │              │  - Recording  │       │              │
│         │              │  - Alerting   │───────┘              │
│         │              └───────┬───────┘                      │
│         │                      │                              │
└─────────┼──────────────────────┼──────────────────────────────┘
          │                      │
          ▼                      ▼
  ┌───────────────┐    ┌─────────────────┐
  │  Targets       │    │  AlertManager   │
  │  (apps, nodes, │    │                 │
  │   exporters)   │    │  - Dedup        │
  │                │    │  - Group        │
  │ app:8080       │    │  - Route        │
  │ node:9100      │    │  - Silence      │
  │ mysql:9104     │    │  - Notify       │
  └───────────────┘    │  (Slack/PD/Email)│
                        └─────────────────┘
```

### 4.2 TSDB Internals (tóm tắt)

```
Time Series Database:
  
  ┌─────────┐     ┌─────────┐     ┌─────────┐
  │  WAL    │     │ Block 1  │     │ Block 2  │
  │ (Write  │     │ (2h old) │     │ (4h old) │
  │  Ahead  │     │          │     │          │
  │  Log)   │     │ chunks/  │     │ chunks/  │
  │         │     │ index    │     │ index    │
  │ In-mem  │     │ meta.json│     │ meta.json│
  └─────────┘     └─────────┘     └─────────┘
       │                │               │
       └────────────────┴───────────────┘
                        │
                   Compaction
                   (merge blocks)
```

- **WAL**: Ghi data vào Write-Ahead Log trước → crash recovery.
- **Head block**: Data trong memory (2 giờ gần nhất).
- **Persisted blocks**: Blocks trên disk, mỗi block = 2 giờ data.
- **Compaction**: Merge blocks nhỏ thành blocks lớn → optimize query.

### 4.3 PromQL Deep Dive

#### Instant Vector vs Range Vector

```promql
# Instant Vector — giá trị tại một thời điểm
http_requests_total{status="200"}
# Returns: {method="GET", status="200"} 1234

# Range Vector — giá trị trong khoảng thời gian
http_requests_total{status="200"}[5m]
# Returns: {method="GET", status="200"} 1200 @1705312200
#                                        1210 @1705312215
#                                        1220 @1705312230
#                                        1234 @1705312245
```

#### Functions quan trọng

```promql
# rate() — tốc độ tăng per second (cho Counter)
rate(http_requests_total[5m])
# "Trung bình bao nhiêu requests/second trong 5 phút qua"

# irate() — instant rate (2 samples gần nhất)
irate(http_requests_total[5m])
# Nhạy hơn rate(), nhưng noisy hơn

# increase() — tổng tăng trong window
increase(http_requests_total[1h])
# "Tổng bao nhiêu requests trong 1 giờ qua"

# histogram_quantile() — tính percentile từ histogram
histogram_quantile(0.99,
  rate(http_request_duration_seconds_bucket[5m])
)
# "p99 latency trong 5 phút qua"

# avg_over_time() — trung bình trong window (cho Gauge)
avg_over_time(node_memory_usage_bytes[1h])

# predict_linear() — dự đoán tuyến tính
predict_linear(node_filesystem_avail_bytes[6h], 24*3600)
# "Disk sẽ còn bao nhiêu bytes sau 24 giờ nếu trend hiện tại tiếp tục"
```

#### Aggregation Operators

```promql
# sum — tổng
sum(rate(http_requests_total[5m])) by (service)
# Total RPS per service

# avg — trung bình
avg(rate(http_requests_total[5m])) by (service)

# max / min
max(http_request_duration_seconds_bucket) by (service)

# count — đếm số series
count(up == 1)
# Bao nhiêu targets đang UP

# topk — top N
topk(5, sum(rate(http_requests_total[5m])) by (path))
# Top 5 endpoints by RPS

# quantile — percentile across series (khác histogram_quantile)
quantile(0.9, rate(http_requests_total[5m]))
```

#### Binary Operators

```promql
# Arithmetic: + - * / % ^
node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes
# Memory used

# Comparison: == != > < >= <=
http_requests_total > 1000

# Logical: and, or, unless
up == 1 and rate(http_requests_total[5m]) > 0
# Targets UP và đang nhận traffic
```

### 4.4 Recording Rules

Recording rules pre-compute expensive PromQL queries và save kết quả thành time series mới:

```yaml
# recording-rules.yml
groups:
  - name: service_metrics
    interval: 30s
    rules:
      # RPS per service
      - record: service:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (service)

      # Error rate per service
      - record: service:http_errors:ratio5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)

      # p99 latency per service
      - record: service:http_latency:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
          )

      # p50 latency per service
      - record: service:http_latency:p50_5m
        expr: |
          histogram_quantile(0.50,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
          )
```

**Naming convention cho recording rules**:
```
level:metric:operations
───── ────── ──────────
  │     │       └── rate5m, ratio5m, p99_5m
  │     └────────── original metric name
  └──────────────── aggregation level (service, cluster, global)
```

### 4.5 Cardinality Explosion ⚠️

**Cardinality** = tổng số unique time series = product of all label value combinations.

```
# Safe: 4 methods × 10 paths × 5 status codes = 200 series ✅
http_requests_total{method, path, status}

# DANGEROUS: 4 methods × 1M users = 4M series ❌
http_requests_total{method, user_id}

# CATASTROPHIC: 4 methods × 1M users × 1M request_ids = 4T series 💀
http_requests_total{method, user_id, request_id}
```

**Impact**:
- 1M active series: ~3GB RAM cho Prometheus.
- 10M active series: ~30GB RAM → Prometheus OOM trên most servers.
- 100M active series: Không khả thi với single Prometheus.

**Rules**:
- Metric labels chỉ chứa **bounded, low-cardinality values**: method, status, service name, endpoint.
- **KHÔNG** dùng: user_id, request_id, IP address, session_id, order_id.
- Unbounded values → Log hoặc Trace, KHÔNG PHẢI metrics.

### 4.6 Long-term Storage: Thanos vs Mimir

Prometheus mặc định retention 15 ngày. Cho long-term storage, cần solution bên ngoài:

| | Thanos | Mimir (Grafana) |
|--|--------|-----------------|
| **Architecture** | Sidecar + Store Gateway + Compactor | Distributed (all-in-one or microservices) |
| **Storage** | Object store (S3/GCS/MinIO) | Object store (S3/GCS/MinIO) |
| **Query** | Thanos Query (multi-store) | Distributed query engine |
| **HA** | Multi-replica dedup | Built-in replication |
| **Global view** | Federation across clusters | Multi-tenant, cross-cluster |
| **Complexity** | Medium-High (nhiều components) | Medium (simpler deployment) |
| **Best for** | Multi-cluster, existing Prom | High-scale, Grafana ecosystem |

```
Thanos Architecture:
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │Prometheus │  │Prometheus │  │Prometheus │
  │ Cluster A │  │ Cluster B │  │ Cluster C │
  │ + Sidecar │  │ + Sidecar │  │ + Sidecar │
  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
        │               │               │
        ▼               ▼               ▼
  ┌──────────────────────────────────────────┐
  │           Object Store (S3)               │
  └──────────────────┬───────────────────────┘
                     │
              ┌──────▼──────┐
              │ Thanos Query │  ← Global query across clusters
              └──────┬───────┘
                     │
              ┌──────▼──────┐
              │   Grafana    │
              └──────────────┘
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Prometheus vs Alternatives

| | Prometheus | InfluxDB | Datadog | CloudWatch |
|--|-----------|----------|---------|------------|
| **Model** | Pull | Push | Push (agent) | Push (agent) |
| **Query** | PromQL | InfluxQL/Flux | Proprietary | Proprietary |
| **Cost** | Free (infra only) | Free/Enterprise | $$$ per host | $$$ per metric |
| **K8s integration** | Native | Good | Good | AWS only |
| **Long-term** | Thanos/Mimir | Built-in | Built-in | Built-in |
| **Vendor lock-in** | None | Low | High | Very High |
| **Best for** | K8s/cloud-native | IoT, custom TSDB | "Just works" SaaS | AWS-only shops |

### 5.2 Best Practices

**Scrape configuration**:
- `scrape_interval: 15s` — mặc định đủ tốt cho hầu hết services.
- `scrape_timeout` < `scrape_interval` — tránh scrape overlap.
- Dùng service discovery thay static config trong Kubernetes.

**Metric design**:
- Follow naming conventions: `namespace_subsystem_name_unit`.
- Counter suffix `_total`, histogram/summary suffix `_seconds` hoặc `_bytes`.
- Giới hạn labels: max 5-7 labels per metric.
- Test cardinality trước khi deploy: ước tính total series.

**Query optimization**:
- Dùng recording rules cho queries dùng trong dashboards.
- Tránh regex matching trên high-cardinality labels.
- Dùng `rate()` thay `irate()` cho dashboards (smoother).
- Dùng `irate()` cho alerts (more responsive).

### 5.3 Anti-patterns

1. **Push via Pushgateway cho long-lived services**: Pushgateway dành cho batch jobs, không phải services.
2. **Scrape interval quá ngắn (1s)**: Tăng load, tăng storage, ít lợi ích thêm.
3. **`rate()` window nhỏ hơn 2× scrape_interval**: Thiếu data points → kết quả sai.
4. **Label values từ user input**: Injection risk + cardinality explosion.
5. **Không có recording rules**: Dashboard load chậm vì compute mỗi lần query.

---

## 6. Performance & Scalability ⭐

### 6.1 Prometheus Resource Sizing

| Active Time Series | RAM (estimate) | CPU | Disk (15d retention) |
|-------------------|----------------|-----|---------------------|
| 100K | 1-2 GB | 0.5 core | 10 GB |
| 1M | 5-8 GB | 1-2 cores | 50 GB |
| 5M | 20-30 GB | 4-6 cores | 200 GB |
| 10M | 40-60 GB | 8-12 cores | 400 GB |
| >10M | Consider sharding/Mimir | - | - |

### 6.2 Query Performance

- **Simple instant query**: < 10ms.
- **Range query 24h, 1M series**: 100-500ms.
- **Range query 7d, 10M series**: 1-5 seconds.
- **Complex aggregation with regex**: 5-30 seconds → cần recording rule.

### 6.3 Optimizations

- **Recording rules**: Pre-compute expensive queries → dashboard load < 100ms.
- **Scrape interval tuning**: 30s cho less-critical services → reduce series ingestion 50%.
- **Label dropping**: `metric_relabel_configs` drop unnecessary labels at scrape time.
- **Compaction tuning**: Default đủ tốt cho hầu hết setups.
- **WAL compression**: Enable `--storage.tsdb.wal-compression` → reduce disk I/O.

---

## 7. Security & Reliability Considerations

### 7.1 Security

- **No built-in auth**: Prometheus mặc định không có authentication. Đặt sau reverse proxy (nginx + basic auth) hoặc dùng OAuth2 proxy.
- **TLS**: Enable `--web.config.file` cho HTTPS.
- **RBAC**: Prometheus không có native RBAC. Dùng Grafana RBAC cho query access control.
- **Sensitive metrics**: Cẩn thận expose business metrics có thể leak revenue/user data.

### 7.2 Reliability - HA Setup

```
                    ┌──────────┐
              ┌────►│ Prom #1  │
              │     └────┬─────┘
              │          │
┌──────────┐  │     ┌────▼─────┐
│  Targets  │──┤     │Deduplicate│ ← Thanos/Mimir handles
└──────────┘  │     └────┬─────┘
              │          │
              │     ┌────▼─────┐
              └────►│ Prom #2  │
                    └──────────┘
```

- 2 Prometheus replicas scrape cùng targets → dedup tại query time.
- AlertManager cluster (3 nodes) → dedup alerts.
- Separate disk cho TSDB → tránh disk contention.

---

## 8. Hands-on Example

### 8.1 Setup Prometheus + Sample App

```bash
mkdir -p /tmp/prom-lab && cd /tmp/prom-lab
```

**File: `docker-compose.yml`**

```yaml
version: '3.8'

services:
  app:
    image: quay.io/brancz/prometheus-example-app:v0.5.0
    ports:
      - "8080:8080"

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./rules.yml:/etc/prometheus/rules.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=1d'
      - '--web.enable-lifecycle'
```

**File: `prometheus.yml`**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - 'rules.yml'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'app'
    static_configs:
      - targets: ['app:8080']
```

**File: `rules.yml`**

```yaml
groups:
  - name: app_recording_rules
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job)

      - record: job:http_errors:ratio5m
        expr: |
          sum(rate(http_requests_total{code=~"5.."}[5m])) by (job)
          /
          sum(rate(http_requests_total[5m])) by (job)

  - name: app_alert_rules
    rules:
      - alert: HighErrorRate
        expr: job:http_errors:ratio5m > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.job }}"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (job, le)
          ) > 1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High p99 latency on {{ $labels.job }}"
```

### 8.2 Chạy và generate traffic

```bash
# Start stack
docker compose up -d

# Wait for Prometheus ready
sleep 10

# Generate traffic
for i in $(seq 1 200); do
  curl -s http://localhost:8080/ > /dev/null
  curl -s http://localhost:8080/err > /dev/null 2>&1 || true
  sleep 0.1
done &

echo "Traffic generator running in background"
```

### 8.3 PromQL Exercises trên Prometheus UI

Truy cập http://localhost:9090 và chạy từng query:

```promql
# 1. RPS tổng
rate(http_requests_total[5m])

# 2. RPS per endpoint
sum(rate(http_requests_total[5m])) by (code)

# 3. Error rate (%)
sum(rate(http_requests_total{code=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# 4. p50 latency
histogram_quantile(0.50,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# 5. p90 latency
histogram_quantile(0.90,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# 6. p99 latency
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# 7. Total requests trong 1 giờ
increase(http_requests_total[1h])

# 8. Prometheus self-monitoring: series count
prometheus_tsdb_head_series

# 9. Scrape duration
prometheus_target_interval_length_seconds

# 10. Check recording rule
job:http_requests:rate5m

# 11. Check alerts
ALERTS{alertstate="firing"}

# 12. Up/Down targets
up
```

### 8.4 Expected outputs

```bash
# Verify targets UP
curl -s http://localhost:9090/api/v1/targets | \
  python3 -c "import sys,json; \
  targets=json.load(sys.stdin)['data']['activeTargets']; \
  [print(f\"{t['labels']['job']}: {t['health']}\") for t in targets]"
# Expected:
# prometheus: up
# app: up

# Verify recording rules
curl -s 'http://localhost:9090/api/v1/query?query=job:http_requests:rate5m' | \
  python3 -m json.tool
# Expected: có value > 0

# Verify series count
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' | \
  python3 -c "import sys,json; \
  print('Series:', json.load(sys.stdin)['data']['result'][0]['value'][1])"
```

### 8.5 Cleanup

```bash
docker compose down -v
cd / && rm -rf /tmp/prom-lab
```

### 8.6 Verify checklist

- [ ] Prometheus chạy và scrape app target (status UP)
- [ ] `rate(http_requests_total[5m])` trả kết quả > 0
- [ ] `histogram_quantile(0.99, ...)` trả p99 latency
- [ ] Recording rules `job:http_requests:rate5m` hoạt động
- [ ] Alert rule `HighErrorRate` defined (có thể chưa firing nếu error rate thấp)
- [ ] `prometheus_tsdb_head_series` hiển thị cardinality hiện tại
- [ ] Biết phân biệt instant vector vs range vector

---

## 9. Common Pitfalls & Debugging

### 9.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| **"no data" trên query** | Target chưa UP hoặc metric name sai | Check `/targets`, verify `/metrics` endpoint |
| **rate() returns empty** | Range window < 2× scrape_interval | Tăng window: `rate(x[5m])` thay vì `rate(x[30s])` |
| **Prometheus OOM** | Cardinality explosion | Check `prometheus_tsdb_head_series`, drop high-cardinality labels |
| **Stale data** | Target down nhưng series vẫn hiện | staleness markers tự xóa sau 5 phút |
| **Alert "pending" mãi** | `for` duration chưa đủ | Chờ hoặc giảm `for` duration |
| **histogram_quantile NaN** | Bucket `+Inf` = 0 (no requests) | Chỉ query khi có traffic |
| **Recording rule không hoạt** | Syntax error trong rules.yml | `promtool check rules rules.yml` |

### 9.2 Debug commands

```bash
# Validate config
promtool check config prometheus.yml

# Validate rules
promtool check rules rules.yml

# Test PromQL
promtool query instant http://localhost:9090 'up'

# Check targets via API
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health}'

# Check current cardinality
curl -s http://localhost:9090/api/v1/status/tsdb | jq '.data.seriesCountByMetricName | to_entries | sort_by(-.value) | .[:10]'

# Check memory usage
curl -s http://localhost:9090/api/v1/status/runtimeinfo | jq '.data | {goroutines, memoryInBytes: (.memStats.alloc / 1048576 | floor | tostring + " MB")}'
```

### 9.3 Production Case Study: Cardinality Explosion at PayPal

**Context**: Team tạo metric `api_requests_total{endpoint="/api/v1/users/{user_id}"}`. User_id trong endpoint path → mỗi user tạo 1 series.

**Symptom**: Prometheus RAM tăng từ 8GB → 45GB trong 2 ngày. Query timeout. Dashboards không load.

**Investigation**:
```promql
# Check top metrics by cardinality
topk(10, count by (__name__)({__name__=~".+"}))
# Result: api_requests_total = 5,000,000 series
```

**Root Cause**: URL template chứa user_id → 5M unique endpoints → 5M series.

**Fix**:
1. Normalize endpoint label: `/api/v1/users/{user_id}` → `/api/v1/users/:id`.
2. Drop original label via `metric_relabel_configs`.
3. Restart Prometheus → series count giảm từ 5M về 200.

**Prevention**: Code review cho metric labels. Add `--storage.tsdb.max-series-per-metric` limit.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 38)
- Day 38 giới thiệu tổng quan observability và three pillars.
- Day 39 deep dive vào pillar Metrics: Prometheus architecture, PromQL, best practices.

### Bài sau (Day 40)
- Day 40: Grafana Dashboard & Alerting — visualization metrics từ Prometheus, thiết kế dashboard và alert rules.
- Recording rules từ Day 39 sẽ được dùng trong Grafana dashboards.
- Alert rules từ Day 39 sẽ kết nối với AlertManager và notification channels.

### Kiến thức liên quan
- **Day 19**: HPA dùng Prometheus metrics (custom metrics adapter).
- **Day 36**: Argo Rollouts analysis dùng Prometheus queries (AnalysisTemplate).
- **Day 43**: SLI/SLO definitions dựa trên Prometheus metrics.

---

## 11. Tài liệu tham khảo

### Must-read
- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Cheat Sheet](https://promlabs.com/promql-cheat-sheet/)
- [Prometheus Best Practices - Naming](https://prometheus.io/docs/practices/naming/)
- [Prometheus Best Practices - Instrumentation](https://prometheus.io/docs/practices/instrumentation/)

### Nice-to-have
- [Robust Perception Blog](https://www.robustperception.io/blog/) — Brian Brazil (Prometheus co-founder)
- [PromQL for Humans](https://timber.io/blog/promql-for-humans/)
- [Thanos Documentation](https://thanos.io/tip/thanos/getting-started.md/)

### Deep-dive
- [Prometheus TSDB Design](https://fabxc.org/tsdb/)
- [Mimir Architecture](https://grafana.com/docs/mimir/latest/references/architecture/)
- [Cardinality is Key](https://www.robustperception.io/cardinality-is-key/)
- [Life of a PromQL Query](https://www.youtube.com/watch?v=SftUrOBHGzY)

