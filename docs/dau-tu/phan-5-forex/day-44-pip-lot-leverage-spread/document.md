# Tài liệu tham khảo — Ngày 44: Pip, Lot, Leverage & Spread

## Cheat Sheet: Giá trị Pip theo Lot Size

### EUR/USD (tỷ giá ~1.0850)
| Lot Size | Đơn vị | Pip Value (USD) | Biến động 100 pip = |
|----------|--------|----------------|---------------------|
| 1.0 (Standard) | 100,000 EUR | $10.00 | $1,000 |
| 0.5 | 50,000 EUR | $5.00 | $500 |
| 0.1 (Mini) | 10,000 EUR | $1.00 | $100 |
| 0.05 | 5,000 EUR | $0.50 | $50 |
| 0.01 (Micro) | 1,000 EUR | $0.10 | $10 |
| 0.001 (Nano) | 100 EUR | $0.01 | $1 |

### USD/JPY (tỷ giá ~150.00)
| Lot Size | Pip Value (USD) |
|----------|----------------|
| 1.0 | ~$6.67 |
| 0.1 | ~$0.67 |
| 0.01 | ~$0.067 |

*Lưu ý: Pip value USD/JPY = (0.01 / 150) × Lot size × 100,000*

---

## Bảng tính kích thước lệnh (Position Sizing)

**Công thức:**
```
Lot Size = (Vốn × % Rủi ro) / (Stop Loss pip × Pip Value)
```

**Bảng tham khảo nhanh (Rủi ro 1%, Stop Loss 50 pip, EUR/USD):**
| Vốn tài khoản | Rủi ro 1% | Lot Size | Pip Value |
|--------------|-----------|----------|-----------|
| $500 | $5 | 0.01 | $0.10/pip |
| $1,000 | $10 | 0.02 | $0.20/pip |
| $2,000 | $20 | 0.04 | $0.40/pip |
| $5,000 | $50 | 0.10 | $1.00/pip |
| $10,000 | $100 | 0.20 | $2.00/pip |

---

## Bảng so sánh Leverage và Rủi ro

| Leverage | Margin 1 Standard Lot (EUR/USD) | Số pip để mất 50% vốn (vốn = margin) |
|----------|--------------------------------|---------------------------------------|
| 1:500 | $216 | 10 pip |
| 1:200 | $543 | 25 pip |
| 1:100 | $1,085 | 50 pip |
| 1:50 | $2,170 | 100 pip |
| 1:20 | $5,425 | 250 pip |
| 1:10 | $10,850 | 500 pip |

**Khuyến nghị cho người mới:** Sử dụng leverage hiệu quả không vượt quá 1:10

---

## Calculator: Swap Rate

**Ví dụ Swap rates (hàng năm):**
| Cặp tiền | Buy Swap | Sell Swap |
|----------|----------|-----------|
| EUR/USD | -5.20% | +2.80% |
| GBP/USD | -4.10% | +1.90% |
| AUD/USD | -0.80% | -0.40% |
| USD/JPY | +3.20% | -5.80% |

*Lưu ý: Swap thay đổi theo quyết định lãi suất của NHTW*

**Tính swap hàng đêm:**
```
Swap = (Lot Size × Contract Size × Swap Rate) / 365
Ví dụ: Buy 0.1 lot EUR/USD, Swap = -5.20%/năm
= (0.1 × 100,000 × -5.20%) / 365
= -1.42 USD/đêm
```

---

## Lịch sử Spread EUR/USD

| Thời điểm | Spread điển hình |
|-----------|----------------|
| Giờ bình thường (phiên London-NY) | 0.1 - 1.5 pip |
| Phiên Sydney (thanh khoản thấp) | 1.5 - 3 pip |
| Cuối tuần/đầu tuần | 2 - 5 pip |
| Trong khi có tin NFP | 10 - 30 pip |
| Trong FOMC Statement | 15 - 50 pip |
| Sự kiện bất ngờ (Black Swan) | 50 - 200+ pip |

---

## Tài liệu đọc thêm

**Công cụ tính toán online:**
- [Myfxbook Position Size Calculator](https://www.myfxbook.com/forex-calculators/position-size)
- [Investing.com Pip Calculator](https://www.investing.com/tools/pip-calculator)

**Sách:**
- *Forex Price Action Scalping* — Bob Volman (hiểu sâu về pip và price movement)
- *The Disciplined Trader* — Mark Douglas (tâm lý giao dịch)

---

## Ghi chú nâng cao: Requote và Slippage

**Requote**: Khi bạn đặt lệnh ở một giá, nhưng broker trả về giá khác vì thị trường đã di chuyển. Thường xảy ra với broker Market Maker trong tin tức mạnh.

**Slippage**: Lệnh được thực thi ở giá khác giá bạn đặt, thường bất lợi cho bạn:
- Stop Loss ở 1.0800, nhưng thực thi ở 1.0795 (gap qua giá)
- Take Profit ở 1.0950, nhưng thực thi ở 1.0948

Slippage phổ biến trong:
- Tin tức quan trọng (NFP, CPI, FOMC)
- Mở cửa thị trường đầu tuần (gap weekend)
- Thanh khoản thấp (đêm khuya, holiday)

**Cách hạn chế slippage:**
- Dùng broker ECN/STP (khớp lệnh thẳng với thị trường)
- Tránh giao dịch ngay lúc tin tức phát hành
- Đặt Limit Order thay vì Market Order
