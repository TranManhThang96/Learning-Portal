# Tài Liệu Chi Tiết: PyTorch Fundamentals

## 1. PyTorch Giải Quyết Gì Sau Day 9?

Ở Day 9, bạn tự viết MLP bằng NumPy:

```text
forward -> tính loss -> tự đạo hàm -> tự update W/b
```

Cách đó tốt để học, nhưng không phù hợp training deep learning thật vì dễ sai gradient, khó dùng GPU, khó mở rộng architecture và khó lưu/load artifact chuẩn.

PyTorch giữ lại mental model đó nhưng thay phần thủ công bằng các primitive production hơn:

| Day 9 với NumPy | Day 10 với PyTorch | Ý nghĩa |
|---|---|---|
| `np.ndarray` | `torch.Tensor` | Dữ liệu n chiều, có thể chạy CPU/GPU |
| Tự viết backprop | Autograd | Tự tính gradient từ computational graph |
| Tự quản lý `W1`, `b1`, `W2`, `b2` | `nn.Module` và `nn.Parameter` | Đóng gói weights thành model |
| Tự chia batch | `Dataset` và `DataLoader` | Data pipeline chuẩn |
| Tự update weight | `torch.optim` | Optimizer chuẩn như SGD, AdamW |
| Tự save mảng NumPy | `state_dict` | Artifact chuẩn của PyTorch |

Best solution trong bài này: viết training loop PyTorch thuần. Chưa dùng abstraction cao hơn vì Senior SE cần hiểu loop nền trước khi debug model thật.

## 2. Tensor, `dtype`, `shape`, `device`

`Tensor` là core data structure của PyTorch. Nó giống NumPy array ở chỗ biểu diễn dữ liệu n chiều, nhưng có thêm:

- `device`: tensor nằm trên CPU, CUDA GPU hoặc backend khác.
- `requires_grad`: có cần autograd track phép toán không.
- `.grad`: nơi gradient được accumulate sau `backward()`.
- Tích hợp với `torch.nn`, optimizer và GPU runtime.

Ví dụ inspect tensor:

```python
import torch

x = torch.tensor(
    [[0.0, 1.0], [1.0, 0.0]],
    dtype=torch.float32,
)

print("shape:", x.shape)   # torch.Size([2, 2])
print("dtype:", x.dtype)   # torch.float32
print("device:", x.device) # cpu
print("ndim:", x.ndim)
print("numel:", x.numel())
```

### Shape Là Contract

Với binary classifier MLP:

```text
X      shape = (batch_size, input_dim)
logits shape = (batch_size, 1)
y      shape = (batch_size, 1)
```

Nếu `logits` là `(32, 1)` nhưng label là `(32,)`, một số operation có thể broadcast âm thầm hoặc loss báo lỗi khó đọc. Trong code gần production, hãy validate shape ở boundary: khi tạo dataset, trước khi tính loss, hoặc trong test.

### Dtype Là Contract Tính Toán

Các dtype hay gặp:

| Dtype | Dùng khi | Lưu ý |
|---|---|---|
| `torch.float32` | Default cho training neural network | Cân bằng tốc độ, memory, độ chính xác |
| `torch.float64` | Numerical analysis cần chính xác cao | Chậm hơn, tốn RAM/VRAM hơn |
| `torch.int64` / `torch.long` | Class index cho `CrossEntropyLoss` | Không dùng cho `BCEWithLogitsLoss` target |
| `torch.bool` | Mask | Không dùng trực tiếp làm feature numeric |
| `torch.float16` / `bfloat16` | Mixed precision | Cần hiểu GPU support và stability |

Với `BCEWithLogitsLoss`, input là logits dạng float và target nên là float cùng shape, giá trị 0 hoặc 1.

### Device Là Runtime Placement

Model và tensor input phải nằm cùng device:

```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

x = x.to(device)
model = model.to(device)
```

Lỗi phổ biến:

```text
Expected all tensors to be on the same device, but found at least two devices...
```

Nguyên nhân thường là model đã `.to("cuda")` nhưng batch từ `DataLoader` vẫn ở CPU, hoặc checkpoint được load về CPU rồi trộn với tensor GPU.

Best practice:

- Chọn `device` một lần ở đầu program.
- Move model sang device ngay sau khi khởi tạo.
- Move từng batch sang device trong training/evaluation loop.
- Khi cần log hoặc convert sang NumPy, đưa tensor về CPU bằng `.detach().cpu()`.

## 3. Autograd

Autograd build computational graph trong lúc bạn chạy forward pass. Khi gọi `loss.backward()`, PyTorch tính gradient của loss theo các leaf tensor có `requires_grad=True`, thường là parameters của model.

Ví dụ nhỏ:

```python
import torch

w = torch.tensor([2.0], requires_grad=True)
x = torch.tensor([3.0])
y = w * x
loss = (y - 10.0) ** 2

loss.backward()

print(w.grad)  # dloss/dw
```

Điều quan trọng: gradient được accumulate. Nếu bạn không reset gradient, batch sau sẽ cộng dồn gradient với batch trước.

Training step chuẩn:

```python
optimizer.zero_grad(set_to_none=True)
logits = model(xb)
loss = loss_fn(logits, yb)
loss.backward()
optimizer.step()
```

Vì sao `set_to_none=True`?

- Giảm một số thao tác ghi zero vào memory.
- Có thể tiết kiệm memory và nhanh hơn trong nhiều workload.
- Giúp phát hiện parameter nào không nhận gradient vì `.grad` vẫn là `None`.

Trade-off: nếu code cũ giả định `.grad` luôn là tensor zero, cần sửa logic đó.

### Khi Không Cần Gradient

Evaluation và inference không cần lưu graph:

```python
model.eval()
with torch.inference_mode():
    logits = model(xb)
    probs = torch.sigmoid(logits)
```

`torch.no_grad()` và `torch.inference_mode()` đều tắt gradient tracking. `inference_mode()` tối ưu mạnh hơn cho inference thuần, nhưng ít linh hoạt hơn nếu bạn còn cần tensor tham gia autograd sau đó. Trong bài này, evaluation/predict dùng `inference_mode()`. Khi viết code debug cần linh hoạt, `no_grad()` vẫn là lựa chọn an toàn.

`model.eval()` không thay thế `no_grad()` hoặc `inference_mode()`. `eval()` đổi behavior của layer như Dropout/BatchNorm; gradient mode kiểm soát autograd memory.

## 4. `nn.Module` Và `forward()`

`nn.Module` là base class cho model/layer. Subclass thường có:

- `__init__`: khai báo layer, parameter, buffer.
- `forward`: mô tả computation từ input sang output.
- `state_dict`: dictionary chứa parameters và buffers.

Ví dụ:

```python
from torch import nn


class XORMLP(nn.Module):
    def __init__(self, hidden_dim: int = 8) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(2, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x):
        if x.ndim != 2 or x.shape[1] != 2:
            raise ValueError(f"Expected input shape (batch, 2), got {tuple(x.shape)}")
        return self.net(x)
```

Gọi model bằng `model(x)`, không gọi trực tiếp `model.forward(x)` trong training code. `model(x)` đi qua hook và cơ chế nội bộ của `nn.Module`.

### `model.train()` Và `model.eval()`

```python
model.train()  # training mode
model.eval()   # evaluation mode
```

Với MLP XOR không có Dropout/BatchNorm, output có thể giống nhau giữa train/eval. Nhưng trong model thật, quên `eval()` có thể làm metric và inference sai.

Production rule:

- Training loop: gọi `model.train()` đầu epoch.
- Validation/test/inference: gọi `model.eval()` và tắt gradient.
- Sau khi load checkpoint để serve: gọi `model.eval()`.

## 5. `Dataset` Và `DataLoader`

`Dataset` mô tả cách lấy một sample. `DataLoader` biến dataset thành iterable mini-batch.

```python
from torch.utils.data import Dataset, DataLoader


class XORDataset(Dataset):
    def __init__(self):
        self.features = ...
        self.labels = ...

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]


loader = DataLoader(
    XORDataset(),
    batch_size=32,
    shuffle=True,
    num_workers=0,
)
```

Các option quan trọng:

| Option | Ý nghĩa | Trade-off |
|---|---|---|
| `batch_size` | Số sample mỗi batch | Lớn hơn thường tăng throughput nhưng tốn memory |
| `shuffle` | Xáo trộn mỗi epoch | Nên bật cho train, tắt cho validation/test |
| `num_workers` | Số process load data | Tăng throughput nhưng phức tạp debug hơn |
| `pin_memory` | Copy tensor vào pinned memory cho CUDA | Có ích khi dùng GPU, không cần cho CPU |
| `drop_last` | Bỏ batch cuối nếu thiếu sample | Hữu ích cho BatchNorm/distributed training |
| `collate_fn` | Cách ghép sample thành batch | Cần cho sequence dài ngắn khác nhau |

Best practice:

- Dataset không nên tự move tensor sang GPU. Để training loop quyết định device.
- Dataset nên trả về tensor có shape/dtype ổn định.
- `shuffle=True` chỉ dùng cho training set.
- Với dữ liệu lớn, tách preprocessing offline hoặc cache để `DataLoader` không thành bottleneck.

## 6. CPU/GPU Device Management

Pattern cơ bản:

```python
def select_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


device = select_device()
model = XORMLP().to(device)

for xb, yb in loader:
    xb = xb.to(device)
    yb = yb.to(device)
```

GPU không tự động nhanh hơn trong mọi trường hợp. Nếu model rất nhỏ hoặc batch rất nhỏ, cost copy CPU -> GPU có thể lớn hơn lợi ích compute.

Production considerations:

- Log device đang dùng ở startup.
- Có fallback khi CUDA không available.
- Tránh `.to(device)` từng sample; move theo batch.
- Tránh gọi `.item()` quá nhiều trong GPU loop vì có thể ép đồng bộ CPU/GPU.
- Theo dõi VRAM, GPU utilization, dataloader wait time.

## 7. Training Loop Tối Thiểu Nhưng Đúng

Skeleton cho binary classification:

```python
from torch import nn

loss_fn = nn.BCEWithLogitsLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-2, weight_decay=1e-4)

model.train()
for xb, yb in train_loader:
    xb = xb.to(device)
    yb = yb.to(device)

    optimizer.zero_grad(set_to_none=True)
    logits = model(xb)
    loss = loss_fn(logits, yb)
    loss.backward()
    optimizer.step()
```

Tại sao không đặt `Sigmoid` trong model khi dùng `BCEWithLogitsLoss`?

- `BCEWithLogitsLoss` nhận raw logits.
- Nó kết hợp sigmoid và binary cross entropy theo cách ổn định số học hơn.
- Khi cần probability để metric/inference, dùng `torch.sigmoid(logits)` sau model.

## 8. Save/Load Bằng `state_dict`

Không nên serialize cả object model nếu không cần. Cách chuẩn là lưu `state_dict` kèm config.

```python
checkpoint = {
    "model_state_dict": model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "config": {
        "input_dim": 2,
        "hidden_dim": 8,
        "output_dim": 1,
    },
    "metrics": {"val_accuracy": 1.0},
}
torch.save(checkpoint, "artifacts/xor_mlp.pt")
```

Load:

```python
checkpoint = torch.load("artifacts/xor_mlp.pt", map_location=device)
model = XORMLP(hidden_dim=checkpoint["config"]["hidden_dim"]).to(device)
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()
```

Production note:

- Chỉ load checkpoint từ nguồn tin cậy.
- Version config, preprocessing và code model cùng artifact.
- Với PyTorch mới, cân nhắc `weights_only=True` khi phù hợp để giảm rủi ro untrusted pickle.

## 9. NumPy Vs PyTorch

| Tiêu chí | NumPy | PyTorch |
|---|---|---|
| Core data | `ndarray` | `Tensor` |
| Autograd | Không có native autograd | Có autograd |
| GPU | Không phải default workflow | First-class CUDA support |
| Neural network layers | Tự viết hoặc dùng lib khác | `torch.nn` |
| Optimizer | Tự viết | `torch.optim` |
| Data pipeline | Tự viết batching | `Dataset`/`DataLoader` |
| Production DL | Không phải lựa chọn chính | Rất phổ biến |
| Học math | Rất tốt | Tốt nhưng che bớt chi tiết gradient |

Best solution:

- Dùng NumPy để học linear algebra, loss, manual gradient.
- Dùng PyTorch khi training neural network thật, cần GPU, checkpoint, ecosystem và khả năng mở rộng.

## 10. Performance Và Trade-Off

| Quyết định | Lợi ích | Chi phí/rủi ro | Gợi ý |
|---|---|---|---|
| CPU | Dễ chạy, ít phụ thuộc | Chậm với model lớn | Tốt cho dev, test, inference nhỏ |
| GPU | Throughput cao cho matrix compute | VRAM, setup, transfer cost | Dùng khi batch/model đủ lớn |
| Batch lớn | Tận dụng vectorization | Tốn memory, có thể ảnh hưởng generalization | Tăng dần đến khi gần giới hạn memory |
| `num_workers > 0` | Load data song song | Debug khó hơn, overhead process | Bắt đầu `0`, tăng khi data loading nghẽn |
| `float32` | Default ổn định | Tốn hơn mixed precision | Dùng trước khi tối ưu |
| Mixed precision | Nhanh hơn, ít VRAM hơn | Có rủi ro numerical issue | Để Day sau khi loop đã đúng |
| `inference_mode()` | Ít overhead hơn inference | Ít linh hoạt hơn `no_grad()` | Dùng cho inference thuần |

Performance rule: đo trước khi tối ưu. Với model nhỏ như XOR, GPU có thể chậm hơn CPU vì overhead dominate.

## 11. Lỗi Phổ Biến

- Quên `optimizer.zero_grad(...)`, làm gradient cộng dồn sai.
- Dùng `Sigmoid` trong model rồi lại dùng `BCEWithLogitsLoss`.
- Label dtype là `torch.long` trong bài toán BCE thay vì float.
- Label shape `(batch,)` nhưng logits shape `(batch, 1)`.
- Model ở GPU nhưng batch ở CPU.
- Quên `model.eval()` khi validation/inference.
- Quên `torch.no_grad()` hoặc `torch.inference_mode()` khi inference, làm tốn memory.
- Save cả object model thay vì `state_dict`, làm artifact phụ thuộc code path nhiều hơn.
- Convert tensor GPU trực tiếp sang NumPy thay vì `.detach().cpu().numpy()`.

## 12. Kết Luận Production

PyTorch fundamentals trong bài này dùng được làm nền production. Code demo có thể chạy local và làm template nhỏ, nhưng chưa đủ production nếu thiếu config management, test, logging, checkpoint policy, data validation, model registry, serving layer và monitoring.

Câu trả lời ngắn: dùng được trong production nếu bạn quản lý đầy đủ artifact, reproducibility, input contract, runtime mode, device fallback, performance benchmark và observability. Không nên copy nguyên training script demo vào production service mà không bổ sung các lớp kiểm soát đó.
