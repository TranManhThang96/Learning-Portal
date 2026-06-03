# Day 3 Document: Algorithms Và Model Selection Reference

Tài liệu này dùng như checklist khi chọn model cho bài toán ML nền tảng. Không cần học công thức sâu ngay hôm nay; mục tiêu là hiểu model nào nên thử trước, trade-off là gì và production concern nằm ở đâu.

## 1. Nguyên tắc Chọn Model

Thứ tự ưu tiên thực tế:

1. Bắt đầu bằng baseline đơn giản.
2. Chọn metric theo business cost.
3. Chọn model đơn giản nhất vượt baseline đủ tốt.
4. Chỉ tăng complexity khi metric hoặc requirement bắt buộc.
5. Tính cả latency, explainability, cost vận hành và khả năng debug.

Không có “best model” tuyệt đối. Best solution phụ thuộc vào data size, feature type, latency budget, explainability, team skill và cost sai lầm.

## 2. Model Cho Regression

### Linear Regression

Ý tưởng: học quan hệ gần tuyến tính giữa features và target.

Nên dùng khi:

- Cần baseline nhanh.
- Cần explainability.
- Feature đã được xử lý tốt.
- Quan hệ giữa input và output tương đối tuyến tính.

Không nên dùng khi:

- Pattern phi tuyến mạnh.
- Có interaction phức tạp.
- Outlier ảnh hưởng lớn nhưng chưa xử lý.

Production note:

- Inference rất nhanh.
- Dễ monitoring vì behavior đơn giản.
- Cần kiểm tra feature scaling, outlier và drift.

### Tree-based Regression

Decision Tree, Random Forest, Gradient Boosting có thể học non-linear pattern tốt hơn linear model.

Trade-off:

- Tốt cho tabular data.
- Ít yêu cầu scaling.
- Dễ overfit nếu tree quá sâu.
- Artifact và latency lớn hơn linear model.

## 3. Model Cho Classification

### DummyClassifier

Baseline không học signal thật, ví dụ luôn predict class phổ biến nhất.

Mục đích:

- Đo xem model thật có vượt “đoán ngu có hệ thống” không.
- Phát hiện metric misleading, đặc biệt khi class imbalance.

Nếu model phức tạp không vượt `DummyClassifier` theo metric business, chưa nên deploy.

### Logistic Regression

Logistic Regression là baseline mạnh cho classification, đặc biệt với tabular feature đã clean hoặc text sparse feature như TF-IDF.

Nên dùng khi:

- Cần baseline nhanh, ổn định.
- Cần probability tương đối dễ calibrate.
- Cần explainability tốt hơn tree ensemble.
- Cần latency thấp.
- Dataset không quá phi tuyến.

Không nên dùng khi:

- Pattern phi tuyến/interactions rất mạnh.
- Feature engineering chưa đủ.
- Boundary giữa classes phức tạp.

Production note:

- Thường là lựa chọn v1 tốt cho API traffic cao.
- Cần scaling cho nhiều trường hợp numerical feature.
- Regularization giúp giảm overfitting.

### Decision Tree

Decision Tree chia data theo rule dạng if/else.

Nên dùng khi:

- Cần giải thích trực quan.
- Muốn hiểu feature split ban đầu.
- Dataset nhỏ/vừa.

Không nên dùng khi:

- Cần generalization mạnh.
- Data noisy.
- Không kiểm soát depth/min samples.

Production note:

- Tree đơn lẻ dễ overfit.
- Shallow tree có thể tốt như rule engine học từ data.

### Random Forest

Random Forest train nhiều decision trees rồi ensemble kết quả.

Nên dùng khi:

- Tabular data có non-linear pattern.
- Muốn model mạnh hơn Logistic Regression nhưng ít tuning hơn boosting.
- Dataset vừa, latency không quá chặt.

Không nên dùng khi:

- Cần inference cực thấp.
- Model artifact size bị giới hạn.
- Cần explainability rất cao.

Production note:

- Cost tăng theo `n_estimators * depth`.
- Set `random_state` để reproducible.
- Có thể dùng `n_jobs=-1` khi training offline, nhưng cần kiểm soát tài nguyên CI/job runner.

### Gradient Boosting, HistGradientBoosting, XGBoost, LightGBM

Boosting train model theo chuỗi, model sau sửa lỗi model trước. Với tabular data, boosting thường rất mạnh.

Nên dùng khi:

- Cần quality cao trên tabular data.
- Có đủ discipline về validation.
- Có thời gian tune hyperparameters.

Không nên dùng khi:

- Team chưa có baseline/evaluation rõ.
- Data ít và noisy.
- Latency hoặc complexity vận hành không phù hợp.

Production note:

- Dễ overfit nếu tune theo validation quá nhiều.
- Cần version params và dataset.
- Nên theo dõi calibration nếu output probability dùng cho decision cost-sensitive.

### SVM

SVM hữu ích cho dataset nhỏ/vừa, đặc biệt với high-dimensional sparse features.

Trade-off:

- Có thể mạnh với text sparse feature.
- Kernel SVM scale kém với data lớn.
- Probability output không tự nhiên bằng Logistic Regression.

### KNN

KNN dự đoán dựa trên các điểm gần nhất.

Nên dùng khi:

- Prototype similarity.
- Dataset nhỏ.
- Muốn baseline trực giác.

Không nên dùng khi:

- Realtime inference trên dataset lớn.
- Feature dimension cao mà không có index tốt.

Production note:

- Naive inference gần O(n) theo số training samples.
- Ở scale lớn nên chuyển sang ANN/vector index hoặc model khác.

## 4. Model Selection Theo Context

| Context | Nên thử trước | Vì sao |
|---|---|---|
| Tabular classification v1 | DummyClassifier + Logistic Regression | Baseline rõ, nhanh, dễ debug |
| Tabular non-linear | Random Forest hoặc HistGradientBoosting | Mạnh hơn linear, hợp tabular |
| Text classification ngắn | TF-IDF + Logistic Regression | Baseline mạnh trước Transformer |
| Fraud/churn mất cân bằng | Logistic Regression/boosting + PR-AUC/recall | Accuracy dễ đánh lừa |
| Latency cực thấp | Logistic Regression | Inference nhẹ |
| Explainability cao | Logistic Regression, shallow tree | Dễ giải thích hơn ensemble lớn |
| Data rất ít | Rule hoặc simple model | Model phức tạp dễ overfit |
| Language generation | LLM | ML classifier không sinh text tự do |
| Search tài liệu nội bộ | BM25/RAG | Classification không giải quyết retrieval |

## 5. Split Strategy Reference

| Tình huống | Split nên dùng | Lý do |
|---|---|---|
| Data IID tương đối | Random split + stratify nếu classification | Đơn giản, nhanh |
| Class imbalance | Stratified split | Giữ tỷ lệ class |
| Dữ liệu có timeline | Time-based split | Mô phỏng production |
| Nhiều dòng cùng user/session | Group split | Tránh cùng entity vào train và test |
| Dataset nhỏ | Cross-validation | Metric ổn định hơn |
| Training rất đắt | Holdout validation | Giảm compute |

## 6. Metric Reference

### Classification

| Metric | Ý nghĩa | Khi dùng |
|---|---|---|
| Accuracy | Tỷ lệ dự đoán đúng | Class cân bằng, cost sai lầm gần nhau |
| Precision | Trong các positive prediction, bao nhiêu đúng | False positive đắt |
| Recall | Trong actual positive, bắt được bao nhiêu | False negative đắt |
| F1 | Trung hòa precision và recall | Cần cân bằng hai phía |
| ROC-AUC | Khả năng rank positive cao hơn negative | Binary classification tổng quát |
| PR-AUC | Precision/recall trên nhiều threshold | Class imbalance |
| Log loss | Phạt probability sai/confident | Cần probability quality |

### Regression

| Metric | Ý nghĩa | Khi dùng |
|---|---|---|
| MAE | Sai số tuyệt đối trung bình | Dễ hiểu, ít nhạy outlier hơn RMSE |
| RMSE | Phạt lỗi lớn mạnh hơn | Lỗi lớn rất đắt |
| R2 | Tỷ lệ variance được giải thích | So sánh nhanh, không đủ một mình |

## 7. Production Checklist Cho Model Selection

- Baseline là gì và score bao nhiêu?
- Candidate model vượt baseline theo metric nào?
- Metric đó có gắn với business cost không?
- Split có phản ánh production data flow không?
- Có data leakage không?
- Model artifact size bao nhiêu?
- Inference latency p95/p99 dự kiến bao nhiêu?
- Feature computation có đắt hơn model inference không?
- Có fallback khi model timeout/confidence thấp không?
- Có monitoring prediction distribution và drift không?
- Có plan retraining hoặc rollback không?

## 8. Anti-patterns

- Chọn model vì “nghe mạnh” trước khi có baseline.
- Dùng accuracy cho fraud/churn imbalance rồi kết luận model tốt.
- Scale/encode/feature-select trước khi split.
- Tune test set nhiều lần.
- Random split cho bài toán theo thời gian.
- Deploy notebook logic khác với inference service.
- Không lưu dataset/code/model version.
- Không đo latency trước khi đưa vào API.

## 9. Kết Luận

Trong giai đoạn đầu của một AI Engineer, kỹ năng quan trọng không phải nhớ mọi thuật toán. Kỹ năng quan trọng là chọn được model đủ đơn giản, đánh giá đúng, tránh leakage và biết khi nào complexity tạo giá trị thật. Model tốt nhất trong production thường là model đơn giản nhất đạt yêu cầu business với chi phí vận hành chấp nhận được.
