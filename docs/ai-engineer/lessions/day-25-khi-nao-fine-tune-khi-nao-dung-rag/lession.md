# Day 25: Khi nào Fine-tune, khi nào dùng RAG

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Phân biệt đúng vai trò của `prompt engineering`, RAG, tool calling, fine-tuning và distillation.
- Biết khi nào nên dùng prompt-only, khi nào thêm RAG, khi nào gọi tool, khi nào fine-tune, và khi nào kết hợp nhiều kỹ thuật.
- Hiểu full fine-tuning, PEFT, LoRA, QLoRA, adapter, prompt tuning và distillation ở mức đủ để ra quyết định engineering.
- Thiết kế được hybrid RAG + fine-tuned model cho production.
- Viết được decision record cho một AI feature, có trade-off về quality, cost, latency, privacy, rollback và operability.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

RAG đưa knowledge từ nguồn bên ngoài vào runtime context. Tool calling lấy realtime data hoặc thực hiện action qua API. Fine-tuning thay đổi behavior của model bằng training data. Prompt engineering là lớp điều khiển nhanh nhất, rẻ nhất để thử nghiệm nhưng kém bền khi workflow phức tạp.

Nếu vấn đề là "model không biết facts mới, private docs hoặc realtime state", ưu tiên RAG hoặc tool. Nếu vấn đề là "model không ổn định về format, tone, policy behavior hoặc domain workflow lặp lại", cân nhắc fine-tuning sau khi đã có baseline và eval. Production thường không chọn một kỹ thuật duy nhất: RAG/tool giữ source of truth, fine-tuned model giữ behavior, validator giữ contract.

## 1. Bài Này Nằm Ở Đâu Trong Lộ Trình

Day 21-24 đã đi qua framework, agent, security, tool calling và memory. Day 25 mở phase Fine-tuning & Local LLM: trước khi train bất kỳ model nào, bạn phải biết có thật sự cần train không.

```text
Day 21-24: app orchestration, agent, security, tool, memory
Day 25: quyết định prompt/RAG/tool/fine-tune/distill
Day 26: chuẩn bị dataset instruction tuning
Day 27: chạy LoRA/QLoRA hands-on
Day 28: evaluate trước/sau fine-tune
Day 29-30: local LLM và deploy
```

Sai lầm phổ biến của team mới làm AI là fine-tune để giải quyết mọi vấn đề. Với góc nhìn production, fine-tuning là build một artifact mới, kéo theo dataset, training job, model registry, eval, deployment, rollback, privacy review và monitoring. Nếu cùng kết quả có thể đạt được bằng prompt, schema validation, RAG hoặc tool, hãy chứng minh fine-tune đáng tiền bằng metric trước.

## 2. Mental Model Cho Senior Software Engineer

| Kỹ thuật | SE analogy | Tác dụng chính | Thời điểm thay đổi |
|---|---|---|---|
| Prompt engineering | Runtime config | Hướng dẫn cách trả lời trong request | Mỗi deploy hoặc mỗi request |
| Structured output | API contract | Ép output theo schema | Mỗi request |
| RAG | Read path tới search/database | Đưa tài liệu liên quan vào context | Khi index/document thay đổi |
| Tool calling | Internal API/RPC | Lấy realtime data hoặc thực hiện action | Khi state backend thay đổi |
| Fine-tuning | Build artifact mới | Dạy behavior từ examples | Khi train/deploy model mới |
| Distillation | Rebuild service nhỏ hơn | Nén capability vào model nhỏ | Khi train/deploy model mới |

Rule ngắn:

```text
Cần facts mới hoặc private docs -> RAG
Cần realtime state hoặc action -> tool calling
Cần format/tone/workflow ổn định -> prompt + schema trước, fine-tune nếu failure lặp lại
Cần giảm cost/latency cho task hẹp -> distill/fine-tune model nhỏ
Cần cả facts và behavior -> hybrid RAG/tool + fine-tune + validation
```

## 3. Đừng Bắt Đầu Bằng Fine-tuning

Trình tự thực tế nên là:

1. Xác định task: hỏi đáp, extraction, classification, generation, coding, support, agent workflow.
2. Viết prompt baseline với input/output contract rõ.
3. Thêm structured output hoặc JSON schema nếu downstream cần parse.
4. Nếu thiếu knowledge, thêm RAG.
5. Nếu cần realtime data/action, thêm tool calling.
6. Tạo golden set gồm input, expected output, nguồn đúng, failure case và metric.
7. Chỉ fine-tune khi baseline đã có failure mode lặp lại mà prompt/RAG/tool không giải quyết tốt hoặc quá đắt.

Ví dụ: model hay trả JSON sai. Fine-tune có thể giúp, nhưng production fix đầu tiên là schema validation, retry có kiểm soát, constrained decoding hoặc provider structured output. Fine-tune chỉ nên vào sau nếu lỗi format vẫn cao trên golden set hoặc prompt quá dài làm cost/latency xấu.

## 4. Khi Nào Dùng Prompt-only

Prompt-only phù hợp khi:

- Task đơn giản, ít rủi ro, không cần facts private.
- Output là text tự nhiên, downstream không parse nghiêm ngặt.
- Traffic thấp hoặc đang discovery.
- Failure có thể chấp nhận bằng human review.
- Yêu cầu thay đổi liên tục, chưa có metric ổn định.

Không nên chỉ dùng prompt khi:

- Cần citation, ACL, tenant isolation hoặc audit source.
- Cần data realtime như order status, account balance, inventory.
- Output đi vào billing, compliance, legal hoặc workflow tự động.
- Prompt dài, dễ drift và khó version.

Production note: prompt là artifact cần version, owner, changelog, eval result và rollback. "Chỉ prompt" không có nghĩa là "không cần engineering".

## 5. Khi Nào Dùng RAG

RAG phù hợp khi source of truth nằm ngoài model:

- Tài liệu nội bộ, policy, handbook, runbook, ticket history.
- Knowledge thay đổi hằng ngày, hằng tuần hoặc theo tenant.
- Cần citation/source để audit hoặc để người dùng kiểm chứng.
- Cần permission-aware access control.
- Không được đưa toàn bộ dữ liệu vào training vì privacy, license hoặc compliance.

Pipeline RAG production-style:

```text
User query
  -> auth + tenant resolution
  -> query rewrite / classification
  -> embedding hoặc hybrid search
  -> metadata filter + ACL
  -> rerank
  -> context builder với token budget
  -> LLM answer
  -> citation checker + schema validator
  -> response + trace
```

RAG không tự động giải quyết:

- Output sai schema.
- Tone không đúng brand.
- Model không tuân thủ workflow nhiều bước.
- Reasoning domain bị yếu dù context đã đúng.
- Hallucination nếu retrieved chunks sai, thiếu hoặc bị prompt injection.

Performance trade-off:

- RAG thêm latency cho embedding/search/rerank. Budget thường gặp: retrieval 50-300 ms với index nội bộ tốt, rerank 100-800 ms tùy model và top_k, generation vẫn là phần lớn latency.
- `top_k` nên bắt đầu 3-8 chunks. Quá ít thì thiếu context, quá nhiều thì tăng token cost và noise.
- Hybrid search dense + BM25 thường tốt hơn dense-only cho tài liệu có mã, tên sản phẩm, policy ID hoặc thuật ngữ hiếm.
- Rerank tăng quality nhưng cần cache và timeout riêng.

## 6. Khi Nào Dùng Tool Calling

Tool calling phù hợp khi model cần đọc hoặc thay đổi state thật:

- Kiểm tra order status, refund status, account tier, quota.
- Tạo ticket, cập nhật CRM, gửi email, đặt lịch.
- Gọi pricing service, inventory service, fraud service.
- Tính toán deterministic bằng service đã kiểm thử.

Nguyên tắc production:

- Model chỉ đề xuất tool call; application mới thực thi.
- Tool phải có auth, authorization, idempotency, timeout, retry policy và audit log.
- Không để model tự quyết định permission.
- Với action có side effect, cần confirmation hoặc policy gate.

Tool calling không thay RAG. Tool trả state hoặc thực hiện action; RAG đọc tài liệu. Một support assistant thường cần cả hai: RAG để đọc policy refund, tool để kiểm tra đơn hàng, validator để đảm bảo response có `case_id`, `next_action`, `risk_level`.

## 7. Khi Nào Fine-tune

Fine-tuning phù hợp khi bạn muốn model học behavior từ examples:

- Output format rất ổn định và schema phức tạp.
- Style/tone riêng của brand hoặc team cần nhất quán ở volume lớn.
- Domain workflow lặp lại: triage, coding review, complaint handling, compliance refusal.
- Classification/extraction/generation task hẹp có nhiều labeled examples.
- Prompt quá dài vì phải lặp instruction nhiều lần.
- Muốn dùng model nhỏ hơn để giảm cost/latency nhưng vẫn đạt quality mục tiêu.

Fine-tuning không phù hợp để:

- Nhồi facts thay đổi thường xuyên vào weights.
- Thay database, search engine hoặc permission system.
- Sửa ingestion/chunking/retrieval kém.
- Bảo đảm không hallucinate.
- Bỏ qua schema validation.
- Che giấu việc chưa có eval set.

Điều kiện tối thiểu trước khi fine-tune:

- Có baseline prompt/RAG/tool và biết failure mode cụ thể.
- Có dataset sạch, có license hợp lệ, không chứa PII/secret không được phép train.
- Có train/validation/test split, golden set không trùng train.
- Có metric quality, latency, cost và safety.
- Có registry cho dataset version, base model, adapter/model artifact, prompt version và eval result.
- Có rollback về base model hoặc adapter trước đó.

## 8. Các Kiểu Fine-tuning

| Kỹ thuật | Ý tưởng | Nên dùng khi | Trade-off |
|---|---|---|---|
| Full fine-tuning | Update toàn bộ weights | Có data lớn, GPU/MLOps mạnh, cần thay đổi behavior sâu | Cost cao, artifact lớn, dễ overfit hoặc catastrophic forgetting |
| PEFT | Chỉ train một phần nhỏ parameter | Muốn tiết kiệm VRAM và quản lý nhiều task/domain | Phụ thuộc runtime support, có thể kém full fine-tune nếu task lệch xa |
| LoRA | Thêm low-rank matrices vào một số layer | Instruction tuning phổ biến, cần artifact nhỏ | Cần chọn rank/target modules; nếu rank quá thấp có thể underfit |
| QLoRA | LoRA trên base model quantized 4-bit | GPU hạn chế, muốn fine-tune model lớn hơn | Train tiết kiệm VRAM nhưng inference/deploy cần kiểm tra chất lượng quantization |
| Adapter | Chèn module nhỏ vào network | Nhiều domain/task, muốn bật/tắt adapter | Runtime phức tạp hơn, không phải stack nào cũng support tốt |
| Prompt tuning | Train soft prompt vector | Task hẹp, model lớn, muốn giữ weights | Ít phổ biến hơn LoRA trong app engineering; khó debug vì prompt không đọc được |
| Distillation | Train model nhỏ bắt chước model lớn | High throughput, latency/cost thấp, task hẹp rõ | Cần teacher output chất lượng và eval chặt để tránh mất capability |

### Full Fine-tuning

Full fine-tuning update toàn bộ weights của model. Nó mạnh nhưng đắt và nhiều rủi ro. Bạn cần data đủ lớn, compute đủ mạnh, monitoring training, checkpointing, eval nhiều chiều và deployment discipline.

Nên cân nhắc khi:

- Domain rất khác base model.
- Task có nhiều dữ liệu chất lượng cao.
- PEFT không đạt metric sau nhiều thử nghiệm hợp lý.
- Team có MLOps để vận hành model artifact lớn.

Không nên là lựa chọn đầu tiên cho team app engineering. Với phần lớn use case enterprise assistant, LoRA/QLoRA hoặc distillation thực dụng hơn.

### PEFT, LoRA Và QLoRA

PEFT là họ kỹ thuật fine-tuning chỉ update một phần nhỏ parameter. LoRA là biến thể phổ biến: thêm low-rank matrices vào các layer attention/MLP, train các matrices này, giữ base model cố định. QLoRA tiết kiệm VRAM hơn bằng cách quantize base model, rồi train LoRA adapter.

Hiểu đúng QLoRA:

```text
Base model weights -> load ở dạng quantized để giảm memory
LoRA adapter       -> parameter nhỏ, vẫn là phần được train
Optimizer state    -> chỉ theo dõi trainable adapter parameters
Output artifact    -> adapter nhỏ + reference tới đúng base model/tokenizer
```

QLoRA không có nghĩa là mọi phép toán training đều trở thành số nguyên 4-bit.
Compute dtype, quantization config, target modules và hardware support vẫn ảnh
hưởng stability, tốc độ và chất lượng. Luôn log trainable parameter count và
so sánh với baseline trước khi train dài.

Decision thực tế:

- Có GPU hạn chế, muốn thử nhanh: QLoRA.
- Có runtime cần merge adapter vào base model để inference đơn giản: LoRA rồi merge nếu quality không giảm.
- Có nhiều tenant/domain riêng: giữ nhiều adapter và route theo tenant/domain, nhưng phải kiểm soát memory và cold start.

Trade-off khi deploy:

- Giữ adapter riêng: artifact nhỏ, đổi adapter nhanh, nhưng runtime phải load đúng
  base model + adapter và quản lý routing/version compatibility.
- `merge_and_unload`: serving đơn giản hơn và có thể giảm adapter overhead, nhưng
  artifact lớn hơn, mất khả năng switch adapter tức thì và cần regression test
  lại sau merge/quantize.
- Nhiều adapter trên một base model giúp reuse weights, nhưng phải kiểm soát adapter
  nào đang active; route sai adapter là một lỗi correctness/privacy.

### Adapter Và Prompt Tuning

Adapter cũng là PEFT nhưng chèn module nhỏ vào network. Nó hữu ích khi cần nhiều task/domain riêng nhưng yêu cầu runtime phức tạp hơn. Prompt tuning train một vector "soft prompt", không giống prompt text do người đọc viết. Nó có thể hiệu quả với task hẹp nhưng khó debug và ít trực quan hơn LoRA.

### Distillation

Distillation không nhất thiết là fine-tuning theo nghĩa instruction tuning, nhưng thường nằm cùng decision space. Bạn dùng model lớn làm teacher để tạo label/output, rồi train model nhỏ cho task hẹp.

Use case tốt:

- 1 triệu request/ngày cho classification hoặc extraction.
- Model lớn đạt quality tốt nhưng cost/request cao.
- Latency target thấp, ví dụ p95 dưới 500 ms.
- Output contract rõ và eval tự động được.

## 9. Hybrid RAG + Fine-tuned Model

Pattern production thường gặp:

```text
Client
  -> API Gateway / Auth
  -> Orchestrator
      -> Query classifier
      -> Retriever với ACL
      -> Tool layer với policy gate
      -> Context builder
      -> Fine-tuned LLM hoặc adapter-routed LLM
      -> Schema validator
      -> Citation checker
      -> Safety/compliance checker
  -> Response + trace
```

Phân chia trách nhiệm:

- RAG cung cấp facts và citation.
- Tool cung cấp realtime state/action.
- Fine-tuned model cung cấp tone, format, workflow, domain behavior.
- Validator enforce API contract.
- Eval phát hiện regression.
- Observability cho biết model, adapter, prompt, retrieval index và tool version nào tạo ra response.

Ví dụ fintech support assistant:

- RAG lấy policy refund hiện hành với citation.
- Tool kiểm tra account status và transaction history.
- Fine-tuned model học cách trả lời ngắn gọn, không hứa vượt policy, biết escalation.
- Schema validator bắt buộc output có `answer`, `sources`, `risk_level`, `needs_human`, `next_action`.
- Rollback có thể chuyển từ adapter `support-v3` về `support-v2` hoặc về base model + prompt nếu eval live xấu.

## 10. Decision Matrix

| Nhu cầu | Nên bắt đầu với | Vì sao |
|---|---|---|
| Trả lời theo policy nội bộ có citation | RAG | Facts nằm trong tài liệu và cần source |
| Giá, tồn kho, order status realtime | Tool calling | Cần state live từ backend |
| Output JSON sai format lặp lại | Structured output, validator, sau đó fine-tune nếu cần | Schema là contract bắt buộc; fine-tune chỉ tăng độ ổn định |
| Customer support cần tone riêng | Prompt baseline, sau đó fine-tune nếu volume/failure đủ lớn | Tone là behavior pattern |
| Knowledge thay đổi hằng tuần | RAG | Update index rẻ và nhanh hơn train |
| Muốn giảm cost/request cho task hẹp | Distillation hoặc fine-tune model nhỏ | Model nhỏ có thể đủ chất lượng |
| Domain jargon và cách trả lời chuẩn | RAG + fine-tune | RAG cấp facts, fine-tune cấp style/workflow |
| Hallucination về tài liệu | Fix retrieval/eval trước | Fine-tune không sửa retrieved context sai |
| Multi-tenant private docs | RAG với ACL | Fine-tune có risk memorize và leak data |
| Cần action có side effect | Tool calling + policy gate | Model không nên tự thực thi action |

## 11. Dataset, Privacy Và Governance

Checklist dữ liệu trước khi train:

- Data source có quyền dùng cho training không.
- Có PII, PHI, secret, token, password, customer contract hoặc dữ liệu regulated không.
- Có cần anonymization, redaction hoặc synthetic data không.
- Có consent hoặc DPA phù hợp không.
- Có license của base model và dataset phù hợp commercial/internal use không.
- Có chống data contamination giữa train và eval không.
- Có version dataset bằng hash, manifest hoặc data registry không.

Một format instruction tuning tối thiểu:

```json
{
  "id": "support_refund_001",
  "messages": [
    {
      "role": "system",
      "content": "Bạn là support assistant cho fintech. Trả lời ngắn, đúng policy, không hứa hoàn tiền nếu chưa đủ điều kiện."
    },
    {
      "role": "user",
      "content": "Tôi bị trừ tiền hai lần khi nâng cấp gói."
    },
    {
      "role": "assistant",
      "content": "{\"answer\":\"Mình sẽ kiểm tra giao dịch bị trừ lặp và tạo yêu cầu đối soát nếu đủ điều kiện.\",\"risk_level\":\"medium\",\"needs_human\":true}"
    }
  ],
  "metadata": {
    "source": "resolved_ticket",
    "policy_version": "refund_policy_2026_04",
    "contains_pii": false,
    "split": "train"
  }
}
```

Không đưa raw ticket chứa email, số điện thoại, card number, access token hoặc nội dung nhạy cảm vào training nếu chưa qua governance. Với RAG, dữ liệu private vẫn phải có ACL trước retrieval, không chỉ filter sau khi LLM trả lời.

## 12. Eval Trước Khi Quyết Định

Không fine-tune bằng cảm giác. Cần eval set trước.

Metric theo lớp:

- Retrieval: recall@k, MRR, nDCG, citation hit rate, permission violation rate.
- Generation: exact match cho extraction/classification, rubric score cho text, JSON validity, schema pass rate.
- Faithfulness: answer có được support bởi context không, citation correctness.
- Safety: refusal accuracy, policy violation rate, prompt injection success rate.
- Business: task success rate, human escalation rate, handle time, CSAT proxy.
- Performance: p50/p95 latency, token/request, cost/request, throughput, error rate.

So sánh tối thiểu:

| Variant | Quality | p95 latency | Cost/request | Risk |
|---|---:|---:|---:|---|
| Prompt baseline |  |  |  |  |
| Prompt + RAG/tool |  |  |  |  |
| Fine-tuned model |  |  |  |  |
| Hybrid |  |  |  |  |

Fine-tune đáng làm khi nó cải thiện metric quan trọng đủ lớn để bù chi phí vận hành. Ví dụ: schema pass rate từ 92% lên 99.2%, p95 latency giảm 40% do dùng model nhỏ, hoặc human escalation giảm 15% mà safety không xấu đi.

## 13. Cost Và Latency

Cost cần tính toàn vòng đời:

- Build cost: data cleaning, labeling, privacy review, training compute, experiments.
- Inference cost: token, model price, GPU hours, adapter memory, batching.
- Ops cost: registry, eval, monitoring, rollback, on-call.
- Opportunity cost: thời gian team dùng để train thay vì sửa retrieval hoặc product flow.

Latency trade-off:

- Prompt-only thường đơn giản nhất nhưng prompt dài làm latency tăng.
- RAG thêm retrieval/rerank latency nhưng giảm hallucination về facts.
- Tool calling thêm network latency và failure modes của backend service.
- Fine-tuned model nhỏ có thể giảm latency, nhưng adapter routing hoặc cold load có thể tăng tail latency.
- Full fine-tuned model lớn không mặc định nhanh hơn base model.

Một budget ví dụ cho support assistant:

```text
p95 target: 2.5s
auth + request validation: 50ms
retrieval + ACL + rerank: 450ms
tool calls: 300ms với timeout 700ms
LLM generation: 1.4s
validation + citation check: 150ms
buffer: 450ms
```

Nếu RAG + tool vượt latency target, đừng vội fine-tune. Kiểm tra cache, parallel retrieval/tool, giảm top_k, chọn reranker nhẹ hơn, streaming response hoặc route task đơn giản sang model nhỏ.

## 14. Rollback Và Deployment

Model deployment cần giống software deployment:

- Version mọi thứ: dataset, prompt, base model, adapter, tokenizer, retrieval index, reranker, schema.
- Có offline eval pass gate trước deploy.
- Canary theo tenant, traffic percent hoặc task type.
- Shadow mode để so sánh response nhưng chưa trả cho user.
- Có rollback nhanh về adapter/model/prompt trước đó.
- Log đủ metadata để debug từng response.

Metadata nên log:

```json
{
  "trace_id": "tr_123",
  "tenant_id": "tenant_a",
  "prompt_version": "support_prompt_v4",
  "base_model": "base-model-x",
  "adapter_version": "support_lora_v3",
  "retrieval_index": "policy_index_2026_05_01",
  "reranker_version": "reranker_v2",
  "schema_version": "support_response_v1",
  "input_tokens": 1840,
  "output_tokens": 220,
  "latency_ms": 2130,
  "estimated_cost_usd": 0.0041,
  "eval_tags": ["refund", "billing"]
}
```

## 15. Dùng Được Trong Production Không? Nếu Có Thì Cần Điều Kiện Gì?

Có, nhưng từng kỹ thuật có điều kiện khác nhau.

Prompt-only dùng được trong production khi task rủi ro thấp, có prompt versioning, eval cơ bản, observability, token budget và fallback.

RAG dùng được trong production khi ingestion ổn định, chunking có kiểm thử, retrieval eval đạt ngưỡng, ACL được enforce trước khi build context, citation checker hoạt động, index được version và có monitoring drift.

Tool calling dùng được trong production khi tool có auth, authorization, idempotency, timeout, retry, audit log, confirmation cho side effect và policy gate tách khỏi model.

Fine-tuning dùng được trong production khi có dataset hợp pháp và sạch, eval offline/online, model registry, canary, rollback, privacy review, cost model, latency test và monitoring regression.

Hybrid RAG + fine-tune dùng được trong production khi team đủ vận hành cả retrieval pipeline lẫn model artifact. Đây thường là best solution cho enterprise assistant phức tạp, nhưng không nên dùng nếu chưa có metric rõ vì complexity tăng mạnh.

## 16. Best Solution Theo Context

| Context | Best starting solution | Khi nào nâng cấp |
|---|---|---|
| POC nội bộ trong 1 tuần | Prompt + structured output | Thêm RAG nếu thiếu facts; thêm eval trước khi mở rộng |
| Q&A theo tài liệu công ty | RAG + citation | Thêm fine-tune nếu tone/workflow vẫn lỗi trên golden set |
| Support tạo ticket và cập nhật CRM | Tool calling + RAG + validator | Fine-tune khi response style và triage decision không ổn định |
| Extraction hóa đơn | Structured output + validator | Fine-tune/distill nếu volume cao hoặc schema pass rate thấp |
| Product FAQ có giá/tồn kho | RAG cho docs + tool cho price/inventory | Không fine-tune facts realtime; chỉ fine-tune tone nếu cần |
| High-volume classification | Prompt baseline rồi distill/fine-tune model nhỏ | Khi cost/latency của model lớn vượt budget |

## 17. Tự Kiểm Tra

1. Vì sao fine-tuning không phải cách tốt để cập nhật facts realtime?
2. Khi nào RAG không đủ và cần fine-tune?
3. LoRA khác full fine-tuning ở điểm nào?
4. QLoRA giải quyết bài toán gì, đổi lại rủi ro nào?
5. Hybrid RAG + fine-tune chia trách nhiệm ra sao?
6. Metric nào chứng minh fine-tune đáng giá hơn prompt/RAG/tool?
7. Vì sao multi-tenant private docs nên dùng RAG với ACL thay vì fine-tune chung?

## 18. Checklist

- [ ] Phân biệt được prompt, RAG, tool calling, fine-tuning và distillation.
- [ ] Giải thích được vì sao facts mới nên dùng RAG/tool.
- [ ] Giải thích được vì sao behavior/format ổn định có thể cần fine-tune.
- [ ] Hiểu full fine-tuning, PEFT, LoRA, QLoRA, adapter và prompt tuning.
- [ ] Biết thiết kế hybrid RAG + fine-tune.
- [ ] Có decision matrix cho ít nhất 5 use case.
- [ ] Có golden metrics trước khi đề xuất fine-tune.
- [ ] Có production notes về dataset, privacy, eval, rollback, cost và latency.
- [ ] Phân biệt được quantized base weights với trainable LoRA adapters trong QLoRA.
- [ ] Có quyết định rõ giữ adapter riêng hay merge khi deploy.
