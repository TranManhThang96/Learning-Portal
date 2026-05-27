# Bài tập — Ngày 44: Pip, Lot, Leverage & Spread

## Phần 1: Câu hỏi ôn tập (Quiz)

**1. EUR/USD di chuyển từ 1.08500 lên 1.08650. Đây là biến động bao nhiêu pip?**
- A. 1.5 pip
- B. 15 pip
- C. 150 pip
- D. 1,500 pip

**2. Với 0.1 lot EUR/USD, mỗi pip có giá trị bao nhiêu USD?**
- A. 0.01 USD
- B. 0.10 USD
- C. 1.00 USD
- D. 10.00 USD

**3. Bạn có 1,000 USD, dùng leverage 1:100. Bạn có thể kiểm soát tối đa bao nhiêu?**
- A. 1,000 USD
- B. 10,000 USD
- C. 100,000 USD
- D. 1,000,000 USD

**4. Spread EUR/USD là 1.5 pip, bạn giao dịch 0.1 lot. Chi phí spread là bao nhiêu?**
- A. 0.015 USD
- B. 0.15 USD
- C. 1.50 USD
- D. 15 USD

**5. Swap âm (-) khi BUY một cặp tiền có nghĩa là gì?**
- A. Bạn nhận tiền mỗi đêm giữ lệnh
- B. Bạn phải trả tiền mỗi đêm giữ lệnh
- C. Lệnh tự động đóng vào midnight
- D. Bạn không thể giữ lệnh qua đêm

**6. Margin Call thường xảy ra khi:**
- A. Bạn kiếm lời quá nhiều
- B. Tài khoản của bạn bị thua lỗ đến mức nguy hiểm
- C. Bạn không đặt Stop Loss
- D. Thị trường đóng cửa

**7. Đâu là kích thước lot nhỏ nhất phổ biến?**
- A. Standard Lot (1.0)
- B. Mini Lot (0.1)
- C. Micro Lot (0.01)
- D. Nano Lot (0.001)

**8. Leverage 1:50 với vốn 2,000 USD → Sức mua là bao nhiêu?**
- A. 20,000 USD
- B. 50,000 USD
- C. 100,000 USD
- D. 200,000 USD

---

## Phần 2: Bài tập tính toán

### Bài tập 1: Tính Pip Value

Tính giá trị 1 pip cho mỗi tình huống sau (EUR/USD tỷ giá 1.0850):

| Tình huống | Lot Size | Pip Value (USD) |
|------------|----------|----------------|
| A | 0.01 | ? |
| B | 0.05 | ? |
| C | 0.2 | ? |
| D | 1.5 | ? |

### Bài tập 2: Tính Lợi nhuận/Thua lỗ

**Tình huống A:**
- Mua GBP/USD tại 1.2650
- Đóng lệnh tại 1.2720
- Kích thước: 0.1 lot
- Spread khi vào: 1.5 pip
- Lợi nhuận/lỗ là bao nhiêu USD?

**Tình huống B:**
- Bán EUR/JPY tại 162.500
- Stop loss chạm ở 163.200
- Kích thước: 0.05 lot
- Tỷ giá EUR/JPY: 162.50
- Thua lỗ là bao nhiêu USD?

*(Gợi ý: Pip value USD/JPY cần chuyển đổi qua USD)*

### Bài tập 3: Tính Kích thước Lệnh (Position Sizing)

Áp dụng quy tắc rủi ro 1% tài khoản:

| Vốn (USD) | % Rủi ro | Stop Loss (pip) | Cặp tiền | Lot Size? |
|-----------|----------|-----------------|----------|-----------|
| 1,000 | 1% | 30 | EUR/USD | ? |
| 3,000 | 2% | 50 | EUR/USD | ? |
| 500 | 1% | 20 | EUR/USD | ? |
| 5,000 | 1.5% | 80 | EUR/USD | ? |

### Bài tập 4: Phân tích Leverage

Bạn có 500 USD. Broker cung cấp leverage 1:200.

1. Bạn có thể kiểm soát tối đa bao nhiêu USD?
2. Nếu bạn mở 1 lot EUR/USD (margin cần ~$543), điều gì xảy ra?
3. Nếu bạn mở 0.1 lot EUR/USD, giá cần di chuyển ngược bao nhiêu pip để mất toàn bộ 500 USD?
4. Với quy tắc rủi ro 1%, bạn nên giao dịch tối đa bao nhiêu lot với stop loss 50 pip?

---

## Phần 3: Case Study — "Anh Nam và Bẫy Leverage"

Anh Nam (35 tuổi, kỹ sư) vừa học về Forex và nghe nói có thể kiếm 10% mỗi tháng. Anh nạp 5,000 USD vào tài khoản broker, leverage tối đa 1:500.

Anh nghĩ: *"Với leverage 1:500, mình có thể kiểm soát 2.5 triệu USD! Chỉ cần giá tăng 10 pip là lãi cả đống tiền!"*

Anh mở **5 lot EUR/USD** (tương đương 500,000 EUR) mua vào khi EUR/USD = 1.0850.
- Margin cần: 500,000 / 500 × 1.0850 = **$1,085**
- Còn lại free margin: $5,000 - $1,085 = $3,915

Ngay hôm đó, dữ liệu CPI Mỹ cao hơn dự báo → USD tăng mạnh → EUR/USD giảm 100 pip xuống 1.0750.

**Câu hỏi phân tích:**
1. Thua lỗ của anh Nam là bao nhiêu USD? (5 lot × 100 pip × $10/pip)
2. Margin Level của anh Nam còn bao nhiêu %?
3. Anh Nam có bị Stop Out không?
4. Nếu anh Nam áp dụng quy tắc rủi ro 1% (= $50), với stop loss 50 pip, anh nên giao dịch bao nhiêu lot?
5. Bài học rút ra là gì?

---

## Đáp án & Giải thích

### Quiz
1. **B — 15 pip** (1.08650 - 1.08500 = 0.00150 = 15 pip)
2. **C — 1.00 USD** (Standard lot = 10 USD/pip; Mini = 1 USD/pip)
3. **C — 100,000 USD** (1,000 × 100 = 100,000)
4. **B — 0.15 USD** (1.5 pip × 0.1 USD/pip = 0.15 USD)
5. **B — Bạn phải trả tiền mỗi đêm giữ lệnh**
6. **B — Tài khoản bị thua lỗ đến mức nguy hiểm**
7. **C — Micro Lot (0.01)**
8. **C — 100,000 USD** (2,000 × 50 = 100,000)

### Bài tập 1: Pip Value
| Tình huống | Lot Size | Pip Value (USD) |
|------------|----------|----------------|
| A | 0.01 | $0.10 |
| B | 0.05 | $0.50 |
| C | 0.2 | $2.00 |
| D | 1.5 | $15.00 |

### Bài tập 2

**Tình huống A (GBP/USD):**
- Di chuyển: 1.2720 - 1.2650 = 70 pip lãi
- Trừ spread: 70 - 1.5 = 68.5 pip net
- Pip value 0.1 lot: $1/pip
- **Lợi nhuận: $68.50**

**Tình huống B (EUR/JPY):**
- Di chuyển: 163.200 - 162.500 = 70 pip ngược chiều (bán mà giá tăng → lỗ)
- Pip value EUR/JPY 0.05 lot: Cần tính
  - 1 pip EUR/JPY = 0.01 JPY
  - 0.05 lot = 5,000 EUR
  - Pip value = (0.01 / 162.50) × 5,000 = 0.3077 USD/pip ≈ $0.31/pip
- **Thua lỗ: 70 pip × $0.31/pip ≈ -$21.54**

### Bài tập 3: Position Sizing
| Vốn | Rủi ro | SL | Rủi ro USD | Lot Size |
|-----|--------|-----|-----------|----------|
| $1,000 | 1% | 30 pip | $10 | 10/(30×1) = **0.03 lot** (làm tròn xuống 0.03) |
| $3,000 | 2% | 50 pip | $60 | 60/(50×1) = **0.12 lot** |
| $500 | 1% | 20 pip | $5 | 5/(20×1) = **0.025 lot** → **0.02 lot** |
| $5,000 | 1.5% | 80 pip | $75 | 75/(80×1) = **0.09 lot** → **0.09 lot** |

### Bài tập 4
1. Sức mua tối đa: 500 × 200 = **$100,000** (khoảng 0.92 lot EUR/USD)
2. Margin cần cho 1 lot = $543, nhưng chỉ có $500 → **KHÔNG THỂ** mở 1 lot. Sẽ bị từ chối.
3. Với 0.1 lot: Pip value = $1/pip. Mất hết $500 khi giá ngược = 500 pip. Nhưng thực tế sẽ Stop Out trước đó.
4. Rủi ro 1% = $5. Stop loss 50 pip. Lot = $5/(50×1) = **0.01 lot** (micro lot)

### Case Study — Anh Nam
1. **Thua lỗ: 5 lot × 100 pip × $10/pip = -$5,000** — Mất toàn bộ vốn!
2. Equity = $5,000 - $5,000 = $0. Margin Level = **0%** → đã bị Stop Out từ trước
3. **Có, bị Stop Out** khi Equity xuống đến ~$542 (khi lỗ khoảng $4,458)
4. Với quy tắc 1% rủi ro ($50), stop loss 50 pip: Lot = $50/(50×$10) = **0.1 lot** (mini lot)
5. **Bài học:**
   - Leverage cao ≠ lợi nhuận cao; nó chỉ khuếch đại thua lỗ
   - Với 5 lot, chỉ cần giá ngược 10 pip → lỗ $500 (10% vốn)
   - Phải luôn dùng Position Sizing dựa trên % rủi ro, không dựa trên "đánh bao nhiêu cho hấp dẫn"
   - Quy tắc vàng: Rủi ro tối đa 1-2% mỗi lệnh
