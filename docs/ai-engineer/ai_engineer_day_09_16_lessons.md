# 8 Bai Hoc Tiep Theo Cho AI Engineer

Nguon: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, Phase 2 - Deep Learning, NLP, Transformer.

Doi tuong: Senior Software Engineer muon chuyen sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus.

Khung hoc moi ngay: 2 gio.

## Muc Luc

| Ngay | Chu de | Output chinh |
|---:|---|---|
| Day 9 | Neural Network Tu Zero | MLP 2-layer bang NumPy train tren XOR |
| Day 10 | PyTorch Fundamentals | Rebuild MLP XOR bang PyTorch |
| Day 11 | Training Loop, Optimizer, Scheduler | Training loop co validation, scheduler, early stopping |
| Day 12 | NLP Fundamentals & Tokenizer | So sanh tokenizer BERT, GPT-style va PhoBERT |
| Day 13 | Attention Mechanism | Implement scaled dot-product attention va visualize attention |
| Day 14 | Transformer Architecture | Tiny Transformer encoder classifier |
| Day 15 | HuggingFace Ecosystem | Load model/tokenizer, inspect model card, run inference |
| Day 16 | Mini-project - Fine-tune PhoBERT/BERT Classifier | Baseline TF-IDF, fine-tune Transformer, FastAPI inference |

---

# Day 9: Neural Network Tu Zero

## Muc Tieu

- Hieu neuron, weight, bias, activation, forward pass, loss va backpropagation.
- Implement MLP 2-layer bang NumPy, khong dung framework deep learning.
- Train model tren XOR dataset va visualize loss giam theo epoch.
- Map neural network concepts ve config, build artifact, runtime API va observability.
- Biet diem nao chi nen dung de hoc, diem nao co the dua vao production.

## TL;DR

Neural network la mot function nhieu layer, moi layer bien doi input bang matrix multiplication, bias va activation. Training la feedback loop lap lai: forward, tinh loss, backprop gradient, update weights. Backpropagation giup tinh gradient cua tung weight, con optimizer dung gradient de giam loss. Trong production, ban hiem khi tu viet backprop bang NumPy, nhung hieu no giup debug shape, loss, learning rate, overfitting va latency.

## 1. Neuron = Weighted Sum + Activation

Mot neuron don gian:

```text
z = w1*x1 + w2*x2 + ... + wn*xn + b
a = activation(z)
```

Map sang Senior SE:

| Neural Network | SE analogy |
|---|---|
| Weight | Config hoc tu data |
| Bias | Default offset |
| Activation | Ham phi tuyen / policy transform |
| Layer | Processing stage |
| Forward pass | Runtime request flow |
| Model weights | Build artifact |
| Training | Build process co feedback |

Khac rule-based system: weights khong duoc viet tay. Chung duoc hoc tu data thong qua training.

## 2. Activation Functions

Neu khong co activation, nhieu linear layers gop lai van chi la mot linear function. Activation giup network hoc quan he phi tuyen.

| Activation | Manh | Yeu | Khi dung |
|---|---|---|---|
| Sigmoid | Output 0-1, hop binary probability | De vanishing gradient | Output binary |
| Tanh | Center quanh 0 | Vanishing gradient khi value lon | Toy model, RNN cu |
| ReLU | Nhanh, gradient tot | Dead neuron | Default hidden layer |
| GELU | Muot, tot cho Transformer | Dat hon ReLU | BERT/GPT-style model |

Guidance: hidden layer thuong dung ReLU/GELU; output binary dung sigmoid hoac logits + BCE loss.

## 3. Forward Pass Va Shape Contract

Voi batch input:

```text
X shape  = (batch_size, input_dim)
W1 shape = (input_dim, hidden_dim)
b1 shape = (hidden_dim,)
H shape  = (batch_size, hidden_dim)
W2 shape = (hidden_dim, output_dim)
Y shape  = (batch_size, output_dim)
```

Shape trong deep learning giong schema trong API/database. Sai shape la bug pho bien nhat khi moi hoc NumPy/PyTorch.

## 4. Loss Function

Loss do model sai bao nhieu. Vi du binary classification:

```text
BCE = - y*log(p) - (1-y)*log(1-p)
```

Map ve production:

- Loss la objective ky thuat.
- Metric la acceptance criteria.
- Business KPI la ket qua cuoi.

Khong nen toi uu loss ma bo qua metric business. Fraud co the can recall cao; spam filter co the can precision cao.

## 5. Backpropagation Va Gradient Descent

Training loop:

```text
forward -> loss -> backward -> update weights
```

Gradient cho biet neu tang/giam weight thi loss thay doi the nao. Gradient descent update:

```text
weight = weight - learning_rate * gradient
```

Learning rate:

- Qua lon: loss dao dong hoac diverge.
- Qua nho: train rat cham.
- Hop ly: loss giam on dinh.

## Trade-offs

| Lua chon | Nen dung khi | Khong nen dung khi | Production note |
|---|---|---|---|
| NumPy tu implement | Hoc concept, debug math | Production training | De sai gradient, khong GPU-friendly |
| PyTorch/TensorFlow | Training that, GPU, autograd | Task classical ML don gian | Default cho DL |
| ReLU | Hidden layer pho bien | Output probability | Nhanh, sparse activation |
| Sigmoid | Binary output | Hidden layer sau nhieu tang | De gradient nho |
| Full batch | Dataset nho | Dataset lon | On dinh nhung ton RAM |
| Mini-batch | Dataset vua/lon | Batch qua nho gay noisy | Default training |
| Model nho | Latency/cost chat | Underfit ro | De deploy hon |
| Model lon | Data lon, pattern phuc tap | Data it, latency chat | Can regularization |

## Best Practices Tu Industry

1. Bat dau bang baseline truoc neural network.
2. Luon log loss curve, metric curve va learning rate.
3. Debug shape o moi layer khi model moi.
4. Tach preprocessing khoi model nhung version chung artifact/config.
5. Dung framework co autograd cho training that; NumPy chi de hoc va verify.

## Performance Considerations

- Matrix multiplication la core workload; vectorized NumPy nhanh hon Python loop rat nhieu.
- Memory cho activation tang theo `batch_size * hidden_dim * dtype_size`.
- `float32` la default hop ly; `float64` ton RAM gap doi va cham hon.
- Batch size lon tang throughput nhung co the tang memory va latency.
- Inference MLP nho tren CPU co the sub-ms den vai ms; model lon can benchmark p95/p99.

## Production Concerns

- Khong deploy hand-written NumPy backprop cho training production.
- Can save architecture, weights, preprocessing config, feature order va metric.
- Train-serving skew: input scaling/encoding luc inference phai giong training.
- Monitor prediction distribution, latency, error rate, drift va data quality.
- Reproducibility can seed, dataset version, package version.
- Rollback can gom model weights, threshold va preprocessing version.

Dung duoc trong production khong? Concept thi co, code NumPy ben duoi thi chi dung de hoc. Production nen dung PyTorch, co test, checkpoint, monitoring va deployment pipeline.

## Ung Dung Thuc Te

- Text classifier: MLP tren TF-IDF/embedding de classify ticket, intent, sentiment.
- Fraud/churn: MLP co the hoc nonlinear pattern, nhung can so sanh voi XGBoost.
- Ranking/recommendation: neural network hoc user/item representation va scoring function.

## Hands-on Trong 60-90 Phut

Chay MLP 2-layer bang NumPy tren XOR.

```bash
pip install numpy matplotlib
```

```python
import numpy as np

RANDOM_STATE = 42


def sigmoid(x):
    x = np.clip(x, -50, 50)
    return 1.0 / (1.0 + np.exp(-x))


def binary_cross_entropy(y_true, y_pred):
    eps = 1e-7
    y_pred = np.clip(y_pred, eps, 1.0 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1.0 - y_true) * np.log(1.0 - y_pred))


class NumpyMLP:
    def __init__(self, input_dim=2, hidden_dim=4, output_dim=1, learning_rate=0.5, seed=42):
        rng = np.random.default_rng(seed)
        self.learning_rate = learning_rate
        self.W1 = rng.normal(0, 0.8, size=(input_dim, hidden_dim))
        self.b1 = np.zeros((1, hidden_dim))
        self.W2 = rng.normal(0, 0.8, size=(hidden_dim, output_dim))
        self.b2 = np.zeros((1, output_dim))

    def forward(self, X):
        z1 = X @ self.W1 + self.b1
        a1 = np.tanh(z1)
        z2 = a1 @ self.W2 + self.b2
        y_hat = sigmoid(z2)
        return y_hat, {"X": X, "a1": a1, "y_hat": y_hat}

    def train_step(self, X, y):
        m = X.shape[0]
        y_hat, cache = self.forward(X)
        loss = binary_cross_entropy(y, y_hat)

        dz2 = (y_hat - y) / m
        dW2 = cache["a1"].T @ dz2
        db2 = np.sum(dz2, axis=0, keepdims=True)

        da1 = dz2 @ self.W2.T
        dz1 = da1 * (1.0 - cache["a1"] ** 2)
        dW1 = X.T @ dz1
        db1 = np.sum(dz1, axis=0, keepdims=True)

        self.W2 -= self.learning_rate * dW2
        self.b2 -= self.learning_rate * db2
        self.W1 -= self.learning_rate * dW1
        self.b1 -= self.learning_rate * db1
        return loss

    def predict_proba(self, X):
        y_hat, _ = self.forward(X)
        return y_hat

    def predict(self, X, threshold=0.5):
        return (self.predict_proba(X) >= threshold).astype(int)


X = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
y = np.array([[0.0], [1.0], [1.0], [0.0]])

model = NumpyMLP(learning_rate=0.5, seed=RANDOM_STATE)
loss_history = []

for epoch in range(1, 8001):
    loss = model.train_step(X, y)
    loss_history.append(loss)
    if epoch % 1000 == 0:
        print(f"epoch={epoch} loss={loss:.6f}")

print("Probabilities:")
print(np.round(model.predict_proba(X), 4))
print("Predictions:")
print(model.predict(X))
print("Expected:")
print(y.astype(int))

try:
    import matplotlib.pyplot as plt

    plt.plot(loss_history)
    plt.title("XOR MLP loss")
    plt.xlabel("epoch")
    plt.ylabel("binary cross entropy")
    plt.show()
except Exception:
    print("matplotlib not available, final loss:", loss_history[-1])
```

Bai tap:

- Doi `hidden_dim` thanh 2, 4, 8 va so sanh loss.
- Doi `learning_rate` thanh 0.01, 0.1, 1.0 va quan sat.
- Thay `tanh` bang ReLU va implement gradient cua ReLU.
- Them noise vao input va xem model co con predict dung khong.

## Tu Kiem Tra

1. Vi sao nhieu linear layers khong activation van tuong duong mot linear layer?
2. Learning rate qua cao gay dau hieu gi tren loss curve?
3. Backpropagation tinh cai gi?
4. Shape `(batch_size, input_dim)` giup debug loi nao?
5. Vi sao NumPy implementation khong nen dung cho production training?

## Checklist

- [ ] Giai thich duoc neuron, weight, bias, activation.
- [ ] Hieu forward pass va shape cua tung layer.
- [ ] Hieu loss va gradient descent o muc truc giac.
- [ ] Implement MLP 2-layer bang NumPy.
- [ ] Train duoc XOR va loss giam.
- [ ] Ghi lai trade-off giua model nho/lon, learning rate, activation.
- [ ] Biet production nen dung framework autograd.

## Tai Lieu Tham Khao

- 3Blue1Brown: Neural Networks.
- Michael Nielsen: Neural Networks and Deep Learning.
- CS231n: Backpropagation notes.
- DeepLearning.AI: Neural Networks basics.
- Keywords: `backpropagation`, `binary cross entropy`, `activation function`, `gradient descent`.

---


# Day 10: PyTorch Fundamentals

## Muc Tieu

- Dung duoc PyTorch Tensor, dtype, shape va device.
- Hieu autograd va flow `forward -> loss -> backward -> optimizer.step`.
- Viet model bang `nn.Module` va `forward()`.
- Tao `Dataset` va `DataLoader` cho mini-batch training.
- Rebuild MLP XOR tu Day 9 bang PyTorch va so sanh voi NumPy.

## TL;DR

PyTorch giup ban khong phai tu viet backprop. Tensor trong PyTorch giong NumPy ndarray nhung co autograd va chay duoc tren GPU. `nn.Module` dong goi architecture, `Dataset/DataLoader` dong goi input pipeline, optimizer cap nhat weights. Voi Senior SE, PyTorch training loop nen duoc xem nhu mot batch job co config, metric, artifact, logging va rollback.

## 1. Tensor, dtype, shape, device

Tensor la core data structure:

```python
import torch
x = torch.tensor([[0.0, 1.0]], dtype=torch.float32)
print(x.shape, x.dtype, x.device)
```

Map sang SE:

| PyTorch concept | SE analogy |
|---|---|
| Tensor shape | API schema |
| dtype | Storage/serialization format |
| device CPU/GPU | Runtime placement |
| batch dimension | Batch processing |
| tensor operation | Vectorized compute |

Loi pho bien: model tren GPU nhung input tren CPU, hoac label dtype sai voi loss function.

## 2. Autograd

Autograd tu dong build computational graph khi tensor co `requires_grad=True`.

```text
logits = model(x)
loss = loss_fn(logits, y)
loss.backward()
optimizer.step()
optimizer.zero_grad()
```

Gradient duoc accumulate. Neu quen `zero_grad`, gradient se cong don qua batch va training sai.

## 3. nn.Module Va forward()

`nn.Module` la cach dong goi model:

```python
class MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(...)

    def forward(self, x):
        return self.layers(x)
```

Map:

- `__init__`: khai bao dependency/layer.
- `forward`: request path.
- `state_dict`: deployable weights.
- `train()` va `eval()`: runtime mode.

`train()` bat dropout/batchnorm training behavior. `eval()` tat dropout va dung running stats cua batchnorm.

## 4. Dataset Va DataLoader

`Dataset` tra ve mot sample. `DataLoader` tao batch, shuffle, parallel loading.

| PyTorch | Data system analogy |
|---|---|
| Dataset | Data access layer |
| DataLoader | Batch reader/queue |
| batch_size | Micro-batch size |
| shuffle | Randomized training order |
| num_workers | Parallel data loading workers |

Production training bi nghen co the do data loading, khong phai model compute.

## 5. CPU/GPU Device Management

Pattern co ban:

```python
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
xb = xb.to(device)
yb = yb.to(device)
```

CPU du cho toy model va inference nho. GPU can cho training lon, nhung khong tu dong nhanh hon neu batch qua nho.

## Trade-offs

| Lua chon | Nen dung khi | Khong nen dung khi | Production note |
|---|---|---|---|
| NumPy | Hoc math, simple numerical task | Training DL that | Khong autograd/GPU native |
| PyTorch | DL training/inference | Classical ML tabular don gian | Default trong Phase 2+ |
| CPU | Model nho, dev local | Training lon | Don gian, re |
| GPU | Matrix compute lon, batch inference | Batch nho, model nho | Monitor VRAM/utilization |
| Manual loop | Can control cao | Team can abstraction cao | Tot de hoc va custom |
| Trainer framework | Fine-tune standard model | Debug custom behavior | Dung sau khi hieu loop |

## Best Practices Tu Industry

1. Set seed cho demo/experiment co the lap lai.
2. Tach `train_one_epoch`, `evaluate`, `predict`.
3. Dung `BCEWithLogitsLoss` thay vi sigmoid + BCE rieng de on dinh so hoc.
4. Chuyen model sang `eval()` va dung `torch.no_grad()` khi inference.
5. Save `state_dict` kem config architecture, preprocessing va metric.

## Performance Considerations

- Dung mini-batch de tan dung vectorized compute.
- `torch.no_grad()` giam memory khi inference vi khong luu graph.
- Device transfer CPU <-> GPU co cost; tranh copy tung sample.
- Batch size lon tang throughput nhung tang VRAM.
- `num_workers > 0` co ich voi image/text loading nang; tren Windows/dev nho co the dung 0.

## Production Concerns

- Reproducibility: seed, package version, dataset snapshot, config.
- Serialization: uu tien `state_dict`, khong load artifact tu nguon khong tin cay.
- Input validation: shape, dtype, range, missing value.
- Monitoring: latency, error rate, prediction distribution, drift.
- Rollback: model version, threshold, preprocessing version.
- Reliability: handle device unavailable, OOM, timeout.

Dung duoc production khong? PyTorch co the dung production, nhung code demo ben duoi la training local. Production can checkpointing, config file, tests, model registry, serving layer va monitoring.

## Ung Dung Thuc Te

- Fine-tune BERT/PhoBERT classifier trong Day 16.
- Train neural classifier cho ticket routing, intent detection, sentiment.
- Export embedding/reranker model de dung trong RAG pipeline.

## Hands-on Trong 60-90 Phut

Rebuild MLP XOR bang PyTorch.

```bash
pip install torch
```

```python
from __future__ import annotations

import random
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

RANDOM_STATE = 42


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class XORDataset(Dataset):
    def __init__(self, repeats: int = 256, noise_std: float = 0.02):
        base_x = torch.tensor([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]], dtype=torch.float32)
        base_y = torch.tensor([[0.0], [1.0], [1.0], [0.0]], dtype=torch.float32)
        self.X = base_x.repeat((repeats, 1))
        self.y = base_y.repeat((repeats, 1))
        if noise_std > 0:
            self.X = torch.clamp(self.X + torch.randn_like(self.X) * noise_std, 0.0, 1.0)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class XORMLP(nn.Module):
    def __init__(self, hidden_dim: int = 8):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(2, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 1))

    def forward(self, x):
        return self.net(x)


def train_one_epoch(model, loader, loss_fn, optimizer, device):
    model.train()
    total_loss = 0.0
    total_rows = 0
    for xb, yb in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(xb)
        loss = loss_fn(logits, yb)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * len(xb)
        total_rows += len(xb)
    return total_loss / total_rows


@torch.no_grad()
def evaluate_clean_xor(model, device):
    model.eval()
    X = torch.tensor([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]], dtype=torch.float32, device=device)
    y = torch.tensor([[0.0], [1.0], [1.0], [0.0]], dtype=torch.float32, device=device)
    probs = torch.sigmoid(model(X))
    preds = (probs >= 0.5).float()
    accuracy = (preds == y).float().mean().item()
    return probs.cpu(), preds.cpu(), accuracy


def main():
    set_seed(RANDOM_STATE)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("device:", device)

    loader = DataLoader(XORDataset(), batch_size=32, shuffle=True, num_workers=0)
    model = XORMLP(hidden_dim=8).to(device)
    loss_fn = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.03, weight_decay=1e-4)

    for epoch in range(1, 201):
        loss = train_one_epoch(model, loader, loss_fn, optimizer, device)
        if epoch % 20 == 0 or epoch == 1:
            _, _, accuracy = evaluate_clean_xor(model, device)
            print(f"epoch={epoch:03d} loss={loss:.6f} clean_accuracy={accuracy:.2f}")

    probs, preds, accuracy = evaluate_clean_xor(model, device)
    print("Probabilities:")
    print(torch.round(probs * 10000) / 10000)
    print("Predictions:")
    print(preds.int())
    print("Accuracy:", accuracy)


if __name__ == "__main__":
    main()
```

## Tu Kiem Tra

1. `Tensor` khac NumPy array o diem nao?
2. Vi sao phai goi `optimizer.zero_grad()` moi batch?
3. `model.train()` va `model.eval()` khac nhau the nao?
4. Khi nao nen dung `torch.no_grad()`?
5. Device mismatch CPU/GPU thuong xay ra o dau?

## Checklist

- [ ] Tao duoc tensor va kiem tra shape/dtype/device.
- [ ] Hieu autograd va `loss.backward()`.
- [ ] Viet duoc `nn.Module` co `forward()`.
- [ ] Tao custom `Dataset` va `DataLoader`.
- [ ] Train MLP XOR bang PyTorch.
- [ ] Dung `eval()` va `torch.no_grad()` khi inference.
- [ ] So sanh duoc NumPy implementation voi PyTorch implementation.

## Tai Lieu Tham Khao

- PyTorch Tutorials: Tensors, Autograd, `nn.Module`.
- PyTorch Documentation: `Dataset`, `DataLoader`, `BCEWithLogitsLoss`, `AdamW`.
- Keywords: `pytorch training loop`, `torch no_grad`, `state_dict`, `device cuda cpu`.

---


# Day 11: Training Loop, Optimizer, Scheduler

## Muc Tieu

- Hieu anatomy cua training loop trong PyTorch.
- Phan biet vai tro cua optimizer, learning rate, weight decay va scheduler.
- Biet dung dropout, gradient clipping, early stopping de giam overfitting/unstable training.
- Log duoc loss, metric, learning rate va checkpoint tot nhat.
- Map training workflow ve reproducibility, monitoring, rollback va cost.

## TL;DR

Training loop la runtime engine cua deep learning: data batch di qua model, tinh loss, backprop gradient, optimizer update weights. Optimizer giong policy de update state; scheduler giong config tu dong dieu chinh learning rate theo thoi gian. Production training khong chi la `loss.backward()`, ma can logging, validation, checkpoint, early stopping, reproducibility va resource control.

## 1. Training Loop Anatomy

```text
for epoch:
  for batch:
    optimizer.zero_grad()
    prediction = model(input)
    loss = loss_fn(prediction, label)
    loss.backward()
    optimizer.step()
```

Map ve Senior SE:

| ML concept | SE analogy |
|---|---|
| Epoch | Mot lan batch job quet qua toan bo dataset |
| Batch | Page/chunk trong data processing |
| Forward pass | Request di qua business logic |
| Loss | Error signal / objective function |
| Backward pass | Root-cause signal ve tung layer |
| Optimizer step | State update co policy |
| Validation loop | Staging acceptance test |
| Checkpoint | Artifact co the rollback |

Chi tiet quan trong:

- `model.train()`: bat dropout/batchnorm training behavior.
- `model.eval()`: tat dropout, dung eval behavior.
- `torch.no_grad()`: validation/inference khong build computation graph.
- `optimizer.zero_grad(set_to_none=True)`: clear gradient cu.
- `loss.backward()`: tinh gradient.
- `optimizer.step()`: update weights.

## 2. Optimizer

| Optimizer | Khi nen dung | Han che |
|---|---|---|
| SGD | Baseline ro, training on dinh | Can tuning LR/momentum ky |
| SGD + momentum | Vision/classic DL | Cham hon Adam luc dau |
| Adam | Prototype nhanh | Weight decay implementation co the khong toi uu |
| AdamW | Transformer/NLP default | Nhieu hyperparameter hon |
| RMSprop | RNN/old workflow | It dung hon AdamW hien nay |

Guidance:

- NLP/Transformer/fine-tuning: bat dau voi `AdamW`.
- Small MLP/classifier: `AdamW` hoac `SGD + momentum`.
- Loss dao dong manh: giam learning rate, tang batch size, gradient clipping.
- Train loss giam nhung val loss tang: regularization/early stopping truoc khi doi optimizer.

## 3. Learning Rate Va Scheduler

```text
LR qua cao -> loss no/dao dong
LR qua thap -> train rat cham
LR hop ly -> loss giam deu
```

| Scheduler | Khi nen dung | Production note |
|---|---|---|
| StepLR | Simple baseline | De explain |
| ReduceLROnPlateau | Giam LR khi val loss dung lai | Tot cho project vua |
| CosineAnnealingLR | Training dai | Smooth decay |
| OneCycleLR | Muon train nhanh | Can biet total steps |
| Warmup + decay | Transformer/fine-tuning | Rat nen dung voi pretrained model |

## 4. Regularization Va Stability

- Dropout: random tat mot phan neuron trong training, giam overfitting.
- Weight decay: phat weight qua lon.
- Gradient clipping: gioi han norm cua gradient, huu ich khi gradient explosion.
- Early stopping: dung training khi validation loss khong cai thien.
- Mixed precision: FP16/BF16 giam memory va tang throughput tren GPU, nhung debug kho hon.

## Trade-offs

| Quyet dinh | Khi chon | Trade-off |
|---|---|---|
| Batch size lon | GPU con memory, can throughput | Co the generalization kem, can LR tuning |
| Batch size nho | Memory han che, dataset nho | Gradient noisy, training cham |
| AdamW | Fine-tune/NLP/default nhanh | Co the generalization kem SGD trong vai case |
| SGD momentum | Can control/generalization | Cham, tuning kho |
| LR cao | Muon converge nhanh | De unstable |
| LR thap | Fine-tune an toan | Train lau, underfit |
| Dropout cao | Overfit manh | Underfit neu qua cao |
| Early stopping | Tiet kiem compute | Can validation set dang tin |
| Mixed precision | GPU training lon | Debug phuc tap hon FP32 |

## Best Practices Tu Industry

1. Log train loss, val loss, metric, LR va epoch time.
2. Save checkpoint theo validation metric, khong theo epoch cuoi.
3. Set seed va luu config training kem artifact.
4. Tach train loop va eval loop ro rang.
5. Bat dau bang loop don gian dung truoc, sau do moi them AMP/scheduler/accumulation.

## Performance Considerations

- Batch size anh huong truc tiep GPU utilization va memory.
- Validation nen dung `model.eval()` va `torch.no_grad()`.
- `num_workers` cua DataLoader co the tang throughput neu data loading cham.
- AMP tren GPU co the giam memory dang ke, nhung can benchmark voi workload that.
- Gradient accumulation giup gia lap batch lon khi VRAM thap, doi lai wall-clock time lau hon.
- Checkpoint qua thuong xuyen co the ton IO.

## Production Concerns

- Reproducibility: seed, package version, dataset snapshot, git commit, config.
- Artifact: model weights, tokenizer/preprocessor, label mapping, threshold, metrics.
- Rollback: giu checkpoint tot nhat va config tuong ung.
- Monitoring training: loss spike, NaN, gradient norm, GPU memory, epoch time.
- Data quality: label noise, class imbalance, train/val leakage.
- Security: khong log raw PII trong sample batch/debug output.
- Cost: GPU hour, retry failed job, checkpoint storage.

## Ung Dung Thuc Te

- Fine-tune sentiment classifier tieng Viet cho Day 16.
- Train text classifier noi bo: ticket routing, spam detection, intent classification.
- Build training script co the dua vao CI/CD hoac scheduled retraining.

## Hands-on Trong 60-90 Phut

```bash
pip install torch
```

```python
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, random_split

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)


@dataclass
class Config:
    n_samples: int = 12000
    batch_size: int = 256
    epochs: int = 50
    lr: float = 3e-3
    weight_decay: float = 1e-2
    dropout: float = 0.20
    grad_clip_norm: float = 1.0
    early_stopping_patience: int = 5
    checkpoint_path: str = "day11_best_model.pt"


class MLPClassifier(nn.Module):
    def __init__(self, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(2, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def build_dataset(n_samples: int) -> TensorDataset:
    half = n_samples // 2
    x0 = torch.randn(half, 2) * 0.9 + torch.tensor([-1.2, -1.2])
    x1 = torch.randn(n_samples - half, 2) * 0.9 + torch.tensor([1.2, 1.2])
    x = torch.cat([x0, x1], dim=0)
    y = torch.cat([torch.zeros(half), torch.ones(n_samples - half)], dim=0)
    perm = torch.randperm(n_samples)
    return TensorDataset(x[perm].float(), y[perm].float())


def binary_metrics(logits: torch.Tensor, y_true: torch.Tensor) -> dict:
    pred = (torch.sigmoid(logits) >= 0.5).int()
    y = y_true.int()
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


def run_epoch(model, loader, loss_fn, optimizer, device, train: bool, grad_clip_norm: float):
    model.train(mode=train)
    total_loss = 0.0
    all_logits = []
    all_labels = []
    for xb, yb in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        if train:
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)
            optimizer.step()
        else:
            with torch.no_grad():
                logits = model(xb)
                loss = loss_fn(logits, yb)
        total_loss += float(loss.item()) * xb.size(0)
        all_logits.append(logits.detach().cpu())
        all_labels.append(yb.detach().cpu())
    return total_loss / len(loader.dataset), binary_metrics(torch.cat(all_logits), torch.cat(all_labels))


def main():
    cfg = Config()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dataset = build_dataset(cfg.n_samples)
    n_train = int(0.70 * len(dataset))
    n_val = int(0.15 * len(dataset))
    n_test = len(dataset) - n_train - n_val
    train_ds, val_ds, test_ds = random_split(dataset, [n_train, n_val, n_test], generator=torch.Generator().manual_seed(SEED))

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size)
    test_loader = DataLoader(test_ds, batch_size=cfg.batch_size)

    model = MLPClassifier(dropout=cfg.dropout).to(device)
    loss_fn = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=2)

    best_val_loss = float("inf")
    stale_epochs = 0
    checkpoint_path = Path(cfg.checkpoint_path)

    for epoch in range(1, cfg.epochs + 1):
        start = time.perf_counter()
        train_loss, _ = run_epoch(model, train_loader, loss_fn, optimizer, device, True, cfg.grad_clip_norm)
        val_loss, val_metrics = run_epoch(model, val_loader, loss_fn, optimizer, device, False, cfg.grad_clip_norm)
        scheduler.step(val_loss)

        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            stale_epochs = 0
            torch.save({"model_state": model.state_dict(), "config": cfg.__dict__, "epoch": epoch}, checkpoint_path)
        else:
            stale_epochs += 1

        print(
            f"epoch={epoch:02d} train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
            f"val_f1={val_metrics['f1']:.4f} lr={optimizer.param_groups[0]['lr']:.6f} "
            f"seconds={time.perf_counter() - start:.2f} stale={stale_epochs}"
        )
        if stale_epochs >= cfg.early_stopping_patience:
            print("Early stopping triggered")
            break

    payload = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(payload["model_state"])
    test_loss, test_metrics = run_epoch(model, test_loader, loss_fn, optimizer, device, False, cfg.grad_clip_norm)
    print("test_loss=", round(test_loss, 4), "test_metrics=", test_metrics)


if __name__ == "__main__":
    main()
```

## Tu Kiem Tra

1. Vi sao phai goi `optimizer.zero_grad()` truoc batch moi?
2. `model.train()` va `model.eval()` khac nhau o dau?
3. Khi nao nen dung AdamW thay vi SGD?
4. Scheduler giai quyet van de gi cua learning rate?
5. Early stopping can save checkpoint nhu the nao de tranh dung model kem?

## Checklist

- [ ] Viet duoc training loop PyTorch co train/validation.
- [ ] Dung optimizer, scheduler, dropout, weight decay.
- [ ] Co gradient clipping.
- [ ] Co early stopping va checkpoint best model.
- [ ] Log loss, metric, LR va epoch time.
- [ ] Chay script thanh cong tren CPU hoac GPU.
- [ ] Giai thich duoc production concerns cua training job.

## Tai Lieu Tham Khao

- PyTorch Tutorials: Training a Classifier.
- PyTorch Docs: `torch.optim`, `lr_scheduler`, `DataLoader`.
- fast.ai Practical Deep Learning.
- Keywords: `AdamW`, `learning rate scheduler`, `gradient clipping`, `early stopping`.

---


# Day 12: NLP Fundamentals & Tokenizer

## Muc Tieu

- Hieu text preprocessing, tokenization, vocabulary, special tokens va OOV.
- Phan biet BPE, WordPiece, SentencePiece o muc ung dung.
- Biet vi sao token count anh huong context limit, latency va cost.
- So sanh tokenizer cua BERT, GPT-style model va PhoBERT.
- Nhan dien cac van de rieng cua tieng Viet khi tokenize.

## TL;DR

Model NLP khong nhin text nhu con nguoi, ma nhin sequence token id. Tokenizer la contract giua raw text va model weights; dung sai tokenizer thi model input sai. Voi LLM/RAG, token count la cost, latency va context budget. Tieng Viet co dau, khong dau, tach am tiet bang space va word segmentation lam tokenization phuc tap hon English.

## 1. Text Preprocessing

Preprocessing bien raw text thanh input on dinh:

- Normalize whitespace.
- Lowercase hay giu case.
- Remove HTML/markdown noise.
- Normalize Unicode.
- Xu ly emoji, punctuation, number, URL, email.
- Language detection.
- PII redaction neu can log/debug.
- Sentence splitting/chunking.

Khong nen clean qua tay:

- Xoa dau tieng Viet co the lam mat meaning.
- Xoa punctuation co the lam mat intent.
- Lowercase co the lam mat entity/code/token.
- Remove stopwords khong phu hop voi Transformer/LLM.

Map ve SE: preprocessing giong input validation + canonicalization trong API. Neu train va inference preprocess khac nhau, do la train-serving skew.

## 2. Tokenization

```text
raw text -> tokens -> token ids -> model embedding
```

Token co the la word, subword, character, byte hoac special token nhu `[CLS]`, `[SEP]`, `[PAD]`, `[UNK]`, `<s>`, `</s>`.

Trong production, tokenizer la dependency bat buoc phai version cung model.

## 3. BPE, WordPiece, SentencePiece

| Method | Dung o dau | Y tuong | Note |
|---|---|---|---|
| BPE | GPT-style, RoBERTa/PhoBERT style | Merge pair pho bien thanh subword | Tot cho open vocabulary |
| WordPiece | BERT | Chon subword dua tren likelihood | Hay co prefix nhu `##` |
| SentencePiece | T5/LLaMA/multilingual | Train tren raw text, coi space nhu symbol | Tot cho multilingual |
| Byte-level BPE | GPT-style | Tokenize o byte level | It gap OOV, token count co the bat ngo |

OOV:

- Word-level tokenizer de gap unknown word.
- Subword/byte tokenizer giam OOV bang cach tach tu la thanh manh nho.
- `[UNK]` nhieu la tin hieu tokenizer/model khong hop domain.

## 4. Vocabulary, Padding, Truncation, Attention Mask

| Token | Vai tro |
|---|---|
| `[PAD]` | Pad batch cung length |
| `[UNK]` | Unknown token |
| `[CLS]` | Dai dien sequence cho BERT classifier |
| `[SEP]` | Separator giua sentence |
| `<s>`, `</s>` | Begin/end sequence |

Padding can cho batch tensor cung shape. Attention mask bao model bo qua PAD.

Truncation cat input vuot max length. Trong RAG, truncation am tham co the lam answer sai.

Production rule:

```text
Khong de truncation mac dinh ma khong log token length distribution.
```

## 5. Token Limit, Token Cost, Latency

Token anh huong:

- Context window.
- Chi phi API.
- Latency.
- Memory/KV cache.
- Chunk size trong RAG.
- Max output length.

Guidance:

- Luon reserve output budget, vi du 500-1000 tokens.
- Log p50/p95/p99 input token.
- Dat hard limit theo tenant/use case.
- Chunk theo tokenizer cua embedding/generator, khong theo character count don thuan.

## 6. Tieng Viet Bi Tokenize Nhu The Nao

Tieng Viet co dac thu:

- Space thuong tach am tiet, khong chac tach tu.
- Co dau vs khong dau token khac nhau.
- Code-mixing Viet/English pho bien trong tech/support.
- Ten rieng, viet tat, so hop dong, ma loi, SKU co the bi tach nho.
- PhoBERT thuong duoc train voi text tieng Viet da word-segmented, vi du `xu_ly ngon_ngu`.

Production note:

- Fine-tune PhoBERT thi dung tokenizer va preprocessing dung voi model card.
- GPT-style co the xu ly raw text linh hoat hon, nhung token cost cho tieng Viet co the cao hon English.
- Khong hard-code chunk size bang ky tu; phai do token.

## Trade-offs

| Lua chon | Khi nen dung | Trade-off |
|---|---|---|
| Word-level tokenizer | Domain vocab dong, simple baseline | OOV cao, kem voi typo |
| Subword tokenizer | NLP hien dai, open vocabulary | Token count kho doan bang word count |
| Byte-level tokenizer | LLM general-purpose | Token co the kho doc/debug |
| Lowercase | Classification simple, vocab nho | Mat case/entity/code |
| Giu dau tieng Viet | Can semantic day du | Input user khong dau can xu ly rieng |
| Xoa punctuation | Text noisy, model truyen thong | Mat signal voi LLM/Transformer |
| Truncate head | Text co thong tin dau tai lieu | Mat ket luan/cuoi context |
| Truncate tail | Chat history cu dai | Mat instruction ban dau neu lam sai |

## Best Practices Tu Industry

1. Version tokenizer cung model artifact.
2. Log token count distribution cho input, output, retrieved context.
3. Fail fast hoac degrade gracefully khi input vuot token budget.
4. Test tokenizer tren data production sample, khong chi cau English.
5. Voi RAG, chunk theo token va co overlap vua du, sau do evaluate retrieval.

## Performance Considerations

- Tokenization co the la bottleneck CPU khi QPS cao.
- Batch tokenization nhanh hon tokenize tung request.
- Long context lam latency tang manh do attention/KV cache.
- Padding qua dai lam waste compute; dung dynamic padding theo batch.
- Cache tokenized document chunks cho ingestion pipeline.

## Production Concerns

- PII: tokenizer debug output co the lo raw text.
- Prompt injection: preprocessing khong duoc xoa mat instruction boundary/audit context.
- Versioning: doi tokenizer la breaking change voi model.
- Observability: log token length, truncation count, OOV/UNK rate neu co.
- Multi-tenant: enforce token budget theo tenant.
- Cost control: reject/summarize/compress input qua dai truoc khi goi LLM.

## Ung Dung Thuc Te

- Estimate cost cho chatbot/RAG truoc khi deploy.
- Chon chunk size cho Vietnamese enterprise RAG.
- Debug vi sao fine-tuned classifier score kem do sai preprocessing/tokenizer.
- So sanh baseline TF-IDF vs Transformer trong text classification.

## Hands-on Trong 60-90 Phut

```bash
pip install transformers tokenizers sentencepiece tiktoken
```

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

TEXTS = {
    "vi_no_diacritics": "Toi dang hoc xu ly ngon ngu tu nhien va tokenizer cho he thong RAG.",
    "vi_with_diacritics": "Toi dang hoc xu ly ngon ngu tu nhien va tokenizer cho he thong RAG.",
    "support_ticket": "Khach hang bao loi thanh toan PAY_403 luc 09:30, can retry idempotent.",
    "phobert_segmented": "Toi dang_hoc xu_ly ngon_ngu tu_nhien va tokenizer cho he_thong RAG.",
}

DEMO_PRICE = {"input_usd_per_1m_tokens": 0.15, "output_usd_per_1m_tokens": 0.60}


@dataclass
class TokenizerAdapter:
    name: str
    count_tokens: Callable[[str], int]
    preview_tokens: Callable[[str], list[str]]


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = input_tokens / 1_000_000 * DEMO_PRICE["input_usd_per_1m_tokens"]
    output_cost = output_tokens / 1_000_000 * DEMO_PRICE["output_usd_per_1m_tokens"]
    return input_cost + output_cost


def load_tokenizers() -> list[TokenizerAdapter]:
    adapters: list[TokenizerAdapter] = []
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        adapters.append(
            TokenizerAdapter(
                name="gpt_style_cl100k_base",
                count_tokens=lambda text, enc=enc: len(enc.encode(text)),
                preview_tokens=lambda text, enc=enc: [enc.decode([i]) for i in enc.encode(text)[:20]],
            )
        )
    except Exception as exc:
        print("Skip tiktoken:", exc)

    try:
        from transformers import AutoTokenizer

        for model_name in ["bert-base-multilingual-cased", "vinai/phobert-base"]:
            try:
                tok = AutoTokenizer.from_pretrained(model_name)
                adapters.append(
                    TokenizerAdapter(
                        name=model_name,
                        count_tokens=lambda text, tok=tok: len(tok.encode(text, add_special_tokens=False)),
                        preview_tokens=lambda text, tok=tok: tok.convert_ids_to_tokens(
                            tok.encode(text, add_special_tokens=False)[:20]
                        ),
                    )
                )
            except Exception as exc:
                print(f"Skip {model_name}: {exc}")
    except Exception as exc:
        print("Skip transformers:", exc)
    return adapters


def main():
    tokenizers = load_tokenizers()
    if not tokenizers:
        print("No tokenizer loaded. Check package install or network for HuggingFace models.")
        return

    reserved_output_tokens = 300
    max_context_tokens = 4096
    for text_name, text in TEXTS.items():
        print("\n===", text_name, "===")
        print(text)
        for adapter in tokenizers:
            input_tokens = adapter.count_tokens(text)
            total = input_tokens + reserved_output_tokens
            budget = "ok" if total <= max_context_tokens else f"too_long_by_{total - max_context_tokens}"
            print(
                f"{adapter.name:32} tokens={input_tokens:4d} "
                f"cost_usd_demo={estimate_cost(input_tokens, reserved_output_tokens):.8f} budget={budget}"
            )
            print("preview=", adapter.preview_tokens(text))


if __name__ == "__main__":
    main()
```

Bai tap:

- Them 10 cau ticket tieng Viet that tu domain cua ban va do p95 token count.
- So sanh text co dau vs khong dau.
- Thu doan markdown dai 2-3 trang va tinh chunk size 300/500/800 tokens.
- Dat budget max context 4096, reserve output 700, tinh input con lai.
- Viet function reject request neu token vuot budget va tra error JSON ro rang.

## Tu Kiem Tra

1. Vi sao tokenizer phai version cung model?
2. BPE khac WordPiece va SentencePiece o muc ung dung nhu the nao?
3. Vi sao word count khong du de estimate LLM cost?
4. Tieng Viet co dac thu gi lam tokenization kho hon English?
5. Truncation am tham co the gay bug production nao?

## Checklist

- [ ] Hieu raw text -> token -> token id -> embedding.
- [ ] Phan biet BPE, WordPiece, SentencePiece.
- [ ] Chay script so sanh BERT, GPT-style va PhoBERT tokenizer.
- [ ] Tinh duoc token count va cost demo.
- [ ] Biet dat context budget va reserve output tokens.
- [ ] Ghi note ve tokenizer choice cho Day 16 fine-tuning.
- [ ] Hieu risk cua truncation, padding, OOV va sai preprocessing.

## Tai Lieu Tham Khao

- HuggingFace Course: Tokenizers.
- HuggingFace Transformers Docs: `AutoTokenizer`.
- OpenAI Cookbook: token counting.
- Google SentencePiece.
- BERT paper: WordPiece/tokenization overview.
- PhoBERT model card / VinAI PhoBERT.

---


# Day 13: Attention Mechanism

## Muc Tieu

- Hieu Query, Key, Value va vi sao day la core primitive cua Transformer.
- Implement scaled dot-product attention bang PyTorch.
- Phan biet self-attention, causal attention va padding mask.
- Hieu multi-head attention va trade-off giua quality, memory, latency.
- Biet production concerns khi dua attention-based model vao service that.

## TL;DR

Attention la co che de moi token chon thong tin quan trong tu cac token khac. Query giong request can tim context, Key giong index/signature, Value giong payload duoc lay ve. Self-attention giup token mix context toan sequence va chay parallel tot hon RNN, nhung chi phi memory/compute tang theo `seq_len^2`. Trong production, context dai, mask sai, KV cache, latency va OOM la nhung diem can quan tam dau tien.

## 1. Attention La Gi?

Trong backend, khi service can du lieu, no query database/cache va lay record phu hop. Attention lam viec tuong tu nhung tren vector:

```text
token hien tai -> tao Query
cac token khac -> co Key va Value
Query so khop voi Key -> score
score qua softmax -> weight
weighted sum cua Value -> context vector
```

Map ve Senior SE:

| Attention concept | SE analogy |
|---|---|
| Query | Request can tim thong tin |
| Key | Index/search signature |
| Value | Payload/record content |
| Attention score | Ranking score |
| Softmax weight | Normalized priority |
| Context vector | Aggregated response |
| Mask | Permission/filter/window constraint |

## 2. Query, Key, Value

Voi embedding cua token `x`, model hoc 3 projection:

```text
Q = x Wq
K = x Wk
V = x Wv
```

- Query: token nay dang can loai thong tin gi.
- Key: token nay co dac diem gi de token khac tim den.
- Value: noi dung se duoc truyen sang token khac neu duoc attend.

Q/K/V khong phai data structure engineer set bang tay. Chung la matrix hoc duoc trong training.

## 3. Scaled Dot-Product Attention

Cong thuc:

```text
Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V
```

Shapes pho bien:

```text
Q: [batch, heads, seq_len, head_dim]
K: [batch, heads, seq_len, head_dim]
V: [batch, heads, seq_len, head_dim]

Q K^T: [batch, heads, seq_len, seq_len]
output: [batch, heads, seq_len, head_dim]
```

Vi sao chia `sqrt(d_k)`? Neu `head_dim` lon, dot product co variance lon, softmax de bi saturated. Khi softmax saturated, gradient yeu va training kho on dinh.

## 4. Self-Attention

Self-attention nghia la Q, K, V deu den tu cung mot sequence.

```text
Input tokens: [t1, t2, t3, t4]
Moi token co the attend den: [t1, t2, t3, t4]
```

Transformer bat long-range dependency tot vi token dau cau co the anh huong token cuoi cau, va tat ca token tinh attention song song trong training. Gia phai tra la `O(n^2)` theo sequence length.

## 5. Mask: Padding Mask Va Causal Mask

Padding mask:

```text
["toi", "thich", "AI", "<pad>", "<pad>"]
```

Model khong nen attend vao `<pad>`, vi do khong phai noi dung that.

Causal mask dung cho decoder-only model:

```text
Token o vi tri i chi duoc attend vao token <= i
```

Neu train language model ma quen causal mask, model nhin thay future token. Day la data leakage nghiem trong.

## 6. Multi-Head Attention

Mot attention head co the hoc mot kieu relation. Multi-head attention chay nhieu head song song:

```text
head 1: subject-verb relation
head 2: entity-reference relation
head 3: local phrase relation
head 4: sentiment keyword relation
```

Sau do concat output cac head va project ve `embed_dim`.

## 7. Attention Parallel Hon RNN O Dau?

RNN xu ly sequence tung buoc:

```text
h1 -> h2 -> h3 -> h4
```

Transformer self-attention co the xu ly tat ca token trong mot matrix operation:

```text
[t1, t2, t3, t4] -> attention matrix -> output
```

Voi GPU, matrix multiplication rat hieu qua. Diem yeu la attention matrix `seq_len x seq_len` rat ton memory voi context dai.

## Trade-offs

| Lua chon | Khi nen dung | Khong nen dung khi | Production note |
|---|---|---|---|
| Full self-attention | Sequence vua, can relation toan cuc | Context rat dai, memory chat | Quality tot nhung `O(n^2)` |
| Causal attention | Generation, decoder-only LM | Classification can bidirectional context | Bat buoc de tranh leakage |
| Bidirectional attention | Classification, embedding, reranking | Autoregressive generation | BERT-style |
| Multi-head attention | Can hoc nhieu relation | Model nho, latency chat | Benchmark head count |
| Flash Attention | Context dai, GPU modern | CPU/simple demo | Giam memory attention |
| Sliding/window attention | Long document | Can global relation day du | Can global token/summary |

Guidance:

- Classification text: dung bidirectional encoder attention.
- Generation: dung causal decoder attention.
- Long context RAG: dung chunking/retrieval truoc, khong nhet tat ca vao context.
- Production GPU: uu tien implementation da toi uu nhu PyTorch SDPA, Flash Attention, vLLM.

## Best Practices Tu Industry

1. Dung implementation co san trong PyTorch/HuggingFace truoc khi tu viet.
2. Test mask rieng bang unit test, dac biet causal mask va padding mask.
3. Gioi han max sequence length theo SLA.
4. Monitor OOM, p95/p99 latency, token length distribution va truncation rate.
5. Benchmark voi input length that.

## Performance Considerations

- Attention compute: gan `O(batch * heads * seq_len^2 * head_dim)`.
- Attention weight memory: `batch * heads * seq_len * seq_len`.
- `batch=8`, `heads=12`, `seq_len=512`, FP16: attention weights khoang 50 MB cho mot layer.
- `batch=1`, `heads=32`, `seq_len=4096`, FP16: attention weights khoang 1 GB cho mot layer neu materialize day du.
- Context dai gap 4 lan thi attention matrix lon gap 16 lan.
- Inference decoder-only can dung KV cache de tranh tinh lai K/V cua token cu.

## Production Concerns

- Mask bug co the gay data leakage hoac model hoc shortcut sai.
- Long prompt/context co the gay OOM hoac p99 latency vuot SLA.
- User input nen co token limit va timeout.
- Attention weights khong phai explainability day du; dung de debug, khong nen xem la audit proof.
- Can version tokenizer/model/config cung nhau.
- Can logging token count, truncation, model version, latency va error type.

Dung duoc trong production khong? Co, nhung khong tu viet attention kernel cho production tru khi co ly do rat ro. Nen dung model/runtime da toi uu, gioi han context, test mask, monitor latency/memory va co fallback khi model service qua tai.

## Ung Dung Thuc Te

- Text classification: BERT/PhoBERT dung self-attention de classify sentiment, spam, ticket category.
- Reranking trong RAG: cross-encoder dung attention giua query va document de score relevance.
- LLM generation: GPT/LLaMA/Qwen dung causal self-attention de sinh token tiep theo.
- Code assistant: attention giup model lien ket function call, variable definition va context trong file.

## Hands-on Trong 60-90 Phut

Implement multi-head self-attention va train classifier nho de visualize attention tu token `<cls>`.

```bash
pip install torch matplotlib
```

```python
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import matplotlib.pyplot as plt
import torch
from torch import nn
import torch.nn.functional as F

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)

VOCAB = ["<cls>", "payment", "shipping", "account", "invoice", "login", "refund", "cancel", "broken", "fast", "slow", "support", "price", "order"]
TARGET_WORDS = {"refund", "cancel", "broken"}
stoi = {word: idx for idx, word in enumerate(VOCAB)}
ID_CLS = stoi["<cls>"]
TARGET_IDS = [stoi[w] for w in TARGET_WORDS]
NON_TARGET_IDS = [idx for word, idx in stoi.items() if word not in TARGET_WORDS and word != "<cls>"]


@dataclass
class Batch:
    tokens: torch.Tensor
    labels: torch.Tensor


def make_batch(batch_size: int, seq_len: int) -> Batch:
    xs, ys = [], []
    for _ in range(batch_size):
        is_positive = random.random() < 0.5
        ids = [random.choice(NON_TARGET_IDS) for _ in range(seq_len - 1)]
        if is_positive:
            ids[random.randrange(len(ids))] = random.choice(TARGET_IDS)
        xs.append([ID_CLS] + ids)
        ys.append(int(is_positive))
    return Batch(torch.tensor(xs, dtype=torch.long), torch.tensor(ys, dtype=torch.long))


def scaled_dot_product_attention(q, k, v, mask=None):
    scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(q.size(-1))
    if mask is not None:
        scores = scores.masked_fill(~mask, torch.finfo(scores.dtype).min)
    weights = torch.softmax(scores, dim=-1)
    return torch.matmul(weights, v), weights


def make_causal_mask(seq_len: int, device: torch.device):
    return torch.tril(torch.ones(seq_len, seq_len, dtype=torch.bool, device=device)).view(1, 1, seq_len, seq_len)


class MultiHeadSelfAttention(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int):
        super().__init__()
        if embed_dim % num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.qkv = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

    def forward(self, x, mask=None):
        batch_size, seq_len, embed_dim = x.shape
        qkv = self.qkv(x).view(batch_size, seq_len, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        context, weights = scaled_dot_product_attention(q, k, v, mask)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, embed_dim)
        return self.out_proj(context), weights


class TinyAttentionClassifier(nn.Module):
    def __init__(self, vocab_size: int, embed_dim: int = 64, num_heads: int = 4):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.attn = MultiHeadSelfAttention(embed_dim, num_heads)
        self.norm1 = nn.LayerNorm(embed_dim)
        self.ffn = nn.Sequential(nn.Linear(embed_dim, 4 * embed_dim), nn.GELU(), nn.Linear(4 * embed_dim, embed_dim))
        self.norm2 = nn.LayerNorm(embed_dim)
        self.classifier = nn.Linear(embed_dim, 2)

    def forward(self, input_ids, mask=None):
        x = self.embedding(input_ids)
        attn_out, weights = self.attn(x, mask=mask)
        x = self.norm1(x + attn_out)
        x = self.norm2(x + self.ffn(x))
        return self.classifier(x[:, 0]), weights


@torch.no_grad()
def evaluate(model: nn.Module) -> float:
    model.eval()
    batch = make_batch(batch_size=1000, seq_len=8)
    logits, _ = model(batch.tokens)
    return (logits.argmax(dim=-1) == batch.labels).float().mean().item()


def train():
    model = TinyAttentionClassifier(vocab_size=len(VOCAB))
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.01)
    for step in range(1, 401):
        model.train()
        batch = make_batch(batch_size=64, seq_len=8)
        logits, _ = model(batch.tokens)
        loss = F.cross_entropy(logits, batch.labels)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if step % 100 == 0:
            print(f"step={step} loss={loss.item():.4f} test_acc={evaluate(model):.3f}")
    return model


def inspect_attention(model: nn.Module):
    model.eval()
    words = ["<cls>", "shipping", "invoice", "refund", "account", "support", "price", "order"]
    input_ids = torch.tensor([[stoi[w] for w in words]], dtype=torch.long)
    with torch.no_grad():
        logits, weights = model(input_ids)
        prob_positive = F.softmax(logits, dim=-1)[0, 1].item()
    cls_attention = weights[0, :, 0, :].mean(dim=0).cpu()
    print("prob_positive=", round(prob_positive, 3))
    for word, weight in zip(words, cls_attention.tolist()):
        print(f"{word:>10s}: {weight:.3f}")
    plt.figure(figsize=(8, 3))
    plt.bar(words, cls_attention.tolist())
    plt.tight_layout()
    plt.savefig("day13_attention_weights.png", dpi=160)
    causal_mask = make_causal_mask(input_ids.size(1), input_ids.device)
    with torch.no_grad():
        embedded = model.embedding(input_ids)
        _, causal_weights = model.attn(embedded, mask=causal_mask)
    print("future attention pos2->pos5 =", round(causal_weights[0, 0, 2, 5].item(), 6))


if __name__ == "__main__":
    inspect_attention(train())
```

## Tu Kiem Tra

1. Query, Key, Value khac nhau o dau?
2. Vi sao phai chia attention score cho `sqrt(d_k)`?
3. Causal mask giai quyet data leakage nao?
4. Vi sao attention parallel tot hon RNN trong training?
5. Khi sequence length tang tu 1024 len 4096, attention memory tang bao nhieu lan?

## Checklist

- [ ] Giai thich duoc Q/K/V bang analogy API/database/cache.
- [ ] Viet duoc scaled dot-product attention.
- [ ] Hieu shape cua Q, K, V va attention weight.
- [ ] Biet khi nao dung causal mask va padding mask.
- [ ] Chay duoc script hands-on va xem attention chart.
- [ ] Ghi lai 3 production risks cua attention.

## Tai Lieu Tham Khao

- Attention Is All You Need: https://arxiv.org/abs/1706.03762
- The Illustrated Transformer: https://jalammar.github.io/illustrated-transformer/
- The Annotated Transformer: https://nlp.seas.harvard.edu/annotated-transformer/
- PyTorch scaled dot product attention docs.

---


# Day 14: Transformer Architecture

## Muc Tieu

- Hieu Transformer block gom attention, residual connection, LayerNorm va feed-forward network.
- Phan biet encoder-only, decoder-only va encoder-decoder architecture.
- Biet BERT, GPT/LLaMA/Qwen, T5 phu hop voi loai bai toan nao.
- Hieu positional encoding, RoPE va vi sao Transformer can position information.
- Nhan dien performance va production constraints cua Transformer model.

## TL;DR

Transformer la stack nhieu block, moi block gom self-attention de mix context va feed-forward network de bien doi feature tung token. Encoder-only model nhu BERT tot cho classification, embedding, reranking. Decoder-only model nhu GPT, LLaMA, Qwen tot cho generation vi dung causal mask va predict next token. Encoder-decoder model nhu T5 tot cho sequence-to-sequence. Trong production, chon architecture theo task, latency, memory, context length, license va deployment constraint.

## 1. Transformer Block

```text
input embeddings
  -> self-attention
  -> residual connection
  -> LayerNorm
  -> feed-forward network
  -> residual connection
  -> LayerNorm
  -> output embeddings
```

Map sang SE:

| Transformer part | SE analogy |
|---|---|
| Embedding | Convert raw input thanh internal representation |
| Self-attention | Context lookup/routing giua tokens |
| Feed-forward network | Per-token business transformation |
| Residual connection | Safe bypass path giup gradient flow |
| LayerNorm | Stabilizer/normalizer giua stages |
| Stack nhieu layers | Pipeline nhieu stage refine representation |

Transformer khong chi la attention. Attention la context mixing, con FFN thuong chiem phan lon parameter va compute.

## 2. Encoder

Encoder nhan toan bo input va cho moi token attend den moi token khac.

```text
Input:  [t1, t2, t3, t4]
Mask:   bidirectional
Output: contextual vector cho tung token
```

Dung tot cho text classification, NER, semantic embedding, reranking va feature extraction. BERT/PhoBERT la encoder-only.

## 3. Decoder

Decoder-only model dung causal mask:

```text
Token i chi thay token 1..i
```

Training objective pho bien: predict next token.

Dung tot cho chatbot, code generation, summarization bang prompt, tool/function calling, agent workflow va general text generation. GPT, LLaMA, Qwen, Mistral, DeepSeek-style chat model la decoder-only.

## 4. Encoder-Decoder

```text
source input -> encoder
decoder sinh output, vua attend vao output da sinh, vua cross-attend vao encoder output
```

Dung tot cho translation, summarization co input ro, data-to-text, text normalization va instruction-to-output theo format on dinh. T5 la vi du pho bien.

## 5. Positional Encoding

Self-attention tu ban than khong biet thu tu token. Cac cach them position:

| Cach | Y tuong |
|---|---|
| Sinusoidal | Cong vector sin/cos theo vi tri |
| Learned absolute position | Hoc embedding rieng cho moi position |
| RoPE | Rotate Q/K theo position |
| ALiBi | Them bias theo khoang cach |

RoPE pho bien trong decoder-only LLM hien dai vi encode relative position tot va ho tro context extension tot hon learned absolute position trong nhieu setting.

## 6. LayerNorm

LayerNorm normalize activation trong hidden dimension cua tung token.

Tac dung:

- Giam exploding/unstable activation.
- Training sau hon on dinh hon.
- Giu distribution giua cac layers de optimizer lam viec tot.

Model hien dai thuong uu tien Pre-LN:

```text
Pre-LN: x -> norm -> sublayer -> residual
```

## 7. Feed-Forward Network

FFN ap dung rieng cho tung token:

```text
FFN(x) = Linear -> activation -> Linear
```

No khong mix token voi nhau. Viec mix token nam o attention. FFN bien doi representation sau khi da co context.

## 8. Residual Connection

```text
x_next = x + sublayer(x)
```

Residual giup gradient flow, cho phep layer hoc delta thay vi hoc lai toan bo representation, va giam risk degrade khi stack nhieu layers.

## Trade-offs

| Architecture | Nen dung khi | Khong nen dung khi | Production note |
|---|---|---|---|
| Encoder-only | Classification, embedding, reranking | Chat/generation dai | Latency tot, output khong generative |
| Decoder-only | Chat, generation, tool calling | Pure classification latency rat chat | Can KV cache, token cost |
| Encoder-decoder | Translation/summarization seq2seq | Chat app tong quat don gian | More moving parts |
| Sinusoidal PE | Hoc concept, model nho | LLM hien dai can context dai | De implement |
| Learned PE | Max length co dinh | Can extrapolate context | Vuot max position la risk |
| RoPE | Decoder LLM hien dai | Tu implement neu chua can | Can config dung voi model |
| Quantized model | Giam VRAM/cost | Quality-sensitive task chua eval | Can regression eval |

Guidance:

- Sentiment/ticket classification tieng Viet: bat dau voi PhoBERT/BERT encoder-only.
- Chatbot/assistant: dung decoder-only chat model.
- Summarization/translation co format ro: can nhac T5/encoder-decoder hoac decoder-only.
- RAG production: generator thuong la decoder-only; embedding/reranker thuong la encoder.

## Best Practices Tu Industry

1. Chon architecture theo task, khong theo hype.
2. Dung pretrained model va tokenizer dung cap.
3. Freeze/LoRA/fine-tune nhe truoc khi full fine-tune.
4. Benchmark tren prompt length va output length that cua product.
5. Viet model card noi bo: intended use, limitation, metrics, license, data risk, rollout plan.
6. Tach model serving khoi business API bang model gateway neu co nhieu model/provider.

## Performance Considerations

- BERT-base khoang 110M parameters: FP32 khoang 420 MB weights, FP16 khoang 220 MB.
- 7B decoder model FP16 can khoang 14 GB chi rieng weights, chua tinh KV cache.
- Attention cost tang theo `seq_len^2`; context 8192 ton attention memory gap 16 lan context 2048.
- Decoder inference co KV cache: tranh tinh lai K/V cu, nhung KV cache ton VRAM.
- Output token cang dai thi request cang cham va cang ton cost.
- Quantization INT8/INT4 giam VRAM nhung can eval quality.

## Production Concerns

- License model co cho commercial use khong.
- Tokenizer/config/model weights phai version cung nhau.
- Prompt/context co PII can masking va retention policy.
- Causal model co prompt injection risk khi goi tool hoac RAG.
- Model upgrade phai co golden eval va rollback.
- Can monitor latency, error rate, token usage, cost/request, refusal rate, hallucination report.
- Long context khong thay the retrieval design tot.

Dung duoc trong production khong? Co, nhung dieu kien la chon dung architecture, co eval set, co serving runtime phu hop, co token budget, monitoring, rollback va policy ve data/license.

## Ung Dung Thuc Te

- Customer support classifier: encoder-only model classify ticket category, priority, sentiment.
- Enterprise RAG assistant: embedding/reranker dung encoder, generator dung decoder-only LLM.
- Code review assistant: decoder-only model doc diff, sinh comment, goi tool test/static analysis.
- Document automation: encoder-decoder hoac decoder-only extract/summarize hop dong, invoice, policy.

## Hands-on Trong 60-90 Phut

Build Tiny Transformer encoder classifier de thay ro embedding, positional encoding, attention, FFN, LayerNorm va residual.

```bash
pip install torch
```

```python
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import torch
from torch import nn
import torch.nn.functional as F

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)

VOCAB = ["<cls>", "good", "great", "fast", "bad", "slow", "broken", "order", "shipping", "payment", "support", "price", "app", "account"]
POSITIVE = {"good", "great", "fast"}
NEGATIVE = {"bad", "slow", "broken"}
stoi = {word: idx for idx, word in enumerate(VOCAB)}
ID_CLS = stoi["<cls>"]
POS_IDS = [stoi[w] for w in POSITIVE]
NEG_IDS = [stoi[w] for w in NEGATIVE]
NEUTRAL_IDS = [idx for word, idx in stoi.items() if word not in POSITIVE and word not in NEGATIVE and word != "<cls>"]


@dataclass
class Batch:
    tokens: torch.Tensor
    labels: torch.Tensor


def make_batch(batch_size: int, seq_len: int) -> Batch:
    xs, ys = [], []
    for _ in range(batch_size):
        label = random.randint(0, 1)
        ids = [random.choice(NEUTRAL_IDS) for _ in range(seq_len - 1)]
        ids[random.randrange(len(ids))] = random.choice(POS_IDS if label == 1 else NEG_IDS)
        xs.append([ID_CLS] + ids)
        ys.append(label)
    return Batch(torch.tensor(xs, dtype=torch.long), torch.tensor(ys, dtype=torch.long))


class SinusoidalPositionalEncoding(nn.Module):
    def __init__(self, max_len: int, embed_dim: int):
        super().__init__()
        pe = torch.zeros(max_len, embed_dim)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, embed_dim, 2, dtype=torch.float32) * (-math.log(10000.0) / embed_dim))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, : x.size(1)]


def scaled_dot_product_attention(q, k, v, mask=None):
    scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(q.size(-1))
    if mask is not None:
        scores = scores.masked_fill(~mask, torch.finfo(scores.dtype).min)
    weights = torch.softmax(scores, dim=-1)
    return torch.matmul(weights, v), weights


class MultiHeadSelfAttention(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int):
        super().__init__()
        if embed_dim % num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.qkv = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

    def forward(self, x, mask=None):
        batch_size, seq_len, embed_dim = x.shape
        qkv = self.qkv(x).view(batch_size, seq_len, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        context, weights = scaled_dot_product_attention(q, k, v, mask)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, embed_dim)
        return self.out_proj(context), weights


class TransformerBlock(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.norm1 = nn.LayerNorm(embed_dim)
        self.attn = MultiHeadSelfAttention(embed_dim, num_heads)
        self.dropout1 = nn.Dropout(dropout)
        self.norm2 = nn.LayerNorm(embed_dim)
        self.ffn = nn.Sequential(nn.Linear(embed_dim, 4 * embed_dim), nn.GELU(), nn.Dropout(dropout), nn.Linear(4 * embed_dim, embed_dim))
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        attn_out, weights = self.attn(self.norm1(x), mask=mask)
        x = x + self.dropout1(attn_out)
        x = x + self.dropout2(self.ffn(self.norm2(x)))
        return x, weights


class TinyTransformerClassifier(nn.Module):
    def __init__(self, vocab_size: int, max_len: int = 16, embed_dim: int = 64, num_heads: int = 4, num_layers: int = 2):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.position = SinusoidalPositionalEncoding(max_len=max_len, embed_dim=embed_dim)
        self.blocks = nn.ModuleList([TransformerBlock(embed_dim=embed_dim, num_heads=num_heads) for _ in range(num_layers)])
        self.norm = nn.LayerNorm(embed_dim)
        self.classifier = nn.Linear(embed_dim, 2)

    def forward(self, input_ids, mask=None):
        x = self.position(self.embedding(input_ids))
        for block in self.blocks:
            x, _ = block(x, mask=mask)
        return self.classifier(self.norm(x)[:, 0])


@torch.no_grad()
def evaluate(model: nn.Module) -> float:
    model.eval()
    batch = make_batch(batch_size=1000, seq_len=10)
    preds = model(batch.tokens).argmax(dim=-1)
    return (preds == batch.labels).float().mean().item()


def main():
    model = TinyTransformerClassifier(vocab_size=len(VOCAB), max_len=10)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.01)
    for step in range(1, 301):
        model.train()
        batch = make_batch(batch_size=64, seq_len=10)
        loss = F.cross_entropy(model(batch.tokens), batch.labels)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if step % 75 == 0:
            print(f"step={step} loss={loss.item():.4f} test_acc={evaluate(model):.3f}")
    print(model)


if __name__ == "__main__":
    main()
```

## Tu Kiem Tra

1. Vi sao Transformer can positional encoding?
2. Encoder-only va decoder-only khac nhau o mask va objective nao?
3. FFN trong Transformer lam gi neu no khong mix token?
4. Residual connection giup training deep network nhu the nao?
5. Khi nao nen dung BERT/PhoBERT thay vi GPT-style model?

## Checklist

- [ ] Ve lai duoc mot Transformer block.
- [ ] Phan biet encoder-only, decoder-only, encoder-decoder.
- [ ] Giai thich duoc positional encoding va RoPE.
- [ ] Hieu LayerNorm, FFN, residual connection.
- [ ] Chay duoc Tiny Transformer classifier.
- [ ] Ghi lai architecture nao phu hop cho Day 16 fine-tune classifier.

## Tai Lieu Tham Khao

- Attention Is All You Need: https://arxiv.org/abs/1706.03762
- The Illustrated Transformer: https://jalammar.github.io/illustrated-transformer/
- The Annotated Transformer: https://nlp.seas.harvard.edu/annotated-transformer/
- HuggingFace Transformer course.
- PyTorch Transformer docs.

---


# Day 15: HuggingFace Ecosystem

## Muc Tieu

- Hieu vai tro cua `transformers`, `datasets`, `tokenizers`, `accelerate`, Model Hub va Model Card.
- Biet load tokenizer/model bang `AutoTokenizer`, `AutoModel`, `AutoModelForSequenceClassification`.
- Chay inference bang `pipeline` va manual forward pass.
- Biet doc model card de check license, intended use, limitation, dataset va metric.
- Map HuggingFace ecosystem ve package registry, artifact registry, API contract va dependency management trong production.

## TL;DR

HuggingFace la ecosystem giup dung model NLP/AI nhu dung package va artifact trong software engineering. `transformers` cung cap model API, `datasets` lo data pipeline, `tokenizers` lo text -> token ids, `accelerate` lo multi-GPU/distributed, Model Hub la artifact registry. Trong production, khong chi `from_pretrained()` la xong: can pin revision, check license, benchmark latency/memory, log model version va co rollback path.

## 1. HuggingFace Nhu Artifact Registry Cho AI

| HuggingFace concept | SE equivalent | Y nghia production |
|---|---|---|
| Model Hub | Docker Hub / npm / Maven registry | Noi lay model artifact |
| Model checkpoint | Build artifact | Version can deploy/rollback |
| Model card | README + contract + risk doc | Check license, limitation |
| Dataset Hub | Data registry | Reproducible dataset |
| `transformers` | SDK/client library | Load model, tokenizer, inference |
| `datasets` | Batch data pipeline | Load, split, map, cache data |
| `tokenizers` | Parser/encoder | Text contract truoc khi vao model |
| `accelerate` | Runtime launcher | Scale train/inference tren GPU/TPU |

Senior SE nen nhin model nhu dependency ben ngoai:

```text
app code
  -> tokenizer version
  -> model weights version
  -> model config
  -> preprocessing rule
  -> postprocessing rule
  -> monitoring/rollback
```

Model co risk ve license, bias, training data, quality drift va hardware cost.

## 2. Transformers: Auto Classes Va Pipeline

Hai cach dung chinh:

1. High-level `pipeline`: nhanh, it code, tot cho demo/prototype.
2. Low-level `AutoTokenizer` + `AutoModel...`: kiem soat cao, tot cho production.

```python
from transformers import pipeline

clf = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
print(clf("This product is great"))
```

Manual path:

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForSequenceClassification.from_pretrained(model_id)
```

Production guidance:

- Dung `pipeline` cho prototype, internal tool, batch script nho.
- Dung manual path cho API production de kiem soat batching, device, dtype, timeout, output schema.
- Pin `revision` neu can reproducibility.
- Tranh `trust_remote_code=True` neu chua audit code model repo.

## 3. Tokenizer La Input Contract

Tokenizer bien text thanh integer ids:

```text
"san pham tot" -> [0, 1042, 183, 99, 2]
```

No giong parser trong API gateway:

- Neu parser doi, input vao model doi.
- Neu train dung tokenizer A nhung serving dung tokenizer B, quality co the hong.
- Neu max length qua ngan, text bi truncate mat thong tin.
- Neu max length qua dai, latency/memory tang.

## 4. Model Card Va Governance

Truoc khi dung model tu Hub, doc model card nhu review third-party dependency:

- License: co duoc dung commercial khong?
- Intended use: model duoc train cho task nao?
- Limitation: domain nao model yeu?
- Dataset: data train co lien quan domain cua minh khong?
- Language: co support tieng Viet khong?
- Metrics: metric tren benchmark nao?
- Bias/safety: co risk phan biet, toxic, privacy khong?
- Size: artifact bao nhieu MB/GB?
- Required code: co can `trust_remote_code` khong?

Production rule: khong deploy model neu khong ro license, source, version va owner.

## 5. Datasets, Trainer Va Accelerate

`datasets` dung Apache Arrow/cache de load va transform dataset hieu qua:

```python
from datasets import load_dataset

ds = load_dataset("csv", data_files={"train": "train.csv", "test": "test.csv"})
ds = ds.map(tokenize_fn, batched=True)
```

`Trainer` la training loop co san cho Transformers model: train/eval loop, checkpoint, logging, mixed precision, distributed support va metric callback.

`accelerate` giup chay cung code tren CPU, 1 GPU, multi-GPU, TPU/deepspeed.

## Trade-offs

| Lua chon | Nen dung khi | Khong nen dung khi | Production note |
|---|---|---|---|
| `pipeline` | Demo, POC, batch nho | API can latency/control chat | Kiem soat it hon manual path |
| `AutoModel` manual | API production, custom batching | Prototype rat nhanh | Can tu viet postprocess |
| Model Hub public | Can prototype nhanh | License/data risk chua ro | Pin revision va doc card |
| Self-host model | Can privacy/control/cost on dinh | Team chua co GPU/ops | Can monitoring va scaling |
| Hosted inference API | Can go-live nhanh | Data nhay cam, cost lon | Kiem tra SLA va data policy |
| Trainer API | Fine-tune standard task | Custom training loop phuc tap | Tot cho v1 |
| PhoBERT | Vietnamese NLP | Khong muon segmentation/preprocess | Benchmark voi BERT multilingual |

## Best Practices Tu Industry

1. Pin model version/revision nhu pin Docker image digest.
2. Luu `model_id`, `revision`, tokenizer config, max length va label mapping trong artifact.
3. Doc model card truoc khi train/deploy.
4. Bat dau bang model nho va baseline don gian truoc khi dung model lon.
5. Benchmark p50/p95 latency va memory tren hardware that.
6. Tach preprocessing/tokenization thanh module dung chung cho training va serving.

## Performance Considerations

- Tokenization co the chiem 10-40% latency voi request nho.
- BERT/PhoBERT base khoang 100M+ params, CPU inference co the cham neu request realtime.
- `max_length=128` nhanh hon ro so voi `max_length=512`.
- Batch inference tang throughput nhung tang latency tung request.
- GPU tot cho throughput, nhung API traffic thap co the CPU/ONNX/quantization re hon.
- Cache model o startup, khong load model trong moi request.

## Production Concerns

- License va data governance.
- Supply-chain risk khi load model public.
- `trust_remote_code=True` can audit nhu chay code ben thu ba.
- Model artifact lon can warmup va readiness probe.
- Tokenizer/model mismatch gay bug quality kho debug.
- Can log model version, input length, latency, label, confidence.
- Can fallback model hoac rule neu model service loi.
- Khong log raw PII neu input la review/customer message nhay cam.

## Ung Dung Thuc Te

- Customer support classification: sentiment, topic, priority.
- Content moderation tieng Viet.
- Search/RAG preprocessing: embedding model, reranker, tokenizer count.
- Backoffice automation: classify ticket, route email, detect intent.

## Hands-on Trong 60-90 Phut

```bash
pip install -U transformers torch huggingface_hub
```

```python
from __future__ import annotations

import os
import time

import torch
from huggingface_hub import HfApi
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

INFER_MODEL_ID = os.getenv("INFER_MODEL_ID", "distilbert-base-uncased-finetuned-sst-2-english")
CARD_MODEL_ID = os.getenv("CARD_MODEL_ID", "vinai/phobert-base")


def as_dict(value):
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    return {}


def inspect_model(model_id: str) -> None:
    info = HfApi().model_info(model_id)
    card_data = as_dict(getattr(info, "cardData", None))
    print("\n== Model Hub inspection ==")
    print("model_id:", model_id)
    print("url:", f"https://huggingface.co/{model_id}")
    print("license:", card_data.get("license", "CHECK_MODEL_CARD"))
    print("pipeline_tag:", getattr(info, "pipeline_tag", None))
    print("sha:", getattr(info, "sha", None))
    files = [s.rfilename for s in getattr(info, "siblings", [])]
    print("files_sample:", files[:8])


def run_inference(model_id: str) -> None:
    texts = ["This product is useful and reliable.", "The delivery was late and the support was terrible."]
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id)
    model.eval()
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=128, return_tensors="pt")

    print("\n== Tokenizer output ==")
    print("input_ids shape:", tuple(encoded["input_ids"].shape))
    print("token_count:", [int(mask.sum()) for mask in encoded["attention_mask"]])

    start = time.perf_counter()
    with torch.no_grad():
        logits = model(**encoded).logits
        probs = torch.softmax(logits, dim=-1)
    latency_ms = (time.perf_counter() - start) * 1000

    print("\n== Manual inference ==")
    for text, prob in zip(texts, probs):
        label_id = int(torch.argmax(prob).item())
        print({"text": text, "label": model.config.id2label[label_id], "confidence": round(float(prob[label_id]), 4)})
    print("batch_latency_ms:", round(latency_ms, 2))

    clf = pipeline("text-classification", model=model, tokenizer=tokenizer, device=-1)
    print("\n== Pipeline inference ==")
    print(clf(texts))


if __name__ == "__main__":
    inspect_model(CARD_MODEL_ID)
    run_inference(INFER_MODEL_ID)
```

Goi y experiment:

- Doi `CARD_MODEL_ID=vinai/phobert-base-v2`.
- Doi `INFER_MODEL_ID` sang model sentiment khac.
- Doi `max_length` tu 64, 128, 256 va ghi lai latency.
- Doc model card va viet 5 dong risk note.

## Tu Kiem Tra

1. `AutoTokenizer` khac `AutoModel` o dau?
2. Khi nao nen dung `pipeline`, khi nao nen manual forward pass?
3. Vi sao can pin model revision?
4. Model card can check nhung thong tin nao truoc production?
5. Vi sao tokenizer la mot phan cua API contract?

## Checklist

- [ ] Chay duoc script load model/tokenizer tu HuggingFace.
- [ ] In duoc token count va label prediction.
- [ ] Doc duoc model card cua PhoBERT.
- [ ] Ghi lai license, intended use, limitation.
- [ ] Hieu trade-off `pipeline` vs manual inference.
- [ ] Biet risk cua `trust_remote_code`.

## Tai Lieu Tham Khao

- HuggingFace Transformers pipelines: https://huggingface.co/docs/transformers/main_classes/pipelines
- HuggingFace Trainer: https://huggingface.co/docs/transformers/main_classes/trainer
- HuggingFace Datasets load: https://huggingface.co/docs/datasets/loading
- HuggingFace Accelerate quicktour: https://huggingface.co/docs/accelerate/quicktour
- HuggingFace Model Cards: https://huggingface.co/docs/hub/model-cards
- PhoBERT model card: https://huggingface.co/vinai/phobert-base

---


# Day 16: Mini-project - Fine-tune PhoBERT/BERT Classifier

## Muc Tieu

- Build sentiment classifier tieng Viet end-to-end.
- Co baseline TF-IDF + Logistic Regression.
- Fine-tune PhoBERT/BERT bang HuggingFace Trainer.
- Compare baseline vs Transformer bang accuracy, macro F1, confusion matrix.
- Export model va expose inference API bang FastAPI.
- Giai thich production trade-off ve latency, memory, quality, drift va rollback.

## TL;DR

Day 16 la mini-project tong hop Phase 2. Cach lam dung khong phai nhay thang vao PhoBERT, ma bat dau bang baseline re, nhanh, explainable. Sau do fine-tune Transformer, compare bang metric va error analysis. Neu Transformer chi tot hon it nhung latency/cost cao hon nhieu, baseline co the la lua chon production v1 tot hon.

## 1. Problem Framing

Bai toan:

```text
Input: review/customer message tieng Viet
Output: sentiment label = negative | neutral | positive
```

Production output nen gom label va confidence:

```json
{
  "text": "san pham tot giao hang nhanh",
  "label": "positive",
  "confidence": 0.94,
  "model_version": "sentiment-phobert-v1",
  "latency_ms": 42
}
```

Can chot truoc:

- Label co may class?
- Neutral co can thiet khong?
- Text dai toi da bao nhieu token?
- Review co PII khong?
- Action sau prediction la gi: route ticket, dashboard, alert, auto-reply?
- Uu tien precision hay recall cho negative review?

## 2. Dataset Va Label Design

Dataset goi y:

- Shopee review sentiment.
- VLSP sentiment.
- Dataset noi bo customer support.
- Synthetic fallback cho hands-on.

Schema toi thieu:

```csv
text,label
"san pham tot giao hang nhanh",positive
"dong goi kem hang bi loi",negative
"tam duoc khong co gi dac biet",neutral
```

Label guideline phai ro nhu API contract. Neu annotator hieu khac nhau, model se hoc noise.

## 3. Baseline TF-IDF + Logistic Regression

Baseline la bat buoc vi:

- Train nhanh tren CPU.
- De debug feature/label.
- Latency thap.
- Giai thich duoc token nao quan trong.
- La regression test cho Transformer.

Map ve Senior SE: baseline nhu implementation don gian truoc khi introduce distributed cache. Neu baseline da dat business metric, dung baseline co the tot hon.

## 4. Fine-tune PhoBERT/BERT

Transformer classifier:

```text
text
  -> tokenizer
  -> input_ids, attention_mask
  -> BERT/PhoBERT encoder
  -> classification head
  -> logits
  -> softmax
  -> label
```

Hyperparameters v1:

- `max_length`: 128 cho review ngan.
- `learning_rate`: 2e-5.
- `epochs`: 2-4.
- `batch_size`: 8-16 tuy VRAM.
- `weight_decay`: 0.01.
- `metric`: macro F1 neu class imbalance.

PhoBERT note:

- Neu dung `vinai/phobert-base`, can kiem soat preprocessing tieng Viet nhat quan giua train va serve.
- Neu can setup don gian hon, benchmark `distilbert-base-multilingual-cased` hoac BERT multilingual.
- Khong deploy neu train preprocessing va serving preprocessing khac nhau.

## 5. Evaluation Va Error Analysis

Can report:

- Accuracy.
- Macro F1.
- Per-class precision/recall/F1.
- Confusion matrix.
- Top false negative negative review.
- Error theo do dai text.
- Error theo source/channel neu co.

Dung macro F1 vi neutral/negative thuong it hon positive. Accuracy cao co the che lap viec model fail class negative.

## 6. Serving Architecture

```text
FastAPI
  -> validate request
  -> normalize text
  -> tokenize
  -> model inference
  -> softmax
  -> response JSON
  -> log latency/model_version/input_length/confidence
```

Production API khong nen load model moi request. Load model luc startup, warmup, expose `/health`.

## Trade-offs

| Lua chon | Nen dung khi | Khong nen dung khi | Production note |
|---|---|---|---|
| TF-IDF + Logistic Regression | Can baseline nhanh, CPU, latency thap | Text co semantic phuc tap | Tot cho v1 neu metric du |
| PhoBERT | Task tieng Viet, can quality cao | Khong quan ly duoc preprocessing | Can benchmark latency |
| BERT multilingual | Multi-language, raw text don gian | Tieng Viet domain-specific | De van hanh hon PhoBERT segmentation |
| 3-class sentiment | Can neutral ro | Label neutral mo ho | Can guideline tot |
| Binary sentiment | Business chi can bad/good | Neutral quan trong | Don gian hon |
| `Trainer` | Standard fine-tune | Custom loss/training phuc tap | Ship nhanh |
| Full fine-tune | Dataset vua/lon, GPU co san | Data it, overfit | Can early stopping/eval |
| Freeze encoder | Data it, CPU/GPU yeu | Can quality cao | Train nhanh hon |

## Best Practices Tu Industry

1. Baseline-first va compare bang cung split.
2. Set seed, luu split, label mapping va model config.
3. Khong tune tren test set; dung validation de chon model.
4. Luu confusion matrix va classification report vao artifact.
5. Tach `train.py` va `serve.py`.
6. Pin model base va package version trong README/requirements.
7. Co model card noi bo: dataset, metric, limitation, intended use, owner.

## Performance Considerations

- TF-IDF baseline thuong sub-ms den vai ms/request tren CPU.
- PhoBERT/BERT base CPU co the 50-300ms/request tuy hardware va max_length.
- GPU giam latency khi batch/throughput cao, nhung cold start va cost tang.
- `max_length=128` thuong du cho review ngan; 512 lam memory attention tang manh.
- Batch inference tang throughput nhung phai can latency SLA.
- Quantization/ONNX co the giam latency cho CPU serving.

## Production Concerns

- PII trong review: khong log raw text neu khong can.
- Drift: slang, campaign, san pham moi lam distribution doi.
- Bias: model co the fail voi dialect/teencode.
- Rollback: luu baseline artifact va Transformer artifact rieng.
- Monitoring: label distribution, confidence distribution, p95 latency, error rate.
- Data quality: duplicate, label noise, spam review.
- Security: validate input length, rate limit, timeout.
- Compliance: license model/dataset phai hop voi commercial use.

## Ung Dung Thuc Te

- Auto-route negative review sang customer support.
- Dashboard sentiment theo product/category/time.
- Alert khi negative sentiment tang bat thuong sau release.
- Pre-filter ticket cho LLM customer support workflow.

## Hands-on Trong 60-90 Phut

```bash
pip install -U pandas numpy scikit-learn datasets transformers accelerate torch fastapi uvicorn
```

CPU cham thi dung model nho:

```powershell
$env:MODEL_ID="distilbert-base-multilingual-cased"
```

Co GPU/Colab va muon PhoBERT:

```powershell
$env:MODEL_ID="vinai/phobert-base"
```

### File 1: `train_sentiment.py`

```python
from __future__ import annotations

import json
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from datasets import Dataset, DatasetDict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, Trainer, TrainingArguments

SEED = 42
MODEL_ID = os.getenv("MODEL_ID", "vinai/phobert-base")
DATA_PATH = os.getenv("DATA_PATH", "")
OUT_DIR = Path(os.getenv("OUT_DIR", "artifacts/sentiment_classifier"))
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "128"))
EPOCHS = float(os.getenv("EPOCHS", "2"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))

LABELS = ["negative", "neutral", "positive"]
LABEL2ID = {label: i for i, label in enumerate(LABELS)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def sample_data() -> pd.DataFrame:
    rows = [
        ("san pham rat tot giao hang nhanh", "positive"),
        ("dong goi can than hang dung mo ta", "positive"),
        ("chat luong tot se mua lai", "positive"),
        ("shop ho tro nhanh va lich su", "positive"),
        ("hang bi loi khong dung mo ta", "negative"),
        ("dong goi te san pham bi vo", "negative"),
        ("giao hang qua cham", "negative"),
        ("chat luong kem rat that vong", "negative"),
        ("san pham tam duoc", "neutral"),
        ("binh thuong khong co gi dac biet", "neutral"),
        ("giao hang dung hen", "neutral"),
        ("moi dung nen chua danh gia", "neutral"),
    ]
    variants = []
    for text, label in rows:
        variants.append((text, label))
        variants.append((text + " lan 2", label))
        variants.append(("review: " + text, label))
    return pd.DataFrame(variants, columns=["text", "label"]).sample(frac=1, random_state=SEED).reset_index(drop=True)


def load_data() -> pd.DataFrame:
    if DATA_PATH and Path(DATA_PATH).exists():
        df = pd.read_csv(DATA_PATH)
        missing = {"text", "label"} - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        df = df[["text", "label"]].dropna()
    else:
        df = sample_data()
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    unknown = sorted(set(df["label"]) - set(LABELS))
    if unknown:
        raise ValueError(f"Unknown labels: {unknown}. Expected: {LABELS}")
    df["label_id"] = df["label"].map(LABEL2ID).astype(int)
    return df


def split_data(df: pd.DataFrame):
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=SEED, stratify=df["label_id"])
    train_df, val_df = train_test_split(train_df, test_size=0.25, random_state=SEED, stratify=train_df["label_id"])
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def train_baseline(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    baseline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=20000)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    baseline.fit(train_df["text"], train_df["label_id"])
    pred = baseline.predict(test_df["text"])
    report = {
        "accuracy": accuracy_score(test_df["label_id"], pred),
        "f1_macro": f1_score(test_df["label_id"], pred, average="macro"),
        "confusion_matrix": confusion_matrix(test_df["label_id"], pred).tolist(),
    }
    print("\n== Baseline TF-IDF + Logistic Regression ==")
    print(json.dumps(report, indent=2))
    print(classification_report(test_df["label_id"], pred, target_names=LABELS))
    return report


def build_dataset(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> DatasetDict:
    keep = ["text", "label_id"]
    return DatasetDict(
        {
            "train": Dataset.from_pandas(train_df[keep], preserve_index=False),
            "validation": Dataset.from_pandas(val_df[keep], preserve_index=False),
            "test": Dataset.from_pandas(test_df[keep], preserve_index=False),
        }
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {"accuracy": accuracy_score(labels, preds), "f1_macro": f1_score(labels, preds, average="macro")}


def fine_tune_transformer(train_df, val_df, test_df) -> dict:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    ds = build_dataset(train_df, val_df, test_df)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

    tokenized = ds.map(tokenize, batched=True)
    tokenized = tokenized.rename_column("label_id", "labels").remove_columns(["text"])

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    args = TrainingArguments(
        output_dir=str(OUT_DIR / "checkpoints"),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        weight_decay=0.01,
        logging_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        report_to="none",
        seed=SEED,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        processing_class=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )

    print("\n== Fine-tune Transformer ==")
    trainer.train()
    test_output = trainer.predict(tokenized["test"])
    preds = np.argmax(test_output.predictions, axis=-1)
    labels = test_output.label_ids

    report = {
        "model_id": MODEL_ID,
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "confusion_matrix": confusion_matrix(labels, preds).tolist(),
    }
    print(json.dumps(report, indent=2))
    print(classification_report(labels, preds, target_names=LABELS))

    model_dir = OUT_DIR / "best_model"
    model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_dir))
    tokenizer.save_pretrained(str(model_dir))
    (OUT_DIR / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT_DIR / "labels.json").write_text(json.dumps({"labels": LABELS, "label2id": LABEL2ID, "id2label": ID2LABEL}, indent=2), encoding="utf-8")
    return report


def main() -> None:
    set_seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    train_df, val_df, test_df = split_data(df)
    print("dataset_size:", len(df))
    print("train/val/test:", len(train_df), len(val_df), len(test_df))
    print("model_id:", MODEL_ID)
    summary = {"baseline": train_baseline(train_df, test_df), "transformer": fine_tune_transformer(train_df, val_df, test_df)}
    (OUT_DIR / "comparison.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n== Comparison ==")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
```

### File 2: `serve_sentiment.py`

```python
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_DIR = Path(os.getenv("MODEL_DIR", "artifacts/sentiment_classifier/best_model"))
LABEL_PATH = Path(os.getenv("LABEL_PATH", "artifacts/sentiment_classifier/labels.json"))
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "128"))

app = FastAPI(title="Vietnamese Sentiment Classifier")

tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
model.eval()

if LABEL_PATH.exists():
    labels = json.loads(LABEL_PATH.read_text(encoding="utf-8"))["labels"]
else:
    labels = [model.config.id2label[i] for i in range(model.config.num_labels)]


class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok", "model_dir": str(MODEL_DIR)}


@app.post("/predict")
def predict(req: PredictRequest):
    start = time.perf_counter()
    encoded = tokenizer(req.text, truncation=True, max_length=MAX_LENGTH, return_tensors="pt")
    with torch.no_grad():
        probs = torch.softmax(model(**encoded).logits, dim=-1)[0]
    pred_id = int(torch.argmax(probs).item())
    latency_ms = (time.perf_counter() - start) * 1000
    return {
        "label": labels[pred_id],
        "confidence": round(float(probs[pred_id]), 4),
        "probabilities": {labels[i]: round(float(probs[i]), 4) for i in range(len(labels))},
        "input_tokens": int(encoded["attention_mask"].sum().item()),
        "latency_ms": round(latency_ms, 2),
        "model_dir": str(MODEL_DIR),
    }
```

Chay:

```bash
python train_sentiment.py
uvicorn serve_sentiment:app --host 0.0.0.0 --port 8000
```

Test:

```bash
curl -X POST http://localhost:8000/predict ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"san pham tot giao hang nhanh\"}"
```

## README Outline

```markdown
# Vietnamese Sentiment Classifier

## Problem
Classify Vietnamese customer review into negative, neutral, positive.

## Dataset
- Source: Shopee/VLSP/internal CSV or synthetic fallback.
- Columns: text,label.
- Labels: negative, neutral, positive.

## Approach
1. Baseline: TF-IDF + Logistic Regression.
2. Transformer: PhoBERT/BERT fine-tuning.
3. Compare accuracy, macro F1, confusion matrix.

## Production Notes
- Pin base model and package versions.
- Keep tokenizer/preprocessing same in train and serve.
- Monitor label distribution, confidence, latency and drift.
- Do not log raw PII by default.
- Keep baseline model as fallback.
```

## Tu Kiem Tra

1. Vi sao phai co TF-IDF baseline truoc Transformer?
2. Macro F1 tot hon accuracy trong case nao?
3. Tokenizer mismatch giua training va serving gay loi gi?
4. Khi nao PhoBERT dang gia hon BERT multilingual?
5. API production can log nhung metric nao?

## Checklist

- [ ] Co dataset CSV hoac synthetic fallback.
- [ ] Train duoc TF-IDF baseline.
- [ ] Fine-tune duoc PhoBERT/BERT classifier.
- [ ] Co comparison baseline vs Transformer.
- [ ] Co confusion matrix va classification report.
- [ ] Save duoc model/tokenizer/label mapping.
- [ ] Chay duoc FastAPI `/predict`.
- [ ] Viet duoc production notes va limitation.

## Tai Lieu Tham Khao

- HuggingFace text classification guide: https://huggingface.co/docs/transformers/tasks/sequence_classification
- HuggingFace Trainer: https://huggingface.co/docs/transformers/main_classes/trainer
- HuggingFace Datasets: https://huggingface.co/docs/datasets/loading
- PhoBERT model card: https://huggingface.co/vinai/phobert-base
- HuggingFace Model Cards: https://huggingface.co/docs/hub/model-cards
- BERT paper: https://arxiv.org/abs/1810.04805
- PhoBERT paper: https://arxiv.org/abs/2003.00744

---


