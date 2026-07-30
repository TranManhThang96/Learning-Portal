# AI Engineer Learning Notes

Repo này chứa khóa học chuyển đổi từ Senior Software Engineer sang GenAI/RAG/LLM Production Engineer.

Nguồn plan: [lo_trinh_50_ngay_senior_se_to_ai_engineer.md](./lo_trinh_50_ngay_senior_se_to_ai_engineer.md).

## Bài Mở Đầu

| Ngày | Bài học | Mục tiêu |
|---:|---|---|
| Day 00 | [Tổng quan AI hiện nay và nghề AI Engineer](./lessions/day-00-tong-quan-ai-hien-nay-va-nghe-ai-engineer.md) | Hiểu bức tranh AI 2026, cơ hội nghề nghiệp, ứng dụng thực tế, skill stack và cách học lộ trình 50 ngày |

## Mục Lục 50 Ngày

| Phase | Ngày | Chủ đề | Deliverable |
|---|---:|---|---|
| Phase 1 | Day 1-8 | ML Foundation | Customer Churn ML Pipeline |
| Phase 2 | Day 9-16 | Deep Learning, NLP, Transformer | Fine-tuned PhoBERT/BERT Classifier |
| Phase 3 | Day 17-24 | LLM Application Engineering | AI Assistant có tool calling + memory |
| Phase 4 | Day 25-30 | Fine-tuning & Local LLM | LoRA experiment + local model API |
| Phase 5 | Day 31-40 | Production RAG | Production RAG system |
| Phase 6 | Day 41-47 | MLOps & Production AI | Deployable AI service với monitoring |
| Phase 7 | Day 48-50 | Capstone & Portfolio | GitHub repo + README + demo + blog/CV/LinkedIn |

## Day 1-8: ML Foundation

| Ngày | Bài học |
|---:|---|
| Day 1 | [AI Mindset cho Senior SE](./lessions/day-01-ai-mindset-cho-senior-se.md) |
| Day 2 | [Math đủ dùng cho ML](./lessions/day-02-math-du-dung-cho-ml.md) |
| Day 3 | [ML Fundamentals](./lessions/day-03-ml-fundamentals.md) |
| Day 4 | [Python ML Stack](./lessions/day-04-python-ml-stack.md) |
| Day 5 | [Feature Engineering](./lessions/day-05-feature-engineering.md) |
| Day 6 | [Model Evaluation Metrics](./lessions/day-06-model-evaluation-metrics.md) |
| Day 7 | [Error Analysis, Data Leakage, Threshold Tuning](./lessions/day-07-error-analysis-data-leakage-threshold-tuning.md) |
| Day 8 | [Customer Churn ML Pipeline](./lessions/day-08-customer-churn-ml-pipeline.md) |

## Day 9-16: Deep Learning, NLP, Transformer

| Ngày | Bài học |
|---:|---|
| Day 9 | [Neural Network từ Zero](./lessions/day-09-neural-network-tu-zero.md) |
| Day 10 | [PyTorch Fundamentals](./lessions/day-10-pytorch-fundamentals.md) |
| Day 11 | [Training Loop, Optimizer, Scheduler](./lessions/day-11-training-loop-optimizer-scheduler.md) |
| Day 12 | [NLP Fundamentals & Tokenizer](./lessions/day-12-nlp-fundamentals-tokenizer.md) |
| Day 13 | [Attention Mechanism](./lessions/day-13-attention-mechanism.md) |
| Day 14 | [Transformer Architecture](./lessions/day-14-transformer-architecture.md) |
| Day 15 | [Hugging Face Ecosystem](./lessions/day-15-huggingface-ecosystem.md) |
| Day 16 | [Fine-tune PhoBERT/BERT Classifier](./lessions/day-16-fine-tune-phobert-bert-classifier.md) |

## Day 17-24: LLM Application Engineering

| Ngày | Bài học |
|---:|---|
| Day 17 | [LLM Fundamentals](./lessions/day-17-llm-fundamentals.md) |
| Day 18 | [Prompt Engineering Thực Chiến](./lessions/day-18-prompt-engineering-thuc-chien.md) |
| Day 19 | [Structured Output & Function Calling](./lessions/day-19-structured-output-function-calling.md) |
| Day 20 | [LLM App Architecture Cho Production](./lessions/day-20-llm-app-architecture-production.md) |
| Day 21 | [Raw SDK vs LangChain vs LlamaIndex vs LangGraph](./lessions/day-21-raw-sdk-langchain-llamaindex-langgraph.md) |
| Day 22 | [Agent Patterns Với LangGraph](./lessions/day-22-agent-patterns-voi-langgraph.md) |
| Day 23 | [Security Basics Cho LLM App](./lessions/day-23-security-basics-cho-llm-app.md) |
| Day 24 | [AI Assistant Có Tool Calling + Memory](./lessions/day-24-ai-assistant-tool-calling-memory.md) |

## Day 25-30: Fine-tuning & Local LLM

| Ngày | Bài học |
|---:|---|
| Day 25 | [Khi nào Fine-tune, khi nào dùng RAG](./lessions/day-25-khi-nao-fine-tune-khi-nao-dung-rag.md) |
| Day 26 | [Dataset Preparation Cho Instruction Tuning](./lessions/day-26-dataset-preparation-instruction-tuning.md) |
| Day 27 | [LoRA/QLoRA Hands-on](./lessions/day-27-lora-qlora-hands-on.md) |
| Day 28 | [Evaluation Trước/Sau Fine-tune](./lessions/day-28-evaluation-truoc-sau-fine-tune.md) |
| Day 29 | [Local LLM - Ollama, llama.cpp, vLLM](./lessions/day-29-local-llm-ollama-llama-cpp-vllm.md) |
| Day 30 | [Quantization & Deploy Local Model API](./lessions/day-30-quantization-deploy-local-model-api.md) |

## Day 31-40: Production RAG

| Ngày | Bài học |
|---:|---|
| Day 31 | [RAG Architecture](./lessions/day-31-rag-architecture.md) |
| Day 32 | [Embedding Models & Benchmark Cho Tiếng Việt](./lessions/day-32-embedding-models-benchmark-tieng-viet.md) |
| Day 33 | [Vector DB](./lessions/day-33-vector-db.md) |
| Day 34 | [Chunking Strategies](./lessions/day-34-chunking-strategies.md) |
| Day 35 | [Metadata, Citation, Permission-aware RAG](./lessions/day-35-metadata-citation-permission-aware-rag.md) |
| Day 36 | [Hybrid Search - Dense + Sparse + BM25](./lessions/day-36-hybrid-search-dense-sparse-bm25.md) |
| Day 37 | [Reranking](./lessions/day-37-reranking.md) |
| Day 38 | [Advanced RAG Patterns](./lessions/day-38-advanced-rag-patterns.md) |
| Day 39 | [RAG Evaluation](./lessions/day-39-rag-evaluation.md) |
| Day 40 | [Mini-project - Production RAG System](./lessions/day-40-mini-project-production-rag-system.md) |

## Day 41-50: MLOps, Production AI Và Portfolio

| Ngày | Bài học |
|---:|---|
| Day 41 | [MLflow, Experiment Tracking, Model Registry](./lessions/day-41-mlflow-experiment-tracking-model-registry.md) |
| Day 42 | [Model Serving](./lessions/day-42-model-serving.md) |
| Day 43 | [Docker/K8s/GPU Serving Cho AI Workload](./lessions/day-43-docker-k8s-gpu-serving-ai-workload.md) |
| Day 44 | [Observability Cho LLM App](./lessions/day-44-observability-cho-llm-app.md) |
| Day 45 | [Cost Optimization](./lessions/day-45-cost-optimization.md) |
| Day 46 | [Guardrails](./lessions/day-46-guardrails.md) |
| Day 47 | [LLM Testing, Golden Set, CI/CD Cho Prompt/RAG](./lessions/day-47-llm-testing-golden-set-cicd-prompt-rag.md) |
| Day 48 | [Capstone Architecture Review + Backend/API](./lessions/day-48-capstone-architecture-review-backend-api.md) |
| Day 49 | [UI, Monitoring, Evaluation Report](./lessions/day-49-ui-monitoring-evaluation-report.md) |
| Day 50 | [README, Demo, Blog, CV/LinkedIn](./lessions/day-50-readme-demo-blog-cv-linkedin.md) |

## Cấu Trúc Mỗi Bài

Mỗi bài học chính nằm trong `ai-engineer/lessions/day-xx-.../`:

| File | Vai trò |
|---|---|
| `lession.md` | Bài học chính, học theo thứ tự từ cơ bản đến chi tiết |
| `document.md` | Tùy chọn: tài liệu đính kèm hoặc reference cần tra cứu độc lập |
| `exercise.md` | Tùy chọn: bài tập đủ lớn để cần workflow và deliverable riêng |

Nguyên tắc phân tách:

- Nội dung cần học để hiểu chủ đề phải nằm trọn trong `lession.md`.
- Không chuyển phần giải thích, trade-off hoặc best practice sang `document.md`.
- Chỉ tạo `document.md` khi có reference/checklist độc lập đáng để tra cứu lại.
- Chỉ tạo `exercise.md` khi bài thực hành đủ lớn; quiz ngắn có thể nằm cuối `lession.md`.
- Day 00 cố ý chỉ có `lession.md` vì đây là bài định hướng liền mạch.

Các file `ai-engineer/lessions/day-xx-....md` ở cấp ngoài là trang điều hướng về bài tương ứng.

## Learning Cadence

| Thời lượng | Việc làm |
|---:|---|
| 10 phút | Đọc TL;DR và mục tiêu |
| 35 phút | Học concept chính |
| 45 phút | Hands-on/code/design |
| 20 phút | Ghi chú trade-off, performance, production concern |
| 10 phút | Update learning log |
