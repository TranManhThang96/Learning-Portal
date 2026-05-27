# Bài tập — Ngày 63: Công cụ & Nền tảng Giao dịch

## Phần 1: Câu hỏi ôn tập (Quiz)

**1. TradingView hỗ trợ xem biểu đồ của thị trường nào?**
   - A. Chỉ Forex và Crypto
   - B. Chỉ cổ phiếu Mỹ
   - C. Tất cả: Cổ phiếu, Forex, Crypto, Hàng hóa, Chỉ số
   - D. Chỉ cổ phiếu và Forex

**2. Trên TradingView, để tìm biểu đồ cổ phiếu Vinamilk (VNM) trên sàn HOSE một cách rõ ràng nhất, bạn gõ gì vào thanh tìm kiếm?**
   - A. `HOSE:VNM`
   - B. `NASDAQ:VNM`
   - C. `VNINDEX:VNM`
   - D. Chỉ cần gõ `VNM`

**3. Trong MT4, lệnh "Buy Limit" được dùng trong tình huống nào?**
   - A. Muốn mua ngay tại giá thị trường hiện tại
   - B. Muốn mua khi giá tăng vượt lên một mức nhất định
   - C. Muốn mua khi giá giảm về một mức thấp hơn giá hiện tại
   - D. Muốn bán khi giá giảm xuống dưới một mức nhất định

**4. "Trailing Stop" trong MT4 có nghĩa là gì?**
   - A. Lệnh dừng lỗ cố định tại một mức giá không đổi
   - B. Lệnh dừng lỗ tự động dịch chuyển theo hướng có lợi cho vị thế
   - C. Lệnh chốt lời tự động khi đạt mục tiêu lợi nhuận
   - D. Lệnh đóng vị thế ngay khi thị trường đóng cửa

**5. Sự khác biệt chính giữa CEX và DEX là gì?**
   - A. CEX chỉ giao dịch Bitcoin, DEX giao dịch tất cả altcoin
   - B. CEX do công ty tập trung quản lý, DEX hoạt động qua smart contract không cần trung gian
   - C. CEX miễn phí hoàn toàn, DEX tính phí cao hơn
   - D. CEX chỉ dành cho người chuyên nghiệp, DEX dành cho người mới

**6. Trên sàn chứng khoán HOSE Việt Nam, lệnh ATC có nghĩa là gì?**
   - A. Automatic Trading Command — Lệnh giao dịch tự động
   - B. At The Close — Lệnh khớp tại giá đóng cửa cuối phiên
   - C. After Trading Close — Lệnh đặt sau giờ giao dịch
   - D. At The Current — Lệnh khớp tại giá hiện tại

**7. Bạn muốn xem dữ liệu lịch sử P/E ratio của chỉ số S&P 500 từ năm 1990 đến nay. Công cụ nào phù hợp nhất?**
   - A. Investing.com
   - B. MetaTrader 5
   - C. Macrotrends
   - D. Finviz Screener

**8. Trên Finviz Screener, bạn muốn tìm cổ phiếu Mỹ có P/E dưới 15, vốn hóa trên $10 tỷ và tăng trưởng EPS trên 10%. Bạn cần vào tab nào?**
   - A. Tab Technical
   - B. Tab Fundamental
   - C. Tab Descriptive
   - D. Tab All

**9. Trang web nào thường được dùng để tra cứu TVL (Total Value Locked) của các protocol DeFi?**
   - A. CoinMarketCap
   - B. Binance
   - C. DefiLlama
   - D. MetaMask

**10. Khi kiểm tra uy tín của một Forex broker, bạn nên tìm giấy phép từ tổ chức nào? (Chọn tất cả đúng)**
   - A. FCA (UK)
   - B. ASIC (Australia)
   - C. CySEC (Cyprus)
   - D. Tất cả các đáp án trên đều đúng

---

## Phần 2: Bài tập thực hành

---

### Bài tập 1: Thiết lập TradingView (Thời gian: 30 phút)

**Mục tiêu**: Làm quen với giao diện TradingView và thực hành phân tích kỹ thuật cơ bản.

**Các bước thực hiện**:

**Step 1 — Tạo tài khoản (5 phút)**
- Truy cập tradingview.com
- Nhấn "Sign Up" → Chọn đăng ký bằng Google (nhanh nhất)
- Hoàn thành thiết lập profile

**Step 2 — Tìm biểu đồ và thêm indicator (10 phút)**
- Nhấn vào thanh tìm kiếm (hoặc nhấn `/`)
- Tìm kiếm: `BINANCE:BTCUSDT`
- Chuyển timeframe sang `1D` (Daily)
- Nhấn "Indicators" → Tìm và thêm:
  - [ ] EMA 20 (đặt màu xanh lá)
  - [ ] EMA 50 (đặt màu cam)
  - [ ] RSI (14) — hiển thị phía dưới
  - [ ] Volume — hiển thị phía dưới

**Mô tả screenshot cần thấy**:
```text
Thanh trên cùng hiển thị BINANCE:BTCUSDT và timeframe 1D.
Giữa màn hình là nến BTCUSDT; hai đường EMA màu xanh/cam chạy trên biểu đồ.
Panel dưới có RSI và Volume.
Bên trái có toolbar vẽ; bên phải có trục giá và watchlist.
```

**Step 3 — Vẽ phân tích kỹ thuật (10 phút)**
- Dùng công cụ Horizontal Line (`H`) vẽ ít nhất:
  - [ ] 1 vùng Resistance (kháng cự) rõ ràng
  - [ ] 1 vùng Support (hỗ trợ) rõ ràng
- Dùng Trendline (`L`) vẽ:
  - [ ] 1 trendline theo xu hướng hiện tại

**Step 4 — Đặt Alert (5 phút)**
- Xác định một vùng kháng cự quan trọng
- Nhấn `Alt+A` hoặc chuột phải → "Add Alert"
- Thiết lập: Condition = "Crossing" | Value = [giá kháng cự bạn xác định]
- Chọn thông báo qua: Popup và Email
- [ ] Xác nhận Alert đã được lưu (biểu tượng chuông xuất hiện trên biểu đồ)

**Step 5 — Ghi nhận vào Trading Journal (5 phút)**
Chụp màn hình biểu đồ (Alt+S) và điền vào template:

```
📊 PHÂN TÍCH BTCUSDT — [Ngày: ]

Timeframe: 1D
Xu hướng hiện tại: [Tăng / Giảm / Sideway]

Vùng Resistance đã xác định: $___________
Vùng Support đã xác định: $___________

Tình trạng RSI hiện tại: ___________ (Overbought >70 / Neutral 30-70 / Oversold <30)
EMA 20 so với EMA 50: [EMA20 trên EMA50 / EMA20 dưới EMA50]
→ Tín hiệu: [Bullish / Bearish]

Alert đã đặt tại: $___________
Lý do đặt alert tại vùng này: _______________

Nhận xét chung về thị trường: _______________
```

**Checklist hoàn thành**:
- [ ] Tạo tài khoản TradingView thành công
- [ ] Thêm đủ 4 indicator (EMA20, EMA50, RSI, Volume)
- [ ] Vẽ ít nhất 1 Support và 1 Resistance
- [ ] Vẽ ít nhất 1 Trendline
- [ ] Đặt Alert thành công
- [ ] Điền xong Trading Journal

---

### Bài tập 2: Thiết lập MT4/MT5 Demo (Thời gian: 45 phút)

**Mục tiêu**: Cài đặt MetaTrader, tạo tài khoản demo và thực hành đặt lệnh Pending Order.

**Step 1 — Tải và cài đặt MT4 (10 phút)**
- Chọn một broker có MT4/MT5 demo và tự verify giấy phép/domain trước khi tải. Có thể dùng broker phổ biến làm ví dụ học giao diện, nhưng không xem đây là khuyến nghị mở tài khoản live.
- Truy cập website chính thức của broker đã chọn, tìm mục "Trading Platforms" → Tải MT4/MT5 cho Windows/Mac
- Cài đặt theo hướng dẫn mặc định
- Khi mở lần đầu, chương trình sẽ kết nối đến server demo của broker đó

**Step 2 — Tạo tài khoản Demo (5 phút)**
- Trong MT4: Vào menu **File** → **Open an Account**
- Chọn server demo/practice của broker → "Open a practice account"
- Điền thông tin tối thiểu cho tài khoản demo; có thể dùng email phụ nhưng phải là email bạn kiểm soát nếu cần xác nhận
- Chọn: Leverage = 1:100, Deposit = **$10,000** (tiền ảo)
- Ghi lại thông tin tài khoản (Account number, Password)

**Step 3 — Thiết lập biểu đồ (10 phút)**
- Trong **Market Watch** (Ctrl+M để hiện), tìm **EURUSD** → Double-click để mở biểu đồ
- Chuyển timeframe sang **H1** (1 giờ)
- Nhấn **Insert** → **Indicators** → **Trend** → Thêm **Moving Average**:
  - Cài đặt MA đầu tiên: Period = 50, Method = Simple, Color = Xanh
  - Cài đặt MA thứ hai: Period = 200, Method = Simple, Color = Đỏ
- Quan sát: MA50 đang nằm trên hay dưới MA200? (Bullish hay Bearish?)

**Mô tả screenshot cần thấy**:
```text
Góc trái là Market Watch có EURUSD với Bid/Ask.
Giữa màn hình là chart EURUSD H1 với MA50 màu xanh và MA200 màu đỏ.
Dưới cùng là Terminal/Trade, hiện số dư demo và vùng lệnh đang mở.
Nút New Order nằm trên toolbar.
```

**Step 4 — Đặt Pending Orders (15 phút)**

Xem biểu đồ EURUSD hiện tại và đặt 2 lệnh sau:

**Lệnh 1 — Buy Limit** (mua khi giá giảm về hỗ trợ):
- Nhấn F9 → Chọn **"Pending Order"**
- Type: **Buy Limit**
- Price: [Giá thấp hơn giá hiện tại khoảng 30-50 pips]
- Stop Loss: [Thấp hơn Price thêm 20 pips]
- Take Profit: [Cao hơn Price 40 pips] (R:R = 1:2)
- Nhấn **Place**

**Lệnh 2 — Sell Stop** (bán khi giá breakdown):
- Nhấn F9 → Chọn **"Pending Order"**
- Type: **Sell Stop**
- Price: [Giá thấp hơn giá hiện tại khoảng 50-70 pips]
- Stop Loss: [Cao hơn Price 20 pips]
- Take Profit: [Thấp hơn Price 40 pips]
- Nhấn **Place**

**Step 5 — Ghi vào Trade Journal (5 phút)**

```
📋 TRADE JOURNAL — MT4 DEMO

Ngày: ___________
Tài khoản: Broker Demo đã verify | Balance: $10,000

─── LỆNH 1: BUY LIMIT EURUSD ───
Giá đặt lệnh: 1.___________
Stop Loss: 1.___________ (rủi ro: ___ pips)
Take Profit: 1.___________ (lợi nhuận mục tiêu: ___ pips)
Risk/Reward Ratio: 1 : ___
Lot size: 0.01 (Micro lot)
Lý do đặt lệnh tại vùng này: _______________

─── LỆNH 2: SELL STOP EURUSD ───
Giá đặt lệnh: 1.___________
Stop Loss: 1.___________
Take Profit: 1.___________
Risk/Reward Ratio: 1 : ___
Lý do: _______________

Theo dõi kết quả sau 24h và ghi lại: _______________
```

**Checklist hoàn thành**:
- [ ] Tải và cài đặt MT4 thành công
- [ ] Tạo tài khoản demo $10,000
- [ ] Mở biểu đồ EURUSD H1
- [ ] Thêm MA50 và MA200 vào biểu đồ
- [ ] Đặt thành công 1 lệnh Buy Limit
- [ ] Đặt thành công 1 lệnh Sell Stop
- [ ] Điền xong Trade Journal

---

### Bài tập 3: Đọc Economic Calendar (Thời gian: 20 phút)

**Mục tiêu**: Thực hành đọc lịch kinh tế và dự đoán tác động lên thị trường.

**Step 1**: Vào **investing.com/economic-calendar**

**Step 2**: Lọc dữ liệu:
- Nhấn vào "Filter" → Chọn **"High Impact"** (biểu tượng 3 con bò đỏ)
- Chọn khoảng thời gian: Tuần này

**Mô tả screenshot cần thấy**:
```text
Bảng lịch có các cột Time, Currency/Country, Event, Impact, Actual, Forecast, Previous.
Bộ lọc đang chọn High Impact và khoảng thời gian là This Week/Tuần này.
Các sự kiện quan trọng có biểu tượng impact nổi bật.
```

**Step 3**: Tìm 3 sự kiện quan trọng nhất trong tuần và điền vào bảng:

```
📅 ECONOMIC CALENDAR — Tuần: ___________

┌────────────────────────────────────────────────────────────────────────────┐
│ Sự kiện 1:                                                                 │
│ Thời gian: ____________  Quốc gia: ____________                            │
│ Tên sự kiện: ____________________________________________                  │
│ Actual: _______  Forecast: _______  Previous: _______                     │
│                                                                            │
│ Phân tích tác động:                                                        │
│ Nếu Actual > Forecast → Tác động lên USD: [Tăng / Giảm]                   │
│ Lý do: ___________________________________________________                 │
│ Tài sản bị ảnh hưởng nhiều nhất: ________________________                  │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ Sự kiện 2:                                                                 │
│ Thời gian: ____________  Quốc gia: ____________                            │
│ Tên sự kiện: ____________________________________________                  │
│ Actual: _______  Forecast: _______  Previous: _______                     │
│                                                                            │
│ Phân tích tác động:                                                        │
│ Nếu Actual > Forecast → Tác động: _______________________________          │
│ Lý do: ___________________________________________________                 │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ Sự kiện 3:                                                                 │
│ Thời gian: ____________  Quốc gia: ____________                            │
│ Tên sự kiện: ____________________________________________                  │
│ Actual: _______  Forecast: _______  Previous: _______                     │
│                                                                            │
│ Phân tích tác động:                                                        │
│ Nếu Actual > Forecast → Tác động: _______________________________          │
│ Lý do: ___________________________________________________                 │
└────────────────────────────────────────────────────────────────────────────┘
```

**Checklist hoàn thành**:
- [ ] Vào được trang Economic Calendar
- [ ] Lọc thành công High Impact events
- [ ] Tìm được 3 sự kiện quan trọng
- [ ] Điền đầy đủ Actual/Forecast/Previous cho từng sự kiện
- [ ] Viết được phân tích tác động cho mỗi sự kiện

---

### Bài tập 4: Screener cổ phiếu Mỹ trên Finviz (Thời gian: 30 phút)

**Mục tiêu**: Sử dụng Finviz để lọc cổ phiếu và thực hành tra cứu thông tin cơ bản.

**Step 1**: Vào **finviz.com/screener.ashx**

**Step 2**: Chọn tab **"Fundamental"** và thiết lập bộ lọc:

| Tiêu chí | Giá trị lọc | Lý do |
|----------|------------|-------|
| P/E | Under 20 | Tránh mua đắt |
| Market Cap | Large ($10bln+) | Công ty lớn, ít biến động |
| EPS growth this Y | Over 10% | Tăng trưởng lợi nhuận |
| Debt/Equity | Under 1 | Không vay nợ quá nhiều |
| ROE | Over 15% | Hiệu quả sử dụng vốn tốt |

**Mô tả screenshot cần thấy**:
```text
Trên đầu trang là các tab Descriptive, Fundamental, Technical.
Các dropdown filter đang hiển thị P/E, Market Cap, EPS growth, Debt/Equity, ROE.
Bên dưới là bảng kết quả gồm ticker, company, sector, price, P/E, ROE, change.
```

**Step 3**: Ghi lại kết quả — điền 5 cổ phiếu đầu tiên trong danh sách:

```
📊 KẾT QUẢ SCREENER — Bộ lọc: P/E<20, LargeCap, EPS>10%, D/E<1, ROE>15%
Ngày thực hiện: ___________
Tổng số kết quả tìm được: ___ cổ phiếu

┌─────┬────────┬───────────────────────┬──────┬──────────┬───────┬─────┐
│ STT │ Ticker │ Tên công ty           │  P/E │ Mkt Cap  │  ROE  │ D/E │
├─────┼────────┼───────────────────────┼──────┼──────────┼───────┼─────┤
│  1  │        │                       │      │          │       │     │
│  2  │        │                       │      │          │       │     │
│  3  │        │                       │      │          │       │     │
│  4  │        │                       │      │          │       │     │
│  5  │        │                       │      │          │       │     │
└─────┴────────┴───────────────────────┴──────┴──────────┴───────┴─────┘
```

**Step 4**: Chọn 1 cổ phiếu trong danh sách và nghiên cứu thêm:
- Click vào tên cổ phiếu trong Finviz → Xem tóm tắt
- Vào TradingView, tìm cổ phiếu đó, xem biểu đồ 1D

```
🔍 PHÂN TÍCH SÂU HƠN — Mã cổ phiếu đã chọn: ___________

Tên công ty: ___________________________________
Ngành (Sector): ________________________________
Mô tả kinh doanh ngắn gọn: ____________________
_________________________________________________

Dữ liệu cơ bản:
- P/E: ___________
- ROE: ___________
- Doanh thu gần nhất (Revenue): $___________
- Lợi nhuận ròng (Net Income): $___________
- EPS growth gần nhất: ___________

Phân tích kỹ thuật (từ TradingView - 1D):
- Xu hướng: [Tăng / Giảm / Sideway]
- Giá hiện tại so với MA200: [Trên / Dưới]
- RSI: ___________ (Overbought / Normal / Oversold)

Nhận xét: Cổ phiếu này có đáng xem xét đầu tư không và tại sao?
_________________________________________________
_________________________________________________
```

**Checklist hoàn thành**:
- [ ] Vào được Finviz Screener
- [ ] Thiết lập đúng 5 tiêu chí lọc
- [ ] Ghi lại được 5 cổ phiếu từ kết quả
- [ ] Phân tích sâu hơn 1 cổ phiếu được chọn
- [ ] Xem biểu đồ kỹ thuật của cổ phiếu trên TradingView

---

### Bài tập 5: Xây dựng Personal Toolkit (Thời gian: 25 phút)

**Mục tiêu**: Hoàn thiện bộ công cụ cá nhân và tổ chức bookmark trình duyệt.

**Step 1**: Điền đầy đủ bảng Personal Toolkit bên dưới:

```
🛠️ PERSONAL TOOLKIT — [Tên của bạn] — [Ngày lập: ]

THỊ TRƯỜNG TÔI TẬP TRUNG:
[ ] Cổ phiếu Việt Nam
[ ] Cổ phiếu Mỹ
[ ] Forex
[ ] Crypto
[ ] Kết hợp nhiều thị trường

────────────────────────────────────────────────────────────
CÔNG CỤ BIỂU ĐỒ & PHÂN TÍCH KỸ THUẬT:
Công cụ chính: TradingView
Tài khoản: [ ] Đã tạo  [ ] Chưa tạo
Gói: [ ] Free  [ ] Pro
────────────────────────────────────────────────────────────

CÔNG CỤ GIAO DỊCH:
Thị trường         | Sàn/Broker      | Loại TK   | Trạng thái
CK Việt Nam        |                 | Demo/Live |
CK Mỹ             |                 | Demo/Live |
Forex              |                 | Demo      |
Crypto (CEX)       |                 |           |
────────────────────────────────────────────────────────────

CÔNG CỤ DỮ LIỆU VĨ MÔ:
[ ] Investing.com — Economic Calendar
[ ] FRED (fred.stlouisfed.org) — Dữ liệu Fed
[ ] Macrotrends — Biểu đồ dài hạn
[ ] Trading Economics — Dữ liệu quốc tế
────────────────────────────────────────────────────────────

SCREENER TÔI SỬ DỤNG:
[ ] Finviz (cổ phiếu Mỹ)
[ ] TradingView Screener (đa thị trường)
[ ] CafeF Screener (cổ phiếu VN)
[ ] CoinMarketCap (Crypto)
────────────────────────────────────────────────────────────

NGUỒN TIN TÔI THEO DÕI:
Tin tức VN: _________________________________
Tin tức quốc tế: ____________________________
Tin tức Crypto (nếu có): ____________________
Podcast/YouTube: ____________________________
────────────────────────────────────────────────────────────

TRADING JOURNAL:
Công cụ: [ ] Google Sheets  [ ] Excel  [ ] Ứng dụng khác: ____
Link Google Sheets: ________________________________
Tần suất cập nhật: [ ] Sau mỗi lệnh  [ ] Hàng tuần
────────────────────────────────────────────────────────────

CAM KẾT CÁ NHÂN:
Tôi cam kết thực hành demo trong ít nhất: ___ tháng trước khi dùng tiền thật
Số vốn tối đa tôi sẵn sàng mất khi bắt đầu live: ___________
Chiến lược tôi sẽ theo đuổi: ___________________________
```

**Step 2**: Tổ chức bookmark trình duyệt

Tạo các folder sau trong bookmark của bạn và điền link:

```
📁 Macro Data
   ├── FRED: fred.stlouisfed.org
   ├── Trading Economics: tradingeconomics.com
   ├── Macrotrends: macrotrends.net
   └── Investing.com Calendar: investing.com/economic-calendar

📁 Charts & Analysis
   ├── TradingView: tradingview.com
   └── [Thêm nếu cần]

📁 News
   ├── [Nguồn tin bạn đã chọn]
   └── [Nguồn tin thứ 2]

📁 Screener
   ├── Finviz: finviz.com/screener
   ├── CafeF: cafef.vn  [nếu theo CK VN]
   └── CMC: coinmarketcap.com  [nếu theo Crypto]

📁 Portfolio & Journal
   ├── Google Sheets danh mục: [Link của bạn]
   └── Portfolio Visualizer: portfoliovisualizer.com
```

**Mô tả screenshot cần thấy**:
```text
Bookmark bar hoặc Bookmark Manager có 5 folder: Macro Data, Charts & Analysis, News, Screener, Portfolio & Journal.
Google Sheets journal có header: Ngày, Mã, Hướng, Giá vào, SL, TP, Rủi ro %, Kết quả, Bài học.
```

**Step 3**: Verify sàn/broker trước khi đưa vào toolkit

Điền bảng kiểm tra sau cho từng nền tảng bạn dự định dùng live:

```
🔎 CHECKLIST VERIFY SÀN/BROKER

Tên nền tảng: _______________________________
Website/domain chính thức: __________________
Tên pháp lý của công ty: ____________________
Cơ quan quản lý/giấy phép: _________________
Link tra cứu giấy phép: _____________________
Quốc gia/khu vực được hỗ trợ: _______________
Phí chính cần biết: _________________________
Quy trình rút tiền đã đọc chưa? [ ] Có [ ] Chưa
Đã thử nạp/rút số nhỏ chưa? [ ] Có [ ] Chưa [ ] Chưa dùng live
Red flag phát hiện: _________________________
Kết luận: [ ] Chỉ demo [ ] Có thể theo dõi thêm [ ] Không dùng
```

**Checklist hoàn thành**:
- [ ] Điền đầy đủ bảng Personal Toolkit
- [ ] Tạo xong các folder bookmark trong trình duyệt
- [ ] Bookmark ít nhất 10 trang web vào đúng folder
- [ ] Tạo Google Sheets Trading Journal (dù chỉ có header)
- [ ] Viết xong Cam kết cá nhân
- [ ] Điền checklist verify cho mọi sàn/broker định dùng live

---

## Phần 3: Case Study — Phân tích và thiết lập công cụ cho một kịch bản thực tế

### Kịch bản: Bạn quyết định bắt đầu Swing Trading cổ phiếu Mỹ

Giả sử bạn có 5,000 USD để đầu tư và muốn thực hiện swing trading cổ phiếu Mỹ (nắm giữ 1-4 tuần mỗi lệnh). Hãy trả lời các câu hỏi sau và lập kế hoạch công cụ phù hợp:

**Câu hỏi 1**: Bạn sẽ dùng timeframe nào trên TradingView để xác định xu hướng chính và timeframe nào để tìm điểm vào lệnh?
```
Timeframe xu hướng chính: ___________
Lý do: _________________________________

Timeframe vào lệnh: ___________
Lý do: _________________________________
```

**Câu hỏi 2**: Với Finviz Screener, bạn sẽ thiết lập bộ lọc nào cho chiến lược swing trading?
```
Tiêu chí lọc của tôi:
1. ___________________________________
2. ___________________________________
3. ___________________________________
4. ___________________________________
Lý do chọn các tiêu chí này: ___________
```

**Câu hỏi 3**: Nếu bạn sử dụng Rule 2% risk per trade (đã học Ngày 49), với vốn $5,000, mỗi lệnh bạn tối đa chịu lỗ bao nhiêu?
```
Số tiền rủi ro tối đa mỗi lệnh: $___________
```

**Câu hỏi 4**: Tuần tới có sự kiện NFP (Non-Farm Payrolls) vào thứ Sáu. Bạn nên kiểm tra thông tin này ở đâu và nó ảnh hưởng thế nào đến chiến lược của bạn?
```
Nơi kiểm tra: ___________________________
Tác động đến chiến lược: _________________
_________________________________________
```

---

## Đáp án & Giải thích

### Quiz

1. **Đáp án: C** — TradingView hỗ trợ tất cả các loại tài sản: Stocks (đa quốc gia), Forex, Crypto, Commodities (hàng hóa như vàng, dầu), Indices (chỉ số thị trường). Đây là lý do nó được gọi là "nền tảng biểu đồ đa thị trường".

2. **Đáp án: A** — Để tránh chọn nhầm mã, hãy dùng đúng prefix sàn khi có thể. Vinamilk giao dịch trên HOSE nên nhập `HOSE:VNM`, hoặc gõ `VNM` rồi chọn dòng có sàn HOSE trong kết quả TradingView.

3. **Đáp án: C** — Buy Limit là lệnh mua chờ tại giá thấp hơn giá hiện tại. Trader dùng khi muốn mua ở vùng hỗ trợ, chờ thị trường "kéo về" mức giá đó rồi mới mua, không mua ngay tại giá thị trường.

4. **Đáp án: B** — Trailing Stop là lệnh dừng lỗ thông minh, tự động dịch chuyển theo hướng có lợi cho vị thế. Ví dụ: Trailing Stop 30 pips trên lệnh Buy — khi giá tăng thêm 30 pips, SL tự động dịch lên 30 pips, khóa một phần lợi nhuận trong khi vẫn để giá tiếp tục chạy.

5. **Đáp án: B** — CEX (như Binance, OKX) do công ty vận hành, có KYC, lưu trữ tài sản người dùng. DEX (như Uniswap) hoạt động hoàn toàn qua smart contract, người dùng giữ private key, không cần tài khoản — nhưng cũng không có hỗ trợ khách hàng nếu xảy ra sự cố.

6. **Đáp án: B** — ATC (At The Close) là lệnh khớp tại giá đóng cửa. Chỉ đặt được trong khoảng 14:30-14:45 trên HOSE. Giá đóng cửa được xác định qua phiên khớp lệnh định kỳ cuối ngày.

7. **Đáp án: C** — Macrotrends chuyên về dữ liệu biểu đồ dài hạn. Trang này có P/E Ratio lịch sử của S&P 500 từ năm 1880, cho phép so sánh mức định giá hiện tại với trung bình lịch sử rất trực quan.

8. **Đáp án: B** — Tab "Fundamental" trong Finviz chứa các bộ lọc về chỉ số tài chính cơ bản: P/E, P/B, ROE, EPS growth, Debt/Equity, Market Cap... Tab "Technical" để lọc theo chỉ báo kỹ thuật (RSI, SMA, Volume).

9. **Đáp án: C** — DefiLlama (defillama.com) là công cụ chuyên theo dõi TVL của nhiều protocol DeFi trên nhiều blockchain và được cộng đồng crypto dùng rộng rãi (đã học ở Ngày 58).

10. **Đáp án: D** — Tất cả đều đúng. FCA (Financial Conduct Authority - UK), ASIC (Australian Securities and Investments Commission - Úc), và CySEC (Cyprus Securities and Exchange Commission) là các cơ quan quản lý thường được dùng để kiểm tra broker. Sau đó vẫn phải đối chiếu đúng tên pháp lý, mã giấy phép, domain và quốc gia/khu vực được phục vụ.

---

### Bài tập thực hành — Hướng dẫn chấm điểm

**Bài tập 1 (TradingView)**:
- Nếu bạn không thấy biểu đồ BTCUSDT: Kiểm tra lại cú pháp `BINANCE:BTCUSDT` (có thể thay bằng `BTCUSDT` đơn giản)
- EMA 20 nên phản ứng nhanh hơn EMA 50 — nếu EMA20 đang nằm trên EMA50, đây là tín hiệu bullish
- Support/Resistance tốt là những vùng giá mà nến "chạm và bật" ít nhất 2-3 lần trong quá khứ

**Bài tập 2 (MT4)**:
- Nếu broker demo không cho mở tài khoản hoặc domain/giấy phép không verify được: bỏ qua broker đó và chọn nền tảng demo khác; không nạp tiền thật để "thử"
- Risk/Reward của Buy Limit phải ≥ 1:2 (SL 20 pips, TP ≥ 40 pips) — đây là tiêu chuẩn tối thiểu
- Khi đặt SL và TP, luôn tính bằng pips trước rồi mới quy ra giá

**Bài tập 3 (Economic Calendar)**:
- Các sự kiện High Impact quan trọng nhất: Fed Rate Decision, US CPI, US NFP, GDP
- Khi Actual > Forecast cho dữ liệu kinh tế tích cực (NFP, GDP, CPI nếu đang chống lạm phát) → USD thường tăng
- Cẩn thận: Đôi khi thị trường phản ứng ngược lại với logic (called "buy the rumor, sell the news")

**Bài tập 4 (Finviz)**:
- Kết quả screener sẽ thay đổi theo thời gian thực vì giá và chỉ số thay đổi hàng ngày
- Không cần chọn cổ phiếu "đúng nhất" — mục tiêu là học cách dùng công cụ
- Khi phân tích sâu, kết hợp cả fundamental (từ Finviz) lẫn technical (từ TradingView) — đây chính là cách bạn đã học suốt 62 ngày

**Bài tập 5 (Personal Toolkit)**:
- Personal Toolkit là tài liệu sống — cập nhật liên tục khi bạn tìm thêm công cụ tốt hơn
- Cam kết cá nhân quan trọng nhất: **Ít nhất 3-6 tháng demo trước khi live** — đây không phải lý thuyết mà là quy tắc bảo vệ vốn thực sự

### Case Study — Gợi ý đáp án

**Câu 1**: Swing trading cổ phiếu → Xác định xu hướng trên **1W (Weekly)** hoặc **1D (Daily)** → Tìm điểm vào trên **4H** hoặc **1D**. Không dùng timeframe nhỏ hơn 4H vì noise quá nhiều cho swing trading.

**Câu 2**: Bộ lọc phù hợp swing trading: P/E dưới 25 (không quá đắt), Market Cap Large+ (thanh khoản tốt), EPS growth dương, Average Volume > 1M (không bị trap trong cổ phiếu ít người mua). Thêm tiêu chí kỹ thuật: 52W High (gần đỉnh cao nhất năm = momentum tốt).

**Câu 3**: 2% của $5,000 = $100. Mỗi lệnh tối đa chịu lỗ $100. Đây là số tiền bạn dùng để tính SL kết hợp với position size.

**Câu 4**: Kiểm tra NFP tại Investing.com Economic Calendar vào thứ Sáu đầu tháng. Nếu NFP tốt (nhiều việc làm được tạo ra hơn dự kiến) → USD mạnh lên → Ảnh hưởng cổ phiếu xuất khẩu Mỹ tiêu cực. Chiến lược: Tránh vào lệnh mới 1-2 ngày trước và ngay sau NFP; chờ thị trường ổn định lại.
