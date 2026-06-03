# Day 1: Bài tập — DevOps, SRE, Platform Engineering & DORA Metrics

---

## Bài 1: Easy — Đánh giá DORA Metrics cho team hiện tại

### Context
Bạn là Senior Software Engineer trong một team 12 người. Team vận hành 3 microservices trên Kubernetes. Hiện tại team deploy bằng cách merge vào `main` → CI build → manual approval → deploy staging → manual approval → deploy production. Mỗi lần deploy mất khoảng 2-3 ngày từ lúc merge.

### Yêu cầu
1. Dùng git repository hiện tại (hoặc bất kỳ repo nào bạn đang làm việc), chạy các command để thu thập DORA metrics thực tế.
2. Điền kết quả vào bảng đánh giá.
3. Xác định DORA level cho từng metric.
4. Đưa ra 2 hành động cải thiện cụ thể.

### Expected Outcome
- Bảng DORA metrics với giá trị thực tế từ repository.
- Level classification cho từng metric (Low/Medium/High/Elite).
- Ít nhất 2 actionable improvements.

### Hint
- Dùng `git log` với các filter phù hợp để đếm deployments, hotfixes, lead time.
- Change failure rate = số hotfix/revert / tổng deployments.
- Nếu repo không có deployment tags, ước lượng từ merge frequency.

### Acceptance Criteria
- [ ] Thu thập được cả 4 DORA metrics (có thể ước lượng).
- [ ] Mỗi metric được classify đúng level theo bảng DORA.
- [ ] Ít nhất 2 improvements có tính khả thi (không phải "deploy nhanh hơn" mà phải cụ thể).

### Bonus Challenge
- So sánh DORA metrics giữa 2 repos khác nhau mà bạn có quyền truy cập.
- Tạo script tự động thu thập DORA metrics từ git log.

<details>
<summary>Solution / Reference</summary>

```bash
#!/bin/bash
# dora-metrics.sh — Thu thập DORA metrics từ git repository

DAYS=${1:-30}
echo "=== DORA Metrics Report (last $DAYS days) ==="
echo ""

# 1. Deployment Frequency
TOTAL_MERGES=$(git log --merges --oneline --after="$DAYS days ago" 2>/dev/null | wc -l)
TOTAL_TAGS=$(git tag --sort=-creatordate | while read tag; do
  tag_date=$(git log -1 --format='%ai' "$tag" 2>/dev/null)
  if [[ $(date -d "$tag_date" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "${tag_date%% *}" +%s 2>/dev/null) -gt $(date -d "$DAYS days ago" +%s 2>/dev/null || date -v-${DAYS}d +%s 2>/dev/null) ]]; then
    echo "$tag"
  fi
done | wc -l)

echo "1. Deployment Frequency:"
echo "   Merges to main (last $DAYS days): $TOTAL_MERGES"
echo "   Release tags (last $DAYS days): $TOTAL_TAGS"
WEEKLY=$(echo "scale=1; $TOTAL_MERGES * 7 / $DAYS" | bc 2>/dev/null || echo "N/A")
echo "   Estimated per week: $WEEKLY"
echo ""

# 2. Lead Time for Changes
echo "2. Lead Time for Changes:"
echo "   (Analyze recent merge commits)"
git log --merges --format="%H %ai %s" --after="$DAYS days ago" | head -5 | while read hash date time tz rest; do
  echo "   Merge: $date $time — $rest"
done
echo ""

# 3. Change Failure Rate
HOTFIXES=$(git log --oneline --after="$DAYS days ago" --grep="hotfix\|revert\|rollback\|fix.*prod\|emergency" -i | wc -l)
TOTAL=$(git log --oneline --after="$DAYS days ago" | wc -l)
if [ "$TOTAL" -gt 0 ]; then
  CFR=$(echo "scale=1; $HOTFIXES * 100 / $TOTAL" | bc 2>/dev/null || echo "N/A")
else
  CFR="N/A"
fi
echo "3. Change Failure Rate:"
echo "   Hotfixes/Reverts: $HOTFIXES"
echo "   Total commits: $TOTAL"
echo "   Rate: ${CFR}%"
echo ""

# 4. MTTR (estimate)
echo "4. MTTR (estimated from fix commits):"
git log --oneline --after="$DAYS days ago" --grep="fix\|hotfix\|incident\|revert" -i | head -5
echo ""

echo "=== Classification ==="
echo "Refer to DORA benchmark table to classify your metrics."
```

**Đánh giá mẫu:**

| Metric | Giá trị | Level |
|--------|---------|-------|
| Deployment Frequency | 3 lần/tuần | High |
| Lead Time | ~2 ngày | High |
| Change Failure Rate | 4.4% | Elite |
| MTTR | ~2 giờ | High |

**Improvements:**
1. **Tự động hóa approval**: Thay manual approval bằng automated smoke test + auto-promote → giảm lead time xuống < 1 giờ.
2. **Thêm canary deployment**: Deploy 5% traffic trước → giảm blast radius → giảm change failure rate.

</details>

---

## Bài 2: Medium — Viết Mini ADR chọn Operating Model

### Context
Bạn vừa được promote lên Tech Lead tại một fintech startup. Team hiện có 25 engineers (4 teams), vận hành 8 microservices. Hệ thống xử lý thanh toán với SLA 99.9% cho khách hàng. Các vấn đề hiện tại:
- Deploy lên production cần 1 "DevOps engineer" approve và thực hiện — người này là bottleneck.
- Không có SLO/SLI formal, chỉ có uptime monitoring basic.
- Khi incident xảy ra, mọi người ping nhau trên Slack, không có quy trình rõ ràng.
- MTTR trung bình là 4 giờ.
- Mỗi team tự viết Dockerfile và CI pipeline riêng, kết quả không consistent.

### Yêu cầu
1. Sử dụng ADR template từ bài học (hoặc tự thiết kế template).
2. Phân tích ít nhất 3 options (DevOps culture only, DevOps + embedded SRE, Platform Engineering).
3. Đánh giá từng option theo: cost, timeline, risk, expected DORA improvement.
4. Đưa ra decision với rationale rõ ràng.
5. Liệt kê consequences (positive, negative, risks).

### Expected Outcome
- Một ADR document hoàn chỉnh, có thể present cho CTO.
- Decision phải phù hợp với context (team size, industry, pain points).
- Có timeline implementation cụ thể (30/60/90 ngày).

### Hint
- Fintech + payment = reliability là ưu tiên → SRE concepts quan trọng.
- Team 25 người = chưa đủ lớn cho full Platform team → nhưng pain point "mỗi team tự build CI" gợi ý cần shared platform.
- Bottleneck "1 DevOps engineer" gợi ý cần distributed ownership.

### Acceptance Criteria
- [ ] ADR có đầy đủ sections: Context, Decision Drivers, Options, Decision, Rationale, Consequences.
- [ ] Mỗi option có pros/cons phân tích theo context cụ thể (không generic).
- [ ] Decision hợp lý cho context (25 engineers, fintech, SLA 99.9%).
- [ ] Có implementation timeline.
- [ ] Có review date.

### Bonus Challenge
- Thêm cost estimate cho mỗi option (hiring, tooling, time investment).
- Thêm migration plan: từ trạng thái hiện tại (1 DevOps engineer bottleneck) chuyển sang model mới.
- Trình bày ADR cho đồng nghiệp và thu thập feedback.

<details>
<summary>Solution / Reference</summary>

```markdown
# ADR-001: Lựa chọn Operating Model cho Engineering Team

## Status
Accepted (2024-XX-XX)

## Context
Fintech startup, 25 engineers (4 teams), 8 microservices.
Payment system SLA 99.9%.

Pain points:
1. 1 DevOps engineer là bottleneck cho mọi deployment
2. Không có SLO/SLI formal
3. Incident response ad-hoc qua Slack
4. MTTR ~4 giờ (quá cao cho payment system)
5. Mỗi team tự build CI/CD → inconsistent

## Decision Drivers
- Team size: 25 (growing to ~40 in 12 months)
- Industry: Fintech — regulated, reliability critical
- Budget: Startup — cần cost-effective
- Pain: Bottleneck deploy, no reliability measurement
- Growth: Mong đợi tăng gấp đôi engineer trong 18 tháng

## Options Considered

### Option A: DevOps Culture Only
Eliminate "DevOps engineer" bottleneck, mọi developer tự deploy.
- **Pros**: Không cần hire, nhanh implement, developer ownership
- **Cons**: Không ai chuyên sâu reliability cho payment (rủi ro cao), 
  SLO/incident process vẫn cần ai đó lead
- **Cost**: $0 hire, ~2 tuần training
- **Risk**: HIGH — payment system cần chuyên gia reliability

### Option B: DevOps Culture + 1 Embedded SRE (RECOMMENDED)
Tất cả developer tự deploy. Hire 1 SRE engineer focus vào:
- Thiết lập SLI/SLO cho payment service
- Build shared CI/CD pipeline (giải quyết consistency)
- Thiết lập incident response process
- On-call rotation design

- **Pros**: Cost-effective, giải quyết reliability gap,
  shared CI/CD giải quyết consistency, SRE vừa đủ cho team size
- **Cons**: Single point of failure (1 SRE), SRE burnout risk
- **Cost**: $150-200k/year (1 SRE hire), ~1 tháng để hire
- **Risk**: MEDIUM — mitigated by making SRE a multiplier, 
  not bottleneck. SRE teaches, not does.

### Option C: Platform Engineering Team
Hire 3-4 engineers build Internal Developer Platform.
- **Pros**: Scalable, self-service, long-term productivity gain
- **Cons**: Quá lớn investment cho team 25, platform cần 6+ months
  để bắt đầu có value, risk over-engineering
- **Cost**: $450-600k/year (3-4 hires), 6+ months to first value
- **Risk**: HIGH — team quá nhỏ để justify dedicated platform team

## Decision
**Option B: DevOps Culture + 1 Embedded SRE**

## Rationale
1. DevOps engineer bottleneck phải giải quyết ngay bằng cultural change 
   (developer tự deploy) — không cần hire.
2. Payment system SLA 99.9% cần chuyên gia reliability → SRE.
3. Team size 25 không justify Platform team, nhưng SRE có thể 
   build shared tooling (CI/CD templates, monitoring) dần dần.
4. Khi team grow lên 40-50, evaluate lại nhu cầu Platform team.

## Implementation Timeline

### Phase 1: 30 ngày — Cultural change
- [ ] Loại bỏ manual approval bottleneck (auto-promote after tests pass)
- [ ] Mọi developer có quyền deploy staging
- [ ] Production deploy cần 1 peer approval (code review) 
- [ ] Kick off SRE hiring process

### Phase 2: 60 ngày — SRE onboard + Foundation
- [ ] SRE onboard, đánh giá current state
- [ ] SLI/SLO defined cho payment service
- [ ] Shared CI/CD pipeline template v1
- [ ] Incident response guide v1 + severity levels

### Phase 3: 90 ngày — Measurement + Iteration
- [ ] DORA metrics dashboard
- [ ] On-call rotation started (SRE + developers)
- [ ] Error budget policy draft
- [ ] First postmortem conducted
- [ ] Review ADR, adjust if needed

## Consequences
### Positive
- Developer autonomy tăng → tốc độ deploy tăng
- Reliability measured → data-driven improvement
- Shared CI/CD → consistency across teams

### Negative
- Developer cần learn deployment safety → training time
- SRE hire có thể mất 1-3 tháng → gap period

### Risks
- SRE burnout nếu on-call chỉ 1 người → mitigate: SRE trains developers, 
  developer join on-call rotation
- Developer resistance "tôi là dev không phải ops" → mitigate: cultural 
  change championed by CTO/tech leads

## Review Date
Re-evaluate in 6 months (team ~35 engineers) or when team reaches 40.
```

</details>

---

## Bài 3: Hard — Thiết kế DORA Metrics Dashboard và Improvement Plan

### Context
Bạn là Principal Engineer tại một mid-size SaaS company. Team có 80 engineers, 12 teams, 40+ microservices. CTO yêu cầu bạn:
1. Thiết kế cách đo DORA metrics tự động cho tất cả teams.
2. Phân tích kết quả giả lập và đưa ra improvement plan.
3. Trình bày trade-offs giữa speed và reliability cho leadership.

### Yêu cầu

**Part 1: Thiết kế DORA Metrics Collection**
- Xác định data source cho mỗi metric (git, CI/CD, incident tracking, deployment tool).
- Thiết kế flow thu thập data.
- Viết pseudo-code hoặc script thu thập ít nhất 2 metrics.

**Part 2: Phân tích dữ liệu giả lập**
Dưới đây là DORA data cho 4 teams:

| Team | Deploy Freq | Lead Time | CFR | MTTR |
|------|------------|-----------|-----|------|
| Payment | 2/tuần | 3 ngày | 8% | 2 giờ |
| User | 5/tuần | 4 giờ | 15% | 30 phút |
| Notification | 1/tháng | 2 tuần | 3% | 8 giờ |
| Analytics | 3/tuần | 1 ngày | 20% | 1 giờ |

Phân tích:
- Team nào performance tốt nhất / tệ nhất?
- Root cause có thể là gì cho từng team?
- Improvement plan cho top 2 teams cần cải thiện nhất.

**Part 3: Leadership Presentation**
- Tạo 1-page summary cho CTO giải thích vì sao DORA matters.
- Bao gồm: current state, target state, investment needed, expected ROI.

### Expected Outcome
- Thiết kế thu thập DORA metrics có thể implement được.
- Phân tích sâu cho dữ liệu giả lập, không chỉ nhìn số mà phân tích root cause.
- 1-page summary chuyên nghiệp cho leadership.

### Hint
- Deployment frequency thấp KHÔNG nhất thiết là xấu — có thể là service ổn định ít thay đổi. Nhưng kết hợp với lead time CAO → chắc chắn có vấn đề process.
- CFR cao + MTTR thấp = team deploy nhanh, fail nhanh, fix nhanh (có thể ok nếu có canary). CFR thấp + MTTR cao = deploy cẩn thận nhưng khi fail thì tê liệt lâu (thiếu incident process).
- Team Notification: deploy 1/tháng + lead time 2 tuần gợi ý big-bang release → rất rủi ro.

### Acceptance Criteria
- [ ] Thiết kế data collection cho cả 4 DORA metrics.
- [ ] Phân tích data giả lập có depth (không chỉ "team X tệ nhất").
- [ ] Improvement plan có timeline và expected impact.
- [ ] 1-page summary có thể present cho non-technical leadership.
- [ ] Trình bày trade-offs rõ ràng, không one-sided.

### Bonus Challenge
- Thêm phân tích: nếu company phải pick TOP 1 metric để focus cải thiện, nên chọn metric nào và vì sao?
- Thiết kế Grafana dashboard layout cho DORA metrics.
- Viết script hoàn chỉnh thu thập DORA metrics từ GitHub API.

<details>
<summary>Solution / Reference</summary>

**Part 2 Analysis:**

**Team xếp hạng (overall):**
1. **User** (Best): Deploy freq High, Lead time Elite, MTTR Elite. CFR 15% hơi cao nhưng MTTR cực thấp → team có canary hoặc feature flags, fail fast fix fast.
2. **Payment**: Deploy freq High, CFR Low (8%), MTTR good. Lead time 3 ngày hơi chậm → có thể do security review/compliance (hợp lý cho payment).
3. **Analytics**: Deploy freq High, Lead time ok. CFR 20% → cao nhất, cần investigation. MTTR tốt.
4. **Notification** (Worst): Deploy 1/tháng + lead time 2 tuần = big-bang release pattern. MTTR 8 giờ = tệ nhất. CFR 3% chỉ vì deploy ít, không phải vì quality cao.

**Root cause analysis:**

**Team Notification (cần cải thiện nhất):**
- Root cause có thể: Tightly coupled codebase, thiếu test automation, manual testing 
  trước mỗi release, không có CI/CD proper, hoặc team quá nhỏ + nhiều tech debt.
- Improvement plan:
  1. Tháng 1: Break down releases thành smaller chunks, deploy ít nhất 1/tuần
  2. Tháng 2: Automated testing pipeline, eliminate manual QA bottleneck
  3. Tháng 3: Incident response training, on-call rotation, runbook cho common failures
  4. Target: Deploy freq 1-2/tuần, Lead time < 3 ngày, MTTR < 2 giờ trong 3 tháng

**Team Analytics (cần cải thiện CFR):**
- Root cause có thể: Deploy nhanh nhưng thiếu test coverage, không có staging environment 
  proper, hoặc schema changes không backward compatible.
- Improvement plan:
  1. Tháng 1: Test coverage analysis, add integration tests cho top 5 failure scenarios
  2. Tháng 2: Pre-production validation (staging + smoke tests)
  3. Tháng 3: Canary deployment, automated rollback
  4. Target: CFR < 10% trong 3 tháng

**1-page Summary cho CTO:**

```markdown
# Engineering Velocity & Reliability Report

## Tại sao DORA metrics quan trọng?
DORA (Google research, 7+ năm, 30,000+ professionals) chứng minh:
- Top performers deploy 208x thường xuyên hơn low performers
- Top performers có 2,604x faster recovery time
- Speed và stability KHÔNG phải trade-off — top teams đạt cả hai

## Current State (4 teams analyzed)
- 1 team Elite/High performance (User)
- 2 teams High/Medium (Payment, Analytics)  
- 1 team Low performance (Notification) — deploy 1x/tháng, MTTR 8 giờ

## Key Risks
- Team Notification: big-bang release pattern → mỗi deploy là high-risk event
- Team Analytics: 20% change failure rate → 1/5 deploys gây issue
- Inconsistency across teams → no organizational learning

## Investment Needed
- Shared CI/CD templates: 2 engineer-months
- SRE hire (1 person): $180k/year
- DORA dashboard + automation: 1 engineer-month
- Training & culture: 2 weeks per team
Total: ~$250k first year

## Expected ROI (6 months)
- Deploy frequency: 2x improvement across all teams
- MTTR: 50% reduction (save ~$X per incident)  
- Developer productivity: 20% increase (less waiting, less manual ops)
- Incident cost reduction: estimated $Y/year saved
```

</details>

---

## Tổng kết thời gian

| Bài | Độ khó | Thời gian ước tính |
|-----|--------|-------------------|
| Bài 1 | Easy | 20-30 phút |
| Bài 2 | Medium | 40-50 phút |
| Bài 3 | Hard | 60-90 phút |

Lưu ý: Bạn không cần hoàn thành tất cả trong 1 ngày. Bài 1 + Bài 2 phù hợp cho 2 giờ/ngày (kết hợp đọc lesson). Bài 3 có thể làm thêm nếu muốn deep-dive.

