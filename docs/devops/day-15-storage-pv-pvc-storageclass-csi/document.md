# Day 15: Storage — Cheat Sheet & Decision Framework

## Storage Decision Matrix

### Khi nào dùng storage type nào?

| Workload | Storage Type | Access Mode | Reclaim Policy | StorageClass Tier |
|----------|-------------|-------------|----------------|-------------------|
| **PostgreSQL/MySQL** | Block (EBS, PD) | RWO/RWOP | Retain | High IOPS (io2, pd-ssd) |
| **Redis persistent** | Block (EBS, PD) | RWO | Retain | General (gp3) |
| **Elasticsearch** | Block (EBS, PD) | RWO | Retain/Delete | Throughput (st1) |
| **File uploads** | File (EFS, NFS) | RWX | Retain | Standard |
| **Shared config** | ConfigMap/Secret | N/A | N/A | N/A (tmpfs) |
| **Temp cache** | emptyDir | N/A | N/A | N/A (node disk/RAM) |
| **Build artifacts** | emptyDir | N/A | N/A | N/A |
| **Media/backups** | Object (S3, GCS) | API-based | N/A | N/A |

### Stateful on K8s vs Managed Service

```
Nên chạy DB trên Kubernetes?
│
├─ Team có K8s + DB expertise?
│  ├─ NO → Managed Service (RDS, Cloud SQL)
│  └─ YES
│     ├─ Compliance yêu cầu self-hosted?
│     │  ├─ YES → K8s + Operator (CloudNativePG, Vitess)
│     │  └─ NO
│     │     ├─ Budget tight?
│     │     │  ├─ YES → K8s (tiết kiệm managed fee)
│     │     │  └─ NO → Managed Service (ít ops burden)
│     │     └─ Scale > 10TB?
│     │        ├─ YES → Managed Service (proven at scale)
│     │        └─ NO → Either works, prefer Managed
│     └─ Dev/Staging? → K8s (cost savings)
│        Production? → Managed Service (hầu hết cases)
```

## PV, PVC, StorageClass Quick Reference

### PersistentVolumeClaim (PVC)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  storageClassName: fast-ssd       # StorageClass name
  accessModes:
    - ReadWriteOnce                # RWO, ROX, RWX, RWOP
  resources:
    requests:
      storage: 10Gi                # Requested size
  # volumeName: specific-pv       # Optional: bind to specific PV
  # selector:                     # Optional: label selector for PV
  #   matchLabels:
  #     type: fast
```

### PersistentVolume (PV) — Static Provisioning

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: my-pv
  labels:
    type: fast
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain    # Retain, Delete
  storageClassName: fast-ssd
  # Storage backend specific:
  hostPath:
    path: /mnt/data                        # Local (dev only)
  # awsElasticBlockStore:                  # AWS EBS
  #   volumeID: vol-xxx
  #   fsType: ext4
  # nfs:                                   # NFS
  #   server: nfs.example.com
  #   path: /exports/data
```

### StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"  # Default class
provisioner: ebs.csi.aws.com              # CSI driver
parameters:                                # Provider-specific
  type: io2
  iopsPerGB: "50"
  encrypted: "true"
reclaimPolicy: Retain                      # Retain or Delete
volumeBindingMode: WaitForFirstConsumer    # or Immediate
allowVolumeExpansion: true                 # Allow PVC resize
mountOptions:
  - debug
```

### Pod Volume Mount

```yaml
spec:
  containers:
    - name: app
      volumeMounts:
        - name: data
          mountPath: /var/lib/data
          subPath: app-data          # Optional: subdirectory
          readOnly: false
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: my-pvc
```

## Access Modes Reference

| Mode | Short | Nodes | Pods | Use Case |
|------|-------|-------|------|----------|
| `ReadWriteOnce` | RWO | 1 node | Multiple (same node) | Database, single-writer |
| `ReadOnlyMany` | ROX | Multiple | Multiple | Shared read config |
| `ReadWriteMany` | RWX | Multiple | Multiple | Shared file storage |
| `ReadWriteOncePod` | RWOP | 1 node | 1 pod only | Strict single-writer |

## Reclaim Policy Comparison

| Policy | PVC Deleted → | Data | Use for |
|--------|--------------|------|---------|
| **Retain** | PV → Released, data intact | ✅ Safe | Production |
| **Delete** | PV deleted, disk deleted | ❌ Lost | Dev/test, temp |
| **Recycle** | ❌ Deprecated | N/A | Don't use |

## Volume Binding Modes

| Mode | When PV Created | Use for |
|------|----------------|---------|
| `Immediate` | When PVC created | Single-AZ, local |
| `WaitForFirstConsumer` | When pod scheduled | Multi-AZ (match AZ) |

## StatefulSet + VolumeClaimTemplate

```yaml
apiVersion: apps/v1
kind: StatefulSet
spec:
  volumeClaimTemplates:
    - metadata:
        name: data                   # Volume name
      spec:
        storageClassName: fast-ssd
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
  template:
    spec:
      containers:
        - volumeMounts:
            - name: data             # Matches template name
              mountPath: /var/lib/data
```

**Kết quả**: Mỗi pod có PVC riêng: `data-<sts-name>-0`, `data-<sts-name>-1`, ...

**Quan trọng**: mặc định PVC **KHÔNG bị xóa** khi delete StatefulSet hoặc scale down (`persistentVolumeClaimRetentionPolicy: Retain`). Chỉ dùng policy `Delete` khi workload thật sự disposable hoặc đã có backup/restore được test.

## Cloud Storage Cost Model

Giá cloud storage thay đổi theo region và thời điểm, nên không hardcode số tiền trong runbook. Khi thiết kế `StorageClass`, hãy tính bằng model:

| Cost driver | Ví dụ | Câu hỏi cần trả lời |
|-------------|-------|---------------------|
| Capacity | GB-month/TB-month | Data thực tế, growth rate, retention bao lâu? |
| Provisioned performance | IOPS, throughput | Database cần steady IOPS hay burst ngắn? |
| Snapshot/backup | Snapshot size, incremental delta | RPO/RTO yêu cầu backup mỗi bao lâu? |
| Data transfer | Cross-AZ, cross-region | Pod và volume có cùng zone không? Có replication không? |
| Request/operation | File/object storage requests | Workload có nhiều small files hoặc metadata ops không? |
| Orphaned volumes | PV `Retain`, PVC bị quên | Ai review và cleanup disk không còn owner? |

### Cost Review Checklist

- [ ] Kiểm tra pricing page hiện tại của cloud/region trước khi chốt estimate.
- [ ] Tách storage class cho `dev`, `staging`, `prod` để tránh dùng premium disk ở môi trường không cần.
- [ ] Alert volume utilization và orphaned PV/PVC.
- [ ] Đặt lifecycle/retention cho snapshots.
- [ ] Với database production, so sánh chi phí tự vận hành trên Kubernetes với managed database gồm backup, HA, patching và on-call cost.

## Debugging Commands

```bash
# PVC status
kubectl get pvc                              # List all
kubectl describe pvc <name>                  # Details + Events

# PV status
kubectl get pv                               # List all
kubectl get pv -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,RECLAIM:.spec.persistentVolumeReclaimPolicy,CLASS:.spec.storageClassName

# StorageClass
kubectl get storageclass                     # List all
kubectl describe storageclass <name>         # Details

# Disk usage inside pod
kubectl exec <pod> -- df -h /var/lib/data    # Check mount
kubectl exec <pod> -- du -sh /var/lib/data   # Data size

# Debug PVC Pending
kubectl describe pvc <name>                  # Check Events
kubectl get events --sort-by='.lastTimestamp' # Recent events

# Debug mount issues
kubectl describe pod <name>                  # Check Events, Volume Mounts
kubectl get pod <name> -o yaml | grep -A 20 volumeMounts
```

### PVC Pending Troubleshooting

```
PVC Pending?
│
├─ "no persistent volumes available"
│  └─ StorageClass provisioner working? Check CSI driver pods
│
├─ "storageclass not found"
│  └─ kubectl get storageclass — name typo?
│
├─ "waiting for first consumer to be created"
│  └─ WaitForFirstConsumer mode — create a pod that uses this PVC
│
├─ "exceeded quota"
│  └─ kubectl describe resourcequota — increase quota
│
└─ No events?
   └─ Check CSI driver logs in kube-system namespace
```

## Backup Strategy Checklist

### Database Backup
- [ ] Logical backup (pg_dump/mysqldump) daily
- [ ] WAL archiving for point-in-time recovery
- [ ] Volume snapshots (CSI VolumeSnapshot) for quick restore
- [ ] Cross-region backup copy
- [ ] Backup retention policy (30 days minimum)
- [ ] Restore test monthly
- [ ] Backup monitoring and alerting

### File Storage Backup
- [ ] Cross-region replication (S3 CRR, EFS replication)
- [ ] Versioning enabled
- [ ] Lifecycle policy for old versions
- [ ] Restore procedure documented

### Recovery Priorities
| Data Type | RPO | RTO | Strategy |
|-----------|-----|-----|----------|
| Transaction DB | < 1 min | < 15 min | WAL + streaming replication |
| Cache (Redis) | < 1 hour | < 5 min | AOF + RDB snapshots |
| File uploads | < 1 hour | < 30 min | S3 versioning |
| Logs | < 24 hours | < 1 hour | Re-ingest if needed |

