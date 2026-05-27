# Tài Liệu Tham Khảo — Ngày 28: Trend, Support & Resistance

## Cheat Sheet: Nhận Diện Xu Hướng

### Uptrend
```
Dấu hiệu xác nhận:
✅ HH1 < HH2 < HH3 (đỉnh sau cao hơn đỉnh trước)
✅ HL1 < HL2 < HL3 (đáy sau cao hơn đáy trước)
✅ Giá trên đường MA (Moving Average)
✅ MA ngắn hạn trên MA dài hạn

Tín hiệu cảnh báo đảo chiều:
⚠️ HL bị phá vỡ (giá tạo đáy thấp hơn HL trước)
⚠️ HH không thể tạo mới (giá không lên được đỉnh cũ)
```

### Downtrend
```
Dấu hiệu xác nhận:
✅ LH1 > LH2 > LH3 (đỉnh sau thấp hơn đỉnh trước)
✅ LL1 > LL2 > LL3 (đáy sau thấp hơn đáy trước)
✅ Giá dưới đường MA
✅ MA ngắn hạn dưới MA dài hạn

Tín hiệu cảnh báo đảo chiều:
⚠️ LH bị phá vỡ lên (giá tạo đỉnh cao hơn LH trước)
⚠️ LL không thể tạo mới (đáy mới không thấp hơn đáy trước)
```

## Bảng: Các Mức Hỗ Trợ & Kháng Cự Phổ Biến

| Loại | Ví dụ | Độ mạnh |
|------|-------|---------|
| Mức số tròn | 1,000 điểm VNI, $50,000 BTC | Cao |
| Đỉnh/đáy lịch sử | All-time high/low | Rất cao |
| Đỉnh/đáy 52 tuần | 52-week high/low | Cao |
| Trendline | Điểm chạm thứ 3+ | Cao |
| Gap (khoảng trống) | Vùng gap chưa lấp | Trung bình |
| Moving Average | MA20, MA50, MA200 | Trung bình-Cao |
| Fibonacci Level | 38.2%, 50%, 61.8% | Trung bình |
| Previous S/R đã bị phá | Role reversal | Cao |

## Công Thức Tính Target Sau Breakout

### Phương pháp Measured Move (Di Chuyển Đo Lường)
```
Chiều cao của sideway = Resistance - Support
Target sau Breakout = Resistance + Chiều cao sideway

Ví dụ:
- Sideway: Support tại 45,000 VND, Resistance tại 50,000 VND
- Chiều cao = 50,000 - 45,000 = 5,000 VND
- Target = 50,000 + 5,000 = 55,000 VND
```

## Checklist Breakout Thật vs Fake

| Tiêu chí | Breakout Thật | Fake Breakout |
|----------|--------------|---------------|
| Đóng cửa | Rõ ràng trên/dưới | Chạm rồi quay lại |
| Volume | Tăng vọt (>1.5x TB) | Thấp hoặc bình thường |
| Nến breakout | Marubozu / thân lớn | Nhỏ, nhiều bóng |
| Ngày hôm sau | Tiếp tục xu hướng | Quay lại vùng cũ |
| Retest | Nếu có, giữ vững | Không giữ vững |

## Chiến Lược Giao Dịch S/R

### Chiến lược 1: Bounce Trading (Giao dịch nảy)
```
Tình huống: Uptrend, giá pullback về hỗ trợ
1. Xác nhận hỗ trợ (vùng giá quan trọng)
2. Đợi tín hiệu nến bullish (Hammer, Engulfing...)
3. Mua khi nến xác nhận đóng cửa
4. Stop-loss: Dưới đáy của vùng hỗ trợ
5. Target: Đỉnh gần nhất (HH)
```

### Chiến lược 2: Breakout Trading
```
Tình huống: Giá sideway, chuẩn bị breakout
1. Xác định vùng kháng cự rõ ràng
2. Quan sát volume tích lũy trước breakout
3. Mua sau khi nến đóng cửa trên kháng cự + volume lớn
4. Stop-loss: Dưới điểm kháng cự cũ (bây giờ là hỗ trợ)
5. Target: Measured Move
```

### Chiến lược 3: Retest Entry (Vào lệnh khi retest)
```
Tình huống: Breakout đã xảy ra, chờ giá quay về "hôn" lại vùng cũ
1. Sau breakout, đợi giá pullback về vùng kháng cự cũ
2. Quan sát giá bounces từ vùng đó (role reversal)
3. Mua khi có tín hiệu nến bullish tại vùng retest
4. Stop-loss: Dưới vùng retest
5. Target: Tương tự breakout trading
Ưu điểm: Entry tốt hơn, R/R tốt hơn
```

## Tài Liệu Đọc Thêm

**Sách:**
- *Technical Analysis of the Financial Markets* — John J. Murphy (kinh điển, bắt buộc)
- *How to Make Money in Stocks* — William O'Neil (phần về pivot points và breakout)
- *Trading in the Zone* — Mark Douglas (tâm lý giao dịch)

**Website:**
- TradingView.com — vẽ trendline, S/R trực quan
- Investing.com — biểu đồ nhiều thị trường
- Finviz.com — screener cổ phiếu theo pattern

## Ghi Chú Nâng Cao

**Thời gian thích hợp của hỗ trợ:**
- Hỗ trợ/kháng cự càng **cũ** thì càng yếu dần (nhưng vẫn có giá trị)
- Hỗ trợ/kháng cự được **test nhiều lần** thì khi bị phá vỡ, động lực di chuyển càng mạnh
  - Lý do: Mỗi lần test thành công, lệnh stop-loss tích tụ ngay sau đó. Khi phá vỡ, stop-loss kích hoạt ồ ạt → giá di chuyển nhanh

**Volume Profile (Hồ sơ khối lượng):**
- Trên TradingView, tính năng Volume Profile cho thấy vùng giá nào có nhiều giao dịch nhất
- Vùng có nhiều giao dịch = hỗ trợ/kháng cự mạnh
- Vùng ít giao dịch = giá di chuyển nhanh qua (thin air)

**Psychological Round Numbers (Mức tâm lý):**
- $100, $1,000, $10,000, $100,000 (Bitcoin)
- 1,000, 1,200, 1,500 (VN-Index)
- Tại sao mạnh? Vì con người thích đặt lệnh tại số tròn
