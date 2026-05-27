# Tài Liệu Tham Khảo — Ngày 26

## 📚 Official Docs

- **HuggingFace Transformers Docs** — https://huggingface.co/docs/transformers — Tài liệu chính thức, có pipeline API reference đầy đủ
- **HuggingFace Pipeline API** — https://huggingface.co/docs/transformers/main_classes/pipelines — Danh sách tất cả pipeline tasks có sẵn
- **Sentence Transformers Docs** — https://www.sbert.net/docs/quickstart.html — Quickstart và danh sách pretrained models
- **Ollama Docs** — https://ollama.com/library — Danh sách models có sẵn và cách dùng
- **Ollama API Reference** — https://github.com/ollama/ollama/blob/main/docs/api.md — REST API docs
- **HuggingFace Model Hub** — https://huggingface.co/models — Tìm kiếm models theo task

## 🎥 Video / Courses

- **HuggingFace NLP Course (miễn phí)** — https://huggingface.co/learn/nlp-course — Course chính thức, rất đầy đủ, có code exercises
- **Andrej Karpathy: Intro to LLMs** — https://www.youtube.com/watch?v=zjkBMFhNj_g — 1 giờ, giải thích cách LLM hoạt động từ đầu
- **Getting Started with Ollama** — https://www.youtube.com/watch?v=ZoxJcPkjirs — Hướng dẫn setup Ollama từ đầu đến cuối
- **sentence-transformers Tutorial** — https://www.youtube.com/watch?v=OATCgQtNX2o — Hands-on với semantic search

## 📝 Articles / Blog Posts

- **A Beginner's Guide to HuggingFace Pipelines** — https://huggingface.co/blog/pipeline — Official blog, giải thích Pipeline từng bước
- **Running LLMs Locally with Ollama** — https://ollama.com/blog — Official blog Ollama
- **Sentence Transformers: Semantic Search** — https://www.sbert.net/examples/applications/semantic-search/README.html — Ví dụ thực tế về semantic search
- **Local LLM Comparison** — https://github.com/ollama/ollama — README có so sánh models, hardware requirements
- **API vs Local LLM Cost Calculator** — https://llm-price.com — Tool so sánh chi phí các API providers

## 🔧 Tools / Libraries

- **transformers** — `uv add transformers` — Core library của HuggingFace
- **torch** — `uv add torch` — PyTorch, backend cho transformers (CPU: `uv add torch --index-url https://download.pytorch.org/whl/cpu`)
- **sentence-transformers** — `uv add sentence-transformers` — Embedding models
- **ollama** — `uv add ollama` — Python client cho Ollama
- **openai** — `uv add openai` — Dùng OpenAI-compatible API với Ollama
- **huggingface_hub** — `uv add huggingface_hub` — Download/upload models
- **accelerate** — `uv add accelerate` — Tối ưu inference trên GPU/CPU
- **bitsandbytes** — `uv add bitsandbytes` — Quantization (INT8/INT4) để giảm memory
- **LM Studio** — https://lmstudio.ai — GUI app để chạy local LLM, alternative cho Ollama

## 💡 Ghi chú thêm

**Cài đặt nhanh cho ngày 26:**
```bash
# Cài Python packages
uv add transformers torch sentence-transformers ollama

# Cài Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Tải model nhỏ để test
ollama pull llama3.2:3b          # LLM, ~2GB
ollama pull nomic-embed-text      # Embedding model, ~274MB
```

**Hardware recommendations:**
- CPU only: Ưu tiên embedding/small Transformers; LLM nên dùng GGUF Q4/Q5 ≤3B, giảm context và chấp nhận tốc độ chậm.
- 8GB RAM: 3B Q4 ổn hơn 7B; 7B Q4 có thể chạy nhưng dễ swap/OOM tùy OS và context window.
- 16GB RAM hoặc GPU 8GB: 7B Q4/Q5 thực tế hơn; 13B có thể chạy nhưng không nên xem là baseline bài học.
- GPU 24GB+: 13B/34B quantized thoải mái hơn; 70B quantized vẫn cần kiểm tra VRAM/RAM, offload và context.

**Caveat quantization/Flash Attention:**
- Transformers docs khuyến nghị `BitsAndBytesConfig` và `device_map="auto"` cho 8-bit/4-bit trên model hỗ trợ, nhưng backend support khác nhau theo CUDA/ROCm/CPU/OS.
- Flash Attention 2 cần model/dtype/device phù hợp (`fp16` hoặc `bf16`, device hỗ trợ) và lợi ích rõ nhất với long sequence ít padding.
- Với laptop CPU, Ollama/llama.cpp + GGUF thường là fallback đáng tin hơn PyTorch CPU cho local LLM.

**HuggingFace Models hay dùng (nhỏ, nhanh):**
- Text classification: `distilbert-base-uncased-finetuned-sst-2-english` (67MB)
- Embeddings: `all-MiniLM-L6-v2` (90MB), hỗ trợ tiếng Việt tốt
- Multilingual: `paraphrase-multilingual-MiniLM-L12-v2` (420MB)
- NER: `dbmdz/bert-large-cased-finetuned-conll03-english`

**Lưu ý cache:**
HuggingFace tự động cache models tại `~/.cache/huggingface/hub/`. Lần đầu tải chậm, lần sau dùng cache. Để thay đổi location: `export HF_HOME=/path/to/cache`
