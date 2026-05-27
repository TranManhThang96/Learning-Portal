# Tài liệu tham khảo — Ngày 55: Crypto Ecosystem — DeFi, NFT, DAO

## Bản đồ DeFi Ecosystem

```
┌─────────────────────────────────────────────────────────────────┐
│                         DEFI STACK                              │
├─────────────────────────────────────────────────────────────────┤
│  APPLICATIONS (User-facing)                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │Aggregator│ │Dashboard │ │Portfolio │ │  Borrow/Lend UI  │  │
│  │(1inch,   │ │(Zapper,  │ │Tracker   │ │(Aave, Compound   │  │
│  │Paraswap) │ │DeBank)   │ │          │ │Frontend)         │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  PROTOCOLS (Smart Contracts)                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │   DEX    │ │ Lending  │ │Stablecoin│ │    Derivatives   │  │
│  │Uniswap   │ │Aave      │ │MakerDAO  │ │    Perps         │  │
│  │Curve     │ │Compound  │ │USDC,USDT │ │    GMX, dYdX     │  │
│  │Balancer  │ │Morpho    │ │FRAX      │ │    Synthetix     │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  Oracle  │ │  Bridge  │ │ Indexer  │ │  Wallet/Identity │  │
│  │Chainlink │ │Stargate  │ │The Graph │ │  MetaMask/ENS    │  │
│  │Pyth      │ │LayerZero │ │Subgraphs │ │  Safe Multisig   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  BLOCKCHAIN (Settlement Layer)                                  │
│       Ethereum │ Arbitrum │ Optimism │ Base │ Polygon          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cheat Sheet: DeFi Protocols theo Category

### DEX (Sàn giao dịch phi tập trung)

| Protocol | Chain | Model | TVL | Đặc điểm |
|---------|-------|-------|-----|----------|
| **Uniswap v3** | Ethereum/L2 | AMM (Concentrated Liquidity) | $4B+ | Lớn nhất, v3 cải tiến capital efficiency |
| **Curve Finance** | Multi-chain | StableSwap AMM | $2B+ | Tối ưu cho stablecoin/pegged assets |
| **Balancer** | Ethereum/L2 | Weighted Pool AMM | $800M | Pool đa token, weight tùy chỉnh |
| **Jupiter** | Solana | Aggregator | — | Aggregator DEX lớn nhất Solana |
| **Raydium** | Solana | AMM + CLOB | $500M+ | Kết hợp AMM và Order Book |
| **PancakeSwap** | BNB Chain | AMM | $1.5B+ | Lớn nhất BNB Chain |
| **GMX** | Arbitrum/Avalanche | Perp DEX | $700M+ | Perpetual swaps, real yield |

### Lending Protocols

| Protocol | TVL | Đặc điểm |
|---------|-----|----------|
| **Aave v3** | $10B+ | Multi-chain, E-Mode, isolation mode |
| **Compound v3** | $1.5B+ | Đơn giản, stable, original DeFi blue chip |
| **MakerDAO/Sky** | $8B+ | Tạo DAI stablecoin, DSR (DAI Savings Rate) |
| **Morpho** | $3B+ | Tối ưu Aave/Compound rates |
| **Spark** | $2B+ | Fork Aave bởi MakerDAO |

### Liquid Staking (ETH Staking)

| Protocol | Share | APY | Đặc điểm |
|---------|-------|-----|----------|
| **Lido** | ~33% ETH staked | ~3.5% | Lớn nhất, nhận stETH |
| **Rocket Pool** | ~5% ETH staked | ~3.8% | Phi tập trung hơn, nhận rETH |
| **Frax Ether** | ~2% | ~4% | Tích hợp Frax ecosystem |
| **Coinbase cbETH** | ~5% | ~3.3% | CeFi-backed |

---

## NFT Ecosystem Overview

### Blue Chip NFT Collections (Ethereum)

| Collection | Supply | Floor Price (peak) | Đặc điểm |
|-----------|--------|---------------------|----------|
| **CryptoPunks** | 10,000 | ~100 ETH | OG NFT, 2017, held by Yuga Labs |
| **Bored Ape Yacht Club** | 10,000 | ~140 ETH (peak) | IP rights, celebrity holders |
| **Azuki** | 10,000 | ~20 ETH | Anime aesthetic, strong community |
| **Pudgy Penguins** | 8,888 | ~25 ETH | Toy expansion, mass market |
| **Nouns** | ∞ (1/day) | ~20 ETH | DAO governance, CC0 |

### NFT Marketplaces

| Marketplace | Chain | Model | Fee |
|------------|-------|-------|-----|
| **OpenSea** | Multi-chain | Peer-to-peer | 2.5% |
| **Blur** | Ethereum | Pro trading, aggregator | 0.5% |
| **Magic Eden** | Multi-chain | NFT marketplace | 2% |
| **Tensor** | Solana | Pro trading | 0-2% |
| **Foundation** | Ethereum | Curated art | 5% |

---

## Công thức AMM — Tóm tắt

```
Uniswap v2 (Constant Product):
  x × y = k
  Mọi asset đều đồng đều trên toàn bộ price range

Curve StableSwap:
  Kết hợp x×y=k và x+y=k
  → Giao dịch stablecoin ít slippage hơn

Uniswap v3 (Concentrated Liquidity):
  LP chọn range giá để cung cấp liquidity
  → Capital efficiency cao hơn ~4000x với range hẹp
  → Nhưng IL cao hơn nếu giá thoát range

Slippage Formula (ước tính):
  Slippage% ≈ Trade Size / (2 × Liquidity Pool Size)
  
  Ví dụ: Trade $100,000 trong pool $1,000,000:
  Slippage ≈ $100,000 / (2 × $1,000,000) = 5%
```

---

## Impermanent Loss Calculator

```
Công thức IL chính xác:
  IL% = 2√r/(1+r) - 1

  r = price ratio (giá mới / giá cũ của một token)

  r=1 (không đổi): IL = 0%
  r=2 (tăng 2x):   IL = -5.7%
  r=4 (tăng 4x):   IL = -20%
  r=9 (tăng 9x):   IL = -50%
  r=0.5 (giảm 50%): IL = -5.7%
  r=0.25 (giảm 75%): IL = -20%

Lưu ý:
- IL tính theo cả 2 hướng (tăng và giảm)
- Fees collected có thể bù đắp IL
- Concentrated liquidity (Uni v3) → IL cao hơn khi price thoát range
```

---

## DAO Governance Frameworks

```
Vòng đời một Proposal trong DAO:

1. IDEA (Diễn đàn thảo luận — 1-2 tuần)
   └── Đăng trên Discourse/Commonwealth
   └── Thu thập phản hồi cộng đồng

2. SNAPSHOT VOTE (Off-chain vote — không tốn gas)
   └── Dùng Snapshot.org
   └── Đo sentiment, không binding

3. ON-CHAIN VOTE (Binding — tốn gas)
   └── Qua Tally, Governor Bravo, OpenZeppelin Governor
   └── Cần đạt Quorum (VD: 4% total supply)
   └── Cần majority (VD: >50%)
   └── Timelock: 2-7 ngày trước khi thực thi

4. EXECUTION
   └── Smart Contract tự động thực thi
   └── Không ai có thể chặn (trừ security module)

Công cụ phổ biến:
- Snapshot: Off-chain voting
- Tally: On-chain voting UI
- Boardroom: Governance aggregator
- Safe (Gnosis Safe): Multi-sig treasury
```

---

## So sánh DeFi vs CeFi

| Tiêu chí | CeFi (Binance, Coinbase) | DeFi (Uniswap, Aave) |
|---------|--------------------------|----------------------|
| **Custody** | Exchange giữ tài sản | Bạn tự giữ (ví riêng) |
| **KYC/AML** | Bắt buộc | Không cần |
| **Truy cập** | Phụ thuộc jurisdiction | Global, không kiểm duyệt |
| **Downtime** | Có thể (bảo trì, hack) | Không thể tắt |
| **Rủi ro** | Hack sàn, insolvency (FTX!) | Smart contract bug |
| **Bảo hiểm** | Một số (FDIC không cover) | Nexus Mutual, InsurAce |
| **UX** | Dễ dùng | Phức tạp hơn |
| **Speed** | Nhanh (off-chain) | Chậm hơn, gas fees |
| **Transparency** | Không minh bạch (proof of reserve?) | Hoàn toàn on-chain |

**Bài học FTX (11/2022):** $8B của khách hàng CeFi bị mất do Sam Bankman-Fried dùng để đầu cơ → Phá sản trong 72 giờ. **"Not your keys, not your coins"** — Không phải private key của bạn, không phải coin của bạn.

---

## Công cụ theo dõi DeFi

| Tool | Link | Dùng để |
|------|------|---------|
| **DefiLlama** | defillama.com | TVL tất cả chains/protocols |
| **Dune Analytics** | dune.com | Custom on-chain analytics |
| **Nansen** | nansen.ai | Smart money tracking |
| **DeBankCloud** | debank.com | Portfolio tracker, protocol monitoring |
| **Zapper** | zapper.xyz | DeFi portfolio management |
| **Token Terminal** | tokenterminal.com | Protocol revenue/earnings |
| **Rekt.news** | rekt.news | DeFi hack history |
| **OpenSea** | opensea.io | NFT marketplace |
| **Blur** | blur.io | NFT pro trading |
| **NFT Price Floor** | nftpricefloor.com | NFT floor price tracker |
| **Tally** | tally.xyz | DAO governance |
| **Snapshot** | snapshot.org | Off-chain DAO voting |

---

## Rủi ro chính trong DeFi

```
RỦIRO                    MÔ TẢ                           CÁCH PHÒNG TRÁNH
─────────────────────────────────────────────────────────────────────────
Smart Contract Bug    Code có lỗ hổng, bị hack         Dùng protocol lâu đời,
                      VD: $600M Poly Network hack        đã audit nhiều lần

Oracle Manipulation   Dữ liệu giá bị thao túng          Dùng TWAP, Chainlink
                      VD: Mango Markets $100M            không dùng spot price

Rug Pull              Team rút liquidity, bỏ trốn       Kiểm tra team, audit,
                      VD: Hundreds of memecoin           thời gian vesting

Liquidation           Giá giảm, bị thanh lý             Health Factor > 1.5,
                      mất tài sản thế chấp               monitor thường xuyên

Impermanent Loss      Giá đổi → LP lỗ so với HODL       Chọn stable-stable pool
                                                          hoặc stable-ETH narrow range

Bridge Hack           Bridge bị tấn công mất tiền       Dùng bridge uy tín,
                      VD: $625M Ronin Bridge             hạn chế số tiền bridge
```

---

## Tài liệu đọc thêm

**Sách:**
- "How DeFi Works" — Finematics series (YouTube tốt hơn)
- "The DeFi Edge" newsletter
- Bankless newsletter/podcast

**Website/Docs:**
- docs.uniswap.org — Tài liệu Uniswap
- docs.aave.com — Tài liệu Aave
- makerdao.com — MakerDAO documentation
- ethereum.org/en/defi — DeFi overview chính thức

**YouTube:**
- Finematics — Giải thích DeFi bằng animation
- Bankless — DeFi news và education
- The Defiant — DeFi journalism

**Podcast:**
- Bankless Podcast
- Unchained (Laura Shin)
- The Defiant
