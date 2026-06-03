# Day 10: Exercises — Kubernetes Architecture Deep Dive

---

## Exercise 1: Tạo Cluster và Khám phá Control Plane (Easy)

### Context

Bạn vừa bắt đầu làm việc với Kubernetes. Bước đầu tiên là tạo local cluster và hiểu các thành phần đang chạy bên trong.

### Yêu cầu

1. Cài đặt `kind` (nếu chưa có).
2. Tạo cluster 1 control-plane + 2 workers.
3. Liệt kê tất cả pods trong `kube-system` namespace.
4. Xác định role của từng pod (API server, etcd, scheduler, controller manager, kube-proxy, CoreDNS).
5. Kiểm tra cluster health.
6. Apply một pod đơn giản và verify nó chạy.

### Expected Outcome

- Cluster 3 nodes (1 control-plane, 2 workers) chạy thành công.
- Liệt kê được 6+ system pods và giải thích role.
- Pod nginx chạy trên worker node.
- `kubectl cluster-info` hiển thị cluster endpoint.

### Hint

- `kind create cluster --name lab --config config.yaml`
- `kubectl get pods -n kube-system`
- `kubectl get nodes`
- `kubectl run nginx --image=nginx:alpine`

### Acceptance Criteria

- [ ] Cluster tạo thành công với 3 nodes
- [ ] Tất cả nodes ở trạng thái Ready
- [ ] Liệt kê được control plane pods
- [ ] Giải thích được role của mỗi component
- [ ] Pod nginx chạy trên worker node
- [ ] `kubectl cluster-info` hiển thị đúng

### Bonus Challenge

Dùng `kubectl get componentstatuses` (deprecated nhưng useful) hoặc health endpoints: `/healthz`, `/readyz`, `/livez` để kiểm tra health.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

echo "=== 1. Install kind (if needed) ==="
if ! command -v kind &>/dev/null; then
    echo "Installing kind..."
    go install sigs.k8s.io/kind@latest 2>/dev/null || \
    curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64 && chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind
fi
kind --version

echo ""
echo "=== 2. Create cluster ==="
cat > /tmp/kind-config.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF

kind delete cluster --name lab 2>/dev/null || true
kind create cluster --name lab --config /tmp/kind-config.yaml
echo "Cluster created!"

echo ""
echo "=== 3. Verify nodes ==="
kubectl get nodes -o wide
# Expected: 3 nodes, all Ready

echo ""
echo "=== 4. Control Plane pods ==="
kubectl get pods -n kube-system -o wide
echo ""
echo "Component Roles:"
echo "  kube-apiserver        → API Gateway, auth, validation, etcd access"
echo "  etcd                  → Distributed key-value store (cluster state)"
echo "  kube-scheduler        → Places pods on nodes"
echo "  kube-controller-manager → Runs reconciliation controllers"
echo "  kube-proxy            → Service networking (iptables/IPVS)"
echo "  coredns               → Cluster DNS resolution"
echo "  kindnet               → CNI plugin (networking between pods)"

echo ""
echo "=== 5. Cluster health ==="
kubectl cluster-info
echo ""
kubectl get --raw /healthz
echo ""
kubectl get --raw /readyz
echo ""

echo ""
echo "=== 6. Deploy test pod ==="
kubectl run nginx-test --image=nginx:alpine --port=80
sleep 10
kubectl get pod nginx-test -o wide
echo ""
echo "Pod is running on:"
kubectl get pod nginx-test -o jsonpath='{.spec.nodeName}'
echo " (should be a worker node)"

echo ""
echo "=== 7. Verify pod ==="
kubectl exec nginx-test -- curl -s localhost:80 | head -5
echo ""
echo "Pod is working!"

echo ""
echo "=== Cleanup ==="
echo "kubectl delete pod nginx-test"
echo "kind delete cluster --name lab"
echo "rm /tmp/kind-config.yaml"
```

</details>

---

## Exercise 2: Trace Request Flow và Reconciliation Loop (Medium)

### Context

Bạn cần chứng minh rằng bạn hiểu luồng xử lý của Kubernetes: từ YAML → API Server → Controller → Scheduler → Kubelet → Running Pod. Bạn cũng cần chứng minh reconciliation loop hoạt động (self-healing).

### Yêu cầu

1. Tạo Deployment với 3 replicas.
2. Trace flow bằng events: xem Deployment Controller tạo ReplicaSet, ReplicaSet Controller tạo Pods, Scheduler bind Pods, Kubelet start Containers.
3. Xóa 1 pod → quan sát ReplicaSet Controller tạo lại.
4. Scale deployment lên 5 → quan sát events.
5. Xóa ReplicaSet trực tiếp → quan sát Deployment Controller tạo lại.
6. Ghi lại timeline của mỗi bước.

### Expected Outcome

- Event timeline showing:
  1. Deployment → `ScalingReplicaSet`
  2. ReplicaSet → `SuccessfulCreate` (3 pods)
  3. Scheduler → `Scheduled` (3 bindings)
  4. Kubelet → `Pulling`, `Pulled`, `Created`, `Started`
- Self-healing: pod xóa → pod mới tạo trong < 10 giây.
- ReplicaSet xóa → Deployment tạo RS mới.

### Hint

- `kubectl get events --watch` trong terminal riêng
- `kubectl get events --sort-by='.lastTimestamp'`
- `kubectl describe deployment NAME` có events ở cuối
- `kubectl get rs` xem ReplicaSet

### Acceptance Criteria

- [ ] Deployment 3 replicas chạy thành công
- [ ] Event log capture đủ flow: Deployment → RS → Pod → Schedule → Start
- [ ] Self-healing: xóa pod → pod mới xuất hiện
- [ ] Scale: 3 → 5 replicas hoạt động
- [ ] ReplicaSet recovery: xóa RS → Deployment tạo RS mới
- [ ] Timeline ghi lại chính xác

### Bonus Challenge

Thay đổi image tag trong deployment (rolling update) và trace flow: Deployment tạo RS mới, scale RS mới lên, scale RS cũ xuống từng bước.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

echo "=== Ensure cluster exists ==="
kubectl cluster-info >/dev/null 2>&1 || { echo "Create cluster first (Exercise 1)"; exit 1; }

echo ""
echo "=== 1. Create Deployment ==="
cat > /tmp/trace-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trace-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: trace-demo
  template:
    metadata:
      labels:
        app: trace-demo
    spec:
      containers:
        - name: nginx
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
EOF

kubectl apply -f /tmp/trace-deployment.yaml
echo "Waiting for deployment..."
kubectl rollout status deployment/trace-demo --timeout=60s

echo ""
echo "=== 2. Trace Request Flow ==="
echo ""
echo "--- Deployment ---"
kubectl get deployment trace-demo
echo ""
echo "--- ReplicaSet (created by Deployment Controller) ---"
kubectl get rs -l app=trace-demo
echo ""
echo "--- Pods (created by ReplicaSet Controller) ---"
kubectl get pods -l app=trace-demo -o wide
echo ""
echo "--- Events (full flow) ---"
kubectl get events --sort-by='.lastTimestamp' --field-selector reason!=Pulling | tail -20
echo ""
echo "--- Deployment events ---"
kubectl describe deployment trace-demo | grep -A 20 "Events:"

echo ""
echo "================================================"
echo "=== 3. Self-Healing: Delete a pod ==="
echo "================================================"
echo ""
echo "Pods before delete:"
kubectl get pods -l app=trace-demo
POD=$(kubectl get pods -l app=trace-demo -o jsonpath='{.items[0].metadata.name}')
echo ""
echo "Deleting pod: $POD"
kubectl delete pod "$POD" --wait=false
echo "Waiting 10 seconds..."
sleep 10
echo ""
echo "Pods after delete (should still be 3, with new pod):"
kubectl get pods -l app=trace-demo
echo ""
echo "New events:"
kubectl get events --sort-by='.lastTimestamp' | tail -5

echo ""
echo "================================================"
echo "=== 4. Scale from 3 to 5 ==="
echo "================================================"
echo ""
kubectl scale deployment trace-demo --replicas=5
sleep 10
echo "Pods after scale:"
kubectl get pods -l app=trace-demo
echo ""
echo "Events:"
kubectl get events --sort-by='.lastTimestamp' | head -5

echo ""
echo "================================================"
echo "=== 5. Delete ReplicaSet (Deployment recreates) ==="
echo "================================================"
echo ""
RS_NAME=$(kubectl get rs -l app=trace-demo -o jsonpath='{.items[0].metadata.name}')
echo "Deleting ReplicaSet: $RS_NAME"
kubectl delete rs "$RS_NAME" --wait=false
sleep 15
echo ""
echo "ReplicaSets after delete (Deployment creates new one):"
kubectl get rs -l app=trace-demo
echo ""
echo "Pods (new RS creates new pods):"
kubectl get pods -l app=trace-demo

echo ""
echo "================================================"
echo "=== 6. Rolling Update (Bonus) ==="
echo "================================================"
echo ""
echo "Current image: nginx:1.25-alpine"
echo "Updating to: nginx:1.26-alpine"
kubectl set image deployment/trace-demo nginx=nginx:1.26-alpine
echo ""
echo "Watch rolling update:"
kubectl rollout status deployment/trace-demo --timeout=60s
echo ""
echo "ReplicaSets (old + new):"
kubectl get rs -l app=trace-demo
echo ""
echo "Events (rolling update flow):"
kubectl get events --sort-by='.lastTimestamp' | head -10

echo ""
echo "=== Cleanup ==="
kubectl delete -f /tmp/trace-deployment.yaml
rm /tmp/trace-deployment.yaml
echo "Done!"
```

</details>

---

## Exercise 3: Component Failure Simulation (Hard)

### Context

Bạn là SRE phụ trách Kubernetes cluster. Bạn cần hiểu chuyện gì xảy ra khi từng component fail — để viết runbook và thiết kế monitoring alerts.

### Yêu cầu

1. Deploy một application (3 replicas).
2. Mô phỏng từng failure scenario và ghi nhận impact:
   - **Scenario A**: Scheduler không hoạt động → tạo pod mới → chuyện gì xảy ra?
   - **Scenario B**: Delete 1 pod → reconciliation hoạt động thế nào?
   - **Scenario C**: Label conflict → pod không match selector → chuyện gì xảy ra?
   - **Scenario D**: Resource exhaustion → pod Pending → debug process
3. Ghi lại cho mỗi scenario: symptom, debug commands, root cause, fix.
4. Viết mini runbook cho mỗi scenario.

### Expected Outcome

| Scenario | Symptom | Impact | Recovery |
|----------|---------|--------|----------|
| Scheduler down | New pods Pending | Existing pods OK | Restore scheduler |
| Pod deleted | Pod count < desired | Auto-recovery < 10s | Automatic |
| Label mismatch | RS creates excess pods | Orphaned pods | Fix labels |
| Resource exhaustion | Pods Pending | Cannot scale | Add capacity |

### Hint

- Scheduler: trên kind cluster, không dễ stop scheduler trực tiếp. Simulate bằng cách tạo pod với impossible nodeSelector.
- Label: `kubectl label pod POD app-` (remove label) → pod không match selector → RS tạo pod mới.
- Resource: set requests rất cao (`cpu: 100`) → Pending.

### Acceptance Criteria

- [ ] 4 scenarios mô phỏng thành công
- [ ] Mỗi scenario có: symptom, debug commands, root cause, fix
- [ ] Debug commands cho thấy cách xác định vấn đề
- [ ] Recovery verified cho mỗi scenario
- [ ] Mini runbook viết cho mỗi loại lỗi

### Bonus Challenge

1. Simulate node failure: `kubectl drain node --ignore-daemonsets` → pods reschedule.
2. Tạo PodDisruptionBudget và test drain behavior.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

echo "=== Setup: Deploy application ==="
cat > /tmp/failure-app.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: failure-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: failure-demo
  template:
    metadata:
      labels:
        app: failure-demo
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
EOF

kubectl apply -f /tmp/failure-app.yaml
kubectl rollout status deployment/failure-demo --timeout=60s
echo "Application deployed with 3 replicas"

echo ""
echo "=============================================="
echo "SCENARIO A: Scheduler Issue (Impossible Placement)"
echo "=============================================="

cat > /tmp/unschedulable-pod.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: unschedulable-pod
spec:
  containers:
    - name: nginx
      image: nginx:alpine
  nodeSelector:
    kubernetes.io/os: windows-impossible
EOF

kubectl apply -f /tmp/unschedulable-pod.yaml

echo "Waiting 10 seconds..."
sleep 10

echo ""
echo "Symptom: Pod stuck in Pending"
kubectl get pod unschedulable-pod

echo ""
echo "Debug:"
kubectl describe pod unschedulable-pod | grep -A 5 "Events:"
echo ""
echo "Root cause: No node matches nodeSelector"
echo "Fix: Correct nodeSelector or add matching node"

kubectl delete pod unschedulable-pod
echo "Cleaned up."

echo ""
echo "=============================================="
echo "SCENARIO B: Pod Deletion → Self-Healing"
echo "=============================================="

echo "Before:"
kubectl get pods -l app=failure-demo
POD=$(kubectl get pods -l app=failure-demo -o jsonpath='{.items[0].metadata.name}')

echo ""
echo "Deleting pod: $POD"
kubectl delete pod "$POD" --wait=false

echo ""
echo "After (5 seconds):"
sleep 5
kubectl get pods -l app=failure-demo

echo ""
echo "Symptom: Temporarily < 3 pods"
echo "Recovery: ReplicaSet controller creates new pod in < 10s"
echo "Impact: Minimal — other 2 pods still serving traffic"

echo ""
echo "=============================================="
echo "SCENARIO C: Label Mismatch → Orphaned Pod"
echo "=============================================="

echo "Before — 3 pods with label app=failure-demo:"
kubectl get pods -l app=failure-demo

POD=$(kubectl get pods -l app=failure-demo -o jsonpath='{.items[0].metadata.name}')
echo ""
echo "Removing label from pod: $POD"
kubectl label pod "$POD" app-

echo ""
echo "After label removal:"
sleep 5
echo "Pods matching selector (app=failure-demo):"
kubectl get pods -l app=failure-demo
echo ""
echo "All pods (including orphaned):"
kubectl get pods | grep -E "failure-demo|NAME"

echo ""
echo "Symptom: RS sees only 2 matching pods → creates new one → now 4 total"
echo "Root cause: Label removed → pod doesn't match selector"
echo "Fix: Re-label or delete orphaned pod"
kubectl delete pod "$POD"
echo "Orphaned pod deleted."

echo ""
echo "=============================================="
echo "SCENARIO D: Resource Exhaustion → Pending"
echo "=============================================="

cat > /tmp/greedy-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: greedy-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: greedy-app
  template:
    metadata:
      labels:
        app: greedy-app
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          resources:
            requests:
              cpu: "100"
              memory: "100Gi"
EOF

kubectl apply -f /tmp/greedy-deployment.yaml
echo "Waiting 10 seconds..."
sleep 10

echo ""
echo "Symptom: Pod stuck Pending"
kubectl get pods -l app=greedy-app

echo ""
echo "Debug:"
kubectl describe pod $(kubectl get pods -l app=greedy-app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "greedy-pod") 2>/dev/null | grep -A 5 "Events:" || \
kubectl get events --sort-by='.lastTimestamp' | grep -i "insufficient\|greedy" | head -5

echo ""
echo "Root cause: No node has 100 CPUs and 100Gi memory"
echo "Fix: Reduce resource requests or add larger nodes"

kubectl delete -f /tmp/greedy-deployment.yaml

echo ""
echo "=============================================="
echo "SCENARIO E (Bonus): Node Drain"
echo "=============================================="

WORKER=$(kubectl get nodes --no-headers | grep -v control-plane | head -1 | awk '{print $1}')
echo "Draining node: $WORKER"
echo "Pods on $WORKER before drain:"
kubectl get pods -l app=failure-demo -o wide | grep "$WORKER" || echo "  (no pods on this node)"

echo ""
kubectl drain "$WORKER" --ignore-daemonsets --delete-emptydir-data --timeout=30s 2>/dev/null || true
sleep 10

echo "Pods after drain (should be on other node):"
kubectl get pods -l app=failure-demo -o wide

echo ""
echo "Uncordoning node:"
kubectl uncordon "$WORKER"

echo ""
echo "=== Cleanup ==="
kubectl delete -f /tmp/failure-app.yaml
rm -f /tmp/failure-app.yaml /tmp/unschedulable-pod.yaml /tmp/greedy-deployment.yaml

echo ""
echo "=== Mini Runbook Summary ==="
cat << 'RUNBOOK'
| Scenario            | Debug Command                          | Root Cause         | Fix                    |
|---------------------|----------------------------------------|-------------------|------------------------|
| Pod Pending         | kubectl describe pod NAME              | Insufficient resources | Add nodes/reduce requests |
| Pod CrashLoop       | kubectl logs NAME --previous           | App error          | Fix app/config         |
| ImagePullBackOff    | kubectl describe pod NAME              | Wrong image/auth   | Fix image name/secret  |
| Label mismatch      | kubectl get pods --show-labels         | Wrong labels       | Fix labels             |
| Node NotReady       | kubectl describe node NAME             | Node issue         | Fix node/drain         |
RUNBOOK
echo ""
echo "Done!"
```

</details>

---

## Tổng kết

| Exercise | Thời gian | Kỹ năng |
|----------|-----------|---------|
| Easy | 20 phút | kind cluster, control plane exploration |
| Medium | 35 phút | Request flow tracing, reconciliation loop |
| Hard | 45 phút | Component failure simulation, debugging |
| **Tổng** | **~100 phút** | |

