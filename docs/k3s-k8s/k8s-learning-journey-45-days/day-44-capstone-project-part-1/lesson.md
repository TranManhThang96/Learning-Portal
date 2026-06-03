# Day 44: Capstone Project Part 1

## Mục tiêu bài học

- Thiết kế architecture cho hệ thống giao vận microservices trên Kubernetes.
- Deploy `api-gateway` và 2-3 microservices bằng Helm hoặc manifest có cấu trúc.
- Cấu hình `Service`, `Ingress`, `ConfigMap`, `Secret`, probes và resources cho workload stateless.
- Debug được luồng traffic từ Ingress đến API Gateway rồi tới service nội bộ.
- Ghi lại trade-offs để chuẩn bị hoàn thiện stateful, observability, GitOps và backup ở Day 45.

## Vấn đề cần giải quyết

Sau 43 ngày học từng mảnh, capstone buộc bạn ghép lại thành một hệ thống có shape gần production. Mục tiêu không phải viết business logic phức tạp, mà là chứng minh bạn hiểu:

- Service nào expose ra ngoài, service nào chỉ nội bộ.
- Routing đi qua Ingress/API Gateway như thế nào.
- Config/secret được inject ra sao.
- Workload có resource/probe/PDB cơ bản.
- Helm chart tổ chức nhiều service ra sao.
- Khi request lỗi, debug theo object graph.

## Capstone scope

Hệ thống giao vận gồm:

```text
Client
  |
  v
Ingress
  |
  v
api-gateway
  |
  +--> order-service
  +--> tracking-service
  +--> notification-service hoặc payment-service
```

Day 44 tập trung vào stateless layer:

- Namespace.
- API Gateway.
- 2-3 microservices.
- Service nội bộ.
- Ingress.
- Helm chart làm main path, manifest raw chỉ dùng để hiểu resource được render.
- Debug routing.

Day 45 sẽ thêm:

- PostgreSQL.
- Redis.
- Kafka.
- Monitoring.
- GitOps.
- Backup.
- Production checklist.

## Mental Model

```text
External traffic
  -> cloud/local LoadBalancer
  -> Ingress controller
  -> Ingress rule
  -> api-gateway Service
  -> api-gateway Pod
  -> internal ClusterIP Service
  -> backend Pod
```

Khi lỗi xảy ra, debug theo chiều request đi qua. Không nhảy thẳng vào app log nếu `Service` chưa có endpoints hoặc Ingress rule trỏ sai service.

## Lý thuyết cốt lõi

### Namespace và ownership

Capstone nên dùng namespace riêng:

```text
logistics
```

Labels chuẩn:

```yaml
app.kubernetes.io/part-of: logistics-platform
app.kubernetes.io/name: order-service
app.kubernetes.io/component: backend
app.kubernetes.io/managed-by: Helm
```

Labels giúp:

- Query resource.
- Debug theo service.
- Prometheus/service discovery.
- Cost allocation.
- Policy target.

### API Gateway trong Kubernetes

API Gateway có thể là:

- App gateway do team viết.
- NGINX/Envoy/Kong/Traefik gateway.
- Cloud API Gateway ngoài cluster.
- Service mesh ingress gateway.

Trong capstone, gateway phải route thật tới backend, ví dụ NGINX reverse proxy `/orders` tới `order-service` và `/tracking` tới `tracking-service`. Nếu chỉ chạy NGINX default page ở gateway, bạn chưa chứng minh được service discovery hoặc gateway routing. Production gateway thường xử lý auth, rate limit, request routing, timeout, retry và observability.

### Service types

Backend services nên dùng `ClusterIP`:

```text
order-service.logistics.svc.cluster.local
tracking-service.logistics.svc.cluster.local
```

Chỉ edge layer cần expose qua Ingress/LoadBalancer. Không nên tạo `NodePort`/`LoadBalancer` cho từng internal service nếu không có yêu cầu thật.

### Ingress

Ingress mô tả HTTP routing:

```text
Host: logistics.local
Path: /
  -> api-gateway Service
```

Ingress controller mới là component thực thi rule. Trong K3s, Traefik thường có sẵn. Trong managed Kubernetes, có thể dùng NGINX, cloud LB controller hoặc Gateway API/controller.

### Helm organization

Hai hướng:

```text
Chart tổng:
  templates/deployment.yaml
  values.yaml chứa services[]
```

hoặc:

```text
Chart reusable microservice:
  cài nhiều release:
    api-gateway
    order-service
    tracking-service
```

Với capstone nhỏ, một chart tổng dễ nhìn. Với production nhiều service/team, reusable chart hoặc chart per service dễ ownership hơn.

## Deep dive: Debug traffic path

Object graph:

```text
Ingress
  -> Service api-gateway
  -> EndpointSlice api-gateway
  -> Pod api-gateway Ready
  -> Service order-service
  -> EndpointSlice order-service
  -> Pod order-service Ready
```

Commands:

```bash
kubectl get ingress,svc,endpointslice,pod -n logistics
kubectl describe ingress logistics -n logistics
kubectl describe svc api-gateway -n logistics
kubectl get endpointslice -n logistics
kubectl logs deploy/api-gateway -n logistics
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
```

Nếu Service không có endpoints, thường do selector không khớp label Pod hoặc Pod chưa Ready.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Day 44 triển khai thế nào | Điểm cần đổi khi production |
|---|---|---|
| K3s/k3d | Dùng Traefik/Ingress local, `ClusterIP`, image public | DNS/TLS local chỉ là mô phỏng |
| Self-managed | Cần chọn Ingress controller, LB layer, DNS/TLS | MetalLB/hardware LB, cert-manager |
| EKS/GKE/AKS | Dùng cloud LB/Ingress controller, external-dns, cert-manager/cloud cert | IAM, subnet tags, LB cost, health checks |

Manifest workload stateless gần như giống nhau giữa các môi trường. Khác biệt lớn nằm ở LB, DNS, TLS, identity và observability integration.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Trade-off |
|---|---|---|
| Một chart tổng | Capstone, demo, app nhỏ | Ownership kém khi nhiều team |
| Chart per service | Team/service độc lập | Nhiều release cần quản lý |
| API Gateway trong cluster | Routing gần service, dễ GitOps | Gateway phụ thuộc cluster |
| API Gateway ngoài cluster | Enterprise edge, auth centralized | Config split, network hop |
| Expose từng service | Debug/demo nhanh | Attack surface lớn, cost cao |
| Chỉ expose gateway | Microservices production | Gateway là critical path |

### Best Practices

- Dùng namespace riêng và labels chuẩn.
- Internal service dùng `ClusterIP`.
- Chỉ expose API Gateway qua Ingress.
- Mỗi Deployment có requests/probes.
- Không hardcode service IP; dùng DNS service name.
- Dùng ConfigMap cho endpoint/config không nhạy cảm.
- Dùng Secret cho token/password nhưng không commit plaintext production.
- Ghi architecture decision trong README.
- Tạo ít nhất một lỗi routing để luyện debug.

## Performance Considerations

Capstone stateless layer cần nghĩ về:

- API Gateway thêm một hop, ảnh hưởng latency nhưng giúp centralize policy.
- Requests quá thấp làm overcommit và latency spike.
- Limits CPU quá thấp có thể gây throttling.
- Readiness probe quá nặng làm tăng load.
- Ingress controller là shared bottleneck.
- Service DNS lookup thường ổn, nhưng app nên reuse connection/pool.

Trong production, gateway cần timeout, retry, circuit breaker và rate limit hợp lý. Retry sai có thể tạo retry storm xuống backend.

## Debugging Checklist

Khi client không gọi được:

```bash
kubectl get ingress -n logistics
kubectl describe ingress logistics -n logistics
kubectl get svc,endpoints,endpointslice -n logistics
kubectl get pods -n logistics -o wide
kubectl describe pod <pod> -n logistics
kubectl logs deploy/api-gateway -n logistics
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
kubectl get events -n logistics --sort-by=.lastTimestamp
```

Symptom:

| Symptom | Root cause phổ biến |
|---|---|
| 404 từ Ingress | Host/path rule sai hoặc controller chưa nhận rule |
| 503 từ Ingress | Service không có endpoints hoặc Pod chưa Ready |
| Gateway gọi backend timeout | DNS/service/network policy/backend down |
| `curl service` fail trong Pod | Service name/namespace sai |
| Pod Ready false | Readiness path/port sai |

## Liên hệ với kiến thức đã biết

Bạn đã quen microservices/API Gateway ở mức application architecture. Kubernetes thêm runtime contract: service discovery qua DNS, load balancing qua Service, rollout qua Deployment, config qua ConfigMap/Secret, và traffic edge qua Ingress. Capstone là nơi nối system design với operational manifests.

## Tóm tắt

- Day 44 xây stateless foundation cho hệ thống giao vận.
- Chỉ API Gateway nên expose ra ngoài; backend dùng `ClusterIP`.
- Debug traffic theo object graph từ Ingress đến Pod.
- Helm giúp package nhưng không thay thế quyết định kiến trúc.
- Day 45 sẽ hoàn thiện stateful, monitoring, GitOps, backup và production review.

## Câu hỏi tự kiểm tra

1. Vì sao backend service không nên dùng `LoadBalancer` riêng trong capstone?
2. Ingress khác Ingress controller ở đâu?
3. Service không có endpoints thường do lỗi gì?
4. Khi chuyển từ K3s sang EKS/GKE/AKS, phần nào phải thay đổi?
5. Một chart tổng và chart per service khác nhau về ownership thế nào?

## Tài liệu tham khảo

- Kubernetes Services: https://kubernetes.io/docs/concepts/services-networking/service/
- Kubernetes Ingress: https://kubernetes.io/docs/concepts/services-networking/ingress/
- Helm Documentation: https://helm.sh/docs/
- Kubernetes Recommended Labels: https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/
