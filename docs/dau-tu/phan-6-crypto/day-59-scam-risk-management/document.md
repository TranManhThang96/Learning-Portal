# Tài liệu tham khảo — Ngày 59: Scam & Risk trong Crypto

## Bảng tổng hợp các loại Scam

| Loại Scam | Cơ chế | Dấu hiệu | Thiệt hại điển hình |
|-----------|--------|----------|---------------------|
| Rug Pull | Dev rút liquidity | Unlocked liquidity, team ẩn danh | Token về 0 ngay lập tức |
| Ponzi | Tiền người mới trả người cũ | Lãi "guaranteed" bất thường | Mất hết khi sụp đổ |
| Pump & Dump | Thao túng giá qua marketing | Tăng đột biến không rõ nguyên nhân | Mất 50-100% sau dump |
| Phishing | Website/app giả mạo | URL sai, email lạ | Mất toàn bộ ví |
| Fake Airdrop | Yêu cầu approve malicious contract | "Claim miễn phí" yêu cầu connect ví | Drain toàn bộ ví |
| Romance Scam | Tình cảm → đầu tư crypto | Người lạ online giới thiệu "cơ hội" | Hàng chục ngàn USD |
| Smart Contract Exploit | Lỗ hổng code | N/A — dự án thật cũng bị | Hàng triệu USD |

---

## Danh sách Red Flags — Checklist đầy đủ

### 🔴 NGUY HIỂM CỰC CAO — Dừng ngay:
- [ ] Ai yêu cầu seed phrase / private key
- [ ] Hứa lợi nhuận "guaranteed" cao bất thường (>10%/tháng)
- [ ] "Gửi crypto nhận lại gấp đôi"
- [ ] Token không thể bán được (honeypot)
- [ ] Liquidity chưa lock, dev có thể rút bất cứ lúc

### 🟠 NGUY HIỂM CAO — Cần điều tra trước:
- [ ] Team hoàn toàn ẩn danh với vesting ngắn
- [ ] Contract chưa được audit
- [ ] Không có product sau 1 năm ra mắt
- [ ] Influencer shilling đồng loạt không rõ lý do
- [ ] Dev giữ >20% total supply không có lock

### 🟡 CẦN CHÚ Ý — Nghiên cứu thêm:
- [ ] Whitepaper mơ hồ, nhiều buzzword
- [ ] Community chủ yếu hỏi về giá
- [ ] Partnership không thể verify từ cả hai phía
- [ ] Roadmap liên tục delay không giải thích
- [ ] GitHub không có commits gần đây

---

## Công cụ verify dự án — Cheat Sheet

### Kiểm tra Smart Contract:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| Token Sniffer | tokensniffer.com | Auto-detect scam token patterns |
| GoPlus Security | gopluslabs.io | API check security |
| RugDoc | rugdoc.io | DeFi project risk assessment |
| Etherscan | etherscan.io | Đọc contract code, check holders |
| BscScan | bscscan.com | Tương tự cho BNB Chain |

### Kiểm tra Liquidity Lock:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| Unicrypt | app.unicrypt.network | Xem liquidity lock info |
| Team Finance | team.finance | Lock LP tokens phổ biến |
| PinkLock | pinksale.finance/pinklock | Verify lock duration |

### Kiểm tra Wallet của Dev:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| Etherscan | etherscan.io | Xem dev wallet transactions |
| Arkham | arkhamintelligence.com | Wallet identity |
| Nansen | nansen.ai | Wallet labeling |

### Kiểm tra Scam History:
| Công cụ | Link | Dùng để |
|---------|------|---------|
| Chainabuse | chainabuse.com | Database địa chỉ scam |
| CryptoScamDB | cryptoscamdb.org | Database website scam |
| ScamAlert | scam-alert.io | Report và tra cứu scam |

---

## Các vụ Scam/Hack lớn nhất lịch sử Crypto

| Vụ | Năm | Thiệt hại | Loại |
|----|-----|-----------|------|
| OneCoin | 2014-2019 | $4-15B | Ponzi |
| Mt.Gox | 2014 | $450M (BTC) | Exchange Hack |
| Bitconnect | 2016-2018 | $2.5B | Ponzi |
| Ronin Bridge (Axie) | 2022 | $625M | Smart Contract Hack |
| FTX | 2022 | $8B+ | Exchange Fraud |
| Terra/LUNA | 2022 | $60B+ | Algorithmic Stablecoin Collapse |
| PlusToken | 2018-2019 | $3B | Ponzi |
| Wormhole Bridge | 2022 | $320M | Smart Contract Hack |
| Nomad Bridge | 2022 | $190M | Smart Contract Hack |
| Squid Game Token | 2021 | $3.4M | Rug Pull |

---

## Hướng dẫn kiểm tra Contract trên Etherscan

### Kiểm tra cơ bản:
1. Vào **etherscan.io**, search địa chỉ contract
2. Tab **Contract**: Code có được verify không? (verified = có thể đọc code)
3. Tab **Holders**: Top holders là ai? Dev giữ bao nhiêu %?
4. Tab **Transactions**: Volume giao dịch thật sự

### Những điều cần tìm trong Contract code:
```
// Dấu hiệu xấu trong code:
function mint(address to, uint256 amount) // Mint không giới hạn
function setTax(uint256 rate) // Tax có thể đặt lên 100%
function blacklist(address) // Có thể chặn địa chỉ cụ thể
canSell = false; // Có thể disable selling

// Dấu hiệu tốt:
maxSupply được set cứng
Ownership đã được renounce (renounceOwnership)
Liquidity được lock trong contract
```

---

## Quy trình xử lý khi nghi ngờ bị scam

### Nếu vừa approve contract đáng ngờ:
1. **Ngay lập tức** vào revoke.cash
2. Revoke tất cả approvals của contract đó
3. Chuyển toàn bộ token còn lại sang ví khác (ví mới tạo)
4. Coi địa chỉ ví cũ là đã compromise

### Nếu vừa nhập seed phrase vào website lạ:
1. Coi seed phrase đó là **đã mất**
2. Ngay lập tức chuyển TOÀN BỘ tài sản sang ví mới (seed phrase mới)
3. Không dùng lại ví cũ đó nữa
4. Chạy antivirus scan trên máy tính

### Nếu bị lừa chuyển tiền:
1. Report lên Chainabuse.com (để cảnh báo người khác)
2. Report lên Cơ quan điều tra tội phạm mạng (Cục An ninh mạng)
3. Liên hệ sàn giao dịch nếu tiền đi qua sàn
4. Khả năng lấy lại tiền gần như = 0, nhưng cần báo cáo để bảo vệ người khác

---

## Tài liệu đọc thêm

### Báo cáo về crypto crime:
- **Chainalysis Crypto Crime Report** — Báo cáo hàng năm về scam và hack
- **FBI IC3 Annual Report** — Thống kê thiệt hại từ crypto fraud

### Để học về security:
- Ledger Academy: ledger.com/academy/security
- CipherTrace reports: ciphertrace.com
- Slowmist Hacks Library: hacks.slowmist.io (database các vụ hack)

### Podcast / Video:
- **Coffeezilla** (YouTube) — Chuyên điều tra crypto scam, rất educational
- **Unchained Podcast** — Episodes về các vụ scam lớn
- **Darknet Diaries** — Episodes về crypto crime

---

## Ghi chú nâng cao: Cách scammer tránh bị track

### Mixing / Tumbling:
Scammer dùng "mixer" như Tornado Cash để trộn ETH, làm mờ trail giao dịch. Tornado Cash bị OFAC sanctions năm 2022.

### Chain-hopping:
Chuyển tiền từ chain này sang chain khác qua bridges để làm phức tạp việc track.

### CEX cash-out:
Dùng tài khoản KYC của người khác (mua lại) để convert sang fiat.

**Tại sao điều này quan trọng:** Ngay cả khi biết địa chỉ ví scammer, rất khó thu hồi tiền. Phòng bệnh hơn chữa bệnh.
