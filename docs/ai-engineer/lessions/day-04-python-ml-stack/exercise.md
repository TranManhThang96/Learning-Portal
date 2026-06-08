# Day 4 Exercise: Titanic-style Production Pipeline

## Mục tiêu exercise

Bạn sẽ viết một training script gần production cho bài toán binary classification:

```text
Input passenger features -> predict survived probability
```

Yêu cầu:

- Load Titanic từ OpenML nếu có network/cache.
- Có fallback synthetic dataset để bài vẫn chạy offline.
- Validate schema trước training và trước inference.
- Dùng `ColumnTransformer` + `Pipeline`.
- Train ít nhất 3 models.
- So sánh metrics và latency.
- Lưu artifact `model.joblib` và `metadata.json`.
- Load lại artifact và predict một request mẫu.

## 1. Chuẩn bị môi trường

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install numpy pandas scikit-learn joblib
```

Nếu dùng `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install numpy pandas scikit-learn joblib
```

## 2. Tạo file `train_titanic_pipeline.py`

Bạn có thể đặt file này ở workspace tạm hoặc trong project riêng của bạn. Nội dung:

```python
from __future__ import annotations

import json
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.datasets import fetch_openml, make_classification
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


RANDOM_STATE = 42
ARTIFACT_DIR = Path("artifacts/day4_titanic")
MODEL_PATH = ARTIFACT_DIR / "model.joblib"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"

RAW_NUMERIC_FEATURES = ["age", "sibsp", "parch", "fare"]
DERIVED_NUMERIC_FEATURES = ["family_size", "is_alone"]
NUMERIC_FEATURES = RAW_NUMERIC_FEATURES + DERIVED_NUMERIC_FEATURES
CATEGORICAL_FEATURES = ["pclass", "sex", "embarked"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "survived"


@dataclass(frozen=True)
class SchemaIssue:
    field: str
    message: str


class SchemaValidationError(ValueError):
    def __init__(self, issues: list[SchemaIssue]) -> None:
        self.issues = issues
        detail = "; ".join(f"{issue.field}: {issue.message}" for issue in issues)
        super().__init__(detail)


def load_titanic_or_fallback() -> tuple[pd.DataFrame, str]:
    """Load Titanic from OpenML; fallback keeps the exercise runnable offline."""
    try:
        titanic = fetch_openml(name="titanic", version=1, as_frame=True)
        frame = titanic.frame
        df = frame[["pclass", "sex", "age", "sibsp", "parch", "fare", "embarked", "survived"]].copy()
        df["survived"] = df["survived"].astype(int)
        return df, "openml_titanic_v1"
    except (OSError, TimeoutError) as exc:
        print(f"OpenML unavailable, using synthetic fallback. Reason: {exc}")
        X, y = make_classification(
            n_samples=1309,
            n_features=6,
            n_informative=4,
            n_redundant=1,
            random_state=RANDOM_STATE,
        )
        df = pd.DataFrame(X, columns=["age_raw", "fare_raw", "sibsp_raw", "parch_raw", "class_raw", "sex_raw"])
        df["age"] = np.clip((df["age_raw"] * 12 + 32).round(1), 0, 80)
        df["fare"] = np.clip((df["fare_raw"] * 20 + 35).round(2), 0, 300)
        df["sibsp"] = np.clip(np.abs(df["sibsp_raw"]).round().astype(int), 0, 5)
        df["parch"] = np.clip(np.abs(df["parch_raw"]).round().astype(int), 0, 5)
        df["pclass"] = pd.cut(df["class_raw"], bins=3, labels=["1", "2", "3"]).astype(str)
        df["sex"] = np.where(df["sex_raw"] > 0, "male", "female")
        df["embarked"] = np.select(
            [df["fare"] < 20, df["fare"] < 80],
            ["S", "C"],
            default="Q",
        )
        df["survived"] = y.astype(int)
        return df[["pclass", "sex", "age", "sibsp", "parch", "fare", "embarked", "survived"]], "synthetic_fallback"


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["family_size"] = df["sibsp"].fillna(0) + df["parch"].fillna(0) + 1
    df["is_alone"] = (df["family_size"] == 1).astype(int)
    df["pclass"] = df["pclass"].astype("string")
    df["sex"] = df["sex"].astype("string")
    df["embarked"] = df["embarked"].astype("string")
    return df


def validate_training_frame(df: pd.DataFrame) -> None:
    required = set(RAW_NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET])
    issues: list[SchemaIssue] = []

    missing = sorted(required - set(df.columns))
    for column in missing:
        issues.append(SchemaIssue(column, "missing required column"))

    if TARGET in df.columns:
        labels = set(pd.Series(df[TARGET]).dropna().astype(int).unique().tolist())
        if not labels.issubset({0, 1}):
            issues.append(SchemaIssue(TARGET, f"expected binary labels 0/1, got {sorted(labels)}"))

    for column in RAW_NUMERIC_FEATURES:
        if column in df.columns and not pd.api.types.is_numeric_dtype(df[column]):
            issues.append(SchemaIssue(column, f"expected numeric dtype, got {df[column].dtype}"))

    if issues:
        raise SchemaValidationError(issues)


def validate_inference_payload(payload: dict[str, Any]) -> pd.DataFrame:
    issues: list[SchemaIssue] = []
    required = set(RAW_NUMERIC_FEATURES + CATEGORICAL_FEATURES)

    for column in sorted(required - set(payload)):
        issues.append(SchemaIssue(column, "missing required field"))

    row: dict[str, Any] = {}
    for column in RAW_NUMERIC_FEATURES:
        value = payload.get(column)
        if value is None:
            row[column] = np.nan
            continue
        try:
            row[column] = float(value)
        except (TypeError, ValueError):
            issues.append(SchemaIssue(column, f"expected numeric value, got {value!r}"))

    for column in CATEGORICAL_FEATURES:
        value = payload.get(column)
        if value is None or str(value).strip() == "":
            row[column] = pd.NA
        else:
            row[column] = str(value)

    if issues:
        raise SchemaValidationError(issues)

    return add_features(pd.DataFrame([row]))[FEATURES]


def build_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            # Titanic has low cardinality. Dense output keeps this shared
            # preprocessor compatible with HistGradientBoostingClassifier.
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ]
    )


def build_model_specs() -> list[tuple[str, Any]]:
    return [
        (
            "logistic_regression",
            LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        ),
        (
            "random_forest",
            RandomForestClassifier(
                n_estimators=250,
                max_depth=7,
                min_samples_leaf=3,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        (
            "hist_gradient_boosting",
            HistGradientBoostingClassifier(
                max_iter=200,
                learning_rate=0.05,
                random_state=RANDOM_STATE,
            ),
        ),
    ]


def evaluate_pipeline(
    name: str,
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
) -> tuple[dict[str, float | str], Pipeline]:
    train_started = time.perf_counter()
    pipeline.fit(X_train, y_train)
    train_ms = (time.perf_counter() - train_started) * 1000

    predict_started = time.perf_counter()
    y_pred = pipeline.predict(X_test)
    predict_ms = (time.perf_counter() - predict_started) * 1000

    if hasattr(pipeline, "predict_proba"):
        y_score = pipeline.predict_proba(X_test)[:, 1]
    else:
        y_score = y_pred

    metrics: dict[str, float | str] = {
        "model": name,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_score),
        "average_precision": average_precision_score(y_test, y_score),
        "train_ms": train_ms,
        "predict_ms_per_row": predict_ms / len(X_test),
    }
    return metrics, pipeline


def train() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    raw_df, dataset_source = load_titanic_or_fallback()
    validate_training_frame(raw_df)
    df = add_features(raw_df)

    print("Dataset source:", dataset_source)
    print("Shape:", df.shape)
    print("Missing ratio:")
    print((df[FEATURES + [TARGET]].isna().mean() * 100).sort_values(ascending=False))
    print("Target distribution:")
    print(df[TARGET].value_counts(normalize=True).sort_index())

    X = df[FEATURES]
    y = df[TARGET].astype(int)

    X_dev, X_test, y_dev, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )
    X_train, X_valid, y_train, y_valid = train_test_split(
        X_dev,
        y_dev,
        test_size=0.25,
        random_state=RANDOM_STATE,
        stratify=y_dev,
    )

    results: list[dict[str, float | str]] = []
    trained: dict[str, Pipeline] = {}

    for name, model in build_model_specs():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", build_preprocessor()),
                ("model", model),
            ]
        )
        metrics, fitted = evaluate_pipeline(
            name,
            pipeline,
            X_train,
            X_valid,
            y_train,
            y_valid,
        )
        results.append(metrics)
        trained[name] = fitted

    summary = pd.DataFrame(results).sort_values(["roc_auc", "f1"], ascending=False)
    print("Validation metrics used for model selection:")
    print(summary.to_string(index=False))

    best_name = str(summary.iloc[0]["model"])
    best_pipeline = trained[best_name]
    test_metrics, best_pipeline = evaluate_pipeline(
        best_name,
        best_pipeline,
        X_dev,
        X_test,
        y_dev,
        y_test,
    )
    print("Final test metrics (evaluated once after selection):")
    print(pd.DataFrame([test_metrics]).to_string(index=False))
    joblib.dump(best_pipeline, MODEL_PATH)

    metadata = {
        "schema_version": "day4-titanic-v1",
        "dataset_source": dataset_source,
        "best_model": best_name,
        "target": TARGET,
        "raw_numeric_features": RAW_NUMERIC_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "features": FEATURES,
        "random_state": RANDOM_STATE,
        "test_size": 0.2,
        "validation_size_within_dev": 0.25,
        "validation_metrics": summary.to_dict(orient="records"),
        "test_metrics": test_metrics,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "security_note": "Only load this joblib artifact from trusted storage.",
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved metadata: {METADATA_PATH}")


def predict_survival(payload: dict[str, Any]) -> dict[str, Any]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model artifact not found: {MODEL_PATH}. Run train() first.")

    pipeline: Pipeline = joblib.load(MODEL_PATH)
    X = validate_inference_payload(payload)
    probability = float(pipeline.predict_proba(X)[0, 1])
    prediction = int(probability >= 0.5)
    return {
        "prediction": prediction,
        "survived_probability": probability,
        "threshold": 0.5,
        "schema_version": "day4-titanic-v1",
    }


if __name__ == "__main__":
    train()
    sample_payload = {
        "pclass": "3",
        "sex": "female",
        "age": 29,
        "sibsp": 0,
        "parch": 0,
        "fare": 7.9,
        "embarked": "S",
    }
    print("Sample prediction:")
    print(json.dumps(predict_survival(sample_payload), indent=2))
```

## 3. Chạy script

```bash
python3 train_titanic_pipeline.py
```

Kết quả kỳ vọng:

- In dataset source: `openml_titanic_v1` hoặc `synthetic_fallback`.
- In missing ratio và target distribution.
- In validation metrics của 3 models để chọn candidate.
- In test metrics đúng một lần cho model đã chọn.
- Tạo `artifacts/day4_titanic/model.joblib`.
- Tạo `artifacts/day4_titanic/metadata.json`.
- In sample prediction dạng JSON.

## 4. Review kết quả

Mở `metadata.json` và kiểm tra:

- Model nào được chọn?
- Validation metrics có được tách khỏi `test_metrics` không?
- `roc_auc`, `average_precision`, `f1`, `precision`, `recall` trên test của model đã chọn là bao nhiêu?
- `predict_ms_per_row` có khác nhiều giữa các model không?
- `dataset_source` là OpenML hay fallback?
- Feature list có đủ raw và derived features không?

Không chọn model chỉ vì accuracy cao. Với bài toán sinh tồn Titanic, đây là exercise học stack; trong business thật, bạn phải định nghĩa false positive/false negative cost. Nếu positive class hiếm như fraud/churn, hãy thêm Average Precision và ghi rõ implementation/definition khi report.

## 5. Bài tập mở rộng

### Bài 1: Thêm schema range check

Trong `validate_inference_payload`, thêm rule:

- `age` nằm trong `[0, 120]` nếu không null.
- `fare` không âm.
- `sibsp`, `parch` không âm và là số gần integer.

Trade-off: strict validation giúp bắt input xấu sớm, nhưng nếu quá strict có thể reject dữ liệu hợp lệ ngoài distribution cũ. Với production, nên phân biệt hard validation và drift alert.

### Bài 2: Thêm threshold tuning

Thay vì hard-code threshold `0.5`, thử các threshold từ `0.2` đến `0.8`, chọn threshold theo mục tiêu:

- Ưu tiên recall nếu bỏ sót positive rất đắt.
- Ưu tiên precision nếu false alarm rất đắt.
- Ưu tiên F1 nếu muốn cân bằng.

Gợi ý:

```python
for threshold in np.arange(0.2, 0.85, 0.05):
    y_pred = (y_score >= threshold).astype(int)
    print(threshold, precision_score(y_test, y_pred), recall_score(y_test, y_pred), f1_score(y_test, y_pred))
```

### Bài 3: Viết smoke test

Tạo test đơn giản:

```python
def test_predict_survival_smoke():
    payload = {
        "pclass": "1",
        "sex": "female",
        "age": 38,
        "sibsp": 1,
        "parch": 0,
        "fare": 71.28,
        "embarked": "C",
    }
    result = predict_survival(payload)
    assert 0 <= result["survived_probability"] <= 1
    assert result["prediction"] in {0, 1}
```

### Bài 4: Tách thành package nhỏ

Nếu muốn gần production hơn, tách file:

```text
day4_project/
  pyproject.toml
  src/day4_titanic/
    data.py
    features.py
    train.py
    predict.py
    schema.py
  tests/
    test_predict.py
```

Đây là bước chuyển từ notebook/script sang maintainable codebase.

## 6. Câu hỏi bắt buộc: dùng được trong production không?

Viết decision memo 300-500 từ, bắt buộc trả lời:

- Dataset và split có mô phỏng production traffic không?
- Model được chọn bằng validation hay test?
- Artifact được build, version, scan và rollback thế nào?
- API/batch boundary validate schema và range ra sao?
- Monitor drift, model quality, latency và unknown category thế nào?
- Khi nào Pandas single-row overhead hoặc dense one-hot không còn chấp nhận được?
- Vì sao chỉ được load `joblib` từ trusted storage?

## 7. Checklist nộp bài

- [ ] Script chạy được không cần chỉnh tay.
- [ ] Có fallback khi không tải được OpenML.
- [ ] Có schema validation.
- [ ] Có `Pipeline` chứa preprocessing và model.
- [ ] Có ít nhất 3 models.
- [ ] Có metrics table.
- [ ] Test set chỉ được dùng sau khi chọn model.
- [ ] Có `model.joblib`.
- [ ] Có `metadata.json`.
- [ ] Có sample prediction.
- [ ] Có câu trả lời production readiness.
