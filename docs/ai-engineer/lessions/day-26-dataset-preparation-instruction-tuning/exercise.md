# Exercise: Tạo Dataset 500 Examples cho Instruction Tuning

## Mục tiêu

Tạo một dataset 500 examples cho một domain, sẵn sàng dùng ở Day 27 LoRA/QLoRA và Day 28 evaluation.

Bạn chọn một trong bốn domain:

- Customer support.
- Code review.
- Technical writing.
- Internal policy Q&A.

Output cuối cùng:

```text
instruction_dataset/
  raw/input.jsonl
  processed/dataset_split.jsonl
  processed/dataset_card.md
  processed/metadata.json
  processed/validation_report.md
```

## Phần 1: Viết behavior guideline

Viết 10 dòng guideline cho assistant. Template:

```markdown
# Behavior Guideline

Domain: customer_support
Language: Vietnamese with English technical terms when needed

1. ...
2. ...
10. ...
```

Checklist:

- [ ] Có tone/style.
- [ ] Có format response.
- [ ] Có điều kiện hỏi clarification.
- [ ] Có điều kiện escalate.
- [ ] Có điều cấm: không invent facts, không yêu cầu password/OTP/secret.
- [ ] Có privacy rule.

## Phần 2: Tạo 30-50 human seed examples

Mỗi example dùng messages format:

```json
{"id":"support_seed_0001","domain":"customer_support","task":"billing_reply","source":"human_seed","quality_score":5,"pii_status":"clean","license":"internal_training_allowed","group_id":"support_seed_0001","messages":[{"role":"system","content":"You are a support assistant for a SaaS product. Answer in Vietnamese, concise, and do not promise refunds without billing verification."},{"role":"user","content":"Tôi bị tính phí 2 lần sau khi upgrade."},{"role":"assistant","content":"Mình xin lỗi vì bất tiện này. Mình sẽ kiểm tra giao dịch upgrade và chuyển ticket sang billing nếu có dấu hiệu tính phí trùng. Bạn vui lòng gửi mã hóa đơn hoặc thời điểm giao dịch, không gửi số thẻ."}]}
```

Phân bổ gợi ý cho customer support:

| Task | Số examples |
|---|---:|
| billing_reply | 10 |
| account_access | 8 |
| how_to | 8 |
| bug_report | 6 |
| cancellation | 5 |
| security_escalation | 5 |
| refusal_or_out_of_scope | 3 |

## Phần 3: Sinh synthetic candidates

Dùng guideline và seed examples để sinh thêm candidates. Không giữ tất cả ngay. Mỗi candidate cần có:

- `source = synthetic_reviewed` chỉ sau khi đã review.
- `quality_score >= 4`.
- `group_id` theo template hoặc scenario family.
- Không có PII thật.
- Không invent product policy.

Prompt gợi ý để sinh synthetic data:

```text
You are creating instruction tuning data for a Vietnamese SaaS support assistant.

Use this behavior guideline:
<paste guideline>

Generate 20 JSONL records in messages format.
Requirements:
- Vietnamese with proper diacritics.
- Include metadata fields: id, domain, task, source, quality_score, pii_status, license, group_id, messages.
- source must be synthetic_reviewed.
- pii_status must be clean.
- license must be internal_training_allowed.
- Vary user wording, emotion, missing information, and escalation cases.
- Assistant must not promise refund, account unlock, data deletion, or billing changes without verification.
- Output valid JSONL only, one object per line.
```

Review sau khi sinh:

- [ ] Loại record lặp template quá rõ.
- [ ] Loại response dài lan man.
- [ ] Loại response invent policy, SLA, nguyên nhân lỗi.
- [ ] Loại record thiếu escalation khi có security/billing/legal risk.
- [ ] Loại record có PII thật.

## Phần 4: Validate, redact, dedup và split

1. Tạo thư mục:

```bash
mkdir -p instruction_dataset/raw instruction_dataset/processed
```

2. Lưu toàn bộ JSONL vào:

```text
instruction_dataset/raw/input.jsonl
```

3. Dùng script trong `document.md` và chạy:

```bash
cd instruction_dataset
python3 prepare_dataset.py --input raw/input.jsonl --out-dir processed --dataset-name support_instruction_v1
```

4. Kiểm tra output:

```bash
wc -l processed/dataset_split.jsonl
sed -n '1,120p' processed/validation_report.md
sed -n '1,120p' processed/dataset_card.md
```

Dataset chỉ đạt khi:

- [ ] Có khoảng 500 rows sau dedup/filter.
- [ ] `errors: 0`.
- [ ] Không có record `needs_review`.
- [ ] Có đủ train/validation/test.
- [ ] Split không trộn cùng `group_id`.
- [ ] Dataset card không còn placeholder quan trọng.

## Phần 5: Tạo golden set cho Day 28

Chọn 20-50 examples từ test split làm golden set. Không dùng golden set để sửa prompt hoặc tune hyperparameter lặp lại.

Golden set nên có:

- [ ] Case bình thường.
- [ ] Case thiếu thông tin.
- [ ] Case user tức giận.
- [ ] Case billing/security/legal cần escalate.
- [ ] Case có PII đã redact.
- [ ] Case assistant phải từ chối an toàn.
- [ ] Case cần output format cố định.

## Phần 6: Câu hỏi bắt buộc

Trả lời trong `validation_report.md` hoặc file riêng:

1. Dataset này dùng để dạy behavior gì, không dạy knowledge gì?
2. Vì sao bạn chọn Alpaca, ShareGPT hoặc messages format?
3. Có bao nhiêu rows từ human seed, synthetic reviewed, production redacted?
4. Bạn đã làm gì để tránh PII/secret?
5. Bạn dedup trước hay sau split? Vì sao?
6. Split có theo `group_id` không?
7. Dataset này dùng được trong production không? Nếu có thì cần điều kiện gì?
8. Rủi ro còn lại lớn nhất là gì?

## Rubric tự chấm

| Hạng mục | Điểm |
|---|---:|
| Guideline rõ, đúng domain, có policy an toàn | 15 |
| Schema đầy đủ metadata | 15 |
| 500 examples đa dạng, quality_score hợp lý | 20 |
| Cleaning/redaction/dedup/split chạy được | 20 |
| Dataset card và metadata đầy đủ | 10 |
| Golden set chuẩn bị tốt cho Day 28 | 10 |
| Trả lời production readiness và trade-off rõ | 10 |

Tổng: 100 điểm.

## Đáp án mẫu ngắn cho production readiness

Dùng được trong production nếu dataset có quyền train/deploy, không còn PII/secret, đã validate schema, dedup trước split, split theo group, synthetic data đã review, có dataset card/metadata và pass evaluation trước/sau fine-tune. Nếu chỉ là synthetic data sinh nhanh chưa review hoặc còn `needs_review`, chỉ dùng cho lab.
