# Day 32: CI/CD Design Patterns — Exercises



## Exercise 1: Pipeline Stage Walkthrough (Easy)



### Context



Bạn mới join một team đang phát triển REST API bằng Go. Team chưa có CI/CD pipeline. Tech lead giao cho bạn nhiệm vụ setup pipeline cơ bản trên local trước khi chuyển sang GitHub Actions.



### Yêu cầu



1. Tạo Go HTTP service đơn giản (dùng code từ hands-on trong lesson).

2. Chạy từng stage trong Makefile tuần tự: `lint → test → build → scan → package`.

3. Ghi lại **thời gian** mỗi stage (dùng `time make <stage>`).

4. Chạy full pipeline bằng `make all`.

5. Deploy local và verify bằng `make deploy && make verify`.



### Expected Outcome



- Hiểu rõ mỗi stage làm gì và tại sao cần stage đó.

- Biết được stage nào chậm nhất.

- Service chạy local, health check pass.



### Hints



- Nếu không có Go, có thể dùng Node.js/Python tương đương.

- `time make lint` để đo thời gian.

- Nếu Trivy chưa cài, stage scan sẽ skip — đó là ok.



### Acceptance Criteria



- [ ] Tất cả 5 stages chạy thành công.

- [ ] Ghi lại timing mỗi stage.

- [ ] Deploy & verify pass.

- [ ] Cleanup thành công.

- [ ] Viết 3 observations: stage nào chậm nhất, cái gì có thể parallelize, cái gì cần caching.



### Bonus Challenge



Thêm stage `coverage-check` vào Makefile: fail nếu test coverage < 60%.



<details>

<summary>Solution</summary>



```bash

# Setup project (copy từ hands-on lesson)

mkdir -p ~/cicd-lab && cd ~/cicd-lab

# ... (tạo go.mod, main.go, main_test.go, Dockerfile, Makefile — xem lesson)



# Chạy từng stage với timing

time make lint      # Expected: < 5s

time make test      # Expected: < 5s

time make build     # Expected: < 10s

time make scan      # Expected: < 30s

time make package   # Expected: < 60s



# Full pipeline

time make all       # Expected: < 2 min total



# Deploy & verify

make deploy

make verify



# Observations:

# 1. Slowest stage: package (Docker build) — ~30-60s

# 2. Parallelizable: lint + test (no dependency between them)

# 3. Needs caching: Docker build layers, Go module cache



# Bonus: Coverage check

cat >> Makefile << 'EOF'



coverage-check:

	@echo "📊 Coverage Check"

	@COVERAGE=$$(go tool cover -func=coverage.out | grep total | awk '{print $$3}' | tr -d '%'); \

	echo "  Coverage: $${COVERAGE}%"; \

	if [ $$(echo "$${COVERAGE} < 60" | bc -l) -eq 1 ]; then \

		echo "  ❌ Coverage below 60%"; \

		exit 1; \

	fi

	@echo "  ✅ Coverage check passed"

EOF



make test

make coverage-check



# Cleanup

make clean

cd ~ && rm -rf ~/cicd-lab

```



</details>



---



## Exercise 2: Quality Gate Design (Medium)



### Context



Bạn đang thiết kế CI/CD pipeline cho một e-commerce platform gồm 5 microservices:



| Service | Language | Criticality |

|---------|---------|-------------|

| payment-service | Go | Critical |

| user-service | TypeScript | High |

| product-service | Python | Medium |

| notification-service | Go | Low |

| analytics-service | Python | Low |



Team có 15 engineers, deploy 10 lần/ngày, và gần đây gặp 3 incidents vì bad deployments.



### Yêu cầu



1. **Thiết kế quality gates** cho mỗi pipeline stage, chia theo criticality level.

2. **Viết quality gate matrix**: mỗi service type có threshold khác nhau.

3. **Thiết kế approval flow**: khi nào cần manual approval, khi nào auto.

4. **Xử lý false positives**: strategy khi security scan báo false positive.

5. **Thiết kế dashboard** track DORA metrics từ pipeline data.



### Expected Outcome



- Quality gate matrix document (bảng rõ ràng).

- Approval flow diagram.

- False positive handling SOP.

- DORA metrics dashboard design (panels + data sources).



### Hints



- Critical services cần stricter gates (coverage > 80%, zero CRITICAL CVEs).

- Low criticality services có thể relax gates (coverage > 50%, allow HIGH CVEs with fix timeline).

- Dùng tiered approach: blocking (fail pipeline) vs warning (log but continue).

- DORA metrics cần data từ: Git (commit times), CI tool (pipeline times), deploy tool (deploy times), incident tracker.



### Acceptance Criteria



- [ ] Quality gate matrix cho 3 criticality levels.

- [ ] Approval flow documented.

- [ ] False positive SOP written.

- [ ] DORA dashboard designed (ít nhất 6 panels).

- [ ] Trade-offs được ghi rõ cho mỗi decision.



### Bonus Challenge



Viết GitHub Actions reusable workflow cho quality gates — có thể share giữa các services.



<details>

<summary>Solution</summary>



### Quality Gate Matrix
### Approval Flow



```

PR Merged to main

│

├── CI Pipeline (auto)

│   ├── Lint + Test + Build + Scan

│   └── Quality gates check

│

├── Deploy to Dev (auto)

│   └── Smoke tests (auto)

│

├── Deploy to Staging (auto for Medium/Low, manual trigger for Critical/High)

│   └── Integration tests (auto)

│   └── Performance tests (auto for Critical)

│

└── Deploy to Prod

    ├── Critical: 2 approvers + change window

    ├── High: 1 approver

    └── Medium/Low: auto (with health check rollback)

```



### False Positive SOP



```markdown

# False Positive Handling SOP



## Step 1: Verify it's a false positive

- Check CVE details in NVD

- Check if affected code path is reachable

- Ask security team for confirmation



## Step 2: Document

- Create ticket: "False positive: CVE-XXXX in &lt;component&gt;"

- Include: why it's false positive, evidence, approver



## Step 3: Suppress

- Add to `.trivyignore` or equivalent:

  ```

  # CVE-XXXX: False positive because <reason>

  # Reviewed by: <name>, Date: <date>, Ticket: <ticket>

  CVE-XXXX

  ```



## Step 4: Review

- False positive suppressions reviewed monthly

- Remove suppressions when CVE is patched upstream

- Track count of active suppressions per service

```



### DORA Dashboard Design



```

┌───────────────────────────────────────────────────────┐

│                  DORA Metrics Dashboard                │

├────────────────────────┬──────────────────────────────┤

│ Panel 1:               │ Panel 2:                      │

│ Deployment Frequency   │ Lead Time for Changes         │

│ (deploys/day, 30d avg) │ (commit→prod, p50/p95)        │

│ Source: CI/CD API      │ Source: Git + CI/CD API        │

│ Target: > 3/day        │ Target: < 1 hour              │

├────────────────────────┼──────────────────────────────┤

│ Panel 3:               │ Panel 4:                      │

│ Change Failure Rate    │ MTTR                          │

│ (failed/total, 30d)    │ (incident→resolved, avg)      │

│ Source: CI/CD + PD     │ Source: PagerDuty/OpsGenie    │

│ Target: < 5%           │ Target: < 1 hour              │

├────────────────────────┼──────────────────────────────┤

│ Panel 5:               │ Panel 6:                      │

│ Pipeline Duration      │ Quality Gate Pass Rate        │

│ (p50/p95, per service) │ (pass/total per gate type)    │

│ Source: CI/CD API      │ Source: CI/CD API              │

│ Target: < 10 min       │ Target: > 95%                 │

├────────────────────────┼──────────────────────────────┤

│ Panel 7:               │ Panel 8:                      │

│ Flaky Test Tracker     │ Top Slow Pipelines            │

│ (tests failing >10%    │ (top 10 by duration)          │

│  of runs, 7d window)   │ Source: CI/CD API              │

│ Source: Test reports    │ Action: Investigate & fix      │

└────────────────────────┴──────────────────────────────┘

```



</details>



---



## Exercise 3: Pipeline Architecture for Monorepo (Hard)



### Context



Công ty bạn đang chuyển từ 8 polyrepos sang 1 monorepo để cải thiện developer experience. Hiện tại mỗi repo có pipeline riêng. Thách thức: monorepo pipeline phải **chỉ build services bị thay đổi**, không build toàn bộ.



Monorepo structure:

```

monorepo/

├── services/

│   ├── payment/

│   ├── user/

│   ├── product/

│   ├── notification/

│   ├── analytics/

│   ├── gateway/

│   ├── auth/

│   └── search/

├── libs/

│   ├── common/     (shared by all services)

│   ├── db/         (shared by payment, user, product)

│   └── cache/      (shared by product, search)

├── infra/

│   ├── terraform/

│   └── k8s/

└── tools/

    ├── scripts/

    └── ci/

```



### Yêu cầu



1. **Thiết kế dependency graph** giữa services và libs.

2. **Viết affected services detection algorithm**: khi file trong `libs/db/` thay đổi → build `payment`, `user`, `product`.

3. **Thiết kế pipeline architecture** cho monorepo:

   - Path-based triggers.

   - Shared pipeline stages (reusable).

   - Parallel builds cho affected services.

   - Dependency-aware build ordering.

4. **Viết GitHub Actions workflow** (pseudo/real):

   - Detect changed paths.

   - Determine affected services.

   - Build only affected services in parallel.

5. **Tính toán cost/time savings** so với build-everything approach.

6. **Thiết kế caching strategy** cho monorepo.



### Expected Outcome



- Dependency graph (diagram).

- Affected services detection logic.

- GitHub Actions workflow file (working hoặc pseudo-code).

- Cost/time analysis.

- Caching strategy document.



### Hints



- `git diff --name-only HEAD~1` để lấy changed files.

- Dùng `paths` filter trong GitHub Actions workflow.

- `needs` keyword cho dependency ordering.

- Matrix strategy cho parallel builds.

- Consider: thay đổi `libs/common/` → phải rebuild TẤT CẢ services.



### Acceptance Criteria



- [ ] Dependency graph chính xác (service ↔ lib relationships).

- [ ] Affected detection logic handles: direct changes, lib changes, infra changes.

- [ ] GitHub Actions workflow có path filters + matrix builds.

- [ ] Cost analysis so sánh build-all vs build-affected.

- [ ] Caching strategy cho node_modules, Go modules, Docker layers.

- [ ] Edge cases handled: libs/common change, infra change, CI config change.



### Bonus Challenge



Implement affected services detection bằng script thật (Bash hoặc Python) và test với mock git diff output.



<details>

<summary>Solution</summary>



### 1. Dependency Graph



```

services/payment ──────► libs/common

                  ──────► libs/db



services/user ─────────► libs/common

                  ──────► libs/db



services/product ──────► libs/common

                  ──────► libs/db

                  ──────► libs/cache



services/search ───────► libs/common

                  ──────► libs/cache



services/notification ─► libs/common

services/analytics ────► libs/common

services/gateway ──────► libs/common

services/auth ─────────► libs/common

```



### 2. Affected Services Detection Script



```bash

#!/usr/bin/env bash

# detect-affected.sh

set -euo pipefail



# Dependency map: service → libs it depends on

declare -A DEPS

DEPS[payment]="common db"

DEPS[user]="common db"

DEPS[product]="common db cache"

DEPS[search]="common cache"

DEPS[notification]="common"

DEPS[analytics]="common"

DEPS[gateway]="common"

DEPS[auth]="common"



ALL_SERVICES="payment user product notification analytics gateway auth search"



# Get changed files

CHANGED_FILES=$(git diff --name-only HEAD~1 2>/dev/null || echo "")



if [ -z "$CHANGED_FILES" ]; then

    echo "No changes detected"

    exit 0

fi



# Detect affected services

AFFECTED=""



# Rule 1: Direct service changes

for svc in $ALL_SERVICES; do

    if echo "$CHANGED_FILES" | grep -q "^services/$svc/"; then

        AFFECTED="$AFFECTED $svc"

    fi

done



# Rule 2: Lib changes → affected dependents

CHANGED_LIBS=""

for lib in common db cache; do

    if echo "$CHANGED_FILES" | grep -q "^libs/$lib/"; then

        CHANGED_LIBS="$CHANGED_LIBS $lib"

    fi

done



if [ -n "$CHANGED_LIBS" ]; then

    for svc in $ALL_SERVICES; do

        for lib in $CHANGED_LIBS; do

            if echo "${DEPS[$svc]}" | grep -qw "$lib"; then

                AFFECTED="$AFFECTED $svc"

            fi

        done

    done

fi



# Rule 3: CI/infra changes → rebuild all

if echo "$CHANGED_FILES" | grep -qE "^(tools/ci/|\.github/|infra/)"; then

    AFFECTED="$ALL_SERVICES"

fi



# Deduplicate

AFFECTED=$(echo "$AFFECTED" | tr ' ' '\n' | sort -u | tr '\n' ' ')



echo "Changed files:"

echo "$CHANGED_FILES" | head -20

echo ""

echo "Affected services: $AFFECTED"



# Output for GitHub Actions matrix

MATRIX=$(echo "$AFFECTED" | tr ' ' '\n' | grep -v '^$' | jq -Rsc 'split("\n") | map(select(. != ""))')

echo "matrix=$MATRIX" >> "${GITHUB_OUTPUT:-/dev/stdout}"

```



### 3. GitHub Actions Workflow



```yaml

name: Monorepo CI



on:

  push:

    branches: [main]

  pull_request:

    branches: [main]



jobs:

  detect:

    runs-on: ubuntu-latest

    outputs:

      services: ${{ steps.detect.outputs.matrix }}

      has_changes: ${{ steps.detect.outputs.has_changes }}

    steps:

      - uses: actions/checkout@v6

        with:

          fetch-depth: 2

      - id: detect

        run: |

          chmod +x tools/ci/detect-affected.sh

          RESULT=$(./tools/ci/detect-affected.sh)

          echo "$RESULT"



  build:

    needs: detect

    if: needs.detect.outputs.has_changes == 'true'

    runs-on: ubuntu-latest

    strategy:

      fail-fast: false

      matrix:

        service: ${{ fromJson(needs.detect.outputs.services) }}

    steps:

      - uses: actions/checkout@v6



      - name: Cache dependencies

        uses: actions/cache@v4

        with:

          path: |

            ~/.cache/go-build

            ~/go/pkg/mod

            node_modules

          key: ${{ matrix.service }}-${{ hashFiles('**/go.sum', '**/package-lock.json') }}



      - name: Lint

        run: make -C services/${{ matrix.service }} lint



      - name: Test

        run: make -C services/${{ matrix.service }} test



      - name: Build

        run: make -C services/${{ matrix.service }} build



      - name: Scan

        uses: aquasecurity/trivy-action@v0.36.0

        with:

          image-ref: ${{ matrix.service }}:${{ github.sha }}

          exit-code: 1

          severity: CRITICAL,HIGH



      - name: Push

        if: github.ref == 'refs/heads/main'

        run: |

          docker tag ${{ matrix.service }}:${{ github.sha }} \

            registry.example.com/${{ matrix.service }}:${{ github.sha }}

          docker push registry.example.com/${{ matrix.service }}:${{ github.sha }}

```



### 4. Cost/Time Analysis



```

Build-all approach:

  8 services × 10 min/service = 80 min (sequential)

  With parallelism (8 runners): 10 min wall time

  Cost: 8 × 10 min × $0.008/min = $0.64 per run

  20 runs/day = $12.80/day = $384/month



Build-affected approach:

  Average 2.5 services affected per change

  2.5 services × 10 min = 25 min (sequential)

  With parallelism: 10 min wall time

  Cost: 2.5 × 10 min × $0.008/min = $0.20 per run

  20 runs/day = $4.00/day = $120/month



Savings: $264/month (69% reduction)

Time savings: 5.5 services × 10 min × 20 runs = 1100 runner-minutes/day saved

```



### 5. Caching Strategy



```yaml

# Layer 1: Language-level dependency caching

- Go modules: ~/go/pkg/mod (key: go.sum hash)

- Node modules: node_modules (key: package-lock.json hash)

- Python: ~/.cache/pip (key: requirements.txt hash)



# Layer 2: Build cache

- Go: ~/.cache/go-build

- Docker: buildx cache (type=gha)



# Layer 3: Docker layer caching

- uses: docker/build-push-action@v5

  with:

    cache-from: type=gha

    cache-to: type=gha,mode=max



# Layer 4: Test result caching

- Skip unchanged test suites (hash source files)

- Cache test fixtures/data



# Expected improvement:

# Without caching: ~10 min/service

# With caching: ~3-4 min/service (60-70% faster)

```



</details>



---



## Tổng kết thời lượng



| Exercise | Thời gian | Skill level |

|----------|-----------|-------------|

| Exercise 1: Pipeline Stage Walkthrough | ~30 phút | Easy |

| Exercise 2: Quality Gate Design | ~40 phút | Medium |

| Exercise 3: Monorepo Pipeline Architecture | ~50 phút | Hard |

| **Tổng** | **~2 giờ** | |

