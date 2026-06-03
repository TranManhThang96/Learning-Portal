# Day 25: Document — Harden, Scale & Debug Kubernetes App

## 1. Hardened BookStore — Complete YAML Manifests

### Namespace & Labels

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: bookstore
  labels:
    team: product
    environment: production
```

### ServiceAccounts

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: frontend-sa
  namespace: bookstore
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway-sa
  namespace: bookstore
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: book-service-sa
  namespace: bookstore
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: redis-sa
  namespace: bookstore
```

### RBAC

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: configmap-reader
  namespace: bookstore
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-gateway-cm-reader
  namespace: bookstore
subjects:
  - kind: ServiceAccount
    name: api-gateway-sa
    namespace: bookstore
roleRef:
  kind: Role
  name: configmap-reader
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: book-service-cm-reader
  namespace: bookstore
subjects:
  - kind: ServiceAccount
    name: book-service-sa
    namespace: bookstore
roleRef:
  kind: Role
  name: configmap-reader
  apiGroup: rbac.authorization.k8s.io
```

### Deployments (Hardened)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
  labels:
    app: frontend
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    metadata:
      labels:
        app: frontend
        team: product
        environment: production
    spec:
      serviceAccountName: frontend-sa
      terminationGracePeriodSeconds: 30
      containers:
        - name: web
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bookstore
  labels:
    app: api-gateway
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    metadata:
      labels:
        app: api-gateway
        team: product
        environment: production
    spec:
      serviceAccountName: api-gateway-sa
      terminationGracePeriodSeconds: 30
      containers:
        - name: gateway
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-service
  namespace: bookstore
  labels:
    app: book-service
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 2
  selector:
    matchLabels:
      app: book-service
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    metadata:
      labels:
        app: book-service
        team: product
        environment: production
    spec:
      serviceAccountName: book-service-sa
      terminationGracePeriodSeconds: 30
      containers:
        - name: service
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: bookstore
  labels:
    app: redis
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
        team: product
        environment: production
    spec:
      serviceAccountName: redis-sa
      terminationGracePeriodSeconds: 30
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
            periodSeconds: 5
```

### Services

```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend-svc
  namespace: bookstore
spec:
  selector:
    app: frontend
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway-svc
  namespace: bookstore
spec:
  selector:
    app: api-gateway
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: book-service-svc
  namespace: bookstore
spec:
  selector:
    app: book-service
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: redis-svc
  namespace: bookstore
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

### HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: bookstore
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: book-service-hpa
  namespace: bookstore
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: book-service
  minReplicas: 2
  maxReplicas: 4
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### PDB

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: frontend-pdb
  namespace: bookstore
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: frontend
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: bookstore
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: api-gateway
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: book-service-pdb
  namespace: bookstore
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: book-service
```

### NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: bookstore
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: bookstore
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels: {app: frontend}
  policyTypes: [Ingress, Egress]
  ingress:
    - from: []
      ports: [{port: 80}]
  egress:
    - to:
        - podSelector:
            matchLabels: {app: api-gateway}
      ports: [{port: 80}]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-gateway-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels: {app: api-gateway}
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels: {app: frontend}
      ports: [{port: 80}]
  egress:
    - to:
        - podSelector:
            matchLabels: {app: book-service}
      ports: [{port: 80}]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: book-service-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels: {app: book-service}
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels: {app: api-gateway}
      ports: [{port: 80}]
  egress:
    - to:
        - podSelector:
            matchLabels: {app: redis}
      ports: [{port: 6379}]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: redis-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels: {app: redis}
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels: {app: book-service}
      ports: [{port: 6379}]
```

---

## 2. Security Checklist (Filled)

| # | Item | Status | Notes |
|---|------|--------|-------|
| S1 | Dedicated ServiceAccount | ✅ | frontend-sa, api-gateway-sa, book-service-sa, redis-sa |
| S2 | RBAC least privilege | ✅ | configmap-reader Role only |
| S3 | Pod Security Standards | ⬜ | Not enforced (future work) |
| S4 | NetworkPolicy default deny | ✅ | default-deny-all + explicit allow |
| S5 | Non-root containers | ⬜ | nginx needs config change |
| S6 | Read-only root filesystem | ⬜ | nginx needs writable /var/cache |
| S7 | Image scanning | ⬜ | No CI/CD yet (Phase 5) |
| S8 | Trusted registry only | ✅ | Kyverno policy (Audit mode) |
| S9 | Secret encryption at rest | ⬜ | Cluster-level config needed |
| S10 | Admission policies | ✅ | Kyverno: privileged, resources, labels |
| S11 | No privileged containers | ✅ | Kyverno Enforce |

**Score: 6/11 (55%)**

---

## 3. Scaling Test Report Template

```markdown
# Scaling Test Report — BookStore Platform

## Test Environment
- Cluster: kind (3 workers, 2 CPU / 4GB each)
- Date: YYYY-MM-DD
- Tester: [name]

## Baseline (Before Load)

| Service | Replicas | CPU Usage | Memory Usage | HPA Target |
|---------|----------|-----------|--------------|------------|
| frontend | 2 | 2m/100m | 5Mi/128Mi | N/A |
| api-gateway | 2 | 3m/200m | 8Mi/256Mi | 70% CPU |
| book-service | 2 | 2m/200m | 7Mi/256Mi | 70% CPU |
| redis | 1 | 1m/100m | 3Mi/128Mi | N/A |

## Load Test Config
- Tool: hey / k6 / curl loop
- Duration: 5 minutes
- Concurrency: 10/50/100

## Results Under Load

| Concurrency | api-gateway Replicas | book-service Replicas | P99 Latency | Error Rate |
|-------------|---------------------|----------------------|-------------|------------|
| 10 | 2 | 2 | 5ms | 0% |
| 50 | 3 | 2 | 12ms | 0% |
| 100 | 4 | 3 | 45ms | 0.1% |

## HPA Behavior
- Scale up triggered at: XX:XX
- Scale up completed at: XX:XX (delta: X min)
- Scale down triggered at: XX:XX
- Scale down completed at: XX:XX (delta: X min)
- Max replicas reached: api-gateway=4, book-service=3

## Observations
- [Finding 1]
- [Finding 2]

## Recommendations
- [Recommendation 1]
- [Recommendation 2]
```

---

## 4. Runbook Examples (5 Required)

### Runbook 1: Service OOMKilled

**Symptom**: Pod restart liên tục, `kubectl describe` hiển thị `Reason: OOMKilled`, Exit Code: 137.

**Severity**: P2

**Detection**: Alert `KubePodCrashLooping` hoặc `container_memory_working_set_bytes > limit`.

**Debug Steps**:
```bash
# 1. Confirm OOMKilled
kubectl describe pod <pod> -n bookstore | grep -A3 "Last State"

# 2. Check memory limit
kubectl get pod <pod> -n bookstore -o jsonpath='{.spec.containers[0].resources.limits.memory}'

# 3. Check actual usage (nếu pod đang Running)
kubectl top pod <pod> -n bookstore

# 4. Check application memory pattern
kubectl logs <pod> -n bookstore --previous | grep -i "memory\|heap\|alloc"
```

**Fix**:
```bash
# Tăng memory limit
kubectl patch deployment <deploy> -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}]'
```

**Verify**:
```bash
kubectl get pods -n bookstore -l app=<app>
# Status: Running, Restarts: 0
```

**Prevention**: Monitor memory usage trends. Set limits ≥ 2x average usage. Alert khi usage > 80% limit.

---

### Runbook 2: Service Routing Failure (Empty Endpoints)

**Symptom**: Service trả về connection refused hoặc no response. curl từ pod khác fail.

**Severity**: P1

**Detection**: Alert `KubeServiceWithNoEndpoints`.

**Debug Steps**:
```bash
# 1. Check endpoints
kubectl get endpoints <svc> -n bookstore
# Nếu <none> → selector mismatch

# 2. Compare selectors
kubectl get svc <svc> -n bookstore -o jsonpath='{.spec.selector}'
kubectl get pods -n bookstore --show-labels | grep <app>

# 3. Check pod readiness
kubectl get pods -n bookstore -l app=<app>
# Pods phải Running + Ready (1/1)
```

**Fix**:
```bash
# Nếu selector mismatch:
kubectl patch svc <svc> -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/selector/app","value":"<correct-value>"}]'

# Nếu pods not ready: fix readiness probe hoặc app issue
```

**Verify**:
```bash
kubectl get endpoints <svc> -n bookstore
# Phải có IP addresses
kubectl exec -n bookstore deploy/<caller> -- curl -s http://<svc>
```

**Prevention**: CI/CD validate service selectors match deployment labels. Monitor endpoint count.

---

### Runbook 3: ImagePullBackOff

**Symptom**: Pod stuck ở ImagePullBackOff. Deployment rollout stuck.

**Severity**: P2

**Debug Steps**:
```bash
kubectl describe pod <pod> -n bookstore | grep -A5 "Events"
# "Failed to pull image" → check image name
# "unauthorized" → check imagePullSecrets
# "timeout" → check network
```

**Fix**: Sửa image name/tag, hoặc tạo imagePullSecret, hoặc fix network.

**Verify**: `kubectl get pods -n bookstore` → Running.

**Prevention**: Kyverno policy restrict image registries. CI/CD verify image exists before deploy.

---

### Runbook 4: Pod Pending (Insufficient Resources)

**Symptom**: Pod stuck Pending. `kubectl describe` hiển thị `FailedScheduling`.

**Severity**: P2

**Debug Steps**:
```bash
kubectl describe pod <pod> -n bookstore | grep -A5 "Events"
# "Insufficient cpu/memory" → node resources
kubectl describe nodes | grep -A15 "Allocated resources"
```

**Fix**: Reduce resource requests, add nodes, hoặc evict low-priority workloads.

**Verify**: `kubectl get pods -n bookstore` → Running.

**Prevention**: Cluster autoscaler. Monitor node resource utilization. ResourceQuota per namespace.

---

### Runbook 5: High Latency / CPU Throttling

**Symptom**: Service latency P99 tăng đột ngột. CPU usage trên dashboard có vẻ bình thường.

**Severity**: P2

**Debug Steps**:
```bash
# 1. Check CPU throttling
kubectl exec <pod> -n bookstore -- cat /sys/fs/cgroup/cpu/cpu.stat 2>/dev/null
# nr_throttled > 0 = bị throttle

# 2. Check CPU limit vs usage
kubectl top pod <pod> -n bookstore
kubectl get pod <pod> -n bookstore -o jsonpath='{.spec.containers[0].resources.limits.cpu}'

# 3. Check HPA
kubectl get hpa -n bookstore
```

**Fix**:
```bash
# Tăng CPU limit hoặc remove CPU limit (chỉ giữ requests)
kubectl patch deployment <deploy> -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"500m"}]'
```

**Verify**: Latency P99 giảm về baseline. `nr_throttled` không tăng.

**Prevention**: Monitor `container_cpu_cfs_throttled_periods_total`. Consider removing CPU limits. HPA scale trước khi throttle.

---

## 5. Before/After Comparison

| Area | Before (Day 17) | After (Day 25) |
|------|-----------------|----------------|
| **Replicas** | 1 per service | 2 per stateless |
| **Resource Requests** | None | All containers |
| **Resource Limits** | None | All containers |
| **Liveness Probe** | None | All services |
| **Readiness Probe** | None | All services |
| **HPA** | None | api-gateway + book-service |
| **PDB** | None | 3 PDBs |
| **ServiceAccount** | default | Dedicated per service |
| **RBAC** | None | Least privilege roles |
| **NetworkPolicy** | None | Default deny + explicit |
| **Admission Policy** | None | 3 Kyverno policies |
| **Labels** | app only | app + team + env + cost |
| **Runbooks** | None | 5 runbooks |
| **Production Score** | ~0% | ~60% |

---

## 6. kubectl Quick Reference for this Project

```bash
# === STATUS ===
kubectl get all -n bookstore
kubectl get pods -n bookstore -o wide
kubectl get hpa -n bookstore
kubectl get pdb -n bookstore
kubectl get networkpolicy -n bookstore
kubectl get sa -n bookstore
kubectl get clusterpolicy

# === DEBUG ===
kubectl describe pod <pod> -n bookstore
kubectl logs <pod> -n bookstore [--previous]
kubectl exec -it <pod> -n bookstore -- /bin/sh
kubectl get events -n bookstore --sort-by=.lastTimestamp
kubectl top pods -n bookstore

# === VERIFY ===
kubectl get endpoints -n bookstore
kubectl auth can-i <verb> <resource> --as=system:serviceaccount:bookstore:<sa> -n bookstore
kubectl exec -n bookstore deploy/<pod> -- curl -s http://<svc>
kubectl exec -n bookstore deploy/<pod> -- nslookup <svc>

# === CLEANUP ===
helm uninstall kyverno -n kyverno
kubectl delete namespace kyverno
kubectl delete namespace bookstore
kind delete cluster --name bookstore-prod
```

