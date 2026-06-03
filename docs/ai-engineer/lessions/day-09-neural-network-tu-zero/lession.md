# Day 9: Neural Network từ Zero

## Mục tiêu của ngày học

Sau bài này, bạn cần làm được 7 việc:

1. Giải thích được neuron là `weighted sum + activation`.
2. Phân biệt được Sigmoid, Tanh, ReLU và GELU theo mục đích sử dụng, điểm mạnh, điểm yếu và rủi ro gradient.
3. Viết được forward pass của MLP 2-layer bằng NumPy với shape contract rõ ràng.
4. Hiểu binary cross entropy loss và vì sao cần clipping khi tính `log`.
5. Theo dõi được backpropagation từng bước từ output layer về hidden layer.
6. Train được MLP 2-layer trên XOR dataset bằng gradient descent.
7. Trả lời được khi nào code NumPy tự viết chỉ để học, khi nào concept có thể đưa vào production và cần điều kiện gì.

## Cách học đề xuất trong 2.5 giờ

| Thời lượng | Việc cần làm | Output |
|---:|---|---|
| 15 phút | Đọc TL;DR, mental model và shape contract trong file này | Nắm được network là một function có tham số học từ data |
| 45 phút | Đọc [document.md](./document.md) phần neuron, activation, forward pass và loss | Hiểu đường đi của data từ `X` đến `y_hat` |
| 35 phút | Đọc phần backpropagation và gradient descent | Tự suy ra được shape của từng gradient |
| 45 phút | Chạy [exercise.md](./exercise.md) với [xor_mlp_numpy.py](./xor_mlp_numpy.py) | Train được XOR, thấy loss giảm và prediction đúng |
| 10 phút | Làm checklist và production review | Biết giới hạn của NumPy implementation |

## TL;DR

Neural network là một hàm có nhiều layer. Mỗi layer nhận input dạng ma trận, nhân với weight, cộng bias, rồi đi qua activation:

```text
Z = X @ W + b
A = activation(Z)
```

Nếu không có activation, nhiều linear layer gộp lại vẫn chỉ là một linear function. Activation tạo non-linearity, nhờ vậy MLP có thể học bài toán XOR mà Logistic Regression tuyến tính không học được.

Training là vòng lặp:

```text
forward pass -> loss -> backward pass -> gradient descent update
```

Trong production, bạn gần như không tự viết backprop bằng NumPy cho training thật. Bạn dùng PyTorch, TensorFlow hoặc framework tương đương để có autograd, GPU, checkpoint, mixed precision, distributed training, profiler và ecosystem deployment. Nhưng hiểu NumPy implementation giúp bạn debug shape, loss curve, exploding/vanishing gradient, learning rate và train-serving skew tốt hơn.

## Mental model cho Senior SE

| Neural Network | Cách nhìn của Senior SE |
|---|---|
| Input tensor `X` | Request payload hoặc batch record đã được chuẩn hóa |
| Weight `W` | Config học từ data, không viết tay |
| Bias `b` | Offset/default học được |
| Activation | Transform/policy phi tuyến |
| Forward pass | Runtime request flow |
| Loss | Objective kỹ thuật để tối ưu |
| Metric | Acceptance criteria theo use case |
| Gradient | Tín hiệu feedback cho từng tham số |
| Optimizer | Update strategy |
| Model artifact | Build artifact cần version, test, rollback |

Điểm khác backend truyền thống: model không chỉ pass/fail theo rule cố định. Model trả score xác suất, và policy layer mới quyết định action cuối cùng theo threshold, risk, cost và business constraint.

## Shape contract tối thiểu

Trong bài này ta dùng binary classification với batch input:

| Ký hiệu | Shape | Ý nghĩa |
|---|---:|---|
| `X` | `(batch_size, input_dim)` | Batch input |
| `W1` | `(input_dim, hidden_dim)` | Weight hidden layer |
| `b1` | `(1, hidden_dim)` | Bias hidden layer, broadcast theo batch |
| `Z1` | `(batch_size, hidden_dim)` | Weighted sum hidden layer |
| `A1` | `(batch_size, hidden_dim)` | Activation hidden layer |
| `W2` | `(hidden_dim, output_dim)` | Weight output layer |
| `b2` | `(1, output_dim)` | Bias output layer |
| `Z2` | `(batch_size, output_dim)` | Logit output |
| `P` | `(batch_size, output_dim)` | Probability sau Sigmoid |
| `Y` | `(batch_size, output_dim)` | Label |

NumPy dùng toán tử `@` cho matrix multiplication. Bias có shape `(1, hidden_dim)` hoặc `(1, output_dim)` để NumPy broadcasting cộng bias vào từng dòng của batch. Đây là contract cần giữ nghiêm; sai shape là nguồn bug phổ biến nhất khi chuyển từ ý tưởng toán học sang code.

## Bản đồ nội dung

- Học phần chính: [document.md](./document.md)
- Bài thực hành: [exercise.md](./exercise.md)
- Script chạy được: [xor_mlp_numpy.py](./xor_mlp_numpy.py)

## Deliverable cuối ngày

Bạn nên có 3 output:

1. Một lần chạy XOR thành công với loss giảm và prediction đúng 4 điểm.
2. Một bảng so sánh ngắn giữa `hidden_dim`, `learning_rate` và `activation`.
3. Một đoạn production review trả lời: có nên tự viết MLP bằng NumPy cho production không, nếu không thì dùng framework nào và cần guardrail gì.

## Dùng được trong production không? Nếu có thì cần điều kiện gì?

Concept trong bài dùng được trong production. Code NumPy trong bài chủ yếu dùng để học và kiểm chứng toán học.

Không nên dùng code NumPy tự viết cho production training vì:

- Không có autograd, gradient dễ sai và khó review khi model lớn hơn.
- Không tận dụng tốt GPU, mixed precision, distributed training và optimizer hiện đại.
- Thiếu checkpointing, profiler, model export, experiment tracking và ecosystem deployment.
- Dễ thiếu test cho numerical stability, data drift và train-serving skew.

Có thể dùng một implementation NumPy nhỏ trong production inference chỉ khi scope rất hẹp, model rất nhỏ, không cần GPU, đã freeze weights và có đầy đủ điều kiện:

- Shape contract, dtype và feature order được validate.
- Preprocessing được version cùng model artifact.
- Có golden tests cho input/output, threshold và edge cases.
- Có benchmark p50/p95/p99 latency trên hardware thật.
- Có monitoring cho latency, error rate, prediction distribution, data quality và drift.
- Có rollback plan, artifact versioning và owner rõ ràng.

Best solution theo context:

- Học concept, debug toán học: dùng NumPy như bài này.
- Training neural network thật: dùng PyTorch hoặc TensorFlow.
- Tabular data ít hoặc vừa, cần explainability: bắt đầu bằng Logistic Regression, Random Forest hoặc XGBoost trước khi dùng MLP.
- Inference production: ưu tiên artifact chuẩn của framework, có serving stack, monitoring và rollback.

## Checklist hoàn thành

- [ ] Tôi giải thích được `z = X @ W + b` và `a = activation(z)`.
- [ ] Tôi biết khi nào dùng Sigmoid, Tanh, ReLU và GELU.
- [ ] Tôi viết được shape của `W1`, `b1`, `A1`, `W2`, `b2`, `P`.
- [ ] Tôi hiểu vì sao BCE cần clipping probability khi tự tính bằng NumPy.
- [ ] Tôi suy ra được `dW2 = A1.T @ dZ2` và `dW1 = X.T @ dZ1`.
- [ ] Tôi train được XOR bằng NumPy MLP 2-layer.
- [ ] Tôi visualize hoặc ít nhất log được loss giảm theo epoch.
- [ ] Tôi nêu được trade-off giữa NumPy tự viết và framework autograd.
- [ ] Tôi trả lời được điều kiện để concept neural network được dùng trong production.
