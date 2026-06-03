# Day 1: DevOps, SRE, Platform Engineering & DORA Metrics

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt rõ ràng** DevOps, SRE và Platform Engineering — biết khi nào áp dụng model nào cho team của mình.
2. **Giải thích được 4 DORA metrics** (deployment frequency, lead time for changes, change failure rate, MTTR) và cách đo từng metric.
3. **Đánh giá được maturity level** của một engineering team dựa trên framework có cấu trúc.
4. **Viết được một mini ADR** (Architecture Decision Record) để lựa chọn operating model phù hợp cho team.
5. **Phân tích được trade-off** giữa tốc độ release và reliability trong các scenario thực tế.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng trong production?

Là một Senior Software Engineer, bạn đã quen với việc viết code, thiết kế system, tối ưu database. Nhưng trong production, **code chỉ là một phần nhỏ** của bức tranh. Phần lớn thời gian và effort nằm ở:

- Làm sao deploy an toàn mà không downtime?
- Khi có incident lúc 2 giờ sáng, ai xử lý và quy trình ra sao?
- Làm sao biết hệ thống đang healthy hay đang chết dần?
- Team scale lên 50, 100 người thì ai quản lý infrastructure?

### Hậu quả nếu làm sai

| Sai lầm | Hậu quả thực tế |
|---------|-----------------|
| Không có operating model rõ ràng | Dev đổ lỗi cho Ops, Ops chặn Dev — mỗi lần deploy mất 2 tuần |
| Không đo DORA metrics | Không biết team đang cải thiện hay tệ đi, decision dựa trên cảm tính |
| Chọn sai model cho team size | Startup 5 người build Internal Developer Platform → over-engineering. Enterprise 500 người không có platform → mỗi team tự chế CI/CD riêng |
| Bỏ qua reliability | Deploy nhanh nhưng rollback chậm, change failure rate 40% → mất trust của business |

### Liên hệ với kiến thức developer

- **System design**: Bạn đã biết thiết kế hệ thống — DevOps/SRE mở rộng góc nhìn sang vận hành, deploy, monitor hệ thống đó.
- **Microservices**: Bạn đã tách service — nhưng ai deploy, monitor, scale chúng?
- **Database optimization**: Bạn tối ưu query — nhưng backup strategy, failover, disaster recovery thì sao?

---

## 3. Kiến thức nền tảng

### 3.1. DevOps là gì?

**DevOps** là một **văn hóa và tập hợp practices** nhằm phá bỏ rào cản giữa Development và Operations, giúp tổ chức deliver software nhanh hơn, an toàn hơn và đáng tin cậy hơn.

**DevOps KHÔNG phải là:**
- Một job title (mặc dù thị trường gọi vậy)
- Một team riêng biệt
- Chỉ là CI/CD
- Chỉ là Docker + Kubernetes
- Một tool hay product

**Analogy cho developer**: DevOps giống như **Agile** — nó là mindset và practices, không phải tool. Giống như Agile không chỉ là Jira, DevOps không chỉ là Jenkins.

**Core principles:**
- **Culture**: Collaboration, shared responsibility, blameless postmortem
- **Automation**: CI/CD, Infrastructure as Code, automated testing
- **Measurement**: Đo lường mọi thứ — performance, reliability, velocity
- **Sharing**: Knowledge sharing, runbook, documentation

### 3.2. SRE là gì?

**Site Reliability Engineering (SRE)** là cách Google implement DevOps principles bằng software engineering approach.

> "SRE is what happens when you ask a software engineer to design an operations team." — Ben Treynor, VP Engineering tại Google

**Analogy**: Nếu DevOps là bản nhạc (principles), thì SRE là một cách biểu diễn cụ thể (implementation) với nhạc cụ và kỹ thuật rõ ràng.

**Core concepts:**
- **SLI/SLO/SLA**: Đo reliability bằng con số cụ thể
- **Error budget**: Cho phép một lượng lỗi nhất định để cân bằng velocity và reliability
- **Toil reduction**: Giảm công việc thủ công, lặp đi lặp lại bằng automation
- **Blameless postmortem**: Học từ incident, không đổ lỗi

**Điểm khác biệt quan trọng**: SRE engineer viết code 50% thời gian. Họ là software engineer làm operations, KHÔNG phải sysadmin biết coding.

### 3.3. Platform Engineering là gì?

**Platform Engineering** tập trung vào việc xây dựng **Internal Developer Platform (IDP)** — một tập hợp tools, workflows và self-service capabilities giúp developer tự phục vụ mà không cần phụ thuộc vào Ops team.

**Analogy**: Platform team giống như team xây **đường cao tốc** — developer là tài xế. Tài xế không cần biết cách xây đường, chỉ cần lái theo làn đường đã thiết kế. Platform team thiết kế guardrails, trạm thu phí tự động, biển báo.

**Core concepts:**
- **Self-service**: Developer tự deploy, tự tạo environment, tự xem logs
- **Golden paths**: Con đường chuẩn đã được thiết kế sẵn, đảm bảo best practices
- **Internal Developer Platform**: Abstraction layer giữa developer và infrastructure
- **Developer Experience (DX)**: Đo lường và cải thiện trải nghiệm developer

### 3.4. DORA Metrics

**DORA** (DevOps Research and Assessment) là nghiên cứu lớn nhất về software delivery performance. Sau 7 năm nghiên cứu hàng ngàn tổ chức, DORA xác định **4 key metrics**:

| Metric | Đo cái gì | Elite | High | Medium | Low |
|--------|-----------|-------|------|--------|-----|
| **Deployment Frequency** | Tần suất deploy lên production | On-demand (nhiều lần/ngày) | 1 lần/tuần - 1 lần/tháng | 1 lần/tháng - 1 lần/6 tháng | < 1 lần/6 tháng |
| **Lead Time for Changes** | Từ commit đến production | < 1 giờ | 1 ngày - 1 tuần | 1 tuần - 1 tháng | 1 tháng - 6 tháng |
| **Change Failure Rate** | % deployment gây incident | 0-15% | 16-30% | 31-45% | 46-60% |
| **MTTR** (Mean Time to Recovery) | Thời gian phục hồi sau incident | < 1 giờ | < 1 ngày | < 1 tuần | > 6 tháng |

**Insight quan trọng**: DORA chứng minh rằng **speed và stability KHÔNG phải trade-off** — top performers đạt cả hai. Team deploy nhiều hơn có change failure rate THẤP hơn, vì mỗi change nhỏ hơn → dễ debug hơn → rollback nhanh hơn.

---

## 4. Deep Dive

### 4.1. DevOps vs SRE vs Platform Engineering

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORGANIZATION                                 │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │   DevOps     │    │     SRE      │    │ Platform Engineering │  │
│  │  (Culture)   │    │(Implementation)│   │    (Product)         │  │
│  │              │    │              │    │                      │  │
│  │ • Mindset    │    │ • SLI/SLO    │    │ • IDP                │  │
│  │ • CI/CD      │    │ • Error      │    │ • Self-service       │  │
│  │ • Automation │    │   Budget     │    │ • Golden Paths       │  │
│  │ • Shared     │    │ • Toil       │    │ • Developer          │  │
│  │   Ownership  │    │   Reduction  │    │   Experience         │  │
│  │ • Measurement│    │ • On-call    │    │ • Abstraction        │  │
│  └──────────────┘    │ • Postmortem │    │   Layer              │  │
│                      └──────────────┘    └──────────────────────┘  │
│                                                                     │
│  Focus:             Focus:              Focus:                      │
│  Breaking silos     Reliability as      Developer                   │
│  between Dev & Ops  engineering problem productivity                │
│                                                                     │
│  Who applies:       Who applies:        Who applies:                │
│  Everyone           SRE team + Dev      Platform team               │
│  in organization    teams               serves Dev teams            │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2. Luồng tương tác trong tổ chức

```
┌────────────────────────────────────────────────────────────┐
│                    Developer Journey                        │
│                                                            │
│  Write Code → Push → CI Pipeline → Build → Test → Scan    │
│       │                                          │         │
│       │         ┌─────────────────────────────────┘         │
│       │         ▼                                          │
│       │    CD Pipeline → Stage Deploy → Smoke Test         │
│       │                                    │               │
│       │                                    ▼               │
│       │                            Prod Deploy             │
│       │                                    │               │
│       │         ┌──────────────────────────┘               │
│       │         ▼                                          │
│       │    Monitoring → Alerting → Incident?               │
│       │                               │                    │
│       │                    ┌──────────┴──────────┐         │
│       │                    ▼                     ▼         │
│       │               No: ✅                Yes: 🔥        │
│       │                                    │               │
│       │                         ┌──────────┘               │
│       │                         ▼                          │
│       │                  Incident Response                  │
│       │                         │                          │
│       │                         ▼                          │
│       │              Mitigation → Postmortem               │
│       │                              │                     │
│       │                              ▼                     │
│       └────────────── Action Items → Fix                   │
│                                                            │
│  DevOps: Owns the culture & practices across this flow     │
│  SRE: Owns reliability, SLO, on-call, postmortem          │
│  Platform: Owns the tooling & self-service of this flow    │
└────────────────────────────────────────────────────────────┘
```

### 4.3. Error Budget — Concept cốt lõi của SRE

```
SLO = 99.9% availability

Total minutes/month = 43,200 minutes (30 days)
Error budget = 0.1% × 43,200 = 43.2 minutes of allowed downtime

┌────────────────────────────────────────────────────┐
│ Error Budget Remaining: 43.2 minutes               │
│ ████████████████████████████████████████ 100%       │
│                                                    │
│ After Incident 1 (15 min):                         │
│ ████████████████████████████░░░░░░░░░░░  65%       │
│ Remaining: 28.2 minutes                            │
│                                                    │
│ After Incident 2 (20 min):                         │
│ ███████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  19%       │
│ Remaining: 8.2 minutes                             │
│                                                    │
│ ⚠️  Error budget low → FREEZE deployments          │
│ Focus on reliability improvements                  │
│ No new features until budget recovers              │
└────────────────────────────────────────────────────┘
```

**Cách hoạt động**:
- Error budget > 50%: Deploy thoải mái, thử feature mới, experiment
- Error budget 20-50%: Cẩn thận hơn, rollback plan phải rõ ràng
- Error budget < 20%: Freeze feature deployment, chỉ fix reliability
- Error budget = 0%: Mọi effort dồn vào reliability, postmortem bắt buộc

---

## 5. Trade-offs & Best Practices ⭐

### 5.1. Khi nào dùng model nào?

| Tiêu chí | DevOps Model | SRE Model | Platform Engineering |
|----------|-------------|-----------|---------------------|
| **Team size** | 5-30 engineers | 30-200 engineers | 100+ engineers |
| **Maturity** | Đang bắt đầu tự động hóa | Đã có CI/CD, cần đo reliability | Đã có DevOps/SRE, cần scale DX |
| **Pain point chính** | Dev và Ops không nói chuyện | Reliability không đo được | Mỗi team tự build tooling riêng |
| **Investment** | Thấp — culture change + CI/CD | Trung bình — hiring SRE + tooling | Cao — build Internal Platform |
| **Risk** | Cultural resistance | SRE burnout nếu on-call quá nhiều | Over-engineering platform |

### 5.2. Theo scenario

**Startup (5-15 engineers):**
- ✅ Dùng DevOps culture — everyone writes code AND deploys
- ✅ Simple CI/CD pipeline
- ✅ Đo DORA metrics cơ bản
- ❌ KHÔNG cần SRE team riêng — quá nhỏ
- ❌ KHÔNG cần Platform team — quá sớm, sẽ over-engineer
- **Anti-pattern**: Thuê "DevOps engineer" để làm mọi thứ Ops → tạo bottleneck mới

**Mid-size company (30-100 engineers):**
- ✅ DevOps culture vẫn cần
- ✅ Bắt đầu có 1-2 SRE embedded trong critical team
- ✅ Shared CI/CD platform bắt đầu cần thiết
- ✅ On-call rotation cho developer — "you build it, you run it"
- ❌ Chưa cần full Platform team trừ khi pain rõ ràng
- **Anti-pattern**: Central Ops team vẫn deploy cho tất cả → bottleneck

**Enterprise (200+ engineers):**
- ✅ Platform team xây Internal Developer Platform
- ✅ SRE team cho critical services (payment, auth, data pipeline)
- ✅ Đo DORA metrics theo từng team/stream
- ✅ Golden paths cho common use cases
- ❌ KHÔNG ép tất cả team dùng cùng tool — cho phép escape hatch
- **Anti-pattern**: Platform team build mà không có developer feedback → ivory tower platform, không ai dùng

**High-traffic system (10K+ RPS):**
- ✅ SRE bắt buộc cho core services
- ✅ Error budget strictly enforced
- ✅ Canary deployment / progressive delivery
- ✅ Chaos engineering
- ❌ KHÔNG deploy thẳng production không qua staging
- **Anti-pattern**: Tất cả service đều SLO 99.99% → không đủ error budget để innovate

### 5.3. Anti-patterns phổ biến

1. **"DevOps team"** — Tạo một team riêng gọi là DevOps nhưng bản chất vẫn là Ops team cũ → vẫn tạo silo
2. **SRE-as-ops** — SRE chỉ on-call và firefight, không viết code automation → SRE burnout
3. **Platform without users** — Build platform phức tạp mà không hỏi developer cần gì → không ai dùng
4. **Metric gaming** — Đo DORA metrics nhưng optimize cho metric thay vì outcome (deploy nhiều nhưng mỗi deployment chỉ thay 1 dòng comment)
5. **Reliability theater** — Nói SLO 99.99% nhưng không đo, không có error budget, không postmortem

---

## 6. Performance & Scalability ⭐

### 6.1. Performance của operating model

Đây không phải system performance mà là **organizational performance** — nhưng impact trực tiếp lên system.

| Metric | Impact nếu model tệ | Impact nếu model tốt |
|--------|---------------------|---------------------|
| Deploy time | Mỗi deployment mất 2 tuần (approval chain dài) | Deploy on-demand, < 1 giờ từ merge |
| Incident response | MTTR > 1 ngày (không ai biết ai responsible) | MTTR < 1 giờ (clear ownership, runbook) |
| Onboarding | Developer mới mất 2 tháng để deploy lần đầu | Developer mới deploy ngày đầu tiên |
| Toil | 60% thời gian engineer làm manual ops | < 20% toil, automation cho repetitive tasks |

### 6.2. Bottleneck thường gặp theo model

**DevOps model bottleneck:**
- Không ai chuyên sâu reliability → khi hệ thống phức tạp, ai cũng biết một ít nhưng không ai biết sâu
- Giải pháp: Embedded SRE hoặc reliability champion trong team

**SRE model bottleneck:**
- SRE team trở thành bottleneck nếu mọi team đều cần SRE review
- Giải pháp: SRE chỉ cho critical services, team khác tự on-call với support từ SRE

**Platform Engineering bottleneck:**
- Platform team build chậm hơn nhu cầu → developer bypass platform
- Giải pháp: Platform as product — có product roadmap, user feedback loop, measure adoption

### 6.3. Scaling strategy

```
Team 10 → 30:
  DevOps culture + shared CI/CD + basic monitoring
  
Team 30 → 100:
  + Dedicated SRE (1-2 người)
  + SLI/SLO cho critical services
  + Basic Internal Developer Platform
  + On-call rotation

Team 100 → 500:
  + Platform team (5-10 người)
  + Golden paths
  + Self-service deployment
  + Multiple SRE embedded in product teams
  + Error budget policy

Team 500+:
  + Platform as product (dedicated PM)
  + Multiple platform capabilities (compute, data, ML)
  + Central SRE + embedded SREs
  + DORA metrics per team/stream
  + Internal marketplace for tools
```

---

## 7. Security & Reliability Considerations

### Security

- **Access control**: Ai có quyền deploy lên production? Principle of least privilege áp dụng cho CI/CD pipeline, không chỉ cho code.
- **secret management**: Pipeline credentials, API keys, database passwords phải được quản lý — KHÔNG hardcode trong CI/CD config.
- **Audit trail**: Mọi deployment phải có trail — ai deploy, lúc nào, commit nào, approve bởi ai.
- **Supply chain**: Image scanning, dependency scanning phải nằm trong pipeline.

### Reliability

- **Rollback plan**: Trước KHI deploy, phải biết cách rollback. Không có rollback plan = không được deploy.
- **Blast radius**: Deploy theo batch, không deploy tất cả region/cluster cùng lúc.
- **Health check**: Deployment pipeline phải verify health sau deploy, tự rollback nếu health check fail.
- **Communication**: Khi incident xảy ra, phải có kênh communication rõ ràng (không phải Slack random).

---

## 8. Hands-on Example

### 8.1. Tạo Engineering Maturity Assessment

Tạo workspace local-first để không ảnh hưởng repository chính:

```bash
mkdir -p /tmp/devops-day01
cd /tmp/devops-day01
```

Tạo file `maturity-assessment.md`:

```markdown
# Engineering Team Maturity Assessment

## Thông tin team
- Team name: _______________
- Team size: _______________
- Main services: _______________
- Assessment date: _______________

## 1. Source Control & Branching
- [ ] Tất cả code trong version control
- [ ] Có branching strategy rõ ràng
- [ ] Code review bắt buộc trước merge
- [ ] Commit message có convention
Rating: [ ] Beginner  [ ] Intermediate  [ ] Advanced  [ ] Elite

## 2. CI/CD
- [ ] Có automated build
- [ ] Có automated test chạy trên mỗi PR
- [ ] Có automated deployment đến staging
- [ ] Có automated deployment đến production
- [ ] Có rollback mechanism
Rating: [ ] Beginner  [ ] Intermediate  [ ] Advanced  [ ] Elite

## 3. Testing
- [ ] Unit tests > 70% coverage
- [ ] Integration tests cho critical paths
- [ ] E2E tests cho golden flows
- [ ] Performance/load testing
- [ ] Security testing (SAST/DAST)
Rating: [ ] Beginner  [ ] Intermediate  [ ] Advanced  [ ] Elite

## 4. Monitoring & Observability
- [ ] Application metrics (RED/USE)
- [ ] Infrastructure metrics
- [ ] Centralized logging
- [ ] Distributed tracing
- [ ] Alerting với runbook
- [ ] Dashboards cho key services
Rating: [ ] Beginner  [ ] Intermediate  [ ] Advanced  [ ] Elite

## 5. Incident Management
- [ ] On-call rotation
- [ ] Incident response process documented
- [ ] Severity levels defined
- [ ] Postmortem process
- [ ] Action items tracked
Rating: [ ] Beginner  [ ] Intermediate  [ ] Advanced  [ ] Elite

## 6. Reliability
- [ ] SLI/SLO defined cho critical services
- [ ] Error budget tracked
- [ ] Backup & restore tested
- [ ] Disaster recovery plan
- [ ] Chaos engineering experiments
Rating: [ ] Beginner  [ ] Intermediate  [ ] Advanced  [ ] Elite

## 7. Infrastructure
- [ ] Infrastructure as Code (Terraform/Pulumi)
- [ ] Environment parity (dev ≈ staging ≈ prod)
- [ ] Secret management (Vault/SOPS)
- [ ] Container/image security scanning
- [ ] Resource right-sizing
Rating: [ ] Beginner  [ ] Intermediate  [ ] Advanced  [ ] Elite

## 8. DORA Metrics (measure hiện tại)
- Deployment frequency: _______________
- Lead time for changes: _______________
- Change failure rate: _______________
- MTTR: _______________
DORA Level: [ ] Low  [ ] Medium  [ ] High  [ ] Elite

## Overall Assessment
- Strengths: _______________
- Weaknesses: _______________
- Top 3 improvement areas:
  1. _______________
  2. _______________
  3. _______________
```

**Chạy/verify nhanh**:

```bash
test -s maturity-assessment.md && grep -n "DORA Metrics" maturity-assessment.md
```

**Expected output ví dụ**:

```text
64:## 8. DORA Metrics (measure hiện tại)
```

### 8.2. Viết Mini ADR

Tạo file `adr-001-operating-model.md`:

```markdown
# ADR-001: Lựa chọn Operating Model cho Engineering Team

## Status
Proposed

## Context
Team hiện tại có [X] engineers, vận hành [Y] services trên [Z] infrastructure.
Hiện tại gặp các vấn đề:
- [Liệt kê pain points: deploy chậm, incident response không rõ ràng, etc.]

## Decision Drivers
- Team size: ___
- Current maturity: ___ (dùng kết quả assessment ở trên)
- Budget constraint: ___
- Growth plan: ___
- Critical services: ___

## Options Considered

### Option A: DevOps Culture (No dedicated team)
- Mọi developer tự deploy, tự on-call
- Shared CI/CD pipeline
- Pros:
  - Không cần hire thêm
  - Developer ownership cao
  - Fast feedback loop
- Cons:
  - Reliability depth thiếu khi hệ thống phức tạp
  - Developer context-switch nhiều
  - Không ai chuyên sâu infrastructure

### Option B: DevOps + Embedded SRE
- DevOps culture nền
- 1-2 SRE embedded trong team for critical services
- Pros:
  - Có chuyên gia reliability
  - Developer vẫn có ownership
  - Cost hiệu quả
- Cons:
  - SRE bottleneck nếu quá ít
  - SRE cô đơn nếu chỉ có 1 người

### Option C: Platform Engineering
- Build Internal Developer Platform
- Platform team phục vụ developer teams
- Pros:
  - Self-service, developer productivity cao
  - Consistency across teams
  - Scalable khi team lớn
- Cons:
  - Investment cao (team + time)
  - Risk over-engineering
  - Cần product mindset cho platform

## Decision
[Team chọn Option ___]

## Rationale
[Giải thích vì sao chọn option này dựa trên context]

## Consequences
### Positive
- [...]

### Negative
- [...]

### Risks
- [...]

## Review Date
[Đặt review sau 6 tháng để đánh giá lại]
```

**Chạy/verify nhanh**:

```bash
test -s adr-001-operating-model.md
grep -E "^(## Context|## Decision|## Consequences)" adr-001-operating-model.md
```

**Expected output ví dụ**:

```text
## Context
## Decision
## Consequences
```

### 8.3. Đo DORA Metrics thực tế

Chạy các command sau trên repository hiện tại để ước lượng DORA metrics:

```bash
# 1. Deployment Frequency
# Đếm số lần deploy/release trong 30 ngày gần nhất
git log --oneline --after="30 days ago" --grep="deploy\|release\|merge" | wc -l

# Hoặc đếm tags
git tag --sort=-creatordate | head -20

# 2. Lead Time for Changes
# Thời gian trung bình từ first commit đến merge vào main
git log --merges --oneline --after="30 days ago" | head -10

# Với mỗi merge commit, tìm first commit trong branch
git log --format="%H %ai" --merges --after="30 days ago" | head -5

# 3. Change Failure Rate
# Đếm hotfix/revert commits vs total deployments
git log --oneline --after="30 days ago" --grep="hotfix\|revert\|rollback" | wc -l
git log --oneline --after="30 days ago" | wc -l

# 4. MTTR
# Cần incident tracking system — nhưng có thể ước lượng
# từ thời gian giữa "incident" commit và "fix" commit
git log --oneline --after="90 days ago" --grep="fix\|hotfix\|incident" | head -10
```

**Expected output ví dụ:**

```
# Deployment Frequency
$ git log --oneline --after="30 days ago" --grep="deploy\|release\|merge" | wc -l
12
→ ~3 deployments/tuần → High level

# Change Failure Rate
$ git log --oneline --after="30 days ago" --grep="hotfix\|revert\|rollback" | wc -l
2
$ git log --oneline --after="30 days ago" | wc -l
45
→ 2/45 = 4.4% → Elite level
```

**Verify**: So sánh kết quả với bảng DORA metrics ở Section 3.4 để xác định level hiện tại.

### Cleanup

```bash
cd /tmp
rm -rf /tmp/devops-day01
```

---

## 9. Common Pitfalls & Debugging

### 9.1. Pitfall: "Chúng tôi đã DevOps rồi vì có CI/CD"

**Dấu hiệu**: Có Jenkins/GitHub Actions nhưng:
- Developer không biết pipeline hoạt động thế nào
- Chỉ 1-2 người biết fix pipeline khi broken
- Deploy lên production vẫn cần approval manual từ "DevOps team"

**Giải pháp**: DevOps là culture, không phải tool. Đo bằng: "Developer có tự tin deploy lên production không? Developer có on-call không?"

### 9.2. Pitfall: "SLO cho mọi service là 99.99%"

**Dấu hiệu**: Tất cả service đều có SLO 99.99%, nhưng:
- Không ai đo SLI thực tế
- Không có error budget policy
- Khi incident xảy ra, không ai biết SLO bị vi phạm chưa

**Giải pháp**: SLO phải realistic. Internal service có thể 99.9%, user-facing critical 99.95%, payment 99.99%. Mỗi level tăng thêm 10x effort và cost.

### 9.3. Pitfall: "Build platform trước khi có user"

**Dấu hiệu**: Platform team dành 6 tháng build internal tool mà chưa hỏi developer cần gì.

**Giải pháp**: Start simple — hỏi developer: "Bước nào trong workflow tốn thời gian nhất?" và giải quyết bước đó trước.

### 9.4. Case Study: Spotify Model thất bại

**Context**: Nhiều company cố copy Spotify model (Squads, Tribes, Chapters, Guilds) mà không hiểu context.

**Symptom**: Team được re-org theo Spotify model nhưng vẫn deploy chậm, incident response không cải thiện.

**Root cause**: Spotify model là kết quả của văn hóa Spotify, không phải nguyên nhân. Copy structure mà không copy culture → failure.

**Lesson**: Không có one-size-fits-all operating model. Hiểu principles → áp dụng cho context riêng.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước
Day 1 là bài đầu tiên — đặt foundation cho toàn bộ chương trình. Mọi kiến thức từ đây trở đi đều xây trên nền DevOps/SRE/Platform Engineering mindset.

### Bài sau
**Day 2: Linux Advanced — Process, Signal, File Descriptor, systemd** sẽ đi sâu vào nền tảng hệ điều hành — kiến thức bắt buộc trước khi học Docker và Kubernetes. Day 2 trả lời câu hỏi: "Trước khi chạy app trong container, bạn cần hiểu app chạy trên Linux thế nào."

**Kết nối**: 
- Operating model (Day 1) xác định **ai và quy trình**.
- Linux fundamentals (Day 2-4) xác định **nền tảng kỹ thuật**.
- Kết hợp cả hai → bạn hiểu **vì sao** cần graceful shutdown (SRE/reliability) và **cách** implement nó (Linux signals).

---

## 11. Tài liệu tham khảo

### Must-read
- **"Accelerate" by Nicole Forsgren, Jez Humble, Gene Kim** — Nghiên cứu DORA gốc, data-driven.
- **Google SRE Book** (free online): https://sre.google/sre-book/table-of-contents/ — SRE bible.
- **DORA State of DevOps Report** (latest): https://dora.dev — Report hàng năm với data mới nhất.

### Nice-to-have
- **"The Phoenix Project" by Gene Kim** — Tiểu thuyết về DevOps transformation, dễ đọc.
- **"Team Topologies" by Matthew Skelton & Manuel Pais** — Framework tổ chức team, bao gồm Platform team.
- **Platform Engineering on Kubernetes** by Mauricio Salatino — Practical guide cho Platform Engineering.

### Deep-dive  
- **Google SRE Workbook**: https://sre.google/workbook/table-of-contents/ — Hands-on companion cho SRE Book.
- **Spotify Engineering Culture** (video): Tìm trên YouTube — 2 parts, mỗi part ~15 phút.
- **Internal Developer Platform**: https://internaldeveloperplatform.org — Resource hub cho Platform Engineering.

