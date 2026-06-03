# Day 41 Document: GitOps và ArgoCD Cheatsheet

## CI/CD flow chuẩn

```text
Code commit
  -> unit/integration tests
  -> build container image
  -> scan image
  -> push registry
  -> update GitOps repo
  -> ArgoCD detects diff
  -> sync to cluster
  -> verify health
```

## Pipeline CI mẫu

CI nên tạo artifact và cập nhật GitOps repo, không apply trực tiếp vào cluster production:

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

    - name: Promote by GitOps PR
      run: |
        echo "Open a PR that changes envs/dev/values.yaml image.tag to ${{ github.sha }}"
```

Production hardening:

- Dùng image digest nếu automation hỗ trợ.
- Tách app repo và config repo khi production cần approval riêng.
- CI token chỉ cần quyền registry và quyền mở PR vào GitOps repo.
- ArgoCD dùng read credential cho repo; không cần credential ghi Git.

## Install ArgoCD có version pin

```bash
kubectl create namespace argocd
ARGOCD_VERSION=v2.13.3
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml
kubectl wait --for=condition=available deploy/argocd-server -n argocd --timeout=180s
```

Không dùng `stable` cho runbook production vì manifest có thể đổi theo thời gian.

## Anti-pattern cần tránh

| Anti-pattern | Vì sao nguy hiểm | Thay bằng |
|---|---|---|
| CI dùng `kubectl apply` vào production | Credential cluster nằm ngoài cluster, audit yếu | CI update GitOps repo, ArgoCD sync |
| Deploy `latest` | Không biết chính xác image nào đang chạy | Immutable tag hoặc digest |
| Secret plaintext trong Git | Lộ secret qua repo/history | External Secrets, SOPS, Sealed Secrets |
| Một app quản lý nhiều namespace unrelated | Blast radius lớn khi prune/sync lỗi | Chia `Application` theo app/env |
| Manual hotfix bằng `kubectl edit` | Drift khỏi Git | Commit fix vào Git hoặc dùng emergency process có backport |
| Auto-sync production không có gate | Commit sai deploy ngay | PR approval, sync window, manual sync |

## ArgoCD command nhanh

```bash
argocd login <argocd-server>
argocd app list
argocd app get <app>
argocd app diff <app>
argocd app sync <app>
argocd app history <app>
argocd app rollback <app> <history-id>
argocd app logs <app>
```

Nếu không dùng CLI:

```bash
kubectl get applications -n argocd
kubectl describe application <app> -n argocd
kubectl get pods -n argocd
kubectl logs deploy/argocd-application-controller -n argocd
kubectl logs deploy/argocd-repo-server -n argocd
```

## Trạng thái quan trọng

| Field | Ý nghĩa | Hành động |
|---|---|---|
| `Synced` | Desired và live khớp | Kiểm tra health nếu app lỗi |
| `OutOfSync` | Có diff giữa Git và cluster | Xem diff, sync hoặc sửa Git |
| `Healthy` | Resource chạy ổn | Không có nghĩa app business đúng |
| `Progressing` | Rollout đang diễn ra | Theo dõi deployment/pod |
| `Degraded` | Resource lỗi | `describe`, logs, events |
| `Missing` | Resource desired không có live | Sync hoặc kiểm tra RBAC/admission |

## Repository layout tham khảo

Helm đơn giản:

```text
platform-config/
  apps/
    order-service/
      Chart.yaml
      templates/
      values-dev.yaml
      values-staging.yaml
      values-prod.yaml
```

Helm chart tách app/env:

```text
platform-config/
  charts/
    microservice/
  envs/
    dev/
      order-service-values.yaml
      tracking-service-values.yaml
    prod/
      order-service-values.yaml
      tracking-service-values.yaml
```

Kustomize:

```text
platform-config/
  apps/
    order-service/
      base/
        deployment.yaml
        service.yaml
        kustomization.yaml
      overlays/
        dev/
          kustomization.yaml
          patch.yaml
        prod/
          kustomization.yaml
          patch.yaml
```

## Application manifest mẫu

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

## AppProject mẫu

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: logistics-dev
  namespace: argocd
spec:
  sourceRepos:
  - https://github.com/example/platform-config.git
  destinations:
  - namespace: logistics-dev
    server: https://kubernetes.default.svc
  clusterResourceWhitelist:
  - group: ""
    kind: Namespace
  namespaceResourceWhitelist:
  - group: "*"
    kind: "*"
```

Production nên whitelist chặt hơn thay vì `*`.

## Promotion model

```text
dev:
  image: order-service:git-a1b2c3

staging:
  image: order-service:git-a1b2c3

production:
  image: order-service@sha256:...
```

Promotion tốt là cùng artifact đi qua nhiều môi trường. Không rebuild image riêng cho production từ cùng source vì digest sẽ khác và audit khó hơn.

## Debug flow

```text
1. Git repo/path/revision đúng không?
2. Render Helm/Kustomize có lỗi không?
3. ArgoCD diff nói gì?
4. Sync operation fail ở resource nào?
5. Kubernetes events nói gì?
6. Workload health: Deployment, ReplicaSet, Pod, Service, Ingress.
7. App runtime: logs, metrics, traces.
```

Command:

```bash
argocd app get <app>
argocd app diff <app>
kubectl describe application <app> -n argocd
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl rollout status deploy/<name> -n <namespace>
kubectl logs deploy/<name> -n <namespace>
```

## Checklist production

- [ ] Image tag immutable hoặc pin digest.
- [ ] CI scan image trước khi update GitOps repo.
- [ ] GitOps repo có PR review cho production.
- [ ] ArgoCD `Project` giới hạn repo/namespace/cluster.
- [ ] ArgoCD admin password/token được quản lý an toàn.
- [ ] Secret không nằm plaintext trong Git.
- [ ] Có quy trình emergency change và backport về Git.
- [ ] Có alert cho app `OutOfSync`, `SyncFailed`, `Degraded`.
- [ ] Có rollback procedure kèm database migration strategy.
- [ ] Có smoke test sau sync cho service quan trọng.
