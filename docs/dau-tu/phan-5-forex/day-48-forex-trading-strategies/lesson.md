# Ngày 48: Forex Trading Strategies — 6 Chiến Lược Giao Dịch Forex

## Mục tiêu học tập
- [ ] Hiểu và phân biệt được 6 chiến lược giao dịch Forex chính
- [ ] Biết ưu điểm, nhược điểm và yêu cầu của từng chiến lược
- [ ] Xác định được chiến lược nào phù hợp với tính cách và thời gian của bản thân
- [ ] Hiểu tại sao không có chiến lược nào "tốt nhất" — chỉ có chiến lược phù hợp nhất
- [ ] Biết cách xây dựng một chiến lược cơ bản và các yếu tố cần có

---

## Nội dung bài giảng

### 1. Tại sao Chiến lược Giao dịch Quan trọng?

Hãy tưởng tượng bạn đi vào một trận chiến mà không có kế hoạch — bạn sẽ phản ứng theo cảm tính, đưa ra quyết định ngẫu hứng, và cuối cùng thua. Giao dịch Forex cũng vậy.

**Không có chiến lược = Đánh bạc**

Chiến lược giao dịch giúp bạn:
- Biết **KHI NÀO** vào lệnh (entry rules)
- Biết **KHI NÀO** thoát lệnh (exit rules)
- Kiểm soát **BAO NHIÊU** rủi ro mỗi lệnh (position sizing)
- **NHẤT QUÁN** theo thời gian (consistency)
- **BACKTEST** được để biết hiệu quả lịch sử

**Phân loại chiến lược theo thời gian giữ lệnh:**

```
Scalping      → Vài giây đến vài phút
Day Trading   → Vài giờ (đóng trước cuối ngày)
Swing Trading → Vài ngày đến vài tuần
Position Trading → Vài tuần đến vài tháng
```

---

### 2. Chiến lược 1: Trend Following (Theo Xu Hướng)

**Triết lý:** "The Trend is Your Friend" — Giao dịch CÙNG chiều với xu hướng hiện tại.

**Nguyên tắc cốt lõi:**
- Xác định xu hướng (Uptrend hay Downtrend)
- Chờ giá hồi về vùng hỗ trợ/kháng cự trong xu hướng
- Vào lệnh THEO hướng xu hướng
- Giữ lệnh đến khi xu hướng kết thúc

**Cách xác định xu hướng:**
```
Uptrend:   Higher Highs (HH) + Higher Lows (HL)
Downtrend: Lower Highs (LH) + Lower Lows (LL)

Công cụ hỗ trợ:
- Moving Average (EMA 50, EMA 200): Giá trên MA = Uptrend
- MACD: Histogram dương = Uptrend; Âm = Downtrend
- ADX > 25: Xu hướng mạnh
```

**Ví dụ chiến lược Trend Following đơn giản:**

```
SETUP: EMA Cross Strategy (EUR/USD Daily)

Điều kiện VÀO LỆNH BUY:
1. EMA 50 cắt lên trên EMA 200 (Golden Cross)
2. Giá nằm trên cả hai EMA
3. MACD histogram dương
4. Chờ giá hồi về EMA 50

Entry: Mua khi giá hồi về EMA 50 và có nến xác nhận
SL: Dưới EMA 200 hoặc Swing Low gần nhất
TP: Không cố định — trailing stop hoặc khi EMA 50 cắt xuống EMA 200
```

**Ưu điểm:**
- Risk/Reward tốt — lệnh thắng thường lớn hơn lệnh thua
- Phù hợp với tâm lý ("thuận chiều thị trường")
- Không cần theo dõi liên tục (swing/position)

**Nhược điểm:**
- Tỷ lệ thắng thường thấp (40-50%) — nhiều lệnh nhỏ bị stop
- Khó trong thị trường Sideway (ranging)
- Cần kiên nhẫn chờ xu hướng rõ

**Phù hợp với:** Người có ít thời gian theo dõi, tính kiên nhẫn, swing/position trader

---

### 3. Chiến lược 2: Breakout Trading (Giao Dịch Phá Vỡ)

**Triết lý:** Khi giá phá vỡ một vùng tích lũy hoặc kháng cự quan trọng → Xu hướng mới bắt đầu → Bám theo momentum đó.

**Khi nào Breakout xảy ra?**
- Giá tích lũy trong Range (sideway) lâu ngày → Breakout có thể bùng nổ mạnh
- Giá phá vỡ Triangle, Flag, Rectangle... (Mô hình giá đã học Ngày 29)
- Tin tức quan trọng kích hoạt breakout

**Ví dụ chiến lược Breakout:**

```
SETUP: Range Breakout (GBP/USD H4)

1. Xác định Range: Giá dao động giữa 1.2600 - 1.2800 trong 2 tuần
2. Chờ giá phá vỡ một trong hai biên:
   - Phá lên trên 1.2800 (với volume/momentum mạnh) → BUY
   - Phá xuống dưới 1.2600 → SELL

Entry: Mua khi nến H4 đóng cửa TRÊN 1.2800
SL: Trong range, khoảng 1.2750 (30-40% range width)  
TP: 1.2800 + (1.2800-1.2600) = 1.3000 (bằng chiều cao range)
```

**False Breakout (Phá vỡ giả):**
Đây là rủi ro lớn nhất — giá phá vỡ nhưng nhanh chóng quay lại.

```
Cách lọc False Breakout:
1. Chờ nến đóng cửa NGOÀI vùng (không vào khi chưa đóng nến)
2. Volume phải TĂNG khi breakout
3. Thời điểm: Phiên London hoặc NY (không phải Sydney)
4. Có tin tức hỗ trợ không?
5. Tránh breakout khi thị trường ít thanh khoản
```

**Ưu điểm:**
- Điểm vào rõ ràng
- Có thể bắt được những cú sóng lớn

**Nhược điểm:**
- False breakout rất phổ biến (~60-70% breakout là giả)
- Cần kỷ luật cao để tránh vào sớm

**Phù hợp với:** Day trader, người thích giao dịch theo momentum

---

### 4. Chiến lược 3: Range Trading (Giao Dịch Trong Biên Độ)

**Triết lý:** Thị trường dành phần lớn thời gian (khoảng 60-70%) đi SIDEWAY, không tạo xu hướng. Kiếm tiền từ việc mua đáy, bán đỉnh trong biên độ đó.

**Điều kiện Range Trading:**
- Giá dao động ổn định giữa Support và Resistance rõ ràng
- ADX < 25 (xu hướng yếu)
- Không có tin tức lớn sắp ra

**Ví dụ chiến lược Range Trading:**

```
SETUP: Support/Resistance Range (EUR/USD M30)

Range: Support 1.0850, Resistance 1.0950 (100 pip range)

BUY signal:
1. Giá chạm vùng Support 1.0845-1.0855
2. RSI Oversold (<30) hoặc Stochastic <20
3. Nến đảo chiều (Hammer, Engulfing...)
Entry: 1.0855
SL: 1.0825 (dưới support 30 pip)
TP: 1.0925 (gần resistance, không cần chờ đỉnh)

SELL signal:
1. Giá chạm vùng Resistance 1.0945-1.0955
2. RSI Overbought (>70)
3. Nến đảo chiều (Shooting Star, Bearish Engulfing...)
Entry: 1.0945
SL: 1.0975 (trên resistance 30 pip)
TP: 1.0875
```

**Ưu điểm:**
- Tỷ lệ thắng cao (60-70%)
- Điểm vào và Stop Loss rõ ràng
- Không cần giữ lệnh lâu

**Nhược điểm:**
- Risk/Reward thường thấp (1:1 đến 1:2)
- Một lần breakout thật sự → Lỗ lớn
- Cần xác định đúng khi nào thị trường sideway

**Phù hợp với:** Người kiên nhẫn, thích tỷ lệ thắng cao, có thể theo dõi biểu đồ thường xuyên

---

### 5. Chiến lược 4: Scalping (Giao Dịch Siêu Ngắn)

**Triết lý:** Kiếm nhiều lợi nhuận nhỏ (5-20 pip/lệnh) từ rất nhiều giao dịch trong ngày.

**Đặc điểm Scalping:**
- Thời gian giữ lệnh: **vài giây đến vài phút**
- Số lượng lệnh: 10-50+ lệnh/ngày
- Mục tiêu: 5-20 pip/lệnh
- Timeframe: M1, M5
- **Cần phản ứng nhanh, cực kỳ tập trung**

**Điều kiện lý tưởng cho Scalping:**
- Phiên London-NY Overlap (19:00-23:00 Việt Nam) — thanh khoản cao nhất
- Spread thấp (dùng cặp EUR/USD hoặc USD/JPY)
- Broker ECN (khớp lệnh nhanh, không requote)
- Kết nối internet ổn định, nền tảng nhanh (MT4/5)

**Ví dụ chiến lược Scalping đơn giản:**

```
SETUP: EMA Scalping (EUR/USD M5)

Indicators: EMA 8, EMA 21, Stochastic (5,3,3)

BUY:
1. EMA 8 trên EMA 21 (trend ngắn hạn tăng)
2. Stochastic cắt lên từ vùng oversold
3. Giá hồi về EMA 8
Entry: Khi nến M5 xác nhận
SL: 8-10 pip
TP: 10-15 pip

Thực hiện: Giám sát liên tục, đóng lệnh ngay khi TP hoặc SL
```

**Ưu điểm:**
- Không giữ qua đêm (không bị swap, không lo gap)
- Nhiều cơ hội giao dịch mỗi ngày
- Tỷ lệ thắng thường cao nếu làm tốt

**Nhược điểm:**
- **Đòi hỏi thời gian và sự tập trung cực cao** — rất căng thẳng
- Chi phí spread cao hơn (nhiều lệnh → tích lũy spread lớn)
- Cần broker tốt, kết nối nhanh
- **Không phù hợp với người mới** — cần nhiều kinh nghiệm
- Không phải broker nào cũng cho phép scalping

**Phù hợp với:** Người có nhiều thời gian, phản xạ nhanh, kỷ luật thép, đã có kinh nghiệm

---

### 6. Chiến lược 5: Swing Trading (Giao Dịch Dao Động)

**Triết lý:** Bắt các "sóng" trong xu hướng lớn — mua tại đáy sóng, bán tại đỉnh sóng — giữ lệnh vài ngày đến vài tuần.

**Swing Trading là chiến lược được khuyến nghị nhất cho người mới đến trung cấp** vì:
- Không cần theo dõi liên tục
- Có thời gian suy nghĩ trước khi ra quyết định
- Số lần giao dịch ít → Kỷ luật dễ hơn
- Risk/Reward tốt

**Ví dụ chiến lược Swing Trading:**

```
SETUP: Fibonacci Swing Trade (EUR/USD H4/Daily)

MULTI-TIMEFRAME ANALYSIS:
Weekly:  Downtrend (Bias: SELL)
Daily:   Đang trong sóng hồi tăng ngắn hạn
H4:      Giá đang test kháng cự

SETUP:
1. Weekly bias = Bearish → Tìm cơ hội SELL
2. Daily: Giá hồi lên Fibonacci 50%-61.8% của swing giảm trước
3. H4: Tín hiệu đảo chiều xuất hiện (Bearish Engulfing, RSI Overbought)

Entry: SELL tại Fibonacci 61.8% = 1.0950
SL: Trên Swing High = 1.1000 (50 pip)
TP1: Swing Low trước = 1.0800 (150 pip) → R:R = 1:3
TP2: Fibonacci Extension 127.2% = 1.0700 (250 pip) → R:R = 1:5

Quản lý: Đóng 50% tại TP1, để 50% chạy đến TP2 với trailing stop
```

**Ưu điểm:**
- Tốt cho người bận công việc chính
- Risk/Reward xuất sắc (1:3 đến 1:10)
- Ít căng thẳng hơn scalping/day trading
- Phù hợp với phân tích kỹ thuật và cơ bản kết hợp

**Nhược điểm:**
- Giữ qua đêm → Rủi ro gap, swap
- Cần vốn lớn hơn (stop loss rộng hơn)
- Cần kiên nhẫn

**Phù hợp với:** Người bận rộn, người mới đến trung cấp, người thích phân tích kỹ thuật

---

### 7. Chiến lược 6: Position Trading (Đầu Tư Theo Xu Hướng Dài Hạn)

**Triết lý:** Bắt những xu hướng lớn kéo dài nhiều tháng, dựa chủ yếu vào phân tích cơ bản (macro) và kỹ thuật trên Weekly/Monthly chart.

**Đặc điểm Position Trading:**
- Thời gian giữ lệnh: **Vài tuần đến vài tháng**
- Số lượng lệnh: **1-5 lệnh/tháng**
- Stop Loss: **200-500+ pip** (rất rộng)
- Vốn yêu cầu: **Lớn** (vì stop rộng)
- Kết hợp Fundamental + Technical

**Ví dụ:**
```
SETUP: Interest Rate Divergence Trade

Tháng 1/2022:
- Fed báo hiệu sắp tăng lãi suất mạnh (Hawkish mạnh)
- BOJ tiếp tục giữ lãi suất âm (Dovish)
→ USD/JPY Bullish rõ ràng về cơ bản

Technical (Weekly):
- USD/JPY phá vỡ kháng cự 116.00 (level quan trọng nhiều năm)
- MACD cắt lên trên 0
→ Tín hiệu kỹ thuật xác nhận

Trade: BUY USD/JPY tại 116.50
SL: 113.00 (350 pip — dưới breakout point)
TP: Không cố định, trailing stop khi xu hướng kết thúc

Kết quả: USD/JPY tăng lên 152.00 (2022)
Lợi nhuận: 3,550 pip!
```

**Ưu điểm:**
- Lợi nhuận tiềm năng cực lớn
- Ít giao dịch → Ít phí, ít căng thẳng
- Phù hợp với người hiểu kinh tế vĩ mô

**Nhược điểm:**
- Cần vốn lớn (stop loss rộng)
- Cần hiểu sâu về macro economics
- Tâm lý khó — phải chịu đựng floating loss lớn

**Phù hợp với:** Nhà đầu tư có kinh nghiệm, hiểu macro, vốn lớn

---

### 8. Tự đánh giá: Chiến lược nào phù hợp với bạn?

Trả lời các câu hỏi sau để xác định chiến lược phù hợp:

**Câu hỏi 1: Bạn có bao nhiêu thời gian theo dõi thị trường?**
- < 1 giờ/ngày → Swing hoặc Position Trading
- 2-4 giờ/ngày → Swing hoặc Day Trading
- Toàn thời gian → Scalping hoặc Day Trading

**Câu hỏi 2: Tính cách của bạn thế nào?**
- Thích action nhanh, phản xạ tốt → Scalping, Day Trading
- Kiên nhẫn, thích phân tích → Swing, Position Trading
- Thích tỷ lệ thắng cao → Range Trading
- Thích lợi nhuận lớn nhưng ít giao dịch → Position Trading

**Câu hỏi 3: Vốn của bạn là bao nhiêu?**
- < 1,000 USD → Micro lot, Swing/Day trading
- 1,000 - 5,000 USD → Day trading, Swing trading
- > 5,000 USD → Tất cả chiến lược đều khả thi

**Câu hỏi 4: Kinh nghiệm của bạn?**
- Mới bắt đầu → Swing Trading (được khuyến nghị nhất)
- Trung cấp → Day Trading, Swing Trading
- Có kinh nghiệm → Tất cả

**Kết luận cho người mới:** Bắt đầu với **Swing Trading** (H4/Daily, giữ lệnh vài ngày) vì:
- Có thời gian phân tích kỹ lưỡng
- Không bị áp lực thời gian
- Học được tất cả các kỹ năng cơ bản
- Sau khi thành thạo, có thể chuyển sang chiến lược khác

---

### 9. Các Yếu tố Cần có Trong Một Chiến lược Hoàn chỉnh

Dù chọn chiến lược nào, một trading plan cần có đủ các thành phần sau:

**1. Market Selection (Chọn thị trường):**
- Cặp tiền nào? (EUR/USD, USD/JPY...)
- Phiên nào? (London, NY...)

**2. Entry Rules (Điều kiện vào lệnh):**
- Cụ thể, không mơ hồ
- Ví dụ: "Vào BUY khi EMA 50 cắt lên EMA 200 và RSI < 50 và giá tại Fibonacci 38.2%"

**3. Stop Loss (Cắt lỗ):**
- Tính theo kỹ thuật (dưới Support/Swing Low)
- KHÔNG được bỏ qua Stop Loss

**4. Take Profit / Exit Rules:**
- TP cố định, TP theo trailing stop, hay đóng theo điều kiện kỹ thuật?

**5. Position Sizing (Kích thước lệnh):**
- Công thức: (Vốn × % Rủi ro) / (SL pip × Pip value)
- Không vượt quá 1-2% vốn mỗi lệnh

**6. Risk Management tổng thể:**
- Tối đa bao nhiêu lệnh cùng lúc?
- Thua bao nhiêu lệnh liên tiếp thì dừng ngày?
- Daily/Weekly loss limit

**7. Trading Journal (Nhật ký giao dịch):**
- Ghi lại mọi lệnh: Ngày, cặp tiền, entry, exit, lý do, cảm xúc
- Review hàng tuần để cải thiện

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **6 chiến lược chính**: Trend Following, Breakout, Range Trading, Scalping, Swing Trading, Position Trading — mỗi chiến lược phù hợp với profile trader khác nhau
2. **Không có "best strategy"** — chỉ có chiến lược phù hợp với tính cách, thời gian và vốn của bạn
3. **Người mới nên bắt đầu với Swing Trading** (H4/Daily) — có thời gian phân tích, ít áp lực, học được toàn bộ kỹ năng
4. **Scalping là chiến lược khó nhất** — tỷ lệ thất bại cao với người mới, cần nhiều kinh nghiệm
5. **Mọi chiến lược đều cần**: Entry rules rõ ràng, Stop Loss, Position Sizing 1-2%, Trading Journal
6. **Kiên định với một chiến lược** ít nhất 3-6 tháng trước khi đánh giá — không nhảy từ chiến lược này sang chiến lược khác liên tục

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|-----------------|-----------------|
| Trend Following | Theo xu hướng | Giao dịch cùng chiều xu hướng hiện tại |
| Breakout Trading | Giao dịch phá vỡ | Vào lệnh khi giá phá vỡ vùng tích lũy |
| Range Trading | Giao dịch trong biên độ | Mua đáy, bán đỉnh trong vùng sideway |
| Scalping | Giao dịch siêu ngắn | Kiếm nhiều lợi nhuận nhỏ trong ngày |
| Swing Trading | Giao dịch dao động | Bắt các sóng giá, giữ vài ngày đến tuần |
| Position Trading | Giao dịch vị thế | Theo xu hướng lớn, giữ nhiều tuần đến tháng |
| False Breakout | Phá vỡ giả | Giá phá vỡ rồi quay lại ngay |
| Entry Rules | Điều kiện vào lệnh | Tiêu chí cụ thể để mở một lệnh |
| Exit Rules | Điều kiện thoát lệnh | Tiêu chí đóng lệnh (TP, SL, trailing) |
| Trailing Stop | Cắt lỗ theo dõi | Stop Loss tự động di chuyển theo giá |
| Trading Plan | Kế hoạch giao dịch | Toàn bộ quy tắc giao dịch của một trader |
| Trading Journal | Nhật ký giao dịch | Ghi chép chi tiết mọi lệnh giao dịch |
| Backtesting | Kiểm tra lịch sử | Áp dụng chiến lược vào dữ liệu lịch sử để kiểm nghiệm |
| Momentum | Động lực giá | Tốc độ và sức mạnh của chuyển động giá |
| ADX | Chỉ báo sức mạnh xu hướng | ADX > 25 = xu hướng mạnh; < 25 = sideways |

---

## Bài học tiếp theo

Ngày 49 sẽ học **Money Management trong Forex** — đi sâu vào quản lý vốn: quy tắc 1-2% rủi ro, tính Position Size chính xác, quản lý Drawdown, và tại sao 90% trader Forex thua lỗ (gợi ý: không phải vì thiếu chiến lược tốt). Đây là bài học quan trọng nhất trong toàn bộ module Forex.
