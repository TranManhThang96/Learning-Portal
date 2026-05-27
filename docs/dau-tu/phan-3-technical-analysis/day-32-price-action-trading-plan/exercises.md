# Bài tập — Ngày 32: Price Action & Trading Plan

## Phần 1: Câu hỏi ôn tập (Quiz)

**1. Price Action Trading khác với dùng Indicators ở điểm nào?**
- A. Price Action dùng nhiều indicators hơn
- B. Price Action đọc biểu đồ giá trực tiếp, không dùng indicators (hoặc dùng rất ít)
- C. Price Action chỉ dùng cho Forex, không dùng cho chứng khoán
- D. Price Action chính xác hơn Indicators trong mọi trường hợp

**2. Pin Bar mạnh nhất khi nào?**
- A. Xuất hiện bất kỳ chỗ nào trên biểu đồ
- B. Xuất hiện tại giữa một xu hướng đang mạnh
- C. Xuất hiện tại vùng hỗ trợ/kháng cự quan trọng với Volume cao
- D. Xuất hiện trên timeframe nhỏ như 1 phút

**3. Inside Bar cho thấy thị trường đang:**
- A. Tăng mạnh không thể dừng
- B. Tích lũy/nén năng lượng trước khi bứt phá
- C. Giảm mạnh
- D. Đang sideways lâu dài

**4. Trong Multi-timeframe Analysis, bạn nên:**
- A. Chỉ dùng một timeframe duy nhất để đơn giản
- B. Dùng tất cả timeframes từ 1 phút đến Monthly
- C. Phân tích từ timeframe lớn xuống nhỏ, giao dịch thuận chiều xu hướng lớn
- D. Chỉ dùng timeframe nhỏ nhất để vào lệnh chính xác nhất

**5. Khi Weekly trend là Bullish nhưng Daily trend là Bearish, bạn nên:**
- A. Mua theo Weekly trend
- B. Bán theo Daily trend
- C. Chờ cho đến khi 2 timeframes đồng thuận
- D. Đảo lệnh liên tục theo từng timeframe

**6. Câu nào đúng về vai trò của Fundamental vs Technical Analysis?**
- A. Fundamental cho biết KHI NÀO mua, Technical cho biết MUA CÁI GÌ
- B. Fundamental cho biết MUA CÁI GÌ, Technical cho biết KHI NÀO mua
- C. Chỉ cần một trong hai là đủ
- D. Hai phương pháp này hoàn toàn mâu thuẫn nhau

**7. Một Trading Plan TỐT bắt buộc phải có:**
- A. Dự đoán giá chính xác
- B. Đảm bảo 100% tỷ lệ thắng
- C. Quy tắc risk management, tiêu chí setup, và Trading Journal
- D. Được viết bởi chuyên gia tài chính có chứng chỉ

**8. "Role Reversal" trong kỹ thuật có nghĩa là:**
- A. Đảo chiều xu hướng hoàn toàn
- B. Kháng cự sau khi bị phá vỡ trở thành hỗ trợ (và ngược lại)
- C. Thay đổi chiến lược giao dịch
- D. Đổi hướng lệnh từ Long sang Short

---

## Phần 2: Bài tập thực hành

### Bài tập 1: Nhận diện mô hình Price Action

Cho mô tả các nến, xác định mô hình PA và ý nghĩa:

**Nến A:**
```
Open:  100,000 VND
High:  100,500 VND  (bóng trên = 500)
Low:   97,000 VND   (bóng dưới = 2,500)
Close: 100,200 VND  (thân = 200)
Bối cảnh: Xuất hiện tại vùng hỗ trợ 97,500 VND đã test 3 lần
```

Đây là mô hình gì? Tín hiệu gì?

**Nến B (2 nến liên tiếp):**
```
Nến 1: Open 95,000 | High 100,000 | Low 94,000 | Close 99,000
Nến 2: Open 97,000 | High 99,500  | Low 95,500  | Close 96,000
```

Đây là mô hình gì? Ý nghĩa?

### Bài tập 2: Phân tích Multi-timeframe

Cho dữ liệu của cổ phiếu MWG (Thế Giới Di Động):

```
Weekly Chart:
- Giá: 52,000 VND (đang trong downtrend rõ ràng)
- EMA 20 > Giá (bearish)
- RSI: 38 (yếu)

Daily Chart:
- Giá: 52,000 VND, vừa test vùng hỗ trợ 50,000-52,000
- Hôm nay xuất hiện Bullish Pin Bar tại 51,500
- RSI: 32 (oversold)
- Volume: 3× trung bình (cao bất thường)

4H Chart:
- Stochastic %K vừa cắt %D từ dưới lên tại vùng 18
- MACD: còn bearish nhưng histogram đang thu hẹp
```

**Yêu cầu:**
1. Phân tích từng timeframe: bullish hay bearish?
2. Có nên vào lệnh long không? Lý do?
3. Nếu vào lệnh, đặt Stop-loss ở đâu? Take-profit ở đâu?
4. Risk là bao nhiêu nếu vốn 100 triệu VND và risk 1%?

### Bài tập 3: Xây dựng Trading Plan cá nhân

Đây là bài tập quan trọng nhất — hãy viết Trading Plan thực sự của bạn:

**Hướng dẫn:**

Sử dụng template trong document.md, điền đầy đủ thông tin. Gợi ý cho người mới:

```
Thị trường: Bắt đầu với chứng khoán VN (quen thuộc, ngôn ngữ dễ tiếp cận)
Timeframe: Daily (không cần ngồi màn hình cả ngày)
Phong cách: Swing Trading (giữ 5-15 ngày)

Setup đề xuất cho người mới:
"Mua cổ phiếu trong uptrend (EMA 20 > EMA 50) khi giá pullback về EMA 50
 và xuất hiện Bullish Pin Bar hoặc Bullish Engulfing, kèm RSI < 55 và Volume
 tăng so với phiên trước"

Quản lý rủi ro đề xuất:
- Risk per trade: 1%
- R:R tối thiểu: 1:2
- Max 3 lệnh cùng lúc
- Stop-loss: Dưới đáy của nến tín hiệu
```

---

## Phần 3: Case Study tổng hợp — Áp dụng toàn bộ kiến thức Phần 3

### Case Study: Phân tích FPT — Từ kỹ thuật đến quyết định

**Bối cảnh:** Tháng 10/2023, bạn đang phân tích cổ phiếu FPT

**Dữ liệu kỹ thuật:**

```
WEEKLY CHART:
- FPT đang trong uptrend rõ ràng từ đầu 2023
- Giá: 95,000 VND, trên tất cả EMA
- RSI Weekly: 61 (bullish zone)

DAILY CHART:
- Giá pullback về EMA 50 (90,000 VND) sau đợt tăng mạnh
- Hôm nay (Thứ 5): Bullish Engulfing tại 90,500 VND
- Volume hôm nay: 4.2 triệu CP (trung bình 20 phiên: 2.8 triệu)
- RSI Daily: 46 (chưa oversold nhưng đã giảm đủ để hấp dẫn)
- OBV: vẫn đang trending lên

4H CHART:
- Stochastic (14,3,3): %K = 22, %D = 18, %K vừa cắt %D từ dưới lên
- MACD: histogram đổi sang dương
- Không có divergence bearish nào

FUNDAMENTAL:
- P/E = 21 (phù hợp với growth stock công nghệ)
- Doanh thu tăng 18% YoY, biên lợi nhuận ổn định
- FPT là công ty CNTT hàng đầu VN, lợi thế cạnh tranh rõ ràng
```

**Yêu cầu phân tích:**

1. **Phân tích kỹ thuật tổng hợp:**
   - Weekly, Daily, 4H đang nói gì?
   - Mô hình PA xuất hiện là gì? Có đủ xác nhận không?

2. **Quyết định giao dịch:**
   - Có vào lệnh không? Tại sao có/không?
   - Nếu có: Entry ở đâu? (Ngay lập tức hay chờ?)

3. **Quản lý lệnh:**
   - Stop-loss: _______ (Lý do?)
   - Take-profit 1 (50% vị thế): _______ (Lý do?)
   - Take-profit 2 (50% còn lại): _______ (Dùng kỹ thuật gì?)
   - R:R của setup này là bao nhiêu?

4. **Scenario analysis:**
   - Nếu ngày mai giá giảm xuống 88,000 VND kèm Volume cao → Hành động?
   - Nếu sau 3 ngày giá tăng lên 97,000 VND kèm Bearish Pin Bar → Hành động?
   - Nếu FPT thông báo kết quả kinh doanh tốt hơn kỳ vọng → Điều chỉnh kế hoạch thế nào?

---

## Đáp án & Giải thích

### Quiz

1. **B** — Price Action đọc trực tiếp biểu đồ giá, không (hoặc ít dùng) indicator
2. **C** — Pin Bar mạnh nhất tại key level với Volume xác nhận
3. **B** — Inside Bar = nén năng lượng trước breakout
4. **C** — Top-down analysis: timeframe lớn → nhỏ, thuận chiều xu hướng lớn
5. **C** — Timeframe conflict = chờ đồng thuận, không vào lệnh
6. **B** — Fundamental: MUA CÁI GÌ; Technical: KHI NÀO mua
7. **C** — Trading Plan tốt có risk management, setup tiêu chí, và journal
8. **B** — Role Reversal: kháng cự phá vỡ → hỗ trợ mới

### Bài tập 1

**Nến A:** Bullish Pin Bar mạnh
- Bóng dưới = 3,000 VND (97,000-100,000) = 85% tổng chiều dài nến
- Thân = 200 VND (nhỏ)
- Xuất hiện tại vùng hỗ trợ đã được test 3 lần → Key Level mạnh
- → **Tín hiệu bullish đáng chú ý**. Nếu đưa vào kế hoạch giao dịch giả định, điểm kích hoạt có thể là trên đỉnh Pin Bar (100,500), SL dưới 96,800 và chỉ thực hiện nếu R:R đạt chuẩn.

**Nến B:** Inside Bar (hoặc xem xét thêm: Harami Pattern)
- Nến 2 hoàn toàn nằm trong phạm vi nến 1 (High 99,500 < 100,000; Low 95,500 > 94,000)
- → **Tín hiệu tích lũy, chờ breakout. Buy Stop tại 99,600, Sell Stop tại 95,400**

### Bài tập 2

1. **Phân tích:**
   - Weekly: Bearish (downtrend, EMA trên giá, RSI yếu)
   - Daily: Tiềm năng đảo chiều (Pin Bar tại S/R, RSI oversold, Volume cao)
   - 4H: Bắt đầu bullish (Stochastic crossover, MACD cải thiện)

2. **Quyết định:** ⚠️ Thận trọng — Có thể vào lệnh nhỏ nhưng biết mình đang "đánh ngược xu hướng lớn". Weekly bearish là rủi ro lớn. Nên giảm size xuống 50% so với thông thường.

3. **Vào lệnh (nếu chấp nhận rủi ro):**
   - Entry: 52,000 (hoặc chờ xác nhận +1 phiên)
   - Stop-loss: 49,500 (dưới đáy Pin Bar, dưới vùng hỗ trợ)
   - Take-profit: 56,000 (kháng cự tiếp theo, R:R = 1:1.6 — hơi thấp)

4. **Risk:**
   - SL = 52,000 - 49,500 = 2,500 VND/CP (4.8%)
   - Risk 1% vốn = 1,000,000 VND
   - Số CP = 1,000,000 / 2,500 = 400 CP
   - Giá trị lệnh = 400 × 52,000 = 20,800,000 VND (20.8% vốn)

### Case Study FPT

1. **Phân tích:** Weekly Bullish + Daily Setup mạnh + 4H xác nhận = Alignment tốt. Bullish Engulfing tại EMA 50 với Volume 1.5× trung bình = tín hiệu đáng tin.

2. **Quyết định:** Có thể đưa vào kế hoạch giao dịch giả định vì các timeframe đồng thuận. Điểm kích hoạt hợp lý là khi giá giữ trên vùng Bullish Engulfing, khoảng 90,500-91,000, với điều kiện R:R và quy mô vị thế đạt chuẩn.

3. **Quản lý:**
   - Stop-loss: 87,500 VND (dưới đáy Bullish Engulfing ~88,000, buffer 500)
   - TP1: 97,000 VND (đỉnh cũ gần nhất, R:R ≈ 1:2)
   - TP2: 103,000 VND (đỉnh cao tiếp theo, trailing stop từ TP1)
   - R:R tổng thể: (90,500 → 87,500 = 3,000 risk) vs (90,500 → 97,000 = 6,500 reward) = 1:2.17 ✓

4. **Scenarios:**
   - Giá giảm 88,000 + Volume cao: Stop-loss kích hoạt bình thường → chấp nhận lỗ, không can thiệp
   - Giá tăng 97,000 + Bearish Pin Bar: Chốt 50-70% tại TP1, giữ lại phần còn lại với trailing SL
   - Kết quả kinh doanh tốt: Nâng Take-profit lên 103,000, giữ lại toàn bộ vị thế, trailing SL lên 93,000
