# Day 23: Kubernetes Upgrade, Backup & Node Maintenance

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** version skew policy của Kubernetes và lý do không thể skip minor versions khi upgrade.
2. **Thực hiện được** quy trình upgrade control plane → nodes theo đúng thứ tự, bao gồm drain/cordon.
3. **Cấu hình và test được** PodDisruptionBudget để đảm bảo availability trong quá trình maintenance.
4. **Backup và restore được** etcd snapshot và namespace resources bằng Velero.
5. **Đánh giá được** trade-offs giữa in-place upgrade vs blue-green cluster upgrade.

---

## 2. Bối cảnh & Động lực

### Vì sao upgrade & maintenance quan trọng?

Kubernetes release **3 minor versions mỗi năm** (khoảng 4 tháng/version). Mỗi version chỉ được support **~14 tháng**. Sau đó: không có security patches, không fix bugs.

### Hậu quả của không upgrade

| Tình huống | Hậu quả |
|------------|---------|
| Chạy version cũ > 2 năm | Không có CVE patches, vulnerable |
| Skip nhiều minor versions | Upgrade path phức tạp, breaking changes tích lũy |
| Upgrade không có PDB | Downtime khi drain node, user impact |
| Không backup etcd | Mất cluster state = mất tất cả |
| Upgrade control plane + nodes cùng lúc | Version skew → API incompatibility |

### Analogy cho Developer

- **Kubernetes upgrade** giống **database migration**: phải chạy tuần tự (v1.28 → v1.29 → v1.30), không skip bước, có rollback plan.
- **etcd backup** giống **database backup**: mất etcd = mất toàn bộ cluster state (giống mất database production).
- **Node drain** giống **graceful shutdown**: di chuyển workload sang nơi khác trước khi tắt server.
- **PDB** giống **rate limiter cho eviction**: đảm bảo luôn có đủ pods running khi drain.

---

## 3. Kiến thức nền tảng

### 3.1 Kubernetes Release Cycle

```
v1.28 ────→ v1.29 ────→ v1.30 ────→ v1.31
 │           │           │           │
 │ 4 months  │ 4 months  │ 4 months  │
 │           │           │           │
 └─ support ─┘─ support ─┘─ support ─┘
   ~14 months   ~14 months
```

- **Major version**: 1 (rarely changes)
- **Minor version**: 28, 29, 30... (new features, API changes)
- **Patch version**: 1.29.1, 1.29.2... (bug fixes, security patches)
- **Support window**: khoảng 14 tháng per minor version

### 3.2 Version Skew Policy

Kubernetes yêu cầu các components phải giữ version trong khoảng cho phép:

| Component | So với API Server | Allowed Skew |
|-----------|------------------|-------------|
| kubelet | ≤ API server | (-2, 0) minor versions |
| kube-proxy | ≤ API server | (-2, 0) |
| kubectl | ± API server | (-1, +1) |
| kube-controller-manager | ≤ API server | (-1, 0) |
| kube-scheduler | ≤ API server | (-1, 0) |
| etcd | Không bị ràng buộc | Theo etcd support matrix |

**Ý nghĩa thực tế**: 
- API server **phải upgrade trước**, rồi mới upgrade kubelet trên nodes.
- Kubelet có thể cũ hơn API server tối đa 2 minor versions.
- Không bao giờ upgrade kubelet lên version cao hơn API server.

### 3.3 Upgrade Order

```
┌─────────────────────────────────────────────────────┐
│ UPGRADE ORDER (bắt buộc tuần tự)                    │
│                                                     │
│ 1. etcd (nếu cần)                                  │
│    ↓                                                │
│ 2. kube-apiserver                                   │
│    ↓                                                │
│ 3. kube-controller-manager + kube-scheduler         │
│    ↓                                                │
│ 4. Kubelet trên từng node (rolling, 1 node tại 1   │
│    thời điểm)                                       │
│    ↓                                                │
│ 5. kube-proxy (thường upgrade cùng kubelet)         │
│    ↓                                                │
│ 6. kubectl (trên máy admin)                         │
└─────────────────────────────────────────────────────┘
```

---

## 4. Deep Dive

### 4.1 Node Maintenance — Cordon & Drain

**Cordon**: đánh dấu node là `Unschedulable` — pods hiện tại vẫn chạy, nhưng không có pod mới được schedule lên.

**Drain**: cordon + evict tất cả pods (trừ DaemonSet) khỏi node.

```
                   ┌────────────────────────────────┐
                   │         Node Lifecycle          │
                   │                                 │
Normal ──→ cordon ──→ drain ──→ maintenance ──→ uncordon
  │           │          │          │              │
  │     Unschedulable  Evict     Upgrade/      Schedulable
  │     (no new pods)  all pods  Repair/       (new pods OK)
  │                              Replace
  └──────────────────────────────────────────────┘
```

```bash
# Cordon — mark unschedulable
kubectl cordon <node-name>

# Drain — evict pods
kubectl drain <node-name> \
  --ignore-daemonsets \        # DaemonSet pods không evict được
  --delete-emptydir-data \     # Xóa emptyDir data
  --timeout=300s \             # Timeout sau 5 phút
  --grace-period=30            # Grace period cho pod termination

# Uncordon — mark schedulable lại
kubectl uncordon <node-name>
```

### 4.2 PodDisruptionBudget (PDB)

PDB kiểm soát **số lượng pods tối thiểu** phải available hoặc **số lượng pods tối đa** có thể unavailable cùng lúc khi drain/eviction.

```yaml
# PDB kiểu 1: minAvailable
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2          # Luôn phải có ≥ 2 pods running
  selector:
    matchLabels:
      app: api-service

# PDB kiểu 2: maxUnavailable
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: worker-pdb
spec:
  maxUnavailable: 1         # Tối đa 1 pod unavailable cùng lúc
  selector:
    matchLabels:
      app: worker

# PDB kiểu 3: percentage
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-pdb
spec:
  maxUnavailable: "25%"     # Tối đa 25% pods unavailable
  selector:
    matchLabels:
      app: web-frontend
```

**PDB behavior khi drain:**

```
Deployment: replicas=3, PDB: minAvailable=2

Drain Node A (có 1 pod):
  → Evict pod trên Node A ✅ (vẫn còn 2 pods trên Node B, C)

Drain Node B (có 1 pod):
  → Chờ pod mới schedule trên Node C/D trước
  → Rồi evict pod trên Node B ✅

Drain Node C (có 2 pods):
  → Evict 1 pod, chờ schedule xong
  → Evict pod còn lại ✅
  → NHƯNG nếu không có node khác → drain STUCK!
```

### 4.3 etcd Backup & Restore

etcd lưu **toàn bộ cluster state**: pods, deployments, services, secrets, configmaps, RBAC... Mất etcd = mất cluster.

```bash
# Backup etcd snapshot
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-snapshot.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Verify backup
ETCDCTL_API=3 etcdctl snapshot status /backup/etcd-snapshot.db --write-table

# Restore (nguy hiểm — chỉ khi disaster recovery)
ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-snapshot.db \
  --data-dir=/var/lib/etcd-restored
```

### 4.4 Velero — Kubernetes Backup & Restore

Velero backup Kubernetes resources (YAML definitions) + persistent volumes.

```
┌──────────────────────────────────────────────┐
│                   Velero                       │
│                                               │
│  Velero Server ◄──► Object Storage (S3/GCS)   │
│       │                                       │
│       ├── Backup: K8s resources → JSON → S3   │
│       ├── Backup: PV snapshots → Cloud snap   │
│       ├── Restore: S3 → K8s resources         │
│       ├── Schedule: CronJob-like auto backup  │
│       └── Migration: Cluster A → Cluster B    │
└──────────────────────────────────────────────┘
```

```bash
# Install Velero CLI
brew install velero  # macOS
# hoặc download binary từ GitHub releases

# Install Velero server (ví dụ với MinIO local)
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket velero-backups \
  --secret-file ./credentials-velero \
  --backup-location-config \
    region=minio,s3ForcePathStyle=true,s3Url=http://minio:9000

# Backup namespace
velero backup create my-backup \
  --include-namespaces production \
  --ttl 720h              # Giữ backup 30 ngày

# List backups
velero backup get

# Restore
velero restore create my-restore \
  --from-backup my-backup

# Schedule automatic backup
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --include-namespaces production \
  --ttl 720h
```

### 4.5 etcd Backup vs Velero vs Cloud Snapshots

```
etcd backup:
  [etcd snapshot] ──→ [file .db] ──→ [S3/NFS/local]
  - Backup: toàn bộ cluster state
  - Restore: phải dừng etcd, restore data dir
  - Scope: toàn cluster

Velero:
  [K8s API] ──→ [JSON resources] ──→ [Object Storage]
  [PV] ──→ [Cloud Volume Snapshot]
  - Backup: chọn namespace/label/resource type
  - Restore: apply resources lại vào cluster (có thể cluster khác)
  - Scope: flexible (namespace, label, resource type)

Cloud Snapshots (EBS/PD):
  [Disk] ──→ [Cloud Snapshot]
  - Backup: raw disk data
  - Restore: tạo disk mới từ snapshot, attach vào node
  - Scope: per volume
```

---

## 5. Trade-offs & Best Practices ⭐

### In-place Upgrade vs Blue-Green Cluster

| Tiêu chí | In-place Upgrade | Blue-Green Cluster |
|----------|-----------------|-------------------|
| **Cách làm** | Upgrade từng component trên cluster hiện tại | Tạo cluster mới, migrate workloads, xóa cluster cũ |
| **Downtime risk** | Thấp-Trung (nếu có PDB) | Rất thấp (traffic switch) |
| **Rollback** | Khó (phải downgrade components) | Dễ (switch traffic về cluster cũ) |
| **Cost** | Không tăng (dùng cùng infra) | 2x cost trong thời gian migration |
| **Complexity** | Trung bình | Cao (DNS switch, state migration) |
| **Data migration** | Không cần (data tại chỗ) | Cần migrate PV, databases |
| **Best for** | Hầu hết cases, clusters nhỏ-trung | Mission-critical, enterprise |

### PDB Strategy

| Strategy | minAvailable | Ưu điểm | Nhược điểm |
|----------|-------------|---------|-----------|
| Conservative | 80% | High availability | Drain chậm, có thể stuck |
| Balanced | 50% | Cân bằng speed/safety | Acceptable cho hầu hết |
| Aggressive | 1 | Drain nhanh | Risk nếu pod scale nhỏ |
| No PDB | - | Drain nhanh nhất | Risk downtime |

### Backup Strategy

| Strategy | RPO | RTO | Cost | Best for |
|----------|-----|-----|------|----------|
| etcd snapshot hourly | 1h | 30min-1h | Thấp | Disaster recovery |
| Velero daily | 24h | 15-30min | Trung bình | Namespace-level restore |
| Velero + Volume snapshots | 1-24h | 30min-1h | Trung-Cao | Stateful workloads |
| Cloud managed backup | Tùy config | 15min | Cao | Enterprise, managed K8s |

### Anti-patterns

1. **Skip minor versions**: v1.27 → v1.30 trực tiếp → API breaking changes, undefined behavior. **Luôn upgrade 1 minor version tại 1 thời điểm**.
2. **Upgrade không test trước**: Upgrade production trực tiếp → incident. **Luôn upgrade staging trước**.
3. **PDB minAvailable = replicas**: PDB = 3, replicas = 3 → drain KHÔNG BAO GIỜ complete. **minAvailable < replicas**.
4. **Không backup trước upgrade**: Upgrade fail → rollback fail → mất cluster. **Luôn backup etcd TRƯỚC upgrade**.
5. **Drain timeout quá ngắn**: Container cần 30s graceful shutdown nhưng drain timeout 10s → data loss. **Drain timeout ≥ terminationGracePeriodSeconds**.

---

## 6. Performance & Scalability ⭐

### Upgrade Impact trên Running Workloads

| Giai đoạn | Impact | Duration |
|-----------|--------|----------|
| Control plane upgrade | Rất thấp (API server restart ~30s) | 2-5 phút |
| Node drain | Pod eviction, reschedule delay | 5-30 phút/node |
| Pod reschedule | Pulling image, startup time | 30s-5min/pod |
| Total upgrade (3 nodes) | Rolling impact | 30-90 phút |

### Drain Time Estimation

```
Drain time per node ≈ 
  Σ(pod termination grace period) +    # thường 30s/pod
  PDB wait time +                       # phụ thuộc reschedule speed
  Volume detach time +                  # 30s-5min cho cloud volumes
  Buffer                                # 2-5 phút
```

### Large Cluster Upgrade Strategy

| Cluster Size | Strategy |
|-------------|----------|
| < 10 nodes | Drain 1 node tại 1 thời điểm |
| 10-50 nodes | Drain 2-3 nodes song song (nếu PDB cho phép) |
| 50-200 nodes | Chia thành node groups, upgrade theo group |
| > 200 nodes | Blue-green cluster hoặc canary upgrade |

---

## 7. Security & Reliability Considerations

### Security — CVE Patching

- Kubernetes CVEs được fix trong patch releases (e.g., 1.29.1 → 1.29.2).
- **Critical CVE**: upgrade trong 24-48h.
- **High CVE**: upgrade trong 1-2 tuần.
- Đăng ký [kubernetes-announce](https://groups.google.com/forum/#!forum/kubernetes-announce) để nhận thông báo.

### Backup Verification

- **Backup mà không test restore = không có backup.**
- Schedule restore test hàng tháng/quý.
- Test restore lên cluster riêng (không restore vào production).

### Rollback Considerations

- Control plane downgrade **không được hỗ trợ chính thức**.
- Nếu upgrade fail: restore etcd snapshot + reinstall old version.
- Node downgrade: drain node → reinstall old kubelet → uncordon.

---

## 8. Hands-on Example

### 8.1 Setup Cluster

```bash
# Tạo kind cluster 3 nodes
kind create cluster --name upgrade-lab --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF

kubectl get nodes
```

### 8.2 Deploy Test Application với PDB

```yaml
# test-app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 4
  selector:
    matchLabels:
      app: web-app
  template:
    metadata:
      labels:
        app: web-app
    spec:
      terminationGracePeriodSeconds: 10
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
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-app-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: web-app
---
apiVersion: v1
kind: Service
metadata:
  name: web-app-svc
spec:
  selector:
    app: web-app
  ports:
    - port: 80
      targetPort: 80
```

```bash
kubectl apply -f test-app.yaml

# Verify pods distributed across nodes
kubectl get pods -o wide
# Nên thấy pods trên cả 2 worker nodes

# Verify PDB
kubectl get pdb
```

Expected output:
```
NAME          MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
web-app-pdb   2               N/A               2                     10s
```

### 8.3 Test Cordon & Drain với PDB

```bash
# Xem pods trên mỗi node
kubectl get pods -o wide --sort-by=.spec.nodeName

# Step 1: Cordon worker-1
kubectl cordon upgrade-lab-worker

# Verify: node đánh dấu SchedulingDisabled
kubectl get nodes
# upgrade-lab-worker   Ready,SchedulingDisabled

# Pods hiện tại vẫn chạy (cordon không evict)
kubectl get pods -o wide

# Step 2: Drain worker-1
kubectl drain upgrade-lab-worker \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --timeout=120s

# Observe: PDB sẽ kiểm soát tốc độ eviction
# Pods sẽ được reschedule lên worker-2
kubectl get pods -o wide
# Tất cả pods nên ở trên upgrade-lab-worker2

# Step 3: Kiểm tra PDB respected
kubectl get pdb
# ALLOWED DISRUPTIONS phải luôn ≥ 0 trong quá trình drain
```

### 8.4 Test PDB Blocking Drain

```bash
# Tạo situation: drain node 2 khi node 1 đã drained
# Tất cả pods đang trên worker-2
# minAvailable=2, 4 pods trên 1 node
# Drain worker-2 → PDB cho evict tối đa 2 pods
# Nhưng không có node khác → 2 pods còn lại KHÔNG evict được

kubectl drain upgrade-lab-worker2 \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --timeout=30s

# Expected: timeout! Drain stuck vì PDB
# "Cannot evict pod as it would violate the pod's disruption budget"
# Ctrl+C để cancel

# Fix: uncordon worker 1 trước
kubectl uncordon upgrade-lab-worker

# Chờ pods reschedule
sleep 15
kubectl get pods -o wide

# Drain worker 2 lại
kubectl drain upgrade-lab-worker2 \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --timeout=120s
# Giờ sẽ thành công — pods move sang worker 1

# Cleanup
kubectl uncordon upgrade-lab-worker2
```

### 8.5 etcd Backup (trên kind)

```bash
# Exec vào control plane node
docker exec -it upgrade-lab-control-plane bash

# Bên trong control plane container:
ETCDCTL_API=3 etcdctl snapshot save /tmp/etcd-backup.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Verify backup
ETCDCTL_API=3 etcdctl snapshot status /tmp/etcd-backup.db --write-table

# Copy backup ra ngoài
exit
docker cp upgrade-lab-control-plane:/tmp/etcd-backup.db ./etcd-backup.db
ls -la etcd-backup.db
```

Expected output:
```
+----------+----------+------------+------------+
|   HASH   | REVISION | TOTAL KEYS | TOTAL SIZE |
+----------+----------+------------+------------+
| 8a1b2c3d |    12345 |        678 |     2.5 MB |
+----------+----------+------------+------------+
```

### 8.6 Cleanup

```bash
kubectl delete -f test-app.yaml
kind delete cluster --name upgrade-lab
rm -f etcd-backup.db
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: PDB Blocking Drain Forever

**Dấu hiệu**: `kubectl drain` stuck, log hiển thị `"Cannot evict pod as it would violate the pod's disruption budget"`.

**Nguyên nhân**: 
- minAvailable = replicas (drain KHÔNG BAO GIỜ complete)
- Pods không reschedule được (thiếu node, taint, resource)

**Debug**:
```bash
# Check PDB status
kubectl get pdb -o wide
# ALLOWED DISRUPTIONS phải > 0

# Check nếu pods đang Pending (không schedule được)
kubectl get pods | grep Pending

# Nếu Pending → check tại sao
kubectl describe pod <pending-pod>
```

**Fix**: Thêm node, uncordon node khác, hoặc tạm thời edit PDB (giảm minAvailable).

### Pitfall 2: Version Skew After Partial Upgrade

**Dấu hiệu**: Sau upgrade API server nhưng chưa upgrade kubelet, một số pod behaviors bất thường.

**Debug**:
```bash
# Check versions
kubectl get nodes -o custom-columns=NODE:.metadata.name,VERSION:.status.nodeInfo.kubeletVersion
kubectl version --short
```

**Fix**: Hoàn thành upgrade kubelet trên tất cả nodes.

### Production Case Study: Upgrade Causes Certificate Expiry

**Context**: Company chạy self-managed K8s cluster (kubeadm), 20 nodes. Upgrade từ v1.28 → v1.29.

**Symptom**: Sau upgrade control plane, kubelet trên 5 nodes báo `certificate has expired`. Pods trên 5 nodes đó bị evict.

**Investigation**:
```bash
kubectl get nodes
# 5 nodes NotReady

kubectl describe node worker-5
# "certificate has expired or is not yet valid"

# Check cert expiry
kubeadm certs check-expiration
```

**Root Cause**: `kubeadm upgrade` renew certificates cho control plane nhưng KHÔNG tự renew kubelet certificates. 5 nodes join cluster > 1 năm → kubelet cert expired vào đúng ngày upgrade.

**Mitigation**: Manual renew certs trên 5 nodes → `systemctl restart kubelet`.

**Long-term Fix**: 
1. Enable kubelet certificate rotation: `serverTLSBootstrap: true`.
2. Thêm cert expiry monitoring (alert 30 ngày trước khi expire).
3. Upgrade runbook thêm step: "Check certificate expiry before upgrade."

---

## 10. Kết nối với bài trước & bài sau

### Từ Day 22 (Troubleshooting)

Troubleshooting skills cần thiết cho upgrade process:
- Pods Pending sau drain → debug scheduling (Day 22 Pending pod).
- CrashLoopBackOff sau upgrade → version incompatibility.
- DNS issues sau upgrade → CoreDNS version mismatch.

### Sang Day 24 (Production-ready Checklist)

Day 24 sẽ tổng hợp tất cả knowledge Phase 3 thành production checklist, bao gồm:
- Backup checklist (etcd + Velero — Day 23).
- Upgrade checklist (version policy, PDB — Day 23).
- Maintenance window checklist.

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Version Skew Policy](https://kubernetes.io/releases/version-skew-policy/)
- [Safely Drain a Node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
- [PodDisruptionBudget](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)

### Nice-to-have

- [kubeadm upgrade](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/)
- [Velero Documentation](https://velero.io/docs/)
- [etcd Backup & Restore](https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/#backing-up-an-etcd-cluster)

### Deep-dive

- [Kubernetes Release Cadence](https://kubernetes.io/releases/)
- [EKS Upgrade Best Practices](https://aws.github.io/aws-eks-best-practices/upgrades/)
- [GKE Upgrade Strategies](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-upgrades)

