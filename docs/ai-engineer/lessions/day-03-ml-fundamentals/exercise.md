# Day 3 Exercise: Baseline-First ML Experiment

## Mục tiêu thực hành

Bài này giúp bạn chạy một experiment ML gần production hơn toy example:

- Có baseline bằng `DummyClassifier`.
- Có split reproducible với `random_state` và `stratify`.
- Có `Pipeline` để tránh preprocessing leakage.
- Có nhiều metrics: accuracy, precision, recall, F1, ROC-AUC.
- Có đo training time và prediction time.
- Có cross-validation để xem metric ổn định không.
- Có câu hỏi production decision ở cuối.

Dataset dùng `load_breast_cancer` vì có sẵn trong scikit-learn, chạy nhanh và đủ để thực hành binary classification. Trong project thật, bạn thay bằng dataset churn/fraud/internal ticket nhưng giữ nguyên discipline.

## 1. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install numpy pandas scikit-learn
```

Kiểm tra version:

```bash
python3 -c "import sklearn; print(sklearn.__version__)"
```

## 2. Experiment Script

Tạo file tạm, ví dụ `day03_experiment.py`, rồi chạy script dưới đây. Script này không lưu artifact để giữ bài tập gọn; trong production bạn sẽ lưu model bằng format phù hợp, kèm metadata về dataset/code/params/metrics.

```python
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.datasets import load_breast_cancer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


RANDOM_STATE = 42
TEST_SIZE = 0.2


@dataclass(frozen=True)
class ModelSpec:
    name: str
    estimator: object
    has_probability: bool = True


def build_models() -> list[ModelSpec]:
    return [
        ModelSpec(
            name="dummy_majority",
            estimator=DummyClassifier(strategy="most_frequent"),
            has_probability=True,
        ),
        ModelSpec(
            name="logistic_regression",
            estimator=Pipeline(
                steps=[
                    ("scaler", StandardScaler()),
                    (
                        "model",
                        LogisticRegression(
                            max_iter=1000,
                            class_weight=None,
                            random_state=RANDOM_STATE,
                        ),
                    ),
                ]
            ),
        ),
        ModelSpec(
            name="random_forest",
            estimator=RandomForestClassifier(
                n_estimators=300,
                max_depth=6,
                min_samples_leaf=3,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
        ModelSpec(
            name="hist_gradient_boosting",
            estimator=HistGradientBoostingClassifier(
                max_iter=200,
                learning_rate=0.05,
                max_leaf_nodes=15,
                l2_regularization=0.1,
                random_state=RANDOM_STATE,
            ),
        ),
    ]


def predict_score(estimator, X_test: pd.DataFrame) -> np.ndarray:
    if hasattr(estimator, "predict_proba"):
        return estimator.predict_proba(X_test)[:, 1]
    if hasattr(estimator, "decision_function"):
        return estimator.decision_function(X_test)
    raise ValueError("Estimator must expose predict_proba or decision_function.")


def evaluate_holdout(
    name: str,
    estimator,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
) -> dict[str, float | str]:
    train_start = time.perf_counter()
    estimator.fit(X_train, y_train)
    train_ms = (time.perf_counter() - train_start) * 1000

    predict_start = time.perf_counter()
    y_pred = estimator.predict(X_test)
    predict_ms = (time.perf_counter() - predict_start) * 1000

    y_score = predict_score(estimator, X_test)

    return {
        "model": name,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_score),
        "train_ms": train_ms,
        "predict_ms_per_1000_rows": predict_ms / len(X_test) * 1000,
    }


def evaluate_cross_validation(name: str, estimator, X: pd.DataFrame, y: pd.Series) -> dict[str, float | str]:
    scoring = {
        "accuracy": "accuracy",
        "precision": "precision",
        "recall": "recall",
        "f1": "f1",
        "roc_auc": "roc_auc",
    }
    result = cross_validate(
        estimator,
        X,
        y,
        cv=5,
        scoring=scoring,
        return_train_score=True,
        n_jobs=None,
    )

    row: dict[str, float | str] = {"model": name}
    for metric in scoring:
        test_values = result[f"test_{metric}"]
        train_values = result[f"train_{metric}"]
        row[f"cv_test_{metric}_mean"] = float(np.mean(test_values))
        row[f"cv_test_{metric}_std"] = float(np.std(test_values))
        row[f"cv_train_{metric}_mean"] = float(np.mean(train_values))
    row["cv_fit_time_ms_mean"] = float(np.mean(result["fit_time"]) * 1000)
    return row


def main() -> None:
    dataset = load_breast_cancer(as_frame=True)
    X = dataset.data
    y = dataset.target

    print("Dataset shape:", X.shape)
    print("Class distribution:")
    print(y.value_counts(normalize=True).sort_index().rename("ratio"))

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    holdout_rows = []
    cv_rows = []
    for spec in build_models():
        holdout_rows.append(
            evaluate_holdout(spec.name, spec.estimator, X_train, X_test, y_train, y_test)
        )
        cv_rows.append(evaluate_cross_validation(spec.name, spec.estimator, X, y))

    holdout_df = pd.DataFrame(holdout_rows).sort_values("f1", ascending=False)
    cv_df = pd.DataFrame(cv_rows).sort_values("cv_test_f1_mean", ascending=False)

    print("\nHoldout metrics:")
    print(holdout_df.round(4).to_string(index=False))

    print("\nCross-validation metrics:")
    selected_columns = [
        "model",
        "cv_test_f1_mean",
        "cv_test_f1_std",
        "cv_train_f1_mean",
        "cv_test_roc_auc_mean",
        "cv_fit_time_ms_mean",
    ]
    print(cv_df[selected_columns].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
```

## 3. Vì Sao Script Này Gần Production Hơn?

### Baseline rõ ràng

`DummyClassifier(strategy="most_frequent")` cho biết nếu chỉ đoán class phổ biến nhất thì metric ra sao. Candidate model phải vượt baseline này theo metric quan trọng.

### Split có kỷ luật

`train_test_split(..., stratify=y, random_state=RANDOM_STATE)` giúp:

- Giữ tỷ lệ class giữa train/test.
- Có thể reproduce kết quả.
- Tránh mỗi lần chạy ra một kết luận khác nhau.

Với bài toán có timeline thật, hãy thay random split bằng time-based split.

### Pipeline giảm leakage

Logistic Regression dùng:

```python
Pipeline(
    steps=[
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(...)),
    ]
)
```

Scaler được fit cùng training fold, không fit trước trên toàn dataset. Đây là pattern quan trọng để tránh preprocessing leakage.

### Metrics không chỉ accuracy

Script in accuracy, precision, recall, F1 và ROC-AUC. Với class imbalance, accuracy thường đánh lừa. Trong production, chọn metric theo cost:

- False negative đắt: ưu tiên recall.
- False positive đắt: ưu tiên precision.
- Cần rank case rủi ro: xem ROC-AUC/PR-AUC.
- Cần action theo budget: xem precision@K hoặc recall@K.

### Có timing

`train_ms` và `predict_ms_per_1000_rows` chưa thay thế load test thật, nhưng giúp bạn bắt đầu nghĩ về performance. Model tốt hơn 0.5% F1 nhưng inference chậm gấp 20 lần chưa chắc là best solution.

## 4. Nhiệm Vụ Cần Làm

### Task 1: Đọc kết quả baseline

Ghi lại:

- `dummy_majority` có accuracy bao nhiêu?
- Precision/recall/F1 có nói cùng một câu chuyện không?
- Nếu chỉ nhìn accuracy, bạn có bị đánh lừa không?

### Task 2: So sánh model

Tạo bảng quyết định:

| Model | F1 | Recall | ROC-AUC | Predict time | Nhận xét |
|---|---:|---:|---:|---:|---|
| dummy_majority | | | | | |
| logistic_regression | | | | | |
| random_forest | | | | | |
| hist_gradient_boosting | | | | | |

Trả lời:

- Model nào tốt nhất theo F1?
- Model nào tốt nhất theo recall?
- Model nào có trade-off latency/quality tốt nhất?
- Nếu API cần p99 thấp, bạn có chọn model top metric không?

### Task 3: Nhìn train vs validation trong cross-validation

So sánh:

```text
cv_train_f1_mean vs cv_test_f1_mean
```

Nếu train cao hơn test nhiều, có thể có overfitting. Nếu cả hai đều thấp, có thể underfitting hoặc feature chưa đủ signal.

### Task 4: Thử thay đổi constraint

Chạy lại với:

- `RandomForestClassifier(max_depth=None)`.
- `RandomForestClassifier(max_depth=3)`.
- `HistGradientBoostingClassifier(max_iter=50)`.
- `LogisticRegression(C=0.1)` và `C=10`.

Ghi lại model nào overfit hơn, model nào train nhanh hơn và model nào ổn định hơn qua folds.

### Task 5: Production decision

Viết decision memo ngắn:

```text
Recommendation:
- Deploy / do not deploy / need more data.

Reason:
- Baseline:
- Best candidate:
- Metric chosen:
- Latency concern:
- Leakage risk:
- Monitoring needed:
- Fallback:
```

## 5. Câu Hỏi Bắt Buộc

### Dùng được trong production không? Nếu có thì cần điều kiện gì?

Script này **chưa đủ để production trực tiếp**, nhưng workflow của nó dùng được làm nền production nếu bổ sung:

- Dataset thật có version và data contract.
- Split strategy đúng với production, ví dụ time-based cho churn/fraud.
- Feature pipeline dùng chung giữa training và inference.
- Test set độc lập, không bị tune lặp lại.
- Threshold được chọn theo business cost, không mặc định 0.5.
- Model artifact được version cùng params, code hash và metrics.
- Có load test cho inference service, không chỉ timing trong script.
- Có monitoring drift, prediction distribution, latency và downstream KPI.
- Có fallback/rollback khi model lỗi hoặc quality giảm.

## 6. Câu Hỏi Tự Kiểm

1. Vì sao không nên fit `StandardScaler` trên toàn bộ dataset trước khi split?
2. Vì sao `stratify=y` hữu ích trong classification?
3. Khi nào random split không đáng tin?
4. Vì sao baseline majority class có thể có accuracy cao nhưng vô dụng?
5. Cross-validation giúp gì so với một holdout split?
6. Nếu model A F1 cao hơn model B 0.01 nhưng latency gấp 10 lần, bạn chọn model nào?
7. Nếu test score gần 100%, bạn kiểm tra gì trước?
8. Trong fraud detection, false positive và false negative ảnh hưởng business khác nhau thế nào?

## 7. Deliverable

Sau khi hoàn thành, bạn nên có:

- Output metrics từ script.
- Một bảng so sánh model.
- Một decision memo ngắn.
- Một danh sách rủi ro trước production.

Đây là artifact nhỏ nhưng đúng tinh thần của course: concept vừa đủ, hands-on thực tế, trade-off rõ và production decision cụ thể.
