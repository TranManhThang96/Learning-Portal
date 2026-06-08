# Day 9 Document: NumPy MLP Reference

File này chỉ dùng để tra cứu nhanh khi làm bài. Toàn bộ phần giải thích neuron, activation, forward pass, BCE, backpropagation, gradient descent và production trade-off nằm trong [lession.md](./lession.md).

## 1. Shape Cheat Sheet

| Biến | Shape | Ý nghĩa |
|---|---:|---|
| `X` | `(batch_size, input_dim)` | Batch feature |
| `W1` | `(input_dim, hidden_dim)` | Weight hidden layer |
| `b1` | `(1, hidden_dim)` | Bias broadcast theo batch |
| `A1` | `(batch_size, hidden_dim)` | Hidden activation |
| `W2` | `(hidden_dim, output_dim)` | Weight output layer |
| `b2` | `(1, output_dim)` | Bias output |
| `P`, `Y` | `(batch_size, output_dim)` | Probability và label |

Gradient của tham số phải có cùng shape với tham số đó.

## 2. Công Thức Cốt Lõi

```text
Z1 = X @ W1 + b1
A1 = activation(Z1)
Z2 = A1 @ W2 + b2
P  = sigmoid(Z2)

dZ2 = (P - Y) / batch_size
dW2 = A1.T @ dZ2
db2 = sum(dZ2, axis=0, keepdims=True)
dA1 = dZ2 @ W2.T
dZ1 = dA1 * activation_gradient
dW1 = X.T @ dZ1
db1 = sum(dZ1, axis=0, keepdims=True)
```

## 3. NumPy API Cheat Sheet

| API | Dùng trong bài | Lưu ý |
|---|---|---|
| `a @ b` / `np.matmul(a, b)` | Matrix multiplication | Hai chiều lõi phải tương thích |
| Broadcasting | Cộng bias `(1, dim)` vào batch `(n, dim)` | So shape từ chiều cuối; mỗi cặp phải bằng nhau hoặc một chiều bằng `1` |
| `np.random.default_rng(seed)` | Khởi tạo weight/noise reproducible | Tránh phụ thuộc random state toàn cục |
| `np.clip(x, low, high)` | Bảo vệ `exp` và `log` | Không sửa được công thức sai; chỉ là guardrail số học |
| `np.float32` | Gần dtype DL thông dụng | 4 byte/phần tử, ít precision hơn |
| `np.float64` | Debug toán học | 8 byte/phần tử, NumPy thường mặc định float này |

## 4. Debug Checklist

- [ ] `X` và `Y` đều là mảng 2 chiều.
- [ ] Số dòng của `X` bằng số dòng của `Y`.
- [ ] Feature order và dtype đúng contract.
- [ ] Probability không chứa `nan` hoặc `inf`.
- [ ] Loss hữu hạn và giảm theo thời gian.
- [ ] `gradient.shape == parameter.shape`.
- [ ] Cùng seed/config cho experiment cần so sánh.
- [ ] Chỉ thay một biến mỗi lần khi benchmark.

## 5. Nguồn Đã Xác Minh Bằng Context7

Đối chiếu ngày 8/6/2026 với tài liệu NumPy 2.4:

- [Matrix multiplication (`numpy.matmul` và toán tử `@`)](https://numpy.org/doc/2.4/reference/generated/numpy.matmul.html)
- [Broadcasting rules](https://numpy.org/doc/2.4/user/basics.broadcasting.html)
- [Random Generator và `default_rng`](https://numpy.org/doc/2.4/reference/random/generator.html)
- [NumPy cho người mới](https://numpy.org/doc/2.4/user/absolute_beginners.html)
- [Floating-point error handling](https://numpy.org/doc/2.4/reference/routines.err.html)

## 6. Ghi Chú Phiên Bản

Code bài học chỉ dùng API cơ bản, ổn định qua nhiều phiên bản NumPy. Dù vậy, môi trường production vẫn nên pin phiên bản, ghi dtype/shape vào contract và chạy golden test trước khi nâng dependency.
