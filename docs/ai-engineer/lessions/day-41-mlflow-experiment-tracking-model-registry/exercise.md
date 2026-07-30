# Exercise: Lab MLflow Experiment Tracking Và Model Registry

## Mục tiêu

Bạn sẽ track lại một training workflow từ Day 16 hoặc Day 27 bằng MLflow, sau đó register model và viết release decision.

Chọn một trong hai hướng:

- Dễ kiểm soát: Day 16 sentiment classifier với scikit-learn hoặc Transformers.
- Nâng cao: Day 27 LoRA adapter, log thêm base model revision, adapter config và eval latency/tokens per second.

Thời lượng đề xuất:

- Bản tối thiểu: 60-90 phút.
- Bản portfolio tốt: 3-4 giờ.
- Bản gần production: 1 ngày, có CI script, model card, rollback và monitoring stub.

## 0. Acceptance criteria

Hoàn thành bài tập khi bạn có:

- [ ] MLflow Tracking UI chạy local.
- [ ] Ít nhất 3 runs trong cùng experiment.
- [ ] Mỗi run log params, validation metrics, artifacts, dataset metadata và code commit.
- [ ] Có artifact `validation_classification_report.json` hoặc eval report tương đương.
- [ ] Có model signature và input example.
- [ ] Có registered model, ví dụ `sentiment-classifier`.
- [ ] Có alias `candidate` cho version được chọn bằng validation.
- [ ] Candidate có holdout test report và tag `holdout_test_status=passed`.
- [ ] Có alias `champion` sau khi promote.
- [ ] Có decision note trả lời production readiness.
- [ ] Có rollback plan rõ version và command.

## 1. Chuẩn bị

Tạo structure:

```text
day41-mlflow-lab/
  data/
    sentiment_v1.csv
  artifacts/
  train_day41.py
  promote_model.py
  decision-note.md
  README.md
```

Cài package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U mlflow scikit-learn pandas matplotlib
```

Chạy MLflow:

```bash
mkdir -p mlruns mlartifacts
mlflow server \
  --host 127.0.0.1 \
  --port 5000 \
  --backend-store-uri sqlite:///mlruns/mlflow.db \
  --default-artifact-root ./mlartifacts
```

## 2. Tạo dataset tối thiểu

Dataset cần ít nhất 30 dòng, có cột `text` và `label`. Với bài 3 lớp, mỗi class nên có ít nhất 5 dòng; dataset thật cần lớn hơn nhiều để metric ổn định.

Ví dụ format:

```csv
text,label
"Giao hàng nhanh và đóng gói cẩn thận",positive
"Ứng dụng bị lỗi khi đăng nhập",negative
"Dịch vụ ở mức chấp nhận được",neutral
```

Yêu cầu:

- Có ít nhất 2 classes; tốt hơn là 3 classes.
- Mỗi class có đủ sample để split stratified.
- Không chứa PII thật.
- Ghi rõ dataset version, ví dụ `sentiment-v1`.

## 3. Implement tracking

Dựa vào code trong `lession.md`, tạo `train_day41.py`.

Bạn có thể dùng scikit-learn baseline hoặc model từ Day 16. Bắt buộc log:

Params:

- `model_type`
- `dataset_version`
- `dataset_hash`
- `random_state`
- hyperparameters chính

Metrics:

- `val_accuracy`
- `val_macro_f1`
- `val_weighted_f1`
- `val_p95_latency_ms`

Artifacts:

- `validation_classification_report.json`
- `eval_summary.json`
- `model_card.md`
- optional: `confusion_matrix.png`

Tags:

- `git_commit`
- `owner`
- `task`
- `approval_status`

Dataset:

- `mlflow.data.from_pandas(...)`
- `mlflow.log_input(..., context="training")`
- `mlflow.log_input(..., context="validation")`

## 4. Chạy 3 runs

Ví dụ:

```bash
python train_day41.py \
  --dataset-path data/sentiment_v1.csv \
  --dataset-version sentiment-v1 \
  --classifier-c 0.3
```

```bash
python train_day41.py \
  --dataset-path data/sentiment_v1.csv \
  --dataset-version sentiment-v1 \
  --classifier-c 1.0
```

```bash
python train_day41.py \
  --dataset-path data/sentiment_v1.csv \
  --dataset-version sentiment-v1 \
  --classifier-c 3.0
```

Trong MLflow UI, so sánh:

- `val_macro_f1`
- per-class recall trong `validation_classification_report.json`
- `val_p95_latency_ms`
- dataset hash có giống nhau không
- git commit có giống hoặc được ghi rõ không

## 5. Chọn best run

Không chọn best run chỉ vì accuracy cao.

Quy tắc gợi ý:

```text
Candidate được chọn nếu:
- val_macro_f1 cao nhất hoặc tốt hơn champion hiện tại ít nhất 1 điểm phần trăm.
- Không class quan trọng nào có recall quá thấp.
- val_p95_latency_ms không vượt 30 ms với batch nhỏ local.
- Artifact đầy đủ và không chứa PII.
- Có dataset_hash và git_commit.
```

Viết vào `decision-note.md`:

```markdown
# Day 41 Release Decision

## Candidate
- Registered model:
- Version:
- Source run:
- Dataset version:
- Dataset hash:
- Git commit:

## Metrics
- Macro F1:
- Accuracy:
- Weighted F1:
- P95 latency:

## So sánh với baseline/champion
- Metric tăng/giảm:
- Latency tăng/giảm:
- Cost/storage impact:

## Quyết định
Promote/Không promote.

## Lý do
<Giải thích ngắn, dựa trên metric và limitation.>

## Rollback
- Previous champion version:
- Rollback command:
```

## 6. Register, chọn candidate và chạy holdout test

Nếu code dùng `registered_model_name` trong `mlflow.sklearn.log_model`, model version sẽ được register tự động.

Sau khi so sánh đủ 3 runs trên cùng validation split, gắn alias `candidate` cho đúng một version. Không đặt alias tự động trong từng training run vì run cuối có thể ghi đè candidate tốt hơn.

```python
from mlflow import MlflowClient

client = MlflowClient()
client.set_registered_model_alias(
    name="sentiment-classifier",
    alias="candidate",
    version="1",
)
```

Tiếp theo, chạy candidate đúng một lần trên holdout test chưa dùng để tune hyperparameter. Log `holdout_test_report.json`; nếu đạt release gate, gắn tag:

```python
client.set_model_version_tag(
    name="sentiment-classifier",
    version="1",
    key="holdout_test_status",
    value="passed",
)
```

Tag chỉ được gắn sau khi release-evaluation run đã log model version, holdout dataset version/hash, test metrics và report. Nộp cả release-evaluation run ID; không tự gắn `passed` để bỏ qua bước test.

Promote thành `champion` sau khi validation gate, holdout test và human review đều đạt:

```python
from mlflow import MlflowClient

client = MlflowClient()
candidate = client.get_model_version_by_alias("sentiment-classifier", "candidate")
if candidate.tags.get("validation_gate") != "passed":
    raise RuntimeError("Candidate chưa qua validation gate")
if candidate.tags.get("holdout_test_status") != "passed":
    raise RuntimeError("Candidate chưa qua holdout test")
client.set_registered_model_alias(
    name="sentiment-classifier",
    alias="champion",
    version=candidate.version,
)
```

Load thử model bằng alias:

```python
import mlflow.pyfunc

model = mlflow.pyfunc.load_model("models:/sentiment-classifier@champion")
print(model.predict(["Sản phẩm tốt, hỗ trợ nhanh"]))
```

## 7. Rollback drill

Giả lập candidate/champion version mới bị lỗi.

Yêu cầu:

- Tìm previous champion version.
- Trỏ alias `champion` về previous version.
- Gắn tag `incident_status=rolled_back` cho version lỗi.
- Ghi lại trong `decision-note.md`.

Ví dụ:

```python
from mlflow import MlflowClient

client = MlflowClient()
client.set_registered_model_alias(
    name="sentiment-classifier",
    alias="champion",
    version="1",
)
client.set_model_version_tag(
    name="sentiment-classifier",
    version="2",
    key="incident_status",
    value="rolled_back_in_lab",
)
```

## 8. Nếu làm với Day 27 LoRA

Log thêm params:

- `base_model_id`
- `base_model_revision`
- `tokenizer_revision`
- `lora_r`
- `lora_alpha`
- `lora_dropout`
- `target_modules`
- `max_seq_length`
- `gradient_accumulation_steps`
- `quantization`

Log thêm metrics:

- `eval_loss`
- task metric chính
- `tokens_per_second`
- `p95_latency_ms`
- `vram_peak_gb`

Artifacts:

- adapter files
- tokenizer files nếu cần
- training config
- eval report
- model card

Production note cho LoRA:

```text
Adapter không đủ để reproduce nếu thiếu base model id/revision, tokenizer revision,
prompt/chat template version và serving config.
```

## 9. Câu hỏi bắt buộc

Trả lời trong README hoặc `decision-note.md`:

1. Dùng workflow này được trong production không? Nếu có thì cần điều kiện gì?
2. Nếu MLflow server mất dữ liệu, model đang chạy có bị ảnh hưởng không? Vì sao?
3. Vì sao không nên dùng test set để chọn hyperparameters?
4. Nếu run tốt nhất có `val_macro_f1` cao hơn nhưng latency gấp 5 lần, bạn có promote không?
5. Nếu artifact có sample prediction chứa email khách hàng, bạn xử lý thế nào?
6. Rollback bằng alias khác gì rollback bằng retrain?
7. Với RAG, bạn sẽ log thêm những version nào ngoài LLM model?

## 10. Production readiness answer mẫu

```markdown
## Dùng được trong production không?

Chưa, nếu chỉ chạy local bằng SQLite và local artifact store.

Có thể dùng trong production nếu:
- MLflow Tracking Server được deploy sau auth/TLS.
- Backend store dùng Postgres/MySQL có backup.
- Artifact store dùng S3/GCS/Azure Blob có encryption và lifecycle policy.
- Training pipeline bắt buộc log dataset hash, code commit, params, metrics, artifacts và model signature.
- Promotion qua release gate và reviewer approval.
- Serving load model bằng `models:/sentiment-classifier@champion`.
- Có monitoring cho drift, latency, error rate và business metric.
- Có rollback alias về previous champion.

Rủi ro còn lại:
- Dataset nhỏ nên metric chưa ổn định.
- Chưa có drift monitoring.
- Chưa có security review đầy đủ cho artifact.
- Chưa benchmark trên traffic thật.
```

## 11. Nộp bài

Nộp các bằng chứng:

- Screenshot hoặc mô tả MLflow UI có 3 runs.
- Run ID của best run.
- Registered model name và version.
- Alias hiện tại của `candidate` và `champion`.
- `validation_classification_report.json`.
- `holdout_test_report.json`.
- `model_card.md`.
- `decision-note.md`.
- Rollback command đã test.
