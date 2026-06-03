# Day 10: PyTorch Fundamentals

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Tạo và debug `Tensor` bằng `shape`, `dtype`, `device`, `requires_grad`.
- Hiểu autograd ở mức đủ để viết training loop đúng: `forward -> loss -> backward -> optimizer.step`.
- Viết model bằng `nn.Module`, đặt computation trong `forward()` và dùng `state_dict` để lưu artifact.
- Tạo `Dataset` và `DataLoader` cho mini-batch training.
- Quản lý CPU/GPU device một cách nhất quán cho model, input, label và checkpoint.
- Rebuild MLP XOR của Day 9 bằng PyTorch, dùng `BCEWithLogitsLoss` thay vì tự viết backprop bằng NumPy.
- Biết khi nào PyTorch phù hợp production và cần thêm điều kiện gì.

## Cách Học Bài Này

1. Đọc [document.md](./document.md) để nắm mental model, API và trade-off.
2. Làm lần lượt [exercise.md](./exercise.md), đặc biệt bài rebuild MLP XOR.
3. So sánh code PyTorch với MLP NumPy ở Day 9: phần nào được framework xử lý, phần nào vẫn là trách nhiệm của engineer.
4. Tự trả lời checklist cuối bài trước khi sang Day 11.

## Bức Tranh Tổng Quan

PyTorch thay thế phần khó nhất của Day 9: bạn không còn tự tính đạo hàm và tự cập nhật từng weight bằng NumPy. Thay vào đó:

```text
Tensor + autograd  -> tự track phép toán và tính gradient
nn.Module          -> đóng gói architecture và parameters
Dataset/DataLoader -> đóng gói data access và mini-batch
Optimizer          -> cập nhật parameters từ gradient
state_dict         -> artifact có thể lưu, load, deploy
```

Nhưng PyTorch không tự giải quyết mọi vấn đề production. Bạn vẫn phải kiểm soát shape contract, dtype, device, preprocessing, seed, data split, metric, checkpoint, logging, monitoring và rollback.

## Best Solution Theo Context

Với bài Day 10, best solution là dùng PyTorch thuần, không dùng trainer framework. Lý do: mục tiêu là hiểu cơ chế nền tảng trước khi sang optimizer/scheduler ở Day 11 và Hugging Face ở các bài sau.

| Context | Lựa chọn nên dùng | Vì sao |
|---|---|---|
| Học backprop ở mức concept | NumPy như Day 9 | Thấy rõ phép toán và gradient |
| Training deep learning thật | PyTorch | Có autograd, GPU, module, optimizer, ecosystem |
| Model nhỏ, dev local | CPU fallback | Đơn giản, ít lỗi môi trường |
| Matrix compute lớn hoặc batch inference | GPU | Tận dụng parallel compute |
| Binary classification | `BCEWithLogitsLoss` | Ổn định số học hơn `sigmoid + BCELoss` |
| Inference/evaluation | `model.eval()` + `torch.inference_mode()` | Đúng behavior và giảm memory |

## Dùng Được Trong Production Không?

Có, PyTorch dùng được trong production cho cả training và inference. Tuy nhiên code demo trong bài chỉ là baseline học tập. Để dùng production, tối thiểu cần:

- Artifact rõ ràng: `state_dict`, config architecture, preprocessing config, label mapping, threshold và metric.
- Reproducibility: seed, package version, dataset snapshot, data split, training config.
- Validation: kiểm tra `shape`, `dtype`, missing value, range của feature và device mismatch.
- Runtime mode đúng: training dùng `model.train()`, evaluation/inference dùng `model.eval()` kèm `torch.no_grad()` hoặc `torch.inference_mode()`.
- Observability: log loss, metric, latency, error rate, prediction distribution, drift.
- Reliability: device fallback CPU/GPU, xử lý checkpoint lỗi, rollback model version, không load checkpoint từ nguồn không tin cậy.
- Performance test: benchmark p50/p95/p99 latency, throughput, VRAM/RAM, data loading bottleneck.

## Checklist Hoàn Thành

- [ ] Giải thích được `Tensor` khác NumPy array ở điểm nào.
- [ ] Biết vì sao `loss.backward()` tạo gradient và vì sao gradient bị accumulate.
- [ ] Biết vì sao cần `optimizer.zero_grad(set_to_none=True)` trước mỗi update.
- [ ] Viết được `nn.Module` có `__init__` và `forward`.
- [ ] Tạo được `Dataset`/`DataLoader` trả về batch `(features, labels)`.
- [ ] Chạy được MLP XOR bằng PyTorch với `BCEWithLogitsLoss`.
- [ ] Save/load được `state_dict`.
- [ ] Trả lời được production readiness của code mình viết.
