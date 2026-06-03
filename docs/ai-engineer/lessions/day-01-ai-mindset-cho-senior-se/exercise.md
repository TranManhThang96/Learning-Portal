# Exercise: Phân tích 5 bài toán AI theo production mindset

## Mục tiêu

Bạn sẽ phân tích 5 bài toán thực tế:

1. Fraud detection.
2. Customer churn prediction.
3. Chatbot CSKH.
4. Search tài liệu nội bộ.
5. Recommendation sản phẩm.

Với mỗi bài toán, bạn phải quyết định:

- Dùng rule, ML, Deep Learning, RAG, LLM hay hybrid?
- Vì sao chọn approach đó?
- Vì sao không chọn approach khác?
- Risk production là gì?
- Cần monitor gì?
- Dùng được trong production không? Nếu có thì cần điều kiện gì?

## Template bắt buộc

Copy template này cho từng bài toán:

```markdown
## Problem: <tên bài toán>

### 1. Business objective

Mục tiêu business là gì? Tối ưu revenue, giảm risk, giảm ticket, tăng conversion hay tăng retention?

### 2. Output cần tạo

Decision / score / ranking / text answer / structured JSON / citation answer.

### 3. Candidate approaches

- Rule-based:
- Classical ML:
- Deep Learning:
- LLM:
- RAG:
- Hybrid:

### 4. Best solution theo context

Chọn approach chính và giải thích vì sao.

### 5. Vì sao không chọn approach khác?

Nêu trade-off cụ thể.

### 6. Input/output contract

Input fields:

Output fields:

Error/fallback behavior:

### 7. Performance budget

p95 latency:

Throughput:

Cost/request:

### 8. Production risks

Security:

Privacy:

Data quality:

False positive / false negative:

Drift:

Operational risk:

### 9. Monitoring

System metrics:

Quality metrics:

Business metrics:

Cost metrics:

### 10. Fallback/rollback

Fallback khi model/LLM/retriever lỗi:

Rollback strategy:

### 11. Dùng được trong production không?

Có/Không. Nếu có, cần điều kiện gì?
```

## Bài 1: Fraud detection

### Context

Bạn làm cho hệ thống payment. Mỗi transaction cần được approve, reject hoặc đưa vào manual review. Fraud rate thấp, chỉ khoảng 0.3-1%, nhưng thiệt hại mỗi case có thể cao. False positive làm user thật bị block, false negative làm mất tiền.

### Gợi ý solution

Best starting solution thường là hybrid:

```text
hard rules
  -> ML fraud score
  -> policy threshold
  -> allow/review/reject
```

Vì sao:

- Rule tốt cho hard constraint: country mismatch, velocity limit, blacklist, suspicious BIN.
- ML tốt cho việc kết hợp nhiều signal yếu.
- Manual review cần cho vùng không chắc chắn.
- Không nên để LLM quyết định fraud trực tiếp vì latency/cost/explainability kém và không phù hợp với tabular real-time scoring.

### Production answer mẫu

Dùng được trong production nếu:

- Có historical transaction + chargeback label đáng tin cậy.
- Có time-based split để tránh data leakage.
- Có threshold khác nhau cho `review` và `reject`.
- Có audit log cho từng decision.
- Có monitoring FP/FN theo segment, merchant, country, payment method.
- Có fallback rule-based khi model service timeout.

## Bài 2: Customer churn prediction

### Context

SaaS B2B muốn biết customer nào có khả năng hủy trong 30-60 ngày tới để Customer Success can thiệp. Dữ liệu gồm usage, billing, ticket, contract, account age, NPS.

### Gợi ý solution

Best starting solution thường là classical ML:

```text
customer features -> churn probability -> retention policy
```

Model có thể bắt đầu bằng Logistic Regression để explainable, sau đó thử tree-based model như Random Forest/XGBoost nếu có đủ dữ liệu.

Không nên bắt đầu bằng LLM vì:

- Bài toán chính là tabular prediction.
- LLM không tự có dữ liệu usage/billing.
- Cost và latency không cần thiết.

LLM có thể hỗ trợ phụ trợ:

- Tóm tắt lý do churn từ ticket/customer notes.
- Draft email retention cá nhân hóa.

### Production answer mẫu

Dùng được trong production nếu:

- Label churn được định nghĩa rõ: cancel, downgrade, không renew, hay inactive.
- Feature được tính tại thời điểm trước churn, không leak tương lai.
- Có calibration để score phản ánh xác suất tương đối đáng tin.
- Có A/B test hoặc holdout để đo uplift từ retention action.
- Có guardrail để không spam customer bằng offer không phù hợp.

## Bài 3: Chatbot CSKH

### Context

Bạn cần chatbot trả lời câu hỏi về chính sách hoàn tiền, billing, account, troubleshooting. Tài liệu nội bộ thay đổi thường xuyên. Câu trả lời sai có thể làm user hiểu nhầm chính sách.

### Gợi ý solution

Best starting solution thường là RAG + LLM + guardrails:

```text
question
  -> classify intent/safety
  -> retrieve policy docs with permission filter
  -> generate answer with citations
  -> validate answer
  -> escalate when uncertain
```

Không nên fine-tune để nhồi policy vì:

- Policy thay đổi thường xuyên.
- Fine-tuning không đảm bảo model nhớ đúng từng chi tiết.
- Khó citation.

### Production answer mẫu

Dùng được trong production nếu:

- Corpus policy được quản lý version và có owner.
- Retrieval có permission filtering.
- Bot phải cite source hoặc nói không biết.
- Có escalation sang human support.
- Có prompt injection test.
- Có monitoring hallucination, unresolved rate, CSAT, deflection rate.

## Bài 4: Search tài liệu nội bộ

### Context

Công ty có nhiều tài liệu trong wiki, Google Drive, Slack export, runbook. User muốn search tự nhiên, ví dụ "quy trình rollback payment service".

### Gợi ý solution

Best starting solution thường là hybrid search:

```text
query
  -> permission filter
  -> BM25 keyword search
  -> vector search
  -> merge/rerank
  -> return documents/snippets
```

Nếu cần answer trực tiếp, thêm RAG ở bước sau. Nhưng search engine tốt không nhất thiết phải luôn generate answer.

Trade-off:

- BM25 tốt với exact term, mã lỗi, tên service.
- Vector search tốt với semantic query.
- Reranking cải thiện relevance nhưng tăng latency/cost.
- Permission filtering là bắt buộc, không phải optional.

### Production answer mẫu

Dùng được trong production nếu:

- Có indexing pipeline ổn định.
- Có ACL/permission filter trước khi trả kết quả hoặc đưa vào prompt.
- Có freshness strategy cho tài liệu mới/cũ.
- Có relevance evaluation dataset.
- Có fallback keyword search nếu vector index lỗi.

## Bài 5: Recommendation sản phẩm

### Context

E-commerce muốn recommend sản phẩm trên homepage, product detail page và email. Có user mới, item mới, seasonal trend và business constraint như margin/inventory.

### Gợi ý solution

Best starting solution thường là hybrid:

```text
candidate generation
  -> ranking model
  -> business rules
  -> diversity/filtering
  -> fallback for cold start
```

Approach có thể gồm:

- Popular/category-based fallback.
- Collaborative filtering khi có interaction data.
- Content-based recommendation khi item metadata tốt.
- Ranking ML khi có click/add-to-cart/purchase label.

LLM có thể hỗ trợ tạo explanation hoặc enrich metadata, nhưng không nên là ranking engine chính trong hot path nếu traffic lớn.

### Production answer mẫu

Dùng được trong production nếu:

- Có event tracking đáng tin: impression, click, add-to-cart, purchase.
- Có chống feedback loop và filter bubble.
- Có fallback cho user mới/item mới.
- Có business rules cho inventory, banned items, margin, compliance.
- Có A/B test đo CTR, conversion, revenue, long-term retention.

## Mini design review checklist

Trước khi coi một AI feature là production-ready, hãy kiểm tra:

- [ ] Có business metric rõ ràng.
- [ ] Có baseline đơn giản.
- [ ] Có input/output contract.
- [ ] Có offline evaluation dataset.
- [ ] Có metric theo segment, không chỉ metric trung bình.
- [ ] Có latency và cost budget.
- [ ] Có log đủ debug theo request/model/prompt/retriever version.
- [ ] Có fallback khi dependency AI lỗi.
- [ ] Có rollback cho model/prompt/threshold/index.
- [ ] Có security/privacy review.
- [ ] Có human-in-the-loop cho case rủi ro cao.

## Câu hỏi tự kiểm tra

1. Khi nào rule-based tốt hơn ML?
2. Vì sao fraud detection không nên đánh giá bằng accuracy đơn thuần?
3. Vì sao model nên trả score thay vì trực tiếp execute business action?
4. Vì sao RAG thường phù hợp hơn fine-tuning cho chatbot hỏi đáp policy?
5. Với search tài liệu nội bộ, permission filtering nên đặt trước hay sau generation? Vì sao?
6. Khi nào LLM không phù hợp với request path?
7. Data drift và concept drift khác nhau thế nào?
8. Nếu AI provider timeout, user experience nên degrade ra sao?

## Output kỳ vọng

Sau khi làm xong, bạn nên có một bảng quyết định như sau:

| Problem | Best approach | Vì sao | Production blocker lớn nhất | Fallback |
|---|---|---|---|---|
| Fraud detection | Hybrid rule + ML + review | Low fraud rate, high risk, cần explain | Label leakage/FP cost | Rule + manual review |
| Customer churn | Classical ML | Tabular prediction, đo ROI được | Label definition/drift | Heuristic retention |
| Chatbot CSKH | RAG + LLM | Cần answer theo policy cập nhật | Hallucination/injection | Human support |
| Internal search | Hybrid BM25 + vector | Exact + semantic search | Permission leakage | BM25 |
| Recommendation | Ranking ML + rules | Personalization + business constraints | Feedback loop/cold start | Popular/category |

