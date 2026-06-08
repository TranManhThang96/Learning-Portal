# Bài Tập Thực Hành: PyTorch Fundamentals

## Chuẩn Bị

Cài PyTorch theo môi trường của bạn. Với máy CPU/dev local, cách tối thiểu thường là:

```bash
python3 -m pip install torch numpy
```

Kiểm tra:

```bash
python3 - <<'PY'
import torch
print(torch.__version__)
print("cuda:", torch.cuda.is_available())
PY
```

Nếu dùng CUDA, hãy cài theo hướng dẫn chính thức phù hợp driver/CUDA runtime của máy. Không hard-code `"cuda"` trong code production; luôn có fallback.

## Bài 1: Inspect Tensor

Mục tiêu: quen với `shape`, `dtype`, `device`, `requires_grad`.

```python
import torch

x = torch.tensor([[0.0, 1.0], [1.0, 0.0]], dtype=torch.float32)
w = torch.randn((2, 1), dtype=torch.float32, requires_grad=True)

print("x:", x)
print("x.shape:", x.shape)
print("x.dtype:", x.dtype)
print("x.device:", x.device)
print("w.requires_grad:", w.requires_grad)
```

Việc cần làm:

1. Đổi `dtype` của `x` sang `torch.float64` và quan sát output.
2. Nếu máy có GPU, move `x` sang CUDA bằng `.to("cuda")`.
3. Tạo lỗi device mismatch bằng cách để `x` ở CPU nhưng `w` ở CUDA, sau đó sửa lại.

## Bài 2: Autograd Tối Giản

Mục tiêu: hiểu `loss.backward()` và gradient accumulation.

```python
import torch

w = torch.tensor([2.0], requires_grad=True)
x = torch.tensor([3.0])
target = torch.tensor([10.0])

for step in range(3):
    y = w * x
    loss = (y - target).pow(2).mean()
    loss.backward()
    print(step, "loss=", loss.item(), "grad=", w.grad.item())
```

Bạn sẽ thấy gradient bị cộng dồn. Sửa loop bằng cách thêm:

```python
w.grad = None
```

trước mỗi `loss.backward()`. Khi dùng optimizer, cách chuẩn là:

```python
optimizer.zero_grad(set_to_none=True)
```

## Bài 3: Rebuild MLP XOR Từ Day 9 Bằng PyTorch

Tạo file `train_xor_pytorch.py` nếu muốn chạy riêng. Code dưới đây cố tình có cấu trúc gần production hơn toy script: có config, seed, device fallback, train/eval mode, `DataLoader`, `BCEWithLogitsLoss`, `state_dict` và checkpoint.

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import random

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 42
    train_repeats: int = 512
    val_repeats: int = 128
    noise_std: float = 0.04
    hidden_dim: int = 8
    batch_size: int = 32
    epochs: int = 250
    learning_rate: float = 0.03
    weight_decay: float = 1e-4
    checkpoint_path: str = "artifacts/xor_mlp.pt"


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    # Determinism giúp demo dễ lặp lại hơn, nhưng có thể giảm performance.
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def select_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class XORDataset(Dataset):
    def __init__(self, repeats: int, noise_std: float, seed: int) -> None:
        base_x = torch.tensor(
            [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]],
            dtype=torch.float32,
        )
        base_y = torch.tensor([[0.0], [1.0], [1.0], [0.0]], dtype=torch.float32)

        self.features = base_x.repeat((repeats, 1))
        self.labels = base_y.repeat((repeats, 1))

        if noise_std > 0:
            generator = torch.Generator().manual_seed(seed)
            noise = torch.randn(self.features.shape, generator=generator) * noise_std
            self.features = torch.clamp(self.features + noise, 0.0, 1.0)

        if self.features.shape[0] != self.labels.shape[0]:
            raise ValueError("features and labels must have the same number of rows")

    def __len__(self) -> int:
        return self.features.shape[0]

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.features[idx], self.labels[idx]


class XORMLP(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(2, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 2 or x.shape[1] != 2:
            raise ValueError(f"Expected input shape (batch, 2), got {tuple(x.shape)}")
        return self.net(x)


def binary_accuracy_from_logits(logits: torch.Tensor, targets: torch.Tensor) -> float:
    probs = torch.sigmoid(logits)
    preds = (probs >= 0.5).to(dtype=targets.dtype)
    return (preds == targets).float().mean().item()


def move_batch(
    batch: tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    features, labels = batch
    non_blocking = device.type == "cuda"
    return (
        features.to(device, non_blocking=non_blocking),
        labels.to(device, non_blocking=non_blocking),
    )


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> dict[str, float]:
    model.train()

    total_loss = 0.0
    total_accuracy = 0.0
    total_rows = 0

    for batch in loader:
        xb, yb = move_batch(batch, device)

        optimizer.zero_grad(set_to_none=True)
        logits = model(xb)
        loss = loss_fn(logits, yb)
        loss.backward()
        optimizer.step()

        batch_size = xb.shape[0]
        total_loss += loss.item() * batch_size
        total_accuracy += binary_accuracy_from_logits(logits.detach(), yb) * batch_size
        total_rows += batch_size

    return {
        "loss": total_loss / total_rows,
        "accuracy": total_accuracy / total_rows,
    }


@torch.inference_mode()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    device: torch.device,
) -> dict[str, float]:
    model.eval()

    total_loss = 0.0
    total_accuracy = 0.0
    total_rows = 0

    for batch in loader:
        xb, yb = move_batch(batch, device)
        logits = model(xb)
        loss = loss_fn(logits, yb)

        batch_size = xb.shape[0]
        total_loss += loss.item() * batch_size
        total_accuracy += binary_accuracy_from_logits(logits, yb) * batch_size
        total_rows += batch_size

    return {
        "loss": total_loss / total_rows,
        "accuracy": total_accuracy / total_rows,
    }


@torch.inference_mode()
def predict_clean_xor(model: nn.Module, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    clean_x = torch.tensor(
        [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]],
        dtype=torch.float32,
        device=device,
    )
    logits = model(clean_x)
    probs = torch.sigmoid(logits)
    preds = (probs >= 0.5).to(torch.int64)
    return probs.cpu(), preds.cpu()


def make_loaders(config: TrainConfig, device: torch.device) -> tuple[DataLoader, DataLoader]:
    train_dataset = XORDataset(
        repeats=config.train_repeats,
        noise_std=config.noise_std,
        seed=config.seed,
    )
    val_dataset = XORDataset(
        repeats=config.val_repeats,
        noise_std=config.noise_std,
        seed=config.seed + 1,
    )

    pin_memory = device.type == "cuda"
    loader_generator = torch.Generator().manual_seed(config.seed)

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=pin_memory,
        generator=loader_generator,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=pin_memory,
    )
    return train_loader, val_loader


def save_checkpoint(
    config: TrainConfig,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    metrics: dict[str, float],
) -> None:
    path = Path(config.checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "config": asdict(config),
            "metrics": metrics,
        },
        path,
    )


def load_model_for_inference(path: str, device: torch.device) -> XORMLP:
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    model_config = checkpoint["config"]
    model = XORMLP(hidden_dim=model_config["hidden_dim"]).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def main() -> None:
    config = TrainConfig()
    set_seed(config.seed)
    device = select_device()
    print("device:", device)

    train_loader, val_loader = make_loaders(config, device)
    model = XORMLP(hidden_dim=config.hidden_dim).to(device)
    loss_fn = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    best_val_accuracy = 0.0
    best_metrics: dict[str, float] = {}

    for epoch in range(1, config.epochs + 1):
        train_metrics = train_one_epoch(model, train_loader, loss_fn, optimizer, device)
        val_metrics = evaluate(model, val_loader, loss_fn, device)

        if val_metrics["accuracy"] >= best_val_accuracy:
            best_val_accuracy = val_metrics["accuracy"]
            best_metrics = {
                "epoch": float(epoch),
                "train_loss": train_metrics["loss"],
                "train_accuracy": train_metrics["accuracy"],
                "val_loss": val_metrics["loss"],
                "val_accuracy": val_metrics["accuracy"],
            }
            save_checkpoint(config, model, optimizer, best_metrics)

        if epoch == 1 or epoch % 25 == 0:
            print(
                f"epoch={epoch:03d} "
                f"train_loss={train_metrics['loss']:.4f} "
                f"train_acc={train_metrics['accuracy']:.3f} "
                f"val_loss={val_metrics['loss']:.4f} "
                f"val_acc={val_metrics['accuracy']:.3f}"
            )

    print("best_metrics:", best_metrics)

    loaded_model = load_model_for_inference(config.checkpoint_path, device)
    probs, preds = predict_clean_xor(loaded_model, device)

    print("Clean XOR probabilities:")
    print(torch.round(probs * 10000) / 10000)
    print("Clean XOR predictions:")
    print(preds)
    print("Expected:")
    print(torch.tensor([[0], [1], [1], [0]], dtype=torch.int64))


if __name__ == "__main__":
    main()
```

Kỳ vọng:

- Loss giảm dần sau vài chục epoch.
- Validation accuracy thường đạt gần `1.0`.
- Clean XOR predictions là `[[0], [1], [1], [0]]`.
- Checkpoint nằm ở `artifacts/xor_mlp.pt`.

Train và validation được sinh bằng hai random seed khác nhau để noise không bị dùng lại. Tuy vậy, XOR vẫn là dataset tổng hợp rất nhỏ; validation accuracy ở đây chỉ kiểm tra training loop, không phải bằng chứng model generalize cho bài toán production.

Nếu model không học:

- Kiểm tra `BCEWithLogitsLoss` đang nhận logits, không nhận probability đã sigmoid.
- Kiểm tra label là `float32` và shape `(batch, 1)`.
- Thử tăng `hidden_dim` lên 16.
- Thử giảm `noise_std` về 0.0.
- Kiểm tra learning rate quá lớn khiến loss dao động.

## Bài 4: So Sánh Với NumPy Day 9

Điền bảng sau sau khi chạy hai phiên bản:

| Câu hỏi | NumPy Day 9 | PyTorch Day 10 |
|---|---|---|
| Weight nằm ở đâu? | | |
| Ai tính gradient? | | |
| Code update weight nằm ở đâu? | | |
| Có GPU dễ không? | | |
| Save/load artifact thế nào? | | |
| Lỗi shape dễ phát hiện ở đâu? | | |

Gợi ý trả lời:

- NumPy giúp thấy rõ math nhưng bạn tự chịu trách nhiệm gradient.
- PyTorch ngắn hơn ở phần gradient/update nhưng vẫn cần bạn kiểm soát data contract.
- PyTorch không loại bỏ nhu cầu test, logging, validation và monitoring.

## Bài 5: Thay Đổi Có Kiểm Soát

Chạy lại script với từng thay đổi, mỗi lần chỉ đổi một biến:

1. `hidden_dim`: 2, 4, 8, 16.
2. `learning_rate`: 0.003, 0.03, 0.3.
3. `batch_size`: 4, 32, 128.
4. `noise_std`: 0.0, 0.04, 0.15.
5. Device: CPU vs CUDA nếu có GPU.

Ghi lại:

- Loss cuối cùng.
- Validation accuracy tốt nhất.
- Clean XOR predictions.
- Thời gian chạy tương đối.
- Có lỗi memory/device/dtype/shape không.

## Bài 6: Checklist Production Readiness

Trả lời trước khi coi code là gần production:

- Input contract đã rõ `shape`, `dtype`, range chưa?
- Train/validation/test split có deterministic và không leakage không?
- Có seed và config lưu cùng checkpoint không?
- Checkpoint có `state_dict`, config và metrics không?
- Inference có `model.eval()` và `torch.inference_mode()` không?
- Có CPU/GPU fallback không?
- Có logging metric theo epoch không?
- Có benchmark latency/throughput không?
- Có kiểm soát nguồn checkpoint khi load không?
- Có version preprocessing và threshold không?

Kết luận: script trong bài dùng tốt cho học tập, prototype và baseline nhỏ. Để vào production, cần bổ sung test tự động, data validation, config file, experiment tracking, model registry, serving API, monitoring và rollback.
