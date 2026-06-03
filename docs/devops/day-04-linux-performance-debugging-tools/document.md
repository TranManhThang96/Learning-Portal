# Day 4: Document — Linux Performance Tools Cheat Sheet

---

## 1. USE Method Checklist cho Linux

### CPU

| Metric | Tool | Command |
|--------|------|---------|
| Utilization | `mpstat` | `mpstat -P ALL 1` — xem %usr, %sys, %idle per CPU |
| Utilization | `top` | `top` — xem %Cpu(s) line |
| Utilization | `vmstat` | `vmstat 1` — cột us, sy, id |
| Saturation | `vmstat` | `vmstat 1` — cột r (run queue) > num CPUs = saturated |
| Saturation | `/proc/loadavg` | `cat /proc/loadavg` — load > num cores = saturated |
| Errors | `perf` | `perf stat` — hardware errors (rare) |
| Per-process | `pidstat` | `pidstat 1` — CPU% per process |
| Per-process | `top` | `top -p <pid>` — single process |

### Memory

| Metric | Tool | Command |
|--------|------|---------|
| Utilization | `free` | `free -h` — xem "available" (NOT "free") |
| Utilization | `/proc/meminfo` | `grep -E "MemTotal\|MemAvailable" /proc/meminfo` |
| Saturation | `vmstat` | `vmstat 1` — cột si, so (swap in/out) > 0 = saturated |
| Saturation | `dmesg` | `dmesg \| grep -i oom` — OOM killer fired |
| Errors | `dmesg` | `dmesg \| grep -i "memory\|oom\|kill"` |
| Per-process | `/proc/<pid>/status` | `grep VmRSS /proc/<pid>/status` |
| Per-process | `pmap` | `pmap -x <pid>` — detailed memory map |

### Disk I/O

| Metric | Tool | Command |
|--------|------|---------|
| Utilization | `iostat` | `iostat -xz 1` — cột %util |
| Saturation | `iostat` | `iostat -xz 1` — cột avgqu-sz (queue size) > 1 |
| Saturation | `vmstat` | `vmstat 1` — cột wa (I/O wait) > 10% |
| Errors | `smartctl` | `smartctl -a /dev/sda` — disk health |
| Errors | `dmesg` | `dmesg \| grep -i "i/o error\|disk"` |
| Per-process | `iotop` | `sudo iotop -b -n 3` — I/O per process |
| Latency | `iostat` | `iostat -xz 1` — cột await (ms) |
| Throughput | `iostat` | `iostat -xz 1` — cột rMB/s, wMB/s |

### Network

| Metric | Tool | Command |
|--------|------|---------|
| Utilization | `sar` | `sar -n DEV 1` — rxkB/s, txkB/s |
| Utilization | `ip` | `ip -s link` — bytes sent/received |
| Saturation | `ss` | `ss -s` — connection count, overflows |
| Saturation | `netstat` | `netstat -s \| grep -i "overflow\|drop"` |
| Errors | `ip` | `ip -s link` — errors, drops, overruns |
| Errors | `netstat` | `netstat -s` — protocol-level errors |
| Connections | `ss` | `ss -tn state established \| wc -l` |

---

## 2. Tool Quick Reference

### top / htop

```
top output reading guide:
━━━━━━━━━━━━━━━━━━━━━━━━

top - 14:30:00 up 5 days, load average: 2.50, 2.10, 1.80
       ↑                                  ↑     ↑     ↑
    current time                      1min  5min  15min
                                     (trend: decreasing = improving)

Tasks: 250 total, 2 running, 248 sleeping, 0 stopped, 0 zombie
                   ↑                                    ↑
              active CPU            zombie > 0 = parent not reaping

%Cpu(s): 25.0 us, 5.0 sy, 0.0 ni, 68.0 id, 1.5 wa, 0.0 hi, 0.5 si
         ↑        ↑                 ↑        ↑
     user code  kernel          idle     I/O wait (disk bottleneck?)

MiB Mem:  16384.0 total,  500.0 free, 8000.0 used, 7884.0 buff/cache
MiB Swap:  4096.0 total, 4096.0 free,    0.0 used. 7500.0 avail Mem
                                                     ↑
                                              THIS is what matters
```

### vmstat

```bash
vmstat 1
# Output columns:
# procs ─────memory──────── ───swap── ────io─── ─system── ──────cpu──────
#  r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs  us sy id wa
#  2  0      0 500000 200000 7000000   0    0    10   100  500 1000  25  5 68  2
#  ↑  ↑                              ↑↑         ↑↑              ↑↑  ↑↑  ↑
#  │  │                              ││         ││              ││  ││  └─ I/O wait
#  │  │                              ││         ││              ││  └─ kernel CPU
#  │  │                              ││         ││              └─ user CPU
#  │  │                              ││         └─ blocks out (write)
#  │  │                              ││         └── blocks in (read)
#  │  │                              └─ swap out (memory pressure!)
#  │  │                              └── swap in  (memory pressure!)
#  │  └── blocked (waiting I/O)
#  └── run queue (> cores = CPU saturated)
```

### iostat

```bash
iostat -xz 1
# Output columns:
# Device  r/s    w/s   rMB/s  wMB/s  rrqm/s  wrqm/s  await  r_await  w_await  svctm  %util
# sda     50.0  100.0  0.5    10.0   0.0     5.0     2.5    1.0      3.5      1.0    85.0
#         ↑      ↑            ↑                       ↑                               ↑
#     reads/s writes/s    write MB/s              avg latency                    utilization
#
# Key thresholds:
#   await > 10ms for SSD      → investigate
#   await > 50ms for HDD      → investigate
#   %util > 80%                → approaching saturation
#   avgqu-sz > 1               → requests queuing
```

---

## 3. Decision Tree: "Service is Slow"

```
Service is slow!
│
├── Step 1: RED Analysis (Service Level)
│   ├── Rate changed? → Traffic spike?
│   ├── Errors increased? → Check error logs
│   └── Duration increased? → Which percentile? (P50 vs P99)
│
├── Step 2: USE Analysis (System Level)
│   │
│   ├── CPU saturated?
│   │   ├── top → high %usr → App code issue / GC
│   │   ├── top → high %sys → Too many syscalls / context switches
│   │   └── top → high %wa  → Actually disk I/O issue, not CPU ←──┐
│   │                                                              │
│   ├── Memory pressure?                                           │
│   │   ├── free → available low → Memory leak?                    │
│   │   ├── vmstat → si/so > 0 → Swapping (very slow!)            │
│   │   └── dmesg → OOM kill → Process killed                     │
│   │                                                              │
│   ├── Disk I/O saturated? ───────────────────────────────────────┘
│   │   ├── iostat → %util > 80% → Disk busy
│   │   ├── iostat → await high → Slow disk
│   │   └── Check: are you on SSD or HDD?
│   │
│   └── Network issue?
│       ├── ss → many TIME_WAIT → Connection churn
│       ├── ss → many CLOSE_WAIT → Connection leak in app
│       ├── curl timing → DNS slow? → DNS issue
│       └── curl timing → Connect slow? → Network/firewall
│
├── Step 3: Deep Dive
│   ├── strace -c -p <pid> → Which syscalls take time?
│   ├── perf top → Which functions use CPU?
│   ├── lsof -p <pid> → What files/sockets are open?
│   └── Application logs → Error patterns?
│
└── Step 4: Fix & Verify
    ├── Apply fix
    ├── Compare metrics before/after
    └── Write incident report
```

---

## 4. Performance Numbers Every Engineer Should Know

```
Latency Comparison Numbers (approximate)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L1 cache reference                         0.5 ns
L2 cache reference                           7 ns
Main memory reference                      100 ns
SSD random read                        150,000 ns  =  150 μs
HDD seek                            10,000,000 ns  =   10 ms
Network round trip (same datacenter)    500,000 ns  =  500 μs
Network round trip (cross-region)    80,000,000 ns  =   80 ms
Network round trip (cross-continent)150,000,000 ns  =  150 ms

Throughput Numbers:
━━━━━━━━━━━━━━━━━━
HDD sequential read:        100-200 MB/s
SSD sequential read:        500-3500 MB/s (NVMe)
Network (1 Gbps):            125 MB/s
Network (10 Gbps):          1250 MB/s
Memory bandwidth:          10-50 GB/s

IOPS:
━━━━━
HDD:                   100-200 IOPS
SSD (SATA):         10,000-100,000 IOPS
SSD (NVMe):        100,000-1,000,000 IOPS

Context:
  1 DB query ≈ 1-10ms (indexed) or 100ms-10s (full scan)
  1 HTTP request ≈ 10ms-500ms
  1 DNS lookup ≈ 1ms (cached) or 50-200ms (uncached)
  1 TLS handshake ≈ 30-100ms
```

---

## 5. One-Liner Recipes

```bash
# ═══ Top 10 CPU consumers ═══
ps aux --sort=-%cpu | head -11

# ═══ Top 10 memory consumers ═══
ps aux --sort=-%mem | head -11

# ═══ Process count per user ═══
ps aux | awk '{print $1}' | sort | uniq -c | sort -rn | head -10

# ═══ Open files per process (top 10) ═══
lsof 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -rn | head -10

# ═══ Disk usage top directories ═══
du -h --max-depth=1 / 2>/dev/null | sort -hr | head -10

# ═══ Network connections per state ═══
ss -tn | awk '{print $1}' | sort | uniq -c | sort -rn

# ═══ Network connections per remote IP ═══
ss -tn state established | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn | head -10

# ═══ System uptime + load ═══
uptime

# ═══ Recent OOM kills ═══
dmesg | grep -i "oom\|killed process" | tail -5

# ═══ Largest files modified in last 24h ═══
find / -mtime -1 -type f -size +100M 2>/dev/null | head -10

# ═══ Quick health check ═══
echo "=== Load ===" && cat /proc/loadavg && \
echo "=== Memory ===" && free -h | grep Mem && \
echo "=== Disk ===" && df -h / && \
echo "=== TCP ===" && ss -s | grep TCP
```

---

## 6. Monitoring Script Template

```bash
#!/bin/bash
# quick-monitor.sh — Run every minute via cron
# Usage: */1 * * * * /opt/scripts/quick-monitor.sh >> /var/log/monitor.log

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
HOSTNAME=$(hostname)

# Thresholds
CPU_WARN=80
MEM_WARN=85
DISK_WARN=90
LOAD_WARN=$(nproc)

# Collect
LOAD=$(cat /proc/loadavg | awk '{print $1}')
MEM_PCT=$(free | awk '/Mem:/{printf "%.0f", ($2-$7)/$2*100}')
DISK_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
CPU_IDLE=$(vmstat 1 2 | tail -1 | awk '{print $15}')
CPU_USED=$((100 - CPU_IDLE))

# Alert logic
ALERTS=""
[ "$CPU_USED" -gt "$CPU_WARN" ] && ALERTS="$ALERTS CPU:${CPU_USED}%"
[ "$MEM_PCT" -gt "$MEM_WARN" ] && ALERTS="$ALERTS MEM:${MEM_PCT}%"
[ "$DISK_PCT" -gt "$DISK_WARN" ] && ALERTS="$ALERTS DISK:${DISK_PCT}%"

# Output
if [ -n "$ALERTS" ]; then
    echo "$TIMESTAMP [$HOSTNAME] ALERT:$ALERTS | load=$LOAD cpu=$CPU_USED% mem=$MEM_PCT% disk=$DISK_PCT%"
else
    echo "$TIMESTAMP [$HOSTNAME] OK | load=$LOAD cpu=$CPU_USED% mem=$MEM_PCT% disk=$DISK_PCT%"
fi
```

