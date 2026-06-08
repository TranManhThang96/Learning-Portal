# Day 11 Reference: Training Loop, Optimizer Và Scheduler

File này là tài liệu tra cứu nhanh sau khi đã học đầy đủ trong `lession.md`. Nội dung được giữ theo từng chủ đề để review API, trade-off, failure mode và production checklist; người học không cần đọc file này theo thứ tự để hiểu bài.

## 1. Vì sao Day 11 quan trọng?

Một model deep learning không chỉ cần architecture đúng. Model còn cần training process đúng. Cùng một `nn.Module`, nếu training loop sai, kết quả có thể rất tệ dù code không crash:

- Loss không giảm vì learning rate quá cao hoặc quá thấp.
- Validation metric tốt giả tạo vì data leakage.
- Model overfit vì không có validation/early stopping.
- Metric không reproduce được vì seed và split thay đổi.
- Checkpoint không resume được vì chỉ lưu model weights, không lưu optimizer/scheduler state.
- GPU dùng kém vì data loading bottleneck hoặc batch size quá nhỏ.
- Training silently sai vì quên `model.eval()` khi validation.

Với Senior SE, hãy nhìn training như một stateful batch job có artifact. Nó cần config, logging, monitoring, retry, rollback và cost control giống các hệ thống production khác.

## 2. Training loop anatomy

Một training step chuẩn gồm các bước:

```text
1. Lấy batch từ DataLoader
2. Move input và label sang device
3. Reset gradient cũ
4. Forward pass
5. Tính loss
6. Backward pass
7. Optional: gradient clipping
8. Optimizer update
9. Optional: log metric theo batch hoặc epoch
```

Code tối thiểu:

```python
model.train()

for xb, yb in train_loader:
    xb = xb.to(device)
    yb = yb.to(device)

    optimizer.zero_grad(set_to_none=True)
    logits = model(xb)
    loss = loss_fn(logits, yb)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()
```

### Vì sao `zero_grad` đứng trước forward?

PyTorch accumulate gradient vào `.grad` của parameter. Đây là thiết kế có chủ ý vì có trường hợp cần gradient accumulation qua nhiều micro-batch. Nhưng trong training thông thường, mỗi optimizer update chỉ nên dùng gradient của batch hiện tại. Vì vậy cần reset gradient trước khi tính batch mới.

`optimizer.zero_grad(set_to_none=True)` thường tốt hơn set gradient về zero vì:

- Giảm thao tác ghi memory.
- Có thể tiết kiệm memory trong một số workload.
- Dễ phát hiện parameter không nhận gradient vì `.grad` vẫn là `None`.

Trade-off: code cũ hoặc custom logic nào giả định `.grad` luôn là tensor zero có thể cần sửa.

### Vì sao validation phải tách khỏi training?

Training và validation có mục đích khác nhau:

| Loop | Mục tiêu | Mode | Gradient | Update weights |
|---|---|---|---|---|
| Train | Học parameter | `model.train()` | Có | Có |
| Validation | Chọn model/hyperparameter | `model.eval()` | Không | Không |
| Test | Ước lượng final performance | `model.eval()` | Không | Không |

`model.train()` bật behavior training của layer như Dropout và BatchNorm. `model.eval()` chuyển chúng sang evaluation behavior. `torch.no_grad()` hoặc `torch.inference_mode()` tắt autograd để giảm memory và compute overhead.

Lỗi phổ biến: chỉ dùng `torch.no_grad()` nhưng quên `model.eval()`. Khi đó Dropout vẫn random và BatchNorm vẫn dùng training behavior, làm metric validation không ổn định.

## 3. Loss, metric và threshold

Loss là objective optimizer minimize. Metric là thứ bạn dùng để ra quyết định theo business context. Chúng không nhất thiết giống nhau.

Ví dụ binary classification:

- Loss: `BCEWithLogitsLoss`.
- Metric: F1, recall, precision, PR-AUC, ROC-AUC hoặc accuracy.
- Business policy: threshold chọn theo cost false positive/false negative.

Nên dùng `BCEWithLogitsLoss` thay vì `Sigmoid + BCELoss` vì implementation này ổn định số học hơn: model output raw logits, loss tự xử lý phần sigmoid bên trong.

```python
loss_fn = torch.nn.BCEWithLogitsLoss()
logits = model(xb)
loss = loss_fn(logits, yb)
probs = torch.sigmoid(logits)
```

Production note:

- Không chọn threshold chỉ vì default `0.5`. Hãy chọn theo validation set và business cost.
- Với class imbalance, accuracy có thể gây hiểu nhầm. Ưu tiên precision/recall/F1/PR-AUC.
- Log cả loss và metric. Loss giảm không đảm bảo metric business tăng.

## 4. Optimizer là gì?

Optimizer nhận gradient và quyết định cách update parameter.

```text
parameter_new = parameter_old + update_rule(gradient, learning_rate, optimizer_state)
```

Optimizer có state nội bộ. Ví dụ AdamW lưu moving average của gradient và squared gradient. Vì vậy checkpoint production nên lưu cả `optimizer.state_dict()`, không chỉ `model.state_dict()`.

### SGD

SGD update trực tiếp theo gradient:

```text
w = w - lr * gradient
```

Điểm mạnh:

- Đơn giản, dễ hiểu, ít state.
- Có thể generalize tốt trong một số bài vision/classic deep learning.
- Dễ debug khi học optimization.

Điểm yếu:

- Nhạy với learning rate.
- Converge chậm nếu loss surface phức tạp.
- Thường cần momentum và schedule tốt.

Nên dùng khi:

- Cần baseline tối giản.
- Model/dataset đủ quen thuộc.
- Bạn có thời gian tuning learning rate và momentum.

### SGD + momentum

Momentum thêm "quán tính" để giảm zig-zag:

```python
optimizer = torch.optim.SGD(
    model.parameters(),
    lr=0.01,
    momentum=0.9,
    weight_decay=1e-4,
)
```

Trade-off: converge mượt hơn SGD thường, nhưng vẫn cần tuning. Với Transformer fine-tuning, đây thường không phải lựa chọn đầu tiên.

### Adam

Adam dùng adaptive learning rate theo từng parameter dựa trên moving average của gradient.

Điểm mạnh:

- Prototype nhanh.
- Ít nhạy hơn SGD với learning rate ban đầu.
- Tốt cho nhiều bài NLP, sparse feature hoặc model khó optimize.

Điểm yếu:

- Có nhiều state hơn, tốn memory hơn.
- Weight decay trong Adam truyền thống không tách biệt tốt như AdamW.
- Không luôn generalize tốt hơn SGD.

### AdamW

AdamW là lựa chọn mặc định tốt cho nhiều bài hiện đại, đặc biệt Transformer và fine-tuning. Điểm khác quan trọng là weight decay được decouple khỏi gradient update.

```python
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=3e-4,
    weight_decay=0.01,
)
```

Nên bắt đầu với AdamW khi:

- Fine-tune BERT/PhoBERT hoặc model pretrained.
- Cần baseline mạnh nhanh.
- Không muốn mất nhiều thời gian tuning optimizer ban đầu.

Trade-off:

- Tốn memory hơn SGD vì optimizer state.
- Learning rate vẫn cần chọn cẩn thận.
- Weight decay không nên áp dụng bừa bãi cho mọi parameter trong model lớn; với Transformer production thường tách group để không decay bias và LayerNorm weight.

## 5. Learning rate là hyperparameter nhạy nhất

Learning rate quyết định độ lớn của mỗi update.

```text
LR quá cao  -> loss dao động, NaN, model không converge
LR quá thấp -> training rất chậm, dễ underfit trong budget cố định
LR hợp lý   -> loss giảm tương đối mượt, validation metric cải thiện
```

Triệu chứng thường gặp:

| Triệu chứng | Nguyên nhân có thể | Cách xử lý |
|---|---|---|
| Loss thành NaN | LR quá cao, input scale xấu, AMP overflow | Giảm LR, kiểm tra data, tắt AMP để debug, clipping |
| Train loss giảm, val loss tăng | Overfitting hoặc leakage ngược chiều | Early stopping, regularization, thêm data, kiểm tra split |
| Loss gần như không giảm | LR quá thấp, model quá yếu, label sai | Tăng LR, kiểm tra label, thử overfit một batch |
| Metric dao động mạnh | Batch nhỏ, validation nhỏ, LR cao | Tăng batch, giảm LR, dùng smoothing/log theo epoch |

Best practice: khi debug, hãy thử overfit một batch nhỏ. Nếu model không thể overfit 32-128 samples, có thể có bug về loss, label, shape, optimizer hoặc data.

## 6. Scheduler là gì?

Scheduler thay đổi learning rate trong quá trình training. Lý do: LR tốt ở đầu training có thể quá cao ở cuối training.

### `StepLR`

Giảm LR theo chu kỳ cố định.

```python
scheduler = torch.optim.lr_scheduler.StepLR(
    optimizer,
    step_size=10,
    gamma=0.5,
)

for epoch in range(num_epochs):
    train_one_epoch(...)
    validate(...)
    scheduler.step()
```

Nên dùng khi cần baseline dễ explain. Nhược điểm là lịch giảm cứng, không phản ứng với validation metric.

### `ReduceLROnPlateau`

Giảm LR khi metric không cải thiện.

```python
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer,
    mode="min",
    factor=0.5,
    patience=2,
)

for epoch in range(num_epochs):
    train_one_epoch(...)
    val_loss = evaluate(...)
    scheduler.step(val_loss)
```

Nên dùng cho project vừa và nhỏ khi validation loss là tín hiệu đáng tin. Lưu ý scheduler này nhận metric, không gọi trống như `StepLR`.

### `OneCycleLR`

Thay đổi LR theo từng step, thường tăng rồi giảm trong một cycle. Cần biết tổng số step.

```python
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer,
    max_lr=1e-3,
    epochs=num_epochs,
    steps_per_epoch=len(train_loader),
)

for epoch in range(num_epochs):
    for batch in train_loader:
        train_step(...)
        scheduler.step()
```

Nên dùng khi muốn train nhanh và đã kiểm soát tốt số step. Gọi sai theo epoch thay vì theo batch sẽ làm schedule sai.

### Cosine decay và warmup

Cosine decay giảm LR mượt từ cao xuống thấp. Warmup tăng LR dần ở đầu training. Warmup rất phổ biến khi fine-tune Transformer vì pretrained weights nhạy với update quá lớn ngay từ những step đầu.

Mental model:

```text
warmup:     bảo vệ model khỏi update sốc ở đầu training
decay:      giảm update khi model gần vùng tốt
plateau:    phản ứng khi validation không cải thiện
one-cycle:  tăng tốc training khi đã biết total steps
```

## 7. Dropout, weight decay, gradient clipping, early stopping

### Dropout

Dropout random tắt một phần activation trong training để model không phụ thuộc quá mức vào vài neuron.

```python
model = torch.nn.Sequential(
    torch.nn.Linear(input_dim, 128),
    torch.nn.ReLU(),
    torch.nn.Dropout(p=0.2),
    torch.nn.Linear(128, 1),
)
```

Trade-off:

- Giảm overfitting khi model lớn hoặc data ít.
- Có thể làm underfit nếu `p` quá cao.
- Chỉ active trong `model.train()`, bị tắt trong `model.eval()`.

### Weight decay

Weight decay phạt weight quá lớn, giúp regularization.

```python
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=3e-4,
    weight_decay=0.01,
)
```

Trade-off:

- Giúp giảm overfitting.
- Quá cao làm model khó fit.
- Với model lớn, nên tách parameter group để tránh decay bias/LayerNorm khi cần.

### Gradient clipping

Gradient clipping giới hạn norm của gradient để giảm exploding gradient.

```python
loss.backward()
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
optimizer.step()
```

Khi dùng AMP, gradient đang được scale. Cần unscale trước khi clipping:

```python
scaler.scale(loss).backward()
scaler.unscale_(optimizer)
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
scaler.step(optimizer)
scaler.update()
```

Trade-off:

- Tăng stability, đặc biệt với RNN, Transformer, loss spike hoặc data noisy.
- Nếu max norm quá thấp, update bị bóp quá mạnh và training chậm.
- Không thay thế việc chọn learning rate đúng.

### Early stopping

Early stopping dừng training khi validation metric không cải thiện sau một số epoch.

```text
if val_loss improved:
    save best checkpoint
    stale_epochs = 0
else:
    stale_epochs += 1

if stale_epochs >= patience:
    stop training
```

Trade-off:

- Tiết kiệm compute và giảm overfitting.
- Có thể dừng quá sớm nếu validation metric noisy.
- Cần `min_delta` và `patience` phù hợp.
- Luôn save best checkpoint, không dùng weights của epoch cuối nếu epoch cuối tệ hơn.

## 8. Mixed precision overview

Mixed precision dùng dtype thấp hơn như FP16 hoặc BF16 cho một số phép toán để giảm memory và tăng throughput trên GPU phù hợp. PyTorch cung cấp `torch.amp.autocast` và `torch.amp.GradScaler`.

Pattern CUDA AMP hiện đại:

```python
scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

for xb, yb in train_loader:
    optimizer.zero_grad(set_to_none=True)

    with torch.amp.autocast(
        device_type="cuda",
        dtype=torch.float16,
        enabled=use_amp,
    ):
        logits = model(xb)
        loss = loss_fn(logits, yb)

    scaler.scale(loss).backward()
    scaler.unscale_(optimizer)
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    scaler.step(optimizer)
    scaler.update()
```

Khi nên dùng:

- Training trên NVIDIA GPU có Tensor Cores.
- Model đủ lớn để memory/throughput là bottleneck.
- Bạn có metric validation để xác nhận không mất ổn định.

Khi nên tắt để debug:

- Loss thành NaN hoặc metric bất thường.
- Custom operation chưa ổn định với low precision.
- Chạy CPU hoặc workload quá nhỏ, overhead không đáng.

Production note: AMP là optimization, không phải requirement. Bắt đầu bằng FP32 để xác minh correctness, sau đó benchmark AMP.

## 9. DataLoader và performance

`DataLoader` không chỉ để chia batch. Nó ảnh hưởng trực tiếp đến throughput.

| Option | Khi dùng | Trade-off |
|---|---|---|
| `batch_size` | Tăng throughput nếu memory đủ | Batch quá lớn tốn VRAM và có thể cần LR tuning |
| `shuffle=True` | Training set | Không dùng cho validation/test nếu cần metric ổn định |
| `num_workers > 0` | Data loading hoặc preprocessing chậm | Debug khó hơn, tốn RAM/process |
| `pin_memory=True` | Copy CPU -> CUDA nhanh hơn | Chỉ hữu ích khi dùng GPU |
| `persistent_workers=True` | Tránh spawn worker mỗi epoch | Chỉ hợp khi `num_workers > 0` |
| `drop_last=True` | BatchNorm/distributed training cần batch đều | Mất một ít data mỗi epoch |
| `collate_fn` | Sequence/text length khác nhau | Cần test kỹ shape và padding |

Best practice:

- Dataset không nên tự move tensor lên GPU. Training loop quyết định device.
- Train loader nên shuffle. Validation/test loader không cần shuffle.
- Nếu GPU utilization thấp, kiểm tra data loading trước khi tăng model size.
- Với NLP, bottleneck có thể nằm ở tokenization. Cân nhắc cache tokenized dataset cho training lặp lại.

## 10. Checkpoint đúng cần lưu gì?

Có 2 loại artifact:

| Loại | Nội dung | Khi dùng |
|---|---|---|
| Model weights | `model.state_dict()` | Deploy hoặc inference |
| Training checkpoint | model, optimizer, scheduler, scaler, epoch, config, metric | Resume training hoặc audit |

Checkpoint training nên có:

```python
payload = {
    "epoch": epoch,
    "model_state_dict": model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "scheduler_state_dict": scheduler.state_dict(),
    "scaler_state_dict": scaler.state_dict(),
    "best_val_loss": best_val_loss,
    "config": config_dict,
    "metrics": validation_metrics,
}
torch.save(payload, checkpoint_path)
```

Load checkpoint:

```python
checkpoint = torch.load(
    checkpoint_path,
    map_location=device,
    weights_only=False,
)
model.load_state_dict(checkpoint["model_state_dict"])
optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
```

Security note: checkpoint PyTorch có thể dùng pickle bên dưới. Chỉ load checkpoint từ nguồn tin cậy. Nếu chỉ cần weights cho inference, ưu tiên lưu/load state dict riêng và cân nhắc `weights_only=True` khi phù hợp.

## 11. Reproducibility

Reproducibility trong deep learning là mục tiêu thực dụng, không phải lời hứa tuyệt đối. Một số CUDA operation có thể nondeterministic, version library khác nhau cũng có thể làm metric lệch nhẹ.

Tối thiểu nên có:

```python
def seed_everything(seed: int) -> None:
    import random
    import torch

    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
```

Trade-off:

- Deterministic setting giúp debug và audit.
- Có thể chậm hơn vì tắt benchmark chọn thuật toán nhanh nhất.
- Production training lớn đôi khi ưu tiên throughput, nhưng vẫn phải version data/config/code để so sánh run.

Nên lưu:

- Seed.
- Git commit hoặc code version.
- Package version.
- Dataset snapshot hoặc query/data hash.
- Train/validation/test split.
- Config optimizer/scheduler.
- Metric và threshold.

## 12. Logging tối thiểu

Log nên giúp trả lời nhanh các câu hỏi:

- Model có học không?
- Có overfit không?
- Learning rate hiện tại là bao nhiêu?
- Gradient có exploding không?
- Epoch này tốn bao lâu?
- Checkpoint nào đang là best?
- Run này dùng config nào?

Log tối thiểu theo epoch:

```text
epoch=7
train_loss=0.3124
val_loss=0.3501
val_f1=0.8421
lr=0.000750
grad_norm=0.91
seconds=12.44
stale_epochs=1
```

Production nên dùng structured logging hoặc experiment tracking như MLflow, Weights & Biases, TensorBoard hoặc hệ thống nội bộ. Với bài học này, JSON line hoặc print có format ổn định là đủ.

## 13. Failure modes và cách debug

| Vấn đề | Cách kiểm tra nhanh |
|---|---|
| Loss không giảm | Overfit một batch nhỏ, kiểm tra label dtype/shape, kiểm tra LR |
| Loss NaN | Tắt AMP, giảm LR, kiểm tra input NaN/Inf, thêm clipping |
| Validation quá tốt bất thường | Kiểm tra data leakage, split theo user/time, duplicate |
| Train nhanh nhưng validation chậm | Tắt gradient trong validation, tăng batch val, kiểm tra metric CPU |
| GPU utilization thấp | Tăng batch size, tăng `num_workers`, cache preprocessing, dùng `pin_memory` |
| Checkpoint load lỗi | Kiểm tra architecture/config match, `map_location`, package version |
| Metric production thấp hơn offline | Kiểm tra train-serving skew, threshold, drift, label distribution |

Debug workflow nên theo thứ tự:

1. Chạy trên subset nhỏ để giảm feedback loop.
2. Overfit một batch.
3. Tắt AMP và scheduler.
4. Log shape/dtype/device ở boundary.
5. Kiểm tra data split và label.
6. Thêm lại từng optimization một: clipping, scheduler, AMP, DataLoader workers.

## 14. Production readiness

Training loop trong bài dùng được làm nền cho production, nhưng production thực sự cần nhiều lớp xung quanh:

| Layer | Điều kiện tối thiểu |
|---|---|
| Data | Snapshot/version, schema validation, leakage check, quality report |
| Code | Script chạy được ngoài notebook, config rõ, unit test cho dataset/metric |
| Training | Seed, device fallback, checkpoint, early stopping, scheduler, logging |
| Evaluation | Validation/test tách rõ, metric theo business, threshold tuning |
| Artifact | Model weights, preprocessing, label mapping, config, metric, package version |
| Operations | Retry, timeout, storage policy, cost tracking, alert khi NaN/loss spike |
| Security | Không log PII, không load checkpoint lạ, kiểm soát quyền truy cập artifact |
| Deployment | Inference mode đúng, benchmark latency/throughput, rollback plan |

Nếu thiếu các điều kiện này, training loop vẫn có giá trị học tập hoặc prototype, nhưng chưa nên gọi là production training pipeline.

## 15. Tóm tắt quyết định kỹ thuật

- Bắt đầu bằng PyTorch loop tự viết để hiểu đúng behavior.
- Dùng `BCEWithLogitsLoss` cho binary classification logits.
- Dùng AdamW làm default cho prototype/fine-tuning hiện đại.
- Dùng `ReduceLROnPlateau` khi validation loss là tín hiệu chính; dùng warmup/cosine hoặc `OneCycleLR` khi biết total steps và training dài.
- Dùng gradient clipping khi có loss spike, RNN/Transformer hoặc fine-tuning không ổn định.
- Dùng AMP sau khi FP32 chạy đúng và có benchmark.
- Save best checkpoint theo validation metric.
- Log đủ để debug, reproduce và so sánh run.

## 16. Nguồn API

- PyTorch 2.12 docs qua Context7: `/websites/pytorch_2_12`.
- [Automatic Mixed Precision examples](https://docs.pytorch.org/docs/2.12/notes/amp_examples.html).
- [Optimizer và scheduler](https://docs.pytorch.org/docs/2.12/optim.html).
- [Gradient clipping](https://docs.pytorch.org/docs/2.12/generated/torch.nn.utils.clip_grad_norm_.html).
