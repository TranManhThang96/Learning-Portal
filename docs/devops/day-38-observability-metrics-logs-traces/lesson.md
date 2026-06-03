# Day 38: Observability — Metrics, Logs, Traces

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt rõ monitoring vs observability** — hiểu vì sao monitoring truyền thống không đủ cho hệ thống phân tán hiện đại.
2. **Hiểu sâu three pillars of observability**: Metrics, Logs, Traces — vai trò, đặc điểm, và khi nào dùng pillar nào.
3. **Áp dụng được Golden Signals** (latency, traffic, errors, saturation) để thiết kế observability cho bất kỳ service nào.
4. **Implement được structured logging, Prometheus metrics, và basic tracing** trong một service đơn giản.
5. **Hiểu được correlation** giữa metrics/logs/traces — từ alert → metric → trace → log → root cause.

---

## 2. Bối cảnh & Động lực

### Monitoring vs Observability

**Monitoring** trả lời: "Hệ thống có đang hoạt động không?" → Known unknowns.
**Observability** trả lời: "Vì sao hệ thống hoạt động như vậy?" → Unknown unknowns.

```
Monitoring (truyền thống):
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ CPU > 80%│     │ Disk > 90│     │ Ping fail│
  │ → Alert  │     │ → Alert  │     │ → Alert  │
  └──────────┘     └──────────┘     └──────────┘
  
  Problem: Biết CPU cao, nhưng KHÔNG biết vì sao.
  
Observability (hiện đại):
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Metrics  │ ←──→│  Traces  │←──→ │   Logs   │
  │ (what)   │     │ (where)  │     │  (why)   │
  └──────────┘     └──────────┘     └──────────┘
  
  Flow: Error rate tăng (metric) → Trace nào bị lỗi? (trace) 
        → Service nào trong trace? → Error message là gì? (log)
```

### Vì sao topic này quan trọng?

Trong hệ thống monolith, debug tương đối đơn giản: 1 server, 1 log file, 1 process. Nhưng trong microservices:

- **1 request đi qua 5-10 services** — lỗi ở service nào?
- **100 instances chạy đồng thời** — instance nào bị vấn đề?
- **Lỗi xảy ra 0.1% requests** — không thể reproduce trên local.
- **Cascading failure** — service A chậm → service B timeout → service C error.

Không có observability = **debug mù**: ssh vào từng server, grep log, đoán nguyên nhân, mất hàng giờ thay vì vài phút.

### Nếu không có observability

- **MTTR tăng 5-10x**: Incident 10 phút → 1-2 giờ vì không biết bắt đầu debug từ đâu.
- **Finger pointing**: "Không phải service tôi" — không ai chứng minh được.
- **Reactive only**: Chỉ biết lỗi khi user phàn nàn, không phải khi metric báo.
- **No capacity planning**: Không biết service nào cần scale, khi nào cần scale.

### Liên hệ với developer

- **Metrics** giống **unit test assertions** — kiểm tra "system behavior có đúng không?" liên tục.
- **Logs** giống **console.log/debug output** — chi tiết what happened tại một thời điểm.
- **Traces** giống **stack trace** nhưng across services — biết request đi qua đâu, mất bao lâu ở mỗi service.
- **Correlation** giống **debugger** — follow execution flow từ đầu đến cuối.

---

## 3. Kiến thức nền tảng

### 3.1 Three Pillars of Observability

| Pillar | Định nghĩa | Trả lời câu hỏi | Ví dụ |
|--------|-----------|-----------------|-------|
| **Metrics** | Số liệu đo lường theo thời gian (time series) | What is happening? How much? | RPS = 500, Error rate = 2%, p99 = 200ms |
| **Logs** | Events rời rạc tại một thời điểm | What exactly happened? | `{"level":"error","msg":"db connection timeout","service":"order","trace_id":"abc123"}` |
| **Traces** | Theo dõi request xuyên suốt nhiều services | Where did the request go? How long at each hop? | Request → API Gateway (5ms) → Order Service (50ms) → Payment (200ms) → DB (150ms) |

### 3.2 Golden Signals (Google SRE)

4 signals quan trọng nhất để đo bất kỳ service nào:

| Signal | Mô tả | Metric ví dụ | Alert khi |
|--------|-------|-------------|-----------|
| **Latency** | Thời gian xử lý request | `http_request_duration_seconds` | p99 > 500ms |
| **Traffic** | Lượng demand trên system | `http_requests_total` (RPS) | RPS drop > 50% |
| **Errors** | Tỷ lệ request thất bại | `http_requests_total{status=~"5.."}` | Error rate > 1% |
| **Saturation** | Mức độ "đầy" của resource | CPU usage, memory, queue depth | CPU > 80% sustained |

### 3.3 RED Method (cho microservices)

Phù hợp cho request-driven services (API, web):

- **R**ate: Số requests per second.
- **E**rrors: Số requests bị lỗi per second.
- **D**uration: Distribution thời gian xử lý (histogram/percentiles).

### 3.4 USE Method (cho infrastructure)

Đã học ở Day 4, tóm tắt lại:

- **U**tilization: % resource đang dùng.
- **S**aturation: Queue length, work waiting.
- **E**rrors: Số errors trên resource.

### 3.5 Structured Logging vs Unstructured Logging

```
Unstructured (BAD):
  2024-01-15 10:23:45 ERROR OrderService - Failed to process order 12345 for user john@example.com

Structured (GOOD):
  {
    "timestamp": "2024-01-15T10:23:45.123Z",
    "level": "error",
    "service": "order-service",
    "message": "Failed to process order",
    "order_id": "12345",
    "user_id": "u-789",
    "trace_id": "abc123def456",
    "span_id": "span-789",
    "error": "database connection timeout",
    "duration_ms": 5023
  }
```

Tại sao structured logging quan trọng?
- **Searchable**: `service=order-service AND level=error AND order_id=12345`.
- **Parseable**: Tools (Loki, ELK) parse tự động.
- **Correlatable**: `trace_id` kết nối log với trace.
- **Aggregatable**: Đếm errors per service, per endpoint.

### 3.6 Cardinality

**Cardinality** = số lượng unique time series. Mỗi combination labels tạo 1 time series.

```
# Low cardinality (TỐT)
http_requests_total{method="GET", status="200"}        → 1 series
http_requests_total{method="POST", status="201"}       → 1 series
# Total: ~20 series (few methods × few status codes)

# High cardinality (NGUY HIỂM)
http_requests_total{method="GET", user_id="user-001"}  → 1 series
http_requests_total{method="GET", user_id="user-002"}  → 1 series
...
http_requests_total{method="GET", user_id="user-1000000"} → 1 series
# Total: MILLIONS of series → Prometheus OOM!
```

**Rule of thumb**: Không dùng unbounded values (user ID, request ID, IP address) làm metric labels. Những giá trị đó thuộc về logs và traces, không phải metrics.

---

## 4. Deep Dive

### 4.1 Observability Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐      │
│  │ Prometheus   │  │ Structured   │  │ OpenTelemetry  │      │
│  │ Client Lib   │  │ Logger       │  │ SDK            │      │
│  │              │  │              │  │                 │      │
│  │ counter()    │  │ log.info()   │  │ span.start()   │      │
│  │ histogram()  │  │ log.error()  │  │ span.end()     │      │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘      │
│         │                  │                   │               │
└─────────┼──────────────────┼───────────────────┼──────────────┘
          │                  │                   │
          ▼                  ▼                   ▼
┌─────────────────┐ ┌───────────────┐ ┌─────────────────────┐
│   Prometheus     │ │  Log Agent    │ │  OTel Collector     │
│   (pull /metrics)│ │  (Promtail/   │ │  (receive, process, │
│                   │ │   Fluentd)    │ │   export)           │
└────────┬──────────┘ └──────┬────────┘ └─────────┬───────────┘
         │                   │                     │
         ▼                   ▼                     ▼
┌─────────────────┐ ┌───────────────┐ ┌─────────────────────┐
│   Prometheus     │ │  Loki / ELK  │ │  Jaeger / Tempo     │
│   TSDB           │ │  (storage)   │ │  (trace storage)    │
└────────┬──────────┘ └──────┬────────┘ └─────────┬───────────┘
         │                   │                     │
         └───────────────────┼─────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Grafana       │
                    │  (visualization) │
                    │                   │
                    │  Dashboard        │
                    │  Alerting         │
                    │  Correlation      │
                    └─────────────────┘
```

### 4.2 Metric Types (Prometheus)

| Type | Mô tả | Use case | Ví dụ |
|------|-------|----------|-------|
| **Counter** | Chỉ tăng (hoặc reset về 0) | Đếm events | `http_requests_total`, `errors_total` |
| **Gauge** | Tăng hoặc giảm | Giá trị hiện tại | `temperature`, `active_connections`, `queue_size` |
| **Histogram** | Đo distribution values | Latency percentiles | `http_request_duration_seconds` |
| **Summary** | Giống Histogram, tính percentile phía client | Latency (ít dùng) | `rpc_duration_seconds` |

**Histogram vs Summary**:

| | Histogram | Summary |
|--|-----------|---------|
| Percentile tính ở | Server-side (PromQL) | Client-side |
| Aggregatable | ✅ Across instances | ❌ Không |
| Accuracy | Phụ thuộc bucket config | Chính xác hơn |
| **Recommendation** | ✅ Dùng histogram | ⚠️ Chỉ khi cần exact percentile |

### 4.3 Trace Anatomy

```
Trace ID: abc-123-def-456
├── Span: API Gateway (5ms)
│   ├── Span: Auth Middleware (2ms)
│   └── Span: Route Handler (3ms)
│       └── Span: Order Service (HTTP call) (250ms)
│           ├── Span: Validate Input (5ms)
│           ├── Span: Database Query (150ms)
│           │   ├── Span: Connection Pool Wait (50ms)
│           │   └── Span: SQL Execute (100ms)
│           └── Span: Payment Service (gRPC call) (80ms)
│               ├── Span: Charge Card (60ms)
│               └── Span: Send Receipt (20ms)
└── Total Duration: 255ms
```

**Context Propagation**: Trace ID được truyền qua HTTP headers (`traceparent`, `X-B3-TraceId`) hoặc gRPC metadata → mỗi service tạo span mới với cùng trace ID.

### 4.4 Correlation — Kết nối 3 Pillars

```
Alert: Error rate > 5% on order-service
  │
  ▼ (Metrics → Which endpoint?)
Metric: http_requests_total{service="order-service", path="/api/orders", status="500"}
  Rate: 50 errors/min (normally 2/min)
  │
  ▼ (Metrics → Traces: find failing traces)
Trace: abc-123 (duration: 5200ms, status: ERROR)
  → order-service: 5200ms
    → payment-service: 5100ms (TIMEOUT)
      → database query: 5000ms (SLOW)
  │
  ▼ (Trace → Logs: get details)
Log: {
  "trace_id": "abc-123",
  "service": "payment-service",
  "level": "error",
  "message": "database connection pool exhausted",
  "active_connections": 50,
  "max_connections": 50,
  "wait_queue": 200
}
  │
  ▼ (Root Cause)
Database connection pool full → queries queue up → timeout cascade
```

### 4.5 Observability Data Characteristics

| | Metrics | Logs | Traces |
|--|---------|------|--------|
| **Volume** | Thấp (aggregated) | Rất cao | Cao (phải sample) |
| **Retention** | Dài (months-years) | Medium (weeks-months) | Ngắn (days-weeks) |
| **Cost** | Thấp | Cao | Medium-Cao |
| **Query speed** | Rất nhanh | Chậm (full-text search) | Medium |
| **Dùng cho** | Alert, dashboard | Debug, audit | Request flow analysis |
| **Cardinality concern** | ⚠️ Label explosion | ❌ Không | ❌ Không |
| **Sampling** | Không cần | Có thể | Thường cần |

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Build vs Buy

| | Self-hosted (OSS) | Managed (SaaS) |
|--|-------------------|----------------|
| **Stack** | Prometheus + Loki + Tempo + Grafana | Datadog, New Relic, Grafana Cloud |
| **Cost** | Infra cost + engineering time | Subscription (thường đắt khi scale) |
| **Control** | Full control, full responsibility | Limited control, managed by vendor |
| **Scale effort** | Phải tự scale, tune, maintain | Vendor handles |
| **Vendor lock-in** | Không | Cao |
| **Best for** | Mid-size+ teams với DevOps experience | Startup nhanh, teams nhỏ |

### 5.2 Theo scenario

**Startup (< 20 engineers)**:
- Managed: Datadog hoặc Grafana Cloud free tier.
- Hoặc minimal: Prometheus + Grafana (simple stack).
- Focus: Golden Signals cho critical services.
- Logs: stdout → cloud logging (AWS CloudWatch, GCP Logging).
- Traces: skip ban đầu hoặc basic Jaeger.

**Mid-size (20-100 engineers)**:
- Self-hosted: Prometheus + Loki + Tempo + Grafana.
- Hoặc Grafana Cloud (managed, OSS-compatible).
- Full three pillars.
- Structured logging enforced.
- Sampling traces ở 10-20%.

**Enterprise (100+ engineers)**:
- Prometheus + Thanos/Mimir (long-term storage).
- Loki hoặc ELK cho logs.
- Tempo hoặc Jaeger cho traces.
- OpenTelemetry Collector cho unified ingestion.
- Dedicated observability team.
- Custom dashboards per team.
- SLO-based alerting.

### 5.3 Anti-patterns

1. **Metric explosion**: Thêm user_id, request_id làm metric label → Prometheus OOM.
2. **Log flooding**: Log every request body → storage cost tăng 10x, search chậm.
3. **Trace everything**: 100% sampling → trace storage full, query chậm.
4. **Dashboard overload**: 50 panels trên 1 dashboard → ai cũng ignore vì quá nhiều thông tin.
5. **Alert on everything**: 200 alert rules → alert fatigue → miss real incidents.
6. **No correlation**: Metrics, logs, traces riêng rẽ → không kết nối được → debug vẫn chậm.
7. **Observability as afterthought**: Thêm observability sau khi deploy production → phải redeploy tất cả services.

### 5.4 Best Practices

- **Start with Golden Signals**: Latency, Traffic, Errors, Saturation — đủ cho hầu hết services.
- **Structured logging from day 1**: Enforce JSON format, include trace_id, service name.
- **Use OpenTelemetry**: Vendor-neutral, tránh lock-in, unified API cho metrics/logs/traces.
- **Sample traces intelligently**: 100% cho errors, 10% cho success, head-based hoặc tail-based sampling.
- **Correlate**: Đảm bảo trace_id xuất hiện trong cả metrics labels, log fields, và trace attributes.
- **Define naming conventions**: `http_requests_total`, `http_request_duration_seconds` — consistent across services.

---

## 6. Performance & Scalability ⭐

### 6.1 Instrumentation Overhead

| Instrumentation | CPU Overhead | Memory Overhead | Latency Impact |
|-----------------|-------------|----------------|---------------|
| Prometheus counter/gauge | Negligible | ~100 bytes/series | < 1μs per operation |
| Prometheus histogram | Low | ~3KB/histogram (default buckets) | < 5μs |
| Structured logging | Low | Depends on verbosity | 5-50μs per log entry |
| OpenTelemetry tracing | Medium | ~500 bytes/span | 10-100μs per span |
| Full OTel (metrics+logs+traces) | Medium | ~2-5MB per service | 20-200μs per request |

### 6.2 Cost Management

| Pillar | Cost driver | Optimization |
|--------|------------|-------------|
| Metrics | Cardinality (number of time series) | Drop high-cardinality labels, use recording rules |
| Logs | Volume (GB/day) | Log levels, sampling, drop debug in prod |
| Traces | Volume × retention | Sampling rate, shorter retention, tail-based sampling |

### 6.3 Scaling Bottlenecks

- **Prometheus**: Single-server bottleneck ở ~10M active time series. Giải pháp: federation, Thanos, Mimir.
- **Loki**: Label cardinality ảnh hưởng query performance. Giải pháp: limit labels, use structured metadata.
- **Jaeger/Tempo**: Storage grows linearly with traffic. Giải pháp: aggressive sampling, tiered storage.
- **Grafana**: Dashboard load time khi query nhiều data sources. Giải pháp: recording rules, caching.

---

## 7. Security & Reliability Considerations

### 7.1 Security

- **PII trong logs**: Không log password, credit card, email, phone number. Mask hoặc redact.
- **PII trong traces**: Span attributes có thể chứa user data → sanitize trước khi send.
- **Access control**: Không phải ai cũng cần xem tất cả logs/metrics. RBAC trên Grafana.
- **Log retention**: Compliance yêu cầu (GDPR: right to be forgotten vs audit log retention).
- **Network**: Observability data nên đi qua internal network, không expose ra internet.

### 7.2 Reliability

- **Observability phải reliable hơn system nó monitor**: Nếu Prometheus down khi incident → mù hoàn toàn.
- **HA cho core components**: Prometheus HA (2 replicas), Grafana HA, AlertManager cluster.
- **Buffering**: Log agent phải buffer locally khi backend unavailable → không mất logs.
- **Graceful degradation**: Nếu tracing backend down → app vẫn chạy bình thường, chỉ mất traces.

---

## 8. Hands-on Example

### 8.1 Sample Application với Metrics + Logs + Traces

Tạo một Go service đơn giản expose đầy đủ three pillars:

```bash
mkdir -p /tmp/observability-lab && cd /tmp/observability-lab
```

**File: `go.mod`**

```go
module observability-lab

go 1.22

require github.com/prometheus/client_golang v1.19.0
```

**File: `main.go`**

```go
package main

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"net/http"
	"os"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: []float64{0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0},
		},
		[]string{"method", "path"},
	)

	activeConnections = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "http_active_connections",
			Help: "Number of active HTTP connections",
		},
	)
)

func init() {
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
	prometheus.MustRegister(activeConnections)
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	http.Handle("/metrics", promhttp.Handler())
	http.HandleFunc("/api/orders", ordersHandler)
	http.HandleFunc("/health", healthHandler)

	slog.Info("server starting", "port", 8080)
	if err := http.ListenAndServe(":8080", nil); err != nil {
		slog.Error("server failed", "error", err)
		os.Exit(1)
	}
}

func ordersHandler(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	activeConnections.Inc()
	defer activeConnections.Dec()

	traceID := r.Header.Get("X-Trace-Id")
	if traceID == "" {
		traceID = fmt.Sprintf("trace-%d", rand.Int63())
	}

	// Simulate processing
	delay := time.Duration(50+rand.Intn(200)) * time.Millisecond
	time.Sleep(delay)

	// Simulate random errors (10% error rate)
	status := http.StatusOK
	if rand.Float64() < 0.1 {
		status = http.StatusInternalServerError
		slog.Error("order processing failed",
			"trace_id", traceID,
			"method", r.Method,
			"path", r.URL.Path,
			"duration_ms", time.Since(start).Milliseconds(),
			"error", "database connection timeout",
		)
	} else {
		slog.Info("order processed successfully",
			"trace_id", traceID,
			"method", r.Method,
			"path", r.URL.Path,
			"duration_ms", time.Since(start).Milliseconds(),
		)
	}

	duration := time.Since(start).Seconds()
	httpRequestsTotal.WithLabelValues(r.Method, "/api/orders", fmt.Sprintf("%d", status)).Inc()
	httpRequestDuration.WithLabelValues(r.Method, "/api/orders").Observe(duration)

	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":   status,
		"trace_id": traceID,
	})
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
```

**File: `Dockerfile`**

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/app .

FROM alpine:3.20
RUN addgroup -g 1001 appgroup && \
    adduser -u 1001 -G appgroup -s /bin/sh -D appuser
USER appuser
COPY --from=builder /out/app /app
EXPOSE 8080
ENTRYPOINT ["/app"]
```

```bash
go mod tidy
```

### 8.2 Docker Compose Stack

```yaml
# docker-compose.yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:8080"
    labels:
      - "prometheus.io/scrape=true"
      - "prometheus.io/port=8080"
      - "prometheus.io/path=/metrics"

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=1d'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_AUTH_ANONYMOUS_ENABLED=true
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  grafana-data:
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['app:8080']
    metrics_path: /metrics
```

### 8.3 Chạy và test

```bash
# Start stack
docker compose up -d

# Generate traffic
for i in $(seq 1 100); do
  curl -s http://localhost:8080/api/orders > /dev/null
  sleep 0.1
done

# Kiểm tra metrics
curl -s http://localhost:8080/metrics | grep http_requests_total
# Expected:
# http_requests_total{method="GET",path="/api/orders",status="200"} 90
# http_requests_total{method="GET",path="/api/orders",status="500"} 10

# Kiểm tra logs (structured JSON)
docker compose logs app | tail -5
# Expected:
# {"time":"2024-01-15T10:23:45Z","level":"INFO","msg":"order processed successfully",
#  "trace_id":"trace-123456","method":"GET","path":"/api/orders","duration_ms":120}

# Truy cập Prometheus UI
# http://localhost:9090
# Query: rate(http_requests_total[1m])
# Query: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Truy cập Grafana
# http://localhost:3000 (admin/admin)
# Add Prometheus data source: http://prometheus:9090
```

### 8.4 PromQL Queries cơ bản

```promql
# RPS (Requests Per Second)
rate(http_requests_total[1m])

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# p99 latency
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# Active connections
http_active_connections
```

### 8.5 Cleanup

```bash
docker compose down -v
cd /tmp && rm -rf /tmp/observability-lab
```

### 8.6 Verify checklist

- [ ] App expose metrics tại `/metrics`
- [ ] Counter `http_requests_total` tăng khi gọi API
- [ ] Histogram `http_request_duration_seconds` ghi nhận latency distribution
- [ ] Gauge `http_active_connections` hiển thị connections hiện tại
- [ ] Logs ở structured JSON format với trace_id
- [ ] Prometheus scrape metrics thành công
- [ ] PromQL queries trả kết quả đúng
- [ ] Grafana connect được Prometheus data source

---

## 9. Common Pitfalls & Debugging

### 9.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| Prometheus "no data" | Service chưa expose /metrics hoặc scrape config sai | Check `curl localhost:8080/metrics`, verify prometheus.yml |
| Metric cardinality explosion | Dùng user_id, request_id làm label | Remove high-cardinality labels, di chuyển vào logs |
| Log flooding | Debug level trong production | Set log level = INFO/WARN cho production |
| Missing trace_id trong logs | Không propagate trace context | Thêm middleware extract trace_id từ header |
| Grafana "no data" | Data source URL sai | Dùng service name (container network) thay vì localhost |
| Prometheus OOM | Quá nhiều time series | Reduce cardinality, increase memory, use recording rules |

### 9.2 Debug commands

```bash
# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {instance, health}'

# Check metric exists
curl -s http://localhost:9090/api/v1/label/__name__/values | jq

# Check series count (cardinality)
curl -s http://localhost:9090/api/v1/status/tsdb | jq '.data.seriesCountByMetricName[:10]'

# Check app metrics endpoint
curl -s http://localhost:8080/metrics | head -20

# Check log output format
docker logs <container> 2>&1 | python3 -m json.tool
```

### 9.3 Production Case Study: The Blind Incident

**Context**: Một fintech startup (30 engineers, 500K users) chạy 15 microservices trên Kubernetes. Monitoring: chỉ có uptime check (ping endpoint) và AWS CloudWatch basic metrics.

**Symptom**: Users báo "checkout chậm" lúc 14:00. Uptime check: tất cả services UP. CloudWatch CPU/Memory: bình thường.

**Investigation**:
- Team SSH vào từng pod, grep log → mất 45 phút.
- Phát hiện payment-service log: "timeout connecting to payment gateway".
- Nhưng vì sao timeout? Payment gateway up, network ok.
- SSH vào logs sâu hơn: order-service gọi payment-service 5 lần retry per request.
- Mỗi retry = 30s timeout → 1 request = 150s.
- Payment gateway rate limit: 100 req/s → bị rate limited vì retry storm.

**Root Cause**: Payment gateway latency tăng nhẹ (200ms → 500ms) → order-service retry → retry storm → payment gateway rate limit → toàn bộ payments fail.

**MTTR**: 2 giờ 15 phút (chỉ vì không có observability).

**Long-term Fix**:
1. Thêm Prometheus + Grafana → alert khi p99 latency > 1s.
2. Structured logging với trace_id → correlate logs across services.
3. Thêm distributed tracing → thấy retry chain ngay lập tức.
4. Thêm circuit breaker trên payment-service (Day 46).
5. Dashboard RED metrics cho mỗi service.

**Nếu có observability từ đầu**: MTTR ước tính 10-15 phút thay vì 2 giờ 15 phút.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước
- **Day 4**: Linux Performance & Debugging Tools — USE method, system-level monitoring.
- **Day 35-37**: CI/CD & Release Engineering — deployment pipeline cần observability để validate deployments.
- **Day 36**: Progressive delivery analysis dựa trên metrics từ observability stack.

### Bài sau
- **Day 39**: Prometheus & PromQL — deep dive vào metrics collection và query language.
- **Day 40**: Grafana Dashboard & Alerting — visualization và alert rules.
- **Day 41**: Logging Architecture (Loki vs ELK) — deep dive vào log management.
- **Day 42**: OpenTelemetry & Distributed Tracing — deep dive vào tracing.
- **Day 43**: SLI/SLO, Error Budget — dùng observability data để define service level objectives.

Day 38 là foundation — giới thiệu tổng quan. Days 39-43 deep dive từng pillar và áp dụng vào production.

---

## 11. Tài liệu tham khảo

### Must-read
- [Google SRE Book - Chapter 6: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [Distributed Systems Observability - Cindy Sridharan (O'Reilly free ebook)](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)

### Nice-to-have
- [The Three Pillars of Observability](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/ch04.html)
- [Prometheus Best Practices - Naming](https://prometheus.io/docs/practices/naming/)
- [Structured Logging Best Practices](https://www.honeycomb.io/blog/structured-logging-and-your-team)

### Deep-dive
- [Observability Engineering - Charity Majors, Liz Fong-Jones (O'Reilly)](https://www.oreilly.com/library/view/observability-engineering/9781492076438/)
- [Google Dapper Paper (Distributed Tracing origin)](https://research.google/pubs/pub36356/)
- [Cardinality is Key - Prometheus cardinality deep dive](https://www.robustperception.io/cardinality-is-key/)

