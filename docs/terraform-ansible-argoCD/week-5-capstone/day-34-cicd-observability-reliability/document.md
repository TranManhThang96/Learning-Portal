# Day 34 — CI/CD, Observability, Reliability
## Reference Document

> Chứa CI/CD pipeline checklist, observability stack reference, reliability manifest template, cost control guide, và troubleshooting quick reference.

---

## A. CI/CD Pipeline Checklist

### Pipeline Quality Gates

```
[ ] Code lint (fmt, vet, lint)
[ ] Unit tests pass (coverage tracked)
[ ] Dockerfile multi-stage build (no secret in image)
[ ] Trivy scan: CRITICAL = block, HIGH = warn
[ ] Image pushed with immutable tag (git SHA)
[ ] SBOM / provenance generated
[ ] GH PAT / OIDC credentials: never hardcoded
[ ] PR created to apps-repo with correct image tag
[ ] Image reference updated in values.yaml or kustomization.yaml
[ ] ArgoCD detects OutOfSync after PR merge
```

### Security Checklist — CI/CD

```
[ ] No long-lived AWS access key (use OIDC)
[ ] GITHUB_TOKEN hoặc GH_PAT có quyền tối thiểu
[ ] IAM role trust policy giới hạn repo + branch
[ ] Image tag = immutable (git SHA, không dùng latest)
[ ] Dockerfile: non-root user, no curl, minimal base image
[ ] Trivy scan không bỏ qua CRITICAL CVE
[ ] Secrets không nằm trong image (use .dockerignore)
[ ] Build cache không chứa secret
```

### OIDC Trust Policy Template (AWS)

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:$GITHUB_ORG/*",
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      }
    }
  }]
}
```

### GitHub Actions Secrets Reference

| Secret Name | Required For | Notes |
|---|---|---|
| `GITHUB_TOKEN` | GHCR login | Auto-provided, no setup |
| `GH_PAT` | PR to different repo | cần `repo` scope |
| `AWS_ACCOUNT_ID` | OIDC role | Vars, không cần secret |
| `AWS_REGION` | ECR push | Vars |
| `ECR_REPOSITORY` | ECR repo name | Vars |

---

## B. Observability Stack Reference

### Prometheus Metrics — Required Labels Per Service

```yaml
# Service annotation để Prometheus tự discover
metadata:
  annotations:
    prometheus.io/scrape: "true"     # legacy way
    prometheus.io/port: "9090"
    prometheus.io/path: "/metrics"
```

### ServiceMonitor (prometheus-operator way — production recommended)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: <service>
  namespace: monitoring
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: <service>
  endpoints:
  - port: metrics
    path: /metrics
    interval: 15s
    scrapeTimeout: 10s
```

### PrometheusRule Alert Severity Matrix

| Alert | Severity | For | Response | Channel |
|---|---|---|---|---|
| PodDown | Critical | replicas = 0 | Restart / page | PagerDuty |
| HighErrorRate | High | 5xx > 5% | Investigate | Slack #incidents |
| HighLatency | Medium | P95 > 2s | Investigate | Slack #alerts |
| MemoryPressure | Medium | Memory > 90% limit | Increase limit | Slack #alerts |
| CPUThrottling | Warning | CPU throttle > 50% | Increase CPU limit | Ticket |
| OOMKilled | High | Any OOMKilled | Increase memory | Slack #incidents |
| CertificateExpiry | Low | Cert < 30 days | Renew | Ticket |

### Grafana Dashboard — Community Dashboards Quick Reference

| Dashboard ID | Name | Use Case |
|---|---|---|
| 1860 | Node Exporter Full | Node CPU/Memory/Disk/Network |
| 1337 | Kubernetes cluster (prometheus-operator) | Cluster overview |
| 8588 | Kubernetes API server | K8s control plane |
| 16042 | Redis Dashboard | Redis monitoring |
| 18032 | PostgreSQL Overview | PostgreSQL monitoring |
| 13701 | Nginx Ingress Controller | Ingress metrics |

### Loki / Log Aggregation Quick Reference

```yaml
# Promtail config (DaemonSet on every node)
apiVersion: v1
kind: ConfigMap
metadata:
  name: promtail-config
  namespace: monitoring
data:
  promtail.yaml: |
    server:
      http_listen_port: 9080
      grpc_listen_port: 0
    positions:
      filename: /tmp/positions.yaml
    client:
      url: http://loki.monitoring.svc.cluster.local:3100/loki/api/v1/push
    scrape_configs:
    - job_name: kubernetes-pods
      kubernetes_sd_configs:
      - role: pod
      relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
```

---

## C. Reliability Manifest Templates

### Complete Deployment Template (Reliability Complete)

```yaml
# api-service-deployment-reliability.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  namespace: default
  labels:
    app: api-service
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1          # Thêm tối đa 1 pod mới
      maxUnavailable: 0    # Không pod nào bị kill trước khi pod mới ready
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      # Reliability: spread across zones
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: api-service
      # Anti-affinity: không chạy 2 pod cùng node
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: api-service
              topologyKey: kubernetes.io/hostname
      # Graceful shutdown
      terminationGracePeriodSeconds: 60
      containers:
      - name: api-service
        image: ghcr.io/myorg/api-service:a1b2c3d
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 8080
        - name: metrics
          containerPort: 9090

        # Readiness: traffic only khi ready
        readinessProbe:
          httpGet:
            path: /healthz/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
          failureThreshold: 3
          successThreshold: 1
          timeoutSeconds: 3

        # Liveness: restart khi stuck
        livenessProbe:
          httpGet:
            path: /healthz/live
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
          failureThreshold: 3
          timeoutSeconds: 3

        # Startup: cho app startup lâu
        startupProbe:
          httpGet:
            path: /healthz/ready
            port: 8080
          failureThreshold: 30
          periodSeconds: 10

        # Resources: requests + limits
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi

        # Security
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: [ALL]

        # Lifecycle hooks
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 5"]  # Graceful shutdown delay
        volumeMounts:
        - name: tmp
          mountPath: /tmp

      volumes:
      - name: tmp
        emptyDir: {}

      # Pod disruption budget protection
      # Áp dụng PDB ở level khác (kubectl apply -f api-service-pdb.yaml)
```

### HPA + PDB Template

```yaml
# api-service-hpa-pdb.yaml
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-service-pdb
spec:
  minAvailable: 1
  # Hoặc: maxUnavailable: 1  (cho replicas >= 3)
  selector:
    matchLabels:
      app: api-service
```

### Resource Ratio Quick Reference

| Workload Type | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---|---|---|---|---|
| Light API (Go/Node) | 50m | 200m | 64Mi | 128Mi |
| Medium API (Go/Node) | 100m | 500m | 128Mi | 256Mi |
| Heavy API (Java/JVM) | 250m | 1000m | 512Mi | 1Gi |
| Python Worker | 100m | 500m | 128Mi | 512Mi |
| Redis | 100m | 500m | 256Mi | 512Mi |
| PostgreSQL (sidecar) | 100m | 250m | 128Mi | 256Mi |

---

## D. AWS Cost Control (Mode B)

### Resource Cost Matrix

| Resource | Monthly Cost | Notes |
|---|---|---|
| ECR storage (3 repos) | ~$5 | 50GB free tier |
| ECR outbound | ~$2 | Tùy traffic |
| Prometheus server (EBS 50GB) | ~$5 | gp3 |
| Grafana (EC2 or managed) | ~$20-50 | nếu không dùng EKS add-on |
| GitHub Actions (2000 phút) | $0 | Public repo free |
| GitHub Actions (private) | ~$8 | 3000 phút |

### Cost Optimization Checklist

```
[ ] Dùng Spot node cho non-production cluster
[ ] ECR lifecycle policy: giữ 10 images gần nhất
[ ] Prometheus retention: 15 ngày (không cần 90 ngày cho dev)
[ ] GitHub Actions: dùng cache (buildx cache-from/cache-to)
[ ] Không chạy workflow vào cuối tuần (automation schedule)
[ ] Mode A cho dev/staging (kind cluster)
[ ] Cleanup: xóa ECR images không dùng sau mỗi sprint
```

---

## E. Troubleshooting Quick Reference

### CI/CD Issues

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: NoCredentialProviders` | Thiếu IAM permission | Thêm IAM policy cho ECR |
| `403 Forbidden` GHCR | GITHUB_TOKEN hết hạn | Dùng GITHUB_TOKEN mặc định |
| Trivy exit 1 nhưng muốn push | CRITICAL CVE found | Fix CVE hoặc thêm vào .trivyignore |
| PR không được tạo | GH_PAT thiếu quyền | Thêm `repo` + `workflow` scope |
| Image tag SHA không match | Caching artifact | Dùng `${<!-- -->{ github.sha }}` không dùng artifact |

### Observability Issues

| Symptom | Cause | Fix |
|---|---|---|
| Prometheus không scrape metrics | Label mismatch | Check `release: prometheus` label |
| Grafana dashboard blank | ConfigMap label sai | Check `grafana_dashboard: "1"` |
| Alert không fire | Rule chưa load | `kubectl get prometheusrule` |
| Loki log missing | Promtail chưa chạy | Check Promtail pod logs |
| Metrics 404 | `/metrics` endpoint không expose | Thêm `/metrics` route trong app |

### Reliability Issues

| Symptom | Cause | Fix |
|---|---|---|
| OOMKilled | Memory limit thấp | Tăng memory limit |
| Liveness probe fail | `initialDelaySeconds` quá thấp | Tăng `initialDelaySeconds` |
| HPA không scale up | Không có node available | Kiểm tra node allocatable |
| PDB blocking drain | `minAvailable` = `replicas` | Đổi sang `maxUnavailable: 1` |
| Pod restart liên tục | Readiness probe fail | Kiểm tra `/healthz/ready` endpoint |
| CPU throttling | CPU limit quá thấp | Tăng CPU limit (request: 100m, limit: 500m) |

---

## F. ArgoCD Image Updater (Alternative)

Nếu muốn ArgoCD tự update image tag thay vì PR-based approach:

```yaml
# Install ArgoCD Image Updater (Day 32 nên cài)
apiVersion: argoproj.io/v1alpha1
kind: ArgoCDExtension
metadata:
  name: argocd-image-updater
spec:
  version: v0.9.1

# Annotation trên Application để auto-update
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service
  annotations:
    argocd-image-updater.argoproj.io/image-list: |
      myorg/api-service=ghcr.io/myorg/api-service
    argocd-image-updater.argoproj.io/write-back-method: git
    argocd-image-updater.argoproj.io/git-branch: main
    argocd-image-updater.argoproj.io/update-strategy: latest
```

**Khi nào dùng ArgoCD Image Updater thay vì PR:**

| Scenario | Approach |
|---|---|
| Dev environment (fast iteration) | ArgoCD Image Updater (direct push) |
| Staging/Prod (audit trail required) | PR-based (GitHub Actions) |
| Bank/regulated (change approval required) | PR-based always |

---

## G. SRE / On-call Quick Reference

### Common Production Alerts và First Response

```
APIServicePodDown (P1)
→ kubectl get pods -l app=api-service
→ kubectl describe pod <pod-name>
→ kubectl logs <pod-name> --previous  # logs trước crash
→ Action: kubectl rollout restart deployment/api-service

APIServiceHighErrorRate (P2)
→ argocd app get api-service  # check sync status
→ kubectl logs -l app=api-service --tail=100
→ Check upstream: Redis, PostgreSQL connectivity
→ Action: Rollback nếu cần (argocd app rollback api-service)

APIServiceOOMKilled (P2)
→ kubectl describe pod <pod-name> | grep -A5 "Last State"
→ kubectl top pod <pod-name>
→ Action: Tăng memory limit + restart

APIServiceMemoryPressure (P3)
→ kubectl top pods -l app=api-service
→ Action: Schedule tăng resource limit

CertificateExpiry (P4)
→ kubectl get certificate
→ kubectl describe certificate
→ Action: cert-manager tự renew, check DNS + cluster issuer
```

### Runbook Template

```markdown
# Runbook: <Incident Name>

## Symptoms
- Alert fired: <alert name>
- Time: <timestamp>
- Impact: <service down / slow / errors>

## Root Cause Hypothesis
1. ...

## Verification Steps
```bash
kubectl get pods -l app=<service>
kubectl logs <pod> --tail=100
argocd app get <service>
```

## Mitigation
- [ ] Step 1
- [ ] Step 2

## Resolution
...

## Follow-up
- [ ] Post-mortem
- [ ] Preventive action
```
