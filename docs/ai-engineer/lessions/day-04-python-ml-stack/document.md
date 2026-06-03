# Day 4 Document: Python ML Stack Reference

File này là reference nhanh để tra trong lúc làm exercise. Bài học chính nằm ở [lession.md](./lession.md), bài thực hành nằm ở [exercise.md](./exercise.md).

## 1. NumPy reference

### `ndarray`

`ndarray` là container N chiều, có `shape`, `dtype`, `ndim`, `size`.

```python
import numpy as np

a = np.arange(15).reshape(3, 5)
print(a.shape)      # (3, 5)
print(a.ndim)       # 2
print(a.dtype.name) # int64 hoặc int32 tùy platform
print(a.size)       # 15
```

Trong ML:

```text
X_train.shape = (số dòng train, số feature)
y_train.shape = (số dòng train,)
```

Nếu shape sai, hãy debug ngay tại boundary của function. Đừng để shape sai đi sâu vào model.

### Matrix multiplication

```python
A = np.array([[1, 2], [3, 4]])
B = np.array([[5, 6], [7, 8]])
v = np.array([1, 2])

print(A @ B)    # matrix multiplication
print(A @ v)    # matrix-vector multiplication
print(A * B)    # element-wise multiplication
```

Rule thực tế:

- Dùng `@` cho linear algebra.
- Dùng `*` cho element-wise operation.
- Luôn kiểm tra shape khi kết quả bất ngờ.

### Broadcasting

```python
X = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])
mean = X.mean(axis=0)
scaled = X - mean
```

`mean` có shape `(2,)` được broadcast qua 3 rows. Broadcasting rất mạnh nhưng cần viết code rõ ràng, tránh “may mắn chạy được”.

### View vs copy

```python
arr = np.array([[1, 2, 3], [4, 5, 6]])
view = arr[0, :]
print(np.shares_memory(arr, view))  # True trong trường hợp này
```

Production concern: mutation trên view có thể làm thay đổi array gốc. Nếu cần tách độc lập, dùng `.copy()`.

## 2. Pandas reference

### Inspect DataFrame

```python
print(df.head())
print(df.info(memory_usage="deep"))
print(df.describe(include="all"))
print(df.isna().mean().sort_values(ascending=False))
```

Checklist khi nhận dataset mới:

- Có đủ columns expected không?
- Target có null không?
- Dtype có hợp lý không?
- Missing ratio column nào cao bất thường?
- Label distribution có quá lệch không?
- Có duplicate row/key không?

### Select/filter/groupby

```python
cols = ["pclass", "sex", "age", "fare"]
X = df[cols]

adults = df[df["age"].fillna(0) >= 18]

summary = (
    df.groupby("pclass")["survived"]
    .agg(["count", "mean"])
    .sort_values("mean", ascending=False)
)
```

### Merge

```python
features = passengers.merge(tickets, on="ticket_id", how="left", validate="many_to_one")
```

Nên dùng `validate` khi biết relationship:

| Relationship | `validate` |
|---|---|
| Mỗi bên unique key | `one_to_one` |
| Left nhiều, right unique | `many_to_one` |
| Left unique, right nhiều | `one_to_many` |
| Cả hai có duplicate | `many_to_many` |

Nếu join làm row count tăng ngoài dự kiến, model có thể học từ dữ liệu bị duplicate sai.

### Missing values

Trong EDA, bạn có thể inspect/fill tạm:

```python
df["age_preview"] = df["age"].fillna(df["age"].median())
```

Trong training production-style, nên đưa imputation vào scikit-learn `Pipeline`, không fill thủ công trên toàn dataset trước split.

## 3. scikit-learn reference

### Estimator API

```python
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
y_score = model.predict_proba(X_test)[:, 1]
```

### Transformer API

```python
transformer.fit(X_train)
X_train_t = transformer.transform(X_train)
X_test_t = transformer.transform(X_test)
```

Không gọi `fit` trên test data.

### Pipeline

```python
from sklearn.pipeline import Pipeline

pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model),
    ]
)

pipeline.fit(X_train, y_train)
pipeline.predict(X_test)
```

Pipeline giúp:

- Đóng gói preprocessing và model.
- Tránh quên bước transform ở inference.
- Giảm train-serving skew.
- Dễ save/load artifact.

### ColumnTransformer

```python
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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

### `OneHotEncoder(handle_unknown="ignore")`

Ý nghĩa:

- Khi inference gặp category chưa thấy trong training, encoder không throw error.
- Các cột one-hot tương ứng category đã biết sẽ là 0.

Trade-off:

- Tăng robustness của API.
- Nhưng category mới không có signal riêng, quality có thể giảm.
- Cần monitor unknown/category drift.

### `train_test_split`

```python
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y,
)
```

`stratify=y` giữ tỷ lệ class gần giống giữa train/test cho classification. Không dùng random split cho time-series hoặc dữ liệu có leakage theo thời gian.

### Metrics

```python
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

metrics = {
    "accuracy": accuracy_score(y_test, y_pred),
    "precision": precision_score(y_test, y_pred, zero_division=0),
    "recall": recall_score(y_test, y_pred, zero_division=0),
    "f1": f1_score(y_test, y_pred, zero_division=0),
    "roc_auc": roc_auc_score(y_test, y_score),
}
```

Guidance:

- Accuracy dễ hiểu nhưng nguy hiểm khi class imbalance.
- Precision quan trọng khi false positive đắt.
- Recall quan trọng khi false negative đắt.
- F1 cân bằng precision/recall.
- ROC-AUC hữu ích khi cần so sánh ranking/probability quality.

## 4. Model artifact với joblib

```python
import joblib

joblib.dump(pipeline, "model.joblib")
loaded = joblib.load("model.joblib")
```

Nên lưu thêm metadata:

```json
{
  "model_name": "logistic_regression",
  "schema_version": "day4-titanic-v1",
  "numeric_features": ["age", "sibsp", "parch", "fare", "family_size", "is_alone"],
  "categorical_features": ["pclass", "sex", "embarked"],
  "target": "survived",
  "metrics": {
    "roc_auc": 0.84,
    "f1": 0.76
  },
  "random_state": 42
}
```

Security rule: chỉ load `joblib`/pickle artifact từ nguồn trusted. Không nhận file model do user upload rồi `joblib.load` trực tiếp.

## 5. Production readiness checklist

- [ ] Có schema validation cho input.
- [ ] Có split strategy phù hợp business.
- [ ] Preprocessing và model nằm chung pipeline.
- [ ] Có baseline và ít nhất một model so sánh.
- [ ] Có metrics phù hợp business cost.
- [ ] Có artifact metadata.
- [ ] Có dependency version hoặc lockfile.
- [ ] Có smoke test load artifact và predict.
- [ ] Có monitoring plan cho missing values, category drift, prediction drift và latency.
- [ ] Có rollback plan khi model mới tệ hơn.

## 6. Context7 docs đã tham khảo

- `/numpy/numpy`: `ndarray`, `shape`, `dtype`, matrix multiplication, views/copies.
- `/websites/pandas_pydata`: DataFrame boolean indexing, groupby aggregate, `info()`, missing value handling.
- `/websites/scikit-learn_stable`: `Pipeline`, `ColumnTransformer`, `OneHotEncoder(handle_unknown="ignore")`, examples for preprocessing pipelines.
