# Day 42: Backup, Restore và Disaster Recovery

## Mục tiêu bài học

- Phân biệt backup cluster state, backup application data và disaster recovery plan.
- Hiểu Velero backup/restore resource Kubernetes và volume snapshot hoạt động ở mức nào.
- Biết backup/restore `etcd` trong K3s/self-managed Kubernetes và giới hạn của cách này.
- Thiết kế restore drill cho PostgreSQL/Redis/Kafka và workloads stateless.
- Xây dựng checklist RPO/RTO, scope, encryption, retention, test restore và ownership.

## Vấn đề cần giải quyết

Backup không có giá trị nếu chưa từng restore. Trong Kubernetes, nhiều team nghĩ đã backup YAML trong Git là đủ. Điều đó chỉ đúng với stateless manifests, không đủ cho:

- PVC chứa dữ liệu.
- Secret/config runtime không nằm trong Git.
- CRD state của operator.
- `etcd` cluster state.
- Object storage, database external, Kafka topics.
- Cloud resources tạo bởi controller.

Disaster recovery cần trả lời:

- Mất một Pod thì ai tự phục hồi?
- Mất một node thì dữ liệu có còn không?
- Mất namespace thì restore ra sao?
- Mất cluster thì dựng lại trong bao lâu?
- Mất region thì hệ thống có phương án nào?

## Mental Model

```text
Desired state in Git
  + Kubernetes manifests
  + Helm values

Cluster state
  + API objects in etcd
  + Secrets
  + CRDs/custom resources

Application data
  + PVC/block/file volumes
  + database logical data
  + Kafka topics/logs
  + object storage

DR plan
  + backups
  + restore procedure
  + RPO/RTO
  + test drills
```

Git giúp rebuild desired manifests. Velero giúp backup Kubernetes objects và volume snapshots. Database-native backup giúp đảm bảo tính nhất quán dữ liệu app. DR tốt thường phối hợp cả ba.

## Lý thuyết cốt lõi

### RPO và RTO

| Thuật ngữ | Câu hỏi | Ví dụ |
|---|---|---|
| `RPO` | Mất tối đa bao nhiêu dữ liệu được chấp nhận? | 5 phút, 1 giờ, 24 giờ |
| `RTO` | Khôi phục dịch vụ trong bao lâu? | 15 phút, 2 giờ, 1 ngày |

RPO/RTO quyết định kiến trúc backup. Không thể yêu cầu RPO 5 phút nhưng chỉ chạy backup nightly.

### Backup scope

| Scope | Backup cái gì | Tool thường dùng |
|---|---|---|
| Git desired state | Manifest, Helm values, policy | Git remote, branch protection |
| Kubernetes API state | Namespace, Deployment, Secret, CRD, PVC object | Velero, etcd snapshot |
| Volume data | PVC content | CSI snapshot, Velero plugin, storage backup |
| Database data | Logical/physical database backup | pg_dump, WAL archive, operator backup |
| Message/log data | Kafka topics, offsets, retention | MirrorMaker, broker backup, app replay strategy |
| Cloud dependencies | LB, DNS, IAM, object storage | IaC, cloud backup |

Không nên coi một tool là đáp án cho mọi lớp.

### Velero

Velero backup Kubernetes resources vào object storage và có thể phối hợp volume snapshot qua provider plugin/CSI.

Luồng đơn giản:

```text
velero backup create
  |
  +-- collect Kubernetes objects
  +-- include/exclude namespaces/resources
  +-- trigger volume snapshot nếu cấu hình
  |
  v
object storage backup location
```

Restore:

```text
velero restore create
  |
  +-- read backup metadata
  +-- recreate Kubernetes objects
  +-- restore PVC/snapshot nếu có
  |
  v
cluster
```

Velero mạnh ở namespace/app restore, migration cluster và backup resource state. Với database có transaction consistency yêu cầu cao, nên dùng backup native hoặc operator-aware backup.

### etcd backup/restore

`etcd` là source of truth cho Kubernetes API state. Backup `etcd` giúp khôi phục cluster state tại một thời điểm.

K3s dùng datastore khác nhau theo cách cài:

| K3s mode | Datastore | Backup phù hợp |
|---|---|---|
| Single-server mặc định | SQLite file trong `/var/lib/rancher/k3s/server/db/` | Filesystem backup/snapshot theo runbook K3s; không dùng `k3s etcd-snapshot` |
| HA embedded datastore | Embedded `etcd` | `k3s etcd-snapshot save/ls/prune` |
| External datastore | MySQL/PostgreSQL/etcd ngoài | Backup native của datastore đó |

Vì vậy câu "backup K3s bằng etcd snapshot" chỉ đúng khi cluster đang chạy embedded `etcd`. Trong lab cần kiểm tra mode hiện tại trước khi chạy command.

Use case phù hợp:

- Khôi phục control plane self-managed.
- Rollback cluster state khi control plane hỏng.
- Disaster recovery cho cluster nhỏ.

Giới hạn:

- Không backup dữ liệu bên trong PVC.
- Restore toàn cluster, không phải restore chọn lọc một namespace.
- Snapshot cũ có thể rollback cả state tốt lẫn state xấu.
- Với managed Kubernetes, cloud provider quản lý control plane nên bạn thường không truy cập `etcd` trực tiếp.

### App-level backup

Stateful app cần backup theo semantics của nó.

PostgreSQL:

- Logical backup: `pg_dump`, dễ restore chọn lọc, chậm với DB lớn.
- Physical backup/WAL: phù hợp production, point-in-time recovery.
- Operator như CloudNativePG có backup integration.

Lab nên có ít nhất một drill `pg_dump`/restore vì đây là cách nhanh nhất để chứng minh application-level backup khác với backup YAML/PVC. Với database nhỏ, dump logical đủ để học restore order, validation và RTO thực tế.

Redis:

- RDB/AOF giúp persistence nhưng không thay thế DR đầy đủ.
- Cache thuần có thể không cần backup, nhưng Redis làm queue/session/state thì phải có strategy.

Kafka:

- Kafka không backup như database truyền thống đơn giản.
- Replication trong cluster không thay thế region disaster recovery.
- Cần topic retention, MirrorMaker/cluster linking hoặc app replay strategy.

## Deep dive: Consistency problem

Backup Kubernetes object và volume snapshot không đảm bảo app-level consistency nếu app đang ghi dữ liệu.

Ví dụ PostgreSQL trên PVC:

```text
Velero snapshots PVC at 10:00:00
Postgres đang flush WAL/checkpoint
Snapshot có thể crash-consistent, không chắc application-consistent
```

Crash-consistent có thể restore được với engine có WAL tốt, nhưng không nên mặc định coi là an toàn cho mọi workload. Production cần:

- Quiesce/freeze hoặc backup native.
- WAL archiving/PITR cho PostgreSQL.
- Restore drill định kỳ.
- Checksum/validation sau restore.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Backup control plane | Backup volume | Ghi chú |
|---|---|---|---|
| K3s local/k3d | Có thể reset nhanh; snapshot chỉ để học | `local-path` không phù hợp DR | Lab nên tập restore namespace bằng Velero hoặc manifest |
| K3s self-managed | K3s snapshot datastore, backup file snapshot ra nơi khác | Longhorn/OpenEBS/NFS/cloud CSI tùy setup | Team chịu trách nhiệm toàn bộ restore |
| Kubernetes self-managed | `etcdctl snapshot save` hoặc tool platform | CSI snapshot/storage backend | Cần runbook control plane |
| EKS/GKE/AKS | Cloud quản lý `etcd`; không restore trực tiếp | Dùng cloud snapshots/Velero plugins/CSI | Team vẫn backup app data, PVC, GitOps, secrets |

Managed Kubernetes giảm gánh nặng control plane DR, nhưng không backup workload data thay bạn.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Trade-off |
|---|---|---|
| Git-only restore | Stateless app, config đầy đủ trong Git | Không restore PVC/Secret runtime |
| Velero namespace restore | App-level restore, migration cluster | Cần object storage/plugin/permission |
| etcd snapshot | Self-managed control plane DR | Restore toàn cluster, không restore chọn lọc |
| CSI snapshot | PVC-level restore nhanh | Phụ thuộc storage provider, consistency cần kiểm tra |
| Database-native backup | Dữ liệu quan trọng | Cần vận hành riêng, restore drill phức tạp |
| Active-passive DR | RTO/RPO vừa phải | Chi phí thấp hơn active-active |
| Active-active multi-region | RTO thấp | Complexity rất cao, data consistency khó |

### Best Practices

- Định nghĩa RPO/RTO trước khi chọn tool.
- Backup phải được mã hóa và lưu ngoài cluster.
- Test restore định kỳ, không chỉ test backup job thành công.
- Ghi rõ owner: platform backup cluster state, app team backup data semantics.
- Dùng GitOps để rebuild stateless manifests.
- Dùng database-native backup cho dữ liệu quan trọng.
- Không lưu backup cùng failure domain với cluster.
- Không backup secret plaintext vào nơi thiếu encryption/access control.
- Tạo restore runbook có command cụ thể và thời gian ước lượng.

## Performance Considerations

Backup ảnh hưởng trực tiếp đến I/O:

- Volume snapshot thường nhanh nếu storage hỗ trợ copy-on-write, nhưng snapshot export có thể tốn network/disk.
- Logical database backup tốn CPU, I/O và có thể làm tăng latency.
- Restore lớn có thể bão hòa storage backend và kéo dài startup.
- Backup nhiều namespace cùng lúc có thể tạo load lên `kube-apiserver`.
- Compression/encryption giảm dung lượng nhưng tăng CPU.

Production nên:

- Chạy backup ngoài giờ peak nếu RPO cho phép.
- Rate limit hoặc chia lịch backup.
- Theo dõi duration, size, failure count.
- Test restore trên cluster riêng để không ảnh hưởng production.

## Debugging Checklist

Khi backup fail:

```bash
velero backup get
velero backup describe <backup> --details
velero backup logs <backup>
kubectl get pods -n velero
kubectl logs deploy/velero -n velero
kubectl get volumesnapshot -A
kubectl get events -A --sort-by=.lastTimestamp
```

Khi restore fail:

```bash
velero restore get
velero restore describe <restore> --details
velero restore logs <restore>
kubectl get pvc,pv -A
kubectl describe pvc <pvc> -n <namespace>
kubectl get pods -n <namespace>
kubectl describe pod <pod> -n <namespace>
```

Root cause phổ biến:

| Symptom | Nguyên nhân | Fix |
|---|---|---|
| Backup `PartiallyFailed` | Một resource không đọc được hoặc snapshot fail | Xem backup logs, RBAC/plugin |
| Restore PVC Pending | StorageClass không tồn tại ở cluster mới | Map StorageClass hoặc tạo class tương đương |
| Pod restore xong CrashLoop | Secret/config/data không tương thích | Restore dependency hoặc sửa env |
| CR restore fail | CRD chưa tồn tại | Restore CRD/operator trước |
| Backup quá chậm | Volume lớn hoặc object storage chậm | Chia scope, schedule, optimize backend |

## Liên hệ với kiến thức đã biết

Trong backend, backup database phải gắn với transaction log và restore verification. Kubernetes cũng vậy: manifest chỉ là schema triển khai, không phải dữ liệu business. Với Kafka/Redis/Postgres, phải hiểu semantics của từng hệ thống trước khi chọn backup.

Với system design, DR là bài toán failure domain. Single cluster backup không giải quyết mất region. Multi-region không tự giải quyết conflict dữ liệu.

## Tóm tắt

- Backup phải đi kèm restore drill.
- GitOps rebuild stateless desired state, không thay thế backup data.
- Velero hữu ích cho Kubernetes objects và volume snapshot, nhưng database quan trọng cần backup native.
- K3s/self-managed cần backup datastore/control plane; managed Kubernetes che phần đó nhưng workload vẫn là trách nhiệm của team.
- RPO/RTO phải là input thiết kế, không phải suy nghĩ sau cùng.

## Câu hỏi tự kiểm tra

1. Khác nhau giữa RPO và RTO là gì?
2. Vì sao Velero backup PVC chưa chắc đủ cho PostgreSQL production?
3. Khi restore sang cluster mới, StorageClass có thể gây lỗi gì?
4. Managed Kubernetes có loại bỏ nhu cầu backup app data không?
5. Bạn sẽ thiết kế restore drill monthly như thế nào?

## Tài liệu tham khảo

- Kubernetes Backup and Restore Concepts: https://kubernetes.io/docs/concepts/cluster-administration/
- Velero Documentation: https://velero.io/docs/
- K3s Backup and Restore: https://docs.k3s.io/cli/etcd-snapshot
- PostgreSQL Continuous Archiving and PITR: https://www.postgresql.org/docs/current/continuous-archiving.html
- Kubernetes Volume Snapshots: https://kubernetes.io/docs/concepts/storage/volume-snapshots/
