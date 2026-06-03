# Day 11: DaemonSet

## Mục tiêu bài học

- Giải thích `DaemonSet` khác `Deployment` ở chỗ chạy theo node thay vì theo replica count.
- Biết khi nào dùng `DaemonSet` cho log agent, metrics agent, CNI agent, storage agent hoặc node maintenance agent.
- Cấu hình được `nodeSelector`, node affinity, tolerations, `updateStrategy`, resource requests và quyền truy cập host khi cần.
- Hiểu điểm khác nhau giữa K3s, Kubernetes tự quản và managed Kubernetes với node-level components.
- Debug được DaemonSet thiếu Pod, Pod kẹt trên node, rollout lỗi hoặc agent gây áp lực tài nguyên.

## Vấn đề cần giải quyết

Một số workload không nên scale theo "3 replicas" mà phải chạy trên mỗi node đủ điều kiện:

- Log collector cần đọc log container trên từng node.
- Metrics/node exporter cần scrape thông tin node local.
- CNI agent cần cấu hình network trên từng node.
- Storage node agent cần mount/attach disk hoặc quản lý volume trên node.
- Security agent cần quan sát syscall, file hoặc network local.

Nếu dùng `Deployment`, bạn phải tự canh số replicas bằng số node và tự xử lý node mới/node bị xóa. `DaemonSet` để controller làm việc đó.

## Mental Model

```text
Deployment:
  replicas: 3
  -> chạy 3 Pod ở đâu đó trong cluster.

DaemonSet:
  target nodes: tất cả node match selector/affinity/tolerations
  -> mỗi node đủ điều kiện có 1 Pod.
```

`DaemonSet` là "node resident controller". Khi node mới join cluster, controller tạo Pod cho node đó. Khi node bị remove, Pod tương ứng biến mất theo.

## Lý thuyết cốt lõi

### DaemonSet dùng cho workload nào?

Dùng `DaemonSet` khi workload gắn với node:

- Log agent: Fluent Bit, Vector, Filebeat.
- Metrics agent: node-exporter, OpenTelemetry Collector node mode.
- Network agent: CNI plugin như Calico/Cilium.
- Storage agent: Longhorn, Rook/Ceph, CSI node plugin.
- Security/compliance agent: Falco, policy/runtime scanner.
- K3s ServiceLB tạo Pod dạng load balancer trên node cho một số Service `LoadBalancer`.

Không dùng `DaemonSet` cho API service thông thường. Nếu app nhận traffic business và có thể chạy ở bất kỳ node nào, thường dùng `Deployment`.

### Desired number không phải `.spec.replicas`

`DaemonSet` không có `.spec.replicas`. Desired Pod count được tính từ số node đủ điều kiện.

Node đủ điều kiện phụ thuộc chủ yếu vào metadata và scheduling constraints:

- Node có schedulable không.
- Pod template có `nodeSelector` hoặc node affinity không.
- Node có taint nào và Pod có toleration phù hợp không.
- Policy/security có cho phép Pod chạy không.

Resource requests là nuance riêng: nếu node được target nhưng không còn đủ CPU/memory, `desiredNumberScheduled` thường vẫn tính node đó, còn Pod có thể `Pending` với event kiểu `Insufficient cpu` hoặc `Insufficient memory`. Vì vậy khi debug phải đọc cả DaemonSet status lẫn Pod events.

Các command quan trọng:

```bash
kubectl get daemonset -A -o wide
kubectl describe daemonset <name> -n <namespace>
kubectl get pods -l app=<label> -o wide
kubectl get nodes --show-labels
kubectl describe node <node>
```

### Scheduling của DaemonSet

Trong Kubernetes hiện đại, DaemonSet controller tạo Pod với ràng buộc để Pod gắn với một node cụ thể, còn scheduler xử lý placement. Controller cũng tự thêm một số tolerations cần thiết để DaemonSet có thể tồn tại tốt hơn trong các tình huống node condition nhất định.

Bạn vẫn phải thêm tolerations riêng nếu muốn agent chạy trên node có taint custom:

```yaml
tolerations:
- key: "dedicated"
  operator: "Equal"
  value: "infra"
  effect: "NoSchedule"
```

Muốn chỉ chạy trên một nhóm node:

```yaml
nodeSelector:
  node-role: observability
```

Hoặc dùng node affinity khi cần expression phức tạp hơn.

Nuance vận hành:

- DaemonSet có một số tolerations tự động, bao gồm các node condition phổ biến và `node.kubernetes.io/unschedulable`. Vì vậy `kubectl cordon` không phải cách đáng tin cậy để "tắt" DaemonSet trên node; hãy dùng label/affinity/taint custom có chủ đích.
- `kubectl drain` thường yêu cầu `--ignore-daemonsets` và sẽ bỏ qua Pod do DaemonSet quản lý. Khi maintenance node, bạn phải kiểm tra agent còn cần chạy trong giai đoạn drain hay không.
- Resource không fit không làm desired giảm chắc chắn; nó thường tạo Pod `Pending`. Đọc `kubectl describe pod` và events để biết scheduler reject vì tài nguyên hay vì constraint khác.

### Update strategy

Mặc định `DaemonSet` dùng rolling update:

```yaml
updateStrategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1
```

Ý nghĩa: update từng node một hoặc một số node cùng lúc tùy cấu hình. Với agent quan trọng như CNI/logging/security, `maxUnavailable` cần chọn thận trọng.

`OnDelete` nghĩa là template đổi nhưng Pod chỉ được update khi bạn xóa Pod cũ. Strategy này dùng khi node agent cần upgrade thủ công, ví dụ môi trường rất nhạy networking.

### Host access: mạnh nhưng nguy hiểm

Node agent thường cần một số quyền đặc biệt:

- `hostPath` mount log directory hoặc runtime socket.
- `hostNetwork: true` để quan sát network local.
- `privileged: true` hoặc Linux capabilities cho CNI/security/storage.
- ServiceAccount/RBAC để đọc Kubernetes API.

Đây là vùng rủi ro cao. Một DaemonSet privileged chạy trên mọi node gần tương đương quyền root trên cluster node. Production phải review image, RBAC, securityContext, namespace và admission policy rất kỹ.

## Deep Dive: DaemonSet controller làm gì bên trong

```text
1. User apply DaemonSet.
2. Controller liệt kê nodes.
3. Với mỗi node, controller xác định node target dựa trên selector/affinity/tolerations và node state.
4. Nếu node đủ điều kiện mà chưa có Pod, controller tạo Pod cho node đó.
5. Nếu node không còn đủ điều kiện, controller xóa Pod tương ứng.
6. Khi node mới join, controller tạo Pod mới.
7. Khi Pod template đổi, controller rollout theo updateStrategy.
```

Điểm cần nhớ: một DaemonSet Pod fail trên một node không có nghĩa là toàn bộ DaemonSet fail. Debug phải nhìn theo node.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| DaemonSet API | Giống upstream | Giống upstream | Giống upstream |
| System agents | K3s đóng gói nhiều component; một số addon/controller tạo Pod ở `kube-system` | Tùy distro/addon | Cloud/CNI/CSI/node agents thường do cloud addon quản lý |
| CNI | K3s mặc định thường dùng Flannel packaged | Tùy admin cài | Cloud CNI hoặc addon được quản lý |
| LoadBalancer local | K3s có ServiceLB cho lab/small cluster | Không mặc định | Cloud LoadBalancer controller |
| Quyền với node | Dễ test trên lab node | Team chịu trách nhiệm hardening | Một phần node image/addon do cloud quản lý, workload vẫn do team chịu trách nhiệm |

Trong K3s lab, hãy quan sát namespace `kube-system` để thấy cluster dùng những Pod hệ thống nào. Trong managed Kubernetes, nhiều DaemonSet ở `kube-system` là phần sống còn của networking/storage; không patch thủ công nếu không hiểu addon lifecycle.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| `DaemonSet` | Agent cần chạy trên mỗi node | Resource nhân với số node | Trung bình | Agent lỗi ảnh hưởng mọi node |
| `Deployment` | Service stateless không gắn node | Scale linh hoạt | Thấp | Không đảm bảo mỗi node có agent |
| Chạy trên mọi node | Log/metrics/security baseline | Tốn resource toàn cluster | Dễ bao phủ | Node nhỏ bị pressure |
| Chạy subset node | Agent chỉ cần infra node | Ít resource hơn | Cần label/taint discipline | Node thiếu label không có agent |
| Privileged DaemonSet | CNI/storage/security cần quyền host | Có thể ảnh hưởng kernel/network | Cao | Rủi ro bảo mật lớn |
| Non-privileged agent | Log/metrics đơn giản | An toàn hơn | Có thể thiếu visibility | Không đọc được dữ liệu host |
| `maxUnavailable: 1` | Agent critical | Rollout chậm | Dễ kiểm soát | Update lâu với nhiều node |
| `maxUnavailable` cao | Agent không critical | Rollout nhanh | Cần monitoring | Mất coverage tạm thời |

### Best Practices

Nên làm:

- Set `resources.requests` cho mọi DaemonSet vì resource cost nhân theo node count.
- Dùng labels/taints rõ ràng để giới hạn node nếu agent không cần chạy mọi nơi.
- Review `hostPath`, `privileged`, capabilities và RBAC như production security boundary.
- Rollout chậm với CNI/storage/security agent.
- Theo dõi DaemonSet desired/current/ready/available và per-node Pod status.
- Gắn version immutable cho image.
- Document owner của từng DaemonSet trong `kube-system`.

Tránh làm:

- Chạy agent nặng trên control-plane node hoặc node nhỏ nếu không cần.
- Dùng DaemonSet thay cho Deployment vì "muốn nhiều Pod".
- Mount `/` từ host vào container nếu chỉ cần một thư mục cụ thể.
- Patch DaemonSet managed bởi cloud provider hoặc K3s packaged component trực tiếp.
- Bỏ resource requests vì nghĩ agent nhỏ.

## Performance Considerations

- CPU/memory requests của DaemonSet nhân với số node. Agent dùng 100Mi trên 100 nodes là 10Gi reserved.
- Log agent có thể tạo disk I/O và network egress lớn khi traffic tăng.
- Metrics agent scrape quá dày làm tăng CPU và cardinality ở backend.
- CNI/storage agent lỗi có thể ảnh hưởng trực tiếp đến Pod startup hoặc network path.
- Rollout DaemonSet trên cluster lớn cần kiểm soát `maxUnavailable` để không mất observability/security coverage.
- HostPath scan toàn filesystem có thể gây disk pressure hoặc latency spike.

## Debugging Checklist

Thiếu Pod trên một node:

```bash
kubectl get daemonset <name> -n <namespace> -o wide
kubectl describe daemonset <name> -n <namespace>
kubectl get pods -n <namespace> -l app=<label> -o wide
kubectl describe node <node>
```

Pod `Pending`:

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl get nodes --show-labels
kubectl describe node <node>
```

Agent crash:

```bash
kubectl logs <pod> -n <namespace> -c <container>
kubectl logs <pod> -n <namespace> -c <container> --previous
kubectl describe pod <pod> -n <namespace>
```

Rollout lỗi:

```bash
kubectl rollout status daemonset/<name> -n <namespace>
kubectl rollout history daemonset/<name> -n <namespace>
kubectl describe daemonset <name> -n <namespace>
```

Lab fix thường là sửa image/selector/resource rồi apply lại. Production fix cần phân biệt DaemonSet do team sở hữu hay do platform/cloud provider quản lý.

## Liên hệ với kiến thức đã biết

`DaemonSet` giống node-level sidecar nhưng không nằm trong Pod app. Nó gần với agent cài trên VM truyền thống: log shipper, monitoring agent, security agent. Khác biệt là lifecycle được quản lý qua Kubernetes API và controller tự theo node inventory.

## Tóm tắt

`DaemonSet` đảm bảo mỗi node đủ điều kiện có một Pod agent. Nó phù hợp cho logging, monitoring, networking, storage và security agents. Sức mạnh của DaemonSet nằm ở node coverage, nhưng rủi ro cũng lớn vì lỗi hoặc quyền quá rộng có thể ảnh hưởng toàn cluster. Debug DaemonSet luôn bắt đầu bằng câu hỏi: node nào đủ điều kiện, Pod nào đang chạy trên node nào, và agent có cần quyền host nào không?

## Câu hỏi tự kiểm tra

1. Vì sao `DaemonSet` không có `.spec.replicas`?
2. Khi nào một node đủ điều kiện nhưng DaemonSet Pod vẫn không chạy được?
3. `nodeSelector` và tolerations giải quyết hai vấn đề khác nhau thế nào?
4. Vì sao privileged DaemonSet là rủi ro bảo mật lớn?
5. Khi rollout CNI agent, vì sao không nên đặt `maxUnavailable` quá cao?

## Tài liệu tham khảo

- Kubernetes DaemonSet: https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/
- Kubernetes DaemonSet API: https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/daemon-set-v1/
- Kubernetes Taints and Tolerations: https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/
- Kubernetes Assign Pods to Nodes: https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/
- K3s Packaged Components: https://docs.k3s.io/installation/packaged-components
