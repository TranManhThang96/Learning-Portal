# Tài liệu tham khảo — Ngày 33: Thị trường chứng khoán cơ bản

## Bảng tóm tắt: 3 sàn chứng khoán Việt Nam

| Tiêu chí | HOSE | HNX | UPCOM |
|----------|------|-----|-------|
| Vốn hóa yêu cầu | ≥ 120 tỷ VND | ≥ 30 tỷ VND | Không yêu cầu cố định |
| Biên độ dao động | ±7% | ±10% | ±15% |
| Lô giao dịch | 100 CP | 100 CP | 100 CP |
| Ký hiệu | 3 ký tự | 3 ký tự | 3 ký tự |
| Chỉ số đại diện | VN-Index, VN30 | HNX-Index | UPCOM-Index |
| Thanh khoản | Cao nhất | Trung bình | Thấp nhất |
| Rủi ro | Thấp nhất | Trung bình | Cao nhất |

---

## Cheat Sheet: Các loại lệnh

### Lệnh Limit Order (LO) — Dùng thường xuyên nhất

```
MUA:                              BÁN:
Đặt giá ≤ giá thị trường         Đặt giá ≥ giá thị trường
→ Lệnh sẽ khớp khi giá           → Lệnh sẽ khớp khi giá
  xuống đến mức bạn đặt            lên đến mức bạn đặt

Ví dụ MUA FPT:                   Ví dụ BÁN FPT:
Giá TT: 95,500                   Giá TT: 95,500
Đặt lệnh: 95,000                 Đặt lệnh: 97,000
→ Chờ FPT về 95,000              → Chờ FPT lên 97,000
```

### So sánh các loại lệnh

| Loại lệnh | Chắc khớp? | Kiểm soát giá? | Khi nào dùng? |
|-----------|-----------|----------------|---------------|
| Market Order | ✅ Chắc chắn | ❌ Không | Cần mua/bán gấp |
| Limit Order | ⚠️ Có thể không | ✅ Có | Hầu hết trường hợp |
| ATO | ✅ Chắc chắn | ❌ Không | Muốn khớp giá mở cửa |
| ATC | ✅ Chắc chắn | ❌ Không | Muốn khớp giá đóng cửa |

---

## Bảng tính: Tổng chi phí giao dịch

**Công thức:**
```
Phí mua = Giá mua × Số lượng × Phí giao dịch (%)
Phí bán = Giá bán × Số lượng × Phí giao dịch (%)
Thuế bán = Giá bán × Số lượng × 0.1%

Tổng chi phí = Phí mua + Phí bán + Thuế bán + Spread
```

**Ví dụ cụ thể:**
```
Mua 1,000 FPT tại 95,000 VND, phí 0.15%:
- Chi phí mua:    95,000,000 × 0.15% = 142,500 VND
- Spread (giả sử): 1,000 × 200 = 200,000 VND

Bán 1,000 FPT tại 100,000 VND, phí 0.15%:
- Chi phí bán:    100,000,000 × 0.15% = 150,000 VND
- Thuế bán:       100,000,000 × 0.1% = 100,000 VND

Tổng chi phí 2 chiều:
142,500 + 200,000 + 150,000 + 100,000 = 592,500 VND

Lợi nhuận thô: (100,000 - 95,000) × 1,000 = 5,000,000 VND
Lợi nhuận sau chi phí: 5,000,000 - 592,500 = 4,407,500 VND
Tỷ suất thực: 4,407,500 / 95,000,000 = 4.64% (không phải 5.26%)
```

---

## Lịch giao dịch HOSE theo tuần

```
Thứ 2: Giao dịch
Thứ 3: Giao dịch
Thứ 4: Giao dịch
Thứ 5: Giao dịch
Thứ 6: Giao dịch
Thứ 7: Nghỉ
CN: Nghỉ

T+2 ví dụ:
Mua Thứ 2 → CP về Thứ 4
Mua Thứ 3 → CP về Thứ 5
Mua Thứ 4 → CP về Thứ 6
Mua Thứ 5 → CP về Thứ 2 (tuần sau)
Mua Thứ 6 → CP về Thứ 3 (tuần sau)
```

---

## Bảng so sánh: TTCK Việt Nam vs Mỹ vs Quốc tế

| Tiêu chí | HOSE/HNX | NYSE/NASDAQ | LSE (London) | TSE (Tokyo) |
|----------|----------|-------------|--------------|-------------|
| Vốn hóa (approx.) | ~200 tỷ USD | ~25,000 tỷ USD | ~4,000 tỷ USD | ~6,000 tỷ USD |
| Số cty niêm yết | ~700 | ~6,000+ | ~2,000 | ~3,800 |
| Giờ giao dịch | 9:00-14:45 VN | 9:30-16:00 ET | 8:00-16:30 GMT | 9:00-15:30 JST |
| Biên độ | ±7% | Không giới hạn | Không giới hạn | Thay đổi theo giá |
| Settlement | T+2 | T+1 (từ 5/2024) | T+2 | T+2 |

---

## Top cổ phiếu theo vốn hóa — VN30

Các cổ phiếu lớn nhất trong VN30 (cập nhật ~ 2024):

| Mã | Tên doanh nghiệp | Ngành |
|----|-----------------|-------|
| VCB | Vietcombank | Ngân hàng |
| VHM | Vinhomes | Bất động sản |
| BID | BIDV | Ngân hàng |
| CTG | Vietinbank | Ngân hàng |
| FPT | FPT Corporation | Công nghệ |
| HPG | Hòa Phát Group | Thép |
| MSN | Masan Group | Tiêu dùng |
| MWG | Thế Giới Di Động | Bán lẻ |
| VNM | Vinamilk | Thực phẩm |
| TCB | Techcombank | Ngân hàng |

---

## Ứng dụng mobile cho nhà đầu tư VN

| Ứng dụng | Nhà phát triển | Tính năng nổi bật |
|----------|---------------|-------------------|
| iBoard (SSI) | SSI | Charts tốt, nhiều tính năng |
| VPS SmartOne | VPS | UX đẹp, phổ biến người trẻ |
| tcTrade | Techcom Securities | Tích hợp TCB banking |
| FireAnt | FireAnt | Mạng xã hội đầu tư, tin tức |
| CafeF | CafeF | Tin tức, screener |
| TradingView | TradingView | Charts chuyên nghiệp (web) |

---

## Tài liệu đọc thêm

**Website chính thức:**
- Sở GDCK TP.HCM (HOSE): https://www.hsx.vn
- Ủy ban Chứng khoán Nhà nước: https://www.ssc.gov.vn
- CafeF (tin tức, dữ liệu VN): https://cafef.vn
- Vietstock (screener, phân tích): https://vietstock.vn

**Quốc tế:**
- NYSE: https://www.nyse.com
- NASDAQ: https://www.nasdaq.com
- Investopedia: https://www.investopedia.com

**Sách nền tảng:**
- *Hướng dẫn đầu tư chứng khoán từ A-Z* — Nhiều tác giả VN
- *The Intelligent Investor* — Benjamin Graham (bản dịch tiếng Việt có bán)

---

## Ghi chú bổ sung: Thuế chứng khoán tại Việt Nam

Khi bán cổ phiếu tại VN, bạn phải nộp **thuế thu nhập cá nhân** theo 2 cách:

**Cách 1:** 0.1% trên **tổng giá trị bán** (bất kể lãi hay lỗ)
- Ví dụ: Bán 1,000 FPT × 100,000 = 100 triệu → Thuế = 100,000 VND

**Cách 2:** 20% trên **lợi nhuận ròng** (chỉ tính khi có lãi)
- Ít phổ biến hơn, phải đăng ký theo phương pháp này

Mặc định: Hầu hết nhà đầu tư dùng Cách 1 (0.1% giá trị bán) — CTCK tự khấu trừ mỗi lần bán.

**Lưu ý:** Mua cổ phiếu **KHÔNG** phải nộp thuế.
