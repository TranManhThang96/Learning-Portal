# Day 18: Bài tập — Resource Requests/Limits, QoS, Right-sizing

---

## Bài 1: Easy — Quan sát QoS Classes và Resource Behavior

### Context

Bạn cần hiểu cách Kubernetes gán QoS class và hành vi khác nhau giữa các class khi node gặp pressure.

### Yêu cầu

1. Tạo 3 pods, mỗi pod thuộc một QoS class khác nhau (Guaranteed, Burstable, BestEffort).
2. Verify QoS class bằng `kubectl get pod -o jsonpath`.
3. Kiểm tra resource usage bằng `kubectl top pod`.
4. Tạo LimitRange cho namespace `test-qos` để tự động set default resources.
5. Deploy pod không set resources vào namespace `test-qos` → verify LimitRange tự set defaults.
6. Cleanup.

### Expected Outcome

- 3 pods running với QoS class tương ứng.
- Pod trong namespace có LimitRange tự được gán default resources.
- Hiểu rõ output của `kubectl describe pod` phần resources.

### Hint

- Guaranteed: `requests == limits` cho cả CPU và memory.
- Burstable: `requests < limits` hoặc chỉ set một.
- BestEffort: không set resources.
- Dùng `kubectl get pod -o jsonpath='{.status.qosClass}'`.

### Acceptance Criteria

- [ ] 3 pods tạo thành công, mỗi pod đúng QoS class.
- [ ] `kubectl top pod` hiển thị usage cho mỗi pod.
- [ ] LimitRange tạo thành công.
- [ ] Pod không set resources được gán defaults từ LimitRange.
- [ ] Cleanup sạch.

### Bonus Challenge

- Tạo ResourceQuota cho namespace, deploy pods cho đến khi chạm quota limit.
- Quan sát error message khi vượt quota.

<details>
<summary>Solution</summary>

```bash
# === Tạo namespace ===
kubectl create namespace test-qos

# === 1. Guaranteed Pod ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: guaranteed-pod
  namespace: test-qos
spec:
  containers:
    - name: app
      image: nginx:1.25-alpine
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 100m
          memory: 128Mi
EOF

# === 2. Burstable Pod ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: burstable-pod
  namespace: test-qos
spec:
  containers:
    - name: app
      image: nginx:1.25-alpine
      resources:
        requests:
          cpu: 50m
          memory: 64Mi
        limits:
          cpu: 200m
          memory: 256Mi
EOF

# === 3. BestEffort Pod ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: besteffort-pod
  namespace: test-qos
spec:
  containers:
    - name: app
      image: nginx:1.25-alpine
EOF

# === 4. Verify QoS ===
echo "=== QoS Classes ==="
for pod in guaranteed-pod burstable-pod besteffort-pod; do
  qos=$(kubectl get pod $pod -n test-qos -o jsonpath='{.status.qosClass}')
  echo "$pod: $qos"
done

# === 5. Check usage ===
kubectl top pods -n test-qos

# === 6. LimitRange ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: test-qos
spec:
  limits:
    - type: Container
      default:
        cpu: 200m
        memory: 256Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
EOF

# === 7. Deploy pod without resources ===
kubectl run auto-limited --image=nginx:1.25-alpine -n test-qos
sleep 5
kubectl get pod auto-limited -n test-qos -o jsonpath='{.spec.containers[0].resources}' | python3 -m json.tool
# Expect: requests and limits auto-set by LimitRange

# === Cleanup ===
kubectl delete namespace test-qos
```

</details>

---

## Bài 2: Medium — Tạo và Debug CPU Throttling & OOMKilled

### Context

Bạn cần thực hành tạo điều kiện gây CPU throttling và OOMKilled, sau đó debug và fix bằng cách điều chỉnh resource configuration.

### Yêu cầu

1. **CPU Throttling**:
   - Tạo pod chạy stress tool với CPU limit `200m` nhưng workload cần 1 CPU.
   - Đo throttling bằng cgroup stats.
   - Fix bằng cách tăng CPU limit.
   - So sánh throttling metrics trước và sau fix.

2. **OOMKilled**:
   - Tạo pod với memory limit `50Mi` chạy workload cần 200Mi.
   - Quan sát OOMKilled và exit code 137.
   - Fix bằng cách tăng memory limit.
   - Verify pod stable sau fix.

3. **Right-sizing**:
   - Deploy NGINX pod với generous resources (cpu: 1, memory: 1Gi).
   - Quan sát actual usage bằng `kubectl top`.
   - Đề xuất right-sized resources dựa trên metrics.
   - Apply right-sized config và verify vẫn hoạt động.

### Expected Outcome

- Hiểu rõ dấu hiệu throttling vs OOMKilled.
- Biết cách đọc cgroup stats.
- Có methodology để right-size resources.

### Hint

- Dùng image `polinux/stress` cho CPU/memory stress.
- `cat /sys/fs/cgroup/cpu.stat` hoặc `/sys/fs/cgroup/cpu/cpu.stat` cho throttling.
- Exit code 137 = 128 + 9 (SIGKILL) → OOMKilled.
- `kubectl top` cần metrics-server.

### Acceptance Criteria

- [ ] CPU throttling tái tạo thành công, cgroup stats cho thấy throttling.
- [ ] OOMKilled tái tạo thành công, exit code 137 confirmed.
- [ ] Fix applied, throttling giảm/hết.
- [ ] Fix applied, OOMKilled không còn.
- [ ] Right-sizing: actual usage <<< limits → đề xuất giảm hợp lý.
- [ ] Document tất cả debug commands đã dùng.

### Bonus Challenge

- Viết script tự động detect pods đang bị throttle trên cluster.
- Tạo pod Java (OpenJDK) với memory limit, verify `-XX:+UseContainerSupport` hoạt động.

<details>
<summary>Solution</summary>

```bash
# === 1. CPU Throttling ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cpu-throttle-test
spec:
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress"]
      args: ["--cpu", "2", "--timeout", "300"]
      resources:
        requests:
          cpu: 100m
          memory: 64Mi
        limits:
          cpu: 200m
          memory: 64Mi
EOF

sleep 15

# Check throttling
echo "=== CPU Throttling Stats ==="
kubectl exec cpu-throttle-test -- cat /sys/fs/cgroup/cpu.stat 2>/dev/null || \
kubectl exec cpu-throttle-test -- cat /sys/fs/cgroup/cpu/cpu.stat

# Check usage (sẽ bị cap ở ~200m)
kubectl top pod cpu-throttle-test

# Fix: tăng CPU limit
kubectl delete pod cpu-throttle-test
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cpu-throttle-fixed
spec:
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress"]
      args: ["--cpu", "2", "--timeout", "120"]
      resources:
        requests:
          cpu: 500m
          memory: 64Mi
        limits:
          cpu: "2"
          memory: 64Mi
EOF

sleep 15
echo "=== After Fix ==="
kubectl exec cpu-throttle-fixed -- cat /sys/fs/cgroup/cpu.stat 2>/dev/null || \
kubectl exec cpu-throttle-fixed -- cat /sys/fs/cgroup/cpu/cpu.stat
# nr_throttled should be 0 or very low

# === 2. OOMKilled ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: oom-test
spec:
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress"]
      args: ["--vm", "1", "--vm-bytes", "200M", "--timeout", "60"]
      resources:
        requests:
          cpu: 50m
          memory: 32Mi
        limits:
          cpu: 100m
          memory: 50Mi
EOF

sleep 15
echo "=== OOMKilled Status ==="
kubectl get pod oom-test
kubectl describe pod oom-test | grep -A 5 "Last State"
# Expect: OOMKilled, Exit Code: 137

# Fix
kubectl delete pod oom-test
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: oom-fixed
spec:
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress"]
      args: ["--vm", "1", "--vm-bytes", "200M", "--timeout", "60"]
      resources:
        requests:
          cpu: 50m
          memory: 256Mi
        limits:
          cpu: 100m
          memory: 300Mi
EOF

sleep 15
echo "=== After Fix ==="
kubectl get pod oom-fixed
# Expect: Running, no restarts

# === 3. Right-sizing ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: oversized-nginx
spec:
  containers:
    - name: nginx
      image: nginx:1.25-alpine
      resources:
        requests:
          cpu: "1"
          memory: 1Gi
        limits:
          cpu: "2"
          memory: 2Gi
EOF

sleep 15
echo "=== Actual Usage ==="
kubectl top pod oversized-nginx
# Expect: CPU ~1-5m, Memory ~5-10Mi
# → Massively over-provisioned!

# Right-sized recommendation:
echo "Recommended:"
echo "  requests: cpu=10m, memory=32Mi"
echo "  limits: cpu=50m, memory=64Mi"

# === Cleanup ===
kubectl delete pod cpu-throttle-test cpu-throttle-fixed oom-test oom-fixed oversized-nginx --ignore-not-found
```

</details>

---

## Bài 3: Hard — ResourceQuota, LimitRange và Multi-team Resource Management

### Context

Bạn là platform engineer quản lý Kubernetes cluster shared cho 3 teams. Mỗi team có namespace riêng. Bạn cần thiết kế resource policies để:
- Mỗi team có fair share resources.
- Ngăn một team dùng hết resources.
- Enforce minimum resource standards.

### Yêu cầu

1. Tạo 3 namespaces: `team-frontend`, `team-backend`, `team-data`.
2. Cho mỗi namespace, tạo:
   - **ResourceQuota**: giới hạn tổng resources (CPU, memory, pod count).
   - **LimitRange**: set default resources, min/max constraints.
3. Resource allocation:
   - `team-frontend`: 2 CPU, 4Gi RAM, max 20 pods
   - `team-backend`: 4 CPU, 8Gi RAM, max 30 pods
   - `team-data`: 3 CPU, 6Gi RAM, max 15 pods
4. Test scenarios:
   - Deploy pods và quan sát quota usage.
   - Thử deploy pod vượt max resources → expect rejection.
   - Thử deploy nhiều pods vượt pod quota → expect rejection.
   - Deploy pod không set resources → verify LimitRange defaults applied.
5. Viết report: tổng resource capacity, per-team allocation, utilization rate.

### Expected Outcome

- 3 namespaces với ResourceQuota + LimitRange configured.
- Pods bị reject khi vượt quota/limits.
- Default resources tự động applied.
- Report chi tiết resource allocation.

### Hint

- ResourceQuota enforced khi pod được tạo, không phải runtime.
- Nếu có ResourceQuota cho CPU/memory, mọi pod PHẢI set requests (hoặc có LimitRange default).
- Dùng `kubectl describe resourcequota` để xem usage vs hard limit.

### Acceptance Criteria

- [ ] 3 namespaces tạo thành công với quota + limitrange.
- [ ] Pods deploy thành công trong quota.
- [ ] Pods bị reject khi vượt quota.
- [ ] LimitRange defaults applied.
- [ ] Resource utilization report viết xong.
- [ ] Cleanup sạch.

### Bonus Challenge

- Thêm PriorityClass: critical pods không bị evict trước non-critical.
- Viết script monitoring quota usage và alert khi > 80%.
- Thêm NetworkPolicy isolate giữa 3 team namespaces.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

# === Create namespaces with policies ===
for team in team-frontend team-backend team-data; do
  kubectl create namespace $team
done

# === team-frontend: 2 CPU, 4Gi, 20 pods ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: quota
  namespace: team-frontend
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 4Gi
    limits.cpu: "4"
    limits.memory: 8Gi
    pods: "20"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: limits
  namespace: team-frontend
spec:
  limits:
    - type: Container
      default:
        cpu: 100m
        memory: 128Mi
      defaultRequest:
        cpu: 50m
        memory: 64Mi
      max:
        cpu: 500m
        memory: 1Gi
      min:
        cpu: 10m
        memory: 16Mi
EOF

# === team-backend: 4 CPU, 8Gi, 30 pods ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: quota
  namespace: team-backend
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "30"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: limits
  namespace: team-backend
spec:
  limits:
    - type: Container
      default:
        cpu: 200m
        memory: 256Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      max:
        cpu: "1"
        memory: 2Gi
      min:
        cpu: 20m
        memory: 32Mi
EOF

# === team-data: 3 CPU, 6Gi, 15 pods ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: quota
  namespace: team-data
spec:
  hard:
    requests.cpu: "3"
    requests.memory: 6Gi
    limits.cpu: "6"
    limits.memory: 12Gi
    pods: "15"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: limits
  namespace: team-data
spec:
  limits:
    - type: Container
      default:
        cpu: 200m
        memory: 512Mi
      defaultRequest:
        cpu: 100m
        memory: 256Mi
      max:
        cpu: "2"
        memory: 4Gi
      min:
        cpu: 50m
        memory: 64Mi
EOF

# === Test: deploy within quota ===
for i in $(seq 1 5); do
  kubectl run app-$i --image=nginx:1.25-alpine -n team-frontend
done
echo "=== Quota usage team-frontend ==="
kubectl describe resourcequota quota -n team-frontend

# === Test: exceed max LimitRange ===
echo "=== Test exceed max ==="
kubectl run big-pod --image=nginx:1.25-alpine -n team-frontend \
  --overrides='{"spec":{"containers":[{"name":"big","image":"nginx:1.25-alpine","resources":{"requests":{"cpu":"2","memory":"2Gi"},"limits":{"cpu":"2","memory":"2Gi"}}}]}}' 2>&1 || echo "Expected: rejected by LimitRange max"

# === Test: default resources ===
echo "=== Test LimitRange defaults ==="
kubectl run default-test --image=nginx:1.25-alpine -n team-backend
sleep 3
kubectl get pod default-test -n team-backend -o jsonpath='{.spec.containers[0].resources}' | python3 -m json.tool 2>/dev/null || \
kubectl get pod default-test -n team-backend -o jsonpath='{.spec.containers[0].resources}'

# === Resource Report ===
echo ""
echo "=========================================="
echo "  Resource Allocation Report"
echo "=========================================="
for ns in team-frontend team-backend team-data; do
  echo ""
  echo "--- $ns ---"
  kubectl describe resourcequota quota -n $ns | grep -E "(Used|Hard|requests|limits|pods)"
done

# === Cleanup ===
kubectl delete namespace team-frontend team-backend team-data
```

</details>

---

## Solution / Reference Implementation

Các reference implementation đầy đủ nằm trong từng block `<details>` của Bài 1, Bài 2 và Bài 3 ở trên. Khi tự chấm bài, verify tối thiểu các điểm sau:

```bash
kubectl get pod -o custom-columns=NAME:.metadata.name,QOS:.status.qosClass -n resource-demo
kubectl top pods -n resource-demo
kubectl describe pod <pod-name> -n resource-demo
kubectl describe resourcequota quota -n team-frontend
```

