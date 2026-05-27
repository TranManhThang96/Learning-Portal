# Bài Tập — Ngày 26: Candlestick Chart Cơ Bản

## Phần 1: Câu Hỏi Ôn Tập (Quiz)

**1. Một cây nến Nhật chứa bao nhiêu thông tin giá?**
   - A. 1 (chỉ giá đóng cửa)
   - B. 2 (giá mở và đóng)
   - C. 3 (mở, cao, thấp)
   - D. 4 (Open, High, Low, Close)

**2. Nến xanh (bullish candle) có nghĩa là:**
   - A. Giá mở cửa cao hơn giá đóng cửa
   - B. Giá đóng cửa cao hơn giá mở cửa
   - C. Giá tăng so với ngày hôm trước
   - D. Khối lượng giao dịch lớn

**3. Bóng dưới dài của một cây nến cho thấy điều gì?**
   - A. Bears đã đẩy giá xuống thấp và giữ ở đó
   - B. Bulls đã vào mua và đẩy giá lên từ vùng thấp
   - C. Giá mở cửa rất thấp
   - D. Không có ý nghĩa gì

**4. Nến Hammer xuất hiện ở đâu để có tín hiệu bullish reversal?**
   - A. Cuối uptrend
   - B. Giữa sideway
   - C. Cuối downtrend
   - D. Bất kỳ vị trí nào

**5. Đâu là sự khác biệt CHÍNH giữa Hammer và Hanging Man?**
   - A. Màu sắc của nến
   - B. Độ dài của bóng dưới
   - C. Vị trí xuất hiện trong xu hướng
   - D. Kích thước thân nến

**6. Nến Marubozu đặc trưng bởi:**
   - A. Không có thân nến
   - B. Hai bóng rất dài
   - C. Thân dài và không có bóng (hoặc bóng rất nhỏ)
   - D. Thân nhỏ ở giữa nến

**7. Shooting Star là tín hiệu gì và xuất hiện ở đâu?**
   - A. Bullish reversal, cuối downtrend
   - B. Bearish reversal, cuối uptrend
   - C. Continuation (tiếp diễn), giữa uptrend
   - D. Không có tín hiệu rõ ràng

**8. Doji cho thấy điều gì về tâm lý thị trường?**
   - A. Bulls đang thắng tuyệt đối
   - B. Bears đang thắng tuyệt đối
   - C. Thị trường đang do dự, không ai kiểm soát
   - D. Sắp có tin tức lớn

**9. Khi nào một mô hình nến đảo chiều đáng tin cậy hơn?**
   - A. Khi xuất hiện trên biểu đồ 1 phút
   - B. Khi xuất hiện tại vùng hỗ trợ/kháng cự quan trọng + volume lớn
   - C. Khi nến có màu xanh tươi
   - D. Khi thị trường đang sideway

**10. Timeframe nào có độ tin cậy cao nhất khi phân tích nến?**
    - A. 1 phút
    - B. 5 phút
    - C. 1 ngày hoặc 1 tuần
    - D. Tất cả đều như nhau

---

## Phần 2: Bài Tập Nhận Diện Nến

### Bài Tập 1: Xác định loại nến

Dựa vào dữ liệu OHLC sau, hãy:
1. Xác định nến tăng hay giảm
2. Vẽ sơ đồ nến bằng text/ASCII
3. Nhận diện mô hình nến (nếu có)

**Nến A:**
- Open: 50,000
- High: 51,500
- Low: 49,800
- Close: 51,200

**Nến B:**
- Open: 80,000
- High: 80,200
- Low: 74,000
- Close: 79,500

**Nến C:**
- Open: 100,000
- High: 106,000
- Low: 99,800
- Close: 100,200

**Nến D:**
- Open: 45,000
- High: 45,100
- Low: 40,000
- Close: 44,800

---

### Bài Tập 2: Phân tích chuỗi nến

Quan sát chuỗi nến sau của một cổ phiếu giả định (giá đơn vị: 1,000 VND):

```
Ngày 1: O=60, H=63, L=59, C=61  (Nến xanh nhỏ)
Ngày 2: O=61, H=64, L=60, C=63  (Nến xanh nhỏ)
Ngày 3: O=63, H=70, L=62, C=63  (Nến có bóng trên rất dài)
```

**Câu hỏi:**
1. Xu hướng trước ngày 3 là gì?
2. Nến ngày 3 là loại nến gì? Mô tả đặc điểm.
3. Tín hiệu từ nến ngày 3 là gì?
4. Bạn sẽ làm gì tiếp theo? (Chờ xác nhận / Mua ngay / Bán ngay)

---

### Bài Tập 3: Tình Huống Thực Tế

Bạn đang theo dõi cổ phiếu HPG (Hòa Phát Group). Trong 5 ngày gần nhất:

- Cổ phiếu đã giảm từ 28,000 xuống 22,000 VND (downtrend rõ ràng)
- Ngày hôm nay xuất hiện nến với: Open=22,000, High=22,300, Low=19,500, Close=21,800
- Khối lượng giao dịch hôm nay gấp 2.5 lần trung bình 20 ngày

**Câu hỏi:**
1. Xác định loại nến hôm nay (tính toán các thành phần).
2. Đây là tín hiệu gì?
3. Để vào lệnh MUA, bạn cần thêm điều kiện gì?
4. Nếu quyết định mua, bạn đặt Stop-loss ở đâu? (Gợi ý: dưới bóng dưới của nến)

---

## Phần 3: Case Study

### Câu chuyện "Bắt đáy VN-Index tháng 3/2020"

Trong đợt COVID crash tháng 3/2020:
- VN-Index giảm từ 950 điểm (tháng 1) xuống dưới 660 điểm (tháng 3)
- Ngày 24/3/2020: Xuất hiện một nến với bóng dưới rất dài, thân nến nhỏ ở phần trên
- Volume ngày đó là một trong những phiên khối lượng cao nhất lịch sử thị trường VN

**Phân tích:**
1. Theo bạn, đây là mô hình nến gì?
2. Tại sao đây có thể là tín hiệu đảo chiều?
3. Nếu bạn là nhà đầu tư tháng 3/2020, bạn cần thêm thông tin gì để quyết định mua?
4. Nhìn lại, VN-Index đã phục hồi về 1,500 điểm vào năm 2021. Bài học rút ra là gì?

---

## Đáp Án & Giải Thích

### Quiz
1. **D** — Một nến chứa 4 thông tin: Open, High, Low, Close
2. **B** — Nến xanh: Close > Open (giá đóng cao hơn giá mở)
3. **B** — Bóng dưới dài = Bulls đã đẩy giá lên từ vùng thấp
4. **C** — Hammer chỉ có ý nghĩa bullish reversal khi ở cuối downtrend
5. **C** — Hammer và Hanging Man trông giống nhau nhưng vị trí quyết định tín hiệu
6. **C** — Marubozu có thân dài, không có hoặc gần như không có bóng
7. **B** — Shooting Star = bearish reversal, xuất hiện cuối uptrend
8. **C** — Doji = cân bằng bulls/bears, thị trường do dự
9. **B** — Tín hiệu mạnh nhất khi kết hợp vị trí + volume
10. **C** — Timeframe lớn hơn = ít nhiễu hơn = tin cậy hơn

### Bài Tập 1: Nhận Diện Nến

**Nến A:** Close (51,200) > Open (50,000) → **Nến xanh (tăng)**
- Body = 1,200, Upper shadow = 300, Lower shadow = 200
- Thân chiếm tỷ lệ lớn → Nến xanh bình thường, bulls kiểm soát tốt

**Nến B:** Close (79,500) > Open (80,000)? Không! Close < Open → **Nến đỏ (giảm)**
- Open = 80,000, Close = 79,500 → Thân nhỏ (500)
- Lower shadow = 79,500 - 74,000 = 5,500 (rất dài!)
- Upper shadow = 80,200 - 80,000 = 200 (gần không có)
- **→ Đây là nến Hammer đỏ** (bóng dưới dài gấp 11 lần thân)

**Nến C:** Close (100,200) ≈ Open (100,000) → **Nến Doji**
- Body = 200 (rất nhỏ)
- Upper shadow = 106,000 - 100,200 = 5,800 (rất dài!)
- Lower shadow = 100,000 - 99,800 = 200 (rất nhỏ)
- **→ Đây là Gravestone Doji** (bóng trên dài, gần không có bóng dưới)

**Nến D:** Close (44,800) > Open (45,000)? Không! Close < Open → **Nến đỏ**
- Body = 200 (rất nhỏ)
- Lower shadow = 44,800 - 40,000 = 4,800 (rất dài, gấp 24 lần thân!)
- **→ Đây là Hammer đỏ — tín hiệu bullish (cần xác nhận)**

### Bài Tập 2: Phân Tích Chuỗi Nến

1. **Xu hướng:** Uptrend nhẹ (giá tăng từ 60 lên 63)
2. **Nến ngày 3:** Open=63, High=70, Low=62, Close=63
   - Body = 0 (Close = Open) → Doji!
   - Upper shadow = 70 - 63 = 7 (rất dài)
   - Lower shadow = 63 - 62 = 1 (gần không có)
   - **→ Gravestone Doji** — tín hiệu bearish reversal tiềm năng
3. **Tín hiệu:** Bears đẩy giá từ 70 xuống 63, cho thấy kháng cự mạnh ở vùng 70
4. **Hành động:** **Chờ xác nhận** — nếu ngày 4 là nến đỏ và đóng cửa dưới 62, xác nhận đảo chiều

### Bài Tập 3: HPG

1. **Phân tích nến:**
   - Body = Open (22,000) - Close (21,800) = 200 → Thân nhỏ (nến đỏ nhẹ)
   - Lower shadow = Close (21,800) - Low (19,500) = 2,300
   - Upper shadow = High (22,300) - Open (22,000) = 300
   - Bóng dưới gấp 11.5 lần thân → **Hammer đỏ!**

2. **Tín hiệu:** Bullish reversal tiềm năng sau downtrend. Volume 2.5x trung bình = xác nhận có lực mua lớn.

3. **Điều kiện vào lệnh:** Đợi nến xanh hôm sau đóng cửa cao hơn đỉnh thân nến hôm nay (> 22,000 VND)

4. **Stop-loss:** Dưới bóng dưới → dưới 19,500 VND (ví dụ: 19,200 VND)
