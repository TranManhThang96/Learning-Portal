# Day 06: Deep Dive — Rate Limiting Internals & Distributed Architecture

> Tài liệu tham khảo nội bộ cho Day 06. Đọc sau khi hoàn thành `lesson.md`.

---

## 1. Leaky Bucket vs Token Bucket — Chi tiết kỹ thuật

### 1.1 Leaky Bucket Algorithm

Leaky bucket là metaphor: nước (request) đổ vào xô (queue), xô rò rỉ đều đặn (processing rate). Nếu đổ nhanh hơn rò rỉ → xô tràn → request bị reject.

```
Leaky Bucket State Machine:

State: {last_time: T, excess: E}

Khi request đến tại thời điểm t:
  1. drain = (t - last_time) * rate
  2. new_excess = max(0, E - drain) + 1
  3. if new_excess > burst_size → REJECT
  4. else → ACCEPT, update state: {last_time=t, excess=new_excess}

Ví dụ: rate=10r/s, burst=20
  t=0.0: request đến, E=0
    drain = 0, new_excess = 0 + 1 = 1 → ACCEPT
  t=0.05: request đến (50ms sau)
    drain = 0.05 * 10 = 0.5, new_excess = max(0, 1-0.5) + 1 = 1.5 → ACCEPT
  t=0.05: 20 requests đến cùng lúc
    new_excess = 1.5 + 20 = 21.5 > 20 → REJECT (excess > burst)
```

**Đặc điểm của leaky bucket:**
- Output rate luôn đều đặn (smooth), không có spike
- Burst được queue, không bị reject ngay (nếu còn chỗ)
- Phù hợp khi backend cần được bảo vệ khỏi spike

### 1.2 Token Bucket Algorithm

Token bucket tích lũy token theo thời gian. Mỗi request tiêu 1 token. Nếu hết token → reject.

```
Token Bucket State Machine:

State: {tokens: T, last_refill: L}

Khi request đến tại thời điểm t:
  1. new_tokens = min(max_tokens, T + (t - L) * refill_rate)
  2. if new_tokens < 1 → REJECT
  3. else → ACCEPT, update: {tokens=new_tokens-1, last_refill=t}

Ví dụ: refill_rate=10/s, max_tokens=20
  t=0: tokens=20 (đầy)
  t=0: 25 requests đến
    → 20 requests đầu: ACCEPT (tiêu hết token)
    → 5 requests sau: REJECT (hết token)
  t=1: tokens = min(20, 0 + 1*10) = 10
    → 10 requests tiếp: ACCEPT
```

**Đặc điểm của token bucket:**
- Cho phép burst ngắn (tiêu token tích lũy)
- Output rate có thể spike (khác leaky bucket)
- Phù hợp khi muốn cho phép burst hợp lệ

### 1.3 So sánh chi tiết

```
Scenario: rate=10r/s, burst=20, 30 requests đến t=0

Leaky Bucket (Nginx limit_req):
  t=0:    10 requests → PASS ngay
          20 requests → vào queue
  t=0.1:  1 request từ queue → PASS
  t=0.2:  1 request từ queue → PASS
  ...
  t=2.0:  request cuối từ queue → PASS
  Tổng: 30 requests PASS, 0 REJECT, nhưng 20 requests bị delay 0.1-2.0s

Token Bucket (Kong):
  t=0:    20 requests → PASS ngay (tiêu hết token)
          10 requests → REJECT ngay (hết token)
  t=1:    10 token mới → 10 requests PASS
  Tổng: 20 requests PASS ngay, 10 REJECT ngay

Với nodelay (Nginx limit_req burst=20 nodelay):
  t=0:    30 requests → PASS ngay (không delay)
          Counter = 30
  t=0-2:  Các requests tiếp theo → REJECT (counter drain về 0 sau 2s)
  Tổng: 30 requests PASS ngay, sau đó 2s không accept request mới
```

### 1.4 Fixed Window vs Sliding Window

```
Fixed Window (đơn giản nhất):
  Window: [0s, 60s), [60s, 120s), ...
  Limit: 100 req/window

  Vấn đề: Boundary spike
  t=59s: 100 requests → PASS (window 1 đầy)
  t=61s: 100 requests → PASS (window 2 mới)
  → 200 requests trong 2 giây! (spike tại boundary)

Sliding Window (chính xác nhất):
  Tại mỗi thời điểm t, đếm requests trong [t-60s, t]
  Không có boundary spike
  Tốn memory hơn (cần lưu timestamp của từng request)

  Nginx không implement sliding window natively
  → Cần Redis với sorted set để implement
```

---

## 2. Shared Memory Zone — Layout và Implementation

### 2.1 Memory Layout

Nginx dùng `ngx_slab_pool_t` để quản lý shared memory zone:

```
Shared Memory Zone (vd: 10m):
┌─────────────────────────────────────────────────────┐
│  ngx_slab_pool_t header (~256 bytes)                │
│  - mutex (spinlock)                                  │
│  - free list                                         │
│  - stats                                             │
├─────────────────────────────────────────────────────┤
│  Red-Black Tree (ngx_rbtree_t)                      │
│  - Sorted by key hash                                │
│  - O(log n) lookup, insert, delete                  │
│                                                      │
│  Node structure (per key):                          │
│  ┌─────────────────────────────────────────────┐   │
│  │  key: hash($binary_remote_addr)              │   │
│  │  data: {last_msec: uint64, excess: uint32}   │   │
│  │  rbtree pointers: left, right, parent        │   │
│  │  Total: ~64 bytes per node                   │   │
│  └─────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│  LRU Queue (ngx_queue_t)                            │
│  - Doubly linked list                               │
│  - Least recently used node ở đầu                  │
│  - Khi zone đầy: xóa node LRU nhất                 │
└─────────────────────────────────────────────────────┘
```

### 2.2 Mutex và Lock Contention

```
Nginx dùng spinlock (không sleep, busy-wait)
Phù hợp cho critical section ngắn (microseconds)

Pseudo-code của limit_req processing:
  acquire_spinlock(zone->mutex)
    node = rbtree_lookup(tree, key)
    if node:
      update_excess(node, now, rate)
    else:
      node = slab_alloc(pool, sizeof(node))
      rbtree_insert(tree, node)
    result = check_limit(node, burst)
  release_spinlock(zone->mutex)

Lock contention analysis:
  Critical section: ~1-5 microseconds
  Với 4 workers, 100k req/s: ~25k req/s per worker
  Lock hold time: 5μs, inter-arrival: 40μs → contention thấp
  Chỉ là vấn đề ở >500k req/s trên single server
```

### 2.3 LRU Eviction

Khi zone đầy, Nginx không reject request. Thay vào đó:
1. Tìm node LRU nhất (ít được access nhất)
2. Xóa node đó
3. Tạo node mới cho request hiện tại

Điều này có nghĩa: nếu zone quá nhỏ, các IP cũ bị evict → counter reset → rate limit không chính xác.

```bash
# Dấu hiệu zone đầy và eviction xảy ra:
[warn] 1234#0: *5678 limiting requests, excess: 0.000 by zone "api_limit"
# excess=0 nhưng vẫn log → có thể do eviction làm reset counter
```

---

## 3. Distributed Rate Limiting

### 3.1 Vấn đề với Per-Instance Rate Limiting

```
Deployment: 3 Nginx instances sau Load Balancer

Client gửi 30 req/s:
  LB phân phối đều: 10 req/s per instance
  Rate limit: 10r/s per instance

  Instance 1: 10 req/s → không bị limit
  Instance 2: 10 req/s → không bị limit
  Instance 3: 10 req/s → không bị limit

  Tổng: 30 req/s đến backend → rate limit không hiệu quả!

Nếu LB không phân phối đều (sticky session):
  Instance 1: 25 req/s → 15 req/s bị reject
  Instance 2: 3 req/s → không bị limit
  Instance 3: 2 req/s → không bị limit
  → Inconsistent behavior
```

### 3.2 Giải pháp: Redis-based Distributed Rate Limiting

```
Architecture:
                    ┌─────────────────┐
  Client ──► LB ──►│  Nginx Instance 1│──┐
                    └─────────────────┘  │
                    ┌─────────────────┐  ├──► Redis Cluster
  Client ──► LB ──►│  Nginx Instance 2│──┤    (shared counter)
                    └─────────────────┘  │
                    ┌─────────────────┐  │
  Client ──► LB ──►│  Nginx Instance 3│──┘
                    └─────────────────┘
```

Nginx OSS không có Redis integration cho rate limiting. Cần:
- `lua-resty-limit-traffic` (OpenResty/Nginx với Lua module)
- Kong Gateway (built-in Redis support)
- Custom Nginx module

### 3.3 Kong Rate Limiting với Redis

```yaml
# Kong rate-limiting plugin config
plugins:
  - name: rate-limiting
    config:
      minute: 60
      hour: 1000
      policy: redis
      redis_host: redis
      redis_port: 6379
      redis_timeout: 2000
      hide_client_headers: false
      # Headers tự động thêm:
      # X-RateLimit-Limit-Minute: 60
      # X-RateLimit-Remaining-Minute: 45
      # X-RateLimit-Reset-Minute: 1705312800
```

**Redis data structure cho rate limiting:**
```
Key: "kong:rate-limiting:consumer_id:minute:1705312800"
Value: 45 (số request đã dùng)
TTL: 60 seconds

Atomic increment: INCR key → trả về giá trị mới
Nếu giá trị > limit → reject
```

### 3.4 Fail-Open vs Fail-Closed

Khi Redis down, distributed rate limiting phải quyết định:

```
Fail-Open (cho phép request khi Redis down):
  + Service vẫn hoạt động
  - Rate limit không hiệu quả trong thời gian Redis down
  - Attacker có thể khai thác window này

Fail-Closed (reject request khi Redis down):
  + Rate limit luôn được enforce
  - Service không hoạt động khi Redis down
  - Không phù hợp cho production critical service

Recommendation: Fail-Open với alerting
  - Khi Redis down: log crit, alert on-call
  - Cho phép request nhưng monitor anomaly
  - Có fallback local rate limit (Nginx limit_req) làm safety net
```

---

## 4. Rate Limiting Headers — RFC Standards

### 4.1 RFC 6585 — 429 Too Many Requests

```
HTTP/1.1 429 Too Many Requests
Content-Type: text/html
Retry-After: 3600
```

**`Retry-After` header:**
- Giá trị số: số giây cần đợi (`Retry-After: 60`)
- Giá trị date: HTTP-date (`Retry-After: Wed, 21 Oct 2015 07:28:00 GMT`)

### 4.2 Draft: RateLimit Headers (IETF)

Có draft IETF cho standardized rate limit headers (chưa là RFC chính thức):

```
RateLimit-Limit: 100
RateLimit-Remaining: 45
RateLimit-Reset: 1705312800
```

Kong tự động thêm các headers này. Nginx OSS cần thêm thủ công:

```nginx
add_header X-RateLimit-Limit 100 always;
add_header Retry-After 10 always;
```

---

## 5. Nginx OSS vs Kong Rate Limiting — Technical Deep Dive

### 5.1 Decision Matrix

```
Chọn Nginx OSS limit_req khi:
  ✓ Single instance hoặc chấp nhận per-instance limit
  ✓ Simple IP-based rate limiting
  ✓ Không cần dynamic config
  ✓ Muốn zero dependency
  ✓ Traffic < 100k req/s

Chọn Kong rate-limiting khi:
  ✓ Multi-instance deployment cần consistent limit
  ✓ Rate limit theo authenticated user/consumer
  ✓ Cần thay đổi rate limit không cần reload
  ✓ Cần rate limit analytics
  ✓ Đã dùng Kong làm API Gateway

Chọn Application-level (Redis) khi:
  ✓ Business logic phức tạp (tier-based: free/paid/enterprise)
  ✓ Rate limit theo user account, không phải IP
  ✓ Cần custom response body khi bị limit
  ✓ Cần rate limit theo nhiều dimension cùng lúc
```

---

## 6. Security Considerations

### 6.1 X-Forwarded-For Spoofing

```
Attacker có thể spoof X-Forwarded-For:
  curl -H "X-Forwarded-For: 127.0.0.1" http://api.example.com/

Nếu Nginx trust tất cả X-Forwarded-For mà không có set_real_ip_from
→ attacker bypass rate limit bằng cách giả mạo IP whitelist

Fix: Chỉ trust IP của proxy bạn kiểm soát
  set_real_ip_from 10.0.0.1;  # IP cụ thể của LB
  real_ip_header X-Forwarded-For;
  real_ip_recursive on;
  # real_ip_recursive: bỏ qua các IP trusted trong chain
  # X-Forwarded-For: 1.2.3.4, 10.0.0.1
  # → real IP = 1.2.3.4 (bỏ qua 10.0.0.1 vì là trusted proxy)
```

### 6.2 Rate Limiting và DDoS

Rate limiting tại Nginx không đủ để chống DDoS volumetric:

```
DDoS volumetric: 1 Gbps traffic từ 100,000 IP
  → Nginx bị overwhelm trước khi rate limit có tác dụng
  → Cần: Cloudflare, AWS Shield, Akamai (edge protection)

DDoS application layer (L7): 10,000 IP, mỗi IP 1 req/s
  → limit_req per IP không hiệu quả (mỗi IP dưới limit)
  → Cần: behavioral analysis, CAPTCHA, WAF

Rate limiting hiệu quả cho:
  → Single IP flood (1 IP, nhiều request)
  → Brute-force attack (1 IP, nhiều login attempt)
  → Buggy client (retry loop)
  → Scraping (1 IP, crawl toàn bộ site)
```

