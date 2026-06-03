# Day 28: Evaluation trước/sau Fine-tune

Bài này đã được tách thành folder riêng để dễ học, dễ review và dễ mở rộng:

- [Lession: kiến thức chính](day-28-evaluation-truoc-sau-fine-tune/lession.md)
- [Document: production reference](day-28-evaluation-truoc-sau-fine-tune/document.md)
- [Exercise: bài thực hành](day-28-evaluation-truoc-sau-fine-tune/exercise.md)

Gợi ý học trong 2 giờ:

1. Đọc `lession.md` để hiểu cách thiết kế golden dataset, metric và before/after comparison.
2. Mở `document.md` khi cần template production: eval schema, deterministic prompts, metric computation, JSON report, judge rubric và regression gate.
3. Làm `exercise.md` để tự tạo evaluation runner so sánh base model với fine-tuned model, rồi quyết định deploy hoặc rollback.
