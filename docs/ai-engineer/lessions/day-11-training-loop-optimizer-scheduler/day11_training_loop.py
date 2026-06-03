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
    scaler = torch.amp.GradScaler(device="cuda", enabled=amp_enabled)

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
