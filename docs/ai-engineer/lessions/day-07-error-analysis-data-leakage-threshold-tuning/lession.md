# Day 7: Error Analysis, Data Leakage, Threshold Tuning

## Mục tiêu

Sau bài này bạn cần làm được những việc sau:

- Phân tích model sai ở đâu thay vì chỉ nhìn một metric tổng.
- Đọc confusion matrix theo chi phí business của false positive và false negative.
- Slice lỗi theo segment như contract, tenure bucket, region, payment method.
- Tune threshold từ `0.30` đến `0.80` theo business objective, không mặc định `0.50`.
- Biết khi nào cần calibration và cách kiểm tra probability có đáng tin không.
- Phát hiện data leakage, train-serving skew và distribution shift.
- Tạo baseline regression test để model hoặc threshold mới không làm production tệ hơn.

## TL;DR

Classification model không kết thúc ở `model.predict`. Trong production, model thường trả probability, còn quyết định cuối cùng phụ thuộc vào threshold, capacity, cost và policy. Error analysis là bước debug model giống cách Senior SE debug production incident: chia theo segment, tìm nhóm lỗi nặng, xem top false positives/false negatives, xác định nguyên nhân rồi mới quyết định sửa data, feature, model hay threshold.

Với churn prediction, false positive nghĩa là gửi ưu đãi cho khách không định rời đi, tốn budget. False negative nghĩa là bỏ lỡ khách sắp churn, mất revenue. Nếu false negative đắt hơn nhiều so với false positive, threshold nên thấp hơn `0.50` để tăng recall, nhưng phải kiểm soát số lượng case gửi cho sales/CSKH.

## Bối cảnh thực hành

Bài này dùng bài toán customer churn dạng tabular classification:

- Input: tenure, monthly charges, số ticket hỗ trợ, usage drop, payment failures, contract type, internet service, region.
- Output: `churn = 1` nếu khách có nguy cơ rời đi.
- Model trả `P(churn)`, ví dụ `0.72`.
- Business action: gửi offer, gọi CSKH, hoặc đưa vào queue review.

Điểm quan trọng: `0.72` chưa phải quyết định. Quyết định phụ thuộc vào threshold:

```text
if P(churn) >= threshold:
    action = "intervene"
else:
    action = "no_action"
```

Threshold là một policy runtime. Nó cần được version, audit và rollback được giống config quan trọng trong backend service.

## Workflow chuẩn từ offline metric đến production decision

### Step 1: Khóa baseline và metric contract

Trước khi phân tích lỗi, cần biết baseline hiện tại là gì.

Baseline tối thiểu nên có:

- Model version: ví dụ `churn-logreg-calibrated-v1`.
- Dataset snapshot hoặc training window.
- Feature contract: danh sách feature, type, missing policy, category policy.
- Metric tổng: ROC-AUC, PR-AUC, precision, recall, F1.
- Threshold hiện tại và lý do chọn.
- Segment metrics quan trọng.
- Expected cost/profit nếu có business cost.

Ví dụ metric contract:

| Metric | Gate ví dụ | Vì sao |
|---|---:|---|
| ROC-AUC | không giảm quá 0.01 so với baseline | Kiểm tra ranking quality tổng |
| PR-AUC | không giảm quá 0.02 | Quan trọng khi positive class hiếm |
| Recall tại threshold đã chọn | `>= 0.75` | Không bỏ lỡ quá nhiều khách churn |
| Precision tại threshold đã chọn | `>= 0.35` | Tránh spam offer quá rộng |
| Predicted positive rate | `<= 0.45` | Đảm bảo capacity CSKH |
| Segment recall thấp nhất | `>= 0.50` | Tránh model tệ ở một nhóm khách |

Không nên dùng test set để chọn threshold. Dùng validation set để chọn threshold, giữ test set cho đánh giá cuối cùng.

### Step 2: Đọc confusion matrix theo business cost

Confusion matrix cho binary classification:

| | Predicted 0 | Predicted 1 |
|---|---:|---:|
| Actual 0 | True Negative | False Positive |
| Actual 1 | False Negative | True Positive |

Trong churn:

- True Positive: model bắt đúng khách sẽ churn, có thể can thiệp.
- False Positive: khách không churn nhưng vẫn bị offer, tốn chi phí.
- False Negative: khách sẽ churn nhưng bị bỏ lỡ, mất revenue.
- True Negative: khách ổn, không cần can thiệp.

Ví dụ business cost:

```text
TP value: giữ được một phần revenue, +300 USD
FP cost: offer hoặc cuộc gọi không cần thiết, -40 USD
FN cost: mất khách, -1,200 USD
```

Khi FN đắt hơn FP, tối ưu accuracy hoặc F1 có thể không đủ. Bạn nên tune threshold theo expected profit hoặc theo constraint như `recall >= 0.80`.

### Step 3: Error slicing theo segment

Metric tổng có thể che giấu lỗi nghiêm trọng ở segment nhỏ.

Ví dụ:

```text
Overall F1: 0.73

F1 by contract:
- month_to_month: 0.76
- one_year: 0.55
- two_year: 0.31
```

Overall nhìn ổn, nhưng model gần như không dùng được cho `two_year`. Với production, lỗi này có thể dẫn đến unfair treatment, lãng phí budget hoặc bỏ lỡ nhóm khách có giá trị cao.

Các segment nên slice trong bài toán churn:

- `contract`: month-to-month, one-year, two-year.
- `tenure_bucket`: 0-6, 7-12, 13-24, 25+ tháng.
- `internet_service`: DSL, fiber, none.
- `region`: north, south, central.
- `monthly_charge_bucket`: low, medium, high.
- `payment_method` nếu có.

Mỗi slice nên xem:

- Count.
- Actual positive rate.
- Predicted positive rate.
- Precision.
- Recall.
- F1.
- Confusion counts: TN, FP, FN, TP.

Lưu ý trade-off: slice càng nhỏ càng dễ nhiễu. Không nên kết luận mạnh từ segment chỉ có vài chục sample. Cần minimum sample size, confidence interval hoặc so sánh qua nhiều snapshot.

### Step 4: Xem top false positives và false negatives

Sau khi có threshold, luôn tạo bảng:

- Top false positives có probability cao nhất.
- Top false negatives có probability thấp nhất.
- Các sample gần threshold nhất.

Vì sao cần ba nhóm này:

- High-confidence false positives chỉ ra feature/model đang hiểu sai pattern nào đó.
- High-confidence false negatives chỉ ra khách nguy hiểm mà model rất tự tin bỏ lỡ.
- Near-threshold samples giúp quyết định vùng nào cần human review hoặc rule bổ sung.

Ví dụ câu hỏi khi review top FP/FN:

- Có category mới mà training chưa thấy không?
- Có missing value bị xử lý khác production không?
- Có segment bị under-represented trong training không?
- Label có bị delay hoặc sai không?
- Feature có được tạo sau thời điểm dự đoán không?

### Step 5: Threshold tuning từ 0.30 đến 0.80

Default `0.50` chỉ hợp lý khi:

- Probability đã calibrated.
- Class tương đối cân bằng.
- FP và FN có cost gần nhau.
- Không có capacity constraint.

Trong thực tế, các điều kiện này hiếm khi cùng đúng.

Threshold thấp:

- Recall tăng.
- False negative giảm.
- Precision thường giảm.
- Nhiều case cần xử lý hơn.

Threshold cao:

- Precision tăng.
- False positive giảm.
- Recall giảm.
- Bỏ lỡ nhiều positive hơn.

Một sweep đơn giản:

```text
threshold: 0.30, precision: 0.32, recall: 0.91, f1: 0.47
threshold: 0.40, precision: 0.39, recall: 0.84, f1: 0.53
threshold: 0.50, precision: 0.48, recall: 0.70, f1: 0.57
threshold: 0.60, precision: 0.58, recall: 0.51, f1: 0.54
threshold: 0.70, precision: 0.69, recall: 0.30, f1: 0.42
threshold: 0.80, precision: 0.78, recall: 0.12, f1: 0.21
```

Cách chọn threshold theo context:

| Context | Objective hợp lý | Threshold thường |
|---|---|---|
| Churn, FN rất đắt | Recall tối thiểu, tối đa expected profit | Thấp hơn `0.50` |
| Fraud review có đội manual nhỏ | Precision hoặc top-K capacity | Cao hơn `0.50` |
| Medical screening | Recall rất cao, human review sau | Thấp |
| Spam blocking tự động | Precision cao để tránh chặn nhầm | Cao |
| Lead scoring sales | Top-K theo capacity/ngày | Dynamic theo queue size |

Best solution cho churn trong bài này: chọn threshold trên validation set bằng rule `recall >= target` rồi tối đa expected profit hoặc precision. Sau đó đánh giá một lần trên test set và lưu threshold thành artifact riêng.

### Step 6: Calibration

Calibration trả lời câu hỏi: nếu model nói `P(churn) = 0.80`, trong 100 khách tương tự có khoảng 80 khách churn thật không?

Ranking tốt không đồng nghĩa probability tốt. Model có thể phân biệt thứ tự khách rủi ro cao/thấp tốt, nhưng probability bị over-confident hoặc under-confident.

Khi nào cần calibration:

- Dùng probability để tính expected value.
- Dùng risk score trong policy hoặc pricing.
- So sánh probability giữa nhiều model.
- Gửi probability cho stakeholder hoặc downstream service.
- Tune threshold dựa trên cost cụ thể.

Khi nào calibration ít quan trọng hơn:

- Chỉ cần ranking top-K.
- Probability không được expose.
- Threshold được chọn trực tiếp từ validation set và không diễn giải như xác suất tuyệt đối.

Kỹ thuật phổ biến:

- Platt scaling/sigmoid: ổn khi data calibration không lớn, ít overfit hơn.
- Isotonic regression: linh hoạt hơn nhưng cần nhiều data calibration.
- Reliability table/diagram: chia probability thành bin, so sánh predicted probability trung bình với actual positive rate.
- Brier score: đo lỗi probability, càng thấp càng tốt.

Trade-off: calibration thêm một bước training và có thể overfit nếu calibration set nhỏ. Với scikit-learn, dùng `CalibratedClassifierCV` trong pipeline đánh giá để tránh tự viết logic sai.

### Step 7: Data leakage

Data leakage xảy ra khi training nhìn thấy thông tin mà production inference không có tại thời điểm dự đoán.

Đây là một trong những lỗi nguy hiểm nhất trong ML vì offline metric rất đẹp nhưng deploy thì hỏng.

Các dạng leakage thường gặp:

| Loại leakage | Ví dụ | Cách tránh |
|---|---|---|
| Target leakage | `customer_cancelled_at`, `cancel_reason` dùng để predict churn | Review timeline feature với domain expert |
| Temporal leakage | Dùng giao dịch sau ngày dự đoán | Time-based split, point-in-time join |
| Preprocessing leakage | Fit scaler/encoder trên toàn bộ dataset trước split | Dùng `Pipeline`, chỉ fit trên train |
| Duplicate leakage | Cùng customer xuất hiện ở train và test | Split theo entity/group hoặc time |
| Aggregation leakage | Feature 30 ngày nhưng aggregate cả tương lai | Feature store có event time và cutoff time |
| Human-process leakage | Ticket reason được cập nhật sau khi biết outcome | Ghi rõ availability time của mỗi feature |
| Label leakage qua sampling | Lọc dataset bằng điều kiện phụ thuộc outcome | Review query tạo training data |

Checklist nhanh:

- Feature này có tồn tại trước prediction time không?
- Feature này có được cập nhật sau khi customer churn không?
- Feature này có được tính bằng dữ liệu của toàn bộ dataset không?
- Một customer hoặc cùng household có nằm ở cả train và test không?
- Split có tôn trọng thời gian production không?

### Step 8: Train-serving skew

Train-serving skew là khác biệt giữa cách tạo feature lúc training và lúc inference.

Ví dụ:

- Training fill missing bằng median, production fill bằng `0`.
- Training category là `Fiber optic`, production gửi `fiber_optic`.
- Training timezone UTC, production timezone local.
- Training dùng full preprocessing pipeline, production reimplement logic bằng code khác.
- Training one-hot có category cố định, production gặp category mới và crash.

Cách giảm skew:

- Serialize nguyên `Pipeline` gồm preprocessing và model.
- Dùng `OneHotEncoder(handle_unknown="ignore")` cho categorical feature có category mới.
- Viết schema validation cho inference input.
- Dùng shared feature code hoặc feature store.
- Log feature distribution và prediction distribution theo version.
- Contract test giữa training pipeline và serving service.

### Step 9: Distribution shift

Distribution shift là production data thay đổi so với training data.

Nguyên nhân:

- Marketing campaign mới làm khách rủi ro vào nhiều hơn.
- Giá thay đổi.
- Competitor launch.
- Seasonality.
- Kênh acquisition mới.
- Thay đổi product hoặc policy billing.
- Bug trong upstream data pipeline.

Monitor tối thiểu:

- Feature distribution: mean/std, missing rate, category share.
- Prediction distribution: histogram probability, predicted positive rate.
- Input volume theo segment.
- Delayed label performance khi label thật xuất hiện.
- Segment metrics theo cohort thời gian.

Nếu production positive rate tăng từ 10% lên 40%, không kết luận ngay là churn tăng thật. Cần kiểm tra:

1. Schema/input có đổi không.
2. Feature distribution nào drift mạnh.
3. Model version hoặc threshold version có đổi không.
4. Upstream data pipeline có bug không.
5. Business event nào xảy ra.
6. Delayed labels có xác nhận pattern này không.

### Step 10: Baseline regression test

Baseline regression test trong ML giống test suite trong backend, nhưng kiểm tra hành vi thống kê.

Các gate nên có:

- Metric tổng không giảm quá ngưỡng.
- Threshold mới không phá capacity.
- Segment quan trọng không tụt quá mạnh.
- Confusion matrix không tăng FN/FP vượt mức cho phép.
- Probability calibration không tệ hơn nhiều.
- Data quality check không có schema/missing/category bất thường.

Ví dụ rule:

```text
Model mới chỉ được promote nếu:
- ROC-AUC >= baseline ROC-AUC - 0.01
- PR-AUC >= baseline PR-AUC - 0.02
- Recall at selected threshold >= 0.75
- Predicted positive rate <= 0.45
- Không segment nào có recall < 0.50 với count >= 200
```

Không nên để một metric duy nhất quyết định deployment.

## Best solution theo context Day 7

Với churn-like tabular classification, giải pháp hợp lý nhất cho giai đoạn foundation:

1. Train baseline bằng scikit-learn `Pipeline` + `ColumnTransformer`.
2. Encode categorical feature bằng `OneHotEncoder(handle_unknown="ignore")`.
3. Fit toàn bộ preprocessing chỉ trên train để tránh preprocessing leakage.
4. Dùng validation set để sweep threshold từ `0.30` đến `0.80`.
5. Chọn threshold theo business rule, ví dụ `recall >= 0.75` rồi tối đa expected profit.
6. Đánh giá cuối cùng trên test set.
7. Tạo slice metrics cho ít nhất `contract`, `tenure_bucket`, `internet_service`.
8. Xuất top 20 FP/FN và near-threshold samples cho human review.
9. Nếu probability được dùng để tính cost/risk, thêm `CalibratedClassifierCV` và kiểm tra Brier score/reliability table.
10. Lưu artifact gồm model pipeline, feature contract, threshold, threshold version, model version, training snapshot và metric summary.
11. Chạy baseline regression gates trong CI hoặc trước khi promote model.

## Performance considerations

- Threshold sweep rất rẻ: với `n` sample và `k` thresholds, chi phí khoảng `O(n*k)`. Với vài trăm nghìn dòng và 11 threshold từ `0.30` đến `0.80`, Pandas vẫn ổn.
- Error slicing trên dataset lớn nên đẩy về SQL/Spark hoặc batch job, không nhất thiết chạy trong request path.
- Calibration thường không làm inference chậm đáng kể, nhưng tăng complexity training và cần validation/calibration data đủ tốt.
- Serialize full pipeline giúp giảm train-serving skew, nhưng artifact có thể lớn. Cần version và kiểm soát tương thích dependency.
- Logging full feature vector có rủi ro PII và tốn storage. Production nên log sample, hash ID, aggregate metrics và chỉ lưu raw feature khi có policy rõ ràng.
- Với model tabular đơn giản như Logistic Regression, inference latency thường thấp. Bottleneck production thường là feature retrieval, validation, network và logging.

## Dùng được trong production không?

Có, cách làm trong bài này dùng được trong production nếu đáp ứng các điều kiện sau:

- Dataset split đúng theo thời gian hoặc entity, không leakage.
- Pipeline preprocessing được serialize cùng model, không reimplement khác ở serving.
- Threshold được chọn trên validation set, test set chỉ dùng đánh giá cuối.
- Threshold có version riêng, audit log và rollback path.
- Có baseline regression gates trước khi promote model/threshold mới.
- Có monitoring cho input distribution, prediction distribution, positive rate, latency và delayed label quality.
- Có schema validation cho inference input.
- Có quy trình xử lý drift, skew và incident.
- Có kiểm soát PII trong logging và artifact.

Chưa nên dùng production nếu:

- Threshold được tune trên test set.
- Feature có thể chứa thông tin sau prediction time.
- Training và serving dùng hai code path preprocessing khác nhau.
- Không biết FP/FN cost hoặc capacity.
- Không có monitoring sau deploy.
- Không có rollback threshold/model.

## Liên kết thực hành

- Bài tập chi tiết: [exercise.md](./exercise.md)
- Script Python minh họa gần production: [exercise.py](./exercise.py)
- Checklist vận hành và template review: [document.md](./document.md)
