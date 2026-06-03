# Day 47: LLM Testing, Golden Set, CI/CD Cho Prompt/RAG

## Mục Tiêu

Sau bài này, bạn cần làm được:

- Tạo `golden set` cho RAG app, không chỉ test thủ công vài câu hỏi.
- Tách retrieval evaluation, generation evaluation, guardrail evaluation và system evaluation.
- Đo `Recall@K`, `MRR@K`, citation correctness, faithfulness, no-answer accuracy và format pass rate.
- Thiết kế CI gate cho prompt, chunking, embedding, reranker, LLM model và context builder.
- Hiểu snapshot testing nên dùng ở đâu và không nên dùng ở đâu.
- Thiết kế canary release, A/B testing và feedback loop cho LLM app.
- Trả lời được: bộ test này đã đủ production chưa, còn thiếu điều kiện gì.

## TL;DR

LLM/RAG không thể release dựa trên cảm giác "chat thử thấy ổn". Golden set chính là regression test suite của hệ thống AI. Mỗi lần đổi prompt, chunking, embedding model, reranker, retrieval top-k, LLM model hoặc guardrail, bạn cần chạy evaluation có version, metrics, threshold và trace. CI không đảm bảo câu trả lời luôn giống hệt, nhưng phải đảm bảo quality không tụt dưới release gate.

## 1. Vì Sao Test LLM Khác Test Backend?

Backend truyền thống thường test deterministic input/output. LLM có thêm các biến:

- Model output không hoàn toàn deterministic.
- Provider có thể update behavior.
- Prompt nhỏ thay đổi lớn ở output.
- Retrieval phụ thuộc corpus/index/chunking.
- Correct answer có thể có nhiều cách diễn đạt.
- User feedback không luôn phản ánh đúng quality.

Vì vậy, test LLM cần nhiều tầng:

| Layer | Câu hỏi cần trả lời |
|---|---|
| Unit tests | Parser, chunker, citation validator, schema validator có đúng không? |
| Retrieval eval | Query có lấy đúng source/chunk không? |
| Generation eval | Answer có grounded và đúng format không? |
| Guardrail eval | Prompt injection, no-answer, ACL có bị fail không? |
| End-to-end eval | API trả response đúng contract, latency/cost trong budget không? |
| Online monitoring | Production traffic có drift, cost spike, thumbs down tăng không? |

## 2. Golden Set Là Gì?

`Golden set` là tập câu hỏi đã được label trước. Mỗi record nên có expected behavior, expected source/chunk và tag phân tích.

Record mẫu:

```json
{
  "id": "q001",
  "question": "Nhân viên full-time được nghỉ phép năm bao nhiêu ngày?",
  "expected_answer": "Nhân viên full-time được nghỉ 12 ngày phép năm.",
  "expected_chunk_ids": ["hr_leave_policy:v1:0003"],
  "must_cite": ["hr_leave_policy"],
  "expected_behavior": "answer_with_citation",
  "tags": ["hr", "easy", "single-hop", "vietnamese"],
  "difficulty": "easy"
}
```

Tags nên có:

- `easy`.
- `synonym`.
- `multi-hop`.
- `no-answer`.
- `acl`.
- `vietnamese`.
- `english-mix`.
- `prompt-injection`.
- `stale-version`.
- `format`.
- `high-impact`.

Golden set chỉ có câu dễ sẽ tạo cảm giác an toàn giả. Bộ 30 câu đầu nên chia tương đối:

| Nhóm | Số lượng gợi ý | Mục đích |
|---|---:|---|
| Normal single-hop | 8 | Baseline |
| Synonym/paraphrase | 5 | Search robustness |
| Multi-hop | 4 | Context composition |
| No-answer/out-of-scope | 4 | Chống hallucination |
| ACL/permission | 3 | Data protection |
| Prompt injection | 3 | Security |
| Format/citation edge case | 3 | Contract |

## 3. Retrieval Regression Test

Retrieval eval nên deterministic và không cần LLM judge.

Metrics:

| Metric | Ý nghĩa | Khi dùng |
|---|---|---|
| `Hit@K` | Top K có ít nhất một chunk đúng không | Smoke signal |
| `Recall@K` | Lấy được bao nhiêu relevant chunks | Multi-label relevance |
| `MRR@K` | Chunk đúng đầu tiên nằm ở rank mấy | Ranking quality |
| `nDCG@K` | Có relevance score nhiều mức | Khi label graded |

Implementation tối giản:

```python
def recall_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    hits = set(retrieved_ids[:k]).intersection(expected_ids)
    return len(hits) / len(expected_ids)


def mrr_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in expected_ids:
            return 1.0 / rank
    return 0.0
```

Cần report theo tag, không chỉ aggregate. Ví dụ `Recall@5` tổng thể 0.85 nhưng tag `acl` fail thì vẫn block release.

## 4. Generation Regression Test

Prompt thay đổi có thể làm wording khác, nên không nên snapshot full answer dài.

Nên test theo rubric:

- Answer có đúng facts chính không?
- Có grounded trong retrieved context không?
- Có citation bắt buộc không?
- Citation có nằm trong context không?
- Output đúng schema không?
- No-answer case có từ chối đúng không?
- Không leak PII/secret/system prompt không?

Scoring options:

| Cách score | Ưu điểm | Nhược điểm |
|---|---|---|
| Exact match | Rẻ, deterministic | Quá cứng với LLM |
| Keyword/rule | Nhanh, dễ CI | Bắt chất lượng hạn chế |
| Embedding similarity | Linh hoạt | Có false positive |
| LLM-as-judge | Scale tốt cho rubric | Tốn cost, judge drift |
| Human review | Chính xác hơn | Chậm, không scale |

Best solution theo context:

- CI smoke: schema, citation, no-answer, retrieval metrics, vài rule-based checks.
- Nightly eval: full golden set + LLM-as-judge có rubric + trace.
- Release review: xem top regressions theo tag, human spot-check các case high-impact.

## 5. Snapshot Testing

Snapshot tốt cho:

- JSON response shape.
- Citation format.
- Error/refusal format.
- Prompt template compiled output sau khi redact secret.
- Tool call arguments.

Snapshot không tốt cho:

- Free-form answer dài.
- Output có nondeterminism cao.
- Provider/model có wording thay đổi.
- Kết quả phụ thuộc thời gian, random seed hoặc external state.

Rule thực dụng: snapshot contract, không snapshot prose.

## 6. CI/CD Cho Prompt/RAG

Pipeline gợi ý:

```text
pull request
  -> lint / unit tests
  -> prompt template tests
  -> smoke eval 10-15 critical cases
  -> check thresholds
  -> block merge nếu critical metric fail

nightly
  -> full eval 30-100+ cases
  -> generate report by tag
  -> compare baseline
  -> open issue nếu regression

release
  -> full eval
  -> manual review top failures
  -> canary 5-10%
  -> monitor online metrics
  -> rollback nếu vượt guardrail
```

Metadata bắt buộc trong mỗi eval run:

- `eval_run_id`.
- `eval_set_version`.
- `corpus_version`.
- `index_version`.
- `chunking_version`.
- `embedding_model`.
- `retriever_config`.
- `reranker_version`.
- `prompt_version`.
- `llm_model`.
- `guardrail_version`.
- `git_sha`.

Nếu không version các yếu tố này, bạn không biết regression đến từ đâu.

## 7. Threshold-Based Deployment

Threshold mẫu:

```yaml
recall_at_5: 0.80
mrr_at_10: 0.70
citation_correctness: 0.95
format_pass_rate: 0.98
no_answer_accuracy: 0.90
prompt_injection_block_rate: 1.00
acl_leak_count: 0
p95_latency_ms: 5000
estimated_cost_per_request_usd: 0.02
```

Block deploy khi:

- `acl_leak_count > 0`.
- Prompt injection critical case fail.
- Citation correctness dưới ngưỡng domain yêu cầu.
- Format pass rate thấp làm API client hỏng.
- No-answer accuracy giảm mạnh.
- Latency/cost vượt budget production.

Cho `CONDITIONAL PASS` khi:

- Metric tổng thể đạt nhưng một tag non-critical giảm nhẹ.
- Có mitigation hoặc rollback plan.
- Canary được giới hạn traffic và monitor rõ.

## 8. Canary, A/B Testing Và Feedback Loop

Canary:

- Route 5-10% traffic sang prompt/model/index mới.
- Theo dõi latency, cost, citation failure, thumbs down, refusal rate.
- Rollback nếu metric vượt ngưỡng.

A/B testing:

- So sánh prompt/model/router bằng offline labels và user feedback.
- Cần randomization hoặc segmentation rõ.
- Không đưa toàn bộ user sang version mới khi chưa qua offline gate.

Feedback payload:

```json
{
  "trace_id": "trace_20260510_001",
  "rating": "down",
  "reason": "wrong_source",
  "comment": "Answer đúng nhưng citation trỏ tài liệu cũ."
}
```

Feedback phải gắn với trace. Nếu chỉ lưu thumbs down mà không có retrieved chunks, prompt_version và model_version, bạn không debug được lỗi do retriever, reranker, prompt hay model.

## 9. Performance Và Cost

Eval có thể tốn chi phí lớn nếu chạy full generation cho mọi PR.

Chiến lược:

- PR chỉ chạy smoke set nhỏ, ưu tiên critical cases.
- Retrieval eval chạy nhiều hơn vì rẻ và deterministic.
- Generation full eval chạy nightly hoặc trước release.
- Cache retrieved results theo `index_version`.
- Dùng cheap judge cho preliminary, human review cho high-risk.
- Giới hạn concurrency để không vượt rate limit provider.

Metrics vận hành eval:

- eval duration.
- token cost per eval run.
- judge agreement.
- flaky case count.
- retry count.
- cases skipped do timeout/provider error.

## 10. Dùng Được Trong Production Không?

Có, nếu evaluation được vận hành như release gate, không phải file demo.

Điều kiện tối thiểu:

- Golden set có ít nhất 30 cases, gồm normal, no-answer, ACL, prompt injection, citation và format.
- Eval runner lưu trace và version đầy đủ.
- Retrieval và generation được score riêng.
- Có threshold theo domain, không chỉ aggregate score.
- CI block critical regression.
- Nightly/full eval report được review.
- Online feedback gắn với trace.
- Có quy trình update golden set khi corpus hoặc product scope đổi.

Không nên claim production-ready nếu:

- Không có golden set versioned.
- Chỉ test bằng vài câu hỏi thủ công.
- Không có no-answer/ACL/security cases.
- Không log prompt/model/index version.
- Không có rollback/canary plan.

## Checklist Cuối Bài

- [ ] Tôi có golden set tối thiểu 30 cases.
- [ ] Mỗi case có expected behavior, expected chunks và tags.
- [ ] Tôi đo retrieval metrics riêng.
- [ ] Tôi đo format/citation/no-answer riêng.
- [ ] Tôi có threshold config cho CI.
- [ ] Tôi có report theo tags.
- [ ] Tôi có trace cho từng eval case.
- [ ] Tôi biết khi nào block deploy, khi nào canary.
