# Day 15: Hugging Face Ecosystem

## Mục tiêu

Sau bài này, bạn cần làm được các việc sau:

- Hiểu vai trò của `transformers`, `datasets`, `tokenizers`, `accelerate`, Model Hub và model card.
- Biết load tokenizer/model bằng `AutoTokenizer`, `AutoModel`, `AutoModelForSequenceClassification`.
- Biết dùng `pipeline` cho prototype và raw model inference cho production control.
- Biết dùng `datasets` để load data, split data, `map` tokenizer theo batch và chuẩn bị input cho `Trainer`.
- Biết khi nào dùng `Trainer API`, khi nào cần custom training loop với `accelerate`.
- Biết đọc model card như review một third-party dependency trước khi đưa vào production.
- Viết được inference wrapper có model/tokenizer loading, device handling, batching, truncation, error handling và output schema rõ ràng.

## TL;DR

Hugging Face là ecosystem giúp bạn dùng model AI giống cách Senior Software Engineer dùng package registry, artifact registry và SDK. `transformers` cung cấp model/tokenizer API, `datasets` xử lý data pipeline, `tokenizers` là lõi encode text thành token IDs, `accelerate` giúp chạy PyTorch code trên CPU/GPU/multi-GPU dễ hơn, Model Hub là nơi lưu model artifact, còn model card là tài liệu rủi ro và contract của model.

Trong production, không nên chỉ gọi `from_pretrained()` rồi deploy. Bạn cần pin `model_id` và `revision`, đọc license, kiểm tra intended use, benchmark latency/memory, kiểm soát tokenizer/model version, log model version, có fallback/rollback và không bật `trust_remote_code=True` nếu chưa audit.

## 1. Day 15 Nằm Ở Đâu Trong Phase 2

Day 14 đã giải thích Transformer architecture: encoder-only như BERT/PhoBERT, decoder-only như GPT/LLaMA/Qwen, encoder-decoder như T5. Day 16 sẽ fine-tune PhoBERT/BERT classifier.

Day 15 trả lời câu hỏi thực dụng ở giữa:

```text
Đã hiểu Transformer rồi.
Làm sao lấy model thật, tokenizer thật, dataset thật, train/infer thật và deploy có kiểm soát?
```

Với góc nhìn Senior SE:

```text
Transformer architecture = runtime engine concept
Hugging Face ecosystem = package registry + artifact registry + SDK + data pipeline + training/runtime tooling
```

## 2. Mental Model: Hugging Face Như Artifact Platform

| Hugging Face concept | SE equivalent | Ý nghĩa production |
|---|---|---|
| Model Hub | Docker Hub, npm, Maven registry | Nơi lấy model artifact, config, tokenizer, model card |
| Model checkpoint | Build artifact | Version có thể deploy, rollback, audit |
| Revision/commit SHA | Image digest, package lock | Pin để reproducible |
| Model card | README + risk note + API contract | Kiểm tra license, intended use, limitation, metrics |
| `transformers` | SDK/client library | Load model, tokenizer, `pipeline`, `Trainer` |
| `datasets` | Data pipeline/cache layer | Load, split, transform, cache dataset |
| `tokenizers` | Parser/encoder runtime | Text contract trước khi vào model |
| `accelerate` | Runtime launcher/device abstraction | Chạy cùng code trên CPU, GPU, multi-GPU, mixed precision |

Một AI feature production thường có dependency graph như sau:

```text
business API
  -> preprocessing
  -> tokenizer version
  -> model config
  -> model weights revision
  -> postprocessing label mapping
  -> monitoring
  -> rollback path
```

Nếu tokenizer đổi nhưng model không đổi, chất lượng có thể hỏng. Nếu model đổi nhưng label mapping không đổi đúng, API vẫn trả JSON hợp lệ nhưng business decision sai. Vì vậy model không chỉ là một file weights, mà là một bundle gồm weights, tokenizer, config, preprocessing, postprocessing và governance.

## 3. Model Hub Và Model Card

Model Hub là nơi bạn tìm model như `bert-base-uncased`, `distilbert-base-uncased-finetuned-sst-2-english`, `vinai/phobert-base`, embedding model, reranker model hoặc text generation model.

Trước khi dùng một model, cần đọc model card như review dependency bên ngoài.

### Checklist đọc model card

| Mục cần kiểm tra | Câu hỏi cần trả lời | Production impact |
|---|---|---|
| License | Có được dùng commercial/internal không? Có điều kiện attribution không? | Legal/compliance |
| Intended use | Model được thiết kế cho task nào? Classification, embedding, generation, reranking? | Tránh dùng sai task |
| Limitations | Model yếu ở domain/ngôn ngữ/input nào? | Risk chất lượng |
| Language | Có hỗ trợ tiếng Việt không? Có cần word segmentation không? | Fit với user data |
| Dataset | Train/eval trên dataset nào? Có gần domain của mình không? | Generalization |
| Metrics | Metric nào, split nào, benchmark nào? | So sánh có cơ sở |
| Safety | Có bias, toxicity, privacy, misuse note không? | Risk vận hành |
| Inference requirements | Cần GPU không? VRAM bao nhiêu? Max sequence length? Có cần `trust_remote_code` không? | Cost/security/deployment |

Quy tắc ngắn: không deploy model nếu không rõ license, source, version, owner, intended use và rollback path.

## 4. `tokenizers`: Tokenizer Là Input Contract

Tokenizer biến text thành integer IDs để model xử lý:

```text
"sản phẩm tốt" -> [0, 1234, 567, 89, 2]
```

Trong production, tokenizer giống parser ở API boundary:

- Parser đổi thì input semantic vào model đổi.
- Train dùng tokenizer A nhưng serve dùng tokenizer B thì quality có thể giảm mạnh.
- `max_length` quá ngắn làm mất thông tin vì truncation.
- `max_length` quá dài làm latency và memory tăng, vì attention thường tăng theo độ dài sequence.
- Padding strategy ảnh hưởng throughput khi batching.

Các tham số quan trọng khi dùng tokenizer:

```python
encoded = tokenizer(
    texts,
    padding=True,
    truncation=True,
    max_length=128,
    return_tensors="pt",
)
```

Ý nghĩa:

- `padding=True`: pad các sample trong batch về cùng chiều dài để tensor hóa.
- `truncation=True`: cắt input vượt quá `max_length` hoặc giới hạn model.
- `max_length=128`: giới hạn token cho latency/memory predictable.
- `return_tensors="pt"`: trả PyTorch tensors.

Với tiếng Việt, cần kiểm tra model yêu cầu preprocessing gì. Một số model như PhoBERT historically thường đi kèm giả định về word segmentation ở một số workflow. Nếu train preprocessing và serving preprocessing khác nhau, bug sẽ khó thấy bằng unit test thông thường nhưng metric production sẽ giảm.

## 5. `transformers`: Auto Classes, Pipeline Và Raw Model

`transformers` cung cấp API thống nhất cho nhiều architecture. Bạn thường bắt đầu bằng Auto Classes:

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_id = "distilbert-base-uncased-finetuned-sst-2-english"
revision = "main"  # Chỉ để demo; production dùng commit SHA bất biến.

tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, use_fast=True)
model = AutoModelForSequenceClassification.from_pretrained(model_id, revision=revision)
```

### `AutoTokenizer`

`AutoTokenizer` đọc tokenizer config từ model repo và trả về tokenizer phù hợp. Đây là cách an toàn hơn việc đoán tokenizer class thủ công.

### `AutoModel`

`AutoModel` load backbone model và thường trả hidden states, chưa có task head. Dùng khi bạn cần embedding, feature extraction hoặc build head riêng.

```python
from transformers import AutoModel, AutoTokenizer

model_id = "bert-base-uncased"
revision = "main"  # Demo only; production thay bằng commit SHA.
tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
model = AutoModel.from_pretrained(model_id, revision=revision)
```

### Task-specific model

Với classification, nên dùng task-specific class:

```python
from transformers import AutoModelForSequenceClassification

model_id = "distilbert-base-uncased-finetuned-sst-2-english"
revision = "main"  # Demo only; production thay bằng commit SHA.
model = AutoModelForSequenceClassification.from_pretrained(
    model_id,
    revision=revision,
)
```

Lý do: class này biết output schema cho classification, có `logits`, có thể có `id2label`/`label2id` trong config và tích hợp tốt với `Trainer`.

## 6. `pipeline`: Nhanh Cho Prototype

`pipeline` gom tokenizer, model, preprocessing và postprocessing vào một interface đơn giản:

```python
from transformers import pipeline

classifier = pipeline(
    "text-classification",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)

print(classifier(["This product is great.", "The delivery was terrible."]))
```

Nên dùng `pipeline` khi:

- Demo nhanh.
- Notebook exploration.
- Internal script nhỏ.
- Batch job đơn giản chưa cần latency SLA chặt.

Không nên xem `pipeline` là production architecture mặc định nếu bạn cần:

- Custom request/response schema.
- Batching theo traffic thật.
- Error handling rõ.
- Timeout/fallback.
- Observability theo model version/input length/latency.
- Kiểm soát device, dtype, quantization, warmup.

## 7. Raw Model Inference: Đường Production-Controlled

Raw model path cho bạn kiểm soát rõ từng bước:

```text
validate input
  -> batch texts
  -> tokenize with truncation
  -> move tensors to device
  -> model forward under no_grad/inference_mode
  -> softmax/postprocess
  -> return stable JSON schema
  -> log metrics without leaking PII
```

Ví dụ dưới đây là wrapper gần production cho text classification. Nó không thay thế full model server, nhưng có các điểm cốt lõi: load một lần, pin revision, device handling, batching, truncation, output schema, latency, token count và error handling.

```python
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


class ModelLoadError(RuntimeError):
    pass


class InferenceInputError(ValueError):
    pass


@dataclass(frozen=True)
class ClassifierConfig:
    model_id: str = "distilbert-base-uncased-finetuned-sst-2-english"
    revision: str = "main"  # Demo default; production phải truyền commit SHA.
    max_length: int = 128
    batch_size: int = 16
    use_fast_tokenizer: bool = True
    local_files_only: bool = False


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    token_count: int


@dataclass(frozen=True)
class BatchResult:
    predictions: list[Prediction]
    model_id: str
    revision: str
    device: str
    latency_ms: float


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class TextClassifier:
    def __init__(self, config: ClassifierConfig):
        self.config = config
        self.device = pick_device()

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                config.model_id,
                revision=config.revision,
                use_fast=config.use_fast_tokenizer,
                local_files_only=config.local_files_only,
            )
            self.model = AutoModelForSequenceClassification.from_pretrained(
                config.model_id,
                revision=config.revision,
                local_files_only=config.local_files_only,
            )
        except Exception as exc:
            raise ModelLoadError(f"Cannot load model/tokenizer for {config.model_id}") from exc

        self.model.to(self.device)
        self.model.eval()

    def predict(self, texts: list[str]) -> BatchResult:
        if not texts:
            raise InferenceInputError("texts must not be empty")
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise InferenceInputError("each text must be a non-empty string")

        started = time.perf_counter()
        predictions: list[Prediction] = []

        try:
            for batch in chunked(texts, self.config.batch_size):
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_length,
                    return_tensors="pt",
                )
                token_counts = encoded["attention_mask"].sum(dim=1).tolist()
                encoded = {key: value.to(self.device) for key, value in encoded.items()}

                with torch.inference_mode():
                    outputs = self.model(**encoded)
                    probs = torch.softmax(outputs.logits, dim=-1)

                for row, token_count in zip(probs.detach().cpu(), token_counts):
                    label_id = int(torch.argmax(row).item())
                    label = self.model.config.id2label.get(label_id, str(label_id))
                    confidence = float(row[label_id].item())
                    predictions.append(
                        Prediction(
                            label=label,
                            confidence=round(confidence, 6),
                            token_count=int(token_count),
                        )
                    )
        except RuntimeError:
            logger.exception(
                "model_inference_failed",
                extra={"model_id": self.config.model_id, "revision": self.config.revision},
            )
            raise

        latency_ms = (time.perf_counter() - started) * 1000
        return BatchResult(
            predictions=predictions,
            model_id=self.config.model_id,
            revision=self.config.revision,
            device=str(self.device),
            latency_ms=round(latency_ms, 2),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    classifier = TextClassifier(ClassifierConfig(batch_size=2, max_length=128))
    result = classifier.predict(
        [
            "This product is useful and reliable.",
            "The delivery was late and support was terrible.",
        ]
    )
    print(result)
```

Production notes:

- Load model ở startup, không load trong từng request.
- Warm up bằng một request nhỏ trước khi nhận traffic thật.
- Log `model_id`, `revision`, device, latency, token count, label, confidence; tránh log raw PII.
- Pin `revision` bằng commit SHA khi cần reproducibility nghiêm túc.
- Không dùng `trust_remote_code=True` trừ khi đã audit repo model như audit dependency chạy code.

## 8. `datasets`: Data Pipeline Cho Training Và Evaluation

`datasets` giúp load dataset từ Hub hoặc local file, convert sang Arrow format/cache và apply transformation hiệu quả.

Ví dụ load CSV local cho Day 16:

```python
from datasets import load_dataset

dataset = load_dataset(
    "csv",
    data_files={"train": "train.csv", "test": "test.csv"},
)

print(dataset)
print(dataset["train"][0])
```

Nếu chỉ có một file, tạo split:

```python
from datasets import load_dataset

raw = load_dataset("csv", data_files="reviews.csv")["train"]
split = raw.train_test_split(test_size=0.2, seed=42)
```

Tokenize theo batch và convert label string sang `labels` dạng số cho `Trainer`:

```python
from transformers import AutoTokenizer

model_id = "distilbert-base-multilingual-cased"
revision = "main"  # Demo only; production thay bằng commit SHA.
tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
labels = ["negative", "neutral", "positive"]
label2id = {label: idx for idx, label in enumerate(labels)}


def tokenize_batch(examples):
    encoded = tokenizer(
        examples["text"],
        truncation=True,
        max_length=128,
    )
    encoded["labels"] = [label2id[label] for label in examples["label"]]
    return encoded


tokenized = split.map(
    tokenize_batch,
    batched=True,
    remove_columns=["text", "label"],
)
```

Vì sao `batched=True` quan trọng:

- Ít overhead Python hơn.
- Tokenizer fast chạy hiệu quả hơn trên list text.
- Dễ giữ preprocessing giống nhau giữa train/eval.

Cache note:

- Datasets cache file đã download và data đã convert để tránh làm lại.
- `map` tạo fingerprint từ dataset và transform. Nếu cần xác minh transform mới, dùng `load_from_cache_file=False` có chủ đích thay vì xóa cache tùy tiện.
- Không commit cache lớn vào repo bài học.

Với dataset lớn hơn RAM, có thể dùng `streaming=True` để nhận `IterableDataset`. Trade-off là không có random access như dataset map-style; shuffle dùng buffer và training loop phải kiểm soát epoch/step rõ. Khi cần tensor PyTorch, dùng `with_format("torch")` hoặc data collator phù hợp thay vì convert thủ công từng row.

## 9. `Trainer API`: Fine-tune Nhanh Cho Task Chuẩn

`Trainer` là training loop có sẵn cho Transformers model. Nó xử lý nhiều phần lặp lại: train/eval loop, checkpoint, logging, gradient accumulation, mixed precision, distributed training integration và metric callback.

Skeleton cho classification:

```python
import numpy as np
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

model_id = "distilbert-base-multilingual-cased"
revision = "main"  # Demo only; production thay bằng commit SHA.
labels = ["negative", "neutral", "positive"]
label2id = {label: idx for idx, label in enumerate(labels)}
id2label = {idx: label for label, idx in label2id.items()}

tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
model = AutoModelForSequenceClassification.from_pretrained(
    model_id,
    revision=revision,
    num_labels=len(labels),
    label2id=label2id,
    id2label=id2label,
)
data_collator = DataCollatorWithPadding(tokenizer=tokenizer)


def compute_metrics(eval_pred):
    logits, label_ids = eval_pred
    predictions = np.argmax(logits, axis=-1)
    accuracy = (predictions == label_ids).mean()
    return {"accuracy": float(accuracy)}


training_args = TrainingArguments(
    output_dir="artifacts/day15-checkpoints",
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=16,
    num_train_epochs=3,
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    logging_steps=20,
    load_best_model_at_end=True,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized["train"],
    eval_dataset=tokenized["test"],
    processing_class=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
)

trainer.train()
trainer.save_model("artifacts/day15-final-model")
tokenizer.save_pretrained("artifacts/day15-final-model")
```

API note: Transformers hiện hành dùng `eval_strategy` trong `TrainingArguments` và `processing_class` trong `Trainer`. Version cũ có thể dùng tên khác như `evaluation_strategy` hoặc `tokenizer`. Pin package version của project và đọc migration notes trước khi copy code giữa các version.

Dùng `Trainer` khi:

- Task là standard classification, token classification, question answering, language modeling.
- Loss không quá custom.
- Bạn muốn ship baseline fine-tune nhanh.
- Bạn muốn tận dụng logging/checkpoint/mixed precision mà không tự viết nhiều boilerplate.

Không dùng `Trainer` làm mặc định khi:

- Training loop có nhiều model hoặc nhiều loss đặc biệt.
- Cần RLHF/custom sampling/custom curriculum.
- Cần logic distributed rất riêng.
- Team đã có training framework nội bộ.

## 10. `accelerate`: Khi Cần Custom Loop Nhưng Vẫn Muốn Scale

`accelerate` giúp viết PyTorch loop gần như bình thường, nhưng chạy được trên CPU, một GPU, nhiều GPU hoặc mixed precision với ít thay đổi code.

Minimal pattern:

```python
from accelerate import Accelerator

accelerator = Accelerator(mixed_precision="fp16")

model, optimizer, train_dataloader, scheduler = accelerator.prepare(
    model,
    optimizer,
    train_dataloader,
    scheduler,
)

for batch in train_dataloader:
    optimizer.zero_grad(set_to_none=True)
    outputs = model(**batch)
    loss = outputs.loss
    accelerator.backward(loss)
    optimizer.step()
    scheduler.step()
```

Điểm cần nhớ:

- Sau `accelerator.prepare(...)`, model/dataloader/optimizer đã được đặt đúng device/distributed setup.
- Dùng `accelerator.backward(loss)` thay vì `loss.backward()`.
- Dùng `accelerator.print(...)` để tránh nhiều process cùng print.
- Dùng `Trainer` trước nếu task chuẩn; chuyển sang `accelerate` khi bạn cần custom loop nhưng vẫn muốn scale.

## 11. Trade-off Quan Trọng

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Production note |
|---|---|---|---|
| `pipeline` | Prototype, demo, notebook, batch nhỏ | API có SLA, cần schema/control/observability chặt | Nhanh để học, ít control |
| Raw model inference | Production API, custom batching, custom output | POC quá sớm, team chưa cần control | Cần tự viết postprocess/error handling |
| `Trainer` | Standard fine-tune Transformer | Custom loss/loop phức tạp | Tốt cho v1 và Day 16 |
| Custom loop + `accelerate` | Cần logic training riêng, multi-GPU control | Task chuẩn mà `Trainer` đã đủ | Tăng flexibility nhưng tăng code |
| Local self-host | Data sensitive, cần kiểm soát cost/latency lâu dài | Team thiếu ops, traffic thấp, GPU đắt | Cần serving, monitoring, scaling |
| Hosted inference | Muốn go-live nhanh, không muốn vận hành GPU | Data nhạy cảm, cost/request cao, cần SLA riêng | Kiểm tra data policy/SLA |
| CPU | Traffic thấp, model nhỏ, cost-sensitive | Realtime high throughput với model lớn | Dễ vận hành, latency cao hơn GPU |
| GPU | Throughput cao, batch tốt, model lớn | Traffic thấp, request rải rác | Cần batching/warmup để đáng tiền |
| Batch size lớn | Tăng throughput, tận dụng GPU | SLA per-request chặt | Tăng queueing latency và memory |
| Batch size nhỏ | Latency thấp, traffic realtime | GPU bị underutilized | Dễ predict latency hơn |
| Quantization | Giảm VRAM/cost, tăng khả năng chạy local | Chưa có regression eval, task quality-sensitive | INT8/INT4 cần benchmark chất lượng |
| Public model license thoáng | Prototype và một số production use | License mơ hồ hoặc hạn chế commercial | Luôn lưu bằng chứng review license |
| `trust_remote_code=True` | Model bắt buộc custom code và đã audit | Chưa audit repo/model owner | Supply-chain risk như chạy code bên thứ ba |

## 12. Quantization Overview

Quantization là giảm precision của weights/activation, ví dụ từ FP32/FP16 xuống INT8 hoặc INT4, để giảm memory và đôi khi tăng tốc inference.

Tư duy thực tế:

- FP32: dễ tương thích, tốn RAM/VRAM.
- FP16/BF16: phổ biến trên GPU, giảm memory, thường ít giảm chất lượng.
- INT8: thường hợp lý cho CPU/GPU inference nếu có benchmark.
- INT4: tiết kiệm mạnh cho LLM lớn, nhưng cần kiểm tra quality regression kỹ hơn.

Không nên quantize chỉ vì thấy tiết kiệm. Cần đo:

- Accuracy/F1 hoặc metric business trước và sau quantization.
- p50/p95 latency.
- RAM/VRAM peak.
- Throughput theo batch size.
- Error cases có tăng không.

## 13. Model License Và Security

Model là dependency có thể kéo theo rủi ro:

- License không cho commercial use.
- Dataset train có dữ liệu nhạy cảm hoặc không rõ nguồn.
- Model card thiếu limitation và safety note.
- Model repo yêu cầu custom code.
- Artifact lớn làm cold start lâu.
- Label mapping không rõ.
- Model output có bias hoặc toxic behavior.

Production baseline:

- Pin `model_id`, `revision`, package version.
- Mirror artifact vào registry nội bộ nếu cần availability/compliance.
- Scan/audit custom code nếu dùng `trust_remote_code=True`.
- Có owner rõ cho model.
- Có model card nội bộ cho version đã deploy.
- Có golden test set và rollback plan.

## 14. Dùng Được Trong Production Không?

Có, Hugging Face ecosystem dùng được trong production, nhưng cần điều kiện rõ:

- Model card đã được review: license, intended use, limitations, language, dataset, metrics, safety, inference requirements.
- Model/tokenizer/config được pin version hoặc revision.
- Inference wrapper load model một lần ở startup, có warmup, batching, truncation và error handling.
- Có benchmark trên hardware thật: p50/p95 latency, throughput, RAM/VRAM, cold start.
- Có evaluation set hoặc golden set đại diện domain thật.
- Có monitoring: latency, error rate, confidence distribution, label distribution, token length, model version.
- Có data policy: không log raw PII, kiểm soát retention và access.
- Có fallback/rollback khi model lỗi hoặc quality regression.
- Có security review nếu model cần custom code hoặc lấy artifact từ nguồn public.

Nếu chỉ dùng notebook gọi `pipeline()` với model public chưa đọc license, chưa pin revision, chưa benchmark và chưa có monitoring, thì chưa đủ production.

## 15. Best Practices

1. Bắt đầu bằng model nhỏ và baseline đơn giản trước khi chọn model lớn.
2. Pin model revision như pin Docker image digest.
3. Lưu `model_id`, `revision`, `max_length`, tokenizer name, label mapping và package versions vào artifact.
4. Tách preprocessing/tokenization thành module dùng chung giữa train và serve.
5. Benchmark với input length thật, không chỉ câu demo ngắn.
6. Không log raw text nếu có PII hoặc nội dung khách hàng nhạy cảm.
7. Viết model card nội bộ cho model đã fine-tune.
8. Dùng `Trainer` cho v1 nếu task chuẩn; chỉ custom loop khi có lý do kỹ thuật thật.
9. Review license/security trước khi đưa model public vào hệ thống nội bộ.
10. Chuẩn bị Day 16 bằng một sentiment dataset nhỏ, label mapping rõ và split reproducible.

## 16. Bài Tập Chuẩn Bị Cho Day 16

Trong 60-90 phút:

1. Chọn một model classification từ Model Hub.
2. Đọc model card theo checklist trong bài.
3. Chạy `pipeline` với 5 câu.
4. Chạy raw model inference bằng wrapper trong bài với cùng 5 câu.
5. So sánh output, latency, token count.
6. Tạo một CSV nhỏ `text,label` cho sentiment tiếng Việt.
7. Load CSV bằng `datasets`, split train/test và tokenize bằng `map(batched=True)`.
8. Ghi lại quyết định: model này có đủ điều kiện production chưa, thiếu gì.

## Tự Kiểm Tra

1. `AutoTokenizer` khác `AutoModel` ở đâu?
2. Vì sao tokenizer là một phần của API contract?
3. Khi nào dùng `pipeline`, khi nào dùng raw model inference?
4. Vì sao cần pin `revision`?
5. `Trainer` giải quyết những phần nào của training loop?
6. Khi nào nên chuyển từ `Trainer` sang custom loop với `accelerate`?
7. Model card cần kiểm tra những mục nào trước production?
8. Batch size lớn giúp gì và gây rủi ro gì?
9. Quantization nên được quyết định bằng metric nào?
10. Điều kiện tối thiểu để dùng Hugging Face model trong production là gì?

## Nguồn kỹ thuật đã đối chiếu

- Transformers docs qua Context7: `/websites/huggingface_co_transformers_main`.
- Datasets docs qua Context7: `/llmstxt/huggingface_co_datasets_main_en_llms_txt`.
- [Transformers tokenizer API](https://huggingface.co/docs/transformers/main/en/main_classes/tokenizer).
- [Transformers Trainer API](https://huggingface.co/docs/transformers/main/en/main_classes/trainer).
- [Datasets processing](https://huggingface.co/docs/datasets/main/en/process) và [streaming](https://huggingface.co/docs/datasets/main/en/stream).
- API/behavior đã đối chiếu: padding/truncation, `return_tensors`, `load_dataset`, `map(batched=True)`, `remove_columns`, cache/fingerprint, streaming và PyTorch formatting.
