# Day 7 Exercise: Error Analysis và Threshold Tuning

## Mục tiêu thực hành

Bạn sẽ chạy một workflow gần production cho churn classification:

- Sinh synthetic churn-like dataset có numerical và categorical features.
- Train scikit-learn `Pipeline` với `ColumnTransformer`.
- Dùng `OneHotEncoder(handle_unknown="ignore")` để tránh crash khi gặp category mới.
- Fit calibration bằng `CalibratedClassifierCV`.
- Sweep threshold từ `0.30` đến `0.80`.
- Tạo confusion matrix, precision, recall, F1, ROC-AUC, PR-AUC.
- Chọn threshold theo business constraint.
- Slice metrics theo segment.
- Xuất top false positives, false negatives và near-threshold samples.
- Demo data leakage bằng một leaky feature.
- Tạo metadata cho model artifact và threshold version.

## Cách chạy

Từ root repo:

```bash
python3 lessions/day-07-error-analysis-data-leakage-threshold-tuning/exercise.py
```

Nếu muốn ghi artifact mẫu vào folder bài học:

```bash
python3 lessions/day-07-error-analysis-data-leakage-threshold-tuning/exercise.py --write-artifacts
```

Nếu muốn biến baseline gates thành lỗi CI:

```bash
python3 lessions/day-07-error-analysis-data-leakage-threshold-tuning/exercise.py --enforce-gates
```

Dependencies:

```bash
pip install numpy pandas scikit-learn joblib
```

## Bài tập bắt buộc

1. Chạy script mặc định và đọc threshold sweep.
2. Trả lời: threshold nào có recall cao nhất? threshold nào có precision cao nhất?
3. Giữ rule `recall >= 0.75`, chọn threshold có expected profit tốt nhất.
4. Đổi rule thành `precision >= 0.50`, xem threshold thay đổi thế nào.
5. Slice thêm theo `region` và `tenure_bucket`, ghi segment nào yếu nhất.
6. Đọc top 20 false positives, ghi 3 pattern có thể giải thích lỗi.
7. Đọc top 20 false negatives, ghi 3 pattern có thể gây mất revenue.
8. So sánh Brier score trước và sau calibration.
9. Chạy leakage demo và giải thích vì sao metric tăng là nguy hiểm.
10. Chạy với `--write-artifacts`, mở metadata JSON và kiểm tra threshold version.

## Bài tập mở rộng

1. Thay Logistic Regression bằng Random Forest hoặc Gradient Boosting.
2. Thêm `payment_method` vào synthetic dataset và slice theo feature này.
3. Chọn threshold theo capacity: mỗi ngày chỉ xử lý tối đa 500 khách.
4. Thêm cost matrix riêng cho từng segment, ví dụ enterprise customer có FN cost cao hơn.
5. Tạo `predict_customer_churn(input_json)` dùng artifact đã ghi.
6. Thêm schema validation bằng Pydantic hoặc Pandera.
7. Thêm time-based split giả lập thay vì random stratified split.
8. Ghi baseline metrics vào JSON và so sánh với run mới.

## Câu hỏi tự kiểm tra

1. Vì sao threshold `0.50` thường không phải default tốt trong production?
2. Data leakage khác train-serving skew như thế nào?
3. Khi nào calibration quan trọng hơn ROC-AUC?
4. Vì sao không nên chọn threshold trên test set?
5. Nếu model có overall F1 tốt nhưng segment `two_year` rất tệ, bạn xử lý thế nào?
6. Nếu predicted positive rate production tăng mạnh, bạn debug theo thứ tự nào?

## Tiêu chí hoàn thành

- [ ] Có bảng threshold từ `0.30` đến `0.80`.
- [ ] Có confusion matrix tại threshold đã chọn.
- [ ] Có top FP/FN.
- [ ] Có slice metrics ít nhất 3 segment.
- [ ] Có leakage demo và giải thích được vì sao không được dùng feature đó.
- [ ] Có threshold metadata gồm model version, threshold version và business objective.
- [ ] Có baseline regression gates.
