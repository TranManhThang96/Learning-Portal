# Day 27 — ArgoCD Observability, Notifications, Backup & Disaster Recovery

> **Neu ArgoCD sync fail ma khong ai biet, thi no khong fail — no chi im lang.**
> Neu backup chua tung test restore, thi no khong phai backup.

**Thoi luong:** 2 tieng (30 phut theory + 30 phut deep dive + 60 phut lab)
**Prerequisite:** Day 17 (ArgoCD core), Day 24 (sync waves), Day 25 (RBAC, secrets, SSO)
**Output:** Prometheus metrics tu ArgoCD, notification webhook, backup + restore, DR playbook

---

## 1. Muc tieu ngay hoc

- Expose ArgoCD metrics qua ServiceMonitor + Prometheus scrape
- Interpret 15+ key metrics: `argocd_app_info`, `argocd_app_sync_total`, `argocd_cluster_api_resource_objects`
- Cau hinh alert Prometheus voi `ArgoAppSyncFailed`, `ArgoAppNotHealthy`, `ArgoAppOutOfSync`
- Cau hinh argocd-notifications voi trigger `on-sync-failed`, `on-health-degraded` len webhook mock
- Backup toan bo ArgoCD config bang `argocd admin export` va restore bang `argocd admin import`
- Thiet ke DR strategy voi RPO/RTO target, khai thac GitOps-first pattern (everything in Git = no backup needed)

---

## 2. Boi canh thuc te

### 3 incident pattern khi khong co observability

| # | Incident | Hau qua |
|---|----------|---------|
| 1 | ArgoCD sync fail 3 tieng, developer khong biet, end-user 5xx | SLA breach, team blame game |
| 2 | Mat mayy chua ArgoCD, team khong co RTO target, restore 8 tieng | Business downtime |
| 3 | Backup khong test restore, luc can thi import that bai | Panic, data loss |

### Bieu hieu chung

- ArgoCD im lang khi sync fail → app degraded nhưng không ai alert
- Lost ArgoCD = lost desired-state mapping → team phải manual track lại toàn bộ app
- Backup tồn tại nhưng chưa từng restore thử → lúc cần thì fail
- Metrics có nhưng dashboard không ai nhìn → Grafana URL không ai bookmark

### Muc tieu Day 27

Observability + notification + backup la 3 layer cuối cùng de ArgoCD production-ready.

---

## 3. Kien thuc nen tang (~30 phut)

### 3.1 ArgoCD metrics overview

ArgoCD export metrics tai 3 endpoint:

```
argocd-server:8083/metrics         # API requests, login, SSO
argocd-application-controller:8082/metrics  # Sync, health, reconciliation
argocd-repo-server:8084/metrics    # Git/Helm/Kustomize render
notifications-controller:9001/metrics  # Notification dispatch (built-in)
```

**Metrics tu argocd-application-controller** (most important):

| Metric | Meaning |
|--------|---------|
| `argocd_app_info` | Application count + health/sync state |
| `argocd_app_sync_total` | Total sync attempts, labeled by result (succeeded/failed) |
| `argocd_app_reconcile` | Reconciliation count + duration histogram |
| `argocd_app_health` | Health status (healthy/degraded/missing) |
| `argocd_cluster_api_resource_objects` | Number of k8s objects per cluster (drift detection input) |
| `argocd_cluster_api_resources_count` | API discovery count |
| `argocd_redis_request_duration_seconds` | Redis latency (if external Redis) |
| `argocd_git_request_total` | Git operations count + result |
| `argocd_git_hardcoded_request_total` | Deprecated; ignore |

**Metrics tu argocd-server:**

| Metric | Meaning |
|--------|---------|
| `argocd_server_request_total` | HTTP requests by path + method + status |
| `argocd_server_cluster_api_request_count` | Cluster API calls from server |
| `argocd_login_total` | Login attempts by result |

### 3.2 Prometheus integration

**kube-prometheus-stack** (recommended): cai qua Helm hoac ArgoCD Application.

```yaml
# ServiceMonitor for argocd-application-controller
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-app-controller
  namespace: argocd
  labels:
    release: prometheus   # Must match prometheus operator selector
spec:
  endpoints:
  - port: metrics
    interval: 30s
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-application-controller
---
# ServiceMonitor for argocd-server
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-server
  namespace: argocd
  labels:
    release: prometheus
spec:
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-server
```

**Labels chuan**:
- ArgoCD pods use `app.kubernetes.io/name: argocd-server`, `app.kubernetes.io/component: server`
- kube-prometheus-stack selector: `release: prometheus` (hoac `app: prometheus` tuy version)

### 3.3 Grafana dashboards

- **Dashboard ID 14584**: "ArgoCD Overview" — app health, sync status, reconciliation rate
- **Dashboard ID 19974**: "ArgoCD Application Details" — per-app drill-down, sync history

Import bang `kubectl apply`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: grafana-dashboards
  namespace: argocd
spec:
  source:
    chart: grafana
    repoURL: https://grafana.github.io/helm-charts
    targetRevision: "7.x"
    helm:
      parameters:
      - name: dashboardProviders.default.path
        value: /var/lib/grafana/dashboards/default
      - name: dashboards.default.argocd-overview.source
        value: https://grafana.com/api/dashboards/14584/revisions/1/download
      - name: dashboards.default.argocd-details.source
        value: https://grafana.com/api/dashboards/19974/revisions/1/download
```

Hoac import truc tiep qua Grafana UI: Dashboards → Import → nhap `14584`.

### 3.4 argocd-notifications

**Architecture**:

```
ArgoCD event → notifications-controller → trigger (CEL filter) → template → service (webhook/email/slack)
```

**Trigger built-in** (partial list):

| Trigger | Condition |
|---------|-----------|
| `on-sync-running` | Sync started |
| `on-sync-succeeded` | Sync completed OK |
| `on-sync-failed` | Sync failed |
| `on-sync-status-unknown` | Sync status unknown > 5 min |
| `on-health-degraded` | Health != Healthy |
| `on-health-unknown` | Health unknown |
| `on-out-of-sync` | Spec != live state |
| `on-created` | Application created |
| `on-deleted` | Application deleted |

**Template example**:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
  namespace: argocd
data:
  service.webhook-mock: |
    url: https://webhook.site/<PLACEHOLDER_YOUR_ID>
  template.app-sync-failed: |
    message: |
      Sync FAILED for {{.app.metadata.name}}
      Namespace: {{.app.spec.destination.namespace}}
      Message: {{.app.status.operationState.phase}}
      ArgoCD: https://argocd.example.com/applications/{{.app.metadata.name}}
  trigger.on-sync-failed: |
    - when: app.status.operationState.phase in ['Failed', 'Error']
      send: [app-sync-failed]
  subscription.<team>: |
    - selector: appLabels['team'] == 'platform'
      send: [app-sync-failed]
```

### 3.5 Backup scope

**Backup can bao gom**:

| Resource | Reason |
|----------|--------|
| `Application` | Desired state mapping |
| `AppProject` | Security boundary + source/destination rules |
| `ApplicationSet` | Mass-generated Application |
| `Secret (type=repository)` | Git/Helm repo credentials |
| `Secret (type=cluster)` | Managed cluster credentials |
| `ConfigMap argocd-cm` | SSO config, URL, accounts |
| `ConfigMap argocd-rbac-cm` | RBAC policies |
| `ConfigMap argocd-cmd-params-cm` | Controller flags |
| `Secret argocd-secret` | Admin password hash, session key |
| `Secret tls-argocd` | TLS cert (if self-signed) |

**Khong can backup** (re-deploy tu Git):
- Workload manifests (Deployment, Service, etc.) — da trong Git
- Ingress, ConfigMap application data — da trong Git
- ESO/Sealed Secrets CRD — da trong Git

### 3.6 DR concepts

**RPO (Recovery Point Objective)**: maximum acceptable data loss measured in time.
**RTO (Recovery Time Objective)**: maximum acceptable downtime.

| Service tier | RPO | RTO | Strategy |
|-------------|-----|-----|----------|
| Critical (payment) | 0 (sync) | 15 min | GitOps + ArgoCD HA |
| Standard (API) | 15 min | 1 hour | GitOps + hourly backup |
| Dev/QA | 1 hour | 4 hours | GitOps only |
| Batch/infra | 24 hours | 1 day | Daily backup |

### 3.7 3 backup strategy

```
GitOps-first (BEST):     Everything in Git → re-apply root app → ArgoCD restore
argocd admin export:    Cron backup ArgoCD CRD → S3/GCS → restore import
Velero cluster-level:    Full cluster backup → restore full cluster
```

### 3.8 ASCII diagram — ArgoCD observability pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  ArgoCD Components                                          │
│  ┌──────┐  ┌──────────────┐  ┌────────────┐                 │
│  │Server│  │App Controller │  │Repo Server │                │
│  │ :8083│  │    :8082      │  │   :8084    │                │
│  └──┬───┘  └──────┬───────┘  └─────┬──────┘                │
└─────┼──────────────┼────────────────┼─────────────────────────┘
      │              │                │
      ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│  Prometheus (kube-prometheus-stack)                         │
│  ServiceMonitor scrape → time-series DB                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Grafana  │ │Alertmgr  │ │  Slack   │
        │Dashboard │ │  Alert   │ │ Webhook  │
        │ 14584    │ │  Route   │ │ Email    │
        └──────────┘ └──────────┘ └──────────┘
```

---

## 4. Deep dive & Trade-offs (~30 phut)

### 4.1 Backup strategy comparison

| Tieu chi | GitOps-only | argocd admin export | Velero cluster-level |
|----------|------------|---------------------|-----------------------|
| RPO | 0 (sync) | 1h-24h (cron) | 1h-24h |
| RTO | 30 min | 15-30 min | 1-4h (full cluster) |
| Coverage | ArgoCD + App + Project | ArgoCD CRD | Everything |
| Secret backup | Manual | Yes (export includes) | Yes |
| Restore testability | Easy (re-apply) | Medium | Hard |
| Git dependency | High (Git must live) | Low | Low |
| Cost | $0 | S3/GCS storage | S3/GCS + Velero license |
| Best fit | Dev/QA, standard prod | Multi-cluster, regulated | Full DR site |

**Recommendation**: GitOps-first + `argocd admin export` nightly to S3 as secondary.

### 4.2 Notification routing strategies

**Per AppProject**:

```yaml
# AppProject annotation
annotations:
  notifications.argoproj.io/subscribe.on-sync-failed.slack: "platform-alerts"
```

**Per team label**:

```yaml
# Application label
labels:
  team: platform
  severity: critical
```

```yaml
# notifications subscription
subscription.team-platform: |
  - selector: appLabels['team'] == 'platform'
    send: [platform-slack]
subscription.team-backend: |
  - selector: appLabels['team'] == 'backend'
    send: [backend-slack]
```

**Per severity**:

| Severity | Alert | Notification |
|----------|-------|-------------|
| P0 critical | ArgoAppNotHealthy > 5min | PagerDuty + Slack #incidents |
| P1 high | ArgoAppOutOfSync > 30min | Slack #alerts |
| P2 medium | ArgoAppSyncFailed once | Slack #dev-alerts |
| P3 low | Reconciliation > 5min | Email digest daily |

### 4.3 Trade-off: alert fatigue vs missed incident

- **Over-alerting**: `on-sync-running` moi lan sync deu alert → noise → ignored channel
- **Under-alerting**: chi alert P0 → P1 P2 bi bo, dev bat gap truoc khi thanh incident
- **Best practice**:
  - Alert on persistent failure (out-of-sync > X min, not every sync attempt)
  - Severity routing khac nhau cho team + SRE
  - Alert suppressed during maintenance window

### 4.4 Cost implications

| Component | Free | Low cost | Medium cost |
|-----------|------|----------|------------|
| Prometheus | Self-hosted (local) | kube-prometheus-stack | thanos sidecar |
| Grafana | Self-hosted local | Grafana Cloud free | Grafana Cloud paid |
| Alertmanager | Self-hosted | PagerDuty $15/app/mo | OpsGenie |
| Slack | Free tier 90-day history | Slack Standard $6.67/seat | Slack Plus |
| Notification webhook | webhook.site (dev) | ngrok tunnel (staging) | Cloudflare Tunnel prod |

### 4.5 Security considerations

- **Backup chua secret**: `argocd admin export` bao gom `argocd-secret` (admin hash) + repo credentials → encrypt at rest, IAM restrict
- **Webhook token**: Luu trong Secret, reference qua `{{.secretName}}`, khong hardcode trong Git ConfigMap
- **Metrics endpoint**: `:8083/metrics` co the expose internal IP → restrict via NetworkPolicy
- **ArgoCD secret**: Backup duoc nhung password hash co the duoc reverse → IAM restrict access

### 4.6 Best solution per context

| Context | Recommended | Ly do |
|---------|-------------|-------|
| Ca nhan hoc tap | GitOps-only + webhook.site | Khong can infrastructure, free |
| Small team 5 dev | GitOps + argocd-notifications Slack mock | Simple, low cost |
| Startup AWS | kube-prometheus-stack + Grafana Cloud + argocd-notifications | Managed, scalable |
| Enterprise multi-cluster | Velero + Prometheus federation + PagerDuty + SIEM | Full coverage |
| Bank regulated | Velero + argocd admin export + SIEM + offline cold storage | Compliance |

### 4.7 Pitfalls Day 27

- ServiceMonitor `release` label khong match → Prometheus khong scrape
- Alert rule condition `> 0` moi sync fail deu alert → fatigue
- Backup khong test restore = backup vô giá trị
- Notification webhook token hardcode trong ConfigMap → leak
- Metrics endpoint public internet (không có NetworkPolicy)
- ArgoCD pod restart = metrics gap nếu Prometheus retention < 2h
- `argocd admin export` chạy trên laptop → backup không tự động

---

## 5. Hands-on Lab (~60 phut)

### Pre-req

```bash
kind create cluster --name gitops27
kubectl cluster-info --context kind-gitops27
# Day 17 ArgoCD da cai: kubectl get ns argocd
# Day 24 orders app da co: kubectl get app -n argocd
# Day 25 RBAC da co
```

---

### Step 1: Cai kube-prometheus-stack qua Application (sync wave -10)

**5 phut**

Tao `prometheus-app.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: prometheus
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "-10"
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: false
    syncOptions:
    - CreateNamespace=true
  source:
    chart: kube-prometheus-stack
    repoURL: https://prometheus-community.github.io/helm-charts
    targetRevision: "55.x"
    helm:
      releaseName: prometheus
      values: |
        prometheus:
          prometheusSpec:
            retention: 15d
            retentionSize: 10GB
        alertmanager:
          enabled: true
        grafana:
          enabled: true
          adminPassword: admin
          defaultDashboardsTimezone: utc
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
```

Apply + observe sync wave -10 (truoc tat ca app khac):

```bash
kubectl apply -f prometheus-app.yaml
argocd app sync prometheus --force
# Verify: Prometheus tra ve Healthy truoc khi cac app khac sync
```

---

### Step 2: Tao ServiceMonitor cho 3 ArgoCD component

**10 phut**

```yaml
# clusters/dev/monitoring/argocd-servicemonitors.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-app-controller
  namespace: argocd
  labels:
    release: prometheus
spec:
  endpoints:
  - port: metrics
    interval: 30s
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-application-controller
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-server
  namespace: argocd
  labels:
    release: prometheus
spec:
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-server
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-repo-server
  namespace: argocd
  labels:
    release: prometheus
spec:
  endpoints:
  - port: metrics
    interval: 30s
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-repo-server
```

Apply + verify:

```bash
kubectl apply -f clusters/dev/monitoring/argocd-servicemonitors.yaml

# Verify Prometheus targets
kubectl port-forward -n monitoring svc/prometheus-prometheus 9090 &
# Open http://localhost:9090/targets → 4 targets UP (argo-server, app-controller, repo-server, notifications)
```

**Expected output**:

```
Endpoint                Status
argocd/8082/metrics     UP
argocd/8083/metrics     UP
argocd/8084/metrics     UP
notifications/9001       UP
```

---

### Step 3: Import Grafana dashboard ArgoCD

**5 phut**

```bash
# Port-forward Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000 &
# Open http://localhost:3000 (admin/admin)

# Import dashboard:
# Dashboards → Import → nhap 14584 → Load → prometheus (data source) → Import
# Dashboards → Import → nhap 19974 → Load → prometheus → Import
```

Verify metrics flow: Dashboard 14584 → kiem tra "Application Status" panel → thay `Healthy: 3, Degraded: 0, OutOfSync: 1`.

---

### Step 4: Tao PrometheusRule voi alert

**10 phut**

```yaml
# clusters/dev/monitoring/argocd-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: argocd-alerts
  namespace: argocd
  labels:
    release: prometheus
spec:
  groups:
  - name: argocd
    interval: 30s
    rules:
    # ArgoCD app out-of-sync > 10 minutes
    - alert: ArgoAppOutOfSync
      expr: argocd_app_info {export_app_labels="true"} * on(name, namespace) group_left() (argocd_app_sync_status{status="OutOfSync"} == 1)
      for: 10m
      labels:
        severity: warning
        team: platform
      annotations:
        summary: "App {{ $labels.name }} is OutOfSync for 10 minutes"
        description: "{{ $labels.name }} in {{ $labels.namespace }} has drifted from desired state."
        runbook_url: "https://wiki.example.com/runbooks/argocd-out-of-sync"

    # ArgoCD app sync failed
    - alert: ArgoAppSyncFailed
      expr: increase(argocd_app_sync_total{phase="Failed"}[5m]) > 0
      for: 1m
      labels:
        severity: critical
        team: platform
      annotations:
        summary: "App {{ $labels.name }} sync failed"
        description: "Sync failed for {{ $labels.name }}. Check ArgoCD UI."

    # ArgoCD app health degraded > 5 minutes
    - alert: ArgoAppNotHealthy
      expr: argocd_app_health_status == 0
      for: 5m
      labels:
        severity: warning
        team: platform
      annotations:
        summary: "App {{ $labels.name }} health degraded"

    # ArgoCD reconciliation slow (drift detection latency)
    - alert: ArgoReconciliationSlow
      expr: histogram_quantile(0.95, rate(argocd_app_reconcile_bucket[5m])) > 30
      for: 5m
      labels:
        severity: info
      annotations:
        summary: "ArgoCD reconciliation p95 > 30s"
```

Apply + verify Alertmanager nhan alert:

```bash
kubectl apply -f clusters/dev/monitoring/argocd-alerts.yaml

# Verify rules loaded
kubectl get prometheusrule -n argocd argocd-alerts
# Check Prometheus rule status
kubectl exec -n monitoring deploy/prometheus-prometheus -- \
  promtool check rules /etc/prometheus/rules/prometheus-argocd-alerts-*.yaml
```

---

### Step 5: Cau hinh argocd-notifications

**10 phut**

Kiem tra notifications-controller da chay (built-in ArgoCD 2.5+):

```bash
kubectl get deployment -n argocd | grep notifications
# Expected: argocd-notifications-controller Running
```

Tao notification ConfigMap:

```yaml
# clusters/dev/argocd/notifications-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
  namespace: argocd
data:
  # Tao webhook service mock (webhook.site)
  service.webhook-mock: |
    apiVersion: v1
    kind: Service
    metadata:
      name: argocd-notifications-webhook-mock
    spec:
      type: ExternalName
      externalName: webhook.site
    # Thuc te: su dung argocd-notifications configmap service
  config.yaml: |
    # Notification services
    notifications:
      services:
        webhook:
          mock: |
            url: https://webhook.site/<PLACEHOLDER_YOUR_WEBHOOK_ID>
            headers:
              Content-Type: application/json
  # Template
  template.app-sync-failed: |
    message: |
      🔴 Sync FAILED: {{.app.metadata.name}}
      Namespace: {{.app.spec.destination.namespace}}
      Phase: {{.app.status.operationState.phase}}
      Error: {{.app.status.operationState.result.message}}
      Link: https://localhost:3000/applications/{{.app.metadata.name}}
  template.app-health-degraded: |
    message: |
      🟡 Health DEGRADED: {{.app.metadata.name}}
      Status: {{.app.status.health.status}}
      Namespace: {{.app.spec.destination.namespace}}
  # Triggers
  trigger.on-sync-failed: |
    - when: app.status.operationState.phase in ['Failed', 'Error']
      send: [app-sync-failed]
  trigger.on-health-degraded: |
    - when: app.status.health.status in ['Degraded', 'Missing']
      send: [app-health-degraded]
---
# Secret cho webhook auth (neu can)
apiVersion: v1
kind: Secret
metadata:
  name: argocd-notifications-secret
  namespace: argocd
type: Opaque
stringData:
  webhook.mock.tls: "false"
```

**Get your webhook.site ID**:

1. Open https://webhook.site
2. Copy the unique URL (e.g. `https://webhook.site/abc123-def456-...`)
3. Replace `<PLACEHOLDER_YOUR_WEBHOOK_ID>` with the path after `webhook.site/`

Apply:

```bash
kubectl apply -f clusters/dev/argocd/notifications-config.yaml
```

---

### Step 6: Test notification — trigger sync fail

**10 phut**

Tao app co loi co chu dong:

```yaml
# clusters/dev/apps/fail-demo.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: fail-demo
  namespace: argocd
  annotations:
    notifications.argoproj.io/subscribe.on-sync-failed.webhook-mock: ""
    notifications.argoproj.io/subscribe.on-health-degraded.webhook-mock: ""
spec:
  project: apps
  source:
    repoURL: https://github.com/argoproj/argo-cd.git
    path: manifests/samples/known-hosts  # Valid path
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: fail-demo
  syncPolicy:
    automated: {}
```

Thay doi de trigger sync fail:

```bash
kubectl apply -f clusters/dev/apps/fail-demo.yaml
argocd app sync fail-demo

# Verify notification sent
# 1. ArgoCD UI: App fail-demo → Status: Sync Failed
# 2. webhook.site: nhan POST request voi JSON payload
# 3. ArgoCD Application events: kubectl describe app fail-demo -n argocd
```

Check notification controller log:

```bash
kubectl logs -n argocd deployment/argocd-notifications-controller | grep -i "fail-demo"
```

Expected: Log hien thi trigger `on-sync-failed` → template rendered → webhook POST.

Clean up fail-demo sau khi verify:

```bash
kubectl delete -f clusters/dev/apps/fail-demo.yaml
```

---

### Step 7: Backup va restore bang argocd admin export

**10 phut**

Backup:

```bash
# Backup to file
argocd admin export -n argocd > clusters/dev/argocd-backup-$(date +%Y%m%d).yaml

# Inspect backup content
grep -E "^kind:" clusters/dev/argocd-backup-*.yaml | sort | uniq -c

# Expected kinds: Application, AppProject, ConfigMap (argocd-*), Secret (argocd-*)
```

Inspect chi tiet:

```bash
# Xem repo credentials trong backup
grep -A5 "kind: Secret" clusters/dev/argocd-backup-*.yaml | head -40
# Kiem tra argocd-secret (admin password hash)
grep "argocd-secret" clusters/dev/argocd-backup-*.yaml
```

Restore test (xoa + restore):

```bash
# Tao 1 AppProject + 1 Application de delete
kubectl create ns test-dr
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: test-dr-project
  namespace: argocd
spec:
  sourceRepos:
  - '*'
  destinations:
  - namespace: test-dr
    server: https://kubernetes.default.svc
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: test-dr-app
  namespace: argocd
spec:
  project: test-dr-project
  source:
    repoURL: https://github.com/argoproj/argo-cd.git
    path: manifests/namespace-install
    targetRevision: v3.4.2
  destination:
    server: https://kubernetes.default.svc
    namespace: test-dr
EOF

# Xoa AppProject + Application
kubectl delete appproject test-dr-project -n argocd
kubectl delete app test-dr-app -n argocd

# Restore
argocd admin import -f clusters/dev/argocd-backup-*.yaml

# Verify
argocd app list | grep test-dr
# Expected: test-dr-app da duoc khoi phuc
```

---

### Step 8: GitOps-style DR — simulate mat ArgoCD

**5 phut**

Nguyen tac: Everything in Git = ArgoCD chi la rendered, không có state đặc biệt.

Scenario: Mat toan bo ArgoCD namespace.

```bash
# Step 1: Backup truoc (da lam Step 7)
# Step 2: Simulate mat ArgoCD
kubectl delete ns argocd --wait=true
kubectl delete crd applicationsets.argoproj.io applications.argoproj.io 2>/dev/null || true

# Step 3: Re-install ArgoCD
kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.2/manifests/install.yaml

# Step 4: Restore credentials + config
argocd admin import -f clusters/dev/argocd-backup-*.yaml

# Step 5: Re-apply root app (trong backup)
argocd app list
# Expected: Tat ca Application + AppProject da khoi phuc

# Step 6: Sync tat ca
argocd app sync --all
```

GitOps DR checklist:
- [ ] ArgoCD CRD reinstalled
- [ ] ArgoCD namespace recreated
- [ ] argocd-secret + argocd-cm restored
- [ ] Application + AppProject restored
- [ ] Repo credentials Secret restored
- [ ] Root app re-apply (App of Apps)
- [ ] Sync all

---

### Step 9: Cleanup

```bash
# Xoa lab resources
kubectl delete -f clusters/dev/monitoring/argocd-servicemonitors.yaml
kubectl delete -f clusters/dev/monitoring/argocd-alerts.yaml
kubectl delete -f clusters/dev/argocd/notifications-config.yaml
kubectl delete app fail-demo -n argocd 2>/dev/null || true
kubectl delete app test-dr-app -n argocd 2>/dev/null || true
kubectl delete appproject test-dr-project -n argocd 2>/dev/null || true
kubectl delete ns test-dr 2>/dev/null || true

# Khong xoa prometheus — dung cho Day 27 exercises
# ArgoCD core khong xoa — dung cho Day 27 tiep theo
```

---

### Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Prometheus no targets for ArgoCD | `kubectl get servicemonitor -n argocd` | Add label `release: prometheus` |
| Alert rule never fires | `kubectl get prometheusrule -n argocd` | Check `for` duration (must elapse) |
| Notification not sent | `kubectl logs -n argocd deploy/argocd-notifications-controller` | Check trigger + subscription annotation |
| webhook.site not receiving | Check firewall / ngrok | Use `kubectl port-forward` |
| Restore fail | Check CRD tồn tại | Re-install ArgoCD CRD truoc `admin import` |
| argocd admin export fail | RBAC: need admin | `argocd login --admin` |

---

## 6. Kiem tra hieu bai

1. **Concept**: Argocd-application-controller export metrics gi qua port 8082, nhung Prometheus ServiceMonitor can label gi de duoc scrape?

2. **Choose approach**: Team 5 dev, khong cloud, can alert Slack → chon notification routing nao? Se danh gia 3 phuong an.

3. **Debug**: Alert `ArgoAppSyncFailed` khong bao gio fire duoi Prometheus, nhung app thuc su da sync fail nhieu lan → root cause checklist (3 buoc)?

4. **Refactor**: Chuyen toan bo backup tu manual `argocd admin export` sang GitOps-first → thiet ke backup policy voi RPO = 15 min, describe 4 buoc.

5. **Trade-off**: Cluster mat hoan toan, bao gom ca persistent volume cua argocd-repo-server (chua cache git) → so sanh 2 phuong phap restore (argocd admin import vs re-sync tu Git).

---

## 7. Tom tat cuoi ngay

**5 y chinh**:

1. **Metrics la nen tang**: ArgoCD components export 30+ metrics; ServiceMonitor `release: prometheus` label la cau noi Prometheus → ArgoCD.

2. **Alert != notification**: Prometheus alert la ve metrics threshold; argocd-notifications la ve event-driven dispatch (Slack/email/webhook). Can ca 2.

3. **Backup 3-layer**: GitOps-first (everything in Git = 0 RPO) + `argocd admin export` nightly (secondary) + Velero (full cluster DR).

4. **DR = RPO/RTO target truoc**: Khong co target = khong co plan. Critical tier: RPO=0 (GitOps), RTO<15min.

5. **Backup chi co gia tri neu da test restore**: Run restore test quarterly, document time-to-recover.

**Output da tao**:

```
day-27-argocd-observability-dr/
  lesson.md        # 8 sections, 9-step lab, 5 quiz
  document.md      # Metrics catalog, ServiceMonitor template, notification reference, backup checklist, DR runbook
  exercises.md     # 6 challenges + bonus (alert design, notification routing, DR exercise, secret backup, multi-cluster observability)
```

**Week 4 hoan thanh.** Chuyen sang **Week 5 - Capstone Production-Grade** (Day 28-35):
- Day 28-31: Multi-environment promotion, CI/CD pipeline, Container Registry
- Day 32-33: Platform bootstrap, observability stack, production-grade config
- Day 34-35: DR scenario, GameDay, production readiness review

---

## 8. Tham khao them

- ArgoCD Metrics: https://argo-cd.readthedocs.io/en/stable/operator-manual/metrics/
- ArgoCD Notifications: https://argocd-notifications.readthedocs.io/en/stable/
- Grafana Dashboard 14584: https://grafana.com/grafana/dashboards/14584
- Grafana Dashboard 19974: https://grafana.com/grafana/dashboards/19974
- kube-prometheus-stack: https://prometheus-community.github.io/helm-charts
- argocd admin: https://argo-cd.readthedocs.io/en/stable/operator-manual/disaster_recovery/
- RTO/RPO reference: https://en.wikipedia.org/wiki/Disaster_recovery
- Alertmanager routing: https://prometheus.io/docs/alerting/latest/configuration/
