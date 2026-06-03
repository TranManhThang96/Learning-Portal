# Day 23: PersistentVolume và PersistentVolumeClaim

## Mục tiêu bài học

- Hiểu vì sao Kubernetes tách nhu cầu storage của app (`PVC`) khỏi implementation storage (`PV`).
- Phân biệt `PersistentVolume`, `PersistentVolumeClaim`, `StorageClass` và volume mount trong Pod.
- Nắm được binding lifecycle, access modes, reclaim policy và volume expansion ở mức vận hành.
- Biết debug PVC `Pending`, Pod `ContainerCreating` do volume attach/mount lỗi.
- Hiểu giới hạn của local storage và K3s `local-path-provisioner` trong lab.

## Vấn đề cần giải quyết

Day 22 cho bạn `emptyDir`, ConfigMap, Secret và hostPath. Nhưng nếu Pod bị xóa hoặc reschedule, dữ liệu quan trọng cần tiếp tục tồn tại. Database, upload storage, queue data, search index hoặc object cache đều cần storage bền vững hơn Pod lifecycle.

Kubernetes giải quyết bằng cách tách role:

- Application developer khai báo "tôi cần 10Gi, ReadWriteOnce" qua `PersistentVolumeClaim`.
- Platform/storage admin cung cấp storage thật qua `PersistentVolume` hoặc dynamic provisioning.
- Pod chỉ mount PVC, không cần biết backend là local disk, NFS, block volume, cloud disk hay distributed storage.

## Mental Model

```text
Pod
  |
  v
PersistentVolumeClaim: "need 5Gi RWO"
  |
  v
PersistentVolume: "this 5Gi volume satisfies claim"
  |
  v
Storage backend: local disk / cloud disk / NFS / CSI driver
```

PVC là yêu cầu. PV là tài nguyên storage cụ thể. Binding nối PVC với PV.

## Lý thuyết cốt lõi

### PersistentVolume

`PersistentVolume` là object cluster-scoped mô tả một volume có thể được claim:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-demo
spec:
  capacity:
    storage: 1Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  hostPath:
    path: /tmp/pv-demo
```

Trong production, PV thường do dynamic provisioner tạo, không viết tay. Static PV vẫn hữu ích khi dùng NFS có sẵn, local disk cố định hoặc migration đặc biệt.

### PersistentVolumeClaim

`PersistentVolumeClaim` là object namespaced do workload dùng:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: manual
```

PVC bind với PV nếu match:

- `storageClassName`
- capacity đủ lớn
- access mode phù hợp
- selector nếu có
- volume mode nếu có

### Binding lifecycle

```text
PV Available
  |
  | PVC phù hợp
  v
PV Bound <-> PVC Bound
  |
  | PVC deleted
  v
PV Released
  |
  | reclaim policy decides
  v
Retain / Delete / Recycle deprecated
```

PVC `Pending` nghĩa là chưa có PV phù hợp hoặc provisioner chưa tạo được PV.

### Reclaim policy

`persistentVolumeReclaimPolicy` quyết định chuyện gì xảy ra với PV khi PVC bị xóa:

- `Delete`: xóa PV và thường xóa storage backend nếu provisioner hỗ trợ. Phổ biến với dynamic provisioning.
- `Retain`: giữ PV/data để admin xử lý thủ công. An toàn hơn cho dữ liệu quan trọng nhưng cần runbook cleanup.
- `Recycle`: cũ/deprecated, tránh dùng.

Điểm vận hành: xóa PVC không nhất thiết nghĩa là data đã mất hoặc còn; phải đọc reclaim policy và storage backend behavior.

### Access modes

Access mode mô tả cách volume có thể được mount:

- `ReadWriteOnce` (`RWO`): volume mount read-write bởi một node.
- `ReadOnlyMany` (`ROX`): nhiều node mount read-only.
- `ReadWriteMany` (`RWX`): nhiều node mount read-write.
- `ReadWriteOncePod` (`RWOP`): một Pod duy nhất mount read-write, khi driver hỗ trợ.

Access mode không phải permission bên trong filesystem. Nó là capability/constraint ở tầng attach/mount storage.

### Volume mode

`volumeMode` có thể là:

- `Filesystem`: mount filesystem vào container. Đây là mặc định.
- `Block`: expose raw block device cho Pod.

Hầu hết application dùng `Filesystem`. Raw block phù hợp với một số database/storage engine cần tự quản filesystem hoặc block device.

### PVC trong Deployment và StatefulSet

Deployment có thể mount một PVC, nhưng nhiều replicas cùng mount một PVC `RWO` thường lỗi hoặc nguy hiểm tùy storage. Với stateful workload, `StatefulSet` + `volumeClaimTemplates` tạo PVC riêng cho mỗi replica:

```text
data-postgres-0
data-postgres-1
data-postgres-2
```

Đây là lý do Day 10 StatefulSet quan trọng trước khi học storage sâu.

### Local storage caveat

K3s mặc định thường có `local-path-provisioner`, tạo storage trên local disk của node. Nó rất tiện cho lab, nhưng có caveat:

- Data gắn với node.
- Nếu node mất, data mất hoặc khó phục hồi.
- Pod cần được schedule về node có volume.
- Không tương đương cloud block storage hay distributed storage.

Đừng xem local-path là HA storage production.

### Volume expansion

PVC có thể mở rộng nếu StorageClass cho phép `allowVolumeExpansion: true` và driver hỗ trợ:

```yaml
spec:
  resources:
    requests:
      storage: 10Gi
```

Không phải volume nào cũng shrink được. Thực tế production thường chỉ hỗ trợ expand, không hỗ trợ giảm size. Cần kiểm tra filesystem resize, driver behavior và application behavior.

## Deep dive: Cách hoạt động bên trong

PV/PVC binding là reconciliation loop riêng của Kubernetes storage controllers. Controller quan sát PVC mới, tìm PV phù hợp hoặc gọi provisioner nếu PVC dùng StorageClass dynamic. Khi PVC đã bind, scheduler phải tính thêm ràng buộc volume như access mode, `nodeAffinity` của PV hoặc topology của backend storage. `kubelet` trên node sau đó mount volume vào Pod path.

Điểm dễ nhầm: PVC `Bound` chỉ chứng minh claim đã có volume phù hợp ở API layer. Nó không đảm bảo filesystem mount thành công, permission đúng, backend latency ổn hoặc dữ liệu đã được backup.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

- K3s lab thường có `local-path-provisioner`, tiện để tạo PVC nhanh nhưng data nằm ở local disk của node.
- Kubernetes chuẩn self-managed có thể dùng NFS, local PV, Longhorn, Ceph, OpenEBS hoặc cloud CSI tùy cách cài.
- EKS/GKE/AKS thường dùng cloud CSI cho block disk; volume có zone/topology và IAM/quota riêng.
- Managed control plane không quản lý backup/restore application data cho bạn; team vẫn phải thiết kế snapshot, retention và restore drill.
- Static `hostPath` PV chỉ nên dùng lab/single-node hoặc phải có `nodeAffinity` rõ ràng để scheduler không đặt Pod sai node.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi phù hợp | Failure mode chính |
|---|---|---|
| Static PV | Storage có sẵn, migration, lab kiểm soát binding | Dễ sai class/capacity/node affinity, cleanup thủ công |
| Dynamic PVC | Self-service production, volume theo workload | Phụ thuộc provisioner/CSI/IAM/quota |
| `Retain` | Dữ liệu quan trọng, cần kiểm tra trước khi xóa backend | PV `Released` cần runbook reuse/delete |
| `Delete` | Lab, ephemeral data, volume tạo theo PVC | Xóa PVC có thể xóa backend volume |
| Local-path/local PV | Lab, edge workload chấp nhận node-local | Không HA, node mất là dữ liệu rủi ro |

### Best Practices

- [ ] Workload cần persistence thật sự hay chỉ cần cache/scratch?
- [ ] PVC size, access mode và StorageClass được chọn theo workload.
- [ ] Reclaim policy phù hợp với risk mất dữ liệu.
- [ ] Backup/restore không dựa vào PVC tồn tại.
- [ ] Stateful workload dùng PVC riêng cho mỗi replica nếu cần identity riêng.
- [ ] Không scale Deployment dùng chung PVC `RWO` một cách mù quáng.
- [ ] PVC expansion đã được test.
- [ ] Storage metrics/alerts có đủ: capacity, latency, attach/mount error.

### Tránh làm

- Dùng `hostPath` hoặc local-path rồi gọi đó là HA database storage.
- Xóa PVC trong cleanup script mà không hiểu reclaim policy.
- Dùng một PVC `ReadWriteOnce` cho Deployment nhiều replicas.
- Tin rằng snapshot/backup tự động có sẵn chỉ vì dùng PVC.
- Không kiểm tra zone/topology khi dùng cloud disk.

## Performance Considerations

- Storage latency thường chi phối p95/p99 của database, queue và stateful service nhiều hơn CPU.
- `ReadWriteOnce` cloud disk attach/detach có thể làm rollout hoặc node drain chậm.
- Local-path/local PV có latency thấp trong lab nhưng không có replication và không survive node failure.
- PVC expansion cần theo dõi filesystem resize, app behavior và capacity alert; Kubernetes không hỗ trợ shrink như workflow phổ biến.
- Benchmark phải đo throughput, fsync latency, inode/capacity, attach/mount time và recovery time sau Pod/node restart.

## Debugging Checklist

### PVC Pending

PVC `Pending` thường do:

- Không có default StorageClass.
- `storageClassName` sai.
- Static PV không match capacity/accessModes/class.
- Provisioner Pod lỗi.
- Cloud quota/subnet/zone không đủ.
- `WaitForFirstConsumer` cần Pod để quyết định zone/node.

Commands:

```bash
kubectl get pvc,pv
kubectl describe pvc <pvc>
kubectl get storageclass
kubectl get events --sort-by=.lastTimestamp
kubectl -n kube-system get pods
```

### Pod mount lỗi

Pod có thể kẹt `ContainerCreating` nếu PVC đã bound nhưng attach/mount fail:

- Node không attach được disk.
- Filesystem corrupt hoặc permission sai.
- CSI node plugin lỗi.
- Volume đang attach ở node khác.
- Access mode không phù hợp với replica placement.

Commands:

```bash
kubectl describe pod <pod>
kubectl describe pvc <pvc>
kubectl describe pv <pv>
kubectl get events --sort-by=.lastTimestamp
kubectl -n kube-system logs <storage-driver-pod> --tail=100
```

## Liên hệ với kiến thức đã biết

Với database như PostgreSQL, Redis persistence hoặc Kafka logs, PVC chỉ giải quyết "volume ở đâu"; nó không giải quyết replication, backup, PITR, quorum hay client failover. Với microservices stateless, PVC thường nên tránh trừ khi thật sự có file state. Với ELK/observability, storage latency và retention policy quyết định chi phí vận hành.

## Tóm tắt

PV/PVC là contract giữa workload và storage. PVC giúp developer nói nhu cầu, PV/provisioner giúp platform cung cấp implementation. Khi học storage Kubernetes, điều quan trọng không phải chỉ là YAML chạy được, mà là hiểu lifecycle dữ liệu khi Pod, node, PVC, PV hoặc backend storage thay đổi.

## Câu hỏi tự kiểm tra

1. PVC `Pending` khác Pod `Pending` ở điểm nào?
2. Vì sao static `hostPath` PV trên multi-node cần `nodeAffinity`?
3. `Retain` và `Delete` khác nhau như thế nào khi xóa PVC?
4. Vì sao PVC `Bound` chưa đủ để kết luận app sẽ ghi được dữ liệu?
5. Expansion PVC cần kiểm tra những điều kiện nào?

## Tài liệu tham khảo

- Kubernetes Documentation: Persistent Volumes.
- Kubernetes Documentation: Storage Classes và Dynamic Volume Provisioning.
- K3s Documentation: Storage và local-path provisioner.
- CSI Documentation: Volume lifecycle concepts.
