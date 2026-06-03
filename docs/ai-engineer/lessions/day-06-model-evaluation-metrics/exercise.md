# Day 6 Exercise: Fraud Metrics Pipeline Với scikit-learn

Bài tập này giúp bạn xây một evaluation pipeline gần production cho fraud detection. Dataset là synthetic để chạy được nhanh, nhưng workflow phản ánh cách làm thật: split đúng, `Pipeline`, preprocessing nhất quán, score metrics, threshold sweep, expected value và capacity reasoning.

## 1. Chuẩn Bị

Cài thư viện:

```bash
pip install numpy pandas scikit-learn
```

Tạo file local tùy ý, ví dụ `fraud_metrics_day06.py`, rồi chép code dưới đây để chạy.

## 2. Full Script

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.datasets import make_classification
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


RANDOM_STATE = 42


@dataclass(frozen=True)
class BusinessAssumptions:
    fraud_loss_usd: float = 500.0
    review_cost_usd: float = 4.0
    false_positive_friction_usd: float = 15.0
    daily_transaction_volume: int = 100_000
    analyst_capacity_per_day: int = 300


def make_fraud_like_dataset(
    n_samples: int = 60_000,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Create an imbalanced fraud-like dataset with numeric and categorical features."""
    rng = np.random.default_rng(random_state)

    X_num, y = make_classification(
        n_samples=n_samples,
        n_features=10,
        n_informative=5,
        n_redundant=2,
        n_clusters_per_class=3,
        weights=[0.985, 0.015],
        class_sep=1.15,
        flip_y=0.01,
        random_state=random_state,
    )

    df = pd.DataFrame(X_num, columns=[f"numeric_{i:02d}" for i in range(X_num.shape[1])])

    # Amount is intentionally skewed, like real transaction amount.
    amount = np.exp(np.clip(df["numeric_00"] + 3.0, 0.0, 8.0))
    amount += rng.gamma(shape=2.0, scale=20.0, size=n_samples)
    df["amount_usd"] = amount.round(2)
    df["hour_of_day"] = rng.integers(0, 24, size=n_samples)
    df["account_age_days"] = rng.integers(1, 2_000, size=n_samples)

    merchant_categories = np.array(
        ["grocery", "travel", "electronics", "gaming", "gift_card", "crypto", "fashion"]
    )
    df["merchant_category"] = rng.choice(
        merchant_categories,
        size=n_samples,
        p=[0.30, 0.15, 0.18, 0.12, 0.10, 0.05, 0.10],
    )

    payment_methods = np.array(["card", "wallet", "bank_transfer", "bnpl"])
    df["payment_method"] = rng.choice(payment_methods, size=n_samples, p=[0.68, 0.18, 0.10, 0.04])

    countries = np.array(["VN", "US", "SG", "ID", "TH", "BR", "NG"])
    df["country"] = rng.choice(countries, size=n_samples, p=[0.42, 0.18, 0.08, 0.12, 0.10, 0.06, 0.04])

    # Inject business-shaped signal into categorical fields without making the task trivial.
    fraud_idx = y == 1
    df.loc[fraud_idx, "merchant_category"] = rng.choice(
        ["gift_card", "crypto", "electronics", "gaming"],
        size=int(fraud_idx.sum()),
        p=[0.35, 0.30, 0.20, 0.15],
    )
    df.loc[fraud_idx, "payment_method"] = rng.choice(
        ["wallet", "card", "bnpl"],
        size=int(fraud_idx.sum()),
        p=[0.45, 0.35, 0.20],
    )

    # Simulate a few missing values to force the pipeline to handle real-world input.
    missing_mask = rng.random(n_samples) < 0.01
    df.loc[missing_mask, "account_age_days"] = np.nan
    return df, y


def build_model(numeric_features: list[str], categorical_features: list[str]) -> Pipeline:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("one_hot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocess = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocess", preprocess),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2_000,
                    n_jobs=None,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def evaluate_threshold(
    y_true: np.ndarray,
    y_score: np.ndarray,
    threshold: float,
    assumptions: BusinessAssumptions,
) -> dict[str, float | bool]:
    y_pred = (y_score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    alerts = tp + fp
    scale = assumptions.daily_transaction_volume / len(y_true)

    prevented_loss = tp * assumptions.fraud_loss_usd
    missed_loss = fn * assumptions.fraud_loss_usd
    review_cost = alerts * assumptions.review_cost_usd
    false_positive_friction = fp * assumptions.false_positive_friction_usd
    net_value = prevented_loss - review_cost - false_positive_friction

    alerts_per_day = alerts * scale
    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "alerts": int(alerts),
        "alerts_per_day": alerts_per_day,
        "missed_loss_per_day": missed_loss * scale,
        "net_value_per_day": net_value * scale,
        "capacity_ok": alerts_per_day <= assumptions.analyst_capacity_per_day,
    }


def build_threshold_report(
    y_true: np.ndarray,
    y_score: np.ndarray,
    assumptions: BusinessAssumptions,
) -> pd.DataFrame:
    thresholds = np.round(np.linspace(0.01, 0.99, 99), 2)
    rows = [evaluate_threshold(y_true, y_score, threshold, assumptions) for threshold in thresholds]
    return pd.DataFrame(rows)


def print_score_metrics(y_true: np.ndarray, y_score: np.ndarray) -> None:
    positive_rate = y_true.mean()
    print("\n=== Score metrics ===")
    print(f"Positive rate:      {positive_rate:.4f}")
    print(f"ROC-AUC:            {roc_auc_score(y_true, y_score):.4f}")
    print(f"PR-AUC / AP:        {average_precision_score(y_true, y_score):.4f}")

    precision, recall, pr_thresholds = precision_recall_curve(y_true, y_score)
    f1_values = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    best_idx = int(np.argmax(f1_values))
    print(f"Best F1 threshold:  {pr_thresholds[best_idx]:.4f}")
    print(f"Best F1 from curve: {f1_values[best_idx]:.4f}")


def run_classification_experiment() -> None:
    assumptions = BusinessAssumptions()
    X, y = make_fraud_like_dataset()

    numeric_features = X.select_dtypes(include="number").columns.tolist()
    categorical_features = X.select_dtypes(exclude="number").columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    model = build_model(numeric_features, categorical_features)
    model.fit(X_train, y_train)
    y_score = model.predict_proba(X_test)[:, 1]

    print_score_metrics(y_test, y_score)

    report = build_threshold_report(y_test, y_score, assumptions)
    columns = [
        "threshold",
        "precision",
        "recall",
        "f1",
        "tp",
        "fp",
        "fn",
        "alerts_per_day",
        "net_value_per_day",
        "capacity_ok",
    ]

    print("\n=== Selected thresholds ===")
    selected = report[report["threshold"].isin([0.10, 0.20, 0.30, 0.50, 0.70, 0.90])]
    print(selected[columns].to_string(index=False))

    best_value = report.sort_values("net_value_per_day", ascending=False).iloc[0]
    print("\n=== Best threshold by expected net value ===")
    print(best_value[columns].to_string())

    capacity_candidates = report[report["capacity_ok"]]
    if capacity_candidates.empty:
        print("\nNo threshold satisfies analyst capacity. Consider top-N review instead of threshold.")
    else:
        best_capacity = capacity_candidates.sort_values("net_value_per_day", ascending=False).iloc[0]
        print("\n=== Best threshold with capacity constraint ===")
        print(best_capacity[columns].to_string())

    high_recall_candidates = report[report["recall"] >= 0.80]
    if not high_recall_candidates.empty:
        best_high_recall = high_recall_candidates.sort_values(
            "net_value_per_day",
            ascending=False,
        ).iloc[0]
        print("\n=== Best threshold with recall >= 0.80 ===")
        print(best_high_recall[columns].to_string())


def run_regression_metric_mini_demo() -> None:
    y_true = np.array([100, 120, 130, 90, 600, 80], dtype=float)
    y_pred = np.array([105, 110, 125, 100, 420, 82], dtype=float)

    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    mape = mean_absolute_percentage_error(y_true, y_pred)

    print("\n=== Regression metric mini demo ===")
    print(f"MAE:  {mae:.2f}")
    print(f"MSE:  {mse:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"MAPE: {mape:.2%}")


def recall_at_k(relevant: set[str], ranked: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(relevant.intersection(ranked[:k])) / len(relevant)


def reciprocal_rank_at_k(relevant: set[str], ranked: list[str], k: int) -> float:
    for idx, item_id in enumerate(ranked[:k], start=1):
        if item_id in relevant:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(relevance_by_item: dict[str, int], ranked: list[str], k: int) -> float:
    def dcg(items: list[str]) -> float:
        score = 0.0
        for idx, item_id in enumerate(items, start=1):
            rel = relevance_by_item.get(item_id, 0)
            score += (2**rel - 1) / np.log2(idx + 1)
        return score

    actual = dcg(ranked[:k])
    ideal_items = sorted(relevance_by_item, key=relevance_by_item.get, reverse=True)
    ideal = dcg(ideal_items[:k])
    return 0.0 if ideal == 0 else actual / ideal


def run_ranking_metric_mini_demo() -> None:
    relevant_docs = {"doc_2", "doc_5"}
    ranked_docs = ["doc_9", "doc_2", "doc_7", "doc_5", "doc_1"]
    relevance_grade = {"doc_2": 3, "doc_5": 2, "doc_7": 1}

    print("\n=== Ranking metric mini demo ===")
    print(f"Recall@3: {recall_at_k(relevant_docs, ranked_docs, k=3):.4f}")
    print(f"MRR@5:    {reciprocal_rank_at_k(relevant_docs, ranked_docs, k=5):.4f}")
    print(f"NDCG@5:   {ndcg_at_k(relevance_grade, ranked_docs, k=5):.4f}")


if __name__ == "__main__":
    run_classification_experiment()
    run_regression_metric_mini_demo()
    run_ranking_metric_mini_demo()
```

## 3. Cách Đọc Output

Bạn sẽ thấy ba nhóm output:

1. `Score metrics`: positive rate, ROC-AUC, PR-AUC/average precision, best F1 threshold.
2. `Selected thresholds`: precision/recall/F1, confusion matrix count, alert volume và expected value ở một số threshold.
3. `Best threshold`: threshold tối ưu theo net value, capacity và recall guardrail.

Đừng chỉ chọn threshold có F1 cao nhất. Hãy so sánh với:

- `net_value_per_day`
- `alerts_per_day`
- `capacity_ok`
- `precision`
- `recall`
- `fp` và `fn`

Nếu threshold tối ưu theo net value tạo 2,000 alerts/ngày nhưng analyst chỉ xử lý được 300, threshold đó chưa deploy được. Bạn phải chọn threshold thỏa capacity hoặc đổi policy sang top-N review.

## 4. Bài Tập Bắt Buộc

Các snippet trong phần này nên được đặt bên trong `run_classification_experiment()` sau khi đã có `X_test`, `y_test`, `y_score` và `report`, trừ khi bài tập nói rõ là sửa hàm khác.

### Bài 1: Accuracy Trap

Thêm baseline luôn dự đoán `0`:

```python
y_pred_all_negative = np.zeros_like(y_test)
print(accuracy_score(y_test, y_pred_all_negative))
print(recall_score(y_test, y_pred_all_negative, zero_division=0))
```

Trả lời:

- Accuracy của baseline là bao nhiêu?
- Recall là bao nhiêu?
- Vì sao baseline này không có business value?

### Bài 2: Đổi Cost Assumption

Đổi:

```python
BusinessAssumptions(fraud_loss_usd=5_000.0)
```

So sánh selected threshold trước và sau khi đổi fraud loss.

Trả lời:

- Threshold tối ưu có giảm không?
- Recall có tăng không?
- Alert volume có vượt capacity không?
- Điều này nói gì về trade-off giữa fraud loss và operational cost?

### Bài 3: Capacity 300 Alerts/Ngày

Giữ `analyst_capacity_per_day=300`.

Trả lời:

- Threshold nào có `capacity_ok = True` và `net_value_per_day` cao nhất?
- Nếu không threshold nào vừa đạt recall mong muốn vừa không vượt capacity, bạn sẽ đề xuất gì?

Gợi ý solution:

- Dùng top-N scoring thay vì threshold tuyệt đối.
- Chia tier: auto allow, manual review, step-up auth, auto block.
- Tăng analyst capacity cho high-risk season.
- Thêm feature tốt hơn để tăng precision.

### Bài 4: Precision Guardrail Cho Auto Block

Giả sử auto block cần precision ít nhất 95%. Lọc report:

```python
auto_block_candidates = report[report["precision"] >= 0.95]
```

Trả lời:

- Có threshold nào đạt không?
- Recall ở threshold đó có thấp không?
- Nếu recall thấp nhưng precision cao, action nào phù hợp: auto block hay manual review?

### Bài 5: Segment Analysis

Tạo report theo `merchant_category`:

```python
X_eval = X_test.copy()
X_eval["y_true"] = y_test
X_eval["y_score"] = y_score
X_eval["y_pred"] = (y_score >= 0.5).astype(int)

segment_rows = []
for segment, group in X_eval.groupby("merchant_category"):
    if group["y_true"].nunique() < 2:
        continue
    segment_rows.append(
        {
            "merchant_category": segment,
            "rows": len(group),
            "positive_rate": group["y_true"].mean(),
            "precision": precision_score(group["y_true"], group["y_pred"], zero_division=0),
            "recall": recall_score(group["y_true"], group["y_pred"], zero_division=0),
            "roc_auc": roc_auc_score(group["y_true"], group["y_score"]),
            "average_precision": average_precision_score(group["y_true"], group["y_score"]),
        }
    )

segment_report = pd.DataFrame(segment_rows).sort_values("average_precision")
print(segment_report.to_string(index=False))
```

Trả lời:

- Segment nào yếu nhất?
- Segment yếu do ít data, positive rate khác, hay model ranking kém?
- Có nên dùng cùng một threshold cho mọi segment không?

### Bài 6: Regression Metrics

Trong mini demo, sửa `y_pred` để một sample lỗi rất lớn. Quan sát MAE và RMSE.

Trả lời:

- RMSE tăng mạnh hơn MAE như thế nào?
- Với bài toán dự đoán demand, vì sao lỗi lớn có thể nguy hiểm hơn lỗi nhỏ?
- Khi nào MAPE không nên dùng?

### Bài 7: Ranking Metrics

Sửa `ranked_docs` sao cho relevant doc đầu tiên từ rank 2 xuống rank 5.

Trả lời:

- Recall@5 có đổi không?
- MRR@5 có đổi không?
- NDCG@5 có đổi không?
- Vì sao trong RAG, Recall@k cao nhưng MRR thấp vẫn có thể làm trải nghiệm kém?

## 5. Câu Hỏi Review Sau Khi Làm

1. Metric nào bạn sẽ đưa vào dashboard offline cho fraud model?
2. Metric nào bạn sẽ đưa vào dashboard online?
3. Threshold production bạn chọn là bao nhiêu và vì sao?
4. Nếu business tăng analyst capacity từ 300 lên 1,000 alerts/ngày, threshold có nên đổi không?
5. Nếu fraud pattern drift sau 2 tuần, metric nào sẽ báo hiệu sớm?
6. Nếu model có PR-AUC tốt hơn nhưng latency p95 tăng 5 lần, có deploy không?

## 6. Expected Takeaways

Sau bài tập, bạn cần rút ra được:

- Accuracy gần như vô dụng nếu positive class rất hiếm và business quan tâm positive class.
- ROC-AUC tốt không đảm bảo threshold production tốt.
- PR-AUC/average precision hữu ích hơn cho imbalanced classification.
- Threshold là business decision, không chỉ là model decision.
- Cost/profit và capacity có thể chọn threshold khác với F1.
- Segment metrics là bắt buộc trước production.
- Regression và ranking cần metric riêng, không dùng classification mindset áp đặt.

## 7. Production Readiness Của Bài Tập

Code trong bài dùng được như skeleton cho production evaluation, nhưng chưa phải production system hoàn chỉnh.

Dùng được nếu bổ sung:

- Data thật với time-based split và label delay handling.
- Feature pipeline giống training và serving.
- Cost assumption được business owner xác nhận.
- Segment/fairness report đầy đủ.
- Calibration nếu score được dùng như xác suất.
- Model registry, versioning và reproducible training.
- Monitoring sau deploy: drift, latency, alert volume, precision proxy, business KPI.
- Human review workflow và rollback policy.

Không nên dùng trực tiếp để auto block giao dịch thật nếu chưa có các điều kiện trên.
