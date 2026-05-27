# Tài liệu tham khảo — Ngày 60: Crypto Trading & Investment Strategies

## So sánh các chiến lược đầu tư Crypto

| Chiến lược | Thời gian giữ | Kỹ năng cần | Thời gian theo dõi | Risk | Phù hợp với |
|-----------|--------------|------------|-------------------|------|-------------|
| HODL | Nhiều năm | Thấp | Vài giờ/tháng | Thấp-Trung | Người mới, bận rộn |
| DCA | Dài hạn (năm) | Rất thấp | Không cần | Thấp | Mọi người |
| Swing Trading | Ngày - Tuần | Trung-Cao | 1-2 giờ/ngày | Trung | Có TA kiến thức |
| Day Trading | Phút - Giờ | Rất cao | Full-time | Rất cao | Chuyên nghiệp |
| Futures (no lev) | Linh hoạt | Cao | Nhiều | Cao | Có kinh nghiệm |
| Futures (leverage) | Phút - Ngày | Chuyên sâu | Full-time | Cực cao | Chuyên nghiệp |
| Staking | Dài hạn | Thấp | Tối thiểu | Thấp | Mọi người |
| Airdrop Farming | Không cố định | Trung | Trung | Thấp-Trung | Có thời gian |

---

## Bảng So sánh Staking Options

| Option | Token | Chain | APY (ước tính) | Unstaking Period | Custodial? |
|--------|-------|-------|----------------|-----------------|-----------|
| Native ETH Staking | ETH | Ethereum | 3-4% | ~1-7 ngày | Không |
| Lido (stETH) | ETH | Ethereum | 3-4% | Instant (sell stETH) | Không |
| Rocket Pool (rETH) | ETH | Ethereum | 3.5-4.5% | Instant | Không |
| SOL Delegation | SOL | Solana | 6-8% | ~2-3 ngày | Không |
| Jito (jitoSOL) | SOL | Solana | 7-8% | Instant | Không |
| Binance Earn | ETH/BNB/SOL | N/A | 1-4% | Tùy option | CÓ |
| AAVE Safety Module | AAVE | Ethereum | 5-10% | 10 ngày | Không |
| Cosmos (ATOM) | ATOM | Cosmos | 10-15% | 21 ngày | Không |

*APY thay đổi theo thời gian, kiểm tra trang chính thức để cập nhật*

---

## Crypto Portfolio Templates

*Các template dưới đây chỉ là ví dụ học tập để luyện phân bổ rủi ro, không phải khuyến nghị đầu tư cá nhân.*

### Template 1: Người mới — Conservative
```
BTC:   60%  ████████████████████████████████████████████████████████
ETH:   30%  ██████████████████████████████
Stables: 10%  ██████████
```
*Mục tiêu: Tối thiểu hóa rủi ro trong khi tham gia crypto market*

### Template 2: Intermediate — Balanced
```
BTC:   50%  ██████████████████████████████████████████████████
ETH:   25%  █████████████████████████
Layer 1s: 15%  ███████████████ (SOL, AVAX, NEAR)
DeFi:  10%  ██████████ (AAVE, UNI, CRV)
```
*Mục tiêu: Exposure đa dạng hơn, vẫn giữ BTC/ETH là core*

### Template 3: Aggressive — High Risk/High Reward
```
BTC:   30%  ██████████████████████████████
ETH:   20%  ████████████████████
Layer 1s: 20%  ████████████████████
DeFi/Other: 20%  ████████████████████
Speculative: 10%  ██████████
```
*Mục tiêu: Maximize upside trong bull market, chấp nhận rủi ro cao hơn*

---

## DCA Calculator — Hướng dẫn tính toán

### Công thức tính Average Cost:
```
Average Cost = Tổng tiền đầu tư / Tổng số coin mua được

Ví dụ:
Tháng 1: $100 / $20,000 = 0.005 BTC
Tháng 2: $100 / $18,000 = 0.00556 BTC
Tháng 3: $100 / $25,000 = 0.004 BTC
Tháng 4: $100 / $22,000 = 0.00455 BTC

Tổng đầu tư: $400
Tổng BTC: 0.01911 BTC
Average Cost: $400 / 0.01911 = $20,930/BTC
```

### So sánh: Lump Sum vs DCA

| Scenario | Lump Sum $1,000 | DCA $100/tháng x 10 |
|----------|-----------------|---------------------|
| Mua tháng đỉnh ($68K) | Vào đúng đỉnh | Giảm impact |
| Mua tháng đáy ($16K) | Lợi nhất | Ít hơn Lump Sum |
| Trung bình 10 tháng | Phụ thuộc vào timing | Trung bình tốt hơn |
| Stress | Cao (sợ sai thời điểm) | Thấp (không cần đoán) |

---

## Leverage Risk Calculator

### Tính Liquidation Price:

```
Long Position:
Liquidation Price = Entry Price × (1 - 1/Leverage + Maintenance Margin)

Ví dụ (BTC Long, Entry $30,000, Leverage 10x, Maintenance Margin 0.5%):
Liquidation = $30,000 × (1 - 0.1 + 0.005) = $30,000 × 0.905 = $27,150

Giảm 10% từ $30K → $27K → Bị Liquidated!
```

### Mức leverage và % giảm để liquidation:

| Leverage | % giảm để Liquidated |
|----------|----------------------|
| 2x | ~50% |
| 5x | ~20% |
| 10x | ~10% |
| 20x | ~5% |
| 50x | ~2% |
| 100x | ~1% |

*Crypto thường biến động 5-15%/ngày → Leverage > 10x = cờ bạc*

---

## Top DeFi Platforms để Staking

### Liquid Staking ETH:
| Platform | Ticker | TVL | Link |
|----------|--------|-----|------|
| Lido | stETH | ~$30B | lido.fi |
| Rocket Pool | rETH | ~$4B | rocketpool.net |
| Frax | frxETH | ~$1B | frax.finance |
| Stakewise | osETH | ~$500M | stakewise.io |

### Staking SOL:
| Platform | Ticker | APY | Link |
|----------|--------|-----|------|
| Jito | jitoSOL | 7-8% | jito.network |
| Marinade | mSOL | 6-7% | marinade.finance |
| BlazeStake | bSOL | 7-8% | stake.solblaze.org |

---

## Airdrop Farming Checklist

### Protocol mới cần interact:
- [ ] Swap token trên DEX của protocol
- [ ] Add/remove liquidity
- [ ] Borrow/lend nếu có lending
- [ ] Bridge tiền sang chain mới
- [ ] Dùng governance (vote on proposals)
- [ ] Stake token của protocol
- [ ] Mint NFT nếu có

### Chains/ecosystems đáng chú ý để farm (tham khảo):
- Layer 2 Ethereum: Arbitrum ecosystem, Base ecosystem
- Cosmos ecosystem: các zone mới
- Solana ecosystem: protocols mới
- BTC Layer 2: đang phát triển mạnh

*Research kỹ trước khi tương tác với bất kỳ protocol mới nào*

---

## Tax Tracking Essentials

### Thông tin cần ghi lại cho mỗi giao dịch:
| Field | Ví dụ |
|-------|-------|
| Ngày giao dịch | 2024-03-15 |
| Loại giao dịch | Mua / Bán / Swap / Staking Reward |
| Asset | BTC |
| Số lượng | 0.05 BTC |
| Giá tại thời điểm | $50,000 |
| Giá trị USD | $2,500 |
| Fee | $5 |
| Sàn/Protocol | Binance |
| Transaction Hash | 0x... |

### Crypto Tax Software:
| Tool | Link | Giá | Hỗ trợ chains |
|------|------|-----|--------------|
| Koinly | koinly.io | Free-$279/năm | 350+ exchanges |
| CoinTracker | cointracker.io | Free-$599/năm | 300+ exchanges |
| TaxBit | taxbit.com | Liên hệ | US-focused |
| Accointing | accointing.com | Free-$199/năm | Multi-country |

---

## Tài liệu đọc thêm

### Về Investment Strategy:
- *"The Bitcoin Standard"* — Saifedean Ammous (lý do HODL Bitcoin)
- *"Digital Gold"* — Nathaniel Popper
- Newsletters: Bankless, The Defiant, Messari Crypto Theses

### Về Trading:
- *"Trading in the Zone"* — Mark Douglas (tâm lý trading)
- TradingView Learn: tradingview.com/education
- Babypips crypto section

### Về Staking & DeFi:
- *"How to DeFi"* — CoinGecko (free PDF)
- Bankless Protocol Deep Dives
- DefiLlama Blog
