# Day 5: Document — Bash & Python Automation Cheat Sheet

---

## 1. Bash Script Template (Production-Grade)

```bash
#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════
# Script: script-name.sh
# Description: One-line description
# Usage: ./script-name.sh [OPTIONS] ARG1 ARG2
# ═══════════════════════════════════════════════════

# ── Constants ──
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly LOG_FILE="/var/log/${SCRIPT_NAME%.sh}.log"

# ── Defaults ──
VERBOSE=false
DRY_RUN=false

# ── Colors (optional) ──
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly NC='\033[0m'

# ── Logging ──
log()   { echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO]  $*" | tee -a "${LOG_FILE}"; }
warn()  { echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN]  $*" | tee -a "${LOG_FILE}" >&2; }
error() { echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $*" | tee -a "${LOG_FILE}" >&2; }
debug() { ${VERBOSE} && echo "$(date '+%Y-%m-%d %H:%M:%S') [DEBUG] $*" | tee -a "${LOG_FILE}"; }

# ── Cleanup ──
cleanup() {
    local exit_code=$?
    # Add cleanup logic here
    exit ${exit_code}
}
trap cleanup EXIT INT TERM

# ── Usage ──
usage() {
    cat <<EOF
Usage: ${SCRIPT_NAME} [OPTIONS] ARG1

Description here.

Options:
  -v, --verbose     Verbose output
  -d, --dry-run     Show what would happen
  -h, --help        Show this help

Examples:
  ${SCRIPT_NAME} /path/to/source
  ${SCRIPT_NAME} --dry-run /path/to/source
EOF
}

# ── Dependency Check ──
check_dependencies() {
    local deps=("curl" "jq" "tar")
    for dep in "${deps[@]}"; do
        command -v "${dep}" >/dev/null 2>&1 || {
            error "Required: ${dep} — install and retry"
            exit 1
        }
    done
}

# ── Parse Arguments ──
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -v|--verbose) VERBOSE=true; shift ;;
            -d|--dry-run) DRY_RUN=true; shift ;;
            -h|--help) usage; exit 0 ;;
            -*) error "Unknown option: $1"; usage; exit 2 ;;
            *) break ;;
        esac
    done

    if [[ $# -lt 1 ]]; then
        error "Missing required argument"
        usage
        exit 2
    fi

    readonly ARG1="$1"
}

# ── Main ──
main() {
    log "Starting ${SCRIPT_NAME}"
    check_dependencies
    
    # Core logic here
    
    log "Completed successfully"
}

parse_args "$@"
main
```

---

## 2. Python Script Template (DevOps)

```python
#!/usr/bin/env python3
"""One-line description of the script."""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Constants ──
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2


def run_command(cmd, timeout=DEFAULT_TIMEOUT, check=True):
    """Run shell command and return result."""
    logger.debug("Running: %s", cmd)
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        timeout=timeout
    )
    if check and result.returncode != 0:
        logger.error("Command failed: %s\nStderr: %s", cmd, result.stderr)
        raise RuntimeError(f"Command failed: {cmd}")
    return result


def retry(func, max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    """Retry function with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                raise
            wait = delay * (2 ** attempt)
            logger.warning("Attempt %d/%d failed: %s. Retrying in %ds...",
                           attempt + 1, max_retries, e, wait)
            time.sleep(wait)


def validate_environment():
    """Check prerequisites before running."""
    required_env = ["HOME"]  # Add required env vars
    for var in required_env:
        if not os.environ.get(var):
            raise EnvironmentError(f"Missing env var: {var}")


def main(args):
    """Main logic."""
    logger.info("Starting...")
    validate_environment()

    if args.dry_run:
        logger.info("[DRY-RUN] Would execute main logic")
        return 0

    # Core logic here

    logger.info("Completed successfully")
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('target', help='Target to process')
    parser.add_argument('-t', '--timeout', type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument('-n', '--dry-run', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        sys.exit(main(args))
    except KeyboardInterrupt:
        logger.info('Interrupted')
        sys.exit(130)
    except Exception as e:
        logger.error('Fatal: %s', e)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
```

---

## 3. Bash Common Patterns

### String Operations (avoid fork)

```bash
# ── Variable defaults ──
name="${1:-default_value}"          # Default if unset
name="${NAME:?ERROR: NAME required}" # Exit if unset

# ── String manipulation (no sed/awk needed!) ──
file="/path/to/file.tar.gz"
echo "${file##*/}"          # file.tar.gz  (basename)
echo "${file%/*}"           # /path/to     (dirname)
echo "${file%%.*}"          # /path/to/file (remove all extensions)
echo "${file%.gz}"          # /path/to/file.tar (remove last extension)
echo "${file#/path/}"       # to/file.tar.gz (remove prefix)

# ── Case conversion ──
str="Hello World"
echo "${str,,}"             # hello world  (lowercase)
echo "${str^^}"             # HELLO WORLD  (uppercase)

# ── Substitution ──
str="hello-world-test"
echo "${str//-/_}"          # hello_world_test  (replace all)
echo "${str/-/_}"           # hello_world-test  (replace first)

# ── Length ──
echo "${#str}"              # 16
```

### Array Operations

```bash
# ── Define ──
arr=("one" "two" "three")

# ── Access ──
echo "${arr[0]}"            # one (first)
echo "${arr[-1]}"           # three (last)
echo "${arr[@]}"            # all elements
echo "${#arr[@]}"           # 3 (count)

# ── Iterate ──
for item in "${arr[@]}"; do
    echo "$item"
done

# ── Append ──
arr+=("four")

# ── Slice ──
echo "${arr[@]:1:2}"        # two three (offset:count)

# ── Check if contains ──
[[ " ${arr[*]} " == *" two "* ]] && echo "found"
```

### Conditional Patterns

```bash
# ── File tests ──
[[ -f "$file" ]]     # File exists and is regular file
[[ -d "$dir" ]]      # Directory exists
[[ -r "$file" ]]     # File is readable
[[ -w "$file" ]]     # File is writable
[[ -x "$file" ]]     # File is executable
[[ -s "$file" ]]     # File exists and is not empty
[[ -L "$file" ]]     # File is symlink

# ── String tests ──
[[ -z "$var" ]]      # String is empty
[[ -n "$var" ]]      # String is not empty
[[ "$a" == "$b" ]]   # String equality
[[ "$a" != "$b" ]]   # String inequality
[[ "$a" =~ ^[0-9]+$ ]]  # Regex match (is numeric?)

# ── Numeric tests ──
[[ "$a" -eq "$b" ]]  # Equal
[[ "$a" -ne "$b" ]]  # Not equal
[[ "$a" -gt "$b" ]]  # Greater than
[[ "$a" -lt "$b" ]]  # Less than

# ── Command exists ──
command -v curl >/dev/null 2>&1
```

### Error Handling Patterns

```bash
# ── OR pattern (do if first fails) ──
mkdir /opt/app || { echo "Failed to create dir"; exit 1; }

# ── AND pattern (do if first succeeds) ──
[[ -f config.yaml ]] && source_config

# ── Try/catch equivalent ──
if ! output=$(some_command 2>&1); then
    echo "Failed: $output" >&2
    exit 1
fi

# ── Retry loop ──
retry() {
    local max_attempts="$1"; shift
    local delay="$1"; shift
    local attempt=0
    
    until "$@"; do
        attempt=$((attempt + 1))
        if [[ $attempt -ge $max_attempts ]]; then
            echo "Failed after $max_attempts attempts" >&2
            return 1
        fi
        echo "Attempt $attempt failed, retrying in ${delay}s..."
        sleep "$delay"
    done
}

# Usage: retry 3 5 curl -f http://api/health
```

---

## 4. Python Common Patterns for DevOps

### HTTP Requests (no external deps)

```python
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import json

def http_get(url, timeout=10, headers=None):
    """GET request, return (status, body)."""
    req = Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except HTTPError as e:
        return e.code, e.read().decode()
    except URLError as e:
        return 0, str(e.reason)

def http_post_json(url, data, timeout=10):
    """POST JSON request."""
    body = json.dumps(data).encode()
    req = Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    with urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read())
```

### File Operations

```python
from pathlib import Path
import shutil

# Read/write
content = Path("config.yaml").read_text()
Path("output.json").write_text(json.dumps(data, indent=2))

# Glob
for log_file in Path("/var/log").glob("*.log"):
    print(log_file.name, log_file.stat().st_size)

# Safe temp files
import tempfile
with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
    f.write(json.dumps(data).encode())
    temp_path = f.name

# Atomic file write (write temp, then rename)
temp = Path(f"{target}.tmp")
temp.write_text(content)
temp.rename(target)  # Atomic on same filesystem
```

### Subprocess (run CLI tools)

```python
import subprocess

# Simple run
result = subprocess.run(
    ["kubectl", "get", "pods", "-o", "json"],
    capture_output=True, text=True, timeout=30
)
if result.returncode == 0:
    pods = json.loads(result.stdout)

# With shell (use cautiously - injection risk)
result = subprocess.run(
    "docker ps --format '{{.Names}}'",
    shell=True, capture_output=True, text=True
)

# Stream output
proc = subprocess.Popen(
    ["tail", "-f", "/var/log/app.log"],
    stdout=subprocess.PIPE, text=True
)
for line in proc.stdout:
    if "ERROR" in line:
        print(f"Found error: {line.strip()}")
```

---

## 5. Bash vs Python Decision Matrix

```
Task complexity / Script length
│
│  Bash Zone              Python Zone
│  ─────────              ───────────
│
│  ┌──────────────┐       ┌──────────────────────┐
│  │ File ops     │       │ JSON/YAML processing │
│  │ CLI wrappers │       │ API integration      │
│  │ Health checks│       │ Complex logic        │
│  │ Log rotation │       │ Data transformation  │
│  │ Cron scripts │       │ Multi-step workflows │
│  │ Git hooks    │       │ Error handling       │
│  │ < 100 lines  │       │ Unit testable        │
│  └──────────────┘       │ > 100 lines          │
│                         └──────────────────────┘
│
└──────────────────────────────────────────────────→
  Simple                                    Complex

Rules of thumb:
  - Need jq in Bash?          → Use Python
  - Need subprocess in Python? → Use Bash (maybe)
  - Need tests?               → Use Python
  - Need no dependencies?     → Use Bash
  - Team knows Python better? → Use Python
  - Quick glue between CLIs?  → Use Bash
```

---

## 6. ShellCheck — Must-Use Tool

```bash
# Install
apt-get install shellcheck   # Debian/Ubuntu
brew install shellcheck      # macOS

# Run
shellcheck myscript.sh

# Common findings:
# SC2086: Double quote to prevent globbing/word splitting
# SC2046: Quote this to prevent word splitting
# SC2034: Variable appears unused
# SC2155: Declare and assign separately
# SC2162: read without -r will mangle backslashes

# Integrate with CI
# .github/workflows/lint.yml:
# - name: ShellCheck
#   uses: ludeeus/action-shellcheck@master

# VS Code extension: "ShellCheck" by timonwong
```

---

## 7. Cron Expression Reference

```
# ┌────── minute (0-59)
# │ ┌──── hour (0-23)
# │ │ ┌── day of month (1-31)
# │ │ │ ┌ month (1-12)
# │ │ │ │ ┌ day of week (0-7, 0&7=Sunday)
# │ │ │ │ │
# * * * * * command

# Common patterns
*/5 * * * *        # Every 5 minutes
0 * * * *          # Every hour (at :00)
0 */2 * * *        # Every 2 hours
0 9 * * *          # Daily at 9:00 AM
0 9 * * 1-5        # Weekdays at 9:00 AM
0 0 * * 0          # Weekly on Sunday at midnight
0 0 1 * *          # Monthly on 1st at midnight
0 2 * * *          # Daily at 2:00 AM (backup time)

# Best practices for cron scripts:
# 1. Always redirect output: >> /var/log/job.log 2>&1
# 2. Use absolute paths: /usr/bin/python3 /opt/scripts/job.py
# 3. Use flock to prevent overlapping: flock -n /tmp/job.lock /opt/scripts/job.sh
# 4. Set PATH explicitly: PATH=/usr/local/bin:/usr/bin:/bin
```

