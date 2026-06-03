# Bài thực hành - Day 34: RBAC + k9s + Lens cho Operations

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Quyền hiện tại đủ để tạo namespace, Role, RoleBinding và ServiceAccount trong lab.
- Quyền hiện tại đủ để dùng `--as` impersonation trong `kubectl auth can-i`; nếu không, dùng kubeconfig readonly ở Task 6 để verify thật.
- Optional: cài `k9s` và Lens nếu muốn thao tác UI.
- Cluster pull được image `nginx:1.27` và `busybox:1.36`.

## Lab Scenario

Bạn sẽ tạo một namespace `day34`, một workload mẫu, rồi cấp quyền theo từng mức:

- Service account chỉ đọc Pods.
- Thêm quyền đọc logs.
- Kiểm tra quyền bị từ chối bằng `kubectl auth can-i`.
- Tạo token/kubeconfig readonly và dùng identity đó cho k9s/Lens.
- So sánh RoleBinding namespaced với ClusterRoleBinding.

Core path khoảng 105-115 phút. k9s và Lens là optional nếu tool đã có sẵn, nhưng identity readonly trong Task 6 là phần core.

## Core Path (105-115 phút)

- Task 1-6, Task 9 và Task 10 là phần bắt buộc.
- Task 7-8 là UI worksheet optional nếu máy lab có k9s hoặc Lens.

## Task 1: Tạo namespace và app mẫu (10 phút)

```bash
kubectl create namespace day34
kubectl config set-context --current --namespace=day34
```

Tạo file `app.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        ports:
        - name: http
          containerPort: 80
        resources:
          requests:
            cpu: 20m
            memory: 64Mi
          limits:
            memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
  ports:
  - name: http
    port: 80
    targetPort: http
```

Apply:

```bash
kubectl apply -f app.yaml
kubectl rollout status deploy/web
kubectl get pod,svc
```

## Task 2: Tạo ServiceAccount và Role chỉ đọc Pods (15 phút)

Tạo file `pod-reader-rbac.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: viewer
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: viewer-pod-reader
subjects:
- kind: ServiceAccount
  name: viewer
  namespace: day34
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

Apply:

```bash
kubectl apply -f pod-reader-rbac.yaml
kubectl get serviceaccount,role,rolebinding
```

Kiểm tra quyền:

```bash
kubectl auth can-i list pods -n day34 --as=system:serviceaccount:day34:viewer
kubectl auth can-i get pods -n day34 --as=system:serviceaccount:day34:viewer
kubectl auth can-i create pods -n day34 --as=system:serviceaccount:day34:viewer
kubectl auth can-i delete pods -n day34 --as=system:serviceaccount:day34:viewer
kubectl auth can-i get services -n day34 --as=system:serviceaccount:day34:viewer
```

### Expected output

- `list pods` và `get pods` trả `yes`.
- `create pods`, `delete pods`, `get services` trả `no`.

### Câu hỏi

- Vì sao Role này không đọc được Service?
- Vì sao `watch` thường cần cho UI/controller?
- Nếu bạn bind Role này bằng `ClusterRoleBinding`, blast radius thay đổi thế nào?

## Task 3: Debug quyền đọc logs bị thiếu (15 phút)

Kiểm tra quyền logs:

```bash
kubectl auth can-i get pods/log -n day34 --as=system:serviceaccount:day34:viewer
```

Kết quả kỳ vọng: `no`.

Patch Role để thêm `pods/log`:

```bash
kubectl patch role pod-reader --type='json' -p='[
  {"op":"add","path":"/rules/0/resources/-","value":"pods/log"}
]'
```

Kiểm tra lại:

```bash
kubectl describe role pod-reader
kubectl auth can-i get pods/log -n day34 --as=system:serviceaccount:day34:viewer
```

### Câu hỏi

- Vì sao `pods/log` là subresource riêng?
- Read logs production có thể lộ dữ liệu gì?
- Có nên cho mọi developer đọc logs mọi namespace không?

## Task 4: Tạo quyền operations có giới hạn cho Deployment (20 phút)

Tạo file `deployer-rbac.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: deployer
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: deployment-operator
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "patch"]
- apiGroups: ["apps"]
  resources: ["deployments/scale"]
  verbs: ["get", "patch", "update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: deployer-deployment-operator
subjects:
- kind: ServiceAccount
  name: deployer
  namespace: day34
roleRef:
  kind: Role
  name: deployment-operator
  apiGroup: rbac.authorization.k8s.io
```

Apply và kiểm tra:

```bash
kubectl apply -f deployer-rbac.yaml
kubectl auth can-i patch deployments -n day34 --as=system:serviceaccount:day34:deployer
kubectl auth can-i patch deployments/scale -n day34 --as=system:serviceaccount:day34:deployer
kubectl auth can-i delete deployments -n day34 --as=system:serviceaccount:day34:deployer
kubectl auth can-i get secrets -n day34 --as=system:serviceaccount:day34:deployer
```

### Expected output

- Patch Deployment và scale trả `yes`.
- Delete Deployment và get Secrets trả `no`.

### Câu hỏi

- Quyền này có đủ cho CI/CD deploy image mới không?
- Nếu dùng GitOps, CI/CD có cần patch Deployment trực tiếp không?
- Ai nên có quyền delete production Deployment?

## Task 5: So sánh built-in `view`, `edit`, `admin` (15 phút)

Không cần bind thật nếu bạn không muốn. Dùng `kubectl auth can-i` với dry-run tư duy và đọc rules:

```bash
kubectl get clusterrole view -o yaml
kubectl get clusterrole edit -o yaml
kubectl get clusterrole admin -o yaml
```

Tạo RoleBinding tạm cho `view`:

```bash
kubectl create serviceaccount builtin-viewer
kubectl create rolebinding builtin-viewer-view --clusterrole=view --serviceaccount=day34:builtin-viewer
```

Kiểm tra:

```bash
kubectl auth can-i get pods -n day34 --as=system:serviceaccount:day34:builtin-viewer
kubectl auth can-i get secrets -n day34 --as=system:serviceaccount:day34:builtin-viewer
kubectl auth can-i patch deployments -n day34 --as=system:serviceaccount:day34:builtin-viewer
```

Xóa binding tạm nếu muốn:

```bash
kubectl delete rolebinding builtin-viewer-view
```

### Câu hỏi

- Built-in `view` có đủ cho incident reader không?
- Khi nào bạn chọn custom Role thay vì built-in role?
- Vì sao `edit` cần được xem là quyền mạnh?

## Task 6: Tạo token và kubeconfig readonly cho k9s/Lens (25 phút)

Tạo ServiceAccount và Role readonly rộng vừa đủ cho quan sát namespace:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ui-viewer
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ui-readonly
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log", "services", "endpoints", "configmaps", "events"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["events.k8s.io"]
  resources: ["events"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["networking.k8s.io"]
  resources: ["ingresses", "networkpolicies"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ui-viewer-readonly
subjects:
- kind: ServiceAccount
  name: ui-viewer
  namespace: day34
roleRef:
  kind: Role
  name: ui-readonly
  apiGroup: rbac.authorization.k8s.io
```

Lưu thành `ui-readonly-rbac.yaml`, apply:

```bash
kubectl apply -f ui-readonly-rbac.yaml
kubectl auth can-i list events.events.k8s.io -n day34 --as=system:serviceaccount:day34:ui-viewer
kubectl auth can-i get secrets -n day34 --as=system:serviceaccount:day34:ui-viewer
kubectl auth can-i delete pods -n day34 --as=system:serviceaccount:day34:ui-viewer
```

### Expected output

- `list events.events.k8s.io` trả `yes`.
- `get secrets` và `delete pods` trả `no`.

Tạo token ngắn hạn và kubeconfig riêng:

```bash
VIEWER_TOKEN=$(kubectl create token ui-viewer -n day34 --duration=2h)
SERVER=$(kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}')
CA_DATA=$(kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

kubectl config set-cluster day34-cluster \
  --server="$SERVER" \
  --certificate-authority-data="$CA_DATA" \
  --kubeconfig=day34-viewer.kubeconfig

kubectl config set-credentials day34-ui-viewer \
  --token="$VIEWER_TOKEN" \
  --kubeconfig=day34-viewer.kubeconfig

kubectl config set-context day34-ui-viewer \
  --cluster=day34-cluster \
  --user=day34-ui-viewer \
  --namespace=day34 \
  --kubeconfig=day34-viewer.kubeconfig

kubectl config use-context day34-ui-viewer --kubeconfig=day34-viewer.kubeconfig
```

Verify bằng kubeconfig mới, không dùng `--as`:

```bash
kubectl --kubeconfig=day34-viewer.kubeconfig get pods
kubectl --kubeconfig=day34-viewer.kubeconfig get events.events.k8s.io
kubectl --kubeconfig=day34-viewer.kubeconfig get secrets
kubectl --kubeconfig=day34-viewer.kubeconfig delete pod -l app=web
```

### Expected output

- `get pods` chạy được.
- `get events.events.k8s.io` chạy được, dù có thể danh sách rỗng.
- `get secrets` bị `Forbidden`.
- `delete pod` bị `Forbidden`.

Nếu `CA_DATA` rỗng, kiểm tra kubeconfig hiện tại có dùng file CA thay vì embedded CA data không. Trong production, không dùng `--insecure-skip-tls-verify` cho kubeconfig UI.

## Task 7: k9s worksheet (optional, 20 phút)

Mở k9s bằng kubeconfig readonly vừa tạo:

```bash
k9s --kubeconfig day34-viewer.kubeconfig -n day34
```

Thực hiện nếu tool có sẵn:

- Xem Pods của namespace `day34`.
- Xem logs của Pod `web`.
- Describe Service `web`.
- Vào view `:events`.
- Thử thao tác delete/scale. Kết quả kỳ vọng là `Forbidden`.

Ghi lại:

```text
Context:
Namespace:
Can view pods:
Can view logs:
Can delete pod:
Can scale deploy:
RBAC subject used:
```

### Câu hỏi

- k9s đang dùng kubeconfig nào?
- Nếu vô tình dùng kubeconfig admin, thao tác nào trở nên nguy hiểm?
- Bạn sẽ tạo context readonly cho k9s production như thế nào?

## Task 8: Lens worksheet (optional, 20 phút)

Nếu dùng Lens:

- Import file `day34-viewer.kubeconfig`, không dùng production admin context.
- Mở namespace `day34`.
- Xem Workloads -> Deployments -> `web`.
- Xem Pods và logs.
- Xem Network -> Services -> `web`.
- Xem Events.

Ghi lại:

```text
Lens context:
Identity:
Namespace filter:
Visible resources:
Mutation actions available:
Should this identity be used in production:
```

### Câu hỏi

- Lens có thể làm gì ngoài đọc object?
- Bạn có phân biệt rõ staging/prod trong UI không?
- Nếu cluster dùng GitOps, Lens edit live object có rủi ro gì?

## Task 9: Forbidden incident note (10 phút)

Viết note cho case `viewer` ban đầu không đọc được logs:

```text
Symptom:
Subject:
Verb:
Resource:
Namespace:
Evidence:
Root cause:
Fix:
Verification:
Prevention:
```

Evidence nên có:

- `kubectl auth can-i get pods/log ...` trước patch là `no`.
- Role ban đầu chỉ có `pods`.
- Sau patch Role có `pods/log`.
- `can-i` sau patch là `yes`.

## Task 10: Cleanup

```bash
kubectl delete namespace day34
```

## Stretch Goals

- Mở k9s bằng kubeconfig readonly và xác nhận thao tác scale/delete bị chặn.
- Import kubeconfig readonly vào Lens và xác nhận chỉ đọc được Pod, logs và Events.
- Tạo thêm một Role chỉ cho phép restart Deployment qua `patch` và so sánh rủi ro với `update`.

## Checklist hoàn thành

- [ ] Tạo được Role/RoleBinding cho ServiceAccount.
- [ ] Dùng được `kubectl auth can-i` để verify quyền.
- [ ] Hiểu `pods/log` là subresource riêng.
- [ ] Phân biệt RoleBinding và ClusterRoleBinding.
- [ ] Biết rủi ro của built-in `edit`/`admin`.
- [ ] Tạo được token/kubeconfig readonly cho k9s/Lens.
- [ ] Có worksheet k9s/Lens theo least-privilege identity.
- [ ] Viết được incident note cho lỗi `Forbidden`.
