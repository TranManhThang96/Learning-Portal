# Tài liệu tham khảo — Ngày 57: Wallet & Security

## Bảng so sánh Hot Wallet vs Cold Wallet

| Tiêu chí | Hot Wallet | Cold Wallet (Hardware) |
|----------|------------|------------------------|
| Kết nối Internet | Có | Không (khi lưu trữ) |
| Bảo mật | Trung bình | Rất cao |
| Chi phí | Miễn phí | $69 - $219 |
| Tiện lợi | Cao | Trung bình |
| Phù hợp với | Giao dịch thường xuyên | Lưu trữ dài hạn |
| Rủi ro chính | Hack, malware, phishing | Mất thiết bị vật lý |
| Ví dụ | MetaMask, Trust Wallet | Ledger, Trezor |
| Số tiền nên giữ | < 10% tổng tài sản | 70-80% tổng tài sản |

---

## Bảng so sánh CEX vs DEX

| Tiêu chí | CEX | DEX |
|----------|-----|-----|
| Custodial | Có (họ giữ key) | Không (bạn giữ key) |
| KYC | Bắt buộc | Không cần |
| Thanh khoản | Rất cao | Thấp hơn (altcoin nhỏ) |
| Phí giao dịch | 0.1-0.5% | Gas fee + 0.01-0.3% |
| Tốc độ | Tức thì (off-chain) | Phụ thuộc blockchain |
| Bảo mật | Rủi ro đối tác | Rủi ro Smart Contract |
| Privacy | Thấp | Cao |
| Dễ dùng | Dễ | Phức tạp hơn |
| Fiat support | Có | Thường không |
| Ví dụ | Binance, OKX, Bybit | Uniswap, Jupiter, PancakeSwap |

---

## Hardware Wallet — So sánh các hãng lớn

| Tiêu chí | Ledger Nano X | Trezor Model T | Coldcard Mk4 |
|----------|---------------|----------------|--------------|
| Giá | ~$149 | ~$219 | ~$149 |
| Số coin hỗ trợ | 5,500+ | 1,800+ | Bitcoin only |
| Kết nối | USB-C, Bluetooth | USB-C | USB-C, MicroSD |
| Open-source | Firmware có | Hoàn toàn | Hoàn toàn |
| Màn hình | Có | Cảm ứng | E-ink |
| Phù hợp | Đa dạng coin | Security cao | Bitcoin maximalist |
| Phần mềm | Ledger Live | Trezor Suite | Sparrow Wallet |

---

## Sơ đồ phân bổ tài sản theo bảo mật

```
TỔNG TÀI SẢN CRYPTO
│
├── [70-80%] COLD STORAGE — Hardware Wallet
│   ├── BTC, ETH dài hạn
│   ├── Không đụng hàng tháng/năm
│   └── Seed phrase offline, 2-3 bản sao
│
├── [15-25%] CEX UY TÍN (Binance, OKX, Coinbase)
│   ├── Sẵn sàng mua/bán
│   ├── Bật 2FA, whitelist địa chỉ rút
│   └── Phân tán qua 2-3 sàn
│
└── [5-10%] HOT WALLET (MetaMask, Phantom)
    ├── DeFi, DEX, NFT, airdrop
    ├── Chỉ approve contract cần thiết
    └── Revoke approval sau khi dùng xong
```

---

## Checklist Bảo mật Crypto — In ra và dán nơi dễ thấy

### ✅ Khi tạo ví mới:
- [ ] Mua Hardware Wallet từ trang chính hãng
- [ ] Kiểm tra seal/bao bì nguyên vẹn
- [ ] Tạo ví trong môi trường riêng tư, offline nếu có thể
- [ ] Viết tay seed phrase — KHÔNG chụp ảnh
- [ ] Kiểm tra lại thứ tự từng từ
- [ ] Lưu 2-3 bản sao ở nơi khác nhau
- [ ] Test khôi phục trước khi nạp tiền lớn

### ✅ Bảo mật tài khoản CEX:
- [ ] Email riêng chỉ cho crypto
- [ ] Mật khẩu mạnh, unique (dùng Password Manager)
- [ ] 2FA bằng Google Authenticator (không phải SMS)
- [ ] Whitelist địa chỉ rút tiền
- [ ] Anti-phishing code đã bật
- [ ] Giới hạn rút tiền hàng ngày

### ✅ Thói quen hàng ngày:
- [ ] Không truy cập crypto qua WiFi công cộng
- [ ] Kiểm tra URL website (tránh phishing)
- [ ] Không click link trong email/Telegram lạ
- [ ] Revoke smart contract approval không cần dùng
- [ ] Không chia sẻ seed phrase/private key với bất kỳ ai

---

## Các công cụ hữu ích

### Kiểm tra địa chỉ ví:
- **Etherscan** (etherscan.io) — Ethereum & EVM chains
- **Solscan** (solscan.io) — Solana
- **BscScan** (bscscan.com) — BNB Chain
- **Blockchain.com** — Bitcoin

### Revoke Contract Approval:
- **Revoke.cash** — Revoke ERC-20 approvals
- **DeBank** (debank.com) — Xem tất cả tài sản và approvals

### Kiểm tra Security Score của Token:
- **Token Sniffer** — Phát hiện scam token
- **GoPlus Security** — API check security

### Password Manager:
- **1Password** — Trả phí, rất uy tín
- **Bitwarden** — Miễn phí, open-source

---

## Tài liệu đọc thêm

### Sách:
- *"Bitcoin and Cryptocurrency Technologies"* — Arvind Narayanan (miễn phí online)
- *"Mastering Bitcoin"* — Andreas Antonopoulos (free on GitHub)
- *"The Bitcoin Standard"* — Saifedean Ammous

### Website chính thức:
- Ledger Academy: ledger.com/academy
- Trezor Wiki: trezor.io/learn
- MetaMask Learn: learn.metamask.io

### Video học:
- 99Bitcoins YouTube — Hướng dẫn ví cho người mới
- Andreas Antonopoulos YouTube — Deep dive về Bitcoin security

---

## Ghi chú nâng cao

### Multi-signature Wallet (Ví đa chữ ký):
Ví yêu cầu **N trong M chữ ký** để thực hiện giao dịch. Ví dụ: 2-of-3 (cần 2 trong 3 key để ký).

Phù hợp cho:
- Quỹ đầu tư/DAO
- Cá nhân có tài sản rất lớn
- Chia sẻ quản lý giữa nhiồu người

Công cụ: **Gnosis Safe** (Safe.global) — Multi-sig phổ biến nhất

### Shamir's Secret Sharing:
Chia seed phrase thành N phần, cần M phần để khôi phục. Trezor hỗ trợ SLIP-39 (Shamir Backup). Ví dụ: chia thành 5 phần, cần 3 phần để khôi phục.

### Passphrase (25th word):
Thêm một mật khẩu tùy chọn vào seed phrase, tạo ra một ví hoàn toàn khác. Ngay cả khi ai đó có seed phrase 24 từ, họ vẫn không vào được ví của bạn nếu không biết passphrase. Ledger và Trezor đều hỗ trợ.
