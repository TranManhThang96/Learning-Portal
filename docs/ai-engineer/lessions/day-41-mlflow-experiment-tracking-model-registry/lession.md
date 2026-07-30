# Day 41: MLflow, Experiment Tracking Và Model Registry

## 1. Mục tiêu bài học

Mục tiêu của Day 41 không phải là mở MLflow UI cho đẹp. Mục tiêu là tạo được một audit trail đủ tin cậy để khi model được deploy, team có thể trả lời:

```text
Model này được train bằng data version nào?
Code commit nào tạo ra model này?
Config và hyperparameters chính xác là gì?
Metric validation/test có đạt release gate không?
Artifact đánh giá nằm ở đâu?
Ai approve model version này?
Nếu production lỗi, rollback về version nào?
```

Sau bài này, bạn cần làm được:

- Chạy MLflow Tracking Server local hoặc self-hosted.
- Log `params`, `metrics`, `artifacts`, model, dataset metadata và code version trong cùng một run.
- Register model version vào Model Registry.
- Dùng alias như `candidate`, `champion`, `shadow` để quản lý deployment target.
- Chọn hyperparameter bằng validation set và chỉ dùng holdout test cho release candidate cuối cùng.
- Viết decision note trả lời production readiness, trade-off, rollback và limitation.

Ghi chú API hiện tại: từ MLflow 2.9.0, Model Registry stages như `Staging`/`Production` đã bị deprecate. Workflow mới nên dùng model version tags và aliases, ví dụ `models:/sentiment-classifier@champion`.

## 2. Mental model

Experiment tracking là metadata system cho quá trình phát triển model.

```text
training code
  -> run metadata
  -> params
  -> metrics
  -> dataset lineage
  -> artifacts
  -> logged model
  -> registered model version
  -> alias candidate/champion
  -> deployment reads exact model URI
```

Nếu chỉ lưu `model.pkl`, bạn mất gần hết bối cảnh ra quyết định. Nếu chỉ log metric, bạn vẫn không biết metric đó đến từ dataset nào, code nào, split nào, seed nào và evaluation script nào.

Một run có giá trị khi nó đủ để phục vụ ba việc:

| Việc cần làm | Câu hỏi cần trả lời | Metadata cần có |
|---|---|---|
| Reproduce | Có chạy lại ra kết quả tương đương không? | code commit, dataset version/hash, config, seed, package versions |
| Compare | Run nào tốt hơn trong cùng điều kiện? | metric chính, metric phụ, eval set, latency, cost |
| Deploy/Rollback | Version nào đang chạy và quay về đâu khi lỗi? | registered model version, alias, model card, approval, rollback target |

## 3. Experiment tracking cần log gì?

Tối thiểu mỗi run nên log:

| Nhóm | Ví dụ | Lý do |
|---|---|---|
| Params | `model_type`, `learning_rate`, `max_features`, `epochs`, `batch_size`, `seed` | So sánh cấu hình và reproduce |
| Metrics | `val_accuracy`, `val_macro_f1`, `eval_loss`, `val_p95_latency_ms`, `cost_per_1k_predictions` | Chọn best run theo business gate |
| Artifacts | `validation_classification_report.json`, `confusion_matrix.png`, `model_card.md`, `eval_summary.json` | Review bằng người, audit và debug |
| Dataset | `dataset_version`, `dataset_hash`, train/validation/test split | Tránh so sánh lệch dữ liệu |
| Code | `git_commit`, `training_script`, package lock | Biết code nào sinh model |
| Tags | `owner`, `task`, `environment`, `approval_status` | Tìm kiếm và governance |

Không nên log raw PII vào params, tags, artifact hoặc sample predictions. Nếu cần sample, phải redact hoặc hash trước.

## 4. Kiến trúc local và production

Local learning setup:

```text
train_day41.py
  -> MLflow Tracking Server
      -> SQLite backend store
      -> local artifact directory
      -> Model Registry
```

Production-style setup:

```text
training job / CI pipeline
  -> MLflow Tracking Server behind auth/TLS
      -> Postgres/MySQL backend store
      -> S3/GCS/Azure Blob artifact store
      -> Model Registry
  -> model validation job
  -> deployment system loads models:/<name>@champion
  -> monitoring writes drift/latency/error metrics
```

Local SQLite đủ cho học tập. Production không nên phụ thuộc vào SQLite và local filesystem vì thiếu backup, concurrency, access control và durability.

## 5. Step by step: chạy MLflow

### Bước 1: Tạo môi trường

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U mlflow scikit-learn pandas matplotlib
```

Nếu bạn train model từ Day 27 với Transformers/LoRA, cài thêm package tương ứng:

```bash
pip install -U torch transformers datasets peft accelerate
```

### Bước 2: Chạy tracking server local

```bash
mkdir -p mlruns mlartifacts
mlflow server \
  --host 127.0.0.1 \
  --port 5000 \
  --backend-store-uri sqlite:///mlruns/mlflow.db \
  --default-artifact-root ./mlartifacts
```

Mở UI tại:

```text
http://127.0.0.1:5000
```

### Bước 3: Chuẩn bị dataset

Ví dụ tối thiểu cho Day 16 sentiment classifier:

```csv
text,label
"Sản phẩm dùng ổn, giao hàng nhanh",positive
"Ứng dụng lỗi liên tục sau khi cập nhật",negative
"Dịch vụ bình thường, chưa có gì nổi bật",neutral
```

Production thật cần dataset version rõ hơn: DVC, LakeFS, Delta table version, data warehouse snapshot hoặc ít nhất là file hash cộng với source URI.

## 6. Code ví dụ gần production

File gợi ý: `train_day41.py`.

Code dưới đây cố tình dùng `TfidfVectorizer + LogisticRegression` để tập trung vào MLOps workflow. Với Day 27 LoRA, giữ cùng cấu trúc tracking nhưng thay phần training/model flavor.

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import mlflow
import mlflow.data
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


@dataclass(frozen=True)
class TrainConfig:
    tracking_uri: str
    experiment_name: str
    registered_model_name: str
    dataset_path: Path
    dataset_version: str
    artifact_dir: Path
    validation_size: float = 0.2
    random_state: int = 42
    max_features: int = 30000
    ngram_min: int = 1
    ngram_max: int = 2
    classifier_c: float = 1.0
    min_val_macro_f1: float = 0.78
    max_p95_latency_ms: float = 30.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def pip_freeze() -> str:
    try:
        return subprocess.check_output(
            [sys.executable, "-m", "pip", "freeze"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return "requirements unavailable\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required_columns = {"text", "label"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Dataset thiếu cột bắt buộc: {sorted(missing)}")

    df = df.dropna(subset=["text", "label"]).copy()
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[(df["text"] != "") & (df["label"] != "")]
    if len(df) < 30:
        raise ValueError("Dataset quá nhỏ cho lab 3 lớp. Cần ít nhất 30 dòng.")
    if df["label"].value_counts().min() < 5:
        raise ValueError("Mỗi class cần ít nhất 5 dòng để split stratified ổn định.")
    return df


def build_model(cfg: TrainConfig) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    max_features=cfg.max_features,
                    ngram_range=(cfg.ngram_min, cfg.ngram_max),
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=cfg.classifier_c,
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=cfg.random_state,
                ),
            ),
        ]
    )


def estimate_latency_ms(model: Pipeline, samples: pd.Series, repeats: int = 30) -> dict[str, float]:
    durations = []
    batch = samples.head(min(len(samples), 32))
    for _ in range(repeats):
        start = time.perf_counter()
        model.predict(batch)
        durations.append((time.perf_counter() - start) * 1000)

    durations = sorted(durations)
    p95_index = max(0, int(len(durations) * 0.95) - 1)
    return {
        "mean_latency_ms": sum(durations) / len(durations),
        "p95_latency_ms": durations[p95_index],
    }


def train_and_log(cfg: TrainConfig) -> str:
    mlflow.set_tracking_uri(cfg.tracking_uri)
    mlflow.set_experiment(cfg.experiment_name)

    dataset_hash = sha256_file(cfg.dataset_path)
    commit = git_commit()
    df = load_dataset(cfg.dataset_path)

    train_df, validation_df = train_test_split(
        df,
        test_size=cfg.validation_size,
        random_state=cfg.random_state,
        stratify=df["label"],
    )

    model = build_model(cfg)
    run_name = (
        f"{cfg.registered_model_name}-{cfg.dataset_version}-"
        f"c{cfg.classifier_c}-{commit[:8]}"
    )

    with mlflow.start_run(run_name=run_name) as run:
        run_id = run.info.run_id

        mlflow.log_params(
            {
                "model_type": "tfidf_logistic_regression",
                "dataset_path": str(cfg.dataset_path),
                "dataset_version": cfg.dataset_version,
                "dataset_hash": dataset_hash,
                "validation_size": cfg.validation_size,
                "split_strategy": (
                    f"stratified_train_validation_"
                    f"{1 - cfg.validation_size:.2f}_{cfg.validation_size:.2f}_"
                    f"seed_{cfg.random_state}"
                ),
                "random_state": cfg.random_state,
                "max_features": cfg.max_features,
                "ngram_range": f"{cfg.ngram_min},{cfg.ngram_max}",
                "classifier_c": cfg.classifier_c,
            }
        )
        mlflow.set_tags(
            {
                "task": "vietnamese_sentiment",
                "owner": os.getenv("USER", "unknown"),
                "git_commit": commit,
                "training_script": "train_day41.py",
                "approval_status": "pending",
            }
        )

        train_input = mlflow.data.from_pandas(
            train_df,
            source=str(cfg.dataset_path),
            targets="label",
            name=f"{cfg.dataset_version}-train",
        )
        validation_input = mlflow.data.from_pandas(
            validation_df,
            source=str(cfg.dataset_path),
            targets="label",
            name=f"{cfg.dataset_version}-validation",
        )
        mlflow.log_input(train_input, context="training")
        mlflow.log_input(validation_input, context="validation")

        model.fit(train_df["text"], train_df["label"])
        predictions = model.predict(validation_df["text"])

        validation_report = classification_report(
            validation_df["label"],
            predictions,
            output_dict=True,
            zero_division=0,
        )
        metrics = {
            "val_accuracy": accuracy_score(validation_df["label"], predictions),
            "val_macro_f1": f1_score(validation_df["label"], predictions, average="macro"),
            "val_weighted_f1": f1_score(
                validation_df["label"],
                predictions,
                average="weighted",
            ),
        }
        metrics.update(
            {
                f"val_{name}": value
                for name, value in estimate_latency_ms(model, validation_df["text"]).items()
            }
        )
        mlflow.log_metrics(metrics)

        cfg.artifact_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            cfg.artifact_dir / "validation_classification_report.json",
            validation_report,
        )
        write_json(
            cfg.artifact_dir / "eval_summary.json",
            {
                "run_id": run_id,
                "registered_model_name": cfg.registered_model_name,
                "metrics": metrics,
                "dataset_version": cfg.dataset_version,
                "dataset_hash": dataset_hash,
                "git_commit": commit,
            },
        )
        (cfg.artifact_dir / "model_card.md").write_text(
            "\n".join(
                [
                    f"# Model Card: {cfg.registered_model_name}",
                    "",
                    "## Intended use",
                    "Vietnamese sentiment classification for controlled text inputs.",
                    "",
                    "## Validation",
                    f"- Dataset version: `{cfg.dataset_version}`",
                    f"- Dataset hash: `{dataset_hash}`",
                    f"- Validation Macro F1: `{metrics['val_macro_f1']:.4f}`",
                    f"- Validation P95 latency ms: `{metrics['val_p95_latency_ms']:.2f}`",
                    "- Holdout test: chưa chạy; chỉ chạy sau khi chọn candidate.",
                    "",
                    "## Known limitations",
                    "- Chưa kiểm thử drift theo thời gian.",
                    "- Chưa kiểm thử fairness theo domain/user segment.",
                    "- Không log raw PII; sample predictions phải được redact trước khi chia sẻ.",
                    "",
                    "## Rollback",
                    f"Deployment nên load `models:/{cfg.registered_model_name}@champion`; "
                    "rollback bằng cách trỏ alias `champion` về version trước đó.",
                ]
            ),
            encoding="utf-8",
        )
        (cfg.artifact_dir / "requirements-lock.txt").write_text(
            pip_freeze(),
            encoding="utf-8",
        )
        mlflow.log_artifacts(str(cfg.artifact_dir), artifact_path="reports")

        signature = infer_signature(
            validation_df["text"].head(5),
            model.predict(validation_df["text"].head(5)),
        )
        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            signature=signature,
            input_example=validation_df["text"].head(2),
            registered_model_name=cfg.registered_model_name,
        )

        client = MlflowClient()
        version = str(model_info.registered_model_version)
        client.set_model_version_tag(
            name=cfg.registered_model_name,
            version=version,
            key="validation_status",
            value="candidate",
        )
        client.set_model_version_tag(
            name=cfg.registered_model_name,
            version=version,
            key="source_run_id",
            value=run_id,
        )

        passed_validation_gate = (
            metrics["val_macro_f1"] >= cfg.min_val_macro_f1
            and metrics["val_p95_latency_ms"] <= cfg.max_p95_latency_ms
        )
        client.set_model_version_tag(
            name=cfg.registered_model_name,
            version=version,
            key="validation_gate",
            value="passed" if passed_validation_gate else "failed",
        )

        return run_id


def parse_args() -> TrainConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-uri", default="http://127.0.0.1:5000")
    parser.add_argument("--experiment-name", default="day41-sentiment-classifier")
    parser.add_argument("--registered-model-name", default="sentiment-classifier")
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/day41"))
    parser.add_argument("--classifier-c", type=float, default=1.0)
    args = parser.parse_args()
    return TrainConfig(**vars(args))


if __name__ == "__main__":
    config = parse_args()
    print(json.dumps(asdict(config), default=str, ensure_ascii=False, indent=2))
    print(f"Logged run_id={train_and_log(config)}")
```

Chạy một run:

```bash
python train_day41.py \
  --dataset-path data/sentiment_v1.csv \
  --dataset-version sentiment-v1 \
  --classifier-c 1.0
```

Chạy nhiều run để so sánh:

```bash
python train_day41.py --dataset-path data/sentiment_v1.csv --dataset-version sentiment-v1 --classifier-c 0.3
python train_day41.py --dataset-path data/sentiment_v1.csv --dataset-version sentiment-v1 --classifier-c 1.0
python train_day41.py --dataset-path data/sentiment_v1.csv --dataset-version sentiment-v1 --classifier-c 3.0
```

Ba run trên chỉ được so sánh bằng validation metrics. Không nhìn holdout test để chọn `classifier_c`. Sau khi chọn đúng một model version làm candidate, chạy release-evaluation job một lần trên holdout test bất biến, log `holdout_test_report.json`, rồi gắn tag `holdout_test_status=passed|failed`.

Code không tự đặt alias `candidate`: nếu mọi run đạt ngưỡng, alias tự động sẽ bị run cuối cùng ghi đè dù đó chưa chắc là run tốt nhất. Reviewer phải so sánh các run cùng dataset/split rồi mới đặt alias.

Với project thật, holdout nên là file/snapshot riêng như `data/sentiment_holdout_v1.csv`; tuning script không được đọc file này. Release-evaluation job cần:

```text
load models:/sentiment-classifier@candidate
  -> predict immutable holdout
  -> compute test metrics và per-class errors
  -> log holdout_test_report.json trong một release-evaluation run
  -> link model version + source training run
  -> set holdout_test_status=passed chỉ khi mọi gate đạt
```

Không gắn tag `passed` bằng tay nếu chưa có artifact và run ID chứng minh kết quả. Nếu sau nhiều release bạn liên tục nhìn holdout để điều chỉnh model, holdout đó đã trở thành validation set; hãy tạo holdout mới.

## 7. Promote candidate thành champion

Không nên tự động promote chỉ vì một run có metric cao nhất. Nên có bước validation và approval riêng.

File gợi ý: `promote_model.py`.

```python
import argparse

import mlflow
from mlflow import MlflowClient


def promote(tracking_uri: str, model_name: str, source_alias: str, target_alias: str) -> None:
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    candidate = client.get_model_version_by_alias(model_name, source_alias)
    if candidate.tags.get("validation_gate") != "passed":
        raise RuntimeError(
            f"Model version {candidate.version} chưa qua validation gate: "
            f"{candidate.tags.get('validation_gate')}"
        )
    if candidate.tags.get("holdout_test_status") != "passed":
        raise RuntimeError(
            f"Model version {candidate.version} chưa qua holdout test: "
            f"{candidate.tags.get('holdout_test_status')}"
        )

    client.set_model_version_tag(
        name=model_name,
        version=candidate.version,
        key="approval_status",
        value="approved",
    )
    client.set_registered_model_alias(
        name=model_name,
        alias=target_alias,
        version=candidate.version,
    )
    print(f"Promoted {model_name} version {candidate.version} to @{target_alias}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-uri", default="http://127.0.0.1:5000")
    parser.add_argument("--model-name", default="sentiment-classifier")
    parser.add_argument("--source-alias", default="candidate")
    parser.add_argument("--target-alias", default="champion")
    args = parser.parse_args()
    promote(args.tracking_uri, args.model_name, args.source_alias, args.target_alias)
```

Ứng dụng serving nên load model bằng alias ổn định:

```python
import mlflow.pyfunc

model = mlflow.pyfunc.load_model("models:/sentiment-classifier@champion")
predictions = model.predict(["Dịch vụ hỗ trợ rất nhanh"])
```

Rollback là thao tác trỏ alias `champion` về version trước đó, không phải rebuild model trong lúc incident.

## 8. Tracking cho LoRA, LLM và RAG

Với Day 27 LoRA, model artifact thường là adapter, không phải full base model. Cần log thêm:

| Thành phần | Cần log |
|---|---|
| Base model | `base_model_id`, `base_model_revision`, license |
| Adapter | LoRA rank, alpha, dropout, target modules |
| Dataset | instruction dataset version/hash, filtering rule |
| Prompt | chat template version, system prompt version |
| Eval | task metrics, safety eval, latency, VRAM, tokens/sec |
| Serving | quantization, max tokens, batch size |

Với RAG, "model version" không chỉ là LLM. Cần tracking cả pipeline:

```text
corpus_version
chunking_strategy
embedding_model
embedding_dimension
index_version
retriever_config
reranker_model
prompt_version
llm_model
eval_set_version
```

Nếu đổi chunk size hoặc embedding model mà không log `index_version`, regression RAG rất khó debug.

## 9. Trade-off quan trọng

| Lựa chọn | Điểm mạnh | Điểm yếu | Khi nào chọn |
|---|---|---|---|
| Log đầy đủ artifacts | Debug và audit tốt | Tốn storage, có rủi ro PII | Production hoặc regulated workflow |
| Chỉ log summary metrics | Nhanh, rẻ | Khó reproduce và rollback | Prototype rất ngắn hạn |
| Local MLflow | Dễ học, không phụ thuộc SaaS | Không có backup/auth/collaboration tốt | Bài học, portfolio, solo project |
| Self-host MLflow | Kiểm soát dữ liệu tốt | Cần vận hành DB, artifact store, auth | Team có yêu cầu data residency |
| Managed SaaS như W&B/Neptune | Collaboration và dashboard mạnh | Cost, vendor policy, data egress | Team research/product cần UI mạnh |
| Manual promotion | Kiểm soát chặt | Dễ quên bước, chậm | Model có rủi ro business cao |
| Automated promotion | Nhanh, consistent | Gate sai có thể đẩy model lỗi | Metric ổn định, có canary/rollback |

Best default cho khóa học: MLflow local/self-host, log đầy đủ run metadata, dùng aliases `candidate` và `champion`, chỉ promote sau khi có decision note. Với team production nhỏ, self-host MLflow + Postgres + object storage là lựa chọn cân bằng giữa cost, control và đủ tính năng.

## 10. Performance, cost, security, reproducibility

Performance concerns:

- Log artifact quá lớn trong training loop có thể làm chậm job.
- UI query chậm nếu backend store phình to và không có retention policy.
- Registry alias chỉ giải quyết chọn model version; serving vẫn cần cache model và warm-up riêng.
- Model tốt nhất theo `val_macro_f1` có thể không đạt latency/cost gate.

Cost concerns:

- Artifact store tăng nhanh nếu log checkpoint mỗi epoch.
- LLM/RAG eval có thể tốn tiền nếu replay golden set lớn bằng provider managed.
- Managed tracking tool tính phí theo user, run, artifact hoặc storage.

Security concerns:

- Không log API key, token, raw PII, customer text nhạy cảm vào params/tags/artifacts.
- Tracking UI phải có authentication, authorization, TLS và network boundary.
- Artifact store cần encryption, IAM least privilege và lifecycle policy.
- Model artifact có thể chứa serialized code; không load model từ registry không tin cậy.

Reproducibility concerns:

- `seed=42` chưa đủ nếu thiếu dataset hash, split strategy, dependency versions và hardware note.
- Base model hoặc tokenizer trên Hugging Face cần pin revision, không chỉ pin model id.
- Evaluation script cũng phải version, vì đổi metric code có thể đổi kết luận.
- Với RAG, phải version index và prompt như version model.

## 11. Dùng được trong production không?

Có, MLflow dùng được trong production nếu đáp ứng các điều kiện sau:

- Tracking Server chạy trên hạ tầng có backup, monitoring, authentication, TLS và access control.
- Backend store dùng Postgres/MySQL hoặc service tương đương, không dùng SQLite local cho nhiều người dùng.
- Artifact store dùng object storage bền vững như S3/GCS/Azure Blob, có encryption và lifecycle policy.
- Training pipeline bắt buộc log dataset version/hash, code commit, params, metrics, artifacts và model signature.
- Model Registry alias là contract với deployment, ví dụ serving chỉ đọc `models:/sentiment-classifier@champion`.
- Promotion có validation gate, holdout test chạy đúng một lần cho candidate, latency/cost gate, security review, data leakage check và rollback target.
- Không log dữ liệu nhạy cảm chưa redact.
- Có monitoring sau deploy để phát hiện drift, latency regression, error rate và business metric regression.

Không nên xem MLflow là toàn bộ production platform. MLflow quản lý lineage, artifact và registry; bạn vẫn cần CI/CD, serving infra, observability, security, data validation và incident process.

## 12. Kết quả cần nộp

Cuối Day 41, bạn nên có:

- MLflow UI có ít nhất 3 runs.
- Mỗi run có params, validation metrics, dataset inputs, artifacts và logged model.
- Một registered model tên rõ, ví dụ `sentiment-classifier`.
- Alias `candidate` trỏ tới version được chọn sau khi so sánh validation công bằng.
- Candidate có holdout test report và tag `holdout_test_status=passed`.
- Alias `champion` trỏ tới version được approve để serve.
- `model_card.md`, `eval_summary.json` và decision note.
- Rollback plan: version trước đó là gì và lệnh nào đổi alias về version đó.
