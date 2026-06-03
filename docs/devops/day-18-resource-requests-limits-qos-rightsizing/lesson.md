# Day 18: Resource Requests/Limits, QoS Classes & Right-sizing

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** sự khác biệt giữa resource requests và limits, và cách Kubernetes scheduler sử dụng chúng để đặt pod lên node.
2. **Phân biệt được** 3 QoS classes (Guaranteed, Burstable, BestEffort) và thứ tự eviction khi node thiếu resources.
3. **Tái tạo và debug được** CPU throttling và OOMKilled — hai lỗi phổ biến nhất liên quan đến resource configuration.
4. **Thiết kế được** resource requests/limits phù hợp cho các loại workload khác nhau (API server, worker, batch job, database).
5. **Cấu hình được** LimitRange và ResourceQuota để enforce resource policies ở cấp namespace.

---

## 2. Bối cảnh & Động lực

### Vì sao resource management quan trọng?

Trong production, resource management là **yếu tố quyết định** giữa cluster ổn định và cluster liên tục gặp sự cố:

| Không set resources | Hậu quả |
|---------------------|---------|
| Không có requests | Scheduler đặt pod bất kỳ đâu → node overloaded |
| Không có limits | Một pod dùng hết CPU/memory → ảnh hưởng tất cả pods khác trên node |
| Requests quá cao | Wasted resources → tốn tiền cloud, nodes lãng phí |
| Limits quá thấp | CPU throttling → latency tăng, OOMKilled → service crash |

### Production incident thực tế

**Case**: Một e-commerce platform chạy 50+ microservices trên Kubernetes. Đêm Black Friday, traffic tăng 10x:
- 30% services **không set resource limits** → một batch job chiếm hết memory trên 3 nodes.
- Kubelet trigger **eviction** → kill random pods trên các nodes đó.
- API server pods bị evict → 502 cho customers → mất $200K doanh thu trong 45 phút.

**Root cause**: Không có resource limits + không có QoS priority → kubelet evict critical services trước non-critical.

### Liên hệ với developer

Nếu bạn đã quen với:
- **Thread pool sizing** → resource requests/limits là "thread pool" cho CPU/memory ở cấp container.
- **Database connection pool** → quá ít = bottleneck, quá nhiều = wasted connections.
- **Rate limiting API** → limits ngăn một consumer ảnh hưởng consumers khác.

---

## 3. Kiến thức nền tảng

### 3.1 CPU vs Memory — Hai loại resources khác nhau

| Đặc tính | CPU | Memory |
|----------|-----|--------|
| **Loại** | Compressible | Incompressible |
| **Khi vượt limit** | Throttled (giảm tốc) | OOMKilled (bị kill) |
| **Đơn vị** | millicores (m) | bytes (Mi, Gi) |
| **Ví dụ** | `100m` = 0.1 CPU core | `128Mi` = 128 MiB |
| **Recovery** | Tự phục hồi khi load giảm | Pod bị restart |

**Tại sao phân biệt quan trọng?**

- CPU throttling làm **chậm** nhưng không **crash** — service vẫn chạy, chỉ latency tăng.
- OOMKilled **crash** pod ngay lập tức — không graceful shutdown, có thể mất data.

### 3.2 Đơn vị đo

```yaml
# CPU: 1 CPU = 1000m (millicores)
cpu: "1"      # 1 full CPU core
cpu: 500m     # 0.5 CPU core
cpu: 100m     # 0.1 CPU core (typical for lightweight service)

# Memory: binary units
memory: 128Mi  # 128 × 2^20 bytes = 134,217,728 bytes
memory: 1Gi    # 1 × 2^30 bytes = 1,073,741,824 bytes
memory: 256M   # 256 × 10^6 bytes = 256,000,000 bytes (decimal, ít dùng)
```

> **Chú ý**: `Mi` (mebibyte, binary) ≠ `M` (megabyte, decimal). Luôn dùng `Mi`/`Gi` cho consistency.

### 3.3 Cơ chế enforcement bên dưới: Linux cgroup

Kubernetes không tự enforce resources — nó dùng **Linux cgroup** (đã học Day 8):

```
Container Process
    │
    ▼
Linux cgroup v2
    ├── cpu.max         ← CPU limit (CFS quota)
    ├── cpu.weight      ← CPU request (CFS shares)
    ├── memory.max      ← Memory limit
    ├── memory.high     ← Memory throttle threshold
    └── memory.current  ← Current memory usage
```

- **CPU request** → `cpu.weight` (proportional share khi CPU contention).
- **CPU limit** → `cpu.max` (hard cap via CFS bandwidth control — mỗi 100ms period, container chỉ được dùng X ms).
- **Memory limit** → `memory.max` (vượt qua → OOM killer kill process).

---

## 4. Deep Dive

### 4.1 Requests vs Limits

```yaml
resources:
  requests:           # "Minimum guaranteed resources"
    cpu: 100m         # Scheduler dùng để quyết định đặt pod ở node nào
    memory: 128Mi     # Kubelet reserves cho pod
  limits:             # "Maximum allowed resources"
    cpu: 500m         # Container bị throttle nếu dùng > 500m
    memory: 256Mi     # Container bị OOMKilled nếu dùng > 256Mi
```

#### Scheduler Decision Flow

```
Pod cần: requests.cpu=100m, requests.memory=128Mi

Node A: allocatable=2000m CPU, 4Gi RAM
        allocated=1800m CPU, 3.5Gi RAM
        remaining=200m CPU, 512Mi RAM
        → ✅ 200m >= 100m, 512Mi >= 128Mi → CÓ THỂ schedule

Node B: allocatable=2000m CPU, 4Gi RAM
        allocated=1950m CPU, 3.9Gi RAM
        remaining=50m CPU, 100Mi RAM
        → ❌ 50m < 100m → KHÔNG schedule

Node C: allocatable=2000m CPU, 4Gi RAM
        allocated=1000m CPU, 2Gi RAM
        remaining=1000m CPU, 2Gi RAM
        → ✅ → PREFERRED (nhiều resources hơn)
```

> **Quan trọng**: Scheduler chỉ dựa vào **requests**, không dựa vào limits hay actual usage. Đây là lý do requests phải phản ánh đúng mức sử dụng thực tế.

### 4.2 QoS Classes

Kubernetes tự động gán QoS class cho mỗi pod dựa trên resource configuration:

```
┌─────────────────────────────────────────────────────────┐
│                    QoS Classes                          │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Guaranteed   │  │ Burstable    │  │ BestEffort   │  │
│  │              │  │              │  │              │  │
│  │ requests =   │  │ requests set │  │ No requests  │  │
│  │ limits       │  │ but ≠ limits │  │ No limits    │  │
│  │ (cho mọi     │  │ (hoặc chỉ   │  │              │  │
│  │  container)  │  │  một trong   │  │              │  │
│  │              │  │  hai)        │  │              │  │
│  │ Eviction:    │  │ Eviction:    │  │ Eviction:    │  │
│  │ CUỐI CÙNG    │  │ GIỮA        │  │ ĐẦU TIÊN    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  Eviction priority: BestEffort → Burstable → Guaranteed │
└─────────────────────────────────────────────────────────┘
```

#### Guaranteed

```yaml
# requests == limits cho TẤT CẢ containers trong pod
resources:
  requests:
    cpu: 500m
    memory: 256Mi
  limits:
    cpu: 500m        # == requests
    memory: 256Mi    # == requests
```

- Được evict **cuối cùng** khi node pressure.
- Dùng cho: **critical services** (payment, auth, API gateway).
- Trade-off: không burst được, phải size chính xác.

#### Burstable

```yaml
# requests < limits (hoặc chỉ set một trong hai)
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m        # > requests → có thể burst
    memory: 512Mi    # > requests → có thể burst
```

- Eviction priority **giữa**.
- Có thể burst khi node có spare capacity.
- Dùng cho: **hầu hết workloads** (APIs, workers).

#### BestEffort

```yaml
# KHÔNG set requests và limits
# (KHÔNG BAO GIỜ dùng trong production!)
resources: {}
```

- Evict **đầu tiên** khi node pressure.
- Dùng: chỉ cho dev/test environments.

### 4.3 CPU Throttling — Chi tiết

Linux CFS (Completely Fair Scheduler) enforcement:

```
CFS Period: 100ms (mặc định)

CPU Limit: 500m = 50ms per 100ms period

Timeline:
├── 0ms ────── 50ms ────── 100ms ────── 150ms ────── 200ms
│   [Running]  [Throttled]  [Running]    [Throttled]
│   ◀── 50ms ──▶            ◀── 50ms ──▶
│              ◀── wait ──▶              ◀── wait ──▶

Nếu container cần 80ms CPU trong một period:
- Chạy 50ms → bị throttle → đợi 50ms → tiếp tục 30ms ở period tiếp
- Latency tăng ~100% (thay vì 80ms, mất ~160ms)
```

**Phát hiện throttling:**

```bash
# Kiểm tra throttling stats trong container
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu.stat
# nr_periods: tổng số CFS periods
# nr_throttled: số periods bị throttle
# throttled_time: tổng thời gian bị throttle (nanoseconds)

# Nếu nr_throttled / nr_periods > 10% → đang bị throttle đáng kể
```

### 4.4 OOMKilled — Chi tiết

```
Container memory usage approaching limit:

Usage:    ██████████████████████░░  220Mi / 256Mi (86%)
          ████████████████████████▓ 256Mi / 256Mi (100%) ← Kernel OOM Killer triggered
          
Linux kernel OOM killer:
1. Scan processes trong cgroup
2. Chọn process có oom_score cao nhất
3. Send SIGKILL (không SIGTERM!) → Pod restart
4. Exit code: 137 (128 + 9 = SIGKILL)
```

**Dấu hiệu OOMKilled:**

```bash
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState}'
# terminationReason: OOMKilled

kubectl describe pod <pod>
# Last State: Terminated
#   Reason: OOMKilled
#   Exit Code: 137
```

### 4.5 LimitRange & ResourceQuota

#### LimitRange — Default và constraints cho containers

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: production
spec:
  limits:
    - type: Container
      default:           # Tự động set nếu pod không specify
        cpu: 200m
        memory: 256Mi
      defaultRequest:    # Default requests
        cpu: 100m
        memory: 128Mi
      max:               # Maximum cho phép
        cpu: "2"
        memory: 2Gi
      min:               # Minimum cho phép
        cpu: 50m
        memory: 64Mi
    - type: Pod
      max:
        cpu: "4"
        memory: 4Gi
```

#### ResourceQuota — Giới hạn tổng resources trong namespace

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-quota
  namespace: team-a
spec:
  hard:
    requests.cpu: "10"       # Tổng CPU requests tối đa
    requests.memory: 20Gi
    limits.cpu: "20"         # Tổng CPU limits tối đa
    limits.memory: 40Gi
    pods: "50"               # Số pods tối đa
    services: "20"
    persistentvolumeclaims: "10"
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Requests = Limits vs Requests < Limits

| Strategy | Ưu điểm | Nhược điểm | Khi nào dùng |
|----------|---------|------------|-------------|
| **requests = limits** (Guaranteed) | Predictable, không throttle, eviction cuối | Không burst, phải size chính xác, tốn resources | Payment, auth, database, critical path |
| **requests < limits** (Burstable) | Burst khi cần, efficient hơn | Có thể bị throttle/OOMKilled khi contention | APIs, workers, hầu hết services |
| **Chỉ set requests** | Burst không giới hạn | Noisy neighbor risk | Dev/test |
| **Không set gì** (BestEffort) | Dễ | Evict đầu tiên, no guarantee | KHÔNG BAO GIỜ trong production |

### 5.2 Recommendations theo workload type

| Workload | CPU Request | CPU Limit | Memory Request | Memory Limit |
|----------|-------------|-----------|----------------|--------------|
| **API server** (latency-sensitive) | P95 usage | 2-3× request hoặc = request | Baseline + 30% | Request + 50% |
| **Background worker** | Average usage | 2-4× request | Baseline + 20% | Request + 50% |
| **Batch job** | Average usage | Không set hoặc cao | Peak usage | Peak + 20% |
| **Database** | Guaranteed (req=limit) | = request | Guaranteed | = request |
| **Cache (Redis)** | Low (50-100m) | = request | Max dataset size + overhead | = request |

### 5.3 Right-sizing Methodology

```
1. Deploy với generous limits (ước đoán cao)
2. Chạy production traffic 3-7 ngày
3. Thu thập metrics:
   - CPU: P95 usage
   - Memory: P99 usage
4. Set requests = P95 usage × 1.2 (20% buffer)
5. Set limits = requests × 2 (burst headroom)
6. Monitor 1 tuần → điều chỉnh nếu cần
7. Lặp lại mỗi quý hoặc khi traffic pattern thay đổi
```

### 5.4 Anti-patterns

| Anti-pattern | Vấn đề | Cách đúng |
|-------------|--------|-----------|
| Không set requests/limits | No scheduling guarantees, noisy neighbor | Luôn set cả hai |
| Requests quá cao (over-provision) | Waste resources, node underutilized | Right-size dựa trên actual usage |
| Memory limit = request quá thấp | OOMKilled thường xuyên | Cho buffer 20-50% |
| CPU limit quá thấp | Throttling → latency spikes | Monitor throttling, tăng limit |
| Copy-paste resources cho mọi service | Mỗi service khác nhau | Right-size per service |
| Set `memory: 1Gi` cho JVM mà không set `-Xmx` | JVM dùng default heap > container limit | Luôn set JVM `-Xmx` < container memory limit |

---

## 6. Performance & Scalability ⭐

### 6.1 CPU Throttling Impact

```
Latency Impact của CPU throttling:

No throttling:     P50=10ms  P95=25ms   P99=50ms
Light throttling:  P50=15ms  P95=50ms   P99=120ms   (2x P99)
Heavy throttling:  P50=30ms  P95=150ms  P99=500ms   (10x P99)

→ CPU throttling chủ yếu ảnh hưởng tail latency (P99)
→ Đặc biệt nguy hiểm cho latency-sensitive services (API, payment)
```

### 6.2 Memory Over-commit Risk

```
Node: 8Gi allocatable memory

Pod A: requests=1Gi, limits=3Gi
Pod B: requests=1Gi, limits=3Gi
Pod C: requests=1Gi, limits=3Gi
Pod D: requests=1Gi, limits=3Gi

Total requests: 4Gi (50% node) → Scheduler cho phép
Total limits: 12Gi (150% node) → Over-committed!

Nếu tất cả pods burst cùng lúc:
→ Node memory pressure → OOM killer → pods bị kill
```

### 6.3 Node Capacity Planning

```bash
# Kiểm tra node capacity
kubectl describe node <node> | grep -A 10 "Allocated resources"

# Expected output:
# Allocated resources:
#   Resource           Requests     Limits
#   --------           --------     ------
#   cpu                1200m (60%)  3000m (150%)  ← Over-committed!
#   memory             2Gi (50%)    6Gi (150%)    ← Over-committed!

# Rule of thumb:
# - Total requests < 80% node allocatable (buffer cho system)
# - Total limits < 150% node allocatable (reasonable over-commit)
# - Critical namespaces: limits < 100% (no over-commit)
```

---

## 7. Security & Reliability Considerations

### Resource Exhaustion Attack

Nếu không set limits, một compromised container có thể:
- **CPU mining**: dùng hết CPU trên node → ảnh hưởng tất cả pods.
- **Memory bomb**: `:(){ :|:& };:` → OOM kill mọi process trên node.
- **Fork bomb**: tạo vô hạn processes → node unresponsive.

### Defense

- **Luôn set resource limits** cho mọi container.
- Dùng **LimitRange** để enforce defaults cho pods không có limits.
- Dùng **ResourceQuota** để giới hạn tổng resources per namespace.
- **PodDisruptionBudget (PDB)** để đảm bảo minimum pods available khi eviction.

### Noisy Neighbor & Blast Radius

```yaml
# Isolate critical workloads sang dedicated node pool
nodeSelector:
  workload-type: critical  # Node riêng cho critical services

tolerations:
  - key: "dedicated"
    value: "critical"
    effect: "NoSchedule"
```

---

## 8. Hands-on Example

### Prerequisites

```bash
# Verify kind cluster
kind get clusters
# Nếu chưa có:
kind create cluster --name devops-lab

# Cài metrics-server (cần cho kubectl top)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch metrics-server cho kind (TLS issue)
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

# Đợi metrics-server ready
kubectl wait --namespace kube-system --for=condition=ready pod -l k8s-app=metrics-server --timeout=120s
```

### 8.1 Tạo pod bị CPU Throttling

```yaml
# cpu-stress.yaml
apiVersion: v1
kind: Pod
metadata:
  name: cpu-stress
spec:
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress"]
      args: ["--cpu", "2", "--timeout", "120"]
      resources:
        requests:
          cpu: 100m
          memory: 64Mi
        limits:
          cpu: 200m       # Limit 200m nhưng stress 2 cores
          memory: 64Mi
```

```bash
# Deploy
kubectl apply -f cpu-stress.yaml

# Quan sát CPU usage vs limit
kubectl top pod cpu-stress
# Expected: CPU ~200m (capped by limit, không phải 2000m)

# Kiểm tra throttling
kubectl exec cpu-stress -- cat /sys/fs/cgroup/cpu.stat 2>/dev/null || \
kubectl exec cpu-stress -- cat /sys/fs/cgroup/cpu/cpu.stat
# nr_throttled sẽ tăng nhanh → đang bị throttle

# Kiểm tra QoS class
kubectl get pod cpu-stress -o jsonpath='{.status.qosClass}'
# Expected: Burstable (vì requests ≠ limits)

# Cleanup
kubectl delete pod cpu-stress
```

### 8.2 Tạo pod bị OOMKilled

```yaml
# memory-hog.yaml
apiVersion: v1
kind: Pod
metadata:
  name: memory-hog
spec:
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress"]
      args: ["--vm", "1", "--vm-bytes", "200M", "--timeout", "60"]
      resources:
        requests:
          cpu: 50m
          memory: 64Mi
        limits:
          cpu: 100m
          memory: 100Mi    # Limit 100Mi nhưng stress dùng 200M
```

```bash
# Deploy
kubectl apply -f memory-hog.yaml

# Quan sát — pod sẽ bị OOMKilled
sleep 10
kubectl get pod memory-hog
# Expected: STATUS = OOMKilled hoặc CrashLoopBackOff

# Xem chi tiết
kubectl describe pod memory-hog | grep -A 5 "Last State"
# Last State:     Terminated
#   Reason:       OOMKilled
#   Exit Code:    137

# Cleanup
kubectl delete pod memory-hog
```

### 8.3 So sánh 3 QoS classes

```yaml
# qos-demo.yaml
---
apiVersion: v1
kind: Pod
metadata:
  name: qos-guaranteed
spec:
  containers:
    - name: app
      image: nginx:1.25-alpine
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 100m         # == request
          memory: 128Mi     # == request
---
apiVersion: v1
kind: Pod
metadata:
  name: qos-burstable
spec:
  containers:
    - name: app
      image: nginx:1.25-alpine
      resources:
        requests:
          cpu: 50m
          memory: 64Mi
        limits:
          cpu: 200m         # > request
          memory: 256Mi     # > request
---
apiVersion: v1
kind: Pod
metadata:
  name: qos-besteffort
spec:
  containers:
    - name: app
      image: nginx:1.25-alpine
      # Không set resources
```

```bash
# Deploy all
kubectl apply -f qos-demo.yaml

# Kiểm tra QoS class
kubectl get pods -o custom-columns=NAME:.metadata.name,QOS:.status.qosClass
# NAME               QOS
# qos-guaranteed     Guaranteed
# qos-burstable      Burstable
# qos-besteffort     BestEffort

# Cleanup
kubectl delete pod qos-guaranteed qos-burstable qos-besteffort
```

### 8.4 LimitRange và ResourceQuota

```yaml
# namespace-policies.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: resource-demo
---
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: resource-demo
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
        memory: 1Gi
      min:
        cpu: 50m
        memory: 64Mi
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: resource-demo
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 4Gi
    limits.cpu: "4"
    limits.memory: 8Gi
    pods: "10"
```

```bash
# Apply
kubectl apply -f namespace-policies.yaml

# Test: deploy pod KHÔNG set resources → LimitRange tự set defaults
kubectl run test-pod --image=nginx:1.25-alpine -n resource-demo
kubectl get pod test-pod -n resource-demo -o jsonpath='{.spec.containers[0].resources}'
# Expected: {"limits":{"cpu":"200m","memory":"256Mi"},"requests":{"cpu":"100m","memory":"128Mi"}}

# Test: deploy pod vượt max → bị reject
kubectl run big-pod --image=nginx:1.25-alpine -n resource-demo \
  --overrides='{"spec":{"containers":[{"name":"big","image":"nginx:1.25-alpine","resources":{"limits":{"cpu":"5","memory":"10Gi"}}}]}}'
# Expected: Error - must be less than or equal to max limit

# Kiểm tra quota usage
kubectl describe resourcequota team-quota -n resource-demo

# Cleanup
kubectl delete namespace resource-demo
```

### Cleanup toàn bộ

```bash
kubectl delete pod cpu-stress memory-hog qos-guaranteed qos-burstable qos-besteffort --ignore-not-found
kubectl delete namespace resource-demo --ignore-not-found
rm -f cpu-stress.yaml memory-hog.yaml qos-demo.yaml namespace-policies.yaml
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Language-specific Pitfalls

#### Java/JVM

```
Container memory limit: 512Mi
JVM default: -XX:MaxRAMPercentage=25% → Heap = 128Mi
Nhưng JVM còn dùng: metaspace, thread stacks, direct buffers, GC overhead
→ Tổng JVM memory có thể > 512Mi → OOMKilled!

Fix:
-XX:MaxRAMPercentage=75     # JVM biết container limit
-XX:+UseContainerSupport    # Mặc định enabled từ JDK 10+
```

```yaml
# Correct JVM container config
env:
  - name: JAVA_OPTS
    value: "-XX:MaxRAMPercentage=75.0 -XX:+UseContainerSupport"
resources:
  requests:
    memory: 512Mi
  limits:
    memory: 512Mi  # JVM sẽ set heap = 75% × 512 = 384Mi
```

#### Node.js

```
Container memory limit: 256Mi
Node.js default heap: ~1.5Gi (64-bit)
→ Node.js sẽ dùng hết 256Mi → OOMKilled

Fix:
--max-old-space-size=200     # Set heap < container limit
NODE_OPTIONS=--max-old-space-size=200
```

#### Go

```
Container CPU limit: 200m
Go runtime.GOMAXPROCS default: NumCPU() → nếu node 8 core → 8 goroutines
→ 8 goroutines chia 200m CPU → context switching overhead lớn

Fix: (Go 1.19+)
import _ "go.uber.org/automaxprocs"
# Hoặc set env: GOMAXPROCS=1
```

### 9.2 Debug Commands

```bash
# "Service chậm" → kiểm tra CPU throttling
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu.stat
# Nếu nr_throttled cao → tăng CPU limit

# Pod liên tục restart → kiểm tra OOMKilled
kubectl describe pod <pod> | grep -A 5 "Last State"
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'

# Xem actual usage
kubectl top pod <pod>
kubectl top pod --containers  # per-container metrics

# So sánh requests vs actual usage
kubectl top pods -n <ns> --no-headers | \
  awk '{print $1, $2, $3}' | sort -k2 -rn

# Kiểm tra node capacity
kubectl describe node <node> | grep -A 20 "Allocated resources"

# Tìm pods không set resources
kubectl get pods -A -o json | jq -r '.items[] | select(.spec.containers[].resources.requests == null) | .metadata.namespace + "/" + .metadata.name'
```

### 9.3 Production Case Study: Silent CPU Throttling

#### Context
SaaS platform, 200 microservices, P99 latency SLO: 500ms.

#### Symptom
P99 latency tăng từ 200ms lên 1.2s vào peak hours (10-12h), nhưng CPU usage trung bình chỉ 30%.

#### Investigation
```bash
# CPU usage looks fine
kubectl top pods -n production -l app=checkout-service
# NAME                    CPU(cores)   MEMORY(bytes)
# checkout-service-xxx    150m         256Mi      # limit: 500m, usage chỉ 30%

# Nhưng kiểm tra throttling...
kubectl exec checkout-service-xxx -- cat /sys/fs/cgroup/cpu.stat
# nr_periods 1000000
# nr_throttled 450000    # 45% periods bị throttle!
# throttled_time 89000000000
```

#### Root Cause
CPU usage **average** thấp, nhưng có **burst spikes** vượt limit mỗi khi nhận request mới. CFS throttle trong mỗi 100ms period → request phải đợi → latency tăng.

#### Fix
```yaml
# Trước
resources:
  requests:
    cpu: 100m
  limits:
    cpu: 500m

# Sau — tăng limit hoặc bỏ CPU limit
resources:
  requests:
    cpu: 200m    # Tăng request cho scheduling accuracy
  limits:
    cpu: "1"     # Tăng limit cho burst headroom
    # Hoặc: không set CPU limit (controversial nhưng nhiều team lớn làm vậy)
```

#### Lesson Learned
- CPU throttling **không hiện** trên `kubectl top` — phải check cgroup stats.
- Average CPU usage thấp KHÔNG có nghĩa là không bị throttle.
- Một số team (Google, Datadog) khuyến nghị **không set CPU limits** cho latency-sensitive services.

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ bài trước

| Bài | Áp dụng |
|-----|---------|
| Day 8 (Docker Internals) | cgroup = cơ chế enforce resource limits |
| Day 11 (Workload Resources) | Deployment resources trong pod template |
| Day 14 (ConfigMap/Secret) | LimitRange/ResourceQuota là namespace-level config |
| Day 17 (Mini-project) | Thêm resource management cho BookStore stack |

### Bài sau sẽ mở rộng

- **Day 19 (Autoscaling)**: HPA scale dựa trên resource metrics → cần requests/limits chính xác để HPA hoạt động đúng.
- **Day 22 (Troubleshooting)**: Debug OOMKilled, throttling là kỹ năng troubleshooting production quan trọng nhất.
- **Day 24 (Production Checklist)**: Resource configuration là mục bắt buộc trong checklist.

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Docs - Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) — Official guide cho requests/limits.
- [Kubernetes Docs - Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/) — Namespace-level resource management.

### Nice-to-have

- [CPU Limits — Stop Using Them](https://home.robusta.dev/blog/stop-using-cpu-limits) — Controversial nhưng well-researched argument by Robusta.
- [Understanding Kubernetes Limits and Requests (Sysdig)](https://sysdig.com/blog/kubernetes-limits-requests/) — Visual explanation.

### Deep-dive

- [Control Group v2 (kernel.org)](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html) — Linux cgroup internals.
- [CFS Bandwidth Control](https://www.kernel.org/doc/html/latest/scheduler/sched-bwc.html) — CPU throttling mechanism.
- [Kubernetes Resource Management Best Practices (Google Cloud)](https://cloud.google.com/blog/products/containers-kubernetes/kubernetes-best-practices-resource-requests-and-limits) — Production recommendations.

