# Ngày 34: Margin Trading, Short Selling & Quyền Cổ Đông

## Mục tiêu học tập
- [ ] Hiểu Margin Trading (giao dịch ký quỹ) là gì và cơ chế hoạt động
- [ ] Nắm rõ rủi ro của Leverage (đòn bẩy) và kịch bản Margin Call
- [ ] Hiểu Short Selling (bán khống) — cách kiếm tiền khi thị trường giảm
- [ ] Biết quyền lợi của cổ đông: Dividend, Voting Rights, Stock Split
- [ ] Áp dụng quy tắc an toàn khi sử dụng margin

---

## Nội dung bài giảng

### 1. Margin Trading (Giao Dịch Ký Quỹ) Là Gì?

Hãy tưởng tượng bạn muốn mua một căn nhà trị giá 1 tỷ đồng, nhưng bạn chỉ có 300 triệu. Bạn vay ngân hàng 700 triệu để mua. Đây chính xác là cách **Margin Trading** hoạt động trong chứng khoán.

**Margin Trading** là hình thức giao dịch mà bạn vay tiền từ công ty chứng khoán (broker) để mua cổ phiếu với số lượng lớn hơn số tiền bạn thực sự có.

#### Cơ chế hoạt động:

Giả sử bạn có **100 triệu VND** và muốn mua cổ phiếu VCB:

| Kịch bản | Vốn của bạn | Vay margin | Tổng mua được | Tỷ lệ margin |
|----------|-------------|------------|---------------|--------------|
| Không dùng margin | 100 triệu | 0 | 100 triệu VND cổ phiếu | 1:1 |
| Margin 1:2 | 100 triệu | 100 triệu | 200 triệu VND cổ phiếu | 1:2 |
| Margin 1:3 | 100 triệu | 200 triệu | 300 triệu VND cổ phiếu | 1:3 |

Ở Việt Nam, tỷ lệ margin thông thường là **1:1** hoặc **1:2** (tức là vay tối đa bằng vốn bạn có). Tại các sàn quốc tế và Forex, leverage có thể lên đến 1:100 hoặc 1:500.

#### Chi phí của margin:
- **Lãi suất vay margin**: Thường 10-14%/năm tại Việt Nam
- Ví dụ: Vay 100 triệu trong 30 ngày = 100 triệu × 12%/365 × 30 ≈ **985,000 VND** tiền lãi

---

### 2. Leverage (Đòn Bẩy) — Con Dao Hai Lưỡi

**Leverage** khuếch đại cả lợi nhuận lẫn thua lỗ. Đây là lý do nó được gọi là "con dao hai lưỡi."

#### Ví dụ thực tế:

Bạn mua cổ phiếu FPT tại 100,000 VND/cổ phiếu.

**Trường hợp 1 — Cổ phiếu tăng 20% (lên 120,000 VND):**

| | Không margin | Có margin 1:2 |
|--|--|--|
| Vốn bỏ ra | 100 triệu | 100 triệu |
| Tổng mua | 100 triệu | 200 triệu |
| Lợi nhuận | +20 triệu (20%) | +40 triệu (40%) |

→ Margin giúp bạn **gấp đôi lợi nhuận**!

**Trường hợp 2 — Cổ phiếu giảm 20% (xuống 80,000 VND):**

| | Không margin | Có margin 1:2 |
|--|--|--|
| Vốn bỏ ra | 100 triệu | 100 triệu |
| Tổng mua | 100 triệu | 200 triệu |
| Thua lỗ | -20 triệu (20%) | -40 triệu (40%) |

→ Margin cũng **gấp đôi thua lỗ**! Bạn mất 40% vốn khi cổ phiếu chỉ giảm 20%.

---

### 3. Margin Call — Kịch Bản Ác Mộng

**Margin Call** xảy ra khi tài khoản của bạn mất giá đến mức công ty chứng khoán yêu cầu bạn nộp thêm tiền hoặc họ sẽ tự động bán cổ phiếu của bạn để thu hồi nợ.

#### Cách tính ngưỡng Margin Call:

Mỗi công ty chứng khoán có tỷ lệ duy trì margin (maintenance margin ratio) khác nhau, thường là **40-50%**.

Ví dụ:
- Bạn có 100 triệu, vay thêm 100 triệu → mua 200 triệu cổ phiếu
- Ngưỡng duy trì: 40%
- **Giá trị tài khoản tối thiểu = Nợ ÷ (1 - Tỷ lệ duy trì) = 100 triệu ÷ (1 - 0.4) = 166.7 triệu**
- Tức là khi danh mục giảm từ 200 triệu xuống còn **166.7 triệu** (giảm ~16.7%), bạn sẽ nhận Margin Call

#### Vòng xoáy chết chóc của Margin Call:

```
Thị trường giảm
      ↓
Tài khoản xuống dưới ngưỡng duy trì
      ↓
Margin Call — broker yêu cầu nộp thêm tiền
      ↓
Nếu không nộp → Broker tự động bán cổ phiếu
      ↓
Bán tháo làm giá giảm thêm
      ↓
Margin Call tiếp theo...
```

> **Bài học thực tế**: Trong đợt giảm mạnh tháng 3/2020 (COVID crash) và tháng 4-5/2022 trên thị trường Việt Nam, hàng nghìn nhà đầu tư bị force sell (bán cưỡng chế) do margin, khiến họ không kịp phục hồi khi thị trường đảo chiều tăng trở lại.

---

### 4. Short Selling (Bán Khống) — Kiếm Tiền Khi Thị Trường Giảm

**Short Selling** là bán cổ phiếu mà bạn **chưa sở hữu**, bằng cách mượn cổ phiếu từ broker, bán ra, sau đó mua lại với giá thấp hơn để trả lại.

#### Cơ chế Short Selling:

```
Bước 1: Mượn 100 cổ phiếu HPG từ broker (giá 40,000/cp)
Bước 2: Bán ngay 100 cp → thu về 4,000,000 VND
Bước 3: Chờ giá giảm xuống 32,000/cp
Bước 4: Mua lại 100 cp → chi 3,200,000 VND
Bước 5: Trả lại 100 cp cho broker
Lợi nhuận: 4,000,000 - 3,200,000 = 800,000 VND (trừ phí)
```

#### Rủi ro đặc biệt của Short Selling:

**Lợi nhuận tối đa = 100%** (nếu cổ phiếu về 0)
**Thua lỗ = KHÔNG GIỚI HẠN** (cổ phiếu có thể tăng mãi mãi)

Ví dụ kinh điển: Những nhà đầu tư short GameStop (GME) năm 2021 đã bị cộng đồng Reddit (WallStreetBets) "squeeze" — giá cổ phiếu tăng từ $20 lên $480 trong vài ngày. Những người bán khống thua lỗ hàng tỷ USD.

> **Lưu ý về thị trường Việt Nam**: Bán khống chính thức (covered short selling) chưa phổ biến trên sàn Việt Nam. Các nhà đầu tư Việt thường dùng **hợp đồng tương lai VN30 (HOSE derivatives)** hoặc **chứng quyền có bảo đảm (covered warrants)** để kiếm tiền khi thị trường giảm.

---

### 5. Quyền Lợi Của Cổ Đông

Khi bạn mua cổ phiếu, bạn trở thành chủ sở hữu một phần doanh nghiệp và có các quyền lợi sau:

#### 5.1 Dividend (Cổ Tức)

**Dividend** là phần lợi nhuận mà công ty chia sẻ với cổ đông.

**Hai hình thức cổ tức:**
- **Cổ tức tiền mặt (Cash Dividend)**: Công ty trả tiền mặt vào tài khoản của bạn
- **Cổ tức cổ phiếu (Stock Dividend)**: Công ty phát hành thêm cổ phiếu thưởng

**Các ngày quan trọng cần biết:**
```
Ngày công bố (Declaration Date): Công ty thông báo sẽ trả cổ tức
        ↓
Ngày chốt danh sách (Record Date): Ai sở hữu CP trước ngày này được nhận
        ↓
Ngày giao dịch không hưởng quyền (Ex-Dividend Date): 
Mua sau ngày này sẽ KHÔNG được nhận cổ tức kỳ này
        ↓
Ngày thanh toán (Payment Date): Tiền cổ tức được chuyển vào tài khoản
```

**Ví dụ thực tế — VNM (Vinamilk):**
- VNM thường trả cổ tức tiền mặt 2 lần/năm
- Tỷ lệ cổ tức khoảng 30-40% mệnh giá (3,000-4,000 VND/cổ phiếu)
- Với giá cổ phiếu ~65,000 VND → **Dividend Yield (tỷ suất cổ tức) ≈ 5-6%/năm**

**Dividend Yield = (Cổ tức hàng năm ÷ Giá cổ phiếu hiện tại) × 100%**

#### 5.2 Voting Rights (Quyền Biểu Quyết)

- Mỗi cổ phiếu phổ thông = 1 phiếu bầu
- Tham gia Đại hội đồng cổ đông (ĐHĐCĐ) hàng năm
- Bỏ phiếu về: Bầu Hội đồng quản trị, phê duyệt chiến lược, sáp nhập M&A...

> Với nhà đầu tư nhỏ lẻ, quyền biểu quyết ít quan trọng (bạn nắm 0.001% cổ phần thì phiếu bầu không ảnh hưởng nhiều). Nhưng với quỹ đầu tư lớn, đây là công cụ quyền lực.

#### 5.3 Stock Split (Tách Cổ Phiếu)

**Stock Split** là khi công ty chia nhỏ cổ phiếu để giảm giá, tăng tính thanh khoản.

**Ví dụ Split 2:1:**
- Bạn có 100 cổ phiếu giá 200,000 VND/cp
- Sau split: bạn có **200 cổ phiếu** giá **100,000 VND/cp**
- Tổng giá trị **không đổi**: 20,000,000 VND

**Ví dụ thực tế nổi tiếng:**
- Apple đã split 7:1 (2014) và 4:1 (2020) để cổ phiếu dễ tiếp cận hơn
- Trên HOSE: nhiều công ty Việt thường trả cổ tức bằng cổ phiếu thay vì tách

#### 5.4 Buyback (Mua Lại Cổ Phiếu)

Khi công ty dùng tiền mặt mua lại cổ phiếu của chính họ:
- Giảm số lượng cổ phiếu lưu hành
- EPS (lợi nhuận trên mỗi cổ phiếu) tăng
- Thường làm giá cổ phiếu tăng
- Đây là cách Buffett ưa thích thay vì trả cổ tức tiền mặt

#### 5.5 Rights Issue (Phát Hành Quyền Mua)

Công ty phát hành thêm cổ phiếu mới và cho cổ đông hiện tại quyền ưu tiên mua với giá ưu đãi. Bạn có thể:
1. **Thực hiện quyền**: Mua thêm cổ phiếu với giá ưu đãi
2. **Bán quyền**: Bán quyền mua cho người khác
3. **Không làm gì**: Cổ phần của bạn bị pha loãng (dilution)

---

### 6. Quy Tắc An Toàn Khi Dùng Margin

Dù margin là công cụ mạnh, hầu hết chuyên gia khuyên người mới **KHÔNG sử dụng margin** trong ít nhất 2-3 năm đầu. Nếu bạn vẫn muốn dùng:

**6 quy tắc bất khả xâm phạm:**

1. **Chỉ dùng margin tối đa 30-50% vốn**: Đừng bao giờ dùng hết hạn mức
2. **Chỉ margin cổ phiếu tốt**: Blue chip, thanh khoản cao, không phải cổ phiếu penny
3. **Luôn đặt Stop-loss**: Giới hạn thua lỗ tối đa 5-7% từ điểm mua
4. **Không average down khi dùng margin**: Thêm tiền vào vị thế thua lỗ = tự đào hố
5. **Theo dõi tỷ lệ margin hàng ngày**: Đừng để bị surprise bởi Margin Call
6. **Không dùng margin trong thị trường biến động cao**: VD: trước công bố lãi suất Fed, trước mùa BCTC...

> **Câu nói kinh điển của Warren Buffett**: *"Chỉ khi thủy triều rút mới biết ai đang bơi không mặc quần."* — Những người dùng quá nhiều margin thường là người đầu tiên bị cuốn trôi khi thị trường sập.

---

## Tóm Tắt Kiến Thức Chính (Key Takeaways)

1. **Margin Trading** cho phép bạn vay tiền để đầu tư nhiều hơn vốn có — nhưng khuếch đại cả lời lẫn lỗ theo cùng tỷ lệ
2. **Margin Call** là tín hiệu nguy hiểm — broker có thể bán tháo cổ phiếu của bạn nếu bạn không nộp thêm tiền kịp thời
3. **Short Selling** là đặt cược vào sự giảm giá — lợi nhuận tối đa 100%, nhưng thua lỗ không có giới hạn
4. Cổ đông có quyền nhận **Dividend** (cổ tức), **Voting Rights** (quyền biểu quyết), và hưởng lợi từ **Stock Split**, **Buyback**, **Rights Issue**
5. **Người mới không nên dùng margin** — hãy làm chủ đầu tư cơ bản trước khi sử dụng đòn bẩy

---

## Thuật Ngữ Quan Trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| Margin Trading | Giao dịch ký quỹ | Vay tiền từ broker để mua nhiều cổ phiếu hơn |
| Leverage | Đòn bẩy | Tỷ lệ nhân vốn, VD: 1:2 = dùng 1 đồng vốn, mua 2 đồng tài sản |
| Margin Call | Lệnh bổ sung ký quỹ | Broker yêu cầu nộp thêm tiền khi tài khoản giảm dưới ngưỡng |
| Force Sell | Bán cưỡng chế | Broker tự động bán cổ phiếu khi không đáp ứng Margin Call |
| Short Selling | Bán khống | Mượn CP bán trước, mua lại sau khi giá giảm để kiếm lời |
| Short Squeeze | Cú ép bán khống | Giá tăng đột biến ép người bán khống phải mua lại, đẩy giá tăng tiếp |
| Dividend | Cổ tức | Phần lợi nhuận công ty chia cho cổ đông |
| Dividend Yield | Tỷ suất cổ tức | Cổ tức hàng năm / Giá cổ phiếu × 100% |
| Ex-Dividend Date | Ngày giao dịch không hưởng quyền | Mua sau ngày này không được nhận cổ tức kỳ đó |
| Stock Split | Tách cổ phiếu | Chia nhỏ cổ phiếu, giảm giá để tăng tính thanh khoản |
| Buyback | Mua lại cổ phiếu | Công ty dùng tiền mặt mua lại cổ phiếu của chính mình |
| Rights Issue | Phát hành quyền mua | Cho cổ đông hiện tại ưu tiên mua CP mới với giá ưu đãi |
| Dilution | Pha loãng | Số CP tăng làm giảm tỷ lệ sở hữu của cổ đông hiện tại |

---

## Bài Học Tiếp Theo

**Ngày 35: Value Investing — Đầu Tư Giá Trị Theo Phong Cách Buffett**

Sau khi hiểu rõ cơ chế thị trường, chúng ta sẽ khám phá triết lý đầu tư nổi tiếng nhất thế giới: mua doanh nghiệp tuyệt vời với giá hợp lý và giữ dài hạn. Đây là chiến lược đã tạo ra người giàu nhất thế giới trong hơn 6 thập kỷ.
