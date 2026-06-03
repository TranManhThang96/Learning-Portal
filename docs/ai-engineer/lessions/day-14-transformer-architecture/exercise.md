# Day 14 Exercise: Transformer Architecture

## Cách làm

Làm theo thứ tự. Mục tiêu không phải nhớ tên architecture, mà là ra quyết định kỹ thuật hợp lý cho production.

## Phần 1: Quiz nhanh

Trả lời ngắn, mỗi câu 2-4 dòng.

1. Vì sao Transformer cần positional encoding hoặc positional strategy?
2. Encoder-only khác decoder-only ở attention mask như thế nào?
3. Vì sao decoder-only model sinh text chậm hơn khi output dài?
4. KV cache lưu gì? Nó giảm compute nào và tăng chi phí nào?
5. FFN trong Transformer làm gì nếu attention mới là nơi mix token?
6. Residual connection giúp gì cho gradient flow?
7. Khi nào BERT/PhoBERT hợp lý hơn GPT/LLaMA/Qwen?
8. Khi nào T5 hoặc encoder-decoder hợp lý hơn decoder-only?
9. Vì sao context dài không tự động làm RAG tốt hơn?
10. Trước khi dùng model open-weight trong công ty, cần check license và data privacy như thế nào?

## Phần 2: Vẽ lại Transformer block

Vẽ lại bằng ASCII diagram một block Pre-LN gồm:

- Input `x`.
- LayerNorm.
- Multi-head self-attention.
- Residual connection.
- LayerNorm.
- FFN.
- Residual connection.
- Output.

Mẫu khởi đầu:

```text
x
|\
| LayerNorm -> Attention -> ...
|___________________________+
```

Sau khi vẽ, giải thích từng mũi tên bằng 1 câu.

## Phần 3: Điền bảng architecture

Điền bảng sau cho 6 bài toán:

| Bài toán | Architecture chọn | Lý do | Không chọn gì | Rủi ro production |
|---|---|---|---|---|
| Sentiment classification tiếng Việt |  |  |  |  |
| Semantic search tài liệu nội bộ |  |  |  |  |
| Rerank top 50 documents trong RAG |  |  |  |  |
| Chatbot CSKH có tool tra cứu đơn hàng |  |  |  |  |
| Summarize hợp đồng dài 80 trang |  |  |  |  |
| Extract NER từ ticket support |  |  |  |  |

Gợi ý:

- Output label/vector/score thường nghiêng về encoder.
- Output text tự do thường nghiêng về decoder-only hoặc encoder-decoder.
- Seq2seq input-output rõ ràng có thể nghiêng về encoder-decoder.

## Phần 4: Case study production decision

Bạn là AI Engineer cho một công ty thương mại điện tử. Team cần 4 tính năng:

1. Classify ticket thành `refund`, `shipping`, `payment`, `account`.
2. Semantic search trong policy nội bộ.
3. Chatbot trả lời khách hàng dựa trên policy và trạng thái đơn hàng.
4. Summarize cuộc hội thoại dài thành ghi chú cho nhân viên CSKH.

Ràng buộc:

- 1 triệu ticket/tháng.
- p95 latency cho classification dưới 150 ms.
- Chatbot được phép p95 first token dưới 2 giây và stream sau đó.
- Dữ liệu đơn hàng có PII, không được gửi sang provider nếu chưa có DPA.
- Budget GPU hạn chế.
- Cần audit được model version và prompt version.

Hãy viết một Architecture Decision Record ngắn theo mẫu:

```text
# ADR: Chọn Transformer architecture cho hệ thống CSKH

## Context
...

## Decision
- Classification:
- Semantic search:
- Chatbot:
- Summarization:

## Trade-offs
- Latency:
- Cost:
- Data privacy:
- License:
- Quality:

## Production conditions
- Eval:
- Serving:
- Monitoring:
- Rollback:
- Security:
```

Điểm cần có trong câu trả lời:

- Classification không nên mặc định dùng decoder-only nếu encoder đáp ứng tốt hơn về latency/cost.
- Semantic search nên tách embedding retrieval và optional reranker.
- Chatbot nên dùng decoder-only nhưng phải có RAG, tool allowlist, output policy và streaming.
- Summarization có thể dùng decoder-only hoặc encoder-decoder tùy format ổn định và hạ tầng.
- Phải nêu điều kiện production rõ ràng.

## Phần 5: Token budget và serving constraints

Tính nhẩm và ghi nhận xét.

Giả sử chatbot dùng decoder-only model:

```text
system prompt: 500 tokens
conversation history: 1,500 tokens
retrieved context: 3 chunks x 700 tokens = 2,100 tokens
tool result: 400 tokens
expected answer: 500 tokens
```

1. Tổng input tokens trước khi sinh output là bao nhiêu?
2. Tổng tokens gồm cả output dự kiến là bao nhiêu?
3. Nếu p95 latency vượt SLA, bạn sẽ giảm phần nào trước?
4. Nếu answer hay thiếu citation, bạn sẽ tăng context hay cải thiện retrieval/reranking trước? Vì sao?
5. Nếu VRAM OOM khi concurrency tăng, KV cache liên quan thế nào?

Gợi ý trả lời:

- Đừng chỉ tăng context length.
- Kiểm tra token distribution và truncation rate.
- Ưu tiên chunk quality, reranking, dedup và prompt ngắn gọn.
- Limit conversation history bằng summary hoặc memory policy.

## Phần 6: Checklist đọc paper/model card

Chọn một model bất kỳ trong 3 nhóm:

- Encoder-only: BERT, RoBERTa, PhoBERT hoặc embedding model.
- Decoder-only: GPT-style, LLaMA, Qwen hoặc Mistral-style model.
- Encoder-decoder: T5 hoặc BART-style model.

Điền checklist:

```text
Model name:
Architecture group:
Training objective:
Supported language/domain:
Context length:
Positional strategy:
License:
Intended use:
Limitations:
Hardware/serving notes:
Production fit for my use case:
Risks:
Decision: use / evaluate further / reject
```

## Phần 7: Đáp án tham khảo ngắn

Không đọc phần này trước khi tự làm.

1. Transformer cần positional information vì self-attention không tự biết thứ tự token; cùng tập token nhưng thứ tự khác có thể đổi nghĩa.
2. Encoder-only dùng bidirectional attention; decoder-only dùng causal mask để không nhìn future tokens.
3. Decoder-only sinh từng token tuần tự; output càng dài thì decode loop càng dài.
4. KV cache lưu Key/Value của token trước trong các layer; giảm việc tính lại K/V nhưng tốn VRAM.
5. FFN biến đổi representation từng token sau khi attention đã đưa context vào.
6. Residual connection giúp signal và gradient đi qua nhiều layer dễ hơn, layer học delta thay vì học lại toàn bộ.
7. BERT/PhoBERT hợp lý hơn cho classification, embedding, NER, reranking khi cần latency/cost tốt và output ổn định.
8. T5/encoder-decoder hợp lý cho translation/summarization/text normalization khi input-output rõ ràng và format ổn định.
9. Context dài tăng cost/latency và có thể lost-in-the-middle; retrieval/reranking tốt thường hiệu quả hơn.
10. Cần kiểm tra license commercial/internal use, data policy, PII, retention, provider DPA, model version và audit trail.

## Phần 8: Tiêu chí hoàn thành

Bạn hoàn thành Day 14 khi:

- Vẽ được Transformer block không cần nhìn tài liệu.
- Phân biệt được encoder-only, decoder-only và encoder-decoder theo mask/objective/output.
- Giải thích được positional encoding, RoPE, LayerNorm, FFN và residual connection.
- Viết được ADR chọn architecture cho ít nhất 2 use cases.
- Trả lời rõ "Dùng được trong production không? Nếu có thì cần điều kiện gì?".
- Chuẩn bị được quyết định cho Day 16: classification tiếng Việt nên bắt đầu bằng baseline đơn giản rồi encoder-only BERT/PhoBERT-style model.
