# Tài liệu tham khảo — Ngày 46: Carry Trade & Central Bank Watch

## Bảng Carry Trade: Lãi suất các NHTW (ví dụ lịch sử 2024)

Bảng này dùng để luyện cơ chế Carry Trade, không phải dữ liệu hiện hành hay khuyến nghị mở lệnh. Khi thực hành, hãy kiểm tra lãi suất, swap của broker, spread và lịch họp NHTW mới nhất.

| Đồng tiền | NHTW | Lãi suất | Vai trò trong Carry |
|-----------|------|---------|---------------------|
| JPY | BOJ | 0.25% | Funding currency (vay) |
| CHF | SNB | 1.00% | Funding currency (vay) |
| EUR | ECB | 3.50% | Trung lập |
| GBP | BOE | 5.00% | Carry currency (đầu tư) |
| USD | Fed | 4.75% | Carry currency (đầu tư) |
| CAD | BOC | 4.25% | Carry currency (đầu tư) |
| AUD | RBA | 4.35% | Carry currency (đầu tư) |
| NZD | RBNZ | 5.25% | Carry currency (đầu tư) |

**Ví dụ carry phổ biến trong giai đoạn đó:**
- BUY NZD/JPY: +5.00% carry/năm
- BUY AUD/JPY: +4.10% carry/năm
- BUY GBP/JPY: +4.75% carry/năm
- BUY USD/JPY: +4.50% carry/năm

---

## Lịch họp NHTW 2024-2025 (mẫu lịch sử)

Không dùng bảng này làm lịch hiện tại. Trước khi giao dịch, luôn kiểm tra lịch mới trên website NHTW hoặc Economic Calendar.

| Tháng | Fed (FOMC) | ECB | BOJ | BOE |
|-------|-----------|-----|-----|-----|
| Jan | ✓ | | ✓ | ✓ |
| Mar | ✓ (Dot Plot) | ✓ | ✓ | ✓ |
| May | ✓ | ✓ | ✓ | ✓ |
| Jun | ✓ (Dot Plot) | ✓ | ✓ | ✓ |
| Jul | ✓ | ✓ | ✓ | ✓ |
| Sep | ✓ (Dot Plot) | ✓ | ✓ | ✓ |
| Oct | ✓ | ✓ | ✓ | ✓ |
| Nov | ✓ | | | ✓ |
| Dec | ✓ (Dot Plot) | ✓ | ✓ | ✓ |

*Lịch chính xác xem tại: federalreserve.gov/monetarypolicy/fomccalendar.htm*

---

## Quy trình đọc FOMC Statement (Cheat Sheet)

```
BƯỚC 1: Đọc dòng đầu tiên
→ Fed tăng/giữ/giảm bao nhiêu?

BƯỚC 2: Đọc phần đánh giá kinh tế
→ Họ nói gì về việc làm? Lạm phát? GDP?
→ So sánh với Statement kỳ trước — có gì thay đổi?

BƯỚC 3: Đọc Forward Guidance (QUAN TRỌNG NHẤT)
→ Tìm từ: "may be appropriate", "ongoing", "some additional"
→ Hawkish hay Dovish hơn kỳ trước?

BƯỚC 4: Kiểm tra biểu quyết
→ Có ai không đồng ý không? Họ muốn gì?

BƯỚC 5: Xem Powell Press Conference
→ Câu hỏi của journalist thường khai thác thêm thông tin
→ Thị trường thường phản ứng lần 2 trong conference
```

---

## Từ điển Hawkish/Dovish trong FOMC Statement

| Ngôn ngữ trong Statement | Ý nghĩa | Tác động USD |
|--------------------------|---------|-------------|
| "Inflation remains well above target" | Còn lo ngại lạm phát | Hawkish ↑ |
| "Inflation has eased substantially" | Lạm phát đã giảm | Dovish ↓ |
| "Ongoing increases will be appropriate" | Sẽ tiếp tục tăng | Hawkish ↑↑ |
| "Some additional firming may be appropriate" | Có thể tăng thêm | Hawkish nhẹ ↑ |
| "In determining the extent of any additional policy firming" | Đang cân nhắc dừng | Dovish nhẹ ↓ |
| "Considering the pace of cuts" | Đang bàn về giảm | Dovish ↓↓ |
| "Higher for longer" | Lãi suất cao lâu hơn | Hawkish ↑ |
| "Data-dependent" | Chờ dữ liệu quyết định | Trung lập |
| "Risks are roughly balanced" | Cân bằng rủi ro | Trung lập → Dovish |
| "Committed to 2% inflation target" | Quyết tâm chống lạm phát | Hawkish ↑ |

---

## Chỉ số VIX — Đo Risk Sentiment

```
VIX < 12:    Cực kỳ bình tĩnh — Risk-On mạnh (hiếm)
VIX 12-15:   Bình tĩnh — Risk-On
VIX 15-20:   Bình thường — Trung lập
VIX 20-25:   Lo lắng — Risk-Off nhẹ
VIX 25-30:   Sợ hãi — Risk-Off (Carry Trade nguy hiểm)
VIX 30-40:   Rất sợ hãi — Risk-Off mạnh
VIX > 40:    Hoảng loạn — Risk-Off cực mạnh (2020 COVID: 82!)
```

**Khi VIX tăng đột biến:**
→ Ưu tiên giảm rủi ro trên các lệnh carry như AUD/JPY, NZD/JPY
→ Theo dõi JPY, CHF, Gold vì thường được mua như safe haven
→ Không mở Carry Trade mới nếu chưa có kế hoạch rủi ro rõ ràng

---

## Lịch sử Carry Trade nổi bật

| Giai đoạn | Cặp tiền | Carry | Kết quả |
|-----------|---------|-------|---------|
| 2003-2007 | AUD/JPY, NZD/JPY | +5-7% | Tuyệt vời — bull market |
| 2008 | AUD/JPY | +7% | Sụp đổ -60% khi khủng hoảng |
| 2009-2012 | NZD/JPY | +3-4% | Khá tốt — recovery |
| 2020 (Mar) | Mọi carry trade | — | Sụp đổ khi COVID |
| 2022-2024 | USD/JPY | +5% | Tốt cho đến tháng 7/2024 |
| 2024 (Aug) | USD/JPY | — | Unwind -12% trong 3 tuần |

---

## Công cụ theo dõi Central Banks

| Công cụ | Link | Mục đích |
|---------|------|---------|
| Fed Website | federalreserve.gov | FOMC Statement, Minutes, Dot Plot gốc |
| CME FedWatch | cmegroup.com/fedwatch | Xác suất kỳ vọng lãi suất Fed |
| ECB Website | ecb.europa.eu | Monetary policy decisions |
| BOJ Website | boj.or.jp/en | Statements và interventions |
| Forex Factory | forexfactory.com/calendar | Lịch tất cả NHTW |
| Bloomberg | bloomberg.com/central-banks | Tổng hợp tin NHTW |

## Tài liệu đọc thêm

**Sách:**
- *Central Banking 101* — Joseph Wang (cựu nhân viên Fed NY)
- *The Creature from Jekyll Island* — G. Edward Griffin (lịch sử Fed)
- *Currency Wars* — James Rickards (chiến tranh tỷ giá)

**Phân tích:**
- Nick Timiraos (Wall Street Journal) — Ký giả "thân thiết" với Fed, thường có thông tin sớm
- Greg Ip (WSJ) — Macro economics analysis
- Neel Kashkari (Minneapolis Fed) — Thường phát biểu rõ ràng nhất
