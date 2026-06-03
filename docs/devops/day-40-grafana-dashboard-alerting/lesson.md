# Day 40: Grafana Dashboard & Alerting

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Thiết kế được dashboard theo đúng best practices** — phân biệt dashboard cho executive, engineer, và on-call với mục đích và audience rõ ràng.
2. **Tạo được Grafana dashboard RED metrics** cho một service từ Prometheus data source — bao gồm RPS, error rate, latency percentiles.
3. **Cấu hình được alert rules trong Grafana** với multi-condition, evaluation period, notification channel, và runbook link.
4. **Hiểu và phòng tránh alert fatigue** — biết cách thiết kế alert giảm noise, tăng signal, dựa trên SLO-based alerting.
5. **Quản lý dashboard as code** — export/import JSON, provisioning, version control.

---

## 2. Bối cảnh & Động lực

### Vì sao dashboard design quan trọng?

Dashboard là "cửa sổ" nhìn vào hệ thống production. Dashboard tệ → team không phát hiện vấn đề → incident kéo dài.

```
Dashboard tệ:
  ┌────────────────────────────────────────────────┐
  │  50 panels, mixed metrics, no structure        │
  │  CPU | Memory | Disk | Network | ... | ...     │
  │  Request count (absolute) | Error count        │
  │  Random colors, no thresholds                  │
  │  → Nobody looks at it → Miss incidents         │
  └────────────────────────────────────────────────┘

Dashboard tốt:
  ┌────────────────────────────────────────────────┐
  │  Service Health Overview (RED Metrics)          │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
  │  │ RPS: 500 │ │ Errors:  │ │ p99:     │       │
  │  │ ▲ normal │ │ 0.3% ✅  │ │ 120ms ✅ │       │
  │  └──────────┘ └──────────┘ └──────────┘       │
  │  [Latency Graph]  [Error Rate Graph]           │
  │  → Glance = system health in 5 seconds         │
  └────────────────────────────────────────────────┘
```

### Alert fatigue là gì?

**Alert fatigue** = quá nhiều alerts → team bắt đầu ignore tất cả → miss real incidents.

Nghiên cứu cho thấy: khi on-call nhận > 10 alerts/ngày, tỷ lệ ignore tăng 60%. Khi > 50 alerts/ngày, tỷ lệ ignore là 90%.

### Liên hệ với developer

- **Dashboard** giống UI/UX cho infrastructure — cùng nguyên tắc: clear hierarchy, progressive disclosure, glanceable.
- **Alert rules** giống automated test suite — continuous verification system behavior matches expectations.
- **Runbook link** giống documentation attached to error — khi exception xảy ra, developer tra cứu docs tương tự.
- **SLO-based alerting** giống feature flag thresholds — không alert individual errors, mà alert khi "error budget" sắp hết.

### Nếu làm sai thì sao?

- **Dashboard quá phức tạp**: 50 panels → không ai nhìn → tốn effort tạo nhưng không ai dùng.
- **Alert mọi thứ**: 200 alert rules → PagerDuty kêu liên tục → engineer bỏ sound → miss real P1.
- **Không có runbook**: Alert fires lúc 3AM → on-call engineer mới, không biết làm gì → MTTR tăng 5x.
- **Alert threshold cố định**: CPU > 80% alert → container bình thường CPU burst lên 90% → false positive → fatigue.

---

## 3. Kiến thức nền tảng

### 3.1 Ba cấp độ Dashboard

| Dashboard | Audience | Mục đích | Metrics | Refresh |
|-----------|----------|----------|---------|---------|
| **Executive** | CTO, VP Eng | Business health, SLO status | SLO compliance, availability, incident count | 5-15 min |
| **Service** | Engineers | Service health, debugging entry point | RED metrics, dependencies | 30s-1min |
| **Debug** | On-call, SRE | Deep investigation | Detailed metrics, logs, traces | 10-30s |

### 3.2 Dashboard Design Principles

```
1. PURPOSE: Mỗi dashboard trả lời 1 câu hỏi chính
   "Service X có healthy không?" hoặc "Vì sao service X chậm?"

2. HIERARCHY: Thông tin quan trọng nhất ở trên cùng
   Row 1: Stat panels (current values: RPS, error rate, p99)
   Row 2: Time series graphs (trends)
   Row 3: Details (per-endpoint, per-instance)

3. GLANCEABLE: Nhìn 5 giây biết status
   Dùng colors: Green = OK, Yellow = Warning, Red = Critical
   Dùng thresholds trên stat panels

4. ACTIONABLE: Khi thấy vấn đề, biết làm gì tiếp
   Drill-down links đến debug dashboard
   Links đến logs, traces, runbooks

5. CONSISTENT: Cùng metric = cùng visualization across dashboards
   Latency luôn là line chart, error rate luôn là %
```

### 3.3 Grafana Core Concepts

| Concept | Mô tả |
|---------|-------|
| **Data Source** | Nơi Grafana lấy data (Prometheus, Loki, Tempo, etc.) |
| **Dashboard** | Tập hợp panels, organized by rows |
| **Panel** | Một visualization đơn lẻ (graph, stat, table, etc.) |
| **Variable** | Template variables cho dynamic dashboards ($service, $environment) |
| **Alert Rule** | Condition → evaluation → notification |
| **Notification Channel** | Nơi gửi alert (Slack, PagerDuty, Email, Webhook) |
| **Annotation** | Markers trên timeline (deployments, incidents) |
| **Provisioning** | Config-as-code cho data sources, dashboards |

### 3.4 Panel Types phổ biến

| Panel | Use case | Ví dụ |
|-------|----------|-------|
| **Stat** | Current value (big number) | Current RPS: 500, Error rate: 0.3% |
| **Time Series** | Trend over time | RPS graph, latency graph |
| **Gauge** | Current value vs threshold | CPU usage: 65% / 100% |
| **Bar Gauge** | Compare values | RPS per endpoint |
| **Table** | Detailed data | Top errors, slow queries |
| **Heatmap** | Distribution over time | Latency heatmap |
| **Logs** | Log entries (from Loki) | Error logs stream |
| **Alert List** | Current alerts | Firing alerts dashboard |

---

## 4. Deep Dive

### 4.1 Grafana Alerting Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Grafana Alerting Engine                   │
│                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │  Alert Rules  │    │  Evaluation  │    │  State     │ │
│  │              │    │  Engine      │    │  Manager   │ │
│  │  - PromQL    │───►│              │───►│            │ │
│  │  - Conditions│    │  - Query DS  │    │  - OK      │ │
│  │  - Period    │    │  - Evaluate  │    │  - Pending │ │
│  │  - For       │    │  - Compare   │    │  - Alerting│ │
│  └──────────────┘    └──────────────┘    │  - NoData  │ │
│                                           └─────┬──────┘ │
│                                                  │        │
│  ┌──────────────────────────────────────────────▼──────┐ │
│  │              Notification Pipeline                    │ │
│  │                                                        │ │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐             │ │
│  │  │ Silence  │  │ Grouping │  │ Route   │             │ │
│  │  │         │  │          │  │         │             │ │
│  │  │ Mute    │──►│ Dedup    │──►│ Match   │──► Notify  │ │
│  │  │ periods │  │ by labels│  │ to      │    (Slack,  │ │
│  │  └─────────┘  └──────────┘  │ channel │    PD, etc) │ │
│  │                              └─────────┘             │ │
│  └────────────────────────────────────────────────────── │ │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Alert States

```
       ┌───────┐
       │  OK   │ ← Condition false
       └───┬───┘
           │ Condition becomes true
           ▼
       ┌───────────┐
       │  Pending   │ ← Waiting for "for" duration
       └───┬───────┘
           │ Condition true for "for" duration
           ▼
       ┌───────────┐
       │  Alerting  │ ← Notification sent
       └───┬───────┘
           │ Condition becomes false
           ▼
       ┌───────┐
       │  OK   │ ← Resolved notification sent
       └───────┘

Special states:
  NoData  ← Data source returns no data
  Error   ← Query execution error
```

### 4.3 Grafana vs Prometheus AlertManager

| | Grafana Alerting | Prometheus AlertManager |
|--|-----------------|----------------------|
| **Alert define** | Grafana UI hoặc provisioning | `rules.yml` file |
| **Evaluation** | Grafana server | Prometheus server |
| **Multi-datasource** | ✅ (Prom + Loki + etc.) | ❌ Prometheus only |
| **UI** | ✅ Built-in | ❌ Separate UI |
| **Silence/Inhibit** | ✅ | ✅ |
| **Routing** | ✅ Label-based | ✅ Label-based |
| **HA** | ⚠️ Cần Grafana HA | ✅ Native cluster |
| **Best for** | Teams dùng Grafana làm single pane | Teams dùng Prometheus extensively |

**Recommendation**: Dùng **Prometheus AlertManager** cho infrastructure alerts (reliability). Dùng **Grafana Alerting** cho alerts cần multi-datasource hoặc team dùng Grafana làm primary tool.

### 4.4 SLO-based Alerting

Thay vì alert trên symptom (CPU > 80%), alert dựa trên SLO consumption:

```
Traditional alerting:
  IF error_rate > 5% for 5m → ALERT
  Problem: 5% error cho 5 phút chưa chắc ảnh hưởng monthly SLO (99.9%)

SLO-based alerting:
  Monthly error budget = 100% - 99.9% = 0.1%
  0.1% of 30 days = 43.2 minutes of total downtime
  
  IF burn_rate > 14.4x for 1h → PAGE (fast burn, will exhaust budget in < 3 hours)
  IF burn_rate > 6x for 6h → TICKET (slow burn, will exhaust budget in < 5 days)
  IF burn_rate > 1x for 3d → WARNING (on track to exhaust budget this month)
```

```promql
# Error budget burn rate
# burn_rate = (actual_error_rate / target_error_rate)
# Target: 99.9% → allowed error rate = 0.1% = 0.001

# Fast burn (1h window)
(
  sum(rate(http_requests_total{status=~"5.."}[1h]))
  /
  sum(rate(http_requests_total[1h]))
) / 0.001

# Slow burn (6h window)
(
  sum(rate(http_requests_total{status=~"5.."}[6h]))
  /
  sum(rate(http_requests_total[6h]))
) / 0.001
```

### 4.5 Alert Fatigue — Nguyên nhân và giải pháp

| Nguyên nhân | Impact | Giải pháp |
|-------------|--------|-----------|
| **Threshold quá nhạy** | Alert minor fluctuations | Tăng "for" duration, tăng threshold |
| **Alert trên symptoms, not impact** | CPU 85% nhưng service vẫn OK | Alert trên RED metrics thay vì resource |
| **Thiếu dedup** | Cùng issue → 10 alerts | Group alerts by service/severity |
| **No auto-resolve** | Alert fire nhưng không auto-resolve | Ensure condition clears properly |
| **Không có severity** | P1 và P3 lẫn lộn | Label severity: critical, warning, info |
| **Dead alerts** | Alert cho service đã decomm | Review alerts quarterly |

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Dashboard Best Practices

**DO**:
- 1 dashboard = 1 purpose (service health, debugging, executive).
- Stat panels ở row đầu tiên (glanceable status).
- Color thresholds: green/yellow/red matching severity.
- Variables cho service/environment filtering.
- Annotations cho deployments (biết deploy lúc nào gây issue).
- Links đến related dashboards, logs, traces.

**DON'T**:
- Quá 15 panels per dashboard → information overload.
- Mix infrastructure metrics và application metrics trên cùng dashboard.
- Dùng pie charts cho time series data.
- Absolute counters trên graphs (dùng rate() thay vì raw counter).
- Auto-refresh < 10s cho non-debug dashboards.

### 5.2 Alerting Best Practices

| Practice | Mô tả |
|----------|-------|
| **Alert trên symptoms** | Error rate, latency — KHÔNG CPU, memory (trừ khi critical) |
| **"for" duration** | ≥ 2 phút — tránh flapping |
| **Severity levels** | Critical (page) → Warning (ticket) → Info (log) |
| **Runbook link** | Mỗi alert PHẢI có link đến runbook |
| **Owner** | Mỗi alert có team owner rõ ràng |
| **Review quarterly** | Delete/update stale alerts |
| **Test alerts** | Periodically trigger alerts to verify pipeline works |

### 5.3 Theo scenario

**Startup**:
- 1 dashboard per service (RED metrics).
- 3-5 critical alerts only (service down, high error rate, high latency).
- Slack notifications.

**Mid-size**:
- Executive dashboard + service dashboards + debug dashboards.
- 10-20 alert rules with severity levels.
- PagerDuty cho critical, Slack cho warning.
- SLO dashboard.
- Deployment annotations.

**Enterprise**:
- Team-specific dashboards + platform dashboards.
- SLO-based alerting with burn rate.
- Multi-level routing (team → escalation → management).
- Dashboard as code (version controlled).
- Quarterly alert review process.

---

## 6. Performance & Scalability ⭐

### 6.1 Dashboard Performance

| Factor | Impact | Optimization |
|--------|--------|-------------|
| **Number of panels** | Mỗi panel = 1+ query | Giới hạn 15 panels, dùng collapsed rows |
| **Query complexity** | Complex PromQL → slow | Recording rules cho dashboard queries |
| **Time range** | 7 days data → slow | Default 1-6h cho service dashboards |
| **Refresh interval** | 10s × 15 panels = 150 queries/min | 30s cho overview, 10s chỉ debug |
| **Variables** | Multi-value variables → multiple queries | Limit variable options |

### 6.2 Grafana Scaling

- **Single instance**: Đủ cho < 50 concurrent users, < 100 dashboards.
- **HA setup**: Multiple Grafana instances + shared database (PostgreSQL/MySQL) + shared session store (Redis).
- **Caching**: Enable query caching trong Grafana.
- **CDN**: Dùng CDN cho static assets nếu Grafana public-facing.

---

## 7. Security & Reliability Considerations

### 7.1 Security

- **Authentication**: OIDC/LDAP integration, không dùng default admin/admin.
- **Authorization**: Org-based hoặc folder-based permissions.
- **Data source permissions**: Team A chỉ query Prometheus namespace A.
- **Dashboard permissions**: Critical dashboards readonly cho non-admin.
- **API keys**: Rotate regularly, scope to minimum permission.

### 7.2 Reliability

- **Dashboard backup**: Export JSON, store trong git.
- **Provisioning**: Config-as-code → recreate Grafana từ scratch trong 5 phút.
- **Alert reliability**: Test notification channels monthly.
- **Grafana HA**: Nếu Grafana down, alerts không fire → cần AlertManager backup.

---

## 8. Hands-on Example

### 8.1 Setup Stack

```bash
mkdir -p /tmp/grafana-lab && cd /tmp/grafana-lab
mkdir -p grafana/provisioning/datasources grafana/provisioning/dashboards grafana/dashboards
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

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_ALERTING_ENABLED=true
      - GF_UNIFIED_ALERTING_ENABLED=true
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
```

**File: `prometheus.yml`**

```yaml
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

**File: `grafana/provisioning/datasources/prometheus.yml`**

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

**File: `grafana/provisioning/dashboards/dashboard.yml`**

```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

### 8.2 Dashboard JSON (RED Metrics)

**File: `grafana/dashboards/service-health.json`**

```json
{
  "dashboard": {
    "title": "Service Health - RED Metrics",
    "tags": ["service", "red", "production"],
    "timezone": "browser",
    "refresh": "30s",
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "panels": [
      {
        "title": "Request Rate (RPS)",
        "type": "stat",
        "gridPos": { "h": 4, "w": 8, "x": 0, "y": 0 },
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{job=\"app\"}[5m]))",
            "legendFormat": "RPS"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "reqps",
            "thresholds": {
              "steps": [
                { "value": 0, "color": "red" },
                { "value": 1, "color": "yellow" },
                { "value": 10, "color": "green" }
              ]
            }
          }
        }
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "gridPos": { "h": 4, "w": 8, "x": 8, "y": 0 },
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{job=\"app\",code=~\"5..\"}[5m])) / sum(rate(http_requests_total{job=\"app\"}[5m])) * 100",
            "legendFormat": "Error %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "steps": [
                { "value": 0, "color": "green" },
                { "value": 1, "color": "yellow" },
                { "value": 5, "color": "red" }
              ]
            }
          }
        }
      },
      {
        "title": "p99 Latency",
        "type": "stat",
        "gridPos": { "h": 4, "w": 8, "x": 16, "y": 0 },
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job=\"app\"}[5m])) by (le))",
            "legendFormat": "p99"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "s",
            "thresholds": {
              "steps": [
                { "value": 0, "color": "green" },
                { "value": 0.5, "color": "yellow" },
                { "value": 1, "color": "red" }
              ]
            }
          }
        }
      },
      {
        "title": "Request Rate Over Time",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 4 },
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{job=\"app\"}[5m])) by (code)",
            "legendFormat": "{{code}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "reqps"
          }
        }
      },
      {
        "title": "Latency Percentiles",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 4 },
        "targets": [
          {
            "expr": "histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{job=\"app\"}[5m])) by (le))",
            "legendFormat": "p50"
          },
          {
            "expr": "histogram_quantile(0.90, sum(rate(http_request_duration_seconds_bucket{job=\"app\"}[5m])) by (le))",
            "legendFormat": "p90"
          },
          {
            "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job=\"app\"}[5m])) by (le))",
            "legendFormat": "p99"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "s"
          }
        }
      },
      {
        "title": "Error Rate Over Time",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 12 },
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{job=\"app\",code=~\"5..\"}[5m])) / sum(rate(http_requests_total{job=\"app\"}[5m])) * 100",
            "legendFormat": "Error Rate %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "steps": [
                { "value": 0, "color": "green" },
                { "value": 1, "color": "yellow" },
                { "value": 5, "color": "red" }
              ]
            },
            "custom": {
              "thresholdsStyle": {
                "mode": "line"
              }
            }
          }
        }
      }
    ]
  }
}
```

### 8.3 Chạy và test

```bash
# Start stack
docker compose up -d

# Wait for services
sleep 15

# Generate traffic (background)
while true; do
  curl -s http://localhost:8080/ > /dev/null 2>&1
  curl -s http://localhost:8080/err > /dev/null 2>&1
  sleep 0.2
done &
TRAFFIC_PID=$!

echo "Traffic generator PID: $TRAFFIC_PID"
echo ""
echo "=== Access Points ==="
echo "App:        http://localhost:8080"
echo "Prometheus: http://localhost:9090"
echo "Grafana:    http://localhost:3000 (admin / admin123)"
echo ""
echo "=== Next Steps ==="
echo "1. Open Grafana → Dashboard 'Service Health - RED Metrics'"
echo "2. Verify 3 stat panels show values"
echo "3. Verify time series graphs show data"
```

### 8.4 Tạo Alert Rule trong Grafana UI

1. Truy cập Grafana: http://localhost:3000 (admin / admin123).
2. Vào **Alerting → Alert rules → New alert rule**.
3. Cấu hình:

```
Rule name: HighErrorRate
Query: 
  A: sum(rate(http_requests_total{job="app",code=~"5.."}[5m])) / sum(rate(http_requests_total{job="app"}[5m]))
  
Condition: 
  IS ABOVE 0.05

Evaluation:
  Evaluate every: 1m
  For: 2m (pending duration)

Labels:
  severity: warning
  service: app

Annotations:
  Summary: Error rate is {{ $values.A }} on app service
  Runbook: https://wiki.example.com/runbooks/high-error-rate
```

### 8.5 Tạo Notification Contact Point

```
1. Alerting → Contact Points → New contact point
2. Name: "DevOps Slack"
3. Type: Slack (hoặc Webhook cho testing)
4. Webhook URL: https://hooks.slack.com/services/xxx (hoặc webhook.site cho testing)
5. Test → Save
```

### 8.6 Cleanup

```bash
# Stop traffic generator
kill $TRAFFIC_PID 2>/dev/null

# Stop and remove all
docker compose down -v
cd / && rm -rf /tmp/grafana-lab
```

### 8.7 Verify checklist

- [ ] Grafana chạy và connect được Prometheus data source
- [ ] Dashboard "Service Health" hiển thị 6 panels
- [ ] Stat panels hiển thị current values (RPS, error rate, p99)
- [ ] Time series graphs hiển thị trends
- [ ] Color thresholds hoạt động (green/yellow/red)
- [ ] Alert rule tạo thành công
- [ ] Biết cách export dashboard JSON
- [ ] Biết cách tạo contact point cho notification

---

## 9. Common Pitfalls & Debugging

### 9.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| **Dashboard "No data"** | Data source URL sai hoặc Prometheus down | Check data source config, dùng service name trong Docker network |
| **Alert never fires** | "for" duration quá dài hoặc condition sai | Giảm "for", test query trên Explore page |
| **Alert always firing** | Threshold quá nhạy hoặc query trả NaN | Adjust threshold, handle NaN trong query |
| **Dashboard load slow** | Complex queries, long time range | Recording rules, giảm time range, collapse rows |
| **Provisioned dashboard can't edit** | `editable: false` trong provisioning | Set `editable: true` hoặc edit provisioning file |
| **Alert notification not received** | Contact point misconfigured | Test contact point, check Grafana logs |

### 9.2 Debug commands

```bash
# Check Grafana logs
docker logs grafana

# Check Grafana health
curl -s http://localhost:3000/api/health | jq

# List data sources
curl -s -u admin:admin123 http://localhost:3000/api/datasources | jq

# List dashboards
curl -s -u admin:admin123 http://localhost:3000/api/search | jq '.[].title'

# Export dashboard JSON
curl -s -u admin:admin123 http://localhost:3000/api/dashboards/uid/<uid> | jq '.dashboard'

# Check alert rules
curl -s -u admin:admin123 http://localhost:3000/api/v1/provisioning/alert-rules | jq
```

### 9.3 Production Case Study: Alert Fatigue at a Payment Company

**Context**: Fintech startup, 15 microservices, 200 alert rules. On-call rotation: 5 engineers.

**Symptom**: On-call engineer nhận trung bình 70 alerts/ngày (PagerDuty + Slack). Sau 3 tháng:
- Mọi engineer mute Slack channel.
- PagerDuty sound quen thuộc → "chắc lại false alarm".
- Thứ 6 tuần trước: payment gateway down 45 phút → P1 incident.
- On-call check điện thoại: "Thấy 12 alerts nhưng tưởng noise như mọi khi."

**Investigation**:
- 200 alert rules → 150 không có owner.
- 80 alerts là infrastructure (CPU, memory) không liên quan service health.
- 30 alerts threshold quá nhạy (traffic fluctuation → fire every day).
- 5 alerts duplicate (cùng condition, khác label).
- Alert "PaymentGatewayDown" bị drown trong noise.

**Root Cause**: No alert hygiene process. Alert tạo dễ, không ai review/delete.

**Long-term Fix**:
1. **Alert audit**: Delete 120 alerts không có owner hoặc không actionable.
2. **Severity redesign**: Critical (page) = 5 alerts. Warning (Slack) = 20 alerts. Info (log) = rest.
3. **SLO-based alerting**: Thay 80 infrastructure alerts bằng 10 SLO burn rate alerts.
4. **Quarterly review**: Calendar reminder review alerts mỗi quý.
5. **On-call metrics**: Track alerts/day, time-to-ack → KPI cho alert quality.

**Result**: Alerts/day giảm từ 70 → 8. P1 response time giảm từ 45 phút → 4 phút.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 39)
- Day 39 dạy Prometheus & PromQL — queries, recording rules, alert rules trong Prometheus.
- Day 40 dùng Prometheus làm data source cho Grafana.
- Recording rules từ Day 39 làm dashboard load nhanh hơn.
- Alert rules có thể define trong Prometheus AlertManager (Day 39) hoặc Grafana Alerting (Day 40).

### Bài sau (Day 41)
- Day 41: Logging Architecture — Loki vs ELK vs Splunk.
- Grafana + Loki = unified observability UI (metrics + logs trên cùng dashboard).
- Log panels trong Grafana dashboard sẽ dùng Loki data source.

### Kiến thức liên quan
- **Day 38**: Three pillars — dashboard là nơi visualize tất cả 3 pillars.
- **Day 42**: Tracing — Grafana + Tempo cho trace visualization.
- **Day 43**: SLI/SLO — SLO dashboard và error budget tracking.
- **Day 44**: Incident Response — dashboard là tool chính khi incident.

---

## 11. Tài liệu tham khảo

### Must-read
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [Grafana Alerting Documentation](https://grafana.com/docs/grafana/latest/alerting/)
- [Google SRE Book - Chapter 11: Being On-Call](https://sre.google/sre-book/being-on-call/)

### Nice-to-have
- [Alert Fatigue Analysis - PagerDuty](https://www.pagerduty.com/resources/learn/what-is-alert-fatigue/)
- [SLO-based Alerting - Google Cloud](https://cloud.google.com/stackdriver/docs/solutions/slo-monitoring/alerting-on-budget-burn-rate)
- [Dashboard Design Patterns - Grafana Blog](https://grafana.com/blog/2022/06/06/grafana-dashboards-a-complete-guide-to-all-the-different-types-you-can-build/)

### Deep-dive
- [Practical Monitoring - Mike Julian (O'Reilly)](https://www.oreilly.com/library/view/practical-monitoring/9781491957349/)
- [The Art of Monitoring - James Turnbull](https://artofmonitoring.com/)
- [Kill Your Dashboard: Why Wall Displays are Useless](https://www.honeycomb.io/blog/kill-your-dashboard)

