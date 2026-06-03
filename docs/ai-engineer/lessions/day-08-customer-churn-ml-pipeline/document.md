# Day 8 Document - Customer Churn ML Pipeline

Tài liệu này là phần tra cứu nhanh khi làm mini-project. Mục tiêu là giúp bạn triển khai nhất quán, tránh bỏ sót schema, metrics, artifact metadata và production notes.

## 1. Project Structure Gợi Ý

Nếu làm thành repository riêng cho portfolio:

```text
customer-churn-ml-pipeline/
  README.md
  requirements.txt
  pyproject.toml
  data/
    telco_customer_churn.csv
  src/
    churn_pipeline.py
  artifacts/
    customer_churn_model.joblib
    metrics_report.json
    error_analysis/
      false_positives.csv
      false_negatives.csv
      slice_metrics.csv
  tests/
    test_schema.py
    test_inference_contract.py
```

Trong repo bài học này, bạn không cần commit dataset hoặc model artifact thật. Dataset và artifact thường lớn hoặc có rủi ro PII. Hãy hướng dẫn cách tạo lại artifact bằng command train.

## 2. Dataset Contract

Schema mặc định cho Telco Customer Churn:

| Column | Required | Training | Inference | Type | Ghi chú |
|---|---:|---:|---:|---|---|
| `customerID` | Có | Có | Có | string | ID, không dùng làm feature |
| `gender` | Có | Có | Có | categorical | Cần fairness review nếu dùng cho decision nhạy cảm |
| `SeniorCitizen` | Có | Có | Có | numeric/binary | Có thể đọc từ CSV là `0/1` hoặc string |
| `Partner` | Có | Có | Có | categorical | `Yes/No` |
| `Dependents` | Có | Có | Có | categorical | `Yes/No` |
| `tenure` | Có | Có | Có | numeric | Số tháng dùng dịch vụ |
| `PhoneService` | Có | Có | Có | categorical | `Yes/No` |
| `InternetService` | Có | Có | Có | categorical | `DSL/Fiber optic/No` |
| `Contract` | Có | Có | Có | categorical | Segment rất quan trọng |
| `PaperlessBilling` | Có | Có | Có | categorical | `Yes/No` |
| `PaymentMethod` | Có | Có | Có | categorical | Có whitespace trong một số dataset |
| `MonthlyCharges` | Có | Có | Có | numeric | Phí hàng tháng |
| `TotalCharges` | Có | Có | Có | numeric/string | Cần convert numeric, blank thành missing |
| `Churn` | Có | Có | Không | target | `Yes/No` hoặc `1/0` |

Quy tắc validation tối thiểu:

- Thiếu required column thì fail fast.
- Strip whitespace ở column name và categorical value.
- Convert numeric columns bằng `pd.to_numeric(errors="coerce")`.
- Target chỉ được là `0/1` sau khi normalize.
- Duplicate `customerID` cần được report.
- Missing rate quá cao ở feature quan trọng cần được cảnh báo.

## 3. Feature Engineering Contract

Feature raw không dùng trực tiếp một cách tùy tiện. Nên có một function hoặc transformer duy nhất tạo feature cho cả training và inference.

Feature gợi ý:

| Feature | Nhóm | Nguồn | Giải thích |
|---|---|---|---|
| `tenure` | numeric | raw | Số tháng sử dụng |
| `MonthlyCharges` | numeric | raw | Spend hiện tại |
| `TotalCharges` | numeric | raw | Spend tích lũy |
| `avg_monthly_charge_observed` | numeric | engineered | `TotalCharges / tenure`, fallback `MonthlyCharges` |
| `SeniorCitizen` | numeric | raw | Binary |
| `tenure_group` | categorical | engineered | `0-6`, `7-12`, `13-24`, `25-48`, `49+` |
| `monthly_charge_band` | categorical | engineered | Low/medium/high spend |
| `Contract` | categorical | raw | Rất quan trọng cho churn |
| `InternetService` | categorical | raw | Segment |
| `PaymentMethod` | categorical | raw | Segment |
| Các cột `Yes/No` | categorical | raw | Partner, Dependents, PhoneService, PaperlessBilling |

Không dùng:

- `customerID` làm feature.
- `Churn` hoặc bất kỳ target proxy nào.
- Feature phát sinh sau khi customer đã churn.
- Aggregate không có cutoff time.

## 4. Requirements Template

`requirements.txt` tối thiểu:

```text
numpy>=1.26
pandas>=2.1
scikit-learn>=1.4,<2.0
joblib>=1.3
```

Nếu dùng `pyproject.toml`:

```toml
[project]
name = "customer-churn-ml-pipeline"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "numpy>=1.26",
  "pandas>=2.1",
  "scikit-learn>=1.4,<2.0",
  "joblib>=1.3",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Ghi chú API: bài này dùng API hiện tại của scikit-learn stable như `Pipeline`, `ColumnTransformer`, `OneHotEncoder(handle_unknown="ignore")`, `LogisticRegression`, `RandomForestClassifier`, `GradientBoostingClassifier` và các metrics classification.

## 5. README Template

````markdown
# Customer Churn ML Pipeline

## Problem
Predict the probability that a customer will churn within the defined prediction horizon so the retention team can prioritize outreach.

## Dataset
Telco Customer Churn or an equivalent customer subscription dataset.

## Target
`Churn`: 1 if customer churned in the target horizon, otherwise 0.

## Approach
- Validate schema and clean numeric/categorical values.
- Run EDA: target distribution, missing values, cardinality, segment churn rate.
- Use sklearn `Pipeline` and `ColumnTransformer`.
- Train Logistic Regression, Random Forest, Gradient Boosting.
- Evaluate ROC-AUC, PR-AUC, precision, recall, F1, confusion matrix.
- Tune threshold on validation set.
- Run error analysis on false positives, false negatives and customer segments.
- Save artifact with model, threshold, schema and metadata.

## Production Readiness
This project is usable as a v1 production pattern only if label definition, point-in-time feature correctness, validation, monitoring, rollback and PII policy are implemented in the target system.

## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/churn_pipeline.py --csv data/telco_customer_churn.csv
```

## Inference
```python
from churn_pipeline import predict_customer_churn

result = predict_customer_churn(customer_payload)
```

## Limitations
- Offline dataset may not represent live customers.
- Random split is not enough if production data has time drift.
- Model probability may require calibration before high-stakes automation.
- Campaign lift must be validated with an experiment.
````

## 6. Artifact Contract

Artifact nên được save bằng `joblib` dưới dạng dictionary:

```python
artifact = {
    "model": fitted_pipeline,
    "metadata": {
        "model_name": "gradient_boosting",
        "model_version": "customer-churn-v1",
        "schema_version": "telco-churn-v1",
        "threshold": 0.45,
        "raw_feature_columns": [...],
        "numeric_features": [...],
        "categorical_features": [...],
        "validation_metrics": {...},
        "test_metrics": {...},
        "created_at_utc": "...",
        "python_version": "...",
        "sklearn_version": "...",
        "random_state": 42,
        "training_note": "Validate on time-based split before production."
    }
}
```

Không chỉ save fitted estimator. Nếu thiếu threshold hoặc schema, service inference sẽ phải hard-code logic bên ngoài artifact, dễ gây train-serving skew.

## 7. Inference Contract

Request:

```json
{
  "customerID": "CUST_000123",
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
  "TotalCharges": 1020.3
}
```

Response:

```json
{
  "customer_id": "CUST_000123",
  "churn_probability": 0.7312,
  "will_churn": true,
  "risk_tier": "high",
  "threshold": 0.45,
  "model_name": "gradient_boosting",
  "model_version": "customer-churn-v1",
  "schema_version": "telco-churn-v1"
}
```

Validation behavior:

- Missing required field: return validation error, không gọi model.
- Unknown categorical value: cho phép đi qua `OneHotEncoder(handle_unknown="ignore")`, đồng thời log unknown category rate ở service.
- Numeric không parse được: convert thành missing và để imputer xử lý nếu field không bắt buộc strict. Với production nghiêm ngặt, nên reject nếu numeric core field invalid.

## 8. Metric Decision Matrix

| Business context | Metric chính | Threshold objective | Lý do |
|---|---|---|---|
| Retention team có capacity thấp | Precision, PR-AUC | Maximize precision với recall tối thiểu | Không muốn lãng phí offer |
| Churn rất đắt | Recall, PR-AUC | Recall >= target rồi maximize precision | Chấp nhận nhiều FP để giảm FN |
| Chỉ dùng để rank list gọi điện | PR-AUC, lift@K | Top K customers | Class threshold ít quan trọng |
| Realtime offer | F1, latency, calibration | Balance precision/recall và p99 latency | Cần quyết định ngay |
| Model monitoring | Positive rate, score drift | Alert theo distribution | Offline metric không đủ |

## 9. Model Selection Matrix

| Điều kiện | Chọn |
|---|---|
| Logistic Regression gần bằng model khác, latency/explainability quan trọng | Logistic Regression |
| Non-linear pattern rõ, model size chấp nhận | Gradient Boosting |
| Cần robust baseline tree ensemble, ít tuning | Random Forest |
| Dataset lớn, nhiều categorical high-cardinality | Cân nhắc histogram boosting hoặc specialized tabular model, nhưng ngoài phạm vi Day 8 |
| Probability dùng cho quyết định tiền lớn | Thêm calibration và business experiment |

## 10. Monitoring Checklist

Training-time:

- Data snapshot version.
- Target rate.
- Missing rate.
- Cardinality.
- Metrics by segment.
- Artifact checksum.

Serving-time:

- Request count.
- Validation error rate.
- Null rate theo field.
- Unknown category rate.
- Score distribution.
- Predicted positive rate.
- Latency p50/p95/p99.
- Model version đang serve.

Post-serving:

- Actual churn rate sau khi label mature.
- Precision/recall thực tế.
- Campaign conversion/lift.
- Segment bias.
- Drift giữa train và live data.

## 11. Review Checklist Cho Portfolio

- README có giải thích business problem, không chỉ code.
- Code có `main()` hoặc CLI rõ ràng.
- Có seed và split strategy.
- Có validation và inference contract.
- Có ít nhất 3 models và leaderboard.
- Có threshold report.
- Có error analysis file.
- Có artifact metadata.
- Có câu trả lời production readiness.
- Không commit data nhạy cảm hoặc artifact lớn không cần thiết.

## 12. Tài Liệu Tham Khảo

- scikit-learn stable documentation: `Pipeline`, `ColumnTransformer`, preprocessing, classification metrics, ensemble classifiers.
- Telco Customer Churn dataset.
- Google Machine Learning Crash Course: Classification.
- Chip Huyen, Designing Machine Learning Systems.
- Hidden Technical Debt in Machine Learning Systems.
