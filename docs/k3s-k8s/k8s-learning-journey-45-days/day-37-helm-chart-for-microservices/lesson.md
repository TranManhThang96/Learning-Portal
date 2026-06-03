# Day 37: Tạo Helm Chart cho Microservices

## Mục tiêu bài học

- Thiết kế được Helm chart tái sử dụng cho một microservice stateless.
- Chuẩn hóa `Deployment`, `Service`, optional `Ingress`, `ConfigMap`, `Secret`, probes, resources và security context.
- Tách values theo môi trường dev/staging/prod mà không làm chart rối.
- Hiểu các anti-pattern khi dùng umbrella chart, global values, template logic quá nhiều và secret trong values.
- Biết debug chart microservice khi selector, env, config, probe hoặc ingress render sai.

## Vấn đề cần giải quyết

Trong hệ thống microservices, phần lớn service có shape giống nhau:

- Một container chính chạy HTTP/gRPC worker.
- `Deployment` để rollout.
- `Service` nội bộ.
- Optional `Ingress` cho public/API Gateway.
- Config qua env hoặc mounted file.
- Resources, probes, labels, securityContext.
- Optional `HPA`, `PDB`, `NetworkPolicy`.

Nếu mỗi team tự viết YAML, production sẽ có drift:

- Service A có readinessProbe, Service B không.
- Service C có resource requests, Service D không.
- Label selector khác nhau làm observability/GitOps khó query.
- Prod values được override bằng CLI và không còn trace trong Git.

Chart microservice tốt không chỉ giúp giảm YAML. Nó tạo một "deployment contract" chuẩn cho service: app expose port nào, health endpoint nào, resources ra sao, security baseline gì và môi trường override phần nào.

## Mental Model

```text
Reusable service chart
        |
        +-- stable contract
        |     +-- labels/selectors
        |     +-- probes/resources/security
        |     +-- service/ingress knobs
        |
        +-- environment values
              +-- dev: small, loose
              +-- staging: near-prod
              +-- prod: strict, observed
```

Chart là API nội bộ. `values.yaml` là input contract. Template là implementation detail. Nếu input contract mơ hồ, mọi service sẽ override theo cách riêng và chart mất giá trị.

## Lý thuyết cốt lõi

### Shape chuẩn cho stateless microservice

Một service HTTP thông thường cần:

| Resource | Vai trò |
|---|---|
| `Deployment` | Rollout, replica, image, env, probes, resources |
| `Service` | Stable DNS và load balancing nội bộ |
| `ServiceAccount` | Identity cho Pod, mặc định không mount token nếu không cần API |
| `ConfigMap` | Non-sensitive config |
| `Secret` hoặc External Secret | Sensitive config |
| `Ingress` | Public routing nếu service expose ra ngoài |
| `HPA` | Autoscaling nếu metrics phù hợp |
| `PDB` | Giữ availability khi voluntary disruption |
| `NetworkPolicy` | Giới hạn traffic nếu CNI hỗ trợ |

Không phải chart nào cũng bật tất cả resource. Nhưng chart nên có knobs rõ ràng:

```yaml
ingress:
  enabled: false
hpa:
  enabled: false
pdb:
  enabled: true
networkPolicy:
  enabled: false
```

### Labels và selectors

Labels nên theo Kubernetes recommended labels:

```yaml
app.kubernetes.io/name: order-service
app.kubernetes.io/instance: order-prod
app.kubernetes.io/component: api
app.kubernetes.io/part-of: logistics
app.kubernetes.io/version: "1.2.3"
app.kubernetes.io/managed-by: Helm
```

Selector nên tối giản và ổn định:

```yaml
selector:
  matchLabels:
    app.kubernetes.io/name: order-service
    app.kubernetes.io/instance: order-prod
```

Không đưa version, chart version hoặc environment label dễ đổi vào selector. `Deployment.spec.selector` immutable; đổi selector có thể làm upgrade fail.

### Environment values

Một pattern thực dụng:

```text
charts/service/
├── values.yaml
├── values-dev.yaml
├── values-staging.yaml
└── values-prod.yaml
```

Hoặc nếu dùng GitOps repo:

```text
environments/
├── dev/order-service-values.yaml
├── staging/order-service-values.yaml
└── prod/order-service-values.yaml
```

Default chart values nên an toàn nhưng không giả vờ là production. Ví dụ:

- `replicaCount: 1` cho default.
- resources có request nhỏ.
- memory limit có default.
- ingress disabled.
- service account token disabled nếu không cần.
- probes có cấu hình mẫu nhưng cần service owner xác nhận endpoint.

Production values nên nằm trong Git, review qua PR và không override thủ công bằng `--set` ngoài trường hợp khẩn cấp có ghi nhận.

### Config và Secret

Non-sensitive config có thể render từ values vào `ConfigMap`:

```yaml
config:
  LOG_LEVEL: info
  FEATURE_X_ENABLED: "false"
```

Sensitive config không nên nằm plain trong `values-prod.yaml`.

Options:

| Option | Khi dùng |
|---|---|
| Pre-created Secret | Lab hoặc platform tạo secret ngoài chart |
| External Secrets Operator | Production dùng AWS Secrets Manager, GCP Secret Manager, Vault |
| SOPS encrypted values | GitOps muốn lưu encrypted secret trong Git |
| Sealed Secrets | Cluster public-key encryption cho secret manifest |

Chart tốt nên hỗ trợ `existingSecret`:

```yaml
envFrom:
  secrets:
  - order-service-secret
```

Và tránh render secret thật từ plain values nếu không có lý do lab.

### Probes

Probes phải phản ánh lifecycle thật:

```yaml
probes:
  readiness:
    enabled: true
    path: /readyz
  liveness:
    enabled: true
    path: /healthz
  startup:
    enabled: false
```

Production caveats:

- `readinessProbe` quyết định Pod có vào Service endpoints không.
- `livenessProbe` kill process; cấu hình quá hung hăng gây restart loop.
- `startupProbe` hữu ích cho app cold start chậm.
- Probe endpoint không nên phụ thuộc dependency ngoài nếu điều đó làm Pod bị loại khỏi endpoints quá dễ trong incident downstream.

### Resources và autoscaling

Chart nên cho phép cấu hình:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    memory: 256Mi
```

Nếu bật HPA theo CPU, CPU request phải có ý nghĩa. HPA sử dụng CPU utilization dựa trên request; request quá thấp làm HPA scale quá nhạy, request quá cao làm HPA phản ứng chậm.

### Ingress và cloud-specific values

Ingress trên K3s lab thường dùng Traefik. Trên production có thể dùng NGINX, ALB Ingress Controller, GKE Ingress, Gateway API hoặc service mesh ingress gateway.

Chart nên không hard-code ingress class:

```yaml
ingress:
  enabled: true
  className: traefik
  annotations: {}
```

Cloud annotations nên nằm trong environment values, không nằm cứng trong template.

## Deep dive: Chart API design

### Values là public API

Một khi nhiều service dùng chart, thay đổi values shape là breaking change.

Ví dụ đổi:

```yaml
image:
  tag: "1.0.0"
```

sang:

```yaml
imageTag: "1.0.0"
```

sẽ phá tất cả pipeline đang override `.Values.image.tag`.

Vì vậy chart reusable cần versioning nghiêm túc:

- Minor version cho backward-compatible feature.
- Major version khi breaking values contract.
- Changelog cho values migration.
- `values.schema.json` nếu muốn validate input sớm.

### Library chart vs application chart

`application chart` tạo resource deploy được. `library chart` chỉ cung cấp template helper dùng lại.

| Pattern | Khi nên dùng | Rủi ro |
|---|---|---|
| Copy một service chart cho từng service | Team ít service, bắt đầu nhanh | Drift giữa copies |
| Reusable application chart | Nhiều service cùng shape | Values phải đủ linh hoạt nhưng không quá mở |
| Library chart | Nhiều chart khác nhau cần common helpers | Khó debug hơn, cần versioning |
| Umbrella chart | Lab hoặc release bundle nhỏ | Coupling lifecycle, rollback khó |

Với microservices production, pattern thường tốt là reusable chart hoặc chart generator/template chuẩn, còn stateful dependencies tách riêng.

### Ownership

Chart có 2 lớp owner:

- Platform team sở hữu chart contract, security baseline, default knobs.
- Service team sở hữu values theo service và môi trường.

Nếu platform team tự quyết values app mà không hiểu runtime, probes/resources sẽ sai. Nếu service team tự do sửa template, platform baseline mất tác dụng.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | Chart render ra object upstream như `Deployment`, `Service`, `Ingress`, `HPA` | Cần controllers tương ứng tồn tại: Ingress controller, metrics-server, policy engine |
| K3s local/lab | Tốt để test chart nhanh; Traefik và local-path thường có sẵn | Ingress class, storage class và LoadBalancer behavior khác cloud |
| Self-managed production | Team quyết định chart repo, ingress controller, DNS, cert-manager, metrics stack | Phải chuẩn hóa values, secret flow, RBAC và upgrade path |
| EKS/GKE/AKS | Chart vẫn deploy workload; cloud cung cấp LB/CSI/IAM integration | Values cần cloud-specific annotations, IRSA/Workload Identity, ingress class, storage class |

Không nên viết chart chỉ chạy trên K3s mặc định rồi gọi là portable. Portability đến từ values phân tách rõ phần cluster-specific.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| Một chart/service riêng | Service có nhu cầu khác biệt nhiều | Nhiều boilerplate, khó chuẩn hóa |
| Reusable service chart | Nhiều stateless service tương tự | Values contract phình to |
| Global values | Umbrella chart nhỏ, shared domain rõ | Coupling ngầm, override khó đọc |
| Environment values file | GitOps/CI production | Cần quản lý secret và review |
| `existingSecret` | Secret do tool khác quản lý | Chart không tự tạo đủ mọi thứ trong lab |
| Render Secret từ values | Lab nhanh | Dễ leak secret nếu dùng production |
| HPA optional trong chart | Service stateless có metrics tốt | Cần requests đúng và metrics-server |
| PDB mặc định bật | Production availability | Có thể block node drain nếu replica quá ít |

### Best Practices

- Nên chuẩn hóa labels, annotations, probes, resources, securityContext trong chart.
- Nên để environment-specific values ngoài chart package nếu team dùng GitOps.
- Nên dùng `values.schema.json` cho chart reusable quan trọng.
- Nên hỗ trợ `existingConfigMap`/`existingSecret` hoặc `envFrom`.
- Nên tách cloud-specific annotations vào values.
- Nên giữ template logic nông; tránh if/else lồng quá sâu.
- Nên pin chart version khi service dùng common chart.
- Nên render manifest trong CI và chạy policy checks.
- Tránh đưa secret thật vào plain values.
- Tránh chart "quá tổng quát" đến mức mọi thứ là raw YAML passthrough.

## Performance Considerations

- Chart microservice không trực tiếp cải thiện performance runtime; nó giúp encode cấu hình performance như resources, probes và autoscaling.
- Default CPU request quá thấp làm HPA scale nhạy và dễ noisy neighbor.
- Memory limit quá thấp gây `OOMKilled`; chart nên cho override rõ theo service.
- PDB với `minAvailable: 1` trên replica 1 có thể block voluntary disruption.
- Ingress annotations sai có thể làm timeout, body size, keepalive hoặc TLS behavior khác môi trường.
- Probes quá dày tạo thêm traffic nội bộ và có thể gây restart loop khi app chậm.
- Tạo nhiều release microservice cùng lúc có thể tạo burst API calls; GitOps controller/pipeline cần sync waves hoặc rate limit hợp lý.

## Debugging Checklist

Khi chart render sai:

```bash
helm lint ./service-chart
helm template order ./service-chart -f values-prod.yaml --debug
kubectl apply --dry-run=server -f rendered.yaml
```

Khi release deploy nhưng service lỗi:

```bash
helm status order -n app
helm get values order -n app --all
helm get manifest order -n app
kubectl get deploy,svc,ingress,endpoints -n app
kubectl describe deploy order -n app
kubectl describe pod <pod> -n app
kubectl logs <pod> -n app
```

Kiểm tra:

- Image repository/tag có đúng môi trường không?
- Selector của Service match labels của Pod không?
- `containerPort`, `targetPort` và app listen port có khớp không?
- Env/config/secret có render đúng không?
- ReadinessProbe có làm endpoints rỗng không?
- Ingress class/host/path có đúng controller không?
- Resource request có làm Pod `Pending` không?
- Policy/RBAC/admission có reject securityContext không?

Lab fix khác production fix:

- Lab: sửa values/template và upgrade lại.
- Production: sửa values trong Git, render diff, deploy qua pipeline/GitOps, rollback theo release revision nếu cần.

## Liên hệ với kiến thức đã biết

Với backend engineer, chart microservice giống một "deployment SDK" cho service. Service code expose port và health endpoint; chart biến contract đó thành Kubernetes runtime: `Deployment`, `Service`, probes, env, resources và rollout. Nếu contract giữa code và chart sai, lỗi sẽ hiện ở endpoints rỗng, 502 từ gateway, Pod restart hoặc autoscaling sai.

## Tổng kết

Helm chart cho microservices nên chuẩn hóa những thứ production luôn cần: labels, resources, probes, security, service discovery, ingress knobs và environment values. Chart tốt có contract nhỏ, rõ, versioned và dễ render trong CI. Chart tệ cố hỗ trợ mọi trường hợp bằng template logic phức tạp, chứa secret trong values, đổi selector tùy tiện và làm service team không hiểu manifest thật đang chạy.

## Câu hỏi tự kiểm tra

1. Vì sao values shape là public API của reusable chart?
2. Những label nào nên nằm trong selector và những label nào không nên?
3. Vì sao `existingSecret` thường tốt hơn render secret thật từ values?
4. PDB có thể gây kẹt node drain trong trường hợp nào?
5. Khi Service không route traffic tới Pod, bạn kiểm tra chart/render ở đâu trước?

## Tài liệu tham khảo

- Helm Chart Best Practices: https://helm.sh/docs/chart_best_practices/
- Helm Values Schema: https://helm.sh/docs/topics/charts/#schema-files
- Kubernetes Recommended Labels: https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/
- Kubernetes Probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Kubernetes PodDisruptionBudget: https://kubernetes.io/docs/tasks/run-application/configure-pdb/
