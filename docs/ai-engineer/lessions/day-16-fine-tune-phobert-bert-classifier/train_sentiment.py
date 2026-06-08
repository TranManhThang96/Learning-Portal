from __future__ import annotations

import json
import os
import platform
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from datasets import Dataset, DatasetDict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, Trainer, TrainingArguments

SEED = int(os.getenv("SEED", "42"))
MODEL_ID = os.getenv("MODEL_ID", "distilbert-base-multilingual-cased")
DATA_PATH = os.getenv("DATA_PATH", "")
OUT_DIR = Path(os.getenv("OUT_DIR", "artifacts/sentiment_classifier"))
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "128"))
EPOCHS = float(os.getenv("EPOCHS", "2"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))

LABELS = ["negative", "neutral", "positive"]
LABEL2ID = {label: idx for idx, label in enumerate(LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def normalize_text(text: str) -> str:
    return " ".join(str(text).strip().split())


def sample_data() -> pd.DataFrame:
    rows = [
        ("sản phẩm rất tốt, giao hàng nhanh", "positive"),
        ("đóng gói cẩn thận, hàng đúng mô tả", "positive"),
        ("chất lượng tốt, sẽ mua lại", "positive"),
        ("shop hỗ trợ nhanh và lịch sự", "positive"),
        ("hàng đẹp hơn mong đợi", "positive"),
        ("giá ổn, dùng mượt", "positive"),
        ("hàng bị lỗi, không đúng mô tả", "negative"),
        ("đóng gói tệ, sản phẩm bị vỡ", "negative"),
        ("giao hàng quá chậm", "negative"),
        ("chất lượng kém, rất thất vọng", "negative"),
        ("shop phản hồi chậm, xử lý không ổn", "negative"),
        ("mua về dùng hai ngày đã hỏng", "negative"),
        ("sản phẩm tạm được", "neutral"),
        ("bình thường, không có gì đặc biệt", "neutral"),
        ("giao hàng đúng hẹn", "neutral"),
        ("mới dùng nên chưa đánh giá", "neutral"),
        ("đóng gói bình thường", "neutral"),
        ("sản phẩm giống hình", "neutral"),
    ]
    variants: list[tuple[str, str, str]] = []
    prefixes = ["", "review: ", "khách nói: "]
    suffixes = ["", " lần sau sẽ cân nhắc", " mình đặt cho gia đình"]
    for row_index, (text, label) in enumerate(rows):
        group_id = f"synthetic-{row_index:03d}"
        for prefix in prefixes:
            for suffix in suffixes:
                variants.append((normalize_text(prefix + text + suffix), label, group_id))
    return (
        pd.DataFrame(variants, columns=["text", "label", "group_id"])
        .sample(frac=1, random_state=SEED)
        .reset_index(drop=True)
    )


def load_data() -> pd.DataFrame:
    if DATA_PATH and Path(DATA_PATH).exists():
        df = pd.read_csv(DATA_PATH)
        missing = {"text", "label"} - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        columns = ["text", "label"]
        if "group_id" in df.columns:
            columns.append("group_id")
        df = df[columns].copy()
    else:
        df = sample_data()

    df["text"] = df["text"].map(normalize_text)
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    if "group_id" in df.columns:
        if df["group_id"].isna().any():
            raise ValueError("group_id must not be null when the column is provided.")
        df["group_id"] = df["group_id"].astype(str).str.strip()
        if (df["group_id"] == "").any():
            raise ValueError("group_id must not be blank when the column is provided.")
    df = df[(df["text"] != "") & (df["label"] != "")].drop_duplicates()

    unknown = sorted(set(df["label"]) - set(LABELS))
    if unknown:
        raise ValueError(f"Unknown labels: {unknown}. Expected only: {LABELS}")

    min_count = df["label"].value_counts().min()
    if min_count < 3:
        raise ValueError("Each label needs at least 3 rows for stratified train/validation/test split.")

    df["label_id"] = df["label"].map(LABEL2ID).astype(int)
    return df.reset_index(drop=True)


def split_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "group_id" in df.columns:
        group_labels = df.groupby("group_id", as_index=False)["label_id"].agg(
            lambda values: values.iloc[0] if values.nunique() == 1 else -1
        )
        if (group_labels["label_id"] == -1).any():
            raise ValueError("Each group_id must contain exactly one label.")

        min_group_count = group_labels["label_id"].value_counts().min()
        if min_group_count < 3:
            raise ValueError("Each label needs at least 3 groups for grouped train/validation/test split.")

        rng = np.random.default_rng(SEED)
        split_group_ids: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
        for _, label_groups in group_labels.groupby("label_id"):
            group_ids = label_groups["group_id"].astype(str).to_numpy(copy=True)
            rng.shuffle(group_ids)
            holdout_per_split = max(1, int(round(len(group_ids) * 0.2)))
            max_holdout_per_split = (len(group_ids) - 1) // 2
            holdout_per_split = min(holdout_per_split, max_holdout_per_split)

            split_group_ids["validation"].extend(group_ids[:holdout_per_split].tolist())
            split_group_ids["test"].extend(group_ids[holdout_per_split : 2 * holdout_per_split].tolist())
            split_group_ids["train"].extend(group_ids[2 * holdout_per_split :].tolist())

        def rows_for(group_ids: list[str]) -> pd.DataFrame:
            return df[df["group_id"].isin(group_ids)].reset_index(drop=True)

        return (
            rows_for(split_group_ids["train"]),
            rows_for(split_group_ids["validation"]),
            rows_for(split_group_ids["test"]),
        )

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=SEED, stratify=df["label_id"])
    train_df, val_df = train_test_split(train_df, test_size=0.25, random_state=SEED, stratify=train_df["label_id"])
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def metric_payload(y_true: np.ndarray, y_pred: np.ndarray, model_name: str) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro")), 6),
        "classification_report": classification_report(y_true, y_pred, target_names=LABELS, output_dict=True, zero_division=0),
        "confusion_matrix_labels": LABELS,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(range(len(LABELS)))).tolist(),
    }


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def train_baseline(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict[str, Any]:
    baseline = Pipeline(
        steps=[
            (
                "features",
                FeatureUnion(
                    [
                        ("word_tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=50000)),
                        ("char_tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, max_features=50000)),
                    ]
                ),
            ),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", n_jobs=1)),
        ]
    )
    baseline.fit(train_df["text"], train_df["label_id"])
    pred = baseline.predict(test_df["text"])
    report = metric_payload(test_df["label_id"].to_numpy(), pred, "tfidf_logistic_regression")

    joblib.dump(baseline, OUT_DIR / "baseline.joblib")
    save_json(OUT_DIR / "baseline_metrics.json", report)
    print("\n== Baseline TF-IDF + Logistic Regression ==")
    print(json.dumps({"accuracy": report["accuracy"], "f1_macro": report["f1_macro"]}, indent=2))
    return report


def build_dataset(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> DatasetDict:
    keep = ["text", "label_id"]
    return DatasetDict(
        {
            "train": Dataset.from_pandas(train_df[keep], preserve_index=False),
            "validation": Dataset.from_pandas(val_df[keep], preserve_index=False),
            "test": Dataset.from_pandas(test_df[keep], preserve_index=False),
        }
    )


def compute_metrics(eval_pred: Any) -> dict[str, float]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": float(accuracy_score(labels, preds)),
        "f1_macro": float(f1_score(labels, preds, average="macro")),
    }


def training_args() -> TrainingArguments:
    kwargs = dict(
        output_dir=str(OUT_DIR / "checkpoints"),
        learning_rate=2e-5,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        weight_decay=0.01,
        logging_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        save_strategy="epoch",
        report_to="none",
        seed=SEED,
    )
    try:
        return TrainingArguments(eval_strategy="epoch", **kwargs)
    except TypeError:
        return TrainingArguments(evaluation_strategy="epoch", **kwargs)


def fine_tune_transformer(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> dict[str, Any]:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    ds = build_dataset(train_df, val_df, test_df)

    def tokenize(batch: dict[str, list[str]]) -> dict[str, Any]:
        return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

    tokenized = ds.map(tokenize, batched=True)
    tokenized = tokenized.rename_column("label_id", "labels").remove_columns(["text"])

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    trainer_kwargs = dict(
        model=model,
        args=training_args(),
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )
    try:
        trainer = Trainer(processing_class=tokenizer, **trainer_kwargs)
    except TypeError:
        trainer = Trainer(tokenizer=tokenizer, **trainer_kwargs)

    print("\n== Fine-tune Transformer ==")
    trainer.train()
    test_output = trainer.predict(tokenized["test"])
    preds = np.argmax(test_output.predictions, axis=-1)
    labels = test_output.label_ids
    report = metric_payload(labels, preds, MODEL_ID)
    report["max_length"] = MAX_LENGTH

    model_dir = OUT_DIR / "best_model"
    model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_dir))
    tokenizer.save_pretrained(str(model_dir))
    save_json(OUT_DIR / "transformer_metrics.json", report)

    errors = test_df.copy()
    errors["pred_label_id"] = preds
    errors["pred_label"] = errors["pred_label_id"].map(ID2LABEL)
    errors = errors[errors["label_id"] != errors["pred_label_id"]]
    errors.to_csv(OUT_DIR / "errors.csv", index=False)

    print(json.dumps({"accuracy": report["accuracy"], "f1_macro": report["f1_macro"]}, indent=2))
    return report


def write_metadata(df: pd.DataFrame, train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, summary: dict[str, Any]) -> None:
    labels_payload = {"labels": LABELS, "label2id": LABEL2ID, "id2label": {str(k): v for k, v in ID2LABEL.items()}}
    save_json(OUT_DIR / "labels.json", labels_payload)

    manifest = {
        "artifact_name": "vietnamese-sentiment-classifier",
        "version": os.getenv("MODEL_VERSION", "sentiment-v1"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": "text-classification",
        "model_id": MODEL_ID,
        "max_length": MAX_LENGTH,
        "seed": SEED,
        "labels": LABELS,
        "data": {
            "data_path": DATA_PATH or "synthetic_fallback",
            "split_strategy": (
                "grouped_target_60_20_20" if "group_id" in df.columns else "stratified_random_60_20_20"
            ),
            "total_size": int(len(df)),
            "train_size": int(len(train_df)),
            "validation_size": int(len(val_df)),
            "test_size": int(len(test_df)),
            "label_distribution": df["label"].value_counts().to_dict(),
        },
        "metrics": {
            "baseline_f1_macro": summary["baseline"]["f1_macro"],
            "transformer_f1_macro": summary["transformer"]["f1_macro"],
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        },
    }
    save_json(OUT_DIR / "manifest.json", manifest)

    model_card = f"""# Vietnamese Sentiment Classifier

## Intended use

Classify Vietnamese customer text into `negative`, `neutral`, `positive`.

## Training data

- Source: {DATA_PATH or "synthetic fallback for hands-on only"}
- Total rows: {len(df)}
- Labels: {", ".join(LABELS)}

## Metrics

- Baseline macro F1: {summary["baseline"]["f1_macro"]}
- Transformer macro F1: {summary["transformer"]["f1_macro"]}

## Production decision

This artifact can be considered for production only after validation on representative real data, license review, PII policy, latency benchmark, monitoring, and rollback planning. Synthetic fallback data is not sufficient for production approval.
"""
    (OUT_DIR / "model_card.md").write_text(model_card, encoding="utf-8")


def main() -> None:
    set_seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    train_df, val_df, test_df = split_data(df)

    print("dataset_size:", len(df))
    print("train/validation/test:", len(train_df), len(val_df), len(test_df))
    print("model_id:", MODEL_ID)
    print("max_length:", MAX_LENGTH)

    baseline_report = train_baseline(train_df, test_df)
    transformer_report = fine_tune_transformer(train_df, val_df, test_df)
    summary = {"baseline": baseline_report, "transformer": transformer_report}
    save_json(OUT_DIR / "comparison.json", summary)
    write_metadata(df, train_df, val_df, test_df, summary)

    print("\n== Comparison ==")
    print(json.dumps(
        {
            "baseline_f1_macro": baseline_report["f1_macro"],
            "transformer_f1_macro": transformer_report["f1_macro"],
            "artifact_dir": str(OUT_DIR),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
