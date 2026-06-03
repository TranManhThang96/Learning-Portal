# Review And Fixed Checklist

Ngày tổng hợp: 2026-05-09

Phạm vi: review và sửa 5 bài đầu của Phase 1 - ML Foundation theo `review-and-fixed-task.md`.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách bài học hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 1, Day 2, Day 3, Day 4, Day 5.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã tổng hợp kết quả và tạo file checklist này.

## 2. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 01-05 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Đúng theo yêu cầu chính tả của task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập riêng. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-01...md` đến `lessions/day-05...md` đã thành trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu. |
| Giữ thuật ngữ chuyên ngành bằng English | Done | Ví dụ: `Pipeline`, `ColumnTransformer`, `embedding`, `inference`, `baseline`, `RAG`, `LLM`. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có TL;DR, concept, workflow, checklist hoặc reference. |
| Ưu tiên thực hành | Done | Mỗi bài có `exercise.md` riêng. |
| Có trade-off theo context | Done | Có bảng hoặc mục trade-off trong từng bài. |
| Có best solution theo context | Done | Day 1 có decision framework; Day 3-5 có model/pipeline selection guidance. |
| Có performance concern | Done | Có latency, capacity, memory, throughput, vector scan, feature explosion hoặc cost notes tùy bài. |
| Code example gần production | Done | Có validation, pipeline reuse, artifact, metadata, threshold/cost logic, fallback dataset hoặc schema checks. |
| Trả lời câu hỏi production | Done | Mỗi bài có mục trả lời "Dùng được trong production không? Nếu có thì cần điều kiện gì?" |
| Context7 khi dùng library docs | Done | Đã dùng Context7 cho NumPy, pandas và scikit-learn. |

## 3. Kết Quả Theo Bài

### Day 1: AI Mindset cho Senior SE

Files:

- `lessions/day-01-ai-mindset-cho-senior-se/lession.md`
- `lessions/day-01-ai-mindset-cho-senior-se/document.md`
- `lessions/day-01-ai-mindset-cho-senior-se/exercise.md`
- `lessions/day-01-ai-mindset-cho-senior-se.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu.
- Nội dung đúng hướng nhưng chưa đủ sâu cho production decision.
- Thiếu framework ra quyết định rule-based vs ML vs Deep Learning vs LLM vs RAG.
- Chưa tách document/exercise.

Đã sửa:

- Viết lại có dấu và tách thành 3 file.
- Bổ sung decision framework cho 5 bài toán: fraud detection, churn prediction, chatbot CSKH, search tài liệu nội bộ, recommendation sản phẩm.
- Bổ sung production architecture, logging fields, fallback/rollback, security/privacy/compliance.
- Bổ sung exercise template bắt buộc và answer mẫu.

### Day 2: Math đủ dùng cho ML

Files:

- `lessions/day-02-math-du-dung-cho-ml/lession.md`
- `lessions/day-02-math-du-dung-cho-ml/document.md`
- `lessions/day-02-math-du-dung-cho-ml/exercise.md`
- `lessions/day-02-math-du-dung-cho-ml.md`

Review findings:

- Bài cũ chưa có dấu và chưa đủ step by step.
- Code còn thiên toy example.
- Thiếu validation, numerical stability, batch/vectorized path.
- Production concern về embedding search và risk scoring chưa đủ rõ.

Đã sửa:

- Bổ sung vector, matrix, tensor, dot product, cosine similarity, gradient descent, probability, expected value, entropy, Bayes.
- Thêm ví dụ gần production cho embedding search và risk scoring.
- Thêm code NumPy có shape validation, finite check, zero-vector guard, dtype rõ ràng, vectorized top-k cosine và stable sigmoid.
- Bổ sung trade-off dot vs cosine, loop vs vectorized, float32 vs float64, full scan vs ANN.

Context7 đã dùng:

- `/numpy/numpy`

### Day 3: ML Fundamentals

Files:

- `lessions/day-03-ml-fundamentals/lession.md`
- `lessions/day-03-ml-fundamentals/document.md`
- `lessions/day-03-ml-fundamentals/exercise.md`
- `lessions/day-03-ml-fundamentals.md`

Review findings:

- Bài cũ chưa có dấu.
- Thiếu nối logic với Day 1-2.
- Thiếu data leakage checklist, split discipline và baseline rõ ràng.
- Code chưa nhấn mạnh `DummyClassifier`, threshold/business metrics và reproducibility.

Đã sửa:

- Bổ sung supervised/unsupervised/reinforcement learning theo góc nhìn application/system.
- Bổ sung random split, time-based split, group-based split, cross-validation và trade-off compute.
- Bổ sung baseline-first mindset, data leakage, train-serving skew, fallback và monitoring.
- Exercise dùng `Pipeline`, `DummyClassifier`, Logistic Regression, Random Forest, HistGradientBoosting, metrics và timing.
- Main agent đã chỉnh setup command trong exercise từ `python` sang `python3` để nhất quán với môi trường hiện tại.

Context7 đã dùng:

- `/websites/scikit-learn_stable`

### Day 4: Python ML Stack

Files:

- `lessions/day-04-python-ml-stack/lession.md`
- `lessions/day-04-python-ml-stack/document.md`
- `lessions/day-04-python-ml-stack/exercise.md`
- `lessions/day-04-python-ml-stack.md`

Review findings:

- Bài cũ còn tiếng Việt không dấu và chưa đủ chi tiết.
- Chưa tách lesson/document/exercise.
- Notebook-to-production workflow chưa rõ.
- Code example thiếu schema validation, artifact metadata, inference contract và security notes.

Đã sửa:

- Bổ sung NumPy `ndarray`, `shape`, `dtype`, broadcasting, vectorization, view/copy.
- Bổ sung Pandas EDA/data wrangling như batch ETL, missing values, `groupby`, `merge`, memory concern.
- Bổ sung scikit-learn `Pipeline`, `ColumnTransformer`, `OneHotEncoder(handle_unknown="ignore")`, split và metrics.
- Exercise có fallback synthetic dataset, schema validation, derived features, 3 models, metrics, latency, `model.joblib`, `metadata.json`, sample inference.
- Bổ sung security note cho `joblib`/pickle artifact.

Context7 đã dùng:

- `/numpy/numpy`
- `/websites/pandas_pydata`
- `/websites/scikit-learn_stable`

### Day 5: Feature Engineering

Files:

- `lessions/day-05-feature-engineering/lession.md`
- `lessions/day-05-feature-engineering/document.md`
- `lessions/day-05-feature-engineering/exercise.md`
- `lessions/day-05-feature-engineering.md`

Review findings:

- Bài cũ đúng chủ đề nhưng còn không dấu và chưa đủ sâu.
- Thiếu point-in-time correctness, leakage checks, schema validation và pipeline reuse rõ ràng.
- Production answer chưa nêu đủ điều kiện vận hành.

Đã sửa:

- Bổ sung feature engineering cho numerical, categorical, text, datetime, missing data và feature selection.
- Bổ sung point-in-time correctness, schema drift, missing spike, PII, artifact versioning và monitoring.
- Exercise có `ColumnTransformer`, `Pipeline`, `SimpleImputer`, `OneHotEncoder`, `TfidfVectorizer`, `LogisticRegression`, validation và persistence.
- Bổ sung decision matrix và checklist riêng trong `document.md`.

Context7 đã dùng:

- `/websites/scikit-learn_stable`
- `/websites/pandas_pydata`

## 4. Verification

Đã chạy các kiểm tra sau:

- `rtk git status --short`
- `rtk wc -l` cho 15 file mới của Day 01-05.
- `rtk rg` để kiểm tra các heading, mục production, trade-off, Context7 và các API chính.
- `rtk python3 --version`
- `rtk python3 -c 'import numpy, pandas, sklearn, joblib; ...'`
- `rtk proxy git diff --check -- ...` cho các file Day 01-05 và checklist.

Kết quả:

- Cấu trúc folder/file đạt yêu cầu.
- Các section production/trade-off xuất hiện trong từng bài.
- Targeted whitespace check cho file đã sửa trong phạm vi task pass.
- `python3` có sẵn: Python 3.12.3.
- Chưa thể chạy full exercise vì môi trường hiện tại thiếu dependency Python ML, bắt đầu từ `numpy`.

## 5. Rủi Ro Còn Lại

- Chưa chạy end-to-end toàn bộ code trong `exercise.md` vì chưa cài `numpy`, `pandas`, `scikit-learn`, `joblib`.
- Repo không thấy tooling markdown lint rõ ràng, nên chưa chạy markdown lint.
- File tổng hợp cũ `ai_engineer_day_01_08_lessons.md` chưa được rewrite để tránh ảnh hưởng Day 06-08 ngoài phạm vi task; các file phẳng riêng của Day 01-05 đã được chuyển thành trang điều hướng về folder mới.
- Worktree trước khi làm đã có thay đổi ngoài phạm vi ở `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, `../generate-process.md` và `review-and-fixed-task.md`; main/subagents không revert các thay đổi đó.
- Global `git diff --check` vẫn fail ở `../generate-process.md:4` do trailing whitespace ngoài phạm vi task.

## 6. Kết Luận

Day 01-05 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code gần production và câu trả lời production readiness cho từng bài.

---

# Review And Fixed Checklist - Day 06 Đến Day 10

Ngày tổng hợp: 2026-05-09

Phạm vi: review và sửa 5 bài học từ Day 06 đến Day 10 theo `review-and-fixed-task.md`.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách bài học hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 6, Day 7, Day 8, Day 9, Day 10.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã tự kiểm tra cấu trúc, heading, keyword bắt buộc, code syntax và whitespace trong phạm vi Day 06-10.
- [x] Main agent đã tổng hợp kết quả và cập nhật checklist này.

## 2. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 06-10 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo/checklist riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập riêng; Day 7 và Day 9 có thêm script `.py`. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-06...md` đến `lessions/day-10...md` đã thành trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu. |
| Giữ thuật ngữ chuyên ngành bằng English | Done | Ví dụ: `Pipeline`, `ColumnTransformer`, `ROC-AUC`, `PR-AUC`, `backpropagation`, `Tensor`, `DataLoader`. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có TL;DR, workflow, decision matrix, checklist hoặc document tra cứu. |
| Ưu tiên thực hành | Done | Mỗi bài có exercise gần production hoặc script chạy được khi đủ dependency. |
| Có trade-off theo context | Done | Có trade-off metric, threshold, model, NumPy vs PyTorch, CPU/GPU, latency/cost. |
| Có best solution theo context | Done | Mỗi bài đều nêu hướng chọn tốt nhất theo tình huống học/production. |
| Có performance concern | Done | Có latency p95/p99, memory, capacity, alert volume, vectorization, dtype, CPU/GPU và artifact size. |
| Code example gần production | Done | Có validation, schema/shape checks, pipeline, artifact metadata, threshold versioning, checkpoint hoặc logging. |
| Trả lời câu hỏi production | Done | Mỗi bài có mục trả lời "Dùng được trong production không? Nếu có thì cần điều kiện gì?" |
| Context7 khi dùng library docs | Done | Đã dùng Context7 cho scikit-learn, NumPy và PyTorch. |

## 3. Kết Quả Theo Bài

### Day 6: Model Evaluation Metrics

Files:

- `lessions/day-06-model-evaluation-metrics/lession.md`
- `lessions/day-06-model-evaluation-metrics/document.md`
- `lessions/day-06-model-evaluation-metrics/exercise.md`
- `lessions/day-06-model-evaluation-metrics.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu.
- Nội dung đúng hướng nhưng thiếu chiều sâu về cost/capacity, ranking metrics và production reporting.
- Chưa tách document/exercise.

Đã sửa:

- Viết lại có dấu và tách thành 3 file.
- Bổ sung accuracy, precision, recall, F1, ROC-AUC, PR-AUC/average precision, confusion matrix, MAE/MSE/RMSE/MAPE, MRR/NDCG/Recall@k.
- Bổ sung fraud case study, business metric vs ML metric, decision matrix và production readiness checklist.
- Exercise dùng synthetic imbalanced fraud dataset, `Pipeline`, `ColumnTransformer`, `OneHotEncoder(handle_unknown="ignore")`, threshold sweep, expected value và capacity reasoning.

Context7 đã dùng:

- `/websites/scikit-learn_stable`

### Day 7: Error Analysis, Data Leakage, Threshold Tuning

Files:

- `lessions/day-07-error-analysis-data-leakage-threshold-tuning/lession.md`
- `lessions/day-07-error-analysis-data-leakage-threshold-tuning/document.md`
- `lessions/day-07-error-analysis-data-leakage-threshold-tuning/exercise.md`
- `lessions/day-07-error-analysis-data-leakage-threshold-tuning/exercise.py`
- `lessions/day-07-error-analysis-data-leakage-threshold-tuning.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu và còn mỏng.
- Thiếu checklist vận hành, regression gate, threshold artifact và ví dụ đủ gần production.

Đã sửa:

- Viết lại có dấu và tách folder.
- Bổ sung error slicing, confusion matrix analysis, top false positives/false negatives, threshold tuning `0.30`-`0.80`, calibration, data leakage, train-serving skew, distribution shift và baseline regression test.
- Thêm `exercise.py` dùng `Pipeline`, `ColumnTransformer`, `OneHotEncoder(handle_unknown="ignore")`, `CalibratedClassifierCV`, threshold sweep, slice metrics, leakage demo, shift report và artifact metadata.

Context7 đã dùng:

- `/websites/scikit-learn_stable`

### Day 8: Mini-project - Customer Churn ML Pipeline

Files:

- `lessions/day-08-customer-churn-ml-pipeline/lession.md`
- `lessions/day-08-customer-churn-ml-pipeline/document.md`
- `lessions/day-08-customer-churn-ml-pipeline/exercise.md`
- `lessions/day-08-customer-churn-ml-pipeline.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu.
- Nội dung đã đúng hướng nhưng thiếu project contract, artifact metadata, inference contract, README/model-card guidance và production readiness đủ chặt.

Đã sửa:

- Viết lại thành mini-project step by step.
- Bao phủ Telco Customer Churn hoặc synthetic fallback, EDA, feature engineering, ít nhất 3 models, multiple metrics, error analysis, save model và inference function.
- Exercise có schema validation, `Pipeline`, `ColumnTransformer`, `OneHotEncoder(handle_unknown="ignore")`, Logistic Regression, Random Forest, Gradient Boosting, threshold tuning, latency measurement và artifact metadata.
- Bổ sung README template, artifact contract, monitoring checklist và decision matrix.

Context7 đã dùng:

- `/websites/scikit-learn_stable`

### Day 9: Neural Network từ Zero

Files:

- `lessions/day-09-neural-network-tu-zero/lession.md`
- `lessions/day-09-neural-network-tu-zero/document.md`
- `lessions/day-09-neural-network-tu-zero/exercise.md`
- `lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py`
- `lessions/day-09-neural-network-tu-zero.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu và hơi compact.
- Thiếu giải thích step by step về shape contract, backpropagation, gradient descent, numerical stability và production answer.

Đã sửa:

- Viết lại có dấu và tách folder.
- Bổ sung neuron, weighted sum + activation, Sigmoid/Tanh/ReLU/GELU, forward pass, BCE loss, backpropagation, gradient descent và XOR dataset.
- Thêm script NumPy vectorized dùng `@`, `np.random.default_rng`, seed, dtype option, shape checks, clipping số học, logging và optional matplotlib.
- Nêu rõ code NumPy tự viết phù hợp để học; production training nên dùng framework autograd như PyTorch.

Context7 đã dùng:

- `/numpy/numpy`

### Day 10: PyTorch Fundamentals

Files:

- `lessions/day-10-pytorch-fundamentals/lession.md`
- `lessions/day-10-pytorch-fundamentals/document.md`
- `lessions/day-10-pytorch-fundamentals/exercise.md`
- `lessions/day-10-pytorch-fundamentals.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu và chưa đủ sâu.
- Thiếu giải thích chi tiết Tensor, dtype/shape/device, autograd, `nn.Module`, `Dataset`, `DataLoader`, CPU/GPU device management và production readiness.

Đã sửa:

- Viết lại có dấu và tách folder.
- Bổ sung Tensor, autograd, `nn.Module`, `forward()`, `Dataset`, `DataLoader`, CPU/GPU device management, `state_dict`, train/eval mode và inference mode.
- Exercise rebuild MLP XOR từ Day 9 bằng PyTorch, dùng `BCEWithLogitsLoss`, `optimizer.zero_grad(set_to_none=True)`, `model.train()`, `model.eval()`, `torch.inference_mode()`, checkpoint và device fallback.
- Bổ sung so sánh NumPy vs PyTorch, performance trade-off và checklist production.

Context7 đã dùng:

- `/pytorch/pytorch`

## 4. Verification

Đã chạy các kiểm tra sau:

- `rtk git status --short`
- `rtk find` và `rtk wc -l` cho file/folder Day 06-10.
- `rtk rg` để kiểm tra heading, production section, trade-off, keyword bắt buộc và API chính.
- `rtk python3 -m py_compile` cho:
  - `lessions/day-07-error-analysis-data-leakage-threshold-tuning/exercise.py`
  - `lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py`
- `rtk python3 -m py_compile` cho code block chính được trích từ:
  - `lessions/day-06-model-evaluation-metrics/exercise.md`
  - `lessions/day-08-customer-churn-ml-pipeline/exercise.md`
  - `lessions/day-10-pytorch-fundamentals/exercise.md`
- `rtk git diff --check -- ...` cho toàn bộ phạm vi Day 06-10.
- `rtk python3 -c` kiểm tra dependency local: `numpy`, `pandas`, `sklearn`, `joblib`, `torch`, `matplotlib`.

Kết quả:

- Cấu trúc folder/file đạt yêu cầu.
- Các section production/trade-off/best solution xuất hiện trong từng bài.
- Targeted whitespace check cho file đã sửa trong phạm vi Day 06-10 pass.
- Script Python và code block chính compile được về mặt cú pháp.
- Môi trường hiện tại chưa có dependency ML/DL: `numpy`, `pandas`, `sklearn`, `joblib`, `torch`, `matplotlib`.

## 5. Rủi Ro Còn Lại

- Chưa chạy end-to-end toàn bộ exercise Day 06-08 vì thiếu `numpy`, `pandas`, `scikit-learn`, `joblib`.
- Chưa chạy exercise Day 10 vì thiếu `torch`.
- Optional plotting path của Day 9 chưa runtime-verified vì thiếu `matplotlib`.
- Day 8 chưa kiểm thử với Telco CSV thật trong repo vì dataset không có sẵn; bài đã có synthetic fallback và hướng dẫn dùng CSV thật.
- Worktree trước khi làm đã có thay đổi ngoài phạm vi ở Day 01-05, `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, `../generate-process.md`, `review-and-fixed-task.md`; main/subagents không revert các thay đổi đó.

## 6. Kết Luận

Day 06-10 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code gần production và câu trả lời production readiness cho từng bài.

---

# Review And Fixed Checklist - Day 11 Đến Day 15

Ngày tổng hợp: 2026-05-10 (Asia/Ho_Chi_Minh)

Phạm vi: review và sửa 5 bài học từ Day 11 đến Day 15 theo `review-and-fixed-task.md`.

## 1. Mục Tiêu Và Deliverable Cần Đạt

Objective cụ thể:

- Review và sửa 5 bài AI từ Day 11 đến Day 15.
- Chuyển nội dung tiếng Việt không dấu thành tiếng Việt có dấu, giữ thuật ngữ chuyên ngành bằng English.
- Làm nội dung đầy đủ hơn, chi tiết hơn, step by step để người học ít phải tra cứu thêm.
- Mỗi bài có folder riêng, trong folder có ít nhất `lession.md`; có `document.md` và `exercise.md` khi cần.
- Mỗi bài phải có thực hành, trade-off, performance concern, best solution theo context và câu trả lời: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"
- Main agent phải đọc plan khóa học, chia thành 5 bài, spawn 5 subagents song song, chờ đủ kết quả, sau đó chỉ main agent cập nhật `review-and-fixed-checklist.md`.

## 2. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách bài học hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 11, Day 12, Day 13, Day 14, Day 15.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã tự kiểm tra cấu trúc, keyword bắt buộc, section production/trade-off, syntax script và whitespace trong phạm vi Day 11-15.
- [x] Main agent đã tổng hợp kết quả và cập nhật checklist này.

## 3. Prompt-to-Artifact Audit

| Yêu cầu explicit | Evidence trong repo | Kết quả |
|---|---|---|
| Đọc plan khóa học trước | Đã đọc `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, phần Phase 2 Day 11-15 | Done |
| Main agent đọc danh sách file | Đã chạy `rtk find`/`rtk rg --files` cho `lessions/` và các folder Day 11-15 | Done |
| Chia thành 5 bài | Day 11, Day 12, Day 13, Day 14, Day 15 được giao riêng cho 5 worker | Done |
| Spawn 5 subagents song song | 5 worker đã xử lý song song: Day 11-15 | Done |
| Subagents review rồi sửa | Mỗi worker trả về review findings, files changed, Context7 IDs, verification và rủi ro còn lại | Done |
| Main agent chờ đủ 5 kết quả | Đã nhận kết quả đủ Day 11, 12, 13, 14, 15 | Done |
| Chỉ main agent cập nhật checklist tổng | `review-and-fixed-checklist.md` được cập nhật ở bước tổng hợp này | Done |
| Tiếng Việt có dấu | Main agent kiểm tra không còn heading/mẫu cũ kiểu `Muc Tieu`, `Dung duoc`, `Tai lieu`, `Bai tap` trong Day 11-15 | Done |
| Giữ thuật ngữ chuyên ngành bằng English | Các bài giữ `DataLoader`, `AdamW`, `BPE`, `WordPiece`, `SentencePiece`, `Query`, `Key`, `Value`, `RoPE`, `KV cache`, `Trainer`, `pipeline` | Done |
| Mỗi bài có folder riêng | Có folder `lessions/day-11.../` đến `lessions/day-15.../` | Done |
| Mỗi folder có `lession.md` | Có đủ 5 file `lession.md` | Done |
| Có `document.md` | Có đủ 5 file `document.md` | Done |
| Có `exercise.md` | Có đủ 5 file `exercise.md` | Done |
| File phẳng cũ không còn là bài dài | `lessions/day-11...md` đến `day-15...md` đã là trang điều hướng | Done |
| Dễ hiểu từ cơ bản đến chi tiết | Mỗi `lession.md` có TL;DR, mental model, flow hoặc roadmap; `document.md` đi sâu hơn | Done |
| Ưu tiên thực hành | Mỗi bài có `exercise.md`; Day 11 và Day 13 có script Python riêng | Done |
| Trade-off, best solution, performance | Main agent kiểm tra `rg` thấy các section/keyword này trong từng bài | Done |
| Code gần production | Day 11 có training job PyTorch; Day 12 có tokenizer wrapper; Day 13 có attention module; Day 15 có inference wrapper/template | Done |
| Production readiness answer | Mỗi bài có câu trả lời hoặc bài tập trực tiếp về "Dùng được trong production không?" | Done |
| Context7 khi dùng library docs | Worker dùng Context7 cho PyTorch, Hugging Face Transformers/Tokenizers/Datasets/Accelerate khi có API cụ thể | Done |

## 4. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 11-15 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tra cứu/checklist riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập riêng. |
| Có script thực hành khi cần | Done | Day 11 có `day11_training_loop.py`, Day 13 có `attention_demo.py`. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-11...md` đến `lessions/day-15...md` là trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu. |
| Giữ thuật ngữ chuyên ngành bằng English | Done | Ví dụ: `DataLoader`, `AdamW`, `BPE`, `WordPiece`, `RoPE`, `KV cache`, `Trainer`. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có TL;DR, mental model, flow, checklist hoặc reference. |
| Ưu tiên thực hành | Done | Mỗi bài có exercise; Day 11/13 có script runnable khi đủ dependency. |
| Có trade-off theo context | Done | Có trade-off optimizer/scheduler, tokenizer, attention, architecture và Hugging Face ecosystem. |
| Có best solution theo context | Done | Có guidance chọn optimizer, tokenizer policy, attention implementation, architecture và Hugging Face API level. |
| Có performance concern | Done | Có batch size, `num_workers`, token length/cost, attention `O(n^2)`, KV cache, latency, memory/VRAM. |
| Code example gần production | Done | Có seed/config, validation, wrapper, shape checks, mask checks, checkpoint, logging, model card/license checks. |
| Trả lời production readiness | Done | Mỗi bài có mục hoặc bài tập trả lời điều kiện production. |
| Context7 khi dùng library docs | Done | Đã dùng Context7 cho PyTorch và Hugging Face-related libraries. |

## 5. Kết Quả Theo Bài

### Day 11: Training Loop, Optimizer, Scheduler

Files:

- `lessions/day-11-training-loop-optimizer-scheduler/lession.md`
- `lessions/day-11-training-loop-optimizer-scheduler/document.md`
- `lessions/day-11-training-loop-optimizer-scheduler/exercise.md`
- `lessions/day-11-training-loop-optimizer-scheduler/day11_training_loop.py`
- `lessions/day-11-training-loop-optimizer-scheduler.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu, nội dung ngắn.
- Thiếu script runnable, checkpoint đầy đủ, AMP clipping order, structured logging, artifact path an toàn.
- Thiếu nối logic từ Day 9-10 và production readiness chi tiết.

Đã sửa:

- Viết lại có dấu và tách folder.
- Bổ sung anatomy training loop, `model.train()`, `model.eval()`, `zero_grad`, `backward`, `optimizer.step`, scheduler, dropout, weight decay, gradient clipping, early stopping, mixed precision.
- Thêm script `day11_training_loop.py` có seed/config, device fallback, `Dataset`/`DataLoader`, `BCEWithLogitsLoss`, `AdamW`, `ReduceLROnPlateau`, AMP, clipping, checkpoint, metric logging và test evaluation.
- Bổ sung production readiness, performance trade-off và checklist hoàn thành.

Context7 đã dùng:

- `/pytorch/pytorch`

### Day 12: NLP Fundamentals & Tokenizer

Files:

- `lessions/day-12-nlp-fundamentals-tokenizer/lession.md`
- `lessions/day-12-nlp-fundamentals-tokenizer/document.md`
- `lessions/day-12-nlp-fundamentals-tokenizer/exercise.md`
- `lessions/day-12-nlp-fundamentals-tokenizer.md`

Review findings:

- Bài cũ không dấu, nội dung mỏng, chưa tách folder.
- Thiếu mạch nối Day 11/13, thiếu tokenizer wrapper gần production và production answer rõ ràng.

Đã sửa:

- Viết lại step by step: preprocessing, tokenization, BPE, WordPiece, SentencePiece, vocabulary, OOV/UNK, padding, truncation, attention mask, token limit/cost và đặc thù tiếng Việt.
- Bổ sung tokenizer wrapper có config, max length, truncation policy, batch tokenization, token stats, cost estimator và warning/error cho input vượt budget.
- Thêm bài tập so sánh tokenizer BERT/GPT-style/PhoBERT, ước lượng cost và thiết kế policy production.

Context7 đã dùng:

- `/websites/huggingface_co_transformers_main`
- `/huggingface/tokenizers`
- `/huggingface/course`

### Day 13: Attention Mechanism

Files:

- `lessions/day-13-attention-mechanism/lession.md`
- `lessions/day-13-attention-mechanism/document.md`
- `lessions/day-13-attention-mechanism/exercise.md`
- `lessions/day-13-attention-mechanism/attention_demo.py`
- `lessions/day-13-attention-mechanism.md`

Review findings:

- Bài cũ là file phẳng, tiếng Việt không dấu, chưa tách `lession.md`/`document.md`/`exercise.md`.
- Thiếu chiều sâu quanh mask, multi-head, production trade-off và test code.

Đã sửa:

- Viết lại có dấu, nối logic từ Day 12 tokenizer/mask sang Day 14 Transformer block.
- Bổ sung Query/Key/Value, scaled dot-product attention, self-attention, causal mask, padding mask, multi-head attention, so sánh với RNN và diagram ASCII.
- Bổ sung trade-off attention `O(n^2)`, memory, long context, FlashAttention concept, batch vs streaming và KV cache.
- Thêm `attention_demo.py` có shape validation, mask handling, dropout train/eval, dtype/device checks và assertions.

Context7 đã dùng:

- `/pytorch/pytorch`
- `/websites/pytorch_2_11`

### Day 14: Transformer Architecture

Files:

- `lessions/day-14-transformer-architecture/lession.md`
- `lessions/day-14-transformer-architecture/document.md`
- `lessions/day-14-transformer-architecture/exercise.md`
- `lessions/day-14-transformer-architecture.md`

Review findings:

- Bài cũ là file phẳng, chưa tách folder.
- Nội dung không dấu và thiếu chiều sâu về encoder/decoder, RoPE, LayerNorm, FFN, residual connection.
- Thiếu decision example gần production, checklist đọc paper/model card, quiz/exercise và trade-off latency/memory/KV cache/context length.

Đã sửa:

- Viết lại có dấu và tách folder.
- Bổ sung Transformer block, encoder, decoder, encoder-only/BERT, decoder-only/GPT/LLaMA/Qwen, encoder-decoder/T5, positional encoding, RoPE, LayerNorm, FFN và residual connection.
- Thêm bảng/diagram luồng dữ liệu, decision matrix chọn architecture cho semantic search, classification, chatbot, summarization.
- Bổ sung production constraints: latency, memory, KV cache, context length, serving, license, data privacy, rollback.

Context7 đã dùng:

- Không dùng. Phần sửa là kiến thức architecture/design, không dùng API/library cụ thể.

### Day 15: Hugging Face Ecosystem

Files:

- `lessions/day-15-huggingface-ecosystem/lession.md`
- `lessions/day-15-huggingface-ecosystem/document.md`
- `lessions/day-15-huggingface-ecosystem/exercise.md`
- `lessions/day-15-huggingface-ecosystem.md`

Review findings:

- Bài cũ không dấu, nội dung ngắn, thiếu `datasets`, `Trainer`, `accelerate`, production wrapper và model card checklist đầy đủ.
- Ví dụ cũ thiên demo, thiếu revision pinning, batching, truncation, device handling, error handling, label mapping, license/security review.

Đã sửa:

- Viết lại step by step về `transformers`, `datasets`, `tokenizers`, `accelerate`, Model Hub, model card, `AutoTokenizer`, `AutoModel`, `pipeline`, `Trainer`.
- Bổ sung model card checklist: license, intended use, limitations, language, dataset, metrics, safety, inference requirements.
- Bổ sung trade-off `pipeline` vs raw model, `Trainer` vs custom loop, local vs hosted, CPU/GPU, batch size, quantization overview, license/security.
- Thêm wrapper/template inference gần production có model/tokenizer loading, revision pinning, device handling, batching, truncation, output schema và error handling.

Context7 đã dùng:

- `/websites/huggingface_co_transformers_main`
- `/llmstxt/huggingface_co_datasets_main_en_llms_txt`
- `/huggingface/accelerate`

## 6. Verification

Main agent đã chạy các kiểm tra sau:

- `rtk git status --short`
- `rtk rg --files` cho folder Day 11-15.
- `rtk wc -l` cho 22 file trong phạm vi Day 11-15.
- `rtk git diff --check -- ...` cho toàn bộ phạm vi Day 11-15.
- `rtk rg` kiểm tra section/keyword: production readiness, trade-off, performance, best solution, checklist, quiz, diagram.
- `rtk rg` kiểm tra API/khái niệm bắt buộc: `DataLoader`, `AdamW`, `ReduceLROnPlateau`, `BCEWithLogitsLoss`, `torch.amp`, `checkpoint`, `early stopping`, `BPE`, `WordPiece`, `SentencePiece`, `OOV`, `Query`, `Key`, `Value`, `causal mask`, `multi-head`, `FlashAttention`, `encoder-only`, `decoder-only`, `encoder-decoder`, `BERT`, `GPT`, `LLaMA`, `Qwen`, `T5`, `RoPE`, `LayerNorm`, `residual`, `KV cache`, `transformers`, `datasets`, `tokenizers`, `accelerate`, `Model Hub`, `model card`, `AutoTokenizer`, `AutoModel`, `Pipeline`, `Trainer`.
- `rtk rg` kiểm tra không còn marker heading tiếng Việt không dấu kiểu cũ trong phạm vi Day 11-15.
- `rtk rg` kiểm tra không còn `TODO`, `FIXME`, `placeholder`, `REPLACE_ME`, `TBD` trong phạm vi Day 11-15.
- `rtk python3 -m py_compile` cho:
  - `lessions/day-11-training-loop-optimizer-scheduler/day11_training_loop.py`
  - `lessions/day-13-attention-mechanism/attention_demo.py`
- `rtk python3 -c "import torch; print(torch.__version__)"`
- `rtk python3 -c "import transformers; print(transformers.__version__)"`

Kết quả:

- Cấu trúc folder/file đạt yêu cầu.
- Các section production/trade-off/performance/best solution xuất hiện trong từng bài.
- Targeted whitespace check cho file đã sửa trong phạm vi Day 11-15 pass.
- Script Day 11 và Day 13 compile được về mặt cú pháp.
- Môi trường hiện tại chưa cài `torch`.
- Môi trường hiện tại chưa cài `transformers`.
- Vì thiếu dependency và có khả năng cần tải model/package từ mạng, chưa chạy end-to-end training/inference/tokenizer runtime.

## 7. Rủi Ro Còn Lại

- Chưa chạy runtime training Day 11 và attention demo Day 13 vì thiếu `torch`.
- Chưa live-run tokenizer/Hugging Face examples Day 12 và Day 15 vì thiếu `transformers` và có thể cần network để tải model.
- Giá token trong Day 12 là demo; khi triển khai thật phải cập nhật theo provider/model hiện tại.
- Model card/license trong Day 15 vẫn phải được review theo model cụ thể trước khi dùng production.
- Worktree trước khi làm đã có thay đổi ở `review-and-fixed-task.md`; main/subagents không revert thay đổi ngoài phạm vi.

## 8. Kết Luận

Day 11-15 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code gần production và câu trả lời production readiness cho từng bài. Main agent đã hoàn tất audit trực tiếp trên artifact hiện tại và cập nhật checklist tổng.

---

# Review And Fixed Checklist - Day 16 Đến Day 20

Ngày tổng hợp: 2026-05-10

Phạm vi: review và sửa 5 bài học từ Day 16 đến Day 20 theo `review-and-fixed-task.md`.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách bài học hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 16, Day 17, Day 18, Day 19, Day 20.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã tự kiểm tra cấu trúc, heading, keyword bắt buộc, syntax script và whitespace trong phạm vi Day 16-20.
- [x] Chỉ main agent cập nhật `review-and-fixed-checklist.md`.

## 2. Prompt-to-Artifact Audit

| Yêu cầu explicit | Evidence trong repo | Kết quả |
|---|---|---|
| Review 5 bài từ Day 16 đến Day 20 | Đã xử lý `lessions/day-16...md` đến `lessions/day-20...md` | Done |
| Nội dung tiếng Việt có dấu | Các bài mới trong folder Day 16-20 đã được viết lại có dấu | Done |
| Giữ thuật ngữ chuyên ngành bằng English | Giữ `Transformer`, `PhoBERT`, `Trainer`, `FastAPI`, `structured output`, `function calling`, `prompt registry`, `model router` | Done |
| Mỗi bài có folder riêng | Có folder `lessions/day-16.../` đến `lessions/day-20.../` | Done |
| Mỗi folder có `lession.md` | Có đủ 5 file `lession.md` | Done |
| Có `document.md` | Có đủ 5 file `document.md` | Done |
| Có `exercise.md` | Có đủ 5 file `exercise.md` | Done |
| File phẳng cũ trỏ về folder mới | `lessions/day-16...md` đến `day-20...md` là trang điều hướng | Done |
| Nội dung step by step, ít phải search thêm | Mỗi bài có TL;DR, workflow, checklist, reference hoặc rubric | Done |
| Ưu tiên thực hành | Day 16, 18, 19, 20 có script; Day 17 có lab đo latency/token/cost | Done |
| Trade-off theo context | Có trade-off model, prompt, schema, tool, provider, cache, retry, cost/latency | Done |
| Best solution theo context | Có decision guidance cho baseline vs Transformer, hosted vs local, zero-shot vs few-shot, schema/tooling, orchestrator | Done |
| Performance concern | Có latency, token budget, batching, retry cost, p95/p99, cache hit, model memory/VRAM | Done |
| Code gần production | Có validation, artifact metadata, versioning, audit log, idempotency, cache/quota, fallback | Done |
| Production readiness answer | Mỗi bài có mục trả lời "Dùng được trong production không? Nếu có thì cần điều kiện gì?" | Done |
| Context7 khi dùng library docs | Subagents dùng Context7 cho Hugging Face, FastAPI và Pydantic khi có API cụ thể | Done |

## 3. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 16-20 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo/checklist riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập riêng. |
| Có script thực hành khi cần | Done | Day 16, 18, 19, 20 có script Python riêng. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-16...md` đến `day-20...md` là trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu. |
| Giữ thuật ngữ chuyên ngành bằng English | Done | Ví dụ: `PhoBERT`, `BERT`, `LLM`, `SFT`, `RLHF`, `JSON Schema`, `Pydantic`, `FastAPI`. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có TL;DR, mental model, workflow, checklist hoặc reference. |
| Ưu tiên thực hành | Done | Có lab, script, rubric và template decision. |
| Có trade-off theo context | Done | Có trade-off quality/latency/cost/security/reliability/maintainability. |
| Có best solution theo context | Done | Có guidance chọn baseline/Transformer, decoding/model, prompt strategy, structured output và architecture. |
| Có performance concern | Done | Có latency p95/p99, token budget, retry cost, batching, cache, quota, memory/VRAM. |
| Code example gần production | Done | Có validation, config, metadata, artifact, audit log, idempotency, timeout, retry, fallback, quota. |
| Trả lời production readiness | Done | Mỗi bài có mục hoặc bài tập trả lời điều kiện production. |
| Context7 khi dùng library docs | Done | Đã dùng Context7 cho Hugging Face, FastAPI và Pydantic-related APIs. |

## 4. Kết Quả Theo Bài

### Day 16: Fine-tune PhoBERT/BERT Classifier

Files:

- `lessions/day-16-fine-tune-phobert-bert-classifier/lession.md`
- `lessions/day-16-fine-tune-phobert-bert-classifier/document.md`
- `lessions/day-16-fine-tune-phobert-bert-classifier/exercise.md`
- `lessions/day-16-fine-tune-phobert-bert-classifier/train_sentiment.py`
- `lessions/day-16-fine-tune-phobert-bert-classifier/serve_sentiment.py`
- `lessions/day-16-fine-tune-phobert-bert-classifier.md`

Review findings:

- Bài cũ là file phẳng, chưa tách `lession.md`, `document.md`, `exercise.md`.
- Nội dung tiếng Việt không dấu và còn ngắn so với yêu cầu khóa học.
- Thiếu workflow production rõ: artifact manifest, model card, label mapping, error analysis, monitoring, rollback.
- Code cũ nằm inline trong bài học, chưa tách thành script chạy được.
- Chưa trả lời đủ rõ câu "Dùng được trong production không? Nếu có thì cần điều kiện gì?".

Đã sửa:

- Viết lại có dấu và tách folder.
- Bổ sung baseline `TF-IDF + Logistic Regression`, fine-tune `PhoBERT/BERT`, evaluation, export artifact và FastAPI serving.
- Thêm trade-off baseline vs Transformer, performance considerations, production concerns và production decision template.
- Thêm `train_sentiment.py` và `serve_sentiment.py` có artifact metadata, label mapping, schema, latency logging và API contract.

Context7 đã dùng:

- Hugging Face/FastAPI docs pattern cho `Trainer`, tokenizer truncation/padding và FastAPI `lifespan`.

### Day 17: LLM Fundamentals

Files:

- `lessions/day-17-llm-fundamentals/lession.md`
- `lessions/day-17-llm-fundamentals/document.md`
- `lessions/day-17-llm-fundamentals/exercise.md`
- `lessions/day-17-llm-fundamentals.md`

Review findings:

- Bản cũ là file phẳng, chưa tách `lession.md`, `document.md`, `exercise.md`.
- Nội dung không dấu, chưa đủ step by step.
- Thiếu chiều sâu về tokenization, next-token prediction, context window, decoding params, cost/latency/security.
- Production readiness còn ngắn, chưa có checklist, template quyết định model, observability và exercise gần production.

Đã sửa:

- Viết lại có dấu, giữ thuật ngữ chuyên ngành English.
- Bổ sung tokenization, next-token prediction, pre-training, SFT, RLHF/preference tuning, context window, decoding, hosted vs local/open-weight model.
- Thêm trade-off, performance, cost worksheet, security checklist, observability fields và production readiness answer.
- Thêm exercise có code Python gọi Ollama-style API, đo latency/token/output stability và kiểm tra output bằng `pydantic`.

### Day 18: Prompt Engineering Thực Chiến

Files:

- `lessions/day-18-prompt-engineering-thuc-chien/lession.md`
- `lessions/day-18-prompt-engineering-thuc-chien/document.md`
- `lessions/day-18-prompt-engineering-thuc-chien/exercise.md`
- `lessions/day-18-prompt-engineering-thuc-chien/prompt_eval.py`
- `lessions/day-18-prompt-engineering-thuc-chien.md`

Review findings:

- File cũ là một bài phẳng, tiếng Việt không dấu, chưa tách `lession.md`, `document.md`, `exercise.md`.
- Nội dung đúng hướng nhưng thiếu độ sâu về API contract, golden set, versioning, canary/A/B, injection risk và production readiness.
- Hands-on chưa đủ gần production: chưa có rubric, release checklist, eval threshold, schema/failure policy rõ.

Đã sửa:

- Bổ sung prompt as API contract, zero-shot, few-shot, examples, Chain-of-Thought dùng đúng mức, role/constraint prompting, structured output, eval golden set, prompt versioning, injection risks, A/B/canary.
- Thêm prompt library mẫu cho 5 use case: summarization, classification, invoice extraction, code review, customer support.
- Thêm trade-off, performance notes, production readiness conditions và các trường log/version/rollback cần có.
- Thêm `prompt_eval.py` để kiểm tra metadata và golden set offline trước khi chạy LLM thật.

### Day 19: Structured Output & Function Calling

Files:

- `lessions/day-19-structured-output-function-calling/lession.md`
- `lessions/day-19-structured-output-function-calling/document.md`
- `lessions/day-19-structured-output-function-calling/exercise.md`
- `lessions/day-19-structured-output-function-calling/day19_service.py`
- `lessions/day-19-structured-output-function-calling.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu, chưa đúng yêu cầu tách folder.
- Nội dung còn mỏng so với plan Day 19: thiếu semantic validation, retry/repair rõ ràng, idempotency, audit log, allowlist, least privilege.
- Code ví dụ trước còn gần toy example, chưa thể hiện production boundary giữa "model decides" và "system executes".
- Production readiness chưa đủ cụ thể.

Đã sửa:

- Viết lại có dấu, giữ thuật ngữ chuyên ngành English.
- Bổ sung JSON Schema/Pydantic validation, structured output, tool/function calling, retry/repair và semantic validation.
- Thêm security boundary: allowlist, least privilege, tenant/user scope, idempotency, audit log, PII logging policy.
- Thêm `day19_service.py` là FastAPI mock service có schema, retry, semantic validation, tool allowlist, idempotency và audit event.

Context7 đã dùng:

- Pydantic v2 và FastAPI API liên quan.

### Day 20: LLM App Architecture Cho Production

Files:

- `lessions/day-20-llm-app-architecture-production/lession.md`
- `lessions/day-20-llm-app-architecture-production/document.md`
- `lessions/day-20-llm-app-architecture-production/exercise.md`
- `lessions/day-20-llm-app-architecture-production/day20_orchestrator.py`
- `lessions/day-20-llm-app-architecture-production.md`

Review findings:

- Bản cũ tiếng Việt không dấu, chưa đạt yêu cầu readability.
- Nội dung còn là file phẳng, chưa tách `lession.md`, `document.md`, `exercise.md`.
- Có skeleton FastAPI trong markdown nhưng chưa có script chạy trực tiếp.
- Chưa đủ sâu về orchestrator/gateway, prompt registry, model router, provider adapter, multi-tenancy, quota, cost controls, observability và audit log.
- Câu trả lời production readiness còn quá ngắn, chưa nêu điều kiện cụ thể.

Đã sửa:

- Viết lại Day 20 thành bài production-style có orchestrator/gateway, prompt registry, model router, provider adapters, retry/timeout/fallback, cache, quota, audit, metrics và cost controls.
- Thêm trade-off, performance, cost, security, reliability và production readiness rubric.
- Thêm `day20_orchestrator.py`, FastAPI skeleton dùng mock providers để kiểm tra cache hit, routing, fallback, quota, audit log và metrics.
- File phẳng cũ giờ là trang điều hướng về folder mới.

## 5. Verification

Main agent đã chạy các kiểm tra sau:

- `git status --short` trong phạm vi Day 16-20 và checklist.
- `find`/`wc -l` cho toàn bộ file Day 16-20.
- `rg` kiểm tra section/keyword: production readiness, trade-off, performance, best solution, checklist và Context7.
- `rg` kiểm tra các marker cũ tiếng Việt không dấu phổ biến trong phạm vi Day 16-20.
- `python3 -B -m py_compile` cho:
  - `lessions/day-16-fine-tune-phobert-bert-classifier/train_sentiment.py`
  - `lessions/day-16-fine-tune-phobert-bert-classifier/serve_sentiment.py`
  - `lessions/day-18-prompt-engineering-thuc-chien/prompt_eval.py`
  - `lessions/day-19-structured-output-function-calling/day19_service.py`
  - `lessions/day-20-llm-app-architecture-production/day20_orchestrator.py`
- `git diff --check -- ...` cho toàn bộ phạm vi Day 16-20.
- Dọn các thư mục `__pycache__` phát sinh sau syntax check.

Kết quả:

- Cấu trúc folder/file đạt yêu cầu.
- Các section production/trade-off/performance/best solution xuất hiện trong từng bài.
- Targeted whitespace check cho file đã sửa trong phạm vi Day 16-20 pass.
- Tất cả script Python trong phạm vi Day 16-20 compile được về mặt cú pháp.
- Chưa chạy full training/inference/FastAPI server vì môi trường hiện thiếu dependency như `pandas`, `fastapi`, `pydantic`, `transformers`, `torch` và có thể cần network để tải model.

## 6. Rủi Ro Còn Lại

- Day 16 chưa chạy full training hoặc serve thật vì thiếu dependency ML và model download có thể cần network.
- Day 17 exercise phụ thuộc Ollama hoặc provider OpenAI-compatible nếu muốn đo runtime thật.
- Day 19 và Day 20 chưa chạy FastAPI server vì môi trường hiện chưa cài `fastapi`/`pydantic`.
- Các script là skeleton/lab gần production; trước khi dùng thật cần thay mock provider/model, cấu hình secret manager, persistence, auth, rate limit và observability backend thật.
- Worktree trước khi làm đã có nhiều thay đổi ở Day 11-15 và checklist; main/subagents không revert thay đổi ngoài phạm vi.

## 7. Kết Luận

Day 16-20 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code gần production và câu trả lời production readiness cho từng bài. Main agent đã hoàn tất audit trực tiếp trên artifact hiện tại và cập nhật checklist tổng.

---

# Review And Fixed Checklist - Day 21 Đến Day 25

Ngày tổng hợp: 2026-05-10

Phạm vi: review và sửa 5 bài học từ Day 21 đến Day 25 theo `review-and-fixed-task.md`.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách file hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 21, Day 22, Day 23, Day 24, Day 25.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã tự kiểm tra cấu trúc, heading, keyword bắt buộc, syntax app Day 24 và whitespace trong phạm vi Day 21-25.
- [x] Chỉ main agent cập nhật `review-and-fixed-checklist.md`.

## 2. Prompt-to-Artifact Audit

| Yêu cầu explicit | Evidence trong repo | Kết quả |
|---|---|---|
| Review 5 bài từ Day 21 đến Day 25 | Đã xử lý `lessions/day-21...md` đến `lessions/day-25...md` | Done |
| Nội dung tiếng Việt có dấu | Các bài mới trong folder Day 21-25 đã được viết lại có dấu | Done |
| Giữ thuật ngữ chuyên ngành bằng English | Giữ `Raw SDK`, `LangChain LCEL`, `LlamaIndex`, `LangGraph`, `ReAct`, `tool calling`, `RAG`, `LoRA`, `QLoRA` | Done |
| Mỗi bài có folder riêng | Có folder `lessions/day-21.../` đến `lessions/day-25.../` | Done |
| Mỗi folder có `lession.md` | Có đủ 5 file `lession.md` | Done |
| Có `document.md` | Có đủ 5 file `document.md` | Done |
| Có `exercise.md` | Có đủ 5 file `exercise.md` | Done |
| File phẳng cũ trỏ về folder mới | `lessions/day-21...md` đến `day-25...md` là trang điều hướng | Done |
| Nội dung step by step, ít phải search thêm | Mỗi bài có TL;DR, workflow, checklist, reference hoặc rubric | Done |
| Ưu tiên thực hành | Day 21 có lab Raw SDK/LangChain; Day 22 có LangGraph lab; Day 23 có threat model lab; Day 24 có app/tests; Day 25 có decision records | Done |
| Trade-off theo context | Có trade-off abstraction, agent pattern, security controls, memory/tool design, RAG vs fine-tune | Done |
| Best solution theo context | Có decision guidance cho framework, agent pattern, security boundary, assistant architecture, prompt/RAG/tool/fine-tune | Done |
| Performance concern | Có latency, token/cost, tool loop, checkpoint IO, retrieval/rerank, retry, memory/idempotency, adapter/runtime cost | Done |
| Code gần production | Có validation, schema, trace, idempotency, tool executor, memory allowlist, security tests hoặc code skeleton production-style | Done |
| Production readiness answer | Mỗi bài có mục "Dùng được trong production không? Nếu có thì cần điều kiện gì?" | Done |
| Context7 khi dùng library docs | Main agent dùng Context7 cho LangChain, LangGraph và LlamaIndex trước khi giao/sửa bài có API cụ thể | Done |

## 3. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 21-25 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo/checklist riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập riêng. |
| Có app/test khi cần | Done | Day 24 có `assistant_app/`, `tests/`, `README.md`, `requirements.txt`. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-21...md` đến `day-25...md` là trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu. |
| Giữ thuật ngữ chuyên ngành bằng English | Done | Ví dụ: `structured output`, `ToolNode`, `tools_condition`, `prompt injection`, `idempotency`, `PEFT`. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có mental model, flow, decision matrix, checklist hoặc exercise rubric. |
| Ưu tiên thực hành | Done | Có lab, mini-project, threat model, decision record và tests. |
| Có trade-off theo context | Done | Có trade-off quality/latency/cost/security/operability/complexity. |
| Có best solution theo context | Done | Có guidance theo SLA, team maturity, workflow complexity, risk và metric. |
| Có performance concern | Done | Có latency p95, token/cost, retry, tool calls, checkpoint, retrieval, adapter memory và throughput. |
| Code example gần production | Done | Có Pydantic schema, FastAPI sample, tool allowlist, idempotency, trace, retry và security tests ở Day 24. |
| Trả lời production readiness | Done | Mỗi bài có mục hoặc bài tập trả lời điều kiện production. |

## 4. Kết Quả Theo Bài

### Day 21: Raw SDK vs LangChain vs LlamaIndex vs LangGraph

Files:

- `lessions/day-21-raw-sdk-langchain-llamaindex-langgraph/lession.md`
- `lessions/day-21-raw-sdk-langchain-llamaindex-langgraph/document.md`
- `lessions/day-21-raw-sdk-langchain-llamaindex-langgraph/exercise.md`
- `lessions/day-21-raw-sdk-langchain-llamaindex-langgraph.md`

Review findings:

- Bài cũ đúng chủ đề nhưng còn mỏng, tiếng Việt không dấu và chưa tách folder.
- Thiếu decision rules production cho Raw SDK, LangChain LCEL, LlamaIndex, LangGraph và DSPy.
- Thiếu observability, abstraction risk, structured output workflow và so sánh control/latency/debugging rõ ràng.

Đã sửa:

- Viết lại bài học có dấu, đầy đủ hơn, có mental model và decision matrix.
- Bổ sung Raw SDK, LangChain LCEL, LlamaIndex, LangGraph, DSPy, trade-off, performance và production readiness.
- Thêm ví dụ gần production cho flow `ticket triage -> structured output` bằng Raw SDK và LangChain LCEL.
- Thêm `document.md` với ADR/decision guide và `exercise.md` để so sánh trực tiếp hai implementation.

### Day 22: Agent Patterns Với LangGraph

Files:

- `lessions/day-22-agent-patterns-voi-langgraph/lession.md`
- `lessions/day-22-agent-patterns-voi-langgraph/document.md`
- `lessions/day-22-agent-patterns-voi-langgraph/exercise.md`
- `lessions/day-22-agent-patterns-voi-langgraph.md`

Review findings:

- File cũ còn tiếng Việt không dấu và chưa tách `lession.md`, `document.md`, `exercise.md`.
- Thiếu coverage về `MessagesState`, `ToolNode`, `tools_condition`, checkpoint, interrupt/resume, permission model và failure playbook.

Đã sửa:

- Bổ sung agent anatomy, ReAct, router, planner-executor, supervisor và human-in-the-loop.
- Thêm ví dụ LangGraph với `StateGraph`, `MessagesState`, `ToolNode`, `tools_condition`, `recursion_limit`, checkpointer, `interrupt` và `Command`.
- Bổ sung security/tool permission, observability, failure modes, performance/cost và production readiness.

### Day 23: Security Basics Cho LLM App

Files:

- `lessions/day-23-security-basics-cho-llm-app/lession.md`
- `lessions/day-23-security-basics-cho-llm-app/document.md`
- `lessions/day-23-security-basics-cho-llm-app/exercise.md`
- `lessions/day-23-security-basics-cho-llm-app.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu, chưa đủ sâu về security boundary.
- Thiếu threat model step-by-step cho chatbot có database tool.
- Thiếu tenant/ACL, audit logging, sandbox execution, red-team prompts và least privilege tool examples.

Đã sửa:

- Bổ sung attack surface, prompt injection, indirect prompt injection, jailbreak, tool abuse, data exfiltration và sensitive data leakage.
- Bổ sung output validation, least privilege tool design, sandbox execution, tenant/ACL và audit logging.
- Thêm `exercise.md` cho threat model + red-team lab và `document.md` làm production security reference/checklist.

### Day 24: Mini-project - AI Assistant Có Tool Calling + Memory

Files:

- `lessions/day-24-ai-assistant-tool-calling-memory/lession.md`
- `lessions/day-24-ai-assistant-tool-calling-memory/document.md`
- `lessions/day-24-ai-assistant-tool-calling-memory/exercise.md`
- `lessions/day-24-ai-assistant-tool-calling-memory/README.md`
- `lessions/day-24-ai-assistant-tool-calling-memory/assistant_app/`
- `lessions/day-24-ai-assistant-tool-calling-memory/tests/`
- `lessions/day-24-ai-assistant-tool-calling-memory/requirements.txt`
- `lessions/day-24-ai-assistant-tool-calling-memory.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu, chưa có mini-project artifact chạy được.
- Thiếu backend sample, tests, idempotency, trace, memory policy và security prompt coverage.
- Trong implementation mới, subagent phát hiện và sửa thêm lỗi echo KB snippet độc hại và conflict key `status` giữa tool status/ticket status.

Đã sửa:

- Bổ sung kiến trúc API assistant: FastAPI `/chat`, prompt template, structured output, tool executor, memory store, logging/trace, retry schema.
- Thêm 2 tools `search_kb`, `create_ticket` với allowlist, confirmation, idempotency và policy.
- Thêm memory allowlist, schema validation, security tests và README architecture.
- Bổ sung trade-off, performance, production readiness và exercise mở rộng tool/memory/retry/security.

### Day 25: Khi Nào Fine-tune, Khi Nào Dùng RAG

Files:

- `lessions/day-25-khi-nao-fine-tune-khi-nao-dung-rag/lession.md`
- `lessions/day-25-khi-nao-fine-tune-khi-nao-dung-rag/document.md`
- `lessions/day-25-khi-nao-fine-tune-khi-nao-dung-rag/exercise.md`
- `lessions/day-25-khi-nao-fine-tune-khi-nao-dung-rag.md`

Review findings:

- File cũ còn tiếng Việt không dấu, nội dung chưa đủ sâu cho phase Fine-tuning & Local LLM.
- Thiếu framework phân biệt prompt, RAG, tool calling, fine-tuning, distillation và hybrid.
- Thiếu dataset/privacy/eval/rollback/cost/latency và decision record cụ thể.

Đã sửa:

- Bổ sung decision framework cho prompt-only, RAG, tool calling, fine-tuning, distillation và hybrid.
- Cover full fine-tuning, PEFT, LoRA, QLoRA, adapter, prompt tuning và distillation.
- Thêm hybrid RAG + fine-tuned model architecture, production conditions, cost/latency model và rollback.
- Thêm 5 decision records cho internal policy Q&A, support ticket, invoice extraction, code review assistant và product FAQ realtime.

## 5. Verification

Main agent đã chạy các kiểm tra sau:

- `find` kiểm tra cấu trúc file/folder Day 21-25.
- `git status --short -- ...` trong phạm vi Day 21-25 và checklist.
- `wc -l` cho file điều hướng, `lession.md`, `document.md`, `exercise.md`.
- `rg` kiểm tra section/keyword bắt buộc:
  - Day 21: Raw SDK, LangChain, LlamaIndex, LangGraph, DSPy, structured output, ticket triage.
  - Day 22: ReAct, router, planner, supervisor, human-in-the-loop, `StateGraph`, `MessagesState`, `ToolNode`, `tools_condition`, `recursion_limit`, `interrupt`, checkpoint.
  - Day 23: prompt injection, indirect prompt injection, jailbreak, tool abuse, data exfiltration, least privilege, sandbox, tenant/ACL, audit, red-team.
  - Day 24: FastAPI, structured output, tool, memory, idempotency, `trace_id`, retry, schema, security, pytest.
  - Day 25: prompt-only, RAG, tool calling, fine-tuning, PEFT, LoRA, QLoRA, adapter, prompt tuning, distillation, hybrid, rollback, privacy, decision record.
- `git diff --check -- ...` cho toàn bộ phạm vi Day 21-25 và checklist: pass.
- `python3 -B -m py_compile lessions/day-24-ai-assistant-tool-calling-memory/assistant_app/*.py`: pass.
- Dọn `__pycache__` phát sinh sau syntax check.

Kết quả:

- Cấu trúc folder/file đạt yêu cầu.
- Các section production/trade-off/performance/best solution xuất hiện trong từng bài.
- Targeted whitespace check cho file đã sửa trong phạm vi Day 21-25 pass.
- App Python Day 24 compile được về mặt cú pháp.
- Subagent Day 24 báo đã chạy `pytest -q` trong pyenv Python 3.12.4 riêng và kết quả `12 passed`.
- Trong shell chính của main agent, `pytest`/`fastapi`/`pydantic` chưa có trên PATH của `python3`, nên main agent chưa chạy lại được test suite Day 24 bằng môi trường chính.

## 6. Rủi Ro Còn Lại

- Day 21 code examples chưa chạy thật vì cần provider key và dependencies như OpenAI/LangChain.
- Day 22 LangGraph snippets chưa chạy end-to-end vì cần LangGraph/LangChain dependency và provider model.
- Day 23 là tài liệu/security lab, không có script runtime để unit test.
- Day 24 có app và tests, nhưng main shell hiện thiếu `pytest`, `fastapi`, `pydantic`; cần cài `requirements.txt` trước khi chạy lại locally.
- Day 25 là bài decision/reference, không có runtime test.
- Các bài có code gần production nhưng vẫn là lab/reference implementation; trước khi dùng thật cần auth, tenant isolation, secret management, persistence, rate limit, observability backend, model/provider config và CI.
- Worktree trước khi làm đã có nhiều thay đổi ở Day 11-20 và checklist; main/subagents không revert thay đổi ngoài phạm vi.

## 7. Kết Luận

Day 21-25 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code hoặc design gần production và câu trả lời production readiness cho từng bài. Main agent đã hoàn tất audit trực tiếp trên artifact hiện tại và cập nhật checklist tổng.

---

# Review And Fixed Checklist - Day 26 Đến Day 30

Ngày tổng hợp: 2026-05-10

Phạm vi: review và sửa 5 bài học từ Day 26 đến Day 30 theo `review-and-fixed-task.md`.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, phần Phase 4 - Fine-tuning & Local LLM.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách file hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 26, Day 27, Day 28, Day 29, Day 30.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã tự kiểm tra cấu trúc, keyword bắt buộc, fenced code block, Python syntax block và whitespace trong phạm vi Day 26-30.
- [x] Chỉ main agent cập nhật `review-and-fixed-checklist.md`.

## 2. Prompt-to-Artifact Audit

| Yêu cầu explicit | Evidence trong repo | Kết quả |
|---|---|---|
| Review 5 bài từ Day 26 đến Day 30 | Đã xử lý `lessions/day-26...md` đến `lessions/day-30...md` | Done |
| Nội dung tiếng Việt có dấu | Nội dung mới trong folder Day 26-30 đã được viết lại có dấu | Done |
| Giữ thuật ngữ chuyên ngành bằng English | Giữ `Instruction Tuning`, `Alpaca`, `ShareGPT`, `ChatML`, `LoRA`, `QLoRA`, `Ollama`, `llama.cpp`, `vLLM`, `FastAPI`, `GGUF`, `AWQ`, `GPTQ` | Done |
| Mỗi bài có folder riêng | Có folder `lessions/day-26.../` đến `lessions/day-30.../` | Done |
| Mỗi folder có `lession.md` | Có đủ 5 file `lession.md` | Done |
| Có `document.md` | Có đủ 5 file `document.md` | Done |
| Có `exercise.md` | Có đủ 5 file `exercise.md` | Done |
| File phẳng cũ trỏ về folder mới | `lessions/day-26...md` đến `day-30...md` là trang điều hướng | Done |
| Nội dung step by step, ít phải search thêm | Mỗi bài có workflow, reference, checklist, code skeleton hoặc rubric | Done |
| Ưu tiên thực hành | Có dataset lab, LoRA/QLoRA lab, evaluation runner, local LLM probe và local model API benchmark | Done |
| Trade-off theo context | Có trade-off dataset quality, LoRA config, eval strategy, runtime choice, quantization và serving | Done |
| Best solution theo context | Có guidance chọn format dataset, target modules, eval gate, local runtime và quantization/deploy strategy | Done |
| Performance concern | Có token length, training VRAM, eval cost, p95/p99 latency, throughput, RAM/VRAM, KV cache và concurrency | Done |
| Code gần production | Có schema validation, PII redaction, adapter metadata, eval JSON report, OpenAI-compatible client, FastAPI gateway, benchmark script | Done |
| Production readiness answer | Mỗi bài có mục hoặc bài tập trả lời điều kiện production | Done |
| Context7 khi dùng library docs | Worker dùng Context7 cho PEFT/Transformers/TRL, OpenAI client, FastAPI/Pydantic khi có API cụ thể | Done |

## 3. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 26-30 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo/checklist riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập riêng. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-26...md` đến `day-30...md` là trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu. |
| Giữ thuật ngữ chuyên ngành bằng English | Done | Ví dụ: `Instruction Tuning`, `LoRA`, `QLoRA`, `LLM-as-a-judge`, `vLLM`, `GGUF`, `FastAPI`. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có TL;DR hoặc mục tiêu, flow, decision matrix, checklist hoặc reference. |
| Ưu tiên thực hành | Done | Có lab tạo dataset 500 examples, LoRA/QLoRA, eval before/after, local runtime và API deploy. |
| Có trade-off theo context | Done | Có trade-off quality/privacy/cost/latency/VRAM/throughput/operability. |
| Có best solution theo context | Done | Có guidance theo dataset source, hardware, SLA, risk, runtime và quality sensitivity. |
| Có performance concern | Done | Có token length, training time, VRAM, KV cache, p50/p95/p99, throughput, concurrency và memory peak. |
| Code example gần production | Done | Có validation, config, metadata, logging, timeout/retry, readiness, regression gate và benchmark. |
| Trả lời production readiness | Done | Mỗi bài có câu trả lời trực tiếp hoặc bài tập bắt buộc về điều kiện production. |

## 4. Kết Quả Theo Bài

### Day 26: Dataset Preparation Cho Instruction Tuning

Files:

- `lessions/day-26-dataset-preparation-instruction-tuning/lession.md`
- `lessions/day-26-dataset-preparation-instruction-tuning/document.md`
- `lessions/day-26-dataset-preparation-instruction-tuning/exercise.md`
- `lessions/day-26-dataset-preparation-instruction-tuning.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu và chưa tách `lession.md`, `document.md`, `exercise.md`.
- Nội dung đúng hướng nhưng thiếu schema validation, grouped split, PII redaction, dataset card, metadata và production readiness.
- Code mẫu cũ chưa xử lý license/source filtering, quality threshold, dedup trước split và split theo `group_id`.

Đã sửa:

- Viết lại có dấu, tách folder và chuyển file phẳng thành trang điều hướng.
- Bổ sung Alpaca, ShareGPT, ChatML/messages, cleaning, deduplication, train/validation/test split, quality > quantity, synthetic data và privacy.
- Thêm script gần production trong `document.md`: validate schema, normalize records, redact PII, deduplicate, filter quality/license, grouped split, xuất dataset card và metadata.
- Thêm exercise tạo dataset 500 examples, checklist, quiz/rubric và golden set làm input cho Day 28.

Context7 đã dùng:

- Không dùng. Script dùng Python standard library, không cần API docs cụ thể.

### Day 27: LoRA/QLoRA Hands-on

Files:

- `lessions/day-27-lora-qlora-hands-on/lession.md`
- `lessions/day-27-lora-qlora-hands-on/document.md`
- `lessions/day-27-lora-qlora-hands-on/exercise.md`
- `lessions/day-27-lora-qlora-hands-on.md`

Review findings:

- File cũ còn tiếng Việt không dấu, nội dung ngắn và chưa tách folder.
- Thiếu step-by-step cho PEFT, bitsandbytes, 4-bit quantization, `r`, `alpha`, `target_modules`, dropout và merge weights.
- Code còn dạng demo, thiếu seed, dataset validation, artifact metadata, inference sanity check và production notes.

Đã sửa:

- Viết lại có dấu, tách folder và chuyển file phẳng thành trang điều hướng.
- Bổ sung PEFT/LoRA/QLoRA, 4-bit NF4, bitsandbytes, Colab/local GPU path, config decision và merge/deploy options.
- Thêm code skeleton gần production: seed, config dataclass, model/tokenizer load, validation, split, train args, adapter save, metadata, inference sanity check và merge.
- Thêm exercise/quiz/rubric về VRAM, cost, performance và điều kiện production.

Context7 đã dùng:

- PEFT, TRL/SFTTrainer và Hugging Face Transformers/BitsAndBytesConfig.

### Day 28: Evaluation Trước/Sau Fine-tune

Files:

- `lessions/day-28-evaluation-truoc-sau-fine-tune/lession.md`
- `lessions/day-28-evaluation-truoc-sau-fine-tune/document.md`
- `lessions/day-28-evaluation-truoc-sau-fine-tune/exercise.md`
- `lessions/day-28-evaluation-truoc-sau-fine-tune.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu và chưa đúng cấu trúc folder.
- Nội dung còn sơ sài cho production: thiếu eval schema, deterministic prompt, metric computation, JSON report, judge rubric và regression gate.
- Chưa trả lời đủ rõ điều kiện dùng fine-tuned model trong production.

Đã sửa:

- Viết lại có dấu, tách folder và chuyển file phẳng thành trang điều hướng.
- Bổ sung golden dataset, exact match, format accuracy, human evaluation, LLM-as-a-judge, regression set, overfitting detection và before/after comparison.
- Thêm code gần production: eval case schema, deterministic prompt, scorer, aggregate, compare base vs fine-tuned, JSON report, judge rubric và regression gate.
- Thêm checklist, quiz, exercise và release gate theo quality, regression, safety, latency và cost.

Context7 đã dùng:

- Không dùng. Ví dụ được viết vendor-neutral, không cần API docs cụ thể.

### Day 29: Local LLM - Ollama, llama.cpp, vLLM

Files:

- `lessions/day-29-local-llm-ollama-llama-cpp-vllm/lession.md`
- `lessions/day-29-local-llm-ollama-llama-cpp-vllm/document.md`
- `lessions/day-29-local-llm-ollama-llama-cpp-vllm/exercise.md`
- `lessions/day-29-local-llm-ollama-llama-cpp-vllm.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu và chưa tách `lession.md`, `document.md`, `exercise.md`.
- Thiếu chiều sâu step by step về privacy, cost, latency, offline, runtime selection và production condition.
- Ví dụ code chưa đủ gần production: thiếu gateway/proxy rõ ràng, config, health/readiness, timeout/retry, logging và benchmark có concurrency.

Đã sửa:

- Viết lại có dấu, tách folder và chuyển file phẳng thành trang điều hướng.
- Bổ sung runtime matrix cho Ollama, llama.cpp, vLLM, TGI, LM Studio và cloud baseline.
- Bổ sung OpenAI-compatible client abstraction, FastAPI proxy/gateway, health/readiness check, timeout/retry, logging, config và benchmark script.
- Bổ sung production readiness checklist, quiz, exercise thiết kế và decision record template.

Context7 đã dùng:

- OpenAI Python client và FastAPI/Pydantic pattern.

### Day 30: Quantization & Deploy Local Model API

Files:

- `lessions/day-30-quantization-deploy-local-model-api/lession.md`
- `lessions/day-30-quantization-deploy-local-model-api/document.md`
- `lessions/day-30-quantization-deploy-local-model-api/exercise.md`
- `lessions/day-30-quantization-deploy-local-model-api.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu và chưa tách folder.
- Thiếu giải thích step by step về dtype, KV cache, VRAM estimation, throughput vs quality.
- Code FastAPI mới ở mức demo: thiếu readiness, timeout rõ, concurrency limit, memory/latency logging, benchmark concurrency và production checklist.

Đã sửa:

- Viết lại có dấu, tách folder và chuyển file phẳng thành trang điều hướng.
- Bổ sung FP32, FP16, BF16, INT8, INT4, GGUF, AWQ, GPTQ, KV cache, VRAM estimation và throughput vs quality.
- Thêm FastAPI gateway template gần production: schema, `/health`, `/ready`, timeout, concurrency limit, JSON logging, memory/latency logging và config qua env.
- Thêm benchmark script đo p50/p95/p99, req/s, error count, memory client và hướng dẫn đo RAM/VRAM server.
- Thêm checklist, quiz, exercise và mẫu `production_decision.md`.

Context7 đã dùng:

- FastAPI docs pattern: Pydantic model, `response_model`, `HTTPException`, lifespan/readiness.

## 5. Verification

Main agent đã chạy các kiểm tra sau:

- `find` kiểm tra cấu trúc file/folder Day 26-30.
- `test -f` xác nhận mỗi folder có đủ `lession.md`, `document.md`, `exercise.md`.
- `git status --short -- ...` trong phạm vi Day 26-30 và checklist.
- `wc -l` cho file điều hướng, `lession.md`, `document.md`, `exercise.md`.
- `rg` kiểm tra section/keyword bắt buộc:
  - Day 26: Alpaca, ShareGPT, ChatML, schema, PII, dedup, split, dataset card, synthetic data.
  - Day 27: PEFT, LoRA, QLoRA, bitsandbytes, `BitsAndBytesConfig`, `target_modules`, `merge_and_unload`, adapter metadata.
  - Day 28: golden dataset, exact match, format accuracy, human evaluation, LLM-as-a-judge, regression gate, JSON report.
  - Day 29: Ollama, llama.cpp, vLLM, TGI, LM Studio, OpenAI-compatible, FastAPI, health, timeout/retry, benchmark, VRAM, KV cache.
  - Day 30: FP32, FP16, BF16, INT8, INT4, GGUF, AWQ, GPTQ, KV cache, FastAPI, readiness, concurrency, benchmark.
- Fenced code block balance check cho toàn bộ Markdown Day 26-30: pass.
- `python3` AST parse cho 19 fenced `python` blocks trong Day 26-30: pass.
- `git diff --check -- ...` cho toàn bộ phạm vi Day 26-30: pass.

Kết quả:

- Cấu trúc folder/file đạt yêu cầu.
- Các section production/trade-off/performance/best solution xuất hiện trong từng bài.
- Targeted whitespace check cho file đã sửa trong phạm vi Day 26-30 pass.
- Các fenced `python` block compile được ở mức syntax/AST.
- Worker Day 26 đã smoke test script dataset trong `document.md` bằng `python3` với sample JSONL: `errors: 0`, output có redaction và split.
- Chưa chạy training LoRA/QLoRA, local LLM runtime, FastAPI server hoặc benchmark thực tế vì cần GPU/model download/runtime server/dependencies ngoài repo.

## 6. Rủi Ro Còn Lại

- Day 26 PII redaction bằng regex không bắt hết mọi loại PII/secret; near-duplicate detection mới mô tả hướng xử lý, script chỉ exact dedup để giữ dependency nhẹ.
- Day 27 code trong `document.md` là skeleton để tách ra thành script, chưa chạy end-to-end vì cần GPU/model download và dependencies Hugging Face/PEFT/TRL/bitsandbytes.
- Day 28 code là reference/snippet trong Markdown, chưa chạy với model/API thật nên latency/cost là hướng dẫn và mock workflow.
- Day 29 code gateway/benchmark là skeleton production-style, chưa chạy end-to-end vì không có Ollama/llama.cpp/vLLM runtime đang bật trong phiên này.
- Day 30 FastAPI gateway và benchmark là template trong tài liệu, chưa materialize thành `app.py` thật và chưa benchmark với model server/hardware cụ thể.
- Các bài có code gần production nhưng vẫn là lab/reference implementation; trước khi dùng thật cần license review, auth, tenant isolation, secret management, rate limit, observability backend, rollout/rollback và CI.
- Worktree trước khi làm đã có nhiều thay đổi ở các bài trước và checklist; main/subagents không revert thay đổi ngoài phạm vi.

## 7. Kết Luận

Day 26-30 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code hoặc design gần production và câu trả lời production readiness cho từng bài. Main agent đã hoàn tất audit trực tiếp trên artifact hiện tại và cập nhật checklist tổng.

---

# Review And Fixed Checklist - Day 31 Đến Day 35

Ngày tổng hợp: 2026-05-10

Phạm vi: review và sửa 5 bài học từ Day 31 đến Day 35 theo `review-and-fixed-task.md`.

## 1. Objective Và Success Criteria

Objective cụ thể: review và sửa Day 31-35 thuộc Phase 5 Production RAG.

Success criteria từ prompt:

- Đã đọc plan khóa học `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- Chia đúng 5 bài: Day 31, Day 32, Day 33, Day 34, Day 35.
- Spawn 5 subagents song song, mỗi subagent xử lý một bài.
- Mỗi bài được sửa từ tiếng Việt không dấu sang tiếng Việt có dấu, giữ thuật ngữ chuyên ngành bằng English khi hợp lý.
- Mỗi bài có folder riêng, gồm `lession.md`, `document.md`, `exercise.md`.
- File phẳng cũ trở thành trang điều hướng.
- Nội dung đủ chi tiết, step by step, ưu tiên thực hành, có trade-off, best solution theo context, performance concern và code/config gần production.
- Mỗi bài trả lời câu hỏi: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"
- Main agent chờ đủ 5 kết quả và chỉ main agent cập nhật `review-and-fixed-checklist.md`.

## 2. Prompt-to-Artifact Checklist

| Yêu cầu | Evidence đã kiểm tra | Trạng thái |
|---|---|---|
| Đọc plan khóa học | Đã inspect section Phase 5 Day 31-35 trong `lo_trinh_50_ngay_senior_se_to_ai_engineer.md` | Done |
| Chia thành 5 bài | Day 31 RAG Architecture, Day 32 Embedding Benchmark tiếng Việt, Day 33 Vector DB, Day 34 Chunking Strategies, Day 35 Metadata/Citation/Permission-aware RAG | Done |
| Spawn 5 subagents song song | 5 worker hoàn tất: Day 31, Day 32, Day 33, Day 34, Day 35 | Done |
| Chờ đủ 5 kết quả | Main agent nhận đủ completion của cả 5 worker trước khi audit/checklist | Done |
| Main agent cập nhật checklist | Chỉ main agent sửa section Day 31-35 trong file này | Done |
| Mỗi bài có folder riêng | `find lessions -maxdepth 2` xác nhận đủ folder Day 31-35 | Done |
| Mỗi folder có `lession.md`, `document.md`, `exercise.md` | `test -f` cho cả 5 folder trả `ok` | Done |
| File phẳng cũ là trang điều hướng | Đã inspect 5 file `lessions/day-31...md` đến `lessions/day-35...md`, đều trỏ về 3 file trong folder | Done |
| Tiếng Việt có dấu | Nội dung mới viết bằng tiếng Việt có dấu; targeted `rg` không còn heading cũ như `Muc Tieu`; một số token không dấu còn lại là code/English/technical terms hoặc false positive | Done |
| Giữ thuật ngữ chuyên ngành English | Có các thuật ngữ `RAG`, `Retrieval`, `Generation`, `Embedding`, `Vector DB`, `Retriever`, `Reranker`, `BM25`, `HNSW`, `IVF`, `PQ`, `ACL`, `metadata`, `citation` | Done |
| Nội dung đầy đủ, step by step | Mỗi `lession.md` có phần concept, pipeline/flow, trade-off, performance, production readiness; tổng 5.493 dòng trong phạm vi Day 31-35 | Done |
| Ưu tiên thực hành | Mỗi bài có `exercise.md`; Day 32 benchmark 3 models/20 queries, Day 33 Qdrant hands-on, Day 34 eval 3 chunking strategies, Day 35 enterprise schema/tests | Done |
| Trade-off theo context | `rg` xác nhận `Trade-off`, decision matrix hoặc best solution trong từng bài | Done |
| Best solution theo context | Day 32 có best solution matrix; Day 33 có decision guide; Day 34 có context matrix; Day 31/35 có production guidance theo system constraints | Done |
| Performance concern | Có latency/cost/storage/p95/p99/indexing lag/vector count/ACL filter/cache notes trong từng bài | Done |
| Code/config gần production | Có 27 Python code blocks parse AST được; có Qdrant/pgvector/schema/context builder/citation validator/chunking eval/benchmark examples | Done |
| Production readiness answer | `rg "Dùng được trong production"` và `production readiness` xuất hiện trong từng bài/folder | Done |
| Code fence hợp lệ | Script kiểm tra 20 Markdown files: `fenced_code_balance=ok` | Done |
| Python snippets parse được | Script AST kiểm tra 27 fenced Python blocks: `python_ast=ok` | Done |
| Whitespace check | `git diff --check -- ...Day 31-35... review-and-fixed-checklist.md` pass | Done |

## 3. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 31-35 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo/schema/runbook/corpus riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập riêng. |
| File phẳng cũ trỏ về folder mới | Done | Day 31-35 đã là trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới đã viết lại có dấu; thuật ngữ chuyên ngành giữ English. |
| Giải thích từ cơ bản đến chi tiết | Done | Có TL;DR/concept/step-by-step/pipeline/code/checklist. |
| Ưu tiên thực hành | Done | Bài tập có rubric, checklist hoặc report template. |
| Có trade-off theo context | Done | Có matrix/section trade-off trong từng bài. |
| Có best solution theo context | Done | Có guidance theo corpus, data policy, latency, cost, privacy, compliance. |
| Có performance concern | Done | Có latency, p95/p99, storage, vector dimension, index overhead, ACL filter, cache, reranker, cost. |
| Code example gần production | Done | Có validation, schema, metadata, ACL, source map, citation validator, trace/audit, report, benchmark. |
| Trả lời production readiness | Done | Từng bài đều nêu điều kiện để dùng production. |
| Context7 khi dùng library docs | Not used | Nội dung chủ yếu architecture/design/vendor-neutral; không cần tra API docs cụ thể. |

## 4. Kết Quả Theo Bài

### Day 31: RAG Architecture

Files:

- `lessions/day-31-rag-architecture/lession.md`
- `lessions/day-31-rag-architecture/document.md`
- `lessions/day-31-rag-architecture/exercise.md`
- `lessions/day-31-rag-architecture.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu.
- Nội dung có outline đúng nhưng chưa đủ sâu cho production RAG.
- Thiếu tách indexing/query/evaluation/admin paths, ACL, citation validation, trace, latency/cost budget và exercise.

Đã sửa:

- Viết lại có dấu, tách folder và chuyển file phẳng thành trang điều hướng.
- Bổ sung architecture diagram text, indexing pipeline, query pipeline, retriever/reranker/context builder/generator/citation validator.
- Thêm feedback loop, offline/online evaluation, trade-off, performance/cost và production readiness.
- Thêm code gần production với `UserContext`, `Retriever`, `Generator`, ACL filtering, context builder, citation validator và trace response.

### Day 32: Embedding Models & Benchmark Cho Tiếng Việt

Files:

- `lessions/day-32-embedding-models-benchmark-tieng-viet/lession.md`
- `lessions/day-32-embedding-models-benchmark-tieng-viet/document.md`
- `lessions/day-32-embedding-models-benchmark-tieng-viet/exercise.md`
- `lessions/day-32-embedding-models-benchmark-tieng-viet.md`

Review findings:

- File cũ là bài phẳng, tiếng Việt không dấu.
- Hands-on chưa đủ qrels, report, failure analysis và production decision.
- Thiếu rõ phần query không dấu, hybrid baseline, privacy, versioning, reindex, latency/cost/storage.

Đã sửa:

- Bổ sung dense vector, sentence embedding, cosine/dot/normalization, OpenAI/Cohere/BGE/E5/Vietnamese-specific models.
- Thêm Vietnamese retrieval concerns: có dấu/không dấu, acronym, English-mix, OCR, legal/finance wording.
- Thêm benchmark design với 20 queries, qrels, Hit@1, Hit@3, Recall@5, MRR@5, p50/p95 latency và storage estimate.
- Thêm document checklist cho normalization, hybrid dense+BM25, model versioning, privacy review và migration/reindex.

### Day 33: Vector DB

Files:

- `lessions/day-33-vector-db/lession.md`
- `lessions/day-33-vector-db/document.md`
- `lessions/day-33-vector-db/exercise.md`
- `lessions/day-33-vector-db.md`

Review findings:

- File cũ tiếng Việt không dấu và chưa tách lesson/document/exercise.
- Nội dung đúng hướng nhưng thiếu runbook production cho ACL, multi-tenancy, delete, reindex, backup/restore, monitoring.
- Thiếu code/config gần production và bài tập kiểm thử leak tenant/ACL.

Đã sửa:

- Bổ sung exact search vs ANN, HNSW, IVF, PQ, sharding, replication, metadata filtering, tenant/ACL.
- Thêm decision guide cho pgvector, Qdrant, Milvus, Weaviate, Pinecone, Chroma.
- Thêm schema production, Qdrant example, pgvector migration/query, delete/reindex/blue-green/backup/restore runbook.
- Thêm exercise Qdrant local với tenant/ACL filter, benchmark latency, Hit@K/Recall@K và tests chống leak.

### Day 34: Chunking Strategies

Files:

- `lessions/day-34-chunking-strategies/lession.md`
- `lessions/day-34-chunking-strategies/document.md`
- `lessions/day-34-chunking-strategies/exercise.md`
- `lessions/day-34-chunking-strategies.md`

Review findings:

- File cũ tiếng Việt không dấu và còn tổng quan.
- Thiếu folder bài học, tài liệu thực hành, exercise đánh giá và production readiness chi tiết.
- Thiếu metadata schema, citation/page/source risk, PDF/table/code handling và eval cụ thể.

Đã sửa:

- Bổ sung fixed-size, recursive, semantic, markdown-aware, PDF, code, parent-child chunking và overlap.
- Thêm metadata schema cho source/page/heading/version/tenant/ACL/parser/chunking strategy.
- Thêm code chunking/eval mini pipeline với stable chunk id, metadata, retrieval demo.
- Thêm corpus markdown policy, 6 ground-truth queries, bảng so sánh và rubric để test 3 strategies.

### Day 35: Metadata, Citation, Permission-aware RAG

Files:

- `lessions/day-35-metadata-citation-permission-aware-rag/lession.md`
- `lessions/day-35-metadata-citation-permission-aware-rag/document.md`
- `lessions/day-35-metadata-citation-permission-aware-rag/exercise.md`
- `lessions/day-35-metadata-citation-permission-aware-rag.md`

Review findings:

- File cũ tiếng Việt không dấu và chưa tách cấu trúc.
- Nội dung đúng hướng nhưng thiếu signed URL/proxy, tombstone/delete, audit event, regression tests, stale ACL/cache và citation validation chi tiết.

Đã sửa:

- Bổ sung metadata contract: source, page, section, document version, tenant, ACL, user/group/role permission, lifecycle fields.
- Thêm pre-filter + post-filter, deny-by-default, `source_map`, citation validator, signed URL/proxy flow.
- Thêm tombstone/delete lifecycle, audit log schema, cache invalidation, permission regression tests.
- Thêm code mẫu gần production và exercise thiết kế enterprise RAG.

## 5. Verification

Main agent đã chạy các kiểm tra sau:

- `find lessions -maxdepth 2` kiểm tra đủ 20 file Day 31-35.
- `test -f` xác nhận mỗi folder có đủ `lession.md`, `document.md`, `exercise.md`: `ok`.
- `wc -l` cho toàn bộ file Day 31-35: tổng 5.493 dòng.
- `rg` kiểm tra keyword bắt buộc theo từng bài:
  - Day 31: RAG, indexing pipeline, query pipeline, loader, chunker, embedding, Vector DB, retriever, reranker, generator, citation, feedback/evaluation.
  - Day 32: embedding, dense, cosine, dot, OpenAI, Cohere, BGE, E5, Vietnamese-specific, tiếng Việt không dấu, qrels, Hit@K, Recall, MRR, hybrid, privacy, storage.
  - Day 33: ANN, HNSW, IVF, PQ, Qdrant, Milvus, Weaviate, Pinecone, pgvector, Chroma, metadata, tenant, ACL, sharding, replication, backup, reindex, delete.
  - Day 34: fixed-size, recursive, semantic, markdown-aware, PDF, code, parent-child, overlap, metadata, citation, page/source, eval.
  - Day 35: metadata, source, page, section, version, tenant, ACL, permission, pre-filter, post-filter, citation, validator, signed URL/proxy, tombstone, delete, audit, regression.
- Script kiểm tra fenced code balance cho 20 Markdown files: pass.
- Script AST parse cho 27 fenced `python` blocks: pass.
- `git diff --check -- ...` trong phạm vi Day 31-35 và checklist: pass.

Kết quả:

- Cấu trúc folder/file đạt yêu cầu.
- Các section production/trade-off/performance/best solution xuất hiện trong từng bài.
- Python snippets parse được ở mức syntax.
- Targeted whitespace check pass.
- Không chạy benchmark/runtime thật cho embedding models, Qdrant, vector DB, RAG server hoặc model API vì cần dependency/model download/service ngoài repo.

## 6. Rủi Ro Còn Lại

- Day 32 benchmark code cần `sentence-transformers` và model download; chưa chạy end-to-end trong môi trường hiện tại.
- Day 33 Qdrant hands-on cần Qdrant service và `qdrant-client`; chưa chạy runtime thật.
- Day 34 chunking/eval code dùng embedding toy để học trade-off; khi dùng production cần thay bằng embedding model/vector DB thật.
- Day 35 code mẫu là framework-neutral reference; khi triển khai thật cần tích hợp authz service, signed URL provider, audit backend, cache invalidation và CI regression tests.
- Các bài là tài liệu/lab production-style, chưa materialize thành service deployable hoàn chỉnh.
- Worktree trước khi làm đã có nhiều thay đổi ở các bài trước và checklist; main/subagents không revert thay đổi ngoài phạm vi.

## 7. Kết Luận

Day 31-35 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code/config gần production và câu trả lời production readiness cho từng bài. Main agent đã hoàn tất audit trực tiếp trên artifact hiện tại và cập nhật checklist tổng.

---

# Review And Fixed Checklist - Day 36 Đến Day 40

Ngày tổng hợp: 2026-05-10

Phạm vi: review và sửa 5 bài học cuối của Phase 5 - Production RAG theo `review-and-fixed-task.md`.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách bài học hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 36, Day 37, Day 38, Day 39, Day 40.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã kiểm tra cấu trúc, heading, keyword bắt buộc, fenced code balance và whitespace trong phạm vi Day 36-40.
- [x] Main agent đã tổng hợp kết quả và cập nhật checklist này.

## 2. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 36-40 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo, template, checklist hoặc runbook riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập/lab riêng. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-36...md` đến `lessions/day-40...md` đã thành trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới đã viết lại bằng tiếng Việt có dấu; một số query cố ý không dấu được giữ làm test case cho retrieval tiếng Việt. |
| Giữ thuật ngữ chuyên ngành bằng English | Done | Ví dụ: `dense retrieval`, `BM25`, `SPLADE`, `RRF`, `reranker`, `RAGAS`, `TruLens`, `LangSmith`, `Docker Compose`. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có mental model, workflow, step-by-step, best practices và checklist. |
| Ưu tiên thực hành | Done | Mỗi bài có exercise/lab gần production hoặc report template. |
| Có trade-off theo context | Done | Có trade-off về quality, latency, cost, privacy, index size, model/API choice và operational complexity. |
| Có best solution theo context | Done | Có decision matrix cho hybrid search, reranking, advanced RAG patterns, eval gates và mini-project stack. |
| Có performance concern | Done | Có p50/p95/p99 latency, candidate count, rerank timeout, token/cost, cache, load test và release gate. |
| Code/config example gần production | Done | Có interface, validation, trace, ACL, citation validation, metrics helper, eval runner, Docker Compose/API/template. |
| Trả lời câu hỏi production | Done | Mỗi bài có mục trả lời "Dùng được trong production không? Nếu có thì cần điều kiện gì?" |
| Context7 khi dùng library docs | Not needed | Nội dung mới chủ yếu là framework-neutral reference và concept; không dựa vào API version-specific behavior. |

## 3. Kết Quả Theo Bài

### Day 36: Hybrid Search - Dense + Sparse + BM25

Files:

- `lessions/day-36-hybrid-search-dense-sparse-bm25/lession.md`
- `lessions/day-36-hybrid-search-dense-sparse-bm25/document.md`
- `lessions/day-36-hybrid-search-dense-sparse-bm25/exercise.md`
- `lessions/day-36-hybrid-search-dense-sparse-bm25.md`

Review findings:

- File cũ đúng hướng nhưng còn tiếng Việt không dấu và gom toàn bộ vào một file.
- Thiếu ACL/filter đồng nhất ở BM25 path và dense path.
- Thiếu query normalization tiếng Việt, benchmark theo query category, logging, cache, reindex và runbook.
- Code cũ thiên demo, chưa đủ report/eval gần production.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung dense retrieval, sparse retrieval, BM25, SPLADE overview, hybrid search, RRF, query normalization và keyword-heavy vs semantic query.
- Thêm document cheat sheet, decision matrix, Python reference pipeline, logging checklist, reindex/debug runbook.
- Thêm exercise BM25 + dense + RRF + Hit@K/Recall@K/MRR@K, pytest/checklist và report template có production readiness cụ thể.

### Day 37: Reranking

Files:

- `lessions/day-37-reranking/lession.md`
- `lessions/day-37-reranking/document.md`
- `lessions/day-37-reranking/exercise.md`
- `lessions/day-37-reranking.md`

Review findings:

- File cũ là file đơn, tiếng Việt không dấu và chưa theo pattern folder.
- Thiếu chiều sâu về BGE/Cohere trade-off, ACL trước rerank, fallback, latency/cost budget và eval before/after.
- Code cũ còn ngắn, chưa có lab/report rõ ràng.

Đã sửa:

- Bổ sung bi-encoder vs cross-encoder, reranker, BGE reranker, Cohere Rerank concept và two-stage retrieval.
- Nhấn mạnh retrieve top 50/100 rồi rerank top 5/10, kèm latency/cost/privacy/fallback trade-off.
- Thêm code Python gần production cho reranker layer, timeout/fallback và metrics Recall@k/MRR.
- Thêm document runbook, observability, rollout checklist và exercise thêm reranker vào pipeline Day 36.

### Day 38: Advanced RAG Patterns

Files:

- `lessions/day-38-advanced-rag-patterns/lession.md`
- `lessions/day-38-advanced-rag-patterns/document.md`
- `lessions/day-38-advanced-rag-patterns/exercise.md`
- `lessions/day-38-advanced-rag-patterns.md`

Review findings:

- File cũ liệt kê đúng pattern nhưng còn mỏng, không dấu và chưa tách lesson/document/exercise.
- Thiếu decision gate để tránh bật quá nhiều pattern cùng lúc.
- Thiếu ví dụ trace, fallback, timeout, tenant/ACL, prompt contract, metric và decision report.

Đã sửa:

- Bổ sung query rewriting, multi-query retrieval, HyDE, step-back prompting, decomposition, multi-hop RAG, contextual retrieval, corrective RAG, agentic RAG và GraphRAG overview.
- Nhấn mạnh ưu tiên production: baseline hybrid + reranking, sau đó mới query rewriting/contextual retrieval theo lỗi đo được.
- Thêm orchestration example gần production với policy, trace, ACL, query variants, merge, rerank và fallback.
- Thêm prompt contracts, performance budget, cost estimation, decision report, rollout/debug runbook và evaluation lab.

### Day 39: RAG Evaluation

Files:

- `lessions/day-39-rag-evaluation/lession.md`
- `lessions/day-39-rag-evaluation/document.md`
- `lessions/day-39-rag-evaluation/exercise.md`
- `lessions/day-39-rag-evaluation.md`

Review findings:

- File cũ có khung đúng nhưng còn tiếng Việt không dấu và chưa theo pattern folder.
- Thiếu golden set mẫu thật, qrels/versioning chi tiết, eval runner, CI/regression workflow và report template.
- RAGAS/TruLens/LangSmith mới ở mức liệt kê, chưa giải thích vai trò/trade-off.

Đã sửa:

- Bổ sung golden dataset, qrels, Recall@k, Precision@k, MRR, NDCG, context precision/recall, faithfulness, answer relevance và hallucination detection.
- Thêm quy trình tạo 30-50 câu golden set, error analysis theo root cause, release gate và regression mindset.
- Thêm `document.md` với schema, 41 câu golden set mẫu, report template, LLM-as-judge rubric và runbook.
- Thêm `exercise.md` với Python eval runner gần production, output contract, CI smoke/full eval và notes cho RAGAS/TruLens/LangSmith.

### Day 40: Mini-project - Production RAG System

Files:

- `lessions/day-40-mini-project-production-rag-system/lession.md`
- `lessions/day-40-mini-project-production-rag-system/document.md`
- `lessions/day-40-mini-project-production-rag-system/exercise.md`
- `lessions/day-40-mini-project-production-rag-system.md`

Review findings:

- File cũ đúng outline nhưng còn sơ sài, không có folder riêng và chưa đủ step-by-step để build end-to-end.
- Thiếu API/UI contract, ACL/security, citation validation, trace latency/token/cost, eval report, Docker/README template và production readiness.
- Chưa tách tài liệu template/runbook và lab triển khai.

Đã sửa:

- Bổ sung end-to-end architecture cho indexing path, query path, eval path, ops path và delivery path.
- Viết step-by-step upload/ingest, parse, normalize, chunk, embed, vector DB, hybrid search, RRF, rerank, context builder, generation và citation validation.
- Thêm backend API, simple UI, logging latency/token/cost, eval report, Docker Compose, README, security/ACL, performance/cost và checklist.
- Thêm `document.md` với architecture/API/schema/prompt/Docker/README/eval templates và incident runbook.
- Thêm `exercise.md` dạng lab triển khai mini-project có acceptance criteria, tests, rubric và câu hỏi production readiness.

## 4. Verification

Main agent đã chạy các kiểm tra sau:

- `find lessions -maxdepth 2` kiểm tra đủ folder/file Day 36-40.
- `wc -l` cho 20 file Day 36-40: tổng 7.891 dòng.
- `rg` kiểm tra heading và keyword bắt buộc theo từng bài:
  - Day 36: dense retrieval, sparse retrieval, BM25, SPLADE, RRF, query normalization, ACL, metrics, latency, production readiness.
  - Day 37: bi-encoder, cross-encoder, BGE, Cohere Rerank, two-stage retrieval, Recall@k, MRR, ACL, fallback, latency.
  - Day 38: query rewriting, multi-query, HyDE, step-back, decomposition, multi-hop, contextual retrieval, corrective RAG, agentic RAG, GraphRAG, evaluation gate.
  - Day 39: golden dataset, qrels, Recall@k, Precision@k, MRR, NDCG, context precision/recall, faithfulness, hallucination, CI, release gate.
  - Day 40: ingest, parse, chunk, embed, vector DB, hybrid search, rerank, citation, API, UI, Docker Compose, eval report, observability, ACL.
- `grep -c '^```'` kiểm tra fenced code count cho 15 file trong folder Day 36-40: tất cả là số chẵn.
- `rg` kiểm tra placeholder dạng `TODO`, `FIXME`, `TBD` và bullet `...`: pass.
- `git diff --check -- ...` trong phạm vi Day 36-40: pass.

Subagents cũng đã báo các kiểm tra riêng:

- Day 36 smoke test tokenizer bằng `python3` cho query có mã lỗi/ký hiệu và tiếng Việt có dấu/không dấu.
- Day 37 `git diff --check` cho file Day 37: pass.
- Day 38 kiểm tra trailing whitespace và diff check cho file tracked: pass.
- Day 39 compile code block `eval_runner.py` và chạy smoke test bằng `python3`.
- Day 40 kiểm tra whitespace và Markdown code fence trong phạm vi Day 40.

## 5. Rủi Ro Còn Lại

- Chưa chạy end-to-end toàn bộ exercises vì cần dependency/service/model ngoài repo như embedding model, reranker model/API, Vector DB, backend server hoặc Docker Compose project thật.
- Day 36 Python reference là in-memory pipeline để học contract; production thật cần thay bằng Elasticsearch/OpenSearch/Postgres full-text và Vector DB.
- Day 37 BGE/Cohere examples cần model/API key và phải kiểm tra license/privacy trước production.
- Day 38 advanced patterns cần eval before/after thật; không nên bật đồng loạt khi chưa có evidence.
- Day 39 LLM-as-judge/RAGAS/TruLens/LangSmith sections ở mức concept và workflow; khi triển khai thật cần khóa version, calibrate judge và lưu eval artifacts.
- Day 40 là mini-project blueprint/lab, chưa phải service production hoàn chỉnh; cần auth thật, secret management, backup/restore, monitoring/alerting, rate limit, CI và deployment hardening.
- Worktree trước khi làm đã có `review-and-fixed-task.md` modified; main/subagents chỉ đọc và không revert thay đổi ngoài phạm vi.

## 6. Kết Luận

Day 36-40 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance concern, code/config gần production và câu trả lời production readiness cho từng bài. Phase 5 hiện đã có chuỗi Production RAG hoàn chỉnh hơn từ architecture, embedding/vector DB, metadata/chunking đến hybrid search, reranking, advanced patterns, evaluation và mini-project.

---

# Review And Fixed Checklist - Day 41 Đến Day 45

Ngày tổng hợp: 2026-05-10

Phạm vi: review và sửa 5 bài học đầu của Phase 6 - MLOps & Production AI theo `review-and-fixed-task.md`.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách bài học hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 41, Day 42, Day 43, Day 44, Day 45.
- [x] Đã spawn 5 subagents song song, mỗi subagent xử lý một bài.
- [x] Đã chờ đủ 5 kết quả từ subagents.
- [x] Main agent đã kiểm tra cấu trúc, heading, keyword bắt buộc, placeholder, fenced code balance, Python snippet syntax và whitespace trong phạm vi Day 41-45.
- [x] Main agent đã tổng hợp kết quả và cập nhật checklist này.

## 2. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 41-45 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo, template, checklist hoặc runbook riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập/lab riêng. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-41...md` đến `lessions/day-45...md` đã thành trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu; thuật ngữ chuyên ngành English được giữ lại. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có mental model, step-by-step workflow, code/config mẫu, checklist hoặc runbook. |
| Ưu tiên thực hành | Done | Mỗi bài có exercise/lab gắn với capstone RAG/LLM service. |
| Có trade-off theo context | Done | Có trade-off về reliability, latency, cost, privacy, GPU ops, observability overhead và model/tool choice. |
| Có best solution theo context | Done | Có decision matrix cho MLflow, serving runtime, Docker/K8s/GPU deployment, observability stack và cost optimization. |
| Có performance concern | Done | Có p50/p95/p99 latency, TTFT, queue/concurrency, batching, GPU VRAM, token/cost, logging overhead và release gate. |
| Code/config example gần production | Done | Có MLflow tracking/registry code, FastAPI/SSE, Dockerfile/Compose/K8s manifests, OpenTelemetry/Prometheus và cost script. |
| Trả lời câu hỏi production | Done | Mỗi bài có mục trả lời "Dùng được trong production không? Nếu có thì cần điều kiện gì?" |
| Context7/official docs khi cần | Done | Subagents đã dùng Context7 hoặc official docs cho MLflow, FastAPI, Docker/K8s/GPU, OpenTelemetry/Prometheus và OpenAI caching/Batch API. |

## 3. Kết Quả Theo Bài

### Day 41: MLflow, Experiment Tracking, Model Registry

Files:

- `lessions/day-41-mlflow-experiment-tracking-model-registry/lession.md`
- `lessions/day-41-mlflow-experiment-tracking-model-registry/document.md`
- `lessions/day-41-mlflow-experiment-tracking-model-registry/exercise.md`
- `lessions/day-41-mlflow-experiment-tracking-model-registry.md`

Review findings:

- File cũ là file phẳng, tiếng Việt không dấu và chưa theo pattern folder.
- Nội dung thiếu production readiness answer, checklist/runbook, security/cost/performance/reproducibility concerns.
- Ví dụ MLflow cũ còn ngắn, chưa log dataset lineage, model signature, model card, latency gate và dependency lock.
- Registry workflow cũ còn nhắc stage transition; MLflow stages đã bị deprecated từ MLflow 2.9.0.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung MLflow Tracking Server, params/metrics/artifacts/tags, dataset logging, code version, model signature và model card.
- Cập nhật Model Registry workflow theo aliases/tags như `candidate`, `champion`, `shadow`; serving load bằng `models:/<model>@champion`.
- Thêm code gần production cho training run, latency benchmark, register model, promote alias và rollback alias.
- Thêm document tracking schema, runbook chọn best run/register/promote/rollback, security/reproducibility/performance/cost checklist.

### Day 42: Model Serving

Files:

- `lessions/day-42-model-serving/lession.md`
- `lessions/day-42-model-serving/document.md`
- `lessions/day-42-model-serving/exercise.md`
- `lessions/day-42-model-serving.md`

Review findings:

- File cũ còn ở dạng outline, tiếng Việt không dấu, chưa tách folder.
- Thiếu serving contract rõ, SSE contract, request validation, timeout, rate/concurrency limit, batching trade-off và tool comparison.
- Code SSE cũ chỉ là sketch, chưa thể hiện trace/error contract, client disconnect, limiter, timeout và runtime lifecycle.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung FastAPI service contract cho `/health`, `/ready`, `/query`, `/query/stream`, `/models/current`.
- Thêm code FastAPI gần production với Pydantic `extra="forbid"`, error contract, trace id, timeout, in-memory limiter cho local, concurrency semaphore và SSE events `meta/token/done/error`.
- Thêm decision matrix FastAPI/BentoML/TorchServe/Triton/vLLM/TGI và giải thích batching vs p95 latency/TTFT.
- Thêm exercise scaffold API, test validation, timeout, rate limit, concurrency limit, streaming client và release decision.

### Day 43: Docker/K8s/GPU Serving Cho AI Workload

Files:

- `lessions/day-43-docker-k8s-gpu-serving-ai-workload/lession.md`
- `lessions/day-43-docker-k8s-gpu-serving-ai-workload/document.md`
- `lessions/day-43-docker-k8s-gpu-serving-ai-workload/exercise.md`
- `lessions/day-43-docker-k8s-gpu-serving-ai-workload.md`

Review findings:

- File cũ còn tiếng Việt không dấu, nội dung mỏng và chưa tách `lession/document/exercise`.
- Thiếu template gần production cho Dockerfile, Compose, `.env.example`, K8s manifests.
- Thiếu phần GPU/NVIDIA stack, `nodeSelector`, taints/tolerations và `nvidia-device-plugin`.
- Thiếu trade-off, best solution theo context/performance và câu trả lời production readiness.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung Dockerfile CPU/GPU, `.dockerignore`, `.env.example`, Docker Compose cho API/vector DB/model server optional profile.
- Thêm Kubernetes manifests cho namespace, ConfigMap, Secret, Deployment, Service, probes, resource requests/limits, rollout/rollback.
- Thêm GPU scheduling: NVIDIA driver, `nvidia-container-toolkit`, `nvidia-device-plugin`, `nvidia.com/gpu`, `nodeSelector`, taints/tolerations.
- Thêm Helm/KServe/Ray Serve overview, deployment note, smoke test, resource estimate và production readiness checklist.

### Day 44: Observability Cho LLM App

Files:

- `lessions/day-44-observability-cho-llm-app/lession.md`
- `lessions/day-44-observability-cho-llm-app/document.md`
- `lessions/day-44-observability-cho-llm-app/exercise.md`
- `lessions/day-44-observability-cho-llm-app.md`

Review findings:

- File cũ là file phẳng, nhiều tiếng Việt không dấu và chưa đủ sâu cho production.
- Trace schema RAG còn mỏng; thiếu TTFT, feedback loop, privacy/redaction/sampling và tool comparison rõ.
- Chưa có code gần production cho structured logs, OpenTelemetry spans, Prometheus metrics và feedback endpoint.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung logs/metrics/traces, RAG trace schema, event catalog, token usage, cost/request, TTFT, error taxonomy và feedback workflow.
- Thêm code gần production với FastAPI, structured JSON logs, OpenTelemetry, Prometheus histograms/counters và feedback endpoint.
- Thêm comparison Langfuse, LangSmith, OpenTelemetry, Prometheus/Grafana, ELK/OpenSearch và custom trace store.
- Thêm privacy, redaction, sampling, retention, access control, dashboard panels, alert rules, incident runbook và lab instrument RAG pipeline.

### Day 45: Cost Optimization

Files:

- `lessions/day-45-cost-optimization/lession.md`
- `lessions/day-45-cost-optimization/document.md`
- `lessions/day-45-cost-optimization/exercise.md`
- `lessions/day-45-cost-optimization.md`

Review findings:

- File cũ là file phẳng, chưa có dấu và còn tóm tắt.
- Thiếu runbook/script tính cost từ trace logs, budget/quota/degrade mode đầy đủ và tách lesson/document/exercise.
- Các phần semantic cache, model routing, Batch API, distillation và production readiness chưa đủ sâu.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung cost model toàn pipeline: retrieval, embedding, rerank, context, generation, retry, eval, observability và infra.
- Thêm token budget, prompt caching, Redis semantic caching, model routing, context compression, chunk pruning, Batch API và distillation overview.
- Thêm budget/quota/degrade mode, rollback feature flags, cost spike runbook và dashboard/alert guidance.
- Thêm pseudo-code gần production để tính cost từ trace JSONL, pricing config và exercise cost plan cho 1k/10k/100k requests/day.

## 4. Verification

Main agent đã chạy các kiểm tra sau:

- `find lessions -maxdepth 2` kiểm tra đủ folder/file Day 41-45.
- `wc -l` cho 20 file Day 41-45: tổng 9.762 dòng.
- `rg` kiểm tra heading và keyword bắt buộc theo từng bài:
  - Day 41: MLflow, dataset lineage, Model Registry, aliases, `candidate`, `champion`, rollback, reproducibility, security, cost, production readiness.
  - Day 42: FastAPI, Pydantic, SSE, timeout, rate limit, concurrency limit, batching, BentoML, TorchServe, Triton, vLLM, TGI, production readiness.
  - Day 43: Dockerfile, Docker Compose, `.env.example`, Kubernetes, `nodeSelector`, taints/tolerations, `nvidia-device-plugin`, `nvidia.com/gpu`, Helm, KServe, Ray Serve, rollback.
  - Day 44: logs, metrics, traces, trace schema, TTFT, token usage, cost/request, feedback, Langfuse, LangSmith, OpenTelemetry, Prometheus/Grafana, ELK/OpenSearch, redaction/sampling.
  - Day 45: cost model, token budget, prompt caching, semantic cache, Redis, model routing, context compression, chunk pruning, Batch API, distillation, quota/degrade mode, trace cost script.
- `rg` kiểm tra placeholder dạng `TODO`, `FIXME`, `TBD`, `...` còn sót: pass sau khi main agent sửa các placeholder trong Day 42/44/45.
- Script kiểm tra fenced code balance cho 20 Markdown files: pass.
- Script compile 49 fenced `python` blocks trong folder Day 41-45: pass.
- `perl` kiểm tra trailing whitespace cho 20 file Day 41-45: pass.
- `git diff --check -- ...` trong phạm vi Day 41-45: pass.

Subagents cũng đã báo các kiểm tra riêng:

- Day 41 dùng Context7/official MLflow docs, kiểm tra aliases/tags và `git diff --check`.
- Day 42 dùng Context7 cho FastAPI/Pydantic/streaming, kiểm tra requirement keywords và whitespace.
- Day 43 đối chiếu official docs Docker/Kubernetes/NVIDIA/KServe/Ray và kiểm tra code fence/whitespace.
- Day 44 dùng Context7 cho OpenTelemetry Python và Prometheus Python client, kiểm tra code fence/whitespace.
- Day 45 đối chiếu official OpenAI Prompt Caching và Batch API docs, compile Python code block tính cost từ trace logs.

## 5. Rủi Ro Còn Lại

- Chưa chạy end-to-end các labs vì cần dependency/service ngoài repo như MLflow server, FastAPI app thật, Docker daemon, Kubernetes cluster, GPU node, Prometheus/Grafana, Redis, vector DB hoặc provider API key.
- Day 41 examples cần cài `mlflow`, model training dependencies và artifact store thật để chạy đầy đủ.
- Day 42 code serving là reference trong Markdown; production thật cần tách thành source files, CI tests, Redis/API Gateway rate limit và runtime thật.
- Day 43 manifests là template gần production; trước khi deploy thật cần chỉnh image registry, ingress, TLS, secret manager, resource sizing, backup/restore và cluster policy.
- Day 44 observability examples cần backend trace store/exporter thật và redaction test tự động trước public production.
- Day 45 pricing/caching/Batch API behavior phụ thuộc provider và có thể thay đổi; production code phải đọc pricing config/version và đối chiếu billing thật.
- Worktree trước khi làm đã có nhiều thay đổi ở các bài trước và checklist; main/subagents không revert thay đổi ngoài phạm vi.

## 6. Kết Luận

Day 41-45 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance/cost/security concern, code/config gần production và câu trả lời production readiness cho từng bài. Phase 6 hiện đã có chuỗi MLOps & Production AI liền mạch hơn từ tracking/registry, serving, deployment, observability đến cost optimization.

---

# Review And Fixed Checklist - Day 46 Đến Day 50

Ngày tổng hợp: 2026-05-10

Phạm vi: review và sửa 5 bài học cuối của Phase 6 và Phase 7 theo `review-and-fixed-task.md`: Guardrails, LLM Testing/CI, Capstone Backend/API, UI/Monitoring/Evaluation Report và Portfolio.

## 1. Quy Trình Đã Thực Hiện

- [x] Đã đọc plan khóa học: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`.
- [x] Đã đọc yêu cầu review/fix: `review-and-fixed-task.md`.
- [x] Đã đọc danh sách bài học hiện có trong `lessions/`.
- [x] Đã chia việc thành 5 bài độc lập: Day 46, Day 47, Day 48, Day 49, Day 50.
- [x] Đã spawn 5 subagents theo yêu cầu quy trình.
- [x] Các subagents đều bị lỗi do platform usage limit trước khi trả kết quả usable; main agent đã đóng agents lỗi và trực tiếp review/fix cả 5 bài để không bỏ dở deliverables.
- [x] Main agent đã dùng Context7 cho FastAPI, Pydantic và pydantic-settings khi bổ sung code/API example.
- [x] Main agent đã kiểm tra cấu trúc, heading, keyword bắt buộc, placeholder, fenced code balance, Python snippet syntax và whitespace trong phạm vi Day 46-50.
- [x] Main agent đã tổng hợp kết quả và cập nhật checklist này.

## 2. Checklist Tổng

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Mỗi bài có folder riêng | Done | Đã tạo folder riêng cho Day 46-50 trong `lessions/`. |
| Mỗi folder có `lession.md` | Done | Giữ đúng tên file theo yêu cầu task: `lession.md`. |
| Có tách `document.md` | Done | Cả 5 bài đều có tài liệu tham khảo, template, checklist hoặc review rubric riêng. |
| Có tách `exercise.md` | Done | Cả 5 bài đều có bài tập/lab riêng. |
| File phẳng cũ trỏ về folder mới | Done | `lessions/day-46...md` đến `lessions/day-50...md` đã thành trang điều hướng. |
| Tiếng Việt có dấu | Done | Nội dung mới và trang điều hướng đã được viết lại có dấu; thuật ngữ chuyên ngành English được giữ lại. |
| Giải thích từ cơ bản đến chi tiết | Done | Mỗi bài có TL;DR, workflow, decision table, template hoặc checklist. |
| Ưu tiên thực hành | Done | Mỗi bài có exercise gắn với capstone RAG/LLM production-style. |
| Có trade-off theo context | Done | Có trade-off về guardrails, eval strategy, backend architecture, UI/monitoring và portfolio public scope. |
| Có best solution theo context | Done | Có best solution cho capstone guardrails, CI eval, backend/API, monitoring/report và portfolio packaging. |
| Có performance concern | Done | Có latency, cost, p95, retry, rerank top-k, eval cost, UI monitoring và capacity notes. |
| Code/API example gần production | Done | Có Pydantic validators, PII redaction, eval metrics, FastAPI schema/API skeleton, TypeScript API contract và config template. |
| Trả lời câu hỏi production | Done | Mỗi bài có mục trả lời "Dùng được trong production không? Nếu có thì cần điều kiện gì?" |
| Context7 khi dùng library docs | Done | Đã dùng Context7 cho FastAPI, Pydantic và pydantic-settings. |

## 3. Kết Quả Theo Bài

### Day 46: Guardrails

Files:

- `lessions/day-46-guardrails/lession.md`
- `lessions/day-46-guardrails/document.md`
- `lessions/day-46-guardrails/exercise.md`
- `lessions/day-46-guardrails.md`

Review findings:

- File cũ là file phẳng, tiếng Việt không dấu và chưa tách document/exercise.
- Nội dung đúng hướng nhưng cần step-by-step hơn về threat model, policy layer, citation validation, PII redaction và prompt injection defense.
- Code example cũ chưa đủ gần production để validate schema/citation hoặc redact logs.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung threat model cho LLM/RAG app, policy matrix, output validation bằng Pydantic, citation guardrail, PII redaction, prompt boundary và tooling overview.
- Thêm performance/reliability notes cho classifier, LLM repair, citation validation, PII detection và LLM-as-judge.
- Thêm document release checklist, red-team test set, prompt template skeleton, metrics và tool selection.
- Thêm exercise implement PII redaction, schema/citation validation, ACL context filter và red-team suite.

### Day 47: LLM Testing, Golden Set, CI/CD Cho Prompt/RAG

Files:

- `lessions/day-47-llm-testing-golden-set-cicd-prompt-rag/lession.md`
- `lessions/day-47-llm-testing-golden-set-cicd-prompt-rag/document.md`
- `lessions/day-47-llm-testing-golden-set-cicd-prompt-rag/exercise.md`
- `lessions/day-47-llm-testing-golden-set-cicd-prompt-rag.md`

Review findings:

- File cũ là outline tiếng Việt không dấu.
- Thiếu phân tầng unit/retrieval/generation/guardrail/system eval.
- Thiếu schema golden set, threshold gate, report template, CI strategy và failure triage chi tiết.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung golden set schema, phân bổ 30 cases, retrieval metrics `Hit@K`, `Recall@K`, `MRR@K`, generation rubric và snapshot testing guidance.
- Thêm CI/CD workflow cho PR, nightly, release, canary, A/B testing và feedback loop.
- Thêm threshold config, eval report template, failure triage và anti-patterns.
- Exercise yêu cầu tạo `golden_set.jsonl`, metric functions, eval runner, threshold gate và CI workflow.

### Day 48: Capstone Architecture Review + Backend/API

Files:

- `lessions/day-48-capstone-architecture-review-backend-api/lession.md`
- `lessions/day-48-capstone-architecture-review-backend-api/document.md`
- `lessions/day-48-capstone-architecture-review-backend-api/exercise.md`
- `lessions/day-48-capstone-architecture-review-backend-api.md`

Review findings:

- File cũ có ý đúng nhưng vẫn là file phẳng, không dấu và chưa đủ API contract/code skeleton.
- Thiếu config boundary, `.env.example`, trace schema, readiness gate và production conditions.
- Cần nối logic với Day 46 guardrails và Day 47 eval trước khi sang UI Day 49.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung capstone scope, non-goals, architecture text diagram, repo structure và boundary giữa API/RAG core/LLM/eval/observability.
- Thêm endpoint contract cho health, ready, upload, ingest, documents, query, feedback, traces và eval.
- Thêm FastAPI/Pydantic skeleton, pydantic-settings config mẫu, ingestion/query pipeline, fallback strategy, trade-off matrix và readiness gate.
- Exercise yêu cầu tạo scope, architecture, API schemas, backend skeleton, `.env.example` và Day 48 readiness checklist.

### Day 49: UI, Monitoring, Evaluation Report

Files:

- `lessions/day-49-ui-monitoring-evaluation-report/lession.md`
- `lessions/day-49-ui-monitoring-evaluation-report/document.md`
- `lessions/day-49-ui-monitoring-evaluation-report/exercise.md`
- `lessions/day-49-ui-monitoring-evaluation-report.md`

Review findings:

- File cũ còn tiếng Việt không dấu và chưa tách folder.
- UI scope, citation experience, feedback loop, monitoring catalog và evaluation report chưa đủ cụ thể.
- Thiếu release decision và production UI/security conditions.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung Chat UI contract, citation panel behavior, feedback endpoint/payload, structured log sample và monitoring metrics.
- Thêm dashboard vs Markdown report trade-off, evaluation report template, release decision rules và TypeScript API contract.
- Bổ sung production notes về ACL cho citation/source excerpt, trace detail role, PII-safe feedback và monitoring alerts.
- Exercise yêu cầu tạo chat UI, citation panel, feedback form, trace summary, monitoring summary, evaluation report và release decision.

### Day 50: README, Demo, Blog, CV/LinkedIn

Files:

- `lessions/day-50-readme-demo-blog-cv-linkedin/lession.md`
- `lessions/day-50-readme-demo-blog-cv-linkedin/document.md`
- `lessions/day-50-readme-demo-blog-cv-linkedin/exercise.md`
- `lessions/day-50-readme-demo-blog-cv-linkedin.md`

Review findings:

- File cũ đã đúng chủ đề nhưng còn tiếng Việt không dấu và chưa tách document/exercise.
- README/demo/blog/CV/LinkedIn cần template đủ dùng ngay, không chỉ liệt kê.
- Cần nhấn mạnh portfolio honesty, public repo safety, security/cost/eval và không claim production quá mức.

Đã sửa:

- Tách thành folder riêng và chuyển root file thành trang điều hướng.
- Bổ sung portfolio package mental model, README outline/template, demo video script 3-5 phút, blog outline, CV bullets và LinkedIn post mẫu.
- Thêm public repo safety checklist, demo query set, interview talking points, positioning guidance và final review rubric.
- Thêm trade-off khi public portfolio, production conditions và wording không phóng đại.
- Exercise yêu cầu viết README final, demo script, blog outline, CV bullets, LinkedIn post, repo audit và final portfolio review.

## 4. Verification

Main agent đã chạy các kiểm tra sau:

- `find` kiểm tra đủ folder/file Day 46-50.
- `wc -l` cho 20 file Day 46-50: tổng 3.589 dòng.
- `rg` kiểm tra heading và keyword bắt buộc:
  - Day 46: Guardrails, Pydantic, policy, PII, red-team, citation, production readiness.
  - Day 47: Golden set, eval metrics, CI/CD, threshold, canary, production readiness.
  - Day 48: FastAPI, Pydantic, backend/API, ingestion, query, config, trade-off, production readiness.
  - Day 49: UI, citation, feedback, monitoring, evaluation report, release decision, production readiness.
  - Day 50: README, demo, blog, CV, LinkedIn, guardrails, evaluation, portfolio, production readiness.
- `rg` kiểm tra placeholder dạng `TODO`, `FIXME`, `TBD`, `[link]`, `replace-me` và template bracket còn sót: pass sau khi main agent sửa các placeholder không cần thiết.
- Script kiểm tra fenced code balance cho 20 Markdown files: pass.
- Script compile 16 fenced `python` blocks trong folder Day 46-50: pass.
- `perl` kiểm tra trailing whitespace cho 20 file Day 46-50: pass.
- `git diff --check -- ...` trong phạm vi Day 46-50: pass trước khi cập nhật checklist; checklist sẽ được kiểm tra lại cùng final audit.

Context7 đã dùng:

- `/websites/fastapi_tiangolo`
- `/websites/pydantic_dev_validation`
- `/pydantic/pydantic-settings`

## 5. Rủi Ro Còn Lại

- Không có subagent review findings độc lập vì cả 5 subagents đều lỗi usage limit trước khi thực hiện; main agent đã thực hiện review/fix trực tiếp và ghi rõ ngoại lệ này.
- Chưa chạy end-to-end các labs vì cần capstone repo/app thật, Vector DB, model provider/API key, frontend runtime hoặc Docker Compose project hoàn chỉnh.
- FastAPI/Pydantic/TypeScript examples là reference trong Markdown; production thật cần tách thành source files, unit tests, auth, rate limit và deployment pipeline.
- Day 46 guardrail examples là deterministic baseline; regulated production cần classifier/eval/human escalation và privacy review chặt hơn.
- Day 47 eval runner là skeleton; production thật cần artifact storage, flaky test handling, judge calibration và baseline comparison.
- Day 48-50 là capstone blueprint/portfolio package; để public production thật cần auth/SSO, secret management, security review, load test, backup/restore và monitoring/alerting.

## 6. Kết Luận

Day 46-50 đã được review và sửa theo yêu cầu: có dấu, đầy đủ hơn, tách folder/file rõ ràng, có thực hành, trade-off, performance/cost/security concern, code/API/template gần production và câu trả lời production readiness cho từng bài. Chuỗi cuối khóa hiện hoàn chỉnh hơn từ guardrails, LLM testing/CI, capstone backend/API, UI/monitoring/evaluation report đến README/demo/blog/CV/LinkedIn portfolio.
