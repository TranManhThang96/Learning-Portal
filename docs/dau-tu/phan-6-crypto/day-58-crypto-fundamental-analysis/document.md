# Tài liệu tham khảo — Ngày 58: Crypto Fundamental Analysis

## Bảng tổng hợp On-chain Metrics

| Metric | Ý nghĩa | Tốt khi | Xấu khi | Tool |
|--------|---------|---------|---------|------|
| TVL | Tổng tài sản deposit vào DeFi | Tăng liên tục | Giảm mạnh đột ngột | DefiLlama |
| Active Addresses | Số ví giao dịch | Tăng cùng giá | Giảm trong khi giá tăng | Glassnode |
| Transaction Volume | Khối lượng giao dịch | NVT < 30 | NVT > 100 | CryptoQuant |
| Protocol Revenue | Phí thu từ người dùng | Tăng trưởng | Gần bằng 0 | Token Terminal |
| Developer Activity | Commits trên GitHub | Nhiều, đều đặn | Ngừng hẳn | Artemis.xyz |
| Exchange Netflow | Dòng tiền vào/ra sàn | Outflow (rút về ví) | Inflow lớn (chuẩn bán) | Glassnode |

---

## Framework phân tích dự án — Scoring Matrix

### Bảng điểm chi tiết (1-5 điểm mỗi tiêu chí)

| Tiêu chí | 1 điểm | 3 điểm | 5 điểm |
|----------|--------|--------|--------|
| **Vấn đề giải quyết** | Mơ hồ, không cụ thể | Có thật nhưng cạnh tranh nhiều | Vấn đề rõ ràng, market lớn, ít giải pháp tốt |
| **Sự cần thiết của Blockchain** | Không cần blockchain | Có thể dùng blockchain | Blockchain là giải pháp tốt nhất |
| **Team background** | Ẩn danh hoàn toàn | Có vài thành viên doxxed | Toàn bộ doxxed, kinh nghiệm mạnh |
| **Team vesting** | Không lock hoặc < 6 tháng | Lock 6-12 tháng | Lock 2-4 năm + cliff |
| **Sản phẩm thực tế** | Chỉ có whitepaper | Beta/testnet | Mainnet đang hoạt động |
| **Adoption (TVL/Users)** | Gần bằng 0 | Tăng chậm | Tăng trưởng mạnh, organic |
| **Revenue** | Không có | Minimal | Revenue thật, tăng trưởng |
| **Code audit** | Chưa audit | Audit bởi công ty nhỏ | Audit bởi Trail of Bits, OpenZeppelin |
| **Developer activity** | Không có commits | Commits không đều | Commits đều đặn, nhiều contributor |
| **Tokenomics** | Token không có utility | Utility giới hạn | Token cần thiết cho ecosystem |
| **Token distribution** | VC/Insiders > 50% | VC/Insiders 20-50% | Community-first, VC < 20% |
| **Community quality** | Chủ yếu bots/shillers | Mixed | Technical, engaged, organic |

**Điểm tổng:**
- 48-60: Dự án xuất sắc, rủi ro thấp
- 36-47: Dự án tốt, rủi ro trung bình
- 24-35: Cần nghiên cứu thêm, rủi ro cao
- < 24: Tránh

---

## Bộ công cụ nghiên cứu Crypto — Cheat Sheet

### Nghiên cứu tổng quan:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| CoinGecko | coingecko.com | Market data, tokenomics cơ bản |
| CoinMarketCap | coinmarketcap.com | Market cap, volume, price history |
| Messari | messari.io | Research reports, metrics |
| CryptoCompare | cryptocompare.com | News, data aggregate |

### DeFi Research:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| DefiLlama | defillama.com | TVL, revenue, DEX volumes |
| Token Terminal | tokenterminal.com | Protocol revenue, P/S ratio |
| Dune Analytics | dune.com | Custom on-chain queries |
| DeFiPulse | defipulse.com | Historical DeFi data |

### On-chain Analysis:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| Glassnode | glassnode.com | BTC/ETH on-chain deep dive |
| Nansen | nansen.ai | Wallet tracking, smart money |
| Arkham Intelligence | arkhamintelligence.com | Wallet de-anonymization |
| Etherscan | etherscan.io | Ethereum transactions |

### Developer Activity:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| Artemis.xyz | artemis.xyz | Dev activity across chains |
| Electric Capital | electriccapital.com/ecosystems | Developer ecosystem reports |
| Santiment | santiment.net | Social + dev metrics |

### Social & Sentiment:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| LunarCrush | lunarcrush.com | Social intelligence |
| Santiment | santiment.net | Social volume, sentiment |
| The Tie | thetie.io | Institutional-grade sentiment |

---

## Các DeFi Protocol lớn nhất theo TVL (tham khảo)

*(Dữ liệu thay đổi theo thời gian — kiểm tra DefiLlama để cập nhật)*

| Protocol | Category | Chain | Mô tả |
|----------|----------|-------|-------|
| Lido | Liquid Staking | Ethereum | Staking ETH nhận stETH |
| AAVE | Lending | Multi-chain | Lending/Borrowing lớn nhất |
| Uniswap | DEX | Ethereum | DEX AMM lớn nhất |
| MakerDAO | CDP/Stablecoin | Ethereum | Tạo DAI stablecoin |
| Curve | DEX | Ethereum | Chuyên stablecoin swap |
| Compound | Lending | Ethereum | Lending protocol OG |
| dYdX | Perpetuals | Cosmos | Derivatives DEX |
| Jupiter | DEX Aggregator | Solana | Aggregator tốt nhất trên Solana |

---

## Checklist đọc Whitepaper

### Phần phải đọc:
- [ ] Abstract/Executive Summary — tóm tắt 1 trang
- [ ] Problem & Solution — vấn đề và giải pháp
- [ ] Technical Architecture — sơ lược kỹ thuật
- [ ] Tokenomics — phân phối và utility của token
- [ ] Roadmap — kế hoạch phát triển
- [ ] Team — thành viên và background

### Câu hỏi sau khi đọc:
- [ ] Mình có hiểu dự án làm gì không?
- [ ] Vấn đề có thật không?
- [ ] Giải pháp có khả thi về mặt kỹ thuật không?
- [ ] Token có cần thiết không?
- [ ] Roadmap có thực tế không?

### Red flags trong Whitepaper:
- 🚩 Quá nhiều buzzword, ít nội dung thật
- 🚩 Whitepaper copy từ dự án khác
- 🚩 Không có technical details
- 🚩 Tokenomics tập trung vào team/VC quá nhiều
- 🚩 Roadmap không có deadline cụ thể
- 🚩 Không đề cập rủi ro

---

## Tài liệu đọc thêm

### Whitepaper kinh điển cần đọc:
- **Bitcoin Whitepaper** — Satoshi Nakamoto (2008): bitcoin.org/bitcoin.pdf
- **Ethereum Whitepaper** — Vitalik Buterin (2014): ethereum.org/whitepaper

### Nghiên cứu:
- **Messari Annual Crypto Theses** — Báo cáo hàng năm toàn diện nhất về crypto
- **Electric Capital Developer Report** — Báo cáo developer activity hàng năm
- **Delphi Digital Reports** — Research cao cấp (một số free)
- **Bankless** — Newsletter và podcast crypto chất lượng cao

### Sách:
- *"How to DeFi"* — CoinGecko team (free PDF)
- *"The Infinite Machine"* — Camila Russo (về lịch sử Ethereum)
- *"Digital Gold"* — Nathaniel Popper (về Bitcoin)

---

## Ghi chú nâng cao: Valuation Frameworks cho Crypto

### 1. Network Value to Transactions (NVT)
```
NVT = Market Cap / Daily Transaction Volume (30-day avg)
NVT < 30: Có thể undervalued
NVT 30-100: Fair value
NVT > 100: Có thể overvalued
```

### 2. Price to Sales (P/S) cho DeFi
```
P/S = Fully Diluted Valuation / Annualized Revenue
Tương tự P/S trong cổ phiếu
P/S < 10: Có thể undervalued cho DeFi protocol có tăng trưởng cao
```

### 3. TVL Ratio
```
TVL Ratio = Market Cap / TVL
< 1: Undervalued (thị trường định giá thấp hơn tài sản đang lock)
1-3: Fair value
> 3: Overvalued
```

### 4. Metcalfe's Law ứng dụng
```
Network Value ∝ n²
(n = số người dùng)
Giá trị mạng tỷ lệ với bình phương số người dùng
→ Tăng trưởng user base mũ 2 so với giá trị
```
