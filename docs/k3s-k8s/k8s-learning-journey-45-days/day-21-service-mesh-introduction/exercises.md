# Bài thực hành - Day 21: Service Mesh introduction

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `curlimages/curl:8.10.1` và `nginx:1.27-alpine`.
- Optional: `linkerd` CLI hoặc `istioctl` nếu muốn cài mesh thật.
- Laptop có đủ tài nguyên; service mesh sidecar có thể làm lab local chậm hơn.
- Command loop/jsonpath trong bài dùng Bash/WSL. Với PowerShell, thay `for i in $(seq 1 10)` bằng `1..10 | ForEach-Object { ... }`.

## Lab Scenario

Bạn triển khai hai version của service `api`, kiểm tra baseline traffic bằng Kubernetes `Service`, sau đó mô phỏng checklist cần có trước khi bật service mesh. Nếu môi trường đủ tài nguyên, bạn cài Linkerd hoặc Istio cho namespace lab và quan sát sidecar/mTLS/metrics. Mục tiêu không phải học sâu từng mesh, mà là hiểu mesh thêm lớp gì vào traffic path.

## Core Path và Stretch Goals

- Core Path: Task 1-3, khoảng 70-85 phút, không yêu cầu cài mesh thật.
- Stretch Goals: Task 4-6, chỉ chạy khi máy đủ tài nguyên và đã có `linkerd` CLI hoặc `istioctl`.

## Task 1: Tạo baseline service-to-service traffic (25 phút)

### Mục tiêu

Chứng minh Kubernetes `Service` đã giải quyết discovery/load balancing cơ bản trước khi thêm mesh.

### Các bước thực hiện

```bash
kubectl create namespace day21
kubectl config set-context --current --namespace=day21
```

Tạo file `baseline.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
      version: v1
  template:
    metadata:
      labels:
        app: api
        version: v1
    spec:
      containers:
      - name: nginx
        image: nginx:1.27-alpine
        command:
        - sh
        - -c
        - |
          echo "api version=v1 pod=$HOSTNAME" > /usr/share/nginx/html/index.html
          nginx -g 'daemon off;'
        ports:
        - name: http
          containerPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-v2
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api
      version: v2
  template:
    metadata:
      labels:
        app: api
        version: v2
    spec:
      containers:
      - name: nginx
        image: nginx:1.27-alpine
        command:
        - sh
        - -c
        - |
          echo "api version=v2 pod=$HOSTNAME" > /usr/share/nginx/html/index.html
          nginx -g 'daemon off;'
        ports:
        - name: http
          containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  ports:
  - name: http
    port: 80
    targetPort: http
---
apiVersion: v1
kind: Pod
metadata:
  name: client
spec:
  serviceAccountName: default
  containers:
  - name: curl
    image: curlimages/curl:8.10.1
    command:
    - sleep
    - "3600"
```

Apply:

```bash
kubectl apply -f baseline.yaml
kubectl rollout status deployment/api-v1
kubectl rollout status deployment/api-v2
kubectl wait --for=condition=Ready pod/client --timeout=90s
kubectl get pods -o wide --show-labels
kubectl get svc,endpoints,endpointslice
```

### Verification

```bash
for i in $(seq 1 10); do kubectl exec client -- curl -s --max-time 3 http://api; done
```

### Expected output

- Client gọi được `http://api`.
- Response có thể trả về cả `v1` và `v2` vì Service selector chọn `app=api`.
- Kubernetes Service không biết canary weight; nó load balance theo endpoint, không theo tỷ lệ release mong muốn.

## Task 2: Xác định vấn đề mà mesh sẽ giải quyết (20 phút)

### Mục tiêu

Không cài mesh khi chưa có use case rõ.

### Các bước thực hiện

Tạo file ghi chú `mesh-decision.md` với các câu trả lời ngắn:

```text
1. Có cần mTLS giữa service nội bộ không? Vì sao?
2. Có cần canary 90/10 thay vì endpoint load balancing không?
3. Có cần policy theo service identity không?
4. Có dashboard request rate/error rate/latency giữa services chưa?
5. Team nào sẽ own mesh upgrade và incident?
```

Kiểm tra hiện trạng Kubernetes:

```bash
kubectl get serviceaccount
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{" sa="}{.spec.serviceAccountName}{" containers="}{.spec.containers[*].name}{"\n"}{end}'
kubectl get networkpolicy
```

### Expected output

- Bạn biết workload đang dùng `ServiceAccount` nào.
- Bạn thấy chưa có sidecar/dataplane container.
- Bạn có câu trả lời cụ thể cho việc mesh có đáng cài trong lab này không.

## Task 3: Inject lỗi mesh-style và debug subset/label (20 phút)

### Mục tiêu

Thấy một lỗi rất phổ biến khi dùng traffic split: route/subset tham chiếu label không tồn tại hoặc workload chưa được inject.

### Các bước thực hiện

Kiểm tra label của các Pod hiện tại:

```bash
kubectl get pods -l app=api --show-labels
kubectl get endpoints api
```

Tạo file đọc hiểu `bad-traffic-split-notes.yaml`:

```yaml
apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: api
spec:
  host: api.day21.svc.cluster.local
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v-two
```

Không apply nếu cluster chưa cài Istio CRD. Trả lời nhanh:

```text
1. Subset v2 đang tìm label nào?
2. Pod api-v2 thật có label nào?
3. Nếu VirtualService route 10% tới subset v2, 10% đó sẽ đi đâu?
4. Nếu dùng Linkerd/Istio injection, command nào xác nhận Pod có proxy container?
```

Kiểm tra command xác nhận sidecar/dataplane:

```bash
kubectl get pod -l app=api -o jsonpath='{range .items[*]}{.metadata.name}{" containers="}{.spec.containers[*].name}{"\n"}{end}'
```

### Expected output

- Pod thật có label `version=v1` hoặc `version=v2`, không có `version=v-two`.
- Đây là lỗi route/subset ở mesh layer, không phải lỗi Kubernetes Service selector.
- Nếu chưa cài mesh, output container chỉ có `nginx`; khi mesh inject đúng, Pod sẽ có thêm proxy/dataplane container.

## Stretch Goals

Các task sau có thể vượt 2 giờ nếu phải cài tool hoặc pull image mới.

## Task 4: Optional - cài Linkerd vào namespace lab (35 phút)

### Mục tiêu

Quan sát sidecar injection và mesh health bằng một mesh đơn giản.

### Các bước thực hiện

Chạy preflight:

```bash
linkerd check --pre
```

Cài control plane nếu preflight đạt:

```bash
linkerd install | kubectl apply -f -
linkerd check
```

Bật injection cho namespace và restart workloads:

```bash
kubectl annotate namespace day21 linkerd.io/inject=enabled
kubectl rollout restart deployment/api-v1 deployment/api-v2
kubectl delete pod client
kubectl apply -f baseline.yaml
kubectl rollout status deployment/api-v1
kubectl rollout status deployment/api-v2
kubectl wait --for=condition=Ready pod/client --timeout=90s
```

Kiểm tra containers:

```bash
kubectl get pods
kubectl get pod -l app=api -o jsonpath='{range .items[*]}{.metadata.name}{" containers="}{.spec.containers[*].name}{"\n"}{end}'
linkerd check
```

### Expected output

- Pod có thêm proxy container.
- `linkerd check` báo control plane và data plane healthy.
- Traffic `client -> api` vẫn hoạt động.

### Troubleshooting

Nếu Pod không có sidecar, kiểm tra namespace annotation và admission webhook:

```bash
kubectl get ns day21 -o yaml
kubectl get mutatingwebhookconfiguration | grep -i linkerd
kubectl describe pod <pod>
```

## Task 5: Optional - quan sát telemetry mesh (20 phút)

### Mục tiêu

Thấy giá trị observability mà mesh thêm vào so với `kubectl logs`.

### Các bước thực hiện

Tạo traffic:

```bash
for i in $(seq 1 30); do kubectl exec client -- curl -s --max-time 3 http://api >/dev/null; done
```

Nếu đã cài Linkerd Viz extension, quan sát:

```bash
linkerd viz stat deploy -n day21
linkerd viz top deploy/api-v1 -n day21
linkerd viz tap deploy/api-v1 -n day21
```

Nếu không cài Viz, dùng Kubernetes-level signal:

```bash
kubectl logs deployment/api-v1 --tail=20
kubectl logs deployment/api-v2 --tail=20
```

### Expected output

- Mesh telemetry cho request-level view nếu extension có sẵn.
- Kubernetes logs vẫn hữu ích nhưng không tự tạo dependency graph hay mTLS status.

## Task 6: Optional - thử Istio traffic split ở mức manifest đọc hiểu (25 phút)

### Mục tiêu

Đọc được ý nghĩa traffic split mà không cần triển khai production mesh.

### Các bước thực hiện

Tạo file `istio-traffic-split-example.yaml` để đọc và phân tích:

```yaml
apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: api
spec:
  host: api.day21.svc.cluster.local
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
---
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: api
spec:
  hosts:
  - api.day21.svc.cluster.local
  http:
  - route:
    - destination:
        host: api.day21.svc.cluster.local
        subset: v1
      weight: 90
    - destination:
        host: api.day21.svc.cluster.local
        subset: v2
      weight: 10
```

Không apply nếu cluster chưa cài Istio CRD. Chỉ trả lời:

```text
1. Service selector chọn Pods nào?
2. DestinationRule subset dựa trên label nào?
3. VirtualService phân bổ traffic ra sao?
4. Nếu Pods v2 thiếu label version=v2 thì chuyện gì xảy ra?
```

### Expected output

- Bạn hiểu mesh traffic split dựa trên route rule và subset label, không dựa vào số lượng replica đơn thuần.

## Cleanup

```bash
kubectl delete namespace day21
```

Nếu đã cài Linkerd riêng cho lab và muốn gỡ:

```bash
linkerd uninstall | kubectl delete -f -
```

## Câu hỏi tự kiểm tra

1. Service mesh thêm gì mà Kubernetes `Service` không có?
2. Vì sao mTLS mesh không thay thế application authorization?
3. Khi nào retry trong mesh có thể làm sự cố nặng hơn?
4. Vì sao cần `ServiceAccount` riêng cho từng workload?
5. Dấu hiệu nào cho thấy mesh đang là overkill với hệ thống hiện tại?

## Đáp án ngắn

1. Mesh thêm mTLS, identity-aware policy, L7 routing, telemetry và retry/timeout nhất quán.
2. mTLS xác thực workload, còn authorization business vẫn nằm ở app/domain logic.
3. Retry request không idempotent hoặc retry đồng loạt khi backend đang quá tải sẽ khuếch đại lỗi.
4. `ServiceAccount` riêng giúp policy/audit theo workload, không gom mọi thứ vào `default`.
5. Ít service, chưa có SLO/owner, chưa đo overhead, và vấn đề hiện tại giải quyết được bằng Service/Ingress/NetworkPolicy.
