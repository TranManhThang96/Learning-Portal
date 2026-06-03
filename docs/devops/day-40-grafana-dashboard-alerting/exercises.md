# Day 40: Exercises — Grafana Dashboard & Alerting

## Bài 1: RED Metrics Dashboard (Easy)

### Context
Bạn vừa được giao tạo dashboard đầu tiên cho team. Hiện tại team chỉ dùng `kubectl logs` và `curl` để check service health. Manager muốn: "Tôi cần nhìn 1 màn hình biết service có OK không."

### Yêu cầu
1. Deploy Grafana + Prometheus + sample app bằng Docker Compose.
2. Cấu hình Prometheus data source trong Grafana.
3. Tạo dashboard "Service Health" với 6 panels:
   - **Row 1 (Stat panels)**: Current RPS, Current Error Rate (%), Current p99 Latency.
   - **Row 2 (Time Series)**: RPS over time (by status code), Latency percentiles (p50/p90/p99).
   - **Row 3 (Time Series)**: Error rate over time với threshold line ở 5%.
4. Thêm color thresholds cho stat panels:
   - RPS: red (0), yellow (1), green (10+).
   - Error rate: green (0-1%), yellow (1-5%), red (5%+).
   - p99: green (0-300ms), yellow (300ms-1s), red (1s+).
5. Export dashboard JSON và save vào file.

### Expected Outcome
- Dashboard hiển thị real-time service metrics.
- Stat panels thay đổi màu theo thresholds.
- Time series graphs hiển thị trends.
- Dashboard JSON file có thể import lại vào Grafana mới.

### Hint
- Grafana default login: admin/admin.
- Data source URL trong Docker: `http://prometheus:9090` (service name, không phải localhost).
- Stat panel: `Visualization → Stat`, set unit (reqps, percent, seconds).
- Export: Dashboard settings → JSON Model → Copy.
- Generate traffic: `while true; do curl -s localhost:8080/; sleep 0.2; done &`

### Acceptance Criteria
- [ ] Grafana chạy và accessible.
- [ ] Prometheus data source connected (green).
- [ ] 6 panels hiển thị data.
- [ ] Stat panels có color thresholds.
- [ ] Time series graphs có đúng legend.
- [ ] Dashboard JSON exported thành công.
- [ ] Import JSON vào Grafana mới → dashboard hoạt động.

### Bonus Challenge
- Thêm template variable `$job` để filter theo service.
- Thêm annotation cho deployments (manual annotation).
- Thêm panel "Top 5 endpoints by RPS" (bar gauge).

---

## Bài 2: Alert Rules & Notification (Medium)

### Context
Team đã có dashboard (Bài 1) nhưng vẫn phải ngồi nhìn dashboard để phát hiện issue. Tuần trước, error rate tăng 20% lúc 2AM nhưng không ai biết cho đến sáng hôm sau (8 giờ delay). Manager yêu cầu: "Tôi cần alert gửi vào Slack khi có vấn đề."

### Yêu cầu

**Part A: Alert Rules**
1. Tạo 4 alert rules trong Grafana:
   - **HighErrorRate**: Error rate > 5% sustained 2 phút → severity: warning.
   - **CriticalErrorRate**: Error rate > 20% sustained 1 phút → severity: critical.
   - **HighLatency**: p99 latency > 1 second sustained 5 phút → severity: warning.
   - **NoTraffic**: RPS = 0 sustained 3 phút (service có thể down) → severity: critical.
2. Mỗi alert phải có:
   - Labels: severity, service.
   - Annotations: summary (mô tả ngắn), description (chi tiết), runbook_url.

**Part B: Notification**
3. Tạo contact point (Webhook hoặc Slack):
   - Dùng webhook.site hoặc requestbin.com nếu không có Slack.
   - Hoặc cấu hình Slack webhook nếu có.
4. Tạo notification policy:
   - Critical → contact point "DevOps On-call".
   - Warning → contact point "DevOps Channel".
5. Test: trigger alert bằng cách tạo high error rate.

**Part C: Silence & Maintenance**
6. Tạo silence cho 1 alert (simulate maintenance window).
7. Verify alert không fire trong silence period.

### Expected Outcome
- 4 alert rules hiển thị trên Alerting → Alert rules.
- Alert fires khi condition met.
- Notification gửi đến contact point.
- Silence hoạt động đúng.

### Hint
- Grafana Alerting: Alerting → Alert rules → New alert rule.
- Query A: PromQL expression. Condition: `IS ABOVE <threshold>`.
- Contact point webhook test: https://webhook.site (free, one-time URL).
- Trigger high error rate: `for i in $(seq 1 1000); do curl -s localhost:8080/err; done`.
- Silence: Alerting → Silences → New silence.

### Acceptance Criteria
- [ ] 4 alert rules created with correct conditions.
- [ ] Each alert has labels (severity, service) và annotations (summary, runbook_url).
- [ ] Contact point configured và tested.
- [ ] Notification policy routes by severity.
- [ ] Alert fires khi condition met (test bằng synthetic traffic).
- [ ] Silence created và prevents alert notification.
- [ ] Alert resolves khi condition clears.

### Bonus Challenge
- Thêm escalation: nếu critical alert không ack trong 10 phút → escalate to manager.
- Tạo "Alert List" panel trên dashboard hiển thị current firing alerts.
- Implement mute timing: no alerts between 00:00-06:00 cho non-critical.
- Compare: cùng alert rule trong Grafana vs trong Prometheus AlertManager → trade-offs.

---

## Bài 3: Production-Grade Observability Dashboard Suite (Hard)

### Context
Bạn là SRE Lead. Company vừa migrate lên microservices (5 services). CEO, CTO, và engineering team đều phàn nàn:
- CEO: "Tôi muốn biết platform có healthy không trong 5 giây."
- CTO: "Tôi cần SLO compliance report hàng tuần."
- Engineers: "Khi có incident, tôi mất 30 phút tìm service nào lỗi."
- On-call: "Alert quá nhiều, 50 alerts/ngày, không biết cái nào quan trọng."

### Yêu cầu

**Part A: Dashboard Suite Design**
1. Thiết kế và tạo 3 dashboards:
   - **Executive Dashboard**: Platform availability (%), total RPS, total error rate, incident count, SLO compliance.
   - **Service Dashboard**: RED metrics per service, dependencies status, deployment annotations. Template variable `$service` để filter.
   - **Debug Dashboard**: Detailed metrics per endpoint, per instance. Latency heatmap. Log panel (nếu có Loki).
2. Mỗi dashboard phải follow design principles: hierarchy, glanceable, actionable.
3. Drill-down links: Executive → Service → Debug.

**Part B: SLO-based Alerting**
4. Define SLO cho sample service: 99.9% availability (monthly).
5. Calculate error budget: 0.1% = 43.2 minutes/month.
6. Tạo burn rate alerts:
   - Fast burn: burn rate > 14.4x cho 1h → PAGE.
   - Slow burn: burn rate > 6x cho 6h → TICKET.
   - Budget consumption > 50% → WARNING.
7. Tạo SLO dashboard panel hiển thị: remaining error budget, burn rate, SLO compliance.

**Part C: Alert Hygiene**
8. Viết "Alert Review Checklist" — quy trình review alerts hàng quý.
9. Tạo "Alert Quality Dashboard" tracking:
   - Alerts fired per day per service.
   - Time-to-acknowledge.
   - False positive rate (resolved < 5 phút = likely false positive).
10. Viết "On-call Runbook Template" cho top 3 alert types.

**Part D: Dashboard as Code**
11. Export tất cả dashboards dưới JSON.
12. Cấu hình Grafana provisioning để auto-load dashboards từ files.
13. Version control dashboard JSON trong git.
14. Viết script recreate toàn bộ Grafana setup từ scratch.

### Expected Outcome
- 3 dashboards với drill-down links.
- SLO-based alerts thay thế threshold-based.
- Alert hygiene process documented.
- Dashboard as code: recreate từ git trong 5 phút.

### Hint
- Executive dashboard dùng stat panels + bar gauge (SLO per service).
- Service dashboard dùng variable `$service` trong queries: `{service="$service"}`.
- Drill-down link: Panel → Links → Add link → `d/<dashboard-uid>?var-service=$service`.
- Burn rate PromQL:
  ```promql
  (sum(rate(http_requests_total{status=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))) / 0.001
  ```
- Grafana provisioning: mount YAML + JSON vào `/etc/grafana/provisioning/`.
- Alert quality: query Grafana API `/api/v1/provisioning/alert-rules` + `/api/annotations`.

### Acceptance Criteria
- [ ] 3 dashboards created (Executive, Service, Debug).
- [ ] Drill-down links work: Executive → Service → Debug.
- [ ] Template variables ($service) filter correctly.
- [ ] SLO burn rate alerts defined (fast burn, slow burn).
- [ ] SLO dashboard panel shows error budget remaining.
- [ ] Alert Review Checklist has ≥ 5 items.
- [ ] On-call runbook template completed for 3 alert types.
- [ ] Dashboard JSON exported and version controlled.
- [ ] Grafana provisioning config works (fresh Grafana loads dashboards).
- [ ] Cleanup script removes everything.

### Bonus Challenge
- Implement "deployment annotation" tự động: GitHub Actions gọi Grafana API add annotation khi deploy.
- Tạo "Cost Dashboard" (ước tính): metrics volume, storage usage, query load.
- Implement Grafana RBAC: CEO chỉ thấy Executive dashboard, engineer thấy tất cả.
- Tạo weekly SLO compliance report tự động (Grafana reporting hoặc script).
- Compare Grafana Alerting vs Prometheus AlertManager in production setup.

---

## Solutions

<details>
<summary>Solution Bài 1: RED Dashboard</summary>

```bash
# Setup
mkdir -p /tmp/grafana-ex1 && cd /tmp/grafana-ex1
mkdir -p grafana/provisioning/datasources

# docker-compose.yml (same as lesson hands-on)
# prometheus.yml (same as lesson)
# grafana/provisioning/datasources/prometheus.yml (same as lesson)

docker compose up -d
sleep 15

# Generate traffic
while true; do
  curl -s localhost:8080/ > /dev/null 2>&1
  curl -s localhost:8080/err > /dev/null 2>&1
  sleep 0.2
done &

# Open Grafana: http://localhost:3000 (admin/admin)
# 1. Verify data source: Configuration → Data Sources → Prometheus → Test
# 2. Create dashboard: + → Dashboard → Add panel
# 3. Create 6 panels with queries from lesson
# 4. Export: Dashboard Settings → JSON Model → Copy → Save to file

# Cleanup
docker compose down -v
```

### Panel Queries Reference

```
Panel 1 - Current RPS (Stat):
  Query: sum(rate(http_requests_total{job="app"}[5m]))
  Unit: reqps

Panel 2 - Error Rate (Stat):
  Query: sum(rate(http_requests_total{job="app",code=~"5.."}[5m])) / sum(rate(http_requests_total{job="app"}[5m])) * 100
  Unit: percent

Panel 3 - p99 Latency (Stat):
  Query: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="app"}[5m])) by (le))
  Unit: seconds

Panel 4 - RPS Over Time (Time Series):
  Query: sum(rate(http_requests_total{job="app"}[5m])) by (code)
  Legend: {{code}}

Panel 5 - Latency Percentiles (Time Series):
  Query A: histogram_quantile(0.50, ...) Legend: p50
  Query B: histogram_quantile(0.90, ...) Legend: p90
  Query C: histogram_quantile(0.99, ...) Legend: p99

Panel 6 - Error Rate Over Time (Time Series):
  Query: error rate formula * 100
  Threshold line at 5%
```

</details>

<details>
<summary>Solution Bài 2: Alert Rules (Key Config)</summary>

### Alert Rules via Grafana API (provisioning)

```yaml
# grafana/provisioning/alerting/alerts.yml
apiVersion: 1

groups:
  - orgId: 1
    name: service_alerts
    folder: alerts
    interval: 1m
    rules:
      - uid: high-error-rate
        title: HighErrorRate
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: >
                sum(rate(http_requests_total{job="app",code=~"5.."}[5m]))
                /
                sum(rate(http_requests_total{job="app"}[5m]))
          - refId: C
            relativeTimeRange:
              from: 0
              to: 0
            datasourceUid: __expr__
            model:
              type: threshold
              expression: A
              conditions:
                - evaluator:
                    type: gt
                    params: [0.05]
        for: 2m
        labels:
          severity: warning
          service: app
        annotations:
          summary: "Error rate is high on app service"
          runbook_url: "https://wiki.example.com/runbooks/high-error-rate"
```

### Test Alert

```bash
# Generate errors to trigger alert
for i in $(seq 1 500); do
  curl -s http://localhost:8080/err > /dev/null 2>&1
  sleep 0.05
done

# Check alert status
curl -s -u admin:admin123 http://localhost:3000/api/v1/provisioning/alert-rules | jq '.[].title'

# Create silence (2 hours)
curl -s -u admin:admin123 -X POST http://localhost:3000/api/alertmanager/grafana/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [{"name": "service", "value": "app", "isRegex": false}],
    "startsAt": "2024-01-15T00:00:00Z",
    "endsAt": "2024-01-15T02:00:00Z",
    "createdBy": "admin",
    "comment": "Maintenance window"
  }'
```

</details>

<details>
<summary>Solution Bài 3: SLO Dashboard (Key Parts)</summary>

### SLO Burn Rate PromQL

```promql
# Error budget: 0.1% (SLO 99.9%)
# Burn rate = actual_error_rate / allowed_error_rate

# 1h burn rate (fast burn → page if > 14.4x)
(
  sum(rate(http_requests_total{status=~"5.."}[1h]))
  /
  sum(rate(http_requests_total[1h]))
) / 0.001

# 6h burn rate (slow burn → ticket if > 6x)
(
  sum(rate(http_requests_total{status=~"5.."}[6h]))
  /
  sum(rate(http_requests_total[6h]))
) / 0.001

# Error budget consumed this month (%)
(
  1 - (
    sum(increase(http_requests_total{status=~"2.."}[30d]))
    /
    sum(increase(http_requests_total[30d]))
  )
) / 0.001 * 100

# Remaining error budget (minutes)
43.2 * (1 - (
  sum(increase(http_requests_total{status=~"5.."}[30d]))
  /
  sum(increase(http_requests_total[30d]))
) / 0.001)
```

### Alert Review Checklist

```markdown
## Quarterly Alert Review Checklist

1. [ ] List all alert rules: how many total? New since last review?
2. [ ] Each alert has an owner? Delete ownerless alerts
3. [ ] Each alert fired in last 90 days? Delete never-fired alerts
4. [ ] Each alert has runbook link? Add missing runbooks
5. [ ] False positive rate per alert? Tune or delete > 50% false positive
6. [ ] Average alerts/day/engineer? Target: < 5
7. [ ] Time-to-acknowledge per severity? Critical < 5min, Warning < 30min
8. [ ] Any duplicate alerts? Consolidate
9. [ ] Severity levels appropriate? Recalibrate if needed
10. [ ] New services covered? Add alerts for new services
```

### On-call Runbook Template

```markdown
## Runbook: [Alert Name]

### Alert Details
- **Severity**: Critical / Warning
- **Service**: <service-name>
- **Condition**: <what triggers this alert>
- **Dashboard**: [link to relevant dashboard]

### Impact Assessment
- **User impact**: <what users experience>
- **Revenue impact**: <estimated if applicable>

### Investigation Steps
1. Check dashboard: [link]
2. Check recent deployments: [link to ArgoCD/CI]
3. Check dependencies: [query/command]
4. Check logs: `kubectl logs -l app=<service> --tail=100`
5. Check resource usage: [Grafana link]

### Mitigation
1. If bad deployment: `kubectl argo rollouts abort <name>`
2. If resource issue: `kubectl scale deployment <name> --replicas=<N>`
3. If dependency down: [circuit breaker / fallback procedure]

### Escalation
- If not resolved in 15 min: page <team-lead>
- If not resolved in 30 min: page <engineering-manager>

### Post-incident
- Create incident ticket
- Write timeline
- Schedule postmortem if P1/P2
```

</details>

