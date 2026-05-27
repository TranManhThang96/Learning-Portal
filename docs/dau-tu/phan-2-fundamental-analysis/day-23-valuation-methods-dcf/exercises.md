# Bài Tập — Ngày 23: Valuation Methods & DCF

## Phần 1: Câu Hỏi Ôn Tập (Quiz)

**1. Intrinsic Value của một cổ phiếu là gì?**
- A. Giá cổ phiếu hiện tại trên thị trường
- B. Giá trị "thật" dựa trên khả năng tạo ra dòng tiền trong tương lai
- C. Giá trị sổ sách (Book Value)
- D. Giá cao nhất cổ phiếu đạt được trong 52 tuần

**2. Tại sao $100 ngày hôm nay có giá trị hơn $100 nhận được 5 năm sau?**
- A. Vì lạm phát, cơ hội đầu tư, và rủi ro tương lai
- B. Vì chính phủ tăng thuế
- C. Vì giá cổ phiếu luôn tăng
- D. Vì đồng tiền in thêm nhiều hơn

**3. Trong DCF, WACC được dùng để làm gì?**
- A. Ước tính doanh thu tương lai
- B. Chiết khấu dòng tiền tương lai về hiện tại
- C. Tính lợi nhuận doanh nghiệp
- D. So sánh với đối thủ cạnh tranh

**4. Terminal Value trong DCF đại diện cho điều gì?**
- A. Giá cổ phiếu cuối năm dự báo
- B. Tổng giá trị doanh nghiệp sau giai đoạn dự báo 5-10 năm
- C. Chi phí mua lại doanh nghiệp
- D. Lợi nhuận năm cuối cùng

**5. Công thức Terminal Value theo Gordon Growth Model là gì?**
- A. TV = FCF₅ × WACC / g
- B. TV = FCF₅ / (WACC + g)
- C. TV = FCF₅ × (1 + g) / (WACC - g)
- D. TV = FCF₅ × n × g

**6. Nếu WACC = 12% và Terminal Growth Rate = 12%, điều gì xảy ra?**
- A. Terminal Value = 0
- B. Terminal Value = vô cùng (phép chia cho 0 — vô nghĩa)
- C. Terminal Value = FCF₅
- D. Không tính được EV

**7. Benjamin Graham khuyến nghị Margin of Safety tối thiểu là bao nhiêu?**
- A. 5 - 10%
- B. 15 - 20%
- C. 30 - 50%
- D. 70 - 80%

**8. Tại sao Sensitivity Analysis quan trọng trong DCF?**
- A. Để tìm ra một con số chính xác duy nhất
- B. Để hiểu kết quả thay đổi như thế nào khi giả định đầu vào thay đổi
- C. Để so sánh với đối thủ
- D. Để tính thuế đầu tư

**9. Phương pháp "Comps" (Comparable Companies) thuộc loại định giá nào?**
- A. Absolute Valuation
- B. DCF Analysis
- C. Relative Valuation
- D. Asset-based Valuation

**10. Terminal Value thường chiếm bao nhiêu phần trăm tổng Enterprise Value trong DCF?**
- A. 10 - 20%
- B. 30 - 40%
- C. 60 - 80%
- D. 90 - 100%

---

## Phần 2: Bài Tập Tính Toán

### Bài Tập 1: Time Value of Money

Áp dụng khái niệm Present Value:

1. Bạn sẽ nhận 500 triệu VND sau 3 năm. Với lãi suất chiết khấu 10%/năm, giá trị hiện tại của khoản tiền này là bao nhiêu?

2. Bạn đầu tư 200 triệu hôm nay với lãi suất 12%/năm. Sau 5 năm bạn có bao nhiêu?

3. Doanh nghiệp dự kiến tạo ra FCF như sau: Năm 1: 100 tỷ, Năm 2: 120 tỷ, Năm 3: 140 tỷ. Với WACC = 10%, tổng PV của 3 dòng tiền này là bao nhiêu?

---

### Bài Tập 2: DCF Hoàn Chỉnh

**Dữ liệu Công ty Vinatech JSC (giả định):**
- FCF hiện tại: 1,200 tỷ VND
- Tốc độ tăng trưởng FCF trong 5 năm tới: 15%/năm
- WACC: 12%
- Terminal Growth Rate: 3%
- Total Debt: 2,000 tỷ VND
- Cash & Equivalents: 800 tỷ VND
- Số cổ phiếu lưu hành: 300 triệu CP
- Giá cổ phiếu hiện tại: 28,000 VND

**Yêu cầu:**
1. Tính FCF cho năm 1 đến năm 5
2. Chiết khấu từng FCF về hiện tại (dùng bảng Discount Factor từ document.md)
3. Tính Terminal Value và PV của Terminal Value
4. Tính Enterprise Value, Equity Value, và Intrinsic Value/CP
5. Tính Margin of Safety so với giá hiện tại 28,000 VND
6. Theo bạn, cổ phiếu này đang rẻ hay đắt trong mô hình giả định? Cần kiểm tra gì trước khi ra quyết định?

---

### Bài Tập 3: Sensitivity Analysis

Dùng kết quả từ Bài Tập 2, thực hiện Sensitivity Analysis:

Tính lại Intrinsic Value/CP với các kịch bản sau và điền vào bảng:

| | g = 2% | g = 3% | g = 4% |
|--|--------|--------|--------|
| WACC = 10% | ? | ? | ? |
| WACC = 12% | ? | ? (đã tính) | ? |
| WACC = 14% | ? | ? | ? |

*(Gợi ý: Chỉ cần thay đổi Terminal Value và PV(TV) — phần PV(FCF 5 năm) thay đổi ít)*

---

### Bài Tập 4: So Sánh Phương Pháp Định Giá

Bạn đang phân tích hai cổ phiếu:

**Cổ phiếu X (Ngân hàng lớn):**
- EPS: 5,000 VND
- Book Value/CP: 30,000 VND
- FCF không rõ ràng (đặc thù ngành)
- ROE: 18%
- P/E trung bình ngành: 12x
- P/B trung bình ngành: 1.5x
- Giá hiện tại: 52,000 VND

**Cổ phiếu Y (Công ty phần mềm startup):**
- Net Income: -50 tỷ (đang lỗ)
- Revenue: 500 tỷ
- Revenue growth: 80%/năm
- P/S trung bình ngành: 8x
- Giá hiện tại: Market Cap = 4,000 tỷ VND

**Yêu cầu:**
1. Phương pháp định giá nào phù hợp nhất cho từng cổ phiếu? Tại sao?
2. Tính giá trị ngụ ý (implied value) của Cổ phiếu X bằng P/E và P/B comps
3. Tính Market Cap ngụ ý của Cổ phiếu Y bằng P/S comps
4. Đánh giá: Cổ phiếu nào đang rẻ/đắt so với ngành?

---

## Phần 3: Case Study

### Tình Huống: DCF Khác Nhau Vì Giả Định Khác Nhau

Hai analyst đều phân tích cùng một công ty với FCF₀ = 1,000 tỷ, 300 triệu CP đang lưu hành, Net Debt = 2,000 tỷ. Kết quả của họ:

**Analyst A (Lạc quan):**
- Tăng trưởng 5 năm: 20%/năm
- WACC: 10%
- Terminal Growth: 4%
- → Intrinsic Value: **85,000 VND/CP**

**Analyst B (Thận trọng):**
- Tăng trưởng 5 năm: 8%/năm
- WACC: 14%
- Terminal Growth: 2%
- → Intrinsic Value: **21,000 VND/CP**

Giá thị trường hiện tại: 40,000 VND/CP

**Câu hỏi thảo luận:**
1. Tại sao hai analyst cùng phân tích một công ty lại ra kết quả khác nhau 4 lần?
2. Giả định nào tạo ra sự khác biệt lớn nhất?
3. Nhà đầu tư nên làm gì khi đối mặt với phạm vi giá trị rộng như vậy?
4. Trong trường hợp này, Margin of Safety có ý nghĩa gì?

---

## Đáp Án & Giải Thích

### Quiz

1. **B** — Intrinsic Value là giá trị dựa trên khả năng tạo ra dòng tiền trong tương lai
2. **A** — Time Value of Money: tiền hôm nay có thể sinh lãi, lạm phát làm mòn giá trị, tương lai bất định
3. **B** — WACC là tỷ lệ chiết khấu để đưa giá trị tương lai về hiện tại
4. **B** — Terminal Value đại diện cho tất cả giá trị sau giai đoạn dự báo
5. **C** — TV = FCF₅ × (1 + g) / (WACC - g)
6. **B** — Mẫu số = WACC - g = 0 → phép chia vô nghĩa, Terminal Growth không được >= WACC
7. **C** — Benjamin Graham khuyên Margin of Safety 30-50%
8. **B** — Sensitivity Analysis cho thấy dải giá trị và rủi ro của từng giả định
9. **C** — Comps là Relative Valuation
10. **C** — Terminal Value thường chiếm 60-80% tổng EV

---

### Bài Tập 1: Time Value of Money

1. **PV** = 500 / (1.10)³ = 500 / 1.331 = **375.7 triệu VND**

2. **FV** = 200 × (1.12)⁵ = 200 × 1.762 = **352.4 triệu VND**

3. **PV tổng**:
   - PV(Năm 1) = 100 / 1.10 = 90.9 tỷ
   - PV(Năm 2) = 120 / (1.10)² = 99.2 tỷ
   - PV(Năm 3) = 140 / (1.10)³ = 105.2 tỷ
   - **Tổng = 295.3 tỷ VND**

---

### Bài Tập 2: DCF Vinatech

**Bước 1-2: FCF dự báo và chiết khấu (WACC 12%):**

| Năm | FCF (tỷ) | Discount Factor | PV (tỷ) |
|-----|----------|----------------|---------|
| 1 | 1,380 | 0.893 | 1,232 |
| 2 | 1,587 | 0.797 | 1,265 |
| 3 | 1,825 | 0.712 | 1,299 |
| 4 | 2,099 | 0.636 | 1,335 |
| 5 | 2,414 | 0.567 | 1,369 |
| **Tổng PV(FCF)** | | | **6,500** |

**Bước 3: Terminal Value:**
```
TV = 2,414 × (1.03) / (0.12 - 0.03) = 2,486 / 0.09 = 27,622 tỷ
PV(TV) = 27,622 / (1.12)⁵ = 27,622 / 1.762 = 15,676 tỷ
```

**Bước 4-5: Intrinsic Value:**
```
EV = 6,500 + 15,676 = 22,176 tỷ
Net Debt = 2,000 - 800 = 1,200 tỷ
Equity Value = 22,176 - 1,200 = 20,976 tỷ
Intrinsic Value/CP = 20,976 tỷ / 300 triệu = 69,920 VND ≈ 70,000 VND
```

**Bước 6: Margin of Safety:**
```
MoS = (70,000 - 28,000) / 70,000 = 60%
```

**Đánh giá**: Giá hiện tại 28,000 VND thấp hơn Intrinsic Value 60% trong mô hình giả định. MoS = 60% vượt ngưỡng Graham 30-50%, nhưng chưa đủ để kết luận mua. Cần kiểm tra tăng trưởng 15% có thực tế không, chất lượng quản trị, rủi ro ngành và lý do thị trường định giá thấp.

---

### Bài Tập 4: So Sánh Phương Pháp

1. **Cổ phiếu X (Ngân hàng)**: Dùng **P/B và P/E** — DCF khó áp dụng cho ngân hàng vì FCF không rõ ràng, tài sản tài chính là cốt lõi.

   **Cổ phiếu Y (Startup phần mềm)**: Dùng **P/S** — không có lợi nhuận, không dùng được P/E hay DCF (FCF âm).

2. **Giá trị ngụ ý Cổ phiếu X:**
   - Theo P/E: 5,000 × 12 = 60,000 VND/CP → Đắt hơn giá thị trường (52,000)
   - Theo P/B: 30,000 × 1.5 = 45,000 VND/CP → Rẻ hơn giá thị trường

3. **Market Cap ngụ ý Cổ phiếu Y:**
   - P/S comps: 500 tỷ × 8 = 4,000 tỷ → Bằng giá thị trường → Định giá hợp lý theo ngành

4. **Nhận xét**: Cổ phiếu X: trung tính (P/E đắt, P/B rẻ — cần xem xét thêm). Cổ phiếu Y: hợp lý theo P/S nhưng rủi ro cao vì đang lỗ, cần tăng trưởng duy trì để biện hộ.

---

### Case Study: Hai Analyst, Một Công Ty

1. **Lý do kết quả khác nhau 4 lần**: DCF cực kỳ nhạy cảm với: (a) tốc độ tăng trưởng FCF, (b) WACC, (c) Terminal Growth Rate. Mỗi giả định khác nhau một chút cộng dồn lại tạo ra sự chênh lệch khổng lồ.

2. **Giả định tạo ra sự khác biệt lớn nhất**: **WACC và Terminal Growth Rate** — vì Terminal Value chiếm 60-80% tổng EV. Sự chênh lệch WACC (10% vs 14%) và g (4% vs 2%) tạo ra mẫu số (WACC-g) khác hoàn toàn: 6% vs 12%.

3. **Nhà đầu tư nên làm gì?**
   - Tự đặt câu hỏi: giả định nào có cơ sở hơn?
   - Dùng kịch bản trung bình làm tham chiếu
   - **Chỉ xem xét mua nếu MoS đủ lớn ngay cả ở kịch bản bi quan**
   - Giá 40,000 VND ở đây: Bear case = 21,000 (lỗ 47%), Bull case = 85,000 (lãi 112%) → Rủi ro/phần thưởng không cân xứng về phía bi quan

4. **Ý nghĩa Margin of Safety**: Trong trường hợp này, MoS âm theo kịch bản thận trọng → chưa đạt tiêu chí an toàn ở giá 40,000. Nếu giá giảm về ~15,000 (MoS 30% so với Bear case), rủi ro được kiểm soát tốt hơn. Đây là bài học về việc Margin of Safety bảo vệ bạn ngay cả khi dự báo sai.
