# Day 3: Bài tập — Linux Networking Fundamentals

---

## Bài 1: Easy — DNS Debugging

### Context
Bạn là on-call engineer. User report rằng `api.internal.company.com` không truy cập được từ một server cụ thể, nhưng từ server khác thì vẫn bình thường.

### Yêu cầu
1. Sử dụng `dig`, `nslookup`, `host` để kiểm tra DNS resolution cho bất kỳ domain nào (ví dụ: `google.com`, `github.com`).
2. So sánh kết quả khi query DNS servers khác nhau (`8.8.8.8`, `1.1.1.1`, local resolver).
3. Kiểm tra TTL của DNS records.
4. Trace full DNS resolution path bằng `dig +trace`.
5. Đo thời gian DNS resolution.

### Expected Outcome
- Output từ 3 tools khác nhau cho cùng domain.
- So sánh TTL và IP trả về từ các DNS servers.
- Hiểu được DNS resolution path.

### Hint
- `dig +short` cho IP nhanh, `dig +trace` cho full path.
- `time dig domain` để đo thời gian.
- So sánh `dig @8.8.8.8` vs `dig @1.1.1.1` — kết quả có thể khác nhau nếu DNS propagation chưa hoàn thành.

### Acceptance Criteria
- [ ] Dùng ít nhất 3 DNS tools thành công.
- [ ] So sánh kết quả từ 2+ DNS servers.
- [ ] Giải thích TTL và ý nghĩa thực tế.
- [ ] `dig +trace` chạy thành công và giải thích output.

### Bonus Challenge
- Viết script kiểm tra DNS resolution time cho list 10 domains và highlight domain nào resolve chậm nhất.

<details>
<summary>Solution / Reference</summary>

```bash
#!/bin/bash
# dns-debug.sh

DOMAIN="${1:-github.com}"
echo "=== DNS Debugging: $DOMAIN ==="
echo ""

echo "--- 1. dig (detailed) ---"
dig "$DOMAIN" +noall +answer +stats
echo ""

echo "--- 2. nslookup ---"
nslookup "$DOMAIN"
echo ""

echo "--- 3. host ---"
host "$DOMAIN"
echo ""

echo "--- 4. Compare DNS servers ---"
echo "Google (8.8.8.8):"
dig @8.8.8.8 "$DOMAIN" +short
echo "Cloudflare (1.1.1.1):"
dig @1.1.1.1 "$DOMAIN" +short
echo "Local resolver:"
dig "$DOMAIN" +short
echo ""

echo "--- 5. TTL ---"
dig "$DOMAIN" +noall +answer | awk '{print "Record:", $1, "TTL:", $2, "Type:", $4, "Value:", $5}'
echo ""

echo "--- 6. Resolution time ---"
for i in 1 2 3; do
  TIME=$( { time dig "$DOMAIN" +short > /dev/null; } 2>&1 | grep real | awk '{print $2}')
  echo "  Attempt $i: $TIME"
done
echo ""

echo "--- 7. Trace (first 20 lines) ---"
dig +trace "$DOMAIN" | head -20
```

```bash
# Bonus: Check 10 domains
#!/bin/bash
DOMAINS="google.com github.com stackoverflow.com aws.amazon.com cloudflare.com
         reddit.com npm.js.org kubernetes.io grafana.com prometheus.io"

echo "Domain                    | Resolve Time | IP"
echo "--------------------------|-------------|----"
for d in $DOMAINS; do
  START=$(date +%s%N)
  IP=$(dig +short "$d" | head -1)
  END=$(date +%s%N)
  MS=$(( (END - START) / 1000000 ))
  printf "%-26s| %6s ms    | %s\n" "$d" "$MS" "$IP"
done | sort -t'|' -k2 -n -r
```

</details>

---

## Bài 2: Medium — TCP Connection Analysis

### Context
Bạn quản lý một web service (HTTP) chạy trên port 8080. Gần đây, service bắt đầu từ chối connections mới. Bạn cần phân tích TCP connection states để tìm root cause.

### Yêu cầu
1. Tạo một HTTP server đơn giản (Python hoặc Node.js) trên port 8080.
2. Tạo nhiều connections đến server bằng `curl` và giữ chúng open.
3. Dùng `ss` để phân tích connection states (ESTABLISHED, TIME_WAIT, CLOSE_WAIT).
4. Dùng `curl -w` để đo timing breakdown (DNS, connect, TLS, TTFB, total).
5. Mô phỏng connection timeout vs connection refused và phân biệt chúng.

### Expected Outcome
- Output `ss` cho thấy các connection states.
- Timing breakdown cho thấy bottleneck ở đâu.
- Phân biệt rõ connection refused vs timeout trong output.

### Hint
- `ss -tn state established | wc -l` đếm ESTABLISHED connections.
- `ss -s` cho summary tất cả states.
- Python one-liner cho HTTP server: `python3 -m http.server 8080`.
- Dùng `curl --connect-timeout 3` cho timeout test.

### Acceptance Criteria
- [ ] Server chạy và nhận connections thành công.
- [ ] Dùng `ss` phân tích ít nhất 3 connection states.
- [ ] Timing breakdown identify được từng phase.
- [ ] Phân biệt rõ connection refused vs timeout (khác nhau thế nào).
- [ ] Giải thích scenario nào gây nhiều TIME_WAIT.

### Bonus Challenge
- Viết script monitor connection states mỗi 5 giây, output dạng time-series.
- Dùng `tcpdump` capture TCP handshake và giải thích từng packet.

<details>
<summary>Solution / Reference</summary>

```bash
#!/bin/bash
# connection-analysis.sh

echo "=== Step 1: Start test server ==="
python3 -m http.server 8080 &
SERVER_PID=$!
sleep 1

echo "=== Step 2: Generate connections ==="
for i in $(seq 1 20); do
  curl -s http://localhost:8080/ > /dev/null &
done
sleep 1

echo ""
echo "=== Step 3: Connection state analysis ==="
echo "--- Summary ---"
ss -s | grep -A2 "TCP:"
echo ""
echo "--- Detailed by state ---"
for state in established time-wait close-wait fin-wait-1 fin-wait-2 syn-sent listen; do
  COUNT=$(ss -tn state "$state" 2>/dev/null | tail -n +2 | wc -l)
  printf "  %-15s: %d\n" "$state" "$COUNT"
done

echo ""
echo "=== Step 4: Timing breakdown ==="
curl -o /dev/null -s -w \
"  DNS Lookup:   %{time_namelookup}s
  TCP Connect:  %{time_connect}s
  TLS Handshake:%{time_appconnect}s
  TTFB:         %{time_starttransfer}s
  Total:        %{time_total}s
  HTTP Code:    %{http_code}
  Size:         %{size_download} bytes
" http://localhost:8080/

echo ""
echo "=== Step 5: Connection Refused vs Timeout ==="
echo "--- Connection Refused (port not listening) ---"
curl -v --connect-timeout 3 http://localhost:9999/ 2>&1 | grep -E "Trying|Connected|refused|timed out"

echo ""
echo "--- Connection Timeout (unreachable IP) ---"
curl -v --connect-timeout 3 http://192.0.2.1:8080/ 2>&1 | grep -E "Trying|Connected|refused|timed out"

echo ""
echo "=== Cleanup ==="
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
echo "Done"
```

```bash
# Bonus: Connection state monitor
#!/bin/bash
echo "Time       | ESTAB | TIME_WAIT | CLOSE_WAIT | LISTEN"
echo "-----------|-------|-----------|------------|-------"
while true; do
  ESTAB=$(ss -tn state established | tail -n +2 | wc -l)
  TW=$(ss -tn state time-wait | tail -n +2 | wc -l)
  CW=$(ss -tn state close-wait | tail -n +2 | wc -l)
  LIS=$(ss -tn state listening | tail -n +2 | wc -l)
  printf "%s | %5d | %9d | %10d | %6d\n" "$(date +%H:%M:%S)" "$ESTAB" "$TW" "$CW" "$LIS"
  sleep 5
done
```

</details>

---

## Bài 3: Hard — Network Debugging Scenario Simulation

### Context
Bạn vận hành một microservice platform gồm 3 services:
- **API Gateway** (port 8080) → gọi **User Service** (port 8081)
- **User Service** (port 8081) → gọi **Database** (port 5432)

Bạn cần simulate và debug 4 network failure scenarios phổ biến.

### Yêu cầu

**Part 1: Setup 3-tier service stack (đơn giản)**
Dùng Python hoặc Node.js tạo 2 HTTP servers (API Gateway proxy đến User Service). Dùng `curl` làm client.

**Part 2: Simulate và debug 4 scenarios**

1. **DNS failure**: User Service hostname không resolve được → API Gateway nhận lỗi gì? Client nhận lỗi gì?

2. **Connection timeout**: User Service chạy nhưng không respond (simulate bằng `iptables DROP` hoặc firewall rule) → phân biệt với connection refused.

3. **Slow response**: User Service trả response sau 10s → API Gateway timeout nếu set 5s → cascading failure.

4. **Ephemeral port exhaustion**: Tạo nhiều short-lived connections → monitor ephemeral port usage → xác định threshold.

**Part 3: Viết runbook**
Cho mỗi scenario, viết runbook ngắn gọn: symptom, debug steps, fix.

### Expected Outcome
- Code cho 2 services chạy được.
- Debug output cho mỗi scenario.
- Runbook document cho 4 scenarios.

### Hint
- Python proxy đơn giản: `requests.get("http://localhost:8081")`.
- Simulate DROP: `iptables -A INPUT -p tcp --dport 8081 -j DROP` (cần sudo, cẩn thận!).
- Hoặc đơn giản hơn: stop User Service → connection refused.
- Ephemeral port check: `ss -s | grep timewait`.

### Acceptance Criteria
- [ ] 2 services chạy và communicate được.
- [ ] Ít nhất 3/4 scenarios simulated và debugged.
- [ ] Dùng networking tools (`ss`, `curl -v`, `dig`, `tcpdump`) trong debug.
- [ ] Runbook cho mỗi scenario có: symptom → diagnosis → fix.
- [ ] Cleanup tất cả processes và firewall rules sau test.

### Bonus Challenge
- Thêm load balancing: run 2 instances của User Service, API Gateway round-robin giữa chúng. Một instance die → observe behavior.
- Dùng `tcpdump` capture packets trong mỗi scenario và giải thích SYN/RST/FIN patterns.

<details>
<summary>Solution / Reference</summary>

**Simplified 2-service setup:**

```python
# user_service.py (port 8081)
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, time, os

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'ok')
            return
        
        if self.path == '/slow':
            time.sleep(10)  # Simulate slow query
        
        self.send_response(200)
        self.end_headers()
        response = {"user": "john", "pid": os.getpid()}
        self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        print(f"[UserService] {args[0]}")

HTTPServer(('', 8081), Handler).serve_forever()
```

```python
# api_gateway.py (port 8080)
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, json, os

USER_SERVICE = os.environ.get('USER_SERVICE_URL', 'http://localhost:8081')

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            req = urllib.request.Request(f"{USER_SERVICE}{self.path}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.URLError as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Upstream error: {e}".encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode())
    
    def log_message(self, format, *args):
        print(f"[Gateway] {args[0]}")

HTTPServer(('', 8080), Handler).serve_forever()
```

**Runbook template:**

```markdown
## Scenario: Connection Timeout to Upstream Service

### Symptom
- API Gateway returns 502/504 after timeout
- curl -v shows: "Connection timed out"
- No RST packet (unlike connection refused)

### Diagnosis
1. Check if upstream is running: `ss -tlnp | grep 8081`
2. Check network path: `ping <upstream_ip>`
3. Check firewall: `iptables -L -n | grep 8081`
4. Capture packets: `tcpdump -i any port 8081 -nn`
   - If SYN sent but no SYN-ACK → firewall DROP or host down
   - If SYN-ACK received → service running but slow

### Fix
- If firewall: `iptables -D INPUT -p tcp --dport 8081 -j DROP`
- If service down: restart service
- If network: check routing, VPC configs
- Temporary: increase timeout or add circuit breaker
```

</details>

---

## Tổng kết thời gian

| Bài | Độ khó | Thời gian ước tính |
|-----|--------|-------------------|
| Bài 1 | Easy | 20 phút |
| Bài 2 | Medium | 40 phút |
| Bài 3 | Hard | 60-90 phút |

