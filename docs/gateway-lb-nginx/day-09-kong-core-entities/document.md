# Day 09 — Kong Core Entities: Reference Document

> **Scope**: Entity field reference, path_handling deep dive, expressions router DSL, plugin precedence matrix
> **Reference**: Kong 3.6

---

## A. Entity Reference Tables

### A.1 Service Entity

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | yes | — | Unique identifier, snake_case recommended |
| `protocol` | string | yes | — | `http`, `https`, `grpc`, `grpcs`, `tcp`, `tls`, `udp` |
| `host` | string | yes* | — | Upstream hostname or IP; `*` for wildcard (Kong 3.x) |
| `port` | integer | yes* | — | Upstream port (1-65535) |
| `path` | string | no | null | Upstream path prefix (e.g. `/api`) |
| `retries` | integer | no | 5 | Number of retry attempts |
| `connect_timeout` | integer | no | 60000 | Connection timeout in ms |
| `read_timeout` | integer | no | 60000 | Read timeout in ms |
| `write_timeout` | integer | no | 60000 | Write timeout in ms |
| `tags` | array | no | — | Meta tags for filtering: `["team-a", "env-prod"]` |
| `client_certificate` | string | no | — | ID of Certificate entity for mTLS to upstream |
| `tls_server_name` | string | no | — | SNI to use when TLS handshake với upstream |
| `url` | string | no | — | Shorthand: `http://host:port/path` auto-parsed into above fields |

*\*host + port required unless url shorthand is used.*

```bash
# URL shorthand parse example:
# url="https://api.example.com:8443/v2/orders"
#   → protocol="https", host="api.example.com", port=8443, path="/v2/orders"

# Service trỏ tới Upstream (virtual LB entity, deep dive Day 13):
curl -X POST http://localhost:8001/services \
  -d "name=order-service" \
  -d "url=http://order-upstream/api"
```

---

### A.2 Route Entity

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | yes | — | Unique identifier |
| `service` | string | yes | — | Service `id` or `name` (FK) |
| `protocols` | array | no | `["http","https"]` | `["http"]`, `["https"]`, `["tcp","tls"]`, etc. |
| `methods` | array | no | — | HTTP methods: `["GET","POST"]` |
| `hosts` | array | no | — | Host matching: `["api.example.com","*.admin.example.com"]` |
| `paths` | array | no | — | Path matching; prefix match or regex (`~/...`) |
| `headers` | object | no | — | Header matching: `{"X-API-Tier": ["premium"]}` |
| `snis` | array | no | — | TLS SNI matching (for tls-based routes) |
| `sources` | array | no | — | Source IP matching: `[{"ip":"10.1.0.0/16"}]` |
| `destinations` | array | no | — | Dest IP matching |
| `regex_priority` | integer | no | 0 | Higher = higher precedence among regex routes |
| `strip_path` | boolean | no | `true` | Strip matched route path prefix before proxying |
| `preserve_host` | boolean | no | `false` | Forward original Host header vs. set upstream host |
| `path_handling` | string | no | `"v0"` | Path concatenation strategy: `v0` or `v1` |
| `request_buffering` | boolean | no | `true` | Buffer request body |
| `response_buffering` | boolean | no | `true` | Buffer response body |
| `tags` | array | no | — | Meta tags |

```bash
# Regex path (Kong 2.x / Kong 3.x traditional):
curl -X POST http://localhost:8001/routes \
  -d "name=order-regex-route" \
  -d "service=order-service" \
  -d 'paths[]=~^/v1/orders/([a-f0-9-]+)$' \
  -d "regex_priority=10"

# Multiple match criteria (AND):
# Route matches when: hosts matches AND paths matches AND methods matches AND headers matches

# Wildcard host:
curl -X POST http://localhost:8001/routes \
  -d "name=admin-wildcard" \
  -d "service=admin-service" \
  -d 'hosts[]=*.admin.example.com' \
  -d "paths[]=/admin"
```

---

### A.3 Consumer Entity

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | string | yes* | — | Unique string identifier (alternative to custom_id) |
| `custom_id` | string | no | — | External ID (e.g. OAuth subject, database ID) |
| `tags` | array | no | — | Meta tags |

*\*Either `username` or `custom_id` required.*

**Credential types** (nested under Consumer):

| Credential | Endpoint | Key Fields |
|---|---|---|
| key-auth | `POST /consumers/{name}/key-auth` | `key` |
| jwt | `POST /consumers/{name}/jwt` | `algorithm`, `rsa_public_key` / `secret` |
| basic-auth | `POST /consumers/{name}/basicauth-credentials` | `username`, `password` |
| oauth2 | `POST /consumers/{name}/oauth2` | `name`, `client_id`, `client_secret`, `redirect_uris` |
| hmac-auth | `POST /consumers/{name}/hmac-auth` | `username`, `secret` |
| mtls-auth | `POST /consumers/{name}/mtls-auth` | `subject_name`, `ca_certificate` |

```bash
# JWT credential
curl -X POST http://localhost:8001/consumers/john/jwt \
  -d "algorithm=RS256" \
  -d "rsa_public_key=-----BEGIN PUBLIC KEY-----..." \
  -d "key=john-kid-001"

# OAuth2 credential
curl -X POST http://localhost:8001/consumers/mobile-app/oauth2 \
  -d "name=mobile-app-oauth" \
  -d "client_id=app_123" \
  -d "client_secret=secret_xyz" \
  -d 'redirect_uris[]=https://app.example.com/callback'
```

---

### A.4 Plugin Entity

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | yes | — | Plugin name from Kong Hub |
| `enabled` | boolean | no | `true` | Toggle plugin on/off |
| `config` | object | no | `{}` | Plugin-specific configuration (deep dive on Kong Hub) |
| `protocols` | array | no | all | Protocols plugin supports; e.g. `["http","https"]` |
| `service` | string | no | — | Service `id` or `name` to scope plugin |
| `route` | string | no | — | Route `id` or `name` to scope plugin |
| `consumer` | string | no | — | Consumer `id` or `username` to scope plugin |
| `consumer_group` | string | no | — | Consumer Group `id` or `name` (Enterprise) |
| `tags` | array | no | — | Meta tags |
| `run_on` | string | no | `"first"` | `"first"` (data plane) or `"second"` (control plane) |

```bash
# Service-level plugin
curl -X POST http://localhost:8001/services/order-service/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=500" \
  -d "config.policy=local"

# Route-level plugin
curl -X POST http://localhost:8001/routes/payment-route/plugins \
  -d "name=key-auth" \
  -d "config.key_names=apikey" \
  -d "config.anonymous=anonymous" \
  -d "config.hide_credentials=true"

# Consumer-level plugin
curl -X POST http://localhost:8001/consumers/mobile-app/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=10000" \
  -d "config.policy=redis" \
  -d "config.redis_host=redis" \
  -d "config.redis_port=6379"

# Global plugin (no service/route/consumer)
curl -X POST http://localhost:8001/plugins \
  -d "name=cors" \
  -d "config.origins=*" \
  -d "config.methods=GET,POST,PUT,DELETE" \
  -d "config.headers=X-API-Key"
```

---

### A.5 Upstream & Target Entities (Day 13 preview)

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Upstream virtual LB name |
| `slots` | integer | no (10) | Load balancing slots (10-65536) |
| `algorithm` | string | no (roundrobin) | `roundrobin`, `consistent-hashing`, `least-connections`, `latency-exponential`, `latency-weighted`, `ip-hash` |
| `healthchecks.active.*` | object | no | Active health check config |
| `healthchecks.passive.*` | object | no | Passive health check config |

| Field | Type | Required | Description |
|---|---|---|---|
| `target` | string | yes | `host:port` or `ip:port` |
| `weight` | integer | no (100) | Load weight (0-1000); 0 = disabled |
| `upstream` | string | yes | Upstream `id` or `name` |

---

### A.6 Certificate & SNI Entities

| Entity | Field | Type | Description |
|---|---|---|---|
| Certificate | `cert` | string | PEM certificate (multi-line string hoặc `\n`) |
| Certificate | `key` | string | PEM private key |
| Certificate | `cert_alt` | string | Alternative certificate (e.g. EC) |
| Certificate | `key_alt` | string | Alternative key |
| Certificate | `tags` | array | Meta tags |
| SNI | `name` | string | SNI hostname |
| SNI | `certificate` | string | Certificate `id` |
| CA Certificate | `cert` | string | CA PEM certificate |

```bash
# Tạo certificate + SNI
curl -X POST http://localhost:8001/certificates \
  -d "cert=$(cat server.pem)" \
  -d "key=$(cat server.key)" \
  -d "snis[]=api.example.com"

# SNI entity riêng (khi 1 cert cho nhiều SNI)
curl -X POST http://localhost:8001/snis \
  -d "name=api.example.com" \
  -d "certificate=$(curl -s http://localhost:8001/certificates | jq -r '.data[0].id')"
```

---

## B. path_handling v0 vs v1 — Deep Dive

### B.1 Concatenation Algorithm

**Kong 3.x default**: `path_handling = "v0"`

Khi request match route, Kong tính toán upstream request path theo 2 strategy:

```
Request URL:  http://kong:8000/v1/orders/123

Service:     path="/api"
Route:       paths=["/v1/orders"], strip_path=true, path_handling=v0

─────────────────────────────────────────────────
Step 1:  Strip
  matched_prefix = "/v1/orders"
  remaining_path = "/123"

Step 2:  Concat (v0)
  upstream_path = service.path + remaining_path
               = "/api" + "/123"
               = "/api/123"

Step 3:  Proxy to upstream
  GET /api/123 HTTP/1.1
  Host: order-backend:8080
─────────────────────────────────────────────────
```

### B.2 All 12 Combinations

Với 4 biến: `service.path` (A/B), `route.paths` (C/D), `strip_path` (true/false), `path_handling` (v0/v1)

**Scenario**: Request `/v1/orders/urgent`

| # | service.path | route.paths | strip_path | path_handling | upstream_path | Notes |
|---|---|---|---|---|---|---|
| 1 | `/api` | `/v1/orders` | `true` | `v0` | `/api/urgent` | Default — stripped prefix gone |
| 2 | `/api` | `/v1/orders` | `false` | `v0` | `/api/v1/orders/urgent` | Full path forwarded |
| 3 | `/api` | `/v1/orders` | `true` | `v1` | `/api/v1/orders/urgent` | v1 re-adds prefix before concat |
| 4 | `/api` | `/v1/orders` | `false` | `v1` | `/api/v1/orders/urgent` | v1 = v0 when strip_path=false |
| 5 | `/` | `/v1/orders` | `true` | `v0` | `/urgent` | Root service path |
| 6 | `/` | `/v1/orders` | `false` | `v0` | `/v1/orders/urgent` | Prefix forwarded |
| 7 | `/` | `/v1/orders` | `true` | `v1` | `/v1/orders/urgent` | v1 re-adds prefix |
| 8 | null | `/v1/orders` | `true` | `v0` | `/urgent` | No service path |
| 9 | null | `/v1/orders` | `false` | `v0` | `/v1/orders/urgent` | Full forwarded |
| 10 | `/v2` | `/v1/orders` | `true` | `v0` | `/v2/urgent` | Path version mismatch |
| 11 | `/v2` | `/v1/orders` | `false` | `v0` | `/v2/v1/orders/urgent` | Double prefix (anti-pattern) |
| 12 | `/v2` | `/v1/orders` | `true` | `v1` | `/v2/v1/orders/urgent` | v1 double prefix |

### B.3 v0 vs v1 Summary

| Aspect | `path_handling=v0` | `path_handling=v1` |
|---|---|---|
| Stripped prefix | **Không** re-add vào upstream path | Re-add vào upstream path |
| Upstream path (strip=true) | `service.path + remaining_path` | `service.path + route.path + remaining_path` |
| Upstream path (strip=false) | Same as v0 | Same as v0 |
| Kong 3.x default | `v0` | — |
| When to use | Path versioning via service.path, strip prefix cleanly | When upstream needs full route path (legacy backends) |

**Common mistakes**:
- Service path = `/api`, Route path = `/v1/orders`, strip=true, v0 → upstream nhận `/api/urgent` nhưng upstream mong đợi `/v1/orders/urgent` → 404 upstream-side
- Fix: dùng `path_handling=v1` HOẶC đổi service.path = `/v1` HOẶC strip_path=false

---

## C. Expressions Router DSL (Kong 3.x)

### C.1 Grammar

```
expression     ::= expr
expr           ::= disjunction
disjunction    ::= conjunction ( "||" conjunction )*
conjunction    ::= term ( "&&" term )*
term           ::= negation | primary
negation       ::= "!" term
primary        ::= "(" expr ")" | condition | function

condition      ::= http_field operator value
operator       ::= "==" | "!=" | "^=" | "$=" | "~=" | "in"

http_field     ::= "http." field
field          ::= "host" | "method" | "path" | "scheme" |
                   "latency" | "size" | "headers." header_name |
                   "uri" | "querystring" | "version"

value          ::= string | number | boolean | null |
                   [ string_list ] | { "not": string_list }

string_list    ::= "\"" "\"" | "\"" string ( "," string )* "\""
```

### C.2 Operator Reference

| Operator | Name | Example | Matches |
|---|---|---|---|
| `==` | Equals | `http.host == "api.example.com"` | Exact match |
| `!=` | Not equals | `http.host != "internal.example.com"` | Not this host |
| `^=` | Starts with (prefix) | `http.path ^= "/v1/"` | Path prefix |
| `$=` | Ends with (suffix) | `http.path $= ".json"` | File extension |
| `~=` | Regex | `http.path ~= "^/v1/orders/\\d+$"` | Regex pattern |
| `in` | In set | `http.method in ["POST", "PUT"]` | Method in list |

### C.3 Examples

```yaml
# 1. Basic: path prefix match
http.path ^= "/v1/orders"

# 2. AND: path + method
http.path ^= "/v1/orders" && http.method == "POST"

# 3. OR: multiple paths
(http.path ^= "/v1/orders" || http.path ^= "/v2/orders")

# 4. Header match
http.headers.X-API-Tier in ["premium", "enterprise"]

# 5. Negative match
!(http.host == "internal.example.com")

# 6. Complex: production scenario
(
  (http.host == "api.example.com" && http.path ^= "/v1/payments")
  && http.method == "POST"
  && !(http.headers.X-Internal == "true")
)

# 7. Regex (expensive, use only when needed)
http.path ~= "^/v1/orders/([a-f0-9-]{36})$"

# 8. Version routing
http.path ^= "/v1/"   → route: v1-service
http.path ^= "/v2/"   → route: v2-service
```

### C.4 Enable Expressions Router

```bash
# Via environment variable
KONG_ROUTER_FLAVOR=expressions

# Via docker-compose.yml
environment:
  KONG_ROUTER_FLAVOR: "expressions"
```

### C.5 Traditional vs Expressions Router

| Aspect | Traditional | Expressions |
|---|---|---|
| **Matching logic** | Priority-based (longest match, regex_priority) | Boolean DSL evaluation |
| **Configuration** | Individual fields (hosts, paths, methods, headers) | Single `expression` field on Route |
| **Complexity** | Low | Medium-High |
| **Debugging** | `curl "http://localhost:8001/routes?paths=..."` | `curl http://localhost:8001/routes/expressions` |
| **Scale** | ~1000 routes OK, >10k slows | Better at high scale |
| **Feature parity** | Most features | All features + more flexibility |
| **Syntax** | Admin API fields | DSL string in `expression` field |
| **Kong version** | All versions | Kong 3.x+ |

```bash
# Route với Expressions (thay thế hosts/paths/methods/headers)
curl -X POST http://localhost:8001/services/order-service/routes \
  -d "name=order-expr-route" \
  -d 'expression=http.path ^= "/v1/orders" && http.method in ["GET", "POST"]' \
  -d "strip_path=true"
```

---

## D. Plugin Precedence Matrix

### D.1 Scope Combination → Config Applied

| Priority | Scopes Matched | Config Source | Override Behavior |
|---|---|---|---|
| 1 (highest) | Consumer + Route + Service | Consumer | Consumer config wins completely |
| 2 | Consumer + Route | Consumer | Consumer config wins completely |
| 3 | Consumer + Service | Consumer | Consumer config wins completely |
| 4 | Route + Service | Route | Route config merges with service |
| 5 | Consumer only | Consumer | Consumer config only |
| 6 | Route only | Route | Route config only |
| 7 | Service only | Service | Service config only |
| 8 (lowest) | None (global) | Global | Global config |

### D.2 Precedence Override Rules

**Key rule**: Consumer-level config **always wins** over Route/Service/Global, regardless of how many scopes match.

**Merge behavior** (Route + Service):
- Non-conflicting fields: merged
- Conflicting fields: Route-level wins

```json
{
  "rate-limiting": {
    "service":  { "config": { "minute": 500, "hour": 10000 } },
    "route":    { "config": { "minute": 100 } },
    "result":   { "minute": 100, "hour": 10000 }
  }
}
```

### D.3 Multiple Plugins of Same Name

```
Không thể có 2 plugin instance cùng tên ở cùng scope.
→ Error: "plugin already exists on this route"
→ Fix: dùng unique name field hoặc xóa plugin cũ trước
```

```bash
# Xóa plugin cũ
curl -X DELETE http://localhost:8001/routes/order-route/plugins/{plugin-id}

# Hoặc update plugin thay vì tạo mới
curl -X PATCH http://localhost:8001/routes/order-route/plugins/{plugin-id} \
  -d "config.minute=200"
```

### D.4 Plugin Execution Order (by phase)

```
balancer      → target selection (Upstream)
access        → auth, rate-limit, ACL, IP restriction
authenticate  → resolve consumer credential
prefunction   → custom Lua
router        → after router
hipatterns    → header/body pattern match
preproxy      → before proxy
postproxy     → after proxy (never blocks)
header_filter → transform response headers
postfunction  → custom Lua
body_filter   → transform response body
filter       → deprecated
log          → logging, metrics
```

---

## E. kong.yml Schema Reference (Kong 3.0)

### E.1 Top-level Structure

```yaml
_format_version: "3.0"        # REQUIRED — Kong 3.x format
_transform: true              # Enable credential transformation

# Entity arrays (optional, include only what you need)
services:        []           # Service entities
routes:          []           # Standalone Route entities (not nested)
plugins:         []           # Global plugins OR scoped plugins
consumers:       []           # Consumer entities
upstreams:       []           # Upstream entities
certificates:    []           # TLS certificates
snis:            []           # SNI entities
ca_certificates: []           # CA certificate entities
vaults:          []           # Secret vault references
```

### E.2 Service + Nested Routes + Nested Plugins

```yaml
services:
  - name: order-service
    url: http://order-upstream/api
    # Nested routes
    routes:
      - name: order-route-v1
        paths: ["/v1/orders"]
        strip_path: true
        path_handling: v0
        methods: ["GET", "POST"]
        tags: ["team-orders"]
      - name: order-route-v2
        paths: ["/v2/orders"]
        strip_path: true
        tags: ["team-orders"]
    # Nested plugins (scoped to this service only)
    plugins:
      - name: rate-limiting
        config:
          minute: 500
          policy: local
          fault_tolerant: true
    # Service-level config
    retries: 3
    connect_timeout: 5000
    read_timeout: 30000
    write_timeout: 30000
    tags: ["team-orders", "env-staging"]
```

### E.3 Consumer + Nested Credentials + Nested Plugins

```yaml
consumers:
  - username: mobile-app
    custom_id: app-ios-2.1.0
    tags: ["team-mobile"]

    # Nested credentials (auto-create)
    keyauth_credentials:
      - key: "${KEY_MOBILE_APP}"   # env var reference (Kong 3.x)

    # Nested plugin (consumer-scoped)
    plugins:
      - name: rate-limiting
        config:
          minute: 10000
          policy: redis
          redis_host: redis
          redis_port: 6379

  - username: admin-team
    tags: ["team-admin"]
    plugins:
      - name: acl
        config:
          allow: ["admin-team"]
      - name: rate-limiting
        config:
          minute: 1000
```

### E.4 Standalone Route (not nested)

```yaml
routes:
  - name: admin-route
    service: admin-service        # references service by name
    protocols: ["http", "https"]
    hosts: ["admin.example.com"]
    paths: ["/admin"]
    strip_path: true
    preserve_host: true
    regex_priority: 10
    tags: ["team-admin"]
```

### E.5 Upstream + Nested Targets

```yaml
upstreams:
  - name: order-upstream
    algorithm: roundrobin
    healthchecks:
      active:
        healthy:
          interval: 5
          successes: 2
        unhealthy:
          interval: 5
          http_failures: 3
        http_path: /health
        timeout: 5
      passive:
        healthy:
          successes: 3
        unhealthy:
          http_failures: 3
          tcp_failures: 3
    targets:
      - target: order-svc-1:8080
        weight: 100
      - target: order-svc-2:8080
        weight: 100
```

### E.6 Global Plugin (top-level)

```yaml
plugins:
  - name: cors
    config:
      origins: ["*"]
      methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
      headers: ["Accept", "Authorization", "Content-Type", "X-API-Key"]
      exposed_headers: ["X-RateLimit-Limit", "X-RateLimit-Remaining"]
      credentials: true
      max_age: 3600
      preflight_continue: false
```

---

## F. Admin API Quick Reference

Các CRUD endpoint dưới đây áp dụng cho DB-mode hoặc Hybrid Control Plane. Trong DB-less mode, Admin API entity CRUD là read-only; dùng `POST /config` để replace declarative config.

### F.1 CRUD Endpoints

```bash
# ── SERVICES ──────────────────────────────────────────────────
POST   /services                         # Create
GET    /services                         # List (size=10, offset=...)
GET    /services/{id_or_name}            # Read
PATCH  /services/{id_or_name}             # Partial update
PUT    /services/{id_or_name}             # Upsert (replace)
DELETE /services/{id_or_name}            # Delete

# ── ROUTES ────────────────────────────────────────────────────
POST   /services/{name}/routes            # Create nested under service
POST   /routes                            # Create standalone
GET    /routes                            # List
GET    /routes/{id_or_name}               # Read
PATCH  /routes/{id_or_name}               # Partial update
DELETE /routes/{id_or_name}               # Delete

# ── CONSUMERS ─────────────────────────────────────────────────
POST   /consumers                         # Create
GET    /consumers                         # List
GET    /consumers/{username_or_id}        # Read
PATCH  /consumers/{username_or_id}        # Update
DELETE /consumers/{username_or_id}        # Delete

# ── CREDENTIALS ───────────────────────────────────────────────
POST   /consumers/{name}/key-auth
POST   /consumers/{name}/jwt
POST   /consumers/{name}/basicauth-credentials
POST   /consumers/{name}/oauth2
POST   /consumers/{name}/hmac-auth
DELETE /consumers/{name}/key-auth/{id}

# ── PLUGINS ───────────────────────────────────────────────────
POST   /plugins                            # Create (any scope)
GET    /plugins                            # List global + scoped
GET    /plugins/{id}                       # Read
PATCH  /plugins/{id}                       # Update
DELETE /plugins/{id}                       # Delete
POST   /services/{name}/plugins            # Nested: service-scoped
POST   /routes/{name}/plugins              # Nested: route-scoped
POST   /consumers/{name}/plugins           # Nested: consumer-scoped

# ── UPSTREAM ──────────────────────────────────────────────────
POST   /upstreams
GET    /upstreams
GET    /upstreams/{name}
PATCH  /upstreams/{name}
DELETE /upstreams/{name}
POST   /upstreams/{name}/targets
GET    /upstreams/{name}/targets

# ── CONFIG (DB-less) ───────────────────────────────────────────
GET    /config                             # Dump current config
POST   /config                             # Reload declarative config (kong.yml)
```

### F.2 Query Parameters

```bash
# Pagination
GET /services?size=10&offset=abc123

# Filter by tag
GET /services?tags=team-orders

# Filter by name
GET /services?name=order-service

# Filter by multiple tags (AND)
GET /routes?tags=team-orders&tags=env-staging

# Filter by protocol
GET /routes?protocols=http

# Only enabled plugins
GET /plugins?enabled=true
```

### F.3 Response Format

```json
{
  "next": "http://localhost:8001/services?size=10&offset=xyz789",
  "data": [
    {
      "id": "a1b2c3d4-...",
      "name": "order-service",
      "protocol": "http",
      "host": "order-backend",
      "port": 8080,
      "path": "/api",
      "retries": 3,
      "connect_timeout": 5000,
      "read_timeout": 30000,
      "write_timeout": 30000,
      "created_at": 1715000000,
      "updated_at": 1715000000,
      "tags": ["team-orders"]
    }
  ]
}
```

---

## G. Entity Relationship Diagram

```mermaid
erDiagram
    SERVICE {
        string id PK
        string name UK
        string protocol
        string host
        int port
        string path
        int retries
        int connect_timeout
        int read_timeout
        int write_timeout
    }

    ROUTE {
        string id PK
        string name UK
        string service FK
        array protocols
        array methods
        array hosts
        array paths
        object headers
        int regex_priority
        bool strip_path
        bool preserve_host
        string path_handling
    }

    CONSUMER {
        string id PK
        string username UK
        string custom_id UK
    }

    PLUGIN {
        string id PK
        string name
        bool enabled
        object config
        string service FK nullable
        string route FK nullable
        string consumer FK nullable
    }

    CREDENTIAL {
        string id PK
        string consumer FK
        string type
    }

    UPSTREAM {
        string id PK
        string name UK
        string algorithm
    }

    TARGET {
        string id PK
        string upstream FK
        string target
        int weight
    }

    SERVICE ||--o{ ROUTE : "1 : N"
    SERVICE ||--o{ PLUGIN : "1 : N"
    ROUTE ||--o{ PLUGIN : "1 : N"
    CONSUMER ||--o{ PLUGIN : "1 : N"
    CONSUMER ||--o{ CREDENTIAL : "1 : N"
    SERVICE }o--o| UPSTREAM : "host points to"
    UPSTREAM ||--o{ TARGET : "1 : N"
```

---

## H. Quick Cheat Sheet

```bash
# 1. Tạo service nhanh (URL shorthand)
curl -X POST http://localhost:8001/services -d name=api -d url=http://backend:8080/api

# 2. Tạo route nhanh (nested)
curl -X POST http://localhost:8001/services/api/routes -d "paths[]=/v1" -d "strip_path=true"

# 3. Tạo consumer + key nhanh
curl -X POST http://localhost:8001/consumers -d username=app
curl -X POST http://localhost:8001/consumers/app/key-auth -d key=secret123

# 4. Bật plugin route-level
curl -X POST http://localhost:8001/routes/route-name/plugins -d name=key-auth -d "config.anonymous="

# 5. Xem route match
curl "http://localhost:8001/routes?paths=/v1/orders"

# 6. Xem plugin config
curl http://localhost:8001/plugins | jq '.data[] | {name, route, service, consumer, enabled}'

# 7. Dump declarative config (DB-less only)
curl http://localhost:8001/config | jq

# 8. Reload DB-less config (DB-less only)
curl -X POST http://localhost:8001/config -F config=@kong.yml

# 9. Health check
curl http://localhost:8001/status | jq '.database.connected'

# 10. Verify routing
curl -v http://localhost:8000/v1/orders/123 2>&1 | grep "< HTTP"
```
