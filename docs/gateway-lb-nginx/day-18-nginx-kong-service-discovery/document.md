# Day 18: Deep Dive — Service Discovery Integration Patterns

> Document này mở rộng các khái niệm trong `lesson.md`, cung cấp reference chi tiết cho production implementation.

---

## 1. consul-template HCL Reference

### 1.1 Full Configuration Schema

```hcl
# ============================================================
# consul-template daemon — complete HCL configuration reference
# consul-template 0.34+
# ============================================================

# --- Global ---
log_level = "info"              # trace, debug, info, warn, err
pid_file   = "/var/run/consul-template.pid"

# Signal configuration
reload_signal  = "SIGHUP"     # trigger config reload
kill_signal     = "SIGINT"     # graceful shutdown
shutdown_signal = "SIGTERM"    # force shutdown

# --- Consul connection ---
consul {
  address     = "consul:8500"  # Consul HTTP API address
  token       = ""              # ACL token (if ACL enabled)
  namespace   = ""              # Consul Enterprise namespace
  auth {
    enabled  = false
    username = ""
    password = ""
  }
  retry {
    enabled   = true
    attempts  = 12              # retry attempts before giving up
    backoff   = "250ms"        # initial backoff
    max_backoff = "1m"         # max backoff
  }
  ssl {
    enabled = false
    verify  = true
    ca_cert = "/path/to/ca.crt"
  }
}

# --- Template blocks (render output files) ---
template {
  # REQUIRED
  source      = "/etc/consul-template/nginx.ctmpl"
  destination = "/etc/nginx/conf.d/upstream.conf"

  # OPTIONAL — run command after render
  command     = "sh -c 'nginx -t && nginx -s reload'"
  command_timeout = "60s"      # max time for command to run

  # OPTIONAL — wait window (debounce)
  wait {
    min = "2s"                  # minimum wait before re-render
    max = "10s"                 # maximum wait
  }

  # OPTIONAL — random splay delay
  splay = "2s"                  # random delay 0 to splay before command

  # ERROR handling
  error_on_missing_key = false  # true = exit if template key missing
  error_fatal          = true   # true = exit if render fails

  # FILE permissions
  perms = 0644                   # destination file permissions
  user  = "root"                 # destination file owner
  group = "root"                 # destination file group

  # BACKUP
  backup = true                  # backup previous destination

  # DELIMITERS (Go template)
  left_delimiter  = "{{"
  right_delimiter = "}}"

  # SANDBOX — limit filesystem access in templates
  sandbox_path = "/etc/nginx"   # template can only write inside this path

  # EXEC inside template (dangerous — use denylist)
  function_denylist = ["exec", "execTemplate"]  # disable dangerous functions

  # CREATE parent directories
  create_dest_dirs = true

  # Custom KV prefix (for multi-env)
  kv_path = ""                   # prefix for keyOrDefault lookups
}

# --- Exec mode (run managed process) ---
exec {
  command       = ["/usr/bin/my-app"]
  enabled       = true
  restart_on_SIGHUP = true
  env {
    pristine = false             # false = inherit env vars
    custom   = ["VAR=value"]
    allowlist = ["CONSUL_*"]    # pass these env vars
    denylist  = ["VAULT_*"]     # block these env vars
  }
  reload_signal  = "SIGHUP"     # Nginx config reload; USR1 chỉ reopen logs
  kill_signal    = "SIGTERM"    # signal to send for graceful stop
  kill_timeout   = "30s"        # force kill after timeout
}

# --- Syslog logging ---
syslog {
  enabled   = true
  facility  = "LOCAL5"         # syslog facility
  tag       = "consul-template"
}

# --- File logging (alternative to syslog) ---
log_file {
  path            = "/var/log/consul-template.log"
  log_rotate_bytes   = 10485760   # 10MB
  log_rotate_duration = "24h"
  log_rotate_max_files = 7
}
```

### 1.2 Nginx Template Example — Multi-Service Upstream

```nginx
# /etc/consul-template/nginx.ctmpl
# Renders all registered services from Consul as Nginx upstream blocks

# === UPSTREAM: Dynamic backends from Consul ===

upstream order_backend {
    server 127.0.0.1:1;  # placeholder — replaced by consul-template

    {{ range service "order-service" "any" }}
    server {{ .Address }}:{{ .Port }} max_fails=3 fail_timeout=30s;
    {{ end }}
}

upstream payment_backend {
    server 127.0.0.1:1;

    {{ range service "payment-service" "any" }}
    server {{ .Address }}:{{ .Port }}
        max_fails=3 fail_timeout=30s;
    {{ end }}
}

upstream catalog_backend {
    server 127.0.0.1:1;

    {{ range service "catalog-service" "any" }}
    server {{ .Address }}:{{ .Port }}
        max_fails=3 fail_timeout=30s;
    {{ end }}
}

# === HTTP SERVER ===

server {
    listen 80;
    server_name _;

    # Health check endpoint
    location /health {
        return 200 'OK';
        add_header Content-Type text/plain;
    }

    # Order service — path-based routing
    location /api/orders/ {
        proxy_pass http://order_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }

    # Payment service
    location /api/payments/ {
        proxy_pass http://payment_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }

    # Catalog service
    location /api/catalog/ {
        proxy_pass http://catalog_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }

    # Default upstream for unmatched paths
    location / {
        return 404 'Not Found';
        add_header Content-Type text/plain;
    }

    # Error logging
    access_log /var/log/nginx/access.log;
    error_log  /var/log/nginx/error.log warn;
}
```

### 1.3 Template Functions Reference

```go
// consul-template uses Go text/template

// Service catalog
service "<name>" "<tag>"        // Query services, optional tag filter
nodes "<name>"                  // Query catalog nodes for a service
datacenters                     // List all datacenters

// Key/Value store
key "<path>"                    // Single key value
keys "<prefix>"                 // All keys under prefix
keyOrDefault "<path>" "<default>"  // Fallback if key missing

// Health
{{ range service "order-svc" "any" }}
  {{ .ID }}                    // Service instance ID
  {{ .Node }}                  // Consul node name
  {{ .Address }}               // Service IP
  {{ .Port }}                  // Service port
  {{ .Tags }}                  // []string of tags
  {{ .Meta }}                  // map[string]string metadata
  {{ .Status }}                // "passing", "warning", "critical"
  {{ .Weights }}               // passingWeight, warningWeight
{{ end }}

// Conditional: only render if service exists
{{ if service "order-service" "any" }}
upstream order_backend {
  {{ range service "order-service" "any" }}
  server {{ .Address }}:{{ .Port }};
  {{ end }}
}
{{ end }}

// Tag-based filtering
{{ range service "order-service" "prod" }}
  // only services tagged "prod"
{{ end }}

// Meta-based filtering (requires template function)
{{ range services }}
  {{ if eq .Meta.env "production" }}
    // only services with meta.env=production
  {{ end }}
{{ end }}

// Math and comparison
{{ $count := len (service "order-svc" "any") }}
{{ if gt $count 0 }}
  // at least 1 service available
{{ end }}

// Datacenter awareness
{{ range datacenters }}
  {{ . }}  // dc1, dc2
{{ end }}
```

---

## 2. Kong DNS Environment Variables — Full Reference

### 2.1 DNS-Related Kong Configuration

```bash
# ============================================================
# Kong DNS configuration environment variables
# Kong 3.7
# ============================================================

# --- DNS Resolver ---
# Comma-separated list of DNS servers
# Format: IP:PORT or just IP (default port 53)
# For Consul: set to Consul DNS port
KONG_DNS_RESOLVER=consul:8600

# Multiple nameservers (fallback order)
# KONG_DNS_RESOLVER=consul:8600,8.8.8.8:53,1.1.1.1:53

# --- DNS TTL (in seconds) ---
# How long to cache a DNS response (from the TTL field in record)
# Lower = faster discovery, higher = less Consul load
KONG_DNS_TTL=30                    # default: 30s

# How long to serve stale data after TTL expires
# Critical for resilience — Consul blip không gây outage
KONG_DNS_STALE_TTL=4              # lab override; default Kong legacy dns_stale_ttl là 3600s

# TTL for NXDOMAIN (domain not found) responses
KONG_DNS_NOT_FOUND_TTL=1          # default: 1s

# TTL for DNS errors (SERVFAIL, REFUSED, etc.)
KONG_DNS_ERROR_TTL=1              # default: 1s

# --- DNS Cache ---
# Kong DNS cache is stored in lua_shared_dict
# Default dict name: kong_dns_cache (size set via KONG_MEM_CACHE_SIZE)
KONG_MEM_CACHE_SIZE=128m          # shared memory for Kong caches

# --- DNS Search Domain (Go template) ---
# Uses /etc/resolv.conf settings if Kong runs on host
# Supports ndots and search list (from Kong 3.0+)
# KONG_DNS_SEARCH_DOMAIN=service.consul

# --- DNS Order ---
# DNS record type lookup order
# Default legacy DNS client: LAST,SRV,A,CNAME
KONG_DNS_ORDER=SRV,A,AAAA,CNAME   # SRV first for service discovery
```

### 2.2 Kong kong.yml with DNS-based Service

```yaml
_format_version: "3.0"
_transform: true

services:
  # Service trỏ trực tiếp tới Consul DNS name
  # Kong sẽ resolve order-service.service.consul qua lua-resty-dns-client
  - name: order-service
    url: http://order-service.service.consul/api/orders
    # Không cần upstream entity — DNS resolver tự phân phối
    connect_timeout: 2000
    read_timeout: 30000
    write_timeout: 30000
    retries: 3
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: true
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true

  # Payment service — cũng dùng Consul DNS
  - name: payment-service
    url: http://payment-service.service.consul/api/payments
    connect_timeout: 2000
    read_timeout: 30000
    write_timeout: 30000
    retries: 3
    routes:
      - name: payment-route
        paths:
          - /api/v1/payments
        strip_path: true
```

### 2.3 Kong Upstream with Health Check + DNS Target

Khi dùng named upstream (Day 13) nhưng target là Consul DNS name:

```yaml
upstreams:
  # Upstream entity — dùng active health check
  - name: order-upstream
    algorithm: round-robin
    slots: 10000
    healthchecks:
      active:
        type: http
        http_path: /healthz
        interval: 10
        timeout: 5
        healthy:
          successes: 2
        unhealthy:
          tcp_failures: 1
          http_failures: 3
          timeouts: 3
      passive:
        type: http
        healthy:
          successes: 2
        unhealthy:
          http_failures: 5
          timeouts: 3
    targets:
      # Targets trỏ tới Consul DNS SRV record
      # Kong sẽ resolve order-service.service.consul và probe từng IP
      - target: order-service.service.consul:8080
        weight: 100

services:
  - name: order-service
    url: http://order-upstream/api/orders
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: true
```

---

## 3. Consul DNS — Full Configuration

### 3.1 Consul Server/Agent Config

```hcl
{
  "datacenter": "dc1",
  "data_dir": "/opt/consul/data",
  "log_level": "info",
  "server": true,
  "ui_config": {
    "enabled": true
  },
  "ports": {
    "dns": 8600,
    "http": 8500,
    "https": -1,
    "grpc": 8502,
    "serf_lan": 8301,
    "serf_wan": 8302,
    "server": 8300
  },
  "dns_config": {
    # Allow stale reads — any server (not just leader) answer DNS
    "allow_stale": true,

    # Maximum staleness — older data is not served
    "max_stale": "10s",

    # Service TTL per service
    "service_ttl": {
      "*": "30s"                  # default TTL for all services
      # "order-service": "10s",  # per-service override
      # "payment-service": "60s"
    },

    # Enable SRV records
    "enable_srv_override": false,

    # Filter: only return passing instances
    "only_passing": false,

    # ECS / Cloud auto-scaling: disable for fast deregister
    "enable_additional_node_meta_ds": true,

    # Recursor: forward unknown queries to upstream DNS
    # "recursors": ["8.8.8.8", "1.1.1.1"],

    # Base domain for service discovery
    "domain": "consul"
  },
  "enable_script_checks": false,
  "disable_update_check": true,
  "leave_on_terminate": false,
  "enable_syslog": false
}
```

### 3.2 Service Registration with Health Check

```json
{
  "ID": "order-1",
  "Name": "order-service",
  "Tags": ["prod", "v2", "us-east"],
  "Address": "10.0.1.15",
  "Port": 8080,
  "Meta": {
    "version": "2.1.0",
    "environment": "production"
  },
  "Check": {
    "ID": "order-1-health",
    "Name": "HTTP Health Check",
    "HTTP": "http://10.0.1.15:8080/healthz",
    "Interval": "10s",
    "Timeout": "5s",
    "DeregisterCriticalServiceAfter": "1m",
    "TLSSkipVerify": false
  }
}
```

### 3.3 Consul DNS Query Examples

```bash
# A record — trả về IP
dig @consul -p 8600 order-service.service.consul A +short

# SRV record — trả về IP + Port + Weight
dig @consul -p 8600 order-service.service.consul SRV +short

# Health filter: bật dns_config.only_passing=true trong Consul agent
dig @consul -p 8600 order-service.service.consul A +short

# API mới có filter per-request
curl 'http://consul:8500/v1/health/service/order-service?passing=true'

# Tag-based filter
dig @consul -p 8600 prod.order-service.service.consul A +short

# Multiple tag filter
dig @consul -p 8600 v2.prod.order-service.service.consul A +short

# Reverse DNS (PTR record)
dig @consul -p 8600 -x 10.0.1.15 PTR +short

# DNS zone transfer (all records) — requires ACL
dig @consul -p 8600 axfr service.consul AXFR +tcp
```

---

## 4. Comparison: Consul vs Kubernetes Service vs Envoy xDS

### 4.1 Consul Service Discovery

```
Pros:
+ HashiCorp ecosystem — Vault, Terraform integration
+ Cross-platform (VM, Docker, bare metal)
+ Built-in health check + ACL
+ DNS + HTTP API dual access
+ consul-template cho Nginx integration
+ Service mesh (Consul Connect) optional

Cons:
- Extra infrastructure component
- ACL complexity cao cho production
- DNS-based ( không push notification)
- Multi-datacenter federation phức tạp
```

### 4.2 Kubernetes Service (DNS-based)

```
Pros:
+ Native Kubernetes — không cần extra component
+ Integration với K8s native tools
+ Headless Service cho stateful set
+ Auto registration via Kubelet

Cons:
- Chỉ trong Kubernetes cluster
- Không có built-in health check (dùng K8s probe)
- Cross-cluster service discovery cần Federation hoặc Service Mesh
- Không có native Nginx integration
```

### 4.3 Envoy xDS (Service Mesh)

```
Pros:
+ Dynamic config via xDS API
+ Envoy là gold standard service proxy
+ Built-in circuit breaker, retry, timeout
+ Envoy Admin API + statsd/prometheus

Cons:
- Envoy complexity cao (không phải API Gateway)
- cần control plane (Istio, Kontena, etc.)
- Không có plugin ecosystem như Kong
- Debugging xDS rất khó
```

### 4.4 Comparison Matrix

| Feature | Consul | Kubernetes Service | Envoy xDS | AWS Cloud Map |
|---|---|---|---|---|
| **Platform** | Any | K8s only | Any | AWS only |
| **Registration** | Self / Agent | Kubelet | Sidecar | SDK/API |
| **Health check** | Built-in | K8s probe | Envoy HC | ELB health |
| **DNS interface** | Yes (8600) | Yes (kube-dns) | No | Yes |
| **Nginx integration** | consul-template | None | None | None |
| **Kong integration** | DNS resolver | K8s ingress | None | DNS resolver |
| **mTLS** | Consul Connect | K8s mTLS | Envoy mesh | ACM private CA |
| **ACL** | HashiCorp ACL | RBAC | Envoy RBAC | IAM |
| **Multi-DC** | Federation | Federation (v1.18+) | Global rate limit | Cross-region |
| **Ops complexity** | Trung bình | Thấp | Cao | Thấp |
| **Setup time** | Giờ | Phút | Ngày | Phút |

### 4.5 When to Use What

```
Scenario:
  Non-Kubernetes, multi-cloud → Consul
  Kubernetes-native → Kubernetes Service
  Service mesh required → Consul Connect hoặc Istio
  AWS-only workload → AWS Cloud Map + Kong DNS
  Hybrid K8s + VM → Consul (single source of truth)
```

---

## 5. Watch + Template Performance Deep Dive

### 5.1 Consul Catalog API vs DNS — When to Use Which

```bash
# ============================================================
# consul-template uses Consul Catalog API
# NOT Consul DNS for service discovery
# ============================================================

# consul-template blocking query (Catalog API)
GET /v1/catalog/service/order-service?wait=10s&index=<last_index>
Response:
{
  "Index": 12345,
  "Nodes": [
    {
      "ID": "order-1",
      "Node": "consul-server",
      "Address": "10.0.1.15",
      "ServicePort": 8080,
      "ServiceTags": ["prod"],
      "ServiceMeta": {"version": "2.1.0"},
      "ServiceEnableTagOverride": false
    }
  ]
}

# Kong uses Consul DNS
# GET /v1/catalog/service/<name> is faster than DNS
# But: DNS is standard, works with any DNS client
# For Kong: DNS is preferred because lua-resty-dns-client handles it natively
```

### 5.2 consul-template Benchmark (Approximate)

> Lưu ý: số liệu chỉ dùng để tham khảo. Test trong Docker Compose, single node, 4 service × 5 replica.

```
Test: 5 service changes in 2 seconds
========================================

No debounce:
  Reload count:     5
  Avg reload time:  ~80ms
  Total downtime:    400ms (sequential)

Debounce 5s + splay 2s:
  Reload count:     1 (after 5-7s delay)
  Reload time:      ~150ms
  Stale window:     5-7s (no change detected during debounce)
  Total downtime:    150ms

Debounce 10s + splay 5s:
  Reload count:     1 (after 10-15s delay)
  Reload time:      ~200ms
  Stale window:     10-15s
  Total downtime:    200ms

========================================
Trade-off: Stale window vs Reload frequency
Recommended: debounce 5s, splay 2s (sensible for most workloads)
For rapid scaling: debounce 10s, splay 3s (accept slower detection)
```

### 5.3 consul-template Memory & CPU

```
consul-template resource usage:
  CPU: ~1-3% per template block
  Memory: ~20-50MB per daemon
  Network: 1 blocking query per template × Consul server
  File descriptor: 1-3 per template (config file, PID file)

Scaling consul-template:
  - 1 daemon per Nginx node (horizontally scalable)
  - Multiple template blocks in same daemon (reduce overhead)
  - Watch same Consul datacenter from multiple daemons (OK)
```

---

## 6. Troubleshooting Case Studies

### Case Study 1: consul-template — duplicate `upstream` sau reload

**Symptom**: Sau khi consul-template reload, Nginx trả lỗi:
```
nginx: [emerg] duplicate upstream "order_backend" in /etc/nginx/conf.d/upstream.conf:3
```

**Root cause**: Static Nginx config đã có `upstream order_backend`, sau đó consul-template lại render thêm một block cùng tên vào file khác. Nginx OSS cho phép nhiều `server` trỏ cùng IP:port trong upstream, nhưng không cho định nghĩa cùng một upstream name hai lần.

```nginx
# /etc/nginx/conf.d/default.conf
upstream order_backend {
    server 127.0.0.1:1;
}

# /etc/nginx/conf.d/upstream.conf
upstream order_backend {
    server 10.0.1.15:8080;
    server 10.0.1.42:8080;
}
```

**Fix**:
```nginx
# Chỉ để consul-template sở hữu upstream dynamic.
# Static server block proxy_pass tới upstream đó, không định nghĩa lại upstream.
upstream order_backend {
    server 127.0.0.1:1;
    {{ range service "order-service" "any" }}
    server {{ .Address }}:{{ .Port }} max_fails=3 fail_timeout=30s;
    {{ end }}
}
```

**Better fix**: Trong lab Day 18 dùng container `nginx-ct` để một process tree sở hữu cả generated file và reload command. Nếu tách container, phải share volume destination và reload qua Docker socket, sidecar supervisor, hoặc endpoint nội bộ có kiểm soát.

### Case Study 2: Kong DNS — Service name leak ra public DNS

**Symptom**: DNS query `order-service.service.consul` được forward ra public DNS (8.8.8.8), trả về NXDOMAIN, service không resolve.

**Root cause**: `KONG_DNS_RESOLVER` không được set, Kong dùng system resolver (`/etc/resolv.conf`) — không trỏ tới Consul.

**Fix**:
```bash
# Wrong: KONG_DNS_RESOLVER=8.8.8.8
# Right:
KONG_DNS_RESOLVER=consul:8600

# Verify: trong Kong container
docker exec kong dig @consul -p 8600 order-service.service.consul SRV

# Hoặc dùng dnsmasq forwarding:
# dnsmasq config:
#   server=/service.consul/consul:8600
#   server=8.8.8.8
# KONG_DNS_RESOLVER=<dnsmasq-ip>:53
```

### Case Study 3: consul-template — Template render OK nhưng Nginx reload fail

**Symptom**: consul-template log OK, nhưng upstream không được update.

**Root cause**: Template render tạo file mới OK, nhưng `nginx -s reload` fail — không có quyền hoặc Nginx đang starting.

```
# Check: xem consul-template log
docker logs nginx-ct

# Lỗi có thể:
# 1. nginx -s reload: "nginx not running"
# 2. nginx -t: "test failed: duplicate upstream"
# 3. Permission denied on destination directory

# Fix: validate trước khi reload
command = "sh -c 'nginx -t && nginx -s reload'"
```

### Case Study 4: Kong + Consul SRV — Port 0 trong SRV record

**Symptom**: Kong log: "dns resolver error: port must be between 1 and 65535"

**Root cause**: Consul service registered với port=0 (placeholder port), hoặc SRV record bị misconfigured.

```
# Check SRV record
dig @consul -p 8600 order-service.service.consul SRV

# Wrong:
# order-service.service.consul. 300 IN SRV 1 1 0 order-1.node.dc1.consul.

# Right:
# order-service.service.consul. 300 IN SRV 1 1 8080 order-1.node.dc1.consul.
```

**Fix**: Đảm bảo service registration có port đúng:
```json
{
  "Name": "order-service",
  "Port": 8080,     // Must be > 0
  ...
}
```

### Case Study 5: consul-template + Nginx — Race condition khi service flap

**Symptom**: Nginx upstream có server IP không còn tồn tại trong Consul (dang deregister).

**Root cause**: Consul deregister rồi, nhưng consul-template chưa kịp re-render.

```
Timeline:
t=0s    Instance order-3 deregister (Consul)
t=0.1s  Consul notifies consul-template (blocking query returns)
t=0.2s  consul-template render (2 instances)
t=0.3s  BUT: nginx -s reload đang chạy từ t=0s (trước đó)
t=0.5s  Nginx reload hoàn thành với config mới (2 instances)
t=0.3s  consul-template reload command → no-op (reload đã done)
→ Race: 200ms window với stale IP
```

**Fix**: Thêm reload lock:
```hcl
template {
  command = "flock /tmp/nginx-reload.lock -c 'nginx -s reload'"
}
```
