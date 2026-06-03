# Bài thực hành - Day 38: CRD và Operator Pattern

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Quyền tạo `CustomResourceDefinition`.
- Không cần viết Operator thật trong bài này.

## Lab Scenario

Bạn sẽ tạo một CRD `WebApp`, tạo custom resource, kiểm tra API discovery, test schema validation, patch status và mô phỏng resource bị kẹt bởi finalizer. Lab này giúp hiểu phần API và lifecycle mà mọi Operator đều dựa vào.

## Core Path (105-115 phút)

- Task 1-6 và Task 8 là phần bắt buộc.
- Task 7 là worksheet/stretch để không biến bài CRD thành bài viết Operator đầy đủ.

## Task 1: Tạo namespace và CRD (20 phút)

```bash
kubectl create namespace day38
```

Tạo file `webapp-crd.yaml`:

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.platform.example.com
spec:
  group: platform.example.com
  scope: Namespaced
  names:
    plural: webapps
    singular: webapp
    kind: WebApp
    shortNames:
    - wa
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        required:
        - spec
        properties:
          spec:
            type: object
            required:
            - image
            - replicas
            properties:
              image:
                type: string
                minLength: 1
              replicas:
                type: integer
                minimum: 1
                maximum: 10
          status:
            type: object
            properties:
              observedGeneration:
                type: integer
              readyReplicas:
                type: integer
              conditions:
                type: array
                items:
                  type: object
                  properties:
                    type:
                      type: string
                    status:
                      type: string
                    reason:
                      type: string
                    message:
                      type: string
    subresources:
      status: {}
```

Apply:

```bash
kubectl apply -f webapp-crd.yaml
kubectl get crd webapps.platform.example.com
kubectl describe crd webapps.platform.example.com
```

### Expected output

- CRD được tạo.
- `kubectl` có thể discover resource `webapps`.

### Câu hỏi

- CRD này namespaced hay cluster-scoped?
- `served` và `storage` nghĩa là gì?
- CRD đã tạo controller chưa?

## Task 2: Kiểm tra API discovery (10 phút)

```bash
kubectl api-resources | findstr WebApp
kubectl explain webapp
kubectl explain webapp.spec
```

Linux/macOS:

```bash
kubectl api-resources | grep WebApp
```

### Câu hỏi

- Vì sao `kubectl explain` biết field của resource mới?
- Nếu schema thiếu field, `kubectl explain` có hữu ích không?

## Task 3: Tạo custom resource hợp lệ (20 phút)

Tạo file `webapp-valid.yaml`:

```yaml
apiVersion: platform.example.com/v1
kind: WebApp
metadata:
  name: checkout
  namespace: day38
spec:
  image: nginx:1.25
  replicas: 2
```

Apply:

```bash
kubectl apply -f webapp-valid.yaml
kubectl get webapps -n day38
kubectl get wa -n day38
kubectl get webapp checkout -n day38 -o yaml
```

### Expected output

- Custom resource được tạo.
- Không có Deployment/Service nào tự sinh ra vì chưa có controller.

Kiểm tra:

```bash
kubectl get deploy,svc -n day38
```

### Câu hỏi

- CRD tồn tại nhưng không có Operator thì chuyện gì không xảy ra?
- `spec` hiện đang là desired state cho ai đọc?

## Task 4: Test schema validation (20 phút)

Tạo file `webapp-invalid.yaml`:

```yaml
apiVersion: platform.example.com/v1
kind: WebApp
metadata:
  name: invalid
  namespace: day38
spec:
  image: ""
  replicas: 50
```

Apply:

```bash
kubectl apply -f webapp-invalid.yaml
```

### Expected output

- API server reject object vì `image` rỗng và `replicas` vượt maximum.

Test thêm object thiếu hẳn `spec`:

```yaml
apiVersion: platform.example.com/v1
kind: WebApp
metadata:
  name: missing-spec
  namespace: day38
```

Apply object này cũng phải bị reject vì CRD root schema có `required: ["spec"]`. Nếu object thiếu `spec` vẫn được tạo, schema của bạn chưa đúng và controller production sẽ phải tự xử lý input rỗng.

Sửa thành:

```yaml
spec:
  image: nginx:1.25
  replicas: 1
```

Apply lại nếu muốn.

### Câu hỏi

- Lỗi này do admission webhook hay schema validation của CRD?
- Nếu schema quá lỏng, lỗi sẽ bị đẩy sang controller như thế nào?

## Task 5: Patch status subresource (20 phút)

Vì lab không có controller, bạn sẽ patch status thủ công để hiểu shape.

```bash
kubectl patch webapp checkout -n day38 --subresource=status --type=merge -p '{
  "status": {
    "observedGeneration": 1,
    "readyReplicas": 2,
    "conditions": [
      {
        "type": "Ready",
        "status": "True",
        "reason": "ManualLab",
        "message": "Status patched manually for learning"
      }
    ]
  }
}'
```

Kiểm tra:

```bash
kubectl get webapp checkout -n day38 -o yaml
```

### Expected output

- `status` xuất hiện trong custom resource.
- `spec` không đổi.

### Câu hỏi

- Trong production ai nên update status?
- `observedGeneration` giúp phát hiện controller stale như thế nào?

## Task 6: Mô phỏng finalizer kẹt (25 phút)

Patch finalizer:

```bash
kubectl patch webapp checkout -n day38 --type=merge -p '{
  "metadata": {
    "finalizers": ["platform.example.com/finalizer"]
  }
}'
```

Delete:

```bash
kubectl delete webapp checkout -n day38 --wait=false
```

`--wait=false` giúp command trả về ngay để lab không block terminal. Sau đó kiểm tra object đang ở trạng thái chờ finalizer:

```bash
kubectl get webapp checkout -n day38 -o yaml
```

Quan sát:

- `deletionTimestamp` tồn tại.
- Finalizer vẫn còn.
- Object chưa bị xóa.

Break-glass cleanup trong lab:

```bash
kubectl patch webapp checkout -n day38 --type=json \
  -p='[{"op":"remove","path":"/metadata/finalizers"}]'
```

Kiểm tra:

```bash
kubectl get webapps -n day38
```

### Câu hỏi

- Vì sao object chưa bị xóa khi đã có `deletionTimestamp`?
- Trong production, vì sao không nên xóa finalizer ngay?
- Controller cần làm gì trước khi remove finalizer?
- Vì sao lab dùng `--wait=false` thay vì để `kubectl delete` chờ vô hạn?

## Task 7: Operator design worksheet (20 phút)

Thiết kế pseudo-Operator cho `WebApp`.

Điền:

```text
Custom resource:
Spec fields:
Child resources:
Status fields:
Finalizer needed? Why?
External systems touched:
RBAC needed:
Failure conditions:
Metrics to expose:
Upgrade risks:
When not to use this Operator:
```

Gợi ý:

```text
Spec:
- image
- replicas
- port
- ingress host

Child resources:
- Deployment
- Service
- optional Ingress

Status:
- observedGeneration
- readyReplicas
- Ready condition
```

### Câu hỏi

- Operator này có thật sự cần thiết hơn Helm chart không?
- Domain logic nào justify controller riêng?

## Task 8: Cleanup

```bash
kubectl delete webapp --all -n day38
kubectl delete crd webapps.platform.example.com
kubectl delete namespace day38
```

Xóa file local nếu không cần:

```bash
Remove-Item -Force .\webapp-crd.yaml,.\webapp-valid.yaml,.\webapp-invalid.yaml
```

Linux/macOS:

```bash
rm -f ./webapp-crd.yaml ./webapp-valid.yaml ./webapp-invalid.yaml
```

## Stretch Goals

- Hoàn thành Task 7 bằng một design note cho controller thật.
- Thêm `conditions` schema chi tiết hơn gồm `type`, `status`, `reason`, `message`, `lastTransitionTime`.
- So sánh cách Helm, Kustomize và Operator xử lý cùng một use case `WebApp`.

## Checklist hoàn thành

- [ ] Tạo được CRD namespaced.
- [ ] Tạo được custom resource hợp lệ.
- [ ] Thấy schema validation reject object sai.
- [ ] Patch được status subresource.
- [ ] Mô phỏng được finalizer kẹt deletion.
- [ ] Giải thích được CRD khác Operator.
- [ ] Viết được Operator design worksheet và biết khi nào không nên viết Operator.
