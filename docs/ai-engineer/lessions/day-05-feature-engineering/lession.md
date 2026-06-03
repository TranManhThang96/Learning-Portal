# Day 5: Feature Engineering

## Mục Tiêu

Sau Day 3, bạn đã biết train/validation/test split, overfitting, baseline model và bias-variance. Sau Day 4, bạn đã dùng NumPy, Pandas và scikit-learn để train model cơ bản. Day 5 nối hai bài đó lại bằng phần hay bị xem nhẹ nhất trong ML production: biến raw data thành feature ổn định, có thể kiểm thử, có thể deploy và không leak dữ liệu tương lai.

Kết thúc bài này, bạn cần làm được:

- Thiết kế feature cho numerical, categorical, text và datetime data.
- Dùng `Pipeline` và `ColumnTransformer` để giữ logic preprocessing nhất quán giữa training/inference.
- Chọn imputation, scaling, encoding và text vectorization theo trade-off cụ thể.
- Nhận diện data leakage, train-serving skew, schema drift và point-in-time bug.
- Viết được validation checks trước khi gọi model.
- Trả lời rõ: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## TL;DR

Feature engineering là lớp contract giữa data system và model. Với Senior SE, hãy nghĩ feature như API schema: tên cột, type, nullability, semantics và thời điểm dữ liệu đều phải rõ. Model tốt không cứu được feature sai thời điểm, feature bị leak, category drift hoặc preprocessing khác nhau giữa train và serve.

Best default cho bài toán tabular ở giai đoạn đầu:

```text
Split đúng thời gian hoặc stratified split
-> fit preprocessing chỉ trên train
-> ColumnTransformer theo nhóm feature
-> Pipeline(preprocess, model)
-> validate schema trước inference
-> log missing rate/cardinality/distribution
```

## 1. Feature Là Gì?

Raw data là dữ liệu nghiệp vụ. Feature là biểu diễn mà model có thể học.

Ví dụ churn prediction:

| Raw data | Feature có thể dùng | Ghi chú production |
|---|---|---|
| `signup_at` | `account_age_days` | Tính tại `prediction_time`, không dùng thời gian hiện tại ngầm định trong training |
| `last_login_at` | `days_since_last_login` | Nếu missing có thể nghĩa là chưa từng login |
| `monthly_charges` | `monthly_charges_scaled`, `log_monthly_charges` | Cần xử lý outlier và missing |
| `contract_type` | one-hot columns | Cần handle category mới ở inference |
| `support_ticket_text` | TF-IDF vector | Cần lưu vocabulary cùng model |
| `ticket_count` | `ticket_count_30d` | Chỉ tính từ event trước thời điểm dự đoán |

Map với backend:

| Backend concept | ML equivalent |
|---|---|
| API request schema | Feature schema |
| Contract test | Input validation và schema validation |
| ETL job | Feature generation job |
| Cache invalidation | Feature freshness |
| Backward compatibility | Feature versioning |
| Observability | Drift, missing rate, cardinality, outlier monitoring |

## 2. Nguyên Tắc Không Leak Dữ Liệu

Data leakage xảy ra khi feature chứa thông tin mà tại thời điểm prediction thật sự chưa thể biết. Đây là lỗi nghiêm trọng hơn chọn sai model, vì offline metrics sẽ đẹp giả.

Ba dạng leakage hay gặp:

1. Fit preprocessing trên toàn bộ dataset trước khi split.
   Ví dụ fit `StandardScaler`, `OneHotEncoder`, `TfidfVectorizer`, imputer trên cả train và test.
2. Dùng future information.
   Ví dụ predict churn ngày 2026-05-01 nhưng dùng `ticket_count_30d` tính cả ticket ngày 2026-05-10.
3. Dùng target proxy.
   Ví dụ feature `cancellation_ticket_created` xuất hiện sau khi khách đã quyết định churn.

Rule thực tế:

```text
Mọi transformer có .fit() phải fit trên training data.
Mọi aggregate feature phải có cutoff time.
Mọi join phải chứng minh point-in-time correctness.
```

## 3. Numerical Features

Numerical features thường gặp vấn đề: missing value, scale lệch lớn, outlier, distribution skewed.

### Scaling

| Kỹ thuật | Khi nên dùng | Trade-off |
|---|---|---|
| `StandardScaler` | Logistic Regression, SVM, KNN, Neural Network; data tương đối ổn | Nhạy với outlier |
| `MinMaxScaler` | Feature cần nằm trong khoảng cố định `[0, 1]` | Rất nhạy với outlier |
| `RobustScaler` | Revenue, transaction amount, latency, usage count có outlier | Có thể kém hơn nếu data sạch và gần normal |
| Không scale | Tree-based model như Random Forest, Gradient Boosting | Nếu đổi sang linear model có thể phải sửa pipeline |

Default production hợp lý cho churn tabular bằng Logistic Regression: median imputation + missing indicator + `RobustScaler`.

```python
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

numeric_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
    ("scaler", RobustScaler()),
])
```

### Log Transform

Dùng cho feature lệch phải như revenue, charge, request count, session duration.

```python
import numpy as np

df["log_monthly_charges"] = np.log1p(df["monthly_charges"])
```

Trade-off: log transform giảm tác động outlier nhưng làm feature khó giải thích hơn với stakeholder không quen toán.

### Binning

Ví dụ:

```text
days_since_last_login:
0-7     -> active
8-30    -> cooling
31-90   -> at_risk
>90     -> dormant
```

Binning hữu ích khi business threshold rõ, nhưng mất thông tin liên tục. Không nên binning chỉ vì model chưa tốt; trước tiên hãy kiểm tra leakage, missing và baseline.

## 4. Categorical Features

### One-hot Encoding

One-hot an toàn cho category không có thứ tự và cardinality thấp-vừa.

```python
from sklearn.preprocessing import OneHotEncoder

encoder = OneHotEncoder(
    handle_unknown="ignore",
    min_frequency=10,
)
```

`handle_unknown="ignore"` giúp inference không crash khi gặp category mới, nhưng category mới sẽ thành vector toàn 0 trong nhóm đó. Với production, vẫn phải log unknown rate.

`min_frequency` hoặc grouping infrequent categories giúp giảm số chiều khi có nhiều category hiếm.

### Label/Ordinal Encoding

Chỉ dùng khi category có thứ tự thật:

```text
free < basic < pro < enterprise
```

Không nên encode `payment_method = credit_card, bank_transfer, wallet` thành `0, 1, 2` cho Logistic Regression, vì model sẽ hiểu nhầm khoảng cách số học.

### Target Encoding

Target encoding thay category bằng thống kê target lịch sử, ví dụ `city -> churn_rate`. Nó mạnh với high-cardinality feature như city, merchant, campaign, device model, nhưng rất dễ leakage.

Điều kiện tối thiểu nếu dùng target encoding:

- Tính encoding trong cross-validation fold, không dùng toàn bộ train trực tiếp cho từng row.
- Có smoothing để category ít data không quá cực đoan.
- Có fallback cho category mới.
- Không dùng test set để tính encoding.

Trong bài Day 5, best solution là chưa dùng target encoding nếu chưa có test leakage chặt. Hãy dùng one-hot với grouping infrequent trước.

## 5. Text Features: TF-IDF

TF-IDF là baseline text quan trọng trước khi chuyển sang Transformer. Nó không hiểu semantic sâu, nhưng nhanh, rẻ, dễ debug và thường đủ tốt cho ticket/email/search query classification.

```python
from sklearn.feature_extraction.text import TfidfVectorizer

text_pipeline = TfidfVectorizer(
    max_features=20_000,
    ngram_range=(1, 2),
    min_df=5,
    max_df=0.9,
    strip_accents="unicode",
)
```

Production concerns:

- Vocabulary được học trong `fit()`, nên phải lưu cùng model artifact.
- Không fit lại vectorizer ở inference.
- `max_features` là trade-off giữa recall, memory và latency.
- Text có thể chứa PII như email, phone, address; cần masking hoặc policy rõ.
- Với tiếng Việt, TF-IDF word-level có thể kém nếu tokenization chưa tốt; có thể cân nhắc char n-gram hoặc tokenizer tiếng Việt ở bài NLP sau.

## 6. Datetime Features Và Point-in-Time Correctness

Không nên đưa raw timestamp trực tiếp vào model. Hãy biến nó thành feature có ý nghĩa:

- `account_age_days`.
- `days_since_last_login`.
- `signup_month`.
- `signup_day_of_week`.
- `is_weekend_signup`.
- `ticket_count_7d`, `ticket_count_30d`.

Điểm quan trọng nhất: dùng `prediction_time`, không dùng `pd.Timestamp.now()` tùy tiện trong training.

```python
import pandas as pd

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in ["prediction_time", "signup_at", "last_login_at"]:
        result[col] = pd.to_datetime(result[col], utc=True, errors="coerce")

    result["account_age_days"] = (
        result["prediction_time"] - result["signup_at"]
    ).dt.total_seconds() / 86_400
    result["days_since_last_login"] = (
        result["prediction_time"] - result["last_login_at"]
    ).dt.total_seconds() / 86_400
    result["signup_month"] = result["signup_at"].dt.month.astype("Int64")
    result["signup_day_of_week"] = result["signup_at"].dt.dayofweek.astype("Int64")
    return result
```

Nếu feature cần join từ bảng event/log, dùng as-of join hoặc query có điều kiện `event_time <= prediction_time`. Trong Pandas, `merge_asof` là pattern hữu ích cho time-aware join, nhưng input phải được sort theo key thời gian.

## 7. Missing Data

Missing không phải lúc nào cũng là lỗi. Nó có thể là signal.

Ví dụ:

- `last_login_at` missing: user chưa từng login.
- `latest_ticket_text` missing: user chưa từng mở ticket.
- `monthly_charges` missing: upstream billing lỗi hoặc plan chưa active.

Decision table:

| Cách xử lý | Khi dùng | Rủi ro |
|---|---|---|
| Drop row | Missing rất ít và random | Mất data, bias nếu missing không random |
| Mean/median | Numerical baseline | Che mất signal missing |
| Most frequent | Categorical đơn giản | Có thể làm category phổ biến bị overweight |
| Constant `__missing__` | Missing có nghĩa nghiệp vụ | Tăng cardinality |
| Missing indicator | Missing là signal | Tăng số feature |
| Model-based imputation | Data lớn, pattern phức tạp | Dễ overfit, khó debug |

Best default: median cho numerical, constant `__missing__` cho categorical/text, thêm missing indicator cho numerical quan trọng.

## 8. Feature Selection

Feature selection giúp giảm overfitting, memory, latency và độ phức tạp vận hành.

Các bước nên làm:

1. Drop feature không có nghĩa tại prediction time.
2. Drop feature quá nhiều missing nếu không có signal rõ.
3. Drop constant/near-constant.
4. Group hoặc drop high-cardinality category không kiểm soát.
5. Dùng `SelectPercentile`, `SelectKBest`, L1 regularization hoặc model importance sau khi có baseline.
6. Không chọn feature dựa trên test set.

Trong scikit-learn, selector có thể nằm trong pipeline để tránh leakage:

```python
from sklearn.feature_selection import SelectPercentile, chi2
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

categorical_pipeline = Pipeline([
    ("encoder", OneHotEncoder(handle_unknown="ignore")),
    ("selector", SelectPercentile(score_func=chi2, percentile=80)),
])
```

## 9. Pipeline Gần Production

Skeleton nên dùng:

```python
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

numeric_features = [
    "monthly_charges",
    "account_age_days",
    "days_since_last_login",
    "support_ticket_count_30d",
]
categorical_features = ["contract_type", "payment_method", "signup_month"]
text_feature = "latest_ticket_text"

numeric_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
    ("scaler", RobustScaler()),
])

categorical_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
    ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=10)),
])

preprocessor = ColumnTransformer([
    ("num", numeric_pipeline, numeric_features),
    ("cat", categorical_pipeline, categorical_features),
    ("text", TfidfVectorizer(max_features=20_000, ngram_range=(1, 2), min_df=5), text_feature),
])

model = Pipeline([
    ("preprocess", preprocessor),
    ("classifier", LogisticRegression(max_iter=1_000, class_weight="balanced")),
])
```

Điểm đáng chú ý:

- `ColumnTransformer` áp dụng preprocessing khác nhau theo nhóm cột.
- `Pipeline.fit()` fit cả preprocessing và model trên train.
- `Pipeline.predict()` tái sử dụng đúng preprocessing đã fit.
- `OneHotEncoder(handle_unknown="ignore")` tránh crash với category mới, nhưng cần monitoring.
- `SimpleImputer(add_indicator=True)` giúp model biết giá trị nào từng bị missing.

## 10. Schema Validation Trước Inference

scikit-learn không thay thế được data contract. Trước khi gọi `model.predict`, service nên validate input.

Ví dụ validation tối thiểu:

```python
REQUIRED_COLUMNS = {
    "customer_id": "object",
    "prediction_time": "datetime64[ns, UTC]",
    "signup_at": "datetime64[ns, UTC]",
    "last_login_at": "datetime64[ns, UTC]",
    "contract_type": "object",
    "payment_method": "object",
    "monthly_charges": "number",
    "latest_ticket_text": "object",
}

def validate_inference_schema(df):
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if df["customer_id"].isna().any():
        raise ValueError("customer_id must not be null")

    if (df["monthly_charges"].dropna() < 0).any():
        raise ValueError("monthly_charges must be non-negative")

    if (df["prediction_time"] < df["signup_at"]).any():
        raise ValueError("prediction_time must be >= signup_at")
```

Trong production thật, nên dùng Pandera, Great Expectations, Pydantic hoặc validation ở API/data layer. Với Day 5, mục tiêu là hiểu contract, không phụ thuộc tool.

## 11. Performance Và Production Concerns

Các bottleneck thường không nằm ở model mà nằm ở feature:

- Join nhiều bảng để tính rolling feature.
- High-cardinality one-hot làm sparse matrix rất lớn.
- TF-IDF vocabulary lớn làm tăng memory và latency.
- Imputation/encoding fit lại trong inference do deploy sai artifact.
- Batch training dùng Pandas ổn nhưng online serving cần feature store/cache.

Checklist vận hành:

- Version model artifact cùng feature pipeline.
- Lưu training schema, feature list, encoder vocabulary, TF-IDF vocabulary.
- Log input row count, missing rate, unknown category rate, text empty rate.
- Monitor distribution drift cho feature quan trọng.
- Có fallback khi feature source chậm hoặc lỗi.
- Không log raw PII trong text.

## 12. Dùng Được Trong Production Không?

Có, pipeline trong bài này dùng được làm nền tảng production cho bài toán tabular/text baseline nếu đáp ứng các điều kiện sau:

- Feature được định nghĩa theo point-in-time correctness, không dùng dữ liệu tương lai.
- Train/test split phản ánh cách model sẽ chạy thật: time-based split nếu bài toán có yếu tố thời gian.
- Toàn bộ preprocessing nằm trong `Pipeline`/`ColumnTransformer` và được lưu cùng model.
- Có schema validation trước inference.
- Có monitoring cho missing rate, unknown category, feature drift, latency và model metrics.
- Có versioning cho feature schema, model, data snapshot và training code.
- Có kiểm thử cho leakage, schema contract và train-serving consistency.
- Với online low-latency, rolling/aggregate features cần precompute hoặc cache, không query/ad-hoc join nặng trong request path.

Không nên coi notebook preprocessing rời rạc là production-ready. Production-ready là deploy cả feature contract + preprocessing pipeline + model + validation + monitoring.

## 13. Tự Kiểm Tra

1. Vì sao không fit scaler/encoder/vectorizer trên toàn bộ dataset trước khi split?
2. Khi nào `RobustScaler` tốt hơn `StandardScaler`?
3. Vì sao `OneHotEncoder(handle_unknown="ignore")` không đủ để bỏ qua monitoring category drift?
4. Target encoding leak như thế nào?
5. Tại sao datetime feature phải dựa trên `prediction_time`?
6. Nếu offline ROC-AUC cao nhưng production fail, bạn kiểm tra feature nào trước?
7. Feature engineering khác business rule engineering ở điểm nào?

## Liên Kết

- [Document: decision matrix và checklist](./document.md)
- [Exercise: pipeline practice](./exercise.md)
