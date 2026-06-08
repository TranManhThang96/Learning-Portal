# Day 1: AI Mindset cho Senior SE

Day 00 đã cho bạn bức tranh nghề AI Engineer và các nhóm hệ thống AI hiện nay. Day 1 chuyển từ “AI có những gì?” sang “với một bài toán cụ thể, nên chọn rule, ML, Deep Learning, LLM, RAG hay không dùng AI?”. Day 2 sẽ cung cấp math vừa đủ để hiểu các score và phép tối ưu được nhắc trong bài này.

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
| 50 phút | Học phần 1-7 trong bài này | Phân biệt rule, ML, DL, LLM, RAG và cách đánh giá |
| 20 phút | Học phần architecture, performance, security | Biết cách ra quyết định kỹ thuật |
| 40 phút | Làm `exercise.md` | Hoàn thành decision record cho 5 bài toán |

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

## 1. Deterministic và probabilistic khác nhau ở đâu?

Backend truyền thống thường được thiết kế quanh logic **deterministic**: với cùng input, code và dependency, ta kỳ vọng cùng output. AI/ML thường là **probabilistic**: model học quy luật thống kê từ dữ liệu và luôn có xác suất sai.

```text
Backend:
input hợp lệ + code đúng -> output kỳ vọng

AI system:
input + data distribution + model/prompt/retriever version
  -> score/output có xác suất đúng hoặc sai
```

`Probabilistic` không có nghĩa là hệ thống tùy tiện. Nó có nghĩa ta phải đo chất lượng trên nhiều mẫu, định nghĩa ngưỡng chấp nhận và thiết kế fallback cho case model không chắc.

Hãy luôn hỏi:

1. Mục tiêu business và quyết định downstream là gì?
2. Sai dương tính và sai âm tính tốn bao nhiêu?
3. Có baseline không-AI đơn giản hơn không?
4. Input/output contract là gì?
5. Chất lượng được đo offline và online thế nào?
6. Có rollback, audit và human review không?

## 2. Rule-based, ML, Deep Learning, LLM và RAG

### 2.1. Rule-based system

**Rule-based system** là hệ thống mà engineer viết trực tiếp logic bằng code, SQL, workflow hoặc configuration.

```python
from dataclasses import dataclass
from enum import StrEnum


class Decision(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class Transaction:
    amount_usd: float
    country_mismatch: bool
    failed_attempts_24h: int
    account_age_days: int


def fraud_guardrail(tx: Transaction) -> tuple[Decision, list[str]]:
    reasons: list[str] = []
    if tx.amount_usd >= 10_000:
        reasons.append("large_amount")
    if tx.country_mismatch:
        reasons.append("country_mismatch")
    if tx.failed_attempts_24h >= 5:
        reasons.append("many_failed_attempts")
    if tx.account_age_days < 3 and tx.amount_usd >= 1_000:
        reasons.append("new_account_large_amount")

    if {"country_mismatch", "many_failed_attempts"} <= set(reasons):
        return Decision.BLOCK, reasons
    if reasons:
        return Decision.REVIEW, reasons
    return Decision.ALLOW, reasons
```

Ưu điểm: nhanh, rẻ, dễ test, dễ audit, không cần training data. Nhược điểm: khó bắt nhiều tín hiệu yếu và dễ thành mạng rule chồng chéo.

Best context: hard constraint, compliance rule, blacklist, rate limit, fallback hoặc bài toán chưa đủ dữ liệu.

### 2.2. Classical Machine Learning

**Machine Learning (ML)** học một function từ dữ liệu lịch sử thay vì yêu cầu engineer viết từng rule:

```text
features -> score/probability/prediction
```

`Feature` là tín hiệu đầu vào, ví dụ số ticket 30 ngày qua. `Label` là kết quả lịch sử muốn model học, ví dụ customer đã churn hay chưa.

Ví dụ:

```text
[tenure, usage_drop, failed_payments, ticket_count]
  -> churn_probability = 0.78
```

Không nên để model tự thực thi action. Model trả score; **policy layer** dùng score cùng cost, capacity và rule để quyết định:

```python
def retention_action(churn_probability: float, customer_ltv_usd: float) -> str:
    if churn_probability >= 0.80 and customer_ltv_usd >= 2_000:
        return "assign_success_manager"
    if churn_probability >= 0.65:
        return "send_retention_offer"
    return "no_action"
```

ML phù hợp với classification, regression, ranking và forecasting khi có dữ liệu/label đủ tốt. Nó không tự hiểu context ngoài những gì data thể hiện.

### 2.3. Deep Learning

**Deep Learning (DL)** là nhánh ML dùng neural network nhiều tầng để học representation từ dữ liệu gần-thô như text, image, audio hoặc sequence.

Nên cân nhắc khi:

- Feature thủ công quá khó.
- Data đủ lớn và pattern phức tạp.
- Classical ML đã chạm trần chất lượng.

Trade-off: compute và data lớn hơn, debug khó hơn, explainability thấp hơn, serving có thể cần GPU/batching/quantization. Với tabular business data, Logistic Regression hoặc tree ensemble thường vẫn là baseline tốt hơn.

### 2.4. LLM application

**Large Language Model (LLM)** là model ngôn ngữ lớn có thể sinh và xử lý text. LLM phù hợp với summarization, extraction, generation, chatbot, tool calling và workflow ngôn ngữ.

Rủi ro production:

- **Hallucination**: tạo thông tin nghe hợp lý nhưng sai.
- Output không ổn định hoàn toàn.
- Latency và cost tăng theo model/token.
- Context window có giới hạn.
- Prompt injection và tool abuse.

LLM output phải được xem như untrusted input. Nếu downstream cần JSON hoặc side effect, hãy validate schema, allowlist action, kiểm tra permission và yêu cầu approval với hành động rủi ro cao.

### 2.5. RAG

**Retrieval-Augmented Generation (RAG)** lấy tài liệu liên quan trước rồi đưa context đó cho LLM:

```text
question
  -> permission-aware retrieval
  -> relevant snippets
  -> grounded prompt
  -> answer + citations
```

RAG phù hợp với knowledge nội bộ thay đổi thường xuyên và cần citation. RAG không tự bảo đảm đúng: retrieval, chunking, metadata, permission filter, reranking và evaluation đều có thể sai.

## 3. Bảng chọn giải pháp

| Nhu cầu | Điểm bắt đầu tốt | Không nên mặc định chọn |
|---|---|---|
| Logic rõ, ổn định, cần audit | Rule/SQL/workflow | ML hoặc LLM |
| Tabular prediction có label | Classical ML baseline | LLM |
| Text/image/audio phức tạp, data lớn | Deep Learning | Rule thủ công dài |
| Tóm tắt, trích xuất, sinh text | LLM + validation | Model tabular |
| Hỏi đáp theo tài liệu riêng | RAG + LLM + citation | Fine-tune để “nhớ” tài liệu |
| Search mã lỗi/tên service | BM25/keyword hoặc hybrid search | LLM-only |
| Quyết định rủi ro cao | Hybrid rule + score + review | Auto-action không guardrail |

Nguyên tắc: chọn solution đơn giản nhất đạt business goal trong latency, cost và risk budget. “Model mạnh nhất” không đồng nghĩa “hệ thống tốt nhất”.

## 4. Map khái niệm AI về Software Engineering

| AI concept | SE analogy | Điều phải quản lý |
|---|---|---|
| Model | Versioned dependency/business function | Version, owner, changelog, rollback |
| Training | Build process | Data + code + config tạo artifact |
| Dataset | Source dependency | Quality, lineage, privacy, snapshot |
| Feature | Input contract | Type, semantics, availability time |
| Label | Expected outcome lịch sử | Definition, delay, noise, bias |
| Hyperparameter | Build config | Tracking để reproduce |
| Evaluation | Statistical test suite | Metric, confidence, segment |
| Inference | Runtime API | SLA, timeout, quota, fallback |
| Threshold | Policy config | Tune theo business cost |
| Prompt | Runtime/config logic | Version và regression test |
| Retriever/index | Knowledge read path | Freshness, relevance, ACL |
| Drift | Production distribution đổi | Monitor và retrain/review |

## 5. Training, inference và artifact

`Training` là quá trình học parameters từ dữ liệu. Output là **model artifact**, tức file/package chứa model đã train.

```text
raw data
  -> validation
  -> feature generation
  -> train/validation/test split
  -> train
  -> evaluate
  -> package/register artifact
  -> approval gate
```

Metadata tối thiểu: dataset snapshot, code version, feature version, algorithm, hyperparameters, metrics theo segment, artifact checksum và known limitations.

`Inference` là chạy artifact trên input mới:

```text
request
  -> authn/authz
  -> schema validation
  -> feature/retrieval
  -> model/LLM
  -> policy
  -> response
  -> audit + metrics
```

Log nên có request id, model/prompt/index version, latency từng bước, score, threshold/policy version, final action và fallback status. Không log raw PII nếu policy không cho phép.

## 6. Evaluation không chỉ là unit test

Unit test kiểm tra logic xác định. AI evaluation đo hành vi trên một tập mẫu đại diện:

```text
precision >= 0.82
recall >= 0.70
p95 latency <= 200 ms
cost / 1,000 requests <= budget
```

Các lớp kiểm tra:

| Test | Mục tiêu |
|---|---|
| Unit/integration | Feature, parser, policy, API contract |
| Data validation | Schema, null, range, distribution |
| Offline evaluation | Quality trên held-out/golden set |
| Segment evaluation | Phát hiện nhóm user bị tệ hơn |
| Safety/security | Injection, PII, tool abuse |
| Load/cost test | SLA và budget |
| Shadow/canary/A-B test | Xác nhận hành vi online |

Accuracy có thể đánh lừa. Nếu fraud rate là 0.5%, hệ thống luôn trả `not_fraud` đạt 99.5% accuracy nhưng bắt được 0 fraud. Day 6 sẽ học precision, recall, ROC-AUC và PR metrics chi tiết; hôm nay cần nhớ metric phải gắn với cost sai lầm.

## 7. Failure modes đặc thù

| Failure mode | Nghĩa | Cách giảm rủi ro |
|---|---|---|
| Data leakage | Train/evaluate dùng thông tin tương lai | Point-in-time review, split đúng |
| Train-serving skew | Transform lúc train khác lúc serve | Shared/versioned pipeline |
| Data drift | Distribution input đổi | Feature monitoring |
| Concept drift | Quan hệ input-outcome đổi | Monitor delayed labels, retrain |
| Hallucination | LLM bịa thông tin | RAG, citation, abstain |
| Permission leakage | Trả tài liệu user không được xem | Filter ACL trước generation |
| Silent degradation | HTTP 200 nhưng quality giảm | Quality feedback/golden probes |
| Feedback loop | Output model làm data tương lai lệch | Exploration, causal/A-B analysis |
| Cost runaway | Prompt/retry/traffic tăng | Limit, cache, budget alert |

## 8. Decision framework step-by-step

1. Viết business objective bằng một câu có số đo.
2. Xác định output: decision, score, ranking, JSON, text hay answer có citation.
3. Xác định nguồn sự thật: rule, historical labels hay trusted corpus.
4. Ước lượng cost false positive/false negative.
5. Đặt latency, throughput và cost budget.
6. Đặt yêu cầu explainability, privacy, compliance và audit.
7. Chọn baseline đơn giản nhất.
8. Thiết kế offline evaluation và online feedback.
9. Thiết kế fallback, human review và rollback.
10. Chỉ tăng complexity khi evidence cho thấy baseline không đủ.

## 9. Architecture mẫu: tách prediction khỏi decision

```text
Client
  -> API Gateway
  -> Input Validator
  -> Feature Builder / Retriever
  -> Model or LLM Client
  -> Policy Layer
  -> Response Formatter
  -> Audit Log + Metrics + Feedback Store
```

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Prediction:
    model_version: str
    risk_probability: float
    latency_ms: int


@dataclass(frozen=True)
class Policy:
    review_threshold: float
    reject_threshold: float
    max_latency_ms: int


def decide(prediction: Prediction, policy: Policy) -> Decision:
    if prediction.latency_ms > policy.max_latency_ms:
        return Decision.REVIEW
    if prediction.risk_probability >= policy.reject_threshold:
        return Decision.BLOCK
    if prediction.risk_probability >= policy.review_threshold:
        return Decision.REVIEW
    return Decision.ALLOW
```

Tách hai lớp giúp đổi threshold không cần retrain, audit được lý do, dùng policy khác theo market và rollback độc lập.

## 10. Performance, security và production readiness

Đừng dùng một con số latency chung cho mọi hệ thống. Hãy benchmark trên workload thật và đo từng stage. Rule/local classical ML thường nhanh hơn LLM nhiều bậc; feature retrieval hoặc network có thể chậm hơn `predict()`.

Checklist:

- Không đặt LLM vào hot path có SLA rất thấp nếu chưa có kiến trúc phù hợp.
- Timeout/retry phải tránh retry storm và duplicate side effect.
- Cache cần xét freshness, personalization và privacy.
- Filter quyền trước khi retrieved text đi vào prompt.
- Không execute SQL/code/tool call do model tạo nếu chưa validate và authorize.
- Decision tài chính, pháp lý hoặc quyền lợi cần audit và appeal/human path.

## 11. Năm case study sẽ thực hành

| Bài toán | Baseline nên thử | Candidate production | Fallback |
|---|---|---|---|
| Fraud detection | Hard rules | Rule + ML score + review | Rule + manual review |
| Customer churn | Heuristic usage drop | Tabular ML + retention policy | Heuristic campaign |
| Chatbot CSKH | Search/FAQ | RAG + LLM + citation | Human support |
| Search nội bộ | BM25 keyword | Hybrid BM25 + vector + ACL | Keyword search |
| Recommendation | Popular/category | Candidate + ranking + rules | Popular/category |

Không chép bảng này làm đáp án. Trong [exercise.md](./exercise.md), bạn phải thay đổi lựa chọn theo context, risk và constraint cụ thể.

## 12. Tài liệu và bài tập

- [document.md](./document.md): decision matrix, glossary và checklist để tra cứu nhanh.
- [exercise.md](./exercise.md): 5 design exercises và rubric tự kiểm.

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
- [ ] Tôi phân biệt được prediction của model và decision của policy.
- [ ] Tôi biết vì sao evaluation dataset phải đại diện production traffic.
