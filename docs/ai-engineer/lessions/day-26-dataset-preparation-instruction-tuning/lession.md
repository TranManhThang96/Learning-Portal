# Day 26: Dataset Preparation cho Instruction Tuning

## Mục tiêu

Sau bài này, bạn cần làm được các việc sau:

- Hiểu instruction tuning dataset là gì và khác classification dataset ở đâu.
- Chọn đúng format giữa Alpaca, ShareGPT và ChatML/messages theo context.
- Thiết kế schema có metadata, source, quality score, PII status và split.
- Làm cleaning, normalization, deduplication và train/validation/test split.
- Biết dùng synthetic data có kiểm soát, không biến dataset thành dữ liệu nhiễu.
- Trả lời được: dataset này dùng được trong production không, và cần điều kiện gì.
- Chuẩn bị dataset 500 examples cho Day 27 LoRA/QLoRA.

## TL;DR

Instruction tuning dataset là tập ví dụ mô tả behavior mà bạn muốn model học. Mỗi record nói với model: khi người dùng hỏi kiểu này, assistant nên trả lời theo format, tone, policy và mức độ chi tiết như thế nào. Data không tốt sẽ tạo behavior không tốt, kể cả khi training code đúng.

Quy tắc quan trọng nhất: quality > quantity. Với fine-tuning nhỏ, 300-1.000 examples tốt, đa dạng và đúng policy thường hữu ích hơn 50.000 examples log thô chứa PII, duplicate, câu trả lời sai hoặc style lộn xộn.

## 1. Instruction Tuning là gì?

Instruction tuning dạy model ánh xạ từ instruction và context sang response mong muốn:

```text
system policy + user instruction + optional history/input -> assistant response
```

Khác với pretraining, instruction tuning không nhằm nhồi toàn bộ knowledge mới vào model. Nó phù hợp hơn để dạy model cách hành xử:

- Trả lời theo format ổn định: JSON, markdown, checklist, code review comment.
- Giữ tone/style nhất quán: ngắn gọn, lịch sự, chuyên nghiệp, không đổ lỗi.
- Tuân thủ quy trình: hỏi clarification, escalate, từ chối khi thiếu quyền.
- Học domain behavior: cách phản hồi billing ticket, cách review PR, cách viết tài liệu nội bộ.
- Giảm prompt dài nếu cùng một instruction lặp lại ở nhiều request.

Không nên dùng instruction tuning để thay thế RAG khi knowledge thay đổi thường xuyên hoặc cần trích dẫn tài liệu mới nhất. Khi cần cả behavior riêng và knowledge nội bộ, best solution thường là RAG + fine-tuning nhẹ: fine-tuning cho format/style/policy, RAG cho knowledge.

## 2. Khác gì với Classification Dataset?

| Tiêu chí | Classification | Instruction tuning |
|---|---|---|
| Input | Text hoặc feature | Instruction, context, history, system policy |
| Output | Label ngắn | Text/code/JSON dài |
| Metric | Accuracy, F1, precision, recall | Format accuracy, task success, human preference, regression eval |
| Debug | Dễ thấy label sai | Khó hơn vì nhiều câu trả lời có thể đúng |
| Risk | Label noise | Hallucination, unsafe policy, PII memorization, style drift |
| Production concern | Threshold, class imbalance | Serving format, prompt compatibility, eval leakage, rollback |

Ví dụ classification:

```json
{"text":"Tôi bị tính phí 2 lần sau khi nâng cấp.", "label":"billing_issue"}
```

Ví dụ instruction tuning:

```json
{"messages":[{"role":"user","content":"Tôi bị tính phí 2 lần sau khi nâng cấp."},{"role":"assistant","content":"Mình xin lỗi vì bất tiện này. Mình sẽ kiểm tra giao dịch nâng cấp và chuyển ticket sang billing nếu có dấu hiệu tính phí trùng. Bạn vui lòng gửi mã hóa đơn hoặc thời điểm giao dịch, không gửi số thẻ."}]}
```

Classification chỉ dạy model phân loại. Instruction tuning dạy model cách phản hồi hoàn chỉnh.

## 3. Chọn Format Dataset

Không có format tốt nhất cho mọi trường hợp. Format tốt là format gần với cách bạn sẽ train và serve model nhất.

### 3.1. Alpaca Format

Alpaca format hợp với task single-turn, đơn giản, dễ inspect bằng mắt và dễ convert.

```json
{"instruction":"Tóm tắt ticket sau thành 3 bullet.","input":"Khách báo bị tính phí 2 lần sau khi upgrade.","output":"- Khách bị tính phí 2 lần.\n- Sự cố xảy ra sau khi upgrade.\n- Cần kiểm tra billing và refund nếu đúng chính sách."}
```

Ưu điểm:

- Dễ tạo bằng spreadsheet hoặc script.
- Dễ hiểu với người mới.
- Hợp cho summarize, rewrite, classify bằng natural language, extraction.

Nhược điểm:

- Không thể hiện role rõ như system/user/assistant.
- Không tự nhiên cho multi-turn chat.
- Nếu production dùng chat API, bạn vẫn phải convert sang messages.

Nên dùng khi: task single-turn, chưa cần system prompt phức tạp, dataset nhỏ cần review nhanh.

### 3.2. ShareGPT Format

ShareGPT format thường dùng cho conversation multi-turn cũ, với role `human` và `gpt`.

```json
{"conversations":[{"from":"human","value":"Khách bị tính phí 2 lần, nên trả lời sao?"},{"from":"gpt","value":"Bạn nên xin lỗi ngắn gọn, xác nhận sẽ kiểm tra billing, hỏi thông tin cần thiết và không hứa refund khi chưa có kết quả."}]}
```

Ưu điểm:

- Phù hợp khi dữ liệu nguồn đã là hội thoại.
- Giữ được nhiều turn.
- Nhiều tool fine-tuning cũ hỗ trợ.

Nhược điểm:

- Role không chuẩn với chat API hiện đại.
- Thiếu `system` role nếu không mở rộng schema.
- Cần convert cẩn thận để không đảo role hoặc mất turn.

Nên dùng khi: bạn có conversation logs đã được redact và muốn giữ multi-turn context.

### 3.3. ChatML / Messages Format

Messages format gần với production chat API nhất. Mỗi record có list message với `role` và `content`.

```json
{"messages":[{"role":"system","content":"You are a support assistant. Answer in Vietnamese, concise, no refund promise."},{"role":"user","content":"Khách bị tính phí 2 lần sau khi upgrade."},{"role":"assistant","content":"Mình xin lỗi vì bất tiện này. Mình sẽ giúp kiểm tra giao dịch upgrade và chuyển ticket sang billing nếu có dấu hiệu tính phí trùng. Bạn vui lòng gửi mã hóa đơn hoặc thời điểm giao dịch, không gửi số thẻ."}]}
```

Ưu điểm:

- Gần production serving nhất.
- Có role rõ: `system`, `user`, `assistant`.
- Phù hợp multi-turn, policy, refusal, tool-style behavior.
- Dễ mask loss để chỉ train trên assistant response nếu trainer hỗ trợ.

Nhược điểm:

- Dài hơn Alpaca.
- Cần validate role order nghiêm túc.
- Một số trainer cần apply chat template trước khi train.

Nên dùng khi: production là chat assistant, cần system instruction, cần multi-turn, hoặc muốn giảm mismatch giữa training và inference.

### 3.4. Decision Rule

| Nhu cầu | Format nên dùng |
|---|---|
| Single-turn, task hẹp, dễ review | Alpaca |
| Có conversation history nhiều turn | ShareGPT hoặc messages |
| Production dùng chat API | ChatML/messages |
| Cần system instruction rõ | ChatML/messages |
| Cần convert qua nhiều tool | Alpaca hoặc messages |
| Cần tool calling sau này | Messages với metadata/tool fields riêng |

Best solution cho đa số production chat assistant: lưu canonical dataset ở messages format, sau đó viết converter sang Alpaca/ShareGPT nếu trainer yêu cầu.

### 3.5. Messages chưa phải token: chat template là một phần contract

`messages` là dữ liệu có cấu trúc. Trước khi model học, tokenizer còn phải render nó thành chuỗi token theo chat template của đúng model:

```text
messages JSON
  -> tokenizer.apply_chat_template(...)
  -> special tokens + role markers
  -> token ids
  -> loss mask
```

Hai model có cùng input `messages` nhưng chat template khác nhau có thể tạo token sequence khác nhau. Vì vậy:

- Không tự ghép chuỗi kiểu `"User: ... Assistant: ..."` nếu model card yêu cầu template khác.
- Pin cả tokenizer revision và chat template cùng base model.
- Inspect ít nhất 3 record sau khi render để chắc role marker, BOS/EOS và generation prompt đúng.
- Nếu chỉ muốn tính loss trên assistant/completion, phải xác minh trainer và chat template tạo loss mask đúng. Không bật một flag rồi mặc định rằng user/system token đã được mask.
- Training và inference phải dùng cùng chat template; lệch template là một dạng train-serving skew.

Day 27 sẽ dùng conversational prompt-completion để loss nằm ở phần assistant một cách rõ ràng hơn.

## 4. Schema nên dùng

Một record production-friendly nên có cả payload training và metadata audit.

```json
{"id":"support_000001","domain":"customer_support","task":"billing_reply","source":"human_seed","quality_score":5,"pii_status":"redacted","license":"internal_training_allowed","group_id":"ticket_family_2026_001","messages":[{"role":"system","content":"You are a support assistant for a SaaS product. Answer in Vietnamese, concise, and do not promise refunds without billing verification."},{"role":"user","content":"Tôi bị tính phí 2 lần sau khi upgrade, email của tôi là [EMAIL]."},{"role":"assistant","content":"Mình xin lỗi vì bất tiện này. Mình sẽ kiểm tra giao dịch upgrade và chuyển ticket sang billing nếu có dấu hiệu tính phí trùng. Bạn không cần gửi thêm thông tin thẻ qua chat."}]}
```

Field nên có:

| Field | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `id` | Có | Stable id để trace, review, rollback |
| `domain` | Có | Domain như `customer_support`, `code_review`, `technical_writing` |
| `task` | Có | Loại task cụ thể như `billing_reply`, `bug_summary` |
| `source` | Có | `human_seed`, `synthetic_reviewed`, `production_redacted` |
| `quality_score` | Có | Điểm 1-5, chỉ train record đạt ngưỡng |
| `pii_status` | Có | `clean`, `redacted`, `needs_review` |
| `license` | Có | Quyền dùng data để train |
| `group_id` | Nên có | Dùng để split không leakage theo ticket/document/customer group |
| `messages` | Có nếu dùng chat | List role/content |
| `split` | Sau khi split | `train`, `validation`, `test` |

Không nên chỉ lưu text đã render thành prompt duy nhất. Bạn sẽ mất khả năng kiểm tra role, redact từng phần, convert format và audit source.

## 5. Data Guideline trước khi tạo data

Dataset guideline giống API contract. Nếu guideline mơ hồ, reviewer và synthetic generator sẽ tạo output không nhất quán.

Ví dụ guideline cho customer support:

1. Trả lời bằng tiếng Việt có dấu, ngắn gọn, lịch sự.
2. Mở đầu bằng việc ghi nhận vấn đề, không đổ lỗi người dùng.
3. Không hứa refund, mở khóa tài khoản, xóa dữ liệu hoặc thay đổi billing nếu chưa có tool result.
4. Nếu thiếu thông tin, hỏi đúng một hoặc hai thông tin cần thiết.
5. Không yêu cầu người dùng gửi password, OTP, số thẻ, secret hoặc token.
6. Với billing/security/legal risk, escalate human hoặc team chuyên trách.
7. Không invent policy, SLA, nguyên nhân lỗi hoặc kết quả kiểm tra.
8. Nếu user đưa PII, không lặp lại PII trong response.
9. Với yêu cầu ngoài phạm vi, từ chối ngắn và đưa hướng xử lý an toàn.
10. Response nên có next step rõ ràng.

Example tốt:

```json
{"messages":[{"role":"user","content":"Tài khoản của tôi bị khóa sau khi đổi mật khẩu."},{"role":"assistant","content":"Mình sẽ giúp bạn kiểm tra. Vì đây là vấn đề bảo mật, mình không thể mở khóa trực tiếp qua chat khi chưa xác minh tài khoản. Mình sẽ tạo ticket cho nhóm support và hướng dẫn bạn các bước xác minh tiếp theo."}]}
```

Example xấu:

```json
{"messages":[{"role":"user","content":"Tài khoản của tôi bị khóa sau khi đổi mật khẩu."},{"role":"assistant","content":"Chắc hệ thống lỗi, mình sẽ mở khóa ngay cho bạn."}]}
```

Lý do xấu: invent nguyên nhân, hứa action không có permission, bỏ qua xác minh bảo mật.

## 6. Cleaning và Normalization

Cleaning tối thiểu:

- Parse được từng dòng JSONL.
- Không có instruction, user message hoặc assistant response rỗng.
- Normalize whitespace, line ending và ký tự control.
- Loại HTML/script/boilerplate nếu không phải signal cần học.
- Loại hoặc sửa record sai role order.
- Loại record quá dài vượt context budget.
- Check language mismatch nếu dataset yêu cầu tiếng Việt.
- Redact PII: email, phone, API key, token, số thẻ, access token, customer id nhạy cảm.
- Gắn `pii_status` sau redaction: `clean`, `redacted`, hoặc `needs_review`.
- Loại response chứa policy sai hoặc hallucination nghiêm trọng.

Không nên clean quá tay. Nếu production user thường viết tắt, sai chính tả hoặc trộn tiếng Anh, bạn có thể giữ một phần để model học robust. Nhưng response của assistant nên sạch, đúng chính sách và có dấu.

## 7. Deduplication

Duplicate làm model overfit và làm eval đẹp giả. Dedup nên chạy trước split.

Các mức dedup:

- Exact duplicate: hash normalized text.
- Near duplicate: similarity theo n-gram, MinHash hoặc embedding khi dataset lớn.
- Group duplicate: cùng `group_id`, cùng ticket family, cùng document version.
- Template duplicate: synthetic data chỉ thay vài từ nhưng response gần như giống nhau.

Với dataset 500 examples, exact dedup + manual review near-duplicate thường đủ. Với dataset lớn hơn, nên thêm MinHash hoặc embedding clustering.

Trade-off: dedup mạnh quá có thể xóa những biến thể hữu ích; dedup yếu quá làm model học lặp pattern và làm validation/test bị leakage.

## 8. Train/Validation/Test Split

Split gợi ý:

| Split | Tỷ lệ | Mục đích |
|---|---:|---|
| Train | 80-90% | Train adapter/model |
| Validation | 5-10% | Chọn checkpoint, hyperparameter, early stopping |
| Test/Golden | 5-10% | Báo cáo before/after, không tune vào đây |

Quy tắc production: split theo group/source nếu có. Không để cùng một ticket, cùng customer thread, cùng document paragraph hoặc cùng synthetic template xuất hiện ở cả train và test.

Ví dụ xấu:

```text
train: ticket_123 turn 1
test:  ticket_123 turn 2
```

Metric sẽ cao giả vì model đã thấy cùng context.

Ví dụ tốt:

```text
train: ticket_family_001..400
validation: ticket_family_401..450
test: ticket_family_451..500
```

## 9. Quality > Quantity

Dataset tốt có các đặc điểm sau:

- Mỗi example đúng policy.
- Task đa dạng nhưng vẫn cùng behavior mục tiêu.
- Response có format ổn định.
- Có edge cases: thiếu thông tin, user tức giận, request không an toàn, PII, escalation.
- Có negative/refusal examples vừa đủ.
- Có metadata rõ để audit.
- Có test set không bị dùng để tune.

Dataset kém thường có:

- Nhiều duplicate.
- Response dài lan man.
- Synthetic pattern lặp.
- Log thô chứa PII.
- Mixing style: lúc thân mật, lúc quá formal, lúc tiếng Anh, lúc tiếng Việt không dấu.
- Output sai quyền hạn: hứa refund, hứa xóa dữ liệu, tự tạo kết quả kiểm tra.

## 10. Synthetic Data

Synthetic data hữu ích khi bạn chưa có đủ examples, nhưng phải có guardrails.

Workflow nên dùng:

```text
Guideline rõ ràng
  -> 30-50 human seed examples chất lượng cao
  -> generate variants theo task/domain/edge case
  -> validate schema
  -> redact PII giả hoặc thật
  -> dedup
  -> human review sample
  -> tag source = synthetic_reviewed
  -> split theo group/template
```

Nên dùng synthetic cho:

- Format variants.
- Edge cases hiếm.
- Tone/style examples.
- Refusal behavior.
- Domain template có source rõ.

Không nên dùng synthetic khi:

- Không có human seed examples.
- Generator invent facts, policy hoặc product behavior.
- Không có human review.
- Synthetic output đến từ chính model sẽ được dùng để eval.
- Dataset bị thống trị bởi một template.

Best practice: với 500 examples đầu tiên, dùng 30-50 human seed, sinh thêm 450-470 synthetic candidates, sau validation/dedup/review chỉ giữ 500 record tốt nhất. Nếu có nguồn production đã redact và được phép train, trộn thêm để tăng tính thực tế.

## 11. Privacy, License và Data Ownership

Fine-tuning có risk memorization. Nếu một chuỗi không được phép xuất hiện trong output, đừng đưa vào train set.

Privacy checklist:

- Data có consent hoặc quyền hợp pháp để train không?
- Có PII nào cần redact không: email, phone, address, full name, IP, account id?
- Có secret/token/API key/log nội bộ không?
- Có customer confidential data không?
- Có chính sách retention/deletion cho dataset và model artifact không?
- Adapter/model có được share public không?
- License của public dataset có cho commercial training không?
- Có thể trace từ model version về dataset version không?

Production rule: `pii_status = needs_review` không được vào train. Public data không mặc định được phép dùng cho commercial fine-tuning.

## 12. Performance và Cost Concern

Dataset preparation ảnh hưởng trực tiếp đến training cost:

- Sequence length dài làm VRAM và thời gian train tăng mạnh. Theo dõi p50/p95 token length.
- Response ngắn, đúng trọng tâm thường tốt hơn response dài nhưng lan man.
- Duplicate làm tốn compute và tăng overfit.
- Packing nhiều short examples vào một sequence có thể tăng throughput nếu trainer hỗ trợ.
- Dataset 500 examples phù hợp để học format/style nhỏ, không đủ để học knowledge rộng.
- Với QLoRA Day 27, nên giữ max length thực tế trong khoảng 512-2.048 tokens tùy GPU và model.
- Chọn messages format có thể cần apply chat template, làm token length tăng so với Alpaca.

Trade-off: cắt ngắn dữ liệu giúp giảm cost nhưng có thể mất context quan trọng; giữ context dài giúp học multi-turn tốt hơn nhưng tốn VRAM và dễ học noise.

## 13. Dùng được trong production không?

Có, dataset từ bài này dùng được làm đầu vào production fine-tuning nếu thỏa các điều kiện sau:

- Có quyền dùng data để train và deploy model/adapters.
- Không có PII/secret hoặc đã redact và review.
- Schema validate tự động, không có record sai role/order/field.
- Dedup trước split và split theo group để giảm leakage.
- Có dataset card, metadata, version, changelog và mapping tới model artifact.
- Có golden test set riêng không dùng để tune.
- Có human review cho sample đại diện, đặc biệt synthetic data và edge cases.
- Có eval trước/sau fine-tune ở Day 28: format accuracy, task success, safety regression, latency/cost.
- Có rollback plan nếu adapter tạo behavior xấu.

Nếu thiếu các điều kiện này, dataset vẫn có thể dùng cho lab hoặc prototype, nhưng chưa nên dùng để train model đi production.

## 14. Checklist nhanh

- [ ] Chọn domain và behavior cần học.
- [ ] Viết data guideline trước khi tạo data.
- [ ] Chọn canonical format: Alpaca, ShareGPT hoặc messages.
- [ ] Có ít nhất 30 human seed examples.
- [ ] Có schema với `id`, `domain`, `task`, `source`, `quality_score`, `pii_status`, `license`, `group_id`.
- [ ] Validate JSONL tự động.
- [ ] Redact PII/secret.
- [ ] Dedup trước split.
- [ ] Split train/validation/test không leakage rõ ràng.
- [ ] Có dataset card và metadata.
- [ ] Pin tokenizer/chat template và inspect dữ liệu sau render.
- [ ] Có 20-50 golden examples cho Day 28.
- [ ] Có câu trả lời production readiness rõ ràng.

## 15. Quiz tự kiểm tra

1. Instruction tuning dataset khác classification dataset ở điểm nào?
2. Khi nào nên chọn Alpaca thay vì messages format?
3. Vì sao canonical dataset cho chat assistant nên giữ role `system`, `user`, `assistant`?
4. Vì sao dedup phải chạy trước split?
5. Near-duplicate trong synthetic data gây hại như thế nào?
6. Tại sao không nên train trên raw customer logs chưa redact?
7. `quality_score` nên dùng để làm gì?
8. Khi nào grouped split tốt hơn random split?
9. Fine-tuning có nên dùng để nhồi tài liệu nội bộ không? Vì sao?
10. Dataset 500 examples có thể production được trong trường hợp nào?
