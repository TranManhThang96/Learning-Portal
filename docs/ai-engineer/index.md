# AI Engineer — 50 ngày từ Senior SE đến GenAI/RAG/LLM Production Engineer

Lộ trình dành cho Senior Software Engineer muốn chuyển hướng sang AI Engineer / GenAI Engineer, tập trung vào LLM Application Engineering, Production RAG và MLOps.

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học 11 bài sau trước — đây là 20% kiến thức tạo ra 80% giá trị thực tế:

1. [Day 00: Tổng quan AI hiện nay và nghề AI Engineer](./lessions/day-00-tong-quan-ai-hien-nay-va-nghe-ai-engineer) — bức tranh AI 2026, cơ hội nghề nghiệp, skill stack
2. [Day 01: AI Mindset cho Senior SE](./lessions/day-01-ai-mindset-cho-senior-se) — map AI concepts về tư duy SE: model = function học từ data, training = build, evaluation = test suite xác suất
3. [Day 03: ML Fundamentals](./lessions/day-03-ml-fundamentals) — supervised/unsupervised, train/val/test, overfitting, bias-variance, baseline-first mindset
4. [Day 04: Python ML Stack](./lessions/day-04-python-ml-stack) — NumPy, Pandas, scikit-learn pipeline, estimator API
5. [Day 06: Model Evaluation Metrics](./lessions/day-06-model-evaluation-metrics) — precision/recall/F1, ROC-AUC, PR-AUC, business metric vs ML metric
6. [Day 17: LLM Fundamentals](./lessions/day-17-llm-fundamentals) — pre-training, SFT, RLHF, context window, temperature, model families
7. [Day 18: Prompt Engineering Thực Chiến](./lessions/day-18-prompt-engineering-thuc-chien) — zero-shot, few-shot, CoT, prompt template, versioning, A/B testing
8. [Day 19: Structured Output & Function Calling](./lessions/day-19-structured-output-function-calling) — JSON Schema, tool calling, output parser, retry khi sai schema
9. [Day 20: LLM App Architecture Cho Production](./lessions/day-20-llm-app-architecture-production) — LLM gateway, model router, fallback, rate limiting, semantic cache, audit log
10. [Day 31: RAG Architecture](./lessions/day-31-rag-architecture) — indexing pipeline, query pipeline, chunker, embedding, vector DB, retriever, reranker, citation
11. [Day 33: Vector DB](./lessions/day-33-vector-db) — ANN search, HNSW, Qdrant, pgvector, Milvus, metadata filtering, multi-tenancy

Sau 11 bài này bạn đã có thể: ra quyết định dùng rule/ML/LLM/RAG, build LLM app với structured output + function calling, thiết kế RAG system cơ bản, và hiểu stack để tự học tiếp các phần còn lại.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---|---|---:|
| Phase 0 | Day 00 | Tổng quan AI & nghề AI Engineer | Career map + skill gap |
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
|---|---|---:|
| Day 00 | Tổng quan AI & nghề AI Engineer | Định hướng: hiểu bức tranh AI 2026, biết mình đang học gì và để làm gì |
| Day 01 | AI Mindset cho Senior SE | Chuyển đổi tư duy từ deterministic → probabilistic; biết khi nào dùng rule/ML/LLM/RAG |
| Day 03 | ML Fundamentals | Nền tảng: supervised learning, overfitting, bias-variance — không hiểu thì không debug được model |
| Day 04 | Python ML Stack | Công cụ hàng ngày: NumPy, Pandas, scikit-learn pipeline |
| Day 06 | Model Evaluation Metrics | Không bị bẫy accuracy; chọn đúng metric cho business problem |
| Day 17 | LLM Fundamentals | Core concepts: pre-training, context window, temperature, model families |
| Day 18 | Prompt Engineering Thực Chiến | Kỹ năng dùng hàng ngày: prompt template, CoT, few-shot, versioning |
| Day 19 | Structured Output & Function Calling | Bắt buộc cho production LLM: JSON output, tool calling, output validation |
| Day 20 | LLM App Architecture | Thiết kế system: gateway, router, cache, rate limit, retry, audit log |
| Day 31 | RAG Architecture | Kiến trúc nền cho RAG: ingestion → chunk → embed → store → retrieve → rerank → generate |
| Day 33 | Vector DB | Chọn và dùng vector DB đúng: pgvector, Qdrant, Milvus, Chroma |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---:|
| Day 05 | Feature Engineering | Feature quality quyết định model quality; preprocessing pipeline là kỹ năng thiết yếu |
| Day 07 | Error Analysis, Data Leakage, Threshold Tuning | Debug model: biết model sai ở đâu, phát hiện data leakage, tune threshold |
| Day 08 | Customer Churn ML Pipeline (mini-project) | Thực hành end-to-end ML pipeline đầu tiên |
| Day 09 | Neural Network từ Zero | Hiểu neuron, forward pass, backprop — nền tảng cho toàn bộ DL |
| Day 10 | PyTorch Fundamentals | Tensor, autograd, nn.Module, DataLoader — công cụ DL chính |
| Day 11 | Training Loop, Optimizer, Scheduler | Training loop anatomy, Adam/AdamW, learning rate schedule, early stopping |
| Day 12 | NLP Fundamentals & Tokenizer | BPE, WordPiece, token limit, token cost — đặc biệt quan trọng với tiếng Việt |
| Day 13 | Attention Mechanism | Q/K/V, scaled dot-product attention, multi-head — cốt lõi của Transformer |
| Day 14 | Transformer Architecture | Encoder/decoder-only, BERT vs GPT vs T5, positional encoding, RoPE |
| Day 15 | HuggingFace Ecosystem | transformers, datasets, AutoTokenizer, Trainer API — dùng hàng ngày |
| Day 21 | Raw SDK vs LangChain vs LlamaIndex vs LangGraph | Chọn framework đúng: không phải lúc nào cũng cần LangChain |
| Day 22 | Agent Patterns với LangGraph | ReAct, planner-executor, router agent, human-in-the-loop |
| Day 23 | Security Basics cho LLM App | Prompt injection, jailbreak, data exfiltration — bắt buộc cho production |
| Day 32 | Embedding Models & Benchmark Tiếng Việt | Chọn embedding model cho tiếng Việt: BGE, E5, multilingual |
| Day 34 | Chunking Strategies | Fixed-size, recursive, semantic, markdown-aware — chunking sai → retrieval kém |
| Day 36 | Hybrid Search (Dense + Sparse + BM25) | Dense + BM25 + RRF — pattern phổ biến nhất trong production RAG |
| Day 37 | Reranking | Bi-encoder vs cross-encoder, two-stage retrieval: retrieve 50 → rerank top 5 |

### Nhóm C — Học sau khi làm được project cơ bản

| Bài | Chủ đề | Khi nào quay lại |
|---|---|---:|
| Day 02 | Math đủ dùng cho ML | Học khi cần debug model sâu hoặc đọc paper — không cần học trước Day 03 |
| Day 16 | Fine-tune PhoBERT/BERT Classifier | Sau khi đã hiểu Transformer và HuggingFace |
| Day 24 | AI Assistant Tool Calling + Memory (mini-project) | Sau khi học xong Day 18-23 |
| Day 25 | Khi nào Fine-tune, khi nào dùng RAG | Quan trọng nhưng cần context từ RAG và LLM trước |
| Day 26-28 | Fine-tuning dataset, LoRA/QLoRA, evaluation | Sau khi đã build được LLM app cơ bản |
| Day 29-30 | Local LLM (Ollama, llama.cpp, vLLM), Quantization | Khi cần privacy/cost optimization |
| Day 35 | Metadata, Citation, Permission-aware RAG | Khi RAG system cần enterprise features |
| Day 38 | Advanced RAG Patterns | Sau khi RAG cơ bản chạy ổn định |
| Day 39 | RAG Evaluation (RAGAS, TruLens) | Khi có golden dataset và RAG system đang chạy |
| Day 40 | Production RAG System (mini-project) | Capstone RAG — cần tích hợp toàn bộ Phase 5 |
| Day 41-47 | MLOps: MLflow, Model Serving, Docker/K8s GPU, Observability, Cost, Guardrails, Testing | Sau khi có model/app cần deploy |
| Day 48-50 | Capstone, UI, Portfolio | Giai đoạn cuối: hoàn thiện portfolio |

### Nhóm D — Đọc lướt / tra cứu khi cần

| Tài liệu | Chủ đề | Ghi chú |
|---|---|---:|
| `document.md` các ngày | Reference, deep dive | Tra cứu khi cần chi tiết |
| `ai_engineer_day_*_lessons.md` | Tổng hợp theo phase | Dùng để ôn tập nhanh từng phase |
| `generate-task.md` | Process generate | Tài liệu tham khảo cho người tạo nội dung |
| `review-and-fixed-checklist.md` | Review checklist | Dùng khi review lại khóa học |

## Cách học đề xuất

Mỗi ngày học 2 giờ theo khung:
- **10 phút**: Đọc TL;DR và mục tiêu
- **35 phút**: Học concept chính
- **45 phút**: Hands-on/code/design
- **20 phút**: Ghi chú trade-off, performance, production concern
- **10 phút**: Update learning log

### Giai đoạn 1 — Học để bắt đầu làm được (Day 00-08, ~16h)

Học theo thứ tự: Day 00 → 01 → 03 → 04 → 06 → 05 → 07 → 08

**Mục tiêu:** Train, evaluate và debug được ML model cơ bản. Build được pipeline dự đoán customer churn end-to-end.

### Giai đoạn 2 — Học để hiểu Deep Learning & LLM (Day 09-24, ~32h)

Học theo thứ tự: Day 09 → 10 → 11 → 12 → 13 → 14 → 15 → 17 → 18 → 19 → 20 → 21 → 22 → 23 → 24

**Mục tiêu:** Hiểu Transformer, fine-tune được model NLP nhỏ, build được LLM app có structured output + tool calling + memory.

### Giai đoạn 3 — Học để build Production RAG (Day 31-40, ~20h)

Học theo thứ tự: Day 31 → 33 → 32 → 34 → 36 → 37 → 35 → 38 → 39 → 40

**Mục tiêu:** Build được RAG system production-style với hybrid search, reranking, citation và evaluation.

### Giai đoạn 4 — Học để deploy & vận hành (Day 25-30, 41-50, ~32h)

Học fine-tuning + local LLM + MLOps theo nhu cầu thực tế. Hoàn thiện capstone project.

## Mini project — Vietnamese Enterprise Knowledge Assistant (Capstone)

**Mô tả:** Hệ thống hỏi đáp tài liệu doanh nghiệp tiếng Việt, có citation, permission, evaluation và monitoring.

**Stack:**
- FastAPI + Qdrant/pgvector + LLM (OpenAI/Claude/Ollama)
- Docker Compose, Prometheus + Grafana, Langfuse/LangSmith

**Kiến thức áp dụng:**
- RAG pipeline: ingestion → chunking → embedding → vector search → hybrid search → reranking → generation
- LLM app architecture: gateway, structured output, function calling, tool calling
- Agent patterns: ReAct, router agent
- Observability: latency, token usage, cost/request, retrieval quality
- Guardrails: output validation, PII redaction, prompt injection defense
- Evaluation: golden dataset, Recall@k, MRR, faithfulness, RAGAS

**Tiêu chí hoàn thành:**
- Upload/ingest tài liệu PDF/Markdown
- Hybrid search (dense + BM25) + RRF
- Reranking cải thiện Recall@5 ≥ 10%
- Citation theo source/page/section
- Log latency, token usage, cost mỗi request
- Evaluation report với golden dataset ≥ 30 câu
- Docker Compose deploy

## Checklist học nhanh

- [ ] Tôi đã hiểu sự khác nhau giữa rule-based, ML, DL, LLM và RAG
- [ ] Tôi đã phân tích được 5 bài toán thực tế và chọn đúng approach
- [ ] Tôi đã train được ML model với scikit-learn pipeline
- [ ] Tôi đã hiểu precision/recall/F1/ROC-AUC và chọn đúng metric cho business
- [ ] Tôi đã fine-tune được model NLP với HuggingFace Trainer
- [ ] Tôi đã build được LLM app với structured output + function calling
- [ ] Tôi đã thiết kế được LLM app architecture cho production
- [ ] Tôi đã build được RAG pipeline với hybrid search + reranking
- [ ] Tôi đã deploy được AI service với FastAPI + Docker
- [ ] Tôi đã thêm observability (token usage, latency, cost) vào LLM app
- [ ] Tôi đã viết guardrails chống prompt injection và output validation
- [ ] Tôi đã hoàn thành capstone project và có thể đưa vào portfolio

## Flashcard / câu hỏi ôn tập

1. Model khác function truyền thống ở điểm nào?
   - **Đáp án:** Model là probabilistic function học từ data, có version, latency, cost, SLA. Output không deterministic — cần evaluation trên dataset, không chỉ unit test.
   - **Liên quan:** Day 01

2. Khi nào dùng rule, ML, LLM hay RAG?
   - **Đáp án:** Rule: logic đơn giản, ổn định, cần explain. ML: prediction trên tabular data. LLM: language reasoning, generation. RAG: cần trả lời theo tài liệu riêng, cập nhật, có citation.
   - **Liên quan:** Day 01

3. Overfitting là gì và phát hiện thế nào?
   - **Đáp án:** Model học quá khớp noise trong training data → train score cao, validation score thấp hơn nhiều. Phát hiện: gap giữa train và validation metrics.
   - **Liên quan:** Day 03

4. Vì sao accuracy là metric nguy hiểm cho imbalanced dataset?
   - **Đáp án:** Với dataset 99% negative, model luôn predict negative → accuracy 99% nhưng recall = 0. Dùng precision/recall/F1 hoặc PR-AUC thay thế.
   - **Liên quan:** Day 06

5. Temperature trong LLM ảnh hưởng gì?
   - **Đáp án:** Temperature cao → output đa dạng, sáng tạo hơn nhưng dễ sai. Temperature thấp → output ổn định, deterministic hơn. T = 0: greedy decoding.
   - **Liên quan:** Day 17

6. Khi nào dùng function calling thay vì parse text output?
   - **Đáp án:** Khi cần structured data từ LLM (JSON), hoặc LLM cần gọi external API/tool. Function calling cho phép LLM chọn function và điền tham số chính xác.
   - **Liên quan:** Day 19

7. RAG khác fine-tuning ở điểm nào?
   - **Đáp án:** RAG: knowledge ở ngoài model (vector DB), cập nhật dễ, có citation. Fine-tuning: knowledge baked vào model weights, format/style ổn định hơn, cost inference thấp hơn model lớn.
   - **Liên quan:** Day 25, Day 31

8. Tại sao cần hybrid search (dense + sparse)?
   - **Đáp án:** Dense (embedding) tốt cho semantic similarity. Sparse (BM25) tốt cho keyword exact match. Hybrid kết hợp cả hai → cải thiện recall đáng kể, đặc biệt với query có keyword cụ thể.
   - **Liên quan:** Day 36

9. Reranker khác embedding model thế nào?
   - **Đáp án:** Embedding (bi-encoder): encode query và document riêng → tính similarity nhanh. Reranker (cross-encoder): nhận cặp (query, doc) cùng lúc → chính xác hơn nhưng chậm hơn. Dùng two-stage: retrieve 50-100 bằng embedding → rerank top 5-10.
   - **Liên quan:** Day 37

10. Prompt injection là gì và phòng tránh thế nào?
    - **Đáp án:** Attacker inject instruction để override system prompt hoặc leak data. Phòng tránh: input validation, role-based prompt isolation, output filtering, least privilege tool design, human-in-the-loop cho action nguy hiểm.
    - **Liên quan:** Day 23, Day 46

11. Recall@k và MRR khác nhau thế nào?
    - **Đáp án:** Recall@k: tỉ lệ relevant docs được retrieve trong top-k. MRR: vị trí trung bình của relevant doc đầu tiên. Recall@k quan trọng cho RAG (cần đủ context), MRR quan trọng cho search (cần relevant doc ở top).
    - **Liên quan:** Day 39

12. LoRA hoạt động thế nào?
    - **Đáp án:** Thay vì update toàn bộ weight, LoRA thêm low-rank matrices (A×B) vào attention layers, chỉ train A và B → giảm số lượng tham số trainable ~100-1000×, giảm VRAM cần.
    - **Liên quan:** Day 27

## Tài nguyên

- [README tổng quan khóa học](./README.md)
- [Lộ trình 50 ngày chi tiết](./lo_trinh_50_ngay_senior_se_to_ai_engineer.md)
- [Tổng hợp Day 01-08](./ai_engineer_day_01_08_lessons.md)
- [Tổng hợp Day 09-16](./ai_engineer_day_09_16_lessons.md)
- [Tổng hợp Day 17-24](./ai_engineer_day_17_24_lessons.md)
- [Tổng hợp Day 25-32](./ai_engineer_day_25_32_lessons.md)
- [Tổng hợp Day 33-40](./ai_engineer_day_33_40_lessons.md)
- [Tổng hợp Day 41-48](./ai_engineer_day_41_48_lessons.md)
- [Tổng hợp Day 49-50](./ai_engineer_day_49_50_lessons.md)
- [fast.ai Practical Deep Learning](https://course.fast.ai/)
- [HuggingFace Course](https://huggingface.co/learn/nlp-course)
- [Anthropic Engineering Blog](https://www.anthropic.com/engineering)
- [OpenAI Cookbook](https://cookbook.openai.com/)
- [Chip Huyen's Blog](https://huyenchip.com/blog/)
- [Lilian Weng's Blog](https://lilianweng.github.io/)
