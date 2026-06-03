# 8 Bai Hoc Tiep Theo Cho AI Engineer

Nguon: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, Phase 4 - Fine-tuning & Local LLM va dau Phase 5 - Production RAG.

Doi tuong: Senior Software Engineer muon chuyen sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus.

Khung hoc moi ngay: 2 gio.

## Muc Luc

| Ngay | Chu de | Output chinh |
|---:|---|---|
| Day 25 | Khi nao Fine-tune, khi nao dung RAG | Decision record: prompt/RAG/tool/fine-tune/hybrid |
| Day 26 | Dataset Preparation cho Instruction Tuning | Dataset 500 examples + dataset card |
| Day 27 | LoRA/QLoRA Hands-on | LoRA adapter artifact cho model nho |
| Day 28 | Evaluation truoc/sau Fine-tune | Before/after evaluation report |
| Day 29 | Local LLM - Ollama, llama.cpp, vLLM | Local LLM decision note + latency probe |
| Day 30 | Quantization & Deploy Local Model API | FastAPI wrapper + latency benchmark |
| Day 31 | RAG Architecture | RAG indexing/query architecture + trace schema |
| Day 32 | Embedding Models & Benchmark cho tieng Viet | Benchmark 3 embedding models tren 20 queries |

## File Chi Tiet

| Ngay | File |
|---:|---|
| Day 25 | [Khi nao Fine-tune, khi nao dung RAG](./bai-hoc-day-25-32/day-25-khi-nao-fine-tune-khi-nao-dung-rag.md) |
| Day 26 | [Dataset Preparation cho Instruction Tuning](./bai-hoc-day-25-32/day-26-dataset-preparation-instruction-tuning.md) |
| Day 27 | [LoRA/QLoRA Hands-on](./bai-hoc-day-25-32/day-27-lora-qlora-hands-on.md) |
| Day 28 | [Evaluation truoc/sau Fine-tune](./bai-hoc-day-25-32/day-28-evaluation-truoc-sau-fine-tune.md) |
| Day 29 | [Local LLM - Ollama, llama.cpp, vLLM](./bai-hoc-day-25-32/day-29-local-llm-ollama-llama-cpp-vllm.md) |
| Day 30 | [Quantization & Deploy Local Model API](./bai-hoc-day-25-32/day-30-quantization-deploy-local-model-api.md) |
| Day 31 | [RAG Architecture](./bai-hoc-day-25-32/day-31-rag-architecture.md) |
| Day 32 | [Embedding Models & Benchmark cho tieng Viet](./bai-hoc-day-25-32/day-32-embedding-models-benchmark-tieng-viet.md) |

## Tong Quan Learning Path

Day 25-30 hoan tat Phase 4: Fine-tuning & Local LLM. Muc tieu khong phai train model lon, ma la biet ra quyet dinh: khi nao dung RAG, khi nao fine-tune, du lieu nao duoc phep train, adapter nao duoc deploy, va local model co that su tot hon hosted API trong dieu kien nao.

Day 31-32 mo dau Phase 5: Production RAG. Hai ngay nay dat nen mong cho ingestion, retrieval, reranking, citation, embedding benchmark va eval. Neu lam ky 2 ngay nay, cac bai Vector DB, hybrid search, reranking, RAG evaluation va production deployment sau do se ro rang hon nhieu.

## Artifact Nen Co Sau Day 25-32

| Artifact | Den tu ngay | Gia tri production |
|---|---:|---|
| AI technique decision record | Day 25 | Chon prompt/RAG/tool/fine-tune/hybrid co ly do |
| Instruction dataset 500 examples | Day 26 | Du lieu train co schema, split, privacy review |
| LoRA adapter artifact | Day 27 | Fine-tune behavior/format voi chi phi thap |
| Before/after eval report | Day 28 | Chung minh adapter tot hon base model |
| Local LLM decision note | Day 29 | Chon runtime dua tren latency/cost/privacy |
| FastAPI local model gateway | Day 30 | API boundary co timeout/logging/benchmark |
| RAG architecture design | Day 31 | Tach indexing/query/eval/admin path |
| Embedding benchmark report | Day 32 | Chon embedding model dua tren data tieng Viet |

## Production Gate

Truoc khi dua bat ky output nao cua nhom bai nay vao capstone, can co it nhat:

- Golden eval set tach khoi train data.
- Version cho dataset, prompt, base model, adapter, embedding model va index.
- Privacy review cho data train, prompt logs, retrieval context va embedding provider.
- Rollback plan cho adapter/local runtime/index version.
- Latency/cost budget cho RAG va local LLM path.
- Security notes cho prompt injection, ACL leak, PII logging va tool abuse.

## Learning Cadence

| Thoi luong | Viec lam |
|---:|---|
| 10 phut | Doc TL;DR va muc tieu |
| 35 phut | Hoc concept chinh |
| 45 phut | Hands-on/code/design |
| 20 phut | Ghi chu trade-off, performance, production concern |
| 10 phut | Update learning log |
