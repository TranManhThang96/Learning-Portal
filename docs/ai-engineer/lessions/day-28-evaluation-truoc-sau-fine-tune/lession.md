# Day 28: Evaluation trước/sau Fine-tune

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Thiết kế golden dataset để so sánh base model và fine-tuned model một cách công bằng.
- Đo được `exact match`, `format accuracy`, `human evaluation`, `LLM-as-a-judge`, regression và latency/cost.
- Phát hiện overfitting, test leakage, format improvement giả và safety regression.
- Viết được evaluation report trước/sau fine-tune theo tag, không chỉ nhìn aggregate score.
- Tạo release gate để quyết định deploy adapter, canary hoặc rollback.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

Fine-tune không có ý nghĩa nếu không chứng minh được chất lượng tăng trên dữ liệu chưa thấy. Train loss giảm không đồng nghĩa production quality tăng. Cách làm đúng là đóng băng một golden dataset, chạy cùng prompt template, cùng decoding config, cùng parser/scorer cho base model và fine-tuned model, sau đó so sánh metric theo từng tag.

Release chỉ nên qua nếu metric chính tăng đủ lớn mà không làm xấu format, regression, safety, latency và cost. Nếu có safety regression nghiêm trọng, fail release dù score tổng cao.

## 1. Bài Này Nằm Ở Đâu Trong Phase 4

```text
Day 25: quyết định khi nào fine-tune, khi nào dùng RAG/tool/prompt
Day 26: chuẩn bị dataset instruction tuning
Day 27: chạy LoRA/QLoRA hands-on
Day 28: evaluate trước/sau fine-tune
Day 29-30: serve local model và deploy API
```

Day 28 là bước chặn trước khi đưa adapter hoặc merged model vào serving path. Với mindset của Senior SE, evaluation giống test suite cho backend, nhưng output của LLM có tính xác suất nên cần thêm sampling, rubric, tag analysis và human review.

## 2. Evaluation Mindset

Evaluation cho fine-tune nên tách thành 4 lớp:

| Lớp | Mục tiêu | Ví dụ check | Tự động được không |
|---|---|---|---|
| Contract check | Output có dùng được bởi downstream không | JSON parse được, đủ key, enum hợp lệ | Có |
| Task metric | Model làm đúng task hẹp không | `category` exact match, extracted field đúng | Có nếu có expected |
| Quality review | Câu trả lời có hữu ích, đúng tone, đủ action không | Human score, LLM judge score | Bán tự động |
| Release risk | Có phá case cũ, safety, latency, cost không | Regression gate, safety gate, p95 latency | Có, nhưng cần review |

Sai lầm phổ biến:

- Evaluate trên train set rồi tưởng model generalize tốt.
- Chỉ nhìn train/validation loss mà không xem output thật.
- So fine-tuned model với prompt khác, temperature khác hoặc parser khác.
- Chỉ xem average score, bỏ qua tag safety hoặc edge case bị giảm mạnh.
- Dùng LLM-as-a-judge như ground truth duy nhất cho decision có rủi ro cao.

## 3. Golden Dataset Step by Step

Golden dataset là test fixture cho model behavior. Nó phải nhỏ đủ để chạy thường xuyên, nhưng đủ đa dạng để đại diện cho production traffic.

### Bước 1: Chốt task và contract

Ví dụ task customer support triage:

- Input: nội dung ticket tiếng Việt.
- Output: JSON gồm `category`, `priority`, `answer`.
- Downstream: hệ thống ticketing parse JSON để route team.
- Failure không chấp nhận: JSON sai, route nhầm ticket billing nghiêm trọng, trả lời lộ PII, hướng dẫn hành động nguy hiểm.

### Bước 2: Định nghĩa schema case

Mỗi case nên có `id`, `input`, `expected`, `checks`, `tags` và `split`.

```json
{
  "id": "billing_001",
  "input": {
    "ticket": "Khách báo bị tính phí 2 lần cho cùng một đơn."
  },
  "expected": {
    "category": "billing",
    "priority": "high"
  },
  "checks": {
    "must_be_json": true,
    "required_keys": ["category", "priority", "answer"],
    "allowed_categories": ["billing", "shipping", "technical", "safety", "other"],
    "allowed_priorities": ["low", "medium", "high"],
    "contains_any": ["mã giao dịch", "kiểm tra lịch sử thanh toán"],
    "forbidden": ["chắc chắn hoàn tiền", "bỏ qua xác minh"]
  },
  "tags": ["billing", "json", "high_priority", "regression"],
  "split": "golden"
}
```

### Bước 3: Phủ đủ nhóm case

| Nhóm | Tỷ lệ gợi ý | Mục đích |
|---|---:|---|
| Normal | 40-50% | Đại diện traffic phổ biến |
| Edge | 15-20% | Input ngắn, mơ hồ, sai chính tả, teencode |
| Format | 10-15% | Ép JSON/schema, enum, required keys |
| Regression | 10-20% | Case model/prompt cũ đã làm đúng, không được phá |
| Safety/PII | 5-10% | Prompt injection, PII, policy bypass |
| Out-of-domain | 5-10% | Model nên hỏi lại hoặc từ chối nhẹ |

Với hands-on, 50-100 cases là đủ học. Với production release, nên có ít nhất vài trăm cases, cộng thêm regression set tăng dần từ lỗi thật.

### Bước 4: Chống leakage

Golden dataset không được đưa vào train set. Nếu team đã dùng case đó để tune prompt hoặc tune data nhiều lần, case đó bắt đầu giống validation hơn là test. Cách làm thực tế:

- `train`: dùng để fine-tune.
- `validation`: dùng để chọn checkpoint, prompt nhỏ, hyperparameter.
- `golden_test`: đóng băng cho release decision.
- `regression`: bổ sung từ lỗi production, chạy ở mọi release.

## 4. Deterministic Before/After Comparison

Muốn biết improvement đến từ fine-tune, cần cố định các biến còn lại:

- Cùng prompt template.
- Cùng system instruction.
- Cùng decoding config: ưu tiên greedy hoặc `temperature=0`.
- Cùng `max_tokens` hoặc `max_new_tokens`.
- Cùng parser, scorer và judge rubric.
- Cùng base model version và adapter version được ghi rõ.
- Cùng test set, không lọc bỏ failures sau khi chạy.

Flow chuẩn:

```text
golden_eval.jsonl
  -> render prompt deterministically
  -> run base model
  -> run fine-tuned model hoặc adapter
  -> parse output
  -> compute metrics
  -> compare aggregate + per-tag
  -> inspect regressions
  -> release decision
```

Nếu thay prompt và fine-tune cùng lúc, bạn không biết model tốt hơn vì adapter hay vì prompt. Trong production, hãy chạy ít nhất 3 baseline:

| Baseline | Trả lời câu hỏi |
|---|---|
| Base + current prompt | Hệ thống hiện tại tốt đến đâu |
| Base + improved prompt | Prompt engineering đã đủ chưa |
| Fine-tuned + same prompt | Fine-tune có thêm giá trị thật không |

## 5. Metric Chính

| Metric | Đo cái gì | Nên dùng khi | Caveat |
|---|---|---|---|
| JSON valid rate | Output parse được JSON | Structured output, tool args | JSON đúng chưa chắc nội dung đúng |
| Format accuracy | Đủ required keys, enum hợp lệ | Downstream parse nghiêm ngặt | Có thể format tốt nhưng answer kém |
| Exact match | Field bằng expected | Classification, extraction | Không phù hợp text tự nhiên nhiều cách đúng |
| Contains score | Có facts/action bắt buộc | Support answer, policy answer | Dễ bị wording bias |
| Forbidden rate | Có phrase/hành vi cấm không | Safety, compliance, workflow | Regex không bắt hết semantic risk |
| Human score | Correctness, helpfulness, tone | User-facing generation | Đắt, chậm, cần guideline |
| LLM judge score | Scale review free-form | Eval nhiều text nhanh | Có bias, cần calibration |
| Regression pass rate | Không phá case cũ | Release gate | Cần duy trì set tốt |
| p50/p95 latency | SLA inference | Production serving | Phụ thuộc serving stack |
| Token/cost per case | Chi phí request | Scale lớn | Judge call làm cost tăng |

Một release score đơn giản:

```text
release_score = 0.35 * format_accuracy
              + 0.35 * task_accuracy
              + 0.20 * judge_score_normalized
              + 0.10 * regression_pass_rate
```

Nhưng gate cứng nên đứng trước score tổng:

```text
Fail nếu:
- JSON valid < 98% cho structured output
- regression pass < 95%
- safety critical failure > 0
- p95 latency tăng quá 20% so với baseline
- cost/request vượt budget đã chốt
```

## 6. Exact Match Và Format Accuracy

`exact match` phù hợp khi expected output rõ ràng:

- Classification: `category == "billing"`.
- Extraction: `invoice_id == "INV-123"`.
- Routing: `priority == "high"`.
- Enum decision: `action == "refund_review"`.

`format accuracy` cần tách khỏi correctness. Một output có thể parse được JSON nhưng route sai:

```json
{
  "category": "shipping",
  "priority": "high",
  "answer": "Tôi sẽ kiểm tra trạng thái giao hàng."
}
```

Với ticket billing, format đúng nhưng task sai. Vì vậy report phải có cả `json_valid`, `required_keys_ok`, `enum_ok`, `exact_score` và `contains_score`.

Cũng cần tách hai khái niệm:

- `strict_json_valid`: toàn bộ output là đúng một JSON object, không có Markdown hay lời dẫn.
- `recoverable_json`: parser có thể moi một JSON object ra khỏi output lỗi contract.

Production gate cho structured output nên dùng `strict_json_valid`. `recoverable_json` chỉ hữu ích cho error analysis hoặc migration; nếu downstream phải tự cắt chuỗi để cứu output thì contract vẫn đã fail.

## 7. Human Evaluation

Human evaluation vẫn cần cho các output có nhiều cách đúng:

- Chat support answer.
- Technical writing.
- Code review suggestion.
- Safety-sensitive refusal.
- Tone/style theo brand.

Rubric nên rõ, ít thang điểm và có ví dụ. Ví dụ:

| Điểm | Ý nghĩa |
|---:|---|
| 1 | Sai task, gây hại, hoặc không trả lời được |
| 2 | Có ý đúng nhưng thiếu phần quan trọng, format/tone kém |
| 3 | Chấp nhận được, còn thiếu chi tiết hoặc next action |
| 4 | Đúng, hữu ích, tone tốt, ít lỗi nhỏ |
| 5 | Đúng đầy đủ, actionable, không bịa, đúng policy |

Best practice:

- Review blind A/B nếu so base và fine-tuned.
- Randomize thứ tự output để giảm bias.
- Mỗi case quan trọng có ít nhất 2 reviewer nếu dùng cho release lớn.
- Tính inter-rater agreement ở mức đơn giản: reviewer có lệch quá 1 điểm không.
- Log lý do điểm thấp để đưa vào regression set.

## 8. LLM-as-a-Judge

LLM-as-a-judge hữu ích để scale eval free-form, nhưng phải được kiểm soát như một evaluator có bias.

Nên dùng khi:

- Cần review hàng trăm hoặc hàng nghìn answer.
- Có rubric rõ và expected facts.
- Decision không hoàn toàn security-critical.
- Có human calibration định kỳ.

Không nên dùng làm nguồn quyết định duy nhất khi:

- Compliance, legal, medical, financial advice có rủi ro cao.
- Safety failure nghiêm trọng.
- Judge model có thể bị prompt injection từ chính output được chấm.

Judge prompt nên deterministic và yêu cầu JSON:

```text
Bạn là evaluator. Chấm output theo rubric, không ưu tiên câu trả lời dài hơn.
Chỉ dựa vào expected và policy bên dưới.
Trả về JSON hợp lệ: {"score": 1-5, "reason": "...", "critical_failure": true|false}
```

Với A/B comparison, không nói đâu là base, đâu là fine-tuned. Hãy randomize nhãn `A` và `B`.

Safety checklist cho LLM judge:

- Không gửi raw prompt chứa PII, secret hoặc dữ liệu khách hàng nhạy cảm sang judge bên ngoài nếu chưa có phê duyệt.
- Redact dữ liệu trước khi judge, nhưng giữ đủ expected facts để judge chấm đúng.
- Nhắc judge bỏ qua instruction nằm trong candidate output. Candidate output là vật bị chấm, không phải system prompt.
- Log `judge_model`, version, prompt rubric và sampling config để lần sau reproduce được.
- Nếu judge chấm case critical thấp/rủi ro cao, đưa vào human review thay vì auto-pass.

## 9. Regression Set

Regression set là danh sách case model đã từng làm đúng hoặc lỗi production đã từng xảy ra. Nó giúp tránh tình trạng fine-tune cải thiện trung bình nhưng phá workflow quan trọng.

Nguồn tạo regression:

- Incident production.
- Ticket user complaint.
- Case support agent phải sửa nhiều.
- Prompt injection attempt.
- Output sai JSON làm downstream lỗi.
- Case high-value tenant.

Quy tắc quản lý:

- Mỗi bug production nghiêm trọng thêm ít nhất 1 regression case.
- Regression case có owner và reason.
- Không xóa case chỉ vì model mới fail, trừ khi business requirement đổi.
- Chạy regression trong CI hoặc pre-release.

## 10. Overfitting Detection

Fine-tuned model có thể trông tốt vì học thuộc training examples. Dấu hiệu overfitting:

- Train loss giảm, validation/golden metric không tăng hoặc giảm.
- Output lặp wording từ train data dù input khác.
- Golden score tăng ở normal cases nhưng giảm mạnh ở edge/OOD.
- Model quá tự tin, ít hỏi lại khi input thiếu thông tin.
- Format accuracy tăng nhưng semantic correctness giảm.
- Judge/human thấy answer dài hơn nhưng chứa giả định không có trong input.

Cách phát hiện:

1. So sánh train-like cases với truly held-out cases.
2. Report per-tag, đặc biệt `edge`, `ood`, `safety`, `regression`.
3. Dùng near-duplicate check giữa train và golden set.
4. Kiểm tra output entropy/variation nếu model lặp template quá mức.
5. Review manual top failures và top deltas.

## 11. Performance Và Cost Concern

Evaluation cũng là workload tốn tiền:

- Chạy base + fine-tuned nhân đôi inference cost.
- LLM judge thêm một model call, thường làm cost tăng 2-3 lần.
- Golden set lớn làm pre-release chậm nếu không batch/cache.
- Local model evaluation có thể bị bottleneck bởi VRAM, batch size, context length.
- Adapter serving có thể tăng latency nhẹ nếu runtime không merge adapter.

Cách tối ưu:

- Cache raw output theo `case_id`, `model_version`, `prompt_version`, `decoding_config_hash`.
- Chạy smoke eval 20-50 cases trong CI, full eval trước release hoặc nightly.
- Batch inference nếu runtime hỗ trợ.
- Giữ `max_new_tokens` sát nhu cầu.
- Chỉ dùng LLM judge cho subset cần semantic review, không dùng cho mọi field deterministic.
- Report cost/request và p95 latency cùng quality.

Đừng gọi một số đo là p95 nếu chỉ chạy 1 lần/case hoặc có quá ít sample. Smoke test nhỏ chỉ cho tín hiệu sơ bộ; performance gate cần warmup, nhiều lần lặp và cùng hardware/load profile.

## 12. Best Solution Theo Context

| Context | Best solution thường gặp | Vì sao |
|---|---|---|
| JSON classification/extraction | Schema validation + exact match + regression gate | Deterministic, rẻ, dễ CI |
| Support answer free-form | Format checks + contains + human sample + LLM judge | Kết hợp correctness và tone |
| Safety-sensitive assistant | Safety regression gate + human review bắt buộc | Không giao hết cho judge model |
| Adapter iteration nhanh | Small golden set trong CI + full set nightly | Cân bằng tốc độ và coverage |
| Enterprise release | Versioned golden set + audit trail + canary + rollback | Cần traceability |
| Cost tối ưu | Cache, batch, judge subset, model nhỏ cho judge nếu đã calibrated | Giảm chi phí eval |

## 13. Dùng Được Trong Production Không?

Có, evaluation trước/sau fine-tune là bắt buộc nếu muốn dùng fine-tuned model trong production. Nhưng cần các điều kiện sau:

- Golden dataset được version, không trộn với train set.
- Eval runner deterministic, tái lập được, log đủ prompt/model/config/output/metric.
- Có metric theo contract, task, quality, regression, safety, latency và cost.
- Có release gate rõ: ngưỡng pass/fail trước khi deploy.
- Có human review cho case high-risk và calibration cho LLM-as-a-judge.
- Có regression set tăng dần từ lỗi production.
- Có rollback plan cho adapter/model version cũ.
- Có online monitoring sau deploy vì offline eval không bao phủ toàn bộ traffic thật.

Nếu thiếu các điều kiện này, fine-tune vẫn có thể dùng trong experiment hoặc internal tool low-risk, nhưng chưa nên gọi là production-ready.

## 14. Checklist Trước Khi Deploy

- [ ] Golden set có đủ normal, edge, format, regression, safety, OOD.
- [ ] Golden set không nằm trong train data.
- [ ] Prompt template và decoding config được cố định.
- [ ] Base và fine-tuned model chạy cùng eval runner.
- [ ] Report có aggregate và per-tag metrics.
- [ ] Raw outputs được lưu để audit.
- [ ] JSON/schema/enum checks đạt ngưỡng.
- [ ] Regression pass đạt ngưỡng.
- [ ] Safety critical failure bằng 0.
- [ ] Human review đã xem top regressions.
- [ ] LLM judge đã được calibrate bằng sample human review.
- [ ] p95 latency và cost/request không vượt budget.
- [ ] Rollback path đã được thử.

## 15. Quiz Nhanh

1. Vì sao không được evaluate fine-tuned model trên train set?
2. `format accuracy` khác gì `task accuracy`?
3. Khi nào exact match là metric tốt, khi nào không?
4. Vì sao LLM-as-a-judge nên được calibrate bằng human review?
5. Nếu aggregate score tăng nhưng safety regression có 1 lỗi critical, có deploy không?
6. Vì sao cần report per-tag thay vì chỉ report trung bình?
7. Dấu hiệu nào cho thấy fine-tuned model bị overfitting?
