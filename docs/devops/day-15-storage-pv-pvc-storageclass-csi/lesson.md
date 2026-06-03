# Day 15: Storage — PV, PVC, StorageClass, CSI

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt được** stateless vs stateful workload và hiểu vì sao stateful trên Kubernetes phức tạp hơn nhiều.
2. **Giải thích được** mối quan hệ giữa PersistentVolume (PV), PersistentVolumeClaim (PVC), StorageClass và cách dynamic provisioning hoạt động.
3. **Cấu hình được** storage cho database workload trên Kubernetes với đúng access modes và reclaim policy.
4. **Phân tích được** rủi ro data loss khi xóa PVC/PV và thiết kế backup strategy phù hợp.
5. **Debug được** các lỗi thường gặp: PVC stuck Pending, PV not releasing, pod không mount được volume.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng?

Ở Day 14, bạn đã hiểu ConfigMap/Secret mount dưới dạng volume — nhưng đó là **tmpfs (in-memory)**, dữ liệu mất khi pod restart. Trong production, bạn cần **persistent storage** cho:

- **Database**: PostgreSQL, MySQL, MongoDB — data phải sống qua pod restart, node failure.
- **File storage**: upload files, media assets.
- **Logs/cache**: local persistent cache, WAL files.
- **Queue**: Kafka logs, RabbitMQ persistent messages.

### Nếu làm sai thì sao?

- **Không dùng PVC** → pod restart = mất toàn bộ data. Database trống.
- **Reclaim policy Delete** → xóa PVC = xóa luôn data trên cloud. Không recovery được.
- **Access mode sai** → multiple pods write cùng volume = data corruption.
- **Không backup** → disk fail = data mất vĩnh viễn.
- **StorageClass sai performance tier** → database chậm, IOPS không đủ.

### Liên hệ với developer background

- **PV** giống physical disk hoặc cloud volume (EBS, Persistent Disk) — resource thực tế.
- **PVC** giống request "tôi cần 10GB disk" — pod claim storage mà không cần biết chi tiết.
- **StorageClass** giống tier trong cloud: gp3 (general), io2 (high IOPS), st1 (throughput).
- **CSI** giống storage driver — interface chuẩn để Kubernetes nói chuyện với storage backend.

---

## 3. Kiến thức nền tảng

### Stateless vs Stateful

```
Stateless Workload:              Stateful Workload:
┌─────────┐                      ┌─────────┐
│   Pod   │  kill & recreate     │   Pod   │──── PVC ──── PV ──── Disk
│  (v1)   │  = no data loss      │  (DB)   │     data persists!
└─────────┘                      └─────────┘

Ví dụ:                           Ví dụ:
- API server                     - PostgreSQL
- Web frontend                   - Redis (persistent)
- Microservice                   - Kafka broker
- Worker (stateless)             - Elasticsearch
```

### Ephemeral vs Persistent Storage

| Type | Lifetime | Dùng cho | K8s Resource |
|------|----------|----------|-------------|
| **emptyDir** | Pod lifetime | Temp files, cache, shared between containers | Volume |
| **hostPath** | Node lifetime | Dev/test, node-level data | Volume |
| **ConfigMap/Secret** | Object lifetime | Config, credentials (tmpfs) | Volume |
| **PersistentVolume** | Independent of pod | Database, file storage | PV + PVC |

### Storage Types

| Type | Ví dụ | Access Pattern | Use Case |
|------|-------|---------------|----------|
| **Block** | AWS EBS, GCE PD, iSCSI | Single node read/write | Database |
| **File** | NFS, EFS, Azure Files | Multi-node read/write | Shared files |
| **Object** | S3, GCS, MinIO | API-based (không mount) | Media, backups |

---

## 4. Deep Dive

### 4.1 PV, PVC, StorageClass Relationship

```
┌──────────────────────────────────────────────────────────┐
│                    Storage Architecture                    │
│                                                            │
│  Developer tạo:          Admin tạo:         Infrastructure: │
│                                                            │
│  ┌──────────┐     bind   ┌──────────┐      ┌───────────┐ │
│  │   PVC    │────────────│    PV    │──────│   Disk    │ │
│  │          │            │          │      │ (EBS,NFS) │ │
│  │ "10Gi,  │            │ "10Gi,  │      │           │ │
│  │  RWO"   │            │  RWO,   │      └───────────┘ │
│  └──────────┘            │  gp3"   │                     │
│       │                  └──────────┘                     │
│       │                       ▲                           │
│       │                       │                           │
│  Pod mounts              StorageClass                     │
│  PVC as volume           auto-creates PV                  │
│                          (dynamic provisioning)           │
└──────────────────────────────────────────────────────────┘
```

### Static vs Dynamic Provisioning

**Static Provisioning** — admin tạo PV trước:

```yaml
# Admin tạo PV
apiVersion: v1
kind: PersistentVolume
metadata:
  name: manual-pv
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  hostPath:
    path: /mnt/data
---
# Developer tạo PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: manual-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  # Kubernetes tìm PV phù hợp và bind
```

**Dynamic Provisioning** — StorageClass tự tạo PV:

```yaml
# Admin tạo StorageClass (1 lần)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-storage
provisioner: kubernetes.io/aws-ebs   # CSI driver
parameters:
  type: gp3
  iopsPerGB: "10"
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
---
# Developer tạo PVC (PV tự động tạo)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: db-data
spec:
  storageClassName: fast-storage
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

### 4.2 Access Modes

| Mode | Viết tắt | Mô tả | Dùng cho |
|------|----------|--------|----------|
| `ReadWriteOnce` | RWO | 1 node read/write | Database, single-writer |
| `ReadOnlyMany` | ROX | Nhiều nodes read-only | Shared config, static assets |
| `ReadWriteMany` | RWX | Nhiều nodes read/write | Shared file storage |
| `ReadWriteOncePod` | RWOP | 1 pod duy nhất (K8s 1.22+) | Strict single-writer |

> ⚠️ **RWO = 1 node**, không phải 1 pod. Nhiều pods trên cùng node vẫn mount được RWO volume.

### 4.3 Reclaim Policy

Khi PVC bị xóa, PV xử lý disk data theo reclaim policy:

| Policy | Behavior | Dùng cho | Risk |
|--------|----------|----------|------|
| `Retain` | Giữ PV và data, admin manual cleanup | Production data | ❌ Disk leak nếu quên cleanup |
| `Delete` | Xóa PV và disk (trên cloud) | Dev/test, temp data | ⚠️ Data loss vĩnh viễn |
| `Recycle` | ❌ Deprecated | Không dùng | N/A |

```
PVC deleted
    │
    ├─ Retain: PV status → "Released"
    │          Data intact, admin decides
    │
    └─ Delete: PV deleted, disk deleted
               DATA GONE FOREVER ⚠️
```

### 4.4 CSI — Container Storage Interface

CSI là interface chuẩn giữa Kubernetes và storage providers.

```
┌─────────┐    ┌───────────┐    ┌─────────────────┐
│   Pod   │    │  Kubelet  │    │   CSI Driver    │
│         │    │           │    │                 │
│  mount  │───►│  CSI call │───►│  Create disk    │
│  volume │    │           │    │  Attach to node │
│         │    │           │    │  Mount to pod   │
└─────────┘    └───────────┘    └─────────────────┘
                                        │
                                        ▼
                                ┌─────────────────┐
                                │  Storage Backend│
                                │  AWS EBS        │
                                │  GCE PD         │
                                │  Ceph           │
                                │  NFS            │
                                └─────────────────┘
```

**CSI Drivers phổ biến:**

| Driver | Storage | Access Modes | Dynamic Provisioning |
|--------|---------|-------------|---------------------|
| `ebs.csi.aws.com` | AWS EBS | RWO | ✅ |
| `efs.csi.aws.com` | AWS EFS | RWX | ✅ |
| `pd.csi.storage.gke.io` | GCE PD | RWO | ✅ |
| `disk.csi.azure.com` | Azure Disk | RWO | ✅ |
| `file.csi.azure.com` | Azure Files | RWX | ✅ |
| `rancher.io/local-path` | Local (kind, k3s) | RWO | ✅ |

### 4.5 Volume Binding Modes

| Mode | Behavior | Dùng cho |
|------|----------|----------|
| `Immediate` | PV tạo ngay khi PVC tạo | Luôn sẵn storage |
| `WaitForFirstConsumer` | PV tạo khi pod được schedule | Multi-AZ (tạo disk cùng AZ với pod) |

> **Production recommendation**: Dùng `WaitForFirstConsumer` trên cloud — tránh tạo disk ở AZ khác với node.

---

## 5. Trade-offs & Best Practices ⭐

### Stateful trên K8s vs Managed Service

| Criteria | DB on Kubernetes | Managed DB (RDS, Cloud SQL) |
|----------|-----------------|---------------------------|
| **Control** | Full control | Limited |
| **Cost** | Lower (no managed fee) | Higher (managed premium) |
| **Operations** | Team phải quản lý backup, upgrade, HA | Provider quản lý |
| **Expertise** | Cần K8s + DB expertise | Chỉ cần DB expertise |
| **HA/Failover** | Phải tự setup (Operator) | Built-in |
| **Compliance** | Full control | Tuỳ provider |
| **Recommendation** | Dev/staging, team có expertise | Production (hầu hết cases) |

### Best Practices

1. **Production database: dùng managed service** trừ khi có lý do rõ ràng (compliance, cost, expertise).
2. **Reclaim policy `Retain` cho production** — không bao giờ auto-delete production data.
3. **`WaitForFirstConsumer`** trên cloud — tránh AZ mismatch.
4. **`allowVolumeExpansion: true`** — cho phép resize volume khi cần.
5. **Backup trước khi thay đổi** — snapshot PV trước upgrade, migration.
6. **RWOP cho database** — đảm bảo chỉ 1 pod write.
7. **Monitor disk usage** — alert khi usage > 80%.

### Anti-patterns

1. **Dùng `hostPath` trong production** → data bị lock vào 1 node, pod reschedule = mất data.
2. **Reclaim policy `Delete` cho production** → xóa PVC = xóa luôn data.
3. **Không backup** → disk fail = data mất.
4. **Shared RWX cho database** → data corruption.
5. **Over-provisioning storage** → lãng phí cost, nhưng under-provisioning nguy hiểm hơn.

---

## 6. Performance & Scalability ⭐

### Storage Performance Tiers

| Tier | AWS | IOPS | Throughput | Use Case |
|------|-----|------|-----------|----------|
| **General** | gp3 | 3,000 base | 125 MB/s | Hầu hết workloads |
| **High IOPS** | io2 | 64,000 max | 1,000 MB/s | OLTP database |
| **Throughput** | st1 | 500 base | 500 MB/s | Log processing, data warehouse |
| **Cold** | sc1 | 250 base | 250 MB/s | Archive, infrequent access |

### Performance Bottlenecks

| Bottleneck | Triệu chứng | Debug | Fix |
|------------|-------------|-------|-----|
| **IOPS limit** | High IO wait, slow queries | `iostat -x`, `kubectl top pod` | Upgrade storage class |
| **Throughput limit** | Slow large file reads/writes | `dd` benchmark | Larger volume = more throughput |
| **Network** (remote storage) | High latency on reads | `ping`, storage metrics | Local storage cho latency-sensitive |
| **Capacity** | Disk full, app crashes | `df -h` in pod | Expand PVC |

### Expand PVC (Online resize)

```bash
# Cần StorageClass có allowVolumeExpansion: true
kubectl patch pvc db-data -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'

# Verify
kubectl get pvc db-data
# CAPACITY sẽ tăng (có thể cần pod restart tuỳ CSI driver)
```

---

## 7. Security & Reliability Considerations

### Security

- **Encryption at rest**: cloud volumes thường encrypt by default, verify config.
- **Access control**: RBAC cho PVC creation (ai được tạo PVC bao nhiêu storage).
- **ResourceQuota**: giới hạn total storage per namespace.

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: storage-quota
spec:
  hard:
    requests.storage: 100Gi                # Tổng storage max
    persistentvolumeclaims: 10              # Số PVC max
    fast-storage.storageclass.storage.k8s.io/requests.storage: 50Gi  # Per class
```

### Reliability

- **Backup strategy**: snapshot PV định kỳ (CSI VolumeSnapshot).
- **PV protection**: Kubernetes có finalizer bảo vệ PV đang được dùng.
- **PVC protection**: PVC đang bound bởi pod không cho xóa.
- **Test restore**: backup vô nghĩa nếu không test restore.

### Backup với VolumeSnapshot

```yaml
# VolumeSnapshotClass (admin tạo)
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: csi-snapclass
driver: ebs.csi.aws.com
deletionPolicy: Retain

---
# VolumeSnapshot (developer tạo)
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: db-backup-20240101
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: db-data
```

---

## 8. Hands-on Example

### Chuẩn bị

```bash
# kind cluster (local-path provisioner built-in)
kind create cluster --name devops-lab 2>/dev/null || echo "Cluster exists"

# Verify StorageClass
kubectl get storageclass
# Expected: standard (default) - kind dùng rancher/local-path
```

### 8.1 Deploy PostgreSQL với PVC

```yaml
# file: postgres-storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  # storageClassName: standard  # default trên kind
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-config
data:
  POSTGRES_DB: "myapp"
  POSTGRES_USER: "admin"
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
type: Opaque
stringData:
  POSTGRES_PASSWORD: "secure-password-123"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  strategy:
    type: Recreate   # Database: chỉ 1 instance chạy cùng lúc
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          envFrom:
            - configMapRef:
                name: postgres-config
            - secretRef:
                name: postgres-secret
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
              subPath: pgdata
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "admin", "-d", "myapp"]
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            exec:
              command: ["pg_isready", "-U", "admin", "-d", "myapp"]
            initialDelaySeconds: 30
            periodSeconds: 10
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: postgres-data
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-svc
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

```bash
# Deploy
kubectl apply -f postgres-storage.yaml

# Wait for ready
kubectl wait --for=condition=Ready pod -l app=postgres --timeout=120s

# Verify PVC bound
kubectl get pvc postgres-data
# Expected: STATUS = Bound

# Verify PV created
kubectl get pv
```

### 8.2 Test Data Persistence

```bash
# Write data
kubectl exec -it $(kubectl get pod -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- psql -U admin -d myapp -c "
CREATE TABLE users (id SERIAL PRIMARY KEY, name VARCHAR(100), email VARCHAR(100));
INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com');
INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com');
SELECT * FROM users;
"
# Expected:
# id | name  | email
# ---+-------+-------------------
#  1 | Alice | alice@example.com
#  2 | Bob   | bob@example.com

# Delete pod (simulate crash)
kubectl delete pod -l app=postgres
echo "Pod deleted, waiting for recreation..."

# Wait for new pod
kubectl wait --for=condition=Ready pod -l app=postgres --timeout=120s

# Verify data persists
kubectl exec -it $(kubectl get pod -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- psql -U admin -d myapp -c "SELECT * FROM users;"
# Expected: Alice and Bob still there!
```

### 8.3 Mô phỏng xóa PVC/PV — Phân tích rủi ro an toàn

Không mô phỏng bằng PVC `postgres-data` đang chứa dữ liệu bài lab, vì `kubectl delete pvc` là thao tác không thể "cancel" theo nghĩa khôi phục deletion request. Dùng một PVC disposable để quan sát finalizer và blast radius.

```yaml
# file: pvc-delete-demo.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: delete-demo-data
  labels:
    app: delete-demo
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: delete-demo-pod
  labels:
    app: delete-demo
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "echo 'temporary data' > /data/test.txt && sleep 3600"]
      volumeMounts:
        - name: data
          mountPath: /data
      resources:
        requests:
          cpu: 25m
          memory: 16Mi
        limits:
          cpu: 50m
          memory: 32Mi
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: delete-demo-data
```

```bash
kubectl apply -f pvc-delete-demo.yaml
kubectl wait --for=condition=Ready pod/delete-demo-pod --timeout=60s
kubectl get pvc delete-demo-data
# Expected: STATUS = Bound

# Thử xóa PVC khi pod đang mount nó
kubectl delete pvc delete-demo-data --wait=false
sleep 2
kubectl get pvc delete-demo-data
# Expected: STATUS = Terminating (bị block bởi pvc-protection finalizer)

# Khi pod bị xóa, PVC deletion sẽ hoàn tất và data của PVC disposable biến mất
kubectl delete pod delete-demo-pod
kubectl wait --for=delete pvc/delete-demo-data --timeout=60s
# Expected: PVC deleted

# Verify PVC database chính vẫn an toàn
kubectl get pvc postgres-data
# Expected: STATUS = Bound
```

### 8.4 EmptyDir vs PVC

```yaml
# file: ephemeral-vs-persistent.yaml
apiVersion: v1
kind: Pod
metadata:
  name: ephemeral-pod
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "echo 'ephemeral data' > /data/test.txt && cat /data/test.txt && sleep 3600"]
      volumeMounts:
        - name: temp-data
          mountPath: /data
      resources:
        requests:
          cpu: 25m
          memory: 16Mi
        limits:
          cpu: 50m
          memory: 32Mi
  volumes:
    - name: temp-data
      emptyDir: {}    # Pod restart = data mất!
```

```bash
kubectl apply -f ephemeral-vs-persistent.yaml
kubectl wait --for=condition=Ready pod/ephemeral-pod --timeout=30s

# Write data
kubectl exec ephemeral-pod -- sh -c 'echo "important data" > /data/important.txt'
kubectl exec ephemeral-pod -- cat /data/important.txt
# Output: important data

# Delete pod
kubectl delete pod ephemeral-pod

# Recreate
kubectl apply -f ephemeral-vs-persistent.yaml
kubectl wait --for=condition=Ready pod/ephemeral-pod --timeout=30s

# Data is GONE
kubectl exec ephemeral-pod -- cat /data/important.txt 2>&1 || echo "FILE NOT FOUND - data lost!"
```

### Cleanup

```bash
kubectl delete -f ephemeral-vs-persistent.yaml 2>/dev/null
kubectl delete -f pvc-delete-demo.yaml 2>/dev/null
kubectl delete -f postgres-storage.yaml
kubectl delete pvc postgres-data 2>/dev/null
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: PVC stuck in Pending

**Triệu chứng**: PVC status `Pending`, pod stuck `ContainerCreating`.

```bash
kubectl describe pvc <name>
# Look for Events:
# - "no persistent volumes available"  → Không có PV match
# - "storageclass not found"           → StorageClass sai tên
# - "waiting for first consumer"       → WaitForFirstConsumer, cần pod scheduled
```

**Nguyên nhân phổ biến:**
- StorageClass không tồn tại.
- Capacity request lớn hơn available.
- Access mode không match.
- `WaitForFirstConsumer` + pod chưa được schedule.

### Pitfall 2: PV stuck in Released

**Triệu chứng**: PV status `Released` sau khi xóa PVC. PVC mới không bind được vào PV cũ.

```bash
kubectl get pv
# STATUS: Released

# Fix: Remove claimRef để PV chuyển về Available
kubectl patch pv <pv-name> -p '{"spec":{"claimRef":null}}'
```

### Pitfall 3: Data loss do Reclaim Policy Delete

**Triệu chứng**: Xóa PVC → PV bị xóa → cloud disk bị xóa → data mất vĩnh viễn.

**Prevention**:
```bash
# Check reclaim policy
kubectl get pv -o custom-columns=NAME:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy

# Patch to Retain nếu cần
kubectl patch pv <pv-name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

### Pitfall 4: subPath và data loss

**Triệu chứng**: Dùng `subPath` mount PostgreSQL data directory, nhưng quên set `subPath` → PostgreSQL init ghi vào root mount → conflict với existing files.

**Fix**: Luôn dùng `subPath: pgdata` cho PostgreSQL trên Kubernetes.

### Case Study: Production database data loss do PVC deletion

**Bối cảnh**: Team dùng Helm chart cho PostgreSQL. StorageClass có `reclaimPolicy: Delete`. Developer chạy `helm uninstall` để cleanup staging → Helm xóa PVC → PV bị xóa → EBS volume bị xóa.

**Root cause**: Helm uninstall xóa tất cả resources bao gồm PVC. StorageClass `Delete` policy = cloud disk bị xóa.

**Fix**:
1. Đổi StorageClass `reclaimPolicy: Retain` cho production/staging.
2. Thêm `helm.sh/resource-policy: keep` annotation cho PVC trong Helm chart.
3. Setup daily EBS snapshots.
4. Test restore process.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 14: ConfigMap, Secret)
- ConfigMap/Secret mount dưới dạng volume (tmpfs) → bài này là persistent storage.
- Kết hợp: database pod dùng PVC cho data + Secret cho password.

### Bài sau (Day 16: Helm vs Kustomize)
- PVC template trong Helm chart → parameterize storage size, class per environment.
- Kustomize overlay → override storage config cho dev/staging/prod.
- StatefulSet + PVC (Day 11) + Storage (Day 15) = nền tảng cho Helm chart database.

---

## 11. Tài liệu tham khảo

### Must-read
- [Persistent Volumes — Official Docs](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes — Official Docs](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Volume Snapshots — Official Docs](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)

### Nice-to-have
- [CSI Drivers List](https://kubernetes-csi.github.io/docs/drivers.html)
- [Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/)
- [Local Persistent Volumes](https://kubernetes.io/blog/2019/04/04/kubernetes-1.14-local-persistent-volumes-ga/)

### Deep-dive
- "Kubernetes in Action" — Chapter 6: Volumes
- [Running Production Databases on Kubernetes](https://thenewstack.io/kubernetes-for-databases/) — The New Stack
- [Data on Kubernetes — DoK Community](https://dok.community/)

