# AI Engineer — 50 ngày từ Senior SE sang AI Production Engineer

Lộ trình dành cho Senior Software Engineer muốn chuyển hướng sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus. Trọng tâm không phải research mà là đưa AI vào production: ML foundation, LLM application engineering, RAG production, MLOps và capstone portfolio.

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học theo thứ tự sau để nhanh nhất có thể build được AI production system:

1. [Day 17: LLM Fundamentals](./lessions/day-17-llm-fundamentals/lession.md) — hiểu LLM runtime, token, temperature, decoding
2. [Day 18: Prompt Engineering thực chiến](./lessions/day-18-prompt-engineering-thuc-chien/lession.md) — zero-shot, few-shot, CoT, prompt template
3. [Day 19: Structured Output & Function Calling](./lessions/day-19-structured-output-function-calling/lession.md) — JSON schema, tool calling, output validation
4. [Day 20: LLM App Architecture cho Production](./lessions/day-20-llm-app-architecture-production/lession.md) — gateway, router, cache, audit log
5. [Day 31: RAG Architecture](./lessions/day-31-rag-architecture/lession.md) — indexing pipeline, query pipeline, citation
6. [Day 33: Vector DB](./lessions/day-33-vector-db/lession.md) — ANN search, HNSW, Qdrant, pgvector
7. [Day 40: Mini-project Production RAG System](./lessions/day-40-mini-project-production-rag-system/lession.md) — end-to-end RAG có eval, monitoring, Docker

Sau 7 bài này bạn đã có thể build và deploy một RAG system production-style. Phần còn lại là mở rộng để làm đúng, làm sâu và tối ưu.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable |
|---|---:|---|---|
| Phase 1 | Day 1-8 | ML Foundation | Customer Churn ML Pipeline |
| Phase 2 | Day 9-16 | Deep Learning, NLP, Transformer | Fine-tuned PhoBERT/BERT Classifier |
| Phase 3 | Day 17-24 | LLM Application Engineering | AI Assistant có tool calling + memory |
| Phase 4 | Day 25-30 | Fine-tuning & Local LLM | LoRA experiment + local model API |
| Phase 5 | Day 31-40 | Production RAG | Production RAG system |
| Phase 6 | Day 41-47 | MLOps & Production AI | Deployable AI service với monitoring |
| Phase 7 | Day 48-50 | Capstone & Portfolio | GitHub repo + README + demo |

## Mức độ ưu tiên (80/20 analysis)

### Nhóm A — Bắt buộc học trước (20% kiến thức tạo 80% giá trị)

| Bài | Chủ đề | Vì sao quan trọng |
|---|---|---|
| Day 17 | LLM Fundamentals | Nền tảng để hiểu mọi thứ về LLM |
| Day 18 | Prompt Engineering | Kỹ năng dùng hằng ngày, quyết định quality output |
| Day 19 | Structured Output & Function Calling | Production pattern quan trọng nhất |
| Day 20 | LLM App Architecture | Thiết kế hệ thống có gateway, cache, monitoring |
| Day 21 | Raw SDK vs LangChain vs LlamaIndex vs LangGraph | Chọn đúng công cụ cho bài toán |
| Day 22 | Agent Patterns với LangGraph | Agent là pattern cốt lõi của AI application |
| Day 31 | RAG Architecture | Hiểu toàn bộ RAG pipeline |
| Day 33 | Vector DB | Core infrastructure của RAG |
| Day 34 | Chunking Strategies | Quyết định retrieval quality |
| Day 36 | Hybrid Search | Production retrieval bắt buộc phải có |
| Day 37 | Reranking | Tăng retrieval quality đáng kể |
| Day 40 | Mini-project Production RAG System | Tổng hợp tất cả |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---|
| Day 1 | AI Mindset | Mental model đúng trước khi học chi tiết |
| Day 3 | ML Fundamentals | Overfitting, bias-variance, evaluation |
| Day 4 | Python ML Stack | NumPy, Pandas, scikit-learn dùng xuyên suốt |
| Day 6 | Model Evaluation Metrics | Chọn metric đúng, tránh bẫy accuracy |
| Day 7 | Error Analysis, Data Leakage | Kỹ năng debug model thực tế |
| Day 8 | Customer Churn ML Pipeline | Mini-project ML đầu tiên |
| Day 32 | Embedding Models & Benchmark | Chọn embedding model phù hợp |
| Day 35 | Metadata, Citation, Permission-aware RAG | Enterprise RAG bắt buộc |
| Day 38 | Advanced RAG Patterns | Query rewriting, multi-query, HyDE |
| Day 39 | RAG Evaluation | Đo retrieval quality, faithfulness |
| Day 42 | Model Serving | FastAPI, streaming, batching |
| Day 44 | Observability cho LLM App | Langfuse, tracing, monitoring |
| Day 46 | Guardrails | Prompt injection defense, output validation |

### Nhóm C — Học sau khi làm được project cơ bản

| Bài | Chủ đề | Khi nào quay lại |
|---|---|---|
| Day 9-14 | Neural Network, PyTorch, Transformer | Khi cần fine-tune hoặc hiểu sâu model internals |
| Day 15 | HuggingFace Ecosystem | Khi cần load/train model từ Hub |
| Day 16 | Fine-tune PhoBERT/BERT Classifier | Khi cần NLP classification production |
| Day 25-27 | Fine-tuning, LoRA/QLoRA | Khi cần custom model cho domain cụ thể |
| Day 29-30 | Local LLM, Quantization | Khi cần on-premise hoặc giảm cost |
| Day 41 | MLflow, Experiment Tracking | Khi team cần experiment tracking |
| Day 43 | Docker/K8s/GPU Serving | Khi deploy AI workload với GPU |
| Day 45 | Cost Optimization | Khi cost bắt đầu là vấn đề |
| Day 47 | LLM Testing, Golden Set, CI/CD | Khi cần release automation |

### Nhóm D — Đọc lướt / tra cứu

| Bài | Chủ đề | Ghi chú |
|---|---|---|
| Day 2 | Math đủ dùng cho ML | Tra cứu khi cần, không cần học thuộc |
| Day 5 | Feature Engineering | Xem lại khi làm tabular data |
| Day 23 | Security Basics cho LLM App | Đọc để biết, implement khi triển khai |
| Day 48-50 | Capstone & Portfolio | Làm sau khi hoàn thành các phase trước |
| Các file `document.md` | Chi tiết mở rộng | Đọc như tài liệu tham khảo |

## Cách học đề xuất

1. **Ưu tiên Phase 3 + 5 trước** (Day 17-24, 31-40): đây là 20% kiến thức tạo 80% giá trị. Học xong bạn đã build được LLM app + RAG system.
2. **Sau đó quay lại Phase 1** (Day 1-8) để hiểu ML foundation đủ để debug và ra quyết định.
3. **Phase 2 + 4** (Day 9-16, 25-30) học khi cần fine-tune hoặc hiểu sâu model internals.
4. **Phase 6 + 7** (Day 41-50) học khi chuẩn bị đưa system vào production thật.

Mỗi ngày học 2 giờ theo format:
- 10 phút: đọc TL;DR và mục tiêu
- 35 phút: học concept chính (đọc `lession.md`)
- 45 phút: hands-on (làm `exercise.md`, tham khảo `document.md`)
- 20 phút: ghi chú trade-off, performance concern
- 10 phút: update learning log

## Tài nguyên

- [Lộ trình 50 ngày chi tiết](./lo_trinh_50_ngay_senior_se_to_ai_engineer.md)
- [README tổng quan](./README.md)
- [Review checklist](./review-and-fixed-checklist.md)
