# Day 2 Document: Math Cheatsheet cho ML

## Ký hiệu và shape

| Ký hiệu | Ý nghĩa | Shape thường gặp |
|---|---|---|
| `x` | Một vector feature/query | `(d,)` |
| `X` | Batch nhiều samples | `(n, d)` |
| `w` | Vector weight | `(d,)` hoặc `(d, 1)` |
| `W` | Matrix weight nhiều output | `(d, k)` |
| `y` | Label hoặc target | `(n,)` |
| `E` | Embedding matrix | `(num_docs, embedding_dim)` |
| `scores` | Điểm similarity/risk | `(n,)` hoặc `(n, k)` |

Quy tắc debug nhanh:

```text
X @ w -> (n, d) @ (d,) = (n,)
X @ W -> (n, d) @ (d, k) = (n, k)
E @ q -> (num_docs, d) @ (d,) = (num_docs,)
```

## Công thức cần nhớ

### Dot product

```text
dot(a, b) = sum(ai * bi)
```

Dùng cho scoring, projection, linear model, attention.

### Norm L2

```text
||a||2 = sqrt(sum(ai^2))
```

Dùng để chuẩn hóa vector và tính cosine.

### Cosine similarity

```text
cosine(a, b) = dot(a, b) / (||a||2 * ||b||2)
```

Dùng nhiều trong semantic search, RAG retrieval, clustering embedding.

### Sigmoid

```text
sigmoid(z) = 1 / (1 + exp(-z))
```

Đưa raw score về khoảng `(0, 1)` cho binary classification. Muốn dùng như probability thật cần calibration.

### Softmax

```text
softmax(zi) = exp(zi) / sum(exp(zj))
```

Production nên dùng dạng ổn định:

```text
softmax(z) = exp(z - max(z)) / sum(exp(z - max(z)))
```

### Entropy

```text
H(p) = -sum(pi * log(pi))
```

Entropy cao nghĩa là model uncertain hơn. Có thể dùng để route sang review/fallback.

### Expected value

```text
expected_loss = probability * cost_if_wrong
```

Rất hữu ích khi quyết định bằng business cost thay vì threshold cố định.

### Partial derivative, gradient và chain rule

```text
gradient(L) = [
  partial L / partial w1,
  partial L / partial w2,
  ...
]

composed function:
y = f(g(x))
dy/dx = df/dg * dg/dx
```

Debug nhanh:

- Parameter và gradient phải có shape tương thích.
- Loss `NaN`: kiểm tra input finite, learning rate, overflow và divide-by-zero.
- Train loss giảm nhưng validation xấu: kiểm tra overfitting/leakage.

### Bayes

```text
P(A | B) = P(B | A) * P(A) / P(B)
```

`P(A)` là prior/base rate. Với event hiếm, false-positive rate nhỏ vẫn có thể tạo rất nhiều false alarms.

## NumPy reminders

Theo tài liệu NumPy:

- `np.array(..., dtype=np.float32)` tạo `ndarray` với dtype rõ ràng.
- `.shape` cho biết kích thước từng chiều.
- `.dtype` cho biết kiểu dữ liệu.
- `A @ B` là matrix multiplication.
- `A * B` là element-wise multiplication.
- `np.dot`, `np.matmul` cũng hỗ trợ nhân vector/matrix, nhưng `@` thường dễ đọc trong code tuyến tính.
- `np.linalg.norm(x, axis=...)` tính norm.
- `np.isfinite(x)` giúp phát hiện `NaN` và `Inf`.

Ví dụ shape:

```python
import numpy as np

X = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
w = np.array([0.1, 0.2, 0.3], dtype=np.float32)

print(X.shape)  # (2, 3)
print(w.shape)  # (3,)
print((X @ w).shape)  # (2,)
```

## Numerical stability checklist

Trước khi tính toán:

- Kiểm tra shape đúng contract.
- Kiểm tra dtype phù hợp (`float32` hoặc `float64`).
- Kiểm tra không có `NaN`/`Inf`.
- Kiểm tra norm không gần 0 trước khi tính cosine.
- Kiểm tra feature range hợp lý, ví dụ amount không âm.

Khi tính probability:

- Dùng stable sigmoid cho raw score rất lớn/rất nhỏ.
- Dùng stable softmax bằng cách trừ `max(logits)`.
- Không so sánh floating point bằng equality tuyệt đối; dùng tolerance.

Khi đưa ra decision:

- Không hard-code threshold trong model artifact nếu threshold cần thay đổi theo business.
- Log model version, feature version, threshold version.
- Lưu raw score và probability để audit/debug.

## Similarity decision guide

| Bài toán | Metric nên thử trước | Lý do |
|---|---|---|
| Semantic document search | Cosine similarity | So hướng semantic, ít bị magnitude chi phối |
| Recommendation candidate generation | Dot product hoặc cosine | Dot product nếu norm mang tín hiệu popularity/confidence |
| Duplicate detection | Cosine + threshold | Cần tune threshold theo false positive |
| Risk scoring tabular | Linear/logistic score, tree model hoặc gradient boosting | Similarity không phải lựa chọn chính |
| RAG production | ANN retrieval + metadata filter + reranker | Full scan không scale, reranker tăng precision |

## Debug checklist khi kết quả sai

1. Shape có đúng không?
2. Feature order có giống training không?
3. Dtype có bị cast ngoài ý muốn không?
4. Có `NaN`, `Inf`, zero vector không?
5. Embedding query và document có cùng model/version không?
6. Vector có cần normalize trước khi index không?
7. Score distribution có đổi sau deploy không?
8. Threshold có được tune trên validation set đúng domain không?
9. Có data leakage trong evaluation không?
10. Metadata/permission filter có loại nhầm document tốt không?

## Production notes

- Với dữ liệu nhỏ, NumPy full scan đủ để prototype và kiểm thử.
- Với dữ liệu lớn, dùng ANN/vector database, đo recall-latency trade-off.
- Với risk model, probability phải được calibration nếu dùng để tính expected loss.
- Với decision nhạy cảm, cần human-in-the-loop, audit trail và rollback threshold.
- Với embedding nội bộ, vẫn áp dụng access control vì vector có thể leak thông tin qua similarity hoặc reconstruction attack.

## Nguồn tra cứu hiện hành

- NumPy 2.4 docs qua Context7: `/websites/numpy_doc_2_4`.
- Các API đã đối chiếu: `ndarray`, `shape`, `dtype`, broadcasting, `@`, `np.linalg.norm`, `np.isfinite`, `np.argpartition`.
- `np.argpartition` không bảo đảm phần top-k đã sort; cần sort candidate theo score trước khi trả kết quả.
