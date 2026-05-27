# Ngày 41: Bài tập thực hành — Portfolio Management

## Phần 1: Trắc nghiệm (10 câu)

**Câu 1:** Theo nghiên cứu của Brinson (1991), khoảng bao nhiêu % hiệu suất dài hạn của danh mục được quyết định bởi Asset Allocation?

A) 30%
B) 60%
C) 90%
D) 100%

---

**Câu 2:** Nhà đầu tư A có danh mục gồm: VCB (25%), TCB (25%), BID (25%), MBB (25%). Điều gì sai với cách đa dạng hóa này?

A) Có quá nhiều cổ phiếu — nên giảm xuống còn 2
B) Tất cả đều là cổ phiếu ngân hàng — rủi ro ngành tập trung (False Diversification)
C) Tỷ trọng đều nhau là sai — cần market cap weight
D) Không có gì sai — đây là danh mục tốt

---

**Câu 3:** Cổ phiếu có Beta = 1.5. Nếu VN-Index giảm 10%, kỳ vọng cổ phiếu này thay đổi bao nhiêu?

A) Giảm khoảng 10%
B) Giảm khoảng 15%
C) Giảm khoảng 5%
D) Tăng khoảng 15%

---

**Câu 4:** Sharpe Ratio của danh mục A = 1.8, danh mục B = 0.9. Kết luận nào ĐÚNG?

A) Danh mục A tốt hơn vì có Sharpe Ratio cao hơn — hiệu quả điều chỉnh rủi ro tốt hơn
B) Danh mục B tốt hơn vì Sharpe Ratio thấp nghĩa là ít rủi ro hơn
C) Không thể so sánh vì không biết lợi nhuận tuyệt đối
D) Sharpe Ratio không có ý nghĩa trong thực tế

---

**Câu 5:** Danh mục của bạn đạt đỉnh 200 triệu VND, sau đó giảm xuống 120 triệu VND. Maximum Drawdown là bao nhiêu?

A) -40%
B) -80 triệu
C) -33%
D) -60%

---

**Câu 6:** Bạn bán 2,000 cổ phiếu VNM tại giá 70,000 VND/cổ. Thuế chuyển nhượng phải nộp là bao nhiêu?

A) Không phải nộp thuế vì đang lỗ
B) 140,000 VND (0.1% × 140,000,000 VND)
C) 7,000,000 VND (5% × 140,000,000 VND)
D) 700,000 VND (0.5% × 140,000,000 VND)

---

**Câu 7:** Chiến lược Rebalancing nào phù hợp nhất với nhà đầu tư bận rộn, không có thời gian theo dõi thị trường hàng ngày?

A) Threshold Rebalancing — rebalance khi lệch 5%
B) Calendar Rebalancing — rebalance vào đầu mỗi quý
C) Continuous Rebalancing — rebalance mỗi ngày giao dịch
D) Không cần rebalancing

---

**Câu 8:** Correlation giữa cổ phiếu ngân hàng (VCB) và vàng (GOLD ETF) thường là:

A) Gần +1 (tương quan dương mạnh)
B) Gần 0 hoặc âm nhẹ (ít tương quan hoặc ngược chiều)
C) Gần -1 (tương quan âm mạnh)
D) Luôn bằng đúng 0

---

**Câu 9:** Danh mục của bạn tăng 20% trong năm, trong khi VN-Index tăng 12%. Lãi suất phi rủi ro là 5%. Alpha (xấp xỉ) của danh mục là bao nhiêu?

A) +8%
B) +15%
C) +3%
D) +20%

---

**Câu 10:** Lý do nào giải thích tại sao giao dịch thường xuyên (high-frequency trading) thường kém hiệu quả hơn chiến lược Buy & Hold cho nhà đầu tư cá nhân?

A) Nhà đầu tư cá nhân không có đủ thông tin
B) Chi phí giao dịch (phí + thuế 0.1% mỗi lần bán) tích lũy theo thời gian ăn mòn lợi nhuận
C) Giao dịch thường xuyên vi phạm pháp luật
D) A và B đều đúng

---

## Phần 2: Bài tập thực hành

### Bài tập 1: Tính Portfolio Beta

Bạn có danh mục sau:

| Cổ phiếu | Giá trị (triệu VND) | Beta ước tính |
|----------|---------------------|---------------|
| VCB | 20 | 0.85 |
| FPT | 25 | 1.25 |
| VHM | 15 | 1.40 |
| VNM | 10 | 0.60 |
| FUEVFVND (ETF VN30) | 20 | 1.00 |
| Tiền mặt | 10 | 0.00 |
| **Tổng** | **100** | |

**Yêu cầu:**
1. Tính tỷ trọng (%) của từng tài sản
2. Tính Portfolio Beta tổng hợp
3. Nhận xét: Danh mục này mang tính tấn công (aggressive), trung tính, hay phòng thủ (defensive)?
4. Nếu muốn giảm Portfolio Beta xuống 0.90, bạn có thể điều chỉnh như thế nào?

---

### Bài tập 2: Tính Sharpe Ratio và so sánh

Hai nhà đầu tư A và B có kết quả sau trong 1 năm (lãi suất phi rủi ro Rf = 5%):

| | Nhà đầu tư A | Nhà đầu tư B |
|---|---|---|
| Lợi nhuận năm | 22% | 14% |
| Độ lệch chuẩn (σ) | 30% | 12% |

**Yêu cầu:**
1. Tính Sharpe Ratio của cả hai
2. Ai đầu tư hiệu quả hơn khi tính đến rủi ro?
3. Nếu bạn muốn đạt Sharpe Ratio = 1.5 với độ lệch chuẩn 15%, lợi nhuận mục tiêu cần là bao nhiêu?

---

### Bài tập 3: Phân tích Maximum Drawdown

Danh mục của bạn có giá trị theo các tháng như sau (triệu VND):

| Tháng | Giá trị |
|-------|---------|
| T1/2022 | 100 |
| T4/2022 | 145 |
| T7/2022 | 115 |
| T11/2022 | 88 |
| T3/2023 | 105 |
| T7/2023 | 130 |
| T12/2023 | 120 |
| T6/2024 | 155 |

**Yêu cầu:**
1. Xác định đỉnh (Peak) và đáy (Trough) để tính Maximum Drawdown
2. Tính MDD (%)
3. Tính thời gian phục hồi (Recovery Time) từ đáy về lại mức đỉnh cũ
4. Nếu bạn có ngưỡng chịu đựng tối đa MDD là -25%, danh mục này có vượt ngưỡng không? Bạn nên điều chỉnh gì?

---

### Bài tập 4: Lập kế hoạch Rebalancing

Danh mục mục tiêu ban đầu của bạn (100 triệu VND):
- VCB: 25% (25 triệu)
- FPT: 30% (30 triệu)
- VNM: 20% (20 triệu)
- Trái phiếu ETF (VNPF): 15% (15 triệu)
- Tiền mặt: 10% (10 triệu)

Sau 8 tháng, giá trị danh mục thay đổi:
- VCB: tăng lên 32 triệu (VCB tăng 28%)
- FPT: tăng lên 51 triệu (FPT tăng 70%!)
- VNM: giảm xuống 17 triệu (VNM giảm 15%)
- VNPF: giữ nguyên 15 triệu
- Tiền mặt: giảm xuống 7 triệu (đã dùng 3 triệu mua thêm VNM)
- **Tổng: 122 triệu VND**

**Yêu cầu:**
1. Tính tỷ trọng hiện tại của từng tài sản
2. Xác định tài sản nào cần bán bớt, tài sản nào cần mua thêm để về đúng tỷ trọng mục tiêu
3. Tính số tiền cần bán/mua cho mỗi tài sản
4. Tính chi phí thuế + phí giao dịch ước tính khi rebalance (giả sử phí 0.15% hai chiều + thuế 0.1% khi bán)

---

## Phần 3: Case Study

### Case Study: Danh mục của anh Hùng — Bài học từ thực tế

**Bối cảnh:** Anh Hùng, 38 tuổi, bắt đầu đầu tư chứng khoán từ năm 2020 với 300 triệu VND. Anh là kỹ sư IT, yêu thích cổ phiếu công nghệ và tài chính.

**Danh mục tháng 3/2022 (tổng 450 triệu — đã tăng 50%):**
- FPT: 120 triệu (27%)
- VNM: 80 triệu (18%)
- VHM: 90 triệu (20%)
- VIC: 85 triệu (19%)
- HPG: 75 triệu (17%)

**Vấn đề:** Từ tháng 4/2022, thị trường bắt đầu điều chỉnh mạnh. VN-Index giảm từ ~1,500 xuống ~870 điểm (tháng 11/2022). Danh mục anh Hùng giảm xuống còn 260 triệu — mất 190 triệu so với đỉnh.

**Phân tích vấn đề:**

1. **Concentration trong bất động sản:** VHM + VIC chiếm 39% danh mục. Khi thị trường BĐS đóng băng 2022-2023, hai cổ phiếu này giảm 50-60%.

2. **Không có tài sản phòng thủ:** Danh mục 100% cổ phiếu, không có trái phiếu, vàng, hay tiền mặt dự phòng. Portfolio Beta ước tính ~1.3 — biến động hơn thị trường 30%.

3. **Không Rebalancing:** Khi FPT và BĐS tăng mạnh năm 2021, anh Hùng không bán bớt để chốt lời và tái phân bổ sang tài sản phòng thủ hơn.

4. **Bán trong hoảng loạn:** Tháng 11/2022, anh Hùng bán toàn bộ VHM và VIC tại vùng đáy vì sợ tiếp tục giảm. Thực tế hai cổ phiếu này phục hồi 40-50% từ đáy trong năm 2023-2024.

**Câu hỏi thảo luận:**

1. Nếu anh Hùng áp dụng nguyên tắc đa dạng hóa đúng cách, danh mục nên được cấu trúc như thế nào? Đề xuất cụ thể tỷ trọng và thêm các tài sản gì.

2. Tính Portfolio Beta của danh mục anh Hùng (giả sử: FPT Beta=1.2, VNM Beta=0.65, VHM Beta=1.45, VIC Beta=1.40, HPG Beta=1.30). Nhận xét về mức độ rủi ro.

3. Anh Hùng nên đặt ngưỡng Rebalancing như thế nào để tự động giảm rủi ro khi thị trường tăng mạnh?

4. Quyết định bán VHM, VIC ở đáy là do tâm lý hay do nguyên tắc đầu tư? Làm thế nào để tránh lỗi này?

5. Nếu anh Hùng không bán và tiếp tục nắm giữ, ước tính danh mục sẽ về đâu vào cuối 2024?

---

## Đáp án

### Trắc nghiệm
1. **C** — 90% hiệu suất dài hạn đến từ Asset Allocation (Brinson 1991)
2. **B** — False Diversification: 4 cổ phiếu nhưng đều là ngân hàng, rủi ro ngành vẫn tập trung
3. **B** — Giảm khoảng 15% (Beta 1.5 × -10% thị trường = -15%)
4. **A** — Sharpe Ratio cao hơn nghĩa là hiệu quả điều chỉnh rủi ro tốt hơn
5. **A** — MDD = (120-200)/200 = -40%
6. **B** — 0.1% × (2,000 × 70,000) = 0.1% × 140,000,000 = 140,000 VND
7. **B** — Calendar Rebalancing phù hợp nhất cho người bận rộn
8. **B** — Vàng và cổ phiếu ngân hàng thường có correlation thấp hoặc âm nhẹ
9. **A** — Alpha ≈ Lợi nhuận danh mục - Lợi nhuận benchmark = 20% - 12% = +8%
10. **D** — Cả A và B đều đúng

### Bài tập 1 — Portfolio Beta
Tỷ trọng: VCB 20%, FPT 25%, VHM 15%, VNM 10%, FUEVFVND 20%, Tiền mặt 10%

Portfolio Beta = (0.20 × 0.85) + (0.25 × 1.25) + (0.15 × 1.40) + (0.10 × 0.60) + (0.20 × 1.00) + (0.10 × 0.00)
= 0.170 + 0.313 + 0.210 + 0.060 + 0.200 + 0.000
= **0.953**

Nhận xét: Gần Beta = 1 → Danh mục trung tính, biến động tương đương thị trường.

Để giảm Beta xuống 0.90: Tăng tỷ trọng VNM và tiền mặt (Beta thấp), giảm tỷ trọng VHM và FPT (Beta cao).

### Bài tập 2 — Sharpe Ratio
- Sharpe A = (22% - 5%) / 30% = 17% / 30% = **0.567**
- Sharpe B = (14% - 5%) / 12% = 9% / 12% = **0.750**

Nhà đầu tư B hiệu quả hơn khi tính đến rủi ro dù lợi nhuận tuyệt đối thấp hơn.

Lợi nhuận mục tiêu nếu Sharpe = 1.5, σ = 15%:
1.5 = (Rp - 5%) / 15% → Rp = 1.5 × 15% + 5% = **27.5%**

### Bài tập 3 — Maximum Drawdown
Peak = 145 triệu (T4/2022)
Trough = 88 triệu (T11/2022)
MDD = (88 - 145) / 145 = **-39.3%**

Recovery Time: Từ đáy T11/2022, phải đợi đến T6/2024 (khi đạt 155 > 145) → khoảng **19 tháng** để phục hồi vượt đỉnh cũ.

MDD -39.3% vượt ngưỡng chịu đựng -25% → Cần giảm Beta danh mục, thêm tài sản phòng thủ (trái phiếu, vàng), áp dụng Rebalancing tự động.

### Bài tập 4 — Rebalancing
Tỷ trọng hiện tại (122 triệu):
- VCB: 32/122 = 26.2%
- FPT: 51/122 = 41.8% ← Vượt 30% mục tiêu!
- VNM: 17/122 = 13.9% ← Dưới 20% mục tiêu
- VNPF: 15/122 = 12.3% ← Dưới 15% mục tiêu
- Tiền mặt: 7/122 = 5.7% ← Dưới 10% mục tiêu

Cần về mục tiêu (122 triệu × tỷ trọng mục tiêu):
- VCB mục tiêu: 30.5 triệu → Mua thêm 1.5 triệu (cân bằng)
- FPT mục tiêu: 36.6 triệu → **Bán bớt 14.4 triệu**
- VNM mục tiêu: 24.4 triệu → Mua thêm 7.4 triệu
- VNPF mục tiêu: 18.3 triệu → Mua thêm 3.3 triệu
- Tiền mặt mục tiêu: 12.2 triệu → Sẽ có từ tiền bán FPT

Chi phí rebalancing (khi bán 14.4 triệu FPT):
- Thuế 0.1%: 14,400 VND (14.4 triệu × 0.1%)
- Phí bán 0.15%: 21,600 VND
- Phí mua (~25.2 triệu): 37,800 VND
- **Tổng chi phí ≈ 73,800 VND (~74,000 VND)**

### Case Study — Gợi ý đáp án

**Câu 2 — Portfolio Beta anh Hùng:**
= (0.27×1.2) + (0.18×0.65) + (0.20×1.45) + (0.19×1.40) + (0.17×1.30)
= 0.324 + 0.117 + 0.290 + 0.266 + 0.221 = **1.218**

Mức Beta 1.22 là khá cao — danh mục biến động mạnh hơn thị trường 22%. Khi VN-Index giảm 42% (2022), danh mục có thể giảm ~51% — phù hợp với thực tế giảm từ 450 → 260 triệu (giảm 42%).

**Câu 4:** Quyết định bán ở đáy là do tâm lý (Loss Aversion — sợ lỗ thêm), không có nguyên tắc Stop-loss cụ thể. Cách tránh: Đặt stop-loss rõ ràng TRƯỚC khi mua, không thay đổi khi cảm xúc hoảng loạn. Tốt hơn là rebalance dần (bán từng phần khi tăng) thay vì bán toàn bộ khi giảm.
