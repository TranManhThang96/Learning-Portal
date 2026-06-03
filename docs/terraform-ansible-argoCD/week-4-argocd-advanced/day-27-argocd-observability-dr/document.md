# Day 27 — ArgoCD Observability, Notifications, Backup & DR — Reference Cheat Sheet

---

## 1. ArgoCD Metrics Catalog

### argocd-application-controller metrics (`:8082`)

| Metric | Type | Meaning |
|--------|------|---------|
| `argocd_app_info` | Gauge | App count by health/sync status |
| `argocd_app_sync_total` | Counter | Sync attempts by result (succeeded/failed) |
| `argocd_app_reconcile` | Histogram | Reconciliation duration |
| `argocd_app_reconcile_count` | Counter | Reconciliation count |
| `argocd_app_health_status` | Gauge | 1=Healthy, 0=Degraded/Missing |
| `argocd_app_sync_status` | Gauge | 1=Synced, 0=OutOfSync, -1=Unknown |
| `argocd_cluster_api_resource_objects` | Gauge | Number of live k8s objects per cluster |
| `argocd_cluster_api_resources_count` | Gauge | Number of discoverable API resources |
| `argocd_git_request_total` | Counter | Git operations by type + result |
| `argocd_kubectl_exec_total` | Counter | kubectl exec into pods |

### argocd-server metrics (`:8083`)

| Metric | Type | Meaning |
|--------|------|---------|
| `argocd_server_request_total` | Counter | HTTP requests by path + method + status |
| `argocd_server_cluster_api_request_count` | Counter | Cluster API calls made by server |
| `argocd_login_total` | Counter | Login attempts by result |
| `argocd_grpc_response_total` | Counter | gRPC responses by service + status |
| `argocd_event_list_total` | Counter | Kubernetes event list operations |

### argocd-repo-server metrics (`:8084`)

| Metric | Type | Meaning |
|--------|------|---------|
| `argocd_git_hardcoded_request_total` | Counter | DEPRECATED, ignore |
| `argocd_repo_pending_syncs` | Gauge | Number of pending sync operations |

---

## 2. ServiceMonitor YAML Template

```yaml
# argocd-application-controller ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-app-controller
  namespace: argocd
  labels:
    release: prometheus   # MUST match kube-prometheus-stack selector
spec:
  endpoints:
  - port: metrics
    interval: 30s
    scheme: http
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-application-controller
---
# argocd-server ServiceMonitor
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
    scheme: http
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-server
---
# argocd-repo-server ServiceMonitor
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
    scheme: http
  namespaceSelector:
    matchNames:
    - argocd
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-repo-server
```

---

## 3. Notification Triggers & Templates Reference

### Full trigger list (built-in)

| Trigger | CEL condition | Send when |
|---------|---------------|-----------|
| `on-sync-running` | `app.status.operationState.phase == "Running"` | Sync started |
| `on-sync-succeeded` | `app.status.operationState.phase == "Succeeded"` | Sync OK |
| `on-sync-failed` | `app.status.operationState.phase in ["Failed", "Error"]` | Sync fail |
| `on-sync-status-unknown` | `app.status.operationState.phase == "Unknown"` | Sync stuck |
| `on-health-degraded` | `app.status.health.status == "Degraded"` | Health bad |
| `on-health-unknown` | `app.status.health.status == "Unknown"` | Health unknown |
| `on-health-missing` | `app.status.health.status == "Missing"` | App deleted from cluster |
| `on-out-of-sync` | `app.status.status == "OutOfSync"` | Spec != live |
| `on-created` | `app.metadata.creationTimestamp - now() < 2m` | New app |
| `on-deleted` | N/A | App deleted |
| `on-rollback` | `app.status.operationState.phase == "Succeeded"` + rollback flag | Rollback done |
| `on-deprecated` | (custom CEL) | Custom condition |

### CEL filter examples

```yaml
# Out-of-sync > 30 minutes
- when: app.status.status == "OutOfSync" && app.status.health.status != "Healthy"
  send: [app-degraded-warning]

# Sync failed, specific app name
- when: app.status.operationState.phase == "Failed" && app.metadata.name == "critical-api"
  send: [pagerduty-critical]

# Out-of-sync on production project
- when: app.status.status == "OutOfSync" && app.metadata.labels['env'] == "prod"
  send: [prod-alerts]

# Health unknown > 5 minutes
- when: app.status.health.status == "Unknown"
  send: [app-health-unknown]

# New application created
- when: app.metadata.labels['team'] != ""
  send: [app-created-notification]
```

### Service types

| Service | Config key | Use case |
|---------|-----------|---------|
| Slack | `service.slack` | Production Slack channel |
| Email | `service.email` | Digest / fallback |
| Webhook | `service.webhook.<name>` | Custom endpoint |
| Teams | `service.teams` | Microsoft Teams |
| Telegram | `service.telegram` | Mobile alert |
| OpsGenie | `service.opsgenie` | PagerDuty-like |
| GitHub | `service.github` | GitHub commit status |
| Custom webhook | `service.webhook.<name>` | Script / automation |

### Template variables

```yaml
# Available in all templates
{{.app.metadata.name}}           # Application name
{{.app.metadata.namespace}}       # ArgoCD namespace
{{.app.spec.destination.namespace}}  # Target namespace
{{.app.spec.destination.server}} # Target cluster
{{.app.status.operationState.phase}}  # Sync phase
{{.app.status.operationState.result.message}}  # Error message
{{.app.status.health.status}}     # Healthy/Degraded/Missing/Unknown
{{.app.status.status}}            # Synced/OutOfSync/Unknown
{{.app.status.health.message}}    # Health details
{{.app.status.resources}}         # Resource list
{{.app.metadata.labels.team}}     # Any label
{{.app.metadata.annotations.notifications.argoproj.io/replicas}}  # Replicas
{{.context.argocdUrl}}           # ArgoCD URL
{{.time}}                        # Current time
```

---

## 4. Backup Checklist

### Must-have (RTO < 1h)

- [ ] `argocd admin export` backup schedule (cron, 6h)
- [ ] Backup includes all Application CRD
- [ ] Backup includes all AppProject CRD
- [ ] Backup includes all ApplicationSet CRD
- [ ] Backup includes `argocd-secret` (admin hash)
- [ ] Backup includes `argocd-cm` (accounts, OIDC config)
- [ ] Backup includes `argocd-rbac-cm` (policies)
- [ ] Backup stored in S3/GCS (off-cluster)
- [ ] Restore tested in last 90 days

### Should-have (RTO < 4h)

- [ ] Backup includes repo credential Secrets (type=repository)
- [ ] Backup includes cluster credential Secrets
- [ ] Backup includes argocd-cmd-params-cm
- [ ] TLS cert backup (if self-signed)
- [ ] Dex config backup (if external Dex)
- [ ] Backup encryption at rest (SSE-KMS)
- [ ] IAM policy: backup bucket restricted to ArgoCD SA
- [ ] Quarterly GameDay DR test

### Nice-to-have (RTO < 15 min)

- [ ] GitOps-first: everything in Git = restore from Git (no backup needed)
- [ ] ArgoCD HA configuration (2+ replicas)
- [ ] Velero cluster-level backup (full DR site)
- [ ] Backup includes notification ConfigMaps
- [ ] Offline cold storage (Glacier) for compliance
- [ ] Immutable backup (WORM storage)
- [ ] Backup integrity verification (checksum)
- [ ] Alert on backup failure

---

## 5. DR Runbook Template

### Scenario A: Lost ArgoCD namespace (most common)

**Trigger**: ArgoCD namespace deleted or corrupt.

**RTO target**: < 30 min

**Steps**:

```
1. PREVENT: ArgoCD namespace deleted → RBAC block (Day 25)
2. ASSESS: Check ArgoCD CRD still exists
3. REINSTALL: kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-cd/v{VERSION}/manifests/install.yaml
4. RESTORE CREDS: argocd admin import < backup-{DATE}.yaml
5. RESTORE APPS: argocd admin import < backup-{DATE}.yaml  (same command)
6. VERIFY: argocd app list → count matches expected
7. SYNC ALL: argocd app sync --all
8. CONFIRM: ArgoCD UI → all apps Healthy
9. POST-INCIDENT: Document restore time, root cause
```

### Scenario B: Lost entire Kubernetes cluster

**Trigger**: Cluster unrecoverable (hardware failure, ransomware).

**RTO target**: < 4 hours

**Steps**:

```
1. NEW CLUSTER: Provision new cluster (Terraform Day 3-5)
2. INSTALL ARGO: ArgoCD install via bootstrap (App of Apps Day 21)
3. RESTORE CREDENTIALS:
   - argocd-secret (admin password)
   - repo credentials Secret
   - cluster secrets
4. RESTORE APPS:
   - argocd admin import < backup.yaml
   - OR re-apply root Application
5. VERIFY: ArgoCD syncs all apps from Git
6. WORKLOAD RECOVERY:
   - DB (from RDS snapshot / backup)
   - Redis (from ElastiCache snapshot)
   - Storage (from EBS snapshot)
7. DNS CUTOVER: Route53 / Cloudflare update
8. POST-INCIDENT: Update RTO/RPO, test restore
```

### Scenario C: Lost Git repository

**Trigger**: GitHub private repo deleted, no fork.

**RTO target**: < 24 hours

**Steps**:

```
1. PREVENT: Mirror to 2 remotes (GitHub + GitLab) + ArgoCD repo backup (Day 20)
2. ASSESS: Check if any ArgoCD app still references repo
3. RESTORE FROM FORK: Clone from any team member's fork
4. RESTORE FROM BACKUP: If no fork exists, restore from GitHub recovery (30-day window)
5. UPDATE REMOTE: argocd app set <app> --repo <new-url>
6. RE-CREATE REPO: Push restored content to new org
7. VERIFY: ArgoCD syncs restored manifests
8. POST-INCIDENT: Add secondary remote mirror
```

---

## 6. RPO/RTO Matrix per Service Tier

| Tier | Example | RPO | RTO | Strategy |
|------|---------|-----|-----|----------|
| P0 Critical | Payment processing, trading | 0 | 15 min | GitOps-only + ArgoCD HA + runbook |
| P1 High | Core API, user auth | 15 min | 1 hour | GitOps + hourly backup |
| P2 Medium | Background jobs, reporting | 1 hour | 4 hours | GitOps + daily backup |
| P3 Low | Dev/QA, internal tools | 24 hours | 1 day | GitOps only |

**Cost implication**: RTO 15 min requires:
- ArgoCD HA (2+ replicas, separate statefulset)
- Pre-provisioned DR cluster (or GitOps fast provisioning)
- Runbook practiced quarterly

---

## 7. Anti-Patterns (15 bullet)

- [ ] Metrics endpoint not secured (no NetworkPolicy, open to internet)
- [ ] `release: prometheus` label missing on ServiceMonitor → no scrape
- [ ] Alert condition `> 0` on every sync → alert fatigue
- [ ] Notification webhook token hardcoded in ConfigMap
- [ ] `argocd admin export` run manually → no automation
- [ ] Backup stored on same machine → single point of failure
- [ ] Backup never tested → restore will fail
- [ ] GitOps-first chosen but some config outside Git → partial restore
- [ ] Velero backup excludes ArgoCD namespace → incomplete
- [ ] Grafana dashboard 14584 imported but Prometheus data source not named "Prometheus" → blank panels
- [ ] `argocd cm` password changed post-backup → old backup has wrong hash
- [ ] Notification annotation `subscribe.on-sync-failed.webhook` but service `webhook` not defined → silent fail
- [ ] Alert fires P0 at 2am but on-call not subscribed → ignored
- [ ] Backup restore on same cluster after namespace delete → name collision
- [ ] Prometheus retention 1h → historical metrics lost for root-cause analysis

---

## 8. Common Errors Table

| Error | Symptom | Root cause | Fix |
|-------|---------|-----------|-----|
| ServiceMonitor not found | Prometheus target page: 0/4 | Wrong `release` label | Add `release: prometheus` label |
| `metric not found` in Grafana | Dashboard panel blank | Prometheus DS wrong name | Check data source name |
| Notification not sent | Webhook.site empty | Subscription annotation missing | Add `notifications.argoproj.io/subscribe.on-sync-failed.webhook-mock: ""` |
| `argocd admin export` timeout | Command hangs | ArgoCD too slow | Increase timeout or use `--grpc-web` |
| Import fail: CRD not found | Error on Application | ArgoCD CRD not installed | `kubectl apply -f argo-cd/crds/` first |
| Alert fires once then stops | On-call not paged | Alert suppressed | Check `for` duration, increase |
| Grafana 14584 shows 0 apps | Dashboard empty | Metrics label mismatch | Check `export_app_labels: "true"` in prometheus rule |
| Restore overwrites live apps | Apps disappear | Import in wrong order | Restore in topological order: AppProject before Application |
| Metrics 404 | Prometheus shows DOWN | Wrong port or path | Verify `:8082/metrics`, `:8083/metrics` |
| argocd-notifications CrashLoopBackOff | Pod not running | Misconfigured template | Check template YAML indentation |
