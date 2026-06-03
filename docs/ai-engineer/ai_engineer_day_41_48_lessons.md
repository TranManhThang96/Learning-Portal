# 8 Bai Hoc Tiep Theo Cho AI Engineer

Nguon: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, Phase 6 - MLOps & Production AI va dau Phase 7 - Capstone & Portfolio.

Doi tuong: Senior Software Engineer muon chuyen sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus.

Khung hoc moi ngay: 2 gio.

## Muc Luc

| Ngay | Chu de | Output chinh |
|---:|---|---|
| Day 41 | MLflow, Experiment Tracking, Model Registry | MLflow run + registered model + model card |
| Day 42 | Model Serving | FastAPI service + SSE streaming + latency test |
| Day 43 | Docker/K8s/GPU Serving cho AI Workload | Docker Compose + optional K8s manifests + deployment note |
| Day 44 | Observability cho LLM App | Trace schema + JSON logs + feedback endpoint |
| Day 45 | Cost Optimization | Cost plan + token budget + optimization PR note |
| Day 46 | Guardrails | Policy matrix + schema/citation validation + red-team tests |
| Day 47 | LLM Testing, Golden Set, CI/CD cho Prompt/RAG | Golden set + eval runner + CI threshold gate |
| Day 48 | Capstone Architecture Review + Backend/API | Capstone backend/API + architecture + readiness gate |

## File Chi Tiet

| Ngay | File |
|---:|---|
| Day 41 | [MLflow, Experiment Tracking, Model Registry](./bai-hoc-day-41-48/day-41-mlflow-experiment-tracking-model-registry.md) |
| Day 42 | [Model Serving](./bai-hoc-day-41-48/day-42-model-serving.md) |
| Day 43 | [Docker/K8s/GPU Serving cho AI Workload](./bai-hoc-day-41-48/day-43-docker-k8s-gpu-serving-ai-workload.md) |
| Day 44 | [Observability cho LLM App](./bai-hoc-day-41-48/day-44-observability-cho-llm-app.md) |
| Day 45 | [Cost Optimization](./bai-hoc-day-41-48/day-45-cost-optimization.md) |
| Day 46 | [Guardrails](./bai-hoc-day-41-48/day-46-guardrails.md) |
| Day 47 | [LLM Testing, Golden Set, CI/CD cho Prompt/RAG](./bai-hoc-day-41-48/day-47-llm-testing-golden-set-cicd-prompt-rag.md) |
| Day 48 | [Capstone Architecture Review + Backend/API](./bai-hoc-day-41-48/day-48-capstone-architecture-review-backend-api.md) |

## Tong Quan Learning Path

Day 41-47 hoan tat Phase 6: MLOps & Production AI. Neu Day 33-40 da build duoc Production RAG system, nhom bai nay dua system do vao operational shape: tracking, serving, deployment, observability, cost, guardrails va CI/CD eval.

Day 48 bat dau Phase 7: Capstone & Portfolio. Muc tieu la dong scope capstone Vietnamese Enterprise Knowledge Assistant va hoan thien backend/API truoc khi lam UI, monitoring report, README, demo va portfolio assets o Day 49-50.

## Artifact Nen Co Sau Day 41-48

| Artifact | Den tu ngay | Gia tri production |
|---|---:|---|
| MLflow run + registry note | Day 41 | Reproduce va audit model/experiment lineage |
| FastAPI serving API | Day 42 | Contract ro cho model/RAG inference |
| Streaming endpoint | Day 42 | UX tot hon va do duoc TTFT |
| Docker Compose deployment | Day 43 | Reviewer chay duoc local bang mot lenh |
| Optional K8s/GPU manifests | Day 43 | Hieu resource scheduling cho AI workload |
| Trace schema + logs | Day 44 | Debug latency, cost, retrieval va citation |
| Feedback endpoint | Day 44 | Noi user feedback voi trace |
| Cost plan | Day 45 | Capacity planning va budget control |
| Token budget | Day 45 | Enforce latency/cost boundary |
| Guardrail policy matrix | Day 46 | Allow/refuse/escalate ro rang |
| PII redaction + citation validation | Day 46 | Giam privacy va hallucination risk |
| Golden set + eval runner | Day 47 | Regression suite cho Prompt/RAG |
| CI threshold gate | Day 47 | Block deploy khi quality regression |
| Capstone backend/API | Day 48 | Nen mong cho UI, monitoring va portfolio |

## Production Gate

Truoc khi tiep tuc Day 49-50, capstone can co it nhat:

- Backend API co `/health`, `/ready`, `/query`, document ingestion, trace va eval endpoints.
- Docker Compose chay duoc local voi vector DB va sample docs.
- Query response co answer, citations, trace id va latency per stage.
- Tenant/ACL filter apply truoc retrieval/context.
- Citation validator khong cho cite source nam ngoai context.
- Trace log co model, prompt, embedding, index va reranker version.
- Cost estimate co token budget va retry limit.
- Guardrail matrix co allow/refuse/escalate va red-team prompts.
- Golden eval set 30+ questions co no-answer, ACL va prompt injection cases.
- CI smoke eval co thresholds cho Recall@K, MRR, citation correctness, faithfulness va format pass rate.

## Learning Cadence

| Thoi luong | Viec lam |
|---:|---|
| 10 phut | Doc TL;DR va muc tieu |
| 35 phut | Hoc concept chinh |
| 45 phut | Hands-on/code/design |
| 20 phut | Ghi chu trade-off, performance, production concern |
| 10 phut | Update learning log |

