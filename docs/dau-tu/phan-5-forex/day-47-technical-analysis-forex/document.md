# Tài liệu tham khảo — Ngày 47: Technical Analysis ứng dụng Forex

## Cheat Sheet: Fibonacci Levels

### Fibonacci Retracement
| Mức | Ý nghĩa | Ghi chú |
|-----|---------|---------|
| 23.6% | Hồi rất nông | Xu hướng cực mạnh |
| 38.2% | Hồi vừa | Điểm vào yêu thích của swing trader |
| 50.0% | Hồi giữa | Không phải Fibonacci nhưng rất quan trọng |
| 61.8% | Golden Ratio — hồi sâu | Vùng đáng chú ý, cần tín hiệu xác nhận |
| 78.6% | Hồi rất sâu | Sắp mất xu hướng nếu phá qua |

### Fibonacci Extension (Mục tiêu giá)
| Mức | Ý nghĩa |
|-----|---------|
| 100% | Bằng biên độ ban đầu |
| 127.2% | Take Profit gần |
| 161.8% | Take Profit chính (Golden Extension) |
| 200% | Take Profit xa |
| 261.8% | Xu hướng rất mạnh |

---

## Công thức Pivot Points

### Classic Pivot Points
```
PP = (H + L + C) / 3
R1 = (2 × PP) - L
R2 = PP + (H - L)
R3 = H + 2 × (PP - L)
S1 = (2 × PP) - H
S2 = PP - (H - L)
S3 = L - 2 × (H - PP)
```

### Camarilla Pivot Points
```
R4 = C + ((H - L) × 1.1 / 2)
R3 = C + ((H - L) × 1.1 / 4)
R2 = C + ((H - L) × 1.1 / 6)
R1 = C + ((H - L) × 1.1 / 12)
S1 = C - ((H - L) × 1.1 / 12)
S2 = C - ((H - L) × 1.1 / 6)
S3 = C - ((H - L) × 1.1 / 4)
S4 = C - ((H - L) × 1.1 / 2)
```
*Camarilla phù hợp cho scalping — các mức R3/S3 thường là điểm đảo chiều tốt*

---

## Bộ Multi-Timeframe cho từng phong cách

### Scalper (Vài phút/lệnh)
```
Higher TF (Trend):  M15 hoặc M30
Entry TF:           M1 hoặc M5
Key Levels:         Pivot Points Daily, Round Numbers
Indicators:         EMA 9, EMA 21, Stochastic
```

### Day Trader (Vài giờ/lệnh)
```
Higher TF (Trend):  H4 hoặc Daily
Entry TF:           H1 hoặc M30
Key Levels:         Daily Pivot Points, Fibonacci, Daily S/R
Indicators:         EMA 20, EMA 50, RSI, MACD
```

### Swing Trader (Vài ngày/lệnh)
```
Higher TF (Trend):  Weekly
Analysis TF:        Daily
Entry TF:           H4
Key Levels:         Weekly Pivot Points, Major S/R, Fibonacci
Indicators:         EMA 50, EMA 200, RSI, MACD
```

### Position Trader (Vài tuần-tháng/lệnh)
```
Higher TF (Trend):  Monthly
Analysis TF:        Weekly
Entry TF:           Daily
Key Levels:         Major historical S/R, Monthly Fibonacci
Indicators:         MA 200, Fundamental bias
```

---

## Mức Round Numbers quan trọng

### EUR/USD
```
Major levels:    1.0000, 1.0500, 1.1000, 1.1500, 1.2000
Minor levels:    1.0200, 1.0300, 1.0700, 1.0800, 1.0900
```

### GBP/USD
```
Major levels:    1.2000, 1.2500, 1.3000, 1.3500
Minor levels:    1.2200, 1.2700, 1.3200
```

### USD/JPY
```
Major levels:    140, 145, 150, 155, 160
Minor levels:    141, 142, 143, 148, 149, 151, 152
```

### AUD/USD
```
Major levels:    0.6000, 0.6500, 0.7000, 0.7500
Minor levels:    0.6200, 0.6300, 0.6700, 0.6800
```

---

## Biểu đồ ASCII: Fibonacci trong Uptrend

```
Giá
  |                        *** Swing High (100%)
  |                    ***
  |                ***
  |            ***
  |        ***         ← Giá bắt đầu hồi
  |                    _____________________ 23.6% retracement
  |                ___________________________
  |            _______________________________  38.2% (BUY ZONE 1)
  |        ___________________________________ 50.0%  (BUY ZONE 2)
  |    _______________________________________  61.8% (BUY ZONE 3 - cần xác nhận)
  |  _________________________________________  78.6% (nguy hiểm - có thể đảo chiều)
  |
  ***  Swing Low (0%)
  |
  +------------------------------------------------> Thời gian

Chiến lược demo: Chờ giá hồi về BUY ZONE → Tìm tín hiệu xác nhận → Chỉ vào lệnh nếu R:R và rủi ro đạt chuẩn
```

---

## Confluence Score — Đánh giá sức mạnh tín hiệu

| Yếu tố | Điểm |
|--------|------|
| Fibonacci 61.8% (Golden Ratio) | +3 |
| Fibonacci 38.2% hoặc 50% | +2 |
| Daily Pivot Point (PP, S1, R1) | +2 |
| Support/Resistance lịch sử mạnh | +3 |
| Round Number (1.0500, 150.00...) | +2 |
| MA 200 Daily | +3 |
| MA 50 Daily | +2 |
| Trendline quan trọng | +2 |
| RSI Oversold/Overbought | +1 |
| Nến đảo chiều xác nhận | +2 |
| Divergence (RSI, MACD) | +3 |
| Cùng hướng với xu hướng lớn | +2 |

**Đánh giá:**
- Tổng < 5: Tín hiệu yếu — nên đứng ngoài
- Tổng 5-8: Tín hiệu trung bình — chỉ theo dõi hoặc test trên demo
- Tổng 9-12: Tín hiệu mạnh hơn — vẫn phải có Stop-Loss, R:R tối thiểu 1:2 và rủi ro 1% trở xuống
- Tổng > 12: Tín hiệu rất mạnh — không phải lý do tăng size; người mới vẫn giữ nguyên quy tắc position sizing

---

## Tài liệu đọc thêm

**Sách:**
- *Technical Analysis of the Financial Markets* — John Murphy (kinh điển)
- *Fibonacci Trading* — Carolyn Boroden
- *Naked Forex* — Alex Nekritin & Walter Peters (Price Action thuần)

**Video/Khóa học:**
- TradingView YouTube Channel — Hướng dẫn sử dụng công cụ
- BabyPips.com — "How to Use Fibonacci" section
- Rayner Teo (YouTube) — Fibonacci và Multi-Timeframe (tiếng Anh, dễ hiểu)

**Công cụ thực hành:**
- TradingView (tradingview.com) — Có đầy đủ Fibonacci tools, Pivot Points
- Khuyến nghị: Tạo tài khoản miễn phí, vào biểu đồ EUR/USD, thực hành vẽ Fibonacci
