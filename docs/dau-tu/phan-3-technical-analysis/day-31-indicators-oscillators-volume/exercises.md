# Bài tập — Ngày 31: Indicators — Oscillators & Volume

## Phần 1: Câu hỏi ôn tập (Quiz)

**1. RSI được tính dựa trên:**
- A. Giá đóng cửa và giá mở cửa
- B. Trung bình số phiên tăng so với số phiên giảm
- C. Khối lượng giao dịch và biến động giá
- D. Đường MA ngắn và MA dài

**2. Trong một uptrend mạnh, RSI liên tục ở mức 72-78 trong 3 tuần. Bạn nên:**
- A. Bán ngay vì RSI đang overbought
- B. Không làm gì, RSI cao là bình thường trong uptrend mạnh
- C. Mua thêm vì RSI trên 70 có nghĩa là tăng mạnh
- D. Short sell để kiếm lời

**3. Tín hiệu mua từ Stochastic xảy ra khi:**
- A. %K cắt %D từ trên xuống tại vùng overbought (>80)
- B. %K vượt qua ngưỡng 50
- C. %K cắt %D từ dưới lên tại vùng oversold (<20)
- D. %D vượt qua %K

**4. Cổ phiếu X: Giá tăng liên tục 5 phiên, Volume mỗi phiên giảm dần. Điều này cho thấy:**
- A. Uptrend rất mạnh và đáng tin
- B. Cảnh báo — tăng giá thiếu sự xác nhận của dòng tiền
- C. Nên mua thêm ngay
- D. Thị trường đang sideways

**5. OBV (On-Balance Volume) tăng trong khi giá đang đi ngang. Điều này gợi ý:**
- A. Không có tín hiệu gì
- B. Smart money đang tích lũy, giá có thể sẽ tăng
- C. Cần bán ra ngay
- D. Volume không đáng tin cậy

**6. Bullish Regular Divergence xảy ra khi:**
- A. Giá tạo đỉnh cao hơn, RSI tạo đỉnh cao hơn
- B. Giá tạo đáy thấp hơn, RSI tạo đáy cao hơn
- C. Giá tạo đáy cao hơn, RSI tạo đáy thấp hơn
- D. Giá và RSI cùng đi xuống

**7. Breakout với Volume bằng 50% trung bình 20 phiên. Bạn đánh giá thế nào?**
- A. Breakout rất mạnh, mua ngay
- B. Breakout đáng nghi — Volume thấp là dấu hiệu fake breakout
- C. Volume không quan trọng, chỉ cần giá breakout
- D. Đây là tín hiệu bán

**8. Hidden Bullish Divergence cho tín hiệu:**
- A. Đảo chiều từ tăng sang giảm
- B. Tiếp diễn xu hướng tăng
- C. Đảo chiều từ giảm sang tăng
- D. Thị trường sideways

---

## Phần 2: Bài tập thực hành

### Bài tập 1: Đọc RSI và nhận diện tín hiệu

Cho dữ liệu RSI(14) của cổ phiếu VNM trong 10 phiên gần nhất:

```
Phiên:  1    2    3    4    5    6    7    8    9    10
Giá:   85   87   89   88   86   83   81   80   82   85  (nghìn VND)
RSI:   58   62   71   68   61   45   38   31   35   42
```

**Yêu cầu:**
1. Xác định phiên nào RSI chạm vùng overbought/oversold
2. Tín hiệu gì xuất hiện tại phiên 8?
3. Nếu bạn đang nắm giữ VNM từ phiên 1, bạn sẽ làm gì tại phiên 3? Tại phiên 8?

### Bài tập 2: Nhận diện Divergence

Phân tích dữ liệu sau và xác định loại divergence:

**Tình huống A:**
```
Thời gian: T1          T2 (2 tháng sau)
Giá BTC:   $45,000     $52,000     (Higher High)
RSI:       74          68           (Lower High)
```
Đây là loại divergence gì? Tín hiệu gì?

**Tình huống B:**
```
Thời gian: T1          T2 (3 tuần sau)
Giá VHM:   42,000 VND  38,000 VND  (Lower Low)
RSI:       28          34           (Higher Low)
```
Đây là loại divergence gì? Tín hiệu gì?

**Tình huống C:**
```
Thời gian: T1          T2 (1 tuần sau)
Giá EUR/USD: 1.0850    1.0920      (Higher Low trong uptrend)
RSI:         38        32           (Lower Low)
```
Đây là loại divergence gì? Tín hiệu gì?

### Bài tập 3: Phân tích Volume

Cho bảng dữ liệu phiên giao dịch của cổ phiếu FPT:

```
Ngày    | Giá đóng | Volume (triệu CP) | Nhận xét
--------|----------|-------------------|----------
01/10   | 95,000   | 2.1               |
02/10   | 97,000   | 3.5               |
03/10   | 99,500   | 5.8               |
04/10   | 101,000  | 8.2               | ← Breakout kháng cự 100,000
05/10   | 100,500  | 1.9               |
06/10   | 99,000   | 1.5               |
07/10   | 100,000  | 1.2               |
08/10   | 102,500  | 6.7               |
```

Volume trung bình 20 phiên trước = 2.8 triệu CP

**Yêu cầu:**
1. Breakout ngày 04/10 có đáng tin không? Tại sao?
2. Điều chỉnh ngày 05-07/10 nói lên điều gì?
3. Phiên 08/10 có ý nghĩa gì? Bạn sẽ hành động thế nào?

---

## Phần 3: Case Study

### Case Study: Cổ phiếu HPG (Hòa Phát Group) — Phân tích tổng hợp

**Tình huống:** Tháng 9/2023, HPG đang ở giá 27,000 VND. Bạn có dữ liệu sau:

```
Kỹ thuật tổng quan:
- EMA(20) = 26,500 VND (giá đang trên EMA 20)
- EMA(50) = 25,000 VND (EMA 20 > EMA 50 → uptrend)
- RSI(14) = 58 (trung lập nhẹ tích cực)
- Stochastic: %K = 45, %D = 40, đang hướng lên
- Volume 5 phiên gần nhất: 12, 15, 18, 22, 28 triệu CP (tăng dần)
- OBV: đang tăng liên tục 3 tuần
- Không có dấu hiệu divergence

Fundamental (cơ bản):
- P/E = 9.5 (thấp hơn trung bình ngành ~12)
- Doanh thu Q3 tăng 15% YoY
- Ngành thép phục hồi sau giai đoạn khó khăn
```

**Yêu cầu:**
1. Đánh giá từng chỉ báo kỹ thuật: bullish hay bearish?
2. Tổng hợp: tín hiệu tổng thể là gì?
3. Nếu bạn quyết định mua, đặt Stop-loss và Take-profit ở đâu? (Gợi ý: dùng EMA 50 làm tham chiếu)
4. Nếu sau 1 tuần HPG tăng lên 29,500 VND nhưng RSI đạt 72 và Volume giảm dần, bạn sẽ làm gì?

---

## Đáp án & Giải thích

### Quiz

1. **Đáp án: B** — RSI = 100 - [100/(1+RS)] trong đó RS = Trung bình phiên tăng / Trung bình phiên giảm
2. **Đáp án: B** — Trong uptrend mạnh, RSI có thể duy trì trên 70 rất lâu. Bán ngay khi thấy overbought là lỗi phổ biến của người mới
3. **Đáp án: C** — Tín hiệu mua khi %K cắt %D từ dưới lên tại vùng oversold (<20), cho thấy đà bán đã cạn kiệt
4. **Đáp án: B** — Giá tăng cần Volume xác nhận. Volume giảm dần khi giá tăng = cảnh báo uptrend yếu
5. **Đáp án: B** — OBV tăng nghĩa là dòng tiền đang vào (smart money tích lũy), giá thường sẽ tăng theo sau
6. **Đáp án: B** — Bullish Regular Divergence: Giá Lower Low + RSI Higher Low = tín hiệu đảo chiều tăng
7. **Đáp án: B** — Volume thấp hơn trung bình là dấu hiệu breakout không đáng tin, cần thận trọng
8. **Đáp án: B** — Hidden Divergence là tín hiệu tiếp diễn, không phải đảo chiều

### Bài tập 1: Đọc RSI

1. Phiên 3: RSI = 71 (vừa chạm vùng overbought >70). Phiên 8: RSI = 31 (chạm vùng oversold <30 lần đầu)
2. Phiên 8: RSI = 31 → vùng oversold. Kết hợp giá đang điều chỉnh (từ 89 xuống 80), đây là tín hiệu cảnh báo đã oversold
3. Tại phiên 3: Không bán ngay — RSI mới vừa chạm 71 trong một đợt tăng, cần thêm tín hiệu xác nhận (Stochastic, Volume). Tại phiên 8: Đây là vùng xem xét giữ hoặc tìm setup hồi phục, vì RSI oversold trong context uptrend thường là vùng đáng quan sát

### Bài tập 2: Divergence

- **Tình huống A:** Bearish Regular Divergence — Giá Higher High + RSI Lower High → Cảnh báo đảo chiều giảm, cân nhắc chốt lời hoặc đặt stop-loss chặt
- **Tình huống B:** Bullish Regular Divergence — Giá Lower Low + RSI Higher Low → Tín hiệu đảo chiều tăng tiềm năng, tìm điểm mua
- **Tình huống C:** Hidden Bullish Divergence — Giá Higher Low (trong uptrend) + RSI Lower Low → Tín hiệu uptrend có thể tiếp tục, chỉ cân nhắc tăng vị thế nếu Trading Plan cho phép và R:R đạt chuẩn

### Bài tập 3: Volume Analysis

1. **Breakout ngày 04/10:** Đáng tin — Volume 8.2 triệu CP = 2.93× trung bình 20 phiên (>2× là xác nhận mạnh). Breakout qua 100,000 kèm volume cao là tín hiệu đáng tin
2. **Điều chỉnh 05-07/10:** Volume giảm mạnh (1.2-1.9 triệu) khi giá điều chỉnh nhẹ — đây là điều chỉnh lành mạnh, áp lực bán yếu, dòng tiền không thoát khỏi cổ phiếu
3. **Phiên 08/10:** Giá tăng lên 102,500 kèm Volume 6.7 triệu (2.4× trung bình) → Xác nhận breakout là thật. Hành động: Có thể mua/giữ, đặt stop-loss dưới 100,000 (ngưỡng breakout cũ)

### Case Study HPG

1. **Đánh giá từng chỉ báo:**
   - EMA: Bullish (EMA 20 > EMA 50, giá trên EMA)
   - RSI 58: Trung lập nhẹ tích cực (không overbought)
   - Stochastic 45/40 đang hướng lên: Bullish
   - Volume tăng dần: Rất Bullish (dòng tiền đang vào)
   - OBV tăng 3 tuần: Bullish (smart money đang tích lũy)
   - Không có divergence: Không có cảnh báo

2. **Tổng hợp:** Tất cả indicators đều bullish. Đây là setup mua tốt với nhiều xác nhận.

3. **Stop-loss và Take-profit:**
   - Stop-loss: 25,000 VND (dưới EMA 50, nếu thủng thì uptrend vỡ)
   - Risk per trade: 27,000 - 25,000 = 2,000 VND (7.4%)
   - Take-profit: Dùng R:R = 1:2 → Take-profit = 27,000 + (2×2,000) = 31,000 VND
   - Hoặc theo kháng cự gần nhất

4. **Sau 1 tuần:** RSI 72 + Volume giảm = Bearish Divergence tiềm năng + Overbought. Hành động hợp lý: Chốt lời 50-70% vị thế, giữ lại phần còn lại với trailing stop-loss nâng lên 27,500 VND (giá vốn + một ít lợi nhuận bảo vệ). Không bán hết vì xu hướng vẫn còn tốt.
