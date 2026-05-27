# Ngày 63: Công cụ & Nền tảng Giao dịch — Hướng dẫn Thực chiến

## Mục tiêu học tập
- [ ] Biết cách sử dụng TradingView để đọc biểu đồ, vẽ trendline và dùng indicator cơ bản
- [ ] Hiểu giao diện MetaTrader 4/5 và biết cách đặt lệnh cơ bản
- [ ] Biết tìm kiếm dữ liệu kinh tế trên Investing.com, Trading Economics, Macrotrends
- [ ] Biết dùng Screener để lọc cổ phiếu/crypto phù hợp tiêu chí
- [ ] Xây dựng bộ công cụ cá nhân (Personal Toolkit) hoàn chỉnh cho từng thị trường

---

## Nội dung bài giảng

### 1. Tại sao cần làm chủ công cụ trước khi giao dịch thật?

Hãy tưởng tượng bạn vừa học xong bằng lái xe — bạn biết lý thuyết về tăng số, phanh, nhường đường. Nhưng nếu lần đầu ngồi vào xe thật bạn không biết nút khởi động ở đâu, đèn xi-nhan bên nào... thì vẫn rất nguy hiểm.

Giao dịch tài chính cũng vậy. Sau 62 ngày bạn đã có kiến thức nền tảng vững chắc: phân tích cơ bản, phân tích kỹ thuật, quản lý rủi ro, tâm lý giao dịch. Nhưng nếu không biết cách dùng công cụ, bạn sẽ:

- **Bỏ lỡ tín hiệu giao dịch** vì không biết cài indicator đúng cách
- **Thao tác sai lệnh** — muốn đặt Limit Order nhưng lại bấm Market Order, mua giá sai ngay lập tức
- **Không tra được dữ liệu kinh tế** đúng lúc, mất cơ hội hoặc bị bẫy bởi tin tức
- **Quản lý danh mục lộn xộn** vì không có hệ thống theo dõi

Ngày 63 này là buổi thực hành thiết lập toàn bộ bộ công cụ (toolkit) của bạn — như chuẩn bị vũ khí trước khi ra trận.

---

### 2. TradingView — Nền tảng biểu đồ phổ biến cho nhiều thị trường

**TradingView** là nền tảng biểu đồ (charting platform) rất phổ biến, được dùng bởi nhiều trader/investor ở các thị trường như cổ phiếu, forex, crypto, hàng hóa. Điểm mạnh: bản miễn phí đã đủ để người mới luyện đọc chart, vẽ trendline và đặt alert cơ bản.

#### 2.1. Tạo tài khoản và giao diện tổng quan

Truy cập **tradingview.com** → Đăng ký miễn phí bằng email hoặc Google. Giao diện chính gồm:

```
┌─────────────────────────────────────────────────┐
│  [Logo] [Search Bar] [Markets] [News] [Community]│  ← Thanh điều hướng
├──────────┬──────────────────────────────────────┤
│          │                                      │
│ Watchlist│         Khu vực biểu đồ chính        │
│ (Danh    │         (Chart Area)                 │
│  sách    │                                      │
│  theo    │                                      │
│  dõi)    │                                      │
│          │                                      │
├──────────┴──────────────────────────────────────┤
│  [Symbol] [Timeframe] [Indicators] [Tools Bar]  │  ← Toolbar biểu đồ
└─────────────────────────────────────────────────┘
```

#### 2.2. Tìm kiếm symbol (mã giao dịch)

Nhấn vào **Search Bar** (hoặc phím tắt `/`) và gõ theo định dạng:

| Thị trường | Cú pháp | Ví dụ |
|------------|---------|-------|
| Cổ phiếu Việt Nam | Chọn đúng sàn như `HOSE:MÃ`, `HNX:MÃ`, `UPCOM:MÃ` | `HOSE:VNM`, `HOSE:FPT`, `HOSE:HPG` |
| Cổ phiếu Mỹ | `NASDAQ:MÃ` hoặc `NYSE:MÃ` | `NASDAQ:AAPL`, `NYSE:BRK.A` |
| Crypto | `BINANCE:MÃ` | `BINANCE:BTCUSDT`, `BINANCE:ETHUSDT` |
| Forex | `FX:CẶP` | `FX:EURUSD`, `FX:USDJPY` |
| Chỉ số | Tên thẳng | `VNI` (VN-Index), `SPX` (S&P 500) |

> **Mẹo**: Nếu không nhớ tên đầy đủ, chỉ cần gõ tên công ty (VD: "Vinamilk") TradingView sẽ tự gợi ý.

**Mô tả screenshot bằng text:** Ô tìm kiếm nằm ở góc trên bên trái. Khi gõ `HOSE:VNM`, danh sách kết quả nên hiển thị nhóm `Stocks` và sàn `HOSE`; chọn đúng dòng này thay vì CFD hoặc nguồn dữ liệu không rõ.

#### 2.3. Timeframe — Chọn khung thời gian phù hợp mục đích

**Timeframe** (khung thời gian) là khoảng thời gian mỗi nến đại diện:

| Timeframe | Dùng cho | Phù hợp với ai |
|-----------|----------|----------------|
| 1m, 5m, 15m | Scalping (giao dịch siêu ngắn) | Trader chuyên nghiệp, không dành cho người mới |
| 1H (1 giờ) | Day Trading (giao dịch trong ngày) | Trader bán thời gian, cần theo dõi liên tục |
| 4H (4 giờ) | Swing Trading (nắm vài ngày-vài tuần) | Người có công việc toàn thời gian — thường dễ theo dõi hơn khung quá ngắn |
| 1D (1 ngày) | Position Trading, đầu tư trung hạn | Nhà đầu tư dài hạn |
| 1W (1 tuần) | Đầu tư dài hạn, xác định xu hướng lớn | Investor |

**Quy tắc Multi-timeframe**: Luôn xem timeframe lớn hơn để xác định xu hướng, sau đó xuống timeframe nhỏ hơn để tìm điểm vào lệnh. Ví dụ: xem 1D để biết xu hướng → xem 4H để vào lệnh.

#### 2.4. Thêm Indicator (chỉ báo kỹ thuật)

Nhấn nút **"Indicators"** trên toolbar → Tìm kiếm tên indicator → Click để thêm vào biểu đồ.

Các indicator cơ bản cần biết (đã học ở Ngày 30-31):

```
Thêm vào biểu đồ:
├── MA (Moving Average) — EMA 20 màu xanh lá, EMA 50 màu cam
├── RSI (Relative Strength Index) — hiển thị dưới biểu đồ chính
├── MACD — hiển thị dưới RSI
└── Bollinger Bands — hiển thị trên biểu đồ chính
```

**Cách chỉnh thông số**: Double-click vào tên indicator để mở Settings. Ví dụ RSI mặc định là 14 kỳ — bạn có thể đổi thành 9 (nhạy hơn) hoặc 21 (mượt hơn).

#### 2.5. Vẽ trendline, Support/Resistance, Fibonacci

Thanh công cụ bên trái biểu đồ có đầy đủ công cụ vẽ:

```
Thanh công cụ vẽ (Drawing Tools):
├── ╱  Trendline — kéo từ đáy/đỉnh này đến đáy/đỉnh khác
├── ═  Horizontal Line — vẽ đường Support/Resistance ngang
├── ⬡  Fibonacci Retracement — kéo từ đáy lên đỉnh (uptrend) 
│                              hoặc đỉnh xuống đáy (downtrend)
├── 📐 Pitchfork — kênh giá theo xu hướng
└── 📝 Text — thêm ghi chú lên biểu đồ
```

**Mẹo vẽ S/R hiệu quả**: Tìm các vùng giá mà nến thường "bật lại" nhiều lần — đó là vùng Support hoặc Resistance quan trọng. Vẽ vùng (zone) thay vì đường thẳng chính xác, vì giá thường chạm vào và đảo chiều trong một vùng, không phải một điểm.

#### 2.6. Alert — Cảnh báo giá tự động

Đây là tính năng cực kỳ hữu ích cho người bận rộn. Thay vì ngồi canh màn hình cả ngày, bạn đặt Alert để TradingView thông báo khi giá đến vùng quan trọng.

**Cách đặt Alert**:
1. Nhấn chuột phải vào biểu đồ → "Add Alert"
2. Hoặc nhấn phím `Alt + A`
3. Chọn điều kiện: "Price crossing" (giá cắt qua), "Greater than" (lớn hơn), "Less than" (nhỏ hơn)
4. Nhập mức giá mục tiêu
5. Chọn thông báo: Popup, Email, hoặc Webhook (cho automation nâng cao)

**Ví dụ thực tế**: BTC hiện ở $65,000. Bạn thấy kháng cự mạnh tại $68,500. Đặt Alert: "BTCUSDT > 68500" → Khi giá chạm 68,500, điện thoại bạn sẽ rung, bạn mở app xem có đủ điều kiện vào lệnh không.

#### 2.7. Paper Trading trên TradingView

**Paper Trading** (giao dịch giả lập) cho phép bạn mua/bán trên biểu đồ TradingView mà không dùng tiền thật. Tính năng này có ở tài khoản miễn phí.

Nhấn nút **"Paper Trading"** ở dưới cùng biểu đồ → Bắt đầu với $100,000 ảo. Tuy nhiên, bản miễn phí chỉ giả lập được trên 1 tài khoản. Muốn kết nối broker thật, cần tài khoản Pro ($14.95/tháng).

---

### 3. MetaTrader 4 & MetaTrader 5 (MT4/MT5) — Nền tảng Forex chuẩn

Như đã học ở Ngày 51 về Broker và Platform, **MetaTrader** (MT4 và MT5) là nền tảng giao dịch phổ biến nhất cho Forex. Hầu hết broker đều hỗ trợ MT4/MT5.

**Sự khác biệt MT4 vs MT5**:
- **MT4**: Ra đời 2005, chỉ tập trung Forex, cộng đồng script (EA) lớn hơn, nhẹ hơn
- **MT5**: Phiên bản mới hơn (2010), hỗ trợ thêm cổ phiếu và hàng hóa, có thêm Order Types, 21 timeframe vs 9 của MT4

Người mới nên dùng **MT4** vì đơn giản hơn và hầu hết tài liệu học Forex đều lấy MT4 làm ví dụ.

#### 3.1. Tải và cài đặt MT4/MT5

1. Truy cập website của broker có giấy phép rõ ràng và tự verify trên website cơ quan quản lý như FCA, ASIC, CySEC hoặc cơ quan tương đương
2. Tải MetaTrader 4 từ trang của broker (tránh tải từ nguồn không rõ)
3. Cài đặt theo hướng dẫn, chọn "Open an Account" → Demo Account

#### 3.2. Giao diện MT4 — Tổng quan

```
┌──────────────────────────────────────────────────────────┐
│  File | View | Insert | Charts | Tools | Window | Help   │  ← Menu bar
├──────────────────────────────────────────────────────────┤
│  [toolbar: New Order | Chart Zoom | Indicators | ...]    │  ← Toolbar
├──────────┬───────────────────────────┬───────────────────┤
│          │                           │                   │
│ Market   │    Khu vực biểu đồ        │    Navigator      │
│ Watch    │    (Chart Window)         │    (Danh sách     │
│ (Bảng    │                           │     indicator,    │
│ giá thị  │                           │     EA, scripts)  │
│ trường)  │                           │                   │
├──────────┴───────────────────────────┴───────────────────┤
│  Terminal: Trade | Account History | News | Alerts       │  ← Terminal
└──────────────────────────────────────────────────────────┘
```

**Các khu vực chính**:
- **Market Watch**: Danh sách các cặp tiền và giá Bid/Ask real-time. Chuột phải → "Show All" để xem tất cả symbol
- **Navigator**: Chứa danh sách tài khoản, indicator, Expert Advisors (EA — robot giao dịch), Scripts
- **Terminal**: Nơi quản lý lệnh đang mở (tab Trade), lịch sử (Account History), tin tức, cảnh báo
- **Chart Area**: Khu vực hiển thị biểu đồ. Có thể mở nhiều biểu đồ cùng lúc

#### 3.3. Đặt lệnh trong MT4

Nhấn **F9** hoặc double-click vào symbol trong Market Watch để mở cửa sổ đặt lệnh:

```
┌─────────────────────────────────┐
│  Order:  [Market Execution ▼]   │
│  Symbol: EURUSD                 │
│  Volume: [0.01 ▼]  (Lot size)   │
│  Stop Loss:    [1.0750      ]   │
│  Take Profit:  [1.0900      ]   │
│  Comment: [ghi chú tùy chọn ]   │
│                                 │
│  [  Sell (Bid: 1.0820)  ]       │
│  [  Buy  (Ask: 1.0822)  ]       │
└─────────────────────────────────┘
```

**Order Types** (loại lệnh):

| Loại lệnh | Mô tả | Dùng khi nào |
|------------|-------|--------------|
| **Market Order** | Mua/bán ngay tại giá thị trường | Muốn vào lệnh ngay lập tức |
| **Buy Limit** | Đặt lệnh mua tại giá thấp hơn giá hiện tại | Chờ giá kéo về vùng hỗ trợ để mua |
| **Sell Limit** | Đặt lệnh bán tại giá cao hơn giá hiện tại | Chờ giá tăng lên kháng cự để bán |
| **Buy Stop** | Đặt lệnh mua tại giá cao hơn giá hiện tại | Mua khi giá breakout lên trên |
| **Sell Stop** | Đặt lệnh bán tại giá thấp hơn giá hiện tại | Bán khi giá breakdown xuống dưới |

**Ví dụ thực tế**:
- EURUSD đang ở 1.0822
- Bạn thấy hỗ trợ mạnh tại 1.0780 → Đặt **Buy Limit** tại 1.0780
- Bạn đặt SL (Stop Loss) tại 1.0750, TP (Take Profit) tại 1.0900
- Nếu giá giảm về 1.0780, lệnh tự động được kích hoạt

#### 3.4. Quản lý lệnh đang mở

Trong tab **Trade** của Terminal, bạn thấy danh sách tất cả lệnh đang mở. Chuột phải vào lệnh để:
- **Modify or Delete Order**: Sửa SL/TP, hoặc xóa lệnh pending
- **Close Order**: Đóng lệnh tại giá thị trường hiện tại
- **Trailing Stop** (dừng lỗ di động): SL tự động di chuyển theo giá khi giá đi đúng hướng

**Trailing Stop** là tính năng rất hữu ích: Ví dụ bạn đặt Trailing Stop 30 pip. Khi giá tăng 30 pip, SL tự động dịch lên 30 pip theo — bảo vệ lợi nhuận trong khi vẫn để giá chạy tiếp.

---

### 4. Nền tảng chứng khoán Việt Nam

Thị trường chứng khoán Việt Nam có hệ thống lệnh và giao diện khác với quốc tế. Đây là những điều cần biết:

#### 4.1. Các công ty chứng khoán (broker) uy tín tại VN

| Tên | App/Platform | Điểm nổi bật |
|-----|-------------|--------------|
| **DNSE** | Entrade X | Giao diện hiện đại, phí 0 đồng/lệnh, phổ biến với người trẻ |
| **SSI** | iBoard, SSI iInvest | Thương hiệu lớn tại VN, dữ liệu tốt, phí có thể cao hơn |
| **VPS** | SmartOne | Phân tích kỹ thuật tốt, phí thấp |
| **MBS** | MBS Online | Của MB Bank, tích hợp ngân hàng tiện lợi |
| **VCBS** | VCBS Online | Của Vietcombank, an toàn, phù hợp người thận trọng |

#### 4.2. Đọc bảng giá chứng khoán VN

Bảng giá VN có màu sắc đặc trưng:

```
Màu sắc bảng giá:
├── 🟣 Tím/Tím tía: Giá Trần (giá tăng tối đa trong ngày, +7% sàn HOSE)
├── 🟢 Xanh lá: Giá tăng (dưới Trần)
├── 🟡 Vàng: Giá Tham chiếu (giá đóng cửa hôm qua)
├── 🔴 Đỏ: Giá giảm (trên Sàn)
└── 🔵 Xanh dương: Giá Sàn (giá giảm tối đa trong ngày, -7% sàn HOSE)
```

**Giải thích Trần/Sàn/Tham chiếu**:
- **Giá Tham chiếu** (Reference Price): Giá đóng cửa ngày hôm trước — đây là mốc tính biên độ
- **Giá Trần** (Ceiling Price): Giá tăng tối đa = Tham chiếu × 1.07 (HOSE); ×1.10 (HNX); ×1.15 (UPCOM)
- **Giá Sàn** (Floor Price): Giá giảm tối đa = Tham chiếu × 0.93 (HOSE); ×0.90 (HNX); ×0.85 (UPCOM)

**Hệ thống lệnh trên HOSE**:

| Lệnh | Tên đầy đủ | Mô tả |
|------|-----------|-------|
| **LO** | Limit Order | Lệnh giới hạn giá — phổ biến nhất, tự chọn giá mua/bán |
| **ATO** | At The Opening | Khớp lệnh tại giá mở cửa (chỉ đặt 8:45-9:00) |
| **ATC** | At The Close | Khớp lệnh tại giá đóng cửa (chỉ đặt 14:30-14:45) |
| **MP** | Market Price | Lệnh thị trường (chỉ có trên HNX) |

#### 4.3. Công cụ phân tích cổ phiếu VN

- **FireAnt** (fireant.vn): Mạng xã hội đầu tư + phân tích cơ bản, xem BCTC, tin tức real-time
- **Simplize** (simplize.com): Điểm chất lượng doanh nghiệp, so sánh ngành, phân tích dễ hiểu
- **CafeF** (cafef.vn): Tin tức tài chính, dữ liệu BCTC, diễn đàn đầu tư
- **Vietstock** (vietstock.vn): Phân tích kỹ thuật, screener cổ phiếu VN

---

### 5. Sàn giao dịch Crypto — CEX & DEX

Như đã học ở Ngày 57, có hai loại sàn crypto: **CEX** (Centralized Exchange — sàn tập trung) và **DEX** (Decentralized Exchange — sàn phi tập trung).

#### 5.1. Binance — Một CEX quy mô lớn

**Binance** là một sàn crypto có khối lượng giao dịch lớn, thường được người mới dùng làm ví dụ học giao diện CEX vì:
- Giao diện đầy đủ tính năng nhưng có chế độ "Lite" đơn giản hơn
- Có app mobile tiện lợi
- Phí thấp (0.1% mặc định, giảm nếu dùng BNB)
- Nhiều đồng coin được niêm yết

**Giao diện Spot Trading trên Binance**:
```
┌────────────────────────────────────────────────────────────┐
│  [BTC/USDT ▼]   Giá: 65,234  +2.34%                       │  ← Chọn cặp giao dịch
├──────────────────────┬─────────────────────────────────────┤
│                      │  Order Book (Sổ lệnh):              │
│   Biểu đồ giá        │  65,250  0.5 BTC  (Ask - màu đỏ)   │
│   (TradingView       │  65,240  1.2 BTC                    │
│    tích hợp)         │  65,234  ← Giá hiện tại             │
│                      │  65,220  0.8 BTC  (Bid - màu xanh)  │
│                      │  65,210  2.1 BTC                    │
├──────────────────────┴──────────────────────┬──────────────┤
│  Đặt lệnh:                                  │ Lịch sử      │
│  [Limit | Market | Stop-Limit]              │ giao dịch    │
│  Giá:  [65,200        ]                     │ gần đây      │
│  SL:   [0.001 BTC     ]                     │              │
│  [  Mua BTC  ] [  Bán BTC  ]                │              │
└─────────────────────────────────────────────┴──────────────┘
```

#### 5.2. OKX và Bybit

- **OKX**: Mạnh về Derivatives (hợp đồng tương lai), có Web3 wallet tích hợp
- **Bybit**: Phổ biến với các trader dùng Futures/Perpetuals, giao diện chuyên nghiệp, nhiều sự kiện airdrop

Cả hai sàn đều có giao diện và tính năng tương tự Binance. Khi đã quen Binance, chuyển sang OKX/Bybit sẽ rất dễ.

#### 5.3. Uniswap — DEX phổ biến nhất trên Ethereum

**Uniswap** là DEX (sàn phi tập trung) — giao dịch trực tiếp từ ví, không cần đăng ký tài khoản.

**Các bước dùng Uniswap**:
1. Cài **MetaMask** (ví crypto trên trình duyệt) — tải từ metamask.io
2. Nạp ETH vào MetaMask
3. Truy cập **app.uniswap.org**
4. Nhấn "Connect Wallet" → Chọn MetaMask → Xác nhận kết nối
5. Chọn token muốn swap (đổi), nhập số lượng → Confirm trong MetaMask

> **Lưu ý quan trọng**: DEX không có team hỗ trợ. Nếu bị lừa (phishing, fake token) sẽ không thể lấy lại tiền. Luôn verify địa chỉ contract token từ CoinGecko hoặc CoinMarketCap.

#### 5.4. Công cụ nghiên cứu Crypto

Như đã học ở Ngày 58 (Crypto Fundamental Analysis), đây là các công cụ quan trọng:

| Công cụ | Link | Dùng để làm gì |
|---------|------|----------------|
| **CoinMarketCap** | coinmarketcap.com | Market cap, giá, volume, thông tin token cơ bản |
| **CoinGecko** | coingecko.com | Tương tự CMC, đáng tin hơn về dữ liệu DeFi |
| **DefiLlama** | defillama.com | Theo dõi TVL (Total Value Locked) toàn bộ DeFi |
| **Dune Analytics** | dune.com | On-chain data dashboard, phân tích deep |
| **Glassnode** | glassnode.com | On-chain metrics: MVRV, NUPL, Puell Multiple (đã học Ngày 61) |

---

### 6. Công cụ tra cứu dữ liệu kinh tế vĩ mô

Như đã học ở Ngày 16 (Economic Calendar), biết đọc dữ liệu kinh tế đúng lúc là lợi thế cạnh tranh lớn.

#### 6.1. Investing.com — Trang tổng hợp dữ liệu phổ biến

**Investing.com** là trang web tài chính tổng hợp phổ biến, cung cấp:

- **Economic Calendar**: Lịch các sự kiện kinh tế quan trọng. Vào *investing.com/economic-calendar*, lọc "High Impact" để chỉ xem tin quan trọng
- **Real-time Quotes**: Giá real-time của mọi loại tài sản
- **News**: Tin tức tài chính từ khắp thế giới
- **Analysis**: Phân tích kỹ thuật tự động cho từng symbol

**Cách đọc Economic Calendar**:
```
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────┐
│ Time     │ Country  │ Event    │ Actual   │ Forecast │ Prev │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────┤
│ 20:30    │ 🇺🇸 USD  │ CPI m/m  │ 0.4%     │ 0.3%     │ 0.2% │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────┘
         ↑ Đọc cách phân tích:
         Actual > Forecast → Bất ngờ tích cực → USD thường tăng (nếu là CPI thì Fed có thể giữ lãi suất cao → USD tăng)
         Actual < Forecast → Bất ngờ tiêu cực → USD thường giảm
```

#### 6.2. Trading Economics

**Trading Economics** (tradingeconomics.com) cung cấp dữ liệu lịch sử của 196 quốc gia. Điểm đặc biệt:
- Biểu đồ dài hạn các chỉ số kinh tế (GDP, CPI, lãi suất từ nhiều thập kỷ trước)
- Forecast (dự báo) dữ liệu kinh tế tương lai
- So sánh giữa các quốc gia dễ dàng

**Ứng dụng**: Muốn biết xu hướng lạm phát của Mỹ trong 10 năm qua? Muốn so sánh tốc độ tăng trưởng GDP Việt Nam vs Thái Lan? Trading Economics là công cụ lý tưởng.

#### 6.3. Macrotrends

**Macrotrends** (macrotrends.net) là kho dữ liệu biểu đồ dài hạn tuyệt vời:
- P/E ratio lịch sử của S&P 500 (từ 1880 đến nay)
- Lãi suất Fed Fund Rate qua các thập kỷ
- Giá dầu, vàng, USD Index theo lịch sử dài
- EPS growth, Revenue growth của từng cổ phiếu Mỹ

**Ứng dụng thực tế**: Như đã học ở Ngày 22 về Valuation Ratios — muốn biết P/E hiện tại của S&P 500 có đắt không? So sánh với P/E lịch sử trung bình (~16-17x) trên Macrotrends.

#### 6.4. FRED — Dữ liệu chính thức từ Federal Reserve

**FRED** (Federal Reserve Economic Data) tại *fred.stlouisfed.org* là nguồn dữ liệu kinh tế chính thức và đáng tin cậy nhất:
- Hàng trăm nghìn data series kinh tế của Mỹ và toàn cầu
- Dữ liệu miễn phí, có thể tải về
- API cho developer
- Biểu đồ tùy chỉnh, so sánh nhiều chỉ số

**Ví dụ dùng FRED**: Muốn xem mối tương quan giữa Fed Funds Rate và tỷ lệ thất nghiệp? FRED cho phép bạn vẽ 2 chỉ số trên cùng 1 biểu đồ, visualize Phillips Curve ngay lập tức.

---

### 7. Công cụ Screener — Lọc cổ phiếu & crypto

**Screener** (bộ lọc cổ phiếu/crypto) là công cụ giúp bạn tìm những cổ phiếu/coin phù hợp tiêu chí đầu tư của bạn từ hàng nghìn lựa chọn. Thay vì phải xem từng mã một, screener lọc xuống còn 10-20 ứng viên để bạn phân tích sâu hơn.

#### 7.1. Finviz — Screener cổ phiếu Mỹ phổ biến

**Finviz** (finviz.com) là screener cổ phiếu Mỹ phổ biến, có bản miễn phí với tính năng cơ bản.

**Cách dùng Finviz Screener**:
1. Vào *finviz.com/screener.ashx*
2. Chọn tab **Fundamental** để lọc theo các chỉ số cơ bản
3. Ví dụ bộ lọc "Cổ phiếu tăng trưởng chất lượng":
   - P/E: Under 20
   - Market Cap: Large ($10bln and more)
   - EPS growthY over Y: Over 10%
   - Debt/Equity: Under 1
   - ROE: Over 15%
4. Nhấn **Screener** → Xem danh sách kết quả

#### 7.2. Stock Screener trên TradingView

TradingView có screener tích hợp cho cổ phiếu Việt Nam, Mỹ và nhiều thị trường khác. Ưu điểm: kết hợp lọc cả fundamental lẫn technical.

**Cách vào**: Menu trên → "Stock Screener" hoặc shortcut `/screener`

#### 7.3. CafeF Screener (cổ phiếu VN)

Truy cập *cafef.vn/thi-truong-chung-khoan/loc-co-phieu.chn* để lọc cổ phiếu Việt Nam theo:
- P/E, P/B, ROE, ROA
- Doanh thu, lợi nhuận tăng trưởng
- Ngành nghề, sàn niêm yết

#### 7.4. CoinMarketCap Screener (Crypto)

Trên CoinMarketCap, vào mục **Screener** để lọc crypto theo:
- Market Cap (vốn hóa thị trường)
- Volume 24h (khối lượng giao dịch)
- % Change 24h/7d/30d (mức thay đổi giá)
- Category (DeFi, Layer 1, Gaming...)

---

### 8. Công cụ quản lý danh mục & theo dõi hiệu suất

Đây là phần mà nhiều nhà đầu tư mới bỏ qua nhưng cực kỳ quan trọng. Như đã học ở Ngày 41 (Portfolio Management), bạn cần biết hiệu suất danh mục của mình và so sánh với benchmark.

#### 8.1. Google Sheets / Excel — Đơn giản nhưng hiệu quả

Tự tạo một spreadsheet theo dõi danh mục với các cột:

```
| Mã CP | Tên | Ngày mua | Giá mua | Số lượng | Giá hiện tại | Lãi/Lỗ | % Lãi/Lỗ | % Danh mục |
|-------|-----|----------|---------|----------|--------------|---------|-----------|------------|
| FPT   | FPT | 01/03    | 95,000  | 100      | 105,000      | +1M     | +10.5%    | 25%        |
```

Dùng hàm `GOOGLEFINANCE` trong Google Sheets nếu mã/sàn được hỗ trợ; với cổ phiếu Việt Nam, hãy kiểm tra lại cú pháp mã trên Google Finance hoặc nhập/import dữ liệu từ nguồn chính thức của công ty chứng khoán.

#### 8.2. Portfolio Visualizer

**Portfolio Visualizer** (portfoliovisualizer.com) là công cụ có bản miễn phí/hạn chế và các gói trả phí cho:
- Backtest danh mục (nếu mua X% cổ phiếu này Y% cổ phiếu kia từ 10 năm trước, kết quả thế nào?)
- Monte Carlo Simulation (mô phỏng ngẫu nhiên các kịch bản tương lai)
- Phân tích tương quan giữa các tài sản

#### 8.3. Delta / CoinStats (Crypto Portfolio Tracker)

- **Delta** (delta.app): Theo dõi danh mục crypto đa sàn, tích hợp API từ Binance, Coinbase
- **CoinStats**: Tương tự Delta, có phân tích DeFi portfolio

---

### 9. Tin tức & nguồn thông tin đáng tin cậy

Thông tin sai lệch trong đầu tư có thể gây tổn thất nghiêm trọng. Chọn nguồn tin đáng tin cậy là kỹ năng quan trọng.

#### 9.1. Tài chính quốc tế (Tiếng Anh)

| Nguồn | Điểm mạnh | Phù hợp với |
|-------|-----------|-------------|
| **Bloomberg** | Dữ liệu real-time, phân tích chuyên sâu | Professional, có phí |
| **Reuters** | Tin tức nhanh, khách quan | Mọi người dùng |
| **Financial Times** | Phân tích macro sâu sắc | Nhà đầu tư dài hạn |
| **Wall Street Journal** | Tin tức doanh nghiệp, thị trường Mỹ | Trader cổ phiếu Mỹ |
| **CNBC** | Video, interview với các nhà đầu tư nổi tiếng | Người mới bắt đầu |

#### 9.2. Crypto (Tiếng Anh)

- **CoinDesk**: Tin tức crypto phổ biến, có phân tích sâu
- **The Block**: Nghiên cứu on-chain, báo cáo chuyên sâu
- **Decrypt**: Giải thích dễ hiểu cho người mới
- **Bankless**: Podcast & newsletter về DeFi/Ethereum

#### 9.3. Chứng khoán VN

- **CafeF** (cafef.vn): Tin tức doanh nghiệp, BCTC, thị trường
- **Vietstock** (vietstock.vn): Phân tích kỹ thuật, tin tức
- **HOSE** (hsx.vn): Thông tin chính thức từ Sở giao dịch
- **SSC** (ssc.gov.vn): Ủy ban Chứng khoán Nhà nước — thông báo chính thức

#### 9.4. Podcast & YouTube học đầu tư

- **We Study Billionaires** (Podcast): Phân tích chiến lược của các nhà đầu tư huyền thoại
- **Lex Fridman Podcast** (YouTube): Phỏng vấn sâu về crypto, AI, công nghệ
- **Adam Khoo** (YouTube): Giảng dạy trading và đầu tư dễ hiểu
- **Aswath Damodaran** (YouTube): Giáo sư NYU — bậc thầy về Valuation

---

### 10. Cảnh báo scam platform và checklist verify

Trước khi nạp tiền thật vào bất kỳ broker, CEX, DEX, app portfolio hoặc nền tảng copy trade nào, hãy kiểm tra:

- **Giấy phép**: Tra trực tiếp trên website cơ quan quản lý, không chỉ tin logo trên trang broker.
- **Domain**: Gõ tay địa chỉ hoặc dùng bookmark; tránh link quảng cáo, link Telegram/Zalo, domain gần giống tên thật.
- **Rút tiền thử**: Nếu bắt buộc dùng tiền thật, thử số tiền nhỏ và kiểm tra quy trình rút trước khi tăng vốn.
- **Seed phrase/private key**: Không nhập vào website lạ, Google Form, bot hỗ trợ hoặc "airdrop checker".
- **Cam kết lợi nhuận**: Bất kỳ nền tảng nào hứa lợi nhuận cố định cao, không rủi ro, hoặc ép nạp thêm để rút tiền đều phải xem là cảnh báo đỏ.

**Mô tả screenshot bằng text:** Một trang verify broker hợp lệ thường có tên pháp nhân, số giấy phép, quốc gia đăng ký, trạng thái giấy phép và domain chính thức. Nếu thông tin trên website broker không khớp với registry của cơ quan quản lý, không nạp tiền.

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **TradingView là công cụ biểu đồ rất hữu ích** cho nhiều trader/investor — có bản miễn phí, đa thị trường, tích hợp indicator và công cụ vẽ. Ưu tiên thiết lập đây trước.

2. **MT4/MT5 là chuẩn công nghiệp cho Forex** — học cách đặt pending orders (Buy Limit, Sell Limit, Buy Stop, Sell Stop) và quản lý SL/TP là kỹ năng căn bản không thể thiếu.

3. **Screener giúp bạn tiết kiệm thời gian** — thay vì xem 1,000 cổ phiếu, dùng Finviz/TradingView Screener để lọc xuống 10-20 ứng viên phù hợp tiêu chí, rồi mới phân tích sâu.

4. **Investing.com + FRED + Macrotrends là bộ ba thiết yếu** để theo dõi dữ liệu vĩ mô — đặc biệt quan trọng trước các sự kiện như Fed Meeting, CPI, NFP.

5. **Bộ công cụ cá nhân (Personal Toolkit) cần được thiết lập một lần đúng cách** — tài khoản demo, bookmark, alert, trading journal. Đầu tư 2-3 tiếng thiết lập ban đầu sẽ tiết kiệm hàng trăm giờ sau này và tránh nhiều sai lầm tốn kém.

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|-------------------|-----------------|
| TradingView | Nền tảng biểu đồ | Web/app xem biểu đồ, phân tích kỹ thuật đa thị trường |
| MT4/MT5 (MetaTrader) | Phần mềm giao dịch | Nền tảng giao dịch Forex chuẩn ngành |
| Screener | Bộ lọc cổ phiếu/crypto | Công cụ lọc tài sản theo tiêu chí tùy chọn |
| FRED | Dữ liệu kinh tế Fed | Cơ sở dữ liệu kinh tế của Cục dự trữ Liên bang Mỹ |
| Pending Order | Lệnh chờ | Lệnh sẽ kích hoạt khi giá đạt mức định trước |
| Buy Limit | Lệnh mua giới hạn | Đặt lệnh mua tại giá thấp hơn giá hiện tại |
| Sell Limit | Lệnh bán giới hạn | Đặt lệnh bán tại giá cao hơn giá hiện tại |
| Buy Stop | Lệnh mua dừng | Đặt lệnh mua khi giá tăng vượt qua mức định sẵn |
| Sell Stop | Lệnh bán dừng | Đặt lệnh bán khi giá giảm phá mức định sẵn |
| Trailing Stop | Dừng lỗ di động | SL tự động dịch chuyển theo hướng có lợi |
| Paper Trading | Giao dịch giả lập | Giao dịch với tiền ảo để luyện tập, không rủi ro |
| CEX | Sàn giao dịch tập trung | Sàn crypto do công ty vận hành (Binance, OKX) |
| DEX | Sàn giao dịch phi tập trung | Sàn crypto chạy tự động qua smart contract (Uniswap) |
| TVL | Tổng giá trị khóa | Tổng tài sản đang được khóa trong protocol DeFi |
| ATO | At The Opening | Lệnh khớp tại giá mở cửa (cổ phiếu VN) |
| ATC | At The Close | Lệnh khớp tại giá đóng cửa (cổ phiếu VN) |
| Alert | Cảnh báo giá | Thông báo tự động khi giá đạt mức định sẵn |

---

## Bài học tiếp theo

Bạn đã hoàn thành toàn bộ 63 ngày của khóa học đầu tư từ A-Z! Hãy quay lại **Ngày 62** để xem lộ trình học tiếp theo:
- Sách nên đọc: The Intelligent Investor, Common Stocks and Uncommon Profits, Market Wizards
- Khóa học nâng cao: CMT (Chartered Market Technician), CFA Level 1
- Cộng đồng: Tham gia các group đầu tư uy tín, tìm mentor

Nhớ quy tắc quan trọng nhất: **Thực hành demo ít nhất 3-6 tháng trước khi dùng tiền thật.**
