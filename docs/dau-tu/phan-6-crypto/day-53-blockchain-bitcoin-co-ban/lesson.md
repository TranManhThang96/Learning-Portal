# Ngày 53: Blockchain & Bitcoin Cơ bản

## Mục tiêu học tập
- [ ] Hiểu Blockchain là gì và tại sao nó mang tính cách mạng
- [ ] Nắm vững các khái niệm cốt lõi: Decentralization, Distributed Ledger, Immutability
- [ ] Hiểu Bitcoin ra đời như thế nào và tại sao được gọi là "Digital Gold"
- [ ] Phân biệt Proof of Work (PoW) và Proof of Stake (PoS)
- [ ] Hiểu Mining và Validators hoạt động như thế nào

---

## Nội dung bài giảng

### 1. Tại sao Blockchain ra đời?

Để hiểu Blockchain, hãy bắt đầu từ một vấn đề rất thực tế:

**Vấn đề: Làm thế nào để chuyển tiền mà không cần ngân hàng?**

Khi bạn chuyển 10 triệu đồng cho bạn bè qua ngân hàng:
1. Bạn yêu cầu ngân hàng A trừ 10 triệu từ tài khoản bạn
2. Ngân hàng A ghi nhận giao dịch vào sổ cái (ledger) của họ
3. Ngân hàng A thông báo cho ngân hàng B
4. Ngân hàng B cộng 10 triệu vào tài khoản bạn bè

Vấn đề ở đây là gì?
- **Tập trung hóa (Centralization)**: Ngân hàng kiểm soát toàn bộ
- **Tin tưởng bên thứ ba**: Bạn phải tin vào ngân hàng
- **Chi phí**: Phí giao dịch, phí chuyển đổi ngoại tệ
- **Kiểm soát**: Ngân hàng có thể đóng băng tài khoản, từ chối giao dịch
- **Rào cản địa lý**: Chuyển tiền quốc tế mất 3-5 ngày, phí cao

**Năm 2008, một người (hoặc nhóm người) bí ẩn có tên Satoshi Nakamoto đặt câu hỏi:** *"Có thể tạo ra hệ thống thanh toán điện tử ngang hàng (peer-to-peer) mà không cần bên thứ ba tin cậy không?"*

Câu trả lời là Bitcoin — và công nghệ nền tảng của nó là Blockchain.

---

### 2. Blockchain là gì?

**Blockchain** (chuỗi khối) là một loại cơ sở dữ liệu đặc biệt với các tính chất sau:

**Hình dung đơn giản:**

Hãy tưởng tượng một cuốn sổ cái chứa lịch sử TẤT CẢ giao dịch từ trước đến nay:
- Không phải chỉ một người giữ sổ này
- Hàng nghìn người trên thế giới mỗi người giữ một bản sao GIỐNG HỆT NHAU
- Khi có giao dịch mới, tất cả mọi người phải đồng ý và cập nhật đồng thời
- Một khi đã ghi vào sổ, không ai có thể xóa hoặc sửa được

**Đây chính là Blockchain!**

#### Cấu trúc của Blockchain:

```
BLOCK 1              BLOCK 2              BLOCK 3
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ Hash trước: │      │ Hash trước: │      │ Hash trước: │
│ 0000000     │ ──→  │ A3F9B2...   │ ──→  │ 7D2C1E...   │
├─────────────┤      ├─────────────┤      ├─────────────┤
│ Giao dịch:  │      │ Giao dịch:  │      │ Giao dịch:  │
│ A → B: 1BTC │      │ C → D: 2BTC │      │ E → F: 0.5BTC│
│ ...         │      │ ...         │      │ ...         │
├─────────────┤      ├─────────────┤      ├─────────────┤
│ Hash của    │      │ Hash của    │      │ Hash của    │
│ Block 1:    │      │ Block 2:    │      │ Block 3:    │
│ A3F9B2...   │      │ 7D2C1E...   │      │ 9K4M5N...   │
└─────────────┘      └─────────────┘      └─────────────┘
```

**Giải thích:**
- Mỗi **Block** (khối) chứa: danh sách giao dịch + mã hash của block trước + mã hash của chính nó
- **Hash**: Một đoạn mã duy nhất được tính toán từ nội dung block. Nếu thay đổi BẤT KỲ thứ gì trong block, hash thay đổi hoàn toàn
- Vì block sau chứa hash của block trước → Nếu sửa block 1, hash của nó thay đổi → Block 2 không còn hợp lệ → Block 3 không còn hợp lệ → Toàn bộ chuỗi bị phá vỡ

Đây chính là **Immutability** (tính bất biến) — một khi ghi vào blockchain, không thể sửa mà không bị phát hiện.

---

### 3. Ba tính chất cốt lõi của Blockchain

#### a. Distributed Ledger (Sổ cái phân tán)

Không phải một máy chủ trung tâm giữ dữ liệu. Hàng nghìn **Node** (máy tính tham gia mạng) trên toàn thế giới đều giữ bản sao đầy đủ của blockchain.

**Ví dụ:** Bitcoin có hàng chục nghìn node được vận hành độc lập trên toàn thế giới. Tuy nhiên, tấn công Bitcoin không đơn giản là "kiểm soát hơn 50% số node". Với Proof of Work, rủi ro nổi tiếng là **51% attack**: kẻ tấn công cần kiểm soát phần lớn **hash power** (sức mạnh tính toán đào block) để cố gắng đảo ngược giao dịch gần đây hoặc kiểm duyệt giao dịch. Ngay cả khi có nhiều hash power, block vẫn phải tuân thủ quy tắc đồng thuận và full node có thể từ chối block không hợp lệ.

#### b. Decentralization (Phi tập trung hóa)

Không có cơ quan trung ương nào kiểm soát:
- Không có CEO của Bitcoin
- Không có chính phủ nào có thể tắt Bitcoin
- Bất kỳ ai cũng có thể tham gia mạng lưới

**So sánh:**

| | Hệ thống truyền thống | Blockchain |
|---|---|---|
| Ai kiểm soát? | Ngân hàng, Công ty | Không ai (hoặc tất cả mọi người) |
| Điểm thất bại | Một (server trung tâm) | Phải kiểm soát phần lớn hash power và vẫn phải tạo block hợp lệ |
| Ai có thể truy cập? | Phải được cấp phép | Ai cũng có thể |
| Ai có thể kiểm duyệt? | Tổ chức trung tâm | Không ai |

#### c. Immutability (Tính bất biến)

Một khi giao dịch được xác nhận và ghi vào blockchain, nó không thể bị xóa hoặc sửa đổi. Điều này đảm bảo:
- Lịch sử giao dịch minh bạch tuyệt đối
- Không thể "làm giả" lịch sử
- Ai cũng có thể kiểm chứng bất kỳ giao dịch nào

---

### 4. Bitcoin — "Digital Gold" của thế kỷ 21

**Bitcoin (BTC)** là đồng tiền điện tử đầu tiên, ra đời ngày 3/1/2009 khi Satoshi Nakamoto khai thác block đầu tiên (Genesis Block).

**Tại sao Bitcoin được gọi là "Digital Gold"?**

| Đặc điểm | Vàng | Bitcoin |
|----------|------|---------|
| Nguồn cung | Hữu hạn (khai thác được ~197,000 tấn) | Hữu hạn (tối đa 21 triệu BTC) |
| Khai thác | Mining vàng vật lý | Mining máy tính |
| Lưu trữ giá trị | Lịch sử hàng nghìn năm | Lịch sử 15+ năm |
| Phân chia được | Khó (gram) | Dễ (1 BTC = 100 triệu Satoshi) |
| Vận chuyển | Nặng, khó di chuyển | Tức thì qua internet |
| Kiểm chứng | Cần thiết bị | Blockchain - bất kỳ ai cũng kiểm tra được |
| Kiểm duyệt được? | Có thể tịch thu vật lý | Không (nếu giữ Private Key đúng cách) |

**Scarcity (Sự khan hiếm) — Yếu tố giá trị cốt lõi:**

Bitcoin được lập trình để tổng cung tối đa là **21,000,000 BTC**. Không bao giờ được tạo thêm. Tính đến nay, đã có khoảng 19.5 triệu BTC được khai thác (mined). Khoảng 1.5 triệu BTC còn lại sẽ được khai thác cho đến năm 2140.

Ngoài ra, ước tính khoảng 3-4 triệu BTC đã bị mất mãi mãi (mất Private Key, chủ sở hữu qua đời không để lại key, v.v.). Vì vậy, **lượng BTC thực sự lưu thông** còn ít hơn con số 21 triệu.

---

### 5. Satoshi Nakamoto — Bí ẩn lớn nhất trong Blockchain

**Satoshi Nakamoto** là tên người tạo ra Bitcoin. Có thể là một người, có thể là một nhóm người. Không ai biết danh tính thực sự của Satoshi.

**Timeline quan trọng:**
- **31/10/2008**: Satoshi đăng Bitcoin Whitepaper: *"Bitcoin: A Peer-to-Peer Electronic Cash System"*
- **03/01/2009**: Bitcoin Genesis Block được đào — Satoshi nhận 50 BTC đầu tiên
- **Tháng 10/2010**: Satoshi dần rút lui khỏi dự án
- **2011**: Satoshi hoàn toàn biến mất, không còn liên lạc

**Satoshi sở hữu khoảng 1.1 triệu BTC** (không bao giờ di chuyển kể từ khi được đào) — tại thời điểm BTC đỉnh ~$69,000 (tháng 11/2021), đây là khối tài sản ~$76 tỷ USD.

Bí ẩn về danh tính Satoshi đến nay vẫn chưa được giải đáp.

---

### 6. Proof of Work (PoW) — Cơ chế Bitcoin

**Proof of Work** (Bằng chứng công việc) là cơ chế đồng thuận (consensus mechanism) của Bitcoin.

**Vấn đề cần giải quyết:** Khi hàng nghìn node muốn thêm block mới vào blockchain, ai được phép thêm? Làm sao đảm bảo không có ai gian lận?

**Giải pháp PoW:**

Để thêm một block mới, node phải giải một bài toán toán học cực kỳ khó (nhưng dễ kiểm chứng đáp án):

**Bài toán:** Tìm một số (Nonce) sao cho khi kết hợp với dữ liệu block, Hash kết quả bắt đầu bằng một số lượng số 0 nhất định.

Ví dụ:
```
Hash(Block Data + Nonce = 000000000000A3F9B2...)
                          ↑ 12 số 0 đầu tiên
```

Không có cách nào tìm Nonce này ngoài việc thử từng số một (billions of times per second). Đây là "Proof of Work" — bằng chứng rằng bạn đã bỏ ra sức mạnh tính toán (computing power).

**Mining (Đào coin):**
- **Miner** (người đào) là những node chạy phần cứng chuyên dụng (ASIC) để giải bài toán này
- Miner nào tìm ra đáp án đầu tiên → Được thêm block mới → Nhận phần thưởng Block Reward
- Hiện tại (sau Halving 2024): **3.125 BTC/block** + phí giao dịch
- Cứ 10 phút, một block mới được thêm vào

**Mining Difficulty (Độ khó đào):**
- Mạng lưới tự động điều chỉnh độ khó mỗi 2016 blocks (~2 tuần)
- Nếu nhiều miner tham gia hơn → Độ khó tăng → Vẫn trung bình 10 phút/block
- Đây là thiết kế thông minh đảm bảo tốc độ phát hành BTC ổn định

**Ưu điểm PoW:**
- Bảo mật cao nhất từ trước đến nay — Bitcoin chưa bao giờ bị hack
- Phi tập trung thực sự
- Đã được chứng minh qua 15+ năm

**Nhược điểm PoW:**
- Tiêu thụ điện khổng lồ: Bitcoin dùng điện tương đương cả nước Argentina
- Chậm: ~7 giao dịch/giây (so với Visa: ~24,000 TPS)
- Phần cứng ASIC đắt tiền, chỉ tập đoàn lớn mới đủ khả năng

---

### 7. Proof of Stake (PoS) — Cơ chế Thế hệ Mới

**Proof of Stake** (Bằng chứng cổ phần) là cơ chế đồng thuận của Ethereum (sau "The Merge" 2022) và nhiều blockchain thế hệ mới.

**Cơ chế hoạt động:**

Thay vì cạnh tranh bằng sức mạnh tính toán, Validators (người xác nhận) phải **Stake** (khóa) một lượng coin nhất định làm "tài sản thế chấp":
- Ethereum: Tối thiểu 32 ETH (~$80,000+) để trở thành Validator
- Validator được chọn ngẫu nhiên để thêm block (xác suất tỷ lệ thuận với lượng stake)
- Nếu Validator hành xử gian lận → Bị **Slash** (mất một phần coin đã stake)

**So sánh PoW vs PoS:**

| Tiêu chí | Proof of Work | Proof of Stake |
|----------|--------------|----------------|
| Năng lượng | Rất cao (điện) | Thấp hơn 99%+ |
| Bảo mật | Cực cao (Bitcoin) | Cao (lý thuyết khác nhau) |
| Phi tập trung | Tốt (nhưng bị ảnh hưởng bởi ASIC pools) | Tranh cãi (tiền nhiều = quyền nhiều) |
| Tốc độ | Chậm (~7 TPS Bitcoin) | Nhanh hơn nhiều |
| Ví dụ | Bitcoin, Litecoin | Ethereum, Solana, Cardano |
| Rào cản tham gia | Phần cứng ASIC | Stake coin |

**Ethereum Merge (September 2022):**

Ethereum chuyển từ PoW sang PoS vào ngày 15/9/2022 — một sự kiện lịch sử trong crypto. Kết quả:
- Tiêu thụ năng lượng giảm 99.95%
- Issuance rate (tốc độ phát hành ETH mới) giảm mạnh
- Ethereum trở thành "deflationary" trong nhiều giai đoạn (nhiều ETH bị burn hơn được phát hành)

---

### 8. Validators và Staking

**Validators** là những node trong mạng PoS có nhiệm vụ:
1. Xác nhận giao dịch
2. Đề xuất block mới
3. Vote cho block của validator khác

**Staking** là hành động khóa (lock) coin để tham gia làm Validator hoặc delegate cho Validator:
- **Solo Staking**: Tự chạy node, cần 32 ETH
- **Staking Pool**: Gộp ETH với người khác (VD: Lido, Rocket Pool)
- **CEX Staking**: Gửi vào sàn giao dịch (Binance, Coinbase) để nhận lãi

**Staking Rewards (Phần thưởng Staking):**
- ETH staking: ~3-5% APY (thay đổi theo điều kiện mạng)
- Không phải "lãi suất ngân hàng" — đây là phần thưởng cho việc bảo vệ mạng lưới

---

### 9. Hash và Cryptography — Công nghệ Nền tảng

**Hash Function** (Hàm băm) là công nghệ mật mã học nền tảng của Blockchain:

- Nhập bất kỳ dữ liệu nào → Ra output (hash) có độ dài cố định
- Cùng input → Luôn cùng output (deterministic)
- Thay đổi 1 bit input → Output thay đổi hoàn toàn
- Không thể tính ngược (one-way function)

**Ví dụ SHA-256 (thuật toán Bitcoin dùng):**
```
SHA256("Hello World") = 
a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e

SHA256("Hello World!") = 
7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069
```

Chỉ thêm dấu "!" → Hash hoàn toàn khác!

**Public Key và Private Key:**

Bitcoin sử dụng mật mã học bất đối xứng (Asymmetric Cryptography):
- **Private Key** (Khóa riêng tư): Như mật khẩu tối thượng, phải giữ bí mật tuyệt đối
- **Public Key** (Khóa công khai): Được tính toán từ Private Key, chia sẻ được
- **Bitcoin Address**: Được tính toán từ Public Key, dùng để nhận BTC

**Ví dụ giao dịch:**
- Bạn muốn gửi 0.1 BTC cho bạn bè
- Bạn dùng Private Key để ký (sign) giao dịch → Chứng minh bạn là chủ sở hữu
- Mạng lưới dùng Public Key để xác nhận chữ ký là hợp lệ
- Giao dịch được broadcast ra toàn mạng và ghi vào blockchain

**"Not your keys, not your coins"** — Nếu bạn không giữ Private Key, bạn không thực sự sở hữu Bitcoin. Khi để Bitcoin trên sàn giao dịch (CEX), sàn giữ Private Key, không phải bạn.

---

### 10. Bitcoin trong thực tế — Con số Biết nói

**Giá và Market Cap:**
- Giá cao nhất lịch sử: ~$108,000/BTC (tháng 12/2024)
- Market Cap đỉnh: ~$2 nghìn tỷ USD
- Bitcoin thường chiếm 40-60% tổng market cap của toàn bộ crypto market

**Ứng dụng thực tế:**
- **Store of Value** (Lưu trữ giá trị): Người ở các nước có lạm phát cao (Venezuela, Argentina, Zimbabwe) dùng BTC để bảo toàn tài sản
- **Remittance** (Chuyển tiền quốc tế): Nhanh hơn, rẻ hơn Western Union
- **El Salvador**: Quốc gia đầu tiên trên thế giới công nhận Bitcoin là tiền tệ hợp pháp (2021)
- **Institutional Adoption**: BlackRock, Fidelity, Goldman Sachs đều có sản phẩm Bitcoin ETF hoặc exposure

**Bitcoin ETF (2024):**
Tháng 1/2024, SEC Mỹ chấp thuận Bitcoin Spot ETF — cột mốc lịch sử giúp nhà đầu tư truyền thống (tổ chức, quỹ hưu trí) tiếp cận Bitcoin mà không cần giữ coin trực tiếp. Đây là sự kiện được nhiều người coi là "Game changer" của Bitcoin.

---

### 11. Rủi ro và Giới hạn của Bitcoin

**Volatility (Biến động giá):**
- Bitcoin từng giảm 80-85% từ đỉnh trong các bear market (2018, 2022)
- Từ $69,000 (tháng 11/2021) xuống $15,500 (tháng 11/2022) — giảm 77%
- Không phù hợp cho tiền tiết kiệm ngắn hạn cần dùng

**Regulatory Risk (Rủi ro pháp lý):**
- Trung Quốc cấm Bitcoin nhiều lần
- Nhiều quốc gia vẫn chưa rõ lập trường pháp lý
- Taxation ngày càng chặt chẽ

**Scalability (Khả năng mở rộng):**
- 7 TPS là quá chậm cho thanh toán toàn cầu
- Lightning Network (Layer 2 solution) đang phát triển để giải quyết
- Visa xử lý 24,000 TPS

**Environmental Concerns:**
- PoW tiêu thụ điện lớn — vấn đề môi trường đang được tranh luận
- Một số miner dùng năng lượng tái tạo, một số không

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **Blockchain** giải quyết vấn đề giao dịch không cần bên thứ ba tin cậy thông qua ba tính chất: Distributed Ledger, Decentralization, Immutability
2. **Hash function** là nền tảng kỹ thuật — thay đổi 1 bit dữ liệu → Hash hoàn toàn khác → Chuỗi blockchain bị phá vỡ → Không thể gian lận
3. **Bitcoin** = Digital Gold: Nguồn cung tối đa 21 triệu, phi tập trung, không thể kiểm duyệt
4. **Satoshi Nakamoto** — Người tạo Bitcoin, danh tính vẫn là bí ẩn lớn nhất lịch sử crypto
5. **Proof of Work** (Bitcoin): Bảo mật cao nhất, tiêu thụ điện lớn, chậm
6. **Proof of Stake** (Ethereum, nhiều altcoin): Tiết kiệm năng lượng hơn 99%, nhanh hơn, nhưng có tranh luận về phi tập trung
7. **"Not your keys, not your coins"** — Giữ Private Key = Thực sự sở hữu Bitcoin
8. **Bitcoin Halving** xảy ra mỗi ~4 năm: Block reward giảm 50% → Supply giảm → Lịch sử thường tạo bull market

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|-------------------|-----------------|
| Blockchain | Chuỗi khối | Cơ sở dữ liệu phân tán, bất biến |
| Distributed Ledger | Sổ cái phân tán | Nhiều node cùng giữ bản sao sổ cái |
| Decentralization | Phi tập trung | Không có cơ quan trung ương kiểm soát |
| Immutability | Tính bất biến | Dữ liệu đã ghi không thể sửa |
| Node | Nút mạng | Máy tính tham gia mạng blockchain |
| Hash | Mã băm | Đoạn mã duy nhất đại diện cho dữ liệu |
| Proof of Work (PoW) | Bằng chứng công việc | Cơ chế đồng thuận dùng sức mạnh tính toán |
| Proof of Stake (PoS) | Bằng chứng cổ phần | Cơ chế đồng thuận dùng coin stake |
| Mining | Đào coin | Quá trình tạo block mới trong PoW |
| Validator | Người xác nhận | Node tham gia đồng thuận trong PoS |
| Staking | Đặt cọc coin | Khóa coin để tham gia PoS |
| Satoshi | Satoshi | Đơn vị nhỏ nhất của Bitcoin (1 BTC = 100M Satoshi) |
| Private Key | Khóa riêng tư | Mật khẩu tuyệt đối để kiểm soát Bitcoin |
| Public Key | Khóa công khai | Dùng để xác nhận chữ ký giao dịch |
| Block Reward | Phần thưởng block | BTC mới được tạo ra khi đào thành công block |
| Halving | Sự kiện giảm phần thưởng | Block reward giảm 50% mỗi 210,000 blocks |
| Genesis Block | Block khởi nguồn | Block đầu tiên trong blockchain Bitcoin |

---

## Bài học tiếp theo

**Ngày 54 — Ethereum & Smart Contracts:** Bitcoin giải quyết bài toán "tiền số phi tập trung". Nhưng Vitalik Buterin hỏi: *"Nếu Blockchain không chỉ xử lý tiền mà còn thực thi bất kỳ hợp đồng nào thì sao?"* Ngày mai chúng ta sẽ khám phá Ethereum — "thế giới máy tính phi tập trung", Smart Contracts, dApps và tại sao Ethereum được coi là nền tảng của Web3.
