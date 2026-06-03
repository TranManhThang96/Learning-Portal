# Day 15 Document: Hugging Face Production Reference

## 1. Model Card Review Template

Dùng template này trước khi đưa một model từ Model Hub vào thử nghiệm nghiêm túc hoặc production.

```markdown
# Model Card Review

## Basic information

- Model ID:
- Revision/commit SHA:
- Model family:
- Task:
- Owner/team:
- Review date:

## License

- License:
- Commercial use allowed:
- Attribution requirements:
- Redistribution restrictions:
- Decision: approved / rejected / needs legal review

## Intended use

- Intended task:
- Intended users:
- Intended domain:
- Out-of-scope use:

## Language and locale

- Supported languages:
- Vietnamese support:
- Required preprocessing:
- Tokenizer notes:

## Training/evaluation data

- Training dataset:
- Evaluation dataset:
- Data source clarity:
- Domain match with our data:
- Known data risks:

## Metrics

- Reported metrics:
- Benchmark/split:
- Metric relevant to our use case:
- Missing metrics:

## Limitations

- Known weak domains:
- Max sequence length/context:
- Robustness concerns:
- Bias/toxicity/privacy notes:

## Safety and security

- Requires trust_remote_code:
- Custom code audited:
- Handles sensitive data:
- Output safety risks:
- Abuse/misuse concerns:

## Inference requirements

- Artifact size:
- CPU viable:
- GPU/VRAM requirement:
- Expected latency:
- Quantization available:
- Batch size tested:

## Production decision

- Can be used in production:
- Required conditions:
- Monitoring needed:
- Rollback plan:
- Final decision:
```

## 2. Dependency Pinning Template

```yaml
model:
  model_id: distilbert-base-uncased-finetuned-sst-2-english
  revision: main
  task: text-classification
  max_length: 128
  tokenizer:
    use_fast: true
  label_mapping:
    "0": NEGATIVE
    "1": POSITIVE
runtime:
  python: "3.12"
  torch: "pin-in-requirements"
  transformers: "pin-in-requirements"
  datasets: "pin-in-requirements"
  accelerate: "pin-in-requirements"
serving:
  device: auto
  batch_size: 16
  timeout_ms: 1000
  log_raw_text: false
```

Trong production thật, nên thay `revision: main` bằng commit SHA cụ thể sau khi đã chọn version.

## 3. Pipeline Vs Raw Model Decision

| Câu hỏi | Nếu câu trả lời là có | Gợi ý |
|---|---|---|
| Cần demo nhanh trong notebook? | Có | Dùng `pipeline` |
| Cần stable response schema cho API? | Có | Dùng raw model wrapper |
| Cần custom batching theo traffic? | Có | Dùng raw model wrapper |
| Cần benchmark nhiều `max_length`/batch size? | Có | Dùng raw model wrapper |
| Cần explain nhanh cho người mới học? | Có | Bắt đầu bằng `pipeline`, sau đó mở raw path |
| Cần timeout, fallback, metrics chi tiết? | Có | Dùng raw model wrapper |

## 4. Trainer Vs Custom Loop Decision

| Câu hỏi | Gợi ý |
|---|---|
| Task là sequence classification/token classification chuẩn? | Dùng `Trainer` trước |
| Cần metric callback, checkpoint, eval mỗi epoch? | `Trainer` đủ tốt cho v1 |
| Cần nhiều loss, nhiều model hoặc sampling custom? | Custom loop |
| Cần scale custom PyTorch loop lên GPU/multi-GPU? | Dùng `accelerate` |
| Team cần học nhanh trước Day 16? | Dùng `Trainer` |

## 5. Inference Wrapper Checklist

- Load model/tokenizer một lần ở startup.
- Pin `model_id` và `revision`.
- Chọn device rõ: `cuda`, `mps` hoặc `cpu`.
- Gọi `model.eval()`.
- Dùng `torch.inference_mode()` hoặc `torch.no_grad()` khi inference.
- Tokenize theo batch.
- Bật `truncation=True`.
- Set `max_length` theo domain và benchmark.
- Dùng `padding=True` cho batch inference.
- Move tensors sang đúng device.
- Convert output về CPU trước khi serialize.
- Trả stable JSON schema: label, confidence, model version, latency.
- Log latency, token count, model ID, revision; không log raw PII.
- Có exception rõ cho load error và input error.
- Có readiness check sau khi model warmup.

## 6. Dataset Preparation Checklist

- Dataset có schema rõ: `text`, `label`.
- Label mapping được lưu lại: `label2id`, `id2label`.
- Cột label string được convert thành cột `labels` dạng số trước khi dùng `Trainer`.
- Split train/validation/test reproducible bằng seed.
- Không leak duplicate gần giống giữa train và test.
- Tokenization chạy qua `dataset.map(..., batched=True)`.
- Giữ preprocessing giống nhau giữa train và serve.
- Không tune hyperparameter trên test set.
- Report macro F1 nếu class imbalance.
- Lưu confusion matrix và error examples.

## 7. CPU/GPU/Batch Size Notes

| Chủ đề | Ghi chú thực tế |
|---|---|
| CPU | Dễ vận hành, hợp model nhỏ/traffic thấp, latency có thể cao |
| GPU | Tốt cho throughput và model lớn, cần batching để tận dụng |
| Batch size | Tăng throughput nhưng tăng memory và queueing latency |
| `max_length` | 128 thường hợp review/ticket ngắn; 512 tốn hơn nhiều |
| Quantization | Có thể giảm RAM/VRAM, phải đo quality regression |
| Warmup | Giảm latency spike đầu tiên sau deploy |

## 8. Hosted Vs Local

| Lựa chọn | Ưu điểm | Rủi ro |
|---|---|---|
| Hosted inference | Go-live nhanh, ít ops, không quản GPU | Cost/request, data policy, vendor SLA |
| Local self-host | Kiểm soát data, cost dài hạn, custom runtime | Ops phức tạp, GPU capacity, monitoring |
| Hybrid | Dùng hosted cho POC, local khi scale | Cần abstraction để đổi provider |

## 9. Tối Thiểu Cho Production

Hugging Face model dùng được trong production khi có đủ:

- Model card review được lưu lại.
- License được approve.
- Version/revision được pin.
- Evaluation set hoặc golden set đại diện domain.
- Inference wrapper có batching/truncation/error handling.
- Benchmark trên hardware thật.
- Monitoring và alert.
- Rollback/fallback.
- Data policy cho PII.
- Security review nếu dùng custom remote code.

## 10. Context7 Docs Đã Tham Chiếu Khi Viết Bài

- `/websites/huggingface_co_transformers_main`: `AutoTokenizer`, tokenizer parameters, `AutoModelForSequenceClassification`, `pipeline`, `Trainer`.
- `/llmstxt/huggingface_co_datasets_main_en_llms_txt`: `load_dataset`, `map(batched=True)`, cache behavior.
- `/huggingface/accelerate`: `Accelerator`, `prepare`, `accelerator.backward`, mixed precision và distributed pattern.
