# Day 16: Mini-project - Fine-tune PhoBERT/BERT Classifier

## Mục tiêu

Sau bài này, bạn cần làm được các việc sau:

- Frame bài toán sentiment classification tiếng Việt theo hướng production.
- Xây baseline `TF-IDF + Logistic Regression` để có mốc so sánh rẻ, nhanh và dễ debug.
- Fine-tune `PhoBERT` hoặc `BERT` multilingual bằng HuggingFace `Trainer`.
- Evaluate model bằng accuracy, macro F1, per-class precision/recall/F1, confusion matrix và error analysis.
- Export artifact đầy đủ: model, tokenizer, label mapping, metric, manifest và model card nội bộ.
- Serve model bằng FastAPI với request validation, health endpoint, inference latency, confidence và schema ổn định.
- Ra quyết định production dựa trên chất lượng, latency, cost, drift, rollback và operational risk.

## TL;DR

Day 16 là mini-project tổng hợp Phase 2: Deep Learning, NLP và Transformer. Cách làm đúng không phải nhảy thẳng vào PhoBERT, mà là bắt đầu bằng baseline đơn giản, đo metric, hiểu lỗi, rồi mới fine-tune Transformer trên cùng split dữ liệu.

Nếu PhoBERT/BERT chỉ tốt hơn baseline rất ít nhưng latency, memory và vận hành đắt hơn nhiều, baseline có thể là production v1 tốt hơn. Nếu domain có nhiều câu dài, slang, sắc thái tiếng Việt và baseline fail ở negative/neutral class, Transformer đáng để dùng hơn.

## 1. Day 16 Nằm Ở Đâu Trong Lộ Trình

Trong Phase 2, bạn đã đi qua:

```text
Day 9-11: Neural Network, PyTorch, training loop
Day 12: NLP và tokenizer
Day 13-14: Attention và Transformer
Day 15: Hugging Face ecosystem
Day 16: Mini-project classifier có thể deploy
```

Day 16 chuyển từ "biết API" sang "ship được một AI service nhỏ có kiểm soát". Với background Senior Software Engineer, output quan trọng không chỉ là notebook train model, mà là một pipeline có data contract, evaluation, artifact, API, monitoring plan và rollback path.

## 2. Problem Framing

Bài toán:

```text
Input: review hoặc customer message tiếng Việt
Output: sentiment label = negative | neutral | positive
```

Output production nên là JSON ổn định, không chỉ một string:

```json
{
  "label": "positive",
  "confidence": 0.94,
  "probabilities": {
    "negative": 0.02,
    "neutral": 0.04,
    "positive": 0.94
  },
  "model_version": "sentiment-phobert-v1",
  "input_tokens": 12,
  "latency_ms": 42.7
}
```

Trước khi train, cần chốt các câu hỏi sau:

| Câu hỏi | Vì sao quan trọng |
|---|---|
| Có mấy class? | Binary dễ hơn, 3-class hữu ích hơn nhưng neutral thường mơ hồ |
| `neutral` nghĩa là gì? | Nếu guideline không rõ, annotator label không nhất quán |
| Input tối đa bao nhiêu ký tự/token? | Ảnh hưởng truncation, latency và memory |
| Text có PII không? | Quyết định logging, retention và masking |
| Prediction dùng để làm gì? | Route ticket, dashboard, alert hay auto-reply có risk khác nhau |
| Class nào quan trọng nhất? | Negative review thường cần recall cao hơn |

Map về Senior SE: label schema giống API contract. Nếu contract mơ hồ, downstream system vẫn chạy nhưng business behavior sai.

## 3. Dataset Và Label Design

Schema tối thiểu:

```csv
text,label
"sản phẩm tốt, giao hàng nhanh",positive
"đóng gói kém, hàng bị lỗi",negative
"tạm được, chưa có gì đặc biệt",neutral
```

Nguồn dữ liệu có thể dùng:

- Dataset nội bộ từ customer support, review, survey hoặc ticket.
- Public Vietnamese sentiment dataset như VLSP/AIVIVN/Shopee review nếu license phù hợp.
- Synthetic fallback chỉ để kiểm tra pipeline, không dùng làm bằng chứng chất lượng production.

Label guideline nên đủ cụ thể:

| Label | Khi dùng | Ví dụ |
|---|---|---|
| `negative` | Người dùng phàn nàn, thất vọng, yêu cầu đổi trả, lỗi sản phẩm/dịch vụ | "hàng lỗi, shop không hỗ trợ" |
| `neutral` | Nhận xét mô tả, chưa đánh giá, vừa có điểm tốt vừa có điểm xấu nhẹ | "mới nhận hàng, chưa dùng" |
| `positive` | Người dùng hài lòng, khen chất lượng, dịch vụ, tốc độ | "sản phẩm tốt, giao nhanh" |

Các lỗi data thường gặp:

- Duplicate gần giống nhau nằm cả train và test, làm metric ảo.
- Text rỗng, quá ngắn hoặc chỉ có emoji.
- Label bị lệch class, ví dụ 85% positive.
- Label `neutral` bị dùng như "không biết label gì".
- Review chứa PII, số điện thoại, địa chỉ hoặc mã đơn hàng.
- Dữ liệu test không cùng distribution với production traffic.

Nếu nhiều dòng được sinh từ cùng review gốc, cùng conversation hoặc cùng customer, hãy thêm `group_id` và split theo group. Mọi biến thể của một câu gốc phải nằm trọn trong một split. Random split từng dòng không đủ vì model có thể đã thấy gần như cùng một câu trong train rồi gặp lại ở test.

```text
review gốc A
  -> A nguyên bản
  -> A thêm prefix
  -> A thêm suffix

Sai:  A1 train, A2 validation, A3 test
Đúng: A1, A2, A3 cùng thuộc train hoặc cùng thuộc validation/test
```

## 4. Vì Sao Phải Có Baseline

Baseline `TF-IDF + Logistic Regression` là bắt buộc, không phải bước phụ.

Baseline giúp:

- Train nhanh trên CPU.
- Dễ phát hiện label noise và data leakage.
- Có latency thấp, thường đủ cho API traffic nhỏ/vừa.
- Dễ giải thích token/ngram nào đang ảnh hưởng prediction.
- Là regression guardrail khi Transformer được fine-tune sai.

Pipeline baseline:

```text
raw text
  -> normalize text
  -> TF-IDF word/char n-gram
  -> Logistic Regression
  -> label probabilities
```

Với tiếng Việt, baseline nên thử cả word n-gram và char n-gram. Char n-gram thường robust hơn với teencode, typo, thiếu dấu hoặc tokenization không chuẩn.

Ví dụ cấu hình hợp lý:

```python
Pipeline(
    steps=[
        ("features", FeatureUnion([
            ("word_tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000)),
            ("char_tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=50000)),
        ])),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ]
)
```

Trade-off: baseline không hiểu semantic sâu như Transformer. Câu "giao hàng nhanh nhưng hàng hỏng" có thể bị kéo về positive nếu token positive quá mạnh. Nhưng nếu business chỉ cần dashboard aggregate và dữ liệu đơn giản, baseline có thể đủ.

## 5. Fine-tune PhoBERT/BERT

Transformer classifier flow:

```text
text
  -> tokenizer
  -> input_ids + attention_mask
  -> BERT/PhoBERT encoder
  -> classification head
  -> logits
  -> softmax
  -> label + confidence
```

Model candidates:

| Model | Nên dùng khi | Trade-off |
|---|---|---|
| `vinai/phobert-base` | Task tiếng Việt, cần quality tốt, có kiểm soát preprocessing | Có thể cần chú ý word segmentation/preprocessing nhất quán |
| `bert-base-multilingual-cased` | Cần baseline Transformer multilingual, không muốn phụ thuộc model riêng tiếng Việt | Quality tiếng Việt có thể kém PhoBERT |
| `distilbert-base-multilingual-cased` | CPU hoặc demo nhanh, latency thấp hơn BERT base | Quality thường thấp hơn model lớn |

Hyperparameters v1:

| Hyperparameter | Giá trị khởi đầu | Ghi chú |
|---|---:|---|
| `max_length` | 128 | Review/ticket ngắn thường đủ; benchmark trước khi tăng |
| `learning_rate` | `2e-5` | Default an toàn cho full fine-tune BERT-like |
| `epochs` | 2-4 | Dataset nhỏ dễ overfit |
| `batch_size` | 8-16 | Tùy VRAM/CPU RAM |
| `weight_decay` | `0.01` | Regularization nhẹ |
| `metric_for_best_model` | `f1_macro` | Tốt hơn accuracy khi class imbalance |

Điểm cần nghiêm túc: preprocessing train và serving phải giống nhau. Nếu train dùng text đã word-segmented nhưng serve nhận raw text, model có thể giảm chất lượng mà API vẫn trả response hợp lệ.

## 6. Evaluation

Không chỉ report accuracy. Cần tối thiểu:

- Accuracy.
- Macro F1.
- Per-class precision/recall/F1.
- Confusion matrix.
- Error samples: false negative cho `negative`, false positive cho `negative`, lỗi `neutral`.
- Metric theo input length, source/channel hoặc product category nếu có metadata.

Vì sao macro F1 quan trọng:

```text
Dataset: 80% positive, 10% neutral, 10% negative
Model luôn đoán positive -> accuracy 80%
Nhưng model vô dụng cho use case bắt lỗi negative review.
```

Macro F1 tính trung bình F1 của từng class, nên phạt model bỏ quên class nhỏ.

Confusion matrix cần đọc như sau:

| Lỗi | Ý nghĩa business |
|---|---|
| negative -> positive | Rủi ro cao, bỏ sót khách hàng bất mãn |
| positive -> negative | Tạo false alarm cho support |
| neutral -> positive/negative | Có thể chấp nhận nếu action downstream không quá nhạy |

## 7. Export Artifact

Artifact không chỉ là weights. Một bundle tốt nên có:

```text
artifacts/sentiment_classifier/
  baseline.joblib
  baseline_metrics.json
  best_model/
    config.json
    model.safetensors
    tokenizer.json hoặc vocab files
  transformer_metrics.json
  comparison.json
  labels.json
  manifest.json
  model_card.md
  errors.csv
```

`manifest.json` nên ghi:

- `model_id` và revision nếu dùng model từ Hub.
- `labels`, `label2id`, `id2label`.
- `max_length`, seed, split ratio.
- Package/runtime version chính.
- Metric trên validation/test.
- Training timestamp.
- Git commit nếu project có Git.

Production bug phổ biến: model artifact mới nhưng label mapping cũ. Ví dụ model output index `0` là `negative`, API lại map `0` thành `positive`. Vì vậy label mapping phải đi cùng artifact.

## 8. FastAPI Inference

Serving flow:

```text
FastAPI startup
  -> load model/tokenizer một lần
  -> warmup inference
request
  -> validate text length
  -> normalize text giống training
  -> tokenize with truncation
  -> model inference under torch.inference_mode()
  -> softmax
  -> response JSON
  -> log latency/model_version/input_tokens/confidence
```

Không load model ở mỗi request. Model loading có thể mất vài giây và tốn RAM/VRAM. Theo pattern hiện đại của FastAPI, tài nguyên lớn như ML model nên được load qua `lifespan` khi app startup, rồi dùng lại cho các request.

API tối thiểu:

- `GET /health`: process sống và model đã load.
- `GET /ready`: model/tokenizer sẵn sàng inference.
- `POST /predict`: nhận một text.
- `POST /predict-batch`: nhận nhiều text nếu traffic cần throughput.

Response nên có `model_version`, `latency_ms`, `input_tokens` và `probabilities`. Không nên log raw text mặc định nếu có khả năng chứa PII.

## 9. Trade-offs

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Production note |
|---|---|---|---|
| TF-IDF + Logistic Regression | Cần baseline nhanh, CPU, latency thấp, explainable | Câu nhiều ngữ cảnh, sarcasm, semantic phức tạp | Có thể là v1 nếu đạt business metric |
| PhoBERT | Task tiếng Việt domain-specific, cần quality cao | Không kiểm soát được preprocessing/latency | Benchmark p95/p99 và memory |
| BERT multilingual | Multi-language hoặc setup đơn giản | Chỉ tiếng Việt và cần quality cao nhất | Dễ vận hành hơn nhưng có thể kém PhoBERT |
| DistilBERT multilingual | CPU, demo, latency nhạy | Metric không đạt | Có thể là middle ground |
| 3-class sentiment | Neutral có ý nghĩa business | Annotator không phân biệt được neutral | Cần guideline tốt |
| Binary sentiment | Chỉ cần good/bad routing | Neutral quan trọng cho dashboard | Đơn giản hơn, metric dễ hơn |
| Full fine-tune | Dataset đủ lớn, GPU có sẵn | Data ít, overfit mạnh | Cần early stopping/eval |
| Freeze encoder | Data ít, train nhanh | Cần quality tối đa | Ít update weights hơn |
| ONNX/quantization | CPU latency/cost quan trọng | Chưa đo quality regression | Là bước tối ưu sau baseline correctness |

## 10. Performance Considerations

Các con số cần benchmark trên hardware thật:

- Baseline TF-IDF thường sub-ms đến vài ms/request trên CPU.
- BERT/PhoBERT base trên CPU có thể 50-300 ms/request tùy CPU, `max_length` và batch size.
- GPU giảm latency khi batch/throughput đủ cao, nhưng cold start và cost tăng.
- `max_length=128` thường đủ cho review ngắn; `512` làm attention cost tăng mạnh.
- Batch inference tăng throughput nhưng thêm queueing latency cho realtime API.
- Quantization, ONNX Runtime hoặc Torch compile có thể giảm CPU latency, nhưng cần đo lại metric.

Benchmark nên report:

| Metric | Vì sao cần |
|---|---|
| p50/p95/p99 latency | SLA không dựa vào average |
| throughput request/s | Capacity planning |
| memory/RAM/VRAM | Sizing container |
| cold start time | Deploy/scale behavior |
| max input accepted | Bảo vệ service khỏi request quá dài |

## 11. Production Concerns

Checklist production:

- Data/license: dataset và base model được phép dùng cho mục đích của bạn.
- Reproducibility: seed, split, model revision và package version được lưu.
- Train-serving skew: preprocessing/tokenizer/label mapping giống nhau.
- Observability: latency, error rate, confidence distribution, label distribution.
- Drift: slang, campaign, sản phẩm mới hoặc channel mới làm distribution đổi.
- Privacy: không log raw text nếu chứa PII; có retention policy.
- Security: validate input length, rate limit, timeout, không bật `trust_remote_code=True` nếu chưa audit.
- Rollback: giữ baseline artifact và previous Transformer artifact.
- Human review: với action high impact, prediction chỉ nên hỗ trợ quyết định.
- Re-training loop: thu thập feedback, review error samples, version dataset.

## 12. Dùng Được Trong Production Không?

Có, sentiment classifier kiểu này dùng được trong production nếu thỏa các điều kiện sau:

1. Dataset đại diện domain thật, đủ size và có label guideline rõ.
2. Có baseline và Transformer được so sánh trên cùng train/validation/test split.
3. Test set không bị leakage; duplicate/variant cùng nguồn được split theo group và có metric theo từng class, đặc biệt là `negative`.
4. Artifact lưu đầy đủ model, tokenizer, label mapping, preprocessing config, metric và manifest.
5. API load model một lần, validate input, có timeout, health/readiness và logging không lộ PII.
6. Đã benchmark p95/p99 latency, memory và throughput trên hardware deploy thật.
7. Có monitoring drift, confidence, label distribution, error rate và rollback plan.
8. License của model/dataset phù hợp với môi trường sử dụng.

Không nên đưa vào production nếu chỉ train bằng synthetic fallback, chỉ có accuracy, không có confusion matrix, không kiểm soát label mapping, chưa benchmark latency hoặc chưa rõ data privacy.

## 13. Best Solution Theo Context

| Context | Gợi ý |
|---|---|
| Cần ship dashboard sentiment nội bộ trong 1 tuần | Baseline TF-IDF + Logistic Regression, monitor lỗi, giữ API schema mở để thay model |
| Cần route negative ticket realtime với SLA thấp | Baseline hoặc DistilBERT, threshold cẩn thận, human-in-the-loop |
| Cần quality tiếng Việt cao cho review đa dạng | Fine-tune PhoBERT, benchmark latency, cân nhắc GPU/ONNX |
| Data ít hơn vài nghìn sample | Baseline trước, active learning, freeze encoder hoặc dùng pretrained multilingual nhỏ |
| Có nhiều ngôn ngữ | BERT/DistilBERT multilingual hoặc model multilingual chuyên dụng |
| Có compliance nghiêm ngặt | Self-host, không log raw text, model/dataset license review, audit artifact |

## 14. Kết Quả Cần Nộp

Sau khi hoàn thành bài này, mini-project nên có:

- `train_sentiment.py` chạy được từ CSV hoặc synthetic fallback.
- `serve_sentiment.py` expose FastAPI inference.
- `artifacts/sentiment_classifier/comparison.json`.
- `artifacts/sentiment_classifier/labels.json`.
- `artifacts/sentiment_classifier/model_card.md`.
- Một đoạn kết luận: chọn baseline hay Transformer cho production v1, vì sao, còn thiếu điều kiện gì.

## 15. Tự Kiểm Tra

1. Vì sao baseline là bắt buộc trước Transformer?
2. Khi nào macro F1 quan trọng hơn accuracy?
3. Train-serving skew trong tokenizer/preprocessing gây lỗi gì?
4. Vì sao label mapping phải nằm trong artifact?
5. Khi nào PhoBERT đáng dùng hơn BERT multilingual?
6. API production cần log những metric nào?
7. Dùng model này trong production được không? Điều kiện còn thiếu là gì?
