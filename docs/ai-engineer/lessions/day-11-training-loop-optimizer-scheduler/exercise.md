# Exercise: Training Loop, Optimizer, Scheduler

## Mục tiêu thực hành

Bạn sẽ viết một training job PyTorch cho binary classifier trên synthetic dataset. Dataset synthetic giúp bài chạy offline, không cần download dữ liệu, nhưng training loop được tổ chức theo style gần production:

- Config bằng `dataclass`.
- Seed và device rõ ràng.
- `Dataset`/`DataLoader` riêng.
- Train/eval loop riêng.
- `model.train()`, `model.eval()`, `torch.inference_mode()`.
- `optimizer.zero_grad(set_to_none=True)`.
- `loss.backward()`, gradient clipping, `optimizer.step()`.
- `AdamW` optimizer.
- `ReduceLROnPlateau` scheduler.
- Optional mixed precision bằng `torch.amp`.
- Early stopping.
- Checkpoint best model.
- Metric logging theo JSON line.

## Setup

Cài PyTorch theo môi trường của bạn. Nếu đã có PyTorch thì bỏ qua bước này.

```bash
pip install torch
```

Chạy script có sẵn trong folder bài học:

```bash
python3 lessions/day-11-training-loop-optimizer-scheduler/day11_training_loop.py
```

Nếu có CUDA GPU, script tự dùng GPU. Nếu không có, script chạy CPU.

## Script mẫu hoàn chỉnh

Nội dung dưới đây giống file [day11_training_loop.py](./day11_training_loop.py), được đặt trong Markdown để bạn đọc và annotate dễ hơn.

```python
from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset, random_split


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 42
    n_samples: int = 12_000
    input_dim: int = 8
    hidden_dim: int = 64
    batch_size: int = 256
    epochs: int = 40
    lr: float = 3e-3
    weight_decay: float = 1e-2
    dropout: float = 0.15
    grad_clip_norm: float = 1.0
    early_stopping_patience: int = 5
    min_delta: float = 1e-4
    num_workers: int = 0
    use_amp: bool = True
    threshold: float = 0.5
    checkpoint_path: str = "artifacts/day11_best_checkpoint.pt"


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def select_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def log_event(event: str, payload: dict[str, Any]) -> None:
    record = {"event": event, **payload}
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))


class SyntheticTicketDataset(Dataset[tuple[Tensor, Tensor]]):
    """Synthetic binary classification data with non-linear signal.

    Features can be read as normalized ticket/review signals:
    length, sentiment cues, refund cue, urgency cue and noise columns.
    """

    def __init__(self, n_samples: int, input_dim: int, seed: int) -> None:
        if input_dim < 6:
            raise ValueError("input_dim must be at least 6")

        generator = torch.Generator().manual_seed(seed)
        features = torch.randn(n_samples, input_dim, generator=generator)

        raw_score = (
            1.4 * features[:, 0]
            - 1.1 * features[:, 1]
            + 0.9 * features[:, 2] * features[:, 3]
            + 0.7 * torch.relu(features[:, 4])
            - 0.6 * features[:, 5].abs()
            - 0.15
        )
        probs = torch.sigmoid(raw_score)
        labels = torch.bernoulli(probs, generator=generator).unsqueeze(1)

        self.features = features.float()
        self.labels = labels.float()

    def __len__(self) -> int:
        return self.features.shape[0]

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        return self.features[index], self.labels[index]


class BinaryClassifier(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, x: Tensor) -> Tensor:
        if x.ndim != 2:
            raise ValueError(f"Expected input shape (batch, features), got {tuple(x.shape)}")
        return self.net(x)


def seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % 2**32
    random.seed(worker_seed)


def build_loaders(cfg: TrainConfig, device: torch.device) -> tuple[DataLoader, DataLoader, DataLoader]:
    dataset = SyntheticTicketDataset(
        n_samples=cfg.n_samples,
        input_dim=cfg.input_dim,
        seed=cfg.seed,
    )

    n_train = int(0.70 * len(dataset))
    n_val = int(0.15 * len(dataset))
    n_test = len(dataset) - n_train - n_val
    split_generator = torch.Generator().manual_seed(cfg.seed)
    train_ds, val_ds, test_ds = random_split(
        dataset,
        [n_train, n_val, n_test],
        generator=split_generator,
    )

    pin_memory = device.type == "cuda"
    common = {
        "batch_size": cfg.batch_size,
        "num_workers": cfg.num_workers,
        "pin_memory": pin_memory,
        "persistent_workers": cfg.num_workers > 0,
        "worker_init_fn": seed_worker if cfg.num_workers > 0 else None,
    }

    train_loader = DataLoader(
        train_ds,
        shuffle=True,
        generator=torch.Generator().manual_seed(cfg.seed),
        **common,
    )
    val_loader = DataLoader(val_ds, shuffle=False, **common)
    test_loader = DataLoader(test_ds, shuffle=False, **common)
    return train_loader, val_loader, test_loader


def binary_metrics(logits: Tensor, targets: Tensor, threshold: float) -> dict[str, float]:
    probs = torch.sigmoid(logits)
    preds = (probs >= threshold).int()
    y_true = targets.int()

    tp = int(((preds == 1) & (y_true == 1)).sum().item())
    tn = int(((preds == 0) & (y_true == 0)).sum().item())
    fp = int(((preds == 1) & (y_true == 0)).sum().item())
    fn = int(((preds == 0) & (y_true == 1)).sum().item())

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def current_lr(optimizer: torch.optim.Optimizer) -> float:
    return float(optimizer.param_groups[0]["lr"])


def resolve_output_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent / path


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    scaler: torch.amp.GradScaler,
    device: torch.device,
    cfg: TrainConfig,
) -> tuple[float, dict[str, float]]:
    model.train()
    amp_enabled = cfg.use_amp and device.type == "cuda"
    total_loss = 0.0
    total_examples = 0
    grad_norms: list[float] = []
    all_logits: list[Tensor] = []
    all_targets: list[Tensor] = []

    for xb, yb in loader:
        xb = xb.to(device, non_blocking=True)
        yb = yb.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast(
            device_type=device.type,
            dtype=torch.float16,
            enabled=amp_enabled,
        ):
            logits = model(xb)
            loss = loss_fn(logits, yb)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            max_norm=cfg.grad_clip_norm,
        )
        scaler.step(optimizer)
        scaler.update()

        batch_size = xb.shape[0]
        total_loss += float(loss.detach().item()) * batch_size
        total_examples += batch_size
        grad_norms.append(float(grad_norm.detach().cpu().item()))
        all_logits.append(logits.detach().cpu())
        all_targets.append(yb.detach().cpu())

    metrics = binary_metrics(
        torch.cat(all_logits),
        torch.cat(all_targets),
        threshold=cfg.threshold,
    )
    metrics["grad_norm"] = sum(grad_norms) / max(len(grad_norms), 1)
    return total_loss / max(total_examples, 1), metrics


@torch.inference_mode()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    device: torch.device,
    cfg: TrainConfig,
) -> tuple[float, dict[str, float]]:
    model.eval()
    total_loss = 0.0
    total_examples = 0
    all_logits: list[Tensor] = []
    all_targets: list[Tensor] = []

    for xb, yb in loader:
        xb = xb.to(device, non_blocking=True)
        yb = yb.to(device, non_blocking=True)

        logits = model(xb)
        loss = loss_fn(logits, yb)

        batch_size = xb.shape[0]
        total_loss += float(loss.item()) * batch_size
        total_examples += batch_size
        all_logits.append(logits.cpu())
        all_targets.append(yb.cpu())

    metrics = binary_metrics(
        torch.cat(all_logits),
        torch.cat(all_targets),
        threshold=cfg.threshold,
    )
    return total_loss / max(total_examples, 1), metrics


def save_checkpoint(
    path: Path,
    epoch: int,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler.ReduceLROnPlateau,
    scaler: torch.amp.GradScaler,
    cfg: TrainConfig,
    best_val_loss: float,
    val_metrics: dict[str, float],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "scaler_state_dict": scaler.state_dict(),
            "config": asdict(cfg),
            "best_val_loss": best_val_loss,
            "val_metrics": val_metrics,
        },
        path,
    )
    path.with_suffix(".config.json").write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    cfg = TrainConfig()
    seed_everything(cfg.seed)
    device = select_device()
    checkpoint_path = resolve_output_path(cfg.checkpoint_path)

    train_loader, val_loader, test_loader = build_loaders(cfg, device)
    model = BinaryClassifier(
        input_dim=cfg.input_dim,
        hidden_dim=cfg.hidden_dim,
        dropout=cfg.dropout,
    ).to(device)

    loss_fn = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.lr,
        weight_decay=cfg.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=2,
    )

    amp_enabled = cfg.use_amp and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    log_event(
        "run_started",
        {
            "device": str(device),
            "amp_enabled": amp_enabled,
            "config": asdict(cfg),
            "train_batches": len(train_loader),
            "val_batches": len(val_loader),
        },
    )

    best_val_loss = float("inf")
    stale_epochs = 0

    for epoch in range(1, cfg.epochs + 1):
        started = time.perf_counter()
        train_loss, train_metrics = train_one_epoch(
            model=model,
            loader=train_loader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            scaler=scaler,
            device=device,
            cfg=cfg,
        )
        val_loss, val_metrics = evaluate(
            model=model,
            loader=val_loader,
            loss_fn=loss_fn,
            device=device,
            cfg=cfg,
        )

        scheduler.step(val_loss)
        improved = val_loss < best_val_loss - cfg.min_delta
        if improved:
            best_val_loss = val_loss
            stale_epochs = 0
            save_checkpoint(
                path=checkpoint_path,
                epoch=epoch,
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                scaler=scaler,
                cfg=cfg,
                best_val_loss=best_val_loss,
                val_metrics=val_metrics,
            )
        else:
            stale_epochs += 1

        log_event(
            "epoch_finished",
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "val_loss": round(val_loss, 6),
                "train_f1": round(train_metrics["f1"], 6),
                "val_f1": round(val_metrics["f1"], 6),
                "val_precision": round(val_metrics["precision"], 6),
                "val_recall": round(val_metrics["recall"], 6),
                "lr": current_lr(optimizer),
                "grad_norm": round(train_metrics["grad_norm"], 6),
                "seconds": round(time.perf_counter() - started, 3),
                "best_val_loss": round(best_val_loss, 6),
                "stale_epochs": stale_epochs,
                "checkpoint_saved": improved,
            },
        )

        if stale_epochs >= cfg.early_stopping_patience:
            log_event(
                "early_stopping",
                {
                    "epoch": epoch,
                    "best_val_loss": round(best_val_loss, 6),
                    "patience": cfg.early_stopping_patience,
                },
            )
            break

    if not checkpoint_path.exists():
        raise RuntimeError("No checkpoint was saved. Check validation loop and config.")

    # Full training checkpoints should only be loaded from trusted storage.
    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_metrics = evaluate(
        model=model,
        loader=test_loader,
        loss_fn=loss_fn,
        device=device,
        cfg=cfg,
    )
    log_event(
        "test_finished",
        {
            "checkpoint_epoch": int(checkpoint["epoch"]),
            "test_loss": round(test_loss, 6),
            "test_metrics": {k: round(v, 6) for k, v in test_metrics.items()},
            "best_val_loss": round(float(checkpoint["best_val_loss"]), 6),
        },
    )


if __name__ == "__main__":
    main()
```

## Kết quả kỳ vọng

Bạn sẽ thấy log dạng JSON line:

```json
{"event": "epoch_finished", "epoch": 1, "train_loss": 0.657812, "val_loss": 0.617493, "val_f1": 0.701234, "lr": 0.003, "checkpoint_saved": true}
```

Metric cụ thể có thể khác theo hardware và version PyTorch, nhưng xu hướng hợp lý là:

- Train loss giảm qua nhiều epoch.
- Validation loss giảm rồi chững lại.
- Scheduler có thể giảm learning rate nếu validation loss plateau.
- Early stopping có thể dừng trước `epochs`.
- File checkpoint được tạo ở `lessions/day-11-training-loop-optimizer-scheduler/artifacts/day11_best_checkpoint.pt` nếu chạy từ repo root.

## Bài tập 1: Chạy baseline và đọc log

Chạy script với config mặc định.

Ghi lại:

| Câu hỏi | Câu trả lời của bạn |
|---|---|
| Epoch nào có best validation loss? | |
| Validation F1 tốt nhất là bao nhiêu? | |
| Learning rate có giảm không? Nếu có ở epoch nào? | |
| Early stopping có chạy không? | |
| Test F1 cuối cùng là bao nhiêu? | |

Giải thích ngắn: vì sao không dùng test set để quyết định checkpoint tốt nhất?

## Bài tập 2: Thử learning rate

Chạy 3 cấu hình:

| Run | `lr` | Quan sát |
|---|---:|---|
| A | `3e-4` | |
| B | `3e-3` | |
| C | `3e-2` | |

Câu hỏi:

1. Run nào converge nhanh nhất?
2. Run nào validation loss dao động mạnh nhất?
3. Nếu loss thành NaN hoặc metric tệ, bạn debug theo thứ tự nào?

## Bài tập 3: Thử batch size

Chạy 3 cấu hình:

| Run | `batch_size` | Quan sát throughput và metric |
|---|---:|---|
| A | `64` | |
| B | `256` | |
| C | `1024` | |

Câu hỏi:

1. Batch size lớn có luôn tốt hơn không?
2. Nếu tăng batch size làm validation F1 giảm, bạn thử điều chỉnh gì?
3. Trên GPU, bạn quan sát memory và utilization bằng công cụ nào?

## Bài tập 4: Thử regularization

Thử các giá trị:

| Run | `dropout` | `weight_decay` | Quan sát |
|---|---:|---:|---|
| A | `0.0` | `0.0` | |
| B | `0.15` | `1e-2` | |
| C | `0.5` | `1e-1` | |

Câu hỏi:

1. Run nào có dấu hiệu overfit?
2. Run nào có dấu hiệu underfit?
3. Vì sao dropout quá cao có thể làm model học chậm?

## Bài tập 5: Tắt từng optimization để debug

Thử lần lượt:

1. `use_amp=False`.
2. `grad_clip_norm=10.0`.
3. `early_stopping_patience=20`.
4. Scheduler `patience=5` thay vì `2`.

Ghi lại ảnh hưởng đến:

- Stability.
- Thời gian chạy.
- Validation F1.
- Số epoch trước khi dừng.

Mục tiêu không phải tìm con số đẹp nhất. Mục tiêu là hiểu mỗi cơ chế ảnh hưởng thế nào đến training behavior.

## Bài tập 6: Production review

Trả lời các câu hỏi sau như một review trước khi đưa training job vào production:

1. Dataset thật sẽ được version bằng gì?
2. Split train/validation/test cần theo random, user hay time? Vì sao?
3. Metric business chính là precision, recall, F1 hay PR-AUC?
4. Threshold có nên giữ `0.5` không?
5. Checkpoint cần lưu ở local disk, object storage hay model registry?
6. Log hiện tại có đủ để debug loss spike không?
7. Có rủi ro log PII không?
8. Nếu job bị kill giữa chừng, cần resume từ đâu?
9. Nếu model mới tệ hơn production model hiện tại, rollback thế nào?
10. Dùng được trong production không? Nếu có thì cần thêm điều kiện gì?

## Gợi ý lời giải production readiness

Training job này có thể làm nền cho production vì đã có seed, config, train/validation/test split, checkpoint best model, metric logging, scheduler, gradient clipping và early stopping.

Nhưng để dùng production thật, cần bổ sung:

- Dataset version và schema validation.
- Data quality check, leakage check và class distribution report.
- Experiment tracking hoặc structured logs được thu thập tập trung.
- Artifact storage đáng tin cậy thay vì chỉ local `artifacts/`.
- Unit test cho dataset, metric, checkpoint load và shape contract.
- Threshold tuning theo validation set và business cost.
- Package lockfile, Docker image hoặc environment reproducible.
- Alert khi loss NaN, validation metric tụt mạnh hoặc training cost vượt budget.
- Quy trình approval trước khi promote model sang inference service.

## Câu hỏi tự kiểm tra

1. Vì sao `optimizer.zero_grad(set_to_none=True)` nên gọi trước batch mới?
2. `model.eval()` khác gì với `torch.no_grad()`?
3. Với `ReduceLROnPlateau`, vì sao cần gọi `scheduler.step(val_loss)` thay vì `scheduler.step()`?
4. Nếu dùng AMP và gradient clipping, vì sao cần `scaler.unscale_(optimizer)` trước `clip_grad_norm_`?
5. Checkpoint để resume training khác gì checkpoint chỉ để inference?
6. Vì sao không nên chọn model theo test metric?
7. Khi validation loss tăng nhưng train loss giảm, bạn nghĩ đến những nguyên nhân nào?
8. Khi GPU utilization thấp, bạn kiểm tra `DataLoader` như thế nào?

## Checklist hoàn thành exercise

- [ ] Chạy được script trên CPU hoặc CUDA.
- [ ] Có log `run_started`, `epoch_finished`, `early_stopping` nếu xảy ra và `test_finished`.
- [ ] Có checkpoint tại `lessions/day-11-training-loop-optimizer-scheduler/artifacts/day11_best_checkpoint.pt` nếu chạy từ repo root.
- [ ] Thay đổi learning rate và giải thích được khác biệt.
- [ ] Thay đổi batch size và giải thích được trade-off performance.
- [ ] Thay đổi dropout/weight decay và nhận diện overfit/underfit.
- [ ] Tắt AMP để debug và hiểu khi nào nên bật lại.
- [ ] Viết được production review ngắn cho training job.
