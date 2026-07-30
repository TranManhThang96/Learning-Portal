# Day 27 Document: Production Reference Cho LoRA/QLoRA

## 1. Recommended Project Layout

```text
day27/
  data/
    support_sft.jsonl
  scripts/
    train_lora_sft.py
    infer_adapter.py
    merge_adapter.py
  artifacts/
    support-lora-v1/
      adapter_config.json
      adapter_model.safetensors
      tokenizer.json
      training_metadata.json
```

Trong repo học này, bạn có thể đặt script ở nơi bạn muốn. Điều quan trọng là artifact phải đủ thông tin để người khác reproduce.

## 2. Dataset Contract

Mỗi dòng JSONL:

```json
{"id":"billing_001","group_id":"billing_duplicate_charge_001","split":"train","messages":[{"role":"user","content":"Khách muốn hoàn tiền vì bị tính phí 2 lần."},{"role":"assistant","content":"{\"category\":\"billing\",\"priority\":\"high\",\"answer\":\"Mình đã ghi nhận yêu cầu hoàn tiền do bị tính phí hai lần. Vui lòng cung cấp mã giao dịch để mình kiểm tra và xử lý tiếp.\"}"}]}
```

Yêu cầu:

- File là UTF-8 JSONL, một example mỗi dòng.
- Mỗi example có `messages`.
- Role hợp lệ: `system`, `user`, `assistant`.
- Có ít nhất một `user` và một `assistant`.
- Nếu assistant phải trả JSON, content phải parse được bằng `json.loads`.
- Dùng nguyên `split` và `group_id` từ Day 26; `test` chỉ dành cho Day 28.
- Không trộn example test vào train.

Script bên dưới triển khai track `customer_support` của bài học và yêu cầu assistant JSON có đúng ba key `category`, `priority`, `answer`. Nếu Day 26 bạn chọn code review, technical writing hoặc internal policy Q&A, hãy thay validator/output contract trước khi train; không nới validator chỉ để data sai lọt qua.

## 3. Training Script Gần Production

Script dưới đây ưu tiên tính rõ ràng và reproducibility. Với dataset lớn, hãy tách thành file `.py` thật, thêm logging/MLflow/W&B và evaluation script riêng ở Day 28.

Compatibility notes trước khi chạy:

- Pin version của `transformers`, `peft`, `trl`, `datasets`, `accelerate`, `bitsandbytes` và base model revision. Fine-tuning rất khó debug nếu mỗi lần cài lại package lại đổi behavior.
- TRL hiện hỗ trợ `SFTTrainer(..., peft_config=...)`. Script này chuyển `messages` thành conversational prompt-completion và dùng `completion_only_loss=True`, nhờ đó mục tiêu loss là assistant cuối. `assistant_only_loss=True` chỉ nên dùng khi chat template tạo được assistant mask.
- `processing_class=tokenizer` là API hiện hành trong TRL. Một số tutorial cũ dùng tham số `tokenizer`; khi copy code từ internet, hãy đối chiếu với version bạn cài.
- `target_modules` phụ thuộc kiến trúc model. Với Qwen/LLaMA-style models, `q_proj`, `k_proj`, `v_proj`, `o_proj` thường hợp lý để bắt đầu; nếu đổi sang model khác, hãy inspect tên module trước khi train.
- Luôn in trainable parameters và lưu `adapter_config.json`. Nếu số trainable parameter bằng 0 hoặc quá khác kỳ vọng, dừng lại trước khi tốn GPU.

```python
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed
from trl import SFTConfig, SFTTrainer


@dataclass(frozen=True)
class TrainConfig:
    model_id: str = os.getenv("MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")
    model_revision: str = os.getenv("MODEL_REVISION", "main")
    data_path: str = os.getenv("DATA_PATH", "data/day27_support_sft.jsonl")
    output_dir: str = os.getenv("OUT_DIR", "artifacts/day27_support_lora_v1")
    seed: int = int(os.getenv("SEED", "42"))
    use_qlora: bool = os.getenv("USE_QLORA", "1") == "1"
    max_length: int = int(os.getenv("MAX_LENGTH", "1024"))
    num_train_epochs: float = float(os.getenv("EPOCHS", "1"))
    learning_rate: float = float(os.getenv("LR", "0.0002"))
    per_device_train_batch_size: int = int(os.getenv("BATCH_SIZE", "1"))
    gradient_accumulation_steps: int = int(os.getenv("GRAD_ACCUM", "8"))
    lora_r: int = int(os.getenv("LORA_R", "16"))
    lora_alpha: int = int(os.getenv("LORA_ALPHA", "32"))
    lora_dropout: float = float(os.getenv("LORA_DROPOUT", "0.05"))
    target_modules_csv: str = os.getenv("TARGET_MODULES", "q_proj,k_proj,v_proj,o_proj")

    @property
    def target_modules(self) -> list[str]:
        modules = [item.strip() for item in self.target_modules_csv.split(",") if item.strip()]
        if not modules:
            raise ValueError("TARGET_MODULES must contain at least one module name")
        return modules


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d .-]{8,}\d)")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}. Run Day 26 preparation first; do not train on fallback sample data."
        )

    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} is not valid JSON") from exc
    return rows


def validate_row(row: dict[str, Any], index: int) -> None:
    for field in ("id", "group_id", "split"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise ValueError(f"row {index}: {field} must be a non-empty string")
    if row["split"] not in {"train", "validation", "test"}:
        raise ValueError(f"row {index}: invalid split {row['split']!r}")

    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"row {index}: messages must be a non-empty list")

    roles = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError(f"row {index}: message must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"row {index}: invalid role {role!r}")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"row {index}: content must be a non-empty string")
        if EMAIL_RE.search(content) or PHONE_RE.search(content):
            raise ValueError(f"row {index}: possible PII detected")
        roles.append(role)

    if "user" not in roles or "assistant" not in roles:
        raise ValueError(f"row {index}: must include at least one user and one assistant message")
    if roles[-1] != "assistant":
        raise ValueError(f"row {index}: last message must be assistant")

    assistant_content = next(message["content"] for message in reversed(messages) if message["role"] == "assistant")
    try:
        parsed = json.loads(assistant_content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"row {index}: assistant content must be JSON") from exc

    required = {"category", "priority", "answer"}
    if set(parsed) != required:
        raise ValueError(f"row {index}: assistant JSON keys must be {sorted(required)}")


def split_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    group_splits: dict[str, set[str]] = {}
    for row in rows:
        group_splits.setdefault(row["group_id"], set()).add(row["split"])
    leaked = sorted(group_id for group_id, splits in group_splits.items() if len(splits) > 1)
    if leaked:
        raise ValueError(f"group_id appears in multiple splits: {leaked[:10]}")

    train_rows = [row for row in rows if row["split"] == "train"]
    eval_rows = [row for row in rows if row["split"] == "validation"]
    test_rows = [row for row in rows if row["split"] == "test"]
    if not train_rows or not eval_rows or not test_rows:
        raise ValueError("Dataset must contain non-empty train, validation and test splits")
    return train_rows, eval_rows, test_rows


def to_prompt_completion(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt": row["messages"][:-1],
        "completion": [row["messages"][-1]],
        "example_id": row["id"],
    }


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in ("transformers", "peft", "trl", "datasets", "accelerate", "bitsandbytes"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result


def load_model_and_tokenizer(config: TrainConfig):
    if config.use_qlora and not torch.cuda.is_available():
        raise RuntimeError("USE_QLORA=1 requires a supported CUDA environment for this hands-on")

    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id,
        revision=config.model_revision,
        use_fast=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    if config.use_qlora:
        compute_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
        )

    model = AutoModelForCausalLM.from_pretrained(
        config.model_id,
        revision=config.model_revision,
        quantization_config=quantization_config,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32,
    )

    if config.use_qlora:
        model = prepare_model_for_kbit_training(model)

    return model, tokenizer


def write_metadata(
    config: TrainConfig,
    train_size: int,
    eval_size: int,
    test_size: int,
    output_dir: Path,
) -> None:
    data_path = Path(config.data_path)
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config),
        "dataset": {
            "train_size": train_size,
            "eval_size": eval_size,
            "reserved_test_size": test_size,
            "data_path": config.data_path,
            "sha256": file_sha256(data_path),
        },
        "environment": {
            "torch": torch.__version__,
            "packages": package_versions(),
            "cuda_available": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "notes": [
            "This directory stores a LoRA adapter, not a full merged model.",
            "Load with the same base model id/revision before inference.",
            "Run regression evaluation before merge or deploy.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "training_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    config = TrainConfig()
    set_seed(config.seed)

    rows = load_jsonl(Path(config.data_path))
    for index, row in enumerate(rows):
        validate_row(row, index)
    train_rows, eval_rows, test_rows = split_rows(rows)

    train_ds = Dataset.from_list([to_prompt_completion(row) for row in train_rows])
    eval_ds = Dataset.from_list([to_prompt_completion(row) for row in eval_rows])

    model, tokenizer = load_model_and_tokenizer(config)

    peft_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        target_modules=config.target_modules,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )

    training_args = SFTConfig(
        output_dir=config.output_dir,
        seed=config.seed,
        data_seed=config.seed,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        max_length=config.max_length,
        packing=False,
        completion_only_loss=True,
        assistant_only_loss=False,
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=20,
        save_strategy="epoch",
        save_total_limit=2,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        peft_config=peft_config,
        processing_class=tokenizer,
    )

    trainer.model.print_trainable_parameters()
    trainer.train()
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    write_metadata(
        config,
        len(train_rows),
        len(eval_rows),
        len(test_rows),
        Path(config.output_dir),
    )
    print(f"saved_adapter={config.output_dir}")


if __name__ == "__main__":
    main()
```

## 4. Inference Sanity Check

Sanity check không thay thế evaluation ở Day 28. Nó chỉ đảm bảo artifact load được và output có hình dạng đúng.

```python
from __future__ import annotations

import json

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


BASE_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_DIR = "artifacts/day27_support_lora_v1"


def main() -> None:
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    model = PeftModel.from_pretrained(base, ADAPTER_DIR)
    model.eval()

    messages = [{"role": "user", "content": "Khách báo bị trừ tiền nhưng đơn hàng chưa tạo."}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=160,
            do_sample=False,
            temperature=None,
            top_p=None,
        )

    generated = tokenizer.decode(output_ids[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
    print(generated)

    try:
        parsed = json.loads(generated)
    except json.JSONDecodeError:
        raise SystemExit("Sanity check failed: output is not valid JSON")

    missing = {"category", "priority", "answer"} - set(parsed)
    if missing:
        raise SystemExit(f"Sanity check failed: missing keys {sorted(missing)}")


if __name__ == "__main__":
    main()
```

## 5. Merge Adapter Notes

Merge khi serving stack cần single model artifact hoặc bạn muốn giảm complexity runtime.

```python
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base_id = "Qwen/Qwen2.5-0.5B-Instruct"
adapter_dir = "artifacts/day27_support_lora_v1"
merged_dir = "artifacts/day27_support_merged_v1"

tokenizer = AutoTokenizer.from_pretrained(base_id, use_fast=True)
base = AutoModelForCausalLM.from_pretrained(
    base_id,
    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" if torch.cuda.is_available() else None,
)
model = PeftModel.from_pretrained(base, adapter_dir)
merged = model.merge_and_unload()
merged.save_pretrained(merged_dir, safe_serialization=True)
tokenizer.save_pretrained(merged_dir)
```

Sau khi merge:

- Chạy lại inference sanity check trên merged model.
- Chạy regression eval trước/sau.
- Ghi rõ merged artifact được tạo từ base model nào và adapter nào.
- Không xóa adapter gốc nếu chưa có rollback plan.

## 6. Best Solution Theo Context

| Context | Best first move | Khi nào nâng cấp |
|---|---|---|
| Output JSON hay sai format | Prompt + schema validation + retry | Fine-tune nếu failure lặp lại và prompt quá dài/đắt |
| Thiếu facts mới/private docs | RAG/tool | Fine-tune chỉ để chuẩn hóa wording/workflow |
| Tone support không đồng nhất | LoRA nhỏ | Tăng `r` hoặc data khi eval cho thấy underfit |
| GPU giới hạn, muốn train 7B | QLoRA | Chuyển LoRA bf16 nếu có GPU đủ và cần speed |
| Multi-domain adapters | Giữ adapter riêng | Merge khi domain cố định và serving không support adapter |
| Traffic lớn, task hẹp | Fine-tune/distill model nhỏ | Chỉ deploy khi latency/cost tốt hơn baseline |

## 7. Production Readiness Checklist

- [ ] Dataset có owner, version, license và privacy review.
- [ ] Có baseline prompt/RAG/tool để so sánh.
- [ ] Có train/validation/test split bằng seed cố định.
- [ ] Có golden eval set độc lập.
- [ ] Training config có seed, model id, revision, `max_length`, LoRA config và package versions.
- [ ] Adapter artifact có metadata.
- [ ] Inference sanity check pass.
- [ ] Regression eval pass.
- [ ] Safety eval pass với prompt injection, refusal, toxic output và data leakage.
- [ ] License base model cho phép use case production.
- [ ] Benchmark latency, throughput, VRAM/RAM và cost.
- [ ] Có rollback path về adapter cũ hoặc base model.
- [ ] Monitoring có format accuracy, error rate, user feedback và drift signal.

## 8. Tài Liệu Tham Khảo

Đối chiếu ngày 2026-06-08 qua Context7, sau đó kiểm tra lại tag chính thức TRL `v1.0.0`. Nếu dùng version khác, đọc migration/changelog trước khi chạy.

- TRL `SFTTrainer`, dataset format, `processing_class`, `completion_only_loss`, `assistant_only_loss`: https://huggingface.co/docs/trl/v1.0.0/en/sft_trainer
- TRL PEFT/QLoRA integration: https://huggingface.co/docs/trl/v1.0.0/en/peft_integration
- PEFT LoRA API: https://huggingface.co/docs/peft/main/en/package_reference/lora
- Transformers bitsandbytes quantization: https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes
- LoRA paper: https://arxiv.org/abs/2106.09685
- QLoRA paper: https://arxiv.org/abs/2305.14314
