# Ngày 4: Tài liệu tham khảo — GitOps & Argo CD

## Cheatsheet Argo CD

### Cài đặt Argo CD vào Minikube

```bash
# Tạo namespace riêng cho Argo CD
kubectl create namespace argocd

# Cài Argo CD bằng manifest chính thức (bản mới nhất trên nhánh stable)
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Theo dõi các pod khởi động (repo-server, application-controller, server, dex, redis...)
kubectl get pods -n argocd -w
```

### Lấy mật khẩu admin ban đầu

```bash
# Mật khẩu admin mặc định được lưu trong Secret argocd-initial-admin-secret
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
# In ra mật khẩu, dùng để đăng nhập UI/CLI với user "admin"
```

### Port-forward truy cập UI

```bash
# Argo CD API server chạy trên port 443 trong cluster
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Mở https://localhost:8080 (chấp nhận cảnh báo self-signed cert)
```

### Đăng nhập và dùng Argo CD CLI

```bash
# Cài argocd CLI (nếu chưa có) rồi login
argocd login localhost:8080 --username admin --password <mật khẩu vừa lấy> --insecure

# Đổi mật khẩu admin (khuyến nghị ngay sau khi login lần đầu)
argocd account update-password
```

### Quản lý Application qua CLI

```bash
# Tạo Application từ CLI (tương đương apply YAML Application)
argocd app create demo-app \
  --repo https://github.com/<user>/<manifest-repo>.git \
  --path apps/demo \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace demo \
  --sync-policy automated \
  --self-heal \
  --auto-prune

# Sync thủ công
argocd app sync demo-app

# Xem chi tiết trạng thái (Synced/OutOfSync, Healthy/Degraded)
argocd app get demo-app

# Danh sách tất cả Application
argocd app list

# Xem lịch sử sync (để rollback)
argocd app history demo-app

# Rollback về 1 revision cụ thể (thay thế cho git revert nếu cần nhanh)
argocd app rollback demo-app <ID_revision>
```

### YAML Application CRD mẫu — plain manifest

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: demo-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<user>/<manifest-repo>.git
    targetRevision: main
    path: apps/demo          # chứa Deployment/Service YAML thuần
  destination:
    server: https://kubernetes.default.svc
    namespace: demo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### YAML Application CRD mẫu — dùng Helm chart

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: demo-app-helm
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<user>/<manifest-repo>.git
    targetRevision: main
    path: charts/demo         # thư mục chứa Chart.yaml
    helm:
      valueFiles:
        - values.yaml
      # parameters:            # override giá trị cụ thể nếu cần
      #   - name: image.tag
      #     value: v1.2.3
  destination:
    server: https://kubernetes.default.svc
    namespace: demo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### Jenkinsfile tối giản (CI, không đụng cluster)

```txt
// Jenkinsfile - chỉ lo build/test/push image, KHÔNG deploy vào cluster
pipeline {
    agent any

    environment {
        IMAGE = "myrepo/demo-app"
        TAG = "${env.GIT_COMMIT}"   // dùng commit SHA làm tag, tránh dùng "latest"
    }

    stages {
        stage('Build') {
            steps {
                // build Docker image từ app code repo
                sh "docker build -t ${IMAGE}:${TAG} ."
            }
        }

        stage('Test') {
            steps {
                // chạy unit test / integration test
                sh "docker run --rm ${IMAGE}:${TAG} npm test"
            }
        }

        stage('Push image') {
            steps {
                // đẩy image lên registry
                sh "docker push ${IMAGE}:${TAG}"
            }
        }

        stage('Update manifest repo') {
            steps {
                // clone manifest repo, bump tag image, commit + push
                // Argo CD sẽ tự phát hiện thay đổi này và sync
                sh """
                    git clone https://github.com/<user>/<manifest-repo>.git manifest
                    cd manifest
                    sed -i "s|image: .*|image: ${IMAGE}:${TAG}|" apps/demo/deployment.yaml
                    git commit -am "bump image tag to ${TAG}"
                    git push
                """
            }
        }
    }
}
```

## Tài liệu tham khảo

| Link | Đọc gì trước | Dùng để làm gì |
|---|---|---|
| [Argo CD - Getting Started](https://argo-cd.readthedocs.io/en/stable/getting_started/) | Phần cài đặt và login CLI | Cài Argo CD vào cluster, lấy mật khẩu, login CLI đúng cách |
| [Argo CD - Declarative Setup](https://argo-cd.readthedocs.io/en/stable/user-guide/declarative-setup/) | Phần "Application" definition | Viết đúng field cho Application CRD (source, destination, syncPolicy) |
| [Argo CD - Application](https://argo-cd.readthedocs.io/en/stable/operator-manual/application.yaml/) | Toàn bộ file mẫu | Tham chiếu đầy đủ mọi field có thể dùng trong Application CRD |
| [Argo CD - Sync Options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/) | Phần Automated Sync Policy, Sync Options | Hiểu prune, selfHeal, CreateNamespace, sync waves |
| [OpenGitOps - Principles](https://opengitops.dev/) | Trang chủ, phần "Principles" | Nắm 4 nguyên tắc chuẩn của GitOps (declarative, versioned, pulled automatically, continuously reconciled) |
| [Jenkins - Pipeline](https://www.jenkins.io/doc/book/pipeline/) | Phần "Getting started" và "Syntax" | Hiểu cấu trúc Jenkinsfile, stages, để viết pipeline CI tối giản |

---

➡️ [thuc-hanh.md](./thuc-hanh.md)
