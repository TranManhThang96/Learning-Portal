# Day 2: Linux Advanced — Process, Signal, File Descriptor, systemd

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được Linux process model** — PID, PPID, process tree, zombie process, orphan process và cách kernel quản lý chúng.
2. **Xử lý được signal trong application code** — đặc biệt `SIGTERM` cho graceful shutdown, hiểu tại sao `SIGKILL` không thể bắt được.
3. **Sử dụng được file descriptor** để debug connection leak, file handle leak trong production.
4. **Viết được systemd unit file** chuẩn production để quản lý service lifecycle.
5. **Debug được process issue** bằng `ps`, `lsof`, `/proc`, `strace` — xác định process nào chiếm resource, port, file.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng trong production?

Trước khi học Docker và Kubernetes, bạn cần hiểu **app chạy trên Linux thế nào**. Container không phải magic — nó vẫn là Linux process với namespace và cgroup. Nếu bạn không hiểu process model, bạn sẽ:

- Không hiểu vì sao container bị kill (OOMKilled, SIGTERM timeout)
- Không biết debug khi pod stuck ở `Terminating`
- Không biết tại sao app mất data khi restart (graceful shutdown fail)

### Hậu quả nếu làm sai

| Sai lầm | Hậu quả thực tế |
|---------|-----------------|
| Không handle `SIGTERM` | Container bị `SIGKILL` sau 30s → mất in-flight requests, corrupt data |
| File descriptor leak | Service chạy vài ngày → "Too many open files" → crash |
| Không hiểu zombie process | PID table đầy → không thể spawn process mới → system hang |
| systemd unit file sai | Service không restart khi crash, log bị mất, dependency sai thứ tự |

### Liên hệ với kiến thức developer

- **Microservices**: Mỗi service là một process. Bạn đã viết code cho service — giờ cần hiểu service đó sống và chết thế nào trên OS.
- **Database connections**: Connection pool trong code tạo ra file descriptor. Leak connection = leak file descriptor.
- **Kafka consumer**: Consumer cần graceful shutdown để commit offset trước khi tắt. Không handle signal = reprocess messages.

---

## 3. Kiến thức nền tảng

### 3.1. Linux Process Model

**Process** là một instance đang chạy của một program. Mỗi process có:

| Thuộc tính | Mô tả | Ví dụ |
|-----------|-------|-------|
| **PID** | Process ID, unique trong system | `1234` |
| **PPID** | Parent Process ID | `1` (init/systemd) |
| **UID/GID** | User/Group sở hữu process | `1000` (user app) |
| **State** | Trạng thái hiện tại | Running, Sleeping, Zombie |
| **File descriptors** | Tài nguyên I/O đang mở | stdin(0), stdout(1), stderr(2), sockets, files |
| **Memory** | Virtual memory mapping | Code, heap, stack, shared libs |
| **Environment** | Biến môi trường | `PATH`, `HOME`, `DATABASE_URL` |

**Analogy cho developer**: Process giống như một **object instance** trong OOP. Program là class definition, process là instance đang chạy. Mỗi instance có state riêng (memory), identity riêng (PID), và lifecycle riêng (create → run → terminate).

### 3.2. Process Tree

```
systemd (PID 1)
├── sshd (PID 500)
│   └── bash (PID 1200)
│       └── node app.js (PID 1500)
│           ├── worker (PID 1501)
│           ├── worker (PID 1502)
│           └── worker (PID 1503)
├── nginx (PID 600)
│   ├── nginx worker (PID 601)
│   └── nginx worker (PID 602)
├── postgresql (PID 700)
│   ├── postgres: writer (PID 701)
│   ├── postgres: wal writer (PID 702)
│   └── postgres: autovacuum (PID 703)
└── dockerd (PID 800)
    └── containerd (PID 801)
        └── containerd-shim (PID 900)
            └── your-app (PID 901)  ← Container process
```

**Quy tắc quan trọng:**
- Khi parent process chết, child processes trở thành **orphan** → được adopt bởi PID 1 (systemd)
- Khi child process chết nhưng parent chưa gọi `wait()` → child trở thành **zombie** (trạng thái Z)
- PID 1 trong container có trách nhiệm đặc biệt: reap zombie processes

### 3.3. Signal

Signal là cơ chế **Inter-Process Communication (IPC)** để gửi notification cho process.

| Signal | Số | Có thể bắt? | Mục đích | Khi nào dùng |
|--------|---|-------------|----------|-------------|
| `SIGTERM` | 15 | ✅ | Yêu cầu terminate gracefully | `kill <pid>`, `docker stop`, Kubernetes pod termination |
| `SIGKILL` | 9 | ❌ | Force kill ngay lập tức | `kill -9`, sau SIGTERM timeout |
| `SIGHUP` | 1 | ✅ | Reload config | `nginx -s reload`, `kill -HUP <pid>` |
| `SIGINT` | 2 | ✅ | Interrupt (Ctrl+C) | User cancel trong terminal |
| `SIGUSR1` | 10 | ✅ | User-defined | Log rotation, debug toggle |
| `SIGUSR2` | 12 | ✅ | User-defined | Custom behavior |
| `SIGCHLD` | 17 | ✅ | Child process status changed | Parent cần reap child |
| `SIGSTOP` | 19 | ❌ | Pause process | Debugging |
| `SIGCONT` | 18 | ✅ | Resume paused process | Sau SIGSTOP |

**Analogy**: Signal giống **event/callback** trong programming. `SIGTERM` giống `onBeforeUnload` trong browser — bạn có cơ hội cleanup trước khi tắt. `SIGKILL` giống kill browser process — không có callback nào được gọi.

### 3.4. File Descriptor

**File descriptor (fd)** là một integer identifier cho mọi I/O resource mà process mở:

```
fd 0  → stdin   (standard input)
fd 1  → stdout  (standard output)
fd 2  → stderr  (standard error)
fd 3  → /var/log/app.log (opened file)
fd 4  → socket: 10.0.0.1:5432 (database connection)
fd 5  → socket: 10.0.0.2:6379 (Redis connection)
fd 6  → pipe (IPC with child process)
...
```

**Vì sao quan trọng**: Mỗi process có giới hạn fd (thường 1024 hoặc 65535). Khi leak → "Too many open files" → service crash.

### 3.5. /proc filesystem

`/proc` là **virtual filesystem** cung cấp thông tin runtime về kernel và processes:

```
/proc/
├── 1/                    # Process PID 1 (systemd)
│   ├── cmdline           # Command line arguments
│   ├── environ           # Environment variables
│   ├── fd/               # File descriptors (symlinks)
│   ├── maps              # Memory mappings
│   ├── status            # Process status (memory, threads, etc.)
│   └── net/              # Network info
├── cpuinfo               # CPU information
├── meminfo               # Memory information
├── loadavg               # System load average
└── sys/                  # Kernel parameters (sysctl)
    └── fs/
        └── file-max      # System-wide fd limit
```

### 3.6. systemd

**systemd** là init system và service manager trên hầu hết Linux distributions hiện đại. Nó quản lý:
- Service lifecycle (start, stop, restart, reload)
- Dependencies giữa services
- Logging (journald)
- Socket activation
- Resource limits (cgroups)

**Analogy**: systemd giống **Kubernetes cho bare-metal** — nó đảm bảo service chạy đúng trạng thái, tự restart khi crash, quản lý dependencies.

---

## 4. Deep Dive

### 4.1. Graceful Shutdown Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    Graceful Shutdown Flow                      │
│                                                              │
│  Kubernetes sends SIGTERM                                    │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────┐                                        │
│  │ App receives     │                                        │
│  │ SIGTERM          │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐     ┌─────────────────┐               │
│  │ Stop accepting   │     │ Finish in-flight │               │
│  │ new requests     │     │ requests         │               │
│  └────────┬────────┘     └────────┬────────┘               │
│           │                       │                          │
│           ▼                       ▼                          │
│  ┌─────────────────┐     ┌─────────────────┐               │
│  │ Close DB         │     │ Flush buffers    │               │
│  │ connections      │     │ (logs, metrics)  │               │
│  └────────┬────────┘     └────────┬────────┘               │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       ▼                                      │
│              ┌─────────────────┐                            │
│              │ Exit with code 0 │                            │
│              └─────────────────┘                            │
│                                                              │
│  ⏱️ terminationGracePeriodSeconds (default: 30s)             │
│  Nếu app chưa exit sau 30s → Kubernetes sends SIGKILL       │
└──────────────────────────────────────────────────────────────┘
```

### 4.2. systemd Service Lifecycle

```
                    ┌─────────┐
                    │ Inactive │
                    └────┬────┘
                         │ systemctl start
                         ▼
              ┌─────────────────────┐
              │    Activating       │
              │ (ExecStartPre runs) │
              └──────────┬──────────┘
                         │ ExecStart succeeds
                         ▼
                    ┌──────────┐
          ┌────────│  Active   │────────┐
          │        └──────────┘        │
          │              │              │
     Process crash  systemctl stop  systemctl reload
          │              │              │
          ▼              ▼              ▼
   ┌──────────┐  ┌──────────────┐  ┌──────────┐
   │ Failed   │  │ Deactivating │  │ Reloading│
   └────┬─────┘  │(ExecStop runs)│  └────┬─────┘
        │        └──────┬───────┘       │
        │               │               │
        │               ▼               │
        │        ┌──────────┐           │
        │        │ Inactive │           │
        │        └──────────┘           │
        │                               │
        └──── Restart=always ──────────┘
              (auto restart)
```

### 4.3. File Descriptor Lifecycle

```
Application startup:
  fd 0 ── stdin
  fd 1 ── stdout
  fd 2 ── stderr

open("/var/log/app.log") → fd 3
connect(db_host:5432)    → fd 4
connect(redis:6379)      → fd 5

... time passes, connections created but not closed ...

fd 6  ── leaked DB connection
fd 7  ── leaked DB connection
fd 8  ── leaked DB connection
...
fd 1023 ── leaked DB connection

open(anything) → ERROR: EMFILE (Too many open files)
                 → Service stops accepting connections
                 → 🔥 Production incident
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1. Graceful Shutdown: Timeout Trade-offs

| terminationGracePeriodSeconds | Ưu điểm | Nhược điểm | Phù hợp cho |
|-------------------------------|---------|------------|-------------|
| **5s** | Pod terminate nhanh, deploy speed tốt | Long-running requests bị kill | Stateless API, low-latency service |
| **30s** (default) | Đủ cho hầu hết HTTP services | Quá ngắn cho batch processing | Web services, API servers |
| **120s** | Đủ cho heavy processing | Deploy chậm, node drain chậm | gRPC streaming, WebSocket |
| **300s+** | Batch job có thể hoàn thành | Node maintenance rất chậm | Data pipeline, long-running jobs |

**Best practice**: Set bằng **max request timeout + buffer 10s**. Nếu request timeout là 30s → terminationGracePeriodSeconds = 40s.

### 5.2. systemd Restart Policy

| Restart | Khi nào dùng | Risk |
|---------|-------------|------|
| `Restart=no` | One-shot task, migration script | Service chết không ai biết |
| `Restart=on-failure` | Service có clean exit code khi stop | Nếu exit code sai → không restart |
| `Restart=always` | Production service phải luôn chạy | Restart loop nếu config sai |
| `Restart=on-abnormal` | Chỉ restart khi signal/timeout, không khi exit clean | Tốt cho service có scheduled shutdown |

**Best practice cho production**:
```ini
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5
```
→ Restart sau 5 giây, tối đa 5 lần trong 5 phút. Sau đó → failed state, cần manual intervention.

### 5.3. PID 1 trong Container

| Approach | Ưu điểm | Nhược điểm |
|----------|---------|------------|
| App là PID 1 | Simple, direct signal handling | App phải reap zombie processes |
| `tini` (init process) | Reap zombies, forward signals | Thêm 1 layer, nhưng overhead cực nhỏ |
| `dumb-init` | Tương tự tini | Ít maintained hơn tini |
| Bash script wrapper | Flexible | Signal forwarding phức tạp, dễ sai |

**Best practice**: Dùng `tini` hoặc Docker `--init` flag. Không dùng bash script wrapper cho PID 1.

### 5.4. Anti-patterns

1. **Kill -9 as first resort**: Dùng `SIGKILL` ngay → app không graceful shutdown → data loss
2. **Ignore signals trong code**: Không handle `SIGTERM` → 30s chờ rồi bị `SIGKILL`
3. **Infinite restart loop**: `Restart=always` + `RestartSec=0` → CPU spike khi config sai
4. **Large cleanup in signal handler**: Signal handler chỉ set flag, cleanup ở main loop
5. **Logging in signal handler**: Signal handler async-signal-unsafe → dùng `write()` thay `printf()`

---

## 6. Performance & Scalability ⭐

### 6.1. Performance Implications

| Quyết định | Impact |
|-----------|--------|
| Fork nhiều child processes | Memory tăng (copy-on-write giảm thiểu), PID table có limit |
| File descriptor limit thấp | Connection throughput bị giới hạn (mỗi connection = 1 fd) |
| Không dùng epoll/kqueue | Mỗi fd cần poll riêng → O(n) thay vì O(1) |
| Graceful shutdown timeout dài | Deploy chậm, node drain chậm |

### 6.2. Bottleneck thường gặp

- **File descriptor exhaustion**: Default 1024, high-traffic service cần 65535+
- **PID exhaustion**: Default 32768, container-heavy system cần tăng
- **Zombie accumulation**: Parent không reap → PID table đầy
- **Signal queue overflow**: Quá nhiều signals → bị drop

### 6.3. Tuning cho high-traffic

```bash
# Tăng file descriptor limit (system-wide)
echo "fs.file-max = 2097152" >> /etc/sysctl.conf

# Tăng file descriptor limit (per-process, trong systemd unit)
# LimitNOFILE=65535

# Tăng PID limit
echo "kernel.pid_max = 4194304" >> /etc/sysctl.conf

# Tăng socket backlog
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf

# Apply
sysctl -p
```

---

## 7. Security & Reliability Considerations

### Security

- **Least privilege**: Service chạy dưới user riêng, KHÔNG chạy root. systemd: `User=appuser`.
- **Capability dropping**: Chỉ giữ Linux capabilities cần thiết. `CapabilityBoundingSet=CAP_NET_BIND_SERVICE` nếu cần bind port < 1024.
- **Seccomp**: Giới hạn system calls mà process được phép gọi.
- **/proc exposure**: Trong container, `/proc` có thể leak host info → dùng `procMount: Unmasked` cẩn thận.
- **Environment variables vs files**: Secrets trong env var visible qua `/proc/<pid>/environ` → prefer mounted files.

### Reliability

- **Process health check**: systemd `WatchdogSec=30` — service phải notify watchdog định kỳ.
- **Pre/post Start/Stop**: `ExecStartPre` để check dependencies, `ExecStopPost` để cleanup.
- **Journal persistent**: `Storage=persistent` trong journald config để logs survive reboot.
- **Core dump**: Configure `coredump` để capture crash dumps cho post-mortem analysis.

---

## 8. Hands-on Example

### 8.1. Viết Golang Service xử lý SIGTERM

Chuẩn bị workspace local-first:

```bash
mkdir -p ~/devops-labs/graceful-server
cd ~/devops-labs/graceful-server
go version
```

**Expected output**: `go version go...` xác nhận máy có Go runtime. Nếu chưa có Go, đọc code và chạy bản Node.js ở phần 8.2.

Tạo file `main.go` trong `~/devops-labs/graceful-server`:

```go
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

var requestCount int64

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		count := atomic.AddInt64(&requestCount, 1)
		// Simulate processing time
		time.Sleep(2 * time.Second)
		fmt.Fprintf(w, "Request #%d processed by PID %d\n", count, os.Getpid())
	})

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprintln(w, "OK")
	})

	server := &http.Server{
		Addr:    ":8080",
		Handler: mux,
	}

	// Channel to listen for OS signals
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)

	// Start server in goroutine
	go func() {
		log.Printf("Server starting on :8080 (PID: %d)", os.Getpid())
		if err := server.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for signal
	sig := <-sigChan
	log.Printf("Received signal: %s", sig)
	log.Println("Starting graceful shutdown...")

	// Create context with timeout for shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// Graceful shutdown: finish in-flight requests
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("Shutdown error: %v", err)
	}

	log.Printf("Server stopped. Total requests served: %d", atomic.LoadInt64(&requestCount))
}
```

**Chạy và test**:

```bash
# Terminal 1: Run server
cd ~/devops-labs/graceful-server
go build -o graceful-server main.go
./graceful-server

# Terminal 2: Send requests
curl http://localhost:8080/
# Output: Request #1 processed by PID 12345

# Terminal 3: Send SIGTERM while request is in-flight
# Gửi request (takes 2 seconds)
curl http://localhost:8080/ &

# Immediately send SIGTERM
kill -SIGTERM $(pgrep -f "devops-labs/graceful-server/graceful-server|./graceful-server" | head -1)
```

**Expected output Terminal 1:**
```
2024/01/15 10:00:00 Server starting on :8080 (PID: 12345)
2024/01/15 10:00:05 Received signal: terminated
2024/01/15 10:00:05 Starting graceful shutdown...
2024/01/15 10:00:07 Server stopped. Total requests served: 2
```

**Verify**: Request đang in-flight vẫn nhận response (không bị drop).

Verify thêm health endpoint:

```bash
curl -i http://localhost:8080/health
```

**Expected output**:

```text
HTTP/1.1 200 OK
...
OK
```

Binary `./graceful-server` ở bước trên cũng sẽ được dùng cho `systemd`.

### 8.2. Viết Node.js Service tương tự

Tạo workspace và file `index.js`:

```bash
mkdir -p ~/devops-labs/graceful-server-node
cd ~/devops-labs/graceful-server-node
node --version
```

```javascript
const http = require('http');

let requestCount = 0;
let isShuttingDown = false;

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(isShuttingDown ? 503 : 200);
    res.end(isShuttingDown ? 'Shutting down' : 'OK');
    return;
  }

  requestCount++;
  const count = requestCount;
  console.log(`Processing request #${count}`);

  // Simulate processing
  setTimeout(() => {
    res.writeHead(200);
    res.end(`Request #${count} processed by PID ${process.pid}\n`);
  }, 2000);
});

server.listen(8080, () => {
  console.log(`Server starting on :8080 (PID: ${process.pid})`);
});

function gracefulShutdown(signal) {
  console.log(`Received ${signal}. Starting graceful shutdown...`);
  isShuttingDown = true;

  server.close(() => {
    console.log(`Server stopped. Total requests: ${requestCount}`);
    process.exit(0);
  });

  // Force exit after 15 seconds
  setTimeout(() => {
    console.error('Forced shutdown after timeout');
    process.exit(1);
  }, 15000);
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
```

**Chạy/verify Node.js**:

```bash
cd ~/devops-labs/graceful-server-node
node index.js &
NODE_PID=$!
sleep 1
curl -s http://localhost:8080/health
kill -SIGTERM "$NODE_PID"
wait "$NODE_PID" 2>/dev/null || true
```

**Expected output**:

```text
OK
Received SIGTERM. Starting graceful shutdown...
Server stopped. Total requests: 0
```

### 8.3. Tạo systemd User Unit File

Để giữ bài thực hành local-first và không cần tạo `appuser`/ghi vào `/opt`, dùng `systemd --user`. Tạo file `~/.config/systemd/user/graceful-server.service`:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/graceful-server.service <<'EOF'
[Unit]
Description=Graceful HTTP Server (user service)
Documentation=https://example.com/docs
After=default.target

[Service]
Type=simple
WorkingDirectory=%h/devops-labs/graceful-server
ExecStartPre=/usr/bin/test -f %h/devops-labs/graceful-server/main.go
ExecStartPre=/usr/bin/test -x %h/devops-labs/graceful-server/graceful-server
ExecStart=%h/devops-labs/graceful-server/graceful-server
ExecStop=/bin/kill -SIGTERM $MAINPID

Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5
TimeoutStopSec=30

# Resource limits
LimitNOFILE=65535
LimitNPROC=4096

# Basic hardening usable for user units on most systemd distros
NoNewPrivileges=yes
PrivateTmp=yes

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=graceful-server

[Install]
WantedBy=default.target
EOF
```

Nếu cần triển khai production system service, bản root-level tương đương sẽ đặt ở `/etc/systemd/system/graceful-server.service`, dùng `User=appuser`, `WorkingDirectory=/opt/graceful-server`, tạo trước user/directory bằng IaC hoặc config management.

```ini
[Unit]
Description=Graceful HTTP Server
Documentation=https://example.com/docs
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/opt/graceful-server

ExecStartPre=/usr/bin/test -f /opt/graceful-server/main.go
ExecStartPre=/usr/bin/test -x /opt/graceful-server/graceful-server
ExecStart=/opt/graceful-server/graceful-server
ExecStop=/bin/kill -SIGTERM $MAINPID

Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5

# Graceful shutdown timeout (match Kubernetes terminationGracePeriodSeconds)
TimeoutStopSec=30

# Resource limits
LimitNOFILE=65535
LimitNPROC=4096

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/graceful-server/logs

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=graceful-server

# Environment
Environment=PORT=8080
EnvironmentFile=-/opt/graceful-server/.env

[Install]
WantedBy=multi-user.target
```

**Chạy và quản lý**:

```bash
# Reload systemd sau khi tạo/sửa unit file
systemctl --user daemon-reload

# Start service
systemctl --user start graceful-server

# Check status
systemctl --user status graceful-server --no-pager

# View logs
journalctl --user -u graceful-server -f

# Test graceful shutdown
systemctl --user stop graceful-server

# Enable auto-start on boot
systemctl --user enable graceful-server
```

**Expected output khi status healthy**:

```text
Active: active (running)
Main PID: 12345 (go)
```

**Verify**:

```bash
systemctl --user is-active graceful-server
curl -s http://localhost:8080/health
```

**Expected output**:

```text
active
OK
```

### 8.4. Debug process bằng /proc và lsof

```bash
# Tìm PID của service
PID=$(systemctl --user show -p MainPID --value graceful-server)
echo "$PID"
# Output: 12345

# Xem file descriptors
ls -la /proc/$PID/fd/
# Output:
# lr-x------ 1 learner learner 64 Jan 15 10:00 0 -> /dev/null
# l-wx------ 1 learner learner 64 Jan 15 10:00 1 -> 'pipe:[12345]'
# l-wx------ 1 learner learner 64 Jan 15 10:00 2 -> 'pipe:[12346]'
# lrwx------ 1 learner learner 64 Jan 15 10:00 3 -> socket:[12347]

# Đếm file descriptors
ls /proc/$PID/fd/ | wc -l

# Xem chi tiết connections
lsof -p "$PID"
# Output:
# COMMAND   PID    USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
# main     12345 learner  3u  IPv6 12347  0t0      TCP *:8080 (LISTEN)

# Xem memory info
grep -E "VmRSS|VmSize|Threads" /proc/$PID/status
# Output:
# VmSize:   1234567 kB  (virtual memory)
# VmRSS:     56789 kB  (resident/physical memory)
# Threads:       8

# Xem command line
tr '\0' ' ' < /proc/$PID/cmdline
# Output: /home/learner/devops-labs/graceful-server/graceful-server

# Xem environment variables
tr '\0' '\n' < /proc/$PID/environ | head -10

# Xem network connections
ss -tlnp | grep "$PID"
# Output: LISTEN  0  128  *:8080  *:*  users:(("main",pid=12345,fd=3))
```

### Cleanup

```bash
# Stop service
systemctl --user stop graceful-server 2>/dev/null || true
systemctl --user disable graceful-server 2>/dev/null || true

# Remove unit file
rm -f ~/.config/systemd/user/graceful-server.service
systemctl --user daemon-reload

# Remove code
rm -rf ~/devops-labs/graceful-server
rm -rf ~/devops-labs/graceful-server-node
```

---

## 9. Common Pitfalls & Debugging

### 9.1. Pitfall: "Too many open files" trong production

**Dấu hiệu**:
- Log: `accept: too many open files` hoặc `EMFILE`
- Service từ chối connection mới
- Response time tăng vọt

**Debug flow**:
```bash
# 1. Tìm process
pgrep -a myservice

# 2. Đếm fd hiện tại
ls /proc/<pid>/fd | wc -l

# 3. Xem limit
cat /proc/<pid>/limits | grep "open files"
# Output: Max open files  1024  1024  files

# 4. Xem fd nào đang mở
lsof -p <pid> | tail -20

# 5. Phân loại fd
lsof -p <pid> | awk '{print $5}' | sort | uniq -c | sort -rn
# Output:
#  850 IPv4    ← quá nhiều connections! có thể leak
#  120 REG     ← files
#    3 CHR     ← stdin/stdout/stderr
```

**Fix**:
- Short-term: Tăng `LimitNOFILE` trong systemd unit
- Long-term: Fix connection leak trong code (close idle connections, connection pool limit)

### 9.2. Pitfall: Container không graceful shutdown

**Dấu hiệu**:
- Kubernetes pod mất đúng 30s để terminate (bằng `terminationGracePeriodSeconds`)
- Client nhận `Connection reset` thay vì proper response
- Data inconsistency sau restart

**Debug flow**:
```bash
# 1. Kiểm tra PID 1 trong container
docker exec <container> cat /proc/1/cmdline | tr '\0' ' '

# 2. Nếu PID 1 là shell script → signal không forward đến app
# Fix: dùng exec trong entrypoint
# BAD:  #!/bin/sh \n ./myapp
# GOOD: #!/bin/sh \n exec ./myapp

# 3. Test signal handling
docker kill --signal=SIGTERM <container>
docker logs -f <container>
# Xem app có log "Received SIGTERM" không
```

### 9.3. Pitfall: Zombie processes trong container

**Dấu hiệu**:
```bash
ps aux | grep defunct
# Output: appuser  1234  0.0  0.0  0    0 ?  Z  10:00  0:00 [worker] <defunct>
```

**Root cause**: PID 1 trong container không reap child processes.

**Fix**:
```dockerfile
# Option 1: Dùng tini
RUN apt-get install -y tini
ENTRYPOINT ["tini", "--"]
CMD ["./myapp"]

# Option 2: Docker --init flag
# docker run --init myimage

# Option 3: Handle SIGCHLD trong code
```

### 9.4. Case Study: Node.js connection leak gây OOM

**Context**: E-commerce platform, Node.js API server, PostgreSQL database. Traffic ~500 RPS.

**Symptom**: Server memory tăng dần 50MB/giờ, sau 24h → OOMKilled. File descriptor count cũng tăng tương ứng.

**Investigation**:
```bash
# Theo dõi fd count theo thời gian
watch -n 5 'ls /proc/$(pgrep node)/fd | wc -l'
# fd count: 1200... 1500... 2000... (tăng đều)

# Xem loại fd
lsof -p $(pgrep node) | grep TCP | grep ESTABLISHED | wc -l
# 1800 established connections → chỉ có 100 expected!

# Xem connections đến đâu
lsof -p $(pgrep node) | grep TCP | awk '{print $9}' | sort | uniq -c | sort -rn
# 1700 postgresql:5432  ← connection leak to DB!
#  100 *:8080           ← normal client connections
```

**Root cause**: Code path có `try-catch` nhưng trong `catch` block không release database connection.

**Fix**: Dùng `finally` block để đảm bảo connection luôn được release.

**Prevention**: Monitor fd count per process, alert khi > threshold.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 1: DevOps, SRE, Platform Engineering
- Day 1 đặt nền tảng **vì sao** cần vận hành tốt (DevOps culture, DORA metrics, SRE practices).
- Day 2 bắt đầu **kiến thức kỹ thuật nền tảng** — process và signal là building blocks cho mọi thứ phía sau.

### Bài sau — Day 3: Linux Networking Fundamentals
- Day 2 giải thích process và file descriptor → Day 3 mở rộng sang **network socket** (cũng là file descriptor).
- Graceful shutdown (Day 2) liên quan trực tiếp đến **connection draining** (Day 3) — cách close network connections gracefully.
- systemd unit file (Day 2) sẽ kết hợp với **service binding network ports** (Day 3).

---

## 11. Tài liệu tham khảo

### Must-read
- **Linux man pages**: `man 7 signal`, `man 5 proc`, `man systemd.service`
- **"How Linux Works" by Brian Ward** — Chapter 2 (Processes), Chapter 10 (Networking) — giải thích rõ ràng cho developer.
- **Kubernetes Pod Lifecycle**: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/ — Hiểu signal handling trong K8s context.

### Nice-to-have
- **systemd for Administrators**: http://0pointer.de/blog/projects/systemd-for-admins-1.html — Series 21 bài chi tiết.
- **"The Linux Programming Interface" by Michael Kerrisk** — Bible cho Linux programming, chapters về signals và file descriptors.
- **Docker init (tini)**: https://github.com/krallin/tini — Vì sao cần init process trong container.

### Deep-dive
- **strace cheat sheet**: https://strace.io/ — Debug system calls để hiểu process behavior.
- **Brendan Gregg's Linux Performance Tools**: https://brendangregg.com/linuxperf.html — Overview toàn bộ performance tools.
- **systemd by Example**: https://systemd-by-example.com/ — Interactive learning cho systemd.

