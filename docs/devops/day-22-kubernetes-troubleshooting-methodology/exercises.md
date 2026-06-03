# Day 22: Exercises — Kubernetes Troubleshooting Methodology

---

## Bài 1: Easy — Debug Pod Cơ Bản

### Context

Bạn vừa nhận được alert: "Service `user-api` trả về 503." Bạn cần debug và fix nhanh nhất có thể.

### Yêu cầu

1. Tạo kind cluster.
2. Deploy 3 workloads có lỗi sau:
   - **Deployment A**: `user-api` với image sai (`nginx:does-not-exist`).
   - **Deployment B**: `order-service` với command crash ngay (`exit 1`).
   - **Deployment C**: `payment-service` chạy OK nhưng Service selector sai (label mismatch).
3. Dùng quy trình debug hệ thống (symptom → scope → hypothesis → verification → fix) cho từng lỗi.
4. Viết lại từng bước debug đã làm (command + output tóm tắt).

### Expected Outcome

- Tất cả 3 deployments Running, Ready.
- Service `payment-service` có endpoints.
- Biết phân biệt ImagePullBackOff vs CrashLoopBackOff vs Service routing.

### Hint

- Bước đầu tiên luôn là `kubectl get pods` → `kubectl describe pod <name>`.
- ImagePullBackOff: check events trong describe.
- CrashLoopBackOff: check `kubectl logs --previous`.
- Service routing: check `kubectl get endpoints`.

### Acceptance Criteria

- [ ] 3 lỗi khác nhau deployed thành công.
- [ ] Từng lỗi debug đúng flow: describe → logs/events → identify → fix.
- [ ] Tất cả pods Running sau fix.
- [ ] Service có endpoints sau fix.
- [ ] Ghi lại debug steps cho từng lỗi (≥ 3 commands mỗi lỗi).

### Bonus Challenge

Thêm lỗi thứ 4: Pod OOMKilled (dùng `stress` image với memory vượt limit). Debug và fix.

<details>
<summary>Solution</summary>

```bash
# Tạo cluster
kind create cluster --name debug-easy

# === Bug A: ImagePullBackOff ===
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: user-api
  template:
    metadata:
      labels:
        app: user-api
    spec:
      containers:
        - name: api
          image: nginx:does-not-exist
          ports:
            - containerPort: 80
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
EOF

# Debug A:
kubectl get pods
# user-api-xxx   0/1   ImagePullBackOff

kubectl describe pod -l app=user-api
# Events: "Failed to pull image nginx:does-not-exist"

# Fix A:
kubectl set image deployment/user-api api=nginx:1.25

# === Bug B: CrashLoopBackOff ===
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
        - name: order
          image: busybox:1.36
          command: ["sh", "-c", "echo 'Starting order-service' && exit 1"]
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
EOF

# Debug B:
kubectl get pods
# order-service-xxx   0/1   CrashLoopBackOff

kubectl logs -l app=order-service --previous
# "Starting order-service"

kubectl describe pod -l app=order-service
# Last State: Terminated, Exit Code: 1

# Fix B:
kubectl patch deployment order-service --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command","value":["sh","-c","echo Starting && sleep 3600"]}]'

# === Bug C: Service Routing ===
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payment-service
  template:
    metadata:
      labels:
        app: payment-service
        tier: backend
    spec:
      containers:
        - name: payment
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: payment-svc
spec:
  selector:
    app: payment-service
    tier: frontend
  ports:
    - port: 80
      targetPort: 80
EOF

# Debug C:
kubectl get endpoints payment-svc
# ENDPOINTS: <none>

kubectl get svc payment-svc -o jsonpath='{.spec.selector}'
# {"app":"payment-service","tier":"frontend"}

kubectl get pods -l app=payment-service --show-labels
# tier=backend → mismatch!

# Fix C:
kubectl patch svc payment-svc --type json \
  -p '[{"op":"replace","path":"/spec/selector/tier","value":"backend"}]'

kubectl get endpoints payment-svc
# Có IPs

# Verify tất cả
kubectl get pods
# Tất cả Running, Ready

# Cleanup
kind delete cluster --name debug-easy
```

</details>

---

## Bài 2: Medium — Broken Cluster Challenge (5 Bugs)

### Context

Bạn vừa được assign on-call. Platform team đã deploy một "BookStore" demo application nhưng nhiều component bị lỗi. Tìm và fix tất cả 5 bugs, viết incident note cho mỗi bug.

### Yêu cầu

1. Tạo kind cluster và deploy 5 workloads có lỗi (manifests bên dưới).
2. Không đọc trước nội dung lỗi — debug từ symptom.
3. Cho mỗi bug:
   - Xác định symptom.
   - Thu thập evidence (commands + output).
   - Đặt hypothesis.
   - Verify hypothesis.
   - Fix.
4. Viết **incident note** cho từng bug theo template:
   ```
   ## Incident: [tên lỗi]
   - Severity: P1/P2/P3
   - Duration: [thời gian debug]
   - Symptom: [mô tả ngắn]
   - Root Cause: [nguyên nhân]
   - Fix: [command/change đã làm]
   - Prevention: [làm gì để không xảy ra lại]
   ```

### Manifest để deploy

```yaml
# broken-bookstore.yaml
---
# Bug 1: ???
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: book-frontend
  template:
    metadata:
      labels:
        app: book-frontend
    spec:
      containers:
        - name: frontend
          image: ngnix:1.25
          ports:
            - containerPort: 80
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
---
# Bug 2: ???
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: book-api
  template:
    metadata:
      labels:
        app: book-api
    spec:
      containers:
        - name: api
          image: busybox:1.36
          command: ["sh", "-c", "cat /config/app.conf && sleep 3600"]
          volumeMounts:
            - name: config
              mountPath: /config
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
      volumes:
        - name: config
          configMap:
            name: book-api-config
---
# Bug 3: ???
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: book-worker
  template:
    metadata:
      labels:
        app: book-worker
    spec:
      containers:
        - name: worker
          image: polinux/stress:1.0.4
          command: ["stress", "--vm", "1", "--vm-bytes", "200M"]
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 100Mi}
---
# Bug 4: ???
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-cache
spec:
  replicas: 1
  selector:
    matchLabels:
      app: book-cache
  template:
    metadata:
      labels:
        app: book-cache
        version: v2
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: book-cache-svc
spec:
  selector:
    app: book-cache
    version: v1
  ports:
    - port: 6379
      targetPort: 6379
---
# Bug 5: ???
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-search
spec:
  replicas: 1
  selector:
    matchLabels:
      app: book-search
  template:
    metadata:
      labels:
        app: book-search
    spec:
      containers:
        - name: search
          image: nginx:1.25
          resources:
            requests: {cpu: "50", memory: "256Gi"}
            limits: {cpu: "50", memory: "256Gi"}
```

### Expected Outcome

- Tất cả 5 bugs identified, fixed, pods Running.
- 5 incident notes viết đúng template.
- Biết dùng đúng tool cho từng loại lỗi.

### Hint

- Bug types: ImagePullBackOff, CrashLoopBackOff (missing ConfigMap), OOMKilled, Service routing, Pending (resources quá lớn).
- Luôn bắt đầu bằng `kubectl get pods` → focus pod có vấn đề → `kubectl describe`.

### Acceptance Criteria

- [ ] 5 bugs found và identified chính xác.
- [ ] 5 bugs fixed, tất cả pods Running.
- [ ] Service `book-cache-svc` có endpoints.
- [ ] 5 incident notes theo đúng template.
- [ ] Mỗi incident note có ≥ 2 commands dùng để debug.

### Bonus Challenge

Sau khi fix tất cả, deploy thêm 1 `NetworkPolicy` default deny ingress trong namespace `default`. Verify rằng pods vẫn Running nhưng không giao tiếp được với nhau. Debug và viết incident note.

<details>
<summary>Solution</summary>

```bash
kind create cluster --name broken-bookstore

# Deploy broken manifests
kubectl apply -f broken-bookstore.yaml

# Chờ 30s rồi check
sleep 30
kubectl get pods

# Bug 1: book-frontend — ImagePullBackOff
# Image "ngnix" là typo (đúng: nginx)
kubectl describe pod -l app=book-frontend
# Fix:
kubectl set image deployment/book-frontend frontend=nginx:1.25

# Bug 2: book-api — CrashLoopBackOff / CreateContainerConfigError
# ConfigMap "book-api-config" không tồn tại
kubectl describe pod -l app=book-api
# "configmap 'book-api-config' not found"
# Fix: tạo ConfigMap
kubectl create configmap book-api-config --from-literal=app.conf="port=8080\nenv=dev"

# Bug 3: book-worker — OOMKilled
# stress --vm-bytes 200M > limit 100Mi
kubectl describe pod -l app=book-worker
# Reason: OOMKilled, Exit Code: 137
# Fix:
kubectl patch deployment book-worker --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"200Mi"}]'

# Bug 4: book-cache — Service routing
# Service selector version:v1 nhưng pod label version:v2
kubectl get endpoints book-cache-svc
# ENDPOINTS: <none>
# Fix:
kubectl patch svc book-cache-svc --type json \
  -p '[{"op":"replace","path":"/spec/selector/version","value":"v2"}]'
kubectl get endpoints book-cache-svc

# Bug 5: book-search — Pending
# requests: cpu=50, memory=256Gi — insane
kubectl describe pod -l app=book-search
# "Insufficient cpu", "Insufficient memory"
# Fix:
kubectl patch deployment book-search --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"50m"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"64Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"100m"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"128Mi"}]'

# Verify
kubectl get pods
# All Running

# Incident Note Example:
# ## Incident: book-frontend ImagePullBackOff
# - Severity: P2
# - Duration: 5 minutes
# - Symptom: Pod stuck in ImagePullBackOff
# - Root Cause: Image name typo "ngnix" instead of "nginx"
# - Fix: kubectl set image deployment/book-frontend frontend=nginx:1.25
# - Prevention: Use image validation policy (Kyverno), CI/CD image verification

kind delete cluster --name broken-bookstore
```

</details>

---

## Bài 3: Hard — Production Incident Simulation & Full Incident Report

### Context

Bạn là on-call SRE cho một payment platform. Lúc 2:00 AM, PagerDuty alert bắn:

- Alert 1: "High error rate on payment-gateway (>5% 5xx)"
- Alert 2: "Pod restarts detected on payment-processor"
- Alert 3: "DNS resolution failures in namespace payment"

Tất cả 3 alerts xảy ra gần như đồng thời. Bạn cần triage, debug, fix, và viết full postmortem.

### Yêu cầu

1. **Setup**: Tạo cluster, deploy payment platform simulation (manifests bên dưới) với 6 bugs ẩn.
2. **Triage**: Xác định priority order — fix bug nào trước?
3. **Debug**: Dùng systematic methodology cho từng bug.
4. **Fix**: Tất cả services phải Running và giao tiếp được.
5. **Postmortem**: Viết full postmortem bao gồm:
   - Timeline (khi nào phát hiện, khi nào fix từng issue)
   - Impact assessment
   - Root cause analysis (5 Whys cho root cause chính)
   - Action items (ít nhất 5 items với owner và deadline)

### Manifest

```yaml
# payment-platform.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payment
---
# Payment Gateway — có lỗi
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-gateway
  namespace: payment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-gateway
  template:
    metadata:
      labels:
        app: payment-gateway
    spec:
      containers:
        - name: gateway
          image: nginx:1.25
          ports:
            - containerPort: 80
          env:
            - name: PROCESSOR_URL
              value: "http://payment-processor-svc:8080"
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 200m, memory: 256Mi}
          livenessProbe:
            httpGet:
              path: /healthz
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 1
          readinessProbe:
            httpGet:
              path: /ready
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: payment-gateway-svc
  namespace: payment
spec:
  selector:
    app: payment-gateway
  ports:
    - port: 80
      targetPort: 80
---
# Payment Processor — có lỗi
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-processor
  namespace: payment
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payment-processor
  template:
    metadata:
      labels:
        app: payment-processor
    spec:
      containers:
        - name: processor
          image: busybox:1.36
          command: ["sh", "-c", "echo 'Connecting to DB...' && sleep 2 && echo 'DB connection failed' && exit 1"]
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 200m, memory: 256Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: payment-processor-svc
  namespace: payment
spec:
  selector:
    app: payment-processor
    tier: production
  ports:
    - port: 8080
      targetPort: 8080
---
# Fraud Detection — có lỗi
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fraud-detection
  namespace: payment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fraud-detection
  template:
    metadata:
      labels:
        app: fraud-detection
    spec:
      containers:
        - name: fraud
          image: polinux/stress:1.0.4
          command: ["stress", "--vm", "1", "--vm-bytes", "500M"]
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 200m, memory: 256Mi}
---
# Payment DB — có lỗi
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-db
  namespace: payment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment-db
  template:
    metadata:
      labels:
        app: payment-db
    spec:
      containers:
        - name: db
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests: {cpu: "10", memory: "100Gi"}
            limits: {cpu: "10", memory: "100Gi"}
---
# NetworkPolicy quá strict
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
  namespace: payment
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### Expected Outcome

- Tất cả pods Running trong namespace `payment`.
- Services có endpoints.
- Pods có thể giao tiếp với nhau (DNS + HTTP).
- Full postmortem document.

### Hint

- 6 bugs: liveness probe path sai (nginx mặc định không có /healthz), CrashLoopBackOff (fake DB connect fail), Service selector mismatch (thiếu label `tier`), OOMKilled (stress 500M > 256Mi nhưng vẫn fit), Pending (impossible resources), NetworkPolicy block tất cả (bao gồm DNS egress).
- Triage order: fix NetworkPolicy trước (ảnh hưởng DNS → ảnh hưởng tất cả), rồi Pending (DB), rồi từng pod.
- Nginx mặc định trả 200 cho `/` nhưng 404 cho `/healthz` → liveness fail → restart loop riêng.

### Acceptance Criteria

- [ ] 6 bugs identified theo đúng methodology.
- [ ] Triage order hợp lý (fix NetworkPolicy/DNS trước).
- [ ] Tất cả pods Running, tất cả services có endpoints.
- [ ] Postmortem có: timeline, impact, root cause (5 Whys), ≥5 action items.
- [ ] Mỗi action item có owner và deadline.
- [ ] Thời gian debug < 45 phút.

### Bonus Challenge

Sau khi fix xong, viết script bash tự động health-check toàn bộ namespace: check pods Running, services có endpoints, DNS resolution, NetworkPolicy allows required traffic.

<details>
<summary>Solution</summary>

```bash
kind create cluster --name incident-sim

kubectl apply -f payment-platform.yaml
sleep 30
kubectl get pods -n payment

# === TRIAGE ===
# 1. NetworkPolicy deny all (bao gồm DNS egress) → fix trước
# 2. payment-db Pending (impossible resources) → fix thứ 2
# 3. fraud-detection OOMKilled → fix thứ 3
# 4. payment-gateway liveness fail → fix thứ 4
# 5. payment-processor CrashLoop → fix thứ 5
# 6. payment-processor-svc selector mismatch → fix thứ 6

# === FIX 1: NetworkPolicy ===
# Thêm DNS egress và internal communication
kubectl delete networkpolicy deny-all -n payment
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-with-dns
  namespace: payment
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  egress:
    - to: []
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    - to:
        - namespaceSelector: {}
          podSelector: {}
  ingress:
    - from:
        - namespaceSelector: {}
          podSelector: {}
EOF

# === FIX 2: payment-db Pending ===
kubectl patch deployment payment-db -n payment --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"200m"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}]'

# === FIX 3: fraud-detection OOMKilled ===
# stress 500M > limit 256Mi
kubectl patch deployment fraud-detection -n payment --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1Gi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"512Mi"}]'

# === FIX 4: payment-gateway liveness ===
# nginx doesn't have /healthz — use / instead
kubectl patch deployment payment-gateway -n payment --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/"},{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/failureThreshold","value":3},{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/"}]'

# === FIX 5: payment-processor CrashLoop ===
kubectl patch deployment payment-processor -n payment --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command","value":["sh","-c","echo Connected to DB && sleep 3600"]}]'

# === FIX 6: payment-processor-svc selector ===
kubectl get pods -n payment -l app=payment-processor --show-labels
# Thiếu label tier=production
kubectl patch svc payment-processor-svc -n payment --type json \
  -p '[{"op":"remove","path":"/spec/selector/tier"}]'
# Hoặc thêm label vào pod:
# kubectl patch deployment payment-processor -n payment --type json \
#   -p '[{"op":"add","path":"/spec/template/metadata/labels/tier","value":"production"}]'

# Verify
sleep 30
kubectl get pods -n payment
kubectl get endpoints -n payment
kubectl exec -n payment deploy/payment-gateway -- nslookup payment-processor-svc.payment.svc.cluster.local

# Postmortem template:
cat <<'POSTMORTEM'
# Postmortem: Payment Platform Multi-Failure Incident

## Timeline
- 02:00 — Alerts fired: high 5xx, pod restarts, DNS failures
- 02:05 — On-call engineer begins triage
- 02:08 — Identified NetworkPolicy blocking DNS as root cause of cascade
- 02:10 — Fixed NetworkPolicy (DNS restored)
- 02:12 — Fixed payment-db Pending (reduced resources)
- 02:15 — Fixed fraud-detection OOM (increased memory limit)
- 02:18 — Fixed gateway liveness probe (/healthz → /)
- 02:20 — Fixed processor crash (DB connection simulation)
- 02:22 — Fixed processor service selector mismatch
- 02:25 — All services verified Running

## Impact
- Duration: ~25 minutes
- User impact: Payment processing unavailable
- Revenue impact: Estimated $X in failed transactions

## Root Cause Analysis (5 Whys)
1. Why did payments fail? → payment-gateway returning 503
2. Why 503? → Liveness probe failing → pod restart loop
3. Why liveness failing? → /healthz returns 404 on nginx
4. Why wasn't this caught? → No pre-deploy testing of health check paths
5. Why no testing? → No staging environment with same configuration

## Action Items
1. [P0] Add health check endpoint validation to CI — Owner: DevOps — Due: next sprint
2. [P0] Review all NetworkPolicy configs, ensure DNS egress — Owner: Platform — Due: 3 days
3. [P1] Add resource request validation in admission controller — Owner: Platform — Due: 1 week
4. [P1] Create staging environment matching prod config — Owner: DevOps — Due: 2 weeks
5. [P2] Add integration tests for service-to-service connectivity — Owner: Dev — Due: 3 weeks
POSTMORTEM

kind delete cluster --name incident-sim
```

</details>

---

## Solution/Reference Implementation

Các lời giải chi tiết nằm trong block `<details><summary>Solution</summary>` của từng bài để người học có thể thử trước khi mở đáp án. Reference cuối file:

- **Bài 1 — Easy**: debug ImagePullBackOff, CrashLoopBackOff và Service selector mismatch bằng `describe`, `logs`, `get endpoints`.
- **Bài 2 — Medium**: xử lý 5 lỗi trong BookStore, viết incident note ngắn cho từng lỗi và verify toàn bộ pod/endpoints.
- **Bài 3 — Hard**: triage incident nhiều lỗi theo thứ tự ưu tiên, fix NetworkPolicy/DNS, Pending, OOMKilled, probe và selector, rồi hoàn thiện postmortem.

