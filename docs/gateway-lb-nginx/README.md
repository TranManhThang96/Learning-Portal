# API Gateway, Load Balancer, Nginx & Kong — Khóa học 21 ngày

> Lộ trình thực chiến dành cho Senior Software Engineer muốn hiểu sâu cách thiết kế, triển khai, vận hành và tối ưu tầng traffic trong hệ thống microservices production-scale.

---

## 🎯 Mục tiêu khóa học

Sau 21 ngày, học viên có thể:

- Thiết kế traffic flow cho hệ thống microservices production
- Dùng Nginx làm reverse proxy / load balancer đúng cách
- Tune Nginx cho traffic cao, debug 502/503/504
- Bảo vệ edge bằng rate limiting / connection limiting / geo whitelist
- Benchmark Nginx bằng wrk/hey/h2load và viết benchmark report chuẩn
- Dùng Kong Gateway cho routing, auth, rate limit, upstream
- Quản lý Kong config bằng declarative config / decK theo GitOps
- Thiết kế timeout/retry strategy hợp lý, tránh retry storm
- Triển khai canary / blue-green ở Gateway layer
- Tích hợp service discovery cơ bản với Consul
- Setup metrics/logging cho Nginx & Kong
- Đưa ra trade-off giữa Nginx, HAProxy, Envoy và Kong

---

## 👤 Đối tượng

- **Level**: Senior Software Engineer
- **Background**: backend tốt, system design, DB optimization, cơ bản về microservices, Redis, Kafka, ELK
- **Thời lượng**: 2 giờ/ngày × 21 ngày

---

## 📚 Cấu trúc khóa học

Mỗi ngày là một folder riêng theo format `day-XX-<topic>/`, gồm:

- `lesson.md` — bài học chính (bắt buộc)
- `document.md` — deep dive, reference (khi cần)
- `exercises.md` — hands-on lab, challenges (khi cần)

---

## 🗓️ Lộ trình 21 ngày

### Tuần 1 — Nginx & Load Balancing Foundation

| Day | Topic | Folder | Trạng thái |
|---:|---|---|---|
| 1 | Reverse Proxy & Traffic Flow Foundation | [`day-01-reverse-proxy-traffic-flow/`](./day-01-reverse-proxy-traffic-flow/) | ✅ Đã tạo |
| 2 | Nginx Architecture: Master/Worker, Event Loop, Connection Lifecycle | [`day-02-nginx-architecture/`](./day-02-nginx-architecture/) | ✅ Đã tạo |
| 3 | Load Balancing Algorithms | [`day-03-load-balancing-algorithms/`](./day-03-load-balancing-algorithms/) | ✅ Đã tạo |
| 4 | Health Check, Failover & Upstream Failure | [`day-04-health-check-failover/`](./day-04-health-check-failover/) | ✅ Đã tạo |
| 5 | TLS Termination, HTTP/2 & Secure Edge | [`day-05-tls-http2-secure-edge/`](./day-05-tls-http2-secure-edge/) | ✅ Đã tạo |
| 6 | Rate Limiting, Connection Limiting & Basic Protection | [`day-06-rate-limiting/`](./day-06-rate-limiting/) | ✅ Đã tạo |
| 7 | Nginx Performance Tuning & Benchmark | [`day-07-nginx-performance/`](./day-07-nginx-performance/) | ✅ Đã tạo |

### Tuần 2 — Kong Gateway Core & Traffic Management

| Day | Topic | Folder | Trạng thái |
|---:|---|---|---|
| 8 | Kong Architecture & OpenResty Foundation | [`day-08-kong-architecture/`](./day-08-kong-architecture/) | ✅ Đã tạo |
| 9 | Kong Core Entities: Services, Routes, Consumers, Plugins | [`day-09-kong-core-entities/`](./day-09-kong-core-entities/) | ✅ Đã tạo |
| 10 | DB-less vs DB-mode & decK Workflow | [`day-10-kong-dbless-deck/`](./day-10-kong-dbless-deck/) | ✅ Đã tạo |
| 11 | Authentication: Key Auth, JWT, mTLS Overview | [`day-11-kong-authentication/`](./day-11-kong-authentication/) | ✅ Đã tạo |
| 12 | Rate Limiting, ACL, IP Restriction & Request Control | [`day-12-kong-traffic-control/`](./day-12-kong-traffic-control/) | ✅ Đã tạo |
| 13 | Kong Upstream Load Balancing & Health Checks | [`day-13-kong-upstream/`](./day-13-kong-upstream/) | ✅ Đã tạo |
| 14 | Timeout, Retry, Circuit Breaker & Backpressure | [`day-14-kong-resilience/`](./day-14-kong-resilience/) | ✅ Đã tạo |
| 15 | Canary, Blue-Green & Gateway Config Rollback | [`day-15-kong-rollout/`](./day-15-kong-rollout/) | ✅ Đã tạo |

### Tuần 3 — Observability, Service Discovery & Production Readiness

| Day | Topic | Folder | Trạng thái |
|---:|---|---|---|
| 16 | Observability for Nginx & Kong | [`day-16-observability-nginx-kong/`](./day-16-observability-nginx-kong/) | ✅ Đã tạo |
| 17 | Consul Service Discovery Essentials | [`day-17-consul-service-discovery/`](./day-17-consul-service-discovery/) | ✅ Đã tạo |
| 18 | Integrating Nginx/Kong with Service Discovery | [`day-18-nginx-kong-service-discovery/`](./day-18-nginx-kong-service-discovery/) | ✅ Đã tạo |
| 19 | Production Security Hardening | [`day-19-production-security-hardening/`](./day-19-production-security-hardening/) | ✅ Đã tạo |
| 20 | Capstone Project: End-to-End Gateway System | [`day-20-capstone-gateway-system/`](./day-20-capstone-gateway-system/) | ✅ Đã tạo |
| 21 | Failure Testing, Benchmark Report & Final Review | [`day-21-failure-testing-final-review/`](./day-21-failure-testing-final-review/) | ✅ Đã tạo |

---

## 📖 Tóm tắt 21 ngày đã hoàn thành

### Tuần 1 — Nginx & Load Balancing Foundation

#### Day 1 — Reverse Proxy & Traffic Flow Foundation
Phân biệt rõ reverse proxy / forward proxy / load balancer, hiểu vì sao không expose service trực tiếp ra Internet và vì sao Load Balancer nên đứng trước API Gateway. Hands-on dựng Nginx reverse proxy + 2 backend services (order-service, payment-service) bằng Docker Compose, troubleshoot 502 cơ bản, trade-offs Nginx/HAProxy/Envoy/Kong/Traefik.

#### Day 2 — Nginx Architecture: Master/Worker, Event Loop, Connection Lifecycle
Đi sâu mô hình master/worker process, event-driven non-blocking I/O với epoll, connection lifecycle từ accept đến keepalive/close, cách tính `max_clients = worker_processes × worker_connections / 2`. Hands-on inspect process bằng `ps`/`pstree`, observe zero-downtime reload, stress test worker_connections exhausted, tune `worker_processes auto` vs fixed, đo ảnh hưởng upstream keepalive on/off.

#### Day 3 — Load Balancing Algorithms
Configure round-robin, least_conn, ip_hash, hash consistent, weighted upstream, random với two-choices. Hiểu Smooth Weighted Round-Robin, Consistent Hashing (Ketama), Power-of-Two Choices. Trade-offs theo các chiều latency-sensitive / stateful / cache-friendly, anti-patterns (ip_hash với mobile/NAT, weighted không có health check). Lab Docker Compose 1 Nginx + 4 backend, đo phân phối request và failover.

#### Day 4 — Health Check, Failover & Upstream Failure
Cơ chế passive health check của Nginx OSS (`max_fails`/`fail_timeout`), phân biệt nguyên nhân chính xác của 502 (connection refused/reset), 503 (no upstream available) và 504 (upstream timeout). Cấu hình `proxy_next_upstream`, `proxy_next_upstream_tries`, `proxy_next_upstream_timeout`, nguyên tắc Timeout Budget (client > edge > gateway > upstream > DB), cảnh báo retry storm. Hands-on 6 failure scenarios chạy được với Docker.

#### Day 5 — TLS Termination, HTTP/2 & Secure Edge
TLS termination models (edge / end-to-end / mTLS), TLS 1.2 vs TLS 1.3 handshake (1-RTT, 0-RTT), cipher suite recommendation theo Mozilla SSL config generator, session resumption (cache vs ticket), OCSP stapling, HSTS, ALPN negotiation, HTTP/2 multiplexing / binary framing / HPACK. Hands-on generate cert bằng `openssl` và `mkcert`, test bằng `openssl s_client` và `curl --http2 -v`, benchmark HTTP/1.1 vs HTTP/2 bằng `h2load`, mô phỏng cert expired.

#### Day 6 — Rate Limiting, Connection Limiting & Basic Protection
`limit_req_zone` + `limit_req` (leaky bucket), `limit_conn_zone` + `limit_conn`, ý nghĩa của `burst` / `nodelay` / `delay=N`, key selection (`$binary_remote_addr` vs `$http_x_api_key`), cách lấy IP thật khi đứng sau Cloud LB/CDN bằng `set_real_ip_from` + `real_ip_header`, geo whitelist, bandwidth throttling. Lý do Nginx OSS không có distributed rate limit (lý do Kong tốt hơn cho enterprise). Hands-on 7 lab: Black Friday burst, brute-force protection với `Retry-After`, slowloris simulation, X-Forwarded-For spoofing, wrk load test phân tích tỉ lệ 200/429.

#### Day 7 — Nginx Performance Tuning & Benchmark
Tổng kết tuần 1. Tuning toàn diện ở 2 tầng: Nginx (`worker_processes auto`, `worker_cpu_affinity`, `worker_connections`, `multi_accept`, `reuseport`, upstream `keepalive`, `proxy_buffering`, `gzip`, `open_file_cache`, `access_log buffer/flush`) và OS (`ulimit -n`, `somaxconn`, `tcp_max_syn_backlog`, `ip_local_port_range`, `tcp_tw_reuse`). Benchmark methodology chuẩn: tools (wrk/hey/vegeta/k6/h2load/ab), coordinated omission problem, vì sao mean latency tệ, p50/p95/p99/p999, capacity planning theo công thức `RPS = (cores × clock × eff) / cycles_per_req`. Hands-on 10 exercise iterative tuning + capacity planning challenge.

### Tuần 2 — Kong Gateway Core & Traffic Management

#### Day 8 — Kong Architecture & OpenResty Foundation
Kong = Nginx + LuaJIT + nhiều `lua-resty-*` module (OpenResty). Nginx request lifecycle phases (rewrite / access / content / header_filter / body_filter / log) và Lua hooks tương ứng. Kiến trúc Kong: Data Plane vs Control Plane, ports 8000/8443/8001/8444/8100/8005, 3 deployment mode (DB-mode / DB-less / Hybrid), plugin priority list (key-auth 1003, jwt 1005, rate-limiting 910, prometheus 13...), shared dict / cosocket / coroutine. So sánh Nginx vs Kong: config, plugin, auth, rate limit, routing, discovery, observability. Hands-on 6 exercise: dựng Kong DB-less Docker Compose, khám phá Admin API, tạo Service/Route qua API và kong.yml, Prometheus plugin, pre-function plugin (custom Lua), convert sang DB-mode Postgres.

#### Day 9 — Kong Core Entities: Services, Routes, Consumers, Plugins
4 entity cốt lõi: Service (upstream backend, có timeout/retry riêng), Route (rule routing thuộc Service, có hosts/paths/methods/headers/snis, regex_priority, strip_path, preserve_host, path_handling v0/v1), Consumer (user/app gọi API + credential), Plugin (middleware có scope global/service/route/consumer với precedence rõ ràng). Admin API CRUD đầy đủ + nested route, kong.yml declarative `_format_version: "3.0"`, traditional router vs expressions router (Kong 3.x). Hands-on 7 exercise: CRUD entity, key-auth + plugin scope, rate-limit precedence 3 scope, lab path_handling 4 tổ hợp, preserve_host on/off, convert sang declarative, optional Expressions Router.

#### Day 10 — DB-less vs DB-mode & decK Workflow
3 deployment mode: DB-mode (Postgres HA, Admin API write trực tiếp), DB-less (kong.yml + `POST /config`, immutable infra), Hybrid (CP có DB + DP pull mTLS qua port 8005, DP có cache fallback khi CP down). decK 1.40+ với subcommand mới `deck gateway <verb>`: ping / dump / lint / validate / diff / sync / reset / render / convert / patch + tag-based partial sync (`--select-tag team-a`). GitOps pipeline mẫu với GitHub Actions: lint → validate (staging) → diff (production) → sync → tag commit. Rollback strategies: dump trước khi sync, git revert + sync, blue-green declarative cluster. Hands-on 7 lab: bootstrap decK, sync workflow, file splitting + render, partial sync theo tag, rollback drill, DB-mode comparison, optional Hybrid mode với cluster cert.

#### Day 11 — Authentication: Key Auth, JWT, mTLS Overview
Authentication vs Authorization, 3 model auth: shared secret (key-auth, basic-auth, hmac-auth), token-based (JWT, OAuth2 delegate), certificate-based (mTLS). Kong consumer model + bảng credential riêng cho từng plugin (`keyauth_credentials`, `jwt_secrets`, `basicauth_credentials`, `mtls_auth_credentials`). Plugin priority: jwt=1005 chạy TRƯỚC key-auth=1003 (số cao priority cao), mtls-auth=1600 chạy ở certificate phase (trước access). JWT internals: header/payload/signature, claims `iss/aud/exp/nbf/iat/jti`, HS256 vs RS256 (RSA verify đắt hơn nhưng key rotation an toàn), JWKS endpoint cho public key, `anonymous consumer` pattern để chain nhiều auth fallback. mTLS overview: TLS handshake với client cert + CA chain verify + match cert subject/SAN. Hands-on 7 lab DB-less: key-auth bật/tắt, JWT HS256, JWT RS256 với RSA key pair, multiple-auth + anonymous, mTLS với CA + client cert, auth + rate-limit per consumer, troubleshooting 401/403. Anti-pattern: key trong query string, basic auth không TLS, JWT `alg: none`, mTLS không monitor cert expiry.

#### Day 12 — Rate Limiting, ACL, IP Restriction & Request Control
4 nhóm plugin: rate limiting & quota (`rate-limiting`, `response-ratelimiting`), access control (`acl`, `ip-restriction`, `bot-detection`), request mutation (`request-transformer`, `response-transformer`, `correlation-id`, `request-termination`), size validation (`request-size-limiting`). 3 policy rate-limit: `local` (mỗi node tự đếm — kém chính xác multi-node), `cluster` (Postgres LISTEN/NOTIFY — DB-mode only, deprecated), `redis` (recommend production, atomic Lua EVAL `INCR + EXPIRE`). Fixed window (OSS) vs sliding window log/counter (rate-limiting-advanced enterprise) — fixed window có "burst boundary" issue. Plugin scope precedence chi tiết: consumer + route + service > consumer + route > consumer + service > consumer > route + service > route > service > global. ACL = group-based authorization, IP Restriction CIDR + `trusted_ips` để lấy real client IP sau Cloud LB. Plugin priority: ip-restriction=990, key-auth=1003, acl=950, rate-limiting=910, request-size-limiting=951, request-transformer=801. Hands-on 9 lab Docker Compose Kong + Redis + 2 backend: 3 tier consumer (free/pro/enterprise), ACL group, IP whitelist CIDR, request-transformer inject metadata, request-termination maintenance mode, Redis fail-open vs fail-close, benchmark `local` vs `redis`, Prometheus metrics 429. Anti-pattern: rate-limit theo IP cho mobile (CGNAT), policy `local` ở 10 node (true rate × 10).

#### Day 13 — Kong Upstream Load Balancing & Health Checks
Upstream entity (logic name + algorithm + healthcheck + ring balancer 10000 slot) vs Service entity (`Service.host` có thể trỏ tới Upstream name). Target = backend instance (host:port + weight), **immutable** — phải tạo target mới với cùng host:port để update. 5 algorithm: `round-robin` (default), `consistent-hashing` (hash on consumer/ip/header/cookie/path/query_arg + `hash_fallback`), `least-connections`, `latency` (EWMA), `none`. **Khác biệt cốt lõi với Nginx OSS**: Kong có **active health check** (chủ động `GET /healthz` interval 5–10s, đếm `successes`/`http_failures`/`tcp_failures`/`timeouts` → toggle healthy/unhealthy theo `threshold`) — Nginx OSS chỉ có passive. Active phát hiện proactive trước khi user thấy lỗi, passive là circuit breaker primitive ở target level. Production: bật cả hai. Ring balancer slot phân bổ theo weight (10000 slot đủ cho weight chênh lệch thông thường, tăng slots khi weight quá lệch). Manual health control: `POST /upstreams/<u>/targets/<host:port>/healthy|unhealthy` cho deploy/maintenance. DNS resolution qua `lua-resty-dns-client` cache theo TTL, hỗ trợ A/AAAA/CNAME/SRV (SRV mở đường cho Consul Day 18). Hands-on 9 lab: 4 backend replicas, distribution test 5 algorithm, active health check `interval/threshold`, weight=0 drain pattern, slow start, force unhealthy, ring balancer variance test, DNS-based discovery với SRV, Prometheus `kong_upstream_target_health`. Anti-pattern: dùng `none` không có DNS discovery, `successes=1`, chỉ active mà không passive.

#### Day 14 — Timeout, Retry, Circuit Breaker & Backpressure
Timeout Budget mathematical model: `T_client > T_edge > T_gateway > T_upstream > T_db` + `T_upstream + T_retry × N ≤ T_gateway`, deadline propagation qua header `X-Request-Deadline`. Retry strategy: chỉ retry idempotent (GET/PUT/DELETE — POST chỉ với Idempotency-Key), retry budget Google SRE ~10% extra request, full jitter / equal jitter / decorrelated jitter (Marc Brooker AWS), không retry trên 4xx (trừ 408, 429 với Retry-After). **Kong retry behavior cốt lõi**: `retries=5` field chỉ retry trên connection error/timeout (next upstream target), KHÔNG retry trên 5xx response từ healthy upstream — khác `proxy_next_upstream` của Nginx. Circuit breaker state machine closed/open/half-open (Hystrix vs Polly vs Sentinel vs Envoy outlier detection); Kong OSS không có circuit breaker per-route — passive health check (Day 13) chính là circuit breaker ở target level, plugin enterprise `circuit-breaker` cho route-level. Backpressure (Little's Law `C = throughput × latency`): worker_connections × keepalive đủ buffer cho 95th percentile, không gateway sẽ sập theo upstream chậm. Trace latency qua `X-Kong-Proxy-Latency` + `X-Kong-Upstream-Latency`. Plugin `proxy-cache` để cache GET giảm load, `request-termination` để shed traffic. Hands-on 8 lab Docker Compose: cấu hình timeout per Service, mô phỏng retry storm (1 backend slow 5s → 6× load), exponential backoff custom Lua, deadline propagation, plugin proxy-cache, Prometheus `kong_latency` + parse access log để đếm retry, circuit breaker overview. Anti-pattern: gateway timeout > client timeout (zombie request), retry POST không idempotency-key, retries=5 với exponential 1+2+4+8+16=31s vượt client timeout.

#### Day 15 — Canary, Blue-Green & Gateway Config Rollback
6 deployment strategy: recreate (downtime), rolling (in-place replace, 2 version chạy song song), canary (split N% v2 tăng dần), blue-green (2 môi trường full song song, switch atomic), shadow/dark launch (mirror traffic v2 không trả response), feature flag at gateway (route theo header/JWT claim/consumer). 3 cách implement Kong canary: route-level header (route v2 với `headers.x-canary: ["true"]` đứng trước route default — internal test), upstream-level (1 Upstream chứa target v1 weight=90 + v2 weight=10, tăng dần — production); plugin `canary-release` enterprise overview. Blue-green Kong: 2 cluster DB-less hoàn toàn độc lập, edge LB switch L7. Ring balancer slot 10000 ÷ weight ratio: weight 90/10 ≈ 9000/1000 slot — không hoàn toàn smooth khi traffic thấp (Day 13 reuse). 4 rollback pattern: dump-before-sync (`deck gateway dump -o snapshot-$(date +%s).yml` rồi `deck sync`), git revert + sync, artifact snapshot, blue-green Kong cluster. RTO target < 5 min với dump-before-sync, RPO = 0 nếu sync atomic. Failure scenario: rollback Gateway xong nhưng app DB schema đã migrate forward (cần "expand-contract" pattern), canary stuck do config sync fail, ring balancer chưa rebuild sau weight update. Hands-on 7 lab: 2 backend v1/v2, route-level header canary, upstream weight progressive 1%→10%→50%→100%, blue-green 2 Kong cluster với Nginx edge switch, dump-before-sync drill, Prometheus PromQL canary monitoring (error rate per-version), feature flag theo JWT claim. Anti-pattern: canary 50% ngay từ bước đầu, không có metric SLO để abort, rollback config nhưng app đã migrate DB không backward-compatible.

### Tuần 3 — Observability, Service Discovery & Production Readiness

#### Day 16 — Observability for Nginx & Kong
Ba trụ cột observability: metrics, logs, traces; trọng tâm production gateway là Prometheus metrics + structured logs, tracing ở mức overview. Nginx dùng `stub_status` + `nginx-prometheus-exporter` để expose active connections, accepts/handled/requests, reading/writing/waiting; Kong dùng plugin `prometheus` với `kong_http_requests_total`, `kong_latency_bucket`, `kong_upstream_latency_bucket`, `kong_kong_latency_bucket`, `kong_upstream_target_health`, shared dict metrics. Bài học phân biệt `kong_latency` / `kong_upstream_latency` / `kong_kong_latency`, thiết kế dashboard theo USE method cho Nginx và RED method cho Kong, viết PromQL `rate`, `histogram_quantile`, `sum by` đúng khi aggregate multi-instance. Logging pipeline: Nginx JSON access log (`log_format json escape=json`) + Kong `file-log`/`http-log` → Promtail/Filebeat → Loki/ELK → Grafana/Kibana. Hands-on dựng Nginx + Kong DB-less + Prometheus + Grafana + Loki/Promtail, generate load bằng `wrk`, simulate backend failure và quan sát metric/log. Anti-pattern: label cardinality bùng nổ, log full request body chứa PII, double-count Prometheus plugin scope.

#### Day 17 — Consul Service Discovery Essentials
Giải quyết vấn đề hardcode IP trong microservices bằng service registry + health check + DNS discovery. Consul architecture gồm server agent (Raft quorum 3/5/7), client agent, gossip protocol, datacenter concept, HTTP API `/v1/agent`, `/v1/catalog`, `/v1/health`, `/v1/kv`. Service registration bằng HTTP API hoặc config file với `id`, `name`, `address`, `port`, `tags`, `meta`, `checks`; health check types gồm HTTP/TCP/TTL/script/gRPC/Docker với `interval`, `timeout`, `deregister_critical_service_after`. Discovery qua REST API `GET /v1/health/service/<name>?passing` và DNS interface `<service>.service.consul`, đặc biệt SRV record mang cả host + port để chuẩn bị cho Kong DNS resolver Day 18. Hands-on dựng Consul server + 2 client + backend services, register order/payment, query bằng API và `dig @localhost -p 8600 order.service.consul SRV`, kill service để quan sát deregister. Anti-pattern: register không health check, không deregister, DNS TTL sai, quorum số chẵn, dùng KV làm config store không versioning.

#### Day 18 — Integrating Nginx/Kong with Service Discovery
Tích hợp gateway với Consul theo 2 pattern chính: Nginx + `consul-template` render upstream config rồi `nginx -s reload`, và Kong DNS resolver query Consul SRV record qua port 8600 với TTL-based cache. Bài học phân tích pull-render pattern: watch → render → `nginx -t` → reload, debounce/splay để tránh reload storm, zero-downtime reload bằng SIGHUP; đồng thời phân tích Kong `lua-resty-dns-client`, `KONG_DNS_RESOLVER`, `KONG_DNS_STALE_TTL`, `KONG_DNS_NOT_FOUND_TTL`, A vs SRV record, stale TTL fallback khi Consul lỗi. Best practice: bật Consul `only_passing=true`, dùng SRV cho service multi-port, bật cả Consul health check và Kong active/passive health check, tránh resolver trỏ public DNS. Hands-on Docker Compose: Consul + 2 order replicas + Nginx + consul-template + Kong DB-less; scale service, quan sát Nginx reload và Kong re-resolve, kill replica, filter theo tag `prod`. Anti-pattern: hardcode IP, reload mỗi giây, dùng A record cho multi-port, không monitor Consul agent.

#### Day 19 — Production Security Hardening
Hardening gateway theo threat model external/internal/supply chain/config drift. Network boundary: Kong proxy 8000/8443 public, Admin API 8001/8444 private hoặc loopback only, Hybrid CP-DP 8005/8006 mTLS only, status 8100 chỉ cho metrics network; Admin API OSS nên đặt sau Nginx proxy với basic auth, IP allowlist và optional mTLS. TLS hardening kế thừa Day 5: TLS 1.2/1.3, Mozilla Modern config, OCSP stapling, HSTS, cert lifecycle ACME, mTLS Nginx↔Kong hoặc CP↔DP. Secret management: không để secret raw trong `kong.yml`, dùng Kong Vault references `{vault://env/...}`, `{vault://aws/...}`, `{vault://gcp/...}`, `{vault://hcv/...}`, rotation cho JWT key/key-auth/mTLS cert. Header/logging hardening: `server_tokens off`, tắt Kong server tokens/latency tokens khi phù hợp, inject security headers bằng response-transformer, mask `Authorization`, `Cookie`, query token. Hands-on gồm Admin API behind Nginx auth + IP allowlist, Vault env reference, mTLS internal, response headers, log masking, slowloris protection, `nikto`/`testssl.sh` scan. Anti-pattern: Admin API public, secret commit lên Git, Lua plugin dùng `os.execute`, image `latest`, log PII.

#### Day 20 — Capstone Project: End-to-End Gateway System
Bài capstone tích hợp toàn bộ stack: Client → Nginx Edge TLS → Kong DB-less → 3 microservices (order/payment/tracking) discover qua Consul DNS SRV; Redis cho rate-limit policy `redis`; Prometheus scrape Nginx/Kong/Consul; Grafana dashboard; decK quản lý Kong config. Roadmap 2 giờ chia 4 phase: chuẩn bị, build infra, validate features, benchmark/failure drill. Nội dung tập trung integration glue: service register Consul → Kong DNS SRV resolve → upstream; Kong rate-limit Redis atomic increment; Prometheus scrape Kong 8100 + Nginx stub_status; decK GitOps lint → diff → sync → tag; Consul down → Kong `dns_stale_ttl` → outage window. Exercises cung cấp scaffold `capstone/` với `docker-compose.yml`, `nginx.conf`, `kong.yml`, Consul service definitions, Node.js mock services, Prometheus/Grafana provisioning, decK script, k6 benchmark, failure drill scripts và `acceptance.sh`. Failure drills: service down, Kong upstream unhealthy, Consul unavailable, Redis down, rate limit exceeded, DNS stale. Deliverable: runnable end-to-end prototype + benchmark snapshot cho Day 21.

#### Day 21 — Failure Testing, Benchmark Report & Final Review
Bài cuối khóa chuyển capstone thành game day: chaos testing, benchmark report, capacity planning và final review. Ba tầng resilience testing: component test, integration test, chaos test; chaos principles gồm hypothesis-driven, blast radius nhỏ, abort criteria rõ, observability-first. Failure scenarios chuẩn: backend down/slow/5xx random, Consul agent down, Redis down, all upstream unhealthy, TLS cert expired, worker connections exhausted, retry storm, network partition, disk full, CPU spike. Tools overview: Pumba, toxiproxy, `tc netem`, chaos-mesh, Gremlin, stress-ng. Benchmark methodology dùng k6/wrk/hey/h2load/vegeta, mô hình smoke/load/stress/spike/soak, ghi rõ hardware/payload/concurrency/warmup/duration, tránh coordinated omission, báo cáo p50/p95/p99/p999/RPS/error rate/CPU/memory. Document có benchmark report template, postmortem template, error budget policy và capacity planning case study 5k/50k RPS với headroom 30%. Exercises chạy 6+ chaos scenario trên capstone, generate markdown report và worksheet retrospective. Kết thúc khóa với checklist kỹ năng và hướng học tiếp: Envoy, Istio/Linkerd, Kong Mesh, OpenTelemetry/eBPF, Kong Ingress Controller.

---

## 🚀 Cách chạy hands-on lab

### Yêu cầu

- Docker Desktop (Windows/macOS) hoặc Docker Engine (Linux)
- Docker Compose v2
- Bash shell (Git Bash trên Windows, hoặc WSL2)
- Tools benchmark: `wrk`, `hey`, `h2load`, `vegeta` (cài qua choco/brew/apt hoặc dùng image Docker)
- `openssl`, `curl`, `dig`/`nslookup` (mặc định có sẵn)
- `mkcert` (tùy chọn, để gen cert tin cậy local)
- `decK` ≥ 1.40 (cho Day 10 trở đi): `brew install kong/deck/deck` hoặc tải binary từ GitHub releases
- Image Kong: `kong:3.6` hoặc `kong:3.7` (KHÔNG dùng `kong:latest` cho production lab)

### Quy trình mỗi ngày

```bash
cd day-XX-<topic>/
# Đọc lesson.md trước
# Sau đó làm theo exercises.md
# Tham khảo document.md cho deep dive
```

Lab Docker Compose điển hình (Day 1-7):

```bash
cd day-01-reverse-proxy-traffic-flow/
# Theo hướng dẫn trong exercises.md
docker compose up -d
docker compose ps
curl -i http://localhost/order/health
curl -i http://localhost/payment/health
docker compose down -v
```

Lab Kong điển hình (Day 8 trở đi):

```bash
cd day-08-kong-architecture/
docker compose up -d
curl -s http://localhost:8001/status | jq
curl -s http://localhost:8001/services | jq
curl -i http://localhost:8000/<route-path>
docker compose down -v
```

Lab Kong + Redis (Day 12 — rate limiting policy `redis`):

```bash
cd day-12-kong-traffic-control/
docker compose up -d
curl -i http://localhost:8000/orders -H "apikey: pro-key"
# Quan sát header X-RateLimit-Remaining-Minute, RateLimit-Reset, Retry-After
docker compose exec redis redis-cli KEYS 'ratelimit:*'
docker compose down -v
```

Lab decK (Day 10, Day 15 rollback):

```bash
cd day-10-kong-dbless-deck/
deck gateway ping --kong-addr http://localhost:8001
deck gateway dump --kong-addr http://localhost:8001 -o kong.yml
deck gateway diff kong.yml
deck gateway sync kong.yml
```

Lab Observability (Day 16 — Prometheus + Grafana + Loki):

```bash
cd day-16-observability-nginx-kong/
docker compose up -d
# Grafana: http://localhost:3000 (admin/admin) — import dashboard 7424 cho Kong
curl -s http://localhost:8100/metrics | grep kong_http_requests_total
curl -s http://localhost:9113/metrics | grep nginx_connections_active
docker compose down -v
```

Lab Consul + Service Discovery (Day 17, Day 18):

```bash
cd day-17-consul-service-discovery/
docker compose up -d
curl -s http://localhost:8500/v1/health/service/order?passing | jq
dig @127.0.0.1 -p 8600 order.service.consul SRV +short

cd ../day-18-nginx-kong-service-discovery/
docker compose up -d
docker compose scale order=3
curl -s http://localhost:8001/upstreams/order-upstream/health | jq
```

Lab Capstone + Chaos (Day 20, Day 21):

```bash
cd day-20-capstone-gateway-system/capstone/
docker compose up -d
./deck/bootstrap.sh
./bench/run.sh smoke
./acceptance.sh

cd ../../day-21-failure-testing-final-review/
./drills/run-drill.sh service-down
./drills/run-drill.sh redis-down
./bench/report.sh > report.md
```

---

## 🔥 Chủ đề production xuyên suốt

Các chủ đề sau lặp lại trong nhiều ngày, đặc biệt từ Day 4 trở đi:

1. **Timeout Budget**: `client > edge > gateway > upstream > DB/cache` — giới thiệu Day 4, áp dụng lại Day 7, 8, 10, 14, 18, 20
2. **Retry Strategy**: chỉ retry idempotent, có limit, có backoff, không retry mutation API — Day 4, mở rộng Day 14, kiểm chứng Day 21 (retry storm drill)
3. **Circuit Breaker & Backpressure**: tránh đẩy traffic vô hạn vào service đang yếu — Day 4 (sơ lược), Day 14 (deep dive), Day 21 (chaos)
4. **Observability**: request count, error rate, latency p50/p95/p99, upstream latency, retry count, rate limit exceeded — Day 7 benchmark, Day 8 Kong Prometheus, Day 16 (deep dive metrics + logs), Day 20 dashboard, Day 21 benchmark report
5. **Service Discovery**: Day 17 Consul essentials, Day 18 Nginx + consul-template / Kong DNS resolver, Day 20 capstone integration
6. **Failure Scenarios**: 502/503/504, DNS stale, connection refused, TLS expired, worker_connections exhausted, retry storm, rate limit lock contention, cert expired, DP cache stale (Hybrid), Consul down, Redis down, AZ failover — luyện đầy đủ ở Day 21
7. **Security Hardening**: TLS Day 5, auth Day 11, rate limit Day 6/12, full hardening Day 19 (network boundary, Vault, Admin API behind proxy, secret rotation, log masking)
8. **GitOps & Rollback**: Day 10 — declarative config, decK diff/sync, dump-before-sync, blue-green cluster, Day 15 canary/blue-green, Day 20 GitOps pipeline trong capstone

---

## 📊 Benchmark methodology (chuẩn áp dụng cho mọi ngày)

Mọi benchmark phải có:

- **Tool**: `wrk` / `hey` / `h2load` / `vegeta` / `k6`
- **Hardware**: CPU cores, RAM, kernel, network topology (cùng host vs khác host vs khác AZ)
- **Workload**: payload size (vd 1KB JSON), connections, threads, duration, warmup
- **Toggle**: TLS on/off, keepalive on/off, gzip on/off, plugin on/off
- **Báo cáo**: p50 / p95 / p99 / p999 / max + throughput (RPS) + error rate by type + CPU/memory utilization
- **Lưu ý**: tránh **coordinated omission** (Day 7) — không dùng tool block khi sender bận
- **Disclaimer**: số liệu chỉ tham khảo, phụ thuộc hardware/kernel/network/payload

---

## 🛠️ Troubleshooting checklist nhanh

### Nginx layer

- DNS resolution OK? (`dig`, `nslookup` từ container Nginx)
- Upstream health OK? (`curl` thẳng tới backend)
- Timeout có hợp lý không? (so với client timeout, DB timeout, theo Timeout Budget)
- Đã đọc `access_log` và `error_log` của Nginx?
- Connection limit (`worker_connections`, `ulimit -n`) còn không?
- CPU/memory/file descriptor có chạm trần?
- TLS handshake có lỗi (cert expired, SNI mismatch, clock skew)?
- Rate limit có đang reject? (log keyword: `limiting requests`)
- Real IP có đúng khi đứng sau CDN? (`set_real_ip_from`, `real_ip_header`)

### Kong layer

- Admin API alive? (`curl :8001/status`)
- kong.yml syntax OK? (`kong config parse kong.yml`, `deck file lint`)
- Plugin scope đúng? (global / service / route / consumer)
- Plugin priority có gây side-effect? (rate-limit chạy trước hay sau auth?)
- 404: route không match → kiểm tra hosts / paths / methods / headers, dump bằng `curl :8001/routes`
- 401: auth plugin chặn → kiểm tra credential, anonymous setting
- 429: rate-limit → kiểm tra scope và policy
- DP không nhận config (Hybrid): cert + port 8005 + version mismatch CP-DP

### Observability layer (Day 16)

- Prometheus scrape `8100/metrics` (Kong), `9113/metrics` (nginx-exporter), `8500/v1/agent/metrics?format=prometheus` (Consul) thành công?
- `kong_http_requests_total`, `kong_upstream_latency_bucket` xuất hiện không?
- PromQL `histogram_quantile` aggregate `sum by (le, route)` chứ không `sum()` rồi quantile
- Cardinality: route/service label OK, cấm tag user-id, full path
- Loki/Promtail nhận log JSON? Mask `Authorization`, `Cookie`?

### Service discovery layer (Day 17–18)

- `dig @<consul> -p 8600 <svc>.service.consul SRV` trả đúng port?
- Consul agent join OK, encrypt key match, gossip 8301 mở?
- consul-template watch ổn định, debounce + splay đặt đúng?
- Kong `KONG_DNS_RESOLVER` trỏ Consul, `dns_stale_ttl ≥ 4s`, `only_passing=true` ở DNS config?
- Health check Consul + Kong active/passive đều bật?

### Security layer (Day 19)

- Admin API bind loopback hoặc behind Nginx auth + IP allowlist?
- `kong.yml` không chứa raw secret, dùng `{vault://env/...}`, `{vault://hcv/...}`?
- `server_tokens off` (Nginx), Kong tắt `latency_tokens`/`server_tokens` ở edge?
- TLS 1.2/1.3, Mozilla Modern config, OCSP stapling, HSTS, cert chưa hết hạn?
- Image pinned theo sha256, container chạy non-root, read-only FS?
- Log đã mask Authorization/Cookie/query token?

### Resilience & Capacity layer (Day 21)

- Có abort criteria và observability dashboard trước khi chạy chaos drill?
- Mỗi chaos scenario có hypothesis + expected behavior + rollback?
- Benchmark có warmup, đủ duration, tránh coordinated omission?
- Báo cáo p50/p95/p99/p999 + RPS + error rate + CPU/memory?
- Capacity plan có headroom 30% và autoscale trigger định nghĩa rõ?

---

## 🎓 Completion checklist toàn khóa

### Tuần 1 (Nginx)

- [ ] Hiểu được vai trò của reverse proxy, load balancer, API Gateway và thứ tự đứng trong traffic flow
- [ ] Dựng được Nginx reverse proxy trước nhiều backend services bằng Docker Compose
- [ ] Giải thích được mô hình master/worker, event loop và connection lifecycle của Nginx
- [ ] Tune được `worker_processes`, `worker_connections`, keepalive theo workload
- [ ] Configure được round-robin, least_conn, ip_hash, hash, weighted upstream và biết khi nào dùng
- [ ] Phân biệt rõ 502 / 503 / 504 từ error log và biết cách fix
- [ ] Cấu hình được `proxy_next_upstream` an toàn, không gây retry storm
- [ ] Hiểu Timeout Budget và áp dụng đúng giữa các layer
- [ ] Bật được HTTPS với TLS 1.2/1.3 và HTTP/2, verify bằng `openssl s_client` và `curl --http2 -v`
- [ ] Bật HSTS, OCSP stapling, session resumption đúng cách
- [ ] Cấu hình `limit_req` / `limit_conn` đúng key, hiểu burst / nodelay / delay
- [ ] Tránh false positive khi đứng sau CDN (set_real_ip_from)
- [ ] Tune sysctl + Nginx + benchmark methodology đầy đủ, đọc kết quả p50/p95/p99
- [ ] Capacity planning sơ bộ theo công thức RPS = cores × clock × eff / cycles

### Tuần 2 (Kong)

- [ ] Hiểu Kong = Nginx + OpenResty + plugin Lua, biết các Nginx phase và Lua hook
- [ ] Phân biệt Data Plane / Control Plane, ports 8000 / 8443 / 8001 / 8444 / 8100 / 8005
- [ ] Dựng được Kong DB-less bằng Docker Compose từ kong.yml
- [ ] CRUD Service / Route / Consumer / Plugin qua Admin API và qua kong.yml
- [ ] Hiểu plugin scope precedence (consumer + route + service > ... > global)
- [ ] Phân biệt path_handling v0 vs v1, strip_path, preserve_host
- [ ] So sánh DB-mode / DB-less / Hybrid và biết khi nào chọn cái nào
- [ ] Workflow GitOps với decK: lint → validate → diff → sync → tag
- [ ] Rollback bằng dump-before-sync hoặc git revert + sync
- [ ] Tag-based partial sync để chia ownership giữa team
- [ ] Bảo vệ API bằng key-auth, JWT HS256/RS256 và hiểu khi nào dùng mTLS
- [ ] Thiết kế auth strategy theo client type: public app / partner B2B / service-to-service
- [ ] Configure rate-limiting policy `local` / `cluster` / `redis`, hiểu fail-open vs fail-close khi Redis lỗi
- [ ] Dùng ACL group, IP Restriction CIDR, request-transformer, request-termination đúng scope
- [ ] Configure Kong Upstream + Target + weight + active/passive health check
- [ ] Chọn đúng load balancing algorithm: round-robin / consistent-hashing / least-connections / latency / none
- [ ] Thiết kế Timeout Budget và Retry Strategy an toàn, tránh retry storm
- [ ] Hiểu passive health check như circuit breaker primitive và khi nào cần circuit breaker per-route
- [ ] Thực hiện canary rollout bằng upstream weight hoặc route-level header
- [ ] Thực hiện blue-green deployment và gateway config rollback bằng decK snapshot
- [ ] Đọc được các metric/log quan trọng: 401/403/429/5xx, `kong_latency`, `kong_upstream_latency`, `kong_upstream_target_health`, p95/p99 per version

### Tuần 3 (Observability, Discovery, Production)

- [ ] Configure Nginx `stub_status` + `nginx-prometheus-exporter` và Kong plugin `prometheus`, scrape ổn định
- [ ] Thiết kế dashboard theo USE method (Nginx) và RED method (Kong)
- [ ] Viết PromQL `rate`, `histogram_quantile`, `sum by (le, route)` đúng cho multi-instance
- [ ] Bật JSON access log Nginx + Kong `file-log`/`http-log`, ship qua Promtail/Filebeat về Loki/ELK
- [ ] Kiểm soát cardinality, mask PII trong log
- [ ] Dựng Consul cluster (server quorum + client agent), register service bằng API/file, configure health check HTTP/TCP/TTL
- [ ] Query service qua REST `?passing=true` và DNS `<svc>.service.consul SRV`
- [ ] Hiểu Raft consensus, gossip protocol, failure khi Consul agent/quorum down
- [ ] Render Nginx upstream bằng consul-template với debounce/splay, reload zero-downtime
- [ ] Configure Kong `KONG_DNS_RESOLVER`, `dns_stale_ttl`, `dns_not_found_ttl`, `dns_error_ttl` cho SRV record
- [ ] Bật song song Consul health check và Kong active/passive health check
- [ ] Đặt Admin API sau Nginx auth + IP allowlist (hoặc loopback only), rotate token định kỳ
- [ ] Sử dụng Kong Vault references thay raw secret, rotate JWT key/key-auth/mTLS cert
- [ ] Inject security headers (HSTS, CSP, X-Content-Type-Options) bằng response-transformer
- [ ] Configure mTLS giữa Edge LB ↔ Kong, CP ↔ DP (hybrid), bật `server_tokens off`
- [ ] Hardening container: image pinned sha256, non-root, read-only FS, drop capabilities
- [ ] Mask `Authorization`/`Cookie`/query token trong access log; biết PCI/SOC2/ISO 27001 checklist
- [ ] Orchestrate capstone Nginx → Kong → 3 microservices ↔ Consul + Redis + Prometheus + Grafana bằng Docker Compose
- [ ] Áp dụng decK GitOps cho Kong config trong capstone (lint → diff → sync → tag)
- [ ] Pass acceptance.sh capstone (15 criteria) và snapshot benchmark trước Day 21
- [ ] Thiết kế chaos experiment với hypothesis, blast radius, abort criteria và observability-first
- [ ] Chạy 6+ failure scenarios trên capstone (service down, slow, Consul down, Redis down, retry storm, TLS expired) và viết runbook
- [ ] Viết benchmark report theo template (env, methodology, scenarios, raw, observation, recommendation)
- [ ] Tính capacity planning cho 5k/50k RPS với headroom 30% và autoscale trigger

---

## 📌 Next steps (sau Day 21)

Khoá 21 ngày đã cover xong gateway/load balancer/observability/discovery/security/capstone/chaos. Hướng học tiếp:

- **Service mesh**: Istio, Linkerd, Kong Mesh — mở rộng từ gateway North-South sang East-West, mTLS giữa pod-to-pod, circuit breaker per-route
- **Envoy & xDS**: Envoy Proxy nâng cao, dynamic config qua xDS API (CDS/EDS/LDS/RDS), Envoy outlier detection vs Kong passive health
- **Kubernetes Ingress**: Kong Ingress Controller, Gateway API, NGINX Ingress, ingress vs service mesh ingress vs API Gateway
- **OpenTelemetry & eBPF observability**: chuẩn hoá traces/metrics/logs, sampling strategy, USE+RED+Golden Signals; eBPF (Cilium, Pixie, Beyla) để observe không inject SDK
- **Advanced Kong**: Kong Konnect, custom plugin với `lua-resty-*` đúng chuẩn, RBAC enterprise, dev portal, admin GUI
- **Security deep dive**: WAF (ModSecurity 3 / Coraza Lua / CRS), runtime security (Falco), supply chain (SLSA, Sigstore), zero-trust internal networking
- **Reliability engineering**: gameday cadence, error budget policy, SLO/SLI design, postmortem culture, Wheel of Misfortune
- **FinOps cho gateway**: cost per million request, sizing Cloud LB vs self-host, savings plan/spot capacity, autoscale economics

---

## 📁 Tài liệu nguồn

- Plan gốc: [`api-gateway-load-balancer-nginx-kong-plan-revised.md`](./api-gateway-load-balancer-nginx-kong-plan-revised.md)
- Generate process: [`gateway-generate.md`](./gateway-generate.md)
- Note ngắn: [`note.txt`](./note.txt)

---

## 📜 Quy ước ngôn ngữ

Toàn bộ nội dung viết bằng **tiếng Việt**. Giữ nguyên các thuật ngữ chuyên ngành bằng **English** (load balancer, reverse proxy, upstream, health check, rate limiting, leaky bucket, token bucket, circuit breaker, p50/p95/p99, observability, decK, DB-less, declarative, GitOps, ...).
