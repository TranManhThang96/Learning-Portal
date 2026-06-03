# Day 5: Bash & Python Automation for DevOps

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Viết được Bash script production-grade** — sử dụng strict mode, exit codes, trap, error handling đúng cách.
2. **Phân biệt được khi nào dùng Bash, khi nào dùng Python** — dựa trên complexity, maintainability và team skill.
3. **Viết được script idempotent** — chạy nhiều lần cho cùng kết quả, không gây side effect.
4. **Tự động hóa được 3 task phổ biến** — health check, backup, và API monitoring.
5. **Áp dụng được best practices** cho DevOps scripting — logging, configuration, error reporting.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng trong production?

Automation là **DNA của DevOps**. Mọi task thủ công lặp lại đều là toil cần được tự động hóa. Kỹ năng scripting quyết định bạn là engineer **tạo ra automation** hay engineer **chờ người khác tạo automation**.

### Hậu quả nếu làm sai

| Sai lầm | Hậu quả thực tế |
|---------|-----------------|
| Script không có error handling | Script fail giữa chừng, để lại state không nhất quán → manual cleanup |
| Script không idempotent | Chạy lần 2 tạo duplicate, ghi đè data, hoặc crash |
| Hardcode credentials trong script | Git push → credentials leak → security incident |
| Bash cho logic phức tạp | Script 500 dòng Bash không ai đọc được, không test được |
| Không có logging | Script fail lúc 3 AM, không ai biết tại sao |

### Liên hệ với kiến thức developer

- **CI/CD pipeline**: Pipeline steps thực chất là scripts — build, test, deploy, health check.
- **Infrastructure as Code**: Terraform/Ansible gọi scripts cho custom logic.
- **Kubernetes**: Init containers, readiness probes, CronJobs đều chạy scripts.
- **Incident response**: Runbook automation — khi on-call, bạn muốn script sẵn, không muốn gõ command manual lúc 2 AM.

---

## 3. Kiến thức nền tảng

### 3.1. Bash Strict Mode

**Mọi Bash script production phải bắt đầu bằng:**

```bash
#!/usr/bin/env bash
set -euo pipefail
```

| Flag | Ý nghĩa | Vì sao cần |
|------|---------|-----------|
| `set -e` | Exit ngay khi command fail (non-zero exit code) | Tránh script tiếp tục chạy trên state lỗi |
| `set -u` | Exit khi dùng biến chưa define | Tránh bug do typo tên biến |
| `set -o pipefail` | Pipeline fail nếu BẤT KỲ command nào trong pipe fail | `cmd1 \| cmd2` — không bỏ qua lỗi cmd1 |

**Analogy cho developer**: Strict mode giống **TypeScript strict mode** — bắt lỗi sớm, tránh bug runtime.

### 3.2. Exit Code

```
Exit Code    Meaning
─────────────────────────
0            Success
1            General error
2            Misuse of shell command
126          Command cannot execute (permission)
127          Command not found
128+N        Fatal signal N (128+9=137 = SIGKILL, 128+15=143 = SIGTERM)
```

**Quy ước trong scripts**:
```bash
readonly EXIT_SUCCESS=0
readonly EXIT_ERROR=1
readonly EXIT_USAGE=2
readonly EXIT_DEPENDENCY=3
```

### 3.3. Pipe, Redirect, Process Substitution

```bash
# Pipe: stdout of cmd1 → stdin of cmd2
cmd1 | cmd2

# Redirect stdout to file
cmd > file.txt          # overwrite
cmd >> file.txt         # append

# Redirect stderr to file
cmd 2> error.txt

# Redirect both stdout and stderr
cmd > output.txt 2>&1   # Traditional
cmd &> output.txt       # Bash shorthand

# Process substitution (treat command output as file)
diff <(sort file1) <(sort file2)

# Here document
cat <<EOF
Hello $USER
Today is $(date)
EOF

# Here string
grep "pattern" <<< "$variable"
```

### 3.4. Trap — Cleanup on Exit

```bash
#!/usr/bin/env bash
set -euo pipefail

TMPDIR=""

cleanup() {
    local exit_code=$?
    echo "Cleaning up..."
    if [[ -n "${TMPDIR}" && -d "${TMPDIR}" ]]; then
        rm -rf "${TMPDIR}"
    fi
    exit $exit_code
}

trap cleanup EXIT ERR INT TERM

TMPDIR=$(mktemp -d)
echo "Working in ${TMPDIR}"
# ... do work ...
# cleanup runs automatically on exit, error, or signal
```

**Analogy**: `trap` giống `defer` trong Go hoặc `finally` trong try-catch — đảm bảo cleanup luôn chạy.

### 3.5. Idempotent Script

**Idempotent** = chạy 1 lần hay 100 lần cho cùng kết quả cuối cùng.

```bash
# ❌ NOT idempotent — sẽ append nhiều lần
echo "127.0.0.1 myapp.local" >> /etc/hosts

# ✅ Idempotent — check trước khi thêm
grep -qF "myapp.local" /etc/hosts || echo "127.0.0.1 myapp.local" >> /etc/hosts

# ❌ NOT idempotent — fail nếu directory đã tồn tại
mkdir /opt/myapp

# ✅ Idempotent
mkdir -p /opt/myapp

# ❌ NOT idempotent — tạo user lỗi nếu đã có
useradd appuser

# ✅ Idempotent
id appuser &>/dev/null || useradd appuser
```

### 3.6. Khi nào dùng Bash, khi nào dùng Python

| Tiêu chí | Bash | Python |
|----------|------|--------|
| **Độ dài** | < 100 dòng | > 100 dòng |
| **Logic** | Linear, simple conditions | Complex logic, data processing |
| **Data format** | Text, line-based | JSON, YAML, CSV, XML |
| **Error handling** | Basic (exit codes) | Rich (exceptions, retry, logging) |
| **Testing** | Khó | Dễ (pytest, unittest) |
| **Dependencies** | None (built-in OS) | Cần Python runtime |
| **Dùng cho** | Glue scripts, file ops, CLI wrappers | API calls, data transformation, complex automation |
| **Team readability** | DevOps team quen | Developer team quen |

**Quy tắc**: Nếu bạn cần `jq` để parse JSON trong Bash → chuyển sang Python. Nếu bạn cần gọi 3 CLI commands liên tiếp → Bash đủ.

---

## 4. Deep Dive

### 4.1. Script Architecture cho DevOps

```
Production Script Structure
━━━━━━━━━━━━━━━━━━━━━━━━━━

#!/usr/bin/env bash
set -euo pipefail

┌─────────────────────────┐
│ Constants & Config      │  ← Readonly variables, defaults
│ (no hardcoded secrets!) │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│ Functions              │  ← log(), cleanup(), validate()
│ (define before use)    │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│ Trap Setup             │  ← trap cleanup EXIT
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│ Input Validation       │  ← Check args, env vars, dependencies
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│ Main Logic             │  ← Core automation
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│ Verification           │  ← Verify result, output summary
└─────────────────────────┘
```

### 4.2. Python Automation Architecture

```python
#!/usr/bin/env python3
"""
Module docstring — one line what this does.
"""

import argparse
import logging
import sys
from pathlib import Path

# ── Logging setup ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Constants ──
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# ── Functions ──
def validate_environment():
    """Check prerequisites."""
    pass

def main(args):
    """Main logic."""
    pass

# ── Entry point ──
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='My automation script')
    parser.add_argument('--target', required=True, help='Target host')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verbose', '-v', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        validate_environment()
        main(args)
    except KeyboardInterrupt:
        logger.info('Interrupted by user')
        sys.exit(130)
    except Exception as e:
        logger.error(f'Fatal error: {e}')
        sys.exit(1)
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1. Script Language Selection

| Scenario | Recommended | Lý do |
|----------|------------|-------|
| Health check (5 dòng curl + grep) | Bash | Simple, no dependencies |
| Log rotation + cleanup | Bash | File operations, cron-friendly |
| Parse JSON API response + alert | Python | JSON handling, HTTP library |
| Database backup + upload S3 | Python | AWS SDK, error handling, retry |
| Kubernetes manifest generation | Python/Go | Template engine, type safety |
| Quick system diagnostics | Bash | Direct access to OS tools |
| Multi-step provisioning | Python + subprocess | Complex logic + CLI calls |

### 5.2. Anti-patterns

1. **Parsing ls output** — `ls` output không reliable cho scripting. Dùng glob: `for f in *.log; do`.
2. **Không quote variables** — `rm $FILE` → nếu FILE có space → delete sai file. Luôn `rm "$FILE"`.
3. **Secrets trong script** — KHÔNG `PASSWORD="abc123"`. Dùng env var hoặc secret manager.
4. **Script không có help** — `./script.sh --help` phải hoạt động.
5. **echo thay logging** — Production script cần timestamp, level, context. Không chỉ `echo`.
6. **Assume path/tool exists** — Check dependencies trước: `command -v curl >/dev/null 2>&1 || { echo "curl required"; exit 1; }`.

### 5.3. Logging Best Practice

```bash
# Bash logging function
readonly LOG_FILE="/var/log/myautomation.log"

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log INFO "Starting backup"
log WARN "Disk space below 20%"
log ERROR "Backup failed: connection refused"
```

---

## 6. Performance & Scalability ⭐

### 6.1. Bash Performance Tips

| Technique | Ưu điểm | Khi nào dùng |
|-----------|---------|-------------|
| `xargs -P` | Parallel execution | Process nhiều files/hosts |
| `GNU parallel` | Better parallel control | Complex parallel jobs |
| Built-in string ops | Avoid forking subshell | `${var%%pattern}` thay `echo \| sed` |
| `mapfile` / `readarray` | Read file into array efficiently | Process file line by line |
| `[[ ]]` thay `[ ]` | Faster, more features | All Bash conditionals |

```bash
# ❌ Slow: fork subprocess for each line
cat file.txt | while read line; do
    result=$(echo "$line" | sed 's/old/new/')
    echo "$result"
done

# ✅ Fast: use built-in
while IFS= read -r line; do
    echo "${line//old/new}"
done < file.txt

# ✅ Parallel processing with xargs
find /var/log -name "*.log.gz" | xargs -P 4 -I {} gunzip {}
```

### 6.2. Python Performance Tips

- **requests.Session()** cho multiple HTTP calls → connection pooling.
- **concurrent.futures** cho parallel HTTP calls.
- **subprocess.run()** thay `os.system()` — safer, more control.
- **pathlib.Path** thay string concatenation cho file paths.

---

## 7. Security & Reliability Considerations

### Security

- **Không bao giờ** store credentials trong script file.
- **Không bao giờ** log sensitive data (passwords, tokens, PII).
- Dùng `mktemp` cho temp files (predictable temp file name → symlink attack).
- Set restrictive permissions: `chmod 700 script.sh` (only owner can execute).
- Validate tất cả input: path traversal (`../../../etc/passwd`), command injection (`; rm -rf /`).

```bash
# ❌ Command injection vulnerable
filename="$1"
cat /var/log/$filename  # $1 = "../../etc/passwd" → leak!

# ✅ Validate input
filename="$1"
if [[ "$filename" =~ [^a-zA-Z0-9._-] ]]; then
    echo "Invalid filename" >&2
    exit 1
fi
cat "/var/log/${filename}"
```

### Reliability

- **Idempotent**: Script chạy nhiều lần không gây side effect.
- **Atomic operations**: Dùng `mv` (atomic) thay `cp` + `rm` cho file move.
- **Lock files**: Tránh 2 instances chạy cùng lúc.
- **Timeout**: Mọi network call phải có timeout.
- **Retry with backoff**: Network call fail → retry 3 lần với exponential backoff.

```bash
# Lock file to prevent concurrent execution
LOCKFILE="/tmp/mybackup.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "Another instance running"; exit 1; }
```

---

## 8. Hands-on Example

### 8.1. Health Check Script (Bash)

Tạo workspace local-first:

```bash
mkdir -p /tmp/devops-day05
cd /tmp/devops-day05
```

Lưu nội dung sau vào `healthcheck.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# ═══ Configuration ═══
readonly SCRIPT_NAME="$(basename "$0")"
readonly SERVICES=(
    "http://localhost:8080/health|API Gateway"
    "http://localhost:8081/health|User Service"
    "http://localhost:5432|PostgreSQL"
)
readonly TIMEOUT=5
readonly LOG_FILE="/tmp/healthcheck.log"

# ═══ Functions ═══
log() {
    local level="$1"; shift
    echo "$(date '+%Y-%m-%d %H:%M:%S') [${level}] $*" | tee -a "${LOG_FILE}"
}

check_http() {
    local url="$1"
    local name="$2"
    local http_code
    local response_time

    response_time=$(curl -o /dev/null -s -w "%{time_total}" \
        --connect-timeout "${TIMEOUT}" \
        --max-time "${TIMEOUT}" \
        "${url}" 2>/dev/null) || true

    http_code=$(curl -o /dev/null -s -w "%{http_code}" \
        --connect-timeout "${TIMEOUT}" \
        --max-time "${TIMEOUT}" \
        "${url}" 2>/dev/null) || http_code="000"

    if [[ "${http_code}" == "200" ]]; then
        log INFO "OK   ${name} (${url}) — ${response_time}s"
        return 0
    else
        log ERROR "FAIL ${name} (${url}) — HTTP ${http_code}"
        return 1
    fi
}

check_tcp() {
    local host="$1"
    local port="$2"
    local name="$3"

    if nc -z -w "${TIMEOUT}" "${host}" "${port}" 2>/dev/null; then
        log INFO "OK   ${name} (${host}:${port})"
        return 0
    else
        log ERROR "FAIL ${name} (${host}:${port})"
        return 1
    fi
}

# ═══ Main ═══
log INFO "=== Health Check Started ==="

FAILURES=0
for service in "${SERVICES[@]}"; do
    IFS='|' read -r endpoint name <<< "${service}"

    if [[ "${endpoint}" =~ ^http ]]; then
        check_http "${endpoint}" "${name}" || ((FAILURES++))
    else
        host=$(echo "${endpoint}" | sed 's|.*://||' | cut -d: -f1)
        port=$(echo "${endpoint}" | sed 's|.*://||' | cut -d: -f2)
        check_tcp "${host}" "${port}" "${name}" || ((FAILURES++))
    fi
done

log INFO "=== Health Check Complete: ${FAILURES} failures ==="

if [[ ${FAILURES} -gt 0 ]]; then
    log ERROR "ALERT: ${FAILURES} service(s) unhealthy!"
    exit 1
fi

exit 0
```

**Chạy:**
```bash
chmod +x healthcheck.sh
./healthcheck.sh || true

# Expected output:
# 2024-01-15 10:00:00 [INFO] === Health Check Started ===
# 2024-01-15 10:00:00 [ERROR] FAIL API Gateway (http://localhost:8080/health) — HTTP 000
# 2024-01-15 10:00:00 [ERROR] FAIL User Service (http://localhost:8081/health) — HTTP 000
# 2024-01-15 10:00:05 [ERROR] FAIL PostgreSQL (localhost:5432)
# 2024-01-15 10:00:05 [INFO] === Health Check Complete: 3 failures ===
# 2024-01-15 10:00:05 [ERROR] ALERT: 3 service(s) unhealthy!
```

**Verify**:

```bash
test -s /tmp/healthcheck.log && tail -3 /tmp/healthcheck.log
```

**Expected output**: thấy dòng `Health Check Complete` và `ALERT` khi các service local chưa chạy.

### 8.2. Backup Script with Rotation (Bash)

Lưu nội dung sau vào `backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# ═══ Configuration ═══
readonly BACKUP_SOURCE="${1:-/var/log}"
readonly BACKUP_DEST="${2:-/tmp/backups}"
readonly RETENTION_DAYS="${3:-7}"
readonly TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
readonly BACKUP_NAME="backup_${TIMESTAMP}.tar.gz"
readonly LOCKFILE="/tmp/backup.lock"

# ═══ Functions ═══
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BACKUP] $*"
}

cleanup_old_backups() {
    local count
    count=$(find "${BACKUP_DEST}" -name "backup_*.tar.gz" -mtime +"${RETENTION_DAYS}" | wc -l)
    if [[ ${count} -gt 0 ]]; then
        log "Removing ${count} backups older than ${RETENTION_DAYS} days"
        find "${BACKUP_DEST}" -name "backup_*.tar.gz" -mtime +"${RETENTION_DAYS}" -delete
    fi
}

# ═══ Lock ═══
exec 200>"${LOCKFILE}"
flock -n 200 || { log "Another backup running, exiting"; exit 1; }

# ═══ Validation ═══
if [[ ! -d "${BACKUP_SOURCE}" ]]; then
    log "ERROR: Source directory not found: ${BACKUP_SOURCE}"
    exit 1
fi

mkdir -p "${BACKUP_DEST}"

# ═══ Main ═══
log "Starting backup: ${BACKUP_SOURCE} → ${BACKUP_DEST}/${BACKUP_NAME}"

START_TIME=$(date +%s)
tar -czf "${BACKUP_DEST}/${BACKUP_NAME}" -C "$(dirname "${BACKUP_SOURCE}")" "$(basename "${BACKUP_SOURCE}")" 2>/dev/null
END_TIME=$(date +%s)

DURATION=$((END_TIME - START_TIME))
SIZE=$(du -h "${BACKUP_DEST}/${BACKUP_NAME}" | cut -f1)

log "Backup complete: ${SIZE} in ${DURATION}s"

# ═══ Verify ═══
if tar -tzf "${BACKUP_DEST}/${BACKUP_NAME}" > /dev/null 2>&1; then
    log "Verification: OK (archive is valid)"
else
    log "ERROR: Backup archive is corrupted!"
    rm -f "${BACKUP_DEST}/${BACKUP_NAME}"
    exit 1
fi

# ═══ Rotation ═══
cleanup_old_backups
TOTAL=$(find "${BACKUP_DEST}" -name "backup_*.tar.gz" | wc -l)
log "Total backups: ${TOTAL} (retention: ${RETENTION_DAYS} days)"
```

**Chạy**:

```bash
mkdir -p /tmp/devops-day05/input
printf 'hello\n' > /tmp/devops-day05/input/app.log
chmod +x backup.sh
./backup.sh /tmp/devops-day05/input /tmp/backups 7
```

**Expected output ví dụ**:

```text
2024-01-15 10:00:00 [BACKUP] Starting backup: /tmp/devops-day05/input → /tmp/backups/backup_20240115_100000.tar.gz
2024-01-15 10:00:00 [BACKUP] Backup complete: 4.0K in 0s
2024-01-15 10:00:00 [BACKUP] Verification: OK (archive is valid)
2024-01-15 10:00:00 [BACKUP] Total backups: 1 (retention: 7 days)
```

**Verify**:

```bash
tar -tzf /tmp/backups/backup_*.tar.gz | grep 'input/app.log'
```

**Expected output**:

```text
input/app.log
```

### 8.3. API Monitor Script (Python)

Lưu nội dung sau vào `api_monitor.py`:

```python
#!/usr/bin/env python3
"""Monitor API endpoints and alert when unhealthy."""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ENDPOINTS = [
    {"name": "API Gateway", "url": "http://localhost:8080/health", "timeout": 5},
    {"name": "User Service", "url": "http://localhost:8081/health", "timeout": 5},
]

def check_endpoint(endpoint: dict) -> dict:
    """Check single endpoint, return result dict."""
    name = endpoint["name"]
    url = endpoint["url"]
    timeout = endpoint.get("timeout", 10)

    start = time.time()
    try:
        req = Request(url, headers={"User-Agent": "HealthCheck/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")[:200]
            duration = time.time() - start

            return {
                "name": name,
                "url": url,
                "status": "healthy",
                "http_code": status,
                "response_time": round(duration, 3),
                "body": body.strip(),
            }
    except HTTPError as e:
        duration = time.time() - start
        return {
            "name": name,
            "url": url,
            "status": "unhealthy",
            "http_code": e.code,
            "response_time": round(duration, 3),
            "error": str(e.reason),
        }
    except URLError as e:
        duration = time.time() - start
        return {
            "name": name,
            "url": url,
            "status": "unhealthy",
            "http_code": 0,
            "response_time": round(duration, 3),
            "error": str(e.reason),
        }
    except Exception as e:
        return {
            "name": name,
            "url": url,
            "status": "unhealthy",
            "http_code": 0,
            "response_time": 0,
            "error": str(e),
        }


def send_alert(failures: list):
    """Send alert for unhealthy services."""
    logger.error("ALERT: %d service(s) unhealthy!", len(failures))
    for f in failures:
        logger.error("  - %s (%s): %s", f["name"], f["url"], f.get("error", "unknown"))


def main(args):
    logger.info("=== API Health Check Started ===")

    results = []
    for ep in ENDPOINTS:
        result = check_endpoint(ep)
        results.append(result)

        if result["status"] == "healthy":
            logger.info("OK   %s — %dms (HTTP %d)",
                        result["name"],
                        int(result["response_time"] * 1000),
                        result["http_code"])
        else:
            logger.warning("FAIL %s — %s", result["name"], result.get("error", ""))

    failures = [r for r in results if r["status"] == "unhealthy"]

    if failures:
        send_alert(failures)

    if args.output_json:
        report = {
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "healthy": len(results) - len(failures),
            "unhealthy": len(failures),
            "results": results,
        }
        print(json.dumps(report, indent=2))

    logger.info("=== Complete: %d/%d healthy ===",
                len(results) - len(failures), len(results))

    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Health Monitor")
    parser.add_argument("--output-json", action="store_true", help="Output JSON report")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    sys.exit(main(args))
```

**Chạy:**
```bash
python3 api_monitor.py || true
python3 api_monitor.py --output-json || true
python3 api_monitor.py -v --output-json || true
```

**Expected output khi chưa có service local**:

```text
WARNING FAIL API Gateway
WARNING FAIL User Service
ERROR ALERT: 2 service(s) unhealthy!
```

**Verify JSON output**:

```bash
python3 api_monitor.py --output-json 2>/dev/null || true
```

**Expected output excerpt**:

```json
{
  "total": 2,
  "healthy": 0,
  "unhealthy": 2
}
```

### Cleanup
```bash
# Xóa test files
rm -f /tmp/healthcheck.log
rm -rf /tmp/backups
rm -f /tmp/backup.lock
rm -rf /tmp/devops-day05
```

---

## 9. Common Pitfalls & Debugging

### 9.1. Pitfall: Word splitting và globbing

```bash
# ❌ DANGEROUS: nếu filename có space hoặc wildcard
file="my file*.txt"
rm $file
# Expands to: rm my file*.txt
# → Delete "my" AND tất cả files matching "file*.txt"!

# ✅ SAFE: always quote
rm "$file"
```

### 9.2. Pitfall: Pipe error swallowed

```bash
# ❌ Without pipefail: grep fails nhưng wc returns 0
grep "ERROR" /nonexistent/file | wc -l
echo $?  # 0 (from wc, not grep!)

# ✅ With pipefail
set -o pipefail
grep "ERROR" /nonexistent/file | wc -l
echo $?  # 2 (from grep!)
```

### 9.3. Pitfall: Script partial failure

```bash
# ❌ Script stops mid-way, temp directory left behind
#!/bin/bash
TMPDIR=$(mktemp -d)
cp data.txt "$TMPDIR/"
process_data "$TMPDIR/data.txt"  # This fails!
rm -rf "$TMPDIR"                  # Never reached!

# ✅ Use trap for cleanup
#!/usr/bin/env bash
set -euo pipefail
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
cp data.txt "$TMPDIR/"
process_data "$TMPDIR/data.txt"
# TMPDIR cleaned up automatically on exit (success or failure)
```

### 9.4. Case Study: Cron Job Silent Failure

**Context**: Backup script chạy daily bằng cron. Một ngày database crash, cần restore. Phát hiện backup script đã fail 2 tuần nhưng không ai biết.

**Symptom**: Backup files cũ 2 tuần, không có file mới.

**Root cause**: 
- Script fail vì disk full
- Cron redirect stdout/stderr vào `/dev/null` → không có log
- Không có monitoring cho backup freshness

**Fix**:
1. Script phải log ra file, không redirect `/dev/null`
2. Thêm monitoring: alert nếu backup file age > 25 hours
3. Script phải exit non-zero khi fail → cron email notification

**Prevention**: Cron entry nên redirect logs, not silence:
```bash
# ❌ Silent failure
0 2 * * * /opt/scripts/backup.sh > /dev/null 2>&1

# ✅ Capture logs
0 2 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 4: Linux Performance & Debugging Tools
- Day 4 sử dụng tools interactively (top, vmstat, iostat) → Day 5 tự động hóa bằng scripts.
- Monitoring script (Day 5) sử dụng metrics từ Day 4 (CPU, memory, disk, network).
- Performance baseline collection (Day 4) có thể được tự động hóa bằng scripts (Day 5).

### Bài sau — Day 6: Git Workflows & Release Models
- Day 5 hoàn thành Phase 1 Foundation (Linux + Networking + Automation).
- Scripts viết trong Day 5 sẽ được version control trong Day 6 (Git).
- Health check và deployment scripts sẽ nằm trong CI/CD pipeline (Phase 5).

### Kết nối Phase 1 → Phase 2
Sau Day 5 (và Day 6-7), bạn đã có nền tảng:
- Linux process/signal → hiểu container (Day 8-9)
- Networking → hiểu Kubernetes networking (Day 12-13)
- Performance tools → debug Kubernetes workloads (Day 18-22)
- Scripting → automate Kubernetes operations (Day 16-17)

---

## 11. Tài liệu tham khảo

### Must-read
- **Bash Strict Mode**: http://redsymbol.net/articles/unofficial-bash-strict-mode/ — Vì sao cần `set -euo pipefail`.
- **Google Shell Style Guide**: https://google.github.io/styleguide/shellguide.html — Best practices cho Bash production.
- **ShellCheck**: https://www.shellcheck.net/ — Static analysis cho shell scripts (phải dùng!).

### Nice-to-have
- **"The Linux Command Line" by William Shotts** (free online) — Bash scripting chapters.
- **Python for DevOps** by Noah Gift — Python automation cho infrastructure.
- **Advanced Bash-Scripting Guide**: https://tldp.org/LDP/abs/html/ — Reference chi tiết.

### Deep-dive
- **Bash Pitfalls**: https://mywiki.wooledge.org/BashPitfalls — 80+ common Bash mistakes.
- **Pure Bash Bible**: https://github.com/dylanaraps/pure-bash-bible — Bash built-in alternatives to external tools.
- **Fabric/Invoke (Python)**: https://www.fabfile.org/ — Python task execution framework cho DevOps.

