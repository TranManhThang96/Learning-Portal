# Day 2: Document — Linux Process, Signal & systemd Cheat Sheet

---

## 1. Process Management Commands

### Xem process

| Command | Mục đích | Ví dụ |
|---------|---------|-------|
| `ps aux` | Liệt kê tất cả processes | `ps aux \| grep nginx` |
| `ps auxf` | Process tree (forest) | `ps auxf` |
| `ps -eo pid,ppid,user,%cpu,%mem,stat,cmd` | Custom columns | Custom format |
| `pstree -p` | Process tree với PID | `pstree -p 1` |
| `pgrep -a <name>` | Tìm PID theo tên | `pgrep -a node` |
| `top` / `htop` | Real-time process monitor | `htop -p <pid>` |
| `pidof <name>` | Tìm PID chính xác | `pidof nginx` |

### Process states

| State | Ký hiệu | Mô tả |
|-------|---------|-------|
| Running | `R` | Đang chạy hoặc trong run queue |
| Sleeping | `S` | Interruptible sleep (chờ I/O, signal) |
| Disk Sleep | `D` | Uninterruptible sleep (chờ disk I/O) |
| Stopped | `T` | Stopped by signal (SIGSTOP/SIGTSTP) |
| Zombie | `Z` | Terminated nhưng parent chưa `wait()` |
| Dead | `X` | Dead (hiếm thấy trong `ps`) |

### Gửi Signal

| Command | Mô tả |
|---------|-------|
| `kill <pid>` | Gửi SIGTERM (default) |
| `kill -SIGTERM <pid>` | Gửi SIGTERM explicitly |
| `kill -SIGKILL <pid>` hoặc `kill -9 <pid>` | Force kill |
| `kill -SIGHUP <pid>` | Reload config |
| `kill -SIGUSR1 <pid>` | User-defined signal 1 |
| `kill -0 <pid>` | Check process exists (không gửi signal) |
| `killall <name>` | Kill tất cả process theo tên |
| `pkill -f <pattern>` | Kill theo pattern |

---

## 2. Signal Reference

```
Signal    Number  Default Action   Can Catch?  Common Usage
──────────────────────────────────────────────────────────────
SIGHUP      1     Terminate        Yes         Reload config
SIGINT      2     Terminate        Yes         Ctrl+C
SIGQUIT     3     Core dump        Yes         Ctrl+\, thread dump (Java)
SIGILL      4     Core dump        No*         Illegal instruction
SIGABRT     6     Core dump        Yes         abort()
SIGFPE      8     Core dump        Yes         Floating point error
SIGKILL     9     Terminate        NO          Force kill (cannot catch!)
SIGUSR1    10     Terminate        Yes         User-defined
SIGSEGV    11     Core dump        Yes*        Segfault
SIGUSR2    12     Terminate        Yes         User-defined
SIGPIPE    13     Terminate        Yes         Broken pipe
SIGALRM    14     Terminate        Yes         alarm() timer
SIGTERM    15     Terminate        Yes         Graceful shutdown
SIGCHLD    17     Ignore           Yes         Child status change
SIGCONT    18     Continue         Yes         Resume after stop
SIGSTOP    19     Stop             NO          Pause (cannot catch!)
SIGTSTP    20     Stop             Yes         Ctrl+Z
```

### Signal Handling trong Code

**Golang:**
```go
sigChan := make(chan os.Signal, 1)
signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)
sig := <-sigChan // blocks until signal received
```

**Node.js:**
```javascript
process.on('SIGTERM', () => { /* cleanup */ });
process.on('SIGINT', () => { /* cleanup */ });
```

**Python:**
```python
import signal
def handler(signum, frame):
    # cleanup
    pass
signal.signal(signal.SIGTERM, handler)
```

**Bash:**
```bash
trap 'echo "Caught SIGTERM"; cleanup; exit 0' SIGTERM
trap 'echo "Caught SIGINT"; cleanup; exit 0' SIGINT
```

---

## 3. File Descriptor Commands

| Command | Mục đích | Ví dụ |
|---------|---------|-------|
| `ls -la /proc/<pid>/fd/` | Liệt kê fd của process | `ls -la /proc/1234/fd/` |
| `ls /proc/<pid>/fd/ \| wc -l` | Đếm fd | Monitoring fd count |
| `lsof -p <pid>` | Chi tiết fd (file, socket, pipe) | `lsof -p 1234` |
| `lsof -i :8080` | Tìm process dùng port | `lsof -i :5432` |
| `lsof -u <user>` | fd theo user | `lsof -u appuser` |
| `cat /proc/<pid>/limits` | Xem fd limit của process | Resource limits |
| `ulimit -n` | Xem fd limit hiện tại (shell) | Default: 1024 |
| `ulimit -n 65535` | Set fd limit (session) | Tạm thời |
| `cat /proc/sys/fs/file-max` | System-wide fd limit | Global limit |
| `cat /proc/sys/fs/file-nr` | fd đang dùng / allocated / max | System health |

### File Descriptor Limit Configuration

```bash
# Per-session (temporary)
ulimit -n 65535

# Per-user (persistent) — /etc/security/limits.conf
appuser  soft  nofile  65535
appuser  hard  nofile  65535

# System-wide — /etc/sysctl.conf
fs.file-max = 2097152

# systemd service — unit file
[Service]
LimitNOFILE=65535
```

---

## 4. /proc Filesystem Quick Reference

```
/proc/<pid>/
├── cmdline        # Command line (null-separated)
│                  # cat /proc/<pid>/cmdline | tr '\0' ' '
├── cwd            # Symlink to current working directory
├── environ        # Environment variables (null-separated)
│                  # cat /proc/<pid>/environ | tr '\0' '\n'
├── exe            # Symlink to executable
├── fd/            # Directory of file descriptors (symlinks)
├── fdinfo/        # Details about each fd
├── limits         # Resource limits (soft/hard)
├── maps           # Memory mappings
├── mem            # Process memory (requires ptrace)
├── net/           # Network statistics
│   ├── tcp        # TCP connections
│   ├── udp        # UDP connections
│   └── dev        # Network device stats
├── oom_score      # OOM killer score (0-1000)
├── oom_score_adj  # OOM adjustment (-1000 to 1000)
├── root           # Symlink to root directory (chroot)
├── stat           # Process status (single line, for parsing)
├── statm          # Memory status (pages)
├── status         # Human-readable process status
│                  # Key fields: VmRSS, VmSize, Threads, State
├── task/          # Thread information
└── wchan          # Wait channel (what the process is waiting for)
```

### Useful /proc One-liners

```bash
# Memory usage (RSS in KB)
grep VmRSS /proc/<pid>/status | awk '{print $2}'

# Thread count
grep Threads /proc/<pid>/status | awk '{print $2}'

# Process state
grep State /proc/<pid>/status

# OOM score (higher = more likely to be killed)
cat /proc/<pid>/oom_score

# CPU info
cat /proc/cpuinfo | grep "model name" | head -1

# Memory total/free
grep -E "MemTotal|MemFree|MemAvailable" /proc/meminfo

# System load
cat /proc/loadavg

# Open file descriptors system-wide
cat /proc/sys/fs/file-nr
# Output: allocated   free   max
```

---

## 5. systemd Unit File Template

### Production-Ready Template

```ini
[Unit]
Description=My Application Service
Documentation=https://docs.example.com/my-app

# Dependencies
After=network-online.target postgresql.service
Wants=network-online.target
Requires=postgresql.service

# Ordering
Before=nginx.service

[Service]
# Service type
Type=simple
# Type=notify       # For services that signal readiness via sd_notify
# Type=forking      # For traditional daemons that fork

# User/Group
User=appuser
Group=appuser

# Working directory
WorkingDirectory=/opt/myapp

# Pre-start checks
ExecStartPre=/usr/bin/test -f /opt/myapp/config.yaml
ExecStartPre=/opt/myapp/bin/validate-config

# Main process
ExecStart=/opt/myapp/bin/server --config /opt/myapp/config.yaml

# Reload configuration
ExecReload=/bin/kill -SIGHUP $MAINPID

# Graceful stop
ExecStop=/bin/kill -SIGTERM $MAINPID

# Post-stop cleanup
ExecStopPost=/opt/myapp/bin/cleanup

# ── Restart Policy ──
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5

# ── Timeouts ──
TimeoutStartSec=30
TimeoutStopSec=30

# ── Resource Limits ──
LimitNOFILE=65535
LimitNPROC=4096
LimitCORE=infinity

# ── Watchdog ──
# WatchdogSec=30
# Requires sd_notify("WATCHDOG=1") from app

# ── Security Hardening ──
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictNamespaces=yes
ReadWritePaths=/opt/myapp/data /opt/myapp/logs

# ── Environment ──
Environment=APP_ENV=production
Environment=LOG_LEVEL=info
EnvironmentFile=-/opt/myapp/.env

# ── Logging ──
StandardOutput=journal
StandardError=journal
SyslogIdentifier=myapp

# ── cgroup limits ──
# MemoryMax=512M
# CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

### systemd Commands Cheat Sheet

```bash
# ── Service Management ──
systemctl start myapp          # Start service
systemctl stop myapp           # Stop service
systemctl restart myapp        # Restart service
systemctl reload myapp         # Reload config (SIGHUP)
systemctl status myapp         # Show status
systemctl enable myapp         # Enable auto-start on boot
systemctl disable myapp        # Disable auto-start

# ── Debugging ──
systemctl is-active myapp      # Check if running
systemctl is-enabled myapp     # Check if enabled
systemctl list-units --failed  # List failed units
systemctl show myapp           # Show all properties
systemctl cat myapp            # Show unit file content

# ── Journal/Logs ──
journalctl -u myapp            # All logs for service
journalctl -u myapp -f         # Follow/tail logs
journalctl -u myapp --since "1 hour ago"
journalctl -u myapp --since "2024-01-15 10:00" --until "2024-01-15 11:00"
journalctl -u myapp -p err     # Only error logs
journalctl -u myapp -o json    # JSON output
journalctl -u myapp --no-pager # Without pager

# ── Reload after edit ──
systemctl daemon-reload        # Reload unit files after changes

# ── Dependencies ──
systemctl list-dependencies myapp
systemctl list-dependencies --reverse myapp
```

---

## 6. Debug Decision Tree

```
Problem: Service not working
│
├── Process running?
│   ├── No  → systemctl status myapp
│   │        → journalctl -u myapp -n 50
│   │        → Check ExecStart path, permissions, config
│   │
│   └── Yes → Accepting connections?
│            ├── No  → ss -tlnp | grep <port>
│            │        → lsof -i :<port>
│            │        → Check firewall: iptables -L
│            │        → Check bind address (0.0.0.0 vs 127.0.0.1)
│            │
│            └── Yes → Performance issue?
│                     ├── High CPU → top -p <pid>
│                     │             → strace -c -p <pid>
│                     │
│                     ├── High Memory → grep VmRSS /proc/<pid>/status
│                     │               → Check for memory leak
│                     │
│                     ├── Too many open files → ls /proc/<pid>/fd | wc -l
│                     │                       → lsof -p <pid> | wc -l
│                     │                       → Check LimitNOFILE
│                     │
│                     └── Slow responses → Check dependencies (DB, cache)
│                                        → strace -e trace=network -p <pid>
│                                        → Check disk I/O: iostat
```

