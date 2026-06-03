# Day 43: SLI/SLO, Error Budget & Alert Fatigue

> **Phase 6 — Observability & Reliability** | Thời lượng: ~2 giờ  
> Prerequisite: Day 39 (Prometheus/PromQL), Day 40 (Grafana Alerting), Day 42 (OpenTelemetry)

---

## 1. Mục tiêu bài học

Sau bài này, học viên có thể:

1. **Phân biệt** SLA, SLO, SLI và giải thích mối quan hệ giữa chúng bằng số liệu cụ thể
2. **Định nghĩa** SLI/SLO phù hợp cho một API service thực tế (availability, latency, correctness)
3. **Tính toán** error budget và hiểu khi nào cần freeze deployment
4. **Thiết kế** burn rate alert dùng multi-window approach để tránh alert fatigue
5. **Nhận biết** và giải quyết các anti-pattern phổ biến: SLO theater, alert storm, toil tích lũy

---

## 2. Bối cảnh & Động lực

### 2.1 Vấn đề thực tế — "Alert năm nào cũng cháy"

Hãy tưởng tượng bạn join một team vận hành API gateway cho 10 triệu request/ngày. Trong on-call runbook có 247 alert rules. Vào 3 giờ sáng thứ Sáu, 12 alert bắn đồng thời. Bạn nhìn vào dashboard, thấy error rate từ 0.1% lên 0.3%, rồi tự hỏi: **"Cái này có nghiêm trọng không? Có cần wake up toàn team không?"**

Đây là hậu quả của việc thiếu SLO:

- Không có ngưỡng nào xác định "bad" vs "good"
- On-call engineer không biết cái gì thực sự quan trọng với người dùng
- Alert fatigue khiến engineer bỏ qua cảnh báo thật
- Mọi incident đều escalate vì không có framework ưu tiên

### 2.2 SLO là cầu nối giữa business và engineering

```
Business nói:          "90% user phải happy"
SLO diễn dịch thành:   "99.9% request < 200ms, 99.95% request thành công"
SLI đo lường:          ratio of good requests / total requests (số thực từ Prometheus)
Error budget cho phép: 0.05% failure = ~21.6 phút downtime/tháng
```

SLO là **thỏa thuận nội bộ** giữa product team và engineering team — không ai expect 100% uptime (kể cả Google.com). SLO formalize câu hỏi: **"Chúng ta sẵn sàng thất bại bao nhiêu để ship nhanh hơn?"**

### 2.3 Không có SLO: hậu quả thực tế

| Tình huống | Không có SLO | Có SLO |
|---|---|---|
| Error rate tăng 0.1% → 0.5% | Alert ngay, wake up on-call | Kiểm tra xem có burn qua budget không |
| Team muốn deploy feature mới | Không có tiêu chí rõ ràng để block | Error budget < 10% → freeze deploy |
| Incident post-mortem | "Lỗi do không đủ monitoring" | "Lỗi burn hết Q3 budget, cần cải thiện reliability" |
| PM hỏi "service có healthy không?" | "Uptime 99.8%... chắc vậy" | "SLO 99.9%, còn 18 phút budget tháng này" |

---

## 3. Kiến thức nền tảng

### 3.1 Tam giác SLA — SLO — SLI

```
┌─────────────────────────────────────────────────────────┐
│                    SLA (Contract)                        │
│   "99.5% availability/month, else 10% credit refund"    │
│                         ↑                               │
│                  (external, legal)                       │
├─────────────────────────────────────────────────────────┤
│                    SLO (Internal Target)                  │
│      "99.9% availability — stricter buffer zone"         │
│                         ↑                               │
│             (internal agreement, no penalty)             │
├─────────────────────────────────────────────────────────┤
│                    SLI (Measurement)                     │
│   "ratio of HTTP 2xx responses / total HTTP responses"   │
│                         ↑                               │
│          (actual metric from Prometheus/logs)            │
└─────────────────────────────────────────────────────────┘
```

**SLA (Service Level Agreement)**:
- Hợp đồng pháp lý với khách hàng
- Thường có penalty clause (refund, credit)
- Ví dụ AWS S3: 99.9% availability, vi phạm → 10-25% credit
- Thường **lỏng hơn** SLO để có buffer

**SLO (Service Level Objective)**:
- Mục tiêu nội bộ, không có penalty với khách hàng
- Thường **chặt hơn SLA** 10-20% để phát hiện sớm
- Ví dụ: SLA là 99.5% → đặt SLO 99.9% để có margin
- Là cơ sở ra quyết định: deploy hay không, scale hay không

**SLI (Service Level Indicator)**:
- Số đo thực tế theo thời gian thực
- Phải đo được (quantifiable) và phù hợp với trải nghiệm user
- Ví dụ: `sum(rate(http_requests_total{code!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`

### 3.2 Các loại SLI phổ biến

| Loại SLI | Định nghĩa | Metric ví dụ |
|---|---|---|
| **Availability** | Tỷ lệ request thành công | `2xx / total requests` |
| **Latency** | % request hoàn thành trong threshold | `P99 < 500ms` |
| **Correctness** | Kết quả trả về đúng không | `valid responses / total` |
| **Freshness** | Dữ liệu có mới không | `age of last successful update` |
| **Throughput** | Hệ thống xử lý đủ volume chưa | `requests/second > threshold` |
| **Durability** | Dữ liệu không bị mất | `(stored - lost) / stored` |

### 3.3 Error Budget — Ngân sách lỗi

Error budget là **lượng failure được phép trong một khoảng thời gian** trước khi SLO bị vi phạm.

**Công thức:**
```
Error Budget = 1 - SLO target
Error Budget (time) = (1 - SLO%) × rolling_window_duration

Ví dụ:
  SLO = 99.9% availability (30-day rolling window)
  Error budget = 0.1%
  Error budget (time) = 0.001 × 30 × 24 × 60 = 43.2 phút/tháng
```

**Bảng error budget theo SLO:**

| SLO Target | Downtime/tháng | Downtime/tuần | Downtime/ngày |
|---|---|---|---|
| 90% | 43.8 giờ | 10.1 giờ | 2.4 giờ |
| 99% | 7.3 giờ | 1.68 giờ | 14.4 phút |
| 99.5% | 3.65 giờ | 50.4 phút | 7.2 phút |
| 99.9% | 43.8 phút | 10.1 phút | 1.44 phút |
| 99.95% | 21.9 phút | 5 phút | 43.2 giây |
| 99.99% | 4.38 phút | 1.01 phút | 8.64 giây |

> **Lưu ý thực tế**: 99.99% (four nines) cực kỳ khó đạt — mỗi deployment routine cũng có thể consume vài giây downtime. Hầu hết B2B SaaS chỉ cần 99.5-99.9%.

### 3.4 Error Budget Policy

Error budget policy là **quy tắc quyết định dựa trên error budget còn lại:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Error Budget Policy                       │
├──────────────────┬──────────────────────────────────────────┤
│ Budget còn > 50% │ Business as usual, deploy freely         │
├──────────────────┼──────────────────────────────────────────┤
│ Budget còn < 25% │ Tăng review, không deploy breaking change│
├──────────────────┼──────────────────────────────────────────┤
│ Budget còn < 10% │ Feature freeze, chỉ ship reliability fix │
├──────────────────┼──────────────────────────────────────────┤
│ Budget = 0%      │ Incident mode, toàn team focus reliability│
└──────────────────┴──────────────────────────────────────────┘
```

---

## 4. Deep Dive

### 4.1 Chọn SLI đúng — The Art of SLI Selection

#### Nguyên tắc: SLI phải phản ánh trải nghiệm người dùng

**Sai**: Đo CPU utilization làm SLI
- CPU cao không có nghĩa là user bị ảnh hưởng
- 100% CPU nhưng request vẫn < 100ms → fine

**Đúng**: Đo request success rate và latency
- Trực tiếp phản ánh user experience
- Khi SLI xấu = user đang gặp vấn đề

#### Framework chọn SLI (Google SRE Book)

```
1. Xác định "happy user" là gì?
   → User hoàn thành checkout thành công trong < 3s

2. Translate sang measurable metric:
   → % checkout requests returning 2xx AND completing < 3s

3. Xác định điểm đo (measurement point):
   → Tại load balancer (client-side perspective)
   → Không phải internal service metrics (vì có thể bỏ qua network issues)

4. Đặt window time:
   → 30-day rolling window (phổ biến nhất)
   → 28-day cho billing cycles
```

#### Request-based SLI vs Time-based SLI

**Request-based** (preferred):
```
SLI = good_requests / total_requests

Ưu điểm:
- Phản ánh actual user impact (1000 bad requests = 1000 users bị ảnh hưởng)
- Không bị ảnh hưởng bởi traffic volume thấp
```

**Time-based** (legacy):
```
SLI = uptime_minutes / total_minutes

Nhược điểm:
- 5 phút downtime lúc 2AM ≠ 5 phút downtime lúc 12PM (traffic khác nhau)
- Không phản ánh actual user impact
```

### 4.2 Burn Rate — Khái niệm cốt lõi

**Burn rate** là tốc độ tiêu thụ error budget so với tốc độ bình thường.

```
Burn Rate = current_error_rate / (1 - SLO_target)

Ví dụ:
  SLO = 99.9% → error budget = 0.1%
  Nếu current error rate = 1%:
  Burn Rate = 1% / 0.1% = 10x

  Nghĩa là: đang tiêu budget nhanh gấp 10 lần bình thường
  → 43.8 phút budget / 10 = còn 4.38 phút budget nếu tiếp tục
```

#### Burn Rate Visualization

```
Budget Consumption Timeline (SLO 99.9%, 30-day window = 43.2 min budget):

Burn Rate 1x (normal):
▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ Budget hết sau 30 ngày (OK)

Burn Rate 6x (elevated):
▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░ Budget hết sau 5 ngày (WARNING)

Burn Rate 14.4x (critical):
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ Budget hết sau ~2 ngày (PAGE)

Burn Rate 36x (catastrophic):
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ Budget hết sau 1 giờ (CRITICAL)
```

### 4.3 Multi-Window, Multi-Burn-Rate Alerting

Đây là phương pháp alerting hiện đại từ Google SRE Workbook, tránh cả **false positive** lẫn **false negative**.

#### Vấn đề với single-window alert:

```
Short window (5m): Too noisy
- Bắt được spike nhanh nhưng nhiều false positive
- 1 phút error rate 5% → alert, nhưng tự hồi phục ngay

Long window (1h): Too slow
- Ít noise nhưng phát hiện chậm
- Hết 30 phút budget mới alert → đã quá muộn
```

#### Giải pháp: Multi-window alerting

```
┌─────────────────────────────────────────────────────────────────┐
│              Google Multi-Window Alert Model                     │
│                    (SLO = 99.9%)                                 │
├────────────────┬───────────┬────────────┬────────────────────── ┤
│ Severity       │ Burn Rate │ Short Win  │ Long Win   │ Action   │
├────────────────┼───────────┼────────────┼────────────┼──────────┤
│ PAGE (Urgent)  │ 14.4x     │ 5 phút     │ 1 giờ      │ Gọi điện │
│ TICKET (High)  │ 6x        │ 30 phút    │ 6 giờ      │ Slack    │
│ WARNING (Med)  │ 3x        │ 2 giờ      │ 24 giờ     │ Dashboard│
│ INFO (Low)     │ 1x        │ 6 giờ      │ 3 ngày     │ Ticket   │
└────────────────┴───────────┴────────────┴────────────┴──────────┘

Quy tắc: BOTH windows phải breach để alert bắn
→ Giảm false positive (spike ngắn không trigger)
→ Phát hiện nhanh (không cần đợi long window đủ dài)
```

**Tại sao 14.4x cho PAGE?**
```
14.4x burn rate × 2-day budget consumption window = budget hết trong 2 ngày
Nhưng với short window 1h: budget × (14.4 × 1h / 720h) = ~2% budget burned
→ Đủ nhanh để phát hiện, đủ nghiêm trọng để wake up on-call
```

### 4.4 Alert Fatigue — Kẻ thù thầm lặng của SRE

#### Alert fatigue là gì?

Alert fatigue xảy ra khi engineer nhận **quá nhiều cảnh báo không quan trọng** đến mức bắt đầu **ignore cả cảnh báo thật**.

**Dấu hiệu alert fatigue:**
- On-call thường xuyên silence alert mà không investigate
- "Alert này hay bắn lắm, bình thường thôi" trở thành mindset
- MTTR tăng vì alert bị delay hoặc ignore
- Engineer burnout, high turnover trong on-call rotation

#### Nguyên nhân phổ biến:

```
1. Threshold quá thấp:
   alert if cpu > 70%  ← CPU 75% là bình thường khi load cao

2. Alert không actionable:
   "Disk usage tăng" ← Tăng bao nhiêu? Còn bao lâu nữa thì đầy?

3. Alert trùng lặp:
   Same incident → 5 alert từ 5 service khác nhau cascade

4. Không có severity phân cấp:
   Tất cả alert đều gửi vào cùng 1 channel với cùng priority

5. Alert không gắn với SLO:
   Alert on symptoms (CPU, memory) thay vì outcomes (user impact)
```

#### Giải pháp giảm alert fatigue:

```
Before (Bad):           After (Good):
247 alert rules    →    12 SLO-based alert rules
Alert on every     →    Alert on burn rate thresholds
 symptom
All alerts page    →    Tiered: PAGE / TICKET / INFO
No runbook         →    Mỗi alert có runbook link và expected action
Cannot silence     →    Structured snooze với reason tracking
```

### 4.5 Toil — Định nghĩa và cách giảm

**Toil** (theo Google SRE) là công việc vận hành có các đặc điểm:

```
✗ Manual (không thể tự chạy)
✗ Repetitive (lặp đi lặp lại)
✗ Automatable (có thể được tự động hóa)
✗ Tactical (reactive, không phải strategic)
✗ No enduring value (làm xong không để lại gì tốt hơn)
✗ Grows with service (scale tuyến tính với traffic)
```

**Ví dụ toil điển hình trong DevOps:**
- Restart service thủ công mỗi tuần vì memory leak
- Approve deployment bằng tay theo checklist
- Copy-paste giá trị config giữa môi trường
- Manually rotate secrets mỗi 90 ngày

**Đo Toil:**
```
% Time on Toil = toil_hours / total_work_hours × 100

Google target: < 50% thời gian là toil
Nếu > 50%: Team không có thời gian improve hệ thống
```

**Reduce Toil — Chiến lược:**

```
Level 1: Automate low-hanging fruit
  → Runbook → Script → Automated runbook

Level 2: Eliminate root cause
  → Memory leak restart → Fix memory leak
  → Manual secret rotation → Auto-rotation với Vault

Level 3: Design for operability
  → Self-healing (health checks with auto-restart)
  → Chaos engineering để tìm toil trước khi nó xảy ra
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 SLO quá chặt vs quá lỏng

```
SLO = 99.99% (quá chặt):
PRO: "Chúng ta rất reliable"
CON: - Error budget chỉ 4.38 phút/tháng
     - Mỗi deployment là rủi ro vi phạm SLO
     - Team không dám deploy → velocity chậm
     - False sense of security (thực tế không đo được 4 nines)

SLO = 90% (quá lỏng):
PRO: "Thoải mái deploy"
CON: - User thấy 10% request fail → abandon product
     - Error budget 43.8h/tháng bị lạm dụng
     - SLO mất ý nghĩa, trở thành SLO theater

NGUYÊN TẮC: SLO phải tight enough để có consequences,
            nhưng achievable với current reliability level.
```

### 5.2 Bao nhiêu SLO cho một service?

```
Startup (1-5 services):
→ 1-2 SLO/service: Availability + Latency P99
→ Keep it simple, iteration là quan trọng hơn

Mid-size (10-50 services):
→ 2-4 SLO/service theo user journey
→ Separate SLO cho read vs write operations
→ Separate SLO cho different customer tiers

Enterprise (100+ services):
→ SLO per critical user journey (không phải per service)
→ Composite SLO cho end-to-end flows
→ Customer-tier SLO (Premium vs Standard)
```

### 5.3 Anti-Patterns cần tránh

**1. SLO Theater** — Đặt SLO nhưng không ai dùng để ra quyết định:
```
Dấu hiệu: SLO được define nhưng deployment không bao giờ bị block
Fix: Error budget policy phải có teeth — meeting với leadership khi budget < 10%
```

**2. Alert on Everything** — Mọi metric đều có alert:
```
Dấu hiệu: > 100 alert rules cho một service
Fix: Mỗi alert phải answer: "Nếu alert này bắn lúc 3AM, on-call làm gì?"
```

**3. SLI không phản ánh user** — Đo internal metrics thay vì user outcomes:
```
Dấu hiệu: Hệ thống "100% available" nhưng user vẫn complain
Fix: Đo tại điểm gần user nhất (load balancer, CDN edge)
```

**4. Ignore Error Budget Consumption** — Không check budget thường xuyên:
```
Dấu hiệ�: Budget hết lúc cuối tháng không ai biết
Fix: Weekly error budget review trong team meeting
```

### 5.4 Best Practices theo scenario

| Scenario | Recommendation |
|---|---|
| **Startup < 20 engineers** | Start với 99.5% availability + latency P95. Review monthly. |
| **Greenfield service** | Bắt đầu với SLO lỏng, tighten sau khi có data real traffic. |
| **Legacy service** | Đo SLI của 30 ngày qua → đặt SLO = P95 performance của period đó |
| **B2B SaaS** | Align SLO với SLA tier của customer. Premium = 99.9%, Standard = 99.5% |
| **Internal tooling** | SLO không cần quá chặt — 99% availability thường đủ |

---

## 6. Performance & Scalability ⭐

### 6.1 Chi phí đo SLI

SLI measurement không miễn phí. Cardinality cao trong Prometheus = memory explosion.

**Bad (high cardinality):**
```yaml
# Tránh: user_id label trong SLI metric
http_requests_total{user_id="12345", endpoint="/api/checkout"}
# → N users × M endpoints = triệu time series
```

**Good (controlled cardinality):**
```yaml
# Tốt: aggregate ở service level
http_requests_total{service="checkout", status_class="2xx"}
# → 1 time series per service per status class
```

### 6.2 Sliding Window vs Burn Rate Performance

```
Vấn đề: PromQL query 30-day window rất nặng
rate(http_requests_total[30d])  ← Query 43,200 data points

Giải pháp: Recording rules
# record rule chạy mỗi 1m, precompute tại server
- record: job:http_requests:rate5m
  expr: rate(http_requests_total[5m])

# Alert dùng recording rule
- alert: SLOBurnRateHigh
  expr: job:http_requests:error_rate5m / 0.001 > 14.4
```

### 6.3 Scale SLO Management

```
1-10 services:   Manage manually, 1 Prometheus config file
10-50 services:  SLO-as-code (pyrra, sloth library)
50+ services:    Centralized SLO platform (Google SLO Cloud, Nobl9, Datadog SLO)

Công cụ open-source:
- Sloth: https://sloth.dev — Generate SLO Prometheus rules từ YAML
- Pyrra: https://pyrra.dev — SLO management UI + auto recording rules
```

---

## 7. Security & Reliability Considerations

### 7.1 SLO là Change Management Gate

Error budget là **lý do kỹ thuật** để block deployment:
```
Trước khi có error budget: "PM muốn deploy → deploy"
Sau khi có error budget:   "PM muốn deploy → check budget → 
                            budget < 10% → defer hoặc reliability fix trước"
```

### 7.2 Incident Priority dựa trên SLO Impact

```
Severity 1 (P1): SLO breach likely/happening
  → Error rate > 1% trên SLO 99.9% service (burn rate > 10x)
  → Immediate response, không quá 5 phút
  → Escalation ngay nếu không resolve trong 30 phút

Severity 2 (P2): SLO at risk
  → Burn rate 3-10x trong > 30 phút
  → Response trong 15 phút
  → Không cần wake up, nhưng cần fix trong working hours

Severity 3 (P3): Monitoring/observability issue
  → SLI không collect được (không biết tình trạng)
  → Treat như potential P1 cho đến khi xác nhận được
```

### 7.3 Security SLI

```
Availability SLI phải exclude planned maintenance windows.
Nếu không: Security patch downtime burn error budget
→ Dùng label hoặc timestamp để mark maintenance window
→ Exclude từ SLI calculation

PromQL:
  rate(http_requests_total[5m]) unless on() vector(maintenance_mode == 1)
```

---

## 8. Hands-on Example

### Scenario: E-commerce Checkout API

Chúng ta sẽ định nghĩa SLI/SLO cho service `checkout-api` với 500K request/ngày.

### 8.1 Định nghĩa SLI và SLO

```yaml
# slo-definition.yaml — Dùng với Sloth hoặc document thủ công

service: checkout-api
owner: payment-team
review_cadence: monthly

slos:
  - name: availability
    description: "Tỷ lệ checkout request thành công"
    sli:
      good_events: 'sum(rate(http_requests_total{service="checkout-api",code!~"5.."}[window]))'
      total_events: 'sum(rate(http_requests_total{service="checkout-api"}[window]))'
    objective: 99.9   # 99.9% over 30-day rolling window
    
  - name: latency-p99
    description: "99% checkout request hoàn thành trong 2 giây"
    sli:
      good_events: 'sum(rate(http_request_duration_seconds_bucket{service="checkout-api",le="2"}[window]))'
      total_events: 'sum(rate(http_request_duration_seconds_count{service="checkout-api"}[window]))'
    objective: 99.0   # 99% of requests under 2s

  - name: correctness
    description: "Tỷ lệ order được tạo thành công và có order_id hợp lệ"
    sli:
      good_events: 'sum(rate(checkout_orders_total{status="created"}[window]))'
      total_events: 'sum(rate(checkout_orders_total[window]))'
    objective: 99.95
```

### 8.2 PromQL Queries cho SLI

```promql
# ===== AVAILABILITY SLI =====

# SLI: Tỷ lệ success request (5 phút window)
sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[5m]))
/
sum(rate(http_requests_total{service="checkout-api"}[5m]))

# Error Rate (= 1 - SLI)
1 - (
  sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[5m]))
  /
  sum(rate(http_requests_total{service="checkout-api"}[5m]))
)

# ===== LATENCY SLI =====

# SLI: % request < 2s (histogram_quantile approach)
sum(rate(http_request_duration_seconds_bucket{service="checkout-api", le="2.0"}[5m]))
/
sum(rate(http_request_duration_seconds_count{service="checkout-api"}[5m]))

# P99 latency
histogram_quantile(0.99, 
  sum by(le) (
    rate(http_request_duration_seconds_bucket{service="checkout-api"}[5m])
  )
)

# ===== ERROR BUDGET REMAINING =====

# Error budget consumed (30-day rolling)
# SLO = 99.9% → error_budget_fraction = 0.001

(
  1 - (
    sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[30d]))
    /
    sum(rate(http_requests_total{service="checkout-api"}[30d]))
  )
) / 0.001

# Value > 1.0 = budget exceeded
# Value = 0.5 = 50% budget consumed

# Error budget remaining (%)
(1 - (
  (
    1 - (
      sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[30d]))
      /
      sum(rate(http_requests_total{service="checkout-api"}[30d]))
    )
  ) / 0.001
)) * 100

# ===== BURN RATE =====

# Current burn rate (1-hour window)
(
  1 - (
    sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[1h]))
    /
    sum(rate(http_requests_total{service="checkout-api"}[1h]))
  )
) / 0.001
```

### 8.3 Recording Rules (Prometheus)

```yaml
# /etc/prometheus/rules/slo-checkout-recording-rules.yaml

groups:
  - name: slo_checkout_recording
    interval: 1m
    rules:
      # Availability SLI — short windows
      - record: slo:sli_error:ratio_rate5m
        expr: |
          1 - (
            sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[5m]))
            /
            sum(rate(http_requests_total{service="checkout-api"}[5m]))
          )
        labels:
          service: checkout-api
          slo: availability

      - record: slo:sli_error:ratio_rate30m
        expr: |
          1 - (
            sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[30m]))
            /
            sum(rate(http_requests_total{service="checkout-api"}[30m]))
          )
        labels:
          service: checkout-api
          slo: availability

      - record: slo:sli_error:ratio_rate1h
        expr: |
          1 - (
            sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[1h]))
            /
            sum(rate(http_requests_total{service="checkout-api"}[1h]))
          )
        labels:
          service: checkout-api
          slo: availability

      - record: slo:sli_error:ratio_rate6h
        expr: |
          1 - (
            sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[6h]))
            /
            sum(rate(http_requests_total{service="checkout-api"}[6h]))
          )
        labels:
          service: checkout-api
          slo: availability

      - record: slo:sli_error:ratio_rate1d
        expr: |
          1 - (
            sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[1d]))
            /
            sum(rate(http_requests_total{service="checkout-api"}[1d]))
          )
        labels:
          service: checkout-api
          slo: availability

      - record: slo:sli_error:ratio_rate3d
        expr: |
          1 - (
            sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[3d]))
            /
            sum(rate(http_requests_total{service="checkout-api"}[3d]))
          )
        labels:
          service: checkout-api
          slo: availability
```

### 8.4 Burn Rate Alert Rules

```yaml
# /etc/prometheus/rules/slo-checkout-alerts.yaml
# SLO target: 99.9% availability (error_budget = 0.001)

groups:
  - name: slo_checkout_alerts
    rules:

      # ===== PAGE: Critical burn rate =====
      # Burn rate > 14.4x: budget hết trong ~2 ngày
      # Requires BOTH: 5m window AND 1h window violated
      - alert: CheckoutSLOBurnRateCritical
        expr: |
          (
            slo:sli_error:ratio_rate5m{service="checkout-api", slo="availability"}
            / 0.001 > 14.4
          )
          and
          (
            slo:sli_error:ratio_rate1h{service="checkout-api", slo="availability"}
            / 0.001 > 14.4
          )
        for: 2m
        labels:
          severity: page
          team: payment
          slo: availability
        annotations:
          summary: "Checkout API SLO critical burn rate"
          description: |
            Checkout API đang burn error budget ở tốc độ {{ $value | humanize }}x.
            Budget sẽ hết trong vòng ~2 ngày nếu tiếp tục.
            Error rate hiện tại: {{ with query "1 - slo:sli_error:ratio_rate5m{service='checkout-api'}" }}{{ . | first | value | humanizePercentage }}{{ end }}
          runbook_url: "https://runbooks.internal/checkout-slo-critical"
          dashboard_url: "https://grafana.internal/d/checkout-slo"

      # ===== TICKET: High burn rate =====
      # Burn rate > 6x: budget hết trong ~5 ngày
      - alert: CheckoutSLOBurnRateHigh
        expr: |
          (
            slo:sli_error:ratio_rate30m{service="checkout-api", slo="availability"}
            / 0.001 > 6
          )
          and
          (
            slo:sli_error:ratio_rate6h{service="checkout-api", slo="availability"}
            / 0.001 > 6
          )
        for: 15m
        labels:
          severity: ticket
          team: payment
          slo: availability
        annotations:
          summary: "Checkout API SLO high burn rate"
          description: |
            Checkout API đang burn error budget ở mức cao.
            Burn rate: {{ $value | humanize }}x (normal = 1x).
            Cần investigate trong working hours.
          runbook_url: "https://runbooks.internal/checkout-slo-high"

      # ===== WARNING: Elevated burn rate =====
      # Burn rate > 3x: budget hết trong ~10 ngày
      - alert: CheckoutSLOBurnRateElevated
        expr: |
          (
            slo:sli_error:ratio_rate2h{service="checkout-api", slo="availability"}
            / 0.001 > 3
          )
          and
          (
            slo:sli_error:ratio_rate1d{service="checkout-api", slo="availability"}
            / 0.001 > 3
          )
        for: 1h
        labels:
          severity: warning
          team: payment
          slo: availability
        annotations:
          summary: "Checkout API SLO burn rate elevated"
          description: |
            Burn rate {{ $value | humanize }}x — theo dõi thêm.

      # ===== INFO: Budget running low =====
      - alert: CheckoutSLOBudgetLow
        expr: |
          (
            (
              1 - (
                sum(rate(http_requests_total{service="checkout-api", code!~"5.."}[30d]))
                /
                sum(rate(http_requests_total{service="checkout-api"}[30d]))
              )
            ) / 0.001
          ) > 0.9
        labels:
          severity: info
          team: payment
        annotations:
          summary: "Checkout API error budget < 10% remaining"
          description: "Chỉ còn < 10% error budget cho tháng này. Feature freeze nên được xem xét."
```

### 8.5 Setup môi trường test

```bash
# === 1. Chạy Prometheus + demo app bằng Docker Compose ===

mkdir -p ~/slo-lab/{prometheus,grafana/dashboards,rules}

# Tạo demo app đơn giản với metrics
cat > ~/slo-lab/app.py << 'EOF'
from flask import Flask, jsonify
from prometheus_client import Counter, Histogram, generate_latest
import random, time

app = Flask(__name__)

REQUEST_COUNT = Counter(
    'http_requests_total', 
    'Total HTTP requests',
    ['service', 'code']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['service'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

@app.route('/checkout', methods=['POST', 'GET'])
def checkout():
    start = time.time()
    service = 'checkout-api'
    
    # Simulate ~1% error rate, occasional spikes
    error_prob = 0.01
    latency = random.gauss(0.3, 0.1)  # mean 300ms, std 100ms
    
    time.sleep(max(0, latency))
    
    if random.random() < error_prob:
        REQUEST_COUNT.labels(service=service, code='500').inc()
        REQUEST_LATENCY.labels(service=service).observe(time.time() - start)
        return jsonify({'error': 'Internal Server Error'}), 500
    
    REQUEST_COUNT.labels(service=service, code='200').inc()
    REQUEST_LATENCY.labels(service=service).observe(time.time() - start)
    return jsonify({'order_id': f'ord_{random.randint(10000,99999)}', 'status': 'created'}), 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Docker Compose
cat > ~/slo-lab/docker-compose.yml << 'EOF'
version: '3.8'
services:
  checkout-api:
    image: python:3.11-slim
    working_dir: /app
    volumes:
      - ./app.py:/app/app.py
    command: bash -c "pip install flask prometheus-client -q && python app.py"
    ports:
      - "5000:5000"

  load-generator:
    image: alpine/curl
    depends_on:
      - checkout-api
    command: >
      sh -c "sleep 10 && while true; do 
        curl -s -o /dev/null http://checkout-api:5000/checkout;
        sleep 0.1; 
      done"

  prometheus:
    image: prom/prometheus:v2.47.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./rules:/etc/prometheus/rules

  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/dashboards:/var/lib/grafana/dashboards

EOF

# Prometheus config
cat > ~/slo-lab/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 30s

rule_files:
  - "rules/*.yaml"

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: checkout-api
    static_configs:
      - targets: ['checkout-api:5000']
    metrics_path: /metrics
EOF

# Copy alert rules
mkdir -p ~/slo-lab/rules
# (paste rules từ section 8.4 vào ~/slo-lab/rules/slo-alerts.yaml)

# Chạy
cd ~/slo-lab
docker compose up -d

# Verify
curl http://localhost:5000/checkout
curl http://localhost:5000/metrics | grep http_requests_total
```

### 8.6 Kiểm tra và simulate incident

```bash
# === Verify SLI metrics có data ===
# Mở Prometheus UI: http://localhost:9090

# Query 1: Kiểm tra error rate baseline
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=1 - (sum(rate(http_requests_total{service="checkout-api",code!~"5.."}[5m])) / sum(rate(http_requests_total{service="checkout-api"}[5m])))' \
  | jq '.data.result[0].value[1]'

# Expected: ~0.01 (1% error rate)

# === Simulate incident: Tăng error rate lên 10% ===
# Modify app.py: error_prob = 0.10
# hoặc inject errors bằng curl:

for i in $(seq 1 100); do
  curl -s -o /dev/null http://localhost:5000/checkout &
done
wait

# Query burn rate sau incident
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=(1 - (sum(rate(http_requests_total{service="checkout-api",code!~"5.."}[5m])) / sum(rate(http_requests_total{service="checkout-api"}[5m])))) / 0.001' \
  | jq '.data.result[0].value[1]'

# Expected: > 14.4 nếu error rate đạt 10%
# (0.10 / 0.001 = 100x burn rate!)

# === Cleanup ===
cd ~/slo-lab
docker compose down -v
cd ~
rm -rf ~/slo-lab
```

---

## 9. Common Pitfalls & Debugging

### 9.1 SLI không có data

```bash
# Symptom: Query trả về empty
# Nguyên nhân thường gặp:
1. Label không khớp: service="checkout" vs service="checkout-api"
2. Metric chưa có data (service chưa nhận traffic)
3. Scrape chưa hoạt động

# Debug:
# Kiểm tra scrape targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'

# Kiểm tra metric tồn tại
curl http://localhost:9090/api/v1/label/__name__/values | jq '.data[]' | grep http_requests
```

### 9.2 Error budget luôn = 0 ngay khi setup

```
Nguyên nhân: SLO đặt cao hơn actual performance
Fix: 
  1. Đo actual error rate của 30 ngày qua
  2. Đặt SLO = (1 - actual_error_rate * 1.5)
  → Cho phép 50% buffer so với historical worst case
```

### 9.3 Alert không bắn dù error rate cao

```bash
# Kiểm tra recording rules có đủ data chưa
# Recording rules cần ít nhất [window] data points

# Nếu dùng rate5m: cần 5 phút data
# Nếu dùng rate1h: cần 1 giờ data
# Nếu dùng rate30d: cần 30 ngày data!

# Solution: Dùng recording rules cascade
# Đừng dùng rate(metric[30d]) trực tiếp trong alert
```

### 9.4 Case study: Từ 247 alert xuống 12

**Bối cảnh**: E-commerce team với 247 alert rules, on-call bị báo hơn 50 lần/tuần.

**Phân tích**:
```
Sau khi audit 247 alerts:
- 89 alert: Chưa bao giờ actionable (CPU/memory threshold)
- 73 alert: Trùng lặp từ service khác (cascade)
- 51 alert: Threshold quá thấp, bắn daily mà không ai xử lý
- 22 alert: Có runbook nhưng runbook outdated
- 12 alert: Thực sự quan trọng, liên quan đến user impact
```

**Kết quả sau migration sang SLO-based alerting**:
```
Before: 247 rules, 50+ pages/week, MTTR = 87 phút
After:  12 rules,  3 pages/week,   MTTR = 23 phút

Cải thiện MTTR 73% vì:
- Engineer không bị desensitized khi alert bắn
- Mỗi alert rõ ràng cần làm gì
- On-call có mental energy để actually investigate
```

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 42: OpenTelemetry & Distributed Tracing
- OTel cung cấp **raw data** (spans, traces, metrics)
- SLI là **aggregate** của OTel data thành meaningful measurement
- Trace sampling rate ảnh hưởng đến SLI accuracy → cần 100% sampling cho error traces
- `http.status_code` span attribute → SLI error rate metric

### Bài sau — Day 44: Incident Response & Postmortem
- SLO breach trigger incident → Day 44 sẽ dạy cách handle incident đó
- Error budget consumed % → severity của incident
- Postmortem output nên include: "How much error budget was consumed?"
- SLO-based alerting (Day 43) → Feeds incident priority system (Day 44)

### Liên quan đến các bài trước
- **Day 39 (Prometheus)**: Recording rules và PromQL foundation cho SLI queries
- **Day 40 (Grafana Alerting)**: Alert routing và notification channels cho SLO alerts
- **Day 38 (Observability fundamentals)**: SLI là practical application của metrics pillar

---

## 11. Tài liệu tham khảo

### Must-Read (ưu tiên cao nhất)
| Tài liệu | Nội dung | Link |
|---|---|---|
| **Google SRE Book — Chapter 4** | SLOs, SLIs nền tảng | https://sre.google/sre-book/service-level-objectives/ |
| **Google SRE Workbook — Chapter 5** | Alerting on SLOs, burn rate | https://sre.google/workbook/alerting-on-slos/ |
| **Google SRE Workbook — Chapter 2** | Implementing SLOs | https://sre.google/workbook/implementing-slos/ |

### Nice-to-Have
| Tài liệu | Nội dung |
|---|---|
| Sloth Documentation | SLO-as-code với Sloth tool |
| Pyrra GitHub | Open-source SLO management |
| Alex Hidalgo — "Implementing Service Level Objectives" (O'Reilly) | Full book về SLO practice |

### Deep-Dive (chuyên sâu)
| Tài liệu | Nội dung |
|---|---|
| Google SRE Book — Chapter 13 | Emergency Response |
| Google SRE Book — Chapter 29 | Dealing with Interrupts (Alert Fatigue) |
| Prometheus Operator SLO Guide | Production Prometheus SLO setup |
| Nobl9 SLO Academy | Interactive SLO learning |

---

*Bài tiếp theo: Day 44 — Incident Response & Postmortem — Khi SLO bị vi phạm, làm gì?*

