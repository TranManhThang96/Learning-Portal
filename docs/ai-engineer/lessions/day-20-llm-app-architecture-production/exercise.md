# Day 20 Exercise: Build LLM Orchestrator Skeleton

## Mục Tiêu Thực Hành

Hoàn thành bài này để bạn có một FastAPI skeleton production-style cho LLM app, dù provider hiện tại là mock. Sau lab, bạn cần chứng minh được:

- Request đi qua orchestrator thay vì gọi provider trực tiếp.
- Prompt được lấy theo `prompt_id` và `prompt_version`.
- Model router chọn provider theo `task` và tenant tier.
- Có timeout, retry và fallback.
- Có exact cache không leak giữa tenant.
- Có quota/rate limit theo tenant.
- Có audit event và metrics metadata.
- Có câu trả lời rõ: muốn production thật cần thay gì.

## Yêu Cầu Môi Trường

```bash
cd lessions/day-20-llm-app-architecture-production
pip install fastapi uvicorn pydantic
```

Không cần API key vì lab dùng mock providers.

## Exercise 1: Chạy Service

```bash
uvicorn day20_orchestrator:app --reload --port 8000
```

Kiểm tra health:

```bash
curl -s http://127.0.0.1:8000/health
```

Kết quả mong đợi:

```json
{"status":"ok"}
```

Ghi lại:

- Service start có lỗi không?
- Endpoint `/health` có trả status `ok` không?
- Bạn sẽ thêm readiness check nào nếu thay mock provider bằng provider thật?

## Exercise 2: Gọi Task `extract`

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{
    "tenant_id": "tenant_pro",
    "user_id": "user_123",
    "task": "extract",
    "message": "Khách bị tính phí hai lần sau khi nâng cấp gói.",
    "prompt_id": "support_triage",
    "prompt_version": "v1",
    "max_output_tokens": 256
  }'
```

Kiểm tra response có các field:

- `trace_id`.
- `answer`.
- `provider`.
- `model`.
- `cache_hit`.
- `fallback_used`.
- `retry_count`.
- `latency_ms`.
- `estimated_cost_usd`.
- `prompt_id`.
- `prompt_version`.

Câu hỏi:

1. Vì sao response cần `trace_id`?
2. Vì sao `prompt_version` nên xuất hiện trong response hoặc trace?
3. Vì sao `max_output_tokens` phải có giới hạn trên?

## Exercise 3: Kiểm Tra Cache Hit

Gọi lại đúng request ở Exercise 2.

Kết quả mong đợi:

- Lần đầu: `cache_hit=false`.
- Lần hai: `cache_hit=true`.
- `latency_ms` lần hai thấp hơn đáng kể.

Thử đổi `tenant_id` sang `tenant_enterprise` nhưng giữ nguyên message.

Câu hỏi:

1. Vì sao cache không nên hit giữa hai tenant?
2. Nếu response phụ thuộc permission của user, cache key cần thêm gì?
3. Vì sao cache key cần `prompt_version` và `model`?

## Exercise 4: Kiểm Tra Routing Theo Task

Gọi task `reasoning`:

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{
    "tenant_id": "tenant_enterprise",
    "user_id": "user_456",
    "task": "reasoning",
    "message": "Hãy phân tích trade-off giữa single provider và multi-provider cho app support enterprise.",
    "prompt_id": "assistant",
    "prompt_version": "v1",
    "max_output_tokens": 512
  }'
```

Ghi lại:

- Model nào được chọn?
- Vì sao tenant enterprise được dùng model mạnh hơn?
- Nếu tenant free gọi task `reasoning`, hệ thống nên degrade sang model nhỏ hay reject? Vì sao?

## Exercise 5: Kiểm Tra Fallback

Skeleton có endpoint debug để bật lỗi provider mock:

```bash
curl -s http://127.0.0.1:8000/debug/provider/mock-fast/fail \
  -H 'content-type: application/json' \
  -d '{"fail": true}'
```

Gọi lại task `extract` với message mới để tránh cache:

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{
    "tenant_id": "tenant_pro",
    "user_id": "user_123",
    "task": "extract",
    "message": "Khách muốn hủy gói vì không dùng tính năng analytics.",
    "prompt_id": "support_triage",
    "prompt_version": "v1"
  }'
```

Kết quả mong đợi:

- `fallback_used=true`.
- `retry_count` lớn hơn `0`.
- `provider` không phải `mock-fast`.

Tắt lỗi:

```bash
curl -s http://127.0.0.1:8000/debug/provider/mock-fast/fail \
  -H 'content-type: application/json' \
  -d '{"fail": false}'
```

Câu hỏi:

1. Fallback có thể làm response khác primary như thế nào?
2. Vì sao fallback cần golden set regression test?
3. Khi nào fallback nên trả degrade response thay vì gọi model khác?

## Exercise 6: Kiểm Tra Quota

Gọi endpoint metrics:

```bash
curl -s http://127.0.0.1:8000/metrics
```

Quan sát:

- Tổng request.
- Cache hit.
- Fallback count.
- Estimated cost.
- Quota usage theo tenant.

Thử giảm quota trong code hoặc gửi nhiều request để đạt giới hạn. Khi quota vượt, API phải trả `429`.

Câu hỏi:

1. Quota nên tính theo request, token hay USD?
2. Vì sao tenant free/pro/enterprise nên có quota khác nhau?
3. Khi gần hết budget, nên alert hay hard fail ngay?

## Exercise 7: Review Audit Log

Gọi:

```bash
curl -s http://127.0.0.1:8000/audit
```

Kiểm tra mỗi event có:

- `trace_id`.
- `tenant_id`.
- `user_id_hash`.
- `task`.
- `prompt_id`.
- `model`.
- `latency_ms`.
- `cache_hit`.
- `retry_count`.
- `fallback_used`.
- `estimated_cost_usd`.
- `status`.

Câu hỏi:

1. Vì sao audit log không nên lưu raw `message` mặc định?
2. Trường nào giúp debug cost spike?
3. Trường nào giúp debug provider outage?

## Exercise 8: Thay Mock Provider Bằng Provider Thật

Không cần làm trong ngày này nếu bạn chưa có API key. Hãy viết design trước:

```markdown
## Provider Adapter Plan

- Provider:
- SDK:
- Secret source:
- Timeout:
- Retryable errors:
- Non-retryable errors:
- Token usage field:
- Streaming support:
- Data retention policy:
- Fallback provider:
- Test cases:
```

Điều kiện tối thiểu trước khi gọi provider thật:

- API key đọc từ environment hoặc secret manager.
- Timeout bắt buộc.
- Không log raw prompt.
- Token usage được parse.
- Error provider được map về error type nội bộ.
- Unit test adapter với fake response.

## Deliverable Cuối Bài

Tạo một file ghi chú ngắn, ví dụ `day20_architecture_decision.md`, trả lời:

1. Architecture của bạn gồm component nào?
2. Prompt registry lưu metadata gì?
3. Router chọn model theo rule nào?
4. Timeout/retry/fallback policy là gì?
5. Cache key có những thành phần nào?
6. Quota và cost budget theo tenant ra sao?
7. Audit log lưu gì và không lưu gì?
8. Dashboard production cần metric nào?
9. Có dùng production được không? Nếu có thì cần điều kiện gì?

## Đáp Án Kỳ Vọng Ở Mức Senior SE

Một câu trả lời tốt không chỉ nói "có retry và cache". Nó phải nói được:

- Retry tối đa bao nhiêu lần, retry error nào, deadline tổng là gì.
- Cache key tránh leak tenant như thế nào.
- Fallback có regression risk gì.
- Model router giảm cost nhưng vẫn giữ quality ra sao.
- Audit log đủ debug nhưng không vi phạm privacy.
- Cost controls nằm ở request validation, router, quota, cache và alert.
- Production readiness phụ thuộc vào eval, observability, security và rollback, không phụ thuộc vào việc endpoint chạy được trên laptop.
