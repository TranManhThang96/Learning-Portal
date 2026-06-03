# Day 30: Monitoring

## Mục tiêu bài học

- Hiểu metrics khác logs và traces ở điểm nào, dùng khi nào.
- Nắm kiến trúc Prometheus, scrape target, time series, labels, PromQL và alerting.
- Phân biệt app metrics, Kubernetes object metrics từ kube-state-metrics và node metrics từ node-exporter.
- Biết áp dụng RED metrics cho service và USE metrics cho hạ tầng.
- Biết các lỗi production thường gặp: thiếu scrape target, metric cardinality cao, alert nhiễu, dashboard đẹp nhưng không giúp incident.

## Vấn đề cần giải quyết

Logging trả lời "chuyện gì đã xảy ra". Monitoring phải trả lời nhanh hơn:

- Hệ thống có đang khỏe không?
- Lỗi có đang tăng không?
- Latency có vượt ngưỡng không?
- Pod/node có thiếu CPU, memory, disk hoặc network không?
- Deployment mới có làm service xấu đi không?
- Có cần đánh thức người trực on-call không?

Nếu không có metrics tốt, team chỉ biết sự cố khi user báo lỗi hoặc khi đọc log thủ công. Production Kubernetes cần metrics cho cả application và platform.

## Mental Model

```text
Application / Kubernetes / Node
  |
  +-- exposes /metrics
        |
        v
Prometheus scrape loop
        |
        +-- labels identify target
        +-- samples stored as time series
        |
        v
PromQL queries
        |
        +-- dashboards
        +-- recording rules
        +-- alerting rules
        |
        v
Grafana / Alertmanager / incident response
```

Prometheus chủ động scrape targets. Target không push metric vào Prometheus trong pattern cơ bản. Mỗi sample là một metric name cộng với label set và timestamp.

## Lý thuyết cốt lõi

### Metrics là số theo thời gian

Metric tốt là dữ liệu số có thể query theo thời gian:

```text
http_requests_total{service="checkout",status="500"} 42
http_request_duration_seconds_bucket{le="0.5"} 1234
process_cpu_seconds_total 99.7
```

Metrics phù hợp để:

- Theo dõi xu hướng.
- Tính rate, percentile, saturation.
- Alert khi vượt ngưỡng.
- So sánh trước/sau rollout.

Metrics không phù hợp để lưu payload, stack trace hoặc event chi tiết. Những thứ đó thuộc logs/traces.

### Prometheus data model

Một time series được xác định bởi:

- Metric name.
- Bộ labels.

Ví dụ:

```text
http_requests_total{method="GET",route="/orders",status="200",pod="api-123"}
```

Nếu label có quá nhiều giá trị như `user_id`, `request_id`, `session_id`, số series có thể tăng cực nhanh. Đây gọi là high cardinality. Cardinality cao làm Prometheus tốn RAM/disk và query chậm.

### Counter, gauge, histogram

Các loại metric thường gặp:

- Counter: chỉ tăng, ví dụ tổng số request.
- Gauge: lên xuống, ví dụ memory đang dùng.
- Histogram: phân phối latency/size theo bucket.
- Summary: tính quantile ở client, ít linh hoạt hơn histogram cho aggregation.

PromQL quan trọng:

```promql
rate(http_requests_total[5m])
sum by (service) (rate(http_requests_total[5m]))
histogram_quantile(0.95, sum by (le, service) (rate(http_request_duration_seconds_bucket[5m])))
```

Không dùng giá trị counter raw để alert request rate. Dùng `rate()` hoặc `increase()`.

### RED metrics cho service

RED là bộ metrics cho request-driven service:

- Rate: request per second.
- Errors: error rate hoặc error ratio.
- Duration: latency distribution.

Ví dụ service HTTP cần:

- Tổng request theo route/status.
- 5xx rate.
- p50/p95/p99 latency.
- In-flight requests nếu có.

RED trả lời: user-facing service có đang tốt không?

### USE metrics cho resource

USE là bộ metrics cho resource:

- Utilization: resource dùng bao nhiêu.
- Saturation: có hàng đợi/áp lực không.
- Errors: resource có lỗi không.

Ví dụ node:

- CPU utilization.
- CPU load/run queue hoặc throttling.
- Memory available/pressure.
- Disk usage, I/O latency.
- Network drops/errors.

USE trả lời: hạ tầng có đang nghẽn hoặc lỗi không?

### kube-state-metrics

kube-state-metrics expose trạng thái Kubernetes objects từ API server thành Prometheus metrics. Nó không đo CPU/memory runtime. Nó đo desired/current state của objects.

Ví dụ:

- Deployment replicas desired/available.
- Pod phase.
- Container restart count.
- PVC status.
- Node labels/conditions.
- Job completion/failure.

kube-state-metrics rất hữu ích cho alert như:

- Deployment thiếu replicas.
- Pod restart nhiều.
- PVC Pending.
- Job failed.

### node-exporter

node-exporter expose metrics từ Linux node:

- CPU.
- Memory.
- Filesystem.
- Disk I/O.
- Network.
- Load average.

node-exporter thường chạy DaemonSet để mỗi node có một exporter.

Kubernetes container metrics thường đến từ kubelet/cAdvisor. Node OS metrics thường đến từ node-exporter. Hai nguồn này bổ sung cho nhau.

### Prometheus Operator và kube-prometheus-stack

Trong production, nhiều team dùng Prometheus Operator hoặc chart kube-prometheus-stack. Operator cung cấp CRDs như:

- `Prometheus`
- `Alertmanager`
- `ServiceMonitor`
- `PodMonitor`
- `PrometheusRule`

Thay vì tự viết scrape config thủ công, bạn gắn labels/ServiceMonitor để Prometheus tự discover targets.

Lab trong ngày này dùng Prometheus standalone để thấy cơ chế scrape trực tiếp. Production nên cân nhắc operator để quản lý cấu hình, rule và lifecycle tốt hơn.

### Grafana và Alertmanager

Prometheus không phải UI incident hoàn chỉnh một mình:

- Grafana dùng để xây dashboard, so sánh service/node/object metrics và chia sẻ view cho team.
- Alertmanager nhận alerts từ Prometheus, group/deduplicate/silence/route tới on-call, chat hoặc ticket.

Lab core chỉ chạy Prometheus standalone và nạp rule tối thiểu để hiểu cơ chế. Grafana/Alertmanager có thể chạy như add-on hoặc dùng kube-prometheus-stack trong production.

## Alerting principles

Alert tốt phải action được. Một alert tốt thường có:

- Symptom rõ.
- Impact rõ.
- Threshold có lý do.
- Window đủ dài để tránh nhiễu.
- Runbook link hoặc mô tả bước kiểm tra.

Không alert mọi metric. Nên ưu tiên:

- User-facing symptoms: error ratio, latency, availability.
- Resource saturation gây impact.
- Control plane/platform failure quan trọng.
- Data loss hoặc backup failure.

Ví dụ alert tốt hơn:

```text
Checkout 5xx ratio > 5% for 10 minutes
```

So với alert kém:

```text
Pod CPU > 80%
```

CPU cao có thể bình thường nếu service vẫn latency tốt. CPU throttling hoặc latency tăng mới là tín hiệu tốt hơn.

## Dashboard principles

Dashboard tốt giúp điều tra:

- Golden signals của service.
- Version/Pod/namespace breakdown.
- Recent deploy marker nếu có.
- Error và latency cùng một màn hình.
- Link sang logs/traces theo label tương ứng.

Dashboard xấu chỉ hiển thị nhiều graph nhưng không trả lời câu hỏi vận hành.

## K3s notes

- K3s có metrics-server tùy cách cài. `kubectl top` cần metrics-server, nhưng Prometheus không phụ thuộc `kubectl top`.
- K3s packaged components như CoreDNS, Traefik, local-path-provisioner cũng nên được monitor trong cluster thật.
- Local lab thường không đủ tải để thấy saturation thật. Bạn vẫn có thể học query, labels và alert design.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điều phù hợp | Caveat |
|---|---|---|
| K3s/k3d lab | Học scrape, PromQL, rule, port-forward UI | Không chứng minh retention, HA, node metrics đầy đủ hoặc real load |
| Kubernetes self-managed | Tự chạy Prometheus/Grafana/Alertmanager/kube-state/node-exporter | Team chịu storage, HA, upgrades, alert quality |
| EKS/GKE/AKS | Có cloud metrics/managed Prometheus options | Vẫn cần app metrics, labels, SLO, alert routing |
| kube-prometheus-stack | Baseline production-friendly nhanh | Cần hiểu CRDs, labels, ServiceMonitor/PodMonitor và chart lifecycle |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Rủi ro chính |
|---|---|---|
| Prometheus standalone | Học cơ chế scrape/rules | Config thủ công, không HA, ít discovery |
| Prometheus Operator | Production self-managed | CRD/chart complexity |
| Managed Prometheus | Giảm vận hành backend | Cost, limits, integration details |
| kube-state-metrics | Object state alerts | Không đo CPU/memory runtime |
| node-exporter | Node USE metrics | Cần node-level permissions/DaemonSet |

### Best Practices

- Nên bắt đầu alert từ user-facing symptoms: error ratio, latency, availability.
- Nên dùng kube-state-metrics cho desired/current object state.
- Nên dùng node-exporter và kubelet/cAdvisor cho node/container resource.
- Nên version dashboard/rules như code.
- Tránh labels unbounded trong metrics.

## Performance Considerations

Prometheus tiêu tốn RAM/disk theo số series, scrape interval và retention:

- High-cardinality labels làm RAM và index tăng nhanh.
- Scrape quá dày tạo nhiều samples và network overhead.
- Query regex trên thời gian dài có thể chậm.
- Recording rules giúp giảm query lặp đắt.
- Alert rules quá nhiều hoặc quá nhiễu làm mệt on-call.

Sizing phải tính số targets, series per target, retention, remote write và HA nếu production.

## Debugging Checklist

```bash
kubectl get pod,svc,endpoints -n <monitoring-ns> -o wide
kubectl logs deploy/prometheus -n <monitoring-ns> --tail=100
kubectl exec -n <monitoring-ns> deploy/prometheus -- wget -qO- http://<target>:<port>/metrics
kubectl port-forward -n <monitoring-ns> svc/prometheus 9090:9090
kubectl get configmap -n <monitoring-ns> prometheus-config -o yaml
```

Nếu `up == 0`, kiểm tra Service endpoints, scrape path, DNS và NetworkPolicy. Nếu query chậm, kiểm tra cardinality trước khi tăng CPU/RAM.

## Liên hệ với kiến thức đã biết

Với microservices, metrics là lớp đo SLO/SLA và phát hiện rollout xấu. Logs giải thích chi tiết lỗi, traces cho đường đi request, còn metrics định lượng rate/error/latency/saturation để quyết định có rollback hoặc page on-call không.

## Tóm tắt

Monitoring là lớp phát hiện và định lượng sự cố. Prometheus cung cấp model scrape, time series và PromQL rất mạnh, nhưng chất lượng monitoring phụ thuộc vào metric design, label discipline, RED/USE mental model và alert có thể hành động. Trong Kubernetes, bạn cần nhìn cả app metrics, object state từ kube-state-metrics và node metrics từ node-exporter.

## Câu hỏi tự kiểm tra

1. `up == 1` chứng minh điều gì và không chứng minh điều gì?
2. kube-state-metrics khác node-exporter ở điểm nào?
3. Vì sao error ratio tốt hơn số lỗi raw khi alert?
4. Khi nào cần recording rule?
5. Alertmanager giải quyết vấn đề gì sau khi Prometheus firing alert?

## Production checklist

- [ ] Mỗi service quan trọng expose `/metrics`.
- [ ] Metric labels không chứa `user_id`, `request_id`, `trace_id` hoặc giá trị unbounded.
- [ ] Có RED dashboard cho service user-facing.
- [ ] Có USE dashboard cho node/storage/network.
- [ ] Có kube-state-metrics cho object state.
- [ ] Có node-exporter cho node metrics.
- [ ] Có alert cho error ratio, latency, availability, restart loop, replica unavailable, PVC Pending.
- [ ] Alert có owner và runbook.
- [ ] Prometheus retention, disk sizing và HA strategy rõ.
- [ ] Grafana dashboard được review bằng incident thật hoặc game day.

## Anti-patterns

- Chỉ monitor Pod `Running` rồi kết luận service khỏe.
- Alert CPU cao nhưng không biết user có bị ảnh hưởng không.
- Gắn label `path` raw chứa ID vào HTTP metrics.
- Query p95 latency bằng average.
- Không monitor restart count và rollout health.
- Không có Alertmanager route/escalation rõ.
- Dùng dashboard làm tranh trang trí thay vì incident tool.

## Tài liệu tham khảo

- Prometheus documentation: Data model, PromQL and alerting rules.
- Grafana documentation: Dashboards.
- kube-state-metrics documentation.
- Prometheus node-exporter documentation.
- Kubernetes documentation: Resource metrics pipeline.
