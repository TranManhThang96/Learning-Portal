# Day 19: Network Policies

## Mục tiêu bài học

- Hiểu `NetworkPolicy` là cơ chế allow-list L3/L4 cho Pod traffic, không phải firewall tổng quát cho toàn cluster.
- Thiết kế được pattern `default deny` rồi mở dần ingress/egress theo dependency thật của microservices.
- Phân biệt rõ `podSelector`, `namespaceSelector`, `ipBlock`, `policyTypes`, `Ingress` và `Egress`.
- Biết giới hạn của `NetworkPolicy`: cần CNI hỗ trợ, policy là additive allow, không có explicit deny và không phải policy L7.
- Debug được lỗi traffic bị timeout do policy chặn, đặc biệt DNS egress và cross-namespace traffic.

## Vấn đề cần giải quyết

Mặc định Kubernetes network model cho phép Pod nói chuyện với Pod khác khá rộng. Điều này tiện cho lab, nhưng không phù hợp với production microservices:

```text
frontend -> api          hợp lệ
api      -> db           hợp lệ
frontend -> db           không nên
debug    -> payment      chỉ nên trong break-glass
unknown  -> redis        không nên
```

Nếu không có policy, một service bị compromise có thể quét port nội bộ, gọi database/cache trực tiếp hoặc truy cập service không thuộc dependency graph của nó. `NetworkPolicy` giúp chuyển mindset từ "mọi thứ được phép" sang "chỉ dependency được khai báo mới được phép".

## Mental Model

```text
Pod traffic
  |
  v
CNI policy engine checks:
  - Pod đích có bị isolated cho ingress không?
  - Pod nguồn có bị isolated cho egress không?
  - Có policy nào allow flow này không?
  |
  v
Allow hoặc drop
```

`NetworkPolicy` không route traffic. Nó chỉ quyết định flow Pod-to-Pod hoặc Pod-to-CIDR có được phép đi tiếp hay không. Dataplane thực thi nằm trong CNI hoặc policy controller đi kèm CNI.

## Lý thuyết cốt lõi

### Default behavior

Pod mặc định là non-isolated:

- Nếu không có policy nào chọn Pod đó cho `Ingress`, mọi ingress traffic tới Pod được phép.
- Nếu không có policy nào chọn Pod đó cho `Egress`, mọi egress traffic từ Pod được phép.
- Khi một policy chọn Pod cho một hướng, Pod trở thành isolated ở hướng đó; chỉ traffic được allow bởi ít nhất một policy mới đi qua.

Policy là additive allow-list. Nhiều policy cùng chọn một Pod thì allowed traffic là hợp của tất cả rule. Không có rule "deny" ưu tiên cao hơn.

### `podSelector`

`podSelector` trong `spec` chọn các Pod mà policy áp dụng tới trong namespace hiện tại.

```yaml
spec:
  podSelector:
    matchLabels:
      app: api
```

Nếu `podSelector: {}` thì policy chọn toàn bộ Pod trong namespace.

### `policyTypes`

`policyTypes` khai báo hướng traffic:

```yaml
policyTypes:
- Ingress
- Egress
```

Nếu tạo default-deny all nhưng quên `Egress`, Pod vẫn có thể gọi ra ngoài. Nếu tạo egress deny mà quên allow DNS, application sẽ fail giống lỗi service discovery.

### Ingress rules

Ingress rule mô tả ai được phép gọi vào selected Pods.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-api
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: frontend
    ports:
    - protocol: TCP
      port: 8080
```

Rule trên nghĩa là Pods `app=api` chỉ nhận TCP 8080 từ Pods `role=frontend` trong cùng namespace.

### Egress rules

Egress rule mô tả selected Pods được phép gọi tới đâu.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-egress-to-api
spec:
  podSelector:
    matchLabels:
      role: frontend
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: api
    ports:
    - protocol: TCP
      port: 8080
```

Trong mô hình zero-trust thực tế, thường cần cả hai phía:

- Đích allow ingress từ nguồn hợp lệ.
- Nguồn allow egress tới đích hợp lệ.

### `namespaceSelector` và cross-namespace

`podSelector` đơn lẻ chỉ match Pod trong namespace của policy. Muốn allow cross-namespace, dùng `namespaceSelector`.

```yaml
from:
- namespaceSelector:
    matchLabels:
      team: payments
  podSelector:
    matchLabels:
      app: payment-api
```

Điểm rất dễ nhầm:

```yaml
from:
- namespaceSelector:
    matchLabels:
      team: payments
  podSelector:
    matchLabels:
      app: payment-api
```

Nghĩa là Pod `app=payment-api` trong namespace có label `team=payments`.

Còn:

```yaml
from:
- namespaceSelector:
    matchLabels:
      team: payments
- podSelector:
    matchLabels:
      app: payment-api
```

Nghĩa là OR: mọi Pod trong namespace `team=payments`, hoặc Pod `app=payment-api` trong namespace hiện tại.

### `ipBlock`

`ipBlock` dùng cho CIDR ngoài cluster, ví dụ gọi third-party API, NAT gateway, corporate network hoặc egress gateway:

```yaml
egress:
- to:
  - ipBlock:
      cidr: 203.0.113.0/24
      except:
      - 203.0.113.42/32
```

Không nên dùng `ipBlock` để match Pod IP nội bộ nếu có thể dùng selector. Pod IP thay đổi theo reschedule và behavior trước/sau NAT có thể khác nhau theo CNI.

### Service NAT, SNAT và port matching

`NetworkPolicy` được viết theo Pod/namespace labels, nhưng packet thực tế có thể đi qua `Service` DNAT, kube-proxy/eBPF hoặc CNI dataplane trước/sau thời điểm policy được enforce. Hệ quả vận hành:

- Đừng dùng `ipBlock` để match `ClusterIP` hoặc Pod IP nội bộ; dùng `podSelector`/`namespaceSelector`.
- Khi allow traffic tới app, match port mà Pod/backend thực sự nhận, không chỉ nhìn mỗi `Service.port`.
- Test cả `http://service:port` và direct Pod IP khi debug vì một số CNI có nuance khác nhau quanh Service translation.
- Egress ra ngoài cluster có thể bị SNAT/masquerade ở node hoặc egress gateway; log phía ngoài có thể không thấy Pod IP gốc.

### DNS là dependency đặc biệt

Khi bật default-deny egress, Pod không resolve được Service nếu không allow DNS tới CoreDNS:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

Selector CoreDNS có thể khác theo distro. Luôn kiểm tra label thực tế bằng:

```bash
kubectl -n kube-system get pods --show-labels | grep -i dns
```

## Deep dive: Policy evaluation

Ví dụ flow `frontend -> api:8080`:

```text
1. frontend gửi packet tới Service api hoặc Pod IP api.
2. Service dataplane chọn endpoint Pod api.
3. CNI policy engine kiểm tra egress của frontend.
4. CNI policy engine kiểm tra ingress của api.
5. Nếu cả hai hướng bị isolated thì cả hai phải có allow rule phù hợp.
6. Nếu không có allow rule, packet thường bị drop, symptom là timeout.
```

NetworkPolicy thường tạo timeout, không tạo HTTP 403. Application không biết packet bị policy drop ở dataplane.

Một flow hợp lệ phải trả lời được các câu hỏi:

- Source Pod có label gì?
- Destination Pod có label gì?
- Cả hai nằm namespace nào?
- Port thật là `port` hay `targetPort`?
- Destination được gọi qua Service hay direct Pod IP?
- DNS có được allow trước khi gọi Service name không?
- CNI hiện tại có enforce NetworkPolicy không?

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| NetworkPolicy API | Có API Kubernetes chuẩn | Có API chuẩn | Có API chuẩn |
| Enforcement | K3s có network policy controller mặc định; custom CNI có thể thay thế | Phụ thuộc CNI được cài | Phụ thuộc cloud CNI/add-on |
| Default CNI | Thường là Flannel kèm policy controller của K3s | Calico/Cilium/Flannel/khác tùy bạn | Provider CNI hoặc add-on |
| Custom CNI | Dùng `--flannel-backend=none`, thường thêm `--disable-network-policy` | Cài CNI theo bootstrap | Theo support matrix của provider |
| Debug | Xem policy object, CoreDNS labels, K3s service logs, CNI pods | Xem CNI DaemonSet/logs/node rules | Một phần qua add-on/provider logs |

Lưu ý quan trọng: `NetworkPolicy` object có thể apply thành công nhưng không có tác dụng nếu dataplane không enforce policy. Vì vậy bài học đầu tiên trong production là xác nhận CNI/policy engine, không chỉ kiểm tra YAML.

## Trade-offs và Best Practices

### Trade-offs

| Pattern | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Không dùng NetworkPolicy | Lab tạm, cluster throwaway | Ít overhead | Thấp | Lateral movement rất rộng |
| Ingress-only policy | Bắt đầu kiểm soát service exposure | Overhead thấp | Trung bình | Egress vẫn gọi ra ngoài tự do |
| Ingress + egress default deny | Production zero-trust | Policy evaluation nhiều hơn | Cao | DNS/dependency bị chặn nếu thiếu allow |
| Namespace-level default deny | Multi-team baseline | Dễ chuẩn hóa | Trung bình | Team quên mở dependency |
| CNI L7 policy extension | Cần HTTP/Kafka/gRPC policy sâu | Có thêm cost dataplane | Cao | Lock-in CNI, debug phức tạp |

### Best Practices

Nên làm:

- Bắt đầu bằng namespace-level `default-deny-all`, rồi mở dependency theo service graph.
- Gắn label có chủ đích: `app`, `component`, `tier`, `team`, `environment`.
- Allow DNS egress là policy nền tảng cho namespace default-deny egress.
- Viết policy gần với workload manifest và review bằng GitOps.
- Test cả positive case và negative case.
- Monitor drop/deny metrics nếu CNI hỗ trợ.
- Với production, chuẩn hóa template policy cho từng loại service: public API, internal API, worker, database client.

Tránh làm:

- Tin rằng apply NetworkPolicy là đủ nếu chưa xác nhận CNI enforce.
- Dùng selector quá rộng như allow từ toàn namespace nếu chỉ cần một app.
- Dùng `ipBlock` cho Pod IP nội bộ.
- Quên rằng policy là namespaced resource.
- Dựa vào short DNS name cross-namespace trong policy lab.
- Debug bằng HTTP status code; policy drop thường là timeout.
- Bật egress default deny trong production mà không có inventory dependency.

## Performance Considerations

- Mỗi CNI triển khai policy khác nhau: iptables/ipset, eBPF maps hoặc policy engine riêng.
- Số lượng policy, selector và endpoint churn cao có thể làm policy recalculation tốn CPU.
- Egress default-deny có thể tăng ticket incident nếu dependency không được khai báo đầy đủ.
- Policy L7 của CNI extension mạnh hơn nhưng tốn nhiều CPU/memory hơn L3/L4.
- DNS bị chặn tạo retry storm từ application và làm latency nhìn giống lỗi CoreDNS.
- NetworkPolicy không thay thế mTLS/authn/authz. Nó giảm blast radius ở network layer, không xác thực user/request.

## Debugging Checklist

Kiểm tra policy và labels:

```bash
kubectl get networkpolicy -n <namespace>
kubectl describe networkpolicy <policy> -n <namespace>
kubectl get pods -n <namespace> --show-labels -o wide
kubectl get namespace --show-labels
```

Kiểm tra Service và endpoints:

```bash
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl describe svc <service> -n <namespace>
```

Test từ Pod nguồn:

```bash
kubectl exec -it <source-pod> -n <namespace> -- nslookup <service>.<namespace>.svc.cluster.local
kubectl exec -it <source-pod> -n <namespace> -- wget -qO- --timeout=2 http://<service>:<port>
```

Kiểm tra DNS egress:

```bash
kubectl -n kube-system get pods --show-labels | grep -i dns
kubectl exec -it <source-pod> -n <namespace> -- nslookup kubernetes.default
```

Kiểm tra CNI/policy engine:

```bash
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get ds
kubectl -n kube-system logs <cni-pod> --tail=100
```

Nếu traffic fail:

- Source Pod có bị isolated egress không?
- Destination Pod có bị isolated ingress không?
- Selector trong policy match đúng labels không?
- Namespace selector match đúng namespace labels không?
- Có allow UDP/TCP 53 tới CoreDNS không?
- Port trong policy là port container thật hay Service port?
- CNI hiện tại có hỗ trợ NetworkPolicy không?

## Liên hệ với kiến thức đã biết

NetworkPolicy giống security group/firewall allow-list ở mức Pod identity, nhưng selector động hơn vì dựa trên Kubernetes labels. Với microservices, nó là một phần của defense-in-depth cùng với authn/authz, mTLS, secrets management và runtime policy. Đừng dùng NetworkPolicy để thay thế authorization ở application layer.

## Tóm tắt

`NetworkPolicy` giúp giới hạn Pod traffic theo allow-list. Pod mặc định open; khi được policy chọn cho ingress/egress thì chỉ allowed traffic mới đi qua. Policy là additive, namespaced và cần CNI/policy engine enforce. Pattern production thường là default-deny theo namespace, allow DNS, rồi allow dependency thật giữa services. Debug cần đi từ labels, policy object, Service/EndpointSlice, DNS tới CNI logs.

## Câu hỏi tự kiểm tra

1. Vì sao apply `NetworkPolicy` thành công nhưng traffic vẫn không bị chặn?
2. `podSelector` trong `spec` khác gì `podSelector` trong `from` hoặc `to`?
3. Khi bật default-deny egress, vì sao app có thể báo lỗi DNS?
4. Hai item `namespaceSelector` và `podSelector` trong cùng một list entry khác gì hai list entry riêng?
5. Vì sao `NetworkPolicy` không thay thế authentication/authorization?

## Tài liệu tham khảo

- Kubernetes Network Policies: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- Kubernetes Security Checklist - Network security: https://kubernetes.io/docs/concepts/security/security-checklist/
- K3s Networking Services: https://docs.k3s.io/networking/networking-services
- K3s Basic Network Options: https://docs.k3s.io/networking/basic-network-options
- Cilium Network Policy: https://docs.cilium.io/en/stable/security/policy/
