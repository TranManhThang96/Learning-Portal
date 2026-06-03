# Day 42: Exercises — OpenTelemetry & Distributed Tracing

**Phase 6: Observability & Reliability**
**Tổng thời gian ước tính:** 90–120 phút

---

## Exercise 1 (Easy): Instrument một HTTP Service đơn giản với OpenTelemetry

### Bối cảnh

Bạn có một Go HTTP service xử lý đơn giản chưa có instrumentation nào. Task này giúp bạn làm quen với OpenTelemetry SDK cơ bản: khởi tạo TracerProvider, tạo spans, và export sang Jaeger.

### Requirements

1. Tạo một Go HTTP service với endpoint `GET /api/products/{id}` và `GET /health`.
2. Khởi tạo OpenTelemetry SDK, export traces đến Jaeger qua OTLP gRPC.
3. Instrument endpoint `/api/products/{id}` với:
   - Một root span tên `getProduct`
   - Một child span tên `db.query` (simulate với `time.Sleep 50ms`)
   - Attribute: `product.id`, `db.system = "postgresql"`, `db.rows_affected`
4. Chạy Jaeger bằng Docker, verify trace hiển thị trong UI.
5. Health check endpoint KHÔNG được tạo span.

### Expected Outcome

```
Jaeger UI → Service: product-service → Operation: getProduct
Trace waterfall:
  product-service: getProduct          [===] 55ms
    product-service: db.query          [==]  50ms
      Attributes:
        product.id = "123"
        db.system = "postgresql"
        db.rows_affected = 1
```

### Hint

<details>
<summary>Hint 1: Khởi tạo TracerProvider</summary>

```go
func initTracer(ctx context.Context) (func(), error) {
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("localhost:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }
    
    res, _ := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName("product-service"),
        ),
    )
    
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.AlwaysSample()),
    )
    otel.SetTracerProvider(tp)
    
    return func() { tp.Shutdown(context.Background()) }, nil
}
```
</details>

<details>
<summary>Hint 2: Tạo child span trong handler</summary>

```go
func getProductHandler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context() // Context đã có parent span từ otelhttp
    
    // Root span cho business logic
    ctx, span := tracer.Start(ctx, "getProduct",
        trace.WithAttributes(attribute.String("product.id", productID)),
    )
    defer span.End()
    
    // Child span cho DB call
    _, dbSpan := tracer.Start(ctx, "db.query",
        trace.WithAttributes(
            attribute.String("db.system", "postgresql"),
            attribute.String("db.statement", "SELECT * FROM products WHERE id = ?"),
        ),
    )
    time.Sleep(50 * time.Millisecond)
    dbSpan.SetAttributes(attribute.Int("db.rows_affected", 1))
    dbSpan.End()
    
    w.WriteHeader(http.StatusOK)
}
```
</details>

<details>
<summary>Hint 3: Chạy Jaeger bằng Docker</summary>

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -e COLLECTOR_OTLP_ENABLED=true \
  jaegertracing/all-in-one:1.52
```
</details>

### Acceptance Criteria

- [ ] Service build thành công, không có lỗi compile
- [ ] Jaeger UI tại `http://localhost:16686` hiển thị service `product-service`
- [ ] Mỗi request tạo đúng 1 trace với 2 spans (getProduct + db.query)
- [ ] Span attributes chứa `product.id`, `db.system`, `db.rows_affected`
- [ ] `/health` endpoint KHÔNG tạo trace
- [ ] `docker stop jaeger && docker rm jaeger` cleanup hoạt động

### Bonus Challenge

Thêm span event khi simulate DB trả về không có data (product not found), set span status thành `codes.Error`, và return HTTP 404.

---


---

## Exercise 2 (Medium): Thiết lập OpenTelemetry Collector với Tail-based Sampling

### Bối cảnh

Bạn đang triển khai observability stack cho một e-commerce platform xử lý ~50K requests/phút. Không thể ghi lại 100% traces. Yêu cầu: giữ lại 100% error traces, 100% traces chậm (>500ms), và 5% traces bình thường. Health check traces phải bị loại bỏ.

### Requirements

1. Triển khai OTel Collector bằng Docker Compose với config:
   - Receiver: OTLP gRPC (port 4317) và HTTP (port 4318)
   - Processor: `memory_limiter`, `batch`, `filter` (loại bỏ health checks), `tail_sampling`
   - Exporter: Jaeger (OTLP) + `debug` ở chế độ `basic`
2. Tail sampling policies:
   - Policy 1: Giữ tất cả spans có status ERROR
   - Policy 2: Giữ traces có latency > 500ms
   - Policy 3: 5% còn lại (probabilistic)
3. Sử dụng service từ Exercise 1 (hoặc demo service tương tự), gửi traces đến Collector.
4. Verify: Gửi 100 requests, đếm traces trong Jaeger — phải thấy ít hơn 100 traces nhưng phải thấy tất cả error traces.
5. Expose Collector metrics ở port 8888 và verify bằng `curl`.

### Expected Outcome

```bash
# Sau khi gửi 100 requests (5 requests có error):
curl http://localhost:16686/api/traces?service=product-service | jq '.data | length'
# Expected: < 100 (5 error traces + ~5 của 5% probabilistic)
# Tất cả 5 error traces PHẢI có mặt

# Collector health:
curl http://localhost:8888/metrics | grep otelcol_receiver_accepted_spans
# otelcol_receiver_accepted_spans_total{...} 100
```

### Hint

<details>
<summary>Hint 1: Cấu trúc tail_sampling processor</summary>

```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 10000
    expected_new_traces_per_sec: 100
    policies:
      - name: keep-errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: keep-slow
        type: latency
        latency:
          threshold_ms: 500
      - name: keep-5-percent
        type: probabilistic
        probabilistic:
          sampling_percentage: 5
```
</details>

<details>
<summary>Hint 2: Filter health check spans</summary>

```yaml
processors:
  filter/drop-healthcheck:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.target"] == "/health"'
        - 'attributes["http.route"] == "/health"'
```

Lưu ý: `filter` phải chạy TRƯỚC `tail_sampling` trong pipeline.
</details>

<details>
<summary>Hint 3: Kiểm tra Collector đang hoạt động</summary>

```bash
# Health check
curl http://localhost:13133/

# Metrics Collector tự báo cáo
curl http://localhost:8888/metrics | grep -E "otelcol_(receiver|exporter|processor)"

# Kiểm tra pipeline
docker logs otel-collector --tail 50
```
</details>

### Acceptance Criteria

- [ ] Collector container chạy thành công (không crash)
- [ ] `curl http://localhost:13133/` trả về `{"status":"Server available",...}`
- [ ] 100 requests → Jaeger có < 100 traces
- [ ] Tất cả error traces (status ERROR) phải có mặt trong Jaeger
- [ ] Traces từ `/health` endpoint KHÔNG xuất hiện trong Jaeger
- [ ] `curl http://localhost:8888/metrics` trả về Collector self-metrics

### Bonus Challenge

Thêm exporter Prometheus: expose span metrics (request count, latency histogram theo service, operation) tại port 8889. Query bằng `curl` để verify.

---


---

## Exercise 3 (Hard): Trace Correlation — Kết nối Traces với Logs (Loki) và Metrics (Prometheus)

### Bối cảnh

Bạn được giao task xây dựng observability stack hoàn chỉnh cho production team: khi thấy latency tăng trên dashboard Grafana, engineer phải có thể click từ metric exemplar sang trace, rồi từ trace sang logs — tất cả trong một workflow liền mạch. Đây là bài tập tích hợp toàn bộ "Three Pillars" đã học từ Day 38-42.

### Requirements

1. **Infrastructure stack** (Docker Compose):
   - Jaeger (tracing backend)
   - Loki + Promtail (log aggregation)
   - Prometheus (metrics)
   - Grafana (visualization, port 3000)
   - OTel Collector (central pipeline)

2. **Go service** instrument đầy đủ:
   - Traces: Export đến Collector → Jaeger
   - Logs (structured JSON): In ra stdout với các fields `traceID`, `spanID`, `level`, `message`, `timestamp`
   - Metrics: Expose histogram `http_request_duration_seconds` với Exemplars (gắn traceID)

3. **Collector pipeline:**
   - Nhận OTLP traces từ service
   - Scrape Prometheus metrics từ service (hoặc dùng service expose endpoint)

4. **Grafana configuration:**
   - Datasource: Jaeger, Loki, Prometheus (provisioned qua YAML, không cấu hình thủ công)
   - Dashboard với 1 panel: HTTP latency histogram
   - Exemplar link: metric point → trace trong Jaeger
   - Trace-to-logs link trong Jaeger (Loki datasource)

5. **Verify end-to-end workflow:**
   - Gửi request chậm (> 500ms) bằng cách trigger special endpoint `/api/slow`
   - Trong Grafana: Thấy latency spike trên graph
   - Click exemplar → Jaeger trace hiển thị (phải có TraceID trong exemplar)
   - Trong trace, xem log panel với filter `{service="my-service"} | json | traceID="<id>"`

### Expected Outcome

```
Workflow hoàn chỉnh:
Grafana (Metrics) → [click exemplar] → Jaeger (Trace) → [Trace to Logs] → Loki (Logs)

Logs phải có format:
{"level":"info","timestamp":"2024-01-01T00:00:00Z",
 "msg":"request processed","traceID":"abc123","spanID":"def456",
 "duration_ms":520,"path":"/api/slow"}
```

### Hint

<details>
<summary>Hint 1: Structured logging với traceID injection (Go)</summary>

```go
import (
    "go.opentelemetry.io/otel/trace"
    "log/slog"
    "os"
)

var logger = slog.New(slog.NewJSONHandler(os.Stdout, nil))

func logWithTrace(ctx context.Context, level slog.Level, msg string, args ...any) {
    span := trace.SpanFromContext(ctx)
    sc := span.SpanContext()
    
    allArgs := append([]any{
        "traceID", sc.TraceID().String(),
        "spanID",  sc.SpanID().String(),
    }, args...)
    
    logger.Log(ctx, level, msg, allArgs...)
}

// Usage:
logWithTrace(ctx, slog.LevelInfo, "request processed",
    "duration_ms", elapsed.Milliseconds(),
    "path", r.URL.Path,
)
```
</details>

<details>
<summary>Hint 2: Prometheus histogram với Exemplars</summary>

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "go.opentelemetry.io/otel/trace"
)

var requestDuration = prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "HTTP request duration",
        Buckets: prometheus.DefBuckets,
    },
    []string{"method", "route", "status_code"},
)

func recordMetricWithExemplar(ctx context.Context, method, route string, statusCode int, duration float64) {
    span := trace.SpanFromContext(ctx)
    sc := span.SpanContext()
    
    requestDuration.With(prometheus.Labels{
        "method":      method,
        "route":       route,
        "status_code": fmt.Sprintf("%d", statusCode),
    }).(prometheus.ExemplarObserver).ObserveWithExemplar(duration,
        prometheus.Labels{
            "traceID": sc.TraceID().String(),
        },
    )
}
```

Lưu ý: Prometheus phải bật native histograms để hỗ trợ exemplars:
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'my-service'
    static_configs:
      - targets: ['my-service:8080']
    # Enable exemplars
feature_flags:
  - exemplar-storage
```

Và trong Grafana, bật "Exemplars" trong datasource config.
</details>

<details>
<summary>Hint 3: Grafana datasource provisioning</summary>

```yaml
# grafana/provisioning/datasources/datasources.yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      exemplarTraceIdDestinations:
        - name: traceID
          datasourceUid: jaeger-uid    # Phải match uid của Jaeger datasource
          urlDisplayLabel: "View in Jaeger"

  - name: Jaeger
    type: jaeger
    uid: jaeger-uid
    url: http://jaeger:16686
    jsonData:
      tracesToLogsV2:
        datasourceUid: loki-uid
        filterByTraceID: true
        customQuery: true
        query: '{service="my-service"} | json | traceID="${__trace.traceId}"'

  - name: Loki
    type: loki
    uid: loki-uid
    url: http://loki:3100
```
</details>

### Acceptance Criteria

- [ ] `docker-compose up` khởi động toàn bộ stack không có lỗi
- [ ] Grafana tại `http://localhost:3000` accessible (admin/admin)
- [ ] Tất cả datasources (Prometheus, Jaeger, Loki) hiển thị "Data source connected" trong Grafana
- [ ] Gửi request đến `/api/slow` → Trace hiển thị trong Jaeger với duration > 500ms
- [ ] Log JSON có `traceID` field khớp với TraceID trong Jaeger
- [ ] Trong Grafana metric panel, click exemplar point → mở Jaeger trace đúng
- [ ] Trong Jaeger trace, "Trace to logs" button → mở Loki với filter traceID đúng
- [ ] `docker-compose down -v` cleanup hoàn toàn

### Bonus Challenge

1. Thêm **Grafana alert rule**: Khi `p99 latency > 1s` trong 2 phút → tạo alert. Alert annotation phải chứa link đến trace exemplar.
2. Implement **baggage propagation**: Service A đọc `X-User-ID` header, đặt vào Baggage. Service B đọc baggage và log `userID`. Verify trong trace viewer.

---


---

## Checklist tự đánh giá

Sau khi hoàn thành tất cả exercises, bạn phải demonstrate được:

| Kỹ năng | Easy | Medium | Hard |
|---------|------|--------|------|
| Khởi tạo OTel SDK và TracerProvider | ✓ | | |
| Tạo spans với attributes và events | ✓ | | |
| Auto-instrument HTTP với otelhttp | ✓ | ✓ | ✓ |
| Cấu hình OTel Collector pipeline | | ✓ | ✓ |
| Tail-based sampling | | ✓ | |
| Filter health check spans | | ✓ | ✓ |
| Structured logging với traceID | | | ✓ |
| Prometheus exemplars | | | ✓ |
| Grafana datasource provisioning | | | ✓ |
| End-to-end Metrics → Trace → Logs | | | ✓ |

---

## Solutions

<details>
<summary>Solution Exercise 1</summary>

```go
package main

import (
    "context"
    "fmt"
    "log"
    "net/http"
    "strings"
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
        otlptracegrpc.WithEndpoint("localhost:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        log.Fatalf("failed to create exporter: %v", err)
    }
    res, _ := resource.New(ctx,
        resource.WithAttributes(semconv.ServiceName("product-service")),
    )
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.AlwaysSample()),
    )
    otel.SetTracerProvider(tp)
    tracer = tp.Tracer("product-service")
    return func() { tp.Shutdown(context.Background()) }
}

func getProductHandler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    // Extract product ID from path: /api/products/123
    parts := strings.Split(r.URL.Path, "/")
    productID := "unknown"
    if len(parts) >= 4 {
        productID = parts[3]
    }

    ctx, span := tracer.Start(ctx, "getProduct",
        trace.WithAttributes(attribute.String("product.id", productID)),
    )
    defer span.End()

    // Simulate DB query
    _, dbSpan := tracer.Start(ctx, "db.query",
        trace.WithAttributes(
            attribute.String("db.system", "postgresql"),
            attribute.String("db.statement", "SELECT * FROM products WHERE id = ?"),
        ),
    )
    time.Sleep(50 * time.Millisecond)

    // Bonus: simulate not found
    if productID == "999" {
        dbSpan.SetAttributes(attribute.Int("db.rows_affected", 0))
        dbSpan.AddEvent("product_not_found")
        dbSpan.End()
        span.SetStatus(codes.Error, "product not found")
        http.Error(w, "product not found", http.StatusNotFound)
        return
    }

    dbSpan.SetAttributes(attribute.Int("db.rows_affected", 1))
    dbSpan.End()

    fmt.Fprintf(w, `{"id":"%s","name":"Product %s"}`, productID, productID)
}

func main() {
    ctx := context.Background()
    shutdown := initTracer(ctx)
    defer shutdown()

    mux := http.NewServeMux()
    mux.Handle("/api/products/", otelhttp.NewHandler(
        http.HandlerFunc(getProductHandler), "GET /api/products/{id}",
    ))
    mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(200)
    })

    fmt.Println("product-service on :8080")
    log.Fatal(http.ListenAndServe(":8080", mux))
}
```

**go.mod:**
```
module product-service

go 1.21

require (
    go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.46.1
    go.opentelemetry.io/otel v1.21.0
    go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.21.0
    go.opentelemetry.io/otel/sdk v1.21.0
    go.opentelemetry.io/otel/semconv/v1.21.0 v1.21.0
)
```

**Test:**
```bash
curl http://localhost:8080/api/products/123   # → 200, trace created
curl http://localhost:8080/api/products/999   # → 404, error span
curl http://localhost:8080/health             # → 200, NO trace
```
</details>

<details>
<summary>Solution Exercise 2</summary>

**`docker-compose.yaml`:**
```yaml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:1.52
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"
      - "14317:4317"  # Jaeger internal OTLP
    networks: [otel]

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.90.0
    volumes:
      - ./collector-config.yaml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8888:8888"   # Collector self-metrics
      - "13133:13133" # Health check
      - "8889:8889"   # Prometheus (bonus)
    depends_on: [jaeger]
    networks: [otel]

networks:
  otel:
    driver: bridge
```

**`collector-config.yaml`:**
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 256
    spike_limit_mib: 64

  filter/drop-healthcheck:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.target"] == "/health"'

  tail_sampling:
    decision_wait: 10s
    num_traces: 10000
    expected_new_traces_per_sec: 50
    policies:
      - name: keep-errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: keep-slow
        type: latency
        latency:
          threshold_ms: 500
      - name: keep-5-percent
        type: probabilistic
        probabilistic:
          sampling_percentage: 5

  batch:
    timeout: 2s
    send_batch_size: 256

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  debug:
    verbosity: basic

  # Bonus: Prometheus exporter
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: otel

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  pprof:
    endpoint: 0.0.0.0:1777

service:
  extensions: [health_check, pprof]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, filter/drop-healthcheck, tail_sampling, batch]
      exporters: [otlp/jaeger, debug]
  telemetry:
    metrics:
      address: 0.0.0.0:8888
```

**Test script (generate 100 requests, 5 errors):**
```bash
#!/bin/bash
# generate-traffic.sh
for i in $(seq 1 95); do
  curl -s "http://localhost:8080/api/products/$i" > /dev/null
done
# 5 error requests
for i in $(seq 1 5); do
  curl -s "http://localhost:8080/api/products/999" > /dev/null
done
echo "Sent 100 requests (95 normal, 5 errors)"
sleep 15  # wait for tail sampling decision_wait
echo "Check Jaeger: http://localhost:16686"
```
</details>

<details>
<summary>Solution Exercise 3 — Cấu trúc file và key snippets</summary>

**Project structure:**
```
ex3-full-stack/
├── docker-compose.yaml
├── my-service/
│   ├── main.go
│   ├── go.mod
│   └── Dockerfile
├── collector/
│   └── config.yaml
├── prometheus/
│   └── prometheus.yml
├── loki/
│   └── loki-config.yaml
├── promtail/
│   └── promtail-config.yaml
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── datasources.yaml
        └── dashboards/
            ├── dashboard-provider.yaml
            └── latency.json
```

**docker-compose.yaml (key services):**
```yaml
version: '3.8'

services:
  loki:
    image: grafana/loki:2.9.0
    ports: ["3100:3100"]
    volumes:
      - ./loki/loki-config.yaml:/etc/loki/local-config.yaml
    command: -config.file=/etc/loki/local-config.yaml
    networks: [obs]

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail/promtail-config.yaml:/etc/promtail/config.yaml
    command: -config.file=/etc/promtail/config.yaml
    networks: [obs]

  prometheus:
    image: prom/prometheus:v2.47.0
    ports: ["9090:9090"]
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--enable-feature=exemplar-storage'   # Enable exemplars!
    networks: [obs]

  grafana:
    image: grafana/grafana:10.2.0
    ports: ["3000:3000"]
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
      - GF_FEATURE_TOGGLES_ENABLE=traceqlEditor
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
    networks: [obs]

  jaeger:
    image: jaegertracing/all-in-one:1.52
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"
    networks: [obs]

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.90.0
    volumes:
      - ./collector/config.yaml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4317:4317"
      - "4318:4318"
    networks: [obs]

  my-service:
    build: ./my-service
    ports: ["8080:8080"]
    labels:
      - "promtail.scrape=true"   # Promtail picks up logs from this container
    networks: [obs]

networks:
  obs:
    driver: bridge
```

**my-service/main.go (key slow endpoint):**
```go
// /api/slow endpoint: simulate bottleneck
func slowHandler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    start := time.Now()
    
    ctx, span := tracer.Start(ctx, "slowOperation")
    defer span.End()
    
    // Simulate slow external call
    _, extSpan := tracer.Start(ctx, "external.api.call",
        trace.WithAttributes(attribute.String("peer.service", "legacy-api")))
    time.Sleep(600 * time.Millisecond)
    extSpan.End()
    
    duration := time.Since(start)
    logWithTrace(ctx, slog.LevelInfo, "slow request completed",
        "duration_ms", duration.Milliseconds(),
        "path", "/api/slow",
    )
    recordMetricWithExemplar(ctx, "GET", "/api/slow", 200, duration.Seconds())
    
    w.WriteHeader(200)
    fmt.Fprint(w, `{"status":"ok","note":"this was intentionally slow"}`)
}
```

**Verify script:**
```bash
#!/bin/bash
echo "=== Starting full observability stack ==="
docker-compose up -d
sleep 10

echo "=== Generating traffic ==="
for i in $(seq 1 10); do
  curl -s http://localhost:8080/api/slow > /dev/null
  curl -s http://localhost:8080/api/products/$i > /dev/null
done

echo ""
echo "=== Verify ==="
echo "Jaeger services:"
curl -s http://localhost:16686/api/services | python3 -m json.tool

echo ""
echo "Prometheus targets:"
curl -s http://localhost:9090/api/v1/targets | python3 -c "
import sys,json
data=json.load(sys.stdin)
for t in data['data']['activeTargets']:
    print(t['scrapeUrl'], '->', t['health'])
"

echo ""
echo "Open Grafana: http://localhost:3000"
echo "Open Jaeger:  http://localhost:16686"
```
</details>

