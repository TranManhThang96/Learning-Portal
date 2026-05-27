# Ngày 44: Pip, Lot, Leverage & Spread — Ngôn Ngữ Của Forex

## Mục tiêu học tập
- [ ] Hiểu Pip là gì và cách tính giá trị của 1 pip
- [ ] Phân biệt Standard Lot, Mini Lot, Micro Lot và ý nghĩa trong giao dịch
- [ ] Hiểu Leverage hoạt động như thế nào và rủi ro của đòn bẩy cao
- [ ] Biết cách tính Spread và tác động đến chi phí giao dịch
- [ ] Tính được lợi nhuận/thua lỗ trong các tình huống thực tế

---

## Nội dung bài giảng

### 1. Pip — Đơn vị đo lường biến động giá

**Pip** (Percentage in Point — điểm phần trăm) là đơn vị đo lường nhỏ nhất của sự biến động tỷ giá trong Forex.

**Quy tắc chung:**
- Với hầu hết các cặp tiền: **1 pip = chữ số thứ 4 sau dấu thập phân (0.0001)**
- Với cặp USD/JPY (và các cặp có JPY): **1 pip = chữ số thứ 2 sau dấu thập phân (0.01)**

**Ví dụ trực quan:**

```
EUR/USD:
  Giá cũ: 1.08450
  Giá mới: 1.08460
  Biến động: +1 pip (thay đổi ở chữ số thứ 4)

USD/JPY:
  Giá cũ: 149.250
  Giá mới: 149.350
  Biến động: +10 pip (thay đổi ở chữ số thứ 2)
```

**Pipette (Fractional Pip):**
Ngày nay, nhiều broker hiển thị đến 5 chữ số thập phân (hoặc 3 với JPY). Chữ số cuối cùng đó gọi là **pipette** = 0.1 pip.

```
EUR/USD: 1.08452
                ^ pipette (1/10 của 1 pip)
```

---

### 2. Tính Giá trị của 1 Pip

Đây là phần QUAN TRỌNG NHẤT để biết bạn lời/lỗ bao nhiêu tiền thực tế.

**Công thức cơ bản:**
```
Giá trị 1 pip = (0.0001 / Tỷ giá hiện tại) × Kích thước lệnh (lot)
```

Tuy nhiên, cách đơn giản hơn là nhớ theo kích thước lot (xem phần tiếp theo).

---

### 3. Lot — Kích thước giao dịch

**Lot** là đơn vị đo kích thước một lệnh giao dịch trong Forex.

| Loại Lot | Kích thước | Giá trị 1 pip (EUR/USD) |
|----------|-----------|------------------------|
| **Standard Lot** | 100,000 đơn vị base currency | ~10 USD |
| **Mini Lot** | 10,000 đơn vị | ~1 USD |
| **Micro Lot** | 1,000 đơn vị | ~0.10 USD |
| **Nano Lot** | 100 đơn vị | ~0.01 USD |

**Giải thích cụ thể:**

Với EUR/USD ở mức 1.0850:
- **Standard Lot (1.0 lot)**: Bạn đang giao dịch 100,000 EUR. Mỗi pip = **10 USD**
- **Mini Lot (0.1 lot)**: Bạn giao dịch 10,000 EUR. Mỗi pip = **1 USD**
- **Micro Lot (0.01 lot)**: Bạn giao dịch 1,000 EUR. Mỗi pip = **0.10 USD**

**Ví dụ thực tế:**
- Bạn mua EUR/USD tại 1.0850, kích thước 0.1 lot (mini lot)
- Giá tăng lên 1.0900 → tăng 50 pip
- Lợi nhuận = 50 pip × 1 USD/pip = **50 USD**

- Nếu giá giảm xuống 1.0800 → giảm 50 pip
- Thua lỗ = 50 pip × 1 USD/pip = **-50 USD**

---

### 4. Leverage — Đòn Bẩy Tài Chính

**Leverage** (Đòn bẩy) cho phép bạn kiểm soát một lượng tiền lớn hơn số tiền thực tế bạn có trong tài khoản.

**Cách hoạt động:**

Leverage 1:100 nghĩa là: với 1 USD trong tài khoản, bạn có thể giao dịch 100 USD trên thị trường.

```
Vốn thực tế:    1,000 USD
Leverage:        1:100
Sức mua:         100,000 USD (= 1 Standard Lot EUR/USD)
```

**Tại sao broker cho bạn dùng leverage?**
Broker giữ lại một phần vốn của bạn làm **Margin** (ký quỹ) — khoản tiền đặt cọc đảm bảo bạn có thể bù đắp thua lỗ. Nếu thua lỗ quá mức, broker sẽ đóng lệnh tự động.

**Margin Required (Ký quỹ cần thiết):**
```
Margin = (Kích thước lệnh / Leverage) × Tỷ giá
Ví dụ: Mua 1 lot EUR/USD (100,000 EUR) với leverage 1:100
Margin cần = 100,000 / 100 = 1,000 EUR ≈ 1,085 USD
```

---

### 5. Tại sao Leverage là Con Dao Hai Lưỡi?

**Tình huống: Bạn có 1,000 USD, dùng leverage 1:100**

**Kịch bản thắng (thị trường đi đúng hướng):**
- Mua 1 lot EUR/USD tại 1.0850
- Margin cần: 1,000 USD (gần hết vốn!)
- EUR/USD tăng lên 1.0950 → +100 pip
- Lợi nhuận = 100 pip × 10 USD/pip = **1,000 USD** → Lãi 100% vốn!

**Kịch bản thua (thị trường đi ngược):**
- EUR/USD giảm xuống 1.0750 → -100 pip
- Thua lỗ = 100 pip × 10 USD/pip = **-1,000 USD** → Mất toàn bộ vốn!

Chỉ cần giá biến động **100 pip** (= 0.92%) là bạn mất hết 1,000 USD.

**So sánh leverage khác nhau với cùng 1,000 USD:**

| Leverage | Lot size | Pip value | Mất hết vốn khi giá ngược |
|----------|----------|-----------|---------------------------|
| 1:500 | 5 lot | 50 USD/pip | 20 pip (!!) |
| 1:100 | 1 lot | 10 USD/pip | 100 pip |
| 1:50 | 0.5 lot | 5 USD/pip | 200 pip |
| 1:10 | 0.1 lot | 1 USD/pip | 1,000 pip |
| 1:1 | 0.01 lot | 0.1 USD/pip | 10,000 pip |

> **Nguyên tắc vàng**: Người mới KHÔNG nên dùng leverage quá 1:10 đến 1:20. Chỉ dùng leverage cao khi đã có kinh nghiệm và kỷ luật rủi ro chặt chẽ.

**Quy tắc thực tế:**
- Rủi ro tối đa mỗi lệnh: **1-2% tổng vốn**
- Với vốn 1,000 USD: mỗi lệnh thua tối đa 10-20 USD
- → Kích thước lệnh phù hợp: 0.01-0.02 lot với stop loss 50-100 pip

---

### 6. Margin Call & Stop Out

**Margin Call**: Cảnh báo từ broker khi tài khoản của bạn bị lỗ đến mức nguy hiểm. Broker yêu cầu bạn nạp thêm tiền hoặc đóng bớt lệnh.

**Stop Out**: Mức thua lỗ mà broker **tự động đóng lệnh** của bạn để ngăn tài khoản âm dư.

```
Ví dụ (broker thông thường):
Margin Call: khi Margin Level = 100%
Stop Out:    khi Margin Level = 50%

Margin Level = (Equity / Used Margin) × 100%
Equity = Balance + Floating P&L
```

**Ví dụ thực tế:**
- Balance: 1,000 USD
- Mở 1 lot EUR/USD, Margin used: 1,000 USD
- Đang lỗ 500 USD → Equity = 500 USD
- Margin Level = (500 / 1000) × 100% = 50% → **STOP OUT!**

---

### 7. Spread — Chi Phí Giao Dịch Thực Sự

Như đã học ở bài trước, **Spread** là chênh lệch giữa Bid và Ask.

```
EUR/USD: BID 1.08452 | ASK 1.08468
                      ↑
          Spread = 1.6 pip
```

**Spread được tính như thế nào vào chi phí?**
- Khi bạn mở lệnh BUY ở ASK (1.08468) và giả sử ngay sau đó đóng lệnh, bạn sẽ đóng ở BID (1.08452)
- Bạn lỗ ngay: **-1.6 pip** chỉ vì spread
- Với 0.1 lot → lỗ 0.16 USD mỗi lần mở rồi đóng ngay

**Spread cố định vs Spread thả nổi:**

| | Fixed Spread | Variable (Floating) Spread |
|--|------------|--------------------------|
| **Ưu điểm** | Biết trước chi phí | Thường thấp hơn fixed trong giờ bình thường |
| **Nhược điểm** | Thường cao hơn | Nở rộng trong giờ tin tức, thanh khoản thấp |
| **Phù hợp** | Scalper, news trader | Swing trader, day trader |

**Spread điển hình:**
| Cặp tiền | Spread bình thường | Khi có tin quan trọng |
|----------|-------------------|----------------------|
| EUR/USD | 0.1 - 1.5 pip | 5 - 30+ pip |
| GBP/USD | 0.5 - 2 pip | 10 - 50+ pip |
| USD/JPY | 0.1 - 1.5 pip | 5 - 25+ pip |
| Exotic pairs | 10 - 50+ pip | 50 - 200+ pip |

> **Cảnh báo**: Trong khi có tin tức quan trọng (NFP, FOMC, CPI...), spread có thể nở rộng đột ngột 10-50 lần bình thường. Stop loss của bạn có thể bị kích hoạt sai do spread rộng — đây gọi là **slippage**.

---

### 8. Swap — Phí Qua Đêm

**Swap** (còn gọi là Rollover hay Overnight Fee) là phí bạn phải trả (hoặc nhận) khi giữ lệnh qua đêm — tức là qua mốc 00:00 GMT (07:00 Việt Nam).

**Tại sao có Swap?**
Vì Forex thực chất là vay đồng tiền này để mua đồng tiền kia. Hai đồng tiền có lãi suất khác nhau → phát sinh chênh lệch lãi suất hàng đêm.

```
Ví dụ: Mua AUD/USD (Buy AUD, Sell USD)
AUD lãi suất: 4.35% → Bạn "nhận" lãi từ AUD
USD lãi suất: 5.50% → Bạn "trả" lãi cho USD
→ Swap = Nhận 4.35% - Trả 5.50% = -1.15%/năm → Bạn phải TRẢ swap mỗi đêm

Ngược lại, nếu bán AUD/USD:
→ Swap = +1.15%/năm → Bạn NHẬN swap mỗi đêm
```

**Swap được áp dụng 3x vào thứ Tư** (để bù cho cuối tuần không giao dịch).

**Ảnh hưởng của Swap:**
- Day traders không bị ảnh hưởng (đóng lệnh trước midnight)
- Swing traders cần tính swap vào chi phí/lợi nhuận
- **Carry Trade** (chiến lược ngày 46) dựa vào swap để kiếm tiền

**Islamic Account (Tài khoản Hồi giáo / Swap-free):** Một số broker cung cấp tài khoản không tính swap cho khách hàng theo đạo Hồi (luật Sharia cấm lãi suất). Một số broker cũng cho phép mở loại tài khoản này theo yêu cầu.

---

### 9. Tổng hợp: Tính Toán Giao Dịch Thực Tế

**Bài toán tổng hợp:**

Bạn có tài khoản 2,000 USD. Muốn mua EUR/USD với các thông số:
- Tỷ giá vào lệnh: 1.0850 (ASK)
- Stop Loss: 1.0800 (50 pip dưới điểm vào)
- Take Profit: 1.0950 (100 pip trên điểm vào)
- Rủi ro tối đa: 2% vốn = 40 USD

**Bước 1: Tính kích thước lệnh**
```
Rủi ro chấp nhận = 40 USD
Stop Loss = 50 pip
Pip value cần = 40 USD / 50 pip = 0.8 USD/pip
→ Kích thước lệnh = 0.08 lot (micro lot ≈ 0.08 lot)
```

**Bước 2: Tính chi phí spread**
```
Spread EUR/USD = 1.5 pip
Chi phí spread = 1.5 pip × 0.8 USD/pip = 1.2 USD
```

**Bước 3: Kết quả nếu TP hit**
```
Lợi nhuận = 100 pip × 0.8 USD/pip = 80 USD
Trừ spread = -1.2 USD
Net profit = 78.8 USD → Lãi ~3.9% vốn
```

**Bước 4: Kết quả nếu SL hit**
```
Thua lỗ = 50 pip × 0.8 USD/pip = -40 USD
Trừ spread = -1.2 USD
Net loss = -41.2 USD → Lỗ ~2.1% vốn
```

**Risk/Reward Ratio = 80/40 = 1:2** — Rất tốt!

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **Pip** = đơn vị đo biến động giá (0.0001 với hầu hết cặp tiền; 0.01 với cặp JPY)
2. **Lot** xác định kích thước lệnh: Standard (10 USD/pip), Mini (1 USD/pip), Micro (0.1 USD/pip)
3. **Leverage** khuếch đại cả lợi nhuận lẫn thua lỗ — người mới nên giới hạn ở 1:10 đến 1:20
4. **Spread** là chi phí giao dịch ẩn, nở rộng khi có tin tức quan trọng
5. **Swap** là phí qua đêm dựa trên chênh lệch lãi suất hai đồng tiền
6. **Quy tắc 1-2% rủi ro/lệnh** + tính toán kích thước lệnh đúng = bảo vệ tài khoản dài hạn

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|-----------------|-----------------|
| Pip (Percentage in Point) | Điểm phần trăm | Đơn vị nhỏ nhất của biến động tỷ giá |
| Pipette | 1/10 pip | Chữ số thập phân thứ 5 |
| Lot | Lô giao dịch | Đơn vị đo kích thước lệnh |
| Standard Lot | Lô tiêu chuẩn | 100,000 đơn vị base currency |
| Mini Lot | Lô nhỏ | 10,000 đơn vị (0.1 lot) |
| Micro Lot | Lô siêu nhỏ | 1,000 đơn vị (0.01 lot) |
| Leverage | Đòn bẩy | Khuếch đại sức mua vượt vốn thực |
| Margin | Ký quỹ | Tiền đặt cọc để mở lệnh |
| Margin Call | Lệnh gọi ký quỹ | Cảnh báo tài khoản sắp hết tiền |
| Stop Out | Đóng lệnh bắt buộc | Broker tự đóng lệnh khi margin cạn |
| Spread | Chênh lệch giá | Chênh lệch Bid-Ask, chi phí giao dịch |
| Swap / Rollover | Phí qua đêm | Phí giữ lệnh qua midnight GMT |
| Slippage | Trượt giá | Lệnh thực thi ở giá khác giá đặt |
| Position Sizing | Tính kích thước lệnh | Quyết định giao dịch bao nhiêu lot |

---

## Bài học tiếp theo

Ngày 45 sẽ học **Fundamental Analysis trong Forex** — cách các dữ liệu kinh tế như GDP, CPI, NFP, và quyết định lãi suất của các ngân hàng trung ương tác động đến tỷ giá. Bạn sẽ biết cách giao dịch xung quanh các sự kiện tin tức quan trọng.
