# Day 1: AI Mindset cho Senior SE

## Mục tiêu của ngày học

Sau bài này, bạn cần làm được 5 việc:

1. Phân biệt được rule-based system, classical ML system, Deep Learning system, LLM application và RAG system.
2. Biết khi nào nên dùng AI, khi nào nên dùng rule/SQL/search truyền thống, và khi nào chưa nên làm AI.
3. Map được các khái niệm AI về tư duy Senior Software Engineer: build, artifact, API contract, testing, observability, rollback, SLA.
4. Nhận diện được các failure mode đặc thù của AI system trong production.
5. Phân tích được 5 bài toán thực tế: fraud detection, customer churn, chatbot CSKH, search tài liệu nội bộ, recommendation sản phẩm.

## Cách học đề xuất trong 2 giờ

| Thời lượng | Việc cần làm | Output |
|---:|---|---|
| 10 phút | Đọc TL;DR và mental model | Nắm được AI system khác backend service ở điểm nào |
| 35 phút | Đọc `document.md` phần 1-5 | Phân biệt rule, ML, DL, LLM, RAG |
| 25 phút | Đọc phần production, trade-off, performance | Biết cách ra quyết định kỹ thuật |
| 40 phút | Làm `exercise.md` | Hoàn thành decision record cho 5 bài toán |
| 10 phút | Tự kiểm tra và ghi lại gap | Biết phần nào cần học sâu ở Day 2-8 |

## TL;DR

AI system không chỉ là "gọi model". Với Senior SE, cách nhìn đúng là:

```text
AI feature = data contract + model/prompt/retriever + policy layer + evaluation + observability + rollback
```

Khác biệt lớn nhất so với backend truyền thống là AI thường trả output có tính xác suất. Unit test vẫn cần, nhưng không đủ. Bạn phải thêm evaluation dataset, metric threshold, segment-level analysis, drift monitoring, cost monitoring và human review cho các use case rủi ro cao.

Nguyên tắc thực dụng:

- Nếu rule đơn giản, ổn định, dễ explain và latency rất thấp: dùng rule.
- Nếu bài toán là prediction trên tabular data: bắt đầu bằng classical ML như Logistic Regression, Random Forest hoặc XGBoost.
- Nếu input là text/image/audio lớn và feature thủ công khó: cân nhắc Deep Learning.
- Nếu cần hiểu/ngôn ngữ/tóm tắt/trích xuất/generation/tool calling: cân nhắc LLM.
- Nếu cần trả lời theo tài liệu riêng, cập nhật, có citation: ưu tiên RAG hơn fine-tuning.
- Nếu quyết định ảnh hưởng tiền, pháp lý, quyền truy cập hoặc trải nghiệm quan trọng: cần human-in-the-loop, threshold thận trọng, audit log và fallback.

## Bản đồ nội dung

- Học phần chính: [document.md](./document.md)
- Bài tập thực hành: [exercise.md](./exercise.md)

## Deliverable cuối ngày

Bạn nên tạo được một file ghi chú riêng, ví dụ `notes/day-01-ai-decision-record.md`, gồm:

- Bảng phân tích 5 bài toán thực tế.
- Approach được chọn cho từng bài toán.
- Vì sao không chọn approach khác.
- Input/output contract.
- Production risks.
- Monitoring metrics.
- Fallback/rollback plan.

## Dùng được trong production không? Nếu có thì cần điều kiện gì?

Có, mindset và checklist trong bài này dùng được trong production. Nhưng đây là framework ra quyết định, không phải implementation hoàn chỉnh.

Điều kiện để dùng production:

- Có business objective rõ ràng và metric đo được.
- Có baseline không-AI hoặc baseline đơn giản để so sánh.
- Có data contract, input validation và output contract.
- Có evaluation dataset đại diện cho production traffic.
- Có monitoring cho latency, error rate, cost, output quality và drift.
- Có owner cho model/prompt/retriever, có versioning và rollback.
- Có policy cho privacy, PII, security, compliance và human review khi rủi ro cao.

## Checklist hoàn thành

- [ ] Tôi giải thích được vì sao AI output thường không deterministic.
- [ ] Tôi phân biệt được rule-based, ML, DL, LLM và RAG.
- [ ] Tôi biết ít nhất 3 trường hợp không nên dùng AI.
- [ ] Tôi biết vì sao model nên trả score, còn business policy mới quyết định action.
- [ ] Tôi có bảng phân tích 5 bài toán trong `exercise.md`.
- [ ] Với mỗi bài toán, tôi có trade-off, production risk, metric và fallback.

