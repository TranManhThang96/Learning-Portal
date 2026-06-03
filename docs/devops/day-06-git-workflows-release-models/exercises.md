# Day 6: Exercises — Git Workflows & Release Models

---

## Exercise 1: Git Workflow Basics (Easy)

### Context

Bạn vừa join một startup 8 developer, đang build một SaaS platform. Team hiện tại không có Git workflow rõ ràng — ai cũng push trực tiếp vào `main`, không có PR review, không có versioning strategy. Tuần trước, một developer push code lỗi vào main lúc 5PM thứ Sáu, gây downtime 3 giờ.

### Yêu cầu

1. Tạo một Git repository mới mô phỏng dự án.
2. Setup branch protection cho `main` (mô phỏng bằng script).
3. Thực hiện GitHub Flow: tạo feature branch → commit → merge.
4. Tạo tag version đầu tiên theo SemVer.
5. Viết `.gitignore` phù hợp cho project.

### Expected Outcome

- Repository có `main` branch protected (conceptual).
- Ít nhất 2 feature branch đã merge vào main.
- Tag `v0.1.0` và `v0.2.0` trên main.
- File `.gitignore` loại bỏ `.env`, `node_modules/`, `*.log`, v.v.
- Git log hiển thị clean history với merge commits.

### Hint

- Dùng `git checkout -b feature/xxx` để tạo branch.
- Dùng `git tag -a v0.1.0 -m "message"` để tạo annotated tag.
- Xem graph: `git log --oneline --graph --all`.

### Acceptance Criteria

- [ ] Repository initialized với README.md
- [ ] Ít nhất 2 feature branches tạo và merge
- [ ] Tags `v0.1.0`, `v0.2.0` tồn tại
- [ ] `.gitignore` có ít nhất 5 patterns phù hợp
- [ ] `git log --graph` cho thấy branching/merging rõ ràng

### Bonus Challenge

Thêm pre-commit hook kiểm tra commit message theo Conventional Commits format (`feat:`, `fix:`, `chore:`, v.v.).

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
# Exercise 1 Solution

# 1. Tạo repository
mkdir -p /tmp/ex1-git-workflow && cd /tmp/ex1-git-workflow
git init
git config user.name "Dev"
git config user.email "dev@example.com"

# 2. Initial setup
cat > README.md << 'EOF'
# SaaS Platform

## Development

- Branch from `main` for features
- Use PR for code review
- Follow Conventional Commits
EOF

cat > .gitignore << 'EOF'
# Dependencies
node_modules/
vendor/
.venv/

# Environment
.env
.env.local
.env.*.local

# Logs
*.log
logs/

# Build
dist/
build/
*.pyc
__pycache__/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Secrets
*.key
*.pem
*.p12
credentials.json
EOF

git add .
git commit -m "chore: initial project setup"

# 3. Feature 1: User API
git checkout -b feature/user-api
cat > user-api.py << 'EOF'
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
def list_users():
    return jsonify({"users": [], "total": 0})
EOF
git add user-api.py
git commit -m "feat: add user listing API endpoint"

# Thêm health check
cat > health.py << 'EOF'
@app.route('/health')
def health():
    return jsonify({"status": "ok"})
EOF
git add health.py
git commit -m "feat: add health check endpoint"

# Merge feature 1
git checkout main
git merge feature/user-api --no-ff -m "Merge feature/user-api"
git tag -a v0.1.0 -m "Release v0.1.0: User API"
git branch -d feature/user-api

# 4. Feature 2: Product API
git checkout -b feature/product-api
cat > product-api.py << 'EOF'
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/api/products', methods=['GET'])
def list_products():
    return jsonify({"products": [], "total": 0})
EOF
git add product-api.py
git commit -m "feat: add product listing API endpoint"

git checkout main
git merge feature/product-api --no-ff -m "Merge feature/product-api"
git tag -a v0.2.0 -m "Release v0.2.0: Product API"
git branch -d feature/product-api

# 5. Verify
echo "=== Git Log ==="
git log --oneline --graph --all

echo ""
echo "=== Tags ==="
git tag -l

echo ""
echo "=== .gitignore ==="
cat .gitignore | head -20

# Bonus: Pre-commit hook
mkdir -p .git/hooks
cat > .git/hooks/commit-msg << 'HOOK'
#!/bin/bash
COMMIT_MSG=$(cat "$1")
PATTERN="^(feat|fix|chore|docs|style|refactor|test|ci|perf|build)(\(.+\))?: .+"

if ! echo "$COMMIT_MSG" | grep -qE "$PATTERN"; then
    echo "ERROR: Commit message does not follow Conventional Commits format."
    echo "Expected: type(scope): description"
    echo "Types: feat, fix, chore, docs, style, refactor, test, ci, perf, build"
    echo "Got: $COMMIT_MSG"
    exit 1
fi
HOOK
chmod +x .git/hooks/commit-msg
echo ""
echo "Pre-commit hook installed!"

# Cleanup note
echo ""
echo "Cleanup: rm -rf /tmp/ex1-git-workflow"
```

</details>

---

## Exercise 2: Hotfix Flow & Versioning (Medium)

### Context

Bạn là lead engineer của team 20 người. Production đang chạy `v1.2.0`. Vừa nhận alert: endpoint `/api/payments` trả về 500 error do bug validate credit card. Team đang phát triển `v1.3.0` trên develop branch với nhiều feature mới chưa sẵn sàng release.

Bạn cần:
1. Tạo hotfix từ `main` (không phải từ develop).
2. Fix bug, test, tag `v1.2.1`.
3. Backport fix vào develop.
4. Đảm bảo không kéo feature chưa sẵn sàng vào production.

### Yêu cầu

1. Setup repository mô phỏng trạng thái hiện tại (main ở v1.2.0, develop có features mới).
2. Thực hiện hotfix flow đầy đủ.
3. Viết script auto-versioning đơn giản.
4. Verify version consistency sau hotfix.
5. Viết release note cho hotfix.

### Expected Outcome

- `main` có tag `v1.2.1` với fix bug.
- `develop` cũng có fix (backport).
- `develop` vẫn giữ feature mới chưa release.
- Release note file mô tả thay đổi.
- Script auto-version hoạt động đúng.

### Hint

- Hotfix branch từ `main`: `git checkout -b hotfix/payment-validation main`
- Merge hotfix vào CẢ main VÀ develop.
- Dùng `git log main..develop` để verify develop có thêm features.

### Acceptance Criteria

- [ ] Hotfix branch tạo từ `main`, không phải `develop`
- [ ] Tag `v1.2.1` trên main sau hotfix
- [ ] Fix đã backport vào develop
- [ ] Develop vẫn có features mới (không mất code)
- [ ] Release note file tồn tại
- [ ] Auto-version script chạy được

### Bonus Challenge

Viết script kiểm tra xem hotfix đã được backport vào tất cả active branch chưa (main, develop, release/*).

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
# Exercise 2 Solution: Hotfix Flow

set -euo pipefail

WORKDIR="/tmp/ex2-hotfix-flow"
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR" && cd "$WORKDIR"

echo "=== Setup Repository ==="
git init
git config user.name "Lead Engineer"
git config user.email "lead@example.com"

# Initial release v1.0.0
echo "# Payment Service" > README.md
cat > payment.py << 'EOF'
def validate_card(card_number):
    """Basic card validation."""
    if len(card_number) < 13:
        return False
    return True

def process_payment(amount, card_number):
    if not validate_card(card_number):
        raise ValueError("Invalid card")
    return {"status": "success", "amount": amount}
EOF
git add .
git commit -m "feat: initial payment service"
git tag -a v1.0.0 -m "Release v1.0.0"

# Setup develop branch
git checkout -b develop

# v1.1.0 - minor feature
echo "def list_transactions(): return []" >> payment.py
git add payment.py
git commit -m "feat: add transaction listing"
git checkout main
git merge develop --no-ff -m "Release v1.1.0"
git tag -a v1.1.0 -m "Release v1.1.0"
git checkout develop
git merge main

# v1.2.0 - another feature
echo "def refund(transaction_id): return {'status': 'refunded'}" >> payment.py
git add payment.py
git commit -m "feat: add refund capability"
git checkout main
git merge develop --no-ff -m "Release v1.2.0"
git tag -a v1.2.0 -m "Release v1.2.0"
git checkout develop
git merge main

# New features on develop (v1.3.0 in progress)
cat > subscription.py << 'EOF'
def create_subscription(plan, user_id):
    return {"plan": plan, "user_id": user_id, "status": "active"}
EOF
git add subscription.py
git commit -m "feat: add subscription module (WIP)"

echo "def analytics(): return {'revenue': 0}" >> payment.py
git add payment.py
git commit -m "feat: add payment analytics (WIP)"

echo ""
echo "=== Current State ==="
echo "Main branch (production): $(git log main --oneline -1)"
echo "Develop branch (WIP): $(git log develop --oneline -1)"
echo "Features on develop not in main:"
git log main..develop --oneline

# =========================
# HOTFIX FLOW START
# =========================
echo ""
echo "=== HOTFIX: Payment Validation Bug ==="

# Step 1: Branch from main (NOT develop!)
git checkout main
git checkout -b hotfix/payment-validation

# Step 2: Fix the bug
cat > payment.py << 'EOF'
def validate_card(card_number):
    """Card validation with proper checks."""
    if not card_number or not isinstance(card_number, str):
        return False
    cleaned = card_number.replace(" ", "").replace("-", "")
    if len(cleaned) < 13 or len(cleaned) > 19:
        return False
    if not cleaned.isdigit():
        return False
    return True

def process_payment(amount, card_number):
    if not validate_card(card_number):
        raise ValueError("Invalid card number")
    if amount <= 0:
        raise ValueError("Amount must be positive")
    return {"status": "success", "amount": amount}

def list_transactions(): return []

def refund(transaction_id): return {'status': 'refunded'}
EOF
git add payment.py
git commit -m "fix: validate card number format and handle edge cases"

# Step 3: Add test
cat > test_payment.py << 'EOF'
from payment import validate_card

def test_valid_card():
    assert validate_card("4111111111111111") == True

def test_short_card():
    assert validate_card("411") == False

def test_empty_card():
    assert validate_card("") == False
    assert validate_card(None) == False

def test_card_with_spaces():
    assert validate_card("4111 1111 1111 1111") == True

def test_non_numeric():
    assert validate_card("abcdefghijklmn") == False

print("All tests passed!")
for test in [test_valid_card, test_short_card, test_empty_card, 
             test_card_with_spaces, test_non_numeric]:
    test()
    print(f"  ✓ {test.__name__}")
EOF
git add test_payment.py
git commit -m "test: add card validation tests"

# Step 4: Merge to main and tag
git checkout main
git merge hotfix/payment-validation --no-ff -m "Merge hotfix: payment validation (v1.2.1)"
git tag -a v1.2.1 -m "Hotfix v1.2.1: Fix card validation"

# Step 5: Backport to develop
git checkout develop
git merge hotfix/payment-validation --no-ff -m "Backport hotfix: payment validation"

# Step 6: Cleanup
git branch -d hotfix/payment-validation

# Step 7: Create release note
cat > RELEASE_v1.2.1.md << 'RELEASE'
# Release v1.2.1 — Hotfix

## Date
$(date +%Y-%m-%d)

## Summary
Emergency fix for payment card validation bug causing 500 errors on `/api/payments`.

## Changes
- **fix**: Validate card number format - check length (13-19 digits), numeric only, handle null/empty
- **test**: Add comprehensive card validation test suite

## Impact
- Affected endpoint: `/api/payments`
- Error type: 500 Internal Server Error
- Duration: ~2 hours
- Root cause: Missing input validation for non-numeric and short card numbers

## Rollback
If issues found: `git checkout v1.2.0 && deploy`
RELEASE
git checkout main
git add RELEASE_v1.2.1.md 2>/dev/null || true

# Step 8: Auto-version script
cat > auto-version.sh << 'SCRIPT'
#!/bin/bash
set -euo pipefail

LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo "Latest tag: $LATEST_TAG"

VERSION="${LATEST_TAG#v}"
IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"

COMMITS=$(git log "${LATEST_TAG}..HEAD" --pretty=format:"%s" 2>/dev/null || echo "")

if [ -z "$COMMITS" ]; then
    echo "No new commits since $LATEST_TAG"
    exit 0
fi

if echo "$COMMITS" | grep -qE "^feat!:|BREAKING CHANGE:"; then
    MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0
    echo "MAJOR bump (breaking change)"
elif echo "$COMMITS" | grep -qE "^feat"; then
    MINOR=$((MINOR + 1)); PATCH=0
    echo "MINOR bump (new feature)"
elif echo "$COMMITS" | grep -qE "^fix"; then
    PATCH=$((PATCH + 1))
    echo "PATCH bump (bug fix)"
else
    echo "No version-relevant commits"
    exit 0
fi

echo "New version: v${MAJOR}.${MINOR}.${PATCH}"
SCRIPT
chmod +x auto-version.sh

echo ""
echo "=== Verification ==="
echo ""
echo "Main branch log:"
git log main --oneline -5
echo ""
echo "Tags:"
git tag -l -n1
echo ""
echo "Develop has WIP features:"
git log main..develop --oneline
echo ""
echo "Develop also has the fix:"
git log develop --oneline --grep="validate card"
echo ""
echo "Test the fix:"
python3 test_payment.py 2>/dev/null || echo "(Python not available, but test file created)"

# Bonus: Check backport status
echo ""
echo "=== Backport Status Check ==="
HOTFIX_COMMIT=$(git log main --oneline --grep="validate card" -1 | awk '{print $1}')
echo "Hotfix commit: $HOTFIX_COMMIT"
for branch in main develop; do
    if git branch --contains "$HOTFIX_COMMIT" | grep -q "$branch"; then
        echo "  ✓ $branch contains the fix"
    else
        echo "  ✗ $branch MISSING the fix!"
    fi
done

echo ""
echo "Cleanup: rm -rf $WORKDIR"
```

</details>

---

## Exercise 3: Workflow Design cho Tổ chức Lớn (Hard)

### Context

Bạn được thuê làm DevOps consultant cho một fintech company có:
- 120 developer, chia thành 15 team
- 8 microservices chính + 20 internal libraries
- Hiện tại dùng GitFlow nhưng đang gặp vấn đề:
  - Release cycle 1 tháng, deploy chậm
  - Merge conflict chiếm 25% thời gian developer
  - Hotfix phải cherry-pick qua 5 branch, thường miss
  - CI pipeline chạy 45 phút cho mỗi PR
  - Không ai biết version nào đang chạy ở production
- Yêu cầu compliance: mọi change phải có audit trail, approval từ 2 reviewer

### Yêu cầu

1. **Phân tích** vấn đề hiện tại (root cause, không chỉ triệu chứng).
2. **Đề xuất** Git workflow mới phù hợp.
3. **Thiết kế** versioning strategy cho microservices và libraries.
4. **Viết** migration plan từ GitFlow sang workflow mới (phased approach).
5. **Tạo** branch naming convention document.
6. **Viết** release checklist phù hợp regulated industry.
7. **Thiết kế** monorepo vs polyrepo strategy.

### Expected Outcome

- Document phân tích 2-3 trang.
- Proposed workflow diagram (ASCII/mermaid).
- Versioning strategy table.
- Migration plan (3 phases).
- Branch naming convention.
- Release checklist cho fintech.
- Decision record monorepo vs polyrepo.

### Hint

- Trunk-based development + feature flags có thể giải quyết merge conflict.
- Compliance yêu cầu không mâu thuẫn với trunk-based (signed commits + PR review vẫn OK).
- Cân nhắc hybrid: trunk-based cho services, GitFlow cho shared libraries.
- Migration nên phased: pilot team → expand → full adoption.

### Acceptance Criteria

- [ ] Phân tích root cause đầy đủ (không chỉ liệt kê triệu chứng)
- [ ] Workflow mới giải quyết được 4 vấn đề chính
- [ ] Versioning strategy cover microservices + libraries
- [ ] Migration plan có rollback plan cho mỗi phase
- [ ] Branch naming convention rõ ràng, consistent
- [ ] Release checklist có compliance requirements
- [ ] Monorepo/polyrepo decision có trade-off analysis

### Bonus Challenge

1. Thiết kế CODEOWNERS file cho 15 team với shared code ownership rules.
2. Viết script CI tối ưu: chỉ build services bị ảnh hưởng bởi PR (affected service detection).
3. Tạo dashboard mockup tracking: deployment frequency, lead time, change failure rate per team.

<details>
<summary>Solution</summary>

```markdown
# Fintech Git Workflow Redesign

## 1. Root Cause Analysis

### Triệu chứng vs Nguyên nhân

| Triệu chứng | Root Cause |
|---|---|
| Release cycle 1 tháng | GitFlow release branch kéo dài, stabilization lâu |
| Merge conflict 25% | Feature branch sống 2-4 tuần, diverge quá xa |
| Cherry-pick miss | Hotfix phải apply lên nhiều branch manually |
| CI 45 phút | Build toàn bộ monolith, không selective |
| Không biết version | Không có automated versioning, manual tracking |

### Nguyên nhân gốc
GitFlow được thiết kế cho **packaged software** (release scheduled, multiple versions).
Fintech SaaS chỉ có **1 production version** → GitFlow gây overhead không cần thiết.

## 2. Proposed Workflow: Modified Trunk-based Development

```
main ──●──●──●──●──●──●──●── (always deployable)
        \  /  \  /
        short  short      Feature flags cho
        branch branch     features chưa sẵn sàng
        (<1d)  (<2d)

Protected by:
- 2 reviewer approval (compliance)
- Signed commits (audit trail)  
- CI pipeline pass (quality gate)
- Security scan pass (compliance)
```

### Tại sao không phải pure trunk-based?
- Compliance yêu cầu PR review → cần short-lived branch + PR
- Nhưng branch < 2 ngày, merge daily

## 3. Versioning Strategy

| Artifact | Strategy | Format | Example |
|---|---|---|---|
| Microservice | SemVer + SHA | `v{M}.{m}.{p}-{sha}` | `v1.5.2-abc123d` |
| Shared library | Strict SemVer | `v{M}.{m}.{p}` | `v2.1.0` |
| Container image | SemVer + SHA | `{service}:v1.5.2-abc123d` | `payment:v1.5.2-abc123d` |
| Helm chart | SemVer | `v{M}.{m}.{p}` | `v0.3.1` |
| API (external) | API version + SemVer | `v{API}/v{M}.{m}.{p}` | `v2/v1.5.2` |

Automated by: conventional commits + semantic-release.

## 4. Migration Plan

### Phase 1: Pilot (Week 1-4) — 2 teams
- Chọn 2 team ít dependency nhất
- Chuyển sang trunk-based + feature flags
- Metrics: deployment frequency, lead time, conflict rate
- Rollback: quay lại GitFlow nếu conflict rate tăng

### Phase 2: Expand (Week 5-8) — 8 teams
- Các team còn lại adopt
- Setup feature flag service (Unleash/LaunchDarkly)
- Training sessions
- Rollback: individual team quay lại nếu cần

### Phase 3: Full Adoption (Week 9-12) — all teams
- Deprecate develop branch
- Update CI/CD pipeline
- Compliance audit cho workflow mới
- Rollback: keep GitFlow tooling 1 tháng sau full adoption

## 5. Branch Naming Convention

```
# Feature
feature/{JIRA-ID}-{short-description}
feature/PAY-123-add-card-validation

# Bug fix  
fix/{JIRA-ID}-{short-description}
fix/PAY-456-null-card-error

# Hotfix (production emergency)
hotfix/{JIRA-ID}-{short-description}
hotfix/PAY-789-payment-timeout

# Release (chỉ cho shared libraries)
release/v{version}
release/v2.0.0

# Chore (non-functional)
chore/{short-description}
chore/update-dependencies
```

Rules:
- Lowercase only
- Dashes between words
- Max 50 characters total
- Must include JIRA ticket ID

## 6. Release Checklist (Fintech Compliance)

### Pre-deploy
- [ ] 2 code reviewers approved (1 must be senior/lead)
- [ ] All commits signed (GPG)
- [ ] CI pipeline green: lint, test, security scan
- [ ] SAST scan: 0 critical findings
- [ ] Dependency scan: no known CVEs in HIGH/CRITICAL
- [ ] Database migration reviewed by DBA
- [ ] API contract backward compatible (or versioned)
- [ ] Feature flags configured for new features
- [ ] Rollback procedure documented

### Deploy
- [ ] Canary deployment (5% traffic, 15 min)
- [ ] Error rate < 0.1% during canary
- [ ] Latency p99 < 200ms during canary
- [ ] Full rollout
- [ ] Health checks passing all regions

### Post-deploy
- [ ] Monitoring dashboard reviewed (30 min)
- [ ] Audit log entry created
- [ ] Release notes published to stakeholders
- [ ] Compliance team notified (for PCI-DSS scope changes)

## 7. Monorepo vs Polyrepo Decision

**Recommendation: Polyrepo with shared library registry**

| Factor | Monorepo | Polyrepo | Decision |
|---|---|---|---|
| Team autonomy | ⚠️ Shared ownership complex | ✅ Clear ownership | Polyrepo |
| Compliance audit | ⚠️ Harder to scope | ✅ Per-service audit | Polyrepo |
| CI/CD speed | ⚠️ Need selective build | ✅ Independent pipeline | Polyrepo |
| Shared code | ✅ Easy import | ⚠️ Need package registry | Mitigate with registry |
| Atomic changes | ✅ Single PR | ⚠️ Multi-repo coordination | Accept trade-off |

Shared libraries → internal npm/pypi registry, versioned independently.
```

```bash
# Bonus: CODEOWNERS example
cat > CODEOWNERS << 'EOF'
# Payment Team
services/payment-service/ @fintech/team-payment
libs/payment-sdk/ @fintech/team-payment

# User Team  
services/user-service/ @fintech/team-user
services/auth-service/ @fintech/team-user

# Platform Team (must review infra changes)
infra/ @fintech/team-platform
.github/ @fintech/team-platform
Dockerfile @fintech/team-platform

# Security Team (must review security-sensitive)
**/auth/** @fintech/team-security
**/crypto/** @fintech/team-security
**/secrets/** @fintech/team-security

# All leads must review shared libraries
libs/shared-utils/ @fintech/tech-leads
EOF

# Bonus: Affected service detection script
cat > detect-affected.sh << 'SCRIPT'
#!/bin/bash
set -euo pipefail

BASE_BRANCH="${1:-main}"
CHANGED_FILES=$(git diff --name-only "$BASE_BRANCH"...HEAD)

AFFECTED_SERVICES=()

for file in $CHANGED_FILES; do
    if [[ "$file" == services/* ]]; then
        SERVICE=$(echo "$file" | cut -d'/' -f2)
        AFFECTED_SERVICES+=("$SERVICE")
    elif [[ "$file" == libs/* ]]; then
        LIB=$(echo "$file" | cut -d'/' -f2)
        # Find services that depend on this lib
        grep -rl "$LIB" services/*/package.json 2>/dev/null | while read dep; do
            SERVICE=$(echo "$dep" | cut -d'/' -f2)
            AFFECTED_SERVICES+=("$SERVICE")
        done
    fi
done

# Deduplicate
UNIQUE=$(echo "${AFFECTED_SERVICES[@]}" | tr ' ' '\n' | sort -u)
echo "Affected services:"
echo "$UNIQUE"
SCRIPT
chmod +x detect-affected.sh
echo "Scripts created!"
echo "Cleanup: rm CODEOWNERS detect-affected.sh"
```

</details>

---

## Tổng kết

| Exercise | Thời gian | Kỹ năng |
|----------|-----------|---------|
| Easy | 20 phút | Git basics, branching, tagging |
| Medium | 35 phút | Hotfix flow, versioning, release notes |
| Hard | 50 phút | Workflow design, migration planning, compliance |
| **Tổng** | **~105 phút** | (phù hợp 2 giờ/ngày bao gồm đọc lesson) |

