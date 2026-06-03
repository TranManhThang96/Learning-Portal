# Day 36: Hybrid Search Production

## 1. Bài toán cần giải quyết

Trong RAG, retriever quyết định LLM nhìn thấy tài liệu nào. Nếu retriever bỏ sót tài liệu đúng, prompt tốt đến đâu cũng khó cứu được câu trả lời.

Một hệ thống RAG đơn giản thường bắt đầu bằng vector search:

```text
user query
  -> embedding query
  -> vector search top_k
  -> build context
  -> LLM answer
```

Cách này tốt cho câu hỏi semantic, nhưng dễ thất bại với query chứa mã lỗi, tên riêng, acronym, SKU, điều khoản pháp lý hoặc từ khóa rất ngắn:

```text
"HTTP 429"
"SLA P1 enterprise"
"VAT invoice"
"CVE-2024-..."
"điều 12.3"
"BAAI/bge-m3 normalize_embeddings"
```

Hybrid search giải quyết bằng cách chạy ít nhất hai retrieval path:

```text
query
  -> BM25 / sparse search
  -> dense vector search
  -> merge candidates
  -> optional reranker
  -> context builder
```

Điểm quan trọng: hybrid search không phải thêm search engine cho vui. Nó là cách giảm rủi ro retrieval miss khi corpus có cả ngôn ngữ tự nhiên lẫn từ khóa exact.

## 2. Mục tiêu học

Sau bài này bạn cần làm được các việc sau:

- Phân biệt dense retrieval, sparse retrieval, BM25 và SPLADE.
- Hiểu vì sao BM25 vẫn cần thiết dù đã có embedding model tốt.
- Thiết kế pipeline BM25 top-k + vector top-k + merge bằng Reciprocal Rank Fusion.
- Biết query nào keyword-heavy, query nào semantic-heavy, query nào mixed.
- Biết normalize query mà không làm mất mã lỗi, acronym, số hiệu và thuật ngữ.
- Biết đánh giá bằng Hit@K, Recall@K, MRR@K, nDCG@K và latency percentile.
- Trả lời được câu hỏi production readiness cho hybrid search.

## 3. Dense retrieval

Dense retrieval biến query và document chunk thành embedding vector. Search được thực hiện bằng similarity trong vector space, thường là cosine similarity hoặc dot product.

```text
query text -> query embedding
chunk text -> chunk embedding
similarity(query embedding, chunk embedding) -> top_k chunks
```

Dense retrieval mạnh ở semantic similarity:

| Query | Chunk đúng | Vì sao dense hữu ích |
|---|---|---|
| "tôi muốn lấy lại tiền" | "Khách hàng có thể yêu cầu hoàn tiền..." | Query và document dùng từ khác nhau |
| "làm sao đổi email đăng nhập" | "Cập nhật địa chỉ email trong profile..." | Ý nghĩa gần nhau dù wording khác |
| "policy nghỉ khi có việc gia đình" | "Compassionate leave..." | Cross-lingual hoặc mixed language nếu model hỗ trợ |

Điểm mạnh:

- Bắt được synonym, paraphrase và intent.
- Hợp với câu hỏi dài, mô tả bằng ngôn ngữ tự nhiên.
- Hữu ích khi user không biết đúng thuật ngữ trong tài liệu.
- Có thể hỗ trợ multilingual nếu embedding model được train phù hợp.

Điểm yếu:

- Dễ bỏ qua exact token như `HTTP 429`, `P1`, `VAT`, `S3`, `C++`, `SKU-123`.
- Vector score khó giải thích cho user và support engineer.
- Chất lượng phụ thuộc mạnh vào embedding model, chunking strategy và domain benchmark.
- Query quá ngắn có ít semantic signal.
- ANN search có thể mất recall nếu index được tune quá aggressive.

Kết luận thực tế: dense retrieval nên được xem là semantic candidate generator, không phải toàn bộ search system.

## 4. Sparse retrieval

Sparse retrieval biểu diễn query/document bằng token hoặc term. Vector sparse thường có kích thước rất lớn, mỗi chiều tương ứng một token trong vocabulary, nhưng phần lớn giá trị bằng 0.

Các dạng sparse retrieval phổ biến:

| Dạng | Mô tả | Khi dùng |
|---|---|---|
| Boolean search | Match token/phrase/filter đơn giản | Admin search, debug, filter chính xác |
| TF-IDF | Term frequency + inverse document frequency | Baseline học thuật, corpus nhỏ |
| BM25 | Ranking keyword mạnh, có saturation và length normalization | Baseline production phổ biến |
| Neural sparse, ví dụ SPLADE | Dùng model để tạo token weight và query/document expansion | Khi cần semantic expansion nhưng vẫn muốn inverted index |

Sparse retrieval mạnh khi query và document chia sẻ token quan trọng:

```text
query: "HTTP 429"
doc: "Vượt giới hạn API trả về HTTP 429."
```

Sparse retrieval yếu khi query dùng synonym:

```text
query: "lấy lại tiền"
doc: "Khách hàng có thể yêu cầu hoàn tiền."
```

Với tiếng Việt, chất lượng sparse retrieval phụ thuộc rất nhiều vào analyzer/tokenizer. Nếu hệ thống tokenization kém, query không dấu, viết tắt, tiếng Anh lẫn tiếng Việt hoặc dấu câu đặc biệt có thể làm BM25 miss.

## 5. BM25 là gì?

BM25, viết tắt của Best Matching 25, là thuật toán ranking keyword phổ biến trong search engine. Trực giác:

```text
score cao nếu query term xuất hiện trong document,
term hiếm có trọng số cao hơn term phổ biến,
document quá dài bị normalize,
term lặp nhiều có lợi nhưng bị saturation.
```

BM25 thường dùng công thức dạng:

```text
score(D, Q) = sum(IDF(q_i) * ((tf(q_i, D) * (k1 + 1)) / (tf(q_i, D) + k1 * (1 - b + b * |D| / avgdl))))
```

Bạn không cần thuộc công thức để dùng tốt BM25, nhưng cần hiểu các thành phần:

| Thành phần | Ý nghĩa | Tác động |
|---|---|---|
| `tf` | Term frequency trong document | Term xuất hiện nhiều hơn thì score tăng |
| `IDF` | Term hiếm trong corpus có trọng số cao hơn | `VAT` thường quan trọng hơn `là` |
| `|D| / avgdl` | Document length normalization | Chunk rất dài không tự động thắng |
| `k1` | Điều khiển saturation của term frequency | Cao hơn nghĩa là lặp term còn có thêm lợi ích |
| `b` | Điều khiển mức phạt document dài | `0` bỏ length normalization, `1` dùng mạnh |

BM25 tốt cho:

- Error code: `HTTP 429`, `ORA-00001`, `ECONNRESET`.
- Acronym: `SLA`, `VAT`, `SSO`, `2FA`, `PII`.
- Product code, SKU, invoice number, ticket ID.
- Legal term, clause number, section heading.
- API name, table name, column name, config key.
- Query ngắn và keyword-heavy.

BM25 yếu khi:

- User không dùng cùng wording với tài liệu.
- Cần hiểu intent dài, mơ hồ hoặc cross-lingual.
- Document được paraphrase nhiều.
- Analyzer không xử lý tiếng Việt, dấu, stemming hoặc phrase đúng.

## 6. SPLADE overview

SPLADE là neural sparse retrieval. Thay vì chỉ đếm token như BM25, SPLADE dùng transformer để tạo sparse vector có token weight. Model có thể "expand" query/document thành các token liên quan.

Ví dụ trực giác:

```text
query: "lấy lại tiền"
neural sparse expansion có thể tăng weight cho token liên quan tới "refund", "hoàn tiền"
```

Điểm mạnh:

- Vẫn tận dụng được inverted index và sparse scoring.
- Có khả năng semantic expansion tốt hơn BM25 trong nhiều benchmark.
- Dễ debug hơn dense một phần vì output vẫn liên quan tới token.

Điểm đổi lại:

- Indexing và serving phức tạp hơn BM25.
- Cần model riêng, compute riêng và eval riêng.
- Sparse vector có thể lớn, cần kiểm soát pruning/top terms.
- Không nên thêm nếu team chưa có BM25 + dense baseline và query eval set.

Rule thực tế: với RAG v1, bắt đầu bằng BM25 + dense + RRF. Xem SPLADE là bước nâng cấp khi eval chứng minh BM25 là bottleneck và team có năng lực vận hành neural sparse index.

## 7. Hybrid search mental model

Hybrid search thường chạy song song hai candidate generators:

```text
                         +-> BM25 top 50 -----+
query -> normalize/filter|                    +-> merge/dedupe -> rerank -> context
                         +-> dense top 50 ----+
```

Mỗi path có vai trò khác nhau:

| Path | Vai trò | Dạng lỗi hay bù cho path còn lại |
|---|---|---|
| BM25 | Bắt exact keyword, acronym, code, term hiếm | Dense miss mã lỗi/tên riêng |
| Dense | Bắt semantic intent, synonym, paraphrase | BM25 miss khi wording khác |
| Reranker | Xếp lại candidates theo query-document relevance sâu hơn | Cả BM25/dense chỉ là candidate generator |

Một pipeline gần production:

```text
1. nhận query + auth context
2. normalize query an toàn
3. build mandatory filters: tenant, ACL, index_version, deleted=false
4. chạy BM25 top_n và dense top_n song song
5. merge bằng RRF, không merge raw score trực tiếp
6. deduplicate theo chunk_id hoặc canonical_chunk_id
7. optional rerank top 20-100
8. build context có citation, source, page, section
9. log ranks/scores/latency/debug info đã redact PII
10. evaluate offline và monitor online
```

Filter quyền phải áp dụng ở cả BM25 path và dense path. Nếu BM25 không filter ACL nhưng vector có filter ACL, RRF merge vẫn có thể đưa chunk restricted vào context. Đây là lỗi security.

## 8. Reciprocal Rank Fusion

Reciprocal Rank Fusion, viết tắt là RRF, merge nhiều ranking bằng rank thay vì raw score:

```text
rrf_score(doc) = sum(1 / (k + rank_i(doc)))
```

Trong đó:

- `rank_i(doc)` là vị trí của document trong ranking thứ `i`, bắt đầu từ 1.
- Nếu document không xuất hiện trong một ranking, ranking đó không đóng góp score.
- `k` thường dùng khoảng 60 để làm giảm độ chênh giữa rank rất cao và rank trung bình.

Ví dụ:

| Doc | BM25 rank | Dense rank | Ý nghĩa |
|---|---:|---:|---|
| A | 1 | 20 | BM25 rất chắc, vẫn nên giữ |
| B | 7 | 3 | Cả hai path đều ủng hộ |
| C | - | 1 | Dense bắt semantic tốt, BM25 miss |
| D | 2 | - | BM25 bắt exact keyword, dense miss |

Vì sao RRF tốt để bắt đầu:

- Không cần calibrate BM25 score với cosine score.
- Ổn định khi hai search engine có score scale khác nhau.
- Dễ implement, dễ explain, dễ debug.
- Thường là baseline mạnh trước khi tuning weighted fusion.

Khi nào cân nhắc weighted score fusion:

- Bạn có eval set đủ tốt.
- Score đã được normalize/calibrate cẩn thận.
- Bạn cần ưu tiên path cụ thể theo query classifier.
- Bạn có monitoring để phát hiện regression theo query category.

Nếu chưa có các điều kiện trên, RRF là lựa chọn thực dụng hơn.

## 9. Query normalization

Query normalization là bước làm query nhất quán với index analyzer, nhưng không được phá hỏng thông tin quan trọng.

Nên làm:

- Unicode normalize, ví dụ NFC/NFKC tùy pipeline.
- Trim khoảng trắng, gom nhiều spaces thành một.
- Lowercase cho phần text thường nếu analyzer cũng lowercase.
- Chuẩn hóa dấu câu phổ biến nhưng giữ ký tự có nghĩa.
- Tạo variant có dấu/không dấu nếu corpus và user input bị mix.
- Map synonym domain bằng dictionary được kiểm soát, ví dụ `2fa -> two factor authentication`.
- Giữ nguyên số, code, SKU, acronym, config key, API name.

Không nên làm quá aggressive:

```text
"C++"       -> "c"       # sai
"S3"        -> "s"       # sai
"HTTP 429"  -> ""        # sai
"P1/P2"     -> "p p"     # sai
"node.js"   -> "node js" # có thể sai nếu corpus giữ "node.js"
```

Với tiếng Việt, các vấn đề hay gặp:

| Vấn đề | Ví dụ | Cách xử lý |
|---|---|---|
| Query không dấu | "hoan tien" vs "hoàn tiền" | Analyzer hỗ trợ folding hoặc tạo query variants |
| English mix | "reset mat khau 2FA" | Giữ acronym/code, normalize phần tiếng Việt |
| Tên riêng | "Phong Ke Toan" vs "Phòng Kế Toán" | Dictionary/entity normalization |
| Dấu câu có nghĩa | `C++`, `C#`, `node.js` | Tokenizer whitelist pattern |

Rule production: analyzer lúc index và analyzer lúc query phải consistent. Mỗi thay đổi analyzer cần reindex hoặc ít nhất chạy lại benchmark.

## 10. Keyword-heavy vs semantic query

Không phải query nào cũng nên được xử lý giống nhau.

| Query type | Ví dụ | Path thường mạnh | Ghi chú |
|---|---|---|---|
| Keyword-heavy | `HTTP 429`, `SLA P1`, `VAT invoice` | BM25 | Exact token rất quan trọng |
| Semantic-heavy | "tôi muốn lấy lại tiền" | Dense | User không dùng đúng wording |
| Mixed | "hoàn tiền gói Pro VAT" | Hybrid | Có intent và exact term |
| No-diacritic Vietnamese | "hoan tien goi enterprise" | Tùy analyzer + dense | Cần test riêng |
| Code/API | `query_points filter MatchAny` | BM25 + dense | Tokenizer phải giữ identifier |
| Legal/policy | "điều kiện nghỉ phép theo điều 12" | Hybrid | Exact clause + semantic context |

Một số hệ thống thêm query classifier:

```text
if query contains many codes/acronyms/numbers:
    increase BM25 top_k or weight
elif query is long natural language:
    increase dense top_k
else:
    use balanced hybrid
```

Đừng bắt đầu bằng classifier phức tạp. Hãy bắt đầu bằng hybrid balanced, log query category, rồi tối ưu bằng số liệu.

## 11. Dedupe và chunk selection

Hybrid search dễ trả về nhiều chunk gần giống nhau vì BM25 và dense cùng tìm thấy các chunk cạnh nhau trong một document.

Dedupe nên có nhiều tầng:

| Tầng | Key | Mục đích |
|---|---|---|
| Exact chunk | `chunk_id` | Không trả một chunk hai lần |
| Canonical chunk | `document_id + section + chunk_index` | Tránh duplicate giữa index version nếu có bug |
| Near-duplicate | text hash hoặc simhash | Loại bản copy giống nhau |
| Document diversity | giới hạn chunk mỗi document | Tránh một document chiếm hết context |

Trong RAG, top results không chỉ cần relevant, mà còn cần đa dạng đủ để trả lời. Sau RRF, context builder có thể áp dụng policy:

```text
max_chunks_per_document = 2
prefer_latest_document_version = true
require_citation_fields = true
drop_chunks_below_min_score_after_rerank = true
```

## 12. Evaluation

Không nên đánh giá retrieval bằng vài câu query tự nghĩ rồi nhìn output. Cần query set có qrels, tức mapping query -> relevant chunk/document.

Query set tối thiểu nên có các category:

```text
semantic
keyword
mixed
acronym
exact_code
no_diacritic
english_mix
short_query
long_question
negative_or_ambiguous
```

Metrics:

| Metric | Ý nghĩa | Khi dùng |
|---|---|---|
| Hit@K | Có ít nhất một chunk đúng trong top K không | Dễ hiểu cho RAG |
| Recall@K | Lấy được bao nhiêu chunk đúng trong top K | Khi nhiều chunk cùng relevant |
| MRR@K | Relevant đầu tiên ở rank mấy | Đo ranking top đầu |
| nDCG@K | Có graded relevance | Khi qrels có mức độ đúng |
| p50/p95/p99 latency | Độ trễ retrieval | Production SLA |
| zero-result rate | Tỷ lệ không có candidate | Health check |
| ACL leak test | Không trả chunk sai quyền | Security gate |

Bảng so sánh bắt buộc:

```markdown
| Config | Hit@5 | Recall@10 | MRR@10 | p95 ms | Ghi chú |
|---|---:|---:|---:|---:|---|
| BM25-only | | | | | |
| Dense-only | | | | | |
| Hybrid RRF | | | | | |
| Hybrid RRF + reranker | | | | | |
```

Luôn xem metric theo category. Average có thể che lỗi:

```text
Dense-only average tốt nhưng exact_code rất tệ.
BM25-only keyword tốt nhưng semantic rất tệ.
Hybrid average tốt và ít category bị rơi mạnh hơn.
```

## 13. Performance và latency

Hybrid search thêm ít nhất hai search calls. Nếu chạy tuần tự, latency có thể tăng đáng kể:

```text
latency_total = normalize + bm25 + dense + merge + rerank + context
```

Production nên chạy BM25 và dense song song nếu infra cho phép:

```text
latency_total ~= normalize + max(bm25, dense) + merge + rerank + context
```

Latency budget tham khảo cho RAG v1:

| Stage | Budget tham khảo |
|---|---:|
| Query normalize | 1-20 ms |
| Build filters | 1-5 ms |
| BM25 search | 20-120 ms |
| Dense search | 20-180 ms |
| RRF merge + dedupe | 1-10 ms |
| Reranker optional | 100-800 ms |
| Context builder | 5-50 ms |

Trade-off chính:

| Quyết định | Tăng chất lượng | Tăng cost/latency | Ghi chú |
|---|---|---|---|
| Tăng BM25 top_k | Tốt hơn cho keyword recall | Nhiều candidate hơn | Có thể làm reranker chậm |
| Tăng dense top_k | Tốt hơn cho semantic recall | Vector search và rerank chậm hơn | Cần benchmark |
| RRF k nhỏ hơn | Top rank ảnh hưởng mạnh hơn | Có thể kém ổn định | Tune bằng eval |
| Thêm reranker | Ranking/citation tốt hơn | Latency lớn nhất | Rerank top 20-100 |
| Query expansion | Cải thiện query ngắn | Risk drift intent | Cần guardrail |
| SPLADE | Sparse semantic tốt hơn | Ops phức tạp hơn | Không phải bước đầu |

## 14. Security và multi-tenancy

Hybrid retrieval có hai path nên dễ có bug phân quyền.

Filter bắt buộc ở cả BM25 và dense:

```text
tenant_id = current_user.tenant_id
AND index_version = active_index_version
AND deleted_at IS NULL
AND acl_roles intersects current_user.roles
```

Cache key cũng phải chứa:

```text
tenant_id
user_permission_hash
query_normalized
index_version
retrieval_config_version
```

Log phải đủ debug nhưng không leak PII:

```json
{
  "query_hash": "sha256:...",
  "tenant_id": "company_a",
  "bm25_top_k": 50,
  "dense_top_k": 50,
  "rrf_k": 60,
  "bm25_latency_ms": 42,
  "dense_latency_ms": 65,
  "merge_latency_ms": 2,
  "final_chunk_ids": ["..."],
  "index_version": "rag-index-2026-05-10"
}
```

Không log raw query hoặc raw chunk nếu dữ liệu có thể chứa thông tin nhạy cảm. Dùng sampling, hashing và redaction.

## 15. Production readiness

Câu hỏi: "Dùng hybrid search trong production được không?"

Có, hybrid search là một lựa chọn rất hợp lý cho production RAG, đặc biệt khi corpus có tài liệu doanh nghiệp, policy, code, acronym, mã lỗi, tiếng Việt không dấu/có dấu và English mix. Tuy nhiên, chỉ nên gọi là production-ready khi thỏa các điều kiện sau:

- Có BM25 index và vector index cùng `index_version` hoặc có cơ chế sync rõ ràng.
- Analyzer/tokenizer được chọn theo ngôn ngữ corpus và đã test với query thật.
- Tenant/ACL/deleted/index filters được áp dụng bắt buộc ở cả hai retrieval path.
- Có qrels và benchmark BM25-only vs dense-only vs hybrid.
- Có metric quality theo query category, không chỉ average.
- Có latency budget p95/p99 và load test với top_k/reranker thực tế.
- Có logging ranks/scores/latency đủ để debug nhưng đã redact PII.
- Có cache key chứa tenant, permission hash, index version và config version.
- Có runbook reindex khi đổi analyzer, embedding model, chunking strategy hoặc SPLADE model.
- Có regression tests chống leak tenant/ACL.

Nếu thiếu eval set và ACL tests, hybrid search vẫn có thể chạy, nhưng chưa nên coi là production-ready.

## 16. Best practices

1. Luôn có BM25 baseline trước khi kết luận embedding model tốt.
2. Với enterprise RAG, thử hybrid trước khi thử vector-only.
3. Merge bằng RRF trước khi tuning weighted fusion.
4. Không merge raw BM25 score và cosine score trực tiếp nếu chưa calibrate.
5. Chạy BM25 và dense song song trên online path.
6. Filter tenant/ACL ở cả hai path, không filter sau merge.
7. Dedupe theo `chunk_id`, rồi kiểm soát diversity theo `document_id`.
8. Log rank từ từng path để debug vì sao chunk vào top results.
9. Đánh giá theo query category: semantic, keyword, mixed, code, no-diacritic.
10. Reranker là bước sau hybrid, không thay thế candidate generation.
11. Không normalize mất acronym, số, mã lỗi, SKU, API name.
12. Re-run eval khi đổi embedding model, analyzer, chunking hoặc RRF config.

## 17. Checklist tự kiểm tra

- [ ] Tôi giải thích được dense retrieval mạnh và yếu ở đâu.
- [ ] Tôi giải thích được BM25 scoring ở mức trực giác.
- [ ] Tôi biết SPLADE khác BM25 và dense retrieval như thế nào.
- [ ] Tôi biết vì sao hybrid không nên merge raw scores trực tiếp.
- [ ] Tôi implement được RRF.
- [ ] Tôi biết normalize query tiếng Việt mà không làm hỏng code/acronym.
- [ ] Tôi biết thiết kế filter tenant/ACL cho cả BM25 và dense.
- [ ] Tôi biết benchmark BM25-only, dense-only, hybrid và hybrid + reranker.
- [ ] Tôi biết đọc kết quả theo query category.
- [ ] Tôi trả lời được điều kiện production readiness.

## 18. Câu hỏi ôn tập

1. Vì sao embedding không thay thế hoàn toàn BM25?
2. BM25 sẽ thắng dense retrieval trong những query nào?
3. Dense retrieval sẽ thắng BM25 trong những query nào?
4. RRF giải quyết vấn đề gì khi merge BM25 và vector search?
5. Vì sao không nên cộng trực tiếp BM25 score với cosine score?
6. Query normalization có thể làm sai retrieval như thế nào?
7. SPLADE phù hợp ở giai đoạn nào của roadmap?
8. Vì sao filter tenant/ACL sau merge là không đủ?
9. Khi nào nên thêm reranker sau hybrid?
10. Những metric nào cần có trước khi thay đổi analyzer hoặc embedding model?
