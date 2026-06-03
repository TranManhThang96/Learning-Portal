# Day 14 Document: Transformer Architecture Notes

File này dùng như tài liệu tra cứu nhanh sau khi đã đọc `lession.md`.

## 1. Từ attention đến Transformer

Một attention layer trả lời câu hỏi:

```text
Mỗi token nên lấy thông tin từ token nào, với trọng số bao nhiêu?
```

Một Transformer block trả lời câu hỏi lớn hơn:

```text
Sau khi token lấy context từ token khác, representation của từng token nên được biến đổi và ổn định như thế nào?
```

Một Transformer model là stack nhiều block:

```text
embedding -> position -> block x N -> output head
```

## 2. Shape mental model

Giả sử:

```text
batch_size = B
sequence_length = T
hidden_dim = H
num_heads = A
head_dim = D = H / A
```

Shape thường gặp:

| Tensor | Shape | Ý nghĩa |
|---|---:|---|
| input_ids | `[B, T]` | Token ids |
| token_embeddings | `[B, T, H]` | Vector input |
| Q/K/V | `[B, A, T, D]` | Query/Key/Value theo head |
| attention_scores | `[B, A, T, T]` | Mỗi token attend đến token khác |
| attention_output | `[B, T, H]` | Contextual vectors |
| FFN intermediate | `[B, T, 4H]` hoặc biến thể | Hidden mở rộng |
| logits classifier | `[B, num_labels]` | Output classification |
| logits LM | `[B, T, vocab_size]` | Output language modeling |

## 3. Encoder-only reference

```text
input_ids
  -> embedding + position
  -> bidirectional self-attention blocks
  -> pooled output hoặc token outputs
  -> task head
```

Đặc điểm:

- Mọi token thấy mọi token trong input, trừ padding.
- Output là vector contextual.
- Thường cần task-specific head.

Use cases:

- Classification.
- Embedding.
- Reranking.
- NER.
- Similarity scoring.

Rủi ro:

- Dùng sai tokenizer làm quality giảm mạnh.
- Truncate input làm mất thông tin quyết định.
- Dùng model multilingual/tiếng Việt không phù hợp domain.
- Deploy không pin label mapping gây đảo nhãn.

## 4. Decoder-only reference

```text
prompt tokens
  -> embedding + positional strategy, thường RoPE
  -> causal self-attention blocks
  -> language modeling head
  -> next-token logits
  -> decoding loop
```

Đặc điểm:

- Token chỉ thấy quá khứ.
- Output tự nhiên là text.
- Inference sinh token tuần tự.

Use cases:

- Chat.
- RAG generation.
- Tool/function calling.
- Code generation.
- Summarization linh hoạt.

Rủi ro:

- Output không deterministic nếu sampling.
- Prompt injection khi input có nội dung không tin cậy.
- Token cost tăng theo input và output.
- KV cache làm VRAM tăng theo concurrent sessions.
- Long context có thể làm latency và cost vượt SLA.

## 5. Encoder-decoder reference

```text
source tokens
  -> encoder bidirectional blocks
  -> encoder hidden states
target prefix tokens
  -> decoder causal self-attention
  -> cross-attention to encoder hidden states
  -> next target token
```

Đặc điểm:

- Encoder hiểu input nguồn.
- Decoder sinh output target.
- Cross-attention nối output đang sinh với source representation.

Use cases:

- Translation.
- Summarization.
- Data-to-text.
- Text normalization.
- Structured text generation cho domain ổn định.

Rủi ro:

- Serving vẫn có decode loop.
- Fine-tune cần cặp input-output tốt.
- Với chatbot tổng quát, decoder-only instruction model thường có ecosystem mạnh hơn.

## 6. Positional strategies

| Strategy | Cách hoạt động | Khi gặp trong thực tế | Ghi chú production |
|---|---|---|---|
| Sinusoidal | Cộng sin/cos vector vào embedding | Transformer gốc, bài học | Dễ hiểu, ít dùng trực tiếp trong LLM mới |
| Learned absolute | Học vector cho từng vị trí | BERT-style model | Không vượt max length tùy tiện |
| Relative position bias | Bias theo khoảng cách | T5-style hoặc biến thể | Cần đúng implementation |
| RoPE | Rotate Q/K theo position | LLaMA/Qwen-style LLM | Context scaling cần eval |
| ALiBi | Bias tuyến tính theo khoảng cách | Một số long-context model | Hữu ích cho extrapolation trong vài setting |

## 7. LayerNorm placement

Post-LN:

```text
x -> sublayer -> residual add -> LayerNorm
```

Pre-LN:

```text
x -> LayerNorm -> sublayer -> residual add
```

Khi dùng pretrained model:

- Không đổi Pre-LN/Post-LN.
- Không đổi epsilon hoặc norm type nếu không có lý do và eval.
- Một số LLM dùng RMSNorm thay vì LayerNorm; vai trò vẫn là ổn định activation.

## 8. FFN variants

FFN cổ điển:

```text
Linear -> GELU/ReLU -> Linear
```

Gated FFN:

```text
Linear gate + Linear up -> activation/gating -> Linear down
```

MoE FFN:

```text
router chọn một vài expert FFN cho mỗi token
```

Trade-off:

- FFN lớn tăng capacity nhưng tăng memory/latency.
- Gated FFN thường mạnh hơn MLP đơn giản nhưng tốn compute.
- MoE tăng parameter tổng nhưng có thể giữ activated parameters thấp; serving phức tạp hơn.

## 9. Inference constraints

### Latency

| Task | Kiến trúc thường hợp | Latency driver |
|---|---|---|
| Classification | Encoder-only | Input length, batch size, device |
| Embedding search | Encoder/bi-encoder | Query encode + vector DB latency |
| Reranking | Encoder cross-encoder | Số candidate cần rerank |
| Chat | Decoder-only | Context length + output tokens |
| Summarization | Decoder-only hoặc encoder-decoder | Input length + output tokens |

### Memory

Memory gồm:

- Model weights.
- Activation khi training.
- KV cache khi decoder inference.
- Batch buffers.
- Runtime overhead.

Approximation thường dùng:

```text
FP16 weights memory ~= parameters * 2 bytes
7B params FP16 ~= 14 GB chỉ riêng weights
```

KV cache có thể vượt weights bottleneck khi:

- Context dài.
- Batch/concurrency cao.
- Số layer/head lớn.
- Session streaming lâu.

### Context length

Context dài giúp nhét nhiều thông tin hơn nhưng:

- Attention/prefill đắt hơn.
- KV cache lớn hơn.
- Dễ mất thông tin ở giữa.
- Cost tăng.
- Debug khó hơn.

Rule thực dụng:

```text
RAG tốt + context vừa đủ thường production-friendly hơn long context không kiểm soát.
```

## 10. Architecture decision matrix

| Use case | Default architecture | Vì sao | Khi đổi hướng |
|---|---|---|---|
| Semantic search | Encoder embedding model | Precompute document vectors, query nhanh | Thêm cross-encoder reranker nếu relevance chưa đủ |
| Ticket classification | Encoder-only classifier | Nhanh, output ổn định, dễ đo metric | Dùng decoder-only khi label thay đổi liên tục và volume thấp |
| Chatbot | Decoder-only chat model | Sinh text tự nhiên, hỗ trợ instruction/tool | Dùng nhỏ hơn/hosted nếu cost hoặc ops là bottleneck |
| Summarization batch | Encoder-decoder hoặc decoder-only | Seq2seq rõ ràng hoặc prompt linh hoạt | Chunk/hierarchical nếu document dài |
| RAG assistant | Encoder retrieval + decoder generation | Tách retrieval và generation | Rerank nếu citation sai hoặc recall thấp |
| NER | Encoder-only token classifier | Cần vector từng token | LLM extraction chỉ khi schema thay đổi và volume thấp |

## 11. Production readiness checklist

- Task và output contract đã rõ.
- Baseline đơn giản đã có.
- Architecture được chọn theo latency/cost/privacy/license, không theo hype.
- Dataset/eval set có dữ liệu thật và edge cases.
- Metric chính đã rõ: accuracy, F1, MRR, nDCG, ROUGE, factuality, latency hoặc cost.
- Tokenizer/model/config được pin version.
- License model được xác nhận.
- Data privacy policy rõ: input nào được gửi ra ngoài, input nào phải self-host.
- Token budget và max context được cấu hình.
- Với decoder-only, có KV cache strategy, streaming và timeout.
- Có observability: model version, token count, truncation, latency, errors, quality feedback.
- Có rollback plan.
- Có human review cho high-risk output.

## 12. Common failure modes

| Failure mode | Thường gặp ở | Dấu hiệu | Cách giảm rủi ro |
|---|---|---|---|
| Mask sai | Training custom Transformer | Data leakage, metric quá đẹp | Unit test mask |
| Tokenizer mismatch | Tất cả | Quality giảm khó hiểu | Pin tokenizer cùng model |
| Label mapping sai | Classification | Label đảo hoặc sai ngẫu nhiên | Lưu id2label/label2id trong artifact |
| Context quá dài | Decoder-only/RAG | p99 cao, OOM, cost tăng | Token budget, retrieval, truncation policy |
| KV cache OOM | Chat serving | Request lỗi khi concurrency tăng | Limit sessions, batching, paged KV cache runtime |
| License không rõ | Model Hub/public weights | Không deploy được commercial | Review model card/license trước |
| Prompt injection | RAG/tool chatbot | Tool gọi sai, lộ data | Instruction hierarchy, tool allowlist, input isolation |
| Hallucination | Generation | Câu trả lời không có nguồn | Citation, retrieval eval, refusal policy |

## 13. Glossary

| Thuật ngữ | Giải thích ngắn |
|---|---|
| Embedding | Vector biểu diễn token |
| Hidden dimension | Kích thước vector nội bộ |
| Head | Một attention subspace |
| Multi-head attention | Nhiều attention head song song |
| Causal mask | Mask không cho token nhìn tương lai |
| Bidirectional attention | Token thấy cả trái và phải trong input |
| Cross-attention | Decoder attend vào encoder output |
| Positional encoding | Cách thêm thứ tự token |
| RoPE | Rotary Position Embedding |
| LayerNorm | Normalize activation theo hidden dimension |
| FFN | Feed-forward network áp dụng từng token |
| Residual connection | Cộng input với output sublayer |
| KV cache | Cache Key/Value cũ trong decoder inference |
| Prefill | Pha xử lý prompt/context ban đầu |
| Decode | Pha sinh từng token output |
| Context length | Số token tối đa model có thể xử lý |
| Token budget | Giới hạn token thiết kế cho request |

## 14. Tài liệu nên đọc

- "Attention Is All You Need": đọc architecture, scaled dot-product attention, multi-head attention, positional encoding và encoder-decoder stack.
- "The Illustrated Transformer": đọc để hình dung luồng dữ liệu.
- "The Annotated Transformer": đọc nếu muốn mapping công thức sang code.
- Model cards của BERT/PhoBERT/LLaMA/Qwen/T5 trước khi dùng trong dự án thật.

Khi đọc, không chỉ hỏi "model có mạnh không". Hãy hỏi:

```text
Model này có đúng task, đúng dữ liệu, đúng license, đúng latency và đúng vận hành không?
```
