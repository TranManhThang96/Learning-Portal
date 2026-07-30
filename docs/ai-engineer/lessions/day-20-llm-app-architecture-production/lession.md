# Day 20: LLM App Architecture cho Production

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Giải thích được vì sao LLM app production không phải chỉ là một API call tới model.
- Thiết kế được architecture gồm `API Gateway`, `LLM Orchestrator`, `Prompt Registry`, `Model Router`, `Provider Adapter`, `Cache`, `Quota`, `Audit Log` và `Observability`.
- Biết đặt timeout, retry, fallback, rate limit, queue và cache cho workload LLM.
- Biết thiết kế multi-tenancy để tránh leak cache, leak prompt, leak tool result và vượt quota giữa tenant.
- Biết kiểm soát cost bằng token budget, model routing, cache, quota, dashboard và alert.
- Build được FastAPI skeleton gần production với router, provider adapters, retry, timeout, fallback, cache, audit event và metrics metadata.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

LLM app production là một distributed system có dependency chậm, đắt tiền, không deterministic và có rủi ro security riêng. Nếu mỗi feature team gọi provider SDK trực tiếp, hệ thống sẽ nhanh chóng mất kiểm soát về prompt version, model version, cost, retry, data policy, audit và rollback.

Pattern thực tế hơn là tập trung LLM calls qua một `LLM Orchestrator` hoặc `LLM Gateway`. Component này chịu trách nhiệm build prompt theo version, chọn model, gọi provider adapter, enforce quota, cache, timeout, retry, fallback, log audit event và emit observability metadata.

## 1. Day 20 Nằm Ở Đâu Trong Phase 3

Day 17 giúp hiểu LLM fundamentals. Day 18 tập trung prompt engineering. Day 19 biến output thành contract bằng structured output và tool calling. Day 20 ghép các mảnh đó thành một backend architecture có thể vận hành.

```text
Day 17: model behavior và token
Day 18: prompt design
Day 19: structured output và tool boundary
Day 20: production architecture, reliability, cost, observability
Day 21: chọn Raw SDK, LangChain, LlamaIndex, LangGraph
```

Với góc nhìn Senior Software Engineer:

```text
LLM provider = external dependency có SLA, rate limit, cost và data policy
Prompt = versioned production artifact
Model = runtime dependency cần routing, rollback và evaluation
LLM response = untrusted output cần validation
Tool call = RPC đề xuất bởi model, app mới là nơi execute
```

## 2. Architecture Tổng Quan

Architecture tối thiểu cho production-style LLM app:

```text
Client
  -> API Gateway / Auth
  -> LLM Orchestrator
      -> Tenant Policy / Quota
      -> Prompt Registry
      -> Model Router
      -> Cache Layer
      -> Provider Adapter(s)
          -> Hosted LLM Provider
          -> Local LLM / vLLM / Ollama
      -> Tool Services
      -> Audit Log
      -> Observability
  -> Response
```

Map về backend system quen thuộc:

| Component | SE analogy | Trách nhiệm chính |
|---|---|---|
| API Gateway | Edge gateway | Auth, request size, tenant resolution, coarse rate limit |
| LLM Orchestrator | Application service | Điều phối prompt, cache, router, provider, retry, fallback |
| Prompt Registry | Config registry | Version prompt, owner, changelog, rollout, eval score |
| Model Router | Policy engine/load balancer | Chọn model theo task, tenant, latency, cost, quality, availability |
| Provider Adapter | DB/payment adapter | Chuẩn hóa SDK/API của từng provider |
| Tool Services | Internal microservices | Cung cấp capability có permission và audit |
| Cache Layer | Redis/CDN-like cache | Exact cache, tool result cache, retrieval cache, semantic cache |
| Audit Log | Compliance event log | Truy vết ai gọi gì, model nào, prompt version nào, tool nào |
| Observability | APM/tracing/metrics | Latency, token, cost, error, cache hit, retry, fallback |

Một nguyên tắc quan trọng: business code không nên biết chi tiết SDK của từng provider. Business code nên gọi interface nội bộ như `LLMClient.generate()` hoặc endpoint `/llm/chat`, còn gateway/orchestrator xử lý policy.

## 3. Orchestrator Và Gateway Khác Nhau Thế Nào?

Trong nhiều team, hai khái niệm này có thể gộp hoặc tách:

| Kiểu | Khi phù hợp | Trade-off |
|---|---|---|
| Chỉ có LLM Gateway mỏng | Nhiều service cần gọi LLM cùng một chuẩn adapter | Dễ dùng lại nhưng có thể thiếu business context |
| Orchestrator trong từng app | Workflow gắn chặt với domain, tool, user journey | Dễ tối ưu domain nhưng có nguy cơ duplicate policy |
| Gateway + Orchestrator | Platform AI chung cho nhiều app production | Tốn công thiết kế contract, version và ownership |

Khuyến nghị cho course này: bắt đầu bằng một `LLM Orchestrator` trong backend app, nhưng thiết kế provider adapter và policy đủ sạch để sau này tách thành gateway riêng nếu nhiều team cùng dùng.

## 4. Prompt Registry: Prompt Là Artifact

Prompt trong production không nên là string rải rác trong code. Nó cần metadata giống config hoặc API contract.

Prompt registry nên lưu:

- `prompt_id`, ví dụ `support_triage`.
- `version`, ví dụ `v1.3.0`.
- Template text và input variables.
- Owner/team chịu trách nhiệm.
- Model compatibility.
- Output schema version.
- Decoding config như temperature và output token cap.
- Eval score trên golden set.
- Changelog.
- Rollout status: `draft`, `canary`, `stable`, `deprecated`.

Ví dụ metadata:

```yaml
prompt_id: support_triage
version: v1.3.0
owner: support-platform
task: ticket_triage
compatible_models:
  - fast-classifier-v2
  - strong-reasoner-v1
schema_version: ticket_triage.v2
rollout: canary
eval:
  golden_set: support_tickets_2026_04
  exact_json_rate: 0.992
  priority_macro_f1: 0.87
```

Trace log và cache key nên luôn chứa `prompt_id`, `prompt_version`, `schema_version` và `model_id`. Nếu không, khi output thay đổi bạn sẽ không biết nguyên nhân là prompt, model, schema, data hay tool.

## 5. Model Router

Model router chọn model dựa trên policy, không dựa trên cảm tính. Signal thường dùng:

- Task type: chat, extraction, classification, reasoning, summarization, code.
- Tenant tier: free, pro, enterprise.
- SLO: latency target, availability target.
- Cost budget: cost/request, daily budget, monthly budget.
- Data policy: provider có được xử lý PII không, region nào, retention ra sao.
- Quality requirement: cần model mạnh hay model nhỏ là đủ.
- Context length: input dài hay ngắn.
- Availability: provider đang lỗi, 429 hoặc p95 quá cao.

Ví dụ routing rule:

| Task | Primary model | Fallback | Lý do |
|---|---|---|---|
| Classification/extraction ngắn | Small/cheap model | Strong model hoặc provider khác | Output ngắn, schema rõ, cost thấp |
| Reasoning phức tạp | Strong model | Strong model provider khác | Chất lượng quan trọng hơn cost |
| Enterprise sensitive data | Provider có data policy phù hợp hoặc local model | Degrade mode/manual review | Privacy và compliance |
| High throughput FAQ | Cheap hosted model + cache | Local vLLM | Tối ưu cost/latency |
| Long report async | Strong model qua queue | Retry later/manual review | Không nên block request realtime |

Fallback không miễn phí. Model fallback có thể khác format, chất lượng, latency và safety behavior. Vì vậy fallback cần được test bằng golden set riêng, không chỉ test "có trả response không".

## 6. Provider Adapters

Provider adapter che giấu khác biệt giữa SDK/API:

```python
class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        ...
```

Adapter nên chuẩn hóa:

- Input messages hoặc prompt.
- `temperature`, `max_output_tokens`, `response_format`.
- Timeout.
- Error type: rate limit, timeout, provider unavailable, invalid request.
- Token usage.
- Model/provider metadata.
- Streaming hoặc non-streaming contract.

Không nên để mỗi feature team tự gọi SDK provider riêng vì các vấn đề sau:

- Khó audit cost theo tenant/team/feature.
- Khó enforce data policy và PII logging.
- Khó rollback prompt/model.
- Retry/fallback mỗi nơi một kiểu.
- Observability không đồng nhất.
- Secret bị copy nhiều nơi.

## 7. Reliability: Timeout, Retry, Fallback, Circuit Breaker

LLM dependency có failure mode riêng:

- `429` do rate limit provider.
- `5xx` hoặc provider outage.
- Timeout hoặc streaming bị ngắt.
- Output sai schema.
- Tool call fail.
- Prompt quá dài làm request bị reject.
- Cost spike do output quá dài hoặc retry quá nhiều.

Pattern nên có:

| Pattern | Dùng khi | Lưu ý production |
|---|---|---|
| Timeout | Mọi LLM/tool call | Timeout nên nhỏ hơn API deadline tổng |
| Retry with backoff | Transient `429`, `5xx`, network error | Giới hạn attempt, thêm jitter, không retry vô hạn |
| Fallback model/provider | Primary lỗi hoặc quá chậm | Cần eval chất lượng fallback |
| Circuit breaker | Provider lỗi liên tục | Tránh làm nghẽn toàn hệ thống |
| Queue | Job dài, batch, report | Có deadline, max depth, retry policy |
| Bulkhead | Tách tenant/task quan trọng | Một tenant không được làm nghẽn tenant khác |
| Cancellation | Client disconnect hoặc deadline hết | Tránh đốt token vô ích |

Quy tắc retry: chỉ retry operation an toàn. Với tool có side effect như gửi email, tạo refund, update ticket, cần idempotency key và audit log trước khi retry.

`Request queue` là hàng đợi đặt job giữa API và worker. API có thể trả `job_id` sớm, worker xử lý LLM call dài ở background. Queue giúp hấp thụ traffic burst và bảo vệ provider, nhưng phải có max depth, per-tenant fairness, deadline, dead-letter queue và backpressure; nếu không, hệ thống chỉ chuyển lỗi timeout thành backlog vô hạn.

## 8. Cache: Exact, Tool Result, Retrieval, Semantic

Cache có thể giảm latency và cost rất mạnh, nhưng sai cache có thể gây data leak.

| Cache | Key | Nên dùng khi | Risk |
|---|---|---|---|
| Exact prompt cache | Hash của tenant, prompt version, schema, model, normalized input | FAQ, deterministic extraction, ticket triage lặp | PII, invalidation, prompt/model drift |
| Tool result cache | tenant, tool name, normalized args, permission context | Lookup order/profile ít đổi | Stale data, permission drift |
| Retrieval cache | tenant, query, index version, ACL hash | RAG traffic lặp | Document version drift, ACL leak |
| Semantic cache | tenant, embedding(query), threshold, prompt version | FAQ public/high traffic | Sai ngữ cảnh, permission-sensitive answer |

Production rule: cache key phải chứa `tenant_id`, `prompt_id`, `prompt_version`, `schema_version`, `model_id` và permission context nếu output phụ thuộc quyền truy cập.

Cache key cũng phải chứa mọi config làm thay đổi output, ví dụ `temperature`, output token cap và tool/retrieval version. Không cache fallback response dưới key của primary model nếu bạn muốn request mới kiểm tra primary đã phục hồi; hoặc phải định nghĩa rõ cache theo logical route thay vì physical model.

Không cache raw prompt/response chứa PII nếu chưa có policy rõ. Có thể chỉ cache metadata hoặc cache sau khi redaction.

## 9. Multi-tenancy Và Quota

Tenant isolation phải xuyên suốt:

```text
auth token
  -> tenant_id
  -> quota bucket
  -> prompt access
  -> cache namespace
  -> tool permission
  -> provider key/policy
  -> audit log partition
```

Các lỗi production thường gặp:

- Cache key thiếu `tenant_id`, tenant A nhận câu trả lời của tenant B.
- Tool service chỉ check user login nhưng không check tenant permission.
- Log raw prompt chứa PII của nhiều tenant vào cùng một index không có access control.
- Tenant free dùng model enterprise vì router không check tier.
- Provider key dùng chung làm một tenant tiêu hết quota của tenant khác.

Quota nên có nhiều lớp:

- Requests/minute theo tenant và user.
- Tokens/day hoặc cost/day theo tenant.
- Concurrent requests theo tenant.
- Max input tokens và max output tokens theo endpoint/task.
- Budget alert trước khi hard limit.

### Secret management

`Secret` là credential nhạy cảm như provider API key, database password hoặc signing key. `Secret manager` là hệ thống lưu, phân quyền, rotate và audit việc đọc secret; environment variable chỉ là cơ chế đưa secret vào process, không phải nơi quản trị secret đầy đủ.

Rule production:

- Không hardcode secret trong source, prompt, image hoặc config commit vào Git.
- Mỗi environment/provider dùng credential riêng, scope tối thiểu.
- Adapter đọc secret lúc runtime; business code không nhận hoặc log secret.
- Có rotation/revocation runbook và audit ai/service nào đã truy cập.
- Không gửi secret vào model context, kể cả với mục đích "debug".

## 10. Audit Log Và Observability

Audit log trả lời câu hỏi: "Ai đã làm gì, lúc nào, với model/prompt/tool nào, tốn bao nhiêu, kết quả policy ra sao?"

Audit event tối thiểu:

```json
{
  "trace_id": "uuid",
  "timestamp": "2026-05-10T09:30:00Z",
  "tenant_id": "tenant_a",
  "user_id_hash": "hash",
  "endpoint": "/chat",
  "task": "extract",
  "prompt_id": "support_triage",
  "prompt_version": "v1.3.0",
  "schema_version": "ticket_triage.v2",
  "provider": "provider_a",
  "model": "fast-classifier-v2",
  "input_tokens": 230,
  "output_tokens": 80,
  "estimated_cost_usd": 0.0012,
  "latency_ms": 842,
  "cache_hit": false,
  "retry_count": 1,
  "fallback_used": false,
  "tool_names": ["lookup_order"],
  "policy_decision": "allow",
  "error_code": null
}
```

Observability nên tách metric, log và trace:

- Metrics: p50/p95/p99 latency, error rate, timeout rate, fallback rate, cache hit rate, token/request, cost/tenant.
- Logs: structured event, error details, policy decision, không log raw PII mặc định.
- Traces: span cho gateway, prompt build, cache lookup, provider call, tool call, validation, response.

Dashboard production nên có ít nhất:

- Latency theo endpoint/task/model/provider.
- Cost theo tenant/team/feature/model.
- Error rate theo provider và error type.
- Fallback và retry rate.
- Cache hit rate.
- Top tenants theo token/cost.

## 11. Cost Controls

Cost LLM thường tăng vì input dài, output dài, retry, tool loop và model quá mạnh cho task đơn giản.

Control nên đặt ở nhiều điểm:

- Max input length và max output tokens.
- Router dùng model nhỏ cho task đơn giản.
- Exact cache cho request lặp.
- Semantic cache chỉ khi có ACL và threshold tốt.
- Per-tenant budget và alert.
- Daily/monthly hard cap.
- Reject hoặc degrade khi budget hết.
- Log token usage và estimated cost từng request.
- Golden set để đo chất lượng trước khi đổi sang model rẻ hơn.

Ví dụ policy:

| Tenant tier | Model default | Daily budget | Max output tokens | Fallback khi hết budget |
|---|---|---:|---:|---|
| Free | small | 1 USD | 256 | Trả lỗi quota hoặc template response |
| Pro | balanced | 20 USD | 1024 | Chuyển sang small model |
| Enterprise | strong theo task | Contract-specific | 2048+ | Queue/manual review/degrade mode |

## 12. Performance Considerations

Latency tổng thường là:

```text
auth
+ request validation
+ prompt build
+ cache lookup
+ provider queueing
+ time to first token
+ output generation
+ tool calls
+ validation/postprocess
+ logging
```

Điểm cần nhớ:

- Output token là latency driver lớn. Sinh 1000 token chậm hơn 100 token nhiều lần.
- Streaming giảm perceived latency nhưng không giảm total compute.
- Retry/fallback có thể làm p95/p99 tăng mạnh dù p50 vẫn đẹp.
- Tool loop nhân số LLM call lên nhiều lần.
- Cache hit rate 20-40% có thể giảm cost đáng kể với FAQ workload.
- Queue giúp bảo vệ API realtime nhưng cần deadline, max depth và backpressure.
- Provider adapter phải expose token usage để tính cost chính xác hơn estimate.

Latency budget mẫu:

| Stage | Budget v1 |
|---|---:|
| Auth/API validation | 20ms |
| Tenant policy/quota | 10ms |
| Prompt build/cache lookup | 30ms |
| LLM first response | 800-2000ms |
| Tool call | 100-500ms |
| Postprocess/validation | 20ms |
| Audit log async enqueue | 5-20ms |
| p95 target non-streaming | 3-5s |

## 13. Trade-offs

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Production note |
|---|---|---|---|
| Raw SDK trực tiếp | POC, script nhỏ, một team | Nhiều team, nhiều provider, cần audit | Nhanh nhưng governance yếu |
| LLM Gateway | Nhiều app/team cùng gọi LLM | Prototype một ngày | Tăng platform work nhưng giảm risk |
| Single provider | SLO chấp nhận, team nhỏ, cần đơn giản | Cần high availability/vendor hedge | Ít ops hơn, dễ optimize |
| Multi-provider | Cần fallback, cost routing, negotiation | Output consistency cực quan trọng | Cần eval từng provider |
| Sync request | Output ngắn, SLA < 5s | Job dài, multi-step agent | Dễ API/UX hơn |
| Async queue | Batch, report, workflow dài | Chat realtime cần token streaming | Cần job state và retry policy |
| Exact cache | Request lặp, deterministic | Input PII/dynamic cao | An toàn hơn semantic cache |
| Semantic cache | FAQ high traffic | Permission-sensitive answer | Cần ACL, threshold và eval |
| Local model | Privacy, cost at scale, predictable workload | Traffic thấp, thiếu GPU ops | Cần serving stack và model ops |

## 14. FastAPI Skeleton Trong Bài

Folder này có file [day20_orchestrator.py](day20_orchestrator.py) minh họa một orchestrator có:

- Pydantic request/response schema.
- Prompt registry in-memory.
- Model router theo task và tenant tier.
- Provider adapter protocol với mock providers.
- Timeout, retry with backoff và fallback.
- Exact cache có tenant namespace.
- Quota theo tenant.
- Audit event in-memory.
- Metrics endpoint đơn giản.

Chạy local:

```bash
cd lessions/day-20-llm-app-architecture-production
pip install fastapi uvicorn pydantic
ENABLE_DEBUG_ENDPOINTS=1 uvicorn day20_orchestrator:app --reload --port 8000
```

`ENABLE_DEBUG_ENDPOINTS=1` chỉ dành cho fault-injection lab. Không bật endpoint thay đổi trạng thái provider trên môi trường public.

Gọi API:

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{
    "tenant_id": "tenant_pro",
    "user_id": "user_123",
    "task": "extract",
    "message": "Khách bị tính phí hai lần sau khi nâng cấp gói.",
    "prompt_id": "support_triage",
    "prompt_version": "v1"
  }'
```

Mục tiêu của skeleton không phải là gọi model thật, mà là làm rõ boundary production. Khi thay mock provider bằng OpenAI, Anthropic, Gemini, local vLLM hoặc provider nội bộ, bạn giữ lại orchestrator policy.

Các giới hạn cố ý của skeleton:

- Cache, quota, audit và provider state nằm trong memory, không chia sẻ giữa nhiều process và mất khi restart.
- Chưa có auth/gateway thật, distributed rate limiter, durable audit sink, secret manager, circuit breaker hoặc queue.
- Token count/cost chỉ là estimate; adapter thật phải lấy usage từ provider.
- Structured output mới minh họa một schema đơn giản; production cần schema registry và semantic validation.

Vì vậy file này là executable architecture lab, không phải service có thể deploy nguyên trạng.

## 15. Dùng Được Trong Production Không?

Có, architecture này dùng được trong production nếu đáp ứng các điều kiện sau:

- Tất cả LLM calls đi qua gateway/orchestrator hoặc một interface nội bộ có policy đồng nhất.
- Prompt, model, schema và tool đều có version, owner, changelog, eval và rollback.
- Có timeout, retry limit, fallback policy, circuit breaker hoặc degrade mode.
- Có quota và budget theo tenant/user/team.
- Cache key có tenant, prompt version, schema version, model id và permission context.
- Không log raw PII mặc định; có redaction, retention và access control rõ.
- Tool execution có allowlist, auth, least privilege và idempotency với side effect.
- Observability đo được latency, token, cost, retry, fallback, cache hit và error rate.
- Thay đổi prompt/model/provider phải chạy golden set và canary trước khi rollout rộng.

Không nên gọi là production-ready nếu chỉ có một endpoint gọi SDK provider trực tiếp, không timeout, không audit, không quota, không prompt version và không biết cost/request.

## 16. Checklist Cuối Bài

- [ ] Vẽ được architecture LLM app production.
- [ ] Giải thích được vai trò của orchestrator/gateway.
- [ ] Thiết kế được prompt registry có version và eval metadata.
- [ ] Thiết kế được model router theo task, tenant, cost và SLO.
- [ ] Có provider adapter thay vì gọi SDK rải rác.
- [ ] Có timeout, retry, fallback và retry budget.
- [ ] Có cache key không leak giữa tenant.
- [ ] Có quota, rate limit và cost budget theo tenant.
- [ ] Có audit event và metrics cần thiết.
- [ ] Trả lời được production readiness với điều kiện cụ thể.
