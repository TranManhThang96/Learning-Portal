# Day 27 — Exercises & Challenges

**Required**: Hoan thanh Day 27 lesson + lab
**Mode**: Work solo hoac pair, 90-120 phut
**Submit**: Pull request voi markdown file trong `exercises/day-27/`

---

## Challenge 1: Alert Rule Design

**Context**: Platform có 5 service: `api-gateway`, `auth-service`, `order-service`, `notification-service`, `report-worker`.

**Task**: Thiet ke PrometheusRule voi 4 alert.

| Alert | Metric | Condition | For | Severity | Team |
|-------|--------|-----------|-----|----------|------|
| `ServiceSyncFailureRate` | Synced app rate | < 80% synced | 10m | ? | platform |
| `DriftDetected` | Out-of-sync apps | > 0 out-of-sync on prod | 5m | ? | platform |
| `ControllerSaturation` | Reconciliation latency | p95 > 60s | 10m | ? | sre |
| `GitOperationSlow` | Git request duration | p99 > 30s | 15m | ? | platform |

**Deliverable**: File `alerts-platform.yaml` voi day du PrometheusRule YAML.

**Constraints**:
- Alert chi fire khi `app.metadata.labels.env == "production"`
- SRE alert route den PagerDuty (annotations)
- Platform alert route den Slack `#platform-alerts`
- Khong hardcode team name

---

## Challenge 2: Notification Routing Per Team

**Context**: 3 team, 4 severity level.

| Team | Services | On-call |
|------|----------|---------|
| platform-team | api-gateway, order-service | Slack #platform-oncall |
| backend-team | auth-service | Slack #backend-alerts |
| data-team | notification-service, report-worker | Slack #data-alerts |

**Severity matrix**:

| Severity | Condition | Action |
|----------|-----------|--------|
| P0 | `app.status.operationState.phase in [Failed, Error]` + prod | PagerDuty + Slack #incidents |
| P1 | `app.status.health.status == Degraded` + prod | Slack team channel |
| P2 | `app.status.status == OutOfSync` + prod | Slack team channel (digest) |
| P3 | dev env any issue | Email daily digest |

**Task**: Viet `notification-routing.yaml` bao gom:
- 3 subscription block (platform/backend/data)
- 4 template (p0-critical, p1-warning, p2-info, p3-digest)
- Service definitions (webhook hoac Slack)
- 4 trigger voi CEL filter phan biet P0/P1/P2/P3

**Bonus**: Thiet ke suppression logic: P0 alert suppressed during maintenance window (annotation `maintenance-window`).

---

## Challenge 3: DR Exercise — Full Cluster Loss

**Scenario**: Toan bo Kubernetes cluster mat (hardware failure). Recovery tu Git + ArgoCD trong < 30 phut.

**Setup**:
```
Services: api-gateway (Helm), auth-service (Kustomize), order-service (Helm)
Database: PostgreSQL (RDS, 15-min snapshot)
Cache: Redis (ElastiCache)
Registry: ECR
Git repo: https://github.com/org/platform-gitops
```

**Task**: Hoan thanh DR runbook trong file `dr-runbook.md`.

**Runbook sections required**:

```
## Pre-conditions
- [ ] Backup co san: argocd backup + RDS snapshot + ECR image tags documented
- [ ] Git repo public/accessible
- [ ] New cluster co the provision duoi 15 phut (Terraform ready)

## Recovery Steps
1. Provision new cluster (target: < 15 min)
2. Install ArgoCD (target: < 5 min)
3. Restore ArgoCD config (target: < 5 min)
4. Sync from Git (target: < 10 min)
5. Verify workload (target: < 5 min)

## Post-recovery
- [ ] Health check 10 endpoint
- [ ] DNS cutover
- [ ] Monitor error rate 1 hour

## RTO measurement
- Time to first successful request: ___
- Time to full recovery: ___
- RTO target: 30 min
- Met?: YES/NO

## Lessons learned
- [ ]
```

**Constraints**:
- Khong su dung Velero (khong co cluster-level backup)
- DB tu snapshot = RPO 15 min
- GitOps-only cho workload

---

## Challenge 4: Backup Secret Strategy with Sealed Secrets (Day 25 Reference)

**Scenario**: Day 25 da setup Sealed Secrets. Seal key (cluster public/private key) mat. Khong co backup cua seal key.

**Context**:
- 47 SealedSecret CRD trong cluster
- ESO chua duoc setup (Day 25 lab only used fake provider)
- Backup strategy: `argocd admin export` chay nightly, luu S3

**Task**: Hoan thanh `sealed-secret-dr.md`.

**Sections**:

```
## Problem Statement
Mat seal key = mat kha nang giai ma bat ky SealedSecret nao.
47 secret can duoc recovery.

## Immediate Response (0-30 min)
1. Assess: Xac dinh scope cua mat key
2. Contain: Disable argocd-notifications webhook (tranh alert)
3. Notify: SRE + Security team

## Recovery Options
Option A: Generate new sealing key pair
  Pros: ...
  Cons: ...
  RTO: ...

Option B: Migration sang ESO + AWS Secrets Manager
  Pros: ...
  Cons: ...
  RTO: ...

## Recommended Path
Chon option nao? Tai sao?

## Recovery Steps (document day buoc)
1. ...
2. ...
3. ...

## Prevention ( Lessons Learned)
- [ ] Seal key backup strategy
- [ ] Rotation cadence
- [ ] Monitoring for key expiry
```

---

## Challenge 5: Multi-Cluster Observability

**Scenario**: 4 cluster ArgoCD federated (hub-and-spoke).

| Cluster | Role | Apps |
|---------|------|------|
| hub-prod | ArgoCD Hub, central monitoring | 2 (management only) |
| spoke-prod-us | Production US | 15 |
| spoke-prod-eu | Production EU | 12 |
| spoke-staging | Staging | 8 |

**Task**: Thiet ke `multi-cluster-observability.md`.

**Sections**:

```
## Architecture Options

Option A: Centralized Prometheus
  - Single Prometheus instance scrape all 4 cluster
  - Challenge: network latency, auth across cluster
  - Solution: ...

Option B: Prometheus Federation
  - 1 central Prometheus aggregates from 4 cluster Prometheus
  - Prometheus per cluster scrape local ArgoCD
  - Federation API exposes aggregated metrics
  - Design: ...

Option C: Thanos Sidecar (recommended)
  - Each cluster Prometheus + Thanos sidecar
  - Global view in Grafana
  - Object storage (S3) for long-term retention
  - Design: ...

## Recommended Design
Chon + giai thich

## Grafana Single-Pane Setup
Dashboard requirements:
- View all 4 cluster health on 1 screen
- Per-cluster drill-down
- Alert source (which cluster fired)
- Query federation / multicluster namespace

## Alert Routing
- Regional alert: spoke-prod-eu issue → Slack #europe-alerts
- Hub alert: ArgoCD Hub issue → PagerDuty SRE
- Cross-cluster alert: > 50% clusters unhealthy → #incidents

## Grafana Dashboard YAML
Thiet ke dashboard provisioning (ConfigMap)
```

**Constraints**:
- Hub Prometheus khong co RBAC toi spoke cluster
- EU cluster co GDPR data — metrics co the chua PII?

---

## Challenge 6: Incident Postmortem Template

**Scenario**: Refactor `postmortem-template.md` for ArgoCD-related incidents.

**Template sections**:

```
# Incident Postmortem — [TITLE]
Date: YYYY-MM-DD
Duration: X hours Y minutes
Severity: P0/P1/P2/P3
Team: [TEAM]
Status: [Draft / Final]

## Summary (3-5 sentences)
...

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired |
| HH:MM | On-call engaged |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Resolution |

## Root Cause Analysis
...

## Impact
- Users affected: X
- Revenue impact: $Y
- SLA breach: YES/NO

## Detection
- How detected: [Alert / User report / Internal]
- Detection time: HH:MM
- Time to detect (TTD): X min

## Response
- Time to acknowledge (TTA): X min
- Time to resolve (TTR): X min
- Steps taken: ...

## Lessons Learned
### What went well
1. ...
### What went poorly
1. ...
### Action items
| Action | Owner | Due |
|--------|-------|-----|
| Add alert for X | @sre | YYYY-MM-DD |
| Test backup restore | @platform | YYYY-MM-DD |

## Related Incidents
...
```

---

## Bonus: GameDay Scenarios

### GameDay 1: Metric Pipeline Failure

**Scenario**: Prometheus Operator upgrade fails. ArgoCD metrics unavailable.

**Tasks**:
1. Confirm symptoms: Grafana panels blank, Prometheus targets DOWN
2. Isolate: ArgoCD app sync van hoat dong binh thuong
3. Mitigate: Temporary `argocd admin export` backup
4. Restore: Rollback Prometheus Operator
5. Verify: Dashboard populated, alerts firing
6. Document: Update runbook

### GameDay 2: Notification Spam

**Scenario**: Alert fatigue. 500 Slack messages trong 10 phut. On-call muted channel.

**Tasks**:
1. Audit: `argocd_app_sync_total{result="Failed"}` moi 30s → alert condition `increase() > 0` (wrong)
2. Root cause: Alert fires moi lan sync fail, khong co `for`
3. Fix: Cap nhat PrometheusRule `for: 5m`
4. Suppress: Silence for 1h
5. Verify: Slient alert stop, real failure van fire
6. Process change: Alert review before deploy

### GameDay 3: Backup Restore Under Time Pressure

**Scenario**: ArgoCD lost. Backup co san nhung restore that bai 3 lan.

**Tasks**:
1. Diagnose: `argocd admin import` fail vi CRD chua khoi tao
2. Fix: Tao CRD truoc, sau do import
3. Alternative: GitOps-only path — re-apply root app
4. Time check: Neu < 15 min, GitOps-only
5. Post-mortem: Tai sao backup restore khong test truoc

---

## Submission

```
exercises/day-27/
  ├── challenge-1-alerts-platform.yaml   # PrometheusRule
  ├── challenge-2-notification-routing.yaml
  ├── challenge-3-dr-runbook.md
  ├── challenge-4-sealed-secret-dr.md
  ├── challenge-5-multi-cluster-observability.md
  ├── challenge-6-postmortem-template.md
  └── bonus-gameday.md                   # (optional)
```

Submit via pull request to `platform-repo/exercises/day-27/`.
