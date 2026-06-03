# Bài thực hành - Day 41: CI/CD và GitOps với ArgoCD

## Prerequisites

- Kubernetes/K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- `helm` đã cài.
- `argocd` CLI khuyến nghị cho phần sync/diff; nếu chưa có thì dùng UI hoặc `kubectl describe application`.
- Git repo thật mà ArgoCD controller trong cluster đọc được qua HTTPS/SSH. Public repo là đường nhanh nhất cho lab.
- Có quyền tạo namespace, Deployment, Service và CRD.
- Không dùng folder local trên laptop làm source chính: ArgoCD chạy trong cluster nên không đọc được đường dẫn local của máy bạn nếu repo đó không được expose.

## Lab Scenario

Bạn sẽ cài ArgoCD, tạo một manifest GitOps tối giản cho `order-service`, tạo `Application`, sync bằng ArgoCD, sau đó cố tình tạo drift và lỗi image để luyện debug. Helm chart được để ở stretch vì mục tiêu chính của ngày này là CI/GitOps flow và repo source thật.

Lab này dùng image public để không phụ thuộc registry riêng. Trong production, CI sẽ build và push image riêng rồi update values trong GitOps repo.

Core path khoảng 110 phút: cài ArgoCD, commit manifest vào repo thật, tạo `Application`, kiểm tra drift và debug image lỗi. Pipeline CI chỉ là file mẫu để thấy flow build/scan/push/update GitOps repo, không bắt buộc chạy nếu bạn chưa có registry.

## Task 1: Cài ArgoCD (20 phút)

```bash
kubectl create namespace argocd
ARGOCD_VERSION=v2.13.3
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml
kubectl get pods -n argocd
kubectl wait --for=condition=available deploy/argocd-server -n argocd --timeout=180s
```

Windows PowerShell:

```powershell
$env:ARGOCD_VERSION = "v2.13.3"
kubectl apply -n argocd -f "https://raw.githubusercontent.com/argoproj/argo-cd/$env:ARGOCD_VERSION/manifests/install.yaml"
```

Nếu cluster không có network ra ngoài, tải manifest trước hoặc bỏ qua phần apply và đọc manifest đã chuẩn bị trong môi trường của bạn.

Port-forward UI/API:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Lấy password ban đầu:

```bash
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

Windows PowerShell:

```powershell
$p = kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}'
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p))
```

### Expected output

- Namespace `argocd` có các Pod như `argocd-server`, `argocd-repo-server`, `argocd-application-controller`.
- UI truy cập qua `https://localhost:8080`.

## Task 2: Tạo GitOps repo và manifest app (25 phút)

Tạo namespace app:

```bash
kubectl create namespace logistics-dev
```

Trong Git repo của bạn, tạo path `day41/order-service/order-service.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: logistics-dev
  labels:
    app.kubernetes.io/name: order-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: order-service
  template:
    metadata:
      labels:
        app.kubernetes.io/name: order-service
    spec:
      containers:
      - name: app
        image: nginx:1.25
        ports:
        - containerPort: 80
        readinessProbe:
          httpGet:
            path: /
            port: 80
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: logistics-dev
spec:
  selector:
    app.kubernetes.io/name: order-service
  ports:
  - port: 80
    targetPort: 80
```

Commit và push:

```bash
git add day41/order-service/order-service.yaml
git commit -m "add day41 order-service gitops manifest"
git push
```

Thêm pipeline CI mẫu vào app repo hoặc config repo để thể hiện flow build/scan/push/update GitOps. File này không cần chạy trong lab nếu bạn chưa có registry:

```yaml
# .github/workflows/build-and-promote.yaml
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
      run: docker build -t ghcr.io/<your-user>/order-service:${{ github.sha }} .

    - name: Scan image
      uses: aquasecurity/trivy-action@0.28.0
      with:
        image-ref: ghcr.io/<your-user>/order-service:${{ github.sha }}
        severity: CRITICAL,HIGH
        exit-code: "1"

    - name: Update GitOps desired state
      run: |
        echo "Update image tag/digest in the GitOps repo, then open a PR"
```

### Expected output

- Repo remote có path `day41/order-service/order-service.yaml`.
- ArgoCD controller có thể fetch repo URL đó từ trong cluster.

### Câu hỏi

- Vì sao ArgoCD cần đọc được repo nhưng không nhất thiết cần credential ghi repo?
- Nếu dùng private repo, credential nên được cấp ở đâu?

## Task 3: Tạo ArgoCD Application (20 phút)

Tạo `application.yaml` và thay `repoURL`, `path` theo repo của bạn:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: order-service-dev
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<your-user>/<your-repo>.git
    targetRevision: main
    path: day41/order-service
  destination:
    server: https://kubernetes.default.svc
    namespace: logistics-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Apply:

```bash
kubectl apply -f application.yaml
kubectl get applications -n argocd
kubectl describe application order-service-dev -n argocd
```

Sync nếu chưa auto-sync:

```bash
argocd app sync order-service-dev
```

Không có ArgoCD CLI thì dùng UI hoặc annotation refresh:

```bash
kubectl annotate application order-service-dev -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

### Expected output

- Application trạng thái `Synced`.
- Deployment và Service xuất hiện trong namespace `logistics-dev`.

Verify:

```bash
kubectl get deploy,svc,pod -n logistics-dev
kubectl rollout status deploy/order-service -n logistics-dev
```

## Task 4: Tạo drift và quan sát self-heal (20 phút)

Scale trực tiếp ngoài Git:

```bash
kubectl scale deploy/order-service -n logistics-dev --replicas=5
kubectl get deploy/order-service -n logistics-dev
```

Chờ ArgoCD self-heal:

```bash
kubectl get deploy/order-service -n logistics-dev -w
```

### Expected output

- Replicas trở lại `2` nếu `selfHeal` hoạt động.

### Câu hỏi

- Drift này xảy ra khi nào trong production?
- Khi emergency hotfix bằng `kubectl patch`, cần làm gì để không bị ArgoCD revert?

## Task 5: Inject lỗi image và debug (25 phút)

Sửa manifest trong Git:

```yaml
image: nginx:this-tag-does-not-exist
```

Commit/push và refresh app:

```bash
kubectl annotate application order-service-dev -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

Debug:

```bash
kubectl get application order-service-dev -n argocd
kubectl describe application order-service-dev -n argocd
kubectl get pods -n logistics-dev
kubectl describe pod <pod> -n logistics-dev
kubectl get events -n logistics-dev --sort-by=.lastTimestamp
```

### Expected output

- Application có thể `Synced` nhưng health `Degraded` hoặc workload rollout lỗi.
- Pod mới bị `ImagePullBackOff`.

Fix bằng cách revert image tag trong Git, commit/push và sync lại.

### Câu hỏi

- Vì sao `Synced` không đảm bảo app chạy thành công?
- Evidence nào chỉ rõ lỗi nằm ở image registry/tag?

## Task 6: Cleanup (10 phút)

```bash
kubectl delete application order-service-dev -n argocd
kubectl delete namespace logistics-dev
```

Nếu muốn giữ ArgoCD cho các ngày sau thì không xóa namespace `argocd`.

## Common Pitfalls

- Repo private nhưng chưa cấu hình credential cho ArgoCD.
- `path` sai nên ArgoCD báo không tìm thấy manifest.
- Helm/Kustomize render lỗi nhưng chỉ nhìn Pod nên không thấy nguyên nhân.
- Bật `prune` trên app trỏ nhầm path có thể xóa resource ngoài ý muốn.
- Dùng `latest` làm rollout không đổi vì Pod template không thay đổi.

## Stretch Goals

- Tạo `AppProject` giới hạn chỉ deploy được vào namespace `logistics-dev`.
- Tạo Helm chart cho `order-service` và để Application render Helm.
- Thêm sync wave cho Namespace trước, Deployment sau.
- Thêm PostSync Job smoke test gọi Service nội bộ.
- Dùng image digest thay vì tag.
