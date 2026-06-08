# Day 13 Reference: Attention Shapes, Masks Và Production Checklist

File này là tài liệu tra cứu sau khi đã học đầy đủ trong `lession.md`. Các phần dưới nhắc lại công thức, shape, implementation và checklist để review nhanh; không phải luồng bài giảng bắt buộc.

## 1. Attention Là Gì?

Attention là cơ chế content-based routing giữa các token. Thay vì nén toàn bộ câu thành một hidden state tuần tự như RNN truyền thống, attention cho phép mỗi token hỏi: "trong sequence này, token nào quan trọng với tôi?"

Ví dụ câu:

```text
"Khách hàng muốn hoàn tiền vì đơn hàng bị hỏng"
```

Khi xử lý token "hoàn tiền", model có thể chú ý mạnh đến "khách hàng", "đơn hàng", "bị hỏng". Khi xử lý token "hỏng", model có thể chú ý đến "đơn hàng". Đây là cách token nhận thêm context từ token khác.

Luồng cơ bản:

```text
embedding của token
  -> tạo Query, Key, Value
  -> Query so khớp với Key của mọi token
  -> softmax tạo attention weight
  -> weighted sum các Value
  -> contextual embedding
```

## 2. Query, Key, Value Step By Step

Giả sử input embedding là `X`:

```text
X: [batch, seq_len, embed_dim]
```

Model học 3 projection:

```text
Q = X Wq
K = X Wk
V = X Wv
```

Ý nghĩa:

- Query: token hiện tại đang cần loại thông tin gì.
- Key: token này có đặc điểm gì để token khác tìm đến.
- Value: nội dung sẽ được truyền đi nếu token này được attend.

Điểm quan trọng: Q/K/V không phải dictionary key-value do engineer viết tay. Chúng là tensor được tạo từ learned weights trong training.

Ví dụ trực giác:

```text
Token "refund"
Query: cần biết nguyên nhân và đối tượng liên quan

Token "broken"
Key: dấu hiệu lỗi sản phẩm
Value: thông tin "bị hỏng"

Nếu Query("refund") match Key("broken") cao, Value("broken") được đưa nhiều hơn vào output của "refund".
```

## 3. Scaled Dot-Product Attention

Công thức:

```text
Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V
```

Shape phổ biến trong multi-head attention:

```text
Q: [batch, heads, target_len, head_dim]
K: [batch, heads, source_len, head_dim]
V: [batch, heads, source_len, head_dim]

Q K^T:           [batch, heads, target_len, source_len]
attention weight:[batch, heads, target_len, source_len]
output:          [batch, heads, target_len, head_dim]
```

Với self-attention, `target_len == source_len == seq_len`.

### Vì Sao Chia Cho `sqrt(d_k)`?

Dot product của vector dài thường có độ lớn tăng theo dimension. Nếu score quá lớn, `softmax` dễ bị saturated:

```text
score rất lớn -> softmax gần one-hot -> gradient yếu -> training khó ổn định
```

Chia cho `sqrt(head_dim)` giúp score có scale ổn định hơn.

## 4. Softmax Biến Score Thành Weight

Nếu token `i` có score với các token khác:

```text
[2.0, 1.0, -1.0]
```

Sau `softmax`, ta có weight gần:

```text
[0.71, 0.26, 0.03]
```

Output của token `i` là:

```text
0.71 * Value(token_1) + 0.26 * Value(token_2) + 0.03 * Value(token_3)
```

Attention weight hữu ích để debug, nhưng không nên xem là explainability đầy đủ cho audit. Model còn có nhiều layer, residual connection, feed-forward network và nonlinear transformation phía sau.

## 5. Mask: Padding Mask Và Causal Mask

### Padding Mask

Day 12 đã nói batch thường cần padding:

```text
["tôi", "thích", "AI", "<pad>", "<pad>"]
```

Model không nên attend vào `<pad>` vì đó không phải nội dung thật.

Mask thường dùng `True` cho token hợp lệ:

```text
[True, True, True, False, False]
```

Trong implementation manual bằng `masked_fill`, thường chuyển thành:

```python
scores = scores.masked_fill(~allowed_mask, very_negative_value)
```

Sau `softmax`, vị trí bị mask có weight gần 0.

### Causal Mask

Causal mask dùng cho decoder-only language model:

```text
Token ở vị trí i chỉ được nhìn token <= i
```

Ma trận causal cho sequence length 5:

```text
      key position
        0 1 2 3 4
q=0     1 0 0 0 0
q=1     1 1 0 0 0
q=2     1 1 1 0 0
q=3     1 1 1 1 0
q=4     1 1 1 1 1
```

Nếu train language model mà quên causal mask, token hiện tại có thể nhìn future token. Đây là data leakage nghiêm trọng: model học shortcut không tồn tại ở inference.

## 6. Self-Attention

Self-attention nghĩa là Q, K, V đều đến từ cùng một sequence:

```text
Input: [t1, t2, t3, t4]

t1 attend tới [t1, t2, t3, t4]
t2 attend tới [t1, t2, t3, t4]
t3 attend tới [t1, t2, t3, t4]
t4 attend tới [t1, t2, t3, t4]
```

Với encoder như BERT/PhoBERT, attention thường bidirectional: token được nhìn cả trái và phải, trừ PAD.

Với decoder như GPT/LLaMA/Qwen, attention là causal: token chỉ nhìn quá khứ và chính nó.

## 7. Vì Sao Attention Parallel Tốt Hơn RNN?

RNN xử lý theo chuỗi:

```text
x1 -> h1 -> h2 -> h3 -> h4
```

Muốn tính `h4`, phải có `h3`; muốn có `h3`, phải có `h2`. Training khó parallel theo chiều sequence.

Self-attention dùng matrix multiplication:

```text
Q @ K^T
```

GPU xử lý matrix multiplication rất tốt, nên toàn bộ token trong sequence có thể được tính đồng thời trong training.

Trade-off:

- RNN có dependency tuần tự nhưng memory theo sequence length thường nhẹ hơn.
- Attention parallel tốt hơn nhưng attention matrix là `seq_len x seq_len`.

Nếu `seq_len` tăng từ 1,024 lên 4,096, attention matrix tăng:

```text
(4096 / 1024)^2 = 16 lần
```

## 8. Multi-Head Attention

Một attention head chỉ là một view. Multi-head attention chia `embed_dim` thành nhiều phần:

```text
embed_dim = num_heads * head_dim
```

Ví dụ:

```text
embed_dim = 64
num_heads = 4
head_dim = 16
```

Quy trình:

```text
X
 -> Linear tạo Q/K/V
 -> reshape thành [batch, heads, seq_len, head_dim]
 -> mỗi head tự tính attention
 -> concat heads
 -> output projection về embed_dim
```

Trực giác:

```text
head 1: quan hệ chủ ngữ - động từ
head 2: entity/reference
head 3: keyword sentiment
head 4: local phrase pattern
```

Không nên diễn giải từng head quá chắc chắn trong production. Đây chỉ là mental model để hiểu vì sao nhiều head giúp tăng capacity.

## 9. PyTorch Implementation Gần Production

Đoạn dưới dùng API PyTorch được kiểm tra qua Context7: `torch.matmul` hỗ trợ batched matrix multiplication theo các chiều cuối, boolean mask cần broadcast được với attention weights, `nn.Dropout` tự tắt ở `eval()` mode. Với PyTorch production code thật, cân nhắc `torch.nn.functional.scaled_dot_product_attention` hoặc module/runtime đã tối ưu trước khi tự viết manual attention.

```python
from __future__ import annotations

import math
import torch
from torch import nn


def causal_mask(seq_len: int, device: torch.device) -> torch.Tensor:
    return torch.tril(torch.ones(seq_len, seq_len, dtype=torch.bool, device=device))


class MultiHeadSelfAttention(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int, dropout_p: float = 0.1) -> None:
        super().__init__()
        if embed_dim <= 0 or num_heads <= 0:
            raise ValueError("embed_dim and num_heads must be positive")
        if embed_dim % num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.qkv = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        self.dropout = nn.Dropout(dropout_p)

    def _normalize_mask(self, mask: torch.Tensor, batch: int, seq_len: int, device: torch.device) -> torch.Tensor:
        if mask.dtype != torch.bool:
            raise TypeError("attention mask must be boolean, where True means allowed")
        mask = mask.to(device=device)
        if mask.shape == (batch, seq_len):
            return mask[:, None, None, :]
        if mask.shape == (batch, 1, 1, seq_len):
            return mask
        if mask.shape == (batch, self.num_heads, seq_len, seq_len):
            return mask
        raise ValueError(f"unsupported mask shape: {tuple(mask.shape)}")

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        causal: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if x.ndim != 3:
            raise ValueError("x must have shape [batch, seq_len, embed_dim]")
        batch, seq_len, embed_dim = x.shape
        if embed_dim != self.embed_dim:
            raise ValueError(f"expected embed_dim={self.embed_dim}, got {embed_dim}")

        qkv = self.qkv(x).view(batch, seq_len, 3, self.num_heads, self.head_dim)
        q, k, v = qkv.permute(2, 0, 3, 1, 4).unbind(0)
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)

        allowed = None
        if attention_mask is not None:
            allowed = self._normalize_mask(attention_mask, batch, seq_len, x.device)
        if causal:
            c_mask = causal_mask(seq_len, x.device)[None, None, :, :]
            allowed = c_mask if allowed is None else allowed & c_mask
        if allowed is not None:
            if not allowed.any(dim=-1).all():
                raise ValueError("each query must be allowed to attend to at least one key")
            scores = scores.masked_fill(~allowed, torch.finfo(scores.dtype).min)

        attention_probs = torch.softmax(scores, dim=-1)
        dropped_attention_probs = self.dropout(attention_probs)
        context = torch.matmul(dropped_attention_probs, v)
        context = context.transpose(1, 2).contiguous().view(batch, seq_len, embed_dim)
        return self.out_proj(context), attention_probs
```

Điểm cần review trong code:

- `embed_dim % num_heads == 0` để chia head không lệch.
- Mask dùng `True = allowed`, sau đó `~allowed` mới bị fill bằng giá trị rất âm.
- Tất cả mask tạo trên cùng `device` với input.
- `torch.finfo(scores.dtype).min` tránh hard-code `-1e9` không phù hợp mọi dtype.
- `nn.Dropout` được áp dụng trên bản dùng để tính context và tự khác behavior giữa `train()`/`eval()`.
- Giá trị trả về là probabilities trước dropout để tổng theo key vẫn gần 1 và phù hợp visualization.
- Nếu một query không được attend vào key nào, code raise lỗi thay vì tạo `NaN`.

## 10. Test Nhỏ Cần Có

Tối thiểu nên test:

- Output shape là `[batch, seq_len, embed_dim]`.
- Attention weight shape là `[batch, heads, seq_len, seq_len]`.
- Padding mask làm weight ở PAD key gần 0.
- Causal mask làm future position có weight gần 0.
- `eval()` tắt dropout nên output lặp lại deterministic hơn `train()`.
- Mask sai dtype hoặc shape phải fail fast.

Folder bài học có script `attention_demo.py` để chạy các test này.

## 11. Trade-Off Và Performance

### Compute

Attention compute xấp xỉ:

```text
O(batch * heads * seq_len^2 * head_dim)
```

### Memory

Nếu materialize attention weights:

```text
batch * heads * seq_len * seq_len * bytes_per_element
```

Ví dụ gần đúng:

| Config | Attention weight memory cho 1 layer |
|---|---:|
| `batch=8`, `heads=12`, `seq_len=512`, FP16 | khoảng 50 MB |
| `batch=1`, `heads=32`, `seq_len=4096`, FP16 | khoảng 1 GB |
| `batch=1`, `heads=32`, `seq_len=8192`, FP16 | khoảng 4 GB |

Các con số này chỉ tính attention weights nếu materialize đầy đủ, chưa tính Q/K/V, activation khác, FFN, optimizer state hoặc KV cache.

### FlashAttention Concept

FlashAttention-style kernel không thay đổi công thức attention. Ý tưởng là tính attention theo block và quản lý memory tốt hơn để không phải materialize toàn bộ ma trận attention lớn trong HBM theo cách naive. Kết quả mong muốn:

- Giảm memory footprint.
- Tăng throughput trên GPU phù hợp.
- Giữ cùng output logic ở mức attention.

Trong PyTorch hiện đại, `scaled_dot_product_attention` có thể dispatch sang backend tối ưu tùy device, dtype, shape và cấu hình. Với production, ưu tiên runtime đã dùng kernel tối ưu thay vì tự viết Python attention loop.

## 12. Batch Vs Streaming

### Batch Training/Batch Inference

Batch giúp tận dụng GPU tốt hơn:

```text
[batch, seq_len, embed_dim]
```

Trade-off:

- Padding nhiều làm waste compute.
- Batch có request dài nhất kéo cả batch dài theo nếu padding naive.
- Dynamic batching cần timeout và queue policy.

### Streaming Decoder Inference

Decoder-only model sinh từng token:

```text
prefix -> next token -> append -> next token
```

Nếu mỗi bước tính lại K/V cho toàn bộ prefix thì rất chậm. KV cache lưu Key/Value của token đã qua để mỗi bước chỉ xử lý token mới. Trade-off:

- Latency/token giảm.
- VRAM tăng theo `batch * layers * heads * seq_len * head_dim`.
- Multi-user streaming cần quản lý cache eviction và request cancellation.

## 13. Production Concerns

- Mask bug: padding mask sai làm model học PAD; causal mask sai gây data leakage.
- Long context: prompt dài có thể gây OOM hoặc p99 latency vượt SLA.
- Truncation âm thầm: cắt mất instruction hoặc evidence quan trọng.
- Dtype mismatch: FP16/BF16/FP32 khác nhau về memory, speed và numerical stability.
- Device mismatch: input CPU nhưng model GPU, hoặc mask CPU nhưng tensor GPU.
- Attention weight logging: có thể lộ PII nếu log token text; cần redaction.
- Model upgrade: thay tokenizer/context length/config là breaking change nếu không có golden eval.
- Interpretability: attention chart chỉ hỗ trợ debug, không đủ làm bằng chứng giải thích quyết định rủi ro cao.

## 14. Guidance Thực Tế

| Use case | Attention mode | Gợi ý production |
|---|---|---|
| Ticket classification tiếng Việt | Bidirectional encoder | PhoBERT/BERT-style, dynamic padding, eval theo class imbalance |
| Reranking trong RAG | Cross-attention hoặc encoder pair input | Giới hạn top-k rerank, benchmark latency |
| Chatbot/assistant | Causal decoder | KV cache, token budget, guardrails, streaming |
| Long document QA | Retrieval trước, attention sau | Chunking, hybrid search, reranking, citation |
| Code assistant | Causal decoder long context | Context packing, file selection, truncation audit |

## 15. Tài Liệu Tham Khảo

- Attention Is All You Need: https://arxiv.org/abs/1706.03762
- The Illustrated Transformer: https://jalammar.github.io/illustrated-transformer/
- The Annotated Transformer: https://nlp.seas.harvard.edu/annotated-transformer/
- PyTorch docs qua Context7: `/websites/pytorch_2_12`
