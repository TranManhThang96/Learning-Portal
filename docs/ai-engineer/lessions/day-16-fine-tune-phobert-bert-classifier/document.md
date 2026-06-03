# Day 16 Document: Vietnamese Sentiment Classifier Production Reference

## 1. Project Structure Đề Xuất

```text
sentiment-classifier/
  data/
    reviews.csv
  src/
    train_sentiment.py
    serve_sentiment.py
  artifacts/
    sentiment_classifier/
      baseline.joblib
      baseline_metrics.json
      best_model/
      transformer_metrics.json
      comparison.json
      labels.json
      manifest.json
      model_card.md
      errors.csv
  tests/
    test_preprocessing.py
    test_api_contract.py
```

Trong repo học này, script mẫu nằm trực tiếp trong folder Day 16 để bạn chạy nhanh.

## 2. Data Contract

CSV input tối thiểu:

```csv
text,label
"sản phẩm tốt, giao hàng nhanh",positive
"đóng gói kém, hàng bị lỗi",negative
"tạm được, chưa có gì đặc biệt",neutral
```

Yêu cầu:

- Cột `text` là string, không rỗng sau khi trim.
- Cột `label` chỉ thuộc `negative`, `neutral`, `positive`.
- Không chứa duplicate exact hoặc near-duplicate giữa train/validation/test.
- Nếu text có PII, cần masking hoặc policy không log raw text.
- Nếu có metadata như channel/product/date, nên giữ để error analysis.

## 3. Label Guideline Template

| Label | Định nghĩa | Nên label | Không nên label |
|---|---|---|---|
| `negative` | Người dùng thể hiện bất mãn hoặc vấn đề cần xử lý | Lỗi, chậm, hỏng, thất vọng, yêu cầu hoàn tiền | Góp ý nhẹ không có cảm xúc xấu rõ |
| `neutral` | Nhận xét mô tả, chưa đánh giá hoặc cảm xúc cân bằng | "mới nhận chưa dùng", "bình thường" | Review vừa có lỗi nghiêm trọng vừa có lời khen |
| `positive` | Người dùng hài lòng hoặc khen rõ | Tốt, nhanh, đáng tiền, sẽ mua lại | Khen mỉa mai hoặc khen một phần nhưng phàn nàn chính |

Quy tắc thực tế: nếu action downstream ưu tiên cứu negative review, hãy label câu có lỗi nghiêm trọng là `negative` dù có khen một phần.

## 4. Split Strategy

Mặc định:

- Train: 60%.
- Validation: 20%.
- Test: 20%.
- Stratify theo label.
- Seed cố định, ví dụ `42`.

Với production data có thời gian:

- Dùng time-based split để mô phỏng tương lai.
- Ví dụ train trên tháng 1-3, validation tháng 4, test tháng 5.
- Tránh random split nếu duplicate/campaign làm leakage.

## 5. Metrics Template

```json
{
  "model_name": "phobert-base-sentiment-v1",
  "dataset_version": "reviews-2026-05-10",
  "split": "test",
  "accuracy": 0.91,
  "f1_macro": 0.88,
  "per_class": {
    "negative": {"precision": 0.86, "recall": 0.82, "f1": 0.84},
    "neutral": {"precision": 0.80, "recall": 0.76, "f1": 0.78},
    "positive": {"precision": 0.95, "recall": 0.97, "f1": 0.96}
  },
  "confusion_matrix_labels": ["negative", "neutral", "positive"],
  "confusion_matrix": [[82, 12, 6], [10, 76, 14], [3, 6, 191]]
}
```

Metric acceptance nên gắn với business:

| Use case | Metric ưu tiên |
|---|---|
| Alert negative review | Recall/F1 của `negative`, false negative rate |
| Dashboard aggregate | Macro F1 và calibration tương đối |
| Auto-route support | Precision và recall theo class route |
| Auto action high impact | Không nên fully automated nếu chưa có human review |

## 6. Error Analysis Checklist

Lấy ít nhất 20-50 lỗi từ test set và phân loại:

- Label noise: ground truth có thể sai.
- Ambiguous neutral: câu không rõ positive/negative.
- Sarcasm: "giao nhanh ghê, chờ có 2 tuần".
- Mixed sentiment: khen giao hàng nhưng chê sản phẩm.
- Domain slang/teencode: "ổn áp", "xịn xò", "toang".
- Missing context: "như lần trước" cần conversation history.
- Long text bị truncation.
- PII/order code làm nhiễu token.

Sau error analysis, quyết định:

- Sửa guideline label.
- Thêm data cho class yếu.
- Thêm preprocessing.
- Điều chỉnh threshold.
- Đổi model hoặc tăng `max_length`.

## 7. Baseline Checklist

- Dùng `Pipeline` của scikit-learn để tránh train-serving skew.
- Thử word n-gram và char n-gram.
- Bật `class_weight="balanced"` nếu class imbalance.
- Save bằng `joblib`.
- Export `classification_report`, `confusion_matrix`, `errors.csv`.
- Không tune trên test set.

Baseline production được nếu:

- Đạt business metric.
- Có latency tốt hơn Transformer rõ rệt.
- Dataset/domain không đòi hỏi semantic quá phức tạp.
- Có monitoring và rollback như model khác.

## 8. Transformer Checklist

- Pin `MODEL_ID` và nếu dùng Hub production thì pin revision/commit SHA.
- Lưu tokenizer cùng model.
- Lưu `label2id`/`id2label` trong config và `labels.json`.
- Dùng `DataCollatorWithPadding` để padding động theo batch.
- Dùng `f1_macro` để chọn best checkpoint nếu class imbalance.
- Dùng validation để chọn model, test chỉ để final report.
- Benchmark `max_length=64/128/256` trước khi chọn.
- Kiểm tra preprocessing PhoBERT nhất quán giữa train và serve.

Theo Context7/HuggingFace docs, tokenizer nên dùng `truncation=True`, `max_length` rõ ràng, `return_tensors="pt"` khi inference PyTorch. Với FastAPI, pattern `lifespan` phù hợp để load ML model một lần trước khi nhận request.

## 9. Artifact Manifest Template

```json
{
  "artifact_name": "vietnamese-sentiment-classifier",
  "version": "sentiment-v1",
  "created_at": "2026-05-10T00:00:00Z",
  "task": "text-classification",
  "labels": ["negative", "neutral", "positive"],
  "model_id": "vinai/phobert-base",
  "max_length": 128,
  "seed": 42,
  "data": {
    "source": "internal_reviews",
    "dataset_version": "reviews-2026-05-10",
    "train_size": 6000,
    "validation_size": 2000,
    "test_size": 2000
  },
  "metrics": {
    "baseline_f1_macro": 0.82,
    "transformer_f1_macro": 0.88
  },
  "runtime": {
    "python": "3.12",
    "torch": "pinned",
    "transformers": "pinned",
    "scikit_learn": "pinned"
  }
}
```

## 10. FastAPI API Contract

Request:

```json
{
  "text": "sản phẩm tốt, giao hàng nhanh"
}
```

Response:

```json
{
  "label": "positive",
  "confidence": 0.94,
  "probabilities": {
    "negative": 0.02,
    "neutral": 0.04,
    "positive": 0.94
  },
  "input_tokens": 12,
  "latency_ms": 42.7,
  "model_version": "sentiment-v1"
}
```

Validation:

- `text` min length: 1.
- `text` max length: ví dụ 2000 ký tự.
- Batch size max: ví dụ 32.
- Timeout inference: theo SLA.

## 11. Monitoring Dashboard

Tối thiểu cần:

| Metric | Alert gợi ý |
|---|---|
| Request rate | Traffic bất thường |
| Error rate | 5xx tăng |
| p95/p99 latency | Vượt SLA |
| Input length distribution | Request quá dài tăng |
| Predicted label distribution | Drift hoặc bug label mapping |
| Confidence distribution | Model không chắc chắn hơn bình thường |
| Negative rate theo channel/product | Vấn đề business thật hoặc data drift |
| Model version | Đảm bảo deploy đúng artifact |

Không log raw text mặc định. Nếu cần debug, dùng sampling có masking và retention ngắn.

## 12. Production Decision Template

```markdown
# Production Decision

## Candidate
- Baseline:
- Transformer:

## Metrics
- Baseline macro F1:
- Transformer macro F1:
- Negative recall:
- p95 latency:
- Memory:

## Decision
- Chọn:
- Lý do:

## Conditions before production
- License checked:
- Dataset representative:
- PII policy:
- Monitoring:
- Rollback:
- Human review:

## Risks
- Drift:
- Label ambiguity:
- Latency/cost:
- Bias:
```

## 13. Dùng Được Trong Production Không?

Có, nhưng chỉ khi model được xem như một service có lifecycle đầy đủ:

- Data có nguồn rõ và đại diện.
- Evaluation đủ sâu, không chỉ notebook accuracy.
- Artifact versioned và reproducible.
- API có contract ổn định.
- Monitoring/rollback có sẵn.
- Privacy/license được xử lý.

Nếu thiếu các điều kiện này, chỉ nên gọi là prototype hoặc internal demo.

## 14. Context7 Docs Đã Tham Chiếu Khi Viết Bài

- `/websites/huggingface_co_transformers_main`: tokenizer parameters, `AutoModelForSequenceClassification`, `Trainer`, `TrainingArguments`, dynamic padding và model save/load pattern.
- `/fastapi/fastapi`: `lifespan` để load ML model một lần, Pydantic request validation, endpoint pattern.
