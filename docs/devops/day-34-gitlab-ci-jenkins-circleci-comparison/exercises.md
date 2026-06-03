# Day 34: GitLab CI, Jenkins, CircleCI Comparison — Exercises

## Exercise 1: Pipeline Syntax Translation (Easy)

### Context

Team bạn đang đánh giá chuyển từ Jenkins sang GitHub Actions. Bước đầu tiên là dịch một Jenkinsfile sang GitHub Actions workflow để hiểu sự khác biệt syntax.

### Yêu cầu

1. Đọc Jenkinsfile sau và hiểu từng stage.
2. Dịch sang GitHub Actions workflow tương đương.
3. Dịch sang GitLab CI pipeline tương đương.
4. Ghi lại 5 điểm khác biệt quan trọng nhất giữa 3 cú pháp.

**Jenkinsfile gốc**:

```groovy
pipeline {
    agent any
    environment {
        APP = 'payment-api'
        REGISTRY = 'registry.example.com'
    }
    stages {
        stage('Lint') {
            steps {
                sh 'go vet ./...'
            }
        }
        stage('Test') {
            steps {
                sh 'go test -v -race -coverprofile=coverage.out ./...'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'coverage.out'
                }
            }
        }
        stage('Build') {
            when { branch 'main' }
            steps {
                sh "docker build -t ${REGISTRY}/${APP}:${GIT_COMMIT.take(7)} ."
                sh "docker push ${REGISTRY}/${APP}:${GIT_COMMIT.take(7)}"
            }
        }
        stage('Deploy') {
            when { branch 'main' }
            input { message 'Deploy to production?' }
            steps {
                sh "kubectl set image deployment/${APP} ${APP}=${REGISTRY}/${APP}:${GIT_COMMIT.take(7)}"
            }
        }
    }
    post {
        failure {
            slackSend channel: '#alerts', message: "Build failed: ${JOB_NAME}"
        }
    }
}
```

### Expected Outcome

- GitHub Actions workflow YAML file.
- GitLab CI YAML file.
- 5 điểm khác biệt quan trọng.

### Hints

- Jenkins `when { branch 'main' }` → GitHub Actions `if: github.ref == 'refs/heads/main'`.
- Jenkins `input` → GitHub Actions `environment` with required reviewers.
- Jenkins `post.failure` → GitHub Actions `if: failure()`.
- Jenkins `archiveArtifacts` → GitHub Actions `actions/upload-artifact`.

### Acceptance Criteria

- [ ] GitHub Actions YAML valid và tương đương Jenkinsfile.
- [ ] GitLab CI YAML valid và tương đương Jenkinsfile.
- [ ] 5 syntax differences documented.
- [ ] Mỗi tool's approach được giải thích ngắn gọn.

### Bonus Challenge

Thêm CircleCI config.yml tương đương — so sánh cả 4 syntax.

<details>
<summary>Solution</summary>

### GitHub Actions

```yaml
name: Payment API CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  APP: payment-api
  REGISTRY: registry.example.com

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          cache: true
      - run: go vet ./...

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          cache: true
      - run: go test -v -race -coverprofile=coverage.out ./...
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage
          path: coverage.out

  build:
    needs: [lint, test]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - run: |
          TAG=$(echo ${{ github.sha }} | cut -c1-7)
          docker build -t $REGISTRY/$APP:$TAG .
          docker push $REGISTRY/$APP:$TAG

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    steps:
      - run: |
          TAG=$(echo ${{ github.sha }} | cut -c1-7)
          kubectl set image deployment/$APP $APP=$REGISTRY/$APP:$TAG

  notify:
    needs: [lint, test, build]
    if: failure()
    runs-on: ubuntu-latest
    steps:
      - uses: slackapi/slack-github-action@v1
        with:
          channel-id: '#alerts'
          slack-message: "Build failed: ${{ github.workflow }}"
```

### GitLab CI

```yaml
stages:
  - lint
  - test
  - build
  - deploy

variables:
  APP: payment-api
  REGISTRY: registry.example.com

lint:
  stage: lint
  image: golang:1.22
  script:
    - go vet ./...

test:
  stage: test
  image: golang:1.22
  script:
    - go test -v -race -coverprofile=coverage.out ./...
  artifacts:
    paths:
      - coverage.out
    when: always

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $REGISTRY/$APP:$CI_COMMIT_SHORT_SHA .
    - docker push $REGISTRY/$APP:$CI_COMMIT_SHORT_SHA
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

deploy:
  stage: deploy
  script:
    - kubectl set image deployment/$APP $APP=$REGISTRY/$APP:$CI_COMMIT_SHORT_SHA
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual  # Manual approval

.notify_failure:
  after_script:
    - 'curl -X POST -H "Content-type: application/json" --data "{\"text\":\"Build failed: $CI_JOB_NAME\"}" $SLACK_WEBHOOK'
```

### 5 Key Differences

| # | Aspect | Jenkins | GitHub Actions | GitLab CI |
|---|--------|---------|---------------|-----------|
| 1 | **Language** | Groovy (programming lang) | YAML (declarative) | YAML (declarative) |
| 2 | **Manual approval** | `input { message }` | `environment` + protection rules | `when: manual` |
| 3 | **Branch filter** | `when { branch 'main' }` | `if: github.ref == '...'` | `rules: - if: $CI_COMMIT_BRANCH` |
| 4 | **Artifacts** | `archiveArtifacts` | `actions/upload-artifact` | `artifacts: paths:` |
| 5 | **Failure notification** | `post { failure { } }` | `if: failure()` in separate job | `after_script` hoặc webhook |

</details>

---

## Exercise 2: CI/CD Tool Selection for Your Team (Medium)

### Context

Bạn là tech lead được CTO giao nhiệm vụ chọn CI/CD tool cho company mới (startup → mid-size transition). Company profile:

- 25 engineers, growing to 50 in 12 months.
- 10 microservices (Go, TypeScript).
- Code on GitHub.
- AWS infrastructure.
- Current: no CI/CD — manual deploy bằng scripts.
- Budget: $500/month max cho CI/CD.
- Compliance: PCI DSS trong 18 tháng (payment processing).

### Yêu cầu

1. **Scoring matrix**: Score 4 tools (GitHub Actions, GitLab CI, Jenkins, CircleCI) trên 12+ tiêu chí.
2. **Weighted scoring**: Assign weights dựa trên company priorities.
3. **Cost projection**: 12-month cost cho mỗi tool.
4. **Risk assessment**: Top 3 risks cho mỗi tool.
5. **Recommendation report**: 1-page executive summary.
6. **Migration timeline**: Phased plan.

### Expected Outcome

- Scoring matrix với weighted scores.
- Cost analysis document.
- 1-page recommendation.
- Migration timeline.

### Hints

- PCI DSS requirement → compliance features quan trọng.
- GitHub integration → GitHub Actions có advantage.
- No ops team → maintenance cost quan trọng.
- Growing team → scalability matters.

### Acceptance Criteria

- [ ] Scoring matrix ≥ 12 tiêu chí, weighted.
- [ ] Cost projection cho 12 months cho cả 4 tools.
- [ ] Risk assessment (3 risks mỗi tool).
- [ ] Recommendation rõ ràng với justification.
- [ ] Migration plan phased (3-6 months).
- [ ] Trade-offs giữa top 2 choices được phân tích.

### Bonus Challenge

Viết thêm "What if" analysis: nếu company chuyển sang GitLab trong 2 năm, recommendation có thay đổi không?

<details>
<summary>Solution</summary>

### Scoring Matrix

| Tiêu chí | Weight | GH Actions | GitLab CI | Jenkins | CircleCI |
|----------|--------|-----------|-----------|---------|----------|
| GitHub integration | 10 | 5 | 3 | 3 | 4 |
| Setup speed | 9 | 5 | 3 | 1 | 4 |
| Low maintenance | 9 | 5 | 3 | 1 | 5 |
| PCI compliance path | 8 | 4 | 5 | 3 | 4 |
| Cost < $500/mo | 7 | 5 | 3 | 4 | 4 |
| Secret management | 8 | 5 | 4 | 3 | 4 |
| Docker support | 7 | 4 | 4 | 3 | 5 |
| OIDC (AWS) | 7 | 5 | 4 | 2 | 4 |
| Reusable pipelines | 6 | 5 | 4 | 4 | 4 |
| Env protection | 8 | 5 | 5 | 3 | 4 |
| Community/ecosystem | 5 | 5 | 4 | 5 | 3 |
| Scalability (50 devs) | 6 | 5 | 4 | 3 | 4 |
| **Weighted Score** | | **4.7** | **3.8** | **2.6** | **4.1** |

### Cost Projection (12 months)

Các số dưới đây là assumption để luyện cách so sánh TCO, không phải quote giá. Khi áp dụng cho công ty thật, thay bằng pricing hiện hành từ vendor và cost nội bộ của runner/admin.

| Tool | Month 1-6 (25 devs) | Month 7-12 (40 devs) | Total/year |
|------|---------------------|---------------------|-----------|
| GitHub Actions | ~$200/mo | ~$350/mo | ~$3,300 |
| GitLab CI Premium | $570/mo (19×30) | $912/mo | ~$8,892 |
| Jenkins | ~$1,200/mo (infra+admin) | ~$1,500/mo | ~$16,200 |
| CircleCI | ~$250/mo | ~$400/mo | ~$3,900 |

### Recommendation

**GitHub Actions** — best fit cho company profile.

**Justification**:
1. Native GitHub integration = zero friction
2. Lowest TCO trong assumption của bài tập ($3,300/year vs $16,200 Jenkins)
3. Zero maintenance → no need to hire DevOps for CI
4. OIDC for AWS = strong security
5. PCI DSS: GitHub Enterprise has SOC 2 Type II (building block for PCI)

**Runner-up**: CircleCI — slightly more expensive nhưng better Docker experience và SSH debugging.

### Migration Plan

```
Month 1: Setup + pilot (2 non-critical services)
Month 2: Migrate 4 more services, establish patterns
Month 3: Migrate remaining 4 services
Month 4: Buffer + optimization + documentation
Month 5: Training for all engineers
Month 6: Decommission manual deploy scripts
```

</details>

---

## Exercise 3: Multi-tool Architecture Design (Hard)

### Context

Bạn là Platform Engineer tại một enterprise (200 engineers, 50 services). Company quyết định dùng **hybrid approach**: Jenkins cho legacy services + GitHub Actions cho new services. Bạn cần thiết kế architecture cho cả hai cùng tồn tại.

### Yêu cầu

1. **Thiết kế hybrid CI/CD architecture**:
   - Jenkins cho 30 legacy services (Java, .NET).
   - GitHub Actions cho 20 new services (Go, TypeScript).
   - Shared artifact registry (Harbor).
   - Shared deployment target (ArgoCD/GitOps).
   - Unified monitoring dashboard.

2. **Viết architecture diagram** (text/mermaid).

3. **Thiết kế shared components**:
   - Shared Docker base images.
   - Shared security scanning pipeline.
   - Shared notification system.
   - Shared artifact naming convention.

4. **Viết standardization document**:
   - Image tag convention.
   - Pipeline stage naming.
   - Secret management approach.
   - Deployment trigger mechanism.

5. **Thiết kế migration path**: Jenkins → GitHub Actions cho legacy services (phased, 18 months).

6. **Risk analysis**: top 5 risks cho hybrid approach.

### Expected Outcome

- Architecture diagram.
- Shared components design.
- Standardization document.
- Migration roadmap (18 months).
- Risk register.

### Acceptance Criteria

- [ ] Architecture diagram shows both CI tools → shared infra.
- [ ] Shared components designed (registry, scanning, notification).
- [ ] Standardization doc covers: tags, stages, secrets, deploys.
- [ ] Migration roadmap with phases and milestones.
- [ ] 5 risks identified with mitigations.
- [ ] Cost comparison: hybrid vs full migration.

### Bonus Challenge

Thiết kế unified CI/CD dashboard (Grafana) aggregating metrics từ cả Jenkins và GitHub Actions.

<details>
<summary>Solution</summary>

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                   Developer Workflow                      │
│                                                           │
│  ┌─────────────┐              ┌──────────────┐           │
│  │ Legacy Repos │              │ New Repos     │           │
│  │ (GitHub)     │              │ (GitHub)      │           │
│  └──────┬──────┘              └──────┬───────┘           │
│         │                            │                    │
│         ▼                            ▼                    │
│  ┌─────────────┐              ┌──────────────┐           │
│  │   Jenkins    │              │ GitHub Actions│           │
│  │  (Self-host) │              │  (Cloud)      │           │
│  │  30 services │              │  20 services  │           │
│  └──────┬──────┘              └──────┬───────┘           │
│         │                            │                    │
│         ▼                            ▼                    │
│  ┌────────────────────────────────────────────┐          │
│  │          Shared Infrastructure              │          │
│  ├─────────────┬──────────────┬───────────────┤          │
│  │   Harbor     │   Trivy      │  SonarQube    │          │
│  │  (Registry)  │ (Scanning)   │ (Quality)     │          │
│  └──────┬──────┴──────┬───────┴───────┬──────┘          │
│         │             │               │                   │
│         ▼             ▼               ▼                   │
│  ┌──────────────┐  ┌──────────┐  ┌──────────┐           │
│  │ GitOps Repo   │  │ Grafana  │  │  Slack   │           │
│  │ (Config)      │  │(Metrics) │  │(Notify)  │           │
│  └──────┬───────┘  └──────────┘  └──────────┘           │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────┐                                        │
│  │   ArgoCD      │                                        │
│  │ (Deployment)  │                                        │
│  └──────┬───────┘                                        │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────┐                                        │
│  │  Kubernetes   │                                        │
│  │  Clusters     │                                        │
│  └──────────────┘                                        │
└──────────────────────────────────────────────────────────┘
```

### Standardization Document

```yaml
# Image Tag Convention (both tools):
# Format: <registry>/<team>/<service>:<git-sha-7>
# Example: harbor.internal/payments/payment-api:a1b2c3d
# Release: harbor.internal/payments/payment-api:v1.2.3

# Pipeline Stage Names (standardized):
stages:
  - lint        # Code quality check
  - test        # Unit + integration tests
  - build       # Compile + Docker build
  - scan        # Security scanning (Trivy + SonarQube)
  - package     # Push to Harbor
  - deploy-dev  # Auto deploy to dev
  - deploy-stg  # Auto deploy to staging
  - deploy-prd  # Manual/auto deploy to production
  - verify      # Post-deploy health check

# Secret Management:
# - Both tools → fetch from AWS Secrets Manager via OIDC
# - Jenkins: AWS Credentials plugin + OIDC
# - GitHub Actions: aws-actions/configure-aws-credentials (OIDC)
# - No static credentials anywhere

# Deployment Trigger:
# Both tools update GitOps config repo → ArgoCD syncs
# Pattern: CI builds image → pushes to Harbor → updates image tag in config repo
```

### Migration Roadmap (18 months)

| Phase | Timeline | Scope | Risk |
|-------|----------|-------|------|
| 1. Foundation | Month 1-3 | Setup shared infra, standards, 2 pilot services | Low |
| 2. Quick wins | Month 4-6 | Migrate 8 simpler services (stateless Go/TS) | Low |
| 3. Medium complexity | Month 7-10 | Migrate 10 services (Java with Gradle/Maven) | Medium |
| 4. Complex services | Month 11-14 | Migrate 8 complex services (.NET, legacy) | High |
| 5. Final cleanup | Month 15-18 | Last 2 services, decommission Jenkins | Medium |

### Risk Register

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|-----------|
| 1 | Dual maintenance overhead | High | High | Automate shared components, single team owns both |
| 2 | Inconsistent security posture | High | Medium | Shared scanning pipeline, unified policy |
| 3 | Knowledge fragmentation | Medium | High | Standards doc, training, rotation |
| 4 | Jenkins vulnerability during migration | High | Medium | Minimal Jenkins plugins, security patches |
| 5 | Migration delays due to legacy complexity | Medium | High | Buffer time, phased approach, acceptance criteria per service |

</details>

---

## Tổng kết thời lượng

| Exercise | Thời gian | Skill level |
|----------|-----------|-------------|
| Exercise 1: Pipeline Syntax Translation | ~30 phút | Easy |
| Exercise 2: Tool Selection for Team | ~40 phút | Medium |
| Exercise 3: Multi-tool Architecture | ~50 phút | Hard |
| **Tổng** | **~2 giờ** | |

