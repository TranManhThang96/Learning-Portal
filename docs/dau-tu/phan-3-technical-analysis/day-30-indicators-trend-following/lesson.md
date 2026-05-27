# Ngày 30: Indicators Trend Following — MA, MACD, Bollinger Bands

## Mục tiêu học tập
- [ ] Hiểu Moving Average (SMA, EMA) và cách sử dụng làm hỗ trợ/kháng cự động
- [ ] Hiểu MACD và cách đọc tín hiệu giao cắt và phân kỳ
- [ ] Hiểu Bollinger Bands và cách xác định biến động, breakout
- [ ] Biết kết hợp các indicators với nhau một cách hợp lý

---

## Nội dung bài giảng

### 1. Indicators Là Gì? Tại Sao Cần?

**Technical Indicator (chỉ báo kỹ thuật)** là những công cụ toán học được tính toán dựa trên dữ liệu giá và/hoặc volume, hiển thị dưới dạng đường, cột, hay vùng trên biểu đồ.

**Tại sao cần Indicators?**
- Nến và chart patterns phụ thuộc nhiều vào "nhìn" chủ quan
- Indicators cung cấp **tín hiệu khách quan, có thể đo lường**
- Giúp **xác nhận** xu hướng và tín hiệu từ nến/patterns

**Nhưng hãy nhớ:** Indicators là **lagging** (trễ) — chúng tính toán dựa trên dữ liệu quá khứ. Chúng **không dự đoán tương lai** mà **xác nhận xu hướng hiện tại**.

**Hai loại indicators chính:**
1. **Trend Following (Theo xu hướng):** MA, MACD, Bollinger Bands — Ngày 30
2. **Oscillators (Dao động):** RSI, Stochastic — Ngày 31

**Quy tắc vàng:** Không dùng quá 3 indicators. Nhiều indicators = nhiều tín hiệu mâu thuẫn = confusion.

---

### 2. Moving Average (MA) — Đường Trung Bình Động

#### 2.1. SMA (Simple Moving Average — Trung Bình Động Giản Đơn)

**Công thức:**
```
SMA(n) = (C1 + C2 + ... + Cn) / n

Trong đó: C = giá đóng cửa, n = số ngày
```

**Ví dụ SMA(5):**
```
Ngày 1: 50k | Ngày 2: 52k | Ngày 3: 51k | Ngày 4: 53k | Ngày 5: 54k
SMA(5) = (50 + 52 + 51 + 53 + 54) / 5 = 260 / 5 = 52,000 VND
```

**Đặc điểm SMA:**
- Trọng số bằng nhau cho mọi ngày → phản ứng chậm hơn
- Ít bị "giật" bởi một ngày giá biến động mạnh
- Thường dùng: SMA20, SMA50, SMA200

#### 2.2. EMA (Exponential Moving Average — Trung Bình Động Hàm Mũ)

EMA **ưu tiên dữ liệu gần nhất** hơn — phản ứng nhanh hơn SMA.

**Công thức:**
```
Multiplier = 2 / (n + 1)
EMA(hôm nay) = Close × Multiplier + EMA(hôm qua) × (1 - Multiplier)
```

EMA12: Multiplier = 2/(12+1) = 0.154 → phản ứng nhanh
EMA26: Multiplier = 2/(26+1) = 0.074 → phản ứng chậm hơn

**SMA vs EMA:**
| | SMA | EMA |
|--|-----|-----|
| Phản ứng | Chậm | Nhanh hơn |
| Nhiễu | Ít | Nhiều hơn |
| Tín hiệu giả | Ít | Nhiều hơn |
| Thích hợp | Dài hạn | Ngắn-trung hạn |

---

#### 2.3. Cách Sử Dụng Moving Average

**Cách 1: MA làm Support/Resistance động**

MA không phải đường cứng như S/R thông thường, mà là **vùng hỗ trợ/kháng cự di chuyển**:

```
                 MA20 (đường xanh)
    *   *   *  /
   * \ * \ * /
  *   *   */           ← Giá pullback về MA20, bounces lên
      ────────── MA20
```

**Quy tắc:**
- Giá **trên** MA → xu hướng tăng, MA là hỗ trợ
- Giá **dưới** MA → xu hướng giảm, MA là kháng cự
- Khi giá pullback về MA và bounces → **vùng xem xét setup bullish** trong uptrend

**Các MA thông dụng:**
- **MA20** (20 ngày): Xu hướng ngắn hạn (khoảng 1 tháng)
- **MA50** (50 ngày): Xu hướng trung hạn (khoảng 2.5 tháng)
- **MA200** (200 ngày): Xu hướng dài hạn (khoảng 1 năm) — **MA quan trọng nhất**

**Ví dụ thực tế:**
```
Nhà đầu tư theo dõi FPT trên biểu đồ ngày:
- Giá ở trên MA200 → Xu hướng dài hạn là tăng
- Giá pullback về MA50 và xuất hiện nến Hammer → setup bullish cần kiểm tra thêm volume, R:R và Stop-loss
- Stop-loss: Dưới MA50 hoặc dưới đáy Hammer
```

---

**Cách 2: Golden Cross & Death Cross**

**Golden Cross (Giao Cắt Vàng):**
```
MA50 cắt lên trên MA200
         ↗ MA50
────────
        ────────── MA200
```
→ **Tín hiệu bullish dài hạn** — xu hướng dài hạn có thể chuyển thành tăng

**Death Cross (Giao Cắt Chết):**
```
        ────────── MA200
────────
         ↘ MA50
```
→ **Tín hiệu bán mạnh** — xu hướng dài hạn chuyển thành giảm

**Ứng dụng thực tế:**
```
VN-Index 2020:
- Death Cross: MA50 cắt xuống dưới MA200 tháng 4/2020 (xác nhận downtrend COVID)
- Golden Cross: MA50 cắt lên trên MA200 tháng 7/2020 (xác nhận phục hồi)
→ Nhà đầu tư theo Golden Cross mua tháng 7/2020 ở ~850 điểm 
  và nắm giữ đến khi Death Cross tháng 5/2022 ở ~1,400 điểm
  → Lợi nhuận ~65%
```

**Hạn chế:** Golden/Death Cross là **tín hiệu rất trễ** — thường xảy ra sau khi xu hướng đã chạy được một đoạn. Dùng tốt nhất cho trading dài hạn, không phù hợp short-term.

---

### 3. MACD (Moving Average Convergence Divergence)

**MACD** được phát triển bởi Gerald Appel vào những năm 1970. Đây là một trong những indicators phổ biến nhất thế giới.

#### 3.1. Cấu Tạo MACD

MACD gồm 3 thành phần:

```
MACD Line = EMA12 − EMA26
Signal Line = EMA9 của MACD Line
Histogram = MACD Line − Signal Line
```

**Hiển thị trên biểu đồ:**
```
    MACD Line (xanh)
    Signal Line (đỏ/cam)
    |||||||||||||||||||   ← Histogram (cột xanh/đỏ)
    ───────────────────   ← Zero Line
    |||||||||||||||||||
```

**Ý nghĩa:**
- **MACD > 0:** EMA12 > EMA26 → Xu hướng tăng
- **MACD < 0:** EMA12 < EMA26 → Xu hướng giảm
- **Histogram to (xanh):** Momentum tăng mạnh
- **Histogram thu hẹp:** Momentum đang yếu đi

---

#### 3.2. Tín Hiệu MACD

**Tín hiệu 1: MACD Crossover (Giao cắt MACD)**

```
Bullish: MACD Line cắt lên trên Signal Line (histogram chuyển từ đỏ → xanh)
Bearish: MACD Line cắt xuống dưới Signal Line (histogram chuyển từ xanh → đỏ)
```

**Ví dụ:**
- MACD cắt lên Signal Line ở vùng âm (dưới zero) → **Tín hiệu bullish đáng chú ý**
- MACD cắt lên Signal Line ở vùng dương (trên zero) → Tín hiệu bullish, nhưng thường kém hấp dẫn hơn vì giá có thể đã chạy một đoạn

**Tín hiệu 2: Zero Line Cross**
- MACD Line cắt lên trên Zero Line → Momentum chuyển tích cực
- MACD Line cắt xuống dưới Zero Line → Momentum chuyển tiêu cực

---

**Tín hiệu 3: MACD Divergence (Phân Kỳ MACD) — Tín Hiệu Mạnh Nhất**

**Bullish Divergence (Phân kỳ tăng):**
```
Giá:  Đáy thấp hơn    (LL)
MACD: Đáy cao hơn     (HL)
              ↗
Giá  ↘              ← Không đồng bộ → Bulls đang tích lũy
MACD   ↗
```

Giá tạo đáy mới thấp hơn, nhưng MACD lại tạo đáy cao hơn. **Momentum không xác nhận giá** → Giá có thể đang chuẩn bị đảo chiều tăng, nhưng vẫn cần nến xác nhận và vùng hỗ trợ rõ ràng.

**Bearish Divergence (Phân kỳ giảm):**
```
Giá:  Đỉnh cao hơn   (HH)
MACD: Đỉnh thấp hơn  (LH)
```
Giá tạo đỉnh mới cao hơn, nhưng MACD tạo đỉnh thấp hơn. **Momentum đang yếu** → Giá có thể chuẩn bị đảo chiều giảm, nhưng không nên xem đây là tín hiệu bán độc lập.

**Đây là tín hiệu cảnh báo sớm** — xuất hiện trước khi giá đảo chiều thực sự.

---

### 4. Bollinger Bands (Dải Bollinger)

Được phát triển bởi John Bollinger, **Bollinger Bands (BB)** là 3 đường bao quanh giá dựa trên độ lệch chuẩn.

#### 4.1. Cấu Tạo

```
Upper Band (Dải trên) = MA20 + 2 × Standard Deviation
Middle Band = MA20 (Simple Moving Average 20 ngày)
Lower Band (Dải dưới) = MA20 − 2 × Standard Deviation
```

**Trên biểu đồ:**
```
─────────────────────  ← Upper Band
        ╭───╮
───────╯     ╰────────  ← Middle Band (MA20)
        ╭───╮
─────────────────────  ← Lower Band
```

**Đặc điểm quan trọng:**
- ~95% thời gian, giá **nằm trong** hai dải
- Khi giá chạm dải trên → có thể đang overbought
- Khi giá chạm dải dưới → có thể đang oversold

---

#### 4.2. Cách Sử Dụng Bollinger Bands

**Cách 1: Bollinger Squeeze (Siết) → Báo hiệu Breakout**

```
Trước squeeze:         Sau squeeze:
───────────────         ────────────────────────────────────
  ─────────────                         ↗
    ───────────          ────────────────  ← Giải phóng
  ─────────────
───────────────
(Dải hẹp dần)          (Breakout mạnh khi dải giãn ra)
```

Khi hai dải thu hẹp lại → **Biến động thấp, năng lượng tích tụ** → Sắp có biến động lớn. Nhưng **không biết hướng breakout**. Kết hợp với pattern hoặc volume để xác định hướng.

**Cách 2: Riding the Bands (Cưỡi Dải)**

Trong uptrend mạnh, giá liên tục "cưỡi" dọc theo Upper Band:
```
     ────────────────  ← Upper Band
   */*/*/*/*/*/*/*/    ← Giá cưỡi upper band
─────────────────────  ← Middle Band
─────────────────────  ← Lower Band
```
→ Đây là uptrend rất mạnh. **Không nên short** chỉ vì giá chạm Upper Band.

**Cách 3: Mean Reversion (Trở Về Trung Bình)**

Trong sideway market, giá có xu hướng quay về Middle Band sau khi chạm Upper/Lower:
- Chạm Lower Band → Cân nhắc kịch bản hồi về trung bình nếu có xác nhận
- Chạm Upper Band → Cân nhắc chốt lời/đảo chiều nếu bối cảnh sideway rõ ràng

**Lưu ý quan trọng:** Cách 3 chỉ hiệu quả trong sideway. Trong trending market, giá có thể dính ở Upper/Lower Band mà không quay về.

---

#### 4.3. %B Và Bandwidth

**%B:** Vị trí giá trong dải Bollinger
```
%B = (Close - Lower Band) / (Upper Band - Lower Band)
- %B = 1 → Giá tại Upper Band
- %B = 0.5 → Giá tại Middle Band
- %B = 0 → Giá tại Lower Band
- %B > 1 → Giá trên Upper Band (rất overbought)
- %B < 0 → Giá dưới Lower Band (rất oversold)
```

**Bandwidth:** Độ rộng của dải
```
Bandwidth = (Upper - Lower) / Middle × 100
```
- Bandwidth thấp → Squeeze → Sắp breakout

---

### 5. Kết Hợp MA + MACD + Bollinger Bands

Không nên dùng cả ba cùng lúc — **chọn 1-2 indicators phù hợp** với phong cách của bạn.

**Setup phổ biến cho swing trader:**
```
1. MA20 và MA50 (xác định trend)
2. MACD (xác nhận momentum và tín hiệu crossover)
3. Kết hợp với Support/Resistance và Candlestick patterns
```

**Ví dụ trade hoàn chỉnh:**
```
Cổ phiếu VHM (Vinhomes):
- Trend: Giá trên MA50 → Uptrend
- MACD: MACD vừa cắt lên Signal Line (tín hiệu bullish)
- Giá: Pullback về MA20 và xuất hiện nến Hammer
- Volume: Tăng nhẹ

→ 3 yếu tố đồng thuận: Trend + MACD + Nến
→ Vào lệnh mua, Stop dưới MA20, Target vùng kháng cự gần nhất
```

**Quy tắc xác nhận:**
- Ít nhất **2 trong 3 indicators** cùng cho tín hiệu
- Tín hiệu từ **timeframe lớn hơn** có ưu tiên cao hơn

---

### 6. Hạn Chế Của Indicators

**Indicators là lagging — không phải magic:**
- Tất cả indicators đều tính toán từ dữ liệu quá khứ
- Trong sideways market, indicators trend-following cho **rất nhiều tín hiệu giả**
- Không có indicator nào đúng 100%

**Indicator Overfitting:**
Nhiều trader tìm indicator "hoàn hảo" bằng cách thêm ngày càng nhiều indicators → biểu đồ đầy đường → confusion. **Less is more.**

**Giải pháp:**
- Dùng indicators để **xác nhận**, không phải để **quyết định**
- Kết hợp với Price Action (hành động giá) cơ bản
- Hiểu bối cảnh thị trường: trending hay sideways?
- Backtest (kiểm tra lịch sử) từng bộ quy tắc trước khi dùng tiền thật: ít nhất 50-100 tín hiệu, tính win rate, R:R, drawdown và phí giao dịch
- Tránh overfitting (tối ưu quá khớp dữ liệu quá khứ): một chiến lược chỉ đẹp trên chart cũ nhưng thất bại khi forward test không phải chiến lược bền vững

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **MA làm hỗ trợ/kháng cự động** — giá pullback về MA trong uptrend là vùng quan sát setup bullish.
2. **Golden Cross / Death Cross** = tín hiệu dài hạn trễ nhưng mạnh khi xảy ra.
3. **MACD Divergence** = tín hiệu cảnh báo sớm trước khi đảo chiều — học thuộc.
4. **Bollinger Squeeze** = báo hiệu breakout mạnh sắp xảy ra.
5. **Kết hợp 2-3 yếu tố** (trend + indicator + nến/pattern) cho tín hiệu đáng tin nhất.
6. **Indicators là lagging** — xác nhận xu hướng, không dự đoán tương lai.

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|--------------------|-------------------|-----------------|
| Moving Average (MA) | Đường trung bình động | Trung bình giá của n ngày gần nhất |
| SMA | TB động giản đơn | Trọng số bằng nhau |
| EMA | TB động hàm mũ | Ưu tiên dữ liệu gần nhất |
| Golden Cross | Giao cắt vàng | MA ngắn hạn cắt lên MA dài hạn |
| Death Cross | Giao cắt chết | MA ngắn hạn cắt xuống MA dài hạn |
| MACD | Hội tụ/Phân kỳ MACD | EMA12 − EMA26 |
| Signal Line | Đường tín hiệu | EMA9 của MACD |
| Histogram | Biểu đồ cột | MACD − Signal |
| MACD Divergence | Phân kỳ MACD | Giá và MACD không đồng bộ |
| Bollinger Bands | Dải Bollinger | MA20 ± 2 độ lệch chuẩn |
| Squeeze | Siết/Thu hẹp | Dải BB hẹp lại, sắp breakout |
| Lagging Indicator | Chỉ báo trễ | Tín hiệu sau khi xu hướng đã bắt đầu |
| Overbought | Quá mua | Giá tăng quá mạnh, có thể điều chỉnh |
| Oversold | Quá bán | Giá giảm quá mạnh, có thể phục hồi |

---

## Bài học tiếp theo

**Ngày 31** sẽ học về **Oscillators và Volume Analysis** — RSI, Stochastic, và On-Balance Volume (OBV). Đây là nhóm indicators đo "sức mạnh" và "cường độ" của xu hướng, bổ sung hoàn hảo cho các trend-following indicators hôm nay. Bạn cũng sẽ hiểu sâu hơn về **Divergence** — một trong những tín hiệu mạnh nhất trong phân tích kỹ thuật.
