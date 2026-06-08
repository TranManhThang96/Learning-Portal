# Day 17: LLM Fundamentals

## Mục tiêu

Sau bài này, bạn cần làm được các việc sau:

- Hiểu LLM sinh output bằng cơ chế `next-token prediction`, không phải truy vấn một database sự thật tuyệt đối.
- Giải thích được `tokenization`, `token IDs`, `logits`, `probability distribution`, `context window` và `decoding`.
- Phân biệt `pre-training`, `supervised fine-tuning` (`SFT`) và `RLHF` hoặc `preference tuning`.
- Biết tính token budget cho một request gồm system prompt, user input, chat history, retrieved documents, tool results và output.
- Chọn được `temperature`, `top_p`, `top_k`, `max_tokens`, `stop sequences` theo từng use case.
- So sánh `hosted closed model` và `local/open-weight model` theo quality, cost, latency, privacy, security, compliance và vận hành.
- Trả lời rõ: LLM dùng được trong production không, và cần điều kiện gì.

## TL;DR

LLM là một runtime xác suất: nó nhận context, biến text thành token, dự đoán token tiếp theo, rồi lặp lại cho đến khi dừng. Khả năng chat tốt đến từ `SFT` và `preference tuning`; kiến thức rộng đến từ `pre-training`; nhưng factual correctness trong production vẫn cần retrieval, tool, validation, eval và monitoring.

Quyết định production không nên chỉ hỏi "model nào thông minh nhất". Cần hỏi thêm: request tốn bao nhiêu token, p95 latency là bao nhiêu, data có được gửi ra provider không, output có schema validate được không, model upgrade có golden set không, và khi provider lỗi thì fallback thế nào.

## 1. Day 17 Nằm Ở Đâu Trong Khóa Học

Day 9-16 đã xây nền tảng neural network, NLP, tokenizer, attention, Transformer và fine-tune classifier. Day 17 mở Phase 3: LLM Application Engineering.

```text
Day 14: Transformer architecture
Day 15: Hugging Face ecosystem
Day 16: fine-tune classifier
Day 17: LLM runtime fundamentals
Day 18: prompt engineering
Day 19: structured output and function calling
Day 20: LLM app architecture for production
```

Với góc nhìn Senior Software Engineer:

| LLM concept | SE analogy | Production implication |
|---|---|---|
| Prompt | Request contract | Version, test và rollback như API contract |
| Tokenizer | Parser/encoder | Đổi tokenizer có thể đổi behavior |
| Model weights | Runtime artifact | Pin model ID/version, có release note |
| Context window | Request payload limit | Cần budget cho input, retrieved docs và output |
| Decoding params | Runtime config | Thay đổi cần eval, log và canary |
| Output | External service response | Không tin raw text; cần parse, validate, guardrail |
| Evaluation set | Test suite xác suất | Bắt regression khi đổi prompt/model |

## 2. LLM Sinh Text Như Thế Nào

Flow inference cơ bản:

```text
text prompt
  -> tokenizer
  -> token IDs
  -> model forward pass
  -> logits cho token kế tiếp
  -> decoding chọn token
  -> append token vào context
  -> lặp lại đến max_tokens/stop/end token
```

Ví dụ rất đơn giản:

```text
Prompt: "Thủ đô của Việt Nam là"
Token tiếp theo có xác suất cao: " Hà", " thủ", " thành", ...
Model chọn " Hà"
Context mới: "Thủ đô của Việt Nam là Hà"
Token tiếp theo có xác suất cao: " Nội", ...
```

Điểm quan trọng: model không "lookup" câu trả lời trong database. Nó học distribution từ training data và sinh token hợp lý theo context. Vì vậy output có thể đúng, sai, thiếu nguồn, hoặc nghe rất tự tin dù không có căn cứ.

### Logits, probability và hallucination

Model trả về `logits`: điểm số chưa chuẩn hóa cho từng token trong vocabulary. Decoding chuyển logits thành probability distribution rồi chọn token.

Hallucination xảy ra khi chuỗi token nghe hợp lý về mặt ngôn ngữ nhưng không đúng với sự thật hoặc không được hỗ trợ bởi dữ liệu trong context. Trong production, hallucination không được giải quyết bằng "prompt hay hơn" một cách tuyệt đối; thường cần kết hợp:

- Retrieval từ nguồn đã kiểm soát.
- Tool/API để lấy dữ liệu realtime.
- Citation hoặc evidence.
- Output validation.
- Human review cho workflow rủi ro cao.
- Golden evaluation set để đo lỗi theo domain.

## 3. Tokenization: Vì Sao Token Không Phải Word

Tokenizer biến text thành các đơn vị mà model hiểu được. Token có thể là một từ, một phần của từ, khoảng trắng, dấu câu hoặc byte-level fragment.

```text
"AI Engineer" -> ["AI", " Engineer"] hoặc token IDs tương ứng
"không" -> có thể là một token hoặc nhiều subword tùy tokenizer
"customer_id=12345" -> thường bị tách thành nhiều token
```

Tác động production:

- Cùng một câu có thể tốn token khác nhau giữa model A và model B.
- Tiếng Việt, code, JSON, log line và text có nhiều ký tự đặc biệt có thể token hóa kém hơn English prose.
- Cost thường tính theo input token và output token.
- Latency tăng khi input dài và output dài.
- Truncation sai có thể cắt mất instruction, constraint hoặc dữ liệu quan trọng.

Rule thực tế: luôn đo token count bằng tokenizer đúng của model đang dùng, không ước lượng bằng số từ.

## 4. Training Pipeline: Pre-training, SFT, RLHF Và Preference Tuning

| Stage | Model học gì | Input điển hình | Tác động đến application |
|---|---|---|---|
| `Pre-training` | Predict next token trên corpus rất lớn | Web text, code, books, mixed data | Ngôn ngữ, pattern, kiến thức rộng, khả năng code/reasoning nền |
| `Supervised fine-tuning` (`SFT`) | Follow instruction qua cặp prompt/answer | Instruction dataset, chat transcript đã curate | Biết trả lời dạng assistant, tuân thủ format tốt hơn |
| `RLHF` | Tối ưu theo human preference | Ranking/preference label của con người | Output helpful/harmless hơn, style ổn hơn |
| `RLAIF` | Preference từ AI feedback | AI-generated preference | Scale rẻ hơn human label, vẫn cần kiểm định |
| `DPO` và preference tuning khác | Học trực tiếp từ cặp chosen/rejected | Chosen answer vs rejected answer | Pipeline đơn giản hơn RL truyền thống, hữu ích khi align model theo domain |

Nhầm lẫn phổ biến:

- `Pre-training` không bảo đảm model biết mọi sự thật mới nhất.
- `SFT` không tự biến model thành domain expert nếu dữ liệu instruction không đủ.
- `RLHF` không biến model thành source of truth; nó làm output hợp preference hơn.
- Fine-tune không phải giải pháp mặc định cho factual knowledge. Với dữ liệu thay đổi thường xuyên, RAG hoặc tool call thường đúng hơn.

## 5. Context Window Và Token Budget

`Context window` là ngân sách token model có thể xử lý cho một request/conversation state. Với nhiều API, input và output cùng chia sẻ một giới hạn tổng; một số model/provider còn công bố thêm output cap riêng. Vì vậy luôn đọc contract của đúng model: `input_tokens + reserved_output_tokens` phải nằm trong context limit, đồng thời `reserved_output_tokens` không được vượt output cap riêng.

Token budget nên tính như sau:

```text
system prompt
+ developer/app instruction
+ prompt template
+ chat history hoặc summary
+ retrieved documents
+ user input
+ tool results
+ reserved output tokens
<= model context window
```

Ví dụ:

```text
Context window: 16,000 tokens
System + policy: 1,000
Chat history summary: 1,500
Retrieved docs: 8,000
User question: 500
Reserved output: 2,000
Safety margin: 1,000
Total: 14,000
```

Nếu vượt budget, đừng cắt bừa phần cuối. Cần strategy:

- Compress chat history thành summary có metadata.
- Rerank retrieved documents để giữ top chunks quan trọng.
- Loại bỏ boilerplate trong prompt.
- Giới hạn tool results.
- Reserve output tokens trước.
- Fail fast với error rõ nếu request vượt policy.

Long context có trade-off:

| Lợi ích | Chi phí/rủi ro |
|---|---|
| Đưa được nhiều tài liệu hơn | Cost input token tăng |
| Giảm số lần call retrieval trong case nhỏ | Latency prefill tăng |
| Hữu ích cho phân tích tài liệu dài | Model có thể bỏ sót thông tin giữa context |
| Đơn giản hơn orchestration v1 | PII/logging risk tăng |

## 6. Decoding Params: Điều Khiển Output

Decoding là bước chọn token tiếp theo từ probability distribution.

`Greedy decoding` luôn chọn token có xác suất cao nhất ở mỗi bước. Nó nhanh, dễ hiểu và thường ổn định hơn sampling, nhưng lựa chọn tốt nhất ở từng bước chưa chắc tạo ra toàn bộ chuỗi tốt nhất. Greedy cũng có thể làm output lặp hoặc cứng. Trong nhiều API hosted, `temperature=0` tạo behavior gần greedy, nhưng implementation cụ thể và hạ tầng song song vẫn có thể làm output không hoàn toàn deterministic.

| Param | Ý nghĩa | Dùng khi | Rủi ro nếu sai |
|---|---|---|---|
| Greedy decoding | Chọn token xác suất cao nhất | Baseline ổn định, task output ngắn | Có thể lặp/cứng, không tìm chuỗi tối ưu toàn cục |
| `temperature=0` hoặc thấp | Output ổn định hơn, ưu tiên token xác suất cao | Classification, extraction, JSON, compliance | Không bảo đảm deterministic tuyệt đối |
| `temperature=0.2-0.5` | Cân bằng ổn định và linh hoạt | Support answer, summarization, rewrite nghiêm túc | Vẫn có nondeterminism |
| `temperature>=0.7` | Sáng tạo hơn | Brainstorm, copywriting, ideation | Dễ drift format, factual risk cao hơn |
| `top_p` | Sample trong cumulative probability mass | Giảm token quá hiếm | Tune cùng temperature bừa bãi làm khó debug |
| `top_k` | Chỉ chọn trong k token top | Hay gặp ở local runtime | k quá thấp làm output nghèo |
| Output token cap | Giới hạn output; tên API có thể là `max_tokens`, `max_output_tokens` hoặc `num_predict` | Kiểm soát cost/latency | Quá thấp gây output bị cụt |
| `stop sequences` | Dừng khi gặp marker | Protocol/template cụ thể | Marker sai làm cắt nhầm |
| `seed` nếu provider hỗ trợ | Tăng reproducibility | Test và regression | Không phải provider nào cũng đảm bảo tuyệt đối |

Rule v1:

- Extraction/schema: `temperature=0` hoặc rất thấp, `max_tokens` chặt, validate schema.
- Customer support: `temperature=0.2-0.4`, citation nếu trả lời theo policy.
- Creative writing: temperature cao hơn, human review nếu public-facing.
- Không tune `temperature`, `top_p`, `top_k` cùng lúc khi chưa có eval.
- Mọi thay đổi decoding params phải đi qua golden set.
- Khi provider hỗ trợ cả `temperature` và `top_p`, thường chỉ thay đổi một tham số tại một thời điểm để biết thay đổi nào tạo ra tác động.

## 7. Hosted Model Vs Local/Open-weight Model

Hosted closed model: provider vận hành model, bạn gọi API. Ví dụ category: GPT, Claude, Gemini.

Open-weight/local model: bạn dùng weights có thể tải về và serve bằng runtime như Ollama, llama.cpp, vLLM, TGI hoặc custom service. Ví dụ category: Llama, Qwen, Mistral, DeepSeek-style open-weight models.

| Tiêu chí | Hosted model | Local/open-weight model |
|---|---|---|
| Go-live | Nhanh | Chậm hơn vì cần serving stack |
| Quality frontier | Thường mạnh, cập nhật nhanh | Tùy model, hardware và tuning |
| Ops | Nhẹ hơn | Cần GPU/CPU capacity, batching, monitoring |
| Privacy | Phụ thuộc data policy provider | Kiểm soát tốt hơn nếu self-host đúng cách |
| Cost | Dễ bắt đầu, có thể đắt khi scale | Capex/infra cao, có thể rẻ ở volume lớn |
| Latency | Network + provider queue | Có thể thấp nếu đặt gần app, nhưng phụ thuộc hardware |
| Compliance | Cần review vendor | Cần review license, model source, deployment controls |
| Upgrade | Provider đổi nhanh, có deprecation | Bạn kiểm soát version, nhưng tự chịu burden |

Decision rule thực dụng:

- POC hoặc product cần quality cao nhanh: bắt đầu hosted.
- Dữ liệu cực nhạy cảm, offline, air-gapped hoặc compliance nghiêm: cân nhắc local/open-weight.
- Task routing/classification/extraction đơn giản: benchmark small model trước.
- Task reasoning/code/multi-step khó: dùng stronger model hoặc route fallback.
- Ở scale lớn: tính `total cost of ownership`, không chỉ giá mỗi token.

## 8. Cost, Latency, Security Và Performance

### Cost

Cost/request thường gồm:

```text
input_tokens * input_price
+ output_tokens * output_price
+ retrieval/tool cost
+ retry cost
+ observability/storage cost
+ human review cost nếu có
```

Các nguyên nhân gây cost spike:

- Chat history không được tóm tắt.
- Retrieved chunks quá nhiều.
- `max_tokens` quá rộng.
- Retry không giới hạn.
- Người dùng paste log dài hoặc file lớn.
- Prompt template chứa boilerplate dư.

### Latency

Latency thường gồm:

```text
client -> app validation -> retrieval/tool call -> LLM prefill -> token generation -> postprocess -> response
```

Điểm cần nhớ:

- Input dài làm `prefill` chậm.
- Output dài làm user cảm thấy chậm vì token generation phải sinh tuần tự.
- Streaming cải thiện perceived latency nhưng không làm total compute biến mất.
- Batching tăng throughput nhưng có thể tăng queueing latency.
- Local model cần quản lý KV cache, quantization, GPU memory và cold start.

### Security

LLM app có attack surface khác backend thường:

- Prompt injection trong user input hoặc retrieved documents.
- Data exfiltration qua tool call.
- Secret bị đưa vào prompt hoặc log.
- Output gây hành động sai nếu không có approval gate.
- Model/provider policy không phù hợp dữ liệu nhạy cảm.

Minimum controls:

- Không đưa API key, password, private token vào prompt.
- Redact PII trong log nếu không có lý do rõ.
- Tách quyền tool theo user/session.
- Validate output trước khi gọi side-effect tool.
- Rate limit và quota theo tenant.
- Audit prompt/model/tool version.

## 9. Production Readiness

LLM dùng được trong production không? Có, nếu scope đúng và có điều kiện vận hành rõ.

### Dùng được khi

- Use case chịu được xác suất hoặc có validation/human review.
- Có golden set đại diện domain để test prompt/model/decoding.
- Output có contract rõ: JSON schema, citation requirement hoặc action policy.
- Có monitoring: latency, token usage, cost/request, error rate, parse failure, user feedback.
- Có data policy: retention, PII, secret handling, vendor review.
- Có fallback: retry có giới hạn, model fallback, cached answer, graceful degradation.
- Có rollback khi model/prompt/provider thay đổi.

### Không nên dùng trực tiếp khi

- Quyết định high-stakes không có human approval.
- Cần factual correctness tuyệt đối nhưng không có authoritative source/tool.
- Không thể gửi dữ liệu ra provider và cũng chưa có local deployment an toàn.
- Không có cách đo quality ngoài cảm giác.
- Output text tự do được đưa thẳng vào workflow có side effect.

### Production v1 checklist

- [ ] `model_id`, version và decoding params được pin.
- [ ] Prompt có version và owner.
- [ ] Token budget được tính trước khi gọi model.
- [ ] Output được validate bằng schema hoặc rule rõ.
- [ ] Có golden evaluation set.
- [ ] Có log không chứa raw PII mặc định.
- [ ] Có dashboard cost/latency/token.
- [ ] Có timeout, retry budget và fallback.
- [ ] Có release process cho prompt/model changes.

## 10. Mini Architecture Cho Day 17

Một LLM wrapper tối thiểu nhưng gần production:

```text
API endpoint
  -> validate request size and tenant quota
  -> build prompt from versioned template
  -> estimate/count tokens
  -> call model with pinned config
  -> validate output contract
  -> log metrics without raw sensitive text
  -> return stable response
```

Ví dụ response nên có metadata đủ để debug:

```json
{
  "answer": "LLM có thể dùng trong production nếu có eval, monitoring, guardrails và rollback.",
  "model": "example-model",
  "prompt_version": "llm-fundamentals-v1",
  "finish_reason": "stop",
  "usage": {
    "input_tokens": 812,
    "output_tokens": 72
  },
  "latency_ms": 1840
}
```

Không nên expose toàn bộ raw provider response cho client. Hãy normalize response schema để provider/model có thể thay đổi phía sau abstraction.

## 11. Trade-off Tổng Hợp

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Production note |
|---|---|---|---|
| Hosted LLM | Cần go-live nhanh, quality cao, ops nhẹ | Data không được rời hệ thống, cost khó kiểm soát | Review vendor policy, log usage, có fallback |
| Local/open-weight LLM | Cần privacy/control/offline hoặc volume lớn | Team chưa có GPU ops và eval năng lực model | Cần serving, security, monitoring, capacity planning |
| Large model | Task ambiguous, reasoning, code, multi-step | Task đơn giản có rule/model nhỏ đủ | Dùng routing để tránh lãng phí |
| Small model | Classification, extraction, routing, latency thấp | Cần reasoning sâu hoặc instruction phức tạp | Benchmark theo domain |
| Long context | Cần đọc tài liệu dài trong một request | Corpus lớn có thể search được | Kết hợp RAG/rerank thay vì nhồi context |
| Low temperature | Output cần ổn định, parse được | Brainstorm sáng tạo | Vẫn cần validation |
| High temperature | Ideation, creative draft | Compliance, JSON, factual QA | Cần human review hoặc guardrail |

## 12. Kết Luận

LLM fundamentals cho AI Engineer không dừng ở "model sinh chữ". Bạn cần nhìn LLM như một dependency runtime có cost, latency, security boundary, config, version, test suite và failure mode riêng. Khi nắm được tokenization, next-token prediction, context budget, decoding và model choice, bạn sẽ học Day 18-20 hiệu quả hơn vì mọi prompt, structured output và architecture decision đều dựa trên các ràng buộc này.
