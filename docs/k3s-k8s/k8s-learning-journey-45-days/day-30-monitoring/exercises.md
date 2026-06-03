# Bài thực hành - Day 30: Monitoring

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `quay.io/brancz/prometheus-example-app:v0.5.0`, `prom/prometheus:v2.54.1` và `curlimages/curl:8.10.1`.
- Port local `9090` còn trống nếu muốn mở Prometheus UI.
- Shell mặc định cho lab là Linux/WSL/Bash.

## Lab Scenario

Bạn sẽ deploy một app có endpoint `/metrics`, deploy Prometheus standalone với scrape config tĩnh, nạp alert/recording rule tối thiểu, tạo traffic và query RED metrics. Lab này giúp hiểu Prometheus core trước khi dùng Prometheus Operator hoặc kube-prometheus-stack.

Core Path dự kiến 95 phút. kube-state-metrics, node-exporter, Grafana và Alertmanager là Stretch Goals có scope rõ vì cài đầy đủ stack có thể vượt 2 giờ.

## Task 1: Tạo namespace (5 phút)

```bash
kubectl create namespace day30
kubectl config set-context --current --namespace=day30
```

## Task 2: Deploy app expose metrics (20 phút)

Tạo file `example-app.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example-app
  labels:
    app: example-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: example-app
  template:
    metadata:
      labels:
        app: example-app
        app.kubernetes.io/name: example-app
        app.kubernetes.io/version: v1
    spec:
      containers:
      - name: app
        image: quay.io/brancz/prometheus-example-app:v0.5.0
        args:
        - --bind=0.0.0.0:8080
        ports:
        - name: web
          containerPort: 8080
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: example-app
  labels:
    app: example-app
spec:
  selector:
    app: example-app
  ports:
  - name: web
    port: 8080
    targetPort: web
```

Apply:

```bash
kubectl apply -f example-app.yaml
kubectl rollout status deploy/example-app
kubectl get pod,svc -o wide
```

Kiểm tra `/metrics`:

```bash
kubectl run curl --image=curlimages/curl:8.10.1 --restart=Never --command -- sleep 3600
kubectl wait --for=condition=Ready pod/curl --timeout=120s
kubectl exec curl -- curl -s http://example-app:8080/metrics | head -40
```

### Expected output

- Service `example-app` trả về Prometheus text format.
- Có metric dạng counter/histogram liên quan request HTTP.

## Task 3: Deploy Prometheus standalone kèm rule file (30 phút)

Tạo file `prometheus.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    rule_files:
    - /etc/prometheus/rules.yml

    scrape_configs:
    - job_name: prometheus
      static_configs:
      - targets:
        - localhost:9090

    - job_name: example-app
      metrics_path: /metrics
      static_configs:
      - targets:
        - example-app.day30.svc.cluster.local:8080
        labels:
          namespace: day30
          app: example-app
  rules.yml: |
    groups:
    - name: day30-core
      rules:
      - alert: ExampleAppTargetDown
        expr: up{job="example-app"} == 0
        for: 2m
        labels:
          severity: ticket
        annotations:
          summary: "example-app scrape target is down"
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:v2.54.1
        args:
        - --config.file=/etc/prometheus/prometheus.yml
        - --storage.tsdb.path=/prometheus
        - --storage.tsdb.retention.time=6h
        - --web.enable-lifecycle
        ports:
        - name: web
          containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        - name: data
          mountPath: /prometheus
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            memory: 512Mi
      volumes:
      - name: config
        configMap:
          name: prometheus-config
      - name: data
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
spec:
  selector:
    app: prometheus
  ports:
  - name: web
    port: 9090
    targetPort: web
```

Apply:

```bash
kubectl apply -f prometheus.yaml
kubectl rollout status deploy/prometheus
kubectl get pod,svc
```

Port-forward:

```bash
kubectl port-forward svc/prometheus 9090:9090
```

Mở `http://localhost:9090` trong browser. Lệnh `port-forward` sẽ giữ terminal, nên chạy trong terminal riêng. Nếu không mở UI, có thể dùng `curl` Pod ở các bước sau.

## Task 4: Query target health và request rate (20 phút)

Trong Prometheus UI, chạy:

```promql
up
```

Rồi:

```promql
up{job="example-app"}
```

Tạo traffic:

```bash
kubectl exec curl -- sh -c 'for i in $(seq 1 100); do curl -s http://example-app:8080/ >/dev/null; done'
```

Query request rate. Tên metric cụ thể có thể khác tùy app, nên trước tiên tìm metric HTTP:

```promql
{job="example-app"}
```

Sau đó thử các hướng:

```promql
rate(http_requests_total[5m])
sum by (app) (rate(http_requests_total[5m]))
```

Nếu app dùng tên metric khác, dùng tên thực tế bạn thấy trong UI.

### Câu hỏi

- `up == 1` chứng minh điều gì?
- `up == 1` có chứng minh user request thành công không?
- Label nào đang xác định series của app?

## Task 5: Verify rules và thực hành RED worksheet (20 phút)

Kiểm tra Prometheus đã nạp rule:

```bash
kubectl exec curl -- curl -s http://prometheus:9090/api/v1/rules | grep ExampleAppTargetDown
kubectl exec curl -- curl -s http://prometheus:9090/api/v1/alerts
```

Expected:

- API `/api/v1/rules` có group `day30-core`.
- Alert `ExampleAppTargetDown` tồn tại nhưng không firing khi target `up`.

Thử tạo lỗi scrape tạm thời:

```bash
kubectl scale deploy/example-app --replicas=0
sleep 150
kubectl exec curl -- curl -s http://prometheus:9090/api/v1/alerts | grep ExampleAppTargetDown
kubectl scale deploy/example-app --replicas=2
kubectl rollout status deploy/example-app
```

Nếu không muốn chờ 2 phút, chỉ cần xác minh rule đã load.

Điền bảng cho service `example-app`:

| RED | Query hoặc metric cần có | Alert đề xuất |
|---|---|---|
| Rate | request/second theo service | Traffic đột ngột về 0 nếu service phải luôn có traffic |
| Errors | 5xx ratio | 5xx ratio > 5% trong 10 phút |
| Duration | p95/p99 latency | p95 > SLO trong 10 phút |

Ví dụ query error ratio nếu metric có label `code`:

```promql
sum(rate(http_requests_total{code=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

Ví dụ query p95 nếu có histogram bucket:

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

Ghi chú: tên metric và label phụ thuộc instrumentation. Điều quan trọng là bạn biết shape của query.

## Verification cuối Core Path

```bash
kubectl get deploy,pod,svc,configmap -o wide
kubectl exec curl -- curl -s http://prometheus:9090/api/v1/targets | grep example-app
kubectl exec curl -- curl -s "http://prometheus:9090/api/v1/query?query=up" | grep example-app
kubectl exec curl -- curl -s http://prometheus:9090/api/v1/rules | grep day30-core
```

Expected:

- Prometheus target `example-app` health là `up`.
- Rule group `day30-core` được load.
- Bạn viết được ít nhất một query Rate, Errors và Duration hoặc ghi rõ metric nào app thiếu.

## Stretch Goal 1: kube-state-metrics practical add-on (30 phút)

kube-state-metrics thường cung cấp các metric như:

```text
kube_deployment_status_replicas_available
kube_deployment_spec_replicas
kube_pod_container_status_restarts_total
kube_persistentvolumeclaim_status_phase
kube_job_status_failed
```

Viết alert expression draft:

Deployment thiếu replica:

```promql
kube_deployment_status_replicas_available{namespace="prod"}
<
kube_deployment_spec_replicas{namespace="prod"}
```

Container restart tăng:

```promql
increase(kube_pod_container_status_restarts_total{namespace="prod"}[15m]) > 3
```

PVC Pending:

```promql
kube_persistentvolumeclaim_status_phase{phase="Pending"} == 1
```

Practical path:

1. Nếu cluster đã có kube-state-metrics, port-forward Service và đọc `/metrics`.
2. Nếu chưa có, cài bằng manifest/chart chính thức của môi trường lab hoặc dùng kube-prometheus-stack ở một ngày riêng.
3. Thêm scrape job theo mẫu trong `document.md`.
4. Query ít nhất một metric object state.

Verification:

```bash
kubectl get deploy,svc -A | grep kube-state-metrics
kubectl port-forward -n <ksm-namespace> svc/<ksm-service> 8080:8080
curl -s http://localhost:8080/metrics | grep kube_deployment_status_replicas_available | head
```

### Câu hỏi

- Vì sao kube-state-metrics không thay thế app metrics?
- Alert restart count nên áp dụng cho mọi Pod hay chỉ workload production?
- PVC Pending alert nên route cho team app hay platform?

## Stretch Goal 2: node-exporter, Grafana và Alertmanager scope (30 phút)

node-exporter thường cung cấp các metric như:

```text
node_cpu_seconds_total
node_memory_MemAvailable_bytes
node_filesystem_avail_bytes
node_disk_io_time_seconds_total
node_network_receive_errs_total
```

Điền bảng:

| Resource | Utilization | Saturation | Errors |
|---|---|---|---|
| CPU | CPU busy ratio | load/run queue, throttling | usually app-level |
| Memory | available memory | memory pressure, swap | OOM events |
| Disk | used bytes | I/O wait, latency | disk errors |
| Network | throughput | drops/queue | rx/tx errors |

Practical path cho node-exporter:

1. Nếu cluster đã có node-exporter, kiểm tra Service và `/metrics`.
2. Nếu chưa có, cài bằng manifest/chart chính thức hoặc kube-prometheus-stack.
3. Thêm scrape job theo mẫu trong `document.md`.
4. Query CPU/memory/filesystem/network theo bảng USE.

Practical path cho Grafana/Alertmanager:

1. Deploy hoặc dùng stack có sẵn.
2. Grafana datasource trỏ về `http://prometheus.day30.svc.cluster.local:9090`.
3. Alertmanager nhận alert từ Prometheus qua `alerting` config.
4. Tạo dashboard tối thiểu: `up`, request rate, error ratio, p95 latency.

Verification:

```bash
kubectl get daemonset,svc -A | grep node-exporter
kubectl get deploy,svc -A | grep -E 'grafana|alertmanager'
```

### Câu hỏi

- Node CPU cao khi nào là vấn đề thật?
- Memory available thấp khác gì container `OOMKilled`?
- Disk full trên node ảnh hưởng Pod như thế nào?

## Task 8: Cleanup

```bash
kubectl delete namespace day30
```

## Checklist hoàn thành

Core:

- [ ] Deploy được app có `/metrics`.
- [ ] Deploy được Prometheus standalone và thấy target `up`.
- [ ] Prometheus load được rule group `day30-core`.
- [ ] Tạo traffic và query được metric request.
- [ ] Viết được RED worksheet cho service.
- [ ] Giải thích được vì sao tránh high-cardinality labels.

Stretch:

- [ ] Viết được alert draft cho kube-state-metrics.
- [ ] Viết được USE worksheet cho node-exporter.
- [ ] Mô tả được scope Grafana/Alertmanager khi chuyển sang stack đầy đủ.
