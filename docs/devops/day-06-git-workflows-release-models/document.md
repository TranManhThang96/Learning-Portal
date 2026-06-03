# Day 6: Document — Git Workflows & Release Models

## 1. Git Workflow Comparison Matrix

| Tiêu chí | GitFlow | GitHub Flow | Trunk-based Development |
|----------|---------|-------------|------------------------|
| **Permanent branches** | `main` + `develop` | `main` | `main` |
| **Feature branch lifetime** | Days-weeks | Hours-days | Hours (< 1 day) |
| **Release mechanism** | Release branch | Deploy from main | Tag/release branch ngắn |
| **Hotfix flow** | Branch from main → merge main + develop | Branch from main → merge main | Branch from main → merge main |
| **Code review** | PR to develop | PR to main | PR to main (hoặc pair programming) |
| **CI/CD complexity** | Cao (nhiều branch) | Trung bình | Thấp |
| **Merge conflict risk** | Cao | Trung bình | Thấp |
| **Best for team size** | 50+ | 5-30 | 10-1000+ |
| **Best for release cadence** | Monthly/Quarterly | Weekly/Daily | Daily/Hourly |
| **Requires feature flags** | Không | Không bắt buộc | Có |
| **Multiple versions support** | Có | Không | Không (nếu cần → release branch ngắn) |
| **Learning curve** | Cao | Thấp | Trung bình |
| **DORA metrics correlation** | Low performer | Medium performer | High/Elite performer |

---

## 2. Monorepo vs Polyrepo Decision Matrix

| Tiêu chí | Monorepo | Polyrepo | Verdict |
|----------|----------|----------|---------|
| **Atomic cross-service changes** | ✅ 1 PR | ❌ Nhiều PRs coordinated | Monorepo thắng |
| **Team autonomy** | ⚠️ Cần CODEOWNERS | ✅ Team sở hữu repo | Polyrepo thắng |
| **CI/CD speed** | ⚠️ Cần selective build | ✅ Pipeline riêng | Polyrepo thắng |
| **Code sharing** | ✅ Import trực tiếp | ⚠️ Package registry | Monorepo thắng |
| **Dependency management** | ✅ Single lockfile | ⚠️ Version sync phức tạp | Monorepo thắng |
| **Git performance** | ⚠️ Chậm khi repo lớn | ✅ Repo nhỏ | Polyrepo thắng |
| **Onboarding** | ✅ 1 repo, thấy tất cả | ⚠️ Phải tìm repo | Monorepo thắng |
| **Access control** | ⚠️ Cần fine-grained perms | ✅ Repo-level perms | Polyrepo thắng |
| **Tooling requirement** | Bazel/Nx/Turborepo | Standard | Polyrepo dễ hơn |

### Decision Framework

```
Nên chọn MONOREPO khi:
├── Team < 50 developer
├── Services share nhiều code
├── Cần atomic changes thường xuyên
├── Có engineering capacity đầu tư tooling
└── Company: Google, Meta, Uber model

Nên chọn POLYREPO khi:
├── Team > 100 developer
├── Services độc lập cao
├── Cần access control per service
├── Regulated industry (audit per service)
└── Không muốn invest vào custom tooling
```

---

## 3. Versioning Strategy Guide

### Semantic Versioning (SemVer) Quick Reference

```
Format: MAJOR.MINOR.PATCH[-pre-release][+build]

MAJOR — Breaking change (API incompatible)
  1.0.0 → 2.0.0:  removed endpoint, changed response format
  
MINOR — New feature (backward compatible)  
  1.0.0 → 1.1.0:  added new endpoint, new optional field
  
PATCH — Bug fix (backward compatible)
  1.0.0 → 1.0.1:  fixed validation, fixed memory leak

Pre-release examples:
  1.0.0-alpha.1    → internal testing
  1.0.0-beta.1     → external beta
  1.0.0-rc.1       → release candidate

Precedence: 1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-beta < 1.0.0-rc.1 < 1.0.0
```

### Versioning Strategy per Artifact Type

| Artifact | Strategy | Tag Format | Ví dụ |
|----------|----------|------------|-------|
| Public API/Library | Strict SemVer | `v{M}.{m}.{p}` | `v2.3.1` |
| Internal microservice | SemVer | `v{M}.{m}.{p}` | `v1.5.0` |
| Container image (CI) | SemVer + SHA | `v{M}.{m}.{p}-{sha7}` | `v1.5.0-abc123d` |
| Container image (CD) | SemVer | `v{M}.{m}.{p}` | `v1.5.0` |
| Helm chart | SemVer | `{M}.{m}.{p}` | `0.3.2` |
| Terraform module | SemVer | `v{M}.{m}.{p}` | `v1.0.0` |
| Database migration | Sequential | `{NNN}` | `042` |
| Config/Infra change | Commit SHA | `{sha7}` | `abc123d` |
| Mobile app | SemVer + build | `v{M}.{m}.{p}+{build}` | `v2.1.0+345` |

### Conventional Commits → Auto Version Bump

| Commit Prefix | SemVer Bump | Ví dụ |
|---------------|-------------|-------|
| `fix:` | PATCH | `fix: null pointer in payment validation` |
| `feat:` | MINOR | `feat: add subscription management` |
| `feat!:` | MAJOR | `feat!: redesign authentication API` |
| `BREAKING CHANGE:` | MAJOR | Footer trong commit body |
| `chore:` | Không bump | `chore: update dependencies` |
| `docs:` | Không bump | `docs: update API documentation` |
| `ci:` | Không bump | `ci: add security scanning step` |
| `refactor:` | Không bump | `refactor: extract payment validator` |
| `perf:` | PATCH | `perf: optimize database queries` |
| `test:` | Không bump | `test: add integration tests` |

---

## 4. Branch Naming Convention

### Format

```
{type}/{ticket-id}-{short-description}
```

### Types

| Type | Mô tả | Ví dụ |
|------|--------|-------|
| `feature/` | Feature mới | `feature/PAY-123-add-card-validation` |
| `fix/` | Bug fix (không urgent) | `fix/PAY-456-null-amount-error` |
| `hotfix/` | Production emergency | `hotfix/PAY-789-payment-timeout` |
| `release/` | Release preparation | `release/v1.2.0` |
| `chore/` | Non-functional changes | `chore/update-node-18` |
| `docs/` | Documentation only | `docs/api-migration-guide` |
| `refactor/` | Code refactoring | `refactor/payment-service-cleanup` |
| `test/` | Test additions | `test/payment-integration` |
| `ci/` | CI/CD pipeline changes | `ci/add-security-scan` |

### Rules

```
✅ Tốt:
  feature/PAY-123-add-card-validation
  fix/AUTH-456-token-expiry-bug
  hotfix/PROD-001-payment-500-error

❌ Xấu:
  my-branch                    # Không có type, ticket
  Feature/PAY-123              # Uppercase
  feature/add_card_validation  # Underscore thay vì dash
  feature/PAY-123-implement-the-new-credit-card-validation-system-with-luhn-algorithm  # Quá dài
```

### Quy tắc bổ sung

- **Lowercase only** — tránh conflict trên case-insensitive filesystem (macOS)
- **Dash-separated** — `add-card` không phải `add_card`
- **Max 60 ký tự** tổng chiều dài
- **Phải có ticket ID** (trừ chore/docs)
- **Mô tả ngắn gọn** — 3-5 từ

---

## 5. Release Checklist Templates

### Standard Release Checklist

```markdown
# Release Checklist — v{VERSION}

## Thông tin release
- Version: v{VERSION}
- Release date: {DATE}
- Release manager: {NAME}
- Type: [ ] Major  [ ] Minor  [ ] Patch  [ ] Hotfix

## Pre-release
- [ ] Feature freeze confirmed
- [ ] All PRs merged to release branch/main
- [ ] CHANGELOG.md updated
- [ ] Version bumped in:
  - [ ] package.json / go.mod / pom.xml
  - [ ] Helm chart (Chart.yaml)
  - [ ] Docker image tag
- [ ] CI pipeline green (all stages)
- [ ] Test coverage ≥ {TARGET}%
- [ ] No critical/high severity bugs open
- [ ] Security scan passed
- [ ] Performance test baseline met

## Staging Deployment
- [ ] Deployed to staging environment
- [ ] Smoke tests passed
- [ ] Integration tests passed
- [ ] Manual QA sign-off (if applicable)
- [ ] Database migration tested

## Production Deployment
- [ ] Deployment window confirmed
- [ ] On-call engineer aware
- [ ] Canary deployment ({PERCENTAGE}% traffic)
- [ ] Monitor for {DURATION} minutes:
  - [ ] Error rate < {THRESHOLD}%
  - [ ] Latency p99 < {THRESHOLD}ms
  - [ ] No new error types in logs
- [ ] Full rollout
- [ ] Health checks passing

## Post-release
- [ ] Git tag created (signed)
- [ ] Release notes published
- [ ] Release branch merged back (if GitFlow)
- [ ] Release branch deleted
- [ ] Team notified
- [ ] Monitoring reviewed (30 min post-deploy)
- [ ] Customers notified (if relevant)

## Rollback Plan
- Rollback command: {COMMAND}
- Previous stable version: v{PREV_VERSION}
- Rollback trigger criteria:
  - Error rate > {THRESHOLD}%
  - Latency p99 > {THRESHOLD}ms
  - Any data corruption detected
- Rollback owner: {ON-CALL}
- Estimated rollback time: {TIME} minutes
```

### Hotfix Release Checklist

```markdown
# Hotfix Checklist — v{VERSION}

## Incident
- Incident ID: {ID}
- Severity: [ ] P1  [ ] P2
- Impact: {DESCRIPTION}
- Affected service: {SERVICE}

## Fix
- [ ] Hotfix branch created from main (NOT develop)
- [ ] Minimal fix only (no refactoring, no features)
- [ ] Unit tests added for the fix
- [ ] 2 reviewers approved
- [ ] CI pipeline green

## Deploy
- [ ] Canary 10% for 5 minutes
- [ ] Error rate normalized
- [ ] Full rollout
- [ ] Incident metrics improved

## Post-fix
- [ ] Tag v{VERSION}
- [ ] Backport to develop/release branches
- [ ] Incident timeline documented
- [ ] Postmortem scheduled (within 48h)
```

---

## 6. Git Command Cheat Sheet cho Workflow

### Branch Operations

```bash
# Tạo branch
git checkout -b feature/PAY-123-description    # Tạo và switch
git branch feature/PAY-123-description         # Chỉ tạo

# List branches
git branch                    # Local branches
git branch -r                 # Remote branches
git branch -a                 # Tất cả
git branch --merged main      # Branches đã merge vào main
git branch --no-merged main   # Branches chưa merge

# Delete branch
git branch -d feature/done          # Safe delete (đã merge)
git branch -D feature/abandoned     # Force delete
git push origin --delete feature/done  # Delete remote

# Rename branch
git branch -m old-name new-name
```

### Merge & Rebase

```bash
# Merge (giữ history)
git merge feature/auth --no-ff     # Luôn tạo merge commit
git merge --abort                  # Hủy merge nếu conflict

# Rebase (linear history)
git rebase main                    # Rebase branch hiện tại lên main
git rebase --abort                 # Hủy rebase
git rebase --continue              # Tiếp tục sau resolve conflict

# Squash merge
git merge --squash feature/auth    # Gộp commits thành 1
git commit -m "feat: add authentication"
```

### Tagging

```bash
# Tạo tag
git tag v1.0.0                      # Lightweight
git tag -a v1.0.0 -m "Release 1.0"  # Annotated (khuyến nghị)
git tag -s v1.0.0 -m "Release 1.0"  # Signed (GPG)

# List tags
git tag -l                          # Tất cả
git tag -l "v1.*"                   # Filter pattern
git tag -l -n1                      # Với message

# Push tags
git push origin v1.0.0              # Push 1 tag
git push origin --tags              # Push tất cả tags

# Delete tag
git tag -d v1.0.0                   # Local
git push origin --delete v1.0.0     # Remote

# Checkout tag
git checkout v1.0.0                 # Detached HEAD
git checkout -b hotfix/v1.0.1 v1.0.0  # Branch from tag
```

### Diff & Log cho Review

```bash
# Xem thay đổi
git diff main..feature/auth           # Diff giữa 2 branch
git diff main...feature/auth          # Diff từ common ancestor
git diff --stat main..feature/auth    # Summary thống kê

# Log
git log --oneline --graph --all             # Overview đẹp
git log --oneline main..feature/auth        # Commits chỉ trên feature
git log --merges --oneline                  # Chỉ merge commits
git log --no-merges --oneline              # Bỏ merge commits
git log --since="2024-01-01" --oneline     # Theo thời gian
git log --author="john" --oneline          # Theo tác giả

# Tìm commit chứa text
git log --grep="payment" --oneline         # Search commit message
git log -S "functionName" --oneline        # Search code changes (pickaxe)

# Blame
git blame payment.py                       # Ai sửa dòng nào
git blame -L 10,20 payment.py             # Chỉ dòng 10-20
```

### Stash & Cherry-pick

```bash
# Stash (lưu tạm thay đổi)
git stash                          # Stash working directory
git stash push -m "WIP: auth"     # Stash với message
git stash list                     # List stashes
git stash pop                      # Apply và xóa stash gần nhất
git stash apply stash@{2}         # Apply stash cụ thể (giữ lại)
git stash drop stash@{0}          # Xóa stash

# Cherry-pick (chỉ dùng cho hotfix)
git cherry-pick abc123d            # Apply 1 commit
git cherry-pick abc123d..def456g   # Apply range
git cherry-pick -x abc123d        # Ghi note commit gốc
```

### Undo & Recovery

```bash
# Undo commit gần nhất (giữ changes)
git reset --soft HEAD~1

# Revert commit (tạo commit mới, safe cho shared branch)
git revert abc123d
git revert -m 1 MERGE_SHA        # Revert merge commit

# Recover deleted branch
git reflog                        # Tìm commit cuối của branch
git checkout -b recovered abc123d # Tạo lại branch

# ⚠️ NGUY HIỂM — chỉ dùng khi biết rõ mình đang làm gì
git reset --hard HEAD~1           # Xóa commit + changes
git push --force origin branch    # Force push (rewrite remote history)
```

---

## 7. Decision Framework: Chọn Git Workflow

```
START
  │
  ├── Team size < 10?
  │     ├── Yes → Deploy liên tục?
  │     │           ├── Yes → GitHub Flow ✅
  │     │           └── No  → GitHub Flow (vẫn OK) ✅
  │     └── No  ↓
  │
  ├── Team size 10-50?
  │     ├── Deploy > 1x/week?
  │     │     ├── Yes → Có feature flag system?
  │     │     │           ├── Yes → Trunk-based ✅
  │     │     │           └── No  → GitHub Flow ✅
  │     │     └── No ↓
  │     └── Scheduled release?
  │           ├── Yes → GitFlow ✅
  │           └── No  → GitHub Flow ✅
  │
  ├── Team size 50+?
  │     ├── Regulated industry?
  │     │     ├── Yes → Modified trunk-based + approval gates ✅
  │     │     └── No  → Trunk-based + feature flags ✅
  │     └── Support multiple versions?
  │           ├── Yes → GitFlow ✅
  │           └── No  → Trunk-based ✅
  │
  └── Mobile app?
        ├── Yes → GitFlow (app store release cycle) ✅
        └── No  → (follow team size above)
```

---

## 8. Automated Versioning Tools Reference

| Tool | Ecosystem | Conventional Commits | Changelog | Monorepo |
|------|-----------|---------------------|-----------|----------|
| **semantic-release** | Node.js | ✅ | ✅ | Plugin |
| **release-please** | Any (GitHub) | ✅ | ✅ | ✅ |
| **standard-version** | Node.js | ✅ | ✅ | ❌ |
| **goreleaser** | Go | ❌ | ✅ | ❌ |
| **commitizen** | Multi-lang | ✅ | ✅ | Plugin |
| **changesets** | Node.js | Custom | ✅ | ✅ |
| **cargo-release** | Rust | ❌ | ❌ | Workspace |

### Setup nhanh semantic-release

```json
// .releaserc.json
{
  "branches": ["main"],
  "plugins": [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    "@semantic-release/changelog",
    "@semantic-release/git",
    "@semantic-release/github"
  ]
}
```

### Setup nhanh release-please (GitHub Actions)

```yaml
# .github/workflows/release-please.yml
name: release-please
on:
  push:
    branches: [main]

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          release-type: node  # hoặc go, python, etc.
```

---

## 9. Pre-commit Hooks Reference

### Cài đặt pre-commit framework

```bash
# Python-based pre-commit
pip install pre-commit

# .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: detect-private-key
      - id: no-commit-to-branch
        args: ['--branch', 'main']

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks

  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.0.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
EOF

pre-commit install
pre-commit install --hook-type commit-msg
```

### Git hooks thủ công

```bash
# .git/hooks/commit-msg — Validate conventional commit
#!/bin/bash
MSG=$(head -1 "$1")
PATTERN="^(feat|fix|chore|docs|style|refactor|test|ci|perf|build|revert)(\(.+\))?(!)?: .{1,72}$"
if ! echo "$MSG" | grep -qE "$PATTERN"; then
    echo "❌ Invalid commit message format"
    echo "Expected: type(scope): description"
    echo "Got: $MSG"
    exit 1
fi

# .git/hooks/pre-push — Prevent push to main
#!/bin/bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ]; then
    echo "❌ Direct push to main is not allowed"
    echo "Create a feature branch and open a PR"
    exit 1
fi
```

