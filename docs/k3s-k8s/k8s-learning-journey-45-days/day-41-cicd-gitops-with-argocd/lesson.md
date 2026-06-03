# Day 41: CI/CD và GitOps với ArgoCD

## Mục tiêu bài học

- Hiểu flow CI/CD thực tế cho Kubernetes: build image, scan, push registry, update manifest/Helm values và deploy.
- Phân biệt rõ CI pipeline và GitOps reconciliation.
- Biết mô hình `ArgoCD Application`, `Project`, sync policy, health status, drift detection và rollback.
- Thiết kế được image tag promotion giữa `dev`, `staging`, `production` mà không deploy trực tiếp từ CI vào cluster.
- Nhận diện rủi ro production: credential, supply chain, sync sai môi trường, secret leakage và rollback không đồng bộ database.

## Vấn đề cần giải quyết

Trước Kubernetes, nhiều team để CI server SSH vào VM, copy artifact, restart process. Với Kubernetes, cách đơn giản nhất là để pipeline chạy:

```bash
kubectl apply -f manifests/
```

Cách này chạy được trong lab nhưng có vấn đề ở production:

- CI cần kubeconfig hoặc token quyền cao.
- Không có source of truth rõ giữa Git, cluster và artifact registry.
- Hotfix bằng `kubectl edit` làm drift khỏi repository.
- Rollback image không đồng nghĩa rollback config/schema.
- Deploy nhiều cluster/môi trường dễ nhầm context.

GitOps giải quyết bằng cách lấy Git làm desired state. CI chỉ build artifact và cập nhật repository cấu hình. ArgoCD chạy trong cluster, quan sát Git và reconcile cluster về đúng trạng thái đã khai báo.

## Mental Model

```text
Developer
  |
  v
App repository
  |
  +-- CI: test -> build image -> scan -> push registry
  |
  v
Config repository hoặc env folder
  |
  +-- update Helm values / Kustomize image tag
  |
  v
ArgoCD
  |
  +-- watches Git
  +-- diffs desired vs live
  +-- syncs Kubernetes objects
  |
  v
Cluster
```

CI là dây chuyền tạo artifact. GitOps là controller đưa cluster về desired state. Không nên trộn hai trách nhiệm này nếu muốn audit, rollback và phân quyền sạch.

## Lý thuyết cốt lõi

### CI pipeline cho Kubernetes

Một pipeline tối thiểu thường có:

| Stage | Mục tiêu | Output |
|---|---|---|
| Test | Chặn lỗi code cơ bản | pass/fail |
| Build image | Đóng gói service thành container image | image digest/tag |
| Scan image | Tìm CVE và policy violation | report/gate |
| Push registry | Lưu immutable artifact | registry URL + digest |
| Update config | Đổi image tag/digest trong GitOps repo | pull request/commit |

Điểm quan trọng: artifact nên immutable. Tag kiểu `latest` không phù hợp promotion vì không audit được chính xác cluster đang chạy image nào.

Ví dụ tag:

```text
registry.example.com/order-service:git-8f4a2c1
registry.example.com/order-service:2026-05-08.3
registry.example.com/order-service@sha256:<digest>
```

Trong production, digest là bằng chứng mạnh nhất. Tag vẫn hữu ích cho con người, nhưng deploy nên pin digest hoặc ghi digest vào metadata.

Pipeline mẫu nên chạy được mà không cần quyền Kubernetes. Ví dụ GitHub Actions tối giản:

```yaml
name: build-and-promote

on:
  push:
    branches:
    - main

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
    - uses: actions/checkout@v4

    - name: Build image
      run: docker build -t ghcr.io/example/order-service:${{ github.sha }} .

    - name: Scan image
      uses: aquasecurity/trivy-action@0.28.0
      with:
        image-ref: ghcr.io/example/order-service:${{ github.sha }}
        severity: CRITICAL,HIGH
        exit-code: "1"

    - name: Push image
      run: |
        echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u "${{ github.actor }}" --password-stdin
        docker push ghcr.io/example/order-service:${{ github.sha }}

    - name: Update GitOps values
      run: |
        yq -i '.image.tag = strenv(GITHUB_SHA)' envs/dev/values.yaml
        git diff -- envs/dev/values.yaml
```

Trong production, bước `Update GitOps values` thường tạo pull request vào config repo thay vì commit thẳng vào branch production. Điểm chính là CI tạo artifact và thay đổi Git desired state; CI không cần `kubectl apply` vào cluster.

### GitOps repository layout

Có hai kiểu phổ biến:

```text
app-repo/
  src/
  chart/
  values-dev.yaml
  values-prod.yaml
```

hoặc:

```text
app-repo/
  src/

platform-config-repo/
  apps/
    order-service/
      base/
      overlays/dev/
      overlays/prod/
```

| Layout | Khi phù hợp | Rủi ro |
|---|---|---|
| Monorepo app + config | Team nhỏ, tốc độ cao, ít môi trường | App team có thể đổi config production quá dễ |
| Tách app repo và config repo | Platform team kiểm soát release tốt hơn | Cần automation cập nhật config |
| Environment folders | Dễ nhìn khác biệt `dev/staging/prod` | Dễ copy-paste lệch |
| Branch per environment | Promotion qua merge branch | Dễ phức tạp conflict và policy |

Với team senior nhưng chưa có platform lớn, layout `apps/<service>/overlays/<env>` hoặc Helm `values-<env>.yaml` là thực dụng.

### ArgoCD Application

`Application` là CRD mô tả:

- Source Git repo/path/chart.
- Destination cluster/namespace.
- Sync policy.
- Project boundary.

Ví dụ tối giản:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: order-service-dev
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/platform-config.git
    targetRevision: main
    path: apps/order-service/envs/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: orders
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

Khái niệm chính:

| Concept | Ý nghĩa |
|---|---|
| `Synced` | Live state khớp desired state |
| `OutOfSync` | Cluster khác Git |
| `Healthy` | Resource chạy ổn theo health check |
| `Degraded` | Resource tồn tại nhưng health xấu |
| `prune` | Xóa resource không còn trong Git |
| `selfHeal` | Tự sửa drift nếu ai đó đổi live object |

`prune` và `selfHeal` rất mạnh. Lab nên bật để hiểu behavior. Production cần rollout theo namespace/project rõ ràng để tránh xóa nhầm resource shared.

### ApplicationSet

`ApplicationSet` tạo nhiều `Application` từ template. Use case:

- Deploy cùng app tới nhiều cluster.
- Deploy nhiều service theo directory generator.
- Deploy preview environment.
- Quản lý fleet cluster.

Ví dụ ý tưởng:

```text
clusters:
  dev-us
  staging-us
  prod-us

ApplicationSet template:
  app: api
  env: each cluster label
```

Nếu chỉ có 2-3 service và một cluster, `Application` đơn giản dễ debug hơn. `ApplicationSet` hữu ích khi số lượng app/cluster đủ lớn để template giảm lỗi thủ công.

### Sync wave và hook

ArgoCD sync theo thứ tự nếu dùng annotation:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "10"
```

Hook có thể chạy trước/sau sync:

- `PreSync`: migration Job, validation.
- `Sync`: resource chính.
- `PostSync`: smoke test.
- `SyncFail`: cleanup hoặc notification.

Không nên biến hook thành deployment engine phức tạp. Migration database nên được thiết kế idempotent, có lock và rollback plan riêng.

## Deep dive: GitOps reconciliation bên trong

ArgoCD hoạt động như một controller:

```text
Git desired state
  |
  v
repo-server renders manifests
  |
  v
application-controller compares desired vs live
  |
  +-- diff
  +-- health assessment
  +-- sync operation
  |
  v
kube-apiserver
```

Với Helm, ArgoCD render chart thành manifest rồi apply vào API server. Vì vậy lỗi có thể nằm ở nhiều lớp:

- Git repo không fetch được.
- Helm template render lỗi.
- Manifest hợp lệ YAML nhưng sai Kubernetes schema.
- RBAC của ArgoCD không đủ quyền apply.
- Admission controller reject workload.
- Resource apply thành công nhưng Pod không healthy.

Debug phải đi theo pipeline này, thay vì chỉ nhìn Pod.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm khác cần chú ý |
|---|---|---|
| K3s local/k3d | ArgoCD chạy như workload bình thường, `Application` giống upstream | Ingress/Traefik mặc định, storage `local-path`, registry local cần cấu hình riêng |
| Kubernetes self-managed | Cần tự lo registry access, TLS, ingress, backup ArgoCD state | ArgoCD HA, Redis, repo credentials và RBAC do team vận hành |
| EKS/GKE/AKS | GitOps model giống nhau | Dùng cloud IAM/workload identity, private registry, managed LB/CSI, nhiều cluster/env hơn |

Trong K3s lab, có thể dùng Docker Hub hoặc local registry. Trong managed Kubernetes, production thường dùng ECR/GAR/ACR và workload identity thay vì long-lived registry secret.

Khi cài ArgoCD, không dùng URL `stable` cho production hoặc bài lab cần tái lập. Pin version cụ thể, ví dụ `v2.13.3`, rồi ghi lại version đó trong runbook. `stable` có thể thay đổi theo thời gian và làm lab hôm nay khác lab tháng sau.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Trade-off |
|---|---|---|
| CI chạy `kubectl apply` | Lab nhanh, prototype | CI giữ credential cluster, audit kém |
| GitOps với ArgoCD | Production, nhiều env, cần audit/drift detection | Cần quản lý repo layout, ArgoCD vận hành thêm |
| Auto-sync | Dev/staging, app ít rủi ro | Commit sai có thể tự deploy |
| Manual sync | Production cần approval | Chậm hơn, vẫn cần người vận hành đúng |
| Helm values update | Team đang dùng Helm | Dễ lệch values giữa env |
| Kustomize overlays | Patch manifest rõ theo env | Nhiều overlay có thể khó bảo trì |
| Tag deploy | Dễ đọc | Mutable tag gây audit yếu nếu không kiểm soát |
| Digest deploy | Chính xác artifact | Khó đọc hơn, cần automation tốt |

### Best Practices

- Dùng immutable tag hoặc digest cho image production.
- CI không nên giữ quyền `cluster-admin`.
- Pin version ArgoCD install manifest và `argocd` CLI, tránh dùng nhánh `stable` không kiểm soát.
- Tách quyền commit app code và quyền approve production config nếu team đủ lớn.
- Dùng PR cho promotion lên staging/production.
- Bật image scanning và policy gate trước khi update GitOps repo.
- Gắn labels chuẩn: `app.kubernetes.io/name`, `version`, `managed-by`, `part-of`.
- Cấu hình ArgoCD `Project` để giới hạn repo, namespace, cluster và resource kind.
- Dùng `sync windows` hoặc approval process cho production nếu cần kiểm soát thời điểm release.
- Tránh dùng `latest`.
- Tránh để secret plaintext trong Git. Dùng External Secrets, SOPS, Sealed Secrets hoặc cloud secret manager.

## Performance Considerations

ArgoCD không nằm trên request path của ứng dụng, nhưng ảnh hưởng đến deployment velocity và control plane load.

Điểm cần chú ý:

- App quá nhiều resource làm diff/render chậm.
- Helm chart phức tạp và values lớn làm repo-server tốn CPU/memory.
- Sync hàng loạt nhiều app có thể tạo burst tới `kube-apiserver`.
- Auto-sync + self-heal trên cluster có nhiều drift có thể gây vòng lặp apply.
- Image pull chậm làm rollout lâu dù ArgoCD đã sync xong.

Tối ưu:

- Chia app theo `Application` hợp lý.
- Tránh một `Application` quản lý quá nhiều namespace unrelated.
- Dùng resource requests/limits cho ArgoCD components.
- Theo dõi metrics của ArgoCD nếu vận hành production.
- Với multi-cluster/fleet, cân nhắc ArgoCD HA và sharding.

## Debugging Checklist

Khi GitOps không deploy như mong đợi:

```bash
kubectl get applications -n argocd
kubectl describe application <app> -n argocd
argocd app get <app>
argocd app diff <app>
argocd app sync <app>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl get pods -n <namespace>
kubectl describe pod <pod> -n <namespace>
```

Triệu chứng thường gặp:

| Symptom | Root cause phổ biến | Fix lab | Fix production |
|---|---|---|---|
| `OutOfSync` liên tục | Có người sửa live object hoặc controller mutate field | Bật self-heal hoặc bỏ field khỏi diff | Dùng ignore differences có kiểm soát, chặn manual edit |
| `ComparisonError` | Repo/path/revision sai, Helm render lỗi | Sửa path/values | Thêm CI render check trước merge |
| `SyncFailed` | RBAC/admission/schema lỗi | Đọc event và sửa manifest | Gate bằng policy/test trước sync |
| App `Synced` nhưng `Degraded` | Pod lỗi runtime, probe fail, image pull | `describe`, `logs` | Rollback release, kiểm tra dependency |
| Rollback không sạch | DB migration không backward-compatible | Redeploy image cũ | Thiết kế expand-contract migration |

## Liên hệ với kiến thức đã biết

Với microservices, GitOps giống event sourcing cho hạ tầng: Git commit là sự kiện thay đổi desired state, ArgoCD là projector đưa cluster về state đó. Khác biệt với API Gateway/Redis/Kafka là GitOps không xử lý request business, nhưng quyết định phiên bản nào của service đang chạy, config nào được áp dụng và ai có quyền thay đổi.

Với kinh nghiệm backend, hãy xem image digest như artifact immutable, Helm values như runtime configuration contract, và ArgoCD sync như deployment transaction có trạng thái quan sát được.

## Tóm tắt

- CI tạo artifact; GitOps deploy desired state từ Git.
- ArgoCD giúp audit, drift detection, rollback và phân quyền tốt hơn `kubectl apply` từ CI.
- Production cần image immutability, secret strategy, repo layout rõ và policy gate.
- `ApplicationSet` hữu ích khi quản lý nhiều app/cluster, nhưng không cần dùng quá sớm.
- Debug GitOps phải đi từ Git source, render, diff, sync, admission đến health của workload.

## Câu hỏi tự kiểm tra

1. Vì sao CI không nên cầm kubeconfig production quyền cao?
2. `Synced` khác `Healthy` như thế nào?
3. Khi nào nên bật `prune` và `selfHeal`?
4. Image tag mutable gây rủi ro gì khi rollback?
5. Nếu ArgoCD báo `Synced` nhưng user vẫn lỗi 500, bạn debug từ đâu?

## Tài liệu tham khảo

- Kubernetes Documentation: https://kubernetes.io/docs/
- Argo CD Documentation: https://argo-cd.readthedocs.io/
- Argo CD ApplicationSet: https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/
- GitOps Principles: https://opengitops.dev/
- SLSA Supply-chain Levels: https://slsa.dev/
