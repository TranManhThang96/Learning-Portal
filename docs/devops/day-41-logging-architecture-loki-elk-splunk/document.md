# Day 41: Cheat Sheet — Logging Architecture (Loki vs ELK vs Splunk)

---

## 1. Comparison Matrix: Loki vs ELK vs Splunk

| Tiêu chí | Loki (Grafana) | ELK (Elastic) | Splunk Enterprise |
|---|---|---|---|
| **Mô hình index** | Label-only (no full-text index) | Full inverted index | Proprietary index |
| **Query language** | LogQL | KQL / Lucene DSL | SPL (Splunk Processing Language) |
| **Chi phí lưu trữ** | Rất thấp (object store) | Cao (SSD-heavy) | Rất cao (per-GB license) |
| **Chi phí license** | OSS / Grafana Enterprise | OSS (Basic) / Elastic Cloud | Per-GB ingest ($50-150/GB/ngày) |
| **TCO 100GB/ngày** | ~$200-400/tháng | ~$800-1500/tháng | ~$3000-8000/tháng |
| **Tốc độ query** | Phụ thuộc label cardinality | Nhanh với indexed fields | Nhanh với hot buckets |
| **Full-text search** | Không (regex scan) | Có (inverted index) | Có (proprietary index) |
| **Log anomaly detection** | Qua Grafana AI (Enterprise) | ML trong Kibana | MLTK addon |
| **Multi-tenancy** | Có (tenant header) | Có (index per tenant) | Có (index per app) |
| **Kubernetes native** | Có (Grafana Agent k8s) | Có (ECK Operator) | Có (Splunk Operator) |
| **Alerting on logs** | Loki Ruler + Grafana | Kibana Alerting / Watcher | Splunk ES / Phantom |
| **RBAC** | Cơ bản (Grafana Enterprise) | Field-level security | Granular capability-based |
| **Audit log** | Nginx proxy logs | Native audit logging | Native audit trail |
| **Compliance** | Cần thêm tooling | SOC2, HIPAA (Elastic Cloud) | PCI-DSS, HIPAA, SOC2 |
| **Horizontal scale** | Xuất sắc (object store) | Tốt (sharding) | Tốt (indexer cluster) |
| **Setup time** | Giờ (single binary) | Ngày (multi-component) | Ngày (appliance-like) |
| **Hệ sinh thái** | Grafana stack | Elastic Stack (Beats, APM) | Splunk Apps Marketplace |

---

## 2. Kiến trúc Summary: 3 Dòng One-liner

```
Loki:    Index labels only → store chunks in S3 → scan on query → CHEAP, label-first
ELK:     Index everything → inverted index → instant full-text search → POWERFUL
Splunk:  Black-box index → SPL on search head → pay per GB → ENTERPRISE-grade
```

---

## 3. LogQL Quick Reference

### Basic Selectors

```logql
# Chọn tất cả logs từ một job
{job="api-gateway"}

# Multiple labels (AND)
{job="api-gateway", env="prod"}

# Regex match
{job=~"api-.*"}

# Negative match
{job!="noise-job"}

# Regex negative
{job!~"test-.*"}
```

### Line Filters (filter sau khi chọn stream)

```logql
# Chứa string (case-sensitive)
{job="api"} |= "error"

# Không chứa string
{job="api"} != "health"

# Regex match
{job="api"} |~ "conn(ect)?ion refused"

# Negative regex
{job="api"} !~ "debug|trace"
```

### JSON Parser

```logql
# Parse JSON fields → có thể filter theo field
{job="api"} | json

# Parse rồi filter theo field
{job="api"} | json | level = "error"

# Numeric comparison
{job="api"} | json | duration_ms > 1000

# Multiple conditions
{job="api"} | json | level = "error" | status_code >= 500
```

### Metrics Queries (MetricQL from logs)

```logql
# Count log lines per minute
count_over_time({job="api"}[1m])

# Rate (logs per second)
rate({job="api"} |= "error" [5m])

# Sum by label
sum by (level) (count_over_time({job="api"}[5m]))

# Error rate (%)
sum(rate({job="api"} |= "error"[5m])) /
sum(rate({job="api"}[5m])) * 100

# P99 latency từ logs
quantile_over_time(0.99,
  {job="api"} | json | unwrap duration_ms [5m]
) by (path)

# Bytes per second
bytes_rate({job="api"}[5m])
```

### Line Format

```logql
# Format output line
{job="api"} | json | line_format "{{.level}} {{.path}} {{.duration_ms}}ms"

# Label format (alias)
{job="api"} | json | label_format request_id=req_id, service=svc

# Unwrap để extract metric
{job="api"} | json | unwrap duration_ms | avg_over_time[5m]
```

---

## 4. KQL (Kibana Query Language) Quick Reference

```kql
# Full-text search
"connection refused"

# Field specific
level: "error"

# AND / OR / NOT
level: "error" AND service: "api"
level: "error" OR level: "warn"
NOT level: "debug"

# Wildcard
message: conn*

# Range (numeric)
duration_ms >= 1000

# Range (date)
@timestamp >= "2026-05-12T00:00:00Z" AND @timestamp <= "2026-05-12T23:59:59Z"

# Nested field
request.headers.authorization: *

# Regex (Kibana)
message: /conn.*timeout/
```

---

## 5. SPL (Splunk) Quick Reference

```splunk
# Basic search
index=prod level=error

# Search with pipe
index=prod | stats count by level

# Top N errors
index=prod level=error | top 10 message

# Time-based aggregation
index=prod | timechart span=5m count by level

# Calculate error rate
index=prod
| eval is_error=if(level="error",1,0)
| stats sum(is_error) as errors, count as total by _time
| eval error_rate=round(errors/total*100, 2)

# Correlate by request ID
index=prod request_id="abc-123" | sort _time | table _time, service, message

# Latency stats
index=prod
| stats avg(duration_ms), p95(duration_ms), p99(duration_ms) by endpoint

# Alert trigger
index=prod level=error
| stats count as error_count
| where error_count > 100
```

---

## 6. Logging Best Practices Checklist

### Application-level

```
[ ] Dùng structured logging (JSON) — không phải printf strings
[ ] Log có các field bắt buộc: timestamp, level, service, request_id, message
[ ] Truyền correlation_id / request_id qua HTTP headers (X-Request-ID)
[ ] Gắn correlation_id vào mọi log entry trong lifetime của request
[ ] Dùng đúng log level: DEBUG/INFO/WARN/ERROR/FATAL
[ ] Không log sensitive data: password, JWT, card number, PII, SSN
[ ] Không log full request/response body ở production (log headers hoặc key fields)
[ ] Log ở stdout/stderr — không log vào file riêng trong container
[ ] Không dùng log.Fatal() hoặc os.Exit() trong library code
[ ] Include stack trace CHỈ trong error/panic entries (không phải mọi warn)
```

### Infrastructure-level

```
[ ] Deploy log shipper sidecar hoặc DaemonSet (Promtail, Fluent Bit, Grafana Agent)
[ ] Buffer/queue giữa shipper và aggregator (tránh drop khi aggregator down)
[ ] Set retention policy rõ ràng: hot (ssd, 7d) → warm (30d) → cold (365d)
[ ] Sampling cho high-volume low-value logs (health check, debug)
[ ] Monitor log volume per service (alert khi volume đột biến)
[ ] Alert khi log shipper lag tăng (agent không kịp gửi)
[ ] Redaction pipeline (Promtail/Logstash) cho sensitive patterns
[ ] Encrypt logs at rest (S3 SSE-S3 hoặc SSE-KMS)
[ ] Restrict access: least privilege — developer không được đọc prod PII logs
[ ] Audit trail cho log queries (ai query gì, khi nào)
```

### Operational

```
[ ] Runbook link trong alert annotations
[ ] Dashboard hiển thị error rate, log volume, latency theo service
[ ] Có SLO cho logging pipeline: "99.9% logs ingested trong 30 giây"
[ ] Test disaster recovery: gián đoạn Loki/ES → verify không mất logs
[ ] Capacity planning: forecast log volume 3 tháng tới
[ ] Cost review định kỳ (ít nhất monthly): sampling, cold storage migration
[ ] Log format versioning: backward-compatible schema evolution
```

---

## 7. Cost Optimization Cheat Sheet

### Tier Estimate (S3 pricing, May 2026)

| Tier | Lưu trữ | Retrieval | Use case |
|---|---|---|---|
| S3 Standard | $0.023/GB/tháng | $0.0004/GB | Hot: 0-7 ngày |
| S3 Standard-IA | $0.0125/GB/tháng | $0.01/GB | Warm: 8-30 ngày |
| S3 Glacier Instant | $0.004/GB/tháng | $0.03/GB | Cold: 31-90 ngày |
| S3 Glacier Deep | $0.00099/GB/tháng | Bulk retrieval | Archive: 91d-365d |

### Ví dụ tính chi phí realworld

```
Scenario: 100GB logs/ngày = 3000 GB/tháng

Hot (7 ngày, S3 Standard):
  7/30 * 3000 GB * $0.023 = $16.1/tháng

Warm (8-30 ngày, S3-IA):
  22/30 * 3000 GB * $0.0125 = $27.5/tháng

Cold (31-90 ngày, Glacier Instant):
  60/30 * 3000 GB * $0.004 = $24/tháng

Archive (91-365 ngày, Glacier Deep):
  ~9 tháng * 3000 GB * $0.001 = $27/tháng

Tổng/tháng: ~$95/tháng (không kể Loki compute)

So với Splunk: 100GB/ngày * $50/GB (mid-tier license) = $5000/ngày!
```

### Sampling tiers để giảm volume

```
Log type                          | Volume | Sampling | New volume
Health check (/health, /ready)    | 40%    | 1%       | 0.4%
Static asset (200 OK, css/js)     | 15%    | 0%       | 0%  (loại bỏ)
Success API (2xx, non-sensitive)  | 30%    | 10%      | 3%
Client error (4xx)                | 10%    | 50%      | 5%
Server error (5xx)                | 3%     | 100%     | 3%
Critical / Security events        | 2%     | 100%     | 2%

Result: 100% → ~13.4% volume  ← 87% cost reduction!
```

### Loki compactor retention config

```yaml
# loki-config.yaml
compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  delete_request_store: filesystem
  deletion_mode: filter-and-delete

limits_config:
  # Global default: 15 ngày
  retention_period: 15d

# Per-tenant override (Loki multi-tenant mode)
# Trong tenant config hoặc overrides:
overrides:
  prod-tenant:
    retention_period: 30d   # Production giữ lâu hơn
  dev-tenant:
    retention_period: 7d    # Dev giữ ít hơn
  security-tenant:
    retention_period: 365d  # Security compliance
```

### ELK ILM (Index Lifecycle Management)

```json
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_primary_shard_size": "50gb",
            "max_age": "1d"
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "searchable_snapshot": {
            "snapshot_repository": "s3-cold-repo"
          },
          "set_priority": { "priority": 0 }
        }
      },
      "delete": {
        "min_age": "365d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

---

## 8. Sensitive Data Pattern Reference

### Regex patterns để redact

```yaml
# Credit Cards (Visa, Master, Amex)
'\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\\b'
replace: '**** **** **** XXXX'

# JWT tokens
'eyJ[A-Za-z0-9_\\-]+\\.[A-Za-z0-9_\\-]+\\.[A-Za-z0-9_\\-]+'
replace: '[JWT_REDACTED]'

# Email addresses
'\\b[A-Za-z0-9._%+\\-]+@[A-Za-z0-9.\\-]+\\.[A-Za-z]{2,}\\b'
replace: '[EMAIL_REDACTED]'

# AWS Access Key
'(AKIA|AIPA|ASIA)[A-Z0-9]{16}'
replace: '[AWS_KEY_REDACTED]'

# Generic API keys / secrets
'(api_?key|secret|token|password)["\s:=]+[^\s,"}{]+'
replace: '$1=[REDACTED]'

# SSH Private Key header
'-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----'
replace: '[PRIVATE_KEY_REDACTED]'

# IPv4 (sometimes PII in healthcare/finance)
'\\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(25[0-5]|...)\\b'
replace: '[IP_REDACTED]'

# US SSN
'\\b\\d{3}-\\d{2}-\\d{4}\\b'
replace: '[SSN_REDACTED]'
```

---

## 9. Decision Framework (Quick Reference)

```
Chọn Loki khi:
  ✅ High-volume logs, cost-sensitive
  ✅ Đã dùng Prometheus + Grafana
  ✅ Logs được query chủ yếu theo labels đã biết
  ✅ Kubernetes environment (Grafana Agent native)
  ✅ Team DevOps nhỏ, muốn setup đơn giản
  ❌ Cần full-text search mạnh
  ❌ Cần compliance audit logs chuyên sâu

Chọn ELK khi:
  ✅ Cần full-text search & anomaly detection
  ✅ Unstructured logs nhiều (legacy apps)
  ✅ Cần rich analytics, dashboards phức tạp
  ✅ Team có Elasticsearch expertise
  ❌ Budget hạn chế (disk + memory heavy)
  ❌ Cần horizontal scale đơn giản

Chọn Splunk khi:
  ✅ Enterprise / Large org với budget lớn
  ✅ SIEM + security use case
  ✅ Compliance-heavy (PCI-DSS, HIPAA, SOC2)
  ✅ Cần powerful SPL analytics ngay built-in
  ✅ Nhiều heterogeneous data sources
  ❌ Startup / Cost-sensitive project
  ❌ Team muốn open source infrastructure
```

---

## 10. Docker Quick Commands

```bash
# Khởi động Loki stack
docker run -d --name loki \
  -p 3100:3100 \
  grafana/loki:3.2.1 \
  -config.file=/etc/loki/local-config.yaml

# Kiểm tra Loki health
curl http://localhost:3100/ready
curl http://localhost:3100/metrics | grep loki_ingester

# Push test log entry
curl -H "Content-Type: application/json" \
  -d '{"streams":[{"labels":"{job=\"test\"}","entries":[{"ts":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","line":"test entry"}]}]}' \
  http://localhost:3100/loki/api/v1/push

# Query labels
curl http://localhost:3100/loki/api/v1/labels | jq .

# Query logs via API
curl -G http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={job="test"}' \
  --data-urlencode 'start=0' \
  --data-urlencode 'limit=10' | jq .data.result

# Volume stats per stream
curl -G http://localhost:3100/loki/api/v1/index/volume \
  --data-urlencode 'query={env="prod"}' \
  --data-urlencode "start=$(date -d '24 hours ago' +%s)000000000" \
  --data-urlencode "end=$(date +%s)000000000" | jq .

# Check ingester ring status
curl http://localhost:3100/ingester/ring | jq .

# Trigger compaction manually
curl -XPOST http://localhost:3100/compactor/delete_requests_queue

# Elasticsearch cluster health
curl http://localhost:9200/_cluster/health?pretty | jq .

# Elasticsearch list indices
curl http://localhost:9200/_cat/indices?v

# Elasticsearch search
curl -X POST http://localhost:9200/logs-*/_search -H "Content-Type: application/json" \
  -d '{"query":{"match":{"level":"error"}},"size":10}'
```

---

## 11. Loki Ruler — Log-based Alerting

```yaml
# /etc/loki/rules/prod/rules.yaml
groups:
  - name: api-service-alerts
    interval: 1m
    rules:
      # Alert: Error rate cao
      - alert: HighErrorRate
        expr: |
          sum(rate({job="api-service"} | json | level = "error" [5m])) by (service)
          /
          sum(rate({job="api-service"}[5m])) by (service)
          > 0.05
        for: 2m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "{{ $labels.service }}: error rate {{ $value | humanizePercentage }}"
          runbook_url: "https://wiki.internal/runbooks/high-error-rate"

      # Alert: Log pipeline lag (Promtail không gửi được)
      - alert: LogPipelineLag
        expr: |
          time() - max by (job) (last_over_time({job="api-service"}[5m]) | unwrap __timestamp__ [5m]) > 120
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Log pipeline lag: {{ $labels.job }} không nhận logs trong 2 phút"

      # Alert: Sudden log volume surge (DDoS detection)
      - alert: LogVolumeSurge
        expr: |
          sum(rate({job="api-service"}[5m])) by (job)
          > 1.5 * sum(rate({job="api-service"}[30m] offset 5m)) by (job)
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "Log volume tăng đột biến 50%+ trong 5 phút: {{ $labels.job }}"
```

---

## 12. Structured Logging Examples by Language

### Go (zerolog)
```go
import "github.com/rs/zerolog/log"

log.Info().
  Str("service", "api-gateway").
  Str("request_id", reqID).
  Str("user_id", userID).
  Str("path", "/api/orders").
  Int("status_code", 200).
  Int64("duration_ms", durationMs).
  Msg("Request completed")
```

### Node.js (pino)
```javascript
const logger = pino({ level: 'info' });

logger.info({
  service: 'api-gateway',
  request_id: reqId,
  user_id: userId,
  path: '/api/orders',
  status_code: 200,
  duration_ms: duration,
}, 'Request completed');
```

### Python (structlog)
```python
import structlog
log = structlog.get_logger()

log.info("request_completed",
  service="api-gateway",
  request_id=req_id,
  user_id=user_id,
  path="/api/orders",
  status_code=200,
  duration_ms=duration_ms)
```

### Java (logback + logstash encoder)
```java
import net.logstash.logback.argument.StructuredArguments.*;

logger.info("Request completed",
  kv("service", "api-gateway"),
  kv("request_id", reqId),
  kv("user_id", userId),
  kv("status_code", 200),
  kv("duration_ms", durationMs));
```

---

## 13. Observability Stack — Nơi Logging Fit vào

```
┌─────────────────────────────────────────────────────────────────┐
│                    Grafana (Unified UI)                          │
│                                                                  │
│  ┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │  Dashboards │  │    Explore     │  │       Alerting        │  │
│  │  (metrics)  │  │ (logs+traces)  │  │  (logs+metrics rules) │  │
│  └──────┬──────┘  └───────┬────────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼─────────────────────-┼──────────────┘
          │                 │                       │
    ┌─────▼─────┐    ┌──────▼───────┐    ┌─────────▼────────┐
    │ Prometheus │    │  Loki        │    │  Alertmanager    │
    │ (metrics)  │    │  (logs)      │    │  (notifications) │
    └─────┬──────┘    └──────┬───────┘    └──────────────────┘
          │                  │
    ┌─────▼──────────────────▼───────────────────────────┐
    │              Tempo (Distributed Traces)             │
    │               [Day 42 — coming next!]               │
    └─────────────────────────────────────────────────────┘
          ↑                  ↑                  ↑
          │                  │                  │
    [Prometheus    [Promtail /         [OpenTelemetry Collector]
     Exporters]    Grafana Agent]      [Day 42]
```

**Correlation in Grafana Explore:**
- Từ metric spike → click "View logs" → auto-filter Loki với matching time range + labels
- Từ Loki log entry có `trace_id` → click "View trace" → open Tempo trace
- **Tất cả correlate được nhờ shared labels và trace_id/request_id chung**

---

*Day 41 — Phase 6: Observability & Reliability | 50-Day DevOps Training Program*

