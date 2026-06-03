# Day 7: Exercises — Mini-project Linux + Networking + Automation

---

## Part 1: Deploy & Configure (Easy)

### Context

Bạn vừa nhận task deploy một HTTP API service lên server development. Service cần chạy ổn định, tự restart khi crash, và có endpoint health check.

### Yêu cầu

1. Build HTTP service (Go hoặc Node.js) với 3 endpoints: `/health`, `/api/info`, `/api/slow`.
2. Tạo systemd unit file (hoặc chạy trực tiếp nếu không có root).
3. Verify service hoạt động đúng.
4. Test graceful shutdown (SIGTERM).

### Expected Outcome

- Service chạy trên port 8080.
- `/health` trả về JSON: `{"status":"healthy","timestamp":"...","uptime":"..."}`.
- `/api/info` trả về service metadata.
- Service dừng gracefully khi nhận SIGTERM (log "graceful shutdown").

### Hint

- Go: `go build -o demo-api server.go && ./demo-api`
- Node.js: `node server.js`
- Test SIGTERM: `kill -SIGTERM $(pgrep -f demo-api)`
- Xem log shutdown: `journalctl -u demo-api -n 5` hoặc output terminal.

### Acceptance Criteria

- [ ] Service start thành công, log PID và port
- [ ] `curl http://localhost:8080/health` trả về 200 + JSON
- [ ] `curl http://localhost:8080/api/info` trả về service info
- [ ] Gửi SIGTERM → service log "graceful shutdown" và exit
- [ ] Nếu dùng systemd: `systemctl status demo-api` → active (running)

### Bonus Challenge

Thêm endpoint `/api/ready` trả về trạng thái readiness (kiểm tra dependencies). Phân biệt liveness (`/health`) vs readiness (`/api/ready`).

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
# Part 1 Solution

set -euo pipefail
WORKDIR="/tmp/mini-project-ex"
mkdir -p "$WORKDIR" && cd "$WORKDIR"

# Option A: Node.js (không cần compile)
cat > server.js << 'NODEJS'
const http = require('http');
const os = require('os');
const PORT = process.env.PORT || 8080;
const startTime = Date.now();

function uptime() {
  const s = Math.floor((Date.now() - startTime) / 1000);
  return `${Math.floor(s/3600)}h${Math.floor((s%3600)/60)}m${s%60}s`;
}

const routes = {
  '/health': (req, res) => {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({status:'healthy', timestamp: new Date().toISOString(), uptime: uptime()}));
  },
  '/api/info': (req, res) => {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({service:'demo-api', version:'1.0.0', host: os.hostname(), pid: process.pid}));
  },
  '/api/slow': (req, res) => {
    setTimeout(() => {
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({message: 'slow response completed'}));
    }, 5000);
  },
  '/api/ready': (req, res) => {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({ready: true, checks: {db: 'ok', cache: 'ok'}}));
  }
};

const server = http.createServer((req, res) => {
  const handler = routes[req.url];
  if (handler) { handler(req, res); }
  else { res.writeHead(404); res.end(JSON.stringify({error:'not found'})); }
});

function shutdown(sig) {
  console.log(`Received ${sig}, graceful shutdown...`);
  server.close(() => { console.log('Server stopped gracefully'); process.exit(0); });
  setTimeout(() => { process.exit(1); }, 30000);
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

server.listen(PORT, () => console.log(`Starting server on port ${PORT} (PID: ${process.pid})`));
NODEJS

# Start service
node server.js &
SERVER_PID=$!
sleep 1

# Test endpoints
echo "=== Health Check ==="
curl -s http://localhost:8080/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8080/health

echo ""
echo "=== Info Endpoint ==="
curl -s http://localhost:8080/api/info | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8080/api/info

echo ""
echo "=== Readiness (Bonus) ==="
curl -s http://localhost:8080/api/ready | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8080/api/ready

echo ""
echo "=== Test Graceful Shutdown ==="
kill -SIGTERM $SERVER_PID
wait $SERVER_PID 2>/dev/null || true
echo "Server exited"

echo ""
echo "Cleanup: rm -rf $WORKDIR"
```

</details>

---

## Part 2: Failure Simulation & Debug (Medium)

### Context

Service đã deploy thành công. Bây giờ bạn cần mô phỏng 4 loại lỗi production phổ biến và chứng minh khả năng debug bằng Linux tools.

### Yêu cầu

Với mỗi loại lỗi bên dưới:
1. **Mô phỏng** lỗi.
2. **Phát hiện** bằng tool phù hợp (không đoán, phải dùng data).
3. **Xác định** root cause.
4. **Fix** và verify recovery.

Các lỗi cần mô phỏng:

| # | Lỗi | Mô phỏng bằng |
|---|------|---------------|
| 1 | Process crash | `kill -9` |
| 2 | Port conflict | Chạy process khác chiếm port 8080 |
| 3 | DNS failure | Sửa `/etc/hosts` hoặc `resolv.conf` |
| 4 | Slow response | Gọi `/api/slow` endpoint |

### Expected Outcome

Cho mỗi lỗi, ghi lại:
- Command mô phỏng
- Dấu hiệu nhận biết (symptom)
- Debug commands đã dùng
- Root cause xác định
- Fix command
- Verification

### Hint

- Process: `ps aux | grep demo-api`, `ss -tlnp | grep 8080`
- Port: `ss -tlnp`, `lsof -i :8080`
- DNS: `dig`, `nslookup`, `curl -v`
- Performance: `time curl`, `top`, `strace`

### Acceptance Criteria

- [ ] Mô phỏng thành công 4 loại lỗi
- [ ] Mỗi lỗi có ít nhất 2 debug commands
- [ ] Root cause chính xác cho mỗi lỗi
- [ ] Service recovery thành công sau fix
- [ ] Health check script phát hiện được ít nhất 3/4 lỗi

### Bonus Challenge

Tạo script `simulate-failure.sh` nhận tham số loại lỗi và tự động mô phỏng:
```bash
./simulate-failure.sh crash
./simulate-failure.sh port-conflict
./simulate-failure.sh dns
./simulate-failure.sh slow
```

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
# Part 2 Solution: Failure Simulation & Debug

set -euo pipefail

WORKDIR="/tmp/mini-project-ex"
cd "$WORKDIR"

# Start service
node server.js &
sleep 1
echo "Service started (PID: $!)"

echo ""
echo "=========================================="
echo "FAILURE 1: Process Crash"
echo "=========================================="

echo "--- Mô phỏng ---"
kill -9 $(pgrep -f "node server.js" | head -1)
echo "Killed process with SIGKILL"

echo "--- Phát hiện ---"
echo "Process check:"
pgrep -f "node server.js" || echo "  → Process NOT found"
echo "Port check:"
ss -tlnp | grep :8080 || echo "  → Port 8080 NOT listening"
echo "HTTP check:"
curl -s --connect-timeout 2 http://localhost:8080/health || echo "  → Connection refused"

echo "--- Root Cause ---"
echo "  Process terminated by SIGKILL (unrecoverable signal)"

echo "--- Fix ---"
node server.js &
sleep 1
echo "Service restarted (PID: $!)"

echo "--- Verify ---"
curl -s http://localhost:8080/health
echo ""

echo ""
echo "=========================================="
echo "FAILURE 2: Port Conflict"
echo "=========================================="

echo "--- Mô phỏng ---"
kill $(pgrep -f "node server.js" | head -1) 2>/dev/null; sleep 1
python3 -c "
import http.server, socketserver
with socketserver.TCPServer(('', 8080), http.server.SimpleHTTPRequestHandler) as s:
    print('Blocking port 8080...')
    s.handle_request()
" &
BLOCKER=$!
sleep 1

echo "--- Phát hiện ---"
echo "Try to start service:"
node server.js 2>&1 &
NEW_PID=$!
sleep 2
echo "Port occupant:"
ss -tlnp | grep :8080

echo "--- Root Cause ---"
echo "  Port 8080 already bound by python3 (PID: $BLOCKER)"

echo "--- Fix ---"
kill $BLOCKER 2>/dev/null; wait $BLOCKER 2>/dev/null || true
kill $NEW_PID 2>/dev/null; wait $NEW_PID 2>/dev/null || true
sleep 1
node server.js &
sleep 1

echo "--- Verify ---"
curl -s http://localhost:8080/health
echo ""

echo ""
echo "=========================================="
echo "FAILURE 3: DNS Failure"
echo "=========================================="

echo "--- Mô phỏng ---"
echo "Attempting DNS lookup of non-existent domain:"
dig nonexistent-service-12345.internal +short 2>&1 || true

echo "--- Phát hiện ---"
echo "DNS resolution test:"
dig google.com +short | head -1
echo "curl error:"
curl -s --connect-timeout 3 http://fake-service-xyz.local/api 2>&1 || echo "  → DNS resolution failed"

echo "--- Root Cause ---"
echo "  DNS cannot resolve hostname (no A/AAAA record)"
echo "--- Debug ---"
echo "DNS config:"
cat /etc/resolv.conf 2>/dev/null | head -3 || echo "  (resolv.conf not accessible)"
echo "--- Fix ---"
echo "  Add DNS entry or fix resolv.conf"

echo ""
echo "=========================================="
echo "FAILURE 4: Slow Response"
echo "=========================================="

echo "--- Mô phỏng ---"
echo "Calling /api/slow (5s delay):"
time curl -s http://localhost:8080/api/slow
echo ""

echo "--- Phát hiện ---"
echo "Latency measurement:"
for i in 1 2 3; do
    curl -o /dev/null -s -w "  Request $i: %{time_total}s (HTTP %{http_code})\n" http://localhost:8080/health
done

echo "--- Root Cause ---"
echo "  Application-level delay (sleep 5s in handler)"
echo "--- Debug ---"
echo "System resources during slow request:"
echo "  CPU/Memory: $(top -b -n 1 | head -4 | tail -2)" 2>/dev/null || echo "  (top not available)"
echo "  Connections:"
ss -tnp | grep :8080 | wc -l

echo ""
echo "=========================================="
echo "ALL FAILURES SIMULATED AND DEBUGGED"
echo "=========================================="

# Cleanup
kill $(pgrep -f "node server.js") 2>/dev/null || true
echo "Cleanup: rm -rf $WORKDIR"
```

### Bonus: simulate-failure.sh

```bash
#!/bin/bash
# simulate-failure.sh — Simulate production failures
set -euo pipefail

case "${1:-help}" in
    crash)
        echo "Simulating process crash..."
        kill -9 $(pgrep -f "demo-api\|node server" | head -1) 2>/dev/null
        echo "Process killed. Run health-check.sh to detect."
        ;;
    port-conflict)
        echo "Simulating port conflict on 8080..."
        python3 -m http.server 8080 &
        echo "Port 8080 blocked by PID $!. Try restarting service."
        ;;
    dns)
        echo "Simulating DNS failure..."
        echo "Test: curl http://nonexistent-host-12345.local/api"
        curl -s --connect-timeout 3 http://nonexistent-host-12345.local/api 2>&1 || true
        ;;
    slow)
        echo "Simulating slow response..."
        time curl -s http://localhost:8080/api/slow
        ;;
    help|*)
        echo "Usage: $0 {crash|port-conflict|dns|slow}"
        ;;
esac
```

</details>

---

## Part 3: Production Runbook & Automation (Hard)

### Context

Service đã hoạt động ổn định. Team lead yêu cầu bạn tạo bộ tài liệu production-ready:
1. Health check script chạy tự động (cron hoặc loop).
2. Runbook cho top 4 loại incident.
3. Auto-recovery script cho các lỗi phổ biến.

### Yêu cầu

1. **Health check đầy đủ** — script kiểm tra 4 tầng: process, port, HTTP, disk.
2. **Auto-recovery** — nếu health check fail, tự động retry → restart service → alert.
3. **Runbook** — cho 4 loại lỗi đã mô phỏng ở Part 2, theo format chuẩn.
4. **Monitoring loop** — script chạy continuous, check mỗi 30 giây, ghi log.
5. **Alert** — khi service unhealthy 3 lần liên tiếp, ghi alert vào file (mô phỏng PagerDuty/Slack).

### Expected Outcome

- `health-check.sh` kiểm tra 4 tầng.
- `auto-recovery.sh` tự restart service khi lỗi.
- `monitor.sh` chạy continuous loop + alert.
- `runbook.md` có 4 runbook theo format chuẩn.
- Alert log file khi có incident.

### Hint

- Monitoring loop: `while true; do ./health-check.sh || handle_failure; sleep 30; done`
- Alert: `echo "[ALERT] $(date) Service unhealthy" >> /tmp/alerts.log`
- Auto-recovery: kiểm tra exit code health check → `systemctl restart` nếu fail.
- Runbook format: Symptom → Triage → Root Cause → Fix → Verify.

### Acceptance Criteria

- [ ] Health check script kiểm tra 4 tầng với exit code đúng
- [ ] Auto-recovery tự restart sau 3 lần fail liên tiếp
- [ ] Monitor loop chạy được ít nhất 2 phút không lỗi
- [ ] Alert log ghi nhận khi service down
- [ ] Runbook cover 4 loại incident với commands cụ thể
- [ ] Tất cả scripts có `set -euo pipefail` và error handling

### Bonus Challenge

1. Thêm metric collection: ghi response time vào CSV file, tạo mini dashboard bằng `awk`.
2. Thêm log rotation cho alert log (giữ tối đa 1000 dòng).
3. Viết `postmortem-template.md` theo blameless postmortem format.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
# Part 3 Solution: Auto-recovery monitor

cat > /tmp/mini-project-ex/monitor.sh << 'MONITOR'
#!/bin/bash
set -euo pipefail

SERVICE_URL="http://localhost:8080"
ALERT_LOG="/tmp/alerts.log"
METRICS_CSV="/tmp/metrics.csv"
FAIL_COUNT=0
MAX_FAIL=3
CHECK_INTERVAL=30

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

alert() {
    local msg="$1"
    log "ALERT: $msg" | tee -a "$ALERT_LOG"
}

check_service() {
    local start_ms=$(($(date +%s%N)/1000000))
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout 5 --max-time 10 \
        "${SERVICE_URL}/health" 2>/dev/null) || http_code="000"
    local end_ms=$(($(date +%s%N)/1000000))
    local duration=$((end_ms - start_ms))

    # Record metric
    echo "$(date -Iseconds),$http_code,$duration" >> "$METRICS_CSV"

    if [ "$http_code" = "200" ]; then
        if [ "$duration" -gt 2000 ]; then
            log "WARN: Slow response ${duration}ms"
        fi
        return 0
    fi
    return 1
}

restart_service() {
    log "Attempting service restart..."
    if command -v systemctl &>/dev/null; then
        sudo systemctl restart demo-api 2>/dev/null && return 0
    fi
    # Fallback: direct restart
    pkill -f "node server.js" 2>/dev/null || true
    sleep 2
    cd /tmp/mini-project-ex
    nohup node server.js > /tmp/demo-api.log 2>&1 &
    sleep 2
    check_service
}

# Initialize metrics
echo "timestamp,http_code,duration_ms" > "$METRICS_CSV"

log "Monitor started (interval: ${CHECK_INTERVAL}s, max_fail: ${MAX_FAIL})"

while true; do
    if check_service; then
        if [ "$FAIL_COUNT" -gt 0 ]; then
            log "Service recovered after $FAIL_COUNT failures"
            FAIL_COUNT=0
        fi
        log "OK"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        log "FAIL ($FAIL_COUNT/$MAX_FAIL)"

        if [ "$FAIL_COUNT" -ge "$MAX_FAIL" ]; then
            alert "Service unhealthy $FAIL_COUNT times, attempting restart"
            if restart_service; then
                alert "Service restarted successfully"
                FAIL_COUNT=0
            else
                alert "CRITICAL: Service restart FAILED - manual intervention required"
            fi
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
MONITOR
chmod +x /tmp/mini-project-ex/monitor.sh

# Log rotation helper
cat > /tmp/mini-project-ex/rotate-logs.sh << 'ROTATE'
#!/bin/bash
LOG_FILE="${1:-/tmp/alerts.log}"
MAX_LINES=1000

if [ -f "$LOG_FILE" ]; then
    LINE_COUNT=$(wc -l < "$LOG_FILE")
    if [ "$LINE_COUNT" -gt "$MAX_LINES" ]; then
        tail -n "$MAX_LINES" "$LOG_FILE" > "${LOG_FILE}.tmp"
        mv "${LOG_FILE}.tmp" "$LOG_FILE"
        echo "Rotated $LOG_FILE: $LINE_COUNT → $MAX_LINES lines"
    fi
fi
ROTATE
chmod +x /tmp/mini-project-ex/rotate-logs.sh

# Mini metrics dashboard
cat > /tmp/mini-project-ex/dashboard.sh << 'DASHBOARD'
#!/bin/bash
CSV="${1:-/tmp/metrics.csv}"

if [ ! -f "$CSV" ] || [ $(wc -l < "$CSV") -le 1 ]; then
    echo "No metrics data yet"
    exit 0
fi

echo "=== Service Metrics Dashboard ==="
echo ""
echo "Total checks: $(tail -n +2 "$CSV" | wc -l)"
echo "Success (200): $(tail -n +2 "$CSV" | awk -F, '$2==200' | wc -l)"
echo "Failed: $(tail -n +2 "$CSV" | awk -F, '$2!=200' | wc -l)"
echo ""
echo "Response time (ms):"
tail -n +2 "$CSV" | awk -F, '$2==200 {
    sum+=$3; count++; 
    if($3>max) max=$3; 
    if(min=="" || $3<min) min=$3
} END {
    if(count>0) printf "  avg: %.0f | min: %d | max: %d | count: %d\n", sum/count, min, max, count
    else print "  no successful requests"
}'
echo ""
echo "Last 5 checks:"
tail -5 "$CSV" | awk -F, 'NR>0 {printf "  %s | HTTP %s | %sms\n", $1, $2, $3}'
DASHBOARD
chmod +x /tmp/mini-project-ex/dashboard.sh

echo "Created: monitor.sh, rotate-logs.sh, dashboard.sh"
echo ""
echo "Usage:"
echo "  ./monitor.sh          # Run continuous monitoring"
echo "  ./rotate-logs.sh      # Rotate alert logs"
echo "  ./dashboard.sh        # View metrics dashboard"
echo ""
echo "Cleanup: rm -rf /tmp/mini-project-ex /tmp/alerts.log /tmp/metrics.csv"
```

### Postmortem Template (Bonus)

```markdown
# Postmortem: [Incident Title]

## Metadata
- **Date**: YYYY-MM-DD
- **Duration**: X hours Y minutes
- **Severity**: P1/P2/P3
- **Author**: [Name]
- **Reviewers**: [Names]

## Summary
One paragraph describing what happened and the impact.

## Impact
- Users affected: X
- Revenue impact: $Y (if applicable)
- SLA impact: Z minutes of downtime

## Timeline (all times UTC)
| Time | Event |
|------|-------|
| HH:MM | First alert fired |
| HH:MM | On-call acknowledged |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Service fully recovered |

## Root Cause
Technical explanation of what caused the incident.

## Resolution
What was done to fix the immediate problem.

## Lessons Learned
### What went well
- ...

### What went poorly
- ...

### Where we got lucky
- ...

## Action Items
| Action | Owner | Priority | Deadline |
|--------|-------|----------|----------|
| ... | ... | P1/P2 | YYYY-MM-DD |

## Prevention
What we will do to prevent similar incidents.
```

</details>

---

## Tổng kết

| Part | Thời gian | Kỹ năng |
|------|-----------|---------|
| Part 1: Deploy & Configure | 25 phút | Service deployment, systemd, graceful shutdown |
| Part 2: Failure Simulation | 35 phút | Debugging, Linux tools, root cause analysis |
| Part 3: Runbook & Automation | 45 phút | Monitoring, auto-recovery, documentation |
| **Tổng** | **~105 phút** | Tổng hợp toàn bộ Phase 1 |

