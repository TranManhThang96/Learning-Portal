# Bài Tập — Ngày 34: Margin Trading, Short Selling & Quyền Cổ Đông

## Phần 1: Câu Hỏi Ôn Tập (Quiz)

**1. Bạn có 50 triệu VND và vay thêm 50 triệu để mua cổ phiếu (margin 1:2). Cổ phiếu giảm 30%. Tỷ lệ thua lỗ thực tế trên vốn của bạn là bao nhiêu?**
   - A. 15%
   - B. 30%
   - C. 60%
   - D. 90%

**2. Margin Call xảy ra khi nào?**
   - A. Khi bạn muốn rút tiền khỏi tài khoản
   - B. Khi giá trị tài khoản giảm xuống dưới ngưỡng duy trì margin
   - C. Khi cổ phiếu tăng quá mạnh
   - D. Khi bạn đặt lệnh mua quá lớn

**3. Trong Short Selling, nhà đầu tư kiếm lời khi:**
   - A. Cổ phiếu tăng giá
   - B. Cổ phiếu giữ nguyên giá
   - C. Cổ phiếu giảm giá
   - D. Công ty trả cổ tức

**4. Ex-Dividend Date (ngày giao dịch không hưởng quyền) có ý nghĩa gì?**
   - A. Ngày công ty công bố sẽ trả cổ tức
   - B. Ngày tiền cổ tức được chuyển vào tài khoản
   - C. Ngày mà nếu mua từ đây trở đi sẽ không được nhận cổ tức kỳ này
   - D. Ngày cuối cùng để đăng ký nhận cổ tức

**5. Công ty X thực hiện Stock Split 3:1. Bạn đang nắm 100 cổ phiếu giá 150,000 VND/cp. Sau split, bạn sẽ có:**
   - A. 33 cổ phiếu, giá 450,000 VND/cp
   - B. 300 cổ phiếu, giá 50,000 VND/cp
   - C. 100 cổ phiếu, giá 50,000 VND/cp
   - D. 300 cổ phiếu, giá 150,000 VND/cp

**6. Rủi ro đặc biệt của Short Selling mà không tồn tại khi mua cổ phiếu thông thường là:**
   - A. Thua lỗ tối đa 100%
   - B. Phải trả thuế thu nhập
   - C. Thua lỗ không có giới hạn (theoretically unlimited)
   - D. Không được nhận cổ tức

**7. Buyback (mua lại cổ phiếu) thường có tác động gì đến EPS?**
   - A. EPS giảm vì công ty dùng hết tiền mặt
   - B. EPS tăng vì số lượng cổ phiếu lưu hành giảm
   - C. EPS không thay đổi
   - D. EPS giảm vì lợi nhuận bị pha loãng

**8. Dividend Yield của cổ phiếu A là bao nhiêu nếu: cổ tức năm nay = 2,000 VND/cp, giá hiện tại = 40,000 VND/cp?**
   - A. 2%
   - B. 5%
   - C. 8%
   - D. 20%

---

## Phần 2: Bài Tập Thực Hành

### Bài Tập 1: Tính Toán Margin

**Tình huống:**
Bạn có tài khoản 200 triệu VND tại công ty chứng khoán. Bạn sử dụng margin 1:1.5, tức là vay thêm 100 triệu để mua tổng cộng 300 triệu đồng cổ phiếu VCB tại giá 85,000 VND/cổ phiếu.

Tỷ lệ duy trì margin (maintenance margin) của công ty CK là 40%.

**Yêu cầu:**
1. Tính số cổ phiếu VCB bạn mua được
2. Tính ngưỡng Margin Call (giá trị danh mục tối thiểu)
3. Tính giá cổ phiếu VCB mà tại đó bạn bị Margin Call
4. Nếu VCB giảm về 65,000 VND/cp, tính lời/lỗ thực tế trên vốn của bạn (200 triệu), chưa tính lãi vay

---

### Bài Tập 2: Phân Tích Cổ Tức

**Tình huống:**
Cổ phiếu REE (Cơ điện lạnh) có các thông tin sau:
- Giá hiện tại: 60,000 VND/cp
- Cổ tức tiền mặt năm ngoái: 2,500 VND/cp (2 lần: 1,000 + 1,500)
- Ngày Ex-Dividend lần này: 15/03/2025
- Ngày thanh toán: 05/04/2025
- Bạn mua 500 cổ phiếu vào ngày 12/03/2025 (3 ngày trước Ex-Dividend)

**Yêu cầu:**
1. Bạn có được nhận cổ tức đợt này không? Giải thích tại sao.
2. Nếu cổ tức đợt này là 1,500 VND/cp, bạn nhận được bao nhiêu tiền?
3. Tính Dividend Yield dựa trên giá mua của bạn
4. Giả sử ngày mai (12/03/2025) bạn bán đi, bạn vẫn được nhận cổ tức không?

---

### Bài Tập 3: Short Selling — Tính Lời/Lỗ

**Tình huống:**
Bạn phân tích và nhận định cổ phiếu HVN (Vietnam Airlines) đang được định giá quá cao do thị trường lạc quan thái quá về du lịch hục phồng. Bạn quyết định bán khống:

- Mượn và bán 1,000 cổ phiếu HVN ở giá 28,000 VND/cp
- Phí mượn cổ phiếu: 3%/năm
- Thời gian nắm giữ vị thế short: 45 ngày
- Tình huống A: Giá giảm xuống 20,000 VND/cp — bạn mua lại và đóng vị thế
- Tình huống B: Giá tăng lên 38,000 VND/cp — bạn buộc phải mua lại để cắt lỗ

**Yêu cầu:**
1. Tính lợi nhuận/thua lỗ trong Tình huống A (đã trừ phí mượn CP)
2. Tính lỗ trong Tình huống B (đã trừ phí mượn CP)
3. Nếu bạn đặt Stop-loss ở 33,600 VND/cp (thua lỗ 20%), kết quả ra sao?

---

## Phần 3: Case Study

### Câu Chuyện GameStop (GME) 2021 — Bài Học Short Squeeze

**Bối cảnh:**
Cuối năm 2020, chuỗi cửa hàng game GameStop (Mỹ) đang thua lỗ do thị trường game chuyển sang digital. Nhiều quỹ hedge fund lớn đặt cược vào sự sụp đổ của công ty bằng cách bán khống GME với tổng số lượng CP bán khống lên đến **140% số CP lưu hành** (điều này có thể xảy ra do cùng một CP được mượn nhiều lần).

**Diễn biến:**
- Tháng 1/2021: Cộng đồng Reddit (r/WallStreetBets) phát hiện tình trạng bán khống quá mức
- Họ kêu gọi nhau mua và giữ GME (HODL) để đẩy giá lên
- Giá GME: $20 → $347 trong vài tuần
- Các quỹ hedge fund như Melvin Capital buộc phải mua lại cổ phiếu ở giá cao để đóng vị thế short
- Kết quả: Melvin Capital lỗ ~$6.8 tỷ USD chỉ trong tháng 1/2021

**Câu hỏi thảo luận:**
1. Tại sao tỷ lệ short interest >100% có thể xảy ra?
2. Cơ chế nào đã tạo ra vòng xoáy "Short Squeeze"?
3. Bài học rút ra cho nhà đầu tư bán khống là gì?
4. Nếu bạn đã short GME ở $20 với 1,000 cổ phiếu và không có Stop-loss, thua lỗ tối đa lý thuyết là bao nhiêu khi giá lên $480?

---

## Đáp Án & Giải Thích

### Quiz
1. **C — 60%**
   - Giải thích: Bạn mua 100 triệu CP. CP giảm 30% → giá trị còn 70 triệu. Trừ nợ 50 triệu → vốn còn 20 triệu. Lỗ 30 triệu / vốn 50 triệu = **lỗ 60%**.

2. **B** — Margin Call xảy ra khi giá trị tài khoản xuống dưới ngưỡng duy trì.

3. **C** — Short Selling kiếm lời khi giá giảm (bán cao, mua lại thấp hơn).

4. **C** — Ex-Dividend Date là ngày mà nếu mua từ ngày đó trở đi sẽ không được nhận cổ tức kỳ này.

5. **B — 300 cổ phiếu, giá 50,000 VND/cp**
   - Split 3:1: số CP ×3, giá ÷3. Tổng giá trị không đổi: 300 × 50,000 = 15,000,000 = 100 × 150,000.

6. **C** — Thua lỗ không có giới hạn vì giá CP có thể tăng lên bất kỳ mức nào.

7. **B** — Buyback giảm số CP lưu hành, cùng mức lợi nhuận ÷ ít CP hơn = EPS tăng.

8. **B — 5%**
   - Dividend Yield = 2,000 / 40,000 × 100% = 5%.

---

### Bài Tập 1: Giải

1. **Số CP mua được** = 300,000,000 / 85,000 = **3,529 CP** (làm tròn xuống)

2. **Ngưỡng Margin Call**:
   - Ngưỡng = Nợ / (1 - Tỷ lệ duy trì) = 100,000,000 / (1 - 0.4) = **166,666,667 VND (~166.7 triệu)**

3. **Giá VCB khi Margin Call**:
   - Giá trị còn 166.7 triệu với 3,529 CP → Giá = 166,700,000 / 3,529 = **~47,239 VND/cp**
   - Tức là VCB giảm từ 85,000 xuống ~47,200 (giảm ~44.5%) thì bị Margin Call

4. **Lời/lỗ khi VCB = 65,000:**
   - Giá trị CP = 3,529 × 65,000 = 229,385,000
   - Trừ nợ 100,000,000 → Vốn còn = 129,385,000
   - Lỗ = 200,000,000 - 129,385,000 = **70,615,000 VND (lỗ ~35.3%)**
   - Không dùng margin thì chỉ lỗ 23.5% (65,000/85,000 - 1)

---

### Bài Tập 2: Giải

1. **Có được nhận cổ tức**: Có. Vì mua ngày 12/03, Ex-Date là 15/03 → mua trước Ex-Date nên được nhận.
   - Lưu ý T+2: Để được vào Record Date thực tế cần mua trước Ex-Date 2 phiên, điều này đã thỏa mãn.

2. **Tiền cổ tức** = 500 × 1,500 = **750,000 VND**

3. **Dividend Yield** = (1,500 / 60,000) × 100% = **2.5%** cho đợt này
   - Nếu tính cả năm (2,500 VND): 2,500/60,000 = **4.17%/năm**

4. **Nếu bán ngày 13/03** (sau khi mua 12/03): Vẫn được nhận cổ tức vì tại ngày 12/03, bạn đã được ghi nhận là cổ đông vào Record Date (do T+2).

---

### Bài Tập 3: Giải

**Phí mượn CP** = (28,000 × 1,000) × 3% / 365 × 45 = 28,000,000 × 0.003699 = **~103,575 VND**

**Tình huống A (giá xuống 20,000):**
- Thu về ban đầu: 28,000 × 1,000 = 28,000,000
- Mua lại: 20,000 × 1,000 = 20,000,000
- Phí mượn: 103,575
- **Lợi nhuận = 28,000,000 - 20,000,000 - 103,575 = 7,896,425 VND (~28.2%)**

**Tình huống B (giá lên 38,000):**
- Thu về ban đầu: 28,000,000
- Mua lại: 38,000 × 1,000 = 38,000,000
- Phí mượn: 103,575
- **Lỗ = 28,000,000 - 38,000,000 - 103,575 = -10,103,575 VND (~36.1%)**

**Stop-loss ở 33,600 VND (tăng 20%)**:
- Mua lại: 33,600 × 1,000 = 33,600,000
- Lỗ = 28,000,000 - 33,600,000 - 103,575 = **-5,703,575 VND (~20.4%)**
- Stop-loss giúp giới hạn lỗ thay vì lỗ 36% như Tình huống B

---

### Case Study GME: Gợi Ý Trả Lời

1. **Tỷ lệ short >100%** xảy ra khi: A mượn CP của B bán cho C. C cho D mượn và D bán nữa. Cùng 1 CP được mượn-bán nhiều lần.

2. **Short Squeeze**: Giá tăng → người short phải mua lại để cắt lỗ → mua thêm làm giá tăng tiếp → người short khác buộc mua → vòng xoáy tăng.

3. **Bài học**: Không bao giờ short quá mức, luôn có Stop-loss, tránh những cổ phiếu đang bị cộng đồng chú ý.

4. **Lỗ tối đa lý thuyết** (nếu không Stop-loss): (480 - 20) × 1,000 = **$460,000** — mất 23 lần số tiền ban đầu bỏ ra.
