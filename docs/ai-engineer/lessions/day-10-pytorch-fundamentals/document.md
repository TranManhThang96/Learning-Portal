# Day 10 Document: PyTorch API Reference

File này là tài liệu tra cứu. Toàn bộ phần giải thích Tensor, autograd, `nn.Module`, `Dataset`/`DataLoader`, device, training loop, checkpoint và production trade-off nằm trong [lession.md](./lession.md).

## 1. Training Step Cheat Sheet

```python
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

`zero_grad(set_to_none=True)` đặt gradient về `None`; parameter không nhận gradient sẽ tiếp tục có `.grad is None`, giúp phát hiện graph bị đứt.

## 2. Evaluation Và Inference Cheat Sheet

```python
model.eval()
with torch.inference_mode():
    logits = model(xb)
    probabilities = torch.sigmoid(logits)
```

- `model.eval()` đổi behavior của module như Dropout và BatchNorm.
- `torch.inference_mode()` tắt autograd bookkeeping cho inference thuần.
- Hai cơ chế giải quyết hai việc khác nhau; thường cần dùng cùng nhau.

## 3. Binary Classification Contract

| Thành phần | Contract |
|---|---|
| Input | `float32`, shape `(batch_size, input_dim)` |
| Logits | `float32`, shape `(batch_size, 1)` |
| Target | `float32`, shape `(batch_size, 1)`, giá trị `0/1` |
| Loss | `nn.BCEWithLogitsLoss()` nhận raw logits |
| Probability | Chỉ gọi `torch.sigmoid(logits)` khi metric/inference cần |

`BCEWithLogitsLoss` kết hợp Sigmoid và BCE theo cách ổn định số học hơn `Sigmoid` rồi `BCELoss`.

## 4. Device Checklist

- Chọn device một lần ở startup.
- Move model lên device sau khi khởi tạo.
- Move theo batch trong loop, không move từng sample trong `Dataset`.
- Chỉ bật `pin_memory` khi đo được lợi ích trên CUDA workload.
- Đưa tensor về CPU trước khi convert sang NumPy: `.detach().cpu().numpy()`.
- Benchmark CPU/CUDA/MPS trên batch và hardware thật.

## 5. Checkpoint Pattern

```python
torch.save(
    {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "config": config,
        "metrics": metrics,
    },
    checkpoint_path,
)

checkpoint = torch.load(
    checkpoint_path,
    map_location=device,
    weights_only=True,
)
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()
```

Guardrail:

- Chỉ load checkpoint từ nguồn tin cậy.
- Giữ `weights_only=True` rõ ràng trong code.
- Nếu checkpoint chứa custom class/global không được allowlist, không tắt guardrail chỉ để hết lỗi; xác minh nguồn và format trước.
- Version architecture config, preprocessing, label mapping, threshold, package/runtime và schema cùng model.

## 6. Reproducibility Checklist

- Seed Python, NumPy, PyTorch và accelerator.
- Lưu dataset/split version và toàn bộ training config.
- Không hứa bit-for-bit reproducibility giữa mọi release, platform và CPU/GPU.
- Deterministic algorithms có thể chậm hơn; chọn theo yêu cầu debug/compliance.
- Chạy regression test khi nâng PyTorch, CUDA, driver hoặc hardware.

## 7. Nguồn Đã Xác Minh Bằng Context7

Đối chiếu ngày 8/6/2026 với tài liệu PyTorch 2.12:

- [Tensor autograd mechanics](https://docs.pytorch.org/docs/2.12/notes/autograd.html)
- [`torch.nn.Module`](https://docs.pytorch.org/docs/2.12/generated/torch.nn.Module.html)
- [`Dataset` và `DataLoader`](https://docs.pytorch.org/docs/2.12/data.html)
- [`BCEWithLogitsLoss`](https://docs.pytorch.org/docs/2.12/generated/torch.nn.BCEWithLogitsLoss.html)
- [`Optimizer.zero_grad`](https://docs.pytorch.org/docs/2.12/generated/torch.optim.Optimizer.zero_grad.html)
- [`torch.inference_mode`](https://docs.pytorch.org/docs/2.12/generated/torch.autograd.grad_mode.inference_mode.html)
- [Serialization semantics và `weights_only`](https://docs.pytorch.org/docs/2.12/notes/serialization.html)
- [Reproducibility](https://docs.pytorch.org/docs/2.12/notes/randomness.html)
- [CUDA availability](https://docs.pytorch.org/docs/2.12/generated/torch.cuda.is_available.html)
- [MPS backend](https://docs.pytorch.org/docs/2.12/notes/mps.html)

## 8. Ghi Chú Phiên Bản

Các API nền trong bài ổn định, nhưng checkpoint, compiler, accelerator và performance behavior có thể đổi theo release. Production nên pin phiên bản, lưu environment metadata và test load/inference trước khi rollout.
