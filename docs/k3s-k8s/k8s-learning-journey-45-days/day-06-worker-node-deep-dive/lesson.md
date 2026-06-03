# Day 06: Worker node deep-dive

## Mục tiêu bài học

- Giải thích vai trò của `kubelet`, `kube-proxy`, `container runtime` và `Node` object.
- Mô tả luồng từ Pod đã được schedule đến container chạy thật trên node.
- Biết đọc Node conditions, allocatable resources, taints, leases và events.
- Debug được lỗi phổ biến ở worker node: `ImagePullBackOff`, `CrashLoopBackOff`, `NotReady`, Service routing lỗi.
- Phân biệt worker node trong K3s, Kubernetes chuẩn và managed Kubernetes.

## Vấn đề cần giải quyết

Control plane quyết định desired state, nhưng worker node mới là nơi workload thật sự chạy. Rất nhiều incident production không nằm ở YAML hay API server mà nằm ở node:

- Kubelet không heartbeat làm node `NotReady`.
- Runtime không pull image được.
- CNI không tạo network cho Pod.
- `kube-proxy` hoặc dataplane làm Service không route đúng.
- Disk/memory pressure khiến Pod bị evict.

Nếu chỉ nhìn `kubectl get pods`, bạn sẽ thấy symptom. Muốn fix đúng, cần biết component nào trên node chịu trách nhiệm cho bước nào.

## Mental Model

```text
Scheduler chọn node.
Kubelet trên node đó biến PodSpec thành container thật.
Container runtime pull/start/stop container.
CNI cấp network cho Pod.
kube-proxy/dataplane làm Service VIP route đến Pod endpoints.
Kubelet báo status ngược lại API server.
```

Worker node là execution plane. Nó không tự quyết định desired state toàn cluster, nhưng nó chịu trách nhiệm hiện thực hóa PodSpec trên máy của nó.

Datapath tối giản trên một node:

```text
PodSpec từ API server
        |
      kubelet
        |
        +--> containerd/CRI: pull image, start container
        |
        +--> CNI: cấp Pod IP, route, network namespace
        |
     Pod Ready
        |
EndpointSlice controller cập nhật backend
        |
kube-proxy/dataplane trên mỗi node route Service VIP -> Pod IP
```

## Lý thuyết cốt lõi

### kubelet

`kubelet` chạy trên mỗi node. Nó watch API server để biết Pod nào được gán cho node mình, sau đó:

- Tạo Pod sandbox.
- Gọi container runtime qua `CRI` để pull image và start container.
- Chạy liveness/readiness/startup probes.
- Mount volume/config/secret.
- Thu thập và gửi Pod/Node status về API server.
- Thực thi eviction khi node pressure vượt ngưỡng.

Kubelet là nguồn sự thật runtime cục bộ. Khi Pod không chạy nhưng scheduler đã gán node, hãy đọc `describe pod`, events và kubelet logs.

### container runtime

Kubernetes không gọi Docker CLI để chạy container. Nó nói chuyện với runtime qua `CRI`. K3s mặc định đóng gói `containerd`. Runtime chịu trách nhiệm:

- Pull image.
- Tạo container.
- Start/stop container.
- Quản lý image/container local.
- Cung cấp logs cho kubelet.

Trong K3s, có thể dùng helper:

```bash
sudo k3s crictl ps
sudo k3s crictl images
```

### kube-proxy

`kube-proxy` duy trì network rules trên node để `Service` route traffic đến backend Pod. Tùy cluster, dataplane có thể là `iptables`, `IPVS` hoặc được thay bởi eBPF/CNI nâng cao.

Điểm quan trọng: Service routing phụ thuộc nhiều lớp:

1. Service selector đúng.
2. EndpointSlice có endpoint.
3. kube-proxy/dataplane lập rule đúng trên node.
4. CNI cho phép Pod-to-Pod traffic.
5. NetworkPolicy/firewall không chặn.

### Node object và lifecycle

`Node` là API object đại diện cho worker/control-plane node. Node có:

- `metadata`: labels, annotations.
- `spec`: taints, providerID, unschedulable.
- `status`: capacity, allocatable, addresses, conditions, images.

Node conditions thường gặp:

| Condition | Ý nghĩa |
|---|---|
| `Ready` | Kubelet healthy và node có thể nhận Pod |
| `MemoryPressure` | Node thiếu memory |
| `DiskPressure` | Disk/image filesystem pressure |
| `PIDPressure` | Thiếu process IDs |
| `NetworkUnavailable` | Network chưa sẵn sàng hoặc CNI có vấn đề |

Kubernetes dùng heartbeat và `Lease` object trong namespace `kube-node-lease` để theo dõi node nhanh hơn, nhẹ hơn so với update full Node status liên tục.

Một vài thuật ngữ dễ gặp khi debug node:

| Thuật ngữ | Giải thích ngắn |
|---|---|
| `Lease` | Object heartbeat nhẹ cho node, giúp control plane phát hiện node mất liên lạc nhanh hơn |
| `eviction` | Kubelet buộc Pod rời node khi memory/disk/PID pressure vượt ngưỡng |
| `EndpointSlice` | Object chứa danh sách backend IP/port cho Service, thay thế cách dùng `Endpoints` lớn một khối |
| `dataplane` | Lớp rule/network thực sự chuyển packet, ví dụ `iptables`, `IPVS` hoặc eBPF |

## Deep Dive: Từ scheduled Pod đến container chạy

```text
1. Scheduler bind Pod vào node A bằng spec.nodeName
2. Kubelet node A watch API server thấy Pod mới
3. Kubelet chuẩn bị volume, secret, config
4. Kubelet yêu cầu runtime tạo Pod sandbox
5. CNI plugin cấp network namespace/IP cho Pod
6. Runtime pull image và start containers
7. Kubelet chạy probes
8. Kubelet update Pod status: Pending -> Running/Ready
9. EndpointSlice controller thêm Pod IP vào endpoint nếu readiness pass
10. kube-proxy/dataplane route Service traffic đến endpoint
```

Điểm dễ nhầm: Pod `Running` chưa chắc nhận traffic. Service chỉ nên route đến Pod `Ready` thông qua endpoint readiness.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Runtime | `containerd` packaged mặc định | Tự cài/chọn runtime CRI | Node image/provider addon |
| Kubelet/proxy | Quản lý bởi `k3s` hoặc `k3s-agent` service | systemd/static config tùy setup | Managed node image/bootstrap |
| CNI | Flannel thường là default nếu không đổi | Team chọn CNI | Cloud CNI hoặc addon |
| Node logs | `journalctl -u k3s-agent` hoặc `k3s` | `journalctl -u kubelet`, component logs | Cloud logging/SSM/serial console tùy provider |
| Node upgrade | Team tự upgrade K3s/node | Team tự quản | Managed node group hỗ trợ nhưng team vẫn kiểm soát rollout |
| Debug runtime | `sudo k3s crictl ...` | `crictl`, `ctr` theo socket | Có thể bị giới hạn quyền tùy image/policy |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Node nhỏ nhiều | Workload nhỏ, cần spread/failure isolation | Scheduling linh hoạt, overhead hệ thống nhiều hơn | Cao hơn | Nhiều node cần upgrade/monitor |
| Node lớn ít | Workload nặng, giảm overhead | Bin packing tốt nhưng blast radius lớn | Thấp hơn | Một node mất ảnh hưởng nhiều Pod |
| kube-proxy iptables | Default phổ biến, đơn giản | Rule count lớn có thể ảnh hưởng scale | Thấp | Service latency/rule sync khi rất nhiều Service |
| IPVS/eBPF | Cluster lớn, performance/dataplane nâng cao | Tốt hơn ở một số workload | Trung bình-cao | Debug phức tạp hơn |
| K3s packaged runtime | Lab/edge đơn giản | Nhẹ, tích hợp tốt | Thấp | Cần hiểu path/socket riêng |
| Custom node image | Production chuẩn hóa | Boot nhanh, config nhất quán | Cao | Image drift/patch lifecycle |

### Best Practices

Nên làm:

- Đặt `resources.requests` hợp lý để scheduler không overcommit mù.
- Theo dõi `allocatable`, node pressure, image filesystem và log growth.
- Dùng readiness probe để Service không route đến Pod chưa sẵn sàng.
- Drain node trước maintenance trong production.
- Chuẩn hóa node labels/taints cho workload đặc thù.
- Ghi lại runtime socket, CNI, kube-proxy mode của cluster.

Tránh làm:

- SSH vào node và kill container thủ công như cách fix lâu dài.
- Debug Service routing khi Service chưa có endpoint.
- Bỏ qua Node events và kubelet logs khi Pod đã có `nodeName`.
- Đặt requests quá thấp để "schedule được"; production sẽ trả giá bằng latency/OOM/eviction.

## Performance Considerations

- Image pull là bottleneck lớn khi rollout nhiều Pod hoặc image quá lớn.
- CPU throttling xảy ra khi limits quá thấp so với workload burst.
- Memory pressure có thể gây eviction hoặc `OOMKilled`.
- Disk pressure thường đến từ image cache, container logs, ephemeral storage.
- kube-proxy `iptables` có thể chịu ảnh hưởng khi số Service/Endpoint rất lớn.
- CNI overlay thêm network overhead; cross-node latency thường cao hơn same-node.
- Pod density cao làm kubelet, logging, conntrack và runtime chịu áp lực.

## Debugging Checklist

Incident checklist 5 phút đầu:

1. Xác định blast radius: một Pod, một namespace, một node hay toàn cluster.
2. Kiểm tra Pod đã có `nodeName` chưa để tách lỗi scheduler khỏi lỗi worker node.
3. Đọc `describe pod` và events trước khi restart hoặc xóa Pod.
4. Nếu nhiều Pod lỗi trên cùng node, kiểm tra Node conditions, Lease và kubelet/runtime logs.
5. Nếu Service fail nhưng Pod `Ready`, kiểm tra EndpointSlice trước khi nghi kube-proxy/CNI.

Pod đã schedule nhưng không chạy:

```bash
kubectl describe pod <pod>
kubectl get pod <pod> -o wide
kubectl logs <pod> --previous
kubectl get events --sort-by=.lastTimestamp
```

Node health:

```bash
kubectl describe node <node-name>
kubectl get nodes -o wide
kubectl get lease -n kube-node-lease
kubectl top nodes
kubectl top pods -A
```

Trên K3s worker:

```bash
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -n 200 --no-pager
sudo k3s crictl ps
sudo k3s crictl images
```

Service routing:

```bash
kubectl get svc,endpoints,endpointslice -A
kubectl describe svc <service>
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh
```

Symptom thường gặp:

| Symptom | Lớp nghi ngờ | Root cause phổ biến |
|---|---|---|
| `ImagePullBackOff` | Runtime/registry | Image sai, auth thiếu, network registry lỗi |
| `CrashLoopBackOff` | App/container/probe | Process crash, config sai, probe quá gắt |
| Node `NotReady` | Kubelet/CNI/runtime | Agent down, network lỗi, disk pressure |
| Pod `Running` nhưng Service không vào | Endpoint/kube-proxy/CNI | Readiness fail, selector sai, dataplane lỗi |
| Pod bị evict | Kubelet/node pressure | Disk/memory/ephemeral storage thiếu |

Lab fix thường là sửa manifest hoặc restart agent. Production fix cần bảo toàn workload: cordon/drain, rollback image, tăng capacity, hoặc xử lý registry/CNI/dataplane theo blast radius.

## Liên hệ với kiến thức đã biết

Worker node giống runtime host trong hệ microservices, nhưng có control loop phía trên. Thay vì SSH vào từng host để chạy process, bạn để kubelet hiện thực hóa PodSpec. Các khái niệm quen thuộc như process crash, health check, disk full, network route, image registry vẫn còn nguyên; Kubernetes chỉ chuẩn hóa cách quan sát và reconcile chúng.

## Tóm tắt

Worker node là nơi Kubernetes biến quyết định scheduling thành container thật. `kubelet` quản Pod lifecycle, runtime chạy container, CNI cấp network, `kube-proxy`/dataplane route Service, Node object phản ánh health/capacity. Debug tốt bắt đầu bằng việc xác định Pod đang kẹt ở lớp nào: scheduling, kubelet, runtime, CNI, readiness hay Service routing.

## Câu hỏi tự kiểm tra

1. Scheduler và kubelet khác nhau ở trách nhiệm nào?
2. Vì sao Pod `Running` chưa chắc nhận traffic qua Service?
3. Khi thấy `ImagePullBackOff`, component nào cần kiểm tra trước?
4. Node `NotReady` có thể đến từ những nguyên nhân nào?
5. Trong K3s, vì sao command runtime debug thường dùng `sudo k3s crictl`?

## Tài liệu tham khảo

- Kubernetes Node Components: https://kubernetes.io/docs/concepts/overview/components/
- Kubernetes Nodes: https://kubernetes.io/docs/concepts/architecture/nodes/
- Kubernetes Node Status: https://kubernetes.io/docs/reference/node/node-status/
- Kubernetes Debug Running Pods: https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
- K3s Architecture: https://docs.k3s.io/architecture
