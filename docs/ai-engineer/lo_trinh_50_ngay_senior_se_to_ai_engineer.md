# 🚀 Lộ Trình 50 Ngày: Senior SE → GenAI/RAG/LLM Production Engineer

> **Mục tiêu**: Giúp Senior Software Engineer xây dựng nền tảng AI/ML đủ vững, tập trung vào GenAI, RAG, LLM application engineering, local LLM, MLOps và production deployment.
>
> **Thời gian**: 50 ngày × 2 giờ/ngày = khoảng 100 giờ.
>
> **Đối tượng**: Senior software engineer đã mạnh về system design, microservices, databases, Docker/K8s, backend/API và muốn chuyển hướng sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus.

---

## 📌 Định vị thực tế

Sau 50 ngày, mục tiêu hợp lý không phải là trở thành AI Researcher hay Senior ML Scientist, mà là:

- Build được GenAI/RAG application production-style.
- Hiểu đủ ML/DL/Transformer để debug, evaluate và ra quyết định kỹ thuật.
- Thành thạo các pattern phổ biến trong LLM application engineering.
- Biết cách thiết kế, deploy, monitor và tối ưu chi phí hệ thống AI.
- Có ít nhất 1 capstone project đủ tốt để đưa vào portfolio, GitHub, CV và LinkedIn.

> Với background Senior SE, lợi thế cạnh tranh lớn nhất là khả năng đưa AI vào production, không chỉ chạy notebook.

---

## 🎯 Mục tiêu sau 50 ngày

Sau khi hoàn thành lộ trình, bạn nên có khả năng:

1. Hiểu ML foundation: training, evaluation, overfitting, bias-variance, data leakage.
2. Fine-tune được model NLP/LLM nhỏ ở mức thực hành.
3. Hiểu Transformer, tokenizer, embedding, attention và inference constraints.
4. Build được LLM application với prompt, structured output, function calling và agent workflow.
5. Build được RAG system có ingestion, chunking, embedding, vector search, hybrid search, reranking và citation.
6. Evaluate được RAG bằng retrieval metrics và generation metrics.
7. Deploy AI service bằng FastAPI, Docker, K8s hoặc Docker Compose.
8. Monitor được latency, token usage, cost/request, retrieval quality và user feedback.
9. Thiết kế guardrails chống prompt injection, data leakage và output sai format.
10. Hoàn thiện capstone project production-style.

---

## 🧭 Triết lý học tập

Bạn là Senior SE nên không học AI theo hướng academic-first. Hướng học nên là:

```text
Concept vừa đủ → Hands-on thực tế → Trade-off → Production decision → Portfolio output
```

Nguyên tắc mỗi ngày:

1. **TL;DR trước**: Hiểu ý chính trong vài phút.
2. **Map về SE concept**: So sánh AI concept với database, cache, queue, API, microservice, observability.
3. **Luôn có trade-off**: Không có best solution tuyệt đối.
4. **Có con số cụ thể**: Latency, memory, token cost, throughput, VRAM, storage.
5. **Production mindset**: Mỗi bài phải trả lời: dùng được trong production không?
6. **Hands-on mỗi ngày**: Ít nhất có code, experiment, checklist hoặc mini-design.
7. **Portfolio-first**: Những gì học nên tích lũy dần vào capstone.

---

## 🗺️ Tổng quan 7 phase

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---:|---|---|
| Phase 1 | Day 1-8 | ML Foundation | Customer Churn ML Pipeline |
| Phase 2 | Day 9-16 | Deep Learning, NLP, Transformer | Fine-tuned PhoBERT/BERT Classifier |
| Phase 3 | Day 17-24 | LLM Application Engineering | AI Assistant có tool calling + memory |
| Phase 4 | Day 25-30 | Fine-tuning & Local LLM | LoRA experiment + local model API |
| Phase 5 | Day 31-40 | Production RAG | Production RAG system |
| Phase 6 | Day 41-47 | MLOps & Production AI | Deployable AI service với monitoring |
| Phase 7 | Day 48-50 | Capstone & Portfolio | GitHub repo + README + demo + blog outline |

---

# PHASE 1: ML FOUNDATION — DAY 1-8

> **Mục tiêu phase**: Hiểu nền tảng ML đủ để đọc hiểu, train, evaluate và debug model cơ bản. Không học quá academic, tập trung vào tư duy production và evaluation.

---

## Day 1: AI Mindset cho Senior SE

### Mục tiêu

- Hiểu sự khác nhau giữa rule-based system, ML system, Deep Learning system và LLM system.
- Biết khi nào nên dùng ML, khi nào không nên dùng.
- Map các khái niệm AI về tư duy SE.

### Nội dung chính

- Rule-based vs ML vs DL vs LLM.
- Model như một function học từ data.
- Hyperparameter như config.
- Training như build process.
- Evaluation như test suite nhưng có xác suất.
- Inference như runtime API.
- Failure mode của AI system khác gì backend service truyền thống.

### Hands-on

Phân tích 5 bài toán thực tế:

1. Fraud detection.
2. Customer churn prediction.
3. Chatbot CSKH.
4. Search tài liệu nội bộ.
5. Recommendation sản phẩm.

Với mỗi bài toán, quyết định:

- Dùng rule, ML, RAG hay LLM?
- Vì sao?
- Risk production là gì?

---

## Day 2: Math đủ dùng cho ML

### Mục tiêu

- Hiểu vector, matrix, dot product, gradient, probability ở mức dùng được.
- Không cần prove theorem, nhưng cần hiểu để debug model.

### Nội dung chính

- Vector, matrix, tensor.
- Dot product và cosine similarity.
- Matrix multiplication.
- Derivative, partial derivative, gradient.
- Chain rule.
- Probability distribution.
- Expected value.
- Entropy.
- Bayes theorem ở mức trực giác.

### Hands-on

- Implement dot product bằng Python thuần.
- Implement cosine similarity.
- Implement gradient descent cho `f(x) = x^2`.
- Dùng NumPy để nhân matrix và tính similarity.

---

## Day 3: ML Fundamentals

### Mục tiêu

- Hiểu supervised, unsupervised và reinforcement learning.
- Hiểu train/validation/test split.
- Hiểu overfitting, underfitting, bias-variance.

### Nội dung chính

- Supervised learning.
- Unsupervised learning.
- Regression vs classification.
- Train/validation/test.
- Cross-validation.
- Bias-variance trade-off.
- Overfitting và regularization.
- Baseline-first mindset.

### Algorithms cần biết

- Linear Regression.
- Logistic Regression.
- Decision Tree.
- Random Forest.
- XGBoost.
- SVM.
- KNN.

### Trade-off

| Model | Khi nên dùng | Khi không nên dùng |
|---|---|---|
| Logistic Regression | Baseline, explainable | Quan hệ phi tuyến phức tạp |
| Random Forest | Tabular data, ít tuning | Dataset rất lớn, cần latency thấp |
| XGBoost | Tabular data mạnh | Text/image/raw unstructured data |
| Neural Network | Data lớn, pattern phức tạp | Data ít, cần explainability cao |
| LLM | Language reasoning, generation | Bài toán đơn giản có rule rõ ràng |

---

## Day 4: Python ML Stack

### Mục tiêu

- Dùng được NumPy, Pandas, scikit-learn cho ML pipeline cơ bản.
- Hiểu workflow notebook nhưng không lệ thuộc notebook.

### Nội dung chính

- NumPy ndarray, broadcasting, vectorization.
- Pandas DataFrame, groupby, merge, missing value.
- scikit-learn estimator API.
- Pipeline và transformer.
- Train/test split.
- Matplotlib cho visualization cơ bản.
- Jupyter workflow.

### Hands-on

Dataset Titanic:

- Load data.
- EDA.
- Clean missing value.
- Train Logistic Regression, Random Forest, XGBoost.
- So sánh metrics.

---

## Day 5: Feature Engineering

### Mục tiêu

- Biết xử lý numerical, categorical, text và datetime features.
- Hiểu vì sao feature quality ảnh hưởng mạnh đến model quality.

### Nội dung chính

- Numerical scaling: StandardScaler, MinMaxScaler, RobustScaler.
- Binning, log transform.
- One-hot encoding.
- Label encoding.
- Target encoding.
- TF-IDF cho text.
- Datetime features.
- Missing data imputation.
- Feature selection.

### Hands-on

Tạo scikit-learn pipeline gồm:

- Numerical preprocessing.
- Categorical preprocessing.
- Model training.
- Evaluation.

---

## Day 6: Model Evaluation Metrics

### Mục tiêu

- Không bị bẫy bởi accuracy.
- Chọn metric đúng với business problem.

### Nội dung chính

- Accuracy.
- Precision.
- Recall.
- F1-score.
- ROC-AUC.
- PR-AUC.
- Confusion matrix.
- MAE, MSE, RMSE, MAPE.
- Ranking metrics: MRR, NDCG, Recall@k.
- Business metric vs ML metric.

### Case study

Fraud detection:

- Khi nào ưu tiên precision?
- Khi nào ưu tiên recall?
- False positive và false negative ảnh hưởng business thế nào?

---

## Day 7: Error Analysis, Data Leakage, Threshold Tuning

### Mục tiêu

- Biết model sai ở đâu.
- Biết phát hiện data leakage.
- Biết tune threshold theo business objective.

### Nội dung chính

- Error slicing theo segment.
- Confusion matrix analysis.
- Threshold tuning.
- Calibration.
- Data leakage.
- Train-serving skew.
- Distribution shift.
- Baseline regression test.

### Hands-on

Với model classification:

- Vẽ confusion matrix.
- Tune threshold từ 0.3 đến 0.8.
- So sánh precision/recall/F1.
- Tìm top 20 false positives và false negatives.

---

## Day 8: Mini-project — Customer Churn ML Pipeline

### Deliverable

Build pipeline dự đoán customer churn.

### Yêu cầu

- Dataset: Telco Customer Churn hoặc dataset tương đương.
- EDA.
- Feature engineering.
- Train ít nhất 3 models.
- Evaluation bằng nhiều metrics.
- Error analysis.
- Save model.
- Viết inference function.
- README giải thích trade-off.

### Output

- Notebook hoặc Python package.
- `README.md`.
- `requirements.txt` hoặc `pyproject.toml`.
- Model artifact.

---

# PHASE 2: DEEP LEARNING, NLP, TRANSFORMER — DAY 9-16

> **Mục tiêu phase**: Hiểu Neural Network, PyTorch, tokenizer, attention và Transformer. Fine-tune được một model NLP nhỏ.

---

## Day 9: Neural Network từ Zero

### Nội dung chính

- Neuron = weighted sum + activation.
- Activation functions: Sigmoid, Tanh, ReLU, GELU.
- Forward pass.
- Loss function.
- Backpropagation.
- Gradient descent.

### Hands-on

- Implement MLP 2-layer bằng NumPy.
- Train trên XOR dataset.
- Visualize loss giảm theo epoch.

---

## Day 10: PyTorch Fundamentals

### Nội dung chính

- Tensor.
- Autograd.
- `nn.Module`.
- `forward()`.
- `Dataset` và `DataLoader`.
- CPU/GPU device management.

### Hands-on

- Rebuild MLP từ Day 9 bằng PyTorch.
- So sánh code NumPy vs PyTorch.

---

## Day 11: Training Loop, Optimizer, Scheduler

### Nội dung chính

- Training loop anatomy.
- Forward → loss → backward → optimizer step → zero grad.
- SGD, Adam, AdamW.
- Learning rate scheduler.
- Dropout.
- Weight decay.
- Gradient clipping.
- Mixed precision overview.

### Hands-on

- Train classifier đơn giản với PyTorch.
- Thêm early stopping.
- Log loss và metrics.

---

## Day 12: NLP Fundamentals & Tokenizer

### Nội dung chính

- Text preprocessing.
- Tokenization.
- BPE.
- WordPiece.
- SentencePiece.
- Vocabulary.
- OOV token.
- Token limit.
- Token cost.
- Tiếng Việt bị tokenize như thế nào.

### Hands-on

- So sánh tokenizer của BERT, GPT-style model và PhoBERT.
- Tính số token cho một số đoạn tiếng Việt.
- Ước lượng cost dựa trên token count.

---

## Day 13: Attention Mechanism

### Nội dung chính

- Query, Key, Value.
- Scaled dot-product attention.
- Self-attention.
- Causal mask.
- Multi-head attention.
- Vì sao attention parallel tốt hơn RNN.

### Hands-on

- Implement self-attention bằng PyTorch khoảng 30-50 dòng.
- Visualize attention weights đơn giản.

---

## Day 14: Transformer Architecture

### Nội dung chính

- Encoder.
- Decoder.
- Encoder-only model: BERT.
- Decoder-only model: GPT, LLaMA, Qwen.
- Encoder-decoder model: T5.
- Positional encoding.
- RoPE.
- LayerNorm.
- Feed-forward network.
- Residual connection.

### Tài liệu nên đọc

- The Illustrated Transformer.
- The Annotated Transformer.
- Attention Is All You Need.

---

## Day 15: HuggingFace Ecosystem

### Nội dung chính

- `transformers`.
- `datasets`.
- `tokenizers`.
- `accelerate`.
- Model Hub.
- Model card.
- AutoTokenizer.
- AutoModel.
- Pipeline.
- Trainer API.

### Hands-on

- Load model từ HuggingFace.
- Tokenize text.
- Chạy inference.
- Đọc model card và xác định license, intended use, limitation.

---

## Day 16: Mini-project — Fine-tune PhoBERT/BERT Classifier

### Deliverable

Fine-tune model sentiment classification tiếng Việt.

### Yêu cầu

- Dataset: Shopee review, VLSP sentiment hoặc dataset tương đương.
- Baseline: TF-IDF + Logistic Regression.
- Fine-tune PhoBERT/BERT.
- Compare baseline vs Transformer.
- Confusion matrix.
- Error analysis.
- Export inference API đơn giản với FastAPI.

### Output

- GitHub repo.
- README.
- Training script.
- Inference API.

---

# PHASE 3: LLM APPLICATION ENGINEERING — DAY 17-24

> **Mục tiêu phase**: Build LLM application theo hướng production, không chỉ prompt thủ công.

---

## Day 17: LLM Fundamentals

### Nội dung chính

- Pre-training.
- Supervised fine-tuning.
- RLHF overview.
- Context window.
- Token limit.
- Temperature.
- Top-p.
- Top-k.
- Greedy decoding.
- Model families: GPT, Claude, Gemini, LLaMA, Qwen, DeepSeek.
- Open-source vs closed-source model.

### Hands-on

- Gọi API LLM hoặc chạy model nhỏ local qua Ollama.
- Thử thay đổi temperature/top-p và quan sát output.

---

## Day 18: Prompt Engineering thực chiến

### Nội dung chính

- Zero-shot.
- Few-shot.
- Chain-of-Thought.
- Role prompting.
- Constraint prompting.
- Prompt template.
- Prompt versioning.
- Prompt A/B testing.
- Prompt injection overview.

### Hands-on

Tạo prompt library cho 5 use case:

1. Summarization.
2. Classification.
3. Data extraction.
4. Code review.
5. Customer support.

---

## Day 19: Structured Output & Function Calling

### Nội dung chính

- JSON output.
- JSON Schema.
- Function calling.
- Tool calling.
- Output parser.
- Validation.
- Retry khi output sai schema.
- Idempotency khi gọi tool.

### Hands-on

Build LLM service nhận natural language và trả về JSON hợp lệ cho một task cụ thể.

Ví dụ:

- Extract invoice data.
- Extract ticket category.
- Generate SQL query safely.

---

## Day 20: LLM App Architecture cho Production

### Nội dung chính

- LLM gateway.
- Model router.
- Fallback model.
- Retry strategy.
- Timeout.
- Rate limiting.
- Request queue.
- Prompt cache.
- Semantic cache.
- Audit log.
- Tenant isolation.
- Secret management.

### Architecture mẫu

```text
Client
  → API Gateway
  → LLM Orchestrator
  → Prompt Registry
  → Model Router
  → LLM Provider / Local LLM
  → Tool Services
  → Observability Stack
```

---

## Day 21: Raw SDK vs LangChain vs LlamaIndex vs LangGraph

### Nội dung chính

| Công cụ | Khi nên dùng | Khi không nên dùng |
|---|---|---|
| Raw SDK | App đơn giản, cần kiểm soát cao | Workflow nhiều bước, nhiều tools |
| LangChain | Chain/tool/RAG nhanh | Cần tối ưu rất sâu, tránh abstraction |
| LlamaIndex | Document-heavy RAG | Agent workflow phức tạp |
| LangGraph | Agent có state machine | Simple chatbot |
| DSPy | Tối ưu prompt/programmatic pipeline | Team chưa quen evaluation-driven workflow |

### Hands-on

Implement cùng một flow bằng:

- Raw SDK.
- LangChain LCEL.

So sánh độ phức tạp và khả năng control.

---

## Day 22: Agent Patterns với LangGraph

### Nội dung chính

- Agent là gì.
- ReAct pattern.
- Planner-executor.
- Router agent.
- Supervisor agent.
- Human-in-the-loop.
- State machine.
- Agent failure modes.
- Infinite loop prevention.

### Hands-on

Build agent có thể:

- Nhận câu hỏi.
- Quyết định có cần gọi tool không.
- Gọi tool.
- Tổng hợp câu trả lời.
- Log trace.

---

## Day 23: Security Basics cho LLM App

### Nội dung chính

- Prompt injection.
- Indirect prompt injection.
- Jailbreak.
- Tool abuse.
- Data exfiltration.
- Sensitive data leakage.
- Output validation.
- Least privilege tool design.
- Sandbox execution.

### Hands-on

Thiết kế threat model cho chatbot có tool gọi database.

---

## Day 24: Mini-project — AI Assistant có Tool Calling + Memory

### Deliverable

Build một AI assistant nhỏ nhưng production-style.

### Yêu cầu

- Có API backend.
- Có prompt template.
- Có structured output.
- Có ít nhất 2 tools.
- Có memory đơn giản.
- Có logging.
- Có retry khi output sai schema.
- Có README giải thích architecture.

---

# PHASE 4: FINE-TUNING & LOCAL LLM — DAY 25-30

> **Mục tiêu phase**: Biết khi nào fine-tune, chuẩn bị dataset, chạy LoRA/QLoRA ở mức thực hành và deploy local model.

---

## Day 25: Khi nào Fine-tune, khi nào dùng RAG

### Nội dung chính

| Nhu cầu | Nên dùng |
|---|---|
| Knowledge thay đổi thường xuyên | RAG |
| Cần trả lời theo tài liệu nội bộ | RAG |
| Cần output format rất ổn định | Fine-tuning |
| Cần style/tone/domain behavior riêng | Fine-tuning |
| Cần model biết thông tin mới realtime | Không fine-tune, dùng RAG/tool |
| Cần giảm cost inference | Fine-tune/distill model nhỏ |

### Nội dung bổ sung

- Full fine-tuning.
- PEFT.
- LoRA.
- QLoRA.
- Adapter.
- Prompt tuning.
- RAG + fine-tuning hybrid.

---

## Day 26: Dataset Preparation cho Instruction Tuning

### Nội dung chính

- Instruction format.
- Alpaca format.
- ShareGPT format.
- ChatML format.
- Data cleaning.
- Deduplication.
- Train/validation split.
- Quality > quantity.
- Synthetic data generation.
- Data privacy.

### Hands-on

Tạo dataset 500 examples cho một domain:

- Customer support.
- Code review.
- Technical writing.
- Internal policy Q&A.

---

## Day 27: LoRA/QLoRA Hands-on

### Nội dung chính

- PEFT library.
- bitsandbytes.
- 4-bit quantization.
- LoRA rank `r`.
- LoRA alpha.
- Target modules.
- Dropout.
- Merge LoRA weights.

### Hands-on

Fine-tune model nhỏ như Qwen/LLaMA-compatible model trên Colab hoặc local GPU.

---

## Day 28: Evaluation trước/sau Fine-tune

### Nội dung chính

- Golden dataset.
- Exact match.
- Format accuracy.
- Human evaluation.
- LLM-as-a-judge.
- Regression set.
- Overfitting detection.
- Before/after comparison.

### Hands-on

Tạo evaluation script để so sánh base model và fine-tuned model.

---

## Day 29: Local LLM — Ollama, llama.cpp, vLLM

### Nội dung chính

- Vì sao dùng local LLM.
- Privacy.
- Cost.
- Latency.
- Offline use case.
- Ollama.
- llama.cpp.
- vLLM.
- TGI.
- LM Studio.
- Model serving API.

### Trade-off

| Runtime | Mạnh ở đâu | Hạn chế |
|---|---|---|
| Ollama | Dễ dùng local/dev | Không tối ưu production throughput cao |
| llama.cpp | CPU/GGUF tốt | Serving scale lớn cần tự thiết kế thêm |
| vLLM | Throughput cao, production serving | Cần GPU, setup phức tạp hơn |
| TGI | HuggingFace ecosystem | Ops phức tạp hơn Ollama |

---

## Day 30: Quantization & Deploy Local Model API

### Nội dung chính

- FP32, FP16, BF16.
- INT8, INT4.
- GGUF.
- AWQ.
- GPTQ.
- KV cache.
- VRAM estimation.
- Throughput vs quality trade-off.

### Hands-on

- Chạy model local.
- Expose qua FastAPI.
- Benchmark latency.
- Ghi lại memory usage.

---

# PHASE 5: PRODUCTION RAG — DAY 31-40

> **Mục tiêu phase**: Build RAG system production-style, có retrieval tốt, evaluation rõ ràng, citation, monitoring và khả năng mở rộng.

---

## Day 31: RAG Architecture

### Nội dung chính

- RAG = Retrieval + Generation.
- Indexing pipeline.
- Query pipeline.
- Document loader.
- Chunker.
- Embedding model.
- Vector DB.
- Retriever.
- Reranker.
- Generator.
- Citation.
- Feedback loop.

### Architecture mẫu

```text
Documents
  → Parser
  → Chunker
  → Metadata Enricher
  → Embedding Model
  → Vector DB

User Query
  → Query Rewriter
  → Retriever
  → Reranker
  → Context Builder
  → LLM
  → Answer + Citation
```

---

## Day 32: Embedding Models & Benchmark cho tiếng Việt

### Nội dung chính

- Embedding là gì.
- Dense vector.
- Cosine similarity.
- Sentence embedding.
- Multilingual embedding.
- OpenAI embedding.
- BGE.
- E5.
- Cohere embedding.
- Vietnamese retrieval concerns.
- Dimension vs cost vs latency.

### Hands-on

So sánh 3 embedding models trên 20 câu hỏi tiếng Việt.

---

## Day 33: Vector DB

### Nội dung chính

- ANN search.
- HNSW.
- IVF.
- PQ.
- Qdrant.
- Milvus.
- Weaviate.
- Pinecone.
- pgvector.
- Chroma.
- Metadata filtering.
- Multi-tenancy.
- Sharding.
- Replication.

### Trade-off

| Vector DB | Khi nên dùng |
|---|---|
| pgvector | Team đã dùng Postgres, scale vừa |
| Qdrant | Self-host tốt, API rõ, production-friendly |
| Milvus | Scale lớn, vector workload nặng |
| Pinecone | Managed, giảm ops |
| Chroma | Dev/local prototype |

---

## Day 34: Chunking Strategies

### Nội dung chính

- Fixed-size chunking.
- Recursive chunking.
- Semantic chunking.
- Markdown-aware chunking.
- PDF chunking.
- Code chunking.
- Parent-child chunking.
- Chunk overlap.
- Chunk metadata.
- Chunk size trade-off.

### Hands-on

Test 3 chunking strategies trên cùng một document và so sánh retrieval result.

---

## Day 35: Metadata, Citation, Permission-aware RAG

### Nội dung chính

- Source metadata.
- Page number.
- Section heading.
- Document version.
- Tenant ID.
- ACL.
- User permission.
- Citation rendering.
- Audit log.
- Data deletion.

### Hands-on

Thiết kế schema metadata cho enterprise RAG.

Ví dụ:

```json
{
  "doc_id": "policy_001",
  "tenant_id": "company_a",
  "source": "hr_policy.pdf",
  "page": 12,
  "section": "Leave Policy",
  "version": "2026-01",
  "allowed_roles": ["hr", "manager"]
}
```

---

## Day 36: Hybrid Search — Dense + Sparse + BM25

### Nội dung chính

- Dense retrieval.
- Sparse retrieval.
- BM25.
- SPLADE overview.
- Hybrid search.
- Reciprocal Rank Fusion.
- Query normalization.
- Keyword-heavy query vs semantic query.

### Hands-on

Build retrieval pipeline:

- BM25 top-k.
- Vector search top-k.
- Merge bằng RRF.

---

## Day 37: Reranking

### Nội dung chính

- Bi-encoder vs cross-encoder.
- Reranker là gì.
- BGE reranker.
- Cohere Rerank.
- Two-stage retrieval.
- Retrieve top 50/100 → rerank top 5/10.
- Latency trade-off.

### Hands-on

Thêm reranker vào pipeline Day 36 và đo cải thiện Recall@k / MRR.

---

## Day 38: Advanced RAG Patterns

### Nội dung chính

- Query rewriting.
- Multi-query retrieval.
- HyDE.
- Step-back prompting.
- Query decomposition.
- Multi-hop RAG.
- Contextual retrieval.
- Agentic RAG.
- Corrective RAG.
- GraphRAG overview.

### Guidance

Không cần implement tất cả. Ưu tiên:

1. Query rewriting.
2. Hybrid search.
3. Reranking.
4. Contextual retrieval.

---

## Day 39: RAG Evaluation

### Nội dung chính

- Golden dataset.
- Recall@k.
- Precision@k.
- MRR.
- NDCG.
- Context precision.
- Context recall.
- Faithfulness.
- Answer relevance.
- Hallucination detection.
- RAGAS.
- TruLens.
- LangSmith eval.

### Hands-on

Tạo 30-50 câu hỏi golden set cho tài liệu của bạn.

Mỗi câu gồm:

- Question.
- Expected answer.
- Expected source chunk.
- Difficulty.
- Tags.

---

## Day 40: Mini-project — Production RAG System

### Deliverable

Build RAG system hoàn chỉnh.

### Yêu cầu

- Upload hoặc ingest document.
- Parse document.
- Chunk document.
- Embed chunks.
- Store vào vector DB.
- Query pipeline.
- Hybrid search.
- Rerank.
- Generate answer.
- Citation.
- Log latency/token/cost.
- Evaluation report.

### Output

- Backend API.
- Simple UI.
- Docker Compose.
- README.
- Evaluation result.

---

# PHASE 6: MLOPS & PRODUCTION AI — DAY 41-47

> **Mục tiêu phase**: Đưa AI system vào production với serving, monitoring, testing, cost optimization và guardrails.

---

## Day 41: MLflow, Experiment Tracking, Model Registry

### Nội dung chính

- Experiment tracking.
- Params.
- Metrics.
- Artifacts.
- Model registry.
- Model versioning.
- Reproducibility.
- MLflow vs W&B vs Neptune.

### Hands-on

- Track training từ Day 16 hoặc Day 27 bằng MLflow.
- Log params, metrics và artifact.

---

## Day 42: Model Serving

### Nội dung chính

- FastAPI.
- BentoML.
- TorchServe overview.
- Triton Inference Server overview.
- vLLM serving.
- TGI.
- Streaming response.
- SSE.
- Request batching.
- Rate limiting.
- Timeout.

### Hands-on

Expose một model hoặc RAG pipeline qua FastAPI với streaming response.

---

## Day 43: Docker/K8s/GPU Serving cho AI Workload

### Nội dung chính

- Docker image cho ML.
- NVIDIA base image.
- nvidia-container-toolkit.
- GPU scheduling.
- K8s node selector.
- Taints/tolerations.
- nvidia-device-plugin.
- Helm chart cơ bản.
- KServe overview.
- Ray Serve overview.

### Hands-on

- Dockerize RAG app.
- Viết Docker Compose.
- Optional: viết K8s manifests.

---

## Day 44: Observability cho LLM App

### Nội dung chính

- Latency.
- Throughput.
- Error rate.
- Token usage.
- Cost/request.
- Time to first token.
- Retrieval latency.
- Rerank latency.
- Model latency.
- Prompt trace.
- User feedback.
- Langfuse.
- LangSmith.
- OpenTelemetry.
- Prometheus/Grafana.
- ELK/OpenSearch.

### Hands-on

Add logging/tracing cho RAG pipeline:

- Query.
- Retrieved chunks.
- Reranked chunks.
- Token usage.
- Final answer.
- User feedback.

---

## Day 45: Cost Optimization

### Nội dung chính

- Prompt caching.
- Semantic caching.
- Redis cache.
- Model routing.
- Small model vs large model.
- Batch API.
- Context compression.
- Chunk pruning.
- Distillation overview.
- Token budget.

### Hands-on

Thiết kế cost plan cho app RAG:

- Estimate request/day.
- Average input/output tokens.
- Cost/request.
- Monthly cost.
- 3 cách giảm cost.

---

## Day 46: Guardrails

### Nội dung chính

- Output validation.
- JSON schema validation.
- PII detection.
- PII redaction.
- Prompt injection defense.
- Jailbreak defense.
- LlamaGuard overview.
- NeMo Guardrails overview.
- Guardrails AI.
- Policy layer.
- Human escalation.

### Hands-on

Thêm guardrail cho RAG app:

- Không trả lời ngoài tài liệu.
- Từ chối câu hỏi nhạy cảm.
- Validate JSON output.
- Redact PII trong log.

---

## Day 47: LLM Testing, Golden Set, CI/CD cho Prompt/RAG

### Nội dung chính

- Golden dataset.
- Prompt regression test.
- Retrieval regression test.
- Snapshot testing.
- Evaluation CI.
- Threshold-based deployment.
- Canary release.
- A/B testing.
- Feedback loop.

### Hands-on

Tạo test suite cho RAG:

- 30 câu hỏi golden set.
- Check retrieved source.
- Check faithfulness.
- Check answer format.
- Fail CI nếu score thấp hơn threshold.

---

# PHASE 7: CAPSTONE & PORTFOLIO — DAY 48-50

> **Mục tiêu phase**: Hoàn thiện project chính để đưa vào portfolio, GitHub, CV và phỏng vấn.

---

## Capstone đề xuất: Vietnamese Enterprise Knowledge Assistant

### Mô tả

Một hệ thống hỏi đáp tài liệu doanh nghiệp tiếng Việt, có citation, permission, evaluation và monitoring.

### Tính năng chính

- Upload tài liệu PDF/Markdown/Text.
- Parse document.
- Chunk theo structure.
- Embedding tiếng Việt/multilingual.
- Vector DB: Qdrant hoặc pgvector.
- Hybrid search.
- Reranking.
- Chat UI.
- Citation theo source/page/section.
- Permission-aware retrieval.
- Function calling cho metadata lookup.
- Evaluation bằng golden dataset.
- Monitoring token/cost/latency.
- Docker Compose deploy.

### Architecture đề xuất

```text
Frontend
  → Backend API
  → Auth/Tenant Context
  → RAG Orchestrator
      → Query Rewriter
      → BM25 Retriever
      → Vector Retriever
      → RRF Merger
      → Reranker
      → Context Builder
      → LLM Gateway
  → Observability
  → Feedback Store
```

---

## Day 48: Capstone Architecture Review + Backend/API

### Việc cần làm

- Chốt scope capstone.
- Vẽ architecture.
- Chuẩn hóa repo structure.
- Hoàn thiện backend API.
- Hoàn thiện ingestion pipeline.
- Hoàn thiện query pipeline.

### Checklist

- [ ] Có architecture diagram.
- [ ] Có API docs.
- [ ] Có ingestion endpoint.
- [ ] Có chat endpoint.
- [ ] Có source citation.
- [ ] Có config file.

---

## Day 49: UI, Monitoring, Evaluation Report

### Việc cần làm

- Hoàn thiện UI đơn giản.
- Hiển thị answer + citation.
- Log token/cost/latency.
- Chạy golden evaluation.
- Viết evaluation report.

### Checklist

- [ ] UI chat chạy được.
- [ ] Hiển thị citations.
- [ ] Có feedback thumbs up/down.
- [ ] Có log traces.
- [ ] Có evaluation dataset.
- [ ] Có bảng metrics.

---

## Day 50: README, Demo, Blog, CV/LinkedIn

### Việc cần làm

- Viết README chuyên nghiệp.
- Viết demo video script.
- Viết blog outline.
- Chuẩn bị CV bullet points.
- Chuẩn bị LinkedIn post.

### README nên có

- Problem statement.
- Architecture.
- Tech stack.
- Features.
- RAG pipeline.
- Evaluation result.
- Security considerations.
- Cost considerations.
- How to run locally.
- Future improvements.

### CV bullet points mẫu

- Built a production-style Vietnamese Enterprise RAG Assistant using FastAPI, Qdrant/pgvector, hybrid search, reranking, citation and LLM observability.
- Designed an evaluation pipeline with golden dataset, Recall@k, MRR, faithfulness and answer relevance metrics.
- Implemented LLM cost optimization using prompt caching, token budgeting and model routing strategy.
- Added guardrails for prompt injection defense, output validation and PII-safe logging.

---

# 🧰 Setup môi trường

## Hardware tối thiểu

| Mức | Cấu hình | Ghi chú |
|---|---|---|
| Tối thiểu | 16GB RAM, no GPU | Dùng Colab/Kaggle cho GPU work |
| Tốt | 32GB RAM, GPU 8GB VRAM | Chạy được model nhỏ, fine-tune nhẹ |
| Rất tốt | 64GB RAM, RTX 4090 24GB | Local LLM/fine-tune tốt hơn |
| Alternative | MacBook M-series 32GB+ | Tốt cho dev/local inference bằng MLX/Ollama |

## Cloud options

- Google Colab.
- Kaggle Notebook.
- Colab Pro.
- RunPod.
- Vast.ai.
- Lambda Labs.
- AWS/GCP/Azure nếu cần enterprise setup.

## Python stack

```bash
python 3.11
uv
pytorch
transformers
datasets
peft
bitsandbytes
accelerate
scikit-learn
pandas
numpy
fastapi
uvicorn
mlflow
qdrant-client
langchain
langgraph
llama-index
ragas
langfuse
pytest
ruff
```

## Suggested repo structure cho capstone

```text
enterprise-rag-assistant/
  apps/
    api/
    web/
  packages/
    rag/
    llm/
    eval/
    observability/
  data/
    raw/
    processed/
    eval/
  scripts/
    ingest.py
    evaluate.py
    benchmark.py
  docker-compose.yml
  README.md
  pyproject.toml
```

---

# 📚 Resources nên học

## Courses

- fast.ai Practical Deep Learning.
- HuggingFace Course.
- DeepLearning.AI Machine Learning Specialization.
- DeepLearning.AI Generative AI courses.

## Blogs

- Chip Huyen.
- Lilian Weng.
- Jay Alammar.
- Sebastian Raschka.
- Anthropic Engineering Blog.
- OpenAI Cookbook.
- HuggingFace Blog.

## Papers / References

- Attention Is All You Need.
- Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.
- LoRA: Low-Rank Adaptation of Large Language Models.
- QLoRA.
- ReAct.
- Self-RAG.
- RAGAS.

---

# 🧪 Prompt Template để generate bài học từng ngày

Copy prompt này vào ChatGPT/Claude/Cursor để generate chi tiết từng ngày.

```markdown
Tôi đang học theo lộ trình "50 ngày từ Senior SE sang GenAI/RAG/LLM Production Engineer".

Context về tôi:
- Senior software engineer, 5+ năm kinh nghiệm
- Thành thạo: TypeScript, Python, Go, Java, PHP
- Mạnh về: system design, microservices, database, Kafka, Redis, Docker/K8s
- Cần bổ sung: AI/ML foundation, GenAI, RAG, Local LLM, MLOps
- Target: AI Engineer / GenAI Engineer / Backend Engineer with AI focus
- Mỗi ngày học 2 giờ

Hôm nay là Day <DAY_NUMBER>: <TOPIC>

Hãy viết bài học chi tiết theo format sau, bằng tiếng Việt, chỉ giữ nguyên thuật ngữ English cần thiết:

# Day <DAY_NUMBER>: <TOPIC>

## 🎯 Mục tiêu
[3-5 mục tiêu cụ thể, đo được]

## 📚 TL;DR
[Tóm tắt trong 3-4 câu]

## 1. [Main concept 1]
[Giải thích từ cơ bản đến chi tiết. Luôn map concept AI về concept SE như database, cache, queue, API, microservice, observability]

## 2. [Main concept 2]
...

## ⚖️ Trade-offs
[Bảng so sánh các lựa chọn. Không được nói chung chung "tùy trường hợp". Phải có guidance cụ thể]

## 🏭 Best practices từ industry
[3-5 practice thực tế, có reasoning]

## ⚡ Performance considerations
[Latency, memory, throughput, token cost, VRAM hoặc storage cụ thể nếu liên quan]

## 🔐 Production concerns
[Security, reliability, monitoring, data quality, rollback, versioning nếu liên quan]

## 🌍 Ứng dụng thực tế
[2-3 use case thực tế, connect với role AI Engineer / GenAI Engineer]

## 🛠️ Hands-on trong 60-90 phút
[Code example hoặc exercise cụ thể, có thể chạy được]

## 📝 Tự kiểm tra
[5 câu hỏi kiểm tra hiểu bài]

## ✅ Checklist hoàn thành hôm nay
[Checklist cụ thể]

## 🔗 Tài liệu tham khảo
[Link hoặc keyword để tự tìm]

Yêu cầu bổ sung:
1. Giải thích dễ hiểu, đi từ cơ bản đến chi tiết.
2. Ưu tiên thực hành và ứng dụng thực tế.
3. Luôn nhấn mạnh trade-off, best solution theo context và performance.
4. Code example phải gần production, không chỉ toy example.
5. Mỗi bài phải trả lời câu hỏi: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"
```

---

# ✅ Cách học mỗi ngày trong 2 giờ

## Khung thời gian đề xuất

| Thời lượng | Việc làm |
|---:|---|
| 10 phút | Đọc TL;DR và mục tiêu |
| 35 phút | Học concept chính |
| 45 phút | Hands-on/code/design |
| 20 phút | Ghi chú trade-off/performance |
| 10 phút | Update README hoặc learning log |

## Learning log mỗi ngày

Tạo file `learning-log.md` và ghi:

```markdown
# Day X: Topic

## Tôi đã học gì?

## Concept quan trọng nhất?

## Trade-off cần nhớ?

## Production concern?

## Code/project output hôm nay?

## Câu hỏi còn chưa rõ?
```

---

# 🧩 Optional topics sau 50 ngày

Sau khi hoàn thành plan, có thể học tiếp:

- Distributed training.
- DeepSpeed.
- Megatron-LM.
- Triton kernels.
- CUDA basics.
- Multimodal LLM.
- Speech AI với Whisper/TTS.
- GraphRAG chuyên sâu.
- Model distillation.
- Fine-tune embedding model.
- Evaluation platform nội bộ.

---

# 🎯 Kết luận

Lộ trình 50 ngày này tối ưu cho Senior SE muốn chuyển sang hướng AI application engineering. Trọng tâm không phải research, mà là:

```text
AI foundation đủ dùng
→ LLM application engineering
→ RAG production
→ MLOps/observability
→ Capstone portfolio
```

Nếu hoàn thành nghiêm túc, bạn sẽ có nền tảng tốt để apply các vị trí:

- AI Engineer.
- GenAI Engineer.
- LLM Engineer thiên về application.
- Backend Engineer with AI focus.
- Solution Architect cho AI-enabled system.

Điểm mạnh cạnh tranh của bạn là: **biết đưa AI vào hệ thống thật, có API, database, queue, cache, monitoring, deployment, security và cost optimization**.
