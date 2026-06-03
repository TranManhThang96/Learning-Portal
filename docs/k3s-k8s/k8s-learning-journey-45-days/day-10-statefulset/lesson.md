# Day 10: StatefulSet

## Mục tiêu bài học

- Giải thích khi nào cần `StatefulSet` thay vì `Deployment`.
- Hiểu stable identity: tên Pod, ordinal, DNS qua Headless Service và storage riêng cho từng replica.
- Cấu hình được `volumeClaimTemplates`, `serviceName`, `podManagementPolicy`, `updateStrategy` và rollout có kiểm soát.
- Phân tích được rủi ro khi chạy workload stateful trên K3s, Kubernetes tự quản và managed Kubernetes.
- Debug được lỗi phổ biến: Pod kẹt `Pending`, PVC không bind, DNS identity sai, rollout stateful bị kẹt.

## Vấn đề cần giải quyết

`Deployment` rất tốt cho stateless service vì Pod có thể bị thay thế bất kỳ lúc nào. Với database, message broker, quorum system hoặc cache cluster, điều đó không đủ:

- Mỗi instance cần identity ổn định để join cluster.
- Storage phải đi theo đúng replica, không được hoán đổi ngẫu nhiên.
- Scale up/scale down thường cần thứ tự để tránh mất quorum.
- Rollout phải thận trọng hơn vì mỗi Pod có thể giữ dữ liệu hoặc vai trò riêng.

`StatefulSet` sinh ra để giải quyết các workload cần identity và storage ổn định. Nó không biến database thành production-ready, nhưng cung cấp primitive cần thiết để chạy các hệ thống stateful có kiểm soát hơn.

## Mental Model

```text
Deployment:
  web-7d8c9f-abcde
  web-7d8c9f-fghij
  web-7d8c9f-klmno
  -> Pod thay được cho nhau.

StatefulSet:
  postgres-0 + pvc data-postgres-0
  postgres-1 + pvc data-postgres-1
  postgres-2 + pvc data-postgres-2
  -> Mỗi Pod có số thứ tự, DNS và volume riêng.
```

Hãy nghĩ `StatefulSet` như một dãy server có số ghế cố định. Nếu `web-1` chết, Kubernetes tạo lại một Pod vẫn tên `web-1` và gắn lại storage của `web-1`. Nó không lấy ghế của `web-2`.

## Lý thuyết cốt lõi

### StatefulSet dùng cho workload nào?

Dùng `StatefulSet` khi app cần ít nhất một trong các điều kiện:

- Stable network identity: member trong cluster cần biết nhau qua hostname ổn định.
- Stable persistent storage: mỗi replica có data riêng.
- Ordered deployment/scaling: tạo `-0` trước, rồi `-1`, rồi `-2`.
- Ordered rolling update: update có kiểm soát theo ordinal.

Ví dụ thường gặp:

- PostgreSQL primary/replica qua operator.
- Kafka broker.
- Redis Sentinel/Cluster.
- Cassandra, ZooKeeper, Elasticsearch.

Không dùng `StatefulSet` chỉ vì "app có database". Nếu service stateless chỉ gọi database ngoài, vẫn dùng `Deployment`.

### Stable Pod identity

Pod của `StatefulSet` có tên deterministic:

```text
<statefulset-name>-<ordinal>
web-0
web-1
web-2
```

Để có DNS identity ổn định, `StatefulSet` cần một Headless Service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
spec:
  clusterIP: None
  selector:
    app: nginx
  ports:
  - name: web
    port: 80
```

Khi `serviceName: nginx`, DNS của từng Pod có dạng:

```text
web-0.nginx.<namespace>.svc.cluster.local
web-1.nginx.<namespace>.svc.cluster.local
web-2.nginx.<namespace>.svc.cluster.local
```

Headless Service không load balance kiểu `ClusterIP`; nó publish endpoint để client hoặc peer có thể resolve từng Pod.

### Stable storage với volumeClaimTemplates

`volumeClaimTemplates` tạo một `PersistentVolumeClaim` riêng cho mỗi Pod:

```yaml
volumeClaimTemplates:
- metadata:
    name: www
  spec:
    accessModes: ["ReadWriteOnce"]
    resources:
      requests:
        storage: 1Gi
```

Với StatefulSet `web`, PVC sẽ có dạng:

```text
www-web-0
www-web-1
www-web-2
```

Mặc định quan trọng: PVC thường được giữ lại khi scale down hoặc delete StatefulSet. Đây là hành vi an toàn để tránh mất dữ liệu ngoài ý muốn. Nếu muốn tự động xóa PVC khi scale/delete, cần dùng chính sách retention phù hợp và hiểu rõ rủi ro.

### OrderedReady và Parallel

Mặc định `StatefulSet` dùng `podManagementPolicy: OrderedReady`:

- Scale up: tạo `web-0`, chờ ready, rồi `web-1`, rồi `web-2`.
- Scale down: xóa từ ordinal cao xuống thấp.
- Rolling update: update theo thứ tự có kiểm soát, thường từ ordinal cao về thấp.

`podManagementPolicy: Parallel` cho phép tạo/xóa Pod song song. Nó nhanh hơn nhưng chỉ nên dùng khi app không phụ thuộc thứ tự bootstrap.

### Update strategy

Hai strategy chính:

```yaml
updateStrategy:
  type: RollingUpdate
```

`RollingUpdate` là mặc định. Khi Pod template đổi, controller update Pod theo thứ tự. Có thể dùng `partition` để update một phần:

```yaml
updateStrategy:
  type: RollingUpdate
  rollingUpdate:
    partition: 2
```

Với replicas=3, `partition: 2` chỉ update Pod có ordinal >= 2, tức `web-2`. Đây là cách đơn giản để thử version mới trên một member trước.

`OnDelete` nghĩa là controller không tự recreate Pod khi template đổi. Bạn phải xóa từng Pod để nó được tạo lại theo template mới. Strategy này hữu ích khi app cần upgrade thủ công nghiêm ngặt.

## Deep Dive: StatefulSet controller làm gì bên trong

```text
1. User apply StatefulSet và Headless Service.
2. StatefulSet controller đọc replicas, serviceName, selector, template.
3. Controller tạo Pod theo ordinal.
4. Nếu có volumeClaimTemplates, controller tạo PVC tương ứng mỗi ordinal.
5. Scheduler đặt Pod lên node sau khi PVC bind được PV phù hợp.
6. Kubelet mount volume rồi start container.
7. Khi Pod chết, controller tạo lại cùng tên và gắn lại PVC cùng ordinal.
8. Khi update template, controller recreate Pod theo update strategy.
```

Điểm khác `Deployment`: controller không coi mọi Pod là interchangeable. Ordinal là một phần của contract vận hành.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| `StatefulSet` API | Giống upstream | Giống upstream | Giống upstream |
| Storage lab | Thường có `local-path-provisioner` mặc định | Tùy admin cài provisioner nào | Thường dùng cloud CSI driver |
| HA storage | `local-path` không phù hợp HA | Cần Longhorn/OpenEBS/Rook/Ceph/NFS/cloud CSI | Cloud disk có lifecycle/zone constraint |
| Node failure | Single-node lab mất node là mất scheduling | Phụ thuộc storage backend | Pod có thể reschedule nhưng volume phải attach được |
| Backup | Bạn tự làm | Bạn tự làm | Cloud snapshot hỗ trợ, nhưng app-consistent backup vẫn là trách nhiệm team |

Trong K3s lab, `local-path` tốt để học PVC binding và volume lifecycle. Nó không làm dữ liệu tự động di chuyển an toàn giữa nodes. Với production, storage backend, backup/restore, anti-affinity, topology và operator mới là phần khó.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| `Deployment` | Stateless service | Scale/rollout nhanh | Thấp | Không có identity/storage ổn định |
| `StatefulSet` | Cần ordinal, DNS, PVC riêng | Rollout/scale chậm hơn | Trung bình-cao | Kẹt vì storage, quorum, ordered readiness |
| `OrderedReady` | Cluster stateful cần thứ tự | Chậm nhưng an toàn | Cần hiểu bootstrap | Một Pod không ready chặn Pod sau |
| `Parallel` | App không phụ thuộc thứ tự | Scale nhanh hơn | Cần app tự xử lý ordering | Race condition khi bootstrap |
| `RollingUpdate` | Update tự động từng member | Có downtime cục bộ từng Pod | Vừa phải | App không chịu được restart tuần tự |
| `OnDelete` | Upgrade cần thao tác thủ công | Kiểm soát tốt hơn | Cao hơn | Quên xóa Pod, version lệch |
| `local-path` | Lab, edge đơn node | I/O phụ thuộc disk node | Thấp | Node hỏng là workload khó recover |
| Cloud CSI | Managed production | Attach/detach có latency | Trung bình | Zone mismatch, attach limit, snapshot inconsistency |

### Best Practices

Nên làm:

- Dùng Headless Service rõ ràng cho identity.
- Đặt `resources.requests` thực tế vì stateful workload thường nhạy CPU/memory/disk I/O.
- Dùng readiness probe phản ánh trạng thái thật: replica đã join cluster, DB đã accept connection, broker đã ready.
- Dùng `PodDisruptionBudget` cho quorum system.
- Dùng `podAntiAffinity` hoặc topology spread để tránh gom nhiều replica stateful lên cùng node/zone khi cluster có đủ topology.
- Tách data path qua PVC, không ghi dữ liệu quan trọng vào container filesystem.
- Test restore, không chỉ test backup.
- Dùng operator đáng tin cậy cho PostgreSQL/Kafka/Redis production thay vì tự ghép YAML thủ công.

Tránh làm:

- Chạy production database trên `local-path` rồi xem đó là HA.
- Scale down StatefulSet mà không hiểu PVC nào sẽ còn lại.
- Dùng một PVC `ReadWriteMany` chung cho mọi replica nếu app không được thiết kế như vậy.
- Rollout đồng loạt stateful cluster mà không có health check/quorum check.
- Xóa PVC để "reset lỗi" khi chưa backup.

## Performance Considerations

- Startup stateful thường chậm hơn stateless vì cần attach/mount volume, replay log, recover data hoặc join cluster.
- `OrderedReady` làm rollout chậm tuyến tính theo số replicas.
- Disk I/O là bottleneck chính với database/broker; CPU/memory chỉ là một phần.
- Cloud volume attach/detach có thể mất thời gian, đặc biệt khi reschedule qua node khác.
- `local-path` phụ thuộc disk của node; benchmark trên laptop không phản ánh cloud SSD/network disk.
- Readiness probe quá đơn giản có thể route traffic vào Pod chưa thật sự đồng bộ dữ liệu.
- Scale stateful không tự động tăng throughput nếu app cần rebalance dữ liệu thủ công.

## Debugging Checklist

Pod kẹt `Pending`:

```bash
kubectl get pod,pvc,pv -n <namespace>
kubectl describe pod <pod>
kubectl describe pvc <pvc>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

DNS identity sai:

```bash
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl exec -it <pod> -- hostname
kubectl run dns-debug --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup <pod>.<service>.<namespace>.svc.cluster.local
```

Rollout kẹt:

```bash
kubectl get statefulset <name> -o wide
kubectl describe statefulset <name>
kubectl get pods -l app=<label> -o wide
kubectl logs <pod> -c <container>
```

Storage nghi ngờ lỗi:

```bash
kubectl get storageclass
kubectl get pvc -n <namespace>
kubectl get pv
kubectl describe pvc <pvc>
kubectl describe pv <pv>
kubectl describe node <node>
```

Đừng giả định PVC/PV luôn có cùng label với Pod. Nếu cần lọc, ưu tiên tên PVC deterministic như `www-web-0` hoặc đọc `.spec.volumeName` từ PVC rồi describe PV tương ứng.

Lab fix thường là sửa manifest/storage class rồi recreate tài nguyên chưa có data quan trọng. Production fix phải ưu tiên backup, snapshot, kiểm tra node/zone/CSI event và kế hoạch failover.

## Liên hệ với kiến thức đã biết

`StatefulSet` giống việc quản lý một cụm server có hostname và disk riêng, không giống một autoscaling group stateless. Với Kafka, broker id và disk phải đi cùng nhau. Với PostgreSQL, primary/replica role không thể được Kubernetes hiểu đầy đủ nếu thiếu operator hoặc logic app-level. Kubernetes cung cấp primitive, không thay thế kiến thức vận hành database.

## Tóm tắt

`StatefulSet` cung cấp stable identity, stable storage và ordered lifecycle cho workload stateful. Nó mạnh hơn `Deployment` ở identity/storage nhưng cũng làm rollout, scaling và recovery phức tạp hơn. Trong K3s, `local-path` rất phù hợp cho lab nhưng không phải HA storage. Production cần storage backend phù hợp, backup/restore đã diễn tập, probes chính xác, anti-affinity và thường cần operator.

## Câu hỏi tự kiểm tra

1. Vì sao `StatefulSet` cần Headless Service?
2. PVC của Pod `web-2` thường có tên theo pattern nào nếu template name là `www`?
3. `OrderedReady` có thể làm rollout kẹt trong tình huống nào?
4. Khi nào chọn `OnDelete` thay vì `RollingUpdate`?
5. Vì sao `local-path-provisioner` phù hợp cho lab nhưng không đủ cho HA production?

## Tài liệu tham khảo

- Kubernetes StatefulSet: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
- Kubernetes StatefulSet API: https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/stateful-set-v1/
- Kubernetes Persistent Volumes: https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- K3s Storage: https://docs.k3s.io/storage
- K3s Packaged Components: https://docs.k3s.io/installation/packaged-components
