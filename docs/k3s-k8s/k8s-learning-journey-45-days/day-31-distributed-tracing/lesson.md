# Day 31: Distributed Tracing

## Mục tiêu bài học

- Hiểu distributed tracing giải quyết vấn đề gì trong microservices.
- Nắm các khái niệm trace, span, parent-child span, trace context, baggage và sampling.
- Hiểu OpenTelemetry Collector ở mức receiver, processor, exporter và pipeline.
- Biết vai trò của Jaeger và Tempo trong lưu trữ/query traces.
- Xác minh được context propagation thật khi service A gọi service B qua HTTP.
- Biết cách liên kết traces với logs và metrics bằng `trace_id`, service name và Kubernetes metadata.

## Vấn đề cần giải quyết

Trong hệ thống monolith, một request thường nằm trong một process. Khi lỗi xảy ra, bạn đọc log process đó.

Trong microservices trên Kubernetes, một request có thể đi qua:

- API Gateway.
- Auth service.
- Order service.
- Payment service.
- PostgreSQL.
- Redis.
- Kafka producer/consumer.
- External provider.

Nếu chỉ có logs rời rạc, bạn phải tự ghép request bằng timestamp, request ID và service name. Distributed tracing tạo một bản đồ request end-to-end:

- Request đi qua service nào?
- Service nào chậm?
- Lỗi bắt đầu ở đâu?
- Có retry hoặc fan-out không?
- Một Kafka message có nối được với request ban đầu không?

## Mental Model

```text
Incoming request
  |
  +-- trace_id = one end-to-end transaction
  |
  +-- span: api-gateway receives HTTP request
        |
        +-- span: order-service validates order
              |
              +-- span: PostgreSQL query
              |
              +-- span: payment-service call
                    |
                    +-- span: external provider call

Each service propagates trace context to the next hop.
```

Trace cho bạn timeline. Logs cho bạn chi tiết event. Metrics cho bạn xu hướng và alert. Ba lớp này bổ sung nhau.

## Lý thuyết cốt lõi

### Trace và span

Trace là toàn bộ hành trình của một request hoặc transaction.

Span là một đơn vị công việc trong trace:

- HTTP request vào service.
- Call từ service A sang service B.
- Database query.
- Kafka produce/consume.
- Cache lookup.
- Background job step.

Span thường có:

- `trace_id`
- `span_id`
- `parent_span_id`
- `service.name`
- `span.name`
- start time và duration
- status/error
- attributes như `http.method`, `http.route`, `db.system`, `messaging.system`

### Context propagation

Tracing chỉ hoạt động end-to-end nếu service propagate context sang downstream. Chuẩn phổ biến là W3C Trace Context:

```text
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
tracestate: vendor-specific-data
```

Khi service A gọi service B, A phải truyền header `traceparent`. Service B đọc header đó, tạo child span và tiếp tục truyền context.

Với messaging, context cần được đưa vào message headers. Nếu producer không inject hoặc consumer không extract, trace sẽ bị đứt tại queue.

Điểm cần kiểm chứng trong lab không chỉ là "trace có trong Jaeger", mà là cùng một `trace_id` xuất hiện ở service A log, service B log và trace backend. Nếu service B tạo trace mới, instrumentation có thể vẫn chạy nhưng propagation đã sai.

### Sampling

Không phải mọi request đều cần lưu trace trong production. Sampling giúp giảm chi phí:

- Head sampling: quyết định ở đầu request.
- Tail sampling: quyết định sau khi thấy kết quả, ví dụ giữ request lỗi hoặc latency cao.
- Probabilistic sampling: giữ một tỷ lệ cố định.
- Rules-based sampling: giữ theo route, status, tenant hoặc service.

Sampling sai có thể làm mất trace đúng lúc cần điều tra. Với service quan trọng, thường giữ 100% trace lỗi và sample trace thành công.

### OpenTelemetry

OpenTelemetry là chuẩn vendor-neutral cho telemetry:

- API/SDK để instrument app.
- Semantic conventions cho attribute names.
- Collector để nhận, xử lý và export telemetry.
- OTLP protocol cho logs, metrics, traces.

Trong app, bạn dùng SDK hoặc auto-instrumentation để tạo spans. Trong cluster, bạn dùng OpenTelemetry Collector để chuẩn hóa pipeline trước khi gửi tới backend.

### OpenTelemetry Collector

Collector gồm:

- Receivers: nhận telemetry, ví dụ OTLP, Zipkin, Jaeger.
- Processors: batch, memory limiter, attributes, resource detection, sampling.
- Exporters: gửi telemetry tới Jaeger, Tempo, Prometheus, logging/debug hoặc vendor backend.
- Pipelines: nối receivers, processors, exporters theo loại telemetry.

Mental model:

```text
receiver -> processor -> exporter
```

Ví dụ:

```text
OTLP receiver
  -> memory_limiter
  -> batch
  -> tail_sampling
  -> Tempo exporter
```

### Jaeger và Tempo

Jaeger:

- Trace backend và UI phổ biến.
- Hữu ích cho lab và nhiều production setup.
- Hỗ trợ query trace theo service, operation, tag, duration.

Tempo:

- Trace backend trong Grafana ecosystem.
- Thường tối ưu chi phí bằng object storage.
- Index ít hơn Jaeger/Elasticsearch-style trace stores.
- Tích hợp tốt với Grafana, Loki và Prometheus qua exemplars/trace IDs.

Chọn backend không thay đổi nguyên tắc instrumentation: trace context, semantic attributes, sampling và service naming vẫn quan trọng.

## Trace, logs, metrics correlation

Một incident workflow tốt:

```text
Alert fires from metrics
  |
  v
Open dashboard and identify service/version/route
  |
  v
Open traces for slow/error requests
  |
  v
Use trace_id to query logs
  |
  v
Find exact error and owning service
```

Để workflow này chạy được:

- Metrics có labels `service`, `route`, `status`.
- Traces có `service.name`, `http.route`, `status`.
- Logs có `trace_id` và `service`.
- Kubernetes labels có app/version/team.

## Deep dive: Cách hoạt động bên trong

### Propagation path trong Kubernetes

Kubernetes không tự tạo hoặc truyền `traceparent` cho application. Service, Ingress và kube-proxy chỉ route network packet. Trace context phải được SDK, middleware, service mesh hoặc gateway layer inject/extract ở protocol level:

```text
client
  -> Ingress/Gateway
  -> service-a HTTP server span
  -> service-a HTTP client span injects traceparent
  -> Service ClusterIP routes to service-b Pod
  -> service-b extracts traceparent and creates child server span
```

Vì vậy lỗi trace bị đứt hiếm khi nằm ở Service object. Nó thường nằm ở code path outbound call, middleware, proxy stripping header hoặc async messaging headers.

### Service name stability

`service.name` trong trace nên là tên service logic, không phải Pod name. Pod name thay đổi theo rollout, nhưng service name cần ổn định để query.

Tốt:

```text
service.name=order-service
```

Không tốt:

```text
service.name=order-service-7d8c9d6b4f-k2m9q
```

### Resource attributes

Collector hoặc SDK nên thêm resource attributes:

- `k8s.namespace.name`
- `k8s.pod.name`
- `k8s.container.name`
- `k8s.deployment.name`
- `service.version`
- `service.namespace`

Những attribute này giúp debug rollout và namespace-specific incident.

### Sidecar vs DaemonSet vs Gateway collector

Collector deployment patterns:

- Sidecar: gần app, isolation tốt, nhiều overhead.
- DaemonSet/agent: mỗi node một collector, phù hợp node-local collection.
- Gateway Deployment: tập trung xử lý, sampling, export ra backend.

Production thường dùng agent collector gần workload và gateway collector để xử lý tập trung.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | Trace context, OpenTelemetry SDK/Collector và backend hoạt động theo cùng nguyên tắc | Cần tự chọn Collector deployment pattern, storage backend, sampling và RBAC/NetworkPolicy |
| K3s local/lab | Phù hợp chạy Jaeger all-in-one và Collector nhỏ để học nhanh | Traefik mặc định không tự thêm tracing cho app; resource laptop nhỏ nên retention/sampling chỉ để lab |
| Self-managed production | Team kiểm soát Collector, backend, retention, sampling và network path | Phải vận hành Collector như workload production: requests/limits, queue, retry, HA |
| EKS/GKE/AKS | Workload instrumentation vẫn giống upstream Kubernetes | Cloud có thể cung cấp managed tracing/backend, nhưng service vẫn phải propagate context và chuẩn hóa `service.name` |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| SDK instrumentation | Kiểm soát span, attributes, error status tốt | Cần sửa code và maintain library |
| Auto-instrumentation | Bootstrap nhanh nhiều service | Có thể thiếu business spans hoặc tạo noise |
| Sidecar/agent Collector | Cô lập và giảm network hop | Nhiều Pod hơn, overhead cao hơn |
| Gateway Collector | Sampling/export tập trung | Collector outage ảnh hưởng nhiều service |
| Always-on sampling | Lab, low traffic, incident ngắn hạn | Chi phí backend cao |
| Tail sampling | Giữ error/slow traces tốt hơn | Cần buffer, memory và cấu hình Collector kỹ |

### Best Practices

- Nên chuẩn hóa `service.name`, `service.version` và `deployment.environment`.
- Nên log `trace_id`/`span_id` ở request boundary và error log.
- Nên kiểm tra propagation bằng service A -> B thật, không chỉ gửi span thủ công.
- Nên gửi app telemetry tới OpenTelemetry Collector bằng OTLP hoặc receiver tương thích, rồi mới export sang Jaeger/Tempo/vendor.
- Nên giữ 100% trace lỗi hoặc latency cao nếu chi phí cho phép.
- Tránh đưa PII, token, raw SQL có dữ liệu nhạy cảm vào span attributes.

## Performance Considerations

- Mỗi span tạo CPU/memory/network overhead trong app và Collector.
- Batch processor giảm số request export nhưng tăng delay nhỏ trước khi trace xuất hiện.
- Tail sampling cần memory để buffer trace trước khi quyết định giữ/bỏ.
- Instrumentation quá chi tiết làm trace khó đọc và tăng chi phí lưu trữ.
- Collector thiếu resource có thể drop span; cần monitor queue, retry, dropped spans và exporter errors.

## Debugging Checklist

Khi không thấy trace end-to-end:

```bash
kubectl logs deploy/<service-a> --tail=100
kubectl logs deploy/<service-b> --tail=100
kubectl logs deploy/<otel-collector> --tail=200
kubectl get svc,endpoints <collector-service>
```

Kiểm tra:

- Service A có nhận hoặc tạo `traceparent` không?
- Service A có inject header khi gọi service B không?
- Service B có extract cùng `trace_id` không?
- Collector receiver có đúng protocol/port không?
- Exporter tới Jaeger/Tempo có lỗi TLS, endpoint hoặc auth không?
- Sampling có drop trace không?

## Liên hệ với kiến thức đã biết

- Với API Gateway, tracing cho bạn thấy route ngoài cluster liên kết với service nội bộ nào.
- Với Kafka, context phải đi trong message headers, không nằm trong payload business nếu có thể.
- Với PostgreSQL/Redis, span giúp thấy dependency latency nhưng phải tránh ghi query/value nhạy cảm.
- Với logs/ELK/Loki, `trace_id` là khóa để nhảy từ một request lỗi sang log chi tiết.

## Production checklist

- [ ] Service quan trọng được instrument bằng OpenTelemetry hoặc library tương đương.
- [ ] `service.name` ổn định và thống nhất.
- [ ] Context propagation hoạt động qua HTTP/gRPC/messaging.
- [ ] Logs có `trace_id`.
- [ ] Collector có memory limiter và batch processor.
- [ ] Sampling strategy rõ, giữ trace lỗi/latency cao.
- [ ] Backend retention và cost được định nghĩa.
- [ ] Trace attributes không chứa PII/secrets.
- [ ] Dashboard từ metrics có link sang traces/logs.
- [ ] Runbook có bước kiểm tra trace đứt ở đâu.

## Anti-patterns

- Instrument service nhưng không propagate context.
- Đặt Pod name làm `service.name`.
- Trace mọi request với mọi attribute trong production mà không tính chi phí.
- Không lưu trace lỗi vì sampling quá thấp.
- Ghi `trace_id` trong trace backend nhưng không đưa vào logs.
- Dùng tracing thay cho metrics alerting.
- Tạo span cho mọi function nhỏ khiến trace nhiễu và tốn chi phí.

## Tóm tắt

Distributed tracing cho bạn timeline end-to-end của request trong microservices. Giá trị thật của tracing không nằm ở UI đẹp, mà ở context propagation đúng, service naming chuẩn, sampling hợp lý và khả năng nối metrics -> traces -> logs trong incident. OpenTelemetry giúp tránh lock-in và chuẩn hóa instrumentation/pipeline, còn Jaeger hoặc Tempo là backend để lưu và query trace.

## Câu hỏi tự kiểm tra

- Vì sao cùng `trace_id` ở service A và B quan trọng hơn việc chỉ thấy một span trong Jaeger?
- Khi nào nên dùng tail sampling thay vì head sampling?
- Vì sao không nên dùng Pod name làm `service.name`?
- Nếu logs có `trace_id` nhưng trace backend không có trace, bạn kiểm tra lớp nào trước?

## Tài liệu tham khảo

- Kubernetes Documentation: Services, Pods và labels.
- OpenTelemetry Documentation: Traces, context propagation, Collector pipeline.
- W3C Trace Context specification.
- Jaeger Documentation: Zipkin receiver, OTLP receiver và query UI.
- Grafana Tempo Documentation: Tempo architecture và trace/log/metric correlation.
