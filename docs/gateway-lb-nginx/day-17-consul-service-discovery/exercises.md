# Day 17: Exercises — Consul Service Discovery Hands-on Lab

> **Yêu cầu**: Docker, Docker Compose, curl, jq, dig (dnsutils), Consul 1.18+
> **Consul version**: 1.18+
> **Thời gian ước tính**: 90-120 phút
> **Note**: Tất cả Exercise dùng chung Docker Compose setup từ Exercise 0.

---

## Exercise 0: Setup — Docker Compose Consul Cluster

**Mục tiêu**: Dựng Consul cluster gồm 1 server agent + 2 client agent + 2 backend service (order, payment). Đây là base cho tất cả Exercise 1-5.

### Bước 1: Tạo directory và cấu trúc

```bash
mkdir -p ~/consul-lab/mocks ~/consul-lab/configs && cd ~/consul-lab
```

### Bước 2: Tạo Consul server config

```bash
cat > configs/consul-server.json << 'EOF'
{
  "server": true,
  "bootstrap_expect": 1,
  "ui_config": {
    "enabled": true
  },
  "data_dir": "/consul/data",
  "bind_addr": "{{ GetInterfaceIP \"eth0\" }}",
  "advertise_addr": "{{ GetInterfaceIP \"eth0\" }}",
  "client_addr": "0.0.0.0",
  "ports": {
    "dns": 8600,
    "http": 8500,
    "serf_lan": 8301,
    "serf_wan": 8302,
    "server": 8300
  },
  "recursors": ["8.8.8.8", "8.8.4.4"],
  "dns_config": {
    "allow_stale": true,
    "max_stale": "200s",
    "enable_truncate": true,
    "only_passing": false,
    "ttl": {
      "a": "0s",
      "srv": "0s",
      "cname": "0s"
    }
  },
  "log_level": "info",
  "enable_syslog": false,
  "enable_debug": false
}
EOF
```

### Bước 3: Tạo Consul client config

```bash
cat > configs/consul-client.json << 'EOF'
{
  "server": false,
  "data_dir": "/consul/data",
  "bind_addr": "{{ GetInterfaceIP \"eth0\" }}",
  "advertise_addr": "{{ GetInterfaceIP \"eth0\" }}",
  "client_addr": "0.0.0.0",
  "ports": {
    "dns": 8600,
    "http": 8500,
    "serf_lan": 8301
  },
  "retry_join": ["consul-server"],
  "dns_config": {
    "allow_stale": true,
    "only_passing": false,
    "ttl": {
      "a": "0s",
      "srv": "0s"
    }
  },
  "log_level": "info",
  "enable_syslog": false
}
EOF
```

### Bước 4: Tạo backend mock service config

```bash
# order-service mock (MockServer)
cat > mocks/order-expectation.json << 'EOF'
{
  "httpRequest": { "path": "/health" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"status\":\"healthy\",\"service\":\"order\"}",
    "headers": { "Content-Type": ["application/json"] }
  }
}
EOF

cat > mocks/order-api.json << 'EOF'
{
  "httpRequest": { "path": "/api/orders" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"order_id\":\"ORD-001\",\"status\":\"created\"}",
    "headers": { "X-Service": ["order-service"] }
  }
}
EOF

# payment-service mock
cat > mocks/payment-expectation.json << 'EOF'
{
  "httpRequest": { "path": "/health" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"status\":\"healthy\",\"service\":\"payment\"}",
    "headers": { "Content-Type": ["application/json"] }
  }
}
EOF

cat > mocks/payment-api.json << 'EOF'
{
  "httpRequest": { "path": "/api/payments" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"payment_id\":\"PAY-001\",\"status\":\"pending\"}",
    "headers": { "X-Service": ["payment-service"] }
  }
}
EOF
```

### Bước 5: Tạo docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"
services:
  # =============================================
  # Consul Server Agent (Raft leader)
  # =============================================
  consul-server:
    image: hashicorp/consul:1.18
    container_name: consul-server
    hostname: consul-server
    command: agent -config-file=/consul/config/consul-server.json
    volumes:
      - ./configs/consul-server.json:/consul/config/consul-server.json:ro
      - consul-server-data:/consul/data
    ports:
      - "8500:8500"   # HTTP API
      - "8600:8600/udp" # DNS
      - "8600:8600/tcp" # DNS fallback for large responses
    networks:
      - consul-lab
    healthcheck:
      test: ["CMD", "consul", "info"]
      interval: 10s
      timeout: 5s
      retries: 5

  # =============================================
  # Consul Client Agent 1 (order-service node)
  # =============================================
  consul-client-1:
    image: hashicorp/consul:1.18
    container_name: consul-client-1
    hostname: consul-client-1
    command: agent -config-file=/consul/config/consul-client.json
    volumes:
      - ./configs/consul-client.json:/consul/config/consul-client.json:ro
      - consul-client-1-data:/consul/data
    networks:
      - consul-lab
    depends_on:
      consul-server:
        condition: service_healthy

  # =============================================
  # Consul Client Agent 2 (payment-service node)
  # =============================================
  consul-client-2:
    image: hashicorp/consul:1.18
    container_name: consul-client-2
    hostname: consul-client-2
    command: agent -config-file=/consul/config/consul-client.json
    volumes:
      - ./configs/consul-client.json:/consul/config/consul-client.json:ro
      - consul-client-2-data:/consul/data
    networks:
      - consul-lab
    depends_on:
      consul-server:
        condition: service_healthy

  # =============================================
  # order-service backend (MockServer)
  # =============================================
  order-backend:
    image: mockserver/mockserver:5.15.0
    container_name: order-backend
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/init.json
    volumes:
      - ./mocks/order-expectation.json:/config/init.json:ro
      - ./mocks/order-api.json:/config/api.json:ro
    ports:
      - "8081:1080"
    networks:
      - consul-lab
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:1080/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 3

  # =============================================
  # payment-service backend (MockServer)
  # =============================================
  payment-backend:
    image: mockserver/mockserver:5.15.0
    container_name: payment-backend
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/init.json
    volumes:
      - ./mocks/payment-expectation.json:/config/init.json:ro
      - ./mocks/payment-api.json:/config/api.json:ro
    ports:
      - "8082:1080"
    networks:
      - consul-lab
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:1080/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 3

  # =============================================
  # dig client (test DNS)
  # =============================================
  dig-client:
    image: alpine:3.19
    container_name: dig-client
    command: sleep infinity
    networks:
      - consul-lab

networks:
  consul-lab:
    driver: bridge

volumes:
  consul-server-data:
  consul-client-1-data:
  consul-client-2-data:
EOF
```

### Bước 6: Start cluster

```bash
cd ~/consul-lab
docker compose up -d

# Wait for Consul server to be healthy
echo "Waiting for Consul server..."
sleep 10
docker compose ps

# Verify Consul is running
curl -sf http://localhost:8500/v1/status/leader | jq .
curl -sf http://localhost:8500/v1/status/peers | jq .
```

**Expected output**:
```
# curl http://localhost:8500/v1/status/leader
"127.0.0.1:8300"

# curl http://localhost:8500/v1/status/peers
["127.0.0.1:8300"]
```

**Lỗi thường gặp**:

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| "Failed to join" | Client start trước server ready | `depends_on` với `condition: service_healthy` |
| 8500 connection refused | Consul server chưa start xong | `sleep 10` sau khi up |
| peers = [] | Server chưa elect leader | Chờ thêm 10s, check `curl http://localhost:8500/v1/status/leader` |

---

## Exercise 1: Service Registration via HTTP API

**Mục tiêu**: Register `order-service` và `payment-service` qua Consul HTTP API, verify bằng API và DNS.

### Bước 1: Get backend IP addresses

```bash
# Lấy IP của backend containers
ORDER_IP=$(docker inspect order-backend -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
PAYMENT_IP=$(docker inspect payment-backend -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

echo "order-backend IP: ${ORDER_IP}"
echo "payment-backend IP: ${PAYMENT_IP}"
```

### Bước 2: Register order-service (HTTP health check)

```bash
# Register order-service với HTTP health check
curl -s -X PUT http://localhost:8500/v1/agent/service/register \
  -d "{
    \"ID\": \"order-service-1\",
    \"Name\": \"order-service\",
    \"Tags\": [\"prod\", \"api\", \"v1\"],
    \"Address\": \"${ORDER_IP}\",
    \"Port\": 1080,
    \"Meta\": {
      \"version\": \"1.2.3\",
      \"environment\": \"production\"
    },
    \"Check\": {
      \"id\": \"order-health-1\",
      \"HTTP\": \"http://${ORDER_IP}:1080/health\",
      \"Interval\": \"10s\",
      \"Timeout\": \"5s\",
      \"DeregisterCriticalServiceAfter\": \"30s\"
    }
  }"

echo "order-service registered"
```

### Bước 3: Register payment-service (HTTP health check)

```bash
# Register payment-service với HTTP health check
curl -s -X PUT http://localhost:8500/v1/agent/service/register \
  -d "{
    \"ID\": \"payment-service-1\",
    \"Name\": \"payment-service\",
    \"Tags\": [\"prod\", \"api\", \"v1\"],
    \"Address\": \"${PAYMENT_IP}\",
    \"Port\": 1080,
    \"Meta\": {
      \"version\": \"2.0.0\",
      \"environment\": \"production\"
    },
    \"Check\": {
      \"id\": \"payment-health-1\",
      \"HTTP\": \"http://${PAYMENT_IP}:1080/health\",
      \"Interval\": \"10s\",
      \"Timeout\": \"5s\",
      \"DeregisterCriticalServiceAfter\": \"30s\"
    }
  }"

echo "payment-service registered"
```

### Bước 4: Verify registration qua API

```bash
echo "=== List all registered services ==="
curl -s http://localhost:8500/v1/agent/services | jq 'keys'

echo ""
echo "=== order-service details ==="
curl -s http://localhost:8500/v1/agent/services | jq '.["order-service-1"]'

echo ""
echo "=== Health checks ==="
curl -s http://localhost:8500/v1/agent/checks | jq '.'

echo ""
echo "=== Health check status ==="
curl -s 'http://localhost:8500/v1/health/service/order-service?passing=true' \
  | jq '.[].Service | {Name, Address, Port, ID}'
```

### Bước 5: Verify DNS A record

```bash
echo "=== DNS A record for order-service ==="
dig @localhost -p 8600 +short order-service.service.consul

echo ""
echo "=== Full DNS response ==="
dig @localhost -p 8600 order-service.service.consul

echo ""
echo "=== DNS A record for payment-service ==="
dig @localhost -p 8600 +short payment-service.service.consul
```

### Bước 6: Verify DNS SRV record

```bash
echo "=== DNS SRV record for order-service (IP + Port) ==="
dig @localhost -p 8600 order-service.service.consul SRV

echo ""
echo "=== DNS SRV record for payment-service ==="
dig @localhost -p 8600 payment-service.service.consul SRV

echo ""
echo "=== Tag-filtered DNS (prod) ==="
dig @localhost -p 8600 prod.order-service.service.consul SRV
```

**Expected outputs**:
```
# dig @localhost -p 8600 order-service.service.consul SRV
;; ANSWER SECTION:
order-service.service.consul.  300  IN  SRV  10  100  1080  consul-client-1.node.dc1.consul.

;; ADDITIONAL SECTION:
consul-client-1.node.dc1.consul. 300 IN A 172.x.x.x
```

**Lỗi thường gặp**:

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Service not appearing | Backend health check fail | `curl http://IP:1080/health` để verify |
| DNS NXDOMAIN | Sai datacenter suffix | Thêm `.dc1` hoặc dùng `+search` |
| Health check always fail | Port nhầm (1080 vs 8081) | Verify port mapping trong docker-compose |

---

## Exercise 2: Service Registration via Config File

**Mục tiêu**: Register `notification-service` bằng config file thay vì API, để so sánh hai phương pháp.

### Bước 1: Tạo service config file

```bash
mkdir -p ~/consul-lab/services

cat > configs/notification-service.json << 'EOF'
{
  "service": {
    "id": "notification-service-1",
    "name": "notification-service",
    "tags": ["prod", "batch", "v1"],
    "address": "consul-client-2",
    "port": 0,
    "meta": {
      "version": "1.0.0",
      "type": "batch"
    },
    "check": {
      "id": "notification-health",
      "name": "Notification service health",
      "notes": "Batch job — no HTTP port exposed, using TTL check",
      "ttl": "30s"
    }
  }
}
EOF
```

### Bước 2: Copy config vào Consul client 2

```bash
# Copy config vào client container
docker cp configs/notification-service.json consul-client-2:/consul/config/

# Reload Consul client 2 để đọc config file
docker exec consul-client-2 consul reload

# Chờ 5s để config được apply
sleep 5
```

### Bước 3: Register TTL check (send heartbeat)

```bash
# TTL check: service phải gửi heartbeat định kỳ
# Trong lab: dùng docker exec từ backend để simulate heartbeat
docker exec -d consul-client-2 sh -c '
while true; do
  curl -sf -X PUT http://localhost:8500/v1/agent/check/pass/service:notification-health || true
  sleep 10
done
'

echo "TTL check heartbeat started"
```

### Bước 4: Verify notification-service registration

```bash
echo "=== List services on consul-client-2 ==="
curl -s http://localhost:8500/v1/agent/services | jq 'keys'

echo ""
echo "=== notification-service details ==="
curl -s http://localhost:8500/v1/agent/services | jq '.["notification-service-1"]'

echo ""
echo "=== Verify via catalog API ==="
curl -s http://localhost:8500/v1/catalog/services | jq .

echo ""
echo "=== DNS query ==="
dig @localhost -p 8600 +short notification-service.service.consul
```

### Bước 5: Compare HTTP API vs Config File

```bash
echo "=== Comparison: HTTP API vs Config File ==="
echo ""
echo "HTTP API registration:"
echo "  - Dynamic: đăng ký khi service start"
echo "  - Ephemeral: service stop → tự deregister"
echo "  - Programmatic: dùng được trong code"
echo "  - Use case: microservices, auto-scaling"
echo ""
echo "Config file registration:"
echo "  - Static: phải reload Consul khi thêm service"
echo "  - Persistent: service config nằm trong config file"
echo "  - Declarative: toàn bộ desired state trong file"
echo "  - Use case: sidecar service, fixed set of services"
```

---

## Exercise 3: Health Check Behavior — Kill & Restore Service

**Mục tiêu**: Quan sát Consul behavior khi backend chết: health check fail → service deregister → DNS update.

### Bước 1: Baseline — Verify both services healthy

```bash
echo "=== Baseline: healthy services ==="
curl -s 'http://localhost:8500/v1/health/service/order-service?passing=true' \
  | jq 'length'

curl -s 'http://localhost:8500/v1/health/service/payment-service?passing=true' \
  | jq 'length'

dig @localhost -p 8600 order-service.service.consul SRV +short
```

### Bước 2: Kill order-backend → observe health check fail

```bash
# Kill order-backend container
echo "=== Killing order-backend ==="
docker stop order-backend

# Wait cho health check interval (10s) + deregister timeout (30s)
echo "Waiting 35 seconds for Consul to detect failure..."
sleep 35

echo "=== Health check after kill ==="
curl -s http://localhost:8500/v1/agent/checks | jq '.["service:order-service-1"] | {Status, Output}'

echo ""
echo "=== Catalog service count ==="
curl -s 'http://localhost:8500/v1/health/service/order-service?passing=true' \
  | jq 'length'

echo ""
echo "=== DNS after kill (should be empty or NXDOMAIN) ==="
dig @localhost -p 8600 order-service.service.consul SRV +short
dig @localhost -p 8600 order-service.service.consul +short
```

**Expected behavior**:
```
# Health check: Status = critical (after 35s)
# Catalog: length = 0 (deregistered)
# DNS: empty (no record)
```

### Bước 3: Restore order-backend → observe re-registration

```bash
# Restore order-backend
echo "=== Restoring order-backend ==="
docker start order-backend

# Wait cho health check pass (10s interval × 1 success = ~10s)
echo "Waiting 15 seconds for Consul to detect recovery..."
sleep 15

echo "=== Health check after restore ==="
curl -s http://localhost:8500/v1/agent/checks | jq '.["service:order-service-1"] | {Status, Output}'

echo ""
echo "=== Catalog service after restore ==="
curl -s 'http://localhost:8500/v1/health/service/order-service?passing=true' \
  | jq '.[].Service | {Name, Address, Port}'

echo ""
echo "=== DNS after restore ==="
dig @localhost -p 8600 order-service.service.consul SRV +short
```

**Expected behavior**:
```
# Health check: Status = passing (after ~10s)
# Catalog: length = 1
# DNS: IP address returned
```

### Bước 4: Simulate slow health check (service slow but not down)

```bash
echo "=== Simulating slow health check ==="
# Create a mock that delays response
cat > mocks/order-slow.json << 'EOF'
{
  "httpRequest": { "path": "/health-slow" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"status\":\"ok\"}",
    "headers": { "Content-Type": ["application/json"] },
    "delay": {
      "delayMillis": 8000
    }
  }
}
EOF

# Register với timeout ngắn (5s) — 8s response sẽ fail
ORDER_IP=$(docker inspect order-backend -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

# Update health check với timeout ngắn
curl -s -X PUT http://localhost:8500/v1/agent/service/deregister/order-service-1

curl -s -X PUT http://localhost:8500/v1/agent/service/register \
  -d "{
    \"ID\": \"order-service-1\",
    \"Name\": \"order-service\",
    \"Tags\": [\"prod\", \"api\", \"v1\"],
    \"Address\": \"${ORDER_IP}\",
    \"Port\": 1080,
    \"Check\": {
      \"id\": \"order-health-1\",
      \"HTTP\": \"http://${ORDER_IP}:1080/health-slow\",
      \"Interval\": \"10s\",
      \"Timeout\": \"3s\",
      \"DeregisterCriticalServiceAfter\": \"30s\"
    }
  }"

echo "Slow health check registered (timeout=3s, response=8s)"

# Copy slow mock
docker cp mocks/order-slow.json order-backend:/config/slow.json

sleep 15

echo "=== Health check status after slow test ==="
curl -s http://localhost:8500/v1/agent/checks | jq '.["service:order-service-1"] | {Status, Output}'
```

---

## Exercise 4: Tag-Based Filtering & Catalog Queries

**Mục tiêu**: Sử dụng tags để phân nhóm service và query theo tag.

### Bước 1: Register service với nhiều tags

```bash
# Register order-service với nhiều tags
PAYMENT_IP=$(docker inspect payment-backend -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

curl -s -X PUT http://localhost:8500/v1/agent/service/register \
  -d "{
    \"ID\": \"payment-service-1\",
    \"Name\": \"payment-service\",
    \"Tags\": [\"prod\", \"api\", \"v1\", \"critical\"],
    \"Address\": \"${PAYMENT_IP}\",
    \"Port\": 1080,
    \"Check\": {
      \"HTTP\": \"http://${PAYMENT_IP}:1080/health\",
      \"Interval\": \"10s\",
      \"Timeout\": \"5s\",
      \"DeregisterCriticalServiceAfter\": \"30s\"
    }
  }"

echo "payment-service registered with tags: prod, api, v1, critical"
```

### Bước 2: Query by tag

```bash
echo "=== Query by single tag (prod) ==="
curl -s 'http://localhost:8500/v1/health/service/order-service?passing=true&tag=prod' \
  | jq '.[].Service | {Name, Tags, Address, Port}'

echo ""
echo "=== Query by tag (critical) ==="
curl -s 'http://localhost:8500/v1/health/service/payment-service?passing=true&tag=critical' \
  | jq '.[].Service | {Name, Tags, Address, Port}'

echo ""
echo "=== Query all services in catalog ==="
curl -s http://localhost:8500/v1/catalog/services | jq .
```

### Bước 3: DNS tag filtering

```bash
echo "=== DNS with tag prefix ==="
dig @localhost -p 8600 prod.order-service.service.consul SRV +short
dig @localhost -p 8600 prod.payment-service.service.consul SRV +short

echo ""
echo "=== DNS without tag (all instances) ==="
dig @localhost -p 8600 order-service.service.consul SRV +short
dig @localhost -p 8600 payment-service.service.consul SRV +short
```

### Bước 4: Query service metadata

```bash
echo "=== Query service metadata ==="
curl -s 'http://localhost:8500/v1/health/service/order-service?passing=true' \
  | jq '.[].Service | {Name, Meta, Tags}'

echo ""
echo "=== Query catalog with metadata ==="
curl -s http://localhost:8500/v1/catalog/service/order-service \
  | jq '.[].ServiceMeta'
```

---

## Exercise 5: Blocking Query & Watch Pattern

**Mục tiêu**: Thực hành blocking query để hiểu cơ chế long-polling của Consul.

### Bước 1: Manual blocking query

```bash
# Blocking query: Consul giữ request 60s hoặc đến khi state change
echo "=== Starting blocking query (60s wait) ==="
echo "This will return when order-service state changes..."

# Get current index
INDEX=$(curl -s 'http://localhost:8500/v1/health/service/order-service?passing=true' \
  | jq -r '.[0].ModifyIndex // 1')

echo "Current ModifyIndex: ${INDEX}"

# Blocking query (sẽ timeout sau 60s nếu không có thay đổi)
echo "Waiting up to 60s for change..."
curl -s --max-time 65 \
  "http://localhost:8500/v1/health/service/order-service?passing=true&index=${INDEX}&wait=60s" \
  | jq -r '.[0].ModifyIndex // "timeout"'

echo "Query completed"
```

### Bước 2: Watch loop (detect service change)

```bash
# Tạo watch script
cat > ~/consul-lab/watch-services.sh << 'WATCHEOF'
#!/bin/bash
# watch-services.sh — monitor service registry changes

CONSUL="http://localhost:8500"
SERVICE="order-service"

echo "Watching ${SERVICE}... (Ctrl+C to stop)"
echo ""

INDEX=""

while true; do
  ARGS="${CONSUL}/v1/health/service/${SERVICE}?passing=true"
  if [ -n "$INDEX" ]; then
    ARGS="${ARGS}&index=${INDEX}&wait=30s"
  else
    ARGS="${ARGS}&wait=30s"
  fi

  RESPONSE=$(curl -s --max-time 35 "$ARGS")
  NEW_INDEX=$(echo "$RESPONSE" | jq -r '.[0].ModifyIndex // empty')
  COUNT=$(echo "$RESPONSE" | jq -r 'length')

  if [ -n "$NEW_INDEX" ]; then
    echo "[$(date '+%H:%M:%S')] Service count: ${COUNT}, Index: ${NEW_INDEX}"
    if [ "$COUNT" -eq 0 ]; then
      echo "  WARNING: ${SERVICE} has NO healthy instances!"
    fi
    INDEX="$NEW_INDEX"
  fi
done
WATCHEOF

chmod +x ~/consul-lab/watch-services.sh

# Start watch in background
~/consul-lab/watch-services.sh &
WATCH_PID=$!

echo "Watch started with PID: ${WATCH_PID}"
echo "Now kill order-backend to see watch detect the change..."

# Give watch time to start
sleep 5
```

### Bước 3: Trigger change and observe watch

```bash
# Trong terminal 2 (hoặc sau khi watch đang chạy):
# Kill order-backend → watch nên phát hiện trong < 60s
docker stop order-backend

# Wait ~20s (health check interval 10s + deregister 30s, nhưng watch detect change sớm hơn)
sleep 20

# Restore
docker start order-backend
sleep 20

# Stop watch
kill $WATCH_PID 2>/dev/null
```

---

## Exercise 6: KV Store — Config Versioning Pattern

**Mục tiêu**: Sử dụng Consul KV store để lưu và đọc config, thực hành CAS (Check-And-Set) pattern.

### Bước 1: Store config in KV

```bash
echo "=== Storing config in Consul KV ==="

# Store rate limit config
curl -s -X PUT http://localhost:8500/v1/kv/order-service/rate-limit \
  -d '{"requests_per_second": 1000, "burst": 2000, "updated_at": "2026-05-18T10:00:00Z"}'

# Store upstream config
curl -s -X PUT http://localhost:8500/v1/kv/order-service/upstream \
  -d '{"algorithm": "round-robin", "health_check_interval": "10s"}'

# Store global config
curl -s -X PUT http://localhost:8500/v1/kv/config/global \
  -d '{"environment": "production", "datacenter": "dc1"}'

echo "Config stored"
```

### Bước 2: Read KV config

```bash
echo "=== Reading KV config ==="

echo "Rate limit config:"
curl -s http://localhost:8500/v1/kv/order-service/rate-limit | jq .

echo ""
echo "Upstream config:"
curl -s http://localhost:8500/v1/kv/order-service/upstream | jq .

echo ""
echo "List all KV keys (recurse):"
curl -s http://localhost:8500/v1/kv/?recurse | jq '.[].Key, .[].Value'
```

### Bước 3: CAS (Check-And-Set) atomic update

```bash
echo "=== CAS (Check-And-Set) atomic update ==="

# Get current index
KV_INDEX=$(curl -s http://localhost:8500/v1/kv/order-service/rate-limit \
  | jq -r '.[0].ModifyIndex')

echo "Current KV index: ${KV_INDEX}"

# Update with correct index (success)
echo "Updating with correct index..."
curl -s -X PUT "http://localhost:8500/v1/kv/order-service/rate-limit?cas=${KV_INDEX}" \
  -d '{"requests_per_second": 2000, "burst": 4000}' | jq .

# Get new index
NEW_INDEX=$(curl -s http://localhost:8500/v1/kv/order-service/rate-limit \
  | jq -r '.[0].ModifyIndex')
echo "New index after update: ${NEW_INDEX}"

# Update with OLD index (fail — someone else already updated)
echo ""
echo "Updating with stale index (should fail)..."
curl -s -X PUT "http://localhost:8500/v1/kv/order-service/rate-limit?cas=${KV_INDEX}" \
  -d '{"requests_per_second": 3000}' | jq .

echo "CAS failure means another process already updated the key — this is expected behavior"
```

### Bước 4: Config versioning pattern

```bash
echo "=== Config versioning with KV ==="

# Store versioned config
TIMESTAMP=$(date +%s)

curl -s -X PUT http://localhost:8500/v1/kv/order-service/config/versions/${TIMESTAMP} \
  -d '{"version": "1.2.3", "features": ["a", "b"], "pinned_at": "'$(date -Iseconds)'"}'

# Get all versions
curl -s http://localhost:8500/v1/kv/order-service/config/versions/?recurse \
  | jq '.[].Key, .[].Value'
```

---

## Exercise 7: Challenge — Multi-Service Registration with Tags

**Mục tiêu**: Challenge nâng cao — register nhiều service instances với tags, filter theo tag, và observe traffic distribution.

### Challenge 7a: Register 3 instances of the same service

```bash
# Register 3 instances of "analytics-service" với tags khác nhau
for i in 1 2 3; do
  docker run -d --name "analytics-$i" \
    --network consul-lab \
    mockserver/mockserver:5.15.0 \
    java -Dmockserver.initializationJsonPath=/config/init.json &

  # Create mock config
  cat > "/tmp/analytics-$i.json" << EOF
{
  "httpRequest": { "path": "/health" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"instance\":\"analytics-$i\",\"status\":\"ok\"}"
  }
}
EOF

  docker cp "/tmp/analytics-$i.json" "analytics-$i:/config/init.json"
done

# Register each instance với datacenter tag
sleep 5

for i in 1 2 3; do
  ANALYTICS_IP=$(docker inspect "analytics-$i" -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

  curl -s -X PUT http://localhost:8500/v1/agent/service/register \
    -d "{
      \"ID\": \"analytics-service-$i\",
      \"Name\": \"analytics-service\",
      \"Tags\": [\"prod\", \"analytics\", \"v1\"],
      \"Address\": \"${ANALYTICS_IP}\",
      \"Port\": 1080,
      \"Check\": {
        \"HTTP\": \"http://${ANALYTICS_IP}:1080/health\",
        \"Interval\": \"10s\",
        \"Timeout\": \"5s\",
        \"DeregisterCriticalServiceAfter\": \"30s\"
      }
    }"
  echo "analytics-service-$i registered"
done
```

### Challenge 7b: Query and filter by tag

```bash
echo "=== All analytics-service instances ==="
curl -s 'http://localhost:8500/v1/health/service/analytics-service?passing=true' \
  | jq '.[] | .Service | {ID, Address, Port, Tags}'

echo ""
echo "=== DNS SRV for analytics-service ==="
dig @localhost -p 8600 analytics-service.service.consul SRV

echo ""
echo "=== Count: how many healthy instances? ==="
curl -s 'http://localhost:8500/v1/health/service/analytics-service?passing=true' \
  | jq 'length'

echo ""
echo "=== DNS A records (all IPs) ==="
dig @localhost -p 8600 analytics-service.service.consul +short
```

### Challenge 7c: DNS round-robin verification

```bash
echo "=== DNS round-robin distribution test ==="
echo "Querying DNS 10 times to observe round-robin IPs:"
for i in $(seq 1 10); do
  dig @localhost -p 8600 +short analytics-service.service.consul | head -1
  sleep 1
done | sort | uniq -c

echo ""
echo "Expected: ~3-4 requests per instance (round-robin)"
```

---

## Cleanup

```bash
cd ~/consul-lab

# Stop all containers
docker compose down -v

# Remove analytics containers
for i in 1 2 3; do
  docker stop "analytics-$i" 2>/dev/null
  docker rm "analytics-$i" 2>/dev/null
done

# Remove lab directory
cd ~ && rm -rf ~/consul-lab

echo "Cleanup done"
```

---

## Tổng Kết Exercises

| Exercise | Topic | Key Commands |
|---|---|---|
| 0 | Consul cluster setup (1 server + 2 client + 2 backend) | `docker compose up -d` |
| 1 | HTTP API service registration | `PUT /v1/agent/service/register` |
| 2 | Config file registration (TTL check) | `consul reload` |
| 3 | Health check behavior (kill/restore) | `dig @consul -p 8600 order-service.service.consul SRV` |
| 4 | Tag-based filtering | `dig prod.order-service.service.consul SRV` |
| 5 | Blocking query / watch pattern | `curl "?index=N&wait=60s"` |
| 6 | KV store + CAS atomic update | `PUT /v1/kv/?cas=N` |
| 7 | Multi-instance registration + DNS round-robin | `dig +short analytics-service.service.consul` |
