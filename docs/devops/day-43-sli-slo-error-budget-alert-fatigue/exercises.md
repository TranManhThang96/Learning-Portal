# Day 43 — Exercises: SLI/SLO, Error Budget & Alert Fatigue

> **Phase 6 — Observability & Reliability**  
> Hoàn thành lesson.md trước khi làm exercises này.

---

## Exercise 1 (Easy) — Tính Error Budget và Phân tích SLO

### Bối cảnh

Bạn vừa join team SRE tại một công ty fintech. Product Manager gửi cho bạn bảng sau và hỏi: *"Chúng ta có thể deploy vào thứ Sáu không?"*

```
Service: payment-api
SLO: 99.9% availability (30-day rolling window)
Tháng hiện tại (30 ngày):

Ngày 1-10:   Error rate 0.05% (normal)
Ngày 11-15:  Error rate 2.0%  (incident xảy ra, đã resolve)
Ngày 16-30:  Error rate 0.03% (normal)
```

Hôm nay là ngày 30. Team vừa có incident nhỏ ngày 28-29 làm error rate lên 0.8%.

### Yêu cầu

1. Tính **total error budget** (tính bằng phút) cho tháng này
2. Tính **error budget đã dùng** dựa trên dữ liệu trên
3. Tính **error budget còn lại** (phút và %)
4. Đưa ra **khuyến nghị** có nên deploy thứ Sáu không, và tại sao
5. Viết **error budget policy** đơn giản (3 dòng) cho team này

### Expected Outcome

- Biết cách tính error budget bằng tay với dữ liệu thực
- Đưa ra quyết định deployment có căn cứ
- Viết được policy ngắn gọn

### Hint

```
Error budget (time) = (1 - SLO%) × 30 days × 24h × 60min
Budget consumed = sum over each period: (error_rate - 0%) × period_days × 24 × 60
Nhớ: Error rate 0.05% thấp hơn 0.1% (threshold), không consume extra budget.
Thực ra budget consumed = actual_errors / total_requests × total_time
Đơn giản hóa: consumed_minutes = error_rate × total_period_minutes
```

### Acceptance Criteria

- [ ] Total error budget tính đúng: 43.2 phút
- [ ] Budget consumed tính có giải thích từng giai đoạn
- [ ] Budget remaining được tính và thể hiện bằng %
- [ ] Khuyến nghị deploy/không deploy có lý do rõ ràng
- [ ] Policy có 3 mức: budget > 50%, budget < 25%, budget < 10%

### Bonus Challenge

Viết một bash script hoặc Python script nhỏ nhận vào: SLO%, danh sách (error_rate, duration_days) và output ra: budget consumed, budget remaining, recommendation.


---

## Exercise 2 (Medium) — Thiết kế SLI/SLO và Burn Rate Alerts cho API thực tế

### Bối cảnh

Bạn là SRE lead tại startup B2B SaaS. Team vừa ra mắt `user-auth-api` — service xác thực người dùng mà 100% feature khác depend vào. Service này có đặc điểm:

- 2M request/ngày (peak: 50K req/phút vào 9AM-10AM)
- 2 loại operation chính: `POST /login` và `GET /validate-token`
- `/login` chấp nhận latency cao hơn (user đang nhập password)
- `/validate-token` phải cực nhanh (called mỗi request từ các service khác)
- Customer tier: Premium (500 customers) và Standard (5,000 customers)

PM nói: *"User không được phép thấy lỗi khi login. Validate token có thể fail, app sẽ redirect login."*

### Yêu cầu

1. Định nghĩa **3 SLI** khác nhau phù hợp với service này (viết cả PromQL expression)
2. Đặt **SLO target** cho mỗi SLI với lý do cụ thể
3. Tính **error budget** cho mỗi SLO (30-day, phút)
4. Viết **2 burn rate alert rules** (PAGE và TICKET level) cho SLI availability
5. Giải thích tại sao chọn multi-window thay vì single window

### Expected Outcome

```yaml
# Output mong đợi dạng:
slo_definitions:
  - name: login-availability
    sli: <promql>
    target: 99.95%
    error_budget: X phút/tháng
    reason: "..."
  
  - name: validate-token-latency
    sli: <promql>
    target: 99.9%  
    error_budget: Y phút/tháng
    reason: "..."

alert_rules:
  - <prometheus yaml>
  - <prometheus yaml>
```

### Hint

```
Với /login:
  - Latency target cao hơn (user tolerant khi login)
  - Availability target rất cao (user không được thấy lỗi)
  - SLO 99.95% → error_budget = 0.0005 × 30 × 24 × 60 = 21.6 phút

Với /validate-token:
  - Latency phải cực thấp (internal service call)
  - Nhưng failure là recoverable (redirect to login)
  - SLO có thể thấp hơn một chút

Multi-window: short window detect fast, long window confirm sustained issue
Burns 14.4x = budget hết trong 30/14.4 ≈ 2 ngày (nếu sustained)
```

### Acceptance Criteria

- [ ] 3 SLI được định nghĩa với PromQL đúng và có label
- [ ] Mỗi SLO có lý do business cụ thể (không chỉ viết số)
- [ ] Error budget được tính đúng cho từng SLO
- [ ] 2 alert rules có đủ: expr, for, labels, annotations với runbook
- [ ] Giải thích multi-window có ví dụ cụ thể về false positive

### Bonus Challenge

Mở rộng thêm: Thiết kế **composite SLO** cho toàn bộ authentication journey (login + validate + logout), trong đó SLO journey < SLO từng component. Giải thích tại sao.


---

## Exercise 3 (Hard) — Redesign Alerting Strategy và Toil Reduction Plan

### Bối cảnh

Bạn được assigned vào một team đang "drowning in alerts". Đây là tình trạng hiện tại:

```
Service: order-processing-platform
Components: 
  - order-api (HTTP service)
  - order-worker (background job processor)  
  - payment-integration (external payment gateway wrapper)
  - notification-service (email/SMS)
  - inventory-service (stock management)

Current alert inventory (312 rules):
  Per service × 5 services:
    - CPU > 70%         → 5 rules
    - Memory > 80%      → 5 rules
    - Disk > 85%        → 5 rules
    - Pod restart > 2   → 5 rules
    - HTTP 5xx > 0.1%   → 5 rules (fires constantly)
    - P99 > 1s          → 5 rules (fires daily)
    - Queue depth > 100 → 3 rules
    - DB connections > 80% → 3 rules
    - External API timeout → 4 rules
    ... (và 267 rules khác tương tự)

On-call stats (last 30 days):
  Total pages: 287 (avg 9.6/ngày)
  Actionable pages: 23 (8%)
  MTTAR (time to acknowledge): 18 phút average
  MTTR: 2.4 giờ average
  On-call engineer survey: 7/10 rating "extremely stressful"

Known toil (from team survey):
  - Restart order-worker mỗi sáng (memory leak) — 15 phút/ngày
  - Review và acknowledge "noise" alerts — 45 phút/ngày
  - Manual deploy approval checklist — 20 phút/deploy, 3 deploy/ngày
  - Rotate database credentials mỗi 90 ngày — 3 giờ/quarter
  - Respond to "is the system ok?" Slack questions — 30 phút/ngày
  - Monthly capacity planning spreadsheet update — 4 giờ/tháng
```

### Yêu cầu

**Phần A: SLO Design (30%)**
1. Xác định **user-centric SLIs** cho toàn bộ order-processing-platform (không phải per-component)
2. Đặt SLO targets với lý do business
3. Viết PromQL cho mỗi SLI (assume metrics đã tồn tại)

**Phần B: Alert Redesign (40%)**
1. Từ 312 rules, thiết kế bộ alert mới (target: < 20 rules)
2. Phân loại: PAGE, TICKET, INFO
3. Viết full Prometheus YAML cho ít nhất 4 alert rules quan trọng nhất
4. Tính toán: Expected pages/ngày sau redesign (với assumption hợp lý)
5. Tạo alert review checklist — câu hỏi để evaluate "alert này có cần không?"

**Phần C: Toil Reduction Plan (30%)**
1. Phân loại toil theo priority (impact × effort matrix)
2. Với TOP 3 toil cao nhất: đề xuất automation với technical approach cụ thể
3. Tính ROI: giờ tiết kiệm/tháng sau khi eliminate toil
4. Đặt KPI: % toil/total work time (target: < 30%)

### Expected Outcome

```
Phần A: 3-4 SLI definitions + SLO targets + PromQL
Phần B: Alert architecture diagram + < 20 alert rules YAML + review checklist
Phần C: Toil matrix + top 3 automation plans + ROI calculation
```

### Hint

- Bắt đầu từ user journey trước, không bắt đầu từ metric có sẵn. Nếu user không bị đánh thức lúc `CPU > 70%`, đó thường là dashboard signal hoặc ticket, không phải PAGE.
- Với burn-rate alerts, dùng multi-window để giảm noise: short window xác nhận tốc độ cháy nhanh, long window xác nhận tác động không phải spike ngắn.
- Toil reduction nên có số giờ/tháng trước và sau automation; nếu không tính được ROI, action item dễ biến thành "nice-to-have".

### Acceptance Criteria

- [ ] SLI phản ánh end-to-end user journey (order creation, payment, notification)
- [ ] Alert rules mới ≤ 20, có đủ severity/tier
- [ ] Giải thích tại sao "CPU > 70%" không nên là alert
- [ ] Toil reduction plan có technical detail (không chỉ "automate nó")
- [ ] ROI calculation có số liệu cụ thể
- [ ] Alert review checklist có ≥ 5 questions cụ thể và actionable

### Bonus Challenge

Viết một **Terraform module** hoặc **Helm chart values** để deploy toàn bộ alert rules mới thành infrastructure-as-code, với variable cho SLO target (dễ điều chỉnh per environment).


---

## Tổng kết Exercises

| Exercise | Skill Focus | Time estimate |
|---|---|---|
| Easy: Error Budget Calculation | Math + policy thinking | 30-45 phút |
| Medium: SLI/SLO Design + Alerts | PromQL + alert design | 60-75 phút |
| Hard: Full Redesign + Toil | System thinking + engineering | 90-120 phút |

**Học được gì sau 3 exercises:**
- Tính error budget bằng tay và bằng code
- Thiết kế SLI/SLO cho real-world service với nhiều constraints
- Viết production-grade Prometheus alert rules
- Phân tích và reduce toil có phương pháp
- Hiểu tại sao alert fatigue xảy ra và cách fix từ gốc rễ

---

## Solutions

<details>
<summary>Xem Solution</summary>

```
=== TÍNH TOÁN ===

Total Error Budget:
  SLO = 99.9% → error budget = 0.001 (0.1%)
  Budget time = 0.001 × 30 × 24 × 60 = 43.2 phút

Budget Consumed (từng giai đoạn):
  Ngày 1-10 (10 ngày = 14,400 phút):
    Error rate = 0.05% = 0.0005
    Consumed = 0.0005 × 14,400 = 7.2 phút
    (note: <0.1% baseline nhưng vẫn consume — mọi error đều consume budget)

  Ngày 11-15 (5 ngày = 7,200 phút):
    Error rate = 2.0% = 0.020
    Consumed = 0.020 × 7,200 = 144 phút
    (đây là giai đoạn incident chính)

  Ngày 16-27 (12 ngày = 17,280 phút):
    Error rate = 0.03% = 0.0003
    Consumed = 0.0003 × 17,280 = 5.18 phút

  Ngày 28-29 (2 ngày = 2,880 phút):
    Error rate = 0.8% = 0.008
    Consumed = 0.008 × 2,880 = 23.04 phút

  Ngày 30 (1 ngày = 1,440 phút):
    Error rate = 0.03% = 0.0003
    Consumed = 0.0003 × 1,440 = 0.43 phút

Total Consumed = 7.2 + 144 + 5.18 + 23.04 + 0.43 = 179.85 phút

Budget Remaining:
  43.2 - 179.85 = -136.65 phút (âm! = SLO đã bị vi phạm)
  % consumed = 179.85 / 43.2 × 100 = 416% (đã burn gấp 4 lần budget!)

=== KHUYẾN NGHỊ ===
KHÔNG deploy thứ Sáu.
- Error budget đã cạn từ ngày 11-15 (incident lớn tiêu 144 phút)
- Incident thêm ngày 28-29 làm tình hình tệ hơn
- Cần post-mortem và reliability sprint trước khi deploy feature mới

=== ERROR BUDGET POLICY ===
1. Budget > 50%: Deploy bình thường, theo process thông thường
2. Budget < 25%: Tăng review gate, không deploy breaking changes, cần SRE approval
3. Budget < 10% hoặc âm: Feature freeze toàn bộ, chỉ ship reliability fixes,
   weekly review với engineering leadership cho đến khi budget recover (next month)
```

```python
#!/usr/bin/env python3
# error_budget_calculator.py

def calculate_error_budget(slo_percent, periods, window_days=30):
    """
    slo_percent: e.g., 99.9
    periods: list of (error_rate_percent, duration_days)
    """
    error_budget_fraction = 1 - (slo_percent / 100)
    total_minutes = window_days * 24 * 60
    budget_minutes = error_budget_fraction * total_minutes
    
    print(f"=== Error Budget Calculator ===")
    print(f"SLO: {slo_percent}%")
    print(f"Error Budget: {error_budget_fraction*100:.3f}% = {budget_minutes:.1f} phút\n")
    
    consumed = 0
    for i, (error_rate, duration) in enumerate(periods):
        period_minutes = duration * 24 * 60
        period_consumed = (error_rate / 100) * period_minutes
        consumed += period_consumed
        status = "⚠️ HIGH" if error_rate / 100 > error_budget_fraction * 5 else "OK"
        print(f"Giai đoạn {i+1} ({duration} ngày, error={error_rate}%): "
              f"consumed {period_consumed:.1f} phút {status}")
    
    remaining = budget_minutes - consumed
    pct_remaining = (remaining / budget_minutes) * 100
    
    print(f"\nTotal consumed: {consumed:.1f} phút ({consumed/budget_minutes*100:.0f}%)")
    print(f"Remaining: {remaining:.1f} phút ({pct_remaining:.0f}%)")
    
    if pct_remaining > 50:
        print("RECOMMENDATION: Deploy OK ✅")
    elif pct_remaining > 10:
        print("RECOMMENDATION: Deploy với caution, cần SRE review ⚠️")
    elif pct_remaining > 0:
        print("RECOMMENDATION: Feature freeze, chỉ reliability fixes 🛑")
    else:
        print("RECOMMENDATION: SLO đã vi phạm! Emergency reliability sprint 🚨")

if __name__ == "__main__":
    periods = [
        (0.05, 10),   # Ngày 1-10
        (2.0,  5),    # Ngày 11-15 (incident)
        (0.03, 12),   # Ngày 16-27
        (0.8,  2),    # Ngày 28-29 (incident nhỏ)
        (0.03, 1),    # Ngày 30
    ]
    calculate_error_budget(99.9, periods, window_days=30)
```

</details>

<details>
<summary>Xem Solution</summary>

```yaml
# === SLO DEFINITIONS ===

slo_definitions:
  - name: login-availability
    description: "Tỷ lệ login request thành công (không 5xx)"
    sli:
      good: 'sum(rate(http_requests_total{service="user-auth-api", endpoint="/login", code!~"5.."}[window]))'
      total: 'sum(rate(http_requests_total{service="user-auth-api", endpoint="/login"}[window]))'
    target: 99.95%
    error_budget_minutes: 21.6
    reason: |
      PM yêu cầu user không được thấy lỗi khi login.
      99.95% cho phép ~21 phút downtime/tháng.
      Cao hơn 99.9% vì login là critical path, user không có fallback.

  - name: validate-token-latency-p99
    description: "99% validate-token request hoàn thành trong 50ms"
    sli:
      good: 'sum(rate(http_request_duration_seconds_bucket{service="user-auth-api", endpoint="/validate-token", le="0.05"}[window]))'
      total: 'sum(rate(http_request_duration_seconds_count{service="user-auth-api", endpoint="/validate-token"}[window]))'
    target: 99.5%
    error_budget_minutes: 216
    reason: |
      validate-token được gọi mỗi API request từ downstream.
      50ms P99 đủ nhanh, tránh làm chậm cascading.
      99.5% (không phải 99.9%) vì failure có graceful fallback (redirect login).

  - name: validate-token-availability
    description: "Tỷ lệ validate-token request không trả 5xx"
    sli:
      good: 'sum(rate(http_requests_total{service="user-auth-api", endpoint="/validate-token", code!~"5.."}[window]))'
      total: 'sum(rate(http_requests_total{service="user-auth-api", endpoint="/validate-token"}[window]))'
    target: 99.9%
    error_budget_minutes: 43.2
    reason: |
      5xx từ validate-token cascade xuống tất cả downstream services.
      99.9% là cân bằng tốt: chặt đủ để detect issue sớm,
      nhưng thoải mái hơn login vì client có fallback.

# === ALERT RULES ===
```

```yaml
# prometheus-alerts.yaml

groups:
  - name: user_auth_api_slo
    rules:

      # === PAGE: login-availability burn rate critical ===
      # SLO 99.95% → error_budget = 0.0005
      # Burn 14.4x → budget hết trong 2 ngày
      - alert: LoginAvailabilitySLOCritical
        expr: |
          (
            (1 - sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login",
              code!~"5.."}[5m]))
            / sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login"}[5m]))
            ) / 0.0005 > 14.4
          )
          and
          (
            (1 - sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login",
              code!~"5.."}[1h]))
            / sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login"}[1h]))
            ) / 0.0005 > 14.4
          )
        for: 2m
        labels:
          severity: page
          team: auth
          slo: login-availability
        annotations:
          summary: "Login API SLO critical — immediate action required"
          description: |
            Login API đang burn error budget ở {{ $value | humanize }}x.
            Người dùng đang không login được. Budget sẽ hết trong ~2 ngày.
          runbook_url: "https://runbooks.internal/login-slo-critical"

      # === TICKET: login-availability burn rate high ===
      # Burn 6x → budget hết trong 5 ngày
      - alert: LoginAvailabilitySLOHigh
        expr: |
          (
            (1 - sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login",
              code!~"5.."}[30m]))
            / sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login"}[30m]))
            ) / 0.0005 > 6
          )
          and
          (
            (1 - sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login",
              code!~"5.."}[6h]))
            / sum(rate(http_requests_total{
              service="user-auth-api",
              endpoint="/login"}[6h]))
            ) / 0.0005 > 6
          )
        for: 15m
        labels:
          severity: ticket
          team: auth
          slo: login-availability
        annotations:
          summary: "Login API SLO elevated burn rate — investigate in working hours"
          description: |
            Login API burn rate {{ $value | humanize }}x (normal = 1x).
            Cần investigate, không cần wake up on-call lúc này.
          runbook_url: "https://runbooks.internal/login-slo-high"
```

```
=== LÝ DO MULTI-WINDOW ===

Scenario: Error rate tăng đột ngột lên 5% trong 3 phút rồi tự hồi phục.

Single window 5m:
  → Alert BẮN (5m window thấy 5% error)
  → Alert TỰ RESOLVE 3 phút sau
  → On-call bị wake up lúc 3AM, vào điều tra thì đã tự fix
  → False positive → on-call bắt đầu ignore alert

Multi-window (5m AND 1h):
  → 5m window: thấy 5% → TRUE
  → 1h window: average chỉ ~0.25% (3 phút / 60 phút × 5%) → FALSE
  → Alert KHÔNG BẮN vì không thoả cả 2 điều kiện
  → On-call không bị disturb
  → Khi issue thực sự sustained: cả 2 window đều breach → alert bắn đúng lúc
```

```yaml
# BONUS: Composite SLO cho authentication journey
# Journey: User → Login → Access protected resource → Logout
# 
# Component SLOs:
#   login-availability: 99.95%
#   validate-token-availability: 99.90%
#   logout-availability: 99.50%
#
# Composite SLO calculation:
#   P(journey success) = P(login) × P(validate) × P(logout)
#                      = 0.9995 × 0.9990 × 0.9950
#                      = 0.9935 ≈ 99.35%
#
# → Composite SLO nên đặt ≤ 99.3% (thấp hơn từng component)
# → ĐÂY LÀ TẠI SAO: even nếu tất cả component đều healthy,
#   end-to-end journey luôn có xác suất thất bại cao hơn.
#   Đặt composite SLO cao hơn tích = setting yourself up for failure.
```

</details>

<details>
<summary>Xem Solution</summary>

```
=== PHẦN A: SLO DESIGN ===

User journey của order-processing-platform:
  1. User tạo order → order-api xử lý
  2. Payment được charge → payment-integration
  3. Inventory được reserve → inventory-service
  4. Notification được gửi → notification-service (async)
  5. order-worker process background jobs

SLI 1: Order Creation Availability
  "Tỷ lệ order creation request thành công (2xx)"
  Good: sum(rate(http_requests_total{service="order-api", endpoint=~"/orders.*", method="POST", code!~"5.."}[window]))
  Total: sum(rate(http_requests_total{service="order-api", endpoint=~"/orders.*", method="POST"}[window]))
  SLO: 99.9%  (order creation fail = revenue loss)
  Budget: 43.2 phút/tháng

SLI 2: Order-to-Payment Latency (E2E)
  "99% order kèm payment hoàn thành trong 5 giây"
  Good: sum(rate(order_payment_duration_seconds_bucket{le="5"}[window]))
  Total: sum(rate(order_payment_duration_seconds_count[window]))
  SLO: 99.0%  (user tolerate một chút chậm khi payment)
  Budget: 432 phút/tháng

SLI 3: Notification Delivery (async, freshness-based)
  "90% notification gửi thành công trong vòng 5 phút sau order"
  Good: sum(rate(notifications_delivered_total{within_sla="true"}[window]))
  Total: sum(rate(notifications_sent_total[window]))
  SLO: 99.5%  (notification failure là bad UX nhưng không block transaction)
  Budget: 216 phút/tháng

SLI 4: Order Processing Throughput
  "order-worker xử lý ≥ 95% queue depth trong SLA window"
  Good: sum(rate(orders_processed_total[window]))
  Total: sum(rate(orders_queued_total[window]))
  SLO: 99.0%  
  Budget: 432 phút/tháng
```

```yaml
# === PHẦN B: NEW ALERT RULES (18 rules total) ===

groups:
  # ============ ORDER CREATION SLO ============
  - name: order_creation_slo
    rules:
      - alert: OrderCreationSLOCritical       # PAGE
        expr: |
          (1 - sum(rate(http_requests_total{service="order-api",method="POST",code!~"5.."}[5m]))
          / sum(rate(http_requests_total{service="order-api",method="POST"}[5m]))) / 0.001 > 14.4
          and
          (1 - sum(rate(http_requests_total{service="order-api",method="POST",code!~"5.."}[1h]))
          / sum(rate(http_requests_total{service="order-api",method="POST"}[1h]))) / 0.001 > 14.4
        for: 2m
        labels:
          severity: page
          slo: order-creation
        annotations:
          summary: "Order creation SLO critical burn rate"
          description: "Customers cannot create orders. Revenue impact active."
          runbook_url: "https://runbooks.internal/order-creation-critical"

      - alert: OrderCreationSLOHigh           # TICKET
        expr: |
          (1 - sum(rate(http_requests_total{service="order-api",method="POST",code!~"5.."}[30m]))
          / sum(rate(http_requests_total{service="order-api",method="POST"}[30m]))) / 0.001 > 6
          and
          (1 - sum(rate(http_requests_total{service="order-api",method="POST",code!~"5.."}[6h]))
          / sum(rate(http_requests_total{service="order-api",method="POST"}[6h]))) / 0.001 > 6
        for: 15m
        labels:
          severity: ticket
          slo: order-creation
        annotations:
          summary: "Order creation SLO elevated — investigate in working hours"

  # ============ PAYMENT INTEGRATION ============
  - name: payment_slo
    rules:
      - alert: PaymentIntegrationSLOCritical  # PAGE
        expr: |
          (1 - sum(rate(order_payment_duration_seconds_bucket{le="5"}[5m]))
          / sum(rate(order_payment_duration_seconds_count[5m]))) / 0.01 > 14.4
          and
          (1 - sum(rate(order_payment_duration_seconds_bucket{le="5"}[1h]))
          / sum(rate(order_payment_duration_seconds_count[1h]))) / 0.01 > 14.4
        for: 2m
        labels:
          severity: page
          slo: payment-latency
        annotations:
          summary: "Payment latency SLO critical"
          description: "Payment processing is extremely slow. Customers may be abandoning checkout."

      - alert: PaymentGatewayErrorRate        # PAGE (external dependency)
        expr: |
          sum(rate(payment_gateway_errors_total[5m]))
          / sum(rate(payment_gateway_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: page
          team: payment
        annotations:
          summary: "Payment gateway error rate > 5%"
          description: "External payment gateway may be down. Contact gateway support."

  # ============ NOTIFICATION SERVICE ============
  - name: notification_slo
    rules:
      - alert: NotificationDeliveryLow        # TICKET (async, less urgent)
        expr: |
          sum(rate(notifications_delivered_total{within_sla="true"}[1h]))
          / sum(rate(notifications_sent_total[1h])) < 0.99
        for: 30m
        labels:
          severity: ticket
        annotations:
          summary: "Notification delivery SLO degraded"

  # ============ INFRASTRUCTURE (minimal, symptom-based) ============
  - name: infrastructure_critical
    rules:
      - alert: PodCrashLooping               # PAGE (immediate symptom)
        expr: |
          sum by(pod, namespace) (
            rate(kube_pod_container_status_restarts_total[15m])
          ) * 60 * 15 > 5
        for: 5m
        labels:
          severity: page
        annotations:
          summary: "Pod {{ $labels.pod }} is crash looping"
          description: "5+ restarts in 15 minutes. Likely memory leak or OOMKill."
          runbook_url: "https://runbooks.internal/pod-crashloop"

      - alert: DiskWillFillIn4Hours          # TICKET (predictive)
        expr: |
          predict_linear(node_filesystem_free_bytes[2h], 4 * 3600) < 0
        for: 30m
        labels:
          severity: ticket
        annotations:
          summary: "Disk will fill in < 4 hours"

      - alert: DatabaseConnectionPoolExhausted # PAGE
        expr: |
          sum by(db) (pg_stat_activity_count)
          / sum by(db) (pg_settings_max_connections) > 0.95
        for: 5m
        labels:
          severity: page
        annotations:
          summary: "Database connection pool > 95% — queries will fail soon"

      - alert: OrderWorkerQueueBacklogged     # TICKET
        expr: |
          order_queue_depth > 1000
          and
          sum(rate(orders_processed_total[10m])) < 10
        for: 15m
        labels:
          severity: ticket
        annotations:
          summary: "Order worker queue backlogged and not draining"
          description: "Queue depth {{ $value }} with low processing rate. Worker may be stuck."

  # ============ BUDGET TRACKING ============
  - name: error_budget
    rules:
      - alert: OrderCreationBudgetLow        # INFO
        expr: |
          (1 - (sum(rate(http_requests_total{service="order-api",method="POST",code!~"5.."}[30d]))
          / sum(rate(http_requests_total{service="order-api",method="POST"}[30d])))) / 0.001 > 0.8
        labels:
          severity: info
        annotations:
          summary: "Order creation error budget < 20% remaining"
          description: "Consider feature freeze and reliability sprint."

# === TỔNG KẾT ===
# PAGE alerts: 5 (OrderCreationCritical, PaymentSLOCritical, PaymentGatewayError, PodCrashLoop, DBConnectionExhausted)
# TICKET alerts: 5 (OrderCreationHigh, NotificationLow, DiskFill, QueueBacklog, + latency-others)
# INFO alerts: 3 (budget tracking × 3 SLOs)
# Total: 18 rules
#
# Expected pages/ngày: ~1-2 (down from 9.6)
# Actionable rate: ~80%+ (up from 8%)
```

```
=== ALERT REVIEW CHECKLIST ===

Trước khi add bất kỳ alert rule nào, answer các câu hỏi sau:

1. "Nếu alert này bắn lúc 3AM, on-call engineer sẽ làm gì trong 5 phút đầu?"
   → Nếu không có câu trả lời rõ ràng → không phải PAGE alert
   → Nếu câu trả lời là "check dashboard" → có thể là TICKET hoặc INFO

2. "Alert này có ảnh hưởng đến user experience không?"
   → CPU 85% nhưng response time vẫn < 200ms → KHÔNG cần PAGE
   → Request error rate tăng → CÓ cần PAGE

3. "Alert này có thể tự recover không?"
   → Spike 2 phút rồi tự về bình thường → Tăng for: duration
   → Sustained > 15 phút → có thể cần alert

4. "Alert này có trùng với alert khác không?"
   → CPU cao + Memory cao + Pod restart → cùng 1 incident, chỉ cần Pod restart alert
   → Ưu tiên alert gần user nhất (outcome > symptom)

5. "Có runbook cụ thể cho alert này không?"
   → Nếu không có runbook → viết runbook trước khi enable alert
   → Runbook phải có: expected action, escalation path, expected resolution time

6. "Alert này có historical false positive rate > 10% không?"
   → Xem alert history 30 ngày qua
   → Nếu > 10% là noise → tune threshold hoặc delete

7. "Ai owns alert này? Ai sẽ respond?"
   → Alert không có owner = alert bị ignore
   → team label phải map vào specific on-call rotation
```

```
=== PHẦN C: TOIL REDUCTION ===

=== TOIL MATRIX (Impact × Effort) ===

Hiện tại per tháng:
  Restart order-worker:            15 min/ngày × 22 ngày = 330 phút (5.5h)
  Review noise alerts:             45 min/ngày × 22 ngày = 990 phút (16.5h)
  Manual deploy approvals:         20 min × 3/ngày × 22 ngày = 1320 phút (22h)
  DB credential rotation:          180 phút/quarter = 60 phút/tháng
  "Is system ok?" Slack responses: 30 min/ngày × 22 ngày = 660 phút (11h)
  Monthly capacity planning:       240 phút/tháng

Total toil: 330 + 990 + 1320 + 60 + 660 + 240 = 3,600 phút = 60 giờ/tháng
Giả sử 2 SRE, mỗi người 160h/tháng = 320h total
Toil % = 60/320 = 18.75% (OK nhưng còn nhiều room để cải thiện)

NHƯNG: Quality of toil quan trọng hơn quantity:
  - Review 990 phút noise alerts = mental burnout, không productive
  - Deploy approvals 1320 phút = chặn velocity của dev team

=== TOP 3 TOIL REDUCTION (Priority: Impact × Effort) ===

PRIORITY 1: Eliminate Alert Noise (Effort: Medium, Impact: Very High)
  Toil: 990 phút/tháng + mental health cost
  Solution: Implement SLO-based alerting (Exercise này!)
  Technical approach:
    1. Audit existing 312 rules → categorize (Week 1)
    2. Define 3-4 SLOs → create recording rules (Week 2)
    3. Deploy new 18 alert rules → shadow mode 1 tuần (Week 3)
    4. Delete old rules sau khi confirm (Week 4)
  ROI:
    Saved: 990 phút/tháng + reduced MTTAR
    Cost: 40 giờ engineer time (one-time)
    Payback: < 2 tháng

PRIORITY 2: Fix Memory Leak → Eliminate Restart Toil (Effort: High, Impact: High)
  Toil: 330 phút/tháng + risk of data loss if crash during processing
  Root cause: order-worker memory leak (cần profile)
  Technical approach:
    1. Add pprof endpoint: import _ "net/http/pprof"
    2. Profile memory: go tool pprof http://order-worker:6060/debug/pprof/heap
    3. Identify leak (likely: goroutine leak, unclosed DB connection, unbounded cache)
    4. Fix leak → write regression test
    Short-term bridge: HPA memory-based scaling + pod restart policy
  ROI:
    Saved: 330 phút/tháng permanently
    Also saved: Reduced incident risk from OOMKill in production

PRIORITY 3: Automate Deploy Approvals → CD Pipeline (Effort: High, Impact: Very High)
  Toil: 1320 phút/tháng + blocks dev velocity
  Solution: Automated deployment pipeline with quality gates
  Technical approach:
    1. Define deployment criteria as code:
       - Error budget remaining > 20%? → auto-approve
       - All unit tests pass? → auto-approve
       - Performance regression < 5%? → auto-approve
    2. Implement với GitHub Actions:
       # .github/workflows/deploy.yml
       - name: Check error budget
         run: |
           BUDGET=$(curl -s 'http://prometheus/api/v1/query' \
             --data-urlencode 'query=...' | jq '.data.result[0].value[1]')
           if (( $(echo "$BUDGET < 0.2" | bc -l) )); then
             echo "ERROR: Error budget < 20%, blocking deploy"
             exit 1
           fi
    3. Route only edge cases to human (breaking changes, budget < 10%)
  ROI:
    Saved: 1320 phút/tháng = 22 giờ
    Dev velocity: +3 deploy/ngày → có thể 2x với confidence
    Payback: < 1 tháng

=== KPI TARGETS ===

Current state:
  Total monthly hours: 320h (2 SRE × 160h)
  Toil: 60h = 18.75%
  Pages/ngày: 9.6
  MTTR: 2.4h

After 3-month improvement:
  Alert redesign savings:    16.5h/tháng
  Memory leak fix savings:    5.5h/tháng
  CD automation savings:     22h/tháng
  Total savings:             44h/tháng

New toil: 60 - 44 = 16h/tháng
New toil %: 16/320 = 5% (excellent! Target < 30%, we're at 5%)
  
Pages/ngày target: 1-2 (down from 9.6)
MTTR target: < 30 phút (down from 2.4h, because on-call not fatigued)
```

```yaml
# === BONUS: Terraform module cho alert rules ===

# modules/slo-alerts/variables.tf
variable "service_name" {
  description = "Name of the service being monitored"
  type        = string
}

variable "slo_target" {
  description = "SLO target as decimal (e.g., 0.999 for 99.9%)"
  type        = number
  default     = 0.999
}

variable "team_label" {
  description = "Team responsible for this service"
  type        = string
}

variable "runbook_base_url" {
  description = "Base URL for runbooks"
  type        = string
  default     = "https://runbooks.internal"
}

variable "environment" {
  description = "Environment (prod, staging, dev)"
  type        = string
  default     = "prod"
}

# modules/slo-alerts/main.tf
locals {
  error_budget = 1 - var.slo_target
}

resource "prometheus_rule_group" "slo_alerts" {
  name     = "${var.service_name}-slo-alerts"
  interval = "30s"

  rule {
    alert = "${var.service_name}SLOCritical"
    expr  = <<-EOT
      (
        (1 - sum(rate(http_requests_total{service="${var.service_name}",code!~"5.."}[5m]))
        / sum(rate(http_requests_total{service="${var.service_name}"}[5m])))
        / ${local.error_budget} > 14.4
      ) and (
        (1 - sum(rate(http_requests_total{service="${var.service_name}",code!~"5.."}[1h]))
        / sum(rate(http_requests_total{service="${var.service_name}"}[1h])))
        / ${local.error_budget} > 14.4
      )
    EOT
    for   = "2m"
    
    labels = {
      severity    = "page"
      team        = var.team_label
      environment = var.environment
    }
    
    annotations = {
      summary     = "${var.service_name} SLO critical burn rate"
      runbook_url = "${var.runbook_base_url}/${var.service_name}-slo-critical"
    }
  }
  
  # ... more rules
}

# Usage:
# module "checkout_slo_alerts" {
#   source           = "./modules/slo-alerts"
#   service_name     = "checkout-api"
#   slo_target       = 0.999   # 99.9%
#   team_label       = "payment"
#   environment      = "prod"
# }
```

</details>

