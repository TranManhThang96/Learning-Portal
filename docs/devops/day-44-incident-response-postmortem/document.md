# Day 44: Templates — Incident Response & Postmortem

> Copy → Fill in → Use immediately. Tất cả templates đều sẵn sàng cho production.

---

## Template 1: Severity Level Definitions

```markdown
# Incident Severity Level Definitions
# Tổ chức: [Tên công ty]
# Cập nhật: [YYYY-MM-DD]

## SEV1 — Critical
**Định nghĩa**: Dịch vụ core hoàn toàn không hoạt động, ảnh hưởng toàn bộ hoặc
               phần lớn users, mất doanh thu ngay lập tức.

**Ví dụ**:
- Payment service 100% down
- Database unresponsive (tất cả writes fail)
- Authentication service down (không ai login được)
- Data loss đang xảy ra

**Response SLA**:
- Acknowledge: < 5 phút
- IC assigned: < 10 phút
- Mitigation: < 30 phút
- Status page update: mỗi 15 phút

**Who to notify**: On-call, Eng Director, VP Engineering, Support Lead

---

## SEV2 — High
**Định nghĩa**: Service degraded nghiêm trọng, >20% users bị ảnh hưởng,
               tính năng core bị hỏng (nhưng không hoàn toàn), hoặc có nguy cơ
               leo thang thành SEV1.

**Ví dụ**:
- API error rate > 10%
- Latency p99 > 5x baseline
- Checkout flow broken (login vẫn OK)
- Database replica lag > 60s

**Response SLA**:
- Acknowledge: < 10 phút
- IC assigned: < 15 phút
- Mitigation: < 1 giờ
- Status page update: mỗi 30 phút

**Who to notify**: On-call, Eng Manager, Support Lead

---

## SEV3 — Medium
**Định nghĩa**: Ảnh hưởng tính năng non-critical, <20% users bị ảnh hưởng,
               có workaround, không mất doanh thu ngay.

**Ví dụ**:
- Search feature slow (checkout OK)
- Email notifications delayed 30+ phút
- Analytics dashboard không load
- Mobile app bị crash cho một số device

**Response SLA**:
- Acknowledge: < 30 phút
- Investigation bắt đầu: < 1 giờ
- Resolution: < 4 giờ
- Status page: optional (internal update đủ)

**Who to notify**: On-call, Eng Manager (next business day OK)

---

## SEV4 — Low
**Định nghĩa**: Minor issues, cosmetic bugs, ảnh hưởng rất ít users,
               không urgent, có thể xử lý trong sprint bình thường.

**Ví dụ**:
- UI typo hoặc layout lỗi nhỏ
- Non-critical feature không hoạt động cho <1% users
- Performance degradation nhỏ, không ảnh hưởng UX
- Documentation sai

**Response SLA**:
- Acknowledge: Next business day
- Resolution: Trong sprint hiện tại
- Status page: Không cần

**Who to notify**: Slack message cho relevant team là đủ

---

## Quy tắc Phân loại

Khi không chắc → ESCALATE lên level cao hơn.
Dễ downgrade hơn là miss một SEV1.

CHECKLIST nhanh:
□ Doanh thu đang mất? → SEV1
□ >50% users bị ảnh hưởng? → SEV1
□ Data đang bị mất hoặc corrupt? → SEV1
□ >20% users bị ảnh hưởng tính năng core? → SEV2
□ <20% users, có workaround? → SEV3
□ Cosmetic, minor usability? → SEV4
```

---

## Template 2: Incident Response Checklist

```markdown
# Incident Response Checklist
# Incident ID: INC-[YYYY]-[MMDD]-[NNN]
# Date: [YYYY-MM-DD]

## PHASE 1: DETECT & TRIAGE (Phút 0–10)

### On-Call Engineer (First Responder)
□ Acknowledge PagerDuty alert (< 5 phút)
□ Open Grafana / Datadog dashboard — check:
  □ Error rate
  □ Latency (p50, p95, p99)
  □ Traffic volume (normal vs spike?)
  □ Recent deployments (last 2 hours)
□ Assess severity:
  □ SEV1: Ngay lập tức page Eng Director
  □ SEV2: Page Eng Manager, Ops Lead
  □ SEV3/4: Handle solo or async
□ Open incident Slack channel: #incident-[YYYYMMDD]-[NNN]
□ Post initial assessment message (template: Section 3 bên dưới)

## PHASE 2: MOBILIZE (Phút 5–15)

### Incident Commander
□ Assign Ops Lead (technical investigation lead)
□ Assign Comms Lead (stakeholder + status page)
□ Invite SMEs nếu cần (DB expert, network, security)
□ Set update cadence (SEV1: 10 phút, SEV2: 15 phút)
□ Bridge call: tạo Zoom/Meet link và pin trong channel
□ Do NOT touch keyboard — delegate everything

### Comms Lead
□ Update internal status (Slack #engineering hoặc #general)
□ Update external status page (statuspage.io / Atlassian Status):
  □ Status: "Investigating"
  □ Affected components: [list]
  □ Message: (xem Template 4)
□ Notify support team với talking points
□ Notify Customer Success nếu enterprise customers bị ảnh hưởng

### Ops Lead
□ Check recent deployments:
  ```
  kubectl rollout history deployment/[service-name]
  git log --oneline -10
  ```
□ Check pod status:
  ```
  kubectl get pods -n [namespace]
  kubectl get events --sort-by='.lastTimestamp' -n [namespace]
  ```
□ Check resource usage:
  ```
  kubectl top pods -n [namespace]
  kubectl top nodes
  ```
□ Preserve evidence BEFORE making changes:
  ```
  kubectl logs deployment/[service] --since=2h > incident-logs-$(date +%Y%m%d-%H%M).txt
  ```

## PHASE 3: MITIGATE (Phút 10–30)

### Decision Matrix (IC approves, Ops Lead executes)
□ Code change was root cause? → Rollback:
  ```
  kubectl rollout undo deployment/[service-name]
  # verify:
  kubectl rollout status deployment/[service-name]
  ```
□ Specific feature broke? → Toggle feature flag
□ Single AZ/region issue? → Shift traffic
□ Memory/CPU saturation? → Scale up:
  ```
  kubectl scale deployment/[service-name] --replicas=[N]
  ```
□ Third-party API down? → Enable cached fallback mode

### Post-Mitigation Verification
□ Error rate returning to baseline?
□ Latency p99 returning to normal?
□ No new errors appearing in logs?
□ Monitor for minimum 15 minutes after mitigation

## PHASE 4: INVESTIGATE ROOT CAUSE

### Structured Investigation
□ What changed in last 2–4 hours? (deploys, config, infra)
□ Is issue reproducible? (staging, canary)
□ What do the metrics tell us? (correlate timestamps)
□ Check: DB slow queries, locks?
□ Check: Memory/CPU during incident?
□ Check: External dependencies (downstream services)?
□ Check: Network errors, timeouts?

## PHASE 5: RESOLVE & CLOSE

□ Long-term fix deployed and verified
□ Monitor 30 minutes after full fix
□ IC declares incident resolved
□ Comms Lead: update status page → "Resolved"
□ Post final update to #incident channel:
  - Duration
  - User impact
  - Root cause (one-liner)
  - Postmortem scheduled date
□ Close PagerDuty incident
□ Schedule postmortem (within 5 business days)
□ Create postmortem document (template: Section 3)
```

---

## Template 3: Blameless Postmortem

```markdown
# Blameless Postmortem

---

## Header

| Field | Value |
|-------|-------|
| Incident ID | INC-YYYY-MMDD-NNN |
| Date of Incident | YYYY-MM-DD |
| Duration | HH:MM – HH:MM UTC (X hours Y minutes) |
| Severity | SEV[1/2/3] |
| Postmortem Author | [name] |
| Postmortem Date | YYYY-MM-DD |
| Reviewers | [names] |
| Status | Draft / In Review / Final |

---

## 1. Executive Summary (5 phút đọc)

> [Một đoạn văn 3–4 câu. Viết như giải thích cho CEO không biết tech:
> "What happened, how many users were affected, how long, and what we did."]

**Impact**:
- Users affected: [số lượng / % total users]
- Revenue impact: [estimate nếu có]
- Services affected: [danh sách]
- Error budget burned: [X% of monthly budget]

---

## 2. Timeline

> Chỉ ghi facts. Không có judgment, không có tên cá nhân trong context blame.
> Format: "HH:MM UTC — [System/Tool/Process] performed [action]"

| Time (UTC) | Event | Notes |
|------------|-------|-------|
| HH:MM | [Earliest relevant event — e.g., deployment] | |
| HH:MM | [First anomalous metric] | |
| HH:MM | [Alert fired] | |
| HH:MM | [First human aware] | |
| HH:MM | [Incident channel opened] | |
| HH:MM | [SEV declared] | |
| HH:MM | [Status page updated] | |
| HH:MM | [Mitigation started] | |
| HH:MM | [Mitigation completed] | |
| HH:MM | [Recovery confirmed] | |
| HH:MM | [Incident closed] | |

---

## 3. Root Cause Analysis

### Contributing Factors
> Incidents thường có nhiều factors. List tất cả:

1. **Factor 1**: [Technical cause — e.g., "Memory leak in cache implementation"]
2. **Factor 2**: [Process gap — e.g., "No cache size validation in code review checklist"]
3. **Factor 3**: [Detection gap — e.g., "No memory usage alert threshold configured"]

### 5 Whys Analysis

```
SYMPTOM: [Initial observable symptom]

Why #1: [Tại sao symptom xảy ra?]
→ [Answer]

Why #2: [Tại sao answer #1 xảy ra?]
→ [Answer]

Why #3: [Tại sao answer #2 xảy ra?]
→ [Answer]

Why #4: [Tại sao answer #3 xảy ra?]
→ [Answer]

Why #5: [Tại sao answer #4 xảy ra?]
→ [Systemic root cause — process, tooling, culture]

ROOT CAUSE: [One clear statement of systemic cause]
```

---

## 4. What Went Well

> Không bỏ section này. Học từ success quan trọng như học từ failure.

- [e.g., Alert fired within X minutes of issue start]
- [e.g., Rollback was successful in < 5 minutes due to runbook]
- [e.g., Communication with customers was proactive and clear]
- [e.g., On-call acknowledged within SLA]

---

## 5. What Went Poorly

> Focus on systems, processes, tools — không mention individuals.

- [e.g., No alert for OOMKill events — detection delayed 7 minutes]
- [e.g., Runbook was out of date — required ad-hoc investigation]
- [e.g., Staging load tests do not reflect production data volume]
- [e.g., Status page update was 10 minutes late]

---

## 6. Action Items

> Mỗi item PHẢI có: owner (1 người), deadline, priority, ticket link.
> Action items không có owner sẽ không được thực hiện.

| ID | Action | Owner | Deadline | Priority | Ticket | Status |
|----|--------|-------|----------|----------|--------|--------|
| A1 | [Specific, measurable action] | @[name] | YYYY-MM-DD | P1 | #link | Open |
| A2 | [Specific, measurable action] | @[name] | YYYY-MM-DD | P1 | #link | Open |
| A3 | [Specific, measurable action] | @[name] | YYYY-MM-DD | P2 | #link | Open |
| A4 | [Specific, measurable action] | @[name] | YYYY-MM-DD | P2 | #link | Open |

**Priority definitions:**
- P0: Security vulnerability, do immediately
- P1: Directly prevents same incident — done in 1 week
- P2: Improves resilience — done in 1 month
- P3: Nice to have — done in quarter

---

## 7. Lessons Learned

> 2–3 key takeaways. Write for engineers who weren't involved in this incident.

1. **[Lesson title]**: [1–2 sentence explanation of what we learned]
2. **[Lesson title]**: [1–2 sentence explanation of what we learned]
3. **[Lesson title]**: [1–2 sentence explanation of what we learned]

---

## Appendix (optional)

- Relevant logs
- Dashboard screenshots at time of incident
- Traces or distributed telemetry
- Architecture diagram
```

---

## Template 4: Communication Templates

```markdown
# Incident Communication Templates

## A. Internal Slack Updates

### Opening Message (post trong #incident channel)
```
[INCIDENT OPENED] SEV[1/2] — [Service Name] [Issue Type]
Time: HH:MM UTC
IC: @[name]
Ops Lead: @[name]
Comms Lead: @[name]

Impact:
- [Metric]: [current value] (baseline: [normal value])
- [Estimate of users affected]
- [Which features are broken]

Current action: [What we're doing right now]

Bridge: [Zoom/Meet link]
Next update: HH:MM UTC
#incident-[YYYYMMDD]-[NNN]
```

### Regular Update Message (mỗi 10–15 phút cho SEV1)
```
[INCIDENT UPDATE #N] SEV[1/2] — [Service Name]
Time: HH:MM UTC

Status: INVESTIGATING / MITIGATING / MONITORING

Current metrics:
- Error rate: X% (was Y% last update)
- Latency p99: Xms

Progress: [What has been done since last update]
Current action: [What we're doing right now]
ETA: [Best estimate, or "unknown — next update in 10 min"]

Next update: HH:MM UTC
```

### Resolution Message
```
[INCIDENT RESOLVED] SEV[1/2] — [Service Name]
Time: HH:MM UTC
Duration: X hours Y minutes

Summary: [One-line root cause]
Impact: [How many users, how long]

All services are operating normally.
Postmortem scheduled: [Date + Time]
```

---

## B. Status Page Templates (External)

### Status: Investigating
```
We are currently investigating [brief description of issue].
Some users may be experiencing [symptom description in plain language].
Our team is actively working on a resolution.
Next update in 30 minutes.
```

### Status: Identified
```
We have identified the cause of [brief issue description] and are working on a fix.
We expect to resolve this by [estimated time].
We will provide another update shortly.
```

### Status: Monitoring
```
A fix has been deployed for [brief issue description].
We are monitoring the situation to ensure the problem has been fully resolved.
Thank you for your patience.
```

### Status: Resolved
```
This incident has been resolved as of [HH:MM UTC].
All systems are operating normally.
We sincerely apologize for any inconvenience this may have caused.
A full post-incident report will be available within 5 business days.
```

---

## C. Stakeholder Briefing (cho Exec/Sales/Support)

```
INCIDENT BRIEF — [Date] [Time]

What happened: [2–3 sentences explaining in business terms, no jargon]

Who was affected: [Number of customers / % of users]

Current status: [INVESTIGATING / MITIGATING / RESOLVED]

Business impact: [Revenue estimate, customer complaints expected]

What we're doing: [High-level, not technical]

ETA: [Best estimate]

Next update: [Time]

Questions? Contact: @[comms-lead or eng-manager]
```

---

## D. Customer-Facing Email (nếu cần cho enterprise customers)

**Subject**: Service Disruption — [Date] — Action Required: None

```
Dear [Customer Name],

We are writing to inform you of a recent service disruption that may have
affected your use of [Product Name].

Incident: [Brief description in plain terms]
Duration: [Start time] to [End time] ([X] hours [Y] minutes)
Impact to your account: [Specific to customer if possible, or generic]

We sincerely apologize for this disruption. Our team has resolved the issue
and all services are now operating normally.

We take reliability seriously and are implementing improvements to prevent
similar issues in the future. A full post-incident report will be available at
[status page URL] within 5 business days.

If you have any questions or continue to experience issues, please contact
our support team at [support email].

Sincerely,
[Name]
[Title]
[Company]
```
```

---

## Template 5: 5 Whys Worksheet

```markdown
# 5 Whys Worksheet
# Incident: INC-[YYYY]-[MMDD]-[NNN]
# Date: [YYYY-MM-DD]
# Facilitator: [Name]
# Participants: [Names]

---

## Incident Summary
[One sentence describing what happened]

## Starting Point: Observable Symptom
[What did users / monitoring see? e.g., "API returning 503 errors"]

---

## WHY CHAIN

### Why #1
**Question**: Tại sao [symptom] xảy ra?
**Answer**: ___________________________________________
**Evidence**: [Metric, log line, or observation that supports this answer]

### Why #2
**Question**: Tại sao [answer #1] xảy ra?
**Answer**: ___________________________________________
**Evidence**: [Metric, log line, or observation that supports this answer]

### Why #3
**Question**: Tại sao [answer #2] xảy ra?
**Answer**: ___________________________________________
**Evidence**: [Metric, log line, or observation that supports this answer]

### Why #4
**Question**: Tại sao [answer #3] xảy ra?
**Answer**: ___________________________________________
**Evidence**: [Metric, log line, or observation that supports this answer]

### Why #5
**Question**: Tại sao [answer #4] xảy ra?
**Answer**: ___________________________________________
**Evidence**: [Metric, log line, or observation that supports this answer]

---

## Root Cause Statement
[Complete this sentence: "The root cause of this incident is that our SYSTEM/PROCESS
did not [safeguard] which allowed [technical failure] to result in [user impact]."]

Example: "The root cause of this incident is that our staging environment does not
run with production-scale data, which allowed a cache miss pattern (harmful only at scale)
to reach production without detection, resulting in 38 minutes of API degradation."

---

## Counterfactual Check
"If we had fixed the root cause, would this incident have been prevented?"
□ Yes → Root cause is correct
□ No → Go deeper (Why #6, #7)

---

## Systemic Actions (not individual)
[List 2-3 systemic improvements that address root cause]
1. ___________________________________________
2. ___________________________________________
3. ___________________________________________

---

## Anti-Patterns to Avoid in This Analysis
□ Did NOT blame individuals
□ Did NOT stop at proximate cause (first Why)
□ Did NOT assume individual error was the root cause
□ DID find a systemic fix (process, tooling, monitoring, testing)
```

---

## Template 6: Action Items Tracking

```markdown
# Postmortem Action Items Tracker
# Linked to Postmortem: [PM ID]
# Owner of tracker: [Name]
# Review cadence: Weekly in team standup

---

## Active Action Items

| ID | Title | Owner | Due Date | Priority | Status | Ticket | Notes |
|----|-------|-------|----------|----------|--------|--------|-------|
| [PM-ID]-A1 | [Action] | @[name] | YYYY-MM-DD | P1 | Open | #[link] | |
| [PM-ID]-A2 | [Action] | @[name] | YYYY-MM-DD | P1 | In Progress | #[link] | |
| [PM-ID]-A3 | [Action] | @[name] | YYYY-MM-DD | P2 | Open | #[link] | |

**Status values**: Open / In Progress / Done / Cancelled / Deferred

---

## Closed Action Items

| ID | Title | Owner | Closed Date | Outcome |
|----|-------|-------|-------------|---------|
| [ID] | [Action] | @[name] | YYYY-MM-DD | [Completed / Cancelled + reason] |

---

## Action Item Health Check (review weekly)

```
Overdue (past deadline, not Done):
- [ ] [List any overdue items]

Blocked (In Progress, no movement > 1 week):
- [ ] [List any blocked items + blocker]

At Risk (due within 7 days, not In Progress):
- [ ] [List any at-risk items]
```

---

## Review History

| Date | Reviewer | Items Completed | Items Added | Notes |
|------|----------|-----------------|-------------|-------|
| YYYY-MM-DD | @[name] | [N] | [N] | [Summary] |

---

## Definition of Done (per action item)

An action item is DONE when:
1. The code/config/process change has been merged/deployed
2. A test or metric confirms the change works as expected
3. The Jira/GitHub ticket is closed
4. Owner has confirmed in the postmortem tracker
```

---

## Template 7: On-Call Handoff

```markdown
# On-Call Handoff
# From: [Name] (@handle)
# To: [Name] (@handle)
# Handoff Time: YYYY-MM-DD HH:MM UTC
# Period Covered: YYYY-MM-DD HH:MM → YYYY-MM-DD HH:MM UTC

---

## 1. Active Incidents

> Mọi open incident PHẢI được handoff. Không được im lặng.

| Incident | Severity | Status | Summary | Bridge | Next Action |
|----------|----------|--------|---------|--------|-------------|
| #INC-... | SEV[N] | [Open/Monitoring] | [1 line] | [link] | [What incoming on-call should do] |

*Nếu không có active incidents: "No active incidents at time of handoff."*

---

## 2. Incidents This Shift (resolved)

| Incident | Severity | Duration | Summary | Postmortem |
|----------|----------|----------|---------|------------|
| #INC-... | SEV[N] | Xh Ym | [1 line root cause] | [Scheduled/Done] |

---

## 3. Known Fragile Systems

> Thứ gì đang "on the edge" — có thể fail mà incoming on-call cần để ý.

| System/Service | Risk | Owner | Watch Metric | Action if alert |
|----------------|------|-------|-------------|-----------------|
| [service-name] | [e.g., Memory at 85% limit] | @[name] | [metric name] | [e.g., Scale up immediately] |

---

## 4. Upcoming High-Risk Events

| Event | Time (UTC) | Risk | Rollback plan |
|-------|-----------|------|---------------|
| [e.g., DB migration] | YYYY-MM-DD HH:MM | High | [procedure or link] |
| [e.g., Traffic spike (event)] | YYYY-MM-DD | Medium | [scale-up runbook] |

---

## 5. Pending Alerts to Tune

> Alerts cần được điều chỉnh sau incident — đừng để incoming on-call bị phiền bởi false positives.

| Alert | Issue | Action |
|-------|-------|--------|
| [Alert name] | [e.g., Too sensitive, firing every 10 min] | [e.g., Increase threshold to 15%] |

---

## 6. Useful Links for This Shift

| Resource | URL |
|----------|-----|
| Monitoring Dashboard | [link] |
| Status Page Admin | [link] |
| Runbook | [link] |
| PagerDuty Escalation Policy | [link] |
| Incident Channel Template | #incident-YYYYMMDD-NNN |

---

## 7. Notes & Context

[Any other context the incoming on-call should know.
e.g., "CEO is doing a demo at 15:00 UTC — please be extra cautious about any deployments before then."
e.g., "DB team is migrating users table this evening — contact @db-lead if anything DB-related fires."]

---

## Handoff Confirmation

Outgoing on-call: _______________________ (sign)
Incoming on-call: _______________________ (sign / Slack acknowledgment)
Time: YYYY-MM-DD HH:MM UTC
```

---

## Quick Reference Card

```
INCIDENT RESPONSE QUICK REFERENCE
===================================

SEVERITY DECISION:
  Revenue loss / total outage → SEV1
  >20% users / core feature broken → SEV2
  <20% users / non-core / workaround → SEV3
  Cosmetic / minor → SEV4

FIRST 5 MINUTES (SEV1/SEV2):
  1. Acknowledge alert
  2. Assess severity
  3. Open #incident-YYYYMMDD-NNN channel
  4. Assign IC / Ops Lead / Comms Lead
  5. Update status page

MITIGATION ORDER:
  1. Rollback (if bad deploy)
  2. Feature flag toggle
  3. Traffic shift
  4. Scale up
  5. Kill switch
  6. Hotfix (last resort during incident)

RULE: Mitigate BEFORE finding root cause
RULE: Monitor 15–30 min after mitigation before closing
RULE: Never fix root cause during live incident

STATUS PAGE UPDATE CADENCE:
  SEV1: Every 15 minutes
  SEV2: Every 30 minutes
  SEV3: Optional, once

POSTMORTEM TIMELINE:
  - Schedule within 24h of resolution
  - Run within 5 business days
  - Publish within 1 week
  - Track action items weekly

BLAMELESS RULES:
  - No names in root cause
  - Ask "what failed" not "who failed"
  - Every action item needs 1 owner
  - "Done" = merged + verified, not just "done in my head"
```

