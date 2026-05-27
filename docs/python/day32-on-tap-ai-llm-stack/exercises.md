# Bài Tập — Ngày 32: Ôn tập AI/LLM Stack

## Bài 1 — Debug một RAG Pipeline Broken (Cơ bản)

**Mô tả:** Tìm và fix các vấn đề trong RAG pipeline dưới đây.

**Code có vấn đề:**
```python
# broken_rag.py — Tìm ít nhất 5 vấn đề
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import CharacterTextSplitter

def create_rag():
    splitter = CharacterTextSplitter(chunk_size=50, chunk_overlap=0)  # Vấn đề 1
    embeddings = OpenAIEmbeddings()
    llm = ChatOpenAI(temperature=1.0)  # Vấn đề 2
    vectorstore = Chroma(embedding_function=embeddings)

    def answer(question: str) -> str:
        docs = vectorstore.similarity_search(question, k=1)  # Vấn đề 3
        context = docs[0].page_content if docs else ""  # Vấn đề 4
        prompt = f"Answer: {question}"  # Vấn đề 5 — không dùng context!
        response = llm.invoke(prompt)
        return response.content

    return answer
```

**Yêu cầu:**
1. Liệt kê 5+ vấn đề với giải thích tại sao mỗi vấn đề gây ra lỗi
2. Viết lại `create_rag()` function đúng
3. Thêm basic test: upload một đoạn text, query về nó, verify answer chứa thông tin từ text
4. Thêm smoke mode dùng mock embeddings/mock LLM để test imports và retrieval path không cần `OPENAI_API_KEY`

**Expected output:**
```
Issues found:
1. chunk_size=50: quá nhỏ, mất context...
2. temperature=1.0: output không nhất quán cho factual Q&A...
...

Test passed: Answer contains expected information from document
Smoke passed: LangChain imports + mock retrieval OK
```

---

## Bài 2 — Build RAG Chatbot với Memory (Trung bình)

**Mô tả:** Xây dựng RAG chatbot hỗ trợ multi-turn conversation (nhớ lịch sử chat).

**Yêu cầu:**
1. Implement `ConversationalRAG` class với:
   - `load_document(text: str, source: str)` — ingest document
   - `async chat(user_message: str, session_id: str) -> AsyncIterator[str]` — streaming response
   - Conversation history per session (dùng dict hoặc Redis)
2. Prompt phải include: system prompt, conversation history, retrieved context, user message
3. Test với scenario:
   - Upload document về Python
   - Turn 1: "Python là gì?"
   - Turn 2: "Tôi vừa hỏi về gì?" (bot phải nhớ)
   - Turn 3: "Kể thêm về topic đó"
4. Implement `clear_history(session_id: str)` để reset conversation

**Expected output:**
```
Turn 1 Q: Python là gì?
Turn 1 A: Python là ngôn ngữ lập trình...

Turn 2 Q: Tôi vừa hỏi về gì?
Turn 2 A: Bạn vừa hỏi về Python, ngôn ngữ lập trình...

Turn 3 Q: Kể thêm về topic đó
Turn 3 A: Về Python, ngoài những gì đã đề cập...
```

**Hint:**
- `ConversationBufferWindowMemory(k=5)` — giữ 5 turns gần nhất
- Hoặc manual: `history: list[dict[str, str]]` với `{"role": "user/assistant", "content": "..."}`
- LCEL với history: `RunnableWithMessageHistory`

---

## Bài 3 — Build Full RAG Chatbot từ Scratch (Nâng cao / Challenge)

**Mô tả:** Xây dựng RAG chatbot hoàn chỉnh với FastAPI backend và CLI client.

**Yêu cầu:**
1. **FastAPI backend** với endpoints:
   - `POST /documents` — upload và ingest file (txt, pdf)
   - `POST /chat` — streaming chat với RAG
   - `GET /documents` — list uploaded documents
   - `DELETE /history` — clear chat history

2. **RAG Pipeline** features:
   - Chroma vector store với persistence
   - Hybrid search (semantic + keyword) nếu có thể
   - Source citation trong response (trích dẫn document nào được dùng)
   - Conversation memory (last 5 turns)

3. **CLI client** (`cli.py`) với:
   - Upload file: `python cli.py upload path/to/file.txt`
   - Chat: `python cli.py chat "Câu hỏi của bạn"`
   - Show sources: display document sources được cite

4. **Tests** (`test_rag.py`):
   - Test document ingestion
   - Test retrieval chính xác (query về content đã ingest)
   - Test conversation memory
   - Test source citation

**Evaluation criteria:**
- RAG accuracy: upload document với facts cụ thể, query facts đó, bot trả lời đúng
- Memory: bot nhớ context từ turns trước
- Source citation: response mention document name

## 🔍 Gợi ý kiểm tra kết quả

### Test RAG accuracy
```python
# test_accuracy.py
import asyncio

GOLDEN_DATASET = [
    {
        "document": "Python được tạo bởi Guido van Rossum năm 1991.",
        "question": "Ai tạo ra Python?",
        "expected_keywords": ["Guido", "van Rossum"],
    },
    {
        "document": "FastAPI được tạo bởi Sebastián Ramírez năm 2018.",
        "question": "FastAPI ra đời năm nào?",
        "expected_keywords": ["2018"],
    },
]

async def test_accuracy(rag_chatbot):
    scores = []
    for case in GOLDEN_DATASET:
        rag_chatbot.load_document(case["document"], "test")
        answer = ""
        async for chunk in rag_chatbot.chat(case["question"], "test_session"):
            answer += chunk

        keywords_found = sum(
            1 for kw in case["expected_keywords"]
            if kw.lower() in answer.lower()
        )
        score = keywords_found / len(case["expected_keywords"])
        scores.append(score)
        print(f"Q: {case['question']}")
        print(f"A: {answer}")
        print(f"Score: {score:.0%}\n")

    print(f"Overall accuracy: {sum(scores)/len(scores):.0%}")
```

### Test memory
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tên tôi là Thang", "session_id": "test"}'
# Response: Xin chào Thang!

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tên tôi là gì?", "session_id": "test"}'
# Response: Tên bạn là Thang (nhớ từ turn trước)
```
