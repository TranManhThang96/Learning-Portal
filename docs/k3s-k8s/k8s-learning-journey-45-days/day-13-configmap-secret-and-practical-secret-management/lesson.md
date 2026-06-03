# Day 13: ConfigMap, Secret và secret management thực tế

## Mục tiêu bài học

- Phân biệt rõ `ConfigMap`, `Secret`, environment variables, mounted files và external secret systems.
- Tạo được `ConfigMap` và `Secret` bằng manifest an toàn cho lab.
- Hiểu vì sao `Secret` trong Kubernetes không đồng nghĩa với mã hóa end-to-end.
- Biết các pattern production phổ biến: `External Secrets Operator`, `Sealed Secrets`, `SOPS`, Vault.
- Debug được lỗi cấu hình sai key, Pod không start, config không cập nhật và secret bị lộ qua RBAC/logs.

## Vấn đề cần giải quyết

Microservices cần config khác nhau theo môi trường: endpoint, feature flag, log level, timeout, credential database, token gọi API ngoài. Nếu bake config vào image, mỗi thay đổi nhỏ đều phải build lại image. Nếu đặt secret trong Git plain text, rủi ro lộ credential là rất cao.

Kubernetes giải quyết phần runtime injection bằng `ConfigMap` và `Secret`, nhưng đây chỉ là lớp phân phối config vào Pod. Production secret management vẫn cần mã hóa, phân quyền, rotation, audit và tích hợp với source of truth như cloud secret manager hoặc Vault.

## Mental Model

```text
Image        = code + runtime dependency.
ConfigMap    = non-sensitive runtime config.
Secret       = sensitive runtime config represented as Kubernetes object.
External store = source of truth cho secret production.
```

Pod không nên biết secret đến từ Git, Vault hay AWS Secrets Manager. Pod chỉ đọc environment variable hoặc file. Platform team quyết định secret được đồng bộ, mã hóa và rotate như thế nào.

## Lý thuyết cốt lõi

### ConfigMap

`ConfigMap` lưu dữ liệu cấu hình không nhạy cảm dưới dạng key-value hoặc file-like data.

Ví dụ:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_MODE: "lab"
  LOG_LEVEL: "debug"
  settings.ini: |
    timeout_seconds=5
    feature_flag=true
```

Cách consume phổ biến:

- Environment variable qua `env` hoặc `envFrom`.
- File mount qua volume `configMap`.
- Command/args dùng giá trị từ config.

Environment variable chỉ được đọc lúc container start. Nếu `ConfigMap` đổi, container không tự reload env. Với mounted file, kubelet có thể cập nhật nội dung sau một khoảng trễ, nhưng app vẫn phải tự reload file nếu muốn nhận config mới mà không restart.

Update behavior cần nhớ:

| Cách consume | Khi `ConfigMap`/`Secret` đổi | Caveat |
|---|---|---|
| Env var | Không đổi trong container đang chạy | Cần restart/rollout để nhận giá trị mới |
| Volume mount bình thường | File có thể được kubelet cập nhật sau một khoảng trễ | App phải tự reload file hoặc reread mỗi lần dùng |
| `subPath` mount | Không nhận update tự động | Dùng khi cần mount một file vào path cụ thể nhưng phải chấp nhận restart |
| `immutable: true` | Không cho sửa object | Tạo object version mới hoặc xóa tạo lại |

`ConfigMap` và `Secret` không phù hợp để chứa blob lớn. Kubernetes giới hạn kích thước object này khoảng 1 MiB; nếu config/secret lớn hơn, hãy dùng image artifact, volume, object storage hoặc external secret system phù hợp.

### Secret

`Secret` dùng cho dữ liệu nhạy cảm như password, token, TLS key, registry credential.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
type: Opaque
stringData:
  DB_USERNAME: app
  DB_PASSWORD: change-me-in-lab
```

`stringData` tiện cho manifest lab vì Kubernetes tự chuyển sang `data` base64 khi lưu. Base64 không phải mã hóa. Người có quyền `get secret` có thể decode được nội dung.

Các loại `Secret` thường gặp:

| Type | Use case |
|---|---|
| `Opaque` | Secret generic cho app |
| `kubernetes.io/tls` | TLS certificate/key |
| `kubernetes.io/dockerconfigjson` | Pull image từ private registry |
| `kubernetes.io/service-account-token` | Token liên quan ServiceAccount, hiện nay thường dùng projected token thay vì tạo thủ công |

### ConfigMap vs Secret

| Tiêu chí | `ConfigMap` | `Secret` |
|---|---|---|
| Dữ liệu | Không nhạy cảm | Nhạy cảm |
| Encoding | Plain text trong `data` | Base64 trong `data`, hoặc plain text qua `stringData` khi apply |
| RBAC | Vẫn cần giới hạn write | Cần giới hạn read/write rất chặt |
| Audit | Ít nhạy hơn | Cần audit ai đọc/sửa |
| GitOps | Có thể commit nếu không chứa secret | Không commit plain text |
| Rotation | Thường ít nghiêm ngặt | Cần quy trình rotation |

### Immutable config

Cả `ConfigMap` và `Secret` có thể đặt `immutable: true`.

```yaml
immutable: true
```

Điều này giảm rủi ro sửa nhầm và giảm watch load với object không cần đổi. Trade-off là muốn thay đổi phải tạo object mới hoặc xóa tạo lại, nên cần naming/versioning rõ ràng.

### External Secrets Operator

`External Secrets Operator` đồng bộ secret từ external provider vào Kubernetes `Secret`. Object `ExternalSecret` tham chiếu `SecretStore` hoặc `ClusterSecretStore`, sau đó tạo/cập nhật target Kubernetes `Secret`.

API version của CRD phụ thuộc version operator đã cài. Ví dụ bên dưới dùng `external-secrets.io/v1`. Nếu cluster của bạn chỉ có `v1beta1` hoặc version khác, kiểm tra bằng `kubectl api-resources | grep -i externalsecret` và `kubectl explain externalsecret.spec` rồi chỉnh `apiVersion` theo CRD thực tế.

Mô hình:

```text
AWS Secrets Manager / Vault / GCP Secret Manager
        |
        v
SecretStore or ClusterSecretStore
        |
        v
ExternalSecret
        |
        v
Kubernetes Secret
        |
        v
Pod env/file
```

Ví dụ rút gọn:

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: app-db
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: team-secret-store
    kind: SecretStore
  target:
    name: app-secret
    creationPolicy: Owner
  data:
  - secretKey: DB_PASSWORD
    remoteRef:
      key: production/app/db-password
```

Lưu ý quan trọng: external secret system là source of truth, nhưng Pod vẫn thường consume Kubernetes `Secret`. Vì vậy vẫn cần RBAC, encryption at rest, namespace boundary và audit.

### Sealed Secrets, SOPS và Vault

| Công cụ | Ý tưởng | Khi phù hợp |
|---|---|---|
| `Sealed Secrets` | Encrypt Secret thành `SealedSecret`, chỉ controller trong cluster giải mã | GitOps đơn giản, một hoặc vài cluster |
| `SOPS` | Encrypt file YAML/values bằng age/GPG/KMS | GitOps linh hoạt, muốn review encrypted files trong repo |
| Vault | Secret engine, dynamic secrets, lease, audit, policy | Tổ chức cần rotation mạnh, dynamic credential, audit chặt |
| `External Secrets Operator` | Sync từ external store về Kubernetes Secret | Cloud-native production, nhiều app dùng secret manager chuẩn |

Không có lựa chọn tuyệt đối. Với team nhỏ, SOPS hoặc Sealed Secrets có thể đủ. Với cloud production, `External Secrets Operator` kết hợp cloud secret manager thường dễ vận hành hơn. Với yêu cầu dynamic credential và audit nghiêm ngặt, Vault đáng cân nhắc nhưng vận hành phức tạp hơn.

## Deep dive: Cách hoạt động bên trong

Khi Pod tham chiếu `ConfigMap` hoặc `Secret`:

```text
1. User apply ConfigMap/Secret.
2. kube-apiserver lưu object vào datastore.
3. Scheduler đặt Pod lên node.
4. kubelet trên node fetch ConfigMap/Secret cần thiết cho Pod.
5. kubelet inject vào container dưới dạng env hoặc mount file.
6. Nếu object đổi, kubelet cập nhật mounted volume theo cơ chế watch/cache/poll, nhưng env không đổi.
```

Failure thường nằm ở 4 điểm:

- Key không tồn tại nên container không được tạo.
- RBAC/admission/policy chặn Secret.
- App không reload file khi config đổi.
- Secret đã được sync nhưng Pod vẫn dùng giá trị cũ vì chưa restart hoặc app cache credential.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| `ConfigMap`/`Secret` API | Giống upstream | Giống upstream | Giống upstream |
| Encryption at rest | Có thể bật qua cấu hình K3s như `secrets-encryption` | Tự cấu hình encryption provider cho API server/datastore | Thường tích hợp KMS/cloud-managed encryption tùy dịch vụ |
| External secret | Tự cài operator | Tự cài operator | Thường dùng cloud secret manager + operator/CSI |
| RBAC/audit | Team tự cấu hình | Team tự cấu hình | Cloud quản control plane, team vẫn phải thiết kế RBAC |
| Lab default | Dễ dùng Secret plain cho demo | Tùy distro | Không nên dùng plain secret trong Git |

K3s phù hợp để học behavior của `ConfigMap` và `Secret`. Nhưng khi chuyển sang managed Kubernetes, thiết kế production nên bắt đầu từ source of truth: cloud secret manager, IAM, KMS, audit log, rotation procedure.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Env var từ `ConfigMap`/`Secret` | App đọc config lúc start | Rất nhẹ | Thấp | Không tự nhận update |
| Mounted file | App có thể reload file | Kubelet cần watch/update volume | Trung bình | App không reload hoặc đọc partial state |
| `envFrom` | Nhiều key đơn giản | Nhẹ | Dễ dùng quá tay | Key conflict, khó trace key nào dùng |
| Key explicit qua `valueFrom` | Config contract rõ | Nhẹ | Dài hơn | Thiếu key làm Pod không start |
| Plain Kubernetes `Secret` | Lab, low-risk internal | Nhẹ | Thấp | Lộ qua RBAC/Git/etcd nếu cấu hình yếu |
| SOPS/Sealed Secrets | GitOps encrypted | Không ảnh hưởng runtime nhiều | Trung bình | Mất key giải mã, rotation khó nếu không chuẩn hóa |
| External Secrets | Secret source of truth bên ngoài | Sync loop tạo API load nhỏ | Trung bình-cao | Provider outage, stale secret |
| Vault dynamic secret | Rotation/audit mạnh | Thêm network dependency | Cao | Vault outage ảnh hưởng workload nếu thiết kế kém |

### Best Practices

Nên làm:

- Tách config không nhạy cảm vào `ConfigMap`, secret thật vào `Secret` hoặc external store.
- Dùng `stringData` cho lab, không commit secret thật.
- Giới hạn RBAC `get/list/watch secrets` theo namespace và service account.
- Bật encryption at rest cho Secret trong production.
- Dùng external secret manager làm source of truth khi chạy cloud production.
- Thiết kế rotation: app reload được credential hoặc rollout restart an toàn.
- Dùng key explicit thay vì `envFrom` cho secret quan trọng.
- Tránh log toàn bộ environment variables.
- Với GitOps, dùng SOPS, Sealed Secrets hoặc External Secrets thay vì Secret plain text.

Tránh làm:

- Đặt password trong `ConfigMap`.
- Nghĩ base64 là mã hóa.
- Cấp `cluster-admin` cho app chỉ để đọc Secret.
- Dùng cùng một Secret cho nhiều service không liên quan.
- Mount tất cả secret vào container nếu app chỉ cần một key.
- Để secret trong image, Dockerfile, CI logs hoặc Helm values plain text.

## Performance Considerations

- `ConfigMap`/`Secret` nhỏ và ít đổi có chi phí thấp. Object lớn hoặc thay đổi liên tục tạo áp lực lên API server, kubelet watch và rollout.
- Environment variable gần như không có overhead runtime nhưng cần restart để cập nhật.
- Mounted file cho phép cập nhật không rebuild image, nhưng app phải tự reload.
- Secret rotation có thể gây connection churn nếu app mở lại kết nối database hàng loạt.
- External secret sync quá dày có thể tạo API load và tăng dependency vào provider.
- Với nhiều namespace/team, số lượng Secret lớn làm backup, audit và RBAC review khó hơn.

## Debugging Checklist

Pod bị `CreateContainerConfigError`:

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get configmap,secret -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Kiểm tra key có tồn tại:

```bash
kubectl get configmap app-config -o yaml -n <namespace>
kubectl get secret app-secret -o jsonpath='{.data}' -n <namespace>
```

Kiểm tra env/file trong container:

```bash
kubectl exec -it <pod> -n <namespace> -- sh
env | sort
ls -la /etc/app/config
cat /etc/app/config/settings.ini
```

Kiểm tra External Secrets:

```bash
kubectl get externalsecret -A
kubectl describe externalsecret <name> -n <namespace>
kubectl get secret <target-secret> -n <namespace>
```

Lab fix thường là sửa manifest và `kubectl rollout restart deployment/<name>`. Production fix phải kiểm tra phạm vi ảnh hưởng, rotation window, app reload behavior và audit xem secret có bị lộ hay không.

## Liên hệ với kiến thức đã biết

Trong microservices, `ConfigMap` giống runtime config layer cho Twelve-Factor App. `Secret` giống credential distribution layer. Nhưng vấn đề thật sự không nằm ở cách inject biến môi trường, mà nằm ở secret lifecycle: ai tạo, ai đọc, ai rotate, ai audit, khi nào credential hết hạn và rollback ra sao nếu rotation lỗi.

## Tóm tắt

`ConfigMap` dùng cho config không nhạy cảm. `Secret` dùng cho dữ liệu nhạy cảm nhưng không tự làm secret an toàn tuyệt đối. Production cần RBAC chặt, encryption at rest, không commit plain secret, có rotation procedure và thường dùng external secret manager. Debug config/secret nên đi từ object tồn tại, key đúng, Pod events, container env/file và app reload behavior.

## Câu hỏi tự kiểm tra

1. Vì sao `Secret` base64 không đủ an toàn cho production?
2. Khi nào dùng mounted file thay vì environment variable?
3. `ExternalSecret` khác Kubernetes `Secret` ở vai trò nào?
4. Vì sao không nên dùng `envFrom` bừa bãi với secret?
5. Nếu config đã đổi nhưng app vẫn dùng giá trị cũ, bạn kiểm tra gì trước?

## Tài liệu tham khảo

- Kubernetes ConfigMaps: https://kubernetes.io/docs/concepts/configuration/configmap/
- Kubernetes Secrets: https://kubernetes.io/docs/concepts/configuration/secret/
- Kubernetes Good practices for Secrets: https://kubernetes.io/docs/concepts/security/secrets-good-practices/
- Kubernetes Encrypting Secret Data at Rest: https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/
- K3s Packaged Components and configuration notes: https://docs.k3s.io/installation/packaged-components
- External Secrets Operator: https://external-secrets.io/latest/
- Bitnami Sealed Secrets: https://github.com/bitnami-labs/sealed-secrets
- SOPS: https://github.com/getsops/sops
