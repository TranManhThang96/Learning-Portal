# Exercises — Day 35: Disaster Recovery
## Capstone Production-Grade

---

## Exercise 1: Design DR Matrix for a 10-Service Platform

### Scenario

Bạn thiết kế DR plan cho một startup có 10 microservices, 2 database (PostgreSQL + MongoDB), 1 Redis cluster, 1 Kubernetes cluster trên AWS.

### Yêu cầu

Tạo DR matrix cho từng component với:

```
| Component        | RTO Target | RPO Target | Failure Mode           | Recovery Method     |
|-----------------|------------|------------|------------------------|---------------------|
| API Gateway     | ?          | ?          | ?                      | ?                   |
| User Service    | ?          | ?          | ?                      | ?                   |
| Order Service   | ?          | ?          | ?                      | ?                   |
| PostgreSQL      | ?          | ?          | ?                      | ?                   |
| MongoDB         | ?          | ?          | ?                      | ?                   |
| Redis           | ?          | ?          | ?                      | ?                   |
| Kubernetes      | ?          | ?          | ?                      | ?                   |
| ArgoCD          | ?          | ?          | ?                      | ?                   |
```

Giải thích logic đằng sau RTO của từng service:
- Order Service (giao dịch tài chính): RTO phải thấp vì mỗi phút down = mất doanh thu
- User Service (authentication): RTO trung bình, RPO có thể cao vì user data không critical-time-sensitive
- Redis (cache): RTO = 0? hay có thể chạy không cache trong 10 phút?

### Bonus

Thêm 1 cột "Monthly DR infrastructure cost" và estimate chi phí cho DR setup (backup storage, RDS backup, Velero snapshots).

---

## Exercise 2: Debug Incident — ArgoCD Apps OutOfSync Nhưng Resource Không Thay Đổi

### Incident

```
$ argocd app list
NAME           SYNC STATUS   HEALTH STATUS
api-service    OutOfSync     Healthy
worker-service OutOfSync     Healthy
frontend-svc   Synced       Healthy

$ argocd app diff api-service
(no diff)

$ kubectl get deployment api-service -n apps
NAME           READY   UP-TO-DATE
api-service    2/2     2
```

**Problem:** ArgoCD báo OutOfSync nhưng kubectl cho thấy resource đang đúng. `argocd app diff` không show diff.

### Yêu cầu

1. Debug để tìm root cause
2. Liệt kê 5 possible causes cho "OutOfSync but no diff"
3. Fix root cause
4. Prevent tương lai bằng cách nào?

### Hint

```
# Những thứ ArgoCD theo dõi mà kubectl get không thấy:
- Annotations (argocd.argoproj.io/tracking-id)
- Labels (khác biệt managed-by, version)
- Spec của resources mà kubectl không show mặc định
- Differences in managedFields
```

---

## Exercise 3: Terraform State Emergency — Production State Lost

### Scenario

Bạn vô tình chạy `terraform destroy` trên production state file. Terraform state file `terraform.tfstate` đã bị ghi đè bằng empty state. S3 bucket không có versioning (đã bị disable vì "save cost").

### Bước đã làm

```bash
# Sau khi terraform destroy chạy xong:
$ aws ec2 describe-instances --filters Name=tag:Project,Values=capstone-prod
# Kết quả: Rỗng — production infrastructure đã bị xóa

$ aws s3 ls s3://capstone-tf-state/
# Kết quả: terraform.tfstate tồn tại nhưng size = 0 bytes (empty)
```

### Yêu cầu

1. Đánh giá damage: Có bao nhiêu resources đã bị xóa?
2. Recovery options: Liệt kê 3 cách recover infrastructure, với pros/cons
3. Recovery plan: Viết step-by-step plan để restore production
4. Post-incident actions: Điều gì cần làm để ngăn repeat?
5. Communication plan: Bạn sẽ thông báo stakeholders như thế nào?

### Constraints

- Không có Terraform state backup trước đó
- Infrastructure resources đã bị xóa hoàn toàn khỏi AWS
- S3 không có versioning (chỉ còn empty state)
- Bạn cần restore production ASAP

---

## Exercise 4: Simulate và Respond — Secret Rotation Incident

### Scenario

```
Thứ Hai 9:00 AM — DevOps team nhận alert:
" ESO sync error on api-service: AWS Secrets Manager secret 'capstone/db-password' not found"

Nguyên nhân: Security team rotate secret vào cuối tuần (đã notify nhưng DevOps không check email).
Secret cũ: capstone/db-password = "old-password-xyz"
Secret mới: capstone/db-password = "new-password-abc"
Ứng dụng: Đang chạy với old password → 100% request fail
Users affected: Tất cả users không thể login
```

### Yêu cầu

```bash
# Step 1: Immediate triage (5 phút)
# Viết triage script để xác định:
# - Bao nhiêu deployment bị ảnh hưởng
# - Bao nhiêu pod đang crash
# - ESO sync status của tất cả namespace
kubectl get externalsecret -A --no-headers | awk '{print $1, $2, $3}'
kubectl get pods -A --field-selector status.phase!=Running --no-headers | wc -l
```

```bash
# Step 2: Emergency fix (10 phút)
# 2a: Option A — Update AWS Secrets Manager (nếu secret mới đã rotate)
aws secretsmanager put-secret-value \
  --secret-id capstone/db-password \
  --secret-string "???"

# 2b: Option B — Manual secret (temporary)
kubectl create secret generic db-password \
  -n apps \
  --from-literal=password="???" \
  --dry-run=client -o yaml | kubectl apply -f -

# 2c: Force ESO sync
kubectl annotate externalsecret ??? force-sync=???
```

```bash
# Step 3: Post-incident (30 phút)
# Viết postmortem outline cho incident này
# Gồm: Timeline, Root cause, Impact, Action items
```

### Bonus

Viết Ansible playbook để detect và respond tự động khi ESO secret sync fail:
- Tự động restart pod khi secret được update
- Tự động alert qua Slack khi ESO ở Error state > 5 phút
- Tự động verify database connectivity sau secret rotation

---

## Exercise 5: GameDay Design — Simulate Full Cluster Loss

### Scenario

Thiết kế một GameDay exercise plan để simulate và test cluster loss recovery.

### Yêu cầu

Thiết kế game day plan gồm:

**1. Pre-game (before the day):**
- Notification template
- Environment preparation
- Success criteria definition

**2. Game day timeline:**

```
| Time | Activity | Owner | Success Metric |
|------|----------|-------|----------------|
| 09:00 | ?        | ?     | ?              |
| 09:15 | ?        | ?     | ?              |
| ...  | ...      | ...   | ...            |
```

**3. Injection scenarios (chọn 2-3):**
- Inject: Xóa EKS cluster bằng Terraform apply destroy
- Inject: ArgoCD namespace delete
- Inject: Database credentials rotation không sync ESO
- Inject: Terraform state lock + corruption

**4. Success criteria:**
- RTO đạt được cho từng scenario
- RPO đạt được cho từng scenario
- Data loss measurement

**5. Post-game:**
- Retrospective questions
- Runbook update checklist
- Action items

---

## Exercise 6: ArgoCD Rollback Strategy — Multi-Service Cascade Failure

### Scenario

```
10:30 AM — Sau khi merge PR #247 (update api-service + worker-service cùng lúc):
- api-service: v2.4.0 deployed → 50% pod CrashLoopBackOff (DB migration bug)
- worker-service: v1.8.0 deployed → 100% pod OOMKilled (memory limit too low)
- frontend-service: v3.1.0 deployed → Healthy (may không liên quan)

Users affected: ~2,000 concurrent users
Revenue impact: ~$50/minute
Current ArgoCD status:
  argocd app list
  NAME             SYNC   HEALTH
  api-service      Synced  Degraded
  worker-service   Synced  Degraded
  frontend-svc     Synced  Healthy
```

### Yêu cầu

**Part A — Immediate Response (5 phút)**

1. Quyết định: Rollback tất cả hay từng service?
2. Rollback order: Nên rollback api-service trước hay worker-service trước? Tại sao?
3. Write the rollback commands:

```bash
# Rollback api-service
# ???

# Rollback worker-service
# ???

# Verify rollback
# ???
```

**Part B — Communication (5 phút)**

Viết message cho stakeholders:

```
TO: all-hands@company.com
SUBJECT: [INCIDENT] API and Worker Service Degradation - IN PROGRESS
```

Body gồm:
- Current status (2-3 sentences)
- User impact
- ETA to restore
- Mitigation steps đang thực hiện
- What users should do trong lúc incident

**Part C — Post-Incident (30 phút)**

1. Root cause analysis:
   - api-service CrashLoopBackOff: Debug để tìm lý do
   - worker-service OOMKilled: Debug để tìm lý do
   - CI/CD pipeline: Tại sao migration bug không được detect trước khi deploy?

2. Write fix PRs:
   - api-service: Fix migration rollback script
   - worker-service: Increase memory limit
   - CI/CD: Add pre-deployment smoke test

3. Process improvement: Điều gì trong CI/CD/CD pipeline nên thay đổi để ngăn incident này?

---

## Exercise 7: Write a Runbook từ đầu cho một Production Incident

### Incident Report

```
INCIDENT SUMMARY
================
Date: 2026-05-15
Severity: P2
Duration: 45 phút (10:15 - 11:00)
Impact: 30% users không thể checkout
Service: api-service (checkout flow)
Cost: ~$2,500 lost revenue

TIMELINE
========
10:15 - Developer push v2.4.0 to production via ArgoCD
10:17 - First error report: checkout fails for ~30% users
10:18 - On-call engineer notified via PagerDuty
10:20 - ArgoCD health check: Degraded (1/3 replicas healthy)
10:22 - kubectl logs: "DB connection refused" on unhealthy replicas
10:25 - Rollback initiated
10:27 - Rollback completed
10:28 - Health check: Still Degraded (2 replicas still crashing)
10:30 - Force restart all replicas: kubectl rollout restart deployment api-service
10:32 - Health check: All replicas Healthy
10:35 - Smoke test: Checkout works for 100% users
11:00 - Incident closed

ROOT CAUSE
==========
PR #247 introduced a breaking database migration that:
1. Changed column type from VARCHAR(50) to VARCHAR(20) without down migration
2. New code tried to INSERT data > 20 chars before migration complete
3. Old replicas had the migration, new replicas failed

FIXES APPLIED
=============
1. Rolled back api-service to v2.3.9
2. Added down migration script for the breaking migration
3. Added pre-deployment smoke test to verify DB connectivity
```

### Yêu cầu

Dựa trên incident report trên, viết một runbook hoàn chỉnh cho `RUNBOOK-BREAKING-MIGRATION` theo template trong document.md.

Runbook phải gồm:
1. Diagnostic checklist (sử dụng incident timeline để viết các bước check)
2. Immediate actions (sử dụng timeline để xác định priority actions)
3. Recovery steps (sử dụng timeline để xác định correct recovery sequence)
4. Post-incident section
5. Prevention section với specific actionable items

---

## Exercise 8: Cost-Benefit Analysis — Backup Strategy

### Scenario

Một startup có budget $200/tháng cho DR infrastructure. Họ đang xem xét 3 backup strategies:

| Strategy | Monthly Cost | RTO | RPO |
|----------|-------------|-----|-----|
| Manual S3 backup (cron job) | $5 | 4 giờ | 24 giờ |
| Velero + daily snapshots | $45 | 1 giờ | 1 giờ |
| Multi-region active-active | $280 | 0 | 0 |

### Yêu cầu

1. Tính ROI của từng strategy dựa trên:
   - Average incident cost: $5,000/incident (conservative estimate)
   - Expected incidents/year: 2 (industry average cho startups)
   - Velero strategy reduces incident cost bao nhiêu?

2. Viết recommendation cho startup này, giải thích:
   - Startup nên chọn strategy nào? Tại sao?
   - Nếu budget tăng lên $500/tháng, recommendation thay đổi không?
   - Nếu startup có Series A funding ($10M ARR), recommendation thay đổi không?

3. Thiết kế phased approach:
   - Phase 1 (Month 1-3): Làm gì với $50?
   - Phase 2 (Month 4-6): Làm gì với $100?
   - Phase 3 (Month 7+): Làm gì với $200?

---

## Exercise 9: Retrospective Deep Dive

### Self-Assessment

Trả lời các câu hỏi sau một cách honest:

**Production Readiness:**

1. Trên scale 1-5, đánh giá capstone platform này theo từng dimension:
   - Infrastructure as Code maturity: __/5
   - GitOps deployment confidence: __/5
   - Observability coverage: __/5
   - Disaster recovery readiness: __/5
   - Cost control discipline: __/5
   - Security baseline strength: __/5
   - CI/CD automation: __/5

2. Điều gì trong 35 ngày học bạn nghĩ sẽ sử dụng thường xuyên nhất trong công việc thực tế?

3. Điều gì bạn nghĩ cần thêm 3-6 tháng nữa để thực sự production-ready?

**Gap Analysis:**

4. List 5 things trong capstone bạn biết cách làm nhưng chưa thực sự hiểu sâu (cần thêm practice)

5. List 3 things bạn chưa có cơ hội làm (stretch goal)

**Transfer:**

6. Câu chuyện/analogy nào từ 35 ngày mà bạn sẽ dùng để explain GitOps cho:
   - A non-technical manager
   - A backend developer
   - A security engineer

7. Điều gì từ Terraform bạn sẽ apply cho IaC của riêng bạn (không phải AWS)?

---

## Bonus Challenge: Design On-Call Rotation cho Capstone Platform

### Scenario

Platform team gồm 3 engineers, cần thiết lập on-call rotation.

### Yêu cầu

Thiết kế:

1. **On-call schedule:**
   - Rotation format (weekly / daily)
   - Primary / secondary escalation
   - Handoff procedure

2. **Alert routing:**
   - P1 (Full outage): Ai nhận? Trong bao lâu?
   - P2 (Partial outage): Ai nhận?
   - P3 (Warning/Degraded): Ai nhận?

3. **Alert fatigue prevention:**
   - Minimum time between alerts?
   - Alert deduplication?
   - Paging only on real issues?

4. **Runbook access:**
   - Làm sao on-call engineer có thể truy cập runbook khi cần?
   - Runbook phải có những thông tin gì để on-call có thể respond trong 5 phút?

5. **On-call compensation:**
   - Standby compensation model
   - Incident response compensation
   - Post-incident review participation

```bash
# Alert routing logic pseudocode:
if alert.severity == P1:
    page(primary_oncall, secondary_oncall)
    if no_acknowledge(5min):
        escalate_to(engineering_manager)
elif alert.severity == P2:
    page(primary_oncall)
    if no_acknowledge(15min):
        escalate_to(secondary_oncall)
elif alert.severity == P3:
    notify(slack_channel)
    if slack_no_response(30min):
        page(primary_oncall)
```
