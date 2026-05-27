# Tài Liệu Tham Khảo — Ngày 34: Margin Trading, Short Selling & Quyền Cổ Đông

## Bảng Tóm Tắt / Cheat Sheet

### So Sánh: Margin vs Không Margin

| Yếu tố | Không Margin | Margin 1:2 | Margin 1:3 |
|--------|-------------|------------|------------|
| Vốn tự có | 100 triệu | 100 triệu | 100 triệu |
| Sức mua | 100 triệu | 200 triệu | 300 triệu |
| Lãi nếu CP tăng 20% | +20% | +40% (trừ lãi) | +60% (trừ lãi) |
| Lỗ nếu CP giảm 20% | -20% | -40% | -60% |
| Lỗ sạch vốn khi CP giảm | -100% | -50% | -33% |
| Rủi ro Margin Call | Không | Có | Cao |

---

### Công Thức Tính Margin

```
Tỷ lệ Margin hiện tại = (Giá trị danh mục - Nợ margin) / Giá trị danh mục × 100%

Ngưỡng Margin Call = Nợ margin / (1 - Tỷ lệ duy trì)

Lãi suất margin hàng ngày = Số tiền vay × Lãi suất năm / 365
```

**Ví dụ tính ngưỡng Margin Call:**
- Vốn: 200 triệu, Nợ: 100 triệu, Tỷ lệ duy trì: 40%
- Ngưỡng = 100 triệu / (1 - 0.4) = **166.7 triệu**
- Nếu danh mục giảm từ 200M xuống 166.7M (giảm 16.7%) → Margin Call

---

### Quy Trình Short Selling

```
[Mượn CP từ broker] → [Bán ra thị trường] → [Chờ giá giảm] → [Mua lại] → [Trả lại broker]
     ↓                        ↓                                    ↓
  Có nghĩa vụ         Thu tiền về tài khoản               Chi tiền ít hơn
  phải trả lại         (ký quỹ đảm bảo)                  = Lợi nhuận
```

**Rủi ro đặc thù Short Selling:**
- Lãi tối đa: 100% (cổ phiếu về 0)
- Lỗ: KHÔNG GIỚI HẠN (cổ phiếu tăng không có trần)
- Phí mượn CP (borrow fee): 1-5%/năm tùy loại
- Short Squeeze: Rủi ro bị ép mua lại ở giá cao

---

### Timeline Cổ Tức (Dividend Timeline)

```
Declaration Date          Ex-Dividend Date    Record Date    Payment Date
(Ngày công bố)           (Không hưởng QT)    (Chốt DS)     (Thanh toán)
      |                         |                  |               |
      |←——————— T-2 ————————————|                  |               |
      |              Mua trước đây → ĐƯỢC nhận      |               |
      |              Mua từ đây → KHÔNG nhận        |               |
```

**Lưu ý**: Tại Việt Nam, giao dịch T+2 (2 ngày làm việc để quyết toán), nên phải mua trước Ex-Dividend Date ít nhất 2 ngày giao dịch để được nhận cổ tức.

---

### Các Loại Corporate Actions & Tác Động

| Corporate Action | Số CP | Giá CP | Tổng giá trị | Tỷ lệ sở hữu |
|-----------------|-------|--------|--------------|--------------|
| Stock Split 2:1 | ×2 | ÷2 | Không đổi | Không đổi |
| Stock Dividend 10% | +10% | Giảm nhẹ | Gần như không đổi | Không đổi |
| Buyback | Giảm | Thường tăng | Không đổi | Tăng (%) |
| Rights Issue | Tăng | Giảm (dilution) | Tăng (công ty có thêm vốn) | Giảm nếu không tham gia |
| Cash Dividend | Không đổi | Giảm đúng bằng cổ tức | Giảm | Không đổi |

---

### Tỷ Suất Cổ Tức Một Số Cổ Phiếu Việt Nam (Tham Khảo)

| Mã CP | Doanh nghiệp | Dividend Yield (ước tính) | Đặc điểm |
|-------|--------------|--------------------------|----------|
| VNM | Vinamilk | 4-6% | Trả đều đặn, 2 lần/năm |
| FPT | FPT Corp | 2-3% | Tăng trưởng + cổ tức |
| REE | Cơ điện lạnh | 3-5% | Cổ tức ổn định |
| VCB | Vietcombank | 1-2% | Ngân hàng, thường cổ tức CP |
| MSN | Masan Group | 0-1% | Tập trung tái đầu tư |
| HPG | Hòa Phát | 1-3% | Biến động theo chu kỳ thép |

> *Số liệu mang tính tham khảo, thay đổi theo từng năm.*

---

### Tóm Tắt Quy Tắc An Toàn Margin

```
✅ NÊN làm:
- Chỉ dùng margin khi đã có ít nhất 2 năm kinh nghiệm
- Tối đa 30-50% hạn mức margin được cấp
- Chỉ margin cổ phiếu bluechip (VN30)
- Luôn có Stop-loss rõ ràng
- Theo dõi tỷ lệ margin mỗi ngày

❌ KHÔNG nên làm:
- Dùng full margin (hết hạn mức)
- Margin cổ phiếu penny/nhỏ
- Average down (bình giá) khi đang lỗ margin
- Margin trong giai đoạn thị trường bất ổn
- Vay thêm bên ngoài để bổ sung margin
```

---

## Tài Liệu Đọc Thêm

### Sách
- **"The Big Short" — Michael Lewis**: Câu chuyện về những người đặt cược vào sự sụp đổ thị trường BĐS Mỹ 2008 qua short selling
- **"Margin of Safety" — Seth Klarman**: Đầu tư thận trọng, tránh rủi ro
- **"When Genius Failed" — Roger Lowenstein**: Sự sụp đổ của quỹ LTCM vì dùng leverage quá cao

### Website
- **[HOSE — hsx.vn](https://www.hsx.vn)**: Danh sách cổ phiếu được margin tại Việt Nam
- **[Cafef.vn](https://cafef.vn)**: Theo dõi lịch trả cổ tức, quyền mua cổ phiếu
- **[Vietstock.vn](https://vietstock.vn)**: Thông tin corporate actions

### Video/Khóa học
- YouTube: "Short Selling Explained" — các kênh tài chính quốc tế
- Phim tài liệu: **"Gamestop: Rise of the Players" (2022)** — câu chuyện Short Squeeze GameStop

---

## Ghi Chú Bổ Sung

### Vì Sao Không Nên Dùng Margin Khi Mới Bắt Đầu?

Nghiên cứu từ các công ty chứng khoán cho thấy:
- **80%** nhà đầu tư dùng margin lần đầu bị lỗ vượt kế hoạch
- Margin tạo ra **áp lực tâm lý** khiến bạn không thể giữ kỷ luật
- **Chi phí lãi margin** liên tục bào mòn lợi nhuận, kể cả khi thị trường đi ngang

### Margin trên Thị Trường Phái Sinh Việt Nam

Nếu muốn dùng đòn bẩy để đầu cơ ngắn hạn, **hợp đồng tương lai VN30** (VN30F) là lựa chọn được quản lý chặt chẽ hơn margin cổ phiếu thông thường:
- Leverage khoảng 1:10 đến 1:15
- Có thể Long (mua lên) hoặc Short (bán xuống)
- Phù hợp hơn cho các nhà đầu tư ngắn hạn chuyên nghiệp
