# Day 4: Linux Performance & Debugging Tools

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Áp dụng được USE method và RED method** để phân tích performance — biết khi nào dùng method nào và cho resource nào.
2. **Xác định được bottleneck** (CPU, memory, disk, network) bằng Linux tools thực tế trong production.
3. **Sử dụng thành thạo ít nhất 6 tools** — `top`/`htop`, `iostat`, `vmstat`, `ss`, `strace`, `tcpdump` để debug performance issue.
4. **Đọc được flame graph** để tìm hotspot trong application.
5. **Tạo được workload giả lập** để test bottleneck và verify fix.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng trong production?

Performance debugging là kỹ năng **bắt buộc** cho mọi engineer vận hành production. Khi hệ thống chậm, bạn cần trả lời: **chậm ở đâu và vì sao?** Không có kỹ năng này, bạn chỉ có thể restart service và hy vọng.

### Hậu quả nếu làm sai

| Sai lầm | Hậu quả thực tế |
|---------|-----------------|
| Không biết đo bottleneck | "Service chậm" → restart random → vẫn chậm → mất hàng giờ |
| Scale up thay vì tìm root cause | CPU 100% do memory leak → tăng CPU không giải quyết gì, tốn tiền |
| Không phân biệt CPU-bound vs I/O-bound | Tối ưu code (CPU) khi vấn đề thực tế là disk I/O |
| Không có baseline metrics | Không biết "bình thường" là gì → không biết "bất thường" là gì |

### Liên hệ với kiến thức developer

- **Database optimization**: Bạn đã biết query plan — giờ cần biết tầng dưới: disk I/O latency ảnh hưởng query thế nào.
- **Caching (Redis)**: Cache hit ratio 99% nhưng vẫn chậm? Có thể network latency giữa app và Redis.
- **Kafka**: Consumer lag tăng? Có thể CPU throttling trong container (Day 2 + Day 4 kết hợp).

---

## 3. Kiến thức nền tảng

### 3.1. USE Method (Brendan Gregg)

**USE** = **U**tilization, **S**aturation, **E**rrors — framework để phân tích **resource-oriented** problems.

Áp dụng cho mỗi resource (CPU, Memory, Disk, Network):

| Dimension | Câu hỏi | Ví dụ |
|-----------|---------|-------|
| **Utilization** | Resource đang bận bao nhiêu %? | CPU utilization 85% |
| **Saturation** | Có work đang phải queue/chờ không? | CPU run queue length > CPU cores |
| **Errors** | Có lỗi resource nào không? | Disk I/O errors, network packet drops |

**Analogy**: Giống như đánh giá một nhà hàng — Utilization (bao nhiêu bàn đang có khách), Saturation (bao nhiêu người đang xếp hàng chờ), Errors (bao nhiêu đơn hàng bị sai).

```
┌──────────────────────────────────────────────────────┐
│                   USE Method                          │
│                                                      │
│  For each resource (CPU, Memory, Disk, Network):     │
│                                                      │
│  1. Utilization → Đang bận bao nhiêu?                │
│     │                                                │
│     ├── Low (<50%)  → Resource không phải bottleneck  │
│     ├── Medium (50-80%) → Monitor, plan capacity     │
│     └── High (>80%) → Potential bottleneck ⚠️         │
│                                                      │
│  2. Saturation → Có work đang chờ?                   │
│     │                                                │
│     ├── No queue → Resource đáp ứng được             │
│     └── Queue > 0 → Work phải chờ → latency tăng ⚠️  │
│                                                      │
│  3. Errors → Có lỗi?                                 │
│     │                                                │
│     ├── No errors → Resource healthy                 │
│     └── Errors > 0 → Investigate immediately 🔥      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 3.2. RED Method (Tom Wilkie)

**RED** = **R**ate, **E**rrors, **D**uration — framework để phân tích **request-oriented** problems (services).

| Dimension | Câu hỏi | Metric ví dụ |
|-----------|---------|-------------|
| **Rate** | Bao nhiêu requests/sec? | HTTP RPS, gRPC calls/sec |
| **Errors** | Bao nhiêu % requests lỗi? | 5xx rate, timeout rate |
| **Duration** | Mỗi request mất bao lâu? | P50, P95, P99 latency |

**USE vs RED**:
- **USE** cho **infrastructure** (server, disk, network device)
- **RED** cho **services** (API server, database, cache)

Sử dụng kết hợp: RED để detect vấn đề (latency tăng), USE để tìm root cause (disk I/O saturated).

### 3.3. Bốn loại bottleneck chính

| Bottleneck | Dấu hiệu | Tool chính | Nguyên nhân thường gặp |
|-----------|----------|-----------|----------------------|
| **CPU** | `%usr` + `%sys` > 80%, load average > cores | `top`, `mpstat`, `perf` | Computation-heavy, regex, serialization, GC |
| **Memory** | `free` thấp, swap tăng, OOM kills | `free`, `vmstat`, `/proc/meminfo` | Memory leak, cache quá lớn, large objects |
| **Disk I/O** | `iowait` cao, `await` cao, throughput thấp | `iostat`, `iotop`, `blktrace` | Sequential scan, no index, write-heavy |
| **Network** | Packet drops, retransmits, latency cao | `ss`, `tcpdump`, `sar -n` | Bandwidth limit, many connections, DNS |

---

## 4. Deep Dive

### 4.1. CPU Performance Analysis

```
                    CPU Bottleneck Analysis
                    ━━━━━━━━━━━━━━━━━━━━━━
                    
User space (app code)          Kernel space (OS)
┌─────────────────┐           ┌─────────────────┐
│  %usr / %user   │           │  %sys / %system  │
│                 │           │                  │
│  Application    │           │  System calls    │
│  computation    │           │  I/O operations  │
│  Libraries      │           │  Context switch  │
│  JIT compile    │           │  Interrupt       │
│  GC             │           │  Scheduling      │
└─────────────────┘           └─────────────────┘

Load Average = CPU run queue length (over 1, 5, 15 min)
  < num_cores  → CPU not saturated
  = num_cores  → CPU at capacity
  > num_cores  → CPU over-saturated, processes waiting

Example (8-core server):
  load average: 3.5, 2.1, 1.8  → Healthy
  load average: 8.0, 7.5, 6.2  → At capacity
  load average: 24.0, 18.5, 12.0 → Over-saturated! ⚠️
```

### 4.2. Memory Analysis

```
Total Memory
┌────────────────────────────────────────────────┐
│                                                │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │  Used    │ │  Buffers │ │   Available    │ │
│  │  (apps)  │ │  /Cache  │ │   (for new)    │ │
│  │          │ │          │ │                │ │
│  └──────────┘ └──────────┘ └────────────────┘ │
│                                                │
└────────────────────────────────────────────────┘

Key metric: "available" (not "free"!)
  - "free" = truly unused memory (often small)
  - "buffers/cache" = memory used for disk cache (can be reclaimed)
  - "available" = free + reclaimable cache ← THIS is what matters

When available → 0:
  → OOM Killer activates
  → Kills process with highest oom_score
  → Check: dmesg | grep -i oom
```

### 4.3. Disk I/O Analysis

```
Application
    │ write() / read()
    ▼
┌─────────────────┐
│ Page Cache      │  ← Linux kernel cache (memory)
│ (buffered I/O)  │     Most reads served from here
└────────┬────────┘
         │ Cache miss or fsync()
         ▼
┌─────────────────┐
│ I/O Scheduler   │  ← Reorder/merge I/O requests
│ (elevator)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Block Device    │  ← HDD, SSD, NVMe
│                 │     Performance varies hugely:
│ HDD:  ~10ms    │     HDD: 100 IOPS
│ SSD:  ~0.1ms   │     SSD: 10,000-100,000 IOPS
│ NVMe: ~0.02ms  │     NVMe: 500,000+ IOPS
└─────────────────┘

iostat key metrics:
  r/s, w/s    = reads/writes per second (IOPS)
  rMB/s, wMB/s = throughput
  await       = average I/O latency (ms) ← most important
  %util       = device utilization
```

### 4.4. Tool Selection Guide

```
Performance issue detected!
         │
         ├── Which resource?
         │
    ┌────┼────┬────┐
    ▼    ▼    ▼    ▼
   CPU  MEM  DISK  NET
    │    │    │     │
    │    │    │     ├── ss -s (connection summary)
    │    │    │     ├── ss -tn state ... (per-state)
    │    │    │     ├── tcpdump (packet analysis)
    │    │    │     ├── sar -n DEV (throughput)
    │    │    │     └── iftop (real-time traffic)
    │    │    │
    │    │    ├── iostat -xz 1 (IOPS, latency, util)
    │    │    ├── iotop (per-process I/O)
    │    │    └── lsblk (device info)
    │    │
    │    ├── free -h (memory overview)
    │    ├── vmstat 1 (memory + swap activity)
    │    ├── /proc/meminfo (detailed)
    │    ├── slabtop (kernel memory)
    │    └── pmap -x <pid> (per-process)
    │
    ├── top / htop (overview)
    ├── mpstat -P ALL 1 (per-CPU)
    ├── pidstat 1 (per-process CPU)
    ├── perf top (find CPU hotspots)
    ├── perf record + perf report
    └── strace -c -p <pid> (syscall profile)
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1. Monitoring Strategy

| Approach | Ưu điểm | Nhược điểm | Phù hợp cho |
|----------|---------|------------|-------------|
| Poll-based (vmstat 1) | Real-time, interactive | Tốn engineer time, không lưu history | Ad-hoc debugging |
| Agent-based (node_exporter) | Automatic, historical data | Setup effort, resource overhead | Production monitoring |
| eBPF-based (bcc tools) | Deep insight, low overhead | Kernel version dependency, complexity | Advanced debugging |
| APM (Datadog, New Relic) | Full stack, easy setup | Cost cao, vendor lock-in | Teams muốn tốc độ |

### 5.2. Anti-patterns

1. **Average, not percentiles** — Average latency 50ms nhưng P99 = 5s → 1% users chờ 5 giây. Luôn dùng percentiles.
2. **Measure inside, not outside** — Đo từ phía server (processing time) mà bỏ qua network latency client → server.
3. **Single metric obsession** — Chỉ nhìn CPU utilization mà bỏ qua memory, disk, network.
4. **Premature optimization** — Profile trước, optimize sau. Đừng guess, measure!
5. **Tool overload** — 20 monitoring tools nhưng không ai nhìn dashboards. Ít tools, clear ownership, actionable alerts.

### 5.3. Theo scenario

**Startup nhỏ**: `top` + `free` + `ss` + `curl timing` là đủ 80% debugging. Không cần APM phức tạp.

**Mid-size**: `node_exporter` + Prometheus + Grafana cho baseline. `strace`, `tcpdump` cho deep debugging.

**Enterprise/High-traffic**: eBPF tools, continuous profiling (Pyroscope, Parca), distributed tracing (Jaeger/Tempo).

---

## 6. Performance & Scalability ⭐

### 6.1. Khi nào scale là sai giải pháp?

| Vấn đề | Scale sẽ... | Nên làm thay |
|--------|-------------|-------------|
| Memory leak | Delay OOM, không fix | Fix leak (profiling) |
| N+1 query | Tăng DB connections = worse | Fix query pattern |
| Single-threaded bottleneck | Waste thêm cores | Re-architect (async, parallel) |
| Lock contention | Quá nhiều threads tranh lock = worse | Reduce lock scope, lockfree |
| DNS resolution timeout | Tăng replicas vô nghĩa | Fix DNS config |

### 6.2. Performance Baseline Template

Trước khi debug, cần biết "bình thường" là gì:

```
Service: ___________
Normal traffic: _____ RPS
Baseline metrics:
  CPU utilization: ____ % (user: __%, sys: __%)
  Memory RSS: ____ MB
  Disk I/O: ____ IOPS, await ____ ms
  Network: ____ connections, ____ Mbps
  Latency: P50=____ms, P95=____ms, P99=____ms
  Error rate: _____%
```

---

## 7. Security & Reliability Considerations

### Security
- **perf, strace, tcpdump** cần root/CAP_SYS_PTRACE — restrict access trong production.
- **tcpdump captures data** — có thể chứa PII, passwords nếu không TLS. Xóa capture files ngay sau debug.
- **/proc exposure** — Trong container, mount `/proc` cẩn thận (leak host info).

### Reliability
- **Monitoring overhead** — Quá nhiều metrics collection ảnh hưởng app performance (especially strace — 10-50x slowdown!).
- **strace trong production** — Chỉ dùng ngắn hạn, specific process, specific syscalls. KHÔNG attach vào toàn bộ service.
- **Disk space** — tcpdump capture file lớn nhanh. Set limit: `-c 10000` (max packets) hoặc `-G 60 -W 5` (rotate).

---

## 8. Hands-on Example

Chuẩn bị workspace và kiểm tra tool local:

```bash
mkdir -p /tmp/devops-day04
cd /tmp/devops-day04
command -v top
command -v vmstat
command -v mpstat || echo "mpstat missing: install sysstat nếu muốn chạy phần per-CPU"
command -v iostat || echo "iostat missing: install sysstat nếu muốn chạy phần disk I/O"
command -v strace || echo "strace missing: cài strace nếu muốn chạy phần syscall tracing"
```

### 8.1. CPU Bottleneck — Detect và Analyze

```bash
# ═══ Tạo CPU bottleneck ═══
# Python calculating primes (CPU-intensive)
python3 -c "
import time
def is_prime(n):
    if n < 2: return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0: return False
    return True

start = time.time()
primes = [n for n in range(2, 500000) if is_prime(n)]
print(f'Found {len(primes)} primes in {time.time()-start:.1f}s')
" &
CPU_PID=$!

# ═══ Detect ═══
echo "=== top (check CPU) ==="
# Chạy top trong 3 seconds
top -b -n 3 -d 1 | head -20

echo ""
echo "=== mpstat (per-CPU breakdown) ==="
mpstat -P ALL 1 3

echo ""
echo "=== pidstat (per-process CPU) ==="
pidstat -p $CPU_PID 1 3

# ═══ Analyze ═══
echo ""
echo "=== Load average ==="
cat /proc/loadavg

echo ""
echo "=== Process info ==="
ps -p $CPU_PID -o pid,ppid,%cpu,%mem,vsz,rss,stat,time,cmd

# Cleanup
wait $CPU_PID 2>/dev/null
```

**Expected output indicators:**
- `%usr` cao (>80%) → CPU-bound computation
- Load average tăng
- `pidstat` cho thấy process nào chiếm CPU

**Verify**:

```bash
ps -p $CPU_PID >/dev/null 2>&1 || echo "CPU workload finished"
```

**Expected output**:

```text
CPU workload finished
```

### 8.2. Memory Issue — Detect Leak Pattern

```bash
# ═══ Tạo memory growth ═══
python3 -c "
import time, os
data = []
for i in range(50):
    data.append('x' * 1_000_000)  # 1MB each iteration
    pid = os.getpid()
    with open(f'/proc/{pid}/status') as f:
        for line in f:
            if 'VmRSS' in line:
                print(f'Iteration {i+1}: {line.strip()}')
                break
    time.sleep(0.5)
print('Done. Total allocated: ~50MB')
time.sleep(5)
" &
MEM_PID=$!

# ═══ Monitor memory growth ═══
echo "=== Watching memory growth ==="
for i in $(seq 1 10); do
  RSS=$(grep VmRSS /proc/$MEM_PID/status 2>/dev/null | awk '{print $2}')
  echo "$(date +%H:%M:%S) RSS: ${RSS:-ended} kB"
  sleep 2
done

echo ""
echo "=== System memory overview ==="
free -h

echo ""
echo "=== vmstat (memory + swap activity) ==="
vmstat 1 5

# Cleanup
wait $MEM_PID 2>/dev/null
```

**Expected output indicators:**
- `VmRSS` tăng theo từng iteration.
- `free -h` cho thấy `available` vẫn là chỉ số quan trọng hơn `free`.

**Verify**:

```bash
ps -p $MEM_PID >/dev/null 2>&1 || echo "memory workload finished"
```

**Expected output**:

```text
memory workload finished
```

### 8.3. Disk I/O — Detect Slow I/O

```bash
# ═══ Tạo disk I/O load ═══
echo "=== Creating I/O workload ==="
dd if=/dev/zero of=/tmp/testfile bs=1M count=200 conv=fdatasync 2>&1 &
IO_PID=$!

# ═══ Monitor disk I/O ═══
echo ""
echo "=== iostat (disk performance) ==="
iostat -xz 1 5

echo ""
echo "=== iotop (per-process I/O — needs root) ==="
# sudo iotop -b -n 3 -d 1 -p $IO_PID

echo ""
echo "=== vmstat (check iowait — 'wa' column) ==="
vmstat 1 5
# 'wa' column = CPU time waiting for I/O. High wa = disk bottleneck

# Cleanup
wait $IO_PID 2>/dev/null
rm -f /tmp/testfile
echo "Cleanup done"
```

**Đọc iostat output:**
```
Device     r/s    w/s   rMB/s  wMB/s  await  %util
sda       0.00  150.00  0.00   75.00  2.50   85.00
           │      │              │      │      │
           │      │              │      │      └─ 85% busy → approaching saturation
           │      │              │      └─ 2.5ms avg wait → acceptable for SSD
           │      │              └─ 75 MB/s throughput
           │      └─ 150 writes/sec (IOPS)
           └─ 0 reads (all writes in this test)
```

### 8.4. strace — Trace System Calls

```bash
# Tạo simple server
python3 -m http.server 8888 &
SERVER_PID=$!
sleep 1

# Trace syscalls khi xử lý request
echo "=== Attach strace to running process ==="
# Trace for 5 seconds, show summary
timeout 5 strace -c -p $SERVER_PID 2>&1 &
STRACE_PID=$!

# Generate some requests
for i in $(seq 1 10); do
  curl -s http://localhost:8888/ > /dev/null
done

wait $STRACE_PID 2>/dev/null

echo ""
echo "=== Trace specific syscalls (network) ==="
timeout 3 strace -e trace=network -p $SERVER_PID 2>&1 &
curl -s http://localhost:8888/ > /dev/null
sleep 3

# Cleanup
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

**Expected strace -c output:**
```
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- --------
 45.00    0.000090           9        10           read
 25.00    0.000050           5        10           write
 15.00    0.000030           3        10           accept
 10.00    0.000020           2        10           close
  5.00    0.000010           1        10           stat
------ ----------- ----------- --------- --------- --------
100.00    0.000200                    50           total
```

### 8.5. Flame Graph Overview

```bash
# Record CPU profile (needs root and perf installed)
# sudo perf record -F 99 -p <pid> --call-graph dwarf -- sleep 30
# sudo perf script > out.perf

# Convert to flame graph (Brendan Gregg's tools)
# git clone https://github.com/brendangregg/FlameGraph
# ./FlameGraph/stackcollapse-perf.pl out.perf > out.folded
# ./FlameGraph/flamegraph.pl out.folded > flamegraph.svg

# Đọc flame graph:
# Width of box = percentage of CPU time
# Y-axis = call stack depth
# Colors = random (don't indicate severity)
# Look for: wide boxes at the top = CPU hotspots
```

```
Flame Graph Reading Guide:
━━━━━━━━━━━━━━━━━━━━━━━━━

         ┌──── This function takes most CPU ────┐
         │                                       │
╔═══════════════════════════════════════════════╗
║           calculateHash (45% CPU)             ║  ← Wide = more CPU
╠═══════════════╦═══════════════════════════════╣
║  encrypt (20%)║    compress (25% CPU)         ║
╠═══════╦═══════╬═══════════════════════════════╣
║ aes   ║sha256 ║     gzip (25% CPU)            ║
╠═══════╩═══════╬═══════════╦═══════════════════╣
║ openssl (20%) ║  deflate  ║   crc32 (10%)     ║
╠═══════════════╩═══════════╩═══════════════════╣
║              main() → handleRequest()          ║  ← Bottom = entry point
╚═══════════════════════════════════════════════╝
  ↑                                              ↑
  │              X-axis = CPU time               │
```

### Cleanup

```bash
# Kill any remaining test processes
pkill -f "http.server 8888" 2>/dev/null
rm -f /tmp/testfile
rm -rf /tmp/devops-day04
```

---

## 9. Common Pitfalls & Debugging

### 9.1. Pitfall: iowait cao nhưng disk không phải bottleneck

**Dấu hiệu**: `vmstat` hiện `wa` (I/O wait) cao, nhưng `iostat` hiện disk utilization thấp.

**Root cause**: Process đang chờ network I/O (NFS mount, remote storage), không phải local disk.

**Debug**:
```bash
# Check nếu có NFS/remote mounts
mount | grep nfs
df -T | grep -v tmpfs

# Check process nào đang D state (uninterruptible I/O)
ps aux | awk '$8 ~ /D/ {print}'

# strace to see what I/O
strace -e trace=read,write,recvfrom,sendto -p <pid>
```

### 9.2. Pitfall: Memory free rất thấp nhưng system vẫn ok

**Dấu hiệu**: `free` hiện "free" memory gần 0, nhưng service vẫn chạy bình thường.

**Giải thích**: Linux sử dụng memory trống cho disk cache. "Free" thấp là bình thường. Nhìn "available" thay vì "free".

```bash
free -h
#               total    used    free    shared  buff/cache   available
# Mem:          16Gi     8.0Gi   0.5Gi   0.1Gi   7.5Gi        7.2Gi
#                                  ↑                            ↑
#                              Rất thấp nhưng OK!        Đây mới quan trọng
```

### 9.3. Pitfall: CPU cao do garbage collection

**Dấu hiệu**: Java/Node.js/Go service có CPU spike định kỳ, latency P99 cao.

**Debug**:
```bash
# Java
jstat -gc <pid> 1000  # GC activity every 1s

# Node.js
node --prof app.js    # V8 profiling
# Hoặc --inspect cho Chrome DevTools

# Go
GODEBUG=gctrace=1 ./myapp  # GC logging
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# Generic: check GC pauses trong application metrics
```

### 9.4. Case Study: Mysterious High Latency at 2 AM

**Context**: E-commerce API, traffic giảm 90% vào 2 AM nhưng latency P99 tăng 10x.

**Symptom**: Request bình thường 50ms, lúc 2 AM → 500ms. CPU idle, memory ok, no errors.

**Investigation**:
```bash
# Check cron jobs
crontab -l
# Found: 0 2 * * * /opt/scripts/log-rotate.sh
# Found: 0 2 * * * /opt/scripts/db-backup.sh

# Check disk I/O lúc 2 AM
sar -d -s 02:00:00 -e 02:30:00  # Historical disk stats
# Result: disk utilization 95% ← backup script writing large file!

# Check I/O wait
sar -u -s 02:00:00 -e 02:30:00  # Historical CPU stats  
# Result: %iowait = 40% ← application disk reads wait behind backup writes
```

**Root cause**: Backup script chạy lúc 2 AM write heavy → disk saturated → application disk reads (log, temp files) bị chậm.

**Fix**: Chuyển backup sang instance riêng hoặc dùng `ionice` để lower priority: `ionice -c2 -n7 /opt/scripts/db-backup.sh`.

**Lesson**: Low traffic ≠ no performance issues. Batch jobs cạnh tranh I/O resource.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 3: Linux Networking
- Day 3 giới thiệu `ss`, `tcpdump` cho network debugging. Day 4 mở rộng với USE method để phân tích network cùng CPU/memory/disk.
- Connection leak (Day 3 CLOSE_WAIT) = fd leak (Day 2) = memory/resource issue (Day 4).

### Bài sau — Day 5: Bash & Python Automation
- Day 4 dùng tools interactive (top, iostat) → Day 5 sẽ tự động hóa monitoring bằng scripts.
- Performance baseline (Day 4) sẽ được capture bằng automation scripts (Day 5).
- Health check và alerting scripts (Day 5) dựa trên metrics từ Day 4.

---

## 11. Tài liệu tham khảo

### Must-read
- **Brendan Gregg's Linux Performance**: https://brendangregg.com/linuxperf.html — THE resource cho Linux performance. USE method, flame graphs.
- **USE Method Checklist**: https://brendangregg.com/USEmethod/use-linux.html — Checklist cụ thể cho từng Linux resource.
- **Netflix TechBlog**: "Linux Performance Analysis in 60,000 Milliseconds" — 6 tools trong 60 giây.

### Nice-to-have
- **"Systems Performance" by Brendan Gregg** — Sách performance bible, 800+ trang.
- **"BPF Performance Tools" by Brendan Gregg** — eBPF tools cho advanced debugging.
- **htop explained**: https://peteris.rocks/blog/htop/ — Guide chi tiết từng column trong htop.

### Deep-dive
- **perf Examples**: https://brendangregg.com/perf.html — Linux perf tool tutorial.
- **FlameGraph**: https://github.com/brendangregg/FlameGraph — Tool tạo flame graphs.
- **eBPF / bcc tools**: https://github.com/iovisor/bcc — Advanced tracing tools.

