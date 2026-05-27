# Tài liệu tham khảo — Ngày 19: Risk Management

## Bảng tóm tắt: Toán học thua lỗ

| Mức thua lỗ | Cần tăng để hòa vốn | Thời gian hòa vốn (nếu tăng 15%/năm) |
|-------------|---------------------|----------------------------------------|
| -10% | +11.1% | ~1 năm |
| -20% | +25% | ~2 năm |
| -30% | +42.9% | ~3 năm |
| -40% | +66.7% | ~4.5 năm |
| -50% | +100% | ~5 năm |
| -75% | +300% | >10 năm |
| -90% | +900% | Gần như không thể |

**Kết luận:** Tránh thua lỗ lớn là ưu tiên số 1, kiếm lợi nhuận lớn là số 2.

---

## Công thức Position Sizing

### Công thức cơ bản
```
Số lượng cổ phần = (Vốn × % Rủi ro tối đa) ÷ (Giá vào - Giá Stop-Loss)
```

### Ví dụ tính toán

**Bài toán:**
- Tổng vốn: 200 triệu VND
- Rủi ro tối đa mỗi lệnh: 1% = 2 triệu VND
- Cổ phiếu A: Giá mua 80,000 VND, Stop-loss 72,000 VND
- Rủi ro mỗi cổ phiếu: 80,000 - 72,000 = 8,000 VND

**Tính:**
- Số cổ phần tối đa = 2,000,000 ÷ 8,000 = **250 cổ phần**
- Tiền đầu tư = 250 × 80,000 = **20 triệu VND** (10% vốn)

**Kiểm tra:**
- Nếu hit stop-loss: Lỗ = 250 × 8,000 = 2 triệu = **đúng 1% vốn** ✓

---

## Cheat Sheet: Kiểm tra danh mục đầu tư

### Checklist hàng tháng
- [ ] Không có một mã nào chiếm >15% danh mục
- [ ] Không có một ngành nào chiếm >30% danh mục
- [ ] Tất cả vị thế đều có Stop-loss
- [ ] Cash reserve ≥ 10% để mua cơ hội
- [ ] Tỷ lệ Risk/Reward của mỗi vị thế ≥ 1:2
- [ ] Tổng rủi ro danh mục (nếu tất cả hit stop) < 15% vốn

### Checklist trước khi vào lệnh
- [ ] Đã xác định mức Stop-loss
- [ ] Đã tính Position Size theo quy tắc 1-2%
- [ ] Risk/Reward ≥ 1:2
- [ ] Không vào lệnh chỉ vì FOMO
- [ ] Có kế hoạch nếu giá đi ngược chiều

---

## So sánh các mô hình Asset Allocation

| Mô hình | Cổ phiếu | Trái phiếu | Vàng | Tiền mặt | Phù hợp với |
|---------|----------|------------|------|----------|-------------|
| **Aggressive (Tích cực)** | 80-90% | 5-10% | 5% | 5% | Trẻ, chấp nhận rủi ro cao |
| **Moderate (Vừa phải)** | 60% | 25% | 10% | 5% | Trung niên, cân bằng |
| **Conservative (Thận trọng)** | 30% | 50% | 10% | 10% | Gần nghỉ hưu |
| **All Weather (Dalio)** | 30% | 55% | 7.5% | 7.5% | Mọi giai đoạn kinh tế |
| **Boglehead (Index)** | 70-90% ETF | 10-30% Bond ETF | 0% | 0-10% | Đầu tư thụ động dài hạn |

---

## Tài liệu tham khảo

### Sách
- **"The Intelligent Investor" — Benjamin Graham:** Chương về Margin of Safety = Risk Management trong đầu tư giá trị
- **"Market Wizards" — Jack Schwager:** 17 trader huyền thoại, tất cả đều đề cao risk management
- **"Trading in the Zone" — Mark Douglas:** Tâm lý và discipline trong giao dịch
- **"The Zurich Axioms" — Max Gunther:** 12 nguyên tắc quản lý rủi ro từ nhà đầu tư Thụy Sĩ

### Khái niệm nâng cao (nghiên cứu sau)
- **Sharpe Ratio:** Lợi nhuận điều chỉnh theo rủi ro = (Lợi nhuận - Lãi suất phi rủi ro) / Độ lệch chuẩn
- **Sortino Ratio:** Tương tự Sharpe nhưng chỉ tính downside risk
- **Kelly Criterion:** Công thức toán học tối ưu hóa position sizing
- **Value at Risk (VaR):** Mức thua lỗ tối đa với xác suất nhất định

### Tools thực hành
- **Portfolio Visualizer (portfoliovisualizer.com):** Backtest và phân tích danh mục
- **Excel/Google Sheets:** Tạo bảng theo dõi Position Size
- **TradingView:** Đặt Stop-loss và Take-profit trực quan trên biểu đồ
