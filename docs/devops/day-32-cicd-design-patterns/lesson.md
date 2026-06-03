# Day 32: CI/CD Design Patterns

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt rõ ràng CI, CD (Continuous Delivery) và CD (Continuous Deployment)** — giải thích được khi nào dùng delivery, khi nào dùng deployment.
2. **Thiết kế được pipeline chuẩn cho microservice** với đủ stages: lint → test → build → scan → package → deploy → verify.
3. **Định nghĩa được quality gates** phù hợp cho từng stage và giải thích tại sao mỗi gate tồn tại.
4. **Áp dụng DORA metrics** để đo lường và cải thiện CI/CD pipeline trong thực tế.
5. **Nhận diện được CI/CD anti-patterns** phổ biến và cách khắc phục.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Hãy tưởng tượng team bạn đang phát triển 8 microservices. Mỗi ngày có 15-20 pull requests merge. Câu hỏi đặt ra:

- Làm sao biết code mới không phá code cũ? → **CI** (chạy tests tự động).
- Làm sao đảm bảo mỗi commit đều deployable? → **CD** (build artifact sẵn sàng).
- Làm sao deploy nhanh mà an toàn? → **Quality gates** + **deployment strategy**.
- Làm sao đo team đang làm tốt hay tệ? → **DORA metrics**.

### Tại sao developer cần hiểu CI/CD

Nhiều developer coi CI/CD là "DevOps problem". Sai. CI/CD ảnh hưởng trực tiếp đến:

- **Developer experience**: Pipeline chậm 30 phút → context switching → năng suất giảm 40%.
- **Code quality**: Không có CI → bugs leak sang production → hotfix liên tục.
- **Release velocity**: Không có CD → release mỗi 2 tuần → features stuck, customers wait.
- **On-call burden**: Không có quality gates → bad deploys → 3 AM alerts.

### Liên hệ với kiến thức đã học

| Concept | Từ bài trước | Vai trò trong CI/CD |
|---------|-------------|-------------------|
| Docker | Day 8-9 | Build container image trong CI |
| Helm/Kustomize | Day 16 | Package manifests trong CD |
| GitOps | Day 31 | CD deployment (ArgoCD pulls from Git) |
| DORA metrics | Day 1 | Đo lường hiệu quả CI/CD |
| Image scanning | Day 9 | Security quality gate |

---

## 3. Kiến thức nền tảng

### 3.1 Định nghĩa chính xác

**Continuous Integration (CI)**:
- Developer merge code vào shared branch thường xuyên (nhiều lần/ngày).
- Mỗi merge trigger automated build + test.
- Mục tiêu: phát hiện integration issues sớm.
- Output: "Code này compile được và tests pass."

**Continuous Delivery (Delivery)**:
- Mọi commit trên main branch đều **có thể deploy** vào production.
- Deploy vẫn cần manual approval (button click).
- Output: "Artifact sẵn sàng deploy bất kỳ lúc nào."

**Continuous Deployment (Deployment)**:
- Mọi commit pass pipeline → **tự động deploy** production.
- Không có manual gate.
- Output: "Code merge → production trong vài phút."

```
Code → CI (build+test) → CD Delivery (artifact ready, manual deploy)
                       → CD Deployment (artifact ready, auto deploy)

             CI                    CD
         ┌────────┐     ┌────────────────────┐
         │ Build  │     │ Delivery: manual ✋  │
Commit──▶│ Test   │────▶│         OR          │──▶ Production
         │ Scan   │     │ Deployment: auto 🤖 │
         └────────┘     └────────────────────┘
```

**Khi nào dùng gì?**

| Model | Khi nào | Ví dụ |
|-------|--------|-------|
| Continuous Delivery | Regulated industry, team chưa mature, cần manual QA | Banking, healthcare, startup mới |
| Continuous Deployment | High-trust team, good test coverage, feature flags | Netflix, GitHub, Etsy |

### 3.2 Pipeline as Code

**Tại sao pipeline phải là code?**

| Aspect | UI-configured pipeline | Pipeline as Code |
|--------|----------------------|-----------------|
| Version control | ❌ Không track changes | ✅ Git history |
| Review | ❌ Không PR review | ✅ Code review |
| Reproducibility | ❌ Phụ thuộc UI state | ✅ Reproducible |
| Sharing | ❌ Copy-paste | ✅ Import/reuse |
| Testing | ❌ Không test được | ✅ Lint, dry-run |
| Disaster recovery | ❌ Backup manual | ✅ Git clone |

**Pipeline as Code formats**:
- GitHub Actions: `.github/workflows/*.yaml`
- GitLab CI: `.gitlab-ci.yml`
- Jenkins: `Jenkinsfile` (Groovy)
- CircleCI: `.circleci/config.yml`

### 3.3 Pipeline Stages Chi Tiết

```mermaid
graph LR
    A[Commit/PR] --> B[Lint]
    B --> C[Test]
    C --> D[Build]
    D --> E[Scan]
    E --> F[Package]
    F --> G[Deploy]
    G --> H[Verify]
    
    style B fill:#e1f5fe
    style C fill:#e1f5fe
    style D fill:#fff3e0
    style E fill:#fce4ec
    style F fill:#fff3e0
    style G fill:#e8f5e9
    style H fill:#e8f5e9
```

| Stage | Mục đích | Tools phổ biến | Thời gian target |
|-------|---------|---------------|-----------------|
| **Lint** | Code style, formatting, static analysis | ESLint, golangci-lint, Ruff, Prettier | < 1 min |
| **Test** | Unit tests, integration tests | Jest, Go test, pytest, JUnit | < 5 min (unit), < 15 min (integration) |
| **Build** | Compile, build artifact | go build, npm build, Docker build | < 3 min |
| **Scan** | Security vulnerabilities, licenses | Trivy, Snyk, Grype, Semgrep | < 2 min |
| **Package** | Create deployable artifact | Docker push, Helm package, OCI push | < 1 min |
| **Deploy** | Deploy to environment | kubectl, ArgoCD sync, Helm upgrade | < 5 min |
| **Verify** | Smoke tests, health checks | curl, k6, custom scripts | < 3 min |

---

## 4. Deep Dive

### 4.1 Pipeline Architecture Patterns

#### Pattern 1: Linear Pipeline

```mermaid
graph LR
    L[Lint] --> T[Test] --> B[Build] --> S[Scan] --> D[Deploy Dev] --> V[Verify]
```

- **Ưu điểm**: Đơn giản, dễ debug.
- **Nhược điểm**: Chậm (sequential).
- **Dùng khi**: Service nhỏ, pipeline tổng < 10 phút.

#### Pattern 2: Fan-out / Fan-in

```mermaid
graph TB
    C[Commit] --> L[Lint]
    C --> UT[Unit Test]
    C --> ST[Security Scan]
    L --> B[Build]
    UT --> B
    ST --> B
    B --> IT[Integration Test]
    B --> PS[Push Image]
    IT --> D[Deploy]
    PS --> D
    D --> V[Verify]
```

- **Ưu điểm**: Nhanh hơn (parallel stages).
- **Nhược điểm**: Phức tạp hơn, khó debug failures.
- **Dùng khi**: Pipeline > 10 phút, cần optimize.

#### Pattern 3: Multi-environment Pipeline

```mermaid
graph LR
    B[Build] --> DD[Deploy Dev]
    DD --> TD[Test Dev]
    TD --> DS[Deploy Staging]
    DS --> TS[Test Staging]
    TS --> AP[Manual Approval]
    AP --> DP[Deploy Prod]
    DP --> VP[Verify Prod]
```

- **Ưu điểm**: Validate qua nhiều environments.
- **Nhược điểm**: Chậm end-to-end.
- **Dùng khi**: Production-critical services.

#### Pattern 4: Matrix Build

```mermaid
graph TB
    C[Commit] --> M1[Go 1.21 / Linux]
    C --> M2[Go 1.22 / Linux]
    C --> M3[Go 1.22 / macOS]
    M1 --> R[Results]
    M2 --> R
    M3 --> R
```

- **Dùng khi**: Libraries, CLI tools cần test nhiều OS/version.

### 4.2 Quality Gates

Quality gate = điều kiện bắt buộc phải pass trước khi pipeline tiếp tục.

```mermaid
graph TB
    subgraph "Gate 1: Code Quality"
        G1A[Lint pass]
        G1B[No formatting issues]
        G1C[Complexity < threshold]
    end
    
    subgraph "Gate 2: Testing"
        G2A[Unit tests pass]
        G2B[Coverage > 80%]
        G2C[No flaky tests]
    end
    
    subgraph "Gate 3: Security"
        G3A[No CRITICAL CVEs]
        G3B[No leaked secrets]
        G3C[License compliant]
    end
    
    subgraph "Gate 4: Performance"
        G4A[No p99 regression > 20%]
        G4B[No memory regression]
    end
    
    subgraph "Gate 5: Deployment"
        G5A[Health check pass]
        G5B[Smoke test pass]
        G5C[Error rate < 1%]
    end
```

**Quality Gate Design Principles**:

1. **Must be automatable**: Nếu không automate được → tắc nghẽn.
2. **Fast feedback**: Gate chậm = developer chờ = morale giảm.
3. **Actionable**: Gate fail → developer biết sửa ở đâu.
4. **No false positives**: False positive quá nhiều → team bỏ qua gate → gate vô nghĩa.
5. **Progressive strictness**: Dev (lax) → Staging (medium) → Prod (strict).

### 4.3 DORA Metrics trong CI/CD

| DORA Metric | Đo gì | CI/CD ảnh hưởng thế nào | Target (Elite) |
|------------|-------|----------------------|---------------|
| **Deployment Frequency** | Bao lâu deploy 1 lần | Automated CD → deploy nhiều lần/ngày | On-demand (nhiều lần/ngày) |
| **Lead Time for Changes** | Từ commit đến production | Pipeline nhanh → lead time ngắn | < 1 giờ |
| **Change Failure Rate** | % deployments gây incident | Quality gates → ít failures | < 5% |
| **MTTR** | Thời gian recovery từ failure | Fast rollback → MTTR ngắn | < 1 giờ |

**Cách đo DORA từ CI/CD data**:

```bash
# Deployment Frequency: count deploys per day
# Data source: CI/CD tool API
git log --format="%H %ci" --since="30 days ago" | wc -l

# Lead Time: time from first commit to deploy
# = PR merge time + pipeline time + deploy time

# Change Failure Rate: failed deploys / total deploys
# Data source: CI/CD tool + incident tracker

# MTTR: mean time incident open → resolved
# Data source: Incident management system (PagerDuty, OpsGenie)
```

### 4.4 Pipeline Speed Optimization

Pipeline chậm = chi phí ẩn rất lớn:

```
10 engineers × 5 PRs/day × 30 min wait = 25 engineering-hours/day WASTED
Với salary $80/hour = $2,000/day = $500,000/year wasted on waiting
```

**Optimization techniques**:

| Technique | Impact | Effort |
|----------|--------|--------|
| **Caching** (dependencies, build cache) | ⭐⭐⭐⭐⭐ | Low |
| **Parallel stages** (fan-out) | ⭐⭐⭐⭐ | Low |
| **Skip unchanged** (path filters) | ⭐⭐⭐ | Low |
| **Smaller images** (multi-stage build) | ⭐⭐⭐ | Medium |
| **Test splitting** (parallel test execution) | ⭐⭐⭐⭐ | Medium |
| **Self-hosted runners** (faster hardware) | ⭐⭐⭐ | High |
| **Incremental builds** | ⭐⭐⭐⭐ | High |
| **Remote build cache** | ⭐⭐⭐⭐ | Medium |

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Pipeline Design Trade-offs

| Decision | Option A | Option B | Recommendation |
|---------|---------|---------|---------------|
| Test scope in CI | Full test suite | Only unit + smoke | Unit + smoke in CI, integration nightly |
| Image tag | Git SHA | Semantic version | SHA cho CI, SemVer cho releases |
| Deploy trigger | On every merge | Manual button | Auto for dev/staging, manual for prod |
| Monorepo pipeline | Build everything | Build only changed | Path filters + build only changed |
| Runner | Cloud-hosted | Self-hosted | Cloud-hosted default, self-hosted cho perf/security |

### 5.2 Best Practices

1. **Pipeline dưới 10 phút** cho CI feedback loop. Mọi thứ trên 15 phút → optimize.
2. **Fail fast**: Chạy lint + unit tests trước, build sau. Nếu tests fail, không cần build.
3. **Immutable artifacts**: Không build lại cho mỗi environment. Build 1 lần, deploy nhiều env.
4. **Cache everything**: Dependencies, Docker layers, build outputs.
5. **Path filters**: Monorepo → chỉ trigger pipeline cho services bị thay đổi.
6. **No secrets in pipeline logs**: Mask sensitive values.
7. **Pin versions**: Lock tool versions trong pipeline (Terraform, Docker, etc.).
8. **Test the pipeline**: Pipeline code cũng cần CI (lint YAML, dry-run).

### 5.3 Anti-patterns

| Anti-pattern | Vấn đề | Giải pháp |
|-------------|--------|----------|
| **Deploy Friday** | Ít người available nếu fail | Deploy freeze Friday PM, hoặc đủ mature → deploy anytime |
| **Manual testing in pipeline** | Chậm, không reproducible | Automate tất cả tests |
| **Snowflake environments** | "Works on staging" ≠ works on prod | IaC cho environments, Docker → consistent |
| **Big bang releases** | Risk cao, rollback khó | Small, frequent releases |
| **No rollback plan** | Stuck khi deploy fail | Automated rollback dựa trên health check |
| **Flaky tests** | Team học cách ignore failures | Fix hoặc quarantine flaky tests |
| **Long-lived feature branches** | Merge hell, integration issues | Trunk-based + feature flags |
| **Pipeline without caching** | Build 5 phút → 15 phút | Cache dependencies + build layers |

---

## 6. Performance & Scalability ⭐

### 6.1 Pipeline Performance Benchmarks

| Metric | Poor | Acceptable | Good | Elite |
|--------|------|-----------|------|-------|
| CI feedback time | > 30 min | 15-30 min | 5-15 min | < 5 min |
| Full pipeline time | > 60 min | 30-60 min | 15-30 min | < 15 min |
| Deploy time | > 30 min | 15-30 min | 5-15 min | < 5 min |
| Rollback time | > 30 min | 15-30 min | 5-15 min | < 1 min |

### 6.2 Scaling CI/CD

| Scale | Challenge | Solution |
|-------|----------|---------|
| 5 engineers | Pipeline quá chậm | Caching, parallel stages |
| 20 engineers | Queue wait time | More runners, matrix optimization |
| 50 engineers | Monorepo build explosion | Path filters, affected services detection |
| 100+ engineers | Cost, infrastructure | Self-hosted runners, build farm, remote cache |

### 6.3 Cost Considerations

```
GitHub Actions: $0.008/min (Linux), $0.016/min (macOS)
1 service × 20 runs/day × 10 min = 200 min/day = $1.60/day = $48/month

10 services × 20 runs/day × 10 min = 2000 min/day = $16/day = $480/month

Optimization impact:
- Caching: -30% time = -$144/month
- Skip unchanged: -40% runs = -$192/month
- Parallel stages: -20% time = -$96/month
```

---

## 7. Security & Reliability Considerations

### 7.1 CI/CD Security Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Secret leaks** | Credentials trong logs/artifacts | Secret masking, vault integration |
| **Supply chain attack** | Compromised dependencies/actions | Pin versions, verify checksums, SCA |
| **Runner compromise** | Attacker access build env | Ephemeral runners, sandboxing |
| **Privilege escalation** | Build job runs as root | Non-root containers, least privilege |
| **Code injection** | PR từ fork chứa malicious code | Require approval for fork PRs |
| **Dependency confusion** | Private package overridden by public | Scoped registries, lockfiles |

### 7.2 Security Best Practices

```yaml
# Pipeline security checklist:
- [ ] Secrets stored trong vault/secret manager, KHÔNG trong code
- [ ] Secret masking enabled (GitHub: add-mask)
- [ ] Pin action versions bằng full commit SHA (`actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11`)
- [ ] OIDC cho cloud authentication (không dùng long-lived tokens)
- [ ] Ephemeral runners (tự cleanup sau mỗi job)
- [ ] Require PR approval trước khi chạy CI cho fork PRs
- [ ] SBOM generated cho mỗi artifact
- [ ] Image signed bằng cosign
- [ ] Audit log cho pipeline executions
```

### 7.3 Reliability

- **Idempotent deployments**: Chạy pipeline 2 lần → cùng kết quả.
- **Retry with backoff**: Network failures → retry với exponential backoff.
- **Circuit breaker**: Nếu deploy fail 3 lần liên tiếp → stop auto-deploy, alert.
- **Blue-green / canary deploys**: Không all-or-nothing (sẽ learn Day 35).

---

## 8. Hands-on Example

### Thiết kế pipeline cho Go microservice

Chúng ta sẽ thiết kế pipeline hoàn chỉnh cho một Go HTTP service đơn giản, sử dụng Makefile local để mô phỏng mỗi stage.

### Bước 1: Tạo project structure

```bash
mkdir -p ~/cicd-lab && cd ~/cicd-lab

# Tạo Go module
cat > go.mod << 'EOF'
module github.com/example/myservice

go 1.22
EOF

# Tạo main.go
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
	fmt.Fprintf(w, `{"status":"healthy","version":"%s"}`, version())
}

func helloHandler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	if name == "" {
		name = "World"
	}
	fmt.Fprintf(w, "Hello, %s!", name)
}

func version() string {
	v := os.Getenv("APP_VERSION")
	if v == "" {
		return "dev"
	}
	return v
}

func main() {
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/hello", helloHandler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Starting server on :%s (version: %s)", port, version())
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
EOF

# Tạo test file
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
		name     string
		query    string
		expected string
	}{
		{"default", "", "Hello, World!"},
		{"custom", "?name=DevOps", "Hello, DevOps!"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/hello"+tt.query, nil)
			w := httptest.NewRecorder()
			helloHandler(w, req)

			if w.Body.String() != tt.expected {
				t.Errorf("expected %q, got %q", tt.expected, w.Body.String())
			}
		})
	}
}
EOF
```

### Bước 2: Tạo Dockerfile

```bash
cat > Dockerfile << 'EOF'
# Stage 1: Build
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/myservice .

# Stage 2: Runtime
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /app/myservice /myservice
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/myservice"]
EOF
```

### Bước 3: Tạo Makefile mô phỏng pipeline stages

```bash
cat > Makefile << 'MAKEFILE'
.PHONY: all lint test build scan package deploy verify clean

APP_NAME := myservice
VERSION := $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")
IMAGE := $(APP_NAME):$(VERSION)

# === Full Pipeline ===
all: lint test build scan package
	@echo "✅ Pipeline completed successfully!"

# === Stage 1: Lint ===
lint:
	@echo "🔍 Stage: LINT"
	@echo "  Checking Go formatting..."
	@test -z "$$(gofmt -l .)" || (echo "  ❌ Files not formatted:" && gofmt -l . && exit 1)
	@echo "  Checking Go vet..."
	@go vet ./...
	@echo "  ✅ Lint passed"
	@echo ""

# === Stage 2: Test ===
test:
	@echo "🧪 Stage: TEST"
	@echo "  Running unit tests..."
	@go test -v -race -coverprofile=coverage.out ./...
	@echo "  Checking coverage..."
	@go tool cover -func=coverage.out | tail -1
	@echo "  ✅ Tests passed"
	@echo ""

# === Stage 3: Build ===
build:
	@echo "🔨 Stage: BUILD"
	@echo "  Building binary..."
	@CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o bin/$(APP_NAME) .
	@ls -lh bin/$(APP_NAME)
	@echo "  ✅ Build completed"
	@echo ""

# === Stage 4: Scan ===
scan:
	@echo "🛡️ Stage: SCAN"
	@echo "  Scanning for vulnerabilities..."
	@if command -v trivy >/dev/null 2>&1; then \
		trivy fs --severity HIGH,CRITICAL --exit-code 1 .; \
	else \
		echo "  ⚠️ Trivy not installed, skipping scan"; \
	fi
	@echo "  Checking for secrets..."
	@! grep -rn "password\|secret\|api_key" --include="*.go" . | grep -v "_test.go" | grep -v "Makefile" || echo "  ⚠️ Potential secrets found!"
	@echo "  ✅ Scan completed"
	@echo ""

# === Stage 5: Package ===
package:
	@echo "📦 Stage: PACKAGE"
	@echo "  Building Docker image: $(IMAGE)"
	@docker build -t $(IMAGE) .
	@docker images $(APP_NAME) --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
	@echo "  ✅ Package completed"
	@echo ""

# === Stage 6: Deploy (local) ===
deploy:
	@echo "🚀 Stage: DEPLOY"
	@echo "  Deploying $(IMAGE) locally..."
	@docker rm -f $(APP_NAME) 2>/dev/null || true
	@docker run -d --name $(APP_NAME) -p 8080:8080 -e APP_VERSION=$(VERSION) $(IMAGE)
	@echo "  Waiting for startup..."
	@sleep 2
	@echo "  ✅ Deploy completed"
	@echo ""

# === Stage 7: Verify ===
verify:
	@echo "✔️ Stage: VERIFY"
	@echo "  Health check..."
	@curl -sf http://localhost:8080/health | python3 -m json.tool || (echo "  ❌ Health check failed" && exit 1)
	@echo "  Smoke test..."
	@curl -sf http://localhost:8080/hello?name=Pipeline || (echo "  ❌ Smoke test failed" && exit 1)
	@echo ""
	@echo "  ✅ Verify passed"
	@echo ""

# === Cleanup ===
clean:
	@echo "🧹 Cleanup"
	@docker rm -f $(APP_NAME) 2>/dev/null || true
	@rm -rf bin/ coverage.out
	@echo "  ✅ Cleaned up"
MAKEFILE
```

### Bước 4: Chạy pipeline

```bash
cd ~/cicd-lab

# Chạy từng stage
make lint
make test
make build
make scan

# Chạy full pipeline (lint → test → build → scan → package)
make all

# Deploy & verify
make deploy
make verify

# Cleanup
make clean
```

### Expected output (tóm tắt):

```
🔍 Stage: LINT
  Checking Go formatting...
  Checking Go vet...
  ✅ Lint passed

🧪 Stage: TEST
  Running unit tests...
  === RUN   TestHealthHandler
  --- PASS: TestHealthHandler (0.00s)
  === RUN   TestHelloHandler
  === RUN   TestHelloHandler/default
  === RUN   TestHelloHandler/custom
  --- PASS: TestHelloHandler (0.00s)
  PASS
  coverage: 62.5% of statements
  ✅ Tests passed

🔨 Stage: BUILD
  Building binary...
  -rwxr-x--- 1 user user 5.2M myservice
  ✅ Build completed

🛡️ Stage: SCAN
  Scanning for vulnerabilities...
  ✅ Scan completed

📦 Stage: PACKAGE
  Building Docker image: myservice:abc1234
  REPOSITORY   TAG       SIZE
  myservice    abc1234   7.2MB
  ✅ Package completed

✅ Pipeline completed successfully!
```

### Bước 5: Tạo GitHub Actions equivalent

```bash
mkdir -p .github/workflows

cat > .github/workflows/ci.yaml << 'EOF'
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  GO_VERSION: '1.22'
  IMAGE_NAME: myservice

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ env.GO_VERSION }}
      - name: Lint
        run: |
          test -z "$(gofmt -l .)"
          go vet ./...

  test:
    runs-on: ubuntu-latest
    needs: []  # Parallel with lint
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ env.GO_VERSION }}
          cache: true
      - name: Test
        run: go test -v -race -coverprofile=coverage.out ./...
      - name: Coverage Check
        run: |
          COVERAGE=$(go tool cover -func=coverage.out | grep total | awk '{print $3}' | tr -d '%')
          echo "Coverage: ${COVERAGE}%"
          # Fail if coverage < 60%
          if (( $(echo "$COVERAGE < 60" | bc -l) )); then
            echo "❌ Coverage below 60%"
            exit 1
          fi

  build-and-scan:
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v6
      - name: Build image
        run: docker build -t $IMAGE_NAME:${{ github.sha }} .
      - name: Scan image
        uses: aquasecurity/trivy-action@v0.36.0
        with:
          image-ref: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          exit-code: 1
          severity: CRITICAL,HIGH

  # deploy job omitted (handled by GitOps - Day 31)
EOF

echo "GitHub Actions workflow created: .github/workflows/ci.yaml"
```

### Verify & Cleanup

```bash
# Verify tất cả files tồn tại
ls -la ~/cicd-lab/
# Expected: go.mod, main.go, main_test.go, Dockerfile, Makefile, .github/

# Cleanup
make clean
cd ~ && rm -rf ~/cicd-lab
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Pipeline Problems

| Problem | Dấu hiệu | Root cause | Fix |
|---------|----------|-----------|-----|
| Pipeline chậm | > 15 min CI feedback | No caching, sequential stages | Add caching, parallelize |
| Flaky tests | Pass/fail randomly | Race conditions, time-dependent, external deps | Fix root cause hoặc quarantine |
| Build fails trên CI nhưng works locally | "Works on my machine" | Env differences, cached state | Docker build, clean workspace |
| Secret leak | Credentials trong logs | echo $SECRET, debug logging | Mask secrets, audit logs |
| Out of disk | Pipeline fails mid-build | Accumulated images/caches | Cleanup steps, ephemeral runners |
| Rate limiting | Docker pull fails | Docker Hub rate limit | Use mirror, authenticated pulls |

### 9.2 Debug Flow

```
Pipeline failed?
│
├── Which stage?
│   ├── Lint → Check linter config, code formatting
│   ├── Test → Check test output, flaky test history
│   ├── Build → Check Dockerfile, dependencies, disk space
│   ├── Scan → Check CVE details, is it false positive?
│   ├── Deploy → Check K8s events, image pull, RBAC
│   └── Verify → Check health endpoint, network, timing
│
├── Is it intermittent?
│   ├── Yes → likely: flaky test, network, rate limit, timing
│   └── No → likely: code issue, config issue, dependency
│
└── Is it new?
    ├── Yes → git diff, check what changed
    └── No → infrastructure issue, expired creds, quota
```

### 9.3 Production Case Study: Pipeline Optimization

#### Context
Một e-commerce company, 20 microservices, 40 engineers, GitHub Actions.

#### Problem
CI pipeline mất **28 phút** trung bình. Engineers merge 20 PRs/ngày → mỗi ngày mất **9+ engineering-hours** chờ pipeline.

#### Investigation
```
Stage breakdown:
- Checkout:           30s
- Install deps:       4m (npm install from scratch mỗi lần)
- Lint:               1m
- Unit tests:         3m
- Integration tests:  12m (full database setup + teardown)
- Docker build:       5m (no layer caching)
- Scan:               2m
- Push:               1m
Total:                ~28m
```

#### Optimizations applied
1. **npm cache**: `actions/cache` cho node_modules → install 4m → 30s.
2. **Parallel stages**: Lint + Unit tests chạy đồng thời → giảm 1m.
3. **Docker layer cache**: `docker/build-push-action` với cache → build 5m → 1m.
4. **Split integration tests**: Chỉ chạy affected tests dựa trên changed files → 12m → 4m.
5. **Skip unchanged services**: Path filter trong monorepo → giảm 60% triggers.

#### Result
Pipeline: 28 min → **8 min**. Engineering hours saved: **7 hours/day**.

#### Lesson Learned
Pipeline performance = developer productivity. Mỗi phút saved × 40 engineers × 5 runs/day = 200 engineer-minutes/day = **3.3 engineer-hours/day per minute saved**.

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ các bài trước

| Bài | Connection |
|-----|-----------|
| Day 1 | DORA metrics — CI/CD là cách implement để improve DORA |
| Day 6 | Git workflows — trunk-based development tương quan CI/CD tốt |
| Day 8-9 | Docker build, image scanning — stages trong CI pipeline |
| Day 16 | Helm/Kustomize — packaging trong CD |
| Day 31 | GitOps — CD deployment model (pull-based) |

### Bài sau sẽ mở rộng

- **Day 33**: GitHub Actions Deep Dive — implement pipeline thật từ design hôm nay.
- **Day 34**: GitLab CI, Jenkins, CircleCI — so sánh tools, chọn tool phù hợp.
- **Day 35**: Deployment Strategies — rolling, canary, blue-green (stage Deploy detail).
- **Day 36**: Progressive Delivery — automated canary analysis (advanced CD).
- **Day 37**: Artifact Registry, Image Signing — stage Package + supply chain security.

---

## 11. Tài liệu tham khảo

### Must-read

- [Continuous Delivery — Jez Humble & David Farley](https://continuousdelivery.com/) (sách gốc định nghĩa CD)
- [DORA State of DevOps Report](https://dora.dev/research/) (data-driven CI/CD insights)
- [The Twelve-Factor App — Build/Release/Run](https://12factor.net/build-release-run)

### Nice-to-have

- [minimumcd.org — Minimum CD Practices](https://minimumcd.org/)
- [Martin Fowler — Continuous Integration](https://martinfowler.com/articles/continuousIntegration.html)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pipeline Design Patterns — DZone](https://dzone.com/articles/pipeline-design-patterns)

### Deep-dive

- [Accelerate — Nicole Forsgren, Jez Humble, Gene Kim](https://itrevolution.com/book/accelerate/) (DORA research book)
- [Release It! — Michael Nygard](https://pragprog.com/titles/mnee2/release-it-second-edition/) (production patterns)
- [Testing in Production — Charity Majors](https://increment.com/testing/testing-in-production/)

