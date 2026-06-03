# Day 16: Fine-tune PhoBERT/BERT Classifier

Bài Day 16 đã được tách thành folder riêng để dễ học, thực hành và bảo trì.

## Nội dung

- [Lesson](./day-16-fine-tune-phobert-bert-classifier/lession.md): bài học chính, đi từ problem framing đến production decision.
- [Document](./day-16-fine-tune-phobert-bert-classifier/document.md): tài liệu tham chiếu, checklist, metric template, deployment notes.
- [Exercise](./day-16-fine-tune-phobert-bert-classifier/exercise.md): bài tập thực hành theo từng bước.
- [Training script](./day-16-fine-tune-phobert-bert-classifier/train_sentiment.py): train baseline TF-IDF + Logistic Regression và fine-tune Transformer.
- [Serving script](./day-16-fine-tune-phobert-bert-classifier/serve_sentiment.py): FastAPI inference service.

## Output sau bài học

Bạn sẽ có một mini-project sentiment classifier tiếng Việt gồm:

- Baseline `TF-IDF + Logistic Regression`.
- Fine-tuned `PhoBERT/BERT` bằng HuggingFace `Trainer`.
- Evaluation bằng accuracy, macro F1, classification report, confusion matrix và error samples.
- Export artifact gồm model, tokenizer, label mapping, metric và manifest.
- FastAPI inference API có request validation, health endpoint, latency và confidence.
- Production checklist trả lời rõ: dùng được trong production không, và cần điều kiện gì.
