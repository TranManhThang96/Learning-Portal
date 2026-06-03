# Day 44: Incident Response & Postmortem — Exercises

---

## Exercise 1 (Easy): Incident Lifecycle Walkthrough

### Context
Bạn là on-call engineer tại một công ty SaaS cỡ trung. Sáng thứ Hai 09:15 UTC, bạn nhận được PagerDuty alert:

> `[CRITICAL] API Error Rate > 15% — Production`
> Alert: `api_error_rate_5m > 0.15` (threshold: 0.05)
> Source: Prometheus alert rule

Bạn check dashboard và thấy:
- API error rate: **18%** (baseline: 0.3%)
- Latency p99: **12s** (baseline: 120ms)
- Database connection errors: **rất nhiều** (`timeout errors` tăng đột biến)

### Requirements

1. **Xác định severity** (SEV1–SEV4) — giải thích lý do chọn level đó
2. **Mở incident channel giả lập** — viết message đầu tiên trong incident channel với đầy đủ thông tin
3. **Phân công roles** — chỉ định IC, Ops Lead, Comms Lead (3 vai trò khác nhau, bạn là on-call)
4. **Viết 3 hypothesis** về root cause (theo format: "Nếu X → thì Y sẽ xảy ra → kiểm tra bằng cách Z")
5. **Viết message cho Comms Lead** gửi lên status page (internal + external)

### Expected Outcome
Một document gồm:
- Severity justification
- Incident channel opening message
- Role assignments với brief description mỗi role
- 3 hypothesis được structured rõ ràng
- 2 status page messages

### Hint
- Severity: look at the "service completely down vs degraded" decision tree
- Status page: luôn dùng present tense và active voice
- Hypothesis: format "IF-THEN-BECAUSE" giúp structure rõ ràng

### Acceptance Criteria
- [ ] Severity có justification rõ ràng
- [ ] Incident message đầy đủ: what, when, who, current action
- [ ] Cả 3 roles được assign với người cụ thể
- [ ] Ít nhất 2 hypothesis testable (có method để verify)
- [ ] Status page messages clear, không technical jargon

### Bonus Challenge
Viết thêm **decision log 15 phút đầu** với 3 mốc thời gian (`09:15`, `09:20`, `09:30`), mỗi mốc có: quyết định, rationale, risk, next check. Mục tiêu là luyện thói quen ghi lại vì sao IC chọn hướng hành động trong lúc pressure cao.

---

## Exercise 2 (Medium): Blameless Postmortem từ Timeline

### Context
Bạn là IC của incident vừa resolve. Ops Lead cung cấp cho bạn raw timeline từ logs:

```
RAW LOG TIMELINE (unstructured):

09:14 - Developer @hieu push code v2.4.1 to staging
09:16 - CI/CD pipeline passes all tests
09:30 - @hieu requests production deployment approval
09:32 - Tech Lead @minh approves (didn't review code in detail)
09:35 - Deployment v2.4.1 starts
09:37 - v2.4.1 fully deployed: 100% traffic
09:38 - First anomalous metric: cache_hit_rate drops from 98% to 12%
09:39 - Latency p99 starts climbing (300ms → 800ms → 3000ms)
09:42 - PagerDuty alert fires: "API Latency SLO Burn Rate 50x"
09:42 - @ngoc.wake (on-call) paged via SMS + call
09:44 - @ngoc.wake acknowledges alert, starts investigation
09:46 - Ops Lead @thao.nguyen joins #incident channel
09:47 - IC @lan declares SEV2 (not SEV1 yet — some traffic still succeeds)
09:48 - Comms Lead @dung updates status page: "Investigating elevated latency"
09:50 - Check: v2.4.1 changelog: "Replaced Redis cache with local in-memory cache"
09:52 - Root cause identified: local in-memory cache → cache miss rate 88%
09:53 - IC decision: Rollback to v2.4.0 (4 minutes ago from full deploy)
09:55 - @thao.nguyen executes rollback
09:57 - Latency p99: 1200ms → 400ms → 200ms
10:02 - API fully recovered (baseline)
10:05 - Incident closed. Error budget burn: 3.2% of monthly budget in 30 min
10:08 - Postmortem scheduled for Friday 14:00
```

### Requirements

1. **Tạo bảng timeline sạch** từ raw log (HH:MM, Event, Actor, Action)
2. **Viết blameless postmortem hoàn chỉnh** (sử dụng template từ lesson.md Section 4.4)
3. **Thực hiện 5 Whys** analysis — ít nhất 4 rounds
4. **Tạo 4 action items theo SMART format** (Owner, Deadline, Priority, Ticket link)
5. **Nhận diện blameless violations** trong scenario này (nếu có) — và đề xuất cách refactor

### Expected Outcome
Một document postmortem bao gồm:
- Clean timeline table
- Blameless postmortem với đầy đủ 7 sections
- 5 Whys chain (visual)
- 4 action items với đầy đủ SMART fields
- 1 paragraph về blameless violations + refactored framing

### Hint
- "5 Whys" nên đi từ proximate cause (cache type) → systemic cause (process/tooling)
- Action items: owner phải là 1 person cụ thể, không phải team
- Blameless violation example: `@hieu pushed code` → nên viết là `v2.4.1 deployment...`

### Acceptance Criteria
- [ ] Timeline đầy đủ, không có judgment trong event description
- [ ] Postmortem có đủ 7 sections
- [ ] 5 Whys đi từ technical → process/systemic
- [ ] Tất cả action items có owner cụ thể (tên) và deadline
- [ ] Không có cá nhân hóa trong root cause description

### Bonus Challenge
Tạo thêm **action item dependency map**: action nào phải làm trước, action nào có thể chạy song song, action nào cần leadership approval. Với mỗi dependency, ghi rõ nếu bị delay thì risk nào quay lại production.

---

## Exercise 3 (Hard): Multi-Team Cascade Incident Simulation

### Context
Bạn là Incident Commander cho một SEV1 incident ảnh hưởng đến 3 microservices trong 2 teams.

**System Architecture:**
```
Users → API Gateway → Auth Service ─┬─→ User Service (Team Alpha)
                     │              └─→ Profile Service (Team Alpha)
                     └─→ Content Service (Team Beta)
```

**Incident Trigger:** 10:00 UTC — Auth Service bắt đầu return 401 errors không đúng (users đang authenticated nhưng bị reject).

**Timeline từ Ops Lead:**
```
10:00 - Auth Service error rate: 0% → 45% (sudden spike)
10:01 - API Gateway bắt đầu queue requests
10:02 - Content Service downstream calls to Auth Service failing
10:03 - Profile Service downstream calls to Auth Service failing
10:04 - Users can't login AND can't view content (cascade)
10:05 - ~40,000 users affected
10:06 - SEV1 declared
10:07 - IC opens #incident-20241120-001
        Team Alpha IC: @phuong.nguyen (Auth + User + Profile owner)
        Team Beta IC: @quan.le (Content Service owner)
        Unified Comms Lead: @hue.tran
10:08 - Investigation begins
```

**Investigation Findings (by 10:20):**
```
Team Alpha:
- Auth Service: JWT validation logic changed in v5.2.0 (deployed 09:45)
- Bug: token expiry validation inverted: tokens VALID > NOW treated as expired
- Fix exists: PR #1847 (was in review, not merged)
- Rollback: NOT POSSIBLE — v5.2.0 fixed a critical security vulnerability (CVE-2024-XXXXX)

Team Beta:
- Content Service: gracefully handles auth failures (returns "please login")
- Can run in degraded mode — 70% functionality without auth
- Feature flag exists for "auth-optional mode"

Team Alpha:
- Workaround: merge PR #1847 → deploy hotfix v5.2.1 (contains both security fix + auth bug fix)
- Estimated deploy time: 25 minutes (security scan required)
```

### Requirements

1. **Viết IC decision log** — mỗi 5 phút, IC note: decision, rationale, risk
2. **Mitigation strategy** cho Team Beta (content service) — trong khi chờ Auth fix
3. **Risk assessment**: Security fix rollback vs Auth service fix — tradeoff analysis
4. **Cross-team coordination plan** — 3 specific coordination points
5. **Comms plan** — viết 3 internal updates (10:10, 10:20, 10:35) và 2 external updates (10:15, 10:40)
6. **Post-incident action items** — 6 items across both teams

### Expected Outcome
Một document gồm:
- IC decision log (10:05 → 10:40, mỗi 5 phút)
- Team Beta mitigation plan (steps + verification)
- Risk assessment table (rollback risk vs hotfix risk)
- Cross-team coordination checklist
- 5 comms messages (2 external, 3 internal)
- 6 action items theo SMART format

### Hint
- Team Beta's feature flag có thể được toggle ngay lập tức — không cần deploy
- Security fix rollback: phải weigh security risk vs availability risk
- Comms Lead: internal vs external khác nhau về level of detail
- Action items: cần assign cụ thể Team Alpha hoặc Team Beta

### Acceptance Criteria
- [ ] IC decision log có ít nhất 7 entries, mỗi entry có rationale
- [ ] Team Beta mitigation thực hiện được trong < 5 phút (feature flag)
- [ ] Risk assessment balance security vs availability
- [ ] Comms messages clear, không technical jargon ở external
- [ ] Action items đủ cho cả 2 teams, có priority

### Bonus Challenge
Thiết kế thêm **security incident branch** cho scenario này: nếu PR hotfix v5.2.1 fail security scan vì một HIGH finding, IC nên quyết định thế nào? Viết decision tree gồm: điều kiện cho phép override, ai phải approve, cách ghi audit trail, và plan verify sau deploy.

---

## Solutions

<details>
<summary>Exercise 1 (Easy) — Sample Solution</summary>

### 1. Severity: SEV2 — Justification

> **Severity: SEV2 (High)**
> - Service degraded significantly (18% error rate, p99 latency 100x normal)
> - Multiple user-facing features impacted (checkout, search likely affected)
> - No complete outage (some traffic still succeeds ~82%)
> - Estimated impact: >20% users affected
> - Rule: when in doubt, escalate → we can always downgrade

### 2. Incident Channel Opening Message

```
🔴 SEV2 INCIDENT OPENED — API Degradation
Channel: #incident-YYYYMMDD-001
Time: 09:15 UTC
IC: @on-call (you)
Ops Lead: TBD — requesting @db-owner
Comms Lead: TBD — requesting @support-lead

Impact:
- API error rate: 18% (baseline: 0.3%)
- Latency p99: 12s (baseline: 120ms)
- ~25% users unable to complete requests
- Payment flow likely affected

Current hypothesis: Database connection pool exhaustion or slow query
Current action: Investigating DB connection metrics

Update in 10 minutes.
```

### 3. Role Assignments

| Role | Person | Responsibility |
|------|--------|---------------|
| Incident Commander | @on-call | Owns incident, makes decisions, coordinates |
| Ops Lead | @db-owner | Investigate DB, check connection pools, query performance |
| Comms Lead | @support-lead | Update status page, notify stakeholders |

### 4. Three Hypotheses

```
H1: DB Connection Pool Exhaustion
IF: Connection pool maxed AND slow queries consuming connections
THEN: New requests will timeout waiting for connection
BECAUSE: We see "connection timeout" errors in logs
VERIFY: Check pg_stat_activity, connection pool metrics, slow query log

H2: Database Primary Replica Lag
IF: Read replica lag > 30s AND app routes reads to replica
THEN: Users see stale data or timeout on read-heavy endpoints
VERIFY: Check replication lag metric, switch to primary for reads

H3: Disk/IO Saturation
IF: DB disk I/O wait > 50% AND queries waiting for disk
THEN: All DB operations slow to crawl
VERIFY: Check disk I/O metrics, cloudwatch EBS metrics
```

### 5. Status Page Messages

**Internal (Slack #general):**
```
[SEV2] Investigating API Degradation
We are aware of elevated error rates on our API (currently ~18%).
Our engineering team is actively investigating.
No customer action required. We expect an update in 30 minutes.
```

**External (Status Page):**
```
[DEGRADED PERFORMANCE] We are currently experiencing elevated latency
and error rates on our API. Some users may experience slower response times.
Our team is investigating and working on a resolution.
```

</details>

<details>
<summary>Exercise 2 (Medium) — Sample Solution</summary>

### 1. Clean Timeline Table

| Time (UTC) | Event | Actor | Action |
|------------|-------|-------|--------|
| 09:14 | v2.4.1 deployed to staging | @hieu | Code push |
| 09:16 | CI/CD pipeline passes | System | Automated test |
| 09:30 | Production deployment requested | @hieu | Approval request |
| 09:32 | Production deployment approved | @minh | Manual approval |
| 09:35 | v2.4.1 deployment starts | System | CI/CD pipeline |
| 09:37 | v2.4.1 at 100% traffic | System | Deployment complete |
| 09:38 | Cache hit rate drops to 12% | System | Metric anomaly detected |
| 09:39 | Latency p99 climbs from 300ms → 3000ms | System | Progressive degradation |
| 09:42 | SLO burn rate alert fires | PagerDuty | Automated alert |
| 09:44 | On-call acknowledges | @ngoc.wake | Human response |
| 09:46 | Ops Lead joins incident channel | @thao.nguyen | Incident participation |
| 09:47 | SEV2 declared | @lan (IC) | Severity assessment |
| 09:48 | Status page updated | @dung (Comms) | External communication |
| 09:50 | Root cause identified: cache type change | Investigation | Root cause found |
| 09:53 | Rollback decision made | @lan (IC) | Mitigation decision |
| 09:55 | Rollback executed | @thao.nguyen | Mitigation action |
| 09:57 | Latency begins recovery | System | Recovery begins |
| 10:02 | API fully recovered | System | Recovery confirmed |
| 10:05 | Incident closed | @lan (IC) | Incident resolved |
| 10:08 | Postmortem scheduled | @lan (IC) | Process follow-up |

### 2. Blameless Postmortem

```markdown
## Postmortem: Cache Architecture Change — API Latency Incident

**Duration**: 30 minutes (09:38–10:02 UTC)
**Severity**: SEV2
**Error Budget Impact**: 3.2% of monthly budget burned in 30 minutes

### Root Cause Summary
v2.4.1 replaced Redis distributed cache with local in-memory LRU cache.
In-memory cache on each API pod has no shared state → cache hit rate
dropped from 98% to 12% → every request generates a new database query →
database overwhelmed → latency spike 100x.

### Timeline: (see table above)

### 5 Whys Analysis

Why #1: Why did API latency spike 100x?
→ Cache hit rate dropped from 98% to 12%

Why #2: Why did cache hit rate drop?
→ v2.4.1 changed cache implementation from Redis (shared) to in-memory (per-pod)

Why #3: Why was in-memory cache chosen over Redis?
→ Developer assumed in-memory LRU cache would perform better for single-pod
   deployments (staging has 1 pod; production has 8 pods)

Why #4: Why did deployment pass CI/CD with no issues?
→ CI/CD pipeline tests on 1-pod staging environment; in-memory cache hit rate
   is still high in single-pod → test environment did not reflect production topology

Why #5: Why did the 8-pod production topology not exist in staging?
→ Staging environment uses smaller instance types with 1 pod for cost optimization;
   cache hit rate behavior differs significantly between 1-pod and multi-pod topologies

**ROOT CAUSE**: Staging topology (1 pod) does not reflect production topology (8 pods);
   performance tests in staging did not catch cache consistency issue in distributed environment.

### What Went Well
- PagerDuty alert fired within 4 minutes of deployment (SLO burn rate alert)
- On-call acknowledged within 2 minutes
- Rollback was fast (~2 minutes) — rollback runbook was clear and tested
- Team communicated effectively in incident channel

### What Went Poorly
- Cache type change was high-risk but reviewed quickly by Tech Lead
- Staging topology does not match production — performance tests are not representative
- No cache consistency check in automated tests
- Error budget was already at 60% before this incident

### Action Items

| ID | Action | Owner | Deadline | Priority | Ticket |
|----|--------|-------|----------|----------|--------|
| A1 | Add cache consistency test to CI/CD: deploy to 3-pod staging, verify hit rate >90% | @hieu | 2024-11-25 | P1 | INFRA-1832 |
| A2 | Mirror production pod count in staging performance tests | @thao | 2024-12-02 | P1 | INFRA-1833 |
| A3 | Create architecture review checklist for cache/storage layer changes | @minh | 2024-11-28 | P2 | ENG-992 |
| A4 | Add cache hit rate to SLO dashboard and set 95% baseline alert | @dung | 2024-11-22 | P1 | MON-447 |

### Lessons Learned
1. Cache layer changes are high-risk in distributed systems — must test with multi-pod topology
2. Staging environment fidelity matters — cost savings in staging can create blind spots in production
3. Tech Lead reviews of high-risk changes need a specific checklist, not just "looks fine"
```

### 3. Blameless Violations in Original Timeline

**Violation found:**
- `Developer @hieu push code v2.4.1` → Cá nhân hóa action
- `Tech Lead @minh approves (didn't review code in detail)` → Implicit blame on @minh

**Refactored (blameless):**
- `v2.4.1 deployment to staging initiated`
- `v2.4.1 production deployment approved — code review did not include cache consistency check`

</details>

<details>
<summary>Exercise 3 (Hard) — Sample Solution</summary>

### 1. IC Decision Log

```
IC DECISION LOG — #incident-20241120-001
=====================================

10:05 [SEV1 DECLARED]
Decision: Declare SEV1 immediately
Rationale: ~40,000 users cannot access any service; auth is foundational
Risk: Minimal — over-response is better than under-response
Communication: Comms Lead update status page within 5 min

10:07 [ROLES ASSIGNED]
Decision: Split unified IC into Team Alpha IC (@phuong) + Team Beta IC (@quan)
Rationale: Auth+User+Profile (Alpha) and Content (Beta) are separate teams;
           unified IC prevents bottlenecks
Risk: Need coordination protocol between ICs
Communication: Shared bridge, Comms Lead in both channels

10:10 [TEAM BETA MITIGATION APPROVED]
Decision: Enable "auth-optional mode" feature flag on Content Service
Rationale: 70% of content still accessible; reduces user impact immediately
Risk: Low — feature flag is a config change, no deploy needed, reversible
Action: @quan.le toggles feature flag immediately
Communication: Comms Lead update — "Some features available without login"

10:15 [ROOT CAUSE IDENTIFIED — AUTH BUG]
Decision: Notify Comms Lead of technical root cause (internal only)
Rationale: Technical team needs accurate information; external users don't need this detail
Risk: None — sharing facts internally is standard practice
Communication: Internal Slack with root cause; external stays at high level

10:20 [HOTFIX DECISION]
Decision: Proceed with v5.2.1 hotfix (security fix + auth bug fix)
Rationale:
  - Security fix (CVE-2024-XXXXX) must be deployed — cannot leave unpatched
  - Auth bug fix is in PR #1847 — already reviewed, ready to merge
  - Net effect: security patch + bug fix together
Risk:
  - Hotfix requires security scan (~25 min)
  - Alternative: rollback and lose security fix (NOT ACCEPTABLE for CVE)
Communication: Comms Lead — ETA updated to 10:45 for full resolution

10:25 [STAGING VERIFICATION]
Decision: Deploy to staging first, verify fix before production
Rationale: Must not introduce new bug while fixing this one
Risk: Adds 5-10 minutes to timeline
Communication: Comms Lead — "Fix being tested before deployment"

10:30 [STAGING PASSED]
Decision: Proceed to production deployment
Rationale: Staging tests pass, hotfix verified
Risk: Standard deployment risk
Action: @thao.nguyen executes production deploy

10:40 [PRODUCTION DEPLOYED]
Decision: Monitor for 5 minutes before closing
Rationale: Confirm error rate returns to baseline
Communication: Comms Lead — "Fix deployed, monitoring"

10:45 [RECOVERY CONFIRMED]
Decision: Declare incident resolved
Rationale: All metrics at baseline; Content Service auth-optional mode disabling
Risk: None
Communication: Status page "Resolved"; postmortem scheduled
```

### 2. Team Beta Mitigation Plan

```
TEAM BETA MITIGATION — Content Service Auth-Optional Mode
===========================================================

Objective: Restore 70% of Content Service functionality while Auth is broken

Step 1: Verify feature flag exists and is functional
  - Command: GET /api/flags/auth-optional-mode
  - Expected: flag exists, current value: disabled

Step 2: Enable feature flag
  - Command: POST /api/flags/auth-optional-mode {value: true}
  - Or via config: AUTH_OPTIONAL=true kubectl rollout restart deployment/content-service

Step 3: Verify functionality
  - Test: curl https://api.example.com/content/trending
  - Expected: 200 OK (no auth required)

Step 4: Monitor error rate
  - Dashboard: Content Service error rate
  - Expected: Drop from 45% to <5% after flag enabled

Step 5: Verify logged-out users can access content
  - Send 5 requests from anonymous browser session
  - Expected: All return 200 with content

Step 6: Plan for rollback (if needed)
  - Command: Same flag toggle to disable
  - Verification: Auth-required behavior restored

Timeline: 5 minutes (Step 1-3), 2 minutes monitoring
```

### 3. Risk Assessment Table

| Option | Availability Impact | Security Impact | Timeline | Risk |
|--------|--------------------|--------------------|----------|------|
| Rollback to pre-CVE | Restore auth immediately | **CRITICAL: CVE unpatched** | 3 min | Security breach |
| Deploy hotfix v5.2.1 | Restore in ~25 min | Fixed | 25 min | Same as hotfix risk |
| Feature flag (temp fix) | Team Beta OK, Team Alpha still down | CVE remains | Immediate partial | CVE remains, partial mitigation |
| **Hotfix + Feature Flag (recommended)** | **Full fix ~25 min, partial mitigation immediate** | Fixed | **25 min** | **Lowest combined risk** |

### 4. Cross-Team Coordination Checklist

```
CROSS-TEAM COORDINATION PROTOCOL
=================================

10:07 — Unified IC briefing
  □ Share architecture diagram with both ICs
  □ Establish shared decision log channel
  □ Agree on severity: SEV1, unified command

10:10 — Dependency mapping
  □ Team Beta: confirms Content → Auth dependency is only 30% of calls
  □ Team Alpha: confirms Auth → User/Profile cascading effect
  □ Unified IC: approves Team Beta feature flag mitigation

10:15 — Resource coordination
  □ Shared monitoring dashboard (Auth + User + Profile + Content on one screen)
  □ Team Alpha gets DB engineer support
  □ Team Beta focuses on graceful degradation

10:20 — Decision alignment
  □ Both ICs agree on hotfix approach (not rollback)
  □ Confirm: no deployment from Team Beta during hotfix window
  □ Unified IC makes final call on security vs availability tradeoff

10:30 — Verification coordination
  □ Team Beta verifies auth-optional mode still works after hotfix
  □ Team Alpha confirms auth service metrics after hotfix

10:45 — Recovery coordination
  □ Team Beta: disable auth-optional mode
  □ Team Alpha: verify full auth flow
  □ Unified IC: confirms all services at baseline
```

### 5. Comms Messages

**Internal Update 10:10:**
```
[INCIDENT UPDATE] SEV1 — Auth Service Failures
Time: 10:10 UTC
Status: MITIGATING (partial)

Impact: Auth service returning false 401 errors
Team Alpha (Auth/User/Profile): Root cause identified, working on fix
Team Beta (Content): Auth-optional mode enabled, 70% functionality restored
ETA to full resolution: ~25 minutes

Next update: 10:20 UTC
```

**Internal Update 10:20:**
```
[INCIDENT UPDATE] SEV1 — Auth Service Failures
Time: 10:20 UTC
Status: MITIGATING → RESOLVING

Update: Hotfix being tested in staging (contains both security patch + auth fix)
Team Beta: Fully operational in auth-optional mode
Team Alpha: Monitoring staging test results
ETA to full resolution: ~15 minutes

Next update: 10:35 UTC
```

**Internal Update 10:35:**
```
[INCIDENT UPDATE] SEV1 — Auth Service Failures
Time: 10:35 UTC
Status: RESOLVING → MONITORING

Update: Hotfix passed staging. Deploying to production now.
Team Beta: Maintaining auth-optional mode as precaution
Team Alpha: Production deployment in progress
ETA to full resolution: ~10 minutes

Next update: 10:45 UTC
```

**External Status Page 10:15:**
```
[DEGRADED SERVICE] Some users may experience difficulty logging in to our platform.
Our team is actively working to resolve this issue.
We expect to provide an update within 30 minutes.
```

**External Status Page 10:40:**
```
[INVESTIGATING UPDATE] Our team has identified the cause and is deploying a fix.
We expect full service restoration within the next 15 minutes.
We apologize for the inconvenience and will provide another update shortly.
```

**External Status Page (Resolution 10:45):**
```
[RESOLVED] The login issue affecting some users has been fully resolved as of 10:45 UTC.
All services are operating normally. We sincerely apologize for the inconvenience.
A detailed postmortem will be published within 5 business days.
```

### 6. Action Items (6 items across 2 teams)

| ID | Action | Owner | Deadline | Priority | Ticket | Team |
|----|--------|-------|----------|----------|--------|------|
| A1 | Implement auth circuit breaker in Content Service (fail-open on auth timeout) | @quan.le | 2024-12-05 | P1 | SVC-3321 | Beta |
| A2 | Add auth service health check to Content Service startup | @quan.le | 2024-12-02 | P1 | SVC-3319 | Beta |
| A3 | Merge PR #1847 + security fix into v5.2.1 hotfix | @phuong.nguyen | 2024-11-20 | P0 | SEC-99 | Alpha |
| A4 | Add JWT validation unit tests covering expiry boundary cases | @phuong.nguyen | 2024-11-28 | P1 | AUTH-881 | Alpha |
| A5 | Implement feature flag infrastructure for auth-optional mode in all services | @thao.nguyen | 2024-12-10 | P2 | PLAT-201 | Platform |
| A6 | Create chaos testing suite: auth service failure scenarios | @hue.tran | 2024-12-15 | P2 | QA-550 | QA |

</details>

---

## Bonus Challenge

### Design Your Team's Incident Response Playbook

Create a complete `incident-response-playbook.md` for your team's specific stack (pick one):

**Option A — Kubernetes-based microservices:**
- Include: kubectl commands for common mitigations (rollback, scale, drain)
- Include: who to page for which component (DB, networking, platform)

**Option B — Serverless (AWS Lambda + API Gateway):**
- Include: CloudWatch alarm → SNS → PagerDuty flow
- Include: Lambda function rollback via versioning

**Option C — Monolith on VMs (Petal / bare metal):**
- Include: SSH commands, systemctl, nginx restart
- Include: backup service restore procedure

Deliverable: A runbook document (3–5 pages) that a brand new engineer can follow during their first on-call shift.

---

## Grading Rubric

| Level | Criteria |
|-------|----------|
| **Exceeds (5/5)** | All criteria met + bonus challenge + real-world nuance addressed |
| **Meets (4/5)** | All acceptance criteria met, proper Vietnamese explanations |
| **Approaching (3/5)** | 3/5 acceptance criteria per exercise |
| **Beginning (2/5)** | Partial answers, missing key sections |
| **Not started (0/5)** | No submission |

