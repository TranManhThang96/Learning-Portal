# Day 01: Kubernetes Mental Model và Container Runtime Refresher

## Mục tiêu bài học

- Giải thích được Kubernetes giải quyết vấn đề gì mà Docker Compose hoặc script deploy thủ công không giải quyết tốt.
- Dựng được local lab tối thiểu bằng `k3d`, Docker và `kubectl` để học ngay từ ngày đầu.
- Mô tả được desired state, actual state và reconciliation loop trong Kubernetes.
- Phân biệt vai trò của `Pod`, `Deployment`, `Service`, `OCI`, `CRI` và `containerd`.
- Đọc được một manifest đơn giản và dự đoán Kubernetes sẽ tạo những object nào.
- Biết debug bước đầu khi một workload không chạy đúng desired state.

## Vấn đề cần giải quyết

Khi hệ thống chỉ có vài container trên một máy, Docker Compose đủ tiện: khai báo service, network, volume rồi start. Nhưng microservices production gặp các vấn đề khác:

- Một container chết cần được thay thế tự động.
- Traffic cần đi tới instance còn sống, không phụ thuộc IP động của container.
- Rollout cần có kiểm soát, rollback được, không làm rơi toàn bộ traffic.
- Scheduler cần quyết định workload chạy ở node nào dựa trên tài nguyên và policy.
- Team vận hành cần quan sát trạng thái thật của hệ thống qua một API nhất quán.

Kubernetes là control system cho containerized workloads. Bạn không chủ yếu "chạy container"; bạn khai báo trạng thái mong muốn, và nhiều controller trong cluster liên tục kéo trạng thái thật về gần trạng thái đó.

## Local Lab Mặc Định Cho Lộ Trình

Để ngày đầu không bị kẹt vì chưa có cluster, lộ trình này dùng `k3d` làm môi trường local mặc định. `k3d` chạy K3s bên trong Docker container, nên tạo/xóa cluster nhanh, ít phá máy thật, và đủ để học `Pod`, `Deployment`, `Service`, `Ingress`, events và object lifecycle.

Phân biệt rõ:

| Mục tiêu | Công cụ nên dùng | Vì sao |
|---|---|---|
| Day 1-3, học mental model và object cơ bản | `k3d` + Docker + `kubectl` | Tạo cluster nhanh, reset dễ, chạy tốt trên laptop |
| Day 4, hiểu K3s server/agent thật | K3s cài trực tiếp trên Linux VM | Thấy `systemd`, kubeconfig thật, node token, agent join |
| CI/test manifest | Kind hoặc `k3d` ephemeral cluster | Tái lập nhanh, dễ tạo/xóa trong pipeline |
| Production cloud | EKS/GKE/AKS hoặc K3s/self-managed tùy bối cảnh | Cần HA, upgrade, security, observability và ownership rõ ràng |

Bootstrap local lab tối thiểu:

```bash
docker version
kubectl version --client
k3d version

k3d cluster create k8s-lab --api-port 6550 -p "8080:80@loadbalancer"
kubectl cluster-info
kubectl get nodes -o wide
kubectl get pods -A
```

Nếu máy đủ tài nguyên và muốn thấy worker node riêng ngay từ đầu, có thể thêm `--agents 1` khi tạo cluster. Nếu chỉ học Day 1, single-node là đủ.

## Mental Model

Hãy nhìn Kubernetes như một vòng điều khiển:

```text
User/YAML
   |
   v
Kubernetes API server ----> etcd lưu desired state
   |
   v
Controllers/Scheduler/Kubelet quan sát actual state
   |
   v
Tạo/sửa/xóa runtime objects cho tới khi actual ~= desired
```

Điểm quan trọng: `kubectl apply` không đồng nghĩa với "container đã chạy". Nó chỉ gửi desired state vào API server. Sau đó scheduler, controller và kubelet mới lần lượt xử lý.

Ví dụ:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: nginx
          image: nginx:1.27
          ports:
            - containerPort: 80
```

Manifest này không nói "hãy chạy lệnh docker run hai lần". Nó nói: "cluster phải có 2 `Pod` thuộc template này". `Deployment controller` tạo `ReplicaSet`, `ReplicaSet controller` đảm bảo số `Pod`, scheduler gán `Pod` vào node, kubelet ở node gọi container runtime để chạy container.

## Lý thuyết cốt lõi

### Desired state và actual state

Desired state là trạng thái bạn khai báo qua Kubernetes API. Actual state là trạng thái thật đang xảy ra: node có sẵn không, image pull được không, container có crash không, readiness có pass không.

Kubernetes không hứa mọi thứ thành công ngay lập tức. Nó hứa các controller sẽ tiếp tục quan sát và điều chỉnh. Đây là khác biệt lớn với script imperative kiểu:

```bash
docker run nginx
```

Imperative command thường thất bại rồi dừng. Declarative API cho phép retry, convergence, drift correction và audit qua object state.

### `Pod`

`Pod` là đơn vị scheduling nhỏ nhất trong Kubernetes. Một `Pod` có thể chứa một hoặc nhiều container chia sẻ network namespace và một số volume. Với app thông thường, một `Pod` thường có một container chính; multi-container dùng cho pattern như sidecar sẽ học ở ngày 8.

Điểm cần nhớ:

- IP gắn với `Pod`, không gắn với container riêng lẻ.
- `Pod` là disposable. Khi bị xóa, Kubernetes thường tạo `Pod` mới với tên/IP khác nếu nó thuộc controller như `Deployment`.
- Không nên deploy production bằng `Pod` trần, vì không có rollout, replica management và self-healing tốt như `Deployment`.

### `Deployment`

`Deployment` quản lý rollout stateless workload. Nó tạo `ReplicaSet`, rồi `ReplicaSet` tạo `Pod`. Khi đổi image hoặc template, `Deployment` tạo `ReplicaSet` mới và giảm dần `ReplicaSet` cũ theo strategy.

Đây là object mặc định cho API service, worker stateless, frontend và hầu hết service không cần identity ổn định.

### `Service`

`Service` cung cấp endpoint ổn định cho một nhóm `Pod` được chọn bằng label selector. Vì `Pod` có thể chết và sinh lại với IP mới, client không nên gọi trực tiếp Pod IP.

`Service` giải quyết service discovery và load balancing nội bộ ở mức L4. Ingress, gateway hoặc service mesh sẽ xử lý các bài toán HTTP routing nâng cao hơn ở các ngày sau.

### `OCI`, `CRI`, `containerd`

`OCI` là bộ chuẩn cho image format và runtime behavior. `CRI` là interface để kubelet nói chuyện với container runtime. `containerd` là container runtime phổ biến mà Kubernetes và K3s dùng để pull image, tạo container, quản lý lifecycle.

Trong Kubernetes hiện đại, kubelet không cần Docker Engine để chạy container. Nó làm việc với runtime qua `CRI`. Docker vẫn hữu ích để build image hoặc chạy local, nhưng không còn là runtime mặc định bên trong nhiều cluster.

Kiểm chứng runtime thật trên cluster bằng:

```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,RUNTIME:.status.nodeInfo.containerRuntimeVersion,KUBELET:.status.nodeInfo.kubeletVersion
kubectl describe node <node-name>
```

Với K3s/k3d, bạn thường thấy runtime dạng `containerd://...`. Đây là tín hiệu quan trọng khi debug lỗi image pull, sandbox creation hoặc khác biệt giữa Docker local và runtime trong cluster.

## Deep Dive: Cách hoạt động bên trong

Luồng tối giản khi apply một `Deployment`:

```text
1. kubectl gửi HTTP request tới kube-apiserver.
2. kube-apiserver validate object, chạy admission, rồi lưu object vào etcd.
3. Deployment controller thấy Deployment mới, tạo ReplicaSet.
4. ReplicaSet controller thấy thiếu Pod, tạo Pod objects.
5. Scheduler thấy Pod chưa có nodeName, chọn node phù hợp.
6. Kubelet trên node nhận PodSpec, gọi container runtime qua CRI.
7. containerd pull image, tạo container, report status.
8. Controller tiếp tục quan sát để giữ số replicas đúng.
```

Mọi bước đều có trạng thái trung gian. Vì vậy debugging Kubernetes là đọc object state theo chuỗi, không chỉ đọc log app.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | Kubernetes chuẩn | K3s | Managed Kubernetes |
|---|---|---|---|
| Packaging | Nhiều binary/component tách rời | Single binary, control plane đóng gói gọn | Cloud provider quản lý control plane |
| Runtime | Thường dùng `containerd` hoặc CRI-compatible runtime | Bundled `containerd` | Provider cấu hình runtime/node image |
| Networking mặc định | Tùy CNI bạn cài | Thường đi kèm Flannel | Cloud CNI hoặc CNI provider |
| Ingress mặc định | Không luôn có sẵn | Thường có Traefik packaged component | Tùy cloud/addon |
| Storage lab | Tùy StorageClass | Thường có `local-path-provisioner` | Cloud CSI như EBS/GCE PD/Azure Disk |
| Vận hành control plane | Team tự quản | Team tự quản nhưng đơn giản hơn | Provider quản lý phần lớn |

Best solution theo bối cảnh:

- Learning environment: `k3d` là lựa chọn mặc định cho Day 1 vì nhanh, dễ reset và chạy K3s thật trong Docker. K3s cài trực tiếp trên Linux/VM sẽ học ở Day 4.
- Small production: K3s có thể hợp lý nếu team chấp nhận tự vận hành backup, upgrade, monitoring và security.
- Medium/large production: ưu tiên managed Kubernetes nếu workload chạy trên cloud và team không muốn tự gánh control plane.
- On-premise/edge: K3s phù hợp nhờ footprint thấp và vận hành đơn giản hơn upstream Kubernetes tự dựng.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Docker Compose | Dev local đơn máy, dependency đơn giản | Nhẹ, startup nhanh | Thấp | Không có scheduler/self-healing cluster-level |
| `k3d` | Học local Kubernetes/K3s, demo, reset nhanh | Phụ thuộc Docker, footprint thấp | Thấp | Networking/storage là mô phỏng containerized, không giống hoàn toàn production |
| Kubernetes `Deployment` | Stateless service cần replica, rollout, self-healing | Overhead control plane nhưng scale tốt | Trung bình | Misconfig selector/probe/resource gây rollout lỗi |
| `Pod` trần | Test nhanh, debug ngắn hạn | Ít object hơn | Thấp nhưng thiếu quản trị | Pod chết không tự phục hồi theo ý muốn |
| K3s | Lab, edge, small cluster | Footprint thấp | Thấp hơn upstream tự dựng | Packaged defaults có thể khác production cloud |

### Best Practices

Nên làm:

- Dùng `Deployment` cho stateless service thay vì `Pod` trần.
- Luôn đặt label rõ ràng: `app`, `component`, `part-of`, `env`.
- Debug theo chuỗi object: `Deployment` -> `ReplicaSet` -> `Pod` -> container -> events.
- Treat `Pod` as disposable; không lưu state quan trọng trong container filesystem.

Tránh làm:

- Gọi trực tiếp Pod IP từ service khác.
- Nhầm `kubectl apply` thành "deploy đã thành công".
- Dùng `latest` image tag cho lab nghiêm túc hoặc production.
- Fix production bằng cách sửa tay object runtime mà không cập nhật source-of-truth.

## Performance Considerations

- Kubernetes thêm overhead điều phối, nhưng đổi lại có self-healing, scaling, rollout và API nhất quán.
- Startup latency gồm scheduling, image pull, container create và readiness. Image lớn hoặc registry chậm làm rollout lâu.
- Không đặt `resources.requests` khiến scheduler thiếu tín hiệu để phân bổ tốt; đặt quá cao làm `Pod` bị `Pending`.
- `Service` thêm một lớp routing nội bộ; thường nhỏ, nhưng debugging latency cần xét kube-proxy/CNI ở các ngày networking.
- Với K3s lab, node đơn dễ bị nghẽn CPU/RAM nếu chạy nhiều addon, observability stack hoặc database.

## Debugging Checklist

- Kiểm tra object có được tạo chưa:

```bash
kubectl get deploy,rs,pod,svc
```

- Nếu `Pod` không chạy:

```bash
kubectl describe pod <pod-name>
kubectl get events --sort-by=.lastTimestamp
kubectl logs <pod-name> -c <container-name>
```

- Nếu nghi lỗi liên quan runtime/image pull:

```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,RUNTIME:.status.nodeInfo.containerRuntimeVersion
kubectl describe node <node-name>
```

- Nếu replicas không đúng:

```bash
kubectl describe deployment <deployment-name>
kubectl get rs -l app=<app>
```

- Symptom thường gặp:

| Symptom | Root cause phổ biến | Lab fix | Production fix |
|---|---|---|---|
| `ImagePullBackOff` | Sai image/tag, registry auth lỗi | Sửa image tag | Kiểm tra CI push, registry secret, rollback |
| `CrashLoopBackOff` | App exit, env thiếu, command sai | Đọc logs, sửa env | Rollback, feature flag, config validation |
| `Pending` | Thiếu resource, node selector sai | Giảm requests | Scale node pool, sửa scheduling policy |
| Service không route | Label selector không match Pod | Sửa label/selector | Thêm test manifest, policy review |

## Liên hệ với kiến thức đã biết

Nếu đã quen microservices, hãy map như sau:

- API Gateway gọi service name thay vì IP instance.
- Redis/Kafka/Postgres cần cân nhắc state, storage và identity, không giống stateless API.
- Observability không chỉ là app logs; cần events, object status, node metrics và rollout history.
- Reconciliation giống một background worker liên tục so sánh desired state với actual state.

## Tóm tắt

Kubernetes là declarative control plane cho container workloads. Bạn khai báo desired state qua API, còn controller, scheduler và kubelet phối hợp để đưa cluster về trạng thái đó. `Pod` là đơn vị chạy nhỏ nhất, `Deployment` là abstraction thực tế cho stateless rollout, `Service` cung cấp endpoint ổn định. Trong lộ trình này, `k3d` là cách nhanh nhất để có lab K3s local ở Day 1; K3s cài trực tiếp trên Linux/VM sẽ được tách riêng ở Day 4 để học vận hành thật hơn.

## Câu hỏi tự kiểm tra

1. Vì sao `kubectl apply` thành công không đồng nghĩa ứng dụng đã sẵn sàng nhận traffic?
2. `Deployment` tạo ra những object nào phía dưới?
3. Khi nào dùng `Pod` trần là hợp lý, và vì sao không nên dùng cho production service?
4. `CRI` giải quyết quan hệ nào giữa kubelet và container runtime?
5. Vì sao Day 1 dùng `k3d`, còn Day 4 mới cài K3s trực tiếp trên Linux/VM?

## Tài liệu tham khảo

- Kubernetes Components: https://kubernetes.io/docs/concepts/overview/components/
- Kubernetes Workloads: https://kubernetes.io/docs/concepts/workloads/
- Kubernetes Services: https://kubernetes.io/docs/concepts/services-networking/service/
- kubectl Reference: https://kubernetes.io/docs/reference/kubectl/
- K3s Introduction: https://docs.k3s.io/
- k3d Documentation: https://k3d.io/
