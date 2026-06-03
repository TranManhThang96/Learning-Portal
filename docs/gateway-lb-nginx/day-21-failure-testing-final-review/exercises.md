# Day 21: Exercises — Failure Testing, Benchmark Report & Final Review

> **Yêu cầu**: Docker, Docker Compose, curl, jq, k6, bc
> **Capstone**: Dựa trên Day 20 (Nginx + Kong + 3 microservices + Consul + Redis + Prometheus + Grafana)
> **Thời gian ước tính**: 90-120 phút
> **Lưu ý**: Exercise 0 reuse setup từ Day 20 capstone. Chỉ setup 1 lần.

---

## Exercise 0: Setup — Capstone Day 20 Docker Compose

**Mục tiêu**: Khởi tạo full capstone stack từ Day 20 để chạy chaos experiments. Nếu đã có capstone Day 20, skip bước này.

### Bước 1: Tạo directory cho Day 21

```bash
mkdir -p ~/gateway-chaos
cd ~/gateway-chaos
```

### Bước 2: Tạo docker-compose.yml (capstone stack)

```bash
cat > docker-compose.yml << 'EOF'
version: "3.9"
services:
  # === EDGE NGINX ===
  nginx-edge:
    image: nginx:1.25-alpine
    container_name: nginx-edge
    ports:
      - "80:80"
      - "8080:8080"   # stub_status
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - kong
    networks:
      - gateway-net

  # === KONG GATEWAY ===
  kong:
    image: kong:3.7
    container_name: kong
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_LOG_LEVEL: info
      KONG_PLUGINS: prometheus,rate-limiting,key-auth
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
      KONG_ADMIN_GUI_AUTH: off
      KONG_ADMIN_API_URI: http://localhost:8001
    volumes:
      - ./kong.yml:/kong/declarative/kong.yml:ro
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8100:8100"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - gateway-net

  # === CONSUL ===
  consul:
    image: hashicorp/consul:1.17
    container_name: consul
    command: agent -server -ui -bootstrap-expect=1 -client=0.0.0.0
    ports:
      - "8500:8500"
    networks:
      - gateway-net

  # === REDIS ===
  redis:
    image: redis:7-alpine
    container_name: redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    networks:
      - gateway-net

  # === ORDER SERVICE ===
  order-service-1:
    image: mockserver/mockserver:5.15.0
    container_name: order-service-1
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/order-expectation.json
    volumes:
      - ./mocks/order-v1.json:/config/order-expectation.json:ro
    ports:
      - "8081:1080"
    networks:
      - gateway-net

  order-service-2:
    image: mockserver/mockserver:5.15.0
    container_name: order-service-2
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/order-expectation.json
    volumes:
      - ./mocks/order-v2.json:/config/order-expectation.json:ro
    ports:
      - "8082:1080"
    networks:
      - gateway-net

  # === PAYMENT SERVICE ===
  payment-service:
    image: mockserver/mockserver:5.15.0
    container_name: payment-service
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/payment-expectation.json
    volumes:
      - ./mocks/payment.json:/config/payment-expectation.json:ro
    ports:
      - "8083:1080"
    networks:
      - gateway-net

  # === TRACKING SERVICE ===
  tracking-service:
    image: mockserver/mockserver:5.15.0
    container_name: tracking-service
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/tracking-expectation.json
    volumes:
      - ./mocks/tracking.json:/config/tracking-expectation.json:ro
    ports:
      - "8084:1080"
    networks:
      - gateway-net

  # === PROMETHEUS ===
  prometheus:
    image: prom/prometheus:v2.53.0
    container_name: prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
    networks:
      - gateway-net

  # === GRAFANA ===
  grafana:
    image: grafana/grafana:10.4.0
    container_name: grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: "false"
    ports:
      - "3000:3000"
    volumes:
      - ./grafana-provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
    networks:
      - gateway-net

networks:
  gateway-net:
    driver: bridge
EOF
```

### Bước 3: Tạo mock config files

```bash
mkdir -p mocks grafana-provisioning/datasources grafana-provisioning/dashboards

# Order service mock
cat > mocks/order-v1.json << 'EOF'
{
  "httpRequest": { "path": "/orders" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"service\":\"order\",\"version\":\"v1\",\"status\":\"ok\"}",
    "headers": { "X-Service-Name": ["order-service"] }
  }
}
EOF

cat > mocks/order-v2.json << 'EOF'
{
  "httpRequest": { "path": "/orders" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"service\":\"order\",\"version\":\"v2\",\"status\":\"ok\"}",
    "headers": { "X-Service-Name": ["order-service"] }
  }
}
EOF

# Payment service mock
cat > mocks/payment.json << 'EOF'
{
  "httpRequest": { "path": "/pay" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"service\":\"payment\",\"status\":\"ok\",\"transaction_id\":\"txn123\"}",
    "headers": { "X-Service-Name": ["payment-service"] }
  }
}
EOF

# Tracking service mock
cat > mocks/tracking.json << 'EOF'
{
  "httpRequest": { "path": "/track" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"service\":\"tracking\",\"status\":\"ok\",\"order_id\":\"order123\"}",
    "headers": { "X-Service-Name": ["tracking-service"] }
  }
}
EOF
```

### Bước 4: Tạo kong.yml (declarative config)

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream/orders
    routes:
      - name: order-route
        paths: ["/api/v1/orders"]
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true
      - name: rate-limiting
        config:
          minute: 1000
          policy: redis
          redis_host: redis
          fault_tolerant: true

  - name: payment-service
    url: http://payment-service:1080/pay
    routes:
      - name: payment-route
        paths: ["/api/v1/pay"]
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
      - name: rate-limiting
        config:
          minute: 500
          policy: redis
          redis_host: redis

  - name: tracking-service
    url: http://tracking-service:1080/track
    routes:
      - name: tracking-route
        paths: ["/api/v1/track"]
        strip_path: false
    plugins:
      - name: prometheus
        config:
          latency_metrics: true

upstreams:
  - name: order-upstream
    targets:
      - target: order-service-1:1080
        weight: 100
      - target: order-service-2:1080
        weight: 100
    healthchecks:
      passive:
        healthy:
          successes: 2
        unhealthy:
          http_failures: 3
          timeouts: 3
          tcp_failures: 3
EOF
```

### Bước 5: Tạo Nginx config

```bash
cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream kong_backend {
        server kong:8000;
        keepalive 32;
    }

    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://kong_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 5s;
            proxy_read_timeout 30s;
        }

        location /nginx_status {
            stub_status;
            allow 127.0.0.1;
            deny all;
        }
    }
}
EOF
```

### Bước 6: Tạo Prometheus config

```bash
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "kong"
    static_configs:
      - targets: ["kong:8100"]
    metrics_path: /metrics

  - job_name: "nginx"
    static_configs:
      - targets: ["nginx-edge:8080"]
    metrics_path: /nginx_status

  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
EOF
```

### Bước 7: Tạo Grafana datasource provisioning

```bash
cat > grafana-provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
EOF
```

### Bước 8: Start stack

```bash
docker compose up -d
sleep 15

echo "=== Verifying stack ==="
echo "Nginx: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:80/)"
echo "Kong: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/orders)"
echo "Kong Admin: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/)"
echo "Prometheus: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:9090/)"
echo "Grafana: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/)"
echo "Consul: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8500/)"
echo "Redis: $(docker exec redis redis-cli ping)"
```

**Expected output**: Tất cả return HTTP 200 và Redis return PONG.

---

## Exercise 1: Scenario 1 — Backend Service Down

**Mục tiêu**: Mô phỏng kill `order-service-1`. Observe Kong failover behavior.

### Hypothesis
> "Khi order-service-1 bị kill, Kong sẽ failover sang order-service-2 trong 5 giây, error rate < 0.5% trong 60 giây."

### Action

```bash
echo "=== Baseline: sending requests continuously ==="
# Start continuous request loop in background
(
  while true; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/api/v1/orders)
    echo "$(date '+%H:%M:%S') - HTTP $STATUS"
    sleep 0.5
  done
) > /tmp/order-requests.log &
REQUEST_PID=$!

sleep 5
echo "=== Baseline established ==="
tail -20 /tmp/order-requests.log

echo ""
echo "=== ACTION: Killing order-service-1 ==="
docker stop order-service-1
echo "order-service-1 stopped at $(date)"

echo ""
echo "=== Observe: Watch Kong failover (30 seconds) ==="
for i in $(seq 1 30); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/api/v1/orders)
    echo "t+${i}s - HTTP $STATUS"
    sleep 1
done

echo ""
echo "=== Check Kong upstream health ==="
curl -s http://localhost:8001/upstreams/order-upstream/healths \
  | jq '.data[] | {target, healthy, ip}'

echo ""
echo "=== Count errors from log ==="
grep -v "HTTP 200" /tmp/order-requests.log | head -20
TOTAL=$(wc -l < /tmp/order-requests.log)
ERRORS=$(grep -v "HTTP 200" /tmp/order-requests.log | wc -l)
echo "Total requests: $TOTAL, Errors: $ERRORS, Error rate: $(echo "scale=2; $ERRORS*100/$TOTAL" | bc)%"

echo ""
echo "=== Recovery: starting order-service-1 ==="
docker start order-service-1
sleep 10
kill $REQUEST_PID 2>/dev/null || true
```

### Observation Checklist

```
[ ] After kill: HTTP 200 continues (failover to order-service-2)
[ ] Error rate during failover: < 0.5% (Kong round-robin to order-service-2)
[ ] Kong upstream health: order-service-1 = unhealthy, order-service-2 = healthy
[ ] After recovery: order-service-1 becomes healthy again (passive HC)
```

### Abort Criteria

- Error rate > 5% kéo dài 2 phút → STOP experiment, restart service
- Both upstreams unhealthy → STOP, restart services

### Recovery

```bash
docker start order-service-1 order-service-2
```

---

## Exercise 2: Scenario 2 — Backend Slow (toxiproxy simulation)

**Mục tiêu**: Mô phỏng backend slow response (2s latency, 500ms jitter). Observe latency degradation.

### Hypothesis
> "Khi order-service-2 trả lời chậm ~2 giây, latency p95 tăng nhưng error rate = 0%."

### Action

```bash
echo "=== Baseline latency check ==="
echo "Measuring baseline latency (10 requests)..."
for i in $(seq 1 10); do
    time curl -s http://localhost:80/api/v1/orders > /dev/null
done 2>&1 | grep real

echo ""
echo "=== ACTION: Simulate slow backend using tc netem ==="
# Apply latency on order-service-2's port
docker exec order-service-2 sh -c "
  apk add iproute2 >/dev/null 2>&1 || true
  tc qdisc add dev eth0 root netem delay 2000ms 500ms
"
echo "Netem applied: 2000ms ± 500ms jitter on order-service-2"

echo ""
echo "=== Measure latency with slow backend (30 requests) ==="
echo "Expected: latency ~2000-2500ms, HTTP 200"
for i in $(seq 1 30); do
    START=$(date +%s%3N)
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:80/api/v1/orders)
    END=$(date +%s%3N)
    ELAPSED=$((END - START))
    echo "Request $i: HTTP $STATUS, Latency: ${ELAPSED}ms"
done

echo ""
echo "=== Recovery: remove netem ==="
docker exec order-service-2 sh -c "tc qdisc del dev eth0 root 2>/dev/null || true"
echo "Netem removed"

echo ""
echo "=== Verify normal latency restored ==="
for i in $(seq 1 5); do
    START=$(date +%s%3N)
    curl -s http://localhost:80/api/v1/orders > /dev/null
    END=$(date +%s%3N)
    echo "Request $i: Latency: $((END - START))ms"
done
```

### Observation Checklist

```
[ ] Slow backend: latency tăng 2000-2500ms (expected)
[ ] HTTP 200: no errors (slow ≠ error)
[ ] Kong retries: không trigger (vì response = 200, không timeout)
[ ] Kong timeouts: connect_timeout/write_timeout/read_timeout đủ lớn cho 2.5s
[ ] After netem removal: latency trở về normal
```

### Abort Criteria

- Latency > 10s per request → STOP, remove netem
- Error rate > 1% → STOP

---

## Exercise 3: Scenario 5 — Redis Down (rate-limit fail-open)

**Mục tiêu**: Kill Redis. Observe rate-limiting behavior khi Redis unavailable.

### Hypothesis
> "Khi Redis down và rate-limit policy = redis với fail_tolerant=true, requests được allow through (fail-open)."

### Action

```bash
echo "=== Baseline: Verify rate-limiting works ==="
echo "Sending 20 rapid requests..."
LIMITED_COUNT=0
for i in $(seq 1 20); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/orders)
    if [ "$STATUS" = "429" ]; then
        LIMITED_COUNT=$((LIMITED_COUNT + 1))
    fi
done
echo "Rate-limited requests: $LIMITED_COUNT / 20"

echo ""
echo "=== ACTION: Kill Redis ==="
docker stop redis
echo "Redis stopped at $(date)"

echo ""
echo "=== Measure rate-limiting during Redis failure ==="
echo "Sending 20 rapid requests with Redis down..."
LIMITED_AFTER=0
ERRORS_AFTER=0
for i in $(seq 1 20); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/orders)
    echo "Request $i: HTTP $STATUS"
    if [ "$STATUS" = "429" ]; then
        LIMITED_AFTER=$((LIMITED_AFTER + 1))
    elif [ "$STATUS" = "500" ]; then
        ERRORS_AFTER=$((ERRORS_AFTER + 1))
    fi
done

echo ""
echo "=== Results ==="
echo "Rate-limited (429): $LIMITED_AFTER / 20"
echo "Server errors (500): $ERRORS_AFTER / 20"
echo "Allowed (200): $((20 - LIMITED_AFTER - ERRORS_AFTER)) / 20"
echo ""
echo "Interpretation:"
if [ "$ERRORS_AFTER" -gt 15 ]; then
    echo "  → fail-close: majority of requests blocked with 500 (secure)"
else
    echo "  → fail-open: majority of requests allowed through (available)"
fi

echo ""
echo "=== Recovery: Start Redis ==="
docker start redis
sleep 5
echo "Redis restarted"

echo ""
echo "=== Verify rate-limiting restored ==="
LIMITED_RESTORED=0
for i in $(seq 1 10); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/orders)
    if [ "$STATUS" = "429" ]; then
        LIMITED_RESTORED=$((LIMITED_RESTORED + 1))
    fi
done
echo "Rate-limited after Redis restore: $LIMITED_RESTORED / 10"
```

### Observation Checklist

```
[ ] Redis down + fail_tolerant=true: requests allowed (fail-open)
[ ] Redis down + fail_tolerant=false: requests denied with 500 (fail-close)
[ ] After Redis restore: rate-limiting resumes normal operation
```

### Abort Criteria

- Server returning 500 for > 80% requests → STOP, restart Redis

---

## Exercise 4: Scenario 9 — Retry Storm

**Mục tiêu**: Bật retries=5 + slow upstream → observe load increase 6×.

### Hypothesis
> "Với retries=5 và upstream trả 5xx 30%, effective upstream load tăng 6× baseline."

### Action

```bash
echo "=== Setup: Create a backend that returns 500 for some requests ==="
# Temporarily update order-service-1 to return 500
cat > mocks/order-v1-500.json << 'EOF'
{
  "httpRequest": { "path": "/orders" },
  "httpResponse": {
    "statusCode": 500,
    "body": "{\"error\":\"internal error\"}"
  }
}
EOF

echo "=== Capture baseline Prometheus metrics ==="
curl -s http://localhost:9090/api/v1/query \
  --data-urlencode 'query=rate(kong_http_requests_total{service="order-service"}[1m])' \
  | jq -r '.data.result[0].value[1]'

echo ""
echo "=== ACTION: Simulate retry storm ==="
echo "Step 1: Update Kong service retries to 5"
curl -s -X PATCH http://localhost:8001/services/order-service \
  -d retries=5 | jq '{retries}'

echo ""
echo "Step 2: Inject 500 errors into order-service-1"
docker stop order-service-1
docker rm order-service-1
docker run -d \
  --name order-service-1 \
  -e MOCKSERVER_INITIALIZATION_JSON_PATH=/config/order-500.json \
  -v $(pwd)/mocks:/config:ro \
  -p 8081:1080 \
  mockserver/mockserver:5.15.0

cat > mocks/order-500.json << 'EOF'
{
  "httpRequest": { "path": "/orders" },
  "httpResponse": {
    "statusCode": 500,
    "body": "{\"error\":\"simulated failure\"}"
  }
}
EOF

docker stop order-service-1
docker rm order-service-1
docker create \
  --name order-service-1 \
  -e MOCKSERVER_INITIALIZATION_JSON_PATH=/config/order-500.json \
  -v $(pwd)/mocks:/config:ro \
  -p 8081:1080 \
  mockserver/mockserver:5.15.0

cat > mocks/order-500.json << 'EOF'
{
  "httpRequest": { "path": "/orders" },
  "httpResponse": {
    "statusCode": 500,
    "body": "{\"error\":\"simulated failure\"}"
  }
}
EOF

docker run -d \
  --name order-service-1 \
  -e MOCKSERVER_INITIALIZATION_JSON_PATH=/config/order-500.json \
  -v $(pwd)/mocks:/config:ro \
  --network gateway-chaos_gateway-net \
  -p 8081:1080 \
  mockserver/mockserver:5.15.0

sleep 5

echo ""
echo "Step 3: Generate 50 requests and observe behavior"
echo "(Watch order-service-2 load — should be 6× due to retries)"
FAILED=0
for i in $(seq 1 50); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/orders)
    if [ "$STATUS" = "500" ] || [ "$STATUS" = "502" ] || [ "$STATUS" = "503" ]; then
        FAILED=$((FAILED + 1))
    fi
done
echo "Failed requests: $FAILED / 50 (error rate: $((FAILED * 2))%)"

echo ""
echo "=== Recovery: restore retries to 0 ==="
curl -s -X PATCH http://localhost:8001/services/order-service \
  -d retries=0 | jq '{retries}'

echo "=== Restore order-service-1 ==="
docker stop order-service-1
docker rm order-service-1
docker run -d \
  --name order-service-1 \
  -e MOCKSERVER_INITIALIZATION_JSON_PATH=/config/order-expectation.json \
  -v $(pwd)/mocks:/config:ro \
  --network gateway-chaos_gateway-net \
  -p 8081:1080 \
  mockserver/mockserver:5.15.0
sleep 5
```

### Observation Checklist

```
[ ] retries=5 + 500 error: Kong retries up to 5 times
[ ] Effective upstream load: 6× (1 original + 5 retries)
[ ] With retries=0: no retry, error propagates directly to client
[ ] After recovery: system returns to normal
```

---

## Exercise 5: k6 Benchmark Script — Full Workload Suite

**Mục tiêu**: Viết và chạy k6 script đầy đủ 4 workload models (smoke, load, stress, spike).

### Bước 1: Tạo k6 script

```bash
cat > k6-benchmark.js << 'EOF'
// k6-benchmark.js — Full workload suite cho Day 21 capstone
// Run: k6 run k6-benchmark.js
// Or with thresholds: k6 run --env SCENARIO=smoke k6-benchmark.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const serviceLatency = new Trend('service_latency');
const kongProxyLatency = new Trend('kong_proxy_latency');
const upstreamLatency = new Trend('upstream_latency');

// Scenario configuration
const SCENARIO = __ENV.SCENARIO || 'smoke';
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Scenario configurations
const scenarios = {
  smoke: {
    vus: 5,
    duration: '30s',
    target: 10, // RPS target
  },
  load: {
    vus: 100,
    duration: '5m',
    target: 100,
  },
  stress: {
    vus: 200,
    duration: '3m',
    target: 200,
  },
  spike: {
    vus: 50,
    stageDuration: '1m',
    spikeVUs: 500,
    spikeDuration: '30s',
    target: 500,
  },
};

const cfg = scenarios[SCENARIO] || scenarios.smoke;

export const options = {
  scenarios: {
    smoke: SCENARIO === 'smoke' ? {
      executor: 'constant-vus',
      vus: cfg.vus,
      duration: cfg.duration,
    } : undefined,

    load: SCENARIO === 'load' ? {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: cfg.vus,
      maxVUs: cfg.vus * 2,
      stages: [
        { duration: '2m', target: cfg.target },
        { duration: cfg.duration, target: cfg.target },
        { duration: '1m', target: 0 },
      ],
    } : undefined,

    stress: SCENARIO === 'stress' ? {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: cfg.vus,
      maxVUs: cfg.vus * 3,
      stages: [
        { duration: '2m', target: cfg.target },
        { duration: cfg.duration, target: cfg.target },
        { duration: '1m', target: 0 },
      ],
    } : undefined,

    spike: SCENARIO === 'spike' ? {
      executor: 'ramping-vus',
      startVUs: cfg.vus,
      stages: [
        { duration: cfg.stageDuration, target: cfg.vus },
        { duration: cfg.spikeDuration, target: cfg.spikeVUs },
        { duration: '1m', target: 0 },
      ],
    } : undefined,
  },

  thresholds: {
    'http_req_duration': ['p(95)<1000', 'p(99)<3000'],
    'errors': ['rate<0.05'],
    'service_latency': ['avg<500'],
  },

  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'p(99.9)'],
};

export default function () {
  const url = `${BASE_URL}/api/v1/orders`;

  const res = http.get(url, {
    tags: { name: 'order-service', scenario: SCENARIO },
  });

  // Extract Kong latency headers
  const proxyLat = parseFloat(res.headers['X-Kong-Proxy-Latency'] || '0');
  const upstreamLat = parseFloat(res.headers['X-Kong-Upstream-Latency'] || '0');
  kongProxyLatency.add(proxyLat);
  upstreamLatency.add(upstreamLat);
  serviceLatency.add(res.timings.duration);

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 3s': (r) => r.timings.duration < 3000,
    'has response body': (r) => r.body && r.body.length > 0,
  });

  errorRate.add(!ok);

  sleep(1);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'summary.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, opts) {
  const indent = opts.indent || '';
  const out = [];
  out.push('\n' + indent + '=== k6 Benchmark Summary ===');
  out.push(indent + `Scenario: ${SCENARIO}`);
  out.push(indent + `Duration: ${data.metrics.http_req_duration.values?.count || 0} requests`);

  const latency = data.metrics.http_req_duration?.values;
  if (latency) {
    out.push(indent + `Latency p50: ${latency['p(50)']?.toFixed(2)}ms`);
    out.push(indent + `Latency p95: ${latency['p(95)']?.toFixed(2)}ms`);
    out.push(indent + `Latency p99: ${latency['p(99)']?.toFixed(2)}ms`);
  }

  const errors = data.metrics.errors?.values;
  if (errors) {
    out.push(indent + `Error rate: ${(errors.rate * 100).toFixed(2)}%`);
  }

  return out.join('\n');
}
EOF

echo "k6-benchmark.js created"
```

### Bước 2: Chạy Smoke Test

```bash
echo "=== Running Smoke Test ==="
k6 run k6-benchmark.js --env SCENARIO=smoke --summary-export=smoke-results.json 2>&1 | tee smoke-output.txt

echo ""
echo "=== Smoke Results ==="
cat smoke-output.txt | grep -E "smoke|p50|p95|p99|error|requests"
```

### Bước 3: Chạy Load Test

```bash
echo "=== Running Load Test (5 minutes) ==="
k6 run k6-benchmark.js \
  --env SCENARIO=load \
  --summary-export=load-results.json \
  2>&1 | tee load-output.txt

echo ""
echo "=== Load Results Summary ==="
cat load-output.txt | grep -E "load|p50|p95|p99|error|RPS"
```

### Bước 4: Chạy Stress Test

```bash
echo "=== Running Stress Test (3 minutes) ==="
k6 run k6-benchmark.js \
  --env SCENARIO=stress \
  --summary-export=stress-results.json \
  2>&1 | tee stress-output.txt

echo ""
echo "=== Stress Results Summary ==="
cat stress-output.txt | grep -E "stress|p50|p95|p99|error|requests"
```

### Bước 5: Chạy Spike Test

```bash
echo "=== Running Spike Test (2.5 minutes) ==="
k6 run k6-benchmark.js \
  --env SCENARIO=spike \
  --summary-export=spike-results.json \
  2>&1 | tee spike-output.txt

echo ""
echo "=== Spike Results Summary ==="
cat spike-output.txt | grep -E "spike|p50|p95|p99|error"
```

### Bước 6: Generate Markdown Report

```bash
cat > generate-report.sh << 'EOF'
#!/bin/bash
# generate-report.sh — Convert k6 results to markdown benchmark report

echo "# Benchmark Report — Day 21 Capstone"
echo "**Date**: $(date '+%Y-%m-%d')"
echo "**Environment**: Local Docker Compose"
echo ""
echo "## Results Summary"
echo ""
echo "| Scenario | RPS | p50 | p95 | p99 | Error% |"
echo "|---|---|---|---|---|---|"

for scenario in smoke load stress spike; do
    FILE="${scenario}-results.json"
    if [ -f "$FILE" ]; then
        COUNT=$(jq -r '.metrics.http_req_duration.values.count' "$FILE" 2>/dev/null || echo "N/A")
        RPS=$(jq -r "(${COUNT} / $(jq -r '.metrics.http_req_duration.values.thresholds."http_req_duration.values.count"' "$FILE" 2>/dev/null || echo 1))" "$FILE" 2>/dev/null || echo "N/A")
        P50=$(jq -r '.metrics.http_req_duration.values["p(50)"]' "$FILE" 2>/dev/null || echo "N/A")
        P95=$(jq -r '.metrics.http_req_duration.values["p(95)"]' "$FILE" 2>/dev/null || echo "N/A")
        P99=$(jq -r '.metrics.http_req_duration.values["p(99)"]' "$FILE" 2>/dev/null || echo "N/A")
        ERR=$(jq -r '.metrics.errors.values.rate' "$FILE" 2>/dev/null || echo "0")
        echo "| $scenario | ~$COUNT req | ${P50}ms | ${P95}ms | ${P99}ms | $(echo "scale=2; $ERR * 100" | bc)% |"
    else
        echo "| $scenario | N/A | N/A | N/A | N/A | N/A |"
    fi
done

echo ""
echo "## Recommendations"
echo ""
echo "1. **Scale up**: Consider adding more backend replicas for higher throughput"
echo "2. **Monitor latency**: p95 > 500ms triggers autoscale in production"
echo "3. **Error budget**: Error rate < 0.1% is within SLO 99.9%"
echo ""
echo "> **Disclaimer**: Số liệu chỉ tham khảo. Benchmark trên local Docker."
echo "> Kết quả production phụ thuộc hardware, network, workload pattern."
EOF

chmod +x generate-report.sh
./generate-report.sh > benchmark-report.md
cat benchmark-report.md
```

---

## Exercise 6: Final Retrospective Worksheet

**Mục tiêu**: Self-assessment 5 câu hỏi sau khi hoàn thành toàn bộ Day 21.

### Câu hỏi 1: Resilience Testing

```
1. Ba tầng resilience testing (Component / Integration / Chaos) khác nhau thế nào?
   Component: [viet vao day]
   Integration: [viet vao day]
   Chaos: [viet vao day]

2. Cho ví dụ một failure scenario bạn đã thực hành và điều gì xảy ra:
   [viet vao day]

3. Bạn đã observe được behavior gì mà không có trong theory?
   [viet vao day]
```

### Câu hỏi 2: Benchmark

```
4. Tại sao dùng k6 constant-arrival-rate thay vì wrk để benchmark?
   [viet vao day]

5. 4 workload models (smoke/load/stress/spike) khác nhau thế nào?
   Smoke: [viet vao day]
   Load: [viet vao day]
   Stress: [viet vao day]
   Spike: [viet vao day]

6. Coordinated omission là gì? Tại sao nó quan trọng?
   [viet vao day]
```

### Câu hỏi 3: Capacity Planning

```
7. Nếu target là 10,000 RPS và benchmark đạt 8,000 RPS trên 1 stack unit,
   bạn cần bao nhiêu stack units với 30% headroom?
   Đáp án: [tinh toan va viet vao day]

8. Autoscale trigger nên đặt ở % nào của max capacity? Tại sao?
   [viet vao day]
```

### Câu hỏi 4: Anti-patterns

```
9. Nêu 2 anti-pattern trong chaos engineering mà bại đã thấy:
   1. [viet vao day]
   2. [viet vao day]

10. Tại sao không nên benchmark trên dev laptop cho production sizing?
    [viet vao day]
```

### Câu hỏi 5: Course Completion

```
11. Day nào trong khóa học bạn thấy KHÓ NHẤT? Tại sao?
    [viet vao day]

12. Day nào bạn thấy HAY NHẤT (áp dụng được ngay vào thực tế)?
    [viet vao day]

13. Một kỹ năng/knowledge gap nào bạn nhận ra còn thiếu sau khóa học?
    [viet vao day]

14. Bạn sẽ học gì tiếp theo? (Istio / Kong Mesh / Kubernetes / eBPF / ...)
    [viet vao day]
```

### Certificate of Completion Checklist

```
Day 1-21 Course Completion Self-Check:
=====================================

Infrastructure Basics:
  [ ] Dựng được Nginx reverse proxy
  [ ] Hiểu được upstream, load balancing
  [ ] Debug được 502/503/504

Kong Gateway:
  [ ] Dựng được Kong DB-less
  [ ] Configure được Service/Route/Consumer/Plugin
  [ ] Quản lý được config bằng decK

Production Readiness:
  [ ] Configure được timeout/retry strategy
  [ ] Implement được canary/blue-green deployment
  [ ] Setup được Prometheus/Grafana monitoring
  [ ] Integrate được Consul service discovery

Testing & Validation:
  [ ] Chạy được k6 benchmark (smoke/load/stress/spike)
  [ ] Viết được benchmark report
  [ ] Tính được capacity planning
  [ ] Chạy được ít nhất 3 chaos scenarios

Final Skills:
  [ ] Hiểu được chaos engineering principles
  [ ] Nhận diện được anti-patterns
  [ ] Biết đường học tiếp theo

If you have checked ALL items above:
  → Congratulations! You have completed the 21-day course.
  → You are now a certified Gateway & Load Balancer Engineer.
```

---

## Cleanup

```bash
cd ~/gateway-chaos

echo "=== Stopping all containers ==="
docker compose down

echo "=== Removing lab files ==="
cd ~ && rm -rf ~/gateway-chaos

echo "=== Cleanup complete ==="
```

---

## Tổng Kết Exercises

| Exercise | Topic | Tools | Deliverable |
|---|---|---|---|
| 0 | Capstone setup | Docker Compose | Running stack |
| 1 | Backend down (failover) | docker stop | Kong failover behavior |
| 2 | Backend slow (netem) | tc netem | Latency degradation |
| 3 | Redis down (fail-open) | docker stop | Rate-limit behavior |
| 4 | Retry storm | Kong retries | Load multiplier effect |
| 5 | k6 benchmark suite | k6 | benchmark-report.md |
| 6 | Retrospective worksheet | Self-assessment | Certificate checklist |
