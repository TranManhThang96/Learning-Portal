# Day 10: Kubernetes Architecture Deep Dive

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Trace được** luồng xử lý từ khi `kubectl apply` YAML manifest đến khi pod chạy trên node.
2. **Giải thích được** vai trò của từng control plane component và failure impact khi mỗi component ngừng hoạt động.
3. **Hiểu được** reconciliation loop — cơ chế tự healing cốt lõi của Kubernetes.
4. **Tạo được** local Kubernetes cluster bằng `kind` và quan sát control plane hoạt động.
5. **Debug được** các vấn đề cơ bản: pod Pending, ImagePullBackOff, cluster không khởi động.

---

## 2. Bối cảnh & Động lực

### Vì sao cần hiểu Kubernetes architecture?

Hầu hết developer dùng Kubernetes ở mức `kubectl apply -f deployment.yaml` và `kubectl get pods`. Khi có vấn đề — pod Pending, service không resolve, deployment stuck — họ không biết bắt đầu debug từ đâu.

**Hiểu architecture giúp bạn:**
- Debug systematic: biết component nào chịu trách nhiệm cho vấn đề đang gặp.
- Thiết kế đúng: hiểu giới hạn và trade-off của mỗi quyết định.
- Đánh giá rủi ro: biết chuyện gì xảy ra khi etcd chết, scheduler lỗi, hoặc kubelet mất kết nối.

### Liên hệ với kiến thức developer

| Concept developer đã biết | Kubernetes equivalent |
|---|---|
| API Gateway | API Server (single entry point, auth, routing) |
| Database (source of truth) | etcd (cluster state store) |
| Background Worker / Cron Job | Controller Manager (reconciliation loops) |
| Load Balancer / Scheduler | Scheduler (place pods on nodes) |
| Agent / Sidecar trên server | Kubelet (node agent) |
| Event-driven architecture | Watch mechanism (controllers watch for changes) |
| Desired state vs actual state | Declarative model (YAML = desired, cluster = actual) |

### Nếu không hiểu architecture?

```
"Pod stuck Pending" 
  → Không biết là scheduler issue, resource issue, hay node issue
  → Random kubectl delete, restart, mất 2 giờ
  → Thực ra chỉ cần: kubectl describe pod → xem Events → "Insufficient cpu"
  → Fix: tăng node hoặc giảm resource requests
```

---

## 3. Kiến thức nền tảng

### Declarative vs Imperative

```bash
# Imperative: nói Kubernetes PHẢI LÀM GÌ (từng bước)
kubectl run nginx --image=nginx
kubectl scale deployment nginx --replicas=3
kubectl expose deployment nginx --port=80

# Declarative: nói Kubernetes TRẠNG THÁI MONG MUỐN (desired state)
kubectl apply -f deployment.yaml
# Kubernetes tự tìm cách đạt trạng thái đó
```

**Kubernetes là declarative system**: bạn mô tả trạng thái mong muốn (desired state) trong YAML, Kubernetes liên tục đảm bảo actual state = desired state.

### Controller Pattern — Reconciliation Loop

```
           ┌─────────────────────────────────┐
           │      Reconciliation Loop        │
           │                                  │
    ┌──────┴──────┐                           │
    │   OBSERVE   │ Watch API server          │
    │  (actual    │ cho thay đổi              │
    │   state)    │                           │
    └──────┬──────┘                           │
           │                                  │
    ┌──────┴──────┐                           │
    │    DIFF     │ So sánh desired           │
    │  (desired   │ vs actual                 │
    │  vs actual) │                           │
    └──────┬──────┘                           │
           │                                  │
    ┌──────┴──────┐                           │
    │    ACT      │ Thực hiện actions         │
    │  (make      │ để actual → desired       │
    │  changes)   │                           │
    └──────┬──────┘                           │
           │                                  │
           └──────────────────────────────────┘
                    (loop forever)
```

**Analogy**: Giống thermostat — bạn set nhiệt độ mong muốn (desired = 25°C), thermostat liên tục đo nhiệt độ thực tế (actual) và bật/tắt điều hòa để đạt desired state.

---

## 4. Deep Dive

### 4.1 Kubernetes Architecture Overview

```
┌───────────────────────────────────────────────────────────┐
│                    CONTROL PLANE                          │
│                                                           │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │ API Server  │  │  etcd    │  │ Controller Manager│   │
│  │             │  │          │  │                    │   │
│  │ • Auth/Authz│  │ • Store  │  │ • ReplicaSet ctrl │   │
│  │ • Admission │  │ • Watch  │  │ • Deployment ctrl │   │
│  │ • Validation│  │ • Quorum │  │ • Node ctrl       │   │
│  │ • REST API  │  │          │  │ • Service ctrl    │   │
│  └──────┬──────┘  └─────┬────┘  └────────┬──────────┘   │
│         │               │                 │               │
│         │          ┌─────┴────────────────┘               │
│         │          │                                      │
│  ┌──────┴──────────┴──┐  ┌──────────────────────────┐   │
│  │   Scheduler         │  │ Cloud Controller Manager │   │
│  │                     │  │ (optional, cloud only)   │   │
│  │ • Filter nodes      │  │ • Node lifecycle         │   │
│  │ • Score nodes       │  │ • Route mgmt            │   │
│  │ • Bind pod → node   │  │ • LB mgmt               │   │
│  └─────────────────────┘  └──────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
                            │
                     ──── Network ────
                            │
┌───────────────────────────────────────────────────────────┐
│                     DATA PLANE (Worker Nodes)             │
│                                                           │
│  ┌─── Node 1 ──────────────────────────────────────────┐ │
│  │                                                      │ │
│  │  ┌──────────┐  ┌────────────┐  ┌─────────────────┐ │ │
│  │  │ kubelet  │  │ kube-proxy │  │ Container       │ │ │
│  │  │          │  │            │  │ Runtime (CRI)   │ │ │
│  │  │ • Watch  │  │ • iptables │  │                  │ │ │
│  │  │   pods   │  │ • IPVS    │  │ • containerd    │ │ │
│  │  │ • Report │  │ • Service │  │ • CRI-O         │ │ │
│  │  │   status │  │   routing │  │                  │ │ │
│  │  └──────────┘  └────────────┘  └─────────────────┘ │ │
│  │                                                      │ │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐              │ │
│  │  │ Pod  │ │ Pod  │ │ Pod  │ │ Pod  │              │ │
│  │  │  A   │ │  B   │ │  C   │ │  D   │              │ │
│  │  └──────┘ └──────┘ └──────┘ └──────┘              │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌─── Node 2 ──────────────────────────────────────────┐ │
│  │  (same structure as Node 1)                          │ │
│  └──────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

### 4.2 Control Plane Components

#### API Server — Cổng vào duy nhất

```
Mọi interaction với cluster đều qua API Server:

kubectl ──────┐
Dashboard ────┤
Controllers ──┼──▶ API Server ──▶ etcd
kubelet ──────┤         │
CI/CD ────────┘         ▼
                    Admission
                    Controllers
```

Vai trò:
- **Authentication**: xác thực identity (certificate, token, OIDC)
- **Authorization**: kiểm tra quyền (RBAC)
- **Admission Control**: mutate/validate request (webhook)
- **Validation**: kiểm tra YAML đúng schema
- **Persistence**: lưu object vào etcd
- **Watch API**: notify controllers khi object thay đổi

#### etcd — Bộ nhớ của cluster

```
etcd là distributed key-value store dùng Raft consensus:

/registry/deployments/default/nginx → {deployment spec}
/registry/pods/default/nginx-abc123 → {pod spec + status}
/registry/services/default/nginx-svc → {service spec}
/registry/secrets/default/db-credentials → {encrypted data}

Đặc điểm:
├── Consistent reads (linearizable)
├── Watch support (real-time notifications)
├── Raft consensus (need quorum: 2/3 hoặc 3/5 nodes)
├── Data encrypted at rest (recommended)
└── CRITICAL: mất etcd = mất toàn bộ cluster state
```

**Failure impact**: etcd down → API server không đọc/ghi state → cluster "đóng băng" (pods vẫn chạy nhưng không thể thay đổi gì).

#### Scheduler — Đặt pod lên node

```
Scheduler Flow:
                                          
1. Watch unscheduled pods        
   (pods without .spec.nodeName)  
                                  
2. Filter nodes (loại bỏ)        
   ├── NodeSelector match?        
   ├── Taint/toleration match?    
   ├── Đủ CPU/memory?             
   ├── Port conflict?             
   └── Affinity/anti-affinity?    
                                  
3. Score nodes (xếp hạng)         
   ├── Least resource usage       
   ├── Spread across zones        
   ├── Node affinity score        
   └── Custom priorities          
                                  
4. Bind: set pod.spec.nodeName    
```

**Failure impact**: Scheduler down → pods mới stay Pending → pods đang chạy không bị ảnh hưởng.

#### Controller Manager — Tự động hóa

Chạy nhiều controllers, mỗi controller có reconciliation loop riêng:

| Controller | Watch | Reconcile |
|-----------|-------|-----------|
| ReplicaSet | ReplicaSet objects | Đảm bảo đúng số replicas |
| Deployment | Deployment objects | Quản lý ReplicaSet (rolling update) |
| Node | Node heartbeats | Mark node NotReady nếu mất heartbeat |
| Service | Service + Endpoints | Cập nhật endpoint list |
| Job | Job objects | Tạo pods cho batch jobs |
| Namespace | Namespace deletion | Cleanup tất cả resources |

**Failure impact**: Controller Manager down → không tự healing (pod chết không tạo lại), deployment không rolling update, nhưng pods đang chạy vẫn OK.

### 4.3 Data Plane Components

#### Kubelet — Agent trên mỗi node

```
Kubelet responsibilities:
├── Watch pods assigned to this node (via API server)
├── Pull container image
├── Create/start container (via CRI → containerd → runc)
├── Monitor container health (liveness/readiness probes)
├── Report node status (capacity, conditions)
├── Report pod status (phase, conditions, container statuses)
└── Mount volumes, inject secrets/configmaps

Kubelet ────CRI───▶ containerd ────OCI───▶ runc
                        │
                    ┌───┴───┐
                    │ Image  │
                    │ Pull   │
                    └────────┘
```

**Failure impact**: Kubelet down trên 1 node → pods trên node đó không được monitor → node marked NotReady sau ~40s → pods rescheduled (nếu có deployment controller).

#### kube-proxy — Service networking

```
kube-proxy modes:

iptables (default):
  Service ClusterIP → iptables rules → random pod IP
  Pros: simple, no userspace, fast
  Cons: no load balancing intelligence, slow at scale (many rules)

IPVS:
  Service ClusterIP → IPVS virtual server → pod IPs
  Pros: better at scale, more LB algorithms
  Cons: more complex, need kernel modules

eBPF (Cilium):
  Service ClusterIP → eBPF program → pod IPs
  Pros: fastest, most flexible, no iptables
  Cons: newer, requires Cilium CNI
```

### 4.4 Request Flow: YAML → Running Pod

```
kubectl apply -f deployment.yaml
         │
         ▼
┌─ 1. API Server ─────────────────────────────────┐
│  • Authenticate user (certificate/token)         │
│  • Authorize (RBAC: can user create deployment?) │
│  • Admission control (mutate/validate)           │
│  • Validate YAML schema                          │
│  • Store Deployment in etcd                      │
└──────────────────────────┬───────────────────────┘
                           │ Watch notification
                           ▼
┌─ 2. Deployment Controller ───────────────────────┐
│  • Observe: new Deployment detected              │
│  • Diff: no ReplicaSet exists yet                │
│  • Act: create ReplicaSet via API Server         │
└──────────────────────────┬───────────────────────┘
                           │
                           ▼
┌─ 3. ReplicaSet Controller ───────────────────────┐
│  • Observe: new ReplicaSet, desired=3, actual=0  │
│  • Diff: need 3 more pods                        │
│  • Act: create 3 Pod objects via API Server      │
└──────────────────────────┬───────────────────────┘
                           │
                           ▼
┌─ 4. Scheduler ───────────────────────────────────┐
│  • Watch: 3 unscheduled pods (no nodeName)       │
│  • Filter: which nodes meet requirements?        │
│  • Score: which node is best?                    │
│  • Bind: set pod.spec.nodeName for each pod      │
└──────────────────────────┬───────────────────────┘
                           │
                           ▼
┌─ 5. Kubelet (on assigned node) ──────────────────┐
│  • Watch: pod assigned to my node                │
│  • Pull image (containerd)                       │
│  • Create container (runc)                       │
│  • Start container                               │
│  • Setup networking (CNI)                        │
│  • Mount volumes                                 │
│  • Run health probes                             │
│  • Report pod status → API Server → etcd         │
└──────────────────────────────────────────────────┘

Result: Pod Running ✅
```

### 4.5 Object Lifecycle

```
Pod Lifecycle:

Pending ──────▶ Running ──────▶ Succeeded
    │              │
    │              ├──▶ Failed
    │              │
    │              └──▶ Unknown (node lost)
    │
    └──▶ Failed (image pull error, etc.)

Pod Phase:
┌──────────┬─────────────────────────────────────────────┐
│ Phase    │ Meaning                                      │
├──────────┼─────────────────────────────────────────────┤
│ Pending  │ Accepted but not all containers started      │
│          │ (scheduling, image pulling)                  │
│ Running  │ At least 1 container running                 │
│ Succeeded│ All containers terminated successfully       │
│ Failed   │ At least 1 container terminated with error   │
│ Unknown  │ Node communication lost                      │
└──────────┴─────────────────────────────────────────────┘
```

---

## 5. Trade-offs & Best Practices ⭐

### Local Kubernetes Tools Comparison

| Tool | Nodes | Resource Usage | Speed | Production-like | Use case |
|------|-------|---------------|-------|----------------|----------|
| **kind** | Multi-node (Docker containers) | Medium | Fast | Medium | CI/CD testing, learning |
| **k3d** | Multi-node (k3s in Docker) | Low | Fast | Medium | Lightweight dev |
| **minikube** | Single node (VM) | High | Slow | Low | Beginners |
| **Docker Desktop K8s** | Single node | High | Medium | Low | Docker users |
| **kubeadm** | Multi-node (VMs) | High | Slow | High | Production-like lab |

**Recommendation**: Dùng **kind** cho khóa học này — multi-node, nhẹ, phù hợp CI/CD.

### Managed vs Self-managed Kubernetes

| Tiêu chí | Managed (EKS/GKE/AKS) | Self-managed (kubeadm) |
|----------|----------------------|----------------------|
| Control plane ops | Cloud provider | Team bạn |
| etcd backup | Tự động | Team bạn chịu trách nhiệm |
| Upgrade | 1-click (với planning) | Manual, risky |
| Cost | Cao hơn ($72-144/month/cluster) | Chỉ infra cost |
| Customization | Limited | Full control |
| Compliance | Shared responsibility | Full responsibility |

### Khi nào Kubernetes là overkill?

```
KHÔNG cần Kubernetes khi:
├── Team < 5 người, 1-3 services
├── Traffic < 1000 RPS, không cần auto-scaling
├── Không cần zero-downtime deployment
├── Budget hạn chế (K8s operational cost cao)
└── Team chưa có K8s experience

→ Dùng: Docker Compose, ECS, Cloud Run, Heroku

CẦN Kubernetes khi:
├── 5+ microservices
├── Cần auto-scaling (HPA)
├── Cần self-healing
├── Multi-environment (dev/staging/prod)
├── Team > 10 developer
└── Cần standardize deployment process
```

---

## 6. Performance & Scalability ⭐

### Kubernetes Limits

| Component | Limit | Bottleneck |
|-----------|-------|-----------|
| Nodes per cluster | ~5000 | API server, etcd |
| Pods per node | ~110 (default) | kubelet, IP exhaustion |
| Pods per cluster | ~150,000 | API server, etcd |
| Services per cluster | ~10,000 | kube-proxy iptables |
| Pods per namespace | ~3,000 | API server pagination |

### API Server Performance

```
API Server là bottleneck số 1 khi scale:

Request rate:
├── Small cluster: ~100 req/s
├── Medium cluster: ~1000 req/s  
├── Large cluster: ~5000 req/s
└── Google-scale: ~10000+ req/s (custom optimizations)

Optimization:
├── API Priority and Fairness (rate limiting)
├── Watch bookmark (reduce reconnection overhead)
├── Resource version caching
└── Reduce unnecessary watches
```

### etcd Performance

```
etcd bottleneck chính là disk I/O:

Recommended:
├── SSD required (nvme preferred)
├── Disk latency < 10ms (p99)
├── etcd data size < 8GB (default quota)
├── Separate disk cho etcd (không share với OS)
└── Regular compaction (auto hoặc manual)

Monitor:
├── etcd_server_slow_apply_total → disk slow
├── etcd_disk_wal_fsync_duration_seconds → disk latency
└── etcd_server_leader_changes_seen_total → cluster unstable
```

---

## 7. Security & Reliability Considerations

### Control Plane Security

```
API Server:
├── TLS everywhere (client → API server → etcd)
├── Authentication: x509 client certs, OIDC, service account tokens
├── Authorization: RBAC (deny by default)
├── Admission: validating + mutating webhooks
├── Audit logging: who did what when
└── API rate limiting

etcd:
├── Encrypt data at rest (EncryptionConfiguration)
├── TLS for peer-to-peer communication
├── Restrict access (only API server should talk to etcd)
├── Regular backups (hourly minimum)
└── Separate network if possible
```

### Control Plane HA

```
Single control plane:
  API Server ──── etcd
  (SPOF!)

HA control plane (production):
  API Server 1 ──┐
  API Server 2 ──┼── Load Balancer ── etcd cluster (3 or 5 nodes)
  API Server 3 ──┘                    
  
  Scheduler: leader election (only 1 active)
  Controller Manager: leader election (only 1 active)
```

### Node Failure Impact

```
Node becomes NotReady:
├── 0-10s: kubelet stops reporting
├── 10-40s: node-controller marks node "Unknown"  
├── 40s: node marked "NotReady"
├── 5min: pods marked for eviction (pod-eviction-timeout)
├── After eviction: pods rescheduled to other nodes
│   └── CHỈ nếu có Deployment/ReplicaSet controller
│       └── Standalone pods KHÔNG tự reschedule!
└── Node comes back: kubelet reconciles
```

---

## 8. Hands-on Example

### Tạo Cluster với kind

```bash
# Cài kind
# go install sigs.k8s.io/kind@latest
# brew install kind (macOS)
# choco install kind (Windows)

kind --version

# Tạo cluster config
cat > kind-config.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF

# Tạo cluster
kind create cluster --name devops-lab --config kind-config.yaml

# Verify
kubectl cluster-info
kubectl get nodes
# Expected:
# NAME                       STATUS   ROLES           AGE   VERSION
# devops-lab-control-plane   Ready    control-plane   2m    v1.29.x
# devops-lab-worker          Ready    <none>          90s   v1.29.x
# devops-lab-worker2         Ready    <none>          90s   v1.29.x
```

### Quan sát Control Plane Components

```bash
# Control plane pods chạy trong namespace kube-system
kubectl get pods -n kube-system
# Expected:
# NAME                                               READY   STATUS
# coredns-xxx                                        1/1     Running
# etcd-devops-lab-control-plane                      1/1     Running
# kube-apiserver-devops-lab-control-plane             1/1     Running
# kube-controller-manager-devops-lab-control-plane    1/1     Running
# kube-proxy-xxx                                     1/1     Running
# kube-scheduler-devops-lab-control-plane             1/1     Running
# kindnet-xxx                                         1/1     Running

# Chi tiết API Server
kubectl describe pod kube-apiserver-devops-lab-control-plane -n kube-system | head -40

# etcd
kubectl describe pod etcd-devops-lab-control-plane -n kube-system | head -30

# API server endpoint
kubectl get endpoints kubernetes
# Expected: ENDPOINTS   10.x.x.x:6443
```

### Trace Flow: YAML → Running Pod

```bash
# Deploy một ứng dụng đơn giản
cat > nginx-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-demo
  labels:
    app: nginx-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx-demo
  template:
    metadata:
      labels:
        app: nginx-demo
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
EOF

# Watch events (mở terminal riêng)
# kubectl get events --watch

# Apply deployment
kubectl apply -f nginx-deployment.yaml

# Trace flow
echo "=== 1. Deployment created ==="
kubectl get deployment nginx-demo
# NAME         READY   UP-TO-DATE   AVAILABLE
# nginx-demo   3/3     3            3

echo ""
echo "=== 2. ReplicaSet created by Deployment Controller ==="
kubectl get replicaset -l app=nginx-demo
# NAME                    DESIRED   CURRENT   READY
# nginx-demo-xxxxxxxxxx   3         3         3

echo ""
echo "=== 3. Pods created by ReplicaSet Controller ==="
kubectl get pods -l app=nginx-demo -o wide
# NAME                          READY   STATUS    NODE
# nginx-demo-xxx-aaa            1/1     Running   devops-lab-worker
# nginx-demo-xxx-bbb            1/1     Running   devops-lab-worker2
# nginx-demo-xxx-ccc            1/1     Running   devops-lab-worker

echo ""
echo "=== 4. Events showing full flow ==="
kubectl get events --field-selector involvedObject.name=nginx-demo --sort-by='.lastTimestamp'
# Events show:
# ScalingReplicaSet (Deployment controller)
# SuccessfulCreate (ReplicaSet controller)
# Scheduled (Scheduler)
# Pulling / Pulled (Kubelet)
# Created / Started (Kubelet)

echo ""
echo "=== 5. Describe pod to see schedule decisions ==="
kubectl describe pod $(kubectl get pods -l app=nginx-demo -o jsonpath='{.items[0].metadata.name}') | grep -A 10 "Events:"
```

### Watch Reconciliation Loop

```bash
# Xóa 1 pod → ReplicaSet controller tự tạo lại
echo "=== Before delete ==="
kubectl get pods -l app=nginx-demo
POD_NAME=$(kubectl get pods -l app=nginx-demo -o jsonpath='{.items[0].metadata.name}')

echo ""
echo "=== Deleting pod $POD_NAME ==="
kubectl delete pod $POD_NAME

echo ""
echo "=== After delete (reconciliation) ==="
sleep 5
kubectl get pods -l app=nginx-demo
# → Vẫn 3 pods! Pod mới được tạo tự động (tên khác)

echo ""
echo "=== Reconciliation events ==="
kubectl get events --sort-by='.lastTimestamp' | tail -5
# → SuccessfulCreate: Created pod: nginx-demo-xxx-NEW
```

### Inspect etcd Content

```bash
# Xem objects lưu trong etcd (qua API server)
kubectl get --raw /api/v1/namespaces/default/pods | python3 -m json.tool 2>/dev/null | head -20

# Xem resource versions
kubectl get deployment nginx-demo -o jsonpath='{.metadata.resourceVersion}'

# Watch mechanism
kubectl get pods -l app=nginx-demo --watch
# → Mở terminal khác, scale deployment
# kubectl scale deployment nginx-demo --replicas=5
# → Watch terminal hiển thị pods mới xuất hiện real-time
```

### Cleanup

```bash
kubectl delete -f nginx-deployment.yaml
kind delete cluster --name devops-lab
rm -f kind-config.yaml nginx-deployment.yaml
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Pod stuck Pending

```bash
kubectl get pod nginx-xxx
# STATUS: Pending

kubectl describe pod nginx-xxx
# Events:
#   Warning  FailedScheduling  0/2 nodes are available:
#   2 Insufficient cpu.

# Root cause: không node nào đủ resource
# Fix: giảm resource requests hoặc thêm node
```

### Pitfall 2: ImagePullBackOff

```bash
kubectl describe pod myapp-xxx
# Events:
#   Warning  Failed  Failed to pull image "myapp:v999": rpc error:
#   code = NotFound desc = failed to pull: not found

# Root cause: image không tồn tại hoặc registry auth lỗi
# Debug:
kubectl get pod myapp-xxx -o jsonpath='{.spec.containers[0].image}'
# Fix: sửa image name/tag hoặc tạo imagePullSecret
```

### Pitfall 3: kind cluster không start (Windows/macOS)

```bash
# Triệu chứng: kind create cluster hangs hoặc fail
# Nguyên nhân: Docker Desktop resource limits quá thấp

# Fix: Docker Desktop → Settings → Resources
# CPU: 4+ cores
# Memory: 8GB+
# Disk: 40GB+
```

### Pitfall 4: CrashLoopBackOff

```bash
kubectl describe pod myapp-xxx
# State: Waiting (CrashLoopBackOff)
# Last State: Terminated (Exit Code: 1)

# Debug:
kubectl logs myapp-xxx                  # Current logs
kubectl logs myapp-xxx --previous       # Previous crash logs

# Root cause thường gặp:
# - Config sai → app crash on startup
# - Missing env var / secret
# - Port conflict
# - Liveness probe too aggressive
```

### Case Study: etcd Disk Pressure

**Context**: Production cluster 200 nodes, suddenly API server chậm.

**Symptom**: kubectl commands mất 5-10s thay vì <1s. New deployments stuck.

**Investigation**:
```bash
# Check etcd health
kubectl get --raw /healthz/etcd
# → unhealthy

# etcd metrics
# etcd_disk_wal_fsync_duration_seconds p99 > 100ms (bình thường <10ms)
# etcd_server_slow_apply_total tăng liên tục
```

**Root Cause**: etcd chạy trên HDD, log volume đầy disk → WAL write chậm → etcd chậm → API server chậm → toàn bộ cluster ảnh hưởng.

**Fix**: 
1. Dọn disk space ngay lập tức
2. Migrate etcd sang SSD
3. Setup alert cho etcd disk latency > 10ms
4. Implement log rotation

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ bài trước

| Bài | Áp dụng |
|-----|---------|
| Day 2 (Process/systemd) | kubelet quản lý containers như systemd quản lý services |
| Day 3 (Networking) | Cluster networking, DNS resolution trong cluster |
| Day 8 (Docker Internals) | Container runtime (containerd → runc) dưới kubelet |
| Day 9 (Image Security) | Image pull, non-root user ảnh hưởng pod startup |

### Preview bài sau

| Bài | Mở rộng |
|-----|---------|
| Day 11 (Workload Resources) | Deployment, StatefulSet, DaemonSet — K8s object types |
| Day 12 (K8s Networking) | Service, CNI, kube-proxy deep dive |
| Day 18 (Resource Requests) | CPU/memory requests/limits → scheduler decisions |
| Day 22 (Troubleshooting) | Systematic K8s debugging methodology |

---

## 11. Tài liệu tham khảo

### Must-read
- [Kubernetes Components](https://kubernetes.io/docs/concepts/overview/components/) — Official docs
- [Kubernetes Architecture (Learnk8s)](https://learnk8s.io/kubernetes-architecture) — Visual explanation
- [What happens when kubectl run](https://github.com/jamiehannaford/what-happens-when-k8s) — Detailed request flow

### Nice-to-have
- [kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/) — Local cluster setup
- [etcd Documentation](https://etcd.io/docs/) — etcd internals
- [Kubernetes API Concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/) — Watch, pagination

### Deep-dive
- [Kubernetes the Hard Way (Kelsey Hightower)](https://github.com/kelseyhightower/kubernetes-the-hard-way) — Build K8s from scratch
- [Kubernetes in Action (2nd Edition)](https://www.manning.com/books/kubernetes-in-action-second-edition) — Manning book
- [Programming Kubernetes (O'Reilly)](https://www.oreilly.com/library/view/programming-kubernetes/9781492047094/) — Building controllers

