# Day 09: ReplicaSet và Deployment

## Mục tiêu bài học

- Giải thích vai trò của `ReplicaSet` và vì sao thường không quản lý trực tiếp ReplicaSet.
- Hiểu cách `Deployment` tạo ReplicaSet, rollout Pod template mới và rollback revision cũ.
- Cấu hình được rolling update bằng `maxSurge`, `maxUnavailable`, `minReadySeconds`, `progressDeadlineSeconds`.
- Dùng `kubectl rollout status/history/undo/pause/resume` để vận hành release.
- Debug được rollout kẹt do image lỗi, readiness fail, resource thiếu hoặc selector sai.

## Vấn đề cần giải quyết

Production workload stateless cần nhiều hơn việc "chạy 3 Pod":

- Nếu Pod chết, hệ thống phải tạo Pod thay thế.
- Khi deploy version mới, traffic không được rơi vào version chưa sẵn sàng.
- Nếu image mới lỗi, cần rollback nhanh.
- Nếu rollout kẹt, cần biết kẹt ở ReplicaSet, Pod readiness, scheduler hay image pull.
- Release cần có lịch sử và audit đủ tốt để điều tra.

`Deployment` là abstraction chính cho stateless service trên Kubernetes vì nó quản lý replica count, rollout và rollback thông qua ReplicaSet.

## Mental Model

```text
Deployment = release controller.
ReplicaSet = replica-count controller cho một Pod template cụ thể.
Pod = runtime instance.

Deployment tạo ReplicaSet mới khi Pod template đổi.
ReplicaSet mới scale up.
ReplicaSet cũ scale down theo rolling update strategy.
Nếu lỗi, Deployment có thể rollback về ReplicaSet/revision trước.
```

Bạn thao tác với Deployment. ReplicaSet là bằng chứng lịch sử của các Pod template đã từng được rollout.

## Lý thuyết cốt lõi

### ReplicaSet

`ReplicaSet` đảm bảo số Pod khớp `.spec.replicas` dựa trên selector.

Các phần quan trọng:

```yaml
apiVersion: apps/v1
kind: ReplicaSet
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: nginx:1.27
```

Selector phải khớp labels trong Pod template. Nếu không, API thường reject hoặc controller không quản đúng Pod.

Trong thực tế, bạn hiếm khi tạo ReplicaSet trực tiếp. Dùng Deployment để có rollout/rollback.

### Deployment

Deployment quản lý desired state của stateless workload. Khi Pod template thay đổi, ví dụ image/probe/env/resource, Deployment tạo ReplicaSet mới.

Command phổ biến:

```bash
kubectl apply -f deployment.yaml
kubectl get deployment
kubectl describe deployment web
kubectl set image deployment/web web=nginx:1.28
kubectl rollout status deployment/web
kubectl rollout history deployment/web
kubectl rollout undo deployment/web
kubectl scale deployment/web --replicas=5
```

Lưu ý: thay đổi `.spec.replicas` không tạo revision mới. Thay đổi Pod template mới tạo rollout revision.

### Rolling update strategy

Mặc định Deployment dùng `RollingUpdate`.

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
minReadySeconds: 5
progressDeadlineSeconds: 120
```

Ý nghĩa:

- `maxSurge`: số Pod vượt quá replicas mong muốn trong rollout.
- `maxUnavailable`: số Pod có thể unavailable trong rollout.
- `minReadySeconds`: Pod phải ready liên tục bao lâu mới được tính available.
- `progressDeadlineSeconds`: thời gian tối đa rollout không progress trước khi báo failed.

Ví dụ replicas=4, `maxSurge=1`, `maxUnavailable=0`: rollout có thể chạy tối đa 5 Pod, nhưng luôn giữ 4 Pod available nếu readiness đúng.

Cách tính capacity nhanh:

```text
peakPods = replicas + maxSurge
minAvailableDuringRollout = replicas - maxUnavailable
peakRequestedCPU = peakPods * requestCPUPerPod
peakRequestedMemory = peakPods * requestMemoryPerPod
```

Với replicas=3, request `50m` CPU và `64Mi` memory, `maxSurge=1` cần đủ chỗ cho 4 Pod, tức khoảng `200m` CPU và `256Mi` memory chỉ riêng workload này. Nếu cluster không còn headroom, rollout sẽ kẹt `Pending` dù manifest đúng.

### Rollout history và rollback

Deployment giữ revision history qua ReplicaSets cũ.

```bash
kubectl rollout history deployment/web
kubectl rollout history deployment/web --revision=2
kubectl rollout undo deployment/web
kubectl rollout undo deployment/web --to-revision=2
```

Để history có ý nghĩa hơn:

```bash
kubectl annotate deployment web kubernetes.io/change-cause="update nginx to 1.28"
```

Production tốt hơn là dùng Git commit, image digest, CI metadata và GitOps audit thay cho annotation thủ công.

### Pause và resume

`pause` giúp gom nhiều thay đổi Pod template thành một revision:

```bash
kubectl rollout pause deployment/web
kubectl set image deployment/web web=nginx:1.28
kubectl set resources deployment/web -c=web --requests=cpu=50m,memory=64Mi
kubectl rollout resume deployment/web
kubectl rollout status deployment/web
```

Không để Deployment paused quá lâu trong production vì bạn có thể nhầm tưởng thay đổi đã rollout.

## Deep Dive: Deployment controller làm gì bên trong

```text
1. User đổi Deployment Pod template.
2. Deployment controller tính hash mới cho template.
3. Controller tạo ReplicaSet mới với label pod-template-hash.
4. ReplicaSet mới scale up theo maxSurge/maxUnavailable.
5. ReplicaSet cũ scale down khi Pod mới available.
6. Deployment status cập nhật updatedReplicas, readyReplicas, availableReplicas.
7. ReplicaSets cũ được giữ theo revisionHistoryLimit để rollback.
```

Rollout "kẹt" không phải lúc nào cũng do Deployment controller. Nó có thể kẹt vì:

- Scheduler không đặt được Pod do resource/taint/affinity.
- Runtime không pull được image.
- App crash.
- Readiness probe fail.
- Quota/LimitRange/Policy reject Pod.

Deployment chỉ phản ánh tiến độ; root cause thường nằm trong Pod events.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Deployment/ReplicaSet API | Giống upstream | Giống upstream | Giống upstream |
| Image pull | Qua containerd packaged | Tùy runtime/registry config | Tùy node image, IAM, private registry integration |
| Service exposure sau rollout | K3s có Traefik/ServiceLB nếu dùng Ingress/LB | Tùy addon | Cloud LB/Ingress controller |
| Capacity khi surge | Bị giới hạn bởi lab node nhỏ | Tùy node pool | Node autoscaler/node group có thể scale |
| Rollback app | `kubectl rollout undo` giống nhau | Giống nhau | Giống nhau, nhưng CI/GitOps/IAM audit khác |

K3s single-node dễ thiếu resource khi `maxSurge` cao. Managed Kubernetes có thể có autoscaler, nhưng surge vẫn cần requests đúng và quota đủ.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Deployment | Stateless service | Rollout/scale tốt | Thấp-trung bình | Không giữ identity/storage ổn định |
| ReplicaSet trực tiếp | Học controller behavior, case rất đặc biệt | Ít abstraction hơn | Không có rollout/rollback | Update thủ công dễ lỗi |
| `maxUnavailable=0` | Cần availability cao | Cần thêm capacity cho surge | Cần tính resource | Rollout kẹt nếu không đủ capacity |
| `maxUnavailable>0` | Chấp nhận giảm capacity tạm thời | Ít cần surge capacity | Dễ hơn với cluster nhỏ | Có thể giảm throughput |
| Image tag mutable | Lab nhanh | Pull behavior khó đoán | Thấp | Rollback/audit mơ hồ |
| Image digest/immutable tag | Production | Predictable | Cần CI discipline | Registry cleanup cần quản |
| Rollback bằng kubectl | Incident nhanh | Nhanh | Có thể lệch Git | GitOps sync lại version lỗi nếu không sửa Git |

### Best Practices

Nên làm:

- Dùng Deployment cho stateless microservices.
- Đặt readiness probe trước khi tin rolling update an toàn.
- Set `resources.requests` để scheduler tính capacity đúng.
- Dùng image tag immutable hoặc digest trong production.
- Theo dõi `rollout status`, `describe deployment`, Pod events và metrics sau release.
- Giữ `revisionHistoryLimit` đủ để rollback gần nhất nhưng không quá lớn.
- Với production, rollback cần cập nhật cả Git/CI/GitOps source of truth.

Tránh làm:

- Tạo Pod hoặc ReplicaSet trực tiếp cho service production thông thường.
- Dùng `latest` tag.
- Set `maxUnavailable` quá cao với service ít replica.
- Bỏ readiness probe rồi tin rằng rolling update không drop traffic.
- Xóa ReplicaSet cũ khi chưa hiểu rollback requirement.
- Dùng `kubectl edit` để hotfix rồi quên đồng bộ Git.

## Performance Considerations

- `maxSurge` tăng tạm thời CPU/memory/network usage; cluster nhỏ có thể không schedule nổi Pod mới.
- Image pull trong rollout nhiều replica tạo tải registry và disk I/O trên node.
- Readiness delay dài làm rollout chậm nhưng bảo vệ traffic.
- `minReadySeconds` giúp tránh Pod vừa ready đã fail, đổi lại rollout lâu hơn.
- Rollback vẫn cần pull image cũ nếu node không còn cache.
- Nhiều ReplicaSet history không lớn về runtime, nhưng làm API output và cleanup phức tạp hơn.
- Scale replicas nhanh có thể tạo burst đến downstream database/cache; Kubernetes không biết app dependency limit nếu bạn không thiết kế.

## Debugging Checklist

Rollout kẹt:

```bash
kubectl rollout status deployment/<name>
kubectl describe deployment <name>
kubectl get rs,pod -l app=<label> -o wide
kubectl get events --sort-by=.lastTimestamp
```

Pod mới không ready:

```bash
kubectl describe pod <pod>
kubectl logs <pod> -c <container> --previous
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses}{"\n"}'
```

Rollback:

```bash
kubectl rollout history deployment/<name>
kubectl rollout undo deployment/<name>
kubectl rollout status deployment/<name>
```

Capacity/scheduling:

```bash
kubectl describe pod <pending-pod>
kubectl describe node <node>
kubectl top nodes
kubectl top pods
```

## Liên hệ với kiến thức đã biết

Deployment tương tự release manager cho stateless service. ReplicaSet giống process supervisor theo replica count. Rolling update giống thay instance trong load balancer từng bước, readiness giống health check của load balancer, rollback giống revert release artifact. Điểm khác là Kubernetes quản lý bằng API objects và controllers, không bằng script deploy tuyến tính.

## Tóm tắt

ReplicaSet giữ số Pod của một template. Deployment quản lý ReplicaSet để rollout, rollback và scale stateless workload. Rollout an toàn phụ thuộc vào readiness probe, resource capacity, image discipline và quan sát events. Khi rollout fail, đọc Deployment status để biết tiến độ, nhưng đọc Pod events/logs để tìm root cause.

## Câu hỏi tự kiểm tra

1. Vì sao production thường dùng Deployment thay vì ReplicaSet trực tiếp?
2. Thay đổi field nào của Deployment tạo revision mới?
3. `maxSurge=1` và `maxUnavailable=0` có trade-off gì?
4. Rollout kẹt do readiness fail thì kiểm tra command nào?
5. Rollback bằng `kubectl rollout undo` cần lưu ý gì trong GitOps?

## Tài liệu tham khảo

- Kubernetes Deployments: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Kubernetes ReplicaSet: https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/
- kubectl rollout: https://kubernetes.io/docs/reference/kubectl/generated/kubectl_rollout/
- Kubernetes Debug Running Pods: https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
- Kubernetes Images: https://kubernetes.io/docs/concepts/containers/images/
