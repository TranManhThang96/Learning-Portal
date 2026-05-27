# Ngày 54: Ethereum & Smart Contracts

## Mục tiêu học tập
- [ ] Hiểu Ethereum là gì và tại sao nó khác Bitcoin
- [ ] Nắm vững khái niệm Smart Contract và ứng dụng thực tế
- [ ] Hiểu EVM, Gas Fee và cơ chế hoạt động của Ethereum
- [ ] Biết về Ethereum 2.0 và sự chuyển dịch sang Proof of Stake
- [ ] So sánh được các Layer 1 blockchain cạnh tranh với Ethereum

---

## Nội dung bài giảng

### 1. Ethereum là gì — "World Computer" vs "Digital Gold"

Như đã học ở Ngày 53, Bitcoin được thiết kế với một mục đích duy nhất: **lưu trữ và chuyển giá trị**. Bitcoin giống như vàng kỹ thuật số — đơn giản, an toàn, không thay đổi.

Ethereum được tạo ra bởi **Vitalik Buterin** — một lập trình viên người Canada gốc Nga — vào năm 2015. Vitalik đặt câu hỏi: "Tại sao chúng ta không thể xây dựng một blockchain có thể chạy **bất kỳ chương trình nào**?"

Ý tưởng đột phá của Ethereum: blockchain không chỉ là sổ cái ghi giao dịch, mà là một **máy tính phi tập trung** có thể thực thi code. Người ta gọi Ethereum là **"World Computer"** (máy tính của thế giới).

**Sự khác biệt cốt lõi:**

| | Bitcoin | Ethereum |
|--|---------|----------|
| **Mục đích chính** | Lưu trữ & chuyển giá trị | Nền tảng lập trình phi tập trung |
| **Ngôn ngữ hợp đồng** | Script (hạn chế) | Solidity (đầy đủ Turing-complete) |
| **Ứng dụng** | Thanh toán, lưu trữ | DeFi, NFT, DAO, dApps |
| **Token gốc** | BTC | ETH (Ether) |
| **Tốc độ block** | ~10 phút | ~12 giây |

---

### 2. Smart Contract — Hợp đồng Thông minh

**Smart Contract** (hợp đồng thông minh) là chương trình tự động chạy trên blockchain khi các điều kiện được thỏa mãn. Không cần bên trung gian, không cần tin tưởng đối phương — code **tự thực thi** khi đủ điều kiện.

**Ví dụ thực tế dễ hiểu:**

Hãy tưởng tượng bạn mua nhà qua hợp đồng thông thường:
1. Ký hợp đồng với luật sư
2. Chờ ngân hàng xác nhận
3. Chờ công chứng
4. Chờ chuyển sổ đỏ
→ Mất 2-3 tháng, tốn phí hàng chục triệu.

Với Smart Contract:
```
IF (người mua chuyển 2 tỷ VND)
AND (người bán ký xác nhận)
THEN → Tự động chuyển quyền sở hữu nhà
     → Trả tiền cho người bán
     → Cập nhật sổ đỏ blockchain
```
→ Xảy ra trong vài phút, phí rất thấp, không ai có thể gian lận.

**Đặc điểm của Smart Contract:**
- **Trustless** (không cần tin tưởng): Không cần tin người kia vì code tự thực thi
- **Immutable** (bất biến): Một khi deploy lên blockchain, không ai sửa được
- **Transparent** (minh bạch): Ai cũng có thể đọc code
- **Permissionless** (không cần xin phép): Ai cũng có thể tương tác

---

### 3. EVM — Ethereum Virtual Machine

**EVM** (Ethereum Virtual Machine — Máy ảo Ethereum) là "engine" chạy Smart Contract trên Ethereum. Mỗi node (máy tính) trong mạng Ethereum đều chạy EVM, và tất cả đều thực thi code y hệt nhau.

**Cách hoạt động đơn giản:**

```
Người dùng gửi Transaction (giao dịch)
        ↓
Giao dịch được broadcast lên mạng
        ↓
Validators (những người xác nhận) chọn giao dịch
        ↓
EVM thực thi Smart Contract Code
        ↓
Kết quả được ghi vào blockchain (bất biến)
```

**Tại sao EVM quan trọng?**

EVM đã trở thành **tiêu chuẩn công nghiệp**. Hàng chục blockchain khác như Polygon, Avalanche C-Chain, BNB Chain, Arbitrum, Optimism đều tương thích EVM — có nghĩa là code Ethereum có thể chạy thẳng trên các chain này mà không cần sửa.

---

### 4. Gas Fee — Chi phí giao dịch trên Ethereum

**Gas** là đơn vị đo lường "công sức tính toán" cần thiết để thực thi một thao tác trên Ethereum.

**Gas Fee** (phí gas) = Gas Used × Gas Price

- **Gas Price** được tính bằng **Gwei** (1 ETH = 1,000,000,000 Gwei)
- Bạn trả phí cao hơn → giao dịch được xử lý nhanh hơn
- Mạng tắc nghẽn → Gas Fee tăng vọt

**Ví dụ thực tế:**
- Chuyển ETH đơn giản: ~21,000 gas
- Swap token trên Uniswap: ~100,000-200,000 gas
- Mint NFT: ~150,000-300,000 gas

Trong đợt bull run 2021, Gas Fee đôi khi lên đến **$100-200 cho một giao dịch**. Đây là vấn đề lớn nhất của Ethereum — chi phí cao.

**EIP-1559 (London Upgrade, 2021):**
Ethereum cải tiến cơ chế phí:
- **Base Fee** (phí cơ bản): Bị **đốt** (burn) — giảm nguồn cung ETH
- **Priority Fee** (tip): Trả thêm cho validator để ưu tiên

Kết quả: ETH trở thành **deflationary** (giảm phát) khi mạng hoạt động nhiều — lượng ETH đốt > lượng ETH phát hành mới.

---

### 5. Solidity — Ngôn ngữ viết Smart Contract

**Solidity** là ngôn ngữ lập trình chính để viết Smart Contract trên Ethereum. Cú pháp tương tự JavaScript/C++.

Bạn không cần học lập trình để đầu tư vào Ethereum, nhưng hiểu cơ bản giúp bạn đánh giá dự án tốt hơn.

**Ví dụ Smart Contract đơn giản (Token ERC-20):**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract MyToken {
    string public name = "My Token";
    string public symbol = "MTK";
    uint256 public totalSupply = 1000000;
    
    mapping(address => uint256) public balanceOf;
    
    constructor() {
        balanceOf[msg.sender] = totalSupply;
    }
    
    function transfer(address to, uint256 amount) public {
        require(balanceOf[msg.sender] >= amount, "Not enough tokens");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }
}
```

Chỉ với ~20 dòng code, bạn đã tạo ra một đồng token có thể giao dịch trên Ethereum. Đây là lý do tại sao hàng nghìn token "vô nghĩa" được tạo ra mỗi ngày.

**Token Standards (Tiêu chuẩn token):**
- **ERC-20**: Token fungible (có thể hoán đổi) — dùng cho altcoin, governance token
- **ERC-721**: Token non-fungible (NFT) — mỗi token là duy nhất
- **ERC-1155**: Kết hợp cả hai — dùng trong game blockchain

---

### 6. Ethereum 2.0 — The Merge

Ethereum ban đầu dùng **Proof of Work (PoW)** như Bitcoin — miners dùng GPU/ASIC để tính toán. Vấn đề: tốn điện khổng lồ, chậm, khó mở rộng.

**The Merge** (tháng 9/2022) là sự kiện lịch sử: Ethereum chuyển hoàn toàn sang **Proof of Stake (PoS)**.

**So sánh PoW vs PoS:**

| | Proof of Work | Proof of Stake |
|--|---------------|----------------|
| **Cơ chế** | Miners cạnh tranh tính toán | Validators stake ETH làm tài sản thế chấp |
| **Tiêu thụ điện** | Rất cao (~110 TWh/năm) | Giảm **99.95%** |
| **Bảo mật** | Tấn công bằng phần cứng | Tấn công bằng tài chính (cần 1/3 tổng stake) |
| **Phần thưởng** | Block reward cho miner | Staking reward cho validator |

**Staking ETH:**
- Cần tối thiểu **32 ETH** để trở thành validator
- Phần thưởng staking: ~3-5%/năm
- Nếu không đủ 32 ETH: có thể dùng Liquid Staking (Lido, Rocket Pool) với bất kỳ số lượng ETH nào

**Tác động của The Merge:**
- Giảm phát hành ETH mới ~90% (ít "inflation" hơn)
- Kết hợp EIP-1559 (đốt Base Fee) → ETH net deflationary trong giai đoạn mạng bận
- Mở đường cho các upgrade tiếp theo: Sharding, Proto-Danksharding

---

### 7. Layer 1 Competitors — Các đối thủ của Ethereum

Vì Ethereum có Gas Fee cao và tốc độ giới hạn, nhiều blockchain Layer 1 khác ra đời với tuyên bố "Ethereum killer":

**Solana (SOL)**
- Tốc độ: ~65,000 TPS (transactions per second) so với Ethereum ~15-30 TPS
- Gas Fee: cực thấp (~$0.0001/giao dịch)
- Cơ chế: Proof of History + Proof of Stake
- Nhược điểm: Đã có nhiều lần **downtime** (mạng ngừng hoạt động), ít decentralized hơn
- Ecosystem mạnh: DeFi (Jupiter, Raydium), NFT, memecoin

**BNB Chain (BSC)**
- Phát triển bởi Binance
- EVM-compatible, Gas Fee thấp
- Nhược điểm: Tập trung (21 validators, kiểm soát bởi Binance)
- Ecosystem: PancakeSwap, Venus Protocol

**Avalanche (AVAX)**
- 3 chain riêng biệt: X-Chain, C-Chain (EVM), P-Chain
- Tốc độ nhanh, finality sub-second
- Subnet: Mỗi dự án có thể tạo blockchain riêng
- Ecosystem: Trader Joe, Benqi

**Cardano (ADA)**
- Phát triển theo hướng học thuật, nhiều peer-reviewed research
- Proof of Stake (Ouroboros) từ đầu
- Tiến độ chậm nhưng chắc chắn
- Ecosystem còn đang phát triển

**Near Protocol (NEAR)**
- Sharding từ đầu (Nightshade sharding)
- UX thân thiện, tên tài khoản dễ nhớ (VD: alice.near)
- Aurora: EVM layer trên Near

**Sui & Aptos**
- Thế hệ blockchain mới nhất (2022-2023)
- Ngôn ngữ Move (an toàn hơn Solidity)
- Founder từ cựu team Diem (Facebook blockchain)
- Throughput cực cao, nhưng ecosystem còn non trẻ

**"Blockchain Trilemma" (Bộ ba bất khả thi):**

Mọi blockchain đều phải cân bằng 3 yếu tố:
```
         Bảo mật (Security)
              △
             / \
            /   \
           /     \
          /       \
Phân tán ─────────── Mở rộng
(Decentralization)  (Scalability)
```
Không blockchain nào có thể tối ưu cả 3 cùng lúc. Ethereum chọn ưu tiên Bảo mật + Phân tán, hy sinh Scalability (giải quyết qua Layer 2).

---

### 8. Layer 2 — Giải pháp mở rộng của Ethereum

**Layer 2** (L2) là các blockchain chạy "bên trên" Ethereum, xử lý giao dịch nhanh/rẻ rồi gửi kết quả về L1 (Ethereum) để đảm bảo bảo mật.

Các L2 lớn nhất:
- **Arbitrum**: L2 lớn nhất theo TVL, dùng Optimistic Rollup
- **Optimism**: L2 lớn thứ 2, OP Stack được nhiều chain khác dùng
- **Base**: L2 của Coinbase, xây trên OP Stack
- **zkSync / StarkNet**: Dùng ZK Rollup (bảo mật toán học cao hơn)
- **Polygon**: EVM-compatible sidechain + đang phát triển zkEVM

Với L2, phí giao dịch giảm từ $10-100 xuống còn $0.01-0.1.

---

### 9. ETH là tài sản đầu tư như thế nào?

**Use cases của ETH:**
1. **Gas payment**: Mọi giao dịch trên Ethereum đều cần ETH để trả phí
2. **Staking**: Stake ETH để nhận ~3-5%/năm
3. **Collateral**: Dùng ETH làm tài sản thế chấp trong DeFi
4. **Store of Value**: Một số người coi ETH như "digital silver"

**Mô hình "Ultra Sound Money":**
Sau The Merge + EIP-1559, ETH có thể deflationary:
- Phát hành mới: ~600,000 ETH/năm (staking rewards)
- Đốt: Phụ thuộc vào hoạt động mạng
- Trong giai đoạn mạng bận (2021 bull run): Đốt > Phát hành → Nguồn cung giảm

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **Ethereum = "World Computer"**: Không chỉ chuyển tiền mà còn chạy chương trình phi tập trung
2. **Smart Contract**: Code tự động thực thi, không cần trung gian, trustless
3. **EVM**: Máy ảo chạy Smart Contract, đã trở thành tiêu chuẩn ngành
4. **Gas Fee**: Chi phí tính toán, vấn đề lớn nhất của Ethereum (đang được giải quyết qua L2)
5. **The Merge**: Chuyển PoW → PoS, giảm 99.95% tiêu thụ điện
6. **Blockchain Trilemma**: Không chain nào tối ưu được cả 3 — Bảo mật, Phân tán, Mở rộng
7. **Layer 2**: Giải pháp mở rộng Ethereum, giảm phí xuống còn vài cent

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| Smart Contract | Hợp đồng thông minh | Code tự động thực thi trên blockchain khi đủ điều kiện |
| EVM | Máy ảo Ethereum | Engine chạy Smart Contract trên Ethereum |
| Gas Fee | Phí gas | Chi phí tính toán cho giao dịch trên Ethereum |
| Gwei | Gwei | Đơn vị nhỏ của ETH (1 ETH = 10^9 Gwei) |
| Solidity | Solidity | Ngôn ngữ lập trình viết Smart Contract |
| ERC-20 | Tiêu chuẩn token | Chuẩn tạo token fungible trên Ethereum |
| ERC-721 | Tiêu chuẩn NFT | Chuẩn tạo token non-fungible (NFT) |
| The Merge | Sự hợp nhất | Sự kiện Ethereum chuyển từ PoW sang PoS (9/2022) |
| Proof of Stake | Bằng chứng cổ phần | Cơ chế đồng thuận dựa trên tài sản thế chấp |
| Staking | Staking | Khóa ETH để trở thành validator và nhận phần thưởng |
| Layer 2 | Lớp 2 | Blockchain chạy trên Ethereum để giảm phí/tăng tốc |
| Rollup | Rollup | Công nghệ L2: gom nhiều giao dịch → gửi về L1 |
| Blockchain Trilemma | Bộ ba bất khả thi | Security + Decentralization + Scalability không thể tối ưu cả 3 |
| dApp | Ứng dụng phi tập trung | Ứng dụng chạy trên Smart Contract |
| Finality | Tính hoàn kết | Giao dịch được xác nhận không thể đảo ngược |

---

## Bài học tiếp theo

**Ngày 55** sẽ khám phá toàn bộ **hệ sinh thái Crypto** được xây dựng trên nền tảng Ethereum và các blockchain khác: **DeFi** (tài chính phi tập trung), **NFT** (token không thể thay thế), **DAO** (tổ chức tự trị phi tập trung), và **GameFi/SocialFi** — những lĩnh vực đang định nghĩa lại cách con người tổ chức tài chính và xã hội.
