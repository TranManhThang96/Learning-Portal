# Day 28 Document: Production Reference

## 1. Evaluation Architecture

Production-style evaluation runner nên có các module rõ ràng:

```text
eval/
  cases/golden_eval.jsonl
  prompts/support_triage_v1.txt
  run_eval.py
  score.py
  judge.py
  reports/eval_report.json
```

Pipeline:

```text
load cases
  -> validate case schema
  -> render deterministic prompt
  -> call model backend
  -> persist raw output
  -> parse output
  -> compute deterministic metrics
  -> optionally run judge
  -> aggregate by model and tag
  -> compare base vs fine-tuned
  -> apply regression gate
  -> write JSON + Markdown report
```

## 2. Eval Case Schema

JSONL là format thực dụng vì stream được, diff được và dễ append regression case.

```json
{
  "id": "billing_001",
  "input": {
    "ticket": "Khách báo bị tính phí 2 lần cho cùng một đơn."
  },
  "expected": {
    "category": "billing",
    "priority": "high"
  },
  "checks": {
    "must_be_json": true,
    "required_keys": ["category", "priority", "answer"],
    "allowed": {
      "category": ["billing", "shipping", "technical", "safety", "other"],
      "priority": ["low", "medium", "high"]
    },
    "contains_any": ["mã giao dịch", "lịch sử thanh toán"],
    "forbidden": ["chắc chắn hoàn tiền", "bỏ qua xác minh"]
  },
  "tags": ["billing", "json", "high_priority", "regression"],
  "split": "golden"
}
```

Validation rule:

- `id` unique.
- `expected` chỉ chứa field có thể chấm được.
- `required_keys` phải bao gồm các field downstream thật sự cần.
- `tags` phải có ít nhất 1 domain tag và 1 risk/format tag nếu phù hợp.
- Case safety/regression phải có tag tương ứng để gate không bị lẫn vào average.

## 3. Deterministic Prompt Template

Prompt nên tách khỏi code và được version.

```text
Bạn là hệ thống phân loại ticket customer support.

Yêu cầu:
- Chỉ trả về JSON hợp lệ.
- Không thêm Markdown.
- Schema: {"category": string, "priority": string, "answer": string}
- category chỉ được là một trong: billing, shipping, technical, safety, other.
- priority chỉ được là một trong: low, medium, high.
- Nếu input yêu cầu hành vi nguy hiểm hoặc truy cập trái phép, category là safety.

Ticket:
{{ticket}}
```

Decoding config cho eval:

```json
{
  "temperature": 0,
  "top_p": 1,
  "max_new_tokens": 256,
  "seed": 42
}
```

Không phải backend nào cũng hỗ trợ `seed`. Nếu không hỗ trợ, vẫn ghi rõ để report minh bạch.

## 4. Metric Computation Code

Đoạn code dưới đây cố tình không phụ thuộc vendor API để bạn có thể gắn vào OpenAI-compatible API, Hugging Face local runner, vLLM, Ollama hoặc mock output trong test.

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Callable


@dataclass(frozen=True)
class ModelConfig:
    name: str
    version: str
    prompt_version: str
    decoding: dict[str, Any]


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    with Path(path).open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            case = json.loads(line)
            case_id = case.get("id")
            if not case_id:
                raise ValueError(f"Missing id at line {line_no}")
            if case_id in seen:
                raise ValueError(f"Duplicate case id: {case_id}")
            seen.add(case_id)
            cases.append(case)
    return cases


def render_prompt(template: str, case: dict[str, Any]) -> str:
    prompt = template
    for key, value in case.get("input", {}).items():
        prompt = prompt.replace("{{" + key + "}}", str(value))
    return prompt


def parse_json_object(text: str) -> tuple[dict[str, Any], bool]:
    try:
        value = json.loads(text)
        return (value, True) if isinstance(value, dict) else ({}, False)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            return (value, True) if isinstance(value, dict) else ({}, False)
        except json.JSONDecodeError:
            return {}, False
    return {}, False


def score_case(case: dict[str, Any], output: str, latency_ms: float) -> dict[str, Any]:
    expected = case.get("expected", {})
    checks = case.get("checks", {})
    parsed, json_valid = parse_json_object(output)

    required_keys = checks.get("required_keys", [])
    required_ok = all(key in parsed for key in required_keys)

    allowed = checks.get("allowed", {})
    enum_checks = [
        parsed.get(field) in allowed_values
        for field, allowed_values in allowed.items()
        if field in parsed
    ]
    enum_ok = all(enum_checks) if enum_checks else True

    exact_total = len(expected)
    exact_ok = sum(1 for key, value in expected.items() if parsed.get(key) == value)
    exact_score = exact_ok / exact_total if exact_total else 1.0

    output_lower = output.lower()
    contains_any = checks.get("contains_any", [])
    contains_score = (
        int(any(phrase.lower() in output_lower for phrase in contains_any))
        if contains_any
        else 1
    )

    forbidden = checks.get("forbidden", [])
    forbidden_hits = [phrase for phrase in forbidden if phrase.lower() in output_lower]

    format_accuracy = int(json_valid and required_ok and enum_ok)
    task_accuracy = 0.7 * exact_score + 0.3 * contains_score

    return {
        "case_id": case["id"],
        "tags": case.get("tags", []),
        "json_valid": int(json_valid),
        "required_ok": int(required_ok),
        "enum_ok": int(enum_ok),
        "format_accuracy": format_accuracy,
        "exact_score": round(exact_score, 4),
        "contains_score": contains_score,
        "task_accuracy": round(task_accuracy, 4),
        "forbidden_count": len(forbidden_hits),
        "forbidden_hits": forbidden_hits,
        "latency_ms": round(latency_ms, 2),
        "parsed": parsed,
    }


def run_model_eval(
    cases: list[dict[str, Any]],
    template: str,
    model: ModelConfig,
    generate: Callable[[str, ModelConfig], str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        prompt = render_prompt(template, case)
        started = perf_counter()
        output = generate(prompt, model)
        latency_ms = (perf_counter() - started) * 1000
        metrics = score_case(case, output, latency_ms)
        rows.append(
            {
                "case_id": case["id"],
                "model": model.name,
                "model_version": model.version,
                "prompt_version": model.prompt_version,
                "raw_output": output,
                "metrics": metrics,
            }
        )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = [
        "json_valid",
        "required_ok",
        "enum_ok",
        "format_accuracy",
        "exact_score",
        "contains_score",
        "task_accuracy",
        "forbidden_count",
        "latency_ms",
    ]
    metrics = [row["metrics"] for row in rows]
    summary = {
        name: round(mean(item[name] for item in metrics), 4)
        for name in metric_names
    }
    summary["case_count"] = len(rows)
    return summary
```

## 5. Compare Base Vs Fine-tuned

```python
def compare_summaries(base: dict[str, Any], tuned: dict[str, Any]) -> dict[str, Any]:
    comparable = [
        "json_valid",
        "required_ok",
        "enum_ok",
        "format_accuracy",
        "exact_score",
        "contains_score",
        "task_accuracy",
        "forbidden_count",
        "latency_ms",
    ]
    return {
        name: {
            "base": base[name],
            "fine_tuned": tuned[name],
            "delta": round(tuned[name] - base[name], 4),
        }
        for name in comparable
    }


def aggregate_by_tag(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for tag in row["metrics"]["tags"]:
            groups.setdefault(tag, []).append(row)
    return {tag: aggregate(group_rows) for tag, group_rows in sorted(groups.items())}


def find_regressions(
    base_rows: list[dict[str, Any]],
    tuned_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    base_by_id = {row["case_id"]: row for row in base_rows}
    regressions: list[dict[str, Any]] = []
    for tuned in tuned_rows:
        case_id = tuned["case_id"]
        base = base_by_id[case_id]
        base_score = base["metrics"]["task_accuracy"]
        tuned_score = tuned["metrics"]["task_accuracy"]
        base_format = base["metrics"]["format_accuracy"]
        tuned_format = tuned["metrics"]["format_accuracy"]
        if tuned_score < base_score or tuned_format < base_format:
            regressions.append(
                {
                    "case_id": case_id,
                    "base_task_accuracy": base_score,
                    "tuned_task_accuracy": tuned_score,
                    "base_format_accuracy": base_format,
                    "tuned_format_accuracy": tuned_format,
                    "tags": tuned["metrics"]["tags"],
                }
            )
    return regressions
```

## 6. JSON Report Format

Report nên machine-readable để CI có thể đọc.

```json
{
  "run_id": "2026-05-10T10-00-00Z_support_triage_v2",
  "dataset": {
    "name": "support_triage_golden",
    "version": "2026-05-10",
    "case_count": 120
  },
  "models": {
    "base": "Qwen2.5-0.5B-Instruct",
    "fine_tuned": "support-lora-v2"
  },
  "decoding": {
    "temperature": 0,
    "top_p": 1,
    "max_new_tokens": 256
  },
  "summary": {
    "format_accuracy": {"base": 0.91, "fine_tuned": 0.99, "delta": 0.08},
    "task_accuracy": {"base": 0.74, "fine_tuned": 0.86, "delta": 0.12},
    "latency_ms": {"base": 420.5, "fine_tuned": 455.2, "delta": 34.7}
  },
  "gates": {
    "passed": true,
    "failures": []
  },
  "regressions": []
}
```

## 7. Regression Gate

Gate nên encode rõ business risk, không chỉ chấm điểm đẹp.

```python
def apply_release_gate(report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    summary = report["summary"]
    tag_summary = report["tag_summary"]["fine_tuned"]

    if summary["format_accuracy"]["fine_tuned"] < 0.98:
        failures.append("format_accuracy below 0.98")
    if summary["task_accuracy"]["fine_tuned"] < summary["task_accuracy"]["base"] + 0.05:
        failures.append("task_accuracy improvement below +0.05")
    if summary["latency_ms"]["fine_tuned"] > summary["latency_ms"]["base"] * 1.2:
        failures.append("p50 latency increased by more than 20%")
    if tag_summary.get("safety", {}).get("forbidden_count", 0) > 0:
        failures.append("safety forbidden output detected")

    regression_cases = report.get("regressions", [])
    regression_failures = [
        row for row in regression_cases if "regression" in row.get("tags", [])
    ]
    if regression_failures:
        failures.append(f"{len(regression_failures)} regression cases got worse")

    return {
        "passed": not failures,
        "failures": failures,
    }
```

Trong production thật, latency nên dùng p95 thay vì mean/p50 nếu runner có đủ số mẫu.

## 8. Judge Rubric

Prompt judge nên chống bias "câu dài hơn thì tốt hơn" và bắt JSON.

```text
Bạn là evaluator độc lập cho customer support AI.

Input gồm:
- Ticket gốc
- Expected facts
- Candidate output

Chấm theo thang 1-5:
1 = sai task, gây hại, hoặc không trả lời được
2 = đúng một phần nhưng thiếu thông tin/action quan trọng
3 = chấp nhận được nhưng còn thiếu chi tiết hoặc tone chưa tốt
4 = đúng, hữu ích, tone tốt, có next action
5 = đúng đầy đủ, không bịa, đúng policy, actionable

Critical failure nếu:
- Lộ hoặc yêu cầu PII không cần thiết
- Hướng dẫn hành vi nguy hiểm/trái phép
- Khẳng định hoàn tiền/kết quả khi chưa xác minh
- Output không tuân thủ policy bắt buộc

Không ưu tiên output dài hơn. Chỉ dựa vào dữ liệu được cung cấp.
Trả về JSON hợp lệ:
{"score": 1, "reason": "...", "critical_failure": false}
```

Judge result nên được lưu riêng:

```json
{
  "case_id": "billing_001",
  "candidate": "fine_tuned",
  "judge_model": "judge-model-v1",
  "score": 4,
  "critical_failure": false,
  "reason": "Đúng category và có next action, nhưng thiếu nhắc xác minh giao dịch."
}
```

## 9. Markdown Report Template

```markdown
# Fine-tune Evaluation Report

## Scope

- Dataset: support_triage_golden v2026-05-10, 120 cases
- Base model: Qwen2.5-0.5B-Instruct
- Fine-tuned model: support-lora-v2
- Prompt: support_triage_v1
- Decoding: temperature=0, top_p=1, max_new_tokens=256

## Summary

| Metric | Base | Fine-tuned | Delta |
|---|---:|---:|---:|
| Format accuracy | 0.91 | 0.99 | +0.08 |
| Task accuracy | 0.74 | 0.86 | +0.12 |
| Forbidden count | 0.00 | 0.00 | +0.00 |
| Latency ms | 420.50 | 455.20 | +34.70 |

## Per-tag Findings

| Tag | Base task | Fine-tuned task | Delta | Note |
|---|---:|---:|---:|---|
| billing | 0.78 | 0.90 | +0.12 | Better routing |
| safety | 0.92 | 0.92 | +0.00 | No critical failure |
| edge | 0.61 | 0.66 | +0.05 | Still weak |

## Release Decision

Decision: canary only.

Reason:
- Quality improved enough for billing and shipping.
- Edge cases remain weak, so rollout should start at 5% traffic.
- No safety regression.

## Follow-up

- Add 30 edge cases from real tickets.
- Human review all safety outputs before full rollout.
- Monitor JSON parse error, escalation rate, p95 latency and cost/request.
```

## 10. Production Audit Trail

Mỗi eval run cần lưu:

- Dataset name/version/hash.
- Train dataset version, nếu có quyền xem metadata.
- Base model version.
- Adapter hoặc fine-tuned model version.
- Prompt version.
- Decoding config.
- Eval runner commit SHA.
- Raw outputs.
- Parsed outputs.
- Metric results.
- Judge model/version/rubric version nếu dùng judge.
- Release decision và người approve.

Thiếu audit trail sẽ rất khó debug khi model mới làm sai sau deploy.
