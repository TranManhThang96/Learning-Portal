# Day 45: Document — DevSecOps Cheat Sheet & Reference

> Quick reference cho SAST, DAST, SCA, Secret Scanning, Container Scanning

---

## 1. So sánh các loại Security Scanning

| Tiêu chí | SAST | DAST | SCA | Secret Scanning | Container Scanning |
|----------|------|------|-----|-----------------|-------------------|
| **Cần app chạy?** | Không | Có | Không | Không | Không (image) |
| **Phân tích gì?** | Source code / bytecode | HTTP requests/responses | Dependency manifests | Git commits & files | Image layers |
| **Tìm được gì?** | SQL injection, XSS, hardcoded secrets, insecure functions | Auth bypass, runtime injection, business logic | Known CVEs trong libraries | Leaked API keys, tokens, passwords | OS & app CVEs trong base image |
| **Không tìm được** | Runtime bugs, config issues | Code-level issues, untested paths | Zero-days, custom code issues | Logic bugs | Code vulnerabilities |
| **False positive rate** | Cao | Thấp | Thấp-Vừa | Vừa | Thấp |
| **Khi chạy trong CI** | Pre-commit, every PR | Staging (sau merge) | Every PR (after install) | Pre-commit, every PR | After docker build |
| **Tốc độ** | Nhanh (1-5 min) | Chậm (15-45 min) | Nhanh (30s-2 min) | Nhanh (30s-2 min) | Trung bình (1-3 min) |
| **Giai đoạn pipeline** | Code → Build | Deploy → Test | Build | Code → Build | Build → Push |

---

## 2. So sánh Tool — Open-source vs Commercial

### SAST Tools

| Tool | Loại | Ngôn ngữ hỗ trợ | Điểm mạnh | Điểm yếu | Giá |
|------|------|-----------------|-----------|-----------|-----|
| **Semgrep** | Open-source | 30+ languages | Nhanh, custom rules dễ, CI-friendly | False positives vừa | Free (OSS), \$40/dev/mo (Pro) |
| **SonarQube** | Open-source/Commercial | 30+ languages | Code quality + security, UI đẹp | Setup phức tạp, chậm hơn | Free (Community), \$150+/mo |
| **CodeQL** | Free (GitHub) | 10 languages | Data flow analysis, sâu | Chậm (10-30 min), chỉ GitHub | Free với GitHub Actions |
| **Checkmarx** | Commercial | 25+ languages | Enterprise features, compliance reports | Đắt, overkill cho teams nhỏ | \$50,000+/năm |
| **Veracode** | Commercial | 20+ languages | Managed service, rich integrations | Đắt, slow scan | \$20,000+/năm |
| **Bandit** | Open-source | Python only | Nhẹ, fast, Python-specific | Chỉ Python | Free |

**Recommendation theo team size**:
- Startup (< 10 devs): Semgrep free tier + Bandit (Python) hoặc ESLint security plugins
- Mid-size (10-100 devs): Semgrep Team hoặc SonarQube Community + CodeQL on GitHub
- Enterprise (100+ devs): SonarQube Enterprise hoặc Checkmarx + CodeQL

### SCA Tools

| Tool | Loại | Ecosystems | Điểm mạnh | Điểm yếu | Giá |
|------|------|------------|-----------|-----------|-----|
| **Trivy** | Open-source | npm, pip, go, maven, gem, cargo, composer | All-in-one (container+fs+IaC), nhanh | UI ít, chủ yếu CLI | Free |
| **Dependabot** | Free (GitHub) | npm, pip, go, maven, gem, nuget | Auto-creates fix PRs, zero setup | Chỉ GitHub, không block CI | Free |
| **Snyk** | Freemium | npm, pip, go, maven, docker | Fix PRs, IDE plugins, UI đẹp | Giới hạn free tier | Free (200/mo), \$52+/dev/mo |
| **OWASP Dependency-Check** | Open-source | Java, .NET, Python, JavaScript | Free, mature, NIST NVD | Chậm, false positives cao | Free |
| **Grype** | Open-source | Container images, filesystems | Anchore ecosystem, nhanh | Ít tính năng hơn Trivy | Free |

### Secret Scanning Tools

| Tool | Phương pháp | Scan git history? | Custom rules? | CI integration | Giá |
|------|------------|-----------------|--------------|----------------|-----|
| **GitLeaks** | Regex + Entropy | Có (full history) | Có (.gitleaks.toml) | GitHub Action, pre-commit | Free |
| **TruffleHog** | Entropy + Regex + Verified | Có (full history) | Có | CLI, GitHub Action | Free |
| **detect-secrets** | Detector plugins | Có (với baseline) | Có | pre-commit, CI | Free |
| **GitHub Secret Scanning** | Pattern matching | Có | Không (provider patterns) | Built-in GitHub | Free (public), GHAS (private) |
| **GitGuardian** | ML + Regex | Có | Có | GitHub App, CI | Free (25 devs), \$55+/dev/mo |

### Container Scanning Tools

| Tool | Databases | Image formats | IaC scan? | SBOM? | Giá |
|------|-----------|--------------|-----------|-------|-----|
| **Trivy** | NVD, OSV, GitHub Advisory | Docker, OCI | Có (Terraform, Helm) | Có (CycloneDX, SPDX) | Free |
| **Grype** | NVD, GitHub Advisory | Docker, OCI, SBOM | Không | Có (via Syft) | Free |
| **Clair** | NVD, vendor advisories | Docker | Không | Không | Free |
| **Snyk Container** | Snyk DB | Docker, OCI | Có | Có | Free (tier), paid |
| **AWS ECR Scanning** | NVD + Inspector | ECR images | Không | Không | \$0.09/image |
| **Aqua Security** | Aqua DB | Docker, OCI, Kubernetes | Có | Có | Enterprise pricing |

---

## 3. GitHub Actions Security Pipeline Template

### Template đầy đủ — Copy & Customize

```yaml
# .github/workflows/security.yml
# DevSecOps Pipeline Template — Day 45
# Customize: SET_SERVICE_TIER, SET_IMAGE_NAME

name: Security Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * 1'  # Weekly Monday 2AM UTC

permissions:
  contents: read
  security-events: write
  issues: write
  pull-requests: write

env:
  # ========= CUSTOMIZE THESE =========
  SERVICE_TIER: internal          # internal | customer | payment
  IMAGE_NAME: myapp               # Docker image name
  FAIL_ON_SEVERITY: CRITICAL      # CRITICAL | CRITICAL,HIGH | CRITICAL,HIGH,MEDIUM
  # ====================================

jobs:
  # ──────────────────────────────────────
  # STAGE 1: Fast parallel security checks
  # ──────────────────────────────────────

  secret-scan:
    name: "🔑 Secret Scanning"
    runs-on: ubuntu-latest
    steps:
      - name: Checkout (full history)
        uses: actions/checkout@v4
        with:
          fetch-depth: 0          # Required: scan full git history

      - name: Run GitLeaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  sast:
    name: "🔍 SAST (Semgrep)"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Cache Semgrep
        uses: actions/cache@v4
        with:
          path: ~/.semgrep
          key: semgrep-${{ hashFiles('.semgrepignore') }}-${{ github.run_id }}
          restore-keys: semgrep-

      - name: Run Semgrep
        run: |
          pip install semgrep --quiet
          semgrep \
            --config=auto \
            --json \
            --output=semgrep-results.json \
            --metrics=off \
            . || true

          python3 - << 'EOF'
          import json, sys
          with open('semgrep-results.json') as f:
              data = json.load(f)
          findings = data.get('results', [])
          errors = [r for r in findings
                    if r.get('extra', {}).get('severity') == 'ERROR']
          print(f"Total findings: {len(findings)}, Blocking (ERROR): {len(errors)}")
          for e in errors[:10]:
              path = e['path']
              line = e['start']['line']
              rule = e['check_id']
              msg = e['extra']['message'][:80]
              print(f"  [ERROR] {rule} at {path}:{line}")
              print(f"          {msg}")
          if errors:
              sys.exit(1)
          EOF

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: semgrep-results.json
          category: sast
        continue-on-error: true   # SARIF upload requires specific permissions

  sca:
    name: "📦 SCA (Trivy Filesystem)"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Cache Trivy DB
        uses: actions/cache@v4
        with:
          path: ~/.cache/trivy
          key: trivy-db-${{ github.run_id }}
          restore-keys: trivy-db-

      - name: Run Trivy SCA
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: fs
          scan-ref: .
          format: sarif
          output: trivy-sca.sarif
          severity: ${{ env.FAIL_ON_SEVERITY }}
          exit-code: '1'
          ignore-unfixed: true    # Don't fail if no fix version available
          trivyignore-file: .trivyignore   # Project-level suppress list

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: trivy-sca.sarif
          category: sca
        continue-on-error: true

  # ──────────────────────────────────────
  # STAGE 2: Build (after security checks)
  # ──────────────────────────────────────

  build:
    name: "🏗️ Build Docker Image"
    runs-on: ubuntu-latest
    needs: [secret-scan, sast, sca]   # All security checks must pass
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
      image-digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=sha-
            type=ref,event=branch
            type=ref,event=pr

      - name: Build image
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          outputs: type=docker,dest=/tmp/image.tar

      - name: Upload image artifact
        uses: actions/upload-artifact@v4
        with:
          name: docker-image
          path: /tmp/image.tar
          retention-days: 1

  # ──────────────────────────────────────
  # STAGE 3: Container scan (after build)
  # ──────────────────────────────────────

  container-scan:
    name: "🐳 Container Scan (Trivy Image)"
    runs-on: ubuntu-latest
    needs: [build]
    steps:
      - name: Download image
        uses: actions/download-artifact@v4
        with:
          name: docker-image
          path: /tmp

      - name: Load image
        run: docker load --input /tmp/image.tar

      - name: Cache Trivy DB
        uses: actions/cache@v4
        with:
          path: ~/.cache/trivy
          key: trivy-db-${{ github.run_id }}
          restore-keys: trivy-db-

      - name: Run Trivy container scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: image
          image-ref: ${{ needs.build.outputs.image-tag }}
          format: sarif
          output: trivy-image.sarif
          severity: ${{ env.FAIL_ON_SEVERITY }}
          exit-code: '1'
          ignore-unfixed: true

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: trivy-image.sarif
          category: container

  # ──────────────────────────────────────
  # STAGE 4: Summary (always runs)
  # ──────────────────────────────────────

  security-gate:
    name: "✅ Security Gate"
    runs-on: ubuntu-latest
    needs: [secret-scan, sast, sca, container-scan]
    if: always()
    steps:
      - name: Evaluate gate
        id: gate
        run: |
          RESULTS=(
            "secret-scan:${{ needs.secret-scan.result }}"
            "sast:${{ needs.sast.result }}"
            "sca:${{ needs.sca.result }}"
            "container-scan:${{ needs.container-scan.result }}"
          )

          echo "## 🔐 Security Gate Results" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Check | Result |" >> $GITHUB_STEP_SUMMARY
          echo "|-------|--------|" >> $GITHUB_STEP_SUMMARY

          FAILED=0
          for item in "${RESULTS[@]}"; do
            NAME="${item%%:*}"
            STATUS="${item##*:}"
            ICON="✅"
            [ "$STATUS" = "failure" ] && { ICON="❌"; FAILED=1; }
            [ "$STATUS" = "skipped" ] && ICON="⏭️"
            echo "| $NAME | $ICON $STATUS |" >> $GITHUB_STEP_SUMMARY
          done

          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Service Tier**: \`${{ env.SERVICE_TIER }}\`" >> $GITHUB_STEP_SUMMARY
          echo "**Policy**: Fail on \`${{ env.FAIL_ON_SEVERITY }}\`" >> $GITHUB_STEP_SUMMARY

          if [ $FAILED -eq 1 ]; then
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "> ❌ **Security gate FAILED.** Fix vulnerabilities before merging." >> $GITHUB_STEP_SUMMARY
            exit 1
          else
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "> ✅ **All security checks passed.** Safe to merge." >> $GITHUB_STEP_SUMMARY
          fi
```

---

## 4. CVE Severity Decision Framework

### Khi nào cần làm gì?

```
CVE được phát hiện
       │
       ▼
 CVSS Score?
       │
   ┌───┴────────────────────────────┐
   │                                │
  9.0+                           7.0-8.9
CRITICAL                          HIGH
   │                                │
   ▼                                ▼
Có exploit                    Có exploit
 public?                       public?
   │                                │
  Có → Fix trong 24h          Có → Fix trong 7 ngày
  Không → Fix trong 72h       Không → Fix trong 30 ngày
                (alert SRE)                         │
                                              Không → Next sprint
       │
    4.0-6.9                       0.1-3.9
    MEDIUM                          LOW
       │                              │
Fix trong 30 ngày              Fix khi convenient
Track trong backlog            hoặc next major version
```

### Quick Decision Table

| CVSS | Severity | Exploitable? | Action | SLA |
|------|----------|-------------|--------|-----|
| 9.0-10.0 | CRITICAL | Có | Fix ngay, alert security team, SRE on-call | 24 giờ |
| 9.0-10.0 | CRITICAL | Không | Fix trong sprint hiện tại | 72 giờ |
| 7.0-8.9 | HIGH | Có | Fix trong sprint hiện tại | 7 ngày |
| 7.0-8.9 | HIGH | Không | Fix trong sprint tiếp theo | 30 ngày |
| 4.0-6.9 | MEDIUM | Bất kỳ | Track trong backlog | 30-90 ngày |
| 0.1-3.9 | LOW | Bất kỳ | Fix khi convenient | Next quarter |
| N/A | N/A | N/A — no fix available | Document risk acceptance | Review quarterly |

### Exploitability Assessment (5 câu hỏi)

```
1. Attack Vector: Có thể tấn công qua NETWORK không?
   → Network = Nguy hiểm hơn Local

2. Authentication: Cần creds để exploit không?
   → None = Nguy hiểm hơn

3. Scope: Có ảnh hưởng ngoài component bị attack không?
   → Changed = Nguy hiểm hơn

4. Context: Package này có được expose ra internet không?
   → Có = Ưu tiên cao hơn

5. Fix availability: Có version fix không?
   → Không có fix → Accept risk với documentation
```

---

## 5. False Positive Triage Checklist

### Bước 1: Identify — Xác nhận đây có phải false positive?

```
□ Đọc finding description đầy đủ (không chỉ severity)
□ Mở file được flag, xem context xung quanh (±20 dòng)
□ Hỏi: Code này có thực sự chạy trong production không?
  □ Test-only code? → Likely false positive
  □ Dead code / commented out? → False positive
  □ Example code trong docs? → False positive
  □ Actually runs và receives untrusted input? → Real finding
□ Nếu SCA/Container: Check NVD entry cho CVE
  □ Affected version range bao gồm version đang dùng?
  □ Affected function/class có được gọi không?
  □ Fix version available chưa?
```

### Bước 2: Classify — Loại false positive gì?

| Loại | Mô tả | Xử lý |
|------|-------|-------|
| **Test code** | Secret/injection trong test files | Suppress với comment + reason |
| **Demo/Example** | Code ví dụ không chạy production | Suppress, move to non-scanned folder |
| **Known-safe pattern** | Tool không hiểu context | Suppress với justification |
| **Unfixable CVE** | Không có fix version | Accept risk, track quarterly |
| **Not-applicable CVE** | CVE ảnh hưởng feature không dùng | Suppress với justification |
| **Transitive dep** | CVE trong dep của dep, không trực tiếp exploitable | Assess impact, suppress nếu not-applicable |

### Bước 3: Suppress — Cách suppress đúng

```bash
# GitLeaks — inline comment
some_value = "test-fake-credential"  # gitleaks:allow

# GitLeaks — ignore file (cần peer review commit)
# .gitleaksignore
tests/fixtures/test_credentials.py:TEST_API_KEY:42
# Reviewed by: [name], Date: YYYY-MM-DD, Reason: test-only fixture

# Semgrep — inline comment
result = eval(user_expr)  # nosemgrep: dangerous-eval
# Or: nosemgrep: full-rule-id

# Semgrep — ignore file (.semgrepignore)
tests/
docs/examples/
legacy/  # noqa: all deprecated

# Trivy — .trivyignore
# Format: CVE-ID [expiration-date] [comment]
CVE-2023-12345 exp:2026-06-01 # Not applicable: we don't use the affected XML parsing feature
CVE-2021-99999              # No fix available, risk accepted by security team 2025-05-01
```

### Bước 4: Document — Audit trail quan trọng

```yaml
# security/suppressions.yaml — track tất cả suppressions
suppressions:
  - id: SPR-001
    finding_type: secret-scan
    tool: gitleaks
    file: tests/fixtures/db_config.py
    line: 15
    reason: "Test fixture with fake credentials, never deployed"
    reviewed_by: "thangtm"
    date: "2025-05-12"
    expiry: "2026-05-12"  # Re-review annually

  - id: SPR-002
    finding_type: sca
    tool: trivy
    cve: CVE-2023-12345
    package: "cryptography==38.0.0"
    reason: "Affected function parse_der() not used in our codebase"
    reviewed_by: "security-team"
    date: "2025-05-01"
    expiry: "2025-08-01"  # Quarterly review
```

### Escalation: Khi nào cần Security Team sign-off?

```
Có thể tự suppress (peer review đủ):
  ✓ Test/fixture file
  ✓ Clearly not-applicable CVE (unused feature)
  ✓ Low/Medium severity, documented reason

Cần Security Team sign-off:
  ✗ CRITICAL CVE suppression
  ✗ HIGH CVE với no fix available
  ✗ Secret scanning suppression trong non-test code
  ✗ Suppression expiry > 3 months
```

---

## 6. OWASP Top 10 Quick Reference (2021)

| # | Vulnerability | Detection | Prevention | Example |
|---|---------------|-----------|------------|---------|
| **A01** | Broken Access Control | DAST, code review | RBAC, deny-by-default | User sees other users' data |
| **A02** | Cryptographic Failures | SAST, manual review | TLS 1.3+, AES-256, no MD5 | Plain text passwords in DB |
| **A03** | Injection | SAST (Semgrep), DAST | Parameterized queries, input validation | SQL injection via URL param |
| **A04** | Insecure Design | Threat modeling, review | Security design patterns | Missing rate limiting on login |
| **A05** | Security Misconfiguration | Container scan, DAST | Secure defaults, config scan | Default creds, debug mode on |
| **A06** | Vulnerable Components | SCA (Trivy, Snyk) | Patch management, SCA pipeline | Log4Shell in Log4j |
| **A07** | Auth & Session Failures | DAST, code review | MFA, secure session mgmt | Weak JWT, no session invalidation |
| **A08** | Software Integrity Failures | SCA, signature verify | Code signing, SCA in CI | Malicious npm package |
| **A09** | Security Logging Failures | SAST, manual review | Structured logging, SIEM | No audit log for admin actions |
| **A10** | SSRF | SAST, DAST | URL allowlist, block private IPs | Fetching internal metadata service |

### Semgrep rule IDs cho OWASP Top 10

```bash
# A01 - Broken Access Control
semgrep --config=p/jwt
semgrep --config=p/insecure-transport

# A02 - Cryptographic Failures
semgrep --config=p/cryptography
semgrep --config=p/secrets

# A03 - Injection
semgrep --config=p/sql-injection
semgrep --config=p/command-injection
semgrep --config=p/xss

# A06 - Vulnerable Components
trivy fs --config auto .

# A10 - SSRF
semgrep --config=p/ssrf
```

---

## 7. Tool Installation Quick Reference

### Install tất cả tools (copy-paste ready)

```bash
# ========== TRIVY (SCA + Container) ==========
# macOS
brew install trivy

# Linux
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
  | sh -s -- -b /usr/local/bin

# Verify
trivy --version
trivy image --download-db-only  # Download CVE database

# ========== GITLEAKS (Secret Scanning) ==========
# macOS
brew install gitleaks

# Linux
curl -sSfL https://raw.githubusercontent.com/gitleaks/gitleaks/main/scripts/install.sh \
  | sh -s -- -b /usr/local/bin

# Verify
gitleaks version

# ========== SEMGREP (SAST) ==========
# All platforms
pip install semgrep
# or
brew install semgrep

# Verify
semgrep --version

# ========== PRE-COMMIT (Hook framework) ==========
pip install pre-commit
pre-commit install
pre-commit run --all-files  # Test run

# ========== TRUFFLEHOG (Alternative secret scanner) ==========
# macOS
brew install trufflehog

# Linux
curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh \
  | sh -s -- -b /usr/local/bin
```

### Quick Scan Commands

```bash
# === TRIVY ===
# Scan container image
trivy image nginx:latest

# Scan only CRITICAL in image
trivy image --severity CRITICAL nginx:latest

# Scan filesystem dependencies
trivy fs .

# Scan IaC configs
trivy config ./terraform/
trivy config ./helm/

# Generate SBOM
trivy image --format cyclonedx --output sbom.json myapp:latest

# JSON output
trivy image --format json --output results.json myapp:latest

# Ignore unfixed CVEs
trivy image --ignore-unfixed myapp:latest

# Fail build only on CRITICAL
trivy image --exit-code 1 --severity CRITICAL myapp:latest

# === GITLEAKS ===
# Scan full repo history
gitleaks detect --source . --verbose

# Scan only new commits (since main branch)
gitleaks detect --source . --log-opts="origin/main..HEAD"

# Generate JSON report
gitleaks detect --source . --report-format json --report-path report.json

# Scan specific branch
gitleaks detect --source . --log-opts="HEAD~10..HEAD"

# === SEMGREP ===
# Scan with auto config (detects language, applies relevant rules)
semgrep --config=auto .

# Scan specific ruleset
semgrep --config=p/security-audit .
semgrep --config=p/python .
semgrep --config=p/owasp-top-ten .

# Fail on any ERROR finding
semgrep --config=auto --error .

# JSON output
semgrep --config=auto --json --output results.json .

# Only scan changed files (PR mode)
git diff --name-only origin/main..HEAD | xargs semgrep --config=auto

# Test custom rule
semgrep --config=my-rule.yaml --test tests/
```

---

## 8. .trivyignore Template

```
# .trivyignore
# Format: CVE-ID [optional-expiry-date]
#
# ================================================================
# INSTRUCTIONS:
# 1. Never suppress CRITICAL without security team sign-off
# 2. Always add comment with reason and reviewer
# 3. Add expiry date for time-bounded suppressions
# 4. Review expired suppressions quarterly
# ================================================================

# Example entries:

# Not applicable: we use rustls, not openssl on this service
# Reviewed: security-team, 2025-05-01, expiry: 2025-08-01
CVE-2023-0286 exp:2025-08-01

# No fix available yet, low exploitability in our context
# Reviewed: thangtm (peer-reviewed by @colleague), 2025-05-12
CVE-2024-9999

# Transitive dependency (lib-x → lib-y), lib-y feature not used
CVE-2023-12345
```

---

## 9. .pre-commit-config.yaml Template

```yaml
# .pre-commit-config.yaml
# Run: pre-commit install && pre-commit run --all-files

repos:
  # ──────────────────────────────
  # Secret Scanning (fast, always)
  # ──────────────────────────────
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
        name: Detect secrets with GitLeaks

  # ──────────────────────────────
  # SAST — Python
  # ──────────────────────────────
  - repo: https://github.com/PyCQA/bandit
    rev: '1.7.8'
    hooks:
      - id: bandit
        args: ['-ll', '--recursive']  # -ll = medium+ severity only
        files: '\.py$'
        exclude: tests/

  # ──────────────────────────────
  # SAST — Semgrep (changed files only)
  # ──────────────────────────────
  - repo: https://github.com/returntocorp/semgrep
    rev: '1.45.0'
    hooks:
      - id: semgrep
        args: ['--config=auto', '--error', '--skip-unknown-extensions']

  # ──────────────────────────────
  # General code hygiene
  # ──────────────────────────────
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-merge-conflict
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: detect-private-key    # Simple private key detection
```

---

## 10. Security Scanning Policy Matrix

### Policy Gate theo Service Tier

| Service Tier | Ví dụ | Secret Scan | SAST | SCA | Container Scan | DAST |
|-------------|-------|-------------|------|-----|----------------|------|
| **Payment** | Billing service, payment processor | Fail (any secret) | Fail (ERROR + WARNING) | Fail (CRITICAL + HIGH + MEDIUM) | Fail (CRITICAL + HIGH) | Weekly + pre-release |
| **Customer-facing** | User API, auth service, public website | Fail (any secret) | Fail (ERROR) | Fail (CRITICAL + HIGH) | Fail (CRITICAL + HIGH) | Monthly |
| **Internal** | Admin tools, internal dashboards | Fail (any secret) | Fail (ERROR) | Fail (CRITICAL) | Fail (CRITICAL) | Quarterly |
| **Dev-only tools** | CI scripts, internal tooling | Warn | Warn | Warn | Warn | None |

### Approval Matrix cho Suppressions

| Severity | Suppression Reviewer | Max Duration | Re-review |
|----------|---------------------|-------------|-----------|
| CRITICAL | Security Team lead sign-off | 30 ngày | Monthly |
| HIGH | Security team + Engineering manager | 90 ngày | Quarterly |
| MEDIUM | Tech lead peer review | 180 ngày | Semi-annual |
| LOW | Developer self-review | No expiry | Annual |
| Secret | Security Team — always required | 30 ngày | Monthly |

---

## 11. Shift-left Security Maturity Model

```
Level 1 — Reactive (Beginner)
├── Security scanning: None / manual
├── When vulnerabilities found: In production or after pentest
├── Fix timeline: "When we have time"
└── Team sentiment: "Security is someone else's job"

Level 2 — Aware (Developing)
├── Security scanning: Basic (one tool, runs in CI)
├── When vulnerabilities found: After PR merge
├── Fix timeline: Next sprint
└── Team sentiment: "Security is important but slows us down"

Level 3 — Integrated (Standard)
├── Security scanning: SAST + SCA + Secret scan in CI
├── When vulnerabilities found: During PR review
├── Fix timeline: Same sprint (CRITICAL: 24h)
└── Team sentiment: "Security is part of our definition of done"

Level 4 — Automated (Advanced)
├── Security scanning: All types, pre-commit + CI + scheduled
├── When vulnerabilities found: Before commit (local) + PR gate
├── Fix timeline: SLA enforced, tracked in metrics
└── Team sentiment: "Security is a feature, not a task"

Level 5 — Proactive (Leading)
├── Security scanning: Threat modeling, chaos security, red teaming
├── When vulnerabilities found: In design phase
├── Fix timeline: Not introduced in the first place
└── Team sentiment: "Security is everyone's responsibility, by design"
```

---

## 12. Tổng kết: Recommended Tool Stack

### Miễn phí, Cloud-agnostic, Production-ready

```
┌─────────────────────────────────────────────────┐
│           RECOMMENDED OPEN-SOURCE STACK         │
├─────────────────────────────────────────────────┤
│ Secret Scanning:    GitLeaks                    │
│ SAST:               Semgrep (auto config)       │
│ SCA:                Trivy (filesystem mode)     │
│ Container Scan:     Trivy (image mode)          │
│ IaC Scan:           Trivy (config mode)         │
│ Pre-commit:         pre-commit framework        │
│ DAST:               OWASP ZAP (scheduled)       │
│ Dependency Update:  Dependabot (GitHub) / Renovate│
├─────────────────────────────────────────────────┤
│ Total cost: $0/month                            │
│ Setup time: ~2 hours                            │
│ Coverage:   ~80% of common vulnerabilities      │
└─────────────────────────────────────────────────┘

When to add commercial tools:
├── Snyk:       When team wants auto-fix PRs + developer UX
├── SonarQube:  When code quality metrics & history needed
├── GitGuardian: When org needs centralized secret management
└── Checkmarx:  When compliance requires certified SAST tool
```

