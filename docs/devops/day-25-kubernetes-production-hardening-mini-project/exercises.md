# Day 25: Exercises — Harden, Scale & Debug Kubernetes App

---

## Bài 1: Easy — Resource Limits + HPA cho Single Service

### Context

Bạn được giao hardening service `api-gateway` trong BookStore stack. Bắt đầu từ deployment không có resources, không có probes, 1 replica.

### Yêu cầu

1. Tạo kind cluster với metrics-server.
2. Deploy `api-gateway` (nginx, 1 replica, không resources/probes).
3. Thêm resource requests/limits (CPU: 100m/200m, memory: 128Mi/256Mi).
4. Thêm liveness + readiness probes (HTTP GET /).
5. Tăng replicas lên 2.
6. Tạo HPA (target 70% CPU, min 2, max 5).
7. Tạo PDB (minAvailable: 1).
8. Verify tất cả bằng `kubectl get`.

### Expected Outcome

- Pod Running với resources, probes đúng.
- HPA hiển thị target metrics.
- PDB hiển thị ALLOWED DISRUPTIONS > 0.

### Hint

- metrics-server trên kind cần flag `--kubelet-insecure-tls`.
- HPA cần vài phút để lấy metrics lần đầu.
- Dùng `kubectl top pods` để verify metrics-server hoạt động.

### Acceptance Criteria

- [ ] Deployment có resources requests/limits.
- [ ] Liveness + readiness probes configured.
- [ ] Replicas = 2.
- [ ] HPA created, showing targets.
- [ ] PDB created, ALLOWED DISRUPTIONS = 1.
- [ ] `kubectl top pods` trả về metrics.

### Bonus Challenge

Tạo load bằng `kubectl run load-gen --image=busybox -- sh -c "while true; do wget -q -O- http://api-gateway-svc; done"` và quan sát HPA scale up.

<details>
<summary>Solution</summary>

```bash
# 1. Cluster + metrics-server
kind create cluster --name hpa-lab
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system --type json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl wait --for=condition=Available deployment/metrics-server -n kube-system --timeout=120s

# 2. Base deployment
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: gateway
          image: nginx:1.25
          ports: [{containerPort: 80}]
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway-svc
spec:
  selector:
    app: api-gateway
  ports: [{port: 80, targetPort: 80}]
EOF

# 3-6. Hardened deployment + HPA + PDB
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: gateway
          image: nginx:1.25
          ports: [{containerPort: 80}]
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 200m, memory: 256Mi}
          livenessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: api-gateway
EOF

# 7. Verify
sleep 30
kubectl get pods
kubectl get hpa
kubectl get pdb
kubectl top pods

# Bonus: Load test
kubectl run load-gen --image=busybox --restart=Never -- \
  sh -c "while true; do wget -q -O- http://api-gateway-svc > /dev/null 2>&1; done"
# Watch HPA:
# kubectl get hpa -w
# After ~2 min, should see replicas increase

# Cleanup
kubectl delete pod load-gen
kind delete cluster --name hpa-lab
```

</details>

---

## Bài 2: Medium — Full Security Hardening (RBAC + NetworkPolicy + Kyverno)

### Context

BookStore stack đang chạy trên shared cluster. Security team audit và phát hiện:
- Tất cả services dùng default ServiceAccount (có token mount).
- Không có NetworkPolicy → mọi pod giao tiếp tự do.
- Không có admission policies → developer có thể deploy privileged pods.

### Yêu cầu

1. Deploy BookStore stack (4 services) trong namespace `bookstore`.
2. **RBAC**:
   - Tạo ServiceAccount riêng cho mỗi service.
   - Tạo Role `configmap-reader` (get/list configmaps).
   - Bind Role cho api-gateway-sa và book-service-sa.
   - Verify với `kubectl auth can-i`.
3. **NetworkPolicy**:
   - Default deny all ingress + egress.
   - Allow DNS egress cho tất cả pods.
   - Frontend: ingress from anywhere, egress to api-gateway.
   - API Gateway: ingress from frontend, egress to book-service.
   - Book Service: ingress from api-gateway, egress to redis.
   - Redis: ingress from book-service only.
4. **Kyverno**:
   - Install Kyverno.
   - Policy 1: Require labels `team` (Enforce).
   - Policy 2: Require resource limits (Enforce).
   - Policy 3: Block privileged containers (Enforce).
   - Verify mỗi policy bằng test case (violating + compliant).
5. **Verification**:
   - Test connectivity: frontend → api-gateway (allowed), frontend → redis (blocked).
   - Test RBAC: api-gateway-sa can get configmaps, cannot list pods.
   - Test policies: create violating pod (should be blocked).

### Expected Outcome

- 4 dedicated ServiceAccounts with least privilege.
- NetworkPolicy isolates services correctly.
- 3 Kyverno policies Enforced.
- All tests pass.

### Hint

- NetworkPolicy cần cho phép DNS egress (UDP/TCP port 53) trước khi default deny.
- Kyverno policies cần `exclude` kube-system và kyverno namespaces.
- Test connectivity bằng `kubectl exec -- curl/nc`.

### Acceptance Criteria

- [ ] 4 ServiceAccounts created, bound to deployments.
- [ ] RBAC verified: can-i get configmaps=yes, can-i list pods=no.
- [ ] 6+ NetworkPolicies deployed.
- [ ] Connectivity test: allowed paths work, blocked paths fail.
- [ ] 3 Kyverno policies Enforced.
- [ ] Violation test: privileged pod blocked, pod without resources blocked.
- [ ] All bookstore pods still Running after all changes.

### Bonus Challenge

Thêm Kyverno **generate policy**: khi tạo Namespace mới, tự động tạo NetworkPolicy default deny + LimitRange. Test bằng cách tạo namespace mới.

<details>
<summary>Solution</summary>

```bash
kind create cluster --name security-lab

# Deploy BookStore
kubectl create namespace bookstore
# (apply base deployment manifests from lesson.md section 3.2)

# === RBAC ===
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata: {name: frontend-sa, namespace: bookstore}
---
apiVersion: v1
kind: ServiceAccount
metadata: {name: api-gateway-sa, namespace: bookstore}
---
apiVersion: v1
kind: ServiceAccount
metadata: {name: book-service-sa, namespace: bookstore}
---
apiVersion: v1
kind: ServiceAccount
metadata: {name: redis-sa, namespace: bookstore}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: configmap-reader, namespace: bookstore}
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: api-gw-cm-reader, namespace: bookstore}
subjects:
  - kind: ServiceAccount
    name: api-gateway-sa
    namespace: bookstore
roleRef: {kind: Role, name: configmap-reader, apiGroup: rbac.authorization.k8s.io}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: book-svc-cm-reader, namespace: bookstore}
subjects:
  - kind: ServiceAccount
    name: book-service-sa
    namespace: bookstore
roleRef: {kind: Role, name: configmap-reader, apiGroup: rbac.authorization.k8s.io}
EOF

# Patch deployments
for svc in frontend api-gateway book-service redis; do
  kubectl patch deployment $svc -n bookstore --type json \
    -p "[{\"op\":\"add\",\"path\":\"/spec/template/spec/serviceAccountName\",\"value\":\"${svc}-sa\"}]"
done

# Verify RBAC
kubectl auth can-i get configmaps --as=system:serviceaccount:bookstore:api-gateway-sa -n bookstore
# yes
kubectl auth can-i list pods --as=system:serviceaccount:bookstore:api-gateway-sa -n bookstore
# no

# === NetworkPolicy ===
# (apply manifests from lesson.md Task 4)

# === Kyverno ===
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno -n kyverno --create-namespace --set replicaCount=1
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kyverno -n kyverno --timeout=120s

# (apply policies from lesson.md Task 5)

# Test violation
kubectl run test-priv -n bookstore --image=nginx:1.25 \
  --overrides='{"spec":{"containers":[{"name":"t","image":"nginx:1.25","securityContext":{"privileged":true},"resources":{"requests":{"cpu":"50m","memory":"64Mi"},"limits":{"cpu":"100m","memory":"128Mi"}}}]}}' 2>&1
# Expected: blocked

# Cleanup
kind delete cluster --name security-lab
```

</details>

---

## Bài 3: Hard — Full Incident Simulation, Debug & Runbook

### Context

Bạn là on-call SRE cho BookStore platform. Đêm qua có ai đó "vô tình" introduce 5 bugs vào production. Sáng nay dashboard đỏ lửa: pods crashing, services unreachable, latency spike.

### Yêu cầu

1. Deploy **hardened** BookStore stack (đã có resources, probes, PDB, NetworkPolicy).
2. **Inject 5 bugs** (theo script bên dưới — KHÔNG đọc trước bugs).
3. **Debug từng bug** theo systematic methodology (Day 22):
   - Identify symptom
   - Scope the problem
   - Form hypothesis
   - Verify
   - Mitigate/Fix
4. **Viết incident note** cho mỗi bug (template chuẩn).
5. **Viết 5 runbooks** cho mỗi loại failure encountered.
6. **Tạo scaling test report**: trước/sau fix, bao gồm pod count, resource usage, HPA status.
7. **Tính production readiness score** trước inject bugs vs sau fix.

### Bug Injection Script (chạy sau khi deploy stack hoàn chỉnh)

```bash
# inject-bugs.sh — Chạy rồi debug!
#!/bin/bash
echo "Injecting 5 bugs into bookstore namespace..."

# Bug 1: ???
kubectl set image deployment/frontend -n bookstore web=nginx:999-nonexistent

# Bug 2: ???
kubectl patch deployment api-gateway -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"5Mi"}]'

# Bug 3: ???
kubectl patch svc book-service-svc -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/selector/app","value":"book-service-v99"}]'

# Bug 4: ???
kubectl patch deployment book-service -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/nonexistent-health"}]'

# Bug 5: ???
kubectl delete networkpolicy allow-dns -n bookstore 2>/dev/null
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: block-everything
  namespace: bookstore
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
EOF

echo "5 bugs injected. Good luck debugging!"
```

### Expected Outcome

- Tất cả 5 bugs identified, diagnosed, và fixed.
- 5 incident notes theo template chuẩn.
- 5 runbooks viết chất lượng.
- Scaling test report có data thực tế.
- Total debug time < 45 phút.

### Hint

Bugs (KHÔNG đọc trước khi debug):
1. ImagePullBackOff (wrong image tag)
2. OOMKilled (memory limit 5Mi)
3. Service routing (selector mismatch)
4. Liveness probe fail (/nonexistent-health → 404 → restart loop)
5. NetworkPolicy blocks ALL including DNS

Debug order suggestion: Fix NetworkPolicy/DNS trước (affects everything), rồi từng service.

### Acceptance Criteria

- [ ] 5 bugs identified chính xác (symptom + root cause).
- [ ] 5 bugs fixed, tất cả pods Running + Ready.
- [ ] 5 incident notes có: severity, timeline, root cause, fix, prevention.
- [ ] 5 runbooks có: symptom, detection, debug steps, fix, verify, prevention.
- [ ] Scaling test report: pod count, resource usage, HPA status.
- [ ] Total debug time documented.
- [ ] Production score improved after fix.

### Bonus Challenge

Viết bash script `health-check.sh` tự động kiểm tra toàn bộ namespace: pods healthy, services have endpoints, DNS works, NetworkPolicy allows required traffic. Script exit code 0 = healthy, 1 = unhealthy.

<details>
<summary>Solution</summary>

```bash
# Debug Order (recommended):

# 1. Check overall status
kubectl get pods -n bookstore
# Multiple issues visible

# 2. Fix Bug 5 FIRST (NetworkPolicy blocks DNS → affects everything)
kubectl get networkpolicy -n bookstore
# "block-everything" — too restrictive, no DNS egress
kubectl delete networkpolicy block-everything -n bookstore
# Re-apply correct NetworkPolicies (default deny + DNS allow + service-specific)
# (from lesson.md Task 4)

# 3. Fix Bug 1: frontend ImagePullBackOff
kubectl describe pod -n bookstore -l app=frontend | grep "Failed to pull"
# nginx:999-nonexistent
kubectl set image deployment/frontend -n bookstore web=nginx:1.25

# 4. Fix Bug 2: api-gateway OOMKilled
kubectl describe pod -n bookstore -l app=api-gateway | grep OOMKilled
# memory limit 5Mi
kubectl patch deployment api-gateway -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}]'

# 5. Fix Bug 3: book-service-svc routing
kubectl get endpoints book-service-svc -n bookstore
# <none>
kubectl get svc book-service-svc -n bookstore -o jsonpath='{.spec.selector}'
# app=book-service-v99 → mismatch
kubectl patch svc book-service-svc -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/selector/app","value":"book-service"}]'

# 6. Fix Bug 4: book-service liveness probe
kubectl describe pod -n bookstore -l app=book-service | grep "Liveness probe failed"
# /nonexistent-health → 404
kubectl patch deployment book-service -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/"}]'

# Verify
sleep 30
kubectl get pods -n bookstore
kubectl get endpoints -n bookstore
kubectl get hpa -n bookstore

# Bonus: health-check.sh
cat <<'SCRIPT' > health-check.sh
#!/bin/bash
NS=${1:-bookstore}
ERRORS=0

echo "=== Health Check: $NS ==="

# Check pods
NOT_RUNNING=$(kubectl get pods -n $NS --no-headers | grep -v Running | grep -v Completed | wc -l)
if [ "$NOT_RUNNING" -gt 0 ]; then
  echo "❌ $NOT_RUNNING pods not Running"
  ERRORS=$((ERRORS+1))
else
  echo "✅ All pods Running"
fi

# Check endpoints
EMPTY_EP=$(kubectl get endpoints -n $NS -o json | jq '[.items[] | select(.subsets==null or .subsets==[])] | length')
if [ "$EMPTY_EP" -gt 0 ]; then
  echo "❌ $EMPTY_EP services have no endpoints"
  ERRORS=$((ERRORS+1))
else
  echo "✅ All services have endpoints"
fi

# Check DNS
DNS_OK=$(kubectl exec -n $NS deploy/api-gateway -- nslookup kubernetes.default 2>/dev/null | grep -c "Address" || true)
if [ "$DNS_OK" -ge 1 ]; then
  echo "✅ DNS resolution working"
else
  echo "❌ DNS resolution failed"
  ERRORS=$((ERRORS+1))
fi

# Check restarts
HIGH_RESTART=$(kubectl get pods -n $NS -o json | jq '[.items[].status.containerStatuses[]? | select(.restartCount > 3)] | length')
if [ "$HIGH_RESTART" -gt 0 ]; then
  echo "⚠️  $HIGH_RESTART containers with high restart count"
  ERRORS=$((ERRORS+1))
else
  echo "✅ No high restart counts"
fi

echo ""
if [ "$ERRORS" -eq 0 ]; then
  echo "✅ HEALTHY"
  exit 0
else
  echo "❌ UNHEALTHY ($ERRORS issues)"
  exit 1
fi
SCRIPT
chmod +x health-check.sh
```

</details>

---

## Solution/Reference Implementation

Các lời giải chi tiết nằm trong block `<details><summary>Solution</summary>` của từng bài để người học có thể thử trước khi mở đáp án. Reference cuối file:

- **Bài 1 — Easy**: harden một service bằng resources, probes, replicas, HPA và PDB; verify bằng `kubectl get/top/describe`.
- **Bài 2 — Medium**: áp RBAC least privilege, NetworkPolicy default deny + explicit allow, Kyverno policies và test violation.
- **Bài 3 — Hard**: inject 5 incidents, debug theo thứ tự ưu tiên, fix từng lỗi và tạo health-check script/runbook.

