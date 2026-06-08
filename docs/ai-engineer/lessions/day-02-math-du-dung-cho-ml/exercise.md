# Day 2 Exercise: Math đủ dùng cho ML

Thời lượng gợi ý: 90-120 phút.

Yêu cầu: viết code trong một file riêng, ví dụ `day02_math_lab.py`. Có thể dùng Python thuần cho phần 1, NumPy cho phần 2 trở đi.

## Bài 1: Python thuần cho dot product và cosine

Implement:

- `dot_product(a, b)`
- `l2_norm(a)`
- `cosine_similarity(a, b)`

Yêu cầu:

- Nếu vector khác chiều, raise `ValueError`.
- Nếu vector rỗng, raise `ValueError`.
- Nếu có phần tử không phải số, raise `TypeError` hoặc `ValueError`.
- Nếu norm bằng 0, raise `ValueError`.

Test cases tối thiểu:

```text
[1, 2, 3] dot [4, 5, 6] = 32
cosine([1, 0], [1, 0]) = 1
cosine([1, 0], [0, 1]) = 0
cosine([0, 0], [1, 2]) -> error
```

Câu hỏi review:

- Vì sao code Python thuần không nên dùng để scan 1 triệu vectors mỗi request?
- Lỗi zero vector nguy hiểm ở đâu trong production?

## Bài 2: NumPy vectorized embedding search

Viết function:

```python
def cosine_top_k(query_embedding, document_embeddings, doc_ids, top_k=5):
    ...
```

Yêu cầu:

- `query_embedding` shape `(d,)`.
- `document_embeddings` shape `(n, d)`.
- `doc_ids` dài bằng `n`.
- Validate `NaN`, `Inf`, zero vector.
- Trả về list kết quả đã sort giảm dần theo score.
- Dùng `@`, `np.linalg.norm`, `np.argpartition` hoặc `np.argsort`.

Dataset mẫu:

```python
import numpy as np

query = np.array([0.90, 0.10, 0.20], dtype=np.float32)
docs = np.array(
    [
        [0.85, 0.18, 0.10],
        [0.10, 0.70, 0.60],
        [0.75, 0.20, 0.30],
        [0.05, 0.80, 0.55],
    ],
    dtype=np.float32,
)
doc_ids = ["leave-policy", "vpn-guide", "benefit-policy", "security-guide"]
```

Câu hỏi review:

- Nếu đổi cosine sang dot product, ranking có thể đổi trong trường hợp nào?
- Với 10 triệu documents, bạn sẽ đổi kiến trúc như thế nào?
- Bạn log những field nào để debug retrieval quality?

## Bài 3: Gradient descent cho `f(x) = x^2`

Viết function:

```python
def gradient_descent_x_squared(start_x, learning_rate, steps):
    ...
```

Output mỗi step:

- `step`
- `x`
- `loss`
- `gradient`

Chạy thử:

```text
start_x = 10
learning_rate = 0.01
learning_rate = 0.1
learning_rate = 0.5
learning_rate = 1.1
```

Câu hỏi review:

- Learning rate nào hội tụ chậm?
- Learning rate nào hội tụ nhanh?
- Learning rate nào dao động hoặc diverge?
- Nếu training model thật bị `NaN loss`, bạn kiểm tra gì trước?

## Bài 4: Risk scoring theo expected loss

Giả sử bạn có feature:

```text
amount_zscore
failed_login_count
new_device_flag
account_age_days_zscore
```

Viết batch scoring:

```python
raw_score = X @ weights + bias
probability = sigmoid(raw_score)
expected_loss = probability * transaction_amount
```

Decision rule:

- `BLOCK` nếu `probability >= 0.85`.
- `REVIEW` nếu `expected_loss >= review_cost`.
- `APPROVE` cho các case còn lại.

Yêu cầu:

- Dùng stable sigmoid.
- Validate shape và finite values.
- Không mutate input.
- Trả về cả probability, expected loss, decision và reason.

Câu hỏi review:

- Vì sao không chỉ dùng threshold `0.5`?
- Khi nào transaction amount lớn nhưng probability thấp vẫn nên review?
- Nếu model probability chưa calibration, rủi ro business là gì?

## Bài 5: Production design mini-review

Thiết kế ngắn một API semantic search nội bộ:

```http
POST /search
{
  "query": "chính sách nghỉ phép",
  "top_k": 5,
  "department": "engineering"
}
```

Bạn cần trả lời:

- Embedding được tạo ở đâu: sync trong request hay async/cache?
- Dùng full scan, ANN index hay vector database?
- Permission filter đặt trước retrieval, trong retrieval hay sau retrieval?
- Có reranker không?
- Monitor metric nào?
- Rollback khi đổi embedding model như thế nào?

Gợi ý best solution theo context:

- Dưới vài nghìn docs: full scan có thể đủ cho prototype.
- Hàng trăm nghìn đến hàng triệu docs: dùng ANN/vector database.
- Tài liệu phân quyền phức tạp: permission-aware retrieval là bắt buộc.
- Domain risk cao: dùng reranker, citation và human-verifiable output.

## Tiêu chí hoàn thành

- Code chạy được với Python 3.11+ và NumPy.
- Có validation cho input xấu.
- Có ít nhất 5 test cases hoặc assert cho edge cases.
- Có giải thích trade-off bằng lời, không chỉ nộp code.
- Trả lời rõ: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## Rubric tự chấm

Mỗi tiêu chí 0-2 điểm:

| Tiêu chí | 0 điểm | 1 điểm | 2 điểm |
|---|---|---|---|
| Correctness | Sai happy path | Đúng happy path | Đúng cả edge cases |
| Validation | Không có | Có shape check | Có shape, finite, zero/range checks |
| Numerical stability | Không xét | Nhận diện rủi ro | Có stable sigmoid/cosine guard |
| Performance reasoning | Không đo | Có timing nhỏ | Có estimate scale và phương án ANN/batch |
| Production decision | Kết luận chung chung | Nêu vài điều kiện | Có metric, security, version, fallback |

Điểm đạt: tối thiểu 8/10 và không có tiêu chí correctness bằng 0.
