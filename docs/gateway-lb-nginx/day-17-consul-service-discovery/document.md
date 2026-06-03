# Day 17: Deep Dive — Consul API Reference, Security, Comparison & Internals

---

## 1. Consul HTTP API — Complete Cheatsheet

### 1.1 Agent API (`/v1/agent/`)

```bash
# === Service Registration ===
# Register service
PUT /v1/agent/service/register
Body: JSON (xem lesson.md Section 3.3)

# Deregister service
PUT /v1/agent/service/deregister/{service_id}

# List registered services (local agent)
GET /v1/agent/services
# Response:
# {
#   "order-service-1": {
#     "ID": "order-service-1",
#     "Service": "order-service",
#     "Tags": ["prod"],
#     "Port": 8080,
#     "Address": "10.0.1.10"
#   }
# }

# === Health Check ===
# Register health check
PUT /v1/agent/check/register
Body: {"Name": "order-health", "HTTP": "http://10.0.1.10:8080/health", "Interval": "10s"}

# TTL check: pass (mark healthy)
PUT /v1/agent/check/pass/{check_id}

# TTL check: fail (mark unhealthy)
PUT /v1/agent/check/fail/{check_id}

# TTL check: warn
PUT /v1/agent/check/warn/{check_id}

# Deregister check
PUT /v1/agent/check/deregister/{check_id}

# List health checks (local agent)
GET /v1/agent/checks
# Response:
# {
#   "service:order-service-1": {
#     "CheckID": "service:order-service-1",
#     "Name": "Service 'order-service' check",
#     "Status": "passing",
#     "Output": "HTTP get http://10.0.1.10:8080/health: 200 OK",
#     "ServiceID": "order-service-1"
#   }
# }

# === Agent Control ===
# Join cluster
PUT /v1/agent/join/{address}

# Force leave
PUT /v1/agent/force-leave/{node}

# Reload config
PUT /v1/agent/reload

# Read config
GET /v1/agent/self

# Metrics
GET /v1/agent/metrics
```

### 1.2 Catalog API (`/v1/catalog/`)

```bash
# === Service Catalog (authoritative source) ===
# List all services
GET /v1/catalog/services
# Response:
# {
#   "order-service": ["prod", "api"],
#   "payment-service": ["prod"]
# }

# Service instances (all, including unhealthy)
GET /v1/catalog/service/{service-name}
# Query params: ?dc=dc1
# Response:
# [
#   {
#     "Node": "consul-client-1",
#     "Address": "10.0.1.10",
#     "ServiceID": "order-service-1",
#     "ServiceName": "order-service",
#     "ServiceTags": ["prod"],
#     "ServicePort": 8080,
#     "ServiceMeta": {"version": "1.2.3"}
#   }
# ]

# Node details
GET /v1/catalog/node/{node-name}

# Datacenter info
GET /v1/catalog/datacenters
```

### 1.3 Health API (`/v1/health/`)

```bash
# === Health Checks (use this for service discovery) ===
# Healthy instances (recommended for discovery)
GET /v1/health/service/{service-name}?passing=true
# Query params:
#   ?passing=true    — only healthy (passing) checks
#   ?passing=false   — all instances
#   ?warning=true    — include warning checks
#   ?dc=dc1          — specific datacenter
#   ?near=_agent     — sort by proximity to agent
#   ?tag=prod        — filter by tag

# Response:
# [
#   {
#     "Node": {
#       "Node": "consul-client-1",
#       "Address": "10.0.1.10"
#     },
#     "Service": {
#       "ID": "order-service-1",
#       "Service": "order-service",
#       "Tags": ["prod", "api"],
#       "Port": 8080,
#       "Address": "10.0.1.10",
#       "Meta": {"version": "1.2.3"}
#     },
#     "Checks": [
#       {
#         "CheckID": "service:order-service-1",
#         "Status": "passing",
#         "Output": "HTTP check..."
#       }
#     ]
#   }
# ]

# Health check for specific service + node
GET /v1/health/checks/{service-name}

# Critical health checks
GET /v1/health/state/critical
# State values: passing, warning, critical
```

### 1.4 KV Store API (`/v1/kv/`)

```bash
# === Key-Value Store (simple use only) ===
# Set key
PUT /v1/kv/order-service/config
Body: '{"replicas": 3, "timeout_ms": 5000}'

# Get key
GET /v1/kv/order-service/config

# Get key with metadata
GET /v1/kv/order-service/config?raw

# List keys (prefix)
GET /v1/kv/?recurse
GET /v1/kv/order-service/?recurse

# Delete key
DELETE /v1/kv/order-service/config

# CAS (Check-And-Set — atomic update)
PUT /v1/kv/order-service/config?cas=15
# Header: X-Consul-Index: 15 (phải khớp mới update được)

# ⚠️ KHÔNG dùng KV cho config-store production
#   → KV không có versioning
#   → KV không có ACL per-key mặc định
#   → Dùng consul-template với blocking query để detect change
```

### 1.5 Status API (`/v1/status/`)

```bash
# Current Raft leader
GET /v1/status/leader
# Response: "\"10.0.1.5:8300\""

# All Raft peers
GET /v1/status/peers
# Response:
# [
#   "10.0.1.5:8300",
#   "10.0.1.6:8300",
#   "10.0.1.7:8300"
# ]
```

---

## 2. Consul ACL & Encryption

### 2.1 Gossip Encryption

```
Consul gossip (serf) có thể encrypted bằng shared key (keyring).

Key format: 32 bytes base64-encoded (16 bytes raw key)

Generate key:
  consul keygen
  # Output: ZxB5L7H8f2gDq3mN9tR4wY6pA0kE1jC=

Config (trên tất cả agent — server và client):
{
  "encrypt": "ZxB5L7H8f2gDq3mN9tR4wY6pA0kE1jC=",
  "encrypt_verify_incoming": true,
  "encrypt_verify_outgoing": true
}

⚠️ Nếu key không khớp giữa các agent → join fail, "Encryption
   key mismatch"
```

### 2.2 TLS Encryption (mTLS for HTTP/RPC)

```bash
# Generate CA + certificates cho Consul
# Step 1: CA
openssl genrsa -out consul-ca-key.pem 4096
openssl req -x509 -new -nodes -sha256 \
  -key consul-ca-key.pem \
  -out consul-ca.crt \
  -days 3650 \
  -subj "/CN=Consul CA"

# Step 2: Server certificate (for server agents)
openssl genrsa -out consul-server-key.pem 2048
openssl req -new -sha256 \
  -key consul-server-key.pem \
  -out consul-server.csr \
  -subj "/CN=server.dc1.consul" \
  -addext "subjectAltName=DNS:server.dc1.consul,DNS:localhost,IP:127.0.0.1"

# Sign server cert với CA
openssl x509 -req -in consul-server.csr \
  -CA consul-ca.crt \
  -CAkey consul-ca-key.pem \
  -CAcreateserial \
  -out consul-server.crt \
  -days 365 -sha256 \
  -extfile <(printf "subjectAltName=DNS:server.dc1.consul,DNS:localhost,IP:127.0.0.1")

# Server config with TLS
{
  "server": true,
  "cert_file": "/etc/consul/tls/consul-server.crt",
  "key_file": "/etc/consul/tls/consul-server-key.pem",
  "ca_file": "/etc/consul/tls/consul-ca.crt",
  "verify_incoming": true,
  "verify_outgoing": true,
  "verify_server_hostname": true,
  "ports": {
    "https": 8501
  }
}
```

### 2.3 ACL System — Overview

```
Consul ACL bảo vệ:
  - HTTP API (ai được đọc/ghi service registration, KV)
  - Node API (ai được join, force-leave)
  - Consul DNS (ai được truy vấn DNS)

ACL components:
  - Token = bearer token cho API requests
  - Policy = rule set (whitelist)
  - Roles = group of policies
  - Services = service identity (for intention)

Token types:
  - Master token (bootstrap): full access
  - Agent token: gửi check, register service trên local agent
  - Service token: service-specific access
  - Anonymous token: không authenticated

⚠️ Trong phạm vi Day 17/18, ACL là overview only.
   Production nên enable ACL:
   {
     "acl": {
       "enabled": true,
       "default_policy": "deny",
       "enable_token_persistence": true
     }
   }
```

---

## 3. Service Discovery Comparison — Deep Dive

### 3.1 Detailed Comparison Table

| Tiêu chí | Consul | etcd | Eureka | K8s Service | ZooKeeper |
|---|---|---|---|---|---|
| **Data store** | Raft (embedded) | Raft (external) | Peer-to-peer | etcd (via API server) | ZAB (embedded) |
| **Protocol** | HTTP/DNS | gRPC | HTTP/Eureka client | Kube-proxy (iptables/IPVS) | Custom (ZK client) |
| **Health check** | Native (HTTP/TCP/TTL/Script) | External (registrator, consul-template) | Client heartbeat | Liveness/Readiness probe | External |
| **Consistency** | Strong (Raft) | Strong (Raft) | Eventual (AP) | Eventual (AP) | Strong (ZAB) |
| **Latency** | DNS: 2-5ms, API: 5-15ms | 3-10ms | 10-30ms | 1-5ms (in-cluster) | 5-20ms |
| **Multi-DC** | Native (WAN gossip) | Manual federation | AWS Region only | federation.v1alpha1 | Không |
| **DNS SRV** | Có | Partial | Không | Có (headless) | Không |
| **Language/Platform** | Go, multi-platform | Go, multi-platform | Java, Netflix OSS | Go, K8s only | Java, multi-platform |
| **Learning curve** | Trung bình | Cao | Thấp | Thấp (K8s user) | Cao |
| **Operation complexity** | Medium | High | Medium | Low | High |
| **Use case fit** | Multi-platform, DNS-first | K8s + distributed config | Spring Cloud, Netflix | K8s-internal only | Legacy Apache ecosystem |

### 3.2 Consistency Models — Why It Matters

```
CP (Consistent + Partition-tolerant):
  Consul, etcd, ZooKeeper
  → Khi network partition xảy ra:
    - Write: FAIL (không thể replicate đến majority)
    - Read: có thể stale (từ follower) hoặc fail (leader không available)
  → Đảm bảo: không có 2 node cùng tin rằng mình là leader

AP (Available + Partition-tolerant):
  Eureka, Kubernetes Service
  → Khi network partition xảy ra:
    - Tất cả node vẫn serve read
    - Có thể có stale data
    - 2 partition đều available
  → Đảm bảo: service luôn available để đọc

Service discovery: AP thường acceptable
  → Vì service registry không cần strong consistency
  → Stale IP trong vài giây = acceptable
  → Unavailability = outage

Config store: CP bắt buộc
  → Distributed lock, config change phải consistent
```

### 3.3 When to Use Consul vs Alternatives

```
Dùng Consul KHI:
  ✓ Multi-platform (VM + bare metal + K8s + cloud)
  ✓ Cần DNS-based discovery (SRV record)
  ✓ Multi-datacenter deployment
  ✓ Cần built-in health check
  ✓ Đã dùng HashiCorp stack (Vault, Nomad)
  ✓ Service mesh use case (Connect)

Dùng etcd KHI:
  ✓ Kubernetes control plane (đã có sẵn)
  ✓ Cần distributed config + service discovery trong K8s
  ✓ Cần watch feature cho distributed lock
  ✓ Đã dùng K8s native

Dùng Eureka KHI:
  ✓ Spring Cloud microservice stack
  ✓ Netflix OSS ecosystem (Hystrix, Zuul)
  ✓ Không cần multi-cloud/multi-DC
  ✓ Java-first organization

Dùng Kubernetes Service KHI:
  ✓ 100% Kubernetes workload
  ✓ Không cần expose ra ngoài cluster
  ✓ Đơn giản là đủ

Dùng ZooKeeper KHI:
  ✓ Legacy Apache Kafka, Hadoop ecosystem
  ✓ Đã có operational expertise
  ✓ Cần distributed coordination (không phải service discovery)
```

---

## 4. Watch & Blocking Query Patterns

### 4.1 Blocking Query Pattern (consul-template core)

```bash
# Manual blocking query loop (để hiểu consul-template)
#!/bin/bash
CONSUL_ADDR="http://consul-server:8500"
SERVICE="order-service"

INDEX_FILE="/tmp/order-service.index"

# Get initial index
get_index() {
  curl -s "${CONSUL_ADDR}/v1/health/service/${SERVICE}?passing=true" \
    | jq -r '.[0].CreateIndex'
}

# Blocking query
watch() {
  CURRENT_INDEX=$(get_index)

  while true; do
    RESPONSE=$(curl -s \
      "${CONSUL_ADDR}/v1/health/service/${SERVICE}?passing=true&index=${CURRENT_INDEX}&wait=60s")

    NEW_INDEX=$(echo "$RESPONSE" | jq -r '.[0].ModifyIndex')

    if [ "$NEW_INDEX" != "$CURRENT_INDEX" ]; then
      echo "Service list changed at index ${NEW_INDEX}"
      # Render config, reload nginx
      # render_nginx_config.sh
      CURRENT_INDEX="$NEW_INDEX"
    fi
  done
}

watch
```

### 4.2 consul-template Configuration

```bash
# consul-template config file
cat > /etc/consul-template/config.hcl << 'EOF'
# Consul connection
consul {
  address = "consul-server:8500"
  token   = "anonymous"  # Hoặc ACL token
  retry   = "4s"
}

# Template block
template {
  source      = "/etc/consul/templates/nginx.ctmpl"
  destination = "/etc/nginx/conf.d/consul-upstream.conf"
  command     = "nginx -s reload"
  command_timeout = "30s"
  error_on_missing = true
  wait {
    min = "2s"
    max = "10s"
  }
}

# Retry settings
retry {
  backoff    = "1s"
  max_backoff = "60s"
  max_elapsed = "5m"
}

# Log
log_level = "info"
```

### 4.3 consul-template Template Syntax

```bash
# nginx.ctmpl — template với groups
upstream order_backend {
    least_conn;
{{ range services "order-service" "any" }}
{{ range service "order-service" "passing" }}
    server {{ .Address }}:{{ .Port }};
{{ end }}
{{ end }}
}

upstream payment_backend {
    least_conn;
{{ range services "payment-service" "any" }}
{{ range service "payment-service" "passing" }}
    server {{ .Address }}:{{ .Port }};
{{ end }}
{{ end }}
}

# Filter by tag
upstream order_backend_prod {
{{ range service "order-service" "passing" "prod" }}
    server {{ .Address }}:{{ .Port }};
{{ end }}
}

# With meta (metadata)
{{ range services "order-service" "passing" }}
{{ with .Meta }}
# version: {{ .version }}
{{ end }}
{{ end }}

# Template với KV store
{{ with $data := key "order-service/config" }}
# replicas: {{ .replicas }}
{{ end }}
```

### 4.4 Alternatives to consul-template

```
Ngoài consul-template, có các tool khác:

1. consul-template (HashiCorp) — standard
   Pros: mature, widespread, declarative
   Cons: file-based reload, nginx reload required

2. consul-replicate (HashiCorp)
   Pros: KV sync tool, simple
   Cons: KV only, no template

3. registrator (Gluster/Proj) + consul-template
   Pros: Auto-register Docker containers
   Cons: Extra component

4. consul-sdk (Python/Go)
   Pros: Programmatic, full control
   Cons: Code required

5. Kubernetes: ExternalDNS + Consul
   Pros: K8s native DNS
   Cons: Extra sync layer

6. DNS forwarder (dnsmasq/systemd-resolved + Consul)
   Pros: No reload needed, real-time DNS
   Cons: TTL stale risk, less control
```

---

## 5. Raft Cluster Sizing & Operations

### 5.1 Quorum Calculator

```
Quorum = (N / 2) + 1, rounded up

N = 1:  quorum = 1   (single point of failure — KHÔNG NÊN)
N = 2:  quorum = 2   (split-brain possible — KHÔNG NÊN)
N = 3:  quorum = 2   ✓ OK (1 failure OK)
N = 4:  quorum = 3   (2 failures OK, but even number — avoid)
N = 5:  quorum = 3   ✓ OK (2 failures OK)
N = 6:  quorum = 4   (2 failures OK, but even number — avoid)
N = 7:  quorum = 4   ✓ OK (3 failures OK)
N = 8:  quorum = 5   (3 failures OK, but even number — avoid)

→ Luôn dùng odd number: 3, 5, 7
```

### 5.2 Recommended Cluster Sizes

| Size | Quorum | Fault tolerance | Recommended use |
|---|---|---|---|
| 3 | 2 | 1 server down | Dev/staging, small production |
| 5 | 3 | 2 server down | Medium production, multi-AZ |
| 7 | 4 | 3 server down | Large production, compliance |

**Không nên dùng nhiều hơn 7 server trong 1 datacenter:**
- Raft replication: mỗi write phải replicate đến majority → thêm server = thêm latency
- Gossip overhead: tăng nhưng không đáng kể
- Operational complexity: tăng theo N²

### 5.3 Bootstrap vs bootstrap_expect

```bash
# bootstrap_expect = N
# Consul sẽ không bootstrap cho đến khi có N server cùng join
{
  "bootstrap_expect": 3
}
# Recommended cho production: dùng bootstrap_expect, không dùng bootstrap

# bootstrap = true (legacy, cho single-node dev only)
{
  "bootstrap": true
}
# ⚠️ KHÔNG dùng trong production
#   → Single node = single point of failure
#   → Khi cluster grow: phải migrate từ bootstrap=true → bootstrap_expect
```

### 5.4 Raft Operations

```bash
# View Raft peers
curl -s http://localhost:8500/v1/status/peers

# View Raft leader
curl -s http://localhost:8500/v1/status/leader

# Force remove failed server (sau khi force-leave)
# Step 1: Xác định peer IP
curl -s http://localhost:8500/v1/status/peers
# ["10.0.1.5:8300","10.0.1.6:8300","10.0.1.7:8300"]

# Step 2: Remove peer
curl -X DELETE http://localhost:8500/v1/admin/peer?address=10.0.1.7:8300

# Raft snapshot (backup state)
# Tự động every 30s (nếu dirty > 8192), configurable
# Manual snapshot:
curl -s -X PUT http://localhost:8500/v1/snapshot

# Restore snapshot:
consul snapshot restore backup.snap

# Raft tuning
{
  "performance": {
    "raft_multiplier": 2,  # 1=fast, 5=stable (default)
    "leave_drain_time": "5s"
  }
}
```

---

## 6. Security Checklist

### 6.1 Production Security Checklist

```
□ Gossip encryption:
  → Set encrypt key trên tất cả agent
  → Xác minh: consul members -key-file /path/to/key (phải thấy encrypted)

□ TLS for HTTP API:
  → Enable HTTPS port 8501
  → verify_incoming = true (server và client)
  → verify_outgoing = true

□ ACL enabled:
  → bootstrap ACL system
  → Tạo policy cho mỗi service
  → Không dùng anonymous token trong production

□ Consul UI:
  → Enable auth (basic auth hoặc OIDC)
  → Chỉ expose trên internal network
  → Không expose port 8500 ra Internet

□ Network:
  → Gossip port 8301: chỉ internal network
  → Server RPC 8300: chỉ giữa các server
  → HTTP API 8500: internal network hoặc load balancer
  → DNS 8600: internal network hoặc filtered

□ Audit:
  → Enable ACL audit logging
  → Monitor /v1/agent/metrics cho suspicious activity
```

### 6.2 Network Ports Reference

| Port | Protocol | Direction | Mục đích |
|---|---|---|---|
| 8300 | TCP | Server ↔ Server | Raft RPC (leader election, replication) |
| 8301 | TCP/UDP | All ↔ All (LAN) | Gossip LAN (member discovery, health) |
| 8302 | TCP/UDP | Server ↔ Server (WAN) | Gossip WAN (cross-DC) |
| 8500 | TCP | Client → Server | HTTP API (Consul HTTP) |
| 8501 | TCP | Client → Server | HTTPS API (TLS) |
| 8600 | UDP/TCP | Client → Server | DNS interface |

---

## 7. DNS Caching & Integration Patterns

### 7.1 Consul DNS Caching Strategy

```bash
# Consul DNS cache settings
{
  "dns_config": {
    "allow_stale": true,           # Cho phép stale read từ any server (nhanh hơn)
    "max_stale": "200s",           # Max staleness cho stale read
    "stale_max_age": 43200,        # Tự động serve stale sau 12h nếu leader unavailable
    "enable_truncate": true,       # Truncate response nếu > 512 bytes
    "only_passing": false,         # true = chỉ trả passing health check
    "always_refresh": false,       # true = không bao giờ cache (force real-time)
    "ttl": {
      "a": "0s",                   # TTL cho A record (0 = không cache, luôn hỏi Consul)
      "aaaa": "0s",
      "cname": "0s",
      "txt": "0s",
      "srv": "0s"
    }
  }
}

# Recommended production config:
{
  "dns_config": {
    "allow_stale": true,
    "max_stale": "200s",
    "only_passing": true,          # Chỉ trả IP healthy
    "ttl": {
      "a": "30s",                  # Cache 30s
      "srv": "30s",
      "cname": "60s"
    }
  }
}
```

### 7.2 DNS Forwarder Integration

```
Pattern 1: dnsmasq + Consul (recommended)
  1. dnsmasq listen on port 53
  2. dnsmasq forward .consul queries → Consul DNS (port 8600)
  3. dnsmasq forward all other queries → upstream DNS (8.8.8.8)
  4. Application dùng Consul DNS tự nhiên

Pattern 2: systemd-resolved + Consul
  1. systemd-resolved listen on 127.0.0.53
  2. Add consul to DNSStubListenerExtra
  3. /etc/resolv.conf: nameserver 127.0.0.53

Pattern 3: CoreDNS + Consul
  1. CoreDNS forward .consul → Consul DNS
  2. CoreDNS resolve all other → upstream
```

```bash
# dnsmasq config
cat > /etc/dnsmasq.d/10-consul << 'EOF'
# Listen on all interfaces
interface=*

# Consul DNS
server=/consul/127.0.0.1#8600

# Upstream DNS (fallback)
server=8.8.8.8
server=8.8.4.4

# Don't read /etc/resolv.conf
no-resolv

# Never forward plain names (without .consul)
domain-needed

# Never forward reverse-lookup for private IPs
bogus-priv
EOF

# systemctl restart dnsmasq
# Test: dig order-service.service.consul @localhost
```

---

## 8. References

- **HashiCorp Consul API**: Complete API reference
  <https://developer.hashicorp.com/consul/api-docs>
- **HashiCorp Consul Agent**: Configuration reference
  <https://developer.hashicorp.com/consul/docs/agent/config>
- **consul-template Documentation**: Template syntax and configuration
  <https://developer.hashicorp.com/consul/docs/dynamic-application-configurations/consul-template>
- **Raft Consensus Algorithm**: Original paper
  <https://raft.github.io/raft.pdf>
- **SWIM: Scalable Weakly-consistent Infection-style Membership**
  <https://www.cs.cornell.edu/~asharifin/papers/swim.pdf>
- **Cloudflare Blog**: Service Discovery with Consul
  <https://blog.cloudflare.com/tag/consul/>
- **HashiCorp Learn**: Consul Service Mesh and Distributed Monitoring
  <https://learn.hashicorp.com/tutorials/consul/service-mesh-overview>
- **Netflix Eureka GitHub**: Eureka source and documentation
  <https://github.com/Netflix/eureka>
- **etcd Documentation**: Service discovery and configuration
  <https://etcd.io/docs/latest/>
- **Kubernetes Services**: Official documentation
  <https://kubernetes.io/docs/concepts/services-networking/service/>
