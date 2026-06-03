# Day 20: CNI deep-dive

## Mục tiêu bài học

- Hiểu `CNI` là lớp triển khai Pod networking, IPAM, routes và đôi khi cả `NetworkPolicy`/Service dataplane.
- Phân biệt Kubernetes network model với cách từng CNI hiện thực model đó.
- So sánh Flannel, Calico, Cilium, cloud CNI theo overlay/routed/eBPF, performance và operational complexity.
- Biết K3s dùng Flannel mặc định như thế nào và khi nào cần thay bằng custom CNI.
- Debug được lỗi Pod-to-Pod, cross-node traffic, MTU, CNI DaemonSet và policy engine.

## Vấn đề cần giải quyết

Từ Day 15-19, bạn đã dùng `Service`, `kube-proxy`, `Ingress`, DNS và `NetworkPolicy`. Nhưng tất cả đều dựa trên một nền tảng thấp hơn: Pod network.

Khi Pod A gọi Pod B:

```text
Pod A IP -> node network -> overlay/routed network -> node khác -> Pod B IP
```

Nếu CNI lỗi, symptom có thể rất giống lỗi application:

- Service có endpoints nhưng timeout.
- DNS resolve được nhưng Pod IP không ping/curl được.
- Same-node traffic chạy, cross-node traffic fail.
- NetworkPolicy không có tác dụng hoặc chặn sai.
- MTU mismatch gây timeout với payload lớn.

Day 20 giúp bạn đọc được lớp dataplane dưới Kubernetes objects.

## Mental Model

```text
kubelet creates Pod sandbox
  |
  v
Container runtime calls CNI plugin
  |
  v
CNI plugin:
  - tạo interface trong Pod netns
  - cấp Pod IP qua IPAM
  - nối Pod với node network
  - cài route/encapsulation/policy nếu cần
  |
  v
Pod có network namespace riêng và IP routable trong cluster
```

CNI không phải một sản phẩm duy nhất. Nó là interface/spec. Flannel, Calico, Cilium, cloud CNI là các implementation với triết lý khác nhau.

## Lý thuyết cốt lõi

### Kubernetes network model

Kubernetes giả định:

- Mỗi Pod có IP riêng.
- Pod có thể nói chuyện với Pod khác mà không cần NAT ở mức application.
- Node có thể nói chuyện với Pod.
- Pod thấy chính IP của nó là source IP trong nhiều tình huống nội bộ.

Kubernetes không bắt buộc cách triển khai. CNI quyết định dùng bridge, veth, VXLAN, Geneve, BGP, cloud route table, eBPF hay kết hợp nhiều cơ chế.

### CNI plugin lifecycle

Khi Pod được schedule tới node:

```text
1. kubelet yêu cầu container runtime tạo Pod sandbox.
2. runtime gọi CNI plugin theo config trong /etc/cni/net.d.
3. CNI tạo veth pair hoặc cơ chế tương đương.
4. Một đầu vào Pod network namespace, một đầu ở node.
5. IPAM cấp IP cho Pod.
6. CNI cài routes/rules/policy để Pod traffic đi được.
7. Khi Pod xóa, runtime gọi CNI DEL để cleanup.
```

Nếu CNI ADD fail, Pod thường kẹt `ContainerCreating` với event liên quan network setup.

### IPAM

`IPAM` (IP Address Management) cấp Pod IP. IPAM có thể đến từ:

- PodCIDR per-node do Kubernetes controller cấp.
- CNI tự quản IP pool.
- Cloud VPC/subnet IP thật.

Failure mode phổ biến:

- Hết IP trong pool/subnet.
- Node không được cấp PodCIDR.
- IP conflict sau restore/migration.
- Route tới PodCIDR không được quảng bá.

Với cloud CNI, IP exhaustion không chỉ là lỗi Kubernetes. Nó còn phụ thuộc subnet size, ENI/NIC quota, secondary IP per node, prefix delegation và autoscaler/node pool strategy. Một cluster có CPU/memory còn trống vẫn có thể không schedule Pod mới vì hết IP cấp được cho node.

### Pod egress, NAT và IP masquerade

Kubernetes network model yêu cầu Pod-to-Pod trong cluster không cần NAT ở application layer, nhưng egress ra ngoài cluster thường bị NAT/masquerade:

- Pod gọi Internet hoặc service ngoài VPC thường ra bằng node IP, NAT Gateway hoặc egress gateway.
- Log ở database/API bên ngoài có thể thấy node/NAT IP thay vì Pod IP.
- Cloud CNI có thể preserve Pod IP trong một số đường nội bộ VPC/VNet, nhưng vẫn phụ thuộc provider, route table và security group.
- NetworkPolicy egress theo `ipBlock` nên được test sau NAT path thật, không suy luận từ Pod IP đơn lẻ.

Production cần ghi rõ "source IP mà hệ thống ngoài nhìn thấy là gì" cho audit, allowlist, fraud/risk rule và incident response.

### Overlay networking

Overlay đóng gói packet Pod trong packet node-to-node, thường qua VXLAN/Geneve/WireGuard.

```text
Pod A packet
  -> encapsulated in node A outer packet
  -> physical network
  -> node B decapsulates
  -> Pod B
```

Ưu điểm:

- Dễ chạy trên hạ tầng không biết PodCIDR.
- Hợp lab, bare-metal nhỏ, môi trường cloud không muốn động tới route table.

Chi phí:

- Encapsulation overhead.
- MTU thấp hơn, dễ lỗi payload lớn nếu cấu hình sai.
- Debug cần nhìn thêm tunnel interface.

### Routed/native networking

Routed mode làm hạ tầng biết route tới PodCIDR, ví dụ BGP, static routes hoặc cloud route table.

Ưu điểm:

- Ít overhead hơn overlay.
- Dễ quan sát bằng route table nếu team network quen.
- Phù hợp on-prem/cloud private network khi kiểm soát được routing.

Chi phí:

- Cần phối hợp với network layer.
- BGP/route table/quota làm vận hành phức tạp hơn.
- Sai route có thể làm cross-node traffic fail toàn bộ.

### Flannel

Flannel tập trung vào Pod connectivity đơn giản. Trong K3s, Flannel là CNI mặc định thường gặp.

Điểm mạnh:

- Dễ vận hành, ít option, hợp lab/edge/small cluster.
- Overlay VXLAN mặc định đủ tốt cho nhiều workload nhỏ.
- K3s đóng gói sẵn nên bootstrap nhanh.

Giới hạn:

- Không phải lựa chọn mạnh nhất cho policy/observability nâng cao.
- NetworkPolicy trong K3s được xử lý bởi K3s network policy controller, không phải Flannel thuần.
- Khi cần zero-trust policy sâu, flow visibility hoặc eBPF Service dataplane, cân nhắc Calico/Cilium.

### Calico

Calico tập trung vào networking và policy. Nó có thể dùng routed/BGP hoặc overlay tùy cấu hình, và là lựa chọn phổ biến khi cần NetworkPolicy mature.

Điểm mạnh:

- Policy engine mạnh, quen thuộc trong production.
- Có thể vận hành ở routed mode với BGP.
- Phù hợp team muốn network policy nghiêm túc nhưng vẫn giữ mô hình tương đối truyền thống.

Chi phí:

- Nhiều mode/config hơn Flannel.
- BGP/routed design cần năng lực network ops.
- Debug cần hiểu Felix, IP pools, routes và policy state.

### Cilium

Cilium dùng eBPF để cung cấp networking, security và observability. Nó có thể enforce identity-based policy, mở rộng L7 policy, có Hubble để quan sát flow và có thể thay kube-proxy bằng eBPF service load balancing.

Điểm mạnh:

- Policy và observability sâu hơn.
- eBPF datapath có thể giảm một số overhead ở quy mô lớn.
- Hỗ trợ kube-proxy replacement, L3/L4/L7 policy, flow visibility.

Chi phí:

- Phụ thuộc kernel/Cilium version/config.
- Operational complexity cao hơn Flannel.
- Debug cần tooling riêng như `cilium status`, Hubble, agent logs.
- Không nên chọn chỉ vì "modern"; chọn khi yêu cầu thật sự cần.

### Cloud CNI

Managed Kubernetes thường có CNI tích hợp cloud:

- EKS thường dùng VPC CNI để Pod nhận IP từ VPC/subnet.
- GKE/AKS có dataplane và policy options riêng.
- Cloud CNI tích hợp route table, security group, ENI/NIC, load balancer và quota cloud.

Điểm cần nhớ: managed control plane không có nghĩa networking được "miễn phí vận hành". Team vẫn phải quản IP exhaustion, subnet sizing, policy, observability, upgrade add-on và cloud quota.

## Deep dive: Cross-node Pod traffic

```text
Pod A
  |
  | veth
  v
Node A bridge/route/eBPF
  |
  | overlay tunnel hoặc routed packet
  v
Node B
  |
  | veth
  v
Pod B
```

Nếu same-node traffic chạy nhưng cross-node fail, nghi ngờ:

- Overlay tunnel bị firewall chặn.
- MTU mismatch.
- Route PodCIDR thiếu.
- CNI DaemonSet trên một node lỗi.
- Node security group/firewall chặn encapsulation port.
- NetworkPolicy chỉ ảnh hưởng một nhóm Pod do labels khác nhau.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Default CNI | Flannel thường bật mặc định | Tùy bootstrap, thường phải cài CNI | Cloud CNI/add-on mặc định |
| Thay CNI | `--flannel-backend=none`, thường `--disable-network-policy` | Cài CNI trước khi node Ready | Theo provider support matrix |
| NetworkPolicy | K3s có policy controller mặc định; custom CNI có thể tự enforce | Phụ thuộc CNI | Phụ thuộc add-on/tier |
| Service dataplane | kube-proxy trong K3s hoặc thay bằng CNI eBPF nếu custom | kube-proxy/IPVS/eBPF tùy chọn | Provider/add-on |
| Debug | K3s logs, Flannel config, CNI pods, node routes | CNI DaemonSet, kubelet, node routes | Add-on logs, cloud route/subnet/security group |

Với K3s custom CNI, docs K3s khuyến nghị start server bằng `--flannel-backend=none` và thường disable network policy controller mặc định để tránh xung đột với policy engine của CNI mới.

## Trade-offs và Best Practices

### Trade-offs

| CNI/pattern | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Flannel VXLAN | Lab, edge, small cluster, K3s default | Encapsulation overhead, đủ tốt cho nhỏ/vừa | Thấp | MTU/tunnel/firewall |
| Calico overlay | Cần policy mature nhưng không muốn BGP | Overlay overhead | Trung bình | IP pool/policy mismatch |
| Calico BGP/routed | On-prem hoặc network team kiểm soát routing | Ít overlay overhead | Cao | BGP/route sai |
| Cilium eBPF | Cần policy/observability/kube-proxy replacement | Có thể rất tốt, tùy kernel/config | Cao | eBPF/kernel/agent issue |
| Cloud CNI | Managed Kubernetes, cần VPC-native integration | Ít overlay, gần cloud network | Trung bình-cao | IP/subnet/quota/security group |

### Best Practices

Nên làm:

- Chọn CNI theo yêu cầu thật: simplicity, policy, observability, performance, cloud integration.
- Với K3s lab, giữ Flannel mặc định cho đến khi có lý do rõ để thay.
- Xác nhận MTU sau khi dùng overlay/VPN/cloud network phức tạp.
- Test same-node và cross-node Pod traffic.
- Theo dõi CNI DaemonSet health trước khi debug app.
- Version-pin CNI add-on và đọc upgrade notes.
- Có rollback plan trước khi thay CNI trong cluster đang chạy.

Tránh làm:

- Thay CNI production trực tiếp trên cluster đang chạy mà không rebuild/test.
- Cài hai CNI cùng quản Pod network.
- Bật Cilium kube-proxy replacement nhưng vẫn để kube-proxy xử lý cùng path mà không hiểu config.
- Dùng Flannel thuần rồi kỳ vọng NetworkPolicy nâng cao.
- Bỏ qua IP exhaustion trong cloud CNI.
- Debug Service timeout mà không kiểm tra Pod-to-Pod direct IP.

## Performance Considerations

- Overlay thêm header, giảm effective MTU và có thể tăng CPU do encapsulation.
- Routed/native networking giảm overhead nhưng yêu cầu route propagation đúng.
- eBPF có thể giảm rule explosion và cải thiện observability, nhưng cần kernel phù hợp và runbook riêng.
- NetworkPolicy enforcement tốn CPU/memory theo số policy/endpoints và implementation.
- Cross-node traffic thường có latency cao hơn same-node traffic.
- Cloud CNI có thể bị giới hạn bởi số IP per node, ENI/NIC quota hoặc subnet size.
- MTU mismatch thường không lộ với request nhỏ nhưng fail với payload lớn.
- CNI agent restart hoặc endpoint regeneration có thể tạo packet loss ngắn.

## Debugging Checklist

Kubernetes level:

```bash
kubectl get nodes -o wide
kubectl describe node <node>
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get ds
kubectl get pods -A -o wide
kubectl get events -A --sort-by=.lastTimestamp
```

CNI logs:

```bash
kubectl -n kube-system logs <cni-pod> --tail=200
kubectl -n kube-system describe pod <cni-pod>
```

Pod-to-Pod tests:

```bash
kubectl get pods -n <namespace> -o wide
kubectl exec -it <source-pod> -n <namespace> -- wget -qO- --timeout=2 http://<pod-ip>:<port>
kubectl exec -it <source-pod> -n <namespace> -- wget -qO- --timeout=2 http://<service>:<port>
```

Node-level inspection nếu có quyền:

```bash
ip addr
ip route
ip link
ls /etc/cni/net.d
cat /etc/cni/net.d/*
journalctl -u k3s -n 200
journalctl -u kubelet -n 200
```

Cilium-specific nếu dùng Cilium:

```bash
cilium status
cilium connectivity test
kubectl -n kube-system logs -l k8s-app=cilium --tail=100
```

Khi traffic fail:

- Pod có IP chưa?
- Pod có nằm cùng node hay khác node?
- Service có endpoints Ready không?
- Direct Pod IP fail hay chỉ Service fail?
- CNI Pod trên node đó Ready không?
- Node route tới PodCIDR có tồn tại không?
- Overlay port có bị firewall/security group chặn không?
- Có NetworkPolicy đang chặn không?
- MTU có thấp hơn underlay không?

## Liên hệ với kiến thức đã biết

CNI là phần networking tương đương "data plane" trong distributed system. Với backend engineer, nó giống layer service-to-service connectivity bên dưới HTTP/gRPC. Application retry, timeout và circuit breaker chỉ hữu ích khi network foundation ổn; nếu CNI mất route hoặc MTU sai, retry chỉ khuếch đại load.

## Tóm tắt

CNI hiện thực Kubernetes Pod network model. Flannel ưu tiên đơn giản, Calico mạnh về policy/routing, Cilium dùng eBPF cho networking/security/observability nâng cao, cloud CNI tích hợp với hạ tầng cloud nhưng có quota và support boundary riêng. Debug CNI cần tách rõ Kubernetes object, Service dataplane, direct Pod traffic, cross-node path, CNI logs, routes, MTU và policy.

## Câu hỏi tự kiểm tra

1. CNI làm gì trong lifecycle tạo Pod?
2. Overlay VXLAN khác routed/BGP networking ở điểm nào?
3. Vì sao same-node Pod traffic chạy nhưng cross-node traffic fail?
4. Khi dùng custom CNI trong K3s, vì sao thường cần `--flannel-backend=none`?
5. Khi nào Cilium đáng để chọn thay vì Flannel mặc định?

## Tài liệu tham khảo

- Kubernetes Cluster Networking: https://kubernetes.io/docs/concepts/cluster-administration/networking/
- Kubernetes Network Policies: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- K3s Basic Network Options: https://docs.k3s.io/networking/basic-network-options
- K3s Networking Services: https://docs.k3s.io/networking/networking-services
- Cilium Kubernetes Networking: https://docs.cilium.io/en/stable/network/kubernetes/
- Cilium kube-proxy replacement: https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/
