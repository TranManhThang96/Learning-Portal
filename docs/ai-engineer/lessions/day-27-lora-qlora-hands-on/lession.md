# Day 27: LoRA/QLoRA Hands-on

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Hiểu PEFT, LoRA và QLoRA ở mức đủ để ra quyết định kỹ thuật.
- Fine-tune một causal language model nhỏ bằng Hugging Face `transformers`, `datasets`, `peft`, `trl`, `accelerate` và `bitsandbytes`.
- Chọn được `r`, `lora_alpha`, `target_modules`, `lora_dropout`, batch size, gradient accumulation và `max_length` theo VRAM/cost/performance.
- Biết lưu adapter, load adapter, chạy inference sanity check và merge LoRA weights khi cần single artifact.
- Biết khi nào nên dùng LoRA, QLoRA, full fine-tuning, prompt engineering hoặc RAG.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

LoRA không train lại toàn bộ model. Nó freeze base model và chỉ train các low-rank adapter nhỏ gắn vào một số linear layer. QLoRA đi thêm một bước: base model được load ở 4-bit quantization để giảm VRAM, còn adapter LoRA vẫn được train ở precision phù hợp như bf16/fp16.

Với production, LoRA/QLoRA phù hợp khi bạn muốn model ổn định hơn về format, tone, workflow hoặc domain behavior. Không nên fine-tune để nhét knowledge thay đổi thường xuyên; trường hợp đó thường hợp với RAG hoặc tool calling hơn.

## 1. Bài Này Nằm Ở Đâu Trong Phase 4

```text
Day 25: quyết định khi nào fine-tune, khi nào dùng RAG
Day 26: chuẩn bị dataset instruction tuning
Day 27: chạy LoRA/QLoRA hands-on
Day 28: evaluate trước/sau fine-tune
Day 29-30: local LLM và deploy
```

Day 27 không chỉ là "chạy được training". Mục tiêu đúng là tạo được một training pipeline có thể kiểm soát: dataset rõ schema, training config có seed, adapter artifact có metadata, inference test chạy được, và biết trade-off trước khi merge/deploy.

## 2. Problem Framing

Bài toán hands-on:

```text
Input: instruction của user trong domain customer support
Output: câu trả lời ngắn, đúng JSON format, đúng tone, có next action
```

Ví dụ output mong muốn:

```json
{
  "category": "billing",
  "priority": "high",
  "answer": "Mình đã ghi nhận vấn đề bị tính phí hai lần. Vui lòng cung cấp mã giao dịch để mình kiểm tra và hoàn tiền nếu phát sinh lỗi."
}
```

Trước khi train, phải chốt các câu hỏi sau:

- Fine-tune để sửa behavior nào: format JSON, tone, classification label, policy wording hay workflow?
- Baseline hiện tại fail ra sao, tần suất bao nhiêu trên golden set?
- Dataset đã tách train/validation/test chưa?
- Output có schema parse được không?
- Facts có thay đổi thường xuyên không? Nếu có, cần RAG/tool thay vì cố train.
- Có đủ GPU cho model size, sequence length và batch size không?
- Có ràng buộc license/commercial use/PII không?

## 3. PEFT Là Gì

PEFT là Parameter-Efficient Fine-Tuning: thay vì update toàn bộ parameter của model, ta chỉ update một phần rất nhỏ. LoRA là một kỹ thuật PEFT phổ biến cho LLM.

Full fine-tuning:

```text
W_base -> update phần lớn hoặc toàn bộ weights
```

LoRA:

```text
W_base frozen
W_runtime = W_base + delta_adapter
delta_adapter = B @ A, với rank thấp r
```

Ý nghĩa thực tế:

- Base model giữ nguyên, dễ rollback.
- Adapter nhỏ hơn base model rất nhiều, dễ version và upload.
- Training nhanh và rẻ hơn full fine-tuning.
- Capacity bị giới hạn bởi adapter nên không thay đổi sâu như full fine-tuning.

## 4. LoRA Config Step by Step

### `r`: LoRA rank

`r` là rank của low-rank adapter. Rank càng cao, adapter càng có nhiều capacity, nhưng train nhiều parameter hơn.

Gợi ý thực tế:

| Context | Gợi ý `r` | Lý do |
|---|---:|---|
| Dataset nhỏ, format/tone đơn giản | 4-8 | Giảm overfit, tiết kiệm VRAM |
| Dataset vừa, task support/code writing hẹp | 16 | Default tốt để bắt đầu |
| Task phức tạp, nhiều style/domain | 32-64 | Tăng capacity, cần eval kỹ |

Không chọn `r` cao chỉ vì "nghe mạnh hơn". Nếu validation loss xấu hơn, output drift hoặc adapter quá nặng, hãy giảm `r`.

### `lora_alpha`

`lora_alpha` là scaling factor cho adapter. Cách nghĩ đơn giản:

```text
adapter_effect ~= lora_alpha / r
```

Default thực tế hay dùng:

- `r=8`, `lora_alpha=16`
- `r=16`, `lora_alpha=32`
- `r=32`, `lora_alpha=64`

Nếu output bị thay đổi quá mạnh, style quá cứng hoặc mất generality, giảm learning rate trước, sau đó cân nhắc giảm `alpha`.

### `target_modules`

`target_modules` quyết định layer nào được gắn LoRA.

Lựa chọn phổ biến:

- `["q_proj", "v_proj"]`: ít parameter, nhanh, thường đủ cho task nhẹ.
- `["q_proj", "k_proj", "v_proj", "o_proj"]`: thêm attention output, capacity tốt hơn.
- `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]`: mạnh hơn cho LLaMA/Qwen-style models, tốn VRAM hơn.
- `"all-linear"`: tiện cho thử nghiệm, nhưng cần kiểm tra model architecture và VRAM.

Best solution theo context: bắt đầu với modules attention (`q_proj`, `v_proj` hoặc full attention projections), chỉ mở rộng sang MLP hoặc `all-linear` khi eval cho thấy adapter chưa đủ học behavior.

### `lora_dropout`

`lora_dropout` giúp regularization, nhất là dataset nhỏ.

Gợi ý:

- `0.0`: dataset lớn/sạch, muốn tối đa signal.
- `0.05`: default tốt cho nhiều hands-on.
- `0.1`: dataset nhỏ hoặc có dấu hiệu overfit.

Dropout cao quá có thể làm model học chậm và format không ổn định.

### `bias`

Trong nhiều use case LoRA cho causal LM, `bias="none"` là lựa chọn tốt để giảm parameter trainable và giảm rủi ro thay đổi ngoài ý muốn.

## 5. QLoRA Và 4-bit Quantization

QLoRA dùng quantization để load base model ở 4-bit, thường với NF4 và double quantization:

```python
BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)
```

Mental model:

```text
Base model: 4-bit, frozen, tiết kiệm VRAM
LoRA adapter: trainable, precision cao hơn
Optimizer: memory-efficient hơn so với full fine-tuning
```

Trade-off:

| Lựa chọn | Ưu điểm | Nhược điểm |
|---|---|---|
| LoRA fp16/bf16 | Nhanh hơn, ít complexity hơn | Cần nhiều VRAM hơn QLoRA |
| QLoRA 4-bit | Chạy được model lớn hơn trên GPU nhỏ | Phụ thuộc CUDA/bitsandbytes, có thể chậm hơn |
| Full fine-tuning | Capacity cao nhất | Đắt, khó rollback, cần nhiều data/GPU |

Production note: QLoRA thường là training-time optimization. Khi serve, bạn có thể giữ adapter riêng hoặc merge adapter vào base model ở precision phù hợp, tùy serving stack.

## 6. Chọn Model Và Hardware

| Model size | Hardware gợi ý | Ghi chú |
|---:|---|---|
| 0.5B-1B | CPU rất chậm hoặc GPU nhỏ | Tốt để học pipeline |
| 1B-3B | Colab T4/A10, GPU 12-24GB | Tốt cho LoRA/QLoRA hands-on |
| 7B-8B | GPU 16-24GB với QLoRA | Cần batch nhỏ, gradient accumulation |
| 13B+ | GPU lớn hoặc multi-GPU | Không phù hợp bài ngắn nếu chưa có infra |

Model gợi ý cho bài học:

- `Qwen/Qwen2.5-0.5B-Instruct`: nhanh, hợp để test pipeline.
- `Qwen/Qwen2.5-1.5B-Instruct`: cân bằng hơn nếu GPU ổn.
- LLaMA-compatible model 7B/8B: chỉ dùng khi license, GPU và thời gian cho phép.

Luôn đọc model card trước khi dùng: license, intended use, language support, safety, commercial use, `trust_remote_code`, context length và tokenizer behavior.

## 7. Training Pipeline

Pipeline chuẩn:

```text
JSONL dataset
  -> validate schema
  -> train/validation split
  -> load tokenizer
  -> load base model
  -> optional 4-bit quantization
  -> prepare_model_for_kbit_training nếu QLoRA
  -> attach LoRA adapter
  -> train bằng SFTTrainer
  -> save adapter + tokenizer + metadata
  -> inference sanity check
  -> optional merge adapter
  -> compare before/after ở Day 28
```

Dataset nên dùng conversational `messages` để khớp chat model:

```json
{"messages":[{"role":"user","content":"Khách bị tính phí 2 lần, cần trả lời sao?"},{"role":"assistant","content":"{\"category\":\"billing\",\"priority\":\"high\",\"answer\":\"Mình đã ghi nhận vấn đề bị tính phí hai lần. Vui lòng cung cấp mã giao dịch để mình kiểm tra và hoàn tiền nếu phát sinh lỗi.\"}"}]}
```

Trong training script của bài này, mỗi record được đổi thành conversational prompt-completion:

```text
prompt     = toàn bộ messages trước assistant cuối
completion = assistant cuối
```

TRL có thể tính loss chỉ trên `completion`. Cách này rõ hơn việc bật `assistant_only_loss=True` mà chưa chứng minh chat template của tokenizer tạo được assistant mask. Nếu bạn muốn train trên nhiều assistant turn trong cùng conversation, hãy dùng `assistant_only_loss` nhưng phải inspect loss mask của template trước.

Validation tối thiểu:

- Mỗi dòng là JSON object.
- Có key `messages`.
- `messages` là list không rỗng.
- Mỗi message có `role` và `content`.
- Role nằm trong `system`, `user`, `assistant`.
- Có ít nhất một `user` và một `assistant`.
- Assistant output parse được JSON nếu downstream yêu cầu JSON.
- Không có PII thô như email, phone, token, card number nếu chưa được approval.
- Giữ nguyên `group_id` và `split` từ Day 26; tuyệt đối không đưa `test` vào trainer.

## 8. Colab Path Và Local GPU Path

### Colab

Phù hợp khi bạn chưa có GPU local.

```bash
pip install -U torch transformers datasets accelerate peft trl bitsandbytes
```

Checklist Colab:

- Runtime chọn GPU.
- Chạy `nvidia-smi` để biết VRAM.
- Dùng model 0.5B-1.5B trước.
- Mount Google Drive nếu cần lưu artifact lâu dài.
- Không upload dataset có PII lên notebook cá nhân nếu chưa được phép.

### Local GPU

Phù hợp khi bạn cần kiểm soát data/privacy hoặc train lặp lại.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U torch transformers datasets accelerate peft trl bitsandbytes
accelerate config
```

Checklist local:

- Driver/CUDA tương thích với PyTorch và bitsandbytes.
- `nvidia-smi` thấy GPU.
- Có disk đủ cho base model cache và artifact.
- Log package versions để reproduce.

## 9. Performance, VRAM Và Cost

Các biến ảnh hưởng mạnh:

- Model size: 7B tốn hơn rất nhiều so với 1.5B.
- `max_length`: 2048 thường tốn hơn đáng kể so với 1024.
- Batch size: tăng batch tăng VRAM.
- Gradient accumulation: tăng effective batch mà không tăng VRAM tuyến tính.
- `target_modules`: nhiều module trainable hơn thì tốn hơn.
- QLoRA: giảm VRAM, có thể chậm hơn LoRA bf16/fp16.
- Packing: tăng throughput với sequence ngắn, nhưng cần hiểu loss masking và dữ liệu.

Effective batch size:

```text
effective_batch = per_device_train_batch_size * gradient_accumulation_steps * num_gpus
```

Cost rule:

- Nếu prompt/RAG giải quyết được với latency/cost chấp nhận được, chưa cần fine-tune.
- Nếu traffic cao và task hẹp, fine-tune model nhỏ có thể giảm inference cost.
- Nếu dataset chưa sạch, GPU rẻ cũng không cứu được quality.

## 10. Merge Weights Hay Giữ Adapter Riêng

| Cách serve | Nên dùng khi | Trade-off |
|---|---|---|
| Giữ adapter riêng | Cần rollback nhanh, A/B test, multi-domain adapters | Serving stack phải support adapter |
| Merge adapter vào base | Cần single artifact, runtime đơn giản, giảm overhead adapter | Artifact lớn hơn, mất linh hoạt swap adapter |

Merge bằng `merge_and_unload()` tạo model thường không còn PEFT wrapper. Sau khi merge, luôn chạy lại sanity check và eval vì artifact đã khác đường load adapter.

## 11. Dùng Được Trong Production Không?

Có, LoRA/QLoRA dùng được trong production nếu các điều kiện sau được đáp ứng:

- Có baseline và golden eval set trước khi train.
- Dataset sạch, có quyền sử dụng, đã xử lý PII và có train/validation/test split.
- Mục tiêu fine-tune là behavior/format/tone/workflow, không phải facts thay đổi liên tục.
- Artifact được version đầy đủ: base model id, revision, tokenizer, LoRA config, seed, package versions, dataset version, training command, hardware.
- Có inference sanity check, regression eval, safety eval và rollback plan.
- License của base model, dataset và adapter cho phép use case production/commercial.
- Serving path đã được benchmark về latency, throughput, VRAM/RAM và cost.
- Có monitoring sau deploy: format accuracy, refusal/safety, hallucination proxy, user feedback, error rate và drift.

Không nên đưa vào production nếu chỉ có train loss giảm, chưa có eval độc lập hoặc chưa kiểm tra license/privacy.

## 12. Checklist Cuối Bài

- [ ] Giải thích được PEFT, LoRA, QLoRA và full fine-tuning.
- [ ] Chọn được `r`, `lora_alpha`, `target_modules`, `lora_dropout` theo context.
- [ ] Có dataset JSONL dạng `messages` và validation schema.
- [ ] Chạy được SFT với LoRA hoặc QLoRA trên model nhỏ.
- [ ] In được trainable parameters.
- [ ] Lưu được adapter artifact.
- [ ] Lưu được metadata artifact.
- [ ] Load được adapter để inference.
- [ ] Chạy được inference sanity check.
- [ ] Biết khi nào merge adapter và khi nào giữ adapter riêng.
- [ ] Ghi lại VRAM/cost/performance concern.
- [ ] Trả lời được điều kiện production.
