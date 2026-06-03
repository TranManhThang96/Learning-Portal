# Day 4: Bài tập — Linux Performance & Debugging Tools

---

## Bài 1: Easy — Performance Baseline Collection

### Context
Trước khi debug performance issues, bạn cần biết "bình thường" là gì. Bài tập này yêu cầu bạn thu thập baseline metrics cho hệ thống hiện tại.

### Yêu cầu
1. Thu thập CPU metrics: utilization, load average, top processes.
2. Thu thập memory metrics: total, used, available, swap.
3. Thu thập disk I/O metrics: IOPS, throughput, latency.
4. Thu thập network metrics: connections, bandwidth.
5. Ghi kết quả vào template baseline.

### Expected Outcome
- Baseline document hoàn chỉnh cho hệ thống hiện tại.
- Hiểu mỗi metric nghĩa là gì và ngưỡng bình thường.

### Hint
- `top -b -n 1` cho snapshot CPU/memory.
- `free -h` cho memory overview.
- `iostat -xz 1 3` cho disk I/O.
- `ss -s` cho connection summary.

### Acceptance Criteria
- [ ] Thu thập được metrics cho cả 4 resource types (CPU, memory, disk, network).
- [ ] Giải thích ý nghĩa mỗi metric quan trọng.
- [ ] Xác định được ngưỡng "bình thường" vs "cần investigate".
- [ ] Baseline document có thể dùng lại cho so sánh sau này.

### Bonus Challenge
- Viết script tự động thu thập baseline và output dạng report.
- Chạy baseline 3 lần ở thời điểm khác nhau, so sánh sự khác biệt.

<details>
<summary>Solution / Reference</summary>

```bash
#!/bin/bash
# baseline-collector.sh — Thu thập performance baseline

echo "════════════════════════════════════════════════"
echo "  Performance Baseline Report"
echo "  Host: $(hostname)"
echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Kernel: $(uname -r)"
echo "════════════════════════════════════════════════"
echo ""

# CPU
echo "━━━ CPU ━━━"
echo "Cores: $(nproc)"
echo "Model: $(grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)"
echo "Load Average: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"
echo "Top 5 CPU processes:"
ps aux --sort=-%cpu | head -6 | awk '{printf "  %-8s %5s%% %s\n", $1, $3, $11}'
echo ""

# Memory
echo "━━━ Memory ━━━"
free -h | awk '
NR==1 {printf "  %-12s %8s %8s %8s %8s\n", "", $1, $2, $3, $6}
NR==2 {printf "  %-12s %8s %8s %8s %8s\n", $1, $2, $3, $4, $7}
NR==3 {printf "  %-12s %8s %8s %8s\n", $1, $2, $3, $4}'
echo ""

# Disk I/O
echo "━━━ Disk I/O ━━━"
echo "Devices:"
lsblk -d -o NAME,SIZE,TYPE,ROTA 2>/dev/null | head -5
echo ""
echo "I/O Stats (1 second sample):"
iostat -xz 1 2 2>/dev/null | tail -n +7 | head -10
echo ""

# Network
echo "━━━ Network ━━━"
echo "TCP Connection Summary:"
ss -s 2>/dev/null | grep -A1 "TCP:"
echo ""
echo "Listening ports:"
ss -tlnp 2>/dev/null | tail -n +2 | awk '{printf "  %s %s\n", $4, $6}' | head -10
echo ""

# File Descriptors
echo "━━━ File Descriptors ━━━"
echo "System-wide: $(cat /proc/sys/fs/file-nr 2>/dev/null)"
echo ""

echo "════════════════════════════════════════════════"
echo "  Baseline collection complete"
echo "════════════════════════════════════════════════"
```

</details>

---

## Bài 2: Medium — Bottleneck Identification Challenge

### Context
Bạn cần tạo 3 loại bottleneck khác nhau (CPU, Memory, Disk I/O), sau đó dùng Linux tools để xác định chính xác bottleneck là gì.

### Yêu cầu
1. **CPU bottleneck**: Tạo workload CPU-intensive, dùng `top`, `mpstat`, `pidstat` để detect.
2. **Memory pressure**: Tạo memory allocation lớn dần, dùng `free`, `vmstat` để monitor.
3. **Disk I/O bottleneck**: Tạo disk write heavy, dùng `iostat`, `vmstat` (wa column) để detect.
4. Với mỗi bottleneck, ghi lại: dấu hiệu, tool phát hiện, metric chính, ngưỡng xác định.

### Expected Outcome
- 3 bottleneck scenarios được tạo và identified thành công.
- Debug report cho mỗi scenario: tool → metric → conclusion.

### Hint
- CPU: `python3 -c "while True: pass"` hoặc `stress --cpu 2`.
- Memory: `python3 -c "x = ['a'*1000000 for _ in range(500)]"`.
- Disk: `dd if=/dev/zero of=/tmp/test bs=1M count=500 conv=fdatasync`.
- `vmstat 1` hiện cả memory, CPU, I/O cùng lúc.

### Acceptance Criteria
- [ ] Tạo thành công 3 loại bottleneck.
- [ ] Identify đúng bottleneck type bằng tools.
- [ ] Ghi lại metric chính cho mỗi bottleneck.
- [ ] Giải thích cách phân biệt 3 loại bottleneck.
- [ ] Cleanup tất cả workload sau test.

### Bonus Challenge
- Tạo scenario kết hợp: CPU cao + disk I/O cao cùng lúc. Phân biệt đâu là primary bottleneck.
- Dùng `strace -c` để profile syscalls của mỗi workload.

<details>
<summary>Solution / Reference</summary>

```bash
#!/bin/bash
# bottleneck-challenge.sh

echo "=== Challenge 1: CPU Bottleneck ==="
python3 -c "
import os
print(f'CPU stress PID: {os.getpid()}')
# Calculate primes (CPU-intensive)
[n for n in range(2, 200000) if all(n%i for i in range(2, int(n**0.5)+1))]
" &
CPU_PID=$!

sleep 2
echo "--- Detection Tools ---"
echo "top (CPU %):"
top -b -n 1 -p $CPU_PID 2>/dev/null | tail -2
echo ""
echo "pidstat:"
pidstat -p $CPU_PID 1 2 2>/dev/null | tail -3
echo ""
echo "Load average: $(cat /proc/loadavg)"
echo ""

echo "Diagnosis: High %usr, load average > cores = CPU-bound"
echo ""
wait $CPU_PID 2>/dev/null

echo "=== Challenge 2: Memory Pressure ==="
python3 -c "
import os, time
print(f'Memory stress PID: {os.getpid()}')
data = []
for i in range(100):
    data.append('x' * 5_000_000)  # 5MB per iteration
    if i % 20 == 0:
        rss = int(open(f'/proc/{os.getpid()}/status').read().split('VmRSS:')[1].split()[0])
        print(f'  Allocated {(i+1)*5}MB, RSS: {rss//1024}MB')
time.sleep(3)
" &
MEM_PID=$!

sleep 1
echo "--- Detection Tools ---"
echo "free -h:"
free -h
echo ""
echo "vmstat 1 3 (watch 'swpd' and 'si/so' columns):"
vmstat 1 3
echo ""

echo "Diagnosis: Available decreasing, swap activity = Memory pressure"
echo ""
wait $MEM_PID 2>/dev/null

echo "=== Challenge 3: Disk I/O Bottleneck ==="
dd if=/dev/zero of=/tmp/io_test bs=1M count=200 conv=fdatasync 2>&1 &
IO_PID=$!

sleep 1
echo "--- Detection Tools ---"
echo "vmstat 1 3 (watch 'wa' column):"
vmstat 1 3
echo ""
echo "iostat -xz 1 2:"
iostat -xz 1 2 2>/dev/null | grep -v "^$" | tail -10
echo ""

echo "Diagnosis: High %iowait (wa), high %util in iostat = Disk I/O bound"
wait $IO_PID 2>/dev/null
rm -f /tmp/io_test

echo ""
echo "=== Summary: How to Distinguish ==="
echo "┌──────────┬───────────────────────────────────┐"
echo "│ Type     │ Key Indicator                     │"
echo "├──────────┼───────────────────────────────────┤"
echo "│ CPU      │ %usr+%sys >80%, load > cores      │"
echo "│ Memory   │ available low, swap active         │"
echo "│ Disk I/O │ %iowait high, iostat %util high   │"
echo "│ Network  │ retransmits, drops, high RTT       │"
echo "└──────────┴───────────────────────────────────┘"
```

</details>

---

## Bài 3: Hard — Production Debugging Simulation

### Context
Bạn nhận alert: "API service latency P99 tăng từ 100ms lên 2 giây". Bạn cần mô phỏng scenario này và debug step-by-step theo quy trình production.

### Yêu cầu

**Part 1: Setup**
Tạo HTTP server có characterisics sau:
- Endpoint `/fast`: respond ngay (< 10ms)
- Endpoint `/slow`: respond sau 2s (simulate DB query)
- Endpoint `/leak`: mỗi request tạo 1MB memory không release
- Endpoint `/cpu`: tính toán nặng (1s CPU)

**Part 2: Load test + Monitor**
1. Dùng `curl` loop hoặc `ab` (Apache Bench) để gửi traffic.
2. Theo dõi real-time bằng `top`, `vmstat`, `iostat`, `ss`.
3. Ghi lại metrics trước, trong, và sau load.

**Part 3: Debug theo USE + RED**
1. Áp dụng RED method: Rate, Errors, Duration cho service.
2. Áp dụng USE method: cho CPU, Memory, Disk, Network.
3. Xác định root cause.
4. Viết incident report ngắn.

### Expected Outcome
- Server với 4 endpoints chạy được.
- Load test output.
- Debug report theo USE + RED framework.
- Incident report template hoàn chỉnh.

### Hint
- Python `http.server` hoặc Node.js cho server đơn giản.
- `ab -n 100 -c 10 http://localhost:8080/slow` cho load test.
- Watch `vmstat 1` trong terminal riêng trong suốt quá trình.
- `/leak` endpoint sẽ gây memory growth → theo dõi bằng `/proc/<pid>/status`.

### Acceptance Criteria
- [ ] Server có 4 endpoints hoạt động.
- [ ] Load test chạy thành công.
- [ ] USE method áp dụng cho ít nhất 3 resources.
- [ ] RED method áp dụng cho service.
- [ ] Root cause identified chính xác.
- [ ] Incident report ngắn gọn, có timeline.

### Bonus Challenge
- Dùng `strace` attach vào server process, identify syscalls chiếm thời gian.
- Tạo flame graph (nếu có `perf` installed) cho CPU-heavy endpoint.
- Viết monitoring script tự detect anomaly (latency > threshold, memory growth rate).

<details>
<summary>Solution / Reference</summary>

```python
# perf-debug-server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import time, os, json

memory_leak = []
request_count = 0
start_time = time.time()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global request_count, memory_leak
        request_count += 1
        req_start = time.time()

        if self.path == '/fast':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'fast response')

        elif self.path == '/slow':
            time.sleep(2)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'slow response (simulated DB query)')

        elif self.path == '/leak':
            memory_leak.append('x' * 1_000_000)  # 1MB leak
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f'leaked {len(memory_leak)}MB total'.encode())

        elif self.path == '/cpu':
            result = sum(i*i for i in range(1_000_000))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f'cpu result: {result}'.encode())

        elif self.path == '/metrics':
            pid = os.getpid()
            rss = 0
            try:
                with open(f'/proc/{pid}/status') as f:
                    for line in f:
                        if 'VmRSS' in line:
                            rss = int(line.split()[1])
            except:
                pass

            metrics = {
                'requests_total': request_count,
                'uptime_seconds': round(time.time() - start_time, 1),
                'memory_rss_kb': rss,
                'memory_leaked_mb': len(memory_leak),
                'pid': pid
            }
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(metrics, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'not found')

        duration = time.time() - req_start
        print(f'[{self.path}] {self.command} {duration:.3f}s')

    def log_message(self, format, *args):
        pass  # Suppress default logging

print(f'Server starting on :8080 (PID: {os.getpid()})')
HTTPServer(('', 8080), Handler).serve_forever()
```

**Incident Report Template:**

```markdown
## Incident Report: High API Latency

### Timeline
- 14:00 — Alert fired: P99 latency > 2s
- 14:05 — On-call acknowledged, started investigation
- 14:10 — Identified: /slow endpoint under heavy load
- 14:15 — Mitigated: rate limiting applied
- 14:30 — Root cause confirmed: DB connection pool exhausted

### RED Analysis (Service Level)
- Rate: 500 RPS (normal: 200 RPS) — traffic spike
- Errors: 5% timeout errors (normal: 0.1%)
- Duration: P99 = 2.5s (normal: 100ms)

### USE Analysis (Infrastructure Level)
- CPU: 45% utilization — NOT bottleneck
- Memory: 2.1GB RSS, growing 50MB/min — LEAK DETECTED ⚠️
- Disk: 3% utilization — NOT bottleneck
- Network: 450 ESTABLISHED connections (normal: 100) — HIGH ⚠️

### Root Cause
Memory leak in /leak endpoint + connection pool exhaustion
due to traffic spike to /slow endpoint.

### Action Items
1. [ ] Fix memory leak in /leak handler
2. [ ] Add connection pool limits
3. [ ] Add rate limiting per endpoint
4. [ ] Add memory growth alert (> 100MB/hour)
```

</details>

---

## Tổng kết thời gian

| Bài | Độ khó | Thời gian ước tính |
|-----|--------|-------------------|
| Bài 1 | Easy | 20 phút |
| Bài 2 | Medium | 40 phút |
| Bài 3 | Hard | 60-90 phút |

