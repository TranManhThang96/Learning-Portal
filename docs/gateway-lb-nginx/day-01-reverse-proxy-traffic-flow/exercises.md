# Day 01 - Exercises: Reverse Proxy & Traffic Flow

> Hoàn thành các bài tập này sau khi đọc `lesson.md`.
> Mỗi bài tập có output mong đợi cụ thể để bạn tự kiểm tra.
> Để giữ đúng khung 2 giờ/ngày: hoàn thành Bài tập 1-4; Bài tập 5-7 là phần nâng cao.

---

## Bài tập 1: Dựng stack cơ bản (Bắt buộc)

### Mục tiêu
Dựng toàn bộ stack từ đầu theo hướng dẫn trong `lesson.md`.

### Các bước

**1.1. Tạo cấu trúc thư mục**

```bash
mkdir -p day-01-lab/nginx
mkdir -p day-01-lab/order-service
mkdir -p day-01-lab/payment-service
cd day-01-lab
```

**1.2. Tạo các file theo nội dung trong lesson.md**

Tạo lần lượt:
- `order-service/server.js`
- `order-service/Dockerfile`
- `payment-service/server.js`
- `payment-service/Dockerfile`
- `nginx/nginx.conf`
- `docker-compose.yml`

**1.3. Khởi động stack**

```bash
docker compose up -d --build
docker compose ps
```

**Kiểm tra output:**
```
NAME                STATUS
nginx               Up
order-service       Up
payment-service     Up
```

**1.4. Chạy các lệnh kiểm tra**

```bash
# Test 1: Health check
curl -s http://localhost:8080/health
# Expected: {"status":"ok"}

# Test 2: Order service
curl -s http://localhost:8080/api/orders/123
# Expected: JSON với "service": "order-service"

# Test 3: Payment service
curl -s http://localhost:8080/api/payments/txn-456
# Expected: JSON với "service": "payment-service"

# Test 4: Unknown path
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/unknown
# Expected: 404
```

**1.5. Kiểm tra header forwarding**

```bash
curl -s http://localhost:8080/api/orders/test | python -m json.tool
```

Xác nhận:
- `x-real-ip` có giá trị (không phải "not-set")
- `x-forwarded-for` có giá trị
- `host` là "localhost"

---

## Bài tập 2: Quan sát access log (Bắt buộc)

### Mục tiêu
Hiểu log format và đọc được thông tin upstream từ access log.

### Các bước

**2.1. Gửi một số requests**

```bash
curl -s http://localhost:8080/api/orders/1 > /dev/null
curl -s http://localhost:8080/api/orders/2 > /dev/null
curl -s http://localhost:8080/api/payments/txn-1 > /dev/null
curl -s http://localhost:8080/unknown > /dev/null
```

**2.2. Xem access log**

```bash
docker compose logs nginx --tail=20
```

**Câu hỏi cần trả lời:**
1. `upstream=` trong log trỏ đến IP và port nào?
2. `upstream_time` và `request_time` khác nhau thế nào?
3. Request đến `/unknown` có `upstream=` không? Tại sao?

**Gợi ý trả lời:**
- `upstream_time`: Thời gian Nginx chờ upstream trả response
- `request_time`: Tổng thời gian từ khi nhận request đến khi gửi xong response về client
- Request đến `/unknown` không có upstream vì Nginx trả response trực tiếp (return 404)

---

## Bài tập 3: Mô phỏng 502 Bad Gateway (Bắt buộc)

### Mục tiêu
Hiểu khi nào xảy ra 502 và cách debug.

### Các bước

**3.1. Stop order-service**

```bash
docker compose stop order-service
```

**3.2. Gửi request đến order-service**

```bash
curl -v http://localhost:8080/api/orders/test 2>&1
```

**Quan sát:**
- HTTP status code là bao nhiêu?
- Response body là gì?
- Nginx error log có ghi gì không?

```bash
docker compose logs nginx 2>&1 | tail -5
```

**3.3. Restart order-service và verify recovery**

```bash
docker compose start order-service
# Chờ 2-3 giây
curl -s http://localhost:8080/api/orders/test
```

**Câu hỏi:** Nginx có tự động recover khi upstream restart không? Tại sao?

---

## Bài tập 4: Trailing slash experiment (Bắt buộc)

### Mục tiêu
Hiểu sự khác biệt giữa `proxy_pass` có và không có trailing slash.

### Các bước

**4.1. Thêm location test vào nginx.conf**

Mở `nginx/nginx.conf`, thêm 2 location blocks mới vào trong `server {}`:

```nginx
# Test: proxy_pass KHÔNG có trailing slash
location /test-no-slash {
    proxy_pass http://order_service;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header X-Real-IP $remote_addr;
}

# Test: proxy_pass CÓ trailing slash
location /test-with-slash/ {
    proxy_pass http://order_service/;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header X-Real-IP $remote_addr;
}
```

**4.2. Reload Nginx config**

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

**4.3. So sánh path nhận được ở upstream**

```bash
# Test 1: Không có trailing slash
curl -s http://localhost:8080/test-no-slash/hello/world
# Upstream nhận path: /test-no-slash/hello/world

# Test 2: Có trailing slash
curl -s http://localhost:8080/test-with-slash/hello/world
# Upstream nhận path: /hello/world
```

Quan sát field `"path"` trong JSON response để xác nhận.

**Kết luận:** Ghi lại sự khác biệt và khi nào nên dùng cách nào.

---

## Bài tập 5: Challenge - Thêm service thứ 3 (Nâng cao)

### Mục tiêu
Tự mình thêm `tracking-service` vào stack mà không xem hướng dẫn.

### Yêu cầu

1. Tạo `tracking-service/server.js` listen trên port 8003
2. Tạo `tracking-service/Dockerfile`
3. Thêm service vào `docker-compose.yml`
4. Thêm upstream `tracking_service` vào `nginx.conf`
5. Thêm location `/api/tracking/` route đến tracking-service
6. Verify: `curl http://localhost:8080/api/tracking/shipment-789` trả về JSON với `"service": "tracking-service"`

### Acceptance criteria

```bash
curl -s http://localhost:8080/api/tracking/shipment-789 | python -m json.tool
# Phải có: "service": "tracking-service"
# Phải có: "x-real-ip" không phải "not-set"
```

---

## Bài tập 6: Challenge - Custom error response (Nâng cao)

### Mục tiêu
Customize error response khi upstream không available.

### Yêu cầu

Khi `order-service` down, thay vì trả về generic 502, Nginx phải trả về:

```json
{
  "error": "order-service temporarily unavailable",
  "code": 502,
  "retry_after": 30
}
```

### Gợi ý

Dùng `error_page` directive và `location @fallback` pattern:

```nginx
location /api/orders/ {
    proxy_pass http://order_service/;
    # ... các config khác ...
    error_page 502 503 504 = @order_fallback;
}

location @order_fallback {
    # Trả về custom JSON
}
```

### Verify

```bash
docker compose stop order-service
curl -s http://localhost:8080/api/orders/test | python -m json.tool
# Phải thấy custom error message
```

---

## Bài tập 7: Challenge - Benchmark cơ bản (Nâng cao)

### Mục tiêu
Đo overhead của Nginx reverse proxy so với direct connection.

### Yêu cầu

**7.1. Expose order-service port tạm thời**

Thêm vào `docker-compose.yml`:
```yaml
order-service:
  ports:
    - "8001:8001"
```

```bash
docker compose up -d
```

**7.2. Benchmark với hey**

```bash
# Cài hey nếu chưa có
# Windows: scoop install hey
# hoặc download binary từ https://github.com/rakyll/hey/releases

# Benchmark direct (bypass Nginx)
hey -n 5000 -c 50 http://localhost:8001/test

# Benchmark qua Nginx
hey -n 5000 -c 50 http://localhost:8080/api/orders/test
```

**7.3. So sánh kết quả**

Ghi lại và so sánh:
- Requests/sec
- p50, p95, p99 latency
- Error rate

**Câu hỏi:** Overhead của Nginx là bao nhiêu % so với direct? Có chấp nhận được không?

**7.4. Dọn dẹp**

Xóa port mapping của order-service sau khi benchmark xong.

---

## Tổng kết

Sau khi hoàn thành tất cả bài tập, bạn đã:

- [ ] Dựng được Nginx reverse proxy với Docker Compose
- [ ] Route traffic đến nhiều backend services theo path
- [ ] Hiểu và verify header forwarding (X-Real-IP, X-Forwarded-For)
- [ ] Debug được lỗi 502 khi upstream down
- [ ] Hiểu trailing slash behavior trong proxy_pass
- [ ] (Nâng cao) Thêm service mới vào stack
- [ ] (Nâng cao) Customize error response
- [ ] (Nâng cao) Benchmark và đo overhead của reverse proxy
