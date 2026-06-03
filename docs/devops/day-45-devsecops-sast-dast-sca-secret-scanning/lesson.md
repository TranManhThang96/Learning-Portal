# Day 45: DevSecOps — SAST, DAST, SCA, Secret Scanning

> **Phase 7 — Security, Cost, DR & Advanced Production**
> Estimated time: 2 hours | Difficulty: Advanced

---

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** sự khác biệt giữa SAST, DAST, SCA, Secret Scanning và Container Scanning — và biết khi nào dùng cái nào.
2. **Tích hợp được** Semgrep (SAST), Trivy (SCA + Container), và GitLeaks (Secret Scanning) vào GitHub Actions pipeline.
3. **Thiết kế được** policy gates: critical vulnerability → fail build, medium → warn.
4. **Xử lý được** false positives theo quy trình triage có cấu trúc — không bỏ qua, không block team.
5. **Áp dụng ngay** shift-left security vào project hiện tại trong vòng 30 phút.

---

## 2. Bối cảnh & Động lực

### Shift-left security là gì và tại sao bạn nên quan tâm?

Ngày xưa (waterfall era): Dev code → QA test → Security audit → Deploy. Security là bước cuối cùng, xảy ra khi sản phẩm đã "xong". Kết quả: một lỗ hổng tìm ra ở Production mất \$10,000–\$1,000,000 để fix (IBM System Sciences Institute). Tìm ra khi dev đang code? Dưới \$100.

**Shift-left** = dịch chuyển security sang trái trong timeline, tức là sớm hơn trong vòng đời phát triển:

```
Waterfall (shift-right):
[Code] → [Build] → [Test] → [Stage] → [Prod] → [Security Audit]
                                                       ↑ Quá muộn!

Shift-left (DevSecOps):
[Code] → [Build] → [Test] → [Stage] → [Prod]
  ↑          ↑        ↑
Secret    SAST     DAST
Scan      SCA
```

### Những vụ breaches đáng nhớ

| Năm | Vụ việc | Nguyên nhân | Thiệt hại |
|-----|---------|-------------|-----------|
| 2020 | SolarWinds | Malicious code trong supply chain | 18,000+ tổ chức bị ảnh hưởng |
| 2021 | Log4Shell | CVE trong thư viện Java phổ biến | ~\$6.9B toàn ngành |
| 2022 | Samsung GitHub Leak | Samsung developers push secret lên public repo | Source code bị đánh cắp |
| 2023 | CircleCI Breach | Secret trong environment bị exfiltrate | Customer secrets bị lộ |
| 2024 | PyPI Supply Chain | Typosquatting packages chứa malware | Hàng nghìn devs bị ảnh hưởng |

Điểm chung: tất cả đều **có thể phát hiện sớm** bằng automated scanning.

### Chi phí thực tế — "Rule of 10"

```
Cost to fix:
├── Dev time (SAST finds it):     $80  (30 min of dev time)
├── QA time (test finds it):      $240 (1.5 hours, QA + Dev)
├── Staging (pentest finds it):   $960 (half day, Security + Dev)
├── Production (incident):        $7,600+ (incident response, SRE, Dev, Management)
└── Post-breach (public):         $4,000,000+ (legal, PR, regulatory fines)
```

### Security không phải là gating — là feedback loop

Quan niệm sai: "Security team là gatekeeper, Dev phải xin phép."
Quan niệm đúng: "Security tool là linter cho security — giống ESLint, nhưng tìm lỗ hổng thay vì typo."

Mục tiêu không phải là chặn deploy. Mục tiêu là **đưa thông tin security đến tay dev sớm nhất có thể**.

---

## 3. Kiến thức nền tảng

### 3.1 SAST — Static Application Security Testing

**Analogy**: Giống như ESLint/SonarQube cho code quality, nhưng tập trung vào security vulnerabilities.

- **Cách hoạt động**: Phân tích source code hoặc bytecode mà **không cần chạy ứng dụng**.
- **Tìm được**: SQL injection patterns, hardcoded secrets, insecure function calls, XSS vectors, path traversal, insecure deserialization.
- **Không tìm được**: Runtime logic bugs, configuration issues, third-party vulnerabilities.

```
Source Code → Parser → AST (Abstract Syntax Tree) → Rule Matching → Findings
               ↓
        [SAST analyzes structure, not behavior]
```

**Timing**: Chạy trong pre-commit hoặc CI khi code được push.

**Ví dụ finding**:
```python
# SAST sẽ flag dòng này:
query = "SELECT * FROM users WHERE id = " + user_input  # SQL Injection!

# vs. safe version:
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_input,))
```

### 3.2 DAST — Dynamic Application Security Testing

**Analogy**: Giống như load testing, nhưng thay vì test performance, nó tấn công ứng dụng đang chạy để tìm lỗ hổng.

- **Cách hoạt động**: Gửi malicious requests đến **ứng dụng đang chạy** và phân tích responses.
- **Tìm được**: Auth bypass, business logic flaws, runtime injection, misconfigured headers, exposed admin panels.
- **Không tìm được**: Code-level issues, issues trong code path không được test.

```
HTTP Requests → Running App → Analyze Responses → Report Vulnerabilities
    ↑               ↑
 Fuzzing        Real runtime
 Crawling       behavior
```

**Timing**: Chạy trong staging environment (cần app đang chạy).

### 3.3 SCA — Software Composition Analysis

**Analogy**: Giống như `npm audit` hoặc `pip check` nhưng mạnh hơn — kiểm tra **tất cả dependencies** của bạn (và dependencies của dependencies) theo CVE database.

- **Cách hoạt động**: Đọc `package.json`, `requirements.txt`, `go.sum`, v.v. → So sánh với NVD/OSV CVE database.
- **Tìm được**: Known vulnerabilities trong open-source dependencies, license violations, outdated packages.
- **Không tìm được**: Zero-day vulnerabilities, custom code issues.

```
package-lock.json → Parse Dependency Tree → Match against CVE DB → Report
    ↓                                              ↓
requirements.txt                          CVSS Score, Severity
    ↓                                              ↓
go.sum                                    Fix version available?
```

**Timing**: Chạy ngay sau install dependencies trong CI.

### 3.4 Secret Scanning

**Analogy**: Giống như `grep` trên steroids — tìm API keys, passwords, tokens bị commit vào code.

- **Cách hoạt động**: Scan git history và code files bằng regex patterns cho known secret formats.
- **Tìm được**: AWS keys, GitHub tokens, Stripe keys, database passwords, private keys, JWT secrets.
- **Quan trọng**: Scan cả **git history** — secret đã xóa vẫn còn trong git log!

```
Git Commits → Extract Content → Regex/Entropy Analysis → Alert
     ↑
All history
(even deleted files!)
```

**Timing**: Pre-commit hook (local) + CI pipeline (defense in depth).

### 3.5 Container Scanning

**Analogy**: Giống SCA nhưng cho container images — kiểm tra base image và tất cả packages được install trong container.

- **Cách hoạt động**: Phân tích image layers, extract package list → Match với CVE database.
- **Tìm được**: Vulnerable OS packages (openssl, glibc), application dependencies trong image, misconfigurations.

```
Docker Image → Extract Layers → List Packages → Match CVEs → Report
                    ↓
              OS packages (apt/yum)
              Language packages (pip/npm)
              Application configs
```

**Timing**: Sau khi build image trong CI, trước khi push to registry.

### 3.6 So sánh nhanh

| Loại | Cần app chạy? | Tìm gì | Giai đoạn |
|------|---------------|---------|-----------|
| SAST | Không | Code-level vulnerabilities | Pre-commit, CI |
| DAST | Có | Runtime vulnerabilities | Staging |
| SCA | Không | Vulnerable dependencies | CI (after install) |
| Secret Scanning | Không | Leaked credentials | Pre-commit, CI |
| Container Scanning | Không (image) | OS/app CVEs trong image | CI (after build) |

---

## 4. Deep Dive

### 4.1 SAST Tools

#### Semgrep — Open-source SAST leader

Semgrep dùng pattern-matching dựa trên syntax, không phải regex thuần. Điều này có nghĩa là:

```
Pattern: $X.execute("SELECT * FROM ... " + $Y)
Matches: db.execute("SELECT * FROM users WHERE id = " + userId)
         conn.execute("SELECT * FROM orders WHERE name = " + name)
```

**Tại sao Semgrep tốt hơn regex**:
- Hiểu syntax của ngôn ngữ (biết `execute` là method call)
- Có 2000+ rules có sẵn (semgrep.dev/r)
- Custom rules dễ viết, dễ test
- CI-friendly: chạy nhanh (~1 phút cho medium codebase)

**Rule example**:
```yaml
# .semgrep/rules/no-hardcoded-password.yaml
rules:
  - id: no-hardcoded-password
    patterns:
      - pattern: password = "..."
      - pattern-not: password = ""
    message: "Hardcoded password detected"
    languages: [python, javascript]
    severity: ERROR
```

#### SonarQube — Enterprise SAST

- Self-hosted hoặc SonarCloud (managed)
- Tốt hơn Semgrep về: code quality, security hotspots, historical trends
- Expensive cho enterprise edition (free community edition có hạn chế)
- Best for: Tổ chức đã có compliance requirements (PCI-DSS, SOC2)

#### CodeQL — GitHub native SAST

- Được tích hợp sẵn vào GitHub Advanced Security
- Phân tích data flow (track biến từ user input đến sink)
- Chậm hơn Semgrep (10-30 phút) nhưng sâu hơn
- Best for: Enterprise trên GitHub, cần depth over speed

### 4.2 DAST Tools

#### OWASP ZAP (Zed Attack Proxy)

```
┌─────────────────────┐
│    Your Browser     │
│   (or ZAP Spider)   │
└──────────┬──────────┘
           │ Proxy
           ▼
┌─────────────────────┐
│     OWASP ZAP       │
│  ┌───────────────┐  │
│  │ Active Scan   │  │  ← Attacks injections
│  │ Passive Scan  │  │  ← Analyzes responses
│  │ Fuzzer        │  │  ← Tests input variations
│  └───────────────┘  │
└──────────┬──────────┘
           │
           ▼
     Your App (must be running)
```

**ZAP Full Scan trong CI**:
```yaml
- name: DAST with OWASP ZAP
  uses: zaproxy/action-full-scan@v0.10.0
  with:
    target: 'https://staging.myapp.com'
    rules_file_name: '.zap/rules.tsv'
    cmd_options: '-a'
```

#### Nuclei — Template-based scanner

- Nhanh hơn ZAP, dùng YAML templates
- 6000+ templates có sẵn (CVEs, misconfigurations, exposures)
- Best for: Quick scanning, pentest automation

### 4.3 SCA Tools

#### Trivy — All-in-one scanner (recommended)

Trivy là tool "Swiss Army knife" — scan được tất cả:
- Container images
- Filesystems (dependencies)
- Git repositories
- Kubernetes configs
- IaC (Terraform, Helm)

```bash
# Scan container image
trivy image nginx:latest

# Scan filesystem (find deps vulnerabilities)
trivy fs .

# Scan IaC
trivy config ./terraform/

# Output formats
trivy image --format json --output results.json nginx:latest
trivy image --format sarif --output results.sarif nginx:latest
```

**Trivy severity levels**:
```
CRITICAL → Fix immediately, fail build
HIGH     → Fix this sprint, warn in CI
MEDIUM   → Fix next sprint, track in backlog
LOW      → Fix when convenient
UNKNOWN  → Review manually
```

#### Dependabot — GitHub native SCA

- Auto-creates PRs để update vulnerable dependencies
- Free cho public repos, GitHub Advanced Security cho private
- Best for: Automation, không cần setup pipeline

#### Snyk — Commercial SCA leader

- Developer-friendly UI, IDE integrations
- Fix suggestions (tự generate PR)
- Container, IaC scanning trong free tier (với limits)
- Best for: Team muốn polish UX, willing to pay

### 4.4 Secret Scanning Tools

#### GitLeaks

```bash
# Scan current repository (all history)
gitleaks detect --source . --verbose

# Scan specific branch
gitleaks detect --source . --log-opts="main..HEAD"

# Generate report
gitleaks detect --source . --report-format json --report-path gitleaks-report.json
```

**Custom rules** trong `.gitleaks.toml`:
```toml
[[rules]]
id = "my-api-key"
description = "MyCompany API Key"
regex = '''MYCO_[A-Z0-9]{32}'''
tags = ["key", "MyCompany"]
```

#### TruffleHog

- Detect secrets bằng entropy analysis + regex
- Scan local, remote repos, S3, Slack, GitHub
- Deep git history scanning

```bash
# Scan git repo
trufflehog git https://github.com/myorg/myrepo --only-verified

# Scan local
trufflehog filesystem /path/to/code
```

#### GitHub Secret Scanning (built-in)

- Tự động enable cho public repos
- Hỗ trợ 200+ provider patterns (AWS, GCP, Stripe, etc.)
- Push protection: block push nếu chứa known secret
- Best for: Teams đang dùng GitHub, zero setup

### 4.5 Pipeline Integration Architecture

```
Developer Workstation
├── pre-commit hooks (local)
│   ├── gitleaks (secret scan, fast)
│   └── semgrep (SAST, quick rules only)
│
GitHub Pull Request (CI)
├── Stage 1: Fast checks (parallel, ~2 min)
│   ├── GitLeaks full scan
│   ├── Semgrep SAST
│   └── SCA (Trivy fs / Dependabot)
│
├── Stage 2: Build (sequential)
│   └── docker build ...
│
├── Stage 3: Container scan (~1 min)
│   └── Trivy image scan
│
└── Stage 4: Policy gate
    ├── CRITICAL found → ❌ FAIL
    ├── HIGH found → ⚠️  WARN (non-blocking in dev, blocking in release)
    └── All clear → ✅ PASS

Staging Environment (scheduled, after merge)
└── DAST (OWASP ZAP full scan, ~15-30 min)
    └── Report → Security dashboard
```

### 4.6 Policy Gates trong CI/CD

Policy gate = điều kiện tự động quyết định pipeline có pass không.

**Trivy exit codes**:
```bash
# Exit 0 = no issues (hoặc no issues at specified severity)
# Exit 1 = vulnerabilities found

# Fail build only on CRITICAL
trivy image --exit-code 1 --severity CRITICAL myapp:latest

# Fail build on CRITICAL or HIGH
trivy image --exit-code 1 --severity CRITICAL,HIGH myapp:latest

# Ignore unfixed (chưa có fix version)
trivy image --exit-code 1 --severity CRITICAL --ignore-unfixed myapp:latest
```

**Semgrep exit codes**:
```bash
# Fail on any ERROR severity finding
semgrep --config=p/security-audit --error

# Non-blocking (chỉ warn)
semgrep --config=p/security-audit || true
```

---

## 5. Trade-offs & Best Practices

### 5.1 SAST vs DAST: Khi nào dùng cái nào?

| Tiêu chí | SAST | DAST |
|----------|------|------|
| Cần app chạy | Không | Có |
| Timing | Sớm (pre-commit, CI) | Muộn (staging) |
| False positive rate | Cao hơn | Thấp hơn |
| Coverage | Code paths | Actual runtime |
| Fix guidance | Thường rõ | Cần investigation |
| Best for | SQL injection, hardcoded secrets | Auth bypass, business logic |

**Recommendation**: SAST cho mọi commit, DAST weekly hoặc trước major release.

### 5.2 Open-source vs Commercial

| Tiêu chí | Open-source | Commercial |
|----------|-------------|------------|
| Chi phí | Miễn phí | \$5,000–\$100,000+/năm |
| Setup effort | Cao | Thấp |
| Customization | Cao | Vừa |
| Support | Community | SLA guaranteed |
| Compliance reporting | Manual | Automated |
| IDE integration | Plugin riêng | Native |
| Best for | Startups, tech-savvy teams | Enterprise, compliance-heavy |

**Recommendation cho most teams**:
```
Semgrep (free tier) + Trivy + GitLeaks = 80% coverage, $0/month
```

### 5.3 False Positive Management — Phần quan trọng nhất

False positive = tool báo vulnerability nhưng thực ra không phải vấn đề.

**Vấn đề của false positives**:
- Quá nhiều → developers mất niềm tin → bắt đầu ignore kết quả
- Hiện tượng "alert fatigue" (giống PagerDuty alert fatigue ở Day 43)
- Team bắt đầu dùng `|| true` để bypass → security theater

**Các loại false positive thường gặp**:

```python
# Case 1: Test code dùng hardcoded credentials
# Test file, không phải production secret
test_password = "test_password_123"  # GitLeaks sẽ flag

# Case 2: Example code trong documentation
# README.md
# Example: curl -H "Authorization: Bearer YOUR_TOKEN_HERE"

# Case 3: Known-safe pattern bị flag
# URL không phải secret
webhook_url = "https://hooks.example.com/services/T00000/B00000/XXXX"
```

**Cách xử lý**:

```bash
# GitLeaks: inline ignore
some_secret = "fake-secret-for-testing"  # gitleaks:allow

# GitLeaks: ignore file (.gitleaksignore)
echo "path/to/test/file.py:line:12" >> .gitleaksignore

# Semgrep: inline ignore
query = "SELECT" + user_input  # nosemgrep: sql-injection

# Semgrep: ignore file (.semgrepignore)
tests/

# Trivy: ignore CVEs (.trivyignore)
# Ignore old CVE that doesn't affect our usage
CVE-2021-12345
```

**Quy trình triage**:
```
Finding → Review → 3 câu hỏi:
  1. Có exploitable không? (Context: Prod hay Test code?)
  2. Có fix version không? (trivy --ignore-unfixed)
  3. Có violated security policy không? (Critical vs Low)
     ↓
  Exploitable + Critical → Fix ngay
  Not exploitable → Document + Suppress với justification
  Unfixable (no fix version) → Accept risk + Track
```

### 5.4 Security Gate Strategy theo Team Maturity

**Stage 1 — Beginner** (team mới bắt đầu):
- Chỉ fail build khi có CRITICAL secret leak
- Warning cho tất cả findings khác
- Mục tiêu: Build trust, không friction

**Stage 2 — Developing** (3-6 tháng):
- Fail build: CRITICAL vulnerabilities + secret leaks
- Warning: HIGH vulnerabilities
- Ignore: unfixed CVEs

**Stage 3 — Mature** (6-12 tháng):
- Fail build: CRITICAL + HIGH
- Track medium trong backlog
- Scheduled fix sprints

**Stage 4 — Advanced** (12+ tháng):
- Fail build: CRITICAL + HIGH + unapproved licenses
- SLA cho remediation (Critical: 24h, High: 7 days)
- Security metrics trong team KPIs

### 5.5 Anti-patterns cần tránh

**Security Theater**: Tool chạy nhưng không ai xem kết quả.
```yaml
# Anti-pattern:
- name: Security Scan
  run: semgrep . || true  # ← Luôn pass, vô nghĩa
```

**One-and-done**: Scan một lần rồi thôi, không update db.
```bash
# Anti-pattern:
trivy image --skip-db-update myapp:latest  # ← CVE DB cũ
```

**Block everything**: Fail build trên mọi low/medium → developers revolt.

**Scan only in CI**: Không có local scanning → feedback loop chậm.

---

## 6. Performance & Scalability

### 6.1 Impact lên CI/CD speed

| Tool | Typical scan time | Codebase size |
|------|------------------|---------------|
| GitLeaks | 30s - 2min | Medium repo |
| Semgrep | 1 - 5 min | Medium codebase |
| Trivy fs | 30s - 2min | With lock files |
| Trivy image | 1 - 3 min | Standard image |
| CodeQL | 10 - 30 min | Large codebase |
| OWASP ZAP | 15 - 45 min | Full crawl |

**Tổng CI time thêm vào**: ~5-10 phút cho SAST + SCA + Secret scan.

### 6.2 Parallel Scanning Strategy

```yaml
# Chạy song song để giảm total time
jobs:
  security-sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: semgrep --config=auto .

  security-secrets:
    runs-on: ubuntu-latest    # ← Job độc lập, chạy song song
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0      # Full history for secret scanning
      - run: gitleaks detect --source .

  security-sca:
    runs-on: ubuntu-latest    # ← Job độc lập, chạy song song
    steps:
      - uses: actions/checkout@v4
      - run: trivy fs --exit-code 1 --severity CRITICAL .

  build:
    needs: [security-sast, security-secrets, security-sca]  # ← Wait for all
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .

  security-container:
    needs: [build]            # ← Sau khi build xong
    runs-on: ubuntu-latest
    steps:
      - run: trivy image myapp:${{ github.sha }}
```

**Kết quả**: 3 jobs song song (~3 min) thay vì tuần tự (~9 min).

### 6.3 Caching Strategies

```yaml
# Cache Trivy vulnerability database
- name: Cache Trivy DB
  uses: actions/cache@v4
  with:
    path: ~/.cache/trivy
    key: trivy-db-${{ hashFiles('**/trivy-db-version') }}
    restore-keys: trivy-db-

# Cache Semgrep rules
- name: Cache Semgrep
  uses: actions/cache@v4
  with:
    path: ~/.semgrep
    key: semgrep-${{ hashFiles('.semgrepignore') }}
```

### 6.4 Incremental Scanning

```bash
# Chỉ scan files thay đổi trong PR (không scan toàn bộ)
# GitLeaks: chỉ scan commits mới
gitleaks detect --log-opts="origin/main..HEAD"

# Semgrep: chỉ scan changed files
git diff --name-only origin/main..HEAD | \
  xargs semgrep --config=auto

# Trivy: chỉ scan image layers thay đổi (tự động với layer caching)
```

### 6.5 Khi nào security scanning quá chậm?

**Dấu hiệu**: CI time tăng >15 phút vì security.

**Giải pháp**:
1. Dùng incremental scanning cho PRs
2. Full scan chỉ khi merge to main
3. DAST chạy scheduled (không block PR)
4. CodeQL chạy weekly, không mỗi commit

---

## 7. Security & Reliability Considerations

### 7.1 OWASP Top 10 (2021) — Quick Reference

| # | Vulnerability | SAST/DAST? | Ví dụ |
|---|---------------|-----------|-------|
| A01 | Broken Access Control | DAST | Missing auth check |
| A02 | Cryptographic Failures | SAST | MD5, hardcoded keys |
| A03 | Injection | SAST + DAST | SQL, LDAP, Command injection |
| A04 | Insecure Design | Code review | Missing rate limiting |
| A05 | Security Misconfiguration | DAST + Container scan | Default credentials |
| A06 | Vulnerable Components | SCA | Log4j in dependencies |
| A07 | Auth Failures | DAST | Brute force, weak tokens |
| A08 | Software Integrity Failures | SCA + Signing | Unsigned packages |
| A09 | Logging Failures | SAST | Missing audit logs |
| A10 | SSRF | SAST + DAST | Unvalidated URL fetch |

### 7.2 CVE Severity Classifications

**CVSS (Common Vulnerability Scoring System) v3.x**:
```
Score 0.0:       None     → No action needed
Score 0.1-3.9:   Low      → Fix when convenient
Score 4.0-6.9:   Medium   → Fix next sprint
Score 7.0-8.9:   High     → Fix this sprint
Score 9.0-10.0:  Critical → Fix immediately (today)
```

**CVSS Score components**:
- **Attack Vector**: Network/Adjacent/Local/Physical
- **Attack Complexity**: Low/High
- **Privileges Required**: None/Low/High
- **User Interaction**: None/Required
- **Scope**: Unchanged/Changed
- **Impact**: Confidentiality/Integrity/Availability (None/Low/High)

### 7.3 Vulnerability Management Lifecycle

```
Discover → Triage → Prioritize → Remediate → Verify → Close
   ↓           ↓          ↓            ↓           ↓
  Tools     Context    CVSS+Risk     Fix PR       Re-scan
 (Trivy,   (Is this    scoring    or Suppress    and mark
 Semgrep)  exploitable?)           with reason   resolved
```

**SLA by severity**:
```
Critical: 24 hours
High:     7 days
Medium:   30 days
Low:      Next quarter
```

### 7.4 Supply Chain Security

**Nguyên tắc**: Mọi dependency đều là potential attack vector.

**Defense in depth**:
```
1. Pin versions (không dùng latest tag)
   FROM node:18.19.1-alpine3.19   ← pinned, not node:18-alpine

2. Verify checksums
   pip install cryptography==41.0.7 --hash=sha256:...

3. SBOM (Software Bill of Materials)
   trivy image --format cyclonedx --output sbom.json myapp:latest

4. Sigstore/Cosign (sign images)
   cosign sign myapp:latest

5. Dependency review (GitHub)
   # Tự động block PRs thêm vulnerable dependencies
```

---

## 8. Hands-on Example

### 8.1 Setup — Vulnerable Sample App

Tạo một repo với các vulnerabilities có chủ đích để demo:

```bash
mkdir devsecops-demo && cd devsecops-demo
git init
```

**app.py** (Python Flask với intentional vulnerabilities):
```python
# app.py - INTENTIONALLY VULNERABLE for demo
from flask import Flask, request
import sqlite3
import subprocess

app = Flask(__name__)

# VULNERABILITY 1: Hardcoded secret (Secret Scanning will catch)
SECRET_API_KEY = "sk-prod-1234567890abcdef"
DB_PASSWORD = "admin123"

@app.route('/user')
def get_user():
    user_id = request.args.get('id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # VULNERABILITY 2: SQL Injection (SAST will catch)
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return str(cursor.fetchall())

@app.route('/ping')
def ping():
    host = request.args.get('host')
    # VULNERABILITY 3: Command Injection (SAST will catch)
    result = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True)
    return result.stdout.decode()

if __name__ == '__main__':
    app.run(debug=True)  # VULNERABILITY 4: Debug mode in production
```

**requirements.txt** (với vulnerable dependency):
```
flask==2.3.3
Werkzeug==2.3.7
cryptography==38.0.0  # OLD VERSION with known CVE
requests==2.28.0      # Has vulnerable transitive dep
```

**Dockerfile**:
```dockerfile
FROM python:3.9  # OLD BASE IMAGE with CVEs

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

### 8.2 GitHub Actions Security Pipeline

Tạo `.github/workflows/security.yml`:

```yaml
name: Security Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read
  security-events: write   # Required for SARIF upload
  actions: read

jobs:
  # ============================================================
  # JOB 1: Secret Scanning (chạy song song)
  # ============================================================
  secret-scan:
    name: Secret Scanning (GitLeaks)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout (full history)
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # IMPORTANT: scan all git history

      - name: Run GitLeaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        # Exits 1 if secrets found → fails job

  # ============================================================
  # JOB 2: SAST (chạy song song)
  # ============================================================
  sast:
    name: SAST (Semgrep)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/security-audit
            p/python
            p/owasp-top-ten
        env:
          SEMGREP_APP_TOKEN: ${{ secrets.SEMGREP_APP_TOKEN }}
        # Free without token, but with limits

      # Alternative: run without token
      - name: Run Semgrep (no token)
        run: |
          pip install semgrep
          semgrep --config=auto \
                  --error \
                  --json \
                  --output semgrep-results.json \
                  . || true
          # Parse and fail on critical/error findings
          python3 -c "
          import json, sys
          with open('semgrep-results.json') as f:
              data = json.load(f)
          critical = [r for r in data['results']
                      if r.get('extra', {}).get('severity') == 'ERROR']
          if critical:
              print(f'FAILED: {len(critical)} critical findings')
              sys.exit(1)
          print(f'PASSED: {len(data[\"results\"])} findings (none critical)')
          "

  # ============================================================
  # JOB 3: SCA — Dependency Scanning (chạy song song)
  # ============================================================
  sca:
    name: SCA (Trivy Filesystem)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Cache Trivy DB
        uses: actions/cache@v4
        with:
          path: ~/.cache/trivy
          key: trivy-db-${{ github.run_id }}
          restore-keys: trivy-db-

      - name: Run Trivy SCA
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-sca-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
          ignore-unfixed: true  # Don't fail on CVEs with no fix

      - name: Upload SARIF results
        uses: github/codeql-action/upload-sarif@v3
        if: always()  # Upload even if scan failed
        with:
          sarif_file: 'trivy-sca-results.sarif'
          category: 'sca'

  # ============================================================
  # JOB 4: BUILD (depends on security checks passing)
  # ============================================================
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: [secret-scan, sast, sca]  # Wait for all security checks
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: myapp
          tags: |
            type=sha,prefix=sha-

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          outputs: type=docker,dest=/tmp/myapp.tar

      - name: Upload image artifact
        uses: actions/upload-artifact@v4
        with:
          name: docker-image
          path: /tmp/myapp.tar

  # ============================================================
  # JOB 5: Container Scanning (depends on build)
  # ============================================================
  container-scan:
    name: Container Scanning (Trivy Image)
    runs-on: ubuntu-latest
    needs: [build]
    steps:
      - name: Download image artifact
        uses: actions/download-artifact@v4
        with:
          name: docker-image
          path: /tmp

      - name: Load Docker image
        run: docker load --input /tmp/myapp.tar

      - name: Cache Trivy DB
        uses: actions/cache@v4
        with:
          path: ~/.cache/trivy
          key: trivy-db-${{ github.run_id }}
          restore-keys: trivy-db-

      - name: Run Trivy container scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'image'
          image-ref: ${{ needs.build.outputs.image-tag }}
          format: 'sarif'
          output: 'trivy-image-results.sarif'
          severity: 'CRITICAL'    # ← Only fail on CRITICAL
          exit-code: '1'
          ignore-unfixed: true

      - name: Upload SARIF results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-image-results.sarif'
          category: 'container'

  # ============================================================
  # JOB 6: Security Summary Report
  # ============================================================
  security-summary:
    name: Security Gate Summary
    runs-on: ubuntu-latest
    needs: [secret-scan, sast, sca, container-scan]
    if: always()  # Run even if previous jobs failed
    steps:
      - name: Check security gate results
        run: |
          echo "## Security Gate Results" >> $GITHUB_STEP_SUMMARY
          echo "| Check | Status |" >> $GITHUB_STEP_SUMMARY
          echo "|-------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Secret Scanning | ${{ needs.secret-scan.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| SAST (Semgrep) | ${{ needs.sast.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| SCA (Dependencies) | ${{ needs.sca.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Container Scan | ${{ needs.container-scan.result }} |" >> $GITHUB_STEP_SUMMARY
```

### 8.3 Pre-commit Hook Setup (Local)

```bash
# Install pre-commit framework
pip install pre-commit

# Tạo .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  # Secret scanning (chạy mỗi commit)
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks

  # SAST quick scan (chỉ changed files)
  - repo: https://github.com/returntocorp/semgrep
    rev: '1.45.0'
    hooks:
      - id: semgrep
        args: ['--config=auto', '--error']
        # Chỉ chạy trên files thay đổi (tự động)

  # Basic Python security
  - repo: https://github.com/PyCQA/bandit
    rev: '1.7.5'
    hooks:
      - id: bandit
        args: ['-ll']  # Only report medium+ severity
EOF

# Install hooks
pre-commit install

# Test với intentional violation
echo 'password = "supersecret123"' > test_secret.py
git add test_secret.py
git commit -m "test"
# → Should be blocked by GitLeaks!

# Clean up test
rm test_secret.py
```

### 8.4 False Positive Triage — Ví dụ thực tế

```bash
# Scenario: GitLeaks flags a test file
# Finding: "secret" found in tests/test_auth.py:42

# Step 1: Review the finding
cat tests/test_auth.py | sed -n '40,44p'
# Output: test_password = "test_password_for_unit_tests"

# Step 2: Xác định đây là false positive (test code)
# Step 3: Suppress với justification

# Option A: Inline suppression
# test_password = "test_password_for_unit_tests"  # gitleaks:allow

# Option B: .gitleaksignore
echo "tests/test_auth.py:test_password:42" >> .gitleaksignore
git add .gitleaksignore
git commit -m "security: suppress false positive in test_auth.py

test_password is a test credential used only in unit tests.
It has no access to any real systems.
Reviewed by: [your-name]
Date: $(date +%Y-%m-%d)
"
```

### 8.5 Verify Results

```bash
# Chạy local để xem output trước khi push
# 1. Secret scan
docker run --rm -v $(pwd):/repo zricethezav/gitleaks detect --source /repo -v

# 2. SAST
python3 -m pip install semgrep
semgrep --config=auto . --json | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f'Findings: {len(d[\"results\"])}')
for r in d['results'][:5]:
    print(f'  [{r[\"extra\"][\"severity\"]}] {r[\"check_id\"]} at {r[\"path\"]}:{r[\"start\"][\"line\"]}')
"

# 3. SCA
trivy fs --severity HIGH,CRITICAL .

# 4. Container scan
docker build -t myapp:test .
trivy image --severity CRITICAL myapp:test

# Expected output từ vulnerable app:
# [CRITICAL] SQL Injection in app.py:18
# [CRITICAL] CVE-2023-XXXXX in cryptography 38.0.0
# [HIGH] Hardcoded credentials in app.py:8
# LEAK: Secret found: sk-prod-1234567890abcdef
```

### 8.6 Cleanup

```bash
# Remove demo app
rm -rf devsecops-demo/

# Remove installed tools (nếu không cần)
pip uninstall semgrep -y
docker rmi myapp:test

# Clear Trivy cache
trivy image --clear-cache
rm -rf ~/.cache/trivy
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Pitfall: Too Many False Positives

**Triệu chứng**: Developers bắt đầu thêm `|| true` hoặc `--exit-code 0` để bypass.

**Nguyên nhân**: Rule set quá rộng, không được tune cho codebase.

**Fix**:
```bash
# Thay vì dùng tất cả rules
semgrep --config=p/all .  # ← Quá nhiều noise

# Chọn ruleset phù hợp với tech stack
semgrep --config=p/python \
        --config=p/flask \
        --config=p/sql-injection \
        .

# Dùng .semgrepignore để exclude test files
cat > .semgrepignore << 'EOF'
tests/
*_test.py
test_*.py
*/fixtures/*
EOF
```

### 9.2 Pitfall: Scanning Only in CI

**Triệu chứng**: Developers nhận findings sau 10 phút (CI time), không phải ngay lúc code.

**Fix**: Pre-commit hooks (xem phần 8.3).

### 9.3 Pitfall: Outdated CVE Database

**Triệu chứng**: New critical CVEs (Log4Shell-level) được publish nhưng CI không phát hiện.

**Fix**:
```bash
# KHÔNG dùng cached db quá lâu
# Trivy tự update khi pull image mới
# Hoặc force update:
trivy image --download-db-only

# GitHub Actions: avoid caching db quá 24h
- name: Cache Trivy DB
  uses: actions/cache@v4
  with:
    path: ~/.cache/trivy
    key: trivy-db-${{ github.run_id }}-${{ hashFiles('**/Dockerfile') }}
    # Không dùng key cố định → rebuild cache mỗi run
```

### 9.4 Pitfall: Not Tracking Remediation

**Triệu chứng**: Same vulnerabilities tái xuất hiện. Team không biết gì đã được fix.

**Fix**: Tích hợp với issue tracker.

```yaml
# GitHub Actions: Create issue khi tìm thấy critical
- name: Create GitHub Issue for Critical Findings
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: `[SECURITY] Critical vulnerability in ${context.sha.substring(0,7)}`,
        body: `Security scan found critical issues.\nPR: #${context.payload.pull_request?.number}\nRun: ${context.runId}`,
        labels: ['security', 'critical', 'automated']
      })
```

### 9.5 Case Study: False Negative trong SCA

**Situation**: Team dùng Trivy SCA scan `requirements.txt`, không phát hiện vulnerable package.

**Root cause**: Package được install tại runtime (không có trong requirements.txt), hoặc dùng `--ignore-unfixed` nhưng fix version đã available.

**Lesson**:
```bash
# Scan cả direct và transitive dependencies
pip freeze > requirements-freeze.txt  # Tất cả installed packages
trivy fs --input requirements-freeze.txt .

# Không dùng --ignore-unfixed cho scheduled scans
# Dùng --ignore-unfixed chỉ cho PR gates
```

---

## 10. Kết nối với bài trước & bài sau

### Day 44 → Day 45: Từ Incident Response đến Prevention

Day 44 (Incident Response & Postmortem) kết thúc Phase 6. Bài học chính: **Respond fast, learn fast**.

Day 45 mở Phase 7 với triết lý ngược lại: **Prevent, not just respond**. Security scanning là công cụ chính để prevent incidents trước khi chúng xảy ra.

Kết nối thực tế:
- Postmortem từ Day 44 thường tìm ra root cause là vulnerable dependency hoặc leaked secret
- Day 45's security pipeline ngăn chặn những root cause đó ngay từ đầu

### Day 9 → Day 45: Container Scanning mở rộng

Day 9 bạn đã học `trivy image` cơ bản và non-root containers.

Day 45 mở rộng:
- Trivy trong pipeline (SARIF format, policy gates)
- Container scan là một phần của multi-layer security
- SBOM generation cho audit trails

### Day 21 → Day 45: Policy as Code

Day 21 (RBAC, Pod Security Standards) bạn đã học Kubernetes policies.

Day 45 mở rộng policy concept sang CI/CD:
- Policy gates trong GitHub Actions (exit codes)
- Security policies cho code, không chỉ infrastructure
- OPA/Conftest cho policy-as-code (preview Day 46+)

### Day 46: Service Mesh & Zero-trust Overview

Day 46 sẽ extend security từ code (Day 45) sang network/runtime:
- mTLS (mutual TLS) giữa services
- Zero-trust networking
- Service mesh security policies

Kết nối: Day 45 secure code/dependencies → Day 46 secure communication between services.

---

## 11. Tài liệu tham khảo

### Must-read
- [OWASP DevSecOps Guideline](https://owasp.org/www-project-devsecops-guideline/) — Framework tổng quan, bookmark ngay
- [Semgrep Tutorial](https://semgrep.dev/learn) — Interactive learning, 30 phút
- [Trivy Documentation](https://aquasecurity.github.io/trivy/) — Reference cho mọi scan type
- [GitLeaks README](https://github.com/gitleaks/gitleaks) — Config và custom rules

### Nice-to-have
- [OWASP Top 10 (2021)](https://owasp.org/Top10/) — Hiểu vulnerabilities bạn đang scan
- [CVSS Calculator](https://www.first.org/cvss/calculator/3.1) — Tính severity score thủ công
- [Semgrep Registry](https://semgrep.dev/r) — Tìm rules có sẵn cho mọi vulnerability
- [NIST National Vulnerability Database](https://nvd.nist.gov/) — Tra cứu CVE details

### Deep-dive
- [SLSA Framework](https://slsa.dev/) — Supply chain security levels (Google)
- [Sigstore/Cosign](https://docs.sigstore.dev/) — Image signing và verification
- [SBOM Guide (CISA)](https://www.cisa.gov/sbom) — Software Bill of Materials cho enterprise
- [Google Project Zero Blog](https://googleprojectzero.blogspot.com/) — Understand how attackers think
- [Snyk State of Open Source Security Report](https://snyk.io/reports/open-source-security/) — Annual industry data

### Tools nhanh (bookmark)
```bash
# Install all tools
brew install semgrep trivy gitleaks  # macOS
# or
pip install semgrep && \
  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh && \
  curl -sSfL https://raw.githubusercontent.com/gitleaks/gitleaks/main/scripts/install.sh | sh
```

