# Ngày 39: Market Indices — Chỉ Số Thị Trường

## Mục tiêu học tập
- [ ] Hiểu cách tính toán và ý nghĩa của các chỉ số thị trường chính
- [ ] Phân biệt các phương pháp tính chỉ số: Price-weighted, Market cap-weighted, Equal-weighted
- [ ] Phân tích được VN-Index, S&P 500, Dow Jones, NASDAQ, Russell 2000
- [ ] Hiểu Market Breadth và cách đọc tín hiệu sức khỏe thị trường
- [ ] Biết cách phân loại Market Cap và ý nghĩa đầu tư

---

## Nội dung bài giảng

### 1. Chỉ số thị trường là gì và tại sao quan trọng?

**Market Index (Chỉ số thị trường)** là một giỏ cổ phiếu đại diện được tổng hợp thành một con số duy nhất, phản ánh sức khỏe chung của thị trường hoặc một phân khúc thị trường.

**Tại sao cần chỉ số thị trường?**

1. **Benchmark (Điểm chuẩn):** So sánh hiệu suất danh mục của bạn với thị trường. Nếu danh mục bạn tăng 8% nhưng VN-Index tăng 15% → bạn đang underperform.

2. **Đo lường tâm lý thị trường:** Chỉ số tăng/giảm phản ánh kỳ vọng tổng thể của hàng triệu nhà đầu tư.

3. **Cơ sở cho sản phẩm tài chính:** ETF, options, futures — tất cả đều dựa trên chỉ số.

4. **Chỉ báo kinh tế:** Chứng khoán thường đi trước nền kinh tế thực 6-12 tháng.

---

### 2. Các phương pháp tính chỉ số

#### 2.1. Price-Weighted Index (Chỉ số theo giá)

**Ví dụ tiêu biểu: Dow Jones Industrial Average (DJIA)**

Cách tính: Cộng giá tất cả cổ phiếu trong rổ, chia cho một số gọi là "Divisor" (hệ số chia).

```
DJIA = Tổng giá 30 cổ phiếu / Divisor
```

**Vấn đề của Price-Weighted:**
- Cổ phiếu giá cao ảnh hưởng nhiều hơn dù công ty có thể nhỏ hơn
- UnitedHealth Group (giá ~$500) ảnh hưởng Dow nhiều hơn Apple (giá ~$180) dù Apple vốn hóa gấp đôi
- Đây là lý do nhiều chuyên gia cho rằng Dow Jones là chỉ số lỗi thời

**Ví dụ minh họa:**

| Cổ phiếu | Giá | Vốn hóa |
|----------|-----|---------|
| A | $200 | $20B |
| B | $50 | $100B |
| C | $10 | $50B |

Price-Weighted Index = (200 + 50 + 10) / 3 = **86.7**
→ Cổ phiếu A chiếm 77% ảnh hưởng dù chỉ là công ty nhỏ nhất!

#### 2.2. Market Cap-Weighted Index (Chỉ số theo vốn hóa)

**Ví dụ tiêu biểu: S&P 500, VN-Index, NASDAQ Composite**

Cách tính: Mỗi cổ phiếu được trọng số theo **Market Capitalization (Vốn hóa thị trường)**.

```
Market Cap = Giá cổ phiếu × Số cổ phiếu lưu hành
Trọng số = Market Cap công ty / Tổng Market Cap tất cả công ty trong rổ
```

**Ví dụ với S&P 500:**
- Apple (AAPL) có vốn hóa ~$3,000 tỷ → chiếm ~7% S&P 500
- Khi Apple tăng 1%, S&P 500 tăng khoảng 0.07%

**Ưu điểm:** Phản ánh đúng quy mô thực tế của công ty → công bằng hơn.

**Nhược điểm:** "Concentration risk" — top 10 công ty có thể chiếm 30-35% chỉ số. Nếu mega-caps giảm mạnh, cả chỉ số giảm dù đa số cổ phiếu nhỏ không sao.

#### 2.3. Equal-Weighted Index (Chỉ số trọng số bằng nhau)

Mỗi cổ phiếu có trọng số như nhau, bất kể vốn hóa.

- S&P 500 Equal Weight (RSP ETF): Mỗi trong 500 cổ phiếu = 0.2%
- Nghiêng về small/mid-cap hơn thông thường

**Thú vị:** Historically, equal-weight S&P 500 đã outperform cap-weight S&P 500 trong dài hạn — nhưng biến động hơn và phí cao hơn.

---

### 3. Các chỉ số chính cần biết

#### 3.1. VN-Index — Chỉ số chứng khoán Việt Nam

**VN-Index** là chỉ số tổng hợp của toàn bộ cổ phiếu niêm yết trên **HOSE (Sàn giao dịch chứng khoán TP.HCM)**.

- Phương pháp: Market cap-weighted
- Ra đời: 28/7/2000 với giá trị ban đầu là **100 điểm**
- Hiện tại (~2024): Dao động quanh **1,000-1,300 điểm**
- Số cổ phiếu: ~400+ mã

**Đọc VN-Index:**
- **VN-Index 1,200 điểm:** Tăng 12 lần so với thời điểm khởi đầu (2000)
- **VN-Index tăng 2% trong ngày:** Trung bình toàn thị trường HOSE tăng 2% (theo trọng số vốn hóa)

**VN30 Index vs VN-Index:**
- VN30 chỉ gồm 30 cổ phiếu vốn hóa lớn nhất và thanh khoản cao nhất
- VN30 thường di chuyển cùng hướng với VN-Index nhưng bớt bị ảnh hưởng bởi cổ phiếu nhỏ

**Các chỉ số khác tại Việt Nam:**
- **HNX-Index:** Sàn Hà Nội (HNX)
- **UPCOM-Index:** Sàn giao dịch phi tập trung
- **VNMidCap:** Cổ phiếu vốn hóa trung bình
- **VN Diamond:** Cổ phiếu không bị giới hạn tỷ lệ sở hữu nước ngoài

#### 3.2. S&P 500 — Vua của các chỉ số

**S&P 500 (Standard & Poor's 500)** theo dõi 500 công ty lớn nhất Mỹ niêm yết trên NYSE và NASDAQ.

- Phương pháp: Float-adjusted market cap-weighted
- Ra đời: 1957 (dưới hình thức hiện tại)
- Được xem là **benchmark chuẩn** cho toàn bộ thị trường Mỹ và cả thế giới

**Tại sao S&P 500 quan trọng hơn Dow Jones?**
- S&P 500: 500 công ty → đại diện rộng hơn (~80% tổng vốn hóa thị trường Mỹ)
- Dow Jones: Chỉ 30 công ty, tính theo giá (bất hợp lý)
- Hầu hết học thuật và chuyên gia dùng S&P 500 làm benchmark

**S&P 500 Top 10 holdings (~2024):**
1. Apple (~7%)
2. Microsoft (~7%)
3. NVIDIA (~6%)
4. Amazon (~4%)
5. Meta (~2.5%)
6. Alphabet Class A (~2.2%)
7. Berkshire Hathaway (~1.8%)
8. Alphabet Class C (~1.8%)
9. Eli Lilly (~1.6%)
10. Broadcom (~1.5%)

**Lịch sử S&P 500:**
- Từ 1957 đến nay: Lợi nhuận trung bình ~10%/năm (danh nghĩa), ~7%/năm (thực)
- Năm tệ nhất: 2008 (-38.5%), 2022 (-19.4%)
- Năm tốt nhất: 1954 (+52.6%), 1995 (+37.6%), 2019 (+31.5%)
- Quy tắc 72: Với 10%/năm, vốn nhân đôi sau 7.2 năm

#### 3.3. Dow Jones Industrial Average (DJIA)

**DJIA** là chỉ số lâu đời nhất nước Mỹ, ra đời năm **1896** bởi Charles Dow.

- 30 công ty blue-chip lớn nhất Mỹ
- Price-weighted (phương pháp lỗi thời)
- Vẫn được dùng rộng rãi trên media vì lịch sử lâu dài

**Thành phần hiện tại (ví dụ):** Apple, Microsoft, Goldman Sachs, JPMorgan, Boeing, Coca-Cola, Nike, Walmart, Disney...

**Tại sao "Dow tăng 500 điểm" ít ý nghĩa hơn "S&P tăng 1%"?**

Dow Jones đang ở ~40,000 điểm. 500 điểm = 1.25%.
S&P 500 ở ~5,000 điểm. 50 điểm = 1%.

Cần so sánh bằng **phần trăm**, không phải điểm số tuyệt đối!

#### 3.4. NASDAQ Composite & NASDAQ-100

**NASDAQ Composite:**
- Toàn bộ cổ phiếu niêm yết trên sàn NASDAQ (~3,000+ công ty)
- Tập trung công nghệ nhiều hơn NYSE
- Market cap-weighted

**NASDAQ-100 (QQQ):**
- 100 công ty lớn nhất phi tài chính trên NASDAQ
- **Dominant bởi Tech:** Apple, Microsoft, NVIDIA, Amazon, Meta, Alphabet chiếm ~50%+
- Biến động cao hơn S&P 500, lợi nhuận cũng cao hơn trong dài hạn gần đây

**So sánh lịch sử (2010-2023):**
- NASDAQ-100: ~+1,200%
- S&P 500: ~+450%
- Dow Jones: ~+350%

→ NASDAQ-100 vượt trội nhưng cũng giảm mạnh hơn trong downturns (2000-2002: -82%!; 2022: -33%)

#### 3.5. Russell 2000

**Russell 2000** theo dõi 2,000 công ty nhỏ nhất trong Russell 3000 Index.

- Đại diện cho **Small-Cap Stocks (Cổ phiếu vốn hóa nhỏ)**
- Dùng làm benchmark cho small-cap fund managers
- Thường outperform S&P 500 trong long run nhưng biến động hơn
- "Risk-on indicator" — khi Russell 2000 tăng mạnh hơn S&P 500, thị trường đang ở trạng thái risk appetite cao

---

### 4. Market Cap Classification (Phân loại theo vốn hóa)

#### 4.1. Phân loại quốc tế

| Loại | Market Cap | Đặc điểm |
|------|-----------|----------|
| **Mega-cap** | > $200 tỷ | Apple, Microsoft, NVIDIA — cực kỳ ổn định |
| **Large-cap** | $10-200 tỷ | Nền tảng danh mục, ít rủi ro |
| **Mid-cap** | $2-10 tỷ | Cân bằng growth và stability |
| **Small-cap** | $300 triệu - $2 tỷ | Growth tiềm năng cao, rủi ro cao |
| **Micro-cap** | $50-300 triệu | Rủi ro cao, ít thanh khoản |
| **Nano-cap** | < $50 triệu | Đầu cơ, cực kỳ rủi ro |

#### 4.2. Phân loại tại Việt Nam (theo VN-Index)

| Nhóm | Vốn hóa (tỷ VND) | Ví dụ |
|------|-----------------|-------|
| **VN30** (Large-cap) | > 10,000 tỷ | VCB, BID, VHM, VIC, FPT |
| **VNMidCap** | 1,000-10,000 tỷ | REE, PNJ, DGC, KDC |
| **VNSmallCap** | 100-1,000 tỷ | Nhiều cổ phiếu ngành |
| **Penny stocks** | < 100 tỷ | Rủi ro cao, thường bị thao túng |

---

### 5. Market Breadth (Chiều rộng thị trường)

**Market Breadth** là thước đo xem sức mạnh của chỉ số có được hỗ trợ bởi đa số cổ phiếu hay chỉ bởi một nhóm nhỏ.

#### 5.1. Advance/Decline Line (A/D Line)

**A/D Line = Số cổ phiếu tăng - Số cổ phiếu giảm (tích lũy)**

**Cách đọc tín hiệu:**

| Tình huống | Ý nghĩa |
|-----------|---------|
| VN-Index tăng + A/D Line tăng | Xu hướng tăng khỏe mạnh, được hỗ trợ rộng |
| VN-Index tăng + A/D Line giảm | **Divergence** — cảnh báo! Chỉ mega-cap kéo lên, đa số yếu |
| VN-Index giảm + A/D Line ổn định | Chỉ vài cổ phiếu lớn kéo xuống, nội lực thị trường còn tốt |

#### 5.2. % Cổ phiếu trên SMA 200

**Chỉ báo:** % cổ phiếu trong chỉ số đang giao dịch trên đường MA 200 ngày

- **> 70%:** Thị trường tăng khỏe, breadth tốt
- **50-70%:** Thị trường bình thường
- **< 30%:** Thị trường yếu, nhiều cổ phiếu trong downtrend
- **< 20%:** Vùng capitulation — có thể là đáy

#### 5.3. New Highs vs New Lows

So sánh số cổ phiếu đạt đỉnh 52 tuần mới vs đạt đáy 52 tuần mới:

- **New Highs >> New Lows:** Thị trường đang tăng khỏe
- **New Lows >> New Highs:** Áp lực bán lớn, cẩn thận

---

### 6. Sector Breakdown — Phân tích ngành trong chỉ số

S&P 500 chia thành **11 ngành (sectors)** theo chuẩn GICS (Global Industry Classification Standard):

| Ngành | Tỷ trọng (~2024) | Đặc điểm |
|-------|-----------------|----------|
| Information Technology | ~30% | Apple, Microsoft, NVIDIA |
| Financials | ~13% | JPMorgan, Berkshire, Visa |
| Health Care | ~12% | Eli Lilly, J&J, UnitedHealth |
| Consumer Discretionary | ~10% | Amazon, Tesla, McDonald's |
| Communication Services | ~9% | Alphabet, Meta, Netflix |
| Industrials | ~8% | Boeing, Caterpillar, UPS |
| Consumer Staples | ~6% | P&G, Coca-Cola, Walmart |
| Energy | ~4% | ExxonMobil, Chevron |
| Real Estate | ~2.5% | American Tower, Prologis |
| Materials | ~2.5% | Linde, Air Products |
| Utilities | ~2.5% | NextEra, Duke Energy |

**Tại Việt Nam (VN-Index theo ngành):**
- Tài chính ngân hàng: ~35-40% (VCB, BID, CTG, VPB, TCB...)
- Bất động sản: ~15-20%
- Công nghiệp, hàng tiêu dùng, công nghệ: còn lại

---

### 7. Đọc thông tin chỉ số hằng ngày

**Những gì cần chú ý khi đọc tin thị trường:**

1. **Điểm số và % thay đổi:** Luôn đọc %, không chỉ điểm tuyệt đối
2. **Khối lượng giao dịch:** Volume cao + tăng điểm = xác nhận mạnh; Volume thấp + tăng điểm = tăng không bền
3. **Breadth:** Số cổ phiếu tăng vs giảm
4. **Sector performance:** Ngành nào dẫn dắt, ngành nào kéo xuống?
5. **So sánh với benchmark:** VN-Index hôm nay so với region (MSCI EM, SET, KLCI...)

**Ví dụ đọc tin thực tế:**
> "VN-Index tăng 12 điểm (+1.0%) lên 1,250, khối lượng khớp lệnh 750 triệu cổ phiếu. Số cổ phiếu tăng 280, giảm 180, đứng giá 85. Ngân hàng và bất động sản dẫn dắt."

Phân tích:
- Tăng 1%, breadth tốt (280 tăng vs 180 giảm)
- Volume 750M — cần biết trung bình để đánh giá
- Ngân hàng + BĐS tăng → hai trụ cột lớn nhất VN-Index tích cực

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **Chỉ số thị trường** = giỏ cổ phiếu đại diện, là benchmark và đo lường sức khỏe thị trường
2. **S&P 500** (market cap-weighted, 500 cổ phiếu) chính xác và đại diện hơn **Dow Jones** (price-weighted, 30 cổ phiếu)
3. **VN-Index** = toàn bộ HOSE, **VN30** = 30 cổ phiếu lớn nhất — cả hai market cap-weighted
4. **NASDAQ-100** tập trung tech → biến động cao hơn nhưng lợi nhuận dài hạn cũng cao hơn
5. **Market Breadth** (A/D Line, % trên MA200) cho biết sức khỏe thực của thị trường — quan trọng hơn điểm số chỉ số
6. Luôn đọc thị trường bằng **%, không phải điểm tuyệt đối**

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| Market Index | Chỉ số thị trường | Giỏ cổ phiếu đại diện tổng hợp thành một số |
| Benchmark | Điểm chuẩn | Chỉ số dùng để so sánh hiệu suất |
| Price-Weighted | Chỉ số theo giá | Cổ phiếu giá cao ảnh hưởng nhiều hơn |
| Market Cap-Weighted | Chỉ số theo vốn hóa | Vốn hóa lớn ảnh hưởng nhiều hơn |
| Float | Số cổ phiếu lưu hành tự do | Số CP thực sự giao dịch trên thị trường (trừ CP nội bộ) |
| Market Breadth | Chiều rộng thị trường | Đo lường số lượng cổ phiếu tham gia xu hướng |
| A/D Line | Đường Advance/Decline | Số cổ phiếu tăng trừ giảm, tích lũy |
| Divergence | Phân kỳ | Chỉ số và breadth/indicator đi ngược chiều nhau |
| Large-cap | Cổ phiếu vốn hóa lớn | Công ty lớn, ổn định |
| Small-cap | Cổ phiếu vốn hóa nhỏ | Công ty nhỏ, tăng trưởng tiềm năng cao hơn nhưng rủi ro cao |
| GICS | Chuẩn phân loại ngành | Global Industry Classification Standard |
| Sector Rotation | Luân chuyển ngành | Dòng tiền chuyển từ ngành này sang ngành khác |

---

## Bài học tiếp theo

**Ngày 40: IPO, M&A & Corporate Actions**

Chúng ta đã hiểu thị trường hoạt động như thế nào, từ cổ phiếu đơn lẻ đến chỉ số. Ngày mai sẽ cover những **sự kiện đặc biệt** tác động mạnh đến giá cổ phiếu: **IPO** (công ty lên sàn lần đầu), **M&A** (mua bán sáp nhập), **Stock Split** (chia tách cổ phiếu), **Share Buyback** (mua lại cổ phiếu). Đây là những kiến thức giúp bạn nhận biết cơ hội và tránh bẫy khi các sự kiện này xảy ra.
