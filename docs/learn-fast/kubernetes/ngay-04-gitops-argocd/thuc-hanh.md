# Ngày 4: Thực hành — GitOps & Argo CD

## Chuẩn bị

1. Minikube đang chạy:
   ```bash
   minikube status
   # Nếu chưa chạy: minikube start
   ```

2. Cài Argo CD vào namespace `argocd`:
   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   kubectl get pods -n argocd -w
   # Chờ đến khi tất cả pod ở trạng thái Running (Ctrl+C để thoát watch)
   ```

3. Port-forward và lấy mật khẩu admin:
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8080:443
   ```
   Mở terminal khác:
   ```bash
   kubectl -n argocd get secret argocd-initial-admin-secret \
     -o jsonpath="{.data.password}" | base64 -d
   ```

4. Đăng nhập UI (https://localhost:8080, user `admin` + mật khẩu vừa lấy) hoặc CLI:
   ```bash
   argocd login localhost:8080 --username admin --password <mật khẩu> --insecure
   ```

5. Chuẩn bị 1 Git repo public (GitHub) chứa manifest hoặc Helm chart từ Ngày 3. Cấu trúc gợi ý:
   ```
   apps/demo/deployment.yaml
   apps/demo/service.yaml
   # hoặc dùng Helm chart Ngày 3:
   charts/demo/Chart.yaml
   charts/demo/values.yaml
   charts/demo/templates/...
   ```
   Push repo này lên GitHub trước khi bắt đầu bài Beginner.

---

## Bài 1 (Beginner): Tạo Application, sync thủ công

**Mục tiêu**: Tạo một Argo CD Application trỏ tới repo manifest, sync thủ công, quan sát Synced/Healthy trên UI.

**Yêu cầu**: Đã hoàn thành phần Chuẩn bị, có repo Git chứa manifest tại `apps/demo/`.

**Các bước**:

1. Tạo file `application-demo.yaml`:
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
       path: apps/demo
     destination:
       server: https://kubernetes.default.svc
       namespace: demo
     syncPolicy:
       syncOptions:
         - CreateNamespace=true
       # Chưa bật automated - sync thủ công ở bài này
   ```

2. Apply Application vào cluster:
   ```bash
   kubectl apply -f application-demo.yaml
   ```

3. Kiểm tra trạng thái qua CLI:
   ```bash
   argocd app get demo-app
   # Trạng thái ban đầu: OutOfSync (vì chưa sync lần nào)
   ```

4. Sync thủ công:
   ```bash
   argocd app sync demo-app
   ```

5. Mở UI (https://localhost:8080), tìm `demo-app`, quan sát trạng thái chuyển thành **Synced** và **Healthy**.

**Kết quả mong đợi**: Pod/Service của app xuất hiện trong namespace `demo`, Argo CD hiển thị Synced + Healthy.

**Kiến thức luyện tập**: Application CRD cơ bản, thao tác sync thủ công qua CLI/UI.

---

## Bài 2 (Practical): Auto-sync, self-heal, drift

**Mục tiêu**: Bật `automated` + `selfHeal`, đổi replicas qua Git, và quan sát Argo CD tự sửa khi có ai sửa tay cluster.

**Yêu cầu**: Đã hoàn thành Bài 1.

**Các bước**:

1. Sửa `application-demo.yaml`, bật syncPolicy automated:
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
       path: apps/demo
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
   Apply lại:
   ```bash
   kubectl apply -f application-demo.yaml
   ```

2. Trong repo Git, sửa `apps/demo/deployment.yaml`, đổi `replicas: 2` thành `replicas: 3`, commit và push:
   ```bash
   git commit -am "scale to 3 replicas"
   git push
   ```

3. Chờ tối đa vài phút (Argo CD poll định kỳ ~3 phút), hoặc chạy `argocd app sync demo-app` để trigger ngay. Xem UI/CLI, replicas trong cluster tự cập nhật thành 3.

4. Mô phỏng drift — sửa tay cluster:
   ```bash
   kubectl scale deployment demo-app -n demo --replicas=5
   ```

5. Quan sát Argo CD phát hiện **OutOfSync** (vì cluster có 5 replicas nhưng Git khai báo 3), sau đó tự động **self-heal** đưa cluster về lại 3 replicas mà không cần con người can thiệp:
   ```bash
   argocd app get demo-app
   kubectl get deployment demo-app -n demo
   ```

**Kết quả mong đợi**: Sau khi commit Git, cluster tự cập nhật theo. Sau khi `kubectl scale` tay, Argo CD tự động đưa cluster về đúng số replicas trong Git.

**Kiến thức luyện tập**: Auto-sync, self-heal, drift detection, cách Git là nguồn sự thật duy nhất.

---

## Bài 3 (Advanced/Differentiating): Deploy Helm chart, mô phỏng CI bump tag, rollback

**Mục tiêu**: Dùng Argo CD deploy Helm chart từ Ngày 3, mô phỏng bước "CI bump image tag", và thực hiện rollback bằng `git revert`.

**Yêu cầu**: Đã hoàn thành Bài 1, Bài 2. Có Helm chart từ Ngày 3 trong repo (`charts/demo/`).

**Các bước**:

1. Tạo Application mới trỏ tới Helm chart:
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
       path: charts/demo
       helm:
         valueFiles:
           - values.yaml
     destination:
       server: https://kubernetes.default.svc
       namespace: demo-helm
     syncPolicy:
       automated:
         prune: true
         selfHeal: true
       syncOptions:
         - CreateNamespace=true
   ```
   Apply:
   ```bash
   kubectl apply -f application-demo-helm.yaml
   argocd app sync demo-app-helm
   ```
   Xác nhận Synced/Healthy trên UI.

2. Mô phỏng "CI bump image tag" — trong `charts/demo/values.yaml`, đổi giá trị tag image (ví dụ `tag: v1` thành `tag: v2`), commit và push:
   ```bash
   git commit -am "CI: bump image tag to v2"
   git push
   ```
   Đây chính là hành động mà Jenkins sẽ thực hiện tự động trong pipeline thật (xem `tai-lieu.md` phần Jenkinsfile).

3. Quan sát Argo CD tự phát hiện thay đổi và deploy phiên bản mới:
   ```bash
   argocd app sync demo-app-helm   # nếu muốn trigger ngay, không chờ poll
   argocd app get demo-app-helm
   kubectl get pods -n demo-helm -o jsonpath='{.items[*].spec.containers[*].image}'
   ```

4. Thực hiện rollback bằng `git revert` (không dùng `argocd app rollback` để giữ đúng triết lý GitOps — mọi thay đổi qua Git):
   ```bash
   git log --oneline    # tìm commit "CI: bump image tag to v2"
   git revert <commit-hash>
   git push
   ```

5. Quan sát Argo CD tự động sync lại về tag image cũ (v1):
   ```bash
   argocd app get demo-app-helm
   kubectl get pods -n demo-helm -o jsonpath='{.items[*].spec.containers[*].image}'
   ```

**Kết quả mong đợi**: Helm chart deploy thành công qua Argo CD. Sau khi đổi tag trong Git, cluster tự cập nhật image mới. Sau khi `git revert`, cluster tự quay lại image cũ — chứng minh rollback = git revert, có audit trail đầy đủ trong Git log.

**Kiến thức luyện tập**: Argo CD + Helm, mô hình CI (bump tag) tách biệt CD (Argo CD deploy), rollback qua Git thay vì script riêng.

---

## Checklist

- [ ] Cài Argo CD vào namespace `argocd` trên Minikube thành công
- [ ] Lấy được mật khẩu admin và đăng nhập UI/CLI
- [ ] Tạo Application trỏ tới repo manifest, sync thủ công thành công (Bài 1)
- [ ] Bật `automated` + `selfHeal`, xác nhận đổi Git tự động cập nhật cluster (Bài 2)
- [ ] Mô phỏng drift bằng `kubectl scale`, xác nhận Argo CD tự self-heal về đúng Git (Bài 2)
- [ ] Deploy thành công Helm chart Ngày 3 qua Argo CD (Bài 3)
- [ ] Mô phỏng CI bump image tag, xác nhận Argo CD tự deploy bản mới (Bài 3)
- [ ] Thực hiện rollback bằng `git revert`, xác nhận cluster quay về bản cũ (Bài 3)
- [ ] Giải thích được sự khác nhau giữa CI push và GitOps pull bằng lời của mình
