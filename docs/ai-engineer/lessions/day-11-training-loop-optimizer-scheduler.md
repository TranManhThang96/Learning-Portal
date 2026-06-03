# Day 11: Training Loop, Optimizer, Scheduler

Bài học đã được tách thành folder riêng để dễ học, dễ chạy thực hành và dễ bảo trì.

## Nội dung

- [Lession](./day-11-training-loop-optimizer-scheduler/lession.md): lộ trình học trong ngày, mục tiêu, mental model, checklist và câu trả lời production.
- [Document](./day-11-training-loop-optimizer-scheduler/document.md): giải thích chi tiết training loop, optimizer, scheduler, regularization, mixed precision, checkpoint, logging, performance và trade-off.
- [Exercise](./day-11-training-loop-optimizer-scheduler/exercise.md): bài thực hành PyTorch training job gần production cho binary classifier, có seed, device, `Dataset`/`DataLoader`, train/eval loop, gradient clipping, scheduler, early stopping, checkpoint và metric logging.
- [Code](./day-11-training-loop-optimizer-scheduler/day11_training_loop.py): script runnable tương ứng với bài thực hành.

Mục tiêu chính: biến kiến thức PyTorch Fundamentals ở Day 10 thành một training workflow đủ chuẩn để chuẩn bị cho fine-tuning model NLP ở Day 16.
