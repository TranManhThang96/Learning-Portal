# Day 9: Neural Network từ Zero

## Mục tiêu của ngày học

Sau bài này, bạn cần làm được:

1. Giải thích neuron là `weighted sum + activation`.
2. Phân biệt Sigmoid, Tanh, ReLU và GELU theo mục đích, ưu điểm và rủi ro gradient.
3. Viết forward pass của MLP 2-layer bằng NumPy với shape contract rõ ràng.
4. Hiểu Binary Cross Entropy (BCE) và vì sao cần bảo vệ phép `log`.
5. Theo dõi backpropagation từng bước từ output layer về hidden layer.
6. Train MLP 2-layer trên XOR bằng gradient descent và đọc loss curve.
7. Giải thích vì sao code NumPy phù hợp để học nhưng framework autograd phù hợp hơn cho production.

## Cách học đề xuất

| Thời lượng | Việc cần làm | Output |
|---:|---|---|
| 20 phút | Đọc neuron, matrix form và shape contract | Tự viết được shape của mọi tensor |
| 35 phút | Đọc activation, forward pass và BCE | Hiểu đường đi từ `X` đến probability |
| 40 phút | Theo dõi backpropagation step-by-step | Kiểm tra được shape từng gradient |
| 50 phút | Làm [exercise.md](./exercise.md) với [xor_mlp_numpy.py](./xor_mlp_numpy.py) | Train XOR, quan sát loss và prediction |
| 15 phút | Làm quiz, checklist và production review | Biết giới hạn của implementation |

## TL;DR

Một layer nhận batch input, nhân với weight, cộng bias rồi áp dụng activation:

```text
Z = X @ W + b
A = activation(Z)
```

Nếu không có activation, nhiều linear layer vẫn chỉ tương đương một linear function. Activation tạo tính phi tuyến, nhờ đó MLP học được XOR. Training lặp lại bốn bước:

```text
forward pass -> loss -> backward pass -> update parameters
```

Day 9 cố ý tự viết gradient để bạn nhìn thấy cơ chế. Day 10 sẽ thay phần đạo hàm thủ công bằng PyTorch autograd.

## Bản đồ từ Day 8 sang Day 10

```text
Day 8: classical ML pipeline
  -> khi quan hệ đơn giản/bảng dữ liệu: baseline thường đã đủ tốt
  -> khi cần học representation phi tuyến:
Day 9: tự xây MLP bằng NumPy để hiểu math và shape
  ->
Day 10: dùng Tensor + autograd + nn.Module để triển khai đúng framework
```

## 1. Vì sao cần Neural Network?

Các model tuyến tính như Linear Regression hoặc Logistic Regression học được quan hệ dạng:

```text
score = w1*x1 + w2*x2 + ... + wn*xn + b
```

Chúng mạnh, nhanh, dễ explain và thường là baseline tốt. Nhưng chúng gặp giới hạn khi pattern là phi tuyến. XOR là ví dụ kinh điển:

| x1 | x2 | y |
|---:|---:|---:|
| 0 | 0 | 0 |
| 0 | 1 | 1 |
| 1 | 0 | 1 |
| 1 | 1 | 0 |

Không có một đường thẳng nào tách được class 0 và 1 trong không gian 2 chiều. MLP với hidden layer có activation phi tuyến có thể biến đổi không gian input trước, rồi output layer phân loại trên representation mới.

Mental model thực dụng:

```text
raw features -> learned representation -> prediction score -> business policy
```

Neural network hữu ích khi feature interaction phức tạp, pattern phi tuyến rõ, dữ liệu đủ lớn và cost/latency chấp nhận được. Với tabular data ít, classical ML vẫn thường là lựa chọn đầu tiên.

## 2. Neuron = Weighted Sum + Activation

Một neuron nhận nhiều feature đầu vào:

```text
z = w1*x1 + w2*x2 + ... + wn*xn + b
a = activation(z)
```

Trong đó:

- `x`: feature input.
- `w`: weight học từ data.
- `b`: bias học từ data.
- `z`: weighted sum, còn gọi là pre-activation.
- `a`: output sau activation.

Ví dụ:

```text
x = [0.8, 0.2]
w = [2.0, -1.0]
b = -0.5

z = 0.8*2.0 + 0.2*(-1.0) - 0.5 = 0.9
```

Nếu dùng ReLU:

```text
a = max(0, 0.9) = 0.9
```

Nếu dùng Sigmoid:

```text
a = 1 / (1 + exp(-0.9)) ≈ 0.711
```

Neuron riêng lẻ rất đơn giản. Sức mạnh đến từ việc ghép nhiều neuron thành layer, rồi ghép nhiều layer thành network.

## 3. Matrix form và shape contract

Trong code production-like, ta không loop từng record rồi từng neuron. Ta xử lý theo batch bằng matrix multiplication:

```text
Z = X @ W + b
A = activation(Z)
```

Shape:

| Ký hiệu | Shape | Ghi chú |
|---|---:|---|
| `X` | `(batch_size, input_dim)` | Mỗi dòng là một sample |
| `W` | `(input_dim, output_dim)` | Mỗi cột tương ứng một neuron output |
| `b` | `(1, output_dim)` | Broadcast theo `batch_size` |
| `Z` | `(batch_size, output_dim)` | Pre-activation |
| `A` | `(batch_size, output_dim)` | Post-activation |

NumPy hỗ trợ toán tử `@` cho matrix multiplication, tương đương `np.matmul` trong trường hợp 2D phổ biến. NumPy broadcasting cho phép cộng `b` shape `(1, output_dim)` vào `Z` shape `(batch_size, output_dim)` khi chiều tương ứng bằng nhau hoặc một chiều là `1`.

Shape contract là API contract của model. Nếu `X` bị đảo thành `(input_dim, batch_size)`, code có thể crash ngay hoặc tệ hơn là chạy ra kết quả sai. Vì vậy script thực hành có `_check_2d` và kiểm tra số chiều trước khi forward.

## 4. Activation functions

Nếu chỉ ghép linear layer:

```text
Y = (X @ W1 + b1) @ W2 + b2
```

Ta có thể viết lại thành một linear layer khác:

```text
Y = X @ (W1 @ W2) + (b1 @ W2 + b2)
```

Nhiều layer nhưng không có activation vẫn không học được quan hệ phi tuyến. Activation phá tính tuyến tính này.

### Sigmoid

```text
sigmoid(x) = 1 / (1 + exp(-x))
```

Đặc điểm:

- Output nằm trong `(0, 1)`.
- Phù hợp ở output layer cho binary classification.
- Có thể hiểu như probability nếu model được train và calibrate tốt.
- Dễ bị vanishing gradient khi `x` quá âm hoặc quá dương.
- Khi tự tính bằng NumPy, nên clip input để tránh overflow trong `exp`.

Derivative nếu đã có output `s`:

```text
sigmoid'(x) = s * (1 - s)
```

### Tanh

```text
tanh(x) = (exp(x) - exp(-x)) / (exp(x) + exp(-x))
```

Đặc điểm:

- Output nằm trong `(-1, 1)`.
- Center quanh 0, thường dễ tối ưu hơn Sigmoid ở hidden layer nhỏ.
- Vẫn bị vanishing gradient khi input có độ lớn cao.
- Tốt cho bài học XOR vì đạo hàm đơn giản và model nhỏ.

Derivative nếu đã có output `t`:

```text
tanh'(x) = 1 - t^2
```

### ReLU

```text
relu(x) = max(0, x)
```

Đặc điểm:

- Nhanh, đơn giản, phổ biến cho hidden layer.
- Giảm vanishing gradient ở vùng dương.
- Có thể gặp dead neuron nếu neuron luôn nhận input âm, gradient bằng 0.
- Thường là default hợp lý cho MLP/CNN cổ điển.

Derivative:

```text
relu'(x) = 1 nếu x > 0, ngược lại 0
```

### GELU

GELU thường gặp trong Transformer như BERT/GPT-style models. Công thức gần đúng phổ biến:

```text
gelu(x) ≈ 0.5*x*(1 + tanh(sqrt(2/pi)*(x + 0.044715*x^3)))
```

Đặc điểm:

- Mượt hơn ReLU vì không cắt cứng tại 0.
- Cho phép một phần giá trị âm đi qua theo xác suất/độ lớn.
- Tốn compute hơn ReLU.
- Thường là lựa chọn tốt trong Transformer, không phải luôn cần cho MLP nhỏ.

### Bảng trade-off activation

| Activation | Điểm mạnh | Điểm yếu | Khi dùng |
|---|---|---|---|
| Sigmoid | Output 0-1, hợp binary probability | Vanishing gradient, dễ overflow nếu không clip | Output layer binary |
| Tanh | Center quanh 0, dễ học XOR | Vẫn vanishing gradient | Hidden layer nhỏ, bài học từ zero |
| ReLU | Nhanh, gradient tốt vùng dương | Dead neuron | Default hidden layer MLP/CNN |
| GELU | Mượt, mạnh trong Transformer | Tốn compute hơn ReLU | Transformer, model lớn |

Best solution theo context của bài: dùng Tanh hoặc ReLU ở hidden layer để học XOR; dùng Sigmoid ở output layer để trả probability.

## 5. Forward pass của MLP 2-layer

MLP 2-layer trong bài này nghĩa là:

1. Hidden layer: linear transform + activation.
2. Output layer: linear transform + Sigmoid.

Với batch `X`:

```text
Z1 = X @ W1 + b1
A1 = activation(Z1)
Z2 = A1 @ W2 + b2
P  = sigmoid(Z2)
```

Shape đầy đủ:

| Biến | Shape với XOR | Shape tổng quát |
|---|---:|---:|
| `X` | `(4, 2)` | `(batch_size, input_dim)` |
| `Y` | `(4, 1)` | `(batch_size, output_dim)` |
| `W1` | `(2, hidden_dim)` | `(input_dim, hidden_dim)` |
| `b1` | `(1, hidden_dim)` | `(1, hidden_dim)` |
| `Z1` | `(4, hidden_dim)` | `(batch_size, hidden_dim)` |
| `A1` | `(4, hidden_dim)` | `(batch_size, hidden_dim)` |
| `W2` | `(hidden_dim, 1)` | `(hidden_dim, output_dim)` |
| `b2` | `(1, 1)` | `(1, output_dim)` |
| `P` | `(4, 1)` | `(batch_size, output_dim)` |

Trong serving, forward pass là phần bạn chạy nhiều nhất. Vì vậy code phải rõ shape, vectorized và không có Python loop theo sample nếu không cần.

## 6. Loss function: Binary Cross Entropy

Với binary classification, model output probability `p` và label `y` thuộc `{0, 1}`. Binary Cross Entropy:

```text
BCE(y, p) = - y*log(p) - (1-y)*log(1-p)
```

Mean loss trên batch:

```text
loss = mean(BCE(Y, P))
```

Ý nghĩa:

- Nếu `y = 1`, model bị phạt khi `p` thấp.
- Nếu `y = 0`, model bị phạt khi `p` cao.
- Dự đoán càng tự tin nhưng sai, loss càng lớn.

Vấn đề số học:

- `log(0)` là vô hạn âm.
- Sigmoid có thể trả giá trị rất gần 0 hoặc 1.
- Khi tự tính bằng NumPy, cần `np.clip(P, eps, 1 - eps)` trước khi `log`.

Trong framework production, thường dùng loss nhận logits trực tiếp như `BCEWithLogitsLoss` để ổn định số học hơn. Trong bài này ta dùng Sigmoid + BCE đã clip để dễ nhìn thấy forward pass.

## 7. Backpropagation step by step

Backpropagation là cách áp dụng chain rule để tính gradient của loss theo từng tham số.

Forward:

```text
Z1 = X @ W1 + b1
A1 = activation(Z1)
Z2 = A1 @ W2 + b2
P  = sigmoid(Z2)
L  = BCE(Y, P)
```

Backward đi ngược từ loss:

```text
dZ2 = (P - Y) / m
dW2 = A1.T @ dZ2
db2 = sum(dZ2, axis=0, keepdims=True)

dA1 = dZ2 @ W2.T
dZ1 = dA1 * activation_grad(Z1 hoặc A1)
dW1 = X.T @ dZ1
db1 = sum(dZ1, axis=0, keepdims=True)
```

Trong đó `m = batch_size`.

### Vì sao `dZ2 = (P - Y) / m`?

Khi kết hợp Sigmoid output và BCE loss, đạo hàm rút gọn rất đẹp:

```text
dL/dZ2 = P - Y
```

Nếu loss là mean trên batch, chia thêm cho `m`.

Đây là lý do nhiều implementation binary classification dùng logits/probability rất cẩn thận: nếu tách sai công thức hoặc quên scale batch, learning rate sẽ khó tuning.

### Shape của gradient

Gradient của một tham số phải có cùng shape với tham số đó:

| Gradient | Công thức | Shape |
|---|---|---:|
| `dZ2` | `(P - Y) / m` | `(batch_size, output_dim)` |
| `dW2` | `A1.T @ dZ2` | `(hidden_dim, output_dim)` |
| `db2` | `sum(dZ2, axis=0, keepdims=True)` | `(1, output_dim)` |
| `dA1` | `dZ2 @ W2.T` | `(batch_size, hidden_dim)` |
| `dZ1` | `dA1 * activation_grad(...)` | `(batch_size, hidden_dim)` |
| `dW1` | `X.T @ dZ1` | `(input_dim, hidden_dim)` |
| `db1` | `sum(dZ1, axis=0, keepdims=True)` | `(1, hidden_dim)` |

Nếu `dW1.shape != W1.shape`, backward đang sai. Đây là check đơn giản nhưng cực kỳ hữu ích.

## 8. Gradient descent

Sau khi có gradient, cập nhật tham số:

```text
W = W - learning_rate * dW
b = b - learning_rate * db
```

Learning rate là hyperparameter nhạy:

- Quá lớn: loss dao động, tăng mạnh hoặc ra `nan`.
- Quá nhỏ: loss giảm rất chậm.
- Vừa đủ: loss giảm ổn định và prediction cải thiện.

Trong bài này dùng full-batch gradient descent vì XOR chỉ có 4 điểm. Với dataset lớn, mini-batch gần như là default vì:

- Không cần load toàn bộ data vào memory cho mỗi update.
- Tăng throughput tốt hơn trên GPU/accelerator.
- Noise từ mini-batch đôi khi giúp generalization.

## 9. Initialization, seed và dtype

### Seed

Neural network bắt đầu từ weight random. Nếu không set seed, mỗi lần chạy có thể ra loss curve khác nhau. NumPy khuyến nghị dùng `np.random.default_rng(seed)` thay vì API random global cũ vì:

- Không phụ thuộc global random state.
- Dễ truyền RNG vào function/class.
- Reproducibility rõ hơn.

### Initialization

Nếu tất cả weight bằng 0, các neuron trong cùng một layer nhận gradient giống nhau và học giống nhau. Cần random initialization để phá symmetry.

Scale initialization nên phụ thuộc `fan_in`:

- Tanh/Sigmoid: thường dùng scale gần Xavier, ví dụ `sqrt(1 / fan_in)`.
- ReLU/GELU: thường dùng scale gần He, ví dụ `sqrt(2 / fan_in)`.

Trong bài, script chọn scale theo activation để model học XOR ổn định hơn.

### dtype

Trade-off:

| dtype | Ưu điểm | Nhược điểm | Khi dùng |
|---|---|---|---|
| `float64` | Chính xác hơn, tốt để học/debug numeric | Tốn RAM gấp đôi, thường chậm hơn | Notebook học toán, gradient check |
| `float32` | Gần default deep learning, nhanh và tiết kiệm RAM hơn | Ít precision hơn | Training/inference thông thường |

Script hỗ trợ `--dtype float32` và `--dtype float64`. Với XOR, cả hai đều đủ.

## 10. NumPy implementation design

Code thực hành dùng các nguyên tắc sau:

- Vectorized `@` thay vì loop từng sample.
- Bias shape `(1, dim)` để broadcasting rõ ràng.
- `np.random.default_rng(seed)` để reproducible.
- Shape checks cho input, label và output.
- Sigmoid clip input trước `exp`.
- BCE clip probability trước `log`.
- Logging loss theo `log_every`.
- Optional matplotlib để visualize loss, nhưng script vẫn chạy nếu không cài matplotlib.

Đây là code gần production theo nghĩa engineering hygiene, không phải production training stack. Nó có contract, validation và observability tối thiểu, nhưng không thay thế autograd framework.

## 11. XOR dataset

XOR nhỏ nhưng hữu ích vì:

- Dễ kiểm tra bằng mắt.
- Bắt buộc model học non-linearity.
- Nếu model linear không học được, bạn thấy rõ giới hạn của baseline tuyến tính.
- Nếu MLP học được, bạn thấy hidden layer đang tạo representation mới.

Dataset:

```python
X = np.array(
    [
        [0.0, 0.0],
        [0.0, 1.0],
        [1.0, 0.0],
        [1.0, 1.0],
    ],
    dtype=np.float32,
)

Y = np.array([[0.0], [1.0], [1.0], [0.0]], dtype=np.float32)
```

Với `hidden_dim=4`, `activation=tanh`, `learning_rate=0.5`, model thường học được XOR sau vài nghìn epoch.

## 12. Trade-off quan trọng

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Production note |
|---|---|---|---|
| NumPy tự viết | Học concept, kiểm chứng shape/gradient | Training thật, model lớn | Dễ sai gradient, không có autograd/GPU ecosystem |
| PyTorch/TensorFlow | Deep learning production, GPU, checkpoint | Bài toán classical ML đơn giản | Default cho neural network thật |
| Sigmoid output | Binary probability | Hidden layer sâu | Nên dùng logits loss trong framework |
| Tanh hidden | Model nhỏ, cần output centered | Network sâu dễ vanishing gradient | Hợp bài XOR |
| ReLU hidden | Default MLP/CNN | Risk dead neuron, output probability | Nhanh, đơn giản |
| GELU hidden | Transformer/model lớn | MLP nhỏ cần latency thấp | Mượt nhưng tốn compute |
| Full batch | Dataset rất nhỏ | Dataset lớn | Ổn định nhưng tốn RAM |
| Mini-batch | Dataset vừa/lớn | Batch quá nhỏ gây noisy | Default training thực tế |
| `float32` | Training/inference thông thường | Cần debug precision cao | Tiết kiệm RAM và nhanh hơn |
| `float64` | Học toán, gradient check | Production latency/memory chặt | Chính xác hơn nhưng đắt hơn |

## 13. Performance considerations

### Vectorization

Matrix multiplication là workload chính. NumPy gọi các thư viện tối ưu thấp hơn như BLAS tùy môi trường cài đặt. Vì vậy:

- `X @ W` nhanh hơn loop Python theo sample và neuron.
- Batch processing tận dụng CPU cache và vectorized kernel tốt hơn.
- Loop Python chỉ nên dùng cho control flow hoặc logging, không dùng cho toán lõi nếu có thể vectorize.

### Memory

Memory activation xấp xỉ:

```text
batch_size * hidden_dim * dtype_size
```

Ví dụ `batch_size=4096`, `hidden_dim=1024`, `float32=4 bytes`:

```text
4096 * 1024 * 4 ≈ 16 MB
```

Đó mới chỉ là một activation. Training cần lưu nhiều activation và gradient hơn inference.

### Latency

Với MLP nhỏ, inference CPU có thể rất nhanh. Nhưng production không đo bằng cảm giác:

- Benchmark trên input thật.
- Đo p50, p95, p99 latency.
- Đo throughput theo batch size.
- Đo memory peak.
- Đo cold start nếu model load theo request hoặc serverless.

### Numerical stability

Các lỗi phổ biến:

- `np.exp` overflow với input quá lớn.
- `log(0)` khi BCE nhận probability đúng 0 hoặc 1.
- Loss thành `nan`.
- Gradient quá lớn làm weight nổ.

Guardrail trong bài:

- Clip Sigmoid input.
- Clip BCE probability.
- Có `--clip-grad-norm` optional để quan sát gradient clipping.
- Log loss định kỳ.

## 14. Production architecture mapping

Một neural network production không chỉ là file weight.

```text
training data version
        |
feature/preprocessing code version
        |
training config + seed + package versions
        |
model artifact + metrics + threshold
        |
serving API + monitoring + rollback
```

Những thứ cần version cùng nhau:

- Feature order và feature schema.
- Preprocessing/scaling/encoding.
- Model architecture.
- Weights.
- Threshold/policy.
- Training dataset snapshot hoặc data version.
- Package/runtime version.

Monitoring tối thiểu:

- Request count, latency p50/p95/p99, error rate.
- Prediction distribution.
- Input null rate, out-of-range rate, schema violation.
- Segment-level metric nếu có delayed label.
- Drift signal.
- Cost và resource utilization.

Testing tối thiểu:

- Unit test activation/loss shape.
- Golden test cho một vài input cố định.
- Contract test cho feature order và dtype.
- Regression test cho metric trên validation set.
- Load test cho latency/memory.
- Rollback drill cho artifact cũ.

## 15. Dùng được trong production không?

Có, nhưng cần tách rõ "concept" và "code trong bài".

Concept neural network dùng production rất rộng rãi: classification, ranking, recommendation, NLP, computer vision, fraud detection, personalization. Điều kiện là có data đủ tốt, baseline để so sánh, metric rõ, serving stack đáng tin cậy và monitoring sau deploy.

Code NumPy tự viết trong bài không nên dùng cho production training. Nó phù hợp để học, debug và giải thích. Nếu muốn production training:

- Dùng PyTorch/TensorFlow/JAX hoặc framework tương đương.
- Dùng autograd thay vì tự viết gradient.
- Dùng data pipeline, checkpoint, experiment tracking và model registry.
- Dùng validation/test set, threshold tuning và model evaluation theo segment.
- Có CI/CD cho model artifact và rollback.

Trường hợp rất hẹp có thể dùng NumPy inference:

- Model nhỏ, frozen, không cần GPU.
- Latency và memory đã benchmark đạt SLA.
- Feature contract rất ổn định.
- Có monitoring, golden tests và rollback.
- Owner hiểu rõ giới hạn của implementation.

Nếu bạn đang build sản phẩm thật, best solution thường là dùng NumPy để học concept hôm nay, rồi chuyển sang PyTorch ở Day 10 cho implementation thực tế hơn.

## 16. Debugging checklist

Khi loss không giảm:

- Kiểm tra `X.shape`, `Y.shape`, `W1.shape`, `W2.shape`.
- Kiểm tra label có đúng shape `(batch_size, 1)` không.
- Kiểm tra learning rate có quá lớn hoặc quá nhỏ không.
- Log min/max của probability, xem model có saturate 0/1 không.
- Thử seed khác vì initialization có thể kẹt với model nhỏ.
- Thử `hidden_dim` lớn hơn.
- Thử activation khác.
- Kiểm tra gradient shape bằng assert.
- Kiểm tra loss có `nan` không.

Khi train đúng nhưng inference sai:

- Kiểm tra feature order.
- Kiểm tra dtype và preprocessing.
- Kiểm tra threshold.
- Kiểm tra model weights có load đúng version không.
- Kiểm tra train-serving skew.

## 17. Câu hỏi tự kiểm tra

1. Vì sao nhiều linear layer không activation vẫn chỉ tương đương một linear layer?
2. Sigmoid nên đặt ở hidden layer hay output layer trong bài toán binary classification? Vì sao?
3. Vì sao BCE cần clipping khi tự tính bằng NumPy?
4. Shape của `dW2` là gì và vì sao?
5. Learning rate quá cao thể hiện như thế nào trên loss curve?
6. Vì sao production training nên dùng framework autograd?
7. Khi nào một MLP nhỏ có thể thua Logistic Regression hoặc XGBoost trong tabular data?

## 18. Checklist hoàn thành

- [ ] Tôi giải thích được `Z = X @ W + b` và `A = activation(Z)`.
- [ ] Tôi viết đúng shape của `W1`, `b1`, `A1`, `W2`, `b2` và `P`.
- [ ] Tôi giải thích được vì sao activation tạo non-linearity.
- [ ] Tôi biết vì sao BCE cần clipping khi tự tính từ probability.
- [ ] Tôi suy ra được `dW2 = A1.T @ dZ2` và `dW1 = X.T @ dZ1`.
- [ ] Tôi chạy được XOR với `--assert-xor`.
- [ ] Tôi quan sát được loss giảm và giải thích được dấu hiệu learning rate quá lớn/quá nhỏ.
- [ ] Tôi nêu được trade-off NumPy tự viết so với framework autograd.
- [ ] Tôi trả lời được điều kiện để một neural network đi vào production.

## 19. Liên kết thực hành và tra cứu

- Bài tập: [exercise.md](./exercise.md)
- Script NumPy chạy được: [xor_mlp_numpy.py](./xor_mlp_numpy.py)
- Công thức, API và nguồn chính thức: [document.md](./document.md)
