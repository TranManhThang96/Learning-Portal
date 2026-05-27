# Tài Liệu Tham Khảo — Ngày 22: Valuation Ratios

## Cheat Sheet: Tất Cả Valuation Ratios Quan Trọng

| Chỉ số | Công thức | Ngưỡng tốt (tham khảo) | Dùng khi nào |
|--------|-----------|------------------------|-------------|
| P/E | Price / EPS | Tùy ngành (8-30x thông thường) | Công ty có lợi nhuận ổn định |
| Forward P/E | Price / Forward EPS | < Trailing P/E = tích cực | Kỳ vọng tương lai |
| PEG | P/E / EPS Growth% | < 1 = hấp dẫn | Công ty tăng trưởng |
| P/B | Price / Book Value Per Share | < 1 = rẻ; >3 = đắt | Ngân hàng, tài sản nhiều |
| P/S | Market Cap / Revenue | Tùy ngành (0.5 - 10x) | Chưa có lợi nhuận |
| EV/EBITDA | EV / EBITDA | 8-15x là hợp lý | So sánh xuyên quốc gia, M&A |
| EV/Sales | EV / Revenue | Tùy ngành | Thay thế P/S khi nợ nhiều |
| ROE | Net Income / Equity | > 15% | Đo hiệu quả vốn cổ đông |
| ROA | Net Income / Assets | > 5% | So sánh ngành đồng nhất |
| ROIC | NOPAT / Invested Capital | > 15%, tốt nhất > WACC | Chất lượng doanh nghiệp |

---

## Công Thức Tổng Hợp

```
EPS = Net Income / Diluted Shares Outstanding

P/E = Share Price / EPS
    = Market Cap / Net Income

PEG = P/E / Annual EPS Growth Rate (%)

P/B = Share Price / Book Value Per Share
    = Market Cap / Total Equity

P/S = Market Cap / Annual Revenue

EV = Market Cap + Total Debt + Minority Interest - Cash & Equivalents

EBITDA = EBIT + Depreciation + Amortization
       = Net Income + Interest + Taxes + D&A

EV/EBITDA = EV / EBITDA

ROE = Net Income / Average Shareholders' Equity × 100%

ROA = Net Income / Average Total Assets × 100%

ROIC = NOPAT / Invested Capital × 100%
NOPAT = EBIT × (1 - Tax Rate)
Invested Capital = Total Equity + Total Debt - Cash
```

---

## P/E Trung Bình Theo Ngành (Tham Khảo — Việt Nam & Mỹ)

| Ngành | P/E VN (tham khảo) | P/E Mỹ (tham khảo) | Ghi chú |
|-------|-------------------|-------------------|---------|
| Công nghệ | 20 - 40x | 30 - 60x | Tăng trưởng cao |
| Ngân hàng | 8 - 14x | 10 - 15x | Đặc thù ngành |
| Bất động sản | 10 - 20x | 15 - 25x | Biến động nhiều |
| Thực phẩm & đồ uống | 15 - 25x | 20 - 30x | Ổn định |
| Dược phẩm | 15 - 30x | 20 - 40x | Tùy pipeline |
| Điện, năng lượng | 10 - 20x | 15 - 25x | Dòng tiền ổn định |
| Bán lẻ | 10 - 20x | 15 - 30x | Margin thấp |
| Thép, vật liệu | 5 - 15x | 10 - 20x | Chu kỳ cao |

*Lưu ý: Các con số này mang tính tham khảo và thay đổi theo điều kiện thị trường.*

---

## Ma Trận Định Giá: Chất Lượng vs Định Giá

```
                    ĐỊNH GIÁ
                 RẺ          ĐẮT
              ┌──────────┬──────────┐
    CHẤT   TỐT│ KHU VỰC  │  GIÁ ĐÃ │
    LƯỢNG     │ TÌM KIẾM │ PHẢN ÁNH│
              │  ★★★★★   │  ★★★    │
              ├──────────┼──────────┤
           XẤU│ BẪY GIÁ  │ TRÁNH   │
              │  TRỊ     │  XA     │
              │  ★★      │  ★      │
              └──────────┴──────────┘
```

**Khu vực tìm kiếm**: Doanh nghiệp chất lượng cao + định giá hợp lý/rẻ = cơ hội tốt nhất
**Bẫy giá trị**: Rẻ nhưng xấu — thường tiếp tục xấu đi
**Giá đã phản ánh**: Tốt nhưng đắt — cần tăng trưởng thật sự để biện hộ

---

## DuPont Analysis — Phân Tích ROE Sâu Hơn

ROE có thể cao vì 3 lý do khác nhau:

```
ROE = Net Profit Margin × Asset Turnover × Financial Leverage
    = (Net Income/Revenue) × (Revenue/Assets) × (Assets/Equity)
```

| Công ty | Net Margin | Asset Turnover | Leverage | ROE |
|---------|------------|----------------|----------|-----|
| Apple | Cao (25%) | Trung bình | Thấp | Cao → Chất lượng cao |
| Siêu thị | Thấp (2%) | Cao | Thấp | Trung bình → OK |
| Ngân hàng rủi ro | Thấp (5%) | Thấp | Rất cao (10x) | Cao → Nguy hiểm! |

**Bài học**: ROE cao không tự động tốt — cần kiểm tra nguồn gốc của ROE cao.

---

## Tài Liệu Đọc Thêm

**Sách:**
- *One Up On Wall Street* — Peter Lynch (người tạo ra PEG ratio)
- *The Little Book That Still Beats the Market* — Joel Greenblatt (Magic Formula: ROIC + EY)
- *What Works on Wall Street* — James O'Shaughnessy (nghiên cứu định lượng về các chỉ số)

**Website tra cứu chỉ số:**
- **Macrotrends.net**: Lịch sử P/E, P/B của cổ phiếu Mỹ
- **Wisesheets / Stockanalysis.com**: Nhanh chóng tra cứu ratios
- **Vietstock.vn / Cafef.vn**: Ratios cổ phiếu Việt Nam
- **Damodaran Online (pages.stern.nyu.edu/~adamodar)**: Dữ liệu P/E, EV/EBITDA theo ngành toàn cầu — của giáo sư Aswath Damodaran (miễn phí, rất uy tín)

---

## Ghi Chú: Adjusted vs GAAP Earnings

Nhiều công ty báo cáo hai loại lợi nhuận:
- **GAAP EPS**: Theo chuẩn kế toán — phải bao gồm stock-based compensation, amortization of intangibles
- **Non-GAAP / Adjusted EPS**: Loại bỏ các khoản "một lần" — thường cao hơn GAAP

> Khi media nói "P/E của Nasdaq trung bình 25x", họ thường dùng **Forward Non-GAAP EPS**.
> Khi so sánh, hãy chắc chắn dùng **cùng loại EPS** cho cả hai công ty.
