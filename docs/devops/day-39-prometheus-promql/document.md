# Day 39: PromQL Cheat Sheet & Reference

## 1. Metric Types Quick Reference

| Type | Ví dụ | Functions | Không dùng |
|------|-------|-----------|-----------|
| **Counter** | `http_requests_total` | `rate()`, `increase()`, `irate()` | Trực tiếp (giá trị tuyệt đối vô nghĩa) |
| **Gauge** | `temperature_celsius` | Trực tiếp, `avg_over_time()`, `max_over_time()` | `rate()` |
| **Histogram** | `http_request_duration_seconds` | `histogram_quantile()`, `rate()` trên `_bucket` | Trực tiếp trên `_bucket` |
| **Summary** | `rpc_duration_seconds` | Trực tiếp `{quantile="0.99"}` | `histogram_quantile()` |

---

## 2. PromQL Functions Thường Dùng

### Counter Functions

```promql
# Tốc độ tăng per second (smoothed, cho dashboards)
rate(http_requests_total[5m])

# Tốc độ tăng instant (2 points gần nhất, cho alerts)
irate(http_requests_total[5m])

# Tổng tăng trong window
increase(http_requests_total[1h])

# Resets counter (debug)
resets(http_requests_total[1h])
```

### Gauge Functions

```promql
# Giá trị hiện tại
node_memory_MemAvailable_bytes

# Trung bình trong window
avg_over_time(node_cpu_seconds_total[1h])

# Min/Max trong window
min_over_time(node_memory_MemAvailable_bytes[1h])
max_over_time(node_memory_MemAvailable_bytes[1h])

# Dự đoán tuyến tính
predict_linear(node_filesystem_avail_bytes[6h], 24*3600)

# Thay đổi trong window
delta(temperature_celsius[1h])
# Hoặc cho counter-like gauges:
deriv(temperature_celsius[1h])
```

### Histogram Functions

```promql
# Percentile (p50, p90, p95, p99)
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.90, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Percentile per service
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
)

# Average duration (từ _sum và _count)
rate(http_request_duration_seconds_sum[5m])
/
rate(http_request_duration_seconds_count[5m])
```

---

## 3. Production PromQL Queries

### RPS (Requests Per Second)

```promql
# Total RPS
sum(rate(http_requests_total[5m]))

# RPS per service
sum(rate(http_requests_total[5m])) by (service)

# RPS per endpoint
sum(rate(http_requests_total[5m])) by (method, path)

# Top 5 endpoints by RPS
topk(5, sum(rate(http_requests_total[5m])) by (path))
```

### Error Rate

```promql
# Error rate (ratio 0-1)
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# Error rate per service (%)
100 * (
  sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
  /
  sum(rate(http_requests_total[5m])) by (service)
)

# Error rate excluding 404 (4xx nhưng không phải client error thật sự)
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total{status!~"4.."}[5m]))
```

### Latency

```promql
# p99 latency (seconds)
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# p99 per service
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
)

# Average latency
sum(rate(http_request_duration_seconds_sum[5m])) by (service)
/
sum(rate(http_request_duration_seconds_count[5m])) by (service)

# Apdex score (satisfied < 0.3s, tolerating < 1.2s)
(
  sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m]))
  +
  sum(rate(http_request_duration_seconds_bucket{le="1.2"}[5m]))
)
/ 2
/ sum(rate(http_request_duration_seconds_count[5m]))
```

### Saturation

```promql
# CPU usage (%)
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage (%)
100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)

# Disk usage (%)
100 * (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes)

# Container CPU usage
sum(rate(container_cpu_usage_seconds_total[5m])) by (pod)

# Container memory usage
sum(container_memory_working_set_bytes) by (pod)
```

---

## 4. Alert Rules Templates

### Service Health Alerts

```yaml
groups:
  - name: service_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)
          > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: "Error rate is {{ $value | humanizePercentage }}"
          runbook: "https://wiki.example.com/runbooks/high-error-rate"

      # High latency
      - alert: HighLatency
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
          ) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High p99 latency on {{ $labels.service }}"
          description: "p99 latency is {{ $value | humanize }}s"

      # Service down
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} is down"

      # No traffic (possible issue)
      - alert: NoTraffic
        expr: |
          sum(rate(http_requests_total[5m])) by (service) == 0
          and
          sum(rate(http_requests_total[1h])) by (service) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "No traffic on {{ $labels.service }} (was receiving traffic before)"
```

### Infrastructure Alerts

```yaml
groups:
  - name: infra_alerts
    rules:
      # Disk almost full
      - alert: DiskWillFull
        expr: |
          predict_linear(node_filesystem_avail_bytes[6h], 24*3600) < 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Disk will be full in 24h on {{ $labels.instance }}"

      # High memory usage
      - alert: HighMemoryUsage
        expr: |
          (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.9
        for: 5m
        labels:
          severity: warning

      # Prometheus cardinality high
      - alert: HighCardinality
        expr: prometheus_tsdb_head_series > 1000000
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Prometheus has {{ $value }} active series"
```

---

## 5. Recording Rules Templates

```yaml
groups:
  - name: service_recording_rules
    interval: 30s
    rules:
      # RPS
      - record: service:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (service)

      # Error ratio
      - record: service:http_errors:ratio5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)

      # Latency percentiles
      - record: service:http_latency:p50_5m
        expr: |
          histogram_quantile(0.50,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
          )

      - record: service:http_latency:p90_5m
        expr: |
          histogram_quantile(0.90,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
          )

      - record: service:http_latency:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
          )

      # Availability (1 - error_rate)
      - record: service:http_availability:ratio5m
        expr: |
          1 - (
            sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
            /
            sum(rate(http_requests_total[5m])) by (service)
          )
```

---

## 6. Useful Prometheus API Endpoints

```bash
# Query instant
curl 'http://localhost:9090/api/v1/query?query=up'

# Query range
curl 'http://localhost:9090/api/v1/query_range?query=rate(http_requests_total[5m])&start=2024-01-15T00:00:00Z&end=2024-01-15T01:00:00Z&step=60s'

# List all metric names
curl 'http://localhost:9090/api/v1/label/__name__/values'

# List targets
curl 'http://localhost:9090/api/v1/targets'

# TSDB status (cardinality)
curl 'http://localhost:9090/api/v1/status/tsdb'

# Runtime info
curl 'http://localhost:9090/api/v1/status/runtimeinfo'

# Config
curl 'http://localhost:9090/api/v1/status/config'

# Rules
curl 'http://localhost:9090/api/v1/rules'

# Alerts
curl 'http://localhost:9090/api/v1/alerts'

# Reload config (need --web.enable-lifecycle)
curl -X POST http://localhost:9090/-/reload
```

---

## 7. Cardinality Debugging

```promql
# Tổng active series
prometheus_tsdb_head_series

# Top metrics by series count
topk(10, count by (__name__)({__name__=~".+"}))

# Series count per job
count({job=~".+"}) by (job)

# Estimate cardinality of a specific metric
count(http_requests_total)

# Find high-cardinality labels
count(http_requests_total) by (path)
# Nếu kết quả > 100 → path label có cardinality cao
```

---

## 8. Common PromQL Mistakes

| Mistake | Đúng | Sai |
|---------|------|-----|
| rate() trên gauge | `node_memory_MemAvailable_bytes` | `rate(node_memory_MemAvailable_bytes[5m])` |
| Thiếu rate() cho counter trong histogram_quantile | `histogram_quantile(0.99, rate(x_bucket[5m]))` | `histogram_quantile(0.99, x_bucket)` |
| Window quá nhỏ | `rate(x[5m])` (≥ 4× scrape_interval) | `rate(x[15s])` |
| Thiếu `by (le)` trong histogram_quantile | `sum(...) by (le)` | `sum(...) by (service)` — thiếu `le` |
| So sánh string dùng `=` | `{status=~"5.."}` | `{status="5xx"}` |
| increase() cho instant value | `rate(x[5m])` cho per-second | `increase(x[5m])` cho dashboard per-second |

