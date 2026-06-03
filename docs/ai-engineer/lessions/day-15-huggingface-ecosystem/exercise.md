# Day 15 Exercise: Hugging Face Ecosystem

## Mục tiêu thực hành

Hoàn thành bài này để bước sang Day 16 mà không bị mơ hồ về model loading, tokenizer, Model Hub, model card, `datasets`, `Trainer` và inference wrapper.

## Yêu cầu môi trường

```bash
pip install -U torch transformers datasets accelerate scikit-learn numpy
```

Nếu máy không có GPU, vẫn làm được bài bằng model nhỏ và batch size thấp.

## Exercise 1: Review Model Card

Chọn một model từ Model Hub, ví dụ:

- `distilbert-base-uncased-finetuned-sst-2-english`
- `distilbert-base-multilingual-cased`
- `vinai/phobert-base`

Điền model card review:

| Mục | Câu trả lời |
|---|---|
| Model ID |  |
| License |  |
| Intended use |  |
| Limitations |  |
| Language |  |
| Dataset |  |
| Metrics |  |
| Safety |  |
| Inference requirements |  |
| Có dùng production được không? |  |
| Điều kiện còn thiếu |  |

Kết quả mong đợi: bạn phải nói được model này phù hợp task nào, không phù hợp task nào và có rủi ro gì.

## Exercise 2: Pipeline Inference

Chạy inference bằng `pipeline`:

```python
from transformers import pipeline

texts = [
    "This product is useful and reliable.",
    "The delivery was late and the support was terrible.",
    "I need to test this model before using it in production.",
]

classifier = pipeline(
    "text-classification",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)

print(classifier(texts))
```

Ghi lại:

- Model ID.
- Output label.
- Confidence.
- Thời gian chạy ước lượng.
- Bạn có kiểm soát được `max_length`, batching, schema và logging đủ tốt chưa?

## Exercise 3: Raw Model Inference

Viết lại inference bằng `AutoTokenizer` và `AutoModelForSequenceClassification`:

```python
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_id = "distilbert-base-uncased-finetuned-sst-2-english"
texts = [
    "This product is useful and reliable.",
    "The delivery was late and the support was terrible.",
]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForSequenceClassification.from_pretrained(model_id).to(device)
model.eval()

encoded = tokenizer(
    texts,
    padding=True,
    truncation=True,
    max_length=128,
    return_tensors="pt",
)
encoded = {key: value.to(device) for key, value in encoded.items()}

with torch.inference_mode():
    outputs = model(**encoded)
    probs = torch.softmax(outputs.logits, dim=-1)

for row in probs.detach().cpu():
    label_id = int(torch.argmax(row).item())
    print(
        {
            "label": model.config.id2label[label_id],
            "confidence": round(float(row[label_id].item()), 6),
        }
    )
```

So sánh với Exercise 2:

- Code nào nhanh để prototype hơn?
- Code nào dễ đưa vào API hơn?
- Bạn sẽ log thêm field nào?
- Bạn sẽ validate input thế nào?

## Exercise 4: Batching Và Truncation

Chạy raw inference với các cấu hình:

| Run | `max_length` | `batch_size` | Ghi chú latency/token count |
|---|---:|---:|---|
| 1 | 64 | 1 |  |
| 2 | 128 | 1 |  |
| 3 | 128 | 8 |  |
| 4 | 256 | 8 |  |

Kết luận:

- `max_length` tăng ảnh hưởng thế nào?
- Batch size tăng throughput hay latency ra sao?
- Với API realtime, bạn chọn cấu hình nào?

## Exercise 5: Load Dataset Và Tokenize

Tạo file CSV nhỏ cho sentiment:

```csv
text,label
"sản phẩm tốt giao hàng nhanh",positive
"đóng gói kém hàng bị lỗi",negative
"tạm được chưa có gì đặc biệt",neutral
"shop hỗ trợ nhanh",positive
"giao hàng quá chậm",negative
"mới dùng nên chưa đánh giá",neutral
```

Load bằng `datasets`:

```python
from datasets import load_dataset
from transformers import AutoTokenizer

model_id = "distilbert-base-multilingual-cased"
tokenizer = AutoTokenizer.from_pretrained(model_id)
labels = ["negative", "neutral", "positive"]
label2id = {label: idx for idx, label in enumerate(labels)}

raw = load_dataset("csv", data_files="reviews.csv")["train"]
split = raw.train_test_split(test_size=0.33, seed=42)


def tokenize_batch(examples):
    encoded = tokenizer(
        examples["text"],
        truncation=True,
        max_length=128,
    )
    encoded["labels"] = [label2id[label] for label in examples["label"]]
    return encoded


tokenized = split.map(tokenize_batch, batched=True, remove_columns=["text", "label"])
print(tokenized)
print(tokenized["train"][0].keys())
```

Ghi lại:

- Dataset có những split nào?
- Sau tokenize có thêm field nào?
- Vì sao `Trainer` cần cột `labels` dạng số thay vì label string?
- Vì sao `map(batched=True)` tốt hơn tokenize từng dòng bằng vòng `for` Python?

## Exercise 6: Trainer Skeleton

Không cần train lâu. Mục tiêu là hiểu wiring giữa dataset, tokenizer, model và `Trainer`.

Viết skeleton:

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
labels = ["negative", "neutral", "positive"]
label2id = {label: idx for idx, label in enumerate(labels)}
id2label = {idx: label for label, idx in label2id.items()}

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForSequenceClassification.from_pretrained(
    model_id,
    num_labels=len(labels),
    label2id=label2id,
    id2label=id2label,
)

data_collator = DataCollatorWithPadding(tokenizer=tokenizer)


def compute_metrics(eval_pred):
    logits, label_ids = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return {"accuracy": float((predictions == label_ids).mean())}


training_args = TrainingArguments(
    output_dir="artifacts/day15-smoke-test",
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    num_train_epochs=1,
    learning_rate=2e-5,
    eval_strategy="epoch",
    save_strategy="no",
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
```

Câu hỏi:

- `DataCollatorWithPadding` giải quyết vấn đề gì?
- `label2id` và `id2label` nên được lưu ở đâu?
- Khi nào skeleton này chưa đủ production training?

## Exercise 7: Production Decision

Trả lời ngắn, nhưng phải cụ thể:

```text
Model đã chọn có dùng được trong production không?

Nếu có, cần điều kiện gì?
Nếu chưa, thiếu bằng chứng nào?
Rollback/fallback là gì?
Metric nào cần monitor?
Rủi ro license/security là gì?
```

Checklist hoàn thành:

- [ ] Đã đọc model card.
- [ ] Đã chạy `pipeline`.
- [ ] Đã chạy raw model inference.
- [ ] Đã đo hoặc ước lượng ảnh hưởng của `max_length` và batch size.
- [ ] Đã load CSV bằng `datasets`.
- [ ] Đã tokenize bằng `map(batched=True)`.
- [ ] Đã hiểu skeleton `Trainer`.
- [ ] Đã viết production decision rõ ràng.
