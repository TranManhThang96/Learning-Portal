# Day 39: Exercises — Prometheus & PromQL

## Bài 1: Setup Prometheus & Basic PromQL (Easy)

### Context
Team bạn quyết định chuyển từ Datadog (quá đắt, $15/host/month × 50 hosts = $9,000/month) sang Prometheus self-hosted. Bạn được giao thiết lập Prometheus đầu tiên và viết các queries cơ bản.

### Yêu cầu
1. Deploy Prometheus bằng Docker Compose.
2. Cấu hình scrape Prometheus self-metrics (`localhost:9090`).
3. Dùng một sample app expose custom metrics (hoặc dùng `prometheus-example-app`).
4. Viết PromQL queries sau trên Prometheus UI:
   - Total requests (counter value).
   - RPS (requests per second) dùng `rate()`.
   - Tổng requests trong 1 giờ dùng `increase()`.
   - Số targets đang UP.
   - Prometheus memory usage.
   - Tổng active time series (cardinality).
5. Screenshot hoặc ghi lại kết quả mỗi query.

### Expected Outcome
- Prometheus chạy và scrape thành công (Targets page: all UP).
- 6 PromQL queries trả kết quả đúng.
- Hiểu sự khác biệt giữa `rate()` và `increase()`.

### Hint
- `docker run -p 9090:9090 prom/prometheus` (quickest start).
- Sample app: `docker run -p 8080:8080 quay.io/brancz/prometheus-example-app:v0.5.0`.
- `rate()` trả per-second, `increase()` trả total trong window.
- Prometheus self-metrics: `prometheus_tsdb_head_series`, `process_resident_memory_bytes`.

### Acceptance Criteria
- [ ] Prometheus chạy và accessible tại `:9090`.
- [ ] Ít nhất 1 target ngoài self-scrape (app hoặc node-exporter).
- [ ] 6 PromQL queries viết đúng và trả kết quả.
- [ ] Phân biệt được `rate()` vs `increase()` vs `irate()`.
- [ ] Biết cách check cardinality bằng `prometheus_tsdb_head_series`.

### Bonus Challenge
- Thêm node-exporter container và scrape system metrics.
- Viết query dự đoán disk full bằng `predict_linear()`.
- So sánh `rate()` vs `irate()` trên cùng metric — khi nào dùng cái nào?

---

## Bài 2: Recording Rules, Alert Rules & Histogram (Medium)

### Context
Prometheus đã chạy 1 tuần. Team phàn nàn: "Grafana dashboards load chậm" (queries phức tạp tính mỗi lần), và "Không có alert khi error rate tăng — phải manually refresh dashboard". Bạn cần:
1. Tạo recording rules để pre-compute dashboard queries.
2. Tạo alert rules cho critical metrics.
3. Viết PromQL cho latency percentiles (histogram).

### Yêu cầu

**Part A: Recording Rules**
1. Tạo recording rules file (`rules.yml`) với:
   - `service:http_requests:rate5m` — RPS per service.
   - `service:http_errors:ratio5m` — Error rate per service.
   - `service:http_latency:p99_5m` — p99 latency per service.
   - `service:http_latency:p50_5m` — p50 latency per service.
2. Load rules vào Prometheus config.
3. Verify recording rules hoạt động bằng query trên Prometheus UI.

**Part B: Alert Rules**
4. Tạo alert rules cho:
   - `HighErrorRate`: error rate > 5% sustained 2 phút → severity: warning.
   - `HighLatency`: p99 > 1 second sustained 5 phút → severity: warning.
   - `ServiceDown`: target down > 1 phút → severity: critical.
   - `DiskWillFull`: predicted disk full trong 24h → severity: warning.
5. Verify alerts trên `/alerts` page.

**Part C: Histogram Queries**
6. Viết PromQL cho:
   - p50, p90, p99 latency.
   - Average latency (dùng `_sum` / `_count`).
   - Apdex score (satisfied ≤ 300ms, tolerating ≤ 1.2s).

### Expected Outcome
- Recording rules tạo time series mới (queryable trên Prometheus).
- Alert rules hiển thị trên `/alerts` page (ít nhất inactive state).
- Histogram queries trả percentile values đúng.

### Hint
- Recording rule naming: `level:metric:operations` — ví dụ `service:http_requests:rate5m`.
- Validate rules: `promtool check rules rules.yml`.
- Alert `for: 2m` = phải true liên tục 2 phút trước khi firing.
- Histogram bucket label là `le` (less or equal) → phải include `by (le)` trong aggregation.
- Apdex: `(satisfied + tolerating/2) / total`.

### Acceptance Criteria
- [ ] Recording rules file validate pass (`promtool check rules`).
- [ ] 4 recording rules trả kết quả khi query.
- [ ] 4 alert rules hiển thị trên `/alerts` page.
- [ ] Histogram percentile queries trả giá trị hợp lý (p50 < p90 < p99).
- [ ] Average latency = `_sum / _count` trả kết quả.
- [ ] Rule naming convention đúng: `level:metric:operations`.

### Bonus Challenge
- Cài AlertManager và cấu hình notification (console/webhook/Slack).
- Trigger alert bằng cách tạo high error rate (curl nhiều bad endpoint).
- Tạo recording rule cho SLO availability (1 - error_rate) và SLO burn rate.
- Compare dashboard load time trước và sau recording rules.

---

## Bài 3: Multi-Service Monitoring & Cardinality Management (Hard)

### Context
Bạn là SRE Lead quản lý Prometheus cho platform 20 microservices (3M active time series). Tuần trước:
1. Prometheus OOM restart 2 lần (RAM 32GB không đủ).
2. Dashboard "Service Overview" load mất 15 giây.
3. Dev team deploy service mới thêm label `user_id` vào metrics → cardinality tăng 500%.

Bạn cần: fix cardinality issue, optimize queries, và thiết lập guardrails.

### Yêu cầu

**Part A: Cardinality Audit**
1. Deploy Prometheus + 3 sample services (simulate multi-service environment).
2. Viết PromQL queries để:
   - Tổng active time series.
   - Top 10 metrics by series count.
   - Series count per job/service.
   - Identify high-cardinality labels.
3. Simulate cardinality explosion: thêm label `request_id` vào metric → observe series count tăng.

**Part B: Cardinality Control**
4. Viết `metric_relabel_configs` để:
   - Drop high-cardinality label `request_id`.
   - Drop metrics không cần thiết (`go_*` nếu không monitor Go runtime).
   - Rename label cho consistency.
5. Verify series count giảm sau relabeling.

**Part C: Query Optimization**
6. Tạo recording rules cho top 5 expensive queries.
7. So sánh query execution time trước và sau recording rules.
8. Viết runbook: "How to debug Prometheus high memory usage".

**Part D: Scaling Plan**
9. Viết document so sánh scaling options cho khi vượt 10M series:
   - Vertical scaling (bigger Prometheus).
   - Federation.
   - Thanos.
   - Mimir.
10. Recommendation cho team setup hiện tại.

### Expected Outcome
- Cardinality audit report: top metrics, high-cardinality labels identified.
- Relabel config giảm series count measurably.
- Recording rules cải thiện query performance.
- Scaling plan với recommendation rõ ràng.

### Hint
- Cardinality queries:
  ```promql
  prometheus_tsdb_head_series
  topk(10, count by (__name__)({__name__=~".+"}))
  count(some_metric) by (label_name)
  ```
- `metric_relabel_configs` in scrape config:
  ```yaml
  metric_relabel_configs:
    - source_labels: [__name__]
      regex: 'go_.*'
      action: drop
    - source_labels: [request_id]
      action: labeldrop
  ```
- Prometheus API: `/api/v1/status/tsdb` shows cardinality breakdown.
- Recording rule query time: compare `(time() - $start)` trước/sau.

### Acceptance Criteria
- [ ] 3 services deployed và scraped bởi Prometheus.
- [ ] Cardinality audit: top metrics and labels identified.
- [ ] High-cardinality label simulated → series count spike visible.
- [ ] `metric_relabel_configs` applied → series count reduced.
- [ ] Recording rules created → query time improved.
- [ ] Runbook: Prometheus high memory → ≥ 5 debug steps.
- [ ] Scaling plan: ≥ 3 options compared with pros/cons.
- [ ] Recommendation cho specific team scenario.

### Bonus Challenge
- Deploy Thanos sidecar + Thanos Query → query across 2 Prometheus instances.
- Implement `--storage.tsdb.max-block-duration` và `--storage.tsdb.min-block-duration` tuning.
- Tạo Grafana dashboard monitoring Prometheus itself: memory, CPU, scrape duration, series count.
- Write admission webhook hoặc Kyverno policy: reject Prometheus ServiceMonitor nếu estimated cardinality > threshold.

---

## Solutions

<details>
<summary>Solution Bài 1: Basic Setup</summary>

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    image: quay.io/brancz/prometheus-example-app:v0.5.0
    ports: ["8080:8080"]

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  - job_name: 'app'
    static_configs:
      - targets: ['app:8080']
```

```bash
docker compose up -d

# Generate traffic
for i in $(seq 1 100); do curl -s localhost:8080/ > /dev/null; sleep 0.1; done &

# Queries on http://localhost:9090:
# 1. Total requests:    http_requests_total
# 2. RPS:               rate(http_requests_total[5m])
# 3. Requests in 1h:    increase(http_requests_total[1h])
# 4. Targets UP:        up
# 5. Prometheus memory: process_resident_memory_bytes / 1024 / 1024
# 6. Active series:     prometheus_tsdb_head_series

docker compose down -v
```

</details>

<details>
<summary>Solution Bài 2: Rules & Histogram</summary>

```yaml
# rules.yml
groups:
  - name: recording_rules
    interval: 30s
    rules:
      - record: service:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job)

      - record: service:http_errors:ratio5m
        expr: |
          sum(rate(http_requests_total{code=~"5.."}[5m])) by (job)
          /
          sum(rate(http_requests_total[5m])) by (job)

      - record: service:http_latency:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (job, le)
          )

      - record: service:http_latency:p50_5m
        expr: |
          histogram_quantile(0.50,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (job, le)
          )

  - name: alert_rules
    rules:
      - alert: HighErrorRate
        expr: service:http_errors:ratio5m > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Error rate {{ $value | humanizePercentage }} on {{ $labels.job }}"

      - alert: HighLatency
        expr: service:http_latency:p99_5m > 1
        for: 5m
        labels:
          severity: warning

      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical

      - alert: DiskWillFull
        expr: predict_linear(node_filesystem_avail_bytes[6h], 24*3600) < 0
        for: 10m
        labels:
          severity: warning
```

```bash
# Validate
promtool check rules rules.yml

# Histogram queries:
# p50:  histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))
# p90:  histogram_quantile(0.90, rate(http_request_duration_seconds_bucket[5m]))
# p99:  histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
# Avg:  rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
# Apdex: (sum(rate(x_bucket{le="0.3"}[5m])) + sum(rate(x_bucket{le="1.2"}[5m]))) / 2 / sum(rate(x_count[5m]))
```

</details>

<details>
<summary>Solution Bài 3: Cardinality Management (Key Parts)</summary>

```yaml
# metric_relabel_configs to control cardinality
scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['app:8080']
    metric_relabel_configs:
      # Drop go runtime metrics
      - source_labels: [__name__]
        regex: 'go_.*'
        action: drop
      # Drop high-cardinality labels
      - regex: 'request_id'
        action: labeldrop
      # Drop promhttp internal metrics
      - source_labels: [__name__]
        regex: 'promhttp_.*'
        action: drop
```

```bash
# Cardinality audit queries
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' | jq '.data.result[0].value[1]'

curl -s 'http://localhost:9090/api/v1/status/tsdb' | jq '.data.seriesCountByMetricName | to_entries | sort_by(-.value) | .[:10]'

# Cardinality per label
curl -s 'http://localhost:9090/api/v1/query?query=count(http_requests_total)+by+(path)' | jq '.data.result | length'
```

### Scaling Plan Summary

| Option | When | Pros | Cons |
|--------|------|------|------|
| Vertical | < 5M series | Simple | Single point of failure |
| Federation | 5-20M, multi-team | Team isolation | Query complexity |
| Thanos | 10M+, multi-cluster | Global view, long-term | Complex (6+ components) |
| Mimir | 10M+, Grafana ecosystem | Simpler than Thanos | Newer, smaller community |

**Recommendation for 20 services, 3M series**: Vertical scaling (64GB RAM) + recording rules + cardinality controls. Move to Thanos/Mimir when hitting 10M series.

</details>

