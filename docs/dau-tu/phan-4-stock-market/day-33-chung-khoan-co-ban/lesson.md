# Ngày 33: Thị trường chứng khoán — Cách hoạt động & Nền tảng thực hành

## Mục tiêu học tập
- [ ] Hiểu cách thị trường chứng khoán hoạt động và vai trò của các bên tham gia
- [ ] Phân biệt HOSE, HNX, UPCOM và đặc điểm của từng sàn
- [ ] Nắm vững các loại lệnh giao dịch: Market Order, Limit Order, Stop Order
- [ ] Hiểu Bid/Ask Spread, T+2 Settlement và ảnh hưởng thực tế
- [ ] So sánh NYSE, NASDAQ với thị trường VN để có góc nhìn toàn cầu

---

## Nội dung bài giảng

### 1. Tại sao thị trường chứng khoán tồn tại?

Hãy tưởng tượng bạn có một quán cà phê đang ăn nên làm ra và muốn mở thêm 10 chi nhánh. Bạn cần 10 tỷ đồng nhưng chỉ có 2 tỷ. Vay ngân hàng thì lãi suất cao, vay bạn bè thì không đủ. Giải pháp?

**Phát hành cổ phiếu ra công chúng!**

Bạn chia công ty thành 1 triệu cổ phần, bán mỗi cổ phần 10,000 VND → thu về 10 tỷ. Người mua cổ phiếu trở thành **cổ đông** (shareholder) — đồng sở hữu công ty của bạn.

Thị trường chứng khoán phục vụ hai mục đích chính:
1. **Doanh nghiệp** huy động vốn để mở rộng kinh doanh
2. **Nhà đầu tư** có kênh sinh lợi từ vốn nhàn rỗi

Đây là mối quan hệ **cộng sinh**: doanh nghiệp cần vốn, nhà đầu tư cần lợi nhuận.

---

### 2. Các bên tham gia thị trường

```
┌─────────────────────────────────────────────────────┐
│                 STOCK EXCHANGE                       │
│            (Sàn giao dịch chứng khoán)               │
│                                                     │
│   Người bán cổ phiếu ←────────────→ Người mua       │
│      (Seller)            Broker         (Buyer)      │
│                        (CTCK)                       │
└─────────────────────────────────────────────────────┘
                           ↑
                    SSC/UBCKNN
              (Cơ quan quản lý nhà nước)
```

**Các bên chính:**
- **Doanh nghiệp niêm yết**: Phát hành cổ phiếu, công bố thông tin
- **Nhà đầu tư**: Cá nhân, tổ chức (quỹ đầu tư, ngân hàng, bảo hiểm)
- **Broker (Công ty chứng khoán — CTCK)**: Trung gian, nơi bạn mở tài khoản
- **Stock Exchange (Sàn giao dịch)**: Nơi các lệnh được khớp tự động
- **Cơ quan quản lý**: UBCKNN (Ủy ban Chứng khoán Nhà nước) ở VN, SEC ở Mỹ

---

### 3. Thị trường chứng khoán Việt Nam

#### 3.1 Ba sàn giao dịch chính

| Sàn | Tên đầy đủ | Đặc điểm | Ví dụ |
|-----|-----------|---------|-------|
| **HOSE** | Ho Chi Minh Stock Exchange | Sàn lớn nhất, blue-chip, thanh khoản cao | VCB, FPT, VHM, MWG |
| **HNX** | Hanoi Stock Exchange | Doanh nghiệp vừa và nhỏ hơn, ngân hàng | SHB, NVB |
| **UPCOM** | Unlisted Public Company Market | Chưa niêm yết chính thức, rủi ro cao hơn | Nhiều doanh nghiệp mới |

**VN-Index**: Chỉ số tổng hợp của HOSE — thước đo sức khỏe TTCK VN
**HNX-Index**: Chỉ số của sàn HNX

**Quan trọng:** Mã cổ phiếu VN chỉ có 3 ký tự (VCB, FPT, HPG). Mỹ dùng 1-5 ký tự (AAPL, GOOGL, MSFT).

#### 3.2 Giờ giao dịch (Giờ Việt Nam)

```
Phiên ATO (At The Open):    9:00 - 9:15   (khớp lệnh mở cửa)
Phiên liên tục buổi sáng:   9:15 - 11:30
Nghỉ trưa:                  11:30 - 13:00
Phiên liên tục buổi chiều:  13:00 - 14:30
Phiên ATC (At The Close):   14:30 - 14:45 (khớp lệnh đóng cửa)
```

#### 3.3 Biên độ dao động giá (Price Limit)

Đây là điểm khác biệt lớn nhất của TTCK VN so với thế giới:

| Sàn | Biên độ tăng/giảm tối đa/ngày |
|-----|-------------------------------|
| HOSE | ±7% (từ giá tham chiếu) |
| HNX | ±10% |
| UPCOM | ±15% |

**Giá trần (Ceiling)** = Giá tham chiếu × 1.07 (HOSE)
**Giá sàn (Floor)** = Giá tham chiếu × 0.93 (HOSE)

**Ví dụ:** FPT giá tham chiếu 95,000 VND
- Giá trần: 95,000 × 1.07 = 101,650 VND
- Giá sàn: 95,000 × 0.93 = 88,350 VND
- Giá tím (trần): Màu tím/hồng trên bảng điện
- Giá xanh lá (sàn): Màu xanh lá trên bảng điện

---

### 4. Các loại lệnh giao dịch

Đây là kiến thức thực hành cực kỳ quan trọng — bạn cần biết rõ trước khi đặt lệnh đầu tiên.

#### 4.1 Market Order (Lệnh thị trường)

**Định nghĩa:** Mua/bán ngay lập tức tại mức giá tốt nhất hiện có trên thị trường.

```
Bạn đặt: "Mua 100 cổ phiếu FPT, Market Order"
Thị trường: Người bán gần nhất đang chào 95,200 VND
Kết quả: Lệnh khớp ngay tại 95,200 VND
```

**Ưu điểm:** Chắc chắn khớp lệnh
**Nhược điểm:** Không kiểm soát được giá — trong thị trường biến động mạnh hoặc ít thanh khoản, có thể mua giá rất cao/bán giá rất thấp (**slippage**)

**Khi nào dùng:** Khi cần mua/bán gấp, cổ phiếu có thanh khoản cao

#### 4.2 Limit Order (Lệnh giới hạn)

**Định nghĩa:** Chỉ mua khi giá ≤ mức bạn đặt, chỉ bán khi giá ≥ mức bạn đặt.

```
Bạn đặt: "Mua 100 FPT, Limit Order, giá 94,000"
Tình huống 1: FPT về 94,000 → Lệnh khớp ✓
Tình huống 2: FPT không bao giờ về 94,000 → Lệnh chờ (không khớp)
Tình huống 3: FPT mở cửa giảm thẳng xuống 92,000 → Lệnh khớp tại 92,000 (vì < 94,000)
```

**Ưu điểm:** Kiểm soát giá vào lệnh
**Nhược điểm:** Có thể không khớp nếu giá không chạm đến

**Khi nào dùng:** Hầu hết mọi trường hợp — đây là loại lệnh phổ biến nhất

#### 4.3 Stop Order (Lệnh dừng)

**Stop-loss Order (Lệnh cắt lỗ):**

```
Bạn mua FPT tại 95,000, đặt Stop-loss tại 91,000.
→ Nếu FPT giảm xuống 91,000: Lệnh bán tự động kích hoạt
→ Bảo vệ vốn khi bạn không theo dõi thị trường
```

**Stop-limit Order:**
Kết hợp Stop + Limit: Khi giá chạm Stop price, tạo ra Limit Order (không phải Market Order).

**Lưu ý quan trọng cho thị trường VN:** HOSE chưa hỗ trợ Stop Order tự động như sàn Mỹ. Nhà đầu tư VN phải **tự đặt Limit Order cắt lỗ** hoặc dùng tính năng Alert (cảnh báo giá) trên app CTCK.

#### 4.4 Tóm tắt các loại lệnh đặc thù HOSE

| Loại lệnh | Ký hiệu | Ý nghĩa |
|-----------|---------|---------|
| Lệnh giới hạn | LO | Limit Order chuẩn |
| Lệnh ATO | ATO | Khớp tại giá mở cửa, chỉ đặt 9:00-9:15 |
| Lệnh ATC | ATC | Khớp tại giá đóng cửa, chỉ đặt 14:30-14:45 |
| Lệnh MP | MP | Market-to-Limit (cho HNX) |

---

### 5. Bid/Ask Spread — Chi phí ẩn bạn phải biết

#### 5.1 Bid và Ask là gì?

```
BID (Giá mua — người mua sẵn sàng trả):     94,800 VND
ASK (Giá bán — người bán sẵn sàng nhận):    95,000 VND

SPREAD = ASK - BID = 95,000 - 94,800 = 200 VND
```

**Ý nghĩa thực tế:** Khi bạn mua 1,000 CP FPT tại giá Ask (95,000) và ngay lập tức muốn bán, bạn chỉ nhận được giá Bid (94,800) → Lỗ ngay 200,000 VND chỉ vì spread!

#### 5.2 Tại sao Spread quan trọng?

- Cổ phiếu **thanh khoản cao** (VCB, FPT, HPG): Spread nhỏ (100-500 VND) → Chi phí thấp
- Cổ phiếu **ít thanh khoản**: Spread lớn (1,000-5,000 VND) → Chi phí cao

**Ví dụ tính tổng chi phí khi mua/bán 1,000 CP FPT:**
```
Mua: 1,000 × 95,000 = 95,000,000 VND
Phí giao dịch (0.15-0.35%): ~142,500 đến 332,500 VND
Spread: 1,000 × 200 = 200,000 VND
Tổng chi phí 1 lượt: ~342,500 đến 532,500 VND

Cho cả 2 chiều (mua + bán): ~685,000 đến 1,065,000 VND
→ Phải tăng ít nhất 1% giá mới hòa vốn!
```

---

### 6. T+2 Settlement — Tiền và cổ phiếu về tay khi nào?

#### 6.1 T+2 là gì?

**T+2 (Trade Date + 2 Business Days)**: Tiền và cổ phiếu được thanh toán sau **2 ngày làm việc** kể từ ngày giao dịch.

```
Thứ 2: Bạn MUA 1,000 FPT ← Tiền bị giữ ngay lập tức
Thứ 3: (Ngày T+1)
Thứ 4: (Ngày T+2) ← Cổ phiếu FPT về tài khoản của bạn

Thứ 2: Bạn BÁN 1,000 FPT ← CP bị giữ ngay lập tức
Thứ 4: (Ngày T+2) ← Tiền về tài khoản của bạn
```

**Lưu ý:** T+2 không tính ngày nghỉ/lễ. Bán vào thứ 6 → tiền về thứ 3 tuần sau.

#### 6.2 Ảnh hưởng thực tế của T+2

**Trường hợp 1:** Bạn mua FPT thứ 2, muốn bán luôn thứ 3 vì có lợi nhuận tốt.
→ **Không thể bán!** FPT chưa về tài khoản. Phải chờ thứ 4.

**Trường hợp 2:** Bạn bán VCB thứ 2, muốn dùng tiền mua HPG ngay thứ 2.
→ **Phụ thuộc CTCK**: Một số CTCK cho dùng "tiền bán chờ về" (margin tạm thời), một số thì không.

**Điều này có nghĩa:** Trong TTCK VN, bạn cần lên kế hoạch **ít nhất 2 ngày trước** nếu cần linh hoạt vốn.

---

### 7. Thị trường Mỹ — So sánh với VN

#### 7.1 NYSE và NASDAQ

| | NYSE | NASDAQ |
|--|------|--------|
| Tên đầy đủ | New York Stock Exchange | National Association of Securities Dealers Automated Quotations |
| Thành lập | 1792 | 1971 |
| Đặc điểm | Truyền thống, blue-chip | Công nghệ, tăng trưởng |
| Ví dụ | JPMorgan, Coca-Cola, Nike | Apple, Google, Amazon, Tesla |
| Chỉ số đại diện | Dow Jones, NYSE Composite | NASDAQ Composite, NASDAQ 100 |

#### 7.2 Sự khác biệt chính VN vs Mỹ

| Tiêu chí | VN (HOSE) | Mỹ (NYSE/NASDAQ) |
|----------|-----------|------------------|
| Biên độ dao động | ±7% | Không giới hạn |
| Giờ giao dịch | 9:00-14:45 (trong ngày) | 9:30-16:00 ET + Pre/After Market |
| Settlement | T+2 (đang chuyển sang T+1) | T+1 (từ 2024) |
| Khối lượng tối thiểu | 100 CP (lô cơ sở) | 1 CP |
| Short Selling | Hạn chế | Phổ biến |
| ETF, Derivatives | Có nhưng ít | Rất phong phú |
| Thuế | 0.1% trên giá trị bán | Thuế capital gains (% lợi nhuận) |

#### 7.3 Nhà đầu tư VN có thể mua cổ phiếu Mỹ không?

Có! Thông qua:
1. **Tài khoản CTCK nước ngoài**: Interactive Brokers, TD Ameritrade (nhưng phức tạp về pháp lý)
2. **Sản phẩm đầu tư gián tiếp**: ETF, Fund nước ngoài
3. **Fintech apps**: Một số ứng dụng cho phép mua cổ phiếu Mỹ (kiểm tra pháp lý cẩn thận)

---

### 8. Mở tài khoản chứng khoán — Hướng dẫn thực hành

#### 8.1 Chọn công ty chứng khoán (CTCK)

**Top CTCK Việt Nam:**

| CTCK | Ưu điểm | Phí giao dịch |
|------|---------|---------------|
| SSI | Uy tín cao, nhiều sản phẩm, app tốt | 0.15-0.25% |
| VPS | App tốt, phổ biến với nhà đầu tư trẻ | 0.15-0.25% |
| VCSC | Research quality cao, dành cho tổ chức | 0.15-0.25% |
| MBS | Thuộc MB Bank, tích hợp ngân hàng tốt | 0.15-0.25% |
| Mirae Asset | Công ty Hàn Quốc, nhiều margin, phí thấp | 0.10-0.15% |
| VPBankS | Thuộc VPBank, ưu đãi tốt cho KH ngân hàng | 0.15-0.25% |

**Tiêu chí chọn CTCK:**
1. Uy tín và lịch sử hoạt động
2. App mobile dễ dùng
3. Phí giao dịch
4. Dịch vụ hỗ trợ khách hàng
5. Sản phẩm và công cụ nghiên cứu

#### 8.2 Quy trình mở tài khoản

1. **Chuẩn bị giấy tờ:** CCCD/CMND, số điện thoại, email
2. **Đăng ký online** hoặc đến trực tiếp CTCK
3. **eKYC** (xác minh danh tính điện tử): Chụp CCCD, selfie
4. **Ký hợp đồng điện tử** (OTP qua SMS)
5. **Nạp tiền** vào tài khoản (chuyển khoản theo hướng dẫn)
6. **Mua cổ phiếu đầu tiên!**

**Thời gian:** Từ đăng ký đến có thể giao dịch: 1-3 ngày làm việc.

---

### 9. Một phiên giao dịch điển hình — Theo dõi từ đầu đến cuối

**Tình huống:** Bạn muốn mua 200 cổ phiếu FPT tại giá tốt

```
Bước 1 (8:30 - trước mở cửa):
→ Phân tích kỹ thuật: FPT Daily chart, xác nhận setup
→ Xác định giá mua hợp lý: 95,000 VND
→ Tính Stop-loss: 91,500 VND
→ Tính Take-profit: 102,000 VND

Bước 2 (9:00 - mở app):
→ Kiểm tra bảng điện: Giá tham chiếu FPT = 95,200
→ Giá trần = 101,864 | Giá sàn = 88,536

Bước 3 (9:15 - đặt lệnh):
→ Chọn: Mua | FPT | Số lượng: 200 | Giá: 95,000 | LO
→ Xác nhận OTP

Bước 4 (Theo dõi):
→ 10:20: Lệnh khớp tại 95,000 ✓
→ 11:00: FPT lên 96,500 — đang có lãi 300,000 VND

Bước 5 (Đặt lệnh bảo vệ):
→ Đặt Limit Order bán tại 91,500 (stop-loss thủ công)
→ Đặt Alert khi giá chạm 102,000 (take-profit target)
```

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **TTCK** là nơi doanh nghiệp huy động vốn và nhà đầu tư kiếm lợi nhuận — mối quan hệ cộng sinh.
2. **VN có 3 sàn**: HOSE (lớn nhất), HNX (vừa), UPCOM (chưa niêm yết) — khác nhau về quy mô và rủi ro.
3. **Biên độ ±7% (HOSE)** là đặc điểm riêng của VN, bảo vệ nhà đầu tư nhưng cũng giới hạn cơ hội.
4. **Limit Order** là loại lệnh phổ biến nhất — kiểm soát giá, dùng thường xuyên.
5. **Bid/Ask Spread** là chi phí ẩn — luôn tính vào bài toán lợi nhuận.
6. **T+2**: Cổ phiếu về sau 2 ngày làm việc — lên kế hoạch vốn phù hợp.
7. **HOSE vs NYSE/NASDAQ**: Khác nhau về biên độ, giờ giao dịch, thanh khoản và đa dạng sản phẩm.

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| Stock Exchange | Sàn giao dịch chứng khoán | Nơi mua/bán cổ phiếu được thực hiện |
| Broker | Công ty chứng khoán | Trung gian giữa nhà đầu tư và sàn |
| Market Order | Lệnh thị trường | Mua/bán ngay tại giá tốt nhất hiện tại |
| Limit Order | Lệnh giới hạn | Mua/bán tại giá được chỉ định |
| Stop Order | Lệnh dừng | Kích hoạt tự động khi giá chạm ngưỡng |
| Bid Price | Giá mua | Giá cao nhất người mua sẵn sàng trả |
| Ask Price | Giá bán | Giá thấp nhất người bán chấp nhận |
| Spread | Chênh lệch bid/ask | Chi phí ẩn mỗi giao dịch |
| Slippage | Trượt giá | Khác biệt giữa giá kỳ vọng và giá thực tế |
| T+2 Settlement | Thanh toán T+2 | Hoàn tất giao dịch sau 2 ngày làm việc |
| Ceiling Price | Giá trần | Giá cao nhất có thể giao dịch trong ngày |
| Floor Price | Giá sàn | Giá thấp nhất có thể giao dịch trong ngày |
| Reference Price | Giá tham chiếu | Giá đóng cửa hôm trước, cơ sở tính trần/sàn |
| ATO | At The Open | Lệnh khớp tại giá mở cửa |
| ATC | At The Close | Lệnh khớp tại giá đóng cửa |
| eKYC | Electronic Know Your Customer | Xác minh danh tính điện tử |
| Blue-chip | Cổ phiếu vốn hóa lớn | Cổ phiếu doanh nghiệp lớn, uy tín |
| Lot | Lô | Đơn vị giao dịch tối thiểu (100 CP ở VN) |

---

## Bài học tiếp theo

**Ngày 34: Margin Trading & Quyền lợi cổ đông**

Ngày mai chúng ta học về **Margin Trading** (giao dịch ký quỹ) — sử dụng đòn bẩy để mua nhiều cổ phiếu hơn số vốn thực có. Đây là con dao hai lưỡi: khuếch đại cả lợi nhuận lẫn thua lỗ. Chúng ta cũng học về **Short Selling** (bán khống) và các quyền lợi của cổ đông: Cổ tức (Dividend), quyền biểu quyết, và tác động của Stock Split đến danh mục của bạn.
