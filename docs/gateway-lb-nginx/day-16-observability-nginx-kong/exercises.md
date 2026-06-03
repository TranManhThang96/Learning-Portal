# Day 16: Exercises — Observability for Nginx & Kong

> **Yêu cầu**: Docker, Docker Compose, curl, jq, wrk, Prometheus, Grafana, Promtail
> **Kong version**: 3.7 | **Prometheus version**: 2.45+
> **Thời gian ước tính**: 90-120 phút
> **Note**: Setup Exercise 0 được dùng chung cho Exercise 1-8. Chỉ setup 1 lần.

---

## Exercise 0: Setup — Full Observability Stack

**Mục tiêu**: Dựng Docker Compose với Nginx + Kong DB-less + Prometheus + Grafana + Loki + Promtail.

### Bước 1: Tạo directory

```bash
mkdir -p ~/kong-observability && cd ~/kong-observability

mkdir -p nginx-logs kong-logs prometheus-data promtail-data
```

### Bước 2: Tạo mock backend expectation

```bash
cat > mocks/order-expectation.json << 'EOF'
[
  {
    "httpRequest": { "path": "/orders" },
    "httpResponse": {
      "statusCode": 200,
      "body": "{\"order_id\":123,\"status\":\"ok\",\"items\":3}",
      "headers": {
        "X-Backend": ["order-service-v1"],
        "Content-Type": ["application/json"]
      }
    }
  },
  {
    "httpRequest": { "path": "/health" },
    "httpResponse": {
      "statusCode": 200,
      "body": "{\"status\":\"healthy\",\"service\":\"order\"}",
      "headers": {
        "Content-Type": ["application/json"]
      }
    }
  }
]
EOF

cat > mocks/payment-expectation.json << 'EOF'
[
  {
    "httpRequest": { "path": "/pay" },
    "httpResponse": {
      "statusCode": 200,
      "body": "{\"payment_id\":\"pay_abc\",\"status\":\"paid\",\"amount\":10000}",
      "headers": {
        "X-Backend": ["payment-service-v1"],
        "Content-Type": ["application/json"]
      }
    }
  },
  {
    "httpRequest": { "path": "/health" },
    "httpResponse": {
      "statusCode": 200,
      "body": "{\"status\":\"healthy\",\"service\":\"payment\"}",
      "headers": {
        "Content-Type": ["application/json"]
      }
    }
  }
]
EOF
```

### Bước 3: Tạo Nginx config với stub_status + JSON log

```bash
cat > nginx.conf << 'EOF'
user  nginx;
worker_processes  auto;
worker_rlimit_nofile 65535;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  4096;
    use epoll;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # JSON access log format
    log_format json_log escape=json
      '{"time":"$time_iso8601",'
      '"remote_addr":"$remote_addr",'
      '"request_id":"$request_id",'
      '"method":"$request_method",'
      '"uri":"$request_uri",'
      '"server_protocol":"$server_protocol",'
      '"status":$status,'
      '"body_bytes_sent":$body_bytes_sent,'
      '"request_time":$request_time,'
      '"upstream_addr":"$upstream_addr",'
      '"upstream_status":$upstream_status,'
      '"http_user_agent":"$http_user_agent",'
      '"http_x_forwarded_for":"$http_x_forwarded_for"}';

    access_log /var/log/nginx/access.json json_log buffer=64k flush=5s;

    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout  65;
    keepalive_requests 10000;

    # Upstream to Kong
    upstream kong_backend {
        server kong:8000;
        keepalive 64;
    }

    server {
        listen 80;
        server_name  localhost;

        # Proxy to Kong
        location / {
            proxy_pass http://kong_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Request-ID $request_id;
            proxy_connect_timeout 5s;
            proxy_read_timeout 30s;
        }

        # Nginx stub_status (for prometheus-exporter)
        location /nginx_status {
            stub_status on;
            allow 127.0.0.1;
            allow 172.16.0.0/12;   # Docker network
            deny all;
            access_log off;
        }
    }
}
EOF
```

### Bước 4: Tạo Kong declarative config với prometheus plugin

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

upstreams:
  - name: order-upstream
    healthchecks:
      active:
        type: http
        http_path: /health
        healthy:
          interval: 5
          successes: 1
        unhealthy:
          interval: 5
          http_failures: 1
          tcp_failures: 1
    targets:
      - target: order-backend:1080

  - name: payment-upstream
    healthchecks:
      active:
        type: http
        http_path: /health
        healthy:
          interval: 5
          successes: 1
        unhealthy:
          interval: 5
          http_failures: 1
          tcp_failures: 1
    targets:
      - target: payment-backend:1080

services:
  # Order service
  - name: order-service
    url: http://order-upstream/orders
    routes:
      - name: order-route
        paths:
          - /api/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true
          upstream_health_metrics: true

  # Payment service
  - name: payment-service
    url: http://payment-upstream/pay
    routes:
      - name: payment-route
        paths:
          - /api/pay
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true
          upstream_health_metrics: true

  # Rate limiting per consumer
  - name: rate-limited-service
    url: http://order-upstream/orders
    routes:
      - name: rate-limited-route
        paths:
          - /api/orders-limited
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
      - name: rate-limiting
        config:
          minute: 10
          policy: local
          fault_tolerant: true
EOF
```

### Bước 5: Tạo Prometheus config

```bash
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 30s
  scrape_timeout: 10s
  evaluation_interval: 30s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files: []

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx-exporter:9113']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: nginx-1

  - job_name: 'kong'
    static_configs:
      - targets: ['kong:8100']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: kong-1
EOF
```

### Bước 6: Tạo Promtail config

```bash
cat > promtail.yaml << 'EOF'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

clients:
  - url: http://loki:3100/loki/api/v1/push

positions:
  filename: /var/positions.yaml

scrape_configs:
  - job_name: nginx-access
    static_configs:
      - targets:
          - localhost
        labels:
          job: nginx
          env: lab
        __path__: /var/log/nginx/*.json

  - job_name: nginx-error
    static_configs:
      - targets:
          - localhost
        labels:
          job: nginx
          log_type: error
          env: lab
        __path__: /var/log/nginx/error.log

  - job_name: kong-access
    static_configs:
      - targets:
          - localhost
        labels:
          job: kong
          env: lab
        __path__: /var/log/kong/*.log
EOF
```

### Bước 7: Tạo Loki config (minimal)

```bash
cat > loki-config.yaml << 'EOF'
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
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
EOF
```

### Bước 8: Tạo Grafana datasource provisioning

```bash
mkdir -p grafana-provisioning/datasources grafana-provisioning/dashboards

cat > grafana-provisioning/datasources/datasources.yaml << 'EOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
EOF
```

### Bước 9: Tạo docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"
services:

  # ── Nginx Reverse Proxy ──────────────────────────────
  nginx:
    image: nginx:1.25-alpine
    container_name: nginx-proxy
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx-logs:/var/log/nginx
    depends_on:
      - kong
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost/nginx_status"]
      interval: 10s
      timeout: 5s
      retries: 3

  # ── Nginx Prometheus Exporter ────────────────────────
  nginx-exporter:
    image: nginx/nginx-prometheus-exporter:1.2.0
    container_name: nginx-exporter
    command:
      - -nginx.scrape-uri=http://nginx:80/nginx_status
      - -web.listen-address=:9113
    ports:
      - "9113:9113"
    depends_on:
      - nginx
    restart: unless-stopped

  # ── Kong Gateway (DB-less) ──────────────────────────
  kong:
    image: kong:3.7
    container_name: kong
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_LOG_LEVEL: info
      KONG_PLUGINS: bundled,prometheus,rate-limiting,correlation-id
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_ERROR_LOG: /dev/stderr
    volumes:
      - ./kong.yml:/kong/declarative/kong.yml:ro
      - ./kong-logs:/var/log/kong
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8100:8100"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # ── Mock Backends ────────────────────────────────────
  order-backend:
    image: mockserver/mockserver:5.15.0
    container_name: order-backend
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/order-expectation.json
    volumes:
      - ./mocks/order-expectation.json:/config/order-expectation.json:ro
    ports:
      - "8081:1080"

  payment-backend:
    image: mockserver/mockserver:5.15.0
    container_name: payment-backend
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/payment-expectation.json
    volumes:
      - ./mocks/payment-expectation.json:/config/payment-expectation.json:ro
    ports:
      - "8082:1080"

  # ── Prometheus ───────────────────────────────────────
  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=7d'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus-data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped

  # ── Grafana ─────────────────────────────────────────
  grafana:
    image: grafana/grafana:10.1.0
    container_name: grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_FEATURE_TOGGLES_ENABLE: publicDashboards
    volumes:
      - ./grafana-provisioning:/etc/grafana/provisioning
      - ./grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
    restart: unless-stopped

  # ── Loki ─────────────────────────────────────────────
  loki:
    image: grafana/loki:2.8.2
    container_name: loki
    command: -config.file=/etc/loki/loki-config.yaml
    volumes:
      - ./loki-config.yaml:/etc/loki/loki-config.yaml:ro
      - ./loki-data:/loki
    ports:
      - "3100:3100"
    restart: unless-stopped

  # ── Promtail ─────────────────────────────────────────
  promtail:
    image: grafana/promtail:2.8.2
    container_name: promtail
    volumes:
      - ./promtail.yaml:/etc/promtail/promtail.yaml:ro
      - ./nginx-logs:/var/log/nginx:ro
      - ./kong-logs:/var/log/kong:ro
    depends_on:
      - loki
    restart: unless-stopped

networks:
  default:
    name: obs-net
EOF
```

### Bước 10: Start và verify

```bash
cd ~/kong-observability
docker compose up -d

# Verify all containers are running
sleep 15
docker compose ps

# Verify Nginx stub_status
curl -s http://localhost:80/nginx_status
# Expected: "Active connections: 1" + accepts/handled/requests

# Verify Nginx prometheus-exporter
curl -s http://localhost:9113/metrics | head -10
# Expected: nginx_connections_active, nginx_http_requests_total

# Verify Kong status
curl -sf http://localhost:8001/ | jq '{version: .version, database: .configuration.database}'
# Expected: {"version":"3.7.x","database":"off"}

# Verify Kong Prometheus metrics
curl -s http://localhost:8100/metrics | head -20
# Expected: kong_http_requests_total, kong_latency_bucket, ...

# Verify Prometheus targets
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
# Expected: nginx UP, kong UP, prometheus UP

# Verify Grafana
curl -s http://localhost:3000/api/health | jq '{version}'
# Expected: {"version":"10.1.0"}

echo "Setup OK — all services running"
```

**Lỗi thường gặp**:

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Prometheus target DOWN | Network / firewall | Check Docker network, `docker network inspect obs-net` |
| Kong metrics empty | `KONG_PLUGINS` không có prometheus | Verify env var, restart Kong |
| Nginx exporter 403 | `allow` block trong stub_status | Update `allow` để include Docker subnet |
| Loki/Promtail error | Volume path sai | Check `./nginx-logs:/var/log/nginx` mount |
| Grafana 502 | Loki container chưa ready | `sleep 5` sau Loki start |

---

## Exercise 1: Explore Nginx Metrics via prometheus-exporter

**Mục tiêu**: Hiểu các Nginx metrics từ `stub_status` được expose bởi prometheus-exporter.

### Bước 1: Đọc tất cả Nginx metrics

```bash
curl -s http://localhost:9113/metrics | grep "^nginx_"
```

### Bước 2: Check active connections under load

```bash
# Terminal 1: Monitor connections
watch -n 2 "curl -s http://localhost:9113/metrics \
  | grep nginx_connections"

# Terminal 2: Generate load
docker run --rm --network obs-net \
  williamyeh/wrk \
  -t2 -c20 -d30s http://nginx/api/orders

# Observe: nginx_connections_active tăng, nginx_connections_waiting thay đổi
```

### Bước 3: Check backlog drop (accepts vs handled)

```bash
# Baseline (before load)
curl -s http://localhost:9113/metrics \
  | grep "nginx_connections_"

# After load
curl -s http://localhost:9113/metrics \
  | grep "nginx_connections_"

# Calculate drop rate
ACCEPTS=$(curl -s http://localhost:9113/metrics \
  | grep "nginx_connections_accepted " | awk '{print $2}')
HANDLED=$(curl -s http://localhost:9113/metrics \
  | grep "nginx_connections_handled " | awk '{print $2}')

echo "Accepted: $ACCEPTS, Handled: $HANDLED"
echo "Drop rate: $(( ACCEPTS - HANDLED )) connections"
```

---

## Exercise 2: Explore Kong Prometheus Metrics

**Mục tiêu**: Hiểu các Kong metrics, phân biệt `kong_latency` vs `kong_upstream_latency` vs `kong_kong_latency`.

### Bước 1: List tất cả Kong metrics

```bash
curl -s http://localhost:8100/metrics \
  | grep "^kong_" \
  | sed 's/{.*//' \
  | sort -u
```

**Expected output**:
```
kong_bandwidth_bytes_total
kong_datastore_reachable
kong_http_requests_total
kong_kong_latency_bucket
kong_kong_latency_count
kong_kong_latency_sum
kong_latency_bucket
kong_latency_count
kong_latency_sum
kong_nginx_metric_errors_total
kong_nginx_metric_errors_total
kong_upstream_latency_bucket
kong_upstream_latency_count
kong_upstream_latency_sum
kong_upstream_target_health
```

### Bước 2: Generate traffic và verify metrics

```bash
# Generate 500 requests để tạo metric data
for i in $(seq 1 500); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/orders &
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/pay &
done
wait

# Check request count by service
curl -s http://localhost:8100/metrics \
  | grep "kong_http_requests_total " \
  | grep -v "^#" \
  | awk -F'{' '{print $2}' \
  | tr ',' '\n' \
  | grep "service=" \
  | sort

# Check status code breakdown
curl -s http://localhost:8100/metrics \
  | grep "kong_http_requests_total{" \
  | grep -v "^#"
```

### Bước 3: So sánh latency types

```bash
# Kong overhead (plugin processing)
curl -s http://localhost:8100/metrics \
  | grep "kong_kong_latency_bucket{" \
  | head -5

# Upstream latency (network + upstream)
curl -s http://localhost:8100/metrics \
  | grep "kong_upstream_latency_bucket{" \
  | head -5

# Total latency (should be sum)
curl -s http://localhost:8100/metrics \
  | grep "kong_latency_bucket{" \
  | head -5

echo "kong_latency = kong_kong_latency + kong_upstream_latency"
echo "Check: Sum of bucket counts should be equal across types"
```

### Bước 4: Check upstream target health

```bash
curl -s http://localhost:8100/metrics \
  | grep "kong_upstream_target_health" \
  | grep -v "^#"
```

**Expected**: `kong_upstream_target_health` gauge = 1 (healthy) cho order-service và payment-service.

---

## Exercise 3: Query PromQL — RED Dashboard

**Mục tiêu**: Viết và chạy PromQL queries cho dashboard RED method.

### Bước 1: Rate — RPS per service

```bash
# Prometheus API
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=sum by (service) (rate(kong_http_requests_total[5m]))' \
  | jq '.data.result[] | {service: .metric.service, rps: .value[1]}'
```

### Bước 2: Errors — 5xx error rate per service

```bash
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=sum by (service) (rate(kong_http_requests_total{status=~"5.."}[5m])) / sum by (service) (rate(kong_http_requests_total[5m])) * 100' \
  | jq '.data.result[] | {service: .metric.service, error_rate_pct: .value[1]}'
```

### Bước 3: Duration — p50/p95/p99 latency (multi-instance safe)

```bash
# p95 gateway latency
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(kong_latency_bucket[5m])))' \
  | jq '.data.result[0] | {metric: "p95_gateway_latency", value_seconds: .value[1]}'

# p99 gateway latency
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.99, sum by (le) (rate(kong_latency_bucket[5m])))' \
  | jq '.data.result[0] | {metric: "p99_gateway_latency", value_seconds: .value[1]}'

# p95 upstream latency (network + backend)
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(kong_upstream_latency_bucket[5m])))' \
  | jq '.data.result[0] | {metric: "p95_upstream_latency", value_seconds: .value[1]}'
```

### Bước 4: Histogram bucket breakdown

```bash
# Xem latency distribution (bucket counts)
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=sum by (le) (rate(kong_latency_bucket[5m]))' \
  | jq '.data.result[] | {bucket_ms: .metric.le, count_per_sec: .value[1]}'
```

---

## Exercise 4: Generate Load và Verify RED Metrics

**Mục tiêu**: Dùng `wrk` để tạo load, verify Prometheus metrics theo thời gian thực.

### Bước 1: Baseline load test (100 RPS, 30s)

```bash
# Install wrk (macOS)
brew install wrk
# Ubuntu/Debian:
# sudo apt-get install wrk

# Baseline: 100 RPS, 30s
wrk -t4 -c50 -d30s \
  --latency \
  http://localhost/api/orders
```

**Expected output** (sample):
```
Running 30s test @ http://localhost/api/orders
  4 threads and 50 connections
  Latency Distribution
     50%   8.23ms
     75%  12.45ms
     90%  18.90ms
     99%  45.12ms
  Requests/sec:  102.34
```

### Bước 2: Verify Prometheus metrics sau load

```bash
# Wait 30s để Prometheus scrape 1 lần
sleep 30

# Check request rate (should be ~100)
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=sum(rate(kong_http_requests_total[1m]))' \
  | jq '.data.result[0].value[1]'

# Check nginx requests rate
curl -s "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=rate(nginx_http_requests_total[1m])' \
  | jq '.data.result[0].value[1]'
```

### Bước 3: High load test (1000 RPS, spike)

```bash
# Spike: 1000 RPS trong 10s
docker run --rm --network obs-net \
  williamyeh/wrk \
  -t4 -c200 -d10s \
  --latency \
  http://localhost/api/orders

# Check active connections spike
curl -s http://localhost:9113/metrics \
  | grep "nginx_connections_active"

# Check waiting (keepalive idle)
curl -s http://localhost:9113/metrics \
  | grep "nginx_connections_waiting"
```

### Bước 4: Compare Nginx vs Kong metrics

```bash
echo "=== Nginx request rate ==="
curl -s http://localhost:9113/metrics \
  | grep "nginx_http_requests_total " \
  | awk '{print "Nginx total requests:", $2}'

echo "=== Kong request rate ==="
curl -s http://localhost:8100/metrics \
  | grep "^kong_http_requests_total " \
  | awk '{print "Kong total requests:", $2}'

echo "Note: Kong < Nginx vì Kong chỉ count đến backend,
       Nginx count cả request đến Kong upstream"
```

---

## Exercise 5: Grafana Dashboard Setup

**Mục tiêu**: Import dashboard và verify panels.

### Bước 1: Login Grafana

```
URL: http://localhost:3000
Username: admin
Password: admin
```

### Bước 2: Check datasource

```
Grafana UI → Connections → Data Sources → Prometheus
→ URL: http://prometheus:9090
→ Save & Test → "Data source is working"
```

### Bước 3: Import dashboard từ JSON skeleton

```
Grafana UI → Dashboards → Import
→ Upload: chọn file dashboard JSON (từ document.md section 4.1)
→ Prometheus datasource: Prometheus
→ Save
```

### Bước 4: Verify panels

Check các panel sau trên dashboard:

| Panel | Expected Query | Check |
|---|---|---|
| Total RPS | `sum(rate(kong_http_requests_total[5m]))` | Có số > 0 |
| Error Rate % | `rate(5xx) / rate(total) * 100` | Có số 0-100 |
| p95 Latency | `histogram_quantile(0.95, sum by (le) (rate(kong_latency_bucket[5m])))` | Có số (giây) |
| Nginx Active | `nginx_connections_active` | Có số |
| Upstream Health | `kong_upstream_target_health` | UP/DOWN indicator |

### Bước 5: Import official Kong dashboard

```
Grafana UI → Dashboards → Import
→ Dashboard ID: 7424
→ Select Prometheus datasource
→ Customize: set job_name filter
→ Import
```

---

## Exercise 6: Logging Pipeline — Loki + Grafana Explore

**Mục tiêu**: Verify log JSON từ Nginx → Promtail → Loki → Grafana.

### Bước 1: Check Loki is receiving logs

```bash
# Query Loki via API
curl -s "http://localhost:3100/loki/api/v1/label/job/values" \
  | jq '.data[]'

# Check log count
curl -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query=count({job="nginx"})' \
  | jq '.data.result'
```

### Bước 2: Query logs via Grafana Explore

```
Grafana UI → Explore → Loki datasource
→ Query: {job="nginx"}
→ Run Query

Expected: JSON log lines xuất hiện
```

### Bước 3: Query logs by status code

```
Grafana Explore → Loki
→ Query: {job="nginx"} | json | status >= 500
→ Run Query

Expected: 5xx log lines (nếu có)
```

### Bước 4: Query logs by request ID

```bash
# Get a request ID from nginx log
curl -s http://localhost/api/orders \
  -H "X-Request-ID: test-123" \
  -w "\n" \
  | jq

# Query by request_id in Loki
# Grafana Explore:
# Query: {job="nginx"} |= "test-123"
```

### Bước 5: Verify Promtail is tailing logs

```bash
# Check Promtail logs
docker compose logs promtail 2>&1 | tail -20

# Expected: "hostname=promtail target=nginx"
# " Successfully sent, received tot" (no error)

# Check Loki ingestion rate
curl -s "http://localhost:3100/metrics" \
  | grep "loki_ingester_lines_received" \
  | head -5
```

---

## Exercise 7: Simulate Failure — Upstream Target Unhealthy

**Mục tiêu**: Simulate backend down, observe `kong_upstream_target_health` metric.

### Bước 1: Check initial target health

```bash
curl -s http://localhost:8100/metrics \
  | grep "kong_upstream_target_health" \
  | grep -v "^#"
```

### Bước 2: Stop order-backend

```bash
docker stop order-backend

echo "Order backend stopped. Waiting 30s for health check..."
sleep 30
```

### Bước 3: Verify metric changed to unhealthy

```bash
curl -s http://localhost:8100/metrics \
  | grep "kong_upstream_target_health" \
  | grep -v "^#"
```

**Expected**: `kong_upstream_target_health` cho order-upstream target = 0 (unhealthy).

### Bước 4: Check Prometheus alert (if configured)

```bash
# Prometheus alerts page
# URL: http://localhost:9090/alerts
# Expected alert: KongUpstreamTargetUnhealthy (nếu đã add alert rule)
```

### Bước 5: Query Kong /upstreams/targets API

```bash
curl -s http://localhost:8001/upstreams \
  | jq '.data[].name'

# Check targets health via API
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target: .target, weight: .weight, healthy: .healthy}'
```

### Bước 6: Restore order-backend

```bash
docker start order-backend
sleep 10

# Verify health restored
curl -s http://localhost:8100/metrics \
  | grep "kong_upstream_target_health" \
  | grep order \
  | grep -v "^#"
```

### Bước 7: Observe impact on access log

```bash
# Tail nginx log (nếu backend down)
tail -f ~/kong-observability/nginx-logs/access.json | jq
```

---

## Exercise 8 (Challenge): Prometheus Alert Rule + Slack Webhook

**Mục tiêu**: Viết alert rule cho 5xx error rate > 1% và p95 latency > 500ms.

### Bước 1: Tạo alert rules file

```bash
cat > prometheus-alerts.yml << 'EOF'
groups:
  - name: gateway-alerts
    interval: 30s
    rules:
      - alert: GatewayHighErrorRate
        expr: |
          (
            sum(rate(kong_http_requests_total{status=~"5.."}[5m]))
            / sum(rate(kong_http_requests_total[5m]))
          ) > 0.01
        for: 2m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Gateway 5xx error rate > 1%"
          description: "Current error rate: {{ $value | humanizePercentage }}"
          runbook_url: "https://wiki.example.com/runbooks/gateway-high-errors"

      - alert: GatewayHighLatencyP95
        expr: |
          histogram_quantile(0.95,
            sum by (le) (rate(kong_latency_bucket[5m]))) > 0.5
        for: 5m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Gateway p95 latency > 500ms"

      - alert: KongUpstreamTargetDown
        expr: count(kong_upstream_target_health == 0) by (upstream) > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Upstream target down: {{ $labels.upstream }}"
EOF
```

### Bước 2: Apply alert rules (via Prometheus reload API)

```bash
# Copy rule file vào Prometheus container
docker cp prometheus-alerts.yml prometheus:/etc/prometheus/rules.yml

# Trigger Prometheus reload (hot reload)
curl -s -X POST http://localhost:9090/-/reload

# Verify rules loaded
curl -s http://localhost:9090/api/v1/rules \
  | jq '.data.groups[].rules[] | {name: .name, state: .health}'
```

### Bước 3: Verify alert fires (simulate error)

```bash
# Tạo 1000 requests với 1% error bằng cách stop backend
docker stop order-backend
sleep 35  # Chờ 2m alert fire

# Check Prometheus alerts
curl -s "http://localhost:9090/api/v1/alerts" \
  | jq '.data.alerts[] | {name: .name, state: .state, labels: .labels}'

# Restore
docker start order-backend
```

### Bước 4: Slack webhook setup (overview — không chạy được trong lab)

```bash
# Note: Slack webhook requires real Slack workspace

# Prometheus Alertmanager config (alertmanager.yml)
# route:
#   group_by: ['alertname']
#   group_wait: 10s
#   group_interval: 10s
#   repeat_interval: 1h
#   receiver: 'slack-notifications'
# receivers:
# - name: 'slack-notifications'
#   slack_configs:
#     - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
#       channel: '#alerts'
#       text: |
#         {{ range .Alerts }}
#         *Alert:* {{ .Annotations.summary }}
#         *Description:* {{ .Annotations.description }}
#         {{ end }}

echo "Slack webhook setup requires real Slack workspace.
       Refer to Alertmanager docs for full configuration."
```

### Bước 5: Challenge — Add recording rules

```bash
# Add recording rules for fast dashboard queries
cat >> prometheus-alerts.yml << 'EOF'

      # Recording rule: service RPS (fast dashboard)
      - record: service:request_rate:rate5m
        expr: sum by (service) (rate(kong_http_requests_total[5m]))

      # Recording rule: error rate %
      - record: service:error_rate:ratio5m
        expr: |
          sum by (service) (rate(kong_http_requests_total{status=~"5.."}[5m]))
          / sum by (service) (rate(kong_http_requests_total[5m]))
EOF

docker cp prometheus-alerts.yml prometheus:/etc/prometheus/rules.yml
curl -s -X POST http://localhost:9090/-/reload

# Verify recording rules
curl -s "http://localhost:9090/api/v1/rules" \
  | jq '.data.groups[].rules[] | select(.type=="recording") | {name: .name}'
```

---

## Cleanup

```bash
cd ~/kong-observability

# Stop all containers
docker compose down -v

# Remove lab directory
cd ~ && rm -rf ~/kong-observability

echo "Cleanup done"
```

---

## Tổng Kết Exercises

| Exercise | Kỹ năng | Công cụ | Thời gian |
|---|---|---|---|
| 0 | Setup full observability stack | Docker Compose, Prometheus, Grafana, Loki | 15 phút |
| 1 | Explore Nginx metrics | Prometheus API, prometheus-exporter | 10 phút |
| 2 | Explore Kong Prometheus metrics | Kong /metrics, jq | 10 phút |
| 3 | PromQL queries (RED method) | Prometheus API, PromQL | 15 phút |
| 4 | Load test và verify metrics | wrk, Prometheus API | 15 phút |
| 5 | Grafana dashboard setup | Grafana UI | 10 phút |
| 6 | Logging pipeline | Loki, Grafana Explore, Promtail | 10 phút |
| 7 | Failure simulation | Docker stop, Kong metrics | 10 phút |
| 8 (Challenge) | Alert rules + Slack | Prometheus API, Alertmanager config | 15 phút |
