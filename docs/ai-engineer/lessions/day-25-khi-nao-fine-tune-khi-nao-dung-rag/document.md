# Day 25 Document: Production Reference

## 1. Decision Flow

Dùng flow này trước khi đề xuất fine-tuning:

```text
1. Task có cần facts/private docs không?
   Có -> RAG với ACL, citation, retrieval eval.
   Không -> sang bước 2.

2. Task có cần realtime state hoặc side effect không?
   Có -> tool calling với policy gate, audit, idempotency.
   Không -> sang bước 3.

3. Output có cần machine-readable contract không?
   Có -> structured output, schema validation, retry có giới hạn.
   Không -> sang bước 4.

4. Failure chính là behavior/style/workflow lặp lại?
   Có -> tạo golden set, so sánh prompt baseline với fine-tune/PEFT.
   Không -> sửa product flow, prompt, retrieval, data hoặc UX trước.

5. Cost/latency của model lớn có vượt budget cho task hẹp không?
   Có -> cân nhắc distillation hoặc fine-tune model nhỏ.
```

## 2. Technique Scorecard

Chấm 1-5, điểm cao hơn là phù hợp hơn.

| Tiêu chí | Prompt | RAG | Tool | Fine-tune | Distill |
|---|---:|---:|---:|---:|---:|
| Setup nhanh | 5 | 3 | 3 | 1 | 1 |
| Facts thay đổi thường xuyên | 1 | 5 | 5 | 1 | 1 |
| Citation/source | 1 | 5 | 3 | 1 | 1 |
| Realtime action | 1 | 1 | 5 | 1 | 1 |
| Format/tone ổn định | 3 | 2 | 1 | 5 | 4 |
| Giảm prompt dài | 2 | 2 | 1 | 5 | 4 |
| Giảm latency/cost ở scale | 2 | 2 | 2 | 4 | 5 |
| Ops complexity thấp | 5 | 3 | 3 | 1 | 1 |
| Privacy với private tenant docs | 3 | 5 | 4 | 2 | 2 |

Không cộng điểm máy móc. Scorecard giúp đặt câu hỏi đúng, decision cuối cùng phải dựa vào metric và risk.

## 3. AI Technique Decision Record Template

```markdown
# AI Technique Decision Record

## Context

- Feature:
- Owner:
- Users:
- Tenant/data scope:
- Data sensitivity:
- Expected traffic:
- p95 latency target:
- Cost/request target:
- Release deadline:

## Problem

Mô tả user workflow, input, output mong muốn và downstream dependency.

## Current Baseline

- Prompt version:
- Model:
- RAG index/tool hiện có:
- Eval set:
- Quality:
- p95 latency:
- Cost/request:

## Failure Modes

- Facts sai:
- Không có source/citation:
- Retrieval miss:
- Permission leak:
- Format sai:
- Tone/style sai:
- Workflow sai:
- Tool call sai:
- Latency/cost cao:
- Safety/compliance issue:

## Options

| Option | Quality | Cost | Latency | Ops complexity | Privacy risk | Rollback | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| Prompt-only | | | | | | | |
| RAG | | | | | | | |
| Tool calling | | | | | | | |
| Fine-tune/PEFT | | | | | | | |
| Distillation | | | | | | | |
| Hybrid | | | | | | | |

## Decision

- Chọn:
- Không chọn:
- Lý do:
- Điều kiện để revisit:

## Implementation Plan

1. Baseline:
2. Data/index/tool:
3. Eval:
4. Rollout:
5. Monitoring:
6. Rollback:

## Metrics

- Task success rate:
- Schema pass rate:
- Faithfulness/citation correctness:
- Retrieval recall@k:
- Tool success rate:
- Human escalation rate:
- p95 latency:
- Cost/request:
- Safety violation rate:
```

## 4. Use Case Decision Records

### Use Case 1: Chatbot Hỏi Đáp Policy Nội Bộ

Decision: RAG trước, không fine-tune facts.

Lý do:

- Policy thay đổi theo thời gian và cần citation.
- Người dùng cần biết câu trả lời dựa trên tài liệu nào.
- Có risk permission theo department hoặc tenant.

Implementation:

```text
Auth -> tenant/role -> hybrid search -> ACL filter -> rerank -> context builder -> LLM -> citation checker
```

Metrics:

- retrieval recall@5 >= 0.85 trên golden set.
- citation correctness >= 0.95.
- permission violation rate = 0.
- p95 latency <= 3s.

Khi nào thêm fine-tune: nếu retrieved context đúng nhưng model liên tục trả lời quá dài, sai tone HR/compliance, hoặc không biết refusal pattern dù prompt đã tốt.

### Use Case 2: Support Assistant Tạo Ticket

Decision: hybrid tool calling + RAG + structured output; fine-tune sau nếu triage/tone lỗi lặp lại.

Lý do:

- Cần RAG để đọc policy.
- Cần tool để tạo ticket và kiểm tra account/order.
- Cần schema để downstream ticket system parse.
- Fine-tune có ích nếu có nhiều resolved tickets chất lượng cao.

Output contract:

```json
{
  "summary": "Khách bị tính phí hai lần sau nâng cấp.",
  "category": "billing",
  "priority": "medium",
  "needs_human": true,
  "tool_calls": [
    {"name": "create_ticket", "arguments": {"category": "billing"}}
  ]
}
```

Production condition: tool execution phải idempotent, có audit log và không để model tự set priority cao nếu policy không cho phép.

### Use Case 3: Extract Invoice Thành JSON

Decision: structured output + validator trước; fine-tune hoặc distill nếu volume cao hoặc schema pass rate chưa đạt.

Lý do:

- Đây là task hẹp, output contract rõ.
- RAG thường không cần nếu dữ liệu nằm trong invoice input.
- Fine-tune model nhỏ có thể giảm cost nếu xử lý nhiều hóa đơn.

Metrics:

- JSON validity >= 99.5%.
- field-level F1 cho `invoice_number`, `date`, `total`, `tax`, `vendor` >= 0.97.
- p95 latency <= 1.5s nếu synchronous.
- human correction rate giảm rõ so với baseline.

Rollback: nếu fine-tuned model miss vendor hiếm hoặc tax rule mới, route fallback sang base model + validator cho nhóm input đó.

### Use Case 4: Code Review Assistant Theo Style Team

Decision: RAG coding standards + fine-tune/LoRA cho comment style nếu có dataset review chất lượng.

Lý do:

- Coding standards thay đổi nên nên nằm trong RAG.
- Style review, severity labeling và comment format là behavior pattern.
- Tool có thể gọi static analysis, test result hoặc code search.

Architecture:

```text
PR diff -> static analysis tools -> RAG team standards -> LLM reviewer -> schema validator -> comments
```

Fine-tune condition:

- Có ít nhất vài nghìn comment review tốt, đã loại bỏ thông tin nhạy cảm.
- Eval đo false positive, missed critical issue, usefulness score và comment tone.
- Có guardrail không sinh secret, không leak code ngoài scope.

### Use Case 5: Product FAQ Với Giá Và Tồn Kho Realtime

Decision: RAG cho product docs, tool calling cho price/inventory, không fine-tune facts realtime.

Lý do:

- Giá và tồn kho thay đổi liên tục.
- Product description có thể nằm trong catalog/search index.
- Fine-tune facts sẽ stale và có risk trả thông tin sai.

Implementation:

```text
Query -> product search/RAG -> price tool -> inventory tool -> response with freshness timestamp
```

Metrics:

- price accuracy = 100% so với pricing service.
- inventory accuracy = 100% so với inventory service.
- stale response rate = 0 cho giá/tồn kho.
- p95 latency <= 2s hoặc dùng streaming nếu tool chậm.

Khi nào fine-tune: chỉ khi cần tone bán hàng, objection handling hoặc format tư vấn sản phẩm nhất quán, không dùng để lưu giá/tồn kho.

## 5. Dataset Checklist Cho Fine-tuning

- [ ] Có mục tiêu training rõ: format, tone, workflow, classification hay extraction.
- [ ] Có baseline và failure mode cụ thể.
- [ ] Data có quyền sử dụng cho training.
- [ ] Đã loại PII, secret, credential, access token, card number, raw contract nhạy cảm.
- [ ] Có data manifest: source, owner, license, collected_at, policy_version.
- [ ] Có train/validation/test split theo thời gian hoặc entity để tránh leakage.
- [ ] Golden set không trùng train.
- [ ] Có negative examples và edge cases.
- [ ] Có examples refusal/safety nếu domain cần.
- [ ] Có review sampling bởi domain expert.

## 6. Privacy Checklist

- [ ] Phân loại data: public, internal, confidential, regulated.
- [ ] Có redaction/anonymization pipeline.
- [ ] Có policy cho dữ liệu không được đưa vào hosted training.
- [ ] Có tenant isolation nếu training adapter theo tenant.
- [ ] Có retention policy cho raw data, processed data, checkpoints và logs.
- [ ] Có quyền xóa dữ liệu nếu user/customer yêu cầu.
- [ ] Có review license của base model và dataset.

## 7. Eval Checklist

- [ ] Eval chạy được tự động trong CI hoặc pipeline release.
- [ ] Có offline eval trước deploy.
- [ ] Có shadow/canary eval khi release.
- [ ] Có threshold rõ cho go/no-go.
- [ ] Có slice eval theo tenant, language, document type, product line, risk level.
- [ ] Có metric cost và latency, không chỉ quality.
- [ ] Có regression report giữa base model, previous adapter và new adapter.

Example go/no-go:

```text
Deploy nếu:
- schema pass rate >= 99%
- faithfulness >= 95%
- safety violation <= 0.2%
- p95 latency không tăng quá 15%
- cost/request không tăng quá 10%
- không có permission leak trong test suite
```

## 8. Rollback Checklist

- [ ] Base model version được pin.
- [ ] Adapter/model artifact có version immutable.
- [ ] Prompt version có rollback.
- [ ] Retrieval index version có rollback.
- [ ] Schema version backward-compatible hoặc có migration.
- [ ] Canary có kill switch.
- [ ] Có route fallback theo task/tenant.
- [ ] Dashboard hiển thị quality proxy, latency, cost, error, safety.
- [ ] Log đủ metadata để biết response đến từ model/prompt/index nào.

## 9. Cost Model Template

```text
Traffic:
- requests/day:
- avg input tokens:
- avg output tokens:
- p95 input tokens:
- p95 output tokens:

Prompt/RAG:
- retrieval calls/request:
- rerank calls/request:
- avg chunks:
- avg chunk tokens:
- cache hit rate:

Fine-tuning:
- data cleaning hours:
- labeling cost:
- training GPU hours:
- experiments count:
- artifact storage:
- eval runs:

Inference:
- hosted model cost/request:
- local GPU cost/hour:
- throughput request/sec/GPU:
- adapter memory overhead:
- batching strategy:

Decision:
- current cost/month:
- expected cost/month:
- break-even traffic:
- quality gain required:
```

## 10. Latency Budget Template

```text
p95 target:
- gateway/auth:
- query rewrite:
- embedding/search:
- metadata filter/ACL:
- rerank:
- tool calls:
- LLM generation:
- validation:
- post-processing:
- observability overhead:

Optimization candidates:
- cache:
- parallelize:
- reduce top_k:
- smaller model:
- streaming:
- async workflow:
- distillation:
```

## 11. Production Readiness By Technique

| Technique | Production-ready khi | Không production-ready khi |
|---|---|---|
| Prompt-only | Có versioning, eval, fallback, logs | Prompt nằm rải rác trong code, không metric |
| RAG | Có ACL, eval retrieval, citation, index version | Filter permission sau generation, không đo recall |
| Tool calling | Có auth, idempotency, audit, timeout | Model tự gọi side effect không kiểm soát |
| LoRA/QLoRA | Có dataset sạch, eval, registry, rollback | Train trên raw sensitive data, không canary |
| Full fine-tune | Có MLOps mạnh, data lớn, regression suite | Chỉ để sửa vài lỗi prompt |
| Distillation | Có teacher tốt, task hẹp, eval chặt | Task mở, cần reasoning rộng, không golden set |
