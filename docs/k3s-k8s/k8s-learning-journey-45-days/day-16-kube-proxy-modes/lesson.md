# Day 16: kube-proxy modes

## Mục tiêu bài học

- Hiểu `kube-proxy` nằm ở đâu trong luồng traffic của `Service`.
- Phân biệt `iptables`, `IPVS` và eBPF-based dataplane khi triển khai Service routing.
- Biết cách kiểm tra mode thực tế của cluster thay vì đoán theo distro.
- Hiểu các bottleneck liên quan đến rule count, endpoint churn, `conntrack` và cross-node traffic.
- Debug được lỗi Service routing ở lớp dataplane trước khi đổ lỗi cho application.

## Vấn đề cần giải quyết

Day 15 đã học `Service` là stable virtual frontend. Nhưng `Service` không tự forward packet. Cần một dataplane trên từng node biến `ClusterIP`, `NodePort` và một phần `LoadBalancer` thành rule thật trong kernel.

Trong Kubernetes upstream, thành phần phổ biến nhất làm việc này là `kube-proxy`. Trong các cluster hiện đại, vai trò đó có thể được thay thế bởi eBPF dataplane như Cilium. Nếu không hiểu lớp này, bạn sẽ thấy Service có endpoints đầy đủ nhưng traffic vẫn timeout, latency tăng, mất source IP hoặc routing lệch node.

## Mental Model

```text
Service/EndpointSlice thay đổi
  |
  v
kube-proxy hoặc eBPF agent watch Kubernetes API
  |
  v
Program node-local dataplane rules
  |
  v
Packet tới ClusterIP/NodePort được DNAT/load balance tới Pod IP
```

`kube-proxy` không phải reverse proxy L7. Nó không đọc HTTP path/header, không terminate TLS và không hiểu application protocol. Nó chủ yếu cấu hình kernel networking để traffic L4 đi đúng backend.

## Lý thuyết cốt lõi

### kube-proxy làm gì

`kube-proxy` watch `Service` và `EndpointSlice` qua API server. Khi danh sách Service hoặc backend Pod đổi, nó cập nhật rule trên node.

Các trách nhiệm chính:

- Cài rule cho `ClusterIP`.
- Cài rule cho `NodePort`.
- Hỗ trợ external traffic path cho `LoadBalancer` tùy provider.
- Load balance L4 tới endpoint đang Ready.
- Tôn trọng một số field như `sessionAffinity` và `externalTrafficPolicy`.

Điểm dễ nhầm: `kube-proxy` không quyết định Pod nào Ready. EndpointSlice controller và readiness state làm việc đó. `kube-proxy` chỉ dùng danh sách endpoint đã được publish.

### iptables mode

Trong `iptables` mode, `kube-proxy` tạo chuỗi rule trong netfilter. Packet tới Service IP/port sẽ match rule rồi DNAT sang một endpoint.

Đặc điểm:

- Rất phổ biến, mature, dễ gặp trong lab và production.
- Dựa vào rule chain. Khi số Service/Endpoint rất lớn, rule sync và traversal có thể thành chi phí đáng kể.
- Debug được bằng `iptables-save`, `conntrack`, node logs.
- Không yêu cầu IPVS kernel modules.

Với cluster nhỏ và trung bình, `iptables` thường đủ tốt. Vấn đề thường đến từ endpoint churn cao, quá nhiều Services, `conntrack` đầy, hoặc firewall/node rule ngoài Kubernetes can thiệp.

### IPVS mode

`IPVS` là Linux Virtual Server trong kernel. `kube-proxy` dùng IPVS để làm load balancing hiệu quả hơn, thường kết hợp iptables để bắt traffic vào service virtual IP.

Đặc điểm:

- Lookup backend hiệu quả hơn nhờ hash table trong kernel.
- Hỗ trợ nhiều scheduling algorithm như round-robin, least-connection tùy cấu hình.
- Hữu ích hơn khi cluster có nhiều Service/Endpoint hoặc traffic rất lớn.
- Cần kernel modules và tooling như `ipvsadm`.
- Operational complexity cao hơn `iptables`.

IPVS không tự làm app-level health check. Backend readiness vẫn đến từ Kubernetes EndpointSlice.

### eBPF dataplane

eBPF không phải một mode của `kube-proxy` upstream theo nghĩa truyền thống. Thực tế production hay gặp là kube-proxy replacement: một CNI/dataplane như Cilium dùng eBPF program để xử lý Service routing, NetworkPolicy, observability và đôi khi load balancing nâng cao.

Đặc điểm:

- Có thể giảm rule explosion và giảm một số overhead NAT/conntrack.
- Quan sát packet path tốt hơn nếu dùng tooling phù hợp.
- Kết hợp networking, security policy và observability trong cùng dataplane.
- Phức tạp hơn khi vận hành, upgrade và debug.
- Phụ thuộc kernel version, distro, CNI và configuration.

Không nên chọn eBPF chỉ vì nghe hiện đại. Chọn khi bạn cần policy/observability/performance ở mức mà iptables/IPVS trở thành giới hạn, và team có khả năng vận hành dataplane đó.

### conntrack

`conntrack` theo dõi connection state trong kernel. Service NAT thường đi qua conntrack. Khi bảng conntrack đầy hoặc timeout không phù hợp, symptom có thể là packet drop ngẫu nhiên, connection reset hoặc latency spike.

Các workload dễ tạo áp lực:

- Nhiều short-lived connections.
- High QPS internal calls.
- Load test không reuse connection.
- DNS query quá nhiều vì client không cache.
- Node có quá nhiều Pods cùng tạo outbound traffic.

### nftables caveat

Một số distro Linux mới dùng `iptables-nft` compatibility layer thay vì backend `iptables-legacy`. Vì vậy:

- `iptables-save` vẫn có thể chạy nhưng output đến từ nftables backend.
- Chuỗi `KUBE-SVC`/`KUBE-SEP` có thể không xuất hiện nếu cluster dùng IPVS, eBPF replacement hoặc implementation mới hơn.
- Không kết luận "không có kube-proxy" chỉ vì một command node-level không có output. Luôn đối chiếu với `EndpointSlice`, kube-proxy/K3s logs, CNI mode và tài liệu distro.

## Deep dive: Packet path của ClusterIP

```text
client Pod -> veth -> node network namespace
  -> packet dst = Service ClusterIP:port
  -> iptables/IPVS/eBPF rule match
  -> choose endpoint Pod IP:targetPort
  -> DNAT
  -> route tới Pod local hoặc Pod trên node khác qua CNI
```

Nếu backend Pod nằm trên node khác, packet còn đi qua CNI overlay/routed network. Vì vậy lỗi Service routing có thể nằm ở 3 lớp:

- Kubernetes object: Service selector, EndpointSlice, readiness.
- Node dataplane: kube-proxy/eBPF rules, conntrack, kernel module.
- CNI/node network: route PodCIDR, overlay tunnel, firewall.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| kube-proxy packaging | Thường chạy trong K3s process, không nhất thiết có DaemonSet `kube-proxy` | Thường là DaemonSet hoặc static component tùy bootstrap | Provider/add-on quản lý hoặc team quản lý tùy cloud |
| CNI mặc định | K3s thường dùng Flannel nếu không đổi | Tùy bạn cài | Cloud CNI hoặc CNI addon |
| Mode thường gặp | Thường iptables nếu chưa custom | iptables/IPVS/nftables tùy config/version | Phụ thuộc provider/add-on |
| eBPF | Cần custom CNI như Cilium và thường disable kube-proxy | Tự triển khai và vận hành | Có thể dùng add-on/marketplace, vẫn cần hiểu support matrix |
| Debug node-level | Có thể phải xem `journalctl -u k3s` hoặc node container k3d | Xem logs DaemonSet `kube-proxy` và node tools | Một phần bị managed abstraction che đi |

Trong K3s lab, không thấy Pod `kube-proxy` trong `kube-system` chưa chắc là lỗi. K3s đóng gói nhiều component vào binary/process riêng.

## Trade-offs và Best Practices

### Trade-offs

| Dataplane | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| `iptables` | Default ổn cho đa số cluster nhỏ/vừa | Rule count tăng theo Service/Endpoint, sync có thể đắt | Thấp | Rule stale, conntrack đầy, firewall conflict |
| `IPVS` | Cluster lớn, nhiều Services, cần lookup hiệu quả hơn | Hash lookup tốt hơn, vẫn cần netfilter hook | Trung bình | Thiếu kernel module, IPVS state lệch |
| eBPF replacement | Cần policy/observability/performance nâng cao | Có thể giảm overhead, tùy CNI/kernel | Cao | Kernel/CNI bug, upgrade phức tạp, tooling khác |

### Best Practices

Nên làm:

- Luôn xác định mode thực tế bằng config/logs, không đoán.
- Debug từ `Service` -> `EndpointSlice` -> Pod readiness -> node dataplane -> CNI route.
- Giữ số lượng Services và endpoint churn ở mức hợp lý.
- Dùng HTTP keep-alive/connection pooling cho microservices traffic lớn.
- Theo dõi `conntrack` usage trên node production.
- Với K3s, hiểu component nào được đóng gói mặc định và component nào bạn đã thay thế.
- Với eBPF, chuẩn hóa runbook bằng tooling của CNI, ví dụ `cilium status`, `cilium service list`.

Tránh làm:

- Chuyển mode dataplane trong production mà không test upgrade/rollback.
- Cài Cilium kube-proxy replacement rồi vẫn để kube-proxy xử lý cùng Service path.
- Đổ lỗi kube-proxy khi Service selector hoặc `targetPort` sai.
- Bỏ qua CNI route khi traffic chỉ fail với Pod ở node khác.
- Tối ưu IPVS/eBPF cho cluster nhỏ khi vấn đề thật là app connection storm.

## Performance Considerations

- `iptables` mode có thể chịu ảnh hưởng khi số rule lớn hoặc update EndpointSlice liên tục.
- `IPVS` tốt hơn cho lookup ở quy mô lớn nhưng vẫn cần đồng bộ state từ Kubernetes API.
- eBPF có thể giảm một số NAT/conntrack overhead, nhưng hiệu quả phụ thuộc CNI, kernel và traffic pattern.
- `externalTrafficPolicy: Local` giảm cross-node forwarding và giữ source IP tốt hơn, nhưng chỉ node có local endpoints nhận traffic.
- `externalTrafficPolicy: Cluster` phân phối rộng hơn nhưng có thể thêm cross-node hop và SNAT.
- `conntrack` đầy thường tạo lỗi khó tái hiện: timeout ngẫu nhiên, retry tăng, latency p99 xấu.
- Endpoint churn cao làm dataplane sync liên tục. Rollout quá lớn hoặc autoscaling dao động có thể ảnh hưởng routing.

## Debugging Checklist

Kiểm tra Kubernetes object trước:

```bash
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl describe svc <service> -n <namespace>
kubectl get pods -n <namespace> -o wide --show-labels
kubectl describe pod <pod> -n <namespace>
```

Kiểm tra kube-proxy trong Kubernetes upstream:

```bash
kubectl -n kube-system get pods -l k8s-app=kube-proxy -o wide
kubectl -n kube-system get configmap kube-proxy -o yaml
kubectl -n kube-system logs -l k8s-app=kube-proxy --tail=100
```

Kiểm tra K3s:

```bash
kubectl -n kube-system get pods -o wide
kubectl get nodes -o wide
# Trên Linux node chạy K3s:
sudo journalctl -u k3s -n 200
sudo journalctl -u k3s-agent -n 200
```

Kiểm tra node dataplane nếu có quyền node:

```bash
sudo iptables-save | grep KUBE-SVC | head
sudo iptables-save | grep <service-name>
sudo ipvsadm -Ln
sudo conntrack -S
sudo sysctl net.netfilter.nf_conntrack_count
sudo sysctl net.netfilter.nf_conntrack_max
```

Nếu node dùng nftables backend, kiểm tra thêm:

```bash
sudo iptables -V
sudo nft list ruleset | grep -E 'KUBE-|kube|service' | head
```

Test từ trong cluster:

```bash
kubectl run curl -n <namespace> --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- http://<service>:<port>
```

Nếu Service có endpoints nhưng traffic timeout, đi theo decision tree ngắn:

1. `EndpointSlice` có endpoint Ready không?
2. `targetPort` có đúng port app listen không?
3. Gọi trực tiếp Pod IP có thành công không?
4. Chỉ Service fail nhưng Pod IP OK: nghi kube-proxy/eBPF Service dataplane.
5. Cả Service và Pod IP cross-node fail: nghi CNI route, overlay, firewall hoặc MTU.
6. Chỉ fail dưới tải cao: kiểm tra conntrack/node saturation.

## Liên hệ với kiến thức đã biết

Với microservices, `kube-proxy` là lớp L4 service discovery/load balancing tương tự một internal VIP fabric. Nó không thay thế API Gateway, Ingress controller hay service mesh. Nếu app tạo quá nhiều short-lived connections như gọi Redis/Postgres/Kafka sai cách, vấn đề có thể xuất hiện ở conntrack và node dataplane trước khi CPU application tăng rõ rệt.

## Tóm tắt

`kube-proxy` biến `Service` và `EndpointSlice` thành node-local dataplane rules. `iptables` là lựa chọn phổ biến và đủ tốt cho nhiều cluster. `IPVS` phù hợp hơn khi scale Service/Endpoint lớn nhưng cần kernel/tooling đúng. eBPF thường là kube-proxy replacement, đem lại performance/observability/policy mạnh hơn với chi phí vận hành cao hơn. Debug Service routing phải đi từ object state tới node dataplane và CNI, không nhìn mỗi `ClusterIP`.

## Câu hỏi tự kiểm tra

1. Vì sao `Service` có endpoints nhưng traffic vẫn có thể timeout?
2. `iptables` mode khác `IPVS` mode ở cấu trúc lookup như thế nào?
3. eBPF có phải mode trực tiếp của `kube-proxy` upstream không?
4. `conntrack` đầy gây symptom gì trong microservices traffic?
5. Vì sao K3s có thể không có DaemonSet `kube-proxy`?

## Tài liệu tham khảo

- Kubernetes Services, Load Balancing, and Networking: https://kubernetes.io/docs/concepts/services-networking/
- Kubernetes Virtual IPs and Service Proxies: https://kubernetes.io/docs/reference/networking/virtual-ips/
- Kubernetes EndpointSlices: https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/
- K3s Networking Services: https://docs.k3s.io/networking/networking-services
- K3s Packaged Components: https://docs.k3s.io/installation/packaged-components
