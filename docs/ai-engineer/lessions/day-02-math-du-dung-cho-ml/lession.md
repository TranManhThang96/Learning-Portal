# Day 2: Math đủ dùng cho ML

## Mục tiêu

Sau bài này, bạn cần làm được các việc sau:

- Hiểu vector, matrix, tensor là gì và vì sao chúng xuất hiện trong embedding, search, ranking, recommender và model training.
- Tính và giải thích được dot product, norm, cosine similarity, matrix multiplication.
- Biết dùng gradient để tối ưu một loss function đơn giản và đọc được dấu hiệu training diverge/converge.
- Hiểu probability, expected value, entropy và Bayes theorem ở mức dùng được cho ML decision.
- Viết code Python/NumPy có validation, xử lý lỗi số học cơ bản, batch/vectorized path và output phù hợp để đưa vào service.
- Trả lời được câu hỏi: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## TL;DR

Math trong ML không cần bắt đầu bằng proof. Với AI Engineer thiên production, bạn cần hiểu vector là numeric representation, dot product/cosine là cách đo độ gần, matrix multiplication là cách scale từ một request sang batch, gradient là hướng cập nhật để giảm loss, probability là ngôn ngữ của uncertainty. Những khái niệm này sẽ quay lại trong embedding search, RAG retrieval, ranking, classifier threshold, optimizer, evaluation và monitoring.

Nguyên tắc thực tế:

- Học bằng shape trước: `batch_size x feature_dim`, `num_docs x embedding_dim`, `batch_size x num_classes`.
- Python loop giúp hiểu concept, nhưng production path nên dùng NumPy/PyTorch/vectorized operations.
- Giữ tách biệt raw score, probability và business decision.
- Luôn kiểm tra `NaN`, `Inf`, zero vector, shape mismatch và dtype.
- Không có metric hay similarity nào tốt tuyệt đối; chọn theo data, latency, explainability và risk.

## 1. Vector: object được biểu diễn bằng số

Vector là một dãy số có thứ tự. Trong ML, vector thường biểu diễn một object sau khi đã encode:

```text
customer_features = [tenure_months, monthly_charges, support_tickets, is_monthly_contract]
query_embedding = [0.12, -0.03, 0.88, ...]
document_embedding = [0.10, -0.01, 0.91, ...]
```

Map sang tư duy software:

| Math concept | SE analogy | Ý nghĩa production |
|---|---|---|
| Vector | Một row dữ liệu đã encode thành numeric fields | Input contract của model/search |
| Dimension | Số feature hoặc số chiều embedding | Ảnh hưởng RAM, latency, index size |
| Norm | Độ dài vector | Cần cho cosine; zero norm gây lỗi |
| Embedding | Representation học từ model | Dùng cho semantic search/RAG/recommendation |
| Vector database | Database tối ưu similarity search | Cần index, metadata filter, permission check |

Ví dụ embedding search:

```text
Query: "chính sách nghỉ phép"
query_embedding -> vector 768 chiều

Document chunks:
- "Quy định nghỉ phép năm..." -> vector 768 chiều
- "Hướng dẫn cấu hình VPN..." -> vector 768 chiều
- "Chính sách bảo mật thiết bị..." -> vector 768 chiều

Search = tìm vector document gần query nhất.
```

Điểm cần nhớ: vector không tự có nghĩa nếu thiếu quy ước encode. Feature order, normalization, dtype và model version đều là một phần của contract.

## 2. Matrix và tensor: batch hóa vector

Matrix là bảng số 2D. Trong ML tabular, mỗi row thường là một sample, mỗi column là một feature:

```text
X = [
  [4, 89.9, 3, 1],
  [24, 39.0, 0, 0],
  [2, 120.0, 8, 1]
]

shape(X) = (3, 4)
```

Trong embedding search:

```text
query_embedding.shape = (768,)
document_embeddings.shape = (100_000, 768)
scores.shape = (100_000,)
```

Tensor là khái niệm tổng quát hơn:

```text
scalar: 5
vector: [1, 2, 3]
matrix: [[1, 2], [3, 4]]
3D tensor: batch_size x sequence_length x embedding_dim
```

Trong LLM, một batch input có thể có shape:

```text
32 x 512 x 4096
```

Nghĩa là 32 requests, mỗi request 512 tokens, mỗi token là vector 4096 chiều.

Production concern:

- Shape mismatch là lỗi rất phổ biến khi nối pipeline.
- Batch lớn tăng throughput nhưng có thể tăng latency và memory peak.
- `float32` thường đủ cho inference/search và tiết kiệm RAM; `float64` hữu ích khi cần tính toán số học chính xác hơn hoặc debug.
- Embedding dimension càng lớn thì storage/index/latency càng tăng.

## 3. Dot product: scoring function nền tảng

Dot product giữa hai vector cùng chiều:

```text
a = [1, 2, 3]
b = [4, 5, 6]
dot(a, b) = 1*4 + 2*5 + 3*6 = 32
```

Trực giác:

- Nếu hai vector cùng hướng và có giá trị lớn ở cùng dimension, dot product lớn.
- Nếu khác hướng, dot product thấp hoặc âm.
- Dot product bị ảnh hưởng bởi magnitude, không chỉ direction.

Trong model tuyến tính:

```text
score = w1*x1 + w2*x2 + ... + wn*xn + bias
```

Ví dụ risk scoring:

```text
features = [late_payment_count, debt_ratio, account_age_months]
weights = [0.8, 1.5, -0.03]
score = dot(features, weights) + bias
```

`score` chưa phải probability. Thường cần sigmoid/calibration/threshold trước khi ra quyết định.

Trade-off:

| Lựa chọn | Khi phù hợp | Rủi ro |
|---|---|---|
| Dot product | Magnitude có ý nghĩa, ví dụ recommender dùng vector norm như độ phổ biến/confidence | Item phổ biến có thể thắng quá nhiều |
| Cosine similarity | Muốn so hướng semantic, giảm ảnh hưởng độ dài vector | Bỏ qua magnitude, có thể mất tín hiệu confidence |

## 4. Norm và cosine similarity: đo độ gần embedding

Norm L2:

```text
norm(a) = sqrt(a1^2 + a2^2 + ... + an^2)
```

Cosine similarity:

```text
cosine(a, b) = dot(a, b) / (norm(a) * norm(b))
```

Giá trị thường nằm trong khoảng:

- Gần `1`: rất giống hướng.
- Gần `0`: gần như không liên quan.
- Gần `-1`: ngược hướng.

Trong RAG, cosine similarity thường dùng để lấy top-k chunks liên quan đến query. Nhưng điểm cosine không phải "độ đúng" tuyệt đối. Nó chỉ nói embedding của query và document gần nhau theo model embedding đang dùng.

Production concern:

- Zero vector làm chia cho 0, phải reject hoặc fallback.
- `NaN`/`Inf` trong embedding phải bị chặn ở boundary.
- Score distribution thay đổi khi đổi embedding model, chunking hoặc normalization.
- Top-k retrieval cần kết hợp metadata filter, permission check và reranking nếu domain có risk cao.

## 5. Matrix multiplication: từ một request sang batch

Thay vì tính từng score:

```text
score_one = dot(x, w)
```

Ta tính cả batch:

```text
scores = X @ W
```

Theo tài liệu NumPy hiện tại, toán tử `@` là matrix multiplication cho `ndarray`; còn `*` là element-wise multiplication. Đây là khác biệt quan trọng khi đọc code ML.

Ví dụ:

```python
import numpy as np

X = np.array(
    [
        [4, 89.9, 3],
        [24, 39.0, 0],
        [2, 120.0, 8],
    ],
    dtype=np.float32,
)
w = np.array([[-0.03], [0.01], [0.40]], dtype=np.float32)

scores = X @ w
print(scores.shape)  # (3, 1)
```

Vì sao production quan tâm:

- Vectorized operation nhanh hơn Python loop vì chạy trong native code tối ưu.
- GPU/BLAS tối ưu mạnh cho matrix multiplication.
- Batch inference có thể tăng throughput.
- Cần kiểm soát batch size để tránh memory spike.

## 6. Derivative, gradient và gradient descent

Derivative cho biết function thay đổi thế nào khi input thay đổi một chút. Với:

```text
f(x) = x^2
f'(x) = 2x
```

Nếu `x = 3`, gradient là `6`. Muốn giảm loss, đi ngược hướng gradient:

```text
x = x - learning_rate * gradient
```

Gradient descent không phải magic. Nó là một vòng lặp:

1. Dự đoán output.
2. Tính loss.
3. Tính gradient của loss theo parameter.
4. Cập nhật parameter theo hướng giảm loss.
5. Lặp lại đến khi hội tụ hoặc dừng theo budget.

Learning rate trade-off:

| Learning rate | Ưu điểm | Rủi ro |
|---|---|---|
| Quá nhỏ | Ổn định hơn | Train chậm, tốn compute |
| Vừa đủ | Hội tụ tốt | Cần tuning |
| Quá lớn | Có thể giảm nhanh lúc đầu | Loss dao động hoặc diverge |

Production/debug signal:

- Loss giảm đều: training có vẻ ổn.
- Loss tăng/`NaN`: learning rate quá lớn, data lỗi, overflow, gradient explode.
- Train loss tốt nhưng validation loss xấu: overfitting hoặc data leakage/split sai.
- Metric business không tăng dù loss giảm: objective không khớp business target.

## 7. Probability: model output không phải sự thật

Classifier thường trả probability:

```json
{
  "not_churn": 0.18,
  "churn": 0.82
}
```

Nhưng probability model không mặc nhiên calibrated. `0.82` chỉ đáng tin như "82% risk" nếu model đã được đánh giá calibration trên data tương tự production.

Best practice:

- Lưu `score`, `probability`, `threshold`, `decision` riêng.
- Threshold thuộc business layer, không hard-code trong model nếu còn cần tuning.
- Với quyết định có cost cao, dùng expected value và human review queue.
- Monitor calibration và drift, không chỉ accuracy.

Ví dụ risk scoring:

```text
fraud_probability = 0.02
transaction_amount = 10_000
expected_loss = 0.02 * 10_000 = 200
manual_review_cost = 5
```

Nếu expected loss lớn hơn review cost, route sang review queue có lý hơn auto approve.

## 8. Expected value, entropy và Bayes

Expected value là giá trị kỳ vọng:

```text
E[loss] = probability_of_event * cost_if_event_happens
```

Entropy đo uncertainty của distribution:

```text
[0.99, 0.01] -> entropy thấp
[0.51, 0.49] -> entropy cao
```

Ứng dụng:

- Entropy cao: route sang human review, ask clarification hoặc dùng model mạnh hơn.
- Entropy thấp nhưng sai nhiều: kiểm tra calibration, bias hoặc data drift.
- Entropy theo thời gian tăng: có thể distribution production đã đổi.

Bayes theorem ở mức trực giác:

```text
posterior = prior * likelihood / evidence
```

Điểm quan trọng nhất với production: base rate rất quan trọng. Nếu fraud base rate chỉ 0.1%, một signal "có vẻ fraud" vẫn có thể tạo nhiều false positive nếu không tính prior.

## 9. Ví dụ gần production: embedding search bằng NumPy

Code dưới đây vẫn là local example, nhưng có các phần nên có trong service thật: validation shape, finite check, dtype rõ ràng, zero norm guard, batch path và output có score.

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SearchResult:
    doc_id: str
    score: float


def as_2d_float_array(name: str, value: np.ndarray, *, expected_dim: int | None = None) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError(f"{name} must be a 2D array, got shape={array.shape}")
    if expected_dim is not None and array.shape[1] != expected_dim:
        raise ValueError(f"{name} must have dim={expected_dim}, got shape={array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains NaN or Inf")
    return array


def as_1d_float_array(name: str, value: np.ndarray, *, expected_dim: int | None = None) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a 1D array, got shape={array.shape}")
    if expected_dim is not None and array.shape[0] != expected_dim:
        raise ValueError(f"{name} must have dim={expected_dim}, got shape={array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains NaN or Inf")
    return array


def cosine_top_k(
    query_embedding: np.ndarray,
    document_embeddings: np.ndarray,
    doc_ids: list[str],
    *,
    top_k: int = 5,
    eps: float = 1e-12,
) -> list[SearchResult]:
    docs = as_2d_float_array("document_embeddings", document_embeddings)
    query = as_1d_float_array("query_embedding", query_embedding, expected_dim=docs.shape[1])

    if len(doc_ids) != docs.shape[0]:
        raise ValueError("doc_ids length must match number of document embeddings")
    if not 1 <= top_k <= docs.shape[0]:
        raise ValueError("top_k must be between 1 and number of documents")

    query_norm = np.linalg.norm(query)
    doc_norms = np.linalg.norm(docs, axis=1)
    if query_norm <= eps:
        raise ValueError("query_embedding is a zero vector")
    if np.any(doc_norms <= eps):
        raise ValueError("document_embeddings contains zero vector")

    scores = (docs @ query) / (doc_norms * query_norm)
    candidate_indices = np.argpartition(-scores, kth=top_k - 1)[:top_k]
    sorted_indices = candidate_indices[np.argsort(-scores[candidate_indices])]

    return [
        SearchResult(doc_id=doc_ids[index], score=float(scores[index]))
        for index in sorted_indices
    ]


if __name__ == "__main__":
    query = np.array([0.90, 0.10, 0.20], dtype=np.float32)
    docs = np.array(
        [
            [0.85, 0.18, 0.10],
            [0.10, 0.70, 0.60],
            [0.75, 0.20, 0.30],
        ],
        dtype=np.float32,
    )
    ids = ["leave-policy", "vpn-guide", "benefit-policy"]

    for result in cosine_top_k(query, docs, ids, top_k=2):
        print(result)
```

Production trade-off:

- Code này tốt để hiểu và làm small-scale local reranking.
- Với hàng triệu vectors, không scan toàn bộ bằng NumPy mỗi request. Dùng ANN/vector database như FAISS, HNSW, pgvector, Milvus, Qdrant, Weaviate tùy context.
- Cần permission-aware filtering trước hoặc trong retrieval, nhất là tài liệu nội bộ.
- Cần log query id, embedding model version, index version, top-k score distribution và latency.

## 10. Ví dụ gần production: risk scoring có threshold theo cost

Ví dụ này minh họa cách biến probability thành decision nhưng vẫn giữ audit trail.

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class Decision(StrEnum):
    APPROVE = "approve"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class RiskDecision:
    probability: float
    expected_loss: float
    decision: Decision
    reason: str


def sigmoid_stable(score: np.ndarray) -> np.ndarray:
    score = np.asarray(score, dtype=np.float64)
    positive = score >= 0
    negative = ~positive
    output = np.empty_like(score, dtype=np.float64)
    output[positive] = 1.0 / (1.0 + np.exp(-score[positive]))
    exp_score = np.exp(score[negative])
    output[negative] = exp_score / (1.0 + exp_score)
    return output


def score_transactions(
    features: np.ndarray,
    weights: np.ndarray,
    bias: float,
    amounts: np.ndarray,
    *,
    review_cost: float,
    block_threshold: float,
) -> list[RiskDecision]:
    X = np.asarray(features, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    transaction_amounts = np.asarray(amounts, dtype=np.float64)

    if X.ndim != 2:
        raise ValueError("features must be 2D")
    if w.shape != (X.shape[1],):
        raise ValueError(f"weights must have shape ({X.shape[1]},)")
    if transaction_amounts.shape != (X.shape[0],):
        raise ValueError("amounts must match number of rows")
    if review_cost < 0 or not 0.0 <= block_threshold <= 1.0:
        raise ValueError("invalid decision configuration")
    if not np.all(np.isfinite(X)) or not np.all(np.isfinite(w)) or not np.all(np.isfinite(transaction_amounts)):
        raise ValueError("input contains NaN or Inf")

    raw_scores = X @ w + bias
    probabilities = sigmoid_stable(raw_scores)
    expected_losses = probabilities * transaction_amounts

    decisions: list[RiskDecision] = []
    for probability, expected_loss in zip(probabilities, expected_losses, strict=True):
        if probability >= block_threshold:
            decision = Decision.BLOCK
            reason = "probability_above_block_threshold"
        elif expected_loss >= review_cost:
            decision = Decision.REVIEW
            reason = "expected_loss_above_review_cost"
        else:
            decision = Decision.APPROVE
            reason = "risk_below_action_threshold"

        decisions.append(
            RiskDecision(
                probability=float(probability),
                expected_loss=float(expected_loss),
                decision=decision,
                reason=reason,
            )
        )

    return decisions
```

Điểm production:

- `sigmoid_stable` tránh overflow khi score quá lớn/quá nhỏ.
- Batch scoring dùng `X @ w`.
- Decision dựa trên cả probability và expected loss.
- Cần calibration trước khi xem probability là rủi ro tiền tệ đáng tin.
- Cần policy rõ ràng cho false positive/false negative.

## 11. Trade-off tổng hợp

| Chủ đề | Option A | Option B | Best solution theo context |
|---|---|---|---|
| Similarity | Dot product | Cosine similarity | Cosine cho semantic direction; dot product khi magnitude/confidence có ý nghĩa |
| Implementation | Python loop | NumPy/PyTorch vectorized | Loop để học/test nhỏ; vectorized cho batch và production-like path |
| Precision | `float32` | `float64` | `float32` cho embedding/inference phổ biến; `float64` khi cần tính toán ổn định hơn |
| Retrieval | Full scan | ANN index | Full scan cho dữ liệu nhỏ/debug; ANN cho dữ liệu lớn và latency thấp |
| Decision | Hard label | Probability + threshold | Production nên giữ probability và threshold theo business cost |
| Uncertainty | Ignore entropy | Route high-entropy case | Risk cao nên có review/fallback/escalation |
| Batch | Single request | Micro-batch | Batch tăng throughput; single request tối ưu latency p50; micro-batch cân bằng |

## 12. Performance và capacity estimate

Ước lượng RAM cho embedding:

```text
num_vectors * dimension * bytes_per_float
```

Ví dụ:

```text
1_000_000 vectors * 768 dims * 4 bytes(float32) ~= 2.86 GiB
```

Đây mới là raw vectors, chưa tính:

- ANN index overhead.
- Metadata.
- Tombstone/deleted records.
- Replication.
- Cache.
- Process/runtime overhead.

Latency rough intuition:

- Full cosine scan trên 1 triệu vectors mỗi request thường không phải lựa chọn tốt cho API latency thấp.
- ANN index giảm latency bằng cách đánh đổi recall.
- Reranking top-50/top-100 bằng model mạnh hơn tăng quality nhưng tăng latency/cost.
- Batch embedding giúp throughput tốt hơn nhưng cần queueing và timeout policy.

## 13. Dùng được trong production không? Nếu có thì cần điều kiện gì?

Có, các công thức và pattern trong bài này dùng trực tiếp trong production, nhưng code minh họa chưa nên bê nguyên làm retrieval service quy mô lớn.

Điều kiện để dùng trong production:

- Có input validation: shape, dtype, finite values, zero vector, range hợp lệ.
- Có numerical stability: tránh divide-by-zero, overflow sigmoid/softmax, tolerance khi so sánh floating point.
- Có scale strategy: vectorized batch path cho dữ liệu vừa; ANN/vector database cho dữ liệu lớn.
- Có observability: latency, error rate, score distribution, top-k quality, drift, model/index version.
- Có business guardrail: threshold theo cost, human review cho risk cao, audit trail cho decision.
- Có security/privacy: embedding không được coi là vô hại; vẫn cần access control, retention policy và redaction khi cần.
- Có evaluation: retrieval recall@k/MRR/nDCG cho search, calibration/Brier score/PR-AUC cho risk model, golden set trước khi đổi model/index.

Không nên dùng production nếu:

- Chưa biết embedding/model version đang sinh vector.
- Không kiểm soát được permission trong retrieval.
- Probability chưa calibration nhưng dùng để ra quyết định tài chính/pháp lý lớn.
- Không có fallback khi input lỗi hoặc score distribution bất thường.
- Chỉ test bằng vài toy vectors mà chưa có golden set thực tế.

## 14. Checklist cuối ngày

- Bạn giải thích được vì sao `X @ w` là batch scoring.
- Bạn phân biệt được `*` element-wise và `@` matrix multiplication trong NumPy.
- Bạn viết được cosine similarity có kiểm tra zero vector.
- Bạn biết khi nào cosine tốt hơn dot product và ngược lại.
- Bạn đọc được loss curve cơ bản và nhận ra learning rate quá lớn/quá nhỏ.
- Bạn dùng expected loss để quyết định approve/review/block thay vì chỉ nhìn label.
- Bạn nêu được điều kiện để math/code này đủ an toàn cho production.
