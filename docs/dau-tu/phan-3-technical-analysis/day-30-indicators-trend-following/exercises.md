# Bài Tập — Ngày 30: Indicators Trend Following

## Phần 1: Câu Hỏi Ôn Tập (Quiz)

**1. EMA khác SMA ở điểm nào?**
   - A. EMA dùng nhiều ngày hơn SMA
   - B. EMA ưu tiên dữ liệu gần đây hơn, phản ứng nhanh hơn
   - C. EMA tính trung bình của giá cao và thấp, SMA chỉ dùng giá đóng
   - D. Không có sự khác biệt thực chất

**2. MA200 thường được coi là:**
   - A. Chỉ báo ngắn hạn cho day trading
   - B. Ranh giới phân chia bull market và bear market dài hạn
   - C. Chỉ dùng cho thị trường Forex
   - D. Kém quan trọng hơn MA20

**3. Golden Cross xảy ra khi:**
   - A. Giá tăng lên all-time high
   - B. MA50 cắt xuống dưới MA200
   - C. MA50 cắt lên trên MA200
   - D. Volume tăng đột biến

**4. MACD được tính từ:**
   - A. Giá cao nhất trừ giá thấp nhất
   - B. EMA12 trừ EMA26
   - C. SMA20 trừ SMA50
   - D. Giá đóng cửa trừ giá mở cửa

**5. MACD Bullish Divergence xảy ra khi:**
   - A. Giá tạo đỉnh cao hơn, MACD tạo đỉnh cao hơn
   - B. Giá tạo đáy thấp hơn (LL), nhưng MACD tạo đáy cao hơn (HL)
   - C. MACD cắt lên trên Signal Line
   - D. Histogram chuyển từ đỏ sang xanh

**6. Bollinger Squeeze cho thấy điều gì?**
   - A. Giá đang quá mua
   - B. Biến động thấp, sắp có breakout lớn nhưng chưa biết hướng
   - C. Xu hướng tăng đang mạnh
   - D. Nên bán ngay

**7. Khi giá đang "cưỡi" Upper Bollinger Band trong uptrend mạnh, bạn nên:**
   - A. Bán ngay vì giá đã quá cao
   - B. Không short vội; có thể tiếp tục theo dõi/giữ theo kế hoạch vì đây là dấu hiệu uptrend mạnh
   - C. Chờ giá về Middle Band rồi mua
   - D. Đặt Stop-loss rất chặt

**8. Tín hiệu MACD MẠNH NHẤT là:**
   - A. Crossover ngay tại Zero Line
   - B. Bullish/Bearish Divergence
   - C. Histogram to nhất
   - D. Signal Line nằm dưới MACD Line

**9. Kết hợp nào hiệu quả nhất khi sử dụng MA?**
   - A. Dùng càng nhiều MA càng tốt (MA5, MA10, MA20, MA50, MA100, MA200)
   - B. MA + S/R + Candlestick pattern + Volume
   - C. Chỉ cần MA, không cần gì khác
   - D. MA + tin tức

**10. Indicators là "lagging" (trễ) có nghĩa là:**
    - A. Indicators không chính xác và vô dụng
    - B. Indicators tính toán từ dữ liệu quá khứ nên tín hiệu xuất hiện sau khi xu hướng bắt đầu
    - C. Cần đợi lâu mới thấy tín hiệu
    - D. Chỉ dùng được cho giao dịch dài hạn

---

## Phần 2: Bài Tập Tính Toán

### Bài Tập 1: Tính SMA và EMA

Cho giá đóng cửa 10 ngày của một cổ phiếu (đơn vị: 1,000 VND):
```
Ngày 1: 100
Ngày 2: 102
Ngày 3: 98
Ngày 4: 104
Ngày 5: 106
Ngày 6: 103
Ngày 7: 108
Ngày 8: 110
Ngày 9: 107
Ngày 10: 112
```

**Câu hỏi:**
1. Tính SMA(5) cho ngày 5 và ngày 10.
2. Giá đóng cửa ngày 10 (112k) so với SMA(5) ngày 10 như thế nào? Xu hướng gì?
3. Nếu SMA(5) ngày 9 là 106.8k và SMA(10) ngày 10 là 105k, giá so với cả hai MA như thế nào? Đây là tín hiệu gì?

---

### Bài Tập 2: Đọc Tín Hiệu MACD

Cho dữ liệu MACD của cổ phiếu TCB (Techcombank) trong 2 tháng:

```
Tháng 1 (Giá giảm từ 35k → 28k):
- MACD Line: Âm và ngày càng âm hơn (-0.3 → -0.8 → -1.2)
- Signal Line: Âm, bám sát MACD
- Histogram: Đỏ và tăng (âm hơn)

Giữa tháng 2 (Giá tiếp tục giảm từ 28k → 25k):
- MACD Line: -1.5 → -1.3 → -1.0 (ít âm hơn dù giá vẫn giảm!)
- Signal Line: Vẫn -1.4
- Histogram: Đỏ nhưng đang thu hẹp

Cuối tháng 2:
- MACD Line (-0.8) cắt lên trên Signal Line (-1.0)
- Histogram chuyển xanh nhỏ
```

**Câu hỏi:**
1. Giữa tháng 2: Giá giảm nhưng MACD tăng lên (ít âm hơn). Đây là tín hiệu gì?
2. Cuối tháng 2: MACD crossover bullish ở vùng âm. Đây là tín hiệu gì? Mạnh hay yếu?
3. Nếu bạn muốn mua TCB dựa trên tín hiệu này, bạn cần thêm điều kiện gì?
4. Đặt Stop-loss ở đâu?

---

### Bài Tập 3: Bollinger Bands

Cổ phiếu HPG trong 3 giai đoạn:

**Giai đoạn 1 (Tháng 1):** BB rộng, giá cưỡi Upper Band liên tục
**Giai đoạn 2 (Tháng 2):** BB thu hẹp dần, giá đi ngang trong 3 tuần
**Giai đoạn 3 (Tháng 3):** BB bắt đầu mở rộng, giá vọt lên phá Upper Band với volume 3x

**Câu hỏi:**
1. Mô tả tình trạng thị trường ở từng giai đoạn.
2. Giai đoạn 2 là tín hiệu gì?
3. Giai đoạn 3: Đây là Breakout thật hay giả? Tại sao?
4. Nếu mua sau khi giá đóng cửa trên Upper Band (giai đoạn 3), đặt Stop-loss ở đâu?

---

## Phần 3: Case Study — Bitcoin 2020-2021

Bitcoin trong giai đoạn phục hồi hậu COVID:

```
Tháng 4/2020: BTC ~ $7,000
- MA50 ở trên MA200 (Death Cross đã xảy ra trước đó)
- MACD: Âm nhưng đang tăng dần

Tháng 7/2020: BTC ~ $10,000
- MA50 bắt đầu cắt lên MA200 (Golden Cross!)
- MACD: Vừa cắt lên Signal Line, histogram xanh nhỏ

Tháng 10/2020: BTC ~ $12,000
- Giá trên cả MA50 và MA200
- MACD: Dương, histogram xanh lớn dần
- BB: Bắt đầu giãn rộng

Tháng 12/2020: BTC ~ $29,000
- Giá cưỡi Upper BB liên tục
- MACD: Histogram rất lớn
- MA50 >> MA200
```

**Phân tích:**
1. Tháng 7/2020, Golden Cross xuất hiện. Nhà đầu tư dài hạn nên làm gì?
2. Tháng 10/2020, kết hợp MA + MACD + BB cho tín hiệu gì?
3. Tháng 12/2020 giá cưỡi Upper BB — đây là tín hiệu gì? Có nên bán không?
4. Bài học về việc "don't fight the trend" khi indicators đồng thuận?
5. Thực tế BTC đạt $69,000 năm 2021. Indicators lagging có giúp được gì trong việc bắt kịp xu hướng này không?

---

## Đáp Án & Giải Thích

### Quiz
1. **B** — EMA ưu tiên dữ liệu gần, phản ứng nhanh hơn
2. **B** — MA200 = ranh giới bull/bear market dài hạn
3. **C** — Golden Cross: MA50 cắt lên trên MA200
4. **B** — MACD = EMA12 − EMA26
5. **B** — Bullish Divergence: Giá LL, MACD HL (không đồng bộ)
6. **B** — BB Squeeze = biến động thấp, sắp breakout
7. **B** — Giá cưỡi Upper BB trong uptrend mạnh → KHÔNG short
8. **B** — Divergence là tín hiệu cảnh báo sớm và mạnh nhất
9. **B** — MA tốt nhất khi kết hợp với S/R + nến + volume
10. **B** — Lagging = tính từ quá khứ → tín hiệu trễ so với giá

### Bài Tập 1: Tính MA

1. **SMA(5) ngày 5:** (100+102+98+104+106)/5 = 510/5 = **102k**
   **SMA(5) ngày 10:** (103+108+110+107+112)/5 = 540/5 = **108k**

2. Giá ngày 10 (112k) > SMA(5) ngày 10 (108k) → **Giá trên MA → Tín hiệu tích cực (uptrend)**

3. Giá 112k > SMA(5) = 108k > SMA(10) = 105k
   → Giá trên cả hai MA, MA ngắn hạn trên MA dài hạn
   → **Xếp MA lý tưởng: Bullish alignment** → Xu hướng tăng được xác nhận tốt

### Bài Tập 2: MACD TCB

1. **Giữa tháng 2 — MACD Bullish Divergence:**
   - Giá giảm (LL): 28k → 25k
   - MACD tăng (HL): -1.5 → -1.3 → -1.0
   → Đây là **Bullish Divergence** — Momentum downtrend đang yếu dần, sắp đảo chiều

2. **Cuối tháng 2 — MACD Crossover ở vùng âm:**
   - MACD cắt lên Signal ở vùng dưới zero → **Tín hiệu mua RẤT MẠNH**
   - Điều kiện tốt nhất: MACD crossover xảy ra SAU divergence

3. **Điều kiện thêm trước khi mua:**
   - Nến xanh xác nhận (Hammer, Bullish Engulfing...)
   - Volume tăng khi giá bounces
   - Kiểm tra hỗ trợ gần: Giá 25k có phải vùng hỗ trợ quan trọng không?

4. **Stop-loss:** Dưới đáy thấp nhất vừa tạo (25k) → ~24,200-24,500k

### Bài Tập 3: Bollinger Bands HPG

1. **Giai đoạn 1:** BB rộng + giá cưỡi Upper → **Uptrend rất mạnh, bulls kiểm soát**
   **Giai đoạn 2:** BB hẹp + giá đi ngang → **Consolidation/Squeeze — tích lũy năng lượng**
   **Giai đoạn 3:** BB mở rộng + breakout → **Biến động mạnh, bulls breakout**

2. **Giai đoạn 2:** BB Squeeze = **cảnh báo breakout lớn sắp đến**. Chưa biết hướng, cần theo dõi thêm pattern và tin tức.

3. **Giai đoạn 3: Breakout thật** vì:
   - Volume 3x trung bình ✅ (xác nhận mạnh)
   - BB đang mở rộng (không phải fake) ✅
   - Giá đóng cửa trên Upper Band ✅

4. **Stop-loss:** Dưới Middle Band (MA20) hoặc dưới Upper Band cũ (vùng breakout) → tùy aggressive/conservative

### Case Study: Bitcoin 2020-2021

1. **Tháng 7/2020 — Golden Cross:** Đây là tín hiệu bullish dài hạn có thể đưa vào kế hoạch giao dịch giả định. Entry quanh $10,000 chỉ là ví dụ backtest; Stop-loss dưới MA200 (~$8,500).

2. **Tháng 10/2020 — MA + MACD + BB đồng thuận:**
   - MA: Giá trên cả MA50 và MA200 ✅
   - MACD: Histogram xanh và tăng ✅
   - BB: Đang giãn = biến động đang tăng ✅
   → **3 yếu tố đồng thuận** = Tín hiệu mua rất mạnh

3. **Tháng 12/2020 — Giá cưỡi Upper BB:**
   - Đây là dấu hiệu **uptrend rất mạnh**, KHÔNG phải tín hiệu bán
   - Người bán non ở $29,000 đã bỏ lỡ $40,000 sau đó

4. **"Don't fight the trend":** Khi tất cả indicators đồng thuận, tin vào chúng. Đừng cố đoán đỉnh/đáy — trend có thể kéo dài lâu hơn bạn nghĩ.

5. **Indicators lagging và xu hướng BTC:**
   - **Có** — Dù lagging, indicators đã giúp nhà đầu tư:
     - Không bỏ lỡ Golden Cross tháng 7 ($10k)
     - Giữ vững position khi giá cưỡi Upper BB
     - Không hoảng loạn bán khi có pullback (MA vẫn dốc lên)
   - Bài học: Lagging không có nghĩa là vô dụng — nó giúp bạn **theo trend, không đoán trend**
