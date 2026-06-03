# Day 41: MLflow, Experiment Tracking, Model Registry

Day 41 mở đầu Phase 6 bằng một năng lực MLOps rất thực tế: biến training từ một script khó kiểm soát thành một workflow có lineage, audit trail, reproducibility và rollback path.

## Nội dung

1. [Lession: MLflow, Experiment Tracking và Model Registry](./day-41-mlflow-experiment-tracking-model-registry/lession.md)
   - Hiểu experiment tracking, params, metrics, artifacts, dataset lineage và code version.
   - Thiết kế workflow từ training run đến registered model, alias `candidate`/`champion`, rollback và production gate.
   - Code ví dụ gần production cho MLflow Tracking, Dataset logging, Model Registry và latency benchmark.
   - Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

2. [Document: Template, checklist và runbook](./day-41-mlflow-experiment-tracking-model-registry/document.md)
   - Tracking schema, naming convention, artifact structure và model card template.
   - Runbook chọn best run, register, validate, promote, rollback và xử lý incident.
   - Checklist về performance, cost, security, reproducibility và governance.
   - So sánh thực dụng MLflow, W&B, Neptune và custom tracking.

3. [Exercise: Lab MLflow tracking và registry](./day-41-mlflow-experiment-tracking-model-registry/exercise.md)
   - Track lại training từ Day 16 hoặc Day 27.
   - Chạy ít nhất 3 runs, log params/metrics/artifacts/dataset/code version.
   - Register model, gắn alias `candidate`, promote `champion` sau khi qua gate, viết decision note.
   - Hoàn thành production readiness answer và rollback plan.

## Mục tiêu sau bài học

- Biết vì sao model không thể production-ready nếu không truy vết được data, code, config, metric và artifact.
- Biết log đầy đủ một training run bằng MLflow thay vì chỉ lưu notebook hoặc file model rời rạc.
- Biết dùng Model Registry để quản lý model version, alias, metadata, approval và rollback.
- Biết đánh giá trade-off giữa tracking đầy đủ, storage cost, privacy, collaboration và vận hành.
- Biết viết release decision có metric gate, latency gate, limitation và điều kiện production.
