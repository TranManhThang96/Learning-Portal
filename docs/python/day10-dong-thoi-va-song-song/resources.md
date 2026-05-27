# Tài Liệu Tham Khảo — Ngày 10: Concurrency & Parallelism

## 📚 Official Docs

- **threading** — https://docs.python.org/3/library/threading.html — Thread, Lock, Event, Semaphore
- **multiprocessing** — https://docs.python.org/3/library/multiprocessing.html — Process, Pool, Queue, Pipe
- **concurrent.futures** — https://docs.python.org/3/library/concurrent.futures.html — ThreadPoolExecutor, ProcessPoolExecutor
- **asyncio.to_thread** — https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread — Python 3.9+
- **GIL** — https://docs.python.org/3/glossary.html#term-global-interpreter-lock — Official explanation

## 🎥 Video / Courses

- **"Python GIL Explained"** - mCoding (YouTube) — Tại sao GIL tồn tại, ảnh hưởng thực tế
- **"Asyncio vs Threading vs Multiprocessing"** - Arjan Codes (YouTube) — Decision guide rõ ràng
- **"David Beazley — Understanding the Python GIL"** (PyCon 2010) — Classic talk, vẫn còn giá trị
- **"Python Multiprocessing"** - Real Python (YouTube)

## 📝 Articles / Blog Posts

- **"Python's GIL"** — dabeaz.com — Sâu nhất về GIL internals
- **"Speed Up Your Python Program With Concurrency"** — realpython.com — Comparison + benchmarks
- **"Python Concurrency: The Tricky Bits"** — python.hamel.dev — Edge cases
- **"Multiprocessing vs Threading vs AsyncIO in Python"** — superfastpython.com

## 🔧 Tools / Libraries

- **`concurrent.futures`** — stdlib — Best starting point cho thread/process pools
- **`multiprocessing.shared_memory`** — stdlib (3.8+) — Shared memory giữa processes
- **`joblib`** — joblib.readthedocs.io — Scikit-learn's parallel computing lib, caching
- **`ray`** — ray.io — Distributed computing framework, production-grade
- **`dask`** — dask.org — Parallel arrays/dataframes, scales to clusters
- **`loky`** — github.com/joblib/loky — Better process pools (joblib backend)

## 💡 Ghi chú thêm

- **`sys.getswitchinterval()`**: GIL switch mỗi 5ms (mặc định), có thể điều chỉnh:
  ```python
  import sys
  sys.setswitchinterval(0.001)  # Switch nhanh hơn — không khuyến khích
  ```

- **`multiprocessing.cpu_count()`**: số logical CPU cores:
  ```python
  import os
  print(os.cpu_count())  # tổng logical cores
  print(len(os.sched_getaffinity(0)))  # cores available cho process này (Linux)
  ```

- **`__name__ == '__main__'` guard** — bắt buộc cho multiprocessing:
  ```python
  if __name__ == "__main__":
      with ProcessPoolExecutor() as pool:
          results = list(pool.map(my_function, data))
  ```
  Trên Windows/macOS hoặc start method `"spawn"`, child process import lại main module; thiếu guard có thể gây `RuntimeError` hoặc spawn lặp. Function truyền vào pool phải ở module level và pickle-able.

- **free-threaded Python (Python 3.13+)**: GIL có thể disabled với `--disable-gil` flag — experimental, API vẫn đang phát triển. Theo dõi: https://peps.python.org/pep-0703/

- **Profiling concurrency**: dùng `py-spy` để profile threads/processes:
  ```bash
  uv add py-spy
  py-spy top --pid <PID>
  ```

- **Xem Ngày 11** để hiểu cách test concurrent code với pytest-asyncio và mock thread pools.
