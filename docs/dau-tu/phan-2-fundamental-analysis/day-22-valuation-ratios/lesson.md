# Ngày 22: Valuation Ratios — Cổ Phiếu Đang Rẻ Hay Đắt?

## Mục tiêu học tập

- [ ] Hiểu và tính toán các chỉ số định giá cơ bản: P/E, P/B, P/S, PEG
- [ ] Hiểu EV/EBITDA và khi nào nên dùng thay P/E
- [ ] Tính và giải thích ROE, ROA, ROIC — đo hiệu quả sinh lời
- [ ] Biết cách kết hợp nhiều chỉ số để đánh giá toàn diện
- [ ] Tránh những sai lầm phổ biến khi dùng valuation ratios

---

## Nội dung bài giảng

### 1. Tại Sao Cần Valuation Ratios?

Bạn muốn mua cổ phiếu của một công ty có lợi nhuận 1,000 tỷ VND. Giá cổ phiếu là 50,000 VND. Câu hỏi tự nhiên: **Đắt hay rẻ?**

Không có con số tuyệt đối nào cho câu hỏi này. Giá cổ phiếu 50,000 VND có thể là rẻ nếu công ty kiếm 10,000 VND/cổ phiếu, nhưng lại đắt nếu chỉ kiếm 100 VND/cổ phiếu.

**Valuation Ratios (chỉ số định giá)** giúp chúng ta so sánh giá cổ phiếu với các chỉ số cơ bản để trả lời câu hỏi: *Nhà đầu tư đang trả bao nhiêu tiền cho mỗi đồng lợi nhuận / doanh thu / tài sản của doanh nghiệp?*

Đây là công cụ để **so sánh** — so sánh với đối thủ cùng ngành, với lịch sử của chính công ty, và với thị trường chung.

---

### 2. P/E Ratio — Chỉ Số Phổ Biến Nhất

**P/E (Price-to-Earnings — hệ số giá trên lợi nhuận)** là chỉ số được nhắc đến nhiều nhất trong thế giới đầu tư.

```
P/E = Giá cổ phiếu / EPS (Earnings Per Share — lợi nhuận mỗi cổ phiếu)

Hoặc: P/E = Market Cap / Net Income
```

**EPS = Net Income / Số cổ phiếu đang lưu hành**

**Ý nghĩa**: P/E = 20 nghĩa là nhà đầu tư đang trả **20 đồng** cho mỗi **1 đồng** lợi nhuận của công ty. Hay nói cách khác, nếu lợi nhuận không đổi, phải mất **20 năm** để thu hồi vốn.

**Ví dụ thực tế:**

| Công ty | Giá CP | EPS | P/E | Nhận xét |
|---------|--------|-----|-----|----------|
| FPT | 120,000 VND | 6,000 VND | 20x | Hợp lý với công ty tăng trưởng |
| Vinamilk | 70,000 VND | 5,000 VND | 14x | Tương đối rẻ, công ty ổn định |
| Một startup công nghệ | 100,000 VND | 500 VND | 200x | Đắt — nhà đầu tư kỳ vọng tăng trưởng lớn |

#### 2.1. Trailing P/E vs Forward P/E

- **Trailing P/E**: Dùng EPS của 12 tháng **vừa qua** — dữ liệu thực tế
- **Forward P/E**: Dùng EPS **dự báo** cho 12 tháng tới — phụ thuộc vào ước tính của analyst

Nếu Forward P/E < Trailing P/E → thị trường kỳ vọng lợi nhuận tăng trong tương lai.

#### 2.2. P/E theo ngành — so sánh đúng cách

P/E **phải so sánh trong cùng ngành**. Không thể so P/E của ngân hàng với công ty công nghệ:

| Ngành | P/E trung bình (tham khảo) |
|-------|--------------------------|
| Công nghệ (growth) | 30 - 60x |
| Tiêu dùng thiết yếu | 20 - 30x |
| Ngân hàng | 8 - 15x |
| Bất động sản | 10 - 20x |
| Điện, tiện ích | 15 - 25x |

#### 2.3. Hạn Chế Của P/E

- **Vô nghĩa khi EPS âm** (công ty đang lỗ)
- **Dễ bị thao túng**: Công ty có thể mua lại cổ phiếu quỹ để giảm số lượng CP, tăng EPS mà không cần tăng lợi nhuận thực
- **Không phản ánh nợ**: Hai công ty cùng P/E nhưng một công ty nợ nhiều rủi ro hơn nhiều

---

### 3. P/B Ratio — Giá Trên Giá Trị Sổ Sách

**P/B (Price-to-Book — hệ số giá trên giá trị sổ sách)**:

```
P/B = Giá cổ phiếu / Book Value Per Share
    = Market Cap / Total Equity
```

**Book Value Per Share** (từ Balance Sheet ngày 21) = Total Equity / Số CP

**Ý nghĩa**: P/B = 1 nghĩa là bạn trả đúng bằng giá trị tài sản ròng trên sổ sách. P/B < 1 có thể nghĩa là cổ phiếu đang rẻ hơn giá trị tài sản (value trap hoặc cơ hội thực sự).

**Khi nào P/B hữu ích nhất?**
- **Ngân hàng và tổ chức tài chính**: Tài sản chủ yếu là tiền và khoản vay — sổ sách phản ánh gần với thực tế
- **Doanh nghiệp sản xuất**: Có nhiều tài sản hữu hình

**Hạn chế của P/B:**
- **Vô nghĩa với công ty công nghệ**: Tài sản lớn nhất của họ là thương hiệu, nhân tài, phần mềm — không nằm trong sổ sách
- **Goodwill thổi phồng Book Value**: Sau các thương vụ M&A lớn, Book Value có thể bị biến dạng

---

### 4. P/S Ratio — Khi Chưa Có Lợi Nhuận

**P/S (Price-to-Sales — hệ số giá trên doanh thu)**:

```
P/S = Market Cap / Revenue (Doanh thu 12 tháng)
```

**Khi nào dùng P/S?**
- Công ty **chưa có lợi nhuận** (startup, công ty tăng trưởng đang đầu tư mạnh)
- So sánh doanh nghiệp trong ngành mà lợi nhuận biến động mạnh

**Ví dụ thực tế:**
- Một startup SaaS với P/S = 10x: Nhà đầu tư trả 10 đồng cho mỗi 1 đồng doanh thu — chấp nhận được nếu tăng trưởng 50%+/năm
- Siêu thị với P/S = 0.5x: Margin thấp, P/S thấp là bình thường

**Hạn chế**: Doanh thu cao không có nghĩa là tốt nếu công ty đang lỗ khủng. P/S bỏ qua khả năng sinh lợi.

---

### 5. PEG Ratio — Bổ Sung Yếu Tố Tăng Trưởng Vào P/E

**PEG (Price/Earnings-to-Growth — hệ số P/E điều chỉnh tăng trưởng)**:

```
PEG = P/E / EPS Growth Rate (%)
```

**Ví dụ**:
- Công ty A: P/E = 30, EPS tăng trưởng 30%/năm → PEG = 30/30 = **1.0**
- Công ty B: P/E = 15, EPS tăng trưởng 5%/năm → PEG = 15/5 = **3.0**

Công ty A nhìn có vẻ đắt (P/E=30) nhưng PEG=1.0 cho thấy **hợp lý hơn** Công ty B (PEG=3.0)!

**Ngưỡng tham khảo của Peter Lynch:**
- PEG < 1: Cổ phiếu rẻ so với tăng trưởng (tiềm năng)
- PEG = 1: Định giá hợp lý
- PEG > 2: Đắt so với tăng trưởng kỳ vọng

> Peter Lynch (nhà quản lý quỹ huyền thoại của Fidelity Magellan): "The P/E ratio of any company that's fairly priced will equal its growth rate."

**Hạn chế**: PEG phụ thuộc vào dự báo tăng trưởng — nếu dự báo sai, PEG vô nghĩa.

---

### 6. EV/EBITDA — Chỉ Số Của Nhà Đầu Tư Chuyên Nghiệp

Đây là chỉ số được M&A professionals và private equity ưa dùng vì nó **loại bỏ ảnh hưởng của cấu trúc vốn và kế toán**.

**EV (Enterprise Value — Giá trị doanh nghiệp)**:
```
EV = Market Cap + Total Debt - Cash & Equivalents
```

EV phản ánh **tổng chi phí thực sự** để mua lại toàn bộ doanh nghiệp (phải trả cho cổ đông + trả nợ - tiền mặt nhận về).

**EBITDA (Earnings Before Interest, Taxes, Depreciation and Amortization)**:
```
EBITDA = Operating Income + Depreciation + Amortization
       ≈ Lợi nhuận trước lãi vay, thuế, và khấu hao
```

EBITDA là thước đo gần với dòng tiền hoạt động, loại bỏ ảnh hưởng của:
- Lãi vay (Interest): Phụ thuộc cấu trúc vốn
- Thuế (Taxes): Khác nhau giữa các quốc gia
- Khấu hao (D&A): Khác nhau giữa các chính sách kế toán

```
EV/EBITDA = Enterprise Value / EBITDA
```

**Ngưỡng tham khảo (tùy ngành):**
- < 8x: Rẻ
- 8-15x: Hợp lý
- > 20x: Đắt (trừ khi tăng trưởng mạnh)

**Ưu điểm so với P/E:**
- So sánh được giữa các công ty có cấu trúc nợ khác nhau
- Không bị ảnh hưởng bởi chính sách thuế khác nhau
- Tốt hơn khi so sánh doanh nghiệp ở các quốc gia khác nhau

---

### 7. ROE, ROA, ROIC — Đo Hiệu Quả Sinh Lời

Các chỉ số này không phải "định giá" theo nghĩa thông thường, nhưng rất quan trọng để đánh giá **chất lượng doanh nghiệp** trước khi nhìn vào định giá.

#### 7.1. ROE — Return on Equity (Lợi nhuận trên vốn chủ sở hữu)

```
ROE = Net Income / Average Total Equity × 100%
```

**Ý nghĩa**: Với mỗi 100 đồng vốn cổ đông bỏ vào, công ty tạo ra bao nhiêu đồng lợi nhuận?

- ROE > 15%: Tốt
- ROE > 20%: Rất tốt
- ROE > 30%: Xuất sắc (điển hình: Apple ~160%, Coca-Cola ~40%)

> **Warren Buffett** ưa thích các doanh nghiệp có ROE > 15% trong nhiều năm liên tiếp.

**Cẩn thận**: ROE cao do nợ nhiều (D/E cao) — cần kiểm tra thêm!

#### 7.2. ROA — Return on Assets (Lợi nhuận trên tổng tài sản)

```
ROA = Net Income / Average Total Assets × 100%
```

**Ý nghĩa**: Công ty sử dụng tài sản hiệu quả đến mức nào?

- ROA > 5%: Tốt với hầu hết ngành
- ROA > 10%: Rất tốt
- Ngân hàng: ROA 1-2% đã là tốt (vì họ có tài sản rất lớn)

**ROA tốt hơn ROE** khi muốn so sánh các công ty có cấu trúc nợ khác nhau, vì ROA không bị ảnh hưởng bởi đòn bẩy.

#### 7.3. ROIC — Return on Invested Capital (Lợi nhuận trên vốn đầu tư)

```
ROIC = NOPAT / Invested Capital
NOPAT = Net Operating Profit After Tax (lợi nhuận hoạt động sau thuế)
Invested Capital = Total Equity + Total Debt - Cash
```

**Đây là chỉ số Warren Buffett và Charlie Munger ưa thích nhất**.

ROIC > WACC (chi phí vốn bình quân) → Doanh nghiệp đang **tạo ra giá trị** cho cổ đông.
ROIC < WACC → Doanh nghiệp đang **phá hủy giá trị** dù có lợi nhuận.

- ROIC > 15%: Doanh nghiệp tốt
- ROIC > 20% bền vững nhiều năm: Doanh nghiệp có Economic Moat thực sự

---

### 8. Kết Hợp Nhiều Chỉ Số — Framework Phân Tích

Đừng bao giờ dùng chỉ một chỉ số để quyết định đầu tư. Đây là framework đơn giản:

**Bước 1: Đánh giá chất lượng doanh nghiệp**
- ROE > 15% liên tục? ✅
- ROIC cao và ổn định? ✅
- FCF dương và tăng trưởng? ✅

**Bước 2: Đánh giá định giá**
- P/E so với lịch sử và đối thủ ngành?
- PEG có hợp lý so với tốc độ tăng trưởng?
- EV/EBITDA so với ngành?

**Bước 3: So sánh và kết luận**
- Rẻ hơn đối thủ cùng chất lượng? → Tiềm năng
- Đắt hơn đối thủ nhưng tăng trưởng nhanh hơn? → Có thể chấp nhận
- Đắt hơn đối thủ, tăng trưởng chậm hơn? → Cẩn thận

**Ví dụ thực tế — So sánh FPT và một công ty IT nhỏ hơn:**

| Chỉ số | FPT | Công ty IT nhỏ | Nhận xét |
|--------|-----|----------------|----------|
| P/E | 20x | 10x | FPT đắt hơn |
| EPS Growth | 20%/năm | 5%/năm | FPT tăng trưởng nhanh hơn |
| PEG | 1.0 | 2.0 | FPT hợp lý hơn! |
| ROE | 25% | 8% | FPT chất lượng tốt hơn |
| ROIC | 20% | 6% | FPT hiệu quả hơn nhiều |

**Kết luận**: FPT dù P/E cao hơn nhưng tổng thể hấp dẫn hơn khi xét toàn bộ chỉ số.

---

### 9. Sai Lầm Phổ Biến Khi Dùng Valuation Ratios

**Sai lầm 1: Chỉ nhìn vào P/E thấp**
- P/E thấp không tự động có nghĩa là rẻ — có thể là "value trap" (bẫy giá trị)
- Ví dụ: Nhiều công ty than, dầu mỏ có P/E rất thấp nhưng triển vọng ngành đang suy tàn

**Sai lầm 2: So sánh P/E khác ngành**
- Không thể so P/E của ngân hàng (10x) với công ty SaaS (50x) và kết luận ngân hàng "rẻ hơn"

**Sai lầm 3: Bỏ qua chất lượng lợi nhuận**
- Cùng P/E 15x nhưng một công ty có FCF mạnh, công ty kia lợi nhuận phụ thuộc vào accounting adjustments

**Sai lầm 4: Không xem xét theo chu kỳ**
- Ở đỉnh chu kỳ kinh tế, lợi nhuận cao bất thường → P/E trông thấp nhưng thực ra đắt
- Ở đáy chu kỳ, lợi nhuận thấp → P/E trông cao nhưng thực ra rẻ

**Sai lầm 5: Bỏ qua nợ**
- Hai công ty cùng P/E nhưng một công ty nợ gấp 3 lần — rủi ro hoàn toàn khác nhau
- Dùng EV/EBITDA để so sánh chính xác hơn trong trường hợp này

---

## Tóm Tắt Kiến Thức Chính (Key Takeaways)

1. **P/E** là chỉ số phổ biến nhất — nhưng phải so trong cùng ngành và xét yếu tố tăng trưởng
2. **PEG** bổ sung yếu tố tăng trưởng vào P/E — PEG < 1 thường hấp dẫn
3. **P/B** hữu ích với ngân hàng và doanh nghiệp tài sản nhiều
4. **P/S** dùng khi chưa có lợi nhuận
5. **EV/EBITDA** trung lập với cấu trúc vốn — ưa dùng trong M&A và so sánh xuyên quốc gia
6. **ROE, ROA, ROIC** đo chất lượng doanh nghiệp — phải đánh giá trước khi nhìn định giá
7. **Kết hợp nhiều chỉ số** — không bao giờ quyết định chỉ dựa trên 1 chỉ số

---

## Thuật Ngữ Quan Trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| P/E Ratio | Hệ số giá/lợi nhuận | Giá CP / EPS |
| Trailing P/E | P/E lịch sử | Dùng EPS 12 tháng qua |
| Forward P/E | P/E dự phóng | Dùng EPS dự báo 12 tháng tới |
| EPS | Lợi nhuận mỗi cổ phiếu | Net Income / Số CP lưu hành |
| P/B Ratio | Hệ số giá/sổ sách | Giá CP / Book Value Per Share |
| P/S Ratio | Hệ số giá/doanh thu | Market Cap / Doanh thu |
| PEG Ratio | Hệ số P/E điều chỉnh tăng trưởng | P/E / EPS Growth Rate |
| EV | Giá trị doanh nghiệp | Market Cap + Debt - Cash |
| EBITDA | Lợi nhuận trước lãi/thuế/khấu hao | Chỉ số gần với dòng tiền hoạt động |
| EV/EBITDA | Hệ số EV trên EBITDA | Phổ biến trong M&A |
| ROE | Lợi nhuận trên vốn chủ | Net Income / Equity |
| ROA | Lợi nhuận trên tài sản | Net Income / Total Assets |
| ROIC | Lợi nhuận trên vốn đầu tư | Chỉ số chất lượng doanh nghiệp |
| Value Trap | Bẫy giá trị | Cổ phiếu rẻ nhưng không cải thiện |

---

## Bài Học Tiếp Theo

**Ngày 23: Valuation Methods — DCF** — Bây giờ bạn đã biết dùng các chỉ số để so sánh tương đối. Ngày mai chúng ta sẽ học phương pháp định giá **tuyệt đối**: DCF (Discounted Cash Flow — chiết khấu dòng tiền) để tính ra **giá trị nội tại** của một doanh nghiệp — và so sánh với giá thị trường để xem đang rẻ hay đắt bao nhiêu phần trăm.
