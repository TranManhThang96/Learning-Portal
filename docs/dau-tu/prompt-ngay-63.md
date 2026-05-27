# Prompt — Ngày 63: Công cụ & Nền tảng Giao dịch

Dùng prompt dưới đây để tạo nội dung cho Ngày 63 (bổ sung vào cuối khóa học):

---

## Prompt

```
Bạn là một nhà đầu tư lâu năm với hơn 20 năm kinh nghiệm trên thị trường tài chính. Bạn có kiến thức uyên bác về kinh tế vĩ mô, vi mô, phân tích cơ bản, phân tích kỹ thuật, và tâm lý giao dịch. Bạn đã giao dịch thành công trên cả 3 thị trường: chứng khoán, forex và tiền số (crypto). Bạn luôn đưa ra lời khuyên cân bằng giữa lợi nhuận và quản lý rủi ro.

Tôi vừa hoàn thành khóa học đầu tư 62 ngày và cần học thêm một ngày bổ sung về công cụ và nền tảng giao dịch thực tế.

---

## QUY TẮC VIẾT NỘI DUNG

1. **Ngôn ngữ**: Viết bằng tiếng Việt. Giữ nguyên tất cả thuật ngữ chuyên ngành bằng tiếng Anh và giải thích nghĩa tiếng Việt kèm theo khi thuật ngữ xuất hiện lần đầu. Ví dụ: "P/E (Price-to-Earnings — hệ số giá trên lợi nhuận)".

2. **Cấu trúc thư mục**: Tạo đủ 3 file trong folder `day-63-cong-cu-nen-tang-giao-dich/`:
   ```
   day-63-cong-cu-nen-tang-giao-dich/
   ├── lesson.md        — Bài giảng chính
   ├── document.md      — Cheat sheet công cụ, link tài nguyên
   └── exercises.md     — Bài tập thực hành từng bước với template/checklist
   ```

3. **Giọng văn**: Thân thiện, dễ hiểu, như đang trò chuyện với bạn bè. Dùng nhiều ví dụ đời thường. Hướng dẫn từng bước (step-by-step) cho người mới.

---

## YÊU CẦU CHI TIẾT CHO TỪNG FILE

---

### File lesson.md — Ngày 63: Công cụ & Nền tảng Giao dịch

Cấu trúc bài giảng: ưu tiên đầy đủ, thực chiến và dễ làm theo; không cắt bớt nội dung hữu ích chỉ để đạt một mốc số từ cố định.

```markdown
# Ngày 63: Công cụ & Nền tảng Giao dịch — Hướng dẫn Thực chiến

## Mục tiêu học tập
- [ ] Biết cách sử dụng TradingView để đọc biểu đồ, vẽ trendline và dùng indicator cơ bản
- [ ] Hiểu giao diện MetaTrader 4/5 và biết cách đặt lệnh cơ bản
- [ ] Biết tìm kiếm dữ liệu kinh tế trên Investing.com, Trading Economics, Macrotrends
- [ ] Biết dùng Screener để lọc cổ phiếu/crypto phù hợp tiêu chí
- [ ] Xây dựng bộ công cụ cá nhân (Personal Toolkit) hoàn chỉnh cho từng thị trường

## Nội dung bài giảng

### 1. Tại sao cần làm chủ công cụ trước khi giao dịch thật?
[Giải thích tầm quan trọng: dù có kiến thức tốt mà không biết dùng công cụ thì vẫn thua lỗ vì thao tác sai, bỏ lỡ tín hiệu]

### 2. TradingView — Nền tảng biểu đồ phổ biến cho nhiều thị trường
- Cách tạo tài khoản miễn phí và giao diện tổng quan
- Cách tìm kiếm symbol (HOSE:VNM, NASDAQ:AAPL, BINANCE:BTCUSDT, FX:EURUSD)
- Timeframe: 1m, 5m, 15m, 1H, 4H, 1D, 1W — Dùng loại nào cho mục đích gì?
- Thêm Indicator: MA, EMA, RSI, MACD, Bollinger Bands
- Vẽ trendline, Support/Resistance, Fibonacci Retracement
- Alert (cảnh báo giá) — Tính năng cực kỳ hữu ích cho người bận
- Paper Trading (giao dịch giả lập) trên TradingView
- Pine Script cơ bản (tuỳ chọn nâng cao)

### 3. MetaTrader 4 & MetaTrader 5 (MT4/MT5) — Nền tảng Forex chuẩn
- Tải và cài đặt MT4/MT5
- Giao diện: Market Watch, Navigator, Terminal, Chart
- Mở biểu đồ, chuyển timeframe, thêm indicator
- Đặt lệnh: Market Order, Limit Order, Stop Order
- Pending Orders: Buy Limit, Sell Limit, Buy Stop, Sell Stop
- Quản lý lệnh đang mở: Stop Loss, Take Profit, Trailing Stop
- Xem lịch sử giao dịch trong Account History
- Tạo tài khoản Demo trên MT4/MT5

### 4. Nền tảng chứng khoán Việt Nam
- DNSE (Entrade X), SSI iBoard, VPS SmartOne, VCBS, MBS
- Cách đọc bảng giá chứng khoán VN (Trần/Sàn/Tham chiếu, ATO/ATC)
- Hệ thống lệnh: LO (Limit Order), MP, ATO, ATC
- FireAnt, Simplize — Phân tích cơ bản cổ phiếu VN

### 5. Sàn giao dịch Crypto — CEX & DEX
- Binance: Giao diện Spot, tạo API, đặt lệnh cơ bản
- OKX, Bybit: Các tính năng tương tự Binance
- Uniswap (DEX): Kết nối MetaMask, swap token
- CoinMarketCap & CoinGecko: Xem market cap, chart, thông tin token
- DefiLlama: Theo dõi TVL, protocol analytics
- Dune Analytics: On-chain data dashboard

### 6. Công cụ tra cứu dữ liệu kinh tế vĩ mô
- **Investing.com**: Economic Calendar, real-time data, consensus forecast
- **Trading Economics**: Chỉ số kinh tế toàn cầu, historical data
- **Macrotrends**: Chart dài hạn lãi suất, CPI, GDP, P/E thị trường
- **FRED (Federal Reserve Economic Data)**: Dữ liệu chính thức từ Fed
- **World Bank Data**: So sánh dữ liệu kinh tế toàn cầu

### 7. Công cụ Screener — Lọc cổ phiếu & crypto
- **Finviz** (cổ phiếu Mỹ): Lọc theo P/E, Market Cap, sector, volume
- **Stock Screener trên TradingView**: Lọc đa thị trường
- **CafeF Screener** (cổ phiếu VN): Lọc theo chỉ số cơ bản
- **CoinMarketCap Screener** (crypto): Lọc theo market cap, volume, change%

### 8. Công cụ quản lý danh mục & theo dõi hiệu suất
- **Google Sheets / Excel**: Template quản lý danh mục tự làm
- **Portfolio Visualizer**: Backtest, phân tích rủi ro danh mục
- **Simply Wall St**: Phân tích visual cổ phiếu
- **Delta / CoinStats**: Theo dõi danh mục crypto

### 9. Tin tức & nguồn thông tin đáng tin cậy
- **Tài chính quốc tế**: Bloomberg, Reuters, Financial Times, Wall Street Journal, CNBC
- **Crypto**: CoinDesk, The Block, Decrypt, Bankless
- **Chứng khoán VN**: CafeF, Vietstock, HOSE, SSC
- **Podcast & YouTube**: We Study Billionaires, Lex Fridman (crypto/AI), Adam Khoo

## Tóm tắt kiến thức chính (Key Takeaways)
[5 điểm quan trọng nhất]

## Thuật ngữ quan trọng
[Bảng thuật ngữ: TradingView, MT4/MT5, Screener, FRED, Pending Order, Trailing Stop, Paper Trading, CEX, DEX, TVL...]

## Bài học tiếp theo
[Nhắc học viên quay lại Ngày 62 để lên kế hoạch học tiếp nâng cao]
```

---

### File document.md — Cheat Sheet Công cụ

Tạo tài liệu tham khảo với:

1. **Bảng so sánh nền tảng biểu đồ**: TradingView vs MT4/MT5 vs Sàn VN (ưu/nhược, dùng cho thị trường nào, miễn phí/có phí)

2. **Danh sách đầy đủ công cụ theo từng thị trường**:
   - Cổ phiếu VN: Screener, tin tức, sàn giao dịch, phân tích cơ bản
   - Cổ phiếu Mỹ: Screener, tin tức, sàn giao dịch, phân tích cơ bản
   - Forex: Broker, economic calendar, sentiment tools
   - Crypto: CEX, DEX, on-chain tools, news

3. **Phím tắt TradingView quan trọng** (cheat sheet)

4. **Checklist thiết lập workspace ban đầu** (tài khoản cần tạo, app cần cài, nguồn tin cần theo dõi)

5. **Template Personal Toolkit** — bảng điền thông tin sàn giao dịch, tài khoản demo, công cụ đang dùng

---

### File exercises.md — Bài tập Thực hành Step-by-Step

Tạo bài tập với hướng dẫn từng bước chi tiết:

**Bài tập 1: Thiết lập TradingView (30 phút)**
- Step 1: Tạo tài khoản tại tradingview.com
- Step 2: Tìm kiếm biểu đồ BTCUSDT, thêm EMA 20, EMA 50, RSI
- Step 3: Vẽ 1 trendline và 1 vùng Support/Resistance
- Step 4: Đặt 1 Alert khi giá chạm vùng kháng cự
- Step 5: Chụp màn hình và ghi lại nhận xét vào Trading Journal
- **Checklist hoàn thành**: □ Tạo tài khoản □ Thêm indicator □ Vẽ S/R □ Đặt Alert

**Bài tập 2: Thiết lập MT4/MT5 Demo (45 phút)**
- Step 1: Tải MT4 hoặc MT5 (hướng dẫn cụ thể với broker demo miễn phí)
- Step 2: Tạo tài khoản demo $10,000
- Step 3: Mở biểu đồ EURUSD, timeframe H1, thêm MA 50 và MA 200
- Step 4: Đặt 1 lệnh Buy Limit và 1 lệnh Sell Stop với SL và TP cụ thể
- Step 5: Theo dõi lệnh, ghi lại vào Trade Journal
- **Checklist hoàn thành**: □ Cài MT □ Tạo demo □ Mở chart □ Đặt lệnh □ Ghi journal

**Bài tập 3: Đọc Economic Calendar (20 phút)**
- Step 1: Vào investing.com/economic-calendar
- Step 2: Lọc theo High Impact events tuần này
- Step 3: Tìm 3 sự kiện quan trọng nhất (CPI, NFP, Fed Rate Decision)
- Step 4: Điền vào template: Sự kiện | Actual | Forecast | Previous | Tác động dự kiến
- **Template được cung cấp sẵn trong bài**

**Bài tập 4: Screener cổ phiếu (30 phút)**
- Step 1: Vào finviz.com/screener
- Step 2: Lọc: P/E < 20, Market Cap > $10B, Sector = Technology, EPS growth > 10%
- Step 3: Ghi lại 5 cổ phiếu tìm được
- Step 4: Tra thêm thông tin cơ bản của 1 trong 5 cổ phiếu đó
- **Template kết quả screener được cung cấp sẵn**

**Bài tập 5: Xây dựng Personal Toolkit (15 phút)**
- Điền đầy đủ bảng Personal Toolkit: Thị trường → Công cụ đang dùng → Link → Ghi chú
- Đặt bookmark tất cả công cụ vào browser theo folder: Macro Data | Charts | News | Screener | Portfolio

**Câu hỏi ôn tập (10 câu trắc nghiệm)**:
- Hỏi về tính năng của từng nền tảng
- So sánh CEX vs DEX
- Cách đặt lệnh Pending Order
- Tìm kiếm dữ liệu kinh tế ở đâu

**Đáp án và giải thích chi tiết cho tất cả bài tập**
```

---

## VỊ TRÍ ĐẶT NGÀY 63 TRONG KHÓA HỌC

Ngày 63 được thêm vào **sau Ngày 62 (Tổng kết khóa học)**, thuộc **Phần Bổ Sung** (không nằm trong 6 phần chính).

Cập nhật cấu trúc thư mục trong `mega-prompt.md`:

```
└── phan-bo-sung/
    └── day-63-cong-cu-nen-tang-giao-dich/
        ├── lesson.md
        ├── document.md
        └── exercises.md
```

---

## GHI CHÚ KHI TẠO NỘI DUNG

- Kết nối với các ngày đã học: "Như đã học ở Ngày 51 về MetaTrader và Broker...", "Ngày 58 đã đề cập DefiLlama..."
- Mỗi hướng dẫn phải có **screenshot mô tả bằng text** (vì không đính kèm ảnh được)
- Ưu tiên công cụ **miễn phí hoặc có bản miễn phí** cho người mới
- Cảnh báo rõ về **scam platform** và cách verify sàn giao dịch uy tín
- Với bài tập: luôn cung cấp **template/checklist** để người dùng điền vào, không để trống
