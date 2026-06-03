# API Gateway, Load Balancer, Nginx & Kong — 21 ngày thực chiến

Lộ trình dành cho Senior Software Engineer muốn thiết kế, triển khai và vận hành tầng traffic cho hệ thống microservices production-scale.

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học các bài sau trước để nhanh nhất có thể thiết kế và vận hành gateway:

1. [Day 01: Reverse Proxy & Traffic Flow Foundation](./day-01-reverse-proxy-traffic-flow/lesson) — reverse proxy vs forward proxy, traffic flow, Nginx setup căn bản
2. [Day 04: Health Check, Failover & Upstream Failure](./day-04-health-check-failover/lesson) — 502/503/504 troubleshooting, timeout budget, retry strategy
3. [Day 05: TLS Termination, HTTP/2 & Secure Edge](./day-05-tls-http2-secure-edge/lesson) — TLS 1.3, HSTS, OCSP stapling, HTTP/2 multiplexing
4. [Day 06: Rate Limiting, Connection Limiting & Basic Protection](./day-06-rate-limiting/lesson) — leaky bucket, burst, nodelay, geo whitelist, anti-DDoS
5. [Day 08: Kong Architecture & OpenResty Foundation](./day-08-kong-architecture/lesson) — Kong = Nginx + LuaJIT, 3 deployment modes, Admin API
6. [Day 09: Kong Core Entities](./day-09-kong-core-entities/lesson) — Services, Routes, Consumers, Plugins — entity cốt lõi nhất của Kong
7. [Day 11: Authentication: Key Auth, JWT, mTLS](./day-11-kong-authentication/lesson) — key-auth, JWT HS256/RS256, multiple auth fallback
8. [Day 13: Kong Upstream & Health Checks](./day-13-kong-upstream/lesson) — active + passive health check, load balancing algorithms
9. [Day 16: Observability for Nginx & Kong](./day-16-observability-nginx-kong/lesson) — Prometheus metrics, JSON logs, Grafana dashboard
10. [Day 20: Capstone — End-to-End Gateway System](./day-20-capstone-gateway-system/lesson) — tích hợp toàn bộ stack, failure drill, benchmark

Sau 10 bài này bạn đã có thể thiết kế và vận hành production-grade gateway với Nginx + Kong, hiểu sâu timeout/retry/health check, auth và observability.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---|---|---:|---|
| Phase 1 — Nginx Foundation | Day 01-07 | Reverse proxy, architecture, load balancing, TLS, rate limiting, performance tuning | Nginx production config + benchmark |
| Phase 2 — Kong Gateway | Day 08-15 | Kong architecture, entities, DB-less/decK, auth, rate-limit, upstream, resilience, rollout | Kong gateway với declarative config |
| Phase 3 — Production Readiness | Day 16-21 | Observability, Consul service discovery, security hardening, capstone, chaos testing | End-to-end gateway system + benchmark report |

## Mức độ ưu tiên (80/20 analysis)

### Nhóm A — Bắt buộc học trước (20% kiến thức tạo 80% giá trị)

| Bài | Chủ đề | Vì sao quan trọng |
|---|---|---:|---|
| Day 01 | Reverse Proxy & Traffic Flow Foundation | Nền tảng: không hiểu reverse proxy thì không thiết kế được traffic flow cho system |
| Day 04 | Health Check, Failover & Upstream Failure | Troubleshooting 502/503/504 là kỹ năng hàng ngày; timeout budget ngăn cascading failure |
| Day 05 | TLS Termination, HTTP/2 & Secure Edge | TLS là bắt buộc cho production; thiếu HSTS/OCSP = lỗ hổng bảo mật |
| Day 06 | Rate Limiting, Connection Limiting | DDoS/brute-force protection cơ bản nhất; leaky bucket + burst là pattern áp dụng mọi nơi |
| Day 08 | Kong Architecture & OpenResty Foundation | Kiến trúc nền cho toàn bộ Week 2: deployment mode, Admin API, plugin lifecycle phases |
| Day 09 | Kong Core Entities | 4 entity cốt lõi dùng mỗi ngày; không hiểu Service/Route/Consumer/Plugin thì không config được Kong |
| Day 11 | Key Auth, JWT, mTLS | Auth là tính năng #1 của API Gateway; consumer model + plugin priority |
| Day 13 | Kong Upstream & Health Checks | Active health check là điểm khác biệt lớn nhất giữa Kong và Nginx OSS |
| Day 16 | Observability for Nginx & Kong | Không có metrics/logs → không biết gateway đang hoạt động thế nào |
| Day 20 | Capstone — End-to-End Gateway | Tích hợp toàn bộ kiến thức 19 ngày thành production-grade system |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---:|---|
| Day 02 | Nginx Architecture — Master/Worker, Event Loop | Giải thích `max_clients`, zero-downtime reload, event-driven I/O — debug Nginx performance |
| Day 03 | Load Balancing Algorithms | round-robin, least_conn, ip_hash, consistent hashing — chọn sai algorithm gây uneven traffic |
| Day 07 | Nginx Performance Tuning & Benchmark | wrk/hey/h2load benchmark, p50/p95/p99, capacity planning — cần để đo trước khi tune |
| Day 10 | DB-less vs DB-mode & decK Workflow | GitOps cho Kong: lint → diff → sync; dump-before-sync rollback |
| Day 12 | Rate Limiting, ACL, IP Restriction & Request Control | Redis policy cho multi-node Kong; ACL + IP restriction cho multi-tenant |
| Day 14 | Timeout, Retry, Circuit Breaker & Backpressure | Retry storm là nguyên nhân #1 cascading failure; deadline propagation |
| Day 15 | Canary, Blue-Green & Gateway Config Rollback | Deployment strategy cơ bản cho gateway; canary = route-level + upstream weight |
| Day 19 | Production Security Hardening | Admin API bảo vệ, Vault references, mTLS internal, log masking |
| Day 21 | Failure Testing, Benchmark & Final Review | Chaos testing trên capstone, benchmark report, capacity planning |

### Nhóm C — Học sau khi làm được project cơ bản

| Bài | Chủ đề | Khi nào quay lại |
|---|---|---:|---|
| Day 17 | Consul Service Discovery Essentials | Khi có > 5 services cần service registry + health check |
| Day 18 | Nginx/Kong + Service Discovery Integration | Khi cần auto-discover backend; consul-template render + DNS SRV |

### Nhóm D — Đọc lướt / tra cứu

| Bài | Chủ đề | Ghi chú |
|---|---|---:|---|
| `document.md` các ngày | Deep dive, reference | Tra cứu khi cần |
| `api-gateway-load-balancer-nginx-kong-plan-revised.md` | Plan gốc | Tài liệu tham khảo |
| `gateway-generate.md` | Generate process | Process documentation |

## Cách học đề xuất

1. **Phase 1** (Day 01-07): Nginx Foundation — học Day 01 → 04 → 05 → 06 → 02 → 03 → 07. Mục tiêu: dựng Nginx reverse proxy + TLS + rate limiting + benchmark.
2. **Phase 2** (Day 08-15): Kong Gateway — học Day 08 → 09 → 11 → 13 → 10 → 12 → 14 → 15. Mục tiêu: dựng Kong gateway với auth, upstream, rate-limit, decK GitOps.
3. **Phase 3** (Day 16-21): Production Readiness — học Day 16 → 19 → 17 → 18 → 20 → 21. Mục tiêu: observability, security, capstone + chaos testing.

Mỗi ngày học 2 giờ theo format:
- 20 phút: đọc concept + problem scenario
- 25 phút: deep dive core concepts + trade-offs
- 50 phút: hands-on lab với Docker Compose
- 15 phút: troubleshooting / checklist
- 10 phút: ghi chú

## Mini project — End-to-End Gateway System (Capstone)

**Mô tả:** Xây dựng production-grade gateway stack: `Client → Nginx Edge TLS → Kong DB-less → 3 microservices (order/payment/tracking) ↔ Consul DNS SRV + Redis rate-limit + Prometheus/Grafana observability + decK GitOps`.

**Stack:**
- Nginx + Kong 3.x + Consul + Redis + Prometheus + Grafana + Loki
- Docker Compose, decK, k6/wrk

**Kiến thức áp dụng:**
- Nginx reverse proxy + TLS termination + HTTP/2
- Kong DB-less declarative config, Services/Routes/Consumers/Plugins
- Key Auth + JWT authentication, rate-limiting với Redis policy
- Upstream load balancing + active/passive health check
- Consul DNS SRV service discovery
- Prometheus metrics + Grafana dashboard
- decK GitOps pipeline: lint → diff → sync → tag
- Failure drill: service down, Redis down, Consul down, retry storm

**Tiêu chí hoàn thành:**
- 3 microservices discoverable qua Consul DNS SRV
- Kong upstream + active health check + weighted load balancing
- Key Auth + JWT cho API protection
- Rate-limiting Redis policy cho multi-node consistency
- Prometheus scrape Nginx + Kong + Consul thành công
- Grafana dashboard với RED method metrics
- decK dump-before-sync rollback
- Pass 6+ failure scenarios (Day 21 drills)

## Checklist học nhanh

- [ ] Tôi đã hiểu reverse proxy khác forward proxy và load balancer ở điểm nào
- [ ] Tôi đã dựng được Nginx reverse proxy + TLS + HTTP/2 bằng Docker Compose
- [ ] Tôi đã cấu hình rate limiting, biết burst/nodelay khác nhau thế nào
- [ ] Tôi đã troubleshoot 502/503/504 từ error log và biết cách fix
- [ ] Tôi đã dựng được Kong DB-less với declarative config (kong.yml)
- [ ] Tôi đã CRUD Service/Route/Consumer/Plugin qua Admin API
- [ ] Tôi đã bảo vệ API bằng key-auth và JWT
- [ ] Tôi đã configure Kong upstream + active health check + weighted targets
- [ ] Tôi đã setup Prometheus + Grafana cho gateway metrics
- [ ] Tôi đã hoàn thành capstone và pass failure drills

## Flashcard / câu hỏi ôn tập gợi ý

1. Reverse proxy khác forward proxy thế nào?
   - **Đáp án:** Forward proxy đại diện cho client (yêu cầu resource thay client), reverse proxy đại diện cho server (nhận request thay server). Forward proxy giấu client, reverse proxy giấu server.
   - **Liên quan:** Day 01

2. Tại sao Load Balancer nên đứng trước API Gateway?
   - **Đáp án:** LB chịu trách nhiệm TLS termination + DDoS mitigation + HA (multi-AZ), gateway chịu trách nhiệm routing + auth + rate-limit. Nếu gateway chết, LB vẫn có thể trả 503 hoặc redirect sang cụm dự phòng.
   - **Liên quan:** Day 01

3. Công thức `max_clients` trong Nginx?
   - **Đáp án:** `max_clients = worker_processes × worker_connections / 2` (chia 2 vì một connection cho client, một cho upstream).
   - **Liên quan:** Day 02

4. 502 vs 503 vs 504 khác nhau thế nào?
   - **Đáp án:** 502 = bad gateway (upstream trả response lỗi hoặc connection refused), 503 = upstream không available (không có target healthy), 504 = upstream timeout.
   - **Liên quan:** Day 04

5. Khi nào nên dùng Kong thay vì Nginx thuần?
   - **Đáp án:** Khi cần > 2 plugins (auth, rate-limit, logging), Admin API dynamic routing, consumer model, active health check, Redis shared rate-limit, GitOps với decK.
   - **Liên quan:** Day 08

6. Plugin scope precedence trong Kong?
   - **Đáp án:** `consumer + route + service > consumer + route > consumer + service > consumer > route + service > route > service > global`
   - **Liên quan:** Day 09

7. Kong active health check khác Nginx passive thế nào?
   - **Đáp án:** Active: Kong chủ động gửi request `/healthz` định kỳ tới target — phát hiện lỗi trước khi user request. Passive: Nginx ghi nhận lỗi khi proxy request (max_fails/fail_timeout) — chỉ phát hiện khi có request thật.
   - **Liên quan:** Day 13

8. Vì sao Kong cần Redis cho rate-limiting ở multi-node?
   - **Đáp án:** Policy `local` mỗi node tự đếm → 10 node cho phép 10× rate. Redis atomic Lua `INCR + EXPIRE` cho counter chính xác toàn cluster.
   - **Liên quan:** Day 12

9. Retry storm là gì và cách phòng tránh?
   - **Đáp án:** Retry storm: backend slow → gateway retry nhiều lần → load tăng gấp N lần → backend sập → cascading failure. Phòng tránh: retry budget (~10% extra), chọn idempotent method, exponential backoff + jitter, circuit breaker.
   - **Liên quan:** Day 14

10. Blue-green deployment cho gateway khác gì cho application?
    - **Đáp án:** Gateway blue-green = 2 cluster DB-less hoàn toàn độc lập, edge LB switch L7 atomic. App blue-green cần DB migration backward-compatible (expand-contract pattern). Rollback gateway xong nhưng app DB đã migrate → data corrupt.
    - **Liên quan:** Day 15

## Tài nguyên

- [README tổng quan khóa học](./README.md)
- [Plan gốc](./api-gateway-load-balancer-nginx-kong-plan-revised.md)
- [Kong Documentation](https://docs.konghq.com/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [decK Documentation](https://docs.konghq.com/deck/)
- [Consul Documentation](https://developer.hashicorp.com/consul/docs)
