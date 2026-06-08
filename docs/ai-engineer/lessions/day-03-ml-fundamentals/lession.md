# Day 3: ML Fundamentals

## Mục tiêu

Sau Day 1, bạn đã biết khi nào nên dùng rule, ML, RAG hoặc LLM. Sau Day 2, bạn đã có trực giác về vector, matrix, gradient và probability. Day 3 nối hai phần đó thành workflow ML thực tế: biến dữ liệu thành một model có thể đánh giá, so sánh và cân nhắc deploy.

Sau bài này, bạn cần làm được:

- Phân biệt supervised, unsupervised và reinforcement learning theo góc nhìn application/system.
- Nhận diện regression, classification, ranking và clustering.
- Thiết kế train/validation/test split không gây data leakage.
- Hiểu cross-validation dùng để làm gì và khi nào không nên dùng.
- Giải thích overfitting, underfitting và bias-variance trade-off bằng ngôn ngữ production.
- Chọn baseline model trước khi thử model phức tạp.
- Trả lời câu hỏi: **Dùng được trong production không? Nếu có thì cần điều kiện gì?**

## TL;DR

Machine Learning là cách xây một function từ data thay vì viết toàn bộ rule bằng tay. Với Senior SE, hãy nhìn model như một dependency có contract xác suất: input giống nhau có thể ổn định, nhưng quality phụ thuộc vào training data, feature, metric, split strategy và distribution ngoài production.

Production ML không bắt đầu bằng model xịn. Nó bắt đầu bằng:

1. Định nghĩa business objective.
2. Chọn metric đúng.
3. Tạo baseline đơn giản.
4. Split data đúng kỷ luật.
5. So sánh model bằng experiment có thể lặp lại.
6. Kiểm tra leakage, latency, drift và fallback trước khi deploy.

## 1. Map ML Về Tư Duy Senior SE

Trong backend truyền thống:

```text
input -> code/rule do engineer viết -> output
```

Trong ML:

```text
historical data + labels + algorithm -> training -> model artifact
new input -> model artifact -> prediction
```

So sánh nhanh:

| Software engineering | Machine learning |
|---|---|
| Code logic | Model parameters học từ data |
| Config | Hyperparameters |
| Unit/integration test | Offline evaluation |
| Staging | Validation/test set |
| Runtime API | Inference service |
| Logging/metrics | Prediction, confidence, drift, latency |
| Regression bug | Quality regression hoặc data drift |

Điểm khác biệt quan trọng: model không đúng/sai tuyệt đối như rule. Model có error rate. Vì vậy release decision phải dựa trên metric, threshold và risk tolerance.

## 2. Các Loại Bài Toán ML

### 2.1. Supervised Learning

Supervised learning dùng data có label:

```text
features -> label
```

Ví dụ:

- Fraud detection: giao dịch có fraud hay không.
- Customer churn prediction: khách hàng có rời bỏ trong 30 ngày tới không.
- Lead scoring: lead có khả năng mua hàng không.
- Ticket classification: ticket thuộc nhóm billing, technical hay account.
- ETA prediction: thời gian giao hàng dự kiến.

Hai nhánh phổ biến:

| Loại | Output | Ví dụ | Metric thường gặp |
|---|---|---|---|
| Regression | Số liên tục | Giá nhà, ETA, doanh thu | MAE, RMSE, R2 |
| Classification | Nhãn rời rạc hoặc probability | Churn, fraud, spam | Precision, recall, F1, ROC-AUC, PR-AUC |

Nếu output là probability, thường vẫn là classification. Ví dụ `P(churn = 1) = 0.82`, sau đó dùng threshold để quyết định action.

### 2.2. Unsupervised Learning

Unsupervised learning không có label rõ ràng. Model tìm structure/pattern trong data:

- Customer segmentation.
- Anomaly detection.
- Topic clustering.
- Embedding visualization.
- Duplicate detection.

Production challenge lớn nhất là evaluation khó hơn supervised learning. Không có label thì không thể chỉ nói “accuracy 95%”. Bạn cần proxy metric, human review, downstream metric hoặc A/B test.

### 2.3. Reinforcement Learning

Reinforcement learning có agent, action, environment và reward:

```text
state -> action -> reward -> policy update
```

Trong production application thông thường, RL ít là lựa chọn đầu tiên vì exploration có thể ảnh hưởng user thật. Trước khi dùng RL, thường cần offline simulation, guardrails, A/B testing hoặc bandit strategy. Với course này, bạn chỉ cần hiểu trực giác để không nhầm RL với supervised learning.

## 3. Cách Nhận Diện Problem Type

Hãy bắt đầu bằng câu hỏi về output và decision cần đưa ra:

| Câu hỏi | Loại bài toán khả dĩ |
|---|---|
| Output là số liên tục? | Regression |
| Output là class rời rạc? | Classification |
| Output là probability của event? | Classification + thresholding |
| Output là danh sách được sắp xếp? | Ranking/recommendation |
| Output là nhóm không có label trước? | Clustering |
| Output là text dài, reasoning hoặc synthesis? | LLM/generation |
| Cần tìm tài liệu liên quan rồi trả lời? | RAG |

Best solution phụ thuộc context. Ví dụ customer support routing có thể dùng rule nếu chỉ có 5 category rõ ràng. Khi ticket đa dạng, rule phình to và khó maintain, supervised classification hợp lý hơn. Nếu user hỏi tự do trên knowledge base, RAG hoặc LLM app mới phù hợp.

## 4. Train, Validation, Test Split

Trong ML, split data là phần tương đương với test discipline trong software. Nếu split sai, metric đẹp nhưng production fail.

```text
train set      -> model học parameters
validation set -> chọn model, tune hyperparameter, tune threshold
test set       -> đánh giá cuối trước release
production     -> dữ liệu thật, có drift và edge cases mới
```

### 4.1. Vai trò từng tập

- **Train set**: dùng để fit model.
- **Validation set**: dùng để chọn model family, hyperparameter, feature set, threshold.
- **Test set**: chỉ dùng ít lần ở cuối để estimate quality trên unseen data.

Nếu bạn dùng test set để tune nhiều lần, test set đã trở thành validation set. Khi đó metric test không còn đáng tin.

### 4.2. Random split

Random split phù hợp khi data độc lập tương đối và không có timeline quan trọng. Ví dụ phân loại ảnh sản phẩm nếu ảnh đã được deduplicate tốt.

Với classification mất cân bằng, nên dùng stratified split để tỷ lệ class giữa train/test gần nhau.

### 4.3. Time-based split

Với bài toán có thời gian, production thường dự đoán tương lai từ quá khứ. Split nên mô phỏng đúng runtime:

```text
train:      tháng 01-03
validation: tháng 04
test:       tháng 05
production: tháng 06 trở đi
```

Ví dụ churn, fraud, demand forecasting, lead scoring, credit risk thường nên cân nhắc time-based split. Random split có thể làm model nhìn thấy pattern tương lai một cách gián tiếp.

### 4.4. Group-based split

Nếu cùng một user/order/session xuất hiện nhiều dòng, phải tránh để cùng group nằm cả train và test. Nếu không, model có thể nhớ đặc điểm user thay vì học pattern tổng quát.

Ví dụ:

- Nhiều transaction của cùng một customer.
- Nhiều event của cùng một device.
- Nhiều review của cùng một product.

## 5. Data Leakage

Data leakage xảy ra khi training/evaluation dùng thông tin mà production không có tại thời điểm dự đoán.

Ví dụ:

- Dự đoán churn hôm nay nhưng feature dùng `cancelled_at`.
- Dự đoán fraud trước khi approve transaction nhưng feature dùng chargeback result sau 30 ngày.
- Scale/impute/feature-select trên toàn bộ dataset trước khi split.
- Duplicate user/session nằm cả train và test.

Checklist audit leakage:

- Feature này có tồn tại tại prediction time không?
- Feature này được tính bằng dữ liệu tương lai không?
- Preprocessing có fit trên test set không?
- Có duplicate hoặc near-duplicate giữa train/test không?
- Label có bị encode gián tiếp trong feature không?

Trong scikit-learn, dùng `Pipeline` giúp giảm leakage vì preprocessing như `StandardScaler` được fit trên train fold trong cross-validation, sau đó mới transform validation/test fold.

## 6. Cross-Validation

Cross-validation chia data thành nhiều fold, train/evaluate nhiều lần rồi lấy mean/std metric.

Ví dụ 5-fold:

```text
run 1: fold 1 test, fold 2-5 train
run 2: fold 2 test, fold 1,3,4,5 train
...
run 5: fold 5 test, fold 1-4 train
```

Nên dùng khi:

- Dataset nhỏ/vừa.
- Cần so sánh model truyền thống.
- Muốn metric ít phụ thuộc vào một lần split.
- Cần phát hiện variance giữa folds.

Không nên lạm dụng khi:

- Dataset rất lớn, training cost cao.
- Bài toán time-series cần split theo thời gian.
- Deep learning/LLM fine-tuning tốn compute.
- Dataset có group leakage nhưng lại dùng K-fold thường.

Trade-off: cross-validation cho estimate ổn định hơn nhưng training time tăng gần tuyến tính theo số fold. 5-fold tức là fit khoảng 5 lần.

## 7. Overfitting, Underfitting, Bias-Variance

### 7.1. Underfitting

Underfitting xảy ra khi model quá đơn giản hoặc feature quá nghèo:

```text
train score thấp
validation score thấp
```

Cách xử lý:

- Thêm feature có signal.
- Dùng model expressive hơn.
- Giảm regularization nếu đang quá mạnh.
- Kiểm tra label noise hoặc problem framing.

### 7.2. Overfitting

Overfitting xảy ra khi model học cả noise/exception của training data:

```text
train score cao
validation score thấp hơn rõ rệt
```

Cách xử lý:

- Thêm data.
- Giảm model complexity.
- Tăng regularization.
- Prune tree, giới hạn depth, giảm số feature.
- Dùng cross-validation.
- Làm error analysis để phân biệt overfit với leakage.

### 7.3. Bias-Variance Trade-off

| Tình huống | Train score | Validation score | Vấn đề | Hướng xử lý |
|---|---:|---:|---|---|
| High bias | Thấp | Thấp | Underfitting | Thêm feature, model mạnh hơn |
| High variance | Cao | Thấp | Overfitting | Regularization, thêm data, giảm complexity |
| Good fit | Tốt vừa | Tốt tương đương | Ổn | Error analysis, threshold tuning |
| Suspicious fit | Gần 100% | Gần 100% | Có thể leakage | Audit feature/split |

Lưu ý: score “quá đẹp” không luôn là tin tốt. Với data thực tế, F1/ROC-AUC gần hoàn hảo thường cần audit leakage trước khi ăn mừng.

## 8. Bảy thuật toán cần biết

Bạn không cần thuộc mọi công thức, nhưng phải hiểu model học kiểu quan hệ nào, cần preprocessing gì và trade-off production nằm ở đâu.

### 8.1. Linear Regression

**Linear Regression** dự đoán một số liên tục bằng tổng có trọng số:

```text
y_hat = w1*x1 + w2*x2 + ... + wn*xn + b
```

Ví dụ: dự đoán ETA, doanh thu hoặc giá. Model học weights sao cho sai số giữa `y_hat` và target nhỏ nhất.

Nên dùng khi cần baseline nhanh, latency thấp và quan hệ gần tuyến tính. Không phù hợp khi pattern phi tuyến hoặc interaction phức tạp chưa được biểu diễn bằng feature.

Production checks: outlier, multicollinearity, feature scale, residual theo segment và data drift.

### 8.2. Logistic Regression

Tên có chữ “Regression” nhưng đây là model **classification**. Model tính linear score rồi dùng sigmoid để tạo score trong `(0, 1)`:

```text
z = w dot x + b
p = sigmoid(z)
```

Nó là baseline mạnh cho tabular data và TF-IDF text:

- Train/inference nhanh.
- Coefficient tương đối dễ giải thích.
- Hỗ trợ regularization.
- Probability thường dễ calibration hơn nhiều model phức tạp, nhưng vẫn phải kiểm tra.

**Regularization** là hình phạt lên parameter quá lớn để giảm overfitting. Trong scikit-learn, `C` nhỏ hơn nghĩa là regularization mạnh hơn cho Logistic Regression.

### 8.3. Decision Tree

**Decision Tree** học các nhánh if/else:

```text
usage_drop > 40%?
  yes -> failed_payment > 0?
           yes -> high churn risk
           no  -> medium risk
  no  -> low risk
```

Tree học nonlinear pattern và interaction mà không cần scale numerical feature. Tree đơn lẻ dễ overfit, đặc biệt khi depth lớn hoặc leaf có quá ít samples.

Nên dùng shallow tree để giải thích hoặc làm baseline rule-like. Cần giới hạn `max_depth`, `min_samples_leaf` và kiểm tra stability qua folds.

### 8.4. Random Forest

**Random Forest** train nhiều decision trees trên các sample/feature subset khác nhau rồi ensemble kết quả. Ensemble nghĩa là kết hợp nhiều model để giảm variance.

Điểm mạnh:

- Hợp tabular nonlinear data.
- Ít tuning hơn boosting.
- Robust hơn một tree đơn.

Trade-off:

- Artifact và inference cost tăng theo số/depth trees.
- Khó giải thích hơn shallow tree/linear model.
- Không phải lựa chọn tốt cho one-hot cực lớn hoặc SLA rất chặt nếu chưa benchmark.

### 8.5. Gradient Boosting và XGBoost

**Boosting** train model theo chuỗi; model sau tập trung sửa lỗi còn lại của ensemble trước. `XGBoost` là một implementation gradient boosting phổ biến; scikit-learn có `GradientBoosting*` và `HistGradientBoosting*`.

Boosting thường rất mạnh trên tabular data, nhưng:

- Hyperparameter tuning dễ overfit validation set.
- Training tuần tự hơn Random Forest.
- Probability vẫn cần calibration nếu dùng cho cost decision.
- Cần ghi version cả library, params và dataset.

Trong exercise dùng `HistGradientBoostingClassifier` để không thêm dependency bên thứ ba. Khi dùng XGBoost thật, phải kiểm tra tài liệu/version riêng thay vì giả định API giống scikit-learn hoàn toàn.

### 8.6. Support Vector Machine

**Support Vector Machine (SVM)** tìm decision boundary có margin lớn giữa các class. Kernel cho phép tạo boundary phi tuyến mà không tự viết feature mapping đầy đủ.

SVM có thể tốt với dataset nhỏ-vừa và feature nhiều chiều, nhưng:

- Kernel SVM scale kém khi số samples lớn.
- Cần scaling.
- Probability không tự nhiên như Logistic Regression và có thể cần calibration.
- Inference cost phụ thuộc số support vectors.

### 8.7. K-Nearest Neighbors

**KNN** dự đoán dựa trên `k` điểm training gần input nhất. Nó gần như không có training cost nhưng chuyển chi phí sang inference.

Trade-off:

- Dễ hiểu, tốt cho baseline nhỏ.
- Cần scaling vì dựa trên distance.
- Naive inference gần tuyến tính theo số training rows.
- Dễ gặp **curse of dimensionality**: khi số chiều cao, distance giữa các điểm kém phân biệt.

Ở scale lớn, thường cần ANN index hoặc model khác thay vì scan toàn bộ training set.

### 8.8. Chọn model theo context

| Context | Nên thử trước | Nâng cấp khi |
|---|---|---|
| Regression baseline | Mean/median + Linear Regression | Residual cho thấy nonlinear pattern |
| Tabular classification | Dummy + Logistic Regression | Baseline chưa đạt quality |
| Tabular nonlinear | Random Forest/HistGradientBoosting | Evidence qua CV và error analysis |
| Text classification | TF-IDF + Logistic Regression/SVM | Semantic/context dài là bottleneck |
| Explainability cao | Linear model/shallow tree | Chỉ khi quality không đủ |
| Latency rất thấp | Linear model/tree nhỏ | Benchmark chứng minh cần model khác |
| Dataset nhỏ | Simple model + CV | Chưa nên tăng complexity sớm |

## 9. Baseline-First Mindset

Baseline là mốc tối thiểu để biết model có tạo giá trị không.

Baseline phổ biến:

- Classification mất cân bằng: predict majority class hoặc `DummyClassifier`.
- Regression: predict mean/median.
- Tabular classification: Logistic Regression.
- Tabular data non-linear: Random Forest hoặc Gradient Boosting.
- Text classification: TF-IDF + Logistic Regression.
- Retrieval/RAG: BM25 trước embedding/reranking.

Rule production:

```text
Không deploy model nếu chưa vượt baseline theo metric gắn với business objective.
```

Ví dụ fraud detection có 1% fraud. Accuracy 99% có thể chỉ là model luôn predict “not fraud”. Baseline này vô dụng về business nếu recall fraud bằng 0.

## 10. Metric Phải Gắn Với Business

Không có metric đúng cho mọi bài toán.

| Bài toán | Sai lầm đắt hơn | Metric nên ưu tiên |
|---|---|---|
| Fraud detection | Bỏ sót fraud | Recall, PR-AUC, cost-weighted metric |
| Spam detection | Chặn nhầm email tốt | Precision cho class spam |
| Churn campaign | Gửi offer sai người | Precision/recall theo campaign budget |
| Medical screening | Bỏ sót ca bệnh | Recall/sensitivity, calibration |
| Lead scoring | Sales gọi nhầm quá nhiều | Precision@K, lift |

Với class imbalance, hãy xem metric theo precision-recall curve. scikit-learn `average_precision_score` tính **Average Precision (AP)** bằng tổng precision có trọng số theo mức tăng recall. AP không phải trapezoidal PR-AUC; khi report, ghi đúng tên metric để tránh so sánh sai. ROC-AUC vẫn hữu ích cho ranking tổng quát, nhưng có thể nhìn quá lạc quan khi positive class rất hiếm.

Threshold là business decision, không chỉ là model decision. Model có thể output probability, còn threshold phụ thuộc cost false positive/false negative, capacity vận hành và risk tolerance.

## 11. Workflow Experiment Gần Production

Một experiment tối thiểu nên có:

1. Problem statement: dự đoán gì, tại thời điểm nào, dùng để quyết định gì.
2. Dataset version hoặc source rõ ràng.
3. Split strategy: random, stratified, time-based hoặc group-based.
4. Baseline: dummy/majority/mean.
5. Candidate models: ít nhất một model đơn giản và một model mạnh hơn.
6. Metrics: business metric + technical metric.
7. Reproducibility: `random_state`, dependency version, params.
8. Latency/fit time: đủ để cân nhắc production.
9. Error analysis: model sai ở nhóm nào.
10. Release decision: deploy, không deploy, hoặc cần thêm data.

## 12. Production Concerns

### Train-serving skew

Training pipeline và inference pipeline phải xử lý feature giống nhau. Nếu notebook encode category một kiểu nhưng service encode kiểu khác, metric offline không còn ý nghĩa.

Giải pháp: đóng gói preprocessing và model trong cùng `Pipeline` hoặc cùng feature pipeline có version.

### Reproducibility

Cần lưu:

- Code version.
- Dataset snapshot.
- Feature definitions.
- Model params/hyperparams.
- Metrics.
- Random seed.
- Artifact version.

### Monitoring

Sau deploy, theo dõi:

- Latency p50/p95/p99.
- Error rate của service.
- Prediction distribution.
- Feature distribution.
- Confidence/probability distribution.
- Business KPI downstream.
- Data drift và concept drift.

### Fallback

Model service cần fallback rõ:

- Nếu model timeout thì dùng rule cũ?
- Nếu feature thiếu thì reject request hay degrade?
- Nếu confidence thấp thì route sang human review?
- Nếu drift mạnh thì rollback model version nào?

## 13. Dùng Được Trong Production Không?

**Có, nhưng không phải chỉ với một notebook và một metric đẹp.**

Day 3 đủ làm nền cho production nếu thỏa các điều kiện:

- Problem framing rõ: model dự đoán gì, tại thời điểm nào, để hỗ trợ decision nào.
- Split strategy mô phỏng đúng production, đặc biệt với time-dependent data.
- Có baseline và model candidate vượt baseline theo metric business.
- Preprocessing nằm trong `Pipeline` hoặc feature pipeline versioned để tránh train-serving skew.
- Test set độc lập, không bị dùng để tune lặp lại.
- Có audit data leakage.
- Có latency/memory estimate cho inference path.
- Có logging, monitoring, rollback và fallback.
- Có quy trình retraining hoặc ít nhất là drift review định kỳ.

Nếu thiếu các điều kiện trên, bài này vẫn dùng tốt cho prototype/offline analysis, nhưng chưa đủ để deploy vào production có user thật.

## 14. Checklist Tự Kiểm

- [ ] Tôi phân biệt được supervised, unsupervised và reinforcement learning.
- [ ] Tôi biết khi nào bài toán là regression, classification, ranking hoặc clustering.
- [ ] Tôi giải thích được vai trò của train, validation và test set.
- [ ] Tôi biết vì sao không tune bằng test set.
- [ ] Tôi nhận diện được data leakage phổ biến.
- [ ] Tôi biết khi nào dùng random split, time split hoặc group split.
- [ ] Tôi hiểu cross-validation đổi compute lấy metric ổn định hơn.
- [ ] Tôi giải thích được overfitting, underfitting và bias-variance.
- [ ] Tôi luôn tạo baseline trước model phức tạp.
- [ ] Tôi giải thích được trade-off của Linear/Logistic Regression, Tree, Random Forest, Boosting, SVM và KNN.
- [ ] Tôi trả lời được điều kiện để dùng model trong production.

## 15. Kết Nối Sang Day 4

Day 4 sẽ đi vào Python ML Stack: NumPy, Pandas, scikit-learn, notebook workflow và cách hiện thực pipeline cơ bản. Day 3 cho bạn “kỷ luật đánh giá”; Day 4 cho bạn công cụ để chạy kỷ luật đó bằng code.

Trước khi sang Day 4, hãy làm [exercise.md](./exercise.md). Bài thực hành sẽ dùng scikit-learn để so sánh baseline, Logistic Regression, Random Forest và HistGradientBoosting với split, metrics và timing rõ ràng.

## Nguồn kỹ thuật đã kiểm tra

- scikit-learn stable docs qua Context7, library ID `/websites/scikit-learn_stable`.
- Đã đối chiếu: `Pipeline`, `train_test_split(stratify=...)`, cross-validation, `LogisticRegression`, `RandomForestClassifier`, `HistGradientBoostingClassifier` và `average_precision_score`.
- AP được định nghĩa khác trapezoidal area dưới precision-recall curve; bài và exercise dùng tên `average_precision`.
