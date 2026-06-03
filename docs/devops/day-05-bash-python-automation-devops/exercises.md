# Day 5: Bài tập — Bash & Python Automation for DevOps

---

## Bài 1: Easy — Health Check Script

### Context
Bạn cần viết script kiểm tra health của các services trong hệ thống. Script này sẽ chạy như CronJob hoặc Kubernetes liveness probe.

### Yêu cầu
1. Viết Bash script health check cho 3 endpoints (có thể dùng bất kỳ URL public nào để test).
2. Script phải có:
   - Bash strict mode (`set -euo pipefail`)
   - Logging function với timestamp
   - Timeout cho mỗi request (5 giây)
   - Exit code phản ánh kết quả (0 = all healthy, 1 = có failure)
   - Output summary cuối script
3. Chạy script và verify output.

### Expected Outcome
- Script chạy check 3 endpoints.
- Log output có timestamp, health status.
- Exit code đúng.

### Hint
- `curl -o /dev/null -s -w "%{http_code}" --max-time 5 URL` lấy HTTP status code.
- Dùng array cho danh sách endpoints.
- `$?` kiểm tra exit code của command trước.

### Acceptance Criteria
- [ ] Script có strict mode.
- [ ] Có logging function với timestamp.
- [ ] Check ít nhất 3 endpoints.
- [ ] Exit code 0 khi all healthy, 1 khi có failure.
- [ ] Output clear và readable.

### Bonus Challenge
- Thêm retry logic: nếu health check fail, retry 2 lần trước khi đánh dấu unhealthy.
- Thêm response time measurement cho mỗi endpoint.
- Output dạng JSON cho integration với monitoring tools.

<details>
<summary>Solution / Reference</summary>

```bash
#!/usr/bin/env bash
set -euo pipefail

# Configuration
readonly TIMEOUT=5
readonly MAX_RETRIES=2
readonly ENDPOINTS=(
    "https://httpbin.org/status/200|HTTPBin OK"
    "https://httpbin.org/delay/1|HTTPBin Delay"
    "https://httpbin.org/status/500|HTTPBin Error (expected fail)"
)

# Logging
log() {
    local level="$1"; shift
    echo "$(date '+%Y-%m-%d %H:%M:%S') [${level}] $*"
}

# Health check with retry
check_endpoint() {
    local url="$1"
    local name="$2"
    local attempt=0
    local http_code
    local response_time

    while [[ $attempt -le $MAX_RETRIES ]]; do
        response_time=$(curl -o /dev/null -s -w "%{time_total}" \
            --connect-timeout "${TIMEOUT}" \
            --max-time "${TIMEOUT}" \
            "${url}" 2>/dev/null) || true

        http_code=$(curl -o /dev/null -s -w "%{http_code}" \
            --connect-timeout "${TIMEOUT}" \
            --max-time "${TIMEOUT}" \
            "${url}" 2>/dev/null) || http_code="000"

        if [[ "${http_code}" =~ ^2[0-9][0-9]$ ]]; then
            log INFO "OK   ${name} — HTTP ${http_code} (${response_time}s)"
            return 0
        fi

        attempt=$((attempt + 1))
        if [[ $attempt -le $MAX_RETRIES ]]; then
            log WARN "RETRY ${name} — HTTP ${http_code} (attempt ${attempt}/${MAX_RETRIES})"
            sleep 1
        fi
    done

    log ERROR "FAIL ${name} — HTTP ${http_code} after ${MAX_RETRIES} retries"
    return 1
}

# Main
log INFO "=== Health Check Started ==="
failures=0

for entry in "${ENDPOINTS[@]}"; do
    IFS='|' read -r url name <<< "${entry}"
    check_endpoint "${url}" "${name}" || ((failures++)) || true
done

log INFO "=== Complete: $((${#ENDPOINTS[@]} - failures))/${#ENDPOINTS[@]} healthy ==="

if [[ ${failures} -gt 0 ]]; then
    log ERROR "${failures} service(s) unhealthy"
    exit 1
fi
exit 0
```

</details>

---

## Bài 2: Medium — Backup Script with Rotation

### Context
Bạn cần tự động backup thư mục logs hàng ngày, giữ lại backups trong 7 ngày, và gửi alert nếu backup fail.

### Yêu cầu
1. Viết Bash script backup:
   - Nhận arguments: source directory, destination, retention days.
   - Có `--help` flag.
   - Idempotent: chạy nhiều lần không tạo duplicate.
   - Lock file: không cho 2 instances chạy cùng lúc.
   - Verify: kiểm tra archive integrity sau khi tạo.
   - Rotation: xóa backups cũ hơn retention period.
   - Logging: mỗi bước có log với timestamp.
   - Cleanup: trap để cleanup temp files khi script bị interrupt.

2. Test:
   - Tạo test data, chạy backup 3 lần.
   - Verify idempotency (không duplicate).
   - Verify lock mechanism (chạy 2 instances cùng lúc).
   - Verify rotation.

### Expected Outcome
- Backup script production-grade.
- Test results cho idempotency, locking, rotation.

### Hint
- `flock` cho locking mechanism.
- `tar -tzf` để verify archive integrity.
- `find -mtime +7 -delete` cho rotation.
- `trap cleanup EXIT` cho cleanup.

### Acceptance Criteria
- [ ] Script nhận arguments với validation.
- [ ] `--help` hoạt động.
- [ ] Lock file ngăn concurrent execution.
- [ ] Archive verified sau khi tạo.
- [ ] Rotation xóa files cũ.
- [ ] Trap cleanup temp files.
- [ ] Logs đầy đủ với timestamp.

### Bonus Challenge
- Thêm `--dry-run` mode: hiển thị sẽ làm gì mà không thực hiện.
- Compression level option (gzip vs bzip2 vs zstd).
- Upload backup lên remote (scp/rsync/s3).
- Gửi notification qua webhook khi backup hoàn thành hoặc fail.

<details>
<summary>Solution / Reference</summary>

```bash
#!/usr/bin/env bash
set -euo pipefail

# ═══ Constants ═══
readonly SCRIPT_NAME="$(basename "$0")"
readonly DEFAULT_RETENTION=7
TMPDIR=""

# ═══ Usage ═══
usage() {
    cat <<EOF
Usage: ${SCRIPT_NAME} [OPTIONS] SOURCE DEST

Backup SOURCE directory to DEST with rotation.

Arguments:
  SOURCE     Source directory to backup
  DEST       Destination directory for backups

Options:
  -r, --retention DAYS    Keep backups for N days (default: ${DEFAULT_RETENTION})
  -d, --dry-run           Show what would happen without doing it
  -v, --verbose           Verbose output
  -h, --help              Show this help

Examples:
  ${SCRIPT_NAME} /var/log /backups
  ${SCRIPT_NAME} -r 14 /opt/app/data /backups
  ${SCRIPT_NAME} --dry-run /var/log /backups
EOF
}

# ═══ Logging ═══
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [BACKUP] $*"; }

# ═══ Cleanup ═══
cleanup() {
    local exit_code=$?
    [[ -n "${TMPDIR}" && -d "${TMPDIR}" ]] && rm -rf "${TMPDIR}"
    [[ ${exit_code} -ne 0 ]] && log "Exited with error code ${exit_code}"
    exit ${exit_code}
}
trap cleanup EXIT INT TERM

# ═══ Parse Args ═══
RETENTION="${DEFAULT_RETENTION}"
DRY_RUN=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -r|--retention) RETENTION="$2"; shift 2 ;;
        -d|--dry-run) DRY_RUN=true; shift ;;
        -v|--verbose) VERBOSE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
        *) break ;;
    esac
done

if [[ $# -lt 2 ]]; then
    echo "Error: SOURCE and DEST required" >&2
    usage
    exit 2
fi

SOURCE="$1"
DEST="$2"

# ═══ Validation ═══
[[ ! -d "${SOURCE}" ]] && { log "ERROR: Source not found: ${SOURCE}"; exit 1; }
mkdir -p "${DEST}"

# ═══ Lock ═══
LOCKFILE="/tmp/${SCRIPT_NAME}.lock"
exec 200>"${LOCKFILE}"
flock -n 200 || { log "Another instance running, exiting"; exit 1; }

# ═══ Main ═══
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="${DEST}/backup_${TIMESTAMP}.tar.gz"

if ${DRY_RUN}; then
    log "[DRY-RUN] Would backup: ${SOURCE} → ${BACKUP_FILE}"
    log "[DRY-RUN] Would remove backups older than ${RETENTION} days"
    OLD_COUNT=$(find "${DEST}" -name "backup_*.tar.gz" -mtime +"${RETENTION}" 2>/dev/null | wc -l)
    log "[DRY-RUN] Would remove ${OLD_COUNT} old backups"
    exit 0
fi

log "Starting backup: ${SOURCE} → ${BACKUP_FILE}"
START=$(date +%s)

TMPDIR=$(mktemp -d)
tar -czf "${TMPDIR}/backup.tar.gz" -C "$(dirname "${SOURCE}")" "$(basename "${SOURCE}")"
mv "${TMPDIR}/backup.tar.gz" "${BACKUP_FILE}"

END=$(date +%s)
DURATION=$((END - START))
SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

# Verify
if tar -tzf "${BACKUP_FILE}" > /dev/null 2>&1; then
    log "Verified: archive integrity OK"
else
    log "ERROR: Archive corrupted!"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

log "Backup complete: ${SIZE} in ${DURATION}s"

# Rotation
OLD_COUNT=$(find "${DEST}" -name "backup_*.tar.gz" -mtime +"${RETENTION}" | wc -l)
if [[ ${OLD_COUNT} -gt 0 ]]; then
    log "Rotating: removing ${OLD_COUNT} backups older than ${RETENTION} days"
    find "${DEST}" -name "backup_*.tar.gz" -mtime +"${RETENTION}" -delete
fi

TOTAL=$(find "${DEST}" -name "backup_*.tar.gz" | wc -l)
log "Total backups: ${TOTAL} (retention: ${RETENTION} days)"
```

</details>

---

## Bài 3: Hard — API Monitoring + Alert System (Python)

### Context
Bạn cần viết hệ thống monitoring bằng Python theo dõi nhiều API endpoints, thu thập metrics (response time, status), detect anomalies, và gửi alert.

### Yêu cầu

**Part 1: API Monitor**
1. Viết Python script monitor danh sách API endpoints.
2. Thu thập: HTTP status, response time, response body hash.
3. Lưu kết quả vào JSON file (time-series data).
4. Detect anomaly: response time > threshold hoặc status != 200.

**Part 2: Alerting**
1. Khi detect anomaly, log alert với severity (WARNING/CRITICAL).
2. Consecutive failures trigger escalation (3 failures → CRITICAL).
3. Recovery notification khi service trở lại healthy.

**Part 3: Report**
1. Tạo summary report: uptime %, average response time, incident count.
2. Output dạng JSON và human-readable text.

### Expected Outcome
- Python script chạy monitoring loop.
- JSON data file chứa historical metrics.
- Alert output với escalation logic.
- Summary report.

### Hint
- `urllib.request` cho HTTP calls (no external dependency).
- `json` module cho data storage.
- `collections.defaultdict` cho state tracking.
- `argparse` cho CLI arguments.

### Acceptance Criteria
- [ ] Monitor ít nhất 3 endpoints.
- [ ] Thu thập response time và status.
- [ ] Anomaly detection hoạt động (slow response, error status).
- [ ] Consecutive failure escalation.
- [ ] Recovery notification.
- [ ] Summary report có uptime % và avg response time.
- [ ] Code có error handling, logging, clean structure.

### Bonus Challenge
- Thêm concurrent checking bằng `concurrent.futures.ThreadPoolExecutor`.
- Thêm webhook alert (gửi POST đến URL khi alert).
- Thêm `-w/--watch` mode: chạy liên tục mỗi N giây.
- Vẽ ASCII chart response time trong terminal.

<details>
<summary>Solution / Reference</summary>

```python
#!/usr/bin/env python3
"""API Monitoring System with alerting and reporting."""

import argparse
import json
import logging
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
ENDPOINTS = [
    {"name": "HTTPBin OK", "url": "https://httpbin.org/get", "timeout": 10},
    {"name": "HTTPBin Delay", "url": "https://httpbin.org/delay/2", "timeout": 10,
     "warn_threshold": 1.0},
    {"name": "HTTPBin 500", "url": "https://httpbin.org/status/500", "timeout": 10},
]

RESPONSE_TIME_WARN = 2.0  # seconds
CONSECUTIVE_FAIL_CRITICAL = 3
DATA_FILE = "/tmp/api_monitor_data.json"


class EndpointState:
    """Track state for a single endpoint."""
    def __init__(self, name):
        self.name = name
        self.consecutive_failures = 0
        self.was_healthy = True
        self.total_checks = 0
        self.total_healthy = 0
        self.total_response_time = 0.0

    def record_success(self, response_time):
        self.total_checks += 1
        self.total_healthy += 1
        self.total_response_time += response_time

        if not self.was_healthy and self.consecutive_failures > 0:
            logger.info("RECOVERY %s — service is healthy again "
                        "(was down for %d checks)", self.name, self.consecutive_failures)

        self.consecutive_failures = 0
        self.was_healthy = True

    def record_failure(self, error):
        self.total_checks += 1
        self.consecutive_failures += 1
        self.was_healthy = False

        if self.consecutive_failures >= CONSECUTIVE_FAIL_CRITICAL:
            logger.critical("CRITICAL %s — %d consecutive failures: %s",
                            self.name, self.consecutive_failures, error)
        else:
            logger.warning("WARNING %s — failure #%d: %s",
                           self.name, self.consecutive_failures, error)

    @property
    def uptime_pct(self):
        if self.total_checks == 0:
            return 100.0
        return (self.total_healthy / self.total_checks) * 100

    @property
    def avg_response_time(self):
        if self.total_healthy == 0:
            return 0.0
        return self.total_response_time / self.total_healthy


def check_endpoint(endpoint):
    """Check single endpoint."""
    url = endpoint["url"]
    timeout = endpoint.get("timeout", 10)
    warn_threshold = endpoint.get("warn_threshold", RESPONSE_TIME_WARN)

    start = time.time()
    try:
        req = Request(url, headers={"User-Agent": "APIMonitor/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            duration = time.time() - start
            body_hash = hashlib.md5(body).hexdigest()[:8]

            result = {
                "timestamp": datetime.now().isoformat(),
                "name": endpoint["name"],
                "url": url,
                "status": "healthy",
                "http_code": resp.status,
                "response_time": round(duration, 3),
                "body_hash": body_hash,
                "body_size": len(body),
            }

            if duration > warn_threshold:
                result["slow"] = True
                logger.warning("SLOW %s — %.1fs (threshold: %.1fs)",
                               endpoint["name"], duration, warn_threshold)

            return result

    except (HTTPError, URLError, Exception) as e:
        duration = time.time() - start
        error_msg = str(getattr(e, 'reason', e))
        return {
            "timestamp": datetime.now().isoformat(),
            "name": endpoint["name"],
            "url": url,
            "status": "unhealthy",
            "http_code": getattr(e, 'code', 0),
            "response_time": round(duration, 3),
            "error": error_msg,
        }


def save_result(result, data_file):
    """Append result to data file."""
    data_path = Path(data_file)
    history = []
    if data_path.exists():
        try:
            history = json.loads(data_path.read_text())
        except json.JSONDecodeError:
            history = []

    history.append(result)
    # Keep last 1000 entries
    if len(history) > 1000:
        history = history[-1000:]

    data_path.write_text(json.dumps(history, indent=2))


def generate_report(states):
    """Generate summary report."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "endpoints": []
    }

    print("\n" + "=" * 60)
    print("  API Monitoring Summary Report")
    print("=" * 60)

    for name, state in states.items():
        ep_report = {
            "name": name,
            "total_checks": state.total_checks,
            "uptime_pct": round(state.uptime_pct, 2),
            "avg_response_time_ms": round(state.avg_response_time * 1000, 1),
            "consecutive_failures": state.consecutive_failures,
        }
        report["endpoints"].append(ep_report)

        status_icon = "OK" if state.was_healthy else "FAIL"
        print(f"  [{status_icon}] {name}")
        print(f"       Uptime: {state.uptime_pct:.1f}% "
              f"({state.total_healthy}/{state.total_checks})")
        print(f"       Avg Response: {state.avg_response_time * 1000:.0f}ms")
        if state.consecutive_failures > 0:
            print(f"       Consecutive Failures: {state.consecutive_failures}")
        print()

    print("=" * 60)
    return report


def main(args):
    states = {}
    for ep in ENDPOINTS:
        states[ep["name"]] = EndpointState(ep["name"])

    iterations = args.iterations

    for i in range(iterations):
        if i > 0:
            logger.info("--- Waiting %ds before next check ---", args.interval)
            time.sleep(args.interval)

        logger.info("=== Check #%d/%d ===", i + 1, iterations)

        for ep in ENDPOINTS:
            result = check_endpoint(ep)
            state = states[ep["name"]]

            if result["status"] == "healthy":
                state.record_success(result["response_time"])
                logger.info("OK   %s — %dms (HTTP %d)",
                            ep["name"],
                            int(result["response_time"] * 1000),
                            result["http_code"])
            else:
                state.record_failure(result.get("error", "unknown"))

            save_result(result, DATA_FILE)

    report = generate_report(states)

    if args.output_json:
        print(json.dumps(report, indent=2))

    unhealthy = sum(1 for s in states.values() if not s.was_healthy)
    return 1 if unhealthy > 0 else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Monitoring System")
    parser.add_argument("-n", "--iterations", type=int, default=1,
                        help="Number of check iterations (default: 1)")
    parser.add_argument("-i", "--interval", type=int, default=10,
                        help="Seconds between iterations (default: 10)")
    parser.add_argument("--output-json", action="store_true",
                        help="Output report as JSON")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    sys.exit(main(args))
```

**Test commands:**
```bash
# Single check
python3 api_monitor.py

# 3 iterations, 5 seconds apart
python3 api_monitor.py -n 3 -i 5

# With JSON output
python3 api_monitor.py -n 2 -i 5 --output-json

# View collected data
cat /tmp/api_monitor_data.json | python3 -m json.tool | head -30
```

</details>

---

## Tổng kết thời gian

| Bài | Độ khó | Thời gian ước tính |
|-----|--------|-------------------|
| Bài 1 | Easy | 20-30 phút |
| Bài 2 | Medium | 40-50 phút |
| Bài 3 | Hard | 60-90 phút |

Bài 1 + Bài 2 phù hợp cho 2 giờ/ngày. Bài 3 là bonus deep-dive.

