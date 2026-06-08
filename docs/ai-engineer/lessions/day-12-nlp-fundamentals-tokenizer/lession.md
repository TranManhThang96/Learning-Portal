# Day 12: NLP Fundamentals & Tokenizer

## Mục tiêu

Sau bài này, bạn cần làm được các việc sau:

- Giải thích được pipeline `raw text -> normalized text -> tokens -> token ids -> tensors -> model`.
- Biết nên preprocessing text ở mức nào, không làm mất tín hiệu quan trọng của tiếng Việt.
- Phân biệt được BPE, WordPiece, SentencePiece/Unigram ở mức ứng dụng.
- Hiểu vocabulary, special tokens, OOV/UNK, padding, truncation, attention mask và offset mapping.
- Ước lượng được token limit, latency và cost/request trước khi đưa NLP/LLM vào production.
- Nhận diện được vì sao tiếng Việt có dấu, không dấu, tách âm tiết bằng khoảng trắng và word segmentation làm tokenization khó hơn English.
- Dùng được tokenizer wrapper có config, batch tokenization, token stats, cost estimator và warning khi input quá dài.

## Liên kết với các ngày trước và sau

Day 11 nói về training loop: model chỉ nhận tensor, loss chỉ tính trên tensor, optimizer chỉ update weights. Day 12 trả lời câu hỏi: text thật của user biến thành tensor như thế nào?

Day 13 nói về attention: attention làm việc trên sequence token embedding và cần mask đúng. Nếu tokenizer, padding hoặc truncation sai, attention phía sau cũng sai.

Day 16 sẽ fine-tune BERT/PhoBERT classifier. Nếu train và inference dùng khác tokenizer hoặc khác preprocessing, model có thể giảm chất lượng rất mạnh dù training loop không báo lỗi.

## TL;DR

Tokenizer là contract giữa raw text và model weights. Cùng một câu nhưng dùng tokenizer khác sẽ ra token ids khác, nghĩa là model đang nhìn một input khác. Với LLM/RAG, token không chỉ là chi tiết kỹ thuật; token quyết định context budget, latency, memory, throughput và tiền.

Trong production, không được xem tokenizer là helper phụ. Nó là một phần của model artifact, phải được version cùng model, được test bằng dữ liệu thật và được monitor bằng token length distribution, truncation rate, OOV/UNK rate nếu có.

## 1. NLP pipeline nhìn từ góc Senior SE

Pipeline tối giản:

```text
raw text
  -> input validation
  -> text preprocessing / normalization
  -> tokenization
  -> token ids + attention mask
  -> embedding lookup
  -> model forward
  -> output decoding / post-processing
```

Map sang backend:

| NLP concept | SE analogy |
|---|---|
| Raw text | HTTP request body chưa validate |
| Preprocessing | Input validation + canonicalization |
| Tokenizer | Parser + schema encoder |
| Vocabulary | Dictionary/index mapping stable |
| Token id | Internal enum/id mà model đã học |
| Attention mask | Mask/filter để bỏ qua padding |
| Truncation | Data loss policy |
| Context window | Request payload limit |
| Token cost | Billing unit + compute unit |

Điểm quan trọng: model không hiểu string trực tiếp. Model học embedding cho từng token id trong vocabulary. Nếu token id thay đổi, embedding lookup thay đổi; nếu preprocessing khác nhau giữa train và inference, đó là train-serving skew.

## 2. Text preprocessing: làm đủ, đừng làm quá tay

Preprocessing là bước biến raw text thành input ổn định hơn. Nhưng với Transformer/LLM, nhiều kỹ thuật "clean text" kiểu truyền thống có thể làm mất thông tin.

### Step 1: xác định mục tiêu

Trước khi clean text, hỏi:

- Đây là text classification, search, RAG, summarization hay generation?
- Model là traditional ML, BERT-style encoder, PhoBERT, hay GPT-style LLM?
- Có cần giữ case, punctuation, URL, code, số hợp đồng, emoji, markdown không?
- Có được phép log raw text không, hay cần redaction PII?
- Input user có tiếng Việt không dấu, có dấu, code-mixing Việt/English không?

Không có preprocessing tốt nhất cho mọi bài toán.

### Step 2: những xử lý thường nên làm

Các bước sau thường an toàn nếu được test:

- Validate input type, size và encoding.
- Normalize Unicode về `NFC` để giảm khác biệt biểu diễn ký tự có dấu.
- Normalize whitespace: chuyển nhiều khoảng trắng, tab, newline không cần thiết về một format nhất quán.
- Loại bỏ control characters vô hình như zero-width space nếu chúng không có ý nghĩa nghiệp vụ.
- Parse HTML/Markdown bằng parser nếu nguồn là HTML/Markdown thật.
- Chuẩn hóa line ending nếu pipeline dùng text document.
- Redact PII trong log/debug output, không nhất thiết trong input đưa vào model.

### Step 3: những xử lý phải cân nhắc kỹ

| Xử lý | Khi có thể dùng | Rủi ro |
|---|---|---|
| Lowercase | Baseline truyền thống, model uncased | Mất entity, mã lỗi, SKU, tên riêng |
| Xóa dấu tiếng Việt | Matching thô hoặc search tolerant | Mất nghĩa: `ma`, `má`, `mà`, `mã`, `mạ` |
| Xóa punctuation | TF-IDF/simple text cleanup | Mất intent, code, URL, markdown, câu hỏi |
| Xóa stopwords | Bag-of-words truyền thống | Thường không cần với Transformer/LLM |
| Stemming/lemmatization | Một số pipeline cổ điển | Tiếng Việt và code-mixing dễ sai |
| Dịch tiếng Việt sang English | Dùng model chỉ mạnh English | Thêm latency, cost, lỗi dịch, mất sắc thái |

Với BERT/PhoBERT/LLM, nguyên tắc mặc định là normalize nhẹ, giữ thông tin, rồi để tokenizer/model xử lý. Chỉ xóa hoặc biến đổi mạnh khi bạn có benchmark chứng minh tốt hơn.

## 3. Tokenization là gì?

Tokenization biến text thành chuỗi token. Token có thể là:

- Word: `xin`, `chào`.
- Subword: `token`, `##izer`, `ngôn`, `_ngữ`.
- Character hoặc byte.
- Special token: `[CLS]`, `[SEP]`, `[PAD]`, `[UNK]`, `<s>`, `</s>`, `<mask>`.

Pipeline:

```text
"Tôi đang học NLP"
  -> ["Tôi", "đang", "học", "NL", "##P"]
  -> [101, 1945, 1234, 5678, 9101, 102]
  -> embedding vectors
```

Các token string chỉ để người đọc debug. Model thật dùng token ids.

## 4. Vocabulary, token ids và special tokens

Vocabulary là mapping ổn định từ token sang id:

```text
"[PAD]" -> 0
"[UNK]" -> 100
"[CLS]" -> 101
"xin"   -> 12345
```

Embedding matrix của model có một row cho mỗi token id. Vì vậy:

- Đổi tokenizer là breaking change với model.
- Đổi thứ tự vocabulary là breaking change.
- Thêm token mới cần resize embedding và fine-tune/retrain phù hợp.
- Cùng một text, token ids phải giống giữa training, evaluation và inference.

Special tokens thường gặp:

| Token | Vai trò |
|---|---|
| `[PAD]` | Pad batch về cùng chiều dài |
| `[UNK]` | Token unknown nếu tokenizer không encode được |
| `[CLS]` | Đại diện sequence trong BERT classifier |
| `[SEP]` | Ngăn cách sentence/pair input trong BERT |
| `[MASK]` | Masked language modeling |
| `<s>`, `</s>` | Begin/end sequence trong một số model |
| `<bos>`, `<eos>` | Begin/end of sequence trong nhiều LLM |

## 5. OOV và UNK

OOV là out-of-vocabulary: text chứa từ hoặc ký tự tokenizer không có trong vocabulary.

Word-level tokenizer dễ OOV:

```text
"tokenizerization" -> [UNK]
```

Subword tokenizer giảm OOV:

```text
"tokenizerization" -> ["token", "##izer", "##ization"]
```

Byte-level tokenizer còn giảm OOV hơn nữa vì gần như mọi text có thể biểu diễn bằng byte. Nhưng "không bị UNK" không có nghĩa model hiểu tốt. Model có thể encode được mã lỗi lạ, tên sản phẩm mới hoặc tiếng Việt không dấu, nhưng semantic quality vẫn phụ thuộc dữ liệu pretraining/fine-tuning.

Production signal:

- UNK rate tăng sau release có thể báo domain drift.
- Nhiều token rất nhỏ cho cùng một từ có thể làm token count tăng, latency tăng và quality giảm.
- Không nên chỉ kiểm tra câu English sạch; cần sample tiếng Việt thật từ production.

## 6. BPE, WordPiece và SentencePiece

### BPE

BPE là subword algorithm bắt đầu từ vocabulary nhỏ như character/byte, rồi học merge rules bằng cách ghép các cặp token xuất hiện thường xuyên.

Ví dụ trực giác:

```text
["t", "o", "k", "e", "n"]
-> merge "t" + "o" = "to"
-> merge "to" + "k" = "tok"
-> ...
```

Khi dùng:

- GPT-style tokenizer thường dùng byte-level BPE.
- RoBERTa-style tokenizer dùng BPE.
- PhoBERT là RoBERTa-style cho tiếng Việt và thường cần đúng preprocessing/word segmentation theo model.

Trade-off:

- Ít OOV, hợp open vocabulary.
- Token preview có thể khó đọc.
- Token count khó đoán bằng word count, nhất là với tiếng Việt có dấu hoặc text code-mixed.

### WordPiece

WordPiece phổ biến trong BERT. Nó học subword theo scoring khác BPE, và khi encode thường chọn subword dài nhất có trong vocabulary từ trái sang phải. Continuation token hay có prefix `##`.

Ví dụ trực giác:

```text
"tokenizer" -> ["token", "##izer"]
```

Khi dùng:

- BERT và nhiều BERT-style encoder.
- Text classification, NER, reranking, embedding model kiểu encoder.

Trade-off:

- Dễ debug hơn byte-level BPE trong nhiều trường hợp.
- Có thể sinh `[UNK]` nếu gặp input quá lạ tùy tokenizer.
- Với tiếng Việt, từ có dấu, không dấu và cách viết khác nhau có thể tách rất khác.

### SentencePiece và Unigram

SentencePiece là framework/tokenizer library thường train trực tiếp trên raw text và xem whitespace như một symbol, ví dụ token có ký hiệu `▁` để đánh dấu đầu từ. SentencePiece có thể dùng Unigram hoặc BPE bên dưới.

Unigram thường bắt đầu từ vocabulary lớn, rồi loại dần token để tối ưu loss trên corpus. Khi encode, nó chọn segmentation có xác suất tốt nhất theo model.

Khi dùng:

- Nhiều multilingual model, T5-style model và một số LLaMA-style tokenizer.
- Bài toán có nhiều ngôn ngữ, không muốn phụ thuộc pre-tokenizer theo whitespace truyền thống.

Trade-off:

- Hợp multilingual và raw text.
- Token nhìn lạ hơn với người debug.
- Vẫn phải dùng đúng tokenizer đi kèm model.

## 7. Padding, truncation, attention mask và offsets

Model training/inference theo batch cần tensor cùng shape. Text thì dài ngắn khác nhau, nên cần padding:

```text
input_ids:
  [101, 10, 11, 102,   0,   0]
  [101, 20, 21,  22,  23, 102]

attention_mask:
  [  1,  1,  1,   1,   0,   0]
  [  1,  1,  1,   1,   1,   1]
```

`attention_mask = 0` cho model biết vị trí đó là padding, không phải nội dung thật.

Truncation là cắt input nếu vượt `max_length`. Đây là nơi dễ có bug production:

- Ticket dài bị cắt mất error code ở cuối.
- Contract bị cắt mất điều khoản quan trọng.
- Chat history bị cắt mất system instruction.
- RAG context bị cắt mất citation/source.

Các policy thường dùng:

| Policy | Khi dùng | Rủi ro |
|---|---|---|
| Reject | API cần độ chính xác cao, input vượt budget là lỗi rõ ràng | User phải sửa input hoặc hệ thống phải hướng dẫn |
| Truncate tail | Thông tin quan trọng thường ở đầu | Mất kết luận/cuối tài liệu |
| Truncate head | Chat history, log tail quan trọng hơn | Mất instruction hoặc background |
| Sliding window | Document dài, cần xử lý từng cửa sổ | Tăng compute và cần merge result |
| Summarize/compress | LLM/RAG input dài | Thêm model call, có thể mất chi tiết |

Offset mapping ánh xạ token về vị trí ký tự trong text gốc. Nó hữu ích cho NER, highlight citation, debug chunking. Với Hugging Face, `return_offsets_mapping` chỉ hoạt động với fast tokenizer.

## 8. Dùng Hugging Face tokenizer từng bước

Phần này minh họa API hiện hành đã đối chiếu qua Context7. Cài dependency trong môi trường ảo:

```bash
python3 -m pip install transformers tokenizers sentencepiece
```

### Step 1: load đúng tokenizer của model

```python
from transformers import AutoTokenizer

model_id = "bert-base-multilingual-cased"
revision = "main"  # Demo only; production thay bằng commit SHA.
tokenizer = AutoTokenizer.from_pretrained(
    model_id,
    revision=revision,
    use_fast=True,
)
```

`AutoTokenizer` đọc config trong model repository và chọn tokenizer class tương ứng. Trong production:

- Pin model/tokenizer revision bằng commit SHA bất biến.
- Cache hoặc mirror artifact theo policy của công ty.
- Không thay tokenizer chỉ vì tokenizer khác tạo ít token hơn; weights đã học theo vocabulary cũ.

### Step 2: quan sát token trước khi tạo batch

```python
text = "Khách hàng báo lỗi thanh toán PAY_403."
tokens = tokenizer.tokenize(text)
token_ids = tokenizer.encode(text, add_special_tokens=True)

print(tokens)
print(token_ids)
print(tokenizer.convert_ids_to_tokens(token_ids))
```

Đây là bước debug. Training/inference thực tế nên gọi tokenizer trên batch thay vì lặp từng text bằng Python.

### Step 3: tạo batch tensors

```python
texts = [
    "Sản phẩm tốt.",
    "Khách hàng muốn hoàn tiền vì đơn giao chậm.",
]

encoded = tokenizer(
    texts,
    padding="longest",
    truncation=True,
    max_length=128,
    return_attention_mask=True,
    return_tensors="pt",
)

print(encoded["input_ids"].shape)
print(encoded["attention_mask"].shape)
```

Ý nghĩa tham số:

| Tham số | Behavior | Trade-off |
|---|---|---|
| `padding="longest"` | Pad đến câu dài nhất trong batch | Ít waste hơn, shape thay đổi |
| `padding="max_length"` | Pad cố định đến `max_length` | Shape ổn định, có thể waste nhiều |
| `truncation=True` | Cắt sequence vượt giới hạn | Có nguy cơ mất dữ liệu âm thầm |
| `max_length=128` | Budget token của batch | Phải chọn từ phân phối dữ liệu thật |
| `return_tensors="pt"` | Trả PyTorch tensors | Sẵn sàng đưa vào model |

`pad_to_multiple_of=8` có thể giúp một số GPU/Tensor Core workload khi padding đã bật, nhưng phải benchmark; nó cũng tạo thêm PAD.

### Step 4: offset mapping cho NER/citation

```python
encoded = tokenizer(
    "Tôi cần hoàn tiền.",
    return_offsets_mapping=True,
    add_special_tokens=True,
)

for token_id, (start, end) in zip(
    encoded["input_ids"],
    encoded["offset_mapping"],
):
    print(tokenizer.convert_ids_to_tokens(token_id), start, end)
```

`return_offsets_mapping` chỉ có ở fast tokenizer. Special token thường có offset `(0, 0)`, nên code highlight phải bỏ qua chúng.

### Step 5: không silent truncation

Đếm length chưa truncate trước, sau đó mới áp policy:

```python
raw = tokenizer(
    texts,
    padding=False,
    truncation=False,
    add_special_tokens=True,
)
lengths = [len(ids) for ids in raw["input_ids"]]

too_long = [length for length in lengths if length > max_length]
if too_long:
    raise ValueError(
        f"{len(too_long)} inputs exceed max_length={max_length}; "
        f"max_seen={max(too_long)}"
    )
```

Nếu business cho phép truncate, log count/rate và loại policy đã dùng. Với pair input, chọn rõ `"longest_first"`, `"only_first"` hoặc `"only_second"` thay vì dựa vào default mà team không hiểu.

### Step 6: production wrapper cần contract gì?

Wrapper ở [document.md](./document.md) là reference đầy đủ. Dù triển khai cách nào, contract cần có:

- Model/tokenizer ID và immutable revision.
- Normalization version.
- `max_length`, padding và truncation policy.
- Batch input validation.
- Token length stats trước truncation.
- Stable output gồm `input_ids`, `attention_mask` và optional offsets.
- Metric latency, p50/p95/p99 token length, rejection/truncation count.
- Test golden samples tiếng Việt có dấu, không dấu, code-mixed và mã lỗi.

## 9. Token limit, latency và cost

Token budget trong một LLM request:

```text
total_tokens =
  system_prompt_tokens
  + user_message_tokens
  + chat_history_tokens
  + retrieved_context_tokens
  + tool_schema_tokens
  + reserved_output_tokens
  + special_tokens_overhead
```

Nếu context window là 8,192 tokens và bạn reserve 1,000 output tokens, input budget thực tế không phải 8,192 mà khoảng 7,192 trừ overhead.

Cost estimate:

```text
cost_usd =
  input_tokens  / 1_000_000 * input_price_per_1m
  + output_tokens / 1_000_000 * output_price_per_1m
```

Latency và memory:

- Tokenization tốn CPU, đặc biệt khi QPS cao hoặc document dài.
- Model inference tăng theo input length; Day 13 sẽ giải thích self-attention có chi phí gần `O(n^2)` theo sequence length cho nhiều kiến trúc.
- Decoder-only LLM còn tốn KV cache theo số token đã xử lý.
- Padding quá dài làm lãng phí compute; dynamic padding theo batch thường tốt hơn padding toàn bộ về max length cố định.

Production metrics nên log:

- `input_tokens`, `output_tokens`, `total_tokens`.
- `p50/p95/p99 input_tokens`.
- `truncation_count`, `truncation_rate`.
- `rejected_too_long_count`.
- `cost_per_request`, `cost_per_tenant`, `cost_per_feature`.
- `tokenization_latency_ms`, `model_latency_ms`.

Không log raw text nếu có PII hoặc dữ liệu khách hàng nhạy cảm.

## 10. Tiếng Việt bị tokenize như thế nào?

Tiếng Việt có vài điểm khác English:

### Khoảng trắng thường tách âm tiết, không chắc tách từ

Trong English, whitespace thường gần với word boundary:

```text
"natural language processing" -> 3 words
```

Trong tiếng Việt:

```text
"xử lý ngôn ngữ tự nhiên"
```

Chuỗi này có nhiều âm tiết, nhưng concept có thể là:

```text
"xử_lý" "ngôn_ngữ" "tự_nhiên"
```

Một số model tiếng Việt như PhoBERT được train với text đã word-segmented, thường nối các âm tiết trong cùng một từ bằng `_`. Nếu fine-tune hoặc inference PhoBERT cho classifier, bạn cần theo đúng hướng dẫn preprocessing/tokenizer của model đang dùng.

### Có dấu và không dấu là input khác

```text
"ma" "má" "mà" "mã" "mạ"
```

Các chuỗi này khác Unicode, khác token và khác nghĩa. Xóa dấu có thể giúp một số search tolerant, nhưng với classification/LLM thường làm mất semantic signal.

### Code-mixing rất phổ biến

Ticket thật có thể như sau:

```text
"Khách hàng báo lỗi thanh toán PAY_403 lúc 09:30, cần retry idempotent."
```

Tokenizer có thể tách `PAY_403`, số giờ, dấu `_`, English term và tiếng Việt thành nhiều token nhỏ. Nếu hệ thống support/RAG dùng nhiều mã lỗi, SKU, log line, bạn phải test token count trên dữ liệu thật.

### Token count tiếng Việt có thể cao hơn bạn đoán

Không nên dùng character count hoặc word count để suy ra token count. Một đoạn 500 từ tiếng Việt có thể có token count khác nhiều so với 500 từ English, tùy tokenizer.

Best practice:

- Đếm token bằng đúng tokenizer của model sẽ dùng.
- Benchmark câu có dấu, không dấu, code-mixed, markdown, bảng, JSON, log line.
- Với RAG, chunk theo token và validate retrieval quality, không chunk cứng theo số ký tự.

## 11. Best solution theo context

| Context | Khuyến nghị | Lý do |
|---|---|---|
| Fine-tune BERT/PhoBERT classifier | Dùng đúng `AutoTokenizer` và preprocessing của model; `max_length` 128/256/512 sau khi đo p95 | Chất lượng phụ thuộc train/inference consistency |
| Vietnamese enterprise RAG | Chunk theo token của embedding/generator, giữ metadata, overlap vừa đủ, reserve output budget | Tránh overflow context và mất citation |
| LLM chatbot có chat history | Đếm token mỗi turn, trim/summarize history có policy, không cắt system prompt | Giữ instruction và kiểm soát cost |
| Search baseline nhanh | Có thể dùng lowercase/normalize nhẹ + TF-IDF/BM25 | Rẻ, explainable, đủ tốt cho baseline |
| NER/highlight citation | Dùng fast tokenizer và offset mapping | Cần map token về text gốc |
| High-QPS service | Batch tokenization, dynamic padding, cache tokenized static docs | Giảm CPU và waste compute |

## 12. Dùng được trong production không?

Có, tokenizer và preprocessing pipeline dùng được trong production, nhưng cần các điều kiện sau:

- Version tokenizer cùng model artifact, config, label mapping và preprocessing code.
- Train, validation, batch inference và online inference dùng cùng contract.
- Có hard limit cho input tokens và reserved output tokens.
- Không silent truncation; nếu truncate phải log và có policy rõ.
- Có token stats trên dữ liệu thật: p50/p95/p99, max, too-long rate.
- Có test cho tiếng Việt có dấu, không dấu, code-mixed, mã lỗi, markdown, JSON/log.
- Không log raw PII; chỉ log length, hash/request id hoặc sample đã redact.
- Có cost estimator theo model price hiện tại và budget theo tenant/feature.
- Có fallback: reject rõ ràng, ask user shorten, summarize/compress, hoặc split document.

Không nên đưa vào production nếu:

- Chưa biết tokenizer đang dùng có đúng với model không.
- Đang rely vào default truncation mà không log.
- Chunking dựa hoàn toàn vào character count.
- Chưa test tiếng Việt thật.
- Không có giới hạn cost/request.

## 13. Thứ tự học và thực hành

1. Đọc lại mental model `raw text -> token ids -> embedding`.
2. Đọc bảng BPE/WordPiece/SentencePiece và tự giải thích bằng lời của mình.
3. Chạy API walkthrough trong bài với 3 tokenizer: `bert-base-multilingual-cased`, `gpt2`, `vinai/phobert-base`; dùng wrapper trong `document.md` khi cần reference hoàn chỉnh.
4. Làm bài tập token stats trong `exercise.md`.
5. Ghi lại quyết định tokenizer/preprocessing để dùng lại ở Day 16.

## Tự kiểm tra nhanh

- Vì sao tokenizer phải version cùng model weights?
- Vì sao xóa dấu tiếng Việt có thể làm model tệ hơn?
- Khi nào nên reject input quá dài thay vì truncate?
- Attention mask khác gì token type ids?
- Vì sao `return_offsets_mapping` quan trọng cho NER/citation?
- Nếu p95 input tokens vượt `max_length`, bạn sẽ sửa dữ liệu, model, chunking hay policy?

## Nguồn kỹ thuật đã đối chiếu

- Transformers docs qua Context7: `/websites/huggingface_co_transformers_main`.
- Tokenizers source/library qua Context7: `/huggingface/tokenizers`.
- [Hugging Face padding và truncation](https://huggingface.co/docs/transformers/main/en/pad_truncation).
- [Hugging Face tokenizer API](https://huggingface.co/docs/transformers/main/en/main_classes/tokenizer).
- Các behavior quan trọng đã kiểm tra: batch tokenization, padding/truncation strategies, `return_tensors`, `return_attention_mask`, `return_offsets_mapping` chỉ cho fast tokenizer và `pad_to_multiple_of`.
