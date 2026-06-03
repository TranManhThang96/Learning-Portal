# Day 42: Cheat Sheet — OpenTelemetry & Distributed Tracing

**Phase 6: Observability & Reliability**

---

## 1. Khái niệm cốt lõi — Quick Reference

| Khái niệm | Định nghĩa ngắn | Tương tự |
|-----------|----------------|----------|
| **Trace** | Toàn bộ hành trình 1 request qua nhiều services | Stack trace vượt network |
| **Span** | Đơn vị công việc nhỏ nhất (có start/end time) | Một frame trong stack trace |
| **TraceID** | UUID 128-bit, duy nhất cho 1 trace | Thread ID trong monolith |
| **SpanID** | UUID 64-bit, duy nhất cho 1 span | Function call ID |
| **ParentSpanID** | SpanID của span cha → tạo thành cây | Caller function |
| **Context Propagation** | Truyền TraceID/SpanID qua network | Pass `ctx` qua function |
| **Baggage** | Metadata tùy ý truyền qua toàn bộ trace | Thread-local storage qua network |
| **Sampling** | Quyết định giữ hay bỏ trace | Log level (DEBUG vs INFO) |

---

## 2. W3C TraceContext Header Format

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             ^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^ ^^
             |   TraceID (32 hex chars = 128-bit)  SpanID (16 hex)  Flags
             version=00                                              01=sampled

tracestate: vendor1=value1,rojo=00f067aa0ba902b7    (optional, vendor-specific)
baggage: userId=123,region=us-east-1                (optional, propagated metadata)
```

---

## 3. OpenTelemetry SDK — Go Quick Reference

### 3.1 Khởi tạo TracerProvider

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func initTracer(ctx context.Context) (func(), error) {
    // 1. Exporter (gửi data đến Collector hoặc backend)
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(), // bỏ ở production, dùng TLS
    )
    if err != nil {
        return nil, err
    }

    // 2. Resource (metadata về service)
    res, _ := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName("my-service"),
            semconv.ServiceVersion("1.2.3"),
            semconv.DeploymentEnvironment("production"),
        ),
        resource.WithFromEnv(),       // Đọc OTEL_SERVICE_NAME, OTEL_RESOURCE_ATTRIBUTES
        resource.WithTelemetrySDK(),  // Thêm otel SDK version
    )

    // 3. TracerProvider
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),     // Async batch export (production)
        // sdktrace.WithSyncer(exporter),   // Sync export (testing only)
        sdktrace.WithResource(res),
        sdktrace.WithSampler(
            sdktrace.ParentBased(           // Respect parent's sampling decision
                sdktrace.TraceIDRatioBased(0.1), // 10% nếu không có parent
            ),
        ),
    )

    otel.SetTracerProvider(tp)
    // otel.SetTextMapPropagator(propagation.TraceContext{}) // Mặc định W3C

    return func() {
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cancel()
        tp.Shutdown(ctx)
    }, nil
}
```

### 3.2 Tạo và sử dụng Spans

```go
var tracer = otel.Tracer("my-service") // gọi sau khi initTracer()

func myFunction(ctx context.Context, userID string) error {
    // Bắt đầu span
    ctx, span := tracer.Start(ctx, "myFunction",
        trace.WithSpanKind(trace.SpanKindInternal),
        trace.WithAttributes(
            attribute.String("user.id", userID),
            attribute.Int("retry.count", 0),
        ),
    )
    defer span.End() // LUÔN defer End()

    // Thêm attributes sau
    span.SetAttributes(attribute.String("result", "success"))

    // Thêm event (structured log gắn vào span)
    span.AddEvent("cache_miss", trace.WithAttributes(
        attribute.String("cache.key", "user:"+userID),
    ))

    // Record error
    if err := doSomething(ctx); err != nil {
        span.RecordError(err)                          // Ghi exception
        span.SetStatus(codes.Error, err.Error())       // Đánh dấu span là lỗi
        return err
    }

    span.SetStatus(codes.Ok, "")
    return nil
}
```

### 3.3 Span Kinds

```go
trace.SpanKindServer   // HTTP/gRPC server handler (nhận request)
trace.SpanKindClient   // HTTP/gRPC client call (gửi request đến service khác)
trace.SpanKindProducer // Publish message (Kafka, RabbitMQ)
trace.SpanKindConsumer // Consume message
trace.SpanKindInternal // Internal logic (mặc định)
```

### 3.4 Context Propagation thủ công

```go
// Inject (service A → gửi đến service B)
propagator := otel.GetTextMapPropagator()
carrier := propagation.MapCarrier{}
propagator.Inject(ctx, carrier)
// carrier["traceparent"] = "00-abc123..."
// Gắn vào HTTP header: request.Header.Set("traceparent", carrier["traceparent"])

// Extract (service B ← nhận từ service A)
ctx = propagator.Extract(ctx, propagation.HeaderCarrier(request.Header))
// ctx bây giờ có parent span từ service A
```

### 3.5 Baggage

```go
import "go.opentelemetry.io/otel/baggage"

// Đặt baggage (service A)
member, _ := baggage.NewMember("tenant.id", "tenant-123")
bag, _ := baggage.New(member)
ctx = baggage.ContextWithBaggage(ctx, bag)

// Đọc baggage (service B, sau khi extract context)
bag := baggage.FromContext(ctx)
tenantID := bag.Member("tenant.id").Value()
```

### 3.6 Auto-instrumentation (HTTP, DB)

```go
// HTTP Server (tự tạo span cho mỗi request)
import "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
mux.Handle("/api/orders", otelhttp.NewHandler(handler, "POST /api/orders"))

// HTTP Client (tự inject traceparent header)
client := &http.Client{
    Transport: otelhttp.NewTransport(http.DefaultTransport),
}

// database/sql (tự tạo span cho mỗi query)
import "github.com/XSAM/otelsql"
db, _ := otelsql.Open("postgres", dsn,
    otelsql.WithAttributes(semconv.DBSystemPostgreSQL),
)

// gRPC (server và client)
import "go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
grpc.NewServer(grpc.StatsHandler(otelgrpc.NewServerHandler()))
grpc.Dial(addr, grpc.WithStatsHandler(otelgrpc.NewClientHandler()))
```

---

## 4. Semantic Conventions — Attribute Names Chuẩn

Luôn tuân thủ semantic conventions để queries trong Jaeger/Tempo hoạt động đúng:

```
HTTP:
  http.method          = "GET", "POST"
  http.url             = "https://api.example.com/users"
  http.route           = "/users/{id}"      ← dùng template, không phải value
  http.status_code     = 200, 404, 500
  http.target          = "/users/123?page=1"

Database:
  db.system            = "postgresql", "mysql", "redis", "mongodb"
  db.name              = "mydb"
  db.operation         = "SELECT", "INSERT", "UPDATE"
  db.statement         = "SELECT * FROM users WHERE id = ?"   ← không có values!
  db.table             = "users"
  db.rows_affected     = 1

RPC (gRPC):
  rpc.system           = "grpc"
  rpc.service          = "helloworld.Greeter"
  rpc.method           = "SayHello"
  rpc.grpc.status_code = 0  (0=OK, 2=UNKNOWN, 14=UNAVAILABLE)

Messaging (Kafka):
  messaging.system               = "kafka"
  messaging.destination          = "orders-topic"
  messaging.destination_kind     = "topic"
  messaging.operation            = "publish", "receive"
  messaging.kafka.consumer.group = "order-processor"

Service:
  service.name         = "order-service"
  service.version      = "1.2.3"
  service.namespace    = "ecommerce"

Deployment:
  deployment.environment = "production", "staging", "development"
  k8s.namespace.name     = "default"
  k8s.pod.name           = "order-service-abc123"
```

---

## 5. OpenTelemetry Collector — Config Cheat Sheet

### 5.1 Full Config Template

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins: ["https://my-app.com"]

  # Pull Prometheus metrics từ services
  prometheus:
    config:
      scrape_configs:
        - job_name: 'my-service'
          static_configs:
            - targets: ['my-service:8080']

  # Host metrics (CPU, memory, disk)
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu: {}
      memory: {}
      disk: {}
      network: {}

processors:
  # BẮT BUỘC: Giới hạn memory
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
    spike_limit_mib: 128

  # BẮT BUỘC: Batch để tăng throughput
  batch:
    timeout: 5s
    send_batch_size: 1024
    send_batch_max_size: 2048

  # Resource detection (thêm cloud/k8s metadata)
  resourcedetection:
    detectors: [env, docker, system, k8snode]
    override: false

  # Filter spans không cần thiết
  filter/drop-noise:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.target"] == "/health"'
        - 'attributes["http.target"] == "/ready"'
        - 'attributes["http.target"] == "/metrics"'
        - 'name == "grpc.health.v1.Health/Check"'

  # Transform: redact sensitive data
  transform/redact:
    trace_statements:
      - context: span
        statements:
          - delete_key(attributes, "http.request.header.authorization")
          - delete_key(attributes, "http.request.header.cookie")
          - replace_pattern(attributes, "db.statement", "\\d{13,16}", "****")

  # Tail-based sampling
  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    expected_new_traces_per_sec: 500
    policies:
      - name: keep-errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: keep-slow
        type: latency
        latency: {threshold_ms: 500}
      - name: keep-fraction
        type: probabilistic
        probabilistic: {sampling_percentage: 10}

  # Attribute processing
  attributes/add-env:
    actions:
      - key: environment
        value: production
        action: insert

exporters:
  # Jaeger via OTLP
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true   # Production: dùng cert_file/key_file

  # Tempo via OTLP
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

  # Prometheus (expose endpoint cho Prometheus scrape)
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: otel
    send_timestamps: true

  # Loki (forward logs)
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

  # Debug (stdout, chỉ dùng dev/troubleshoot)
  debug:
    verbosity: basic   # basic | normal | detailed

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  pprof:
    endpoint: 0.0.0.0:1777
  zpages:
    endpoint: 0.0.0.0:55679

service:
  extensions: [health_check, pprof, zpages]
  
  pipelines:
    traces:
      receivers:  [otlp]
      processors: [memory_limiter, filter/drop-noise, transform/redact,
                   tail_sampling, batch]
      exporters:  [otlp/jaeger, debug]

    metrics:
      receivers:  [otlp, prometheus, hostmetrics]
      processors: [memory_limiter, resourcedetection, batch]
      exporters:  [prometheus]

    logs:
      receivers:  [otlp]
      processors: [memory_limiter, batch]
      exporters:  [loki]

  telemetry:
    metrics:
      address: 0.0.0.0:8888
    logs:
      level: info
```

### 5.2 Collector Troubleshooting Commands

```bash
# Health check
curl http://localhost:13133/

# Self-metrics (throughput, errors, drops)
curl http://localhost:8888/metrics | grep -E "otelcol_(receiver|processor|exporter)"

# Key metrics to watch:
# otelcol_receiver_accepted_spans_total      ← spans nhận được
# otelcol_exporter_sent_spans_total          ← spans gửi thành công
# otelcol_exporter_send_failed_spans_total   ← spans gửi thất bại (ALERT này!)
# otelcol_processor_dropped_spans_total      ← spans bị drop (memory_limiter)

# zpages (debug pipeline, service, traces)
# Mở browser: http://localhost:55679/debug/servicez
# http://localhost:55679/debug/pipelinez
# http://localhost:55679/debug/tracez

# Logs
docker logs otel-collector --tail 100 -f
```

---

## 6. Jaeger vs Grafana Tempo — Comparison Matrix

```
┌─────────────────────────┬────────────────────────────┬────────────────────────────┐
│ Tiêu chí                │ Jaeger                     │ Grafana Tempo              │
├─────────────────────────┼────────────────────────────┼────────────────────────────┤
│ STORAGE                 │                            │                            │
│ Backend options         │ Cassandra, Elasticsearch,  │ S3, GCS, Azure Blob,       │
│                         │ Badger (local), OpenSearch │ local filesystem           │
│ Storage cost (1TB/mo)   │ ES: ~$50-200 (EC2+storage) │ S3: ~$23                   │
│ Compression             │ Yes (ES built-in)          │ Yes (parquet format)       │
├─────────────────────────┼────────────────────────────┼────────────────────────────┤
│ QUERY                   │                            │                            │
│ Query language          │ UI form-based, tags search │ TraceQL (powerful DSL)     │
│ Full-text search spans  │ Yes (ES backend)           │ TraceQL (attribute search)  │
│ TraceID lookup latency  │ < 100ms                    │ < 100ms                    │
│ Complex queries         │ Limited                    │ Powerful (TraceQL)         │
├─────────────────────────┼────────────────────────────┼────────────────────────────┤
│ SCALABILITY             │                            │                            │
│ Max spans/day           │ ~100M (ES cluster)         │ Virtually unlimited (S3)   │
│ Horizontal scaling      │ ES cluster scaling         │ Stateless + object storage │
│ Multi-tenancy           │ Limited                    │ Native                     │
├─────────────────────────┼────────────────────────────┼────────────────────────────┤
│ ECOSYSTEM               │                            │                            │
│ Standalone UI           │ Full-featured UI           │ Dùng Grafana               │
│ Grafana integration     │ Plugin datasource          │ Native datasource          │
│ Loki correlation        │ Manual config              │ Automatic (same org)       │
│ Prometheus correlation  │ Manual exemplar config     │ Automatic (same org)       │
├─────────────────────────┼────────────────────────────┼────────────────────────────┤
│ OPERATIONS              │                            │                            │
│ Operational complexity  │ Medium (quản lý ES/Cass)  │ Low (chỉ object storage)   │
│ Backup/restore          │ ES snapshot                │ Standard S3 backup         │
│ Resource requirements   │ ES: 3+ nodes, nhiều RAM    │ Tempo: 1-2 nodes + S3      │
├─────────────────────────┼────────────────────────────┼────────────────────────────┤
│ KHI NÀO CHỌN            │                            │                            │
│ Scenario phù hợp        │ - Team mới, cần UI đơn    │ - Đã dùng Grafana stack    │
│                         │   giản và độc lập          │ - Scale > 10M spans/day    │
│                         │ - Không có S3/object store │ - Muốn cost-effective      │
│                         │ - Cần full-text search     │ - Muốn TraceQL queries     │
│                         │ - On-premise, không có     │ - Cloud-native workloads   │
│                         │   cloud object storage     │ - Muốn tích hợp L+M+T      │
└─────────────────────────┴────────────────────────────┴────────────────────────────┘
```

**TraceQL Quick Reference (Tempo):**

```
# Tìm trace theo TraceID
{ traceID = "4bf92f3577b34da6" }

# Tìm tất cả traces có error
{ status = error }

# Tìm traces chậm từ service cụ thể
{ resource.service.name = "order-service" && duration > 500ms }

# Tìm traces có span chứa attribute
{ span.http.route = "/api/orders" && span.http.status_code = 500 }

# Aggregate: đếm traces theo service
{ } | by(resource.service.name) | count() > 0

# Tìm traces liên quan đến user
{ span.user.id = "user-123" }

# Kết hợp: error traces chậm từ specific service
{ resource.service.name = "inventory-service" && status = error && duration > 1s }
```

---

## 7. Sampling Decision Framework

```
                    ┌─────────────────────────────────────┐
                    │    TRAFFIC VOLUME PER DAY?          │
                    └─────────────────────────────────────┘
                           │              │
                    < 1M requests    ≥ 1M requests
                           │              │
                    ┌──────▼──────┐  ┌────▼────────────────────┐
                    │ AlwaysOn    │  │ CRITICAL TRACES?         │
                    │ (100%)      │  │ (errors, slow, VIP user) │
                    │ Simple,     │  └────┬───────────────────┬─┘
                    │ no config   │       │ Yes               │ No
                    └─────────────┘  ┌────▼──────────┐  ┌────▼──────────────┐
                                     │ Tail-based    │  │ Head-based        │
                                     │ Sampling      │  │ (Probabilistic)   │
                                     │               │  │                   │
                                     │ Keep:         │  │ 1-10% rate        │
                                     │ - All errors  │  │ + AlwaysOn errors │
                                     │ - Slow > Xms  │  │                   │
                                     │ - VIP users   │  │ Simpler config    │
                                     │ - N% others   │  │ Lower overhead    │
                                     │               │  │                   │
                                     │ Needs buffer  │  │ May miss rare err │
                                     │ Complex setup │  │                   │
                                     └───────────────┘  └───────────────────┘
```

**Sampling rate recommendations:**

| Traffic/day | Head-based Rate | Tail-based Fallback | Expected stored spans/day |
|-------------|-----------------|---------------------|---------------------------|
| < 1M        | 100%            | N/A                 | < 1M                      |
| 1M - 10M    | 20-50%          | Optional            | 200K - 5M                 |
| 10M - 100M  | 5-10%           | Recommended         | 500K - 10M                |
| > 100M      | 1-5%            | Required            | 1M - 5M                   |

---

## 8. Environment Variables — OTel SDK Config

```bash
# Service identity
OTEL_SERVICE_NAME=order-service
OTEL_SERVICE_VERSION=1.2.3
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,team=backend

# Exporter config
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc          # grpc | http/protobuf | http/json
OTEL_EXPORTER_OTLP_TIMEOUT=10000          # milliseconds
OTEL_EXPORTER_OTLP_HEADERS=api-key=secret # Custom headers (auth)

# Sampling
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1               # 10% sampling rate

# Turn off tracing entirely (disaster mode)
OTEL_TRACES_EXPORTER=none

# Propagation
OTEL_PROPAGATORS=tracecontext,baggage     # W3C standards (default)
# OTEL_PROPAGATORS=b3,b3multi            # B3 (Zipkin compat)
# OTEL_PROPAGATORS=jaeger                # Jaeger native header

# Batch processor tuning
OTEL_BSP_MAX_QUEUE_SIZE=2048
OTEL_BSP_MAX_EXPORT_BATCH_SIZE=512
OTEL_BSP_EXPORT_TIMEOUT=30000
OTEL_BSP_SCHEDULE_DELAY=5000
```

---

## 9. Docker Compose — Minimal Stack Templates

### 9.1 Minimal: Jaeger Only (Development)

```yaml
version: '3.8'
services:
  jaeger:
    image: jaegertracing/all-in-one:1.52
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC (direct, no Collector)
      - "4318:4318"    # OTLP HTTP
```

Trỏ SDK đến `localhost:4317`, không cần Collector.

### 9.2 Standard: Collector + Jaeger (Staging)

```yaml
version: '3.8'
services:
  jaeger:
    image: jaegertracing/all-in-one:1.52
    environment: [COLLECTOR_OTLP_ENABLED=true]
    ports: ["16686:16686"]
    networks: [obs]

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.90.0
    volumes:
      - ./collector-config.yaml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4317:4317"
      - "4318:4318"
      - "8888:8888"   # Self-metrics
      - "13133:13133" # Health
    networks: [obs]

networks:
  obs:
    driver: bridge
```

### 9.3 Full Stack: Collector + Tempo + Grafana (Production-like)

```yaml
version: '3.8'
services:
  tempo:
    image: grafana/tempo:2.3.0
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml
      - tempo-data:/var/tempo
    ports: ["3200:3200"]
    networks: [obs]

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.90.0
    volumes:
      - ./collector-config.yaml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4317:4317"
      - "4318:4318"
    networks: [obs]

  grafana:
    image: grafana/grafana:10.2.0
    ports: ["3000:3000"]
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_FEATURE_TOGGLES_ENABLE=traceqlEditor
    networks: [obs]

volumes:
  tempo-data:

networks:
  obs:
    driver: bridge
```

**tempo.yaml:**
```yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal

compactor:
  compaction:
    block_retention: 168h  # 7 days
```

---

## 10. Collector Quick Deploy — Kubernetes

```yaml
# otel-collector-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
  namespace: observability
spec:
  replicas: 2
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
        - name: otel-collector
          image: otel/opentelemetry-collector-contrib:0.90.0
          args: ["--config=/conf/config.yaml"]
          resources:
            requests:
              cpu: 200m
              memory: 400Mi
            limits:
              cpu: 1000m
              memory: 1Gi
          ports:
            - containerPort: 4317  # OTLP gRPC
            - containerPort: 4318  # OTLP HTTP
            - containerPort: 8888  # Metrics
            - containerPort: 13133 # Health
          livenessProbe:
            httpGet:
              path: /
              port: 13133
          readinessProbe:
            httpGet:
              path: /
              port: 13133
          volumeMounts:
            - name: config
              mountPath: /conf
      volumes:
        - name: config
          configMap:
            name: otel-collector-config
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
  namespace: observability
spec:
  ports:
    - name: otlp-grpc
      port: 4317
    - name: otlp-http
      port: 4318
    - name: metrics
      port: 8888
  selector:
    app: otel-collector
```

**Cấu hình app pods trỏ đến Collector:**
```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-collector.observability.svc.cluster.local:4317"
  - name: OTEL_SERVICE_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.labels['app']
```

---

## 11. Common Commands — Quick Reference

```bash
# === JAEGER ===
# Xem danh sách services
curl -s http://localhost:16686/api/services | jq '.data[]'

# Xem traces của service (10 traces gần nhất)
curl -s "http://localhost:16686/api/traces?service=order-service&limit=10" | jq '.data | length'

# Xem trace theo TraceID
curl -s "http://localhost:16686/api/traces/4bf92f3577b34da6" | jq '.data[0].spans | length'

# === OTEL COLLECTOR ===
# Health check
curl -s http://localhost:13133/ | jq .

# Self-metrics
curl -s http://localhost:8888/metrics | grep otelcol_exporter_sent_spans

# zpages debug
curl -s http://localhost:55679/debug/servicez   # Service info
curl -s http://localhost:55679/debug/pipelinez  # Pipeline info

# === TEMPO ===
# Query by TraceID
curl -s "http://localhost:3200/api/traces/4bf92f3577b34da6" | jq .

# TraceQL search (Tempo API)
curl -s -G "http://localhost:3200/api/search" \
  --data-urlencode 'q={ status = error && duration > 500ms }' \
  --data 'limit=20&start=1700000000&end=1700086400' | jq '.traces[].traceID'

# === DEBUGGING ===
# Test nếu Collector nhận được spans
docker logs otel-collector 2>&1 | grep -i "span\|trace\|error" | tail -20

# Check container networking
docker exec my-app nc -zv otel-collector 4317 && echo "Connected!" || echo "FAILED"

# Verify OTLP endpoint reachable
curl -v http://localhost:4318/v1/traces \
  -H 'Content-Type: application/json' \
  -d '{"resourceSpans":[]}'
# Expected: 200 OK (empty body is fine)
```

---

## 12. Observability Stack — Three Pillars Integration Summary

```
                         USER REQUEST
                              │
              ┌───────────────┴───────────────┐
              │         YOUR SERVICE           │
              │  ┌─────────────────────────┐  │
              │  │     OTel SDK            │  │
              │  │  traces ──┐             │  │
              │  │  metrics ─┼──► OTLP ───┼──┼──► OTel Collector
              │  │  logs ────┘   (gRPC)   │  │         │
              │  └─────────────────────────┘  │    ┌────┴────────────────────┐
              └───────────────────────────────┘    │                         │
                                                   ▼                         ▼
                                            ┌──────────┐             ┌────────────┐
                                            │  Traces  │             │  Metrics   │
                                            │ Jaeger / │             │ Prometheus │
                                            │  Tempo   │             └─────┬──────┘
                                            └──────┬───┘                   │
                                                   │              ┌────────▼──────────┐
                                            ┌──────▼───┐          │      Logs         │
                                            │  Logs    │◄─────────│  Loki / ELK       │
                                            │ (correl) │ traceID   │  (structured JSON) │
                                            └──────────┘          └───────────────────┘
                                                   │                        │
                                            ┌──────▼────────────────────────▼──────┐
                                            │              GRAFANA                  │
                                            │  Metric panel → Exemplar → Trace      │
                                            │  Trace → Trace-to-logs → Log panel    │
                                            │  Alert → Trace correlation            │
                                            └───────────────────────────────────────┘

Day 41: Logging Architecture  ──────────────────────────────────────────────►┐
Day 42: OpenTelemetry Tracing ──────────────────────────────────────────────►│  Three Pillars
Day 39-40: Prometheus + Grafana ────────────────────────────────────────────►┘  Complete
                                                                                   │
                                                                                   ▼
                                                                          Day 43: SLI/SLO
                                                                          (sử dụng 3 pillars
                                                                           để đo error budget)
```

