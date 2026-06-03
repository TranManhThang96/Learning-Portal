# Day 21: Service Mesh introduction

## Mục tiêu bài học

- Hiểu service mesh giải quyết vấn đề gì khi hệ thống microservices đã vượt quá khả năng của `Service`, `Ingress` và application code tự xử lý.
- Phân biệt data plane, control plane, sidecar proxy, ambient/proxyless pattern ở mức khái niệm.
- Nắm được các năng lực chính: mTLS, traffic splitting, retries/timeouts, circuit breaking, telemetry và policy.
- So sánh Istio và Linkerd theo độ mạnh, độ phức tạp và chi phí vận hành.
- Biết khi nào không nên dùng service mesh vì nó là overkill.

## Vấn đề cần giải quyết

Từ Day 15-20, bạn đã biết Kubernetes có `Service`, `Ingress`, DNS, `NetworkPolicy` và CNI. Các primitive đó giúp traffic đi được, nhưng chúng không giải quyết hết các câu hỏi ở tầng service-to-service:

- Service A gọi Service B có được mã hóa và xác thực không?
- Release version mới có thể chỉ nhận 5% traffic không?
- Timeout/retry policy có nhất quán giữa nhiều ngôn ngữ không?
- Team platform có quan sát được latency, error rate và request volume giữa service không?
- Có thể áp policy "frontend chỉ được gọi api, api chỉ được gọi payment" ở cấp service identity không?

Nếu để từng application tự xử lý, mỗi team sẽ implement khác nhau. Service mesh đưa các concern đó xuống một lớp hạ tầng chung, thường bằng proxy đứng cạnh workload hoặc dataplane riêng.

## Mental Model

```text
Application container
  |
  v
Local proxy / mesh dataplane
  |
  v
Service-to-service network
  |
  v
Remote proxy / mesh dataplane
  |
  v
Remote application container
```

Application vẫn gọi DNS/Service như bình thường. Mesh chèn thêm dataplane để kiểm soát traffic, mã hóa, thu telemetry và áp policy. Control plane cấu hình proxy/dataplane dựa trên Kubernetes objects và mesh-specific resources.

## Lý thuyết cốt lõi

### Control plane và data plane

Service mesh có hai phần:

- `Control plane`: đọc Kubernetes API, certificate, mesh policy, traffic rule; sau đó phân phối cấu hình xuống dataplane.
- `Data plane`: xử lý traffic thực tế giữa Pods, thường là sidecar proxy như Envoy hoặc một proxy nhẹ hơn.

Khi debug mesh, luôn tách rõ:

- Kubernetes object có đúng không?
- Sidecar/dataplane có được inject không?
- Control plane có healthy không?
- Proxy có nhận config mới không?
- Traffic fail ở DNS, Service endpoint, policy, TLS hay application?

### Sidecar proxy

Pattern phổ biến là mỗi Pod có thêm container proxy:

```text
Pod
├── app container
└── sidecar proxy
```

Traffic vào/ra Pod được iptables/eBPF/routing rule chuyển qua proxy. Proxy thực hiện mTLS, routing, telemetry, retry, timeout và policy. Ưu điểm là app không cần đổi code nhiều. Chi phí là mỗi Pod thêm CPU, memory, startup dependency và một lớp debug mới.

### mTLS và service identity

`mTLS` nghĩa là cả client và server đều dùng certificate để xác thực nhau, không chỉ server-side TLS như HTTPS thông thường. Trong mesh:

- Workload được cấp identity, thường dựa trên `ServiceAccount`.
- Proxy dùng certificate ngắn hạn cho identity đó.
- Traffic giữa workload trong mesh được mã hóa.
- Policy có thể nói "identity A được gọi identity B" thay vì dựa vào IP động.

Điểm quan trọng: mTLS mesh bảo vệ traffic trong cluster hoặc giữa mesh workloads. Nó không thay thế secret management, RBAC, Pod Security, image scanning hoặc application-level authorization.

### Traffic management

Mesh có thể route theo version, header, weight hoặc failover:

```text
client -> reviews service
           ├── v1: 90%
           └── v2: 10%
```

Use case phổ biến:

- Canary release.
- Blue/green switching.
- A/B test.
- Mirror traffic sang service mới.
- Timeout/retry policy nhất quán.

Rủi ro: retry sai có thể khuếch đại lỗi. Nếu request không idempotent, retry có thể tạo side effect trùng. Timeout quá dài giữ tài nguyên, timeout quá ngắn gây lỗi giả.

### Observability

Mesh nhìn thấy request giữa services nên có thể sinh:

- Request rate.
- Error rate.
- Latency p50/p95/p99.
- Dependency graph.
- TLS status.
- Policy deny/allow signal.

Telemetry mesh rất hữu ích, nhưng không thay thế application logs, metrics business hoặc distributed tracing có instrumentation đúng trong code. Mesh thấy network/request layer; app vẫn phải expose domain signal.

### Authorization policy

Mesh authorization thường dùng identity và workload metadata:

```text
frontend service account -> allowed -> api
debug service account    -> denied  -> payment
```

So với `NetworkPolicy`, mesh policy có thể gần với service identity hơn và trong một số mesh có thể áp thêm L7 rule như path/method/header. Nhưng mesh policy chỉ áp trên traffic đi qua mesh. Workload không được inject hoặc traffic bypass proxy có thể nằm ngoài phạm vi nếu cluster không cấu hình chặt.

### Istio

Istio là service mesh nhiều tính năng, dùng Envoy làm dataplane. Nó phù hợp khi hệ thống cần:

- Traffic management phức tạp.
- mTLS và authorization policy mạnh.
- Gateway/API edge integration.
- Multi-cluster/multi-network.
- L7 telemetry và extensibility sâu.

Chi phí:

- Nhiều CRD và khái niệm.
- Nặng hơn về CPU/memory.
- Upgrade và debug phức tạp hơn.
- Dễ bị dùng quá mức nếu team chưa có operational maturity.

### Linkerd

Linkerd tập trung vào trải nghiệm đơn giản hơn, proxy nhẹ và mTLS mặc định. Nó phù hợp khi team muốn:

- mTLS service-to-service nhanh.
- Golden metrics và tap/top đơn giản.
- Ít cấu hình hơn.
- Learning curve thấp hơn Istio.

Chi phí:

- Ít tính năng advanced traffic/gateway hơn Istio.
- Một số use case phức tạp cần extension hoặc tool khác.
- Vẫn cần vận hành control plane, proxy injection và certificate lifecycle.

### Khi nào không nên dùng service mesh

Service mesh là overkill nếu:

- Cluster có ít service, dependency graph đơn giản.
- Team chưa debug vững `Service`, DNS, Ingress, CNI và NetworkPolicy.
- Nhu cầu chỉ là north-south ingress routing.
- App chưa có readiness/timeout/retry discipline cơ bản.
- Chi phí CPU/memory/latency không được chấp nhận.
- Không có người chịu trách nhiệm vận hành mesh upgrade và incident.

Một rule thực tế: nếu bạn chưa mô tả được vấn đề cụ thể mesh sẽ giải quyết trong hệ thống của mình, đừng cài mesh chỉ vì nó phổ biến.

## Deep dive: Cách hoạt động bên trong

Một request trong mesh thường đi qua chuỗi sau:

```text
app container -> local proxy/dataplane -> Service DNS/ClusterIP -> remote proxy/dataplane -> remote app
```

Sidecar injection thường được thực hiện bởi admission webhook khi Pod được tạo. Nếu namespace được annotate sau khi Pod đã tồn tại, Pod cũ không tự có sidecar; cần rollout restart. Certificate mTLS thường do mesh control plane cấp ngắn hạn cho identity dựa trên `ServiceAccount`, sau đó proxy dùng certificate này để xác thực peer.

Debug thực tế phải kiểm tra cả Kubernetes path và mesh path. Nếu `Service` không có endpoint, mesh không cứu được. Nếu endpoint đúng nhưng proxy thiếu route/certificate/policy, lỗi nằm ở mesh. Nếu proxy route đúng nhưng app trả 500, lỗi quay về application.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

K3s có thể chạy service mesh như Kubernetes khác, nhưng cần chú ý:

- Lab local bằng `k3d` có tài nguyên hạn chế; sidecar cho nhiều Pod sẽ nhanh tốn RAM.
- Traefik mặc định của K3s giải quyết Ingress, không phải service mesh.
- Flannel mặc định đủ cho Pod networking, nhưng mesh thêm lớp proxy và certificate phía trên.
- Một số mesh cần kiểm tra tương thích với CNI, iptables mode, kernel feature hoặc admission webhook.

Trên Kubernetes chuẩn self-managed, team platform tự vận hành admission webhook, control plane, certificate rotation, proxy upgrade và observability add-on. Trên EKS/GKE/AKS, cloud provider quản lý control plane Kubernetes nhưng không tự vận hành mesh cho bạn, trừ khi bạn chọn managed mesh/add-on như GKE Cloud Service Mesh hoặc vendor-managed Istio/Linkerd. Dù dùng managed option, team vẫn phải sở hữu policy, rollout plan, resource overhead và incident runbook.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi phù hợp | Chi phí/rủi ro |
|---|---|---|
| Không dùng mesh | Ít service, traffic đơn giản, app đã có timeout/metrics tốt | Thiếu mTLS/canary/policy nhất quán ở hạ tầng |
| Linkerd | Cần mTLS và golden metrics nhanh, vận hành nhẹ | Ít tính năng traffic/gateway nâng cao hơn Istio |
| Istio | Cần L7 routing, policy, gateway, multi-cluster sâu | CRD nhiều, resource overhead và debug phức tạp hơn |
| Managed mesh | Muốn giảm gánh nặng control plane/upgrade | Bị ràng buộc provider, vẫn phải thiết kế policy và SLO |

### Best Practices

- [ ] Có use case rõ: mTLS, canary, telemetry, authorization hoặc multi-cluster.
- [ ] Resource overhead của proxy được đo trên workload thật.
- [ ] Có owner cho mesh control plane, upgrade và certificate rotation.
- [ ] Có policy quyết định namespace/workload nào được inject.
- [ ] Có runbook phân biệt lỗi application, Service, DNS, CNI và mesh.
- [ ] Timeout/retry/circuit breaking được thiết kế theo idempotency.
- [ ] Observability mesh được nối với dashboard và alert hiện có.
- [ ] Bypass path được kiểm soát, nhất là workload chưa inject sidecar.

### Tránh làm

- Cài mesh trước khi hiểu traffic flow Kubernetes cơ bản.
- Bật retry mặc định cho mọi request.
- Dùng mesh để che application thiếu timeout hoặc readiness.
- Inject sidecar toàn cluster mà không tính resource requests/limits.
- Viết traffic rule phức tạp nhưng không có dashboard xác nhận actual split.
- Nhầm mTLS với authorization đầy đủ ở tầng business.

## Performance Considerations

Mesh thêm proxy/dataplane vào request path nên luôn có overhead:

- Mỗi Pod sidecar cần CPU/memory request riêng; cluster nhỏ có thể hết tài nguyên trước khi app scale.
- Latency tăng theo proxy hop, mTLS handshake, telemetry export và policy evaluation.
- Retry/circuit breaking sai có thể tăng traffic khi backend đang suy yếu.
- Control plane mất ổn định có thể làm proxy không nhận config/certificate mới, dù data plane cũ có thể vẫn xử lý traffic.
- Benchmark phải đo p95/p99, error rate, CPU throttling của proxy và app, không chỉ đo average latency.

## Debugging Checklist

Khi service trong mesh không gọi được nhau:

1. Kiểm tra Pod và Service bình thường trước: `kubectl get pods,svc,endpoints,endpointslice`.
2. Kiểm tra sidecar/dataplane đã inject chưa.
3. Kiểm tra control plane Pods và admission webhook.
4. Kiểm tra certificate/mTLS status.
5. Kiểm tra mesh policy hoặc authorization rule.
6. Kiểm tra traffic rule có route tới subset/version tồn tại không.
7. So sánh direct Pod log, proxy log và mesh dashboard.

## Liên hệ với kiến thức đã biết

Với microservices, service mesh giống một lớp platform cho concerns lặp lại giữa service: mTLS, timeout, retry, traffic split và request metrics. Nó bổ sung cho API Gateway/Ingress ở north-south traffic, không thay thế chúng. Với Redis, Kafka, database hoặc payment API, retry và timeout phải bám vào idempotency và semantics của protocol, không bật đại trà chỉ vì mesh hỗ trợ.

## Tóm tắt

Service mesh là lớp điều khiển traffic east-west mạnh, nhưng không miễn phí. Nó hợp khi hệ thống có nhu cầu rõ về mTLS, traffic management, authorization và telemetry nhất quán. Với cluster nhỏ hoặc team mới học Kubernetes, hãy thành thạo Service, DNS, Ingress, NetworkPolicy và CNI trước; sau đó dùng mesh như một công cụ có chủ đích.

## Câu hỏi tự kiểm tra

1. Vì sao sidecar injection chỉ tác động lên Pod được tạo sau khi namespace/workload được annotate?
2. Khi nào Linkerd là lựa chọn hợp lý hơn Istio?
3. Retry trong mesh có thể làm sự cố nặng hơn trong trường hợp nào?
4. Managed Kubernetes khác managed service mesh ở điểm trách nhiệm vận hành nào?
5. Bạn sẽ đo metric nào trước khi rollout mesh toàn namespace?

## Tài liệu tham khảo

- Kubernetes Documentation: Services, DNS, NetworkPolicy.
- Istio Documentation: Traffic Management, Security, Observability.
- Linkerd Documentation: Architecture, Automatic mTLS, Viz.
- CNCF Service Mesh Landscape và các case study production liên quan.
