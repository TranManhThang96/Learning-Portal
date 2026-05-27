# Bài tập — Ngày 53: Blockchain & Bitcoin Cơ bản

## Phần 1: Câu hỏi ôn tập (Quiz)

1. Tổng cung tối đa của Bitcoin là bao nhiêu?
   - A. 1 triệu BTC
   - B. 21 triệu BTC
   - C. 100 triệu BTC
   - D. Không giới hạn

2. Điều gì xảy ra nếu ai đó cố gắng sửa dữ liệu trong một block của blockchain?
   - A. Blockchain tự động phục hồi sau vài phút
   - B. Hash của block đó thay đổi → Tất cả block tiếp theo bị vô hiệu hóa → Mạng lưới từ chối
   - C. Chỉ admins mới có thể phát hiện
   - D. Không ảnh hưởng gì vì các node khác giữ bản sao

3. Bitcoin được tạo ra để giải quyết vấn đề gì?
   - A. Giao dịch nhanh hơn thẻ tín dụng
   - B. Đầu tư sinh lời cao hơn vàng
   - C. Thanh toán điện tử peer-to-peer không cần bên thứ ba tin cậy
   - D. Thay thế hoàn toàn hệ thống ngân hàng quốc tế

4. Proof of Work yêu cầu Miner làm gì?
   - A. Chứng minh họ sở hữu nhiều Bitcoin nhất
   - B. Giải bài toán toán học khó (tìm Hash hợp lệ) bằng sức mạnh tính toán
   - C. Vote cho giao dịch hợp lệ
   - D. Stake một lượng Bitcoin nhất định

5. Sự kiện "Ethereum Merge" (2022) là:
   - A. Ethereum sáp nhập với Bitcoin
   - B. Ethereum chuyển từ Proof of Work sang Proof of Stake
   - C. Ethereum tăng block size gấp đôi
   - D. Ethereum ra mắt sản phẩm mới "Merge Token"

6. "Not your keys, not your coins" có nghĩa là:
   - A. Bạn cần nhiều Private Keys để mua nhiều coin
   - B. Nếu bạn không giữ Private Key, bạn không thực sự kiểm soát coin
   - C. Keys trong ví điện tử thì an toàn hơn trên sàn
   - D. Câu này chỉ áp dụng với Bitcoin, không phải altcoin

7. Bitcoin Halving xảy ra khi nào?
   - A. Mỗi năm một lần
   - B. Mỗi khi giá Bitcoin tăng gấp đôi
   - C. Mỗi 210,000 blocks (khoảng 4 năm)
   - D. Do cộng đồng biểu quyết quyết định

8. Tính chất nào KHÔNG phải của Blockchain?
   - A. Distributed Ledger (Sổ cái phân tán)
   - B. Centralized Control (Kiểm soát tập trung)
   - C. Immutability (Tính bất biến)
   - D. Decentralization (Phi tập trung)

9. Lợi thế lớn nhất của Proof of Stake so với Proof of Work là:
   - A. Bảo mật tuyệt đối hơn
   - B. Hoàn toàn phi tập trung hơn
   - C. Tiêu thụ năng lượng ít hơn rất nhiều
   - D. Không thể bị tấn công 51%

10. Satoshi Nakamoto là ai?
    - A. CEO của Bitcoin Foundation
    - B. Một nhà toán học người Nhật đã qua đời
    - C. Tên bí danh của người/nhóm tạo ra Bitcoin, danh tính vẫn là bí ẩn
    - D. Craig Wright — một kỹ sư người Úc

---

## Phần 2: Bài tập thực hành

### Bài tập 1: Khám phá Blockchain Explorer

Truy cập **mempool.space** (hoặc blockchain.com/explorer) và:

1. Tìm Bitcoin Genesis Block (Block #0):
   - Block Hash là gì?
   - Được tạo vào ngày nào?
   - Chứa bao nhiêu giao dịch?
   - Coinbase message (thông điệp ẩn) của Satoshi là gì?

2. Tìm một transaction gần đây trên trang chủ:
   - Transaction ID (TxID) là gì?
   - Giao dịch từ bao nhiêu địa chỉ?
   - Phí giao dịch (Fee) là bao nhiêu?
   - Đã có bao nhiêu Confirmations?

3. Quan sát Bitcoin mempool:
   - Có bao nhiêu giao dịch đang chờ xác nhận (Unconfirmed)?
   - Fee hiện tại để giao dịch được xác nhận trong 1 block tiếp theo là bao nhiêu sat/vByte?

---

### Bài tập 2: Tính toán Mining Reward

Dựa vào thông tin đã học:

1. Năm 2024, Block Reward là 3.125 BTC/block. Nếu giá BTC = $60,000:
   - Giá trị Block Reward mỗi block = ?
   - Mỗi ngày Bitcoin network tạo ra bao nhiêu block? (biết 10 phút/block, 1440 phút/ngày)
   - Tổng BTC mới được phát hành mỗi ngày = ?
   - Tổng giá trị USD mỗi ngày = ?

2. Sau Halving #5 (~2028), Block Reward sẽ là bao nhiêu BTC?

3. Bitcoin cuối cùng (block thứ 21 triệu) dự kiến được đào vào năm nào?

---

### Bài tập 3: So sánh Bitcoin và Vàng

Điền vào bảng so sánh sau:

| Tiêu chí | Vàng | Bitcoin | Ưu thế |
|----------|------|---------|--------|
| Nguồn cung | Hữu hạn (~197,000 tấn đã khai thác) | 21 triệu BTC tối đa | |
| Có thể chia nhỏ? | Gram, milligram | Đến 1 Satoshi (0.00000001 BTC) | |
| Vận chuyển | | | |
| Xác minh tính thật | | | |
| Kiểm duyệt bởi chính phủ | | | |
| Lịch sử làm tiền | 5,000+ năm | 15+ năm | |
| Tính năng lập trình | | | |
| Volatility (biến động giá) | Thấp | Rất cao | |

**Kết luận của bạn:** Trong danh mục đầu tư cá nhân, bạn sẽ phân bổ Bitcoin và Vàng theo tỷ lệ nào? Tại sao?

---

### Bài tập 4: Nghiên cứu Bitcoin Whitepaper

Đọc Abstract (tóm tắt) của Bitcoin Whitepaper (8 trang):
*"Bitcoin: A Peer-to-Peer Electronic Cash System"* — Satoshi Nakamoto (2008)

Tìm tại: nakamotoinstitute.org/bitcoin/

**Sau khi đọc, trả lời:**
1. Satoshi định nghĩa Bitcoin là gì trong câu đầu tiên?
2. Vấn đề gì với hệ thống thanh toán điện tử hiện tại mà Satoshi muốn giải quyết?
3. Giải pháp Satoshi đề xuất là gì?
4. Tại sao Paper này được coi là một trong những tài liệu quan trọng nhất thế kỷ 21?

---

## Phần 3: Case Study

### Người dùng và Blockchain — 3 Câu chuyện Thực tế

**Câu chuyện 1: Anh Hùng ở Venezuela**

Venezuela đang trải qua siêu lạm phát — đồng Bolivar mất giá 1,000,000% trong một thập kỷ. Anh Hùng, một bác sĩ ở Caracas, bắt đầu chuyển 10-20% lương sang Bitcoin mỗi tháng từ năm 2017. Năm 2023, đồng Bolivar anh tiết kiệm gần như vô giá trị, nhưng Bitcoin của anh đã bảo toàn và tăng giá trị đáng kể.

**Câu chuyện 2: Lập trình viên James ở Mỹ**

James mua 10 BTC vào năm 2011 với giá $1/BTC tổng cộng $10. Sau đó anh quên mất và ổ cứng cũ chứa private key bị hỏng. Năm 2021, khi BTC đạt $60,000, James nhớ lại — $600,000 đã biến mất mãi mãi vì không có cách khôi phục private key.

**Câu chuyện 3: Sàn FTX sụp đổ**

Năm 2022, sàn giao dịch FTX (từng có giá trị ~$32 tỷ) sụp đổ trong vài ngày. Hàng triệu người dùng để tiền trên sàn — họ không giữ Private Key. Khi FTX phá sản, tài sản của họ bị "đóng băng" và nhiều người mất toàn bộ.

**Câu hỏi phân tích:**

1. Câu chuyện 1 minh họa use case nào quan trọng nhất của Bitcoin? Tại sao quan trọng với người ở các nước đang phát triển?

2. Bài học quan trọng nhất từ câu chuyện 2 là gì? Nếu bạn mua Bitcoin, bạn sẽ backup Private Key như thế nào?

3. Câu chuyện 3 liên quan đến nguyên tắc "Not your keys, not your coins" như thế nào? Sàn giao dịch tập trung (CEX) có những rủi ro gì?

4. Dựa vào 3 câu chuyện trên, bạn rút ra được bài học tổng quát nào về cách tiếp cận Bitcoin an toàn?

---

## Đáp án & Giải thích

### Quiz
1. **B — 21 triệu BTC** — Con số được mã hóa cố định trong protocol Bitcoin
2. **B — Hash thay đổi → Chuỗi bị phá vỡ → Mạng lưới từ chối** — Đây là cơ chế Immutability
3. **C — Thanh toán điện tử peer-to-peer không cần bên thứ ba** — Câu đầu tiên trong Bitcoin Whitepaper
4. **B — Giải bài toán toán học khó bằng sức mạnh tính toán** — "Proof of Work" = bằng chứng đã bỏ ra công việc
5. **B — Ethereum chuyển từ PoW sang PoS** — Sự kiện ngày 15/9/2022, giảm điện năng 99.95%
6. **B — Nếu không giữ Private Key, không thực sự kiểm soát coin** — Bài học đắt giá từ FTX, Celsius...
7. **C — Mỗi 210,000 blocks (~4 năm)** — Lập trình cố định trong Bitcoin protocol
8. **B — Centralized Control** — Blockchain KHÔNG có kiểm soát tập trung, đó là phi tập trung
9. **C — Tiêu thụ năng lượng ít hơn rất nhiều** — Ethereum giảm 99.95% sau Merge
10. **C — Tên bí danh, danh tính vẫn là bí ẩn** — Craig Wright tự nhận là Satoshi nhưng không thể chứng minh

---

### Bài tập 2 — Mining Calculations

1. **Block Reward giá trị:**
   - Giá trị mỗi block = 3.125 × $60,000 = **$187,500**
   - Số block/ngày = 1440 ÷ 10 = **144 blocks/ngày**
   - BTC mới/ngày = 3.125 × 144 = **450 BTC/ngày**
   - Giá trị USD/ngày = 450 × $60,000 = **$27 triệu/ngày**

2. **Halving #5 Block Reward:** 3.125 ÷ 2 = **1.5625 BTC/block**

3. **Bitcoin cuối cùng:** Khoảng **năm 2140** — vì mỗi halving giảm tốc độ phát hành, phép tính là chuỗi hội tụ vô hạn

---

### Case Study — Phân tích

**Câu 1:** Use case quan trọng nhất: **Store of Value** (Lưu trữ giá trị) và **Hedge against Hyperinflation** (Bảo hiểm lạm phát). Đặc biệt quan trọng với người ở nước đang phát triển vì họ không có tiếp cận USD hoặc tài sản ổn định, trong khi Bitcoin có thể mua trên điện thoại với internet.

**Câu 2:** Backup Private Key là SỐNG CÒN. Các phương pháp an toàn:
- Viết Seed Phrase (24 từ) ra giấy, lưu nhiều nơi khác nhau
- Hardware Wallet (Ledger, Trezor) — thiết bị vật lý
- Không bao giờ lưu Seed Phrase trên điện thoại/email/cloud
- Không chia sẻ với BẤT KỲ ai

**Câu 3:** FTX là ví dụ điển hình. Khi để tiền trên CEX, bạn chỉ có "IOU" (I Owe You) — sàn hứa nợ bạn số coin đó. Rủi ro CEX: phá sản, hack, tịch thu bởi chính phủ, fraud.

**Câu 4:** Bài học tổng quát:
1. Bitcoin có giá trị thực trong bối cảnh lạm phát và kiểm soát vốn
2. Bảo vệ Private Key quan trọng hơn mọi chiến lược đầu tư
3. Không để tất cả trứng vào một giỏ (CEX), tự custody là lý tưởng
4. Blockchain là công nghệ — Bitcoin là asset — cần hiểu cả hai
