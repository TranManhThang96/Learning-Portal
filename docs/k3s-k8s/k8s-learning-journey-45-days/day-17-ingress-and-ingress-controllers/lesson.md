# Day 17: Ingress và Ingress controllers

## Mục tiêu bài học

- Hiểu `Ingress` là API object mô tả HTTP/HTTPS routing, không phải proxy tự chạy.
- Phân biệt `Ingress`, `Ingress controller`, `Service` và cloud/bare-metal load balancer.
- Viết được rule host/path routing với `ingressClassName`, `pathType` và backend Service.
- Hiểu TLS termination bằng Secret `kubernetes.io/tls` và ranh giới trách nhiệm của controller.
- Debug được lỗi 404, 503, TLS sai cert, controller không reconcile và backend không có endpoints.

## Vấn đề cần giải quyết

`Service` expose L4 traffic. Nhưng hệ thống microservices thực tế thường cần HTTP routing theo host/path:

```text
api.example.com/orders   -> order-service
api.example.com/payments -> payment-service
admin.example.com        -> admin-service
```

Nếu mỗi service public HTTP tạo một `LoadBalancer`, chi phí và vận hành tăng nhanh. `Ingress` gom nhiều route HTTP/HTTPS vào một hoặc vài entrypoints, phía sau vẫn route tới `Service` nội bộ.

## Mental Model

```text
External client
  |
  v
LoadBalancer / NodePort / port-forward
  |
  v
Ingress controller Pod
  |
  | reads Ingress objects
  v
Service ClusterIP
  |
  v
Backend Pods
```

`Ingress` là desired state. `Ingress controller` là runtime component biến desired state thành config thật cho proxy như Traefik, NGINX hoặc HAProxy.

## Lý thuyết cốt lõi

### Ingress resource

`Ingress` thuộc API `networking.k8s.io/v1`. Nó mô tả host, path và backend Service.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app
spec:
  ingressClassName: traefik
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 8080
```

Nếu không có Ingress controller đang chạy, object này vẫn được tạo nhưng không có traffic routing thật.

### Ingress controller

Controller watch `Ingress`, `Service`, `EndpointSlice` và Secret TLS, sau đó cấu hình proxy/load balancer.

Controller phổ biến:

- Traefik: thường có sẵn trong K3s, cấu hình đơn giản cho lab/small cluster.
- NGINX Ingress Controller: phổ biến, nhiều annotation, cộng đồng lớn.
- HAProxy Ingress: phù hợp khi team quen HAProxy và cần performance/control.
- Cloud ingress controller: AWS Load Balancer Controller, GKE Ingress, Azure Application Gateway Ingress Controller tùy cloud.

Annotation thường là controller-specific. Một manifest dùng annotation của NGINX có thể không chạy giống vậy trên Traefik.

### IngressClass

`ingressClassName` chỉ định controller nào xử lý Ingress.

```bash
kubectl get ingressclass
```

Trong K3s mặc định, thường có class `traefik`. Trong cluster khác có thể là `nginx`, `haproxy` hoặc class do cloud provider tạo.

Nếu cluster có nhiều controller, không set `ingressClassName` có thể dẫn đến:

- Không controller nào xử lý.
- Sai controller xử lý.
- Behavior khác nhau giữa môi trường.

### Host routing và path routing

Ingress routing thường dựa trên:

- `host`: domain HTTP Host header.
- `path`: URL path.
- `pathType`: cách match path.

`pathType` chính:

| pathType | Ý nghĩa |
|---|---|
| `Exact` | Match đúng path |
| `Prefix` | Match prefix theo path segment |
| `ImplementationSpecific` | Controller tự định nghĩa, kém portable |

Production nên dùng `Exact` hoặc `Prefix` rõ ràng. Tránh dựa vào behavior controller-specific nếu muốn manifest portable.

### Prefix routing không đồng nghĩa path rewrite

Ingress `path: /api` với `pathType: Prefix` thường forward nguyên request path `/api/...` tới backend. Nó không tự strip prefix thành `/...`.

Nếu backend chỉ phục vụ `/` nhưng Ingress route `/api`, bạn cần một trong các hướng sau:

- Sửa backend để hiểu base path `/api`.
- Dùng annotation/middleware rewrite của controller cụ thể, ví dụ Traefik Middleware hoặc NGINX rewrite annotation.
- Đặt API Gateway/app gateway phía sau Ingress để xử lý routing/transform rõ ràng hơn.

Rewrite là controller-specific, nên manifest dùng rewrite sẽ kém portable hơn manifest chỉ dùng host/path routing chuẩn.

### TLS termination

Ingress có thể terminate TLS bằng Secret chứa cert/key:

```yaml
spec:
  tls:
  - hosts:
    - app.example.com
    secretName: app-tls
```

Secret thường được tạo:

```bash
kubectl create secret tls app-tls --cert=tls.crt --key=tls.key
```

Trong production, cert thường do `cert-manager`, cloud certificate manager hoặc platform team cấp. Không quản lý cert thủ công cho nhiều service nếu hệ thống lớn.

### Ingress không phải API Gateway đầy đủ

Ingress làm HTTP routing cơ bản. Nó không mặc định có:

- Authentication/authorization theo user.
- Rate limiting portable giữa controller.
- Request/response transformation chuẩn.
- Canary phức tạp portable.
- Service discovery ngoài Kubernetes.

Một số controller làm được qua annotation/plugin, nhưng khi cần policy L7 phức tạp, hãy cân nhắc API Gateway, Gateway API hoặc service mesh tùy bài toán.

## Deep dive: Controller reconcile route như thế nào

```text
1. User apply Ingress.
2. API server lưu desired routing.
3. Ingress controller watch object.
4. Controller đọc IngressClass để quyết định có quản lý object không.
5. Controller đọc Service backend và EndpointSlice.
6. Controller generate config cho proxy.
7. Proxy reload/dynamic update.
8. Client traffic đi vào controller và được proxy tới Service/Pod.
```

Lỗi có thể nằm ở từng bước. Ví dụ:

- IngressClass sai: controller bỏ qua object.
- Host header sai: route không match, thường 404.
- Backend Service sai tên: controller match route nhưng không có upstream, thường 503.
- Service không endpoints: proxy có route nhưng backend rỗng.
- TLS Secret sai namespace hoặc sai key: HTTPS fail hoặc dùng default cert.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Controller mặc định | K3s thường đóng gói Traefik | Không có sẵn, team tự cài | Có cloud ingress/LB options, vẫn có thể cài NGINX/Traefik |
| External access | Traefik thường expose qua ServiceLB nếu bật | Cần NodePort/LB/MetalLB/cloud LB | Cloud LB hoặc managed ingress tạo tài nguyên cloud |
| Cấu hình controller | `HelmChartConfig` cho packaged Traefik | Helm values/manifest tự quản | Annotation/provider-specific resources |
| Disable default | `k3s server --disable=traefik` | Không áp dụng | Tùy add-on/provider |
| Production caveat | Traefik mặc định tốt cho lab, cần review config production | Toàn bộ lifecycle do team quản lý | Cost, security group, IAM, cloud health check |

K3s tạo trải nghiệm thuận tiện vì có Traefik/CoreDNS/ServiceLB mặc định. Nhưng production vẫn cần quyết định rõ: dùng Traefik mặc định, tự quản NGINX/HAProxy, hay chuyển sang managed/cloud ingress.

## Trade-offs và Best Practices

### Trade-offs

| Option | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Traefik bundled K3s | Lab, small cluster, muốn nhanh | Đủ tốt cho nhiều use case nhỏ | Thấp | Config mặc định không khớp production need |
| NGINX Ingress | Phổ biến, nhiều docs/annotation | Tốt, reload/config size cần theo dõi | Trung bình | Annotation drift, reload issue |
| HAProxy Ingress | Cần HAProxy behavior/control | Mạnh cho L7/L4 proxy | Trung bình | Tuning phức tạp |
| Cloud ingress | Tích hợp cloud LB/cert/WAF | Phụ thuộc cloud LB | Trung bình-cao | Cost, quota, provider annotation |
| API Gateway/Gateway API | Policy L7 phức tạp | Tùy implementation | Cao hơn | Overkill nếu chỉ routing đơn giản |

### Best Practices

Nên làm:

- Luôn set `ingressClassName`.
- Dùng `ClusterIP` Service làm backend cho Ingress.
- Tách public host/path rõ ràng, không để wildcard quá rộng nếu không cần.
- Quản lý TLS bằng `cert-manager` hoặc cloud certificate workflow trong production.
- Chuẩn hóa annotation theo controller đang dùng.
- Theo dõi controller logs, reload errors, 4xx/5xx, latency và upstream health.
- Đặt resource requests/limits cho Ingress controller.
- Có ít nhất 2 replicas controller trong production nếu controller hỗ trợ và hạ tầng LB phù hợp.

Tránh làm:

- Tạo một `LoadBalancer` cho từng microservice HTTP public.
- Dùng annotation của controller A rồi deploy lên controller B.
- Quên backend Service/EndpointSlice khi debug 503.
- Dùng `ImplementationSpecific` nếu không có lý do.
- Lưu private key TLS trong repo plaintext.
- Coi Ingress controller là service mesh hoặc API Gateway đầy đủ.

## Performance Considerations

- Ingress controller là shared choke point cho nhiều service, cần scale và monitor riêng.
- TLS termination tiêu tốn CPU; bật HTTP/2, keep-alive và cipher phù hợp theo controller.
- Large config hoặc quá nhiều Ingress rules có thể làm reload chậm ở một số controller.
- Path regex/annotation phức tạp có thể tăng latency và khó debug.
- Backend Service vẫn chịu ảnh hưởng của kube-proxy/dataplane Day 16.
- `readinessProbe` của backend quyết định endpoint có được proxy nhận traffic không.
- Cloud ingress có thêm latency/cost từ external load balancer, WAF, cross-zone routing.

## Debugging Checklist

Kiểm tra controller và class:

```bash
kubectl get ingressclass
kubectl -n kube-system get pods,svc | grep -E 'traefik|ingress|nginx|haproxy'
kubectl describe ingress <ingress> -n <namespace>
```

Kiểm tra route:

```bash
kubectl get ingress -n <namespace> -o wide
kubectl describe ingress <ingress> -n <namespace>
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl get pods -n <namespace> -o wide --show-labels
```

Kiểm tra logs controller:

```bash
kubectl -n kube-system logs deploy/traefik --tail=100
kubectl -n ingress-nginx logs deploy/ingress-nginx-controller --tail=100
```

Test host/path:

```bash
curl -H 'Host: app.example.com' http://<ingress-ip>/api
curl -k --resolve app.example.com:443:<ingress-ip> https://app.example.com/api
```

Symptom thường gặp:

- 404: host/path không match hoặc request không đi tới đúng controller.
- 503: route match nhưng backend Service/Endpoint rỗng hoặc upstream fail.
- TLS default cert: Secret sai, host không match SNI, controller chưa load cert.
- Ingress không có address: controller/LB chưa provision hoặc class sai.

## Liên hệ với kiến thức đã biết

Ingress controller giống reverse proxy/API edge layer ở mức Kubernetes-native. Với microservices, nó thường đứng trước API Gateway hoặc thay API Gateway cho routing đơn giản. Day 15 Service là backend ổn định, Day 16 dataplane chuyển packet tới Pod, Day 17 thêm HTTP host/path/TLS ở entrypoint.

## Tóm tắt

`Ingress` là object khai báo HTTP/HTTPS routing; cần `Ingress controller` để chạy thật. K3s thường có Traefik mặc định, Kubernetes tự dựng phải cài controller, managed Kubernetes có cloud-specific option. Production cần chuẩn hóa `IngressClass`, TLS workflow, annotation, monitoring và debug path từ controller tới Service/EndpointSlice. Ingress tốt cho routing cơ bản, nhưng không thay thế toàn bộ API Gateway hoặc service mesh.

## Câu hỏi tự kiểm tra

1. Vì sao tạo Ingress thành công nhưng traffic không route?
2. `Ingress` khác `Ingress controller` ở điểm nào?
3. `pathType: Prefix` khác `Exact` như thế nào?
4. Lỗi 404 và 503 trong Ingress thường khác nhau ở layer nào?
5. K3s Traefik mặc định khác gì so với cloud ingress controller?

## Tài liệu tham khảo

- Kubernetes Ingress: https://kubernetes.io/docs/concepts/services-networking/ingress/
- Kubernetes Ingress Controllers: https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/
- kubectl create ingress reference: https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_ingress/
- K3s Networking Services: https://docs.k3s.io/networking/networking-services
- K3s HelmChartConfig for packaged components: https://docs.k3s.io/add-ons/helm
