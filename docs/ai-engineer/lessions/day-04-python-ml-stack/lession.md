# Day 4: Python ML Stack

## Mục tiêu

Sau bài này, bạn cần làm được các việc sau:

- Dùng NumPy để hiểu `ndarray`, `shape`, `dtype`, broadcasting và vectorization ở mức đủ để debug ML code.
- Dùng Pandas cho EDA, data cleaning, `groupby`, `merge`, missing value analysis và kiểm tra schema dữ liệu.
- Dùng scikit-learn `Pipeline` và `ColumnTransformer` để đóng gói preprocessing cùng model, tránh train-serving skew.
- Train và so sánh Logistic Regression, Random Forest, Gradient Boosting trên Titanic-style dataset.
- Lưu pipeline artifact kèm metadata, rồi viết inference function có input validation.

## TL;DR

Python ML stack phổ biến gồm NumPy cho numerical compute, Pandas cho data wrangling, scikit-learn cho training pipeline, Matplotlib/Seaborn cho visualization và joblib cho artifact nhỏ-vừa. Với Senior SE, hãy xem ML pipeline như một service build artifact: input có schema, transform có version, model có metrics, artifact có metadata và inference có contract rõ ràng. Notebook rất tốt cho exploration, nhưng production cần logic repeatable trong script/package, test được và có monitoring.

## 1. Bức tranh tổng thể

Một ML workflow tabular cơ bản thường đi qua các bước:

```text
raw data
  -> data loading
  -> schema check
  -> EDA
  -> train/test split
  -> preprocessing
  -> model training
  -> evaluation
  -> artifact packaging
  -> batch/API inference
  -> monitoring
```

Map về tư duy software engineering:

| ML stack | SE analogy | Điều cần kiểm soát |
|---|---|---|
| NumPy array | Binary buffer/vector payload | Shape, dtype, memory layout |
| Pandas DataFrame | In-memory table/batch ETL | Column schema, null, join cardinality |
| scikit-learn transformer | Pure function có `fit/transform` | Fit chỉ trên train data |
| scikit-learn estimator | Business logic được học từ data | Params, random seed, metrics |
| Pipeline artifact | Deployable binary | Version, compatibility, rollback |
| Notebook | Spike/experiment document | Không phải source of truth duy nhất |

Best solution trong Phase 1: dùng Pandas + scikit-learn `Pipeline` cho tabular ML nhỏ-vừa, vì API đơn giản, ecosystem mạnh, dễ chuyển từ notebook sang script. Chưa cần Spark, MLflow hay feature store trừ khi dữ liệu lớn, team đông hoặc cần governance nghiêm ngặt.

## 2. NumPy: nền tảng của numerical compute

`ndarray` là mảng N chiều đồng nhất kiểu dữ liệu. Trong ML, dữ liệu thường có shape:

```text
X: (n_samples, n_features)
y: (n_samples,)
```

Ví dụ:

```python
import numpy as np

X = np.array(
    [
        [22, 7.25],
        [38, 71.28],
        [26, 7.92],
    ],
    dtype=np.float64,
)
w = np.array([0.03, 0.01])

scores = X @ w
print(X.shape)      # (3, 2)
print(X.dtype)      # float64
print(scores)       # vector score cho 3 rows
```

Điểm cần nhớ:

- `shape` là contract. Nếu training dùng 8 features mà inference đưa 7 features, kết quả phải fail sớm.
- `dtype` ảnh hưởng memory và tốc độ. `float64` chính xác hơn nhưng tốn memory hơn `float32`.
- Vectorization đẩy compute xuống native code, thường nhanh hơn Python loop rất nhiều.
- Broadcasting tiện nhưng dễ tạo bug nếu shape không rõ ràng.
- Slicing có thể tạo view chia sẻ memory; copy/view không rõ có thể gây mutation ngoài ý muốn.

Ví dụ broadcasting:

```python
X = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])
mean = X.mean(axis=0)
std = X.std(axis=0)
scaled = (X - mean) / std
```

Ở production, bạn hiếm khi tự scale bằng NumPy nếu dùng scikit-learn. Nhưng hiểu cơ chế này giúp debug `StandardScaler`, feature matrix và lỗi shape.

## 3. Pandas: data wrangling như batch ETL

Pandas `DataFrame` là bảng có index, column name và dtype. Với ML tabular, Pandas phù hợp cho:

- Inspect schema.
- Thống kê missing values.
- Tạo feature đơn giản.
- Join dữ liệu nguồn.
- EDA trước khi đóng gói preprocessing vào pipeline.

Các thao tác cốt lõi:

```python
import pandas as pd

df = pd.DataFrame(
    {
        "pclass": [3, 1, 3],
        "sex": ["male", "female", "female"],
        "age": [22.0, 38.0, None],
        "fare": [7.25, 71.28, 7.92],
        "survived": [0, 1, 1],
    }
)

selected = df[["pclass", "sex", "age"]]
adults = df[df["age"].fillna(0) >= 18]
survival_by_class = df.groupby("pclass")["survived"].agg(["count", "mean"])
missing_ratio = df.isna().mean().sort_values(ascending=False)
```

Map Pandas sang SQL:

| Pandas | SQL |
|---|---|
| `df[cols]` | `SELECT cols` |
| `df[df["age"] >= 18]` | `WHERE age >= 18` |
| `groupby().agg()` | `GROUP BY` |
| `merge()` | `JOIN` |
| `sort_values()` | `ORDER BY` |
| `drop_duplicates()` | `DISTINCT` |

Production concern:

- Pandas load data vào RAM. Nếu dataset lớn hơn memory, cân nhắc DuckDB, Polars, database query, Spark hoặc chunk processing.
- `object` dtype tốn memory và dễ lẫn kiểu. Với dữ liệu category, kiểm tra unique count và null ratio.
- Join có thể nhân bản dòng nếu key không unique. Luôn kiểm tra row count trước/sau `merge`.
- Không hard-code EDA transformation vào notebook rồi quên đưa vào training pipeline.

## 4. scikit-learn mental model

scikit-learn xoay quanh 3 interface chính:

```python
transformer.fit(X_train)
X_train_transformed = transformer.transform(X_train)
X_test_transformed = transformer.transform(X_test)

model.fit(X_train_transformed, y_train)
y_pred = model.predict(X_test_transformed)
```

`Pipeline` gộp các bước lại:

```text
raw DataFrame
  -> impute missing values
  -> scale numerical columns
  -> encode categorical columns
  -> classifier
```

Điểm cực kỳ quan trọng: các bước có học tham số từ dữ liệu như imputer, scaler, encoder phải `fit` trên train set, sau đó chỉ `transform` validation/test/production data. Nếu `fit` trên toàn bộ dataset trước khi split, bạn đã leak thông tin từ test set vào training.

## 5. ColumnTransformer cho dữ liệu mixed type

Dữ liệu business thường có numerical và categorical columns. Mỗi nhóm cần preprocessing khác nhau:

```python
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

numeric_features = ["age", "sibsp", "parch", "fare"]
categorical_features = ["pclass", "sex", "embarked"]

numeric_pipeline = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]
)

categorical_pipeline = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore")),
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_pipeline, numeric_features),
        ("cat", categorical_pipeline, categorical_features),
    ]
)
```

Vì sao `handle_unknown="ignore"` quan trọng? Production luôn có category mới: một cảng mới, plan mới, campaign mới, country code mới. Nếu encoder fail toàn bộ request vì category mới, service sẽ brittle. `ignore` giúp request vẫn chạy, nhưng bạn cần monitor category drift vì quality có thể giảm.

## 6. Notebook-to-production workflow

Notebook tốt cho:

- EDA nhanh.
- Plot distribution.
- So sánh hypothesis.
- Ghi chú reasoning.
- Demo kết quả.

Notebook không nên là production source duy nhất vì:

- Cell execution order dễ sai.
- Config và seed không rõ.
- Khó test tự động.
- Khó review diff.
- Artifact tạo ra không có metadata.

Workflow đề xuất:

```text
01_explore.ipynb
  -> ghi insight, plot, assumption

src/data.py
  -> load data, validate schema, split

src/features.py
  -> build preprocessing pipeline

src/train.py
  -> train, evaluate, save artifact

src/predict.py
  -> load artifact, validate request, predict

tests/
  -> schema test, prediction smoke test
```

Trong repo học này, bạn chưa cần tạo package đầy đủ ngay. Nhưng exercise sẽ mô phỏng các thành phần quan trọng bằng một script gần production.

## 7. Chọn model baseline

Với Titanic-style tabular classification, ba model hợp lý để so sánh:

| Model | Khi nên dùng | Điểm mạnh | Hạn chế |
|---|---|---|---|
| Logistic Regression | Baseline đầu tiên | Nhanh, dễ giải thích, ít overfit | Cần feature engineering cho quan hệ phi tuyến |
| Random Forest | Baseline tree mạnh | Bắt nonlinear pattern, ít preprocessing numerical hơn | Artifact lớn hơn, latency cao hơn linear model |
| HistGradientBoosting | Tabular mạnh, training nhanh | Hiệu quả với numeric pattern | Categorical vẫn cần encode, tuning cần cẩn thận |

Best solution theo context:

- Học nền tảng/need explainability: bắt đầu với Logistic Regression.
- Tabular data nhỏ-vừa và muốn quality tốt nhanh: thử Random Forest hoặc Gradient Boosting.
- Production latency rất thấp hoặc cần explainability cao: ưu tiên linear model hoặc tree nhỏ.
- Dataset lớn, feature cardinality cao: đo memory của one-hot; cân nhắc hashing, target encoding có kiểm soát hoặc model khác.

## Trade-offs

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Guidance cụ thể |
|---|---|---|---|
| Pandas | EDA, training batch nhỏ-vừa, dữ liệu fit RAM | Dataset quá RAM, realtime low-latency path | Dùng mặc định trong Day 4, nhưng không đưa Pandas-heavy transform vào hot path nếu latency nghiêm ngặt |
| NumPy vectorization | Compute lặp trên array lớn | Logic branch phức tạp per row | Ưu tiên vectorize feature computation thay vì Python loop |
| scikit-learn Pipeline | Preprocessing + model tabular | Deep learning training loop phức tạp | Mặc định dùng để tránh train-serving skew |
| OneHotEncoder | Categorical low/medium cardinality | Hàng chục nghìn category | Monitor feature explosion; dùng sparse output khi phù hợp |
| Random split | Data IID, không phụ thuộc thời gian | Time-series, user lifecycle, event stream | Với production có thời gian, dùng time-based split |
| joblib artifact | Internal artifact từ training trusted | Artifact không rõ nguồn | Không load artifact từ untrusted source |

## Best practices từ industry

1. Split data trước khi fit preprocessing để tránh leakage.
2. Luôn lưu preprocessing và model trong cùng một `Pipeline`.
3. Lưu metadata cạnh artifact: feature list, target, metrics, dataset source, package version, random seed.
4. Validate schema ở cả training và inference. Fail rõ ràng khi thiếu cột hoặc sai kiểu nghiêm trọng.
5. Log metrics không chỉ accuracy. Với classification, luôn xem precision, recall, F1 và ROC-AUC nếu có probability.
6. Pin dependency version cho artifact quan trọng vì pickle/joblib phụ thuộc Python và package version.
7. Không dùng notebook làm cron job production; chuyển sang script/package có CLI, config và test.

## Performance considerations

- Pandas giữ DataFrame trong RAM; `object` string column có overhead lớn. Dùng `df.info(memory_usage="deep")` để ước lượng tốt hơn.
- One-hot encoding có thể làm feature matrix phình mạnh. Nếu 1 triệu rows và 50.000 category, one-hot dense là không khả thi.
- Sparse matrix tiết kiệm memory cho one-hot/text, nhưng không phải model nào cũng xử lý sparse tối ưu như nhau.
- `n_jobs=-1` tăng throughput training/prediction với một số estimator, nhưng có thể tranh CPU với service khác.
- Batch prediction thường nhanh hơn single-row prediction vì giảm overhead Python.
- Scaling numerical features rất quan trọng với Logistic Regression/SVM/KNN, ít quan trọng hơn với tree-based models.

## Production concerns

### Data quality

- Missing value ratio tăng đột biến có thể là upstream pipeline bug.
- Category mới tăng nhanh là signal drift.
- Numeric range vượt xa training distribution cần alert.
- Duplicate key sau join có thể làm label distribution sai.

### Reliability

- Training script phải deterministic ở mức hợp lý: set `random_state`, lưu split strategy, lưu config.
- Artifact cần versioning và rollback.
- Inference phải trả lỗi rõ ràng cho invalid payload, không silently reorder/missing feature.

### Security

- `pickle`/`joblib` có thể thực thi code khi load object độc hại. Chỉ load artifact do pipeline build đáng tin cậy tạo ra.
- Không log raw PII trong prediction logs. Với Titanic exercise không có PII thật, nhưng production customer data thường có.

### Observability

Tối thiểu cần log:

- Model version.
- Input schema version.
- Prediction latency.
- Missing/unknown category rate.
- Prediction distribution.
- Business outcome khi label về sau có sẵn.

## Dùng được trong production không? Nếu có thì cần điều kiện gì?

Có, stack Pandas + scikit-learn dùng được trong production cho nhiều bài toán tabular batch hoặc low/medium throughput API, nếu thỏa các điều kiện sau:

- Dataset và feature transformation fit với memory/latency budget.
- Training và inference dùng chung `Pipeline` artifact.
- Có schema validation, dependency pinning, artifact versioning và rollback.
- Artifact chỉ được load từ nguồn trusted.
- Có monitoring cho data drift, missing values, prediction distribution, latency và model quality.
- Có quy trình retraining/evaluation trước khi promote model mới.

Không nên dùng nguyên xi nếu workload là streaming real-time cực lớn, feature join phức tạp cần feature store, model deep learning, hoặc latency SLA rất thấp mà Pandas overhead không chấp nhận được. Khi đó cần thiết kế lại serving path bằng feature service, compiled transform, online store hoặc framework serving chuyên biệt.

## Hands-on trong 60-90 phút

Làm bài trong [exercise.md](./exercise.md). Output tối thiểu:

- Train được 3 models trên Titanic hoặc fallback dataset.
- Có bảng metrics.
- Lưu được `model.joblib` và `metadata.json`.
- Load lại artifact và predict thử một payload.
- Trả lời câu hỏi production readiness ở cuối exercise.

## Tự kiểm tra

1. Vì sao `fit_transform` preprocessing trên toàn bộ dataset trước khi split là data leakage?
2. `Pipeline` khác gì so với việc gọi từng bước thủ công trong notebook?
3. Khi nào Pandas không còn phù hợp cho training hoặc serving?
4. `OneHotEncoder(handle_unknown="ignore")` giải quyết vấn đề gì và không giải quyết vấn đề gì?
5. Vì sao cần lưu feature list và package version trong artifact metadata?
6. Accuracy cao có đủ để chọn model không? Vì sao?
7. Risk bảo mật chính của joblib/pickle artifact là gì?

## Checklist hoàn thành hôm nay

- [ ] Hiểu `ndarray`, `shape`, `dtype`, broadcasting và vectorization.
- [ ] Dùng được Pandas select/filter/groupby/merge/missing value analysis.
- [ ] Hiểu `Estimator`, `Transformer`, `Pipeline`, `ColumnTransformer`.
- [ ] Tách được numerical và categorical preprocessing.
- [ ] Train được ít nhất 3 model bằng cùng preprocessing contract.
- [ ] Lưu và load pipeline artifact.
- [ ] Viết inference function có schema validation.
- [ ] Trả lời được câu hỏi production readiness.

## Tài liệu tham khảo

- NumPy documentation: `ndarray`, broadcasting, matrix multiplication, views vs copies.
- Pandas documentation: DataFrame selection, boolean indexing, groupby aggregation, `info(memory_usage=...)`.
- scikit-learn documentation: `Pipeline`, `ColumnTransformer`, `OneHotEncoder`, `fetch_openml`, model persistence.
- Keywords: `train-serving skew`, `data leakage`, `model artifact metadata`, `categorical drift`.
