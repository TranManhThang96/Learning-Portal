# Day 05: Control plane deep-dive

## Mục tiêu bài học

- Giải thích vai trò của `kube-apiserver`, `etcd`, `kube-scheduler`, `kube-controller-manager` và `cloud-controller-manager`.
- Mô tả luồng từ YAML manifest đến Pod được gán node.
- Phân biệt control plane trong K3s, Kubernetes tự dựng và managed Kubernetes.
- Biết kiểm tra health, logs, events và symptoms của control plane.
- Nhận diện bottleneck thường gặp: API latency, datastore disk I/O, scheduler pending queue, controller backlog.

## Vấn đề cần giải quyết

Kubernetes không chạy workload bằng cách "thực thi YAML" trực tiếp. YAML chỉ là request gửi vào API. Control plane lưu desired state, validate, schedule, rồi nhiều controller/kubelet cùng reconcile actual state. Khi control plane chậm hoặc lỗi, mọi thao tác như deploy, scale, rollout, HPA, controller/operator đều bị ảnh hưởng.

Senior engineer cần hiểu control plane đủ sâu để trả lời các câu hỏi production:

- Vì sao `kubectl apply` thành công nhưng Pod vẫn `Pending`?
- Vì sao API server latency tăng làm controller/operator lag?
- Vì sao datastore disk latency có thể làm cả cluster mất ổn định?
- Trong EKS/GKE/AKS, provider quản lý phần nào và team vẫn phải debug phần nào?

## Mental Model

```text
kube-apiserver = cửa API duy nhất
etcd/datastore  = nguồn sự thật của cluster state
scheduler       = chọn node cho Pod chưa được gán node
controllers     = worker nền liên tục kéo actual state về desired state
```

Control plane không "đẩy lệnh" trực tiếp xuống mọi nơi. Phần lớn component `watch` API server, nhận thay đổi state, rồi ghi state mới ngược lại API server. Đây là kiến trúc event-driven dựa trên API object và reconciliation.

## Lý thuyết cốt lõi

### kube-apiserver

`kube-apiserver` expose Kubernetes API. Mọi client và component nói chuyện với cluster gần như đều đi qua API server:

- `kubectl`
- controller
- scheduler
- kubelet
- admission webhook
- operator/CRD controller

API server chịu trách nhiệm authentication, authorization, admission, validation, defaulting, object storage và watch stream. Nếu API server chậm, cả cluster chậm theo, kể cả khi workload đang chạy vẫn phục vụ traffic.

### etcd hoặc datastore

Trong Kubernetes upstream, `etcd` là highly available key-value store cho cluster data. Nó lưu desired state, object metadata, status và nhiều thông tin cần thiết cho reconciliation.

K3s single-node mặc định có thể dùng SQLite để đơn giản hóa lab. K3s HA có thể dùng embedded `etcd` hoặc external datastore. Dù backend là gì, ý tưởng vẫn giống nhau: API server cần datastore ổn định, latency thấp, backup được.

Điểm production quan trọng:

- Disk I/O của datastore ảnh hưởng trực tiếp API latency.
- Backup datastore là backup cluster state, không thay thế backup application data.
- Mất quorum `etcd` trong HA cluster có thể làm control plane không ghi được state mới.

### kube-scheduler

`kube-scheduler` watch các Pod chưa có `spec.nodeName`, đánh giá node dựa trên resource, taint/toleration, affinity, topology và plugin scheduling, rồi bind Pod vào một node.

Scheduler không start container. Nó chỉ chọn node và ghi quyết định vào API server. Kubelet trên node được chọn mới là thành phần start Pod.

### kube-controller-manager

`kube-controller-manager` chạy nhiều controller built-in:

- Deployment/ReplicaSet controller.
- Node controller.
- Job/CronJob controller.
- EndpointSlice controller.
- ServiceAccount/token controller.

Controller liên tục so sánh desired state và actual state. Ví dụ, khi Deployment cần 3 replicas nhưng chỉ có 2 Pod, controller tạo Pod mới. Khi Node mất heartbeat, Node controller cập nhật status và có thể kích hoạt eviction flow tùy điều kiện.

### cloud-controller-manager

`cloud-controller-manager` tách logic phụ thuộc cloud provider ra khỏi core Kubernetes. Trên managed Kubernetes, cloud integration thường xử lý node metadata, route, LoadBalancer, volume hoặc identity theo từng provider. Trong K3s local hoặc bare-metal, bạn thường không có cloud-controller-manager kiểu cloud public; LoadBalancer/storage cần giải pháp riêng như ServiceLB, MetalLB hoặc CSI phù hợp.

## Deep Dive: Cách hoạt động bên trong

```text
1. User chạy kubectl apply -f deployment.yaml
2. kubectl gửi request đến kube-apiserver
3. API server authn/authz/admission/validation
4. API server ghi object vào datastore
5. Deployment controller thấy Deployment mới
6. ReplicaSet controller tạo Pod object
7. Scheduler thấy Pod chưa có nodeName
8. Scheduler chọn node và bind Pod
9. Kubelet trên node watch thấy Pod được gán cho mình
10. Kubelet gọi container runtime để pull image/start container
11. Kubelet update Pod status qua API server
```

Điểm dễ nhầm: `kubectl apply` thành công chỉ chứng minh API server nhận object. Nó chưa chứng minh image pull được, scheduler chọn được node, CNI cấp network được, hay container start thành công.

### API request lifecycle

Một request tạo object thường đi qua chuỗi:

```text
authentication -> authorization -> admission -> validation/defaulting -> persistence -> watch notification
```

Admission có hai nhóm chính: built-in admission plugin và admission webhook. Webhook chậm hoặc unreachable có thể làm `kubectl apply` timeout dù node và workload cũ vẫn khỏe. Vì vậy khi nhiều apply cùng chậm, đừng chỉ nhìn scheduler hoặc kubelet; hãy kiểm tra API latency, webhook và datastore.

### Watch, cache và controller workqueue

Controller không poll toàn bộ API liên tục. Nó dùng watch stream/informer cache để nhận thay đổi, đưa key object vào workqueue, rồi worker xử lý reconcile. Khi xử lý fail, key thường được requeue với rate limit. Hậu quả production:

- API server/watch lỗi làm controller nhìn state cũ hoặc reconnect liên tục.
- Workqueue backlog làm rollout/scale chậm dù node còn tài nguyên.
- Controller retry quá nhanh có thể tăng áp lực API nếu controller/operator viết kém.

### Scheduler phases

Scheduler pipeline hiện đại có nhiều extension point, nhưng mental model thực dụng là:

```text
QueueSort -> Filter -> Score -> Reserve/Permit -> Bind
```

`Filter` loại node không đủ resource, không match taint/toleration, affinity hoặc topology. `Score` xếp hạng node còn lại. `Bind` ghi quyết định vào API server. Nếu không node nào qua `Filter`, Pod ở `Pending` và event thường đã nói lý do.

### Leader election và `Lease`

Nhiều controller/scheduler chạy nhiều replica trong production nhưng chỉ một replica active nhờ leader election. Kubernetes lưu tín hiệu leader trong object `Lease` ở API group `coordination.k8s.io`. Node heartbeat hiện đại cũng dùng `Lease` để giảm tải update trực tiếp lên `Node` object.

```bash
kubectl get lease -A
kubectl -n kube-system get lease
```

Trong K3s single-server, bạn có thể chỉ thấy một số lease ít hơn cluster HA/managed. Vẫn nên biết `Lease` tồn tại vì nó là tín hiệu quan trọng khi debug node heartbeat, leader election hoặc controller failover.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Packaging | `k3s server` đóng gói nhiều component | Component thường tách hơn, hay là static pod | Provider ẩn control plane |
| Datastore | SQLite single-node, embedded etcd hoặc external DB | etcd | Provider quản lý etcd/control plane |
| Logs control plane | `journalctl -u k3s` là nguồn chính | Pod logs/static pod logs/systemd tùy setup | Cloud logging/control plane logs tùy provider |
| Upgrade | Team tự chạy và kiểm soát | Team tự vận hành | Provider hỗ trợ control plane, team vẫn quản node/workload |
| API availability | Phụ thuộc server node/datastore | Phụ thuộc HA thiết kế | SLA/tùy gói provider |
| Debug scope của team | OS + K3s + workload | Toàn bộ cluster | Workload, node, addon, IAM/CNI/CSI, quota |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| SQLite single-node | Lab/small non-HA | Nhẹ, ít overhead | Thấp | Một node hỏng là mất control plane |
| Embedded etcd | K3s HA nhỏ-vừa | Cần disk/network ổn định | Trung bình-cao | Mất quorum, disk latency |
| External datastore | Có DB vận hành tốt sẵn | Phụ thuộc DB latency/HA | Cao | DB outage kéo control plane |
| Managed control plane | Production cloud | API thường ổn định hơn | Trung bình | Cloud quota/IAM/provider outage |
| Self-managed control plane | On-prem/full control | Tùy thiết kế | Cao | Team chịu toàn bộ incident |

### Best Practices

Nên làm:

- Theo dõi API server latency, request errors, watch errors và saturation.
- Backup datastore trước upgrade và định kỳ kiểm tra restore drill.
- Với K3s production, quyết định rõ SQLite/embedded etcd/external datastore theo HA requirement.
- Tách vấn đề "API accepted object" khỏi "workload đã chạy thành công".
- Khi Pod `Pending`, kiểm tra scheduler events trước khi đụng kubelet/runtime.

Tránh làm:

- Xem `kubectl apply` success là deploy success.
- Chạy datastore trên disk chậm hoặc không có monitoring.
- Sửa trực tiếp object status để "fix" controller symptom.
- Bỏ qua events; scheduler/controller thường đã ghi lý do vào events.

## Performance Considerations

- API server là shared bottleneck. Controller, operator, CI/CD và user đều dùng cùng API.
- Watch-heavy workload hoặc quá nhiều CRD/operator có thể tăng áp lực lên API server và datastore.
- Datastore disk latency cao làm write/read state chậm, gây controller lag.
- Scheduler thường không phải bottleneck đầu tiên trong cluster nhỏ, nhưng có thể nghẽn khi có quá nhiều pending Pod, affinity phức tạp hoặc topology constraints nặng.
- Controller backlog làm rollout/scale chậm dù node vẫn còn tài nguyên.
- Admission webhook chậm hoặc lỗi có thể làm API request timeout, kể cả khi control plane core khỏe.

## Debugging Checklist

Khi nghi control plane có vấn đề:

```bash
kubectl get --raw='/readyz?verbose'
kubectl get --raw='/livez?verbose'
kubectl get nodes -o wide
kubectl get pods -A
kubectl get events -A --sort-by=.lastTimestamp
kubectl get lease -A
```

Kiểm tra API object và scheduling:

```bash
kubectl describe pod <pod>
kubectl get pod <pod> -o yaml
kubectl get deployment,rs,pod
kubectl get endpoints kubernetes
```

Trên K3s server:

```bash
sudo systemctl status k3s
sudo journalctl -u k3s -n 200 --no-pager
sudo ls -lh /var/lib/rancher/k3s/server/
```

Symptom thường gặp:

| Symptom | Lớp nghi ngờ | Kiểm tra đầu tiên |
|---|---|---|
| `kubectl` timeout | API server/network/datastore | `/readyz`, `journalctl -u k3s` |
| Pod `Pending` | Scheduler/resource/taint | `kubectl describe pod` events |
| Deployment không tạo Pod | Controller manager/admission/quota | `kubectl describe deploy`, events |
| Apply chậm hàng loạt | API latency/admission/datastore | API health, logs, webhook state |
| Node biến `NotReady` | Node controller/kubelet/network | `describe node`, kubelet logs |

Lab fix có thể là restart K3s hoặc giảm workload. Production fix cần xác định bottleneck, tránh restart mù, kiểm tra datastore health và bảo toàn API availability.

## Liên hệ với kiến thức đã biết

Control plane giống một hệ thống event-sourcing/reconciliation cho hạ tầng. API server là public API, datastore là state store, controller là background worker, scheduler là decision engine. Nếu bạn từng vận hành microservices với queue/worker, hãy áp dụng cùng tư duy: request accepted không đồng nghĩa job đã xử lý xong; cần quan sát queue, worker, state transition và failure reason.

## Tóm tắt

Control plane là nơi Kubernetes lưu, kiểm tra và điều phối desired state. API server nhận và phục vụ API, datastore lưu state, scheduler chọn node, controller kéo actual state về desired state. Trong K3s, các thành phần được đóng gói gọn hơn; trong managed Kubernetes, provider quản control plane nhưng team vẫn phải hiểu symptoms để debug workload, node, addon và cloud integration.

## Câu hỏi tự kiểm tra

1. `kubectl apply` success chứng minh điều gì và chưa chứng minh điều gì?
2. Scheduler làm gì, và không làm gì?
3. Vì sao datastore disk latency ảnh hưởng đến toàn cluster?
4. Khi Pod `Pending`, bạn đọc object nào trước?
5. Managed Kubernetes giúp giảm trách nhiệm nào, và không giúp phần nào?

## Tài liệu tham khảo

- Kubernetes Components: https://kubernetes.io/docs/concepts/overview/components/
- Kubernetes Control Plane-Node Communication: https://kubernetes.io/docs/concepts/architecture/control-plane-node-communication/
- Kubernetes Debugging Clusters: https://kubernetes.io/docs/tasks/debug/debug-cluster/
- K3s Architecture: https://docs.k3s.io/architecture
- K3s Datastore Options: https://docs.k3s.io/datastore
