# Day 47 Exercise: Tạo Eval Suite Cho RAG

## Mục Tiêu

Bạn sẽ tạo một evaluation suite có thể chạy local hoặc CI cho capstone RAG app.

Kết quả mong muốn:

- `data/eval/golden_set.jsonl` tối thiểu 30 câu hỏi.
- `eval_thresholds.yaml`.
- Eval runner tạo report JSON/Markdown.
- CI gate fail khi metric dưới threshold.
- Release decision rõ: `PASS`, `CONDITIONAL PASS`, hoặc `FAIL`.

## Bài Tập 1: Tạo Golden Set 30 Cases

Phân bổ tối thiểu:

| Nhóm | Số case |
|---|---:|
| Normal single-hop | 8 |
| Synonym/paraphrase | 5 |
| Multi-hop | 4 |
| No-answer/out-of-scope | 4 |
| ACL/permission | 3 |
| Prompt injection | 3 |
| Format/citation edge case | 3 |

Record template:

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

## Bài Tập 2: Viết Metric Functions

Tạo `eval/metrics.py`:

```python
def recall_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    return len(set(retrieved_ids[:k]).intersection(expected_ids)) / len(expected_ids)


def mrr_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in expected_ids:
            return 1.0 / rank
    return 0.0


def citation_correctness(cited_chunk_ids: list[str], allowed_context_ids: set[str]) -> float:
    if not cited_chunk_ids:
        return 0.0
    valid_count = sum(chunk_id in allowed_context_ids for chunk_id in cited_chunk_ids)
    return valid_count / len(cited_chunk_ids)
```

Test metric bằng input nhỏ trước khi gọi RAG pipeline thật.

## Bài Tập 3: Eval Runner Skeleton

Tạo `scripts/evaluate.py`:

```python
import json
from pathlib import Path
from statistics import mean


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def evaluate_case(case: dict, rag_client) -> dict:
    response = rag_client.query(case["question"], roles=case.get("roles", ["employee"]))
    retrieved_ids = [chunk["chunk_id"] for chunk in response["trace"]["retrieved_chunks"]]
    cited_ids = [c["chunk_id"] for c in response.get("citations", [])]
    expected_ids = set(case.get("expected_chunk_ids", []))

    return {
        "id": case["id"],
        "tags": case["tags"],
        "recall_at_5": recall_at_k(retrieved_ids, expected_ids, 5),
        "mrr_at_10": mrr_at_k(retrieved_ids, expected_ids, 10),
        "format_pass": isinstance(response.get("answer"), str) and isinstance(response.get("citations"), list),
        "citation_correctness": citation_correctness(cited_ids, set(retrieved_ids)),
        "latency_ms": response["trace"]["latency_ms"]["total"],
    }


def summarize(results: list[dict]) -> dict:
    return {
        "case_count": len(results),
        "recall_at_5": mean(r["recall_at_5"] for r in results),
        "mrr_at_10": mean(r["mrr_at_10"] for r in results),
        "format_pass_rate": mean(float(r["format_pass"]) for r in results),
        "citation_correctness": mean(r["citation_correctness"] for r in results),
        "p95_latency_ms": sorted(r["latency_ms"] for r in results)[int(len(results) * 0.95) - 1],
    }
```

Điền `rag_client` theo API capstone của bạn. Nếu chưa có backend, mock `rag_client` để test metric trước.

## Bài Tập 4: Threshold Gate

Tạo `eval_thresholds.yaml`:

```yaml
recall_at_5: 0.80
mrr_at_10: 0.70
citation_correctness: 0.95
format_pass_rate: 0.98
no_answer_accuracy: 0.90
prompt_injection_block_rate: 1.00
acl_leak_count: 0
p95_latency_ms: 5000
```

Gate logic:

```python
def check_thresholds(summary: dict, thresholds: dict) -> list[str]:
    failures = []
    for metric, threshold in thresholds.items():
        current = summary.get(metric)
        if current is None:
            failures.append(f"Missing metric: {metric}")
            continue
        if metric.endswith("_count"):
            if current > threshold:
                failures.append(f"{metric}={current} > {threshold}")
        elif current < threshold:
            failures.append(f"{metric}={current:.3f} < {threshold:.3f}")
    return failures
```

## Bài Tập 5: GitHub Actions Hoặc CI Tương Đương

Pseudo workflow:

```yaml
name: rag-eval-smoke

on:
  pull_request:
    paths:
      - "prompts/**"
      - "packages/rag/**"
      - "data/eval/**"

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: python scripts/evaluate.py --golden-set data/eval/golden_set_smoke.jsonl --thresholds eval_thresholds.yaml
```

## Bài Tập 6: Viết Eval Report

Tạo `evaluation_report.md` với:

- Summary metrics.
- Results by tag.
- Top 5 regressions.
- Top 5 latency/cost cases.
- Release decision.
- Known limitations.
- Next actions.

## Checklist Nộp Bài

- [ ] Golden set có đủ 30 cases và đủ tag bắt buộc.
- [ ] Eval runner chạy được với mock hoặc API thật.
- [ ] Có metrics retrieval và generation riêng.
- [ ] Có threshold gate fail process khi dưới ngưỡng.
- [ ] Có report theo tag, không chỉ aggregate.
- [ ] Có trace metadata: prompt/model/index/eval set version.
- [ ] Có decision `PASS`, `CONDITIONAL PASS` hoặc `FAIL`.
