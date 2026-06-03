# Day 38: CRD và Operator Pattern

## Mục tiêu bài học

- Hiểu `CRD`, `CustomResource`, `controller`, `reconciliation loop`, `status`, `finalizer` và `ownerReference`.
- Biết khi nào nên dùng Operator có sẵn, khi nào nên viết Operator riêng và khi nào không nên.
- Đọc được CRD schema, versions, conversion, status subresource và validation failure.
- Hiểu failure modes phổ biến của Operator: reconcile loop lỗi, finalizer kẹt, RBAC thiếu, CRD upgrade sai.
- Thực hành tạo CRD đơn giản, tạo custom resource, validate schema, patch status và mô phỏng finalizer kẹt.

## Vấn đề cần giải quyết

Kubernetes built-in resources không thể bao phủ mọi domain. Bạn có thể cần object như:

- `PostgresCluster`
- `KafkaTopic`
- `Certificate`
- `ExternalSecret`
- `Application`
- `BackupSchedule`
- `FeatureEnvironment`

Nếu chỉ dùng YAML rời rạc, platform team phải viết script hoặc pipeline để biến "mong muốn cấp cao" thành nhiều resource thấp hơn. Operator pattern đưa logic đó vào Kubernetes control loop: người dùng tạo custom resource, controller liên tục reconcile trạng thái thật về desired state.

Nhưng Operator không phải magic. Operator là software production chạy trong cluster. Nó có bug, RBAC, upgrade path, metrics, leader election, finalizer và data-loss risk. Dùng sai Operator có thể nguy hiểm hơn YAML thủ công.

## Mental Model

```text
CustomResource (desired state)
        |
        v
Operator controller watches resource
        |
        v
Reconcile loop
        |
        +-- create/update child resources
        +-- call external APIs
        +-- update status
        +-- handle deletion via finalizer
```

`CRD` mở rộng Kubernetes API. `Operator` là controller hiểu domain đó. CRD không tự vận hành gì nếu không có controller tương ứng.

## Lý thuyết cốt lõi

### CRD và CustomResource

`CustomResourceDefinition` đăng ký một resource type mới vào Kubernetes API.

Ví dụ CRD tạo resource `webapps.platform.example.com`. Sau đó người dùng có thể tạo:

```yaml
apiVersion: platform.example.com/v1
kind: WebApp
metadata:
  name: checkout
spec:
  image: ghcr.io/acme/checkout:1.0.0
  replicas: 3
```

CRD định nghĩa:

- Group: `platform.example.com`
- Version: `v1`
- Kind: `WebApp`
- Plural: `webapps`
- Scope: `Namespaced` hoặc `Cluster`
- OpenAPI schema cho `spec` và `status`
- Subresources như `status`, `scale`

### Controller và reconciliation

Controller watch custom resources và reconcile từng object.

Pseudo-code:

```text
for each WebApp event:
  read desired spec
  read current Deployment/Service
  if missing, create them
  if drifted, update them
  update WebApp.status.conditions
  requeue if not ready
```

Controller phải idempotent. Reconcile có thể chạy nhiều lần, chạy lại sau lỗi, chạy khi object không đổi hoặc khi child resource thay đổi. Logic kiểu "chạy đúng một lần" thường sai trong Kubernetes.

### Spec và Status

`spec` là desired state do user đặt. `status` là observed state do controller cập nhật.

```yaml
spec:
  replicas: 3
  image: ghcr.io/acme/api:1.0.0
status:
  observedGeneration: 4
  readyReplicas: 3
  conditions:
  - type: Ready
    status: "True"
    reason: AllReplicasReady
```

Best practice:

- User không nên sửa `status`.
- Controller không nên tự sửa `spec` để che input sai, trừ khi có admission/defaulting rõ.
- `observedGeneration` giúp biết controller đã xử lý spec generation mới chưa.
- `conditions` giúp debug thay vì chỉ có một status string.

### Finalizer

Finalizer chặn xóa object cho tới khi controller cleanup xong.

Ví dụ khi xóa `PostgresCluster`, Operator có thể cần:

- Snapshot backup.
- Xóa external DNS.
- Gỡ cloud volume.
- Xóa child resources theo thứ tự.

Nếu controller down hoặc logic cleanup fail, custom resource sẽ kẹt ở trạng thái `Terminating` với `deletionTimestamp` và finalizer vẫn còn. Đây là failure mode production rất phổ biến.

Không xóa finalizer thủ công nếu chưa hiểu cleanup còn dang dở gì. Với resource data/stateful, xóa finalizer có thể bỏ qua bước backup hoặc cleanup external resource.

### OwnerReference

Child resources có thể có `ownerReferences` trỏ về custom resource. Kubernetes garbage collector dùng ownerReferences để cleanup child khi owner bị xóa.

Operator thường tạo:

```text
WebApp
  +-- Deployment ownerReference -> WebApp
  +-- Service ownerReference -> WebApp
  +-- ConfigMap ownerReference -> WebApp
```

OwnerReference hữu ích nhưng không thay thế finalizer khi cần cleanup external system hoặc data.

### CRD versions và conversion

CRD có thể có nhiều version:

```yaml
versions:
- name: v1alpha1
  served: true
  storage: false
- name: v1
  served: true
  storage: true
```

Khái niệm:

| Field | Meaning |
|---|---|
| `served` | API server nhận request version này |
| `storage` | Version lưu trong etcd |
| conversion webhook | Convert giữa versions khi schema thay đổi |

Upgrade CRD là việc nghiêm túc. Breaking schema hoặc conversion sai có thể làm controller không đọc được object cũ.

### Operator dùng cho stateful systems

Operator thường rất có giá trị với hệ thống stateful có lifecycle phức tạp:

- PostgreSQL: init cluster, replication, backup, failover, restore.
- Kafka: broker identity, topic/user, rolling upgrade.
- Cert-manager: certificate issuance/renewal.
- External Secrets: sync secret từ external store.

Nhưng Operator không loại bỏ yêu cầu hiểu domain. Ví dụ dùng PostgreSQL Operator mà không hiểu backup/restore, storage latency, replication lag và failover vẫn rủi ro.

## Deep dive: Failure modes của Operator

### CRD tồn tại nhưng controller không chạy

Bạn vẫn tạo được custom resource nếu CRD tồn tại. Nhưng không có controller thì sẽ không có child resource/status update.

Symptom:

```bash
kubectl get <custom-resource>
kubectl describe <custom-resource>
```

Object tồn tại nhưng `status` rỗng hoặc stale. Không có Deployment/Service/child resources như kỳ vọng.

### RBAC thiếu

Controller cần quyền đọc custom resource và tạo/update child resources.

Symptom:

- Controller logs có `Forbidden`.
- Status condition báo reconcile fail.
- Child resource không được tạo.

Debug:

```bash
kubectl logs deploy/<operator> -n <operator-namespace>
kubectl auth can-i create deployments --as=system:serviceaccount:<ns>:<sa> -n <target-ns>
```

### Finalizer kẹt

Resource `Terminating` lâu:

```bash
kubectl get <resource> <name> -o yaml
```

Kiểm tra:

- `metadata.deletionTimestamp`
- `metadata.finalizers`
- Controller logs
- External dependency còn sống không

Patch finalizer chỉ là break-glass, không phải fix đầu tiên.

### Reconcile storm

Controller reconcile liên tục do:

- Spec/status update loop sai.
- Child resource drift vì tool khác sửa liên tục.
- Error requeue không có backoff tốt.
- Watch quá rộng.

Impact:

- API server load tăng.
- Controller CPU tăng.
- Logs noise.
- Child resources bị update liên tục làm rollout lặp lại.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | CRD, custom resource, finalizer, ownerReference là API upstream | Cần CRD lifecycle, RBAC, conversion và backup etcd |
| K3s local/lab | Rất tốt để học CRD và finalizer; nhẹ để thử operator | Local etcd/sqlite/datastore backup không giống production; CRD sai vẫn có thể phá lab |
| Self-managed production | Team kiểm soát CRD install order, controller HA, metrics, leader election | Phải tự backup CRDs/custom resources và test upgrade/restore |
| EKS/GKE/AKS | CRD/Operator behavior giống Kubernetes; cloud quản lý control plane | Team vẫn chịu trách nhiệm operator Deployment, RBAC, CRD upgrade, cloud IAM permissions |

Managed Kubernetes không quản lý Operator của bạn. Nếu Operator đồng bộ cloud resource, bạn còn phải quản lý IAM/Workload Identity đúng.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| Raw manifests | Lifecycle đơn giản, ít object | Manual drift, không có domain reconciliation |
| Helm chart | Packaging app, config theo môi trường | Không reconcile external/domain state liên tục |
| Operator có sẵn | Domain phức tạp đã có tool trưởng thành | Cần tin và vận hành controller; upgrade risk |
| Viết Operator riêng | Có domain/platform workflow lặp lại, cần API cấp cao | Tốn engineering/ops lớn, phải maintain lâu dài |
| CRD không controller | API schema/config registry đơn giản | User tưởng có automation nhưng không có |
| Finalizer | Cleanup external/data an toàn | Có thể kẹt deletion nếu controller lỗi |
| OwnerReference | Cleanup child resources trong cluster | Không cleanup external resource |

### Best Practices

- Nên dùng Operator trưởng thành cho domain phức tạp thay vì tự viết sớm.
- Nên đọc CRD schema trước khi apply custom resource production.
- Nên monitor controller logs, reconcile errors, queue depth và API latency nếu có metrics.
- Nên backup CRDs và custom resources cùng cluster backup.
- Nên test CRD/operator upgrade ở staging với object thật.
- Nên dùng status conditions rõ ràng để debug.
- Nên thiết kế finalizer idempotent và có timeout/runbook.
- Nên dùng ownerReferences cho child resources trong cluster.
- Tránh viết Operator chỉ để thay vài dòng YAML đơn giản.
- Tránh xóa finalizer thủ công nếu chưa hiểu cleanup hậu quả.

## Performance Considerations

- Controller watch nhiều resource/namespaces tạo load lên API server.
- Reconcile loop không idempotent hoặc update status quá thường xuyên gây API churn.
- CRD schema lớn và nhiều custom resource có thể ảnh hưởng API discovery, kubectl và backup size.
- Conversion webhook chậm hoặc down có thể ảnh hưởng request tới CRD version liên quan.
- Operator stateful như database operator có thể trigger rolling restart, backup hoặc failover; performance impact nằm ở domain operation, không chỉ Kubernetes object.
- Finalizer cleanup external API chậm làm deletion kéo dài.

## Debugging Checklist

Khi custom resource không tạo child resources:

```bash
kubectl get crd
kubectl get <plural> -A
kubectl describe <kind-or-resource> <name> -n <namespace>
kubectl get <kind-or-resource> <name> -n <namespace> -o yaml
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl logs deploy/<operator> -n <operator-namespace>
```

Khi nghi RBAC:

```bash
kubectl auth can-i get <plural> --as=system:serviceaccount:<ns>:<sa> -n <target-ns>
kubectl auth can-i create deployments --as=system:serviceaccount:<ns>:<sa> -n <target-ns>
kubectl get role,rolebinding,clusterrole,clusterrolebinding -A
```

Khi resource kẹt deletion:

```bash
kubectl get <resource> <name> -n <namespace> -o yaml
kubectl describe <resource> <name> -n <namespace>
kubectl logs deploy/<operator> -n <operator-namespace> --since=30m
```

Kiểm tra:

- CRD version có đúng không?
- Controller có chạy không?
- `status.observedGeneration` có bằng `metadata.generation` không?
- Conditions nói lỗi gì?
- Finalizer nào đang chặn deletion?
- Child resources có ownerReference không?
- Có GitOps/Helm tool khác đang sửa cùng object không?

## Liên hệ với kiến thức đã biết

Operator giống một service backend event-driven, nhưng event là Kubernetes object changes. `spec` tương đương request/input, `status` tương đương response/observed result, reconcile loop tương đương worker idempotent xử lý message nhiều lần. Khác biệt lớn là controller phải sống trong Kubernetes API consistency model và luôn chịu tác động của RBAC, admission, finalizer, watch cache và versioned schema.

## Tổng kết

CRD mở rộng Kubernetes API, Operator biến custom resource thành automation có reconciliation. Đây là pattern mạnh cho platform và stateful systems, nhưng chỉ đáng dùng khi lifecycle đủ phức tạp để justify controller riêng. Khi vận hành Operator, phải xem nó như production service: có metrics, logs, RBAC, upgrade plan, backup, finalizer runbook và domain knowledge rõ.

## Câu hỏi tự kiểm tra

1. CRD khác Operator ở điểm nào?
2. Vì sao controller reconcile phải idempotent?
3. `spec`, `status`, `observedGeneration` và `conditions` giúp debug thế nào?
4. Finalizer kẹt có thể gây hậu quả gì?
5. Khi nào bạn sẽ chọn Helm chart thay vì viết Operator?

## Tài liệu tham khảo

- Kubernetes Custom Resources: https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
- Kubernetes CRDs: https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/
- Kubernetes Finalizers: https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/
- Kubebuilder Book: https://book.kubebuilder.io/
- Operator SDK Documentation: https://sdk.operatorframework.io/
