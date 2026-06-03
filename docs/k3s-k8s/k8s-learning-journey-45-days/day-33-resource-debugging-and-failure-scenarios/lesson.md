# Day 33: Resource Debugging và Failure Scenarios

## Mục tiêu bài học

- Debug được các lỗi `OOMKilled`, `CrashLoopBackOff`, `Pending`, CPU throttling và eviction theo đúng lớp nguyên nhân.
- Hiểu quan hệ giữa `resources.requests`, `resources.limits`, scheduler, kubelet, container runtime và Linux cgroups.
- Phân biệt lỗi do application, lỗi do Kubernetes scheduling và lỗi do node pressure.
- Biết đọc `events`, `describe`, `kubectl top`, QoS class và metrics liên quan đến resource.
- Biết đặt requests/limits thực dụng cho microservices thay vì copy cấu hình tùy tiện.

## Vấn đề cần giải quyết

Ở production, rất nhiều incident nhìn giống lỗi application nhưng gốc nằm ở resource:

- API thỉnh thoảng chậm vì CPU bị throttle.
- Pod restart liên tục vì memory limit quá thấp.
- Rollout kẹt vì request CPU/memory lớn hơn capacity còn trống.
- Node disk pressure làm Pod bị evict.
- Một workload `BestEffort` bị kill trước khi workload quan trọng bị ảnh hưởng.

Nếu chỉ nhìn `kubectl get pods`, bạn sẽ thấy vài trạng thái ngắn như `Running`, `Pending`, `CrashLoopBackOff` hoặc `Evicted`. Phần khó là hiểu trạng thái đó đến từ scheduler, kubelet, cgroup hay chính process trong container.

## Mental Model

```text
YAML resources
  |
  +-- requests
  |     |
  |     v
  |   scheduler dùng để chọn node
  |
  +-- limits
        |
        v
      kubelet/container runtime cấu hình cgroups
        |
        +-- memory vượt limit -> OOMKilled
        +-- CPU vượt limit -> throttled, không bị kill
        +-- ephemeral storage vượt limit/node pressure -> eviction
```

`requests` là lời hứa để scheduler đặt Pod lên node. `limits` là hàng rào runtime. Nhầm hai khái niệm này là nguyên nhân phổ biến của sizing sai.

## Lý thuyết cốt lõi

### Requests quyết định scheduling

Scheduler không đo CPU/memory thực tế của process để đặt Pod. Nó nhìn tổng `requests` của Pod so với allocatable resource còn lại trên node.

Ví dụ Pod này request 500m CPU và 512Mi memory:

```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    memory: 1Gi
```

Nếu không node nào còn đủ 500m CPU và 512Mi memory theo tính toán scheduler, Pod sẽ `Pending` dù thực tế node có thể đang idle. Đây là hành vi đúng: Kubernetes đặt lịch dựa trên capacity đã cam kết, không dựa trên hy vọng workload sẽ dùng ít.

### Limits quyết định runtime enforcement

Memory limit là hard limit. Khi process trong container dùng vượt giới hạn, kernel OOM killer có thể kill process. Kubernetes sẽ hiển thị:

```text
Last State: Terminated
Reason: OOMKilled
Exit Code: 137
```

CPU limit khác memory limit. Khi container dùng CPU vượt limit, nó thường bị throttle thay vì bị kill. Kết quả là latency tăng, throughput giảm, request timeout, nhưng Pod vẫn `Running`.

Điểm quan trọng: CPU throttling thường khó thấy hơn `OOMKilled` vì nó không tạo restart rõ ràng.

### QoS classes

Kubernetes gán QoS class cho Pod dựa trên requests/limits:

| QoS class | Điều kiện | Khi node pressure |
|---|---|---|
| `Guaranteed` | Mỗi container có CPU/memory request bằng limit | Bị evict sau cùng |
| `Burstable` | Có request/limit nhưng không đủ điều kiện Guaranteed | Bị evict sau Guaranteed |
| `BestEffort` | Không có CPU/memory request và limit | Bị evict trước |

QoS không thay thế priority, nhưng là tín hiệu quan trọng khi kubelet cần bảo vệ node.

Nói chính xác: Pod không bị evict "trước khi có node pressure". Eviction xảy ra khi kubelet thấy node pressure hoặc Pod vượt ephemeral-storage limit. Trong lúc đó, `BestEffort` thường là nhóm bị chọn trước vì không có resource request bảo vệ.

### CrashLoopBackOff không luôn là resource issue

`CrashLoopBackOff` chỉ nói container process exit rồi kubelet restart theo backoff. Nguyên nhân có thể là:

- App panic vì config sai.
- Lệnh container sai.
- Dependency chưa sẵn sàng.
- Memory vượt limit dẫn tới `OOMKilled`.
- Liveness probe kill container quá sớm.

Vì vậy phải đọc `Last State`, `Reason`, `Exit Code`, events và `logs --previous`.

### Eviction và node pressure

Kubelet có eviction manager để bảo vệ node khi các tín hiệu như memory, disk hoặc inode vượt ngưỡng. Pod có thể bị evict khi:

- Node thiếu memory.
- Node filesystem gần đầy.
- Image filesystem gần đầy.
- Pod dùng ephemeral storage vượt limit.

Eviction khác OOMKilled:

- `OOMKilled`: container process bị kill vì memory cgroup hoặc node OOM.
- `Evicted`: kubelet chủ động đuổi Pod để bảo vệ node.

### Ephemeral storage cũng là resource thật

Log container, writable layer, `emptyDir` và temporary files đều có thể ăn ephemeral storage. Workload ghi nhiều file tạm nhưng không đặt limit có thể làm node disk pressure và ảnh hưởng Pod khác.

Với microservices, các nguồn tăng storage thường gặp:

- Log quá nhiều.
- Upload file tạm.
- Cache local không giới hạn.
- Batch job tạo artifact trong container filesystem.
- App ghi vào `/tmp` nhưng không cleanup.

## Deep dive: Cách hoạt động bên trong

### Từ manifest đến cgroups

Luồng đơn giản:

```text
kubectl apply
  -> kube-apiserver lưu PodSpec
  -> scheduler chọn node dựa trên requests và constraints
  -> kubelet trên node nhận PodSpec
  -> container runtime tạo container
  -> cgroups áp dụng CPU/memory limits
```

Scheduler không thực thi limit. Kubelet/runtime không chọn node. Mỗi thành phần chịu một phần của resource lifecycle.

### CPU request, CPU limit và throttling

CPU request ảnh hưởng scheduling và CPU share khi node bị cạnh tranh. CPU limit tạo quota theo chu kỳ. Nếu process muốn chạy nhiều CPU hơn quota, kernel dừng container đến chu kỳ tiếp theo.

Triệu chứng thực tế:

- p95/p99 latency tăng dù Pod không restart.
- `kubectl top pod` thấy CPU chạm gần limit.
- Metrics cAdvisor có `container_cpu_cfs_throttled_periods_total` tăng.
- Tăng replica không giải quyết nếu mỗi replica vẫn bị limit quá chặt với workload single-thread hoặc bursty.

Với latency-sensitive services, CPU limit quá thấp thường gây hại hơn lợi. Nhiều team đặt CPU request hợp lý và không đặt CPU limit cho app stateless, nhưng vẫn đặt memory limit.

`kubectl top` không hiển thị throttling trực tiếp. Nó chỉ cho biết usage hiện tại. Muốn chứng minh throttling, cần metrics từ cAdvisor/Prometheus hoặc node-level cgroup counters.

### Memory request, memory limit và OOM

Memory request giúp scheduler tránh overcommit quá mức. Memory limit ngăn một container ăn hết memory node.

Nếu app có heap runtime như JVM, Node.js, Go, Python, PHP-FPM, bạn cần hiểu memory model của runtime:

- Heap limit nội bộ nên nhỏ hơn container memory limit.
- Native memory, thread stack, buffers và page cache vẫn tính vào usage.
- Liveness probe không sửa được memory leak; nó chỉ làm restart lặp lại.

### Scheduler `Pending`

Pod `Pending` thường không phải lỗi image. Khi container chưa được tạo, hãy đọc scheduling events:

```bash
kubectl describe pod <pod>
kubectl get events --sort-by=.lastTimestamp
```

Thông báo thường gặp:

- `Insufficient cpu`
- `Insufficient memory`
- `node(s) had untolerated taint`
- `node(s) didn't match Pod's node affinity/selector`
- PVC chưa bind hoặc topology storage không phù hợp

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | Requests/limits, QoS, eviction, scheduler và kubelet behavior giống API upstream | Behavior cụ thể phụ thuộc version, runtime, kubelet config và metrics stack |
| K3s local/lab | Dùng cùng object model; phù hợp luyện `OOMKilled`, `Pending`, `top`, events | Node nhỏ, thường chạy nhiều thứ chung máy; local-path storage và k3d không phản ánh đầy đủ production disk pressure |
| Self-managed production | Team kiểm soát kubelet config, node sizing, eviction thresholds, runtime và monitoring | Phải tự chuẩn hóa requests/limits, alerting, capacity planning và upgrade |
| EKS/GKE/AKS | Cloud quản lý control plane; workload resource semantics vẫn giống Kubernetes | Team vẫn chịu trách nhiệm requests/limits, node pool sizing, autoscaling, observability và cost; cloud chỉ cung cấp node/metrics/add-on theo cấu hình |

K3s thường phù hợp để học failure mode nhanh, nhưng không nên lấy limit từ laptop lab rồi áp vào production. Production sizing phải dựa trên metrics thật.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| Không đặt requests | Lab rất nhỏ, thử nghiệm nhanh | Scheduler không có tín hiệu capacity; Pod thành `BestEffort`; dễ bị evict |
| Đặt requests sát usage trung bình | Tối ưu bin-packing, tiết kiệm cost | Burst có thể cạnh tranh CPU/memory nếu không có headroom |
| Đặt requests theo p95 usage | Service quan trọng, latency-sensitive | Tốn node capacity hơn |
| Memory limit thấp | Bảo vệ node khỏi leak | Dễ `OOMKilled` nếu không hiểu runtime overhead |
| Memory limit rất cao hoặc không đặt | Tránh kill sớm trong lab | Một Pod lỗi có thể ảnh hưởng node và Pod khác |
| CPU limit thấp | Chặn workload ăn CPU quá nhiều | Throttling, latency spike khó debug |
| Không đặt CPU limit | Phù hợp nhiều service latency-sensitive | Cần requests/priority/monitoring tốt để tránh noisy neighbor |
| `Guaranteed` QoS | Workload cực kỳ quan trọng, sizing rõ | Ít linh hoạt, giảm utilization |
| `Burstable` QoS | Phần lớn microservices production | Cần chọn request/limit có dữ liệu |

### Best Practices

- Nên đặt memory request và memory limit cho workload production.
- Nên đặt CPU request cho mọi workload production.
- Nên cân nhắc bỏ CPU limit hoặc đặt rất thận trọng cho API latency-sensitive.
- Nên đo usage thật trước khi chuẩn hóa requests/limits.
- Nên alert theo triệu chứng người dùng: latency, error rate, saturation, restart, OOM, throttling.
- Nên đặt ephemeral-storage request/limit cho workload ghi file tạm nhiều.
- Nên phân biệt cấu hình cho API, worker, batch job và database.
- Tránh copy cùng một resource block cho mọi service.
- Tránh tăng limit để che memory leak mà không điều tra.
- Tránh chỉ nhìn average CPU/memory; hãy xem percentile và burst.

## Performance Considerations

- CPU throttling ảnh hưởng trực tiếp latency và throughput, đặc biệt với API có request burst.
- Memory limit quá thấp gây restart, cold start, cache warm-up lại và lỗi ngắt quãng.
- Requests quá cao làm cluster cần nhiều node hơn, tăng cost và giảm scheduling flexibility.
- Requests quá thấp làm overcommit nặng, tăng noisy neighbor và eviction risk.
- Ephemeral storage đầy có thể làm node mất khả năng tạo Pod mới, ghi log hoặc pull image.
- HPA scale theo CPU có thể phản ứng sai nếu CPU limit quá thấp và throttling xảy ra trước khi autoscaling kịp mở rộng.

## Debugging Checklist

### Khi Pod `OOMKilled`

```bash
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace> --previous
kubectl top pod <pod> -n <namespace>
kubectl get pod <pod> -n <namespace> -o jsonpath='{.status.containerStatuses[*].lastState}'
```

Kiểm tra:

- Container nào bị kill?
- `Exit Code` có phải 137 không?
- Memory limit hiện tại là bao nhiêu?
- App có heap/runtime memory limit riêng không?
- Có spike traffic hoặc rollout gần đó không?

### Khi Pod `Pending`

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get nodes
kubectl describe node <node>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Kiểm tra:

- Events báo `Insufficient cpu/memory` hay taint/affinity/PVC?
- Request của Pod có vượt allocatable của mọi node không?
- Namespace có `ResourceQuota` hoặc `LimitRange` không?
- Node pool hiện tại có phù hợp workload không?

### Khi nghi CPU throttling

```bash
kubectl top pod -n <namespace>
kubectl describe pod <pod> -n <namespace>
kubectl get pod <pod> -n <namespace> -o yaml
```

Nếu có Prometheus/cAdvisor, kiểm tra:

```promql
rate(container_cpu_cfs_throttled_periods_total{namespace="<namespace>"}[5m])
/
rate(container_cpu_cfs_periods_total{namespace="<namespace>"}[5m])
```

Kiểm tra:

- CPU usage có chạm limit không?
- Có metrics throttling trực tiếp không, hay chỉ mới thấy usage bằng `kubectl top`?
- Latency tăng cùng thời điểm throttling không?
- Workload có bursty không?
- HPA target có dựa trên CPU không?

### Khi Pod bị `Evicted`

```bash
kubectl describe pod <pod> -n <namespace>
kubectl describe node <node>
kubectl get events -A --sort-by=.lastTimestamp
kubectl top node
```

Kiểm tra:

- Eviction do memory, disk hay inode?
- Pod QoS class là gì?
- Pod có ghi log/temp file quá nhiều không?
- Node có image/container garbage collection hoạt động không?

## Production checklist

- [ ] Mỗi service có baseline requests/limits dựa trên metrics thật.
- [ ] Có dashboard restart, OOMKilled, CPU throttling, memory working set, pod pending và node pressure.
- [ ] Có runbook riêng cho `Pending`, `OOMKilled`, `Evicted`, `CrashLoopBackOff`.
- [ ] Có `LimitRange` hoặc policy để tránh workload production không có requests.
- [ ] Có review resource khi traffic pattern thay đổi.
- [ ] Có phân loại workload quan trọng bằng namespace, priority hoặc node pool khi cần.
- [ ] Có capacity planning cho node pool, không chỉ autoscaling phản ứng.
- [ ] Có test load hoặc incident drill trước khi đặt limit quá chặt.

## Anti-patterns

- Đặt CPU/memory limit giống nhau cho mọi service.
- Thấy `CrashLoopBackOff` là xóa Pod ngay trước khi đọc `--previous` logs.
- Chỉ tăng memory limit sau `OOMKilled` mà không kiểm tra leak hoặc runtime heap.
- Đặt CPU limit rất thấp cho API latency-sensitive rồi debug nhầm sang network.
- Không đặt requests, để scheduler không có dữ liệu capacity.
- Bỏ qua ephemeral storage cho workload ghi nhiều log/temp file.
- Dùng metrics trung bình ngày để sizing service có burst mạnh.

## Liên hệ với kiến thức đã biết

- Với backend APIs, CPU throttling thường biểu hiện thành p95/p99 latency tăng trước khi có lỗi rõ.
- Với database/cache clients, memory leak hoặc connection pool quá lớn có thể biến thành `OOMKilled`.
- Với Kafka/worker jobs, request quá cao hoặc burst batch lớn dễ làm Pod `Pending` hoặc node pressure.
- Với observability, metrics lịch sử mới chứng minh spike/throttling tốt hơn một lần chạy `kubectl top`.

## Tóm tắt

Resource debugging là cầu nối giữa Kubernetes object model và hệ điều hành bên dưới. `requests` giải thích vì sao Pod có được schedule hay không. `limits` giải thích vì sao container bị kill hoặc throttle. Events, `describe`, `logs --previous`, `kubectl top`, QoS class và metrics cAdvisor giúp bạn tách rõ lỗi scheduling, lỗi runtime resource và lỗi application. Khi sizing production, mục tiêu không phải đặt limit thật thấp, mà là tạo đủ tín hiệu để scheduler, kubelet và platform bảo vệ hệ thống mà không làm hỏng latency.

## Câu hỏi tự kiểm tra

- Vì sao `CrashLoopBackOff` không đủ để kết luận lỗi do resource?
- `requests` ảnh hưởng scheduler khác `limits` ảnh hưởng runtime như thế nào?
- Khi node pressure xảy ra, QoS class ảnh hưởng eviction order ra sao?
- Vì sao `kubectl top` không chứng minh trực tiếp CPU throttling?

## Tài liệu tham khảo

- Kubernetes Documentation: Resource Management for Pods and Containers.
- Kubernetes Documentation: Pod QoS Classes.
- Kubernetes Documentation: Node-pressure Eviction.
- Kubernetes Documentation: Metrics Server và Resource Metrics Pipeline.
