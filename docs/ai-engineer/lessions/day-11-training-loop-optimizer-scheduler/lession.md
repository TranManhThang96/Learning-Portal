# Day 11: Training Loop, Optimizer, Scheduler

## Mục tiêu của ngày học

Sau bài này, bạn cần làm được 8 việc:

1. Viết được training loop PyTorch đúng thứ tự: load batch, forward, loss, `zero_grad`, `backward`, gradient clipping, `optimizer.step`, scheduler.
2. Tách rõ train loop, validation loop và test loop bằng `model.train()`, `model.eval()` và `torch.no_grad()` hoặc `torch.inference_mode()`.
3. Giải thích được vai trò của optimizer, learning rate, weight decay và scheduler.
4. Biết khi nào chọn SGD, Adam, AdamW, `ReduceLROnPlateau`, `OneCycleLR`, warmup hoặc cosine decay.
5. Thêm được early stopping, checkpoint best model và resume metadata.
6. Log được loss, metric, learning rate, gradient norm, epoch time và config.
7. Hiểu performance trade-off của batch size, `num_workers`, `pin_memory`, mixed precision và checkpoint IO.
8. Trả lời được: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## Bài này nối logic từ Day 9 và Day 10 như thế nào?

Day 9 giúp bạn thấy neural network từ bên trong: forward pass, loss, gradient và manual update bằng NumPy. Day 10 thay phần manual bằng PyTorch primitive: `Tensor`, autograd, `nn.Module`, `Dataset`, `DataLoader` và device management.

Day 11 là bước tiếp theo: biến các primitive đó thành một training job có thể kiểm soát được. Đây là phần khác biệt giữa "chạy được một notebook" và "có một pipeline training có thể debug, repeat, rollback và tối ưu chi phí".

```text
Day 9  -> hiểu toán và gradient
Day 10 -> dùng PyTorch primitive đúng cách
Day 11 -> tổ chức training job gần production
Day 16 -> fine-tune PhoBERT/BERT classifier
```

## Cách học đề xuất trong 2.5-3 giờ

| Thời lượng | Việc cần làm | Output |
|---:|---|---|
| 15 phút | Đọc TL;DR, mental model và anatomy của training loop trong file này | Nắm được thứ tự một training step |
| 45 phút | Đọc [document.md](./document.md) phần optimizer, scheduler và regularization | Chọn được AdamW/SGD và scheduler theo context |
| 40 phút | Đọc phần checkpoint, logging, reproducibility và performance | Biết training job cần log và lưu gì |
| 60 phút | Làm [exercise.md](./exercise.md), chạy script mẫu và thay đổi hyperparameter | Có một training run có validation, early stopping và checkpoint |
| 10 phút | Tự review bằng checklist cuối bài | Biết còn thiếu gì trước khi sang NLP/Transformer |

## TL;DR

Training loop là runtime engine của deep learning. Một batch đi qua model, model tạo prediction, loss đo sai số, autograd tính gradient, optimizer cập nhật weights. Scheduler điều chỉnh learning rate theo thời gian hoặc theo validation metric.

Loop tối thiểu:

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

Loop gần production cần thêm:

- Seed, config, device và dataset split có thể tái lập.
- `Dataset`/`DataLoader` tách khỏi model.
- Train/eval mode đúng.
- Validation metric để chọn checkpoint tốt nhất.
- Gradient clipping để giảm rủi ro exploding gradient.
- Scheduler để kiểm soát learning rate.
- Early stopping để tiết kiệm compute và giảm overfitting.
- Logging đủ để debug loss spike, NaN, learning rate và thời gian chạy.
- Checkpoint có model state, optimizer state, scheduler state, scaler state nếu dùng mixed precision, config và metric.

## Mental model cho Senior SE

| Deep learning training | Cách nhìn của Senior SE |
|---|---|
| Training script | Batch job có state, retry, artifact và logging |
| Epoch | Một lần quét qua toàn bộ training set |
| Batch | Page/chunk trong data processing |
| Forward pass | Request đi qua business logic của model |
| Loss | Objective kỹ thuật cần minimize |
| Metric | Acceptance criteria theo business use case |
| Backward pass | Tín hiệu feedback cho từng parameter |
| Optimizer | Policy cập nhật state |
| Scheduler | Policy thay đổi config runtime theo thời gian |
| Validation loop | Staging acceptance test |
| Checkpoint | Artifact có thể rollback hoặc resume |
| Early stopping | Circuit breaker cho training job |

Điểm quan trọng: training loop không chỉ là code tính toán. Nó là một workflow có dữ liệu, artifact, config, metric, chi phí, khả năng reproduce và khả năng rollback.

## Anatomy chuẩn của một epoch

```text
for epoch:
  model.train()
  for train batch:
    move batch to device
    optimizer.zero_grad()
    forward
    loss
    backward
    clip gradient if needed
    optimizer.step()

  model.eval()
  with no_grad or inference_mode:
    for validation batch:
      forward
      loss
      metric

  scheduler.step(...)
  save best checkpoint if validation improves
  early stop if validation stops improving
```

Các điểm dễ sai:

- Quên `optimizer.zero_grad()` làm gradient cộng dồn qua batch ngoài ý muốn.
- Quên `model.eval()` làm Dropout/BatchNorm hoạt động sai khi validation.
- Quên `torch.no_grad()` hoặc `torch.inference_mode()` làm tốn memory trong validation.
- Gọi scheduler sai thời điểm, đặc biệt `ReduceLROnPlateau` cần validation loss.
- Save checkpoint cuối epoch thay vì checkpoint tốt nhất theo validation metric.
- Chỉ log train loss, không log validation metric nên không biết overfitting.

## Best solution theo context

| Context | Lựa chọn nên bắt đầu | Lý do |
|---|---|---|
| Học training loop nền tảng | PyTorch loop tự viết | Thấy rõ thứ tự operation và dễ debug |
| Binary classifier nhỏ | `BCEWithLogitsLoss` + AdamW | Ổn định số học và ít tuning hơn SGD |
| Fine-tune Transformer/NLP | AdamW + warmup/linear hoặc cosine decay | Phù hợp pretrained model và giảm shock learning rate |
| Dataset nhỏ, metric dao động | `ReduceLROnPlateau` + early stopping | Tối ưu theo validation signal |
| Training dài, biết tổng số step | cosine decay hoặc `OneCycleLR` | Learning rate schedule mượt và kiểm soát tốt |
| GPU có Tensor Cores | AMP với `torch.amp.autocast` và `GradScaler` | Tăng throughput, giảm VRAM |
| Production training job | Config file + checkpoint + experiment tracking | Reproduce, compare và rollback được |

Không có optimizer hoặc scheduler tốt nhất cho mọi bài toán. Best solution phụ thuộc dữ liệu, model, loss surface, hardware, latency/cost budget và mục tiêu metric.

## Dùng được trong production không? Nếu có thì cần điều kiện gì?

Có. Training loop PyTorch kiểu trong bài có thể là nền cho production training nếu được đóng gói thành script/job có guardrail đầy đủ. Code trong exercise vẫn là bản học tập nhưng đã chứa các building block quan trọng.

Điều kiện tối thiểu để dùng production:

- Data split cố định, không leakage, có dataset snapshot hoặc data version.
- Config được lưu cùng artifact: model architecture, feature schema, optimizer, scheduler, seed, threshold, metric và package version.
- Training job có log structured: loss, metric, learning rate, gradient norm, epoch time, data size, device, checkpoint path.
- Checkpoint lưu best model theo validation metric, không chỉ epoch cuối.
- Có cơ chế resume hoặc ít nhất rollback từ artifact đã lưu.
- Evaluation trên test set chỉ chạy sau khi chọn model bằng validation set.
- Có monitoring cho NaN, loss spike, class imbalance, data quality và drift sau deploy.
- Checkpoint chỉ load từ nguồn tin cậy; không log raw PII hoặc sample nhạy cảm.
- Có benchmark throughput, GPU/CPU memory, checkpoint IO và training cost.
- Có owner chịu trách nhiệm khi metric production lệch khỏi offline metric.

Không nên coi code training loop trong notebook là production nếu thiếu reproducibility, checkpoint, validation, observability và artifact management.

## Deliverable cuối ngày

Bạn nên có 4 output:

1. Một training run hoàn chỉnh chạy được trên CPU hoặc GPU.
2. Một checkpoint best model được lưu theo validation loss.
3. Một bảng log theo epoch có train loss, validation loss, validation F1, learning rate và thời gian chạy.
4. Một đoạn production review trả lời vì sao training job này có thể hoặc chưa thể đưa vào production.

## Checklist hoàn thành

- [ ] Tôi giải thích được thứ tự `zero_grad -> forward -> loss -> backward -> clip -> optimizer.step`.
- [ ] Tôi biết vì sao train dùng `model.train()` còn validation/test dùng `model.eval()`.
- [ ] Tôi biết khi nào dùng `torch.no_grad()` hoặc `torch.inference_mode()`.
- [ ] Tôi chọn được AdamW hoặc SGD theo context và giải thích trade-off.
- [ ] Tôi biết scheduler nào gọi theo epoch, scheduler nào gọi theo validation metric, scheduler nào gọi theo step.
- [ ] Tôi thêm được gradient clipping và biết phải unscale gradient trước khi clipping nếu dùng AMP.
- [ ] Tôi save được checkpoint gồm model, optimizer, scheduler, scaler, config, epoch và best metric.
- [ ] Tôi có early stopping dựa trên validation metric.
- [ ] Tôi log được metric đủ để debug một training run.
- [ ] Tôi nêu được điều kiện để training loop PyTorch dùng được trong production.
