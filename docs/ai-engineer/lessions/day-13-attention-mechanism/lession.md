# Day 13: Attention Mechanism

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Giải thích được Query, Key, Value bằng mental model gần với search/index/cache trong backend.
- Tính được scaled dot-product attention ở mức shape: `QK^T -> softmax -> weighted sum V`.
- Phân biệt được self-attention, padding mask và causal mask.
- Hiểu multi-head attention: vì sao chia nhiều head, concat lại, rồi project về `embed_dim`.
- Giải thích được vì sao attention train parallel tốt hơn RNN, nhưng tốn `O(n^2)` theo sequence length.
- Viết và review được một module PyTorch self-attention nhỏ có shape validation, mask handling, dropout, dtype/device awareness và test cơ bản.
- Trả lời được câu hỏi: dùng attention trong production được không, và cần điều kiện gì.

## Vị Trí Trong Phase 2

Day 12 đã nói rằng text sau tokenizer trở thành sequence token id, có padding, truncation và attention mask. Day 13 giải thích model dùng mask đó như thế nào để các token "nhìn" nhau. Day 14 sẽ đặt attention vào một Transformer block hoàn chỉnh cùng positional encoding, LayerNorm, feed-forward network và residual connection.

```text
Day 12: text -> token ids -> embedding-ready sequence
Day 13: token embeddings -> attention -> contextual embeddings
Day 14: attention + FFN + norm + residual -> Transformer architecture
```

## Cách Học Trong 2 Giờ

| Thời lượng | Việc cần làm | Output |
|---:|---|---|
| 10 phút | Đọc TL;DR và diagram Q/K/V | Nắm được attention là content-based routing giữa token |
| 30 phút | Học công thức, shape, mask và self-attention trong bài này | Tự tính được một attention row |
| 25 phút | Học phần PyTorch implementation trong bài này | Biết cách kiểm tra shape, dtype, device và mask |
| 25 phút | Học trade-off production trong bài này | Biết rủi ro `O(n^2)`, memory, long context, FlashAttention, KV cache |
| 25 phút | Làm `exercise.md` và chạy script demo | Có output test và attention weight đơn giản |
| 5 phút | Dùng `document.md` như cheat sheet rồi tự trả lời checklist | Biết phần nào cần học lại trước Day 14 |

## TL;DR

Attention là cơ chế để mỗi token chọn thông tin quan trọng từ các token khác.

```text
token hiện tại tạo Query  -> "tôi đang cần gì?"
token khác có Key         -> "tôi có dấu hiệu gì để được tìm thấy?"
token khác có Value       -> "nội dung tôi sẽ truyền đi là gì?"

score  = Query dot Key
weight = softmax(score / sqrt(head_dim))
output = weighted sum(Value)
```

Với self-attention, Query/Key/Value đều đến từ cùng một sequence. Tất cả token có thể tính attention bằng matrix multiplication nên training trên GPU parallel tốt hơn RNN. Giá phải trả là attention matrix có kích thước `seq_len x seq_len`, khiến compute và memory tăng theo `O(n^2)`.

## Diagram Nhanh

```text
Input embeddings X: [batch, seq_len, embed_dim]
        |
        | Linear projections học được
        v
 Q = XWq     K = XWk     V = XWv
        \       |       /
         \      |      /
          Q @ K^T / sqrt(d_k)
                 |
              mask nếu có
                 |
              softmax
                 |
              @ V
                 |
 Contextual embeddings: [batch, seq_len, embed_dim]
```

## Mental Model Cho Senior SE

| Attention concept | Backend analogy | Điểm cần nhớ |
|---|---|---|
| Query | Request cần tìm context | Mỗi token tự tạo request vector |
| Key | Search index/signature | Token nào match Query cao sẽ được chú ý hơn |
| Value | Payload/record content | Thứ thật sự được aggregate vào output |
| Score | Ranking score | Dot product đo độ tương thích |
| Softmax | Normalize priority | Biến score thành weight tổng gần 1 |
| Mask | Filter/permission/window | Chặn PAD hoặc future token |
| Head | Một view độc lập | Nhiều head học nhiều kiểu quan hệ |

## 1. Từ embedding đến contextual embedding

Tokenizer ở Day 12 tạo token IDs. Embedding layer đổi mỗi ID thành vector, nhưng vector ban đầu chưa biết context:

```text
"bank" trong "river bank"
"bank" trong "bank account"
```

Attention cho mỗi token lấy thông tin từ token khác để tạo **contextual embedding**, tức vector đã phụ thuộc câu hiện tại.

Ví dụ:

```text
"Khách hàng muốn hoàn tiền vì đơn hàng bị hỏng"
```

Khi xử lý "hoàn tiền", model có thể lấy nhiều thông tin từ "đơn hàng" và "bị hỏng". Attention không dùng rule do engineer viết tay; quan hệ này được học từ loss trong quá trình training.

## 2. Query, Key, Value từng bước

Giả sử input embeddings:

```text
X: [batch, seq_len, embed_dim]
```

Model học ba phép chiếu tuyến tính:

```text
Q = X Wq
K = X Wk
V = X Wv
```

- **Query (Q)**: token đang tìm loại thông tin gì.
- **Key (K)**: token có dấu hiệu gì để được tìm thấy.
- **Value (V)**: payload nào được truyền nếu token được chú ý.

Q/K/V là tensor học được, không phải key-value map của backend. Cùng input nhưng weights khác sẽ tạo Q/K/V khác.

Ví dụ trực giác:

```text
Query("refund")  -> cần nguyên nhân của yêu cầu hoàn tiền
Key("broken")    -> biểu diễn tín hiệu lỗi sản phẩm
Value("broken")  -> nội dung về trạng thái bị hỏng
```

Nếu Query của "refund" khớp Key của "broken", Value của "broken" đóng góp lớn hơn vào output của "refund".

## 3. Scaled dot-product attention

Công thức:

```text
Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V
```

Shape với multi-head attention:

```text
Q:       [B, H, T_query, D]
K:       [B, H, T_key,   D]
V:       [B, H, T_key,   D]
Q @ K^T: [B, H, T_query, T_key]
output:  [B, H, T_query, D]
```

Trong self-attention, `T_query == T_key == sequence_length`.

### Tự tính một ví dụ nhỏ

Giả sử một Query có score với ba Key:

```text
scores = [2.0, 1.0, -1.0]
```

Softmax tạo weight gần:

```text
[0.71, 0.26, 0.03]
```

Output:

```text
0.71 * V1 + 0.26 * V2 + 0.03 * V3
```

Vì vậy attention là weighted routing, không phải chọn cứng một token.

### Vì sao chia cho `sqrt(d_k)`?

Khi dimension tăng, dot product có xu hướng lớn hơn. Score quá lớn làm softmax gần one-hot, gradient rất nhỏ ở phần lớn vị trí và training kém ổn định. Chia cho căn bậc hai của head dimension giữ scale hợp lý hơn.

## 4. Mask là policy "token nào được phép nhìn token nào"

Mask phải được hiểu trước khi viết code vì mỗi API có thể dùng convention khác nhau.

### Padding mask

Batch có câu dài ngắn khác nhau:

```text
tokens:         ["tôi", "học", "AI", "<pad>", "<pad>"]
attention_mask: [   1,     1,    1,       0,       0]
```

PAD chỉ làm tensor cùng shape, không mang nội dung. Query thật không được lấy Value từ PAD key.

Manual implementation trong bài dùng:

```python
scores = scores.masked_fill(~allowed_mask, torch.finfo(scores.dtype).min)
```

Ở đây `True = allowed`.

### Causal mask

Decoder-only language model không được nhìn future token:

```text
      key position
        0 1 2 3
q=0     1 0 0 0
q=1     1 1 0 0
q=2     1 1 1 0
q=3     1 1 1 1
```

Quên causal mask khi train next-token prediction là data leakage: model nhìn thấy đáp án tương lai nhưng inference thật không có.

### Mask convention không thống nhất giữa API

- Manual code của bài: boolean `True` nghĩa là được phép.
- `torch.nn.functional.scaled_dot_product_attention`: boolean `True` cũng nghĩa là tham gia attention.
- Một số API như key padding mask của `nn.MultiheadAttention` dùng `True` theo nghĩa bỏ qua vị trí.

Không đoán convention từ tên biến. Đọc docs đúng version và viết unit test chứng minh masked weight/output.

## 5. Self-attention, cross-attention và causal self-attention

| Loại | Query từ đâu? | Key/Value từ đâu? | Use case |
|---|---|---|---|
| Self-attention | Sequence A | Sequence A | Encoder hoặc decoder block |
| Causal self-attention | Output prefix | Cùng output prefix | Decoder-only generation |
| Cross-attention | Decoder state | Encoder output | Encoder-decoder như T5 |

Encoder BERT/PhoBERT thường dùng bidirectional self-attention: token thấy cả trái và phải, trừ PAD. GPT/LLaMA/Qwen dùng causal self-attention: token chỉ thấy quá khứ và chính nó.

## 6. Vì sao attention parallel tốt hơn RNN?

RNN có dependency tuần tự:

```text
x1 -> h1 -> h2 -> h3 -> h4
```

Muốn tính `h4` phải chờ `h3`. Self-attention tính toàn bộ `Q @ K^T` bằng matrix multiplication, nên GPU có thể xử lý nhiều token cùng lúc trong training.

Trade-off:

- RNN tuần tự nhưng không tạo ma trận attention đầy đủ.
- Attention parallel tốt, nhưng compute/memory theo sequence length thường gần bậc hai.

Nếu sequence tăng từ 1,024 lên 4,096:

```text
(4096 / 1024)^2 = 16 lần
```

Đây là lý do "context dài hơn" không miễn phí.

## 7. Multi-head attention

Một head là một attention subspace:

```text
embed_dim = num_heads * head_dim
```

Ví dụ `embed_dim=64`, `num_heads=4` thì `head_dim=16`.

Luồng:

```text
X
  -> project Q/K/V
  -> reshape [B, H, T, D]
  -> attention độc lập trên từng head
  -> concat heads
  -> output projection về embed_dim
```

Nhiều head tăng capacity để model học nhiều kiểu quan hệ. Không nên gán chắc chắn "head 1 là ngữ pháp, head 2 là sentiment" nếu chưa có phân tích; đó chỉ là mental model, không phải guarantee.

## 8. Implement manual attention để học

Đây là phiên bản rút gọn của [attention_demo.py](./attention_demo.py):

```python
from __future__ import annotations

import math
import torch
from torch import nn


class MultiHeadSelfAttention(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int, dropout_p: float = 0.1) -> None:
        super().__init__()
        if embed_dim % num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.qkv = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        self.dropout = nn.Dropout(dropout_p)

    def forward(
        self,
        x: torch.Tensor,
        allowed_mask: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        batch, seq_len, embed_dim = x.shape
        qkv = self.qkv(x).view(
            batch,
            seq_len,
            3,
            self.num_heads,
            self.head_dim,
        )
        q, k, v = qkv.permute(2, 0, 3, 1, 4).unbind(0)

        scores = q @ k.transpose(-2, -1)
        scores = scores / math.sqrt(self.head_dim)

        if allowed_mask is not None:
            scores = scores.masked_fill(
                ~allowed_mask,
                torch.finfo(scores.dtype).min,
            )

        attention_probs = torch.softmax(scores, dim=-1)
        context = self.dropout(attention_probs) @ v
        context = context.transpose(1, 2).contiguous()
        context = context.view(batch, seq_len, embed_dim)
        return self.out_proj(context), attention_probs
```

Các guardrail trong file runnable đầy đủ:

- Validate input rank và `embed_dim`.
- Validate `embed_dim % num_heads == 0`.
- Validate boolean mask và shape broadcast.
- Tạo mask trên cùng device.
- Fail fast nếu một query không được attend vào key nào.
- Trả **attention probabilities trước dropout** để visualization vẫn có tổng gần 1.
- Dùng dropout-applied probabilities chỉ để tính context.

Manual implementation nhằm học và test shape. Production nên ưu tiên implementation đã tối ưu.

## 9. PyTorch SDPA và behavior dễ sai

`torch.nn.functional.scaled_dot_product_attention` có thể chọn backend tối ưu theo device, dtype và shape:

```python
import torch.nn.functional as F

context = F.scaled_dot_product_attention(
    q,
    k,
    v,
    attn_mask=allowed_mask,
    dropout_p=self.dropout_p if self.training else 0.0,
    is_causal=False,
)
```

Hai trap quan trọng:

1. Boolean mask của SDPA dùng `True = tham gia attention`.
2. SDPA luôn áp dụng dropout theo `dropout_p` được truyền vào; nó không tự đọc `module.training`. Inference phải truyền `0.0`.

Không truyền đồng thời causal mask tùy biến và `is_causal=True` nếu API/version không cho phép. Viết test chống future leakage thay vì chỉ kiểm tra code không crash.

## 10. Attention weights không phải explainability hoàn chỉnh

Attention chart hữu ích để:

- Debug mask.
- Quan sát token nào được route mạnh.
- Phát hiện PAD/future token còn weight.

Nhưng không đủ để kết luận nguyên nhân quyết định vì output còn qua nhiều layer, residual path, FFN và nonlinear transformation. Với use case rủi ro cao, cần evaluation, counterfactual test và phương pháp giải thích phù hợp hơn.

## 11. Compute, memory và kernel tối ưu

Naive attention có compute gần:

```text
O(batch * heads * seq_len^2 * head_dim)
```

Nếu materialize weights:

```text
memory ~= batch * heads * seq_len * seq_len * bytes_per_element
```

Ví dụ gần đúng chỉ cho attention matrix một layer:

| Config | FP16 memory |
|---|---:|
| `B=8, H=12, T=512` | khoảng 50 MB |
| `B=1, H=32, T=4096` | khoảng 1 GB |
| `B=1, H=32, T=8192` | khoảng 4 GB |

FlashAttention-style kernel không đổi công thức. Nó tổ chức tính toán theo block để giảm memory traffic và tránh materialize toàn bộ matrix theo cách naive. Production nên để PyTorch/runtime/model server chọn kernel tối ưu, rồi benchmark thay vì assume tên kernel luôn đồng nghĩa nhanh hơn.

## 12. Batch, streaming và KV cache

Batch tăng GPU throughput nhưng request dài nhất có thể kéo padding cả batch. Dynamic batching phải cân bằng:

- Thời gian chờ gom batch.
- Similarity về sequence length.
- Memory peak.
- p95/p99 latency.

Decoder-only generation sinh từng token. **KV cache** lưu Key/Value của prefix cũ để không tính lại chúng ở mỗi decode step:

```text
không cache: tính lại prefix cho mỗi token
có KV cache: chỉ project token mới, tái sử dụng K/V cũ
```

Trade-off: giảm latency mỗi token nhưng VRAM tăng theo concurrency, layers và context length. Multi-user streaming cần timeout, cancellation và cache eviction.

## 13. Failure modes cần test

| Failure | Hậu quả | Test tối thiểu |
|---|---|---|
| Padding mask đảo nghĩa | Model attend vào PAD | PAD key weight gần 0 |
| Quên causal mask | Future leakage | Upper triangle weight bằng 0 |
| Mask sai device | Runtime error | CPU/CUDA smoke test |
| Mọi key đều bị mask | NaN softmax | Fail fast trước softmax |
| Dropout còn bật khi infer | Output không ổn định | Hai lần eval output giống nhau |
| Sequence không giới hạn | OOM/p99 cao | Hard token limit + load test |
| Log token/weights thô | Lộ PII | Redaction và logging policy |

## Best Solution Theo Context

| Context | Lựa chọn nên dùng | Lý do |
|---|---|---|
| Học nền tảng | Tự implement scaled dot-product attention bằng PyTorch | Thấy rõ Q/K/V, shape và mask |
| Training/inference production | Dùng implementation đã tối ưu trong PyTorch/Hugging Face/runtime serving | Giảm rủi ro bug, tận dụng kernel tối ưu |
| Text classification | Bidirectional encoder attention | Token được nhìn toàn bộ input |
| Autoregressive generation | Causal self-attention | Không nhìn future token, tránh leakage |
| Long-context RAG | Retrieval/chunking trước, không nhồi mọi thứ vào prompt | Attention `O(n^2)`, KV cache tốn VRAM |
| GPU hiện đại, sequence dài | SDPA/FlashAttention-style kernel nếu runtime hỗ trợ | Giảm memory materialize attention matrix |

## Dùng Được Trong Production Không?

Có. Attention là core primitive của Transformer và đang được dùng trong production rất rộng rãi. Nhưng có hai tầng cần phân biệt:

- Dùng model attention-based trong production: có, nếu có eval, serving runtime, monitoring, token budget và rollback.
- Tự viết attention kernel/module cho production: chỉ nên làm khi có lý do rõ ràng như custom research, custom mask/window, hoặc model nhỏ nội bộ; còn lại nên dùng implementation đã được tối ưu và kiểm thử.

Điều kiện tối thiểu:

- Shape contract rõ ràng: `batch`, `seq_len`, `embed_dim`, `num_heads`, `head_dim`.
- Tokenizer, padding policy, truncation policy và attention mask được version cùng model.
- Test riêng cho padding mask và causal mask để tránh data leakage.
- Giới hạn sequence length theo SLA, VRAM/RAM và p95/p99 latency.
- Monitoring token length distribution, OOM, timeout, truncation rate, latency và error type.
- Với decoder-only inference, dùng KV cache/runtime phù hợp thay vì tính lại toàn bộ prefix mỗi token.
- Có fallback khi context quá dài: reject, summarize, retrieve lại, hoặc degrade model.

## Deliverable Cuối Ngày

Bạn nên có:

- Ghi chú riêng mô tả Q/K/V và công thức attention bằng lời của mình.
- Một lần chạy `attention_demo.py` trong folder bài học.
- Ít nhất 3 test hoặc assertion về shape, mask và dropout train/eval.
- Một đoạn note ngắn trả lời: nếu sequence length tăng 4 lần thì memory attention tăng bao nhiêu lần và ảnh hưởng production thế nào.

## Checklist Hoàn Thành

- [ ] Tôi giải thích được Query, Key, Value không phải do engineer set tay mà là projection được học trong training.
- [ ] Tôi viết được công thức `softmax(QK^T / sqrt(d_k))V`.
- [ ] Tôi biết shape phổ biến của Q/K/V là `[batch, heads, seq_len, head_dim]`.
- [ ] Tôi phân biệt được padding mask và causal mask.
- [ ] Tôi hiểu vì sao quên causal mask trong language model là data leakage.
- [ ] Tôi giải thích được multi-head attention bằng nhiều view quan hệ khác nhau.
- [ ] Tôi biết attention parallel tốt hơn RNN ở training nhờ matrix multiplication.
- [ ] Tôi biết điểm yếu lớn nhất là compute/memory `O(n^2)`.
- [ ] Tôi chạy được bài tập và thấy masked attention weight về 0.
- [ ] Tôi trả lời được điều kiện production readiness của attention-based model.

## Nguồn kỹ thuật đã đối chiếu

- PyTorch 2.12 docs qua Context7: `/websites/pytorch_2_12`.
- API trọng tâm: batched matrix multiplication, `nn.Dropout`, `torch.nn.functional.scaled_dot_product_attention`, boolean mask và optimized attention backends.
- Paper nền tảng: [Attention Is All You Need](https://arxiv.org/abs/1706.03762).
- Khi triển khai, pin PyTorch/model version và test mask semantics trên đúng runtime; các API khác nhau có thể dùng convention mask khác nhau.
