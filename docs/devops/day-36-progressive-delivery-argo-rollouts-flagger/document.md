# Day 36: Document — Progressive Delivery Checklist & Runbooks

Tài liệu này dùng như checklist vận hành khi đưa Argo Rollouts hoặc Flagger vào production. Lesson giải thích concept; file này tập trung vào quyết định, guardrail và runbook.

## 1. Pre-rollout Checklist

### Application Readiness

- [ ] Service có readiness probe phản ánh đúng khả năng nhận traffic thật, không chỉ process còn sống.
- [ ] Liveness probe không quá nhạy khiến canary bị restart vì dependency chậm tạm thời.
- [ ] App expose version/build metadata qua `/health`, `/version`, logs hoặc metric label có cardinality thấp.
- [ ] Backward compatibility được kiểm tra cho API contract, database schema, message schema và cache key.
- [ ] Feature flag hoặc kill switch tồn tại cho thay đổi có rủi ro business logic.

### Metric Readiness

- [ ] Có RED metrics: request rate, error rate, duration.
- [ ] Có dependency metrics cho database, cache, queue, external API nếu release phụ thuộc mạnh vào chúng.
- [ ] Analysis query loại trừ client-side noise hợp lý, ví dụ không tính toàn bộ `4xx` như server error.
- [ ] Query có đủ traffic tối thiểu trước khi quyết định promote.
- [ ] Dashboard có thể so sánh stable vs canary theo cùng time window.

### Traffic Routing Readiness

- [ ] Ingress/service mesh/ALB controller hỗ trợ traffic weight chính xác.
- [ ] Stable service và canary service selector không bị overlap sai.
- [ ] Sticky session/cookie behavior được đánh giá nếu app có session affinity.
- [ ] Rollout step không làm capacity tăng vượt quota cluster.
- [ ] Có rollback path thủ công nếu controller hoặc router gặp lỗi.

## 2. Rollout Policy Template

| Mức rủi ro | Step đề xuất | Pause | Analysis | Ghi chú |
|------------|--------------|-------|----------|---------|
| Low | 20% -> 50% -> 100% | 2-5 phút | error rate, p95 latency | Dùng cho thay đổi UI/API nhỏ |
| Medium | 5% -> 20% -> 50% -> 100% | 5-10 phút | RED + dependency metrics | Dùng cho logic nghiệp vụ quan trọng |
| High | 1% -> 5% -> 10% -> 25% -> 50% -> 100% | 10-30 phút | RED + SLO burn + business KPI | Dùng cho payment, auth, data mutation |
| Critical | dark launch + manual approval + canary nhỏ | theo change window | full dashboard review | Nên có war room và rollback owner |

Nguyên tắc: rollout càng chậm thì giảm blast radius nhưng tăng thời gian tồn tại nhiều version. Không chọn step chỉ vì "an toàn"; chọn theo rủi ro, traffic volume và khả năng rollback của thay đổi.

## 3. Analysis Metric Reference

### Error Rate

```promql
sum(rate(http_requests_total{
  service="order-service",
  status=~"5.."
}[5m]))
/
sum(rate(http_requests_total{
  service="order-service"
}[5m]))
```

Threshold khởi đầu: `< 0.01` cho service thông thường, `< 0.001` cho payment/auth nếu SLO yêu cầu cao.

### P99 Latency

```promql
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{
    service="order-service"
  }[5m])) by (le)
)
```

So sánh với baseline stable sẽ tốt hơn dùng threshold cố định nếu traffic thay đổi mạnh theo giờ.

### Minimum Request Volume

```promql
sum(increase(http_requests_total{
  service="order-service"
}[5m]))
```

Nếu volume quá thấp, analysis pass không có ý nghĩa thống kê. Với endpoint ít traffic, dùng synthetic checks hoặc manual approval.

## 4. Runbook: Rollout Stuck ở `Progressing`

### Dấu hiệu

- `kubectl argo rollouts get rollout <name> -n <ns>` đứng ở một step quá lâu.
- Pod canary ready nhưng traffic weight không đổi.
- Events có lỗi từ ingress/service mesh controller.

### Kiểm tra

```bash
kubectl argo rollouts get rollout demo-app -n demo
kubectl describe rollout demo-app -n demo
kubectl get analysisrun -n demo
kubectl describe analysisrun -n demo <analysisrun-name>
kubectl get ingress,svc,rs,pod -n demo -l app=demo-app
kubectl get events -n demo --sort-by=.lastTimestamp
```

### Quyết định

- Nếu analysis query lỗi do Prometheus/query syntax: sửa `AnalysisTemplate`, retry rollout.
- Nếu pod canary không ready: debug pod như deployment thường, không promote.
- Nếu traffic router không update weight: kiểm tra ingress/service mesh controller trước khi retry.
- Nếu user impact tăng: `kubectl argo rollouts abort <name> -n <ns>`.

## 5. Runbook: Automated Rollback Không Mong Muốn

### Dấu hiệu

- Rollout chuyển `Degraded` dù dashboard chính không thấy outage.
- Analysis metric failed nhưng canary logs không có lỗi rõ ràng.
- Error budget burn tăng do dependency chung, không phải version mới.

### Kiểm tra

```bash
kubectl argo rollouts get rollout demo-app -n demo
kubectl describe analysisrun -n demo <analysisrun-name>
kubectl logs -n demo -l app=demo-app --since=15m
```

Đối chiếu:

- Canary traffic có đủ sample size không?
- Query có phân biệt stable/canary không?
- Có incident dependency cùng thời điểm không?
- Threshold có quá thấp so với normal variance không?

### Fix dài hạn

- Thêm `minimum request volume`.
- Dùng multiple metrics thay vì một metric đơn lẻ.
- Tách alert user-impact khỏi alert canary-analysis.
- Gắn deployment annotation lên Grafana để correlate với metrics.

## 6. Emergency Rollback Checklist

- [ ] Xác nhận version stable gần nhất và image digest.
- [ ] Abort rollout: `kubectl argo rollouts abort <name> -n <ns>`.
- [ ] Nếu abort không đủ, rollback revision: `kubectl argo rollouts undo <name> -n <ns>`.
- [ ] Verify traffic về stable: kiểm tra router weight, pod labels, logs và RED metrics.
- [ ] Freeze deploy pipeline cho service bị ảnh hưởng.
- [ ] Tạo incident note: timeline, metric failed, blast radius, mitigation, owner follow-up.

## 7. Argo Rollouts vs Flagger Decision Matrix

| Context | Nên chọn | Lý do |
|---------|----------|-------|
| Team dùng Argo CD làm GitOps chính | Argo Rollouts | Workflow và UI thống nhất với Argo ecosystem |
| Team dùng Flux CD | Flagger | Native hơn với Flux và GitOps reconciliation |
| Cần dashboard rollout trực quan cho developer | Argo Rollouts | Có plugin và dashboard riêng |
| Muốn giữ `Deployment` gốc, ít thay resource model | Flagger | Bọc thêm `Canary` CRD quanh `Deployment` |
| Cần A/B testing/header routing phức tạp | Tùy router | Quyết định theo Istio/NGINX/ALB capability hơn là tool |

## 8. Production Guardrails

- Không dùng progressive delivery để che lấp thiếu automated test. Canary giảm blast radius, không thay thế test.
- Không auto-promote khi metrics source đang down hoặc stale.
- Không dùng metric label có cardinality cao như `user_id`, `request_id`, raw URL path.
- Không rollout database migration destructive cùng lúc với app canary.
- Không để canary chạy quá lâu nếu hai version xử lý data khác nhau.
- Luôn có manual override nhưng audit mọi lần override.

