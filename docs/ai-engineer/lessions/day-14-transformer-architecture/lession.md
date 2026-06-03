# Day 14: Transformer Architecture

## Mục tiêu học tập

Sau bài này, bạn cần làm được 5 việc:

- Vẽ được luồng dữ liệu của một Transformer từ text input đến output.
- Giải thích được encoder, decoder, encoder-only, decoder-only và encoder-decoder khác nhau ở mask, objective và output.
- Hiểu vai trò của positional encoding, RoPE, LayerNorm, FFN và residual connection.
- Chọn được kiến trúc phù hợp cho semantic search, classification, chatbot và summarization theo latency, cost, data privacy và license.
- Trả lời được câu hỏi production: dùng được không, dùng trong điều kiện nào, cần monitor gì.

## TL;DR

Transformer là kiến trúc xử lý sequence bằng cách lặp nhiều Transformer block. Mỗi block thường có self-attention để trộn thông tin giữa các token, FFN để biến đổi representation của từng token, residual connection để giữ đường đi ổn định cho gradient và LayerNorm để ổn định activation. Encoder-only model như BERT/PhoBERT mạnh cho classification, embedding và reranking. Decoder-only model như GPT, LLaMA, Qwen mạnh cho generation, chat và tool calling. Encoder-decoder model như T5 mạnh cho sequence-to-sequence task như translation và summarization có input rõ ràng.

Trong production, không chọn kiến trúc theo độ nổi tiếng của model. Hãy chọn theo task, latency target, context length, memory/VRAM, KV cache, throughput, data privacy, license và khả năng vận hành.

## 1. Transformer nối tiếp Day 13 như thế nào?

Day 13 tập trung vào attention: Query, Key, Value, scaled dot-product attention, self-attention, causal mask và multi-head attention.

Day 14 đặt attention vào một kiến trúc đầy đủ:

```text
Text
  -> tokenizer
  -> token ids
  -> token embedding
  -> cộng hoặc áp positional information
  -> nhiều Transformer blocks
  -> task head hoặc language modeling head
  -> output
```

Attention chỉ là một phần. Một Transformer production còn cần tokenizer đúng version, embedding table, positional strategy, LayerNorm placement, FFN, residual path, output head, decoding strategy, serving runtime và monitoring.

## 2. Luồng dữ liệu tổng quát

Ví dụ input:

```text
"Khách hàng muốn hoàn tiền vì đơn giao chậm"
```

Sau tokenization:

```text
[<cls>, "Khách", "hàng", "muốn", "hoàn", "tiền", "vì", "đơn", "giao", "chậm", <sep>]
```

Luồng qua Transformer encoder classifier:

```text
token ids
  -> token embedding:        [batch, seq_len, hidden_dim]
  -> positional information: [batch, seq_len, hidden_dim]
  -> block 1
  -> block 2
  -> ...
  -> block N
  -> lấy vector <cls>
  -> classification head
  -> label: "refund_request"
```

Luồng qua decoder-only chatbot:

```text
prompt tokens
  -> token embedding + position
  -> causal Transformer blocks
  -> logits cho token kế tiếp
  -> sample/greedy/beam
  -> append token mới
  -> lặp đến khi gặp stop token hoặc max_tokens
```

Khác biệt quan trọng: encoder xử lý toàn bộ input một lượt để tạo contextual vector; decoder-only sinh output từng token, nên latency tăng theo số output token.

## 3. Transformer block gồm những gì?

Một block hiện đại thường dùng dạng Pre-LN:

```text
                 +-----------------------------+
                 |                             |
x -------------- + --------------------------> + -> x1
|                |                             ^
|                v                             |
|          LayerNorm -> Multi-Head Attention ->|
|
|                +-----------------------------+
|                |                             |
x1 ------------- + --------------------------> + -> x2
                 |                             ^
                 v                             |
            LayerNorm -> FFN -> Dropout -------+
```

Dạng công thức:

```text
x1 = x + Attention(LayerNorm(x))
x2 = x1 + FFN(LayerNorm(x1))
```

Các thành phần chính:

| Thành phần | Vai trò | Điều cần nhớ |
|---|---|---|
| Token embedding | Biến token id thành vector | Là input representation học được |
| Positional information | Cho model biết thứ tự token | Self-attention tự thân không biết vị trí |
| Multi-head attention | Trộn thông tin giữa các token | Chi phí tăng mạnh theo sequence length |
| Residual connection | Giữ đường đi trực tiếp cho signal | Giúp train network sâu ổn định hơn |
| LayerNorm | Ổn định activation theo hidden dimension | Pre-LN thường ổn định hơn với model sâu |
| FFN | Biến đổi representation từng token | Không mix token; attention mới mix token |
| Dropout | Regularization khi training | Thường tắt trong inference |

## 4. Encoder

Encoder nhận toàn bộ input và cho mỗi token attend đến các token khác trong cùng sequence. Đây là bidirectional context.

```text
Input tokens: [t1, t2, t3, t4]

Token t1 thấy: t1, t2, t3, t4
Token t2 thấy: t1, t2, t3, t4
Token t3 thấy: t1, t2, t3, t4
Token t4 thấy: t1, t2, t3, t4
```

Encoder phù hợp khi output không cần sinh từng token tự do:

- Text classification: sentiment, intent, category, priority.
- Token classification: NER, POS tagging.
- Semantic embedding: biến text thành vector để search.
- Reranking: score relevance giữa query và document.
- Feature extraction: tạo representation cho downstream model.

Trong BERT-style classifier, vector `[CLS]` thường được đưa vào classification head:

```text
[CLS] tôi cần hoàn tiền [SEP]
  -> BERT encoder
  -> hidden state của [CLS]
  -> Linear layer
  -> label probabilities
```

Điểm mạnh:

- Hiểu context hai chiều tốt.
- Inference một lượt cho input cố định.
- Thường rẻ hơn decoder-only cho classification ngắn.

Điểm yếu:

- Không tự nhiên cho open-ended generation.
- Max length thường cố định và ngắn hơn LLM hiện đại.
- Cần fine-tune hoặc train head cho task cụ thể.

## 5. Decoder

Decoder trong Transformer gốc có 2 attention:

- Masked self-attention trên output đã sinh.
- Cross-attention sang encoder output.

Trong decoder-only LLM hiện đại, ta thường nói đến stack chỉ có causal self-attention:

```text
Token i chỉ được nhìn các token <= i
```

Causal mask:

```text
        attend to
        t1 t2 t3 t4
from t1  1  0  0  0
from t2  1  1  0  0
from t3  1  1  1  0
from t4  1  1  1  1
```

Training objective phổ biến:

```text
Input:  "Hà Nội là thủ đô của"
Target: "Việt Nam"
```

Model học predict next token. Khi inference, model lặp:

```text
prompt -> logits token kế tiếp -> chọn token -> append -> chạy tiếp
```

Điểm mạnh:

- Sinh text linh hoạt.
- Hợp với chatbot, reasoning, tool calling, code generation.
- Có thể làm nhiều task bằng prompt mà không cần train head riêng.

Điểm yếu:

- Latency phụ thuộc output length.
- Cần KV cache để inference hiệu quả.
- Tốn memory cho weights và KV cache.
- Dễ phát sinh hallucination, prompt injection, output không ổn định nếu không có guardrails/eval.

## 6. Encoder-only: BERT, PhoBERT

Encoder-only model dùng bidirectional attention và thường được pretrain bằng masked language modeling hoặc biến thể tương tự.

```text
"Tôi muốn [MASK] tiền"
  -> model dự đoán token bị mask: "hoàn"
```

BERT/PhoBERT phù hợp với:

- Classification tiếng Việt.
- Intent detection.
- Sentiment analysis.
- Named Entity Recognition.
- Embedding hoặc reranking, tùy model/head.

Decision rule:

```text
Nếu output là label, score hoặc vector -> ưu tiên encoder-only.
Nếu output là đoạn văn dài -> không ưu tiên encoder-only.
```

Production note:

- Model encoder nhỏ có thể chạy CPU nếu latency không quá chặt.
- GPU hoặc ONNX/quantization hữu ích khi throughput cao.
- Cần version chặt giữa tokenizer, model config và label mapping.
- Với tiếng Việt, kiểm tra tokenizer/preprocessing vì word segmentation có thể ảnh hưởng mạnh.

## 7. Decoder-only: GPT, LLaMA, Qwen

Decoder-only model dùng causal attention và next-token prediction. GPT, LLaMA, Qwen, Mistral và nhiều chat model hiện đại thuộc nhóm này.

Phù hợp với:

- Chatbot.
- General assistant.
- Code assistant.
- RAG generation.
- Tool/function calling.
- Drafting, rewriting, summarization bằng prompt.

Điểm production cần hiểu:

```text
total latency ~= prefill latency + decode latency * output_tokens
```

- Prefill: xử lý prompt/context ban đầu. Chi phí attention tăng theo context length.
- Decode: sinh từng token. KV cache giúp không tính lại K/V cũ.
- KV cache: tăng tốc decoding nhưng tốn VRAM theo batch, layers, heads, head_dim và context length.

Khi dùng decoder-only cho classification:

- Có thể prompt để model trả label.
- Nhưng nếu SLA chặt, label space ổn định và volume lớn, encoder-only fine-tuned thường rẻ và nhanh hơn.

## 8. Encoder-decoder: T5

Encoder-decoder có 2 phần:

```text
source text
  -> encoder tạo source representation
  -> decoder sinh target text, vừa nhìn target đã sinh vừa cross-attend sang encoder output
```

Luồng chi tiết:

```text
Input document
  -> encoder self-attention bidirectional
  -> encoder hidden states
  -> decoder masked self-attention trên output prefix
  -> decoder cross-attention vào encoder hidden states
  -> output token kế tiếp
```

T5 biến nhiều NLP task thành text-to-text:

```text
"summarize: <document>" -> "<summary>"
"translate English to Vietnamese: <text>" -> "<translation>"
"classify sentiment: <text>" -> "positive"
```

Phù hợp với:

- Translation.
- Summarization có input rõ.
- Data-to-text.
- Text normalization.
- Task sequence-to-sequence với format tương đối ổn định.

Trade-off:

- Có thể mạnh và gọn cho seq2seq chuyên biệt.
- Serving phức tạp hơn encoder-only vì vẫn phải decode token.
- Với chatbot tổng quát, decoder-only thường phổ biến hơn do ecosystem và instruction tuning.

## 9. Positional encoding

Self-attention nhìn một set token và tính similarity giữa Query/Key. Nếu không thêm thông tin vị trí, model khó phân biệt:

```text
"chó cắn người"
"người cắn chó"
```

Hai câu có token giống nhau nhưng ý nghĩa khác do thứ tự khác.

Các cách phổ biến:

| Cách | Ý tưởng | Ưu điểm | Hạn chế |
|---|---|---|---|
| Sinusoidal positional encoding | Cộng vector sin/cos theo vị trí | Không cần học thêm parameter, giải thích được | Không phải lựa chọn chính của nhiều LLM hiện đại |
| Learned absolute position | Học embedding riêng cho từng vị trí | Đơn giản, hiệu quả trong max length đã train | Khó extrapolate vượt max position |
| Relative position bias | Thêm bias theo khoảng cách tương đối | Tốt cho quan hệ gần/xa | Cần implementation đúng với architecture |
| RoPE | Rotate Query/Key theo vị trí | Phổ biến trong decoder-only LLM, hỗ trợ relative position tốt | Context extension cần cấu hình cẩn thận |
| ALiBi | Thêm bias tuyến tính theo khoảng cách | Có thể extrapolate tốt trong một số setting | Không phải mặc định của mọi model |

## 10. RoPE

RoPE là Rotary Position Embedding. Thay vì cộng position vector vào embedding, RoPE xoay các chiều của Query và Key theo vị trí token.

Trực giác:

```text
Q(token, position i) được xoay theo i
K(token, position j) được xoay theo j
Dot product giữa Q_i và K_j chứa thông tin khoảng cách i - j
```

Vì sao RoPE quan trọng trong LLM hiện đại:

- Giúp attention nhận biết vị trí tương đối.
- Phù hợp với causal decoder.
- Được dùng rộng rãi trong LLaMA/Qwen-style model.
- Có nhiều kỹ thuật context extension dựa trên RoPE scaling.

Production note:

- Không tự đổi RoPE config nếu không hiểu model đã train thế nào.
- Context extension bằng RoPE scaling cần eval riêng; model có thể chạy được nhưng quality giảm ở đoạn dài.
- Khi load model, tokenizer, config và RoPE parameters phải đi cùng version.

## 11. LayerNorm

LayerNorm normalize activation theo hidden dimension của từng token:

```text
token vector x -> normalize mean/variance -> scale + bias
```

Tác dụng:

- Ổn định training.
- Giảm activation quá lớn hoặc quá lệch giữa layers.
- Giúp optimizer làm việc dễ hơn với network sâu.

Post-LN trong Transformer gốc:

```text
x -> sublayer -> residual add -> LayerNorm
```

Pre-LN phổ biến trong nhiều model hiện đại:

```text
x -> LayerNorm -> sublayer -> residual add
```

Trade-off:

- Pre-LN thường ổn định hơn khi train model sâu.
- Post-LN có thể cho behavior khác về gradient và final representation.
- Khi dùng pretrained model, không thay đổi placement của LayerNorm; đó là một phần architecture đã train.

## 12. FFN

FFN trong Transformer thường là MLP áp dụng độc lập cho từng token:

```text
FFN(x) = Linear(hidden_dim -> intermediate_dim)
       -> activation, thường GELU/SwiGLU
       -> Linear(intermediate_dim -> hidden_dim)
```

FFN không mix thông tin giữa các token. Attention đã làm việc đó. FFN xử lý từng token sau khi token đã nhận context.

Trực giác:

```text
attention: token này cần lấy gì từ token khác?
FFN: sau khi có context, biến đổi feature của token này như thế nào?
```

Production note:

- FFN thường chiếm phần lớn parameter và compute trong nhiều Transformer.
- Một số LLM dùng gated FFN như SwiGLU thay vì GELU MLP đơn giản.
- Quantization ảnh hưởng mạnh đến cả attention projection và FFN weights; phải eval chất lượng sau quantization.

## 13. Residual connection

Residual connection cộng input ban đầu vào output của sublayer:

```text
x_next = x + sublayer(x)
```

Tác dụng:

- Cho signal và gradient có đường đi ngắn hơn qua nhiều layers.
- Cho layer học phần delta thay vì học lại toàn bộ representation.
- Giảm rủi ro model sâu bị degrade khi thêm layers.

Nếu bỏ residual connection, Transformer sâu thường khó train hơn nhiều.

## 14. So sánh architecture

| Architecture | Mask | Objective phổ biến | Output tự nhiên | Ví dụ | Nên dùng khi |
|---|---|---|---|---|---|
| Encoder-only | Bidirectional | Masked LM, classification fine-tune | Vector, label, score | BERT, PhoBERT | Classification, embedding, reranking |
| Decoder-only | Causal | Next-token prediction | Text sinh tự do | GPT, LLaMA, Qwen | Chat, RAG answer, tool calling, code |
| Encoder-decoder | Encoder bidirectional, decoder causal + cross-attention | Seq2seq text-to-text | Text target | T5 | Translation, summarization, text normalization |

## 15. Latency, memory, KV cache và context length

### Encoder-only latency

Encoder xử lý input trong một forward pass:

```text
latency ~= tokenization + encoder_forward + head
```

Nếu `seq_len` tăng, attention cost tăng gần bậc hai. Nhưng với classification, output chỉ là label nên không có decode loop.

### Decoder-only latency

Decoder-only có 2 pha:

```text
prefill: xử lý prompt/context ban đầu
decode: sinh từng token output
```

Nếu prompt dài, prefill chậm. Nếu output dài, decode chậm.

```text
request latency ~= prefill(context_tokens) + output_tokens * per_token_decode
```

### KV cache

Khi sinh token thứ 100, nếu không cache, model phải tính lại Key/Value cho 99 token trước. KV cache lưu K/V cũ để token mới chỉ cần tính phần mới.

Trade-off:

- Tăng tốc generation.
- Tốn VRAM theo batch size, number of layers, number of heads, head dimension và context length.
- Với nhiều concurrent users, KV cache có thể là bottleneck chính, không phải weights.

### Context length

Context dài không miễn phí:

- Attention memory/compute tăng mạnh.
- KV cache tăng theo sequence length.
- Long prompt làm p95/p99 latency xấu.
- Model có thể bị lost-in-the-middle, không dùng tốt thông tin ở giữa context.

Production guidance:

- Đặt token budget theo use case, không default max context.
- Với RAG, ưu tiên retrieval/chunking/reranking tốt hơn là nhét mọi tài liệu vào context.
- Monitor token distribution, truncation rate, p95 latency, VRAM usage và OOM.

## 16. Chọn kiến trúc cho bài toán gần production

### Case A: semantic search nội bộ

Yêu cầu:

- Query tiếng Việt.
- Search tài liệu công ty.
- Latency p95 dưới 300 ms cho retrieval.
- Dữ liệu có thể có thông tin nội bộ.

Khuyến nghị:

```text
embedding model: encoder-only hoặc bi-encoder sentence embedding
reranker: encoder cross-encoder nếu cần quality cao
generator: không cần nếu chỉ search; dùng decoder-only nếu có RAG answer
```

Trade-off:

- Bi-encoder nhanh vì precompute document embedding.
- Cross-encoder reranker chất lượng cao hơn nhưng chậm hơn vì phải score từng cặp query-document.
- Self-host nếu data privacy không cho gửi query/document ra external API.

### Case B: ticket classification

Yêu cầu:

- Gán label: billing, refund, shipping, account.
- 200 requests/second.
- Label ổn định.
- Chi phí thấp.

Khuyến nghị:

```text
baseline: TF-IDF + Logistic Regression
production v1: encoder-only fine-tuned BERT/PhoBERT
không ưu tiên: decoder-only prompt classification nếu volume lớn và SLA chặt
```

Trade-off:

- Encoder-only nhanh, output ổn định, dễ đo F1/confusion matrix.
- Decoder-only dễ prototype nhưng tốn token, latency cao hơn và output cần parse/validate.
- Nếu data nhạy cảm, self-host encoder nhỏ dễ hơn self-host LLM lớn.

### Case C: chatbot CSKH có RAG

Yêu cầu:

- Trả lời tự nhiên.
- Có citation từ knowledge base.
- Có tool lookup order.
- Cần guardrails.

Khuyến nghị:

```text
retrieval embedding: encoder model
reranking: encoder cross-encoder hoặc lightweight reranker
generator: decoder-only instruction/chat model
tool calling: controlled schema + allowlist
```

Trade-off:

- Decoder-only cần KV cache, streaming và rate limit.
- RAG giảm hallucination nhưng không loại bỏ hoàn toàn.
- External model nhanh triển khai nhưng cần kiểm tra data policy.
- Self-host tăng privacy/control nhưng cần GPU, autoscaling, monitoring và on-call.

### Case D: summarization tài liệu pháp lý

Yêu cầu:

- Input dài.
- Output có format: facts, obligations, risks.
- Không được bịa.
- Có thể chạy batch qua đêm.

Khuyến nghị:

```text
option 1: encoder-decoder/T5-style model fine-tuned nếu domain và format rất ổn định
option 2: decoder-only long-context model + chunked summarization + verification nếu cần linh hoạt
```

Trade-off:

- Encoder-decoder tốt cho seq2seq cố định nhưng ecosystem serving có thể ít tiện hơn decoder-only chat model.
- Decoder-only linh hoạt hơn nhưng phải kiểm soát hallucination, citation và output schema.
- Với tài liệu dài, dùng hierarchical summarization thay vì nhét toàn bộ context nếu latency/cost cao.

## 17. Dùng được trong production không?

Có, Transformer dùng được trong production và thực tế đang là nền tảng của nhiều hệ thống NLP/LLM. Nhưng điều kiện tối thiểu là:

- Chọn architecture theo task, không chọn theo hype.
- Có eval set đại diện dữ liệu thật, gồm cả edge cases và negative cases.
- Có baseline đơn giản để so sánh, ví dụ rule/TF-IDF/logistic trước khi fine-tune model lớn.
- Pin version tokenizer, model weights, config, label mapping và prompt/template.
- Kiểm tra license model cho commercial/internal use.
- Có policy cho PII, retention, logging và data residency.
- Benchmark latency, throughput, memory/VRAM, context length và cost/request trên hardware thật.
- Có monitoring: p50/p95/p99 latency, error rate, token usage, OOM, truncation rate, output quality, user feedback.
- Có rollback path khi model upgrade làm giảm quality.
- Có guardrails nếu model sinh text, gọi tool hoặc đọc dữ liệu không tin cậy.

Không nên đưa vào production nếu:

- Chưa rõ license.
- Chưa có eval set.
- Chưa biết tokenizer/model version nào đang chạy.
- Chưa đo latency/memory trên traffic thật.
- Chưa có cách rollback.
- Với LLM generation, chưa có output validation, safety policy hoặc human escalation cho case rủi ro cao.

## 18. Checklist đọc paper/tài liệu

Khi đọc "Attention Is All You Need", "The Illustrated Transformer" hoặc model paper mới, dùng checklist này:

- Architecture thuộc encoder-only, decoder-only hay encoder-decoder?
- Input/output contract là gì?
- Attention mask là bidirectional, causal, sliding window hay biến thể khác?
- Positional strategy là sinusoidal, learned, relative bias, RoPE hay ALiBi?
- LayerNorm là Pre-LN hay Post-LN?
- FFN dùng GELU, SwiGLU hay MoE?
- Context length lúc train là bao nhiêu?
- Training objective là masked LM, next-token prediction, seq2seq hay instruction tuning?
- Model size, number of layers, hidden size, heads, vocab size là bao nhiêu?
- Dataset/language/domain có khớp use case không?
- License có cho phép mục tiêu sử dụng không?
- Serving yêu cầu GPU/CPU/TPU, memory, quantization, KV cache như thế nào?
- Paper report metric nào, có metric nào gần production use case của mình không?
- Failure modes hoặc limitations được tác giả nêu là gì?

## 19. Tự kiểm tra nhanh

1. Vì sao self-attention cần positional information?
2. Encoder-only và decoder-only khác nhau ở mask và training objective nào?
3. FFN làm gì nếu nó không mix token?
4. Residual connection giúp gì khi stack nhiều Transformer blocks?
5. KV cache giải quyết vấn đề gì và đổi lại tốn gì?
6. Khi nào classification bằng BERT/PhoBERT hợp lý hơn prompt GPT-style model?
7. Khi nào T5/encoder-decoder đáng cân nhắc hơn decoder-only?
8. Vì sao long context không thay thế retrieval design tốt?

## 20. Kết nối sang Day 15 và Day 16

Day 15 sẽ dùng HuggingFace ecosystem để load tokenizer/model, đọc model card, chạy inference và kiểm tra license/intended use. Day 16 sẽ fine-tune PhoBERT/BERT classifier. Vì vậy sau Day 14, bạn nên đã có quyết định rõ:

```text
Task Day 16 là classification -> ưu tiên encoder-only -> BERT/PhoBERT-style model.
```

Decoder-only vẫn quan trọng cho các ngày sau về LLM application, RAG, tool calling và agent workflow.
