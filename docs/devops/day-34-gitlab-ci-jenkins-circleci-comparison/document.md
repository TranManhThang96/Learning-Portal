# Day 34: GitLab CI, Jenkins, CircleCI Comparison — Document

## 1. Comprehensive Feature Comparison Matrix

### Core Features

| Feature | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|---------|---------------|-----------|---------|----------|
| **License** | Proprietary | MIT (CE) / Proprietary (EE) | MIT | Proprietary |
| **First Release** | 2019 | 2015 | 2011 | 2011 |
| **Pipeline Language** | YAML | YAML | Groovy | YAML |
| **Git Platform** | GitHub only | GitLab only | Any | GitHub, Bitbucket |
| **SaaS** | ✅ | ✅ | ❌ | ✅ |
| **Self-hosted** | ✅ (runners) | ✅ (full instance) | ✅ (full) | ✅ (runners) |
| **Container Registry** | ✅ GHCR | ✅ Built-in | ❌ | ❌ |
| **Package Registry** | ✅ npm, Maven, etc. | ✅ npm, Maven, etc. | ❌ | ❌ |
| **Wiki** | ✅ | ✅ | ❌ | ❌ |
| **Issue Tracker** | ✅ | ✅ | ❌ | ❌ |

### CI/CD Features

| Feature | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|---------|---------------|-----------|---------|----------|
| **Pipeline as Code** | YAML | YAML | Groovy/YAML | YAML |
| **DAG Pipeline** | ✅ `needs` | ✅ `needs` | ✅ stages | ✅ `requires` |
| **Matrix Build** | ✅ `strategy.matrix` | ✅ `parallel:matrix` | ⚠️ Plugin | ✅ `parallelism` |
| **Caching** | ✅ `actions/cache` | ✅ `cache:` | ⚠️ Plugin | ✅ `save/restore_cache` |
| **Artifacts** | ✅ `upload-artifact` | ✅ `artifacts:` | ✅ `archiveArtifacts` | ✅ `store_artifacts` |
| **Manual Approval** | ✅ Environment | ✅ `when: manual` | ✅ `input` | ✅ `type: approval` |
| **Scheduled Runs** | ✅ `schedule` | ✅ `schedules` | ✅ `cron` | ✅ `schedule` |
| **Conditional** | ✅ `if:` | ✅ `rules:` | ✅ `when {}` | ✅ `when:` |
| **Reusable Config** | Reusable workflows | `include`, `extends` | Shared libraries | Orbs |
| **Service Containers** | ✅ `services:` | ✅ `services:` | ✅ Docker agent | ✅ `docker:` |
| **Multi-project** | ⚠️ `workflow_dispatch` | ✅ Cross-project | ✅ Build triggers | ⚠️ API |
| **Review Apps** | ⚠️ Manual setup | ✅ Built-in | ⚠️ Manual | ⚠️ Manual |
| **Auto DevOps** | ❌ | ✅ | ❌ | ❌ |

### Security Features

| Feature | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|---------|---------------|-----------|---------|----------|
| **SAST** | CodeQL (free) | ✅ (Ultimate) | ❌ | ❌ |
| **DAST** | ❌ | ✅ (Ultimate) | ❌ | ❌ |
| **SCA** | Dependabot | ✅ (Ultimate) | ❌ | ❌ |
| **Container Scan** | ⚠️ 3rd party | ✅ (Ultimate) | ❌ | ❌ |
| **Secret Detection** | ✅ (push protection) | ✅ (Ultimate) | ❌ | ❌ |
| **License Compliance** | ❌ | ✅ (Ultimate) | ❌ | ❌ |
| **OIDC** | ✅ | ✅ | ⚠️ Plugin | ✅ |
| **Audit Logs** | ✅ (Enterprise) | ✅ (Premium+) | ⚠️ Plugin | ✅ (Scale) |

---

## 2. Pipeline Syntax Quick Reference

### Same Pipeline — 4 Formats

**Task**: Lint → Test → Build Docker → Deploy (main only, manual for prod)

#### GitHub Actions
```yaml
on:
  push:
    branches: [main]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - run: make lint
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - run: make test
  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - run: docker build -t app:${{ github.sha }} .
  deploy:
    needs: build
    environment: production
    runs-on: ubuntu-latest
    steps:
      - run: echo "deploy"
```

#### GitLab CI
```yaml
stages: [lint, test, build, deploy]
lint:
  stage: lint
  script: make lint
test:
  stage: test
  script: make test
build:
  stage: build
  script: docker build -t app:$CI_COMMIT_SHORT_SHA .
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
deploy:
  stage: deploy
  script: echo "deploy"
  environment: production
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

#### Jenkins
```groovy
pipeline {
  agent any
  stages {
    stage('Lint') { steps { sh 'make lint' } }
    stage('Test') { steps { sh 'make test' } }
    stage('Build') {
      when { branch 'main' }
      steps { sh "docker build -t app:${GIT_COMMIT.take(7)} ." }
    }
    stage('Deploy') {
      when { branch 'main' }
      input { message 'Deploy?' }
      steps { sh 'echo deploy' }
    }
  }
}
```

#### CircleCI
```yaml
version: 2.1
jobs:
  lint:
    docker: [{image: cimg/base:current}]
    steps: [checkout, {run: make lint}]
  test:
    docker: [{image: cimg/base:current}]
    steps: [checkout, {run: make test}]
  build:
    docker: [{image: cimg/base:current}]
    steps:
      - checkout
      - setup_remote_docker
      - run: docker build -t app:$CIRCLE_SHA1 .
  deploy:
    docker: [{image: cimg/base:current}]
    steps: [{run: echo deploy}]
workflows:
  main:
    jobs:
      - lint
      - test
      - build:
          requires: [lint, test]
          filters: {branches: {only: main}}
      - hold: {type: approval, requires: [build]}
      - deploy: {requires: [hold]}
```

---

## 3. Cost Calculator Reference

### Pricing Models

| Tool | Free Tier | Paid (per user/month) | CI Minutes Cost |
|------|-----------|----------------------|-----------------|
| **GitHub Actions** | 2000 min/mo (private) | Team/Enterprise theo GitHub pricing | $0.006/min Linux 2-core |
| **GitLab CI** | Quota theo subscription | Premium/Ultimate theo GitLab pricing | Compute-minute pack rate trên GitLab pricing |
| **Jenkins** | ∞ (self-hosted) | N/A | Infra cost only |
| **CircleCI** | 30,000 free credits/mo, up to 6,000 build minutes | Performance starts at $15/mo | Credit-per-minute theo resource class |

Pricing thay đổi thường xuyên. Bảng này dùng để hiểu model tính chi phí; khi làm budget thật, kiểm tra lại trang pricing chính thức của từng vendor.

### Cost Formula

```
Monthly CI/CD Cost =
  Platform fee (per user × users)
  + CI minutes (minutes × rate)
  + Infrastructure (self-hosted runners/agents)
  + Admin time (hours × hourly rate)

Example: 30 engineers, 200 builds/day, 10 min avg

GitHub Actions:
  Team: 30 × $4 = $120
  Minutes: 200 × 10 × 22 days = 44,000 min
  Free: 2,000 → Paid: 42,000 × $0.006 = $252
  Total: $372/month

Jenkins (self-hosted):
  Infra: 3 × m5.xlarge = 3 × $140 = $420
  Admin: 15 hours × $80 = $1,200
  Total: $1,620/month

Verdict: GitHub Actions is ~4.3x cheaper at this scale under these assumptions
```

---

## 4. Decision Framework Flowchart

```
START: Choose CI/CD Tool
│
├── Q1: Where is your code hosted?
│   ├── GitHub → Strong lean toward GitHub Actions
│   ├── GitLab → Strong lean toward GitLab CI
│   ├── Bitbucket → CircleCI or Jenkins
│   └── Self-hosted Git → Jenkins
│
├── Q2: Do you have ops/infra team?
│   ├── No → Cloud CI (GitHub Actions, CircleCI, GitLab SaaS)
│   └── Yes → Any option viable
│
├── Q3: Compliance requirements?
│   ├── PCI/HIPAA/SOC2 → GitLab Ultimate or GitHub Enterprise
│   ├── Air-gapped → Jenkins or GitLab Self-hosted
│   └── None → Any option
│
├── Q4: Budget sensitivity?
│   ├── < $200/mo → GitHub Actions or CircleCI free tier
│   ├── $200-1000/mo → Any cloud CI
│   └── $1000+/mo → Consider Jenkins TCO vs cloud
│
├── Q5: Team size?
│   ├── < 10 → GitHub Actions (simplest)
│   ├── 10-50 → GitHub Actions or GitLab CI
│   ├── 50-200 → GitLab CI or Jenkins + GitHub Actions hybrid
│   └── 200+ → Enterprise evaluation needed
│
└── RESULT: Top recommendation based on answers
```

---

## 5. Migration Checklist

### From Jenkins to GitHub Actions

```
Pre-migration:
□ Inventory all Jenkins jobs (count, type, frequency)
□ Identify shared libraries used
□ Map Groovy constructs to YAML equivalents
□ List all plugins and find GHA alternatives
□ Identify jobs with special requirements (GPU, hardware)
□ Export credentials/secrets list (don't export values!)
□ Document custom integrations (Slack, Jira, etc.)

Migration:
□ Phase 1: New services on GitHub Actions (parallel run)
□ Phase 2: Simple jobs migration (lint, test, build)
□ Phase 3: Complex jobs (multi-stage, approval flows)
□ Phase 4: Jobs with custom agents/hardware
□ Phase 5: Shared libraries → reusable workflows
□ Each phase: verify, monitor, compare outputs

Post-migration:
□ Verify all workflows running correctly (2 weeks parallel)
□ Update documentation
□ Train team on new tool
□ Decommission Jenkins (backup config first!)
□ Redirect old webhooks
□ Clean up Jenkins infrastructure
□ Cost comparison report
```

### From Any Tool to GitLab CI

```
Pre-migration:
□ Evaluate: code migration to GitLab needed?
□ If code stays on GitHub: GitLab CI can mirror repos
□ Map existing pipeline stages to GitLab CI syntax
□ Identify GitLab tier needed (Free/Premium/Ultimate)
□ Plan runner infrastructure

Migration:
□ Setup GitLab instance or SaaS account
□ Configure runners (shared or dedicated)
□ Migrate pipeline configs (.gitlab-ci.yml)
□ Setup environments and variables
□ Configure integrations (Slack, monitoring)
□ Parallel run period (2-4 weeks minimum)
```

---

## 6. Terminology Mapping

| Concept | GitHub Actions | GitLab CI | Jenkins | CircleCI |
|---------|---------------|-----------|---------|----------|
| Pipeline file | workflow (.yaml) | .gitlab-ci.yml | Jenkinsfile | config.yml |
| Pipeline | Workflow | Pipeline | Pipeline/Job | Pipeline |
| Stage group | Job | Stage | Stage | Job |
| Task unit | Step | Job | Step | Step |
| Parallel | Matrix | parallel:matrix | Matrix axis | parallelism |
| Runner | Runner | Runner | Agent/Node | Executor |
| Reuse | Reusable workflow | include/extends | Shared library | Orb |
| Approval | Environment | when: manual | input | approval |
| Secret | Secret | Variable (masked) | Credential | Context |
| Cache | actions/cache | cache: key/paths | stash/unstash | save/restore_cache |
| Artifact | upload-artifact | artifacts: | archiveArtifacts | store_artifacts |
| Condition | if: | rules: | when {} | when: |
| Env var | env: | variables: | environment {} | environment: |
| Trigger | on: | trigger/rules | triggers {} | filters: |
| Badge | ![badge](https://img.shields.io/badge/build-passing-brightgreen) | Pipeline badge | Build status | Status badge |

