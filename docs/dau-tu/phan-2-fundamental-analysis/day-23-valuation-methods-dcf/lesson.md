# Ngày 23: Valuation Methods — Định Giá Bao Nhiêu Là Hợp Lý?

## Mục tiêu học tập

- [ ] Phân biệt hai phương pháp định giá chính: Relative Valuation và Absolute Valuation
- [ ] Hiểu và áp dụng DCF (Discounted Cash Flow) step-by-step
- [ ] Tính Intrinsic Value và so sánh với giá thị trường
- [ ] Hiểu và áp dụng Margin of Safety trong đầu tư
- [ ] Biết khi nào dùng phương pháp nào và hạn chế của từng phương pháp

---

## Nội dung bài giảng

### 1. Tổng Quan: Hai Trường Phái Định Giá

Câu hỏi cốt lõi của phân tích cơ bản là: **"Giá trị thực của doanh nghiệp này là bao nhiêu?"**

Có hai cách tiếp cận chính:

```
┌─────────────────────────────────────────────────────┐
│           PHƯƠNG PHÁP ĐỊNH GIÁ                      │
├──────────────────────┬──────────────────────────────┤
│  RELATIVE VALUATION  │    ABSOLUTE VALUATION        │
│  (Định giá tương đối)│    (Định giá tuyệt đối)      │
├──────────────────────┼──────────────────────────────┤
│ So sánh với:         │ Tính từ giá trị nội tại:     │
│ • Đối thủ cùng ngành │ • DCF (Discounted Cash Flow) │
│ • Lịch sử công ty    │ • Dividend Discount Model    │
│ • Thị trường chung   │ • Asset-based Valuation      │
│                      │                              │
│ Dùng: P/E, P/B,      │ Dùng: Dự báo FCF,           │
│ EV/EBITDA, PEG...    │ Discount Rate (WACC)...      │
├──────────────────────┼──────────────────────────────┤
│ Nhanh, phổ biến      │ Phức tạp hơn, chính xác hơn  │
│ Phụ thuộc thị trường │ Độc lập với thị trường       │
└──────────────────────┴──────────────────────────────┘
```

**Relative Valuation** (đã học Ngày 22): Nếu toàn bộ thị trường đang bong bóng, so sánh tương đối vẫn sẽ cho kết quả "hợp lý" — nhưng tất cả đều đang đắt.

**Absolute Valuation** (hôm nay): Tìm ra giá trị nội tại độc lập với tâm lý thị trường — nền tảng của đầu tư giá trị.

---

### 2. Intrinsic Value — Giá Trị Nội Tại Là Gì?

**Intrinsic Value (giá trị nội tại)** là giá trị "thật" của một doanh nghiệp, dựa trên khả năng tạo ra tiền mặt trong tương lai.

> **Warren Buffett**: "Intrinsic value is the discounted value of the cash that can be taken out of a business during its remaining life."

Nguyên lý cơ bản: **Một đồng hôm nay có giá trị hơn một đồng ngày mai** (Time Value of Money — giá trị thời gian của tiền).

**Tại sao?**
- Đồng tiền hôm nay có thể đầu tư sinh lời
- Lạm phát làm giảm sức mua theo thời gian
- Tương lai không chắc chắn (rủi ro)

---

### 3. Time Value of Money — Nền Tảng Của DCF

#### 3.1. Future Value (Giá trị tương lai)

```
FV = PV × (1 + r)^n

Trong đó:
PV = Present Value (giá trị hiện tại)
r  = Lãi suất / tỷ suất sinh lời
n  = Số năm
```

**Ví dụ**: 100 triệu VND hôm nay với lãi suất 10%/năm, sau 5 năm sẽ là:
FV = 100 × (1 + 0.10)^5 = 100 × 1.61 = **161 triệu VND**

#### 3.2. Present Value (Giá trị hiện tại — quan trọng hơn cho DCF)

```
PV = FV / (1 + r)^n
```

**Chiều ngược lại**: 100 triệu nhận được sau 5 năm, với lãi suất chiết khấu 10%, giá trị hiện tại chỉ là:
PV = 100 / (1.10)^5 = 100 / 1.61 = **62.1 triệu VND**

Đây chính là **chiết khấu** (discounting) — đưa giá trị tương lai về hiện tại.

---

### 4. DCF — Discounted Cash Flow (Chiết Khấu Dòng Tiền)

DCF là phương pháp tính giá trị hiện tại của **tất cả dòng tiền tự do tương lai** mà doanh nghiệp có thể tạo ra.

```
Intrinsic Value = Σ [FCF_t / (1 + WACC)^t]  +  Terminal Value / (1 + WACC)^n
```

**Nghe phức tạp?** Hãy chia nhỏ thành 5 bước đơn giản.

---

### 5. DCF Step-by-Step — 5 Bước Thực Hiện

#### Bước 1: Xác định Free Cash Flow hiện tại

Lấy FCF từ Cash Flow Statement (đã học Ngày 21):
```
FCF = Operating Cash Flow - Capital Expenditure
```

#### Bước 2: Dự báo FCF trong giai đoạn tăng trưởng (thường 5-10 năm)

Ước tính FCF sẽ tăng trưởng với tốc độ nào trong tương lai?

- Dùng lịch sử tăng trưởng FCF
- Dùng dự báo tăng trưởng doanh thu và margin
- Tham khảo analyst estimates

**Ví dụ thực hành — Công ty FPT (số liệu giả định minh họa):**

| Năm | FCF dự báo | Tốc độ tăng trưởng |
|-----|-----------|-------------------|
| Hiện tại (0) | 3,000 tỷ | — |
| Năm 1 | 3,300 tỷ | 10% |
| Năm 2 | 3,630 tỷ | 10% |
| Năm 3 | 3,993 tỷ | 10% |
| Năm 4 | 4,392 tỷ | 10% |
| Năm 5 | 4,832 tỷ | 10% |

#### Bước 3: Chọn Discount Rate — WACC

**WACC (Weighted Average Cost of Capital — Chi phí vốn bình quân gia quyền)** là tỷ lệ chiết khấu, phản ánh chi phí huy động vốn của doanh nghiệp và mức độ rủi ro.

```
WACC = (E/V × Re) + (D/V × Rd × (1 - T))

Trong đó:
E = Giá trị vốn chủ sở hữu (Equity)
D = Giá trị nợ (Debt)
V = E + D (tổng vốn)
Re = Chi phí vốn chủ (Cost of Equity)
Rd = Chi phí nợ (Cost of Debt = lãi suất vay)
T  = Thuế suất doanh nghiệp
```

**Đơn giản hóa**: Đối với người mới, có thể dùng tỷ lệ chiết khấu đơn giản:
- Doanh nghiệp Việt Nam ổn định: 12-15%
- Doanh nghiệp Việt Nam rủi ro cao: 15-20%
- Cổ phiếu Mỹ ổn định: 8-12%
- Cổ phiếu Mỹ tăng trưởng cao: 10-15%

*Trong ví dụ này, dùng WACC = 12%*

#### Bước 4: Chiết khấu FCF về hiện tại

```
PV(FCF_t) = FCF_t / (1 + WACC)^t
```

| Năm | FCF dự báo | Discount Factor (12%) | PV của FCF |
|-----|-----------|----------------------|------------|
| 1 | 3,300 tỷ | 1/(1.12)^1 = 0.893 | 2,946 tỷ |
| 2 | 3,630 tỷ | 1/(1.12)^2 = 0.797 | 2,893 tỷ |
| 3 | 3,993 tỷ | 1/(1.12)^3 = 0.712 | 2,843 tỷ |
| 4 | 4,392 tỷ | 1/(1.12)^4 = 0.636 | 2,793 tỷ |
| 5 | 4,832 tỷ | 1/(1.12)^5 = 0.567 | 2,740 tỷ |
| **Tổng** | | | **14,215 tỷ** |

#### Bước 5: Tính Terminal Value và cộng lại

Doanh nghiệp không kết thúc sau 5 năm. **Terminal Value (giá trị cuối)** đại diện cho tất cả giá trị sau năm dự báo.

**Công thức Gordon Growth Model (phổ biến nhất):**
```
Terminal Value = FCF_5 × (1 + g) / (WACC - g)

Trong đó:
g = Terminal Growth Rate (tốc độ tăng trưởng vĩnh viễn)
    Thường = 2-4% (gần bằng tăng trưởng GDP dài hạn)
```

**Ví dụ** (g = 3%):
```
Terminal Value = 4,832 × (1 + 0.03) / (0.12 - 0.03)
              = 4,977 / 0.09
              = 55,300 tỷ VND
```

Chiết khấu Terminal Value về hiện tại:
```
PV(Terminal Value) = 55,300 / (1.12)^5
                   = 55,300 / 1.762
                   = 31,385 tỷ VND
```

**Tổng Enterprise Value (EV):**
```
EV = PV của FCF 5 năm + PV của Terminal Value
   = 14,215 + 31,385
   = 45,600 tỷ VND
```

**Tính giá trị nội tại mỗi cổ phiếu:**
```
Intrinsic Value/CP = (EV - Net Debt) / Số CP lưu hành
Net Debt = Total Debt - Cash = 3,000 - 1,500 = 1,500 tỷ

Equity Value = 45,600 - 1,500 = 44,100 tỷ
Giả sử có 500 triệu CP:
Intrinsic Value = 44,100 tỷ / 500 triệu = 88,200 VND/CP
```

---

### 6. Margin of Safety — Biên An Toàn

Bạn vừa tính được Intrinsic Value = 88,200 VND. Vậy nên mua ở giá nào?

**Margin of Safety (biên an toàn)** là khoảng cách giữa giá mua và giá trị nội tại, tạo ra "vùng đệm" bảo vệ nhà đầu tư khi dự báo sai.

```
Margin of Safety = (Intrinsic Value - Market Price) / Intrinsic Value × 100%
```

**Benjamin Graham (cha đẻ của Value Investing)**: Chỉ mua khi Margin of Safety ít nhất **30-50%**.

**Ví dụ:**
- Intrinsic Value = 88,200 VND
- Margin of Safety 30% → Mua ở giá tối đa: 88,200 × (1 - 0.30) = **61,740 VND**
- Margin of Safety 50% → Mua ở giá tối đa: 88,200 × 0.50 = **44,100 VND**

**Tại sao cần Margin of Safety?**

DCF rất nhạy cảm với các giả định đầu vào. Nếu dự báo tăng trưởng quá lạc quan hoặc WACC quá thấp, kết quả có thể sai lệch nhiều. Margin of Safety bảo vệ bạn khỏi:
1. Sai lầm trong dự báo
2. Những rủi ro bất ngờ không lường trước
3. Tình trạng thị trường xấu trong ngắn hạn

---

### 7. Sensitivity Analysis — Phân Tích Độ Nhạy

DCF thay đổi rất nhiều tùy theo giả định. Hãy xem giá trị nội tại thay đổi như thế nào khi thay đổi WACC và g:

**Bảng giá trị nội tại (VND/CP) theo WACC và Terminal Growth Rate:**

| | g = 2% | g = 3% | g = 4% |
|--|--------|--------|--------|
| WACC = 10% | 102,000 | 118,000 | 142,000 |
| WACC = 12% | 79,000 | 88,200 | 102,000 |
| WACC = 14% | 63,000 | 69,000 | 78,000 |

**Kết luận**: Giá trị nội tại dao động từ 63,000 đến 142,000 — phạm vi rất rộng! Đây là lý do tại sao Margin of Safety quan trọng.

> "DCF là công cụ tốt nhất để suy nghĩ về giá trị, không phải để tính chính xác." — Howard Marks

---

### 8. Relative Valuation — Bổ Sung Cho DCF

Sau khi có kết quả DCF, hãy kiểm tra chéo bằng Relative Valuation:

**Phương pháp Comps (Comparable Companies):**

1. Tìm 3-5 công ty tương đương trong ngành (peers)
2. Tính EV/EBITDA trung bình của các peers
3. Áp dụng vào EBITDA của công ty đang phân tích

**Ví dụ:**

| Peer | EV/EBITDA |
|------|----------|
| Công ty B | 12x |
| Công ty C | 14x |
| Công ty D | 11x |
| **Trung bình** | **12.3x** |

Nếu EBITDA của công ty phân tích = 3,600 tỷ:
```
Implied EV = 3,600 × 12.3 = 44,280 tỷ
```

Kết quả gần với DCF (45,600 tỷ) → Tăng độ tin cậy vào định giá!

---

### 9. Asset-Based Valuation — Khi Nào Dùng?

**Phương pháp định giá theo tài sản** thích hợp cho:
- Doanh nghiệp bất động sản (giá trị chủ yếu từ đất đai, tài sản)
- Công ty đang thanh lý
- Ngân hàng (Net Asset Value)

```
Asset-Based Value = Total Assets - Total Liabilities = Total Equity (Book Value)
```

Với nhiều doanh nghiệp tăng trưởng, Book Value **thấp hơn nhiều** so với giá trị thực (vì tài sản vô hình không được ghi nhận đầy đủ). Đây là lý do P/B của Apple > 40x — phần lớn giá trị Apple là thương hiệu, hệ sinh thái, không phải tài sản hữu hình.

---

### 10. Khi Nào Dùng Phương Pháp Nào?

| Tình huống | Phương pháp phù hợp |
|------------|---------------------|
| Công ty có FCF ổn định, dự báo được | DCF |
| So sánh nhanh trong ngành | Relative (P/E, EV/EBITDA) |
| Startup, chưa có lợi nhuận | Revenue multiple, DCF với nhiều kịch bản |
| Ngân hàng | P/B, ROE |
| Bất động sản | Asset-based, DCF |
| M&A | EV/EBITDA, DCF |
| Kiểm tra chéo | Dùng cả hai! |

---

## Tóm Tắt Kiến Thức Chính (Key Takeaways)

1. **Relative Valuation** (P/E, EV/EBITDA) nhanh nhưng phụ thuộc tâm lý thị trường
2. **Absolute Valuation (DCF)** tính giá trị nội tại độc lập với thị trường — chuẩn mực của value investing
3. **DCF gồm 5 bước**: Xác định FCF → Dự báo → Chọn WACC → Chiết khấu → Cộng Terminal Value
4. **Terminal Value** chiếm 60-80% tổng giá trị DCF — nhạy cảm với giả định tăng trưởng dài hạn
5. **Margin of Safety** ít nhất 30%: Chỉ mua khi giá thị trường thấp hơn giá trị nội tại đáng kể
6. **Sensitivity Analysis**: Luôn kiểm tra kết quả với nhiều kịch bản khác nhau
7. **Kết hợp cả hai**: Dùng DCF làm neo định giá, Relative Valuation để kiểm tra chéo

---

## Thuật Ngữ Quan Trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| Intrinsic Value | Giá trị nội tại | Giá trị "thật" dựa trên khả năng sinh tiền |
| DCF | Chiết khấu dòng tiền | Phương pháp định giá tuyệt đối |
| Discounting | Chiết khấu | Đưa giá trị tương lai về hiện tại |
| Present Value (PV) | Giá trị hiện tại | Giá trị quy đổi về thời điểm hiện tại |
| Future Value (FV) | Giá trị tương lai | Giá trị tại một thời điểm tương lai |
| WACC | Chi phí vốn bình quân | Tỷ lệ chiết khấu cho DCF |
| Terminal Value | Giá trị cuối | Giá trị sau giai đoạn dự báo |
| Terminal Growth Rate | Tốc độ tăng trưởng vĩnh viễn | Thường 2-4%, gần bằng tăng trưởng GDP |
| Margin of Safety | Biên an toàn | Khoảng cách an toàn giữa giá mua và intrinsic value |
| Relative Valuation | Định giá tương đối | So sánh với peers |
| Comps | So sánh tương đồng | Comparable companies analysis |
| Sensitivity Analysis | Phân tích độ nhạy | Kiểm tra kết quả khi thay đổi giả định |
| Time Value of Money | Giá trị thời gian của tiền | 1 đồng hôm nay > 1 đồng tương lai |

---

## Bài Học Tiếp Theo

**Ngày 24: Industry Analysis** — Bạn đã biết cách phân tích một doanh nghiệp từ báo cáo tài chính đến định giá. Bước tiếp theo là hiểu **bối cảnh ngành** — vì doanh nghiệp tốt trong ngành xấu thường thất bại, còn doanh nghiệp trung bình trong ngành tốt đôi khi vẫn thành công. Chúng ta sẽ học cách phân tích Top-down (vĩ mô → ngành → doanh nghiệp) và chu kỳ luân phiên ngành (Sector Rotation).
