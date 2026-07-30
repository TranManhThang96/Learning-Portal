# Day 17 Document: LLM Fundamentals Production Reference

## 1. Glossary Nhanh

| Thuật ngữ | Giải thích ngắn | Lưu ý production |
|---|---|---|
| Token | Đơn vị text sau tokenizer | Cost/latency tính theo token, không phải word |
| Tokenizer | Bộ mã hóa text thành token IDs | Phải khớp với model version |
| Context window | Ngân sách token model xử lý | Kiểm tra cả context limit và output cap riêng của model |
| Logits | Điểm số model trả cho token kế tiếp | Decoding biến logits thành lựa chọn token |
| Temperature | Điều chỉnh độ ngẫu nhiên | Thấp cho stability, cao cho creativity |
| Top-p | Nucleus sampling theo probability mass | Dùng cẩn thận cùng temperature |
| Top-k | Giới hạn trong k token top | Phổ biến ở local runtime |
| Max tokens | Giới hạn output token | Kiểm soát cost và latency |
| SFT | Supervised fine-tuning theo instruction | Tăng khả năng follow instruction |
| RLHF | Reinforcement learning from human feedback | Align preference, không bảo đảm factuality |
| DPO | Direct Preference Optimization | Preference tuning đơn giản hơn RLHF truyền thống |
| Open-weight | Weights có thể tải về theo license | Không đồng nghĩa miễn phí hoặc production-safe |

## 2. Token Budget Template

Dùng template này trước khi thiết kế prompt hoặc endpoint.

```markdown
# Token Budget

Use case:
Model/context window:
Max output tokens reserved:
Safety margin:

| Component | Estimated tokens | Required? | Notes |
|---|---:|---|---|
| System prompt |  | yes |  |
| Developer/app instruction |  | yes |  |
| User input |  | yes |  |
| Chat history |  | no | Summary or last N turns |
| Retrieved documents |  | no | Top chunks after rerank |
| Tool results |  | no | Truncate or summarize |
| Output reservation |  | yes | max_tokens |
| Safety margin |  | yes | avoid overflow |
| Total |  |  | must be <= context window |

Overflow strategy:
- Drop:
- Summarize:
- Rerank:
- Reject with clear error:
```

Rule nhanh:

- Reserve output token trước khi nhét docs.
- Với RAG, ưu tiên ít chunk nhưng liên quan cao.
- Với chat, không giữ toàn bộ history mãi; dùng summary có timestamp/source.
- Với tool result lớn, summarize hoặc paginate.

## 3. Decoding Decision Table

| Use case | Temperature | Top-p | Max tokens | Extra controls |
|---|---:|---:|---:|---|
| JSON extraction | 0-0.1 | default/1.0 | Chặt | Schema validation, retry repair có giới hạn |
| Classification | 0 | default/1.0 | Rất thấp | Prefer enum output |
| Customer support answer | 0.2-0.4 | 0.9-1.0 | Vừa | Citation, policy source, refusal rule |
| Summarization | 0.2-0.5 | 0.9-1.0 | Theo length target | Check coverage |
| Brainstorm | 0.7-1.0 | 0.9-0.95 | Rộng hơn | Human selection |
| Code generation | 0.1-0.4 | 0.9-1.0 | Theo task | Tests, static analysis |

Không có config tốt tuyệt đối. Config đúng là config thắng trên evaluation set của use case cụ thể.

## 4. Hosted Vs Local Decision Record

```markdown
# LLM Model Decision Record

## Context

- Use case:
- Users:
- Data sensitivity:
- SLA:
- Expected traffic:
- Required languages:
- Expected output format:

## Options

| Option | Model/provider | Pros | Cons | Estimated cost | Estimated latency |
|---|---|---|---|---:|---:|
| Hosted strong model |  |  |  |  |  |
| Hosted small model |  |  |  |  |  |
| Local/open-weight model |  |  |  |  |  |

## Security and compliance

- Can data leave our infra:
- Retention policy:
- PII handling:
- Vendor review required:
- Open-weight license review required:

## Evaluation

- Golden set size:
- Quality metric:
- Format validity metric:
- Factuality/citation metric:
- Latency p50/p95:
- Cost per 1,000 requests:

## Decision

- Selected option:
- Why:
- Required guardrails:
- Fallback:
- Rollback:
- Review date:
```

## 5. Cost Worksheet

```text
requests_per_day = 50,000
avg_input_tokens = 1,200
avg_output_tokens = 250
retry_rate = 3%

daily_input_tokens = requests_per_day * avg_input_tokens * (1 + retry_rate)
daily_output_tokens = requests_per_day * avg_output_tokens * (1 + retry_rate)

daily_llm_cost =
  daily_input_tokens / 1_000_000 * input_price_per_1m
+ daily_output_tokens / 1_000_000 * output_price_per_1m
```

Ngoài token price, đừng quên:

- Embedding/retrieval cost nếu có RAG.
- Vector DB hoặc search infra.
- Observability storage.
- Human review.
- GPU/CPU serving nếu self-host.
- On-call và capacity planning.

## 6. Latency Breakdown Template

```markdown
# Latency Breakdown

| Step | p50 ms | p95 ms | Notes |
|---|---:|---:|---|
| API validation |  |  |  |
| Auth/quota |  |  |  |
| Retrieval/search |  |  |  |
| Reranking |  |  |  |
| Prompt build/token count |  |  |  |
| LLM prefill |  |  | Input length sensitive |
| LLM generation |  |  | Output length sensitive |
| Output validation |  |  |  |
| Total |  |  |  |
```

Optimization order thường hợp lý:

1. Cắt prompt boilerplate và retrieved docs dư.
2. Giảm output verbosity.
3. Dùng streaming cho UX.
4. Route task đơn giản sang small model.
5. Cache deterministic result hoặc stable prefix nếu provider/runtime hỗ trợ.
6. Với local model, benchmark batching, quantization và serving runtime.

## 7. Observability Fields

Log metadata, không log raw sensitive text mặc định.

```json
{
  "request_id": "req_123",
  "tenant_id": "tenant_hash",
  "use_case": "support_answer",
  "prompt_version": "support-v3",
  "model": "provider/model-version",
  "decoding": {
    "temperature": 0.2,
    "top_p": 1.0,
    "max_tokens": 512
  },
  "usage": {
    "input_tokens": 1432,
    "output_tokens": 218
  },
  "latency_ms": 2410,
  "finish_reason": "stop",
  "validation_status": "passed",
  "fallback_used": false,
  "cost_estimate": 0.0
}
```

Metrics tối thiểu:

- p50/p95/p99 latency.
- Input/output tokens per request.
- Cost per request và cost per tenant.
- Timeout/rate limit/provider error.
- Schema validation failure.
- Retry/fallback rate.
- User thumbs up/down hoặc domain-specific quality signal.

## 8. Output Contract Checklist

- Output có schema rõ không?
- Có enum thay vì free text cho class/action không?
- Có maximum length không?
- Có citation/evidence nếu factual QA không?
- Có policy khi thiếu thông tin không?
- Có validation trước khi lưu DB hoặc gọi tool không?
- Có retry repair không, và retry tối đa mấy lần?
- Có test case cho malformed output không?

## 9. Security Checklist

- [ ] Không đưa secret vào prompt.
- [ ] Không log raw prompt/response chứa PII mặc định.
- [ ] Có data retention policy cho provider hoặc self-host log.
- [ ] Tool permissions được scope theo user/tenant.
- [ ] Retrieved documents có permission filter trước khi đưa vào context.
- [ ] Output không được tự động thực hiện side effect high-risk.
- [ ] Có prompt injection tests.
- [ ] Có rate limit và quota.
- [ ] Có audit trail cho prompt/model/tool version.

## 10. Production Readiness Answer

LLM có thể dùng trong production khi được treat như một external probabilistic dependency:

- Có boundary rõ: input validation, token budget, output contract.
- Có quality control: golden set, eval trước khi đổi prompt/model.
- Có runtime control: timeout, retry, fallback, rollback.
- Có cost control: token logging, quota, budget alert.
- Có security control: PII/secret handling, permission-aware retrieval, tool guardrails.
- Có observability: latency, tokens, cost, error, quality feedback.

Nếu thiếu những điều kiện này, LLM vẫn có thể dùng cho prototype hoặc internal low-risk workflow, nhưng chưa nên tự động hóa quyết định quan trọng.

## 11. Nguồn Kỹ Thuật Đã Xác Minh

- Context7 `/websites/huggingface_co_transformers_main`: tokenization, truncation và generation controls của Transformers.
- Context7 `/websites/developers_openai_api`: Responses API, sampling parameters, structured outputs và tool calling.
- Hugging Face generation docs: <https://huggingface.co/docs/transformers/main/en/main_classes/text_generation>
- OpenAI Responses API reference: <https://developers.openai.com/api/reference/responses/overview>

Tên tham số không đồng nhất giữa runtime. Ví dụ OpenAI Responses API dùng `max_output_tokens`, trong khi Ollama `/api/generate` dùng `options.num_predict`. Khi đổi provider, adapter phải map về một field nội bộ ổn định thay vì để business code phụ thuộc tên SDK.
