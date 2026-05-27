# Tài liệu tham khảo — Ngày 56: Tokenomics

## Cheat Sheet: Đánh giá Tokenomics nhanh

```
TOKENOMICS QUICK CHECKLIST

Supply:
□ Max Supply có giới hạn? (Tốt hơn nếu có)
□ Circulating / Total Supply ratio > 50%? (< 30% = cảnh báo)
□ FDV / Market Cap < 3x? (> 5x = đèn đỏ)

Distribution:
□ Team + VC < 40%?
□ Community allocation > 35%?
□ Distribution được công khai minh bạch?

Vesting:
□ Team có cliff ≥ 12 tháng?
□ Tổng vesting period ≥ 3 năm?
□ Unlock events sắp tới trong 6 tháng tới?

Utility:
□ Token có real utility (gas, fee sharing, collateral)?
□ Value accrual mechanism rõ ràng?
□ Protocol có real revenue?

Inflation:
□ Inflation rate < 10%/năm?
□ Có cơ chế giảm inflation theo thời gian?
□ Có burn mechanism offset inflation?
```

---

## Bảng so sánh Tokenomics các dự án lớn

| Project | Max Supply | Inflation | FDV/MC | Vesting | Đánh giá |
|---------|-----------|-----------|--------|---------|----------|
| **Bitcoin** | 21M | ~0.85%/năm | ~1.06x | Không có | ⭐⭐⭐⭐⭐ Tốt nhất |
| **Ethereum** | Không có | ~-0.2% (deflationary) | ~1x | Không có | ⭐⭐⭐⭐⭐ Rất tốt |
| **BNB** | 200M (burn về 100M) | Deflationary | ~1.01x | Không có | ⭐⭐⭐⭐ Tốt |
| **Solana** | Không có | ~5-7%/năm (giảm dần) | ~1.2x | Không có | ⭐⭐⭐ Trung bình |
| **Cardano** | 45B | ~1.6%/năm | ~1.03x | Không có | ⭐⭐⭐⭐ Khá tốt |
| **Avalanche** | 720M | ~7%/năm | ~1.5x | Vesting dần | ⭐⭐⭐ Trung bình |
| **Aptos** | 1B | ~7%/năm | ~5-8x | Vesting dài | ⭐⭐ Cần thận |
| **Sui** | 10B | ~10%/năm | ~5-6x | Vesting dài | ⭐⭐ Cần thận |

*Lưu ý: Số liệu thay đổi theo thời gian, luôn verify trên nguồn chính thức*

---

## Công thức tính toán quan trọng

```
MARKET CAP
Market Cap = Token Price × Circulating Supply

FDV (Fully Diluted Valuation)
FDV = Token Price × Max Supply (hoặc Total Supply nếu không có Max)

FDV RATIO
FDV/Market Cap = Max Supply / Circulating Supply
→ Tỷ lệ token chưa lưu hành

INFLATION RATE
Annual Inflation% = (New Tokens Issued / Current Supply) × 100

DILUTION IMPACT
Giá điều chỉnh = Giá hiện tại × (Cung hiện tại / Cung sau unlock)
Ví dụ: Unlock thêm 20% token:
→ Giá điều chỉnh lý thuyết = $10 × (100/120) = $8.33
→ Giảm 16.7% nếu cầu không đổi

REAL YIELD (Staking)
Real APY = Nominal APY - Token Inflation Rate
Ví dụ: APY staking 15%, Inflation 20% → Real APY = -5% (thực ra đang lỗ)
```

---

## Unlock Event Calendar — Cách theo dõi

```
Các nguồn theo dõi Unlock Events:

1. token.unlocks.app
   - Calendar toàn bộ unlock events
   - Filter theo ngày, project, chain

2. Vestlab.io
   - Vesting tracker chi tiết

3. CryptoRank.io
   - Unlock calendar + market cap data

4. Dune Analytics
   - Custom queries on-chain

Cách dùng thực tế:
1. Mở token.unlocks.app
2. Xem unlock events 30-60 ngày tới
3. Tìm unlock > 5% circulating supply
4. Cân nhắc: Tránh mua 1-2 tuần trước unlock lớn
5. Sau unlock: Nếu giá không dump → signal mạnh
```

---

## Token Distribution — Mẫu "Good" vs "Bad"

### Good Distribution Example
```
Protocol A (DeFi Blue Chip):
Total Supply: 100M tokens

Community Rewards:    40% = 40M  [Farming, grants, ecosystem]
Treasury (DAO):       20% = 20M  [Vesting: unlock tuyến tính 4 năm]
Team:                 15% = 15M  [Cliff 1 năm, vesting 3 năm]
Investors:            15% = 15M  [Cliff 6 tháng, vesting 2 năm]
Public Sale:          5%  = 5M   [No lock]
Liquidity/Exchange:   5%  = 5M   [No lock]

Tích cực:
✓ Community nhận phần lớn nhất
✓ Team/VC có cliff rõ ràng
✓ Treasury do DAO kiểm soát
✓ Circulating khi launch: ~10% (public + liquidity)
✓ FDV/Market Cap tại launch: ~10x (cần monitor unlock)
```

### Bad Distribution Example
```
Protocol B (Scam/Low Quality):
Total Supply: 1 tỷ tokens

"Ecosystem":          30% = 300M  [Thực ra team kiểm soát]
Team + Advisors:      25% = 250M  [Vesting 6 tháng, không cliff]
Private Sale Round 1: 20% = 200M  [Lock 3 tháng, 3 tháng unlock]
Private Sale Round 2: 15% = 150M  [Lock 1 tháng]
IDO/Public:           5%  = 50M   [No lock]
Marketing:            5%  = 50M   [No lock]

Tiêu cực:
✗ Team + VC = 60% total supply
✗ Vesting cực ngắn (3-6 tháng)
✗ Không có cliff
✗ "Ecosystem" do team kiểm soát = effective team allocation 55%
✗ Sau 6 tháng: 90% supply có thể bán
→ Pattern: Launch cao → dump sau 3-6 tháng
```

---

## Inflation Rate So sánh

```
Annual Inflation Rates (ước tính 2024):

0%        Bitcoin (cố định 21M)
~0%       Ethereum (net deflationary khi mạng bận)
~1.5%     Cardano ADA
~5%       Solana SOL (giảm ~15%/năm)
~7%       Avalanche AVAX
~8%       Polkadot DOT
~15%      Nhiều DeFi farming tokens
~100%+    Extreme farming tokens (Olympus-style)

Tham khảo:
- USD Inflation: ~3-4%/năm (2024)
- Vàng: ~1.5%/năm (khai thác mới)
- Bitcoin so với vàng: Halving đưa BTC inflation về < vàng năm 2024
```

---

## Bitcoin Halving History & Impact

```
EVENT      DATE        BTC PRICE    12-MONTH AFTER
─────────────────────────────────────────────────────
Genesis    Jan 2009    $0           -
1st Half   Nov 2012    $12          ~$1,200 (+9,900%)
2nd Half   Jul 2016    $650         ~$19,000 (+2,823%)
3rd Half   May 2020    $8,600       ~$63,000 (+633%)
4th Half   Apr 2024    $63,000      ? (tính từ 4/2024)

Pattern:
- Bull peak thường ~12-18 tháng sau halving
- Không đảm bảo lặp lại vì market mature hơn
- ETF BTC (Jan 2024) thay đổi dynamics — institutional demand

Lưu ý: Past performance ≠ Future results
Nhưng supply shock từ halving là THẬT và có thể đo được
```

---

## Tools phân tích Tokenomics

| Tool | Link | Dùng để |
|------|------|---------|
| **CoinGecko** | coingecko.com | Supply data, market cap, FDV |
| **CoinMarketCap** | coinmarketcap.com | Supply data, circulating vs total |
| **Token Unlocks** | token.unlocks.app | Vesting & unlock calendar |
| **Messari** | messari.io | Tokenomics research, metrics |
| **CryptoRank** | cryptorank.io | Fundraising, vesting data |
| **Etherscan** | etherscan.io | On-chain holder distribution |
| **Solscan** | solscan.io | Solana token holders |
| **Nansen** | nansen.ai | Whale wallet tracking |
| **Arkham** | arkhamintelligence.com | Wallet identity & tracking |
| **Token Terminal** | tokenterminal.com | Protocol P/E, revenue metrics |
| **Ultrasound Money** | ultrasound.money | ETH supply, burn rate |

---

## Value Accrual Mechanisms — Bảng so sánh

| Mechanism | Ví dụ | Cách tạo giá trị | Bền vững? |
|----------|-------|-----------------|----------|
| **Gas Token** | ETH, SOL, BNB | Cần để dùng network | ⭐⭐⭐⭐⭐ Rất cao |
| **Fee Sharing** | GMX, dYdX | Stakers nhận % fee | ⭐⭐⭐⭐⭐ Cao nếu revenue thực |
| **Buyback & Burn** | BNB | Doanh thu → mua+đốt | ⭐⭐⭐⭐ Cao |
| **Collateral** | ETH, BTC | Được chấp nhận DeFi | ⭐⭐⭐⭐ Cao |
| **Real Staking Yield** | ETH staking | Phí từ validators | ⭐⭐⭐⭐ Cao |
| **Governance (với treasury)** | MKR | Vote kiểm soát tài sản | ⭐⭐⭐ Trung bình |
| **Governance (chỉ vote)** | Nhiều DeFi tokens | Vote về protocol params | ⭐⭐ Yếu |
| **Fake APY farming** | OHM-forks | Phát token mới làm yield | ⭐ Không bền vững |

---

## Tài liệu đọc thêm

**Articles:**
- "Tokenomics 101" — Messari Research
- "Understanding Token Vesting" — Coinbase Learn
- "FDV: The Most Misunderstood Metric" — Delphi Digital

**Tools & Docs:**
- docs.uniswap.org/concepts/governance/overview (Uniswap governance)
- bitcoinhalving.com (Bitcoin halving countdown)
- token.unlocks.app (unlock calendar)

**Sách:**
- "The Bitcoin Standard" — Saifedean Ammous (Bitcoin monetomics)
- "Digital Gold" — Nathaniel Popper (Bitcoin lịch sử)

**Ghi chú nâng cao — Token Valuation Models:**

```
Mô hình định giá token (experimental):

1. P/E Ratio tương tự (Price/Revenue):
   Protocol Revenue = Annualized fees
   P/Revenue = FDV / Annual Revenue
   VD: Uniswap FDV $8B / Revenue $500M = P/R = 16x
   So sánh với TradFi: Thấp = undervalued? (cẩn thận)

2. NVT Ratio (Network Value to Transactions):
   NVT = Market Cap / Daily Transaction Volume
   Cao = overvalued, Thấp = undervalued
   Dùng tốt nhất cho Bitcoin

3. Metcalfe's Law:
   Network Value ∝ n² (n = active users)
   Dự báo giá dựa trên tăng trưởng user

Lưu ý: Tất cả mô hình này còn rất experimental trong crypto.
Không có mô hình nào được chứng minh đáng tin cậy.
```
