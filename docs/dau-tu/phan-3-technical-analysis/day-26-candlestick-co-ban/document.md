# Tài liệu tham khảo — Ngày 26: Candlestick Chart Cơ Bản

## Cheat Sheet: 6 Mô Hình Nến Đơn Quan Trọng

| Mô hình | Hình dạng | Vị trí xuất hiện | Tín hiệu | Độ tin cậy |
|---------|-----------|-------------------|----------|------------|
| Doji | Thân = 0, hai bóng | Sau xu hướng dài | Đảo chiều tiềm năng | Trung bình |
| Hammer | Bóng dưới dài, thân nhỏ trên | Cuối downtrend | Bullish reversal | Cao |
| Inverted Hammer | Bóng trên dài, thân nhỏ dưới | Cuối downtrend | Bullish reversal | Trung bình |
| Shooting Star | Bóng trên dài, thân nhỏ dưới | Cuối uptrend | Bearish reversal | Cao |
| Hanging Man | Bóng dưới dài, thân nhỏ trên | Cuối uptrend | Bearish reversal | Trung bình |
| Marubozu | Thân dài, không bóng | Bất kỳ | Tiếp tục xu hướng | Rất cao |
| Spinning Top | Thân nhỏ, hai bóng đều | Sau xu hướng | Không chắc chắn | Thấp |

## Bảng So Sánh: Hammer vs Hanging Man

Hai nến này trông **giống hệt nhau** về hình dạng (bóng dưới dài, thân nhỏ ở trên) nhưng tín hiệu hoàn toàn ngược nhau vì **vị trí khác nhau**:

```
Hammer (Cuối downtrend → Bullish):     Hanging Man (Cuối uptrend → Bearish):
   
   📉📉📉 [Hammer] 📈                    📈📈📈 [Hanging Man] 📉
```

## Bảng So Sánh: Shooting Star vs Inverted Hammer

Tương tự — hình dạng giống nhau (bóng trên dài, thân nhỏ ở dưới) nhưng tín hiệu khác nhau:

```
Inverted Hammer (Cuối downtrend → Bullish):   Shooting Star (Cuối uptrend → Bearish):
   
   📉📉📉 [Inverted Hammer] 📈                  📈📈📈 [Shooting Star] 📉
```

## Công Thức Tính Thành Phần Nến

```
Body Size = |Close - Open|
Upper Shadow = High - max(Open, Close)
Lower Shadow = min(Open, Close) - Low
Total Candle Range = High - Low
```

**Tỷ lệ để nhận diện:**
- Bóng dưới dài ≥ 2x thân → Hammer / Hanging Man
- Bóng trên dài ≥ 2x thân → Shooting Star / Inverted Hammer
- Thân < 10% tổng nến → Doji
- Thân > 60% tổng nến, bóng < 5% → Marubozu

## Checklist Trước Khi Giao Dịch Dựa Trên Nến

- [ ] Xác định xu hướng hiện tại (up/down/sideway)
- [ ] Nhận diện mô hình nến
- [ ] Kiểm tra vị trí: đầu/cuối xu hướng? Gần hỗ trợ/kháng cự?
- [ ] Kiểm tra volume: có tăng đột biến không?
- [ ] Đợi nến xác nhận tiếp theo
- [ ] Xác định điểm vào lệnh, Stop-loss, Take-profit

## Tài Liệu Đọc Thêm

**Sách:**
- *Japanese Candlestick Charting Techniques* — Steve Nison (kinh điển, bắt buộc đọc)
- *Encyclopedia of Candlestick Charts* — Thomas Bulkowski (tổng hợp 103 mô hình với thống kê)
- *Candlestick and Pivot Point Trading Triggers* — John L. Person

**Website & Tools:**
- TradingView.com — nền tảng biểu đồ miễn phí tốt nhất, có sẵn nến Nhật
- Investing.com — biểu đồ và dữ liệu thị trường
- Stockcharts.com — phân tích kỹ thuật chuyên sâu

**Video:**
- Kênh YouTube: "Adam Khoo" — phân tích kỹ thuật tiếng Anh dễ hiểu
- Kênh YouTube tiếng Việt: "Chứng khoán Phú Hưng", "StockBiz"

## Ghi Chú Bổ Sung

**Lịch sử nến Nhật:**
Munehisa Homma (1724-1803) — còn gọi là "God of Markets" — đã kiếm được tương đương hàng trăm triệu USD từ giao dịch gạo bằng phương pháp nến Nhật. Ông viết cuốn sách "Sakata Rules" đặt nền tảng cho phân tích kỹ thuật hiện đại.

**Màu sắc nến:**
- Hệ thống Nhật truyền thống: Trắng (tăng) / Đen (giảm)
- Hệ thống phương Tây hiện đại: Xanh (tăng) / Đỏ (giảm)
- Bạn có thể tùy chỉnh màu trên TradingView

**Timeframe và ý nghĩa:**
- Nến 1 phút (1m): Nhiễu loạn, chỉ dùng cho scalping
- Nến 15 phút (15m): Day trading
- Nến 1 giờ (1H) / 4 giờ (4H): Swing trading
- Nến ngày (1D): Tổng quan xu hướng
- Nến tuần (1W): Xu hướng dài hạn
