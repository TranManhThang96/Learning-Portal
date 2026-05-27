# Bài Tập — Ngày 17: Numpy & Pandas

## Bài 1 — Numpy: Sales Statistics (Cơ bản)

**Mô tả:**
Bạn có dữ liệu doanh thu 12 tháng của 3 sản phẩm dưới dạng Numpy array. Hãy thực hiện các phân tích cơ bản mà không dùng vòng lặp Python.

**Yêu cầu:**

```python
import numpy as np

# Dữ liệu: 3 sản phẩm × 12 tháng (đơn vị: triệu VND)
sales = np.array([
    [120, 135, 110, 145, 160, 175, 190, 185, 170, 155, 140, 200],  # Product A
    [ 80,  75,  90, 100,  95, 110, 105, 115, 120, 125, 130, 140],  # Product B
    [ 50,  55,  45,  60,  70,  65,  80,  75,  85,  90,  95, 100],  # Product C
])

# TODO: Hoàn thành các yêu cầu sau (KHÔNG dùng Python for loop):
```

1. Tính tổng doanh thu của từng sản phẩm theo năm (1 dòng code)
2. Tính doanh thu trung bình từng tháng (average across 3 products, 1 dòng)
3. Tìm tháng có doanh thu cao nhất của từng sản phẩm (dùng `argmax`)
4. Tính % tăng trưởng tháng sau so tháng trước cho Product A (dùng `np.diff`)
5. Normalize dữ liệu toàn bộ về range [0, 1] bằng min-max normalization (vectorized)
6. Tìm tất cả các ô (product, month) có doanh thu > 150 triệu

**Expected output:**
```
Tổng theo năm: [1885  1285   870]
Avg theo tháng: [83.33 88.33 81.67 101.67 108.33 116.67 125.  125.  125.  123.33 121.67 146.67]
Tháng đỉnh Product A: tháng 12 (index 11)
Tháng đỉnh Product B: tháng 12 (index 11)
Tháng đỉnh Product C: tháng 12 (index 11)
% tăng trưởng Product A: [12.5% -18.5% 31.8% ...]
Normalized min: 0.0, max: 1.0
Các ô > 150 triệu: [(0, 4), (0, 5), ...]
```

**Hint:**
- `array.sum(axis=1)` để sum theo hàng (từng product)
- `array.mean(axis=0)` để mean theo cột (từng tháng)
- `np.argmax(array, axis=1)` tìm vị trí max
- `np.diff(array) / array[:, :-1] * 100` cho % change
- `np.where(condition)` trả về indices thỏa điều kiện

---

## Bài 2 — Pandas: E-commerce Order Analysis (Trung bình)

**Mô tả:**
Bạn có dataset đơn hàng e-commerce. Hãy thực hiện phân tích để trả lời các câu hỏi business.

**Setup:**
```python
import pandas as pd
import numpy as np

np.random.seed(42)
n = 1000

orders = pd.DataFrame({
    'order_id':    range(1001, 1001 + n),
    'customer_id': np.random.randint(1, 201, n),  # 200 customers
    'product':     np.random.choice(['Laptop', 'Phone', 'Tablet', 'Watch', 'Earbuds'], n),
    'category':    np.random.choice(['Electronics', 'Accessories'], n, p=[0.6, 0.4]),
    'city':        np.random.choice(['HN', 'HCM', 'DN', 'HP'], n, p=[0.35, 0.40, 0.15, 0.10]),
    'quantity':    np.random.randint(1, 4, n),
    'unit_price':  np.random.choice([999, 599, 399, 299, 149], n),
    'discount':    np.random.choice([0, 0.05, 0.10, 0.15, 0.20], n, p=[0.5, 0.2, 0.15, 0.1, 0.05]),
    'order_date':  pd.date_range('2024-01-01', periods=n, freq='8H'),
    'status':      np.random.choice(['completed', 'pending', 'cancelled'], n, p=[0.75, 0.15, 0.10]),
})
orders['revenue'] = orders['quantity'] * orders['unit_price'] * (1 - orders['discount'])
```

**Yêu cầu:**

1. **Basic stats:** Tính tổng revenue, số orders, average order value cho toàn bộ dataset. Chỉ tính các orders có status = 'completed'.

2. **Top customers:** Tìm top 5 customer có tổng revenue cao nhất (chỉ completed orders). Output gồm: customer_id, total_revenue, order_count, avg_order_value.

3. **City analysis:** Tính revenue và market share (%) của từng thành phố. Sort descending by revenue.

4. **Monthly trend:** Tính tổng revenue và số orders theo từng tháng. Tính % tăng trưởng revenue MoM (month-over-month).

5. **Product performance:** Với mỗi sản phẩm, tính: total_revenue, avg_discount, total_quantity, cancellation_rate (%).

6. **Customer segmentation:** Phân loại customers thành 3 tier dựa trên tổng revenue của họ:
   - Tier 1 (VIP): Top 20% customers
   - Tier 2 (Regular): 20%-60%
   - Tier 3 (Occasional): Bottom 40%
   Đếm số customers mỗi tier.

**Expected output format:**
```
=== BASIC STATS (completed only) ===
Total Revenue: X,XXX,XXX
Order Count: XXX
Avg Order Value: X,XXX.XX

=== TOP 5 CUSTOMERS ===
   customer_id  total_revenue  order_count  avg_order_value
0          ...        ...           ...          ...

=== CITY MARKET SHARE ===
  city   revenue  market_share_%
0  HCM   ...         XX.X%
...

=== MONTHLY TREND ===
  month  revenue  orders  mom_growth_%
...

=== PRODUCT PERFORMANCE ===
  product  total_revenue  avg_discount  total_qty  cancel_rate_%
...

=== CUSTOMER SEGMENTS ===
Tier 1 (VIP): XX customers
Tier 2 (Regular): XX customers
Tier 3 (Occasional): XX customers
```

**Hint:**
- Dùng `df[df['status'] == 'completed']` để filter completed orders
- `groupby('customer_id').agg(...)` cho customer stats
- `dt.to_period('M')` để convert date thành tháng
- `pct_change()` cho MoM growth
- `pd.qcut()` hoặc `pd.cut()` với `quantiles` cho segmentation

---

## Bài 3 — Pandas + Numpy: Log Analysis Pipeline (Nâng cao / Challenge)

**Mô tả:**
Mô phỏng tình huống thực tế: bạn nhận được access logs từ một API server (NodeJS style), cần build pipeline phân tích performance và phát hiện anomalies.

**Setup:**
```python
import pandas as pd
import numpy as np

np.random.seed(123)
n = 5000

# Simulate API access logs
endpoints = ['/api/users', '/api/orders', '/api/products', '/api/auth/login', '/api/payments']
methods = ['GET', 'POST', 'PUT', 'DELETE']
status_codes = [200, 200, 200, 200, 201, 400, 401, 403, 404, 500]

logs = pd.DataFrame({
    'timestamp':    pd.date_range('2024-01-15 00:00:00', periods=n, freq='30s') +
                    pd.to_timedelta(np.random.randint(0, 30, n), unit='s'),
    'endpoint':     np.random.choice(endpoints, n, p=[0.3, 0.25, 0.2, 0.15, 0.1]),
    'method':       np.random.choice(methods, n, p=[0.6, 0.2, 0.15, 0.05]),
    'status_code':  np.random.choice(status_codes, n),
    'response_time_ms': np.concatenate([
        np.random.normal(120, 30, int(n * 0.95)).clip(10, 500),   # Normal requests
        np.random.normal(2000, 500, int(n * 0.05)).clip(800, 5000) # Slow requests (anomalies)
    ])[:n],
    'user_id':      np.random.randint(1, 501, n),
    'ip':           [f"192.168.{np.random.randint(1,5)}.{np.random.randint(1,255)}" for _ in range(n)],
    'bytes_sent':   np.random.randint(100, 50000, n),
})
```

**Yêu cầu:**

1. **Data quality check:**
   - Kiểm tra null values, duplicates, data types
   - Report % success rate (2xx), client errors (4xx), server errors (5xx)
   - Tính p50, p95, p99 response time (percentiles)

2. **Endpoint performance dashboard:**
   Với mỗi endpoint, tính:
   - Total requests, success rate, avg/p95 response time, avg bytes
   - Flag endpoint nào có p95 > 500ms là "SLOW"

3. **Anomaly detection — Slow requests:**
   - Định nghĩa "slow request": response_time > mean + 2*std (Z-score > 2)
   - Tìm top 3 endpoints có tỷ lệ slow requests cao nhất
   - Với slow requests, kiểm tra xem có pattern theo giờ không (group by hour)

4. **Suspicious IP detection:**
   - Tìm các IP có > 100 requests trong dataset
   - Trong các IP đó, flag IP nào có error rate > 30% là "suspicious"
   - Tính tổng bytes sent của suspicious IPs

5. **Hourly traffic summary:**
   - Tính request count theo `hour`
   - Tìm peak hour của toàn hệ thống và quiet hour
   - Optional sau giờ học: tạo pivot/heatmap theo endpoint x hour nếu muốn luyện visualization

6. **User behavior analysis:**
   - Tìm users có nhiều requests nhất (top 10)
   - Tính "session" đơn giản: nhóm các requests của cùng user trong vòng 30 phút vào 1 session
   - Hint: Sort by user_id + timestamp, dùng `diff()` và `cumsum()` để tạo session_id

**Expected insights:**
```
=== DATA QUALITY ===
Total logs: 5000, Nulls: 0, Duplicates: X
Success rate: ~78%, 4xx: ~15%, 5xx: ~7%
p50 response: ~120ms, p95: ~XXXms, p99: ~XXXXms

=== SLOW ENDPOINTS ===
endpoint              requests  success_rate  avg_ms  p95_ms  flag
/api/payments              XXX         XX.X%    XXX   XXXX  SLOW
...

=== ANOMALY DETECTION ===
Threshold: XXXms (mean + 2*std)
Slow request rate: X.X%
Top 3 endpoints by slow rate: [...]
Slow requests peak at hour: XX:00

=== SUSPICIOUS IPs ===
Found X suspicious IPs
Total bytes from suspicious IPs: XXX MB

=== HOURLY TRAFFIC ===
Peak hour: XX:00 (XXX requests)
Quiet hour: XX:00 (XX requests)
```

**Hint:**
- `df['status_code'].between(200, 299)` để check 2xx
- `np.percentile()` hoặc `df.quantile()` cho percentiles
- Z-score: `(x - mean) / std` — có thể dùng `scipy.stats.zscore` hoặc tính thủ công
- `df['timestamp'].dt.hour` để extract hour
- Optional heatmap: dùng `pd.pivot_table(aggfunc='count')`, sau đó `seaborn.heatmap(...)`
- Cho session: `df.sort_values(['user_id', 'timestamp'])`, rồi `diff() > pd.Timedelta('30min')`, rồi `cumsum()`

---

## 🔍 Gợi ý kiểm tra kết quả

**Bài 1 — Tự kiểm tra:**
```python
# Kiểm tra normalized array
assert normalized.min() == 0.0, "Min phải là 0"
assert normalized.max() == 1.0, "Max phải là 1"
assert normalized.shape == sales.shape, "Shape phải giữ nguyên"

# Kiểm tra tổng doanh thu
assert annual_sales.shape == (3,), "Phải có 3 giá trị (3 sản phẩm)"
print("Bài 1 PASS!" if annual_sales[0] == 1885 else "Bài 1 FAIL")
```

**Bài 2 — Sanity checks:**
```python
# Tổng market share phải = 100%
assert abs(city_analysis['market_share_%'].sum() - 100) < 0.1, "Market share phải tổng = 100%"

# Mỗi customer chỉ thuộc 1 tier
total_customers = tier1_count + tier2_count + tier3_count
unique_customers = orders[orders['status'] == 'completed']['customer_id'].nunique()
print(f"Total tiered: {total_customers}, Unique customers: {unique_customers}")
```

**Bài 3 — Performance checks:**
```python
import time

# Pipeline của bạn nên chạy trong < 5 giây cho 5000 records
start = time.time()
# ... run your analysis ...
elapsed = time.time() - start
print(f"Pipeline took: {elapsed:.2f}s {'OK' if elapsed < 5 else 'TOO SLOW — check for Python loops'}")

# Kiểm tra không dùng Python loop
# Code review: grep for "for " trong solution của bạn
# Nếu thấy for loop, thử vectorize lại
```

**Tips debug khi bị lỗi:**
- `KeyError`: Column name sai — kiểm tra `df.columns`
- `ValueError: ambiguous truth value`: Đang dùng `and`/`or` thay vì `&`/`|`
- `SettingWithCopyWarning`: Đang modify slice — thêm `.copy()` sau slice
- Shape mismatch: In `df.shape` tại từng bước để theo dõi
