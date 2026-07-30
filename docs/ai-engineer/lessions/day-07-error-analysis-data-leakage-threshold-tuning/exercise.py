from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
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
TARGET = "churn"
MODEL_VERSION = "churn-logreg-calibrated-v1"
THRESHOLD_VERSION = "threshold-recall75-profit-v1"
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"

NUMERIC_COLS = [
    "tenure_months",
    "monthly_charges",
    "support_tickets_90d",
    "usage_drop_pct",
    "payment_failures_90d",
    "is_senior",
]
CATEGORICAL_COLS = ["contract", "internet_service", "region"]
FEATURE_COLS = NUMERIC_COLS + CATEGORICAL_COLS
THRESHOLDS = np.round(np.arange(0.30, 0.801, 0.05), 2)


def build_churn_dataset(n_samples: int = 12_000) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_STATE)

    tenure_months = rng.integers(1, 73, n_samples)
    monthly_charges = np.clip(rng.normal(72, 22, n_samples), 20, 160).round(2)
    support_tickets_90d = rng.poisson(0.8, n_samples)
    usage_drop_pct = np.clip(rng.beta(2.5, 7.0, n_samples), 0, 1)
    payment_failures_90d = rng.binomial(3, 0.09, n_samples)
    is_senior = rng.binomial(1, 0.16, n_samples)

    contract = rng.choice(
        ["month_to_month", "one_year", "two_year"],
        size=n_samples,
        p=[0.58, 0.25, 0.17],
    )
    internet_service = rng.choice(
        ["dsl", "fiber", "none"],
        size=n_samples,
        p=[0.32, 0.53, 0.15],
    )
    region = rng.choice(["north", "south", "central"], size=n_samples, p=[0.40, 0.35, 0.25])

    logit = -2.45
    logit += 1.25 * (contract == "month_to_month")
    logit -= 0.85 * (contract == "two_year")
    logit += 0.75 * (internet_service == "fiber")
    logit -= 0.65 * (internet_service == "none")
    logit += 0.024 * (monthly_charges - 70)
    logit -= 0.030 * tenure_months
    logit += 0.62 * support_tickets_90d
    logit += 2.8 * usage_drop_pct
    logit += 0.58 * payment_failures_90d
    logit += 0.25 * is_senior
    logit += 0.18 * (region == "south")

    churn_probability = 1 / (1 + np.exp(-logit))
    churn = rng.binomial(1, np.clip(churn_probability, 0.01, 0.95))

    df = pd.DataFrame(
        {
            "customer_id": [f"CUST_{i:06d}" for i in range(n_samples)],
            "tenure_months": tenure_months,
            "monthly_charges": monthly_charges,
            "support_tickets_90d": support_tickets_90d,
            "usage_drop_pct": usage_drop_pct.round(4),
            "payment_failures_90d": payment_failures_90d,
            "is_senior": is_senior,
            "contract": contract,
            "internet_service": internet_service,
            "region": region,
            TARGET: churn,
        }
    )
    df["tenure_bucket"] = pd.cut(
        df["tenure_months"],
        bins=[0, 6, 12, 24, 72],
        labels=["0-6", "7-12", "13-24", "25+"],
        include_lowest=True,
    ).astype(str)
    df["monthly_charge_bucket"] = pd.cut(
        df["monthly_charges"],
        bins=[0, 50, 90, 200],
        labels=["low", "medium", "high"],
        include_lowest=True,
    ).astype(str)
    return df


def split_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_valid_df, test_df = train_test_split(
        df,
        test_size=0.20,
        stratify=df[TARGET],
        random_state=RANDOM_STATE,
    )
    train_df, valid_df = train_test_split(
        train_valid_df,
        test_size=0.25,
        stratify=train_valid_df[TARGET],
        random_state=RANDOM_STATE,
    )
    return (
        train_df.reset_index(drop=True),
        valid_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def build_pipeline(
    numeric_cols: list[str] | None = None,
    categorical_cols: list[str] | None = None,
) -> Pipeline:
    numeric_cols = numeric_cols or NUMERIC_COLS
    categorical_cols = categorical_cols or CATEGORICAL_COLS

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_cols),
            ("cat", categorical_transformer, categorical_cols),
        ]
    )
    classifier = LogisticRegression(
        max_iter=1_000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    return Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("model", classifier),
        ]
    )


def confusion_counts(y_true: pd.Series | np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def threshold_metrics(
    y_true: pd.Series | np.ndarray,
    proba: np.ndarray,
    threshold: float,
    tp_retained_value: int = 300,
    fp_offer_cost: int = 40,
    fn_lost_value: int = 1_200,
) -> dict[str, Any]:
    y_pred = (proba >= threshold).astype(int)
    counts = confusion_counts(y_true, y_pred)
    expected_profit = (
        counts["tp"] * tp_retained_value
        - counts["fp"] * fp_offer_cost
        - counts["fn"] * fn_lost_value
    )
    return {
        "threshold": float(threshold),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "predicted_positive_rate": float(y_pred.mean()),
        "expected_profit": int(expected_profit),
        **counts,
    }


def threshold_sweep(y_true: pd.Series | np.ndarray, proba: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame([threshold_metrics(y_true, proba, threshold) for threshold in THRESHOLDS])


def choose_threshold(threshold_df: pd.DataFrame, min_recall: float = 0.75) -> pd.Series:
    candidates = threshold_df[threshold_df["recall"] >= min_recall]
    if candidates.empty:
        candidates = threshold_df
    return candidates.sort_values(
        ["expected_profit", "precision", "f1"],
        ascending=[False, False, False],
    ).iloc[0]


def build_result_frame(df: pd.DataFrame, proba: np.ndarray, threshold: float) -> pd.DataFrame:
    result = df[
        [
            "customer_id",
            "contract",
            "internet_service",
            "region",
            "tenure_bucket",
            "monthly_charge_bucket",
            "monthly_charges",
            "support_tickets_90d",
            "usage_drop_pct",
            "payment_failures_90d",
            TARGET,
        ]
    ].copy()
    result = result.rename(columns={TARGET: "y_true"})
    result["proba"] = proba
    result["y_pred"] = (result["proba"] >= threshold).astype(int)
    result["distance_to_threshold"] = (result["proba"] - threshold).abs()
    return result


def slice_metrics(
    result_df: pd.DataFrame,
    segment_col: str,
    threshold: float,
    min_count: int = 100,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for segment_value, group in result_df.groupby(segment_col):
        if len(group) < min_count:
            continue

        y_true = group["y_true"].to_numpy()
        y_pred = (group["proba"].to_numpy() >= threshold).astype(int)
        counts = confusion_counts(y_true, y_pred)
        rows.append(
            {
                "segment_col": segment_col,
                "segment": segment_value,
                "count": len(group),
                "actual_positive_rate": float(y_true.mean()),
                "predicted_positive_rate": float(y_pred.mean()),
                "precision": precision_score(y_true, y_pred, zero_division=0),
                "recall": recall_score(y_true, y_pred, zero_division=0),
                "f1": f1_score(y_true, y_pred, zero_division=0),
                **counts,
            }
        )
    return pd.DataFrame(rows).sort_values(["f1", "recall", "count"], ascending=[True, True, False])


def top_false_positives(result_df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    return (
        result_df[(result_df["y_true"] == 0) & (result_df["y_pred"] == 1)]
        .sort_values("proba", ascending=False)
        .head(limit)
    )


def top_false_negatives(result_df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    return (
        result_df[(result_df["y_true"] == 1) & (result_df["y_pred"] == 0)]
        .sort_values("proba", ascending=True)
        .head(limit)
    )


def near_threshold_samples(result_df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    return result_df.sort_values("distance_to_threshold", ascending=True).head(limit)


def calibration_table(y_true: pd.Series | np.ndarray, proba: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    calibration_df = pd.DataFrame({"y_true": y_true, "proba": proba})
    calibration_df["bin"] = pd.cut(
        calibration_df["proba"],
        bins=np.linspace(0, 1, n_bins + 1),
        include_lowest=True,
    )
    return (
        calibration_df.groupby("bin", observed=False)
        .agg(
            count=("y_true", "size"),
            avg_predicted_probability=("proba", "mean"),
            actual_positive_rate=("y_true", "mean"),
        )
        .reset_index()
    )


def distribution_shift_report(reference_df: pd.DataFrame, current_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for col in NUMERIC_COLS:
        ref_mean = reference_df[col].mean()
        cur_mean = current_df[col].mean()
        ref_std = reference_df[col].std() or 1.0
        rows.append(
            {
                "feature": col,
                "check": "mean_z_delta",
                "reference": ref_mean,
                "current": cur_mean,
                "delta": (cur_mean - ref_mean) / ref_std,
            }
        )

    for col in CATEGORICAL_COLS:
        ref_share = reference_df[col].value_counts(normalize=True)
        cur_share = current_df[col].value_counts(normalize=True)
        categories = sorted(set(ref_share.index).union(cur_share.index))
        max_delta = max(abs(cur_share.get(cat, 0.0) - ref_share.get(cat, 0.0)) for cat in categories)
        rows.append(
            {
                "feature": col,
                "check": "max_category_share_delta",
                "reference": None,
                "current": None,
                "delta": max_delta,
            }
        )
    return pd.DataFrame(rows).sort_values("delta", key=lambda series: series.abs(), ascending=False)


def simulate_distribution_shift(test_df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_STATE + 100)
    shifted = test_df.copy()
    shifted["monthly_charges"] = np.clip(shifted["monthly_charges"] + 18, 20, 180)
    mask = rng.random(len(shifted)) < 0.18
    shifted.loc[mask, "contract"] = "month_to_month"
    return shifted


def leakage_demo(df: pd.DataFrame) -> dict[str, float]:
    leaked_df = df.copy()
    rng = np.random.default_rng(RANDOM_STATE + 7)
    leaked_df["cancel_request_seen"] = np.where(
        leaked_df[TARGET].to_numpy() == 1,
        rng.binomial(1, 0.92, len(leaked_df)),
        rng.binomial(1, 0.03, len(leaked_df)),
    )

    train_df, _, test_df = split_dataset(leaked_df)
    clean_model = build_pipeline()
    clean_model.fit(train_df[FEATURE_COLS], train_df[TARGET])
    clean_proba = clean_model.predict_proba(test_df[FEATURE_COLS])[:, 1]

    leaked_numeric_cols = NUMERIC_COLS + ["cancel_request_seen"]
    leaked_features = leaked_numeric_cols + CATEGORICAL_COLS
    leaked_model = build_pipeline(numeric_cols=leaked_numeric_cols, categorical_cols=CATEGORICAL_COLS)
    leaked_model.fit(train_df[leaked_features], train_df[TARGET])
    leaked_proba = leaked_model.predict_proba(test_df[leaked_features])[:, 1]

    return {
        "clean_roc_auc": roc_auc_score(test_df[TARGET], clean_proba),
        "clean_average_precision": average_precision_score(test_df[TARGET], clean_proba),
        "leaked_roc_auc": roc_auc_score(test_df[TARGET], leaked_proba),
        "leaked_average_precision": average_precision_score(test_df[TARGET], leaked_proba),
    }


def dataset_signature(df: pd.DataFrame) -> str:
    payload = {
        "rows": len(df),
        "columns": list(df.columns),
        "target_rate": round(float(df[TARGET].mean()), 6),
        "feature_nulls": {col: int(df[col].isna().sum()) for col in FEATURE_COLS},
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def to_native(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: to_native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_native(item) for item in value]
    if isinstance(value, tuple):
        return [to_native(item) for item in value]
    if isinstance(value, pd.Series):
        return {key: to_native(item) for key, item in value.to_dict().items()}
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return [to_native(item) for item in value.tolist()]
    return value


def persist_artifacts(
    model: CalibratedClassifierCV,
    threshold: float,
    threshold_row: pd.Series,
    test_summary: dict[str, Any],
    train_df: pd.DataFrame,
) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACT_DIR / f"{MODEL_VERSION}.joblib"
    metadata_path = ARTIFACT_DIR / f"{MODEL_VERSION}.{THRESHOLD_VERSION}.metadata.json"

    feature_contract = {
        "required_columns": FEATURE_COLS,
        "numeric_columns": NUMERIC_COLS,
        "categorical_columns": CATEGORICAL_COLS,
        "categorical_unknown_policy": "ignore",
        "missing_value_policy": {
            "numeric": "median imputation fitted on train",
            "categorical": "most_frequent imputation fitted on train",
        },
    }
    joblib.dump({"model": model, "feature_contract": feature_contract}, model_path)

    metadata = {
        "model_version": MODEL_VERSION,
        "threshold_version": THRESHOLD_VERSION,
        "threshold": threshold,
        "selected_on": "validation",
        "business_objective": "maximize expected profit among thresholds with recall >= 0.75",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_snapshot_id": dataset_signature(train_df),
        "feature_contract": feature_contract,
        "validation_metrics_at_threshold": threshold_row,
        "test_summary": test_summary,
    }
    metadata_path.write_text(
        json.dumps(to_native(metadata), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return model_path, metadata_path


def predict_customer_churn(
    input_json: dict[str, Any],
    model_path: Path | None = None,
    metadata_path: Path | None = None,
) -> dict[str, Any]:
    model_path = model_path or ARTIFACT_DIR / f"{MODEL_VERSION}.joblib"
    metadata_path = metadata_path or ARTIFACT_DIR / f"{MODEL_VERSION}.{THRESHOLD_VERSION}.metadata.json"

    # Security boundary: only load artifacts produced by a trusted training pipeline.
    artifact = joblib.load(model_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    missing = [col for col in FEATURE_COLS if col not in input_json]
    if missing:
        raise ValueError(f"Missing required input columns: {missing}")

    row = pd.DataFrame([{col: input_json[col] for col in FEATURE_COLS}])
    probability = float(artifact["model"].predict_proba(row)[:, 1][0])
    threshold = float(metadata["threshold"])
    return {
        "probability": probability,
        "decision": bool(probability >= threshold),
        "threshold": threshold,
        "model_version": metadata["model_version"],
        "threshold_version": metadata["threshold_version"],
    }


def regression_gate_report(
    test_metrics: dict[str, Any],
    contract_slice: pd.DataFrame,
) -> pd.DataFrame:
    min_contract_recall = float(contract_slice["recall"].min()) if not contract_slice.empty else 0.0
    gates = [
        ("roc_auc", test_metrics["roc_auc"], ">=", 0.70),
        ("average_precision", test_metrics["average_precision"], ">=", 0.35),
        ("recall", test_metrics["threshold_metrics"]["recall"], ">=", 0.65),
        ("precision", test_metrics["threshold_metrics"]["precision"], ">=", 0.25),
        ("predicted_positive_rate", test_metrics["threshold_metrics"]["predicted_positive_rate"], "<=", 0.60),
        ("min_contract_recall", min_contract_recall, ">=", 0.45),
    ]
    rows = []
    for name, actual, op, expected in gates:
        passed = actual >= expected if op == ">=" else actual <= expected
        rows.append(
            {
                "gate": name,
                "actual": actual,
                "operator": op,
                "expected": expected,
                "pass": bool(passed),
            }
        )
    return pd.DataFrame(rows)


def print_df(title: str, df: pd.DataFrame, columns: list[str] | None = None, limit: int | None = None) -> None:
    print(f"\n=== {title} ===")
    view = df[columns] if columns else df
    if limit is not None:
        view = view.head(limit)
    print(view.to_string(index=False))


def main(write_artifacts: bool, enforce_gates: bool) -> None:
    df = build_churn_dataset()
    train_df, valid_df, test_df = split_dataset(df)

    base_model = build_pipeline()
    base_model.fit(train_df[FEATURE_COLS], train_df[TARGET])
    base_valid_proba = base_model.predict_proba(valid_df[FEATURE_COLS])[:, 1]

    calibrated_model = CalibratedClassifierCV(build_pipeline(), method="isotonic", cv=3)
    calibrated_model.fit(train_df[FEATURE_COLS], train_df[TARGET])
    valid_proba = calibrated_model.predict_proba(valid_df[FEATURE_COLS])[:, 1]

    threshold_df = threshold_sweep(valid_df[TARGET], valid_proba)
    chosen = choose_threshold(threshold_df, min_recall=0.75)
    chosen_threshold = float(chosen["threshold"])

    test_proba = calibrated_model.predict_proba(test_df[FEATURE_COLS])[:, 1]
    test_pred = (test_proba >= chosen_threshold).astype(int)
    result_df = build_result_frame(test_df, test_proba, chosen_threshold)

    test_threshold_metrics = threshold_metrics(test_df[TARGET], test_proba, chosen_threshold)
    test_metrics = {
        "roc_auc": roc_auc_score(test_df[TARGET], test_proba),
        "average_precision": average_precision_score(test_df[TARGET], test_proba),
        "brier_score": brier_score_loss(test_df[TARGET], test_proba),
        "threshold_metrics": test_threshold_metrics,
    }

    print(f"Dataset rows: {len(df)}")
    print(f"Train/valid/test: {len(train_df)}/{len(valid_df)}/{len(test_df)}")
    print(f"Target rate: {df[TARGET].mean():.3f}")
    print(f"Base validation Brier score: {brier_score_loss(valid_df[TARGET], base_valid_proba):.4f}")
    print(f"Calibrated validation Brier score: {brier_score_loss(valid_df[TARGET], valid_proba):.4f}")

    print_df(
        "Threshold sweep on validation",
        threshold_df,
        columns=[
            "threshold",
            "precision",
            "recall",
            "f1",
            "predicted_positive_rate",
            "expected_profit",
            "tn",
            "fp",
            "fn",
            "tp",
        ],
    )
    print(f"\nChosen threshold: {chosen_threshold:.2f}")

    print("\n=== Test metrics ===")
    print(json.dumps(to_native(test_metrics), indent=2))
    print("\n=== Confusion matrix on test ===")
    print(confusion_matrix(test_df[TARGET], test_pred, labels=[0, 1]))
    print("\n=== Classification report on test ===")
    print(classification_report(test_df[TARGET], test_pred, zero_division=0))

    contract_slice = slice_metrics(result_df, "contract", chosen_threshold)
    print_df("Slice metrics by contract", contract_slice)
    print_df("Slice metrics by internet_service", slice_metrics(result_df, "internet_service", chosen_threshold))
    print_df("Slice metrics by tenure_bucket", slice_metrics(result_df, "tenure_bucket", chosen_threshold))

    error_columns = [
        "customer_id",
        "contract",
        "internet_service",
        "region",
        "tenure_bucket",
        "monthly_charges",
        "support_tickets_90d",
        "usage_drop_pct",
        "payment_failures_90d",
        "y_true",
        "y_pred",
        "proba",
    ]
    print_df("Top false positives", top_false_positives(result_df), columns=error_columns, limit=20)
    print_df("Top false negatives", top_false_negatives(result_df), columns=error_columns, limit=20)
    print_df("Near-threshold samples", near_threshold_samples(result_df), columns=error_columns, limit=20)

    print_df("Calibration table on test", calibration_table(test_df[TARGET], test_proba))

    shifted_df = simulate_distribution_shift(test_df)
    print_df("Distribution shift report", distribution_shift_report(train_df, shifted_df))

    leakage_metrics = leakage_demo(df)
    print("\n=== Leakage demo ===")
    print(json.dumps(to_native(leakage_metrics), indent=2))
    print("The leaked feature looks great offline because it encodes post-outcome information.")

    gate_df = regression_gate_report(test_metrics, contract_slice)
    print_df("Baseline regression gates", gate_df)
    failed_gates = gate_df[~gate_df["pass"]]
    if enforce_gates and not failed_gates.empty:
        raise AssertionError(f"Regression gates failed: {failed_gates['gate'].tolist()}")

    if write_artifacts:
        model_path, metadata_path = persist_artifacts(
            calibrated_model,
            chosen_threshold,
            chosen,
            test_metrics,
            train_df,
        )
        print(f"\nWrote model artifact: {model_path}")
        print(f"Wrote metadata artifact: {metadata_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--enforce-gates", action="store_true")
    args = parser.parse_args()
    main(write_artifacts=args.write_artifacts, enforce_gates=args.enforce_gates)
