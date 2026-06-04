# Day 40: Document — Dashboard Design Checklist, Alert Templates & Runbook

## 1. Dashboard Design Checklist

### Pre-build Checklist

- [ ] **Audience xác định**: Executive, Engineer, hoặc On-call?
- [ ] **Câu hỏi chính**: Dashboard trả lời câu hỏi gì? (1 câu duy nhất)
- [ ] **Data sources**: Metrics từ đâu? (Prometheus, Loki, Tempo)
- [ ] **Time range mặc định**: 1h (service), 24h (executive), 15m (debug)?
- [ ] **Refresh interval**: 30s (service), 5min (executive), 10s (debug)?

### Layout Checklist

- [ ] **Row 1**: Stat panels — glanceable status (3-4 panels max)
- [ ] **Row 2**: Time series — trends (2-3 panels)
- [ ] **Row 3**: Details — per-endpoint, per-instance (collapsible)
- [ ] **Tổng panels**: ≤ 15 (target: 8-12)
- [ ] **Color thresholds**: Green/Yellow/Red consistent
- [ ] **Units đúng**: reqps, percent, seconds, bytes
- [ ] **Legend rõ ràng**: Meaningful names, không phải raw metric names

### Content Checklist (RED Metrics)

- [ ] **Rate**: RPS total, RPS by endpoint, RPS by status code
- [ ] **Errors**: Error rate %, error count, error by type
- [ ] **Duration**: p50, p90, p99 latency, average latency
- [ ] **Saturation** (nếu cần): CPU, memory, connections, queue depth

### Interactivity Checklist

- [ ] **Variables**: $service, $environment, $instance (nếu multi-service)
- [ ] **Drill-down links**: Executive → Service → Debug
- [ ] **Annotations**: Deployment markers (manual hoặc automatic)
- [ ] **Links**: Log explorer, trace viewer, runbook

### Maintenance Checklist

- [ ] **Dashboard exported as JSON** và stored trong git
- [ ] **Provisioning configured** (auto-load từ files)
- [ ] **Owner assigned** (ai maintain dashboard này?)
- [ ] **Review quarterly** (delete outdated panels, add new services)

---

## 2. Alert Rule Templates

### Template: Service Error Rate

```yaml
Alert Name: {Service}HighErrorRate
Query: |
  sum(rate(http_requests_total{service="$SERVICE",status=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{service="$SERVICE"}[5m]))
Condition: IS ABOVE 0.05 (5%)
For: 2m
Labels:
  severity: warning
  service: $SERVICE
  team: $TEAM
Annotations:
  summary: "High error rate {{ $value | humanizePercentage }} on {{ $labels.service }}"
  description: "Service {{ $labels.service }} has error rate above 5% for more than 2 minutes"
  runbook_url: "https://wiki.example.com/runbooks/high-error-rate"
  dashboard_url: "https://grafana.example.com/d/service-health?var-service={{ $labels.service }}"
```

### Template: Service High Latency

```yaml
Alert Name: {Service}HighLatency
Query: |
  histogram_quantile(0.99,
    sum(rate(http_request_duration_seconds_bucket{service="$SERVICE"}[5m])) by (le)
  )
Condition: IS ABOVE 1.0 (1 second)
For: 5m
Labels:
  severity: warning
  service: $SERVICE
Annotations:
  summary: "High p99 latency {{ $value | humanize }}s on {{ $labels.service }}"
  runbook_url: "https://wiki.example.com/runbooks/high-latency"
```

### Template: Service Down

```yaml
Alert Name: {Service}Down
Query: up{job="$SERVICE"}
Condition: IS BELOW 1
For: 1m
Labels:
  severity: critical
  service: $SERVICE
Annotations:
  summary: "{{ $labels.service }} is DOWN"
  runbook_url: "https://wiki.example.com/runbooks/service-down"
```

### Template: No Traffic (Possible Outage)

```yaml
Alert Name: {Service}NoTraffic
Query: |
  sum(rate(http_requests_total{service="$SERVICE"}[5m])) == 0
  AND
  sum(rate(http_requests_total{service="$SERVICE"}[1h])) > 0
Condition: IS ABOVE 0 (the AND result is true)
For: 3m
Labels:
  severity: critical
  service: $SERVICE
Annotations:
  summary: "No traffic on {{ $labels.service }} - was previously receiving traffic"
  runbook_url: "https://wiki.example.com/runbooks/no-traffic"
```

### Template: SLO Burn Rate (Fast)

```yaml
Alert Name: {Service}SLOFastBurn
Query: |
  (
    sum(rate(http_requests_total{service="$SERVICE",status=~"5.."}[1h]))
    /
    sum(rate(http_requests_total{service="$SERVICE"}[1h]))
  ) / (1 - $SLO_TARGET)
Condition: IS ABOVE 14.4
For: 5m
Labels:
  severity: critical
  service: $SERVICE
  alert_type: slo_burn
Annotations:
  summary: "SLO fast burn on {{ $labels.service }} - burn rate {{ $value }}x"
  description: "At this rate, error budget will be exhausted in less than 3 hours"
  runbook_url: "https://wiki.example.com/runbooks/slo-burn"
```

### Template: Disk Prediction

```yaml
Alert Name: DiskWillFull
Query: |
  predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 24*3600) < 0
Condition: IS BELOW 0
For: 15m
Labels:
  severity: warning
Annotations:
  summary: "Disk on {{ $labels.instance }} will be full in 24 hours"
  runbook_url: "https://wiki.example.com/runbooks/disk-full"
```

---

## 3. Runbook Template

```markdown
# Runbook: [Alert Name]

## Overview
- **Alert**: [Full alert name]
- **Severity**: Critical / Warning / Info
- **Service(s)**: [Affected services]
- **Dashboard**: [Link to Grafana dashboard]
- **Last updated**: [Date]
- **Owner**: [Team/Person]

## What This Alert Means
[1-2 sentences explaining what condition triggered this alert and why it matters]

## User Impact
- [What users experience when this fires]
- [Estimated revenue/business impact if known]

## Investigation Steps

### Step 1: Assess Scope
~~~
[Command or dashboard link to check scope]
~~~
- Is it one instance or all instances?
- Is it one endpoint or all endpoints?
- When did it start? (check timeline on dashboard)

### Step 2: Check Recent Changes
~~~
[Command to check recent deployments]
kubectl rollout history deployment/<service> -n <namespace>
~~~
- Was there a recent deployment?
- Was there a config change?
- Was there a dependency change?

### Step 3: Check Dependencies
~~~
[Commands to check upstream/downstream services]
curl -s http://<dependency>/health
kubectl get pods -l app=<dependency>
~~~
- Are all dependencies healthy?
- Any increased latency to dependencies?

### Step 4: Check Resources
~~~
kubectl top pods -l app=<service>
~~~
- CPU throttled?
- Memory pressure?
- Disk full?

### Step 5: Check Logs
~~~
kubectl logs -l app=<service> --tail=100 --since=5m | grep -i error
~~~
- What error messages appear?
- Any stack traces?
- Pattern: all instances or specific?

## Mitigation Actions

### If bad deployment:
~~~
kubectl argo rollouts abort <service>
# or
kubectl rollout undo deployment/<service>
~~~

### If resource issue:
~~~
kubectl scale deployment/<service> --replicas=&lt;n&gt;
~~~

### If dependency failure:
~~~
[Activate circuit breaker / fallback]
~~~

### If data issue:
~~~
[Database recovery steps]
~~~

## Escalation Path
| Time | Action |
|------|--------|
| 0-5 min | On-call investigates |
| 5-15 min | If not resolved, page team lead |
| 15-30 min | If critical + not resolved, page engineering manager |
| 30+ min | Incident Commander takes over |

## Post-Incident
1. Create incident ticket in [tool]
2. Write timeline of events
3. Schedule postmortem if P1/P2
4. Update this runbook if needed

## Common False Positives
- [Known scenario that triggers this alert but is not a real issue]
- [How to distinguish false positive from real issue]

## Related
- [Link to architecture diagram]
- [Link to dependent service runbooks]
- [Link to postmortems for this alert type]
```

---

## 4. Alert Severity Matrix

| Severity | Meaning | Notification | Response Time | Examples |
|----------|---------|-------------|---------------|---------|
| **Critical** | Service down or severely degraded, user impact | PagerDuty page | < 5 minutes | Service down, error rate > 20%, SLO fast burn |
| **Warning** | Degradation detected, may escalate | Slack channel | < 30 minutes | Error rate > 5%, high latency, slow burn |
| **Info** | Notable event, no action needed now | Slack (low-priority) | Next business day | Deployment completed, certificate expiring in 30d |

---

## 5. Dashboard Naming Convention

```
Format: {Scope} / {Service} - {Purpose}

Examples:
  Platform / Executive - Business Health
  Platform / All Services - Overview
  Service / Order Service - Health
  Service / Order Service - Debug
  Infrastructure / Kubernetes - Node Health
  Infrastructure / Prometheus - Self Monitoring
  SLO / Order Service - Error Budget
  Alerts / On-call - Active Alerts
```

---

## 6. Grafana Provisioning Quick Reference

### Data Source Provisioning

```yaml
# grafana/provisioning/datasources/datasources.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    editable: false
    jsonData:
      tracesToLogs:
        datasourceUid: loki
        tags: ['service']
```

### Dashboard Provisioning

```yaml
# grafana/provisioning/dashboards/dashboards.yml
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: 'Production'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
```

### Deployment Annotation API

```bash
# Add deployment annotation via API
curl -s -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -u admin:admin123 \
  -d '{
    "dashboardUID": "<dashboard-uid>",
    "time": '$(date +%s000)',
    "tags": ["deployment", "order-service"],
    "text": "Deployed order-service v1.2.3 (commit abc123)"
  }'
```

