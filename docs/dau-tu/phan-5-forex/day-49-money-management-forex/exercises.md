# Bài tập — Ngày 49: Money Management trong Forex

## Phần 1: Câu hỏi ôn tập (Quiz)

1. Trader có tài khoản $5,000, áp dụng rủi ro 2% mỗi lệnh. Số tiền tối đa có thể mất trong một lệnh là bao nhiêu?
   - A. $50
   - B. $100
   - C. $500
   - D. $1,000

   *(Đáp án: B — $100)*

2. Trader đặt lệnh mua EUR/USD với Stop-Loss 40 pips, Take-Profit 80 pips. Risk/Reward Ratio là:
   - A. 1:1
   - B. 1:2
   - C. 2:1
   - D. 1:3

3. Tài khoản đang ở mức cao nhất là $12,000, sau đó giảm xuống còn $9,600. Maximum Drawdown là bao nhiêu?
   - A. $2,400
   - B. 20%
   - C. 25%
   - D. Cả A và B đều đúng theo nghĩa khác nhau

4. Trader A có win rate 40% nhưng R:R luôn 1:3. Trader B có win rate 65% nhưng R:R luôn 1:0.5. Ai có Expectancy tốt hơn?
   - A. Trader A
   - B. Trader B
   - C. Bằng nhau
   - D. Không đủ thông tin

5. Bạn đang hold lệnh mua EUR/USD và lệnh mua GBP/USD cùng lúc. Đây là:
   - A. Đa dạng hóa tốt vì 2 cặp tiền khác nhau
   - B. Rủi ro cao vì hai cặp tương quan mạnh cùng chiều
   - C. An toàn vì hai cặp tiền thường đi ngược nhau
   - D. Không có vấn đề gì

6. Khi lệnh đang thua và chạm gần Stop-Loss, hành động đúng đắn là:
   - A. Di chuyển SL xa hơn để "cho lệnh thêm không gian"
   - B. Thêm vào lệnh (averaging down) để giảm giá trung bình
   - C. Để SL tự chạm và chấp nhận khoản lỗ đã định trước
   - D. Đóng lệnh ngay lập tức trước khi SL bị hit

7. Position Size Calculator cho kết quả 0.15 lots với tài khoản $8,000, rủi ro 1%, SL 50 pips EUR/USD. Nếu pip value = $10/pip, kết quả này có đúng không?
   - A. Đúng
   - B. Sai, phải là 0.16 lots
   - C. Sai, phải là 1.5 lots
   - D. Không đủ thông tin

8. Theo nguyên tắc quản lý Drawdown, bạn nên làm gì khi drawdown trong tháng đạt 10%?
   - A. Tăng size lệnh để "gỡ lại" nhanh hơn
   - B. Dừng giao dịch và xem lại chiến lược
   - C. Chỉ trade các cặp tiền mình thích nhất
   - D. Không cần làm gì, drawdown 10% là bình thường

9. Trailing Stop có ưu điểm chính là:
   - A. Bảo vệ tài khoản khỏi mọi khoản lỗ
   - B. Cho phép bắt xu hướng dài và bảo vệ lợi nhuận đã có
   - C. Giúp win rate tăng lên
   - D. Thay thế hoàn toàn cho Stop-Loss cố định

10. Expectancy của hệ thống: Win Rate 45%, R:R 1:2 là:
    - A. -0.10R (âm)
    - B. 0.00R (hòa)
    - C. +0.35R (dương)
    - D. +0.45R (dương)

---

## Phần 2: Bài tập thực hành

### Bài tập 1: Tính Position Size

Cho các thông tin sau, tính Position Size phù hợp:

**Tình huống A:**
- Tài khoản: $15,000
- Rủi ro: 1%
- Cặp: EUR/USD
- Entry: 1.0950
- Stop-Loss: 1.0890 (60 pips)
- Pip Value: $10/pip (Standard Lot)

Tính: Số tiền rủi ro = ? | Position Size = ? lots

**Tình huống B:**
- Tài khoản: $5,000
- Rủi ro: 2%
- Cặp: GBP/USD
- Entry: 1.2700
- Stop-Loss: 1.2630 (70 pips)
- Pip Value: $10/pip (Standard Lot)

Tính: Số tiền rủi ro = ? | Position Size = ? lots

**Tình huống C:**
- Tài khoản: $20,000
- Rủi ro: 0.5%
- Cặp: USD/JPY
- Entry: 149.50
- Stop-Loss: 150.80 (130 pips)
- Pip Value: $9.09/pip (Standard Lot, tỷ giá ~150)

Tính: Số tiền rủi ro = ? | Position Size = ? lots

---

### Bài tập 2: Phân tích Expectancy hệ thống

Bạn đã giao dịch 50 lệnh trong 3 tháng:
- Số lệnh thắng: 22 (Win Rate = ?)
- Số lệnh thua: 28 (Loss Rate = ?)
- Tổng lợi nhuận từ lệnh thắng: $2,200
- Tổng lỗ từ lệnh thua: $1,400

Tính:
1. Win Rate và Loss Rate
2. Average Win per trade
3. Average Loss per trade
4. Risk/Reward Ratio thực tế
5. Expectancy mỗi lệnh
6. Hệ thống này có bền vững không? Tại sao?

---

### Bài tập 3: Phân tích Drawdown

Tài khoản bắt đầu: $10,000. Lịch sử giao dịch:

| Lệnh | P&L | Balance |
|------|-----|---------|
| 1 | +$200 | $10,200 |
| 2 | +$150 | $10,350 |
| 3 | -$100 | $10,250 |
| 4 | +$300 | $10,550 |
| 5 | -$100 | $10,450 |
| 6 | -$100 | $10,350 |
| 7 | -$100 | $10,250 |
| 8 | -$100 | $10,150 |
| 9 | +$200 | $10,350 |
| 10 | +$200 | $10,550 |

Tính:
1. Đỉnh cao nhất (Peak) của tài khoản là bao nhiêu và sau lệnh nào?
2. Drawdown tối đa (Maximum Drawdown) là bao nhiêu $ và %?
3. Cần bao nhiêu % lợi nhuận để phục hồi từ MDD đó?
4. Trong giai đoạn drawdown, bạn có nên dừng giao dịch không? Tại sao?

---

### Bài tập 4: Xây dựng Trading Plan cá nhân

Thiết kế Trading Plan Money Management của bạn:

```
TRADING PLAN — MONEY MANAGEMENT CÁ NHÂN

Họ tên: _______________
Ngày bắt đầu: _______________

TÀI KHOẢN
- Vốn ban đầu: $_______________
- Loại tài khoản: Demo / Live
- Broker: _______________

QUẢN LÝ RỦI RO
- % rủi ro mỗi lệnh: ____%
- Số tiền rủi ro mỗi lệnh ($): $_______________
- R:R tối thiểu: 1:___
- Số lệnh tối đa mỗi ngày: ___ lệnh
- Số lệnh tối đa mỗi tuần: ___ lệnh

QUY TẮC DỪNG
- Thua bao nhiêu lệnh liên tiếp thì nghỉ hôm đó: ___ lệnh
- Drawdown tuần tối đa cho phép: ____%
- Drawdown tháng tối đa cho phép: ____%
- Hành động khi đạt mức trên: _______________

MỤC TIÊU
- Mục tiêu quy trình tháng: _______________
- Chỉ đặt mục tiêu lợi nhuận sau khi đã có dữ liệu backtest/forward test đủ dài: ____%

CHỮ KÝ CAM KẾT: _______________
```

---

## Phần 3: Case Study

### Trường hợp Trader Nguyễn Minh Hùng

Anh Hùng bắt đầu với $10,000, rất tự tin vì đã học phân tích kỹ thuật 3 tháng.

**Tháng 1:** Anh Hùng không tính Position Size, chỉ trade 0.5 lots mỗi lệnh vì "cảm thấy ổn". Kết quả: 8 lệnh thắng, 4 lệnh thua nhưng vì không có SL cố định, 2 lệnh thua lỗ rất lớn. Tài khoản còn $8,200 (-18%).

**Tháng 2:** Anh Hùng tức giận, tăng size lên 1 lot để "gỡ nhanh". 3 lệnh thua liên tiếp vì thị trường đột biến (NFP). Tài khoản còn $5,500. Anh Hùng tiếp tục tăng size lên 2 lots.

**Tháng 3:** Thêm 2 lệnh thua lớn. Tài khoản còn $2,100 — mất 79% vốn ban đầu.

**Câu hỏi phân tích:**

1. Nếu anh Hùng áp dụng quy tắc 1% từ đầu với SL cố định, hãy ước tính kết quả tháng 1 sẽ khác như thế nào?

2. Sai lầm lớn nhất trong Tháng 2 là gì? Anh nên làm gì thay vì tăng size?

3. Anh Hùng mất 79% vốn. Tính số % lợi nhuận cần thiết để về bằng vốn $10,000 ban đầu.

4. Thiết kế một Trading Plan Money Management đơn giản mà anh Hùng nên áp dụng từ Tháng 1. Bao gồm: % risk, quy tắc dừng, R:R tối thiểu.

---

## Đáp án & Giải thích

### Quiz
1. **B — $100** (2% × $5,000 = $100)
2. **B — 1:2** (40 pips risk : 80 pips profit = 1:2)
3. **B — 20%** ($2,400 ÷ $12,000 = 20%. Option A đúng về số tiền nhưng không phải % drawdown tiêu chuẩn)
4. **A — Trader A**: Expectancy A = (0.4×3R) - (0.6×1R) = 1.2R - 0.6R = +0.6R; Expectancy B = (0.65×0.5R) - (0.35×1R) = 0.325R - 0.35R = -0.025R → Trader A tốt hơn!
5. **B — Rủi ro cao** vì EUR/USD và GBP/USD tương quan ~0.85-0.95, di chuyển cùng chiều
6. **C — Để SL tự chạm** — Tôn trọng kế hoạch, không thay đổi SL khi đang thua
7. **B — Sai, phải là 0.16 lots**: Số tiền rủi ro = 1% × $8,000 = $80; Position Size = $80 ÷ (50 × $10) = $80/$500 = 0.16 lots. Nếu broker chỉ cho bước lot 0.01, có thể làm tròn xuống 0.15 để rủi ro thấp hơn một chút.
8. **B — Dừng giao dịch và xem lại chiến lược**
9. **B — Cho phép bắt xu hướng và bảo vệ lợi nhuận**
10. **C — +0.35R**: Expectancy = (0.45 × 2R) - (0.55 × 1R) = 0.90R - 0.55R = +0.35R

---

### Bài tập 1 — Position Size

**Tình huống A:**
- Số tiền rủi ro = 1% × $15,000 = **$150**
- Position Size = $150 ÷ (60 × $10) = $150 ÷ $600 = **0.25 lots**

**Tình huống B:**
- Số tiền rủi ro = 2% × $5,000 = **$100**
- Position Size = $100 ÷ (70 × $10) = $100 ÷ $700 = **0.143 lots ≈ 0.14 lots**

**Tình huống C:**
- Số tiền rủi ro = 0.5% × $20,000 = **$100**
- Position Size = $100 ÷ (130 × $9.09) = $100 ÷ $1,181.7 = **0.085 lots ≈ 0.08 lots**

---

### Bài tập 2 — Expectancy

1. Win Rate = 22/50 = **44%**; Loss Rate = 28/50 = **56%**
2. Average Win = $2,200 ÷ 22 = **$100/lệnh**
3. Average Loss = $1,400 ÷ 28 = **$50/lệnh**
4. R:R thực tế = $100 ÷ $50 = **2:1 (1:2)**
5. Expectancy = (0.44 × $100) - (0.56 × $50) = $44 - $28 = **+$16/lệnh**
6. **Có bền vững** — Expectancy dương +$16/lệnh. Sau 100 lệnh kỳ vọng +$1,600 lợi nhuận

---

### Bài tập 3 — Drawdown

1. **Đỉnh cao nhất = $10,550 sau lệnh 4** (và lại đạt $10,550 sau lệnh 10)
2. **Drawdown tối đa**: Từ đỉnh $10,550 (sau lệnh 4) xuống $10,150 (sau lệnh 8)
   - MDD = ($10,550 - $10,150) ÷ $10,550 = $400 ÷ $10,550 = **3.8%**
3. Cần **3.94%** lợi nhuận từ $10,150 để về $10,550
4. **Không nên dừng giao dịch** vì drawdown 3.8% còn rất nhỏ và nằm trong vùng bình thường. Chỉ dừng khi drawdown > 10% trong tháng hoặc > 20% tổng thể.

---

### Bài tập 4 — Case Study Hùng

**Câu 1:** Với 1% risk/lệnh từ $10,000 ($100/lệnh), ngay cả 2 lệnh thua rất lớn cũng chỉ mất tối đa $200. Tháng 1 sẽ kết thúc với P&L dương vì có 8 lệnh thắng vs 4 thua, tài khoản khoảng $10,400-$10,600.

**Câu 2:** Sai lầm lớn nhất là **Revenge Trading** — tăng size sau khi thua để "gỡ gạc". Anh Hùng nên: Dừng giao dịch sau 3 lệnh thua liên tiếp, xem lại nhật ký giao dịch, không thay đổi quy tắc quản lý vốn.

**Câu 3:** Còn $2,100, cần về $10,000:
- Cần tăng = ($10,000 - $2,100) ÷ $2,100 = $7,900 ÷ $2,100 = **376%** — gần như bất khả thi!

**Câu 4:** Trading Plan đề xuất:
```
- % risk mỗi lệnh: 1% ($100 với $10,000)
- R:R tối thiểu: 1:2
- Thua 3 lệnh liên tiếp: nghỉ hôm đó
- Drawdown tuần > 3%: giảm size 50%
- Drawdown tháng > 7%: dừng giao dịch, review
- Không thay đổi SL khi đang thua
- Ghi chép mọi lệnh vào Trading Journal
```
