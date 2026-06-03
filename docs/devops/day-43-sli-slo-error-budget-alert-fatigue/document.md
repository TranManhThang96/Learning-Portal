# Day 43 — Cheat Sheet & Reference: SLI/SLO, Error Budget & Alert Fatigue

> Tài liệu tham chiếu nhanh — dùng khi thiết kế SLO hoặc review alert rules.

---

## 1. Công thức nhanh

```
Error Budget (fraction) = 1 - SLO_target
Error Budget (time/30d) = (1 - SLO%) × 30 × 24 × 60  [phút]

Burn Rate = current_error_rate / error_budget_fraction
Time to budget exhaustion = error_budget_time / burn_rate

SLI (availability) = good_requests / total_requests
SLI (latency)      = requests_under_threshold / total_requests
```

---

## 2. Bảng Error Budget nhanh

| SLO | Error Budget | Budget/30d | Budget/7d | Budget/1d |
|---|---|---|---|---|
| 90.000% | 10.000% | 43h 48m | 10h 4m | 2h 24m |
| 95.000% | 5.000% | 21h 54m | 5h 2m | 1h 12m |
| 99.000% | 1.000% | 7h 18m | 1h 41m | 14m 24s |
| 99.500% | 0.500% | 3h 39m | 50m 24s | 7m 12s |
| 99.900% | 0.100% | 43m 48s | 10m 5s | 1m 26s |
| 99.950% | 0.050% | 21m 54s | 5m 2s | 43s |
| 99.990% | 0.010% | 4m 23s | 1m | 8.6s |
| 99.999% | 0.001% | 26s | 6s | 0.86s |

---

## 3. Bảng Burn Rate — Multi-Window Reference

> Dùng cho SLO 99.9% (error_budget = 0.001). Scale theo tỷ lệ cho SLO khác.

| Severity | Burn Rate | Thời gian hết budget | Short Window | Long Window | Action |
|---|---|---|---|---|---|
| PAGE | 14.4x | ~2 ngày | 5 phút | 1 giờ | Wake up on-call ngay |
| TICKET | 6x | ~5 ngày | 30 phút | 6 giờ | Slack ticket, fix hôm nay |
| WARNING | 3x | ~10 ngày | 2 giờ | 24 giờ | Track trên dashboard |
| INFO | 1x | 30 ngày (normal) | 6 giờ | 3 ngày | Tự động ticket |

**Tính burn rate threshold cho SLO khác:**
```
PAGE threshold  = 14.4  (hằng số — không đổi theo SLO)
TICKET thresh   = 6     (hằng số)
WARNING thresh  = 3     (hằng số)

Chỉ thay error_budget_fraction trong expr — threshold không đổi.
```

---

## 4. SLO Template — Theo loại service

### 4.1 HTTP API (Read-heavy)

```yaml
service_type: http-api-read-heavy
example: user-profile-api, product-catalog, search

slos:
  - name: availability
    target: 99.9%
    sli: |
      sum(rate(http_requests_total{code!~"5.."}[window]))
      / sum(rate(http_requests_total[window]))
    rationale: "Read-only, eventual consistency OK, high volume"

  - name: latency-p99
    target: 99.0%
    threshold: 500ms
    sli: |
      sum(rate(http_request_duration_seconds_bucket{le="0.5"}[window]))
      / sum(rate(http_request_duration_seconds_count[window]))
    rationale: "User-facing, 500ms P99 competitive target"

  - name: latency-p50
    target: 99.5%
    threshold: 100ms
    rationale: "Median experience phải nhanh"
```

### 4.2 HTTP API (Write/Transactional)

```yaml
service_type: http-api-write-transactional
example: checkout-api, payment-api, order-api

slos:
  - name: availability
    target: 99.95%   # Cao hơn read API — write failure = revenue loss
    sli: |
      sum(rate(http_requests_total{method=~"POST|PUT|PATCH", code!~"5.."}[window]))
      / sum(rate(http_requests_total{method=~"POST|PUT|PATCH"}[window]))

  - name: latency-p99
    target: 99.0%
    threshold: 2000ms   # User tolerate payment slowness hơn là browsing
    sli: |
      sum(rate(http_request_duration_seconds_bucket{le="2.0"}[window]))
      / sum(rate(http_request_duration_seconds_count[window]))

  - name: correctness
    target: 99.99%   # Rất cao — double charge/wrong amount = critical
    sli: |
      sum(rate(transactions_correct_total[window]))
      / sum(rate(transactions_total[window]))
```

### 4.3 Background Worker / Queue Consumer

```yaml
service_type: background-worker
example: email-worker, report-generator, data-sync

slos:
  - name: throughput
    target: 99.0%
    description: "95% messages processed within SLA time"
    sli: |
      sum(rate(messages_processed_within_sla_total[window]))
      / sum(rate(messages_received_total[window]))

  - name: freshness
    target: 99.5%
    description: "Data updated trong vòng 5 phút"
    sli: |
      sum(rate(data_sync_completed_total{lag_seconds="<300"}[window]))
      / sum(rate(data_sync_started_total[window]))

  - name: job-success-rate
    target: 99.0%
    sli: |
      sum(rate(job_runs_total{status="success"}[window]))
      / sum(rate(job_runs_total[window]))
```

### 4.4 Internal Microservice (Downstream dependency)

```yaml
service_type: internal-microservice
example: auth-service, user-service, config-service

slos:
  - name: availability
    target: 99.95%   # Cascade failures nếu bị down
    sli: |
      sum(rate(grpc_server_handled_total{grpc_code!="UNAVAILABLE",grpc_code!="INTERNAL"}[window]))
      / sum(rate(grpc_server_handled_total[window]))

  - name: latency-p99
    target: 99.5%
    threshold: 100ms   # Internal services phải nhanh (không add latency to caller)
    sli: |
      sum(rate(grpc_server_handling_seconds_bucket{le="0.1"}[window]))
      / sum(rate(grpc_server_handling_seconds_count[window]))
```

### 4.5 Data Pipeline / ETL

```yaml
service_type: data-pipeline
example: analytics-etl, ML feature pipeline, reporting

slos:
  - name: pipeline-success-rate
    target: 99.0%
    sli: |
      sum(rate(pipeline_runs_total{status="success"}[window]))
      / sum(rate(pipeline_runs_total[window]))

  - name: data-freshness
    target: 99.5%
    description: "Dashboard data phải mới hơn 1 giờ"
    measurement: time-based (không phải request-based)
    metric: "time() - data_last_updated_timestamp_seconds < 3600"
```

---

## 5. PromQL Snippets — SLO Monitoring

### 5.1 Availability SLI

```promql
# Error rate (short form)
1 - (
  sum(rate(http_requests_total{service="my-service", code!~"5.."}[5m]))
  / sum(rate(http_requests_total{service="my-service"}[5m]))
)

# Burn rate (SLO 99.9% = error_budget 0.001)
(1 - sum(rate(http_requests_total{service="my-service",code!~"5.."}[1h]))
 / sum(rate(http_requests_total{service="my-service"}[1h]))) / 0.001

# Error budget consumed (30-day rolling, SLO 99.9%)
(1 - (
  sum(rate(http_requests_total{service="my-service",code!~"5.."}[30d]))
  / sum(rate(http_requests_total{service="my-service"}[30d]))
)) / 0.001

# Error budget remaining (%)
(1 - (
  (1 - (
    sum(rate(http_requests_total{service="my-service",code!~"5.."}[30d]))
    / sum(rate(http_requests_total{service="my-service"}[30d]))
  )) / 0.001
)) * 100
```

### 5.2 Latency SLI

```promql
# % requests under threshold (histogram)
sum(rate(http_request_duration_seconds_bucket{service="my-service", le="0.5"}[5m]))
/ sum(rate(http_request_duration_seconds_count{service="my-service"}[5m]))

# P99 latency
histogram_quantile(0.99,
  sum by(le) (rate(http_request_duration_seconds_bucket{service="my-service"}[5m]))
)

# P50, P95, P99 in one query (để compare)
histogram_quantile(0.99, sum by(le, service) (rate(http_request_duration_seconds_bucket[5m])))
```

### 5.3 Recording Rules Template

```yaml
# prometheus-recording-rules.yaml
# Thay "my-service" và slo-name theo service thực tế

groups:
  - name: slo_recording_rules
    interval: 30s
    rules:
      # Availability error ratio — nhiều windows
      - record: slo:sli_error_rate:ratio_rate5m
        expr: |
          1 - (sum(rate(http_requests_total{service="my-service",code!~"5.."}[5m]))
          / sum(rate(http_requests_total{service="my-service"}[5m])))
        labels:
          service: my-service
          slo: availability

      - record: slo:sli_error_rate:ratio_rate30m
        expr: |
          1 - (sum(rate(http_requests_total{service="my-service",code!~"5.."}[30m]))
          / sum(rate(http_requests_total{service="my-service"}[30m])))
        labels:
          service: my-service
          slo: availability

      - record: slo:sli_error_rate:ratio_rate1h
        expr: |
          1 - (sum(rate(http_requests_total{service="my-service",code!~"5.."}[1h]))
          / sum(rate(http_requests_total{service="my-service"}[1h])))
        labels:
          service: my-service
          slo: availability

      - record: slo:sli_error_rate:ratio_rate6h
        expr: |
          1 - (sum(rate(http_requests_total{service="my-service",code!~"5.."}[6h]))
          / sum(rate(http_requests_total{service="my-service"}[6h])))
        labels:
          service: my-service
          slo: availability

      - record: slo:sli_error_rate:ratio_rate1d
        expr: |
          1 - (sum(rate(http_requests_total{service="my-service",code!~"5.."}[1d]))
          / sum(rate(http_requests_total{service="my-service"}[1d])))
        labels:
          service: my-service
          slo: availability

      - record: slo:sli_error_rate:ratio_rate3d
        expr: |
          1 - (sum(rate(http_requests_total{service="my-service",code!~"5.."}[3d]))
          / sum(rate(http_requests_total{service="my-service"}[3d])))
        labels:
          service: my-service
          slo: availability
```

### 5.4 Multi-Window Alert Template (Parametric)

```yaml
# Full template — thay SERVICE, SLO_TARGET, ERROR_BUDGET, TEAM trước khi dùng
# ERROR_BUDGET = 1 - SLO_TARGET (e.g., SLO=99.9% → ERROR_BUDGET=0.001)

groups:
  - name: SERVICE_slo_alerts
    rules:

      # PAGE: 14.4x burn rate — budget hết trong 2 ngày
      - alert: SERVICESLOCritical
        expr: |
          (slo:sli_error_rate:ratio_rate5m{service="SERVICE"} / ERROR_BUDGET > 14.4)
          and
          (slo:sli_error_rate:ratio_rate1h{service="SERVICE"} / ERROR_BUDGET > 14.4)
        for: 2m
        labels:
          severity: page
          team: TEAM
        annotations:
          summary: "SERVICE SLO critical burn rate ({{ $value | humanize }}x)"
          description: |
            Budget sẽ hết trong ~2 ngày.
            Current error rate: {{ with query "1 - slo:sli_error_rate:ratio_rate5m{service='SERVICE'}" }}
              {{ . | first | value | humanizePercentage }}{{ end }}
          runbook_url: "RUNBOOK_URL"

      # TICKET: 6x burn rate — budget hết trong 5 ngày
      - alert: SERVICESLOHigh
        expr: |
          (slo:sli_error_rate:ratio_rate30m{service="SERVICE"} / ERROR_BUDGET > 6)
          and
          (slo:sli_error_rate:ratio_rate6h{service="SERVICE"} / ERROR_BUDGET > 6)
        for: 15m
        labels:
          severity: ticket
          team: TEAM
        annotations:
          summary: "SERVICE SLO elevated burn rate ({{ $value | humanize }}x)"
          runbook_url: "RUNBOOK_URL"

      # WARNING: 3x burn rate — budget hết trong 10 ngày
      - alert: SERVICESLOElevated
        expr: |
          (slo:sli_error_rate:ratio_rate2h{service="SERVICE"} / ERROR_BUDGET > 3)
          and
          (slo:sli_error_rate:ratio_rate1d{service="SERVICE"} / ERROR_BUDGET > 3)
        for: 1h
        labels:
          severity: warning
          team: TEAM
        annotations:
          summary: "SERVICE SLO elevated — monitor closely"

      # INFO: Budget < 20%
      - alert: SERVICEBudgetLow
        expr: |
          (slo:sli_error_rate:ratio_rate30d{service="SERVICE"} / ERROR_BUDGET) > 0.8
        labels:
          severity: info
          team: TEAM
        annotations:
          summary: "SERVICE error budget < 20% remaining this month"
```

---

## 6. Error Budget Calculation Worksheet

```
=== ERROR BUDGET WORKSHEET ===
Service: _______________________
SLO Target: _______%
Review Period: 30 ngày (_____ phút = 43,200 phút)

STEP 1: Error Budget Allocation
  Error Budget % = 1 - SLO_target% = _______%
  Error Budget (phút) = ______% × 43,200 = _______ phút

STEP 2: Incidents This Period
  Incident | Duration (phút) | Error Rate | Budget Burned
  ---------|-----------------|------------|---------------
  Incident 1 | ___________ | _________% | ___________
  Incident 2 | ___________ | _________% | ___________
  Incident 3 | ___________ | _________% | ___________
  Normal baseline | 43,200 | _________% | ___________
  
  Budget burned = duration × error_rate   (per incident)
  Total burned = SUM of all rows

STEP 3: Budget Remaining
  Remaining = Budget_total - Total_burned = _______phút
  Remaining % = Remaining / Budget_total × 100 = _______%

STEP 4: Decision
  [ ] > 50% remaining → Deploy bình thường
  [ ] 20-50% remaining → Deploy với SRE review
  [ ] 10-20% remaining → Defer non-critical deploys
  [ ] < 10% remaining → Feature freeze
  [ ] < 0% remaining  → Incident mode, no new features

STEP 5: Next Month Targets
  If > 50% remaining this month: Can tighten SLO
  If < 20% remaining this month: Consider reliability sprint
  If 0% remaining (SLO breach): Mandatory post-mortem + roadmap change
```

---

## 7. Alert Fatigue Reduction Checklist

Dùng checklist này để đánh giá alert hiện có và alert mới.

### 7.1 Alert Health Check (Weekly Review)

```
Cho mỗi alert rule, trả lời:

ACTIONABILITY:
  [ ] On-call biết chính xác phải làm gì trong 5 phút đầu
  [ ] Alert có link runbook cụ thể và runbook được cập nhật < 90 ngày
  [ ] Alert có owner team label khớp với on-call rotation

SIGNAL QUALITY:
  [ ] Alert đo user impact (không phải chỉ infrastructure symptom)
  [ ] False positive rate < 5% trong 30 ngày qua
  [ ] Alert không overlap với alert khác cho cùng incident

THRESHOLD:
  [ ] Threshold được review dựa trên historical data (không phải "best guess")
  [ ] `for:` duration đủ dài để tránh transient spike (≥ 2m cho PAGE)
  [ ] Multi-window được dùng cho SLO-based alerts

SEVERITY:
  [ ] PAGE chỉ khi cần human response ngay (< 5 phút)
  [ ] TICKET cho issues cần attention nhưng không khẩn cấp
  [ ] INFO/WARNING không page, chỉ appear trên dashboard

CLEANUP:
  [ ] Alert đã không fire trong 60 ngày → review (có cần không?)
  [ ] Alert fire nhưng không có action taken → tune hoặc delete
```

### 7.2 Alert Triage Decision Tree

```
Alert triggered. Hỏi theo thứ tự:

1. Có liên quan đến user impact không?
   NO → Xuống severity hoặc delete
   YES → tiếp tục

2. Có needs IMMEDIATE human action không?
   NO → TICKET hoặc INFO
   YES → tiếp tục → PAGE

3. On-call biết làm gì không?
   NO → Viết runbook trước khi enable
   YES → tiếp tục

4. False positive rate < 5%?
   NO → Tune threshold/window, re-evaluate sau 2 tuần
   YES → Alert rule này OK
```

---

## 8. Error Budget Policy Template

```markdown
# Error Budget Policy — [Service Name]

Last reviewed: [DATE]
Owner: [TEAM NAME]
Service: [SERVICE NAME]
SLO: [X.XX%] availability, [Y.YY%] latency P99

## Tiêu chí

### Trạng thái HEALTHY (Budget > 50%)
- Deploy pipeline hoạt động bình thường
- Không có review bổ sung cho feature deploy
- Team có thể experiment và ship nhanh

### Trạng thái CAUTION (Budget 20-50%)
- Tất cả deploy cần SRE review và sign-off
- Không deploy breaking changes hoặc large refactor
- Daily budget check trong standup

### Trạng thái AT RISK (Budget 10-20%)
- Feature freeze: chỉ ship critical bug fixes
- SRE cần approve mọi change đến production
- Mandatory reliability review meeting trong tuần
- Escalate đến Engineering Manager

### Trạng thái EXHAUSTED (Budget < 10%)
- Full feature freeze: zero new features
- Engineering leadership được notify
- Reliability sprint bắt đầu
- Weekly progress report đến VP Engineering

### Trạng thái BREACHED (Budget ≤ 0%)
- SLO đã bị vi phạm
- Bắt buộc incident post-mortem trong 1 tuần
- Reliability roadmap được update với priority fixes
- Customer communication nếu SLA bị ảnh hưởng
- Không deploy mới cho đến khi VP Engineering approval

## Exceptions
Các trường hợp cho phép deploy dù budget thấp:
- Security patch với CVE score > 9.0
- Data loss risk fixes
- Regulatory compliance deadline

Mọi exception cần: Engineering Manager approval + documented justification
```

---

## 9. SLI Selection Guide

### Bước 1: Identify "Happy User"

```
Câu hỏi cần trả lời:
  - User đang cố làm gì? (checkout, search, login, upload file)
  - Điều gì khiến user unhappy? (timeout, error, sai data, chậm)
  - User có alternative khi service fail không? (fallback, retry)
```

### Bước 2: Map to Measurable Metric

```
User action → SLI category → Metric

User checkout thành công     → Availability    → 2xx rate on POST /checkout
User thấy kết quả search     → Latency         → P99 < 1s on GET /search
Order data đúng              → Correctness      → valid_orders / total_orders
Dashboard có data mới nhất   → Freshness        → age(last_update) < 1h
System phục vụ đủ load       → Throughput       → req/s > threshold
File không bị mất            → Durability       → (stored - lost) / stored
```

### Bước 3: Chọn điểm đo

```
Priority (cao → thấp):
  1. Client-side (real user monitoring) — phản ánh trải nghiệm thực nhất
  2. Load balancer / API gateway — gần client nhất, exclude internal issues
  3. Service ingress — bỏ qua network issues ngoài service
  4. Application metrics — internal, có thể miss external failures

Tránh: Internal metrics xa với user (database query time, CPU, memory)
```

### Bước 4: Đặt Target

```
Phương pháp đặt SLO target:
  Option A (Data-driven):
    → Đo 30-60 ngày lịch sử
    → SLO = current_performance_P90 (chặt vừa phải)
    
  Option B (Business-driven):
    → PM/Business define: "User tolerance = max 500ms"
    → Engineering đánh giá feasibility
    → Negotiate về timeline để đạt target
    
  Option C (Competitive-driven):
    → Research competitor SLAs
    → Match hoặc exceed trên metric quan trọng nhất

Quy tắc: SLO phải achievable với current architecture.
         Nếu không achievable → đây là gap cần address, không phải bỏ qua.
```

---

## 10. Toil Tracking Template

```
=== TOIL LOG (Weekly) ===
Team: _______________________
Week: ___/___/______

| Task | Duration | Type | Automatable? | Priority |
|------|----------|------|--------------|----------|
| Restart service X | 15 min | Manual | Yes | High |
| Review noise alerts | 45 min | Repetitive | Yes | Very High |
| Deploy approval form | 20 min/deploy × 3 | Repetitive | Yes | High |
| ... | | | | |

Total toil this week: _____ giờ
Total work hours: _____ giờ
Toil percentage: _____%

TOP TOIL TO ELIMINATE NEXT SPRINT:
1. [Task]: ______________ | Expected savings: ____h/month
2. [Task]: ______________ | Expected savings: ____h/month

=== TOIL TARGETS ===
Current month toil%: _____%
Target: < 30%
Trend: ↑ / ↓ / → (circle one)
```

---

## 11. Grafana Dashboard Panels cho SLO

```
Panel 1: SLO Status (Stat panel)
  Query: slo:sli_error_rate:ratio_rate1h / 0.001
  Thresholds: < 1 = green, 1-6 = yellow, 6-14.4 = orange, > 14.4 = red
  Unit: short (burn rate multiplier)
  Title: "Current Burn Rate"

Panel 2: Error Budget Remaining (Gauge panel)
  Query: (1 - slo:sli_error_rate:ratio_rate30d / 0.001) * 100
  Min: 0, Max: 100
  Thresholds: 0-10 = red, 10-25 = orange, 25-50 = yellow, 50-100 = green
  Unit: percent
  Title: "Error Budget Remaining (30d)"

Panel 3: Error Rate Over Time (Time series)
  Query A: 1 - slo:sli_error_rate:ratio_rate5m   (label: "5m avg")
  Query B: 1 - slo:sli_error_rate:ratio_rate1h    (label: "1h avg")
  Query C: 1 - slo:sli_error_rate:ratio_rate1d    (label: "1d avg")
  Reference line: SLO threshold
  Title: "Error Rate vs SLO Threshold"

Panel 4: Burn Rate History (Time series)
  Query: slo:sli_error_rate:ratio_rate1h / 0.001
  Threshold annotations: 6x (ticket), 14.4x (page)
  Fill below threshold lines
  Title: "Burn Rate (1h window)"

Panel 5: P99 Latency (Time series)
  Query: histogram_quantile(0.99, sum by(le) (rate(http_request_duration_seconds_bucket[5m])))
  Reference line: latency SLO threshold (e.g., 0.5s)
  Title: "P99 Latency vs SLO"

Panel 6: Budget Burn Chart (Time series / Bar chart)
  Show daily error budget consumed this month
  Cumulative line overlay
  Title: "Error Budget Consumption This Month"
```

---

## 12. Quick Reference: SLO Anti-Patterns

| Anti-Pattern | Triệu chứng | Fix |
|---|---|---|
| **SLO Theater** | SLO define xong không ai dùng | Error budget policy có teeth — meeting với leadership |
| **Vanity SLO** | SLO = 99.999% nhưng not achievable | Measure actual, set SLO = P90 historical |
| **Alert Everything** | > 100 rules cho 1 service | Keep only SLO-based alerts, delete symptom alerts |
| **Alert Blindness** | On-call ignores alerts | Reduce to < 20 rules, ensure 100% actionable |
| **Wrong SLI** | "Uptime" based on ping check | Measure at load balancer, use request-based SLI |
| **No Team Buy-in** | PM deploys without checking budget | Weekly budget review in team meeting |
| **SLO silos** | Each team has SLO, no end-to-end | Add composite / journey SLO |
| **Static thresholds** | Alert thresholds set once, never reviewed | Monthly alert audit |

---

## 13. Cheatsheet: Sloth (SLO-as-Code)

```yaml
# Sloth generates Prometheus recording rules + alerts từ YAML đơn giản
# Install: https://sloth.dev

# example-slo.yaml
version: prometheus/v1
service: checkout-api
labels:
  team: payment
  env: production

slos:
  - name: availability
    objective: 99.9
    description: "Checkout API availability"
    sli:
      events:
        error_query: sum(rate(http_requests_total{service="checkout-api", code=~"5.."}[{{.window}}]))
        total_query: sum(rate(http_requests_total{service="checkout-api"}[{{.window}}]))
    alerting:
      name: CheckoutAPIAvailability
      page_alert:
        labels:
          severity: page
      ticket_alert:
        labels:
          severity: ticket

# Generate rules:
sloth generate -i example-slo.yaml -o generated-rules.yaml

# Apply:
kubectl apply -f generated-rules.yaml
```

---

*Bài tiếp theo: Day 44 — Incident Response & Postmortem*

