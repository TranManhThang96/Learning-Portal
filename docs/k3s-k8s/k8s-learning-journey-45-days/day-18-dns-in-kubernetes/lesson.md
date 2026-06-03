# Day 18: DNS trong Kubernetes

## Mục tiêu bài học

- Hiểu cách Kubernetes tạo DNS records cho `Service`, Headless Service và một số Pod FQDN.
- Biết vai trò của `CoreDNS` trong service discovery nội bộ.
- Đọc được `/etc/resolv.conf`, search domains, `ndots` và `dnsPolicy` trong Pod.
- Debug được lỗi service discovery: sai namespace, Service không endpoints, CoreDNS lỗi; nhận diện ở mức preview khi NetworkPolicy chặn DNS để nối sang Day 19.
- Hiểu khác biệt giữa K3s, Kubernetes tự dựng và managed Kubernetes khi vận hành DNS.

## Vấn đề cần giải quyết

Microservices không nên gọi Pod IP. Day 15 dùng `Service` để có IP ổn định, Day 17 dùng Ingress cho HTTP entrypoint. Nhưng application thường không gọi IP, mà gọi DNS name:

```text
http://payment.payment.svc.cluster.local:8080
redis.cache.svc.cluster.local:6379
postgres.database.svc.cluster.local:5432
```

Khi DNS lỗi, symptom thường giống app/network lỗi: timeout, connection refused, random 5xx hoặc service chỉ fail ở một namespace. Vì vậy cần biết Kubernetes DNS tạo record như thế nào và debug từ Pod ra CoreDNS.

## Mental Model

```text
Pod app
  |
  | DNS query: web.day18.svc.cluster.local
  v
CoreDNS Service kube-dns
  |
  | kubernetes plugin reads Service/EndpointSlice
  v
Answer: ClusterIP hoặc endpoint IPs
```

`CoreDNS` là cluster DNS server. Pod thường dùng `kube-dns` Service IP làm nameserver trong `/etc/resolv.conf`.

## Lý thuyết cốt lõi

### Service DNS records

Với Service bình thường có `ClusterIP`, Kubernetes tạo A/AAAA record trỏ tới ClusterIP:

```text
<service>.<namespace>.svc.<cluster-domain>
```

Ví dụ:

```text
web.day18.svc.cluster.local -> 10.43.x.y
```

Trong cùng namespace, Pod có thể gọi ngắn:

```text
web
web.day18
web.day18.svc
web.day18.svc.cluster.local
```

Nhưng trong namespace khác, gọi `web` có thể tìm Service tên `web` ở namespace hiện tại, không phải `day18`.

### Headless Service DNS

Headless Service dùng `clusterIP: None`. DNS không trả về một ClusterIP, mà trả về IP của endpoints phía sau.

Use case:

- Stateful peer discovery.
- Client-side load balancing.
- Database/cache cluster cần biết từng member.

Điểm cần nhớ: client phải chịu trách nhiệm retry, load balancing và xử lý endpoint churn tốt hơn so với khi gọi ClusterIP.

### SRV records

Với named port, Kubernetes DNS có thể trả SRV record:

```text
_<port-name>._<protocol>.<service>.<namespace>.svc.cluster.local
```

Ví dụ:

```text
_http._tcp.web.day18.svc.cluster.local
```

SRV hữu ích khi client cần discover port theo tên, nhưng trong microservices HTTP/gRPC thực tế, nhiều team vẫn cấu hình port rõ qua environment/config.

### Pod DNS và stable Pod FQDN

Kubernetes có thể tạo Pod DNS record theo IP hoặc stable hostname/subdomain khi Pod được cấu hình phù hợp với Headless Service.

Với `StatefulSet`, pattern quen thuộc:

```text
<pod-name>.<headless-service>.<namespace>.svc.cluster.local
```

Ví dụ:

```text
postgres-0.postgres.database.svc.cluster.local
```

Không nên dựa vào raw Pod DNS cho stateless Deployment. Với Deployment, Pod identity thay đổi sau rollout/reschedule.

### Pod `/etc/resolv.conf`

Pod mặc định thường có:

```text
nameserver <kube-dns-service-ip>
search <namespace>.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

Search domain giúp gọi `web` thay vì FQDN. `ndots:5` làm tên có ít dấu chấm được thử với search domains trước khi query absolute name. Điều này tiện trong cluster nhưng có thể làm external DNS lookup chậm nếu app gọi nhiều external host ngắn hoặc client không cache DNS.

### dnsPolicy

Các giá trị thường gặp:

| dnsPolicy | Ý nghĩa |
|---|---|
| `ClusterFirst` | Default cho Pod thường; query trong cluster đi CoreDNS |
| `Default` | Dùng DNS config của node |
| `ClusterFirstWithHostNet` | Dùng cho Pod `hostNetwork` muốn vẫn dùng cluster DNS |
| `None` | Tự cấu hình `dnsConfig` |

Sai `dnsPolicy` có thể làm Pod không resolve được `*.svc.cluster.local` dù CoreDNS vẫn khỏe.

### CoreDNS

CoreDNS thường chạy trong `kube-system`, expose qua Service tên `kube-dns`. Plugin `kubernetes` trả lời records cho Service/Pod trong cluster; plugin `forward` chuyển external DNS ra upstream resolver; plugin `cache` giảm query load.

K3s thường đóng gói CoreDNS mặc định. Có thể disable bằng `--disable=coredns`, nhưng production chỉ nên làm khi bạn có DNS replacement rõ ràng.

## Deep dive: DNS query path

```text
app calls getaddrinfo("web")
  |
  v
glibc/musl reads /etc/resolv.conf
  |
  v
tries web.<namespace>.svc.cluster.local
  |
  v
query CoreDNS Service IP
  |
  v
kube-proxy/eBPF routes to CoreDNS Pod
  |
  v
CoreDNS kubernetes plugin returns Service ClusterIP
  |
  v
app connects to ClusterIP:port
```

DNS thành công chưa đảm bảo application connect thành công. Sau DNS còn Service dataplane, EndpointSlice, NetworkPolicy, Pod readiness và app port.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| DNS addon | CoreDNS bundled mặc định | Team cài qua bootstrap/addon | Provider/add-on quản lý nhưng team vẫn cấu hình/monitor |
| Service name | Thường vẫn là `kube-dns` | Thường `kube-dns` | Thường `kube-dns` hoặc provider equivalent |
| Disable/replace | `--disable=coredns` nếu tự thay | Tự quản manifest/addon | Theo provider support boundary |
| Config | ConfigMap CoreDNS, K3s packaged component caveat | ConfigMap/Helm/GitOps | Add-on config tùy provider |
| Failure blast radius | Nhỏ nhưng dễ làm toàn cluster mất discovery | Toàn cluster | Toàn cluster, nhưng control plane có thể managed |

CoreDNS là shared dependency. Một thay đổi nhỏ trong Corefile có thể làm toàn bộ service discovery lỗi.

## Trade-offs và Best Practices

### Trade-offs

| Option | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Gọi short name `web` | Same namespace, lab, app đơn giản | Nhanh đọc, dựa search domain | Thấp | Sai namespace |
| Gọi FQDN `web.ns.svc.cluster.local` | Cross-namespace, config rõ ràng | Ít ambiguity | Thấp | Cluster domain hard-code |
| Headless Service | Stateful/client-side discovery | Client xử lý nhiều IP | Trung bình | Client không retry endpoint churn |
| Custom `dnsPolicy: None` | Need DNS đặc biệt | Có thể bypass CoreDNS | Cao | Mất cluster DNS nếu sai |
| NodeLocal DNSCache | Cluster lớn, DNS QPS cao | Giảm latency/load CoreDNS | Trung bình | Cache/config issue |

### Best Practices

Nên làm:

- Dùng FQDN khi gọi cross-namespace trong config production.
- Đặt Service names ổn định và tránh đổi tên tùy release.
- Monitor CoreDNS QPS, latency, error rate và Pod restarts.
- Dùng DNS caching hợp lý ở application/runtime khi traffic lớn.
- Sau Day 19, kiểm tra cả UDP và TCP 53 nếu dùng NetworkPolicy.
- Với Pod `hostNetwork`, dùng `ClusterFirstWithHostNet` nếu cần cluster DNS.
- Quản lý CoreDNS Corefile bằng GitOps/change review.

Tránh làm:

- Gọi short name từ namespace khác rồi hy vọng resolve đúng.
- Patch CoreDNS Corefile trực tiếp trong production mà không có rollback.
- Dùng Headless Service cho app không xử lý multiple endpoints.
- Chặn egress DNS bằng NetworkPolicy mà không allow `kube-dns`.
- Tạo quá nhiều external DNS lookup short-lived không cache.
- Hard-code CoreDNS Service IP trong app.

## Performance Considerations

- DNS query volume cao có thể làm CoreDNS CPU tăng và p99 latency xấu.
- `ndots:5` có thể tạo nhiều query hơn cho external names.
- App không cache DNS hoặc tạo connection mới liên tục sẽ gây áp lực lên CoreDNS.
- CoreDNS Pod cần requests/limits phù hợp; thiếu CPU có thể tạo timeout dây chuyền.
- NodeLocal DNSCache có thể giảm load CoreDNS trong cluster lớn.
- Headless Service trả nhiều IP; response size lớn có thể chuyển sang TCP DNS.
- CoreDNS phụ thuộc kube-proxy/dataplane để Pod gọi được Service `kube-dns`.

## Debugging Checklist

Kiểm tra DNS system:

```bash
kubectl -n kube-system get svc kube-dns
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system get configmap coredns -o yaml
kubectl -n kube-system logs deploy/coredns --tail=100
```

Kiểm tra từ Pod:

```bash
kubectl exec -it <pod> -n <namespace> -- cat /etc/resolv.conf
kubectl exec -it <pod> -n <namespace> -- nslookup kubernetes.default
kubectl exec -it <pod> -n <namespace> -- nslookup <service>.<namespace>.svc.cluster.local
```

Tạo debug Pod:

```bash
kubectl run dns-test -n <namespace> --rm -it --restart=Never --image=busybox:1.36 -- nslookup kubernetes.default
```

Kiểm tra Service sau DNS:

```bash
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl describe svc <service> -n <namespace>
kubectl get pods -n <namespace> -o wide --show-labels
```

Nếu DNS fail:

- Same namespace hay cross-namespace?
- Short name hay FQDN?
- Pod dùng `dnsPolicy` gì?
- `/etc/resolv.conf` có nameserver CoreDNS không?
- CoreDNS Pods có Ready không?
- NetworkPolicy có allow UDP/TCP 53 tới `kube-dns` không?
- External DNS fail hay chỉ `*.svc.cluster.local` fail?

## Liên hệ với kiến thức đã biết

Kubernetes DNS giống service discovery registry được expose qua DNS. Với backend engineer, nó thay thế một phần config service host thủ công. Nhưng DNS chỉ trả địa chỉ; retry, timeout, connection pooling và circuit breaker vẫn là trách nhiệm application/runtime hoặc service mesh/API gateway.

## Tóm tắt

CoreDNS cung cấp service discovery nội bộ cho Kubernetes. Service thường resolve về ClusterIP; Headless Service resolve về endpoint IPs. Pod dùng search domains và `ndots`, nên short name tiện nhưng dễ sai namespace. Debug DNS phải bắt đầu từ `/etc/resolv.conf`, CoreDNS health, Service/EndpointSlice và NetworkPolicy. Production cần monitor DNS như một shared dependency quan trọng, không coi nó là chi tiết phụ.

## Câu hỏi tự kiểm tra

1. Service bình thường và Headless Service trả DNS khác nhau thế nào?
2. Vì sao `web` resolve được trong namespace A nhưng fail trong namespace B?
3. `dnsPolicy: Default` có thể gây lỗi gì trong Pod?
4. `ndots:5` ảnh hưởng external DNS lookup ra sao?
5. Khi DNS resolve thành công nhưng curl Service fail, cần kiểm tra layer nào tiếp theo?

## Tài liệu tham khảo

- Kubernetes DNS for Services and Pods: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- Kubernetes Debugging DNS Resolution: https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/
- Kubernetes Debug Services: https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/
- CoreDNS: https://coredns.io/
- K3s Networking Services: https://docs.k3s.io/networking/networking-services
