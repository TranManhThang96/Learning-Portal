# Ngày 17: Python cho Data & AI — Numpy & Pandas

## 🎯 Mục tiêu học tập
- Hiểu tại sao Numpy array nhanh hơn Python list và khi nào cần dùng
- Thực hiện vectorized operations và broadcasting không cần vòng lặp
- Tạo, đọc, lọc, transform dữ liệu bằng Pandas DataFrame
- Biết khi nào nên dùng Pandas thay vì truy vấn SQL trực tiếp
- Làm quen với tư duy "columnar data" khác biệt hoàn toàn với JSON/array trong NodeJS

---

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| Xử lý mảng số lớn | `number[]`, lodash, slow loops | `numpy.ndarray` — vectorized, C-speed |
| Tabular data | Array of objects `{id, name, age}[]` | `pandas.DataFrame` — column-oriented |
| Filter rows | `.filter(row => row.age > 18)` | `df[df['age'] > 18]` |
| Group & aggregate | `.reduce()` hoặc lodash `groupBy` | `df.groupby('col').agg(...)` |
| Join 2 datasets | Viết tay hoặc dùng thư viện | `pd.merge(df1, df2, on='id')` |
| SQL-like query | Phải kết nối DB hoặc viết logic | `df.query("age > 18 and city == 'HN'")` |
| Missing values | `undefined`, `null` | `NaN` — có hàm xử lý riêng |
| Performance 1M rows | Chậm, tốn RAM | Numpy/Pandas — nhanh, memory-efficient |

**Tư duy chính cần thay đổi:** Trong NodeJS bạn nghĩ theo hàng (row-by-row, object-by-object). Trong Pandas bạn nghĩ theo cột (column operations). Đây là sự thay đổi tư duy lớn nhất.

---

## 🧰 Setup nhẹ trước khi học

NumPy/Pandas là heavy binary packages, không giống một utility package nhỏ trong npm. Cài bằng `uv` hoặc wheel chính thức để tránh tự build native dependencies:

```bash
uv add numpy pandas

# Optional, chỉ khi cần notebook, Parquet hoặc visualization:
uv add jupyterlab pyarrow matplotlib seaborn
```

Lưu ý thực tế:
- `pandas`, `numpy`, `pyarrow`, `jupyterlab`, `matplotlib` có thể làm `.venv` tăng vài trăm MB. Không cài tất cả nếu chỉ làm script phân tích nhỏ.
- Notebook tốt cho EDA, nhưng production pipeline nên là Python module/script có test, logging, và input/output rõ.
- Nếu chạy trong Docker, prefer image có wheels tương thích và cache dependency layer; tránh Alpine cho data stack vì nhiều package phụ thuộc native libs.

---

## 📖 Lý thuyết

### Section 1: Tại sao Numpy tồn tại — Vấn đề với Python list

**WHY — Tại sao Python list không đủ cho data/AI?**

Python list rất linh hoạt — một list có thể chứa `[1, "hello", True, None]` cùng lúc. Sự linh hoạt này có cái giá: mỗi phần tử trong list là một Python object riêng biệt, được cấp phát bộ nhớ động, có type checking overhead. Khi bạn cần xử lý 1 triệu số floating point để train model hay tính toán ma trận, chi phí này là không chấp nhận được.

Numpy giải quyết bằng cách: lưu trữ dữ liệu dạng **contiguous memory block** với **fixed type** — giống như C array. Không có Python object overhead. CPU có thể dùng SIMD instructions để tính nhiều phần tử cùng lúc.

**Analogie với NodeJS:** Hãy tưởng tượng `number[]` trong TypeScript chạy trên V8 với JIT optimization vs `Float64Array` (typed array). Numpy array tương tự `Float64Array` nhưng với API phong phú hơn nhiều cho toán học.

```python
import numpy as np
import time

# So sánh tốc độ: Python list vs Numpy array
size = 1_000_000

# Python list — slow path
python_list = list(range(size))
start = time.time()
result_list = [x * 2 for x in python_list]
list_time = time.time() - start

# Numpy array — fast path
numpy_array = np.arange(size)
start = time.time()
result_numpy = numpy_array * 2  # vectorized — không có vòng lặp Python
numpy_time = time.time() - start

print(f"Python list: {list_time:.4f}s")
print(f"Numpy array: {numpy_time:.4f}s")
print(f"Numpy nhanh hơn: {list_time / numpy_time:.1f}x")

# Kiểm tra bộ nhớ
import sys
print(f"\nBộ nhớ Python list: {sys.getsizeof(python_list) / 1024:.1f} KB")
print(f"Bộ nhớ Numpy array: {numpy_array.nbytes / 1024:.1f} KB")
# Numpy thường nhỏ hơn 5-8x vì không có Python object overhead
```

```python
import numpy as np

# ===== Tạo Numpy Array =====

# Từ Python list
arr1 = np.array([1, 2, 3, 4, 5])
print(f"arr1: {arr1}, dtype: {arr1.dtype}")  # int64 mặc định

# Chỉ định dtype — quan trọng cho memory optimization
arr_float = np.array([1.0, 2.0, 3.0], dtype=np.float32)  # 4 bytes/số thay vì 8
arr_int32 = np.array([1, 2, 3], dtype=np.int32)

# Tạo array đặc biệt
zeros = np.zeros(5)              # [0. 0. 0. 0. 0.]
ones = np.ones((3, 3))           # Ma trận 3x3 toàn số 1
identity = np.eye(3)             # Ma trận đơn vị 3x3
random_arr = np.random.rand(4)   # 4 số random trong [0, 1)
arange = np.arange(0, 10, 2)     # [0 2 4 6 8] — giống range() nhưng trả về array
linspace = np.linspace(0, 1, 5)  # [0.   0.25 0.5  0.75 1.  ] — 5 điểm đều nhau

print(f"\nzeros: {zeros}")
print(f"ones:\n{ones}")
print(f"identity:\n{identity}")
print(f"arange: {arange}")
print(f"linspace: {linspace}")

# ===== Shape và Reshape =====
# Shape là "hình dạng" của array — rất quan trọng trong ML
arr_2d = np.array([[1, 2, 3], [4, 5, 6]])  # 2 hàng, 3 cột
print(f"\narr_2d shape: {arr_2d.shape}")    # (2, 3)
print(f"arr_2d ndim: {arr_2d.ndim}")        # 2 — số chiều
print(f"arr_2d size: {arr_2d.size}")        # 6 — tổng số phần tử

# Reshape — thay đổi shape mà không copy data
arr_reshaped = arr_2d.reshape(3, 2)  # 3 hàng, 2 cột
arr_flat = arr_2d.flatten()          # về 1D: [1 2 3 4 5 6]
arr_ravel = arr_2d.ravel()           # tương tự flatten nhưng không copy khi có thể

print(f"\nReshaped:\n{arr_reshaped}")
print(f"Flat: {arr_flat}")
```

### Section 2: Vectorized Operations & Broadcasting

**WHY — Tại sao vectorized operations quan trọng?**

Trong NodeJS, để nhân mọi phần tử trong mảng với 2, bạn viết `arr.map(x => x * 2)`. Dù JavaScript V8 có tối ưu nhất định, vòng lặp vẫn chạy tuần tự qua từng phần tử. Numpy vectorized operations được biên dịch thành C/Fortran, dùng CPU SIMD instructions để xử lý nhiều phần tử **cùng lúc** — thực sự song song ở mức hardware.

**Broadcasting** là tính năng cho phép thực hiện operations trên arrays có shape khác nhau — Numpy tự động "mở rộng" array nhỏ hơn theo quy tắc nhất định.

```python
import numpy as np

# ===== Basic Vectorized Operations =====
a = np.array([1, 2, 3, 4, 5])
b = np.array([10, 20, 30, 40, 50])

# Arithmetic operations — element-wise
print(a + b)      # [11 22 33 44 55]
print(a * b)      # [10 40 90 160 250]
print(a ** 2)     # [1 4 9 16 25] — bình phương từng phần tử
print(np.sqrt(a)) # [1.   1.41 1.73 2.   2.24]

# Scalar operations — broadcast scalar tới mọi phần tử
print(a * 2 + 1)  # [3 5 7 9 11]

# So sánh — trả về boolean array
print(a > 3)      # [False False False True True]
print(a == 3)     # [False False True False False]

# Boolean indexing — lọc phần tử thỏa điều kiện
# Tương đương .filter() trong NodeJS nhưng nhanh hơn nhiều
print(a[a > 3])   # [4 5]

# ===== Mathematical Functions =====
angles = np.array([0, np.pi/2, np.pi])
print(np.sin(angles))   # [0.  1.  0.] — sin của mảng
print(np.cos(angles))   # [1.  0. -1.]
print(np.exp(a))        # e^1, e^2, e^3, e^4, e^5
print(np.log(a))        # log tự nhiên
print(np.log2(a))       # log base 2 — hữu ích cho information theory

# ===== Aggregate Functions =====
data = np.array([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5])
print(f"Sum: {data.sum()}")
print(f"Mean: {data.mean():.2f}")
print(f"Std: {data.std():.2f}")          # Standard deviation
print(f"Min: {data.min()}, Max: {data.max()}")
print(f"Median: {np.median(data)}")
print(f"Percentile 75: {np.percentile(data, 75)}")

# Cumulative operations
print(f"Cumsum: {data.cumsum()}")  # Tổng tích lũy — hữu ích cho time series

# ===== 2D Array Operations =====
matrix = np.array([[1, 2, 3],
                   [4, 5, 6],
                   [7, 8, 9]])

print(f"\nMatrix shape: {matrix.shape}")
print(f"Sum tất cả: {matrix.sum()}")
print(f"Sum theo cột (axis=0): {matrix.sum(axis=0)}")  # [12 15 18]
print(f"Sum theo hàng (axis=1): {matrix.sum(axis=1)}")  # [6 15 24]
print(f"Max theo cột: {matrix.max(axis=0)}")  # [7 8 9]

# Matrix multiplication — dùng @ operator (Python 3.5+)
a_mat = np.array([[1, 2], [3, 4]])
b_mat = np.array([[5, 6], [7, 8]])
print(f"\nMatrix multiply:\n{a_mat @ b_mat}")
# [[19 22]
#  [43 50]]

# Transpose
print(f"Transpose:\n{matrix.T}")
```

```python
import numpy as np

# ===== Broadcasting — Numpy's "magic" =====
# Broadcasting cho phép operations giữa arrays có shape khác nhau
# theo quy tắc: align từ phải sang trái, size phải = 1 hoặc bằng nhau

# Ví dụ 1: scalar broadcast to array
arr = np.array([1, 2, 3])
print(arr + 10)    # [11 12 13] — scalar 10 "broadcast" thành [10, 10, 10]

# Ví dụ 2: 1D broadcast với 2D
row = np.array([1, 2, 3])       # shape (3,)
matrix = np.ones((4, 3))        # shape (4, 3)
result = matrix + row           # row broadcast thành (4, 3)
print(f"Broadcasting result:\n{result}")
# [[2. 3. 4.]
#  [2. 3. 4.]
#  [2. 3. 4.]
#  [2. 3. 4.]]

# Ví dụ 3: column vector vs row vector — tạo outer product
col = np.array([[1], [2], [3], [4]])  # shape (4, 1)
row2 = np.array([10, 20, 30])         # shape (3,)
outer = col + row2                     # shape (4, 3)
print(f"\nOuter product-like:\n{outer}")
# [[11 21 31]
#  [12 22 32]
#  [13 23 33]
#  [14 24 34]]

# ===== Ứng dụng thực tế: Normalize features cho ML =====
# Trong ML, thường cần normalize dữ liệu về range [0, 1]
features = np.array([
    [100, 25, 50000],    # tuổi=25, lương=50000, điểm=100
    [85,  30, 75000],
    [92,  22, 45000],
    [78,  35, 90000],
])

# Min-max normalization: (x - min) / (max - min)
min_vals = features.min(axis=0)  # min của từng cột
max_vals = features.max(axis=0)  # max của từng cột
normalized = (features - min_vals) / (max_vals - min_vals)

print(f"Features gốc:\n{features}")
print(f"\nNormalized (min-max):\n{normalized.round(3)}")
# Mỗi cột giờ nằm trong [0, 1]
```

```python
import numpy as np

# ===== Slicing & Indexing — quan trọng =====
arr = np.arange(10)  # [0 1 2 3 4 5 6 7 8 9]

# Basic slicing — tương tự Python list
print(arr[2:5])    # [2 3 4]
print(arr[-3:])    # [7 8 9]
print(arr[::2])    # [0 2 4 6 8] — step=2

# 2D indexing
matrix = np.arange(12).reshape(3, 4)
# [[ 0  1  2  3]
#  [ 4  5  6  7]
#  [ 8  9 10 11]]

print(matrix[1, 2])     # 6 — hàng 1, cột 2
print(matrix[0, :])     # [0 1 2 3] — hàng 0, tất cả cột
print(matrix[:, 2])     # [2 6 10] — tất cả hàng, cột 2
print(matrix[1:, 2:])   # [[6 7], [10 11]] — sub-matrix

# Fancy indexing — chọn hàng/cột không liên tục
rows = [0, 2]
cols = [1, 3]
print(matrix[rows, cols])  # [1, 11] — (0,1) và (2,3)

# Boolean indexing
print(matrix[matrix > 5])  # [6 7 8 9 10 11]

# ===== Views vs Copies — QUAN TRỌNG =====
# Slicing trả về VIEW (không copy) — thay đổi view ảnh hưởng original
original = np.array([1, 2, 3, 4, 5])
view = original[1:4]     # View, không phải copy
view[0] = 99             # Thay đổi view
print(f"Original sau khi thay đổi view: {original}")  # [1 99 3 4 5] — bị thay đổi!

# Để có copy thực sự, dùng .copy()
safe_copy = original[1:4].copy()
safe_copy[0] = 0
print(f"Original sau khi thay đổi copy: {original}")  # Không đổi
```

### Section 3: Pandas DataFrame — Xử lý dữ liệu bảng

**WHY — Tại sao Pandas ra đời?**

Numpy rất mạnh với mảng số đồng nhất, nhưng dữ liệu thực tế thường là **bảng** với nhiều kiểu: cột `name` (string), cột `age` (int), cột `salary` (float), cột `hired_date` (datetime). Numpy không handle tốt điều này.

Pandas DataFrame về cơ bản là **dict của Numpy arrays** — mỗi cột là một Numpy array, được đặt tên và gắn với một shared index. Điều này cho phép bạn xử lý dữ liệu bảng với performance gần Numpy.

Nếu bạn từng làm với SQL, Pandas sẽ rất quen thuộc — `groupby`, `merge`, `filter`, `sort` đều có đầy đủ, nhưng ngay trong Python không cần kết nối database.

```python
import pandas as pd
import numpy as np

# ===== Tạo DataFrame =====

# Cách 1: Từ dict — tự nhiên nhất, giống JSON object trong NodeJS
data = {
    'name':   ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
    'age':    [28, 35, 22, 31, 27],
    'city':   ['HN', 'HCM', 'HN', 'DN', 'HCM'],
    'salary': [75000, 90000, 55000, 82000, 68000],
    'active': [True, True, False, True, False],
}
df = pd.DataFrame(data)
print(df)
print(f"\nShape: {df.shape}")       # (5, 5) — 5 hàng, 5 cột
print(f"Columns: {df.columns.tolist()}")
print(f"Dtypes:\n{df.dtypes}")

# Cách 2: Từ CSV file — phổ biến nhất trong thực tế
# df = pd.read_csv('data.csv')
# df = pd.read_csv('data.csv', encoding='utf-8', parse_dates=['created_at'])

# Cách 3: Từ list of dicts — giống Array of Objects trong NodeJS
records = [
    {'id': 1, 'product': 'Laptop', 'price': 1200},
    {'id': 2, 'product': 'Mouse',  'price': 25},
    {'id': 3, 'product': 'Keyboard', 'price': 75},
]
df_records = pd.DataFrame(records)
print(f"\nDataFrame từ records:\n{df_records}")

# ===== Khám phá DataFrame — Luôn làm trước khi xử lý =====
print(f"\n--- Thông tin tổng quan ---")
print(df.info())         # dtype, null count, memory usage
print(df.describe())     # statistics: count, mean, std, min, max, percentiles
print(df.head(3))        # 3 hàng đầu
print(df.tail(2))        # 2 hàng cuối
print(df.sample(2))      # 2 hàng ngẫu nhiên — hữu ích để inspect dữ liệu lớn
```

```python
import pandas as pd

# ===== Selecting Data — Truy cập dữ liệu =====
data = {
    'name':   ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
    'age':    [28, 35, 22, 31, 27],
    'city':   ['HN', 'HCM', 'HN', 'DN', 'HCM'],
    'salary': [75000, 90000, 55000, 82000, 68000],
}
df = pd.DataFrame(data)

# Chọn cột — trả về Series (1D)
print(df['name'])           # Series
print(df['salary'])

# Chọn nhiều cột — trả về DataFrame
print(df[['name', 'salary']])

# .loc — label-based indexing (dùng index labels)
print(df.loc[0])            # Hàng index 0
print(df.loc[1:3])          # Hàng index 1, 2, 3 (INCLUSIVE — khác Python slicing!)
print(df.loc[0:2, 'name':'age'])  # Hàng 0-2, cột name đến age

# .iloc — integer-based indexing (dùng số nguyên vị trí)
print(df.iloc[0])           # Hàng đầu tiên
print(df.iloc[-1])          # Hàng cuối
print(df.iloc[1:3])         # Hàng 1, 2 (EXCLUSIVE như Python slicing)
print(df.iloc[:, 0:2])      # Tất cả hàng, cột 0 và 1

# ===== Filtering — Lọc dữ liệu =====
# Tương đương WHERE trong SQL

# Điều kiện đơn
high_salary = df[df['salary'] > 70000]
print(f"\nSalary > 70000:\n{high_salary}")

# Nhiều điều kiện — dùng & (AND) và | (OR), KHÔNG dùng 'and'/'or'
hn_high = df[(df['city'] == 'HN') & (df['salary'] > 70000)]
print(f"\nHN và salary > 70000:\n{hn_high}")

young_or_rich = df[(df['age'] < 25) | (df['salary'] > 85000)]
print(f"\nTuổi < 25 hoặc salary > 85000:\n{young_or_rich}")

# .query() — cú pháp SQL-like, dễ đọc hơn với điều kiện phức tạp
result = df.query("age > 25 and city == 'HN'")
print(f"\nQuery syntax:\n{result}")

# .isin() — kiểm tra giá trị trong danh sách
cities_filter = df[df['city'].isin(['HN', 'HCM'])]
print(f"\nisin filter:\n{cities_filter}")

# String operations
# df[df['name'].str.startswith('A')]    # Tên bắt đầu bằng A
# df[df['name'].str.contains('ali', case=False)]  # Tên chứa "ali"
```

```python
import pandas as pd
import numpy as np

# ===== Data Manipulation — Biến đổi dữ liệu =====
data = {
    'name':     ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
    'age':      [28, 35, 22, 31, 27],
    'city':     ['HN', 'HCM', 'HN', 'DN', 'HCM'],
    'salary':   [75000, 90000, 55000, 82000, 68000],
    'bonus':    [5000, None, 3000, None, 4500],  # Có missing values
}
df = pd.DataFrame(data)

# ===== Thêm cột mới =====
# Cách 1: Tính từ cột khác
df['total_comp'] = df['salary'] + df['bonus'].fillna(0)  # fillna thay NaN = 0
df['seniority'] = df['age'].apply(lambda age: 'senior' if age >= 30 else 'junior')

# Cách 2: apply() với function phức tạp hơn
def classify_salary(row):
    if row['salary'] > 80000:
        return 'high'
    elif row['salary'] > 60000:
        return 'medium'
    return 'low'

df['salary_band'] = df.apply(classify_salary, axis=1)  # axis=1 = apply theo hàng

print(df[['name', 'salary', 'bonus', 'total_comp', 'seniority', 'salary_band']])

# ===== Xử lý Missing Values =====
print(f"\nNull counts:\n{df.isnull().sum()}")  # Đếm null từng cột

# Các chiến lược xử lý NaN
df_filled = df.fillna({'bonus': 0, 'city': 'Unknown'})  # Fill bằng giá trị cụ thể
df_filled_mean = df.copy()
df_filled_mean['bonus'] = df['bonus'].fillna(df['bonus'].mean())  # Fill bằng mean
df_dropped = df.dropna()         # Xóa hàng có bất kỳ NaN nào
df_dropped_subset = df.dropna(subset=['salary'])  # Chỉ xóa nếu 'salary' là NaN

# ===== Sort =====
df_sorted = df.sort_values('salary', ascending=False)
print(f"\nSort by salary descending:\n{df_sorted[['name', 'salary']]}")

df_multi_sort = df.sort_values(['city', 'salary'], ascending=[True, False])
print(f"\nSort by city asc, salary desc:\n{df_multi_sort[['name', 'city', 'salary']]}")

# ===== Rename, Drop columns =====
df_renamed = df.rename(columns={'name': 'full_name', 'age': 'years_old'})
df_dropped_col = df.drop(columns=['bonus'])
df_dropped_row = df.drop(index=[0, 2])  # Xóa hàng 0 và 2
```

```python
import pandas as pd
import numpy as np

# ===== GroupBy & Aggregation — Giống GROUP BY trong SQL =====
data = {
    'name':       ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank'],
    'department': ['Eng', 'Eng', 'Sales', 'Sales', 'Eng', 'Sales'],
    'city':       ['HN', 'HCM', 'HN', 'HCM', 'HN', 'DN'],
    'salary':     [75000, 90000, 55000, 82000, 68000, 60000],
    'experience': [3, 7, 2, 5, 4, 3],
}
df = pd.DataFrame(data)

# GroupBy cơ bản — tương đương: SELECT department, AVG(salary) GROUP BY department
dept_avg = df.groupby('department')['salary'].mean()
print(f"Avg salary by dept:\n{dept_avg}")

# Multiple aggregations
dept_stats = df.groupby('department').agg(
    avg_salary=('salary', 'mean'),
    max_salary=('salary', 'max'),
    min_salary=('salary', 'min'),
    headcount=('name', 'count'),
    avg_exp=('experience', 'mean'),
)
print(f"\nDept stats:\n{dept_stats}")

# Group by nhiều cột
multi_group = df.groupby(['department', 'city'])['salary'].agg(['mean', 'count'])
print(f"\nMulti-level groupby:\n{multi_group}")

# ===== Merge / Join — Tương đương JOIN trong SQL =====
employees = pd.DataFrame({
    'emp_id':   [1, 2, 3, 4],
    'name':     ['Alice', 'Bob', 'Charlie', 'Diana'],
    'dept_id':  [101, 102, 101, 103],
})

departments = pd.DataFrame({
    'dept_id':   [101, 102, 104],  # 104 không có employee, 103 không có dept
    'dept_name': ['Engineering', 'Sales', 'Marketing'],
    'budget':    [500000, 300000, 200000],
})

# INNER JOIN — chỉ hàng khớp cả 2 phía
inner = pd.merge(employees, departments, on='dept_id', how='inner')
print(f"\nINNER JOIN:\n{inner}")

# LEFT JOIN — giữ tất cả employees dù không có dept
left = pd.merge(employees, departments, on='dept_id', how='left')
print(f"\nLEFT JOIN:\n{left}")

# RIGHT JOIN — giữ tất cả departments
right = pd.merge(employees, departments, on='dept_id', how='right')
print(f"\nRIGHT JOIN:\n{right}")

# JOIN với tên cột khác nhau
orders = pd.DataFrame({'order_id': [1, 2], 'customer_id': [10, 20], 'amount': [100, 200]})
customers = pd.DataFrame({'id': [10, 20], 'customer_name': ['X Corp', 'Y Ltd']})
joined = pd.merge(orders, customers, left_on='customer_id', right_on='id')
print(f"\nJoin với tên cột khác:\n{joined}")

# ===== Optional reference: Pivot Table — không cần master trong 2 giờ =====
# NOTE: Phần này là "reference skill" — không cần master ngay.
# Tự học khi cần: https://pandas.pydata.org/docs/user_guide/reshaping.html
pivot = df.pivot_table(
    values='salary',
    index='department',
    columns='city',
    aggfunc='mean',
    fill_value=0
)
print(f"\nPivot table (avg salary by dept x city):\n{pivot}")
```

```python
import pandas as pd
import numpy as np

# ===== Time Series — Xử lý dữ liệu thời gian =====
# Rất phổ biến khi làm với logs, metrics, financial data

# Tạo time series data
dates = pd.date_range(start='2024-01-01', periods=10, freq='D')  # 10 ngày
ts_data = pd.DataFrame({
    'date': dates,
    'revenue': [1000, 1200, 900, 1500, 1100, 1300, 1400, 800, 1600, 1700],
    'users':   [100, 120, 90, 150, 110, 130, 140, 80, 160, 170],
})
ts_data.set_index('date', inplace=True)  # Set date làm index
print(ts_data)

# Resample — tổng hợp theo time bucket
weekly = ts_data.resample('W').sum()     # Tổng theo tuần
print(f"\nWeekly sum:\n{weekly}")

# Optional reference: rolling window — đọc thêm khi làm time-series thật
ts_data['revenue_ma3'] = ts_data['revenue'].rolling(window=3).mean()
print(f"\n3-day moving average:\n{ts_data}")

# Shift — lag features (hữu ích cho forecasting)
ts_data['revenue_yesterday'] = ts_data['revenue'].shift(1)   # Giá trị hôm qua
ts_data['revenue_change'] = ts_data['revenue'].diff()         # Thay đổi so với hôm qua

# ===== Export Data =====
# df.to_csv('output.csv', index=False)         # CSV
# df.to_json('output.json', orient='records')  # JSON array of objects
# df.to_parquet('output.parquet')              # Parquet — binary, compressed, fast
# df.to_sql('table_name', engine, if_exists='replace')  # SQLAlchemy
```

### Section 4: Khi nào dùng Pandas vs SQL

**WHY — Tại sao cần biết điều này?**

Câu hỏi này rất thực tế: nếu bạn có thể làm trong database, tại sao phải load data vào Python? Và ngược lại, khi nào Pandas có lợi thế hơn?

**Dùng SQL khi:**
- Data nằm trong database và bạn chỉ cần subset nhỏ
- Cần tận dụng index, join optimization của database engine
- Data quá lớn để load vào RAM. Pandas thường cần nhiều RAM hơn kích thước file thô vì index, object/string columns, intermediate copies, và dtype conversion.
- Nhiều người cùng query, cần concurrency control
- Query đơn giản, không cần Python logic

**Dùng Pandas khi:**
- Data đã có sẵn (CSV, Excel, API response, S3)
- Cần transformations phức tạp không dễ viết trong SQL
- Làm EDA (Exploratory Data Analysis) — khám phá dữ liệu nhanh
- Pipeline preprocessing cho ML model
- Cần tích hợp với Python ecosystem (scikit-learn, matplotlib, etc.)
- Prototype nhanh trước khi optimize

**Data-size caveat:** Pandas không thay thế database. Nếu dữ liệu nằm trong Postgres/BigQuery/Snowflake, hãy push filter/join/aggregate xuống engine trước rồi chỉ kéo subset đã giảm kích thước về Pandas. Với CSV/Parquet lớn, đo `df.memory_usage(deep=True).sum()` ngay sau khi load và dùng `usecols`, `dtype`, `chunksize`, hoặc DuckDB/Polars lazy scan khi cần.

**Hybrid approach — phổ biến nhất trong thực tế:**

```python
import pandas as pd
import sqlalchemy as sa

# Dùng SQL để filter + aggregate ở database level
# Chỉ pull dữ liệu đã được reduce về Python
# engine = sa.create_engine('postgresql://user:pass@host/db')

# query = """
#     SELECT
#         date_trunc('month', created_at) as month,
#         product_category,
#         SUM(amount) as total_revenue,
#         COUNT(*) as order_count
#     FROM orders
#     WHERE created_at >= '2024-01-01'
#     GROUP BY 1, 2
# """
# df = pd.read_sql(query, engine)

# Sau đó dùng Pandas cho phần Python không làm được trong SQL
# df['revenue_share'] = df['total_revenue'] / df.groupby('month')['total_revenue'].transform('sum')
# df['yoy_growth'] = df.groupby('product_category')['total_revenue'].pct_change(12)

# Ví dụ demo không cần DB:
df = pd.DataFrame({
    'month':    ['2024-01', '2024-01', '2024-02', '2024-02'],
    'category': ['A', 'B', 'A', 'B'],
    'revenue':  [1000, 2000, 1200, 1800],
})

# Tính % share của từng category trong tháng — khó làm trong SQL thuần
df['monthly_total'] = df.groupby('month')['revenue'].transform('sum')
df['share'] = (df['revenue'] / df['monthly_total'] * 100).round(1)
print(df)
```

---

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Dùng Python loop thay vectorized ops | Chậm 100-1000x | Dùng `numpy` ops hoặc `df.apply()` |
| Không kiểm tra `df.info()` / `df.describe()` trước | Xử lý sai kiểu dữ liệu, bỏ qua NaN | Luôn explore trước khi transform |
| Quên `axis=0` vs `axis=1` trong aggregation | Kết quả sai | `axis=0` = theo cột (default), `axis=1` = theo hàng |
| Dùng `and`/`or` thay `&`/`|` trong filter | `ValueError` | Dùng `&`, `|` và wrap từng condition trong `()` |
| Modify slice (SettingWithCopyWarning) | Thay đổi không như ý | Dùng `.copy()` hoặc `.loc[]` trực tiếp |
| Load toàn bộ CSV lớn vào RAM | Memory error | Dùng `chunksize`, `usecols`, hoặc `dtype` để giảm RAM |
| Quên reset index sau `groupby`/`filter` | Index lộn xộn | Thêm `.reset_index()` khi cần |
| `df.loc[1:3]` vs `df.iloc[1:3]` nhầm lẫn | Kết quả khác nhau | `.loc` inclusive, `.iloc` exclusive |

---

## ✅ Best Practices

- **Luôn kiểm tra shape và dtypes trước:** `df.info()`, `df.describe()`, `df.isnull().sum()` — giúp phát hiện vấn đề sớm.
- **Prefer vectorized operations:** Tránh `.apply()` với Python function khi có Numpy/Pandas built-in equivalent. `.apply()` chạy Python loop ở backend.
- **Chỉ định dtype khi đọc data:** `pd.read_csv('file.csv', dtype={'id': 'int32', 'price': 'float32'})` — giảm RAM và tăng tốc độ đọc.
- **Dùng `.copy()` khi tạo DataFrame con để modify:** Tránh `SettingWithCopyWarning` và side effects.
- **Dùng `query()` cho điều kiện phức tạp:** Dễ đọc hơn chained boolean indexing.
- **Đặt tên có nghĩa khi `agg()`:** `agg(avg_salary=('salary', 'mean'))` thay vì `agg({'salary': 'mean'})` — kết quả có tên cột đẹp hơn.
- **Dùng Parquet thay CSV cho production:** Parquet nhỏ hơn 5-10x, đọc nhanh hơn, giữ dtype information.
- **Với data lớn hơn RAM hoặc cần query pushdown, xem xét DuckDB/Polars/Dask:** chọn theo workload thay vì theo ngưỡng tuyệt đối. Pandas vẫn tốt cho subset vừa RAM và EDA nhanh.

---

## ⚖️ Trade-offs

| | Numpy | Pandas | SQL | Polars |
|-|-------|--------|-----|--------|
| **Use case** | Numerical compute, ML | Data manipulation, EDA | Query stored data | Large-scale data processing |
| **Performance** | Rất nhanh cho numeric arrays đồng nhất | Nhanh nếu data vừa RAM và dùng vectorized ops | Phụ thuộc DB engine/index/query plan | Thường nhanh hơn Pandas cho workloads lớn, nhưng cần benchmark |
| **Memory** | Hiệu quả | Có thể lớn hơn file thô nhiều lần, nhất là string/object columns | Data ở DB | Lazy evaluation, pushdown tốt hơn |
| **API** | Low-level | High-level, SQL-like | Declarative | Pandas-like nhưng stricter |
| **Missing values** | Không hỗ trợ trực tiếp | Tốt (NaN, NA) | DB-specific | Tốt |
| **Learning curve** | Trung bình | Trung bình | Thấp (nếu biết SQL) | Trung bình |

---

## 🚀 Performance Notes

- **Chỉ định dtype khi tạo array/DataFrame:** `np.int32` thay `np.int64` tiết kiệm 50% RAM, tính toán nhanh hơn trên nhiều CPU.
- **Avoid chained indexing:** `df['a']['b']` tạo intermediate copy. Dùng `df.loc[:, ['a', 'b']]`.
- **Dùng `numba` khi cần loop không tránh được:** `@numba.jit` compile Python function thành machine code.
- **`pd.eval()` cho expressions phức tạp:** Pandas dùng numexpr backend, nhanh hơn cho large DataFrames.
- **Categoricals cho string columns lặp lại:** `df['city'] = df['city'].astype('category')` tiết kiệm RAM 10x nếu có ít unique values.
- **Vectorized string ops:** `df['name'].str.lower()` nhanh hơn `.apply(lambda x: x.lower())`.

```python
import pandas as pd
import numpy as np

# Demo: Category dtype tiết kiệm RAM
n = 1_000_000
cities = ['HN', 'HCM', 'DN', 'HP', 'CT']

df_str = pd.DataFrame({'city': np.random.choice(cities, n)})
df_cat = df_str.copy()
df_cat['city'] = df_cat['city'].astype('category')

print(f"String dtype memory: {df_str.memory_usage(deep=True)['city'] / 1e6:.1f} MB")
print(f"Category dtype memory: {df_cat.memory_usage(deep=True)['city'] / 1e6:.1f} MB")
# String: ~64 MB, Category: ~1 MB — tiết kiệm 60x!
```

---

## 📊 Data Visualization Cơ Bản

> **Phần mở rộng — chỉ cần biết đủ dùng, không cần master.**
> Đủ để: debug embeddings, analyze data distributions, visualize model evaluation metrics trong AI workflow.

```python
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd

# --- Matplotlib cơ bản ---
# Plot, bar, scatter, histogram — đủ cho 90% use cases

# Line plot — show trends
x = np.linspace(0, 10, 100)
fig, axes = plt.subplots(1, 3, figsize=(15, 4))

axes[0].plot(x, np.sin(x), label="sin(x)", color="blue")
axes[0].plot(x, np.cos(x), label="cos(x)", color="red", linestyle="--")
axes[0].set_title("Line Plot")
axes[0].legend()

# Histogram — analyze distribution
data = np.random.normal(loc=0, scale=1, size=1000)
axes[1].hist(data, bins=30, edgecolor="black", alpha=0.7)
axes[1].set_title("Distribution — LLM Embedding Similarities")
axes[1].set_xlabel("Cosine similarity")

# Scatter — debug embeddings
# Dùng t-SNE/UMAP để reduce từ 1536-dim → 2D rồi visualize
points = np.random.randn(50, 2)
labels = np.random.choice(["category_A", "category_B", "category_C"], size=50)
colors = {"category_A": "blue", "category_B": "red", "category_C": "green"}
for cat, color in colors.items():
    mask = labels == cat
    axes[2].scatter(points[mask, 0], points[mask, 1], c=color, label=cat, alpha=0.7)
axes[2].set_title("Embedding Clusters (2D t-SNE)")
axes[2].legend()

plt.tight_layout()
plt.savefig("analysis.png", dpi=150, bbox_inches="tight")
# plt.show()  # Uncomment nếu chạy interactive

# --- Seaborn — statistical plots đẹp hơn matplotlib ---
# Đặc biệt tốt cho: correlation heatmaps, distribution comparisons

df = pd.DataFrame({
    "score": np.random.uniform(0.5, 1.0, 100),
    "latency_ms": np.random.exponential(200, 100),
    "model": np.random.choice(["gpt-4o", "gpt-4o-mini", "claude-3"], 100),
})

fig, axes = plt.subplots(1, 2, figsize=(12, 4))

# Violin plot — compare distributions between groups
sns.violinplot(data=df, x="model", y="score", ax=axes[0])
axes[0].set_title("Model Score Distribution")

# Scatter với regression line
sns.scatterplot(data=df, x="latency_ms", y="score", hue="model", ax=axes[1], alpha=0.7)
axes[1].set_title("Score vs Latency")

plt.tight_layout()
plt.savefig("model_comparison.png", dpi=150, bbox_inches="tight")

# --- Ứng dụng trong AI workflow ---
# 1. Visualize embedding clusters (t-SNE/UMAP)
# from sklearn.manifold import TSNE
# embeddings_2d = TSNE(n_components=2).fit_transform(embeddings)
# plt.scatter(embeddings_2d[:, 0], embeddings_2d[:, 1], c=labels)

# 2. RAG evaluation — precision/recall curve
# plt.plot(recall_values, precision_values)

# 3. Token usage analysis
# df["tokens"].hist(bins=50)

# Lưu ý: trong Jupyter Notebook dùng %matplotlib inline
# Trong scripts, dùng plt.savefig() thay plt.show()
```

> **Khi cần visualization**: debug embeddings (t-SNE/UMAP), analyze data distribution trước khi train, so sánh model performance, present results cho stakeholders.

## 📝 Tóm tắt

- **Numpy array** lưu trữ dữ liệu đồng nhất trong contiguous memory block, loại bỏ Python object overhead — nhanh hơn Python list 10-100x cho numerical computation.
- **Vectorized operations** thay thế Python loops bằng C-level operations — đây là core philosophy của numerical Python.
- **Broadcasting** cho phép operations giữa arrays có shape khác nhau theo quy tắc alignment từ phải sang trái.
- **Pandas DataFrame** = dict of named Numpy arrays + shared index — best tool cho tabular data manipulation trong Python ecosystem.
- **Tư duy columnar:** Thay vì iterate qua từng hàng (như NodeJS), hãy nghĩ theo cột và apply operations lên toàn cột.
- **Pandas vs SQL:** Dùng SQL để filter/aggregate ở DB layer, pull subset nhỏ về Pandas cho Python-specific transformations — đây là hybrid approach phổ biến nhất.
- **Pandas advanced topics** (pivot tables, multi-index, window functions) — tự học khi cần, đây là reference skill không cần master ngay.
- **Visualization**: matplotlib/seaborn — đủ dùng cho AI workflow, không cần master.
- **Với dữ liệu lớn hơn RAM**, xem xét Polars (lazy evaluation), DuckDB (SQL engine chạy trực tiếp trên file), Dask/Spark (distributed). Đừng chọn chỉ theo con số dòng/file size; đo memory và query pattern trước.
