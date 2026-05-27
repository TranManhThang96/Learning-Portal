# Ngày 26: HuggingFace & Local Models

## 🎯 Mục tiêu học tập
- Hiểu và sử dụng được HuggingFace Transformers pipeline API để chạy các tác vụ NLP phổ biến
- Cài đặt và gọi local LLM qua Ollama từ Python
- Tạo embedding vectors bằng local embedding models
- Phân tích được trade-offs giữa API cloud vs local model để chọn đúng giải pháp

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| Gọi AI model | `openai.responses.create()` | `pipeline("text-generation")(prompt)` |
| Package manager | `npm install @huggingface/inference` | `uv add transformers torch` |
| Inference local | Không phổ biến, thường dùng API | Native với `transformers`, `llama.cpp` |
| Streaming | `for await (const chunk of stream)` | `for token in streamer:` |
| Tensor operations | Không có native | `torch.tensor()`, NumPy arrays |
| Model loading | N/A | `AutoModel.from_pretrained("model-id")` |

Khác biệt lớn nhất: Python là ngôn ngữ "native" của ML ecosystem. HuggingFace, PyTorch, TensorFlow đều viết bằng Python. NodeJS chỉ là wrapper, Python là ngôn ngữ gốc.

## 🧰 Hardware & Local Fallback

Các bài trong ngày này phải chạy được trên laptop CPU, nhưng tốc độ và dung lượng tải model sẽ khác nhau rất lớn. Ước tính dưới đây dùng model nhỏ để learner không bị block:

| Phần | Model gợi ý | Disk tải lần đầu | RAM/VRAM ước tính | CPU fallback |
|------|-------------|------------------|-------------------|--------------|
| Pipeline sentiment/QA | DistilBERT/SQuAD nhỏ | 250-500MB | 1-2GB RAM | Chạy được, latency vài trăm ms đến vài giây |
| Text generation demo | `gpt2` | ~550MB | 2-4GB RAM | Chạy được với `max_new_tokens` nhỏ, không batch lớn |
| Embedding FAQ | `all-MiniLM-L6-v2` | ~90MB | <1GB RAM | Chạy tốt trên CPU |
| Ollama chat | `llama3.2:3b` Q4 | ~2GB | 6-8GB RAM | Chạy được nhưng token/sec thấp; giảm context và output tokens |

Nếu máy yếu: đặt `device=-1`, dùng `gpt2` hoặc `distilgpt2`, giảm `max_new_tokens <= 64`, và ưu tiên Bài 1-2 trước. Bài Ollama là challenge nếu không đủ RAM.

## 📖 Lý thuyết

### 1. HuggingFace Transformers Pipeline API

**WHY:** Pipeline API là lớp abstraction cao nhất của HuggingFace, giúp bạn chạy các tác vụ AI phức tạp chỉ với 2-3 dòng code mà không cần hiểu sâu về model architecture. Tương tự như cách Express.js abstract HTTP server.

**HOW:** Pipeline tự động tải model, tokenizer, xử lý input/output. Bạn chỉ cần chỉ định task name.

```python
# Cài đặt: uv add transformers torch sentencepiece
from transformers import pipeline
import torch

# Kiểm tra GPU có sẵn không
device = 0 if torch.cuda.is_available() else -1
print(f"Dùng device: {'GPU' if device == 0 else 'CPU'}")

# === TEXT CLASSIFICATION ===
# Task: phân loại cảm xúc (sentiment analysis)
classifier = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
    device=device
)

results = classifier([
    "I love this product, it's amazing!",
    "This is terrible, worst experience ever.",
    "It's okay, nothing special."
])

for text, result in zip(["positive", "negative", "neutral"], results):
    print(f"Predicted: {result['label']}, Score: {result['score']:.3f}")

# Output:
# Predicted: POSITIVE, Score: 0.999
# Predicted: NEGATIVE, Score: 0.998
# Predicted: NEGATIVE, Score: 0.693
```

```python
# === TEXT GENERATION ===
from transformers import pipeline

# Dùng model nhỏ để test nhanh (GPT-2)
generator = pipeline(
    "text-generation",
    model="gpt2",
    device=-1  # CPU
)

# Sinh văn bản từ prompt
output = generator(
    "Python is a programming language that",
    max_new_tokens=50,      # số token tối đa sinh thêm
    num_return_sequences=2,  # sinh 2 đoạn khác nhau
    temperature=0.7,         # độ random (0=deterministic, 1=creative)
    do_sample=True,          # bật sampling
    pad_token_id=50256       # tránh warning
)

for i, seq in enumerate(output):
    print(f"\n--- Sequence {i+1} ---")
    print(seq['generated_text'])
```

```python
# === QUESTION ANSWERING ===
from transformers import pipeline

qa_pipeline = pipeline(
    "question-answering",
    model="distilbert-base-cased-distilled-squad"
)

context = """
Python was created by Guido van Rossum and first released in 1991.
It emphasizes code readability and uses indentation to define code blocks.
Python supports multiple programming paradigms including procedural,
object-oriented, and functional programming.
"""

questions = [
    "Who created Python?",
    "When was Python first released?",
    "What does Python emphasize?"
]

for question in questions:
    result = qa_pipeline(question=question, context=context)
    print(f"Q: {question}")
    print(f"A: {result['answer']} (confidence: {result['score']:.3f})\n")
```

```python
# === ZERO-SHOT CLASSIFICATION ===
# Phân loại KHÔNG cần fine-tune, chỉ cần mô tả label
from transformers import pipeline

classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

text = "The new iPhone 15 has amazing camera features and long battery life"
candidate_labels = ["technology", "sports", "politics", "entertainment", "business"]

result = classifier(text, candidate_labels)
print("Text:", text)
print("\nKết quả phân loại:")
for label, score in zip(result['labels'], result['scores']):
    bar = "█" * int(score * 20)
    print(f"  {label:15s}: {score:.3f} {bar}")
```

```python
# === SUMMARIZATION ===
from transformers import pipeline

summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn"
)

long_text = """
Machine learning is a subset of artificial intelligence (AI) that provides systems
the ability to automatically learn and improve from experience without being explicitly
programmed. Machine learning focuses on the development of computer programs that can
access data and use it to learn for themselves. The process begins with observations or
data, such as examples, direct experience, or instruction, to look for patterns in data
and make better decisions in the future. The primary aim is to allow the computers to
learn automatically without human intervention or assistance and adjust actions accordingly.
"""

summary = summarizer(
    long_text,
    max_length=100,
    min_length=30,
    do_sample=False
)

print("Original length:", len(long_text.split()))
print("Summary length:", len(summary[0]['summary_text'].split()))
print("\nSummary:", summary[0]['summary_text'])
```

### 2. Chạy Local LLM với Ollama

**WHY:** Ollama cho phép chạy các LLM mạnh (Llama, Mistral, Gemma) hoàn toàn local, không cần internet, không tốn tiền API, dữ liệu không rời khỏi máy. Quan trọng cho các use case nhạy cảm về privacy.

**HOW:** Ollama expose REST API tương tự OpenAI, bạn có thể dùng openai client hoặc requests trực tiếp.

```python
# Cài đặt Ollama: https://ollama.ai
# Sau khi cài: ollama pull llama3.2:3b
# uv add ollama

import ollama

# === BASIC CHAT ===
def chat_with_ollama(prompt: str, model: str = "llama3.2:3b") -> str:
    """Gọi Ollama model đơn giản"""
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response['message']['content']

# Test basic call
answer = chat_with_ollama("Giải thích Python list comprehension trong 2 câu")
print(answer)
```

```python
# === STREAMING RESPONSE ===
import ollama

def stream_ollama(prompt: str, model: str = "llama3.2:3b"):
    """Stream từng token từ Ollama"""
    print(f"Model: {model}")
    print("-" * 40)

    # stream=True trả về generator
    stream = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    full_response = ""
    for chunk in stream:
        # Mỗi chunk có content mới
        token = chunk['message']['content']
        print(token, end='', flush=True)  # in ngay không buffer
        full_response += token

    print()  # newline cuối
    return full_response

stream_ollama("Viết một hàm Python tính fibonacci bằng memoization")
```

```python
# === MULTI-TURN CONVERSATION ===
import ollama
from typing import List, Dict

class OllamaChat:
    """Wrapper quản lý conversation history"""

    def __init__(self, model: str = "llama3.2:3b", system_prompt: str = ""):
        self.model = model
        self.messages: List[Dict[str, str]] = []

        # System prompt định hướng behavior
        if system_prompt:
            self.messages.append({
                "role": "system",
                "content": system_prompt
            })

    def chat(self, user_message: str) -> str:
        """Gửi message và nhận response, giữ history"""
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        response = ollama.chat(
            model=self.model,
            messages=self.messages
        )

        assistant_message = response['message']['content']

        # Lưu response vào history để context tiếp theo
        self.messages.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message

    def reset(self):
        """Xóa history, giữ system prompt nếu có"""
        self.messages = [m for m in self.messages if m['role'] == 'system']

# Sử dụng
bot = OllamaChat(
    model="llama3.2:3b",
    system_prompt="Bạn là Python expert. Trả lời ngắn gọn, tập trung code."
)

# Conversation có context
r1 = bot.chat("Decorator trong Python là gì?")
print("Bot:", r1[:200], "...")

r2 = bot.chat("Cho tôi ví dụ thực tế")  # "ví dụ" ở đây hiểu là decorator
print("Bot:", r2[:200], "...")
```

```python
# === GỌI OLLAMA QUA OPENAI-COMPATIBLE API ===
# Hữu ích khi bạn muốn swap giữa OpenAI và local model
from openai import OpenAI

# Ollama serve tại localhost:11434 với OpenAI-compatible API
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Ollama không cần API key thật
)

def call_local_llm(prompt: str, model: str = "llama3.2:3b") -> str:
    # Ollama OpenAI-compatible endpoint vẫn dùng Chat Completions shape.
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content

# Giờ code giống hệt khi dùng OpenAI API thật
result = call_local_llm("List 5 Python best practices")
print(result)
```

### 3. Embedding Models Local

**WHY:** Embedding là cách biến văn bản thành vector số để máy tính so sánh "độ tương đồng ngữ nghĩa". Dùng cho semantic search, RAG, clustering. Chạy local tránh gửi dữ liệu nhạy cảm lên cloud.

**HOW:** `sentence-transformers` là thư viện chuẩn để tạo sentence embeddings local.

```python
# uv add sentence-transformers
from sentence_transformers import SentenceTransformer
import numpy as np

# Load model (tải lần đầu ~90MB)
model = SentenceTransformer('all-MiniLM-L6-v2')  # model nhỏ, nhanh
# all-mpnet-base-v2: chất lượng cao hơn, chậm hơn
# paraphrase-multilingual-MiniLM-L12-v2: hỗ trợ tiếng Việt

# === TẠO EMBEDDINGS ===
sentences = [
    "Python is great for machine learning",
    "I love programming in Python",
    "The weather is nice today",
    "Machine learning with Python is powerful",
    "It's sunny outside"
]

# Tạo embedding cho tất cả cùng lúc (batch processing)
embeddings = model.encode(sentences)
print(f"Shape: {embeddings.shape}")  # (5, 384) — 5 câu, mỗi câu 384 dimensions
print(f"Dtype: {embeddings.dtype}")  # float32
```

```python
# === SEMANTIC SIMILARITY ===
from sentence_transformers import SentenceTransformer, util
import torch

model = SentenceTransformer('all-MiniLM-L6-v2')

# Tính cosine similarity giữa các câu
query = "How to learn Python programming?"
corpus = [
    "Python tutorial for beginners",           # liên quan cao
    "JavaScript web development guide",         # không liên quan
    "Best resources to learn Python coding",    # liên quan cao
    "Python machine learning with scikit-learn", # liên quan trung bình
    "Cooking pasta at home",                    # không liên quan
]

# Encode
query_embedding = model.encode(query, convert_to_tensor=True)
corpus_embeddings = model.encode(corpus, convert_to_tensor=True)

# Tính cosine similarity
cosine_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]

# Sắp xếp theo độ tương đồng
results = sorted(
    zip(cosine_scores.tolist(), corpus),
    key=lambda x: x[0],
    reverse=True
)

print(f"Query: '{query}'\n")
print("Kết quả theo độ tương đồng:")
for score, sentence in results:
    bar = "█" * int(score * 20)
    print(f"  {score:.3f} {bar} | {sentence}")
```

```python
# === SEMANTIC SEARCH ENGINE ĐƠN GIẢN ===
from sentence_transformers import SentenceTransformer, util
import numpy as np

class SimpleSemanticSearch:
    """Search engine dùng embedding để tìm theo nghĩa, không chỉ keyword"""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
        self.documents = []
        self.embeddings = None

    def add_documents(self, docs: list[str]):
        """Thêm documents vào index"""
        self.documents.extend(docs)
        # Encode tất cả documents
        new_embeddings = self.model.encode(docs, convert_to_tensor=True)

        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            # Ghép embeddings mới vào existing
            import torch
            self.embeddings = torch.cat([self.embeddings, new_embeddings])

        print(f"Indexed {len(docs)} documents. Total: {len(self.documents)}")

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """Tìm kiếm theo semantic similarity"""
        query_embedding = self.model.encode(query, convert_to_tensor=True)

        # Tính similarity với tất cả documents
        scores = util.cos_sim(query_embedding, self.embeddings)[0]

        # Lấy top_k kết quả
        top_indices = scores.topk(min(top_k, len(self.documents))).indices

        results = []
        for idx in top_indices:
            results.append({
                "document": self.documents[idx],
                "score": scores[idx].item()
            })

        return results

# Demo
search_engine = SimpleSemanticSearch()

documents = [
    "Python decorators are functions that modify other functions",
    "List comprehensions provide a concise way to create lists",
    "Async/await in Python handles concurrent operations",
    "Type hints improve code readability and IDE support",
    "Context managers handle resource cleanup automatically",
    "Generators produce values lazily to save memory",
    "Dataclasses reduce boilerplate for data containers",
]

search_engine.add_documents(documents)

# Test queries
queries = [
    "how to handle async code",
    "memory efficient iteration",
    "code documentation and types"
]

for query in queries:
    print(f"\nQuery: '{query}'")
    results = search_engine.search(query, top_k=2)
    for r in results:
        print(f"  [{r['score']:.3f}] {r['document']}")
```

```python
# === EMBEDDING VỚI OLLAMA (hoàn toàn local) ===
import ollama
import numpy as np

def get_embedding_ollama(text: str, model: str = "nomic-embed-text") -> list[float]:
    """
    Tạo embedding dùng Ollama model.
    Cần: ollama pull nomic-embed-text
    """
    response = ollama.embeddings(
        model=model,
        prompt=text
    )
    return response['embedding']

# Test
text1 = "Python programming language"
text2 = "Snake programming tool"
text3 = "Cooking recipe for dinner"

emb1 = np.array(get_embedding_ollama(text1))
emb2 = np.array(get_embedding_ollama(text2))
emb3 = np.array(get_embedding_ollama(text3))

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

print(f"'{text1}' vs '{text2}': {cosine_sim(emb1, emb2):.3f}")  # cao
print(f"'{text1}' vs '{text3}': {cosine_sim(emb1, emb3):.3f}")  # thấp
```

### 4. API vs Local Model — Trade-offs

**WHY:** Không có giải pháp nào hoàn hảo. Bạn cần hiểu trade-offs để chọn đúng cho từng use case.

```python
# === FRAMEWORK ĐỂ QUYẾT ĐỊNH API VS LOCAL ===
from dataclasses import dataclass
from enum import Enum

class ModelChoice(Enum):
    API = "API Cloud"
    LOCAL = "Local"
    HYBRID = "Hybrid"

@dataclass
class UseCase:
    has_sensitive_data: bool      # dữ liệu nhạy cảm?
    requests_per_day: int         # số requests/ngày
    avg_tokens_per_request: int   # input + output tokens trung bình
    has_gpu: bool                 # có GPU không?
    budget_usd_per_month: float   # budget (USD/tháng)
    needs_latest_model: bool      # cần model mới nhất?
    api_price_usd_per_million_tokens: float  # lấy từ pricing page/config hiện hành

def decide_model_strategy(uc: UseCase) -> tuple[ModelChoice, str]:
    """
    Rule-based decision cho API vs Local.
    Thực tế thường phức tạp hơn, nhưng đây là framework cơ bản.
    """
    reasons = []

    # Hard constraint: dữ liệu nhạy cảm → local/private deployment.
    # "Local" vẫn cần policy cho logs, telemetry, backups và observability.
    if uc.has_sensitive_data:
        reasons.append("Dữ liệu nhạy cảm → ưu tiên local hoặc private deployment có retention policy rõ")
        return ModelChoice.LOCAL, "\n".join(reasons)

    # Tính cost ước tính với API.
    # Giá model thay đổi nhanh, nên lấy từ pricing page hoặc config vận hành.
    estimated_monthly_cost = (
        uc.requests_per_day
        * 30
        * uc.avg_tokens_per_request
        / 1_000_000
        * uc.api_price_usd_per_million_tokens
    )

    if estimated_monthly_cost > uc.budget_usd_per_month:
        reasons.append(f"Chi phí ước tính ${estimated_monthly_cost:.2f}/tháng vượt budget")
        if not uc.has_gpu:
            reasons.append("Không có GPU → CPU inference sẽ chậm")
            return ModelChoice.HYBRID, "\n".join(reasons)
        return ModelChoice.LOCAL, "\n".join(reasons)

    # Volume thấp, không nhạy cảm, trong budget → API dễ hơn
    if uc.requests_per_day < 1000 and not uc.has_sensitive_data:
        reasons.append("Volume thấp + không nhạy cảm → API tiện hơn")
        if uc.needs_latest_model:
            reasons.append("Cần model mới nhất → API")
        return ModelChoice.API, "\n".join(reasons)

    # Có GPU, volume cao → local efficient hơn
    if uc.has_gpu and uc.requests_per_day > 10000:
        reasons.append(f"Volume cao ({uc.requests_per_day}/ngày) + có GPU → local hiệu quả")
        return ModelChoice.LOCAL, "\n".join(reasons)

    reasons.append("Balanced → Hybrid (API cho complex, local cho simple)")
    return ModelChoice.HYBRID, "\n".join(reasons)

# Test các scenarios
scenarios = [
    UseCase(True, 500, 2000, False, 100, True, 2.50),      # healthcare data
    UseCase(False, 100, 5000, False, 20, True, 2.50),       # startup với budget nhỏ
    UseCase(False, 50000, 200, True, 500, False, 0.20),     # high volume với GPU
    UseCase(False, 200, 1000, False, 200, True, 2.50),      # normal web app
]

scenario_names = [
    "Healthcare app (dữ liệu nhạy cảm)",
    "Startup nhỏ (budget eo hẹp)",
    "High-volume service (có GPU)",
    "Web app thông thường",
]

for name, uc in zip(scenario_names, scenarios):
    choice, reason = decide_model_strategy(uc)
    print(f"\n📌 {name}")
    print(f"   Quyết định: {choice.value}")
    print(f"   Lý do: {reason}")
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Load model trong loop | Cực kỳ chậm, OOM | Load model 1 lần, tái sử dụng nhiều lần |
| Không dùng `torch.no_grad()` khi inference | Tốn 2x memory không cần thiết | Wrap inference code trong `with torch.no_grad():` |
| Dùng CPU cho batch lớn | Chậm 10-100x so với GPU | Kiểm tra `device` và move tensor sang GPU |
| Gửi dữ liệu nhạy cảm lên HuggingFace API | Vi phạm compliance | Dùng local model hoặc enterprise plan |
| Không pin model version | Code break khi model update | Dùng commit hash: `model="bert-base/abc123"` |
| Encode từng câu trong loop | 10-50x chậm hơn batch | Encode list cùng lúc: `model.encode(sentences)` |
| Không handle OOM error | App crash | Try/catch `torch.cuda.OutOfMemoryError` |

## ✅ Best Practices

- **Cache model sau khi load:** Model load tốn 2-10 giây, không load lại mỗi request. Dùng singleton pattern hoặc module-level variable.
- **Batch processing:** Luôn encode nhiều items cùng lúc thay vì từng cái một, tăng throughput 5-20x.
- **Sử dụng `half precision` (fp16) trên GPU:** Giảm memory 50%, tốc độ tăng 30-50% trên hardware hiện đại.
- **Quantization cho local inference:** GGUF format (llama.cpp) cho phép chạy model 7B trên laptop CPU.
- **Monitor memory usage:** `torch.cuda.memory_allocated()` để theo dõi GPU memory.
- **Dùng `device_map="auto"` cho model lớn:** Tự động split model qua nhiều GPU hoặc CPU+GPU.
- **Tokenizer và model phải match:** Luôn load tokenizer từ cùng model checkpoint.

## ⚖️ Trade-offs

**HuggingFace Transformers vs Ollama:**

| | HuggingFace Transformers | Ollama |
|--|--------------------------|--------|
| Flexibility | Rất cao — access full model | Thấp hơn — black box |
| Ease of use | Trung bình — cần biết PyTorch | Cao — chỉ cần REST API |
| Custom models | Dễ dàng | Khó hơn (cần tạo Modelfile) |
| Memory management | Manual | Tự động |
| Use case | Research, fine-tuning | Production serving |

**Cloud API vs Local:**

| | Cloud API | Local |
|--|-----------|-------|
| Chi phí | Thấp khi volume nhỏ; phải đọc pricing hiện hành | Thấp khi volume lớn nếu đã có hardware/ops |
| Latency | Phụ thuộc network, region, queue và model tier | Từ vài chục ms đến nhiều giây, phụ thuộc GPU/CPU, quantization và context |
| Privacy | Dữ liệu rời khỏi máy; cần đọc retention/data-control policy | Có thể private hơn, nhưng vẫn phải kiểm soát logs, telemetry và backups |
| Setup | 5 phút | 30 phút - vài giờ |
| Model quality | Frontier models và managed features mới nhất | Phụ thuộc model local; 3B-7B phù hợp lab, 13B-70B cần hardware nghiêm túc |

## 🚀 Performance Notes

- **Quantization:** 8-bit thường giảm memory khoảng một nửa; 4-bit/GGUF có thể đưa model 7B về khoảng 4-6GB RAM/VRAM, nhưng chất lượng và tốc độ phụ thuộc backend, GPU/CPU, kernel và batch size. Đừng promise "chỉ giảm 5-10% tốc độ" trong tài liệu production.
- **bitsandbytes caveat:** `BitsAndBytesConfig(load_in_8bit=True/load_in_4bit=True)` trong Transformers cần model hỗ trợ Accelerate và chủ yếu tối ưu cho GPU/backend được bitsandbytes hỗ trợ. Nếu chạy CPU laptop, GGUF qua Ollama/llama.cpp thường thực tế hơn PyTorch + bitsandbytes.
- **Flash Attention 2:** Dùng `attn_implementation="flash_attention_2"` cho model hỗ trợ, nhưng chỉ phù hợp khi model ở `fp16`/`bf16` và chạy trên device hỗ trợ. Lợi ích rõ nhất với sequence dài; batched generation có nhiều padding có thể chậm hơn kỳ vọng.
- **Batch size optimization:** Tăng batch size tới khi gần đầy GPU memory để maximize throughput.
- **Pipeline parallelism:** Với model rất lớn, dùng `device_map="auto"` để spread across devices.
- **Caching tokenized inputs:** Nếu prompt cố định (system prompt), tokenize 1 lần, reuse nhiều lần.
- **CPU inference:** Với CPU-only, ưu tiên GGUF Q4/Q5 qua Ollama/llama.cpp, giảm context window, tắt batch lớn, và chấp nhận latency tính bằng giây cho 3B-7B.

## 📝 Tóm tắt

- Pipeline API của HuggingFace là fastest path để chạy NLP tasks (classification, generation, QA, summarization) với vài dòng code
- Ollama là cách dễ nhất để chạy local LLM, expose OpenAI-compatible API nên dễ swap với cloud API
- `sentence-transformers` là thư viện chuẩn cho embedding, hỗ trợ semantic search, RAG
- Local model phù hợp khi: dữ liệu nhạy cảm, volume cao, cần offline, budget hạn chế
- Cloud API phù hợp khi: cần frontier models/features mới nhất, volume thấp, muốn setup nhanh, hoặc không muốn vận hành inference stack
- Luôn load model một lần và tái sử dụng, không load trong loop
- Batch processing quan trọng hơn nhiều so với NodeJS vì ML operations có overhead lớn hơn
