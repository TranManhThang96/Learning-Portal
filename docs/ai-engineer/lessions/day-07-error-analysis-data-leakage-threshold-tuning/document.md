# Day 7 Document: Production Checklist và Review Template

## 1. Confusion matrix cheat sheet

| Case | Ý nghĩa trong churn | Hành động |
|---|---|---|
| TP | Khách sẽ churn và model bắt đúng | Gửi offer, gọi CSKH, đưa vào retention flow |
| FP | Khách không churn nhưng bị cảnh báo | Tốn budget, có thể làm phiền khách |
| FN | Khách sẽ churn nhưng model bỏ lỡ | Mất revenue, cần ưu tiên giảm nếu churn cost cao |
| TN | Khách không churn và model bỏ qua | Không cần action |

Luôn gắn FP/FN với cost thật. Nếu chưa có cost thật, ghi assumption rõ ràng và review lại sau khi có dữ liệu.

## 2. Error analysis checklist

- [ ] Có metric tổng: ROC-AUC, Average Precision, precision, recall, F1.
- [ ] Có confusion matrix tại threshold đang dùng.
- [ ] Có threshold sweep từ `0.30` đến `0.80`.
- [ ] Có lý do chọn threshold bằng business objective.
- [ ] Có top 20 false positives.
- [ ] Có top 20 false negatives.
- [ ] Có sample gần threshold.
- [ ] Có slice metrics theo ít nhất 2 segment quan trọng.
- [ ] Có minimum sample size cho slice metrics.
- [ ] Có nhận xét cụ thể: lỗi đến từ data, feature, label, model hay threshold.

## 3. Threshold Decision Record

Template nên lưu cùng artifact hoặc trong model registry:

```yaml
model_version: churn-logreg-calibrated-v1
threshold_version: threshold-recall75-profit-v1
threshold: 0.42
selected_on: validation
selected_at: 2026-05-09T00:00:00Z
business_objective: maximize expected profit with recall >= 0.75
constraints:
  min_recall: 0.75
  max_predicted_positive_rate: 0.45
cost_assumptions:
  tp_retained_value: 300
  fp_offer_cost: 40
  fn_lost_value: 1200
validation_metrics:
  precision: 0.41
  recall: 0.78
  f1: 0.54
  predicted_positive_rate: 0.39
approval:
  owner: growth-ml
  reviewer: retention-business-owner
rollback:
  previous_model_version: churn-logreg-calibrated-v0
  previous_threshold_version: threshold-v0
```

## 4. Data leakage review checklist

Hỏi những câu này cho từng feature:

- [ ] Feature có tồn tại trước prediction time không?
- [ ] Feature có phụ thuộc trực tiếp hoặc gián tiếp vào label không?
- [ ] Feature có được tạo sau khi customer churn không?
- [ ] Aggregation window có dùng dữ liệu tương lai không?
- [ ] Query tạo training data có filter nào dựa trên outcome không?
- [ ] Có duplicate customer/entity giữa train và test không?
- [ ] Preprocessing có fit trên toàn bộ dataset trước split không?
- [ ] Label delay có làm train/test bị sai thời điểm không?
- [ ] Feature này có thể được tính giống hệt ở serving không?

Red flags:

- Tên cột chứa `cancel`, `closed`, `resolved_after`, `refund_after`, `final_status`.
- Feature có correlation gần tuyệt đối với label.
- Offline metric tăng đột biến sau khi thêm một feature.
- Feature chỉ có trong warehouse, không có trong online serving path.

## 5. Train-serving skew checklist

- [ ] Training và serving dùng cùng serialized preprocessing pipeline.
- [ ] Input schema có validation type/range/category.
- [ ] Missing value policy giống nhau.
- [ ] Categorical normalization giống nhau.
- [ ] Timezone và cutoff time giống nhau.
- [ ] Feature code có test với fixture production-like.
- [ ] `model_version`, `feature_version`, `threshold_version` được log ở mỗi prediction.
- [ ] Có alert khi missing rate/category unknown/predicted positive rate đổi mạnh.

## 6. Distribution shift dashboard

Dashboard tối thiểu nên có:

| Signal | Cách đọc |
|---|---|
| Input volume theo ngày | Phát hiện upstream outage hoặc traffic spike |
| Missing rate theo feature | Phát hiện schema/API bug |
| Numeric mean/std/p95 | Phát hiện drift ở feature liên tục |
| Category share | Phát hiện category mới hoặc mapping lỗi |
| Prediction probability histogram | Phát hiện model output lệch bất thường |
| Predicted positive rate | Phát hiện threshold/model/data shift |
| Segment predicted positive rate | Phát hiện drift cục bộ |
| Delayed precision/recall | Xác nhận chất lượng khi label thật về |

Alert không nên chỉ dựa vào một signal. Ví dụ positive rate tăng có thể do churn thật tăng, upstream bug, threshold đổi hoặc model artifact sai.

## 7. Baseline regression gates

Ví dụ gate trước khi promote:

| Gate | Rule ví dụ | Lý do |
|---|---:|---|
| ROC-AUC | `new >= old - 0.01` | Ranking quality không tụt nhiều |
| Average Precision | `new >= old - 0.02` | Positive class thường hiếm |
| Recall | `>= 0.75` | Giữ business objective |
| Precision | `>= 0.35` | Không spam quá nhiều |
| Positive rate | `<= 0.45` | Không vượt capacity |
| Segment recall | `>= 0.50` với count đủ lớn | Tránh fail ở nhóm quan trọng |
| Brier score | `new <= old + 0.02` | Probability không mất calibration quá mạnh |

Nếu gate fail, không tự động deploy. Cần error analysis và ghi decision nếu business vẫn muốn override.

## 8. Incident runbook: positive rate tăng bất thường

Khi predicted positive rate tăng từ 10% lên 40%:

1. Kiểm tra deploy log: model version, threshold version, feature version có đổi không.
2. Kiểm tra traffic volume và request schema.
3. So sánh feature distribution trước/sau thời điểm tăng.
4. Kiểm tra category unknown và missing rate.
5. Chạy lại inference trên một sample cũ bằng artifact mới và artifact cũ.
6. Kiểm tra upstream pipeline, timezone, cutoff window.
7. Nếu nghiêm trọng, rollback threshold hoặc model trước, phân tích sau.
8. Khi delayed labels về, so sánh actual positive rate để phân biệt real shift và pipeline bug.

## 9. Review findings thường gặp trong bài Day 7

- Bài học chỉ nói metric tổng nhưng thiếu segment analysis.
- Có threshold tuning nhưng chọn theo test set.
- Có calibration nhưng không giải thích khi nào cần.
- Code fit preprocessing trước split, gây leakage.
- Chỉ save model, không save threshold và feature contract.
- Không có baseline regression test.
- Không có câu trả lời rõ ràng về production readiness.

## 10. Nguồn Đã Xác Minh Bằng Context7

Đối chiếu ngày 8/6/2026 với tài liệu scikit-learn stable:

- [Decision threshold tuning](https://scikit-learn.org/stable/modules/classification_threshold.html)
- [`TunedThresholdClassifierCV`](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TunedThresholdClassifierCV.html)
- [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [`CalibratedClassifierCV`](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html)
- [Common pitfalls và data leakage](https://scikit-learn.org/stable/common_pitfalls.html)
- [Model persistence và security](https://scikit-learn.org/stable/model_persistence.html)

`joblib`, `pickle` và `cloudpickle` có thể thực thi code khi load artifact độc hại. Chỉ load file từ nguồn tin cậy, pin dependency version và test artifact khi nâng scikit-learn.
