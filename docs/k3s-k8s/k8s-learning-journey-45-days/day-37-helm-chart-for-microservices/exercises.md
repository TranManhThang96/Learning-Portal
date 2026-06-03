# Bài thực hành - Day 37: Tạo Helm Chart cho Microservices

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` và `helm` version 3.
- Đã hiểu Day 36.
- Cluster pull được image `nginx:1.25`; trong lab này `nginx` listen HTTP port 80.
- Optional: Ingress controller nếu muốn test host routing.

## Lab Scenario

Bạn sẽ tạo một chart `microservice-chart` dùng để deploy 2 release khác nhau: `order-api` và `tracking-api`. Cả hai dùng cùng chart nhưng khác values. Starter chart phải hỗ trợ `container.port`, `service.targetPort`, env/config, probes, optional HPA, PDB và `existingSecret`. Sau đó bạn sẽ inject lỗi selector/port để debug object graph từ Helm manifest tới Service endpoints.

## Core Path (105-115 phút)

- Task 1-6 và Task 8 là phần bắt buộc.
- Task 7 là worksheet/stretch để thiết kế values production mà không kéo lab vượt 2 giờ.

## Task 1: Tạo chart và namespace (15 phút)

```bash
kubectl create namespace day37
helm create microservice-chart
```

Xóa bớt phần chưa dùng nếu muốn giữ chart gọn, nhưng giữ hoặc tạo các template sau:

- Có thể giữ `deployment.yaml`, `service.yaml`, `serviceaccount.yaml`, `_helpers.tpl`.
- Nên giữ `hpa.yaml` và thêm `pdb.yaml`, nhưng render chúng bằng `hpa.enabled`/`pdb.enabled`.
- Có thể tạm bỏ `ingress.yaml` và test hook nếu bạn muốn tự thêm sau.

Chuẩn hóa starter chart trước khi deploy:

- `deployment.yaml` dùng `.Values.container.port` cho `containerPort`, đặt tên port là `http`.
- `service.yaml` dùng `.Values.service.port` cho port ngoài Service và `.Values.service.targetPort` cho target; mặc định nên là `http`.
- `deployment.yaml` render env từ `ConfigMap` nếu `.Values.env` có dữ liệu.
- `deployment.yaml` render `envFrom.secretRef` nếu `.Values.existingSecret` được set.
- `deployment.yaml` render readiness/liveness/startup probes từ `.Values.probes`.
- `hpa.yaml` chỉ render khi `.Values.hpa.enabled: true`.
- `pdb.yaml` chỉ render khi `.Values.pdb.enabled: true`.

Nếu chưa có template, dùng các snippet trong `document.md` của Day 37 làm starter. Không dùng chart mặc định của `helm create` nguyên trạng cho lab này vì default chart thường lấy `containerPort` từ `service.port`, dễ làm sai với app không listen cùng port Service.

Chạy lint:

```bash
helm lint ./microservice-chart
```

### Câu hỏi

- Chart này là application chart hay library chart?
- Nếu nhiều service dùng chung chart, file nào là public contract?

## Task 2: Tạo values cho `order-api` (25 phút)

Tạo file `values-order-dev.yaml`:

```yaml
replicaCount: 2

image:
  repository: nginx
  tag: "1.25"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: http

container:
  port: 80

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    memory: 128Mi

podAnnotations:
  app.kubernetes.io/part-of: logistics

env:
  LOG_LEVEL: debug

probes:
  readiness:
    enabled: true
    path: /
    initialDelaySeconds: 5
    periodSeconds: 10
  liveness:
    enabled: true
    path: /
    initialDelaySeconds: 15
    periodSeconds: 20
  startup:
    enabled: false
```

Render:

```bash
helm template order-api ./microservice-chart -n day37 -f values-order-dev.yaml > order-rendered.yaml
kubectl apply --dry-run=server -f order-rendered.yaml
```

Install:

```bash
helm upgrade --install order-api ./microservice-chart -n day37 -f values-order-dev.yaml --wait --timeout 2m
kubectl get deploy,svc,pod,endpoints -n day37
```

### Expected output

- Release `order-api` được deploy.
- Deployment có 2 replicas.
- Service có endpoints nếu Pod Ready.

### Câu hỏi

- Release name ảnh hưởng fullname resource thế nào?
- Service selector đang match label nào?
- Nếu chart không hỗ trợ `.Values.env` hoặc `.Values.existingSecret`, bạn sẽ thêm vào template hay bỏ qua?

## Task 3: Deploy release thứ hai cùng chart (20 phút)

Tạo file `values-tracking-dev.yaml`:

```yaml
replicaCount: 1

image:
  repository: nginx
  tag: "1.25"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8080
  targetPort: http

container:
  port: 80

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    memory: 128Mi

probes:
  readiness:
    enabled: true
    path: /
    initialDelaySeconds: 5
    periodSeconds: 10
  liveness:
    enabled: true
    path: /
    initialDelaySeconds: 15
    periodSeconds: 20
  startup:
    enabled: false
```

Install:

```bash
helm upgrade --install tracking-api ./microservice-chart -n day37 -f values-tracking-dev.yaml --wait --timeout 2m
kubectl get deploy,svc,pod,endpoints -n day37
helm list -n day37
```

### Expected output

- Hai release cùng chart cùng tồn tại trong namespace.
- Tên resource khác nhau theo release.

### Câu hỏi

- Vì sao cùng chart deploy được nhiều release?
- Nếu cả hai release dùng cùng hard-coded `metadata.name`, chuyện gì xảy ra?
- Port `service.port` khác `container.port` ở đâu, và `service.targetPort` nối hai bên thế nào?

## Task 4: Kiểm tra labels và selectors (20 phút)

```bash
kubectl get deploy order-api-microservice-chart -n day37 -o yaml
kubectl get svc order-api-microservice-chart -n day37 -o yaml
kubectl get endpoints order-api-microservice-chart -n day37 -o yaml
```

Nếu tên resource khác do helper chart, lấy tên bằng:

```bash
kubectl get deploy,svc -n day37
```

Ghi lại:

```text
Deployment selector:
Pod template labels:
Service selector:
Endpoint addresses:
```

### Câu hỏi

- Label nào không nên đưa vào selector?
- Vì sao đổi selector của Deployment sau khi tạo thường bị reject?
- Observability dashboard nên query theo label nào?

## Task 5: Inject lỗi Service targetPort (20 phút)

Sửa `values-tracking-dev.yaml` để service trỏ nhầm port:

```yaml
service:
  type: ClusterIP
  port: 8080
  targetPort: 9999
```

Upgrade:

```bash
helm upgrade tracking-api ./microservice-chart -n day37 -f values-tracking-dev.yaml
kubectl get svc,endpoints -n day37
```

Test từ trong cluster:

```bash
kubectl run curl -n day37 --rm -it --image=curlimages/curl:8.7.1 --restart=Never -- \
  curl -sv http://tracking-api-microservice-chart.day37.svc.cluster.local:8080/
```

Nếu tên Service khác, thay URL cho đúng.

### Expected output

- Endpoints có thể vẫn tồn tại nhưng request fail nếu targetPort không có container listen.
- Symptom thường là connection refused hoặc timeout.
- Đây là lỗi chart/values deterministic; nếu request vẫn thành công, kiểm tra lại `service.yaml` có thật sự dùng `.Values.service.targetPort` chưa.

### Câu hỏi

- Endpoints tồn tại có chứng minh app listen đúng port không?
- Lỗi nằm ở chart values, Service template hay app container?
- Bạn sẽ thêm validation nào vào chart để tránh lỗi port?

## Task 6: Inject lỗi readinessProbe (20 phút)

Nếu chart có readinessProbe, đổi path sang endpoint không tồn tại:

```yaml
livenessProbe:
  httpGet:
    path: /healthz-wrong
readinessProbe:
  httpGet:
    path: /readyz-wrong
```

Hoặc sửa template tạm thời rồi upgrade:

```bash
helm upgrade order-api ./microservice-chart -n day37 -f values-order-dev.yaml --wait --timeout 60s
kubectl get pods -n day37
kubectl describe pod <order-pod> -n day37
kubectl get endpoints order-api-microservice-chart -n day37
kubectl get events -n day37 --sort-by=.lastTimestamp
```

### Expected output

- Pod có thể Running nhưng không Ready.
- Service endpoints có thể rỗng.
- Helm `--wait` có thể timeout.

### Câu hỏi

- Readiness khác liveness thế nào trong impact tới Service?
- Probe sai gây lỗi ở Kubernetes hay application contract?
- Production nên test health endpoint ở CI như thế nào?

## Task 7: Thêm production values worksheet (15 phút)

Tạo file nháp `values-order-prod.yaml`:

```yaml
replicaCount: 3
image:
  repository: ghcr.io/example/order-service
  tag: "1.4.0"
resources:
  requests:
    cpu: 300m
    memory: 512Mi
  limits:
    memory: 768Mi
existingSecret: order-service-prod
service:
  type: ClusterIP
  port: 80
  targetPort: http
container:
  port: 8080
envFrom:
  configMaps:
  - order-service-prod-config
  secrets: []
probes:
  readiness:
    enabled: true
    path: /readyz
    initialDelaySeconds: 5
    periodSeconds: 10
  liveness:
    enabled: true
    path: /healthz
    initialDelaySeconds: 15
    periodSeconds: 20
  startup:
    enabled: true
    path: /startupz
    initialDelaySeconds: 0
    periodSeconds: 5
hpa:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
pdb:
  enabled: true
  minAvailable: 2
```

Không cần install nếu image không tồn tại. Chỉ render và review:

```bash
helm template order-api ./microservice-chart -n day37 -f values-order-prod.yaml --debug
```

### Câu hỏi

- Values nào nên do service team quyết định?
- Values nào nên do platform team chuẩn hóa?
- File này có chứa secret thật không?
- `existingSecret` là reference tới Secret có sẵn hay là nơi lưu secret value?

## Task 8: Cleanup

```bash
helm uninstall order-api -n day37
helm uninstall tracking-api -n day37
kubectl delete namespace day37
```

Xóa file local nếu không cần:

```bash
Remove-Item -Recurse -Force .\microservice-chart
Remove-Item -Force .\values-order-dev.yaml,.\values-tracking-dev.yaml,.\values-order-prod.yaml,.\order-rendered.yaml
```

Linux/macOS:

```bash
rm -rf ./microservice-chart ./values-order-dev.yaml ./values-tracking-dev.yaml ./values-order-prod.yaml ./order-rendered.yaml
```

## Stretch Goals

- Hoàn thành Task 7 với một `values-order-prod.yaml` không chứa secret thật.
- Thêm `ingress.yaml` có `ingressClassName` và annotations tách theo environment.
- Chạy `helm lint` và `helm template --debug` cho cả dev/prod values.

## Checklist hoàn thành

- [ ] Dùng cùng chart deploy được 2 release.
- [ ] Starter chart hỗ trợ `container.port`, `service.targetPort`, env, probes, HPA, PDB và `existingSecret`.
- [ ] Hiểu values theo môi trường.
- [ ] Kiểm tra được labels, selectors và endpoints.
- [ ] Debug được lỗi Service port/targetPort.
- [ ] Debug được lỗi readinessProbe làm endpoints rỗng.
- [ ] Viết được production values worksheet không chứa secret thật.
- [ ] Phân biệt được chart owner và service values owner.
