# Ngày 6: Tài liệu tham khảo - Prometheus, Grafana, ELK

## Cheatsheet lệnh

### Cài đặt qua Helm

```bash
# Thêm repo prometheus-community (chứa chart kube-prometheus-stack)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Cài kube-prometheus-stack (gồm Prometheus + Grafana + Alertmanager + node-exporter + kube-state-metrics)
helm install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# Thêm repo Elastic (chart ECK operator hoặc Elasticsearch/Kibana chuẩn)
helm repo add elastic https://helm.elastic.co
helm repo update

# Cài ECK operator (Elastic Cloud on Kubernetes - quản lý Elasticsearch/Kibana)
helm install elastic-operator elastic/eck-operator \
  --namespace elastic-system --create-namespace
```

### Port-forward để truy cập UI

```bash
# Grafana (service của kube-prometheus-stack thường tên <release>-grafana, port 80)
kubectl port-forward -n monitoring svc/kube-prom-grafana 3000:80

# Prometheus (service <release>-kube-prometheus-prometheus, port 9090)
kubectl port-forward -n monitoring svc/kube-prom-kube-prometheus-prometheus 9090:9090

# Kibana (tuỳ cách cài, ví dụ service kibana-kb-http, port 5601, thường là HTTPS)
kubectl port-forward -n elastic-system svc/kibana-kb-http 5601:5601
```

### Lấy mật khẩu Grafana

```bash
# kube-prometheus-stack tạo Secret chứa user/pass admin cho Grafana
kubectl get secret -n monitoring kube-prom-grafana \
  -o jsonpath="{.data.admin-user}" | base64 --decode; echo
kubectl get secret -n monitoring kube-prom-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode; echo
```

### PromQL mẫu

```txt
# Kiểm tra target có đang được scrape thành công không
up

# Tốc độ request mỗi giây trong 5 phút gần nhất
rate(http_requests_total[5m])

# Tổng tốc độ request, nhóm theo status_code
sum by (status_code) (rate(http_requests_total[5m]))

# p95 latency từ histogram bucket
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
```

## Tài liệu tham khảo

- [Prometheus - Getting Started](https://prometheus.io/docs/prometheus/latest/getting_started/): đọc trước để hiểu cách chạy Prometheus, cấu trúc file config cơ bản. Dùng làm nền tảng trước khi đọc phần Querying.
- [Prometheus - Querying (PromQL)](https://prometheus.io/docs/prometheus/latest/querying/basics/): đọc để hiểu cú pháp PromQL, các hàm `rate`, `sum`, `histogram_quantile`. Dùng khi viết query cho Grafana panel hoặc alert rule.
- [Prometheus - Concepts / Metric Types](https://prometheus.io/docs/concepts/metric_types/): đọc để phân biệt rõ counter/gauge/histogram/summary. Dùng khi viết code instrument app hoặc đọc metric có sẵn.
- [Grafana Documentation](https://grafana.com/docs/grafana/latest/): đọc phần "Dashboards" và "Alerting" trước. Dùng khi tạo dashboard, panel, data source, và alert rule trong Grafana.
- [Elastic - Elasticsearch Guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html): đọc phần "Getting started" và "Index basics". Dùng khi cần hiểu cách Elasticsearch lưu và tìm log.
- [Elastic - Kibana Guide](https://www.elastic.co/guide/en/kibana/current/index.html): đọc phần "Discover" và "Dashboard". Dùng khi tìm kiếm log và tạo visualization trong Kibana.
- [prometheus-community/helm-charts (GitHub)](https://github.com/prometheus-community/helm-charts): đọc README của chart `kube-prometheus-stack` để biết các giá trị `values.yaml` quan trọng. Dùng khi tuỳ biến cài đặt qua Helm.
- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/): đọc phần "Fundamentals" và "Getting started" để hiểu Loki khác Elasticsearch ở điểm nào (index label thay vì full-text). Dùng khi đánh giá lựa chọn ELK vs Loki cho log stack nhẹ hơn.
- ECK (Elastic Cloud on Kubernetes) Helm chart - đường dẫn/tên chart cụ thể cần kiểm chứng trên helm.elastic.co, vì Elastic thay đổi cấu trúc repo theo thời gian.
