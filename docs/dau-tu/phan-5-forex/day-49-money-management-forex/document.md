# Tài liệu tham khảo — Ngày 49: Money Management trong Forex

## Bảng tóm tắt / Cheat Sheet

### Công thức Position Sizing

```
Position Size (lots) = Số tiền rủi ro ($) ÷ (Stop-Loss pips × Pip Value/lot)

Trong đó:
- Số tiền rủi ro = Tài khoản ($) × % Risk
- Pip Value Standard Lot:
  • Cặp xxx/USD (EUR/USD, GBP/USD...): $10/pip
  • Cặp USD/xxx (USD/JPY, USD/CAD...): thay đổi, ~$9-10/pip
  • Cặp Cross (EUR/GBP, EUR/JPY...): khác nhau, cần Calculator
```

### Bảng Position Size nhanh — Tài khoản $10,000

**Rủi ro 1% ($100):**

| SL (pips) | EUR/USD (lots) | GBP/USD (lots) | USD/JPY (lots) |
|-----------|---------------|---------------|---------------|
| 10 | 1.00 | 1.00 | ~1.10 |
| 20 | 0.50 | 0.50 | ~0.55 |
| 30 | 0.33 | 0.33 | ~0.37 |
| 50 | 0.20 | 0.20 | ~0.22 |
| 75 | 0.13 | 0.13 | ~0.15 |
| 100 | 0.10 | 0.10 | ~0.11 |

**Rủi ro 2% ($200):** Nhân đôi tất cả các số trên

---

### Bảng Win Rate vs R:R — Expectancy

**Expectancy = (Win Rate × Average Win) - (Loss Rate × Average Loss)**

| Win Rate | R:R 1:1 | R:R 1:2 | R:R 1:3 | R:R 1:4 |
|----------|---------|---------|---------|---------|
| 25% | -0.50R | 0.00R | +0.25R | +0.50R |
| 33% | -0.33R | +0.00R | +0.33R | +0.66R |
| 40% | -0.20R | +0.20R | +0.60R | +1.00R |
| 45% | -0.10R | +0.35R | +0.80R | +1.25R |
| 50% | 0.00R | +0.50R | +1.00R | +1.50R |
| 55% | +0.10R | +0.65R | +1.20R | +1.75R |
| 60% | +0.20R | +0.80R | +1.40R | +2.00R |
| 70% | +0.40R | +1.10R | +1.80R | +2.50R |

*R = đơn vị rủi ro (ví dụ: 1R = $100 nếu risk 1%)*
*Expectancy dương = hệ thống có lợi nhuận dài hạn*

---

### Bảng Drawdown vs Recovery

| Drawdown | Cần lợi nhuận để phục hồi |
|----------|--------------------------|
| 5% | 5.3% |
| 10% | 11.1% |
| 15% | 17.6% |
| 20% | 25.0% |
| 25% | 33.3% |
| 30% | 42.9% |
| 40% | 66.7% |
| 50% | 100.0% |
| 60% | 150.0% |
| 70% | 233.0% |
| 80% | 400.0% |
| 90% | 900.0% |

---

### Correlation Matrix (Tương quan cặp tiền chính — Approximate)

| | EUR/USD | GBP/USD | USD/CHF | USD/JPY | AUD/USD |
|---|---------|---------|---------|---------|---------|
| **EUR/USD** | 1.00 | +0.90 | -0.90 | -0.50 | +0.75 |
| **GBP/USD** | +0.90 | 1.00 | -0.85 | -0.45 | +0.70 |
| **USD/CHF** | -0.90 | -0.85 | 1.00 | +0.60 | -0.70 |
| **USD/JPY** | -0.50 | -0.45 | +0.60 | 1.00 | -0.40 |
| **AUD/USD** | +0.75 | +0.70 | -0.70 | -0.40 | 1.00 |

*Lưu ý: Correlation thay đổi theo thời gian và điều kiện thị trường*

**Hướng dẫn đọc:**
- Gần +1.0: Di chuyển cùng chiều rất mạnh → Tránh hold cả hai cùng chiều
- Gần -1.0: Di chuyển ngược chiều rất mạnh → Hold cùng chiều = hedge (triệt tiêu)
- Gần 0: Không tương quan rõ → Ít chồng rủi ro hơn, nhưng vẫn phải tính tổng risk toàn danh mục

---

### Quy tắc Money Management — Tóm tắt

```
✅ LUÔN LUÔN:
□ Tính Position Size trước khi vào lệnh
□ Đặt Stop-Loss ngay khi vào lệnh
□ Đảm bảo R:R ≥ 1:2
□ Rủi ro ≤ 1-2% mỗi lệnh
□ Ghi chép vào Trading Journal

❌ KHÔNG BAO GIỜ:
□ Vào lệnh không có Stop-Loss
□ Di chuyển SL xa hơn khi đang thua
□ Tăng size sau khi thua (Revenge Trading)
□ Trade khi Drawdown tháng > 10%
□ Dùng số tiền không thể mất được
```

---

### Money Management theo quy mô tài khoản

| Tài khoản | Risk/Trade | Max position | Phong cách phù hợp |
|-----------|-----------|--------------|-------------------|
| < $1,000 | 1-2% | Micro lots | Học, thực hành |
| $1,000-$10,000 | 1% | Mini lots | Xây dựng kỷ luật |
| $10,000-$50,000 | 0.5-1% | Mix lots | Phát triển bền vững |
| > $50,000 | 0.25-0.5% | Standard lots | Bảo tồn và tăng trưởng |

---

### Tools hỗ trợ

**Online Position Size Calculator:**
- Myfxbook.com/tools/position-size-calculator
- BabyPips.com/tools/position-size-calculator

**Trong MetaTrader 4/5:**
- Indicator: Position Size Calculator (tải từ Market)
- Script: tự động tính và đặt lệnh theo risk %

**Spreadsheet theo dõi:**
Tạo Excel/Google Sheets với các cột:
- Ngày | Cặp | Direction | Entry | SL | TP | Lots | Risk($) | R:R | Kết quả | P&L | Balance | Ghi chú

---

## Tài liệu đọc thêm

### Sách
- **"Trading in the Zone"** — Mark Douglas: Kinh điển về tâm lý và quản lý rủi ro
- **"The New Trading for a Living"** — Alexander Elder: Bao gồm chương về Money Management
- **"Van Tharp's Definitive Guide to Position Sizing"** — Van K. Tharp: Chuyên sâu về Position Sizing

### Website
- BabyPips.com/learn/forex/risk-management — Khóa học miễn phí, cực kỳ chi tiết
- Investopedia.com — Tra cứu các thuật ngữ
- Myfxbook.com — Tools và cộng đồng Forex

### Video
- YouTube: "Forex Risk Management" — nhiều kênh như Rayner Teo, UKspreadbetting
- YouTube: "Position Sizing Tutorial" — Nino Forex, Adam Khoo

---

## Ghi chú bổ sung

### Kelly Criterion (Nâng cao)
Công thức toán học tối ưu hóa kích thước lệnh:

```
Kelly % = W - [(1-W) / R]

Trong đó:
- W = Win Rate (ví dụ: 0.55 cho 55%)
- R = Win/Loss Ratio (ví dụ: 2 cho R:R 1:2)

Ví dụ: W=0.55, R=2
Kelly = 0.55 - [(1-0.55)/2] = 0.55 - 0.225 = 0.325 = 32.5%
```

Kelly Criterion nói rủi ro 32.5% mỗi lệnh — **ĐỪNG làm vậy!**

Trong thực tế, traders dùng **Half-Kelly** (16%) hoặc **Quarter-Kelly** (8%). Nhưng ngay cả vậy vẫn quá cao cho Forex với leverage.

**Kết luận**: Kelly Criterion hữu ích để hiểu lý thuyết, nhưng trong Forex thực tế, giới hạn 1-2% mỗi lệnh là cách thận trọng hơn cho người mới.

### Expectancy — Kỳ vọng toán học
Một hệ thống giao dịch tốt cần Expectancy dương:

```
Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)

Ví dụ:
- Win Rate: 50%, Avg Win: $200 (2R)
- Loss Rate: 50%, Avg Loss: $100 (1R)
- Expectancy = (0.5 × $200) - (0.5 × $100) = $100 - $50 = +$50 mỗi lệnh
```

Hệ thống này kỳ vọng kiếm $50 mỗi lệnh về dài hạn. Sau 100 lệnh: +$5,000 lợi nhuận kỳ vọng.
