# Day 7: Mini-project — Linux + Networking + Automation

## 1. Mục tiêu bài học

Sau mini-project này, bạn sẽ:

1. **Deploy được** một HTTP service local và quản lý bằng systemd.
2. **Viết được** health check script tự động phát hiện service lỗi.
3. **Mô phỏng và debug được** 4 loại lỗi production phổ biến: process crash, port conflict, DNS failure, slow response.
4. **Viết được** runbook ngắn gọn cho từng loại lỗi.
5. **Tổng hợp được** kiến thức Phase 1 (Day 1-6) vào một deliverable hoàn chỉnh.

---

## 2. Bối cảnh & Động lực

### Vì sao cần mini-project?

Bạn đã học 6 ngày lý thuyết và bài tập riêng lẻ. Mini-project này **kết nối tất cả** lại:

```
Day 1: DevOps mindset     → Tư duy "mọi thứ phải observable và automated"
Day 2: Process & systemd  → Quản lý service lifecycle
Day 3: Networking          → Debug network issues
Day 4: Performance tools   → Xác định bottleneck
Day 5: Bash automation     → Script health check, automation
Day 6: Git workflow        → Version và release management
```

### Scenario thực tế

Bạn là DevOps engineer vừa nhận task: deploy một API service lên server, đảm bảo:
- Service tự khởi động khi server reboot
- Có monitoring/health check
- Team có runbook để debug khi service gặp vấn đề
- Mọi thứ được version control

Đây chính xác là công việc hàng ngày của DevOps/SRE engineer.

---

## 3. Kiến thức nền tảng

| Day | Kiến thức | Áp dụng trong project |
|-----|-----------|----------------------|
| Day 2 | Process, signal, systemd | Tạo systemd unit, xử lý SIGTERM |
| Day 3 | TCP/IP, DNS, curl, ss | Debug network issues |
| Day 4 | USE/RED method, top, strace | Xác định bottleneck |
| Day 5 | Bash strict mode, trap, automation | Health check script |
| Day 6 | Git workflow | Version control cho project |

---

## 4. Deep Dive

```
┌──────────────────────────────────────────────────┐
│                    Linux Server                   │
│                                                   │
│  ┌─────────────┐    ┌──────────────────────────┐ │
│  │  systemd     │    │   HTTP Service            │ │
│  │              │───▶│   Port 8080               │ │
│  │  manage      │    │                           │ │
│  │  lifecycle   │    │   GET /health → 200       │ │
│  │              │    │   GET /api/info → JSON    │ │
│  │  auto-       │    │   GET /api/slow → delay   │ │
│  │  restart     │    │                           │ │
│  └─────────────┘    └──────────────────────────┘ │
│         ▲                       ▲                 │
│         │                       │                 │
│  ┌──────┴───────┐    ┌─────────┴──────────────┐ │
│  │ health-      │    │  Failure Scenarios       │ │
│  │ check.sh     │    │                          │ │
│  │              │    │  1. Process crash         │ │
│  │ curl /health │    │  2. Port conflict         │ │
│  │ every 30s    │    │  3. DNS failure           │ │
│  │ alert if     │    │  4. Slow response         │ │
│  │ unhealthy    │    └──────────────────────────┘ │
│  └──────────────┘                                 │
│                                                   │
│  ┌──────────────────────────────────────────────┐ │
│  │ Debugging Toolbox                             │ │
│  │ ps, ss, curl, dig, top, strace, journalctl   │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### Luồng vận hành chính

1. `systemd` start service, giữ PID, nhận exit code và quyết định restart theo `Restart=on-failure`.
2. Service bind port `8080`, trả `/health` để health check có tín hiệu application-level.
3. `health-check.sh` kiểm tra theo nhiều lớp: process, port, HTTP response, disk pressure.
4. Khi có lỗi, người vận hành dùng `journalctl`, `ss`, `curl`, `dig`, `top`, `strace` để thu hẹp nguyên nhân trước khi restart hoặc đổi cấu hình.

### Failure modes cần quan sát

| Failure mode | Dấu hiệu | Component liên quan |
|--------------|----------|---------------------|
| Process crash | PID biến mất, systemd restart loop | app, systemd |
| Port conflict | `bind: address already in use` | socket, process khác |
| DNS failure | `Could not resolve host` | resolver, `/etc/resolv.conf`, upstream DNS |
| Slow response | `/api/slow` hoặc `/health` vượt timeout | app, CPU, disk, dependency |
| Bad shutdown | request bị cắt ngang khi deploy/restart | signal handling, timeout |

---

## 5. Trade-offs & Best Practices ⭐

### systemd, container hay Kubernetes?

| Scenario | Recommendation | Lý do |
|----------|----------------|-------|
| Startup nhỏ, một vài VM | `systemd` + script health check | Ít moving parts, debug trực tiếp, chi phí thấp |
| Mid-size company | Container + managed deploy runner hoặc lightweight orchestrator | Đóng gói nhất quán hơn, vẫn chưa cần full Kubernetes cho mọi service |
| Enterprise | Kubernetes hoặc platform chuẩn hóa | Cần RBAC, audit, rollout, policy, multi-team ownership |
| High-traffic system | Kubernetes + probes + autoscaling + observability | Cần self-healing, rollout an toàn, scale ngang và giảm blast radius |

### Best practices trong project này

- Health check nên có timeout ngắn và exit code rõ ràng; script treo còn nguy hiểm hơn service lỗi.
- `Restart=on-failure` phù hợp cho process crash, nhưng không chữa được config sai hoặc dependency down.
- Runbook phải bắt đầu bằng triage nhanh, không bắt đầu bằng "restart service" nếu chưa biết blast radius.
- Log nên đi ra stdout/journald trước; đừng ghi file tùy tiện nếu chưa có rotation.
- Port, user chạy service, working directory và env file phải explicit để tránh khác biệt giữa shell cá nhân và service runtime.

### Anti-patterns cần tránh

- Chạy service bằng `nohup` hoặc `screen` rồi coi đó là production deployment.
- Health check chỉ kiểm tra PID sống, bỏ qua HTTP response và latency.
- Dùng `kill -9` mặc định, làm mất graceful shutdown và khiến request đang xử lý bị cắt.
- Sửa trực tiếp file production mà không lưu vào Git hoặc không có rollback note.

---

## 6. Performance & Scalability ⭐

### Performance implications

- Health check quá dày có thể tạo load giả; với service local, 10-30 giây/lần là đủ cho bài lab.
- Timeout quá dài làm alert chậm; timeout quá ngắn dễ false positive khi máy đang CPU/disk pressure.
- `RestartSec` quá thấp có thể tạo restart storm, spam log và che mất lỗi gốc.
- Endpoint `/health` phải nhẹ; deep dependency check nên tách khỏi readiness hoặc synthetic check nếu dependency chậm.

### Bottleneck thường gặp và cách phát hiện

| Bottleneck | Dấu hiệu | Command gợi ý |
|------------|----------|---------------|
| CPU saturation | latency tăng, `top` thấy process ăn CPU | `top -p <PID>`, `pidstat 1` |
| Memory leak | RSS tăng đều, OOM hoặc swap | `ps -o pid,rss,cmd -p <PID>`, `free -h` |
| Port/socket backlog | connection timeout hoặc refused | `ss -ltnp`, `ss -s` |
| DNS chậm | `curl` mất thời gian ở name lookup | `curl -w '%{time_namelookup}\n'` |
| Disk pressure | log ghi chậm, service timeout | `df -h`, `iostat -xz 1` |

### Scaling strategy

- Vertical scaling: tăng CPU/RAM cho VM khi bottleneck là resource cục bộ và traffic chưa lớn.
- Horizontal scaling: chạy nhiều instance sau load balancer khi service stateless.
- Queue-based scaling: dùng queue khi request có thể xử lý async, tránh ép HTTP worker giữ connection lâu.
- Event-driven scaling: phù hợp cho batch/job không đều, nhưng cần idempotency và retry rõ ràng.
- Khi scale là sai giải pháp: config sai, port conflict, DNS lỗi, memory leak, hoặc dependency timeout chưa được xử lý.

---

## 7. Security & Reliability Considerations

- Chạy service bằng user riêng, không dùng `root` nếu không cần bind privileged port.
- Đặt permission chặt cho env file: `chmod 600 /opt/demo-api/.env` nếu chứa token.
- Không ghi secret vào command line vì có thể lộ qua `ps` hoặc shell history.
- Giới hạn quyền systemd bằng `NoNewPrivileges=true`, `ProtectSystem=strict`, `PrivateTmp=true` khi service không cần ghi toàn filesystem.
- Reliability cần có rollback: binary version trước đó, unit file trước đó, và command stop/start rõ ràng.
- Giảm blast radius bằng cách dùng port riêng, working directory riêng, log riêng và cleanup không xóa nhầm ngoài `/opt/demo-api`.
- Health check nên fail closed với exit code khác `0`; monitoring không nên parse text tiếng người nếu có thể dùng code/status.

---

## 8. Hands-on Example

### Step 1: Tạo HTTP Service

Chọn **một** trong hai ngôn ngữ bên dưới.

#### Option A: Golang

```go
// File: server.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

type HealthResponse struct {
	Status    string `json:"status"`
	Timestamp string `json:"timestamp"`
	Uptime    string `json:"uptime"`
}

type InfoResponse struct {
	Service string `json:"service"`
	Version string `json:"version"`
	Host    string `json:"host"`
	PID     int    `json:"pid"`
}

var startTime = time.Now()

func healthHandler(w http.ResponseWriter, r *http.Request) {
	resp := HealthResponse{
		Status:    "healthy",
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Uptime:    time.Since(startTime).Round(time.Second).String(),
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func infoHandler(w http.ResponseWriter, r *http.Request) {
	hostname, _ := os.Hostname()
	resp := InfoResponse{
		Service: "demo-api",
		Version: "1.0.0",
		Host:    hostname,
		PID:     os.Getpid(),
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func slowHandler(w http.ResponseWriter, r *http.Request) {
	time.Sleep(5 * time.Second)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "slow response completed",
	})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/api/info", infoHandler)
	mux.HandleFunc("/api/slow", slowHandler)

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown
	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Printf("Starting server on port %s (PID: %d)", port, os.Getpid())
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-done
	log.Println("Received shutdown signal, graceful shutdown...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Forced shutdown: %v", err)
	}

	log.Println("Server stopped gracefully")
}
```

```bash
# Build
cd /tmp && mkdir -p mini-project && cd mini-project
# (copy server.go vào thư mục)
go build -o demo-api server.go

# Test
./demo-api &
curl -s http://localhost:8080/health | jq .
# Expected:
# {
#   "status": "healthy",
#   "timestamp": "2024-01-15T10:30:00Z",
#   "uptime": "5s"
# }

curl -s http://localhost:8080/api/info | jq .
# Expected:
# {
#   "service": "demo-api",
#   "version": "1.0.0",
#   "host": "myhost",
#   "pid": 12345
# }

kill %1
```

#### Option B: Node.js

```javascript
// File: server.js
const http = require('http');
const os = require('os');

const PORT = process.env.PORT || 8080;
const startTime = Date.now();

function formatUptime() {
  const seconds = Math.floor((Date.now() - startTime) / 1000);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h${m}m${s}s`;
}

const routes = {
  '/health': (req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: formatUptime()
    }));
  },
  '/api/info': (req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      service: 'demo-api',
      version: '1.0.0',
      host: os.hostname(),
      pid: process.pid
    }));
  },
  '/api/slow': (req, res) => {
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ message: 'slow response completed' }));
    }, 5000);
  }
};

const server = http.createServer((req, res) => {
  const handler = routes[req.url];
  if (handler) {
    handler(req, res);
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'not found' }));
  }
});

// Graceful shutdown
function shutdown(signal) {
  console.log(`Received ${signal}, graceful shutdown...`);
  server.close(() => {
    console.log('Server stopped gracefully');
    process.exit(0);
  });
  setTimeout(() => {
    console.error('Forced shutdown after timeout');
    process.exit(1);
  }, 30000);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

server.listen(PORT, () => {
  console.log(`Starting server on port ${PORT} (PID: ${process.pid})`);
});
```

```bash
# Test
node server.js &
curl -s http://localhost:8080/health | jq .
curl -s http://localhost:8080/api/info | jq .
kill %1
```

### Step 2: Tạo systemd Unit File

```ini
# File: /etc/systemd/system/demo-api.service
[Unit]
Description=Demo API Service
Documentation=https://github.com/your-org/demo-api
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=demo-api
Group=demo-api
WorkingDirectory=/opt/demo-api
ExecStart=/opt/demo-api/demo-api
# Hoặc cho Node.js:
# ExecStart=/usr/bin/node /opt/demo-api/server.js

Environment=PORT=8080
EnvironmentFile=-/opt/demo-api/.env

Restart=on-failure
RestartSec=5
StartLimitBurst=3
StartLimitIntervalSec=60

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/demo-api/logs

# Graceful shutdown
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=demo-api

[Install]
WantedBy=multi-user.target
```

```bash
# Cài đặt service (cần root)
# Nếu không có root, mô phỏng bằng cách chạy trực tiếp

# Với root:
sudo useradd -r -s /sbin/nologin demo-api
sudo mkdir -p /opt/demo-api/logs
sudo cp demo-api /opt/demo-api/   # hoặc server.js
sudo cp demo-api.service /etc/systemd/system/
sudo chown -R demo-api:demo-api /opt/demo-api

sudo systemctl daemon-reload
sudo systemctl enable demo-api
sudo systemctl start demo-api

# Verify
sudo systemctl status demo-api
# Expected: Active: active (running)

journalctl -u demo-api -f
# Expected: "Starting server on port 8080 (PID: xxxxx)"

curl -s http://localhost:8080/health | jq .
# Expected: {"status":"healthy",...}
```

### Step 3: Viết Health Check Script

```bash
#!/bin/bash
# File: health-check.sh
set -euo pipefail

# Configuration
SERVICE_URL="${SERVICE_URL:-http://localhost:8080}"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-/health}"
TIMEOUT="${TIMEOUT:-5}"
MAX_RETRIES="${MAX_RETRIES:-3}"
LOG_FILE="${LOG_FILE:-/tmp/health-check.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() {
    local level="$1"
    shift
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] $*" | tee -a "$LOG_FILE"
}

check_health() {
    local url="${SERVICE_URL}${HEALTH_ENDPOINT}"
    local attempt=1

    while [ $attempt -le "$MAX_RETRIES" ]; do
        local http_code
        local response
        local start_time
        local end_time
        local duration

        start_time=$(date +%s%N)

        response=$(curl -s -o /dev/null -w "%{http_code}" \
            --connect-timeout "$TIMEOUT" \
            --max-time "$TIMEOUT" \
            "$url" 2>/dev/null) || response="000"

        end_time=$(date +%s%N)
        duration=$(( (end_time - start_time) / 1000000 ))

        if [ "$response" = "200" ]; then
            log "INFO" "${GREEN}HEALTHY${NC} — $url responded $response in ${duration}ms"

            if [ "$duration" -gt 2000 ]; then
                log "WARN" "${YELLOW}SLOW RESPONSE${NC} — ${duration}ms exceeds 2000ms threshold"
            fi
            return 0
        fi

        log "WARN" "Attempt $attempt/$MAX_RETRIES — $url responded $response in ${duration}ms"
        attempt=$((attempt + 1))
        sleep 2
    done

    log "ERROR" "${RED}UNHEALTHY${NC} — $url failed after $MAX_RETRIES attempts"
    return 1
}

check_process() {
    local service_name="${1:-demo-api}"

    if pgrep -f "$service_name" > /dev/null 2>&1; then
        local pid
        pid=$(pgrep -f "$service_name" | head -1)
        log "INFO" "Process $service_name running (PID: $pid)"
        return 0
    else
        log "ERROR" "${RED}Process $service_name NOT running${NC}"
        return 1
    fi
}

check_port() {
    local port="${1:-8080}"

    if ss -tlnp | grep -q ":${port} "; then
        local process_info
        process_info=$(ss -tlnp | grep ":${port} " | awk '{print $NF}')
        log "INFO" "Port $port is listening — $process_info"
        return 0
    else
        log "ERROR" "${RED}Port $port is NOT listening${NC}"
        return 1
    fi
}

check_disk() {
    local threshold="${1:-90}"
    local usage
    usage=$(df /opt 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')

    if [ -z "$usage" ]; then
        usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    fi

    if [ "$usage" -gt "$threshold" ]; then
        log "WARN" "${YELLOW}Disk usage ${usage}% exceeds ${threshold}% threshold${NC}"
        return 1
    else
        log "INFO" "Disk usage: ${usage}%"
        return 0
    fi
}

# Main
main() {
    log "INFO" "=== Health Check Started ==="

    local exit_code=0

    echo "--- Process Check ---"
    check_process "demo-api" || exit_code=1

    echo "--- Port Check ---"
    check_port 8080 || exit_code=1

    echo "--- HTTP Health Check ---"
    check_health || exit_code=1

    echo "--- Disk Check ---"
    check_disk 90 || exit_code=1

    echo ""
    if [ $exit_code -eq 0 ]; then
        log "INFO" "${GREEN}=== All Checks PASSED ===${NC}"
    else
        log "ERROR" "${RED}=== Some Checks FAILED ===${NC}"
    fi

    return $exit_code
}

main "$@"
```

```bash
# Chạy health check
chmod +x health-check.sh
./health-check.sh

# Expected output:
# 2024-01-15 10:30:00 [INFO] === Health Check Started ===
# --- Process Check ---
# 2024-01-15 10:30:00 [INFO] Process demo-api running (PID: 12345)
# --- Port Check ---
# 2024-01-15 10:30:00 [INFO] Port 8080 is listening — users:("demo-api",pid=12345,fd=3)
# --- HTTP Health Check ---
# 2024-01-15 10:30:00 [INFO] HEALTHY — http://localhost:8080/health responded 200 in 5ms
# --- Disk Check ---
# 2024-01-15 10:30:00 [INFO] Disk usage: 45%
# 2024-01-15 10:30:00 [INFO] === All Checks PASSED ===
```

### Step 4: Mô phỏng lỗi và Debug

#### Failure 1: Process Crash

```bash
# Mô phỏng: kill service
kill -9 $(pgrep -f demo-api)

# Quan sát: systemd tự restart (nếu Restart=on-failure)
systemctl status demo-api
# Expected: Active: activating (auto-restart)
# Sau 5s: Active: active (running) — PID mới

# Debug commands khi process không tự restart:
journalctl -u demo-api --since "5 min ago" --no-pager
# → Tìm exit code, error message

ps aux | grep demo-api
# → Kiểm tra process có đang chạy không

# Verify recovery
./health-check.sh
```

#### Failure 2: Port Conflict

```bash
# Mô phỏng: chiếm port 8080 trước khi service start
python3 -m http.server 8080 &
BLOCKER_PID=$!

# Restart service → sẽ fail
sudo systemctl restart demo-api
sudo systemctl status demo-api
# Expected: Active: failed (Result: exit-code)

# Debug:
ss -tlnp | grep :8080
# → Thấy python3 đang chiếm port

journalctl -u demo-api -n 20
# → "bind: address already in use"

# Fix:
kill $BLOCKER_PID
sudo systemctl start demo-api

# Verify
./health-check.sh
```

#### Failure 3: DNS Failure

```bash
# Mô phỏng: block DNS resolution
# Cách 1: Thêm entry sai vào /etc/hosts (cần root)
echo "127.0.0.1 api.external-service.com" | sudo tee -a /etc/hosts

# Cách 2: Service gọi DNS resolve (mô phỏng)
curl -s --connect-timeout 3 http://nonexistent-domain-12345.com/api || true
# Expected: curl: (6) Could not resolve host

# Debug DNS:
dig api.external-service.com
nslookup api.external-service.com
cat /etc/resolv.conf
# → Kiểm tra DNS server configuration

# Fix:
sudo sed -i '/api.external-service.com/d' /etc/hosts

# Verify DNS:
dig google.com +short
# Expected: IP address
```

#### Failure 4: Slow Response

```bash
# Mô phỏng: gọi endpoint chậm
time curl -s http://localhost:8080/api/slow
# Expected: ~5 seconds delay

# Debug performance:
# 1. Kiểm tra latency
for i in {1..5}; do
    curl -o /dev/null -s -w "Response time: %{time_total}s\n" http://localhost:8080/health
done

# 2. Kiểm tra system resources
top -b -n 1 | head -20
# → CPU, memory usage

# 3. Kiểm tra network connections
ss -s
# → Connection statistics

# 4. Kiểm tra file descriptors
ls /proc/$(pgrep -f demo-api | head -1)/fd | wc -l
# → Số file descriptors đang mở

# 5. strace để xem system calls
strace -p $(pgrep -f demo-api | head -1) -c -e trace=network
# → Xem network syscalls summary
# Ctrl+C sau 10 giây
```

### Step 5: Viết Runbook

```markdown
# File: runbook.md
# Demo API — Incident Runbook

## Runbook 1: Service Down — Process Not Running

### Symptom
- Health check trả về connection refused
- `systemctl status demo-api` → inactive/failed

### Triage (2 phút)
1. `systemctl status demo-api` → xem status và exit code
2. `journalctl -u demo-api --since "10 min ago" -n 50` → xem logs

### Common Causes & Fix

| Cause | Evidence | Fix |
|-------|----------|-----|
| OOM Killed | `dmesg \| grep -i oom` | Tăng memory limit, fix memory leak |
| Crash loop | Restart count cao trong status | Xem log, fix bug |
| Config error | Exit code 1 + error message | Fix config, validate trước khi deploy |

### Recovery
```bash
sudo systemctl restart demo-api
sleep 5
./health-check.sh
```

---

## Runbook 2: Port Already in Use

### Symptom
- Service fail to start
- Log: "bind: address already in use"

### Triage
```bash
ss -tlnp | grep :8080
# Output: process name và PID đang chiếm port
```

### Fix
```bash
# Option 1: Kill process chiếm port
kill $(ss -tlnp | grep :8080 | grep -oP 'pid=\K\d+')

# Option 2: Đổi port cho service
# Edit /opt/demo-api/.env → PORT=8081
sudo systemctl restart demo-api
```

---

## Runbook 3: DNS Resolution Failure

### Symptom
- Service log: "could not resolve host"
- Health check OK nhưng external API calls fail

### Triage
```bash
dig google.com
cat /etc/resolv.conf
ping -c 1 8.8.8.8  # Test network connectivity (bypass DNS)
```

### Fix
```bash
# Check DNS config
cat /etc/resolv.conf

# Temporary fix: add Google DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# Permanent: fix DHCP/network config
```

---

## Runbook 4: High Latency / Slow Response

### Symptom
- Response time > 2 giây
- Health check cảnh báo SLOW RESPONSE

### Triage (5 phút)
```bash
# 1. Measure response time
curl -w "time_total: %{time_total}s\n" -o /dev/null -s http://localhost:8080/health

# 2. Check system resources
top -b -n 1 | head -5     # CPU/memory overview
iostat -x 1 3              # Disk I/O
vmstat 1 5                  # Memory/swap

# 3. Check connections
ss -s                       # Connection summary
ss -tnp | grep :8080 | wc -l  # Active connections

# 4. Check if throttled (container/cgroup)
cat /sys/fs/cgroup/cpu/cpu.stat 2>/dev/null || true
```

### Common Causes

| Cause | Signal | Fix |
|-------|--------|-----|
| CPU saturated | top → CPU >90% | Scale hoặc optimize code |
| Memory pressure | vmstat → swap active | Tăng memory, fix leak |
| Disk I/O | iostat → await >20ms | Optimize queries, SSD |
| Too many connections | ss -s → high count | Connection pooling, rate limit |
| Downstream slow | strace → long recv() | Timeout config, circuit breaker |
```

### Step 6: Tổng hợp Project Structure

```bash
# Project structure cuối cùng
mini-project/
├── server.go            # (hoặc server.js)
├── demo-api.service     # systemd unit file
├── health-check.sh      # Health check script
├── runbook.md           # Incident runbook
├── Makefile             # Build và management commands
└── README.md            # Project documentation
```

```makefile
# File: Makefile
.PHONY: build run test health install clean

SERVICE_NAME=demo-api
PORT=8080

build:
	go build -o $(SERVICE_NAME) server.go
	@echo "Built $(SERVICE_NAME)"

run: build
	PORT=$(PORT) ./$(SERVICE_NAME)

test:
	@echo "Testing endpoints..."
	@curl -sf http://localhost:$(PORT)/health | jq . || echo "Health check failed"
	@curl -sf http://localhost:$(PORT)/api/info | jq . || echo "Info endpoint failed"

health:
	@./health-check.sh

install: build
	sudo cp $(SERVICE_NAME) /opt/$(SERVICE_NAME)/
	sudo cp demo-api.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable $(SERVICE_NAME)
	sudo systemctl start $(SERVICE_NAME)
	@echo "Installed and started $(SERVICE_NAME)"

clean:
	rm -f $(SERVICE_NAME)
	@echo "Cleaned build artifacts"

uninstall:
	sudo systemctl stop $(SERVICE_NAME) || true
	sudo systemctl disable $(SERVICE_NAME) || true
	sudo rm -f /etc/systemd/system/demo-api.service
	sudo systemctl daemon-reload
	@echo "Uninstalled $(SERVICE_NAME)"
```

### Cleanup

```bash
# Nếu dùng systemd:
sudo systemctl stop demo-api 2>/dev/null || true
sudo systemctl disable demo-api 2>/dev/null || true
sudo rm -f /etc/systemd/system/demo-api.service
sudo systemctl daemon-reload
sudo rm -rf /opt/demo-api

# File local:
rm -rf /tmp/mini-project
rm -f /tmp/health-check.log
```

---

### Ghi chú bổ sung: systemd, Supervisor, Container

### systemd vs Supervisor vs Container

| Approach | Ưu điểm | Nhược điểm | Khi nào dùng |
|----------|---------|-------------|-------------|
| systemd | Native Linux, mature, dependency mgmt | Linux only, complex unit syntax | Bare metal / VM |
| Supervisor | Cross-platform, simple config | Extra dependency, ít feature | Legacy systems |
| Docker + restart policy | Isolation, portable | Overhead, thêm layer | Container environments |
| Kubernetes | Auto-healing, scaling | Phức tạp, cần cluster | Microservices at scale |

### Health Check Strategy

```
Level 1: Process alive (is PID running?)
  → Đơn giản, nhanh, phát hiện crash
  → KHÔNG phát hiện deadlock, resource exhaustion

Level 2: Port listening (is port accepting connections?)
  → Phát hiện port conflict, bind failure
  → KHÔNG phát hiện application-level issues

Level 3: HTTP health endpoint (does /health return 200?)
  → Phát hiện application errors
  → KHÔNG phát hiện dependency failures

Level 4: Deep health check (/health includes dependency status)
  → Phát hiện DB down, cache unreachable
  → CẨN THẬN: cascading failure nếu dependency slow
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Service chạy được trong shell nhưng fail trong systemd

**Dấu hiệu:** `go run server.go` hoặc `node server.js` chạy tốt, nhưng `systemctl start demo-api` fail.

**Debug flow:**

```bash
sudo systemctl status demo-api --no-pager
sudo journalctl -u demo-api -n 100 --no-pager
sudo systemctl cat demo-api
```

**Nguyên nhân thường gặp:** sai `WorkingDirectory`, thiếu env var, binary chưa executable, path trong `ExecStart` là relative path.

### Pitfall 2: Restart loop che mất lỗi gốc

**Dấu hiệu:** `systemctl status` báo `activating (auto-restart)` hoặc `Start request repeated too quickly`.

**Debug flow:**

```bash
sudo journalctl -u demo-api --since "10 minutes ago" --no-pager
sudo systemctl show demo-api -p NRestarts -p RestartUSec -p ExecMainStatus
```

Tạm thời tăng `RestartSec` hoặc stop service để đọc log ổn định trước khi sửa.

### Pitfall 3: Health check false positive

**Dấu hiệu:** monitoring báo healthy nhưng user vẫn lỗi.

**Nguyên nhân:** chỉ kiểm tra PID/port, không gọi endpoint HTTP hoặc không đo latency.

**Fix:** health check tối thiểu cần status code, timeout, response time và exit code rõ ràng.

### Pitfall 4: Port conflict xử lý sai

**Dấu hiệu:** service fail với `address already in use`.

**Debug flow:**

```bash
sudo ss -ltnp 'sport = :8080'
sudo lsof -iTCP:8080 -sTCP:LISTEN
```

Không kill process lạ ngay lập tức nếu đó là service production khác; xác định owner trước rồi mới đổi port hoặc stop process.

### Pitfall 5: DNS lỗi bị nhầm thành application lỗi

**Dấu hiệu:** HTTP client báo `Could not resolve host`, nhưng service local vẫn healthy.

**Debug flow:**

```bash
getent hosts example.com
dig example.com
cat /etc/resolv.conf
curl -w 'dns=%{time_namelookup} total=%{time_total}\n' -o /dev/null -s http://example.com
```

### Case study nhỏ

Một API bị báo "down" sau deploy. PID vẫn chạy, port vẫn listen, `/health` trả `200`, nhưng request thật timeout. Debug bằng `curl -w` cho thấy `time_namelookup` cao bất thường; `dig` tới upstream DNS mất hơn 3 giây. Root cause không nằm ở process manager mà ở resolver config mới. Fix đúng là rollback DNS config hoặc đổi resolver, không phải tăng replica/service restart.

### Acceptance Criteria

- [ ] HTTP service chạy được trên port 8080
- [ ] `/health` trả về JSON với status, timestamp, uptime
- [ ] `/api/info` trả về service name, version, hostname, PID
- [ ] systemd unit file tạo đúng cấu trúc (hoặc mô phỏng)
- [ ] Service tự restart khi bị kill (Restart=on-failure)
- [ ] Graceful shutdown khi nhận SIGTERM
- [ ] Health check script kiểm tra: process, port, HTTP, disk
- [ ] Mô phỏng và debug được 4 loại lỗi
- [ ] Runbook viết cho mỗi loại lỗi
- [ ] Cleanup commands hoạt động

---

## 10. Kết nối với bài trước & bài sau

### Từ Linux → Container

Mọi thứ bạn vừa làm trong project này sẽ được **containerize** trong Phase 2:

| Phase 1 (vừa làm) | Phase 2 (sắp học) |
|-------------------|-------------------|
| systemd unit file | Dockerfile + K8s Pod spec |
| health-check.sh | K8s liveness/readiness probe |
| Port 8080 binding | K8s Service + port mapping |
| Process management | Container runtime + kubelet |
| Runbook | K8s troubleshooting methodology |
| SIGTERM handling | Pod termination lifecycle |
| Log to journalctl | Container stdout → logging system |

### Day 8 Preview

Ngày mai bạn sẽ học **Docker Internals**: hiểu container thực chất là Linux process + namespace + cgroup — xây dựng trên nền tảng Linux đã học trong Phase 1.

---

## 11. Tài liệu tham khảo

### Must-read
- [systemd Service File Reference](https://www.freedesktop.org/software/systemd/man/systemd.service.html) — Official systemd docs
- [Brendan Gregg's Linux Performance Tools](https://www.brendangregg.com/linuxperf.html) — Performance debugging reference

### Nice-to-have
- [Google SRE Book — Chapter 29: Dealing with Interrupts](https://sre.google/sre-book/dealing-with-interrupts/) — Runbook best practices
- [PagerDuty Incident Response](https://response.pagerduty.com/) — Incident response framework

### Deep-dive
- [Linux Observability with BPF](https://www.oreilly.com/library/view/linux-observability-with/9781492050193/) — Advanced Linux debugging
- [Systems Performance by Brendan Gregg](https://www.brendangregg.com/systems-performance-2nd-edition-book.html) — Comprehensive performance analysis

