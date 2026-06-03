# Day 26 — Argo Rollouts, Progressive Delivery — Reference

---

## 1. Argo Rollouts Strategy Reference

### 1.1 Canary Strategy — Full YAML

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: <app-name>
  namespace: <namespace>
spec:
  replicas: 4
  minReadySeconds: 30
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: <app-name>
  template:
    metadata:
      labels:
        app: <app-name>
    spec:
      containers:
        - name: <app-name>
          image: <image>:<tag>
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
  strategy:
    canary:
      # Services
      canaryService: <app>-canary
      stableService: <app>-stable

      # Traffic weight steps
      steps:
        - setWeight: 25
        - pause: {}              # Manual pause
        - setWeight: 50
        - pause:
            duration: 5m         # Auto-pause 5 phut
        - setWeight: 75
        - pause: {}
        - setWeight: 100

      # Analysis integration
      analysis:
        templates:
          - templateName: success-rate-check
        startingStep: 1         # Bat dau sau step 1 (25%)
        args:
          - name: service-name
            value: <app>-canary.<namespace>.svc.cluster.local

      # Replica management
      maxSurge: "25%"
      maxUnavailable: 0

      # Anti-affinity
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          labelSelector:
            matchLabels:
              app: <app-name>
```

### 1.2 Blue-Green Strategy — Full YAML

```yaml
strategy:
  blueGreen:
    activeService: <app>-active
    previewService: <app>-preview

    # Auto-promote khi replicas ready (default: true)
    autoPromotionEnabled: false   # RECOMMENDED: manual

    # Delay truoc khi scale down old version
    scaleDownDelaySeconds: 30
    scaleDownDelayRevisionLimit: 3  # Giu 3 revision truoc khi xoa

    # Anti-affinity
    topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: kubernetes.io/hostname
        labelSelector:
          matchLabels:
            app: <app-name>
```

### 1.3 Rollout — Full Spec (key fields)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
spec:
  # Scale
  replicas: 4
  minReadySeconds: 30
  revisionHistoryLimit: 3

  # Pause/Resume
  paused: true    # Manually pause rollout

  # Strategy
  strategy:
    canary:
      canaryService: <name>
      stableService: <name>
      steps: []
      analysis:
        templates: []
        startingStep: 0
        args: []
      maxSurge: "25%"
      maxUnavailable: 0
    blueGreen:
      activeService: <name>
      previewService: <name>
      autoPromotionEnabled: true
      scaleDownDelaySeconds: 30

  # Pod spec
  template: {}

  # Lifecycle
  progressDeadlineSeconds: 600
```

---

## 2. AnalysisTemplate Examples

### 2.1 Prometheus — Success Rate

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate-check
  namespace: <namespace>
spec:
  args:
    - name: service-name
  metrics:
    - name: success-rate
      interval: 30s
      count: 5
      successCondition: result[0] >= 0.95   # 95% success
      failureLimit: 1                       # 1 point fail = fail
      inconclusiveLimit: 2
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(
              http_requests_total{
                job="{{args.service-name}}",
                status!~"5.."
              }[1m]
            ))
            /
            sum(rate(
              http_requests_total{
                job="{{args.service-name}}"
              }[1m]
            ))
```

### 2.2 Prometheus — P95 Latency

```yaml
    - name: p95-latency
      interval: 1m
      count: 3
      successCondition: result[0] <= 1000   # 1000ms = 1s
      failureLimit: 1
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            histogram_quantile(
              0.95,
              sum(rate(
                http_request_duration_ms_bucket{
                  job="{{args.service-name}}"
                }[5m]
              )) by (le)
            )
```

### 2.3 Prometheus — Error Budget

```yaml
    - name: error-budget
      interval: 30s
      count: 5
      successCondition: result[0] < 0.01   # < 1% errors
      failureLimit: 1
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(
              http_requests_total{
                job="{{args.service-name}}",
                status=~"5.."
              }[1m]
            ))
            /
            sum(rate(
              http_requests_total{
                job="{{args.service-name}}"
              }[1m]
            ))
```

### 2.4 Datadog

```yaml
    - name: success-rate
      interval: 1m
      count: 5
      successCondition: result[0] >= 0.98
      provider:
        datadog:
          apiVersion: v2
          interval: 60000       # ms
          query: |
            avg(last_5m) {
              check: http.server.hits,
              service: "{{args.service-name}}",
              status: "ok"
            }
          parse: |
            json "result" path ["series", 0, "pointlist"]
```

### 2.5 Web — Health Check

```yaml
    - name: web-health
      interval: 1m
      count: 3
      successCondition: result[0] == 200
      failureLimit: 1
      provider:
        job:
          spec:
            parallelism: 1
            completions: 1
            template:
              spec:
                restartPolicy: Always
                containers:
                  - name: health-check
                    image: curlimages/curl:8.5
                    command:
                      - sh
                      - -c
                      - |
                        STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
                          http://{{args.service-name}}/healthz)
                        echo "HTTP: $STATUS"
                        exit $((STATUS >= 400))
```

### 2.6 Multi-Metric AnalysisTemplate

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: full-quality-check
spec:
  args:
    - name: service-name
  metrics:
    - name: success-rate
      successCondition: result[0] >= 0.95
      provider:
        prometheus:
          address: http://prometheus:9090
          query: ...
    - name: p95-latency
      successCondition: result[0] <= 500
      provider:
        prometheus:
          address: http://prometheus:9090
          query: ...
    - name: error-budget
      successCondition: result[0] < 0.01
      provider:
        prometheus:
          address: http://prometheus:9090
          query: ...
```

---

## 3. Traffic Shaping Comparison

| Method | Version | Config complexity | Traffic control | Header routing | Cost |
|--------|---------|-----------------|-----------------|---------------|------|
| **Replica-based** | All | None | Weight via pod count | No | Free |
| **Istio** | v1alpha3 | High | % + L7 | Yes (header-based) | High (sidecar) |
| **NGINX Ingress** | v1 | Medium | % via upstream | No | Low |
| **SMI** | v1alpha2 | Medium | % (abstraction) | Limited | Low |
| **AWS ALB** | — | Medium | Weighted target group | No | ~$0.008/LCU |
| **Gateway API** | v1 | Medium | % + filters | Yes | Low |

### Service mesh integration examples

**Istio VirtualService:**

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: orders-api
spec:
  hosts:
    - orders-api
  http:
    - route:
        - destination:
            host: orders-api-stable
            subset: v1
          weight: 75
        - destination:
            host: orders-api-canary
            subset: v2
          weight: 25
```

**NGINX Ingress annotation:**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "25"
    nginx.ingress.kubernetes.io/canary-by-header: "X-Canary"
    nginx.ingress.kubernetes.io/canary-by-header-value: "always"
```

---

## 4. Decision Tree: Khi nao dung gi?

```
Muon progressive delivery?
├─ Co
│   ├─ Co database schema change?
│   │   ├─ Co → Blue-Green (rollback instant)
│   │   └─ Khong → Canary
│   ├─ Chi co ClusterIP (khong service mesh)?
│   │   └─ Replica-based canary (steps 25/50/75/100)
│   └─ Co Prometheus metrics?
│       ├─ Co → AnalysisTemplate (automated promotion)
│       └─ Khong → Manual pause (kubectl argo rollouts promote)
└─ Khong
    └─ Kubernetes Deployment + RollingUpdate (default)
```

```
Canary hay Blue-Green?
├─ Cost (2x resource)?
│   ├─ La van de → Canary
│   └─ Khong la van de → Blue-Green (simpler)
├─ Can rollback instant?
│   └─ Co → Blue-Green (switch selector = 0s)
├─ Can test truoc khi switch?
│   └─ Co → Blue-Green (preview service)
└─ Chi can gradual traffic shift?
    └─ Canary (setWeight steps)
```

---

## 5. Anti-Patterns Checklist

- [ ] `autoPromotionEnabled: true` khong co AnalysisTemplate → bug auto-promote to production
- [ ] Canary nhung khong co pause → 100% traffic sang version moi ngay lap tuc
- [ ] `failureLimit: 0` cho AnalysisTemplate → metric fail = rollout fail ngay
- [ ] Rollout + Deployment cung app → conflict, Rollout override Deployment
- [ ] AnalysisTemplate query tra null hoac NaN → Inconclusive forever
- [ ] Replica-based canary nhung chi co 1 replica → weight 25% = 0 pod
- [ ] Blue-green khong co `scaleDownDelaySeconds` → v1 bi xoa truoc khi v2 ready
- [ ] `maxUnavailable: 100%` → tat ca pod bi kill cung luc
- [ ] Rollback bang `git revert` thay vi `kubectl argo rollouts undo` → chu ky qua lau
- [ ] Canary nhung khong co canaryService/stableService → traffic khong split duoc
- [ ] Prometheus khong co metric → AnalysisRun inconclusive → rollout stalled
- [ ] `startingStep` lon hon so step thuc te → analysis khong bao gio chay
- [ ] `ttlSecondsAfterFinished` tren Rollout → Rollout CR bi xoa sau 1 gio → history mat
- [ ] Khong commit Rollout thay vi apply truc tiep → ArgoCD drift detection bi bypass
- [ ] Deploy nhieu Rollout cung namespace ma khong co `namePrefix` → name conflict

---

## 6. Common Errors Reference

| Error | Nguyen nhan | Fix |
|-------|------------|-----|
| `Rollout not found` | kubectl context sai cluster | `kubectl config use-context <cluster>` |
| `AnalysisRun Inconclusive` | Prometheus metric not found | Verify metric ton tai: `curl prometheus:9090/api/v1/query` |
| `Replicaset not available` | Image pull fail | `kubectl describe replicaset` |
| `Strategy conflict` | Rollout + Deployment cung app | Xoa Deployment truoc |
| `Canary stuck at step N` | Pause chua duoc promote | `kubectl argo rollouts promote <name>` |
| `Service selector match zero pod` | Label `rollouts-pod-template-hash` chua duoc patch | Verify Rollout canary service label |
| `Webhook timeout` | Istio sidecar chua ready | Them wait hook |
| `Rollback khong roll ve` | Stable RS bi xoa (history=0) | Set `revisionHistoryLimit: 3` |
| `Ingress canary not working` | Annotation nam o sai vi tri | Ingress annotation phai dung `canary: "true"` |
| `ArgoCD drift` | Rollout status thay doi nhung Git chua cap nhat | Sync ArgoCD de cap nhat |

---

## 7. Argo Rollouts CLI Quick Reference

```bash
# Install
brew install argoproj/tap/kubectl-argo-rollouts

# Watch rollout status
kubectl argo rollouts get rollout <name> -n <ns> --watch

# List rollouts
kubectl argo rollouts list rollouts -n <ns>

# Promote (next step)
kubectl argo rollouts promote <name> -n <ns>

# Abort
kubectl argo rollouts abort <name> -n <ns>

# Rollback (ve stable version truoc)
kubectl argo rollouts undo <name> -n <ns>

# Restart (restart tat ca replicas)
kubectl argo rollouts restart <name> -n <ns>

# Pause
kubectl argo rollouts pause <name> -n <ns>

# Resume
kubectl argo rollouts resume <name> -n <ns>

# Set image (khong can edit YAML)
kubectl argo rollouts set image <name> <container>=<image> -n <ns>

# History
kubectl argo rollouts history <name> -n <ns>

# Rollback ve revision cu the
kubectl argo rollouts undo <name> --to-revision=3 -n <ns>

# Analysis
kubectl argo rollouts analysis get <name> -n <ns>
kubectl argo rollouts analysis logs <name> -n <ns>

# Dashboard (web UI)
kubectl argo rollouts dashboard -n <ns>

# Retry
kubectl argo rollouts retry <name> -n <ns>
```

---

## 8. Argo Rollouts Architecture

```
Argo Rollouts Architecture
=========================

┌─────────────────────────────────────────────────────────┐
│  Git Repository                                         │
│  (Rollout YAML + AnalysisTemplate YAML)                 │
└────────────────────┬──────────────────────────────────┘
                     │ pull
                     ▼
┌─────────────────────────────────────────────────────────┐
│  ArgoCD Application                                     │
│  spec.source.path: services/orders-app/base            │
└────────────────────┬──────────────────────────────────┘
                     │ sync
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Argo Rollouts Controller (argo-rollouts namespace)    │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ReplicaSet Controller                          │   │
│  │  - Stable ReplicaSet (v1)                       │   │
│  │  - Canary ReplicaSet (v2)                       │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  Analysis Controller                            │   │
│  │  - Query Prometheus → AnalysisRun               │   │
│  │  - Success → promote / Fail → abort             │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  Traffic Manager (Istio/NGINX/SMI)              │   │
│  │  - Update VirtualService / Ingress              │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────┬──────────────────────────────────┘
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
┌──────────────┐           ┌──────────────┐
│ Stable SVC   │           │ Canary SVC   │
│ (orders-v1)  │           │ (orders-v2)  │
└──────────────┘           └──────────────┘
```

---

## 9. Migration Checklist: Deployment → Rollout

```
1. Backup
   □ kubectl get deployment <name> -n <ns> -o yaml > backup.yaml

2. Update YAML
   □ apiVersion: argoproj.io/v1alpha1
   □ kind: Rollout
   □ spec.strategy: canary hoac blueGreen

3. Add services (canary requires 2 service)
   □ stableService: <name>-stable
   □ canaryService: <name>-canary

4. Remove Deployment-specific fields
   □ spec.strategy.rollingUpdate (thay bang strategy.canary)

5. Commit to Git (de ArgoCD sync)
   □ git add ... && git commit && git push

6. Verify
   □ kubectl argo rollouts get rollout <name> -n <ns>
   □ argocd app sync <app-name>

7. Test rollback
   □ kubectl argo rollouts undo <name> -n <ns>
   □ Verify stable version running
```
