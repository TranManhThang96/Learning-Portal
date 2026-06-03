# Day 22: Kubernetes Troubleshooting Methodology

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Áp dụng được** quy trình debug có hệ thống: symptom → scope → hypothesis → verification → mitigation → root cause fix.
2. **Chẩn đoán và sửa được** 7 lỗi phổ biến nhất trong Kubernetes: ImagePullBackOff, CrashLoopBackOff, OOMKilled, Pending pod, Stuck Terminating, DNS issue, Service routing issue.
3. **Sử dụng thành thạo** các công cụ debug: `kubectl describe`, `kubectl logs`, `kubectl events`, `kubectl exec`, `kubectl debug` và ephemeral containers.
4. **Viết được** incident note theo template chuẩn sau mỗi lần debug.
5. **Phân biệt được** khi nào cần mitigation ngay vs khi nào cần tìm root cause trước.

---

## 2. Bối cảnh & Động lực

### Vì sao troubleshooting methodology quan trọng?

Trong production, 80% thời gian on-call là **debug** — không phải deploy. Kubernetes có nhiều moving parts: pod, container, node, network, DNS, storage, admission controller, scheduler — bất kỳ component nào cũng có thể gây lỗi.

### Hậu quả của debug không hệ thống

| Cách debug | Hậu quả |
|------------|---------|
| Restart pod ngay khi thấy lỗi | Mất log, mất evidence, lỗi lặp lại |
| Đoán nguyên nhân rồi sửa ngay | Fix sai chỗ, tạo thêm lỗi mới |
| Google error message → copy paste fix | Không hiểu root cause, technical debt |
| Escalate ngay khi thấy lỗi | Tốn thời gian team, giảm ownership |

### Analogy cho Developer

Debug Kubernetes giống **debug distributed system**:

- Debug monolith: xem 1 log file, trace 1 stack.
- Debug microservices: xem nhiều log files, trace cross-service.
- Debug Kubernetes: xem nhiều log files + **events** + **describe** + **node metrics** + **network** + **scheduler decisions**.

Kubernetes thêm 1 lớp abstraction → thêm failure modes. Nhưng nếu bạn đã quen debug distributed systems, bạn đã có 70% kỹ năng cần thiết.

---

## 3. Kiến thức nền tảng

### 3.1 Quy trình debug có hệ thống

```
┌────────────┐
│  SYMPTOM   │  ← Alert bắn, user report, monitoring dashboard
└─────┬──────┘
      ▼
┌────────────┐
│   SCOPE    │  ← 1 pod? 1 service? 1 node? Toàn cluster?
└─────┬──────┘
      ▼
┌────────────┐
│ HYPOTHESIS │  ← Dựa trên evidence, đặt giả thuyết nguyên nhân
└─────┬──────┘
      ▼
┌────────────┐
│VERIFICATION│  ← Thu thập data để confirm/reject hypothesis
└─────┬──────┘
      ▼
┌────────────┐
│ MITIGATION │  ← Giảm impact ngay (rollback, scale, restart)
└─────┬──────┘
      ▼
┌────────────┐
│ ROOT CAUSE │  ← Tìm và fix nguyên nhân gốc
│    FIX     │
└────────────┘
```

**Nguyên tắc quan trọng**: **Mitigation trước, root cause sau**. Nếu service đang down ảnh hưởng users → giảm impact ngay (rollback, restart, scale) → sau đó mới tìm root cause khi hệ thống đã ổn định.

### 3.2 Kubernetes Object Lifecycle

```
                  ┌─────────┐
                  │ Pending │  ← Chờ scheduler assign node
                  └────┬────┘
                       ▼
                  ┌─────────┐
                  │ Running │  ← Container đang chạy
                  └────┬────┘
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
        ┌──────────┐ ┌────────┐ ┌────────────┐
        │Succeeded │ │ Failed │ │  Unknown   │
        └──────────┘ └────────┘ └────────────┘
```

### 3.3 Nơi tìm thông tin debug

| Thông tin | Lệnh | Khi nào dùng |
|-----------|-------|-------------|
| Object status & events | `kubectl describe pod <name>` | Luôn luôn — bước đầu tiên |
| Container logs | `kubectl logs <pod> [-c container]` | Khi pod đã start được |
| Previous container logs | `kubectl logs <pod> --previous` | Khi pod crash loop |
| Cluster events | `kubectl get events --sort-by=.lastTimestamp` | Xem timeline sự kiện |
| Exec vào container | `kubectl exec -it <pod> -- /bin/sh` | Debug từ bên trong |
| Debug container | `kubectl debug <pod> --image=busybox` | Container không có shell |
| Node status | `kubectl describe node <node>` | Lỗi liên quan node |
| Resource usage | `kubectl top pod/node` | Kiểm tra CPU/memory |

---

## 4. Deep Dive — 7 Debug Cases

### 4.1 ImagePullBackOff

**Symptom**: Pod stuck ở trạng thái `ImagePullBackOff` hoặc `ErrImagePull`.

**Nguyên nhân phổ biến**:
- Image name/tag sai (typo)
- Image không tồn tại trên registry
- Registry cần authentication nhưng thiếu `imagePullSecrets`
- Network từ node tới registry bị block
- Rate limit (Docker Hub: 100 pulls/6h cho anonymous)

**Debug flow**:

```bash
# Step 1: Xem events
kubectl describe pod <pod-name>
# Tìm: "Failed to pull image" + chi tiết error

# Step 2: Verify image tồn tại
docker pull <image-name>:<tag>
# Hoặc: crane manifest <image-name>:<tag>

# Step 3: Check imagePullSecrets
kubectl get pod <pod-name> -o jsonpath='{.spec.imagePullSecrets}'
kubectl get secret <secret-name> -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d

# Step 4: Check network từ node
kubectl debug node/<node-name> -it --image=busybox -- nslookup registry-1.docker.io
```

**Fix pattern**:

| Nguyên nhân | Fix |
|-------------|-----|
| Image name sai | Sửa image name trong manifest |
| Thiếu auth | Tạo `docker-registry` secret + thêm `imagePullSecrets` |
| Rate limit | Dùng registry mirror, hoặc authenticate Docker Hub |
| Network block | Check NetworkPolicy, firewall, proxy |

### 4.2 CrashLoopBackOff

**Symptom**: Pod restart liên tục, status `CrashLoopBackOff`, restart count tăng.

**Cơ chế**: Container start → crash → Kubernetes restart → crash → restart. Backoff delay tăng dần: 10s → 20s → 40s → ... → max 5 phút.

**Nguyên nhân phổ biến**:
- Application crash khi startup (config sai, dependency unavailable)
- Liveness probe fail liên tục
- Entrypoint/command sai
- Permission denied (non-root container cần write vào root-owned dir)
- Missing environment variables hoặc mounted secrets

**Debug flow**:

```bash
# Step 1: Xem logs container hiện tại
kubectl logs <pod-name>

# Step 2: Nếu container mới crash → xem logs lần trước
kubectl logs <pod-name> --previous

# Step 3: Check exit code
kubectl describe pod <pod-name>
# Tìm: "Last State: Terminated" → Exit Code
# Exit Code 1: application error
# Exit Code 137: OOMKilled (SIGKILL) hoặc killed by system
# Exit Code 139: Segmentation fault
# Exit Code 143: SIGTERM (graceful shutdown but failed)

# Step 4: Nếu không có logs → exec vào container
kubectl run debug-pod --image=<same-image> --command -- sleep 3600
kubectl exec -it debug-pod -- /bin/sh
# Chạy entrypoint manually, xem lỗi gì

# Step 5: Check events
kubectl get events --field-selector involvedObject.name=<pod-name>
```

### 4.3 OOMKilled

**Symptom**: Pod bị terminate, status `OOMKilled`, Exit Code 137.

**Cơ chế**: Container sử dụng memory vượt `resources.limits.memory` → kernel OOM killer giết process.

**Debug flow**:

```bash
# Step 1: Confirm OOMKilled
kubectl describe pod <pod-name>
# Tìm: "Reason: OOMKilled", "Exit Code: 137"

# Step 2: Xem memory limit
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].resources}'

# Step 3: Xem actual memory usage (nếu có metrics-server)
kubectl top pod <pod-name>

# Step 4: Xem memory usage pattern
kubectl logs <pod-name> --previous | grep -i "memory\|heap\|alloc"

# Step 5: Check node memory pressure
kubectl describe node <node-name> | grep -A5 "Conditions"
```

**Fix pattern**:

| Tình huống | Fix |
|------------|-----|
| Memory limit quá thấp | Tăng `resources.limits.memory` |
| Memory leak trong app | Fix application code, profiling |
| JVM heap không set | Set `-Xmx` bằng 75% container memory limit |
| Node memory pressure | Reduce pod density, add nodes |

### 4.4 Pending Pod

**Symptom**: Pod stuck ở trạng thái `Pending`, không được schedule.

**Debug flow**:

```bash
# Step 1: Xem events
kubectl describe pod <pod-name>
# Tìm events từ scheduler

# Step 2: Decode scheduler message
# "Insufficient cpu" → node không đủ CPU cho requests
# "Insufficient memory" → node không đủ memory
# "0/3 nodes are available: 3 node(s) had taint" → taint/toleration
# "0/3 nodes are available: 3 Insufficient cpu" → cluster hết resource
# "persistentvolumeclaim not found" → PVC chưa bound

# Step 3: Check node resources
kubectl describe nodes | grep -A5 "Allocated resources"

# Step 4: Check PVC nếu pod dùng volumes
kubectl get pvc
kubectl describe pvc <pvc-name>

# Step 5: Check taints
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints
```

**Fix pattern**:

| Nguyên nhân | Fix |
|-------------|-----|
| Insufficient resources | Giảm requests, add nodes, hoặc evict low-priority pods |
| Taint/toleration | Thêm toleration vào pod spec |
| PVC unbound | Tạo PV, check StorageClass, check provisioner |
| Node selector mismatch | Sửa nodeSelector hoặc label node |
| Pod affinity conflict | Review affinity rules |

### 4.5 Stuck Terminating

**Symptom**: Pod stuck ở `Terminating`, không biến mất dù đã `kubectl delete`.

**Nguyên nhân phổ biến**:
- Finalizer chưa complete
- Container không handle SIGTERM → chờ 30s grace period → SIGKILL nhưng process vẫn stuck
- Node unreachable (network partition)
- Volume unmount chậm

**Debug flow**:

```bash
# Step 1: Check finalizers
kubectl get pod <pod-name> -o jsonpath='{.metadata.finalizers}'

# Step 2: Check thời gian đã Terminating
kubectl get pod <pod-name> -o jsonpath='{.metadata.deletionTimestamp}'

# Step 3: Check node status
kubectl get node <node-name>
# Nếu NotReady → node problem

# Step 4: Force delete (SAU KHI đã investigate)
kubectl delete pod <pod-name> --grace-period=0 --force
```

**Cảnh báo**: `--force` delete có thể gây orphan container trên node. Chỉ dùng khi đã xác nhận node unreachable hoặc container đã stop.

### 4.6 DNS Issue

**Symptom**: Service không thể resolve tên service khác. `curl http://service-name:port` timeout hoặc `NXDOMAIN`.

**Debug flow**:

```bash
# Step 1: Test DNS từ trong pod
kubectl exec -it <pod> -- nslookup kubernetes.default
kubectl exec -it <pod> -- nslookup <service-name>
kubectl exec -it <pod> -- nslookup <service-name>.<namespace>.svc.cluster.local

# Step 2: Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns

# Step 3: Check Service và Endpoints
kubectl get svc <service-name>
kubectl get endpoints <service-name>
# Endpoints rỗng = không có pod match selector

# Step 4: Check /etc/resolv.conf trong pod
kubectl exec <pod> -- cat /etc/resolv.conf
# Phải có: nameserver <CoreDNS ClusterIP>

# Step 5: Check ndots config
# Default ndots:5 → K8s thử 4 suffix trước khi query absolute
# "api.example.com" → thử api.example.com.default.svc.cluster.local trước!
```

**Fix pattern**:

| Nguyên nhân | Fix |
|-------------|-----|
| CoreDNS crash | Restart CoreDNS, check resource limits |
| Service selector mismatch | Fix labels trên pod để match service selector |
| NetworkPolicy block DNS | Allow egress UDP port 53 tới kube-dns |
| ndots:5 slow DNS | Dùng FQDN (`svc.ns.svc.cluster.local.`) hoặc giảm ndots |

### 4.7 Service Routing Issue

**Symptom**: Service tồn tại, DNS resolve OK, nhưng traffic không tới pod hoặc tới sai pod.

**Debug flow**:

```bash
# Step 1: Verify Service → Endpoints mapping
kubectl get endpoints <service-name>
# Nếu rỗng → không có pod match selector

# Step 2: Compare service selector vs pod labels
kubectl get svc <service-name> -o jsonpath='{.spec.selector}'
kubectl get pods --show-labels

# Step 3: Check port mapping
kubectl get svc <service-name> -o yaml
# service.spec.ports[].targetPort phải match container port

# Step 4: Check pod readiness
kubectl get pods -o wide
# Pod phải READY (readiness probe pass) mới nhận traffic

# Step 5: Test trực tiếp tới pod IP
kubectl get pod <pod> -o jsonpath='{.status.podIP}'
kubectl exec debug-pod -- curl <pod-ip>:<container-port>
```

---

## 5. Trade-offs & Best Practices ⭐

### Debug Methodology Trade-offs

| Approach | Ưu điểm | Nhược điểm | Khi nào dùng |
|----------|---------|-----------|-------------|
| Systematic (full flow) | Tìm đúng root cause, documentation tốt | Chậm hơn | Non-urgent, complex issues |
| Quick mitigation first | Giảm impact nhanh | Có thể miss root cause | P1/P2 incidents ảnh hưởng users |
| Pattern matching | Nhanh với known issues | Bias, miss novel issues | Recurring/known errors |
| Bisect/binary search | Hiệu quả khi scope lớn | Cần clear signal | "Something changed" issues |

### Anti-patterns

1. **Restart-first**: Restart pod trước khi xem logs → mất evidence. **Luôn collect evidence trước**.
2. **Google-driven debugging**: Copy paste fix từ StackOverflow không hiểu → technical debt. **Hiểu rồi mới áp dụng**.
3. **Blame game**: "DevOps team fix đi" → chậm resolution. **Cùng debug, cùng ownership**.
4. **Không viết incident note**: Lỗi tương tự xảy ra lại → debug từ đầu. **Luôn document**.

### Tool Selection Guide

```
Pod không start được?
  ├── Status: ImagePullBackOff → kubectl describe pod
  ├── Status: Pending → kubectl describe pod (scheduler events)
  ├── Status: CrashLoopBackOff → kubectl logs --previous
  └── Status: Running nhưng không work → kubectl exec + kubectl logs

Pod running nhưng lỗi?
  ├── Application error → kubectl logs [-f]
  ├── Connectivity issue → kubectl exec + curl/nslookup
  ├── Performance issue → kubectl top pod + kubectl exec
  └── Intermittent → kubectl logs --since=1h + events

Cluster-wide issue?
  ├── Node problem → kubectl describe node
  ├── DNS issue → kubectl exec + nslookup + CoreDNS logs
  ├── Network issue → kubectl exec + tcpdump/curl
  └── Resource shortage → kubectl top nodes + kubectl describe nodes
```

---

## 6. Performance & Scalability ⭐

### Debug Tools — Performance Impact

| Tool | Impact | Lưu ý |
|------|--------|-------|
| `kubectl describe` | Không (read-only API call) | An toàn dùng mọi lúc |
| `kubectl logs` | Thấp (stream từ kubelet) | `-f` giữ connection mở |
| `kubectl logs --previous` | Không | Đọc từ disk |
| `kubectl exec` | Thấp-Trung | Tạo exec stream, tốn bandwidth nếu transfer data |
| `kubectl debug` (ephemeral container) | Trung | Tạo container mới trong pod |
| `kubectl debug` (node debug) | Cao | Tạo privileged pod trên node |
| `kubectl top` | Thấp | Cần metrics-server |
| `kubectl port-forward` | Trung | Giữ tunnel mở, single-threaded |

### Khi debug cluster lớn

- Dùng `--field-selector` thay vì grep trên client side:
  ```bash
  # Tốt: filter trên server
  kubectl get events --field-selector involvedObject.name=my-pod
  
  # Kém: lấy hết rồi grep
  kubectl get events | grep my-pod
  ```
- Dùng `--selector` để narrow scope.
- Tránh `kubectl get pods -A` trên cluster 10K+ pods — dùng namespace scope.

---

## 7. Security & Reliability Considerations

### Security Risks khi Debug

| Action | Risk | Mitigation |
|--------|------|-----------|
| `kubectl exec` | Code execution trong container | RBAC restrict, audit log |
| `kubectl debug` node | Privileged access toàn node | Restrict, time-limited sessions |
| Port-forwarding | Bypass NetworkPolicy | Chỉ dùng cho debug, không production traffic |
| Copy logs ra ngoài | Data leakage | Review log content, mask sensitive data |

### Best Practices

- **Audit logging**: Enable Kubernetes audit logs để track mọi `exec`, `debug` commands.
- **RBAC**: Chỉ cho `exec` trong non-production namespaces. Production cần approval.
- **Ephemeral containers**: Dùng thay vì `exec` khi container không có shell (distroless images).
- **Time-limited debug**: Set TTL cho debug pods, cleanup sau debug session.

---

## 8. Hands-on Example — Broken Cluster Challenge

### Setup: Tạo cluster với 5 lỗi cài sẵn

```bash
# Tạo cluster
kind create cluster --name debug-lab --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF

kubectl cluster-info
```

#### Bug 1: ImagePullBackOff

```yaml
# bug1-imagepull.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-frontend
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web-frontend
  template:
    metadata:
      labels:
        app: web-frontend
    spec:
      containers:
        - name: web
          image: nginx:99.99-nonexistent
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
```

#### Bug 2: CrashLoopBackOff

```yaml
# bug2-crashloop.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      containers:
        - name: api
          image: busybox:1.36
          command: ["sh", "-c", "echo 'Starting...' && exit 1"]
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
```

#### Bug 3: OOMKilled

```yaml
# bug3-oom.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-hog
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: memory-hog
  template:
    metadata:
      labels:
        app: memory-hog
    spec:
      containers:
        - name: hog
          image: polinux/stress:1.0.4
          command: ["stress", "--vm", "1", "--vm-bytes", "256M", "--vm-hang", "1"]
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
```

#### Bug 4: Service Routing Issue

```yaml
# bug4-service-mismatch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
      version: v2
  template:
    metadata:
      labels:
        app: backend
        version: v2
    spec:
      containers:
        - name: backend
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
---
apiVersion: v1
kind: Service
metadata:
  name: backend-svc
spec:
  selector:
    app: backend
    version: v1          # ← BUG: selector v1 nhưng pods là v2
  ports:
    - port: 80
      targetPort: 80
```

#### Bug 5: Pending Pod (resource)

```yaml
# bug5-pending.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: resource-monster
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: resource-monster
  template:
    metadata:
      labels:
        app: resource-monster
    spec:
      containers:
        - name: monster
          image: nginx:1.25
          resources:
            requests:
              cpu: "100"
              memory: "512Gi"
            limits:
              cpu: "100"
              memory: "512Gi"
```

```bash
# Deploy tất cả bugs
kubectl apply -f bug1-imagepull.yaml
kubectl apply -f bug2-crashloop.yaml
kubectl apply -f bug3-oom.yaml
kubectl apply -f bug4-service-mismatch.yaml
kubectl apply -f bug5-pending.yaml

# Verify — tất cả đều có vấn đề
kubectl get pods -o wide
kubectl get svc
```

### Debug từng bug

**Bug 1 — ImagePullBackOff:**

```bash
kubectl describe pod -l app=web-frontend
# Events: "Failed to pull image nginx:99.99-nonexistent: tag does not exist"
# Fix:
kubectl set image deployment/web-frontend web=nginx:1.25
```

**Bug 2 — CrashLoopBackOff:**

```bash
kubectl logs -l app=api-service --previous
# Output: "Starting..." → exit 1
# Fix: sửa command
kubectl patch deployment api-service --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command","value":["sh","-c","echo Starting && sleep 3600"]}]'
```

**Bug 3 — OOMKilled:**

```bash
kubectl describe pod -l app=memory-hog
# State: Terminated, Reason: OOMKilled, Exit Code: 137
# stress --vm-bytes 256M > limit 128Mi
# Fix: tăng memory limit
kubectl patch deployment memory-hog --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"256Mi"}]'
```

**Bug 4 — Service Routing:**

```bash
kubectl get endpoints backend-svc
# ENDPOINTS: <none> ← rỗng!
kubectl get svc backend-svc -o jsonpath='{.spec.selector}'
# {"app":"backend","version":"v1"}
kubectl get pods -l app=backend --show-labels
# version=v2 → mismatch!
# Fix:
kubectl patch svc backend-svc --type json \
  -p '[{"op":"replace","path":"/spec/selector/version","value":"v2"}]'
kubectl get endpoints backend-svc
# Bây giờ có endpoints
```

**Bug 5 — Pending:**

```bash
kubectl describe pod -l app=resource-monster
# Events: "Insufficient cpu", "Insufficient memory"
# Requests: 100 CPU + 512Gi memory → impossible
# Fix:
kubectl patch deployment resource-monster --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"200m"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}]'
```

### Verify tất cả đã fix

```bash
kubectl get pods
# Tất cả phải Running, READY

kubectl get endpoints backend-svc
# Phải có IPs
```

### Cleanup

```bash
kubectl delete deployment --all
kubectl delete svc backend-svc
kind delete cluster --name debug-lab
```

---

## 9. Common Pitfalls & Production Case Studies

### Production Case Study 1: DNS Storm Gây Latency Spike

#### Context
E-commerce platform, 200 microservices, 1500 pods, peak 5K RPS. Dùng Kubernetes trên AWS EKS.

#### Symptom
Latency P99 tăng từ 100ms lên 2s vào peak hours. Không có deployment nào mới. Alert: "High latency on API gateway."

#### Investigation

```bash
# Step 1: Check API gateway pod
kubectl top pod -l app=api-gateway
# CPU/memory bình thường

# Step 2: Check CoreDNS
kubectl top pod -n kube-system -l k8s-app=kube-dns
# CPU đang ở 90%!

# Step 3: Check CoreDNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns | tail -100
# Rất nhiều query cho: "payment-service.default.svc.cluster.local"
# Mỗi pod generate ~50 DNS queries/second

# Step 4: Check resolv.conf
kubectl exec api-gateway-xxx -- cat /etc/resolv.conf
# ndots:5 → mỗi query internal service thử 5 suffixes trước!
```

#### Root Cause
`ndots:5` (default) khiến mỗi DNS query thử 4-5 suffixes trước khi resolve đúng. 200 services × multiple queries × ndots expansion = CoreDNS overload.

#### Mitigation
Scale CoreDNS replicas từ 2 lên 6 ngay.

#### Long-term Fix
1. Sử dụng FQDN trong code: `payment-service.default.svc.cluster.local.` (trailing dot).
2. Giảm `ndots` xuống 2 trong pod spec:
   ```yaml
   dnsConfig:
     options:
       - name: ndots
         value: "2"
   ```
3. Enable NodeLocal DNSCache.

#### Lesson Learned
DNS là single point of failure ẩn trong Kubernetes. Monitor CoreDNS resource usage.

#### Prevention
- Alert khi CoreDNS CPU > 70%.
- Thêm NodeLocal DNSCache vào cluster baseline.
- Review `ndots` setting trong pod template.

---

### Production Case Study 2: Silent CPU Throttling

#### Context
SaaS platform, Go-based API service, Kubernetes trên GKE. Service xử lý 2K RPS.

#### Symptom
Latency P99 tăng 3x nhưng CPU usage dashboard chỉ ~40%. Không có code change. Alert: "SLO violation on /api/v2/users endpoint."

#### Investigation

```bash
# Step 1: Check resource config
kubectl get deployment api-service -o yaml | grep -A10 resources
# requests: cpu=100m, limits: cpu=200m

# Step 2: Check actual CPU usage
kubectl top pod -l app=api-service
# CPU: 180m / 200m limit ← gần limit!

# Step 3: Check throttling metrics
kubectl exec api-xxx -- cat /sys/fs/cgroup/cpu/cpu.stat
# nr_throttled: 45672 ← BIG number!
# throttled_time: 12345678901 ns

# Step 4: Check container metrics (Prometheus)
# container_cpu_cfs_throttled_periods_total > 50%
```

#### Root Cause
CPU limit 200m quá thấp cho Go service nhiều goroutines. CFS scheduler throttle CPU khi vượt limit → latency tăng. Dashboard thấy ~40% vì đo trung bình cả node, không phải per-container throttling.

#### Mitigation
Tăng CPU limit lên 1000m ngay.

#### Long-term Fix
1. Nhiều teams đang loại bỏ CPU limits hoàn toàn (chỉ set requests) — Google SRE recommendation.
2. Nếu giữ CPU limits: set >= 2-3x requests.
3. Monitor `container_cpu_cfs_throttled_periods_total` metric.

#### Lesson Learned
CPU throttling là **silent killer** — `kubectl top` và dashboard trung bình KHÔNG thấy được. Phải check cgroup stats hoặc Prometheus throttling metrics.

#### Prevention
- Alert khi throttled_periods > 25%.
- Right-sizing based on P99 CPU, không phải average.
- Xem xét loại bỏ CPU limits cho non-critical workloads.

---

### Production Case Study 3: Stuck Terminating Pods Gây Resource Leak

#### Context
Logistics platform, 50 services, Kubernetes on bare-metal. Weekly cluster maintenance.

#### Symptom
Sau drain node cho maintenance, 15 pods stuck ở `Terminating` > 2 giờ. New pods `Pending` vì "Insufficient memory" dù cluster capacity đủ.

#### Investigation

```bash
# Step 1: Check stuck pods
kubectl get pods --field-selector=status.phase=Running -A | wc -l
# 340 running + 15 Terminating

# Step 2: Check resource allocation
kubectl describe nodes | grep -A8 "Allocated resources"
# Terminating pods vẫn count trong allocation!

# Step 3: Check finalizers
kubectl get pod stuck-pod-1 -o jsonpath='{.metadata.finalizers}'
# ["custom.cleanup/database-connection"]

# Step 4: Check finalizer controller
kubectl logs -n system deployment/cleanup-controller
# "Error: database connection timeout"
```

#### Root Cause
Custom finalizer controller bị lỗi kết nối database → không cleanup được → pods stuck Terminating → resource allocation không release → new pods Pending.

#### Mitigation
Remove finalizers từ stuck pods (sau khi verify manual cleanup):
```bash
kubectl patch pod stuck-pod-1 -p '{"metadata":{"finalizers":null}}' --type merge
```

#### Long-term Fix
1. Thêm timeout cho finalizer controller (max 5 phút).
2. Alert khi pods Terminating > 10 phút.
3. Finalizer controller cần graceful degradation khi dependency unavailable.

---

## 10. Kết nối với bài trước & bài sau

### Từ Day 21 (Admission Controller)

Khi admission policy chặn nhầm workload:
- Event sẽ hiển thị: `admission webhook denied the request`.
- Debug bằng: `kubectl describe pod` → xem events → check PolicyReport.
- Đây là 1 trong những "new failure modes" khi thêm admission control layer.

### Sang Day 23 (Kubernetes Upgrade, Backup & Node Maintenance)

- Troubleshooting skills rất cần trong upgrade process: pods bị evict, PDB blocking drain, version skew issues.
- Node maintenance (drain/cordon) có thể trigger nhiều bugs đã học hôm nay.
- Upgrade là thời điểm incident rate cao — cần debug methodology vững.

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Troubleshooting Guide (Official)](https://kubernetes.io/docs/tasks/debug/)
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [Ephemeral Containers](https://kubernetes.io/docs/concepts/workloads/pods/ephemeral-containers/)

### Nice-to-have

- [Kubernetes Debugging Flows (learnk8s.io)](https://learnk8s.io/troubleshooting-deployments)
- [kubectl debug Documentation](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_debug/)
- [A visual guide on troubleshooting Kubernetes deployments](https://learnk8s.io/troubleshooting-deployments)

### Deep-dive

- [SRE Book — Chapter 12: Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/)
- [Brendan Gregg — Linux Performance Analysis](https://www.brendangregg.com/linuxperf.html)
- [Komodor Kubernetes Troubleshooting Blog](https://komodor.com/learn/kubernetes-troubleshooting/)

