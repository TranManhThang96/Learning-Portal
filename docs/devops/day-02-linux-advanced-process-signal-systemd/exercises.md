# Day 2: Bài tập — Linux Process, Signal, File Descriptor, systemd

---

## Bài 1: Easy — Quan sát Process và Signal

### Context
Bạn cần hiểu cách Linux process hoạt động và cách signal ảnh hưởng đến process. Đây là kiến thức nền tảng trước khi làm việc với container và Kubernetes.

### Yêu cầu
1. Tạo một process tree đơn giản: parent process spawn 2 child processes.
2. Quan sát process tree bằng `ps`, `pstree`.
3. Gửi `SIGTERM` đến parent → quan sát child processes.
4. Gửi `SIGTERM` đến child → quan sát parent.
5. Tạo zombie process và quan sát.

### Expected Outcome
- Hiểu rõ parent/child relationship.
- Biết cách xác định PID, PPID.
- Thấy được zombie process trong `ps` output.

### Hint
- Dùng bash script: `sleep 1000 &` để tạo child process.
- `ps auxf` hiển thị process tree.
- Zombie: child exit nhưng parent chưa `wait()`.

### Acceptance Criteria
- [ ] Tạo được process tree với ít nhất 3 processes.
- [ ] Screenshot/output `ps auxf` hoặc `pstree -p` cho thấy tree.
- [ ] Gửi signal thành công và quan sát kết quả.
- [ ] Tạo được zombie process và giải thích cách fix.

### Bonus Challenge
- Viết Python script tạo 5 child processes, handle SIGTERM ở parent để kill tất cả children trước khi exit.

<details>
<summary>Solution / Reference</summary>

```bash
#!/bin/bash
# exercise-1-process-tree.sh

echo "Parent PID: $$"

# Spawn child processes
sleep 1000 &
CHILD1=$!
echo "Child 1 PID: $CHILD1"

sleep 1000 &
CHILD2=$!
echo "Child 2 PID: $CHILD2"

# View process tree
echo ""
echo "=== Process Tree ==="
pstree -p $$
echo ""
echo "=== ps output ==="
ps -o pid,ppid,state,cmd --forest -g $$

# Wait for children
wait
```

```bash
# Tạo zombie process
cat << 'ZOMBIE_SCRIPT' > /tmp/zombie-demo.sh
#!/bin/bash
echo "Parent PID: $$"

# Fork child that exits immediately
bash -c 'echo "Child PID: $$"; exit 0' &
CHILD=$!

echo "Child $CHILD spawned and exited"
echo "Sleeping without calling wait() — child becomes zombie"
sleep 5

echo ""
echo "=== Check for zombie ==="
ps aux | grep -E "PID|defunct|$CHILD"

echo ""
echo "Now calling wait to reap zombie..."
wait $CHILD
echo "Zombie reaped"

ps aux | grep -E "PID|defunct|$CHILD"
ZOMBIE_SCRIPT

chmod +x /tmp/zombie-demo.sh
bash /tmp/zombie-demo.sh
```

</details>

---

## Bài 2: Medium — Graceful Shutdown Service

### Context
Bạn đang viết một API service xử lý payment. Khi deploy version mới, Kubernetes gửi `SIGTERM` để yêu cầu service tắt. Service cần:
1. Ngừng nhận request mới.
2. Hoàn thành các request đang xử lý (in-flight).
3. Close database connections.
4. Flush logs/metrics buffers.
5. Exit với code 0.

### Yêu cầu
1. Viết service bằng Golang hoặc Node.js (chọn một) có:
   - HTTP endpoint `/process` mất 3-5 giây xử lý (simulate payment processing).
   - HTTP endpoint `/health` trả 200 khi healthy, 503 khi shutting down.
   - Handle `SIGTERM` và `SIGINT`.
   - Graceful shutdown với timeout 15 giây.
   - Log mỗi bước trong shutdown process.
2. Test bằng cách gửi request + SIGTERM đồng thời.
3. Verify: in-flight request phải nhận response, request mới sau SIGTERM phải bị reject.

### Expected Outcome
- Service graceful shutdown thành công.
- In-flight request hoàn thành.
- Health endpoint trả 503 trong quá trình shutdown.
- Clean exit code 0.

### Hint
- Golang: `http.Server.Shutdown(ctx)` handles in-flight requests.
- Node.js: `server.close(callback)` waits for connections to finish.
- Dùng `curl` trong background (`&`) để simulate in-flight request.

### Acceptance Criteria
- [ ] Service handle SIGTERM và graceful shutdown.
- [ ] In-flight request không bị drop.
- [ ] Health endpoint trả 503 khi shutting down.
- [ ] Exit code 0 sau shutdown thành công.
- [ ] Log output cho thấy từng bước shutdown.

### Bonus Challenge
- Thêm database connection pool (dùng SQLite hoặc mock). Verify connection pool được close trong shutdown.
- Dockerize service và test với `docker stop` (gửi SIGTERM + 10s timeout).
- Thêm metric: đếm số request completed vs dropped.

<details>
<summary>Solution / Reference</summary>

**Golang solution:**

```go
package main

import (
	"context"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

var (
	isShuttingDown int32
	activeRequests sync.WaitGroup
	totalProcessed int64
	totalDropped   int64
)

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/process", func(w http.ResponseWriter, r *http.Request) {
		if atomic.LoadInt32(&isShuttingDown) == 1 {
			atomic.AddInt64(&totalDropped, 1)
			http.Error(w, "Service shutting down", http.StatusServiceUnavailable)
			return
		}

		activeRequests.Add(1)
		defer activeRequests.Done()

		processingTime := 3 + rand.Intn(3) // 3-5 seconds
		log.Printf("[REQUEST] Processing payment (will take %ds)...", processingTime)
		time.Sleep(time.Duration(processingTime) * time.Second)

		count := atomic.AddInt64(&totalProcessed, 1)
		fmt.Fprintf(w, "Payment #%d processed successfully (took %ds)\n", count, processingTime)
		log.Printf("[REQUEST] Payment #%d completed", count)
	})

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if atomic.LoadInt32(&isShuttingDown) == 1 {
			w.WriteHeader(http.StatusServiceUnavailable)
			fmt.Fprintln(w, "shutting down")
			return
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprintln(w, "ok")
	})

	server := &http.Server{Addr: ":8080", Handler: mux}

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		log.Printf("[STARTUP] Server listening on :8080 (PID: %d)", os.Getpid())
		if err := server.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("[ERROR] %v", err)
		}
	}()

	sig := <-sigChan
	log.Printf("[SHUTDOWN] Step 1: Received %s signal", sig)

	atomic.StoreInt32(&isShuttingDown, 1)
	log.Println("[SHUTDOWN] Step 2: Marked as shutting down (health → 503)")

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	log.Println("[SHUTDOWN] Step 3: Stopping HTTP listener (no new connections)")
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("[SHUTDOWN] Error: %v", err)
	}

	log.Println("[SHUTDOWN] Step 4: Waiting for active requests to complete...")
	activeRequests.Wait()

	log.Println("[SHUTDOWN] Step 5: Closing database connections (simulated)")
	time.Sleep(500 * time.Millisecond)

	log.Println("[SHUTDOWN] Step 6: Flushing metrics/logs (simulated)")
	time.Sleep(200 * time.Millisecond)

	log.Printf("[SHUTDOWN] Complete. Processed: %d, Dropped: %d",
		atomic.LoadInt64(&totalProcessed),
		atomic.LoadInt64(&totalDropped))
}
```

**Test script:**
```bash
#!/bin/bash
echo "Starting server..."
go run main.go &
SERVER_PID=$!
sleep 2

echo ""
echo "=== Sending 3 requests in parallel ==="
curl -s http://localhost:8080/process &
curl -s http://localhost:8080/process &
curl -s http://localhost:8080/process &

# Wait 1 second then send SIGTERM
sleep 1
echo ""
echo "=== Sending SIGTERM ==="
kill -SIGTERM $SERVER_PID

# Try to send request during shutdown
sleep 0.5
echo ""
echo "=== Request during shutdown ==="
curl -s http://localhost:8080/process
echo ""
echo "=== Health during shutdown ==="
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health
echo ""

wait $SERVER_PID
echo ""
echo "Server exit code: $?"
```

</details>

---

## Bài 3: Hard — systemd Production Service + Debug Simulation

### Context
Bạn cần deploy một HTTP service trên Linux server với systemd, sau đó simulate và debug các production issues: file descriptor leak, zombie processes, service crash loop.

### Yêu cầu

**Part 1: systemd Service Setup**
1. Viết systemd unit file chuẩn production cho service từ Bài 2. Bao gồm:
   - Security hardening (NoNewPrivileges, ProtectSystem, etc.)
   - Resource limits (LimitNOFILE, LimitNPROC)
   - Restart policy với rate limiting
   - Journal logging configuration
   - Health check (hoặc watchdog)
2. Deploy và verify service chạy đúng.

**Part 2: Simulate và Debug Issues**
1. **File descriptor leak**: Sửa code để leak fd, quan sát bằng `/proc` và `lsof`, tìm root cause.
2. **Crash loop**: Sửa code để crash ngay khi start, quan sát systemd restart behavior.
3. **Zombie processes**: Tạo children không được reap, quan sát và fix.

**Part 3: Monitoring Script**
Viết script monitor process health: fd count, memory usage, thread count. Alert khi vượt threshold.

### Expected Outcome
- systemd unit file chuẩn production.
- Debug report cho mỗi simulated issue.
- Monitoring script có thể chạy cron.

### Hint
- File descriptor leak: mở file/socket trong loop nhưng không close.
- Crash loop: `StartLimitIntervalSec` và `StartLimitBurst` control restart behavior.
- Monitoring: đọc từ `/proc/<pid>/status` và `/proc/<pid>/fd/`.

### Acceptance Criteria
- [ ] systemd unit file có security hardening, resource limits, restart policy.
- [ ] Service deploy và chạy thành công qua systemd.
- [ ] Debug fd leak: xác định được fd nào leak, fix được.
- [ ] Debug crash loop: hiểu systemd restart behavior, limits.
- [ ] Monitoring script chạy được, output readable.

### Bonus Challenge
- Thêm `WatchdogSec` vào systemd unit và implement watchdog notify trong code.
- Tạo `ExecStartPre` script kiểm tra dependencies (database, config file).
- Viết runbook cho mỗi issue đã debug.

<details>
<summary>Solution / Reference</summary>

**Part 3: Monitoring Script:**

```bash
#!/bin/bash
# process-monitor.sh — Monitor process health

SERVICE_NAME="${1:-graceful-server}"
PID=$(pgrep -f "$SERVICE_NAME" | head -1)

if [ -z "$PID" ]; then
    echo "CRITICAL: $SERVICE_NAME not running!"
    exit 2
fi

# Thresholds
FD_WARN=500
FD_CRIT=900
MEM_WARN_MB=512
MEM_CRIT_MB=1024
THREAD_WARN=50

echo "=== Process Monitor: $SERVICE_NAME (PID: $PID) ==="
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# File descriptors
FD_COUNT=$(ls /proc/$PID/fd 2>/dev/null | wc -l)
FD_LIMIT=$(grep "Max open files" /proc/$PID/limits 2>/dev/null | awk '{print $4}')
FD_STATUS="OK"
[ "$FD_COUNT" -gt "$FD_WARN" ] && FD_STATUS="WARNING"
[ "$FD_COUNT" -gt "$FD_CRIT" ] && FD_STATUS="CRITICAL"
echo "File Descriptors: $FD_COUNT / $FD_LIMIT [$FD_STATUS]"

# Memory
MEM_RSS_KB=$(grep VmRSS /proc/$PID/status 2>/dev/null | awk '{print $2}')
MEM_RSS_MB=$((MEM_RSS_KB / 1024))
MEM_VIRTUAL_KB=$(grep VmSize /proc/$PID/status 2>/dev/null | awk '{print $2}')
MEM_VIRTUAL_MB=$((MEM_VIRTUAL_KB / 1024))
MEM_STATUS="OK"
[ "$MEM_RSS_MB" -gt "$MEM_WARN_MB" ] && MEM_STATUS="WARNING"
[ "$MEM_RSS_MB" -gt "$MEM_CRIT_MB" ] && MEM_STATUS="CRITICAL"
echo "Memory RSS: ${MEM_RSS_MB}MB / Virtual: ${MEM_VIRTUAL_MB}MB [$MEM_STATUS]"

# Threads
THREADS=$(grep Threads /proc/$PID/status 2>/dev/null | awk '{print $2}')
THREAD_STATUS="OK"
[ "$THREADS" -gt "$THREAD_WARN" ] && THREAD_STATUS="WARNING"
echo "Threads: $THREADS [$THREAD_STATUS]"

# Uptime
START_TIME=$(stat -c %Y /proc/$PID 2>/dev/null || stat -f %m /proc/$PID 2>/dev/null)
NOW=$(date +%s)
UPTIME_SEC=$((NOW - START_TIME))
UPTIME_HOURS=$((UPTIME_SEC / 3600))
UPTIME_MINS=$(( (UPTIME_SEC % 3600) / 60 ))
echo "Uptime: ${UPTIME_HOURS}h ${UPTIME_MINS}m"

# TCP connections
TCP_ESTABLISHED=$(ss -tnp | grep "$PID" | grep ESTAB | wc -l)
TCP_LISTEN=$(ss -tlnp | grep "$PID" | wc -l)
echo "TCP: $TCP_LISTEN listening, $TCP_ESTABLISHED established"

echo ""
# Overall status
if [ "$FD_STATUS" = "CRITICAL" ] || [ "$MEM_STATUS" = "CRITICAL" ]; then
    echo "OVERALL: CRITICAL — immediate action needed"
    exit 2
elif [ "$FD_STATUS" = "WARNING" ] || [ "$MEM_STATUS" = "WARNING" ] || [ "$THREAD_STATUS" = "WARNING" ]; then
    echo "OVERALL: WARNING — investigate soon"
    exit 1
else
    echo "OVERALL: HEALTHY"
    exit 0
fi
```

</details>

---

## Tổng kết thời gian

| Bài | Độ khó | Thời gian ước tính |
|-----|--------|-------------------|
| Bài 1 | Easy | 20 phút |
| Bài 2 | Medium | 40-50 phút |
| Bài 3 | Hard | 60-90 phút |

Bài 1 + Bài 2 phù hợp cho 2 giờ/ngày. Bài 3 là bonus deep-dive.

