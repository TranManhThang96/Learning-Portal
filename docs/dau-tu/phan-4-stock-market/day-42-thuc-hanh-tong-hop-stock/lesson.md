# Ngày 42: Thực hành tổng hợp chứng khoán — Xây dựng danh mục 100 triệu VND

## Mục tiêu học tập
- [ ] Áp dụng toàn bộ kiến thức từ Day 33-41 để xây dựng danh mục đầu tư thực tế giả định
- [ ] Lựa chọn cổ phiếu dựa trên phân tích cơ bản (Day 35-36) kết hợp phân tích kỹ thuật (Day 31-32)
- [ ] Phân bổ tỷ trọng theo nguyên tắc Portfolio Construction (Day 41)
- [ ] Đặt Stop-loss và Take-profit cụ thể cho từng vị thế
- [ ] Đăng ký và sử dụng tài khoản chứng khoán demo để luyện tập
- [ ] Tổng kết toàn bộ Stock Module và xác định bước tiếp theo

---

## Nội dung bài giảng

### 1. Nhìn lại hành trình — Stock Module từ Day 33 đến Day 41

Trước khi bắt tay vào thực hành, hãy dừng lại một chút và nhìn lại những gì bạn đã học trong 10 ngày qua của **Stock Module (Phần 4: Thị trường chứng khoán)**:

| Ngày | Chủ đề | Kỹ năng cốt lõi |
|------|--------|-----------------|
| Day 33 | Chứng khoán cơ bản | Hiểu cách thị trường hoạt động, lệnh mua/bán |
| Day 34 | Margin & Short Selling | Công cụ đòn bẩy và bán khống, rủi ro cao |
| Day 35 | Value Investing | P/E, P/B, DCF — tìm cổ phiếu định giá thấp |
| Day 36 | Growth Investing | PEG, Revenue Growth — tìm cổ phiếu tăng trưởng |
| Day 37 | DCA & Dividend | Đầu tư định kỳ, lựa chọn cổ tức |
| Day 38 | ETF & Index Fund | Đầu tư thụ động, chi phí thấp |
| Day 39 | Market Indices | VN-Index, VN30, cách đọc chỉ số |
| Day 40 | IPO, M&A, Corporate Actions | Sự kiện đặc biệt ảnh hưởng giá |
| Day 41 | Portfolio Management | Beta, Sharpe, MDD, Rebalancing |

Hôm nay là ngày tổng hợp — bạn sẽ đóng vai một nhà đầu tư thực sự với 100 triệu VND.

---

### 2. Khung tư duy trước khi xây dựng danh mục

#### 2.1. Xác định Investment Policy Statement (IPS) — Tuyên bố chính sách đầu tư

**IPS (Investment Policy Statement — Tuyên bố chính sách đầu tư)** là bản kế hoạch cá nhân trả lời các câu hỏi nền tảng trước khi đầu tư. Các quỹ chuyên nghiệp bắt buộc phải có IPS; nhà đầu tư cá nhân viết IPS sẽ giảm đáng kể các quyết định bốc đồng theo cảm xúc.

**Bản IPS mẫu cho danh mục 100 triệu VND:**

```
Mục tiêu sinh lời: 15-20%/năm (vượt VN-Index + 5%)
Chân trời đầu tư: 3-5 năm
Khẩu vị rủi ro: Trung bình-cao (chịu được MDD tối đa -30%)
Hạn chế: Không đầu tư cổ phiếu ngành cờ bạc, thuốc lá
Tiêu chí chọn cổ phiếu:
  - ROE > 15%
  - Tăng trưởng EPS 3 năm > 10%/năm
  - P/E < 20x hoặc PEG < 1.5
  - Thanh khoản > 1 triệu cổ phiếu/ngày
Quy tắc quản lý rủi ro:
  - Stop-loss: -15% từ giá mua cho mỗi cổ phiếu
  - Không cổ phiếu nào chiếm > 25% danh mục
  - Rebalancing: Hàng quý nếu lệch > 5%
```

#### 2.2. Phân bổ tài sản ban đầu (Asset Allocation)

Với 100 triệu VND và mục tiêu tăng trưởng trung bình-cao, một phân bổ hợp lý có thể là:

```
Cổ phiếu cá nhân:     70 triệu (70%)
ETF / Index Fund:     15 triệu (15%)
Tiền mặt dự phòng:    15 triệu (15%)
```

Tại sao giữ 15% tiền mặt?
- Cơ hội mua thêm khi thị trường giảm mạnh (dry powder)
- Tâm lý ổn định hơn — không bị margin call, không cần bán vội
- Sẵn sàng cho các cơ hội IPO hấp dẫn (Day 40)

---

### 3. Quy trình chọn cổ phiếu — Stock Screening

#### 3.1. Bước 1: Screener lọc cổ phiếu

**Stock Screener (Bộ lọc cổ phiếu)** là công cụ lọc cổ phiếu theo các tiêu chí định lượng. Tại Việt Nam, bạn có thể dùng:
- **FireAnt.vn** — screener miễn phí khá mạnh
- **Simplize.vn** — phân tích sâu hơn, có scoring
- **Vndirect.com.vn** — screener trực tiếp trên sàn

**Tiêu chí screener tham khảo (Chiến lược GARP — Growth at Reasonable Price):**
- Vốn hóa > 1,000 tỷ VND (tránh cổ phiếu quá nhỏ, dễ bị thao túng)
- Thanh khoản bình quân > 2 tỷ VND/ngày
- ROE > 15% (3 năm liên tiếp)
- EPS tăng trưởng > 10%/năm (3 năm)
- P/E < 20x
- Nợ/Vốn chủ sở hữu (D/E) < 1 (trừ ngân hàng, D/E cao là bình thường)

#### 3.2. Bước 2: Phân tích cơ bản sâu (Fundamental Analysis)

Sau khi screener lọc ra danh sách ứng viên, bạn cần phân tích sâu hơn:

**Phân tích doanh nghiệp (Business Analysis):**
- Mô hình kinh doanh: Công ty kiếm tiền như thế nào?
- Lợi thế cạnh tranh (Competitive Moat): Thương hiệu mạnh? Bằng sáng chế? Chi phí thấp? Network effects?
- Vị thế trong ngành: Market share đang tăng hay giảm?
- Ban lãnh đạo: Lịch sử quản trị, sở hữu cổ phần của lãnh đạo (insider ownership)

**Phân tích tài chính:**
- Đọc Báo cáo kết quả kinh doanh (Income Statement): Doanh thu, lợi nhuận gộp, lợi nhuận ròng
- Đọc Bảng cân đối kế toán (Balance Sheet): Tài sản, nợ, vốn chủ sở hữu
- Đọc Báo cáo lưu chuyển tiền tệ (Cash Flow Statement): **Free Cash Flow (FCF)** — tiền mặt thực sự tạo ra
- Tính các chỉ số: P/E, P/B, ROE, ROA, ROIC, EV/EBITDA

**Định giá (Valuation):**
- So sánh P/E với trung bình ngành và lịch sử
- Tính Intrinsic Value bằng DCF đơn giản (Day 35)
- Xác định Margin of Safety: Giá hiện tại thấp hơn Intrinsic Value bao nhiêu %?

#### 3.3. Bước 3: Phân tích kỹ thuật (Technical Analysis) để chọn Entry Point

Phân tích cơ bản cho biết **nên mua cổ phiếu gì**, phân tích kỹ thuật giúp xác định **mua vào lúc nào** và **ở mức giá nào**.

**Entry Point (Điểm vào lệnh) lý tưởng:**
- Giá vừa phá vỡ kháng cự (Breakout) với khối lượng tăng
- Giá pullback về đường MA50 hoặc MA200 sau xu hướng tăng
- RSI trong vùng 40-60 (không quá mua, không quá bán)
- MACD cắt lên Signal Line (bullish crossover)

**Ví dụ thực tế:** Bạn muốn mua FPT. Phân tích cơ bản cho thấy công ty tốt, P/E hợp lý. Phân tích kỹ thuật cho thấy giá đang test đường MA50 tại 115,000 VND, RSI = 45, MACD đang tích lũy. Đây là entry point tốt hơn so với mua khi FPT đang tăng mạnh ở 135,000 VND với RSI = 75.

---

### 4. Xây dựng danh mục mẫu 100 triệu VND

#### 4.1. Ví dụ danh mục minh họa (tham khảo, không phải khuyến nghị đầu tư)

Dưới đây là một ví dụ danh mục giả định minh họa quy trình xây dựng. Bạn cần tự nghiên cứu và xây dựng danh mục phù hợp với mình.

**Danh mục giả định — Chiến lược GARP, chân trời 3 năm:**

| Mã | Tên công ty | Ngành | Số lượng CP | Giá tham khảo | Giá trị | Tỷ trọng | Lý do chọn |
|----|-------------|-------|-------------|--------------|---------|----------|------------|
| FPT | FPT Corp | Công nghệ | 150 | 115,000 | 17.25 triệu | 17.25% | Tăng trưởng IT, dịch vụ nước ngoài |
| VCB | Vietcombank | Ngân hàng | 200 | 87,000 | 17.4 triệu | 17.4% | Ngân hàng lớn, chất lượng tài sản tốt |
| MWG | Mobile World | Bán lẻ | 380 | 46,000 | 17.48 triệu | 17.48% | Bán lẻ tiêu dùng, phục hồi theo chu kỳ |
| VNM | Vinamilk | Tiêu dùng thiết yếu | 255 | 70,000 | 17.85 triệu | 17.85% | Defensive stock, dòng tiền ổn định |

Tổng nhóm cổ phiếu cá nhân: khoảng **69.98 triệu VND**, gần đúng mục tiêu 70 triệu. Phần còn lại của danh mục mẫu là ETF 15 triệu và tiền mặt 15 triệu. *(Lưu ý: Đây là ví dụ minh họa, giá tham khảo có thể không phản ánh giá thực tế hiện tại.)*

**Thay vào đó, hãy xây dựng danh mục theo template sau:**

```
Danh mục mẫu — [Tên của bạn] — Ngày: ___________
Tổng vốn: 100,000,000 VND

Phân bổ chiến lược:
├── Cổ phiếu cá nhân: 70,000,000 VND (70%)
│   ├── Ngành 1 (____): __ triệu (__%)
│   ├── Ngành 2 (____): __ triệu (__%)
│   └── Ngành 3 (____): __ triệu (__%)
├── ETF: 15,000,000 VND (15%)
└── Tiền mặt: 15,000,000 VND (15%)
```

#### 4.2. Tiêu chí phân bổ tỷ trọng

**Quy tắc tỷ trọng gợi ý:**

| Loại vị thế | Tỷ trọng | Mô tả |
|-------------|----------|-------|
| Core Holdings (Nền tảng) | 15-25% mỗi mã | 2-3 cổ phiếu chất lượng cao, nắm giữ dài hạn |
| Satellite Holdings (Vệ tinh) | 5-10% mỗi mã | 4-6 cổ phiếu bổ sung, tăng trưởng |
| Speculative (Đầu cơ) | 2-5% mỗi mã | 0-2 cổ phiếu rủi ro cao, tiềm năng lớn |
| ETF | 10-15% | Phòng thủ, theo dõi chỉ số |
| Tiền mặt | 10-20% | Dự phòng cơ hội |

**Ví dụ phân bổ:**
- **Core (VCB, FPT):** 20% mỗi mã → 40 triệu
- **Satellite (MWG, VNM, HPG):** 8% mỗi mã → 24 triệu
- **Speculative (1 cổ phiếu nhỏ tiềm năng):** 3% → 3 triệu
- **ETF FUEVFVND:** 15% → 15 triệu
- **Tiền mặt:** 18% → 18 triệu

---

### 5. Stop-loss và Take-profit — Quản lý vị thế

#### 5.1. Stop-loss (Cắt lỗ) — Ranh giới bảo vệ vốn

**Stop-loss** là mức giá bạn sẽ bán cổ phiếu để giới hạn tổn thất nếu giá đi ngược dự đoán. Đây là kỷ luật quan trọng nhất trong trading.

**Các phương pháp đặt Stop-loss:**

**1. Percentage Stop (Dừng lỗ theo %):**
- Ví dụ: Mua FPT tại 115,000 VND, stop-loss -15% → Bán nếu giá xuống 97,750 VND
- Ưu điểm: Đơn giản, dễ tính
- Nhược điểm: Không tính đến cấu trúc kỹ thuật của biểu đồ

**2. Technical Stop (Dừng lỗ kỹ thuật):**
- Đặt stop dưới vùng hỗ trợ quan trọng hoặc đường MA
- Ví dụ: Mua FPT khi giá phá vỡ kháng cự 115,000 VND, stop-loss dưới đường MA50 tại 108,000 VND
- Ưu điểm: Dựa trên cấu trúc thị trường, hợp lý hơn
- Nhược điểm: Phức tạp hơn, cần biết phân tích kỹ thuật

**3. ATR Stop (Average True Range Stop):**
- Stop-loss = Giá mua - (2 × ATR)
- ATR đo mức biến động trung bình — giúp stop-loss không bị "shake out" (bị dừng lỗ sớm do biến động bình thường)

**Nguyên tắc Risk per Trade:** Không để một giao dịch thua lỗ quá **2-3% tổng danh mục**.

Ví dụ: Danh mục 100 triệu, risk per trade = 2% = 2 triệu VND.
- Mua FPT tại 115,000 VND, stop-loss tại 108,000 VND → Risk per share = 7,000 VND
- Số cổ phiếu tối đa = 2,000,000 / 7,000 = **285 cổ phiếu**
- Giá trị vị thế = 285 × 115,000 = **32.8 triệu VND** (32.8% danh mục)
- Nếu vị thế này quá lớn so với tỷ trọng mục tiêu, cần giảm số cổ phiếu xuống

#### 5.2. Take-profit (Chốt lời)

**Take-profit** là mức giá bạn sẽ bán một phần hoặc toàn bộ vị thế để hiện thực hóa lợi nhuận.

**Chiến lược Take-profit phổ biến:**

**1. Fixed Target (Mục tiêu cố định):**
- Đặt Take-profit tại mức lãi 30%, 50%, hoặc 100% từ giá mua
- Đơn giản nhưng có thể bỏ lỡ lợi nhuận nếu cổ phiếu tiếp tục tăng mạnh

**2. Staged Exit (Chốt lời từng phần):**
- Bán 1/3 khi lãi 20%, bán 1/3 khi lãi 40%, nắm giữ 1/3 dài hạn
- Bảo đảm chốt lời nhưng vẫn giữ cơ hội tăng thêm

**3. Trailing Stop (Dừng lỗ di động):**
- Stop-loss di chuyển theo giá khi giá tăng lên
- Ví dụ: Trailing stop 10% → Nếu FPT lên 150,000, stop tự động lên 135,000
- Khi giá quay đầu giảm qua 135,000 → Tự động bán
- Ưu điểm: Không cần đặt mục tiêu cứng, để giá chạy tự nhiên

**4. Fundamental-based Exit (Thoát dựa trên cơ bản):**
- Bán khi định giá trở nên quá cao (P/E vượt 2 lần trung bình lịch sử)
- Bán khi có sự thay đổi cơ bản tiêu cực trong doanh nghiệp (lợi nhuận giảm liên tục, lãnh đạo từ chức...)
- Phù hợp nhất với Value/Growth Investing dài hạn

**Bảng Stop-loss và Take-profit mẫu:**

| Mã CP | Giá mua | Stop-loss | % Stop | Take-profit 1 | Take-profit 2 | R/R Ratio |
|-------|---------|-----------|--------|--------------|--------------|-----------|
| FPT | 115,000 | 98,000 | -14.8% | 138,000 (+20%) | 161,000 (+40%) | 1:1.35 |
| VCB | 87,000 | 74,000 | -14.9% | 104,000 (+20%) | 122,000 (+40%) | 1:1.34 |
| MWG | 46,000 | 39,000 | -15.2% | 57,500 (+25%) | 70,000 (+52%) | 1:1.65 |

**Risk/Reward Ratio (R/R)** = (Take-profit - Giá mua) / (Giá mua - Stop-loss)

Nguyên tắc: R/R tối thiểu phải ≥ 1:1.5 nghĩa là tiềm năng lãi ít nhất bằng 1.5 lần rủi ro thua.

---

### 6. Tài khoản Demo — Luyện tập không rủi ro

#### 6.1. Tại sao nên dùng tài khoản Demo trước?

**Demo Account (Tài khoản mô phỏng)** là tài khoản giao dịch sử dụng tiền ảo nhưng hoạt động với dữ liệu thị trường thực. Đây là "sân tập" an toàn để:

- Làm quen giao diện phần mềm giao dịch
- Thực hành đặt lệnh, chỉnh sửa, hủy lệnh
- Test chiến lược đầu tư mà không mất tiền thực
- Xây dựng kỷ luật tâm lý trước khi đối mặt với tiền thật

**Lưu ý:** Demo account không hoàn toàn tái hiện cảm xúc thực khi giao dịch bằng tiền thật — nhưng vẫn tốt hơn nhiều so với "nhảy vào" thị trường khi chưa quen thao tác.

#### 6.2. Các nền tảng Demo tại Việt Nam

**1. VCBS (Vietcombank Securities) — Demo Trading:**
- Truy cập: vcbs.com.vn → Dịch vụ → Giao dịch thử
- Giao diện VCBSmart với dữ liệu real-time
- Phù hợp cho người mới hoàn toàn

**2. SSI (Saigon Securities) — iBoard Paper Trading:**
- Đăng ký tài khoản SSI, chọn chế độ giả lập
- Giao diện iBoard đầy đủ tính năng

**3. VPS Securities — VPS SmartOne Demo:**
- App mobile SmartOne có chế độ demo
- Đặc biệt tốt cho giao dịch trên điện thoại

**4. Nền tảng quốc tế (cho ETF, cổ phiếu Mỹ):**
- **TradingView (tradingview.com):** Paper Trading với cổ phiếu toàn cầu
- **TD Ameritrade thinkorswim:** Demo cực kỳ mạnh, đầy đủ công cụ kỹ thuật

#### 6.3. Hướng dẫn đăng ký tài khoản chứng khoán thực

Nếu bạn đã sẵn sàng giao dịch thực, đây là quy trình tổng quát:

**Bước 1: Chọn Công ty Chứng khoán (CTCK)**
Tiêu chí lựa chọn:
- Phí giao dịch thấp
- Giao diện app/web dễ dùng
- Dịch vụ hỗ trợ tốt
- Tính thanh khoản margin (nếu cần)

**Bước 2: Mở tài khoản**
- Chuẩn bị: CMND/CCCD, tài khoản ngân hàng
- Đăng ký online qua app CTCK hoặc đến chi nhánh
- Ký hợp đồng điện tử (eKYC)
- Nhận mã số tài khoản và mật khẩu

**Bước 3: Nộp tiền**
- Chuyển khoản ngân hàng vào tài khoản chứng khoán
- Thường xử lý trong T+1 ngày làm việc

**Bước 4: Thực hiện giao dịch đầu tiên**
- Tốt nhất: Mua ETF VN30 (FUEVFVND hoặc E1VFVN30) trước
- Làm quen với lệnh, khớp lệnh, xem portfolio

---

### 7. Tổng kết Stock Module — Key Lessons

#### 7.1. Những điều quan trọng nhất sau 10 ngày

**Về triết lý đầu tư:**
- Không có chiến lược nào là tốt nhất mọi lúc — Value, Growth, DCA, ETF đều có vai trò riêng
- **Consistency (Nhất quán)** quan trọng hơn tìm kiếm "công thức hoàn hảo"
- Kiểm soát rủi ro quan trọng hơn tối đa hóa lợi nhuận — thua ít để thắng lâu dài

**Về tâm lý:**
- Thị trường không hợp lý ngắn hạn, nhưng hợp lý dài hạn
- Cảm xúc (sợ hãi + tham lam) là kẻ thù số một của nhà đầu tư cá nhân
- Có kế hoạch rõ ràng trước khi vào lệnh — IPS, stop-loss, take-profit

**Về thực hành:**
- Bắt đầu nhỏ, học từ thực tế thị trường
- Ghi chép Investment Journal (nhật ký đầu tư) — tại sao mua, tại sao bán
- Review định kỳ — không chỉ xem lãi/lỗ mà hiểu được mình đúng/sai ở đâu

#### 7.2. Lộ trình tiếp theo sau Stock Module

```
Stock Module (Day 33-42) ✓ HOÀN THÀNH
           ↓
     Phần 5: Forex
     ├── Day 43: Forex cơ bản
     ├── Day 44: Pip, Lot, Leverage & Spread
     ├── Day 45: Fundamental Analysis trong Forex
     └── Day 52: Thực hành tổng hợp Forex
           ↓
     Phần 6: Tiền số (Crypto)
     ├── Day 53: Bitcoin & Blockchain
     ├── Day 55: DeFi, NFT, DAO
     └── ...
```

Trước khi bước vào Forex, hãy đảm bảo bạn đã:
- [ ] Đọc ít nhất 2 báo cáo tài chính doanh nghiệp
- [ ] Xây dựng danh mục demo ít nhất 1 tháng
- [ ] Tính được P/E, ROE, Sharpe Ratio không cần xem tài liệu

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **Xây dựng IPS** trước khi đầu tư — xác định mục tiêu, khẩu vị rủi ro, tiêu chí chọn cổ phiếu. IPS giúp bạn không ra quyết định bốc đồng theo cảm xúc.

2. **Quy trình chọn cổ phiếu** gồm 3 bước: Screener lọc định lượng → Phân tích cơ bản sâu → Phân tích kỹ thuật tìm Entry Point tốt.

3. **Cấu trúc danh mục** theo tầng: Core Holdings (15-25%) + Satellite Holdings (5-10%) + Speculative (<5%) + ETF + Tiền mặt. Đa dạng hóa theo ngành, không chỉ theo số lượng.

4. **Stop-loss** là kỷ luật quan trọng nhất — đặt TRƯỚC khi mua, không thay đổi khi cảm xúc hoảng loạn. Nguyên tắc: không thua quá 2-3% tổng danh mục cho một giao dịch.

5. **Risk/Reward Ratio ≥ 1:1.5** — Chỉ vào lệnh khi tiềm năng lãi ít nhất 1.5 lần rủi ro thua. Ngay cả khi chỉ thắng 50% số giao dịch, bạn vẫn có lời tổng thể.

6. **Tài khoản Demo** là bước đệm quan trọng — làm quen thao tác, test chiến lược, xây dựng kỷ luật trước khi dùng tiền thật.

7. **Nhật ký đầu tư (Investment Journal)** là công cụ học tập mạnh nhất — ghi lại lý do mua/bán, cảm xúc lúc đó, bài học rút ra. Sau 6 tháng nhìn lại bạn sẽ thấy rõ điểm mạnh/yếu của mình.

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| Investment Policy Statement (IPS) | Tuyên bố chính sách đầu tư | Bản kế hoạch cá nhân về mục tiêu, khẩu vị rủi ro và tiêu chí đầu tư |
| Stock Screener | Bộ lọc cổ phiếu | Công cụ lọc cổ phiếu theo tiêu chí định lượng |
| Entry Point | Điểm vào lệnh | Mức giá tối ưu để mua vào một vị thế |
| Stop-loss | Dừng lỗ / Cắt lỗ | Lệnh bán tự động khi giá xuống mức đã định để giới hạn tổn thất |
| Take-profit | Chốt lời | Lệnh bán khi giá đạt mức mục tiêu lợi nhuận |
| Trailing Stop | Dừng lỗ di động | Stop-loss tự động di chuyển theo chiều giá tăng |
| Risk/Reward Ratio (R/R) | Tỷ lệ rủi ro/lợi nhuận | So sánh tiềm năng lãi với rủi ro thua của một giao dịch |
| Risk per Trade | Rủi ro mỗi giao dịch | % tổng danh mục bạn sẵn sàng mất cho một giao dịch |
| Position Sizing | Định cỡ vị thế | Tính toán số lượng cổ phiếu mua dựa trên rủi ro |
| Core Holdings | Vị thế nền tảng | Cổ phiếu chất lượng cao, tỷ trọng lớn, nắm giữ dài hạn |
| Satellite Holdings | Vị thế vệ tinh | Cổ phiếu bổ sung tỷ trọng nhỏ hơn |
| Demo Account | Tài khoản mô phỏng | Tài khoản giao dịch tiền ảo với dữ liệu thực |
| Investment Journal | Nhật ký đầu tư | Ghi chép quyết định, lý do, bài học từ mỗi giao dịch |
| GARP | Tăng trưởng ở giá hợp lý | Growth at Reasonable Price — kết hợp value và growth |
| Paper Trading | Giao dịch giả lập | Thực hành đầu tư không dùng tiền thật |
| Dry Powder | Tiền mặt dự phòng | Tiền mặt giữ lại để nắm bắt cơ hội khi thị trường giảm |

---

## Bài học tiếp theo

**Ngày 43: Forex cơ bản** — Bước vào thị trường ngoại hối, nơi các đồng tiền được giao dịch theo cặp như EUR/USD, USD/JPY hoặc USD/VND. Phần tiếp theo sẽ nhấn mạnh cơ chế thị trường 24/5, pip, lot, spread, leverage và đặc biệt là kỷ luật quản trị rủi ro trước khi dùng tài khoản thật.
