# Day 16 Exercise: Fine-tune Vietnamese Sentiment Classifier

## Mục tiêu thực hành

Bạn sẽ build một classifier sentiment tiếng Việt end-to-end:

1. Chuẩn bị dataset CSV.
2. Train baseline `TF-IDF + Logistic Regression`.
3. Fine-tune Transformer bằng HuggingFace `Trainer`.
4. So sánh metric và phân tích lỗi.
5. Export artifact.
6. Serve model bằng FastAPI.
7. Viết production decision: dùng được production chưa, còn thiếu gì.

## Yêu cầu môi trường

Khuyến nghị dùng virtual environment riêng.

```bash
pip install -U pandas numpy scikit-learn joblib datasets transformers accelerate torch fastapi uvicorn pydantic
```

Nếu không có GPU, hãy dùng model nhỏ:

```bash
export MODEL_ID=distilbert-base-multilingual-cased
export EPOCHS=1
export BATCH_SIZE=4
```

Nếu có GPU/Colab và muốn thử PhoBERT:

```bash
export MODEL_ID=vinai/phobert-base
export EPOCHS=3
export BATCH_SIZE=8
```

## Exercise 1: Tạo Dataset

Tạo file `data/reviews.csv`:

```csv
text,label
"sản phẩm rất tốt, giao hàng nhanh",positive
"đóng gói cẩn thận, hàng đúng mô tả",positive
"chất lượng tốt, sẽ mua lại",positive
"shop hỗ trợ nhanh và lịch sự",positive
"hàng bị lỗi, không đúng mô tả",negative
"đóng gói tệ, sản phẩm bị vỡ",negative
"giao hàng quá chậm",negative
"chất lượng kém, rất thất vọng",negative
"sản phẩm tạm được",neutral
"bình thường, không có gì đặc biệt",neutral
"giao hàng đúng hẹn",neutral
"mới dùng nên chưa đánh giá",neutral
```

Trong thực tế, dataset nên có ít nhất vài nghìn sample và được review label guideline. File nhỏ này chỉ để kiểm tra pipeline.

## Exercise 2: Chạy Training Script

Từ folder Day 16:

```bash
cd lessions/day-16-fine-tune-phobert-bert-classifier
DATA_PATH=data/reviews.csv OUT_DIR=artifacts/sentiment_classifier python train_sentiment.py
```

Nếu chưa có `data/reviews.csv`, script sẽ dùng synthetic fallback có dấu để bạn vẫn chạy được.

Kết quả mong đợi:

```text
artifacts/sentiment_classifier/
  baseline.joblib
  baseline_metrics.json
  best_model/
  transformer_metrics.json
  comparison.json
  labels.json
  manifest.json
  model_card.md
  errors.csv
```

Ghi lại:

| Metric | Baseline | Transformer |
|---|---:|---:|
| Accuracy |  |  |
| Macro F1 |  |  |
| Negative recall |  |  |
| p95 latency | chưa đo | chưa đo |

## Exercise 3: Đọc Confusion Matrix

Mở `comparison.json` và trả lời:

- Model nào có macro F1 tốt hơn?
- Model nào bỏ sót nhiều `negative` hơn?
- Nếu dùng để route ticket khẩn cấp, lỗi nào nguy hiểm nhất?
- Nếu Transformer tốt hơn 1-2 điểm F1 nhưng latency cao hơn 50 lần, bạn chọn gì cho v1?

## Exercise 4: Error Analysis

Mở `errors.csv`, chọn ít nhất 10 lỗi và phân loại:

| Text | True | Pred | Nhóm lỗi | Cách sửa |
|---|---|---|---|---|
|  |  |  | label noise / ambiguous / slang / truncation / mixed sentiment |  |

Kết luận cần có:

- Có cần sửa label guideline không?
- Có cần thêm data cho class nào không?
- Có cần tăng `max_length` không?
- Có cần chuyển từ baseline sang Transformer không?

## Exercise 5: Serve FastAPI

Sau khi train xong:

```bash
MODEL_DIR=artifacts/sentiment_classifier/best_model \
LABEL_PATH=artifacts/sentiment_classifier/labels.json \
MODEL_VERSION=sentiment-v1 \
uvicorn serve_sentiment:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Predict:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"sản phẩm tốt, giao hàng nhanh"}'
```

Batch predict:

```bash
curl -X POST http://localhost:8000/predict-batch \
  -H "Content-Type: application/json" \
  -d '{"texts":["sản phẩm tốt","giao hàng quá chậm","mới dùng nên chưa đánh giá"]}'
```

Ghi lại:

- `latency_ms`.
- `input_tokens`.
- `confidence`.
- Output schema có đủ cho downstream service chưa?

## Exercise 6: Benchmark Cấu Hình

Chạy lại với các cấu hình:

| Run | `MODEL_ID` | `MAX_LENGTH` | `BATCH_SIZE` | Macro F1 | Ghi chú latency |
|---|---|---:|---:|---:|---|
| 1 | `distilbert-base-multilingual-cased` | 64 | 4 |  |  |
| 2 | `distilbert-base-multilingual-cased` | 128 | 4 |  |  |
| 3 | `bert-base-multilingual-cased` | 128 | 8 |  |  |
| 4 | `vinai/phobert-base` | 128 | 8 |  |  |

Kết luận:

- `max_length` tăng có cải thiện metric không?
- Model lớn có đáng với latency/cost không?
- Với hardware của bạn, model nào phù hợp production v1?

## Exercise 7: Production Decision

Viết file ngắn `production_decision.md` theo template:

```markdown
# Production Decision

## Use case

## Dataset

## Metrics
- Baseline:
- Transformer:

## Latency and cost

## Decision
Chọn baseline hoặc Transformer.

## Dùng được trong production không?
Có/không.

## Điều kiện bắt buộc trước production
- Dataset:
- License:
- Monitoring:
- PII:
- Rollback:
- Human review:
```

Yêu cầu câu trả lời không được chung chung. Ví dụ chưa đạt:

```text
Có thể dùng production nếu cải thiện thêm.
```

Ví dụ đạt:

```text
Chưa dùng production. Dataset hiện chỉ là synthetic fallback 36 dòng, không đại diện traffic thật. Có thể dùng làm demo nội bộ. Để production cần ít nhất 3.000 review đã label theo guideline, test set không leakage, negative recall >= 0.85, p95 latency < 100 ms trên CPU target, không log raw PII và có rollback sang baseline artifact.
```

## Checklist Hoàn Thành

- [ ] Dataset có schema `text,label`.
- [ ] Baseline đã train và lưu artifact.
- [ ] Transformer đã fine-tune và lưu artifact.
- [ ] Có `comparison.json`.
- [ ] Có confusion matrix và error samples.
- [ ] FastAPI chạy được `/health`, `/ready`, `/predict`.
- [ ] Có production decision rõ ràng.
- [ ] Trả lời được: dùng production được không, cần điều kiện gì.
