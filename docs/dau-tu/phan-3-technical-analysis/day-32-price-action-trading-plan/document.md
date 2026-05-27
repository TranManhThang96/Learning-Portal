# Tài liệu tham khảo — Ngày 32: Price Action & Trading Plan

## Cheat Sheet: Mô hình Price Action

### Pin Bar — Nhận diện nhanh

```
VALID BULLISH PIN BAR:        INVALID (không phải Pin Bar):
    ─── ← bóng trên ngắn          ───────  ← bóng trên dài
    │█│ ← thân nhỏ (≤ 1/3)        │█████│ ← thân quá lớn
    │   ← bóng dưới dài (≥ 2/3)   ─────── ← bóng dưới ngắn
    │
    │   ← bóng phải ≥ 2x thân
```

**Tiêu chí Pin Bar mạnh:**
- Bóng dài ≥ 2/3 tổng chiều dài nến
- Thân nến nhỏ, nằm gần 1 đầu của nến
- Xuất hiện tại Key Level (không phải giữa trời)
- Volume > trung bình (lý tưởng)

### Inside Bar — Nhận diện nhanh

```
MOTHER BAR         INSIDE BAR
───────────        ────────     ← High IB ≤ High MB
│         │           │█│
│  MOTHER │           │█│      ← Inside Bar hoàn toàn
│   BAR   │           │█│         nằm trong Mother Bar
│         │        ────────     ← Low IB ≥ Low MB
───────────
```

**Breakout Inside Bar:**
- Buy Stop: 1 tick trên đỉnh Inside Bar
- Sell Stop: 1 tick dưới đáy Inside Bar
- Stop-loss: Phía bên kia đỉnh/đáy Mother Bar

---

## Bảng so sánh: Phong cách giao dịch

| Tiêu chí | Scalping | Day Trading | Swing Trading | Position Trading |
|----------|----------|-------------|---------------|-----------------|
| Thời gian giữ lệnh | Phút | Giờ | Ngày - Tuần | Tuần - Tháng |
| Timeframe chính | 1M-5M | 15M-1H | 4H-Daily | Weekly-Monthly |
| Số lệnh/ngày | 10-50 | 2-10 | 2-5/tuần | 1-5/tháng |
| Yêu cầu thời gian | Toàn thời gian | Toàn thời gian | Bán thời gian | Ít thời gian |
| Phù hợp với | Trader chuyên nghiệp | Người rảnh rỗi | Người có việc làm | Nhà đầu tư |
| Khó khăn | Spread/phí lớn, stress | Đòi hỏi kỷ luật cao | Cần kiên nhẫn | Cần vốn lớn |

**Gợi ý cho người mới:** Bắt đầu với **Swing Trading** (Daily chart) — đủ thời gian phân tích, không cần ngồi màn hình cả ngày.

---

## Framework: Multi-timeframe Analysis

```
TIMEFRAME HIERARCHY:

Monthly  ─────────────────────────────────► Big Picture
Weekly   ──────────────────────►            Trend Direction
Daily    ─────────────────►                 Setup & Entry Zone
4H/1H    ──────────►                        Precise Entry
15M/5M   ──►                                Scalping only

RULE: Chỉ giao dịch khi ít nhất 2/3 timeframe cùng chiều
```

### Decision Matrix: Nên vào lệnh hay không?

| Weekly | Daily | 4H | Quyết định |
|--------|-------|----|------------|
| Bullish | Bullish | Bullish | Ưu tiên kịch bản long nếu R:R đạt chuẩn |
| Bullish | Bullish | Bearish | Chờ 4H xác nhận |
| Bullish | Bearish | Bearish | Không vào (conflict) |
| Bearish | Bearish | Bearish | Ưu tiên kịch bản short nếu R:R đạt chuẩn |
| Sideways | Bullish | Bullish | Chỉ cân nhắc vị thế nhỏ, cẩn thận fakeout |

---

## Template: Trading Plan cá nhân

```markdown
# TRADING PLAN — [Tên của bạn]
Ngày tạo: ___________  |  Phiên bản: 1.0

## 1. MỤC TIÊU
- Mục tiêu học tập: _______________
- Mục tiêu lợi nhuận (thực tế): ___% / năm
- Vốn ban đầu: ___________ VND

## 2. THỊ TRƯỜNG & TIMEFRAME
- Thị trường: [ ] Chứng khoán VN  [ ] Forex  [ ] Crypto
- Timeframe chính: _______________
- Timeframe cao hơn để xác nhận xu hướng: _______________

## 3. SETUP GIAO DỊCH (Chỉ giao dịch khi đủ điều kiện)
Setup tôi sử dụng: _______________
Điều kiện vào lệnh:
  □ Điều kiện 1: _______________
  □ Điều kiện 2: _______________
  □ Điều kiện 3: _______________

## 4. QUẢN LÝ RỦI RO
- Tổng vốn trading: ___________ VND
- Risk per trade: ___% = ___________ VND
- Risk/Reward tối thiểu: 1:___
- Số lệnh tối đa cùng lúc: ___ lệnh
- Max drawdown chấp nhận: ___%
- Nếu chạm max drawdown: [Hành động cụ thể]

## 5. QUY TẮC BẮT BUỘC
1. LUÔN đặt Stop-loss trước khi vào lệnh
2. KHÔNG dịch Stop-loss ra xa khi lệnh đang lỗ
3. KHÔNG revenge trading sau khi thua
4. KHÔNG trading khi cảm xúc không ổn định
5. [Quy tắc bổ sung của riêng bạn]

## 6. TRADING JOURNAL
Ghi chép mỗi lệnh: [Link file/Notebook]
Review định kỳ: [ ] Hàng tuần  [ ] Hàng tháng
```

---

## Template: Trading Journal (Nhật ký giao dịch)

| Cột | Nội dung |
|-----|---------|
| Ngày | DD/MM/YYYY |
| Mã/Cặp | VD: FPT, EURUSD, BTC |
| Hướng | Long / Short |
| Giá vào | ____________ |
| Stop-loss | ____________ |
| Take-profit | ____________ |
| R:R | 1:___ |
| Setup | Pin Bar / Engulfing / Inside Bar / ... |
| Timeframe | Daily / 4H / 1H |
| Kết quả | Thắng / Thua / Breakeven |
| P/L (VND) | +/- ___________ |
| % vốn | +/- ___% |
| Cảm xúc khi vào | Calm / FOMO / Revenge / ... |
| Bài học | __________________________ |

---

## Tài liệu đọc thêm

**Sách về Price Action:**
- *Price Action Trading* — Nial Fuller (Free trên website của tác giả)
- *Trading in the Zone* — Mark Douglas (Tâm lý + Trading Plan)
- *The Daily Trading Coach* — Brett Steenbarger

**Sách về kỷ luật và tâm lý:**
- *Reminiscences of a Stock Operator* — Edwin Lefèvre (Classic)
- *Market Wizards* — Jack D. Schwager

**Website:**
- Learn to Trade the Market (Nial Fuller): https://www.learntotradethemarket.com
- TradingView Pine Script (tự viết indicator): https://www.tradingview.com/pine-script-docs/

---

## Ghi chú: Backtesting chiến lược

Trước khi giao dịch thật, hãy **backtest** (kiểm tra lịch sử):

1. Mở TradingView, chọn cổ phiếu/cặp tiền bạn muốn giao dịch
2. Cuộn biểu đồ về 1-2 năm trước
3. Tìm các setup theo tiêu chí của bạn
4. Giả sử vào lệnh theo setup, ghi lại kết quả
5. Sau 50-100 lệnh: tính tỷ lệ thắng, R:R trung bình, max drawdown

**Kết quả backtest tốt:** Win rate > 40% với R:R > 1:2 là đủ để có lợi nhuận dài hạn.

**Lưu ý:** Backtest tốt không đảm bảo forward test cũng tốt — tâm lý khi trading thật khác hoàn toàn. Khi backtest, hãy tính cả phí giao dịch, trượt giá, các lệnh thua liên tiếp và tránh nhìn trước dữ liệu tương lai. Nếu phải thay đổi quá nhiều tham số để chiến lược đẹp lên trên quá khứ, đó có thể là **overfitting** chứ không phải lợi thế thật.
