# Document: Reranking Cheat Sheet Và Runbook

## 1. Mental model nhanh

Reranking là bước xếp hạng lại một candidate pool nhỏ hơn sau retrieval.

```text
Hybrid retrieval = recall layer
Reranker         = precision layer
Context builder  = token/citation layer
LLM              = answer layer
```

Ba câu cần hỏi trước khi thêm reranker:

1. Candidate pool trước rerank có chứa chunk đúng chưa?
2. Reranker có đưa chunk đúng lên top context tốt hơn không?
3. Latency/cost tăng thêm có đáng với chất lượng tăng thêm không?

## 2. Decision matrix

| Context | Lựa chọn hợp lý | Lý do |
|---|---|---|
| Prototype hoặc eval nhanh | Cohere Rerank hoặc managed rerank API | Ít vận hành, tạo baseline nhanh |
| Dữ liệu nhạy cảm, không được gửi ra ngoài | Self-host BGE reranker | Kiểm soát privacy và network boundary |
| Traffic thấp, quality quan trọng | Cross-encoder rerank top 50/100 | Latency tăng nhưng chấp nhận được |
| Traffic cao, SLA chặt | Rerank top 20/50 hoặc conditional rerank | Giữ p95 ổn định hơn |
| Corpus nhỏ, retrieval đã rất tốt | Có thể chưa cần reranker | Tránh thêm complexity khi metric không tăng |
| Legal/compliance/support policy | Nên rerank và eval kỹ | Cần top context chính xác, citation đúng |

## 3. Cấu hình khởi điểm

| Tham số | Giá trị khởi điểm | Khi tăng | Khi giảm |
|---|---:|---|---|
| `bm25_top_k` | 50 | Query nhiều keyword, cần recall cao | BM25 nhiều nhiễu |
| `vector_top_k` | 50 | Semantic query đa dạng | Latency search cao |
| `rrf_k` | 60 | Muốn giảm ảnh hưởng rank đầu | Ít khi cần đổi sớm |
| `rerank_k` | 50 | Recall@50 tốt và cần top precision hơn | p95/cost cao |
| `final_k` | 5-10 | Câu trả lời cần nhiều evidence | Prompt bị noise hoặc quá dài |
| `max_tokens_per_doc` | 512-1200 | Chunk ngắn bị thiếu context | Reranker chậm hoặc truncate sai |
| `rerank_timeout_ms` | 500-1500 | SLA rộng, quality ưu tiên | Chat cần phản hồi nhanh |

Không copy cấu hình này vào production mà không benchmark. Nó là điểm bắt đầu để chạy eval.

## 4. Metrics bắt buộc

| Metric | Nơi đo | Ý nghĩa |
|---|---|---|
| Recall@50 before rerank | Candidate pool | Retriever có tìm thấy chunk đúng không |
| Recall@5 after rerank | Final context | Reranker có đưa chunk đúng vào prompt không |
| MRR@10 | Final ranking | Chunk đúng đầu tiên đứng cao không |
| nDCG@10 | Final ranking | Ranking có tôn trọng relevance nhiều mức không |
| Context precision | Context builder | Prompt ít chunk nhiễu không |
| Citation correctness | Answer audit | Câu trả lời cite đúng nguồn không |
| p50/p95/p99 rerank latency | Runtime | Có đạt SLA không |
| Fallback rate | Runtime | Reranker fail/timeout nhiều không |
| Cost per 1K queries | Finance/ops | Có scale được theo traffic không |

## 5. Eval report template

```markdown
| Pipeline | Recall@5 | MRR@10 | nDCG@10 | p95 search ms | p95 rerank ms | p95 total ms | Cost/1K | Note |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Hybrid only | | | | | 0 | | | |
| Hybrid + BGE rerank top 50 | | | | | | | | |
| Hybrid + Cohere rerank top 50 | | | | | | | | |
| Hybrid + rerank top 100 | | | | | | | | |
```

Phân tích bắt buộc sau bảng:

- 5 query improved: vì sao reranker giúp?
- 5 query regressed: vì sao reranker làm tệ hơn?
- Nhóm query nào hưởng lợi nhiều nhất?
- Nhóm query nào cần sửa chunking/retrieval thay vì rerank?
- Cấu hình nào đạt quality tốt nhất trong latency budget?

## 6. Runbook rollout

1. Chốt query eval set và qrels.
2. Chạy baseline Hybrid Search từ Day 36.
3. Thêm reranker phía sau RRF, phía sau ACL filter.
4. Chạy offline eval với nhiều cấu hình `rerank_k`: 20, 50, 100.
5. Benchmark latency với độ dài chunk thật.
6. Chạy security test: tenant A không thể rerank chunk tenant B.
7. Shadow traffic: log ranking mới nhưng chưa dùng để trả lời user.
8. So sánh answer quality và citation correctness.
9. Bật feature flag cho internal users hoặc một phần traffic.
10. Theo dõi p95/p99, fallback rate, cost và complaint rate.
11. Rollback nếu latency vượt SLA hoặc regression ở query rủi ro cao.

## 7. Observability

Log mỗi request nên có:

- `query_id`, `tenant_id`, `user_role_group`.
- `retriever_versions`: BM25 config, embedding model, index version.
- `retrieve_k`, `rerank_k`, `final_k`.
- Candidate ids trước rerank và sau rerank.
- Retrieval score, RRF rank, reranker score.
- Reranker provider, model version, timeout, retry count.
- Latency từng stage: normalize, BM25, vector, RRF, ACL filter, rerank, context build.
- Fallback reason nếu có.

Không log raw query hoặc raw chunk nếu chứa PII mà chưa có policy. Có thể log hash, redacted text hoặc sample theo allowlist.

## 8. Failure modes

| Lỗi | Dấu hiệu | Cách xử lý |
|---|---|---|
| Candidate pool thiếu chunk đúng | Recall@50 thấp | Sửa retrieval, chunking, embedding, BM25 hoặc RRF |
| Reranker làm tụt ranking | MRR giảm, query regressed nhiều | Đổi model, format input, fine-tune hoặc threshold |
| ACL leak | Candidate không đúng quyền xuất hiện trong log/API/prompt | Filter trước rerank, thêm regression test |
| Latency spike | p95/p99 tăng mạnh | Giảm `rerank_k`, batch tốt hơn, timeout/fallback |
| Cost spike | Cost/1K queries tăng | Conditional rerank, cache, giảm candidate/text length |
| Score khó hiểu | Threshold fail khi đổi model | Calibrate score theo eval set, không xem score là confidence |
| Citation sai | Answer cite nhầm source | Giữ stable `chunk_id`, `source_uri`, page metadata qua mọi stage |

## 9. Managed vs self-host checklist

Managed API phù hợp khi:

- Team cần ship nhanh.
- Data policy cho phép gửi query/chunk ra provider.
- Traffic chưa quá lớn hoặc cost dự đoán được.
- SLA của provider và rate limit phù hợp.

Self-host phù hợp khi:

- Dữ liệu nhạy cảm hoặc yêu cầu data residency chặt.
- Traffic đủ lớn để tối ưu cost bằng hạ tầng riêng.
- Team có năng lực vận hành CPU/GPU inference.
- Cần fine-tune hoặc kiểm soát model version chặt.

## 10. Production readiness checklist

- [ ] Có qrels và eval set đại diện.
- [ ] Có baseline Hybrid Search trước khi thêm reranker.
- [ ] Recall@50 hoặc Recall@100 trước rerank đủ cao.
- [ ] Reranker cải thiện Recall@5, MRR@10 hoặc metric mục tiêu.
- [ ] Đã đo latency p50/p95/p99 bằng dữ liệu thật.
- [ ] Đã lọc tenant, ACL, deleted, index version trước rerank.
- [ ] Có timeout và fallback về retrieval rank.
- [ ] Có feature flag và rollback path.
- [ ] Có model/config versioning.
- [ ] Có cost estimate cho traffic hiện tại và 3-6 tháng tới.
- [ ] Có policy logging cho PII.
- [ ] Có citation correctness test.

## 11. Quiz nhanh

1. Vì sao reranker không thể sửa lỗi khi chunk đúng không nằm trong top 50 candidate?
2. Khi nào nên dùng cross-encoder thay vì chỉ dùng bi-encoder?
3. Vì sao phải filter ACL trước khi gọi managed rerank API?
4. Nếu Recall@50 thấp nhưng MRR@10 sau rerank cao, bạn kết luận gì?
5. Nếu MRR tăng nhưng p95 latency vượt SLA, bạn thử những thay đổi nào trước?

Đáp án gợi ý:

1. Reranker chỉ sắp xếp candidate có sẵn, không search lại toàn corpus.
2. Khi top context precision, citation quality hoặc câu hỏi có nuance quan trọng hơn latency tăng thêm.
3. Vì gửi chunk không đúng quyền ra ngoài đã là data leak, dù sau đó không đưa vào prompt.
4. Reranker tốt trên candidate có sẵn, nhưng retrieval vẫn bỏ sót nhiều đáp án. Cần cải thiện retrieval/chunking.
5. Giảm `rerank_k`, dedupe tốt hơn, truncate text, batching, cache, conditional rerank hoặc đổi model nhỏ hơn.

## 12. Câu trả lời production readiness

Reranker dùng được trong production, nhưng không nên bật chỉ vì "nghe có vẻ tốt hơn". Quyết định production cần dựa trên eval và SLA:

- Nếu metric tăng rõ, latency/cost nằm trong budget, privacy được xử lý và có fallback, nên dùng.
- Nếu metric không tăng hoặc candidate recall thấp, hãy sửa retrieval trước.
- Nếu data policy không cho gửi dữ liệu ra ngoài, chỉ dùng managed API khi có approval rõ, còn lại self-host.
- Nếu p95 vượt SLA, dùng conditional rerank hoặc giảm candidate thay vì hy sinh toàn bộ trải nghiệm chat.
