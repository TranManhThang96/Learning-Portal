# Day 42: OpenTelemetry & Distributed Tracing

**Phase 6: Observability & Reliability**
**Thời gian học:** ~2 giờ
**Cấp độ:** Senior Software Engineer

---

## 1. Mục tiêu bài học

Sau bài học này, bạn có thể:

1. **Giải thích** khái niệm Trace, Span, Context Propagation và tại sao chúng là nền tảng của observability trong hệ thống microservices.
2. **Thiết kế** pipeline instrumentation dùng OpenTelemetry SDK + Collector, với chiến lược sampling phù hợp cho từng quy mô hệ thống.
3. **So sánh** Jaeger vs Grafana Tempo để chọn backend phù hợp theo yêu cầu thực tế.
4. **Instrument** 2 services gọi nhau, xem end-to-end trace, và phân tích bottleneck từ trace data.
5. **Nhận biết** các anti-pattern phổ biến: missing context propagation, high-cardinality attributes, và sampling misconfiguration.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Ở **Day 39 (Prometheus)** và **Day 40 (Grafana)** bạn đã có metrics — bạn biết service X đang chậm (latency p99 = 3s). Ở **Day 41 (Loki/ELK)** bạn có logs — bạn thấy có error xảy ra. Nhưng câu hỏi quan trọng nhất vẫn chưa trả lời được:

> **"Request này đi qua những service nào, mất bao lâu ở mỗi bước, và bottleneck nằm ở đâu?"**

Đây chính xác là vấn đề mà **distributed tracing** giải quyết. Nó là **"cầu nối"** giữa metrics (what is happening) và logs (what happened) để trả lời (where and why it happened).

### Analogy dành cho Software Engineer

Bạn đã quen với **stack trace** khi debug monolith: một exception hiện toàn bộ call stack từ điểm lỗi lên đến entry point. Distributed tracing chính xác là khái niệm đó, nhưng áp dụng qua nhiều services, networks, và processes:

```
Stack trace (monolith):          Distributed trace (microservices):
─────────────────────            ─────────────────────────────────
main()                           API Gateway
  └─ UserService.getUser()         └─ UserService [HTTP call]
       └─ CacheService.get()            └─ CacheService [gRPC call]
            └─ DB.query()                    └─ PostgreSQL [DB query]
                 └─ ERROR ❌                      └─ ERROR ❌
```

Distributed trace = **stack trace vượt qua network boundaries**, với timestamp ở mỗi bước.

### Hậu quả nếu không có tracing

| Tình huống | Không có tracing | Có tracing |
|-----------|-----------------|-----------|
| Latency tăng đột ngột | Debug mù, xem từng service log | Xác định bottleneck trong < 5 phút |
| Cascade failure | Không biết service nào trigger đầu tiên | Thấy rõ chain of failure |
| Third-party API chậm | Đổ lỗi cho nhau giữa các team | Proof: external call chiếm 80% latency |
| Performance regression sau deploy | A/B compare metrics, tốn nhiều giờ | So sánh trace P95 trước/sau deploy |

---

## 3. Kiến thức nền tảng

### 3.1 Trace là gì?

Một **Trace** đại diện cho toàn bộ hành trình của một request qua hệ thống phân tán. Nó được định nghĩa bởi một `TraceID` duy nhất (128-bit, thường là UUID).

```
TraceID: 4bf92f3577b34da6a3ce929d0e0e4736

Trace timeline:
0ms    100ms   200ms   300ms   400ms   500ms
│       │       │       │       │       │
├───────────────────────────────────────┤  API Gateway (500ms)
        ├───────────────────────────────┤  OrderService (400ms)
                ├───────────────────────┤  InventoryService (300ms)
                        ├───────────────┤  DB Query (200ms) ← BOTTLENECK
```

### 3.2 Span là gì?

Một **Span** là đơn vị công việc nhỏ nhất trong một trace. Mỗi span có:

```
SpanID: a3ce929d0e0e4736
ParentSpanID: 4bf92f3577b34da6  (liên kết thành tree)

Span attributes:
  service.name = "order-service"
  http.method = "POST"
  http.url = "/api/orders"
  http.status_code = 200
  db.system = "postgresql"
  db.statement = "INSERT INTO orders ..."

Span events (structured logs gắn vào span):
  t=150ms: "Inventory check started"
  t=300ms: "Inventory reserved"

Span status: OK | ERROR | UNSET
```

**Span hierarchy** tạo thành cây (tree), không phải danh sách phẳng:

```
[Root Span] API Gateway: POST /orders
  ├─ [Child Span] Auth check (5ms)
  ├─ [Child Span] Order Service: createOrder (390ms)
  │     ├─ [Child Span] Inventory gRPC call (280ms)
  │     │     └─ [Child Span] DB SELECT (270ms) ← slow!
  │     └─ [Child Span] Payment HTTP call (100ms)
  └─ [Child Span] Notify Service (async, 10ms)
```

### 3.3 Context Propagation

Đây là cơ chế **truyền TraceID và SpanID** qua các network boundaries. Không có context propagation, các span sẽ "rời rạc" — bạn có nhiều traces độc lập thay vì một trace thống nhất.

**W3C TraceContext standard** (RFC định nghĩa HTTP headers):

```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
              ^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^ ^^
              |  TraceID (128-bit)                SpanID (64-bit)  Flags
              version
```

**Baggage** (truyền metadata tùy ý qua services):

```http
tracestate: vendor1=value1,vendor2=value2
baggage: userId=123,sessionId=abc,region=us-east-1
```

**Cách hoạt động trong code:**

```
Service A (OrderService):                Service B (InventoryService):
─────────────────────────                ──────────────────────────────
span = tracer.startSpan("createOrder")   // HTTP request tới đây với header:
ctx = context.withSpan(span)             // traceparent: 00-abc123...-xyz789...-01

// Khi gọi HTTP sang B:                  span = tracer.extract(request.headers)
// SDK tự inject header:                 // → span này trở thành child của A's span
request.headers["traceparent"] = ...    childSpan = tracer.startSpan("checkInventory",
                                                      parent=span)
```

### 3.4 Sampling

Không thể ghi lại 100% traces trong production — chi phí storage và processing quá cao. **Sampling** quyết định trace nào được giữ lại.

```
Head-based sampling:                    Tail-based sampling:
────────────────────                    ──────────────────────
Quyết định ngay tại điểm đầu           Quyết định sau khi trace hoàn thành

[Request A] → 10% chance → KEEP         [Trace A, 50ms, OK]  → DISCARD (fast, ok)
[Request B] → 10% chance → DISCARD      [Trace B, 500ms, OK] → KEEP (slow)
[Request C] → 10% chance → KEEP         [Trace C, 10ms, ERR] → KEEP (error)

Ưu điểm: Đơn giản, overhead thấp       Ưu điểm: Giữ traces quan trọng
Nhược điểm: Có thể drop lỗi hiếm       Nhược điểm: Phức tạp, cần buffer
```

---

## 4. Deep Dive

### 4.1 OpenTelemetry Architecture

OpenTelemetry (OTel) là CNCF project cung cấp **vendor-neutral** instrumentation standard. Nó thay thế OpenCensus và OpenTracing.

```
┌──────────────────────────────────────────────────────────────────┐
│                    YOUR APPLICATION                               │
│                                                                   │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐ │
│  │ OTel SDK        │    │ Auto-Instrumentation Agents           │ │
│  │ ─────────────   │    │ (Java agent, Node.js require hook,   │ │
│  │ Tracer          │    │  Go contrib packages)                 │ │
│  │ Meter           │    │                                       │ │
│  │ Logger          │    │ Tự động instrument: HTTP, DB, gRPC,   │ │
│  │                 │    │ Redis, messaging frameworks...        │ │
│  └────────┬────────┘    └──────────────────┬───────────────────┘ │
│           │                                │                      │
│           └──────────────┬─────────────────┘                      │
│                          │ OTLP (gRPC/HTTP)                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                 OPENTELEMETRY COLLECTOR                            │
│                                                                   │
│  ┌──────────────┐  ┌─────────────────┐  ┌──────────────────────┐ │
│  │  RECEIVERS   │  │   PROCESSORS    │  │     EXPORTERS        │ │
│  │ ──────────── │  │ ─────────────── │  │ ──────────────────── │ │
│  │ otlp         │→ │ batch           │→ │ jaeger               │ │
│  │ jaeger       │  │ memory_limiter  │  │ prometheus           │ │
│  │ prometheus   │  │ resourcedetect  │  │ loki                 │ │
│  │ zipkin       │  │ filter          │  │ otlp (to other srv)  │ │
│  │ hostmetrics  │  │ transform       │  │ debug                │ │
│  └──────────────┘  └─────────────────┘  └──────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                           │                        │
                    ┌──────▼──────┐         ┌──────▼──────┐
                    │   JAEGER    │         │    TEMPO     │
                    │  (UI+Store) │         │  (storage)  │
                    └─────────────┘         └─────────────┘
```

### 4.2 Collector Pipeline Chi Tiết

**Receiver**: Nhận data từ nhiều nguồn và protocol khác nhau.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  
  # Thu thập metrics từ host
  hostmetrics:
    collection_interval: 10s
    scrapers:
      cpu: {}
      memory: {}
      disk: {}
```

**Processors**: Transform, filter, batch data trước khi export.

```yaml
processors:
  # Giới hạn memory để tránh OOM
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
    spike_limit_mib: 128

  # Batch để giảm số lần gửi network
  batch:
    timeout: 10s
    send_batch_size: 1024
    send_batch_max_size: 2048

  # Thêm resource attributes tự động
  resourcedetection:
    detectors: [env, docker, system]
    timeout: 5s

  # Lọc spans không cần thiết
  filter/health:
    traces:
      span:
        - 'attributes["http.target"] == "/health"'
        - 'attributes["http.target"] == "/metrics"'
```

**Exporter**: Gửi data đến backend.

```yaml
exporters:
  # Gửi traces đến Jaeger
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  # Gửi traces đến Tempo
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

  # Gửi metrics đến Prometheus (expose endpoint)
  prometheus:
    endpoint: "0.0.0.0:8889"
    
  # Debug (log ra stdout, chỉ dùng cho dev)
  debug:
    verbosity: detailed
```

### 4.3 Jaeger vs Grafana Tempo

```
┌─────────────────────┬────────────────────────┬──────────────────────────┐
│ Tiêu chí            │ Jaeger                 │ Grafana Tempo            │
├─────────────────────┼────────────────────────┼──────────────────────────┤
│ Nguồn gốc           │ Uber, CNCF graduated   │ Grafana Labs             │
│ Storage backend     │ Cassandra/Elasticsearch│ Object storage (S3/GCS)  │
│                     │ /Badger (local)        │ /Azure Blob + local disk │
├─────────────────────┼────────────────────────┼──────────────────────────┤
│ Query language      │ UI-based search        │ TraceQL (powerful)       │
│ TraceID lookup      │ Fast                   │ Fast                     │
│ Tag-based search    │ Yes (indexed)          │ TraceQL + tag search      │
├─────────────────────┼────────────────────────┼──────────────────────────┤
│ Scalability         │ Medium-Large           │ Massive scale            │
│ Storage cost        │ DB = đắt hơn           │ Object storage = rẻ hơn  │
│ Operational cost    │ Cần quản lý Cassandra  │ Chỉ cần object storage   │
├─────────────────────┼────────────────────────┼──────────────────────────┤
│ Tích hợp Grafana    │ Plugin (datasource)    │ Native (cùng ecosystem)  │
│ Tích hợp Loki/Prom  │ Thủ công               │ Tự động correlate        │
│ UI standalone       │ Đầy đủ, trực quan      │ Dùng Grafana UI          │
├─────────────────────┼────────────────────────┼──────────────────────────┤
│ Khi nào chọn        │ Team mới bắt đầu,      │ Scale lớn, đã dùng       │
│                     │ muốn UI độc lập,       │ Grafana stack, muốn      │
│                     │ không có S3            │ tích hợp metrics+logs    │
└─────────────────────┴────────────────────────┴──────────────────────────┘
```

**Grafana Tempo + TraceQL example:**

```
# Tìm tất cả traces có error và duration > 1s
{ status = error && duration > 1s }

# Tìm traces từ service cụ thể, có span chậm
{ resource.service.name = "order-service" } | by(span.http.route) | rate() > 10

# Tìm traces liên quan đến specific user
{ span.userId = "user-123" }
```

### 4.4 Sampling Strategies Chi Tiết

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAMPLING STRATEGIES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. AlwaysOn (100% sampling)                                    │
│     Use case: Development, low-traffic systems                   │
│     Cost: Rất cao ở production                                  │
│                                                                  │
│  2. AlwaysOff (0% sampling)                                     │
│     Use case: Tắt hoàn toàn (disaster mode)                    │
│                                                                  │
│  3. TraceIdRatioBased (Probabilistic - Head-based)              │
│     Ví dụ: 10% → mỗi request có 10% cơ hội được giữ lại       │
│     Ưu: Đơn giản, overhead thấp                                 │
│     Nhược: Có thể drop 90% lỗi hiếm gặp                       │
│                                                                  │
│  4. ParentBased                                                  │
│     Nếu parent sampled → child cũng sampled                     │
│     Đảm bảo trace được giữ hoàn chỉnh hoặc drop hoàn chỉnh    │
│                                                                  │
│  5. Tail-based Sampling (Collector-side)                        │
│     Collector buffer traces, quyết định sau khi hoàn thành     │
│     Rules: Keep nếu error, duration > 500ms, hoặc user VIP     │
│     Ưu: Giữ traces quan trọng                                   │
│     Nhược: Cần memory buffer lớn, phức tạp hơn                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Tail-based sampling config trong Collector:**

```yaml
processors:
  tail_sampling:
    decision_wait: 10s          # Chờ 10s trước khi quyết định
    num_traces: 50000           # Buffer tối đa 50k traces
    expected_new_traces_per_sec: 100
    policies:
      # Giữ tất cả traces có error
      - name: error-policy
        type: status_code
        status_code: {status_codes: [ERROR]}
      
      # Giữ traces chậm (> 500ms)
      - name: slow-traces
        type: latency
        latency: {threshold_ms: 500}
      
      # Giữ 10% traces bình thường
      - name: probabilistic-policy
        type: probabilistic
        probabilistic: {sampling_percentage: 10}
```

### 4.5 Trace Correlation với Logs và Metrics

Đây là điểm cốt lõi của **"Three Pillars of Observability"** (giới thiệu từ Day 38):

```
Grafana Dashboard:
┌─────────────────────────────────────────────────────────────────┐
│ Metrics Panel (Prometheus)   │ Thấy latency tăng lúc 14:30     │
│ ─────────────────────────────┤                                  │
│ [Graph: HTTP p99 latency]    │ Click → Exemplar (trace link)    │
│                         ↑   │                                  │
│                    spike!   │                                  │
└─────────────────────────────────────────────────────────────────┘
                              │ (click exemplar)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Trace View (Jaeger/Tempo)                                        │
│ TraceID: 4bf92f3577b34da6                                       │
│ ─────────────────────────────────────────────────────────────── │
│ [Waterfall diagram showing slow DB call]                        │
│                         │                                       │
│                    span_id: a3ce929d                            │
└─────────────────────────────────────────────────────────────────┘
                              │ (click "View Logs")
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Log View (Loki)                                                  │
│ Filter: {traceID="4bf92f3577b34da6"}                           │
│ ─────────────────────────────────────────────────────────────── │
│ 14:30:01 [ERROR] Connection pool exhausted, waiting 2s...      │
│ 14:30:03 [WARN]  DB query slow: 2100ms, query=SELECT...        │
└─────────────────────────────────────────────────────────────────┘
```

**Inject TraceID vào logs (structured logging):**

```go
// Go: Lấy TraceID từ context và inject vào log
func logWithTrace(ctx context.Context, msg string) {
    span := trace.SpanFromContext(ctx)
    spanCtx := span.SpanContext()
    
    slog.InfoContext(ctx, msg,
        "traceID", spanCtx.TraceID().String(),
        "spanID",  spanCtx.SpanID().String(),
    )
}
```

**Exemplars trong Prometheus** (metrics → traces link):

```go
// Ghi histogram với trace exemplar
histogram.With(prometheus.Labels{
    "method": "POST",
    "route":  "/api/orders",
}).Observe(duration.Seconds(),
    // Exemplar: link tới trace
    prometheus.Labels{
        "traceID": spanCtx.TraceID().String(),
    },
)
```

---

## 5. Trade-offs & Best Practices

### 5.1 Auto-instrumentation vs Manual Instrumentation

```
                    AUTO-INSTRUMENTATION
                    ─────────────────────
Ưu điểm:
  ✓ Không cần sửa code (agent inject vào runtime)
  ✓ Nhanh chóng instrument toàn bộ framework
  ✓ Ít bug do instrumentation sai
  ✓ Tốt cho brownfield projects (codebase cũ)

Nhược điểm:
  ✗ Không có business context (không biết userId, orderId...)
  ✗ Có thể tạo quá nhiều spans không cần thiết
  ✗ Khó customize span names/attributes
  ✗ Có thể xung đột với một số frameworks

                    MANUAL INSTRUMENTATION
                    ──────────────────────
Ưu điểm:
  ✓ Full control: span names, attributes, events
  ✓ Thêm business context (userId, orderId, SKU...)
  ✓ Chỉ trace những gì thực sự cần thiết
  ✓ Tốt hơn cho phân tích business logic

Nhược điểm:
  ✗ Cần viết code thêm
  ✗ Dễ quên instrument một số path
  ✗ Cần maintain khi refactor

BEST PRACTICE: Kết hợp cả hai
  Auto-instrument: HTTP, DB, gRPC, messaging
  Manual instrument: Business logic, custom attributes
```

### 5.2 Sampling Decision Framework

```
Traffic/day      | Recommendation
─────────────────┼──────────────────────────────────────────────
< 100K requests  | AlwaysOn — ghi lại 100%, không cần sampling
100K - 10M req   | Head-based 10-50% + AlwaysOn cho errors
10M - 100M req   | Tail-based: giữ errors + slow traces + 1-10%
> 100M req       | Tail-based với adaptive sampling,
                 | Head-based theo endpoint (tắt health checks)
```

### 5.3 Best Practices theo Scenario

**Startup (< 5 services, single team):**
- Dùng Jaeger với memory storage (dev) hoặc Badger (staging)
- Auto-instrumentation 100%
- Không cần sampling (traffic thấp)
- Tổng thời gian setup: < 1 ngày

**Mid-size (5-50 services, multiple teams):**
- Jaeger + Elasticsearch hoặc Tempo + S3
- Collector với batch processor + tail-based sampling
- Standard span naming convention
- Tổng thời gian setup: 1-2 tuần

**Enterprise / High-traffic (> 50 services):**
- Tempo + S3/GCS (cost-effective storage)
- Collector cluster với load balancing
- Adaptive tail-based sampling theo SLO
- Tổng thời gian setup: 1-3 tháng (governance + rollout)

### 5.4 Anti-patterns Cần Tránh

**Anti-pattern 1: High Cardinality Attributes**

```go
// WRONG: URL có user ID → cardinality vô hạn
span.SetAttributes(attribute.String("http.url", "/users/123456/orders"))

// RIGHT: Dùng route template
span.SetAttributes(
    attribute.String("http.route", "/users/{userId}/orders"),
    attribute.String("user.id", userID),  // Attribute riêng, có thể filter
)
```

**Anti-pattern 2: Span cho mọi thứ**

```go
// WRONG: Span overhead cho function nhanh (< 1ms)
for _, item := range items {
    span, ctx := tracer.Start(ctx, "process-item")
    processItem(item)
    span.End()  // 10,000 spans cho 10,000 items = chậm hơn!
}

// RIGHT: Một span cho toàn bộ batch
span, ctx := tracer.Start(ctx, "process-items-batch",
    trace.WithAttributes(attribute.Int("batch.size", len(items))))
for _, item := range items {
    processItem(item)
}
span.End()
```

**Anti-pattern 3: Baggage không kiểm soát**

```go
// WRONG: Truyền sensitive data qua Baggage (có thể bị log, leak)
baggage.NewMember("user.credit_card", "4242-4242-4242-4242")

// RIGHT: Chỉ dùng Baggage cho non-sensitive routing metadata
baggage.NewMember("tenant.id", "tenant-123")
baggage.NewMember("feature.flag", "new-checkout-v2")
```

---

## 6. Performance & Scalability

### 6.1 Overhead của Instrumentation

```
Thành phần               | Overhead điển hình
─────────────────────────┼──────────────────────────────
SDK (in-process)         | 0.1-0.5ms per request (object allocation)
Context propagation      | ~0 (chỉ là header read/write)
Exporting (async)        | 0 (background goroutine/thread)
Batch processor          | 0 (buffering, không block request)
Sampling computation     | < 0.1ms (hash computation)

TỔNG OVERHEAD ĐIỂN HÌNH: < 1ms per request (< 0.1% với 100ms request)
```

**Khi nào tracing CÓ THỂ ảnh hưởng performance:**

```
1. AlwaysOn ở traffic cao (> 10K RPS):
   → Tốn storage, Collector CPU tăng, network I/O tăng
   → FIX: Giảm sampling rate

2. Quá nhiều spans per request (> 100 spans):
   → Object allocation pressure, GC pressure (Go/JVM)
   → FIX: Loại bỏ spans không cần thiết

3. Synchronous export (không dùng batch):
   → Block thread khi gửi dữ liệu
   → FIX: Luôn dùng BatchSpanProcessor

4. Collector bị overwhelmed:
   → Backpressure, spans bị drop
   → FIX: Scale Collector horizontally, tăng batch size
```

### 6.2 Collector Bottlenecks

```
Collector capacity điển hình (1 node, 4 CPU, 4GB RAM):
  ─────────────────────────────────────────────────────
  Throughput: ~10,000 spans/second
  Memory: ~500MB cho buffer 50K traces (tail-based)

  Scale up: Nhiều Collector nodes + Load Balancer
  Pattern: Sticky routing theo TraceID (cho tail-based)
  
  Sticky routing (QUAN TRỌNG cho tail-based):
  Tất cả spans của cùng TraceID phải về cùng 1 Collector
  → Dùng load_balancing exporter:
  
exporters:
  loadbalancing:
    protocol:
      otlp:
        tls:
          insecure: true
    resolver:
      static:
        hostnames:
          - collector-1:4317
          - collector-2:4317
          - collector-3:4317
    routing_key: traceID  # Hash theo TraceID
```

### 6.3 Storage Scaling

```
Ước tính storage:
  Span size trung bình: ~500 bytes (sau nén)
  100K spans/day → 50MB/day → 18GB/year
  10M spans/day  → 5GB/day  → 1.8TB/year

Retention policy:
  Development: 1-3 ngày
  Staging:     7 ngày
  Production:  7-30 ngày (tuỳ compliance)

Tempo storage (S3):
  30 ngày, 10M spans/day = 150GB = ~$3/month (S3 Standard)
  Jaeger + Elasticsearch:
  30 ngày, 10M spans/day = ~200GB = máy chủ ES 3-node
```

---

## 7. Security & Reliability Considerations

### 7.1 Sensitive Data trong Spans

```
NGUY CỞ: Spans có thể chứa data nhạy cảm nếu không cẩn thận
─────────────────────────────────────────────────────────────
Thường bị lộ:
  - SQL queries đầy đủ (chứa WHERE user_id='...' với data thật)
  - HTTP request/response body
  - Authorization headers
  - PII trong URL parameters

CÁC BIỆN PHÁP BẢO VỆ:
```

```yaml
# Collector: Filter/Redact sensitive attributes
processors:
  transform:
    trace_statements:
      - context: span
        statements:
          # Xoá auth header
          - delete_key(attributes, "http.request.header.authorization")
          # Redact SQL query (giữ query structure, xoá values)
          - replace_pattern(attributes, "db.statement",
              "\\b\\d+\\b", "?")
          # Giới hạn độ dài value
          - truncate_all(attributes, 256)
```

### 7.2 Collector Security

```yaml
# TLS cho OTLP endpoint (production)
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        tls:
          cert_file: /certs/collector.crt
          key_file: /certs/collector.key
          client_ca_file: /certs/ca.crt  # mTLS

# Authentication (Collector 0.75+)
extensions:
  basicauth/server:
    htpasswd:
      inline: |
        myapp:$2y$12$...hashed_password...

# Network policy: Chỉ cho phép app pods gửi đến Collector
# Collector không expose ra ngoài cluster
```

### 7.3 Failure Isolation

```
Nếu Collector down → Application PHẢI TIẾP TỤC HOẠT ĐỘNG

SDK behavior khi Collector không available:
  ┌─────────────────────────────────────────────────────────┐
  │ Export thất bại → retry với exponential backoff         │
  │ Buffer đầy → Drop spans mới nhất (configurable)        │
  │ Application: zero impact (export là async)              │
  └─────────────────────────────────────────────────────────┘

Config SDK để fail-safe:
  - Max queue size: 2048 spans
  - Export timeout: 30s
  - Max export batch size: 512
  - Export interval: 5s
```

---

## 8. Hands-on Example

### 8.1 Kiến trúc Demo

Chúng ta sẽ xây dựng 2 services Go gọi nhau:

```
User → [HTTP] → order-service:8080
                    └── [HTTP] → inventory-service:8081
                                      └── [Simulated DB]

Cả 2 services gửi traces → OTel Collector → Jaeger
```

### 8.2 Cài đặt

**Bước 1: Tạo project structure**

```bash
mkdir -p otel-demo/{order-service,inventory-service,collector}
cd otel-demo
```

**Bước 2: `order-service/main.go`**

```go
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "time"

    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
    "go.opentelemetry.io/otel/trace"
)

var tracer trace.Tracer

func initTracer(ctx context.Context) func() {
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        log.Fatalf("failed to create exporter: %v", err)
    }

    res, _ := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName("order-service"),
            semconv.ServiceVersion("1.0.0"),
            attribute.String("environment", "demo"),
        ),
    )

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(res),
        // Sampling: AlwaysOn cho demo
        sdktrace.WithSampler(sdktrace.AlwaysSample()),
    )

    otel.SetTracerProvider(tp)
    tracer = tp.Tracer("order-service")

    return func() {
        tp.Shutdown(context.Background())
    }
}

func createOrderHandler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()

    // Bắt đầu span cho business logic
    ctx, span := tracer.Start(ctx, "createOrder",
        trace.WithAttributes(
            attribute.String("order.customer_id", r.URL.Query().Get("customerId")),
        ),
    )
    defer span.End()

    // Simulate: Validate order
    ctx, validateSpan := tracer.Start(ctx, "validateOrder")
    time.Sleep(10 * time.Millisecond)
    validateSpan.End()

    // Gọi inventory-service (HTTP client được wrap bởi otelhttp)
    inventoryClient := &http.Client{
        Transport: otelhttp.NewTransport(http.DefaultTransport),
    }

    req, _ := http.NewRequestWithContext(ctx, "GET",
        "http://inventory-service:8081/api/check?sku=ITEM-001", nil)

    resp, err := inventoryClient.Do(req)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "inventory check failed")
        http.Error(w, "inventory service unavailable", 503)
        return
    }
    defer resp.Body.Close()

    // Thêm event vào span
    span.AddEvent("inventory_checked",
        trace.WithAttributes(attribute.Int("http.status", resp.StatusCode)))

    // Simulate: Save to DB
    ctx, dbSpan := tracer.Start(ctx, "saveOrder",
        trace.WithAttributes(
            attribute.String("db.system", "postgresql"),
            attribute.String("db.operation", "INSERT"),
            attribute.String("db.table", "orders"),
        ),
    )
    time.Sleep(20 * time.Millisecond) // Simulate DB call
    dbSpan.End()

    span.SetAttributes(attribute.String("order.id", "ORD-12345"))

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{
        "orderId": "ORD-12345",
        "status":  "created",
    })
}

func main() {
    ctx := context.Background()
    shutdown := initTracer(ctx)
    defer shutdown()

    // Wrap router với otelhttp để tự động instrument HTTP
    mux := http.NewServeMux()
    mux.Handle("/api/orders", otelhttp.NewHandler(
        http.HandlerFunc(createOrderHandler),
        "POST /api/orders",
    ))
    mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(200)
    })

    fmt.Println("order-service listening on :8080")
    log.Fatal(http.ListenAndServe(":8080", mux))
}
```

**Bước 3: `inventory-service/main.go`**

```go
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "math/rand"
    "net/http"
    "time"

    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
    "go.opentelemetry.io/otel/trace"
)

var tracer trace.Tracer

func initTracer(ctx context.Context) func() {
    exporter, _ := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )

    res, _ := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName("inventory-service"),
            semconv.ServiceVersion("1.0.0"),
        ),
    )

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.AlwaysSample()),
    )

    otel.SetTracerProvider(tp)
    tracer = tp.Tracer("inventory-service")

    return func() { tp.Shutdown(context.Background()) }
}

func checkInventoryHandler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    sku := r.URL.Query().Get("sku")

    _, span := tracer.Start(ctx, "checkInventory",
        trace.WithAttributes(attribute.String("inventory.sku", sku)),
    )
    defer span.End()

    // Simulate DB lookup với random latency (để demo bottleneck)
    latency := time.Duration(50+rand.Intn(200)) * time.Millisecond
    ctx, dbSpan := tracer.Start(ctx, "db.query.inventory",
        trace.WithAttributes(
            attribute.String("db.system", "postgresql"),
            attribute.String("db.statement", "SELECT quantity FROM inventory WHERE sku = ?"),
            attribute.String("db.table", "inventory"),
        ),
    )
    // Simulate occasional slow query
    if rand.Float32() < 0.3 { // 30% chance of slow query
        latency = time.Duration(500+rand.Intn(1500)) * time.Millisecond
        dbSpan.SetAttributes(attribute.Bool("db.slow_query", true))
    }
    time.Sleep(latency)
    dbSpan.SetAttributes(attribute.Int("db.rows_affected", 1))
    dbSpan.End()

    quantity := 100 - rand.Intn(50)
    span.SetAttributes(attribute.Int("inventory.quantity", quantity))

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]interface{}{
        "sku":      sku,
        "quantity": quantity,
        "available": quantity > 0,
    })
}

func main() {
    ctx := context.Background()
    shutdown := initTracer(ctx)
    defer shutdown()

    mux := http.NewServeMux()
    mux.Handle("/api/check", otelhttp.NewHandler(
        http.HandlerFunc(checkInventoryHandler),
        "GET /api/check",
    ))
    mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(200)
    })

    fmt.Println("inventory-service listening on :8081")
    log.Fatal(http.ListenAndServe(":8081", mux))
}
```

**Bước 4: `go.mod` cho mỗi service**

```bash
# Trong order-service/:
go mod init order-service
go get go.opentelemetry.io/otel@v1.21.0
go get go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc@v1.21.0
go get go.opentelemetry.io/otel/sdk@v1.21.0
go get go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.46.1

# Trong inventory-service/:
go mod init inventory-service
# (same dependencies)
```

**Bước 5: `collector/otel-collector-config.yaml`**

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 100
  
  memory_limiter:
    check_interval: 1s
    limit_mib: 256

  # Drop health check spans
  filter/healthcheck:
    traces:
      span:
        - 'attributes["http.target"] == "/health"'

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  
  debug:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, filter/healthcheck, batch]
      exporters: [otlp/jaeger, debug]
```

**Bước 6: `docker-compose.yaml`**

```yaml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:1.52
    ports:
      - "16686:16686"   # Jaeger UI
      - "4317:4317"     # OTLP gRPC (internal)
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - otel-demo

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.90.0
    volumes:
      - ./collector/otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4318:4318"   # OTLP HTTP
      - "8889:8889"   # Prometheus metrics
    depends_on:
      - jaeger
    networks:
      - otel-demo

  order-service:
    build: ./order-service
    ports:
      - "8080:8080"
    depends_on:
      - otel-collector
      - inventory-service
    networks:
      - otel-demo

  inventory-service:
    build: ./inventory-service
    ports:
      - "8081:8081"
    depends_on:
      - otel-collector
    networks:
      - otel-demo

networks:
  otel-demo:
    driver: bridge
```

**Bước 7: `Dockerfile` cho cả 2 services**

```dockerfile
# Dockerfile (dùng cho cả order-service và inventory-service)
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o service .

FROM alpine:3.18
WORKDIR /app
COPY --from=builder /app/service .
EXPOSE 8080
CMD ["./service"]
```

### 8.3 Chạy và Verify

```bash
# Build và khởi động
docker-compose up --build -d

# Kiểm tra tất cả services up
docker-compose ps

# Gửi một số requests (để tạo traces)
for i in {1..20}; do
  curl -s "http://localhost:8080/api/orders?customerId=user-$i" | jq .
  sleep 0.5
done

# Mở Jaeger UI
open http://localhost:16686
```

### 8.4 Phân tích Trace trong Jaeger UI

**Xem trace list:**
1. Chọn Service = `order-service`
2. Operation = `POST /api/orders`
3. Click "Find Traces"

**Tìm bottleneck:**
```
Trong Jaeger UI, nhìn vào trace waterfall:

order-service: POST /api/orders          [===================] 650ms
  order-service: createOrder             [================]   600ms
    order-service: validateOrder         [=]                   10ms
    inventory-service: GET /api/check    [===========]        480ms  ← SLOW!
      inventory-service: checkInventory  [==========]         470ms
        inventory-service: db.query...   [=========]          460ms  ← BOTTLENECK
    order-service: saveOrder             [=]                   20ms

Kết luận: DB query trong inventory-service chiếm 70% total latency
Root cause: Slow query (missing index? connection pool exhausted?)
```

**Xem span details:**
- Click vào span `db.query.inventory`
- Xem attributes: `db.slow_query = true`, `db.statement = ...`
- Xem events: timestamp của từng bước

### 8.5 Cleanup

```bash
# Dừng và xoá containers
docker-compose down -v

# Xoá images (optional)
docker-compose down --rmi local

# Xoá toàn bộ
rm -rf otel-demo/
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Missing Context Propagation

**Triệu chứng:** Jaeger hiển thị nhiều traces riêng lẻ thay vì một trace thống nhất.

```
WRONG: Tạo HTTP request mà không truyền context
──────────────────────────────────────────────
ctx, span := tracer.Start(ctx, "callInventory")
// THIẾU ctx trong request → không có traceparent header
req, _ := http.NewRequest("GET", inventoryURL, nil)
resp, _ := http.DefaultClient.Do(req)

Kết quả:
Trace 1: order-service [một trace riêng]
Trace 2: inventory-service [một trace riêng, không liên quan!]

RIGHT: Luôn dùng NewRequestWithContext
───────────────────────────────────────
ctx, span := tracer.Start(ctx, "callInventory")
req, _ := http.NewRequestWithContext(ctx, "GET", inventoryURL, nil)
// otelhttp.NewTransport() tự inject traceparent header
resp, _ := instrumentedClient.Do(req)

Kết quả:
Trace 1: order-service → inventory-service [một trace thống nhất!]
```

### 9.2 Traces Không Hiển Thị Trong Jaeger

**Debug checklist:**

```bash
# 1. Kiểm tra Collector nhận được data
docker logs otel-collector | grep -i "span\|trace\|error"

# 2. Kiểm tra kết nối từ app đến Collector
docker exec order-service nc -zv otel-collector 4317
# Expected: Connection succeeded

# 3. Kiểm tra Collector config
docker exec otel-collector cat /etc/otelcol-contrib/config.yaml

# 4. Bật debug exporter trong Collector
# Sửa config để thêm:
# exporters:
#   debug:
#     verbosity: detailed
# service:
#   pipelines:
#     traces:
#       exporters: [otlp/jaeger, debug]  # Thêm debug

# 5. Kiểm tra Jaeger nhận được
curl http://localhost:16686/api/services
# Phải thấy: {"data":["order-service","inventory-service"],...}
```

### 9.3 Case Study: Cascade Failure Debug

**Kịch bản:** Lúc 02:30 sáng, alert bắn: order-service error rate 80%. On-call engineer nhận alert, cần debug.

```
Bước 1: Mở Grafana → Error rate spike lúc 02:28
         → Click exemplar trace link

Bước 2: Mở trace trong Jaeger
         TraceID: 7d5f...
         order-service [ERROR, 5.2s]
           └── inventory-service [ERROR, 5.1s]
                 └── db.query.inventory [ERROR, 5.0s]
                       Error message: "context deadline exceeded"

Bước 3: Mở logs với filter traceID=7d5f...
         02:28:14 [ERROR] inventory DB: connection pool exhausted
         02:28:14 [WARN]  Waiting for connection, pool_size=10, waited=4.9s

Bước 4: Root cause xác định trong 5 phút
         → DB connection pool đầy
         → Nguyên nhân: Deployment 02:25 tạo 5x pod replicas
           nhưng quên tăng pool size
         → Fix: Rollback deployment, tăng pool size từ 10 lên 50

Không có tracing: Debug có thể mất vài giờ
```

### 9.4 Sampling Dropping Important Traces

**Vấn đề:** Head-based sampling 10% đang drop 90% error traces.

```bash
# Kiểm tra sampling decision
# Trong Jaeger, nếu không thấy error traces:

# 1. Tạm thời tăng sampling lên 100% để debug
# Sửa SDK config:
sdktrace.WithSampler(sdktrace.AlwaysSample())

# 2. Long-term fix: Dùng tail-based sampling
# Collector config: giữ tất cả error traces
processors:
  tail_sampling:
    policies:
      - name: keep-errors
        type: status_code
        status_code: {status_codes: [ERROR]}
```

---

## 10. Kết nối với bài trước & bài sau

### Nhìn lại hành trình Three Pillars

Từ **Day 38** (Production Readiness), bạn đã học về "Three Pillars of Observability". Sau 4 ngày, bạn đã xây dựng đủ cả ba:

```
Day 39-40:  METRICS  →  "What is happening?"
            (Prometheus + Grafana)
            
Day 41:     LOGS     →  "What happened? What was the error?"
            (Loki/ELK/Splunk)
            
Day 42:     TRACES   →  "Where did it happen? Which path was slow?"
            (OpenTelemetry + Jaeger/Tempo)
            
Kết hợp 3 pillars:  → Complete observability
```

### Kết nối Bài Hôm Nay

**Day 41 - Logging Architecture:** Logs chỉ hữu ích khi bạn có traceID để filter. `{traceID="abc123"}` trong Loki cho phép jump từ trace sang logs ngay lập tức. Instrumentation hôm nay đã inject traceID vào log context.

**Day 43 - SLI/SLO & Error Budget:** SLO định nghĩa "99.9% requests < 500ms". Tracing data cho bạn *chứng minh* SLO đang bị vi phạm ở service nào, span nào — không chỉ biết tổng thể system chậm. Khi error budget của một service chuẩn bị hết, trace data giúp engineering team ưu tiên fix đúng chỗ.

---

## 11. Tài liệu tham khảo

- **OpenTelemetry Official Docs:** https://opentelemetry.io/docs/ — Nguồn chính thức, có Getting Started cho mọi ngôn ngữ
- **OpenTelemetry Go SDK:** https://pkg.go.dev/go.opentelemetry.io/otel — API reference
- **Jaeger Documentation:** https://www.jaegertracing.io/docs/latest/ — Architecture, deployment, troubleshooting
- **Grafana Tempo Documentation:** https://grafana.com/docs/tempo/latest/ — TraceQL reference, backend config
- **W3C TraceContext Specification:** https://www.w3.org/TR/trace-context/ — Standard context propagation format
- **"Distributed Systems Observability"** - Cindy Sridharan (O'Reilly, free online) — Nền tảng lý thuyết
- **OpenTelemetry Collector Contrib:** https://github.com/open-telemetry/opentelemetry-collector-contrib — Tất cả receivers/processors/exporters
- **Tail Sampling Processor:** https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor
- **CNCF Observability Whitepaper:** https://github.com/cncf/tag-observability/blob/main/whitepaper.md

