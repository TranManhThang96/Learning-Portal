# Day 40: Advanced Scheduling

## Mục tiêu bài học

- Hiểu `nodeSelector`, node affinity, pod affinity/anti-affinity, taints/tolerations và topology spread constraints.
- Biết phân biệt constraint bắt buộc (`required`) và ưu tiên mềm (`preferred`).
- Thiết kế scheduling cho node pool, workload isolation, high availability và latency-aware placement.
- Debug được Pod `Pending` do taint, label, affinity, anti-affinity, topology hoặc resource constraints.
- Hiểu khác biệt giữa scheduling trong lab K3s single-node, self-managed multi-node và managed node pools trên cloud.

## Vấn đề cần giải quyết

Scheduler mặc định cố đặt Pod lên node phù hợp dựa trên resource requests và constraints. Với production, "đặt ở đâu cũng được" thường không đủ:

- Database/cache cần node có disk nhanh.
- GPU workload cần node pool riêng.
- Ingress/controller cần chạy trên edge nodes.
- Workload team A không được chạy chung node với workload team B.
- Replicas của cùng service cần spread qua zones/nodes.
- System workloads cần tránh bị app workload chen vào.
- Spot/preemptible nodes chỉ phù hợp worker chịu restart.

Advanced scheduling giúp encode các ràng buộc đó. Nhưng constraint quá chặt làm Pod `Pending`, cluster autoscaling kém hiệu quả và rollout kẹt.

## Mental Model

```text
PodSpec
  |
  +-- resources requests
  +-- nodeSelector / nodeAffinity
  +-- podAffinity / podAntiAffinity
  +-- tolerations
  +-- topologySpreadConstraints
  |
  v
kube-scheduler
  |
  +-- filter: node nào hợp lệ?
  +-- score: node nào tốt hơn?
  +-- bind: gán Pod vào node
```

Scheduling constraint giống bộ lọc và điểm ưu tiên. `required` loại node khỏi candidate set. `preferred` tăng/giảm điểm nhưng không chặn scheduling.

## Lý thuyết cốt lõi

### nodeSelector

`nodeSelector` là cách đơn giản nhất để yêu cầu Pod chạy trên node có label cụ thể.

```yaml
spec:
  nodeSelector:
    disk: ssd
```

Ưu điểm:

- Dễ đọc.
- Dễ debug.
- Phù hợp constraint đơn giản.

Nhược điểm:

- Chỉ hỗ trợ match exact key/value.
- Không có preferred rule.
- Dễ làm Pod Pending nếu label thiếu.

### Node affinity

Node affinity linh hoạt hơn `nodeSelector`.

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: nodepool
          operator: In
          values:
          - compute
          - general
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 80
      preference:
        matchExpressions:
        - key: disk
          operator: In
          values:
          - ssd
```

Tên dài nhưng ý nghĩa quan trọng:

- `requiredDuringScheduling`: bắt buộc lúc schedule.
- `IgnoredDuringExecution`: nếu label node đổi sau khi Pod chạy, Pod không bị đuổi tự động.

Node affinity tốt cho node pool strategy:

- `nodepool=system`
- `nodepool=general`
- `nodepool=memory-optimized`
- `nodepool=gpu`
- `lifecycle=spot`

### Taints và tolerations

Taint đặt trên node để repel Pod. Toleration đặt trên Pod để cho phép Pod chịu taint đó.

```bash
kubectl taint nodes <node> dedicated=platform:NoSchedule
```

Pod cần toleration:

```yaml
tolerations:
- key: dedicated
  operator: Equal
  value: platform
  effect: NoSchedule
```

Effects:

| Effect | Meaning |
|---|---|
| `NoSchedule` | Pod mới không schedule lên node nếu không tolerate |
| `PreferNoSchedule` | Cố tránh nhưng không bắt buộc |
| `NoExecute` | Pod đang chạy không tolerate có thể bị evict |

Taints/tolerations thường dùng để reserve node cho workload đặc biệt, nhưng chỉ toleration chưa đảm bảo Pod sẽ chạy ở node đó. Muốn "chỉ workload X chạy ở node pool X", thường dùng cả taint trên node và node affinity/nodeSelector trên Pod.

### Pod anti-affinity

Pod anti-affinity dùng để tránh đặt Pod gần Pod khác.

Ví dụ spread replicas của cùng app ra nhiều node:

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app: api
        topologyKey: kubernetes.io/hostname
```

Required anti-affinity có thể làm rollout Pending nếu cluster không đủ node/topology. Vì vậy với nhiều app, `preferred` hoặc topology spread constraints thường thực dụng hơn.

### Pod affinity

Pod affinity đặt Pod gần Pod khác.

Use case:

- Side workloads cần gần cache/local service.
- Batch worker gần data-local service.
- App và node-local dependency.

Rủi ro:

- Tăng coupling placement.
- Giảm scheduling flexibility.
- Có thể làm blast radius xấu hơn nếu nhiều workload quan trọng tụ lại cùng node/zone.

### Topology spread constraints

Topology spread constraints điều khiển phân bổ Pod qua topology domains như node, zone, region.

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      app: api
```

Khái niệm:

| Field | Meaning |
|---|---|
| `topologyKey` | Label xác định domain, ví dụ hostname hoặc zone |
| `maxSkew` | Chênh lệch tối đa số Pod giữa domains |
| `whenUnsatisfiable` | `DoNotSchedule` hoặc `ScheduleAnyway` |
| `labelSelector` | Tập Pod cần spread |

So với anti-affinity, topology spread mô tả cân bằng phân bổ rõ hơn và phù hợp HA multi-zone.

### Priority và preemption

`PriorityClass` cho scheduler biết Pod nào quan trọng hơn. Nếu bật preemption, Pod priority cao có thể đẩy Pod priority thấp khỏi node để có chỗ chạy.

Use case:

- System-critical workloads.
- Ingress/gateway quan trọng.
- Control plane add-ons.

Rủi ro:

- Preemption gây disruption workload khác.
- Nếu resource tổng thể thiếu nghiêm trọng, preemption chỉ chuyển incident sang nơi khác.

## Deep dive: Scheduler failure path

Khi Pod `Pending`, scheduler ghi events:

```text
0/3 nodes are available: 1 node(s) had untolerated taint,
2 node(s) didn't match Pod's node affinity/selector.
```

Đây là evidence quan trọng nhất. Không đoán. Đọc `describe pod`.

Luồng debug:

```text
Pod Pending
  |
  +-- describe pod events
  |
  +-- resource insufficient?
  +-- untolerated taint?
  +-- node selector/affinity mismatch?
  +-- pod anti-affinity impossible?
  +-- topology spread impossible?
  +-- PVC topology binding?
```

Advanced scheduling thường tương tác với autoscaling:

- Constraint quá chặt có thể làm Cluster Autoscaler không tìm được node group phù hợp.
- Node group label/taint template sai làm Pod Pending mãi.
- Spread multi-zone cần node pool ở nhiều zone thật.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | Scheduler constraints là API upstream | Kết quả phụ thuộc labels/taints/topology hiện có |
| K3s local/lab | Có thể học label, taint, affinity trên single/multi-node | Single-node không thể chứng minh HA spread thật; k3d node labels không giống cloud zone |
| Self-managed production | Team tự quản lý node labels, taints, scheduler config, node pools | Cần governance cho labels/taints, capacity và upgrade/drain |
| EKS/GKE/AKS | Node pools/node groups có labels, taints, zones, spot/on-demand | Cloud provider/node autoscaler cần cấu hình label/taint template đúng; storage topology và zone-aware LB/CSI quan trọng |

Managed Kubernetes giúp tạo node pool theo zone/instance type, nhưng team vẫn thiết kế Pod constraints.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| Không constraint | Workload stateless phổ thông | Có thể chạy trên node không phù hợp |
| `nodeSelector` | Constraint đơn giản, rõ | Không linh hoạt |
| Required node affinity | Workload bắt buộc cần node pool cụ thể | Pod Pending nếu node pool thiếu |
| Preferred node affinity | Muốn ưu tiên node tốt hơn | Không đảm bảo placement |
| Taint/toleration | Reserve node hoặc isolate workload | Toleration không kéo Pod vào node nếu thiếu affinity |
| Required anti-affinity | HA cứng, replica không được cùng node | Rollout Pending nếu thiếu node |
| Preferred anti-affinity | HA mềm cho app thông thường | Có thể co-locate khi cluster chật |
| Topology spread `DoNotSchedule` | HA zone/node bắt buộc | Pending nếu topology không đủ |
| Topology spread `ScheduleAnyway` | Cân bằng mềm | Không đảm bảo HA |
| Priority/preemption | Workload cực kỳ quan trọng | Evict workload khác |

### Best Practices

- Nên bắt đầu với constraint tối thiểu, thêm dần theo failure domain thật.
- Nên dùng labels/taints chuẩn hóa theo node pool và lifecycle.
- Nên dùng taint + affinity cho dedicated node pool.
- Nên dùng topology spread cho HA replicas thay vì required anti-affinity quá cứng nếu không thật cần.
- Nên dùng preferred rules cho app thông thường để giữ scheduling flexibility.
- Nên kiểm tra scheduler events trước khi sửa manifest.
- Nên document label/taint contract của từng node pool.
- Nên test constraints với Cluster Autoscaler nếu dùng managed/cloud.
- Tránh dùng hostname cụ thể trong production manifest trừ trường hợp break-glass.
- Tránh required constraints nhiều lớp nếu cluster không đủ topology/capacity.

## Performance Considerations

- Scheduling constraints quá chặt giảm bin-packing efficiency và tăng cost.
- Required anti-affinity/topology trên cluster lớn có thể tăng độ phức tạp scheduling, dù scheduler đã tối ưu nhiều.
- Spread qua zones cải thiện availability nhưng có thể tăng cross-zone latency/cost.
- Co-locate app với cache/local dependency giảm latency nhưng tăng blast radius.
- Dedicated node pool giúp isolation/performance ổn định hơn nhưng giảm utilization.
- Spot/preemptible node giảm cost nhưng tăng interruption; phù hợp worker idempotent hơn API critical.
- GPU/high-memory node pool cần taint để tránh workload thường chiếm node đắt tiền.

## Debugging Checklist

Khi Pod `Pending`:

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl get nodes --show-labels
kubectl describe node <node>
kubectl get pod <pod> -n <namespace> -o yaml
```

Kiểm tra:

- Event nói thiếu resource hay constraint mismatch?
- Node có label mà Pod yêu cầu không?
- Node có taint mà Pod chưa tolerate không?
- Required affinity/anti-affinity có impossible không?
- `topologyKey` có tồn tại trên node labels không?
- PVC có `WaitForFirstConsumer`/zone topology không?
- Namespace quota hoặc LimitRange có ảnh hưởng không?
- Cluster Autoscaler có node group phù hợp để thêm node không?

Khi spread không như kỳ vọng:

```bash
kubectl get pods -n <namespace> -o wide --show-labels
kubectl get nodes -L topology.kubernetes.io/zone,kubernetes.io/hostname
kubectl describe pod <pod> -n <namespace>
```

Kiểm tra:

- Pod labels có match `labelSelector` của spread constraint không?
- `topologyKey` có trên tất cả nodes không?
- `whenUnsatisfiable` là `DoNotSchedule` hay `ScheduleAnyway`?
- Replica count có đủ để spread không?
- Node capacity có làm scheduler chọn lệch không?

## Liên hệ với kiến thức đã biết

Advanced scheduling giống placement strategy trong distributed systems. Bạn đang chọn failure domain, locality, isolation và cost. Với Redis/Kafka/PostgreSQL, placement ảnh hưởng latency, disk, zone failure và recovery. Với API Gateway, placement ảnh hưởng ingress path, availability và node pool capacity. Với CI/CD/GitOps, constraints nên nằm trong chart/values và được review như production architecture, không phải patch tay.

## Tổng kết

Advanced scheduling cho phép kiểm soát Pod chạy ở đâu và tránh chạy ở đâu. `nodeSelector` và node affinity chọn node theo label. Taints/tolerations đẩy workload không phù hợp ra khỏi node. Pod affinity/anti-affinity và topology spread điều khiển placement tương quan giữa Pods. Càng nhiều required constraints, càng dễ Pending và tốn capacity. Production tốt dùng constraint tối thiểu nhưng rõ ràng, ưu tiên spread/topology theo failure domain thật và luôn debug bằng scheduler events.

## Câu hỏi tự kiểm tra

1. Toleration có đảm bảo Pod sẽ chạy trên node bị taint không?
2. Khi nào nên dùng required anti-affinity, khi nào dùng preferred hoặc topology spread?
3. Vì sao `IgnoredDuringExecution` quan trọng?
4. Constraint scheduling có thể làm Cluster Autoscaler bó tay như thế nào?
5. Vì sao spread qua zones có thể tăng cost hoặc latency?

## Tài liệu tham khảo

- Kubernetes Assign Pods to Nodes: https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/
- Kubernetes Taints and Tolerations: https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/
- Kubernetes Pod Topology Spread Constraints: https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/
- Kubernetes Pod Priority and Preemption: https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/
- Kubernetes Scheduler: https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/
