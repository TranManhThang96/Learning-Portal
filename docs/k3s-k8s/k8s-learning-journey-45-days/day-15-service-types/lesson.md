# Day 15: Service types

## Mục tiêu bài học

- Hiểu `Service` giải quyết bài toán stable network identity cho Pods.
- Phân biệt `ClusterIP`, `NodePort`, `LoadBalancer`, `ExternalName` và Headless Service.
- Hiểu quan hệ giữa `Service`, selector, `EndpointSlice`, kube-proxy/dataplane và Pod readiness.
- Biết khác biệt giữa K3s local, bare-metal Kubernetes và managed Kubernetes khi dùng `LoadBalancer`.
- Debug được Service không có endpoints, traffic không tới Pod, port mapping sai và LoadBalancer pending.

## Vấn đề cần giải quyết

Pod IP không ổn định. Deployment scale lên/xuống, rollout, node drain hoặc Pod crash đều có thể làm backend IP thay đổi. Client không nên gọi trực tiếp Pod IP.

`Service` tạo một abstraction ổn định:

- DNS name ổn định.
- Virtual IP ổn định với `ClusterIP`.
- Selector tự động cập nhật backend Pods.
- Tích hợp với kube-proxy hoặc dataplane để load balance L4.

Service là nền tảng trước khi học `Ingress`, DNS, NetworkPolicy và service mesh.

## Mental Model

```text
Pod        = endpoint động.
Service    = stable virtual frontend.
EndpointSlice = danh sách backend endpoint hiện tại.
kube-proxy/dataplane = rule route traffic tới endpoint.
```

Client gọi Service. Service không chạy container. Nó là object mô tả cách chọn backend và expose traffic.

## Lý thuyết cốt lõi

### ClusterIP

`ClusterIP` là Service type mặc định. Nó tạo IP nội bộ trong cluster, chỉ truy cập được từ bên trong cluster network.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: ClusterIP
  selector:
    app: web
  ports:
  - name: http
    port: 8080
    targetPort: 8080
```

Use case:

- Service-to-service internal traffic.
- Backend API, Redis, database endpoint nội bộ.
- Backend sau Ingress controller.

Đây là default tốt nhất cho phần lớn microservices nội bộ.

### NodePort

`NodePort` mở một port trên mỗi node và forward vào Service.

```yaml
spec:
  type: NodePort
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 30080
```

Use case:

- Lab nhanh.
- Bare-metal khi chưa có load balancer.
- Debug tạm thời.
- Là lớp bên dưới cho một số implementation `LoadBalancer`.

NodePort mở surface trên node, nên production thường không expose trực tiếp ra internet nếu không có firewall, load balancer hoặc ingress strategy rõ ràng.

### LoadBalancer

`LoadBalancer` yêu cầu hạ tầng bên ngoài tạo load balancer trỏ vào Service.

```yaml
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
```

Trong managed Kubernetes, cloud controller thường tạo cloud L4 load balancer. Trong K3s, `LoadBalancer` có thể được xử lý bởi ServiceLB bundled component nếu còn bật. Trong bare-metal Kubernetes chuẩn, Service `LoadBalancer` thường `Pending` cho đến khi cài MetalLB hoặc một load balancer integration tương đương.

### ExternalName

`ExternalName` không tạo proxy hay endpoints. Nó tạo DNS CNAME từ Service name sang DNS name bên ngoài.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-api
spec:
  type: ExternalName
  externalName: api.example.com
```

Use case:

- Cho app dùng DNS name nội bộ ổn định, nhưng target thực tế nằm ngoài cluster.
- Migration từng bước từ external service vào cluster hoặc ngược lại.

Không dùng `ExternalName` nếu cần load balancing, health check, mTLS hoặc policy phức tạp ở Kubernetes layer.

### Headless Service

Headless Service dùng `clusterIP: None`. Kubernetes không cấp virtual IP. DNS trả về endpoint IPs trực tiếp.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-headless
spec:
  clusterIP: None
  selector:
    app: web
  ports:
  - name: http
    port: 8080
    targetPort: 8080
```

Use case:

- Stateful workloads cần stable network identity theo Pod.
- Client-side discovery.
- Database/cache cluster cần biết từng peer.

Day 10 đã nói `StatefulSet`; Headless Service là mảnh networking thường đi cùng StatefulSet.

### Port, targetPort và named port

| Field | Ý nghĩa |
|---|---|
| `port` | Port của Service mà client gọi |
| `targetPort` | Port trên container/Pod backend |
| `nodePort` | Port mở trên node khi type là `NodePort` hoặc một số `LoadBalancer` |
| `name` | Tên port, cần thiết khi nhiều ports và hữu ích cho tooling |

Sai `targetPort` là lỗi rất phổ biến: Service có endpoints nhưng traffic vẫn fail vì forward vào port không có process listen.

### EndpointSlice

Kubernetes dùng `EndpointSlice` để lưu danh sách endpoint backend cho Service. EndpointSlice scale tốt hơn object `Endpoints` cũ khi số lượng backend lớn.

Luồng cơ bản:

```text
Service selector -> Pods Ready match labels -> EndpointSlices -> kube-proxy/dataplane rules -> traffic to Pod IP
```

Nếu Pod chưa Ready, endpoint có thể không được đưa vào danh sách ready. Vì vậy probe configuration ảnh hưởng trực tiếp đến Service traffic.

## Deep dive: Traffic đi qua Service như thế nào

```text
Client Pod
  |
  | DNS query: web.day15.svc.cluster.local
  v
CoreDNS returns ClusterIP
  |
  | TCP connect to ClusterIP:port
  v
kube-proxy/dataplane rule on node
  |
  | choose backend endpoint
  v
Pod IP:targetPort
```

Service không inspect HTTP path/header. Nó load balance ở L4. HTTP routing theo host/path thuộc bài `Ingress` ở Day 17 hoặc Gateway API/service mesh ở các bài sau.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| `ClusterIP` | Giống upstream | Giống upstream | Giống upstream |
| `NodePort` | Giống upstream, phụ thuộc node/network lab | Giống upstream | Có thể bị firewall/security group giới hạn |
| `LoadBalancer` | Thường có ServiceLB bundled nếu không disable | Cần cloud-controller, MetalLB hoặc integration khác | Cloud LB tự tạo, có chi phí và annotation riêng |
| Ingress path | K3s thường có Traefik mặc định | Tự cài ingress controller | Cloud ingress/LB controller tùy provider |
| External IP | Phụ thuộc node IP, k3d port mapping hoặc ServiceLB | Phụ thuộc hạ tầng | Cloud provider cấp hostname/IP |

Trong K3s lab, `LoadBalancer` có thể hoạt động khác cloud production. Đừng suy luận rằng một Service `LoadBalancer` local tương đương AWS NLB, GCP Load Balancer hoặc Azure Load Balancer về health check, source IP, cost, firewall và annotations.

Matrix truy cập thực tế:

| Môi trường | `NodePort` từ máy học viên | `LoadBalancer` | Caveat chính |
|---|---|---|---|
| k3d | Chỉ vào được nếu map port khi tạo cluster | Phụ thuộc k3d/K3s ServiceLB và port mapping | Host không tự thấy mọi node port trong container network |
| K3s trên VM/Linux | Vào được nếu node IP reachable và firewall mở | ServiceLB có thể cấp external IP nếu chưa disable | Node IP, firewall và interface binding quyết định kết quả |
| Bare-metal Kubernetes chuẩn | Vào được nếu network/firewall cho phép | Thường `Pending` nếu chưa có MetalLB/cloud integration | Cần LB implementation riêng |
| EKS/GKE/AKS | Thường bị security group/firewall chặn nếu không mở | Cloud LB thật, có cost và annotations riêng | Health check, source IP và firewall phụ thuộc provider |

## Trade-offs và Best Practices

### Trade-offs

| Type | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| `ClusterIP` | Internal service-to-service | Ít overhead, route nội bộ | Thấp | Selector/targetPort sai |
| `NodePort` | Lab, debug, bare-metal đơn giản | Extra hop có thể xảy ra | Trung bình vì firewall/node exposure | Mở port ngoài ý muốn |
| `LoadBalancer` | Public/private L4 entrypoint | Phụ thuộc cloud LB/dataplane | Trung bình, có cost | Pending, health check fail, source IP mất |
| `ExternalName` | DNS alias tới external service | DNS only, không proxy | Thấp | Không có health check/endpoints |
| Headless | Stateful discovery/client-side LB | Client chịu discovery/LB | Trung bình | Client không xử lý endpoint churn |

### Best Practices

Nên làm:

- Dùng `ClusterIP` cho service nội bộ mặc định.
- Dùng `Ingress` hoặc Gateway/API gateway cho HTTP public traffic thay vì tạo quá nhiều `LoadBalancer`.
- Đặt port name rõ ràng như `http`, `grpc`, `metrics`.
- Giữ Service selector cụ thể và ổn định.
- Kiểm tra `EndpointSlice` sau khi tạo Service.
- Set readiness probe đúng để Pod chỉ nhận traffic khi sẵn sàng.
- Với cloud `LoadBalancer`, review annotations, health check, firewall/security group và chi phí.
- Với K3s/bare-metal, hiểu rõ ServiceLB/MetalLB đang cấp external IP như thế nào.

Tránh làm:

- Expose mọi service bằng `NodePort`.
- Dùng `LoadBalancer` cho từng microservice nội bộ.
- Gọi trực tiếp Pod IP từ app khác.
- Đặt selector quá rộng.
- Quên `targetPort` khi container không listen cùng port với Service.
- Coi `ExternalName` là reverse proxy.
- Dùng Headless Service cho app client không xử lý endpoint changes.

## Performance Considerations

- Service routing thêm một lớp NAT hoặc dataplane lookup, thường nhỏ nhưng có ý nghĩa ở traffic rất lớn.
- `externalTrafficPolicy: Local` có thể giữ source IP tốt hơn nhưng chỉ route tới node có local endpoints, cần load balancer health check đúng.
- `externalTrafficPolicy: Cluster` phân phối rộng hơn nhưng có thể thêm cross-node hop và thay đổi source IP.
- NodePort/LoadBalancer có thể đi qua nhiều lớp: cloud LB -> node port -> kube-proxy -> Pod.
- EndpointSlice giúp scale tốt hơn khi Service có nhiều endpoints.
- Readiness probe quá chậm làm endpoint vào service chậm; quá lỏng làm traffic vào Pod chưa sẵn sàng.
- Headless Service đẩy trách nhiệm load balancing và retry sang client.

## Debugging Checklist

Service không có backend:

```bash
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl describe service <service> -n <namespace>
kubectl get pods -n <namespace> --show-labels
kubectl get pods -n <namespace> -l '<selector>'
```

Service có endpoints nhưng gọi fail:

```bash
kubectl describe service <service> -n <namespace>
kubectl get pods -n <namespace> -o wide
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace>
kubectl port-forward service/<service> 8080:<service-port> -n <namespace>
```

Test từ trong cluster:

```bash
kubectl run curl -n <namespace> --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- http://<service>:<port>
```

Nếu cần chạy shell loop trong image `curl`, phải dùng `--command --` để `sh -c` là command của container, không bị truyền thành args cho entrypoint `curl`:

```bash
kubectl run curl-loop -n <namespace> --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh -c 'for i in 1 2 3; do curl -s http://<service>:<port>; echo; done'
```

Fallback dùng BusyBox:

```bash
kubectl run wget-test -n <namespace> --rm -it --restart=Never --image=busybox:1.36 --command -- wget -qO- http://<service>:<port>
```

LoadBalancer pending:

```bash
kubectl get svc -n <namespace>
kubectl describe svc <service> -n <namespace>
kubectl get pods -A | grep -E 'traefik|svclb|metallb|cloud'
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Production fix phải xác định đây là lỗi Kubernetes metadata, dataplane, cloud load balancer, firewall hay app readiness. Đừng sửa bằng cách đổi type lung tung khi chưa biết layer nào fail.

## Liên hệ với kiến thức đã biết

`Service` giống service discovery và L4 load balancing primitive. Nó không thay thế API Gateway, reverse proxy hay service mesh. Với microservices, Service là endpoint nội bộ ổn định để app gọi nhau; Ingress/Gateway là lớp expose HTTP bên ngoài; NetworkPolicy là lớp kiểm soát ai được gọi ai.

## Tóm tắt

`ClusterIP` là default cho internal service. `NodePort` mở port trên node, hữu ích cho lab/debug nhưng cần cẩn trọng production. `LoadBalancer` tích hợp với hạ tầng bên ngoài, khác nhau mạnh giữa K3s, bare-metal và cloud. `ExternalName` là DNS alias. Headless Service phục vụ discovery trực tiếp, đặc biệt cho stateful workloads. Debug Service luôn bắt đầu từ selector, endpoints, port mapping, readiness và môi trường cấp external IP.

## Câu hỏi tự kiểm tra

1. Vì sao client không nên gọi trực tiếp Pod IP?
2. `port`, `targetPort` và `nodePort` khác nhau thế nào?
3. Service có `ClusterIP` nhưng không có endpoints thường do đâu?
4. K3s `LoadBalancer` khác cloud `LoadBalancer` ở điểm nào?
5. Khi nào dùng Headless Service thay vì `ClusterIP`?

## Tài liệu tham khảo

- Kubernetes Service: https://kubernetes.io/docs/concepts/services-networking/service/
- Kubernetes EndpointSlices: https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/
- Kubernetes DNS for Services and Pods: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- Kubernetes Ingress overview: https://kubernetes.io/docs/concepts/services-networking/ingress/
- K3s Networking Services: https://docs.k3s.io/networking/networking-services
- K3s Packaged Components: https://docs.k3s.io/installation/packaged-components
