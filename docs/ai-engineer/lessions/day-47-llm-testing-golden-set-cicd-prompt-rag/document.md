# Day 47 Document: Eval Design Reference

## 1. Golden Set Schema

```json
{
  "id": "q001",
  "question": "string",
  "expected_answer": "string|null",
  "expected_chunk_ids": ["chunk_id"],
  "must_cite": ["doc_id"],
  "expected_behavior": "answer_with_citation|no_answer|refuse|escalate",
  "tags": ["hr", "easy"],
  "difficulty": "easy|medium|hard",
  "notes": "optional reviewer note"
}
```

Validation rules:

- `id` unique.
- `question` không rỗng.
- `expected_behavior` nằm trong enum.
- `expected_chunk_ids` bắt buộc với `answer_with_citation`.
- `tags` có ít nhất một domain tag và một difficulty tag.
- Không đưa PII thật vào golden set public.

## 2. Metric Formulas

```python
def hit_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    return float(bool(set(retrieved_ids[:k]).intersection(expected_ids)))


def recall_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    return len(set(retrieved_ids[:k]).intersection(expected_ids)) / len(expected_ids)


def mrr_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in expected_ids:
            return 1.0 / rank
    return 0.0
```

## 3. Eval Report Template

```markdown
# RAG Evaluation Report

Date:
Git SHA:
Eval set version:
Corpus version:
Index version:
Prompt version:
LLM model:
Embedding model:
Reranker:

## Summary

| Metric | Current | Baseline | Threshold | Status |
|---|---:|---:|---:|---|
| Recall@5 |  |  |  |  |
| MRR@10 |  |  |  |  |
| Citation correctness |  |  |  |  |
| Format pass rate |  |  |  |  |
| No-answer accuracy |  |  |  |  |
| Prompt injection block rate |  |  |  |  |
| ACL leak count |  |  |  |  |
| p95 latency ms |  |  |  |  |

## Results By Tag

| Tag | Cases | Pass rate | Main failures |
|---|---:|---:|---|

## Top Regressions

| Case | Expected | Actual | Suspected layer | Owner |
|---|---|---|---|---|

## Release Decision

Decision: PASS / CONDITIONAL PASS / FAIL

Reason:
Mitigation:
Rollback plan:
```

## 4. Threshold Config Mẫu

```yaml
critical:
  acl_leak_count:
    max: 0
  prompt_injection_block_rate:
    min: 1.0
  format_pass_rate:
    min: 0.98

quality:
  recall_at_5:
    min: 0.80
  mrr_at_10:
    min: 0.70
  citation_correctness:
    min: 0.95
  no_answer_accuracy:
    min: 0.90

operations:
  p95_latency_ms:
    max: 5000
  estimated_cost_per_request_usd:
    max: 0.02
```

## 5. CI Gate Strategy

| Change type | Required eval |
|---|---|
| Prompt wording nhỏ | Smoke generation + schema/citation |
| Chunking strategy | Full retrieval eval + generation sample |
| Embedding model | Full retrieval eval |
| Reranker | Retrieval/ranking eval + latency |
| Guardrail policy | Security/no-answer/ACL eval |
| LLM provider/model | Full generation eval + cost/latency |
| Corpus update | Targeted eval cho affected docs |

## 6. Failure Triage

| Symptom | Likely layer | Debug evidence |
|---|---|---|
| Expected chunk không vào top K | Retriever/chunking/embedding | retrieved IDs, scores |
| Chunk đúng vào top K nhưng answer sai | Prompt/generator/context builder | prompt trace, final context |
| Citation không hợp lệ | Generator/citation parser | citations vs context IDs |
| No-answer case vẫn trả lời | Policy/prompt/guardrail | policy decision, context score |
| ACL case leak | Retrieval filter/auth | tenant/roles/query filter |
| Format fail | Prompt/schema/model | raw output, validation error |
| Latency tăng | Reranker/LLM/retry | stage latency |

## 7. Anti-Patterns

- Chỉ đo answer quality, không đo retrieval.
- Tuning prompt trực tiếp trên test set rồi báo score cao.
- Snapshot full free-form answer.
- Không version corpus/index/prompt/model.
- Không có negative cases.
- Không có trace cho từng eval row.
- Dùng LLM-as-judge nhưng không calibration.
- CI quá chậm nên team bỏ qua.
