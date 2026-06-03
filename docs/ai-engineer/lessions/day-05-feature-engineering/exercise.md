# Day 5 Exercise: Production-style Feature Pipeline

Mục tiêu bài tập: build một pipeline churn prediction có numerical, categorical, text và datetime features; kiểm soát leakage; validate schema; đánh giá baseline. Đây không phải code cuối cùng cho production, nhưng là skeleton đủ gần production để bạn mở rộng.

## 1. Setup

```bash
pip install pandas numpy scikit-learn joblib
```

## 2. Yêu Cầu

Bạn sẽ tạo pipeline với:

- Feature datetime dựa trên `prediction_time`.
- Numerical preprocessing: impute median, missing indicator, scale.
- Categorical preprocessing: impute constant, one-hot, handle unknown category.
- Text preprocessing: TF-IDF.
- Model: Logistic Regression baseline.
- Validation: check required columns, non-negative charge, prediction time hợp lệ.
- Leakage checks: không dùng event sau `prediction_time`.

## 3. Full Example

```python
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler


RAW_REQUIRED_COLUMNS = [
    "customer_id",
    "prediction_time",
    "signup_at",
    "last_login_at",
    "contract_type",
    "payment_method",
    "monthly_charges",
    "support_ticket_count_30d",
    "latest_ticket_text",
]


def build_sample_data(n: int = 2_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    prediction_time = pd.Timestamp("2026-05-01", tz="UTC")

    signup_days_ago = rng.integers(30, 1_500, size=n)
    last_login_days_ago = rng.integers(0, 180, size=n).astype(float)
    never_login_mask = rng.random(n) < 0.08
    last_login_days_ago[never_login_mask] = np.nan

    contract_type = rng.choice(
        ["monthly", "one_year", "two_year"],
        size=n,
        p=[0.58, 0.30, 0.12],
    )
    payment_method = rng.choice(
        ["credit_card", "bank_transfer", "electronic_check", "wallet"],
        size=n,
        p=[0.38, 0.28, 0.28, 0.06],
    )
    monthly_charges = rng.lognormal(mean=4.1, sigma=0.45, size=n).clip(5, 300)
    support_ticket_count_30d = rng.poisson(1.4, size=n)

    latest_ticket_text = np.where(
        support_ticket_count_30d >= 3,
        "service slow billing issue want cancel",
        "general question invoice support ok",
    )

    df = pd.DataFrame({
        "customer_id": [f"cus_{i:05d}" for i in range(n)],
        "prediction_time": prediction_time,
        "signup_at": prediction_time - pd.to_timedelta(signup_days_ago, unit="D"),
        "last_login_at": prediction_time - pd.to_timedelta(last_login_days_ago, unit="D"),
        "contract_type": contract_type,
        "payment_method": payment_method,
        "monthly_charges": monthly_charges,
        "support_ticket_count_30d": support_ticket_count_30d,
        "latest_ticket_text": latest_ticket_text,
    })

    df.loc[rng.choice(df.index, size=int(n * 0.04), replace=False), "monthly_charges"] = np.nan
    df.loc[rng.choice(df.index, size=int(n * 0.03), replace=False), "payment_method"] = np.nan
    df.loc[rng.choice(df.index, size=int(n * 0.06), replace=False), "latest_ticket_text"] = ""

    churn_logit = (
        0.95 * (df["contract_type"] == "monthly").astype(float)
        + 0.75 * (df["payment_method"] == "electronic_check").astype(float)
        + 0.18 * df["support_ticket_count_30d"]
        + 0.010 * np.nan_to_num(last_login_days_ago, nan=120.0)
        + 0.004 * np.nan_to_num(monthly_charges, nan=np.nanmedian(monthly_charges))
        - 2.15
        + rng.normal(0, 0.65, size=n)
    )
    churn_probability = 1 / (1 + np.exp(-churn_logit))
    df["churn"] = rng.binomial(1, churn_probability)
    return df


def validate_raw_schema(df: pd.DataFrame) -> None:
    missing = set(RAW_REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if df["customer_id"].isna().any():
        raise ValueError("customer_id must not be null")

    prediction_time = pd.to_datetime(df["prediction_time"], utc=True, errors="coerce")
    signup_at = pd.to_datetime(df["signup_at"], utc=True, errors="coerce")
    last_login_at = pd.to_datetime(df["last_login_at"], utc=True, errors="coerce")

    if prediction_time.isna().any() or signup_at.isna().any():
        raise ValueError("prediction_time and signup_at must be valid datetimes")

    if (prediction_time < signup_at).any():
        raise ValueError("prediction_time must be greater than or equal to signup_at")

    known_last_login = last_login_at.notna()
    if (last_login_at[known_last_login] > prediction_time[known_last_login]).any():
        raise ValueError("last_login_at must not be after prediction_time")

    if (df["monthly_charges"].dropna() < 0).any():
        raise ValueError("monthly_charges must be non-negative")


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["prediction_time"] = pd.to_datetime(result["prediction_time"], utc=True, errors="coerce")
    result["signup_at"] = pd.to_datetime(result["signup_at"], utc=True, errors="coerce")
    result["last_login_at"] = pd.to_datetime(result["last_login_at"], utc=True, errors="coerce")

    result["account_age_days"] = (
        result["prediction_time"] - result["signup_at"]
    ).dt.total_seconds() / 86_400
    result["days_since_last_login"] = (
        result["prediction_time"] - result["last_login_at"]
    ).dt.total_seconds() / 86_400
    result["signup_month"] = result["signup_at"].dt.month.astype("Int64").astype("string")
    result["signup_day_of_week"] = result["signup_at"].dt.dayofweek.astype("Int64").astype("string")
    result["latest_ticket_text"] = result["latest_ticket_text"].fillna("")
    return result


def build_model_pipeline() -> Pipeline:
    numeric_features = [
        "monthly_charges",
        "support_ticket_count_30d",
        "account_age_days",
        "days_since_last_login",
    ]
    categorical_features = [
        "contract_type",
        "payment_method",
        "signup_month",
        "signup_day_of_week",
    ]

    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", RobustScaler()),
    ])

    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=5)),
    ])

    preprocessor = ColumnTransformer([
        ("num", numeric_pipeline, numeric_features),
        ("cat", categorical_pipeline, categorical_features),
        ("text", TfidfVectorizer(max_features=3_000, ngram_range=(1, 2), min_df=3), "latest_ticket_text"),
    ])

    return Pipeline([
        ("preprocess", preprocessor),
        ("classifier", LogisticRegression(max_iter=1_000, class_weight="balanced")),
    ])


def train_and_evaluate() -> Pipeline:
    df = build_sample_data()
    validate_raw_schema(df)
    df = add_time_features(df)

    X = df.drop(columns=["churn"])
    y = df["churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = build_model_pipeline()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    print(classification_report(y_test, y_pred))
    print("ROC-AUC:", round(roc_auc_score(y_test, y_prob), 4))

    transformed_shape = model.named_steps["preprocess"].transform(X_test).shape
    print("Transformed shape:", transformed_shape)

    joblib.dump(model, "day05_churn_pipeline.joblib")
    return model


if __name__ == "__main__":
    train_and_evaluate()
```

## 4. Bài Tập Bắt Buộc

1. Chạy baseline và ghi lại ROC-AUC.
2. Thay `RobustScaler` bằng `StandardScaler`, so sánh metric và giải thích vì sao khác hoặc không khác.
3. Bỏ text feature khỏi `ColumnTransformer`, đo lại ROC-AUC và transformed shape.
4. Thêm feature `is_inactive_30d = days_since_last_login > 30`. Feature này nên là numerical hay categorical? Vì sao?
5. Tạo 5 row inference giả lập có category mới `payment_method = "crypto"`. Pipeline có crash không? Bạn sẽ monitor gì?
6. Viết test nhỏ để đảm bảo `last_login_at > prediction_time` bị reject.
7. Thay `train_test_split` bằng time-based split nếu dataset có nhiều `prediction_time`. Giải thích khi nào stratified random split là không đủ.

## 5. Câu Hỏi Review

- Feature nào có nguy cơ leakage nhất trong pipeline này?
- Nếu production latency target là 50 ms/request, phần nào cần precompute?
- Nếu unknown category rate tăng từ 1% lên 18%, bạn nghi ngờ điều gì?
- Nếu text có PII, bạn xử lý ở đâu: trước TF-IDF, trong pipeline, hay sau prediction?
- Pipeline này dùng được trong production không? Nếu có, thiếu điều kiện nào so với hệ thống thật?

## 6. Gợi Ý Kiểm Thử Production

Các test tối thiểu:

- Schema test: thiếu cột bắt buộc thì fail.
- Type test: datetime parse lỗi thì fail.
- Point-in-time test: event/login sau prediction time thì fail.
- Pipeline persistence test: `joblib.dump` rồi `joblib.load`, prediction không đổi.
- Unknown category test: category mới không crash.
- Empty text test: text rỗng không crash.
- Transformed shape test: shape ổn định với cùng model artifact.

## 7. Deliverable

Tạo một file ghi chú ngắn gồm:

- Baseline ROC-AUC.
- 3 thay đổi bạn thử và kết quả.
- 3 leakage risks bạn đã kiểm tra.
- 5 validation rules cho inference input.
- Kết luận production readiness.
