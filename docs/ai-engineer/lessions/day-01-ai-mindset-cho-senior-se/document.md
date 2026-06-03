# Document: AI Mindset cho Senior SE

## 1. Vì sao Senior SE cần mindset khác khi bước vào AI

Backend system truyền thống thường được thiết kế quanh logic deterministic:

```text
input hợp lệ + code đúng + dependency ổn định -> output kỳ vọng
```

AI system thường là probabilistic:

```text
input + data distribution + model version + prompt/retriever/config -> output có xác suất đúng/sai
```

Điểm khó không nằm ở việc gọi API `predict()` hay gọi LLM provider. Điểm khó nằm ở việc đưa một thành phần không hoàn toàn deterministic vào hệ thống có SLA, user thật, dữ liệu thật, chi phí thật và rủi ro thật.

Với background Senior SE, lợi thế của bạn là biết thiết kế production system. Vì vậy khi học AI, hãy luôn hỏi:

- Input contract là gì?
- Output contract là gì?
- Ai chịu trách nhiệm nếu output sai?
- Sai kiểu nào thì chấp nhận được, sai kiểu nào thì không?
- Có baseline đơn giản hơn không?
- Có cách rollback không?
- Có log đủ để debug không?
- Có đo được chất lượng sau deploy không?

## 2. Rule-based, ML, Deep Learning, LLM và RAG khác nhau thế nào?

### 2.1 Rule-based system

Rule-based system là hệ thống mà logic được viết trực tiếp bằng code, SQL, workflow hoặc configuration.

Ví dụ fraud guardrail:

```python
from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class Transaction:
    user_id: str
    amount_usd: float
    user_country: str
    card_country: str
    failed_attempts_24h: int
    account_age_days: int


def fraud_rule_decision(tx: Transaction) -> tuple[Decision, list[str]]:
    reasons: list[str] = []

    if tx.amount_usd >= 10_000:
        reasons.append("large_amount")
    if tx.user_country != tx.card_country:
        reasons.append("country_mismatch")
    if tx.failed_attempts_24h >= 5:
        reasons.append("many_failed_attempts")
    if tx.account_age_days < 3 and tx.amount_usd >= 1_000:
        reasons.append("new_account_large_amount")

    if "many_failed_attempts" in reasons and "country_mismatch" in reasons:
        return Decision.BLOCK, reasons
    if reasons:
        return Decision.REVIEW, reasons
    return Decision.ALLOW, reasons
```

Ưu điểm:

- Dễ hiểu, dễ test, dễ audit.
- Latency rất thấp.
- Không cần training data.
- Dễ đáp ứng compliance khi cần giải thích.

Nhược điểm:

- Khó bắt pattern phức tạp.
- Rule dễ chồng chéo, conflict, khó maintain khi domain lớn.
- Rule thường bị lag so với behavior mới của user/fraudster.

Nên dùng khi:

- Logic rõ ràng và tương đối ổn định.
- Sai sót cần explain được.
- Data lịch sử chưa đủ để train model.
- Cần latency rất thấp và chi phí gần như bằng 0.

Không nên dùng một mình khi:

- Pattern thay đổi nhanh.
- Có nhiều signal yếu cần kết hợp.
- Domain có hàng trăm biến tương tác phi tuyến.

### 2.2 Classical Machine Learning system

ML system học pattern từ data. Thay vì viết toàn bộ rule, bạn định nghĩa feature, label, algorithm và metric. Model học một function xấp xỉ:

```text
features -> probability/score/prediction
```

Ví dụ customer churn:

```text
[tenure_months, plan_price, tickets_30d, failed_payments_90d, usage_drop_pct]
  -> churn_probability = 0.78
```

Điểm quan trọng: model nên trả score, business policy mới quyết định action.

```python
def retention_policy(churn_probability: float, customer_ltv_usd: float) -> str:
    if churn_probability >= 0.80 and customer_ltv_usd >= 2_000:
        return "assign_success_manager"
    if churn_probability >= 0.65:
        return "send_discount_offer"
    if churn_probability >= 0.50:
        return "send_usage_tips"
    return "no_action"
```

Ưu điểm:

- Mạnh với tabular data.
- Có thể đo bằng metric rõ ràng.
- Inference thường nhanh hơn LLM rất nhiều.
- Có thể explain tương đối tốt với model đơn giản hoặc feature importance.

Nhược điểm:

- Phụ thuộc chất lượng label và feature.
- Có data drift, concept drift, training-serving skew.
- Không tự hiểu business context ngoài dữ liệu đã học.

Nên dùng khi:

- Có dữ liệu lịch sử đủ tốt.
- Bài toán là classification, regression, ranking hoặc forecasting.
- Output là score/probability chứ không cần sinh văn bản dài.

Không nên dùng khi:

- Không có label hoặc label sai lệch nghiêm trọng.
- Bài toán có rule đơn giản hơn nhiều.
- Cần reasoning/generation theo ngôn ngữ tự nhiên.

### 2.3 Deep Learning system

Deep Learning là một nhánh của ML dùng neural network nhiều tầng. Điểm mạnh là học representation từ dữ liệu thô hoặc gần-thô như text, image, audio, sequence.

Nên cân nhắc Deep Learning khi:

- Feature engineering thủ công quá khó.
- Data đủ lớn.
- Input là unstructured data.
- Classical ML đã chạm trần chất lượng.

Trade-off:

- Có thể mạnh hơn, nhưng cần compute lớn hơn.
- Debug khó hơn.
- Explainability thấp hơn.
- Deployment có thể cần GPU, batching, quantization, model serving stack.

Với Senior SE mới chuyển sang AI Engineer, không nên mặc định dùng Deep Learning cho mọi thứ. Với tabular business data, baseline như Logistic Regression, Random Forest, XGBoost thường là điểm bắt đầu tốt hơn.

### 2.4 LLM application

LLM phù hợp với các tác vụ ngôn ngữ:

- Summarization.
- Extraction.
- Classification bằng natural language.
- Draft email/ticket/report.
- Chatbot.
- Tool calling.
- Code assistant.
- Reasoning workflow có nhiều bước.

Nhưng LLM có các đặc tính production rất khác:

- Output có thể không ổn định.
- Có hallucination.
- Có context window limit.
- Chi phí phụ thuộc token.
- Latency thường cao hơn classical ML.
- Dễ bị prompt injection khi nhận input từ user hoặc document không tin cậy.
- Cần schema validation nếu downstream cần JSON hoặc action có side effect.

Ví dụ gần production hơn cho extraction: không để LLM tự do trả text, mà ép output qua schema và policy validation.

```python
from dataclasses import dataclass
from typing import Literal


Priority = Literal["low", "medium", "high", "urgent"]


@dataclass(frozen=True)
class TicketExtraction:
    category: str
    priority: Priority
    customer_id: str | None
    requires_refund: bool
    summary: str


ALLOWED_CATEGORIES = {
    "billing",
    "technical_support",
    "account_access",
    "product_feedback",
}


def validate_ticket_extraction(payload: dict) -> TicketExtraction:
    category = str(payload.get("category", "")).strip()
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(f"unsupported category: {category}")

    priority = str(payload.get("priority", "")).strip()
    if priority not in {"low", "medium", "high", "urgent"}:
        raise ValueError(f"unsupported priority: {priority}")

    summary = str(payload.get("summary", "")).strip()
    if not 20 <= len(summary) <= 500:
        raise ValueError("summary must be between 20 and 500 characters")

    return TicketExtraction(
        category=category,
        priority=priority,  # type: ignore[arg-type]
        customer_id=payload.get("customer_id"),
        requires_refund=bool(payload.get("requires_refund", False)),
        summary=summary,
    )
```

Production point: LLM output là untrusted input. Hãy validate như validate request từ public API.

### 2.5 RAG system

RAG, viết tắt của Retrieval-Augmented Generation, kết hợp retrieval với LLM:

```text
user question
  -> retrieve relevant documents
  -> build grounded prompt with snippets/citations
  -> LLM generates answer
  -> validate/cite/log
```

RAG phù hợp khi:

- Cần trả lời theo tài liệu nội bộ.
- Knowledge thay đổi thường xuyên.
- Cần citation/source.
- Không muốn nhét knowledge vào model bằng fine-tuning.

RAG không tự động đảm bảo đúng. Chất lượng phụ thuộc vào:

- Document ingestion.
- Chunking strategy.
- Embedding model.
- Vector search/hybrid search.
- Reranking.
- Permission filtering.
- Prompt grounding.
- Citation policy.
- Evaluation dataset.

Không nên dùng RAG khi:

- Không có corpus đáng tin cậy.
- Bài toán chỉ cần rule hoặc SQL.
- User hỏi những thứ không cần knowledge riêng.
- Không có cách kiểm soát quyền truy cập tài liệu.

## 3. Map AI concept về tư duy Software Engineering

| AI concept | SE equivalent | Ghi chú production |
|---|---|---|
| Model | Versioned dependency / business function | Cần version, owner, changelog, rollback |
| Training | Build process | Input là data + code + config, output là artifact |
| Dataset | Source dependency | Cần quality check, lineage, privacy policy |
| Feature | API input contract | Thay đổi feature là breaking change nếu không quản lý |
| Label | Expected behavior trong dữ liệu lịch sử | Label sai thì model học sai |
| Hyperparameter | Config | Cần tracking để reproduce |
| Evaluation | Statistical test suite | Không pass/fail từng case đơn giản như unit test |
| Inference | Runtime API | Cần latency, timeout, retry, quota |
| Threshold | Business policy config | Nên tách khỏi model artifact |
| Prompt | Runtime/config logic | Cần versioning và regression test |
| Retriever | Read path của knowledge system | Cần permission, freshness, relevance |
| Model registry | Artifact registry | Quản lý promote/stage/rollback |
| Drift monitoring | Observability | Phát hiện production data khác training data |

Điểm cần nhớ: model không thay thế software architecture. Model là một thành phần trong architecture.

## 4. Training giống build process, inference giống runtime API

### 4.1 Training pipeline tối thiểu

Một training pipeline nghiêm túc cần biết đầu vào và đầu ra:

```text
raw data
  -> validation
  -> feature generation
  -> train/validation/test split
  -> train model
  -> evaluate model
  -> package artifact
  -> register artifact
  -> approval gate
```

Metadata cần lưu:

- Dataset version hoặc snapshot time.
- Feature code version.
- Model algorithm.
- Hyperparameters.
- Metric tổng thể và metric theo segment.
- Training time.
- Artifact checksum.
- Người approve.
- Known limitations.

### 4.2 Inference path tối thiểu

```text
request
  -> authentication/authorization
  -> input validation
  -> feature retrieval/transformation
  -> model prediction
  -> policy decision
  -> response
  -> logging/metrics
```

Production log nên có:

- `request_id`.
- `user_id` hoặc entity id đã được xử lý theo privacy policy.
- `model_version`.
- `feature_version`.
- `prompt_version` nếu dùng LLM.
- `retriever_version` nếu dùng RAG.
- latency từng bước.
- score/output.
- threshold/policy version.
- final decision.
- fallback used hay không.

## 5. Evaluation không giống unit test

Unit test thường xác minh một case:

```text
given input A -> expect output B
```

AI evaluation thường xác minh phân phối:

```text
on evaluation dataset:
  precision >= 0.82
  recall >= 0.70
  p95_latency_ms <= 200
  cost_per_1k_requests <= 3 USD
```

Vấn đề kinh điển: accuracy có thể gây ảo tưởng. Nếu fraud rate là 0.5%, model luôn đoán "not fraud" sẽ đạt 99.5% accuracy nhưng không bắt được fraud nào.

Các lớp test nên có:

| Test type | Mục tiêu |
|---|---|
| Unit test | Kiểm tra feature code, parser, policy layer |
| Data validation | Kiểm tra schema, missing value, range, distribution |
| Offline evaluation | Kiểm tra metric trên held-out dataset |
| Segment evaluation | Kiểm tra từng nhóm user/product/region |
| Regression golden set | Đảm bảo case quan trọng không tụt chất lượng |
| Latency benchmark | Đảm bảo SLA |
| Cost benchmark | Đảm bảo cost/request |
| Safety/security test | Prompt injection, PII leakage, toxic output |
| Online experiment | A/B test, shadow deploy, canary |

## 6. Failure mode đặc thù của AI system

| Failure mode | Ví dụ | Cách giảm rủi ro |
|---|---|---|
| Data leakage | Feature chứa thông tin chỉ biết sau khi outcome xảy ra | Review feature lineage, time-based split |
| Training-serving skew | Training dùng transform khác production | Dùng shared feature code hoặc feature store |
| Data drift | User behavior thay đổi sau campaign | Monitor distribution và retrain trigger |
| Concept drift | Quan hệ feature-label thay đổi | Monitor outcome, retrain, recalibrate |
| Hallucination | LLM bịa policy hoàn tiền | RAG, citation, abstain policy |
| Prompt injection | Document chứa "ignore previous instruction" | Treat retrieved text as untrusted, isolate instruction |
| Permission leakage | Search trả tài liệu user không có quyền | Permission filter trước rerank/generation |
| Silent degradation | Metric giảm từ từ nhưng service vẫn 200 OK | Quality monitoring và feedback loop |
| Cost runaway | Prompt dài, retry nhiều, traffic tăng | Budget, token limit, cache, rate limit |
| Feedback loop | Recommendation chỉ reinforce item phổ biến | Exploration policy và diversity constraints |

## 7. Decision framework: chọn rule, ML, DL, LLM, RAG hay hybrid

Hãy trả lời lần lượt:

1. Business objective là gì?
2. Output cần là decision, score, ranking, text, JSON, hay answer có citation?
3. Có dữ liệu lịch sử/label đủ tốt không?
4. Có corpus knowledge đáng tin cậy không?
5. Sai dương tính và sai âm tính tốn bao nhiêu?
6. Latency budget là bao nhiêu?
7. Cost/request chấp nhận được là bao nhiêu?
8. Có cần explainability hoặc audit không?
9. Có constraint privacy/compliance không?
10. Có fallback khi AI không chắc không?

Gợi ý chọn:

| Context | Best starting solution | Vì sao |
|---|---|---|
| Logic rõ, ít biến, cần audit | Rule-based | Rẻ, nhanh, explainable |
| Tabular prediction có label | Classical ML baseline | Mạnh, nhanh, dễ đo |
| Fraud/payment risk | Hybrid rule + ML + review queue | Cần guardrail và kiểm soát rủi ro |
| Hỏi đáp tài liệu nội bộ | RAG + LLM | Knowledge cập nhật, có citation |
| Extract JSON từ email/ticket | LLM + schema validation | Linh hoạt với ngôn ngữ tự nhiên |
| Search tài liệu | Hybrid search BM25 + vector | Kết hợp exact match và semantic search |
| Recommendation | Ranking model + heuristic fallback | Cá nhân hóa nhưng xử lý cold start |
| Need real-time < 50ms | Rule/cache/classical ML local | LLM thường không phù hợp trong sync path |

## 8. Production architecture mẫu cho AI decision service

```text
Client/API
  -> API Gateway
  -> AI Decision Service
      -> Input Validator
      -> Feature Builder / Retriever
      -> Model or LLM Client
      -> Policy Layer
      -> Response Formatter
      -> Audit Logger
  -> Metrics/Tracing/Cost Dashboard
  -> Feedback/Outcome Store
```

Tách `prediction` và `decision` là best practice quan trọng.

```python
from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    APPROVE = "approve"
    MANUAL_REVIEW = "manual_review"
    REJECT = "reject"


@dataclass(frozen=True)
class Prediction:
    model_version: str
    fraud_probability: float
    latency_ms: int


@dataclass(frozen=True)
class PolicyConfig:
    review_threshold: float
    reject_threshold: float
    max_model_latency_ms: int


def decide_action(prediction: Prediction, policy: PolicyConfig) -> Action:
    if prediction.latency_ms > policy.max_model_latency_ms:
        return Action.MANUAL_REVIEW
    if prediction.fraud_probability >= policy.reject_threshold:
        return Action.REJECT
    if prediction.fraud_probability >= policy.review_threshold:
        return Action.MANUAL_REVIEW
    return Action.APPROVE
```

Vì sao tách như vậy?

- Có thể đổi threshold mà không retrain model.
- Có thể audit quyết định.
- Có thể rollback policy riêng.
- Có thể dùng cùng model cho nhiều market/product với policy khác nhau.

## 9. Performance và cost mindset

Latency rất khác nhau theo approach:

| Approach | Latency thường gặp | Ghi chú |
|---|---:|---|
| Rule/SQL đơn giản | microseconds đến vài ms | Phù hợp request path rất nóng |
| Classical ML local | vài ms đến vài chục ms | Feature retrieval có thể là phần chậm nhất |
| Deep Learning nhỏ | 10-200ms | Phụ thuộc CPU/GPU/batching |
| Vector search | 10-100ms | Phụ thuộc index, filter, network |
| Reranking | 50-500ms | Cross-encoder thường đắt hơn embedding search |
| LLM API | vài trăm ms đến nhiều giây | Phụ thuộc model, token, provider |
| RAG full pipeline | 1-10 giây | Retrieval + rerank + generation |

Performance concern:

- Đừng đặt LLM vào synchronous hot path nếu SLA p95 dưới 200ms, trừ khi có cache/streaming/async design.
- Feature retrieval thường là bottleneck của ML system, không phải `predict()`.
- RAG cần đo riêng retrieval latency, rerank latency và generation latency.
- Token budget là performance budget. Prompt càng dài, latency và cost càng tăng.
- Batch inference có thể giảm cost nhưng tăng latency.
- Cache giúp rẻ và nhanh hơn, nhưng phải xử lý freshness, personalization và privacy.

## 10. Security, privacy và compliance

AI system không làm security biến mất. Một số nguyên tắc:

- Không execute output từ LLM nếu chưa qua allowlist và permission check.
- Không gửi PII/secrets sang third-party provider nếu policy không cho phép.
- Với RAG, filter quyền truy cập trước khi đưa document vào prompt.
- Log cần đủ debug nhưng không được vô tình lưu sensitive data.
- Prompt, retrieved context và model output đều nên được xem như data có thể chứa rủi ro.
- Với decision ảnh hưởng user nghiêm trọng, cần audit trail và human appeal path.

## 11. Dùng được trong production không? Nếu có thì cần điều kiện gì?

Có. Các pattern trong bài này dùng được trong production vì chúng là nền tảng thiết kế AI system thực tế. Tuy nhiên, không nên hiểu là chỉ cần chọn "ML" hoặc "LLM" là production-ready.

Điều kiện tối thiểu:

1. Có baseline và business metric.
2. Có data quality check.
3. Có offline evaluation đủ đại diện.
4. Có latency/cost budget rõ ràng.
5. Có input/output contract.
6. Có policy layer tách khỏi model.
7. Có observability: latency, error, score distribution, cost, quality feedback.
8. Có fallback: rule, cached answer, manual review, hoặc graceful degradation.
9. Có versioning cho model, prompt, retriever, threshold và dataset.
10. Có security/privacy review trước khi xử lý dữ liệu nhạy cảm.

## 12. Tóm tắt quyết định theo 5 bài toán mẫu

| Bài toán | Approach nên bắt đầu | Trade-off chính | Production fallback |
|---|---|---|---|
| Fraud detection | Hybrid rule + ML + manual review | Rule explainable nhưng bỏ sót pattern; ML mạnh hơn nhưng có FP/FN | Rule threshold + review queue |
| Customer churn | Classical ML trên tabular data | Dễ đo ROI nhưng phụ thuộc label và campaign drift | Heuristic theo usage/support ticket |
| Chatbot CSKH | RAG + LLM + guardrails | Trả lời tự nhiên nhưng có hallucination/prompt injection | Escalate human support |
| Search tài liệu nội bộ | Hybrid BM25 + vector + permission filter | Semantic tốt nhưng dễ leakage nếu filter sai | BM25 keyword search |
| Recommendation sản phẩm | Ranking ML + business rules | Cá nhân hóa tốt nhưng cold start/filter bubble | Popular/category fallback |

## 13. Thuật ngữ cần nhớ

- `Model artifact`: file/package chứa model đã train.
- `Inference`: quá trình chạy model để tạo output.
- `Feature`: tín hiệu đầu vào cho model.
- `Label`: kết quả đúng dùng để train/evaluate.
- `Threshold`: ngưỡng biến score thành action.
- `Drift`: production data hoặc quan hệ feature-label thay đổi theo thời gian.
- `Hallucination`: LLM tạo thông tin nghe hợp lý nhưng sai hoặc không có nguồn.
- `RAG`: lấy thông tin liên quan từ corpus rồi đưa vào LLM để trả lời.
- `Guardrail`: lớp kiểm soát input/output/action để giảm rủi ro.
- `Human-in-the-loop`: con người review/approve các case rủi ro hoặc model không chắc.

