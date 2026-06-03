# Exercise: Xây Dựng RAG Eval Runner Gần Production

## Mục tiêu

Sau bài tập này bạn sẽ có một eval runner có thể dùng cho capstone Day 40:

- Đọc golden dataset dạng JSONL.
- Đọc output trace từ RAG pipeline dạng JSONL.
- Tính Hit@k, Recall@k, Precision@k, MRR và NDCG.
- Tính context recall, citation correctness và abstention accuracy.
- Xuất report theo config và theo tag.
- Dùng release gate để quyết định pass/fail.
- Chuẩn bị extension point cho RAGAS, TruLens hoặc LangSmith.

Thời lượng đề xuất: 120-180 phút.

## 1. Cấu trúc thư mục đề xuất

```text
rag-eval/
  golden/day39_golden_v1.jsonl
  runs/baseline_outputs.jsonl
  runs/candidate_outputs.jsonl
  reports/
  eval_runner.py
```

Trong repo học này, bạn có thể tạo thư mục riêng ở capstone hoặc copy code vào project RAG của bạn. Bài học này chỉ cung cấp contract và code mẫu.

## 2. Golden dataset JSONL

Tạo file `golden/day39_golden_v1.jsonl`. Mỗi dòng là một JSON object. Bạn có thể lấy 41 câu trong [document.md](./document.md) và chuyển thành JSONL.

Ví dụ 5 dòng đầu:

```jsonl
{"id":"hr_leave_001","question":"Nhân viên full-time được nghỉ phép năm bao nhiêu ngày?","expected_answer":"12 ngày phép năm.","expected_chunk_ids":["hr_leave_policy:v2026-01:chunk_003"],"relevance":{"hr_leave_policy:v2026-01:chunk_003":3},"must_cite":["hr_leave_policy:v2026-01:chunk_003"],"difficulty":"easy","tags":["hr","policy","single-hop"],"expected_behavior":"answer","user_context":{"tenant_id":"company_a","roles":["employee"]}}
{"id":"api_002","question":"Loi ERR-429 co nghia la gi?","expected_answer":"ERR-429 nghĩa là vượt rate limit; client nên backoff và retry theo header Retry-After.","expected_chunk_ids":["product_api_docs:v2026-03:chunk_004"],"relevance":{"product_api_docs:v2026-03:chunk_004":3},"must_cite":["product_api_docs:v2026-03:chunk_004"],"difficulty":"easy","tags":["api","no-diacritic","error-code"],"expected_behavior":"answer","user_context":{"tenant_id":"company_a","roles":["developer"]}}
{"id":"sales_004","question":"Có được hứa custom SLA qua email không?","expected_answer":"Không. Custom SLA phải được Legal và Support leadership duyệt trong hợp đồng.","expected_chunk_ids":["sales_handbook:v2026-01:chunk_007","support_sla_policy:v2026-01:chunk_007"],"relevance":{"sales_handbook:v2026-01:chunk_007":3,"support_sla_policy:v2026-01:chunk_007":2},"must_cite":["sales_handbook:v2026-01:chunk_007","support_sla_policy:v2026-01:chunk_007"],"difficulty":"hard","tags":["sales","sla","multi-hop"],"expected_behavior":"answer","user_context":{"tenant_id":"company_a","roles":["sales"]}}
{"id":"no_answer_001","question":"Công ty có chính sách mua xe cho nhân viên không?","expected_answer":"Không đủ thông tin trong corpus mẫu.","expected_chunk_ids":[],"relevance":{},"must_cite":[],"difficulty":"easy","tags":["no-answer","hr","abstain"],"expected_behavior":"abstain","user_context":{"tenant_id":"company_a","roles":["employee"]}}
{"id":"acl_003","question":"User company B hỏi chính sách nghỉ phép company A thì sao?","expected_answer":"Không được leak dữ liệu company A; phải chỉ dùng corpus của tenant company B hoặc nói không có quyền/thông tin.","expected_chunk_ids":["hr_leave_policy:v2026-01:chunk_003"],"relevance":{"hr_leave_policy:v2026-01:chunk_003":3},"must_cite":[],"difficulty":"hard","tags":["acl","tenant","security"],"expected_behavior":"permission_denied","user_context":{"tenant_id":"company_b","roles":["employee"]}}
```

## 3. RAG output JSONL

RAG pipeline của bạn cần xuất mỗi query thành một dòng JSON. Điều quan trọng là output phải có đủ trace để debug.

```jsonl
{"query_id":"api_002","config_id":"hybrid-rerank-v3","question":"Loi ERR-429 co nghia la gi?","retrieved_chunks":[{"chunk_id":"product_api_docs:v2026-03:chunk_004","score":0.91,"rank":1},{"chunk_id":"product_api_docs:v2026-03:chunk_002","score":0.72,"rank":2}],"context_chunks":[{"chunk_id":"product_api_docs:v2026-03:chunk_004","text_hash":"sha256:abc"}],"answer":"`ERR-429` nghĩa là vượt rate limit. Client nên backoff và retry theo header `Retry-After`.","citations":["product_api_docs:v2026-03:chunk_004"],"latency_ms":{"embed":24,"retrieve":38,"rerank":160,"generate":1320,"end_to_end":1548},"tokens":{"prompt":1840,"completion":72},"cost_usd":0.0028,"versions":{"eval_set":"day39-golden-v1","index":"rag-index-2026-05-10-bge-m3","prompt":"rag-answer-v7","generator":"gpt-4o-mini"}}
```

Nếu bạn đang dùng LangChain/LlamaIndex, hãy viết adapter để map trace framework về schema này. Đừng để eval runner phụ thuộc trực tiếp vào framework, vì retrieval metrics nên deterministic và dễ chạy trong CI.

## 4. Python eval runner

Tạo `eval_runner.py`:

```python
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


K_VALUES = (5, 10)


@dataclass(frozen=True)
class GoldenCase:
    id: str
    question: str
    expected_answer: str
    expected_chunk_ids: list[str]
    relevance: dict[str, int]
    must_cite: list[str]
    difficulty: str
    tags: list[str]
    expected_behavior: str = "answer"
    user_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldenCase":
        expected_chunk_ids = list(data.get("expected_chunk_ids") or [])
        relevance = dict(data.get("relevance") or {})
        if not relevance:
            relevance = {chunk_id: 3 for chunk_id in expected_chunk_ids}
        return cls(
            id=data["id"],
            question=data["question"],
            expected_answer=data.get("expected_answer", ""),
            expected_chunk_ids=expected_chunk_ids,
            relevance={str(k): int(v) for k, v in relevance.items()},
            must_cite=list(data.get("must_cite") or []),
            difficulty=data.get("difficulty", "unknown"),
            tags=list(data.get("tags") or []),
            expected_behavior=data.get("expected_behavior", "answer"),
            user_context=dict(data.get("user_context") or {}),
        )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}") from exc
    return rows


def chunk_ids(items: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and item.get("chunk_id"):
            ids.append(str(item["chunk_id"]))
    return ids


def has_expected_chunks(case: GoldenCase) -> bool:
    return bool(case.expected_chunk_ids)


def hit_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return 1.0 if relevant.intersection(ranked_ids[:k]) else 0.0


def recall_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return len(relevant.intersection(ranked_ids[:k])) / len(relevant)


def precision_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    denom = min(k, max(len(ranked_ids), 1))
    return len(relevant.intersection(ranked_ids[:k])) / denom


def mrr_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def dcg(relevance_scores: list[int]) -> float:
    score = 0.0
    for rank, rel in enumerate(relevance_scores, start=1):
        score += (2**rel - 1) / math.log2(rank + 1)
    return score


def ndcg_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int) -> float | None:
    if not relevance:
        return None
    ranked_relevance = [relevance.get(chunk_id, 0) for chunk_id in ranked_ids[:k]]
    ideal_relevance = sorted(relevance.values(), reverse=True)[:k]
    ideal = dcg(ideal_relevance)
    if ideal == 0:
        return None
    return dcg(ranked_relevance) / ideal


def context_recall(context_ids: list[str], relevant: set[str]) -> float | None:
    if not relevant:
        return None
    return len(relevant.intersection(context_ids)) / len(relevant)


def abstained(answer: str) -> bool:
    normalized = answer.lower()
    phrases = [
        "không đủ thông tin",
        "không tìm thấy thông tin",
        "không có thông tin",
        "không thể xác định",
        "không có quyền",
    ]
    return any(phrase in normalized for phrase in phrases)


def citation_correctness(case: GoldenCase, citations: list[str], context_ids: list[str]) -> float:
    citation_set = set(citations)
    context_set = set(context_ids)

    if case.expected_behavior in {"abstain", "permission_denied"}:
        return 1.0 if not citation_set or citation_set.issubset(context_set) else 0.0

    if not case.must_cite:
        return 1.0 if citation_set.issubset(context_set) else 0.0

    required = set(case.must_cite)
    required_covered = len(required.intersection(citation_set)) / len(required)
    citations_exist_in_context = 1.0 if citation_set.issubset(context_set) else 0.0
    return min(required_covered, citations_exist_in_context)


def behavior_score(case: GoldenCase, answer: str) -> float:
    if case.expected_behavior == "answer":
        return 0.0 if abstained(answer) else 1.0
    if case.expected_behavior in {"abstain", "permission_denied"}:
        return 1.0 if abstained(answer) else 0.0
    return 1.0


def safe_mean(values: list[float | None]) -> float | None:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def evaluate_one(case: GoldenCase, output: dict[str, Any]) -> dict[str, Any]:
    retrieved = chunk_ids(output.get("retrieved_chunks", []))
    context = chunk_ids(output.get("context_chunks", []))
    citations = chunk_ids(output.get("citations", []))
    relevant = set(case.expected_chunk_ids)
    answer = str(output.get("answer") or "")

    metrics: dict[str, float | None] = {}
    for k in K_VALUES:
        metrics[f"hit@{k}"] = hit_at_k(retrieved, relevant, k)
        metrics[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
        metrics[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
        metrics[f"mrr@{k}"] = mrr_at_k(retrieved, relevant, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(retrieved, case.relevance, k)

    metrics["context_recall"] = context_recall(context, relevant)
    metrics["citation_correctness"] = citation_correctness(case, citations, context)
    metrics["behavior_score"] = behavior_score(case, answer)

    latency = output.get("latency_ms") or {}
    metrics["latency_end_to_end_ms"] = float(latency.get("end_to_end", 0.0) or 0.0)
    metrics["cost_usd"] = float(output.get("cost_usd", 0.0) or 0.0)

    failed_checks: list[str] = []
    if has_expected_chunks(case) and metrics.get("recall@10") == 0:
        failed_checks.append("retrieval_miss")
    if metrics["context_recall"] == 0:
        failed_checks.append("context_miss")
    if metrics["citation_correctness"] < 1.0:
        failed_checks.append("bad_citation")
    if metrics["behavior_score"] < 1.0:
        failed_checks.append("wrong_behavior")

    return {
        "query_id": case.id,
        "config_id": output.get("config_id", "unknown"),
        "difficulty": case.difficulty,
        "tags": case.tags,
        "expected_behavior": case.expected_behavior,
        "metrics": metrics,
        "failed_checks": failed_checks,
        "retrieved_ids": retrieved,
        "context_ids": context,
        "citations": citations,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    metric_names = sorted({name for row in rows for name in row["metrics"]})
    return {
        metric: safe_mean([row["metrics"].get(metric) for row in rows])
        for metric in metric_names
    }


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil((p / 100) * len(ordered)) - 1)
    return ordered[index]


def aggregate_with_latency(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    summary = aggregate(rows)
    latencies = [
        row["metrics"]["latency_end_to_end_ms"]
        for row in rows
        if row["metrics"].get("latency_end_to_end_ms")
    ]
    summary["p95_latency_ms"] = percentile(latencies, 95)
    summary["failed_case_rate"] = sum(bool(row["failed_checks"]) for row in rows) / max(len(rows), 1)
    return summary


def group_by_tag(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for tag in row["tags"]:
            grouped[tag].append(row)
    return dict(grouped)


def markdown_report(results: dict[str, list[dict[str, Any]]]) -> str:
    lines: list[str] = []
    lines.append("# RAG Evaluation Report")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append("| Config | Cases | Recall@10 | MRR@10 | NDCG@10 | Context recall | Citation correctness | Behavior score | Failed case rate | p95 latency ms |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for config_id, rows in sorted(results.items()):
        summary = aggregate_with_latency(rows)
        lines.append(
            "| {config} | {cases} | {recall} | {mrr} | {ndcg} | {context} | {citation} | {behavior} | {failed} | {latency} |".format(
                config=config_id,
                cases=len(rows),
                recall=fmt(summary.get("recall@10")),
                mrr=fmt(summary.get("mrr@10")),
                ndcg=fmt(summary.get("ndcg@10")),
                context=fmt(summary.get("context_recall")),
                citation=fmt(summary.get("citation_correctness")),
                behavior=fmt(summary.get("behavior_score")),
                failed=fmt(summary.get("failed_case_rate")),
                latency=fmt(summary.get("p95_latency_ms")),
            )
        )

    lines.append("")
    lines.append("## Breakdown By Tag")
    lines.append("")
    lines.append("| Config | Tag | Cases | Recall@10 | MRR@10 | Citation correctness | Failures |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")

    for config_id, rows in sorted(results.items()):
        for tag, tag_rows in sorted(group_by_tag(rows).items()):
            summary = aggregate(tag_rows)
            failures = sum(bool(row["failed_checks"]) for row in tag_rows)
            lines.append(
                f"| {config_id} | {tag} | {len(tag_rows)} | {fmt(summary.get('recall@10'))} | {fmt(summary.get('mrr@10'))} | {fmt(summary.get('citation_correctness'))} | {failures} |"
            )

    lines.append("")
    lines.append("## Failed Queries")
    lines.append("")
    lines.append("| Config | Query ID | Expected behavior | Failed checks | Retrieved top 3 | Context IDs | Citations |")
    lines.append("|---|---|---|---|---|---|---|")

    for config_id, rows in sorted(results.items()):
        failed_rows = [row for row in rows if row["failed_checks"]]
        for row in failed_rows[:30]:
            lines.append(
                "| {config} | {query_id} | {behavior} | {checks} | {retrieved} | {context} | {citations} |".format(
                    config=config_id,
                    query_id=row["query_id"],
                    behavior=row["expected_behavior"],
                    checks=", ".join(row["failed_checks"]),
                    retrieved=", ".join(row["retrieved_ids"][:3]),
                    context=", ".join(row["context_ids"]),
                    citations=", ".join(row["citations"]),
                )
            )

    return "\n".join(lines) + "\n"


def check_release_gate(rows: list[dict[str, Any]], gates: dict[str, float]) -> tuple[bool, list[str]]:
    summary = aggregate_with_latency(rows)
    failures: list[str] = []

    for metric, threshold in gates.items():
        value = summary.get(metric)
        if value is None:
            failures.append(f"{metric}: missing")
        elif metric.endswith("_ms"):
            if value > threshold:
                failures.append(f"{metric}: {value:.3f} > {threshold}")
        elif value < threshold:
            failures.append(f"{metric}: {value:.3f} < {threshold}")

    critical_failures = [
        row for row in rows
        if "acl" in row["tags"] and row["failed_checks"]
    ]
    if critical_failures:
        failures.append(f"acl critical failures: {len(critical_failures)}")

    return not failures, failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--outputs", required=True, nargs="+", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()

    golden_cases = {
        case.id: case
        for case in [GoldenCase.from_dict(row) for row in load_jsonl(args.golden)]
    }

    results: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for output_file in args.outputs:
        for output in load_jsonl(output_file):
            query_id = output.get("query_id")
            if query_id not in golden_cases:
                raise KeyError(f"Output references unknown query_id={query_id}")
            row = evaluate_one(golden_cases[query_id], output)
            results[row["config_id"]].append(row)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown_report(results), encoding="utf-8")

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    gates = {
        "recall@10": 0.85,
        "mrr@10": 0.70,
        "citation_correctness": 0.95,
        "behavior_score": 0.90,
        "p95_latency_ms": 6000.0,
    }

    any_failed = False
    for config_id, rows in sorted(results.items()):
        passed, failures = check_release_gate(rows, gates)
        status = "PASS" if passed else "FAIL"
        print(f"{config_id}: {status}")
        for failure in failures:
            print(f"  - {failure}")
        any_failed = any_failed or not passed

    if any_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

## 5. Chạy eval

```bash
python eval_runner.py \
  --golden golden/day39_golden_v1.jsonl \
  --outputs runs/baseline_outputs.jsonl runs/candidate_outputs.jsonl \
  --report reports/day39_eval_report.md \
  --json-report reports/day39_eval_report.json
```

Trong CI, exit code `1` nghĩa là release gate fail.

## 6. Bổ sung LLM-as-judge

Custom runner ở trên cố ý không gọi LLM judge để retrieval metrics deterministic. Với generation metrics như faithfulness và answer relevance, bạn có thể thêm một bước judge sau khi đã có trace.

Pseudo interface:

```python
class JudgeClient:
    def score(self, question: str, expected_answer: str, context: str, answer: str, citations: list[str]) -> dict:
        """Return JSON scores: faithfulness, answer_relevance, answer_correctness, citation_correctness."""
        raise NotImplementedError
```

Nguyên tắc:

- Judge prompt phải versioned.
- Judge model phải versioned.
- Raw judge response phải lưu lại.
- Không dùng judge score duy nhất để debug retrieval.
- Với domain rủi ro cao, human review vẫn là gate cuối.

## 7. Optional: RAGAS

RAGAS phù hợp khi bạn đã có dataset gồm question, answer, contexts và reference answer.

```python
from ragas import evaluate
from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

metrics = [
    ContextPrecision(),
    ContextRecall(),
    Faithfulness(),
    AnswerRelevancy(),
]

result = evaluate(dataset=ragas_dataset, metrics=metrics)
scores = result.to_pandas()
```

Khi dùng trong production workflow:

- Pin version của `ragas`.
- Lưu dataset columns và raw score.
- So sánh RAGAS score với human labels trên một subset.
- Không thay thế qrels-based Recall@k/MRR/NDCG bằng LLM judge.

## 8. Optional: TruLens

TruLens hữu ích nếu bạn muốn tracing và feedback functions quanh app.

```python
from trulens.core import Feedback
from trulens.providers.openai import OpenAI

provider = OpenAI(model_engine="gpt-4o-mini")

f_groundedness = Feedback(
    provider.groundedness_measure_with_cot_reasons,
    name="Groundedness",
)

f_answer_relevance = Feedback(
    provider.relevance_with_cot_reasons,
    name="Answer Relevance",
)

f_context_relevance = Feedback(
    provider.context_relevance_with_cot_reasons,
    name="Context Relevance",
)
```

Điểm cần chú ý là selector phải lấy đúng input, output và context chunks của app. Nếu selector sai, metric nhìn có vẻ hợp lệ nhưng thật ra đang chấm sai dữ liệu.

## 9. Optional: LangSmith

LangSmith phù hợp khi pipeline dùng LangChain/LangGraph hoặc team muốn quản lý datasets, traces và experiments trong một UI.

```python
from langsmith import Client

client = Client()
dataset = client.create_dataset(dataset_name="day39-rag-golden-v1")
client.create_examples(dataset_id=dataset.id, examples=examples)

results = client.evaluate(
    target_rag_function,
    data=dataset.name,
    evaluators=[retrieval_evaluator, correctness_evaluator],
    experiment_prefix="hybrid-rerank-v3",
    max_concurrency=4,
)
```

Với CI nghiêm túc, vẫn nên export raw results về artifact của build để không phụ thuộc hoàn toàn vào UI.

## 10. Bài tập bắt buộc

1. Chuyển 41 câu golden set trong `document.md` thành JSONL.
2. Chạy RAG pipeline hiện tại của bạn với 2 configs:
   - `vector-only`
   - `hybrid-rerank`
3. Xuất trace đúng output contract.
4. Chạy `eval_runner.py`.
5. Điền eval report:
   - aggregate metrics
   - breakdown theo tag
   - top failed queries
   - root cause
   - release decision
6. Chọn 5 query fail nặng nhất và đề xuất fix cụ thể.

## 11. Bài tập nâng cao

1. Thêm `context_precision` dựa trên qrels:
   - Context chunks relevant / tổng context chunks.
2. Thêm `answer_correctness` bằng LLM-as-judge.
3. Thêm comparison report baseline vs candidate:
   - improved
   - regressed
   - unchanged
4. Thêm cache để không judge lại cùng `(question, context_hash, answer_hash)`.
5. Thêm GitHub Actions hoặc CI job:
   - smoke eval 10 câu chạy trên PR
   - full eval chạy nightly
6. Thêm test riêng cho ACL:
   - cùng câu hỏi, khác `tenant_id`
   - cùng câu hỏi, khác `roles`

## 12. Câu hỏi kiểm tra

1. Vì sao eval runner cần đọc raw trace thay vì chỉ đọc answer?
2. Nếu Recall@10 tăng nhưng faithfulness giảm, bạn debug theo thứ tự nào?
3. Vì sao no-answer cases phải có `expected_behavior = "abstain"`?
4. Khi nào citation correctness nên là release blocker?
5. Nếu LLM judge score drift sau khi đổi model judge, bạn xử lý thế nào?
6. Tại sao ACL failure phải block release dù aggregate score cao?

## 13. Đáp án production readiness

Eval runner này có thể dùng làm nền production nếu được gắn vào pipeline release thật: dataset versioned, output trace đầy đủ, threshold rõ ràng, CI artifact được lưu, LLM judge được calibration và các lỗi ACL/hallucination nghiêm trọng block release. Nó chưa đủ nếu chỉ chạy thủ công trong notebook, không có owner cho golden set, không có baseline comparison hoặc không có cách tái hiện corpus/index/prompt/model version của từng eval run.
