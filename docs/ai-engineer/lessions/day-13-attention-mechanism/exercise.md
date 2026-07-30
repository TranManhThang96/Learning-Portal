# Day 13 Exercise: Attention Mechanism

## Mục Tiêu Thực Hành

Bạn sẽ chạy một module multi-head self-attention nhỏ bằng PyTorch để kiểm tra:

- Shape của output và attention weights.
- Padding mask chặn PAD key.
- Causal mask chặn future token.
- Dropout khác nhau giữa `train()` và `eval()`.
- Dtype/device được xử lý nhất quán.

## Setup

Từ root repo:

```bash
python3 lessions/day-13-attention-mechanism/attention_demo.py
```

Nếu chưa có PyTorch:

```bash
python3 -m pip install torch
```

## Bài 1: Đọc Output Shape

Chạy script và ghi lại:

- `output.shape`
- `weights.shape`
- `device`
- `dtype`

Giải thích vì sao:

```text
input:   [batch, seq_len, embed_dim]
weights: [batch, heads, seq_len, seq_len]
output:  [batch, seq_len, embed_dim]
```

## Bài 2: Padding Mask

Trong script, tìm biến `padding_mask`.

```python
padding_mask = torch.tensor(
    [
        [True, True, True, False, False],
        [True, True, True, True, True],
    ],
    dtype=torch.bool,
    device=device,
)
```

Yêu cầu:

- Giải thích vì sao batch 0 có hai token PAD.
- Kiểm tra attention weight trỏ vào key position 3 và 4 của batch 0 phải gần 0.
- Đổi mask thành tất cả `True` và quan sát test nào không còn ý nghĩa.

## Bài 3: Causal Mask

Causal mask chặn future token:

```text
query position 1 không được attend key position 2, 3, 4
```

Yêu cầu:

- In attention weights của head 0.
- Chỉ ra các vị trí phía trên đường chéo chính.
- Giải thích vì sao các vị trí đó phải bằng 0 trong decoder-only model.

## Bài 4: Dropout Train/Eval

Script có test:

```text
model.train() -> dropout active
model.eval()  -> dropout disabled
```

Yêu cầu:

- Chạy nhiều lần và ghi lại output.
- Giải thích vì sao `eval()` cần thiết khi inference.
- Nếu quên `eval()` khi serve model có dropout, production risk là gì?

## Bài 5: Sửa Code Để Dùng PyTorch SDPA

Không bắt buộc hoàn thành trong Day 13, nhưng nên thử sau khi hiểu manual implementation.

Yêu cầu:

- Tạo nhánh thử nghiệm trong ghi chú cá nhân, không cần sửa file bài học.
- Thay phần `scores -> softmax -> dropout -> matmul` bằng `torch.nn.functional.scaled_dot_product_attention`.
- Giữ nguyên shape `[batch, heads, seq_len, head_dim]`.
- So sánh output shape và mask behavior.

Gợi ý quan trọng: boolean mask của PyTorch SDPA dùng `True` để cho phép phần tử tham gia attention, còn manual code trong bài dùng `masked_fill(~allowed, very_negative_value)`.

`scaled_dot_product_attention` luôn áp dụng dropout theo giá trị `dropout_p` truyền vào, kể cả module đang ở `eval()`. Vì vậy hãy truyền:

```python
dropout_p = self.dropout_p if self.training else 0.0
```

Không được truyền cố định `dropout_p=0.1`, nếu không inference vẫn ngẫu nhiên.

## Quiz

1. Query, Key và Value khác nhau ở đâu?
2. Vì sao attention score phải chia cho `sqrt(head_dim)`?
3. Padding mask và causal mask giải quyết hai vấn đề khác nhau như thế nào?
4. Vì sao quên causal mask trong language model là data leakage?
5. Multi-head attention tăng capacity bằng cách nào?
6. Vì sao attention train parallel tốt hơn RNN?
7. Nếu sequence length tăng từ 2,048 lên 8,192, attention matrix tăng bao nhiêu lần?
8. FlashAttention concept giải quyết điểm nghẽn gì?
9. Vì sao attention weights không đủ làm bằng chứng explainability?
10. Dùng self-attention manual trong production cần điều kiện gì?

## Đáp Án Gợi Ý

1. Query biểu diễn nhu cầu tìm context, Key biểu diễn dấu hiệu để được match, Value là nội dung được aggregate.
2. Để giữ scale score ổn định, tránh `softmax` saturated và gradient yếu.
3. Padding mask chặn PAD token; causal mask chặn future token.
4. Vì token hiện tại nhìn được đáp án tương lai trong training nhưng inference không có thông tin đó.
5. Nhiều head học nhiều projection/view quan hệ khác nhau, sau đó concat và project về `embed_dim`.
6. Attention dùng matrix multiplication cho toàn bộ sequence, GPU parallel tốt hơn dependency tuần tự của RNN.
7. `(8192 / 2048)^2 = 16 lần`.
8. Giảm memory traffic/materialization của attention matrix lớn và tăng throughput trên GPU phù hợp.
9. Vì output cuối còn qua nhiều layer, FFN, residual, nonlinear transformation và attention có thể không tương ứng trực tiếp với causal explanation.
10. Cần test mask, giới hạn sequence length, eval đúng, dtype/device nhất quán, runtime tối ưu, monitoring latency/OOM và rollback.

## Checklist Nộp Bài

- [ ] Chạy được `attention_demo.py`.
- [ ] Ghi lại shape của output và weights.
- [ ] Chứng minh padding mask làm PAD key có weight bằng 0.
- [ ] Chứng minh causal mask làm future attention bằng 0.
- [ ] Giải thích được dropout khác nhau giữa `train()` và `eval()`.
- [ ] Trả lời quiz bằng lời của mình.
- [ ] Viết một đoạn ngắn: "Dùng attention trong production được không? Nếu có thì cần điều kiện gì?"
