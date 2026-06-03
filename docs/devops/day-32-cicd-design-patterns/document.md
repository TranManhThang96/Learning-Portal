# Day 32: CI/CD Design Patterns — Document

## 1. Pipeline Stage Reference

### Stage Details

| Stage | Input | Output | Fail Condition | Recovery |
|-------|-------|--------|----------------|---------|
| **Lint** | Source code | Pass/fail report | Formatting/style violations | Fix code, re-run |
| **Unit Test** | Source code | Test results + coverage | Test failure or coverage < threshold | Fix test/code |
| **Integration Test** | Built artifact + deps | Test results | External dep failure or code bug | Check deps, fix code |
| **Build** | Source code | Binary/artifact | Compile error, missing dep | Fix code/deps |
| **Security Scan** | Built artifact/image | CVE report | CRITICAL/HIGH vulnerability | Update dep, suppress false positive |
| **Package** | Built artifact | Container image / archive | Docker build failure | Fix Dockerfile |
| **Deploy** | Packaged artifact | Running service | K8s apply failure, image pull error | Check manifests, RBAC, registry |
| **Verify** | Running service | Health/smoke test results | Endpoint unreachable, wrong response | Check logs, rollback |

### Stage Ordering Rules

```
Mandatory order:
1. Lint (fast, no deps)
2. Test (needs source, no build)
3. Build (needs source)
4. Scan (needs built artifact)
5. Package (needs built artifact)
6. Deploy (needs packaged artifact)
7. Verify (needs deployed service)

Can parallelize:
- Lint ║ Unit Test ║ Secret Scan
- Build → (Scan ║ Package) [after build]
- Integration Test ║ Performance Test [after deploy]
```

---

## 2. Quality Gate Checklist Templates

### Template: CI Quality Gates

```yaml
quality_gates:
  code_quality:
    lint:
      blocking: true
      tool: "golangci-lint / eslint / ruff"
      config: ".golangci.yml / .eslintrc / ruff.toml"
    
    formatting:
      blocking: true
      tool: "gofmt / prettier / black"
      auto_fix: true  # CI có thể auto-format trong PR
    
    complexity:
      blocking: false  # warning only
      threshold: "cyclomatic complexity < 15"
      tool: "gocyclo / eslint complexity rule"

  testing:
    unit_tests:
      blocking: true
      coverage_threshold:
        critical: 80%
        high: 70%
        default: 50%
      flaky_threshold: "0 flaky tests allowed"
    
    integration_tests:
      blocking: true  # for critical services
      timeout: "15 minutes"
      retry: 1  # retry once on failure
    
    e2e_tests:
      blocking: false  # warning, run nightly
      environment: "staging-like"

  security:
    vulnerability_scan:
      blocking_severity: ["CRITICAL"]  # block on CRITICAL
      warning_severity: ["HIGH"]       # warn on HIGH
      tool: "trivy / snyk / grype"
      ignore_file: ".trivyignore"
    
    secret_scan:
      blocking: true
      tool: "gitleaks / trufflehog"
      pre_commit: true  # also run as pre-commit hook
    
    license_check:
      blocking: true
      allowed: ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]
      tool: "license-checker / go-licenses"
    
    sast:
      blocking: false  # warning, high false positive rate
      tool: "semgrep / gosec / bandit"

  artifact:
    image_size:
      warning_threshold: "100MB"
      blocking_threshold: "500MB"
    
    image_tag:
      format: "git-sha"  # immutable
      no_latest: true     # never use :latest in prod
    
    sbom:
      required: true
      format: "spdx-json"
      tool: "syft / trivy"
```

### Template: CD Quality Gates

```yaml
deployment_gates:
  pre_deploy:
    approval:
      critical_services: "2 approvers required"
      high_services: "1 approver required"
      default: "auto-deploy"
    
    change_window:
      blocked_times: ["Friday 16:00 - Monday 08:00"]
      exceptions: "hotfix with incident ticket"
    
    canary_config:
      initial_weight: "5%"
      step: "10%"
      max_wait: "30 minutes per step"

  post_deploy:
    health_check:
      endpoint: "/health"
      expected_status: 200
      timeout: "30 seconds"
      retries: 3
    
    smoke_test:
      endpoints:
        - "GET /api/v1/status"
        - "GET /api/v1/health/deep"
      timeout: "60 seconds"
    
    metric_check:
      error_rate: "< 1% for 5 minutes"
      latency_p99: "< 2x baseline"
      cpu_usage: "< 80%"
    
    auto_rollback:
      trigger: "error_rate > 5% for 2 minutes"
      method: "argocd app rollback / helm rollback"
      notify: "slack #prod-alerts"
```

---

## 3. DORA Metrics Measurement Guide

### Data Sources

| Metric | Data Source | Calculation |
|--------|-----------|-------------|
| **Deployment Frequency** | CI/CD tool API (GitHub Actions, ArgoCD) | Count of successful production deploys / time period |
| **Lead Time** | Git (commit time) + CI/CD (deploy time) | Median(deploy_time - first_commit_time) for each change |
| **Change Failure Rate** | CI/CD + Incident tracker | Failed deploys / Total deploys (30-day window) |
| **MTTR** | Incident tracker (PagerDuty, OpsGenie) | Mean(resolved_time - detected_time) |

### DORA Performance Levels (tham khảo report gần đây)

| Metric | Elite | High | Medium | Low |
|--------|-------|------|--------|-----|
| Deploy Frequency | On-demand (multiple/day) | 1/day - 1/week | 1/week - 1/month | 1/month - 1/6months |
| Lead Time | < 1 hour | 1 day - 1 week | 1 week - 1 month | 1 month - 6 months |
| Change Failure Rate | < 5% | 5-10% | 10-15% | > 15% |
| MTTR | < 1 hour | < 1 day | < 1 week | > 1 week |

### Measurement Scripts

```bash
#!/bin/bash
# dora-metrics.sh - Calculate DORA metrics from Git + CI data

# 1. Deployment Frequency (last 30 days)
echo "=== Deployment Frequency ==="
DEPLOYS=$(git log --since="30 days ago" --oneline --grep="deploy\|release" | wc -l)
echo "Deploys in last 30 days: $DEPLOYS"
echo "Frequency: $(echo "scale=1; $DEPLOYS / 30" | bc) per day"

# 2. Lead Time (last 10 merges)
echo ""
echo "=== Lead Time (approx) ==="
git log --merges --format="%H %ci" -10 | while read hash date time tz; do
    # Time from first commit in branch to merge
    FIRST=$(git log --format="%ci" ${hash}^..${hash} | tail -1)
    echo "  Merge $hash: first commit $FIRST, merged $date $time"
done

# 3. Change Failure Rate
echo ""
echo "=== Change Failure Rate ==="
TOTAL_DEPLOYS=50  # from CI tool API
FAILED_DEPLOYS=3  # from incident tracker
echo "Total: $TOTAL_DEPLOYS, Failed: $FAILED_DEPLOYS"
echo "Rate: $(echo "scale=1; $FAILED_DEPLOYS * 100 / $TOTAL_DEPLOYS" | bc)%"

# 4. MTTR
echo ""
echo "=== MTTR ==="
echo "Requires data from incident management tool (PagerDuty/OpsGenie API)"
echo "Calculate: mean(resolved_at - created_at) for production incidents"
```

---

## 4. Pipeline Anti-patterns Reference

| # | Anti-pattern | Symptoms | Impact | Fix |
|---|-------------|----------|--------|-----|
| 1 | **No CI** | Bugs found in production | High change failure rate | Add basic lint + test pipeline |
| 2 | **Manual deploy** | Deploy takes hours, error-prone | Low deploy frequency | Automate deployment |
| 3 | **Long pipeline** | > 30 min CI, developers wait | Context switching, low velocity | Cache, parallelize, split |
| 4 | **No caching** | Fresh install every run | Slow builds, high cost | Cache deps, build layers |
| 5 | **Flaky tests** | Tests pass/fail randomly | Team ignores failures | Fix or quarantine flaky tests |
| 6 | **Build everything** | Monorepo builds all services | Waste, slow | Path filters, affected detection |
| 7 | **No quality gates** | Bad code reaches production | High change failure rate | Add gates progressively |
| 8 | **Too many gates** | Pipeline takes 1+ hour | Low deploy frequency | Prioritize, async non-critical |
| 9 | **Deploy Friday** | Weekend incidents | Poor MTTR, unhappy team | Deploy freeze or mature enough |
| 10 | **No rollback** | Stuck with bad deploy | Long MTTR | Automated rollback |
| 11 | **Snowflake envs** | Works on staging, fails prod | Unreliable testing | IaC, Docker, env parity |
| 12 | **Secret in code** | Credentials committed | Security breach | Vault, secret scanning |
| 13 | **No monitoring post-deploy** | Don't know if deploy is good | Silent failures | Post-deploy verify stage |
| 14 | **Big bang releases** | Deploy monthly, huge changesets | High risk, hard rollback | Small, frequent releases |
| 15 | **Feature branches > 3 days** | Merge conflicts, integration hell | Slow lead time | Trunk-based + feature flags |

---

## 5. Pipeline Templates

### Go Service Pipeline

```yaml
# .github/workflows/go-service.yaml
name: Go Service CI

on:
  push:
    branches: [main]
    paths: ['services/my-service/**', 'libs/**']
  pull_request:
    branches: [main]
    paths: ['services/my-service/**', 'libs/**']

env:
  SERVICE_NAME: my-service
  GO_VERSION: '1.22'

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ env.GO_VERSION }}
          cache: true
      - name: Lint
        uses: golangci/golangci-lint-action@v4
      - name: Test
        run: go test -v -race -coverprofile=coverage.out ./...
      - name: Coverage
        run: |
          COVERAGE=$(go tool cover -func=coverage.out | grep total | awk '{print $3}')
          echo "Coverage: $COVERAGE"

  build-and-push:
    needs: lint-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: registry/${{ env.SERVICE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  scan:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: aquasecurity/trivy-action@v0.36.0
        with:
          image-ref: registry/${{ env.SERVICE_NAME }}:${{ github.sha }}
          exit-code: 1
          severity: CRITICAL,HIGH
```

### Node.js Service Pipeline

```yaml
# .github/workflows/node-service.yaml
name: Node.js Service CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  NODE_VERSION: '20'

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run test -- --coverage
      - run: npm run build
```

### Python Service Pipeline

```yaml
# .github/workflows/python-service.yaml
name: Python Service CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest --cov=src --cov-report=term-missing
```

---

## 6. CI/CD Tool Quick Comparison

| Feature | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|---------|---------------|-----------|---------|----------|
| Pipeline as Code | YAML | YAML | Groovy (Jenkinsfile) | YAML |
| Hosting | Cloud + self-hosted | Cloud + self-hosted | Self-hosted (+ cloud) | Cloud + self-hosted |
| Free tier | 2000 min/month | 400 min/month | Free (self-hosted) | 6000 min/month |
| Marketplace | 20,000+ actions | Limited | 1800+ plugins | Orbs ecosystem |
| Container support | ✅ Native | ✅ Native | ✅ Plugin | ✅ Native |
| Matrix builds | ✅ | ✅ | ✅ (parallel) | ✅ |
| Caching | ✅ actions/cache | ✅ Built-in | ⚠️ Plugin | ✅ Built-in |
| Secrets | ✅ Encrypted | ✅ Variables | ⚠️ Credentials plugin | ✅ Contexts |
| OIDC | ✅ | ✅ | ⚠️ Plugin | ✅ |
| Monorepo | ✅ Path filters | ✅ rules:changes | ⚠️ Manual | ✅ Path filtering |
| Reusable workflows | ✅ | ✅ includes | ✅ Shared libraries | ✅ Orbs |
| Environment protection | ✅ | ✅ | ⚠️ Plugin | ✅ |
| Learning curve | Low | Low | High | Low |
| Vendor lock-in | Medium (GitHub) | Medium (GitLab) | Low (open source) | High |

---

## 7. Pipeline Performance Optimization Checklist

```
□ Dependencies cached (npm, go modules, pip, Docker layers)
□ Stages parallelized where possible (lint ║ test)
□ Path filters configured (monorepo: only build changed services)
□ Docker multi-stage build used (smaller images, faster push)
□ Docker layer caching enabled (buildx cache)
□ Test splitting enabled (parallel test execution)
□ Unnecessary steps removed (no redundant installs)
□ Runner size appropriate (larger runner = faster build)
□ Artifacts reused between jobs (don't rebuild)
□ Conditional stages (skip deploy on PR, skip perf test on docs change)
□ Timeout configured (prevent hanging jobs)
□ Pipeline duration tracked (alert on regression)
```

