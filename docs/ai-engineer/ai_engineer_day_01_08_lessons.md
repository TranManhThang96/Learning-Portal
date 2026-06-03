# 8 Bai Hoc Dau Tien Cho AI Engineer

Nguon: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, Phase 1 - ML Foundation.

Doi tuong: Senior Software Engineer muon chuyen sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus.

Khung hoc moi ngay: 2 gio.

```text
10 phut  - Doc TL;DR va muc tieu
35 phut  - Hoc concept chinh
45 phut  - Hands-on/code/design
20 phut  - Ghi chu trade-off, performance, production concern
10 phut  - Update learning log
```

## Muc Luc

| Ngay | Chu de | Output chinh |
|---:|---|---|
| Day 1 | AI Mindset cho Senior SE | Bang quyet dinh rule/ML/RAG/LLM cho 5 bai toan |
| Day 2 | Math du dung cho ML | Dot product, cosine similarity, gradient descent bang Python |
| Day 3 | ML Fundamentals | Baseline classification experiment |
| Day 4 | Python ML Stack | Pipeline NumPy/Pandas/scikit-learn |
| Day 5 | Feature Engineering | Preprocessing pipeline cho numerical/categorical/text/datetime |
| Day 6 | Model Evaluation Metrics | Metric va threshold theo business cost |
| Day 7 | Error Analysis, Data Leakage, Threshold Tuning | False positive/false negative analysis va threshold tuning |
| Day 8 | Mini-project - Customer Churn ML Pipeline | Pipeline churn end-to-end, artifact, inference function |

---

# Day 1: AI Mindset cho Senior SE

## Muc Tieu

- Phan biet rule-based system, ML system, Deep Learning system va LLM system.
- Biet khi nao nen dung rule, ML, RAG, LLM hoac khong dung AI.
- Map duoc AI concepts ve API, config, build process, test suite, observability, rollback.
- Nhan dien failure mode dac thu cua AI system trong production.
- Phan tich 5 bai toan thuc te theo huong production decision.

## TL;DR

AI system khong giong backend service deterministic. Thay vi viet toan bo rule bang code, ban dung data va model de tao mot function co tinh xac suat. Voi Senior SE, cach tiep can dung la xem model nhu mot dependency co version, latency, cost, SLA, monitoring va rollback path. Khong phai bai toan nao cung can AI: neu rule don gian, on dinh, re va de explain thi rule-based van la lua chon tot hon.

## 1. Rule-based vs ML vs DL vs LLM

### Rule-based system

Rule-based system la logic ban viet truc tiep:

```python
if transaction.amount > 10_000 and user.country != card.country:
    flag_as_suspicious()
```

Dac diem:

- Deterministic: cung input luon ra cung output.
- De debug: doc code thay logic.
- De test: expected output ro rang.
- De explain: bi block vi amount vuot threshold.
- Kho scale khi rule nhieu, conflict va domain phuc tap.

Nen dung rule-based khi logic ro, it thay doi, can audit/explain va latency rat thap.

### ML system

ML system hoc pattern tu data:

```text
features = [tenure_months, monthly_charges, support_tickets, contract_type]
model.predict_proba(features) -> churn_probability = 0.82
```

Map sang backend:

| AI concept | SE equivalent |
|---|---|
| Model | Business function sinh ra tu data |
| Training | Build process |
| Hyperparameter | Config |
| Feature | Input contract |
| Evaluation | Test suite dang xac suat |
| Inference | Runtime API call |
| Model artifact | Build artifact |
| Model registry | Artifact registry |
| Drift monitoring | Runtime observability |

Khac biet quan trong: ML thuong tra score/probability, con business layer moi ra decision.

```python
if churn_probability >= retention_threshold:
    send_retention_offer(customer_id)
```

### Deep Learning system

Deep Learning la ML dung neural network nhieu tang. Manh voi unstructured data nhu text, image, audio.

Nen dung khi:

- Feature thu cong kho thiet ke.
- Data lon.
- Pattern phi tuyen phuc tap.
- Input chinh la text/image/audio.

Khong nen voi tay qua som khi:

- Data tabular nho.
- Can explainability cao.
- Latency/cost chat.
- Logistic Regression, Random Forest, XGBoost da du tot.

### LLM system

LLM dung cho generation, reasoning, extraction, summarization, tool calling, chatbot, coding assistant.

Dac thu:

- Input/output la token.
- Output co the non-deterministic.
- Co context window va token cost.
- Co hallucination.
- Co prompt injection risk.
- Can schema validation, guardrails, logging va fallback.

LLM khong phai database. Neu can tra loi theo thong tin chinh xac, cap nhat, co source, thuong can RAG hoac tool calling.

## 2. Model nhu mot dependency production

Trong software truyen thong:

```text
output = function_written_by_engineer(input)
```

Trong ML:

```text
model = train(data, algorithm, hyperparameters)
output = model(input)
```

Logic khong chi nam trong source code nua. No nam trong:

- Training data.
- Feature engineering.
- Algorithm.
- Hyperparameters.
- Model version.
- Threshold.
- Runtime preprocessing.
- Post-processing.

Mot bug ML co the den tu data source doi schema, feature tinh sai, training-serving skew, model artifact sai version, threshold khong con phu hop, distribution shift hoac data leakage.

## 3. Training nhu build process, inference nhu runtime API

Training pipeline:

```text
source data + feature code + model code + config -> model artifact
```

Nen co:

- Dataset version.
- Feature code version.
- Hyperparameter config.
- Metrics.
- Artifact output.
- Reproducibility.
- Approval gate truoc deploy.

Inference path:

```text
API request
  -> validate input
  -> fetch/generate features
  -> transform features
  -> model.predict_proba()
  -> apply threshold
  -> return decision
  -> log prediction + model_version
```

Production inference can quan tam p50/p95/p99 latency, throughput, timeout, retry, idempotency, input validation, output contract, audit va cost/request.

## 4. Evaluation khong giong unit test

Unit test thuong la:

```text
input A -> expected B
```

ML evaluation la thong ke:

```text
precision = 0.81
recall = 0.73
ROC-AUC = 0.89
```

Accuracy co the gay ao tuong. Fraud rate 0.5% thi model luon predict "not fraud" co the dat 99.5% accuracy nhung business value bang 0.

AI test suite nen gom:

- Data validation.
- Metric threshold.
- Segment-level evaluation.
- Golden dataset regression test.
- Latency benchmark.
- Cost benchmark.
- Safety test.
- Human review cho sample quan trong.

## Trade-offs

| Lua chon | Nen dung khi | Khong nen dung khi | Production note |
|---|---|---|---|
| Rule-based | Logic ro, can explain, latency rat thap | Rule qua nhieu, pattern phuc tap | De test, de audit |
| Classical ML | Tabular prediction/classification | Text/image raw phuc tap | Baseline manh cho business data |
| Deep Learning | Data lon, unstructured | Data it, can explain | Can GPU/compute/monitoring |
| LLM | Language reasoning/generation/extraction | Task don gian co rule ro | Can guardrails va cost control |
| RAG | Tra loi theo tai lieu cap nhat, can citation | Khong can knowledge rieng | Phu thuoc retrieval quality |
| Fine-tuning | Can style/format/domain behavior on dinh | Can knowledge realtime | Khong thay database/RAG |

Guidance:

- Neu co the giai bang SQL/rule don gian, dung SQL/rule.
- Neu prediction tren tabular data, bat dau bang Logistic Regression/XGBoost.
- Neu hoi dap theo tai lieu noi bo, uu tien RAG hon fine-tuning.
- Neu can JSON on dinh tu text, dung LLM + schema validation + retry.
- Neu decision co risk tai chinh/phap ly, can human-in-the-loop hoac threshold than trong.

## Best Practices Tu Industry

1. Baseline-first: bat dau bang rule, SQL heuristic, Logistic Regression hoac keyword search.
2. Treat model as versioned dependency: model co version, owner, metrics, changelog va rollback path.
3. Separate prediction from decision: model tra score, policy layer quyet dinh action.
4. Log du de debug: request id, model version, feature version, score, threshold, latency, outcome neu co.
5. Design for human override voi use case co risk cao.

## Performance Considerations

- Rule-based: microseconds den vai milliseconds.
- Classical ML inference: thuong vai milliseconds neu feature san.
- Deep Learning: 10ms den vai tram ms tuy model/hardware.
- LLM API: vai tram ms den nhieu giay, phu thuoc token.
- RAG them retrieval, reranking va generation latency.
- Neu can p95 duoi 100ms, LLM truc tiep trong request path thuong khong phu hop tru khi async hoac cached.

## Production Concerns

- Security: khong execute LLM output truc tiep; tool calling can allowlist va permission check.
- Reliability: external AI provider co the timeout/rate limit; can fallback/circuit breaker.
- Observability: monitor latency, error rate, token usage, cost/request, prediction distribution.
- Privacy: khong gui PII/secret sang third-party model neu policy khong cho phep.
- Rollback: rollback model, prompt, threshold va feature config.
- Compliance: decision anh huong user can audit trail va explainability.

## Ung Dung Thuc Te

1. Customer churn prediction: classical ML phu hop hon LLM, output la probability.
2. Chatbot CSKH: RAG + LLM neu tra loi theo policy/tai lieu cong ty.
3. Fraud detection: ML classification + rule guardrails + review queue.

## Hands-on Trong 60-90 Phut

Phan tich 5 bai toan theo template:

```markdown
## Problem: <name>

### Business objective

### Candidate approach
Rule-based / ML / DL / RAG / LLM / Hybrid

### Vi sao chon approach nay?
Data, latency, explainability, cost, risk.

### Input/output contract

### Production risks
Security, latency, cost, data quality, drift, hallucination, false positive/negative.

### Monitoring

### Rollback/fallback
```

Goi y:

| Bai toan | Approach goi y | Risk chinh | Fallback |
|---|---|---|---|
| Fraud detection | Classical ML + rule guardrails | FP block nham, FN mat tien | Rule threshold |
| Customer churn | Logistic Regression/XGBoost | Drift sau campaign/pricing | Heuristic theo tenure/support |
| Chatbot CSKH | RAG + LLM | Hallucination, prompt injection | Human support |
| Search tai lieu | Hybrid search BM25 + vector | Permission leakage | BM25 |
| Recommendation | Ranking ML + heuristic | Cold start, filter bubble | Popular/category-based |

## Tu Kiem Tra

1. Khi nao rule-based tot hon ML?
2. Vi sao accuracy nguy hiem trong fraud detection?
3. Training giong build process o diem nao?
4. Vi sao model khong nen truc tiep quyet dinh business action?
5. LLM hallucination khac bug backend thong thuong the nao?

## Checklist

- [ ] Phan biet duoc rule-based, ML, DL, LLM.
- [ ] Map duoc model/training/inference/evaluation sang SE concepts.
- [ ] Phan tich xong 5 bai toan thuc te.
- [ ] Voi moi bai toan, chon approach va neu trade-off.
- [ ] Ghi lai it nhat 3 production risks cua AI system.

## Tai Lieu Tham Khao

- Google Machine Learning Crash Course.
- Chip Huyen: Designing Machine Learning Systems.
- Full Stack Deep Learning.
- OpenAI Cookbook.
- Keywords: `training-serving skew`, `data drift`, `model registry`, `ML monitoring`, `LLM hallucination`.

---

# Day 2: Math Du Dung Cho ML

## Muc Tieu

- Hieu vector, matrix, tensor o muc du dung cho ML/embedding.
- Implement dot product va cosine similarity bang Python thuan.
- Hieu gradient descent truc giac va chay vi du toi uu `f(x) = x^2`.
- Biet probability, expected value, entropy, Bayes theorem dung de lam gi trong ML.
- Map math concepts sang search, ranking, recommendation, RAG va model training.

## TL;DR

Math trong ML khong can bat dau bang proof. Voi AI Engineer thien production, ban can hieu vector la representation, dot product/cosine la cach do do gan, gradient la huong cap nhat de giam loss, probability la ngon ngu cua uncertainty. Nhung concept nay se xuat hien lai trong embedding search, classifier confidence, loss function, optimizer, RAG retrieval va evaluation.

## 1. Vector, Matrix, Tensor

Vector la list so dai dien cho object:

```text
customer = [tenure_months, monthly_charges, support_tickets]
document_embedding = [0.12, -0.03, 0.88, ...]
```

Map:

| Concept | SE analogy |
|---|---|
| Vector | Row da encode thanh numeric representation |
| Dimension | So cot/feature |
| Embedding | Representation cho semantic search |
| Vector DB | Database toi uu cho similarity search |

Matrix la bang so 2D:

```text
X = [
  [4, 89.9, 3],
  [24, 39.0, 0],
  [2, 120.0, 8]
]
```

Moi row thuong la sample, moi column la feature.

Tensor la generalization cua vector/matrix:

```text
scalar: 5
vector: [1, 2, 3]
matrix: [[1, 2], [3, 4]]
tensor 3D: batch_size x sequence_length x embedding_dim
```

Trong LLM, input co the la:

```text
32 x 512 x 4096
```

Nghia la batch 32 requests, moi request 512 tokens, moi token co vector 4096 chieu.

## 2. Dot Product Va Cosine Similarity

Dot product:

```text
a = [1, 2, 3]
b = [4, 5, 6]
dot(a, b) = 1*4 + 2*5 + 3*6 = 32
```

No giong scoring function:

```text
score = w1*x1 + w2*x2 + w3*x3
```

Cosine similarity:

```text
cosine(a, b) = dot(a, b) / (norm(a) * norm(b))
```

Gia tri gan 1 la rat giong huong, gan 0 la it lien quan, gan -1 la nguoc huong. Trong RAG/vector search, cosine similarity dung de tim document chunk gan query nhat.

## 3. Matrix Multiplication

Thay vi tinh tung request:

```text
score_one = dot(x, w)
```

Ta tinh batch:

```text
scores = X @ W
```

Production relevance:

- Batch inference tang throughput.
- Vectorized operation nhanh hon loop Python.
- GPU toi uu matrix multiplication.
- Transformer chu yeu la nhieu phep matrix multiplication lon.

## 4. Derivative, Gradient, Gradient Descent

Voi:

```text
f(x) = x^2
f'(x) = 2x
```

Neu `x = 3`, gradient la `6`. Muon giam loss thi di nguoc huong gradient:

```text
x = x - learning_rate * gradient
```

Production intuition:

- Learning rate qua lon: training unstable, loss dao dong/diverge.
- Learning rate qua nho: training cham, ton compute.
- Training failure can xem loss curve, khong chi final metric.

## 5. Probability, Expected Value, Entropy, Bayes

Classifier output:

```json
{
  "not_churn": 0.18,
  "churn": 0.82
}
```

Probability model khong mac nhien la su that. Can calibration neu probability dung cho risk/cost decision.

Expected value:

```text
fraud_probability = 0.02
transaction_amount = 10000
expected_loss = 0.02 * 10000 = 200
manual_review_cost = 5
```

Neu expected loss lon hon review cost, dua vao review queue co ly.

Entropy do uncertainty:

```text
[0.99, 0.01] -> entropy thap
[0.51, 0.49] -> entropy cao
```

Entropy cao co the route sang human review hoac active learning.

Bayes theorem giup cap nhat niem tin khi co evidence moi. Truc giac production: base rate rat quan trong, dac biet voi fraud/spam/medical risk.

## Trade-offs

| Chu de | Option A | Option B | Guidance |
|---|---|---|---|
| Similarity | Dot product | Cosine similarity | Cosine tot khi so semantic direction; dot product tot khi magnitude co y nghia |
| Implementation | Python loop | NumPy vectorized | Loop de hoc, NumPy/PyTorch cho production |
| Training | Learning rate cao | Learning rate thap | Cao nhanh nhung de diverge; thap on dinh nhung ton compute |
| Decision | Hard label | Probability + threshold | Production nen giu probability de tune theo business |
| Uncertainty | Ignore entropy | Route entropy cao sang review | Risk cao nen co review/fallback |
| Batch inference | Single request | Batch request | Batch tang throughput nhung co the tang latency cho request don |

## Best Practices Tu Industry

1. Think in shapes: debug ML/DL luon biet shape cua tensor.
2. Vectorize early: Python loop de hoc, vectorized operation cho data lon.
3. Keep raw score, probability and decision separately.
4. Monitor distributions, not only averages.
5. Use numerical tolerance trong test, vi floating point khong nen assert exact equality.

## Performance Considerations

- 1 trieu vectors 768 chieu float32 can khoang `1_000_000 * 768 * 4 bytes = ~3GB`, chua tinh index overhead.
- Cosine scan toan bo vector khong scale; production dung ANN index.
- Batch size lon tang throughput nhung tang memory va co the tang latency.
- Matrix multiplication la core workload cua DL, nen GPU giup nhieu.

## Production Concerns

- Numerical stability: tranh overflow/underflow/divide-by-zero.
- Input validation: feature khong NaN/Inf, dung range.
- Reproducibility: seed giup mot phan, hardware/library van co the khac nho.
- Auditability: luu model version, feature vector summary, probability.
- Privacy: embedding van co the leak thong tin, khong xem la vo hai.

## Ung Dung Thuc Te

1. Semantic search/RAG: query va document thanh embedding vectors, cosine lay top-k.
2. Recommendation: user vector gan item vector thi ranking cao hon.
3. Risk scoring: model tra probability, business layer ap threshold/expected value.

## Hands-on Trong 60-90 Phut

```python
import math
import numpy as np


def dot_product(a, b):
    if len(a) != len(b):
        raise ValueError("Vectors must have same length")
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(sum(x * x for x in a))


def cosine_similarity(a, b):
    norm_a = norm(a)
    norm_b = norm(b)
    if norm_a == 0 or norm_b == 0:
        raise ValueError("Cosine similarity is undefined for zero vector")
    return dot_product(a, b) / (norm_a * norm_b)


def gradient_descent_x_squared(start_x=10.0, learning_rate=0.1, steps=25):
    x = start_x
    history = []
    for step in range(steps):
        loss = x ** 2
        grad = 2 * x
        history.append({"step": step, "x": x, "loss": loss, "grad": grad})
        x = x - learning_rate * grad
    return history


query = [0.9, 0.1, 0.2]
doc_policy = [0.8, 0.2, 0.1]
doc_vpn = [0.1, 0.7, 0.6]

print("Cosine query-policy:", cosine_similarity(query, doc_policy))
print("Cosine query-vpn:", cosine_similarity(query, doc_vpn))

X = np.array([[4, 89.9, 3], [24, 39.0, 0], [2, 120.0, 8]], dtype=float)
weights = np.array([[-0.03], [0.01], [0.4]])
print("Batch scores:")
print(X @ weights)

for row in gradient_descent_x_squared():
    print(row)
```

Bai tap mo rong:

- Doi `learning_rate` thanh `0.01`, `0.5`, `1.1` va quan sat.
- Them document vector va sort theo cosine.
- Tao 5 customer vectors va tinh score bang matrix multiplication.
- Thu zero vector va dam bao code bao loi ro rang.

## Tu Kiem Tra

1. Vi sao cosine similarity hay dung cho semantic search?
2. Dot product xuat hien o dau trong linear model/attention?
3. Learning rate qua cao gay van de gi?
4. Vi sao probability van can threshold?
5. Entropy cao nen xu ly the nao trong production?

## Checklist

- [ ] Giai thich duoc vector, matrix, tensor.
- [ ] Implement dot product bang Python thuan.
- [ ] Implement cosine similarity va xu ly zero vector.
- [ ] Chay gradient descent cho `f(x)=x^2`.
- [ ] Dung NumPy de nhan matrix batch.
- [ ] Hieu expected value, entropy, Bayes o muc ung dung.

## Tai Lieu Tham Khao

- 3Blue1Brown: Essence of Linear Algebra.
- Google Machine Learning Crash Course: Linear regression, gradients.
- NumPy documentation: `numpy.dot`, `matmul`, broadcasting.
- Keywords: `cosine similarity`, `gradient descent`, `entropy`, `expected value`, `embedding vector search`.

---

# Day 3: ML Fundamentals

## Muc Tieu

- Phan biet supervised, unsupervised va reinforcement learning theo goc nhin application/system.
- Hieu train/validation/test split, cross-validation va vai tro cua tung tap.
- Giai thich overfitting, underfitting, bias-variance trade-off bang vi du production.
- Biet chon baseline model cho regression/classification tren tabular data.
- Chay experiment co ban va so sanh Logistic Regression, Random Forest, Gradient Boosting.

## TL;DR

Machine Learning la cach xay function tu data thay vi viet rule thu cong. Voi Senior SE, hay xem model nhu service co contract khong tuyet doi: chat luong phu thuoc data, feature, metric va distribution. Production ML khong bat dau bang model phuc tap, ma bat dau bang baseline do duoc, metric dung va quy trinh evaluation co the lap lai.

## 1. ML Problem Types

### Supervised learning

Dung data co label:

```text
features -> label
```

Vi du:

- Fraud detection.
- Churn prediction.
- Lead scoring.
- Ticket classification.
- ETA prediction.
- Demand forecasting.

Regression du doan so lien tuc, classification du doan class roi rac.

| Cau hoi | Loai bai toan |
|---|---|
| Output la so lien tuc? | Regression |
| Output la nhan roi rac? | Classification |
| Output la probability cua event? | Classification |
| Output la ranking? | Ranking/recommendation |
| Output la text dai? | LLM/generation |

### Unsupervised learning

Khong co label, tim pattern/cau truc:

- Customer segmentation.
- Anomaly detection.
- Topic clustering.
- Embedding visualization.
- Duplicate detection.

### Reinforcement learning

Agent action -> environment reward -> policy improve. Voi AI application engineer, Phase 1 chi can biet truc giac. Production concern lon nhat la exploration anh huong user that, nen thuong can A/B testing, bandit hoac offline evaluation truoc.

## 2. Train/Validation/Test Split

Trong software:

```text
unit test -> integration test -> staging -> production
```

Trong ML:

```text
train set -> validation set -> test set -> production data
```

- Train set: model hoc parameter.
- Validation set: chon model, tune hyperparameter, tune threshold.
- Test set: estimate quality cuoi truoc release.

Neu dung test set de tune nhieu lan, test set khong con la acceptance test doc lap.

Voi time-dependent problem:

```text
train: Jan-Mar
validation: Apr
test: May
```

Khong nen shuffle random neu production luon du doan tu qua khu sang tuong lai.

## 3. Cross-validation

5-fold cross-validation train/evaluate 5 lan tren 5 fold khac nhau de metric on dinh hon.

Nen dung khi:

- Dataset nho/vua.
- So sanh model truyen thong.
- Muon giam phu thuoc vao mot lan split.

Khong nen lam dung khi:

- Dataset rat lon.
- Time-series co thu tu thoi gian.
- Deep learning/LLM fine-tuning ton compute.

## 4. Overfitting, Underfitting, Bias-Variance

Underfitting:

```text
train score thap
validation score thap
```

Model qua don gian, it feature, khong bat duoc pattern.

Overfitting:

```text
train score rat cao
validation score thap hon nhieu
```

Model hoc ca noise/exception cua training data.

| Tinh huong | Train score | Validation score | Van de | Cach xu ly |
|---|---:|---:|---|---|
| High bias | Thap | Thap | Underfitting | Them feature, model phuc tap hon |
| High variance | Cao | Thap | Overfitting | Regularization, them data, giam complexity |
| Good fit | Cao vua | Cao tuong duong | On | Chuyen sang error analysis |
| Suspicious fit | Gan 100% | Gan 100% | Co the leakage | Audit feature/data split |

## 5. Baseline-first Mindset

Baseline la moc don gian:

- Classification: majority class baseline.
- Regression: predict mean/median.
- Tabular: Logistic Regression hoac Random Forest.
- Text classification: TF-IDF + Logistic Regression.
- RAG: BM25 truoc embedding/reranking.

Production rule:

```text
Khong deploy model neu chua vuot baseline theo metric gan voi business.
```

## 6. Algorithms Can Biet

| Model | Manh o dau | Han che |
|---|---|---|
| Linear Regression | Regression baseline, nhanh, explainable | Quan he phai gan tuyen tinh |
| Logistic Regression | Classification baseline, probability, nhanh | Kho hoc interaction phuc tap |
| Decision Tree | De hieu, non-linear | De overfit |
| Random Forest | Tabular manh, it tuning | Artifact/latency lon hon |
| XGBoost/Gradient Boosting | Tabular rat manh | Nhieu hyperparameter, co the overfit |
| SVM | Dataset nho/vua, sparse high-dimensional | Scale kem voi data lon |
| KNN | Similarity truc giac | Inference dat neu khong co index |

## Trade-offs

| Lua chon | Khi nen dung | Khi khong nen dung | Production note |
|---|---|---|---|
| Logistic Regression | Baseline, explainability, latency thap | Quan he phi tuyen manh | De deploy, phu hop traffic cao |
| Random Forest | Tabular data vua, it tuning | Latency rat chat | Kiem soat tree/depth |
| XGBoost/LightGBM | Tabular can quality cao | Team chua co eval discipline | Version params, early stopping |
| KNN | Prototype similarity nho | Realtime large-scale | Dung ANN/vector index neu scale |
| Neural Network | Data lon/unstructured | Data it, can explain | Compute/monitoring phuc tap |
| LLM | Language reasoning/generation | Rule/ML don gian | Dat, cham, can guardrails |

Guidance:

- Tabular classification: Logistic Regression + Random Forest truoc.
- Can accuracy cao hon: thu Gradient Boosting/XGBoost/LightGBM.
- Can explainability: Logistic Regression, shallow tree, SHAP.
- API latency rat thap: Logistic Regression la v1 tot.
- Text ngan: TF-IDF + Logistic Regression truoc Transformer.

## Best Practices Tu Industry

1. Luon tao baseline truoc model phuc tap.
2. Tach data split theo thoi gian neu bai toan co timeline.
3. Version dataset, feature definition, params, metric va artifact.
4. Dung metric phu hop, khong chi accuracy.
5. Treat model as service dependency: timeout, fallback, monitoring, rollback.

## Performance Considerations

- Logistic Regression inference rat nhanh neu feature extraction nhe.
- Random Forest cost tang theo `n_estimators * max_depth`.
- KNN naive la O(n) theo training samples.
- Cross-validation nhan training time theo so fold.
- Feature computation co the dat hon model inference.

## Production Concerns

- Data leakage: audit feature availability time.
- Train-serving skew: preprocessing train/inference phai giong nhau.
- Model versioning: artifact, params, code hash, dataset snapshot.
- Monitoring: prediction distribution, confidence, latency, error rate.
- Drift: production data thay doi theo thoi gian.
- Explainability/privacy/reproducibility tuy domain.

## Hands-on Trong 60-90 Phut

```bash
pip install numpy pandas scikit-learn
```

```python
import time
import numpy as np
import pandas as pd

from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split, cross_validate
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

RANDOM_STATE = 42


def evaluate_model(name, model, X_train, X_test, y_train, y_test):
    start_train = time.perf_counter()
    model.fit(X_train, y_train)
    train_ms = (time.perf_counter() - start_train) * 1000

    start_predict = time.perf_counter()
    y_pred = model.predict(X_test)
    predict_ms = (time.perf_counter() - start_predict) * 1000

    y_score = model.predict_proba(X_test)[:, 1]
    return {
        "model": name,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_score),
        "train_ms": train_ms,
        "predict_ms_per_1000": predict_ms / len(X_test) * 1000,
    }


data = load_breast_cancer(as_frame=True)
X, y = data.data, data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
)

models = [
    ("logistic_regression", Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
    ])),
    ("random_forest", RandomForestClassifier(
        n_estimators=200, max_depth=6, random_state=RANDOM_STATE, n_jobs=-1
    )),
    ("hist_gradient_boosting", HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.05, max_leaf_nodes=15, random_state=RANDOM_STATE
    )),
]

results = [evaluate_model(name, model, X_train, X_test, y_train, y_test) for name, model in models]
print(pd.DataFrame(results).sort_values("f1", ascending=False))

cv_model = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
])
cv = cross_validate(cv_model, X, y, cv=5, scoring=["accuracy", "precision", "recall", "f1", "roc_auc"])
for metric_name, values in cv.items():
    if metric_name.startswith("test_"):
        print(metric_name, "mean=", np.mean(values), "std=", np.std(values))
```

Sau khi chay, ghi lai:

- Model nao co F1/recall tot nhat?
- Model nao train/predict nhanh nhat?
- Neu API can p99 duoi 20ms, chon model nao?
- Neu day la fraud detection, co chon theo accuracy khong?

## Tu Kiem Tra

1. Vi sao khong nen dung test set de tune hyperparameter?
2. Accuracy 95% co the te trong truong hop nao?
3. Overfitting khac data leakage the nao?
4. Khi nao Logistic Regression tot hon Random Forest trong production?
5. Voi churn prediction, vi sao time split dang tin hon random split?

## Checklist

- [ ] Phan biet supervised, unsupervised, reinforcement learning.
- [ ] Giai thich regression vs classification.
- [ ] Hieu train/validation/test va cross-validation.
- [ ] Nhan dien overfitting, underfitting, bias-variance.
- [ ] Chay 3 model baseline bang scikit-learn.
- [ ] So sanh metric va latency.

## Tai Lieu Tham Khao

- scikit-learn User Guide: Supervised learning.
- Google Machine Learning Crash Course: Generalization.
- Andrew Ng Machine Learning Specialization: train/dev/test split, bias/variance.
- Keywords: `bias variance tradeoff`, `data leakage`, `baseline model`.

---

# Day 4: Python ML Stack

## Muc Tieu

- Dung NumPy, Pandas, scikit-learn de xay ML pipeline co ban.
- Hieu ndarray, broadcasting, vectorization va anh huong performance.
- Xu ly DataFrame: select, filter, groupby, merge, missing values.
- Dung scikit-learn Estimator API, Transformer, Pipeline, ColumnTransformer.
- Train va so sanh Logistic Regression, Random Forest, Gradient Boosting tren dataset Titanic-style.

## TL;DR

Python ML stack gom NumPy cho numerical compute, Pandas cho data wrangling, scikit-learn cho model/pipeline va Matplotlib cho visualization. Voi Senior SE, Pandas giong batch data layer, scikit-learn Pipeline giong workflow co contract ro, model artifact giong deployable binary. Diem quan trong la preprocessing train/inference phai dung chung logic de tranh train-serving skew.

## 1. NumPy: Vectorization Va Memory Mindset

```python
import numpy as np

x = np.array([1, 2, 3])
w = np.array([0.1, 0.2, 0.3])
score = np.dot(x, w)
```

Python loop chay tung phan tu o interpreter level; NumPy day compute xuong optimized C/Fortran routines.

Map:

| NumPy concept | Backend analogy |
|---|---|
| Vectorization | Batch processing thay vi per-record RPC |
| ndarray shape | Schema/dimension contract |
| Broadcasting | Implicit expansion rule |
| dtype | Storage format |
| Matrix multiplication | Bulk compute operation |

Shape la contract:

```text
X shape = (n_samples, n_features)
y shape = (n_samples,)
```

Train co 20 features ma inference chi co 19 features thi fail hoac predict sai neu feature order lech.

## 2. Pandas: Data Wrangling Nhu Batch ETL

Operations thuong dung:

```python
df[["plan", "monthly_charge"]]
df[df["monthly_charge"] > 20]
df["monthly_charge"].fillna(df["monthly_charge"].median())
df.groupby("plan")["monthly_charge"].mean()
orders.merge(customers, on="customer_id", how="left")
```

Map ve SQL:

| Pandas | SQL |
|---|---|
| `df[cols]` | `SELECT cols` |
| `df[df["x"] > 1]` | `WHERE x > 1` |
| `groupby().agg()` | `GROUP BY` |
| `merge()` | `JOIN` |
| `sort_values()` | `ORDER BY` |
| `drop_duplicates()` | `DISTINCT` |

Pandas tot cho EDA/training/batch nho-vua. Voi data lon hon RAM hoac realtime low latency, can can nhac SQL engine, Polars, DuckDB, Spark.

## 3. scikit-learn Estimator API

Estimator:

```python
model.fit(X_train, y_train)
model.predict(X_test)
model.predict_proba(X_test)
```

Transformer:

```python
transformer.fit(X_train)
transformer.transform(X_test)
```

Pipeline:

```text
raw features -> preprocessing -> model
```

Production mindset:

```text
Deploy pipeline, khong chi deploy model.
```

## 4. ColumnTransformer

Numerical va categorical can preprocessing khac nhau:

```python
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

numeric_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
])

categorical_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("encoder", OneHotEncoder(handle_unknown="ignore")),
])

preprocessor = ColumnTransformer([
    ("num", numeric_pipeline, ["age", "fare"]),
    ("cat", categorical_pipeline, ["sex", "embarked", "pclass"]),
])
```

`handle_unknown="ignore"` quan trong vi production data luon co category moi.

## 5. Notebook Workflow Nhung Khong Le Thuoc Notebook

Notebook tot cho EDA, visualization, quick experiment, report. Khong du cho production neu cell chay lon xon, khong config, khong test, khong artifact versioning.

Workflow tot:

```text
notebook exploration
-> script/package repeatable training
-> saved pipeline artifact
-> inference API
-> monitoring
```

## Trade-offs

| Tool/Pattern | Khi nen dung | Khi khong nen dung | Guidance |
|---|---|---|---|
| NumPy | Numerical compute | Data bang phuc tap | Core math/performance-sensitive logic |
| Pandas | EDA, batch nho/vua | Dataset vuot RAM, realtime | Tot cho training, can trong serving |
| Polars/DuckDB | Local analytics nhanh hon Pandas | Team/tooling chua quen | Can nhac khi Pandas cham |
| scikit-learn Pipeline | Tabular ML repeatable | DL workflow phuc tap | Mac dinh nen dung trong Phase 1 |
| Notebook | Exploration/report | Production training duy nhat | Chuyen logic chinh ra script |
| Random split | IID data | Time-series/event-based | Production theo thoi gian dung time split |

## Best Practices Tu Industry

1. Dong goi preprocessing va model trong mot Pipeline.
2. Dung `handle_unknown="ignore"` cho categorical encoder.
3. Set random seed cho experiment.
4. Tach EDA khoi training repeatable.
5. Log metric cung metadata: data split, params, package version, feature list.

## Performance Considerations

- Pandas giu data trong RAM; object dtype overhead co the lon.
- One-hot encoding cardinality cao lam feature space phinh.
- Sparse matrix tiet kiem memory cho one-hot/text.
- `n_jobs=-1` dung nhieu CPU core, can tranh tranh tai nguyen.
- Batch prediction throughput tot hon single-row prediction.

## Production Concerns

- Schema validation: thieu cot/sai dtype fail ro rang.
- Category drift: category moi co the lam quality giam.
- Missing value drift: missing spike bao upstream issue.
- Artifact compatibility: pickle/joblib phu thuoc version thu vien.
- Security: khong load pickle/joblib tu nguon khong tin cay.

## Hands-on Trong 60-90 Phut

```bash
pip install numpy pandas scikit-learn matplotlib joblib
```

```python
import time
import joblib
import numpy as np
import pandas as pd

from sklearn.datasets import fetch_openml, make_classification
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

RANDOM_STATE = 42


def load_titanic_or_fallback():
    try:
        titanic = fetch_openml("titanic", version=1, as_frame=True)
        df = titanic.frame[["pclass", "sex", "age", "sibsp", "parch", "fare", "embarked", "survived"]].copy()
        df["survived"] = df["survived"].astype(int)
        return df, "openml_titanic"
    except Exception:
        X, y = make_classification(n_samples=1000, n_features=6, n_informative=4, random_state=RANDOM_STATE)
        df = pd.DataFrame(X, columns=["age", "fare", "sibsp", "parch", "pclass_numeric", "noise"])
        df["pclass"] = pd.cut(df["pclass_numeric"], bins=3, labels=["1", "2", "3"]).astype(str)
        df["sex"] = np.where(df["noise"] > 0, "male", "female")
        df["embarked"] = np.where(df["fare"] > df["fare"].median(), "S", "C")
        df["survived"] = y
        return df.drop(columns=["pclass_numeric", "noise"]), "synthetic_fallback"


def build_preprocessor(numeric_features, categorical_features):
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("num", numeric_pipeline, numeric_features),
        ("cat", categorical_pipeline, categorical_features),
    ])


def evaluate(name, pipeline, X_train, X_test, y_train, y_test):
    start_train = time.perf_counter()
    pipeline.fit(X_train, y_train)
    train_ms = (time.perf_counter() - start_train) * 1000

    start_predict = time.perf_counter()
    y_pred = pipeline.predict(X_test)
    predict_ms = (time.perf_counter() - start_predict) * 1000
    y_score = pipeline.predict_proba(X_test)[:, 1]

    return {
        "model": name,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_score),
        "train_ms": train_ms,
        "predict_ms_per_row": predict_ms / len(X_test),
    }, pipeline


df, source = load_titanic_or_fallback()
print("Dataset source:", source)
print("Missing value ratio:")
print((df.isna().mean() * 100).sort_values(ascending=False))

target = "survived"
numeric_features = ["age", "sibsp", "parch", "fare"]
categorical_features = ["pclass", "sex", "embarked"]

X = df[numeric_features + categorical_features]
y = df[target]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y)

model_specs = [
    ("logistic_regression", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
    ("random_forest", RandomForestClassifier(n_estimators=200, max_depth=6, random_state=RANDOM_STATE, n_jobs=-1)),
    ("hist_gradient_boosting", HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, random_state=RANDOM_STATE)),
]

results = []
trained = {}
for name, model in model_specs:
    pipeline = Pipeline([
        ("preprocessor", build_preprocessor(numeric_features, categorical_features)),
        ("model", model),
    ])
    metrics, fitted = evaluate(name, pipeline, X_train, X_test, y_train, y_test)
    results.append(metrics)
    trained[name] = fitted

summary = pd.DataFrame(results).sort_values("roc_auc", ascending=False)
print(summary)

best_name = summary.iloc[0]["model"]
joblib.dump(trained[best_name], f"{best_name}_pipeline.joblib")
```

Bai tap:

- Them feature `family_size = sibsp + parch + 1`.
- Save artifact va load lai de predict mot request.
- Viet `predict_survival(model, payload)` co input validation.

## Tu Kiem Tra

1. Vi sao fit scaler/imputer tren toan bo dataset la leakage?
2. Pipeline giup tranh train-serving skew the nao?
3. Khi nao Pandas khong con phu hop?
4. Vi sao `handle_unknown="ignore"` quan trong?
5. Artifact `joblib` co risk bao mat gi?

## Checklist

- [ ] Hieu ndarray, shape, broadcasting, vectorization.
- [ ] Dung Pandas select/filter/groupby/merge/missing values.
- [ ] Hieu Estimator, Transformer, Pipeline.
- [ ] Dung ColumnTransformer cho numerical/categorical.
- [ ] Train 3 model bang cung preprocessing pipeline.
- [ ] Save/load pipeline artifact.
- [ ] Viet inference function co validation.

## Tai Lieu Tham Khao

- NumPy documentation: ndarray, broadcasting.
- Pandas User Guide.
- scikit-learn documentation: Pipeline, ColumnTransformer.
- Keywords: `train serving skew`, `scikit-learn pipeline production`, `pandas memory optimization`.

---

# Day 5: Feature Engineering

## Muc Tieu

- Hieu feature engineering va vi sao anh huong truc tiep den model quality.
- Xu ly numerical, categorical, text, datetime, missing values bang scikit-learn.
- Xay preprocessing pipeline co the tai su dung cho training va inference.
- Nhan dien data leakage khi tao feature.
- Map feature engineering ve schema design, API contract, ETL, observability.

## TL;DR

Feature engineering bien raw data thanh input model hoc duoc. Voi Senior SE, feature la API contract giua data layer va model: contract sai thi model fail du algorithm tot. Trong production, feature engineering khong phai notebook trick, ma la pipeline can versioning, test, monitoring va tinh nhat quan giua training/inference.

## 1. Feature La Gi?

Vi du churn:

```text
Raw data:
- customer_id
- contract_type
- monthly_charges
- signup_date
- last_login_at
- support_ticket_count
- latest_ticket_text

Features:
- contract_type_onehot_month_to_month
- monthly_charges_scaled
- account_age_days
- days_since_last_login
- support_ticket_count_last_30d
- ticket_text_tfidf_vector
```

Map:

| Backend concept | ML equivalent |
|---|---|
| API request schema | Feature schema |
| DB normalization | Feature transformation |
| Cache key design | Feature identity tai thoi diem prediction |
| ETL pipeline | Feature generation pipeline |
| Contract test | Feature validation |
| Backward compatibility | Feature versioning |
| Observability | Feature drift/missing rate/distribution shift |

## 2. Numerical Features

Van de:

- Scale lech lon.
- Outlier.
- Distribution skewed.
- Missing value.

Scaling:

- `StandardScaler`: mean 0, std 1. Tot cho Logistic Regression, SVM, KNN, Neural Network.
- `MinMaxScaler`: ve `[0, 1]`, nhay voi outlier.
- `RobustScaler`: dung median/IQR, tot voi revenue/transaction/usage co outlier.

Log transform:

```python
df["log_total_charges"] = np.log1p(df["total_charges"])
```

Dung cho revenue, transaction amount, API usage, session duration.

Binning:

```text
age: 18-25, 26-35, 36-50, 51+
```

Tot khi business threshold ro, nhung mat thong tin va tao boundary gap.

## 3. Categorical Features

One-hot encoding:

```text
contract_type = monthly
contract_monthly = 1
contract_yearly = 0
contract_two_year = 0
```

An toan cho category cardinality thap-vua.

Label encoding:

```text
free = 0
basic = 1
premium = 2
enterprise = 3
```

Chi dung khi category co thu tu that hoac tree model chap nhan duoc.

Target encoding:

```text
payment_method = electronic_check -> historical_churn_rate = 0.42
```

Manh voi high-cardinality, nhung rat de leakage. Phai tinh tren training fold, dung CV encoding va smoothing.

## 4. Text Features: TF-IDF

TF-IDF bien text thanh sparse vector dua tren tan suat tu.

```python
from sklearn.feature_extraction.text import TfidfVectorizer

tfidf = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=3, max_df=0.9)
X_text = tfidf.fit_transform(train_texts)
```

Production note:

- Vocabulary phai save cung model.
- Khong fit lai vectorizer o inference.
- `max_features` anh huong memory/latency.
- Text preprocessing phai nhat quan.

TF-IDF la baseline text quan trong truoc khi dung Transformer.

## 5. Datetime Features

Datetime raw thuong khong nen dua truc tiep vao model. Tao:

- `account_age_days`.
- `days_since_last_login`.
- `signup_month`.
- `signup_day_of_week`.
- Rolling counts: `count_last_7d`, `count_last_30d`.

Production concern: point-in-time correctness. Neu predict ngay `2026-05-08`, khong duoc dung event sau ngay do.

## 6. Missing Data Imputation

Missing co the mang signal:

- `last_login_at` missing: user chua tung login.
- `support_ticket_text` missing: user chua mo ticket.

Cach xu ly:

| Cach | Khi dung |
|---|---|
| Drop rows | Missing it |
| Mean/median | Numerical baseline |
| Most frequent | Categorical don gian |
| Constant `__missing__` | Missing co y nghia |
| Missing indicator | Missing la signal |
| Model-based imputation | Dataset lon, pattern phuc tap |

## 7. Feature Selection

Giup giam noise, latency, memory va overfitting:

- Drop feature qua nhieu missing.
- Drop constant/near-constant.
- Drop duplicate/correlated.
- Dung model importance.
- Dung L1 regularization.
- Dung domain knowledge.

Khong chon feature dua tren test set.

## Trade-offs

| Lua chon | Uu diem | Nhuoc diem | Guidance |
|---|---|---|---|
| StandardScaler | Tot cho linear/SVM/NN | Nhay outlier | Mac dinh neu model khong phai tree |
| RobustScaler | Chong outlier | Co the kem neu data sach | Revenue/transaction/latency |
| One-hot | De hieu, it leakage | No chieu voi cardinality cao | Category < vai tram |
| Label encoding | Gon | Tao thu tu gia | Category ordinal hoac tree model |
| Target encoding | Manh high-cardinality | Rat de leakage | Chi dung khi co CV encoding |
| TF-IDF | Baseline text nhanh | Khong hieu semantic sau | Lam baseline truoc Transformer |
| Binning | Explainable | Mat thong tin | Dung khi threshold business ro |

## Best Practices Tu Industry

1. Dung `Pipeline` va `ColumnTransformer`, khong preprocessing thu cong roi copy sang inference.
2. Split train/test truoc, sau do moi fit preprocessing tren train.
3. Version feature schema nhu API contract.
4. Log missing rate, distribution, min/max, cardinality.
5. Luon co baseline don gian truoc model phuc tap.

## Performance Considerations

- One-hot cardinality cao co the tao sparse matrix rat lon.
- TF-IDF `max_features=50_000` co the on cho batch, nhung phai do latency online.
- Feature generation tu join nhieu bang co the la bottleneck lon hon model.
- Rolling feature nen precompute neu latency target < 100ms.

## Production Concerns

- Data leakage: khong dung future info, khong fit preprocessing tren test.
- Train-serving skew: logic train/inference khac nhau.
- Schema drift: upstream doi type/format.
- Missing spike: source loi lam missing rate tang.
- PII: text feature co the chua email/phone/address.
- Model version phai gan voi feature pipeline version.

## Hands-on Trong 60-90 Phut

```bash
pip install pandas numpy scikit-learn
```

```python
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler


def build_sample_data(n=1000, seed=42):
    rng = np.random.default_rng(seed)
    contract_type = rng.choice(["monthly", "one_year", "two_year"], size=n, p=[0.55, 0.30, 0.15])
    payment_method = rng.choice(["credit_card", "bank_transfer", "electronic_check"], size=n)
    monthly_charges = rng.normal(70, 25, size=n).clip(10, 180)
    support_tickets = rng.poisson(1.2, size=n)
    days_since_last_login = rng.integers(0, 120, size=n)
    latest_ticket_text = np.where(
        support_tickets > 2,
        "mang cham loi lien tuc muon huy",
        "dich vu on can ho tro hoa don",
    )
    churn_score = (
        0.9 * (contract_type == "monthly").astype(float)
        + 0.7 * (payment_method == "electronic_check").astype(float)
        + 0.03 * support_tickets
        + 0.015 * days_since_last_login
        + 0.006 * monthly_charges
        + rng.normal(0, 0.8, size=n)
        - 2.0
    )
    churn_prob = 1 / (1 + np.exp(-churn_score))
    churn = rng.binomial(1, churn_prob)
    df = pd.DataFrame({
        "contract_type": contract_type,
        "payment_method": payment_method,
        "monthly_charges": monthly_charges,
        "support_tickets": support_tickets,
        "days_since_last_login": days_since_last_login,
        "latest_ticket_text": latest_ticket_text,
        "churn": churn,
    })
    df.loc[rng.choice(df.index, size=int(n * 0.05), replace=False), "monthly_charges"] = np.nan
    return df


df = build_sample_data()
X = df.drop(columns=["churn"])
y = df["churn"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

numeric_features = ["monthly_charges", "support_tickets", "days_since_last_login"]
categorical_features = ["contract_type", "payment_method"]
text_feature = "latest_ticket_text"

preprocessor = ColumnTransformer([
    ("num", Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", RobustScaler()),
    ]), numeric_features),
    ("cat", Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ]), categorical_features),
    ("text", TfidfVectorizer(max_features=1000, ngram_range=(1, 2), min_df=2), text_feature),
])

model = Pipeline([
    ("preprocess", preprocessor),
    ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
])

model.fit(X_train, y_train)
y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)[:, 1]
print(classification_report(y_test, y_pred))
print("ROC-AUC:", round(roc_auc_score(y_test, y_prob), 4))
```

Bai tap:

- Thay `RobustScaler` bang `StandardScaler`.
- Bo text feature va do ROC-AUC.
- Them feature `high_support_ticket = support_tickets >= 3`.
- In shape sau preprocessing.
- Viet 5 validation rules cho inference input.

## Tu Kiem Tra

1. Vi sao khong fit scaler/encoder tren toan bo dataset truoc split?
2. Khi nao one-hot encoding gay van de memory/latency?
3. Target encoding leakage nhu the nao?
4. Vi sao datetime raw khong nen dua truc tiep vao model?
5. Feature engineering khac business rule engineering the nao?

## Checklist

- [ ] Hieu numerical/categorical/text/datetime feature.
- [ ] Chay duoc `ColumnTransformer + Pipeline`.
- [ ] Xu ly missing value theo tung loai feature.
- [ ] Biet it nhat 3 dang data leakage trong feature engineering.
- [ ] Co baseline model voi classification report va ROC-AUC.
- [ ] Ghi lai trade-off one-hot/label/target encoding.

## Tai Lieu Tham Khao

- scikit-learn: `Pipeline`, `ColumnTransformer`, `preprocessing`, `TfidfVectorizer`.
- Kaggle Learn: Feature Engineering.
- Chip Huyen: Designing Machine Learning Systems.
- Feast documentation ve Feature Store.

---

# Day 6: Model Evaluation Metrics

## Muc Tieu

- Khong bi bay boi accuracy trong dataset mat can bang.
- Chon metric dung voi business objective.
- Hieu precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix.
- Biet regression metrics: MAE, MSE, RMSE, MAPE.
- Nam ranking metrics: MRR, NDCG, Recall@k de chuan bi cho RAG.
- Map ML metrics sang SLA, business KPI, cost va risk.

## TL;DR

Evaluation metric la test suite cua ML system, nhung do dung/sai theo xac suat va nhieu goc nhin. Accuracy chi huu ich khi class balance va cost loi gan nhau. Trong production, metric tot phai noi duoc voi business cost: false positive ton bao nhieu, false negative nguy hiem the nao, latency va throughput co chap nhan duoc khong.

## 1. Accuracy Khong Du

```text
accuracy = so du doan dung / tong so du doan
```

Fraud rate 1%, model luon predict "not fraud" dat 99% accuracy nhung bat duoc 0 fraud.

Metric aggregate co the dep nhung che endpoint/segment quan trong fail, giong service uptime cao nhung payment endpoint hong.

## 2. Confusion Matrix

| | Predicted Positive | Predicted Negative |
|---|---:|---:|
| Actual Positive | True Positive | False Negative |
| Actual Negative | False Positive | True Negative |

Fraud:

- TP: fraud bi chan.
- FP: giao dich hop le bi chan.
- FN: fraud lot qua.
- TN: giao dich hop le qua.

Khong co metric dung nhat neu chua biet cost FP/FN.

## 3. Precision, Recall, F1

Precision:

```text
precision = TP / (TP + FP)
```

Trong cac case model bao positive, bao nhieu case dung. Uu tien precision khi action positive gay phien/toan kem: auto-ban, block payment, manual review capacity thap.

Recall:

```text
recall = TP / (TP + FN)
```

Trong positive thuc te, model bat duoc bao nhieu. Uu tien recall khi bo sot nguy hiem: fraud, medical triage, security alert, PII leak.

F1:

```text
F1 = 2 * precision * recall / (precision + recall)
```

Tot khi can summary can bang, nhung khong phan anh cost lech manh.

## 4. ROC-AUC Va PR-AUC

ROC-AUC do ranking quality tong quat, threshold-independent. Co the qua lac quan voi imbalanced dataset.

PR-AUC tap trung positive class. Huu ich hon khi positive hiem:

- Fraud.
- Churn rate thap.
- Rare disease.
- Anomaly.
- Spam/phishing.

Rule:

- Dataset can bang: ROC-AUC on.
- Positive hiem: xem PR-AUC truoc.
- Chon threshold production: xem precision/recall tai threshold cu the.

## 5. Threshold Tuning

Model tra probability:

```text
p(churn) = 0.73
```

Default threshold `0.5` hiem khi toi uu. Threshold la business decision, giong rate limit/circuit breaker/alert threshold.

Tune theo:

- Max F1.
- Recall >= target, precision cao nhat co the.
- Precision >= target, recall cao nhat co the.
- Expected profit/cost.
- Capacity cua team van hanh.

## 6. Regression Metrics

| Metric | Y nghia | Khi dung |
|---|---|---|
| MAE | Sai so tuyet doi trung binh | De explain, it nhay outlier |
| MSE/RMSE | Phat loi lon manh hon | Loi lon rat nguy hiem |
| MAPE | Sai so phan tram | Can can trong khi y gan 0 |

## 7. Ranking Metrics

Recall@k: top-k co item dung khong. RAG can Recall@k vi neu retrieval khong lay dung context, LLM kho tra loi dung.

MRR: item dung xuat hien o rank nao:

```text
rank 1 -> 1
rank 2 -> 1/2
rank 5 -> 1/5
not found -> 0
```

NDCG: ranking khi co nhieu muc relevance, dung cho search/recommendation/RAG.

## 8. Business Metric vs ML Metric

Churn:

| ML metric | Business metric |
|---|---|
| ROC-AUC | Retention uplift |
| Precision | Offer gui dung user risk |
| Recall | Ty le churn-risk duoc phat hien |
| Calibration | Expected ROI campaign |

Fraud:

| ML metric | Business metric |
|---|---|
| Recall | Fraud amount prevented |
| Precision | Manual review efficiency |
| FPR | Legit transaction blocked |
| Latency p95 | Checkout UX |
| Alert volume | Analyst workload |

## Trade-offs

| Metric/Decision | Toi uu | Danh doi | Guidance |
|---|---|---|---|
| Accuracy | Dung tong the | Che class hiem | Chi dung khi class/cost can bang |
| Precision | It FP | Bo sot positive | Dung khi action ton kem/gay hai |
| Recall | It FN | Nhieu FP | Dung khi bo sot nguy hiem |
| F1 | Can bang P/R | Khong phan anh cost lech | Summary baseline |
| ROC-AUC | Ranking tong quat | Lac quan voi imbalance | So model, khong chot threshold |
| PR-AUC | Positive hiem | Kho explain hon | Fraud/churn/anomaly |
| Threshold thap | Recall cao | FP/ops cao | Co human review/risk bo sot cao |
| Threshold cao | Precision cao | FN cao | Action tu dong impact lon |

## Best Practices Tu Industry

1. Bat dau bang confusion matrix va class distribution.
2. Bao cao metric theo segment.
3. Chon threshold theo cost hoac capacity.
4. Theo doi offline va online metric rieng.
5. Luu evaluation dataset co dinh nhu regression test.

## Performance Considerations

Evaluation can do runtime:

- Prediction latency p50/p95/p99.
- Throughput.
- Batch scoring time.
- Memory footprint.
- Feature generation latency.
- Cost per 1,000 predictions.

Fraud realtime target vi du:

```text
Feature fetch p95: < 50ms
Model inference p95: < 20ms
End-to-end decision p95: < 100ms
Alert volume: <= analyst capacity
```

## Production Concerns

- Test set bi tune nhieu lan mat gia tri.
- Label delay: fraud/churn label co the tre.
- Feedback bias: chi case bi flag moi duoc review.
- Segment fairness.
- Alert fatigue.
- Calibration.
- Drift theo thoi gian.

## Hands-on Trong 60-90 Phut

```bash
pip install numpy pandas scikit-learn
```

```python
import numpy as np
import pandas as pd

from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

X, y = make_classification(
    n_samples=50000,
    n_features=20,
    n_informative=8,
    n_redundant=4,
    weights=[0.985, 0.015],
    class_sep=1.2,
    random_state=42,
)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

model = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
])
model.fit(X_train, y_train)
y_prob = model.predict_proba(X_test)[:, 1]

print("Positive rate:", round(y_test.mean(), 4))
print("ROC-AUC:", round(roc_auc_score(y_test, y_prob), 4))
print("PR-AUC:", round(average_precision_score(y_test, y_prob), 4))


def evaluate_at_threshold(threshold):
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "alerts": tp + fp,
    }


results = pd.DataFrame([evaluate_at_threshold(t) for t in [0.1, 0.2, 0.3, 0.5, 0.7, 0.9]])

def business_cost(row):
    return row["fn"] * 500 + row["fp"] * 5 + row["tp"] * 5

results["estimated_cost"] = results.apply(business_cost, axis=1)
print(results.to_string(index=False))
print("Best threshold by cost:")
print(results.sort_values("estimated_cost").iloc[0])
```

Bai tap:

- Doi fraud cost tu 500 sang 5000.
- Gia su team chi xu ly 300 alerts/ngay, chon threshold nao?
- So sanh best F1 threshold vs best cost threshold.
- Viet giai thich vi sao accuracy cao khong du.

## Tu Kiem Tra

1. Vi sao predict toan negative van accuracy cao?
2. Precision va recall khac nhau the nao trong fraud?
3. Khi nao PR-AUC huu ich hon ROC-AUC?
4. Vi sao threshold 0.5 khong nen mac dinh production?
5. Trong RAG, vi sao Recall@k quan trong?

## Checklist

- [ ] Giai thich confusion matrix bang ngon ngu business.
- [ ] Phan biet accuracy, precision, recall, F1.
- [ ] Biet khi nao dung ROC-AUC/PR-AUC.
- [ ] Chay threshold tuning tren imbalanced dataset.
- [ ] Chon threshold theo business cost/capacity.
- [ ] Hieu MAE/RMSE/MAPE va Recall@k/MRR/NDCG.

## Tai Lieu Tham Khao

- scikit-learn Metrics and scoring.
- Google Machine Learning Crash Course: Classification metrics.
- Evidently AI: ML monitoring and drift.
- Keywords: `MRR`, `NDCG`, `Recall@k`, `faithfulness`.

---

# Day 7: Error Analysis, Data Leakage, Threshold Tuning

## Muc Tieu

- Phan tich model sai o dau thay vi chi nhin metric tong.
- Phat hien data leakage, train-serving skew, distribution shift.
- Tune threshold theo business objective, khong mac dinh `0.5`.
- Tao regression test de tranh model moi te hon model cu.
- Map error analysis ve observability, debugging, rollout, incident review.

## TL;DR

Model classification khong chi can score cao, ma can sai theo cach business chap nhan duoc. Error analysis giong debugging production: slice theo segment, xem FP/FN, tim pattern loi va do impact. Threshold tuning la buoc bien probability thanh decision, tuong tu config policy layer. Data leakage la bug nghiem trong: offline metric dep gia nhung deploy hong.

## 1. Error Analysis Nhu Debug Production

Khong chi nhin F1 tong. Can hoi:

- Sai nhieu o nhom customer nao?
- Sai o plan monthly hay yearly?
- Sai o tenure thap hay cao?
- FP va FN co business cost khac nhau the nao?

Churn:

- FP: gui uu dai cho khach khong dinh roi di, ton budget.
- FN: bo lo khach sap roi di, mat doanh thu.

Neu false negative mat 1,200 USD lifetime revenue con false positive chi ton 50 USD offer, recall co the quan trong hon precision.

## 2. Error Slicing

Slice theo:

- `Contract`: Month-to-month, One year, Two year.
- `tenure_bucket`: 0-6, 7-12, 13-24, 25+ thang.
- `InternetService`.
- `PaymentMethod`.
- `MonthlyCharges` bucket.

Metric tong co the che:

```text
Overall F1: 0.78
F1 by Contract:
- Month-to-month: 0.72
- One year: 0.61
- Two year: 0.35
```

## 3. Top False Positives / False Negatives

Luon tao bang:

- Top 20 FP co probability cao nhat.
- Top 20 FN co probability thap nhat hoac gan threshold.
- Sample gan threshold, vi du 0.45-0.55.

Sample gan threshold co the can human review hoac rule bo sung.

## 4. Threshold Tuning

Default `0.5` chi hop ly khi:

- Class can bang.
- FP/FN cost gan nhau.
- Probability calibrated.
- Khong co capacity constraint.

Tune theo:

- Maximize F1.
- Recall >= 0.80 va precision cao nhat.
- Precision >= 0.70 va recall cao nhat.
- Maximize expected profit.
- So case gui CSKH moi ngay.

Threshold la runtime policy config, nen can versioning, audit va rollback.

## 5. Calibration

Model bao `0.8` khong dam bao 100 case nhu vay co 80 positive. Can calibration khi probability dung cho expected value/risk score.

Ky thuat:

- Platt scaling.
- Isotonic regression.
- Reliability diagram.

## 6. Data Leakage

Leakage xay ra khi training thay thong tin production inference khong co tai thoi diem du doan.

Vi du:

- `customer_cancelled_at` de predict churn.
- `last_support_ticket_reason = cancellation_request`.
- Billing sau ngay churn.
- Fit scaler/encoder tren toan bo dataset truoc split.

| Leakage type | Vi du | Cach tranh |
|---|---|---|
| Target leakage | Feature chua label | Review timeline business |
| Temporal leakage | Dung future data | Time split, point-in-time join |
| Preprocessing leakage | Fit scaler truoc split | Pipeline, fit tren train |
| Duplicate leakage | Cung user ca train/test | Split theo entity/group |
| Aggregation leakage | Aggregate gom future | Feature store point-in-time |
| Human-process leakage | Feature tao sau khi biet outcome | Xac dinh availability time |

## 7. Train-serving Skew Va Distribution Shift

Train-serving skew:

- Training fill missing bang median, production fill bang 0.
- Training category `Fiber optic`, production `fiber_optic`.
- Timezone khac nhau.

Giam skew bang shared preprocessing code, serialized pipeline, contract test, feature distribution logging.

Distribution shift:

- Marketing campaign moi.
- Gia thay doi.
- Seasonality.
- Competitor launch.
- Schema pipeline thay doi.

Monitor feature distribution, prediction distribution, positive rate, segment performance va delayed labels.

## Trade-offs

| Quyet dinh | Khi chon | Trade-off |
|---|---|---|
| Threshold thap | Muon bat nhieu positive | Recall tang, precision giam, nhieu alert |
| Threshold cao | FP gay hai/manual review dat | Precision tang, bo sot positive |
| Optimize F1 | FP/FN gan ngang | Khong phan anh cost lech |
| Optimize PR-AUC | Positive hiem | Kho explain hon confusion matrix |
| Calibration | Probability dung cho risk/cost | Them step training, can validation data |
| Error slicing sau | Can tim loi theo segment | Segment nho de nhieu |
| Time-based split | Bai toan co timeline | Score thap hon random split nhung thuc te hon |

## Best Practices Tu Industry

1. Giu baseline don gian.
2. Error analysis truoc khi doi model.
3. Version threshold cung model.
4. Dung Pipeline de tranh preprocessing leakage.
5. Monitor prediction distribution sau deploy.

## Performance Considerations

- Threshold tuning gan nhu mien phi.
- Error slicing voi data lon nen dung SQL/Spark thay Pandas.
- Calibration latency nhe neu la post-processing.
- Logging full feature vector ton storage va risk PII; nen sample/hash/aggregate.

## Production Concerns

- Khong log raw PII khong can thiet.
- Audit trail: model version, threshold version, feature version, prediction time.
- Rollback threshold nhanh neu positive rate bat thuong.
- Schema validation cho inference input.
- Delayed-label evaluation khi label that xuat hien sau vai ngay/tuan.

## Hands-on Trong 60-90 Phut

```bash
pip install pandas numpy scikit-learn joblib
```

```python
import numpy as np
import pandas as pd
import joblib

from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score
from sklearn.calibration import CalibratedClassifierCV

RANDOM_STATE = 42


def build_dataset(n_samples=8000):
    X, y = make_classification(
        n_samples=n_samples,
        n_features=5,
        n_informative=4,
        n_redundant=1,
        weights=[0.78, 0.22],
        class_sep=0.9,
        random_state=RANDOM_STATE,
    )
    df = pd.DataFrame(X, columns=[
        "tenure_score", "monthly_charge_score", "support_ticket_score",
        "usage_drop_score", "payment_risk_score",
    ])
    rng = np.random.default_rng(RANDOM_STATE)
    df["contract"] = rng.choice(["month_to_month", "one_year", "two_year"], size=n_samples, p=[0.55, 0.25, 0.20])
    df["internet_service"] = rng.choice(["dsl", "fiber", "none"], size=n_samples, p=[0.35, 0.50, 0.15])
    df["churn"] = y
    df["customer_id"] = [f"CUST_{i:06d}" for i in range(n_samples)]
    return df


def evaluate_threshold(y_true, proba, threshold):
    y_pred = (proba >= threshold).astype(int)
    return {
        "threshold": threshold,
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "predicted_positive_rate": y_pred.mean(),
        "tn_fp_fn_tp": confusion_matrix(y_true, y_pred).ravel().tolist(),
    }


def slice_metrics(df_result, segment_col, threshold):
    rows = []
    for segment_value, group in df_result.groupby(segment_col):
        if len(group) < 50:
            continue
        y_true = group["y_true"].to_numpy()
        y_pred = (group["proba"] >= threshold).astype(int)
        rows.append({
            "segment": segment_value,
            "count": len(group),
            "positive_rate": y_true.mean(),
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
            "predicted_positive_rate": y_pred.mean(),
        })
    return pd.DataFrame(rows).sort_values("f1")


df = build_dataset()
target = "churn"
numeric_cols = ["tenure_score", "monthly_charge_score", "support_ticket_score", "usage_drop_score", "payment_risk_score"]
categorical_cols = ["contract", "internet_service"]

train_df, test_df = train_test_split(df, test_size=0.25, stratify=df[target], random_state=RANDOM_STATE)

preprocess = ColumnTransformer([
    ("num", StandardScaler(), numeric_cols),
    ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
])

pipeline = Pipeline([
    ("preprocess", preprocess),
    ("model", LogisticRegression(max_iter=1000, class_weight="balanced")),
])

calibrated_model = CalibratedClassifierCV(estimator=pipeline, method="isotonic", cv=3)
calibrated_model.fit(train_df[numeric_cols + categorical_cols], train_df[target])

X_test = test_df[numeric_cols + categorical_cols]
y_test = test_df[target]
proba = calibrated_model.predict_proba(X_test)[:, 1]

print("ROC-AUC:", round(roc_auc_score(y_test, proba), 4))
print("PR-AUC:", round(average_precision_score(y_test, proba), 4))

threshold_report = pd.DataFrame([evaluate_threshold(y_test, proba, t) for t in np.arange(0.30, 0.85, 0.05)])
print(threshold_report[["threshold", "precision", "recall", "f1", "predicted_positive_rate"]])

candidates = threshold_report[threshold_report["recall"] >= 0.75]
best = candidates.sort_values(["precision", "f1"], ascending=False).iloc[0]
chosen_threshold = float(best["threshold"])

result = test_df[["customer_id", "contract", "internet_service"]].copy()
result["y_true"] = y_test.to_numpy()
result["proba"] = proba
result["y_pred"] = (result["proba"] >= chosen_threshold).astype(int)

print(slice_metrics(result, "contract", chosen_threshold))
print("Top false positives:")
print(result[(result["y_true"] == 0) & (result["y_pred"] == 1)].sort_values("proba", ascending=False).head(20))
print("Top false negatives:")
print(result[(result["y_true"] == 1) & (result["y_pred"] == 0)].sort_values("proba").head(20))

joblib.dump({
    "model": calibrated_model,
    "threshold": chosen_threshold,
    "numeric_cols": numeric_cols,
    "categorical_cols": categorical_cols,
}, "churn_model_day7.joblib")
```

Bai tap:

- Thay Logistic Regression bang Random Forest.
- Them expected profit: `TP * retained_value - FP * offer_cost - FN * lost_value`.
- Slice theo `internet_service`.
- Gia lap leakage bang feature `leaky_cancel_signal = churn` va xem metric.
- Viet `predict_customer_churn(input_json)` load artifact va tra `{probability, decision, threshold}`.

## Tu Kiem Tra

1. Accuracy cao van co the la model te khi nao?
2. Khi nao nen threshold thap hon 0.5?
3. Data leakage khac train-serving skew the nao?
4. Vi sao time-based split thuc te hon random split?
5. Neu positive rate production tang tu 10% len 40%, debug gi?

## Checklist

- [ ] Hieu confusion matrix va cost FP/FN.
- [ ] Tune threshold 0.3 den 0.8.
- [ ] Tao top FP/FN.
- [ ] Slice metric theo it nhat 2 segment.
- [ ] Nhan dien it nhat 5 dang leakage.
- [ ] Save artifact kem threshold.
- [ ] Ghi threshold decision bang business reasoning.

## Tai Lieu Tham Khao

- scikit-learn: `classification metrics`, `CalibratedClassifierCV`, `Pipeline`.
- Evidently AI: data drift and monitoring.
- Hidden Technical Debt in Machine Learning Systems.

---

# Day 8: Mini-project - Customer Churn ML Pipeline

## Muc Tieu

- Build ML pipeline end-to-end cho customer churn theo huong production-style.
- Co EDA, feature engineering, train it nhat 3 models, evaluation, error analysis.
- Save model artifact va viet inference function.
- Giai thich trade-off giua quality, latency, explainability, operational complexity.
- Tao nen tang portfolio cho Phase 1.

## TL;DR

Day 8 la mini-project tong hop Phase 1. Muc tieu khong phai score cao nhat, ma la quy trinh dung: split hop ly, tranh leakage, preprocessing reproducible, metric phu hop, threshold co reasoning va artifact co the deploy. Day la buoc chuyen tu notebook ML sang backend/production mindset.

## 1. Problem Framing

Churn prediction:

```text
Dua tren thong tin hien tai cua customer, du doan xac suat customer roi bo dich vu trong tuong lai gan.
```

Output production khong nen chi la class:

```json
{
  "customer_id": "123",
  "churn_probability": 0.73,
  "risk_tier": "high",
  "decision": "send_retention_offer",
  "model_version": "churn-v1",
  "threshold": 0.45
}
```

Cau hoi business can chot:

- Predict churn trong horizon nao: 30 ngay, 60 ngay, end of contract?
- Churn label tao the nao?
- Action sau prediction la gi?
- Capacity moi ngay bao nhieu?
- Cost FP/FN la gi?

## 2. Dataset Va Schema

Dataset goi y: Telco Customer Churn.

Cot thuong gap:

- `customerID`
- `gender`
- `SeniorCitizen`
- `Partner`
- `Dependents`
- `tenure`
- `PhoneService`
- `InternetService`
- `Contract`
- `PaperlessBilling`
- `PaymentMethod`
- `MonthlyCharges`
- `TotalCharges`
- `Churn`

Data quality issues:

- `TotalCharges` co the la string/blank.
- Categorical values co whitespace.
- Class imbalance.
- Feature nhu `tenure`, `Contract`, `MonthlyCharges` correlation manh voi churn.
- Khong phai feature nao cung available tai prediction time trong system that.

## 3. Pipeline Architecture

```text
Raw CSV
  -> schema validation nhe
  -> train/test split
  -> preprocessing
      -> numeric imputation + scaling
      -> categorical imputation + one-hot
  -> train models
      -> Logistic Regression
      -> Random Forest
      -> Gradient Boosting
  -> evaluation
      -> ROC-AUC, PR-AUC, precision, recall, F1
      -> threshold tuning
      -> error slicing
  -> save artifact
      -> model
      -> threshold
      -> feature columns
      -> metrics
  -> inference function
```

## 4. Model Choices

| Model | Manh | Yeu |
|---|---|---|
| Logistic Regression | Baseline nhanh, explainable, latency thap | Kho hoc nonlinear/interaction |
| Random Forest | Bat nonlinear, robust outlier | Artifact/latency lon hon, probability can calibration |
| Gradient Boosting | Manh cho tabular | Can tuning, de overfit neu dataset nho |

Guidance:

- Bat buoc co Logistic Regression baseline.
- Random Forest/Gradient Boosting la candidate chinh.
- Chon threshold theo business objective.
- Neu model phuc tap chi hon baseline it, uu tien baseline cho v1 production.

## Trade-offs

| Lua chon | Khi nen dung | Khong nen dung khi | Production note |
|---|---|---|---|
| Logistic Regression | Baseline, explainability, latency thap | Pattern nonlinear manh | Tot cho v1 |
| Random Forest | Dataset vua, quality hon baseline | p99 latency rat chat | Benchmark artifact/latency |
| Gradient Boosting | Tabular quality cao | Chua co tuning discipline | Ung vien tot cho production |
| One-hot | Cardinality thap-vua | Cardinality rat cao | Feature space phinh |
| Class weight balanced | Class imbalance, can recall | Precision uu tien tuyet doi | Tune threshold lai |
| ROC-AUC | Ranking tong quat | Positive hiem | PR-AUC huu ich hon |
| Expected profit | Co cost FP/FN | Business cost chua ro | Tot nhat neu estimate duoc |
| Notebook-only | Kham pha nhanh | Can deploy/reproduce | Chuyen sang script/package |

## Best Practices Tu Industry

1. Baseline-first.
2. Reproducibility: set `random_state`, luu package version, metrics report.
3. Pipeline hoa preprocessing.
4. Mini model card trong README: dataset, target, metric, threshold, limitation, intended use.
5. Error analysis la deliverable, khong optional.

## Performance Considerations

- Logistic Regression thuong sub-millisecond/record tren CPU.
- Tree ensemble vai ms den chuc ms tuy so cay/depth.
- Batch daily scoring co the don gian va re hon API realtime cho churn.
- Model artifact nen load nhanh; artifact lon can warmup/readiness.
- Do p50/p95/p99 neu synchronous API.

## Production Concerns

- Customer data co PII: masking/logging policy.
- Feature freshness.
- Schema drift: `handle_unknown="ignore"`.
- Model/threshold/training date/dataset snapshot versioning.
- Rollback artifact cu.
- Monitor prediction distribution, positive rate, null rate, latency.
- Fairness/segment bias.
- Human override cho retention action.

## Hands-on Trong 60-90 Phut

Script mau duoi day co synthetic fallback neu chua co Telco CSV.

```bash
pip install pandas numpy scikit-learn joblib
```

```python
from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.datasets import make_classification
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42
ARTIFACT_PATH = Path("customer_churn_pipeline.joblib")


def load_or_create_data(csv_path: str | None = None) -> pd.DataFrame:
    if csv_path and Path(csv_path).exists():
        df = pd.read_csv(csv_path)
        df = df.copy()
        df.columns = [c.strip() for c in df.columns]
        if "TotalCharges" in df.columns:
            df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
        if "Churn" in df.columns:
            df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0}).astype(int)
        return df

    X, y = make_classification(
        n_samples=10000,
        n_features=6,
        n_informative=5,
        n_redundant=1,
        weights=[0.75, 0.25],
        class_sep=0.8,
        random_state=RANDOM_STATE,
    )
    df = pd.DataFrame(X, columns=["tenure", "MonthlyCharges", "TotalCharges", "support_tickets", "usage_drop", "payment_delay"])
    rng = np.random.default_rng(RANDOM_STATE)
    df["customerID"] = [f"CUST_{i:06d}" for i in range(len(df))]
    df["Contract"] = rng.choice(["Month-to-month", "One year", "Two year"], len(df), p=[0.55, 0.25, 0.20])
    df["InternetService"] = rng.choice(["DSL", "Fiber optic", "No"], len(df), p=[0.35, 0.50, 0.15])
    df["PaymentMethod"] = rng.choice(["Electronic check", "Mailed check", "Bank transfer", "Credit card"], len(df), p=[0.45, 0.15, 0.20, 0.20])
    df["PaperlessBilling"] = rng.choice(["Yes", "No"], len(df), p=[0.6, 0.4])
    df["Churn"] = y
    return df


def infer_columns(df: pd.DataFrame):
    target_col = "Churn"
    id_col = "customerID" if "customerID" in df.columns else None
    ignored = {target_col}
    if id_col:
        ignored.add(id_col)
    feature_cols = [c for c in df.columns if c not in ignored]
    numeric_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in feature_cols if c not in numeric_cols]
    return target_col, id_col, numeric_cols, categorical_cols


def build_preprocessor(numeric_cols, categorical_cols):
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("num", numeric_pipeline, numeric_cols),
        ("cat", categorical_pipeline, categorical_cols),
    ])


def build_models(numeric_cols, categorical_cols):
    return {
        "logistic_regression": Pipeline([
            ("preprocess", build_preprocessor(numeric_cols, categorical_cols)),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]),
        "random_forest": Pipeline([
            ("preprocess", build_preprocessor(numeric_cols, categorical_cols)),
            ("model", RandomForestClassifier(
                n_estimators=250,
                max_depth=8,
                min_samples_leaf=20,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )),
        ]),
        "gradient_boosting": Pipeline([
            ("preprocess", build_preprocessor(numeric_cols, categorical_cols)),
            ("model", GradientBoostingClassifier(
                n_estimators=160,
                learning_rate=0.05,
                max_depth=3,
                random_state=RANDOM_STATE,
            )),
        ]),
    }


def threshold_metrics(y_true, proba, threshold):
    y_pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "threshold": round(float(threshold), 3),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "predicted_positive_rate": float(y_pred.mean()),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
    }


def evaluate_model(name, model, X_test, y_test):
    start = time.perf_counter()
    proba = model.predict_proba(X_test)[:, 1]
    latency_ms_for_test_batch = (time.perf_counter() - start) * 1000
    threshold_df = pd.DataFrame([threshold_metrics(y_test, proba, t) for t in np.arange(0.25, 0.81, 0.05)])

    candidates = threshold_df[threshold_df["recall"] >= 0.75]
    if len(candidates) == 0:
        best_row = threshold_df.sort_values("f1", ascending=False).iloc[0]
    else:
        best_row = candidates.sort_values(["precision", "f1"], ascending=False).iloc[0]

    return {
        "model_name": name,
        "roc_auc": roc_auc_score(y_test, proba),
        "pr_auc": average_precision_score(y_test, proba),
        "chosen_threshold": float(best_row["threshold"]),
        "chosen_precision": float(best_row["precision"]),
        "chosen_recall": float(best_row["recall"]),
        "chosen_f1": float(best_row["f1"]),
        "latency_ms_for_test_batch": latency_ms_for_test_batch,
        "threshold_report": threshold_df,
        "proba": proba,
    }


def error_analysis(df_test, y_test, proba, threshold, slice_cols):
    result = df_test.copy()
    result["y_true"] = y_test.to_numpy()
    result["proba"] = proba
    result["y_pred"] = (result["proba"] >= threshold).astype(int)
    fp = result[(result["y_true"] == 0) & (result["y_pred"] == 1)].sort_values("proba", ascending=False)
    fn = result[(result["y_true"] == 1) & (result["y_pred"] == 0)].sort_values("proba")

    print("Top false positives:")
    print(fp.head(20))
    print("Top false negatives:")
    print(fn.head(20))

    for col in slice_cols:
        rows = []
        for value, group in result.groupby(col):
            if len(group) < 30:
                continue
            rows.append({
                "segment": str(value),
                "count": len(group),
                "actual_positive_rate": float(group["y_true"].mean()),
                "predicted_positive_rate": float(group["y_pred"].mean()),
                "precision": precision_score(group["y_true"], group["y_pred"], zero_division=0),
                "recall": recall_score(group["y_true"], group["y_pred"], zero_division=0),
                "f1": f1_score(group["y_true"], group["y_pred"], zero_division=0),
            })
        if rows:
            print(f"Slice report by {col}:")
            print(pd.DataFrame(rows).sort_values("f1"))


def train_pipeline(csv_path: str | None = None):
    df = load_or_create_data(csv_path)
    target_col, id_col, numeric_cols, categorical_cols = infer_columns(df)
    X = df[numeric_cols + categorical_cols]
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, stratify=y, random_state=RANDOM_STATE)

    evaluations = []
    trained_models = {}
    for name, model in build_models(numeric_cols, categorical_cols).items():
        print(f"Training {name}...")
        model.fit(X_train, y_train)
        trained_models[name] = model
        eval_result = evaluate_model(name, model, X_test, y_test)
        evaluations.append(eval_result)
        print(json.dumps({
            "model_name": eval_result["model_name"],
            "roc_auc": round(eval_result["roc_auc"], 4),
            "pr_auc": round(eval_result["pr_auc"], 4),
            "chosen_threshold": eval_result["chosen_threshold"],
            "precision": round(eval_result["chosen_precision"], 4),
            "recall": round(eval_result["chosen_recall"], 4),
            "f1": round(eval_result["chosen_f1"], 4),
        }, indent=2))

    leaderboard = pd.DataFrame([{
        "model_name": e["model_name"],
        "roc_auc": e["roc_auc"],
        "pr_auc": e["pr_auc"],
        "threshold": e["chosen_threshold"],
        "precision": e["chosen_precision"],
        "recall": e["chosen_recall"],
        "f1": e["chosen_f1"],
    } for e in evaluations]).sort_values(["pr_auc", "f1"], ascending=False)

    print("Leaderboard:")
    print(leaderboard)

    best_name = leaderboard.iloc[0]["model_name"]
    best_eval = next(e for e in evaluations if e["model_name"] == best_name)
    best_model = trained_models[best_name]

    slice_cols = [c for c in ["Contract", "InternetService", "PaymentMethod"] if c in X_test.columns]
    error_analysis(X_test, y_test, best_eval["proba"], best_eval["chosen_threshold"], slice_cols)

    artifact = {
        "model": best_model,
        "model_name": best_name,
        "threshold": best_eval["chosen_threshold"],
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "target_col": target_col,
        "id_col": id_col,
        "metrics": leaderboard.to_dict(orient="records"),
        "training_note": "Demo churn model. Validate on real time-based split before production.",
    }
    joblib.dump(artifact, ARTIFACT_PATH)
    print(f"Saved artifact: {ARTIFACT_PATH}")


def predict_customer_churn(customer: dict, artifact_path: Path = ARTIFACT_PATH) -> dict:
    artifact = joblib.load(artifact_path)
    model = artifact["model"]
    threshold = artifact["threshold"]
    feature_cols = artifact["numeric_cols"] + artifact["categorical_cols"]
    input_df = pd.DataFrame([customer])[feature_cols]
    proba = float(model.predict_proba(input_df)[:, 1][0])
    return {
        "churn_probability": round(proba, 4),
        "threshold": threshold,
        "will_churn": bool(proba >= threshold),
        "risk_tier": "high" if proba >= 0.70 else "medium" if proba >= 0.40 else "low",
        "model_name": artifact["model_name"],
    }


if __name__ == "__main__":
    train_pipeline()
```

## README Outline

```markdown
# Customer Churn ML Pipeline

## Problem
Predict customer churn probability for retention prioritization.

## Dataset
Telco Customer Churn or synthetic fallback dataset.

## Approach
- EDA
- Preprocessing with sklearn Pipeline
- Models: Logistic Regression, Random Forest, Gradient Boosting
- Metrics: ROC-AUC, PR-AUC, precision, recall, F1
- Threshold tuning based on recall >= 0.75
- Error analysis by customer segments

## Production Notes
- Pipeline artifact includes preprocessing and model.
- Threshold is saved with model artifact.
- Unknown categorical values are handled safely.
- Need time-based validation before real production.
- Monitor prediction distribution, input null rate, segment-level performance.

## How to run
pip install pandas numpy scikit-learn joblib
python churn_pipeline.py
```

## Tu Kiem Tra

1. Vi sao khong fit scaler/encoder truoc train/test split?
2. Vi sao PR-AUC huu ich hon ROC-AUC khi churn class nho?
3. Khi nao chon Logistic Regression thay vi Gradient Boosting du score thap hon?
4. Model artifact production can luu gi ngoai model weights?
5. Neu inference API nhan category moi, pipeline nen xu ly the nao?

## Checklist

- [ ] Co script/notebook train pipeline end-to-end.
- [ ] Train va so sanh it nhat 3 models.
- [ ] Co ROC-AUC, PR-AUC, precision, recall, F1.
- [ ] Co threshold tuning va business reasoning.
- [ ] Co error analysis: FP, FN, slice metrics.
- [ ] Save artifact bang `joblib`.
- [ ] Co inference function tra probability, decision, threshold, risk tier.
- [ ] Co README outline ve trade-off va production concerns.

## Tai Lieu Tham Khao

- Kaggle: Telco Customer Churn dataset.
- scikit-learn: `Pipeline`, `ColumnTransformer`, `model evaluation`.
- Google ML Crash Course: Classification.
- Evidently AI: ML monitoring and data drift.
- Chip Huyen: Designing Machine Learning Systems.
- Hidden Technical Debt in Machine Learning Systems.

---

# Learning Log Template

Dung template nay sau moi ngay:

```markdown
# Day X: Topic

## Toi da hoc gi?

## Concept quan trong nhat?

## Trade-off can nho?

## Production concern?

## Code/project output hom nay?

## Cau hoi con chua ro?
```
