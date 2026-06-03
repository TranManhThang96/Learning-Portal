# Day 25: CSI drivers và storage troubleshooting

## Mục tiêu bài học

- Hiểu `CSI` là chuẩn để Kubernetes tích hợp storage backend qua driver.
- Phân biệt CSI controller plugin, node plugin, sidecars và Kubernetes objects liên quan.
- Biết đọc `CSIDriver`, `StorageClass`, `VolumeAttachment`, PVC/PV events và driver logs.
- So sánh Longhorn, OpenEBS, Rook/Ceph ở mức use case, trade-offs và operational caveats.
- Có runbook debug provisioning, attach, mount, expansion và data-path issue.

## Vấn đề cần giải quyết

PV/PVC/StorageClass là API surface. Nhưng storage thật nằm sau driver:

```text
PVC -> StorageClass -> CSI controller -> backend volume
                         |
Pod -> kubelet -> CSI node plugin -> attach/mount volume
```

Khi lỗi storage xảy ra, symptom thường xuất hiện ở Pod:

- Pod kẹt `ContainerCreating`.
- PVC `Pending`.
- Volume attach timeout.
- Filesystem mount failed.
- App báo I/O error hoặc latency tăng.
- Node reboot làm volume detach/attach chậm.

Day 25 giúp bạn debug xuyên qua Kubernetes object layer xuống driver/backend layer.

## Mental Model

```text
Kubernetes API objects
  PVC / PV / StorageClass / VolumeAttachment
          |
          v
CSI controller side
  create/delete volume, attach/detach, snapshot/expand
          |
          v
Storage backend
  disk, replicated block, filesystem, Ceph, cloud volume
          |
          v
CSI node side
  stage/publish/mount volume on the node
          |
          v
Pod container path
```

Provisioning and mounting are different phases. PVC Bound does not guarantee Pod can mount the volume.

## Lý thuyết cốt lõi

### CSI là gì?

`Container Storage Interface` là specification cho storage vendors viết driver dùng chung với Kubernetes và container orchestrators. Kubernetes không cần biết chi tiết từng backend. Nó gọi driver qua chuẩn CSI để:

- Create/delete volume.
- Attach/detach volume.
- Mount/unmount volume.
- Expand volume.
- Snapshot/restore nếu driver hỗ trợ.

### CSI components

Một CSI deployment thường có:

- Controller plugin: chạy dạng Deployment/StatefulSet, xử lý create/delete/attach/snapshot/expand.
- Node plugin: chạy dạng DaemonSet trên mỗi node, xử lý stage/publish/mount.
- Sidecars: container chuẩn như external-provisioner, external-attacher, external-resizer, external-snapshotter, livenessprobe, node-driver-registrar.

Không phải driver nào cũng có đủ mọi sidecar. File/block/network storage có yêu cầu khác nhau.

### Kubernetes objects liên quan

| Object | Ý nghĩa |
|---|---|
| `StorageClass` | Class policy, provisioner name, parameters |
| `PersistentVolumeClaim` | Request của workload |
| `PersistentVolume` | Volume đã provision hoặc static |
| `CSIDriver` | Driver registration/capabilities |
| `VolumeAttachment` | Attach state cho CSI volume vào node |
| `VolumeSnapshotClass` | Policy snapshot nếu snapshot CRD/driver hỗ trợ |
| `VolumeSnapshot` | Snapshot request |

Khi debug, đọc các object này trước khi vào logs.

### Provision vs attach vs mount

Storage failure thường rơi vào ba pha:

```text
Provision:
  PVC -> PV/backend volume

Attach:
  Volume attached to node if backend requires attach

Mount:
  Filesystem/device mounted into Pod path
```

Một PVC có thể `Bound` nhưng Pod vẫn fail vì attach/mount. Một Pod có thể mount được nhưng app vẫn lỗi vì permission, filesystem, capacity hoặc latency.

### Longhorn

Longhorn là distributed block storage cho Kubernetes, phổ biến với K3s/Rancher ecosystem. Nó replicate volume giữa nodes và cung cấp UI, backup/snapshot features.

Điểm mạnh:

- Dễ tiếp cận cho homelab, edge, small cluster.
- Tích hợp Kubernetes-native.
- Có replication, snapshot/backup workflow.
- Hợp K3s hơn so với tự build Ceph nếu team nhỏ.

Caveat:

- Cần disk/network ổn định giữa nodes.
- Replicated block storage nhạy với latency và node pressure.
- Upgrade, engine image, replica rebuild cần hiểu rõ.
- Không biến cluster nhỏ thành database platform "miễn phí".

### OpenEBS

OpenEBS là tập hợp nhiều storage engines, có thể dùng local PV hoặc replicated engine tùy mode.

Điểm mạnh:

- Linh hoạt, có lựa chọn local PV đơn giản.
- Phù hợp lab hoặc workload cần node-local performance.
- Có thể dùng làm bước trung gian trước giải pháp phức tạp hơn.

Caveat:

- Mỗi engine có behavior khác nhau; đừng nói "OpenEBS" chung chung.
- Local PV không HA.
- Replicated mode cần vận hành kỹ như bất kỳ distributed storage nào.

### Rook/Ceph

Rook vận hành Ceph trên Kubernetes. Ceph cung cấp block, filesystem và object storage.

Điểm mạnh:

- Nền tảng storage mạnh, nhiều feature.
- Hỗ trợ block (`RBD`), shared filesystem (`CephFS`) và object (`RGW`).
- Phù hợp platform lớn có năng lực storage ops.

Caveat:

- Operational complexity cao.
- Cần hiểu Ceph concepts: OSD, MON, MGR, pool, placement group, CRUSH.
- Cần disk/network/monitoring nghiêm túc.
- Không nên dùng chỉ để có RWX nếu team chưa sẵn sàng vận hành Ceph.

### Managed cloud CSI

Trên EKS/GKE/AKS, CSI drivers thường tích hợp cloud disk/file:

- Block disk: tốt cho `RWO`, database single-writer.
- Managed file/NFS-like: có thể hỗ trợ `RWX`, đổi lại latency/semantics khác.
- Snapshots/backups tích hợp cloud nhưng vẫn cần policy và restore drill.

Managed control plane không loại bỏ trách nhiệm:

- IAM/permissions cho CSI controller.
- Cloud quota.
- Zone topology.
- Upgrade add-on.
- Backup/retention.
- Cost.

## Deep dive: Cách hoạt động bên trong

CSI tách controller path và node path. Controller side thường xử lý `CreateVolume`, `DeleteVolume`, `ControllerPublishVolume` hoặc snapshot/resize. Node side chạy trên từng node để `NodeStageVolume` và `NodePublishVolume`, tức là chuẩn bị device/filesystem rồi mount vào Pod path. Vì vậy một lỗi có thể nằm ở API object, controller, backend, node plugin, kubelet hoặc chính permission bên trong container.

Với driver không cần attach riêng, bạn có thể không thấy `VolumeAttachment`. Với cloud block disk, `VolumeAttachment` thường là evidence quan trọng để biết volume attach vào node nào và phase nào đang lỗi.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

- K3s local-path là local provisioner tiện cho lab, không phải distributed CSI storage và có thể không tạo `CSIDriver`/`VolumeAttachment` như cloud CSI.
- Kubernetes chuẩn self-managed có thể chạy Longhorn, OpenEBS, Rook/Ceph hoặc vendor CSI; team phải vận hành controller/node plugin.
- EKS/GKE/AKS thường dùng CSI add-on tích hợp cloud IAM/quota/zone; provider hỗ trợ control plane nhưng workload data safety vẫn do team thiết kế.
- Với k3d, test CSI thật có thể bị giới hạn do node là container; ưu tiên object/debug flow, không kết luận performance production.

## Trade-offs và Best Practices

### Trade-offs

| Backend | Điểm mạnh | Chi phí vận hành |
|---|---|---|
| K3s local-path | Rất nhẹ cho lab | Không HA, object CSI có thể rỗng/không có |
| Longhorn | Dễ tiếp cận cho K3s/edge, có replication/snapshot | Nhạy với disk/network, cần upgrade/rebuild runbook |
| OpenEBS | Nhiều engine, local PV đơn giản | Behavior khác nhau theo engine, replicated mode phức tạp hơn |
| Rook/Ceph | Block/file/object mạnh | Cần năng lực Ceph ops nghiêm túc |
| Cloud CSI | Tích hợp cloud disk/file, snapshot/quota/IAM | Zone attach, IAM, cost và provider-specific limits |

### Best Practices

- [ ] Storage driver có owner, version pinning và upgrade plan.
- [ ] Controller và node plugin có alerts.
- [ ] PVC/PV/VolumeAttachment events được đưa vào runbook.
- [ ] Backup, snapshot và restore drill đã test.
- [ ] Topology/zone behavior được hiểu.
- [ ] Node drain/upgrade với attached volumes đã test.
- [ ] Capacity, inode, latency, IOPS/throughput có monitoring.
- [ ] SecurityContext/fsGroup/permissions được chuẩn hóa.
- [ ] Không chạy database production trên storage backend chưa được benchmark.

### Tránh làm

- Thấy PVC `Bound` rồi kết luận storage healthy.
- Chỉ monitor capacity mà bỏ qua latency.
- Dùng distributed storage trên cluster có network yếu rồi đổ lỗi cho database.
- Cài Rook/Ceph chỉ để học nhanh RWX nhưng không có năng lực vận hành.
- Không test restore mà tin snapshot/backup đã đủ.
- Drain node chứa volume mà không hiểu attach/detach behavior.

## Performance Considerations

- Storage incident thường biểu hiện ở p95/p99 latency, I/O wait, queue depth hoặc app timeout trước khi Pod/PVC đổi trạng thái.
- Distributed storage như Longhorn/Ceph phụ thuộc mạnh vào network latency, replica rebuild và node pressure.
- Cloud block disk có giới hạn IOPS/throughput theo size/type; PVC size nhỏ có thể đồng nghĩa performance thấp.
- Inode full và filesystem full là hai lỗi khác nhau; cần kiểm tra cả `df -h` và `df -i`.
- Node drain/upgrade có thể tăng downtime nếu attach/detach hoặc filesystem check mất lâu.

## Debugging Checklist

### PVC Pending

Kiểm tra:

```bash
kubectl describe pvc <pvc> -n <ns>
kubectl get storageclass
kubectl describe storageclass <class>
kubectl get events -n <ns> --sort-by=.lastTimestamp
```

Nguyên nhân thường gặp:

- StorageClass không tồn tại.
- Provisioner name sai hoặc driver chưa cài.
- Provisioner controller lỗi.
- Quota/capacity không đủ.
- `WaitForFirstConsumer` chưa có Pod consumer.
- Topology constraints không thỏa.

### PV Bound nhưng Pod không chạy

Kiểm tra:

```bash
kubectl describe pod <pod> -n <ns>
kubectl describe pv <pv>
kubectl get volumeattachment
kubectl get events -n <ns> --sort-by=.lastTimestamp
```

Nguyên nhân thường gặp:

- Attach timeout.
- Volume already attached to another node.
- CSI node plugin không chạy trên node.
- Filesystem mount failed.
- Permission/securityContext mismatch.
- Node topology không match volume.

### App chạy nhưng storage chậm/lỗi I/O

Kubernetes object có thể nhìn healthy trong khi data path có vấn đề. Kiểm tra:

- App logs và error rate.
- Node disk/network pressure.
- CSI driver metrics/logs.
- Backend health dashboard.
- Latency p95/p99, queue depth, IOPS/throughput.
- Filesystem full hoặc inode full.

### Expansion lỗi

Kiểm tra:

- StorageClass có `allowVolumeExpansion`.
- Driver hỗ trợ controller/node expansion.
- PVC conditions.
- Pod cần restart hay filesystem online resize được.
- Backend quota/capacity.

## Liên hệ với kiến thức đã biết

Với PostgreSQL/Kafka/Redis, CSI chỉ là đường đến volume; durability còn phụ thuộc replication, WAL/AOF/log semantics, backup và restore drill. Với observability stack như Elasticsearch/Loki/Prometheus, storage latency và retention quyết định cả chi phí lẫn độ tin cậy. Với microservices stateless, lỗi storage thường nằm ở upload/cache/tmp hoặc secret/config mount hơn là CSI attach.

## Tóm tắt

CSI là cầu nối giữa Kubernetes API và storage backend thật. Khi debug storage, bạn cần đi theo chuỗi PVC -> PV -> StorageClass -> CSI controller -> VolumeAttachment -> CSI node plugin -> Pod mount -> application I/O. Storage trong Kubernetes không chỉ là "claim một volume"; nó là một hệ thống vận hành có topology, performance, failure mode và data safety riêng.

## Câu hỏi tự kiểm tra

1. Vì sao PVC `Bound` chưa đảm bảo Pod mount thành công?
2. Controller plugin và node plugin trong CSI khác nhau như thế nào?
3. Khi nào `VolumeAttachment` có thể không tồn tại dù Pod dùng PVC?
4. Bạn kiểm tra gì khi app báo I/O chậm nhưng PVC/PV đều healthy?
5. Vì sao restore drill quan trọng hơn việc chỉ có snapshot?

## Tài liệu tham khảo

- Kubernetes Documentation: CSI Volume Plugins.
- Kubernetes Documentation: Storage Classes, Volume Snapshots, Volume Expansion.
- Container Storage Interface Specification.
- Longhorn, OpenEBS, Rook/Ceph official documentation.
