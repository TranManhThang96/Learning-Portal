# Day 6 Document: Metrics Reference Và Production Checklist

Tài liệu này dùng như cheat sheet khi review model. Mục tiêu là giúp bạn chọn metric nhanh nhưng vẫn đúng context.

## 1. Classification Metrics Reference

Ký hiệu:

| Ký hiệu | Ý nghĩa |
|---|---|
| `TP` | Actual positive, predicted positive |
| `FP` | Actual negative, predicted positive |
| `FN` | Actual positive, predicted negative |
| `TN` | Actual negative, predicted negative |

| Metric | Công thức | Trả lời câu hỏi | Cẩn thận |
|---|---|---|---|
| Accuracy | `(TP + TN) / total` | Dự đoán đúng bao nhiêu trên tổng số? | Misleading khi class imbalance |
| Precision | `TP / (TP + FP)` | Trong những case bị báo positive, bao nhiêu case đúng? | Có thể cao nhưng bỏ sót nhiều |
| Recall | `TP / (TP + FN)` | Trong positive thật, bắt được bao nhiêu? | Có thể cao nhưng tạo nhiều FP |
| F1 | `2PR / (P + R)` | Precision và recall cân bằng thế nào? | Không phản ánh cost lệch |
| FPR | `FP / (FP + TN)` | Negative thật bị báo nhầm bao nhiêu? | FPR nhỏ vẫn có nhiều FP nếu negative rất lớn |
| Specificity | `TN / (TN + FP)` | Negative thật được giữ đúng bao nhiêu? | Ít trực quan với business hơn FP count |
| ROC-AUC | Area under ROC curve | Ranking positive cao hơn negative tốt không? | Có thể lạc quan với positive hiếm |
| Average Precision (AP) | Precision trung bình có trọng số theo mức tăng recall | Model xử lý positive hiếm tốt không? | Không giống hoàn toàn trapezoidal PR-AUC; không chọn threshold thay bạn |

## 2. Regression Metrics Reference

| Metric | Diễn giải | Khi nên dùng | Khi không nên dùng |
|---|---|---|---|
| MAE | Sai số tuyệt đối trung bình, cùng đơn vị với target | Stakeholder cần hiểu nhanh; outlier không nên chi phối quá mạnh | Lỗi lớn nghiêm trọng nhưng bị phạt chưa đủ mạnh |
| MSE | Sai số bình phương trung bình | Làm loss function; muốn phạt lỗi lớn | Đơn vị bị bình phương, khó giải thích |
| RMSE | Căn bậc hai của MSE, cùng đơn vị với target | Lỗi lớn nguy hiểm; cần cùng đơn vị với target | Nhạy với outlier |
| MAPE | Sai số phần trăm trung bình | Forecasting khi target luôn dương và xa 0 | Target gần 0 hoặc có 0 |
| p95 absolute error | 95% sample có lỗi dưới mức này | Cần quản lý tail risk/SLA | Không thay thế metric trung bình |

Checklist regression:

- Luôn xem distribution của residual.
- Báo cáo metric theo segment quan trọng.
- Với forecasting, so sánh với naive baseline: dự đoán bằng ngày/tuần trước.
- Nếu target có nhiều giá trị gần 0, đừng dùng MAPE làm metric chính.
- Nếu lỗi under-prediction và over-prediction có cost khác nhau, cân nhắc metric custom hoặc quantile loss.

## 3. Ranking Metrics Reference

| Metric | Dùng cho | Ý nghĩa | Trade-off |
|---|---|---|---|
| Recall@k | Retrieval, RAG, recommendation | Trong top-k có lấy đủ item relevant không? | Tăng k thường tăng recall nhưng tăng latency/cost |
| Precision@k | Search/recommendation | Top-k sạch đến mức nào? | Không đo đủ recall nếu nhiều relevant item |
| MRR | FAQ/search có một answer chính | Item đúng đầu tiên nằm cao không? | Không quan tâm nhiều relevant item sau item đúng đầu |
| NDCG@k | Search/recommendation có relevance grade | Item relevant cao có được xếp lên đầu không? | Cần label relevance theo mức |

RAG rule:

```text
Retrieval quality trước, generation quality sau.
Nếu Recall@k thấp, LLM thiếu context đúng và dễ hallucinate.
```

## 4. Decision Matrix Chọn Metric

| Context | Metric chính | Metric phụ | Quyết định thường gặp |
|---|---|---|---|
| Binary classification cân bằng | Accuracy, F1, ROC-AUC | Confusion matrix | Chọn model có generalization tốt |
| Fraud/anomaly positive hiếm | AP, recall, precision, FP/FN count | ROC-AUC, calibration | Chọn threshold theo cost/capacity |
| Medical/security triage | Recall, FN count | Precision, workload | Giữ recall cao, thêm human review |
| Auto block/ban user | Precision, FP count | Recall, complaint rate | Threshold cao, audit kỹ |
| Churn campaign | AP, recall@budget, calibration | ROI, uplift | Chọn top-N user để target |
| Regression forecast | MAE/RMSE, p95 error | MAPE nếu an toàn | Chọn model theo cost lỗi lớn |
| Search/RAG retrieval | Recall@k, MRR/NDCG | Latency, token cost | Chọn k/reranker theo quality-cost |

## 5. Threshold Selection Recipes

### Recipe A: Tối Đa F1

Dùng khi:

- Precision và recall quan trọng tương đối cân bằng.
- Chưa có cost model rõ.
- Cần baseline nhanh.

Không đủ khi:

- `FP` và `FN` có cost lệch mạnh.
- Có capacity constraint.
- Action positive gây hại lớn.

### Recipe B: Recall Guardrail

```text
Chọn threshold có cost thấp nhất
với điều kiện recall >= target_recall
```

Dùng khi bỏ sót positive rất nguy hiểm. Ví dụ: security triage muốn recall ít nhất 95%.

### Recipe C: Precision Guardrail

```text
Chọn threshold có recall cao nhất
với điều kiện precision >= target_precision
```

Dùng khi action positive gây tác động mạnh. Ví dụ: auto block cần precision ít nhất 98%.

### Recipe D: Capacity Constraint

```text
Chọn threshold có expected value cao nhất
với điều kiện alerts_per_day <= analyst_capacity
```

Dùng khi đội vận hành chỉ xử lý được số case hữu hạn.

### Recipe E: Expected Value

Ví dụ fraud manual review:

```text
value = TP * fraud_loss_prevented
cost = FP * false_positive_friction + (TP + FP) * review_cost
net_value = value - cost
```

Chọn threshold có `net_value` cao nhất, sau đó kiểm tra guardrail:

- Precision tối thiểu.
- Recall tối thiểu.
- Alert volume.
- Segment fairness.
- Latency.

## 6. Fraud Evaluation Template

Khi review fraud model, báo cáo ít nhất:

```text
Dataset:
- Time window:
- Train/validation/test split:
- Positive class:
- Fraud rate:
- Label delay:

Score metrics:
- ROC-AUC:
- Average Precision:
- Calibration check:

Threshold decision:
- Candidate thresholds:
- Selected threshold:
- Precision / recall / F1:
- TP / FP / FN / TN:
- Alerts per day:
- Expected net value:
- Capacity OK:

Segment checks:
- Country:
- Merchant category:
- Payment method:
- Customer age/cohort:
- Device/channel:

Production checks:
- Feature latency p95:
- Inference latency p95:
- Drift monitoring:
- Feedback loop:
- Human review process:
```

## 7. Segment Metrics

Aggregate metric có thể che lỗi theo segment. Luôn kiểm tra các segment có business hoặc fairness risk:

- Region/country.
- Language.
- Device/channel.
- Customer type.
- Merchant category.
- Account age.
- Transaction amount bucket.
- Traffic source.

Ví dụ một fraud model có precision tổng 70%, nhưng ở segment `new_user + wallet` precision chỉ 20%. Nếu auto block segment này, business sẽ nhận nhiều complaint dù aggregate nhìn ổn.

## 8. Offline Vs Online Metrics

| Loại metric | Ví dụ | Mục tiêu | Rủi ro |
|---|---|---|---|
| Offline ML metric | ROC-AUC, AP, F1, MAE, NDCG | So sánh model trước deploy | Dataset không đại diện production |
| Online technical metric | Latency, error rate, throughput | Hệ thống chạy ổn định | Model đúng nhưng serve chậm |
| Online business metric | Fraud loss, conversion, revenue, retention | Tác động thật | Bị ảnh hưởng bởi nhiều yếu tố ngoài model |
| Ops metric | Alert volume, review SLA, analyst precision | Vận hành được không | Model tạo workload vượt capacity |

Không deploy chỉ vì offline metric tăng. Hãy hỏi:

```text
Metric tăng có đủ lớn để đáng risk không?
Có cải thiện business metric không?
Có làm xấu latency/cost/capacity không?
Có segment nào bị ảnh hưởng xấu không?
```

## 9. Production Readiness Checklist

- [ ] Target, positive class và prediction time được định nghĩa rõ.
- [ ] Split đúng với cách dữ liệu xuất hiện trong production.
- [ ] Không fit preprocessing trên test set.
- [ ] Không dùng feature tương lai hoặc target proxy.
- [ ] Có baseline đơn giản để so sánh.
- [ ] Báo cáo class distribution.
- [ ] Có confusion matrix tại selected threshold.
- [ ] Có ROC-AUC và Average Precision cho score; nếu báo cáo trapezoidal PR-AUC thì ghi rõ cách tính.
- [ ] Có threshold sweep với FP/FN/TP/TN.
- [ ] Threshold được chọn theo cost, capacity hoặc guardrail.
- [ ] Có metrics theo segment quan trọng.
- [ ] Có calibration check nếu score được hiểu là probability.
- [ ] Có performance metrics: latency p95/p99, throughput, memory/cost.
- [ ] Có logging model version, feature version, score, threshold và action.
- [ ] Có monitoring drift và metric sau deploy.
- [ ] Có rollback/fallback/human review cho action rủi ro cao.

## 10. API Ghi Nhớ Cho Bài Tập scikit-learn

Các API dùng trong bài tập đã được đối chiếu với tài liệu stable của scikit-learn qua Context7:

- `sklearn.pipeline.Pipeline`
- `sklearn.compose.ColumnTransformer`
- `sklearn.preprocessing.OneHotEncoder(handle_unknown="ignore")`
- `sklearn.metrics.confusion_matrix`
- `sklearn.metrics.precision_recall_curve`
- `sklearn.metrics.average_precision_score`
- `sklearn.metrics.roc_auc_score`
- `sklearn.model_selection.train_test_split`

Pattern production-friendly:

```python
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

preprocess = ColumnTransformer(
    transformers=[
        ("num", numeric_pipeline, numeric_features),
        ("cat", categorical_pipeline, categorical_features),
    ]
)

model = Pipeline(
    steps=[
        ("preprocess", preprocess),
        ("classifier", classifier),
    ]
)
```

Điểm quan trọng: mọi transformer có `.fit()` phải nằm trong `Pipeline` và chỉ fit trên training data.

Với scikit-learn stable hiện tại, `TunedThresholdClassifierCV` có thể tune decision threshold bằng cross-validation. Trong khóa học ta vẫn sweep threshold thủ công để thấy rõ FP/FN/capacity. Dù dùng cách nào, không được fit model và tune threshold trên cùng dữ liệu; hãy dùng validation set mới hoặc cross-validation phù hợp.

## 11. Câu Trả Lời Production Ngắn Gọn

Dùng được trong production không? Có, nếu:

- Dataset evaluation đúng thời gian và đại diện traffic thật.
- Metric được chọn theo business objective.
- Threshold được chọn theo cost/capacity/guardrail.
- Có monitoring online và process review định kỳ.
- Có kiểm tra segment, drift, latency và feedback bias.

Không đủ production nếu chỉ có một notebook với accuracy/ROC-AUC đẹp nhưng không có threshold, cost model, segment analysis và monitoring plan.

## 12. Nguồn Đã Xác Minh Bằng Context7

Đối chiếu ngày 8/6/2026 với tài liệu scikit-learn stable:

- [Classification metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#classification-metrics)
- [`precision_recall_curve`](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html)
- [`average_precision_score`](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
- [Decision threshold tuning](https://scikit-learn.org/stable/modules/classification_threshold.html)
- [`TunedThresholdClassifierCV`](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TunedThresholdClassifierCV.html)
- [Common pitfalls và data leakage](https://scikit-learn.org/stable/common_pitfalls.html)
