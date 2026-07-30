# Document: Production Reference cho Instruction Tuning Dataset

## 1. Cấu trúc thư mục khuyến nghị

```text
instruction_dataset/
  raw/
    human_seed.jsonl
    synthetic_candidates.jsonl
  processed/
    dataset_clean.jsonl
    dataset_split.jsonl
  reports/
    validation_report.md
    review_sample.md
  dataset_card.md
  metadata.json
  prepare_dataset.py
```

Nguyên tắc:

- `raw/` giữ dữ liệu gốc đã được phép xử lý, nhưng không commit PII/secret.
- `processed/` là dữ liệu đã normalize, redact, dedup và split.
- `reports/` lưu kết quả validation, lỗi bị loại, sample cần human review.
- `dataset_card.md` giải thích mục đích, nguồn, license, privacy, known limitations.
- `metadata.json` gắn dataset version với model/adapters ở Day 27.

## 2. Canonical JSONL schema

Mỗi dòng là một JSON object.

```json
{"id":"support_000001","domain":"customer_support","task":"billing_reply","source":"human_seed","quality_score":5,"pii_status":"clean","license":"internal_training_allowed","group_id":"ticket_family_000001","messages":[{"role":"system","content":"You are a support assistant for a SaaS product. Answer in Vietnamese, concise, and do not promise refunds without billing verification."},{"role":"user","content":"Tôi bị tính phí 2 lần sau khi upgrade."},{"role":"assistant","content":"Mình xin lỗi vì bất tiện này. Mình sẽ kiểm tra giao dịch upgrade và chuyển ticket sang billing nếu có dấu hiệu tính phí trùng. Bạn vui lòng gửi mã hóa đơn hoặc thời điểm giao dịch, không gửi số thẻ."}]}
```

Required fields:

- `id`: unique stable id.
- `domain`: domain của dataset.
- `task`: task cụ thể.
- `source`: `human_seed`, `synthetic_reviewed`, `production_redacted`.
- `quality_score`: integer 1-5.
- `pii_status`: `clean`, `redacted`, `needs_review`.
- `license`: quyền dùng data.
- `group_id`: dùng cho grouped split.
- `messages`: list message với role hợp lệ.

Allowed roles: `system`, `user`, `assistant`.

Role order hợp lệ:

- Optional first `system`.
- Sau đó phải là cặp `user -> assistant`.
- Record phải kết thúc bằng `assistant`.
- Không có `assistant` rỗng.

## 3. Script chuẩn bị dataset gần production

Script dưới đây dùng Python standard library để dễ chạy. Nó validate schema, normalize record, redact PII phổ biến, deduplicate, split theo `group_id` và xuất dataset card/metadata cơ bản. Script fail closed: nếu có schema/parse error, nó vẫn ghi report để debug nhưng không xuất file training.

Mỗi run nên dùng một `out-dir` mới có version/run id. Failed run không được xóa artifact cũ, nên đừng suy luận thành công chỉ vì `dataset_split.jsonl` từ run trước vẫn tồn tại; luôn kiểm tra exit code, `input_sha256` và `automated_checks_passed`.

Lưu thành `instruction_dataset/prepare_dataset.py`, đặt input ở `raw/input.jsonl`, rồi chạy:

```bash
python3 prepare_dataset.py --input raw/input.jsonl --out-dir processed --dataset-name support_instruction_v1
```

```python
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_ROLES = {"system", "user", "assistant"}
ALLOWED_PII_STATUS = {"clean", "redacted", "needs_review"}
ALLOWED_SOURCES = {"human_seed", "synthetic_reviewed", "production_redacted"}
ALLOWED_LICENSES = {"internal_training_allowed", "public_commercial_allowed", "research_only"}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d .-]{8,}\d)\b")
API_KEY_RE = re.compile(r"\b(?:sk|pk|api|token|key)[-_]?[A-Za-z0-9]{16,}\b", re.IGNORECASE)
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
WHITESPACE_RE = re.compile(r"[ \t]+")


@dataclass
class PreparedDataset:
    rows: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]
    counters: Counter[str]


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {line_no}: row must be an object")
            continue
        value["_line_no"] = line_no
        rows.append(value)
    return rows, errors


def normalize_text(text: str) -> str:
    text = CONTROL_CHARS_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(WHITESPACE_RE.sub(" ", part).strip() for part in text.split("\n"))
    return text.strip()


def redact_pii(text: str) -> tuple[str, bool]:
    original = text
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = API_KEY_RE.sub("[SECRET]", text)
    text = CREDIT_CARD_RE.sub("[CARD]", text)
    return text, text != original


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_messages(row: dict[str, Any], row_id: str) -> list[str]:
    errors: list[str] = []
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        return [f"{row_id}: messages must be a non-empty list"]

    roles: list[str] = []
    for idx, message in enumerate(messages):
        if not isinstance(message, dict):
            errors.append(f"{row_id}: messages[{idx}] must be an object")
            continue
        role = message.get("role")
        content = message.get("content")
        if role not in ALLOWED_ROLES:
            errors.append(f"{row_id}: messages[{idx}].role is invalid: {role!r}")
        if not isinstance(content, str) or not content.strip():
            errors.append(f"{row_id}: messages[{idx}].content is empty")
        roles.append(role)

    start = 1 if roles and roles[0] == "system" else 0
    expected = "user"
    for idx in range(start, len(roles)):
        if roles[idx] != expected:
            errors.append(f"{row_id}: expected role {expected!r} at messages[{idx}], got {roles[idx]!r}")
            break
        expected = "assistant" if expected == "user" else "user"
    if roles and roles[-1] != "assistant":
        errors.append(f"{row_id}: last message must be assistant")
    return errors


def validate_required_fields(row: dict[str, Any]) -> list[str]:
    row_id = str(row.get("id") or f"line_{row.get('_line_no', 'unknown')}")
    errors: list[str] = []
    required_string_fields = ["id", "domain", "task", "source", "pii_status", "license", "group_id"]
    for field in required_string_fields:
        if not isinstance(row.get(field), str) or not row[field].strip():
            errors.append(f"{row_id}: {field} must be a non-empty string")

    quality_score = row.get("quality_score")
    if not isinstance(quality_score, int) or not 1 <= quality_score <= 5:
        errors.append(f"{row_id}: quality_score must be an integer from 1 to 5")
    if row.get("source") not in ALLOWED_SOURCES:
        errors.append(f"{row_id}: source must be one of {sorted(ALLOWED_SOURCES)}")
    if row.get("pii_status") not in ALLOWED_PII_STATUS:
        errors.append(f"{row_id}: pii_status must be one of {sorted(ALLOWED_PII_STATUS)}")
    if row.get("license") not in ALLOWED_LICENSES:
        errors.append(f"{row_id}: license must be one of {sorted(ALLOWED_LICENSES)}")
    errors.extend(validate_messages(row, row_id))
    return errors


def canonical_training_text(row: dict[str, Any]) -> str:
    parts = []
    for message in row["messages"]:
        parts.append(f"{message['role']}:{normalize_text(message['content']).lower()}")
    return "\n".join(parts)


def normalize_and_redact_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    clean = {key: value for key, value in row.items() if not key.startswith("_")}
    redacted_any = False
    for key in ["id", "domain", "task", "source", "pii_status", "license", "group_id"]:
        if isinstance(clean.get(key), str):
            clean[key] = normalize_text(clean[key])
    normalized_messages = []
    for message in clean["messages"]:
        content = normalize_text(message["content"])
        content, redacted = redact_pii(content)
        redacted_any = redacted_any or redacted
        normalized_messages.append({"role": message["role"], "content": content})
    clean["messages"] = normalized_messages
    if redacted_any:
        clean["pii_status"] = "redacted"
    return clean, redacted_any


def split_by_group(rows: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["group_id"]].append(row)

    groups = list(grouped)
    if len(groups) < 3:
        raise ValueError("Need at least 3 distinct group_id values for train/validation/test")
    random.Random(seed).shuffle(groups)

    split_names = ["train", "validation", "test"]
    targets = {
        "train": len(rows) * 0.8,
        "validation": len(rows) * 0.1,
        "test": len(rows) * 0.1,
    }
    counts: Counter[str] = Counter()
    output: list[dict[str, Any]] = []

    # Seed every split with one whole group, then place each remaining group
    # into the split furthest below its target. Group integrity is never broken.
    assignments: list[tuple[str, str]] = []
    for group_id, split in zip(groups[:3], split_names, strict=True):
        assignments.append((group_id, split))
        counts[split] += len(grouped[group_id])
    for group_id in groups[3:]:
        split = max(split_names, key=lambda name: targets[name] - counts[name])
        assignments.append((group_id, split))
        counts[split] += len(grouped[group_id])

    for group_id, split in assignments:
        for row in grouped[group_id]:
            row["split"] = split
            output.append(row)
    return output


def prepare(rows: list[dict[str, Any]], parse_errors: list[str], seed: int, min_quality: int) -> PreparedDataset:
    errors = list(parse_errors)
    warnings: list[str] = []
    counters: Counter[str] = Counter()
    valid_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()

    for raw in rows:
        row_id = str(raw.get("id") or f"line_{raw.get('_line_no', 'unknown')}")
        field_errors = validate_required_fields(raw)
        if field_errors:
            errors.extend(field_errors)
            counters["invalid_schema"] += 1
            continue
        if raw["id"] in seen_ids:
            errors.append(f"{row_id}: duplicate id")
            counters["duplicate_id"] += 1
            continue
        seen_ids.add(raw["id"])

        row, redacted = normalize_and_redact_row(raw)
        if row["quality_score"] < min_quality:
            warnings.append(f"{row_id}: dropped because quality_score < {min_quality}")
            counters["dropped_low_quality"] += 1
            continue
        if row["pii_status"] == "needs_review":
            warnings.append(f"{row_id}: dropped because pii_status is needs_review")
            counters["dropped_needs_review"] += 1
            continue
        if row["license"] == "research_only":
            warnings.append(f"{row_id}: dropped because license is research_only")
            counters["dropped_license"] += 1
            continue
        if redacted:
            counters["redacted"] += 1

        digest = hashlib.sha256(canonical_training_text(row).encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            warnings.append(f"{row_id}: dropped exact duplicate")
            counters["dropped_duplicate"] += 1
            continue
        seen_hashes.add(digest)
        valid_rows.append(row)

    try:
        split_rows = split_by_group(valid_rows, seed)
    except ValueError as exc:
        errors.append(str(exc))
        split_rows = []
    counters.update(Counter(row["split"] for row in split_rows))
    return PreparedDataset(rows=split_rows, errors=errors, warnings=warnings, counters=counters)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def write_report(path: Path, result: PreparedDataset) -> None:
    lines = ["# Validation Report", ""]
    lines.append("## Counters")
    for key, value in sorted(result.counters.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Errors"])
    lines.extend(f"- {error}" for error in result.errors[:200])
    if len(result.errors) > 200:
        lines.append(f"- ... truncated {len(result.errors) - 200} more errors")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {warning}" for warning in result.warnings[:200])
    if len(result.warnings) > 200:
        lines.append(f"- ... truncated {len(result.warnings) - 200} more warnings")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_dataset_card(path: Path, dataset_name: str, result: PreparedDataset) -> None:
    split_counts = Counter(row["split"] for row in result.rows)
    source_counts = Counter(row["source"] for row in result.rows)
    task_counts = Counter(row["task"] for row in result.rows)
    lines = [
        f"# Dataset Card: {dataset_name}",
        "",
        "## Purpose",
        "Instruction tuning dataset for a domain assistant. Replace this section with the exact behavior goal before training.",
        "",
        "## Format",
        "JSONL messages format with role/content pairs and metadata fields.",
        "",
        "## Size",
        f"- total: {len(result.rows)}",
        f"- train: {split_counts.get('train', 0)}",
        f"- validation: {split_counts.get('validation', 0)}",
        f"- test: {split_counts.get('test', 0)}",
        "",
        "## Sources",
    ]
    lines.extend(f"- {source}: {count}" for source, count in sorted(source_counts.items()))
    lines.extend(["", "## Tasks"])
    lines.extend(f"- {task}: {count}" for task, count in sorted(task_counts.items()))
    lines.extend(
        [
            "",
            "## Privacy",
            "Common PII patterns were scanned/redacted. Records marked needs_review are excluded; human/privacy review is still required.",
            "",
            "## License",
            "Only rows with training-allowed licenses are included. Verify this before production use.",
            "",
            "## Known Limitations",
            "- Regex redaction does not catch every possible PII type.",
            "- Near-duplicate detection still requires human review or a stronger similarity pipeline for large datasets.",
            "- Synthetic data quality depends on seed examples and review process.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_metadata(
    path: Path,
    dataset_name: str,
    input_path: Path,
    result: PreparedDataset,
    seed: int,
) -> None:
    split_counts = Counter(row["split"] for row in result.rows)
    automated_checks_passed = (
        not result.errors
        and bool(result.rows)
        and all(split_counts.get(name, 0) > 0 for name in ("train", "validation", "test"))
    )
    metadata = {
        "dataset_name": dataset_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "input_sha256": file_sha256(input_path),
        "format": "messages_jsonl",
        "seed": seed,
        "rows": len(result.rows),
        "counters": dict(result.counters),
        "automated_checks_passed": automated_checks_passed,
        "production_ready": False,
        "production_ready_note": "Requires human quality, privacy, license, leakage and golden-eval review.",
    }
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-quality", type=int, default=4)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows, parse_errors = load_jsonl(args.input)
    result = prepare(rows, parse_errors, seed=args.seed, min_quality=args.min_quality)

    write_report(args.out_dir / "validation_report.md", result)
    write_metadata(args.out_dir / "metadata.json", args.dataset_name, args.input, result, args.seed)
    if not result.errors:
        write_jsonl(args.out_dir / "dataset_split.jsonl", result.rows)
        write_dataset_card(args.out_dir / "dataset_card.md", args.dataset_name, result)

    print(f"rows_in: {len(rows)}")
    print(f"rows_out: {len(result.rows)}")
    print(f"errors: {len(result.errors)}")
    print(f"warnings: {len(result.warnings)}")
    for key, value in sorted(result.counters.items()):
        print(f"{key}: {value}")
    if result.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

## 4. Dataset card template

```markdown
# Dataset Card: support_instruction_v1

## Purpose
Instruction tuning cho support assistant xử lý billing/account/how-to bằng tiếng Việt.

## Behavior Goal
- Trả lời ngắn gọn, lịch sự, có next step.
- Không hứa refund, mở khóa, xóa dữ liệu hoặc thay đổi billing nếu chưa có tool result.
- Escalate billing/security/legal risk.

## Format
JSONL messages format.

## Size
- Total: 500
- Train: 400
- Validation: 50
- Test: 50

## Sources
- Human seed: 50
- Synthetic reviewed: 350
- Production redacted: 100

## Privacy
- PII redacted.
- No password, OTP, API key, access token or raw customer identifier.
- Records marked needs_review are excluded.

## License and Ownership
Internal training allowed. Adapter is not approved for public release unless legal review approves.

## Quality Process
- Schema validation passed.
- Exact dedup completed before split.
- 50 random examples manually reviewed.
- 20 golden examples reserved for Day 28 eval.

## Known Limitations
- Regex redaction may miss rare PII patterns.
- Near-duplicate synthetic variants require manual review.
- Dataset teaches response behavior, not product knowledge.
```

## 5. Metadata template

```json
{
  "dataset_name": "support_instruction_v1",
  "format": "messages_jsonl",
  "version": "2026-05-10",
  "owner": "ai-engineer-course",
  "intended_model_family": "Qwen/LLaMA-compatible chat model",
  "rows": 500,
  "splits": {
    "train": 400,
    "validation": 50,
    "test": 50
  },
  "sources": {
    "human_seed": 50,
    "synthetic_reviewed": 350,
    "production_redacted": 100
  },
  "privacy": {
    "pii_redacted": true,
    "needs_review_excluded": true,
    "secret_scan_required": true
  },
  "training_allowed": true,
  "notes": "Use for behavior/style fine-tuning, not as knowledge source."
}
```

## 6. Review checklist cho production

- [ ] Có quyền train và deploy trên data.
- [ ] Không có raw PII/secret trong train/validation/test.
- [ ] `research_only` hoặc unclear license đã bị loại.
- [ ] Mọi record validate schema.
- [ ] Role order đúng và record kết thúc bằng assistant.
- [ ] Assistant response đúng policy.
- [ ] Dedup chạy trước split.
- [ ] Split theo `group_id`, không leakage giữa train và test.
- [ ] Validation/test không được dùng để viết lại prompt hoặc tune hyperparameter nhiều vòng.
- [ ] Có dataset card và metadata.
- [ ] Có model rollback plan sau Day 27.
- [ ] Có eval trước/sau fine-tune ở Day 28.

## 7. Trade-off thường gặp

| Quyết định | Lợi ích | Rủi ro | Best solution theo context |
|---|---|---|---|
| Messages format | Gần production chat API, role rõ | Token dài hơn, cần chat template | Dùng làm canonical cho chat assistant |
| Alpaca format | Đơn giản, dễ inspect | Kém multi-turn và policy role | Dùng cho single-turn task hoặc converter output |
| Synthetic nhiều | Scale nhanh, phủ edge cases | Pattern lặp, hallucinated policy | Giữ synthetic dưới kiểm soát, tag source, review sample |
| Raw production logs | Rất thực tế | PII, consent, noise, unsafe response | Chỉ dùng sau redaction, license check, quality filtering |
| Random split | Nhanh | Leakage theo ticket/document | Chỉ dùng khi không có group và dataset độc lập |
| Grouped split | Eval thật hơn | Split ratio có thể lệch | Dùng cho production dataset |
| Cắt max length thấp | Giảm VRAM/cost | Mất context multi-turn | Đo p95 token length rồi chọn limit |

## 8. Production answer

Dùng được trong production không? Có, nếu dataset pass schema validation, privacy/license review, dedup, grouped split, human review và eval trước/sau fine-tune. Nếu chỉ mới có dataset tạo nhanh từ synthetic data chưa review, nó chỉ phù hợp prototype hoặc lab.

`metadata.json` cố ý luôn để `production_ready=false`: script chỉ chứng minh automated checks, không thể tự chứng minh consent, license, policy correctness hoặc chất lượng semantic.

## 9. Nguồn đã đối chiếu

Đối chiếu ngày 2026-06-08 qua Context7 và tài liệu chính thức:

- TRL dataset formats, conversational và prompt-completion: https://huggingface.co/docs/trl/v1.0.0/en/dataset_formats
- TRL `SFTTrainer`, chat template và loss masking: https://huggingface.co/docs/trl/v1.0.0/en/sft_trainer
- Hugging Face dataset cards: https://huggingface.co/docs/hub/en/datasets-cards
- Hugging Face Datasets loading/JSON: https://huggingface.co/docs/datasets/en/loading
