# Day 39: Autoscaling

## Mục tiêu bài học

- Hiểu `HPA`, `VPA`, `Cluster Autoscaler` và `KEDA` giải quyết các lớp scaling khác nhau.
- Biết HPA dùng metrics và `resources.requests` như thế nào để tính replica.
- Phân biệt scale Pod, scale resource request và scale node.
- Chọn metric phù hợp cho API, worker, queue consumer và batch workload.
- Debug được HPA không scale, scale quá nhạy, scale chậm hoặc Pod Pending sau khi scale.

## Vấn đề cần giải quyết

Microservices production không có tải cố định:

- API traffic tăng theo giờ cao điểm.
- Worker backlog tăng khi Kafka/queue có spike.
- Batch job cần scale theo schedule.
- Pod scale lên nhưng node không đủ capacity.
- App chậm vì CPU throttling trước khi HPA kịp phản ứng.

Autoscaling giúp cluster phản ứng với nhu cầu thay đổi, nhưng autoscaling sai có thể gây incident:

- HPA scale dựa trên CPU request sai.
- Scale quá nhanh làm downstream database chết.
- Scale quá chậm làm queue backlog tăng.
- Cluster Autoscaler thêm node chậm, Pod vẫn Pending.
- VPA restart workload không đúng thời điểm.
- KEDA event metric sai làm worker scale về 0 khi vẫn còn backlog.

## Mental Model

```text
Traffic / workload demand
        |
        v
Metrics pipeline
        |
        +-- HPA: change replicas
        |
        +-- VPA: change pod requests/recommendations
        |
        +-- KEDA: scale replicas from events/external metrics
        |
        v
Scheduler places Pods
        |
        v
Cluster Autoscaler adds/removes nodes if capacity insufficient
```

Autoscaling là control loop. Control loop chỉ tốt khi metric đúng, target đúng, delay được hiểu rõ và downstream có khả năng chịu tải.

## Lý thuyết cốt lõi

### HPA

`HorizontalPodAutoscaler` thay đổi số replicas của workload như `Deployment`, `StatefulSet` hoặc custom resource có `/scale`.

HPA phổ biến nhất dùng CPU utilization:

```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70
```

CPU utilization của HPA được tính theo CPU request:

```text
current CPU usage / CPU request
```

Nếu container dùng 200m CPU và request là 100m, utilization là 200%. Nếu request đặt sai, HPA ra quyết định sai.

HPA cũng hỗ trợ:

- Memory resource metric.
- Pods metric.
- Object metric.
- External metric.
- Custom metric qua metrics adapters.

### HPA behavior

Autoscaling không nên phản ứng giật cục. `autoscaling/v2` cho phép cấu hình behavior:

```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0
    policies:
    - type: Percent
      value: 100
      periodSeconds: 60
  scaleDown:
    stabilizationWindowSeconds: 300
    policies:
    - type: Percent
      value: 50
      periodSeconds: 60
```

Scale up thường cần nhanh hơn scale down. Scale down chậm giúp tránh oscillation khi traffic dao động.

### VPA

`VerticalPodAutoscaler` điều chỉnh hoặc gợi ý `resources.requests` cho Pod.

Mode phổ biến:

| Mode | Hành vi |
|---|---|
| `Off` | Chỉ đưa recommendation |
| `Initial` | Set request khi Pod tạo mới |
| `Auto` | Có thể evict Pod để áp request mới |

VPA hữu ích khi workload khó sizing thủ công. Nhưng VPA có thể conflict với HPA nếu cùng dùng CPU/memory. Pattern thực dụng:

- HPA scale replicas theo traffic.
- VPA mode `Off` để lấy recommendation.
- Nếu dùng VPA `Auto`, tránh dùng HPA CPU utilization trên cùng workload hoặc hiểu rõ interaction.

### Cluster Autoscaler

`Cluster Autoscaler` không scale Pod. Nó scale node group/node pool khi Pod Pending vì thiếu capacity và có thể xóa node rảnh.

Luồng:

```text
HPA increases replicas
  -> new Pods Pending due to insufficient CPU/memory
  -> Cluster Autoscaler adds node
  -> scheduler places Pods
```

Delay thực tế:

- HPA sync period.
- Pod scheduling.
- Cloud VM provisioning.
- Node boot/join.
- Image pull.
- App startup/readiness.

Vì vậy autoscaling node thường chậm hơn autoscaling Pod trên capacity có sẵn.

### KEDA

`KEDA` scale workload theo event/external source như:

- Kafka lag.
- RabbitMQ queue length.
- Redis list length.
- Prometheus query.
- Cron schedule.
- Cloud queue metrics.

KEDA tạo/điều khiển HPA phía sau cho nhiều scaler. Nó phù hợp với worker/event-driven workload hơn CPU metric.

Ví dụ worker Kafka nên scale theo consumer lag hơn là CPU. CPU thấp không có nghĩa backlog thấp.

### Scale to zero

KEDA có thể scale worker về 0 nếu không có event. Điều này tiết kiệm cost nhưng có caveats:

- Cold start tăng latency xử lý event mới.
- Consumer group rebalance.
- Connection warm-up.
- First event delay.
- App phải chịu được start/stop thường xuyên.

API HTTP public thường không scale-to-zero bằng HPA thuần. Nếu cần, dùng platform hỗ trợ request-driven scale như Knative, KEDA HTTP add-on hoặc serverless layer, với trade-off cold start.

## Deep dive: Chọn metric đúng

### API services

Metric tốt:

- Request rate.
- p95/p99 latency.
- In-flight requests.
- CPU nếu CPU-bound và request đúng.

CPU HPA không phù hợp nếu:

- App chờ network/database nhiều.
- Bottleneck nằm ở DB connection pool.
- CPU throttling do limit thấp.
- Request latency tăng nhưng CPU không tăng.

### Worker/queue consumer

Metric tốt:

- Queue length.
- Consumer lag.
- Oldest message age.
- Processing rate.
- Error/dead-letter rate.

Không nên chỉ dùng CPU cho worker nếu backlog là tín hiệu kinh doanh chính.

### Stateful workloads

Autoscaling stateful system khó hơn:

- PostgreSQL không scale write bằng cách tăng Pod replica đơn giản.
- Kafka broker scaling cần rebalancing partition.
- Redis Cluster scaling cần shard migration.

Dùng Operator/domain tool nếu cần scale stateful. HPA generic thường không đủ.

### Downstream protection

Scale app lên có thể làm downstream chết nhanh hơn:

- API thêm replicas làm DB connection tăng.
- Worker thêm consumers làm Kafka/DB/cache bị overload.
- Retry storm cộng với autoscaling tạo load khuếch đại.

Autoscaling phải đi cùng:

- Rate limiting.
- Connection pool limits.
- Backpressure.
- Queue length alarms.
- Circuit breaker nếu phù hợp.
- Capacity plan cho downstream.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | HPA/VPA/KEDA/Cluster Autoscaler đều dựa trên API/controller patterns | Cần metrics-server hoặc metrics adapter, controller install riêng |
| K3s local/lab | Học HPA tốt nếu có metrics-server; KEDA/VPA có thể cài thêm | Cluster Autoscaler ít ý nghĩa trên local single-node; node provisioning không giống cloud |
| Self-managed production | Team tự vận hành metrics pipeline, autoscaler, node provisioning integration | Phải tự xử lý capacity, node image, scale-down disruption, observability |
| EKS/GKE/AKS | HPA semantics giống upstream; cloud có node autoscaling integration | Team vẫn phải cấu hình node pools, requests, KEDA/VPA, metrics adapters; cloud provisioning có delay/cost |

Managed Kubernetes giúp scale node pool dễ hơn, nhưng không chọn metric đúng thay bạn.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| HPA CPU | API/worker CPU-bound, requests đúng | Sai nếu workload I/O-bound hoặc request sai |
| HPA memory | Workload memory correlates with load | Memory không giảm nhanh, dễ scale-down kém |
| HPA custom metric | Latency, RPS, in-flight, queue metric | Cần metrics adapter, query ổn định |
| VPA recommendation | Sizing requests | Không tự scale throughput |
| VPA Auto | Workload ít nhạy restart, cần request tuning tự động | Eviction gây disruption, conflict HPA |
| Cluster Autoscaler | Cloud/node pool có thể scale | Pod Pending trong lúc chờ node, cost tăng |
| KEDA | Event-driven worker, queue lag | External metric sai làm scale sai |
| Scale to zero | Worker không cần luôn sẵn | Cold start, first event delay |

### Best Practices

- Nên đặt CPU/memory requests có dữ liệu trước khi bật HPA.
- Nên dùng `autoscaling/v2` và cấu hình scale behavior cho production.
- Nên scale worker theo queue lag/age thay vì CPU nếu backlog là tín hiệu chính.
- Nên đặt `maxReplicas` dựa trên downstream capacity, không chỉ cluster capacity.
- Nên monitor desired/current replicas, scaling events và metrics availability.
- Nên giữ headroom node pool cho scale-up nhanh, nhất là API latency-sensitive.
- Nên dùng PDB, probes và graceful shutdown để scale-down không làm rớt request.
- Nên test load và scale-down trước production.
- Tránh bật HPA CPU khi CPU request để quá thấp/chưa có.
- Tránh để autoscaling thay thế capacity planning.

## Performance Considerations

- HPA có delay theo metrics scrape, metrics-server, HPA sync period và app readiness.
- Cluster Autoscaler thêm delay provisioning node; scale từ 0 node pool có thể rất chậm.
- Scale up tăng throughput nhưng cũng tăng connection, cache misses, image pull và cold start.
- Scale down quá nhanh có thể drop in-flight requests nếu termination/graceful shutdown kém.
- CPU limit thấp gây throttling trước khi HPA nhìn thấy đủ tín hiệu.
- HPA theo memory thường scale down chậm vì memory usage không giảm ngay.
- KEDA polling interval và cooldown period ảnh hưởng tốc độ phản ứng với backlog.

## Debugging Checklist

Khi HPA không scale:

```bash
kubectl get hpa -n <namespace>
kubectl describe hpa <name> -n <namespace>
kubectl top pods -n <namespace>
kubectl get deploy <name> -n <namespace> -o yaml
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Kiểm tra:

- Metrics-server có hoạt động không?
- HPA có thấy current metric không hay `<unknown>`?
- Pod có CPU request không?
- Workload có đạt target chưa?
- `minReplicas`/`maxReplicas` đang giới hạn không?
- Scale behavior có stabilization window chặn scale không?

Khi Pod Pending sau scale:

```bash
kubectl get pods -n <namespace>
kubectl describe pod <pending-pod> -n <namespace>
kubectl get nodes
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Kiểm tra:

- Thiếu CPU/memory?
- Node taints/affinity?
- Cluster Autoscaler có chạy không?
- Node pool max size đã đạt chưa?
- PVC topology/storage có block không?

Khi KEDA không scale:

```bash
kubectl get scaledobject -A
kubectl describe scaledobject <name> -n <namespace>
kubectl get hpa -n <namespace>
kubectl logs deploy/keda-operator -n keda
```

Kiểm tra:

- Trigger authentication/secret đúng không?
- Metric query trả giá trị gì?
- Polling interval/cooldown?
- Target deployment name đúng không?

## Liên hệ với kiến thức đã biết

Autoscaling trong Kubernetes giống adaptive capacity trong hệ thống backend, nhưng tín hiệu điều khiển đến từ metrics pipeline và tác động đi qua scheduler/node pool. Với API Gateway, Redis, Kafka, PostgreSQL, bạn phải hỏi: scale layer này có làm bottleneck chuyển sang layer khác không? Tăng replicas app chỉ hữu ích nếu downstream, network, storage và node capacity chịu được.

## Tổng kết

Autoscaling không phải bật HPA là xong. HPA scale replicas dựa trên metric và requests. VPA giúp sizing requests. Cluster Autoscaler scale node khi Pod không có chỗ chạy. KEDA scale theo event/backlog. Production autoscaling tốt cần metric đúng, target đúng, behavior ổn định, downstream protection, capacity headroom và runbook debug metrics/Pending/scale oscillation.

## Câu hỏi tự kiểm tra

1. Vì sao HPA CPU phụ thuộc vào `resources.requests.cpu`?
2. Khi nào queue lag tốt hơn CPU làm scaling metric?
3. Cluster Autoscaler xử lý vấn đề gì mà HPA không xử lý?
4. VPA `Auto` có rủi ro gì với workload latency-sensitive?
5. Vì sao `maxReplicas` nên dựa trên downstream capacity?

## Tài liệu tham khảo

- Kubernetes Horizontal Pod Autoscaling: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- Kubernetes HPA Walkthrough: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/
- Kubernetes Autoscaling v2 API: https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/horizontal-pod-autoscaler-v2/
- Vertical Pod Autoscaler: https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler
- Cluster Autoscaler: https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler
- KEDA Documentation: https://keda.sh/docs/
