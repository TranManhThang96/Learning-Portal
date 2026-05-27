# Tài liệu tham khảo — Ngày 53: Blockchain & Bitcoin Cơ bản

## Bảng tóm tắt / Cheat Sheet

### Bitcoin Fundamentals — Số liệu cốt lõi

| Thông số | Giá trị | Ghi chú |
|----------|---------|---------|
| Tổng cung tối đa | 21,000,000 BTC | Cố định mãi mãi |
| BTC đã được đào | ~19.7 triệu BTC | Cập nhật ~2024 |
| BTC còn lại | ~1.3 triệu BTC | Sẽ khai thác đến ~2140 |
| BTC ước tính mất mãi | 3-4 triệu BTC | Mất private key |
| Block Time | ~10 phút | Trung bình giữa các block |
| Block Size | 1-4 MB (với SegWit) | |
| Transaction per second | ~7 TPS | Chậm so với Visa 24,000 TPS |
| Block Reward hiện tại | 3.125 BTC (sau 2024 Halving) | |
| Halving chu kỳ | Mỗi 210,000 blocks (~4 năm) | |
| Genesis Block | 03/01/2009 | Satoshi đào block đầu tiên |
| Satoshi → BTC | 1 BTC = 100,000,000 Satoshi | |

---

### Lịch sử Bitcoin Halving

| Halving | Ngày | Block Reward trước | Block Reward sau | Giá BTC tại thời điểm |
|---------|------|--------------------|------------------|----------------------|
| Genesis | 2009 | — | 50 BTC | ~$0 |
| Halving #1 | 28/11/2012 | 50 BTC | 25 BTC | ~$12 |
| Halving #2 | 09/07/2016 | 25 BTC | 12.5 BTC | ~$650 |
| Halving #3 | 11/05/2020 | 12.5 BTC | 6.25 BTC | ~$8,700 |
| Halving #4 | 19/04/2024 | 6.25 BTC | 3.125 BTC | ~$63,000 |
| Halving #5 | ~2028 | 3.125 BTC | 1.5625 BTC | ? |

**Pattern lịch sử:** Giá BTC thường tăng mạnh trong 12-18 tháng SAU halving (do supply giảm, demand tăng). Tuy nhiên, lịch sử không đảm bảo tương lai.

---

### So sánh PoW vs PoS Chi tiết

| Tiêu chí | Proof of Work | Proof of Stake |
|----------|--------------|----------------|
| Cơ chế | Cạnh tranh sức mạnh tính toán | Chọn ngẫu nhiên theo tỷ lệ stake |
| Phần thưởng | Block reward + Transaction fees | Staking rewards + Transaction fees |
| Phần cứng cần | ASIC miners ($5,000-$10,000+) | Máy tính thông thường |
| Điện năng | Rất cao | Thấp hơn 99.95% |
| Xác suất tấn công | Cần 51% hash rate | Cần 51% tổng stake |
| Thời gian block | ~10 phút (Bitcoin) | ~12 giây (Ethereum) |
| Ví dụ blockchain | Bitcoin, Litecoin, Monero | Ethereum, Solana, Cardano, Avalanche |
| Thay đổi được? | Rất khó (Bitcoin sẽ không đổi) | Đã thay đổi (ETH từ PoW → PoS) |

---

### Blockchain vs Database Truyền thống

```
DATABASE TRUYỀN THỐNG          BLOCKCHAIN
─────────────────────          ──────────────────────────
┌─────────────┐                ○    ○    ○
│   Server    │                │  ╲  │  ╱ │
│   Trung     │                ○    ○    ○
│   Tâm       │                │  ╱  │  ╲ │
└─────────────┘                ○    ○    ○

• 1 điểm kiểm soát            • Hàng nghìn node
• Có thể bị tắt/hack          • Không có điểm thất bại trung tâm
• Có thể sửa dữ liệu          • Bất biến
• Nhanh                        • Chậm hơn
• Rẻ                           • Tốn phí gas
• Phù hợp: mọi ứng dụng      • Phù hợp: khi cần phi tập trung
```

---

### Cách đọc một Bitcoin Transaction

```
TRANSACTION EXAMPLE
═══════════════════
Transaction ID (TxID):
4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b

INPUT (From):
Address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf (Satoshi's Genesis Address)
Amount: 0.5 BTC

OUTPUT (To):
Address: 3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5 (Recipient)
Amount: 0.4985 BTC

Fee: 0.0015 BTC (Phí giao dịch → Miner)
Confirmations: 750,000+ (Đã được xác nhận 750,000 lần)
```

**Số Confirmations:** Số block được thêm vào sau block chứa giao dịch của bạn.
- 1 confirmation: Giao dịch vào block gần nhất
- 6 confirmations: Coi là "an toàn hoàn toàn" với giá trị lớn
- Với số tiền nhỏ: 1-3 confirmations thường đủ

---

### Hệ sinh thái Bitcoin hiện tại

```
BITCOIN ECOSYSTEM

Layer 1: Bitcoin Base Layer
├── ~15,000+ Full Nodes trên toàn thế giới
├── ~1 EH/s (Exahash/s) tổng Hash Rate toàn mạng
└── Mining Pools: Foundry USA, AntPool, F2Pool, ViaBTC...

Layer 2: Lightning Network
├── Thanh toán tức thì, phí gần 0
├── Dùng cho micropayments
└── El Salvador, nhiều merchant sử dụng

Institutional Adoption (2024)
├── Bitcoin ETF: BlackRock iShares Bitcoin Trust (IBIT), Fidelity Wise Origin...
├── MicroStrategy: ~200,000+ BTC trên balance sheet
├── El Salvador: Quốc gia công nhận BTC là legal tender
└── Nhiều công ty Fortune 500 chấp nhận BTC thanh toán
```

---

### Tools Theo dõi Bitcoin

**Block Explorers (Kiểm tra giao dịch):**
- **Blockchain.com**: blockchain.com/explorer
- **Mempool.space**: mempool.space — Tốt nhất để xem mempool và fee

**Metrics & Analysis:**
- **Glassnode** (glassnode.com): On-chain metrics, phân tích chuyên sâu (có gói free)
- **CoinMetrics** (coinmetrics.io): Dữ liệu on-chain
- **Bitcoin Treasuries** (bitcointreasuries.net): Theo dõi holdings của tổ chức

**Price & Market:**
- **CoinGecko** (coingecko.com): Giá, market cap, volume
- **CoinMarketCap** (coinmarketcap.com): Tương tự CoinGecko
- **TradingView**: Chart phân tích kỹ thuật

**Mining:**
- **BTC.com**: Pool stats, hashrate
- **Blockchain.com/charts**: Hashrate, difficulty charts

---

## Tài liệu đọc thêm

### Tài liệu Gốc
- **Bitcoin Whitepaper** (2008): nakamotoinstitute.org/bitcoin — Đọc bản gốc 8 trang của Satoshi
- **Bitcoin Wiki**: en.bitcoin.it/wiki — Tài liệu kỹ thuật chi tiết

### Sách
- **"The Bitcoin Standard"** — Saifedean Ammous: Giải thích Bitcoin từ góc độ kinh tế học, tại sao Bitcoin là tiền tốt nhất
- **"Digital Gold"** — Nathaniel Popper: Lịch sử Bitcoin từ 2009-2015, kể câu chuyện rất hấp dẫn
- **"Mastering Bitcoin"** — Andreas Antonopoulos: Kỹ thuật chuyên sâu (miễn phí online: github.com/bitcoinbook)
- **"The Internet of Money"** — Andreas Antonopoulos: Ý nghĩa triết học và xã hội của Bitcoin

### Video
- **YouTube: "Bitcoin Explained"** — 3Blue1Brown: Giải thích kỹ thuật Blockchain rất trực quan
- **YouTube: Andreas Antonopoulos**: Giảng giải về Bitcoin, rất sâu sắc
- **YouTube: "But how does bitcoin actually work?"** — 3Blue1Brown: Video nổi tiếng nhất giải thích Bitcoin

### Podcast
- **"What Bitcoin Did"** — Peter McCormack: Phỏng vấn các nhân vật trong Bitcoin space
- **"Unchained"** — Laura Shin: Crypto news và phỏng vấn

---

## Ghi chú bổ sung

### Tại sao 21 triệu là con số giới hạn?

Satoshi không giải thích rõ lý do chọn 21 triệu. Tuy nhiên, có thể suy luận:
- Toán học: 21 triệu × 100 triệu satoshi = 2.1 quadrillion satoshi — đủ nhỏ để làm đơn vị vi thanh toán
- Con số không quá nhỏ (gây phân tán) cũng không quá lớn (gây cảm giác dư thừa)
- Quan trọng hơn: Đây là TỔNG CỐ ĐỊNH — yếu tố khan hiếm là cốt lõi

### Lightning Network — Layer 2 Bitcoin

Bitcoin base layer chậm và đắt cho micropayments. **Lightning Network** giải quyết bằng:
- Mở "Payment Channel" giữa 2 người (cần 1 on-chain transaction)
- Giao dịch qua channel là tức thì, gần như miễn phí
- Đóng channel: 1 on-chain transaction ghi lại số dư cuối
- El Salvador dùng Lightning Network cho thanh toán hàng ngày bằng BTC

### Taproot — Nâng cấp Bitcoin 2021

Bitcoin nâng cấp Taproot (Tháng 11/2021) cải thiện:
- **Privacy**: Nhiều loại giao dịch phức tạp trông giống giao dịch thông thường
- **Efficiency**: Script phức tạp được nén lại, tiết kiệm phí
- **Smart Contract tiềm năng**: Nền tảng cho các ứng dụng phức tạp hơn trên Bitcoin

### Ordinals & Bitcoin NFT (2023)

Năm 2023, **Ordinals Protocol** cho phép ghi dữ liệu (hình ảnh, text) trực tiếp vào từng Satoshi trên Bitcoin — tạo ra "Bitcoin NFT". Tranh cãi trong cộng đồng Bitcoin về việc điều này có phù hợp với triết lý Bitcoin không.

### MVRV Ratio — Chỉ số On-chain Quan trọng

**MVRV** (Market Value to Realized Value):
- Market Value = Tổng giá trị tất cả BTC tại giá hiện tại
- Realized Value = Tổng giá trị tất cả BTC tại giá mà chúng cuối cùng di chuyển
- MVRV > 3.5: Thị trường overvalued, thường gần đỉnh
- MVRV < 1: Thị trường undervalued, thường gần đáy lịch sử
- Có thể xem trên Glassnode (gói free có giới hạn) hoặc LookIntoBitcoin.com
