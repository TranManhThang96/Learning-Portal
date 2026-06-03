# Day 18: Prompt Engineering Thực Chiến

Trang này là điều hướng cho Day 18. Nội dung chi tiết đã được tách vào folder riêng theo yêu cầu review.

## Mục tiêu

- Thiết kế prompt như một API contract có input, constraint, output schema và failure policy.
- Phân biệt zero-shot, few-shot, role prompting, constraint prompting và cách dùng reasoning prompt đúng mức.
- Xây prompt library cho 5 use case: summarization, classification, data extraction, code review và customer support.
- Tạo golden set, chạy eval, quản lý prompt versioning, rollout bằng A/B test hoặc canary.
- Nhận diện prompt injection risk và biết điều kiện để dùng prompt trong production.

## Nội dung

1. [Bài học chính](day-18-prompt-engineering-thuc-chien/lession.md)
2. [Tài liệu tra cứu và prompt library mẫu](day-18-prompt-engineering-thuc-chien/document.md)
3. [Bài tập thực hành, golden set và production review](day-18-prompt-engineering-thuc-chien/exercise.md)
4. [Script kiểm tra prompt library/golden set](day-18-prompt-engineering-thuc-chien/prompt_eval.py)

## Gợi ý học

Đọc Day 17 trước để nắm model behavior, token budget và decoding params. Sau Day 18, chuyển sang Day 19 để biến output contract thành JSON Schema, function calling, validation và retry strategy.
