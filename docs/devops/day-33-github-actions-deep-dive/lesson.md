# Day 33: GitHub Actions Deep Dive

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Hiểu sâu kiến trúc GitHub Actions**: workflow, job, step, runner — và cách chúng tương tác.
2. **Viết được pipeline hoàn chỉnh** build/test/scan/push Docker image cho microservice.
3. **Sử dụng các tính năng advanced**: matrix build, reusable workflow, environment protection, composite actions.
4. **Quản lý secrets an toàn** trong CI và hiểu OIDC authentication cho cloud services.
5. **Nhận diện security risks** trong GitHub Actions và cách phòng chống.

---

## 2. Bối cảnh & Động lực

### Tại sao GitHub Actions?

GitHub Actions là CI/CD platform phổ biến trong modern software delivery:
- **Tích hợp native** với GitHub — không cần external CI server.
- **Marketplace** với 20,000+ actions có sẵn.
- **Free tier** rộng rãi (2000 min/month cho public repos unlimited).
- **YAML-based** — Pipeline as Code, version controlled.
- **Matrix builds** — test across multiple OS/versions dễ dàng.

### Liên hệ với bài trước

Day 32 đã thiết kế pipeline stages và quality gates. Hôm nay implement thật trên GitHub Actions — biến design thành working pipeline.

---

## 3. Kiến thức nền tảng

### 3.1 GitHub Actions Architecture

```
GitHub Actions Hierarchy:

Repository
└── .github/workflows/
    └── ci.yaml (Workflow)
        ├── Job 1: lint-and-test
        │   ├── Step 1: Checkout code
        │   ├── Step 2: Setup Go
        │   ├── Step 3: Run lint
        │   └── Step 4: Run tests
        ├── Job 2: build (needs: lint-and-test)
        │   ├── Step 1: Checkout code
        │   ├── Step 2: Build Docker image
        │   └── Step 3: Push to registry
        └── Job 3: scan (needs: build)
            └── Step 1: Trivy scan
```

**Concepts chính**:

| Concept | Giải thích | Analogy |
|---------|-----------|---------|
| **Workflow** | File YAML define automation, triggered by events | Lệnh make all |
| **Event** | Trigger workflow (push, PR, schedule, manual) | Git hook |
| **Job** | Tập hợp steps chạy trên cùng runner | Function/task |
| **Step** | Một action hoặc shell command | Một lệnh |
| **Action** | Reusable unit (marketplace hoặc custom) | Library/package |
| **Runner** | Server chạy jobs (GitHub-hosted hoặc self-hosted) | Build server |

### 3.2 Event Types

```yaml
on:
  # Code events
  push:
    branches: [main, 'release/**']
    paths: ['src/**', 'Dockerfile']      # Path filter
    tags: ['v*']                          # Tag trigger
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]
  
  # Schedule
  schedule:
    - cron: '0 2 * * 1-5'               # Weekdays at 2am UTC
  
  # Manual
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [dev, staging, prod]
  
  # Other workflow
  workflow_call:                          # Reusable workflow
    inputs:
      service_name:
        type: string
        required: true
```

### 3.3 Runner Types

| Type | Specs | Cost | Khi nào dùng |
|------|-------|------|-------------|
| **ubuntu-latest** | Standard Linux runner | $0.006/min | Default cho hầu hết jobs |
| **ubuntu-24.04** | Pinned OS image | $0.006/min | Reproducibility |
| **macos-latest** | Standard macOS runner | $0.062/min | iOS/macOS builds |
| **windows-latest** | Standard Windows runner | $0.010/min | Windows-specific builds |
| **Self-hosted** | Custom specs | Your infra cost | Security, performance, special hardware |
| **Larger runners** | 4-96 core tiers | $0.012-0.552/min tùy OS/size | Heavy builds |

Giá runner thay đổi theo thời gian và theo billing plan. Khi lập budget thật, luôn lấy rate mới nhất từ GitHub Actions runner pricing thay vì copy số trong lesson.

---

## 4. Deep Dive

### 4.1 Job Dependencies & Parallelism

```mermaid
graph LR
    subgraph "Parallel"
        L[lint]
        T[test]
        S[secret-scan]
    end
    
    L --> B[build]
    T --> B
    S --> B
    
    B --> SC[security-scan]
    B --> P[push-image]
    
    SC --> D[deploy-staging]
    P --> D
    
    D --> V[verify]
    V --> DP[deploy-prod]
```

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

  test:
    runs-on: ubuntu-latest
    # Không có needs → chạy parallel với lint
    steps: [...]

  build:
    needs: [lint, test]  # Chờ cả 2 xong
    runs-on: ubuntu-latest
    steps: [...]

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging  # Environment protection
    steps: [...]

  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production  # Requires approval
    steps: [...]
```

### 4.2 Matrix Build

```yaml
jobs:
  test:
    strategy:
      fail-fast: false  # Không cancel jobs khác khi 1 fail
      matrix:
        go-version: ['1.21', '1.22']
        os: [ubuntu-latest, macos-latest]
        exclude:
          - go-version: '1.21'
            os: macos-latest  # Skip Go 1.21 on macOS
        include:
          - go-version: '1.22'
            os: ubuntu-latest
            coverage: true  # Extra variable cho combo này
    
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go-version }}
      - run: go test ./...
      - if: matrix.coverage
        run: go test -coverprofile=coverage.out ./...
```

### 4.3 Caching

```yaml
# Go modules cache
- uses: actions/setup-go@v5
  with:
    go-version: '1.22'
    cache: true  # Auto-cache Go modules

# Manual cache (npm example)
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-

# Docker layer cache
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### 4.4 Reusable Workflows

```yaml
# .github/workflows/reusable-build.yaml (CALLED workflow)
name: Reusable Build

on:
  workflow_call:
    inputs:
      service_name:
        required: true
        type: string
      go_version:
        required: false
        type: string
        default: '1.22'
    secrets:
      REGISTRY_TOKEN:
        required: true
    outputs:
      image_tag:
        description: Built image tag
        value: ${{ jobs.build.outputs.tag }}

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ inputs.go_version }}
          cache: true
      - run: go test ./services/${{ inputs.service_name }}/...
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: registry.example.com/${{ inputs.service_name }}
      - uses: docker/build-push-action@v5
        with:
          context: ./services/${{ inputs.service_name }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}

---
# .github/workflows/ci-payment.yaml (CALLER workflow)
name: Payment Service CI

on:
  push:
    paths: ['services/payment/**']

jobs:
  build:
    uses: ./.github/workflows/reusable-build.yaml
    with:
      service_name: payment
    secrets:
      REGISTRY_TOKEN: ${{ secrets.REGISTRY_TOKEN }}
```

### 4.5 Environment Protection Rules

```yaml
# Trong GitHub Settings → Environments:
# - staging: no protection
# - production: required reviewers (2), wait timer (5 min), branch policy (main only)

jobs:
  deploy-staging:
    environment: staging
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying to staging..."

  deploy-prod:
    needs: deploy-staging
    environment: production  # Triggers approval flow
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying to production..."
```

### 4.6 OIDC Authentication (không cần long-lived secrets)

```yaml
jobs:
  deploy:
    permissions:
      id-token: write   # Required for OIDC
      contents: read
    
    steps:
      # AWS
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions
          aws-region: ap-southeast-1
      
      # GCP
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: projects/123/locations/global/workloadIdentityPools/github/providers/github
          service_account: github-actions@project.iam.gserviceaccount.com
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 GitHub-hosted vs Self-hosted Runners

| Tiêu chí | GitHub-hosted | Self-hosted |
|----------|--------------|-------------|
| **Setup** | Zero setup | Cần provisioning + maintenance |
| **Cost** | $0.008/min, free cho public repos | Infra cost + maintenance |
| **Security** | Ephemeral, clean environment | Persistent, risk of contamination |
| **Performance** | Standard (4 CPU) | Custom (choose your hardware) |
| **Network** | Public internet | Access internal resources |
| **Availability** | 99.9% SLA | Your responsibility |

**Recommendation**: Bắt đầu GitHub-hosted, chuyển self-hosted khi cần access internal network hoặc performance.

### 5.2 Best Practices

1. **Pin action versions bằng full commit SHA** (không chỉ dùng floating tag như `@v6` hoặc branch như `@main`):
   ```yaml
   # ❌ Risky
   - uses: actions/checkout@v6
   # ✅ Secure
   - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # example full SHA; verify current release before use
   ```

2. **Least privilege permissions**:
   ```yaml
   permissions:
     contents: read    # Chỉ read, không write
     packages: write   # Chỉ cho push image
   ```

3. **Dùng OIDC thay vì long-lived secrets** cho cloud authentication.

4. **Reusable workflows cho DRY** — không copy-paste pipeline giữa services.

5. **Fail fast nhưng thông minh**: `fail-fast: false` cho matrix builds (biết tất cả failures).

6. **Timeout cho mỗi job**: Tránh jobs chạy vô hạn.
   ```yaml
   jobs:
     build:
       timeout-minutes: 15
   ```

7. **Concurrency control**: Tránh deploy cùng lúc.
   ```yaml
   concurrency:
     group: deploy-${{ github.ref }}
     cancel-in-progress: true  # Cancel runs cũ khi có run mới
   ```

### 5.3 Anti-patterns

| Anti-pattern | Risk | Fix |
|-------------|------|-----|
| `actions/checkout@main` | Malicious code injection | Pin SHA |
| `secrets.GITHUB_TOKEN` với write-all | Over-privileged | Least privilege permissions |
| Chạy CI cho fork PRs không review | Code injection qua PR | `pull_request_target` + approval |
| Log secrets | Credential leak | Always mask, never echo |
| Không set timeout | Stuck jobs burn credits | `timeout-minutes` |
| Rebuild mọi thứ mỗi commit | Slow, expensive | Caching + path filters |

---

## 6. Performance & Scalability ⭐

### 6.1 Optimization Impact

| Technique | Before | After | Savings |
|----------|--------|-------|---------|
| Go module cache | 45s install | 3s restore | 93% |
| Docker layer cache | 3 min build | 30s build | 83% |
| Parallel lint+test | 5 min sequential | 3 min parallel | 40% |
| Path filters (monorepo) | 8 services built | 2 services built | 75% |
| Larger runner (8 CPU) | 10 min build | 5 min build | 50% |

### 6.2 Cost Management

```yaml
# Tip 1: Cancel redundant runs
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

# Tip 2: Path filters
on:
  push:
    paths:
      - 'src/**'
      - 'Dockerfile'
      - '.github/workflows/ci.yaml'
    paths-ignore:
      - '**.md'
      - 'docs/**'

# Tip 3: Conditional expensive steps
- name: Integration tests
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  run: make integration-test

# Tip 4: Reuse artifacts between jobs
- uses: actions/upload-artifact@v4
  with:
    name: binary
    path: bin/myservice
    retention-days: 1  # Don't keep forever
```

---

## 7. Security & Reliability Considerations

### 7.1 Security Threats

```mermaid
graph TB
    subgraph "Supply Chain Attacks"
        A1[Compromised action<br/>via tag/branch]
        A2[Dependency confusion<br/>npm/pip]
        A3[Typosquatting<br/>actions/checkuot]
    end
    
    subgraph "Credential Theft"
        B1[Secret in logs]
        B2[Secret in artifact]
        B3[Exfiltration via<br/>network call]
    end
    
    subgraph "Code Injection"
        C1[Malicious PR<br/>from fork]
        C2[Script injection<br/>via PR title/body]
        C3[workflow_run<br/>privilege escalation]
    end
```

### 7.2 Script Injection Prevention

```yaml
# ❌ VULNERABLE - PR title injected into shell
- run: echo "PR: ${{ github.event.pull_request.title }}"

# ✅ SAFE - Use environment variable
- env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: echo "PR: $PR_TITLE"
```

### 7.3 Fork PR Security

```yaml
# ❌ Dangerous: pull_request_target runs with repo secrets on fork code
on:
  pull_request_target:

# ✅ Safe: pull_request doesn't have access to secrets
on:
  pull_request:

# ✅ If you need secrets for fork PRs: require label/approval first
on:
  pull_request_target:
    types: [labeled]
jobs:
  build:
    if: contains(github.event.pull_request.labels.*.name, 'safe-to-test')
```

---

## 8. Hands-on Example

### Complete CI Pipeline cho Go Microservice

#### Bước 1: Tạo project

```bash
mkdir -p ~/gha-lab && cd ~/gha-lab
git init

# Tạo Go service (tái sử dụng từ Day 32)
cat > go.mod << 'EOF'
module github.com/example/myservice
go 1.22
EOF

cat > main.go << 'EOF'
package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
)

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"status":"healthy","version":"%s"}`, os.Getenv("APP_VERSION"))
}

func helloHandler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	if name == "" {
		name = "World"
	}
	fmt.Fprintf(w, "Hello, %s!", name)
}

func main() {
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/hello", helloHandler)
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("Starting on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
EOF

cat > main_test.go << 'EOF'
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthHandler(t *testing.T) {
	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()
	healthHandler(w, req)
	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
}

func TestHelloHandler(t *testing.T) {
	tests := []struct {
		query, expected string
	}{
		{"", "Hello, World!"},
		{"?name=GHA", "Hello, GHA!"},
	}
	for _, tt := range tests {
		req := httptest.NewRequest("GET", "/hello"+tt.query, nil)
		w := httptest.NewRecorder()
		helloHandler(w, req)
		if w.Body.String() != tt.expected {
			t.Errorf("expected %q, got %q", tt.expected, w.Body.String())
		}
	}
}
EOF

cat > Dockerfile << 'EOF'
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o myservice .

FROM gcr.io/distroless/static:nonroot
COPY --from=builder /app/myservice /myservice
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/myservice"]
EOF
```

#### Bước 2: Tạo GitHub Actions workflow

```bash
mkdir -p .github/workflows

cat > .github/workflows/ci.yaml << 'WORKFLOW'
name: CI Pipeline

on:
  push:
    branches: [main]
    paths-ignore: ['**.md', 'docs/**']
  pull_request:
    branches: [main]

permissions:
  contents: read
  packages: write

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  GO_VERSION: '1.22'
  IMAGE_NAME: myservice

jobs:
  # === Stage 1: Lint (parallel) ===
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ env.GO_VERSION }}
          cache: true
      - name: Check formatting
        run: test -z "$(gofmt -l .)"
      - name: Vet
        run: go vet ./...

  # === Stage 2: Test (parallel with lint) ===
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ env.GO_VERSION }}
          cache: true
      - name: Run tests
        run: go test -v -race -coverprofile=coverage.out ./...
      - name: Check coverage
        run: |
          COVERAGE=$(go tool cover -func=coverage.out | grep total | awk '{print $3}' | tr -d '%')
          echo "Coverage: ${COVERAGE}%"
          if (( $(echo "$COVERAGE < 50" | bc -l) )); then
            echo "::error::Coverage ${COVERAGE}% is below 50% threshold"
            exit 1
          fi
      - name: Upload coverage
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.out
          retention-days: 7

  # === Stage 3: Build & Push (after lint + test) ===
  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    timeout-minutes: 15
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v6

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Docker meta
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository_owner }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch
            type=semver,pattern={{version}}

      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          load: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Test image
        run: |
          docker run -d --name test-container -p 8080:8080 \
            -e APP_VERSION=test \
            $(echo "${{ steps.meta.outputs.tags }}" | head -1)
          sleep 2
          curl -sf http://localhost:8080/health | grep -q healthy
          docker rm -f test-container

      - name: Push image
        if: github.ref == 'refs/heads/main'
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # === Stage 4: Security Scan (after build) ===
  scan:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v6
      - name: Trivy vulnerability scan
        uses: aquasecurity/trivy-action@v0.36.0
        with:
          image-ref: ghcr.io/${{ github.repository_owner }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          exit-code: 1
          severity: CRITICAL,HIGH
          format: table

  # === Stage 5: Deploy to staging (after scan) ===
  deploy-staging:
    needs: scan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          echo "Deploying ${{ env.IMAGE_NAME }}:${{ github.sha }} to staging"
          # In production: update GitOps config repo
          # Example: update image tag in Kustomize overlay
          echo "Image: ghcr.io/${{ github.repository_owner }}/${{ env.IMAGE_NAME }}:${{ github.sha }}"
WORKFLOW

echo "Workflow created: .github/workflows/ci.yaml"
```

#### Bước 3: Validate workflow locally

```bash
# Kiểm tra YAML syntax
cat .github/workflows/ci.yaml | python3 -c "import yaml,sys; yaml.safe_load(sys.stdin); print('YAML valid ✅')"

# Kiểm tra structure
grep -c "jobs:" .github/workflows/ci.yaml    # Should be 1
grep -c "steps:" .github/workflows/ci.yaml   # Should be 5 (one per job)
grep -c "timeout-minutes:" .github/workflows/ci.yaml  # Should be 5

echo "Workflow structure verified ✅"
```

#### Bước 4: Test locally với act (optional)

```bash
# act = local GitHub Actions runner
# Install: https://github.com/nektos/act
# brew install act (macOS) hoặc go install github.com/nektos/act@latest

# Dry run
act --dryrun

# Run specific job
act -j lint
act -j test

# Full run
act push
```

#### Cleanup

```bash
cd ~ && rm -rf ~/gha-lab
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Common Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| `Permission denied` | Action can't push/write | Check `permissions:` block |
| Cache miss every time | No speedup | Check cache key, verify path |
| Job stuck "Queued" | Runner not available | Check runner status, concurrency limits |
| Secret empty | `$&#123;&#123; secrets.X &#125;&#125;` is empty | Check secret name, case-sensitive |
| Matrix generates 0 jobs | No combinations match | Check exclude/include logic |
| Workflow not triggered | Push doesn't start workflow | Check branch filter, path filter |
| Fork PR can't access secrets | Secrets empty | Expected — use `pull_request_target` carefully |

### 9.2 Debugging Tips

```yaml
# Debug step: print context
- name: Debug
  run: |
    echo "Event: ${{ github.event_name }}"
    echo "Ref: ${{ github.ref }}"
    echo "SHA: ${{ github.sha }}"
    echo "Actor: ${{ github.actor }}"
    echo "Runner OS: ${{ runner.os }}"

# Enable debug logging: set secret ACTIONS_RUNNER_DEBUG=true
# Enable step debug: set secret ACTIONS_STEP_DEBUG=true

# Re-run with debug: "Re-run jobs" → "Enable debug logging" checkbox

# Download logs: gh run view <run-id> --log
```

### 9.3 Production Case Study: Supply Chain Attack Prevention

#### Context
Một open-source project phổ biến (~5000 stars) trên GitHub dùng community actions không pin version.

#### Incident
Attacker compromise một action (`malicious-org/deploy-action@v2`). Tag `v2` được force-push để trỏ đến commit mới có mã độc. Tất cả repos dùng `@v2` tự động chạy mã độc.

#### Impact
- Secrets exfiltrated (AWS keys, npm tokens).
- 15 repos bị compromise.
- Malicious packages published lên npm.

#### Root Cause
- Dùng mutable tag (`@v2`) thay vì pinned SHA.
- Không review actions trước khi dùng.
- Over-privileged permissions (default `write-all`).

#### Prevention
1. Pin actions bằng full SHA: `actions/checkout@b4ffde65...`
2. Set `permissions:` explicitly — least privilege.
3. Dùng Dependabot cho GitHub Actions updates.
4. Review action source code trước khi adopt.
5. Prefer first-party actions (actions/*, github/*).

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ các bài trước

| Bài | Connection |
|-----|-----------|
| Day 8-9 | Docker build, image scan — stages Build + Scan |
| Day 31 | GitOps — Deploy stage update config repo thay vì kubectl apply |
| Day 32 | Pipeline design patterns — implement thật hôm nay |

### Bài sau

- **Day 34**: GitLab CI, Jenkins, CircleCI — so sánh với GitHub Actions.
- **Day 35**: Deployment Strategies — canary, blue-green trong deploy stage.
- **Day 37**: Artifact Registry, Image Signing — package stage advanced.

---

## 11. Tài liệu tham khảo

### Must-read

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
- [Reusable Workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows)

### Nice-to-have

- [act — Local GitHub Actions Runner](https://github.com/nektos/act)
- [GitHub Actions Marketplace](https://github.com/marketplace?type=actions)
- [GitHub Actions Cheat Sheet](https://github.github.io/actions-cheat-sheet/actions-cheat-sheet.html)

### Deep-dive

- [OIDC for GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [GitHub Actions Performance](https://github.blog/engineering/engineering-principles/how-we-build-containerized-services-at-github-using-github/)
- [Supply Chain Security — SLSA](https://slsa.dev/)

