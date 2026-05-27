# Tài Liệu Tham Khảo — Ngày 17: Numpy & Pandas

## 📚 Official Docs

- **Numpy User Guide** — https://numpy.org/doc/stable/user/index.html — Bắt đầu từ "Absolute Basics", đặc biệt đọc phần Broadcasting
- **Numpy API Reference** — https://numpy.org/doc/stable/reference/index.html — Tra cứu function cụ thể
- **Pandas User Guide** — https://pandas.pydata.org/docs/user_guide/index.html — Đọc "10 minutes to pandas" trước, sau đó "Indexing and selecting data"
- **Pandas API Reference** — https://pandas.pydata.org/docs/reference/index.html — Reference đầy đủ
- **Pandas Cheat Sheet (Official)** — https://pandas.pydata.org/Pandas_Cheat_Sheet.pdf — In ra, dán lên tường

## 🎥 Video / Courses

- **NumPy Tutorial (Tech With Tim)** — https://www.youtube.com/watch?v=GB9ByFAIAH4 — 1 giờ, đủ foundation
- **Pandas Tutorial (Corey Schafer)** — https://www.youtube.com/playlist?list=PL-osiE80TeTsWmV9i9c58mdDCSskIFdDS — Series 10 video, chất lượng cao, cover từng topic riêng
- **NumPy vs Lists (Speed Test visual)** — https://www.youtube.com/watch?v=vF5S7QRxhOc — Ngắn, demo rõ tại sao Numpy nhanh hơn
- **Pandas GroupBy Explained** — https://www.youtube.com/watch?v=txMdrV1Ut64 — Chuyên sâu về groupby, rất hữu ích

## 📝 Articles / Blog Posts

- **"Why NumPy is Fast"** — https://numpy.org/doc/stable/user/whatisnumpy.html — Giải thích kỹ thuật tại sao Numpy nhanh hơn Python list
- **"A Visual Intro to NumPy"** — http://jalammar.github.io/visual-numpy/ — Visualization rất đẹp, dễ hiểu shape/broadcasting
- **"Pandas DataFrame, Hello World"** — https://towardsdatascience.com/pandas-dataframe-a-lightweight-intro-680e3a212b96 — Intro nhanh cho người mới
- **"Pandas vs SQL"** — https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_sql.html — Official comparison, có code ví dụ song song
- **"Modern Pandas" (Tom Augspurger)** — https://tomaugspurger.github.io/modern-1-intro — Series 7 phần, intermediate level, best practices thực tế
- **"Vectorization in Python"** — https://realpython.com/numpy-array-programming/ — Real Python, giải thích vectorization chi tiết

## 🔧 Tools / Libraries

- **Numpy** — `uv add numpy` — Numerical computing foundation
- **Pandas** — `uv add pandas` — Data manipulation
- **Polars** — `uv add polars` — https://pola.rs — Pandas alternative, Rust-based, lazy evaluation; thường nhanh hơn trên workloads lớn nhưng phải benchmark với dữ liệu thật
- **DuckDB** — `uv add duckdb` — https://duckdb.org — Chạy SQL query trực tiếp trên Pandas DataFrame và Parquet files, rất mạnh
- **Pyarrow** — `uv add pyarrow` — https://arrow.apache.org/docs/python/ — Parquet I/O, tích hợp với Pandas
- **Jupyter Lab** — `uv add jupyterlab` — Interactive notebook, tốt nhất để explore data với Pandas
- **Matplotlib** — `uv add matplotlib` — Visualization cơ bản, tích hợp với Pandas (`df.plot()`)
- **Seaborn** — `uv add seaborn` — Statistical visualization đẹp hơn Matplotlib

**Setup caveats:**
- Cài tối thiểu cho bài chính: `uv add numpy pandas`.
- `jupyterlab`, `pyarrow`, `matplotlib`, `seaborn` kéo thêm nhiều native/binary dependencies; chỉ cài khi cần notebook, Parquet, hoặc visualization.
- Trong Docker/CI, cache `uv.lock` và dependency layer. Tránh Alpine cho data stack nếu không có lý do rõ, vì wheel/native dependency có thể khó tương thích.

## 💡 Ghi chú thêm

**Cho NodeJS devs — những điểm hay nhầm:**

1. **Indexing**: Trong Pandas, `df.loc[1:3]` lấy index 1, 2, **và 3** (inclusive). Khác với JavaScript/Python slice `[1:3]` = exclusive. `df.iloc[1:3]` mới là exclusive như Python.

2. **In-place vs returning new object**: Hầu hết Pandas operations trả về DataFrame mới, không modify in-place. Để modify in-place dùng `inplace=True` parameter (hoặc reassign: `df = df.sort_values(...)`). Khác với nhiều JS array methods mutate in-place.

3. **NaN != None**: `None` trong Python và `NaN` trong Numpy/Pandas là khác nhau. Pandas tự convert `None` thành `NaN` cho numeric columns. Luôn dùng `pd.isna()` hoặc `df.isnull()` để check — đừng dùng `== None` hay `== np.nan`.

4. **Copy vs View warning**: Khi bạn slice một DataFrame rồi assign vào cột, Pandas warn `SettingWithCopyWarning`. Đây là Python gotcha không có tương đương trong JS. Solution: luôn dùng `.copy()` khi cần modify subset, hoặc dùng `.loc` trực tiếp.

**Workflow khuyến nghị khi làm việc với data mới:**
```
1. df.info()          → dtypes, nulls, memory
2. df.describe()      → statistics
3. df.head(20)        → visual check
4. df.isnull().sum()  → null audit
5. df.duplicated().sum() → duplicate check
6. df['col'].value_counts() → categorical distribution
```

**Khi nào upgrade từ Pandas:**
- Data vừa RAM nhưng cần SQL/pushdown trên CSV/Parquet: xem xét **DuckDB**
- Data lớn hơn RAM hoặc cần lazy/multi-threaded DataFrame: xem xét **Polars**
- Data distributed: xem xét **Dask** (Pandas-like API) hoặc **Spark**
- Real-time streaming: **Kafka + Faust** (Python Kafka library) — quen thuộc với bạn
