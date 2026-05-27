# Tài liệu tham khảo — Ngày 31: Indicators — Oscillators & Volume

## Cheat Sheet: RSI

| Giá trị RSI | Ý nghĩa | Hành động tham khảo |
|-------------|---------|---------------------|
| > 80 | Extremely Overbought | Cân nhắc chốt lời, không mua thêm |
| 70–80 | Overbought | Cảnh giác, tìm tín hiệu đảo chiều |
| 50–70 | Bullish zone | Xu hướng tăng, tìm setup bullish có xác nhận |
| 50 | Neutral | Không xu hướng rõ ràng |
| 30–50 | Bearish zone | Xu hướng giảm hoặc điều chỉnh |
| 20–30 | Oversold | Cơ hội tiềm năng, tìm xác nhận |
| < 20 | Extremely Oversold | Cơ hội mua tốt (nếu không phải downtrend mạnh) |

**Cài đặt RSI phổ biến:**
- RSI(14): Mặc định, cân bằng tốt nhất
- RSI(9): Nhạy hơn, nhiều tín hiệu hơn, cũng nhiều giả hơn
- RSI(21): Chậm hơn, ít tín hiệu nhưng đáng tin hơn

---

## Cheat Sheet: Stochastic Oscillator

| Vùng | %K | Ý nghĩa |
|------|----|---------|
| Overbought | > 80 | Cân nhắc bán/short |
| Trung lập | 20–80 | Theo xu hướng |
| Oversold | < 20 | Cân nhắc mua |

**Tín hiệu giao cắt Stochastic:**
- %K cắt %D từ dưới lên tại vùng < 20 → **BUY signal**
- %K cắt %D từ trên xuống tại vùng > 80 → **SELL signal**

**Cài đặt thông dụng:** Stochastic(14, 3, 3) hoặc Stochastic(5, 3, 3) cho scalping

---

## Cheat Sheet: Volume Analysis

```
Volume Patterns:

TĂNG GIÁ MẠNH:           TĂNG GIÁ YẾU:
Price:  ↑↑↑              Price:  ↑↑↑
Volume: ↑↑↑              Volume: ↓↓↓
→ Tin tưởng              → Cảnh báo

GIẢM GIÁ MẠNH:           ĐIỀU CHỈNH TRONG UPTREND:
Price:  ↓↓↓              Price:  ↓↓↓
Volume: ↑↑↑              Volume: ↓↓↓
→ Tháo chạy              → Bình thường, vùng xem xét hồi phục
```

**Volume Moving Average:** So sánh volume hiện tại với MA(20) của volume:
- Volume > 1.5× MA20: Volume cao bất thường
- Volume > 2× MA20: Volume rất cao (breakout/breakdown đáng tin)
- Volume < 0.5× MA20: Volume rất thấp (thị trường thờ ơ)

---

## Cheat Sheet: Divergence

### Regular Divergence (Đảo chiều)

| Loại | Giá | RSI/MACD | Tín hiệu |
|------|-----|----------|---------|
| Bearish Regular | Higher High (HH) | Lower High (LH) | Bán/short sắp tới |
| Bullish Regular | Lower Low (LL) | Higher Low (HL) | Mua sắp tới |

### Hidden Divergence (Tiếp diễn)

| Loại | Giá | RSI/MACD | Tín hiệu |
|------|-----|----------|---------|
| Hidden Bullish | Higher Low (HL) | Lower Low (LL) | Uptrend tiếp tục |
| Hidden Bearish | Lower High (LH) | Higher High (HH) | Downtrend tiếp tục |

---

## Bảng so sánh: RSI vs Stochastic vs MACD

| Chỉ báo | Loại | Tốt nhất khi | Hạn chế |
|---------|------|--------------|---------|
| RSI(14) | Oscillator | Trending + Ranging | Lag trong strong trend |
| Stochastic | Oscillator | Ranging/Sideways | Nhiều tín hiệu giả |
| MACD | Trend + Momentum | Strong trending | Chậm trong sideways |
| OBV | Volume | Xác nhận dòng tiền | Không cho timing cụ thể |

---

## Tài liệu đọc thêm

**Sách:**
- *Technical Analysis of the Financial Markets* — John J. Murphy (Chương 10, 11)
- *New Concepts in Technical Trading Systems* — J. Welles Wilder (tác giả RSI)
- *Granville's New Key to Stock Market Profits* — Joe Granville (tác giả OBV)

**Website:**
- Investopedia RSI: https://www.investopedia.com/terms/r/rsi.asp
- TradingView — xem indicators miễn phí: https://www.tradingview.com
- School of Pipsology (Babypips): https://www.babypips.com/learn/forex

**Video YouTube (tiếng Việt):**
- Kênh TraderViet — series phân tích kỹ thuật
- Kênh Chứng khoán F — bài giảng RSI và Volume

---

## Ghi chú bổ sung: Thực hành trên TradingView

Cách thêm indicators trên TradingView:
1. Mở chart bất kỳ (VD: HOSE:FPT)
2. Click "Indicators" (biểu tượng f(x))
3. Tìm kiếm: "RSI", "Stochastic", "OBV"
4. Nhấn để thêm vào chart

**Layout gợi ý cho người mới:**
- Panel 1 (chính): Candlestick + EMA(20) + EMA(50) + Volume bars
- Panel 2: RSI(14) với đường 70/50/30
- Panel 3: Stochastic(14,3,3) với đường 80/20
- Panel 4: OBV

**Tip:** Đừng thêm quá nhiều indicators cùng lúc — sẽ gây "indicator paralysis" (tê liệt vì quá nhiều tín hiệu mâu thuẫn).
