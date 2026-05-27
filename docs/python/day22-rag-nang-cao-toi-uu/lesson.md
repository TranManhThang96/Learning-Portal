# Ngày 22: RAG Nâng Cao & Optimization

## 🎯 Mục tiêu học tập
- Hiểu và implement các chunking strategies khác nhau, biết khi nào dùng cái nào
- Xây dựng hybrid search kết hợp dense vectors (semantic) và sparse vectors (BM25)
- Implement re-ranking pipeline với cross-encoders để cải thiện độ chính xác
- Đánh giá chất lượng RAG pipeline bằng RAGAS framework
- Nhận diện và xử lý các failure mode phổ biến trong RAG

> **Version/import note:** LangChain retrieval APIs có nhiều thế hệ import. Ưu tiên package tách riêng cho integrations (`langchain_chroma`, `langchain_openai`, `langchain_text_splitters`, `langchain_community.retrievers` cho BM25). Với các retriever core như `EnsembleRetriever` hoặc `ContextualCompressionRetriever`, kiểm tra theo version đang pin; nếu import từ `langchain.retrievers.*` lỗi, tra docs của target version hoặc chuyển sang path tương ứng trong `langchain_classic`/package integration và thêm smoke test import.

## 🔄 So sánh với NodeJS

| Khái niệm RAG | Tương đương NodeJS | Ghi chú |
|--------------|-------------------|---------|
| Chunking | Splitting large JSON/text thành smaller payloads | Giống pagination nhưng cho content |
| Dense search | Full-text search với embeddings (elastic kNN) | Hiểu ngữ nghĩa, không cần exact match |
| Sparse search (BM25) | Elasticsearch full-text search mặc định | TF-IDF, exact keyword match |
| Hybrid search | Elasticsearch `bool` query kết hợp `knn` + `match` | Kết hợp 2 phương pháp |
| Re-ranking | Sorting results với scoring function phức tạp hơn | Post-processing sau khi fetch |
| RAGAS | Integration test suite cho RAG | Giống Jest test nhưng đánh giá AI output |

**Analogy quan trọng:** Trong NodeJS, khi bạn search Elasticsearch, bạn thường dùng combination của `match` (keyword) và `knn` (vector) — đó chính là hybrid search. RAG optimization là nâng cấp chính xác cái pattern này.

## 📖 Lý thuyết

### Section 1: Chunking Strategies — Tại sao quan trọng

**WHY — Tại sao chunking lại phức tạp?**

Khi bạn index một document vào vector database, bạn không thể index cả document một lúc (token limit của embedding model). Nhưng nếu chunk quá nhỏ, bạn mất context. Nếu chunk quá lớn, embedding trở nên "diluted" — vector đại diện cho quá nhiều thứ, mất đi sự chính xác.

Đây giống như vấn đề của microservices: service quá lớn thì khó maintain, quá nhỏ thì overhead cao. Cần tìm "sweet spot".

**Các chunking strategies:**

#### 1.1 Fixed-size Chunking (Naive)

```python
# uv add langchain-text-splitters tiktoken

from langchain_text_splitters import CharacterTextSplitter, TokenTextSplitter

# Character-based splitting — đơn giản nhất
# Vấn đề: có thể cắt giữa câu, giữa paragraph
char_splitter = CharacterTextSplitter(
    separator="\n",          # Tách theo newline
    chunk_size=1000,         # 1000 ký tự mỗi chunk
    chunk_overlap=200,       # 200 ký tự overlap giữa các chunk
    length_function=len,
)

# Token-based splitting — chính xác hơn cho LLM
# Dùng tiktoken để đếm tokens thật sự
token_splitter = TokenTextSplitter(
    encoding_name="cl100k_base",  # Encoding của GPT-4
    chunk_size=512,               # 512 tokens mỗi chunk
    chunk_overlap=50,
)

sample_text = """
Python là ngôn ngữ lập trình bậc cao, được thiết kế với triết lý
ưu tiên tính đọc được của code. Guido van Rossum tạo ra Python vào
năm 1991. Python hỗ trợ nhiều paradigm: OOP, functional, procedural.

Một trong những điểm mạnh của Python là ecosystem phong phú với
PyPI có hơn 400,000 packages. Từ data science (NumPy, Pandas) đến
web development (Django, FastAPI) và AI/ML (TensorFlow, PyTorch).
"""

# So sánh kết quả
char_chunks = char_splitter.split_text(sample_text)
token_chunks = token_splitter.split_text(sample_text)

print(f"Char splitter: {len(char_chunks)} chunks")
print(f"Token splitter: {len(token_chunks)} chunks")
for i, chunk in enumerate(char_chunks):
    print(f"\nChunk {i+1} ({len(chunk)} chars):\n{chunk[:100]}...")
```

#### 1.2 Recursive Character Splitting (Recommended Default)

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

# WHY recursive? Nó thử tách theo hierarchy:
# paragraph → sentence → word → character
# Giữ được context tốt hơn fixed-size

recursive_splitter = RecursiveCharacterTextSplitter(
    # Thứ tự ưu tiên tách: paragraph → newline → space → char
    separators=["\n\n", "\n", ".", " ", ""],
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    is_separator_regex=False,
)

# Với code — dùng language-aware splitter
from langchain_text_splitters import Language

python_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=2000,
    chunk_overlap=200,
)

typescript_code = """
// Đây là TypeScript code
interface User {
    id: string;
    name: string;
    email: string;
}

async function getUserById(id: string): Promise<User | null> {
    const result = await db.query('SELECT * FROM users WHERE id = $1', [id]);
    return result.rows[0] || null;
}

class UserService {
    constructor(private db: Database) {}

    async createUser(data: Omit<User, 'id'>): Promise<User> {
        const id = generateId();
        const user = { ...data, id };
        await this.db.insert('users', user);
        return user;
    }
}
"""

# Language splitter hiểu cấu trúc code, không cắt giữa function
chunks = python_splitter.split_text(typescript_code)
print(f"Code chunks: {len(chunks)}")
```

#### 1.3 Semantic Chunking — Advanced / cần eval

```python
# uv add langchain-experimental langchain-openai

from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

# WHY semantic chunking?
# Thay vì cắt theo ký tự/token, nó cắt khi "ý nghĩa thay đổi"
# Dùng cosine similarity giữa các sentences để quyết định chỗ tách
# Không mặc định tốt hơn recursive splitter: chậm hơn, tốn embedding,
# và cần benchmark trên corpus/query thật.

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

semantic_splitter = SemanticChunker(
    embeddings,
    # breakpoint_threshold_type:
    # "percentile" — cắt ở top X% similarity drops
    # "standard_deviation" — cắt khi drop > N standard deviations
    # "interquartile" — dùng IQR để detect outliers
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=95,  # Cắt ở top 5% thay đổi mạnh nhất
)

long_text = """
Machine learning là một nhánh của trí tuệ nhân tạo. Nó cho phép
máy tính học từ dữ liệu mà không cần được lập trình cụ thể.
Các thuật toán ML phổ biến bao gồm linear regression, decision trees,
và neural networks.

Ẩm thực Việt Nam nổi tiếng với sự đa dạng và hương vị đặc trưng.
Phở, bún bò Huế, bánh mì là những món ăn được yêu thích toàn thế giới.
Mỗi vùng miền có những đặc sản riêng biệt.

Python được tạo ra bởi Guido van Rossum vào năm 1991. Triết lý của
Python là code phải dễ đọc và rõ ràng. The Zen of Python (PEP 20)
tóm tắt các nguyên tắc thiết kế của ngôn ngữ này.
"""

# Semantic chunker sẽ tách 3 topic khác nhau này thành 3 chunks riêng
semantic_chunks = semantic_splitter.split_text(long_text)
print(f"Semantic chunks: {len(semantic_chunks)}")
for i, chunk in enumerate(semantic_chunks):
    print(f"\n--- Chunk {i+1} ---\n{chunk}")
```

#### 1.4 Hierarchical / Parent-Child Chunking

```python
# ParentDocumentRetriever là API classic/version-sensitive; smoke-test import theo version pin.
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryStore
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# WHY parent-child?
# Index small chunks (chính xác) nhưng retrieve large chunks (context đầy đủ)
# Giải quyết tension giữa precision và context

# Parent chunks — lớn, có đầy đủ context
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)

# Child chunks — nhỏ, chính xác cho embedding
child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)

# Vector store chỉ lưu child chunks
vectorstore = Chroma(
    collection_name="child_chunks",
    embedding_function=OpenAIEmbeddings()
)

# Doc store lưu parent chunks
docstore = InMemoryStore()

retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=docstore,
    child_splitter=child_splitter,
    parent_splitter=parent_splitter,
)

# Khi add documents:
# 1. Split thành parent chunks → lưu vào docstore
# 2. Split parent thành child chunks → lưu vào vectorstore
# 3. Child chunks có metadata trỏ về parent

docs = [
    Document(page_content=long_text, metadata={"source": "example.txt"})
]
retriever.add_documents(docs)

# Khi query:
# 1. Embed query → tìm child chunks gần nhất
# 2. Lookup parent chunks của những child chunks đó
# 3. Trả về parent chunks (context đầy đủ)
results = retriever.invoke("machine learning algorithms")
print(f"Retrieved {len(results)} parent chunks")
```

### Section 2: Hybrid Search — Dense + Sparse

**WHY hybrid search?**

Dense search (vector similarity) giỏi hiểu ngữ nghĩa: "laptop" và "notebook computer" là giống nhau. Nhưng nó yếu với proper nouns, codes, và technical terms: "GPT-4o" vs "GPT-4" có thể được coi là giống nhau.

Sparse search (BM25) giỏi exact matching: "error code 404" sẽ match chính xác documents có chứa "404". Nhưng nó không hiểu "car" và "automobile" là cùng nghĩa.

Hybrid search kết hợp cả hai: **semantic understanding + keyword precision**.

```python
# uv add rank_bm25 langchain-community

import numpy as np
from rank_bm25 import BM25Okapi
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from typing import List, Tuple
import re

class HybridSearcher:
    """
    Hybrid search kết hợp BM25 (sparse) và vector search (dense).
    Tương tự Elasticsearch hybrid search trong NodeJS stack.
    """

    def __init__(self, documents: List[Document], alpha: float = 0.5):
        """
        alpha: trọng số cho dense search (0=pure BM25, 1=pure dense)
        """
        self.documents = documents
        self.alpha = alpha
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

        # Setup BM25 (sparse)
        self._setup_bm25()

        # Setup vector store (dense)
        self._setup_vectorstore()

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer — lowercase và split theo whitespace/punctuation"""
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens

    def _setup_bm25(self):
        """Initialize BM25 index"""
        tokenized_corpus = [
            self._tokenize(doc.page_content)
            for doc in self.documents
        ]
        self.bm25 = BM25Okapi(tokenized_corpus)
        print(f"BM25 index created with {len(self.documents)} documents")

    def _setup_vectorstore(self):
        """Initialize Chroma vector store"""
        self.vectorstore = Chroma.from_documents(
            documents=self.documents,
            embedding=self.embeddings,
        )
        print(f"Vector store created with {len(self.documents)} documents")

    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Min-max normalization về [0, 1]"""
        min_score = scores.min()
        max_score = scores.max()
        if max_score == min_score:
            return np.ones_like(scores)
        return (scores - min_score) / (max_score - min_score)

    def search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """
        Hybrid search với Reciprocal Rank Fusion (RRF).
        RRF là technique phổ biến để kết hợp rankings từ nhiều sources.
        """
        # === BM25 Search ===
        query_tokens = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(query_tokens)
        bm25_normalized = self._normalize_scores(bm25_scores)

        # === Dense Vector Search ===
        # Lấy nhiều hơn để có đủ để rank
        dense_results = self.vectorstore.similarity_search_with_score(
            query, k=len(self.documents)
        )

        # Convert dense scores về numpy array theo thứ tự documents
        dense_scores = np.zeros(len(self.documents))
        for doc, score in dense_results:
            # Tìm index của document trong list gốc
            for i, orig_doc in enumerate(self.documents):
                if orig_doc.page_content == doc.page_content:
                    # Chroma trả về distance (thấp hơn = tốt hơn)
                    # Convert sang similarity score
                    dense_scores[i] = 1 - score
                    break

        dense_normalized = self._normalize_scores(dense_scores)

        # === Combine với weighted average ===
        # alpha=0.5: 50% dense + 50% BM25
        combined_scores = (
            self.alpha * dense_normalized +
            (1 - self.alpha) * bm25_normalized
        )

        # Rank theo combined score
        ranked_indices = np.argsort(combined_scores)[::-1][:k]

        results = []
        for idx in ranked_indices:
            results.append((
                self.documents[idx],
                float(combined_scores[idx])
            ))

        return results


# Demo sử dụng
sample_docs = [
    Document(page_content="Python là ngôn ngữ lập trình bậc cao với cú pháp đơn giản",
             metadata={"id": 1}),
    Document(page_content="Node.js cho phép chạy JavaScript phía server với event-driven architecture",
             metadata={"id": 2}),
    Document(page_content="TypeScript thêm static typing vào JavaScript, tương tự như Python type hints",
             metadata={"id": 3}),
    Document(page_content="FastAPI framework Python cho REST API, tương đương Express.js trong Node.js",
             metadata={"id": 4}),
    Document(page_content="Error 404 không tìm thấy resource, error 500 là server internal error",
             metadata={"id": 5}),
]

searcher = HybridSearcher(sample_docs, alpha=0.6)  # Nghiêng về dense search hơn

# Test 1: Semantic query — dense search sẽ giỏi hơn
print("\n=== Query: 'backend web framework' ===")
results = searcher.search("backend web framework", k=3)
for doc, score in results:
    print(f"Score: {score:.3f} | {doc.page_content[:60]}...")

# Test 2: Exact keyword — BM25 sẽ giỏi hơn
print("\n=== Query: 'error 404' ===")
results = searcher.search("error 404", k=3)
for doc, score in results:
    print(f"Score: {score:.3f} | {doc.page_content[:60]}...")
```

#### 2.1 Hybrid Search với LangChain EnsembleRetriever

```python
# EnsembleRetriever là API classic/version-sensitive; smoke-test import theo version pin.
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# BM25 Retriever (sparse)
bm25_retriever = BM25Retriever.from_documents(sample_docs)
bm25_retriever.k = 5  # Lấy top 5

# Vector Retriever (dense)
vectorstore = Chroma.from_documents(
    sample_docs,
    OpenAIEmbeddings(model="text-embedding-3-small")
)
dense_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Ensemble — tự động dùng Reciprocal Rank Fusion
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.4, 0.6],  # 40% BM25, 60% dense
)

# Sử dụng như bình thường
results = ensemble_retriever.invoke("Python web framework")
print(f"Ensemble results: {len(results)}")
for doc in results:
    print(f"- {doc.page_content[:80]}")
```

### Section 3: Re-ranking với Cross-Encoders

**WHY re-ranking?**

Bi-encoder (dùng trong vector search) encode query và document **độc lập** → nhanh nhưng kém chính xác. Cross-encoder đọc query VÀ document **cùng lúc** → chậm nhưng chính xác hơn nhiều.

Pattern phổ biến: dùng bi-encoder để lấy top-20/50/100 candidates (fast retrieval), rồi cross-encoder để re-rank và lấy top-5 (accurate ranking). Đây không phải default bắt buộc: re-ranker thêm latency/cost và đôi khi làm tệ hơn nếu model không hợp domain/ngôn ngữ. Luôn đo bằng retrieval eval trước/sau.

```python
# uv add sentence-transformers

from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from typing import List, Tuple
import numpy as np

class CrossEncoderReranker:
    """
    Re-ranker sử dụng cross-encoder model.
    Input: (query, document) pairs
    Output: relevance scores
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Các model cross-encoder phổ biến:
        - cross-encoder/ms-marco-MiniLM-L-6-v2: Nhanh, tốt cho general use
        - cross-encoder/ms-marco-electra-base: Chính xác hơn, chậm hơn
        - BAAI/bge-reranker-v2-m3: Multilingual, hỗ trợ tiếng Việt
        """
        print(f"Loading cross-encoder: {model_name}")
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """
        Re-rank documents theo query.

        Workflow:
        1. Tạo (query, doc) pairs
        2. Cross-encoder score tất cả pairs
        3. Sort theo score, lấy top_k
        """
        if not documents:
            return []

        # Tạo input pairs cho cross-encoder
        pairs = [(query, doc.page_content) for doc in documents]

        # Score tất cả pairs — cross-encoder xem CÙNG LÚC query và doc
        scores = self.model.predict(pairs)

        # Sort theo score (cao hơn = relevant hơn)
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return scored_docs[:top_k]

    def rerank_with_threshold(
        self,
        query: str,
        documents: List[Document],
        threshold: float = 0.5,
        top_k: int = 10
    ) -> List[Tuple[Document, float]]:
        """Re-rank và filter theo threshold score"""
        results = self.rerank(query, documents, top_k=top_k)
        return [(doc, score) for doc, score in results if score >= threshold]


# Demo: 2-stage retrieval pipeline
def two_stage_retrieval_pipeline(
    query: str,
    retriever,  # Stage 1: fast retrieval
    reranker: CrossEncoderReranker,  # Stage 2: accurate reranking
    initial_k: int = 20,  # Lấy nhiều ở stage 1
    final_k: int = 5,     # Chỉ giữ ít ở stage 2
) -> List[Document]:
    """
    2-stage retrieval: recall optimization → precision optimization

    Stage 1 (Retrieval): Maximize recall — lấy nhiều candidates
    Stage 2 (Re-ranking): Maximize precision — rank chính xác
    """
    # Stage 1: Fast retrieval — lấy top-20 candidates
    print(f"Stage 1: Retrieving top-{initial_k} candidates...")
    candidates = retriever.invoke(query)[:initial_k]
    print(f"  Got {len(candidates)} candidates")

    # Stage 2: Re-rank với cross-encoder
    print(f"Stage 2: Re-ranking to top-{final_k}...")
    reranked = reranker.rerank(query, candidates, top_k=final_k)
    print(f"  Final {len(reranked)} results")

    # Log score comparison
    print("\nRe-ranking results:")
    for i, (doc, score) in enumerate(reranked):
        print(f"  {i+1}. Score: {score:.4f} | {doc.page_content[:60]}...")

    return [doc for doc, _ in reranked]


# Sử dụng với LangChain
reranker = CrossEncoderReranker()

# Giả sử đã có retriever từ section trước
# final_docs = two_stage_retrieval_pipeline(
#     query="Python web framework comparison",
#     retriever=ensemble_retriever,
#     reranker=reranker,
# )
```

#### 3.1 Cohere Re-ranker (API-based option)

```python
# uv add cohere langchain-cohere

# ContextualCompressionRetriever là API classic/version-sensitive; smoke-test import theo version pin.
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import os

# Cohere re-ranker — dùng API, không cần GPU
# Có thể dùng production nếu latency/cost/data policy phù hợp.
# Chất lượng multilingual vẫn cần eval trên query tiếng Việt của bạn.
cohere_reranker = CohereRerank(
    model="rerank-multilingual-v3.0",  # Hỗ trợ tiếng Việt
    top_n=5,  # Chỉ giữ top 5 sau re-ranking
    cohere_api_key=os.getenv("COHERE_API_KEY"),
)

# Wrap retriever với compression (re-ranking là một dạng compression)
vectorstore = Chroma.from_documents(
    sample_docs,
    OpenAIEmbeddings(model="text-embedding-3-small")
)
base_retriever = vectorstore.as_retriever(search_kwargs={"k": 20})

# ContextualCompressionRetriever: retrieve nhiều, compress (re-rank) về ít
compression_retriever = ContextualCompressionRetriever(
    base_compressor=cohere_reranker,
    base_retriever=base_retriever,
)

# Sử dụng transparent — interface giống retriever thường
results = compression_retriever.invoke("Python vs NodeJS performance")
print(f"Re-ranked results: {len(results)}")
```

### Section 4: RAGAS — Đánh giá RAG Pipeline

**WHY cần evaluation framework?**

Không có evaluation = không biết RAG pipeline có hoạt động tốt không. Giống như deploy API mà không có monitoring — bạn chỉ biết lỗi khi user complaint.

RAGAS đo 4 metrics chính:

| Metric | Đo gì | Range |
|--------|-------|-------|
| Faithfulness | Answer có supported bởi context không? | 0-1 |
| Answer Relevancy | Answer có relevant với question không? | 0-1 |
| Context Precision | Context có chứa info cần thiết không? | 0-1 |
| Context Recall | Context có bỏ sót info quan trọng không? | 0-1 |

```python
# uv add ragas datasets langchain-openai

from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)
from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# Chuẩn bị test dataset.
# RAGAS schema có thể đổi tên cột giữa versions; nếu version pin yêu cầu
# user_input/response/retrieved_contexts/reference, map 4 cột dưới đây tương ứng:
# question -> user_input, answer -> response, contexts -> retrieved_contexts,
# ground_truth -> reference.
# Trong production: tạo từ domain experts hoặc dùng LLM để generate
test_data = {
    "question": [
        "Python được tạo ra bởi ai và khi nào?",
        "FastAPI có ưu điểm gì so với Flask?",
        "Làm thế nào để xử lý async trong Python?",
    ],
    "answer": [
        # Đây là answers từ RAG pipeline của bạn
        "Python được tạo ra bởi Guido van Rossum vào năm 1991.",
        "FastAPI nhanh hơn Flask, có auto-documentation, và hỗ trợ async native.",
        "Python dùng asyncio với async/await keywords, tương tự Node.js.",
    ],
    "contexts": [
        # Contexts được retrieved bởi RAG
        [
            "Python là ngôn ngữ lập trình do Guido van Rossum tạo ra năm 1991.",
            "Python 2.0 ra mắt năm 2000, Python 3.0 ra mắt năm 2008.",
        ],
        [
            "FastAPI là modern web framework, nhanh hơn Flask và Django REST.",
            "FastAPI tự động generate OpenAPI docs, hỗ trợ async/await native.",
            "Pydantic validation tích hợp sẵn trong FastAPI.",
        ],
        [
            "Python asyncio library cho phép viết concurrent code dùng async/await.",
            "Async functions trong Python tương tự Promise/async-await trong JavaScript.",
        ],
    ],
    "ground_truth": [
        # Ground truth answers — cần cho context_recall
        "Python được tạo ra bởi Guido van Rossum và ra mắt lần đầu năm 1991.",
        "FastAPI nhanh hơn Flask nhờ Starlette, có tự động tạo API docs, type checking với Pydantic, và hỗ trợ async native.",
        "Python xử lý async thông qua asyncio library với cú pháp async/await, event loop quản lý coroutines.",
    ],
}

dataset = Dataset.from_dict(test_data)

evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))

# Chạy evaluation
# RAGAS dùng LLM để evaluate; dùng model rẻ cho regression suite, model mạnh hơn
# cho audit quan trọng. Scores là tín hiệu tương đối, không phải chân lý tuyệt đối.
result = evaluate(
    dataset=dataset,
    metrics=[
        Faithfulness(llm=evaluator_llm),        # Answer có hallucinate không?
        AnswerRelevancy(llm=evaluator_llm),     # Answer có trả lời đúng câu hỏi không?
        ContextPrecision(llm=evaluator_llm),    # Context retrieved có chính xác không?
        ContextRecall(llm=evaluator_llm),       # Context có đủ thông tin không?
    ],
    embeddings=OpenAIEmbeddings(model="text-embedding-3-small"),
)

print("\n=== RAGAS Evaluation Results ===")
print(f"Faithfulness:      {result['faithfulness']:.3f}")
print(f"Answer Relevancy:  {result['answer_relevancy']:.3f}")
print(f"Context Precision: {result['context_precision']:.3f}")
print(f"Context Recall:    {result['context_recall']:.3f}")

# Convert sang pandas DataFrame để analysis
df = result.to_pandas()
print("\nPer-question breakdown:")
print(df[['question', 'faithfulness', 'answer_relevancy']].to_string())
```

#### 4.1 Custom Evaluation Pipeline

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List
import json

class EvaluationResult(BaseModel):
    score: float = Field(ge=0, le=1, description="Score từ 0 đến 1")
    reasoning: str = Field(description="Giải thích tại sao cho score này")
    issues: List[str] = Field(default=[], description="Các vấn đề phát hiện được")

class RAGEvaluator:
    """Custom evaluator khi không muốn dùng RAGAS (cost hoặc customization)"""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def evaluate_faithfulness(
        self,
        answer: str,
        contexts: List[str]
    ) -> EvaluationResult:
        """
        Kiểm tra: Answer có chứa thông tin KHÔNG có trong context không?
        (Hallucination detection)
        """
        context_str = "\n".join(f"[{i+1}] {ctx}" for i, ctx in enumerate(contexts))

        prompt = ChatPromptTemplate.from_template("""
Bạn là evaluator cho RAG system. Hãy đánh giá xem câu trả lời có faithful với context không.

CONTEXT:
{context}

ANSWER:
{answer}

Đánh giá: Mỗi claim trong Answer có được support bởi Context không?
- Score 1.0: Tất cả claims đều có trong context
- Score 0.5: Một số claims không có trong context
- Score 0.0: Answer chứa nhiều thông tin không có trong context (hallucination)

Trả về JSON với format:
{{"score": <0-1>, "reasoning": "<giải thích>", "issues": ["<vấn đề 1>", "..."]}}
""")

        response = self.llm.invoke(
            prompt.format(context=context_str, answer=answer)
        )

        result_dict = json.loads(response.content)
        return EvaluationResult(**result_dict)

    def evaluate_batch(self, test_cases: List[dict]) -> dict:
        """Evaluate nhiều test cases và tổng hợp kết quả"""
        all_scores = []

        for case in test_cases:
            result = self.evaluate_faithfulness(
                case["answer"],
                case["contexts"]
            )
            all_scores.append(result.score)

            if result.score < 0.7:
                print(f"⚠️  Low faithfulness ({result.score:.2f})")
                print(f"   Q: {case['question'][:50]}...")
                print(f"   Issues: {result.issues}")

        return {
            "mean_faithfulness": sum(all_scores) / len(all_scores),
            "min_faithfulness": min(all_scores),
            "low_quality_cases": sum(1 for s in all_scores if s < 0.7),
        }
```

### Section 5: Common RAG Failure Modes

**WHY cần biết failure modes?**

Hiểu failure modes = biết cách debug khi RAG cho kết quả tệ. Giống như biết các anti-patterns trong NodeJS (callback hell, blocking event loop) giúp bạn debug nhanh hơn.

#### Failure Mode 1: Poor Retrieval (The Most Common)

```python
# Triệu chứng: Context retrieved không relevant với question
# Nguyên nhân thường gặp:

# 1. Chunk size quá lớn hoặc quá nhỏ
# 2. Embedding model không phù hợp với domain
# 3. Question và document dùng vocabulary khác nhau

# FIX: Query expansion — tạo nhiều versions của query
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

def expand_query(query: str, n_variations: int = 3) -> List[str]:
    """
    Tạo nhiều phiên bản của query để improve retrieval.
    Technique: HyDE (Hypothetical Document Embeddings) hoặc Query Rewriting
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    prompt = ChatPromptTemplate.from_template("""
Hãy tạo {n} phiên bản khác nhau của câu hỏi sau để improve document retrieval.
Mỗi phiên bản nên dùng cách diễn đạt khác nhau nhưng cùng ý nghĩa.

Câu hỏi gốc: {query}

Trả về {n} câu hỏi, mỗi câu một dòng, không đánh số.
""")

    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"query": query, "n": n_variations})

    variations = result.strip().split("\n")
    return [query] + [v.strip() for v in variations if v.strip()]

# Sử dụng: multi-query retrieval
def multi_query_retrieve(query: str, retriever, k: int = 5):
    """Retrieve với nhiều query variations, deduplicate kết quả"""
    queries = expand_query(query, n_variations=3)

    all_docs = []
    seen_content = set()

    for q in queries:
        docs = retriever.invoke(q)
        for doc in docs:
            content_hash = hash(doc.page_content)
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                all_docs.append(doc)

    print(f"Multi-query: {len(queries)} queries → {len(all_docs)} unique docs")
    return all_docs[:k]
```

#### Failure Mode 2: Context Window Stuffing

```python
# Triệu chứng: LLM ignore một số context vì quá nhiều text
# "Lost in the middle" problem — LLM nhớ đầu và cuối, quên giữa

# FIX: Reorder documents — đặt relevant nhất ở đầu và cuối
from langchain_community.document_transformers import LongContextReorder

def fix_lost_in_middle(documents: List[Document]) -> List[Document]:
    """
    Reorder: đặt least relevant ở giữa, most relevant ở đầu và cuối.
    LLM attention map có hình chữ U — đầu và cuối được chú ý hơn.
    """
    reordering = LongContextReorder()
    return reordering.transform_documents(documents)

# FIX: Selective context — chỉ giữ câu relevant
from langchain.retrievers.document_compressors import LLMChainExtractor  # version-sensitive
from langchain.retrievers import ContextualCompressionRetriever  # version-sensitive

def create_selective_retriever(base_retriever, llm):
    """
    Compressor: extract chỉ phần relevant trong mỗi document.
    Giảm noise, tăng signal.
    """
    compressor = LLMChainExtractor.from_llm(llm)
    return ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever,
    )
```

#### Failure Mode 3: Hallucination

```python
# Triệu chứng: LLM trả lời câu hỏi dù context không có đủ thông tin
# LLM "tự sáng tạo" thông tin

# FIX: Strict grounding prompt
STRICT_RAG_PROMPT = """Bạn là assistant chỉ trả lời dựa trên context được cung cấp.

CONTEXT:
{context}

RULES:
1. CHỈ dùng thông tin từ context trên
2. Nếu context không có đủ thông tin, nói "Tôi không tìm thấy thông tin này trong tài liệu"
3. KHÔNG tự thêm thông tin từ training data
4. Trích dẫn nguồn khi có thể

CÂU HỎI: {question}

TRẢ LỜI:"""

# FIX: Citation-based answers
CITATION_PROMPT = """Dựa trên các đoạn tài liệu sau, hãy trả lời câu hỏi.
Mỗi claim phải được trích dẫn từ tài liệu cụ thể.

{context}

Câu hỏi: {question}

Format trả lời:
[Câu trả lời với citations như [1], [2], ...]

Nguồn:
[1] <quote từ tài liệu>
[2] <quote từ tài liệu>
"""
```

#### Failure Mode 4: Stale/Outdated Information

```python
# Triệu chứng: RAG trả lời dựa trên tài liệu cũ

# FIX: Metadata filtering theo date
from langchain_chroma import Chroma
from datetime import datetime, timedelta

vectorstore = Chroma(embedding_function=OpenAIEmbeddings())

# Thêm date metadata khi index
def index_with_date(docs: List[Document], vectorstore):
    """Thêm timestamp vào metadata"""
    for doc in docs:
        doc.metadata["indexed_at"] = datetime.now().isoformat()
        doc.metadata["source_date"] = doc.metadata.get("date", "unknown")
    vectorstore.add_documents(docs)

# Filter khi search
def search_recent_docs(
    query: str,
    vectorstore,
    days_limit: int = 30
) -> List[Document]:
    """Chỉ search documents trong N ngày gần nhất"""
    cutoff_date = (datetime.now() - timedelta(days=days_limit)).isoformat()

    # Chroma filter syntax
    results = vectorstore.similarity_search(
        query,
        k=5,
        filter={"indexed_at": {"$gte": cutoff_date}}
    )
    return results
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Chunk size quá nhỏ (<100 tokens) | Mất context, embedding kém | Dùng 256-512 tokens + overlap 10-20% |
| Chunk size quá lớn (>2000 tokens) | Embedding "diluted", retrieval kém chính xác | Test với 512-1024 tokens trước |
| Không có chunk overlap | Thông tin bị cắt giữa ranh giới | Overlap 10-20% chunk size |
| Chỉ dùng dense search mà không đo keyword queries | Có thể miss exact keyword matches | Thử hybrid search và so sánh Precision/Recall |
| Thêm re-rank mà không đo latency/quality | Tốn tiền/chậm hơn, có thể không tăng chất lượng | A/B evaluate trước khi bật mặc định |
| Không có evaluation | Không biết pipeline có tốt không | Setup RAGAS hoặc custom eval từ đầu dự án |
| Embed toàn bộ document cùng lúc | Token limit exceeded, kém chính xác | Parent-child chunking |
| Prompt không có grounding instruction | LLM hallucinate | Thêm explicit "only use provided context" |

## ✅ Best Practices

- **Chunk size baseline:** 512 tokens với 10% overlap là điểm bắt đầu hợp lý, không phải default tốt nhất cho mọi corpus.
- **Dùng semantic chunking cho unstructured text:** Blog posts, articles — nơi topic thay đổi không đều.
- **Dùng recursive splitter cho structured text:** Docs có headings, code — cấu trúc rõ ràng hơn.
- **Alpha cho hybrid search:** Bắt đầu với 0.5 rồi tune bằng eval; query keyword-heavy và semantic-heavy thường cần trọng số khác nhau.
- **Re-ranking threshold:** Score threshold phụ thuộc model/range calibration; đừng copy `0.3` nếu chưa plot distribution trên validation set.
- **RAGAS evaluation frequency:** Chạy sau mỗi lần thay đổi chunking hoặc retrieval strategy.
- **Metadata là vũ khí bí mật:** Source, date, section, document type — filter metadata nhanh hơn semantic search.
- **Cache embeddings:** Embedding computation tốn kém — cache kết quả để tránh recompute.

## ⚖️ Trade-offs

| Approach | Pros | Cons | Khi nào dùng |
|----------|------|------|--------------|
| Fixed chunking | Đơn giản, nhanh | Cắt giữa context | Prototype nhanh |
| Semantic chunking | Có thể tốt hơn trên text topic-shift | Cần embedding, chậm, dễ overfit heuristic | Khi recursive splitter fail và eval chứng minh cải thiện |
| Parent-child | Balance precision/context | Phức tạp hơn | Documents dài |
| Dense-only search | Đơn giản | Miss keyword matches | General semantic queries |
| Sparse-only (BM25) | Nhanh, keyword chính xác | Không hiểu ngữ nghĩa | Exact search |
| Hybrid search | Có thể tăng recall cho mix semantic + keyword | Cần tune alpha/RRF, có thể thêm latency | Khi eval cho thấy dense-only/BM25-only thiếu |
| Local re-ranker | Free, offline | Cần GPU/RAM | Self-hosted setup |
| Cohere re-ranker | Managed API, không cần GPU | Tốn tiền, latency, data leaves infra | Cloud production nếu policy cho phép |

## 🚀 Performance Notes

- **Embedding caching:** Dùng cache-backed embeddings hoặc Redis/file cache để tránh re-embed unchanged text; savings phụ thuộc tỷ lệ document unchanged.
- **Batch embedding:** Gửi nhiều texts cùng lúc thay vì từng cái một; kiểm tra batch size/rate limit theo provider và model đang dùng.
- **Async retrieval:** Dùng async APIs khi retriever/vector store support; tên method có thể khác theo integration/version.
- **FAISS vs Chroma:** FAISS có thể nhanh hơn cho large local ANN workloads, nhưng khác hẳn về persistence, filters, ops, và API surface.
- **Pre-filter với metadata:** Filter theo metadata trước khi vector search → giảm search space → nhanh hơn.
- **Re-ranker batch size:** Cross-encoder có thể process 32-64 pairs cùng lúc — dùng batch inference.
- **Quantization:** Int8 quantization có thể giảm memory đáng kể, nhưng accuracy loss phụ thuộc model/dataset; benchmark trước khi dùng.

## 📝 Tóm tắt

- **Chunking strategy quan trọng:** Bắt đầu với recursive splitter (512 tokens, 10% overlap), chỉ upgrade sang semantic chunking khi eval cho thấy lợi ích
- **Hybrid search là candidate mạnh:** Kết hợp BM25 (keyword) + dense vector (semantic) thường đáng thử, nhưng không luôn tốt hơn từng phương pháp riêng lẻ
- **2-stage retrieval là pattern phổ biến:** Retrieve nhiều (top-20-50) với bi-encoder, re-rank top-k với cross-encoder nếu latency/cost chấp nhận được
- **RAGAS 4 metrics cần theo dõi:** Faithfulness (no hallucination), Answer Relevancy, Context Precision, Context Recall
- **Failure mode phổ biến:** Poor retrieval do vocabulary mismatch → thử query expansion/hybrid search, rồi validate bằng eval set
- **Metadata filtering là optimization cực mạnh:** Filter trước, search sau — giảm search space và tăng relevance
- **Parent-child chunking:** Index nhỏ, retrieve lớn — giải quyết tension giữa embedding precision và LLM context quality
