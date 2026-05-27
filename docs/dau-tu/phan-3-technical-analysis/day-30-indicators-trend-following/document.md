# Tài Liệu Tham Khảo — Ngày 30: Indicators Trend Following

## Cheat Sheet: Cài Đặt Mặc Định Indicators

| Indicator | Cài đặt phổ biến | Dùng trên TradingView |
|-----------|-----------------|----------------------|
| SMA | 20, 50, 200 | "MA" hoặc "SMA" |
| EMA | 9, 12, 26, 50, 200 | "EMA" |
| MACD | 12, 26, 9 (mặc định) | "MACD" |
| Bollinger Bands | 20, 2 (mặc định) | "BB" |

## Bảng So Sánh: SMA vs EMA

| Tiêu chí | SMA | EMA |
|----------|-----|-----|
| Cách tính | Trung bình đơn giản | Ưu tiên dữ liệu gần |
| Phản ứng | Chậm hơn | Nhanh hơn |
| Tín hiệu giả | Ít hơn | Nhiều hơn |
| Smoothing | Tốt hơn | Kém hơn |
| Thích hợp | Dài hạn (MA50, MA200) | Ngắn-trung hạn |
| Dùng khi | Xác định trend lớn | Entry/Exit timing |

## Giải Mã MACD Histogram

```
Histogram xanh to và tăng → Momentum tăng mạnh (mua mạnh)
Histogram xanh nhưng thu hẹp → Momentum tăng đang yếu đi (cẩn thận)
Histogram chuyển đỏ → Momentum chuyển tiêu cực (xem xét thoát)
Histogram đỏ và tăng (âm hơn) → Bears kiểm soát mạnh
Histogram đỏ thu hẹp → Bears đang yếu đi (chuẩn bị đảo chiều?)
```

## Tín Hiệu MACD: Mạnh vs Yếu

| Tín hiệu | Điều kiện | Độ mạnh |
|----------|-----------|---------|
| Bullish crossover dưới zero | MACD cắt Signal ở vùng âm | ⭐⭐⭐⭐⭐ |
| Bullish crossover trên zero | MACD cắt Signal ở vùng dương | ⭐⭐⭐ |
| MACD cắt Zero Line lên | MACD từ âm → dương | ⭐⭐⭐⭐ |
| Bullish Divergence | Giá LL, MACD HL | ⭐⭐⭐⭐⭐ |
| Bearish Divergence | Giá HH, MACD LH | ⭐⭐⭐⭐⭐ |
| Bearish crossover trên zero | MACD cắt Signal ở vùng dương | ⭐⭐⭐⭐⭐ |

## Bollinger Bands: Tín Hiệu Và Ý Nghĩa

| Tình huống | Ý nghĩa | Hành động |
|-----------|---------|----------|
| BB Squeeze (hẹp) | Sắp có biến động lớn | Chuẩn bị, theo dõi hướng breakout |
| Giá cưỡi Upper Band | Uptrend rất mạnh | Không short, giữ lệnh mua |
| Giá cưỡi Lower Band | Downtrend rất mạnh | Không mua, giữ lệnh bán |
| Giá chạm Lower, quay lên | Sideway bounce | Mua (chỉ trong sideway) |
| Giá vọt qua Upper Band | Breakout hoặc overbought | Xem volume để phán đoán |
| Upper và Lower mở rộng | Biến động đang tăng | Xu hướng đang mạnh |

## Chiến Lược Kết Hợp Indicators

### Setup 1: Trend Trader (Dài hạn)
```
Indicators: MA50 + MA200 + MACD
Entry: Golden Cross + MACD crossover (bullish)
Exit: Death Cross hoặc MACD crossover (bearish)
Timeframe: Daily/Weekly
```

### Setup 2: Swing Trader (Trung hạn)
```
Indicators: EMA20 + EMA50 + MACD
Entry: Giá pullback về EMA20/EMA50 + MACD bullish crossover
Exit: MACD bearish crossover hoặc chạm kháng cự
Timeframe: 4H/Daily
```

### Setup 3: Breakout Trader
```
Indicators: Bollinger Bands + Volume
Entry: BB Squeeze → Breakout với volume lớn
Exit: Khi giá đạt target (Measured Move) hoặc BB bắt đầu thu hẹp
Timeframe: Daily
```

## Checklist Trước Khi Dùng Indicators

- [ ] Xác định market là trending hay sideways?
  - Trending → Dùng MA, MACD
  - Sideways → Dùng Bollinger Bands với mean reversion
- [ ] Không dùng quá 2-3 indicators cùng lúc
- [ ] Indicators chỉ xác nhận — không phải tín hiệu độc lập
- [ ] Kiểm tra tín hiệu trên timeframe cao hơn trước
- [ ] Kết hợp với Support/Resistance và Candlestick

## Tài Liệu Đọc Thêm

**Sách:**
- *Technical Analysis of the Financial Markets* — John J. Murphy (chương về Moving Averages và Oscillators)
- *Bollinger on Bollinger Bands* — John Bollinger (tác giả chính)
- *MACD Primer* — Gerald Appel (tác giả MACD, sách mỏng nhưng súc tích)

**Website:**
- TradingView.com — thực hành indicators miễn phí, có cộng đồng chia sẻ setup
- Investopedia.com — giải thích chi tiết từng indicator
- StockCharts.com/school — khóa học kỹ thuật miễn phí

## Ghi Chú Nâng Cao

**MACD và chu kỳ thời gian:**
- Cài đặt mặc định 12, 26, 9 phù hợp với giao dịch hàng ngày
- Cho scalping ngắn hạn: 5, 13, 1 hoặc 3, 10, 9
- Cho trading dài hạn: 24, 52, 18 (tương đương tuần trên biểu đồ ngày)

**Bollinger Bands Width (Độ rộng):**
- Mức độ rộng thấp nhất trong 6 tháng → Squeeze quan trọng
- John Bollinger khuyến nghị: Khi Bandwidth xuống dưới 1% (forex) hoặc dưới mức lịch sử → Chuẩn bị kỹ cho breakout

**Hidden Divergence (Phân kỳ ẩn):**
- **Bullish hidden divergence:** Giá tạo Higher Low (HL), MACD tạo Lower Low (LL) → Xu hướng tăng tiếp tục (không đảo chiều)
- **Bearish hidden divergence:** Giá tạo Lower High (LH), MACD tạo Higher High (HH) → Xu hướng giảm tiếp tục
- Đây là tín hiệu **continuation** trong khi regular divergence là tín hiệu **reversal**
