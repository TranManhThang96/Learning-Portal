# Day 6: Git Workflows & Release Models

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt được** GitFlow, GitHub Flow, và trunk-based development — biết khi nào dùng workflow nào dựa trên team size, release cadence, và product type.
2. **Đánh giá được** trade-off giữa monorepo và polyrepo cho tổ chức engineering cụ thể.
3. **Thiết kế được** versioning strategy phù hợp (Semantic Versioning, commit SHA, build number) cho từng loại artifact.
4. **Xây dựng được** release checklist và hotfix flow cho team 10-100 developer.
5. **Nhận diện được** anti-patterns trong Git workflow gây bottleneck cho CI/CD pipeline.

---

## 2. Bối cảnh & Động lực

### Vì sao Git workflow quan trọng trong production?

Là Senior Developer, bạn đã quen với `git commit`, `git push`, `git merge`. Nhưng khi scale từ 1-2 developer lên team 10-100 người, Git workflow trở thành **yếu tố quyết định tốc độ delivery và stability**.

**Câu chuyện thực tế**: Một team 30 developer dùng GitFlow với release branch dài 2 tuần. Mỗi sprint, merge conflicts chiếm 20% thời gian developer. Hotfix phải cherry-pick qua 3 branch (hotfix → main → develop → release). Một lần cherry-pick sai gây regression trên production, downtime 4 giờ.

### Nếu làm sai thì hậu quả là gì?

- **Merge hell**: Conflict liên tục, developer mất thời gian resolve thay vì code feature.
- **Release bottleneck**: Chỉ 1 người biết release process, họ nghỉ phép = không ai release được.
- **Hotfix nightmare**: Không biết patch nào đã apply ở đâu, regression sau hotfix.
- **CI/CD chậm**: Pipeline chạy trên quá nhiều branch, resource CI bị phân tán.
- **Rollback thất bại**: Không biết version nào đang chạy, rollback về version sai.

### Liên hệ với kiến thức developer

| Concept developer đã biết | Ánh xạ sang DevOps |
|---|---|
| API versioning (v1, v2) | Semantic Versioning cho artifact |
| Feature flag trong code | Branch strategy + feature flag |
| Database migration order | Release order giữa services |
| Dependency management | Monorepo vs polyrepo dependency |

---

## 3. Kiến thức nền tảng

### Git Branching Model — Tại sao cần strategy?

Git cho phép tạo branch gần như miễn phí (chỉ là pointer đến commit). Nhưng **tự do quá mức** dẫn đến chaos:

```
# Không có strategy → ai cũng tạo branch random
feature/john-login
fix/bug-123
test/experiment-new-ui
johns-branch
temp-fix-friday
hotfix-urgent-please-merge
```

Branch strategy giải quyết 3 câu hỏi:
1. **Khi nào tạo branch?** → Trigger: feature, bugfix, hotfix, release
2. **Branch từ đâu?** → Source: main, develop, release
3. **Merge vào đâu?** → Target: develop, main, release

### 3 workflow phổ biến

```
Complexity:  Low ←————————————————————→ High
             GitHub Flow → Trunk-based → GitFlow
             
Team size:   Small ←———————————————————→ Large
             GitHub Flow → Trunk-based → GitFlow

Release:     Continuous ←——————————————→ Scheduled
             Trunk-based → GitHub Flow → GitFlow
```

---

## 4. Deep Dive

### 4.1 GitFlow

Được đề xuất bởi Vincent Driessen (2010). Phù hợp với **scheduled release** và **multiple versions in production**.

```
                    main (production)
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
 tag v1.0         tag v1.1         tag v2.0
    │                │                │
    │    hotfix/     │                │
    │◄───fix-123 ◄───┘                │
    │                                 │
    └──────────► develop ◄────────────┘
                   │  │  │
                   │  │  │
            feature/ feature/ feature/
            login    cart     payment
                   │
                   ▼
              release/v1.1
              (stabilize)
                   │
                   ▼
                  main
```

**Branch types trong GitFlow:**

| Branch | Source | Merge to | Mục đích | Lifetime |
|--------|--------|----------|----------|----------|
| `main` | — | — | Production code | Permanent |
| `develop` | `main` | — | Integration branch | Permanent |
| `feature/*` | `develop` | `develop` | New feature | Temporary |
| `release/*` | `develop` | `main` + `develop` | Release stabilization | Temporary |
| `hotfix/*` | `main` | `main` + `develop` | Emergency fix | Temporary |

**Khi nào dùng GitFlow:**
- Product có scheduled release (monthly, bi-weekly)
- Cần support multiple versions (v1.x, v2.x song song)
- Team lớn (50+) cần isolation rõ ràng
- Regulated industry cần audit trail

### 4.2 GitHub Flow

Đơn giản hóa tối đa: chỉ có `main` + feature branch.

```
main ──●──●──●──●──●──●──●──●──●──●── (always deployable)
        \        /  \        /
         feature/   feature/
         login      cart
         (PR+review) (PR+review)
```

**Quy trình:**
1. Branch từ `main`
2. Commit thường xuyên
3. Mở Pull Request
4. Code review + CI pass
5. Merge vào `main`
6. Deploy từ `main`

**Khi nào dùng GitHub Flow:**
- Web application deploy liên tục
- Team nhỏ-trung (5-20 developer)
- Không cần support multiple versions
- CI/CD pipeline mạnh, deploy tự động

### 4.3 Trunk-based Development

Mọi developer commit trực tiếp vào `main` (trunk) hoặc dùng **short-lived feature branch** (< 1-2 ngày).

```
main ──●──●──●──●──●──●──●──●──●──●──●──●── 
        \  /    \  /        │
        short   short    direct
        branch  branch   commit
        (< 1d)  (< 1d)
        
Release: tag hoặc release branch ngắn
         ──────► v1.0 (cut from main)
```

**Nguyên tắc cốt lõi:**
- Feature branch sống **tối đa 1-2 ngày**
- Merge vào main **ít nhất 1 lần/ngày**
- Code chưa sẵn sàng → **feature flag** (không phải long-lived branch)
- Main **luôn deployable**

**Khi nào dùng trunk-based development:**
- Team có kỷ luật testing cao (>80% coverage)
- CI/CD pipeline nhanh (< 10 phút)
- Có feature flag system
- Google, Meta, Netflix dùng approach này

### 4.4 Monorepo vs Polyrepo

```
# Monorepo
my-company/
├── services/
│   ├── user-service/
│   ├── order-service/
│   └── payment-service/
├── packages/
│   ├── shared-utils/
│   └── proto-definitions/
└── infra/
    ├── terraform/
    └── k8s-manifests/

# Polyrepo
my-company/user-service/
my-company/order-service/
my-company/payment-service/
my-company/shared-utils/
my-company/infra-terraform/
```

| Tiêu chí | Monorepo | Polyrepo |
|----------|----------|----------|
| **Atomic changes** | ✅ Thay đổi cross-service trong 1 commit | ❌ Phải coordinate nhiều PR |
| **Code sharing** | ✅ Import trực tiếp | ❌ Publish package, version dependency |
| **CI/CD** | ⚠️ Phải build selective (affected only) | ✅ Mỗi repo có pipeline riêng |
| **Ownership** | ⚠️ Cần CODEOWNERS rõ ràng | ✅ Team sở hữu repo riêng |
| **Git performance** | ⚠️ Repo lớn → clone/checkout chậm | ✅ Repo nhỏ, nhanh |
| **Tooling** | Cần Bazel, Nx, Turborepo | Standard tooling |
| **Onboarding** | ✅ 1 repo, thấy toàn bộ codebase | ⚠️ Phải biết repo nào làm gì |

### 4.5 Versioning Strategy

#### Semantic Versioning (SemVer)

```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └── Bug fix, backward compatible
  │     └──────── New feature, backward compatible  
  └────────────── Breaking change

Ví dụ: 2.3.1
- 2 → có breaking changes so với v1
- 3 → feature thứ 3 kể từ v2.0.0
- 1 → patch thứ 1 của v2.3.0
```

**Pre-release và build metadata:**
```
1.0.0-alpha.1        # Alpha release
1.0.0-beta.2         # Beta release
1.0.0-rc.1           # Release candidate
1.0.0+build.123      # Build metadata
1.0.0-beta.1+sha.abc # Pre-release + build metadata
```

#### Commit SHA

```bash
# Dùng short SHA làm version identifier
git rev-parse --short HEAD
# Output: a1b2c3d

# Image tag bằng SHA
docker build -t myapp:a1b2c3d .
```

**Khi nào dùng commit SHA:**
- Internal service không cần public versioning
- Continuous deployment (mỗi commit = 1 version)
- Traceability: từ running container → exact source code

#### Build Number

```bash
# CI/CD tự tăng build number
myapp:build-1234
myapp:build-1235

# Kết hợp với SemVer
myapp:1.2.3-build.1234
```

**Versioning decision matrix:**

| Artifact type | Versioning strategy | Ví dụ |
|---|---|---|
| Public library/API | SemVer | `v2.3.1` |
| Internal microservice | SemVer hoặc SHA | `v1.5.0` hoặc `abc123d` |
| Container image | SemVer + SHA | `v1.5.0-abc123d` |
| Helm chart | SemVer | `0.3.2` |
| Terraform module | SemVer | `v1.0.0` |
| Config change | Commit SHA | `cfg-abc123d` |

### 4.6 Hotfix Flow

```
Incident detected!
        │
        ▼
┌─────────────────────┐
│ 1. Branch from main │  ← Không phải từ develop!
│    hotfix/CVE-2024   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 2. Fix + Test        │  ← Minimal change only
│    (unit + smoke)    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 3. PR → Review       │  ← Expedited review (2 approvers)
│    CI pipeline pass  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 4. Merge → main      │  ← Tag new version
│    Tag v1.2.1        │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 5. Deploy to prod    │  ← Canary → full rollout
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 6. Backport to       │  ← Đừng quên!
│    develop/release   │
└─────────────────────┘
```

---

## 5. Trade-offs & Best Practices ⭐

### Workflow Comparison Matrix

| Tiêu chí | GitFlow | GitHub Flow | Trunk-based |
|----------|---------|-------------|-------------|
| **Complexity** | Cao | Thấp | Trung bình |
| **Release cadence** | Scheduled | Continuous | Continuous |
| **Merge conflicts** | Nhiều | Ít | Rất ít |
| **Learning curve** | Cao | Thấp | Trung bình |
| **CI/CD load** | Cao (nhiều branch) | Trung bình | Thấp |
| **Rollback** | Tag-based | Revert commit | Revert/flag |
| **Feature isolation** | Branch dài | Branch ngắn | Feature flag |
| **Code review** | PR lớn | PR vừa | PR nhỏ |
| **Integration risk** | Cao (merge muộn) | Trung bình | Thấp (merge sớm) |

### Recommendation theo scenario

#### Startup (5-10 developer, 1 product)
```
✅ GitHub Flow
- Lý do: đơn giản, fast iteration, mọi người đều deploy
- Release: merge to main = deploy
- Versioning: commit SHA cho internal, SemVer cho API
```

#### Mid-size SaaS (20-50 developer, microservices)
```
✅ Trunk-based development + feature flags
- Lý do: velocity cao, conflict thấp, CI/CD nhanh
- Release: continuous deployment per service
- Versioning: SemVer per service
- Cần: feature flag system (LaunchDarkly, Unleash, self-built)
```

#### Enterprise (100+ developer, regulated industry)
```
✅ GitFlow hoặc modified trunk-based
- Lý do: audit trail, release approval, compliance
- Release: scheduled release train
- Versioning: strict SemVer
- Cần: release manager role, approval gates
```

#### Mobile app (app store release)
```
✅ GitFlow
- Lý do: app store review = scheduled release, cần support old versions
- Release: release branch cho từng version
- Hotfix: patch branch từ release branch
```

### Anti-patterns cần tránh

1. **Long-lived feature branch** (> 1 tuần)
   - Vấn đề: merge conflict tăng exponentially theo thời gian
   - Fix: chia feature nhỏ, merge daily, dùng feature flag

2. **Cherry-pick thay vì merge**
   - Vấn đề: commit history diverge, miss changes
   - Fix: merge/rebase, chỉ cherry-pick cho hotfix

3. **Không protect main branch**
   - Vấn đề: push trực tiếp, break production
   - Fix: branch protection rules, require PR + CI + review

4. **Quá nhiều branch types**
   - Vấn đề: team confused, process overhead
   - Fix: giữ tối đa 3-4 branch types

5. **Manual versioning**
   - Vấn đề: quên bump version, version conflict
   - Fix: automated versioning (conventional commits + semantic-release)

---

## 6. Performance & Scalability ⭐

### Git workflow ảnh hưởng CI/CD pipeline thế nào?

#### Pipeline execution cost

```
GitFlow:     5 branch types × pipeline per branch = 5x CI cost
             feature/ + develop + release/ + hotfix/ + main
             
GitHub Flow: 2 branch types × pipeline per branch = 2x CI cost
             feature/ + main
             
Trunk-based: 1 branch + short-lived = ~1.2x CI cost
             main + tiny feature branches
```

#### Build time impact

| Metric | GitFlow | GitHub Flow | Trunk-based |
|--------|---------|-------------|-------------|
| Avg PR size | 500-2000 LOC | 100-500 LOC | 50-200 LOC |
| CI time/PR | 15-30 min | 10-15 min | 5-10 min |
| Merge conflict rate | 30-50% | 10-20% | 1-5% |
| Time to resolve conflict | 30-120 min | 10-30 min | 5-10 min |

#### Monorepo performance at scale

```bash
# Problem: clone toàn bộ monorepo 10GB
git clone https://github.com/company/monorepo.git
# → 5 phút, tốn bandwidth

# Solution 1: Shallow clone
git clone --depth 1 https://github.com/company/monorepo.git
# → 30 giây

# Solution 2: Sparse checkout (chỉ lấy thư mục cần)
git clone --filter=blob:none --sparse https://github.com/company/monorepo.git
cd monorepo
git sparse-checkout set services/user-service packages/shared-utils

# Solution 3: Git LFS cho file lớn
git lfs track "*.bin" "*.model" "*.wasm"
```

### DORA Metrics theo workflow

Trunk-based development tương quan mạnh với DORA metrics cao (theo State of DevOps Report):

| Metric | GitFlow typical | Trunk-based typical |
|--------|----------------|---------------------|
| Deployment frequency | Weekly-Monthly | Daily-Hourly |
| Lead time for changes | 1-6 months | < 1 day |
| Change failure rate | 16-30% | 0-15% |
| MTTR | 1-7 days | < 1 hour |

---

## 7. Security & Reliability Considerations

### Branch Protection

```yaml
# GitHub branch protection rules cho main
branch_protection:
  main:
    required_reviews: 2
    dismiss_stale_reviews: true
    require_code_owner_review: true
    required_status_checks:
      - "ci/lint"
      - "ci/test"
      - "ci/security-scan"
    enforce_admins: true        # Admin cũng phải follow rules
    restrict_pushes: true       # Không push trực tiếp
    require_signed_commits: true # GPG signing
    require_linear_history: true # No merge commits
```

### Secret trong Git

```bash
# ❌ KHÔNG BAO GIỜ commit secret
echo "DATABASE_URL=postgres://user:password@host:5432/db" > .env
git add .env
git commit -m "add config"  # SECRET LEAKED!

# Ngay cả khi xóa, secret vẫn trong git history
git rm .env
git commit -m "remove secret"
# → Secret vẫn ở commit trước!

# ✅ .gitignore
echo ".env" >> .gitignore
echo "*.key" >> .gitignore
echo "*.pem" >> .gitignore

# ✅ Pre-commit hook scan secret
# Dùng tool: gitleaks, trufflehog, git-secrets
```

### Signed Commits

```bash
# Setup GPG key
gpg --full-generate-key
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true

# Signed commit
git commit -S -m "verified commit"

# Verify
git log --show-signature
```

### Rollback Strategy

```bash
# Strategy 1: Revert commit (safe, tạo commit mới)
git revert HEAD          # Revert commit cuối
git revert abc123        # Revert commit cụ thể
git push origin main

# Strategy 2: Revert merge commit
git revert -m 1 MERGE_COMMIT_SHA

# Strategy 3: Deploy previous tag
git checkout v1.2.0
# Trigger deployment pipeline

# ❌ KHÔNG dùng git reset --hard trên shared branch
# git reset --hard HEAD~1  # NGUY HIỂM: rewrite history
```

### Blast Radius Analysis

| Workflow | Blast radius khi merge lỗi |
|----------|---------------------------|
| GitFlow | Chỉ release branch bị ảnh hưởng → fix trước khi release |
| GitHub Flow | Main bị ảnh hưởng → production nếu auto-deploy |
| Trunk-based | Main bị ảnh hưởng → nhưng change nhỏ → dễ revert |

---

## 8. Hands-on Example

### Exercise 1: Thiết kế Git workflow cho team

#### Scenario A: Team 10 developer — E-commerce startup

```bash
# Tạo repo mô phỏng
mkdir -p /tmp/git-workflow-demo && cd /tmp/git-workflow-demo
git init
echo "# E-commerce Platform" > README.md
git add README.md
git commit -m "Initial commit"

# Setup GitHub Flow
# Step 1: Protect main branch (trên GitHub UI hoặc CLI)
# Step 2: Tạo feature branch
git checkout -b feature/add-product-api

# Step 3: Develop
cat > product-api.py << 'EOF'
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/products', methods=['GET'])
def list_products():
    return jsonify({"products": [], "total": 0})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(port=8080)
EOF

git add product-api.py
git commit -m "feat: add product listing API endpoint"

# Step 4: Push và tạo PR
git push origin feature/add-product-api
# gh pr create --title "feat: add product listing API" --body "..."

# Step 5: Sau review, merge
git checkout main
git merge feature/add-product-api
git tag v0.1.0
git push origin main --tags

# Step 6: Cleanup
git branch -d feature/add-product-api

# Verify
git log --oneline --graph
```

**Expected output:**
```
*   a1b2c3d (HEAD -> main, tag: v0.1.0) Merge branch 'feature/add-product-api'
|\
| * d4e5f6g feat: add product listing API endpoint
|/
* 1234567 Initial commit
```

#### Scenario B: Team 100 developer — Enterprise platform

```bash
# GitFlow setup
cd /tmp && mkdir git-flow-demo && cd git-flow-demo
git init
echo "# Enterprise Platform" > README.md
git add README.md
git commit -m "Initial commit"

# Tạo develop branch
git checkout -b develop
git push origin develop

# Developer A: feature branch
git checkout -b feature/JIRA-123-user-auth develop
echo "auth module v1" > auth.py
git add auth.py
git commit -m "feat(JIRA-123): implement user authentication"
# → PR to develop

# Release Manager: tạo release branch
git checkout develop
git checkout -b release/v1.0.0
echo "1.0.0" > VERSION
git add VERSION
git commit -m "chore: bump version to 1.0.0"

# QA tìm bug → fix trên release branch
echo "auth module v1 - fixed" > auth.py
git add auth.py
git commit -m "fix: auth token expiry validation"

# Release: merge to main + tag
git checkout main
git merge release/v1.0.0 --no-ff
git tag -a v1.0.0 -m "Release v1.0.0"

# Backport to develop
git checkout develop
git merge release/v1.0.0 --no-ff

# Cleanup
git branch -d release/v1.0.0

# Verify
git log --oneline --graph --all
```

### Exercise 2: Viết Release Checklist

```bash
# Tạo release checklist template
cat > RELEASE_CHECKLIST.md << 'CHECKLIST'
# Release Checklist — v{VERSION}

## Pre-release
- [ ] All features merged to release branch
- [ ] All CI/CD pipelines green
- [ ] Security scan passed (0 critical/high CVEs)
- [ ] Database migration tested on staging
- [ ] API backward compatibility verified
- [ ] Performance test passed (< 200ms p99 latency)
- [ ] Load test passed (handles 2x expected traffic)

## Release
- [ ] Version bumped in all manifests
- [ ] CHANGELOG.md updated
- [ ] Release branch merged to main
- [ ] Git tag created (signed)
- [ ] Container images tagged and pushed
- [ ] Helm chart version updated

## Deployment
- [ ] Staging deployment successful
- [ ] Smoke tests passed on staging
- [ ] Canary deployment (10% traffic)
- [ ] Monitor error rate for 15 minutes
- [ ] Full rollout (100% traffic)
- [ ] Health checks passing

## Post-release
- [ ] Release branch merged back to develop
- [ ] Release branch deleted
- [ ] Release notes published
- [ ] Team notified in Slack
- [ ] Monitoring dashboard reviewed (30 min post-deploy)
- [ ] Rollback plan documented and tested

## Rollback Plan
- Rollback command: `kubectl rollout undo deployment/app`
- Previous version: v{PREV_VERSION}
- Rollback criteria: error rate > 1% OR p99 > 500ms
- Rollback owner: {ON-CALL ENGINEER}
CHECKLIST

echo "Release checklist created!"
cat RELEASE_CHECKLIST.md
```

### Exercise 3: Automated Versioning

```bash
# Conventional Commits → Automated version bump

# Install commitlint (nếu dùng Node.js)
# npm install -g @commitlint/cli @commitlint/config-conventional

# Commit convention:
# feat: → MINOR bump (0.1.0 → 0.2.0)
# fix:  → PATCH bump (0.1.0 → 0.1.1)
# feat!: hoặc BREAKING CHANGE: → MAJOR bump (0.1.0 → 1.0.0)

# Ví dụ script tính version (bash)
cat > auto-version.sh << 'SCRIPT'
#!/bin/bash
set -euo pipefail

CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "0.0.0")
echo "Current version: $CURRENT_VERSION"

IFS='.' read -r MAJOR MINOR PATCH <<< "${CURRENT_VERSION#v}"

# Đọc commit messages since last tag
COMMITS=$(git log "${CURRENT_VERSION}..HEAD" --pretty=format:"%s" 2>/dev/null || git log --pretty=format:"%s")

if echo "$COMMITS" | grep -qE "^feat!:|BREAKING CHANGE:"; then
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
    BUMP_TYPE="MAJOR"
elif echo "$COMMITS" | grep -qE "^feat(\(.+\))?:"; then
    MINOR=$((MINOR + 1))
    PATCH=0
    BUMP_TYPE="MINOR"
elif echo "$COMMITS" | grep -qE "^fix(\(.+\))?:"; then
    PATCH=$((PATCH + 1))
    BUMP_TYPE="PATCH"
else
    echo "No version bump needed"
    exit 0
fi

NEW_VERSION="v${MAJOR}.${MINOR}.${PATCH}"
echo "Bump type: $BUMP_TYPE"
echo "New version: $NEW_VERSION"

# Tag
git tag -a "$NEW_VERSION" -m "Release $NEW_VERSION"
echo "Tagged $NEW_VERSION"
SCRIPT

chmod +x auto-version.sh
echo "Auto-version script created!"
```

### Cleanup

```bash
# Dọn dẹp
rm -rf /tmp/git-workflow-demo
rm -rf /tmp/git-flow-demo
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Merge Conflict Storm

**Triệu chứng**: Mỗi PR đều có conflict, developer mất hàng giờ resolve.

**Nguyên nhân**: Feature branch sống quá lâu (> 1 tuần), nhiều người sửa cùng file.

**Debug:**
```bash
# Xem branch diverge bao nhiêu so với main
git rev-list --count main..feature/my-branch
# Output: 47  ← quá nhiều commits, cần merge thường xuyên

# Xem file nào thường conflict
git log --diff-filter=M --name-only --pretty=format: | sort | uniq -c | sort -rn | head
```

**Fix:**
- Merge main vào feature branch hàng ngày: `git merge main`
- Hoặc rebase: `git rebase main`
- Chia file lớn thành module nhỏ
- Dùng CODEOWNERS để giảm overlap

### Pitfall 2: "Works on my branch" — Integration lỗi

**Triệu chứng**: Feature works trên branch, break khi merge vào main.

```bash
# Debug: so sánh diff giữa feature branch và main
git diff main...feature/my-branch --stat

# Kiểm tra có file nào bị conflict resolution sai
git log --merge  # Xem merge commits
```

### Pitfall 3: Tag bị overwrite

```bash
# ❌ Đừng move tag
git tag -f v1.0.0  # NGUY HIỂM: overwrite tag
git push --force --tags  # NGUY HIỂM: force push tags

# ✅ Immutable tags
# Nếu tag sai → tạo tag mới
git tag v1.0.1
```

### Pitfall 4: Secret trong Git History

**Case Study**: Team push AWS credentials vào repo. Phát hiện sau 2 ngày. Rotate key ngay lập tức, nhưng key đã bị scan bởi bot tự động trong 30 phút đầu.

```bash
# Detect secrets đã committed
# Install gitleaks
gitleaks detect --source . --verbose

# Nếu đã commit secret:
# 1. NGAY LẬP TỨC rotate credential
# 2. Remove từ history (nếu repo private)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/secret" \
  --prune-empty HEAD
# Hoặc dùng BFG Repo Cleaner (nhanh hơn)
# 3. Force push (chỉ khi repo private và team nhỏ)
```

### Pitfall 5: Release branch diverge

```bash
# Problem: release branch sống quá lâu, diverge từ develop
# Debug
git log --oneline develop..release/v1.0 | wc -l
# Output: 23  ← 23 commits trên release mà develop không có

# Fix: merge release → develop thường xuyên
git checkout develop
git merge release/v1.0
```

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ bài trước

| Bài | Kiến thức áp dụng |
|-----|-------------------|
| Day 1 (DevOps/SRE) | DORA metrics bị ảnh hưởng trực tiếp bởi Git workflow |
| Day 5 (Automation) | Script automation cho release process (bash scripts) |
| Day 5 (Bash) | Git hooks, pre-commit scripts, auto-versioning |

### Preview bài sau

| Bài | Mở rộng |
|-----|---------|
| Day 7 (Mini-project) | Áp dụng Git workflow + automation vào project thực |
| Day 8-9 (Docker) | Container image versioning strategy |
| Day 32-34 (CI/CD) | Pipeline chạy theo branch strategy đã thiết kế |
| Day 31 (GitOps) | Git as source of truth cho infrastructure |

---

## 11. Tài liệu tham khảo

### Must-read
- [A successful Git branching model (Vincent Driessen)](https://nvie.com/posts/a-successful-git-branching-model/) — Bài gốc về GitFlow
- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow) — Official GitHub docs
- [Trunk-Based Development](https://trunkbaseddevelopment.com/) — Comprehensive guide
- [Semantic Versioning 2.0.0](https://semver.org/) — SemVer specification

### Nice-to-have
- [Conventional Commits](https://www.conventionalcommits.org/) — Commit message convention
- [DORA State of DevOps Report](https://dora.dev/) — Research linking trunk-based dev to performance
- [Monorepo Tools](https://monorepo.tools/) — Comparison of monorepo build tools

### Deep-dive
- [Google's Monorepo (Why Google Stores Billions of Lines of Code in a Single Repository)](https://research.google/pubs/pub45424/) — Google Research paper
- [Patterns for Managing Source Code Branches (Martin Fowler)](https://martinfowler.com/articles/branching-patterns.html) — Deep analysis of branching patterns
- ["Accelerate" by Nicole Forsgren, Jez Humble, Gene Kim](https://itrevolution.com/product/accelerate/) — Book linking practices to outcomes

