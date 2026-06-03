# Document: Production Notes cho Embedding Benchmark tiếng Việt

## 1. Reference architecture

```text
                 Indexing path
Documents -> Parser -> Chunker -> Text normalizer -> Embedding worker
          -> Vector index + BM25 index + metadata store

                 Query path
User query -> Query normalizer -> Dense embed -> Vector search
           -> BM25 search -> Score fusion -> Permission filter
           -> Optional reranker -> Context builder -> LLM
```

Điểm dễ sai: permission filter phải được thiết kế rõ. Với tài liệu enterprise, đừng retrieve chunk mà user không có quyền rồi mới hy vọng LLM không dùng. Filter theo tenant, workspace, ACL, classification hoặc document visibility phải là một phần của retrieval plan.

## 2. Text normalization cho tiếng Việt

Normalization nên vừa đủ, không phá mất thông tin quan trọng.

Nên làm:

- Chuẩn hóa Unicode về NFC/NFKC theo pipeline thống nhất.
- Trim whitespace, collapse nhiều khoảng trắng.
- Lowercase cho BM25 field phụ nếu phù hợp.
- Tạo thêm field không dấu cho sparse search hoặc query expansion.
- Giữ nguyên field gốc để hiển thị và citation.
- Giữ mã lỗi, số hợp đồng, mã sản phẩm, SKU, `%`, `+`, `#`, `/` nếu có ý nghĩa.

Không nên làm bừa:

- Xóa toàn bộ dấu câu trong legal/finance docs.
- Xóa số vì "không semantic".
- Xóa dấu tiếng Việt khỏi document gốc rồi chỉ index bản không dấu.
- Apply normalizer khác nhau giữa indexing và query nhưng không version lại.

Metadata nên lưu:

```json
{
  "text_normalizer_version": "vn-normalizer-2026-05-10",
  "source_text_checksum": "sha256:...",
  "indexed_text_checksum": "sha256:..."
}
```

## 3. Qrels schema

Qrels là ground truth cho retrieval. Mỗi query cần biết chunk nào đúng.

Schema gợi ý:

```json
{
  "query_id": "q001",
  "query": "toi muon hoan tien goi Pro",
  "category": "billing",
  "difficulty": ["no-diacritic", "synonym"],
  "relevant_chunk_ids": ["refund_policy"],
  "notes": "User gõ không dấu, tài liệu có dấu."
}
```

Với production, qrels nên có:

- Reviewer hoặc source tạo nhãn.
- Ngày cập nhật.
- Domain/category.
- Độ khó.
- Expected citation nếu dùng cho RAG answer eval.
- Negative notes: chunk nào nhìn giống nhưng không đủ đúng.

## 4. Metrics definition

Với một query:

```text
ranked = ["a", "b", "c", "d", "e"]
relevant = {"c", "e"}
```

Hit@3:

```text
top3 = {"a", "b", "c"}
hit@3 = 1 vì có "c"
```

Recall@5:

```text
top5 lấy được {"c", "e"} trong 2 relevant chunks
recall@5 = 2 / 2 = 1.0
```

MRR@5:

```text
relevant đầu tiên là "c" ở rank 3
mrr@5 = 1 / 3 = 0.333
```

Report không nên chỉ có aggregate. Phải có fail cases:

| query_id | query | difficulty | expected | top_5 | lỗi |
|---|---|---|---|---|---|
| q007 | API tra ve 429 nghia la gi | acronym/exact-code | api_rate_limit | password_reset,... | Dense không ưu tiên mã lỗi |

## 5. Hybrid baseline

Dense search mạnh ở semantic similarity. BM25 mạnh ở exact lexical match. Tiếng Việt production thường cần cả hai.

Score fusion đơn giản:

```text
dense_rank_score = 1 / (k + dense_rank)
bm25_rank_score = 1 / (k + bm25_rank)
final_score = alpha * dense_rank_score + (1 - alpha) * bm25_rank_score
```

Đây là Reciprocal Rank Fusion phiên bản có trọng số. Bắt đầu với:

```text
k = 60
alpha = 0.5
```

Sau đó tune theo qrels. Không tune trên test set cuối; hãy tách dev/test nếu eval set đủ lớn.

## 6. Versioning và migration

Không coi embedding là config nhỏ. Đổi model là đổi schema retrieval.

Metadata bắt buộc:

```json
{
  "embedding_model": "intfloat/multilingual-e5-large",
  "embedding_model_revision": "pinned-revision-or-provider-version",
  "dimension": 1024,
  "similarity_metric": "cosine",
  "normalized": true,
  "prefix_strategy": "e5-query-passage",
  "chunking_version": "chunk-v3",
  "index_version": "kb-embedding-2026-05-10"
}
```

Migration plan:

1. Tạo collection/index mới.
2. Backfill embeddings bằng model mới.
3. Chạy offline benchmark trên cùng qrels.
4. Chạy shadow traffic nếu có query log.
5. So sánh retrieval quality, latency, cost, error rate.
6. Cutover theo feature flag.
7. Giữ index cũ đủ lâu để rollback.

Không làm:

- Upsert vector mới vào collection cũ nếu dimension/model khác.
- Xóa index cũ trước khi có report regression.
- Chỉ test vài query đẹp trong notebook rồi deploy.

## 7. Privacy và compliance

Nếu dùng managed embedding API, cần trả lời:

- Query/chunk có chứa PII, secrets, contract, medical/legal/finance data không?
- Provider có data retention thế nào?
- Có dùng dữ liệu để train không?
- Region xử lý dữ liệu ở đâu?
- Có cần DPA, BAA hoặc điều khoản enterprise không?
- Log nội bộ của mình có lưu raw query/chunk không?

Biện pháp giảm rủi ro:

- Redact PII trước khi gửi nếu business cho phép.
- Không log raw sensitive text ở level info.
- Tách tenant và ACL trong metadata.
- Encrypt backups.
- Dùng self-host nếu data residency hoặc policy không cho phép external API.

## 8. Latency và cost model

Online path:

```text
query embedding latency + vector search latency + BM25 latency + rerank latency + LLM latency
```

Embedding query thường chỉ là một phần của latency, nhưng p95 tăng mạnh nếu:

- Provider throttling hoặc network chậm.
- Self-host model không batch tốt.
- Model quá lớn so với CPU/GPU.
- Query path gọi embedding nhiều lần vì query rewrite/multi-query.

Indexing path:

```text
num_chunks * embedding_cost_per_chunk + vector_db_upsert + index build time
```

Cost cần tính riêng:

- Initial backfill.
- Incremental updates.
- Reindex khi đổi model/chunking.
- Query embedding.
- Vector DB storage/replicas/backups.
- GPU/CPU serving nếu self-host.

## 9. Report template

```markdown
# Embedding Benchmark Report

## Dataset

- Corpus: <số document>, <số chunk>, domain <...>
- Queries: <số query>, categories <...>
- Qrels reviewer: <ai/nhóm nào>
- Ngày chạy: <yyyy-mm-dd>

## Config

| Model | Dimension | Metric | Normalize | Prefix | Serving | Notes |
|---|---:|---|---|---|---|---|
| model-a | 1024 | cosine | yes | query/passsage | local GPU | ... |

## Metrics

| Model | Hit@1 | Hit@3 | Recall@5 | MRR@5 | p50 embed ms | p95 embed ms | Storage/1M chunks |
|---|---:|---:|---:|---:|---:|---:|---:|
| model-a | 0.70 | 0.85 | 0.90 | 0.76 | 45 | 120 | 4.1 GB |

## Failure Analysis

| Model | Query | Difficulty | Expected | Top 5 | Finding |
|---|---|---|---|---|---|
| model-a | ... | no-diacritic | ... | ... | ... |

## Decision

- Selected model: <model>
- Reason: <quality/cost/latency/privacy>
- Production conditions: <hybrid/reranker/versioning/monitoring>
- Rollback plan: <old index/version>
```

## 10. Review checklist

- [ ] Có qrels, không chỉ có query demo.
- [ ] Có ít nhất một model managed hoặc một baseline dễ vận hành.
- [ ] Có ít nhất một open-source multilingual model.
- [ ] Có test no-diacritic query.
- [ ] Có test acronym, number, mã lỗi.
- [ ] Có BM25 hoặc hybrid baseline.
- [ ] Có Hit@1, Hit@3, Recall@5, MRR@5.
- [ ] Có latency p50/p95.
- [ ] Có storage estimate theo dimension.
- [ ] Có phân tích fail cases, không chỉ bảng aggregate.
- [ ] Có production decision và điều kiện deploy.
- [ ] Có versioning và reindex plan.
