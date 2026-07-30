# Day 37: Reranking Cho Production RAG

## 1. Reranking giải quyết vấn đề gì?

Trong Day 36, pipeline Hybrid Search đã lấy candidate bằng BM25, dense retrieval và Reciprocal Rank Fusion. Bước đó tối ưu cho recall: cố gắng không bỏ sót chunk có khả năng liên quan. Nhưng top result của retriever không luôn là context tốt nhất cho LLM.

Các lỗi thường gặp khi chỉ dùng retrieval top-k:

- Dense retrieval hiểu ý nghĩa tổng quát nhưng có thể bỏ qua phủ định, điều kiện, version hoặc tên riêng.
- BM25 bắt đúng keyword nhưng có thể đưa lên cao đoạn chỉ nhắc từ khóa, không trả lời câu hỏi.
- RRF merge nhiều nguồn tốt cho recall nhưng thứ tự sau merge vẫn còn nhiễu.
- Chunk gần giống nhau làm top-k bị trùng, khiến context thiếu đa dạng.
- Query tiếng Việt trộn English, acronym, mã lỗi hoặc tên sản phẩm làm embedding khó xếp đúng.

Reranker nhận từng cặp:

```text
(query, candidate_chunk) -> relevance_score
```

Sau đó hệ thống sắp xếp lại candidate và chỉ lấy top nhỏ hơn để đưa vào prompt.

Mental model:

```text
Retriever: tìm rộng để không bỏ sót.
Reranker: chấm đắt hơn nhưng chính xác hơn trên tập candidate nhỏ.
Context builder: lấy vài chunk tốt nhất, giữ citation và giới hạn token.
```

Điểm quan trọng: reranker không cứu được chunk không nằm trong candidate pool. Nếu retrieve top 50 không có chunk đúng, rerank top 50 cũng không thể tạo ra chunk đúng. Vì vậy production pattern thường là retrieve rộng trước, sau đó rerank hẹp.

## 2. Bi-encoder vs cross-encoder

Bi-encoder encode query và document riêng biệt:

```text
query -> embedding_q
doc   -> embedding_d
score = similarity(embedding_q, embedding_d)
```

Ưu điểm là document embedding có thể tính offline và lưu trong Vector DB. Query runtime chỉ cần embed query rồi search nhanh. Nhược điểm là query và document không tương tác token-by-token khi chấm điểm, nên ranking có thể sai ở các câu hỏi cần hiểu chi tiết.

Cross-encoder encode query và document cùng lúc:

```text
[query, doc] -> transformer -> relevance_score
```

Ưu điểm là model nhìn thấy tương tác giữa từng token của query và chunk, nên thường xếp hạng chính xác hơn. Nhược điểm là không thể precompute score cho mọi query-doc pair. Nếu có 100 candidate, cross-encoder phải chạy 100 cặp ở runtime.

| Cách làm | Dùng cho | Ưu điểm | Nhược điểm | Production note |
|---|---|---|---|---|
| Bi-encoder | First-stage retrieval | Nhanh, index được offline, scale tốt | Ranking chưa đủ tinh | Default cho dense retrieval |
| Cross-encoder | Second-stage reranking | Top-k precision tốt | Latency/cost tăng theo số candidate | Rerank top 20-100, không rerank toàn corpus |
| Late-interaction | Search/rerank chất lượng cao | Giữ token-level matching tốt hơn bi-encoder | Serving/index phức tạp | Phù hợp team search mạnh |
| LLM rerank | Query đặc biệt phức tạp | Linh hoạt, có thể giải thích | Đắt, chậm, khó deterministic | Dùng có chọn lọc hoặc offline analysis |

Rule thực dụng: dùng bi-encoder để retrieve, dùng cross-encoder để rerank.

## 3. Reranker là gì?

Reranker là một model hoặc service nhận query và danh sách candidate, trả về relevance score hoặc danh sách đã sắp xếp.

Input tốt cho reranker không chỉ là `chunk.text`. Nó nên chứa đủ ngữ cảnh ngắn:

- `title` của tài liệu.
- `section_path` hoặc heading.
- Nội dung chunk đã cắt vừa token budget.
- `source_type`, `document_version`, `effective_date` nếu domain phụ thuộc version.
- `page_start`, `page_end`, `chunk_id` để giữ citation.

Ví dụ format text đưa vào reranker:

```text
Title: Chính sách nghỉ phép 2026
Section: HR > Leave Policy > Annual Leave
Version: 2026-01
Text: Nhân viên full-time có 12 ngày nghỉ phép năm...
```

Không nên đưa cả document dài vào reranker. Tài liệu dài sẽ bị truncate, tăng latency và có thể làm mất đúng phần chứa đáp án. Chunking tốt từ Day 35 vẫn rất quan trọng.

## 4. BGE reranker

BGE reranker là nhóm reranker open-source từ BAAI, thường dùng như cross-encoder cho search/RAG. Với dữ liệu tiếng Việt hoặc multilingual, một lựa chọn thực tế là `BAAI/bge-reranker-v2-m3` vì model này hỗ trợ multilingual và có thể chạy self-host.

Ưu điểm:

- Không gửi dữ liệu ra managed API nếu self-host.
- Có thể batch inference để tối ưu throughput.
- Có thể fine-tune trên query/document domain riêng khi có dữ liệu.
- Phù hợp để học và để xây baseline nội bộ.

Nhược điểm:

- Cần CPU/GPU serving, autoscale, monitoring và model lifecycle.
- Latency tăng theo `candidate_count * chunk_length`.
- Cần kiểm tra license, hardware và khả năng vận hành trước production.

Ví dụ dùng `sentence-transformers`:

```python
from sentence_transformers import CrossEncoder

model = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)

query = "Nhân viên full-time được nghỉ phép bao nhiêu ngày trong năm 2026?"
passages = [
    "Title: Chính sách nghỉ phép 2026\nText: Nhân viên full-time có 12 ngày nghỉ phép năm.",
    "Title: Quy định bảo mật\nText: Nhân viên phải đổi mật khẩu mỗi 90 ngày.",
]

scores = model.predict([(query, passage) for passage in passages])
```

Trong production, đoạn trên nên được bọc trong service có batching, timeout, circuit breaker, metric và model version.

## 5. Cohere Rerank concept

Cohere Rerank là managed rerank API. Thay vì tự host model, hệ thống gửi query và documents lên API, nhận về relevance score cùng thứ tự kết quả.

Ưu điểm:

- Ship nhanh, ít vận hành model serving.
- API đã có batching, model hosting, scaling.
- Dễ dùng để tạo baseline chất lượng trước khi quyết định self-host.

Nhược điểm:

- Có network latency và rate limit.
- Cost tăng theo số request, số document và độ dài document.
- Cần đánh giá data privacy, PII, data residency và hợp đồng xử lý dữ liệu.
- Vendor/model version thay đổi có thể làm score distribution đổi.

Ví dụ concept với Python SDK:

```python
import os

import cohere

co = cohere.Client(token=os.environ["CO_API_KEY"])

response = co.v2.rerank(
    model="rerank-v4.0-pro",
    query="Nhân viên full-time được nghỉ phép bao nhiêu ngày?",
    documents=[
        "Title: Chính sách nghỉ phép\nText: Nhân viên full-time có 12 ngày nghỉ phép năm.",
        "Title: Chính sách bảo mật\nText: Không chia sẻ mật khẩu cho người khác.",
    ],
    top_n=2,
)

for item in response.results:
    print(item.index, item.relevance_score)
```

Trong hệ thống thật, không hard-code model. Hãy đưa model name, `top_n`, timeout và `max_tokens_per_doc` vào config.

## 6. Two-stage retrieval

Pipeline production hợp lý sau Day 36:

```text
user query
  -> normalize query
  -> build mandatory tenant/ACL/deleted/index filters
  -> BM25 top 50 + vector top 50, mỗi path đều áp dụng filters
  -> merge bằng RRF
  -> defense-in-depth permission assertion
  -> dedupe theo document_id/chunk_id/text_hash
  -> truncate text theo max tokens per doc
  -> rerank top 50 hoặc top 100
  -> lấy top 5-10
  -> context builder giữ citation
  -> LLM answer
```

Thứ tự ACL rất quan trọng. Filter quyền phải chạy trước rerank và trước khi gửi sang managed API. Nếu candidate không đúng quyền được gửi vào prompt hoặc ra API ngoài, dữ liệu đã bị leak.

Candidate sizing:

| Cấu hình | Khi phù hợp | Rủi ro |
|---|---|---|
| Retrieve top 20 -> rerank top 5 | Corpus nhỏ, SLA rất chặt | Dễ bỏ sót chunk đúng |
| Retrieve top 50 -> rerank top 5/8 | Default tốt cho nhiều RAG nội bộ | Vẫn cần đo Recall@50 |
| Retrieve top 100 -> rerank top 10 | Cần recall cao, query đa dạng, corpus nhiều nhiễu | Latency/cost tăng |
| Retrieve top 200+ -> rerank top 10 | Chỉ dùng khi đã chứng minh cần | Có thể quá đắt, p95 xấu |

Default thực dụng cho bài học: BM25 top 50, vector top 50, RRF merge, dedupe còn khoảng 50-100 candidate, rerank lấy top 5-10.

## 7. Latency và cost trade-off

Reranker nằm trước bước LLM generation, nên nó ảnh hưởng trực tiếp tới time-to-first-token.

Các yếu tố làm latency tăng:

- Số candidate rerank.
- Độ dài chunk sau khi format.
- Model size.
- CPU vs GPU.
- Batch size và queue time.
- Managed API network latency, rate limit và retry.

Trade-off quan trọng:

| Quyết định | Quality | Latency | Cost | Ghi chú |
|---|---:|---:|---:|---|
| Không rerank | Thấp đến vừa | Tốt | Thấp | Chỉ ổn nếu eval chứng minh top-k đã đủ |
| Rerank top 20 | Vừa | Tốt | Vừa | Phù hợp SLA chặt |
| Rerank top 50 | Tốt | Vừa | Vừa | Default nên thử |
| Rerank top 100 | Tốt hơn nếu retrieval recall cao | Chậm hơn | Cao hơn | Cần benchmark p95 |
| Self-host BGE | Tốt nếu vận hành ổn | Phụ thuộc hardware | Predictable hơn ở scale | Cần GPU/CPU serving |
| Cohere Rerank | Tốt, ship nhanh | Có network latency | Pay-per-use | Cần review privacy |

Kỹ thuật giảm latency:

- Dedupe trước rerank.
- Cắt text theo heading/sentence boundary và giới hạn `max_chars` hoặc `max_tokens_per_doc`.
- Batch candidate pairs.
- Cache với query normalize nếu không chứa PII và dữ liệu không quá volatile.
- Timeout reranker và fallback về RRF rank.
- Chỉ rerank khi query cần độ chính xác cao, ví dụ policy/legal/support.
- Dùng model nhỏ hơn cho traffic thường, model mạnh hơn cho query có risk cao.

## 8. Evaluation: Recall@k và MRR

Reranking nên được đo bằng query set có ground truth, không đo bằng cảm giác.

Một eval item tối thiểu:

```json
{
  "query_id": "q001",
  "query": "Nhân viên full-time có bao nhiêu ngày nghỉ phép năm 2026?",
  "relevant_chunk_ids": ["hr_leave_2026:chunk_003"]
}
```

Các metric:

| Metric | Dùng để đo | Cách đọc |
|---|---|---|
| Recall@50 before rerank | Candidate pool có chứa chunk đúng không | Thấp thì sửa retrieval/chunking trước |
| Recall@5 after rerank | Context cuối có chứa chunk đúng không | Cao hơn nghĩa là rerank giúp top context |
| MRR@10 | Chunk đúng đầu tiên lên gần đầu không | Tốt cho câu hỏi có một đáp án chính |
| nDCG@10 | Ranking nhiều mức relevance có tốt không | Tốt khi qrels có điểm 0/1/2/3 |
| Context precision | Context đưa vào prompt ít noise không | Liên quan trực tiếp đến faithfulness |
| p50/p95/p99 latency | Có đạt SLA không | Luôn đo riêng search, rerank, LLM |

Nếu Recall@50 thấp, reranker không phải giải pháp chính. Cần xem lại chunking, query normalization, BM25, embedding model, metadata filter hoặc RRF.

## 9. Code Python gần production

Ví dụ dưới đây tập trung vào layer reranking. Hàm `hybrid_retrieve` được giả định đến từ pipeline Day 36.

```python
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccessContext:
    tenant_id: str
    roles: frozenset[str]


@dataclass(frozen=True)
class CandidateChunk:
    id: str
    document_id: str
    chunk_id: str
    tenant_id: str
    acl_roles: frozenset[str]
    title: str
    section_path: tuple[str, ...]
    text: str
    source_uri: str
    page_start: int | None
    page_end: int | None
    retrieval_score: float
    retrieval_rank: int
    retriever: str

    def text_for_reranker(self, max_chars: int = 2_500) -> str:
        section = " > ".join(self.section_path)
        body = self.text[:max_chars]
        return (
            f"Title: {self.title}\n"
            f"Section: {section}\n"
            f"Source: {self.source_uri}\n"
            f"Text: {body}"
        )


@dataclass(frozen=True)
class RankedChunk:
    chunk: CandidateChunk
    rerank_score: float
    final_rank: int


class Reranker(Protocol):
    name: str
    model_version: str

    def score(self, query: str, candidates: Sequence[CandidateChunk]) -> list[float]:
        """Return one relevance score per candidate, same order as input."""


class BgeCrossEncoderReranker:
    name = "bge-cross-encoder"

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        max_length: int = 512,
        device: str | None = None,
    ) -> None:
        from sentence_transformers import CrossEncoder

        self.model_version = model_name
        self.model = CrossEncoder(model_name, max_length=max_length, device=device)

    def score(self, query: str, candidates: Sequence[CandidateChunk]) -> list[float]:
        pairs = [(query, candidate.text_for_reranker()) for candidate in candidates]
        scores = self.model.predict(pairs)
        return [float(score) for score in scores]


class CohereReranker:
    name = "cohere-rerank"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "rerank-v4.0-pro",
        max_tokens_per_doc: int = 1_200,
    ) -> None:
        import cohere

        self.model_version = model
        self.client = cohere.Client(token=api_key or os.environ["CO_API_KEY"])
        self.max_tokens_per_doc = max_tokens_per_doc

    def score(self, query: str, candidates: Sequence[CandidateChunk]) -> list[float]:
        documents = [candidate.text_for_reranker() for candidate in candidates]
        response = self.client.v2.rerank(
            model=self.model_version,
            query=query,
            documents=documents,
            top_n=len(documents),
            max_tokens_per_doc=self.max_tokens_per_doc,
        )

        scores = [float("-inf")] * len(candidates)
        for result in response.results:
            scores[result.index] = float(result.relevance_score)
        return scores


HybridRetrieveFn = Callable[
    [str, AccessContext, int],
    list[CandidateChunk],
]


def has_access(candidate: CandidateChunk, access: AccessContext) -> bool:
    if candidate.tenant_id != access.tenant_id:
        return False
    return bool(candidate.acl_roles & access.roles)


def dedupe_candidates(candidates: Sequence[CandidateChunk]) -> list[CandidateChunk]:
    best_by_chunk: dict[str, CandidateChunk] = {}
    for candidate in candidates:
        previous = best_by_chunk.get(candidate.id)
        if previous is None or candidate.retrieval_score > previous.retrieval_score:
            best_by_chunk[candidate.id] = candidate

    return sorted(
        best_by_chunk.values(),
        key=lambda item: (item.retrieval_rank, -item.retrieval_score),
    )


def fallback_rank(candidates: Sequence[CandidateChunk], final_k: int) -> list[RankedChunk]:
    return [
        RankedChunk(chunk=candidate, rerank_score=float("nan"), final_rank=index + 1)
        for index, candidate in enumerate(candidates[:final_k])
    ]


def retrieve_then_rerank(
    *,
    query: str,
    access: AccessContext,
    hybrid_retrieve: HybridRetrieveFn,
    reranker: Reranker,
    retrieve_k: int = 100,
    rerank_k: int = 50,
    final_k: int = 8,
    rerank_slo_ms: int = 800,
) -> list[RankedChunk]:
    raw_candidates = hybrid_retrieve(query, access, retrieve_k)
    permitted = [item for item in raw_candidates if has_access(item, access)]
    deduped = dedupe_candidates(permitted)
    rerank_input = deduped[:rerank_k]

    if not rerank_input:
        return []

    rerank_started = time.perf_counter()
    try:
        scores = reranker.score(query, rerank_input)
    except Exception:
        logger.exception(
            "reranker_failed",
            extra={
                "reranker": reranker.name,
                "model_version": reranker.model_version,
                "retrieve_k": retrieve_k,
                "rerank_k": rerank_k,
            },
        )
        return fallback_rank(rerank_input, final_k)

    rerank_elapsed_ms = (time.perf_counter() - rerank_started) * 1000
    if rerank_elapsed_ms > rerank_slo_ms:
        logger.warning(
            "reranker_slow",
            extra={
                "elapsed_ms": round(rerank_elapsed_ms, 2),
                "slo_ms": rerank_slo_ms,
                "reranker": reranker.name,
            },
        )
        return fallback_rank(rerank_input, final_k)

    ranked_pairs = sorted(
        zip(rerank_input, scores, strict=True),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        RankedChunk(chunk=chunk, rerank_score=float(score), final_rank=index + 1)
        for index, (chunk, score) in enumerate(ranked_pairs[:final_k])
    ]
```

Production note cho code trên:

- `hybrid_retrieve` nhận `AccessContext` và phải filter `tenant_id`, ACL, `deleted_at`, `index_version` trong từng database/search-engine query. `has_access` phía sau chỉ là defense-in-depth, không thay thế pre-filter.
- Reranker không được nhận candidate chưa qua ACL.
- `rerank_slo_ms` trong skeleton chỉ phát hiện request chậm sau khi sync call kết thúc; nó không cancel inference. Với self-host BGE, nên expose qua service riêng hoặc chạy qua worker có `asyncio.wait_for`/client timeout để có timeout thực sự, batching và autoscale.
- Với managed API, đặt timeout/retry/circuit breaker ở HTTP client hoặc SDK layer.
- Log cần có `query_id`, `candidate_count`, `reranker_model`, `before_rank`, `after_rank`, latency và fallback flag.

## 10. Evaluation code

```python
from collections.abc import Iterable


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    retrieved = set(ranked_ids[:k])
    return len(retrieved & relevant_ids) / len(relevant_ids)


def mrr_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> float:
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def evaluate_ranker(
    run: dict[str, list[str]],
    qrels: dict[str, set[str]],
    recall_k: int = 5,
    mrr_k: int = 10,
) -> dict[str, float]:
    recall_scores = []
    mrr_scores = []

    for query_id, relevant_ids in qrels.items():
        ranked_ids = run.get(query_id, [])
        recall_scores.append(recall_at_k(ranked_ids, relevant_ids, recall_k))
        mrr_scores.append(mrr_at_k(ranked_ids, relevant_ids, mrr_k))

    total = max(len(qrels), 1)
    return {
        f"Recall@{recall_k}": sum(recall_scores) / total,
        f"MRR@{mrr_k}": sum(mrr_scores) / total,
    }
```

Cách chạy eval đúng:

1. Tạo baseline `hybrid_only_run`: danh sách `chunk_id` sau RRF, chưa rerank.
2. Tạo `hybrid_rerank_run`: danh sách `chunk_id` sau rerank.
3. So sánh Recall@5, MRR@10 và latency cùng query set.
4. Tách query theo tag: keyword-heavy, semantic, acronym, no-diacritic, policy version, tiếng Việt/English mix.
5. Đọc ít nhất 5 query improved và 5 query regressed để biết vì sao metric đổi.

## 11. Production readiness

Dùng reranker trong production được không? Có, nếu thỏa các điều kiện sau:

- Có eval set đại diện và reranker cải thiện metric quan trọng, ví dụ Recall@5 hoặc MRR@10, không chỉ cải thiện demo.
- Candidate pool trước rerank có recall đủ cao, thường đo Recall@50 hoặc Recall@100.
- ACL, tenant, deleted document và index version được filter trước rerank.
- Latency p95/p99 sau khi thêm rerank vẫn nằm trong SLA.
- Có timeout, fallback về retrieval rank và monitoring lỗi.
- Có quyết định rõ managed vs self-host dựa trên privacy, cost, traffic và năng lực vận hành.
- Có versioning cho reranker model, prompt/context builder và config `retrieve_k`, `rerank_k`, `final_k`.
- Có regression test cho citation correctness và các query rủi ro cao.

Nếu chưa có eval set, chưa có ACL filter hoặc không đo latency percentile, chưa nên bật reranker mặc định cho production traffic. Có thể bật bằng feature flag cho internal users hoặc shadow traffic để thu số liệu.

## 12. Checklist cuối bài

- [ ] Giải thích được vì sao retrieval top-k chưa đủ cho RAG production.
- [ ] Phân biệt được bi-encoder và cross-encoder bằng latency, cost và quality.
- [ ] Mô tả được BGE reranker và Cohere Rerank ở mức concept lẫn trade-off.
- [ ] Thiết kế được pipeline retrieve top 50/100 -> rerank top 5/10.
- [ ] Biết đặt ACL filter trước rerank.
- [ ] Đo được Recall@k và MRR trước/sau rerank.
- [ ] Có latency p50/p95/p99 cho search, rerank và total retrieval.
- [ ] Có fallback khi reranker fail hoặc quá chậm.
- [ ] Trả lời được production readiness bằng điều kiện cụ thể, không trả lời chung chung.
