# Day 8 Exercise - Mini-project Customer Churn ML Pipeline

Mục tiêu của bài tập là viết một script training gần production, không chỉ train model trong notebook. Bạn có thể dùng Telco Customer Churn CSV hoặc để script tạo synthetic dataset có schema tương tự.

## 1. Yêu Cầu Hoàn Thành

Bạn cần nộp được:

- `README.md` mô tả problem, dataset, metrics, threshold, trade-off và production readiness.
- `requirements.txt` hoặc `pyproject.toml`.
- Script train pipeline.
- Metrics report.
- Error analysis report.
- Model artifact `.joblib`.
- Inference function nhận `dict` và trả `dict`.

Trong repo bài học, bạn có thể làm trong folder riêng của mình. Không cần commit dataset thật hoặc artifact lớn.

## 2. Cài Đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy pandas scikit-learn joblib
```

Nếu dùng `requirements.txt`:

```text
numpy>=1.26
pandas>=2.1
scikit-learn>=1.4,<2.0
joblib>=1.3
```

## 3. Code Mẫu Hoàn Chỉnh

Tạo package:

```text
src/
  __init__.py
  churn_pipeline.py
  train_churn.py
```

Đặt code dưới đây trong `src/churn_pipeline.py`. File này là module importable, có schema validation, pipeline, threshold tuning, artifact metadata và inference contract.

```python
from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


RANDOM_STATE = 42
TARGET_COL = "Churn"
ID_COL = "customerID"
SCHEMA_VERSION = "telco-churn-v1"
MODEL_VERSION = "customer-churn-v1"

RAW_FEATURE_COLUMNS = [
    "customerID",
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "tenure",
    "PhoneService",
    "InternetService",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
    "MonthlyCharges",
    "TotalCharges",
]

REQUIRED_TRAINING_COLUMNS = RAW_FEATURE_COLUMNS + [TARGET_COL]

NUMERIC_FEATURES = [
    "SeniorCitizen",
    "tenure",
    "MonthlyCharges",
    "TotalCharges",
    "avg_monthly_charge_observed",
]

CATEGORICAL_FEATURES = [
    "gender",
    "Partner",
    "Dependents",
    "PhoneService",
    "InternetService",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
    "tenure_group",
    "monthly_charge_band",
]


@dataclass
class ThresholdResult:
    threshold: float
    precision: float
    recall: float
    f1: float
    predicted_positive_rate: float
    tp: int
    fp: int
    fn: int
    tn: int


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=json_default),
        encoding="utf-8",
    )


def normalize_string_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    for column in df.columns:
        if pd.api.types.is_object_dtype(df[column]) or pd.api.types.is_string_dtype(df[column]):
            df[column] = df[column].map(lambda value: value.strip() if isinstance(value, str) else value)
            df[column] = df[column].replace("", np.nan)
    return df


def validate_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    missing = sorted(set(required_columns) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def normalize_telco_frame(df: pd.DataFrame, require_target: bool) -> pd.DataFrame:
    df = normalize_string_values(df)
    required_columns = REQUIRED_TRAINING_COLUMNS if require_target else RAW_FEATURE_COLUMNS
    validate_columns(df, required_columns)

    df = df.copy()
    for column in ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if require_target:
        if not pd.api.types.is_numeric_dtype(df[TARGET_COL]):
            normalized_target = df[TARGET_COL].map(
                lambda value: value.strip().lower() if isinstance(value, str) else value
            )
            df[TARGET_COL] = normalized_target.replace({"yes": 1, "no": 0})
        df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors="coerce")
        if df[TARGET_COL].isna().any():
            raise ValueError("Target column contains values other than Yes/No or 1/0.")
        unique_targets = set(df[TARGET_COL].astype(int).unique())
        if not unique_targets.issubset({0, 1}):
            raise ValueError(f"Target must be binary 0/1, got {sorted(unique_targets)}.")
        df[TARGET_COL] = df[TARGET_COL].astype(int)

    return df


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    tenure = df["tenure"].clip(lower=0)
    safe_tenure = tenure.replace(0, np.nan)
    avg_charge = df["TotalCharges"] / safe_tenure
    df["avg_monthly_charge_observed"] = avg_charge.replace([np.inf, -np.inf], np.nan)
    df["avg_monthly_charge_observed"] = df["avg_monthly_charge_observed"].fillna(df["MonthlyCharges"])

    df["tenure_group"] = pd.cut(
        tenure,
        bins=[-0.1, 6, 12, 24, 48, np.inf],
        labels=["0-6", "7-12", "13-24", "25-48", "49+"],
    ).astype("object")

    df["monthly_charge_band"] = pd.cut(
        df["MonthlyCharges"],
        bins=[-np.inf, 35, 70, np.inf],
        labels=["low", "medium", "high"],
    ).astype("object")

    return df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]


class TelcoFeatureBuilder(BaseEstimator, TransformerMixin):
    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> "TelcoFeatureBuilder":
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        normalized = normalize_telco_frame(X, require_target=False)
        return add_engineered_features(normalized)


def generate_synthetic_telco(n_rows: int = 7000) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_STATE)

    tenure = rng.integers(0, 73, size=n_rows)
    contract = rng.choice(["Month-to-month", "One year", "Two year"], size=n_rows, p=[0.55, 0.25, 0.20])
    internet = rng.choice(["DSL", "Fiber optic", "No"], size=n_rows, p=[0.35, 0.50, 0.15])
    payment = rng.choice(
        ["Electronic check", "Mailed check", "Bank transfer", "Credit card"],
        size=n_rows,
        p=[0.45, 0.15, 0.20, 0.20],
    )
    monthly_base = np.where(internet == "Fiber optic", 82, np.where(internet == "DSL", 58, 28))
    monthly_charges = np.clip(rng.normal(monthly_base, 12), 18, 120).round(2)
    total_charges = (monthly_charges * np.maximum(tenure, 1) * rng.normal(1.0, 0.08, size=n_rows)).round(2)
    total_charges = total_charges.astype(object)
    total_charges[tenure == 0] = " "

    paperless = rng.choice(["Yes", "No"], size=n_rows, p=[0.6, 0.4])
    senior = rng.choice([0, 1], size=n_rows, p=[0.84, 0.16])
    partner = rng.choice(["Yes", "No"], size=n_rows, p=[0.48, 0.52])
    dependents = rng.choice(["Yes", "No"], size=n_rows, p=[0.30, 0.70])
    phone = rng.choice(["Yes", "No"], size=n_rows, p=[0.90, 0.10])
    gender = rng.choice(["Female", "Male"], size=n_rows)

    logit = (
        -1.7
        + 1.15 * (contract == "Month-to-month")
        + 0.55 * (internet == "Fiber optic")
        + 0.35 * (payment == "Electronic check")
        + 0.25 * (paperless == "Yes")
        + 0.30 * senior
        - 0.035 * tenure
        + 0.25 * (monthly_charges > 85)
        - 0.20 * (partner == "Yes")
        - 0.25 * (dependents == "Yes")
    )
    probability = 1 / (1 + np.exp(-logit))
    churn = rng.binomial(1, probability)

    return pd.DataFrame(
        {
            "customerID": [f"CUST_{i:06d}" for i in range(n_rows)],
            "gender": gender,
            "SeniorCitizen": senior,
            "Partner": partner,
            "Dependents": dependents,
            "tenure": tenure,
            "PhoneService": phone,
            "InternetService": internet,
            "Contract": contract,
            "PaperlessBilling": paperless,
            "PaymentMethod": payment,
            "MonthlyCharges": monthly_charges,
            "TotalCharges": total_charges,
            "Churn": np.where(churn == 1, "Yes", "No"),
        }
    )


def load_dataset(csv_path: Path | None, synthetic_rows: int) -> pd.DataFrame:
    if csv_path is not None:
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        return pd.read_csv(csv_path)
    return generate_synthetic_telco(synthetic_rows)


def run_eda(df: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "target_rate": float(df[TARGET_COL].mean()),
        "duplicate_customer_id": int(df[ID_COL].duplicated().sum()) if ID_COL in df.columns else None,
        "missing_rate": df.isna().mean().sort_values(ascending=False).to_dict(),
        "numeric_summary": df[["tenure", "MonthlyCharges", "TotalCharges"]].describe().to_dict(),
    }

    segment_cols = ["Contract", "InternetService", "PaymentMethod", "PaperlessBilling"]
    segment_report = {}
    for column in segment_cols:
        segment_report[column] = (
            df.groupby(column, dropna=False)[TARGET_COL]
            .agg(["count", "mean"])
            .sort_values("mean", ascending=False)
            .reset_index()
            .to_dict(orient="records")
        )
    report["segment_churn_rate"] = segment_report

    write_json(output_dir / "eda_report.json", report)
    return report


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
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def make_pipeline_for(model: Any) -> Pipeline:
    return Pipeline(
        steps=[
            ("features", TelcoFeatureBuilder()),
            ("preprocess", build_preprocessor()),
            ("model", model),
        ]
    )


def build_models() -> dict[str, Pipeline]:
    return {
        "logistic_regression": make_pipeline_for(
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            )
        ),
        "random_forest": make_pipeline_for(
            RandomForestClassifier(
                n_estimators=300,
                max_depth=9,
                min_samples_leaf=20,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
        ),
        "gradient_boosting": make_pipeline_for(
            GradientBoostingClassifier(
                n_estimators=180,
                learning_rate=0.05,
                max_depth=3,
                random_state=RANDOM_STATE,
            )
        ),
    }


def metrics_at_threshold(y_true: pd.Series, proba: np.ndarray, threshold: float) -> ThresholdResult:
    y_pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return ThresholdResult(
        threshold=float(threshold),
        precision=float(precision_score(y_true, y_pred, zero_division=0)),
        recall=float(recall_score(y_true, y_pred, zero_division=0)),
        f1=float(f1_score(y_true, y_pred, zero_division=0)),
        predicted_positive_rate=float(y_pred.mean()),
        tp=int(tp),
        fp=int(fp),
        fn=int(fn),
        tn=int(tn),
    )


def tune_threshold(
    y_true: pd.Series,
    proba: np.ndarray,
    min_recall: float,
) -> tuple[ThresholdResult, pd.DataFrame]:
    rows = [asdict(metrics_at_threshold(y_true, proba, threshold)) for threshold in np.arange(0.10, 0.91, 0.02)]
    threshold_report = pd.DataFrame(rows)
    candidates = threshold_report[threshold_report["recall"] >= min_recall]
    if candidates.empty:
        best = threshold_report.sort_values(["f1", "precision"], ascending=False).iloc[0]
    else:
        best = candidates.sort_values(["precision", "f1"], ascending=False).iloc[0]
    return ThresholdResult(**best.to_dict()), threshold_report


def evaluate_predictions(y_true: pd.Series, proba: np.ndarray, threshold: float) -> dict[str, Any]:
    threshold_metrics = metrics_at_threshold(y_true, proba, threshold)
    y_pred = (proba >= threshold).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "average_precision": float(average_precision_score(y_true, proba)),
        "threshold_metrics": asdict(threshold_metrics),
        "classification_report": classification_report(y_true, y_pred, output_dict=True, zero_division=0),
    }


def measure_prediction_latency(model: Pipeline, X: pd.DataFrame, repeats: int = 10) -> dict[str, float]:
    sample = X.head(min(len(X), 512))
    durations = []
    for _ in range(repeats):
        start = time.perf_counter()
        model.predict_proba(sample)[:, 1]
        durations.append((time.perf_counter() - start) * 1000)
    per_row = [duration / len(sample) for duration in durations]
    return {
        "batch_size": float(len(sample)),
        "p50_ms_per_row": float(np.percentile(per_row, 50)),
        "p95_ms_per_row": float(np.percentile(per_row, 95)),
    }


def run_error_analysis(
    model: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    threshold: float,
    output_dir: Path,
    min_slice_size: int = 30,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    proba = model.predict_proba(X_test)[:, 1]
    y_pred = (proba >= threshold).astype(int)

    scored = X_test.copy()
    scored["y_true"] = y_test.to_numpy()
    scored["proba"] = proba
    scored["y_pred"] = y_pred
    scored["error_type"] = np.select(
        [
            (scored["y_true"] == 0) & (scored["y_pred"] == 1),
            (scored["y_true"] == 1) & (scored["y_pred"] == 0),
        ],
        ["false_positive", "false_negative"],
        default="correct",
    )

    false_positives = scored[scored["error_type"] == "false_positive"].sort_values("proba", ascending=False)
    false_negatives = scored[scored["error_type"] == "false_negative"].sort_values("proba", ascending=True)
    false_positives.head(50).to_csv(output_dir / "false_positives.csv", index=False)
    false_negatives.head(50).to_csv(output_dir / "false_negatives.csv", index=False)

    feature_view = TelcoFeatureBuilder().transform(X_test)
    feature_view["y_true"] = y_test.to_numpy()
    feature_view["y_pred"] = y_pred

    slice_rows = []
    for column in ["Contract", "InternetService", "PaymentMethod", "tenure_group", "monthly_charge_band"]:
        for value, group in feature_view.groupby(column, dropna=False):
            if len(group) < min_slice_size:
                continue
            slice_rows.append(
                {
                    "slice_column": column,
                    "slice_value": str(value),
                    "count": int(len(group)),
                    "actual_positive_rate": float(group["y_true"].mean()),
                    "predicted_positive_rate": float(group["y_pred"].mean()),
                    "precision": float(precision_score(group["y_true"], group["y_pred"], zero_division=0)),
                    "recall": float(recall_score(group["y_true"], group["y_pred"], zero_division=0)),
                    "f1": float(f1_score(group["y_true"], group["y_pred"], zero_division=0)),
                }
            )

    slice_metrics = pd.DataFrame(slice_rows).sort_values(["f1", "count"], ascending=[True, False])
    slice_metrics.to_csv(output_dir / "slice_metrics.csv", index=False)

    return {
        "false_positive_count": int(len(false_positives)),
        "false_negative_count": int(len(false_negatives)),
        "worst_slices": slice_metrics.head(10).to_dict(orient="records"),
    }


def train_pipeline(
    csv_path: Path | None,
    artifact_path: Path,
    report_dir: Path,
    synthetic_rows: int,
    min_recall: float,
) -> dict[str, Any]:
    raw_df = load_dataset(csv_path, synthetic_rows)
    df = normalize_telco_frame(raw_df, require_target=True)
    run_eda(df, report_dir)

    X = df[RAW_FEATURE_COLUMNS]
    y = df[TARGET_COL]

    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        stratify=y,
        random_state=RANDOM_STATE,
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full,
        y_train_full,
        test_size=0.25,
        stratify=y_train_full,
        random_state=RANDOM_STATE,
    )

    model_reports = []
    trained_models = {}
    threshold_reports = {}

    for model_name, model in build_models().items():
        print(f"Training {model_name}...")
        model.fit(X_train, y_train)
        trained_models[model_name] = model

        val_proba = model.predict_proba(X_val)[:, 1]
        best_threshold, threshold_report = tune_threshold(y_val, val_proba, min_recall=min_recall)
        threshold_reports[model_name] = threshold_report
        threshold_report.to_csv(report_dir / f"threshold_report_{model_name}.csv", index=False)

        val_metrics = evaluate_predictions(y_val, val_proba, best_threshold.threshold)
        latency = measure_prediction_latency(model, X_val)
        model_reports.append(
            {
                "model_name": model_name,
                "threshold": best_threshold.threshold,
                "validation_metrics": val_metrics,
                "latency": latency,
            }
        )

    leaderboard = pd.DataFrame(
        [
            {
                "model_name": report["model_name"],
                "threshold": report["threshold"],
                "average_precision": report["validation_metrics"]["average_precision"],
                "roc_auc": report["validation_metrics"]["roc_auc"],
                "precision": report["validation_metrics"]["threshold_metrics"]["precision"],
                "recall": report["validation_metrics"]["threshold_metrics"]["recall"],
                "f1": report["validation_metrics"]["threshold_metrics"]["f1"],
                "p95_ms_per_row": report["latency"]["p95_ms_per_row"],
            }
            for report in model_reports
        ]
    ).sort_values(["average_precision", "f1"], ascending=False)

    report_dir.mkdir(parents=True, exist_ok=True)
    leaderboard.to_csv(report_dir / "leaderboard.csv", index=False)

    best_model_name = str(leaderboard.iloc[0]["model_name"])
    best_threshold = float(leaderboard.iloc[0]["threshold"])
    best_model = trained_models[best_model_name]
    test_proba = best_model.predict_proba(X_test)[:, 1]
    test_metrics = evaluate_predictions(y_test, test_proba, best_threshold)
    latency = measure_prediction_latency(best_model, X_test)
    error_report = run_error_analysis(best_model, X_test, y_test, best_threshold, report_dir / "error_analysis")

    metadata = {
        "model_name": best_model_name,
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "threshold": best_threshold,
        "raw_feature_columns": RAW_FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "validation_leaderboard": leaderboard.to_dict(orient="records"),
        "test_metrics": test_metrics,
        "latency": latency,
        "error_analysis": error_report,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "sklearn_version": sklearn.__version__,
        "joblib_version": joblib.__version__,
        "random_state": RANDOM_STATE,
        "training_rows": int(len(X_train)),
        "validation_rows": int(len(X_val)),
        "test_rows": int(len(X_test)),
        "training_note": "Validate with a time-based split and live monitoring before production deployment.",
    }

    artifact = {
        "model": best_model,
        "metadata": metadata,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_path)

    write_json(report_dir / "metrics_report.json", metadata)
    print(f"Saved artifact: {artifact_path}")
    print(leaderboard)
    return metadata


def risk_tier(probability: float, decision_threshold: float) -> str:
    if not 0.0 < decision_threshold < 1.0:
        raise ValueError("decision_threshold must be between 0 and 1")
    if probability >= decision_threshold:
        return "high"
    if probability >= decision_threshold * 0.75:
        return "medium"
    return "low"


def predict_customer_churn(customer: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
    # Security boundary: only load artifacts produced by a trusted training pipeline.
    artifact = joblib.load(artifact_path)
    model: Pipeline = artifact["model"]
    metadata: dict[str, Any] = artifact["metadata"]
    threshold = float(metadata["threshold"])

    input_df = pd.DataFrame([customer])
    normalized = normalize_telco_frame(input_df, require_target=False)
    probability = float(model.predict_proba(normalized[RAW_FEATURE_COLUMNS])[:, 1][0])

    return {
        "customer_id": str(customer.get(ID_COL, "")),
        "churn_probability": round(probability, 4),
        "will_churn": bool(probability >= threshold),
        "risk_tier": risk_tier(probability, threshold),
        "threshold": threshold,
        "model_name": metadata["model_name"],
        "model_version": metadata["model_version"],
        "schema_version": metadata["schema_version"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and evaluate a customer churn ML pipeline.")
    parser.add_argument("--csv", type=Path, default=None, help="Path to Telco Customer Churn CSV.")
    parser.add_argument("--artifact", type=Path, default=Path("artifacts/customer_churn_model.joblib"))
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/reports"))
    parser.add_argument("--synthetic-rows", type=int, default=7000)
    parser.add_argument("--min-recall", type=float, default=0.75)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_pipeline(
        csv_path=args.csv,
        artifact_path=args.artifact,
        report_dir=args.report_dir,
        synthetic_rows=args.synthetic_rows,
        min_recall=args.min_recall,
    )
```

Tạo `src/__init__.py` rỗng và `src/train_churn.py`:

```python
from src.churn_pipeline import main


if __name__ == "__main__":
    main()
```

Launcher import module bằng tên ổn định `src.churn_pipeline`. Điều này quan trọng vì artifact chứa custom transformer `TelcoFeatureBuilder`; nếu chạy file định nghĩa class trực tiếp, pickle có thể ghi class dưới module `__main__` và process inference khác không load được.

## 4. Chạy Training

Không có CSV:

```bash
python -m src.train_churn
```

Có Telco CSV:

```bash
python -m src.train_churn --csv data/telco_customer_churn.csv
```

Kết quả mong đợi:

```text
artifacts/customer_churn_model.joblib
artifacts/reports/eda_report.json
artifacts/reports/leaderboard.csv
artifacts/reports/metrics_report.json
artifacts/reports/threshold_report_logistic_regression.csv
artifacts/reports/threshold_report_random_forest.csv
artifacts/reports/threshold_report_gradient_boosting.csv
artifacts/reports/error_analysis/false_positives.csv
artifacts/reports/error_analysis/false_negatives.csv
artifacts/reports/error_analysis/slice_metrics.csv
```

## 5. Thử Inference

Sau khi train xong:

```python
from pathlib import Path

from src.churn_pipeline import predict_customer_churn


customer = {
    "customerID": "CUST_999999",
    "gender": "Female",
    "SeniorCitizen": 0,
    "Partner": "Yes",
    "Dependents": "No",
    "tenure": 12,
    "PhoneService": "Yes",
    "InternetService": "Fiber optic",
    "Contract": "Month-to-month",
    "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
    "MonthlyCharges": 89.9,
    "TotalCharges": 1020.3,
}

result = predict_customer_churn(customer, Path("artifacts/customer_churn_model.joblib"))
print(result)
```

Response cần có dạng:

```json
{
  "customer_id": "CUST_999999",
  "churn_probability": 0.7312,
  "will_churn": true,
  "risk_tier": "high",
  "threshold": 0.45,
  "model_name": "gradient_boosting",
  "model_version": "customer-churn-v1",
  "schema_version": "telco-churn-v1"
}
```

## 6. Bài Tập Mở Rộng

1. Thêm unit test cho `normalize_telco_frame()`:
   - Missing column phải raise `ValueError`.
   - `TotalCharges=" "` phải thành missing.
   - `Churn="Yes"` phải thành `1`.

2. Thêm test cho inference contract:
   - Payload đủ field trả về đầy đủ keys.
   - Payload thiếu `MonthlyCharges` phải fail.
   - Category mới trong `PaymentMethod` không làm model crash.

3. So sánh threshold objectives:
   - `min_recall=0.60`
   - `min_recall=0.75`
   - `min_recall=0.90`

4. Thêm calibration:
   - Dùng `CalibratedClassifierCV` cho model tốt nhất.
   - So sánh calibration curve hoặc Brier score.

5. Thêm time-based split nếu dataset của bạn có timestamp:
   - Train trên tháng cũ.
   - Validation trên tháng kế tiếp.
   - Test trên tháng mới nhất.

6. Viết README thật:
   - Không chỉ liệt kê command.
   - Phải có trade-off, limitation và production readiness.

## 7. Câu Hỏi Review

1. Vì sao `TelcoFeatureBuilder` nằm trong `Pipeline` thay vì gọi thủ công ở notebook?
2. Vì sao threshold được tune trên validation set, không phải test set?
3. Nếu model có Average Precision cao nhưng recall thấp tại threshold đã chọn, bạn xử lý thế nào?
4. `OneHotEncoder(handle_unknown="ignore")` giải quyết vấn đề gì và không giải quyết vấn đề gì?
5. Nếu service nhận category mới liên tục, bạn monitor metric nào?
6. Nếu Random Forest tốt hơn Logistic Regression 0.5 điểm AP nhưng latency p95 gấp 20 lần, bạn chọn gì trong batch scoring và realtime API?
7. Điều kiện nào còn thiếu trước khi gọi pipeline này là production-ready?
8. Vì sao không được nhận file `.joblib` từ user rồi load trực tiếp trong service?
9. Vì sao training launcher phải import module chứa custom transformer thay vì chạy file đó trực tiếp?

## 8. Tiêu Chí Chấm

| Hạng mục | Đạt |
|---|---|
| Schema validation | Fail fast khi thiếu cột, normalize type đúng |
| EDA | Có target distribution, missing, segment churn rate |
| Pipeline | Có `Pipeline`, `ColumnTransformer`, transformer chung training/inference |
| Models | Ít nhất 3 models, có Logistic Regression baseline |
| Metrics | Có ROC-AUC, Average Precision, precision, recall, F1, confusion matrix |
| Threshold | Tune trên validation set, có business objective |
| Error analysis | Có FP/FN và slice metrics |
| Artifact | Save model + metadata + threshold + schema |
| Inference | Function nhận `dict`, trả contract rõ ràng |
| Production notes | Có trade-off, limitation, monitoring, rollback |
