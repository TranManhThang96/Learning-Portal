# Day 6: Model Evaluation Metrics

## Mục Tiêu

Day 3 đã nói về train/validation/test split và overfitting. Day 4-5 đã đưa bạn đến scikit-learn stack và feature engineering. Day 6 trả lời câu hỏi tiếp theo: model đã train xong thì đánh giá thế nào để không chọn nhầm model đẹp trên notebook nhưng gây thiệt hại trong production?

Kết thúc bài này, bạn cần làm được:

- Giải thích được `accuracy`, `precision`, `recall`, `F1`, `ROC-AUC`, Precision-Recall curve, `Average Precision` và `confusion matrix` bằng ngôn ngữ business.
- Chọn metric đúng cho imbalanced classification, đặc biệt là fraud detection.
- Hiểu và dùng đúng regression metrics: `MAE`, `MSE`, `RMSE`, `MAPE`.
- Hiểu ranking metrics: `MRR`, `NDCG`, `Recall@k`, và vì sao chúng quan trọng cho recommendation/search/RAG.
- Tách bạch `ML metric` với `business metric`, rồi nối chúng bằng cost, profit, SLA, capacity và risk.
- Thiết kế evaluation workflow gần production: fixed test set, threshold sweep, segment metrics, monitoring, drift và calibration.
- Trả lời rõ: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## TL;DR

Evaluation metric là test suite của ML system, nhưng khác unit test ở chỗ output thường là xác suất và quyết định phụ thuộc business context. Không có "metric tốt nhất" cho mọi bài toán. Accuracy chỉ đáng tin khi class tương đối cân bằng và cost của các loại lỗi gần nhau. Với positive class hiếm như fraud, Average Precision, recall, precision tại threshold cụ thể và confusion matrix thường quan trọng hơn accuracy.

Best default khi đánh giá một model tabular classification:

```text
Xác định positive class và action sau prediction
-> xem class distribution
-> train baseline đơn giản
-> báo cáo ROC-AUC, Precision-Recall curve và Average Precision trên score
-> sweep threshold
-> chọn threshold theo cost/capacity/guardrail
-> kiểm tra confusion matrix theo segment
-> log metric offline và online sau deploy
```

## 1. Metric Không Chỉ Là Công Thức

Metric là cách bạn biến một mục tiêu mơ hồ như "model tốt hơn" thành tiêu chí ra quyết định. Với production ML, metric phải trả lời được:

- Model sai theo kiểu nào?
- Kiểu sai đó gây thiệt hại gì?
- Ai hoặc hệ thống nào sẽ hành động dựa trên prediction?
- Action đó có capacity, latency hoặc compliance constraint không?
- Model tốt offline có thật sự cải thiện business KPI online không?

Ví dụ fraud detection:

| Câu hỏi | Ý nghĩa kỹ thuật | Ý nghĩa business |
|---|---|---|
| Positive class là gì? | `fraud = 1` | Giao dịch cần chặn hoặc review |
| Model trả gì? | Probability/score | Mức nghi ngờ fraud |
| Action là gì? | Threshold decision | Cho qua, manual review, hoặc block |
| False positive là gì? | Legit transaction bị flag | Khách thật bị làm phiền, giảm conversion |
| False negative là gì? | Fraud lọt qua | Mất tiền, chargeback, risk compliance |
| Capacity là gì? | Số alert xử lý được | Analyst chỉ review được N case/ngày |

Nếu chưa định nghĩa action và cost, bạn chưa thật sự chọn được metric.

## 2. Confusion Matrix

`confusion matrix` là điểm bắt đầu tốt nhất cho classification vì nó hiển thị trực tiếp các loại đúng/sai.

| | Predicted Positive | Predicted Negative |
|---|---:|---:|
| Actual Positive | True Positive (`TP`) | False Negative (`FN`) |
| Actual Negative | False Positive (`FP`) | True Negative (`TN`) |

Trong fraud detection:

- `TP`: fraud bị phát hiện.
- `FP`: giao dịch hợp lệ bị flag.
- `FN`: fraud lọt qua.
- `TN`: giao dịch hợp lệ được cho qua.

Công thức tổng:

```text
total = TP + FP + FN + TN
```

Điểm cần nhớ: confusion matrix phụ thuộc threshold. Cùng một model probability có thể tạo ra nhiều confusion matrix khác nhau khi threshold thay đổi.

## 3. Accuracy Và Cái Bẫy Imbalanced Dataset

`accuracy` đo tỷ lệ dự đoán đúng:

```text
accuracy = (TP + TN) / (TP + FP + FN + TN)
```

Accuracy hữu ích khi:

- Class tương đối cân bằng.
- Cost của `FP` và `FN` gần nhau.
- Bạn không chỉ quan tâm một class hiếm.
- Dataset test phản ánh đúng traffic production.

Accuracy dễ gây hại khi positive class hiếm. Nếu fraud rate là 1%, model luôn dự đoán "not fraud" vẫn đạt 99% accuracy nhưng bắt được 0 fraud:

```text
TP = 0
FP = 0
FN = toàn bộ fraud
TN = toàn bộ giao dịch hợp lệ
accuracy rất cao, business value gần như bằng 0
```

Tư duy cho Senior SE: accuracy giống một uptime aggregate toàn hệ thống. Số tổng thể có thể đẹp, nhưng endpoint quan trọng nhất vẫn có thể đang fail.

## 4. Precision, Recall Và F1

### Precision

`precision` trả lời: trong các case model báo positive, bao nhiêu case thật sự positive?

```text
precision = TP / (TP + FP)
```

Ưu tiên precision khi action positive đắt hoặc gây hại:

- Tự động block payment.
- Ban account.
- Gửi cảnh báo bảo mật đến khách hàng.
- Tạo ticket cho đội vận hành có capacity thấp.

Trade-off: tăng precision thường làm giảm recall. Model cẩn trọng hơn, ít báo nhầm hơn, nhưng bỏ sót nhiều positive hơn.

### Recall

`recall` trả lời: trong các positive thật, model bắt được bao nhiêu?

```text
recall = TP / (TP + FN)
```

Ưu tiên recall khi bỏ sót nguy hiểm:

- Fraud mất tiền thật.
- Medical triage.
- Security incident.
- PII leak.
- Abuse/spam nghiêm trọng.

Trade-off: tăng recall thường làm giảm precision. Model báo nhiều hơn, bắt được nhiều positive hơn, nhưng tạo thêm false positive và workload.

### F1

`F1` là harmonic mean của precision và recall:

```text
F1 = 2 * precision * recall / (precision + recall)
```

F1 hữu ích khi:

- Bạn cần một số tổng hợp để so sánh nhanh nhiều model.
- Precision và recall đều quan trọng tương đối cân bằng.
- Chưa có cost model đủ tin cậy.

F1 không đủ khi cost lệch mạnh. Nếu `FN` fraud tốn 500 USD nhưng `FP` chỉ tốn 5 USD review, chọn threshold theo F1 có thể không tối ưu business.

## 5. ROC-AUC, Precision-Recall Curve Và Average Precision

Nhiều model trả score/probability thay vì label cứng. Khi đó cần metric đánh giá khả năng ranking trước khi chọn threshold.

### ROC-AUC

`ROC curve` vẽ quan hệ giữa:

```text
TPR = recall = TP / (TP + FN)
FPR = FP / (FP + TN)
```

`ROC-AUC` đo xác suất model xếp một positive ngẫu nhiên cao hơn một negative ngẫu nhiên. Giá trị gần 1 tốt hơn, 0.5 tương đương random.

Ưu điểm:

- Không phụ thuộc một threshold cố định.
- Tốt để so sánh ranking quality tổng quát giữa các model.
- Ít bị ảnh hưởng bởi việc chọn threshold sai tạm thời.

Nhược điểm:

- Có thể quá lạc quan với imbalanced dataset.
- FPR nhỏ nhìn có vẻ tốt, nhưng vì số negative rất lớn nên vẫn có thể tạo rất nhiều false positive.
- Không nói trực tiếp threshold nào dùng được trong production.

### Precision-Recall Curve, PR-AUC Và Average Precision

`Precision-Recall curve` vẽ quan hệ giữa precision và recall khi threshold thay đổi. Cụm từ `PR-AUC` thường được dùng không chặt chẽ cho một số cách tóm tắt curve. Trong scikit-learn:

- `average_precision_score` tính **Average Precision (AP)** bằng trung bình có trọng số của precision theo mức tăng recall.
- `auc(recall, precision)` tính diện tích hình thang dưới các điểm trên curve.
- Hai con số có thể khác nhau; phải ghi rõ report đang dùng cách nào.

Trong khóa học này, code dùng `average_precision_score`, vì vậy report sẽ gọi chính xác là `Average Precision (AP)`.

Precision-Recall curve và AP thường hữu ích hơn ROC-AUC khi positive class hiếm:

- Fraud.
- Churn rate thấp.
- Rare disease.
- Anomaly detection.
- Phishing/spam hiếm nhưng quan trọng.

Baseline trực giác của AP gần với positive rate. Nếu fraud rate là 1%, model random có AP khoảng 0.01. Model đạt AP 0.25 có thể đã tốt hơn random rất nhiều, dù con số nghe không "cao" như ROC-AUC 0.95.

Rule thực tế:

| Context | Metric nên xem trước | Lý do |
|---|---|---|
| Class cân bằng, cost tương đối đều | Accuracy, ROC-AUC, F1 | Aggregate không quá misleading |
| Positive hiếm | AP, recall/precision tại threshold | Tập trung vào class cần bắt |
| Action positive rất đắt | Precision tại threshold, FP count | Tránh báo nhầm quá nhiều |
| Bỏ sót rất đắt | Recall tại threshold, FN cost | Tránh lọt case nguy hiểm |
| Có capacity cố định | Alerts per day, precision, cost | Metric phải khớp vận hành |

## 6. Threshold Là Business Decision

Model thường trả probability:

```text
p(fraud) = 0.73
```

Bạn cần threshold để chuyển score thành decision:

```text
if p(fraud) >= threshold:
    flag_for_review()
else:
    approve()
```

Default `0.5` hiếm khi tối ưu. Threshold nên được chọn theo một trong các chiến lược:

- Tối đa hóa F1 khi precision và recall quan trọng tương đối cân bằng.
- Đạt `recall >= target`, rồi chọn precision/cost tốt nhất.
- Đạt `precision >= target`, rồi chọn recall tốt nhất.
- Tối đa hóa expected profit hoặc tối thiểu hóa expected cost.
- Giữ số alert dưới capacity vận hành.
- Dùng nhiều threshold cho nhiều action: allow, review, block.

Ví dụ 3 vùng quyết định trong fraud:

| Score | Action | Lý do |
|---:|---|---|
| `< 0.20` | Allow | Risk thấp |
| `0.20 - 0.85` | Manual review | Cần người kiểm tra |
| `>= 0.85` | Auto block | Precision đủ cao để tự động chặn |

Đây thường là thiết kế tốt hơn một threshold duy nhất vì cost của manual review khác cost của auto block.

## 7. Regression Metrics: MAE, MSE, RMSE, MAPE

Regression dự đoán giá trị liên tục: giá nhà, demand, latency, revenue, delivery time. Classification metrics không dùng được trực tiếp.

| Metric | Công thức trực giác | Khi dùng | Trade-off |
|---|---|---|---|
| `MAE` | Trung bình `abs(y_true - y_pred)` | Cần dễ giải thích, outlier không nên chi phối quá mạnh | Không phạt lỗi lớn mạnh như RMSE |
| `MSE` | Trung bình bình phương lỗi | Training objective phổ biến, phạt lỗi lớn | Đơn vị bị bình phương, khó giải thích |
| `RMSE` | Căn bậc hai của MSE | Muốn phạt lỗi lớn nhưng vẫn cùng đơn vị với target | Nhạy với outlier |
| `MAPE` | Trung bình lỗi phần trăm | Forecasting cần diễn giải theo % | Rất nguy hiểm khi `y_true` gần 0 |

Ví dụ chọn metric:

- Dự đoán delivery time: `MAE` dễ nói "sai trung bình 4.2 phút".
- Dự đoán demand cho kho hàng: `RMSE` nếu lỗi lớn gây hết hàng nghiêm trọng.
- Dự đoán revenue theo cửa hàng: `MAPE` hữu ích nếu mọi cửa hàng có doanh thu đủ xa 0; nếu có cửa hàng revenue gần 0, dùng `MAE`, `SMAPE` hoặc metric custom.

Không chỉ nhìn một metric. Với regression production, nên báo cáo ít nhất:

```text
MAE + RMSE + percentile absolute error + segment error
```

Ví dụ p95 absolute error giúp biết tail risk, tương tự latency p95 trong backend.

## 8. Ranking Metrics: Recall@k, MRR, NDCG

Ranking metrics dùng khi output là danh sách được sắp xếp: search result, recommendation, retrieval cho RAG.

### Recall@k

`Recall@k` trả lời: trong top-k kết quả, hệ thống có lấy được item đúng không?

```text
Recall@k = số relevant item xuất hiện trong top-k / tổng số relevant item
```

Với RAG, Recall@k rất quan trọng. Nếu retrieval không đưa đúng context vào top-k, LLM gần như không có cơ hội trả lời đúng, dù prompt hay.

### MRR

`MRR` là mean reciprocal rank. Nó thưởng mạnh khi item đúng xuất hiện ở vị trí cao.

```text
rank 1 -> 1.0
rank 2 -> 0.5
rank 5 -> 0.2
không tìm thấy -> 0
```

MRR phù hợp khi mỗi query thường chỉ cần một câu trả lời/item đúng đầu tiên.

### NDCG

`NDCG` dùng khi có nhiều mức relevance, ví dụ:

```text
0 = không liên quan
1 = hơi liên quan
2 = liên quan
3 = rất liên quan
```

NDCG thưởng việc đưa item relevance cao lên đầu danh sách. Nó phù hợp cho search, recommendation và RAG khi nhiều tài liệu có thể hỗ trợ câu trả lời ở mức khác nhau.

Rule chọn ranking metric:

| Bài toán | Metric chính | Vì sao |
|---|---|---|
| RAG cần lấy đủ context | Recall@k | Không retrieve đúng thì generation khó đúng |
| FAQ/search cần câu trả lời đầu tiên tốt | MRR | Rank đầu rất quan trọng |
| Search/recommendation có nhiều mức relevance | NDCG@k | Thưởng thứ tự và relevance grade |
| Feed/recommendation tối ưu click/conversion | NDCG@k + business metric | Ranking tốt chưa chắc tăng revenue |

## 9. Business Metric Vs ML Metric

`ML metric` đo model trên dataset. `Business metric` đo tác động thật của quyết định trong hệ thống.

| Use case | ML metric | Business metric |
|---|---|---|
| Fraud detection | AP, recall, precision, FP/FN count | Fraud amount prevented, chargeback rate, legitimate approval rate, analyst workload |
| Churn prediction | ROC-AUC, AP, calibration, recall@top% | Retention uplift, campaign ROI, discount cost |
| Recommendation | NDCG@k, Recall@k, CTR prediction AUC | Conversion, revenue/session, long-term retention |
| RAG retrieval | Recall@k, MRR, NDCG@k | Answer correctness, support deflection, hallucination rate |
| Demand forecast | MAE, RMSE, p95 error | Stockout rate, inventory cost, waste |

Một metric offline tốt chỉ là điều kiện cần. Điều kiện đủ là metric đó phải liên hệ được với decision và outcome.

## 10. Fraud Case Study

### Bối cảnh

Giả sử hệ thống payment có 100,000 giao dịch/ngày:

- Fraud rate: 1%.
- Mỗi fraud lọt qua gây mất trung bình 500 USD.
- Mỗi case manual review tốn 4 USD.
- Mỗi false positive gây friction 15 USD do giảm conversion, support ticket hoặc trải nghiệm xấu.
- Đội analyst xử lý tối đa 300 alert/ngày.

### Vì Sao Accuracy Không Đủ?

Model luôn dự đoán "not fraud":

```text
accuracy khoảng 99%
recall = 0
fraud prevented = 0
business loss vẫn rất lớn
```

Với fraud, câu hỏi đúng không phải "accuracy bao nhiêu?" mà là:

- Bắt được bao nhiêu fraud thật?
- Để bắt được số đó phải review/chặn nhầm bao nhiêu giao dịch hợp lệ?
- Alert volume có vượt capacity không?
- Expected value sau khi trừ review cost và friction có dương không?
- Có segment nào bị false positive quá cao không?

### Khi Nào Ưu Tiên Recall?

Ưu tiên recall khi:

- Fraud amount lớn.
- Regulatory/compliance risk cao.
- Hệ thống có manual review capacity đủ lớn.
- False positive chỉ gây friction nhẹ, không tự động block.

Ví dụ: giao dịch lớn hoặc merchant risk cao có thể dùng threshold thấp hơn để bắt nhiều fraud hơn.

### Khi Nào Ưu Tiên Precision?

Ưu tiên precision khi:

- Action là auto block.
- False positive làm mất khách hàng hoặc doanh thu lớn.
- Analyst capacity rất thấp.
- Có yêu cầu legal/compliance về giải thích quyết định.

Ví dụ: threshold auto block phải cao hơn threshold manual review.

### Best Solution Theo Context

Thiết kế tốt hơn cho fraud thường là policy nhiều tầng:

| Tier | Điều kiện | Action | Metric guardrail |
|---|---|---|---|
| Low risk | Score thấp | Approve | FN rate theo segment |
| Medium risk | Score trung bình | Manual review | Alert volume, precision, analyst SLA |
| High risk | Score rất cao | Step-up auth hoặc block | Precision rất cao, complaint rate |

Khi fraud loss lớn và capacity thấp, dùng threshold sweep theo expected value nhưng thêm constraint capacity:

```text
Chọn threshold có net value cao nhất
với điều kiện alerts_per_day <= analyst_capacity
và precision >= mức tối thiểu business chấp nhận
```

## 11. Evaluation Workflow Gần Production

Quy trình thực tế nên đi theo thứ tự:

1. Định nghĩa target, positive class và prediction time.
2. Chọn split đúng: time-based split nếu dữ liệu có thời gian; stratified split cho bài tập/baseline.
3. Giữ test set cố định, không tune nhiều lần trên test set.
4. Train baseline đơn giản trước: dummy classifier, logistic regression, tree baseline.
5. Báo cáo class distribution và confusion matrix.
6. Báo cáo score metrics: ROC-AUC và Average Precision; nếu dùng diện tích hình thang PR-AUC thì ghi rõ cách tính.
7. Sweep threshold và tính precision, recall, F1, FP, FN, alert volume.
8. Tính business cost/profit theo assumption rõ ràng.
9. Kiểm tra metrics theo segment: country, merchant category, channel, device, customer type.
10. Kiểm tra calibration nếu probability được dùng như xác suất thật.
11. Chạy shadow mode hoặc A/B test trước khi tự động hóa action rủi ro.
12. Sau deploy, monitor data drift, label drift, precision proxy, alert volume, latency và business KPI.

## 12. Performance Considerations

Evaluation không chỉ là chất lượng model. Trong production, bạn phải đo cả runtime:

- Feature generation latency.
- Model inference latency p50/p95/p99.
- Batch scoring time.
- Memory footprint.
- Throughput.
- Cost per 1,000 predictions.
- Alert volume per hour/day.

Fraud realtime target minh họa:

```text
Feature fetch p95: < 50 ms
Model inference p95: < 20 ms
Decision end-to-end p95: < 100 ms
Alert volume: <= analyst capacity
```

Threshold sweep nên vectorized thay vì gọi model lại nhiều lần. Model chỉ cần scoring một lần để tạo `y_score`; sau đó tính metrics cho nhiều threshold từ cùng score.

Với ranking/RAG, performance còn gồm:

- Retrieval latency.
- Số document top-k.
- Reranking latency.
- Context size đưa vào LLM.
- Cost token.

Tăng `k` có thể cải thiện Recall@k nhưng làm tăng latency, cost và nguy cơ đưa noise vào prompt.

## 13. Production Concerns

Những lỗi thường làm evaluation sai:

- Data leakage: feature chứa thông tin tương lai hoặc target proxy.
- Test set bị dùng quá nhiều lần để tune model.
- Label delay: fraud/churn label xuất hiện muộn.
- Feedback bias: chỉ case bị flag mới được review nên label không đầy đủ.
- Segment fairness: aggregate tốt nhưng một nhóm khách hàng bị FP cao.
- Calibration kém: score 0.8 không tương đương xác suất 80%.
- Distribution drift: fraud pattern thay đổi sau vài tuần.
- Business process thay đổi: đội analyst tăng/giảm capacity nhưng threshold không đổi.

Mitigation:

- Dùng validation set để tune, test set để estimate cuối.
- Dùng time-based backtesting nếu dữ liệu có thời gian.
- Log score, threshold, features version, model version và action.
- Lưu evaluation dataset như regression test.
- Có dashboard offline/online metric.
- Review threshold định kỳ theo capacity và drift.

## 14. Dùng Được Trong Production Không?

Có, các metrics và workflow trong bài dùng được trong production, nhưng chỉ khi thỏa các điều kiện sau:

- Dataset evaluation đại diện cho traffic production hoặc được backtest theo thời gian.
- Target và positive class được định nghĩa đúng business.
- Không có leakage giữa train/validation/test.
- Threshold được chọn theo cost, capacity hoặc guardrail cụ thể, không dùng mặc định `0.5` vô thức.
- Metrics được báo cáo theo segment quan trọng, không chỉ aggregate.
- Probability được calibration nếu dùng như xác suất thật.
- Có monitoring sau deploy cho drift, latency, alert volume và business KPI.
- Có fallback/human review cho action rủi ro cao.
- Cost assumption được owner business xác nhận và cập nhật khi business thay đổi.

Nếu thiếu các điều kiện trên, metrics vẫn hữu ích cho học tập và offline research, nhưng chưa đủ để tự động ra quyết định production.

## 15. Tự Kiểm Tra

1. Vì sao model luôn dự đoán class majority có thể có accuracy cao nhưng business value thấp?
2. Trong fraud detection, `FP` và `FN` gây hậu quả khác nhau thế nào?
3. Khi nào nên nhìn Precision-Recall curve và AP trước ROC-AUC?
4. Vì sao threshold `0.5` không nên là lựa chọn mặc định?
5. F1 có thể sai hướng khi cost `FP` và `FN` lệch mạnh như thế nào?
6. Với bài toán delivery time prediction, khi nào chọn MAE và khi nào chọn RMSE?
7. Trong RAG, vì sao Recall@k thường là retrieval metric đầu tiên cần nhìn?
8. Cần điều kiện gì để đưa threshold đã chọn vào production?
