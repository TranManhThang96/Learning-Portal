# Ngày 31: Indicators — Oscillators & Volume Analysis

## Mục tiêu học tập
- [ ] Hiểu và sử dụng được RSI (Relative Strength Index) để xác định vùng quá mua/quá bán
- [ ] Áp dụng Stochastic Oscillator kết hợp với RSI để tăng độ chính xác tín hiệu
- [ ] Phân tích Volume để xác nhận xu hướng và tín hiệu đảo chiều
- [ ] Sử dụng OBV (On-Balance Volume) để theo dõi dòng tiền thông minh
- [ ] Nhận biết Divergence (phân kỳ) — một trong những tín hiệu mạnh nhất trong phân tích kỹ thuật

---

## Nội dung bài giảng

### 1. Nhìn lại bức tranh toàn cảnh

Ở Ngày 30, chúng ta đã học các chỉ báo theo xu hướng (Trend Following): Moving Average, MACD, Bollinger Bands. Những chỉ báo này rất tốt khi thị trường đang trending rõ ràng, nhưng lại hay đưa ra tín hiệu giả trong giai đoạn sideways.

Hôm nay chúng ta học nhóm chỉ báo thứ hai: **Oscillators** (chỉ báo dao động) và **Volume Analysis** (phân tích khối lượng). Chúng bổ sung hoàn hảo cho nhóm đầu:

```
Trend Following Indicators → Cho biết HƯỚNG đi
Oscillators               → Cho biết ĐỘNG LỰC (momentum) và timing vào lệnh
Volume Analysis           → Xác nhận tín hiệu và theo dõi dòng tiền
```

---

### 2. RSI — Relative Strength Index (Chỉ số sức mạnh tương đối)

#### 2.1 RSI là gì?

RSI được J. Welles Wilder phát triển năm 1978, đo lường **tốc độ và độ lớn của biến động giá** trong một khoảng thời gian nhất định. RSI dao động từ 0 đến 100.

**Công thức cơ bản:**
```
RSI = 100 - [100 / (1 + RS)]
RS = Trung bình số phiên tăng / Trung bình số phiên giảm
```

Mặc định: RSI(14) — tính trên 14 phiên gần nhất.

#### 2.2 Cách đọc RSI

```
RSI > 70  → Overbought (quá mua) → Cảnh báo đảo chiều giảm
RSI < 30  → Oversold (quá bán)  → Cảnh báo đảo chiều tăng
RSI = 50  → Ngưỡng trung lập, phân chia bull/bear
```

**Biểu đồ RSI minh họa:**
```
100 |
 70 |------------------------------------  ← Vùng Overbought
    |         /‾‾\          /‾\
 50 |--------/----\--------/---\--------  ← Đường trung lập
    |              \      /
 30 |---------------\----/---------------  ← Vùng Oversold
    |                \__/
  0 |
```

**Ví dụ thực tế:** Cổ phiếu FPT tháng 11/2023: RSI chạm 72, sau đó giá điều chỉnh 8% trong 2 tuần trước khi tiếp tục tăng. Đây là ví dụ về việc chờ pullback giúp có vùng phân tích tốt hơn thay vì đuổi theo khi RSI đã cao.

#### 2.3 Cách dùng RSI hiệu quả

**Không chỉ dùng RSI đơn độc!** RSI > 70 không có nghĩa là bán ngay — trong uptrend mạnh, RSI có thể duy trì trên 70 hàng tuần. Tương tự, RSI < 30 trong downtrend mạnh có thể tiếp tục xuống.

**Quy tắc thực hành:**
- Trong **uptrend**: RSI vùng 40-50 là vùng xem xét setup bullish (không chờ xuống 30)
- Trong **downtrend**: RSI vùng 50-60 là vùng xem xét setup bearish (không chờ lên 70)
- Trong **sideways**: RSI gần 30/70 là vùng xem xét giao dịch hồi về trung bình, không phải tín hiệu tự động

---

### 3. Stochastic Oscillator (Chỉ báo ngẫu nhiên)

#### 3.1 Nguyên lý hoạt động

Stochastic được George Lane phát triển vào những năm 1950. Ý tưởng cốt lõi: **trong uptrend, giá đóng cửa có xu hướng gần với mức cao nhất; trong downtrend, giá đóng cửa có xu hướng gần với mức thấp nhất.**

Stochastic đo lường vị trí của giá đóng cửa hiện tại so với vùng giá cao-thấp trong N phiên vừa qua.

```
%K = [(Close - Lowest Low) / (Highest High - Lowest Low)] × 100
%D = Moving Average 3 phiên của %K
```

#### 3.2 Cách đọc Stochastic

```
> 80  → Overbought
< 20  → Oversold
```

**Tín hiệu giao cắt:** Khi %K cắt %D từ dưới lên tại vùng oversold (<20) → tín hiệu bullish. Khi %K cắt %D từ trên xuống tại vùng overbought (>80) → tín hiệu bearish.

```
Stochastic Chart:
100 |
 80 |------------------------------------  ← Overbought
    |     /‾\    /‾\
    |    /   \  /   \   %K (nhanh hơn)
    |---/-----\/-----\-------------------
    |  /       \      \  %D (chậm hơn)
 20 | /         \______\-----------------  ← Oversold
    |
  0 |
       ↑ Tín hiệu bullish khi %K cắt %D từ dưới lên ở vùng oversold
```

#### 3.3 RSI vs Stochastic — Khi nào dùng cái nào?

| Tiêu chí | RSI | Stochastic |
|----------|-----|------------|
| Phản ứng | Chậm hơn, ổn định hơn | Nhanh hơn, nhạy cảm hơn |
| Phù hợp | Trending market | Sideways/ranging market |
| Tín hiệu giả | Ít hơn | Nhiều hơn |
| Ứng dụng | Xác định xu hướng dài hạn | Timing vào/ra lệnh ngắn hạn |

**Best practice:** Dùng RSI xác nhận xu hướng, dùng Stochastic tìm điểm vào lệnh.

---

### 4. Volume Analysis (Phân tích khối lượng giao dịch)

#### 4.1 Tại sao Volume quan trọng?

Volume (khối lượng giao dịch) là **số lượng cổ phiếu/hợp đồng được mua bán trong một phiên**. Giá cho biết "đi đâu", Volume cho biết "đi có thuyết phục không".

Câu nói kinh điển trong kỹ thuật: **"Price is what you pay, Volume is what confirms."**

#### 4.2 Các nguyên tắc Volume cơ bản

**Nguyên tắc 1: Volume xác nhận xu hướng**
```
Giá tăng + Volume tăng  → Uptrend MẠNH và đáng tin cậy ✓
Giá tăng + Volume giảm  → Uptrend YẾU, cảnh báo đảo chiều ⚠️
Giá giảm + Volume tăng  → Downtrend MẠNH ✗
Giá giảm + Volume giảm  → Downtrend YẾU, có thể đảo chiều sắp tới ↑
```

**Nguyên tắc 2: Volume xác nhận Breakout**

Breakout (phá vỡ kháng cự) có Volume cao → Tín hiệu mạnh, khả năng tiếp diễn cao
Breakout với Volume thấp → Tín hiệu yếu, nguy cơ "fake breakout" cao

```
Biểu đồ giá + Volume:
         Breakout!
Giá:  _____|‾‾‾‾‾‾‾‾
         |
Vol: ____█████_______  ← Volume bùng nổ khi breakout = tín hiệu xác nhận
```

**Ví dụ thực tế:** VN-Index ngày 14/3/2024: chỉ số phá vỡ ngưỡng 1,260 điểm với khối lượng gấp 2.3 lần trung bình 20 phiên. Kết quả: VN-Index tăng thêm 5% trong 2 tuần tiếp theo.

**Nguyên tắc 3: Volume Climax (Đỉnh/Đáy khối lượng)**

Khi Volume đột ngột tăng vọt bất thường (gấp 3-5 lần trung bình) kèm theo biến động giá lớn → Thường đánh dấu điểm đảo chiều tạm thời (Climax selling/buying).

---

### 5. OBV — On-Balance Volume (Khối lượng cân bằng)

#### 5.1 OBV là gì?

OBV được Joe Granville phát triển năm 1963. Đây là chỉ báo tích lũy đơn giản nhưng cực kỳ hiệu quả để theo dõi **dòng tiền thông minh (smart money)**.

**Cách tính OBV:**
```
Nếu Close hôm nay > Close hôm qua:
    OBV = OBV hôm qua + Volume hôm nay (cộng dồn)

Nếu Close hôm nay < Close hôm qua:
    OBV = OBV hôm qua - Volume hôm nay (trừ dồn)

Nếu Close không đổi:
    OBV = OBV hôm qua
```

#### 5.2 Cách sử dụng OBV

**Xác nhận xu hướng:**
```
Giá tăng + OBV tăng  → Xu hướng tăng được xác nhận (dòng tiền vào)
Giá tăng + OBV giảm  → CẢNH BÁO ĐỎ — tín hiệu phân kỳ, giá có thể đảo chiều
```

**OBV dẫn trước giá (Leading Indicator):** Một trong những đặc điểm thú vị của OBV là nó thường đi trước giá. Khi "smart money" âm thầm mua vào (tích lũy), OBV sẽ tăng trước khi giá tăng mạnh.

```
OBV tăng → Giá tăng theo sau    (tích lũy xong mới bơm giá)
OBV giảm → Giá giảm theo sau    (phân phối xong mới xả hàng)
```

---

### 6. Divergence (Phân kỳ) — Tín hiệu mạnh nhất

#### 6.1 Divergence là gì?

**Divergence (phân kỳ)** xảy ra khi **giá và chỉ báo đi ngược chiều nhau**. Đây là tín hiệu cảnh báo sớm rằng xu hướng hiện tại đang mất động lực và có thể đảo chiều.

#### 6.2 Regular Divergence (Phân kỳ thông thường) — Tín hiệu đảo chiều

**Bearish Divergence (Phân kỳ giảm):**
- Giá tạo đỉnh cao hơn (Higher High)
- RSI/MACD tạo đỉnh thấp hơn (Lower High)
- → Cảnh báo: Uptrend có thể đang yếu đi, cần xác nhận bằng phá vỡ hỗ trợ hoặc tín hiệu giá tiếp theo

```
Giá:    /‾‾\      /‾‾‾‾\    ← Đỉnh sau CAO hơn đỉnh trước
             \    /
              \__/

RSI:    /‾‾\    /‾\          ← Đỉnh sau THẤP hơn đỉnh trước
             \  /  \
              \/    \        ← PHÂN KỲ GIẢM: Cảnh báo đảo chiều!
```

**Bullish Divergence (Phân kỳ tăng):**
- Giá tạo đáy thấp hơn (Lower Low)
- RSI/MACD tạo đáy cao hơn (Higher Low)
- → Cảnh báo/cơ hội: Downtrend có thể đang yếu đi, nhưng chỉ nên hành động khi có xác nhận từ giá và quản lý rủi ro rõ ràng

```
Giá:        \__/   \___/     ← Đáy sau THẤP hơn đáy trước
                  ↘

RSI:        \__/    \/       ← Đáy sau CAO hơn đáy trước
                  ↗         ← PHÂN KỲ TĂNG: Cơ hội mua!
```

#### 6.3 Hidden Divergence (Phân kỳ ẩn) — Tín hiệu tiếp diễn

**Hidden Bullish Divergence:**
- Giá tạo đáy cao hơn (Higher Low)
- RSI tạo đáy thấp hơn (Lower Low)
- → Xu hướng tăng vẫn còn mạnh, tiếp tục tăng

**Hidden Bearish Divergence:**
- Giá tạo đỉnh thấp hơn (Lower High)
- RSI tạo đỉnh cao hơn (Higher High)
- → Xu hướng giảm vẫn còn mạnh, tiếp tục giảm

#### 6.4 Case Study thực tế: Bitcoin 2021

```
Tháng 4/2021: BTC đạt ATH ~$65,000
- Giá: Higher High ($65K > $58K của tháng 2)
- RSI: Lower High (68 < 78 của tháng 2)
→ BEARISH DIVERGENCE rõ ràng

Kết quả: BTC giảm từ $65K xuống $29K trong 2 tháng (-55%)
```

Đây là ví dụ điển hình về sức mạnh của phân kỳ khi nhận diện đúng.

---

### 7. Tổng hợp — Hệ thống chỉ báo hoàn chỉnh

Không nên dùng một chỉ báo duy nhất. Hãy xây dựng hệ thống **xác nhận đa chỉ báo**:

```
BƯỚC 1: Xác định xu hướng (Trend)
├── EMA 20/50/200 → Biết đang trong uptrend hay downtrend
└── MACD → Xác nhận momentum xu hướng

BƯỚC 2: Tìm điểm vào lệnh (Entry)
├── RSI → Xác định vùng oversold/overbought
├── Stochastic → Timing chính xác hơn
└── Volume → Xác nhận tín hiệu

BƯỚC 3: Xác nhận (Confirmation)
├── OBV → Dòng tiền có đồng thuận không?
└── Divergence → Có tín hiệu cảnh báo ngược chiều không?
```

**Ví dụ setup mua cổ phiếu:**
1. EMA 20 > EMA 50 > EMA 200 (uptrend) ✓
2. Giá pullback về EMA 50 ✓
3. RSI chạm 40-50 (không quá bán, chỉ là điều chỉnh trong uptrend) ✓
4. Stochastic %K cắt %D từ dưới lên tại vùng 20-30 ✓
5. Volume giảm trong lúc pullback (áp lực bán yếu) ✓
6. OBV vẫn đang tăng (dòng tiền không rời đi) ✓
→ **Setup bullish đáng theo dõi với nhiều yếu tố xác nhận**. Trước khi biến thành lệnh thật, vẫn cần xác định điểm vào, Stop-loss, R:R và kiểm tra xem setup này có hiệu quả trong backtest/journal của chính bạn không.

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **RSI** đo lường momentum, vùng >70 là overbought, <30 là oversold — nhưng phải xét trong context xu hướng.
2. **Stochastic** nhạy cảm hơn RSI, tốt cho timing trong sideways market; dùng khi %K cắt %D.
3. **Volume** xác nhận xu hướng: giá tăng + volume tăng = mạnh; giá tăng + volume giảm = cảnh báo.
4. **OBV** theo dõi dòng tiền thông minh và thường dẫn trước giá.
5. **Divergence** là tín hiệu mạnh nhất: giá và indicator đi ngược nhau → cảnh báo đảo chiều sắp đến.
6. Không dùng một chỉ báo đơn lẻ — hãy xây dựng hệ thống xác nhận đa chỉ báo.

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| RSI (Relative Strength Index) | Chỉ số sức mạnh tương đối | Đo momentum giá, dao động 0-100 |
| Overbought | Quá mua | RSI > 70, cảnh báo giảm |
| Oversold | Quá bán | RSI < 30, vùng xem xét tín hiệu hồi phục |
| Stochastic Oscillator | Chỉ báo dao động ngẫu nhiên | Đo vị trí giá trong vùng cao-thấp |
| %K, %D | Đường nhanh và chậm | Hai đường của Stochastic |
| Volume | Khối lượng giao dịch | Số CP/hợp đồng được giao dịch |
| OBV (On-Balance Volume) | Khối lượng cân bằng | Chỉ báo tích lũy dòng tiền |
| Divergence | Phân kỳ | Giá và indicator đi ngược chiều |
| Bullish Divergence | Phân kỳ tăng | Tín hiệu đảo chiều tăng |
| Bearish Divergence | Phân kỳ giảm | Tín hiệu đảo chiều giảm |
| Hidden Divergence | Phân kỳ ẩn | Tín hiệu tiếp diễn xu hướng |
| Smart Money | Dòng tiền thông minh | Tiền của tổ chức/nhà đầu tư lớn |
| Climax Volume | Đỉnh khối lượng | Volume đột biến bất thường |
| Momentum | Động lực giá | Tốc độ và sức mạnh của biến động giá |

---

## Bài học tiếp theo

**Ngày 32: Price Action & Timeframe Analysis**

Sau 6 ngày xây nền tảng phân tích kỹ thuật, ngày mai chúng ta sẽ học cách đọc thị trường **không cần indicator** — chỉ thuần túy dựa vào hành động giá (Price Action). Đây là phong cách của nhiều trader chuyên nghiệp. Chúng ta cũng sẽ học Multi-timeframe Analysis (phân tích đa khung thời gian) và quan trọng nhất — **xây dựng Trading Plan cá nhân hoàn chỉnh** để kết thúc phần Phân tích kỹ thuật.
