# Day 29: Logging

## Mục tiêu bài học

- Hiểu đường đi của log từ container `stdout`/`stderr` tới node và backend tập trung.
- Phân biệt log local bằng `kubectl logs` với log aggregation bằng Fluent Bit, Elasticsearch/OpenSearch hoặc Loki.
- Biết thiết kế log format, labels, retention và quyền truy cập log cho microservices.
- Biết debug các lỗi thường gặp: Pod restart mất log hiện tại, log collector không đọc được file, log bị thiếu metadata, multiline stack trace bị cắt sai.
- Nắm các production caveat khi dùng EFK/ELK hoặc Loki trong Kubernetes.

## Vấn đề cần giải quyết

Khi chạy trên máy local, developer thường đọc log trực tiếp từ terminal hoặc file. Trên Kubernetes, Pod có thể:

- Restart và đổi container ID.
- Bị reschedule sang node khác.
- Có nhiều replica cùng ghi log.
- Có nhiều container trong cùng Pod.
- Bị xóa theo rollout hoặc autoscaling.

Nếu chỉ dựa vào `kubectl logs`, bạn có thể debug nhanh một Pod còn tồn tại, nhưng không đủ cho production incident. Production cần log aggregation để trả lời:

- Request lỗi đã đi qua service nào?
- Pod nào tạo lỗi, chạy trên node nào, image version nào?
- Lỗi bắt đầu từ thời điểm nào?
- Có bao nhiêu request bị ảnh hưởng?
- Log còn đủ retention để điều tra sau vài ngày không?

## Mental Model

```text
Application process
  |
  +-- stdout/stderr
        |
        v
Container runtime log file on node
        |
        v
Kubelet exposes logs to kubectl logs
        |
        v
Node log collector DaemonSet
        |
        +-- parse
        +-- enrich with Kubernetes metadata
        +-- filter/drop/redact
        |
        v
Log backend: Loki, Elasticsearch/OpenSearch, cloud logging
        |
        v
Query, dashboard, alert, incident analysis
```

Kubernetes không phải log database. Kubernetes chỉ chuẩn hóa cách container ghi log ra `stdout`/`stderr` và cách kubelet cho phép đọc log của container. Việc lưu trữ, index, query, retention và phân quyền log là trách nhiệm của observability stack.

## Lý thuyết cốt lõi

### stdout/stderr là default tốt nhất

Ứng dụng trong container nên ghi log ra `stdout` và `stderr`, không ghi vào file nội bộ trừ khi có lý do rõ. Lý do:

- Container runtime đã biết cách capture `stdout`/`stderr`.
- `kubectl logs` đọc được ngay.
- Log collector trên node có thể tail file runtime chuẩn.
- Không cần sidecar chỉ để copy file log.
- Pod restart không làm app phải quản lý rotation nội bộ.

Nếu app legacy bắt buộc ghi file, bạn có thể dùng sidecar hoặc cấu hình app chuyển sang console logging. Nhưng sidecar tail file làm tăng độ phức tạp: volume sharing, multiline parsing, backpressure và lifecycle ordering.

### Log local và log tập trung khác nhau

`kubectl logs` phù hợp cho debug nhanh:

```bash
kubectl logs deploy/api
kubectl logs pod/api-xxxxx -c api --previous
kubectl logs -l app=api --since=10m --tail=200
```

Nhưng `kubectl logs` có giới hạn:

- Chỉ đọc được log container còn tồn tại hoặc log previous của container vừa crash.
- Không phải công cụ query nhiều ngày.
- Không join log giữa nhiều service.
- Không có index, alert, retention policy, phân quyền theo team.

Log aggregation giải quyết phần dài hạn bằng cách thu log từ node, thêm metadata Kubernetes rồi đẩy vào backend.

### Metadata quyết định khả năng query

Một dòng log thô như sau rất khó vận hành:

```text
payment failed
```

Một dòng log có cấu trúc và metadata tốt:

```json
{"ts":"2026-05-07T08:30:00Z","level":"error","service":"payment","trace_id":"4bf92f","order_id":"o-123","msg":"payment provider timeout"}
```

Backend còn cần Kubernetes metadata:

- `namespace`
- `pod`
- `container`
- `node`
- `deployment` hoặc `statefulset`
- `app.kubernetes.io/name`
- `app.kubernetes.io/version`
- `team`
- `environment`

Nếu label taxonomy kém, query sẽ kém. Observability bắt đầu từ naming và labels, không chỉ từ tool.

### EFK/ELK pattern

EFK/ELK thường gồm:

- Fluent Bit hoặc Fluentd làm collector.
- Elasticsearch hoặc OpenSearch làm backend index/search.
- Kibana hoặc OpenSearch Dashboards làm UI.

Điểm mạnh:

- Full-text search mạnh.
- Query log linh hoạt.
- Phù hợp nhiều loại log.

Điểm cần cẩn thận:

- Elasticsearch/OpenSearch vận hành nặng hơn Loki.
- Index cardinality và retention ảnh hưởng chi phí lớn.
- Cần capacity planning cho disk, shard, replica, lifecycle policy.
- Không nên index mọi field động từ JSON log mà chưa kiểm soát schema.

### Loki pattern

Loki thường gồm:

- Promtail, Fluent Bit, Vector hoặc Alloy làm collector.
- Loki làm log store.
- Grafana làm UI.

Loki index labels, không index toàn bộ nội dung log như Elasticsearch. Điều này giảm chi phí index nhưng yêu cầu chọn label cẩn thận.

Label tốt:

- `namespace`
- `app`
- `container`
- `cluster`
- `environment`

Label xấu:

- `request_id`
- `user_id`
- `order_id`
- `trace_id`

Các giá trị có cardinality cao không nên là label. Chúng nên nằm trong nội dung log để filter sau khi đã chọn stream hợp lý.

### Multiline logs

Stack trace thường trải nhiều dòng. Nếu collector xử lý từng dòng riêng lẻ, một exception có thể biến thành nhiều event rời rạc.

Ưu tiên:

- Ghi JSON log một dòng cho mỗi event.
- Nếu dùng ngôn ngữ có stack trace multiline, cấu hình collector multiline parser.
- Đảm bảo timestamp nằm ở dòng đầu event.

Multiline parsing sai có thể tạo ra hai lỗi nghiêm trọng: mất context hoặc gom nhiều event không liên quan thành một log lớn.

### Retention, cost và compliance

Log production có chi phí thật:

- Ingest volume.
- Index/storage.
- Query CPU.
- Network egress.
- Backup/replication.

Không phải log nào cũng cần giữ lâu. Một policy thực tế có thể là:

- Debug log: tắt mặc định hoặc retention rất ngắn.
- App info/error log: 7-30 ngày tùy nhu cầu.
- Audit/security log: retention dài hơn theo yêu cầu compliance.
- PII/secrets: không được ghi ra log.

Log pipeline nên có filter/redaction trước backend nếu có nguy cơ lộ token, password, email hoặc dữ liệu nhạy cảm.

## Kubernetes logging layers

### Container log file

Kubelet và container runtime ghi log container vào filesystem của node. Collector dạng DaemonSet thường mount các path như:

```text
/var/log/containers
/var/log/pods
```

Sau đó collector parse symlink/file name để lấy namespace, pod và container.

### Kubelet log API

`kubectl logs` gọi Kubernetes API, rồi API server proxy tới kubelet để lấy log container. Vì vậy `kubectl logs` có thể fail nếu:

- Pod đã bị xóa.
- Container chưa từng start.
- Node/kubelet không reachable.
- Bạn không có quyền RBAC `pods/log`.
- Bạn đọc sai container trong Pod nhiều container.

### Node-level collector

Log collector thường chạy DaemonSet để mỗi node có một collector local. Pattern này giảm network hop và đảm bảo collector đọc được file log trên chính node đó.

Collector pipeline thường gồm:

```text
Input tail file
  -> parser CRI/containerd
  -> Kubernetes metadata enrichment
  -> multiline/filter/redaction
  -> output backend
```

## Deep dive: Collector pipeline trong node

Fluent Bit/Promtail/Vector thường chạy dưới dạng `DaemonSet` vì log file nằm trên node. Collector phải giải quyết bốn việc trước khi gửi log đi:

1. Tail đúng file runtime (`/var/log/containers/*.log`, `/var/log/pods/...`).
2. Parse CRI/containerd format để tách timestamp, stream và message.
3. Enrich Kubernetes metadata bằng API server, cần RBAC `get/list/watch pods,namespaces`.
4. Filter multiline/redaction trước khi output tới Loki/Elasticsearch/cloud logging.

Lab có thể output ra `stdout` của Fluent Bit để thấy collector đọc được log. Đây không phải log aggregation production vì dữ liệu vẫn chỉ nằm trong log của collector.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điều phù hợp | Caveat |
|---|---|---|
| K3s/k3d lab | Học `stdout`, `kubectl logs`, collector DaemonSet | Host log path có thể khác VM Linux thật |
| Kubernetes self-managed | Tự chọn Loki/EFK/Vector/Fluent Bit và vận hành backend | Team chịu retention, storage, RBAC, upgrade, cost |
| EKS/GKE/AKS | Có cloud logging tích hợp và node metadata | Vẫn cần app log format, labels, redaction, access control |
| Managed observability | Giảm backend operations | Cost/cardinality/PII vẫn là trách nhiệm thiết kế |

- K3s dùng containerd, log container vẫn đi theo Kubernetes logging pattern.
- K3s packaged Traefik, CoreDNS và local-path-provisioner cũng tạo log hữu ích khi debug networking/storage.
- Local cluster không chứng minh retention/cost của production backend.
- Với k3d, node là container Docker, nên một số hostPath log path có thể khác môi trường Linux VM thật.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Rủi ro chính |
|---|---|---|
| `kubectl logs` | Debug nhanh Pod hiện tại | Không có history/query/retention production |
| Fluent Bit -> stdout | Lab collector path | Không phải aggregation backend |
| Fluent Bit/Vector -> Loki | Chi phí index thấp, Grafana workflow | Label cardinality phải kiểm soát |
| Fluent Bit/Vector -> Elasticsearch/OpenSearch | Full-text search mạnh | Vận hành/storage/index cost cao |
| Cloud logging | Managed backend, tích hợp IAM | Cost, vendor coupling, quota/retention |

### Best Practices

- Nên log JSON một dòng cho app mới.
- Nên chuẩn hóa labels `app`, `team`, `environment`, `version`.
- Nên redact token/password/email trước backend nếu app chưa đảm bảo.
- Tránh high-cardinality labels như `request_id`, `user_id`, `trace_id`.
- Tránh ghi log vào file trong container nếu có thể ghi `stdout`/`stderr`.

## Performance Considerations

Logging pipeline ảnh hưởng production theo nhiều cách:

- Ingest volume cao làm collector và backend tốn CPU/network/disk.
- Multiline parser sai có thể gom quá nhiều dòng thành một event lớn.
- Backend down có thể tạo backpressure hoặc drop log tùy config.
- Elasticsearch/OpenSearch index nhiều field động làm tăng shard/storage cost.
- Loki label cardinality cao làm index phình nhanh.

Giới hạn log level, sampling, drop noisy logs, buffer size và retention theo môi trường.

## Debugging Checklist

```bash
kubectl logs <pod> -c <container> --tail=100
kubectl logs <pod> --previous
kubectl logs -l app=<app> --since=10m --tail=200
kubectl get daemonset,pod -l app=<collector> -A -o wide
kubectl logs daemonset/<collector> --tail=200
kubectl auth can-i list pods --as=system:serviceaccount:<ns>:<collector-sa> -n <app-ns>
kubectl get events --sort-by=.lastTimestamp
```

Nếu collector thiếu metadata, kiểm tra RBAC và kết nối API server trước khi sửa parser. Nếu stack trace bị tách dòng, kiểm tra app có thể log JSON một dòng không trước khi viết multiline parser phức tạp.

## Liên hệ với kiến thức đã biết

Với microservices, logging chỉ hữu ích khi đi cùng correlation ID/trace ID, version labels và query convention. Logs giúp đọc chi tiết một request lỗi; metrics báo lỗi đang tăng; traces cho biết request đi qua service nào. Ba lớp này phải dùng chung naming/labels.

## Tóm tắt

Logging trong Kubernetes bắt đầu từ một quyết định đơn giản: ứng dụng ghi log ra `stdout`/`stderr`. Nhưng production logging là cả một pipeline: collector trên node, metadata enrichment, parsing, filtering, backend storage, query, retention và quyền truy cập. Nếu logs không có cấu trúc và metadata tốt, bạn sẽ có nhiều dữ liệu nhưng ít khả năng điều tra.

## Câu hỏi tự kiểm tra

1. Vì sao `kubectl logs` không đủ cho incident production nhiều ngày?
2. Collector DaemonSet cần RBAC nào để enrich Kubernetes metadata?
3. Khi nào nên dùng multiline parser thay vì yêu cầu app log JSON một dòng?
4. Vì sao `request_id` không nên là Loki label?
5. Redaction nên đặt ở app, collector hay backend?

## Production checklist

- [ ] App ghi log ra `stdout`/`stderr`.
- [ ] Log format có timestamp, level, service name và message rõ.
- [ ] Có correlation ID hoặc trace ID trong log khi request đi qua nhiều service.
- [ ] Kubernetes labels chuẩn hóa theo app/team/environment/version.
- [ ] Log collector chạy DaemonSet trên mọi node cần thu log.
- [ ] Collector parse đúng CRI/containerd format.
- [ ] Multiline stack trace được xử lý hoặc app log JSON một dòng.
- [ ] Sensitive data được redact hoặc không ghi ra log.
- [ ] Backend có retention policy rõ.
- [ ] Query path được test trong incident drill.
- [ ] RBAC/log access phân quyền theo team hoặc namespace.
- [ ] Có dashboard/query mẫu cho lỗi 5xx, crash loop, deployment version và request ID.

## Anti-patterns

- Ghi log vào file trong container rồi không ship ra ngoài.
- Dùng `kubectl logs` như giải pháp production logging.
- Đặt `request_id` hoặc `user_id` làm Loki label.
- Bật debug log toàn hệ thống trong thời gian dài.
- Ghi secrets, token hoặc payload nhạy cảm ra log.
- Không đặt label `app`/`version` nên không query được theo rollout.
- Không kiểm tra log `--previous` khi Pod `CrashLoopBackOff`.
- Để log backend đầy disk rồi làm mất observability đúng lúc incident.

## Tài liệu tham khảo

- Kubernetes documentation: Logging Architecture.
- Fluent Bit documentation.
- Grafana Loki documentation: Labels.
- Elasticsearch/OpenSearch documentation: Index lifecycle and mappings.
