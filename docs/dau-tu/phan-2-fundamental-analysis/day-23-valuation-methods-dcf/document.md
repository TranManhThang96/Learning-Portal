# Tài Liệu Tham Khảo — Ngày 23: Valuation Methods & DCF

## Cheat Sheet: So Sánh Các Phương Pháp Định Giá

| Phương pháp | Dựa trên | Ưu điểm | Nhược điểm | Phù hợp với |
|-------------|----------|---------|------------|-------------|
| DCF | FCF tương lai | Khách quan, không phụ thuộc thị trường | Rất nhạy cảm với giả định | Doanh nghiệp FCF ổn định |
| P/E Comps | Lợi nhuận + so sánh ngành | Nhanh, dễ | Thị trường có thể đang sai | Doanh nghiệp trưởng thành |
| EV/EBITDA Comps | EBITDA + so sánh ngành | Trung lập với cấu trúc vốn | Bỏ qua CapEx | M&A, so sánh xuyên biên giới |
| P/B | Giá trị sổ sách | Đơn giản | Bỏ qua tài sản vô hình | Ngân hàng, tài chính |
| Asset-based | Giá trị tài sản ròng | Rõ ràng | Bỏ qua tiềm năng kinh doanh | Bất động sản, thanh lý |
| DDM | Cổ tức tương lai | Phù hợp cổ phiếu cổ tức | Chỉ dùng được khi có cổ tức ổn định | Utilities, REITs |

---

## DCF Template — Bảng Tính Nhanh

```
BƯỚC 1: FREE CASH FLOW HIỆN TẠI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Operating Cash Flow:     _____ tỷ
- Capital Expenditure:   _____ tỷ
= Free Cash Flow (FCF₀): _____ tỷ

BƯỚC 2: DỰ BÁO FCF (5 NĂM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tốc độ tăng trưởng giai đoạn 1:  _____ %

Năm 1: FCF₀ × (1+g)¹  = _____
Năm 2: FCF₀ × (1+g)²  = _____
Năm 3: FCF₀ × (1+g)³  = _____
Năm 4: FCF₀ × (1+g)⁴  = _____
Năm 5: FCF₀ × (1+g)⁵  = _____

BƯỚC 3: DISCOUNT RATE (WACC)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WACC = _____ %

BƯỚC 4: CHIẾT KHẤU FCF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PV(Năm 1) = FCF₁ / (1+WACC)¹ = _____
PV(Năm 2) = FCF₂ / (1+WACC)² = _____
PV(Năm 3) = FCF₃ / (1+WACC)³ = _____
PV(Năm 4) = FCF₄ / (1+WACC)⁴ = _____
PV(Năm 5) = FCF₅ / (1+WACC)⁵ = _____
Tổng PV(FCF): _____

BƯỚC 5: TERMINAL VALUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Terminal Growth Rate (g): _____ %
Terminal Value = FCF₅ × (1+g) / (WACC - g) = _____
PV(Terminal Value) = TV / (1+WACC)⁵ = _____

BƯỚC 6: TỔNG HỢP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enterprise Value (EV)    = PV(FCF) + PV(TV) = _____
- Net Debt               = Total Debt - Cash = _____
= Equity Value           = _____
÷ Shares Outstanding     = _____ CP
= Intrinsic Value/Share  = _____

BƯỚC 7: MARGIN OF SAFETY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Intrinsic Value          = _____
Margin of Safety (30%)   = Intrinsic Value × 0.70 = _____
Margin of Safety (50%)   = Intrinsic Value × 0.50 = _____
```

---

## Bảng Discount Factor Nhanh

| Năm | WACC 8% | WACC 10% | WACC 12% | WACC 15% |
|-----|---------|----------|----------|----------|
| 1 | 0.926 | 0.909 | 0.893 | 0.870 |
| 2 | 0.857 | 0.826 | 0.797 | 0.756 |
| 3 | 0.794 | 0.751 | 0.712 | 0.658 |
| 4 | 0.735 | 0.683 | 0.636 | 0.572 |
| 5 | 0.681 | 0.621 | 0.567 | 0.497 |
| 7 | 0.583 | 0.513 | 0.452 | 0.376 |
| 10 | 0.463 | 0.386 | 0.322 | 0.247 |

---

## Ước Tính WACC Đơn Giản

### Phương pháp đơn giản cho người mới:

```
Discount Rate gợi ý:
• Doanh nghiệp VN blue-chip ổn định:   10 - 12%
• Doanh nghiệp VN tăng trưởng tốt:     12 - 15%
• Doanh nghiệp VN rủi ro cao:           15 - 20%
• Cổ phiếu Mỹ S&P 500:                  8 - 10%
• Cổ phiếu Mỹ tăng trưởng (FAANG):    10 - 12%
• Cổ phiếu Mỹ rủi ro cao (small cap):  12 - 15%

Nguyên tắc: WACC càng cao → Định giá càng thận trọng
```

### WACC đầy đủ (nâng cao):

```
WACC = (E/V × Re) + (D/V × Rd × (1 - T))

Tính Re (Cost of Equity) dùng CAPM:
Re = Rf + β × (Rm - Rf)

Rf = Risk-free rate (lãi suất phi rủi ro)
     = Lãi suất trái phiếu chính phủ 10 năm
     VN ≈ 4-5%, Mỹ ≈ 4-5%

β (Beta) = Độ nhạy cảm với thị trường
     β < 1: Ít biến động hơn thị trường
     β = 1: Biến động bằng thị trường
     β > 1: Biến động nhiều hơn thị trường

(Rm - Rf) = Equity Risk Premium ≈ 5-7%
```

---

## Terminal Growth Rate — Hướng Dẫn Chọn

| Loại doanh nghiệp | Terminal Growth Rate |
|-------------------|---------------------|
| Doanh nghiệp toàn cầu, ngành tăng trưởng | 3 - 4% |
| Doanh nghiệp ổn định, ngành trưởng thành | 2 - 3% |
| Doanh nghiệp địa phương | 2 - 3% |
| Ngành đang suy tàn | 0 - 1% |

> **Quy tắc vàng**: Terminal Growth Rate KHÔNG được > WACC (toán học vô lý) và KHÔNG nên > tăng trưởng GDP dài hạn dự kiến.

---

## Sensitivity Table — Kịch Bản Phân Tích

Luôn tính DCF với ít nhất 3 kịch bản:

```
KỊCH BẢN THẬN TRỌNG (Bear Case):
  - Tăng trưởng thấp hơn kỳ vọng 30-40%
  - WACC cao hơn 2-3%
  - Terminal Growth = GDP - 1%

KỊCH BẢN CƠ SỞ (Base Case):
  - Tăng trưởng theo dự báo
  - WACC = chi phí vốn thực tế
  - Terminal Growth = GDP dài hạn

KỊCH BẢN LẠC QUAN (Bull Case):
  - Tăng trưởng cao hơn 20-30%
  - WACC thấp hơn 1-2%
  - Terminal Growth = GDP + 1%

→ Chỉ nên đầu tư khi EVEN Bear Case
  vẫn cho Margin of Safety dương!
```

---

## Ví Dụ Thực Tế: Định Giá Apple (Đơn Giản Hóa)

*Số liệu minh họa, không phải khuyến nghị đầu tư*

```
FCF 2023: ~$99 tỷ
Tăng trưởng dự báo 5 năm: 8%/năm
WACC: 9%
Terminal Growth: 3%
Shares: 15.4 tỷ CP
Net Cash: +$50 tỷ (tiền > nợ)

PV(FCF 5 năm) ≈ $415 tỷ
Terminal Value = FCF₅ × 1.03 / (0.09-0.03) = ~$1,940 tỷ
PV(Terminal Value) = $1,940 / (1.09)^5 ≈ $1,260 tỷ

EV ≈ 415 + 1,260 = $1,675 tỷ
Equity Value = 1,675 + 50 = $1,725 tỷ
Intrinsic Value/CP = $1,725B / 15.4B = ~$112/CP

Giá thị trường Apple ~$190/CP
→ Thị trường đang định giá cao hơn mô hình này
→ Thị trường kỳ vọng tăng trưởng cao hơn HOẶC chấp nhận WACC thấp hơn
```

---

## Tài Liệu Đọc Thêm

**Sách:**
- *The Intelligent Investor* — Benjamin Graham (Chương 20: Margin of Safety)
- *Valuation: Measuring and Managing the Value of Companies* — McKinsey (sách giáo khoa chuẩn)
- *Investment Valuation* — Aswath Damodaran (chi tiết nhất về DCF)

**Online Resources (miễn phí):**
- **Damodaran Online**: Dữ liệu Beta, Risk Premium, WACC theo ngành
- **DCF Calculator trên Finbox / Wisesheets**: Tính DCF tự động
- **Simply Wall St**: Visualize DCF dễ nhìn
- **Macrotrends**: Lịch sử FCF của công ty Mỹ

**Video:**
- YouTube "Aswath Damodaran DCF": Giáo sư định giá nổi tiếng nhất thế giới — free lectures

---

## Ghi Chú Bổ Sung: Hạn Chế Của DCF

1. **"Garbage in, garbage out"**: Dự báo sai → kết quả hoàn toàn sai
2. **Nhạy cảm với Terminal Value**: Chiếm 60-80% tổng giá trị — sai 1% g là sai cả ngàn tỷ
3. **Khó dùng cho**: Startup (FCF âm), ngân hàng (FCF khái niệm khác), công ty chu kỳ cao
4. **Giải pháp**: Luôn sensitivity analysis + kiểm tra chéo với Relative Valuation
5. **Quan điểm thực tiễn**: DCF là công cụ để **tư duy**, không phải máy in ra giá "chính xác"
