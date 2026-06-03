# Bài thực hành - Day 36: Helm Fundamentals

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- `helm` version 3 đã cài.
- Cluster pull được image mặc định từ chart `helm create` hoặc image `nginx`.

## Lab Scenario

Bạn sẽ tạo một Helm chart nhỏ, render manifest, cài release, override values, upgrade, rollback và cố ý tạo lỗi để debug. Mục tiêu là hiểu Helm ở cả 3 lớp: template, release state và Kubernetes runtime.

Đường thực hành chính trong 2 giờ là Task 1-5 và cleanup. Task 6-7 là optional nếu còn thời gian hoặc muốn đào sâu `--atomic` và lỗi template.

## Task 1: Kiểm tra tool và tạo chart (15 phút)

```bash
helm version
kubectl version --client
kubectl create namespace day36
helm create day36-web
```

Quan sát cấu trúc:

```bash
Get-ChildItem -Recurse .\day36-web
```

Nếu dùng Linux/macOS:

```bash
find ./day36-web -maxdepth 3 -type f
```

### Câu hỏi

- `Chart.yaml` khác `values.yaml` thế nào?
- `templates/_helpers.tpl` giải quyết vấn đề gì?
- Vì sao chart mới tạo có nhiều resource optional?

## Task 2: Lint và render chart (20 phút)

```bash
helm lint ./day36-web
helm template web ./day36-web -n day36 > rendered.yaml
```

Kiểm tra manifest render:

```bash
kubectl apply --dry-run=server -f rendered.yaml
```

Tìm các object được render:

```bash
Select-String -Path .\rendered.yaml -Pattern '^kind:'
```

Linux/macOS:

```bash
grep '^kind:' rendered.yaml
```

### Expected output

- `helm lint` không báo lỗi nghiêm trọng.
- `helm template` tạo YAML gồm `ServiceAccount`, `Service`, `Deployment`, optional test hook.
- Server-side dry-run pass nếu cluster chấp nhận manifest.

### Câu hỏi

- `helm template` có cần cluster không?
- Server-side dry-run bắt được loại lỗi nào tốt hơn render offline?
- Nếu admission policy reject manifest, bạn muốn phát hiện ở CI hay lúc deploy?

## Task 3: Install release và đọc release state (20 phút)

```bash
helm install web ./day36-web -n day36
helm list -n day36
helm status web -n day36
helm history web -n day36
kubectl get all -n day36
```

Đọc manifest release:

```bash
helm get values web -n day36
helm get values web -n day36 --all
helm get manifest web -n day36
```

Kiểm tra Secret release:

```bash
kubectl get secrets -n day36
```

### Câu hỏi

- Vì sao `helm get values` mặc định có thể rỗng?
- Release history được lưu ở đâu?
- Nếu namespace bị xóa thì Helm history còn không?

## Task 4: Override values và upgrade (25 phút)

Tạo file `values-day36.yaml`:

```yaml
replicaCount: 2

image:
  repository: nginx
  tag: "1.25"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    memory: 128Mi
```

Render trước:

```bash
helm template web ./day36-web -n day36 -f values-day36.yaml
```

Upgrade:

```bash
helm upgrade web ./day36-web -n day36 -f values-day36.yaml --wait --timeout 2m
helm history web -n day36
kubectl get deploy web-day36-web -n day36
kubectl get pods -n day36
```

### Expected output

- Release có revision mới.
- Deployment có 2 replicas.
- Pod dùng image `nginx:1.25`.

### Câu hỏi

- File values override field nào từ `values.yaml`?
- `--wait` đang đợi điều kiện gì?
- Nếu readinessProbe sai nhưng Pod vẫn Ready, Helm có phát hiện business failure không?

## Task 5: Inject lỗi image và rollback (25 phút)

Upgrade sang image tag không tồn tại:

```bash
helm upgrade web ./day36-web -n day36 \
  --set image.repository=nginx \
  --set image.tag=tag-does-not-exist \
  --wait \
  --timeout 60s
```

Nếu command fail, kiểm tra:

```bash
helm status web -n day36
helm history web -n day36
kubectl get pods -n day36
kubectl describe pod <pod-name> -n day36
kubectl get events -n day36 --sort-by=.lastTimestamp
```

Rollback:

```bash
helm rollback web 2 -n day36 --wait --timeout 2m
helm history web -n day36
kubectl get pods -n day36
```

### Expected output

- Pod lỗi có symptom kiểu `ImagePullBackOff` hoặc rollout timeout.
- `helm history` có revision failed hoặc superseded tùy kết quả.
- Rollback quay lại image hợp lệ.

### Câu hỏi

- Lỗi này là lỗi Helm template, Kubernetes apply hay runtime rollout?
- `helm rollback` rollback resource nào?
- Vì sao production nên dùng image tag immutable hoặc digest?

## Task 6: Thử `--atomic` (optional, 20 phút)

Chỉ làm task này nếu bạn đã hoàn thành rollback ở Task 5 và còn đủ thời gian. `--atomic` rất hữu ích trong CI/CD, nhưng không nên làm core path bị vượt 2 giờ.

Chạy upgrade lỗi với `--atomic`:

```bash
helm upgrade web ./day36-web -n day36 \
  --set image.repository=nginx \
  --set image.tag=still-not-found \
  --wait \
  --atomic \
  --timeout 60s
```

Kiểm tra sau đó:

```bash
helm status web -n day36
helm history web -n day36
kubectl get deploy web-day36-web -n day36 -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### Expected output

- Helm tự rollback khi upgrade fail.
- Deployment quay lại image trước đó.

### Câu hỏi

- `--atomic` có thay thế được canary/blue-green không?
- Nếu lỗi nằm trong DB migration hook không idempotent, rollback có đủ không?
- Timeout nên chọn dựa trên gì?

## Task 7: Debug template error (optional, 15 phút)

Mở `day36-web/templates/deployment.yaml`, tạm sửa một dòng value thành path sai, ví dụ:

```gotemplate
{{ .Values.image.notExisting.requiredField }}
```

Chạy:

```bash
helm template web ./day36-web -n day36 --debug
```

Khôi phục file sau khi quan sát lỗi, rồi chạy lại các check để chắc chart đã trở về trạng thái sạch:

```bash
helm lint ./day36-web
helm template web ./day36-web -n day36 -f values-day36.yaml > rendered.yaml
kubectl apply --dry-run=server -f rendered.yaml
```

Nếu `helm lint` hoặc server-side dry-run vẫn fail, bạn chưa restore đúng template.

### Câu hỏi

- Lỗi này xảy ra trước hay sau khi gọi Kubernetes API?
- `--debug` giúp thấy thêm thông tin gì?
- Làm sao thiết kế values để tránh nil pointer?

## Stretch Goals

Nếu máy lab đã cài plugin `helm diff`, xem diff trước khi upgrade:

```bash
helm diff upgrade web ./day36-web -n day36 -f values-day36.yaml
```

Nếu plugin chưa có, bỏ qua. Không cần cài plugin trong core path vì có thể tốn thời gian hoặc cần network.

## Task 8: Cleanup

```bash
helm uninstall web -n day36
kubectl delete namespace day36
```

Xóa file lab local nếu không cần:

```bash
Remove-Item -Recurse -Force .\day36-web
Remove-Item -Force .\rendered.yaml,.\values-day36.yaml
```

Linux/macOS:

```bash
rm -rf ./day36-web ./rendered.yaml ./values-day36.yaml
```

## Checklist hoàn thành

- [ ] Tạo được chart bằng `helm create`.
- [ ] Render được manifest bằng `helm template`.
- [ ] Validate được manifest bằng server-side dry-run.
- [ ] Install, upgrade và rollback release.
- [ ] Đọc được release values, manifest, status và history.
- [ ] Phân biệt được lỗi render, lỗi apply và lỗi runtime rollout.
- [ ] Hiểu tác dụng và rủi ro của `--wait --atomic`.
- [ ] Optional: chạy được restore check sau khi debug template.
