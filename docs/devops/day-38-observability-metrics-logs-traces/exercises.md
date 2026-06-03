# Day 38: Exercises — Observability: Metrics, Logs, Traces

## Bài 1: Golden Signals Instrumentation (Easy)

### Context
Bạn là developer vừa join team Platform. Team yêu cầu mọi service mới phải expose Golden Signals metrics. Bạn cần instrument một HTTP API service đơn giản.

### Yêu cầu
1. Tạo một HTTP service (Go, Node.js, hoặc Python) với 2 endpoints: `/api/users` và `/api/orders`.
2. Instrument 4 Golden Signals:
   - **Latency**: Histogram cho request duration (buckets: 10ms, 50ms, 100ms, 250ms, 500ms, 1s).
   - **Traffic**: Counter cho total requests, label by method, path, status.
   - **Errors**: Dùng cùng counter với status label `5xx`.
   - **Saturation**: Gauge cho active connections.
3. Expose metrics tại `/metrics` endpoint (Prometheus format).
4. Simulate random latency (50-300ms) và random errors (5-10%).
5. Generate traffic và verify metrics bằng `curl`.

### Expected Outcome
- `/metrics` endpoint trả về Prometheus-format metrics.
- Counter tăng đúng khi có requests.
- Histogram ghi nhận latency distribution.
- Gauge phản ánh connections hiện tại.

### Hint
- Go: `github.com/prometheus/client_golang/prometheus`
- Node.js: `prom-client`
- Python: `prometheus_client`
- Test: `for i in $(seq 1 50); do curl -s localhost:8080/api/orders > /dev/null; done`
- Verify: `curl -s localhost:8080/metrics | grep http_requests_total`

### Acceptance Criteria
- [ ] Service chạy với 2+ endpoints.
- [ ] 4 Golden Signals metrics exposed.
- [ ] Metrics format đúng Prometheus convention (snake_case, _total suffix cho counter).
- [ ] Histogram có buckets phù hợp.
- [ ] Labels không chứa high-cardinality values (no user_id, request_id).
- [ ] `/health` endpoint cho liveness/readiness.

### Bonus Challenge
- Thêm `build_info` metric (gauge = 1) với labels: version, git_sha, go_version.
- Thêm Prometheus scrape config và verify trên Prometheus UI.
- So sánh histogram vs summary cho latency measurement.

---

## Bài 2: Structured Logging + Correlation (Medium)

### Context
Team bạn vừa trải qua incident mất 3 giờ debug vì logs unstructured và không có trace_id. CTO yêu cầu: "Từ giờ tất cả logs phải structured JSON, phải có trace_id, và phải correlate được với metrics."

### Yêu cầu
1. Tạo 2 services giao tiếp qua HTTP:
   - `api-gateway`: Nhận request, generate trace_id, gọi `order-service`.
   - `order-service`: Xử lý order, log kết quả.
2. Implement structured logging (JSON format) với fields bắt buộc:
   - `timestamp` (ISO 8601)
   - `level` (info, warn, error)
   - `service` (tên service)
   - `trace_id` (propagate qua HTTP header `X-Trace-Id`)
   - `span_id` (unique per service per request)
   - `method`, `path`
   - `duration_ms`
   - `status_code`
3. Propagate trace_id từ api-gateway → order-service qua HTTP header.
4. Log ở cả 2 services với cùng trace_id.
5. Simulate lỗi ở order-service (database timeout) và verify log correlation.
6. Deploy cả 2 services bằng Docker Compose.

### Expected Outcome
- Logs từ cả 2 services ở JSON format.
- Cùng request có cùng trace_id ở cả 2 services.
- Có thể grep trace_id để thấy full request flow.
- Error logs có đủ context để debug (error message, duration, which service).

### Hint
- Generate trace_id: UUID v4 hoặc random hex string.
- Propagate: `req.headers['x-trace-id']` hoặc `r.Header.Get("X-Trace-Id")`.
- Docker Compose: 2 services, api-gateway gọi order-service qua service name.
- Test correlation: `docker compose logs | grep <trace_id>`.

### Acceptance Criteria
- [ ] 2 services chạy và giao tiếp qua HTTP.
- [ ] Logs ở JSON format với tất cả required fields.
- [ ] trace_id propagate đúng giữa 2 services.
- [ ] `grep <trace_id>` trên combined logs hiển thị entries từ cả 2 services.
- [ ] Error log chứa error message, duration, stack trace (nếu có).
- [ ] Không log PII (password, email, credit card).
- [ ] Log level = INFO cho production, DEBUG cho development.

### Bonus Challenge
- Thêm service thứ 3 (payment-service) và verify trace correlation qua 3 services.
- Viết script parse logs và tạo "request timeline" (hiển thị duration ở mỗi service).
- Deploy Loki + Promtail và query logs bằng LogQL.
- Thêm metrics (counter) cho log levels: đếm info/warn/error per service.

---

## Bài 3: Full Observability Stack (Hard)

### Context
Bạn là DevOps Lead tại một e-commerce platform. Team vừa migrate từ monolith sang microservices (5 services). CEO phàn nàn: "Từ khi chuyển microservices, mọi incident mất gấp 3 lần thời gian resolve. Tôi cần biết health của hệ thống real-time."

Yêu cầu: Thiết kế và deploy observability stack đầy đủ three pillars cho 2 sample services.

### Yêu cầu

**Part A: Application Instrumentation**
1. Tạo 2 services với full instrumentation:
   - `order-service`: REST API, xử lý orders.
   - `payment-service`: gRPC hoặc REST, xử lý payments.
2. Mỗi service phải có:
   - Prometheus metrics: Golden Signals (4 metrics tối thiểu).
   - Structured JSON logging với trace_id correlation.
   - Health endpoint (`/health`, `/ready`).
3. Trace context propagation giữa 2 services.

**Part B: Observability Infrastructure**
4. Deploy observability stack bằng Docker Compose:
   - Prometheus (metrics collection).
   - Grafana (visualization).
   - Loki + Promtail (log aggregation) hoặc stdout-based.
5. Cấu hình Prometheus scrape cả 2 services.
6. Cấu hình Grafana data sources (Prometheus + Loki nếu có).

**Part C: Dashboards & Queries**
7. Tạo Grafana dashboard "Service Health Overview" với:
   - RPS per service (graph panel).
   - Error rate per service (graph panel + threshold).
   - p50/p90/p99 latency per service (graph panel).
   - Active connections (gauge panel).
8. Viết PromQL queries cho:
   - Top 5 endpoints by RPS.
   - Error rate trend last 1 hour.
   - Latency percentiles comparison (p50 vs p99).

**Part D: Incident Simulation**
9. Simulate incident: payment-service latency spike.
10. Document debug flow: Alert → Metric → Log → Root cause.
11. Viết "Observability Runbook" — khi nhận alert, làm gì step by step.

### Expected Outcome
- 2 services chạy với full instrumentation.
- Observability stack (Prometheus + Grafana + optional Loki) hoạt động.
- Dashboard hiển thị real-time health.
- Incident simulation + debug flow documented.

### Hint
- Docker Compose có thể chạy 5+ services cùng lúc.
- Prometheus scrape config dùng Docker service names.
- Grafana provisioning: mount dashboard JSON + datasource YAML vào container.
- Simulate latency spike: thêm random `sleep(2s)` trong payment-service sau khi receive flag.
- Loki Promtail config cần `docker_sd_configs` để auto-discover containers.

### Acceptance Criteria
- [ ] 2 services chạy với Golden Signals metrics.
- [ ] Structured logging với trace_id correlation.
- [ ] Prometheus scrape thành công (Targets page: all UP).
- [ ] Grafana dashboard có ≥ 4 panels (RPS, errors, latency, saturation).
- [ ] PromQL queries trả kết quả đúng.
- [ ] Incident simulation: latency spike visible trên dashboard.
- [ ] Debug flow documented: metric → log → root cause.
- [ ] Runbook có ≥ 5 bước cụ thể.
- [ ] Cleanup script xóa toàn bộ stack.

### Bonus Challenge
- Thêm Jaeger hoặc Tempo cho distributed tracing.
- Tạo dashboard "Request Flow" hiển thị trace waterfall.
- Implement SLO dashboard: error budget remaining, burn rate.
- Thêm alert rule: error rate > 5% → notification (console log hoặc webhook).
- Export Grafana dashboard as JSON và version control trong git.

---

## Solutions

<details>
<summary>Solution Bài 1: Golden Signals (Go)</summary>

```go
// main.go
package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"net/http"
	"os"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	requestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	requestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration",
			Buckets: []float64{0.01, 0.05, 0.1, 0.25, 0.5, 1.0},
		},
		[]string{"method", "path"},
	)

	activeConns = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "http_active_connections",
			Help: "Active HTTP connections",
		},
	)

	buildInfo = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "app_build_info",
			Help: "Build information",
		},
		[]string{"version", "git_sha"},
	)
)

func init() {
	buildInfo.WithLabelValues("1.0.0", "abc123d").Set(1)
}

func instrumentedHandler(path string, handler http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		activeConns.Inc()
		defer activeConns.Dec()

		// Simulate latency
		time.Sleep(time.Duration(50+rand.Intn(250)) * time.Millisecond)

		status := http.StatusOK
		if rand.Float64() < 0.08 {
			status = http.StatusInternalServerError
		}

		w.WriteHeader(status)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": status,
			"path":   path,
		})

		duration := time.Since(start).Seconds()
		requestsTotal.WithLabelValues(r.Method, path, fmt.Sprintf("%d", status)).Inc()
		requestDuration.WithLabelValues(r.Method, path).Observe(duration)
	}
}

func main() {
	http.Handle("/metrics", promhttp.Handler())
	http.HandleFunc("/api/users", instrumentedHandler("/api/users", nil))
	http.HandleFunc("/api/orders", instrumentedHandler("/api/orders", nil))
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
		fmt.Fprint(w, `{"status":"ok"}`)
	})

	fmt.Fprintf(os.Stderr, "Server starting on :8080\n")
	http.ListenAndServe(":8080", nil)
}
```

```bash
# Run
go run main.go &

# Generate traffic
for i in $(seq 1 100); do
  curl -s localhost:8080/api/orders > /dev/null
  curl -s localhost:8080/api/users > /dev/null
done

# Verify Golden Signals
echo "=== Traffic (Counter) ==="
curl -s localhost:8080/metrics | grep 'http_requests_total{'

echo "=== Latency (Histogram) ==="
curl -s localhost:8080/metrics | grep 'http_request_duration_seconds_bucket'

echo "=== Saturation (Gauge) ==="
curl -s localhost:8080/metrics | grep http_active_connections

echo "=== Build Info ==="
curl -s localhost:8080/metrics | grep app_build_info
```

</details>

<details>
<summary>Solution Bài 2: Structured Logging (Node.js)</summary>

```javascript
// api-gateway/index.js
const express = require('express');
const { v4: uuidv4 } = require('uuid');
const axios = require('axios');

const app = express();
const SERVICE = 'api-gateway';

function structuredLog(level, msg, fields = {}) {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    service: SERVICE,
    ...fields,
    message: msg,
  }));
}

app.get('/api/orders', async (req, res) => {
  const traceId = req.headers['x-trace-id'] || uuidv4();
  const spanId = uuidv4().substring(0, 8);
  const start = Date.now();

  structuredLog('info', 'Received order request', {
    trace_id: traceId, span_id: spanId,
    method: req.method, path: req.path,
  });

  try {
    const response = await axios.get('http://order-service:8081/api/process', {
      headers: { 'X-Trace-Id': traceId },
      timeout: 5000,
    });

    const duration = Date.now() - start;
    structuredLog('info', 'Order request completed', {
      trace_id: traceId, span_id: spanId,
      duration_ms: duration, status_code: 200,
    });

    res.json({ status: 'ok', trace_id: traceId, order: response.data });
  } catch (err) {
    const duration = Date.now() - start;
    structuredLog('error', 'Order request failed', {
      trace_id: traceId, span_id: spanId,
      duration_ms: duration, status_code: 500,
      error: err.message,
    });
    res.status(500).json({ status: 'error', trace_id: traceId });
  }
});

app.get('/health', (_, res) => res.json({ status: 'ok' }));
app.listen(8080, () => structuredLog('info', 'Server started', { port: 8080 }));
```

```javascript
// order-service/index.js
const express = require('express');
const { v4: uuidv4 } = require('uuid');

const app = express();
const SERVICE = 'order-service';

function structuredLog(level, msg, fields = {}) {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    service: SERVICE,
    ...fields,
    message: msg,
  }));
}

app.get('/api/process', async (req, res) => {
  const traceId = req.headers['x-trace-id'] || 'unknown';
  const spanId = uuidv4().substring(0, 8);
  const start = Date.now();

  // Simulate processing
  const delay = 50 + Math.random() * 200;
  await new Promise(r => setTimeout(r, delay));

  // Simulate 10% errors
  if (Math.random() < 0.1) {
    const duration = Date.now() - start;
    structuredLog('error', 'Database connection timeout', {
      trace_id: traceId, span_id: spanId,
      duration_ms: duration, status_code: 500,
      error: 'connection pool exhausted',
    });
    return res.status(500).json({ error: 'db timeout' });
  }

  const duration = Date.now() - start;
  structuredLog('info', 'Order processed', {
    trace_id: traceId, span_id: spanId,
    duration_ms: duration, status_code: 200,
    order_id: `ord-${Date.now()}`,
  });

  res.json({ status: 'processed', order_id: `ord-${Date.now()}` });
});

app.get('/health', (_, res) => res.json({ status: 'ok' }));
app.listen(8081, () => structuredLog('info', 'Server started', { port: 8081 }));
```

```yaml
# docker-compose.yaml
version: '3.8'
services:
  api-gateway:
    build: ./api-gateway
    ports: ["8080:8080"]
  order-service:
    build: ./order-service
    ports: ["8081:8081"]
```

```bash
# Test correlation
curl -s http://localhost:8080/api/orders | jq .trace_id
# Copy trace_id

docker compose logs 2>&1 | grep "<trace_id>"
# Should show logs from BOTH services with same trace_id
```

</details>

<details>
<summary>Solution Bài 3: Key Architecture (Docker Compose)</summary>

```yaml
# docker-compose.yaml
version: '3.8'

services:
  order-service:
    build: ./order-service
    ports: ["8080:8080"]
    environment:
      - PAYMENT_URL=http://payment-service:8081
    labels:
      - "logging=promtail"

  payment-service:
    build: ./payment-service
    ports: ["8081:8081"]
    labels:
      - "logging=promtail"

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards

  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log
      - ./promtail.yml:/etc/promtail/config.yml
      - /var/run/docker.sock:/var/run/docker.sock
    command: -config.file=/etc/promtail/config.yml
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'order-service'
    static_configs:
      - targets: ['order-service:8080']
  - job_name: 'payment-service'
    static_configs:
      - targets: ['payment-service:8081']
```

### Observability Runbook

```markdown
## Alert: Error Rate > 5%

1. Open Grafana dashboard "Service Health"
2. Identify which service has high error rate
3. Check error rate trend: sudden spike or gradual increase?
4. Open Prometheus, query:
   sum(rate(http_requests_total{status=~"5.."}[5m])) by (service, path)
5. Identify affected endpoint
6. Query logs (Loki/grep):
   {service="<name>"} |= "error" | json | duration_ms > 1000
7. Look for trace_id in error logs
8. If trace available, check trace waterfall for bottleneck
9. Common causes:
   - Database timeout → check DB connections
   - Downstream service failure → check dependency health
   - OOM → check resource usage
10. Mitigate: restart pods, scale up, or rollback if bad deploy
```

</details>

