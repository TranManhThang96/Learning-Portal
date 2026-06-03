# Day 34: GitLab CI, Jenkins, CircleCI Comparison

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Hiểu kiến trúc và điểm mạnh/yếu** của GitLab CI, Jenkins, và CircleCI — đủ để đánh giá cho team mình.
2. **So sánh được 4 CI/CD tools** (bao gồm GitHub Actions từ Day 33) theo 15+ tiêu chí thực tế.
3. **Xây dựng được decision framework** chọn CI/CD tool phù hợp cho 3 loại tổ chức: startup, mid-size, enterprise.
4. **Nhận diện được risks** của mỗi tool: vendor lock-in, plugin ecosystem, security, cost.
5. **Viết được comparison matrix** có thể trình bày cho leadership để ra quyết định.

---

## 2. Bối cảnh & Động lực

### Tại sao cần so sánh CI/CD tools?

Chọn CI/CD tool là quyết định có impact dài hạn:
- **Migration cost**: Chuyển CI/CD tool cho 50 services mất 3-6 tháng.
- **Team productivity**: Tool phù hợp = developer happy, tool tệ = bottleneck.
- **Cost**: Từ $0 (Jenkins self-hosted) đến $50K+/year (enterprise tiers).
- **Security**: CI/CD có access tới code, secrets, infrastructure.

### Không có "best tool" — chỉ có "best fit"

Mỗi tool có trade-offs riêng. Quyết định phụ thuộc vào: team size, existing stack, security requirements, budget, và operational maturity.

---

## 3. Kiến thức nền tảng

### 3.1 GitLab CI

**Architecture**: Tích hợp trực tiếp vào GitLab platform.

```
GitLab Instance
├── GitLab Server (Rails app)
│   ├── Sidekiq (background jobs)
│   ├── Pipeline engine
│   └── Container Registry
├── GitLab Runner (executor)
│   ├── Shell executor
│   ├── Docker executor
│   ├── Kubernetes executor
│   └── Custom executor
└── PostgreSQL + Redis + Object Storage
```

**Điểm mạnh**:
- All-in-one platform: code, CI/CD, registry, monitoring, security scanning.
- `.gitlab-ci.yml` — clean YAML syntax.
- Auto DevOps: zero-config CI/CD cho common patterns.
- Built-in container registry và package registry.
- DAG (Directed Acyclic Graph) pipeline.
- Multi-project pipelines, parent-child pipelines.
- Environments và review apps built-in.

**Điểm yếu**:
- Self-hosted GitLab nặng (cần 8GB+ RAM).
- UI chậm hơn GitHub.
- Marketplace nhỏ hơn GitHub Actions.
- License model phức tạp (Free/Premium/Ultimate).

**Pipeline example**:

```yaml
# .gitlab-ci.yml
stages:
  - lint
  - test
  - build
  - scan
  - deploy

variables:
  GO_VERSION: "1.22"

lint:
  stage: lint
  image: golang:${GO_VERSION}
  script:
    - test -z "$(gofmt -l .)"
    - go vet ./...
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

test:
  stage: test
  image: golang:${GO_VERSION}
  script:
    - go test -v -race -coverprofile=coverage.out ./...
    - go tool cover -func=coverage.out
  coverage: '/total:\s+\(statements\)\s+(\d+\.\d+)%/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.out

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

container_scan:
  stage: scan
  image:
    name: aquasec/trivy
    entrypoint: [""]
  script:
    - trivy image --exit-code 1 --severity CRITICAL,HIGH $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA

deploy_staging:
  stage: deploy
  environment:
    name: staging
    url: https://staging.example.com
  script:
    - echo "Deploy to staging"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

deploy_production:
  stage: deploy
  environment:
    name: production
    url: https://example.com
  script:
    - echo "Deploy to production"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual  # Manual approval
```

### 3.2 Jenkins

**Architecture**: Distributed build system.

```
Jenkins Controller (Master)
├── Web UI
├── Job scheduler
├── Plugin manager
├── Configuration (XML/JCasC)
└── Agents
    ├── Permanent Agent (dedicated VM)
    ├── Cloud Agent (Docker/K8s)
    └── SSH Agent (remote machine)
```

**Điểm mạnh**:
- **Free và open-source** (MIT license).
- **1800+ plugins** — kết nối với mọi thứ.
- **Maximum flexibility** — có thể customize mọi aspect.
- **Self-hosted** — full control, no vendor lock-in.
- Mature ecosystem, rất lớn community.
- Pipeline as Code (Jenkinsfile) với Groovy — full programming language.
- Distributed builds trên nhiều agents.

**Điểm yếu**:
- **Maintenance burden** — upgrade, security patches, plugin conflicts.
- **Plugin hell** — dependency conflicts, abandoned plugins, security vulnerabilities.
- **Groovy learning curve** — Declarative ok, Scripted phức tạp.
- **UI outdated** — cải thiện với Blue Ocean (nhưng Blue Ocean đã deprecated).
- **No built-in secrets management** — cần Credentials plugin.
- **Single point of failure** nếu không HA.

**Pipeline example**:

```groovy
// Jenkinsfile (Declarative Pipeline)
pipeline {
    agent any

    environment {
        GO_VERSION = '1.22'
        REGISTRY = 'registry.example.com'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Lint') {
            agent {
                docker { image "golang:${GO_VERSION}" }
            }
            steps {
                sh 'gofmt -l . | tee /dev/stderr | wc -l | xargs test 0 -eq'
                sh 'go vet ./...'
            }
        }

        stage('Test') {
            agent {
                docker { image "golang:${GO_VERSION}" }
            }
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
            steps {
                sh "docker build -t ${REGISTRY}/myservice:${env.GIT_COMMIT.take(7)} ."
            }
        }

        stage('Scan') {
            steps {
                sh "trivy image --exit-code 1 --severity CRITICAL,HIGH ${REGISTRY}/myservice:${env.GIT_COMMIT.take(7)}"
            }
        }

        stage('Deploy Staging') {
            when {
                branch 'main'
            }
            steps {
                sh "echo 'Deploy to staging'"
            }
        }

        stage('Deploy Production') {
            when {
                branch 'main'
            }
            input {
                message 'Deploy to production?'
                ok 'Deploy'
            }
            steps {
                sh "echo 'Deploy to production'"
            }
        }
    }

    post {
        failure {
            slackSend channel: '#ci-alerts', message: "Build failed: ${env.JOB_NAME}"
        }
    }
}
```

### 3.3 CircleCI

**Architecture**: Cloud-native CI/CD platform.

```
CircleCI Cloud
├── Pipeline Engine
├── Workflow Orchestrator
├── Docker Layer Cache
├── Insights Dashboard
└── Executors
    ├── Docker executor (default)
    ├── Machine executor (full VM)
    ├── macOS executor
    └── Self-hosted runner
```

**Điểm mạnh**:
- **Docker-first** — native Docker support, Docker Layer Cache (DLC).
- **Orbs** — reusable packages (like GitHub Actions marketplace).
- **Insights dashboard** — built-in analytics (pipeline duration, flaky tests).
- **Resource classes** — granular runner sizing.
- **SSH debugging** — SSH vào running job để debug.
- **Test splitting** — tự chia tests qua multiple containers.
- Nhanh: parallel execution + DLC.

**Điểm yếu**:
- **Git platform agnostic** — tách biệt từ code host (thêm integration step).
- **Cost** — có thể đắt ở scale lớn.
- **Vendor lock-in** — Orbs, config syntax khác biệt.
- **Limited self-hosted** — primarily cloud.
- **Config complexity** — YAML nesting sâu.

**Pipeline example**:

```yaml
# .circleci/config.yml
version: 2.1

orbs:
  go: circleci/go@1.9
  docker: circleci/docker@2.4

executors:
  go-executor:
    docker:
      - image: cimg/go:1.22
    resource_class: medium

jobs:
  lint:
    executor: go-executor
    steps:
      - checkout
      - go/load-cache
      - run: |
          test -z "$(gofmt -l .)"
          go vet ./...
      - go/save-cache

  test:
    executor: go-executor
    parallelism: 2
    steps:
      - checkout
      - go/load-cache
      - run:
          name: Run tests
          command: |
            TESTS=$(circleci tests glob "**/*_test.go" | circleci tests split)
            go test -v -race -coverprofile=coverage.out $TESTS
      - store_artifacts:
          path: coverage.out
      - go/save-cache

  build:
    executor: go-executor
    steps:
      - checkout
      - setup_remote_docker:
          docker_layer_caching: true
      - run: docker build -t myservice:$CIRCLE_SHA1 .
      - run: docker push registry/myservice:$CIRCLE_SHA1

  deploy:
    executor: go-executor
    steps:
      - run: echo "Deploy to production"

workflows:
  build-and-deploy:
    jobs:
      - lint
      - test
      - build:
          requires: [lint, test]
          filters:
            branches:
              only: main
      - hold:
          type: approval
          requires: [build]
      - deploy:
          requires: [hold]
```

---

## 4. Deep Dive

### 4.1 Comprehensive Comparison Matrix

| Tiêu chí | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|----------|---------------|-----------|---------|----------|
| **Type** | Platform-integrated | Platform-integrated | Standalone | Standalone |
| **Pipeline syntax** | YAML | YAML | Groovy (Jenkinsfile) | YAML |
| **Learning curve** | Low | Low-Medium | High | Medium |
| **Setup time** | 0 (built-in) | 0 (built-in) | Hours-days | Minutes |
| **Hosting** | Cloud + self-hosted | Cloud + self-hosted | Self-hosted only | Cloud + self-hosted |
| **Free tier** | 2000 min/month | Compute minutes quota theo plan | ∞ (self-hosted) | Up to 6,000 build minutes / 30,000 credits |
| **Enterprise cost** | $$$ | $$$ | Free + infra cost | $$$ |
| **Marketplace** | 20,000+ actions | Limited marketplace | 1800+ plugins | Orbs ecosystem |
| **Container support** | ✅ Native | ✅ Native + DinD | ✅ Plugin | ✅ Docker-first |
| **Matrix builds** | ✅ Native | ✅ parallel keyword | ✅ Matrix plugin | ✅ parallelism |
| **Reusable configs** | Reusable workflows | includes, extends | Shared libraries | Orbs |
| **Secrets** | ✅ Encrypted | ✅ Variables (masked) | ⚠️ Credentials plugin | ✅ Contexts |
| **OIDC** | ✅ Native | ✅ Native | ⚠️ Plugin | ✅ Native |
| **Environment protection** | ✅ Native | ✅ Native | ⚠️ Plugin | ✅ Approval jobs |
| **Built-in registry** | ✅ GHCR | ✅ Container + Package | ❌ | ❌ |
| **Built-in security scan** | ⚠️ CodeQL + Dependabot | ✅ SAST/DAST/SCA | ❌ | ❌ |
| **Built-in monitoring** | ⚠️ Basic insights | ✅ CI/CD analytics | ❌ | ✅ Insights |
| **SSH debugging** | ❌ | ❌ | ✅ Agent | ✅ SSH rerun |
| **DAG pipeline** | ✅ needs keyword | ✅ needs keyword | ✅ Stage dependency | ✅ requires |
| **Caching** | actions/cache | Built-in cache | ⚠️ Stash/plugin | ✅ Built-in + DLC |
| **Auto-scaling runners** | ✅ (GitHub-hosted) | ✅ (Fleet scaling) | ⚠️ Manual/plugin | ✅ (cloud) |
| **Multi-project pipeline** | ⚠️ workflow_dispatch | ✅ Native | ✅ Upstream/downstream | ⚠️ API triggers |
| **Maintenance** | Zero (cloud) | Medium (self-hosted) | High | Low (cloud) |
| **Vendor lock-in** | Medium (GitHub) | Medium (GitLab) | Low (open-source) | High |
| **Community** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 4.2 Architecture Comparison

```
GitHub Actions:
  Code (GitHub) ──── Workflow (YAML) ──── Runner (GitHub/Self-hosted)
  [Tightly coupled with GitHub]

GitLab CI:
  Code (GitLab) ──── Pipeline (YAML) ──── Runner (GitLab/Self-hosted)
  [All-in-one platform]

Jenkins:
  Code (Any Git) ──── Pipeline (Groovy) ──── Agent (Self-managed)
  [Git-agnostic, requires infra management]

CircleCI:
  Code (GitHub/Bitbucket) ──── Config (YAML) ──── Executor (Cloud/Self-hosted)
  [Git platform agnostic]
```

### 4.3 Runner/Agent Model

| Aspect | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|--------|---------------|-----------|---------|----------|
| **Default** | GitHub-hosted | Shared runners | Phải tự cài agent | Cloud executors |
| **Self-hosted setup** | Binary install | Binary install | Java agent | Binary install |
| **Ephemeral** | ✅ (GitHub-hosted) | ✅ (configurable) | ⚠️ Manual | ✅ (Docker exec) |
| **Auto-scale** | ✅ Automatic | ✅ Fleet scaling | ⚠️ Plugin (K8s) | ✅ Automatic |
| **Isolation** | Container/VM | Container/VM/shell | Agent-based | Container/VM |
| **GPU/special HW** | ✅ Larger runners | ✅ Custom runners | ✅ Custom agents | ✅ Resource classes |

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Decision Framework

```mermaid
graph TB
    A[Chọn CI/CD Tool] --> B{Code ở đâu?}
    B -->|GitHub| C{Budget?}
    B -->|GitLab| D[GitLab CI]
    B -->|Multiple/Other| E{Cần flexibility?}
    
    C -->|Có budget| F[GitHub Actions]
    C -->|Minimize cost| G{Team size?}
    
    G -->|< 10| F
    G -->|> 10| H{Ops capacity?}
    
    H -->|Có ops team| I[Jenkins]
    H -->|Không| F
    
    E -->|Max flexibility| I
    E -->|Ease of use| J[CircleCI]
    
    D --> K[All-in-one platform]
    F --> L[Best ecosystem]
    I --> M[Max control, high maintenance]
    J --> N[Great DX, Docker-first]
```

### 5.2 Recommendation theo Context

| Context | Recommendation | Lý do |
|---------|---------------|------|
| **Startup (< 10 devs)** | GitHub Actions | Zero setup, free tier đủ, ecosystem lớn |
| **Startup dùng GitLab** | GitLab CI | Built-in, không thêm tool |
| **Mid-size (10-50 devs)** | GitHub Actions hoặc GitLab CI | Tùy Git platform, cả hai đều production-ready |
| **Enterprise (> 100 devs)** | GitLab CI Ultimate hoặc Jenkins | GitLab: all-in-one compliance. Jenkins: max flexibility |
| **Regulated industry** | GitLab CI Ultimate | Built-in security scanning, compliance features |
| **Multi-cloud/hybrid** | Jenkins | No vendor lock-in, connect mọi thứ |
| **Docker-heavy workflows** | CircleCI | Docker Layer Cache, Docker-first design |
| **Open-source projects** | GitHub Actions | Free unlimited, ecosystem, community |
| **Air-gapped/on-prem** | Jenkins hoặc GitLab Self-hosted | Chạy hoàn toàn offline |

### 5.3 Migration Considerations

| From → To | Effort | Key challenges |
|----------|--------|---------------|
| Jenkins → GitHub Actions | High | Groovy → YAML, plugins → actions, agent → runner |
| Jenkins → GitLab CI | High | Groovy → YAML, agent → runner, different concepts |
| GitHub Actions → GitLab CI | Medium | Similar YAML, different keywords, registry change |
| CircleCI → GitHub Actions | Medium | Orbs → actions, config differences |

**Migration strategy**:
1. Start with new services → new tool.
2. Run parallel (old + new) for 1-2 months.
3. Migrate service-by-service, critical services last.
4. Decommission old after 100% migration + 1 month buffer.

---

## 6. Performance & Scalability ⭐

### 6.1 Performance Comparison

| Metric | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|--------|---------------|-----------|---------|----------|
| **Cold start** | ~5-15s | ~10-30s | ~5-60s (agent startup) | ~5-10s |
| **Docker build (cached)** | ~30-60s (GHA cache) | ~20-40s (registry cache) | Varies (agent local) | ~10-20s (DLC) |
| **Parallel jobs** | Unlimited (cloud) | Depends on runners | Depends on agents | Depends on plan |
| **Queue time** | Low (cloud) | Depends on shared runners | Depends on agents | Low (cloud) |
| **Max concurrent** | Plan-dependent | Runner count | Agent count | Plan-dependent |

### 6.2 Cost at Scale

```
Scenario: 20 services, 30 builds/day, 10 min average

GitHub Actions:
  30 × 10 min × 22 days = 6,600 min/month
  Free: 2,000 min → Extra: 4,600 min × $0.006 = $27.60/month

GitLab CI (SaaS):
  Cost = max(0, usage - included_quota) × current compute-minute pack rate
  Lấy rate hiện hành từ GitLab Pricing page; không hard-code vào runbook.

Jenkins (Self-hosted):
  EC2 m5.xlarge (4 agents): 4 × $140/month = $560/month
  + Admin time: ~10 hours/month × $80/hour = $800/month
  Total: ~$1,360/month (but no per-minute cost)

CircleCI:
  Performance plan: $15/month + credits
  6,600 min × 10 credits/min = 66,000 credits
  30,000 included credits → Extra: 36,000 credits
  Paid credits are sold in vendor-defined blocks; estimate from current CircleCI pricing.
```

---

## 7. Security & Reliability Considerations

### 7.1 Security Comparison

| Security Feature | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|-----------------|---------------|-----------|---------|----------|
| Secret masking | ✅ Auto | ✅ Auto | ⚠️ Manual | ✅ Auto |
| OIDC | ✅ | ✅ | ⚠️ Plugin | ✅ |
| RBAC | ✅ Org-level | ✅ Project-level | ⚠️ Matrix auth plugin | ✅ Contexts |
| Audit logs | ✅ Enterprise | ✅ Premium+ | ⚠️ Plugin | ✅ Enterprise |
| Supply chain | Dependabot | Dependency scanning | ❌ | ❌ |
| SAST built-in | CodeQL | ✅ GitLab SAST | ❌ | ❌ |
| Compliance | SOC 2, GDPR | SOC 2, GDPR, FedRAMP | Self-managed | SOC 2, FedRAMP |

### 7.2 Jenkins-specific Security Risks

Jenkins đặc biệt vì self-hosted = your responsibility:

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Outdated plugins | CVEs, RCE | Regular updates, minimize plugins |
| Admin API exposed | Full system access | VPN, LDAP/OIDC auth, IP whitelist |
| Shared agents | Cross-job contamination | Ephemeral Docker/K8s agents |
| Groovy sandbox escape | Code execution on controller | Restrict scripted pipeline, use declarative |
| Credentials leak | Secret exposure | Credentials binding, folder isolation |

---

## 8. Hands-on Example

### Viết Comparison Matrix cho Tổ chức

Thay vì hands-on kỹ thuật (đã cover Day 33), bài này focus vào **decision-making exercise**.

#### Bước 1: Xác định requirements

```bash
cat > ~/cicd-comparison/requirements.md << 'EOF'
# CI/CD Tool Selection Requirements

## Organization Profile
- Type: Mid-size SaaS company
- Engineers: 35
- Services: 12 microservices
- Languages: Go (8), TypeScript (3), Python (1)
- Git platform: GitHub
- Cloud: AWS
- Current CI: Jenkins (3 years, 2 admins maintain)
- Pain points: Plugin conflicts, slow builds, maintenance overhead

## Must-have Requirements
1. Pipeline as Code (YAML preferred)
2. Docker build support
3. Secret management
4. Environment protection/approval gates
5. GitHub integration
6. Container image scanning
7. < 15 min pipeline for Go service

## Nice-to-have Requirements
1. Reusable pipeline templates
2. Built-in caching
3. OIDC for AWS
4. Cost < $500/month
5. SSH debugging
6. Insights/analytics

## Constraints
- Migration must be incremental (no big bang)
- No additional infrastructure team (current 2 Jenkins admins)
- Compliance: SOC 2
EOF
```

#### Bước 2: Score mỗi tool

```bash
cat > ~/cicd-comparison/scoring.md << 'EOF'
# CI/CD Tool Scoring Matrix

Scoring: 1 (Poor) - 3 (Adequate) - 5 (Excellent)

| Requirement | Weight | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|-------------|--------|---------------|-----------|---------|----------|
| Pipeline as Code | 10 | 5 (YAML) | 5 (YAML) | 3 (Groovy) | 5 (YAML) |
| Docker build | 9 | 4 | 4 | 4 | 5 (DLC) |
| Secret management | 9 | 5 | 4 | 3 | 4 |
| Env protection | 8 | 5 | 5 | 3 | 4 |
| GitHub integration | 10 | 5 (native) | 3 | 3 | 4 |
| Image scanning | 7 | 4 | 5 (built-in) | 2 | 3 |
| Pipeline speed | 8 | 4 | 4 | 4 | 5 |
| Reusable templates | 6 | 5 | 4 | 4 | 4 |
| Caching | 7 | 4 | 4 | 3 | 5 |
| OIDC for AWS | 7 | 5 | 4 | 2 | 4 |
| Cost < $500/mo | 5 | 4 | 3 | 3* | 4 |
| SSH debugging | 3 | 1 | 1 | 4 | 5 |
| Analytics | 4 | 3 | 4 | 2 | 5 |
| SOC 2 compliance | 8 | 5 | 5 | 3** | 5 |
| Low maintenance | 9 | 5 | 4 | 1 | 5 |
| Migration effort | 7 | 4 | 3 | 5*** | 3 |

* Jenkins: free but infra cost + admin time
** Jenkins: self-managed compliance
*** Jenkins: already using, no migration needed

Weighted Scores:
- GitHub Actions: 4.3 / 5.0 ← Winner
- GitLab CI: 3.9 / 5.0
- Jenkins: 2.9 / 5.0
- CircleCI: 4.2 / 5.0
EOF
```

#### Bước 3: Viết recommendation

```bash
cat > ~/cicd-comparison/recommendation.md << 'EOF'
# Recommendation: Migrate to GitHub Actions

## Summary
Dựa trên scoring matrix, GitHub Actions đạt điểm cao nhất (4.3/5.0)
cho context của tổ chức: 35 engineers, GitHub-based, AWS, need low maintenance.

## Key Reasons
1. Native GitHub integration (code + CI cùng platform)
2. Zero maintenance (vs 2 FTEs maintaining Jenkins)
3. OIDC for AWS (no static credentials)
4. Strong ecosystem (20K+ actions)
5. SOC 2 compliant

## Migration Plan
- Month 1: Setup GitHub Actions for 2 new services
- Month 2: Migrate 3 non-critical services
- Month 3: Migrate 4 more services, parallel run with Jenkins
- Month 4: Migrate 3 critical services
- Month 5: Decommission Jenkins, reassign 2 Jenkins admins

## Cost Estimate
- GitHub Team: $4/user × 35 = $140/month
- CI minutes: ~8000 min × $0.008 = $64/month
- Total: ~$204/month (vs Jenkins infra ~$560 + admin ~$800 = $1,360)
- Savings: ~$1,156/month = $13,872/year

## Risks
- Learning curve (1-2 weeks per engineer)
- GitHub vendor lock-in (mitigated: YAML is transferable)
- Migration period (dual maintenance for 3 months)
EOF
```

#### Cleanup

```bash
rm -rf ~/cicd-comparison
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Tool Selection Mistakes

| Mistake | Consequence | Prevention |
|---------|-----------|-----------|
| Chọn vì "cool" không vì fit | Migration pain | Score matrix trước |
| Không tính maintenance cost | Hidden $$ | Include FTE cost |
| Big bang migration | Service outage risk | Incremental migration |
| Ignore vendor lock-in | Stuck khi tool thay đổi pricing | Keep pipeline logic portable |
| Over-engineer pipeline | Complex, slow, hard to debug | Start simple, iterate |
| Copy pipeline từ internet | Security risks, không fit | Understand then adapt |

### 9.2 Production Case Study: Jenkins Plugin Hell

#### Context
Một fintech company, 100+ engineers, 200+ Jenkins jobs, 80+ plugins installed.

#### Symptom
Sau Jenkins upgrade từ 2.361 → 2.387, 30% pipelines fail. Error messages: `NoSuchMethodError`, `ClassNotFoundException`, `PluginException`.

#### Root Cause
- Plugin A depended on plugin B v2.x, nhưng Jenkins upgrade required plugin B v3.x.
- Plugin C (role-strategy) không compatible version mới.
- 15 plugins chưa được update trong 2 năm.

#### Impact
- 2 ngày downtime cho CI/CD.
- 40 engineers blocked.
- 3 releases delayed.
- Cost estimate: ~$200K (40 engineers × 2 days × $2,500/day loaded cost).

#### Resolution
- Rollback Jenkins version.
- Cập nhật plugins từng cái một (3 tuần).
- Remove 25 unused plugins.
- Upgrade lại Jenkins.

#### Lesson Learned
1. Jenkins plugins = npm packages: nhiều ≠ tốt.
2. Plugin audit quarterly.
3. Test upgrades trên staging Jenkins instance.
4. Team bắt đầu migration plan sang GitHub Actions.

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ các bài trước

| Bài | Connection |
|-----|-----------|
| Day 32 | CI/CD design patterns → áp dụng cho mọi tool |
| Day 33 | GitHub Actions deep dive → 1 trong 4 tools so sánh |
| Day 6 | Git workflows → CI tool phải fit Git workflow |

### Bài sau

- **Day 35**: Deployment Strategies — rolling, canary, blue-green (tool-agnostic patterns).
- **Day 36**: Progressive Delivery — Argo Rollouts (advanced deployment).
- **Day 37**: Artifact Registry, Image Signing — supply chain (used in all CI tools).

---

## 11. Tài liệu tham khảo

### Must-read

- [GitLab CI Documentation](https://docs.gitlab.com/ee/ci/)
- [Jenkins Documentation](https://www.jenkins.io/doc/)
- [CircleCI Documentation](https://circleci.com/docs/)
- [ThoughtWorks Technology Radar — CI/CD](https://www.thoughtworks.com/radar)

### Nice-to-have

- [Jenkins Configuration as Code (JCasC)](https://www.jenkins.io/projects/jcasc/)
- [GitLab Auto DevOps](https://docs.gitlab.com/ee/topics/autodevops/)
- [CircleCI Orbs Registry](https://circleci.com/developer/orbs)

### Deep-dive

- [Jenkins Scaling Guide](https://www.jenkins.io/doc/book/scaling/)
- [GitLab CI/CD Architecture](https://docs.gitlab.com/ee/development/cicd/)
- [CI/CD Pipeline Security — OWASP](https://owasp.org/www-project-devsecops-guideline/)

