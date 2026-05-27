# Bài tập — Ngày 52: Thực hành Tổng hợp Forex

## Phần 1: Kiểm tra kiến thức tổng hợp Module Forex

1. Thị trường Forex giao dịch bao nhiêu USD mỗi ngày?
   - A. $500 triệu
   - B. $7 tỷ
   - C. $7 nghìn tỷ (trillion)
   - D. $70 tỷ

2. Trader mua EUR/USD tại 1.0850, đặt SL tại 1.0800 (50 pips), TP tại 1.0950 (100 pips). Risk/Reward là:
   - A. 1:1
   - B. 1:2
   - C. 2:1
   - D. 1:3

3. Tài khoản $8,000, risk 1.5%, SL 40 pips, EUR/USD (pip value $10/std lot). Position Size đúng là:
   - A. 0.03 lots
   - B. 0.30 lots
   - C. 3.0 lots
   - D. 0.003 lots

4. "Carry Trade" trong Forex có nghĩa là:
   - A. Giao dịch trong phiên London (carry time)
   - B. Vay đồng lãi suất thấp, mua đồng lãi suất cao
   - C. Giữ lệnh qua đêm để tránh spread
   - D. Giao dịch các cặp Major

5. Broker ECN tốt hơn Market Maker vì:
   - A. Spread luôn thấp hơn
   - B. Không có xung đột lợi ích với trader
   - C. Không bao giờ có slippage
   - D. Không cần giấy phép quản lý

6. Sau khi thua 4 lệnh liên tiếp, bạn nên:
   - A. Tăng size để gỡ lại nhanh
   - B. Đổi cặp tiền để đổi vận
   - C. Dừng giao dịch trong ngày, review journal
   - D. Giao dịch nhiều hơn để tăng xác suất thắng

7. Fibonacci Retracement 61.8% được coi là mức:
   - A. Overbought
   - B. "Golden Ratio" — vùng hỗ trợ/kháng cự mạnh nhất
   - C. Entry signal tự động
   - D. Stop Loss chuẩn

8. Phiên giao dịch nào có volume lớn nhất và volatility cao nhất?
   - A. Sydney
   - B. Tokyo
   - C. London + New York overlap
   - D. New York

9. RSI đang ở mức 75 trên H4 chart. Điều này có nghĩa là:
   - A. Tín hiệu mua mạnh
   - B. Thị trường overbought — cẩn thận với lệnh mua
   - C. Tín hiệu bán ngay lập tức
   - D. RSI không có ý nghĩa ở mức 75

10. Trading Journal quan trọng nhất vì:
    - A. Giúp bạn biết tổng lợi nhuận/lỗ
    - B. Giúp nhận ra pattern hành vi và cải thiện qua thời gian
    - C. Yêu cầu bắt buộc của broker
    - D. Giúp tính thuế chính xác

---

## Phần 2: Bài tập thực hành tổng hợp

Các bài thực hành dưới đây chỉ thực hiện trên tài khoản demo hoặc dữ liệu lịch sử. Không chuyển thành lệnh tiền thật nếu chưa có Trading Plan, kiểm tra broker độc lập và giới hạn rủi ro rõ ràng.

### Bài tập 1: Phân tích EUR/USD hoàn chỉnh

Sử dụng tài khoản demo và chart thực tế, thực hiện phân tích đầy đủ theo quy trình Top-Down:

**Bước 1: Macro Analysis**
- Kiểm tra Economic Calendar tuần này: Có tin tức High Impact nào về EUR và USD?
- Fed đang Hawkish hay Dovish? ECB đang Hawkish hay Dovish?
- Dựa vào Interest Rate Differential, bias của bạn cho EUR/USD là gì?

Ghi lại: Bias là _______________ vì _______________

**Bước 2: Weekly Chart (W1)**
- Xu hướng dài hạn là gì?
- Support/Resistance quan trọng nhất ở mức nào?
- Giá đang ở vùng nào của xu hướng?

Ghi lại: Xu hướng dài hạn _______________, S/R quan trọng _______________

**Bước 3: Daily Chart (D1)**
- Xu hướng trung hạn?
- Có mô hình gì đặc biệt không?

**Bước 4: H4 Chart**
- Tìm setup: Có tín hiệu không?
- Entry cụ thể ở đâu?
- SL ở đâu? (dưới Support hoặc trên Resistance)
- TP ở đâu? R:R là bao nhiêu?

**Bước 5: Tính Position Size**
- Tài khoản: $10,000
- Risk: 1%
- SL distance: ___ pips
- Position Size: ___ lots

**Bước 6: Thực hiện lệnh demo và ghi Journal**

**Risk checkpoint trước khi bấm lệnh demo:**
- Rủi ro/lệnh: tối đa 1% tài khoản demo
- R:R: tối thiểu 1:2
- SL/TP: nhập sẵn trước khi xác nhận lệnh
- Tin High Impact: không vào lệnh trong 30 phút trước/sau tin

---

### Bài tập 2: Backtest 20 lệnh

Thực hiện backtest thủ công chiến lược EMA 20/50 + RSI trên EUR/USD H4:

1. Mở chart EUR/USD H4 trên MT4 hoặc TradingView
2. Thêm EMA 20 (màu xanh) và EMA 50 (màu đỏ), RSI 14
3. Kéo về 3-6 tháng trước
4. Lần lượt xem từng nến, đánh dấu khi EMA 20 cắt EMA 50
5. Ghi chép vào bảng sau:

| # | Ngày | Direction | Entry | SL | TP | Kết quả | Pips |
|---|------|-----------|-------|----|----|---------|------|
| 1 | | | | | | W/L | |
| 2 | | | | | | W/L | |
| ... | | | | | | | |
| 20 | | | | | | | |

**Sau 20 lệnh, tính:**
- Win Rate = _____ %
- Average Win = _____ pips
- Average Loss = _____ pips  
- Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss) = _____ pips
- Nhận xét: Chiến lược này có promising không?

---

### Bài tập 3: Hoàn thiện Trading Plan

Điền đầy đủ vào template Trading Plan trong bài học. Sau khi hoàn thành:
1. In ra (hoặc lưu ở nơi dễ thấy)
2. Đọc lại mỗi sáng trước khi giao dịch trong 1 tuần đầu
3. Ký tên vào phần cam kết

**Checklist Trading Plan hoàn chỉnh:**
- [ ] Đã xác định phong cách giao dịch
- [ ] Đã chọn 2-3 cặp tiền cụ thể
- [ ] Đã có quy tắc entry và exit rõ ràng
- [ ] Đã xác định % risk và quy tắc position sizing
- [ ] Đã có quy tắc dừng (drawdown limits)
- [ ] Đã lên lịch review định kỳ

---

### Bài tập 4: Cam kết Demo 90 ngày

Viết "Cam kết Demo 90 ngày" của bạn:

```
CAM KẾT DEMO 90 NGÀY

Tôi, _____________________, cam kết:

1. Giao dịch tài khoản demo từ ngày ___ đến ngày ___

2. Trong 90 ngày này, tôi sẽ:
   □ Thực hiện ít nhất ___ lệnh
   □ Ghi chép 100% lệnh vào Trading Journal
   □ Không chuyển sang live cho đến khi đạt tiêu chí

3. Tiêu chí để chuyển sang live:
   □ Profitable trong ít nhất 2 tháng liên tiếp
   □ Win Rate > 40% qua ít nhất 50 lệnh
   □ Max Drawdown < 10%
   □ Không vi phạm quy tắc Trading Plan nghiêm trọng

4. Review định kỳ:
   □ Hàng tuần: Thứ 6 tối, review tuần
   □ Hàng tháng: Ngày cuối tháng, tổng kết

Ngày ký: _______________
Chữ ký: _______________
```

---

## Phần 3: Bài tập tổng kết Module Forex

### Tổng kết tự đánh giá

Đánh giá mức độ tự tin của bạn với từng chủ đề (1 = Chưa hiểu, 5 = Rất tự tin):

| Chủ đề | Mức độ tự tin (1-5) | Cần ôn thêm? |
|--------|---------------------|--------------|
| Cấu trúc thị trường Forex (cặp tiền, session) | | |
| Tính Pip Value và P&L | | |
| Phân tích cơ bản Forex (lãi suất, GDP, CPI) | | |
| Carry Trade và theo dõi Central Bank | | |
| Fibonacci Retracement | | |
| Support & Resistance | | |
| Trend Following strategies | | |
| Tính Position Size | | |
| Risk/Reward Ratio | | |
| Kiểm soát cảm xúc (FOMO, Revenge Trading) | | |
| Chọn và kiểm tra broker uy tín | | |
| Sử dụng MT4/TradingView | | |

**Chủ đề nào dưới 3 điểm?** → Ôn lại bài học tương ứng trước khi bắt đầu thực hành demo.

---

## Đáp án Quiz

1. **C — $7 nghìn tỷ (trillion) USD/ngày** — Forex là thị trường tài chính lớn nhất thế giới
2. **B — 1:2** (50 pips risk : 100 pips profit)
3. **B — 0.30 lots**: Risk = 1.5% × $8,000 = $120; Position = $120 ÷ (40 × $10) = $120/$400 = 0.30 lots
4. **B — Vay đồng lãi suất thấp, mua đồng lãi suất cao**
5. **B — Không có xung đột lợi ích** — ECN kết nối trader với LP, không làm counterparty
6. **C — Dừng giao dịch trong ngày, review journal**
7. **B — "Golden Ratio"** — Fibonacci 61.8% là vùng quan trọng nhất
8. **C — London + New York overlap** (19:00-23:00 giờ Việt Nam)
9. **B — Thị trường overbought** — RSI > 70 là tín hiệu cẩn thận, không phải bán ngay
10. **B — Nhận ra pattern hành vi và cải thiện** — Đây là giá trị cốt lõi của Trading Journal
