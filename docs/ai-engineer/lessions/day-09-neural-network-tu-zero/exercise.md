# Exercise: MLP 2-layer bằng NumPy trên XOR

## Mục tiêu thực hành

Sau phần này, bạn cần:

- Chạy được MLP 2-layer bằng NumPy, không dùng framework deep learning.
- Thấy loss giảm theo epoch.
- Predict đúng XOR dataset.
- Thay đổi `hidden_dim`, `learning_rate`, `activation`, `dtype` và quan sát trade-off.
- Biết cách đọc shape contract và debug khi model không học.

## Chuẩn bị môi trường

Yêu cầu tối thiểu:

```bash
python3 -m pip install numpy
```

Nếu muốn visualize loss:

```bash
python3 -m pip install matplotlib
```

Script chính:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --help
```

Nếu bạn đã active virtualenv và `python` trỏ đúng interpreter có NumPy, có thể thay `python3` bằng `python`.

## Bài 1: Chạy baseline XOR

Chạy:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py \
  --hidden-dim 4 \
  --activation tanh \
  --learning-rate 0.5 \
  --epochs 8000 \
  --seed 42 \
  --assert-xor
```

Kỳ vọng:

- `final_loss` nhỏ hơn `0.05`.
- `accuracy=1.000`.
- `predictions` khớp với `expected`.
- Probability gần 0 cho `[0,0]`, `[1,1]` và gần 1 cho `[0,1]`, `[1,0]`.

Ví dụ output có thể khác nhẹ theo NumPy/runtime, nhưng pattern phải giống:

```text
final_loss=0.0...
accuracy=1.000
predictions=
[[0]
 [1]
 [1]
 [0]]
expected=
[[0]
 [1]
 [1]
 [0]]
```

## Bài 2: Visualize loss

Nếu đã cài matplotlib:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py \
  --hidden-dim 4 \
  --activation tanh \
  --learning-rate 0.5 \
  --epochs 8000 \
  --seed 42 \
  --plot \
  --plot-path /tmp/day09-xor-loss.png
```

Quan sát:

- Loss có giảm đều không?
- Có plateau không?
- Có đoạn dao động mạnh không?
- Nếu tăng learning rate, đường loss thay đổi thế nào?

Trong production, loss curve là observability tối thiểu của training. Nếu không log loss/metric, bạn không biết model đang học hay chỉ đang chạy.

## Bài 3: So sánh hidden size

Chạy 3 cấu hình:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --hidden-dim 2 --activation tanh --learning-rate 0.5 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --hidden-dim 4 --activation tanh --learning-rate 0.5 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --hidden-dim 8 --activation tanh --learning-rate 0.5 --epochs 8000 --seed 42
```

Ghi lại:

| hidden_dim | final_loss | accuracy | Nhận xét |
|---:|---:|---:|---|
| 2 | | | |
| 4 | | | |
| 8 | | | |

Câu hỏi:

1. `hidden_dim=2` có luôn học được với seed này không?
2. `hidden_dim=8` có giảm loss nhanh hơn không?
3. Model lớn hơn có luôn tốt hơn trong production không?

Gợi ý production: hidden size lớn hơn tăng capacity nhưng cũng tăng memory, latency, risk overfitting và cost.

## Bài 4: So sánh learning rate

Chạy:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --learning-rate 0.01 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --learning-rate 0.1 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --learning-rate 0.5 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --learning-rate 1.5 --epochs 8000 --seed 42
```

Ghi lại:

| learning_rate | final_loss | accuracy | Loss behavior |
|---:|---:|---:|---|
| 0.01 | | | |
| 0.1 | | | |
| 0.5 | | | |
| 1.5 | | | |

Câu hỏi:

1. Learning rate nào học chậm?
2. Learning rate nào dễ dao động?
3. Khi loss thành `nan`, bạn sẽ debug theo thứ tự nào?

Best solution theo context: bắt đầu từ learning rate vừa phải, log loss, sau đó tune. Với framework thật, dùng optimizer như Adam và scheduler khi bài toán phức tạp hơn.

## Bài 5: So sánh activation

Chạy:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --activation tanh --learning-rate 0.5 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --activation relu --learning-rate 0.1 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --activation sigmoid --learning-rate 0.5 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --activation gelu --learning-rate 0.1 --epochs 8000 --seed 42
```

Ghi lại:

| activation | learning_rate | final_loss | accuracy | Nhận xét |
|---|---:|---:|---:|---|
| tanh | 0.5 | | | |
| relu | 0.1 | | | |
| sigmoid | 0.5 | | | |
| gelu | 0.1 | | | |

Câu hỏi:

1. Activation nào ổn định nhất cho XOR với seed này?
2. Sigmoid hidden layer học chậm hơn không?
3. ReLU có bị kẹt với một số seed không?
4. GELU có đáng dùng cho bài toán nhỏ này không?

Trade-off: activation không có lựa chọn tốt tuyệt đối. ReLU nhanh và phổ biến; GELU hợp Transformer; Sigmoid hợp output probability; Tanh dễ minh họa bài học nhỏ.

## Bài 6: Dtype và numerical stability

So sánh:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --dtype float32 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --dtype float64 --epochs 8000 --seed 42
```

Ghi lại:

| dtype | final_loss | accuracy | Nhận xét |
|---|---:|---:|---|
| float32 | | | |
| float64 | | | |

Câu hỏi:

1. Với XOR, `float64` có cải thiện đáng kể không?
2. Vì sao deep learning production thường ưu tiên `float32`, `float16` hoặc `bfloat16` hơn `float64`?
3. Vì sao BCE trong script phải clip probability trước khi gọi `log`?

## Bài 7: Thêm noise vào input

Chạy:

```bash
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --noise-std 0.05 --epochs 8000 --seed 42
python3 lessions/day-09-neural-network-tu-zero/xor_mlp_numpy.py --noise-std 0.20 --epochs 8000 --seed 42
```

Quan sát:

- Probability có còn tự tin không?
- Prediction có còn đúng 4 điểm không?
- Loss có tăng không?

Production lesson: dữ liệu thật hiếm khi sạch như XOR. Nếu feature noisy hoặc distribution thay đổi, cần validation set, monitoring drift và retraining strategy.

## Bài 8: Đọc shape contract trong code

Mở [xor_mlp_numpy.py](./xor_mlp_numpy.py), tìm các dòng:

```python
Z1 = X @ self.W1 + self.b1
A1 = activation_forward(self.config.activation, Z1)
Z2 = A1 @ self.W2 + self.b2
P = sigmoid(Z2)
```

Tự điền shape:

| Biến | Shape |
|---|---:|
| `X` | |
| `W1` | |
| `b1` | |
| `Z1` | |
| `A1` | |
| `W2` | |
| `b2` | |
| `P` | |

Sau đó đọc backward:

```python
dZ2 = (P - Y) / batch_size
dW2 = cache["A1"].T @ dZ2
db2 = np.sum(dZ2, axis=0, keepdims=True)
dA1 = dZ2 @ self.W2.T
dZ1 = dA1 * activation_backward(...)
dW1 = cache["X"].T @ dZ1
db1 = np.sum(dZ1, axis=0, keepdims=True)
```

Tự điền shape:

| Gradient | Shape |
|---|---:|
| `dZ2` | |
| `dW2` | |
| `db2` | |
| `dA1` | |
| `dZ1` | |
| `dW1` | |
| `db1` | |

Rule kiểm tra nhanh: gradient của tham số nào phải có đúng shape của tham số đó.

## Bài 9: Production review

Viết một đoạn 10-15 dòng trả lời:

```text
Nếu team muốn dùng MLP cho một bài toán churn/fraud/ticket classification, tôi sẽ:
1. Bắt đầu bằng baseline nào?
2. Khi nào tôi mới chọn neural network?
3. Tôi có dùng code NumPy tự viết này không?
4. Nếu không, tôi dùng framework nào và vì sao?
5. Artifact cần version những gì?
6. Monitoring production gồm những metric nào?
7. Rollback/fallback ra sao?
```

Câu trả lời kỳ vọng:

- Baseline trước: Logistic Regression, tree-based model hoặc XGBoost cho tabular.
- Chọn neural network khi pattern phi tuyến phức tạp, data đủ và baseline không đạt.
- Không dùng NumPy tự viết cho production training.
- Dùng PyTorch/TensorFlow để có autograd, checkpoint, GPU, ecosystem.
- Version preprocessing, feature order, model architecture, weights, threshold, dataset và package.
- Monitor latency, error rate, prediction distribution, data quality, drift và delayed labels.
- Có fallback baseline hoặc model artifact trước đó.

## Checklist hoàn thành

- [ ] Baseline XOR chạy thành công với `--assert-xor`.
- [ ] Tôi có loss curve hoặc log loss giảm theo epoch.
- [ ] Tôi đã so sánh ít nhất 3 `hidden_dim`.
- [ ] Tôi đã so sánh ít nhất 3 `learning_rate`.
- [ ] Tôi đã chạy ít nhất 2 activation khác nhau.
- [ ] Tôi giải thích được shape của forward và backward.
- [ ] Tôi giải thích được vì sao cần clipping cho Sigmoid/BCE.
- [ ] Tôi viết được production review ngắn.
