# Day 39: RAG Evaluation Production

## 1. Vì sao RAG phải có evaluation?

Một RAG system có nhiều bước hơn một chatbot thông thường:

```text
user query
  -> normalize/rewrite query
  -> retrieve candidates
  -> hybrid merge optional
  -> rerank optional
  -> build context
  -> generate answer
  -> attach citations
  -> log trace/feedback
```

Nếu answer sai, nguyên nhân có thể nằm ở bất kỳ bước nào:

- Parser làm mất bảng, heading hoặc footnote.
- Chunking cắt mất điều kiện quan trọng.
- Embedding model không hiểu từ viết tắt, mã sản phẩm hoặc tiếng Việt không dấu.
- BM25/analyzer không match dấu, casing, token đặc biệt.
- Hybrid merge lấy được chunk đúng nhưng xếp quá thấp.
- Reranker đẩy nhầm chunk nhiễu lên đầu.
- Context builder bỏ mất chunk đúng vì token budget.
- LLM hallucinate dù context đã đủ.
- Citation trỏ sai source.
- ACL filter làm user thấy tài liệu không đúng quyền hoặc không thấy tài liệu cần thiết.

RAG không nên release chỉ vì vài câu hỏi demo trả lời đúng. Evaluation phải trả lời được 4 câu hỏi:

1. Retriever có tìm được chunk đúng không?
2. Context được đưa vào LLM có đủ và đúng không?
3. Answer có đúng, grounded và cite đúng không?
4. Khi thay đổi embedding, chunking, reranker, prompt hoặc model, chất lượng có regression không?

## 2. Tư duy evaluation theo tầng

Không gộp mọi thứ thành một điểm số duy nhất. Hãy đo theo tầng để debug được nguyên nhân.

| Tầng | Câu hỏi cần trả lời | Metric chính |
|---|---|---|
| Dataset | Golden set có đại diện traffic thật không? | Coverage theo tag/difficulty |
| Retrieval | Top-k có chứa chunk đúng không? | Hit@k, Recall@k, Precision@k, MRR, NDCG |
| Context | Context đưa vào LLM có đủ, ít nhiễu và đúng quyền không? | Context recall, context precision, ACL pass rate |
| Generation | Answer có đúng và dựa trên context không? | Faithfulness, answer relevance, answer correctness |
| Citation | Citation có tồn tại và support claim không? | Citation correctness, citation coverage |
| Safety | Có leak dữ liệu, prompt injection hoặc hallucination không? | Hallucination rate, abstention accuracy, security cases |
| Ops | Có đạt latency, cost và stability không? | p95 latency, cost/query, error rate |

Điểm tổng hợp chỉ dùng cho dashboard. Quyết định release nên dựa trên gate cụ thể theo metric và theo nhóm query quan trọng.

## 3. Golden dataset là gì?

Golden dataset là bộ câu hỏi đã được review, có expected answer và expected source. Với RAG, mỗi row nên có cả nhãn cho retrieval và generation.

Schema tối thiểu:

```json
{
  "id": "hr_leave_001",
  "question": "Nhân viên full-time được nghỉ phép năm bao nhiêu ngày?",
  "expected_answer": "Nhân viên full-time được nghỉ 12 ngày phép năm.",
  "expected_chunk_ids": ["hr_leave_policy:v2026-01:chunk_003"],
  "relevance": {
    "hr_leave_policy:v2026-01:chunk_003": 3,
    "hr_leave_policy:v2026-01:chunk_004": 1
  },
  "must_cite": ["hr_leave_policy"],
  "difficulty": "easy",
  "tags": ["hr", "policy", "single-hop"],
  "user_context": {
    "tenant_id": "company_a",
    "roles": ["employee"]
  },
  "expected_behavior": "answer"
}
```

Các field nên có trong production:

| Field | Mục đích |
|---|---|
| `id` | Trace, report, regression diff |
| `question` | Query thật hoặc query đã review |
| `expected_answer` | Dùng cho answer correctness và human review |
| `expected_chunk_ids` | Dùng cho retrieval metrics |
| `relevance` | Dùng cho NDCG khi có nhiều mức liên quan |
| `must_cite` | Dùng cho citation gate |
| `difficulty` | Dễ thấy model fail ở easy/medium/hard |
| `tags` | Breakdown theo domain, case type, language, ACL |
| `user_context` | Test tenant/role/permission-aware retrieval |
| `expected_behavior` | `answer`, `abstain`, `permission_denied`, `escalate` |
| `notes` | Lý do label, edge case, nguồn review |

Golden set 30-50 câu đủ tốt cho learning và capstone. Với production thật, hãy tăng dần lên 100-500+ câu theo traffic, domain risk và số lượng document type.

## 4. Cách tạo golden set 30-50 câu

Step-by-step:

1. Chọn corpus ổn định: 20-50 tài liệu đại diện cho RAG pipeline hiện tại.
2. Gắn `document_id`, `document_version`, `chunk_id`, `section_path`, `page_start`, `page_end`, `acl_roles`.
3. Chọn 30-50 câu hỏi theo ma trận coverage, không chỉ hỏi câu dễ.
4. Với mỗi câu, label expected answer ngắn, expected chunk IDs và mức relevance.
5. Thêm no-answer cases để đo hallucination và abstention.
6. Thêm ACL cases để đo leak hoặc thiếu quyền.
7. Thêm Vietnamese no-diacritic, acronym, SKU, số liệu, ngày tháng, multi-hop.
8. Review bởi domain expert hoặc người hiểu tài liệu.
9. Freeze test set. Nếu cần tuning, tạo validation set riêng.
10. Version dataset cùng corpus, chunking strategy, embedding model, reranker, prompt và generator model.

Ma trận coverage gợi ý cho khoảng 40 câu:

| Nhóm | Số câu | Ví dụ |
|---|---:|---|
| Easy exact match | 6 | Hỏi đúng wording trong tài liệu |
| Paraphrase/synonym | 5 | "nghỉ phép" vs "annual leave" |
| No-diacritic Vietnamese | 4 | "nghi phep nam bao nhieu ngay" |
| Acronym/code/SKU | 4 | "SLA", "PTO", "ERR-429" |
| Multi-hop | 5 | Cần nối chính sách và bảng điều kiện |
| Table/numeric | 4 | Số ngày, hạn mức, latency, chi phí |
| No-answer/abstain | 4 | Tài liệu không có thông tin |
| ACL/tenant | 4 | User role khác nhau nhận kết quả khác nhau |
| Stale/version | 2 | Tài liệu cũ và mới mâu thuẫn |
| Prompt injection/security | 2 | Tài liệu chứa câu lệnh độc hại |

## 5. Qrels và relevance levels

`qrels` là mapping từ query sang chunk liên quan. Đây là nền cho retrieval metrics.

```json
{
  "query_id": "q001",
  "relevant_chunks": [
    {
      "chunk_id": "hr_leave_policy:v2026-01:chunk_003",
      "relevance": 3,
      "reason": "Chứa số ngày nghỉ phép chính thức"
    },
    {
      "chunk_id": "hr_leave_policy:v2026-01:chunk_004",
      "relevance": 1,
      "reason": "Chứa điều kiện prorate bổ sung"
    }
  ]
}
```

Relevance level thường dùng:

| Relevance | Ý nghĩa |
|---:|---|
| 0 | Không liên quan |
| 1 | Liên quan phụ, có background |
| 2 | Liên quan mạnh nhưng chưa đủ answer |
| 3 | Chứa fact bắt buộc để trả lời |

Khi thay đổi chunking strategy, `chunk_id` có thể đổi. Vì vậy chunk cần có metadata ổn định:

- `document_id`
- `document_version`
- `section_path`
- `page_start`, `page_end`
- `text_hash`
- `chunking_strategy`
- `index_version`

Nếu không quản lý version, eval có thể fail vì label cũ không còn map được sang chunk mới, không phải vì retrieval kém.

## 6. Retrieval metrics

Giả sử với một query:

- `R` là tập relevant chunk IDs theo qrels.
- `T_k` là top-k retrieved chunk IDs.
- `rank(r)` là vị trí của chunk relevant đầu tiên trong ranking.

### Hit@k

Hit@k kiểm tra top-k có ít nhất một chunk đúng không.

```text
Hit@k = 1 nếu T_k giao R khác rỗng, ngược lại 0
```

Dễ hiểu cho product stakeholder, nhưng không biết retriever lấy đủ evidence hay không.

### Recall@k

Recall@k đo tỷ lệ relevant chunks được lấy về.

```text
Recall@k = |T_k giao R| / |R|
```

RAG thường ưu tiên Recall@k cao ở retrieval stage, vì nếu chunk đúng không vào candidate pool thì generator gần như không thể trả lời grounded.

### Precision@k

Precision@k đo độ sạch của top-k.

```text
Precision@k = |T_k giao R| / k
```

Precision thấp nghĩa là context nhiều nhiễu, có thể làm LLM bị distraction, tăng token cost và tăng hallucination.

### MRR@k

MRR, viết tắt của Mean Reciprocal Rank, đo chunk đúng đầu tiên xuất hiện sớm hay muộn.

```text
RR@k = 1 / rank(relevant đầu tiên) nếu rank <= k, ngược lại 0
MRR@k = trung bình RR@k trên toàn bộ query
```

MRR hữu ích khi generator chỉ nhận top 3-5 chunks. Chunk đúng ở rank 10 có thể không bao giờ vào prompt.

### NDCG@k

NDCG phù hợp khi có nhiều mức relevance.

```text
DCG@k = sum((2^rel_i - 1) / log2(i + 1)) với i từ 1 đến k
NDCG@k = DCG@k / IDCG@k
```

`IDCG` là DCG lý tưởng khi các chunk được sort theo relevance giảm dần. NDCG cao nghĩa là chunk quan trọng được xếp lên cao, không chỉ có mặt trong top-k.

## 7. Context precision và context recall

Retrieval metrics đo ranking của retriever. Context metrics đo thứ thật sự đưa vào LLM sau rerank, trimming, dedup và context building.

### Context recall

Context recall trả lời: context cuối cùng có chứa đủ evidence để tạo expected answer không?

Có 2 cách đo:

1. Dựa trên qrels: `context_chunk_ids` có chứa expected chunk IDs không.
2. Dựa trên LLM judge: reference answer có được suy ra từ context không.

Với production, nên dùng cả hai. Qrels deterministic và rẻ. LLM judge bắt được trường hợp chunk ID khác nhưng text vẫn chứa evidence đúng.

### Context precision

Context precision trả lời: context cuối cùng có chứa nhiều đoạn nhiễu không, và evidence đúng có đứng trước không?

Nếu context có 8 chunks nhưng chỉ 1 chunk liên quan, LLM vẫn có thể trả lời sai vì bị nhiễu. Context precision thấp thường là dấu hiệu cần:

- Tăng chất lượng reranker.
- Giảm `top_k` đưa vào prompt.
- Deduplicate chunks gần nhau.
- Cải thiện chunking để mỗi chunk tự đủ nghĩa.
- Tách evidence chính và background context.

## 8. Generation metrics

Generation quality không thể đo chỉ bằng retrieval score. Một pipeline có Recall@10 cao vẫn có thể trả lời sai.

| Metric | Câu hỏi | Cách đo |
|---|---|---|
| Faithfulness | Mọi claim trong answer có được support bởi context không? | Human review hoặc LLM-as-judge |
| Answer relevance | Answer có trả lời đúng câu hỏi không? | LLM-as-judge hoặc rubric |
| Answer correctness | Answer có khớp expected answer không? | Human, exact match cho fact ngắn, LLM judge |
| Answer completeness | Có thiếu fact quan trọng không? | Rubric theo expected answer |
| Citation correctness | Citation có tồn tại và support claim không? | Chunk/source check + human/judge |
| Citation coverage | Claim quan trọng có citation không? | Claim extraction + citation check |
| Abstention accuracy | No-answer case có từ chối đúng không? | Expected behavior |
| Hallucination rate | Có thêm fact ngoài context không? | Faithfulness fail, unsupported claim count |
| Format correctness | Output có đúng JSON/schema/UI contract không? | Parser/schema validator |

Faithfulness khác correctness:

- Answer có thể faithful nhưng không correct nếu context retrieved sai.
- Answer có thể correct nhưng không faithful nếu model tự biết từ pretraining mà context không support.

Trong RAG production có citation, faithful nhưng cite sai vẫn không đạt gate.

## 9. Hallucination detection

Hallucination trong RAG thường có 4 dạng:

| Dạng | Ví dụ | Cách bắt |
|---|---|---|
| Unsupported claim | Answer nêu số ngày nghỉ không có trong context | Claim-level faithfulness |
| Wrong citation | Answer đúng nhưng cite chunk khác | Citation correctness |
| Over-answer | Context thiếu nhưng model vẫn trả lời chắc chắn | No-answer cases, abstention gate |
| Policy violation | Model làm theo instruction trong retrieved document | Prompt injection tests |

Quy trình phát hiện gần production:

1. Log answer, context chunks, citations và model version.
2. Tách answer thành claims.
3. Với mỗi claim, kiểm tra claim có được support bởi context/citation không.
4. Nếu claim không support, gắn `unsupported_claim`.
5. Nếu expected behavior là `abstain` nhưng model trả lời nội dung cụ thể, gắn `failed_abstention`.
6. Nếu cited chunk không support claim, gắn `bad_citation`.
7. Report hallucination rate theo tag, không chỉ aggregate.

LLM-as-judge giúp scale nhanh nhưng cần calibration. Hãy lấy một subset 30-100 outputs cho human label, rồi so sánh judge với human label trước khi dùng làm gate cứng.

## 10. RAGAS, TruLens và LangSmith dùng để làm gì?

Các tool này hữu ích, nhưng không thay thế custom eval runner cho retrieval metrics deterministic.

| Tool | Mạnh ở đâu | Khi nên dùng | Lưu ý production |
|---|---|---|---|
| RAGAS | Metrics cho RAG như faithfulness, answer relevancy, context precision/recall | Muốn chấm RAG offline nhanh bằng dataset | Phụ thuộc LLM judge, cần pin version và lưu raw score |
| TruLens | Feedback functions, tracing, RAG Triad: context relevance, groundedness, answer relevance | Muốn quan sát app và feedback theo trace | Cần setup selector đúng với framework của app |
| LangSmith | Dataset, traces, experiments, evaluator và regression workflow cho LangChain/LangGraph ecosystem | Pipeline dùng LangChain/LangGraph hoặc muốn quản lý eval experiment | Có ecosystem lock-in, vẫn nên export raw results |
| Custom runner | Retrieval metrics, qrels, release gate, CI report | Luôn nên có | Phải tự viết và duy trì |

Ví dụ RAGAS concept:

```python
from ragas import evaluate
from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

metrics = [
    ContextPrecision(),
    ContextRecall(),
    Faithfulness(),
    AnswerRelevancy(),
]

result = evaluate(dataset=ragas_dataset, metrics=metrics)
df = result.to_pandas()
```

Ví dụ TruLens concept:

```python
from trulens.core import Feedback
from trulens.providers.openai import OpenAI

provider = OpenAI(model_engine="gpt-4o-mini")

f_groundedness = Feedback(
    provider.groundedness_measure_with_cot_reasons,
    name="Groundedness",
)

f_answer_relevance = Feedback(
    provider.relevance_with_cot_reasons,
    name="Answer Relevance",
)
```

Ví dụ LangSmith concept:

```python
from langsmith import Client

client = Client()
dataset = client.create_dataset(dataset_name="rag-golden-v1")
client.create_examples(dataset_id=dataset.id, examples=examples)

results = client.evaluate(
    target_rag_function,
    data=dataset.name,
    evaluators=[retrieval_evaluator, correctness_evaluator],
    experiment_prefix="hybrid-rerank-v3",
)
```

API của các thư viện eval thay đổi theo version. Trong hệ thống thật, hãy pin dependency, lưu version vào report và không để CI phụ thuộc hoàn toàn vào metric LLM-as-judge không deterministic.

## 11. Trace bắt buộc cho mỗi eval case

Không có trace thì eval chỉ nói "sai", không nói "sai ở đâu".

Mỗi case nên log:

```json
{
  "query_id": "hr_leave_001",
  "question": "Nhân viên full-time được nghỉ phép năm bao nhiêu ngày?",
  "query_rewrite": "số ngày nghỉ phép năm nhân viên full-time",
  "retrieved_chunks": [
    {"chunk_id": "hr_leave_policy:v2026-01:chunk_003", "score": 0.83, "stage": "hybrid"}
  ],
  "reranked_chunks": [
    {"chunk_id": "hr_leave_policy:v2026-01:chunk_003", "score": 0.91, "rank": 1}
  ],
  "context_chunks": ["hr_leave_policy:v2026-01:chunk_003"],
  "answer": "Nhân viên full-time được nghỉ 12 ngày phép năm.",
  "citations": ["hr_leave_policy:v2026-01:chunk_003"],
  "latency_ms": {
    "embed": 28,
    "retrieve": 42,
    "rerank": 180,
    "generate": 1450
  },
  "tokens": {"prompt": 1800, "completion": 80},
  "cost_usd": 0.0032,
  "versions": {
    "eval_set": "rag-golden-v1.2",
    "corpus": "company-handbook-2026-01",
    "chunking": "markdown_v2_800_120",
    "embedding": "bge-m3",
    "index": "rag-index-2026-05-10",
    "reranker": "bge-reranker-v2-m3",
    "prompt": "answer-with-citation-v7",
    "generator": "gpt-4o-mini-2026-xx"
  }
}
```

Trace cũng giúp so sánh regression:

- Chunk đúng từng có ở rank 2, nay biến mất khỏi top 50: lỗi retriever/index/filter.
- Chunk đúng có trong retrieved nhưng bị reranker đẩy xuống: lỗi reranker.
- Chunk đúng có trong context nhưng answer sai: lỗi generator/prompt.
- Answer đúng nhưng citation sai: lỗi citation extraction/rendering.

## 12. Error analysis theo root cause

Sau mỗi eval run, đừng chỉ nhìn average. Hãy xem top failed queries.

| Root cause | Dấu hiệu | Cách sửa |
|---|---|---|
| Parser | Text chunk thiếu bảng, heading hoặc số liệu | Cải thiện parser, OCR, table extraction |
| Chunking | Evidence bị cắt qua 2 chunks | Tăng overlap, parent-child, section-aware chunking |
| Embedding | Semantic query không retrieve đúng | Đổi embedding model, normalize query, add examples |
| BM25/analyzer | Từ khóa, mã lỗi, acronym không match | Tune analyzer, synonym, preserve token |
| Hybrid merge | Dense hoặc BM25 có chunk đúng nhưng merge làm mất | Tune RRF, weights, candidate pool |
| Reranker | Chunk đúng trong top 50 nhưng không vào top 5 | Đổi reranker, tune prompt/model, train pairwise |
| Context builder | Chunk đúng có trong rerank nhưng không vào prompt | Dedup, token budgeting, context packing |
| Generator | Context đúng nhưng answer sai | Prompt, model, constrained output, few-shot |
| Citation | Answer đúng nhưng cite sai | Claim-citation alignment, citation validator |
| ACL | Leak hoặc thiếu source do quyền | Mandatory filters, security tests, policy-as-code |
| Stale data | Trả lời theo version cũ | Index version, document freshness, reindex job |

Một eval report tốt phải có phần "What changed?" và "Why did metrics move?", không chỉ có bảng số.

## 13. Release gate và regression mindset

Ví dụ gate cho internal knowledge assistant:

```text
Retrieval:
  Recall@10 >= 0.85
  MRR@10 >= 0.70
  NDCG@10 >= 0.75

Generation:
  Faithfulness >= 0.90
  Answer relevance >= 0.88
  Citation correctness >= 0.95
  No-answer accuracy >= 0.90

Safety/Ops:
  ACL leak count = 0
  Critical hallucination count = 0
  p95 end-to-end latency <= 6s
  cost/query <= budget
```

Gate phải theo context:

- Legal/finance/HR: citation, faithfulness, ACL và abstention gate rất chặt.
- Customer support FAQ: có thể chấp nhận latency cao hơn hoặc answer style linh hoạt hơn, nhưng factual correctness vẫn quan trọng.
- Engineering docs: acronym/code search cần BM25/hybrid gate riêng.
- Public marketing bot: safety và brand tone có thể là gate bổ sung.

CI strategy:

| Eval type | Khi chạy | Kích thước | Mục tiêu |
|---|---|---:|---|
| Unit tests | Mỗi commit | 10-50 tests | Schema, metric functions, prompt format |
| Smoke eval | PR/CI | 10-20 golden queries | Bắt regression rõ ràng |
| Full offline eval | Nightly hoặc trước release | 100-500+ queries | Release decision |
| Shadow eval | Sau deploy | Traffic thật replay | So sánh version mới/cũ |
| Online monitoring | Liên tục | Production traces | Drift, feedback, incident |

Không tune trực tiếp trên frozen test set. Nếu bạn tối ưu prompt, retriever hoặc reranker bằng chính golden test set, metric tăng nhưng khả năng generalize có thể giảm. Dùng validation set để tune, test set để quyết định release.

## 14. Performance và cost trong eval

Eval có thể đắt hơn một request thường vì có thêm judge model.

Các cách kiểm soát:

- Cache embedding của query theo `embedding_model`.
- Cache retrieval results khi chỉ thay prompt hoặc generator.
- Cache LLM answer theo `prompt_version`, `model_version`, `question_id`, `context_hash`.
- Chạy retrieval metrics deterministic trước, chỉ judge generation cho cases cần thiết.
- Chạy LLM judge theo batch/concurrency có giới hạn.
- Tách smoke eval trong CI và full eval nightly.
- Lưu raw trace để không phải chạy lại toàn bộ khi chỉ đổi report.

Latency phải đo theo stage:

```text
embed_ms
retrieve_ms
rerank_ms
context_build_ms
generate_ms
judge_ms
end_to_end_ms
```

Nếu chỉ đo end-to-end latency, bạn không biết bottleneck nằm ở vector DB, reranker hay LLM.

## 15. Dùng được trong production không?

Có. RAG Evaluation không chỉ dùng được mà là điều kiện bắt buộc trước khi production, đặc biệt với RAG có citation, permission hoặc domain rủi ro cao.

Điều kiện để production-ready:

- Có golden dataset versioned, đại diện domain và có no-answer/ACL/security cases.
- Có qrels hoặc expected source để đo retrieval deterministic.
- Có eval runner lưu raw trace, report aggregate và breakdown theo tag.
- Có release gate rõ ràng cho retrieval, generation, citation, safety, latency và cost.
- Có human review hoặc calibrated LLM-as-judge cho metric subjective.
- Có CI smoke eval và full offline eval trước release.
- Có monitoring production để phát hiện drift, stale index, provider/model change và user feedback xấu.
- Có quy trình cập nhật golden set khi corpus hoặc policy thay đổi.

Nếu thiếu các điều kiện trên, RAG vẫn có thể chạy demo nhưng chưa nên coi là production-grade.

## 16. Checklist nhanh

- [ ] Golden set có 30-50 câu tối thiểu cho capstone.
- [ ] Mỗi câu có expected answer, expected chunk/source, difficulty và tags.
- [ ] Có no-answer, ACL, stale version, prompt injection và multi-hop cases.
- [ ] Đo Hit@k, Recall@k, Precision@k, MRR và NDCG.
- [ ] Đo context precision/recall sau context builder, không chỉ sau retriever.
- [ ] Đo faithfulness, answer relevance, answer correctness và citation correctness.
- [ ] Report có breakdown theo tag/difficulty.
- [ ] Có raw trace cho từng query.
- [ ] Có error analysis top failed queries.
- [ ] Có release gate và regression comparison với baseline.
- [ ] Có CI smoke eval và full eval trước release.
- [ ] Có câu trả lời rõ ràng cho production readiness.

## 17. Câu hỏi ôn tập

1. Vì sao Recall@10 cao vẫn chưa đảm bảo answer đúng?
2. Precision@k thấp gây hại gì cho RAG generation?
3. MRR@10 khác Recall@10 ở điểm nào?
4. Khi nào nên dùng NDCG thay vì Recall@k?
5. Context recall khác retrieval recall như thế nào?
6. Faithfulness khác answer correctness như thế nào?
7. Vì sao no-answer cases là bắt buộc khi test hallucination?
8. Vì sao LLM-as-judge cần calibration bằng human labels?
9. Khi đổi chunking strategy, golden set bị ảnh hưởng ra sao?
10. Release gate cho HR/legal RAG nên chặt hơn support FAQ ở metric nào?
