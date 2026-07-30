# Day 11: Training Loop, Optimizer, Scheduler

## Mục tiêu của ngày học

Sau bài này, bạn cần làm được 8 việc:

1. Viết được training loop PyTorch đúng thứ tự: load batch, `zero_grad`, forward, loss, `backward`, gradient clipping, `optimizer.step`, scheduler.
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
| 15 phút | Đọc TL;DR, mental model và anatomy của training loop | Nắm được thứ tự một training step |
| 45 phút | Học optimizer, scheduler và regularization trong bài này | Chọn được AdamW/SGD và scheduler theo context |
| 40 phút | Học checkpoint, logging, reproducibility và performance trong bài này | Biết training job cần log và lưu gì |
| 60 phút | Làm [exercise.md](./exercise.md), chạy script mẫu và thay đổi hyperparameter | Có một training run có validation, early stopping và checkpoint |
| 10 phút | Dùng [document.md](./document.md) như cheat sheet rồi tự review checklist | Biết còn thiếu gì trước khi sang NLP/Transformer |

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

## 1. Training step, epoch và gradient accumulation

Ba thuật ngữ đầu tiên cần phân biệt:

- **Training step**: một lần model xử lý batch và optimizer có cơ hội cập nhật weights.
- **Epoch**: một lần đi qua toàn bộ training set.
- **Gradient accumulation**: cộng gradient của nhiều micro-batch trước một lần `optimizer.step()`, hữu ích khi batch mong muốn không vừa VRAM.

PyTorch cộng gradient vào `parameter.grad` thay vì tự ghi đè. Vì vậy loop thông thường phải reset gradient trước batch mới:

```python
model.train()

for features, labels in train_loader:
    features = features.to(device, non_blocking=True)
    labels = labels.to(device, non_blocking=True)

    optimizer.zero_grad(set_to_none=True)
    logits = model(features)
    loss = loss_fn(logits, labels)
    loss.backward()
    optimizer.step()
```

`set_to_none=True` thường giảm memory write và giúp nhận ra parameter không có gradient vì `.grad` giữ giá trị `None`. Đổi lại, custom code giả định `.grad` luôn là tensor phải xử lý trường hợp `None`.

Nếu dùng gradient accumulation với `accumulation_steps=4`, loss phải được scale để gradient trung bình không lớn gấp bốn:

```python
optimizer.zero_grad(set_to_none=True)

for step, (features, labels) in enumerate(train_loader, start=1):
    logits = model(features)
    loss = loss_fn(logits, labels) / accumulation_steps
    loss.backward()

    if step % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
```

Production code phải xử lý cả batch cuối khi số batch không chia hết cho `accumulation_steps`. Với distributed training, accumulation còn liên quan đồng bộ gradient; không nên tự tối ưu trước khi baseline một GPU chạy đúng.

## 2. Train, validation và test giải quyết ba câu hỏi khác nhau

| Split | Câu hỏi | Có update weights? | Dùng để chọn model? |
|---|---|---:|---:|
| Train | Model học parameter từ dữ liệu nào? | Có | Có, gián tiếp qua optimization |
| Validation | Config/checkpoint nào tốt nhất? | Không | Có |
| Test | Sau khi khóa mọi quyết định, chất lượng ước lượng là bao nhiêu? | Không | Không |

Validation loop chuẩn:

```python
@torch.inference_mode()
def evaluate(model, data_loader, loss_fn, device):
    model.eval()
    total_loss = 0.0

    for features, labels in data_loader:
        features = features.to(device)
        labels = labels.to(device)
        logits = model(features)
        total_loss += loss_fn(logits, labels).item() * features.size(0)

    return total_loss / len(data_loader.dataset)
```

`model.eval()` và `torch.inference_mode()` không thay thế nhau:

- `model.eval()` đổi behavior của Dropout/BatchNorm sang inference.
- `torch.inference_mode()` tắt autograd và thêm một số tối ưu so với `no_grad()`.
- `torch.no_grad()` linh hoạt hơn nếu tensor tạo trong block còn được dùng ở luồng có autograd sau đó.

Lỗi phổ biến là chạy test sau mỗi thử nghiệm rồi chọn config tốt nhất theo test. Khi đó test đã trở thành validation và con số cuối bị optimistic. Chỉ mở test set sau khi đã khóa architecture, hyperparameter, threshold và checkpoint.

## 3. Loss, metric và threshold

**Loss** là hàm optimizer tối thiểu hóa. **Metric** là cách con người đánh giá model. **Threshold** là policy đổi score liên tục thành quyết định.

Binary classification nên output raw logits và dùng `BCEWithLogitsLoss`:

```python
loss_fn = torch.nn.BCEWithLogitsLoss()
logits = model(features)
loss = loss_fn(logits, labels)

probabilities = torch.sigmoid(logits)
predictions = probabilities >= threshold
```

`BCEWithLogitsLoss` ổn định số học hơn việc gọi `sigmoid` rồi `BCELoss` riêng. Threshold `0.5` chỉ là baseline, không phải chân lý. Nếu bỏ sót gian lận đắt hơn cảnh báo nhầm, threshold phải được chọn theo validation set và business cost.

| Tình huống | Metric nên xem |
|---|---|
| Class cân bằng, cost hai lỗi gần nhau | Accuracy và F1 |
| Positive hiếm | Precision, recall, F1, PR-AUC |
| Cần xếp hạng score | ROC-AUC/PR-AUC và calibration |
| Quyết định có chi phí cụ thể | Expected business cost tại threshold |

Với dataset lớn, không nên giữ toàn bộ logits của cả epoch trong RAM như demo nhỏ. Hãy dùng streaming metric, histogram hoặc thư viện metric hỗ trợ distributed aggregation.

## 4. Optimizer: policy cập nhật weights

Optimizer biến gradient thành update. Nó có state riêng, vì vậy muốn resume training đúng phải lưu `optimizer.state_dict()`.

### SGD và momentum

SGD cơ bản:

```text
weight_new = weight_old - learning_rate * gradient
```

Momentum tích lũy hướng update để giảm zig-zag:

```python
optimizer = torch.optim.SGD(
    model.parameters(),
    lr=0.01,
    momentum=0.9,
    weight_decay=1e-4,
)
```

SGD ít state và có thể generalize tốt trong một số bài vision, nhưng nhạy learning rate và thường cần schedule được tune kỹ.

### Adam và AdamW

Adam giữ moving average của gradient và bình phương gradient để tạo learning rate thích nghi theo parameter. AdamW tách weight decay khỏi adaptive gradient update, nên là default thực dụng cho nhiều bài fine-tune Transformer:

```python
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=3e-4,
    weight_decay=0.01,
)
```

Trade-off:

- AdamW thường hội tụ baseline nhanh hơn SGD.
- Adam/AdamW tốn thêm memory cho optimizer states.
- Weight decay không nên áp dụng máy móc cho mọi parameter. Với Transformer, thường tách bias và normalization weights khỏi decay theo convention của model/framework.
- Không có optimizer tốt nhất cho mọi loss surface; phải giữ cùng data split và budget khi benchmark.

## 5. Learning rate và cách debug model không học

Learning rate thường là hyperparameter nhạy nhất:

```text
quá cao  -> loss dao động, overflow hoặc NaN
quá thấp -> loss gần như đứng yên trong compute budget
hợp lý   -> train loss giảm và validation metric cải thiện
```

Khi model không học, làm theo thứ tự:

1. Kiểm tra shape, dtype, label range và device.
2. Thử overfit 32-128 samples hoặc một batch.
3. Tắt AMP, scheduler, augmentation và DataLoader workers.
4. Kiểm tra parameter có gradient và gradient có finite không.
5. Quét learning rate trên vài bậc độ lớn.
6. Thêm lại từng optimization một.

Nếu model không overfit nổi một batch nhỏ, đừng train lâu hơn. Khả năng cao pipeline có bug về label, loss, mask, detached tensor hoặc optimizer.

## 6. Scheduler và vị trí gọi `step`

Scheduler thay đổi learning rate theo thời gian hoặc metric. Vị trí `scheduler.step()` phụ thuộc loại scheduler.

### Scheduler theo epoch

```python
scheduler = torch.optim.lr_scheduler.StepLR(
    optimizer,
    step_size=10,
    gamma=0.5,
)

for epoch in range(num_epochs):
    train_one_epoch(...)
    validate(...)
    scheduler.step()  # sau optimizer.step() của epoch
```

### Scheduler theo validation metric

```python
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer,
    mode="min",
    factor=0.5,
    patience=2,
)

for epoch in range(num_epochs):
    train_one_epoch(...)
    val_loss = validate(...)
    scheduler.step(val_loss)
```

`ReduceLROnPlateau` chỉ nên dùng khi validation signal đủ ổn định. Scheduler patience phải phối hợp với early-stopping patience; nếu early stopping dừng ngay sau khi LR giảm, model chưa có thời gian hưởng lợi.

### Scheduler theo optimizer step

```python
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer,
    max_lr=1e-3,
    epochs=num_epochs,
    steps_per_epoch=len(train_loader),
)

for batch in train_loader:
    train_step(batch)
    optimizer.step()
    scheduler.step()
```

`OneCycleLR`, linear warmup và nhiều cosine schedule dùng số optimizer step, không phải số micro-batch. Khi gradient accumulation hoặc distributed training thay đổi số update thật, total steps phải được tính lại.

Mental model:

- **Warmup**: tăng LR từ nhỏ để tránh update sốc ở đầu fine-tuning.
- **Decay**: giảm update khi model tiến gần vùng tốt.
- **Plateau**: phản ứng với validation signal.
- **One-cycle**: schedule mạnh khi biết chắc tổng số optimizer updates.

## 7. Regularization và stability

### Dropout

Dropout tắt ngẫu nhiên một phần activation khi training:

```python
torch.nn.Sequential(
    torch.nn.Linear(input_dim, 128),
    torch.nn.ReLU(),
    torch.nn.Dropout(p=0.2),
    torch.nn.Linear(128, 1),
)
```

`p` quá cao có thể gây underfit. Dropout chỉ tắt đúng khi inference nếu đã gọi `model.eval()`.

### Weight decay

Weight decay hạn chế weights quá lớn. Giá trị quá cao làm model khó fit. Với pretrained model, hãy bắt đầu từ recipe đã được kiểm chứng rồi tune trên validation set thay vì copy `0.01` cho mọi context.

### Gradient clipping

```python
loss.backward()
grad_norm = torch.nn.utils.clip_grad_norm_(
    model.parameters(),
    max_norm=1.0,
)
optimizer.step()
```

Clipping giúp giảm exploding gradient nhưng không sửa được learning rate sai, data lỗi hoặc loss không finite. Hãy log norm trước clipping để biết model có thường xuyên chạm ngưỡng hay không.

### Early stopping

Early stopping dừng khi validation metric không cải thiện sau `patience` epoch. Luôn kết hợp với:

- `min_delta` để bỏ qua dao động quá nhỏ.
- Best checkpoint để không dùng weights của epoch cuối.
- Patience đủ dài so với scheduler và độ nhiễu của metric.

## 8. Mixed precision đúng thứ tự

Mixed precision dùng FP16/BF16 cho phép toán phù hợp để giảm VRAM và tăng throughput. Với CUDA FP16, pattern hiện hành là `torch.amp.autocast` và `torch.amp.GradScaler`:

```python
amp_enabled = device.type == "cuda"
scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

for features, labels in train_loader:
    optimizer.zero_grad(set_to_none=True)

    with torch.amp.autocast(
        device_type="cuda",
        dtype=torch.float16,
        enabled=amp_enabled,
    ):
        logits = model(features)
        loss = loss_fn(logits, labels)

    scaler.scale(loss).backward()
    scaler.unscale_(optimizer)
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    scaler.step(optimizer)
    scaler.update()
```

Thứ tự bắt buộc khi có clipping:

```text
scaled backward -> unscale -> clip -> scaler.step -> scaler.update
```

Không chạy backward bên trong autocast. Bắt đầu bằng FP32 để xác minh correctness, sau đó mới bật AMP và so sánh metric, throughput, peak memory. BF16 thường ổn định hơn FP16 trên hardware hỗ trợ, nhưng lựa chọn phải dựa trên device và benchmark.

## 9. DataLoader và throughput

| Option | Tác dụng | Trade-off |
|---|---|---|
| `batch_size` | Tăng throughput nếu memory đủ | Tăng VRAM, có thể cần tune LR |
| `shuffle=True` | Đổi thứ tự train samples | Không dùng để quyết định validation/test order |
| `num_workers` | Parallel data loading | Tốn process/RAM, debug khó hơn |
| `pin_memory=True` | Hỗ trợ copy CPU-to-CUDA nhanh hơn | Không hữu ích đáng kể khi chỉ CPU |
| `persistent_workers=True` | Không respawn workers mỗi epoch | Chỉ hợp khi `num_workers > 0` |
| custom `collate_fn` | Dynamic padding/ghép sample | Cần test shape và edge cases |

Dataset không nên tự move tensor lên GPU. Device placement thuộc training loop. Nếu GPU utilization thấp, đo riêng data wait time, tokenization/augmentation time và host-to-device copy trước khi tăng model.

## 10. Checkpoint: deploy artifact khác resume artifact

| Artifact | Nội dung | Mục đích |
|---|---|---|
| Inference weights | Model weights, config, tokenizer/preprocessing, label mapping | Deploy |
| Training checkpoint | Model + optimizer + scheduler + scaler + epoch/step + RNG/config/metric | Resume/audit |

Payload tối thiểu:

```python
checkpoint = {
    "epoch": epoch,
    "model_state_dict": model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "scheduler_state_dict": scheduler.state_dict(),
    "scaler_state_dict": scaler.state_dict(),
    "best_val_loss": best_val_loss,
    "config": config,
    "metrics": val_metrics,
}
torch.save(checkpoint, checkpoint_path)
```

Production nên ghi file tạm rồi atomic rename hoặc upload artifact hoàn tất mới publish metadata, tránh checkpoint dở dang khi process chết. Chỉ load checkpoint từ nguồn tin cậy; full checkpoint có thể dùng pickle. Khi chỉ load tensor weights phù hợp, cân nhắc `weights_only=True`.

## 11. Reproducibility thực dụng

Reproducibility không có nghĩa mọi hardware/version cho bit-identical output. Mục tiêu là giải thích và tái tạo được run trong sai số chấp nhận:

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

Phải lưu thêm:

- Git commit hoặc code version.
- Python/PyTorch/CUDA/container version.
- Dataset snapshot, query hoặc content hash.
- Split IDs, seed và sampling policy.
- Config model/optimizer/scheduler.
- Metric implementation và threshold.

Deterministic algorithms có thể chậm hơn. Production có thể ưu tiên throughput, nhưng không được bỏ data/code/config versioning.

## 12. Logging và observability

Một epoch log tối thiểu:

```text
epoch=7
global_step=1400
train_loss=0.3124
val_loss=0.3501
val_f1=0.8421
learning_rate=0.00075
grad_norm=0.91
seconds=12.44
checkpoint_saved=true
```

Log phải trả lời được:

- Model có học không?
- Bắt đầu overfit từ đâu?
- LR và gradient có bất thường không?
- Bottleneck nằm ở data hay compute?
- Checkpoint nào tốt nhất và được tạo bởi config nào?

Không log raw PII hoặc toàn bộ batch. Với production training, dùng structured logs và experiment tracker/model registry; nhưng vẫn phải giữ metadata cốt lõi độc lập với một vendor cụ thể.

## 13. Failure modes và playbook debug

| Vấn đề | Kiểm tra đầu tiên | Hướng xử lý |
|---|---|---|
| Loss không giảm | Overfit một batch, label/shape/dtype | Sửa pipeline rồi mới tune |
| Loss NaN/Inf | Input, LR, AMP, gradient norm | Tắt AMP, giảm LR, fail fast |
| Validation quá tốt | Duplicate/leakage/split | Split theo user/time/entity |
| Train tốt, production tệ | Train-serving skew, drift, threshold | Contract test và monitoring |
| GPU rảnh nhiều | DataLoader/tokenizer/copy | Profile pipeline, cache/batch |
| Checkpoint load lỗi | Architecture/config/version | Validate metadata trước load |

Quy trình debug tốt là giảm hệ thống về bản đơn giản nhất chạy đúng, rồi bật lại từng optimization. Đừng thay đồng thời optimizer, scheduler, batch size và AMP vì bạn sẽ không biết nguyên nhân.

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

## Nguồn kỹ thuật đã đối chiếu

- PyTorch 2.12 docs qua Context7: `/websites/pytorch_2_12`.
- Optimizer/scheduler: `optimizer.step()` phải xảy ra trước scheduler step; `OneCycleLR` step theo batch, `ReduceLROnPlateau` step sau validation metric.
- AMP: `torch.amp.autocast`, `torch.amp.GradScaler`; phải `unscale_` trước `clip_grad_norm_`.
- API cụ thể có thể đổi theo PyTorch version. Khi triển khai, pin version và kiểm tra lại docs của version đang chạy.
