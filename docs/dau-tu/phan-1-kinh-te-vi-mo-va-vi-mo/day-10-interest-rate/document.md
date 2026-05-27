# Tài liệu tham khảo — Ngày 10: Lãi Suất (Interest Rate)

## Bảng tóm tắt: Tác động của lãi suất đến các loại tài sản

| Tài sản | Lãi suất TĂNG | Lãi suất GIẢM | Ghi chú |
|---------|--------------|--------------|---------|
| **Cổ phiếu (chung)** | Tiêu cực ↓ | Tích cực ↑ | Discount rate tăng → P/E giảm |
| **Growth Stocks (Công nghệ)** | Rất tiêu cực ↓↓ | Rất tích cực ↑↑ | Dòng tiền xa tương lai, nhạy cảm nhất |
| **Ngân hàng** | Thường tích cực ↑ | Tiêu cực ↓ | NIM tăng khi lãi suất cao |
| **Utilities/REIT** | Tiêu cực ↓ | Tích cực ↑ | Cạnh tranh với trái phiếu |
| **Trái phiếu dài hạn** | Rất tiêu cực ↓↓ | Rất tích cực ↑↑ | Duration cao, biến động lớn |
| **Trái phiếu ngắn hạn** | Ít tiêu cực ↓ | Ít tích cực ↑ | Duration thấp |
| **USD** | Tích cực ↑ | Tiêu cực ↓ | Dòng tiền vào Mỹ tăng |
| **Vàng** | Tiêu cực ↓ (ngắn hạn) | Tích cực ↑ | Vàng không trả lãi, cạnh tranh kém |
| **Bất động sản** | Tiêu cực ngắn hạn ↓ | Tích cực ↑ | Lãi vay tăng → cầu giảm |
| **Bitcoin/Crypto** | Tiêu cực ↓ | Tích cực ↑ | Vẫn là "risk asset" tương quan Nasdaq |

---

## Yield Curve — Cheat Sheet

```
NORMAL CURVE       FLAT CURVE         INVERTED CURVE
(Bình thường)      (Phẳng)            (Đảo ngược)

Yield                Yield              Yield
  |        ●●●        |  ●●●●●●●         |●●●
  |    ●●●            |                  |    ●●●
  | ●●                |                  |        ●●●●●
  +-------→ Time    +-------→ Time     +-------→ Time

Tín hiệu:          Tín hiệu:           Tín hiệu:
Kinh tế tốt,       Chuyển tiếp,        CẢNH BÁO MẠNH
tăng trưởng        kinh tế giảm tốc    Suy thoái trong
bình thường                            12-18 tháng nữa
```

---

## Công thức quan trọng

```
1. Fisher Equation:
   Real Rate = Nominal Rate - Inflation Rate

2. Approximate Bond Price Change:
   % Price Change ≈ -Duration × % Change in Yield

   Ví dụ: Duration = 8 năm, lãi suất tăng 1%
   % Price Change ≈ -8 × 1% = -8%

3. Discount Rate & Valuation:
   PV = CF / (r - g)
   PV = Giá trị hiện tại
   CF = Dòng tiền kỳ vọng
   r = Discount rate (lãi suất chiết khấu)
   g = Tốc độ tăng trưởng

4. Mortgage Payment (Trả góp BĐS):
   M = P × [r(1+r)^n] / [(1+r)^n - 1]
   M = Số tiền trả hàng tháng
   P = Vốn vay
   r = Lãi suất tháng (= lãi suất năm / 12)
   n = Số tháng vay
```

---

## Lãi suất chính sách các NHTW lớn (tham khảo 2024)

| NHTW | Quốc gia | Lãi suất (2024) | Xu hướng |
|------|---------|----------------|---------|
| **Fed** | Mỹ | 5.25-5.5% | Bắt đầu cắt giảm |
| **ECB** | Eurozone | 4.0% | Cắt giảm |
| **BOJ** | Nhật Bản | 0.1% | Tăng nhẹ (thoát âm) |
| **BOE** | Anh | 5.0% | Cắt giảm |
| **RBA** | Úc | 4.35% | Giữ nguyên |
| **PBOC** | Trung Quốc | 3.45% | Cắt giảm (hỗ trợ kinh tế) |
| **NHNN** | Việt Nam | 4.5% | Giữ/Cắt giảm nhẹ |

*Lưu ý: Lãi suất thay đổi liên tục, tham khảo nguồn mới nhất khi cần.*

---

## Timeline Fed Funds Rate trong lịch sử

| Giai đoạn | Lãi suất | Bối cảnh |
|-----------|---------|---------|
| 1980 | 20% | Paul Volcker chống lạm phát 14% |
| 1990-1992 | 3% | Hỗ trợ sau recession |
| 2000-2003 | 1% | Hỗ trợ sau Dot-com crash |
| 2004-2006 | 5.25% | Thắt chặt trước khủng hoảng |
| 2008-2015 | 0-0.25% | Hỗ trợ sau Financial Crisis |
| 2018-2019 | 2.5% | Thắt chặt dần |
| 2020-2021 | 0-0.25% | COVID support |
| 2022-2023 | 5.5% | Đánh bại lạm phát 9.1% |
| 2024 | 5.25-5.5% | Bắt đầu pivot |

---

## Tài liệu đọc thêm

### Sách
- **"The Courage to Act" — Ben Bernanke:** Hồi ký của Chủ tịch Fed trong cuộc khủng hoảng 2008 — cực kỳ hay
- **"A History of Interest Rates" — Sidney Homer & Richard Sylla:** Lịch sử lãi suất 5.000 năm (cho người muốn hiểu sâu)
- **"The Bond King" — Mary Childs:** Tiểu sử Bill Gross, người thống trị thị trường trái phiếu Mỹ

### Website & Tools
- **federalreserve.gov** — Trang chủ Fed: họp FOMC, thông cáo, phát biểu
- **cmegroup.com/markets/interest-rates/cme-fedwatch-tool** — FedWatch Tool: xem xác suất thị trường đặt cược cho từng kịch bản lãi suất
- **fred.stlouisfed.org/series/FEDFUNDS** — Lịch sử Fed Funds Rate từ 1954
- **fred.stlouisfed.org/series/T10Y2Y** — Yield Curve 10Y-2Y thời gian thực
- **sbv.gov.vn** — NHNN Việt Nam: lãi suất điều hành, tỷ giá

### Video
- "Interest Rates Explained" — Khan Academy (YouTube) — Cơ bản nhất
- "How does raising interest rates control inflation?" — Investopedia (YouTube)
- Fed Press Conferences — Họp báo Chủ tịch Fed sau mỗi cuộc họp FOMC (YouTube: Federal Reserve channel)

---

## Ghi chú nâng cao: Taylor Rule

**Taylor Rule** là công thức lý thuyết giúp ước tính lãi suất "phù hợp" mà Fed nên đặt ra:

```
i = r* + π + 0.5(π - π*) + 0.5(y - y*)

Trong đó:
i = Lãi suất danh nghĩa cần thiết
r* = Lãi suất thực dài hạn (~2%)
π = Lạm phát hiện tại
π* = Lạm phát mục tiêu (2%)
y = GDP tăng trưởng thực tế
y* = GDP tiềm năng
```

Đây không phải công thức Fed dùng cứng nhắc, nhưng là benchmark để đánh giá Fed đang "hawk" hay "dove" so với lý thuyết.
