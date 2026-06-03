# Day 45: Exercises — DevSecOps SAST, DAST, SCA, Secret Scanning

> **3 bài tập từ Easy → Hard** | Thời gian: ~90 phút tổng

---

## Exercise 1 (Easy): Chạy Trivy scan nhiều loại target

### Bối cảnh

Bạn vừa join một team đang dùng Python và Docker. Tech lead yêu cầu bạn chạy thử security scan trước khi team bắt đầu setup full pipeline. Nhiệm vụ: chạy Trivy scan trên 3 loại target khác nhau và hiểu output.

### Requirements

1. Install Trivy trên máy local.
2. Scan một container image phổ biến (nginx:1.24) — tìm CRITICAL CVEs.
3. Tạo `requirements.txt` với các packages cũ và scan bằng `trivy fs`.
4. Scan một Dockerfile có intentional misconfiguration bằng `trivy config`.
5. Export kết quả ra JSON và tóm tắt: bao nhiêu CRITICAL, HIGH, MEDIUM?

### Expected Outcome

```
# Terminal output sau khi hoàn thành:
=== Image Scan: nginx:1.24 ===
CRITICAL: X findings
HIGH:     Y findings

=== Filesystem Scan: requirements.txt ===
CRITICAL: X findings (package: ..., CVE: ...)
HIGH:     Y findings

=== Config Scan: Dockerfile ===
FAILURE: Z misconfigurations found
  - Running as root
  - No healthcheck
  ...

=== Summary JSON ===
{
  "total_critical": ...,
  "total_high": ...,
  "action_required": true/false
}
```

### Hints

- Install Trivy: `brew install trivy` (Mac) hoặc `curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin`
- Scan image: `trivy image --severity CRITICAL,HIGH nginx:1.24`
- Scan filesystem: `trivy fs --severity CRITICAL,HIGH .`
- Scan Dockerfile config: `trivy config Dockerfile`
- JSON output: thêm `--format json --output results.json`
- Đọc JSON: `cat results.json | python3 -m json.tool | grep -A2 '"Severity"'`

### Acceptance Criteria

- [ ] Chạy được `trivy image` và giải thích được ít nhất 1 CVE trong output (CVE ID, severity, affected package, fix version).
- [ ] Chạy được `trivy fs` trên `requirements.txt` chứa ít nhất 1 vulnerable package.
- [ ] Chạy được `trivy config` và thấy ít nhất 1 Dockerfile misconfiguration.
- [ ] Export được kết quả ra JSON.
- [ ] Viết được 3-5 câu tóm tắt: "Nếu đây là production, action cần làm ngay là gì?"

### Bonus Challenge

Tạo script `security-check.sh` nhận tên image làm argument và in ra:
- Exit 0 nếu không có CRITICAL
- Exit 1 nếu có CRITICAL, kèm danh sách CVE IDs


---

## Exercise 2 (Medium): Setup Full Security Pipeline trong GitHub Actions

### Bối cảnh

Team của bạn đang build một REST API bằng Node.js với Express. CTO yêu cầu mọi PR phải pass security scan trước khi được merge vào `main`. Nhiệm vụ: thiết lập GitHub Actions pipeline với SAST (Semgrep), SCA (Trivy), và Secret Scanning (GitLeaks) — với policy gate hợp lý.

### Requirements

1. Tạo một Node.js app nhỏ với ít nhất 2 intentional vulnerabilities (SQL injection, hardcoded secret).
2. Tạo `package.json` với ít nhất 1 vulnerable dependency (package version cũ).
3. Tạo `.github/workflows/security.yml` với:
   - Job 1: GitLeaks secret scanning (fail nếu tìm thấy secret)
   - Job 2: Semgrep SAST (fail nếu có ERROR-severity finding)
   - Job 3: Trivy SCA (fail nếu có CRITICAL, ignore unfixed)
   - Job 4: Summary report (luôn chạy, tổng hợp kết quả)
4. Jobs 1-3 chạy **song song**.
5. Thêm `.semgrepignore` để exclude `test/` directory.
6. Thêm `.gitleaksignore` để suppress 1 false positive trong test file.
7. Verify pipeline chạy đúng bằng cách push lên GitHub và xem Actions tab.

### Expected Outcome

```
GitHub Actions tab hiển thị:
┌─────────────────────────────────────────────────────┐
│ Security Scanning                                   │
│                                                     │
│ ● Secret Scanning (GitLeaks)    ✓ / ✗             │
│ ● SAST (Semgrep)                ✓ / ✗  (parallel) │
│ ● SCA (Trivy)                   ✓ / ✗  (parallel) │
│                                                     │
│ ● Security Summary              ✓ (always runs)   │
└─────────────────────────────────────────────────────┘

Step Summary tab hiển thị bảng:
| Check | Status |
|-------|--------|
| Secret Scanning | failure |
| SAST | failure |
| SCA | success |
```

### Hints

- Tạo repo mới trên GitHub, không dùng repo production
- Semgrep chạy không cần token: `pip install semgrep && semgrep --config=auto .`
- GitLeaks GitHub Action: `gitleaks/gitleaks-action@v2`
- Trivy Action: `aquasecurity/trivy-action@master` với `scan-type: 'fs'`
- `needs: [job1, job2, job3]` để tạo dependency
- `if: always()` để summary job luôn chạy dù job khác fail
- `$&#123;&#123; needs.job-name.result &#125;&#125;` để lấy status của job

### Acceptance Criteria

- [ ] Pipeline yaml hợp lệ (không syntax error).
- [ ] 3 security jobs chạy song song (xem timeline trong Actions).
- [ ] GitLeaks job fail khi app.js chứa hardcoded API key.
- [ ] Semgrep job fail khi tìm thấy SQL injection pattern.
- [ ] Summary job luôn chạy và hiển thị bảng kết quả trong Step Summary.
- [ ] `.semgrepignore` hoạt động: Semgrep không scan `test/` directory.
- [ ] Push commit fix vulnerabilities → pipeline pass.

### Bonus Challenge

Thêm job thứ 5 chạy **sau** 3 jobs kia:
- Nếu tất cả pass: tag commit với `security-approved-{sha}`
- Nếu có job fail: tạo GitHub Issue với label `security` và title chứa commit SHA


---

## Exercise 3 (Hard): Thiết kế Security Scanning Strategy cho Microservices Platform

### Bối cảnh

Bạn là Senior DevOps Engineer tại một fintech startup chuẩn bị scale từ monolith lên 12 microservices. CTO yêu cầu bạn thiết kế và implement toàn bộ security scanning strategy cho platform, bao gồm policy gates phù hợp cho từng loại service (internal, customer-facing, payment).

### Requirements

**Phần A: Thiết kế Architecture (tài liệu)**

1. Vẽ sơ đồ (ASCII art hoặc mermaid) cho toàn bộ security scanning pipeline.
2. Phân loại 3 tier services với policy khác nhau:
   - Internal services (low risk): warn on HIGH, fail on CRITICAL
   - Customer-facing services (medium risk): fail on HIGH + CRITICAL
   - Payment services (high risk): fail on MEDIUM + HIGH + CRITICAL
3. Thiết kế triage process: ai review findings, SLA cho từng severity.
4. Thiết kế false positive management: suppression workflow có audit trail.

**Phần B: Implementation (code và config)**

1. Tạo reusable GitHub Actions workflow (`security-scan.yml`) dùng `workflow_call` để các service repos gọi vào.
2. Input parameters cho workflow:
   - `service_tier` (internal/customer/payment)
   - `image_name`
   - `fail_on_severity` (auto-detect từ tier)
3. Tạo custom Semgrep rule cho fintech use case: detect việc log sensitive data (credit card, SSN, account numbers).
4. Tạo Trivy ignore file strategy: global ignores + per-service ignores.
5. Script tự động tạo GitHub Issues từ critical findings với đầy đủ context.
6. Tạo weekly scheduled scan cho tất cả production images.

**Phần C: Metrics & Reporting**

1. Thiết kế security metrics dashboard (mô tả, không cần implement):
   - MTTR (Mean Time to Remediate) per severity
   - Vulnerability trends over time
   - False positive rate per tool
2. Viết `security-report.py` script tổng hợp Trivy JSON output thành Markdown report.

### Expected Outcome

```
Deliverables:
├── design/
│   ├── security-architecture.md    # Pipeline diagram + policy matrix
│   └── triage-runbook.md           # Triage process + SLAs
├── .github/workflows/
│   ├── security-scan.yml           # Reusable workflow
│   └── weekly-scan.yml             # Scheduled scan
├── security/
│   ├── semgrep/
│   │   └── fintech-rules.yaml      # Custom Semgrep rules
│   ├── trivy/
│   │   ├── global.trivyignore      # Global false positive suppressions
│   │   └── payment-service.trivyignore  # Service-specific ignores
│   └── scripts/
│       ├── create-security-issue.sh    # Auto-create GitHub Issues
│       └── security-report.py          # JSON → Markdown report
└── example-service/
    ├── app.py                      # Demo fintech service
    └── .github/workflows/ci.yml    # Calls reusable workflow
```

### Acceptance Criteria

- [ ] Reusable workflow nhận `service_tier` và tự động set `fail_on_severity` phù hợp.
- [ ] Calling workflow từ service repo chỉ cần 5 dòng YAML (không duplicate logic).
- [ ] Custom Semgrep rule detect ít nhất 2 patterns: log credit card, log SSN.
- [ ] `security-report.py` đọc Trivy JSON và output Markdown table với: CVE ID, package, severity, fix version, status.
- [ ] `create-security-issue.sh` nhận JSON path làm argument và tạo GitHub Issue với body có: CVE details, affected service, remediation steps.
- [ ] `weekly-scan.yml` chạy vào 2:00 AM thứ Hai mỗi tuần, scan tất cả production images được define trong `production-images.txt`.
- [ ] Tài liệu policy matrix rõ ràng: ai phê duyệt false positive suppression (peer review vs security team sign-off).

### Hints

- Reusable workflow: `on: workflow_call:` với `inputs:` và `secrets:` sections
- Service tier → severity mapping: dùng `if/elif` trong bash hoặc matrix strategy
- Semgrep custom rule: pattern `metavariable-regex` để match credit card patterns
- GitHub Issues API: `gh issue create --repo $GITHUB_REPOSITORY --title "..." --body "..."`
- Scheduled scan: `on: schedule: - cron: '0 2 * * 1'`
- `security-report.py`: parse `data['Results'][*]['Vulnerabilities']`, group by severity

### Bonus Challenge

Implement **Security Scorecard** cho mỗi service:
- Score từ 0-100 dựa trên: số CRITICAL (mỗi cái -20), số HIGH (-5), số suppressed findings (+bonus nếu documented)
- In ra scorecard sau mỗi scan
- Fail build nếu score < 70

---

## Solutions

<details>
<summary>Xem Solution</summary>

```bash
#!/bin/bash
# Exercise 1 Solution

# 1. Install Trivy (nếu chưa có)
which trivy || curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /tmp/bin
export PATH=$PATH:/tmp/bin

mkdir -p ex1-trivy-scan && cd ex1-trivy-scan

# 2. Image scan
echo "=== Scanning nginx:1.24 ==="
trivy image --severity CRITICAL,HIGH \
            --format table \
            nginx:1.24 2>/dev/null | tee image-scan.txt
echo ""

# 3. Tạo requirements.txt với vulnerable packages
cat > requirements.txt << 'EOF'
flask==2.3.3
cryptography==38.0.0
requests==2.28.0
Pillow==9.3.0
Django==3.2.0
EOF

echo "=== Scanning requirements.txt ==="
trivy fs --severity CRITICAL,HIGH \
         --format table \
         . 2>/dev/null | tee fs-scan.txt
echo ""

# 4. Tạo Dockerfile với misconfigurations
cat > Dockerfile << 'EOF'
FROM ubuntu:20.04
RUN apt-get update && apt-get install -y python3
COPY . /app
CMD ["python3", "/app/main.py"]
# Missing: USER, HEALTHCHECK, pinned base image
EOF

echo "=== Scanning Dockerfile config ==="
trivy config --severity HIGH,CRITICAL \
             --format table \
             Dockerfile 2>/dev/null | tee config-scan.txt
echo ""

# 5. Export JSON và parse
trivy image --severity CRITICAL,HIGH \
            --format json \
            --output results.json \
            nginx:1.24 2>/dev/null

python3 << 'PYEOF'
import json

with open('results.json') as f:
    data = json.load(f)

critical_count = 0
high_count = 0
critical_cves = []

for result in data.get('Results', []):
    for vuln in result.get('Vulnerabilities', []) or []:
        sev = vuln.get('Severity', '')
        if sev == 'CRITICAL':
            critical_count += 1
            critical_cves.append(vuln.get('VulnerabilityID', ''))
        elif sev == 'HIGH':
            high_count += 1

summary = {
    "image": "nginx:1.24",
    "total_critical": critical_count,
    "total_high": high_count,
    "critical_cves": critical_cves[:5],  # Top 5
    "action_required": critical_count > 0
}
print(json.dumps(summary, indent=2))
PYEOF

# Bonus: security-check.sh
cat > security-check.sh << 'EOF'
#!/bin/bash
IMAGE=${1:-nginx:latest}
echo "Scanning $IMAGE for CRITICAL vulnerabilities..."

CRITICAL_COUNT=$(trivy image --severity CRITICAL \
                              --quiet \
                              --format json \
                              "$IMAGE" 2>/dev/null | \
                 python3 -c "
import json,sys
d=json.load(sys.stdin)
total=sum(len([v for v in (r.get('Vulnerabilities') or []) if v.get('Severity')=='CRITICAL'])
          for r in d.get('Results',[]))
print(total)
")

if [ "$CRITICAL_COUNT" -eq 0 ]; then
  echo "PASS: No CRITICAL vulnerabilities found in $IMAGE"
  exit 0
else
  echo "FAIL: $CRITICAL_COUNT CRITICAL vulnerabilities found in $IMAGE"
  trivy image --severity CRITICAL --quiet "$IMAGE" 2>/dev/null
  exit 1
fi
EOF
chmod +x security-check.sh
./security-check.sh nginx:1.24
```

</details>

<details>
<summary>Xem Solution</summary>

**Cấu trúc thư mục:**
```
node-api-demo/
├── app.js                          # App với vulnerabilities
├── package.json                    # Với vulnerable dep
├── test/
│   └── auth.test.js                # Test với "fake" secret
├── .semgrepignore                  # Exclude test/
├── .gitleaksignore                 # Suppress test false positive
└── .github/
    └── workflows/
        └── security.yml
```

**app.js:**
```javascript
const express = require('express');
const mysql = require('mysql2');
const app = express();

// VULNERABILITY 1: Hardcoded secret (GitLeaks will catch)
const API_KEY = "sk-prod-abc123def456ghi789";
const DB_PASSWORD = "P@ssw0rd123!";

app.use(express.json());

const db = mysql.createConnection({
  host: 'localhost',
  user: 'root',
  password: DB_PASSWORD,
  database: 'mydb'
});

// VULNERABILITY 2: SQL Injection (Semgrep will catch)
app.get('/user', (req, res) => {
  const userId = req.query.id;
  // Semgrep will flag this pattern:
  const query = `SELECT * FROM users WHERE id = ${userId}`;
  db.query(query, (err, results) => {
    res.json(results);
  });
});

// VULNERABILITY 3: eval() usage (Semgrep will catch)
app.post('/calc', (req, res) => {
  const expr = req.body.expression;
  const result = eval(expr);  // nosemgrep for intentional demo
  res.json({ result });
});

app.listen(3000);
module.exports = app;
```

**package.json:**
```json
{
  "name": "node-api-demo",
  "version": "1.0.0",
  "dependencies": {
    "express": "4.18.2",
    "mysql2": "3.6.0",
    "lodash": "4.17.19",
    "axios": "0.21.1"
  },
  "devDependencies": {
    "jest": "29.7.0"
  }
}
```

**test/auth.test.js:**
```javascript
// Test credentials - NOT real secrets
// gitleaks:allow - these are test-only values
const TEST_PASSWORD = "test_password_only_for_unit_tests";
const TEST_TOKEN = "test-token-not-real";

describe('Auth tests', () => {
  it('rejects wrong password', () => {
    expect(authenticate(TEST_PASSWORD)).toBe(false);
  });
});
```

**.semgrepignore:**
```
test/
*.test.js
*.spec.js
node_modules/
```

**.gitleaksignore:**
```
# False positive: test credentials in unit tests
# Reviewed: not real secrets, only used in test environment
test/auth.test.js:TEST_PASSWORD:3
test/auth.test.js:TEST_TOKEN:4
```

**.github/workflows/security.yml:**
```yaml
name: Security Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read
  security-events: write
  issues: write

jobs:
  secret-scan:
    name: Secret Scanning (GitLeaks)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  sast:
    name: SAST (Semgrep)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Semgrep
        run: pip install semgrep
      - name: Run Semgrep
        run: |
          semgrep --config=auto \
                  --json \
                  --output semgrep-results.json \
                  . || true
          python3 -c "
          import json, sys
          with open('semgrep-results.json') as f:
              data = json.load(f)
          errors = [r for r in data.get('results', [])
                    if r.get('extra', {}).get('severity') in ['ERROR', 'WARNING']]
          print(f'Total findings: {len(data[\"results\"])}')
          print(f'Error/Warning findings: {len(errors)}')
          for e in errors[:10]:
              print(f'  [{e[\"extra\"][\"severity\"]}] {e[\"check_id\"]} at {e[\"path\"]}:{e[\"start\"][\"line\"]}')
          if errors:
              sys.exit(1)
          "

  sca:
    name: SCA (Trivy Filesystem)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy SCA
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL'
          exit-code: '1'
          ignore-unfixed: true

  security-summary:
    name: Security Gate Summary
    runs-on: ubuntu-latest
    needs: [secret-scan, sast, sca]
    if: always()
    steps:
      - name: Write summary
        run: |
          echo "## Security Gate Results" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Check | Status |" >> $GITHUB_STEP_SUMMARY
          echo "|-------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Secret Scanning (GitLeaks) | ${{ needs.secret-scan.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| SAST (Semgrep) | ${{ needs.sast.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| SCA (Trivy) | ${{ needs.sca.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          if [[ "${{ needs.secret-scan.result }}" == "failure" ||
                "${{ needs.sast.result }}" == "failure" ||
                "${{ needs.sca.result }}" == "failure" ]]; then
            echo "> ❌ Security gate FAILED. Fix issues before merging." >> $GITHUB_STEP_SUMMARY
            exit 1
          else
            echo "> ✅ All security checks passed." >> $GITHUB_STEP_SUMMARY
          fi
```

</details>

<details>
<summary>Xem Solution (Core Components)</summary>

**.github/workflows/security-scan.yml (Reusable Workflow):**
```yaml
name: Reusable Security Scan

on:
  workflow_call:
    inputs:
      service_tier:
        required: true
        type: string
        description: "Service tier: internal, customer, payment"
      image_name:
        required: false
        type: string
        description: "Docker image to scan (optional)"
      skip_dast:
        required: false
        type: boolean
        default: true
    secrets:
      GITHUB_TOKEN:
        required: true

jobs:
  determine-policy:
    name: Determine Security Policy
    runs-on: ubuntu-latest
    outputs:
      fail_severity: ${{ steps.policy.outputs.fail_severity }}
      semgrep_error_on: ${{ steps.policy.outputs.semgrep_error_on }}
    steps:
      - id: policy
        run: |
          TIER="${{ inputs.service_tier }}"
          case $TIER in
            payment)
              echo "fail_severity=CRITICAL,HIGH,MEDIUM" >> $GITHUB_OUTPUT
              echo "semgrep_error_on=ERROR,WARNING" >> $GITHUB_OUTPUT
              echo "Tier: PAYMENT (strictest policy)"
              ;;
            customer)
              echo "fail_severity=CRITICAL,HIGH" >> $GITHUB_OUTPUT
              echo "semgrep_error_on=ERROR" >> $GITHUB_OUTPUT
              echo "Tier: CUSTOMER (medium policy)"
              ;;
            internal)
              echo "fail_severity=CRITICAL" >> $GITHUB_OUTPUT
              echo "semgrep_error_on=ERROR" >> $GITHUB_OUTPUT
              echo "Tier: INTERNAL (standard policy)"
              ;;
            *)
              echo "Unknown tier: $TIER"
              exit 1
              ;;
          esac

  secret-scan:
    name: Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  sast:
    name: SAST (Semgrep + Custom Rules)
    runs-on: ubuntu-latest
    needs: [determine-policy]
    steps:
      - uses: actions/checkout@v4
      - name: Install Semgrep
        run: pip install semgrep
      - name: Run Semgrep with custom fintech rules
        run: |
          semgrep --config=auto \
                  --config=security/semgrep/ \
                  --json \
                  --output semgrep-results.json \
                  . || true

          ERROR_THRESHOLD="${{ needs.determine-policy.outputs.semgrep_error_on }}"
          python3 << 'PYEOF'
          import json, sys, os
          threshold = os.environ.get('ERROR_THRESHOLD', 'ERROR').split(',')
          with open('semgrep-results.json') as f:
              data = json.load(f)
          blocking = [r for r in data.get('results', [])
                      if r.get('extra', {}).get('severity') in threshold]
          print(f"Total: {len(data['results'])}, Blocking: {len(blocking)}")
          for r in blocking:
              print(f"  [{r['extra']['severity']}] {r['check_id']} @ {r['path']}:{r['start']['line']}")
          if blocking:
              sys.exit(1)
          PYEOF
        env:
          ERROR_THRESHOLD: ${{ needs.determine-policy.outputs.semgrep_error_on }}

  sca:
    name: SCA (Trivy)
    runs-on: ubuntu-latest
    needs: [determine-policy]
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy SCA
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: ${{ needs.determine-policy.outputs.fail_severity }}
          exit-code: '1'
          ignore-unfixed: true
          trivyignore-file: 'security/trivy/global.trivyignore'

  container-scan:
    name: Container Scan
    runs-on: ubuntu-latest
    needs: [determine-policy]
    if: inputs.image_name != ''
    steps:
      - name: Run Trivy image scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'image'
          image-ref: ${{ inputs.image_name }}
          severity: ${{ needs.determine-policy.outputs.fail_severity }}
          exit-code: '1'
          format: 'json'
          output: 'trivy-image.json'
      - name: Generate report & create issues for criticals
        if: failure()
        run: |
          python3 security/scripts/security-report.py trivy-image.json
          bash security/scripts/create-security-issue.sh trivy-image.json
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SERVICE_TIER: ${{ inputs.service_tier }}
```

**security/semgrep/fintech-rules.yaml:**
```yaml
rules:
  # Rule 1: Detect credit card numbers being logged
  - id: log-credit-card-number
    patterns:
      - pattern-either:
          - pattern: logging.$FUNC(..., $CC, ...)
          - pattern: logger.$FUNC(..., $CC, ...)
          - pattern: print($CC)
      - metavariable-regex:
          metavariable: $CC
          regex: '(?:card|credit|pan|cc).*'
    message: >
      Potential credit card number being logged.
      Logging PAN (Primary Account Number) violates PCI-DSS requirement 3.4.
      Mask or tokenize before logging: $CC → mask_card($CC)
    languages: [python, javascript, go]
    severity: ERROR
    metadata:
      category: security
      cwe: CWE-532
      compliance: PCI-DSS-3.4

  # Rule 2: Detect SSN being logged
  - id: log-ssn
    patterns:
      - pattern-either:
          - pattern: logging.$FUNC(..., $SSN, ...)
          - pattern: logger.$FUNC(..., $SSN, ...)
      - metavariable-regex:
          metavariable: $SSN
          regex: '(?:ssn|social.?security|tax.?id).*'
    message: >
      Potential SSN being logged. Logging SSN violates PII regulations (GDPR, CCPA).
    languages: [python, javascript, go]
    severity: ERROR
    metadata:
      category: security
      compliance: GDPR-Article-5

  # Rule 3: Unencrypted account number storage
  - id: plaintext-account-storage
    patterns:
      - pattern: $OBJ.account_number = $VAL
      - pattern-not: $OBJ.account_number = encrypt($VAL)
      - pattern-not: $OBJ.account_number = tokenize($VAL)
    message: "Account numbers should be encrypted or tokenized before storage."
    languages: [python]
    severity: WARNING
```

**security/scripts/security-report.py:**
```python
#!/usr/bin/env python3
"""Convert Trivy JSON output to Markdown security report."""
import json
import sys
from datetime import datetime


def severity_emoji(severity):
    return {
        'CRITICAL': '🔴',
        'HIGH': '🟠',
        'MEDIUM': '🟡',
        'LOW': '🟢',
        'UNKNOWN': '⚪'
    }.get(severity, '⚪')


def generate_report(json_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)

    lines = [
        f"# Security Scan Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
        f"Target: {data.get('ArtifactName', 'Unknown')}",
        "",
        "## Summary",
    ]

    all_vulns = []
    for result in data.get('Results', []):
        for v in result.get('Vulnerabilities') or []:
            v['_target'] = result.get('Target', '')
            all_vulns.append(v)

    by_severity = {}
    for v in all_vulns:
        sev = v.get('Severity', 'UNKNOWN')
        by_severity.setdefault(sev, []).append(v)

    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = len(by_severity.get(sev, []))
        lines.append(f"- {severity_emoji(sev)} **{sev}**: {count}")

    lines += ["", "## Vulnerabilities", ""]
    lines += ["| Severity | CVE ID | Package | Version | Fix Version | Target |"]
    lines += ["|----------|--------|---------|---------|-------------|--------|"]

    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        for v in by_severity.get(sev, []):
            lines.append(
                f"| {severity_emoji(sev)} {sev} "
                f"| [{v.get('VulnerabilityID', 'N/A')}](https://nvd.nist.gov/vuln/detail/{v.get('VulnerabilityID', '')}) "
                f"| `{v.get('PkgName', 'N/A')}` "
                f"| {v.get('InstalledVersion', 'N/A')} "
                f"| {v.get('FixedVersion', 'No fix available')} "
                f"| {v.get('_target', 'N/A')} |"
            )

    return "\n".join(lines)


if __name__ == '__main__':
    json_path = sys.argv[1] if len(sys.argv) > 1 else 'trivy-results.json'
    report = generate_report(json_path)
    print(report)

    # Also write to file
    with open('security-report.md', 'w') as f:
        f.write(report)
    print(f"\nReport written to security-report.md")
```

**security/scripts/create-security-issue.sh:**
```bash
#!/bin/bash
# Create GitHub Issue from Trivy critical findings
JSON_PATH=${1:-trivy-results.json}
SERVICE_TIER=${SERVICE_TIER:-unknown}

CRITICALS=$(python3 -c "
import json, sys
with open('$JSON_PATH') as f:
    data = json.load(f)
vulns = []
for r in data.get('Results', []):
    for v in (r.get('Vulnerabilities') or []):
        if v.get('Severity') == 'CRITICAL':
            vulns.append(f\"- {v['VulnerabilityID']}: {v['PkgName']} {v['InstalledVersion']} → fix: {v.get('FixedVersion', 'none')}\")
print('\n'.join(vulns[:10]))
")

if [ -z "$CRITICALS" ]; then
  echo "No critical findings, skipping issue creation."
  exit 0
fi

COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

gh issue create \
  --repo "$GITHUB_REPOSITORY" \
  --title "[SECURITY-CRITICAL] Vulnerabilities in ${SERVICE_TIER} service @ ${COMMIT_SHA}" \
  --body "## Critical Security Findings

**Service Tier**: ${SERVICE_TIER}
**Commit**: ${COMMIT_SHA}
**Scan Date**: $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Run**: https://github.com/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}

## Critical Vulnerabilities Found

${CRITICALS}

## Required Actions

- [ ] Review each CVE and assess exploitability in this context
- [ ] Update affected packages to fix versions
- [ ] If no fix available: document risk acceptance with security team sign-off
- [ ] Re-run scan to verify remediation
- [ ] Close this issue after verification

## SLA

**Critical**: Must be remediated within **24 hours** per security policy.
" \
  --label "security,critical,automated" 2>/dev/null || \
  echo "Note: Could not create issue (no permissions or gh not configured)"
```

**example-service/.github/workflows/ci.yml (Calling workflow):**
```yaml
name: CI

on: [push, pull_request]

jobs:
  security:
    uses: myorg/security-workflows/.github/workflows/security-scan.yml@main
    with:
      service_tier: payment
      image_name: myorg/payment-service:${{ github.sha }}
    secrets:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  deploy:
    needs: [security]
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploy after security passed"
```

**Bonus: Security Scorecard:**
```python
#!/usr/bin/env python3
"""Calculate security scorecard from Trivy JSON."""
import json, sys

def calculate_score(json_path):
    with open(json_path) as f:
        data = json.load(f)

    score = 100
    findings = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}

    for result in data.get('Results', []):
        for v in (result.get('Vulnerabilities') or []):
            sev = v.get('Severity', 'UNKNOWN')
            findings[sev] = findings.get(sev, 0) + 1

    score -= findings['CRITICAL'] * 20
    score -= findings['HIGH'] * 5
    score -= findings['MEDIUM'] * 2
    score -= findings['LOW'] * 0.5
    score = max(0, score)

    print(f"""
╔══════════════════════════════╗
║     SECURITY SCORECARD       ║
╠══════════════════════════════╣
║ CRITICAL: {findings['CRITICAL']:3d}  (-{findings['CRITICAL']*20:3d} pts)    ║
║ HIGH:     {findings['HIGH']:3d}  (-{findings['HIGH']*5:3d} pts)    ║
║ MEDIUM:   {findings['MEDIUM']:3d}  (-{findings['MEDIUM']*2:3d} pts)    ║
║ LOW:      {findings['LOW']:3d}  (-{int(findings['LOW']*0.5):3d} pts)    ║
╠══════════════════════════════╣
║ SCORE:    {score:3.0f}/100               ║
╚══════════════════════════════╝
""")

    if score < 70:
        print(f"FAIL: Score {score:.0f} < 70 threshold")
        sys.exit(1)
    elif score < 85:
        print(f"WARN: Score {score:.0f} — improvement needed")
    else:
        print(f"PASS: Score {score:.0f} — good security posture")

if __name__ == '__main__':
    calculate_score(sys.argv[1] if len(sys.argv) > 1 else 'trivy-results.json')
```

</details>

