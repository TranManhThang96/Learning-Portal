# Bài tập — Ngày 60: Crypto Trading & Investment Strategies

## Phần 1: Câu hỏi ôn tập (Quiz)

**1. Bạn có $1,000 để đầu tư crypto lần đầu tiên. Chiến lược nào phù hợp nhất?**
- A. Mua altcoin meme coin đang hot để x10 nhanh
- B. Dùng leverage 10x để tối đa hóa lợi nhuận
- C. DCA vào BTC/ETH hàng tháng với kỳ vọng dài hạn
- D. Day trading để tận dụng volatility cao

**2. Staking ETH qua Lido có nghĩa là bạn sẽ nhận được gì?**
- A. ETH thật được stake trực tiếp trên Ethereum
- B. stETH — token đại diện tích lũy staking rewards, có thể dùng trong DeFi
- C. LIDO token như phần thưởng
- D. USD equivalent của ETH bạn stake

**3. Khi giữ vị thế Futures Long BTC với leverage 20x, giá giảm bao nhiêu % sẽ bị liquidation?**
- A. 50%
- B. 20%
- C. 10%
- D. ~5%

**4. "Funding Rate" trong Perpetual Futures là gì?**
- A. Phí rút tiền khi đóng vị thế
- B. Phí định kỳ giữa long và short positions để align giá perpetual với spot
- C. Hoa hồng sàn cho mỗi lệnh
- D. Lãi suất vay margin từ sàn

**5. Tại sao airdrop farming ngày càng khó kiếm được airdrop lớn?**
- A. Các dự án không còn làm airdrop nữa
- B. Sybil detection ngày càng tinh vi, dự án loại bỏ các ví chỉ farm airdrop
- C. Gas fees quá cao để tương tác
- D. Chính phủ cấm airdrop

**6. Portfolio mẫu 60% BTC + 30% ETH + 10% altcoin thường được dùng để minh họa điều gì?**
- A. BTC và ETH là coin duy nhất có thể sinh lợi
- B. BTC/ETH có track record dài, ít nguy cơ về 0, altcoin nhỏ bổ sung upside tiềm năng
- C. Đây là portfolio của các hedge fund lớn nhất
- D. BTC và ETH được chính phủ bảo lãnh

**7. Swing Trading trong crypto khác gì so với Forex/Stocks?**
- A. Crypto Swing Trading chỉ dùng timeframe ngắn hơn
- B. Crypto volatile hơn, trade 24/7, news/FOMO tác động mạnh hơn
- C. Crypto không có Technical Analysis patterns
- D. Swing Trading crypto luôn sinh lợi cao hơn

**8. Khi nào thì hợp lý để "all-in" vào một altcoin?**
- A. Khi influencer lớn đang shilling coin đó
- B. Khi coin đó đã tăng 10x trong tuần trước
- C. Không bao giờ — diversification luôn cần thiết
- D. Khi bạn chắc chắn 100% coin sẽ tăng

**9. Native staking SOL trực tiếp có ưu điểm gì so với staking qua CEX?**
- A. APY cao hơn đáng kể
- B. Không custodial — bạn giữ quyền kiểm soát token, không phụ thuộc sàn
- C. Phần thưởng được trả bằng USD
- D. Không cần unstaking period

**10. Điều nào sau đây là MỤC ĐÍCH CHÍNH của việc rebalancing danh mục crypto?**
- A. Tăng tổng giá trị danh mục nhanh nhất
- B. Mua thêm coin đang tăng để tối đa hóa lợi nhuận
- C. Giữ tỷ trọng đúng với mục tiêu ban đầu, bán bớt những gì tăng nhiều, mua thêm những gì giảm
- D. Giảm số lượng loại coin để đơn giản hóa

---

## Phần 2: Bài tập thực hành

### Bài tập 1: Thiết lập DCA plan thực tế

Hãy xây dựng DCA plan của bạn:

**Bước 1: Xác định số tiền**
- Thu nhập hàng tháng của bạn: $___
- % có thể dành cho đầu tư: ___%
- Tổng đầu tư/tháng: $___ 
- % cho crypto (tối đa 20%): ___%
- Số tiền DCA/tháng vào crypto: $___

**Bước 2: Phân bổ theo coin**

| Coin | Tỷ trọng | Số tiền/tháng |
|------|----------|---------------|
| BTC | ___% | $___ |
| ETH | ___% | $___ |
| Khác: ___ | ___% | $___ |
| **Tổng** | **100%** | **$___** |

**Bước 3: Chọn platform**
- Tôi sẽ DCA qua: _______________ (Binance Auto-Invest / Coinbase Recurring / Thủ công)
- Ngày mua mỗi tháng: Ngày ___
- Đây là tự động hay thủ công?

**Bước 4: Cam kết**
- Tôi cam kết DCA trong tối thiểu ___ tháng
- Tôi sẽ không panic sell khi giá giảm quá ___% vì: _______________

---

### Bài tập 2: Tính toán Liquidation Price

Cho các vị thế sau, tính Liquidation Price gần đúng:

*Công thức: Liquidation ≈ Entry Price × (1 - 1/Leverage)*

**Vị thế A:**
- LONG BTC, entry $40,000
- Leverage: 10x
- Liquidation Price ≈ $___
- Giảm ___% từ entry để bị liquidated

**Vị thế B:**
- LONG ETH, entry $3,000
- Leverage: 5x
- Liquidation Price ≈ $___
- Giảm ___% từ entry để bị liquidated

**Vị thế C:**
- LONG SOL, entry $100
- Leverage: 20x
- Liquidation Price ≈ $___
- Trong thực tế, SOL đã từng biến động ±10% trong một ngày. Với leverage 20x, vị thế này có an toàn không?

**Kết luận:** Với volatility đặc trưng của crypto (5-20%/ngày), leverage nào là "tương đối an toàn"?

---

### Bài tập 3: Xây dựng Portfolio cá nhân

Bạn có $5,000 để đầu tư vào crypto. Xây dựng portfolio của bạn:

**Mục tiêu đầu tư:** _______________
**Horizon (thời gian):** ___ năm
**Khẩu vị rủi ro:** Thấp / Trung bình / Cao

**Portfolio của tôi:**

| Coin/Token | Lý do chọn | % | Số tiền ($) | Giá mua dự kiến | Số lượng |
|------------|-----------|---|-------------|-----------------|---------|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| **Tổng** | | **100%** | **$5,000** | | |

**Chiến lược:**
- HODL: Coin nào tôi sẽ không bán dù thị trường như thế nào?
- Take profit: Tôi sẽ chốt lãi từng phần khi nào?
- Stop loss danh mục: Nếu danh mục giảm __%, tôi sẽ xem xét lại

---

## Phần 3: Case Study

### Case Study: So sánh 3 nhà đầu tư crypto — Kết quả khác nhau

**Bối cảnh:** Cả 3 người đều bắt đầu đầu tư crypto vào tháng 1/2020 với $10,000 mỗi người.

**Nhà đầu tư A — HODLer:**
- Mua $6,000 BTC + $4,000 ETH
- Không bán lần nào, bất kể biến động
- Tháng 12/2021: Portfolio ~$230,000 (+2,200%)
- Sau bear 2022: Portfolio ~$55,000 (+450%)

**Nhà đầu tư B — Trader:**
- Bắt đầu với $10,000
- Trade thường xuyên, đúng vài lệnh đầu
- Tháng 5/2021: Portfolio $60,000
- Bắt đầu dùng leverage 5x
- Bị liquidated tháng 6/2021 (Bitcoin giảm 50%)
- Portfolio cuối năm 2021: $8,000

**Nhà đầu tư C — DCA-er:**
- Mua $500/tháng đều đặn vào BTC + ETH (50/50)
- Tổng đầu tư 24 tháng: $12,000
- Tháng 12/2021: Portfolio ~$85,000
- Sau bear 2022: Portfolio ~$28,000

**Câu hỏi phân tích:**

1. Tại sao Nhà đầu tư A có kết quả tốt nhất ở đỉnh 2021, nhưng Nhà đầu tư C ổn định hơn trong bear market?

2. Nhà đầu tư B mắc những sai lầm nào? Bài học rút ra?

3. Nếu bạn là nhà đầu tư thứ 4, bắt đầu với $10,000 vào tháng 1/2020:
   - Bạn sẽ chọn chiến lược nào?
   - Tại sao?
   - Kết quả ước tính sẽ như thế nào?

4. "The best time to plant a tree was 20 years ago. The second best time is now." Câu này liên quan thế nào đến DCA strategy?

---

## Đáp án & Giải thích

### Quiz
1. **C** — DCA vào BTC/ETH là chiến lược an toàn, phù hợp cho người mới với kỳ vọng dài hạn
2. **B** — stETH là token đại diện, linh hoạt dùng trong DeFi trong khi vẫn nhận staking rewards
3. **D** — 20x leverage → ~5% biến động là bị liquidated. Crypto thường dao động nhiều hơn thế
4. **B** — Funding Rate là phí cân bằng giữa long và short, paid định kỳ (thường mỗi 8 giờ)
5. **B** — Projects dùng Sybil detection algorithm để lọc, chỉ tặng airdrop cho genuine users
6. **B** — Đây là ví dụ về cách giữ BTC/ETH làm core, còn altcoin chỉ là phần rủi ro nhỏ để học cách phân bổ
7. **B** — Crypto đặc thù: 24/7, volatility cao, news/influencer tác động mạnh hơn
8. **C** — Không bao giờ all-in một altcoin — risk quá cao, 95%+ altcoin sẽ về 0
9. **B** — Non-custodial = bạn giữ key, không có rủi ro sàn phá sản như FTX
10. **C** — Rebalancing là bán bớt winner để mua thêm loser, duy trì tỷ trọng mục tiêu

---

### Bài tập 2: Liquidation Price

**Vị thế A (BTC, 10x):**
- Liquidation ≈ $40,000 × (1 - 0.1) = $36,000
- Giảm 10% từ entry → bị liquidated

**Vị thế B (ETH, 5x):**
- Liquidation ≈ $3,000 × (1 - 0.2) = $2,400
- Giảm 20% từ entry → bị liquidated

**Vị thế C (SOL, 20x):**
- Liquidation ≈ $100 × (1 - 0.05) = $95
- Giảm 5% từ entry → bị liquidated
- SOL đã biến động ±10-30% trong một ngày nhiều lần → Cực kỳ nguy hiểm

**Kết luận:** Với crypto volatility thông thường 5-20%/ngày, leverage tối đa "tương đối an toàn" cho BTC là 2-3x, cho altcoin nên tránh hoàn toàn.

---

### Case Study: So sánh 3 nhà đầu tư

**1. HODLer vs DCA-er trong bear market:**
- HODLer A mua một lần ở đáy 2020 → đỉnh 2021 lợi nhuận tối đa
- DCA-er C mua đều qua cả 2020-2021 → average cost cao hơn, nhưng tiếp tục mua khi giá giảm
- Bear market 2022: HODLer A vẫn có lợi nhuận lớn từ entry thấp; DCA-er C vẫn ổn vì average cost hợp lý

**2. Sai lầm của Nhà đầu tư B:**
- Dùng leverage khi chưa đủ kinh nghiệm
- Không có stop loss rõ ràng
- Greed — tham khi đang thắng, tăng leverage
- Không hiểu liquidation risk với crypto volatility

**4. Câu nói về "trồng cây":**
Thời điểm tốt nhất để bắt đầu DCA đã qua (2009, 2012, 2017...), nhưng thời điểm tốt thứ hai là ngay bây giờ. DCA loại bỏ việc "chờ đúng thời điểm" — cứ bắt đầu, thị trường sẽ làm phần còn lại theo thời gian.
