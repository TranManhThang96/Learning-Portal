# Day 32: Embedding Models & Benchmark cho tiếng Việt

## TL;DR

Embedding biến text thành vector số để text gần nghĩa nằm gần nhau trong vector space. Trong RAG, embedding quyết định retriever có lấy đúng tài liệu trước khi LLM sinh câu trả lời hay không. Với tiếng Việt, không nên chọn model chỉ vì leaderboard hoặc vì model "nghe có vẻ mạnh". Cách đúng là benchmark trên corpus thật, query thật hoặc query giả lập sát production, có qrels rõ ràng, đo Hit@K, Recall@K, MRR, latency, cost, storage, privacy và khả năng vận hành.

Baseline production cho tiếng Việt thường không nên là dense-only. Nên bắt đầu bằng hybrid retrieval: BM25 cho exact keyword, acronym, mã lỗi, số hợp đồng; dense embedding cho semantic match; reranker ở bước sau nếu cần cải thiện thứ tự top results.

## 1. Embedding là gì?

Embedding là cách biểu diễn một object thành vector số. Trong bài này object là text: query, câu, đoạn văn, chunk tài liệu.

Ví dụ trực giác:

```text
"làm sao xuất hóa đơn VAT" -> [0.12, -0.04, 0.87, ...]
"tôi cần hóa đơn công ty"  -> [0.10, -0.01, 0.82, ...]
"đổi mật khẩu tài khoản"  -> [-0.34, 0.63, 0.02, ...]
```

Hai câu đầu nói về hóa đơn nên vector của chúng nên gần nhau. Câu thứ ba nói về mật khẩu nên nên nằm xa hơn.

Trong RAG, embedding nằm ở hai pipeline:

```text
Indexing path:
Document -> parse -> chunk -> embedding -> lưu vector + metadata vào index

Query path:
User query -> embedding -> vector search -> top chunks -> rerank/context -> LLM
```

Embedding không phải là "hiểu ngôn ngữ" theo nghĩa tuyệt đối. Nó là một phép chiếu xác suất học từ dữ liệu huấn luyện. Vì vậy nó có thể tốt với synonym nhưng yếu với exact code, SKU, số hợp đồng, tên riêng hoặc thuật ngữ domain hiếm.

## 2. Dense vector, sentence embedding và vector space

Dense vector là vector có nhiều chiều và phần lớn chiều có giá trị khác 0. Embedding hiện đại thường là dense vector 384, 768, 1024, 1536, 3072 chiều tùy model.

Sentence embedding là embedding cho cả câu hoặc đoạn text, khác với token embedding bên trong Transformer. Với retrieval, ta thường cần embedding cấp câu/chunk để so sánh query với document chunk.

Điểm quan trọng với Senior SE:

| Khái niệm | Cách nghĩ tương tự trong backend |
|---|---|
| Embedding model | Hàm feature extraction có version |
| Vector dimension | Schema vật lý ảnh hưởng storage/latency |
| Vector index | Index database tối ưu nearest-neighbor search |
| Similarity metric | Hàm ranking, giống ORDER BY theo score |
| Reindex | Migration lớn, tốn tiền và thời gian |
| Qrels | Test fixture/golden set cho retrieval |

## 3. Cosine similarity, dot product và normalization

Ba cách đo similarity phổ biến:

| Metric | Ý nghĩa | Khi dùng |
|---|---|---|
| Cosine similarity | Đo góc giữa hai vector | Phổ biến cho embedding text |
| Dot product | Tổng tích từng chiều | Tốt khi model yêu cầu hoặc vector đã normalize |
| Euclidean distance | Khoảng cách hình học | Dùng khi vector DB/model card khuyến nghị |

Cosine similarity:

```text
cosine(a, b) = dot(a, b) / (||a|| * ||b||)
```

Nếu mọi vector đã được normalize về độ dài 1, ranking theo cosine và dot product thường tương đương:

```text
normalize(a) dot normalize(b) == cosine(a, b)
```

Production rule:

- Đọc model card để biết model khuyến nghị cosine, dot product hay L2.
- Không trộn vector đã normalize và chưa normalize trong cùng index.
- Không so sánh raw score giữa hai model khác nhau như một confidence score.
- Metric đánh giá phải là ranking metric, không chỉ là similarity score trung bình.

## 4. Các nhóm embedding model cần biết

| Nhóm | Ví dụ | Điểm mạnh | Điểm yếu |
|---|---|---|---|
| Managed API | OpenAI embedding, Cohere embedding | Ít vận hành, scale nhanh, SLA/provider tooling tốt | Cost theo usage, phụ thuộc network/provider, privacy/data residency |
| Open-source multilingual | BGE-M3, multilingual-E5 | Self-host được, kiểm soát dữ liệu, tốt cho Viet-English mix | Cần serving, batching, monitoring, GPU/CPU capacity |
| Vietnamese-specific | Vietnamese bi-encoder models | Có thể tốt hơn với tiếng Việt domain-specific | Chất lượng không đồng đều, cần tự benchmark |
| Domain fine-tuned | Fine-tune từ BGE/E5 bằng qrels nội bộ | Quality cao nếu dữ liệu tốt | Cần dataset, training pipeline, regression eval, model governance |

Không có model nào thắng mọi bối cảnh. Legal docs, FAQ support, sản phẩm SaaS, banking, e-commerce và developer docs có failure mode khác nhau.

## 5. BGE, E5, OpenAI, Cohere khác nhau ở đâu?

### OpenAI embedding

Phù hợp khi muốn ship nhanh, giảm ops, không muốn tự host model. Thường là baseline mạnh cho production nếu data policy cho phép gửi query/chunk ra provider. Cần kiểm tra pricing, rate limit, timeout, batch API, data retention và model version.

### Cohere embedding

Thường được dùng trong workflow document retrieval và enterprise search. Tương tự managed API: vận hành nhẹ hơn self-host nhưng phải đánh đổi cost, privacy và dependency.

### BGE

BGE là họ model embedding/reranking open-source phổ biến. BGE-M3 đáng chú ý vì hỗ trợ multilingual và có hướng dense/sparse/multi-vector trong cùng hệ sinh thái. Phù hợp khi cần self-host hoặc muốn giảm phụ thuộc provider.

### E5

E5 là họ model multilingual mạnh cho retrieval. Một chi tiết dễ sai: nhiều model E5 yêu cầu prefix:

```text
query: câu hỏi của user
passage: đoạn tài liệu
```

Nếu quên prefix, benchmark có thể thấp giả tạo. Đây là ví dụ vì sao benchmark phải lưu cả preprocessing config, không chỉ lưu tên model.

### Vietnamese-specific embedding

Nên test nếu corpus chủ yếu là tiếng Việt, có nhiều từ ghép, dấu, không dấu, chính sách nội bộ, thuật ngữ pháp lý/tài chính hoặc câu hỏi support đời thường. Tuy nhiên không nên mặc định rằng model Vietnamese-specific luôn tốt hơn multilingual model. Hãy đo trên qrels của chính mình.

## 6. Vietnamese retrieval concerns

Tiếng Việt có nhiều case làm dense retrieval sai hoặc thiếu ổn định:

| Nhóm vấn đề | Ví dụ | Rủi ro |
|---|---|---|
| Có dấu/không dấu | `hóa đơn` vs `hoa don` | User gõ không dấu nhưng tài liệu có dấu |
| Từ ghép | `bảo mật tài khoản`, `xác thực hai lớp` | Tokenization và semantic match không ổn định |
| English mix | `reset password`, `invoice VAT`, `rate limit` | Query lai ngôn ngữ |
| Acronym | `SLA`, `SSO`, `2FA`, `P1`, `VAT` | Dense model có thể bỏ qua exact match |
| Mã lỗi/số liệu | `HTTP 429`, `99.9%`, `MST`, `SKU` | Cần match chính xác |
| Synonym | `hoàn tiền`, `hủy gói`, `trả lại tiền` | Dense model giúp nhưng không chắc chắn |
| OCR/PDF lỗi | `hoa don`, `h0a d0n`, thiếu khoảng trắng | Cần normalize và parser tốt |
| Domain wording | Pháp lý, tài chính, bảo hiểm | Một từ sai có thể đổi nghĩa |

Baseline thực tế:

```text
hybrid retrieval = dense vector search + BM25 + metadata filter
```

Sau đó mới cân nhắc reranker:

```text
top 50 hybrid results -> reranker -> top 5 context chunks
```

## 7. Dimension vs cost vs latency

Vector dimension càng lớn thì storage, memory bandwidth, index size và network payload thường càng tăng.

Ước tính raw vector float32:

```text
storage_bytes = num_chunks * dimension * 4

1,000,000 chunks * 768 dim  * 4 bytes = ~3.1 GB raw vectors
1,000,000 chunks * 1024 dim * 4 bytes = ~4.1 GB raw vectors
1,000,000 chunks * 1536 dim * 4 bytes = ~6.1 GB raw vectors
```

Đây chưa tính overhead của HNSW/IVF index, metadata, replicas, WAL, backups, compression hoặc quantization.

Trade-off:

| Lựa chọn | Lợi ích | Chi phí/rủi ro |
|---|---|---|
| Dimension nhỏ | Rẻ hơn, nhanh hơn, index nhỏ hơn | Có thể giảm recall |
| Dimension lớn | Có thể tăng quality | Tốn storage, RAM, latency, reindex cost |
| Managed API | Ít ops, time-to-market nhanh | Cost/request, privacy, rate limit |
| Self-host | Kiểm soát dữ liệu và unit cost ở scale lớn | Cần model serving, autoscale, monitoring |
| Dense-only | Đơn giản | Yếu với acronym, exact keyword, mã lỗi |
| Hybrid | Robust hơn cho enterprise docs | Cần merge score, tune weight, vận hành thêm BM25 |

## 8. Benchmark design đúng cách

Benchmark tối thiểu cho bài học:

```text
20 queries tiếng Việt
50-100 document chunks
qrels: query_id -> relevant_chunk_ids
3 embedding models
metrics: Hit@1, Hit@3, Recall@5, MRR@5, latency p50/p95
```

Mỗi query nên có metadata:

- `category`: billing, security, API, policy, incident...
- `difficulty`: easy, synonym, no-diacritic, English-mix, acronym, exact-number...
- `expected_behavior`: dense should match semantic, BM25 should catch exact code...

Qrels là danh sách document/chunk đúng cho từng query:

```json
{
  "q001": ["refund_policy"],
  "q002": ["invoice_vat"],
  "q003": ["sla_enterprise", "support_priority"]
}
```

Nếu một query có nhiều chunk đúng, Recall@K khác Hit@K. Đây là lý do không nên chỉ đo "có trúng một chunk không".

## 9. Metrics cần dùng

| Metric | Công thức trực giác | Ý nghĩa |
|---|---|---|
| Hit@K | Có ít nhất một relevant chunk trong top K | Tốt cho RAG khi chỉ cần một nguồn đúng |
| Recall@K | Số relevant chunks lấy được / tổng relevant chunks | Quan trọng khi câu trả lời cần nhiều nguồn |
| MRR@K | 1 / rank của relevant chunk đầu tiên | Đo chunk đúng xuất hiện sớm hay muộn |
| nDCG@K | Ranking có weighted relevance | Dùng khi có relevance 0/1/2/3 |
| p50/p95 latency | Median và tail latency | Kiểm tra SLA |
| Cost/query | Chi phí online embedding | Kiểm soát unit economics |
| Storage/1M chunks | Raw vector + index overhead | Dự báo infra cost |

Với RAG, retrieval metric tốt hơn không đảm bảo answer tốt hơn 100%, nhưng retrieval kém gần như chắc chắn làm answer kém. LLM không thể cite đúng tài liệu không được retrieve.

## 10. Production checklist

Một embedding setup dùng được trong production khi có đủ các điều kiện sau:

- Có eval set nội bộ tối thiểu 100-500 queries theo category; bài học dùng 20 queries chỉ là bản học tập.
- Có qrels review bởi người hiểu domain.
- Có BM25 hoặc hybrid baseline để so sánh.
- Có test riêng cho query không dấu, English-mix, acronym, số liệu và synonym.
- Có version metadata: `embedding_model`, `model_version`, `dimension`, `normalization`, `prefix_strategy`, `text_normalizer_version`, `chunking_version`, `index_version`.
- Không trộn vector từ nhiều model hoặc nhiều dimension trong cùng collection.
- Có migration plan khi đổi model: tạo index mới, backfill, shadow traffic, compare, cutover, rollback.
- Có timeout, retry, rate limit handling và batch size config.
- Có privacy review nếu gửi chunk/query ra managed provider.
- Có monitoring: latency, error rate, empty result rate, score distribution, query category, retrieval feedback.
- Có cost dashboard: indexing cost, query cost, vector DB storage, replicas, backup.

## 11. Dùng được trong production không?

Có, embedding models dùng được trong production và là thành phần lõi của RAG. Nhưng điều kiện là không được dùng theo kiểu "chọn một model rồi hy vọng". Cần:

1. Benchmark trên dữ liệu thật hoặc gần thật.
2. Có qrels và regression test cho retrieval.
3. Có hybrid baseline, đặc biệt với tiếng Việt và enterprise docs.
4. Có versioning và reindex strategy.
5. Có privacy, cost, latency, monitoring và rollback plan.
6. Có ngưỡng chất lượng theo use case, ví dụ `Recall@5 >= 0.90` cho support FAQ hoặc cao hơn cho domain rủi ro như legal/finance.

Best solution theo context:

| Context | Khuyến nghị |
|---|---|
| Prototype nhỏ, data không nhạy cảm | Managed API embedding + vector DB managed, đo nhanh |
| Enterprise tiếng Việt có acronym/mã lỗi | Hybrid BM25 + dense, reranker nếu cần |
| Data residency nghiêm ngặt | Self-host BGE/E5/Vietnamese model, private vector DB |
| Corpus rất lớn, cost nhạy | Benchmark model nhỏ hơn, quantization/index tuning, batch indexing |
| Legal/finance | Hybrid + reranker + citation strict + human-reviewed qrels |
| Traffic lớn và qrels đủ tốt | Cân nhắc fine-tune embedding hoặc distill model |

## 12. Liên kết với các ngày tiếp theo

- Day 33 dùng kết quả benchmark để chọn vector DB config và metric.
- Day 34 thay đổi chunking sẽ làm retrieval metric thay đổi, vì vậy phải re-run benchmark.
- Day 35 metadata và permission filter phải chạy trước hoặc cùng retrieval để tránh leak dữ liệu.
- Day 36 mở rộng dense-only thành hybrid search.
- Day 37 thêm reranking khi top K có nhiều near-miss.
- Day 39 biến benchmark hôm nay thành retrieval evaluation suite nghiêm túc hơn.

## Tự kiểm tra

1. Vì sao cosine và dot product có thể cho ranking giống nhau khi vector đã normalize?
2. Vì sao embedding không thay thế BM25 trong RAG tiếng Việt?
3. Qrels khác gì với một danh sách query demo?
4. Khi đổi embedding model, vì sao phải tạo index mới?
5. Với 1M chunks và vector 1024 chiều float32, raw vector storage khoảng bao nhiêu?
6. Dùng managed API embedding trong production cần review những rủi ro nào?
7. Vì sao query không dấu cần nằm trong benchmark riêng?
