# Tài liệu tham khảo — Ngày 54: Ethereum & Smart Contracts

## Bảng so sánh các Layer 1 Blockchain

| Blockchain | Token | Consensus | TPS | Gas Fee | EVM? | Đặc điểm nổi bật |
|-----------|-------|-----------|-----|---------|------|------------------|
| **Ethereum** | ETH | PoS | ~30 | $1-50 | Gốc | Ecosystem lớn nhất, bảo mật nhất |
| **Solana** | SOL | PoH+PoS | ~65,000 | ~$0.0001 | Không | Tốc độ cực cao, có downtime |
| **BNB Chain** | BNB | PoSA | ~300 | ~$0.05 | Có | Của Binance, tập trung |
| **Avalanche** | AVAX | PoS | ~4,500 | ~$0.1 | C-Chain | Subnet architecture |
| **Cardano** | ADA | PoS (Ouroboros) | ~250 | ~$0.2 | Không | Academic approach |
| **Near** | NEAR | PoS | ~100,000 | ~$0.001 | Aurora | Sharding, UX tốt |
| **Polygon** | MATIC/POL | PoS+ZK | ~7,000 | ~$0.01 | Có | Ethereum sidechain+L2 |
| **Arbitrum** | ARB | Optimistic Rollup | ~40,000 | ~$0.1 | Có | L2 lớn nhất |
| **Optimism** | OP | Optimistic Rollup | ~2,000 | ~$0.05 | Có | OP Stack ecosystem |
| **Sui** | SUI | DPoS | ~297,000 | ~$0.001 | Không (Move) | Mới nhất, throughput cao |

---

## Cheat Sheet: Gas Fee Calculator

```
Gas Fee (ETH) = Gas Used × Gas Price (Gwei) ÷ 10^9

Ví dụ:
- Transfer ETH: 21,000 gas × 20 Gwei = 420,000 Gwei = 0.00042 ETH
- Nếu ETH = $2,000: Chi phí = $0.84

Gas Used thường gặp:
┌─────────────────────────────┬────────────────┐
│ Giao dịch                   │ Gas Used       │
├─────────────────────────────┼────────────────┤
│ Transfer ETH                │ 21,000         │
│ Transfer ERC-20 Token       │ 65,000         │
│ Approve ERC-20              │ 46,000         │
│ Uniswap Swap                │ 100,000-200,000│
│ Add Liquidity               │ 150,000-300,000│
│ Mint NFT (đơn giản)         │ 80,000-150,000 │
│ Deploy Smart Contract       │ 500,000+       │
└─────────────────────────────┴────────────────┘

Gas Price theo tình trạng mạng:
- Mạng bình thường: 10-30 Gwei
- Mạng trung bình: 30-80 Gwei
- Mạng tắc nghẽn: 80-300+ Gwei
- Bull run 2021 đỉnh: ~1,000+ Gwei
```

---

## Timeline Ethereum — Các Milestone quan trọng

```
2013 ── Vitalik Buterin công bố Ethereum Whitepaper
2014 ── ICO gây quỹ: $18.4M (bán ETH giá $0.31)
2015 ── Mainnet ra mắt (Frontier)
2016 ── The DAO Hack → Hard Fork → ETH/ETC tách
2017 ── ICO boom, ETH tăng từ $10 → $1,400
2019 ── Constantinople upgrade, giảm block reward
2020 ── Ethereum 2.0 Beacon Chain ra mắt (PoS bắt đầu chạy song song)
2021 ── EIP-1559 (London Upgrade): Base Fee + Burn mechanism
        ETH đạt ATH ~$4,800
2022 ── THE MERGE (9/15/2022): Chuyển hoàn toàn sang PoS
2023 ── Shanghai/Capella: Cho phép rút ETH đã stake
2024 ── Dencun upgrade: EIP-4844 (Proto-Danksharding) → L2 fees giảm 90%
2025+ ── Pectra, Fusaka: Tiếp tục cải thiện scalability
```

---

## Token Standards trên Ethereum

| Standard | Loại | Dùng cho | Ví dụ |
|----------|------|----------|-------|
| **ERC-20** | Fungible Token | Altcoin, governance token, stablecoin | USDT, LINK, UNI, AAVE |
| **ERC-721** | Non-Fungible Token (NFT) | Digital art, collectibles, PFP | Bored Ape, CryptoPunks |
| **ERC-1155** | Multi Token | Game items, semi-fungible | Axie Infinity |
| **ERC-4626** | Vault Token | DeFi yield vaults | Yearn Finance |
| **ERC-2981** | Royalty | NFT royalty standards | Nhiều NFT marketplace |

---

## Sơ đồ Layer Architecture

```
┌─────────────────────────────────────────┐
│              Layer 3 (L3)               │
│     App-specific chains (AppChains)     │
│         Xylabs, Degen Chain...          │
├─────────────────────────────────────────┤
│              Layer 2 (L2)               │
│   Arbitrum │ Optimism │ Base │ zkSync   │
│   StarkNet │ Polygon zkEVM │ Scroll     │
│   [Giao dịch nhanh, phí thấp]          │
├─────────────────────────────────────────┤
│              Layer 1 (L1)               │
│              ETHEREUM                   │
│    [Bảo mật, Phân tán, Settlement]     │
└─────────────────────────────────────────┘
```

---

## Ethereum vs Solana — So sánh chi tiết

### Khi nào chọn Ethereum/L2?
- Giao dịch giá trị lớn (cần bảo mật tối đa)
- DeFi nghiêm túc (TVL cao, audit kỹ)
- NFT blue-chip
- Muốn sử dụng L2 (Base, Arbitrum, Optimism)

### Khi nào chọn Solana?
- Giao dịch tần suất cao, giá trị nhỏ
- Memecoin trading (phí thấp, tốc độ cao)
- NFT gaming
- Chấp nhận rủi ro downtime thỉnh thoảng

---

## Tools theo dõi Ethereum

| Tool | Link | Dùng để |
|------|------|---------|
| Etherscan | etherscan.io | Xem giao dịch, Smart Contract |
| ETH Gas Station | ethgasstation.info | Theo dõi Gas Price |
| DefiLlama | defillama.com | TVL các protocol |
| Dune Analytics | dune.com | On-chain data analytics |
| Ultrasound Money | ultrasound.money | ETH supply, burn rate |
| L2Beat | l2beat.com | Theo dõi L2 ecosystem |

---

## Tài liệu đọc thêm

**Sách/Whitepaper:**
- Ethereum Whitepaper (Vitalik Buterin, 2013) — ethereum.org/en/whitepaper
- "The Infinite Machine" — Camila Russo (lịch sử Ethereum)
- Ethereum Yellow Paper — spec kỹ thuật

**Website:**
- ethereum.org — Tài liệu chính thức
- docs.soliditylang.org — Tài liệu Solidity
- ethereum.org/en/developers/docs/evm — Chi tiết EVM

**YouTube/Video:**
- "Ethereum Explained" — Finematics
- "How does Ethereum work?" — 3Blue1Brown style animations
- "EVM Deep Dive" — Patrick Collins

---

## Ghi chú bổ sung — Nâng cao

**Các loại Rollup:**

**Optimistic Rollup** (Arbitrum, Optimism):
- Giả định giao dịch hợp lệ (optimistic)
- Có **7-day challenge period** để phát hiện gian lận
- Pros: Đơn giản hơn, tương thích EVM cao
- Cons: Rút tiền về L1 mất 7 ngày (có bridge để bypass)

**ZK Rollup** (zkSync, StarkNet, Polygon zkEVM):
- Dùng **zero-knowledge proof** để chứng minh toán học rằng giao dịch hợp lệ
- Không cần challenge period → rút tiền nhanh hơn
- Pros: Bảo mật cao hơn về mặt toán học
- Cons: Phức tạp hơn, EVM compatibility hạn chế hơn (đang cải thiện)

**Account Abstraction (EIP-4337):**
- Cho phép Smart Contract làm "wallet"
- Tính năng: Gas trả bằng bất kỳ token nào, batch transactions, social recovery
- Đây là tương lai của UX trong crypto
