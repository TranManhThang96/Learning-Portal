# Day 20: Exercises — End-to-End Gateway Capstone

> **Yêu cầu**: Docker, Docker Compose, curl, jq, decK 1.40+, k6, openssl, dig (via `dig` or `nslookup`), wrk (optional)
> **Kong version**: 3.7 | **Consul version**: 1.18 | **Redis version**: 7
> **Thời gian ước tính**: 120 phút (4 phase)
> **Lab type**: Capstone — tích hợp tất cả components từ Day 1-19

---

## Phase A: Scaffold & Preparation (15 phút)

**Mục tiêu**: Clone/verify scaffold, generate TLS certs, verify Docker networking, understand file structure.

### A.1 — Directory Setup

```bash
# Tạo thư mục capstone
mkdir -p ~/capstone && cd ~/capstone

# Tạo cấu trúc thư mục đầy đủ
mkdir -p nginx/certs kong consul/config consul/services
mkdir -p services/order-service services/payment-service services/tracking-service
mkdir -p prometheus grafana/provisioning/dashboards grafana/provisioning/datasources
mkdir -p deck bench

echo "Directory structure:"
find ~/capstone -type d | sort
```

### A.2 — Generate TLS Certificates (Self-Signed CA for Local)

```bash
cd ~/capstone/nginx/certs

# Generate CA key + certificate
openssl req -x509 -newkey rsa:4096 -keyout ca.key -out ca.crt \
  -days 365 -nodes \
  -subj "/CN=capstone-ca/O=Capstone Training"

# Generate server key + CSR
openssl req -newkey rsa:4096 -keyout server.key -out server.csr \
  -nodes -subj "/CN=localhost"

# Sign server cert với CA
openssl x509 -req -in server.csr -out server.crt \
  -CA ca.crt -CAkey ca.key \
  -days 365 -extfile <(printf "subjectAltName=DNS:localhost,IP:127.0.0.1") \
  -CAcreateserial

# Cleanup CSR
rm -f server.csr

echo "=== Certs generated ==="
ls -la

# Verify cert
openssl x509 -in server.crt -noout -subject -dates
```

### A.3 — Docker Network Verification

```bash
# Tạo Docker network
docker network create capstone-net 2>/dev/null || true

# Verify network
docker network ls | grep capstone-net

# Kiểm tra Docker resource limit (Docker Desktop: nên có 4+ CPU, 8 GB RAM)
docker info --format '{{.NCPU}},{{.MemTotal}}'
```

### A.4 — Quick Kong Config Baseline (kong.yml)

Tạo minimal `kong.yml` để verify Kong bootstrap hoạt động:

```bash
cat > ~/capstone/kong/kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: healthcheck-service
    url: http://httpbin.org
    routes:
      - name: healthcheck-route
        paths:
          - /healthcheck
        strip_path: true
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
EOF

echo "kong.yml baseline created"
```

---

## Phase B: Infrastructure Build (45 phút)

**Mục tiêu**: Consul + services + Redis + Kong DB-less + decK bootstrap. Sau phase này, Consul DNS phải resolve service name, Kong phải proxy traffic.

### B.1 — Consul Configuration

```bash
cat > ~/capstone/consul/config/consul.json << 'EOF'
{
  "datacenter": "dc1",
  "data_dir": "/consul/data",
  "ui_config": {
    "enabled": true
  },
  "server": true,
  "bootstrap_expect": 1,
  "ports": {
    "dns": 8600,
    "http": 8500,
    "serf_lan": 8301
  },
  "dns_config": {
    "allow_stale": true,
    "max_stale": 300,
    "service_ttl": {
      "*": "10s"
    },
    "enable_truncate": true
  },
  "enable_script_checks": false,
  "disable_update_check": true,
  "log_level": "info"
}
EOF

echo "Consul config created"
```

### B.2 — Consul Service Registration Files

**order-service**:

```bash
cat > ~/capstone/consul/services/order.json << 'EOF'
{
  "ID": "order-1",
  "Name": "order",
  "Namespace": "default",
  "Tags": ["v1", "primary"],
  "Address": "order-service",
  "Port": 3001,
  "Meta": {
    "version": "1.0.0",
    "team": "orders"
  },
  "Check": {
    "ID": "order-health",
    "Name": "order-service health",
    "http": "http://order-service:3001/health",
    "Interval": "10s",
    "Timeout": "2s",
    "DeregisterCriticalServiceAfter": "30s"
  }
}
EOF
```

**payment-service**:

```bash
cat > ~/capstone/consul/services/payment.json << 'EOF'
{
  "ID": "payment-1",
  "Name": "payment",
  "Namespace": "default",
  "Tags": ["v1"],
  "Address": "payment-service",
  "Port": 3002,
  "Meta": {
    "version": "1.0.0",
    "team": "payments"
  },
  "Check": {
    "ID": "payment-health",
    "Name": "payment-service health",
    "http": "http://payment-service:3002/health",
    "Interval": "10s",
    "Timeout": "2s",
    "DeregisterCriticalServiceAfter": "30s"
  }
}
EOF
```

**tracking-service**:

```bash
cat > ~/capstone/consul/services/tracking.json << 'EOF'
{
  "ID": "tracking-1",
  "Name": "tracking",
  "Namespace": "default",
  "Tags": ["v1"],
  "Address": "tracking-service",
  "Port": 3003,
  "Meta": {
    "version": "1.0.0",
    "team": "logistics"
  },
  "Check": {
    "ID": "tracking-health",
    "Name": "tracking-service health",
    "http": "http://tracking-service:3003/health",
    "Interval": "10s",
    "Timeout": "2s",
    "DeregisterCriticalServiceAfter": "30s"
  }
}
EOF
```

### B.3 — Microservices (Node/Express)

Tạo 3 microservices đơn giản:

**order-service/server.js**:

```javascript
const http = require('http');

const PORT = process.env.PORT || 3001;
const SERVICE_NAME = 'order-service';

const server = http.createServer((req, res) => {
  const url = req.url;

  if (url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: SERVICE_NAME, uptime: process.uptime() }));
    return;
  }

  if (url === '/orders' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'X-Service-Version': '1.0.0' });
    res.end(JSON.stringify({
      orders: [
        { id: 'ORD-001', status: 'pending', created_at: new Date().toISOString() },
        { id: 'ORD-002', status: 'shipped', created_at: new Date().toISOString() }
      ],
      total: 2,
      service: SERVICE_NAME
    }));
    return;
  }

  if (url.startsWith('/orders/') && req.method === 'GET') {
    const orderId = url.split('/')[2];
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      id: orderId,
      status: 'pending',
      items: [{ sku: 'PROD-001', qty: 2 }],
      service: SERVICE_NAME
    }));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found', path: url }));
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`${SERVICE_NAME} listening on port ${PORT}`);
});
```

**Dockerfile cho order-service**:

```bash
cat > ~/capstone/services/order-service/Dockerfile << 'EOF'
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY server.js ./
EXPOSE 3001
CMD ["node", "server.js"]
EOF

cat > ~/capstone/services/order-service/package.json << 'EOF'
{
  "name": "order-service",
  "version": "1.0.0",
  "main": "server.js",
  "scripts": { "start": "node server.js" },
  "dependencies": {}
}
EOF
```

**payment-service/server.js** (tương tự order-service, port 3002):

```bash
cat > ~/capstone/services/payment-service/Dockerfile << 'EOF'
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY server.js ./
EXPOSE 3002
CMD ["node", "server.js"]
EOF

cat > ~/capstone/services/payment-service/package.json << 'EOF'
{"name":"payment-service","version":"1.0.0","main":"server.js","scripts":{"start":"node server.js"},"dependencies":{}}
EOF

cat > ~/capstone/services/payment-service/server.js << 'EOF'
const http = require('http');
const PORT = process.env.PORT || 3002;
const SERVICE_NAME = 'payment-service';

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: SERVICE_NAME, uptime: process.uptime() }));
    return;
  }
  if (url === '/payments' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      res.writeHead(201, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ id: 'PAY-' + Date.now(), status: 'completed', service: SERVICE_NAME }));
    });
    return;
  }
  if (req.url.startsWith('/payments/') && req.method === 'GET') {
    const id = req.url.split('/')[2];
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ id, status: 'completed', amount: 99.99, service: SERVICE_NAME }));
    return;
  }
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, '0.0.0.0', () => console.log(`${SERVICE_NAME} listening on ${PORT}`));
EOF
```

**tracking-service/server.js** (port 3003):

```bash
cat > ~/capstone/services/tracking-service/Dockerfile << 'EOF'
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY server.js ./
EXPOSE 3003
CMD ["node", "server.js"]
EOF

cat > ~/capstone/services/tracking-service/package.json << 'EOF'
{"name":"tracking-service","version":"1.0.0","main":"server.js","scripts":{"start":"node server.js"},"dependencies":{}}
EOF

cat > ~/capstone/services/tracking-service/server.js << 'EOF'
const http = require('http');
const PORT = process.env.PORT || 3003;
const SERVICE_NAME = 'tracking-service';

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: SERVICE_NAME, uptime: process.uptime() }));
    return;
  }
  if (req.url.match(/^\/tracking\/.+/) && req.method === 'GET') {
    const id = req.url.split('/')[2];
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      order_id: id,
      status: 'in_transit',
      location: 'HCMC Distribution Center',
      ETA: new Date(Date.now() + 86400000).toISOString(),
      service: SERVICE_NAME
    }));
    return;
  }
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, '0.0.0.0', () => console.log(`${SERVICE_NAME} listening on ${PORT}`));
EOF
```

### B.4 — Docker Compose (Phase B Baseline)

```bash
cat > ~/capstone/docker-compose.yml << 'EOF'
version: "3.8"

networks:
  capstone-net:
    driver: bridge

volumes:
  consul-data:
  prometheus-data:
  grafana-data:

services:
  # ─── Consul Service Discovery ────────────────────────────────────────────
  consul:
    image: consul:1.18
    container_name: consul
    hostname: consul
    command: agent -config-file=/consul/config/consul.json
    volumes:
      - ./consul/config/consul.json:/consul/config/consul.json:ro
      - consul-data:/consul/data
    ports:
      - "8500:8500"   # HTTP API (Prometheus scrape)
      - "8600:8600/udp"  # DNS
    networks:
      - capstone-net
    healthcheck:
      test: ["CMD", "consul", "info"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: on-failure

  # ─── Microservices ──────────────────────────────────────────────────────
  order-service:
    build: ./services/order-service
    container_name: order-service
    hostname: order-service
    environment:
      PORT: 3001
    networks:
      - capstone-net
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3001/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    depends_on:
      consul:
        condition: service_healthy

  payment-service:
    build: ./services/payment-service
    container_name: payment-service
    hostname: payment-service
    environment:
      PORT: 3002
    networks:
      - capstone-net
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3002/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    depends_on:
      consul:
        condition: service_healthy

  tracking-service:
    build: ./services/tracking-service
    container_name: tracking-service
    hostname: tracking-service
    environment:
      PORT: 3003
    networks:
      - capstone-net
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3003/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    depends_on:
      consul:
        condition: service_healthy

  # ─── Redis (Rate Limit Counter) ─────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: redis
    hostname: redis
    command: redis-server --save "" --appendonly no --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    networks:
      - capstone-net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: on-failure

  # ─── Kong Gateway DB-less ───────────────────────────────────────────────
  kong:
    image: kong:3.7
    container_name: kong
    hostname: kong
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
      KONG_LOG_LEVEL: info
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ERROR_LOG: /dev/stderr
      # DNS resolver: point to Consul DNS
      KONG_DNS_STALE_TTL: "300"
      KONG_DNS_NOT_FOUND_TTL: "3"
      KONG_DNS_ERROR_TTL: "3"
      KONG_UPSTREAM_KEEPALIVE_POOL_SIZE: "60"
      KONG_UPSTREAM_KEEPALIVE_IDLE_TIMEOUT: "60"
      KONG_NGINX_PROXY_PROXY_BUFFERING: "off"
    volumes:
      - ./kong/kong.yml:/kong/declarative/kong.yml:ro
    ports:
      - "8000:8000"   # Proxy HTTP
      - "8001:8001"   # Admin API
      - "8100:8100"   # Status / Metrics
    networks:
      - capstone-net
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 10
    depends_on:
      consul:
        condition: service_healthy
      redis:
        condition: service_healthy
      order-service:
        condition: service_started
      payment-service:
        condition: service_started
      tracking-service:
        condition: service_started
    restart: on-failure
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # ─── Prometheus ──────────────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:v3.0.0
    container_name: prometheus
    hostname: prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=7d'
      - '--web.enable-lifecycle'
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - capstone-net
    depends_on:
      - kong
      - consul
    restart: on-failure

  # ─── Grafana ────────────────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:11.0.0
    container_name: grafana
    hostname: grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_SERVER_ROOT_URL: http://localhost:3000
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    ports:
      - "3000:3000"
    networks:
      - capstone-net
    depends_on:
      - prometheus
    restart: on-failure

  # ─── Nginx Edge ──────────────────────────────────────────────────────────
  nginx-edge:
    image: nginx:alpine
    container_name: nginx-edge
    hostname: nginx-edge
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    ports:
      - "80:80"
      - "443:443"
    networks:
      - capstone-net
    depends_on:
      kong:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:80/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: on-failure
EOF

echo "docker-compose.yml created"
```

### B.5 — Kong Declarative Config (kong.yml) — Full Version

```bash
cat > ~/capstone/kong/kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

# ─── Consumers ─────────────────────────────────────────────────────────────
consumers:
  - username: mobile-app
    tags: [production]
    keyauth_credentials:
      - key: "mobile-app-key-2026"
    plugins:
      - name: rate-limiting
        config:
          minute: 1000
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: false

  - username: partner-b
    tags: [production]
    keyauth_credentials:
      - key: "partner-b-key-2026"
    plugins:
      - name: rate-limiting
        config:
          minute: 100
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: false

  - username: internal-service
    tags: [production]
    jwt_secrets:
      - rsa_public_key: |
          -----BEGIN PUBLIC KEY-----
          MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDPbPRsNdG3QVPnGP5vTqZ4
          n5sN8bKzK9qJ8L5xGkP7mN2rT4wQ9vF6eP1sD3hM2jK5nL8fO1qR7pS3tU6
          vW2xE4yZ8nQ9pH1mK7jF3dC5gS8bT2nL6wA9xV1pR4eY3mK8jF7qN5pH2wS
          -----END PUBLIC KEY-----
        algorithm: RS256
        key: internal-service-key
        secret: internal-service-secret

# ─── Services ──────────────────────────────────────────────────────────────
services:
  # ORDER SERVICE
  - name: order-service
    url: http://order.service.consul:3001
    tags: [production, orders]
    connect_timeout: 2000
    write_timeout: 5000
    read_timeout: 5000
    retries: 2
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        methods:
          - GET
          - POST
        strip_path: true
        plugins:
          - name: key-auth
            config:
              key_names:
                - apikey
                - x-api-key
              key_in_query: false
              key_in_header: true
              hide_credentials: true
          - name: prometheus
            config:
              status_code_metrics: true
              latency_metrics: true
              bandwidth_metrics: true
              upstream_health_metrics: true
    upstream:
      name: order-upstream
      healthchecks:
        active:
          type: http
          http_path: /health
          interval: 10s
          timeout: 2s
          healthy_threshold: 2
          unhealthy_threshold: 3
        passive:
          type: http
          healthy_threshold: 3
          unhealthy_threshold: 3

  # PAYMENT SERVICE
  - name: payment-service
    url: http://payment.service.consul:3002
    tags: [production, payments]
    connect_timeout: 3000
    write_timeout: 10000
    read_timeout: 10000
    retries: 0
    routes:
      - name: payment-route
        paths:
          - /api/v1/payments
        methods:
          - GET
          - POST
        strip_path: true
        plugins:
          - name: key-auth
            config:
              key_names: [apikey]
              hide_credentials: true
          - name: rate-limiting
            config:
              minute: 50
              policy: redis
              redis_host: redis
              redis_port: 6379
              fault_tolerant: false
              limit_by: consumer
          - name: prometheus
            config:
              status_code_metrics: true
              latency_metrics: true

  # TRACKING SERVICE
  - name: tracking-service
    url: http://tracking.service.consul:3003
    tags: [production, logistics]
    connect_timeout: 2000
    write_timeout: 5000
    read_timeout: 5000
    routes:
      - name: tracking-route
        paths:
          - /api/v1/tracking
        methods:
          - GET
        strip_path: true
        plugins:
          - name: key-auth
            config:
              key_names: [apikey]
              hide_credentials: true
          - name: prometheus
            config:
              status_code_metrics: true
              latency_metrics: true

# ─── Global Plugins ──────────────────────────────────────────────────────────
plugins:
  - name: correlation-id
    config:
      header_name: X-Request-ID
      generator: uuid#counter
      echo_downstream: true

  # Global rate limit for anonymous (no consumer)
  - name: rate-limiting
    config:
      minute: 100
      policy: local
      fault_tolerant: false
      limit_by: ip

  - name: ip-restriction
    config:
      allow:
        - 0.0.0.0/0
        - ::/0

  - name: acl
    config:
      allow:
        - production
      hide_groups_header: true

# ─── Upstreams ──────────────────────────────────────────────────────────────
upstreams:
  - name: order-upstream
    targets:
      - target: order-service:3001
        weight: 100
        upstream: order-upstream

  - name: payment-upstream
    targets:
      - target: payment-service:3002
        weight: 100
        upstream: payment-upstream

  - name: tracking-upstream
    targets:
      - target: tracking-service:3003
        weight: 100
        upstream: tracking-upstream
EOF

echo "kong.yml (full) created"
```

### B.6 — Nginx Edge Config

```bash
cat > ~/capstone/nginx/nginx.conf << 'EOF'
# ─── Rate Limit Zones ──────────────────────────────────────────────────────
limit_req_zone $binary_remote_addr zone=ip_limit:10m rate=100r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# ─── Upstream (Kong Gateway) ────────────────────────────────────────────────
upstream kong_backend {
    server kong:8000 max_fails=3 fail_timeout=10s;
    keepalive 32;
}

# ─── HTTP Server (redirect to HTTPS) ────────────────────────────────────────
server {
    listen 80;
    server_name localhost;
    return 301 https://$host$request_uri;
}

# ─── Health Check Endpoint ───────────────────────────────────────────────────
server {
    listen 80 default_server;
    server_name _;

    location /health {
        return 200 'nginx-edge healthy';
        add_header Content-Type text/plain;
    }

    # Nginx stub_status (for Prometheus)
    location /metrics_nginx {
        stub_status on;
        access_log off;
    }

    # Kong metrics proxy (Prometheus → Kong :8100)
    location /kong-metrics {
        proxy_pass http://kong:8100/metrics;
        access_log off;
    }

    # ─── Main HTTPS Server ─────────────────────────────────────────────────
    server {
        listen 443 ssl http2;
        server_name localhost;

        # TLS Configuration
        ssl_certificate /etc/nginx/certs/server.crt;
        ssl_certificate_key /etc/nginx/certs/server.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 1d;

        # Client settings
        client_max_body_size 1m;
        client_body_timeout 30s;

        # IP rate limiting (edge layer)
        limit_req zone=ip_limit burst=50 nodelay;
        limit_conn conn_limit 10;

        # ─── API Proxy to Kong ───────────────────────────────────────────
        location /api/ {
            proxy_pass http://kong_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header Connection "";

            # Timeouts
            proxy_connect_timeout 5s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;

            # Buffers
            proxy_buffering off;
            proxy_request_buffering off;
        }

        # Default → Kong
        location / {
            proxy_pass http://kong_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
            proxy_connect_timeout 5s;
            proxy_read_timeout 30s;
        }

        # Access/Error log
        access_log /dev/stdout json_combined;
        error_log /dev/stderr warn;
    }
}
EOF

echo "nginx.conf created"
```

### B.7 — Prometheus Configuration

```bash
cat > ~/capstone/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    environment: capstone-local

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

scrape_configs:
  # Kong Gateway metrics (port 8100)
  - job_name: kong
    static_configs:
      - targets: [kong:8100]
    metrics_path: /metrics
    honor_labels: true

  # Nginx stub_status
  - job_name: nginx-edge
    static_configs:
      - targets: [nginx-edge:80]
    metrics_path: /metrics_nginx
    params:
      format: [text]

  # Consul agent metrics
  - job_name: consul
    consul_sd_configs:
      - server: consul:8500
    relabel_configs:
      - source_labels: [__meta_consul_service]
        target_label: service
      - source_labels: [__meta_consul_service_id]
        target_label: instance

  # Prometheus self-monitoring
  - job_name: prometheus
    static_configs:
      - targets: [localhost:9090]
EOF

cat > ~/capstone/prometheus/alerts.yml << 'EOF'
groups:
  - name: kong-capstone
    rules:
      - alert: KongHighErrorRate
        expr: rate(kong_http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Kong 5xx error rate > 5%"

      - alert: KongUpstreamSlow
        expr: histogram_quantile(0.95, rate(kong_upstream_latency_ms_bucket[5m])) > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Kong upstream p95 > 1s"

      - alert: RateLimitExceededHigh
        expr: rate(kong_http_requests_total{status="429"}[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Rate limit exceeded > 10/sec"
EOF
```

### B.8 — Grafana Provisioning

```bash
cat > ~/capstone/grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      httpMethod: POST
      timeInterval: 15s
EOF

cat > ~/capstone/grafana/provisioning/dashboards/dashboard.yml << 'EOF'
apiVersion: 1
providers:
  - name: Gateway Capstone
    folder: Gateway
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

cat > ~/capstone/grafana/provisioning/dashboards/gateway-overview.json << 'EOF'
{
  "annotations": { "list": [] },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "green", "value": null }]
          },
          "unit": "reqps"
        }
      },
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "id": 1,
      "options": {
        "legend": { "calcs": ["mean", "max"], "displayMode": "table", "placement": "bottom" },
        "tooltip": { "mode": "multi" }
      },
      "targets": [
        {
          "expr": "sum(rate(kong_http_requests_total[1m]))",
          "legendFormat": "Total RPS",
          "refId": "A"
        },
        {
          "expr": "sum(rate(kong_http_requests_total{service=~\"order|payment|tracking\"}[1m])) by (service)",
          "legendFormat": "{{service}}",
          "refId": "B"
        }
      ],
      "title": "Request Rate (RPS)",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "unit": "ms"
        }
      },
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "id": 2,
      "options": {
        "legend": { "calcs": ["mean", "max"], "displayMode": "table", "placement": "bottom" },
        "tooltip": { "mode": "multi" }
      },
      "targets": [
        {
          "expr": "histogram_quantile(0.50, sum(rate(kong_latency_ms_bucket[5m])) by (le, service))",
          "legendFormat": "p50 - {{service}}",
          "refId": "A"
        },
        {
          "expr": "histogram_quantile(0.95, sum(rate(kong_latency_ms_bucket[5m])) by (le, service))",
          "legendFormat": "p95 - {{service}}",
          "refId": "B"
        },
        {
          "expr": "histogram_quantile(0.99, sum(rate(kong_latency_ms_bucket[5m])) by (le, service))",
          "legendFormat": "p99 - {{service}}",
          "refId": "C"
        }
      ],
      "title": "Latency Distribution (p50/p95/p99)",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 1 },
              { "color": "red", "value": 5 }
            ]
          },
          "unit": "percent"
        }
      },
      "gridPos": { "h": 8, "w": 8, "x": 0, "y": 8 },
      "id": 3,
      "targets": [
        {
          "expr": "sum(rate(kong_http_requests_total{status=~\"5..\"}[5m])) / sum(rate(kong_http_requests_total[5m])) * 100",
          "legendFormat": "5xx Error Rate",
          "refId": "A"
        },
        {
          "expr": "sum(rate(kong_http_requests_total{status=~\"4..\"}[5m])) / sum(rate(kong_http_requests_total[5m])) * 100",
          "legendFormat": "4xx Rate",
          "refId": "B"
        },
        {
          "expr": "sum(rate(kong_http_requests_total{status=\"429\"}[5m]))",
          "legendFormat": "429 Rate Limit",
          "refId": "C"
        }
      ],
      "title": "Error Rates",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": { "color": { "mode": "thresholds" }, "unit": "short" }
      },
      "gridPos": { "h": 8, "w": 8, "x": 8, "y": 8 },
      "id": 4,
      "targets": [
        {
          "expr": "sum(kong_upstream_target_health{healthcheck=\"active\", state=\"healthy\"})",
          "legendFormat": "Healthy Targets",
          "refId": "A"
        },
        {
          "expr": "sum(kong_upstream_target_health{healthcheck=\"active\", state=\"unhealthy\"})",
          "legendFormat": "Unhealthy Targets",
          "refId": "B"
        }
      ],
      "title": "Upstream Target Health",
      "type": "stat"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": { "unit": "percentunit" }
      },
      "gridPos": { "h": 8, "w": 8, "x": 16, "y": 8 },
      "id": 5,
      "targets": [
        {
          "expr": "rate(kong_upstream_retry_total[5m]) / (rate(kong_upstream_request_total[5m]) + 1e-9) * 100",
          "legendFormat": "Retry Rate",
          "refId": "A"
        }
      ],
      "title": "Retry Rate",
      "type": "timeseries"
    }
  ],
  "refresh": "10s",
  "schemaVersion": 38,
  "tags": ["gateway", "kong", "capstone"],
  "templating": { "list": [] },
  "time": { "from": "now-15m", "to": "now" },
  "timepicker": {},
  "timezone": "browser",
  "title": "Gateway Capstone Overview",
  "uid": "gateway-capstone",
  "version": 1,
  "weekStart": ""
}
EOF
```

### B.9 — Consul Service Registration

```bash
cd ~/capstone

# Start Consul first
docker compose up -d consul
sleep 10

# Register all services
for svc in order payment tracking; do
  echo "Registering ${svc}-service..."
  docker exec consul curl -s -X PUT \
    -H "Content-Type: application/json" \
    -d @/capstone/consul/services/${svc}.json \
    http://127.0.0.1:8500/v1/agent/service/register
  echo ""
done

# Verify services registered
echo "=== Consul Catalog ==="
docker exec consul curl -s http://127.0.0.1:8500/v1/catalog/services | jq .

echo "=== Consul DNS — order service ==="
docker exec consul dig @127.0.0.1 -p 8600 order.service.consul SRV +short

echo "=== Consul DNS — payment service ==="
docker exec consul dig @127.0.0.1 -p 8600 payment.service.consul SRV +short
```

### B.10 — Build & Start All Services

```bash
cd ~/capstone

# Pull images
docker compose pull consul redis prometheus grafana kong nginx:alpine

# Build microservices
docker compose build order-service payment-service tracking-service

# Start all services (except nginx-edge temporarily — start after Kong healthy)
docker compose up -d consul redis

# Wait for Consul healthy
sleep 15

# Register services
for svc in order payment tracking; do
  docker exec consul curl -s -X PUT \
    -H "Content-Type: application/json" \
    -d @/capstone/consul/services/${svc}.json \
    http://127.0.0.1:8500/v1/agent/service/register
done

# Start microservices
docker compose up -d order-service payment-service tracking-service
sleep 15

# Start Kong
docker compose up -d kong
sleep 20

# Verify Kong
curl -sf http://localhost:8001 | jq '{version: .version}'

# Verify Kong upstream health
curl -s http://localhost:8001/upstreams | jq '.data[].health'

# Sync Kong config via decK
deck gateway sync ~/capstone/kong/kong.yml --kong-addr http://localhost:8001

# Start Prometheus and Grafana
docker compose up -d prometheus grafana
sleep 10

# Start Nginx edge (after Kong is healthy)
docker compose up -d nginx-edge
```

---

## Phase C: Validation & Feature Verification (45 phút)

**Mục tiêu**: Verify end-to-end flow, auth, rate-limit, metrics.

### C.1 — End-to-End Health Check

```bash
echo "=== C1: End-to-End Health Check ==="

echo "[1] Consul services registered"
docker exec consul curl -s http://127.0.0.1:8500/v1/health/service/order | jq '.[0].Service.Service'

echo "[2] Service health endpoints"
curl -s http://localhost:3001/health | jq '.status'
curl -s http://localhost:3002/health | jq '.status'
curl -s http://localhost:3003/health | jq '.status'

echo "[3] Consul DNS resolve"
docker exec consul dig @127.0.0.1 -p 8600 order.service.consul SRV

echo "[4] Kong upstream targets"
curl -s http://localhost:8001/upstreams | jq '.data[].name'

echo "[5] Kong routes"
curl -s http://localhost:8001/routes | jq '.data[].name'

echo "[6] Kong consumers"
curl -s http://localhost:8001/consumers | jq '.data[].username'

echo "[7] Kong plugins enabled"
curl -s http://localhost:8001/plugins/enabled | jq '.enabled_plugins | length'

echo "[8] Kong status"
curl -sf http://localhost:8100/status

echo "[9] Prometheus targets"
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].labels.job'

echo "[10] Nginx edge health"
curl -s http://localhost:80/health
```

### C.2 — End-to-End API Test (via Nginx Edge)

```bash
echo "=== C2: End-to-End API Flow ==="

# Test 1: Request WITHOUT API key → 401
echo "[TEST 1] No API key (expect 401)"
curl -s -o /dev/null -w "HTTP %{http_code} | Latency: %{time_total}s\n" \
  http://localhost:80/api/v1/orders

# Test 2: Request WITH API key → 200
echo "[TEST 2] Valid API key (expect 200)"
curl -s -o /dev/null -w "HTTP %{http_code} | Latency: %{time_total}s\n" \
  -H "apikey: mobile-app-key-2026" \
  http://localhost:80/api/v1/orders

# Test 3: Get order list
echo "[TEST 3] GET /api/v1/orders (expect 200)"
curl -s -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders | jq '{total, service}'

# Test 4: Get order detail
echo "[TEST 4] GET /api/v1/orders/ORD-001 (expect 200)"
curl -s -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders/ORD-001 | jq '{id, status}'

# Test 5: Payment endpoint (strict rate-limit)
echo "[TEST 5] POST /api/v1/payments (expect 201)"
curl -s -X POST -H "apikey: mobile-app-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"amount": 99.99, "currency": "USD"}' \
  http://localhost:80/api/v1/payments | jq '{id, status}'

# Test 6: Tracking endpoint
echo "[TEST 6] GET /api/v1/tracking/ORD-001 (expect 200)"
curl -s -H "apikey: mobile-app-key-2026" \
  http://localhost:80/api/v1/tracking/ORD-001 | jq '{order_id, status, location}'

# Test 7: Wrong API key → 401
echo "[TEST 7] Wrong API key (expect 401)"
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "apikey: wrong-key-xxx" \
  http://localhost:80/api/v1/orders

# Test 8: Partner B rate-limit (100/min)
echo "[TEST 8] Partner B rate-limit"
for i in $(seq 1 3); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "apikey: partner-b-key-2026" \
    http://localhost:80/api/v1/orders)
  echo "Request $i: HTTP $STATUS"
done

# Test 9: X-Request-ID header propagation
echo "[TEST 9] X-Request-ID propagation"
curl -s -v -H "apikey: mobile-app-key-2026" \
  http://localhost:80/api/v1/orders 2>&1 | grep -i "x-request-id"

# Test 10: X-RateLimit headers present
echo "[TEST 10] X-RateLimit headers"
curl -sI -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders \
  | grep -i "ratelimit"

# Test 11: Prometheus metrics endpoint
echo "[TEST 11] Kong Prometheus metrics (sample)"
curl -sf http://localhost:8100/metrics | grep "^kong_http_requests_total" | head -5

echo "[TEST 12] Nginx Prometheus metrics"
curl -s http://localhost:80/metrics_nginx
```

### C.3 — Rate Limit Verification

```bash
echo "=== C3: Rate Limit Trigger Test ==="

# partner-b has 100 requests/min limit
# Rapidly send requests to trigger limit
echo "Sending 105 requests rapidly (limit=100/min for partner-b)..."
for i in $(seq 1 105); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "apikey: partner-b-key-2026" \
    http://localhost:80/api/v1/orders)
  if [ "$STATUS" == "429" ]; then
    echo "Request $i: HTTP $STATUS — Rate limit triggered!"
    curl -sI -H "apikey: partner-b-key-2026" http://localhost:80/api/v1/orders \
      | grep -i "retry-after\|ratelimit"
    break
  fi
done

# Wait for window to reset
echo "Waiting 65s for rate limit window to reset..."
sleep 65

# Verify reset
echo "[After reset] Request should be 200 again"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "apikey: partner-b-key-2026" \
  http://localhost:80/api/v1/orders)
echo "Status after reset: HTTP $STATUS"
```

### C.4 — Consul DNS + Kong Health Check Integration

```bash
echo "=== C4: Service Discovery & Health Check ==="

# Step 1: Verify Consul DNS SRV records
echo "[1] Consul DNS SRV records"
docker exec consul dig @127.0.0.1 -p 8600 _order._tcp.order.service.consul SRV +short
docker exec consul dig @127.0.0.1 -p 8600 _payment._tcp.payment.service.consul SRV +short
docker exec consul dig @127.0.0.1 -p 8600 _tracking._tcp.tracking.service.consul SRV +short

# Step 2: Verify Kong can resolve via Consul DNS
echo "[2] Kong resolves service via Consul DNS"
docker exec kong dig @127.0.0.1 -p 8600 order.service.consul A +short

# Step 3: Kong upstream target health
echo "[3] Kong upstream target health"
curl -s http://localhost:8001/upstreams | jq '.data[] | {name, health: .healthchecks}'

# Step 4: Simulate service down — stop order-service
echo "[4] Stopping order-service (simulate failure)..."
docker stop order-service
sleep 15  # Wait for health check interval

# Step 5: Check Kong health check marks target unhealthy
echo "[5] Kong upstream target health after order-service stop"
curl -s http://localhost:8001/upstreams/order-upstream/targets | \
  jq '.data[] | {target, healthy, weight}'

# Step 6: Verify Kong still serves requests (503 if no healthy target)
echo "[6] Request to order-service (expect 503 — no healthy target)"
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "apikey: mobile-app-key-2026" \
  http://localhost:80/api/v1/orders

# Step 7: Restore order-service
echo "[7] Restoring order-service..."
docker start order-service
sleep 15  # Wait for health check

# Step 8: Verify recovery
echo "[8] Request after restore (expect 200)"
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "apikey: mobile-app-key-2026" \
  http://localhost:80/api/v1/orders
```

---

## Phase D: Benchmark & Failure Drill (15 phút)

### D.1 — k6 Benchmark Script

```bash
cat > ~/capstone/bench/scenarios.lua << 'EOF'
-- k6 Gateway Capstone Benchmark
-- Usage: k6 run scenarios.lua

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const proxyLatency = new Trend('kong_proxy_latency');
const upstreamLatency = new Trend('kong_upstream_latency');

export const options = {
  scenarios: {
    // Warmup: 5s, 10 VUs
    warmup: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '5s', target: 10 },
      ],
      tags: { type: 'warmup' },
    },
    // Steady state: 30s, 50 VUs
    steady: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { duration: '10s', target: 50 },
        { duration: '20s', target: 50 },
        { duration: '10s', target: 50 },
      ],
      tags: { type: 'steady' },
    },
    // Stress: 10s, 50 → 100 VUs
    stress: {
      executor: 'ramping-vus',
      startVUs: 50,
      stages: [
        { duration: '10s', target: 100 },
        { duration: '10s', target: 100 },
        { duration: '5s', target: 0 },
      ],
      tags: { type: 'stress' },
    },
  },
  thresholds: {
    'http_req_duration': ['p(95)<500', 'p(99)<1000'],
    'kong_proxy_latency': ['p(95)<100'],
    'errors': ['rate<0.05'],
  },
};

const BASE_URL = 'http://localhost:80';
const API_KEY = 'mobile-app-key-2026';

const endpoints = [
  '/api/v1/orders',
  '/api/v1/payments',
  '/api/v1/tracking/ORD-TEST',
];

export default function () {
  const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
  const url = `${BASE_URL}${endpoint}`;

  const params = {
    headers: {
      'apikey': API_KEY,
      'Content-Type': 'application/json',
    },
    tags: { endpoint, name: 'gateway-capstone' },
  };

  const res = http.get(url, params);

  // Extract Kong latency headers
  const proxyMs = parseFloat(res.headers['X-Kong-Proxy-Latency'] || 0);
  const upstreamMs = parseFloat(res.headers['X-Kong-Upstream-Latency'] || 0);
  proxyLatency.add(proxyMs);
  upstreamLatency.add(upstreamMs);

  // Check response
  const isSuccess = check(res, {
    'status is 2xx or 429': (r) => [200, 201, 429].includes(r.status),
    'response has body': (r) => r.body && r.body.length > 0,
    'X-Request-ID present': (r) => !!r.headers['X-Request-ID'],
  });

  errorRate.add(!isSuccess);

  sleep(Math.random() * 2 + 0.5); // 0.5-2.5s between requests
}
EOF

echo "k6 scenarios.lua created"
```

### D.2 — Benchmark Runner Script

```bash
cat > ~/capstone/bench/run.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${BENCH_DIR}/results"
mkdir -p "$RESULTS_DIR"

TIMESTAMP=$(date +%F-%H%M%S)
RESULT_FILE="${RESULTS_DIR}/benchmark-${TIMESTAMP}.json"
SUMMARY_FILE="${RESULTS_DIR}/summary-${TIMESTAMP}.txt"

echo "=============================================="
echo "Gateway Capstone Benchmark"
echo "Time: $(date)"
echo "Results: $RESULT_FILE"
echo "=============================================="

echo ""
echo "[1] Verify all services healthy..."
SERVICES=("kong" "consul" "redis" "order-service" "payment-service" "tracking-service" "prometheus" "grafana" "nginx-edge")
for svc in "${SERVICES[@]}"; do
  STATUS=$(docker inspect -f '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "unknown")
  printf "  %-20s %s\n" "$svc" "$STATUS"
done

echo ""
echo "[2] Baseline health check..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders)
echo "  Baseline request: HTTP $HTTP_STATUS"
if [ "$HTTP_STATUS" != "200" ]; then
  echo "ERROR: Baseline request failed. Fix services before benchmarking."
  exit 1
fi

echo ""
echo "[3] Run k6 benchmark (warmup → steady → stress)..."
k6 run \
  --out json="${RESULT_FILE}" \
  --summary-export="${SUMMARY_FILE}" \
  "${BENCH_DIR}/scenarios.lua" \
  2>&1 | tee "${RESULTS_DIR}/k6-output-${TIMESTAMP}.log"

echo ""
echo "[4] Benchmark results saved to:"
echo "  JSON: $RESULT_FILE"
echo "  Summary: $SUMMARY_FILE"
echo ""

echo "[5] Quick summary check:"
if [ -f "${SUMMARY_FILE}" ]; then
  grep -E "http_req_duration|errors| kong_proxy" "${SUMMARY_FILE}" | head -20
fi

echo ""
echo "=== Benchmark complete ==="
EOF
chmod +x ~/capstone/bench/run.sh

echo "run.sh created"
```

### D.3 — Failure Drill Script

```bash
cat > ~/capstone/bench/drill.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "=============================================="
echo "Gateway Capstone — Failure Drill"
echo "Time: $(date)"
echo "=============================================="

API_KEY="mobile-app-key-2026"
ENDPOINT="http://localhost:80/api/v1/orders"

# Helper function
check_result() {
  local label=$1
  local expected=$2
  local actual=$3
  if [[ "$actual" == "$expected" ]]; then
    echo "  [PASS] $label → HTTP $actual"
  else
    echo "  [FAIL] $label → Expected $expected, got HTTP $actual"
  fi
}

echo ""
echo "[DRILL 1] Service Down — order-service"
echo "  Triggering: docker stop order-service"
docker stop order-service
sleep 12
RESULT=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: $API_KEY" "$ENDPOINT")
check_result "order-service down → expect 503" "503" "$RESULT"
echo "  Observing: Kong logs"
docker compose logs --tail=5 kong 2>&1 | grep -i "health\|upstream\|502\|503" || true
docker start order-service
sleep 15
RESULT=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: $API_KEY" "$ENDPOINT")
check_result "order-service restored → expect 200" "200" "$RESULT"

echo ""
echo "[DRILL 2] Rate Limit Exceeded — partner-b"
echo "  partner-b limit: 100 req/min. Sending 105 rapid requests..."
for i in $(seq 1 105); do
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: partner-b-key-2026" "$ENDPOINT")
  if [[ "$RESULT" == "429" ]]; then
    echo "  [PASS] Rate limit triggered at request $i"
    curl -sI -H "apikey: partner-b-key-2026" "$ENDPOINT" | grep -i "retry-after\|ratelimit"
    break
  fi
done

echo ""
echo "[DRILL 3] Redis Down — rate limit fail-open"
echo "  Triggering: docker stop redis"
docker stop redis
sleep 3
# Rate-limit should fail-open (requests pass through)
RESULT=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: $API_KEY" "$ENDPOINT")
check_result "Redis down, rate-limit fail-open → expect 200" "200" "$RESULT"
echo "  Kong error log (should show Redis error):"
docker compose logs --tail=3 kong 2>&1 | grep -i redis || echo "  (no redis error logged)"
docker start redis
sleep 5

echo ""
echo "[DRILL 4] Consul Down — DNS stale"
echo "  Triggering: docker stop consul"
docker stop consul
sleep 5
# Kong should continue using cached DNS
RESULT=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: $API_KEY" "$ENDPOINT")
check_result "Consul down, DNS cache still valid → expect 200" "200" "$RESULT"
docker start consul
sleep 10

echo ""
echo "[DRILL 5] Kong Admin API — protected by Nginx"
echo "  Direct Kong Admin API from host (should work via mapped port 8001)"
RESULT=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/services)
check_result "Kong Admin API on 8001 → expect 200" "200" "$RESULT"
echo "  Note: In production, Admin API 8001 should be behind Nginx auth or internal network only"

echo ""
echo "=============================================="
echo "Failure Drill Complete"
echo "=============================================="
EOF
chmod +x ~/capstone/bench/drill.sh

echo "drill.sh created"
```

### D.4 — decK Bootstrap Script

```bash
cat > ~/capstone/deck/bootstrap.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

KONG_ADDR="${KONG_ADDR:-http://localhost:8001}"
KONG_YML="${KONG_YML:-$HOME/capstone/kong/kong.yml}"
BACKUP_DIR="$HOME/capstone/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%F-%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup-${TIMESTAMP}.yml"

echo "=============================================="
echo "Kong decK Bootstrap — GitOps Pipeline"
echo "Time: $(date)"
echo "Kong: $KONG_ADDR"
echo "=============================================="

echo ""
echo "[Step 1] Lint kong.yml (offline validation)"
echo "Command: deck file lint $KONG_YML"
if deck file lint "$KONG_YML" 2>&1; then
  echo "  [PASS] Lint OK"
else
  echo "  [FAIL] Lint failed — fix errors before proceeding"
  exit 1
fi

echo ""
echo "[Step 2] Verify Kong is reachable"
echo "Command: deck gateway ping --kong-addr $KONG_ADDR"
if deck gateway ping --kong-addr "$KONG_ADDR" 2>&1; then
  echo "  [PASS] Kong reachable"
else
  echo "  [FAIL] Kong not reachable — check Kong is running"
  exit 1
fi

echo ""
echo "[Step 3] Validate kong.yml against Kong"
echo "Command: deck gateway validate $KONG_YML --kong-addr $KONG_ADDR"
if deck gateway validate "$KONG_YML" --kong-addr "$KONG_ADDR" 2>&1; then
  echo "  [PASS] Validation OK"
else
  echo "  [FAIL] Validation failed"
  exit 1
fi

echo ""
echo "[Step 4] Backup current state"
echo "Command: deck gateway dump -o $BACKUP_FILE --kong-addr $KONG_ADDR"
deck gateway dump -o "$BACKUP_FILE" --kong-addr "$KONG_ADDR" 2>&1
if [ -f "$BACKUP_FILE" ]; then
  SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
  echo "  [PASS] Backup saved: $BACKUP_FILE ($SIZE)"
else
  echo "  [FAIL] Backup not created"
  exit 1
fi

echo ""
echo "[Step 5] Diff — preview changes"
echo "Command: deck gateway diff $KONG_YML --kong-addr $KONG_ADDR"
deck gateway diff "$KONG_YML" --kong-addr "$KONG_ADDR" 2>&1 || true

echo ""
echo "[Step 6] Sync (apply config)"
echo "Command: deck gateway sync $KONG_YML --kong-addr $KONG_ADDR"
if deck gateway sync "$KONG_YML" --kong-addr "$KONG_ADDR" 2>&1; then
  echo "  [PASS] Sync OK"
else
  echo "  [FAIL] Sync failed — rolling back"
  echo "Command: deck gateway sync $BACKUP_FILE --kong-addr $KONG_ADDR"
  deck gateway sync "$BACKUP_FILE" --kong-addr "$KONG_ADDR" 2>&1
  echo "  [DONE] Rollback complete"
  exit 1
fi

echo ""
echo "[Step 7] Smoke test"
sleep 5
echo "Command: curl -H 'apikey: mobile-app-key-2026' http://localhost:8000/api/v1/orders"
SMOKE=$(curl -sf -H "apikey: mobile-app-key-2026" http://localhost:8000/api/v1/orders)
if [ $? -eq 0 ]; then
  echo "  [PASS] Smoke test OK"
else
  echo "  [FAIL] Smoke test failed"
  echo "  Rolling back..."
  deck gateway sync "$BACKUP_FILE" --kong-addr "$KONG_ADDR" 2>&1
  exit 1
fi

echo ""
echo "=============================================="
echo "Git tag:"
echo "  git tag -a deploy-${TIMESTAMP} -m 'Kong config deploy ${TIMESTAMP}'"
echo "=============================================="
EOF
chmod +x ~/capstone/deck/bootstrap.sh

echo "bootstrap.sh created"
```

### D.5 — Prometheus Dashboard Verification

```bash
echo "=== D5: Grafana Dashboard Verification ==="

echo "[1] Check Grafana is running"
curl -sf http://localhost:3000/api/health | jq '.'

echo "[2] Login to Grafana and check datasource"
curl -sf -u admin:admin \
  http://localhost:3000/api/datasources \
  | jq '.[0] | {name, type, url}'

echo "[3] Query Prometheus from Grafana"
curl -sf -u admin:admin \
  "http://localhost:3000/api/ds/query" \
  -H "Content-Type: application/json" \
  -d '{"queries":[{"refId":"A","expr":"up","datasource":{"type":"prometheus","uid":"prometheus"}}],"from":"now-5m","to":"now"}' \
  | jq '.results.A.status'
```

### D.6 — Benchmark Execution

```bash
echo "=== D6: Run k6 Benchmark ==="

# Check if k6 is available
if ! command -v k6 &> /dev/null; then
  echo "k6 not found. Installing..."
  # macOS
  brew install k6 2>/dev/null || \
  # Linux
  sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69 && \
  echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list && \
  sudo apt-get update && sudo apt-get install -y k6 2>/dev/null || \
  echo "Manual install: https://k6.io/docs/getting-started/installation/"
fi

echo "Running k6 benchmark..."
~/capstone/bench/run.sh

echo "=== D6 Complete ==="
```

### D.7 — Failure Drill Execution

```bash
echo "=== D7: Failure Drill ==="
~/capstone/bench/drill.sh

echo "=== D7 Complete ==="
```

---

## Phase E: Final Verification & Deliverables

### E.1 — End-to-End Acceptance Criteria

```bash
cat > ~/capstone/acceptance.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }

echo "========================================"
echo "Day 20 Capstone — Acceptance Criteria"
echo "========================================"

echo ""
echo "[Security]"
curl -sf http://localhost:80/api/v1/orders -o /dev/null -w "%{http_code}" | \
  grep -q "401" && pass "No API key → 401" || fail "No API key → 401"
curl -sf -H "apikey: wrong-key" http://localhost:80/api/v1/orders -o /dev/null -w "%{http_code}" | \
  grep -q "401" && pass "Wrong API key → 401" || fail "Wrong API key → 401"

echo ""
echo "[Routing]"
curl -sf -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders -o /dev/null -w "%{http_code}" | \
  grep -q "200" && pass "GET /api/v1/orders → 200" || fail "GET /api/v1/orders → 200"
curl -sf -X POST -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders -o /dev/null -w "%{http_code}" | \
  grep -q "200" && pass "POST /api/v1/orders → 200" || fail "POST /api/v1/orders → 200"
curl -sf -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/tracking/ORD-001 -o /dev/null -w "%{http_code}" | \
  grep -q "200" && pass "GET /api/v1/tracking → 200" || fail "GET /api/v1/tracking → 200"

echo ""
echo "[Observability]"
curl -sf http://localhost:8100/metrics | grep -q "kong_http_requests_total" && \
  pass "Kong metrics available" || fail "Kong metrics available"
curl -sf http://localhost:80/metrics_nginx | grep -q "Active" && \
  pass "Nginx stub_status available" || fail "Nginx stub_status available"
curl -sf http://localhost:9090/api/v1/query?query=up | jq '.status' | grep -q "success" && \
  pass "Prometheus queryable" || fail "Prometheus queryable"

echo ""
echo "[Service Discovery]"
docker exec consul curl -sf http://127.0.0.1:8500/v1/health/service/order -o /dev/null && \
  pass "Consul service registered" || fail "Consul service registered"

echo ""
echo "[Rate Limiting]"
docker exec consul curl -sf http://127.0.0.1:8500/v1/health/service/order > /dev/null
# Rapid requests for partner-b (limit=100/min)
HIT_LIMIT=0
for i in $(seq 1 110); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: partner-b-key-2026" http://localhost:80/api/v1/orders)
  [ "$STATUS" == "429" ] && HIT_LIMIT=1 && break
done
[ "$HIT_LIMIT" -eq 1 ] && pass "Rate limit triggered (429)" || fail "Rate limit triggered (429)"

echo ""
echo "[Health Check & Failover]"
docker stop order-service > /dev/null 2>&1
sleep 15
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders)
[ "$STATUS" == "503" ] && pass "Service down → 503" || fail "Service down → 503 (got $STATUS)"
docker start order-service > /dev/null 2>&1
sleep 15
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "apikey: mobile-app-key-2026" http://localhost:80/api/v1/orders)
[ "$STATUS" == "200" ] && pass "Service restored → 200" || fail "Service restored → 200 (got $STATUS)"

echo ""
echo "========================================"
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && echo "STATUS: ALL CHECKS PASSED" || echo "STATUS: SOME CHECKS FAILED"
echo "========================================"
EOF
chmod +x ~/capstone/acceptance.sh

~/capstone/acceptance.sh
```

### E.2 — Generate Benchmark Snapshot (Day 21 Deliverable)

```bash
cat > ~/capstone/BENCHMARK-SNAPSHOT.md << 'EOF'
# Benchmark Report Snapshot — Day 20 Capstone
> Generated: $(date)
> Environment: Docker Desktop, 4 vCPU, 8 GB RAM, macOS/Windows
> Tool: k6 v0.55+
> Kong version: 3.7 | Consul: 1.18 | Redis: 7

## Methodology

- Tool: k6
- Scenario: ramping-vus (0 → 10 → 50 → 100 → 0)
- Duration: ~90s total
- Endpoint: GET /api/v1/orders, /api/v1/payments, /api/v1/tracking/ORD-TEST
- Auth: apikey: mobile-app-key-2026
- Rate-limit: 1000 req/min (mobile-app)

## Metrics (to be filled after benchmark run)

| Metric | Warmup | Steady | Stress |
|---|---|---|---|
| RPS (avg) | TBD | TBD | TBD |
| p50 latency (ms) | TBD | TBD | TBD |
| p95 latency (ms) | TBD | TBD | TBD |
| p99 latency (ms) | TBD | TBD | TBD |
| Error rate | TBD | TBD | TBD |
| Kong proxy overhead (p95 ms) | TBD | TBD | TBD |
| HTTP 429 count | TBD | TBD | TBD |
| HTTP 5xx count | TBD | TBD | TBD |

## Container Resource Usage

```bash
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
  kong consul redis order-service payment-service tracking-service prometheus grafana nginx-edge
```

## Observations

_Fill after running benchmark_

## Action Items for Day 21

- [ ] Run full benchmark suite
- [ ] Fill in metrics table above
- [ ] Document failure drill results
- [ ] Identify bottleneck (if any)
- [ ] Capacity planning for production scale
EOF

echo "Benchmark snapshot created: ~/capstone/BENCHMARK-SNAPSHOT.md"
```

---

## Cleanup

```bash
echo "=== Cleanup ==="
cd ~/capstone

# Stop all containers
docker compose down

# Remove networks/volumes (optional)
# docker compose down -v --remove-orphans

# Remove images (optional)
# docker compose down --rmi local

echo "Cleanup complete. To restart:"
echo "  cd ~/capstone && docker compose up -d"
```

---

## Tổng Kết Exercises

| Phase | Nội dung | Thời gian | Key Commands |
|---|---|---|---|
| **A** | Scaffold, TLS certs, Docker network | 15 phút | `openssl req -x509`, `docker network create` |
| **B** | Consul, services, Redis, Kong DB-less, decK bootstrap | 45 phút | `docker compose up -d`, `deck gateway sync`, `consul services register` |
| **C** | End-to-end verify, auth, rate-limit, DNS+health check | 45 phút | `curl`, `dig`, `jq`, health check drill |
| **D** | k6 benchmark, failure drill, Grafana verify | 15 phút | `k6 run`, `drill.sh`, `run.sh` |
| **E** | Acceptance criteria, benchmark snapshot | 15 phút | `acceptance.sh`, `BENCHMARK-SNAPSHOT.md` |

**Total**: ~135 phút (có thể chạy trong 2 giờ nếu follow đúng thứ tự)
