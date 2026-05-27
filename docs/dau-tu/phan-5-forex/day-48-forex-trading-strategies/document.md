# Tài liệu tham khảo — Ngày 48: Forex Trading Strategies

## Bảng So sánh 6 Chiến lược Forex

| Tiêu chí | Trend Following | Breakout | Range Trading | Scalping | Swing Trading | Position Trading |
|----------|----------------|----------|---------------|----------|---------------|-----------------|
| **Thời gian giữ lệnh** | Ngày-Tuần | Giờ-Ngày | Giờ-Ngày | Phút | Ngày-Tuần | Tuần-Tháng |
| **Số lệnh/tháng** | 5-15 | 10-30 | 20-50 | 100-500 | 4-10 | 1-5 |
| **Tỷ lệ thắng** | 40-55% | 35-50% | 55-70% | 55-70% | 40-55% | 40-55% |
| **Risk/Reward** | 1:3 đến 1:10 | 1:2 đến 1:5 | 1:1 đến 1:2 | 1:1 đến 1:2 | 1:3 đến 1:8 | 1:5 đến 1:20 |
| **Thời gian cần/ngày** | 30-60 phút | 1-2 giờ | 2-4 giờ | Toàn thời gian | 30-60 phút | 15-30 phút |
| **Vốn tối thiểu** | $500 | $500 | $500 | $1,000+ | $500 | $2,000+ |
| **Khó khăn** | Trung bình | Cao | Trung bình | Rất cao | Trung bình | Cao |
| **Phù hợp nhất** | Trung-Nâng cao | Trung-Nâng cao | Trung | Chuyên gia | **Người mới** | Nâng cao |
| **Giữ qua đêm?** | Có | Đôi khi | Không | Không | Có | Có |
| **Cần hiểu Macro?** | Ít | Ít | Không | Không | Vừa | Nhiều |

---

## Template: Trading Plan cơ bản

```markdown
# TRADING PLAN — [Tên bạn]
Cập nhật: [Ngày]

## 1. MỤC TIÊU
- Mục tiêu quy trình: tuân thủ plan, ghi journal 100%, kiểm soát drawdown
- Mục tiêu lợi nhuận: chỉ đặt sau khi đã backtest/forward test đủ dữ liệu; không dùng % cố định như cam kết
- Mức drawdown tối đa chấp nhận: Y% (thường 10-15%)

## 2. CHIẾN LƯỢC GIAO DỊCH
- Chiến lược: [Swing Trading / Day Trading / ...]
- Cặp tiền: [EUR/USD, USD/JPY...]
- Phiên giao dịch: [London / NY / ...]
- Timeframe phân tích: [Daily / H4 / H1]
- Timeframe vào lệnh: [H4 / H1 / M30]

## 3. ĐIỀU KIỆN VÀO LỆNH (Entry Rules)
BUY khi:
- Điều kiện 1: ...
- Điều kiện 2: ...
- Điều kiện 3: ...

SELL khi:
- Điều kiện 1: ...
- ...

## 4. QUẢN LÝ RỦI RO
- Rủi ro mỗi lệnh: 1% tài khoản
- Stop Loss: [Kỹ thuật / Cố định X pip]
- Take Profit: [Kỹ thuật / Cố định Y pip / Trailing]
- Số lệnh tối đa cùng lúc: 2-3 lệnh
- Dừng giao dịch khi: Thua 3 lệnh liên tiếp HOẶC lỗ 3%/ngày

## 5. ĐIỀU KIỆN KHÔNG GIAO DỊCH
- Trong vòng 30 phút trước/sau tin High Impact
- Khi VIX > 30 (nếu trading carry)
- Thứ Hai đầu tuần (gap risk)
- Khi không rõ xu hướng
- Khi đang thua 3 lệnh liên tiếp

## 6. TRADING JOURNAL
- Ghi chép mọi lệnh vào spreadsheet
- Review hàng tuần mỗi cuối tuần
```

---

## Template: Trading Journal (Nhật Ký Giao Dịch)

| # | Ngày | Cặp | Hướng | Entry | SL | TP | Exit | Pip | R | Lý do vào | Cảm xúc | Bài học |
|---|------|-----|-------|-------|----|----|------|-----|---|-----------|---------|---------|
| 1 | 15/1 | EUR/USD | BUY | 1.0850 | 1.0800 | 1.0950 | 1.0930 | +80 | +1.6R | Fib 61.8% + S/R | Bình tĩnh | Nên giữ thêm |
| 2 | 17/1 | USD/JPY | SELL | 148.50 | 149.00 | 147.00 | 148.95 | -45 | -0.9R | Tin CPI tốt | Lo lắng | Không giao dịch trước NFP |

**Các cột quan trọng cần ghi:**
- **R**: Kết quả tính bằng đơn vị Risk (1R = lãi đúng bằng rủi ro ban đầu)
- **Cảm xúc**: Quan trọng để phát hiện pattern tâm lý
- **Bài học**: Cải thiện cho lần sau

---

## Cheat Sheet: Lọc Tín Hiệu Giao Dịch

### Checklist Trend Following
```
✅ Timeframe lớn hơn cùng xu hướng?
✅ Giá trên/dưới MA 200?
✅ ADX > 25 (xu hướng đủ mạnh)?
✅ Giá đang hồi về MA 50 hoặc Fibonacci?
✅ Có tín hiệu đảo chiều hồi (nến, indicator)?
✅ Risk/Reward ≥ 1:2?
```

### Checklist Breakout
```
✅ Range đã tích lũy đủ lâu (>1-2 tuần)?
✅ Nến đóng cửa NGOÀI vùng tích lũy?
✅ Volume/momentum tăng khi breakout?
✅ Không phải thứ Hai đầu tuần hay trước tin lớn?
✅ Đang trong giờ phiên London hoặc NY?
✅ Không phải False Breakout (chờ retest)?
```

### Checklist Range Trading
```
✅ ADX < 25 (thị trường sideway)?
✅ Support/Resistance rõ ràng đã test ≥ 2 lần?
✅ Giá ở biên (không ở giữa range)?
✅ Oscillator xác nhận (RSI, Stochastic)?
✅ Không có tin High Impact trong vài giờ tới?
✅ Risk/Reward hợp lý?
```

---

## Backtesting — Cách Kiểm Tra Chiến Lược

**Backtesting** là áp dụng chiến lược vào dữ liệu lịch sử để xem hiệu quả.

### Phương pháp Manual Backtesting:
1. Mở TradingView, chọn cặp tiền và timeframe
2. Cuộn biểu đồ về quá khứ (6-12 tháng)
3. Dùng công cụ "Replay" để xem từng nến xuất hiện
4. Ghi lại mọi tín hiệu theo strategy rules
5. Thống kê kết quả

### Các thống kê cần tính:
```
Win Rate = (Số lệnh thắng / Tổng lệnh) × 100%
Average Win = Tổng pip thắng / Số lệnh thắng
Average Loss = Tổng pip thua / Số lệnh thua
Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
Profit Factor = Tổng lãi / Tổng lỗ

Chiến lược tốt: Expectancy > 0, Profit Factor > 1.5
```

### Ví dụ thống kê sau 100 lệnh:
```
Tổng lệnh: 100
Thắng: 45 lệnh (Win Rate 45%)
Thua: 55 lệnh

Average Win: +80 pip
Average Loss: -40 pip

Expectancy = (45% × 80) - (55% × 40) = 36 - 22 = +14 pip/lệnh ✅
Profit Factor = (45 × 80) / (55 × 40) = 3,600 / 2,200 = 1.64 ✅
```

---

## Tài liệu đọc thêm

**Sách về Trading Strategy:**
- *Trading Systems and Methods* — Perry Kaufman (bách khoa về strategy)
- *The Complete TurtleTrader* — Michael Covel (Trend Following)
- *Street Smarts: High Probability Short-Term Trading* — Linda Raschke & Laurence Connors

**Sách về Trading Psychology (quan trọng không kém):**
- *Trading in the Zone* — Mark Douglas (**Phải đọc**)
- *Market Wizards* — Jack Schwager (phỏng vấn các trader huyền thoại)

**YouTube:**
- Rayner Teo — Chiến lược Swing Trading rõ ràng, miễn phí
- Anton Kreil — Institutional trading perspective
- Adam Khoo — Phân tích kỹ thuật cơ bản

**Platform để Backtest:**
- TradingView (có Strategy Tester)
- MetaTrader 4/5 (Strategy Tester built-in)
- Forex Tester (phần mềm chuyên backtest)
