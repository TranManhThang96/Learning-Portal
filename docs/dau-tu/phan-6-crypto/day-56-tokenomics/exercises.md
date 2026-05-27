# Bài tập — Ngày 56: Tokenomics

## Phần 1: Câu hỏi ôn tập (Quiz)

**1. Token XYZ có giá $5, Circulating Supply 50M, Max Supply 500M. Market Cap và FDV là bao nhiêu?**
- A. Market Cap $250M, FDV $250M
- B. Market Cap $250M, FDV $2.5B
- C. Market Cap $2.5B, FDV $250M
- D. Market Cap $500M, FDV $5B

**2. FDV/Market Cap = 8x có nghĩa là gì?**
- A. Token đang được định giá cao 8 lần so với giá trị thực
- B. Chỉ có 12.5% token đang lưu hành, 87.5% chưa được unlock
- C. Token sẽ tăng 8x trong tương lai
- D. Có 8 triệu token đang được vesting

**3. "Cliff Period 12 tháng" trong vesting schedule có nghĩa là?**
- A. Team phải làm việc 12 tháng trước khi nhận lương
- B. Không có token nào được unlock trong 12 tháng đầu
- C. 12% token được unlock mỗi tháng
- D. Token sẽ bị đốt sau 12 tháng nếu không dùng

**4. Impermanent Loss là rủi ro của?**
- A. Gửi tiết kiệm vào ngân hàng
- B. Cung cấp thanh khoản cho DEX (LP)
- C. Stake token trên validator
- D. Mua token trên sàn CEX

**5. Cơ chế nào tạo ra "Real Yield" bền vững nhất?**
- A. Phát hành token mới để trả staking reward
- B. Vay từ treasury để trả yield
- C. Chia sẻ phí giao dịch thực tế từ protocol cho stakers
- D. Tăng emission rate khi giá token giảm

**6. Bitcoin Halving xảy ra mỗi?**
- A. 2 năm (52,500 blocks)
- B. 4 năm (210,000 blocks)
- C. 4 năm đúng theo lịch (không phụ thuộc blocks)
- D. Khi tổng miners giảm 50%

**7. "Deflationary token" có nghĩa là?**
- A. Token có giá giảm theo thời gian
- B. Token có nguồn cung giảm theo thời gian (đốt > phát hành)
- C. Token được thế chấp bằng USD
- D. Token không thể mint thêm

**8. Dự án có phân phối: Team 35%, VC 30%, Community 25%, Public 10% — Vấn đề chính là?**
- A. Community quá ít
- B. Public quá nhiều
- C. Team + VC = 65% tổng supply → rủi ro dump cao
- D. Không có vấn đề gì

**9. EIP-1559 trên Ethereum làm gì với Gas Fee?**
- A. Giảm Gas Fee xuống 0
- B. Đốt phần Base Fee → ETH có thể deflationary
- C. Chuyển toàn bộ phí cho validators
- D. Tăng block size để giảm phí

**10. Token chỉ có "Governance Utility" nhưng protocol không có revenue — Giá trị nội tại của token là?**
- A. Cao — vì governance quan trọng
- B. Thấp — vì không có cash flow, không có value accrual thực sự
- C. Phụ thuộc vào số lượng voters
- D. Bằng với Market Cap

---

## Phần 2: Bài tập thực hành

### Bài tập 1: Tính toán cơ bản

Cho dữ liệu sau của Token ABC:
- Giá hiện tại: $2.50
- Circulating Supply: 200,000,000
- Total Supply: 800,000,000
- Max Supply: 1,000,000,000

**Yêu cầu:**
1. Tính Market Cap
2. Tính FDV (dùng Max Supply)
3. Tính FDV/Market Cap ratio
4. Nhận xét: Đây có phải "cờ đỏ" không? Tại sao?
5. Nếu tất cả token unlock và giá không thay đổi, Market Cap sẽ là bao nhiêu?

---

### Bài tập 2: Phân tích Vesting Schedule

Token DEF có vesting schedule sau:
```
Total Supply: 100M DEF
Team (20M): Cliff 6 tháng, Linear vesting 18 tháng sau cliff
VC (15M): Cliff 3 tháng, Linear vesting 9 tháng sau cliff
Community (50M): Phát hành dần theo block rewards (5 năm)
Public Sale (10M): Không lock
Treasury (5M): DAO kiểm soát
```

**Yêu cầu:**
1. Circulating Supply tại ngày launch là bao nhiêu?
2. Tại tháng thứ 4, bao nhiêu % VC tokens được unlock?
3. Tại tháng thứ 7, tổng token lưu thông là bao nhiêu (xấp xỉ, bỏ qua community rewards)?
4. Thời điểm nguy hiểm nhất (áp lực bán cao nhất) là tháng nào? Tại sao?
5. Đánh giá vesting schedule này: Tốt hay xấu so với tiêu chuẩn?

---

### Bài tập 3: So sánh Token Utility

Cho 3 token sau, xếp hạng từ cao đến thấp về giá trị nội tại và giải thích:

**Token X:** Governance token của DEX có $1B daily volume, 0.3% fee. Token holders có thể vote về protocol parameters. Không có fee sharing.

**Token Y:** Gas token của Layer 1 blockchain với 500,000 giao dịch/ngày. Mọi giao dịch đều cần dùng Y để trả phí.

**Token Z:** Staking token của lending protocol. Stakers nhận 40% tổng phí giao dịch (bằng USDC). Protocol có $100M revenue/năm.

---

### Bài tập 4: Đọc Tokenomics thực tế

Truy cập CoinGecko (coingecko.com) và chọn **một altcoin** trong top 50 (không phải BTC, ETH, BNB, SOL):

**Yêu cầu:**
1. Ghi lại: Tên token, giá, Circulating Supply, Total Supply, Max Supply
2. Tính FDV và FDV/Market Cap ratio
3. Tìm Tokenomics breakdown (thường trong Whitepaper hoặc trang chủ)
4. Ghi lại: Team %, Investor %, Community %
5. Tìm Vesting Schedule — Có cliff không? Vesting bao lâu?
6. Token có utility gì? Có real value accrual không?
7. Nhận xét tổng thể: Tokenomics tốt hay xấu?

---

### Bài tập 5: Tính Real Yield

Bạn đang cân nhắc stake vào 2 protocol:

**Protocol Alpha:**
- Staking APY: 25%
- Token Inflation Rate: 30%/năm
- Staking reward trả bằng token gốc

**Protocol Beta:**
- Staking APY: 8%
- Token Inflation Rate: 2%/năm
- Staking reward trả bằng USDC (từ protocol fee)

**Yêu cầu:**
1. Tính Real Yield của Alpha và Beta
2. Protocol nào có Real Yield tốt hơn?
3. Ngoài con số, còn yếu tố nào khác cần xem xét?

---

## Phần 3: Case Study — Phân tích Token thất bại

### Luna Classic (LUNC) — Bài học $40 tỷ biến mất

**Bối cảnh:**
Tháng 5/2022, hệ sinh thái Terra (LUNA + UST stablecoin) sụp đổ trong 72 giờ. Đây là một trong những vụ sụp đổ lớn nhất lịch sử crypto.

**Dữ liệu:**
- LUNA đỉnh (4/2022): $119
- LUNA đáy (5/2022): $0.00001
- UST mất neo: $1 → $0.02
- Tổng thiệt hại: ~$40 tỷ

**Tokenomics của LUNA (trước khi sụp):**
- UST là algorithmic stablecoin: Mint 1 UST = Burn $1 LUNA
- Để maintain peg: Burn UST = Mint LUNA
- Anchor Protocol: Trả 20% APY cho UST deposits (không bền vững)
- LUNA không có Max Supply — có thể mint không giới hạn

**Timeline sụp đổ:**
```
Ngày 1: UST mất neo nhẹ ($0.98) → Arbitrageurs burn UST → Mint LUNA
Ngày 2: UST = $0.80 → Panic → Burn nhiều UST hơn → Mint thêm LUNA
         LUNA supply tăng từ 400M → 6.5T (gấp 16,000 lần!)
Ngày 3: LUNA hyperinflation → Giá về $0.0001
         UST = $0.10 → Trust hoàn toàn mất
```

**Câu hỏi phân tích:**
1. Dấu hiệu cảnh báo tokenomics nào có thể thấy TRƯỚC khi sụp đổ?
2. Tại sao Anchor Protocol 20% APY là không bền vững (hint: từ đâu ra 20%)?
3. Cơ chế "burn UST → mint LUNA" có gì nguy hiểm khi áp lực bán lớn?
4. So sánh với USDC (fiat-backed stablecoin) — tại sao USDC an toàn hơn?
5. Nếu bạn biết tokenomics này, bạn sẽ đưa ra quyết định đầu tư như thế nào?

---

## Đáp án & Giải thích

### Quiz
1. **B** — Market Cap = $5 × 50M = $250M; FDV = $5 × 500M = $2.5B
2. **B** — FDV/MC = 8x nghĩa là 1/8 = 12.5% token đang lưu hành
3. **B** — Cliff = thời gian không có token nào unlock
4. **B** — Impermanent Loss là rủi ro đặc thù của Liquidity Providers trong DEX
5. **C** — Fee sharing từ doanh thu thực là Real Yield; phát token mới = inflation
6. **B** — Halving xảy ra mỗi 210,000 blocks, trung bình ~4 năm
7. **B** — Deflationary = nguồn cung giảm (burn > mint); không liên quan đến giá
8. **C** — Team + VC = 65% rủi ro dump cực cao, community chỉ 25%
9. **B** — EIP-1559 đốt Base Fee → reduce ETH supply → potential deflationary
10. **B** — Không có cash flow → không có value accrual → giá trị phụ thuộc speculation

---

### Bài tập 1: Giải
1. Market Cap = $2.50 × 200M = **$500M**
2. FDV = $2.50 × 1,000M = **$2.5B**
3. FDV/Market Cap = $2.5B / $500M = **5x**
4. **Cờ đỏ nhẹ**: FDV/MC = 5x, đúng ở ngưỡng cảnh báo. Có 800M token nữa chưa lưu hành. Cần kiểm tra unlock schedule để biết khi nào chúng được release.
5. Nếu tất cả unlock (1B tokens): Market Cap = $2.50 × 1B = **$2.5B** (= FDV lúc đó)

---

### Bài tập 2: Giải
1. **Circulating Supply tại launch**: Public Sale (10M) = **10M DEF** (10%)
2. **Tháng 4**: VC cliff là 3 tháng → tháng 4 là tháng đầu tiên unlock
   → Unlock: 15M / 9 tháng = 1.67M/tháng → ~**1.67M VC tokens** (11% VC tokens)
3. **Tháng 7**:
   - Public: 10M
   - VC: Cliff 3 tháng, đã vesting 4 tháng = 4 × 1.67M = 6.67M
   - Team: Cliff 6 tháng → tháng 7 là tháng đầu tiên → 20M/18 = 1.11M/tháng → 1.11M
   - Tổng ≈ **10M + 6.67M + 1.11M = 17.78M DEF**
4. **Tháng nguy hiểm nhất: Tháng 3-4** khi VC cliff kết thúc
   - VC có cliff ngắn nhất (3 tháng) → unlock sớm nhất → áp lực bán đầu tiên
   - Tháng 7: Team bắt đầu unlock → áp lực bán lần 2
5. **Đánh giá: TRUNG BÌNH-XẤU**
   - Xấu: VC cliff chỉ 3 tháng (quá ngắn), Team cliff 6 tháng (ngắn)
   - Tốt hơn nếu: VC cliff 12 tháng, Team cliff 12 tháng + vesting 36 tháng

---

### Bài tập 3: Xếp hạng
**Thứ 1: Token Z** (Staking + Real Revenue Sharing)
- Real yield từ $100M × 40% = $40M USDC/năm cho stakers
- Không phụ thuộc inflation, nhận USDC thực
- Giống như cổ phiếu chia cổ tức tiền mặt

**Thứ 2: Token Y** (Gas Token)
- Must-have utility — mọi giao dịch cần Y
- Network effect: Càng nhiều dApp → càng nhiều demand
- Nhược điểm: Không có direct cash flow cho holders

**Thứ 3: Token X** (Governance Only)
- Có thể vote, nhưng không nhận phần chia phí
- Protocol có $1B volume × 0.3% = $1.1M revenue/ngày nhưng holders không nhận gì
- Giá trị phụ thuộc speculation và hy vọng tương lai

---

### Bài tập 5: Giải
**Real Yield Alpha:**
Real APY = 25% - 30% = **-5%**
→ Tuy APY cao, nhưng token mới được phát ra nhiều hơn → giá giảm → thực ra lỗ

**Real Yield Beta:**
Real APY = 8% - 2% = **+6%**
→ Yield thực dương, nhận USDC không phụ thuộc token price

**Beta tốt hơn nhiều** dù APY thấp hơn.

**Các yếu tố khác:**
- Risk của protocol (audit, TVL, age)
- Liquidity khi muốn unstake
- Smart contract risk

---

### Case Study LUNA: Hướng dẫn phân tích

1. **Dấu hiệu cảnh báo trước:**
   - Anchor 20% APY không có nguồn revenue bền vững (dùng treasury)
   - UST algorithmic → không có real collateral backup
   - LUNA không có Max Supply → mint unlimited khi cần peg
   - Phụ thuộc vào growth liên tục để duy trì

2. **Tại sao 20% APY không bền vững:**
   - Nguồn: Từ Anchor's "yield reserve" (tiền VC đầu tư)
   - Reserve cạn dần mỗi tháng ~$50M
   - Không có organic revenue để duy trì 20%
   - Ponzi dynamics: Cần tiền mới vào để trả người cũ

3. **Nguy hiểm của burn UST → mint LUNA:**
   - Hoạt động tốt khi mọi người tin tưởng
   - Khi trust sụp đổ → vòng xoáy tử thần (death spiral)
   - Mint LUNA không giới hạn → hyperinflation → giá về 0

4. **USDC an toàn hơn:**
   - 1 USDC = 1 USD thực trong ngân hàng (fiat-backed)
   - Có thể redeem bất lúc nào
   - Không phụ thuộc algorithm hay market confidence

5. **Quyết định đầu tư:**
   - Tránh algorithmic stablecoin hoàn toàn
   - Tránh APY > 20% từ nguồn không rõ ràng
   - Nếu đã đầu tư: Set hard stop loss, đừng quá FOMO vào yield cao
