# Day 7: Document — Linux/Networking/Automation Command Cheat Sheet

## 1. Process Management (Day 2)

### Xem process

```bash
# List tất cả process
ps aux                          # BSD format, full detail
ps -ef                          # POSIX format

# Tìm process theo tên
ps aux | grep demo-api
pgrep -f demo-api               # Chỉ trả PID
pgrep -af demo-api              # PID + command line

# Process tree
ps auxf                         # Tree format
pstree -p                       # Visual tree với PID

# Top process theo resource
top -b -n 1 -o %MEM | head -15  # Sort theo memory
top -b -n 1 -o %CPU | head -15  # Sort theo CPU
```

### Kill process

```bash
kill PID                        # SIGTERM (graceful)
kill -9 PID                     # SIGKILL (force - last resort)
kill -HUP PID                   # SIGHUP (reload config)

pkill -f "node server"          # Kill theo pattern
killall demo-api                # Kill theo tên

# Verify process đã chết
kill -0 PID 2>/dev/null && echo "alive" || echo "dead"
```

### File Descriptors

```bash
# Đếm FD của process
ls /proc/PID/fd | wc -l

# Xem chi tiết FD
ls -la /proc/PID/fd

# Xem file đang mở
lsof -p PID                     # Tất cả file
lsof -p PID | wc -l             # Đếm
lsof -i -P -n | grep PID       # Network connections
```

---

## 2. systemd Commands (Day 2)

```bash
# Service lifecycle
sudo systemctl start demo-api
sudo systemctl stop demo-api
sudo systemctl restart demo-api
sudo systemctl reload demo-api     # Reload config (nếu support)
sudo systemctl status demo-api

# Enable/disable auto-start
sudo systemctl enable demo-api     # Start on boot
sudo systemctl disable demo-api    # Don't start on boot

# Unit file management
sudo systemctl daemon-reload       # Sau khi sửa unit file
systemctl cat demo-api             # Xem unit file
systemctl show demo-api            # Xem tất cả properties
systemctl list-dependencies demo-api

# Logs
journalctl -u demo-api              # Tất cả logs
journalctl -u demo-api -f           # Follow (tail -f)
journalctl -u demo-api --since "5 min ago"
journalctl -u demo-api --since "2024-01-15 10:00"
journalctl -u demo-api -n 50        # 50 dòng cuối
journalctl -u demo-api -p err       # Chỉ errors
journalctl -u demo-api --no-pager   # Không paginate

# Troubleshooting
systemctl is-active demo-api        # active/inactive
systemctl is-enabled demo-api       # enabled/disabled
systemctl is-failed demo-api        # failed/active
systemctl list-units --failed       # Tất cả units bị fail
```

---

## 3. Network Debugging (Day 3)

### DNS

```bash
# DNS lookup
dig google.com                    # Full DNS query
dig google.com +short             # Chỉ IP
dig @8.8.8.8 google.com           # Query DNS server cụ thể
dig google.com A                  # A record
dig google.com AAAA               # IPv6
dig google.com MX                 # Mail server
dig google.com NS                 # Nameserver
dig google.com +trace             # Full resolution path

nslookup google.com               # Simple lookup
host google.com                   # Simple lookup

# DNS config
cat /etc/resolv.conf              # DNS server config
cat /etc/hosts                    # Local DNS override
```

### HTTP/Connection Testing

```bash
# curl — HTTP client
curl -s http://localhost:8080/health                     # Silent
curl -v http://localhost:8080/health                     # Verbose (headers)
curl -w "HTTP %{http_code} in %{time_total}s\n" -o /dev/null -s URL  # Timing
curl --connect-timeout 5 --max-time 10 URL               # Timeouts
curl -H "Content-Type: application/json" -d '{}' URL     # POST JSON
curl -I URL                                               # HEAD only

# Connection timing breakdown
curl -w "\
  DNS:        %{time_namelookup}s\n\
  Connect:    %{time_connect}s\n\
  TLS:        %{time_appconnect}s\n\
  Start:      %{time_starttransfer}s\n\
  Total:      %{time_total}s\n\
  HTTP Code:  %{http_code}\n" \
  -o /dev/null -s http://localhost:8080/health
```

### Port & Socket

```bash
# ss — Socket Statistics (thay thế netstat)
ss -tlnp                         # TCP listening ports với process
ss -ulnp                         # UDP listening ports
ss -tnp                          # TCP established connections
ss -s                            # Socket statistics summary
ss -tnp | grep :8080             # Connections trên port 8080

# Kiểm tra port cụ thể
ss -tlnp | grep :8080            # Ai đang listen port 8080

# lsof — List Open Files
lsof -i :8080                    # Process trên port 8080
lsof -i -P -n                   # Tất cả network connections
lsof -i TCP:8080                 # TCP connections trên port 8080
```

### Packet Capture

```bash
# tcpdump — Capture packets
sudo tcpdump -i any port 8080 -n         # Capture traffic port 8080
sudo tcpdump -i any port 8080 -A         # Với payload (ASCII)
sudo tcpdump -i any port 8080 -X         # Với payload (hex+ASCII)
sudo tcpdump -i any port 8080 -c 10      # Capture 10 packets
sudo tcpdump -i any port 8080 -w /tmp/capture.pcap  # Save to file

# Connectivity test
ping -c 3 google.com              # ICMP ping
traceroute google.com             # Route tracing
nc -zv localhost 8080              # TCP port check
```

---

## 4. Performance Tools (Day 4)

### CPU

```bash
# Overview
top -b -n 1 | head -20           # Snapshot
htop                              # Interactive (nếu có)

# CPU usage
mpstat -P ALL 1 3                 # Per-CPU usage
uptime                            # Load average

# Process CPU
pidstat -u 1 5                    # CPU per process
```

### Memory

```bash
# Overview
free -h                           # Human readable
free -m                           # Megabytes

# Detailed
cat /proc/meminfo | head -10
vmstat 1 5                        # Virtual memory stats

# Process memory
pidstat -r 1 5                    # Memory per process
pmap PID                          # Memory map of process
```

### Disk I/O

```bash
# Usage
df -h                             # Filesystem usage
du -sh /opt/demo-api              # Directory size

# I/O performance
iostat -x 1 3                     # Extended I/O stats
iotop -b -n 3                     # I/O per process

# File system
lsof +D /opt/demo-api            # Files open in directory
```

### System Overview

```bash
# vmstat — Virtual Memory Statistics
vmstat 1 5
# Columns: r(run queue), b(blocked), swpd, free, si/so(swap), bi/bo(block I/O)

# dmesg — Kernel messages
dmesg | tail -20                  # Recent messages
dmesg | grep -i oom               # OOM killer events
dmesg | grep -i error             # Errors

# uptime
uptime                            # Load average 1/5/15 min
```

### strace — System Call Tracing

```bash
# Trace running process
strace -p PID                     # All syscalls
strace -p PID -e trace=network    # Network only
strace -p PID -e trace=file       # File access only
strace -p PID -c                  # Summary (statistics)
strace -p PID -T                  # Show time spent

# Trace new process
strace -f ./demo-api              # Follow child processes
```

---

## 5. Bash Automation Patterns (Day 5)

### Script Template

```bash
#!/bin/bash
set -euo pipefail  # Exit on error, undefined var, pipe failure

# Logging
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Cleanup on exit
cleanup() {
    log "Cleaning up..."
    # kill background processes, remove temp files, etc.
}
trap cleanup EXIT

# Main logic here
main() {
    log "Script started"
    # ...
    log "Script completed"
}

main "$@"
```

### Common Patterns

```bash
# Retry with backoff
retry() {
    local max_attempts="${1:-3}"
    local delay="${2:-5}"
    shift 2
    local attempt=1
    while [ $attempt -le "$max_attempts" ]; do
        if "$@"; then return 0; fi
        echo "Attempt $attempt/$max_attempts failed, retrying in ${delay}s..."
        sleep "$delay"
        delay=$((delay * 2))
        attempt=$((attempt + 1))
    done
    return 1
}
# Usage: retry 3 5 curl -sf http://localhost:8080/health

# Check command exists
require_cmd() {
    command -v "$1" &>/dev/null || { echo "ERROR: $1 not found"; exit 1; }
}
# Usage: require_cmd curl; require_cmd jq

# Timeout wrapper
timeout 10 curl -s http://localhost:8080/health || echo "Timeout!"

# Lock file (prevent duplicate runs)
LOCKFILE="/tmp/my-script.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "Already running"; exit 1; }
```

---

## 6. Runbook Template

```markdown
# Runbook: [Incident Type]

## Quick Reference
- **Service**: [service name]
- **Port**: [port]
- **Log location**: `journalctl -u service-name`
- **Config**: `/opt/service/config.yaml`
- **Owner**: [team/person]
- **Escalation**: [contact]

## Symptom
- [What does the user/alert see?]

## Triage (< 2 minutes)
1. `systemctl status service-name` → Is it running?
2. `curl -s http://localhost:PORT/health` → Is it responding?
3. `journalctl -u service-name --since "5 min ago" -n 20` → Recent errors?

## Diagnosis
| Observation | Likely Cause | Next Step |
|-------------|--------------|-----------|
| Process not running | Crash/OOM | Check logs, dmesg |
| Port not listening | Config error / port conflict | Check ss -tlnp |
| HTTP 500 | Application error | Check app logs |
| HTTP timeout | Resource exhaustion | Check top, iostat |

## Resolution
### Cause A: [Description]
```bash
# Fix commands
```

### Cause B: [Description]
```bash
# Fix commands
```

## Verification
```bash
# Commands to verify service is healthy
curl -s http://localhost:PORT/health
systemctl status service-name
```

## Escalation
- If not resolved in 15 min → escalate to [team]
- If data loss suspected → notify [person]

## Post-incident
- [ ] Update incident timeline
- [ ] Schedule postmortem (within 48h)
- [ ] Create action items
```

---

## 7. Quick Reference: Error → Tool Mapping

| Triệu chứng | Đầu tiên kiểm tra | Tool |
|---|---|---|
| Connection refused | Process có đang chạy? | `ps aux`, `systemctl status` |
| Connection timeout | Network reachable? | `ping`, `traceroute`, `ss` |
| DNS resolution failed | DNS config đúng? | `dig`, `cat /etc/resolv.conf` |
| Port already in use | Ai chiếm port? | `ss -tlnp`, `lsof -i :PORT` |
| Service slow | CPU/Memory/Disk? | `top`, `vmstat`, `iostat` |
| Service OOM killed | Memory limit? | `dmesg \| grep oom`, `free -h` |
| Permission denied | User/ownership? | `ls -la`, `id`, `namei -l path` |
| Disk full | Disk usage? | `df -h`, `du -sh /*` |
| Too many open files | FD limit? | `ulimit -n`, `lsof -p PID \| wc -l` |
| High load average | CPU bound? I/O wait? | `uptime`, `vmstat`, `iostat` |

---

## 8. USE Method Checklist (Day 4 Recap)

**U**tilization — **S**aturation — **E**rrors cho mỗi resource:

| Resource | Utilization | Saturation | Errors |
|----------|-------------|------------|--------|
| **CPU** | `mpstat -P ALL 1` | `vmstat 1` (r column) | `dmesg \| grep error` |
| **Memory** | `free -h` | `vmstat 1` (si/so) | `dmesg \| grep oom` |
| **Disk** | `df -h`, `iostat -x 1` | `iostat -x 1` (avgqu-sz) | `dmesg \| grep I/O` |
| **Network** | `ss -s`, `sar -n DEV 1` | `ss -tnp \| wc -l` | `netstat -s \| grep error` |

---

## 9. Troubleshooting Decision Tree

```
Service unhealthy
│
├── Process running?
│   ├── No → Check journalctl → Fix & restart
│   └── Yes ↓
│
├── Port listening?
│   ├── No → Port conflict? → ss -tlnp → Kill conflicting process
│   └── Yes ↓
│
├── HTTP responding?
│   ├── No (connection refused) → App crashed after bind? → Check logs
│   ├── No (timeout) → Check: CPU? Memory? Disk? Network? → USE method
│   ├── Yes (5xx) → Application error → Check app logs
│   └── Yes (200) → Service healthy ✅
│
└── Response slow?
    ├── CPU high → top → optimize/scale
    ├── Memory pressure → free -h → fix leak/add memory
    ├── Disk I/O → iostat → optimize queries/SSD
    └── Network → ss -s, tcpdump → check connectivity
```

