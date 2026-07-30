# Ngày 6: Thực hành - Observability với Prometheus, Grafana, ELK

## Lưu ý tài nguyên (đọc trước khi bắt đầu)

Stack quan sát hệ thống (Prometheus + Grafana + Alertmanager + Elasticsearch + Kibana) khá nặng khi chạy cùng lúc trên Minikube. Khuyến nghị:

```bash
# Cấp đủ RAM và CPU cho Minikube trước khi cài (ví dụ 6-8GB RAM, 4 CPU)
minikube start --memory 8192 --cpus 4
```

Nếu máy yếu, có thể cài từng phần: làm xong bài Beginner/Practical (Prometheus + Grafana) rồi tắt (`helm uninstall`) trước khi cài phần Advanced (ELK), hoặc thay ELK bằng Loki (nhẹ hơn nhiều).

## Chuẩn bị

```bash
# Kiểm tra Minikube đang chạy đủ tài nguyên
minikube status
kubectl top nodes 2>/dev/null || echo "metrics-server chưa có, không sao, không bắt buộc cho bài này"

# Thêm Helm repo cần dùng
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add elastic https://helm.elastic.co
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

## Bài 1 (Beginner): Cài kube-prometheus-stack và xem dashboard có sẵn

**Mục tiêu**: Cài Prometheus + Grafana qua Helm, đăng nhập Grafana, xem dashboard cluster/node có sẵn, chạy vài PromQL cơ bản trên Prometheus UI.

**Yêu cầu**: Minikube đang chạy, Helm đã cài, đã thêm repo prometheus-community.

**Các bước**:

1. Cài kube-prometheus-stack:

```bash
helm install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=admin123
```

2. Chờ các Pod sẵn sàng:

```bash
kubectl get pods -n monitoring -w
# Ctrl+C khi thấy tất cả Pod ở trạng thái Running
```

3. Port-forward Grafana và đăng nhập:

```bash
kubectl port-forward -n monitoring svc/kube-prom-grafana 3000:80
```

Mở `http://localhost:3000`, đăng nhập với user `admin`, password `admin123` (đã set ở bước 1).

4. Vào menu Dashboards, mở dashboard có sẵn tên "Kubernetes / Compute Resources / Cluster" hoặc "Node Exporter / Nodes" để xem CPU/memory của cluster và từng node.

5. Port-forward Prometheus và chạy PromQL:

```bash
kubectl port-forward -n monitoring svc/kube-prom-kube-prometheus-prometheus 9090:9090
```

Mở `http://localhost:9090`, vào tab Graph, thử các query:

```txt
up
rate(node_cpu_seconds_total{mode="idle"}[5m])
```

**Kết quả mong đợi**: Đăng nhập được Grafana, thấy dashboard cluster/node có dữ liệu thật. Query `up` trên Prometheus trả về danh sách target với giá trị 1 (đang được scrape thành công).

**Kiến thức luyện tập**: cài Helm chart, port-forward Service, đọc dashboard Grafana có sẵn, chạy PromQL cơ bản.

## Bài 2 (Practical): Expose metrics từ app và tạo ServiceMonitor

**Mục tiêu**: Có 1 app expose endpoint `/metrics`, tạo ServiceMonitor để Prometheus tự scrape, tạo panel Grafana và 1 alert rule.

**Yêu cầu**: Đã hoàn thành Bài 1, có 1 app đơn giản expose metrics (dùng client library Prometheus, ví dụ `prom-client` cho Node.js hoặc `prometheus_client` cho Python), hoặc dùng image có sẵn expose metrics để demo.

**Các bước**:

1. Deploy app có expose `/metrics` (ví dụ dùng image demo `prom/promhttp` hoặc app tự viết có endpoint `/metrics` ở port 8080). Ví dụ Deployment + Service:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-app
  namespace: monitoring
  labels:
    app: demo-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo-app
  template:
    metadata:
      labels:
        app: demo-app
    spec:
      containers:
        - name: demo-app
          image: <image-app-cua-ban-co-expose-/metrics>
          ports:
            - containerPort: 8080
              name: http-metrics
---
apiVersion: v1
kind: Service
metadata:
  name: demo-app
  namespace: monitoring
  labels:
    app: demo-app
spec:
  selector:
    app: demo-app
  ports:
    - name: http-metrics
      port: 8080
      targetPort: 8080
```

2. Tạo ServiceMonitor để Prometheus Operator tự phát hiện và scrape Service trên:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: demo-app
  namespace: monitoring
  labels:
    release: kube-prom   # phải khớp label selector của Prometheus Operator (release name)
spec:
  selector:
    matchLabels:
      app: demo-app
  endpoints:
    - port: http-metrics
      path: /metrics
      interval: 30s
```

```bash
kubectl apply -f demo-app.yaml
kubectl apply -f servicemonitor.yaml

# Kiểm tra Prometheus đã nhận target mới chưa (Status > Targets trên UI, hoặc query)
```

3. Trên Prometheus UI (`http://localhost:9090`), vào Status > Targets, kiểm tra target `demo-app` có trạng thái UP.

4. Tạo panel Grafana: vào Grafana > Dashboards > New Dashboard > Add panel, chọn data source Prometheus, nhập query ví dụ:

```txt
rate(http_requests_total{job="demo-app"}[5m])
```

5. Tạo 1 alert rule đơn giản trong Grafana (Alerting > Alert rules > New alert rule), điều kiện ví dụ: metric target không UP quá 1 phút (`up{job="demo-app"} == 0`).

**Kết quả mong đợi**: Target `demo-app` hiện UP trên Prometheus, panel Grafana hiển thị dữ liệu thật từ app, alert rule ở trạng thái "Normal" khi app đang chạy.

**Kiến thức luyện tập**: ServiceMonitor và Prometheus Operator discovery, viết PromQL cho panel, tạo alert rule cơ bản trong Grafana.

## Bài 3 (Advanced/Differentiating): Cài log stack và điều tra log lỗi

**Mục tiêu**: Cài stack log tập trung, gửi log app vào đó, tìm log của 1 request lỗi, thảo luận cardinality và alert theo golden signals.

**Yêu cầu**: Đã hoàn thành Bài 1-2. Chọn 1 trong 2 lựa chọn log stack tuỳ tài nguyên máy:

- **Lựa chọn A - ELK** (đầy đủ, nặng hơn): dùng khi cần full-text search mạnh, đã quen ELK.
- **Lựa chọn B - Loki** (nhẹ hơn, tích hợp sẵn Grafana): khuyến nghị nếu máy yếu hoặc muốn stack đơn giản.

**Các bước (Lựa chọn B - Loki, khuyến nghị cho Minikube)**:

1. Cài Loki + Promtail (agent thu log) bằng Helm chart chính thức của Grafana:

```bash
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set promtail.enabled=true \
  --set loki.persistence.enabled=false
```

2. Thêm Loki làm data source trong Grafana (thường tự động nếu cài cùng namespace, hoặc thêm thủ công URL `http://loki:3100`).

3. Vào Grafana > Explore, chọn data source Loki, dùng LogQL để tìm log của app:

```txt
{app="demo-app"} |= "error"
```

**Các bước (Lựa chọn A - ELK)**:

1. Cài ECK operator (nếu chưa cài ở phần tài liệu) rồi tạo Elasticsearch + Kibana qua custom resource, hoặc dùng chart Elasticsearch/Kibana/Filebeat riêng của Elastic Helm repo. Cấu hình chi tiết phụ thuộc phiên bản chart hiện tại — kiểm tra README chart trước khi áp dụng, vì cấu trúc values thay đổi giữa các version.

2. Cài Filebeat (DaemonSet) để thu log từ tất cả Node, cấu hình output tới Elasticsearch.

3. Mở Kibana, tạo Data View cho index Filebeat, dùng Discover để tìm log:

```
kubernetes.labels.app: "demo-app" and message: "error"
```

**Bước chung cuối**: cố ý gây lỗi ở app demo (ví dụ gọi endpoint không tồn tại), sau đó tìm đúng dòng log lỗi đó trên Kibana/Loki bằng filter theo label/time range.

**Thảo luận (bắt buộc suy nghĩ, không chỉ chạy lệnh)**:
- Nếu bạn gắn `request_id` làm label cho metric Prometheus, điều gì sẽ xảy ra? (Gợi ý: cardinality explosion — mỗi request tạo 1 time series mới, Prometheus sẽ hết RAM.) Label này chỉ nên gắn vào log, không gắn vào metric.
- Với app demo, thiết kế 1 alert rule theo golden signal "Errors": alert khi tỉ lệ lỗi 5xx vượt X% trong 5 phút. Viết thử PromQL cho điều kiện này.

**Kết quả mong đợi**: Tìm được chính xác dòng log lỗi bạn vừa tạo ra, thông qua filter theo app và nội dung/thời gian. Giải thích được vì sao không nên gắn `request_id` vào label metric.

**Kiến thức luyện tập**: log tập trung, LogQL/Kibana query, nhận diện rủi ro cardinality, thiết kế alert theo golden signals.

## Checklist

- [ ] Minikube chạy với đủ RAM/CPU (`--memory`, `--cpus`)
- [ ] Cài kube-prometheus-stack qua Helm, tất cả Pod Running
- [ ] Đăng nhập được Grafana, xem dashboard cluster/node có sẵn
- [ ] Port-forward Prometheus, chạy được `up` và `rate(...)`
- [ ] Deploy app có `/metrics`, tạo ServiceMonitor, target hiện UP
- [ ] Tạo panel Grafana hiển thị metric app
- [ ] Tạo 1 alert rule trong Grafana
- [ ] Cài log stack (Loki hoặc ELK), gửi log app vào đó
- [ ] Tìm được log của 1 request lỗi cụ thể trên Kibana/Grafana Explore
- [ ] Giải thích được vì sao không gắn `request_id`/`user_id` làm label metric
- [ ] Viết được 1 PromQL alert theo golden signal "Errors"
