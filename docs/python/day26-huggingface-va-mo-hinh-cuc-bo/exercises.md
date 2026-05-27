# Bài Tập — Ngày 26: HuggingFace & Local Models

## Ước tính tài nguyên trước khi làm bài

| Bài | Có bắt buộc GPU? | Disk tải model | RAM/VRAM ước tính | Fallback CPU |
|-----|------------------|----------------|-------------------|--------------|
| Bài 1 — Pipelines | Không | 700MB-1.5GB nếu chạy đủ sentiment + zero-shot + summarization | 2-4GB RAM | Nếu chậm, bỏ summarization hoặc dùng text <100 words |
| Bài 2 — FAQ embeddings | Không | ~90MB (`all-MiniLM-L6-v2`) | <1GB RAM | Chạy tốt trên laptop |
| Bài 3 — Ollama chat | Không, nhưng RAM quan trọng | ~2GB (`llama3.2:3b`) | 6-8GB RAM; GPU 6GB+ nhanh hơn | Dùng `llama3.2:1b`/model nhỏ hơn, giảm context, hoặc mock response |

Nếu máy không đủ tài nguyên, vẫn hoàn thành acceptance criteria bằng Bài 1-2 và chạy Bài 3 ở mock mode: giữ memory/cache/token counting y hệt, thay phần gọi Ollama bằng function trả về response cố định.

## Bài 1 — Multi-Task NLP Pipeline (Cơ bản)

**Mô tả:** Xây dựng một script Python chạy nhiều NLP tasks khác nhau trên cùng một đoạn text input, sử dụng HuggingFace Pipeline API.

**Yêu cầu:**
1. Nhận input text từ user (dùng `input()` hoặc hardcode 3-5 câu tiếng Anh)
2. Chạy **sentiment analysis** → in ra label và confidence score
3. Chạy **zero-shot classification** với labels: `["technology", "science", "politics", "sports", "entertainment"]`
4. Chạy **summarization** nếu text > 100 words
5. Format output đẹp với separator và icon (dùng print, không cần thư viện)

**Expected output:**
```
=== NLP Analysis Results ===

📊 Sentiment: POSITIVE (confidence: 0.987)

🏷️  Topic Classification:
    - technology: 0.823 ████████████████░░░░
    - science:    0.104 ██░░░░░░░░░░░░░░░░░░
    - ...

📋 Summary (word count: 45):
    "Python is a versatile language..."

✅ Analysis complete!
```

**Hint:**
- Dùng `pipeline("sentiment-analysis")`, `pipeline("zero-shot-classification")`, `pipeline("summarization")`
- Tính word count bằng `len(text.split())`
- Vẽ progress bar: `"█" * int(score * 20) + "░" * (20 - int(score * 20))`
- CPU-only: set `device=-1`, chạy từng pipeline tuần tự, và chỉ load summarization khi cần để tránh giữ nhiều model trong RAM.

---

## Bài 2 — Semantic FAQ Search Engine (Trung bình)

**Mô tả:** Xây dựng một FAQ search engine đơn giản dùng sentence embeddings. User nhập câu hỏi bằng ngôn ngữ tự nhiên, hệ thống tìm FAQ gần nhất về nghĩa.

**Yêu cầu:**
1. Tạo FAQ database với ít nhất 10 cặp Q&A về Python (hardcode trong script)
2. Encode tất cả questions khi khởi động (chỉ encode 1 lần)
3. Vòng lặp: nhận query từ user → tìm top-3 FAQ phù hợp nhất → hiển thị với score
4. Nếu score của kết quả tốt nhất < 0.3, hiển thị "Không tìm thấy FAQ phù hợp"
5. Gõ `quit` để thoát, in ra số queries đã xử lý

**FAQ mẫu để dùng:**
```python
FAQ = [
    {"q": "What is a Python decorator?", "a": "A decorator is a function that wraps another function to extend its behavior."},
    {"q": "How to read a file in Python?", "a": "Use open() with 'r' mode: with open('file.txt', 'r') as f: content = f.read()"},
    {"q": "What is list comprehension?", "a": "A concise way to create lists: [x*2 for x in range(10)]"},
    {"q": "How to handle exceptions?", "a": "Use try/except: try: risky_code() except Exception as e: handle(e)"},
    {"q": "What is a generator?", "a": "A function using yield to produce values lazily without storing all in memory"},
    {"q": "How to install packages?", "a": "Use pip: uv add package_name"},
    {"q": "What are type hints?", "a": "Annotations like def foo(x: int) -> str: that help IDEs and static analyzers"},
    {"q": "What is the GIL?", "a": "Global Interpreter Lock prevents true parallelism in CPython threads"},
    {"q": "How to create a virtual environment?", "a": "Run: python -m venv venv, then activate with source venv/bin/activate"},
    {"q": "What is a context manager?", "a": "Objects using __enter__ and __exit__ for resource management, used with 'with' statement"},
]
```

**Expected output:**
```
FAQ Search Engine (sentence-transformers)
Nhập câu hỏi (hoặc 'quit' để thoát):

> how do I wrap a function
Top 3 kết quả:
  1. [0.782] Q: What is a Python decorator?
             A: A decorator is a function that wraps another function...

  2. [0.534] Q: What is a context manager?
             A: Objects using __enter__ and __exit__...

  3. [0.421] Q: What is a generator?
             A: A function using yield...
```

**Hint:**
- `SentenceTransformer('all-MiniLM-L6-v2').encode([q['q'] for q in FAQ])`
- `util.cos_sim(query_emb, faq_embeddings)[0]` trả về tensor, dùng `.tolist()` để convert
- `sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:3]` để lấy top-3

---

## Bài 3 — Ollama Chat với Context & Caching (Nâng cao / Challenge)

**Mô tả:** Xây dựng một CLI chatbot sử dụng Ollama với các tính năng: conversation memory, response caching (tránh gọi lại cùng câu hỏi), và cost estimation (tính số tokens đã dùng).

**Yêu cầu:**

1. **Conversation Memory:** Giữ toàn bộ conversation history, có thể `!reset` để xóa
2. **Response Caching:** Cache response dựa trên exact match của query. Nếu user hỏi câu đã hỏi → trả về cached response ngay lập tức, in `[CACHED]`
3. **Token Counting:** Đếm tokens đã dùng (ước tính: 1 token ≈ 4 characters). In stats sau mỗi response:
   ```
   [Tokens: input=234 | output=156 | total_session=1240]
   ```
4. **Commands hỗ trợ:**
   - `!reset` — xóa conversation history và cache
   - `!stats` — hiển thị session statistics (total queries, cached hits, total tokens)
   - `!history` — in toàn bộ conversation history
   - `!quit` — thoát
5. **Streaming:** Dùng streaming API để in từng token, không đợi full response
6. **Error handling:** Nếu Ollama không chạy, in thông báo hướng dẫn thay vì crash

**Expected output:**
```
🤖 Ollama Chat (model: llama3.2:3b)
Type !help for commands

You: What is Python?
Assistant: Python is a high-level, interpreted programming language...
[Tokens: input=12 | output=89 | total_session=101]

You: What is Python?
[CACHED] Assistant: Python is a high-level, interpreted programming language...
[Tokens: input=0 | output=0 | total_session=101] (served from cache)

You: !stats
=== Session Statistics ===
Total queries:    2
Cache hits:       1 (50.0%)
Total tokens:     101
Estimated cost:   $0.00 API cost khi chạy local; nếu so sánh cloud, tự lấy giá hiện hành từ pricing page
```

**Hint:**
- Cache bằng `dict`: `cache = {}`, key là `query.strip().lower()`
- Token estimate: `len(text) // 4`
- Ollama connection error: `except ConnectionError: print("Ollama không chạy. Chạy: ollama serve")`
- Streaming: `for chunk in ollama.chat(..., stream=True): print(chunk['message']['content'], end='', flush=True)`
- Mock mode khi không có Ollama/RAM: tạo `mock_chat(history) -> str` trả về câu cố định nhưng vẫn đi qua cache, token counter và command handling.

**Bonus challenge:** Thêm **semantic caching** — thay vì exact match, dùng cosine similarity > 0.95 để coi là "câu hỏi giống nhau" và trả về cached response.

---

## 🔍 Gợi ý kiểm tra kết quả

**Bài 1:**
- Chạy với text: *"Python is an amazing programming language used in AI, web development, and data science. It has a simple syntax that makes it perfect for beginners while being powerful enough for experts."*
- Kết quả sentiment phải là POSITIVE với score > 0.9
- Topic "technology" hoặc "science" phải có score cao nhất

**Bài 2:**
- Test với các queries khác nhau về ngữ nghĩa nhưng cùng ý:
  - `"how to add behavior to a function"` → phải match "decorator"
  - `"lazy evaluation"` → phải match "generator"
  - `"what is pizza"` → score thấp < 0.3, hiển thị "Không tìm thấy"

**Bài 3:**
- Đảm bảo cache hoạt động: hỏi cùng câu 2 lần, lần 2 phải có `[CACHED]`
- `!stats` phải hiển thị đúng số cache hits
- Test error handling: tắt Ollama rồi chạy, không được crash

**Kiểm tra environment:**
```bash
# Kiểm tra transformers
python -c "from transformers import pipeline; print('OK')"

# Kiểm tra sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; print('OK')"

# Kiểm tra Ollama
curl http://localhost:11434/api/tags
```
