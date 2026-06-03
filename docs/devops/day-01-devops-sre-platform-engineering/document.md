# Day 1: Document — Comparison Matrix, Checklists & Templates

---

## 1. Comparison Matrix: DevOps vs SRE vs Platform Engineering

| Tiêu chí | DevOps | SRE | Platform Engineering |
|----------|--------|-----|---------------------|
| **Định nghĩa** | Văn hóa & practices phá bỏ silo Dev/Ops | Software engineering approach cho operations | Xây dựng Internal Developer Platform |
| **Xuất phát** | Phong trào cộng đồng (~2009) | Google (~2003) | Phát triển từ DevOps/SRE (~2020) |
| **Focus** | Collaboration, automation, measurement | Reliability, error budget, toil reduction | Developer experience, self-service |
| **Scope** | Toàn bộ tổ chức | Critical services | Tooling & platform |
| **Ai áp dụng** | Mọi engineer | SRE team + dev teams | Platform team phục vụ dev teams |
| **Metric chính** | DORA metrics | SLI/SLO/Error budget | Developer productivity, adoption rate |
| **On-call** | Developer on-call cho service mình | SRE + developer rotation | Platform on-call cho platform |
| **Code ratio** | Không quy định | 50% coding / 50% ops | 80%+ coding |
| **Khi nào bắt đầu** | Ngay lập tức, mọi team size | Team 30+, có critical services | Team 100+, nhiều teams |
| **Investment** | Thấp (culture change) | Trung bình (hire SRE + tooling) | Cao (team + platform build) |
| **Time to value** | 1-3 tháng | 3-6 tháng | 6-12 tháng |
| **Risk chính** | "DevOps team" trở thành Ops team mới | SRE burnout, bottleneck | Over-engineering, no adoption |
| **Scaling** | Tốt đến ~50 engineers | Tốt đến ~500 engineers | Cần thiết khi 100+ engineers |
| **Relationship** | Foundation | Implementation của DevOps | Evolution của DevOps/SRE |

### Khi nào KẾT HỢP?

```
Startup (5-20):     DevOps culture only
                    ┌──────────────┐
                    │   DevOps     │
                    └──────────────┘

Scale-up (20-80):   DevOps + SRE practices
                    ┌──────────────────────────┐
                    │   DevOps + Embedded SRE   │
                    └──────────────────────────┘

Mid-size (80-200):  DevOps + SRE + Basic Platform
                    ┌──────────────────────────────────────┐
                    │   DevOps + SRE + Shared Platform     │
                    └──────────────────────────────────────┘

Enterprise (200+):  Full stack
                    ┌──────────────────────────────────────────────────┐
                    │   DevOps Culture + SRE Teams + Platform Team     │
                    └──────────────────────────────────────────────────┘
```

---

## 2. DORA Metrics Reference Card

### 2.1. Benchmark Table (DORA 2023)

| Metric | Elite | High | Medium | Low |
|--------|-------|------|--------|-----|
| **Deployment Frequency** | On-demand (nhiều lần/ngày) | 1/tuần — 1/tháng | 1/tháng — 1/6 tháng | < 1/6 tháng |
| **Lead Time for Changes** | < 1 giờ | 1 ngày — 1 tuần | 1 tuần — 1 tháng | 1 — 6 tháng |
| **Change Failure Rate** | 0-15% | 16-30% | 31-45% | 46-60% |
| **MTTR** | < 1 giờ | < 1 ngày | < 1 tuần | > 6 tháng |

### 2.2. Cách đo từng metric

#### Deployment Frequency
```
Data source: CI/CD pipeline, deployment tool, git tags
Formula:     Count of successful production deployments / time period
Tool:        GitHub Actions logs, ArgoCD sync history, deployment webhook
```

#### Lead Time for Changes
```
Data source: Git commits + CI/CD pipeline
Formula:     Median time from first commit to production deployment
Tool:        GitHub PR created_at → deployment timestamp
Note:        Đo MEDIAN, không phải average (tránh outlier skew)
```

#### Change Failure Rate
```
Data source: Incident tracking + deployment history
Formula:     (Failed deployments / Total deployments) × 100%
Definition:  "Failed" = deployment gây incident, rollback, hotfix, 
             hoặc degradation cần fix
Tool:        Incident count correlation với deployment events
```

#### MTTR (Mean Time to Recovery)
```
Data source: Incident tracking system
Formula:     Average(incident_resolved_at - incident_detected_at)
Note:        Bắt đầu từ detection, không phải customer report
Tool:        PagerDuty, OpsGenie, hoặc custom incident tracking
```

### 2.3. DORA Metrics Collection Script Template

```bash
#!/bin/bash
# dora-quick-check.sh
# Ước lượng nhanh DORA metrics từ Git repository

REPO_PATH="${1:-.}"
DAYS="${2:-30}"

cd "$REPO_PATH" || exit 1

echo "════════════════════════════════════════"
echo "  DORA Metrics Quick Check"
echo "  Repo: $(basename "$(pwd)")"
echo "  Period: Last $DAYS days"
echo "════════════════════════════════════════"
echo ""

# Deployment Frequency
DEPLOYS=$(git log --oneline --after="$DAYS days ago" --first-parent main 2>/dev/null | wc -l)
PER_WEEK=$(echo "scale=1; $DEPLOYS * 7 / $DAYS" | bc 2>/dev/null || echo "?")
echo "📦 Deployment Frequency"
echo "   Deployments (est.): $DEPLOYS"
echo "   Per week: $PER_WEEK"
if (( DEPLOYS > DAYS )); then echo "   Level: ELITE"
elif (( DEPLOYS > DAYS/7 )); then echo "   Level: HIGH"
elif (( DEPLOYS > 1 )); then echo "   Level: MEDIUM"
else echo "   Level: LOW"
fi
echo ""

# Change Failure Rate
TOTAL=$(git log --oneline --after="$DAYS days ago" | wc -l)
FAILURES=$(git log --oneline --after="$DAYS days ago" \
  --grep="hotfix\|revert\|rollback\|fix.*prod\|emergency\|bugfix.*critical" -i | wc -l)
if [ "$TOTAL" -gt 0 ]; then
  CFR=$(echo "scale=1; $FAILURES * 100 / $TOTAL" | bc 2>/dev/null || echo "?")
else
  CFR="N/A"
fi
echo "🔥 Change Failure Rate"
echo "   Failures: $FAILURES / $TOTAL"
echo "   Rate: ${CFR}%"
echo ""

# Lead Time (simplified)
echo "⏱️  Lead Time for Changes"
echo "   Recent merges (analyze manually):"
git log --merges --format="   %ai  %s" --after="$DAYS days ago" | head -5
echo ""

echo "════════════════════════════════════════"
echo "  Run with: bash dora-quick-check.sh [repo-path] [days]"
echo "════════════════════════════════════════"
```

---

## 3. Engineering Maturity Assessment Template

### 3.1. Quick Assessment (5 phút)

Đánh giá nhanh 5 dimension, mỗi dimension cho điểm 1-5:

| Dimension | 1 (Ad-hoc) | 2 (Repeatable) | 3 (Defined) | 4 (Measured) | 5 (Optimized) | Score |
|-----------|------------|----------------|-------------|--------------|---------------|-------|
| **CI/CD** | Manual build & deploy | Basic CI, manual deploy | Automated pipeline, manual gates | Automated pipeline + quality gates | Progressive delivery, auto-rollback | __ |
| **Monitoring** | Không có | Uptime check only | APM + basic alerts | Metrics/logs/traces + dashboards | SLO-based alerting, error budget | __ |
| **Incident Mgmt** | Ai rảnh thì fix | Informal on-call | Documented process, severity levels | On-call rotation, postmortem | Automated response, chaos engineering | __ |
| **Infrastructure** | Manual server setup | Scripts/runbooks | IaC (partial) | IaC (full) + GitOps | Self-service platform, policy as code | __ |
| **Security** | Chưa nghĩ tới | Annual pen test | SAST/DAST in CI | Shift-left security, image scanning | Zero-trust, automated compliance | __ |

**Tổng: __/25**

| Score | Level | Recommendation |
|-------|-------|---------------|
| 5-10 | Foundation | Focus CI/CD và monitoring cơ bản |
| 11-15 | Developing | Standardize processes, start measuring |
| 16-20 | Mature | Optimize, add SRE practices |
| 21-25 | Advanced | Fine-tune, platform engineering, chaos |

### 3.2. Detailed Assessment Checklist

#### CI/CD Maturity
- [ ] Source code trong version control (Git)
- [ ] Branching strategy documented
- [ ] Automated build trên mỗi commit/PR
- [ ] Automated unit tests trong pipeline
- [ ] Automated integration tests
- [ ] Static code analysis (linting, SAST)
- [ ] Dependency vulnerability scanning (SCA)
- [ ] Container image scanning
- [ ] Automated deployment đến staging
- [ ] Automated deployment đến production
- [ ] Deployment không cần manual approval (auto-promote after tests)
- [ ] Rollback mechanism (< 5 phút)
- [ ] Canary / blue-green deployment
- [ ] Feature flags cho controlled rollout
- [ ] Pipeline as Code (không cấu hình qua UI)

#### Observability Maturity
- [ ] Application logs centralized
- [ ] Structured logging (JSON)
- [ ] Request/correlation ID trong logs
- [ ] Application metrics (latency, error rate, throughput)
- [ ] Infrastructure metrics (CPU, memory, disk, network)
- [ ] Custom business metrics
- [ ] Dashboards cho key services
- [ ] Alert rules cho critical metrics
- [ ] Alert routing đến đúng team
- [ ] Runbook link trong mỗi alert
- [ ] Distributed tracing
- [ ] Trace correlation với logs và metrics
- [ ] SLI defined cho critical services
- [ ] SLO tracked và reviewed
- [ ] Error budget policy

#### Incident Management Maturity
- [ ] Severity levels defined (SEV1-SEV4)
- [ ] On-call rotation schedule
- [ ] Escalation policy documented
- [ ] Incident response checklist
- [ ] Communication template (internal + external)
- [ ] War room / incident channel convention
- [ ] Incident Commander role defined
- [ ] Postmortem conducted cho mọi SEV1/SEV2
- [ ] Postmortem blameless
- [ ] Action items tracked đến completion
- [ ] Incident metrics tracked (frequency, MTTR, severity distribution)
- [ ] Regular incident drills / game days
- [ ] Automated incident detection
- [ ] Automated mitigation cho known issues

---

## 4. ADR (Architecture Decision Record) Template

```markdown
# ADR-[NUMBER]: [TITLE]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Date
[YYYY-MM-DD]

## Context
[Mô tả bối cảnh, problem statement, constraints]

## Decision Drivers
- [Driver 1: e.g., team size, growth plan]
- [Driver 2: e.g., budget constraint]
- [Driver 3: e.g., compliance requirement]
- [Driver 4: e.g., current pain points]

## Options Considered

### Option A: [Name]
- Description: [...]
- Pros: [...]
- Cons: [...]
- Cost: [...]
- Timeline: [...]
- Risk: [LOW/MEDIUM/HIGH]

### Option B: [Name]
[Same structure]

### Option C: [Name]
[Same structure]

## Decision
[Option chosen]

## Rationale
[Vì sao chọn option này, mapping với decision drivers]

## Consequences

### Positive
- [...]

### Negative
- [...]

### Risks & Mitigations
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| [...] | H/M/L | H/M/L | [...] |

## Implementation Plan
- [ ] Phase 1 (30 days): [...]
- [ ] Phase 2 (60 days): [...]
- [ ] Phase 3 (90 days): [...]

## Success Metrics
- [Metric 1]: current [X] → target [Y] in [Z] months
- [Metric 2]: current [X] → target [Y] in [Z] months

## Review Date
[Date — typically 3-6 months after decision]

## References
- [Link 1]
- [Link 2]
```

---

## 5. Key Terminology Reference

| Term | Giải thích | Ví dụ |
|------|-----------|-------|
| **SLA** | Service Level Agreement — hợp đồng cam kết với khách hàng | "99.9% uptime mỗi tháng, vi phạm thì credit 10%" |
| **SLO** | Service Level Objective — mục tiêu nội bộ, strict hơn SLA | "99.95% availability" (strict hơn SLA 99.9%) |
| **SLI** | Service Level Indicator — metric đo cụ thể | "% requests responded in < 200ms" |
| **Error budget** | Lượng lỗi cho phép trước khi vi phạm SLO | SLO 99.9% → error budget = 0.1% = 43 min/month |
| **Toil** | Công việc manual, lặp lại, có thể tự động hóa | Manual deploy, manual log grep, manual scaling |
| **Blast radius** | Phạm vi ảnh hưởng của một thay đổi | "Deploy lỗi ảnh hưởng 100% users" vs "5% canary" |
| **Postmortem** | Phân tích sau incident, tìm root cause | Blameless document mô tả timeline, cause, fix |
| **Runbook** | Hướng dẫn step-by-step xử lý specific scenario | "Khi DB connection pool exhausted, làm các bước sau..." |
| **Golden path** | Con đường chuẩn đã thiết kế sẵn cho developer | "Tạo service mới: dùng template này, deploy qua pipeline này" |
| **IDP** | Internal Developer Platform | Portal self-service để developer tạo env, deploy, xem logs |
| **MTTR** | Mean Time to Recovery | Thời gian trung bình từ detect incident đến recovery |
| **MTTD** | Mean Time to Detect | Thời gian từ issue xảy ra đến khi phát hiện |
| **CFR** | Change Failure Rate | % deployments gây ra incident/rollback |

