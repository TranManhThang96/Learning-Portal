# Day 41: Exercises — Logging Architecture (Loki vs ELK vs Splunk)

---

## Exercise 1 (Easy): Deploy Loki Stack và Query Logs cơ bản

### Context

Bạn vừa join một team startup sử dụng Docker Compose. Team chưa có centralized logging. Nhiệm vụ của bạn là dựng Loki stack cơ bản và verify rằng logs được collect.

### Requirements

1. Dựng Loki + Promtail + Grafana bằng Docker Compose (dùng config từ lesson).
2. Tạo một file log giả lập (`fake-app.log`) với định dạng JSON structured logging.
3. Cấu hình Promtail để scrape file đó.
4. Verify logs xuất hiện trong Grafana Explore bằng LogQL.
5. Viết ít nhất 3 LogQL queries:
   - Xem toàn bộ logs từ job `fake-app`
   - Filter chỉ logs có `level=error`
   - Count số log entries mỗi phút (rate)

### Expected Outcome

```
Grafana Explore → query {job="fake-app"} → hiện ít nhất 10 log entries
Loki API:
$ curl "http://localhost:3100/loki/api/v1/label/job/values"
{"status":"success","data":["fake-app","...others..."]}

Log count (phải > 0):
$ curl "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query=count_over_time({job="fake-app"}[1h])' | jq .
```

### Hint

- Tạo fake logs bằng bash loop:
  ```bash
  for i in {1..20}; do
    LEVEL=$([ $((RANDOM % 5)) -eq 0 ] && echo "error" || echo "info")
    echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"level\":\"$LEVEL\",\"service\":\"fake-app\",\"message\":\"Processing request $i\",\"request_id\":\"req-$i\"}" >> fake-app.log
  done
  ```
- Mount `fake-app.log` vào container Promtail `/var/log/fake-app/app.log`
- Trong Promtail config: `__path__: /var/log/fake-app/*.log`

### Acceptance Criteria

- [ ] `docker-compose ps` hiển thị loki, promtail, grafana đang running
- [ ] `curl http://localhost:3100/ready` trả về `OK`
- [ ] Grafana Explore: `{job="fake-app"}` trả về >= 10 log entries
- [ ] Grafana Explore: `{job="fake-app", level="error"}` trả về chỉ error entries
- [ ] `{job="fake-app"} | json | duration_ms > 0` hoạt động nếu field đó có trong logs

### Bonus Challenge

Thêm một second job `fake-db` vào Promtail scrape config (log giả lập database query logs). Sau đó viết một query tổng hợp:
```
sum by (job) (count_over_time({job=~"fake-app|fake-db"}[5m]))
```

---

## Exercise 2 (Medium): Implement Correlation ID Tracing

### Context

Team của bạn có một hệ thống microservices: `api-gateway` → `user-service` → `order-service`. Mỗi service log ra riêng. Khi có lỗi, bạn phải mở 3 terminal khác nhau, tìm theo timestamp thủ công. Nhiệm vụ: implement correlation ID để có thể trace một request qua toàn bộ 3 services chỉ với một LogQL query.

### Requirements

1. Viết 3 microservices (Go hoặc Node.js) mô phỏng flow: `api-gateway` → `user-service` → `order-service`
2. Mỗi service:
   - Nhận `X-Request-ID` header (nếu không có thì tạo UUID mới)
   - Pass header này forward tới service kế tiếp
   - Log mọi request/response với field `request_id`
   - Log bằng JSON (structured logging)
3. Deploy 3 services + Loki stack bằng Docker Compose
4. Generate traffic: `curl -H "X-Request-ID: my-test-123" http://localhost:8080/place-order`
5. Query Loki để xem toàn bộ lifecycle của request `my-test-123`

### Expected Outcome

```
$ curl -H "X-Request-ID: my-test-123" http://localhost:8080/place-order
{"order_id":"uuid-xyz","status":"created"}

# LogQL query trong Grafana:
{job=~"api-gateway|user-service|order-service"} | json | request_id = "my-test-123"

# Expected output (theo chronological order):
14:00:01 api-gateway  INFO  "Received request"      {request_id: "my-test-123"}
14:00:01 api-gateway  INFO  "Forwarding to user-svc" {request_id: "my-test-123"}
14:00:01 user-service INFO  "Validating user"        {request_id: "my-test-123"}
14:00:01 user-service INFO  "User valid, returning"  {request_id: "my-test-123"}
14:00:01 api-gateway  INFO  "User validated, forward to orders" {request_id: "my-test-123"}
14:00:01 order-service INFO "Creating order"         {request_id: "my-test-123"}
14:00:01 order-service INFO "Order persisted"        {request_id: "my-test-123"}
14:00:01 api-gateway  INFO  "Response sent"          {request_id: "my-test-123"}
```

### Hint

**Go HTTP client with header propagation:**
```go
func callService(ctx context.Context, url string, reqID string) (*http.Response, error) {
    req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
    req.Header.Set("X-Request-ID", reqID)
    return http.DefaultClient.Do(req)
}
```

**JSON structured logger (zerolog):**
```go
log.Info().
    Str("request_id", reqID).
    Str("service", "api-gateway").
    Str("action", "forward_to_user_service").
    Int("status", resp.StatusCode).
    Int64("duration_ms", time.Since(start).Milliseconds()).
    Msg("Upstream call completed")
```

**Promtail config cho multiple services:**
```yaml
scrape_configs:
  - job_name: api-gateway
    static_configs:
      - targets: [localhost]
        labels:
          job: api-gateway
          __path__: /var/log/api-gateway/*.log
  - job_name: user-service
    ...
  - job_name: order-service
    ...
```

**LogQL để tìm tất cả errors trong cả 3 services cùng lúc:**
```
{job=~"api-gateway|user-service|order-service"} | json | level = "error"
```

### Acceptance Criteria

- [ ] 3 services running với logs JSON format
- [ ] `X-Request-ID` được forward qua tất cả services
- [ ] Tất cả services log `request_id` field
- [ ] Query `{job=~".*-service|api-gateway"} | json | request_id = "my-test-123"` trả về >= 5 entries từ các services khác nhau
- [ ] Các log entries được sorted theo timestamp (chronological order)
- [ ] Có thể phân biệt entries từ service nào qua `job` label

### Bonus Challenge

Implement một **error injection**: khi request header `X-Force-Error: true` được gửi, `order-service` trả về lỗi 500. Sau đó dùng LogQL để:
1. Đếm error rate: `sum(rate({job="order-service"} |= "error"[5m]))`
2. Phân tích latency distribution của error vs success: `histogram_quantile(0.99, ...)`
3. Viết Loki recording rule để pre-compute error rate metric

---

## Exercise 3 (Hard): Sensitive Data Redaction Pipeline + Cost Optimization

### Context

Bạn là Security Engineer + DevOps lead tại một fintech company. Yêu cầu:
1. Services đang vô tình log sensitive data (email, card number, JWT token).
2. Log volume đang 150GB/ngày, bill S3 quá cao.
3. Cần implement redaction pipeline và tiered retention.

### Requirements

#### Part A: Sensitive Data Redaction

1. Viết một service có bug — intentionally log sensitive data:
   ```
   - User email: user@example.com
   - Credit card: 4111111111111111
   - JWT bearer token: eyJhbGciOiJIUzI1NiIs...
   - API key: sk-prod-xxxxxxxxxxxxxx
   ```

2. Implement Promtail pipeline stages để:
   - Redact email → `u***@***.com`
   - Redact credit card → `**** **** **** 1111` (giữ 4 số cuối)
   - Redact JWT token → `[JWT_REDACTED]`
   - Redact API key `sk-prod-*` → `[API_KEY_REDACTED]`

3. Verify bằng cách query Loki: sensitive data KHÔNG được xuất hiện trong raw logs.

4. Implement một alternative approach: Application-level sanitization trong Go — viết một `sanitizeFields()` function xử lý trước khi log.

#### Part B: Retention Policy & Cost Optimization

1. Cấu hình Loki với **multi-tier retention**:
   - Hot: 7 ngày (local disk)
   - Warm: 30 ngày (object store với Infrequent Access class)
   - Archive: 365 ngày (object store với Glacier/Archive class)

2. Implement **log sampling** cho high-volume, low-value logs:
   - Health check logs (`/health`, `/readiness`): chỉ giữ 1% (sampling)
   - Success logs (2xx): giữ 10%
   - Error logs (4xx, 5xx): giữ 100%

3. Tính toán và báo cáo cost estimate:
   - Baseline: 150GB/ngày không filter
   - After sampling: Giảm xuống còn bao nhiêu GB/ngày?
   - Estimate monthly S3 cost trước và sau

4. Viết một script kiểm tra log volume bằng Loki API:
   ```bash
   # Query volume per job
   curl ... | jq "volume breakdown"
   ```

### Expected Outcome

**Part A — Redaction:**
```bash
# Gửi request có sensitive data
curl -H "X-User-Email: alice@company.com" \
     -H "X-Card: 4111111111111111" \
     http://localhost:8080/payment

# Query Loki — KHÔNG được thấy raw sensitive data
$ curl "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={job="fintech-api"}' \
  | grep -i "4111111111111111"
# Expected: NO output (card number redacted)

# Should see redacted form
$ curl ... | grep "REDACTED"
# Expected: [JWT_REDACTED], [API_KEY_REDACTED], u***@company.com
```

**Part B — Cost:**
```
Volume Report:
  /health (100% capture): 40GB/ngày
  /health (1% sampling):   0.4GB/ngày  ← 99.6% reduction!

  Success 2xx (100%): 80GB/ngày
  Success 2xx (10%):   8GB/ngày  ← 90% reduction!

  Errors 4xx/5xx (100%): 30GB/ngày
  Errors 4xx/5xx (100%): 30GB/ngày  ← no change, keep all

Tổng:
  Trước: 150GB/ngày = 4500GB/tháng ≈ $103/tháng (S3 Standard)
  Sau:   38.4GB/ngày = 1152GB/tháng ≈ $26/tháng  (S3 Standard)
  Tiết kiệm: ~75% từ sampling alone
```

### Hint

**Promtail redaction pipeline stages:**
```yaml
pipeline_stages:
  - json:
      expressions:
        message: message
        email: email
        card: card_number
  - replace:
      expression: '(\b[A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+)\.([A-Z|a-z]{2,})\b'
      replace: '***@***.***'
  - replace:
      expression: '\b(\d{4})\s?\d{4}\s?\d{4}\s?(\d{4})\b'
      replace: '**** **** **** $2'
  - replace:
      expression: 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'
      replace: '[JWT_REDACTED]'
  - replace:
      expression: 'sk-[a-z]+-[A-Za-z0-9]+'
      replace: '[API_KEY_REDACTED]'
```

**Sampling với Promtail:**
```yaml
pipeline_stages:
  - json:
      expressions:
        path: path
        status: status_code
  - match:
      selector: '{job="fintech-api"}'
      stages:
        - sampling:
            rate: 0.01  # 1% — Health checks
      pipeline_name: health_sampling
      action: keep
      expression: '"health|ready"'
```

**Loki retention config:**
```yaml
compactor:
  retention_enabled: true
limits_config:
  retention_period: 7d  # default hot tier
# Per-stream override via stream_retention trong ruler (Loki Enterprise)
# Hoặc config per tenant
```

**Loki volume query API:**
```bash
# Volume theo labels
curl -s "http://localhost:3100/loki/api/v1/index/volume" \
  --data-urlencode 'query={env="prod"}' \
  --data-urlencode 'start='"$(date -d '24 hours ago' +%s%N)"'' \
  --data-urlencode 'end='"$(date +%s%N)"'' | jq '.data.result'
```

### Acceptance Criteria

**Part A:**
- [ ] Service log có sensitive data trước pipeline
- [ ] Sau Promtail pipeline, query Loki không tìm thấy raw card number (4111...)
- [ ] Redacted form xuất hiện trong logs
- [ ] Application-level `sanitizeFields()` function được implement và tested

**Part B:**
- [ ] Loki config có `retention_period` set
- [ ] Compactor enabled với `deletion_mode`
- [ ] Sampling pipeline config cho /health logs
- [ ] Cost estimate report với số cụ thể (GB/ngày trước và sau)
- [ ] Volume query script chạy được và trả về breakdown per job

### Bonus Challenge

Implement một **log audit trail** — đảm bảo tất cả log queries đến Loki đều được logged:

1. Thêm nginx access log trước Loki
2. Promtail scrape nginx access log → gửi về Loki (job: `loki-access`)
3. Query: "Ai đã query logs của `fintech-api` trong 24h qua?"
4. Viết Alert: Nếu > 5 unique users query log data user trong 1h → alert Security team

---

## Solutions

<details>
<summary>Click để xem Solution Exercise 1</summary>

```bash
# 1. Tạo directory structure
mkdir -p day41-ex1/{grafana/provisioning/datasources,fake-logs}

# 2. Tạo fake log file
for i in {1..30}; do
  LEVEL=$([ $((RANDOM % 5)) -eq 0 ] && echo "error" || echo "info")
  DURATION=$((RANDOM % 500 + 10))
  STATUS=$([ "$LEVEL" = "error" ] && echo "500" || echo "200")
  echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"level\":\"$LEVEL\",\"service\":\"fake-app\",\"message\":\"Processing request $i\",\"request_id\":\"req-$i\",\"duration_ms\":$DURATION,\"status_code\":$STATUS}" \
    >> day41-ex1/fake-logs/app.log
  sleep 0.1
done

cat day41-ex1/fake-logs/app.log | head -3  # verify

# 3. docker-compose.yaml
cat > day41-ex1/docker-compose.yaml << 'EOF'
version: "3.8"
services:
  loki:
    image: grafana/loki:3.2.1
    ports: ["3100:3100"]
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml:ro
      - loki-data:/loki

  promtail:
    image: grafana/promtail:3.2.1
    volumes:
      - ./promtail-config.yaml:/etc/promtail/config.yaml:ro
      - ./fake-logs:/var/log/fake-app:ro
    command: -config.file=/etc/promtail/config.yaml
    depends_on: [loki]

  grafana:
    image: grafana/grafana:11.5.2
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin123
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro

volumes:
  loki-data:
  grafana-data:
EOF

# 4. promtail-config.yaml
cat > day41-ex1/promtail-config.yaml << 'EOF'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/log/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: fake-app
    static_configs:
      - targets: [localhost]
        labels:
          job: fake-app
          env: dev
          __path__: /var/log/fake-app/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            service: service
      - labels:
          level: level
          service: service
EOF

# 5. Grafana datasource provisioning
mkdir -p day41-ex1/grafana/provisioning/datasources
cat > day41-ex1/grafana/provisioning/datasources/loki.yaml << 'EOF'
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    url: http://loki:3100
    isDefault: true
    access: proxy
EOF

# 6. Loki config (minimal)
cat > day41-ex1/loki-config.yaml << 'EOF'
auth_enabled: false
server:
  http_listen_port: 3100
common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
limits_config:
  retention_period: 15d
compactor:
  working_directory: /loki/compactor
  retention_enabled: true
EOF

# 7. Start
cd day41-ex1
docker-compose up -d

# 8. Verify
sleep 15
curl -s http://localhost:3100/ready  # → OK
curl -s "http://localhost:3100/loki/api/v1/label/job/values" | jq .

# LogQL queries to test:
# {job="fake-app"}
# {job="fake-app", level="error"}
# sum(count_over_time({job="fake-app"}[1m])) by (level)
# {job="fake-app"} | json | duration_ms > 200

# Cleanup
docker-compose down -v
cd ..
rm -rf day41-ex1
```

</details>

<details>
<summary>Click để xem Solution Exercise 2 (core structure)</summary>

```go
// main.go cho api-gateway
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "os"
    "time"

    "github.com/google/uuid"
    "github.com/rs/zerolog"
    "github.com/rs/zerolog/log"
)

var logger zerolog.Logger

func init() {
    f, _ := os.OpenFile("/app/logs/app.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    logger = zerolog.New(zerolog.MultiLevelWriter(os.Stdout, f)).
        With().
        Timestamp().
        Str("service", "api-gateway").
        Logger()
}

func getOrCreateRequestID(r *http.Request) string {
    id := r.Header.Get("X-Request-ID")
    if id == "" {
        id = uuid.New().String()
    }
    return id
}

func callUpstream(ctx context.Context, url, requestID string) ([]byte, int, error) {
    req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
    req.Header.Set("X-Request-ID", requestID) // propagate!

    resp, err := http.DefaultClient.Do(req)
    if err != nil {
        return nil, 0, err
    }
    defer resp.Body.Close()

    var buf []byte
    json.NewDecoder(resp.Body).Decode(&buf)
    return buf, resp.StatusCode, nil
}

func placeOrderHandler(w http.ResponseWriter, r *http.Request) {
    reqID := getOrCreateRequestID(r)
    start := time.Now()

    logger.Info().Str("request_id", reqID).Str("path", "/place-order").Msg("Received request")

    // Call user-service
    _, code, err := callUpstream(r.Context(), "http://user-service:8081/validate", reqID)
    if err != nil || code >= 400 {
        logger.Error().Str("request_id", reqID).Str("upstream", "user-service").
            Err(err).Msg("User validation failed")
        http.Error(w, "user validation failed", http.StatusBadGateway)
        return
    }
    logger.Info().Str("request_id", reqID).Str("upstream", "user-service").Msg("User validated")

    // Call order-service
    _, code, err = callUpstream(r.Context(), "http://order-service:8082/create", reqID)
    if err != nil || code >= 400 {
        logger.Error().Str("request_id", reqID).Str("upstream", "order-service").
            Err(err).Msg("Order creation failed")
        http.Error(w, "order creation failed", http.StatusBadGateway)
        return
    }
    logger.Info().Str("request_id", reqID).Str("upstream", "order-service").
        Int64("total_duration_ms", time.Since(start).Milliseconds()).
        Msg("Order placed successfully")

    w.Header().Set("X-Request-ID", reqID)
    json.NewEncoder(w).Encode(map[string]string{
        "order_id":   uuid.New().String(),
        "request_id": reqID,
        "status":     "created",
    })
}

func main() {
    os.MkdirAll("/app/logs", 0755)
    mux := http.NewServeMux()
    mux.HandleFunc("/place-order", placeOrderHandler)
    mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
    })
    log.Info().Msg(fmt.Sprintf("api-gateway starting on :8080"))
    http.ListenAndServe(":8080", mux)
}
```

```bash
# Test correlation ID
curl -H "X-Request-ID: my-test-123" http://localhost:8080/place-order

# LogQL — trace tất cả logs
{job=~"api-gateway|user-service|order-service"} | json | request_id = "my-test-123"

# Test force-error
curl -H "X-Request-ID: err-test-456" -H "X-Force-Error: true" http://localhost:8080/place-order

# View all errors
{job=~"api-gateway|user-service|order-service"} | json | level = "error"
```

</details>

<details>
<summary>Click để xem Solution Exercise 3 (redaction pipeline)</summary>

```yaml
# promtail-config.yaml — Full redaction pipeline
server:
  http_listen_port: 9080

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: fintech-api
    static_configs:
      - targets: [localhost]
        labels:
          job: fintech-api
          __path__: /var/log/fintech-api/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            path: path
            status_code: status_code
      - labels:
          level: level
      # Redact credit cards: NNNN-NNNN-NNNN-NNNN → **** **** **** NNNN
      - replace:
          expression: '\b(\d{4})[\s-]?\d{4}[\s-]?\d{4}[\s-]?(\d{4})\b'
          replace: '**** **** **** $2'
      # Redact JWT tokens
      - replace:
          expression: 'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+'
          replace: '[JWT_REDACTED]'
      # Redact API keys
      - replace:
          expression: '\bsk-[a-z]+-[A-Za-z0-9]+'
          replace: '[API_KEY_REDACTED]'
      # Redact emails
      - replace:
          expression: '\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b'
          replace: '[EMAIL_REDACTED]'
      # Sampling: keep 1% of health checks
      - match:
          selector: '{job="fintech-api"}'
          pipeline_name: health_sampling
          action: drop
          expression: '(health|readiness|liveness)'
          drop_counter_reason: health_check_sampled
```

```go
// Go: Application-level sanitization
package logger

import (
    "regexp"
    "github.com/rs/zerolog"
)

var (
    reCardNumber = regexp.MustCompile(`\b(\d{4})[\s-]?\d{4}[\s-]?\d{4}[\s-]?(\d{4})\b`)
    reJWT        = regexp.MustCompile(`eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+`)
    reAPIKey     = regexp.MustCompile(`\bsk-[a-z]+-[A-Za-z0-9]+`)
    reEmail      = regexp.MustCompile(`\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b`)
)

func SanitizeString(s string) string {
    s = reCardNumber.ReplaceAllString(s, "**** **** **** $2")
    s = reJWT.ReplaceAllString(s, "[JWT_REDACTED]")
    s = reAPIKey.ReplaceAllString(s, "[API_KEY_REDACTED]")
    s = reEmail.ReplaceAllString(s, "[EMAIL_REDACTED]")
    return s
}

type SanitizedFieldObject struct {
    data map[string]string
}

func (s *SanitizedFieldObject) MarshalZerologObject(e *zerolog.Event) {
    for k, v := range s.data {
        e.Str(k, SanitizeString(v))
    }
}

// Usage:
// log.Info().Object("request", &SanitizedFieldObject{data: requestFields}).Msg("Request received")
```

```bash
# Cost estimation script
#!/bin/bash
# Calculate log volume before/after sampling

LOKI_URL="http://localhost:3100"
START=$(date -d '24 hours ago' +%s%N)
END=$(date +%s%N)

echo "=== Log Volume Report ==="
echo ""
echo "Querying Loki for volume breakdown..."

# Total volume
TOTAL=$(curl -s "$LOKI_URL/loki/api/v1/index/volume_range" \
  --data-urlencode 'query={env="prod"}' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$END" | jq '[.data.result[].values[].1 // "0" | tonumber] | add // 0')

echo "Total bytes today: $TOTAL"
echo "Total GB/day: $(echo "scale=2; $TOTAL / 1073741824" | bc)"
echo ""

# Estimate after sampling
echo "--- After Sampling Estimates ---"
echo "Health logs (1%):    ~$(echo "scale=1; $TOTAL * 0.267 * 0.01 / 1073741824" | bc) GB/day"
echo "Success 2xx (10%):  ~$(echo "scale=1; $TOTAL * 0.533 * 0.10 / 1073741824" | bc) GB/day"
echo "Errors 4xx/5xx (100%): ~$(echo "scale=1; $TOTAL * 0.20 / 1073741824" | bc) GB/day"

# S3 cost estimate ($0.023/GB standard)
echo ""
echo "--- Cost Estimate (S3 Standard $0.023/GB) ---"
MONTHLY_GB=$(echo "scale=0; $TOTAL * 30 / 1073741824" | bc)
COST_BEFORE=$(echo "scale=2; $MONTHLY_GB * 0.023" | bc)
COST_AFTER=$(echo "scale=2; $MONTHLY_GB * 0.25 * 0.023" | bc)
echo "Before sampling: ~\$$COST_BEFORE/month ($MONTHLY_GB GB/month)"
echo "After sampling:  ~\$$COST_AFTER/month (est. 75% reduction)"
echo "Savings: ~\$$(echo "scale=2; $COST_BEFORE - $COST_AFTER" | bc)/month"
```

</details>

