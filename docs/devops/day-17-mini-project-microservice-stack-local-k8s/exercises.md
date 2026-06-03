# Day 17: Bài tập — Mini-project Deploy Microservice Stack

---

## Bài 1: Easy — Deploy BookStore Stack theo hướng dẫn

### Context

Bạn cần deploy toàn bộ BookStore microservice stack lên local Kubernetes cluster theo hướng dẫn trong lesson.md.

### Yêu cầu

1. Tạo kind cluster với Ingress support.
2. Cài NGINX Ingress Controller.
3. Tạo toàn bộ manifest files theo hướng dẫn.
4. Apply bằng Kustomize.
5. Verify tất cả services hoạt động.
6. Test Ingress routing.
7. Test data persistence của Redis.

### Expected Outcome

- 4 services running (frontend, api-gateway, book-service, redis).
- Ingress routing: `/` → frontend, `/api/*` → api-gateway → book-service.
- Redis data persist qua pod restart.
- Tất cả health checks pass.

### Hint

- Tạo files theo đúng thứ tự trong lesson.md.
- Đợi Ingress Controller ready trước khi test Ingress.
- Thêm `bookstore.local` vào `/etc/hosts`.

### Acceptance Criteria

- [ ] Kind cluster tạo thành công.
- [ ] Ingress Controller running.
- [ ] Tất cả 4 services (pods) Running và Ready.
- [ ] `curl http://bookstore.local/` trả về HTML.
- [ ] `curl http://bookstore.local/api/books` trả về JSON.
- [ ] Redis data persist sau khi xóa và tạo lại pod.
- [ ] Cleanup script xóa sạch.

### Bonus Challenge

- Thêm `kubectl top pods -n bookstore` để xem resource usage (cần metrics-server).
- Thêm port-forward để access từng service trực tiếp mà không qua Ingress.

<details>
<summary>Solution</summary>

Tham khảo toàn bộ hướng dẫn step-by-step trong `lesson.md`. Dưới đây là quick deploy script:

```bash
#!/bin/bash
set -euo pipefail

# 1. Tạo cluster
cat > /tmp/kind-config.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
EOF

kind create cluster --name bookstore --config /tmp/kind-config.yaml

# 2. Cài Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# 3. Apply stack
kubectl apply -k bookstore-k8s/overlays/dev

# 4. Đợi ready
kubectl wait --namespace bookstore --for=condition=ready pod --all --timeout=120s

# 5. Verify
echo "=== All Resources ==="
kubectl get all -n bookstore

echo "=== PVC ==="
kubectl get pvc -n bookstore

echo "=== Ingress ==="
kubectl get ingress -n bookstore

# 6. Test (sau khi thêm bookstore.local vào /etc/hosts)
echo "=== Test Frontend ==="
curl -s http://bookstore.local/ | head -5

echo "=== Test API ==="
curl -s http://bookstore.local/api/books

echo "=== Test Redis ==="
kubectl exec -n bookstore redis-0 -- redis-cli -a bookstore-redis-pass ping
```

</details>

---

## Bài 2: Medium — Thêm Monitoring và Multi-environment Overlay

### Context

Stack đã chạy. Bây giờ bạn cần:
1. Thêm monitoring cơ bản (NGINX stub_status endpoint).
2. Tạo thêm prod overlay với cấu hình khác dev.

### Yêu cầu

1. **Monitoring**: Thêm NGINX stub_status endpoint `/nginx_status` vào mỗi NGINX service.
2. **Prod overlay**: Tạo `overlays/prod/` với:
   - Replicas: frontend=2, api-gateway=3, book-service=3.
   - Tăng resource limits cho tất cả services.
   - Thêm `namePrefix: prod-` và `commonLabels: env: production`.
   - Thay đổi ConfigMap: `LOG_LEVEL=warn`.
3. So sánh diff giữa dev và prod overlay.
4. Deploy prod overlay (nếu cluster có đủ resources).

### Expected Outcome

- `/nginx_status` endpoint trả về NGINX metrics.
- Prod overlay render YAML với replicas cao hơn, resources lớn hơn.
- Diff rõ ràng giữa dev vs prod.

### Hint

- Thêm `location /nginx_status { stub_status; }` vào NGINX config.
- Tạo `overlays/prod/kustomization.yaml` reference `../../base`.
- Dùng `diff <(kubectl kustomize overlays/dev) <(kubectl kustomize overlays/prod)`.

### Acceptance Criteria

- [ ] `/nginx_status` endpoint trả về stats.
- [ ] Prod overlay render đúng replicas (2, 3, 3).
- [ ] Prod overlay có namePrefix `prod-`.
- [ ] Diff giữa dev và prod hiển thị rõ differences.
- [ ] Prod overlay pass `kubectl apply --dry-run=server`.

### Bonus Challenge

- Tạo script so sánh resource usage giữa dev và prod overlay (total CPU requests, memory requests).
- Thêm PodDisruptionBudget cho prod overlay.

<details>
<summary>Solution</summary>

```bash
# === 1. Thêm monitoring endpoint ===
# Sửa book-service-configmap.yaml, thêm location vào server block:
# location /nginx_status {
#     stub_status;
#     allow 10.0.0.0/8;  # chỉ cho internal
#     deny all;
# }

# === 2. Tạo prod overlay ===
mkdir -p bookstore-k8s/overlays/prod

cat > bookstore-k8s/overlays/prod/deployment-patches.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: frontend
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 300m
              memory: 128Mi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bookstore
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: api-gateway
          resources:
            requests:
              cpu: 200m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-service
  namespace: bookstore
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: book-service
          resources:
            requests:
              cpu: 200m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
EOF

cat > bookstore-k8s/overlays/prod/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

commonLabels:
  env: production

patches:
  - path: deployment-patches.yaml
EOF

# === 3. So sánh ===
diff <(kubectl kustomize bookstore-k8s/overlays/dev) \
     <(kubectl kustomize bookstore-k8s/overlays/prod)

# === 4. Dry-run ===
kubectl kustomize bookstore-k8s/overlays/prod | \
  kubectl apply --dry-run=server -f -
```

</details>

---

## Bài 3: Hard — Simulate Failures, Debug và Viết Incident Notes

### Context

Bạn là on-call engineer. BookStore stack đang chạy nhưng bạn sẽ mô phỏng các lỗi production thường gặp và phải debug, fix, và viết incident notes.

### Yêu cầu

Mô phỏng và debug 5 scenarios:

1. **Scenario 1 — Service Down**: Xóa book-service deployment và quan sát API gateway trả 502. Tìm nguyên nhân và fix.

2. **Scenario 2 — Wrong Config**: Sửa api-gateway ConfigMap đổi upstream thành service name sai. Quan sát lỗi. Debug và fix.

3. **Scenario 3 — Resource Exhaustion**: Giảm memory limit của book-service xuống 4Mi. Quan sát OOMKilled. Fix.

4. **Scenario 4 — Redis Connection Lost**: Xóa redis Secret. Restart book-service pods. Quan sát lỗi. Fix.

5. **Scenario 5 — PVC Data Loss**: Xóa PVC của Redis (scale redis xuống 0 trước). Tạo lại. Quan sát data mất.

Cho mỗi scenario:
- Ghi lại **symptom** (dấu hiệu).
- Ghi lại **debug steps** (commands đã chạy).
- Xác định **root cause**.
- Thực hiện **fix**.
- Viết **incident note** ngắn gọn.

### Expected Outcome

- 5 scenarios được mô phỏng và debug thành công.
- 5 incident notes ngắn gọn, mỗi note: Symptom, Debug, Root Cause, Fix, Prevention.
- Stack trở lại trạng thái healthy sau mỗi fix.

### Hint

- Dùng `kubectl get events -n bookstore --sort-by='.lastTimestamp'` để xem events.
- Dùng `kubectl logs` với `--previous` flag cho crashed containers.
- Dùng `kubectl describe` để xem chi tiết.
- Dùng `kubectl exec` để test connectivity.

### Acceptance Criteria

- [ ] 5 scenarios mô phỏng thành công.
- [ ] Debug commands documented cho mỗi scenario.
- [ ] Root cause xác định đúng.
- [ ] Fix applied và verified.
- [ ] 5 incident notes viết xong.
- [ ] Stack healthy sau tất cả scenarios.

### Bonus Challenge

- Viết runbook cho top 3 lỗi thường gặp nhất.
- Tạo script automated health check chạy tất cả verification steps.
- Mô phỏng cascading failure: Redis down → book-service fail → api-gateway 502 → frontend broken.

<details>
<summary>Solution</summary>

```bash
# === Scenario 1: Service Down ===
echo "=== Scenario 1: Delete book-service ==="
kubectl delete deploy book-service -n bookstore
sleep 5
# Symptom: curl http://bookstore.local/api/books → 502 Bad Gateway
curl -s http://bookstore.local/api/books
# Debug:
kubectl get pods -n bookstore
kubectl get endpoints book-service -n bookstore  # No endpoints
kubectl describe svc book-service -n bookstore
# Root Cause: Deployment deleted, no pods backing the service
# Fix:
kubectl apply -k bookstore-k8s/overlays/dev
kubectl wait --namespace bookstore --for=condition=ready pod -l app=book-service --timeout=60s
curl -s http://bookstore.local/api/books  # Should work

# === Scenario 2: Wrong Config ===
echo "=== Scenario 2: Wrong upstream config ==="
kubectl edit cm api-gateway-config -n bookstore
# Change: server book-service.bookstore.svc.cluster.local:80;
# To:     server wrong-service.bookstore.svc.cluster.local:80;
# Restart pods to pick up new config:
kubectl rollout restart deploy/api-gateway -n bookstore
sleep 10
# Symptom: curl http://bookstore.local/api/books → 502
curl -s -o /dev/null -w "%{http_code}" http://bookstore.local/api/books
# Debug:
kubectl logs deploy/api-gateway -n bookstore | tail -10
# Root Cause: upstream service name wrong in NGINX config
# Fix:
kubectl apply -k bookstore-k8s/overlays/dev  # Restore correct ConfigMap
kubectl rollout restart deploy/api-gateway -n bookstore
kubectl wait --namespace bookstore --for=condition=ready pod -l app=api-gateway --timeout=60s

# === Scenario 3: OOMKilled ===
echo "=== Scenario 3: Memory limit too low ==="
kubectl patch deploy book-service -n bookstore --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "4Mi"}]'
sleep 15
# Symptom: pods in CrashLoopBackOff/OOMKilled
kubectl get pods -n bookstore -l app=book-service
kubectl describe pod -n bookstore -l app=book-service | grep -A5 "Last State"
# Debug:
kubectl get events -n bookstore --field-selector reason=OOMKilling
# Root Cause: Memory limit 4Mi too low for NGINX
# Fix:
kubectl apply -k bookstore-k8s/overlays/dev
kubectl wait --namespace bookstore --for=condition=ready pod -l app=book-service --timeout=60s

# === Scenario 4: Secret Missing ===
echo "=== Scenario 4: Delete Redis secret ==="
kubectl delete secret redis-secret -n bookstore
kubectl rollout restart deploy/book-service -n bookstore
sleep 10
# Symptom: book-service pods fail to start (CreateContainerConfigError)
kubectl get pods -n bookstore -l app=book-service
kubectl describe pod -n bookstore -l app=book-service | grep -A3 "Warning"
# Root Cause: Secret referenced by pod doesn't exist
# Fix:
kubectl apply -k bookstore-k8s/overlays/dev
kubectl wait --namespace bookstore --for=condition=ready pod -l app=book-service --timeout=60s

# === Scenario 5: PVC Data Loss ===
echo "=== Scenario 5: PVC deletion ==="
kubectl exec -n bookstore redis-0 -- redis-cli -a bookstore-redis-pass SET important-data "critical-value"
kubectl exec -n bookstore redis-0 -- redis-cli -a bookstore-redis-pass GET important-data
# Scale down Redis
kubectl scale statefulset redis -n bookstore --replicas=0
kubectl wait --namespace bookstore --for=delete pod/redis-0 --timeout=60s
# Delete PVC
kubectl delete pvc redis-data-redis-0 -n bookstore
# Scale back up
kubectl scale statefulset redis -n bookstore --replicas=1
kubectl wait --namespace bookstore --for=condition=ready pod/redis-0 --timeout=60s
# Check - data is gone!
kubectl exec -n bookstore redis-0 -- redis-cli -a bookstore-redis-pass GET important-data
# Expected: (nil) - data lost!
# Root Cause: PVC deleted, new PVC created empty
# Lesson: Never delete PVC in production without backup

echo "=== All scenarios complete ==="
```

### Incident Note Template (mỗi scenario):

```markdown
## Incident Note: [Scenario Name]

**Date**: YYYY-MM-DD
**Duration**: X minutes
**Impact**: [Describe user impact]

### Symptom
- [What was observed]

### Debug Steps
1. [Command and what it showed]
2. [Next command]

### Root Cause
[One sentence]

### Fix Applied
[What was done]

### Prevention
- [How to prevent this in the future]
```

</details>

---

## Solution / Reference Implementation

Các reference implementation đầy đủ nằm trong từng block `<details>` của Bài 1, Bài 2 và Bài 3 ở trên. Khi tự chấm bài, verify tối thiểu các điểm sau:

```bash
kubectl get all -n bookstore
kubectl get ingress,pvc,cm,secret -n bookstore
curl -s http://bookstore.local/api/books
kubectl exec -n bookstore redis-0 -- redis-cli -a bookstore-redis-pass ping
```

