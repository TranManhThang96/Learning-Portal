# Day 8: Mini-project - Customer Churn ML Pipeline

## Mục Tiêu

Day 8 là mini-project tổng hợp Phase 1. Mục tiêu không phải đạt score cao nhất, mà là xây được một ML pipeline đúng quy trình, có thể kiểm thử, có thể lặp lại và đủ gần production để một Senior Software Engineer hiểu được toàn bộ vòng đời từ dữ liệu đến inference.

Kết thúc bài này, bạn cần làm được:

- Định nghĩa bài toán customer churn bằng ngôn ngữ business và ML.
- Dùng Telco Customer Churn hoặc dataset tương đương để thực hiện EDA.
- Thiết kế feature engineering không gây data leakage.
- Train và so sánh ít nhất 3 models: Logistic Regression baseline, Random Forest, Gradient Boosting.
- Đánh giá bằng nhiều metrics: ROC-AUC, Average Precision, precision, recall, F1, confusion matrix và latency.
- Tune threshold theo mục tiêu business thay vì dùng mặc định `0.5`.
- Làm error analysis trên false positives, false negatives và từng customer segment.
- Save model artifact kèm metadata, threshold, schema và metrics.
- Viết inference function có input contract rõ ràng.
- Trả lời rõ: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## TL;DR

Customer churn prediction là bài toán binary classification: dự đoán xác suất một customer sẽ rời bỏ dịch vụ trong một horizon cụ thể, ví dụ 30 ngày hoặc cuối kỳ hợp đồng. Một pipeline tốt cần nhất quán giữa training và serving:

```text
Raw data
-> schema validation
-> EDA
-> train/validation/test split
-> feature engineering trong pipeline
-> preprocessing bằng ColumnTransformer
-> train nhiều models
-> evaluate bằng ranking metrics và threshold metrics
-> tune threshold trên validation set
-> error analysis trên test set
-> save artifact kèm metadata
-> inference function có contract
```

Best default cho Day 8:

- Dùng `Pipeline` để gói feature engineering, preprocessing và model.
- Dùng `ColumnTransformer` để xử lý numerical/categorical columns tách biệt.
- Dùng `OneHotEncoder(handle_unknown="ignore")` cho category mới ở inference.
- Dùng Logistic Regression làm baseline bắt buộc.
- So sánh với Random Forest và Gradient Boosting.
- Chọn model theo Average Precision, F1 tại threshold đã tune, latency và explainability.
- Nếu score cải thiện không đáng kể, ưu tiên baseline đơn giản hơn cho v1.

## Dùng Được Trong Production Không?

Có thể dùng làm v1 production nếu thỏa các điều kiện sau:

- Label churn được định nghĩa rõ: churn là gì, horizon bao lâu, thời điểm tạo label là khi nào.
- Dataset training đại diện cho traffic thật và có split phù hợp. Nếu dữ liệu có timestamp, ưu tiên time-based split thay vì random split.
- Feature tại training đều available tại prediction time. Không dùng target proxy hoặc future information.
- Preprocessing nằm trong artifact, không viết lại thủ công ở service.
- Có schema validation trước training và inference.
- Threshold được chọn theo cost FP/FN hoặc mục tiêu business như recall tối thiểu.
- Artifact lưu model, threshold, feature schema, package versions, training date, metrics và limitation.
- Artifact `joblib` chỉ được load từ nguồn tin cậy; pickle-based format có thể thực thi code và không bảo đảm tương thích giữa các version scikit-learn.
- Custom transformer phải nằm trong module importable ổn định; chạy training qua launcher riêng để artifact không tham chiếu class dưới `__main__`.
- Có monitoring: input null rate, unknown category rate, prediction distribution, positive rate, latency, drift và business outcome.
- Có quy trình rollback model và đánh giá định kỳ.

Chưa nên dùng production nếu:

- Chỉ train trong notebook, không lưu artifact reproducible.
- Chưa có validation/test set độc lập.
- Chưa làm error analysis theo segment quan trọng.
- Chưa biết action sau prediction là gì.
- Chưa có policy cho PII, logging và retention campaign.
- Dùng random split trong khi data thật có strong time drift mà chưa kiểm chứng.

## 1. Problem Framing

Churn prediction không phải câu hỏi "customer có churn không" một cách mơ hồ. Bài toán cần được đóng khung như sau:

```text
Dựa trên thông tin có sẵn tại prediction_time,
dự đoán xác suất customer sẽ churn trong prediction_horizon.
```

Ví dụ output nên là probability và decision metadata, không chỉ là class:

```json
{
  "customer_id": "CUST_000123",
  "churn_probability": 0.73,
  "risk_tier": "high",
  "decision": "send_retention_offer",
  "model_version": "churn-v1",
  "threshold": 0.45
}
```

Các câu hỏi business cần chốt trước khi train:

| Câu hỏi | Vì sao quan trọng |
|---|---|
| Churn horizon là 30 ngày, 60 ngày hay cuối hợp đồng? | Horizon khác nhau tạo label khác nhau, model khác nhau |
| Customer nào nằm trong population scoring? | Không nên score customer không thể hành động hoặc không đủ dữ liệu |
| Action sau prediction là gì? | Threshold phụ thuộc vào campaign capacity và cost |
| False positive tốn gì? | Gửi offer cho người không churn gây lãng phí hoặc giảm revenue |
| False negative tốn gì? | Bỏ lỡ customer sắp churn |
| Có constraint về fairness/segment không? | Model có thể over-target một nhóm customer |

Best solution theo context Day 8: giả định horizon là "churn trong kỳ tiếp theo", dùng dataset Telco để học quy trình. Khi áp dụng ở công ty thật, phần định nghĩa label và point-in-time data quan trọng hơn việc đổi model.

## 2. Dataset Và Schema

Dataset gợi ý: Telco Customer Churn. Nếu không có CSV, bạn có thể dùng synthetic dataset có schema tương tự để luyện pipeline, nhưng khi đánh giá portfolio nên dùng dataset thật.

Một số cột thường gặp:

| Column | Type gợi ý | Ý nghĩa | Production note |
|---|---|---|---|
| `customerID` | string | ID customer | Không dùng làm feature |
| `gender` | categorical | Giới tính | Cần cân nhắc fairness |
| `SeniorCitizen` | numeric/binary | Khách hàng cao tuổi | Có thể là sensitive-ish feature |
| `Partner` | categorical | Có partner hay không | Category mới cần xử lý |
| `Dependents` | categorical | Có người phụ thuộc hay không | Category mới cần xử lý |
| `tenure` | numeric | Số tháng sử dụng | Feature mạnh, nhưng cần kiểm tra missing/outlier |
| `PhoneService` | categorical | Có phone service hay không | Categorical |
| `InternetService` | categorical | DSL/Fiber/No | Segment quan trọng |
| `Contract` | categorical | Month-to-month/One year/Two year | Feature rất mạnh |
| `PaperlessBilling` | categorical | Billing điện tử | Categorical |
| `PaymentMethod` | categorical | Phương thức thanh toán | Có thể liên quan đến churn |
| `MonthlyCharges` | numeric | Phí hàng tháng | Cần xử lý outlier |
| `TotalCharges` | numeric/string | Tổng phí đã trả | Hay bị đọc thành string hoặc blank |
| `Churn` | target | Yes/No hoặc 1/0 | Không được xuất hiện trong inference input |

Data quality issues thường gặp:

- `TotalCharges` có blank string, cần convert bằng `pd.to_numeric(errors="coerce")`.
- Categorical values có whitespace.
- Class imbalance: churn thường ít hơn non-churn.
- Category ở production có thể không có trong training.
- Một số feature có thể không available tại prediction time trong hệ thống thật.

## 3. Kiến Trúc Pipeline

Pipeline mục tiêu:

```text
data/telco.csv
  -> load + schema validation
  -> EDA report
  -> split train/validation/test
  -> sklearn Pipeline
       -> feature builder
       -> ColumnTransformer
            -> numeric: median imputation + scaling
            -> categorical: most-frequent imputation + one-hot
       -> classifier
  -> model comparison
  -> threshold tuning trên validation set
  -> final evaluation trên test set
  -> error analysis
  -> joblib artifact
  -> predict_customer_churn(customer: dict) -> dict
```

Điểm quan trọng: mọi transformer có `.fit()` chỉ được fit trên training data. Không fit scaler, encoder hoặc imputer trên toàn bộ dataset trước khi split.

## 4. EDA Tối Thiểu Cần Có

EDA trong bài này không phải vẽ biểu đồ cho đẹp. Mục tiêu là phát hiện rủi ro dữ liệu trước khi train.

Checklist EDA:

- Shape: số rows, số columns.
- Target distribution: churn rate.
- Missing rate theo column.
- Duplicate `customerID`.
- Numeric summary: min, p25, median, p75, max.
- Cardinality của categorical columns.
- Churn rate theo segment: `Contract`, `InternetService`, `PaymentMethod`, `tenure_group`.
- Outlier rõ ràng: `tenure < 0`, `MonthlyCharges < 0`, `TotalCharges` blank.

Ví dụ interpretation:

- Nếu churn rate rất thấp, Precision-Recall curve và Average Precision thường hữu ích hơn ROC-AUC.
- Nếu `Contract=Month-to-month` có churn rate cao, đây là segment cần error analysis riêng.
- Nếu `TotalCharges` missing chủ yếu ở `tenure=0`, missing không hẳn là lỗi, có thể mang ý nghĩa nghiệp vụ.

## 5. Feature Engineering

Feature engineering nên đơn giản, kiểm thử được và không leak dữ liệu. Với Telco, các feature hợp lý:

| Feature | Cách tạo | Lợi ích | Rủi ro |
|---|---|---|---|
| `avg_monthly_charge_observed` | `TotalCharges / tenure`, fallback `MonthlyCharges` khi `tenure=0` | Bắt quan hệ giữa tenure và spend | Cần xử lý chia cho 0 |
| `tenure_group` | bin `tenure` thành nhóm | Dễ error analysis và model học non-linear nhẹ | Binning mất thông tin |
| `monthly_charge_band` | bin `MonthlyCharges` | Giúp slice analysis | Ngưỡng bin có thể không ổn theo thị trường |
| Raw categorical one-hot | `Contract`, `InternetService`, `PaymentMethod` | Baseline mạnh cho tabular | Feature space tăng theo cardinality |

Không nên làm trong Day 8:

- Target encoding nếu chưa có cross-validation đúng cách, vì dễ leakage.
- Feature dùng event sau thời điểm churn.
- Dùng `customerID` làm feature.
- Tune feature thủ công theo test set.

Best solution: để feature engineering deterministic nằm trong `Pipeline` hoặc ít nhất trong function được dùng chung cho training và inference. Không copy logic feature engineering sang service bằng tay.

## 6. Model Choices

| Model | Vai trò | Mạnh | Yếu | Khi chọn |
|---|---|---|---|---|
| Logistic Regression | Baseline bắt buộc | Nhanh, dễ giải thích, latency thấp | Khó bắt interaction phức tạp | V1 production khi score đủ tốt |
| Random Forest | Candidate non-linear | Robust, ít cần scaling, bắt interaction | Artifact lớn hơn, probability có thể chưa calibrated | Khi quality tăng rõ và latency chấp nhận |
| Gradient Boosting | Candidate mạnh cho tabular | Thường tốt trên tabular vừa/nhỏ | Cần tuning, dễ overfit nếu thiếu discipline | Khi validation/test ổn định và monitoring đủ |

Trade-off thực tế:

- Nếu Logistic Regression kém Average Precision 1-2 điểm nhưng nhanh, dễ debug và đủ đáp ứng business, chọn Logistic Regression cho v1.
- Nếu Gradient Boosting cải thiện recall ở cùng precision rõ ràng, có thể chọn Gradient Boosting.
- Nếu Random Forest artifact lớn và p99 latency cao trong API synchronous, dùng batch scoring thay vì realtime.

## 7. Metrics Và Threshold

Không dùng accuracy làm metric chính cho churn nếu class imbalance. Một model dự đoán tất cả là "No churn" có thể accuracy cao nhưng vô dụng.

Metrics cần report:

| Metric | Dùng để trả lời | Lưu ý |
|---|---|---|
| ROC-AUC | Model rank positive cao hơn negative tốt không? | Có thể lạc quan khi positive class nhỏ |
| Average Precision | Model duy trì precision thế nào khi recall tăng? | Hữu ích cho churn/retention |
| Precision | Gửi campaign cho người được flag thì bao nhiêu người thật sự churn? | Liên quan cost FP |
| Recall | Bắt được bao nhiêu churners thật? | Liên quan cost FN |
| F1 | Cân bằng precision/recall | Không thay thế business cost |
| Confusion matrix | TP/FP/FN/TN cụ thể | Dễ giải thích với stakeholder |
| Latency | Dự đoán mất bao lâu | Quan trọng nếu serve realtime |

Threshold tuning:

```text
1. Train model trên train set.
2. Predict probability trên validation set.
3. Quét threshold từ 0.10 đến 0.90.
4. Chọn threshold theo objective, ví dụ recall >= 0.75 rồi maximize precision.
5. Chỉ sau khi chọn xong mới đánh giá test set.
```

Không tune threshold trên test set. Test set là dữ liệu "chưa đụng tới" để ước lượng performance cuối.

## 8. Error Analysis

Error analysis là deliverable bắt buộc, không phải phần trang trí.

Cần xem:

- Top false positives: model rất tự tin customer churn nhưng thực tế không churn.
- Top false negatives: model bỏ sót customer churn thật.
- Slice metrics theo `Contract`, `InternetService`, `PaymentMethod`, `tenure_group`.
- Segment có recall thấp bất thường.
- Segment có predicted positive rate lệch xa actual positive rate.

Ví dụ câu hỏi:

- Model bỏ sót nhiều customer `Month-to-month` mới đăng ký không?
- Model over-predict churn cho `Fiber optic` vì lịch sử training bias không?
- Threshold chung có làm một segment bị recall quá thấp không?

Nếu phát hiện một segment quan trọng có performance kém, các hướng xử lý:

- Thu thập thêm dữ liệu cho segment đó.
- Thêm feature liên quan đến behavior trước churn.
- Tune threshold theo segment, nhưng cần kiểm soát fairness và complexity.
- Chạy campaign thí điểm để đo business lift thay vì chỉ nhìn offline metrics.

## 9. Artifact Và Inference Contract

Model artifact không chỉ là model weights. Artifact cần chứa:

- Fitted `Pipeline`.
- `threshold`.
- `model_name`.
- `schema_version`.
- `raw_feature_columns`.
- `numeric_features` và `categorical_features` sau feature engineering.
- Metrics trên validation/test.
- Training time, package versions, random seed.
- Limitation và intended use.

Inference input contract:

```json
{
  "customerID": "CUST_000123",
  "gender": "Female",
  "SeniorCitizen": 0,
  "Partner": "Yes",
  "Dependents": "No",
  "tenure": 12,
  "PhoneService": "Yes",
  "InternetService": "Fiber optic",
  "Contract": "Month-to-month",
  "PaperlessBilling": "Yes",
  "PaymentMethod": "Electronic check",
  "MonthlyCharges": 89.9,
  "TotalCharges": 1020.3
}
```

Inference output contract:

```json
{
  "customer_id": "CUST_000123",
  "churn_probability": 0.73,
  "will_churn": true,
  "risk_tier": "high",
  "threshold": 0.45,
  "model_name": "gradient_boosting",
  "schema_version": "telco-churn-v1"
}
```

Production note: với API thật, không nên log raw PII. Log request ID, schema version, missing count, model version, latency và prediction score bucket là đủ trong đa số trường hợp.

## 10. Performance Và Deployment

Performance cần nhìn theo context:

- Batch daily scoring: latency từng record ít quan trọng hơn throughput, cost và reproducibility.
- Realtime API: cần đo p50/p95/p99 latency, artifact load time và memory footprint.
- Logistic Regression thường nhanh nhất.
- Random Forest có latency tăng theo số cây và depth.
- Gradient Boosting có latency phụ thuộc số estimators, thường vẫn ổn với tabular nhỏ.

Best solution cho churn trong nhiều công ty: batch scoring mỗi ngày hoặc mỗi vài giờ, lưu score vào database/CRM để retention team dùng. Realtime API chỉ cần nếu action xảy ra ngay trong user session, ví dụ hiển thị offer tại thời điểm customer vào trang hủy dịch vụ.

## 11. README Và Model Card Tối Thiểu

README của mini-project cần có:

- Problem statement.
- Dataset và target definition.
- Feature list và feature engineering.
- Split strategy.
- Models đã thử.
- Metrics và threshold objective.
- Error analysis summary.
- Production readiness.
- Cách train và cách inference.
- Limitations.

Model card tối thiểu:

```text
Model: customer-churn-v1
Intended use: prioritize retention outreach
Not intended use: fully automated denial, pricing discrimination
Training data: Telco Customer Churn or equivalent
Target: churn in defined horizon
Primary metric: Average Precision + recall at selected threshold
Threshold: chosen on validation set
Known limitations: offline dataset, no live feedback, possible segment bias
Monitoring: input drift, score drift, outcome drift, latency
```

## 12. Checklist Hoàn Thành Day 8

- [ ] Có dataset Telco hoặc synthetic fallback tương đương.
- [ ] Có EDA report.
- [ ] Có schema validation cho training và inference.
- [ ] Feature engineering không dùng target hoặc future data.
- [ ] Dùng `Pipeline` và `ColumnTransformer`.
- [ ] Dùng `OneHotEncoder(handle_unknown="ignore")`.
- [ ] Train ít nhất 3 models.
- [ ] Report ROC-AUC, Average Precision, precision, recall, F1, confusion matrix.
- [ ] Tune threshold trên validation set.
- [ ] Đánh giá cuối trên test set.
- [ ] Có error analysis FP/FN và slice metrics.
- [ ] Save artifact bằng `joblib`.
- [ ] Chỉ load artifact tin cậy và có test tương thích dependency.
- [ ] Artifact có metadata.
- [ ] Có inference function trả probability, decision, threshold và risk tier.
- [ ] Có performance measurement.
- [ ] Có README/trade-off/production notes.

## Lỗi Hay Gặp

- Fit encoder/scaler trước split.
- Dùng test set để chọn threshold.
- Chỉ report accuracy.
- Save model nhưng quên save threshold.
- Pickle custom transformer từ file chạy trực tiếp, khiến artifact tham chiếu module `__main__` và không load được ở service.
- Training có feature engineering, inference lại không có.
- Không xử lý category mới ở production.
- Dùng `customerID` làm feature.
- Không kiểm tra `TotalCharges` blank.
- Không phân tích false negatives trong segment giá trị cao.
- Nói "production-ready" khi chưa có monitoring và rollback.

## Tự Kiểm Tra

1. Vì sao cần validation set riêng cho threshold tuning?
2. Khi nào Precision-Recall curve và Average Precision quan trọng hơn ROC-AUC?
3. Nếu Gradient Boosting tốt hơn Logistic Regression rất ít, bạn chọn model nào cho v1 và vì sao?
4. Artifact cần lưu gì ngoài model object?
5. Nếu inference input có category mới chưa từng thấy, pipeline nên xử lý thế nào?
6. Vì sao batch scoring thường hợp lý hơn realtime API cho churn?
7. Điều kiện tối thiểu để gọi pipeline này là production-ready là gì?
