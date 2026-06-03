# Day 27 Exercise: LoRA/QLoRA Hands-on

## Bài 1: Chuẩn Bị Dataset

Tạo file `data/day27_support_sft.jsonl` với ít nhất 30 examples theo format:

```json
{"messages":[{"role":"user","content":"Khách muốn đổi địa chỉ giao hàng."},{"role":"assistant","content":"{\"category\":\"shipping\",\"priority\":\"medium\",\"answer\":\"Mình đã ghi nhận yêu cầu đổi địa chỉ giao hàng. Vui lòng cung cấp mã đơn hàng và địa chỉ mới để mình kiểm tra khả năng cập nhật.\"}"}]}
```

Yêu cầu:

- Có ít nhất 3 category: `billing`, `shipping`, `account`.
- Có ít nhất 3 priority: `low`, `medium`, `high`.
- Không dùng email, số điện thoại, mã thẻ, token thật.
- Assistant output phải là JSON string parse được.

## Bài 2: Chạy LoRA Hoặc QLoRA

Chạy training trên model nhỏ:

```bash
MODEL_ID=Qwen/Qwen2.5-0.5B-Instruct \
DATA_PATH=data/day27_support_sft.jsonl \
OUT_DIR=artifacts/day27_support_lora_v1 \
USE_QLORA=1 \
SEED=42 \
LORA_R=16 \
LORA_ALPHA=32 \
LORA_DROPOUT=0.05 \
python scripts/train_lora_sft.py
```

Ghi lại:

- GPU name và VRAM.
- `max_length`.
- Batch size và gradient accumulation.
- Trainable parameter percentage.
- Train loss/eval loss cuối cùng.
- Thời gian train.
- Artifact size.

## Bài 3: Thử Ba Config LoRA

Chạy tối thiểu 3 biến thể:

| Run | `r` | `alpha` | `target_modules` | Kỳ vọng |
|---|---:|---:|---|---|
| A | 8 | 16 | `q_proj,v_proj` | Rẻ, ít capacity |
| B | 16 | 32 | `q_proj,k_proj,v_proj,o_proj` | Default cân bằng |
| C | 32 | 64 | attention + MLP projections | Mạnh hơn, tốn hơn |

So sánh:

- VRAM peak.
- Training time.
- Format accuracy trên 20 prompts.
- Output có bám tone không.
- Có dấu hiệu overfit không.

## Bài 4: Inference Sanity Check

Viết 5 prompts chưa xuất hiện trong train set:

```text
Khách báo bị trừ tiền nhưng đơn hàng chưa tạo.
Khách muốn đổi địa chỉ nhận hàng.
Khách quên mật khẩu và không nhận được email khôi phục.
Khách hỏi vì sao mã giảm giá không áp dụng được.
Khách muốn hủy đơn đã bàn giao cho vận chuyển.
```

Pass criteria:

- Output parse được JSON.
- Có đủ `category`, `priority`, `answer`.
- `answer` không bịa policy cụ thể nếu input chưa có thông tin.
- Tone nhất quán, lịch sự, ngắn gọn.
- Có next action rõ.

## Bài 5: Merge Hay Không Merge

Trả lời bằng một decision record ngắn:

```text
Decision: giữ adapter riêng hay merge?
Context:
Options:
Trade-off:
Decision:
Rollback:
```

Gợi ý:

- Nếu cần A/B test nhiều adapter, giữ adapter riêng.
- Nếu serving stack không support PEFT adapter, merge.
- Nếu merge, phải chạy lại sanity check và regression eval.

## Quiz

1. LoRA khác full fine-tuning ở điểm nào về parameter update và rollback?
2. QLoRA tiết kiệm VRAM bằng cơ chế nào?
3. `r` tăng thì capacity, VRAM và overfit risk thay đổi ra sao?
4. Vì sao `lora_alpha / r` là một mental model hữu ích?
5. Khi nào `target_modules="all-linear"` có thể không phải lựa chọn tốt?
6. `lora_dropout=0.05` giúp gì cho dataset nhỏ?
7. Vì sao train loss giảm chưa đủ để deploy?
8. Khi nào nên dùng RAG thay vì fine-tune?
9. Merge adapter có lợi và hại gì?
10. Dùng được trong production không? Nếu có thì cần điều kiện gì?

## Đáp Án Gợi Ý

1. LoRA freeze base model và chỉ train adapter nhỏ, rollback dễ bằng cách đổi hoặc tắt adapter. Full fine-tuning update nhiều weights hơn, artifact lớn và rollback khó hơn.
2. QLoRA load base model ở 4-bit quantization, thường NF4/double quantization, trong khi train LoRA adapter với precision phù hợp.
3. `r` cao hơn tăng capacity nhưng tăng trainable parameters, VRAM, training time và overfit risk.
4. Vì adapter effect thường tỉ lệ với scaling factor; nếu `alpha` tăng quá mạnh so với `r`, adapter có thể tác động quá nhiều lên output.
5. Khi GPU hạn chế, dataset nhỏ, task đơn giản hoặc muốn thay đổi behavior nhẹ; `all-linear` có thể tốn hơn và dễ overfit hơn.
6. Nó regularize adapter, giảm khả năng học thuộc dữ liệu nhỏ/noisy.
7. Vì train loss có thể giảm do overfit; cần validation, golden eval, format accuracy, safety eval và regression test.
8. Khi vấn đề là facts mới, private docs, citation hoặc realtime state.
9. Merge làm serving đơn giản hơn và không cần PEFT runtime, nhưng artifact lớn hơn và khó swap/rollback nhiều adapter.
10. Có, nếu có dataset hợp lệ, eval độc lập, metadata artifact, license/privacy review, benchmark cost/latency/VRAM, safety check và rollback plan.

## Rubric Tự Chấm

| Mức | Tiêu chí |
|---|---|
| Chưa đạt | Chỉ chạy training toy, không validation, không inference check |
| Đạt | Train được adapter, lưu artifact, load inference, có sanity check |
| Tốt | Có metadata, so sánh config, ghi VRAM/cost/performance, có decision merge |
| Production-minded | Có baseline, golden eval, privacy/license review, rollback và monitoring plan |
