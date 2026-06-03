# Day 16: Deep Dive — Observability for Nginx & Kong

---

## 1. PromQL Recipes

### 1.1 Rate & Throughput

```promql
-- Tổng RPS toàn cluster
sum(rate(kong_http_requests_total[5m]))

-- RPS theo service
sum by (service) (rate(kong_http_requests_total[5m]))

-- RPS theo service + route
sum by (service, route) (rate(kong_http_requests_total[5m]))

-- Nginx requests per second (nginx-prometheus-exporter)
rate(nginx_http_requests_total[5m])
```

### 1.2 Error Rate

```promql
-- Error rate % (tất cả 5xx)
sum(rate(kong_http_requests_total{status=~"5.."}[5m]))
  / sum(rate(kong_http_requests_total[5m]))
  * 100

-- Error rate % theo service
sum by (service) (rate(kong_http_requests_total{service=~".+",status=~"5.."}[5m]))
  / sum by (service) (rate(kong_http_requests_total{service=~".+"}[5m]))
  * 100

-- 4xx rate (client error)
sum by (service) (rate(kong_http_requests_total{service="payment",status=~"4.."}[5m]))
  / sum by (service) (rate(kong_http_requests_total{service="payment"}[5m]))
  * 100

-- Error count per minute
increase(kong_http_requests_total{status=~"5.."}[1m])
```

### 1.3 Latency — Histogram Quantile

```promql
-- p95 total gateway latency (single instance) — DÙNG CÁCH NÀY
histogram_quantile(0.95,
  rate(kong_latency_bucket{service="payment"}[5m]))

-- p95 total gateway latency (multi-instance) — CÁCH ĐÚNG
histogram_quantile(0.95,
  sum by (le) (rate(kong_latency_bucket{service="payment"}[5m])))

-- p99 total gateway latency
histogram_quantile(0.99,
  sum by (le) (rate(kong_latency_bucket{service="payment"}[5m])))

-- p50 (median)
histogram_quantile(0.50,
  sum by (le) (rate(kong_latency_bucket{service="payment"}[5m])))

-- Kong overhead (không phải upstream latency)
histogram_quantile(0.95,
  sum by (le) (rate(kong_kong_latency_bucket{service="payment"}[5m])))

-- Upstream latency (network + upstream processing)
histogram_quantile(0.95,
  sum by (le) (rate(kong_upstream_latency_bucket{service="payment"}[5m])))

-- Compare: Kong overhead vs Upstream overhead
# Kong overhead ratio = kong_kong_latency / kong_latency
```

### 1.4 Latency — Aggregated with Service/Route Labels

```promql
-- p95 latency per service (multi-instance safe)
sum by (service) (
  histogram_quantile(0.95,
    sum by (le, service) (rate(kong_latency_bucket[5m])))
)

-- Top 5 slowest services by p95
topk(5,
  sum by (service) (
    histogram_quantile(0.95,
      sum by (le, service) (rate(kong_latency_bucket[5m])))
  )
)

-- Latency by route (high cardinality warning: nếu route label chứa dynamic path param → cardinality explosion)
sum by (route) (
  histogram_quantile(0.95,
    sum by (le, route) (rate(kong_latency_bucket{route!=""}[5m])))
)
```

### 1.5 Saturation — Nginx

```promql
-- Active connections (Nginx)
nginx_connections_active

-- Accepts vs handled (if handled < accepts → backlog drops)
rate(nginx_connections_accepted[5m])
  - rate(nginx_connections_handled[5m])
-- Giá trị > 0 → kernel đang drop connection

-- Waiting (keepalive idle) connections
nginx_connections_waiting

-- Connection utilization (active / max)
nginx_connections_active / 4096

-- HTTP requests rate
rate(nginx_http_requests_total[5m])
```

### 1.6 Upstream Health

```promql
-- Target health: 1=healthy, 0=unhealthy
kong_upstream_target_health{upstream="payment-upstream"}

-- Số target healthy per upstream
sum by (upstream) (kong_upstream_target_health == 1)

-- Số target unhealthy per upstream
sum by (upstream) (kong_upstream_target_health == 0)

-- Alert: any target unhealthy
count(kong_upstream_target_health == 0) > 0
```

### 1.7 Bandwidth

```promql
-- Total bandwidth (bytes/s) per service
sum by (service) (rate(kong_bandwidth_bytes_total[5m]))

-- Egress bandwidth
sum by (service) (
  rate(kong_bandwidth_bytes_total{service="payment",direction="egress"}[5m])
)

-- Ingress bandwidth
sum by (service) (
  rate(kong_bandwidth_bytes_total{service="payment",direction="ingress"}[5m])
)
```

### 1.8 Recording Rules (Performance)

```promql
-- Recording rule: service RPS (fast dashboard queries)
- record: service:request_rate:rate5m
  expr: sum by (service) (rate(kong_http_requests_total[5m]))

-- Recording rule: error rate %
- record: service:error_rate:ratio5m
  expr: |
    sum by (service) (rate(kong_http_requests_total{status=~"5.."}[5m]))
    / sum by (service) (rate(kong_http_requests_total[5m]))

-- Recording rule: request rate for p95 (NOTE: NOT quantile itself)
- record: service:latency_p95:rate5m
  expr: |
    sum by (le, service) (rate(kong_latency_bucket[5m]))
  # ⚠️ DO NOT record histogram_quantile() result
  # p99 không aggregate tốt, chỉ record rate() hoặc sum()
```

---

## 2. Log JSON Schema

### 2.1 Nginx Access Log JSON Schema

```nginx
log_format json_log escape=json
  '{'
    '"time":"$time_iso8601",'
    '"remote_addr":"$remote_addr",'
    '"request_id":"$request_id",'
    '"host":"$host",'
    '"method":"$request_method",'
    '"uri":"$request_uri",'
    '"server_protocol":"$server_protocol",'
    '"status":$status,'
    '"body_bytes_sent":$body_bytes_sent,'
    '"request_time":$request_time,'
    '"upstream_response_time":$upstream_response_time,'
    '"upstream_addr":"$upstream_addr",'
    '"upstream_status":$upstream_status,'
    '"http_referer":"$http_referer",'
    '"http_user_agent":"$http_user_agent",'
    '"http_x_forwarded_for":"$http_x_forwarded_for",'
    '"real_ip":"$realip_remote_addr"'
  '}';

access_log /var/log/nginx/access.json json_log buffer=64k flush=5s;
```

**Log line example**:
```json
{
  "time": "2026-05-18T10:23:45+00:00",
  "remote_addr": "203.0.113.42",
  "request_id": "a1b2c3d4",
  "host": "api.example.com",
  "method": "GET",
  "uri": "/orders/12345",
  "server_protocol": "HTTP/1.1",
  "status": 200,
  "body_bytes_sent": 512,
  "request_time": 0.045,
  "upstream_response_time": 0.038,
  "upstream_addr": "10.0.1.5:8080",
  "upstream_status": 200,
  "http_referer": "",
  "http_user_agent": "Mozilla/5.0",
  "http_x_forwarded_for": "",
  "real_ip": "203.0.113.42"
}
```

### 2.2 Kong File-Log JSON Schema

```yaml
# kong.yml — DB-less declarative config
_format_version: "3.0"

services:
  - name: payment-service
    url: http://payment-upstream/pay
    routes:
      - name: payment-route
        paths:
          - /api/v1/pay
    plugins:
      - name: file-log
        config:
          path: /var/log/kong/payment-access.log
          custom_fields_by_lua:
            request_id: "return kong.request.get_id()"
            service_name: "return kong.service.name"
            route_name: "return kong.route.name"
            consumer_name: "return kong.client.authenticated_consumer.credential.username or ''"
          # Sử dụng JSON format bằng template
          # Hoặc dùng http-log với Loki/Grafana
```

**Lua template cho JSON log** (dùng `pre-function` plugin):
```lua
-- Custom JSON log (via pre-function plugin)
local json = require("cjson")
local log = {
    timestamp = os.date("!%Y-%m-%dT%H:%M:%SZ"),
    request_id = kong.request.get_id(),
    method = kong.request.get_method(),
    uri = kong.request.get_path(),
    service = kong.service.name,
    route = kong.route.name,
    status = kong.response.get_status(),
    latency_ms = (kong.response.get_latency() or 0) / 1000,
    request_size = kong.request.get_size(),
    response_size = kong.response.get_size(),
}
ngx.log(ngx.INFO, json.encode(log))
```

### 2.3 Kong http-log (Loki/Grafana JSON)

```yaml
# kong.yml
plugins:
  - name: http-log
    config:
      http_endpoint: http://promtail:9080/loki/api/v1/push
      method: POST
      content_type: application/json
      headers:
        X-Loki-Host: loki
      timeout: 5000
      retry_count: 3
      queue_size: 1000
```

### 2.4 Promtail Scrape Config

```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

clients:
  - url: http://loki:3100/loki/api/v1/push

positions:
  filename: /var/positions.yaml

scrape_configs:
  - job_name: nginx-access
    static_configs:
      - targets:
          - localhost
        labels:
          job: nginx
          env: lab
        __path__: /var/log/nginx/access.json

  - job_name: kong-access
    static_configs:
      - targets:
          - localhost
        labels:
          job: kong
          env: lab
        __path__: /var/log/kong/payment-access.log

  - job_name: nginx-error
    static_configs:
      - targets:
          - localhost
        labels:
          job: nginx
          log_type: error
        __path__: /var/log/nginx/error.log
```

### 2.5 Loki LogQL Examples

```logql
-- Query all nginx errors
{job="nginx"} |= "error"

-- Query by status code
{job="nginx"} | json | status >= 500

-- Query by service + latency
{job="kong"} | json | service="payment" | latency_ms > 500

-- Query by trace/request ID
{job="kong"} | json | request_id="a1b2c3d4"

-- Count errors per minute
sum by (service) (
  count_over_time(
    {job="kong"} | json | status >= 500 [1m]
  )
)

-- Latency histogram from logs (khi không có Prometheus histogram)
quantile_over_time(0.95,
  {job="nginx"} | json | unwrap latency_ms [5m]) by (service)
```

---

## 3. Prometheus Alert Rules — Sample YAML

```yaml
# prometheus-alerts.yml
groups:
  - name: gateway-alerts
    interval: 30s
    rules:

      # ── RED: Error Rate ──────────────────────────────
      - alert: GatewayHighErrorRate5xx
        expr: |
          (
            sum(rate(kong_http_requests_total{status=~"5.."}[5m]))
            / sum(rate(kong_http_requests_total[5m]))
          ) > 0.01
        for: 2m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Gateway 5xx error rate > 1% for 2 minutes"
          description: "Current error rate: {{ $value | humanizePercentage }}"
          runbook: "https://wiki.example.com/runbooks/gateway-high-errors"

      - alert: GatewayHighClientErrorRate4xx
        expr: |
          (
            sum(rate(kong_http_requests_total{status=~"4.."}[5m]))
            / sum(rate(kong_http_requests_total[5m]))
          ) > 0.05
        for: 5m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Gateway 4xx error rate > 5%"
          description: "High 4xx rate may indicate auth issues or client bugs"

      # ── RED: Latency ────────────────────────────────
      - alert: GatewayHighLatencyP95
        expr: |
          histogram_quantile(0.95,
            sum by (le) (rate(kong_latency_bucket[5m]))) > 0.5
        for: 5m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Gateway p95 latency > 500ms"
          description: "p95 latency = {{ $value | humanizeDuration }}"

      - alert: ServiceHighLatencyP95
        expr: |
          histogram_quantile(0.95,
            sum by (le, service) (rate(kong_latency_bucket[5m]))) > 1
        for: 5m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Service {{ $labels.service }} p95 latency > 1s"
          description: "p95 = {{ $value | humanizeDuration }}"

      - alert: UpstreamHighLatency
        expr: |
          histogram_quantile(0.95,
            sum by (le) (rate(kong_upstream_latency_bucket[5m]))) > 0.8
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "Upstream latency p95 > 800ms"
          description: "Bottleneck likely in upstream service, not Kong"

      # ── USE: Saturation ─────────────────────────────
      - alert: NginxHighConnectionUtilization
        expr: |
          nginx_connections_active / on(instance) nginx_connections_max{job="nginx"}
          > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Nginx connection utilization > 80%"
          description: "Active connections: {{ $value | humanize }}"

      - alert: NginxConnectionBacklogDrop
        expr: |
          rate(nginx_connections_accepted[5m])
          - rate(nginx_connections_handled[5m]) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Nginx connection backlog drops detected"
          description: "Kernel is dropping connections. Check somaxconn and worker_connections"

      - alert: KongUpstreamTargetUnhealthy
        expr: |
          count(kong_upstream_target_health == 0) by (upstream) > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Unhealthy upstream target: {{ $labels.upstream }}"
          description: "{{ $value }} target(s) unhealthy in upstream {{ $labels.upstream }}"

      - alert: KongUpstreamAllTargetsDown
        expr: |
          sum by (upstream) (kong_upstream_target_health == 1) == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "All targets DOWN in upstream {{ $labels.upstream }}"
          description: "No healthy target available. All requests will return 503."

      # ── Prometheus Health ──────────────────────────
      - alert: PrometheusScrapeFailure
        expr: |
          up{job=~"nginx|kong"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Prometheus cannot scrape {{ $labels.job }}"
          description: "Target {{ $labels.job }} on {{ $labels.instance }} is DOWN"

      - alert: PrometheusMetricsMissing
        expr: |
          absent(kong_http_requests_total{service="payment"}[10m])
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "No Kong metrics received for 10 minutes"
          description: "payment service metrics missing. Check Kong Prometheus plugin."

      # ── Capacity ──────────────────────────────────
      - alert: NginxMemoryHigh
        expr: |
          (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Nginx host memory > 85%"
```

---

## 4. Grafana Dashboard JSON Skeleton

### 4.1 Overview Dashboard JSON

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "title": "Total Request Rate (RPS)",
      "type": "timeseries",
      "gridPos": {"h": 6, "w": 8, "x": 0, "y": 0},
      "targets": [
        {
          "expr": "sum(rate(kong_http_requests_total[5m]))",
          "legendFormat": "RPS",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 5000},
              {"color": "red", "value": 10000}
            ]
          }
        }
      }
    },
    {
      "title": "Error Rate % (5xx)",
      "type": "timeseries",
      "gridPos": {"h": 6, "w": 8, "x": 8, "y": 0},
      "targets": [
        {
          "expr": "sum(rate(kong_http_requests_total{status=~\"5..\"}[5m])) / sum(rate(kong_http_requests_total[5m])) * 100",
          "legendFormat": "Error Rate %",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 0.5},
              {"color": "red", "value": 1}
            ]
          }
        }
      }
    },
    {
      "title": "p95 Latency",
      "type": "timeseries",
      "gridPos": {"h": 6, "w": 8, "x": 16, "y": 0},
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(kong_latency_bucket[5m])))",
          "legendFormat": "p95 Gateway",
          "refId": "A"
        },
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(kong_upstream_latency_bucket[5m])))",
          "legendFormat": "p95 Upstream",
          "refId": "B"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 0.3},
              {"color": "red", "value": 0.5}
            ]
          }
        }
      }
    },
    {
      "title": "Nginx Active Connections",
      "type": "timeseries",
      "gridPos": {"h": 6, "w": 8, "x": 0, "y": 6},
      "targets": [
        {
          "expr": "nginx_connections_active",
          "legendFormat": "Active",
          "refId": "A"
        },
        {
          "expr": "nginx_connections_waiting",
          "legendFormat": "Waiting (keepalive)",
          "refId": "B"
        },
        {
          "expr": "nginx_connections_reading",
          "legendFormat": "Reading",
          "refId": "C"
        },
        {
          "expr": "nginx_connections_writing",
          "legendFormat": "Writing",
          "refId": "D"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short"
        }
      }
    },
    {
      "title": "RPS by Service",
      "type": "bargauge",
      "gridPos": {"h": 6, "w": 8, "x": 8, "y": 6},
      "targets": [
        {
          "expr": "sum by (service) (rate(kong_http_requests_total[5m]))",
          "legendFormat": "{{service}}",
          "refId": "A"
        }
      ],
      "options": {
        "displayMode": "gradient",
        "orientation": "horizontal"
      }
    },
    {
      "title": "Upstream Target Health",
      "type": "stat",
      "gridPos": {"h": 6, "w": 8, "x": 16, "y": 6},
      "targets": [
        {
          "expr": "kong_upstream_target_health",
          "legendFormat": "{{upstream}} / {{target}}",
          "refId": "A"
        }
      ],
      "options": {
        "colorMode": "value"
      },
      "fieldConfig": {
        "defaults": {
          "mappings": [
            {"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}}},
            {"type": "value", "options": {"1": {"text": "UP", "color": "green"}}}
          ]
        }
      }
    }
  ],
  "refresh": "30s",
  "schemaVersion": 38,
  "tags": ["kong", "nginx", "observability"],
  "templating": {"list": []},
  "time": {"from": "now-1h", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "Gateway Observability — Overview",
  "uid": "gateway-overview",
  "version": 1
}
```

### 4.2 Import Official Kong Dashboard

```bash
# Grafana Dashboard ID 7424 (official Kong dashboard)
# Import bằng Grafana API hoặc UI

# Option 1: Import qua Grafana UI
# 1. Go to Grafana → Dashboards → Import
# 2. Dashboard ID: 7424
# 3. Select Prometheus datasource
# 4. Customize: namespace, service filter

# Option 2: Import via curl
curl -X POST \
  http://admin:admin@localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @kong-dashboard-7424.json
```

---

## 5. Kong Prometheus Plugin — Scope & Configuration

### 5.1 Global Scope

```yaml
# kong.yml — GLOBAL scope (affects all routes)
plugins:
  - name: prometheus
    config:
      # Per configuration
      status_code_metrics: true   # Expose status code breakdown
      latency_metrics: true        # Expose latency histograms
      bandwidth_metrics: true      # Expose ingress/egress bytes
      upstream_health_metrics: true # Expose kong_upstream_target_health

# ⚠️ CAUTION: If a service-level prometheus plugin also exists:
# kong_http_requests_total will be DOUBLE COUNTED
# Solution: Either global OR service/route, never both
```

### 5.2 Service Scope

```yaml
# kong.yml — SERVICE scope (recommended for multi-service)
services:
  - name: payment-service
    url: http://payment-upstream/pay
    routes:
      - name: payment-route
        paths:
          - /api/v1/pay
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true
          upstream_health_metrics: true

  - name: order-service
    url: http://order-upstream/orders
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
```

### 5.3 Plugin Scope Conflict — Detection

```bash
# Check all prometheus plugins
curl -s http://localhost:8001/plugins?name=prometheus \
  | jq '.data[] | {name, scope: .route.name // .service.name // "global", enabled: .enabled}'

# Expected: chỉ 1 plugin prometheus (hoặc global, hoặc per-service)
# Nếu thấy nhiều hơn → double counting

# Verify double counting: generate 100 requests
# Expected count (correct): 100
# If double counting: 200
```

### 5.4 Kong Prometheus — DB-less vs DB-mode

```yaml
# DB-less: plugin configured in kong.yml (declarative)
# Plugin config is part of the declarative config
# decK sync propagates plugin config to all Kong nodes

# DB-mode: plugin via Admin API or Kong Manager
# All Kong nodes share plugin config from Postgres
# Prometheus metrics exposed identically

# Kong Hybrid mode:
# Both CP and DP nodes expose metrics on port 8100
# Prometheus should scrape EACH DP node individually
# Metrics are per-node (lua_shared_dict)
```

---

## 6. OpenTelemetry Tracing — Overview

### 6.1 Architecture

```
Client Request
    │
    ▼
┌─────────────────┐
│ Kong Zipkin     │ ← Accepts: X-B3-TraceId, X-B3-SpanId
│ plugin          │ ← Generates: traceparent (W3C)
└────────┬────────┘
         │ OTLP / Zipkin exporter
         ▼
┌─────────────────┐
│ OTEL Collector  │ ← Receives spans, batch, export
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
 Jaeger    Tempo
 (UI)     (Grafana)
```

### 6.2 Kong Zipkin Plugin Config

```yaml
# kong.yml — Kong OSS Zipkin plugin (overview)
plugins:
  - name: zipkin
    config:
      # Endpoint (Zipkin collector or OTEL)
      endpoint: http://otel-collector:9411/api/v2/spans
      # Sample rate: 1.0 = 100%, 0.1 = 10%
      sample_ratio: 0.1
      # Header types to accept
      header_type: "b3"
      # Trace ID from header
      trace_id_byte_count: 16
      # Span ID from header
      span_id_byte_count: 8
```

### 6.3 Trace Context Format

```
W3C traceparent:
  traceparent: 00-<trace-id-32hex>-<span-id-16hex>-<trace-flags>
  Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
            └─ version └─ trace ID (128 bit)    └─ span ID      └─ flags

B3 (Zipkin):
  X-B3-TraceId: 80f198ee56343ba864fe8b2a57d3eff7
  X-B3-SpanId: e457b5a2e4d86bd1
  X-B3-Sampled: 1

Correlation ID (Kong correlation-id plugin):
  X-Correlation-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  → Không W3C-compliant, chỉ dùng cho log correlation
```

### 6.4 When to Use Tracing

| Use Case | Metrics | Logs | Traces |
|---|---|---|---|
| Error rate spike | ✅ | ✅ | ⚠️ |
| Slow request (p95) | ✅ | ✅ | ⚠️ |
| Which service is slow? | ⚠️ (per-service) | ⚠️ | ✅ |
| Distributed transaction debug | ❌ | ⚠️ | ✅ |
| Request path through 10 services | ❌ | ❌ | ✅ |
| Latency breakdown per hop | ❌ | ❌ | ✅ |

**Recommendation**: Traces cho 1-5% request production (sampling), full trace cho error path.

---

## 7. Glossary

| Term | Định nghĩa |
|---|---|
| **Prometheus scrape** | Prometheus server gọi GET /metrics từ target theo scrape_interval |
| **Counter** | Prometheus metric type — chỉ tăng, không giảm. Dùng cho request count, error count |
| **Gauge** | Prometheus metric type — có thể tăng/giảm. Dùng cho active connections, memory, target health |
| **Histogram** | Prometheus metric type — đếm observations trong bucket. Dùng cho latency, response size |
| **Summary** | Prometheus metric type — đếm và tính quantile trên server. Không aggregate được tốt |
| **RED method** | Rate / Errors / Duration — framework metrics cho microservices |
| **USE method** | Utilization / Saturation / Errors — framework metrics cho infrastructure |
| **Histogram quantile** | `histogram_quantile()` — PromQL function tính percentile từ histogram bucket |
| **Cardinality** | Số lượng unique label value combination. Cao = nhiều time series = Prometheus TSDB lớn |
| **PromQL subquery** | Query trong query: `rate(metric[5m])[10m:1m]` — dùng để histogram_quantile multi-instance |
| **Pull model** | Prometheus chủ động scrape target. Target không cần push agent |
| **Push model** | Application/agent chủ động push metrics/logs đến collector/server |
| **Recording rule** | Pre-computed PromQL query, lưu thành new metric name. Dùng cho query tốc độ |
| **lua_shared_dict** | Shared memory zone trong OpenResty/Kong. Dùng để share counters/histograms giữa workers |
| **Lua-resty-counter** | OpenResty library cho atomic counter operations trong lua_shared_dict |
| **scrape_timeout** | Thời gian Prometheus chờ response từ target trước khi abandon scrape |
| **scrape_interval** | Khoảng cách giữa 2 scrape lần liên tiếp |
| **Keepalive idle** | Số connection giữ mở sau khi response xong, chờ request tiếp theo |
| **Log buffering** | Ghi log vào userspace buffer trước, flush xuống disk khi buffer đầy hoặc timeout |
| **traceparent** | W3C standard header cho distributed trace context. Format: `00-<trace-id>-<span-id>-<flags>` |
| **LogQL** | Loki query language. Khác với PromQL, gần với grep + pipe |
| **Promtail** | Loki agent — tail file, parse, label, push to Loki |
| **Loki** | Grafana log aggregation system — label-based, Prometheus-like query |

---

## 8. Cardinality Audit Query

```promql
-- Top 10 metrics by series count
topk(10,
  count by (__name__) (
    {__name__=~"kong_.*"}
  )
)

-- Check per-service cardinality
count by (service, route, status) (
  {__name__=~"kong_http_requests_total.*"}
)

-- Nginx cardinality check
count by (host, status) (
  {__name__=~"nginx_.*"}
)

-- Estimate TSDB size growth
# prometheus_tsdb_storage_blocks_bytes / prometheus_tsdb_head_series
# Target: < 3KB per series
```
