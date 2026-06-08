# Day 5 Document: Feature Engineering Decision Matrix

File này dùng như tài liệu tra nhanh khi chọn kỹ thuật feature engineering. Hãy đọc cùng [lession.md](./lession.md) và làm bài trong [exercise.md](./exercise.md).

## 1. Decision Matrix Theo Loại Feature

| Feature type | Default tốt để bắt đầu | Khi cần đổi | Production concern |
|---|---|---|---|
| Numerical sạch, ít outlier | Median imputation + `StandardScaler` | Có outlier lớn thì dùng `RobustScaler` | Monitor min/max, p95/p99, missing rate |
| Numerical skewed | `np.log1p` + scaler | Nếu value có âm thì cần transform khác | Log transform phải giống nhau ở train/inference |
| Count feature | Raw count + optional log/count bucket | Count quá lệch hoặc long-tail | Đảm bảo window tính count không dùng future event |
| Low-cardinality categorical | Constant imputation + one-hot | Category có thứ tự thật thì ordinal | Unknown category rate có thể báo upstream drift |
| High-cardinality categorical | Group infrequent + one-hot | Target encoding nếu có CV encoding chặt | Memory, latency, leakage |
| Text ngắn | TF-IDF word/char n-gram | Cần semantic thì dùng embedding/Transformer ở phase sau | PII, vocabulary version, latency |
| Datetime | Age/delta/cyclical/calendar features | Seasonality phức tạp thì thêm rolling feature | Point-in-time correctness |
| Missing value có nghĩa | Missing indicator hoặc `__missing__` | Missing là lỗi source thì fail fast | Phân biệt business missing và system missing |

## 2. Encoding Trade-off

| Encoding | Ưu điểm | Nhược điểm | Best context |
|---|---|---|---|
| One-hot | Dễ hiểu, ít giả định, hợp linear model | Nổ số chiều với cardinality cao | Category dưới vài trăm giá trị ổn định |
| Ordinal | Gọn, nhanh | Tạo thứ tự giả nếu dùng sai | Category có thứ tự thật |
| Hashing | Không cần vocabulary, xử lý category mới | Collision, khó debug | Streaming/high-cardinality khi memory hạn chế |
| Target encoding | Mạnh với high-cardinality | Rất dễ leakage | Có CV encoding, smoothing và kiểm thử nghiêm |
| Learned embedding | Mạnh khi data lớn | Cần deep learning pipeline | Recommender/NLP/large-scale categorical |

Best solution theo context Day 5: one-hot với `handle_unknown="ignore"` và grouping infrequent categories. Chỉ nâng cấp lên target encoding khi đã có leakage tests và cross-validation encoding đúng.

## 3. Scaling Trade-off

| Scaler | Nên dùng khi | Không nên dùng khi |
|---|---|---|
| `StandardScaler` | Linear/SVM/KNN/NN, data gần normal | Outlier cực lớn |
| `MinMaxScaler` | Cần range cố định, ví dụ một số NN setup | Data production có outlier không kiểm soát |
| `RobustScaler` | Revenue, usage, latency, transaction amount | Data sạch và muốn interpret z-score |
| No scaling | Tree-based model | Model phụ thuộc distance/gradient |

## 4. Leakage Checklist

Trước khi tin metrics, hãy hỏi:

- Feature này có tồn tại tại thời điểm prediction không?
- Aggregation window có điều kiện `event_time <= prediction_time` không?
- Split có được làm trước khi fit imputer/scaler/encoder/vectorizer không?
- Feature selection có dùng test set không?
- Duplicate customer/order/session có bị rơi cả train và test không?
- Text có chứa label trực tiếp như "cancelled", "refund completed", "retention approved" sau outcome không?
- Target encoding có được tính out-of-fold không?
- Mọi feature experiment có dùng validation thay vì nhìn test lặp lại không?
- Custom datetime/text transform có nằm trong artifact dùng chung giữa train và inference không?

## 5. Schema Contract Tối Thiểu

Mỗi feature nên có metadata:

| Field | Ý nghĩa |
|---|---|
| `name` | Tên ổn định của feature |
| `dtype` | Kiểu dữ liệu expected |
| `nullable` | Có cho phép null không |
| `allowed_values` | Domain cho categorical nếu biết |
| `range` | Min/max hợp lệ cho numerical |
| `source` | Bảng/API/event sinh ra feature |
| `availability_time` | Khi nào feature có thể biết |
| `owner` | Team chịu trách nhiệm |
| `version` | Version khi đổi semantics |

Ví dụ:

```yaml
monthly_charges:
  dtype: float
  nullable: true
  range: [0, 10000]
  source: billing.accounts
  availability_time: before_prediction
  owner: billing-platform
  version: 1
```

## 6. Monitoring Metrics

| Metric | Vì sao cần |
|---|---|
| Missing rate theo feature | Phát hiện upstream source lỗi |
| Unknown category rate | Phát hiện taxonomy/category drift |
| Numerical p50/p95/p99 | Phát hiện distribution shift/outlier |
| Text empty rate và average length | Phát hiện ingestion/tokenization lỗi |
| Preprocessing latency | Feature pipeline có thể là bottleneck |
| Prediction input rejection rate | Validation quá chặt hoặc upstream sai contract |
| Feature freshness | Aggregate feature stale làm model sai |

## 7. Khi Nào Nâng Cấp Feature Pipeline?

| Tín hiệu | Hành động |
|---|---|
| One-hot matrix quá lớn | Group infrequent, hashing, target encoding có kiểm soát |
| Rolling feature tính chậm | Precompute batch, cache, feature store |
| Text TF-IDF không đủ tốt | Thử char n-gram, tokenizer tốt hơn, embedding model |
| Offline tốt production kém | Kiểm tra leakage, train-serving skew, drift |
| Model khó giải thích | Giảm feature phức tạp, thêm feature lineage, dùng model explainability |

## 8. Context7 Docs Đã Dùng

- `/websites/scikit-learn_stable`: `Pipeline`, `ColumnTransformer`, `SimpleImputer`, `OneHotEncoder(handle_unknown="ignore")`, `TfidfVectorizer`, `SelectPercentile`.
- `/websites/pandas_pydata`: `pd.to_datetime`, nullable `Int64`, boolean indexing, missing data handling, as-of lookup/join patterns cho time-aware feature.
- `/websites/numpy_doc_2_4`: `ndarray`, broadcasting, `@` matrix multiplication và `*` element-wise multiplication.
- `merge_asof` cần sort theo time key; dùng `direction="backward"` và tolerance phù hợp để tránh future/stale match.
- Scalar column selector trong `ColumnTransformer` tạo 1D input phù hợp cho `TfidfVectorizer`.
