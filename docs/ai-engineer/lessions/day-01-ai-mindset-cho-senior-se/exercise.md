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

### Việc phải nộp

- Chọn ít nhất một hard rule, một ML signal và vùng manual review.
- Định nghĩa cost của false positive/false negative.
- Đề xuất split, audit log, fallback và 5 metrics cần monitor.

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

### Việc phải nộp

- Định nghĩa chính xác `churn` và thời điểm prediction.
- Chọn 8-12 feature chỉ dùng dữ liệu có trước prediction time.
- Đề xuất cách đo model quality và uplift của retention action.

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

### Việc phải nộp

- Vẽ flow retrieval, permission, generation, citation và escalation.
- Viết abstain policy cho câu hỏi thiếu nguồn hoặc confidence thấp.
- Đề xuất safety test và quality/business metrics.

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

### Việc phải nộp

- Chọn keyword, vector hay hybrid search và giải thích.
- Chỉ rõ vị trí ACL filter, freshness strategy và fallback.
- Thiết kế tối thiểu 20 query relevance test.

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

### Việc phải nộp

- Định nghĩa event schema cho impression, click, cart và purchase.
- Thiết kế cold-start fallback và business-rule stage.
- Đề xuất A/B metrics ngắn hạn lẫn guardrail dài hạn.

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

Sau khi làm xong, tự điền bảng quyết định sau:

| Problem | Best approach | Vì sao | Production blocker lớn nhất | Fallback |
|---|---|---|---|---|
| Fraud detection | | | | |
| Customer churn | | | | |
| Chatbot CSKH | | | | |
| Internal search | | | | |
| Recommendation | | | | |
