# Day 36: Helm Fundamentals

## Mục tiêu bài học

- Hiểu `Helm chart`, `release`, `values`, `template`, `helper` và `dependency` ở mức vận hành được.
- Biết render manifest bằng `helm template`, kiểm tra bằng `helm lint`, cài bằng `helm install` và nâng cấp bằng `helm upgrade`.
- Hiểu cách Helm lưu release state, xử lý rollback và vì sao release có thể kẹt.
- Phân biệt Helm với raw YAML, Kustomize, GitOps và Operator.
- Debug được lỗi template render, lỗi apply, lỗi rollout sau khi Helm install/upgrade.

## Vấn đề cần giải quyết

Khi microservices tăng từ vài manifest lên hàng chục service, copy YAML thủ công nhanh chóng tạo lỗi:

- `Deployment`, `Service`, `Ingress`, `ConfigMap`, `Secret`, `HPA` lặp lại cấu trúc giống nhau.
- Mỗi môi trường dev/staging/prod cần image tag, replica, resources, ingress host và secret khác nhau.
- Rollback release cần biết version nào đã deploy.
- CI/CD cần render manifest nhất quán trước khi apply.

Helm giải quyết phần packaging và parameterization. Nhưng Helm cũng tạo thêm một lớp phức tạp: template logic, values precedence, release state và hook lifecycle. Production dùng Helm tốt khi chart rõ ràng, values được quản trị chặt và GitOps/CI kiểm tra render trước khi deploy.

## Mental Model

```text
Chart files + values
        |
        v
Helm render templates
        |
        v
Kubernetes manifests
        |
        v
kube-apiserver apply/create/update
        |
        v
Release revision stored in cluster
```

Helm không thay thế Kubernetes controller. Helm chỉ render và gửi manifest. Sau khi object được tạo, `Deployment`, `StatefulSet`, `Service`, `Ingress controller`, `HPA` và các controller khác vẫn vận hành theo Kubernetes reconciliation loop.

## Lý thuyết cốt lõi

### Chart

`Helm chart` là một package gồm metadata, default values và templates.

```text
my-chart/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── _helpers.tpl
└── charts/
```

Các file quan trọng:

| File/thư mục | Vai trò |
|---|---|
| `Chart.yaml` | Metadata: name, version, appVersion, dependencies |
| `values.yaml` | Default configuration của chart |
| `templates/` | YAML templates dùng Go template syntax |
| `templates/_helpers.tpl` | Helper functions để chuẩn hóa tên, labels, selectors |
| `charts/` | Dependencies đã được vendored hoặc unpacked |

Chart nên mô tả một unit deploy rõ ràng. Với microservice, một chart thường tạo `Deployment`, `Service`, optional `Ingress`, `ConfigMap`, `Secret`, `HPA`, `PDB` và `NetworkPolicy`.

### Release

`Release` là một lần chart được cài vào cluster với một bộ values cụ thể.

Ví dụ cùng một chart có thể cài nhiều release:

```bash
helm install order-api ./service-chart -n dev -f values-dev.yaml
helm install order-api ./service-chart -n prod -f values-prod.yaml
```

Release có revision history:

```bash
helm history order-api -n prod
helm rollback order-api 2 -n prod
```

Helm 3 lưu release state trong Kubernetes `Secret` theo namespace của release. Điều này có nghĩa:

- Mất namespace là mất release history.
- RBAC đọc secret có thể thấy metadata release.
- GitOps tool và Helm đều cần thống nhất ai là owner của release.

### Values và precedence

Values đi vào template qua `.Values`.

Ví dụ template:

```yaml
replicas: {{ .Values.replicaCount }}
image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
```

Nguồn values phổ biến:

| Nguồn | Ví dụ | Độ ưu tiên |
|---|---|---|
| `values.yaml` | default trong chart | Thấp |
| file override | `-f values-prod.yaml` | Cao hơn default |
| nhiều file override | `-f base.yaml -f prod.yaml` | File sau ghi đè file trước |
| CLI set | `--set image.tag=1.2.3` | Cao |
| CLI set file/string | `--set-string`, `--set-file` | Cao |

Production nên hạn chế `--set` thủ công vì khó audit. Tốt hơn là lưu values theo môi trường trong Git.

### Templates và helpers

Helm dùng Go template. Template mạnh nhưng dễ bị lạm dụng.

Helper thường dùng để chuẩn hóa name và labels:

```gotemplate
{{- define "app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
```

Lý do cần helper:

- Tránh name quá 63 ký tự.
- Giữ label selector ổn định.
- Tái sử dụng common labels.
- Giảm copy-paste giữa `Deployment`, `Service`, `Ingress`.

Selector là phần không nên thay đổi tùy tiện. Nếu template đổi label selector của `Deployment`, Kubernetes có thể reject update vì `spec.selector` immutable.

### Dependencies

Chart có thể phụ thuộc chart khác, ví dụ Redis, PostgreSQL, Kafka hoặc common library chart.

Trong `Chart.yaml`:

```yaml
dependencies:
- name: redis
  version: 19.x.x
  repository: https://charts.bitnami.com/bitnami
  condition: redis.enabled
```

Dependency tiện cho lab, nhưng production cần thận trọng:

- Database dependency trong app chart có thể làm lifecycle app và data dính chặt nhau.
- Upgrade app vô tình upgrade dependency stateful.
- Values của dependency có thể phức tạp và khó review.

Với production, stateful platform component thường nên có release/chart riêng, owner riêng và backup/upgrade plan riêng.

### Hooks

Helm hooks chạy resource ở thời điểm đặc biệt như `pre-install`, `post-install`, `pre-upgrade`, `post-upgrade`.

Use case:

- DB migration job.
- Preflight check.
- Cleanup job.

Rủi ro:

- Hook fail làm release fail.
- Hook job chạy lại không idempotent có thể phá dữ liệu.
- Hook resource có thể bị bỏ sót cleanup nếu policy không rõ.

Migration production nên idempotent, có lock, có rollback strategy và tách khỏi deploy app nếu rủi ro cao.

## Deep dive: Helm làm gì và không làm gì

### Helm render trước, Kubernetes reconcile sau

Khi chạy:

```bash
helm upgrade --install api ./chart -n app -f values-prod.yaml
```

Helm thực hiện các bước chính:

1. Merge values.
2. Render templates thành YAML.
3. Gửi object tới Kubernetes API.
4. Lưu release revision.
5. Nếu dùng `--wait`, đợi resource đạt condition phù hợp.

Helm không tự kiểm tra business health. `--wait` chủ yếu dựa vào condition của Kubernetes object. Nếu readinessProbe quá dễ dãi, Helm có thể báo success dù app không xử lý request đúng.

### `helm template` là tuyến phòng thủ đầu tiên

Trước khi đụng cluster:

```bash
helm template api ./chart -f values-prod.yaml
helm lint ./chart
```

Các lỗi có thể bắt sớm:

- YAML invalid.
- Missing required values.
- Name/label sai.
- Resource bị render thừa/thiếu.
- Secret/config không đúng structure.

Nhưng `helm template` không bắt được mọi lỗi Kubernetes API, ví dụ immutable field, RBAC, admission policy hoặc quota. Vì vậy CI tốt thường có thêm validate bằng server-side dry-run hoặc policy tools.

### Release kẹt

Release có thể ở trạng thái `pending-install`, `pending-upgrade`, `failed`.

Nguyên nhân thường gặp:

- Hook job chưa xong hoặc fail.
- `--wait` timeout vì Pod không Ready.
- API request bị admission/RBAC reject.
- Network hoặc client bị ngắt giữa deploy.
- Chart tạo resource đã tồn tại nhưng không thuộc release.

Không nên xóa Secret release thủ công trừ khi đã hiểu hậu quả. Cách xử lý nên bắt đầu bằng:

```bash
helm status <release> -n <namespace>
helm history <release> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | Helm render/apply manifest qua API giống nhau | Behavior phụ thuộc RBAC, admission, CRDs và controllers có sẵn |
| K3s local/lab | Rất phù hợp học Helm nhanh; K3s thường có Traefik và local-path-provisioner mặc định | Chart Ingress/Storage có thể chạy khác khi sang cloud; tránh giả định default Traefik luôn tồn tại |
| Self-managed production | Team kiểm soát Helm repo, registry, CRD lifecycle, release namespace | Phải tự quản lý chart versioning, rollback, secret handling, policy validation |
| EKS/GKE/AKS | Helm vẫn dùng như client-side packaging tool | Cloud quản lý control plane; team vẫn quản lý chart values, IAM/RBAC, cloud LB/CSI annotations và GitOps flow |

Managed Kubernetes không làm chart tự đúng. Chart vẫn phải encode đúng resources, probes, securityContext, service annotations, ingress class và cloud-specific values.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| Raw YAML | App rất nhỏ, học object cơ bản | Copy-paste nhiều, khó quản lý môi trường |
| Helm | Package app reusable, CI/CD, release history | Template logic phức tạp, values drift |
| Kustomize | Patch YAML theo môi trường, ít logic | Không có release history/package dependency như Helm |
| Helm + GitOps | Production deploy có audit và sync | Cần thống nhất owner, tránh `helm upgrade` tay ngoài GitOps |
| Umbrella chart | Lab hoặc bundle hệ thống nhỏ | Coupling lifecycle nhiều service/dependency |
| Chart riêng từng service | Microservices production | Cần chuẩn hóa common chart/pattern |
| `--set` CLI | Override nhanh trong lab/CI đơn giản | Khó audit, dễ sai type |
| Values file trong Git | Production/staging | Cần quản lý secret riêng, review kỹ |

### Best Practices

- Nên chạy `helm lint`, `helm template` và dry-run trước khi deploy.
- Nên dùng labels chuẩn `app.kubernetes.io/*`.
- Nên giữ selector labels ổn định, không phụ thuộc giá trị dễ đổi như version.
- Nên đưa `resources`, probes, `securityContext`, `serviceAccount`, `podAnnotations` vào values có default hợp lý.
- Nên tách secret thật khỏi plain values; dùng External Secrets, SOPS hoặc secret manager.
- Nên pin chart dependency version.
- Nên giữ chart logic đơn giản; template không nên chứa business rules phức tạp.
- Nên dùng `helm upgrade --install --atomic --wait` cho nhiều flow CI/CD, sau khi hiểu timeout và rollback behavior.
- Tránh dùng một umbrella chart lớn để deploy toàn bộ platform nếu team ownership khác nhau.
- Tránh edit live resource do Helm quản lý nếu không đưa thay đổi ngược vào chart/values.

## Performance Considerations

- Helm render chủ yếu tốn CPU client-side; thường không đáng kể với chart nhỏ.
- Chart lớn hoặc umbrella chart có nhiều CRDs/hooks có thể tăng thời gian deploy và API load.
- `--wait` làm pipeline chậm hơn nhưng giảm false success.
- Hook migration chạy lâu có thể kéo dài deployment window và giữ release pending.
- Chart tạo quá nhiều resource nhỏ gây áp lực API server và tăng thời gian reconciliation.
- Dependencies stateful trong cùng release làm rollback chậm và rủi ro hơn app stateless.
- Template quá nhiều `lookup` gọi API cluster có thể làm render phụ thuộc trạng thái live, khó reproduce trong CI.

## Debugging Checklist

Khi Helm render lỗi:

```bash
helm lint ./chart
helm template <release> ./chart -f values.yaml --debug
helm show values ./chart
```

Khi install/upgrade lỗi:

```bash
helm status <release> -n <namespace>
helm history <release> -n <namespace>
helm get values <release> -n <namespace>
helm get manifest <release> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl describe pod <pod> -n <namespace>
```

Kiểm tra:

- Lỗi xảy ra ở render, API apply hay rollout?
- Values nào thực sự được dùng?
- Manifest render có đúng image, selector, labels, resources không?
- Resource có bị admission/RBAC/quota chặn không?
- Pod có Ready không, hay Helm timeout vì readiness/liveness?
- Có hook job fail hoặc kẹt không?
- Release có đang `pending-*` không?

Lab fix khác production fix:

- Lab: sửa chart/values và chạy lại `helm upgrade --install`.
- Production: tạo PR sửa chart/values, render diff, chạy staging, dùng GitOps hoặc pipeline chuẩn để deploy.

## Liên hệ với kiến thức đã biết

Với microservices, Helm giống một build artifact cho deployment config. Backend engineer đã quen package code thành image; Helm package phần Kubernetes runtime contract: port, env, resources, probes, service discovery, ingress, security và scaling knobs.

Helm cũng giống config templating trong Terraform/Ansible ở điểm có biến và module, nhưng khác ở chỗ output là Kubernetes object được các controller reconcile liên tục.

## Tổng kết

Helm là công cụ đóng gói và render Kubernetes manifests theo values. Điểm mạnh của Helm là tái sử dụng chart, quản lý release history và chuẩn hóa deployment giữa môi trường. Điểm yếu là template logic và values drift nếu không có kỷ luật. Production nên xem Helm chart như một API nội bộ: values rõ schema, default an toàn, render được trong CI, deploy qua pipeline/GitOps và luôn có rollback/debug path.

## Câu hỏi tự kiểm tra

1. `Chart`, `release` và `revision` khác nhau thế nào?
2. Vì sao không nên để selector label phụ thuộc image tag hoặc chart version?
3. `helm template` bắt được lỗi gì và không bắt được lỗi gì?
4. Khi nào nên dùng dependency chart, khi nào nên tách release riêng?
5. Vì sao `--atomic --wait` hữu ích nhưng vẫn cần hiểu readinessProbe?

## Tài liệu tham khảo

- Helm Documentation: https://helm.sh/docs/
- Helm Chart Template Guide: https://helm.sh/docs/chart_template_guide/
- Helm Best Practices: https://helm.sh/docs/chart_best_practices/
- Kubernetes Labels Recommended: https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/
- Kubernetes Server-Side Dry Run: https://kubernetes.io/docs/reference/using-api/api-concepts/#dry-run
