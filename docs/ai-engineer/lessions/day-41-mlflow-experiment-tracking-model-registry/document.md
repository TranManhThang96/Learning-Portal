# Document: MLflow Tracking, Registry Template, Checklist Và Runbook

## 1. Tracking schema chuẩn

Một run đủ tốt cho production review nên có schema tối thiểu:

| Field | Ví dụ | Bắt buộc? |
|---|---|---|
| `experiment_name` | `day41-sentiment-classifier` | Có |
| `run_name` | `sentiment-v1-a1b2c3d4` | Có |
| `registered_model_name` | `sentiment-classifier` | Có nếu có deploy |
| `git_commit` | `a1b2c3d4...` | Có |
| `dataset_version` | `sentiment-v1` | Có |
| `dataset_hash` | `sha256:...` | Có |
| `split_strategy` | `stratified_train_validation_80_20_seed_42` | Có |
| `primary_metric` | `val_macro_f1` | Có |
| `validation_gate` | `passed` hoặc `failed` | Có |
| `holdout_test_status` | `not_run`, `passed`, `failed` | Có trước promote |
| `owner` | `ai-team` | Có |
| `approval_status` | `pending`, `approved`, `rejected` | Có với registry |

Naming convention gợi ý:

```text
experiment: <phase>-<task>-<model-family>
run_name:   <dataset-version>-<model-config>-<git-short-sha>
model:      <business-task>-<model-role>
alias:      candidate | champion | shadow | rollback
```

Ví dụ:

```text
experiment: day41-vietnamese-sentiment
run_name: sentiment-v1-tfidf-lr-a1b2c3d4
model: sentiment-classifier
alias: champion
```

## 2. Artifact structure

Artifact nên có cấu trúc đọc được bằng người và máy:

```text
artifacts/day41/
  validation_classification_report.json
  holdout_test_report.json
  confusion_matrix.png
  eval_summary.json
  model_card.md
  sample_predictions_redacted.jsonl
  requirements-lock.txt
```

`eval_summary.json` nên có:

```json
{
  "run_id": "abc123",
  "registered_model_name": "sentiment-classifier",
  "model_version": "3",
  "dataset_version": "sentiment-v1",
  "dataset_hash": "sha256:...",
  "git_commit": "a1b2c3d4",
  "primary_metric": "val_macro_f1",
  "metrics": {
    "val_macro_f1": 0.84,
    "val_accuracy": 0.86,
    "val_p95_latency_ms": 18.5
  },
  "validation_gate": {
    "val_macro_f1_min": 0.80,
    "val_p95_latency_ms_max": 30,
    "status": "passed"
  }
}
```

## 3. Model card template

```markdown
# Model Card: <registered_model_name>

## Intended Use
<Bài toán model được phép xử lý.>

## Not Intended Use
<Các tình huống không được dùng hoặc chưa được kiểm chứng.>

## Training Data
- Dataset version:
- Dataset hash:
- Split strategy:
- Data source:
- PII handling:

## Evaluation
- Primary metric:
- Secondary metrics:
- Latency:
- Cost estimate:
- Error analysis:

## Model Version
- Registered model:
- Version:
- Alias:
- Source run:
- Git commit:

## Limitations
- <Known limitation 1>
- <Known limitation 2>

## Production Conditions
- <Điều kiện hạ tầng, monitoring, security, fallback.>

## Rollback
- Previous champion version:
- Rollback command:
```

## 4. Release gate mẫu

Release gate phải phụ thuộc context. Không có một metric chung cho mọi model.

| Loại model | Primary gate | Secondary gate | Gate vận hành |
|---|---|---|---|
| Classification mất cân bằng | `macro_f1`, per-class recall | calibration, confusion matrix | p95 latency, memory |
| Fraud/risk | recall ở class rủi ro | precision, false positive cost | audit trail, explainability |
| Search/RAG | recall@k, MRR, citation accuracy | answer faithfulness, no-answer accuracy | token cost, p95 latency |
| LoRA/LLM task | task success rate | safety eval, refusal accuracy | tokens/sec, VRAM, cost |

Ví dụ gate cho Day 16 sentiment:

```yaml
quality:
  macro_f1_min: 0.80
  negative_recall_min: 0.75
performance:
  p95_latency_ms_max: 30
security:
  pii_in_artifacts: false
reproducibility:
  requires_dataset_hash: true
  requires_git_commit: true
approval:
  reviewer: required
```

## 5. Registry lifecycle

Workflow đề xuất:

```text
run training
  -> log params/metrics/artifacts/model
  -> register model version
  -> compare runs on the same validation split
  -> set version tag validation_gate=passed
  -> set alias candidate
  -> evaluate candidate once on immutable holdout test
  -> set holdout_test_status=passed
  -> reviewer approves
  -> set alias champion
  -> deploy serving reads @champion
  -> monitor
  -> rollback alias if regression
```

Không dùng alias như decoration. Alias phải là contract mà serving thật sự đọc.

## 6. Runbook: chọn best run

1. Mở MLflow UI và lọc đúng experiment.
2. Sắp xếp theo primary validation metric, ví dụ `val_macro_f1`.
3. Loại các run không cùng dataset version hoặc không cùng eval set.
4. Kiểm tra metric phụ: per-class recall, latency, memory, cost.
5. Mở artifacts: `validation_classification_report.json`, confusion matrix, model card.
6. Xác nhận run có `git_commit`, `dataset_hash`, `split_strategy`.
7. So sánh với champion hiện tại, không chỉ so với các run mới.
8. Nếu tốt hơn và qua gate, register hoặc giữ model version đã auto-register.
9. Gắn tag `validation_gate=passed`.
10. Gắn alias `candidate`.
11. Chạy holdout test đúng một lần cho candidate; nếu đạt, gắn `holdout_test_status=passed`.

Decision rule ví dụ:

```text
Chỉ chọn run mới nếu:
- Macro F1 tăng ít nhất 1 điểm phần trăm hoặc sửa lỗi class quan trọng.
- Không làm p95 latency vượt gate.
- Không tăng cost vượt budget.
- Không có regression nghiêm trọng trong error analysis.
```

## 7. Runbook: promote

Trước khi promote:

- [ ] Candidate qua validation gate.
- [ ] Candidate được chọn bằng validation set, không phải holdout test.
- [ ] Holdout test chạy đúng một lần và có `holdout_test_status=passed`.
- [ ] Model card đã cập nhật.
- [ ] Artifact không chứa raw PII hoặc secret.
- [ ] Dataset và code version đầy đủ.
- [ ] Serving đã smoke test model URI `models:/<name>@candidate`.
- [ ] Rollback target đã xác định.
- [ ] Reviewer approve.

Promote:

```python
from mlflow import MlflowClient

client = MlflowClient()
model_name = "sentiment-classifier"
candidate = client.get_model_version_by_alias(model_name, "candidate")

if candidate.tags.get("validation_gate") != "passed":
    raise RuntimeError("Candidate chưa qua validation gate")
if candidate.tags.get("holdout_test_status") != "passed":
    raise RuntimeError("Candidate chưa qua holdout test")

client.set_model_version_tag(
    name=model_name,
    version=candidate.version,
    key="approval_status",
    value="approved",
)
client.set_registered_model_alias(
    name=model_name,
    alias="champion",
    version=candidate.version,
)
```

Smoke test sau promote:

```python
import mlflow.pyfunc

model = mlflow.pyfunc.load_model("models:/sentiment-classifier@champion")
result = model.predict(["Ứng dụng hoạt động ổn định sau bản cập nhật"])
print(result)
```

## 8. Runbook: rollback

Rollback nên đổi alias, không retrain trong lúc incident.

Các bước:

1. Xác nhận incident: metric, latency, error rate hoặc business KPI regression.
2. Tìm previous champion version từ deployment log hoặc MLflow UI.
3. Gắn tag cho version lỗi: `incident_status=rollback_requested`.
4. Trỏ alias `champion` về previous version.
5. Restart hoặc reload serving nếu service không tự refresh model alias.
6. Ghi incident note: thời gian, version lỗi, version rollback, nguyên nhân ban đầu, follow-up.

Lệnh rollback:

```python
from mlflow import MlflowClient

client = MlflowClient()
client.set_registered_model_alias(
    name="sentiment-classifier",
    alias="champion",
    version="2",
)
client.set_model_version_tag(
    name="sentiment-classifier",
    version="3",
    key="incident_status",
    value="rolled_back",
)
```

## 9. Security checklist

- [ ] Tracking UI không public internet nếu chưa có auth.
- [ ] Dùng TLS khi truy cập từ network khác machine local.
- [ ] Artifact store có encryption at rest.
- [ ] IAM cho training job chỉ được ghi vào artifact prefix cần thiết.
- [ ] Không log API key, database URL có password, bearer token hoặc private key.
- [ ] Không log raw PII trong sample predictions.
- [ ] Dataset source nhạy cảm không ghi vào tag nếu tag có nhiều người đọc.
- [ ] Model artifact đến từ registry không tin cậy không được load vào service production.
- [ ] Có retention policy cho artifacts và runs cũ.

## 10. Reproducibility checklist

- [ ] Có `git_commit`.
- [ ] Có `dataset_version` và `dataset_hash`.
- [ ] Có train/validation/test split strategy.
- [ ] Hyperparameter chỉ được chọn bằng validation; holdout test không bị dùng lặp lại.
- [ ] Có seed và note về nondeterminism nếu dùng GPU.
- [ ] Có package versions hoặc lock file.
- [ ] Có base model id và revision nếu dùng pretrained model.
- [ ] Có tokenizer version hoặc tokenizer artifact.
- [ ] Có evaluation script version.
- [ ] Có model signature và input example.
- [ ] Có model card mô tả limitation.

## 11. Performance và cost checklist

- [ ] Log `p50_latency_ms`, `p95_latency_ms`, batch size và hardware.
- [ ] Không log checkpoint lớn không cần thiết.
- [ ] Có lifecycle policy cho artifact store.
- [ ] Có cost estimate nếu dùng managed LLM/embedding/reranker.
- [ ] Có budget gate cho replay eval hoặc batch inference.
- [ ] Serving load model bằng alias ổn định và có warm-up.
- [ ] Có benchmark trên input gần production, không chỉ sample rất ngắn.

## 12. MLflow vs W&B vs Neptune

| Tool | Mạnh nhất khi | Điểm cần cân nhắc | Best context |
|---|---|---|---|
| MLflow | Muốn open-source, self-host, tracking + registry + artifact | UI collaboration không mạnh bằng SaaS chuyên dụng | MLOps baseline, portfolio, team cần kiểm soát dữ liệu |
| W&B | Cần dashboard đẹp, collaboration research, rich media | SaaS/data policy/cost | Team train nhiều model và cần phân tích experiment mạnh |
| Neptune | Cần metadata management cho ML team | Adoption thấp hơn MLflow/W&B ở nhiều org | Team ML chuyên sâu cần quản trị metadata |
| Custom tracking | Domain rất đặc thù | Dễ thiếu registry, lineage, UI và governance | Chỉ nên làm khi requirement vượt hẳn tool sẵn có |

Best solution theo context:

- Học tập hoặc capstone: MLflow local với SQLite và local artifacts.
- Team nhỏ cần production baseline: MLflow self-host, Postgres, S3-compatible artifact store, auth qua reverse proxy.
- Team research-heavy: W&B hoặc Neptune có thể tốt hơn cho collaboration, nhưng vẫn cần policy về data egress.
- Enterprise nhiều environment: tách registry/dev/prod hoặc dùng alias/environment naming rõ, kết hợp CI/CD và approval workflow.

## 13. Production readiness answer template

```markdown
## Dùng được trong production không?

Có/Chưa.

### Nếu có, điều kiện bắt buộc
- Tracking server:
- Backend store:
- Artifact store:
- Auth/TLS:
- Dataset/code lineage:
- Release gate:
- Monitoring:
- Rollback:

### Rủi ro còn lại
- Performance:
- Cost:
- Security:
- Reproducibility:
- Model quality:

### Quyết định release
- Champion hiện tại:
- Candidate:
- Metric thay đổi:
- Người approve:
- Rollback version:
```

## 14. Nguồn API đã kiểm chứng

- MLflow Model Registry hiện tại dùng registered models, model versions, aliases và tags; aliases phù hợp để deployment đọc `models:/<model-name>@<alias>`.
- MLflow Model Registry stages đã bị deprecate từ MLflow 2.9.0; không nên xây workflow mới quanh `Staging`/`Production` stages.
- `mlflow.data.from_pandas(..., targets=...)` và `mlflow.log_input(..., context=...)` dùng để log dataset metadata vào run.

Tham khảo chính thức:

- https://mlflow.org/docs/latest/ml/model-registry/
- https://mlflow.org/docs/latest/ml/model-registry/workflow/
- https://mlflow.org/docs/latest/python_api/mlflow.data.html
