# Day 44: Incident Response & Postmortem

> **Phase 6 — Observability & Reliability (Ngày cuối)** | Thời lượng: ~2 giờ

---

## 1. Mục tiêu bài học

Sau bài học này, học viên có thể:

1. **Mô tả được vòng đời của một incident** từ detect → triage → mitigate → resolve → postmortem và thực hành theo đúng flow.
2. **Phân loại severity** (SEV1–SEV4) và quyết định được mức độ phản ứng phù hợp cho từng loại.
3. **Điều phối incident theo vai trò** — đảm nhận được Incident Commander, Ops Lead, hoặc Comms Lead trong một incident thực tế.
4. **Viết được blameless postmortem** đạt chuẩn SRE với timeline chính xác, root cause rõ ràng, và action items có accountability.
5. **Áp dụng kỹ thuật 5 Whys** để tìm root cause thật sự thay vì dừng ở proximate cause.

---

## 2. Bối cảnh & Động lực

### Tại sao incident response process quan trọng?

Bạn đã xây dựng monitoring tốt (Day 38–42), thiết lập SLO và alert thông minh (Day 43). Nhưng **alert chỉ là khởi đầu**. Điều thực sự xác định chất lượng của một team là: **họ phản ứng như thế nào khi production bị sự cố?**

```
Không có process chuẩn:           Có incident response process:
─────────────────────────────      ────────────────────────────────
Alert → mọi người panic            Alert → IC được chỉ định
→ 5 người cùng SSH vào prod        → Ops Lead điều tra, IC điều phối
→ không ai biết ai đang làm gì     → Comms Lead giữ stakeholder updated
→ ai đó tắt service nhầm           → Mitigation thực hiện có kiểm soát
→ blame game sau incident          → Blameless postmortem để học
→ incident tái diễn 2 tuần sau    → Action items có owner/deadline
```

### Chi phí của việc không có process

| Tình huống | Hệ quả |
|------------|--------|
| Không phân công vai trò | MTTR tăng 2–5x vì overlap và coordination overhead |
| Blame culture | Engineers sợ thừa nhận lỗi → ẩn thông tin → root cause không tìm được |
| Không có postmortem | Cùng incident tái diễn trong 60–90 ngày |
| Action items không có owner | 80% action items không được thực hiện |

### Con số thực tế

- **AWS**: Mỗi phút downtime của một large e-commerce = ~$5,600 mất mát doanh thu (2023)
- **Google SRE**: Teams với blameless postmortem culture giảm repeat incidents **40–60%**
- **PagerDuty Research**: Incident response không có process → MTTR trung bình **4.5 giờ**; có process → **1.2 giờ**

### Kết nối với Day 43

Day 43 bạn đã học: SLO, Error Budget, và SLO-based alerting. Khi alert SLO budget burn rate cao (>14.4x trong 1 giờ) kích hoạt → đó chính là trigger để bắt đầu incident response flow của Day 44.

---

## 3. Kiến thức nền tảng

### 3.1 Incident Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                      INCIDENT LIFECYCLE                              │
├──────────┬──────────┬───────────┬───────────┬────────┬─────────────┤
│  DETECT  │  TRIAGE  │ MITIGATE  │ INVESTIGATE│RESOLVE │  POSTMORTEM │
├──────────┼──────────┼───────────┼───────────┼────────┼─────────────┤
│ Alert    │ Severity │ Stop the  │ Find root │ Full   │ Blameless   │
│ fired or │ assess-  │ bleeding  │ cause     │ fix    │ review      │
│ user     │ ment     │ (rollback,│           │ deploy │ within 5    │
│ report   │          │ ff, scale)│           │        │ business    │
│          │          │           │           │        │ days        │
├──────────┼──────────┼───────────┼───────────┼────────┼─────────────┤
│ Goal:    │ Goal:    │ Goal:     │ Goal:     │ Goal:  │ Goal:       │
│ Detect   │ Know     │ Restore   │ Understand│ Never  │ Learn and   │
│ fast     │ severity │ service   │ why       │ again  │ improve     │
│          │ + IC     │ ASAP      │           │        │             │
└──────────┴──────────┴───────────┴───────────┴────────┴─────────────┘

Key Metrics:
├─ MTTD (Mean Time To Detect): Detect → Triage
├─ MTTR (Mean Time To Respond/Resolve): Detect → Resolve
└─ MTTF (Mean Time To Fix): Mitigate → full Resolve
```

### 3.2 Severity Levels

| Level | Tên | Định nghĩa | Response Time | Ví dụ |
|-------|-----|------------|---------------|-------|
| **SEV1** | Critical | Service hoàn toàn không hoạt động, ảnh hưởng toàn bộ user, mất doanh thu | Ngay lập tức (<5 phút) | Database down, payment service 100% fail |
| **SEV2** | High | Service degraded nghiêm trọng, ảnh hưởng nhiều user hoặc tính năng core | <15 phút | Latency tăng 10x, 30% requests fail |
| **SEV3** | Medium | Ảnh hưởng một phần user hoặc tính năng không core, có workaround | <1 giờ | Search feature down (checkout vẫn OK) |
| **SEV4** | Low | Minor issue, cosmetic, ảnh hưởng không đáng kể | Trong ngày / sprint | Typo trên UI, analytics dashboard lag |

> **Rule of thumb**: Khi không chắc, **escalate lên level cao hơn**. Dễ downgrade hơn là miss một SEV1.

### 3.3 Vai trò trong Incident Response

```
                    ┌─────────────────────┐
                    │  INCIDENT COMMANDER │
                    │  (IC)               │
                    │  ─ Owns the incident│
                    │  ─ Final decisions  │
                    │  ─ Coordinates all  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌───────▼──────┐ ┌──────▼──────────┐
    │   OPS LEAD     │ │  COMMS LEAD  │ │  SME / EXPERTS  │
    │                │ │              │ │  (optional)     │
    │ ─ Technical    │ │ ─ Stakeholder│ │  ─ Database     │
    │   investigation│ │   updates    │ │  ─ Network      │
    │ ─ Mitigation   │ │ ─ Status page│ │  ─ Security     │
    │ ─ Coordinates  │ │ ─ Customer   │ │                 │
    │   engineers    │ │   support    │ │                 │
    └────────────────┘ └──────────────┘ └─────────────────┘
```

**Incident Commander (IC)**:
- Không phải là người "tốt nhất về technical" — là người **điều phối tốt nhất**
- Không SSH vào server — delegate mọi thứ
- Owns: severity declaration, role assignment, mitigation approval, postmortem scheduling
- Nói khi cần quyết định: *"Chúng ta rollback. @ops-lead thực hiện ngay."*

**Ops Lead**:
- Engineer technical dẫn dắt investigation và mitigation
- Assign sub-tasks cho engineers khác
- Report trạng thái cho IC mỗi 5–10 phút

**Comms Lead**:
- Cập nhật status page mỗi 15–30 phút
- Brief stakeholders (CEO, support team, sales) ở mức độ phù hợp
- Draft external communication nếu cần
- Người duy nhất được phép communicate ra ngoài

---

## 4. Deep Dive

### 4.1 Incident Response Flow chi tiết

```
ALERT FIRED / USER REPORT
        │
        ▼
┌───────────────────┐
│ 1. ACKNOWLEDGE    │ ← Ai đó nhận alert trong <5 phút
│    Alert/Report   │   (on-call engineer)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐    Severity < SEV3?
│ 2. INITIAL        │─────────────────────► Handle solo or
│    ASSESSMENT     │                        async, no IC needed
└────────┬──────────┘
         │ SEV1 or SEV2
         ▼
┌───────────────────┐
│ 3. OPEN INCIDENT  │ ← Tạo incident channel (#incident-YYYYMMDD-NNN)
│    CHANNEL        │   Declare severity
│    + ASSIGN ROLES │   Assign IC, Ops Lead, Comms Lead
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ 4. USER IMPACT    │ ← Comms Lead: status page "Investigating"
│    COMMUNICATION  │   Internal: notify Eng Director, Support
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ 5. MITIGATE FIRST │ ← Rollback? Feature flag? Traffic shift?
│    (if possible)  │   Goal: restore service, NOT find root cause
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ 6. INVESTIGATE    │ ← Đây mới là lúc tìm root cause
│    ROOT CAUSE     │   Hypothesis-driven debugging
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ 7. RESOLVE        │ ← Long-term fix deployed
│    + MONITOR      │   Watch metrics 30 phút sau khi fix
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ 8. CLOSE INCIDENT │ ← IC declares "incident resolved"
│    + SCHEDULE PM  │   Comms Lead: status page "Resolved"
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ 9. POSTMORTEM     │ ← Trong vòng 5 business days
│                   │   Blameless, publish internally
└───────────────────┘
```

### 4.2 Communication Templates

**Internal Update (mỗi 15–30 phút trong incident):**
```
[INCIDENT UPDATE] SEV1 - Payment Service Down
Time: 14:35 UTC
IC: @nguyen.van.a
Status: INVESTIGATING

Impact: ~40% users cannot complete checkout
Current action: Rolling back v2.3.1 → v2.3.0
ETA to mitigation: ~10 phút

Next update: 14:50 UTC
```

**External Status Page Update:**
```
[INVESTIGATING] We are experiencing issues with our payment processing service.
Some users may be unable to complete purchases.
Our team is actively working on a fix.
Next update in 30 minutes.
```

**External Status Update (sau khi mitigate):**
```
[MONITORING] The issue affecting payment processing has been identified and mitigated.
We are monitoring to confirm full recovery.
We apologize for the inconvenience.
```

**External Resolution:**
```
[RESOLVED] The payment processing issue has been fully resolved as of 15:12 UTC.
All services are operating normally. We will publish a full postmortem within 5 business days.
```

### 4.3 Mitigation Strategies

| Strategy | Khi nào dùng | Trade-off | Ví dụ |
|----------|-------------|-----------|-------|
| **Rollback** | Bad deploy là root cause | Mất features của deploy mới | `kubectl rollout undo deployment/api` |
| **Feature Flag** | Feature cụ thể gây lỗi | Cần flag infra có sẵn | Tắt "new checkout flow" flag |
| **Traffic Shift** | Một region/AZ bị ảnh hưởng | Traffic cao hơn ở region còn lại | Route 100% traffic sang us-east-1 |
| **Scale Up** | Capacity issue (OOM, CPU) | Tốn tiền, không fix root cause | Scale từ 3 → 10 replicas |
| **Kill Switch** | Feature gây lỗi nghiêm trọng | Mất functionality | Disable toàn bộ payment flow, redirect sang maintenance page |
| **Hotfix Deploy** | Root cause rõ ràng, fix nhỏ | Rủi ro deploy lúc hệ thống đang yếu | Cherry-pick fix, deploy qua fast track pipeline |

### 4.4 Blameless Postmortem Methodology

**Nguyên tắc cốt lõi:**

> "Individuals are not the problem — **systems are the problem**. People make mistakes. The system should prevent single human errors from causing incidents."
>
> — Google SRE Handbook

**5 điều blameless postmortem KHÔNG làm:**
1. ❌ Không đặt tên người trong root cause: *"A. đã xóa nhầm database"* → ✅ *"Command thực thi trực tiếp trên prod DB không có safety mechanism"*
2. ❌ Không hỏi "Ai đã làm điều này?" → ✅ Hỏi "Hệ thống nào cho phép điều này xảy ra?"
3. ❌ Không fire/punish người gây lỗi
4. ❌ Không dừng ở first cause (proximate cause)
5. ❌ Không kết thúc không có action items rõ ràng

**Cấu trúc blameless postmortem:**

```
1. INCIDENT SUMMARY (5 phút đọc)
   - Duration, severity, impact
   - One-line summary

2. TIMELINE (fact-based)
   - HH:MM UTC - Event (system action, not person)
   - No judgment, just facts

3. ROOT CAUSE ANALYSIS
   - Contributing factors (thường có nhiều hơn 1)
   - 5 Whys analysis

4. WHAT WENT WELL
   - Detection nhanh?
   - Rollback hoạt động tốt?
   - Communication tốt?

5. WHAT WENT POORLY
   - MTTD quá cao?
   - Alert không đủ?
   - Runbook lỗi thời?

6. ACTION ITEMS
   - Mỗi item: Owner, Deadline, Priority, Tracking link

7. LESSONS LEARNED
   - 2-3 key takeaways
```

### 4.5 Kỹ thuật 5 Whys

**Quy tắc**: Hỏi "Tại sao?" liên tục cho đến khi đến **systemic root cause**, không phải individual mistake.

**Ví dụ thực tế — Database connection pool exhausted:**

```
SYMPTOM: API trả về 502 errors

Why #1: Tại sao API trả về 502?
→ Vì API không connect được đến database (connection timeout)

Why #2: Tại sao API không connect được database?
→ Vì connection pool đã đạt max (100/100 connections used)

Why #3: Tại sao connection pool đầy?
→ Vì mỗi request tạo một DB connection mới và không release

Why #4: Tại sao connection không được release?
→ Vì code mới trong v2.4.0 có bug: connection không được close trong error path

Why #5: Tại sao bug này vào production?
→ Vì không có integration test cho error path, và code review không catch được
   resource leak khi exception xảy ra

ROOT CAUSE: Thiếu integration test coverage cho error paths và
            không có code review checklist về resource management
```

**Systemic fixes từ 5 Whys example trên:**
- Thêm integration tests cho all error paths
- Thêm connection pool monitoring alert
- Thêm mục "resource cleanup" vào code review checklist
- Enable connection pool leak detection trong staging

### 4.6 Action Items theo chuẩn SMART

Mỗi action item trong postmortem phải có:

| Field | Mô tả | Ví dụ |
|-------|-------|-------|
| **ID** | Tracking ID | PM-2024-11-001-A1 |
| **Title** | Mô tả ngắn gọn | Add connection pool exhaustion alert |
| **Owner** | 1 người chịu trách nhiệm (không phải team) | @tran.thi.b |
| **Deadline** | Ngày cụ thể | 2024-11-22 |
| **Priority** | P1/P2/P3 | P1 |
| **Status** | Open / In Progress / Done | Open |
| **Ticket** | Link Jira/GitHub issue | https://jira.../INFRA-4521 |
| **Prevents** | Incident tái diễn nếu action này done | Prevents connection pool exhaustion |

---

## 5. Trade-offs & Best Practices

### 5.1 Mitigate vs Fix Root Cause

```
MITIGATION                    ROOT CAUSE FIX
────────────────────────      ──────────────────────────
Goal: Restore service         Goal: Prevent recurrence
Time: Minutes                 Time: Hours to days
Risk: Low (known state)       Risk: Medium (new code)
Priority in incident: #1      Priority in incident: NEVER

                    THE RULE:
        During incident → ALWAYS mitigate first.
        Never try to fix root cause during an incident.
        Exception: if fix is a 1-line config change
                   with zero risk (e.g., increase timeout value)
```

**Lý do không fix root cause trong incident:**
- Engineer đang panic → higher bug risk
- Chưa có đủ thông tin để fix đúng
- Fix mới = second incident risk
- MTTR tăng nếu fix phức tạp

### 5.2 Overhead vs Speed cho Small Teams

| Team Size | Recommended Approach |
|-----------|---------------------|
| 1–5 người | Lightweight: 1 người = IC + Ops Lead, text update trong Slack |
| 5–20 người | Đầy đủ roles nhưng có thể combine Comms + IC cho SEV2/3 |
| 20+ người | Full process: dedicated IC, Comms Lead, formal channels |

**Với startup nhỏ**: Đừng skip postmortem vì "team nhỏ". Làm lightweight postmortem (30 phút, 1-page) vẫn tốt hơn không làm.

### 5.3 Postmortem Anti-Patterns

| Anti-Pattern | Tác hại | Solution |
|-------------|---------|---------|
| **Blame game**: "Tại A. push code sai" | Sợ hãi, thiếu transparency | Reframe: "Deployment pipeline không có safeguard" |
| **No follow-up**: Action items không tracking | Repeat incidents | Assign owner cụ thể, track trong Jira, đưa vào sprint |
| **Too formal**: 10-page postmortem cho SEV4 | PM fatigue, team stop doing PMs | Calibrate format theo severity |
| **Too fast**: PM 2 ngày sau incident khi còn nhớ | Thiếu fact, thiếu timeline | Do PM ngay khi mọi người còn nhớ, trong 2–5 ngày |
| **No WGWS**: Chỉ viết bad things | Mất morale, không học từ success | Luôn có "What Went Well" section |
| **Vague action items**: "Fix the bug" | Không ai làm | Mỗi item: owner, deadline, ticket link |

### 5.4 On-Call Scheduling & Burnout

```
Healthy On-Call:                  Toxic On-Call:
─────────────────────────         ─────────────────────────
- Rotation: 1 week / person       - Same 2 người on-call mãi
- Max 2-3 pages/night             - 10+ pages/night
- Primary + Secondary             - Không có backup
- Compensation policy clear       - "Just deal with it"
- Biz hours backup available      - Solo on-call 24/7
- Alert tuning after each PM      - Alert noise không giảm
```

**Rule**: Nếu on-call engineer bị page trên 2 lần/đêm trong 1 tuần → đây là SEV2 incident về alerting chất lượng. Ưu tiên fix alerting.

---

## 6. Performance & Scalability

### 6.1 Multiple Concurrent Incidents

Khi có 2+ incidents cùng lúc:

```
PRIORITY MATRIX:
                High Business Impact
                        │
              SEV1 ─────┼───── SEV1 với Customer Data
                        │
Low Tech ───────────────┼─────────────── High Tech
Complexity              │                Complexity
                        │
              SEV2 ─────┼───── SEV2 Security
                        │
                Low Business Impact

Rules:
1. Mỗi incident PHẢI có IC riêng
2. Không share Ops Lead cho 2 SEV1 cùng lúc
3. IC của incident cao hơn có thể claim resources từ IC thấp hơn
4. Bridge call riêng cho mỗi incident
```

### 6.2 Cross-Team Incidents

Khi incident span nhiều team (ví dụ: Platform + Backend + Data):

- **Unified IC**: 1 IC duy nhất điều phối tất cả
- **Sub-IC pattern**: Mỗi team có mini-IC report về Unified IC
- **Shared incident channel**: Tất cả trong 1 channel, mỗi team có thread riêng
- **Dependency mapping**: IC phải biết dependency giữa các teams để prioritize

### 6.3 Incident Metrics để track

```yaml
# Prometheus metrics to track
incident_total{severity="SEV1", status="open"}
incident_duration_seconds{severity="SEV1"}
incident_mttd_seconds  # detect time
incident_mttr_seconds  # resolve time
postmortem_action_items_total{status="open"}
postmortem_action_items_total{status="overdue"}
```

---

## 7. Security & Reliability Considerations

### 7.1 Security Incidents vs Availability Incidents

| Dimension | Availability Incident | Security Incident |
|-----------|----------------------|-------------------|
| Communication | Transparent, frequent updates | **Limited disclosure** — "need to know" only |
| Status Page | Update publicly | May NOT update details publicly |
| Root cause sharing | Full postmortem public | Partial or delayed disclosure |
| Mitigation | Restore service | Contain breach + change credentials |
| Evidence | Preserve logs | **Do NOT touch** — forensic evidence |

**Golden rule cho Security Incidents:**
1. **Isolate trước, investigate sau** — cut off attacker access ngay
2. **Không xóa bất cứ thứ gì** — preserve evidence
3. **Notify Legal/Compliance** ngay khi suspect data breach
4. **Kênh liên lạc riêng** — assume attackers may be watching Slack/email

### 7.2 Preserving Evidence Trong Incidents

```bash
# Ngay khi detect incident — capture state trước khi làm bất cứ điều gì
kubectl get events --sort-by='.lastTimestamp' > incident-events-$(date +%Y%m%d-%H%M).txt
kubectl logs deployment/api --since=2h > incident-logs-$(date +%Y%m%d-%H%M).txt

# Capture metrics snapshot
curl -s "http://prometheus:9090/api/v1/query?query=up" > metrics-snapshot.json

# DO NOT restart pods yet — lose logs
```

### 7.3 Post-Incident Security Review

Sau mỗi incident (kể cả availability):
- Có credentials nào bị expose không?
- Attacker có thể đã exploit window này không?
- Access logs có suspicious activity không?
- Cần rotate bất kỳ secret nào không?

---

## 8. Hands-on Example

### Scenario: E-Commerce Checkout Service Degradation

**Context**: Production e-commerce platform. 14:22 UTC, PagerDuty alert: `checkout-service error rate > 10% (SLO burn rate 20x)`.

#### Bước 1: Detect & Triage (14:22–14:27 UTC)

```
14:22 - PagerDuty pages on-call engineer @minh.le
14:23 - @minh.le acknowledges, checks dashboard
        → Error rate: 35% (checkout API)
        → Latency p99: 8s (normal: 200ms)
        → Other services: OK
14:25 - Declares SEV1
14:26 - Opens #incident-20241115-001
        IC: @minh.le (on-call lead)
        Ops Lead: @thanh.nguyen (checkout service owner)
        Comms Lead: @lan.tran (platform team)
```

#### Bước 2: Initial Communication (14:27 UTC)

```
Internal Slack #incident-20241115-001:
"SEV1 - Checkout service degraded. 35% error rate, 8s p99 latency.
IC: @minh.le | Ops: @thanh.nguyen | Comms: @lan.tran
Investigating. Update in 10 min."

Status page (by @lan.tran):
"[INVESTIGATING] We are aware of issues with our checkout service."
```

#### Bước 3: Mitigation (14:28–14:35 UTC)

```bash
# @thanh.nguyen investigates
kubectl get pods -n checkout
# NAME                        READY   STATUS    RESTARTS
# checkout-api-xxx-aaa        1/1     Running   0
# checkout-api-xxx-bbb        1/1     Running   0
# checkout-api-xxx-ccc        0/1     OOMKilled 12 ← !

kubectl top pods -n checkout
# checkout-api-xxx-aaa   450m   1800Mi  ← gần limit 2Gi
# checkout-api-xxx-bbb   420m   1750Mi

# Recent deployments?
kubectl rollout history deployment/checkout-api
# REVISION  CHANGE-CAUSE
# 5         v2.1.4 deployed 09:15 UTC
# 6         v2.1.5 deployed 13:58 UTC  ← 28 phút trước incident

# IC decision: Rollback
kubectl rollout undo deployment/checkout-api --to-revision=5
```

#### Bước 4: Verify & Monitor (14:35–15:00 UTC)

```
14:35 - Rollback completed. Error rate bắt đầu giảm.
14:38 - Error rate: 2% (normal baseline ~0.1%, đang recover)
14:42 - Error rate: 0.3%
14:50 - Error rate: 0.1% — fully recovered
14:50 - IC: "Monitoring for 10 more minutes before closing"
15:00 - IC: "Incident resolved. Ticket: #INC-2024-1115-001"
```

#### Bước 5: Timeline Documentation

```markdown
## Incident Timeline: INC-2024-1115-001

| Time (UTC) | Event |
|------------|-------|
| 13:58      | v2.1.5 deployed to production (checkout-service) |
| 14:15      | First pod OOMKilled (no alert configured for this) |
| 14:22      | SLO burn rate alert fires (35% error rate) |
| 14:22      | @minh.le paged via PagerDuty |
| 14:23      | Alert acknowledged by @minh.le |
| 14:25      | SEV1 declared |
| 14:26      | Incident channel opened, roles assigned |
| 14:27      | Status page updated: Investigating |
| 14:28      | Investigation begins — OOMKilled pods identified |
| 14:32      | Root cause hypothesis: memory leak in v2.1.5 |
| 14:33      | IC approves rollback to v2.1.4 |
| 14:35      | Rollback completed |
| 14:42      | Error rate recovering |
| 14:50      | Full recovery confirmed |
| 15:00      | Incident closed, postmortem scheduled |
```

#### Bước 6: Blameless Postmortem Draft

```markdown
## Postmortem: Checkout Service OOM — 2024-11-15

**Duration**: 38 minutes (14:22–15:00 UTC)
**Severity**: SEV1
**Impact**: ~35% of checkout requests failed; estimated ~$18,000 revenue impact

### Root Cause
v2.1.5 introduced a change to the product recommendation engine
that loaded the entire product catalog into memory per request
(272MB per request → 3 requests → OOMKill at 2Gi limit)

### 5 Whys
1. Why did checkout fail? → Pods were OOMKilled
2. Why were pods OOMKilled? → Memory exceeded 2Gi limit
3. Why did memory exceed limit? → v2.1.5 loaded full catalog per request
4. Why was this not caught? → Load test only uses 100 products; production has 50,000
5. Why didn't load test reflect production scale? → Test data not representative of production

### What Went Well
- SLO-based alert fired within 37 minutes of deployment (before user complaints)
- Rollback was fast (<3 minutes) due to clear kubectl commands in runbook
- Comms Lead kept stakeholders updated without IC distraction

### What Went Poorly
- No OOMKilled pod alert → 7 minutes of impact before SLO alert
- Load test dataset too small → 500x difference from production
- No memory profiling in staging

### Action Items
| ID | Action | Owner | Deadline | Priority |
|----|--------|-------|----------|----------|
| A1 | Add OOMKill alert for all pods | @thanh.nguyen | 2024-11-18 | P1 |
| A2 | Load test with production-scale dataset (50k products) | @quan.pham | 2024-11-25 | P1 |
| A3 | Add memory profiling step to staging CI | @lan.tran | 2024-11-29 | P2 |
| A4 | Memory limits review for all services | @minh.le | 2024-12-06 | P2 |
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Incident Response Mistakes

```
MISTAKE 1: "Tôi biết root cause rồi!"
→ Bẫy: Confirmation bias. Bạn thấy evidence phù hợp với hypothesis đầu tiên.
→ Fix: Luôn có hypothesis thứ 2. "What else could cause this?"

MISTAKE 2: Hero syndrome — 1 người làm tất cả
→ Tác hại: Bottleneck, burnout, single point of failure
→ Fix: IC phải delegate. "Tôi cần @thanh.nguyen check DB metrics ngay."

MISTAKE 3: Silence during incident
→ Tác hại: Stakeholders escalate, leadership gọi điện interrupt investigation
→ Fix: Comms Lead update mỗi 15 phút, kể cả khi "vẫn đang điều tra"

MISTAKE 4: Fixing prod trực tiếp không có review
→ Tác hại: Second incident từ hotfix
→ Fix: Rollback trước, fix sau. Mọi change phải có review dù 1 phút.

MISTAKE 5: Close incident khi "looks OK"
→ Tác hại: Incident tái diễn 30 phút sau
→ Fix: Monitor ít nhất 15–30 phút sau mitigation trước khi close
```

### 9.2 Running a Good Postmortem Meeting

**Trước khi họp (1–2 ngày trước):**
- Thu thập đầy đủ timeline từ logs, chat history
- Draft postmortem document
- Gửi draft cho participants check accuracy

**Trong meeting (45–60 phút):**
```
0-5 min:   Facilitator intro: "Đây là blameless postmortem. 
            Không blame individual. Chúng ta improve system."
5-20 min:  Walk through timeline — facts only, không phán xét
20-35 min: Root cause discussion — 5 Whys
35-50 min: Action items — brainstorm + assign
50-60 min: Lessons learned — top 3 takeaways
```

**Sau meeting:**
- Publish document trong 24 giờ
- Tạo tickets cho tất cả action items
- Share với toàn công ty (optional nhưng recommended)

---

### 9.3 Production Case Studies

---

#### Case Study 1: AWS US-EAST-1 Outage gây knock-on effect (Inspired by real events)

**Context**: B2B SaaS company, 500 enterprise customers, stack: AWS US-East-1, RDS Aurora, ECS Fargate, CloudFront.

**Symptom**:
- 08:15 UTC: PagerDuty flood — 47 alerts trong 3 phút
- API error rate: 89%
- Multiple services unreachable
- Support team nhận 200+ tickets trong 15 phút

**Investigation**:
```
08:15 - IC mở incident, declares SEV1
08:18 - Ops Lead nhận thấy: AWS Status page chưa có gì
08:20 - Mọi services CÙNG lúc fail → không phải code issue
08:22 - Check AWS Health Dashboard: "EC2 connectivity issues in us-east-1"
08:23 - Root cause identified: AWS infrastructure issue, NOT our code

Hypothesis: All services depend on us-east-1, no multi-region failover
```

**Root Cause**: AWS us-east-1 partial AZ failure. Company chỉ deploy ở một AZ, không có multi-AZ setup. Khi AZ đó bị ảnh hưởng → 89% services down (1/3 ECS tasks vẫn OK trong AZ khác).

**Mitigation**:
```bash
# Force shift traffic sang healthy AZ
aws ecs update-service \
  --cluster production \
  --service api-service \
  --force-new-deployment

# Scale up trong AZ khác
aws ecs update-service \
  --cluster production \
  --service api-service \
  --desired-count 20  # từ 6 lên 20, force placement ở AZ khác
```
→ Partial recovery sau 35 phút: error rate xuống 12%
→ AWS fixed AZ sau 90 phút: full recovery

**Long-term Fix**:
- Multi-AZ deployment bắt buộc cho tất cả services
- RDS Aurora Multi-AZ enabled (chi phí +40% nhưng HA)
- Runbook: "AWS Regional Issues" với playbook cụ thể
- CloudWatch Alarm cho AWS Service Health changes

**Lessons Learned**:
1. **External dependency incidents cần runbook riêng** — không có code để debug
2. **AWS Status Page lag thực tế** — khi AWS ack thì bạn đã bị impact 10–15 phút rồi
3. **Multi-AZ không optional đối với production SaaS**
4. **Alert storm masking**: 47 alerts nhưng chỉ có 1 root cause → cần alert grouping

**Prevention**:
- Thiết lập AWS Service Health → PagerDuty integration
- Multi-AZ là standard không được override
- Chaos Engineering: quarterly AZ failure drill

---

#### Case Study 2: Database Migration Gone Wrong

**Context**: Fintech startup, 50,000 active users, PostgreSQL 14 trên RDS, Rails monolith.

**Symptom**:
- 02:30 UTC (maintenance window): Migration bắt đầu
- 02:47 UTC: API p99 latency tăng từ 150ms → 45,000ms
- 02:52 UTC: PagerDuty fires — error rate 67%
- 02:52 UTC: On-call engineer woken up

**Investigation**:
```sql
-- Checking pg_stat_activity
SELECT pid, wait_event_type, wait_event, query, query_start
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start;

-- Kết quả:
-- 1 query: ALTER TABLE transactions ADD COLUMN metadata JSONB;
--   wait_event: Lock
--   running_for: 17 minutes
-- 247 queries: waiting on Lock (này mới là vấn đề!)
```

**Root Cause**:
```
ALTER TABLE ... ADD COLUMN yêu cầu ACCESS EXCLUSIVE LOCK trên table
→ Block tất cả reads và writes đến table 'transactions'
→ Table 'transactions' là hot table: 800 queries/second
→ Lock queue built up: 247 blocked queries
→ Connection pool exhausted

5 Whys:
1. Tại sao API down? → Connection pool exhausted
2. Tại sao connection pool exhausted? → 247 queries blocked
3. Tại sao queries blocked? → ALTER TABLE giữ lock
4. Tại sao ALTER TABLE giữ lock? → PostgreSQL behavior cho non-null columns
5. Tại sao không biết? → Migration review không có DBA sign-off,
                          không test trên production-scale data
```

**Mitigation**:
```sql
-- Kill migration (nguy hiểm nhưng cần thiết)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE query LIKE '%ALTER TABLE transactions%';

-- Unblock immediately
-- API recovered trong 2 phút sau khi kill migration
```

**Long-term Fix**:
```sql
-- Safe migration pattern cho large tables:
-- Bước 1: Add column với DEFAULT NULL (không cần lock)
ALTER TABLE transactions ADD COLUMN metadata JSONB;

-- Bước 2: Backfill data (offline, batch)
UPDATE transactions SET metadata = '{}' 
WHERE id > X AND id <= Y;  -- batch theo ID range

-- Bước 3: Add NOT NULL constraint riêng (PostgreSQL 12+: online)
ALTER TABLE transactions 
  ALTER COLUMN metadata SET NOT NULL,
  ALTER COLUMN metadata SET DEFAULT '{}';
```

**Lessons Learned**:
1. **Mọi migration trên table > 1M rows cần DBA review**
2. **Test migration trên staging với production data volume**
3. **Maintenance window ≠ "no monitoring needed"** — thực ra cần monitor chặt hơn
4. **Zero-downtime migration patterns** phải là standard, không phải optional

**Prevention**:
- Strong Migrations gem (Rails): tự động detect nguy hiểm
- Mandatory staging migration với production-clone data
- Migration checklist: table size, estimated lock time, rollback plan
- Separate migration tracking alert: migration running > 5 min → alert

---

#### Case Study 3: Memory Leak Dẫn đến Cascading Failure

**Context**: E-learning platform, 200,000 monthly active users, microservices trên Kubernetes (GKE), Node.js services.

**Symptom**:
- Thứ Hai 09:00 UTC: Đầu tuần,traffic bắt đầu tăng (từ cuối tuần thấp)
- 09:45 UTC: Video streaming service bắt đầu slow (p95 tăng từ 300ms → 2s)
- 10:15 UTC: Video service pods begin OOMKilling
- 10:20 UTC: Cascade: recommendation service (depend on video service) bắt đầu queue up
- 10:28 UTC: User service bị ảnh hưởng (session lookup calls recommendation service)
- 10:30 UTC: Full platform degradation, SEV1 declared
- Hơn 15,000 concurrent users bị ảnh hưởng

**Investigation Timeline**:
```
10:30 - IC opens #incident-20241118-001
        SEV1 declared. IC: @hung.vo | Ops: @mai.nguyen

10:33 - Ops Lead checks dashboards:
        → Video pods: Memory 1.9Gi/2Gi, CPU 80%
        → OOMKill restarts: 47 trong 30 phút
        → After restart: pods healthy 5 phút rồi leak lại

10:38 - Hypothesis 1: Traffic spike → check HPA
        → HPA scaling đang hoạt động (từ 5 → 15 pods)
        → Nhưng mỗi pod mới cũng bị OOMKill sau 5 phút
        → Conclusion: Không phải traffic spike, là memory leak

10:42 - Check recent deployments:
        → video-service v3.2.1 deployed Friday 17:00 UTC (3 ngày trước)
        → Không có incident weekend (traffic thấp)
        → Memory leak chỉ visible khi traffic cao

10:45 - Check v3.2.1 changelog:
        → Added video thumbnail caching (in-memory LRU cache)
        → Cache size: "unlimited" ← BUG: không có size limit

10:48 - Root cause confirmed
```

**Mitigation**:
```bash
# Option 1: Rollback video service
kubectl rollout undo deployment/video-service --to-revision=10
# Risk: mất thumbnail caching feature
# Timeline: 3 phút

# Option 2: Patch cache size via env var (nếu có flag)
kubectl set env deployment/video-service THUMBNAIL_CACHE_SIZE=500
# Risk: unknown nếu app không support
# Timeline: unknown

# IC decision: Rollback (guaranteed fix, low risk)
kubectl rollout undo deployment/video-service --to-revision=10

# Đồng thời: restart recommendation + user service để clear queue
kubectl rollout restart deployment/recommendation-service
kubectl rollout restart deployment/user-service
```

**Cascade Recovery**:
```
10:50 - Video service rollback deployed
10:52 - Video pod memory bắt đầu ổn định
10:55 - Recommendation service queue clearing
11:00 - User service recovery
11:05 - Full platform recovery confirmed
11:15 - Monitoring for 10 minutes — stable
11:25 - Incident closed
```

**Root Cause**:
```
v3.2.1 thêm in-memory thumbnail cache với unbounded size:
  const cache = new LRUCache(); // BUG: không set maxSize

Weekend: Low traffic → cache grows slowly → không hit limit
Monday: Traffic 5x → cache grows fast → OOMKill trong 5 phút
Cascade: OOMKill → rapid restarts → dependent services overwhelmed
```

**Long-term Fix**:
```javascript
// v3.2.2 fix:
const cache = new LRUCache({
  max: 500,                    // max 500 items
  maxSize: 100 * 1024 * 1024, // 100MB max
  sizeCalculation: (value) => Buffer.byteLength(value.data),
  ttl: 1000 * 60 * 60,        // 1 hour TTL
});
```

**Lessons Learned**:
1. **Memory leaks hide on weekends** — traffic patterns mask bugs. Weekend incidents ≠ no problems
2. **Unbounded caches are time bombs** — mọi cache phải có size limit
3. **Cascade failure planning**: circuit breaker between recommendation → video service để prevent cascade
4. **5-day delay** giữa deployment và incident — cần staging load test với production-level traffic

**Prevention**:
- Memory usage alert: pod memory > 80% of limit → SEV3
- Mandatory LRU cache size limits trong coding standards
- Circuit breaker pattern cho inter-service calls
- Load test trên staging với production traffic volume (không chỉ unit test)
- "Chaos Monday" weekly: tăng traffic 2x sau weekend để catch leaks sớm

---

## 10. Kết nối với bài trước & bài sau

### Từ Day 43 (SLI/SLO/Error Budget):
- **Alert trigger → Incident trigger**: Khi SLO burn rate alert kích hoạt (ví dụ: fast burn 14.4x trong 1 giờ), đó là tín hiệu để bắt đầu incident response flow
- **Error budget depletion** = SEV2 minimum nếu burn rate không giảm
- **SLO dashboard** là tool đầu tiên Ops Lead nên kiểm tra khi triage

### Sang Day 45 (DevSecOps):
- **Security incidents** từ Day 44 → DevSecOps (Day 45) sẽ dạy cách **prevent** chúng bằng SAST, DAST, SCA
- **Secret scanning** phòng tránh credential exposure incidents
- Incident postmortem action items thường thêm security scanning vào CI/CD pipeline

### Checkpoint Phase 6 — Observability & Reliability:

```
Day 38: Observability foundations (Metrics/Logs/Traces)
Day 39: Prometheus & PromQL (metric collection)
Day 40: Grafana (visualization + alerting)
Day 41: Logging architecture (Loki/ELK)
Day 42: OpenTelemetry + Distributed Tracing
Day 43: SLI/SLO/Error Budget + Alert Fatigue
Day 44: Incident Response & Postmortem ← YOU ARE HERE
                     │
                     ▼
         Complete feedback loop:
         Observe → Alert → Respond → Learn → Improve
```

---

## 11. Tài liệu tham khảo

### Must-Read
- **Google SRE Book — Chapter 14: Managing Incidents** — https://sre.google/sre-book/managing-incidents/
- **Google SRE Book — Chapter 15: Postmortem Culture** — https://sre.google/sre-book/postmortem-culture/
- **PagerDuty Incident Response Guide** — https://response.pagerduty.com/

### Nice-to-Have
- **Atlassian Incident Management** — https://www.atlassian.com/incident-management
- **etsy/morgue** — Open source postmortem tool từ Etsy
- **Datadog: Anatomy of an Incident** — Blog series thực tế

### Deep-Dive
- **Accelerate (book)** — Nicole Forsgren: Data về MTTR và postmortem culture
- **Increments — Increment Magazine: On-Call issue** — https://increment.com/on-call/
- **Learning from Incidents** podcast — https://www.learningfromincidents.io/
- **AWS Post-Event Summaries** — https://aws.amazon.com/premiumsupport/technology/pes/ (real AWS postmortems)

