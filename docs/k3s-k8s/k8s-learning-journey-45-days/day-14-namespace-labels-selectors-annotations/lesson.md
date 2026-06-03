# Day 14: Namespace, labels, selectors và annotations

## Mục tiêu bài học

- Dùng `Namespace` để tổ chức resource theo team, môi trường hoặc domain.
- Thiết kế label taxonomy đủ rõ cho query, ownership, rollout, Service selector và policy.
- Phân biệt `labels` với `annotations` và biết khi nào dùng mỗi loại.
- Hiểu rủi ro production khi selector sai, label đổi bừa bãi hoặc namespace bị coi nhầm là security boundary đầy đủ.
- Debug được Service không có endpoints, Deployment không quản lý Pod đúng và query resource theo label.

## Vấn đề cần giải quyết

Cluster production không chỉ có vài Pod. Nó có hàng trăm hoặc hàng nghìn object thuộc nhiều team, môi trường, service và release khác nhau. Nếu không có naming, namespace và labels tốt:

- Không biết resource nào thuộc service nào.
- Service selector có thể trỏ nhầm Pod hoặc không trỏ Pod nào.
- Monitoring, logging, billing, RBAC, NetworkPolicy khó áp dụng theo nhóm.
- Cleanup và incident response mất thời gian.

`Namespace`, `labels`, `selectors` và `annotations` là lớp metadata nền tảng để vận hành Kubernetes có trật tự.

## Mental Model

```text
Namespace  = logical workspace.
Label      = queryable identity and grouping metadata.
Selector   = rule chọn object theo label.
Annotation = non-query metadata for tools/controllers.
```

Nếu xem cluster như một database object lớn, label chính là indexed fields bạn dùng để query và join behavior giữa các controller.

## Lý thuyết cốt lõi

### Namespace

`Namespace` chia cluster thành các không gian tên logic. Nhiều resource là namespaced: `Pod`, `Deployment`, `Service`, `ConfigMap`, `Secret`, `Role`, `RoleBinding`. Một số resource là cluster-scoped: `Node`, `Namespace`, `ClusterRole`, `ClusterRoleBinding`, `StorageClass`, `PersistentVolume`.

Tạo namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: orders-dev
  labels:
    environment: dev
    owner: platform
```

Namespace giúp tổ chức, nhưng không tự tạo isolation đầy đủ. Muốn isolation thực tế cần kết hợp:

- `RBAC` để giới hạn quyền.
- `ResourceQuota` và `LimitRange` để giới hạn tài nguyên.
- `NetworkPolicy` để giới hạn traffic.
- Admission policy để chặn workload không đạt chuẩn.
- Observability labels để phân tách log/metrics.

### Labels

`Labels` là key-value metadata dùng để identify và group object.

Ví dụ label chuẩn:

```yaml
metadata:
  labels:
    app.kubernetes.io/name: orders
    app.kubernetes.io/component: api
    app.kubernetes.io/part-of: commerce
    app.kubernetes.io/managed-by: kubectl
    environment: dev
    tier: backend
```

Nên ưu tiên các recommended labels như `app.kubernetes.io/name`, `app.kubernetes.io/instance`, `app.kubernetes.io/component`, `app.kubernetes.io/part-of`, `app.kubernetes.io/managed-by`. Chúng giúp tooling như Helm, dashboards, logging và GitOps dễ hiểu object hơn.

### Selectors

`Selector` chọn object dựa trên labels. Các controller và resource dùng selector rất nhiều:

- `Deployment.spec.selector` chọn Pod thuộc Deployment.
- `Service.spec.selector` chọn Pod làm backend.
- `NetworkPolicy.podSelector` chọn Pod áp policy.
- `kubectl -l` query resource.

Ví dụ Service selector:

```yaml
spec:
  selector:
    app.kubernetes.io/name: orders
    app.kubernetes.io/component: api
```

Nếu selector không match Pod nào, Service vẫn tồn tại nhưng không có endpoints. Đây là lỗi rất thường gặp khi app không nhận traffic.

`Deployment.spec.selector` là immutable sau khi tạo. Nếu chọn selector sai, Kubernetes thường bắt bạn tạo Deployment mới thay vì patch trực tiếp. Vì vậy selector phải được review cùng Pod template labels trước khi apply production. `Service.spec.selector` patch được, nhưng đổi nhầm có thể làm traffic chuyển sang sai backend ngay lập tức.

### Equality-based và set-based selectors

Equality-based:

```bash
kubectl get pods -l app.kubernetes.io/name=orders
kubectl get pods -l environment!=prod
```

Set-based:

```bash
kubectl get pods -l 'environment in (dev,staging)'
kubectl get pods -l 'tier notin (frontend,edge)'
kubectl get pods -l 'app.kubernetes.io/component'
```

Set-based selectors hữu ích khi query nhiều nhóm, nhưng trong manifest production nên giữ selector ổn định và dễ review.

### Annotations

`Annotations` cũng là key-value metadata nhưng không dùng cho grouping/query chính. Chúng phù hợp cho dữ liệu tool/controller cần đọc:

- Checksum config để trigger rollout.
- Link runbook, owner contact, ticket, commit SHA.
- Ingress controller hints.
- Prometheus scrape hints trong một số setup.
- GitOps metadata.

Ví dụ:

```yaml
metadata:
  annotations:
    runbook.example.com/url: "https://wiki.example.com/orders-runbook"
    git.example.com/commit: "abc1234"
```

Không nên dùng annotation cho selector logic. Nếu bạn cần query thường xuyên, hãy dùng label.

## Deep dive: Vì sao selector cần ổn định

Deployment selector gần như là contract bất biến giữa Deployment và Pod template. Nếu selector không match template labels, Kubernetes sẽ từ chối hoặc Deployment không quản lý Pod như mong muốn.

Luồng Service routing:

```text
1. Pod có labels.
2. Service có selector.
3. EndpointSlice controller tìm Pod match selector.
4. Controller tạo EndpointSlice chứa Pod IP/port.
5. kube-proxy hoặc dataplane dùng endpoint để route traffic.
```

Khi `Service` không có endpoints, lỗi thường không nằm ở network. Nó thường là metadata mismatch: label sai, namespace sai, port sai hoặc Pod chưa Ready.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Namespace/label API | Giống upstream | Giống upstream | Giống upstream |
| Multi-team isolation | Tự cấu hình RBAC/quota/policy | Tự cấu hình | Cloud IAM hỗ trợ, nhưng Kubernetes RBAC vẫn cần thiết |
| Default namespace | Dễ dùng cho lab | Không nên dùng production | Không nên dùng production |
| Tooling metadata | K3s packaged components có labels riêng trong `kube-system` | Tùy distro/addon | Cloud add-ons có labels/annotations riêng |
| Billing/ownership | Manual | Manual | Có thể tích hợp label/tag với cloud cost tools |

Trong K3s lab, namespace giúp giữ bài học sạch và cleanup dễ. Trong production, namespace strategy phải gắn với RBAC, quota, network policy, GitOps ownership và incident workflow.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Namespace theo environment | `dev`, `staging`, `prod` tách rõ | Thấp | Dễ hiểu ban đầu | Team ownership lẫn lộn |
| Namespace theo team | Team tự vận hành service | Thấp | Cần quota/RBAC chuẩn | Khó tách env nếu label yếu |
| Namespace theo app | App lớn, isolation mạnh | Nhiều namespace hơn | Trung bình-cao | RBAC/GitOps object tăng |
| Label taxonomy chuẩn | Cluster nhiều team/tooling | Query nhanh và rõ | Cần governance | Label drift nếu không enforce |
| Free-form labels | Lab, prototype | Thấp | Dễ bắt đầu | Khó automation về sau |
| Annotation cho tool metadata | Controller cần dữ liệu phụ | Thấp nếu không quá lớn | Tool-specific | Khó discover nếu lạm dụng |

### Best Practices

Nên làm:

- Không deploy workload production vào `default`.
- Dùng namespace cho boundary vận hành, không coi nó là security boundary duy nhất.
- Chuẩn hóa labels tối thiểu: app name, component, environment, owner, part-of.
- Giữ selector của Deployment/Service nhỏ, ổn định và có ý nghĩa.
- Dùng recommended `app.kubernetes.io/*` labels.
- Dùng annotations cho metadata phụ như runbook URL, commit SHA, checksum.
- Kiểm tra endpoints sau khi tạo Service.
- Dùng `kubectl get ... -l` thường xuyên để xác minh label taxonomy.

Tránh làm:

- Đổi label mà Service/Deployment/NetworkPolicy đang dùng làm selector.
- Dùng annotation thay cho label khi cần query/filter.
- Gắn label chứa dữ liệu nhạy cảm.
- Tạo namespace theo cảm hứng mà không có ownership/quota.
- Dùng selector quá rộng như `app=api` trong namespace nhiều service.
- Copy manifest giữa môi trường nhưng quên đổi labels/namespace.

## Performance Considerations

- Selector query là thao tác phổ biến và được Kubernetes tối ưu, nhưng label taxonomy hỗn loạn làm con người và automation chậm lại.
- Quá nhiều label có cardinality cao như request id, timestamp, pod-specific random value sẽ làm metrics/log indexing tốn kém nếu được scrape.
- Namespace nhiều không tự gây vấn đề lớn, nhưng mỗi namespace thường kéo theo RoleBinding, Quota, NetworkPolicy, Secret và GitOps object.
- Service selector sai không chỉ gây downtime; nó còn làm debugging traffic tốn thời gian vì symptom giống lỗi network.
- Label thay đổi trên nhiều Pod có thể trigger controller reconciliation và EndpointSlice updates.

## Debugging Checklist

Service không route được:

```bash
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl describe service <service> -n <namespace>
kubectl get pods -n <namespace> --show-labels
kubectl get pods -n <namespace> -l '<selector>'
```

Deployment không quản lý Pod:

```bash
kubectl get deployment <deployment> -o yaml -n <namespace>
kubectl get rs,pod -n <namespace> --show-labels
kubectl describe deployment <deployment> -n <namespace>
```

Namespace và scope:

```bash
kubectl get all -n <namespace>
kubectl api-resources --namespaced=true
kubectl api-resources --namespaced=false
kubectl config set-context --current --namespace=<namespace>
```

`kubectl get all` không thật sự là "all". Nó chỉ in một tập resource phổ biến và không bao gồm nhiều object quan trọng như `ConfigMap`, `Secret`, `RoleBinding`, `NetworkPolicy`, `ResourceQuota`, `LimitRange`, `Ingress` hoặc CRD. Khi audit namespace, dùng `kubectl api-resources --namespaced=true` hoặc checklist resource cụ thể.

Kiểm tra quyền theo namespace:

```bash
kubectl auth can-i get pods -n <namespace>
kubectl auth can-i create deployment -n <namespace>
```

Lab fix thường là sửa label/selector và apply lại. Production fix cần xác định controller nào phụ thuộc selector đó trước khi đổi, vì một label có thể ảnh hưởng Service, NetworkPolicy, monitoring và deployment automation.

## Liên hệ với kiến thức đã biết

Trong microservices, labels giống service metadata trong service catalog. Namespace giống workspace hoặc tenant boundary vận hành. Selector giống query predicate. Nếu metadata sai, hệ thống vẫn chạy ở tầng process nhưng traffic, observability và policy có thể trỏ sai đối tượng.

## Tóm tắt

Namespace giúp tổ chức resource nhưng cần RBAC/quota/policy để thành boundary vận hành thật. Labels là metadata queryable và là nền tảng cho selectors. Selectors kết nối Deployment với Pod, Service với Pod, policy với Pod. Annotations chứa metadata phụ cho tools/controllers. Debug nhiều lỗi Kubernetes nên bắt đầu bằng câu hỏi: object có đang ở đúng namespace và labels/selectors có match không?

## Câu hỏi tự kiểm tra

1. Namespace giải quyết gì và không giải quyết gì?
2. Vì sao Service có thể tồn tại nhưng không có endpoints?
3. Khi nào dùng annotation thay vì label?
4. Vì sao selector của Deployment nên ổn định?
5. Label taxonomy tối thiểu cho microservice production nên gồm những gì?

## Tài liệu tham khảo

- Kubernetes Namespaces: https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/
- Kubernetes Labels and Selectors: https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
- Kubernetes Annotations: https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/
- Kubernetes Recommended Labels: https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/
- Kubernetes Organizing Cluster Access Using kubeconfig: https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/
