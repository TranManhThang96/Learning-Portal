# Day 38: Document — Observability Instrumentation Reference

Tài liệu này là cheat sheet cho việc instrument service production-grade với metrics, structured logs và traces. Dùng nó khi review code service trước khi đưa vào dashboard/alerting ở các ngày sau.

## 1. Instrumentation Checklist

### Metrics

- [ ] Có request counter theo `service`, `method`, `route`, `status`.
- [ ] Có latency histogram với bucket phù hợp SLO.
- [ ] Có in-flight gauge nếu service có queue/concurrency quan trọng.
- [ ] Không dùng `user_id`, `request_id`, raw URL, email, IP làm metric label.
- [ ] Metric name theo convention: unit ở suffix, ví dụ `_seconds`, `_bytes`, `_total`.

### Logs

- [ ] Logs là JSON hoặc structured key-value.
- [ ] Mỗi log có `timestamp`, `level`, `service`, `message`, `trace_id`.
- [ ] Error log có `error`, `error_type`, operation/context đủ debug.
- [ ] Không log secret, token, password, raw PII.
- [ ] Sampling hoặc level control tồn tại cho endpoint high-volume.

### Traces

- [ ] Service nhận và propagate W3C `traceparent`.
- [ ] Span name dùng route template, không dùng raw URL có ID.
- [ ] Span có attributes cho dependency, status code, retry count.
- [ ] Sampling policy được đặt rõ, ví dụ head sampling 1-10% hoặc tail sampling cho error.
- [ ] Trace ID được đưa vào logs để correlate.

## 2. Naming Convention

| Signal | Pattern | Ví dụ |
|--------|---------|-------|
| Counter | `<domain>_<event>_total` | `http_requests_total` |
| Histogram | `<domain>_<measurement>_<unit>` | `http_request_duration_seconds` |
| Gauge | `<domain>_<state>` | `http_active_connections` |
| Log field | `snake_case` | `trace_id`, `duration_ms` |
| Span name | `<METHOD> <route_template>` | `GET /api/orders/{id}` |

## 3. RED Metrics Template

```go
http_requests_total{service="order-service",method="GET",route="/api/orders",status="200"}
http_request_duration_seconds_bucket{service="order-service",method="GET",route="/api/orders",le="0.25"}
http_active_requests{service="order-service"}
```

PromQL cơ bản:

```promql
# Request rate
sum(rate(http_requests_total{service="order-service"}[5m])) by (route)

# Error rate
sum(rate(http_requests_total{service="order-service",status=~"5.."}[5m]))
/
sum(rate(http_requests_total{service="order-service"}[5m]))

# p99 latency
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{service="order-service"}[5m])) by (le)
)
```

## 4. Log Schema Template

```json
{
  "timestamp": "2026-05-20T10:15:30Z",
  "level": "ERROR",
  "service": "order-service",
  "env": "production",
  "message": "order payment failed",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "operation": "POST /api/orders",
  "customer_tier": "enterprise",
  "duration_ms": 842,
  "error_type": "PaymentGatewayTimeout",
  "error": "upstream timeout after 800ms"
}
```

Không đưa vào log:

- `authorization` header.
- Session cookie.
- Password/API key.
- Full credit card, national ID, private key.
- Payload lớn không cần thiết.

## 5. Trace Attribute Reference

| Attribute | Ví dụ | Ghi chú |
|-----------|-------|---------|
| `service.name` | `order-service` | Bắt buộc để group traces |
| `deployment.environment` | `production` | Tách prod/staging |
| `http.route` | `/api/orders/{id}` | Không dùng raw path |
| `http.response.status_code` | `500` | Dùng chuẩn OpenTelemetry |
| `db.system` | `postgresql` | Cho dependency spans |
| `messaging.system` | `kafka` | Cho queue/pubsub |
| `retry.count` | `2` | Hữu ích khi debug retry storm |

## 6. Cardinality Guardrails

### Safe Labels

- `service`
- `env`
- `method`
- `route` đã normalize
- `status`
- `region`
- `cluster`

### Dangerous Labels

- `user_id`
- `request_id`
- `trace_id`
- raw `path`
- `email`
- `ip_address`
- exception message đầy đủ

Rule of thumb: nếu label value có thể tăng theo số user/request/order, không dùng làm metric label. Đưa nó vào logs hoặc trace attributes.

## 7. Debug Flow: "Có lỗi nhưng dashboard không thấy"

1. Xác nhận traffic có vào service:

```bash
curl -s http://localhost:8080/metrics | grep http_requests_total
```

2. Xác nhận Prometheus scrape target healthy:

```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health, lastError}'
```

3. Kiểm tra label mismatch:

```bash
curl -s 'http://localhost:9090/api/v1/series?match[]=http_requests_total' | jq '.data[0:5]'
```

4. Kiểm tra query window có quá ngắn không:

```promql
rate(http_requests_total[1m])
rate(http_requests_total[5m])
increase(http_requests_total[15m])
```

5. Correlate bằng trace ID trong logs:

```bash
docker compose logs app | grep '<trace-id>'
```

## 8. Production Readiness Questions

- Khi deploy version mới, dashboard có chỉ ra version nào gây lỗi không?
- Khi user report chậm, có phân biệt latency server-side, dependency-side và client-side không?
- Khi service không có traffic, alert có phân biệt "healthy nhưng idle" và "scrape mất dữ liệu" không?
- Khi log volume tăng gấp 10 lần, backend logging có sampling/retention policy không?
- Khi tracing bị tắt hoặc collector down, service có tiếp tục phục vụ request không?

## 9. Anti-patterns

- Chỉ có CPU/memory dashboard nhưng không có user-facing metrics.
- Log text tự do khiến không query được theo `trace_id`.
- Dùng p99 latency từ average thay vì histogram.
- Alert trên từng pod thay vì service-level symptom.
- Instrument mọi thứ nhưng không có owner duy trì dashboard và alert.

