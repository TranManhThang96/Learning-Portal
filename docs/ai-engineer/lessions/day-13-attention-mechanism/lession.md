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
| 30 phút | Đọc `document.md` phần 1-5 | Hiểu công thức, shape, mask và self-attention |
| 25 phút | Đọc phần PyTorch implementation | Biết cách kiểm tra shape, dtype, device và mask |
| 25 phút | Đọc trade-off production | Biết rủi ro `O(n^2)`, memory, long context, FlashAttention, KV cache |
| 25 phút | Làm `exercise.md` và chạy script demo | Có output test và attention weight đơn giản |
| 5 phút | Tự trả lời checklist | Biết phần nào cần học lại trước Day 14 |

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
