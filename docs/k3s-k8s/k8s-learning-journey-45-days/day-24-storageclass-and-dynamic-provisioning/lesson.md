# Day 24: StorageClass và dynamic provisioning

## Mục tiêu bài học

- Hiểu `StorageClass` là policy mô tả cách tạo volume động cho PVC.
- Phân biệt static provisioning và dynamic provisioning.
- Nắm các field quan trọng: `provisioner`, `parameters`, `reclaimPolicy`, `allowVolumeExpansion`, `volumeBindingMode`.
- Biết vì sao `WaitForFirstConsumer` quan trọng với storage có topology/zone/node constraint.
- Debug được lỗi provisioner, default StorageClass sai và PVC không bind.

## Vấn đề cần giải quyết

Ở Day 23, bạn có thể tạo PV thủ công. Nhưng production không thể yêu cầu platform admin tạo từng PV cho từng PVC. Dynamic provisioning cho phép team app chỉ tạo PVC; storage provisioner tự tạo PV và backend volume tương ứng.

Ví dụ:

```text
PVC: "need 20Gi ReadWriteOnce from fast-ssd"
  |
  v
StorageClass fast-ssd
  |
  v
CSI/provisioner creates real disk
  |
  v
PV is created and bound
```

`StorageClass` là nơi platform encode policy: dùng driver nào, disk type nào, reclaim thế nào, có expand được không, bind ngay hay chờ Pod.

## Mental Model

```text
StorageClass
  = provisioning policy

PVC
  = request referencing a class

Provisioner / CSI controller
  = component that creates backend volume and PV

PV
  = result of provisioning
```

PVC không tự tạo disk. Nó kích hoạt provisioner thông qua StorageClass.

## Lý thuyết cốt lõi

### Static vs dynamic provisioning

Static provisioning:

- Admin tạo PV trước.
- PVC bind vào PV phù hợp.
- Hợp cho storage có sẵn, migration, lab hoặc local/static disk.
- Tốn công, dễ sai capacity/class/access mode.

Dynamic provisioning:

- Admin tạo StorageClass.
- App tạo PVC.
- Provisioner tạo PV/backend volume tự động.
- Hợp production và self-service platform.

### `provisioner`

`provisioner` là tên driver/provisioner xử lý PVC:

```yaml
provisioner: rancher.io/local-path
```

Hoặc với CSI driver thường có dạng:

```yaml
provisioner: disk.csi.azure.com
provisioner: ebs.csi.aws.com
provisioner: pd.csi.storage.gke.io
```

Tên provisioner phải match driver đã cài. Nếu StorageClass tham chiếu provisioner không tồn tại, PVC sẽ Pending.

### `parameters`

`parameters` truyền option cho provisioner. Ví dụ cloud disk có thể có disk type, IOPS, encrypted flag, filesystem type. Local-path có config riêng.

Điểm vận hành:

- Parameters phụ thuộc driver, không portable giữa cloud/provider.
- Thay đổi StorageClass không nhất thiết thay đổi volume đã tạo.
- Platform nên publish một số class rõ ràng như `standard`, `fast`, `shared`, thay vì để mọi team tự viết parameters.

### Default StorageClass

Một StorageClass có thể được đánh dấu default bằng annotation:

```yaml
metadata:
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
```

PVC không khai báo `storageClassName` sẽ dùng default class nếu có. Rủi ro:

- Default class sai khiến workload dùng storage đắt/chậm/không HA.
- Nhiều default class gây behavior khó đoán.
- PVC muốn không dùng dynamic provisioning phải set `storageClassName: ""`.

### `reclaimPolicy`

StorageClass có thể set reclaim policy cho PV được tạo động:

```yaml
reclaimPolicy: Delete
```

Với dynamic provisioning, `Delete` thường phổ biến vì volume tạo theo PVC. Nhưng dữ liệu quan trọng vẫn cần backup, snapshot, retention policy và review xóa PVC.

### `allowVolumeExpansion`

Nếu bật:

```yaml
allowVolumeExpansion: true
```

PVC có thể request size lớn hơn sau này. Điều kiện:

- Driver hỗ trợ expansion.
- Filesystem resize được.
- Có đủ capacity/quota.
- Workload chịu được quá trình resize.

Kubernetes không cung cấp shrink PVC như thao tác phổ biến. Thiết kế capacity nên có buffer và monitor.

### `volumeBindingMode`

Hai mode chính:

- `Immediate`: provision/bind PV ngay khi PVC được tạo.
- `WaitForFirstConsumer`: chờ Pod dùng PVC được schedule rồi mới provision/bind.

`Immediate` đơn giản nhưng có thể tạo volume sai zone/node. `WaitForFirstConsumer` quan trọng với:

- Cloud disk theo availability zone.
- Local persistent volume.
- Storage phụ thuộc topology.

Ví dụ failure nếu dùng `Immediate`:

```text
PVC creates disk in zone-a
Pod scheduled to node in zone-b
Disk cannot attach
Pod stuck ContainerCreating/Pending
```

Với `WaitForFirstConsumer`, scheduler xem cả Pod constraints và storage topology trước khi quyết định.

### `storageClassName` semantics

Trong PVC:

```yaml
storageClassName: fast
```

Nghĩa là dùng class `fast`.

```yaml
storageClassName: ""
```

Nghĩa là không dùng dynamic provisioning; chỉ bind static PV không có class.

Nếu field bị omit, PVC dùng default StorageClass nếu cluster có.

### StorageClass không phải SLA đầy đủ

Tên `fast` không đủ nếu không có contract rõ:

- Latency target là gì?
- IOPS/throughput thế nào?
- Có snapshot không?
- Có expansion không?
- Reclaim policy là gì?
- Có multi-zone replication không?
- Backup thuộc trách nhiệm ai?

Platform tốt thường document từng class như một product nhỏ.

## Deep dive: Cách hoạt động bên trong

Khi PVC tham chiếu một StorageClass, storage controller/provisioner quan sát PVC và quyết định tạo backend volume. Với `Immediate`, provisioning xảy ra ngay khi PVC xuất hiện. Với `WaitForFirstConsumer`, scheduler giữ PVC ở trạng thái chờ cho đến khi có Pod consumer, rồi kết hợp Pod constraints, node topology và storage topology để chọn nơi tạo volume.

PV được tạo động thường có `claimRef`, `storageClassName`, capacity, access mode và đôi khi có `nodeAffinity` hoặc topology labels. Khi PVC bị xóa, reclaim policy trên StorageClass quyết định PV/backend volume bị xóa hay giữ lại.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

K3s thường cài `local-path-provisioner` và StorageClass `local-path` mặc định. Đây là dynamic provisioning rất tiện cho lab:

- PVC tự tạo PV.
- Data nằm trên local disk node.
- Không cần cloud CSI.

Caveat:

- Không HA.
- Node-local data ràng buộc scheduling.
- Trong `k3d`, path thực tế có thể nằm trong node container hoặc mount từ host tùy cấu hình.
- Không dùng để kết luận performance/behavior của cloud disk, NFS, Ceph hay Longhorn.

Trên Kubernetes chuẩn, platform có thể cài nhiều provisioner như NFS, Longhorn, OpenEBS, Ceph hoặc cloud CSI. Trên EKS/GKE/AKS, StorageClass thường map tới cloud disk/file với quota, IAM và zone topology riêng. Team app không nên hardcode `local-path`; hãy inspect class thực tế hoặc dùng class name do platform publish.

## Trade-offs và Best Practices

### Trade-offs

| Backend/class | Phù hợp | Caveat |
|---|---|---|
| K3s `local-path` | Lab, single-node, demo persistence | Node-local, không HA |
| Cloud block disk | Database single-writer `RWO`, managed cloud | Zone attach, quota/IAM, thường không `RWX` |
| Cloud file/NFS | Shared files `RWX` | Latency/locking semantics khác block disk |
| Longhorn/OpenEBS replicated | Edge/on-prem cần storage Kubernetes-native | Cần disk/network ổn định, vận hành driver |
| Rook/Ceph | Platform lớn cần block/file/object | Operational complexity cao |

### Best Practices

- [ ] Có danh sách StorageClass được platform support chính thức.
- [ ] Default class được chọn có chủ đích.
- [ ] `volumeBindingMode` phù hợp với topology.
- [ ] `allowVolumeExpansion` và expansion runbook rõ ràng.
- [ ] Reclaim policy và data retention được document.
- [ ] Parameters không để app team tự đoán.
- [ ] StorageClass gắn với backup/snapshot/monitoring policy.
- [ ] Provisioner/CSI controller có alert và upgrade plan.

### Tránh làm

- Tạo nhiều StorageClass không ai sở hữu.
- Đặt default class là storage đắt hoặc không HA mà không thông báo.
- Dùng `Immediate` cho topology-sensitive disk rồi debug Pod mount lỗi sau.
- Tin rằng `Delete` reclaim policy là backup strategy.
- Đổi parameters StorageClass và nghĩ volume cũ tự đổi theo.

## Performance Considerations

- `StorageClass` không tự đảm bảo latency/IOPS; nó chỉ truyền policy/parameters cho backend.
- `WaitForFirstConsumer` có thể làm PVC nhìn như `Pending` lâu hơn, nhưng đổi lại tránh provisioning sai zone/node.
- `allowVolumeExpansion` giúp tăng capacity nhưng không thay thế capacity planning và alert trước khi full disk.
- Default class sai có thể tạo chi phí lớn hoặc performance thấp cho nhiều workload mà team không nhận ra.
- Với storage topology-sensitive, rollout, reschedule và autoscaling node pool đều có thể bị giới hạn bởi attach/mount behavior.

## Debugging Checklist

PVC dynamic không bind:

1. `kubectl describe pvc <pvc>` đọc events.
2. `kubectl get storageclass` kiểm tra class tồn tại/default.
3. `kubectl describe storageclass <class>` kiểm tra provisioner.
4. `kubectl -n kube-system get pods` tìm provisioner/CSI controller.
5. Đọc logs provisioner/controller.
6. Kiểm tra quota/capacity/topology.
7. Với `WaitForFirstConsumer`, tạo Pod consumer và inspect scheduler events.

Pod mount volume dynamic lỗi:

1. `kubectl describe pod <pod>`.
2. Kiểm tra node/zone của Pod và PV node affinity/topology.
3. Kiểm tra CSI node plugin trên node đó.
4. Kiểm tra attach/mount errors trong events.

## Liên hệ với kiến thức đã biết

StorageClass giống một "product contract" nội bộ: team platform publish vài class như `standard`, `fast`, `shared`, còn team app chọn theo nhu cầu workload. Với PostgreSQL/Kafka, class phải gắn với latency, fsync, topology và backup. Với upload/shared file, block disk `RWO` có thể sai hoàn toàn nếu app cần nhiều replicas ghi chung.

## Tóm tắt

StorageClass là API self-service cho storage. Nó giúp platform đưa ra vài lựa chọn được quản lý, còn app chỉ claim nhu cầu. Khi vận hành, phần khó nằm ở topology, reclaim, expansion, quota và driver health. YAML PVC đơn giản chỉ là bề mặt của một chuỗi storage backend phức tạp phía dưới.

## Câu hỏi tự kiểm tra

1. PVC omit `storageClassName` khác `storageClassName: ""` như thế nào?
2. Vì sao `WaitForFirstConsumer` quan trọng với cloud disk theo zone?
3. Tại sao không nên hardcode `local-path` trong tài liệu production?
4. StorageClass có phải backup policy không?
5. Khi PVC dynamic Pending, bạn đọc object/log nào trước?

## Tài liệu tham khảo

- Kubernetes Documentation: Storage Classes.
- Kubernetes Documentation: Dynamic Volume Provisioning.
- Kubernetes Documentation: Persistent Volumes và Volume Expansion.
- K3s Documentation: local-path provisioner.
