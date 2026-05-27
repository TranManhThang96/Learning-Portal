# Ngày 41: Quản lý Danh mục Chứng khoán — Portfolio Management

## Mục tiêu học tập
- [ ] Hiểu nguyên tắc xây dựng danh mục đầu tư (Portfolio Construction) đa dạng hóa rủi ro
- [ ] Nắm được khái niệm Rebalancing và biết khi nào cần tái cân bằng danh mục
- [ ] So sánh được hiệu suất danh mục với Benchmark phù hợp
- [ ] Tính toán và giải thích được các chỉ số rủi ro: Beta, Sharpe Ratio, Maximum Drawdown
- [ ] Hiểu các ảnh hưởng thuế đầu tư (Tax Implications) tại Việt Nam và cách tối ưu

---

## Nội dung bài giảng

### 1. Portfolio Construction — Xây dựng danh mục đầu tư

#### 1.1. Portfolio là gì và tại sao cần quản lý?

**Portfolio (Danh mục đầu tư)** là tập hợp tất cả các tài sản tài chính mà bạn đang nắm giữ — cổ phiếu, ETF, trái phiếu, tiền mặt. Quản lý portfolio không chỉ là chọn cổ phiếu tốt, mà còn là tối ưu hóa cách các tài sản này kết hợp với nhau để đạt mục tiêu sinh lời trong khi kiểm soát rủi ro.

Hãy hình dung portfolio như một đội bóng: có tiền đạo (cổ phiếu tăng trưởng cao, rủi ro cao), tiền vệ (cổ phiếu ổn định, cổ tức đều), và hậu vệ (trái phiếu, tiền mặt). Đội mạnh không chỉ có tiền đạo giỏi — cần sự phối hợp cân bằng.

#### 1.2. Các bước xây dựng Portfolio

**Bước 1: Xác định Asset Allocation (Phân bổ tài sản)**

**Asset Allocation** là quyết định tỷ lệ phân bổ vốn giữa các loại tài sản khác nhau. Đây là quyết định quan trọng nhất — nghiên cứu của Brinson (1991) cho thấy **90% hiệu suất dài hạn** của danh mục được quyết định bởi asset allocation, không phải chọn cổ phiếu cụ thể.

Các loại tài sản phổ biến:
- **Equities (Cổ phiếu):** Tiềm năng sinh lời cao, rủi ro cao
- **Fixed Income (Trái phiếu):** Ổn định, lãi suất cố định, rủi ro thấp hơn
- **Cash/Cash Equivalents (Tiền mặt/Tương đương tiền):** Thanh khoản cao, sinh lời thấp
- **Alternatives (Tài sản thay thế):** Vàng, bất động sản, ETF hàng hóa

Công thức phân bổ theo tuổi đơn giản (Rule of 100): **% Cổ phiếu = 100 - Tuổi của bạn**

Ví dụ thực tế Việt Nam:
- Nhà đầu tư 25 tuổi, chịu được rủi ro cao: 80% cổ phiếu / 15% ETF trái phiếu / 5% tiền mặt
- Nhà đầu tư 50 tuổi, cần bảo toàn vốn: 40% cổ phiếu / 40% trái phiếu / 20% tiền mặt

**Bước 2: Diversification (Đa dạng hóa)**

**Diversification** nghĩa là không bỏ tất cả trứng vào một giỏ. Nhưng đa dạng hóa thông minh không chỉ là mua nhiều cổ phiếu — cần phân tán theo:

- **Ngành (Sector Diversification):** Không tập trung quá 30% vào một ngành. Nếu danh mục có VCB (ngân hàng), TCB (ngân hàng), MBB (ngân hàng), BID (ngân hàng) — đây là phân tán giả, rủi ro vẫn tập trung vào ngành ngân hàng.

- **Quy mô công ty (Market Cap Diversification):** Kết hợp Large-cap (VIC, VHM, VCB — ổn định), Mid-cap (DGW, FRT — tăng trưởng), Small-cap (tiềm năng cao, rủi ro cao).

- **Địa lý (Geographic Diversification):** Kết hợp cổ phiếu Việt Nam với ETF quốc tế (FUEVFVND, SSIAM VNFIN LEAD...) để giảm rủi ro quốc gia.

- **Thời gian (Temporal Diversification):** Mua dần nhiều đợt thay vì mua một lần — kết nối với DCA (Day 37).

**Correlation (Tương quan)** là khái niệm quan trọng trong đa dạng hóa. Hai tài sản có correlation thấp hoặc âm sẽ giúp giảm rủi ro tổng thể:
- Correlation = +1: Hai tài sản luôn di chuyển cùng chiều (không đa dạng hóa được)
- Correlation = 0: Không liên quan nhau (đa dạng hóa tốt)
- Correlation = -1: Luôn di chuyển ngược chiều (hedge hoàn hảo)

Ví dụ: Cổ phiếu ngân hàng và vàng thường có correlation âm — khi khủng hoảng, ngân hàng giảm nhưng vàng tăng.

**Bước 3: Position Sizing (Định cỡ vị thế)**

**Position Sizing** là quyết định mỗi cổ phiếu chiếm bao nhiêu % danh mục. Quy tắc phổ biến:

- **Equal Weight (Tỷ trọng đều):** Mỗi cổ phiếu chiếm tỷ lệ bằng nhau. Ví dụ 10 cổ phiếu, mỗi cổ 10%. Đơn giản, dễ quản lý.

- **Market Cap Weight (Theo vốn hóa):** Cổ phiếu lớn hơn chiếm tỷ trọng lớn hơn — cách các ETF chỉ số (VN30, VNINDEX) hoạt động.

- **Risk-based Weight (Theo rủi ro):** Phân bổ nhiều hơn cho cổ phiếu ít rủi ro, ít hơn cho cổ phiếu biến động cao.

- **Conviction-based Weight (Theo mức độ tin tưởng):** Cổ phiếu bạn phân tích kỹ, tin tưởng cao thì phân bổ nhiều hơn. Thường 5-15% cho "high conviction ideas", 2-5% cho các vị thế nhỏ.

**Quy tắc vàng:** Không để một cổ phiếu chiếm quá 20-25% danh mục trừ khi bạn là chuyên gia về ngành đó.

---

### 2. Rebalancing — Tái cân bằng danh mục

#### 2.1. Tại sao cần Rebalancing?

Theo thời gian, do biến động giá, tỷ trọng ban đầu của các cổ phiếu sẽ thay đổi. Ví dụ:

Danh mục ban đầu 100 triệu VND:
- VNM: 30 triệu (30%) — cổ phiếu phòng thủ
- FPT: 40 triệu (40%) — tăng trưởng công nghệ
- FUEVFVND ETF: 20 triệu (20%) — ETF chỉ số
- Tiền mặt: 10 triệu (10%)

Sau 1 năm, FPT tăng 60%, VNM giảm 10%, ETF tăng 15%:
- VNM: 27 triệu (23%)
- FPT: 64 triệu (54%) — vượt ngưỡng mục tiêu!
- FUEVFVND: 23 triệu (19%)
- Tiền mặt: 5 triệu (4%)

Danh mục đã "drift" — lệch xa mục tiêu ban đầu. Rủi ro tập trung vào FPT quá nhiều.

**Rebalancing** là hành động đưa danh mục về tỷ trọng mục tiêu ban đầu bằng cách bán bớt tài sản đã tăng và mua thêm tài sản đã giảm.

#### 2.2. Các chiến lược Rebalancing

**Calendar Rebalancing (Tái cân bằng theo lịch):** Tái cân bằng vào thời điểm cố định — hàng quý, 6 tháng, hoặc hàng năm. Đơn giản, dễ thực hiện nhưng có thể bỏ lỡ thời điểm tốt.

**Threshold Rebalancing (Tái cân bằng theo ngưỡng):** Tái cân bằng khi tỷ trọng một tài sản lệch quá X% so với mục tiêu. Ví dụ: nếu FPT vượt 45% (tỷ trọng mục tiêu 40% ± 5%) thì rebalance. Phản ứng với thị trường tốt hơn nhưng phức tạp hơn.

**Hybrid Rebalancing:** Kết hợp cả hai — kiểm tra theo lịch (hàng quý) và rebalance nếu lệch quá ngưỡng cho phép.

#### 2.3. Chi phí và lợi ích của Rebalancing

**Chi phí:**
- Phí giao dịch (commission)
- **Thuế capital gains** (thuế lãi vốn) — bán cổ phiếu đã tăng sẽ phát sinh thuế
- Công sức và thời gian theo dõi

**Lợi ích:**
- Kiểm soát rủi ro — duy trì profile rủi ro mong muốn
- Buộc bạn "bán cao, mua thấp" — bán cổ phiếu đã tăng, mua cổ đã giảm
- Tránh bị chi phối bởi cảm xúc — rebalancing là kỷ luật tự động

**Mẹo giảm chi phí rebalancing:** Thay vì bán cổ phiếu đã tăng (phát sinh thuế), hướng tiền đầu tư mới vào các tài sản đang thấp hơn tỷ trọng mục tiêu.

---

### 3. Benchmark — Thước đo hiệu suất

#### 3.1. Benchmark là gì?

**Benchmark (Chỉ số tham chiếu)** là thước đo để so sánh hiệu suất danh mục của bạn. Nếu danh mục bạn tăng 15% trong năm, đó là tốt hay xấu? Bạn cần benchmark để biết.

**Các benchmark phổ biến tại Việt Nam:**
- **VN-Index:** Chỉ số tổng hợp sàn HOSE, gồm tất cả cổ phiếu niêm yết
- **VN30:** Top 30 cổ phiếu lớn nhất HOSE về vốn hóa và thanh khoản
- **HNX-Index:** Chỉ số tổng hợp sàn HNX
- **VNMID:** Chỉ số các cổ phiếu vốn hóa trung bình
- **Lãi suất tiết kiệm ngân hàng:** Thước đo đơn giản nhất — bạn có làm tốt hơn gửi ngân hàng không?

#### 3.2. Alpha — Hiệu suất vượt trội so với Benchmark

**Alpha** là phần lợi nhuận danh mục vượt trội hơn so với benchmark (sau khi điều chỉnh rủi ro).

- Alpha > 0: Danh mục đánh bại thị trường
- Alpha = 0: Danh mục theo sát thị trường
- Alpha < 0: Danh mục kém hơn thị trường

Ví dụ: VN-Index tăng 12% trong năm, danh mục của bạn tăng 18% → Alpha ≈ +6%. Bạn đã "beat the market" (đánh bại thị trường).

**Lưu ý quan trọng:** Đa số nhà đầu tư cá nhân (và cả quỹ chuyên nghiệp) không thể liên tục tạo ra Alpha dương sau khi trừ chi phí. Đây là lý do ETF index fund trở nên phổ biến (Day 38).

---

### 4. Risk Metrics — Các chỉ số đo lường rủi ro

#### 4.1. Beta — Độ nhạy cảm với thị trường

**Beta** đo lường mức độ biến động của một cổ phiếu/danh mục so với thị trường chung (benchmark).

**Công thức:** Beta = Covariance(Cổ phiếu, Thị trường) / Variance(Thị trường)

**Cách đọc Beta:**
- **Beta = 1:** Cổ phiếu biến động đúng bằng thị trường. VN-Index tăng 10% → cổ phiếu tăng ~10%
- **Beta > 1 (High Beta):** Cổ phiếu biến động mạnh hơn thị trường. Beta = 1.5 → thị trường tăng 10%, cổ phiếu tăng ~15% (nhưng thị trường giảm 10%, cổ phiếu giảm ~15%)
- **Beta < 1 (Low Beta):** Cổ phiếu biến động ít hơn thị trường. Beta = 0.5 → thị trường tăng 10%, cổ phiếu tăng ~5% (ít rủi ro hơn nhưng cũng ít lợi nhuận hơn)
- **Beta âm:** Cổ phiếu di chuyển ngược chiều thị trường (hiếm gặp — thường là vàng, một số ETF phòng thủ)

**Ví dụ thực tế:**
- VIC, VHM (bất động sản): Thường có Beta cao (~1.3-1.5) — biến động mạnh theo thị trường
- VNM (hàng tiêu dùng thiết yếu): Beta thấp (~0.5-0.7) — ít biến động, cổ phiếu phòng thủ
- VCB (ngân hàng): Beta trung bình (~0.9-1.1)

**Ứng dụng Beta trong quản lý danh mục:**
- Muốn tăng tốc trong bull market: Tăng tỷ trọng cổ phiếu High Beta
- Lo ngại thị trường giảm: Chuyển sang Low Beta stocks, trái phiếu, tiền mặt
- **Portfolio Beta** = Bình quân gia quyền Beta của tất cả cổ phiếu trong danh mục

#### 4.2. Sharpe Ratio — Tỷ lệ lợi nhuận trên rủi ro

**Sharpe Ratio** là chỉ số đo lường lợi nhuận bạn nhận được trên mỗi đơn vị rủi ro chấp nhận. Được phát triển bởi William Sharpe (Nobel Kinh tế 1990).

**Công thức:**
```
Sharpe Ratio = (Rp - Rf) / σp

Trong đó:
- Rp = Lợi nhuận danh mục (Portfolio Return)
- Rf = Lợi suất phi rủi ro (Risk-free Rate) — thường là lãi suất trái phiếu chính phủ
- σp = Độ lệch chuẩn lợi nhuận danh mục (Standard Deviation — đo độ biến động)
```

**Cách đọc Sharpe Ratio:**
- **< 1:** Lợi nhuận không bù đắp xứng đáng cho rủi ro
- **1 - 2:** Tốt — lợi nhuận bù đắp được rủi ro
- **2 - 3:** Rất tốt
- **> 3:** Xuất sắc (hiếm gặp trong thực tế dài hạn)

**Ví dụ so sánh:**

| Danh mục | Lợi nhuận | Độ lệch chuẩn | Sharpe Ratio |
|----------|-----------|---------------|--------------|
| A        | 20%       | 25%           | 0.68         |
| B        | 15%       | 10%           | 1.00         |
| C        | 12%       | 5%            | 1.40         |

*(Giả sử Rf = 5% — lãi suất trái phiếu chính phủ VN)*

Danh mục A có lợi nhuận cao nhất nhưng Sharpe Ratio thấp nhất — nhà đầu tư chịu rủi ro quá nhiều để đạt lợi nhuận đó. Danh mục C tuy lợi nhuận thấp nhất nhưng hiệu quả điều chỉnh rủi ro tốt nhất.

**Hạn chế của Sharpe Ratio:** Chỉ sử dụng độ lệch chuẩn (biến động cả lên lẫn xuống) làm đại diện cho rủi ro — không phân biệt biến động tốt (lên) và biến động xấu (xuống).

**Sortino Ratio** là biến thể cải tiến — chỉ tính biến động âm (downside deviation) trong mẫu số, phản ánh rủi ro thực tế hơn.

#### 4.3. Maximum Drawdown — Mức giảm tối đa

**Maximum Drawdown (MDD)** đo lường mức sụt giảm lớn nhất từ đỉnh cao nhất xuống đáy thấp nhất trong một khoảng thời gian. Đây là chỉ số phản ánh "nỗi đau" thực sự của nhà đầu tư.

**Công thức:**
```
MDD = (Đáy thấp nhất - Đỉnh cao nhất trước đó) / Đỉnh cao nhất trước đó × 100%
```

**Ví dụ:**
- Danh mục đạt đỉnh 150 triệu VND (tháng 4/2022)
- Sau đó giảm xuống 90 triệu VND (tháng 11/2022)
- MDD = (90 - 150) / 150 × 100% = **-40%**

**Ý nghĩa của MDD:**
- MDD -20%: Bạn từng mất 20% từ đỉnh — có thể chịu đựng được
- MDD -40%: Bạn từng mất 40% — áp lực tâm lý rất lớn, nhiều người hoảng loạn bán ra
- MDD -60%: Bạn từng mất 60% — cần tăng 150% chỉ để hòa vốn!

**Recovery Time (Thời gian phục hồi):** Bao lâu để danh mục từ đáy MDD trở lại đỉnh cũ. VN-Index sau đỉnh 1500 điểm (tháng 4/2022) xuống 870 điểm (tháng 11/2022) — MDD khoảng -42%, mất hơn 2 năm để phục hồi.

**Calmar Ratio:** Lợi nhuận hàng năm / |Maximum Drawdown| — đo lường hiệu quả điều chỉnh drawdown, càng cao càng tốt.

#### 4.4. Volatility (Biến động) và Value at Risk (VaR)

**Volatility (Độ biến động)** thường được đo bằng độ lệch chuẩn hàng năm của lợi nhuận. Cổ phiếu Việt Nam thường có volatility 20-40%/năm, ETF thấp hơn.

**VaR — Value at Risk (Giá trị rủi ro):** Ước tính mức tổn thất tối đa với xác suất nhất định trong khoảng thời gian nhất định.

Ví dụ: VaR 95% 1 ngày = -2% nghĩa là "95% khả năng danh mục không mất quá 2% trong 1 ngày". Hay nói khác đi, 1 trong 20 ngày giao dịch, bạn có thể mất hơn 2%.

---

### 5. Tax Implications — Thuế đầu tư chứng khoán

#### 5.1. Thuế tại Việt Nam

Việt Nam hiện áp dụng các loại thuế chứng khoán như sau:

**Thuế thu nhập từ chuyển nhượng chứng khoán:**
- **0.1% trên giá trị giao dịch** (giá bán × khối lượng) — thu ngay khi bán, bất kể lời hay lỗ
- Đây là loại thuế "flat tax on revenue" không phải "capital gains tax" như nhiều nước khác
- Ví dụ: Bán 1000 cổ phiếu FPT tại giá 120,000 VND → thuế = 120,000,000 × 0.1% = **120,000 VND**

**Thuế cổ tức:**
- **5% trên cổ tức nhận bằng tiền mặt** — khấu trừ tại nguồn (broker tự trừ trước khi chuyển vào tài khoản)
- Cổ tức bằng cổ phiếu: Không bị thuế ngay khi nhận, chỉ tính thuế khi bán số cổ phiếu cổ tức đó

#### 5.2. Tối ưu hóa thuế (Tax Optimization)

**Tax-loss Harvesting (Thu hoạch lỗ thuế):** Bán cổ phiếu đang lỗ để "hiện thực hóa" khoản lỗ. Tại Việt Nam, thuế 0.1% trên doanh thu bán, không phụ thuộc lãi/lỗ — nên chiến lược này ít áp dụng so với các nước có capital gains tax. Tuy nhiên vẫn hữu ích để "reset" tâm lý và danh mục.

**Hold Long-term (Nắm giữ dài hạn):** Do thuế 0.1% tính trên mỗi lần bán, trading thường xuyên sẽ tốn thuế + phí giao dịch nhiều hơn. Nắm giữ dài hạn giảm số lần phát sinh thuế.

**Dividend vs Capital Gains:** Cổ tức bị thuế 5%, trong khi lãi vốn (capital gains) từ chênh lệch giá chỉ bị thuế 0.1% trên doanh thu. Với góc độ thuế, lãi vốn có lợi hơn về thuế so với nhận cổ tức.

**Thời điểm nhận cổ tức:** Nếu bạn mua cổ phiếu ngay trước ngày chốt danh sách cổ đông (Record Date) để nhận cổ tức, thường giá cổ phiếu sẽ giảm tương đương giá trị cổ tức vào ngày Ex-Dividend. Bạn không "được" gì thêm về mặt kinh tế nhưng lại phải đóng 5% thuế cổ tức — cần cân nhắc kỹ.

#### 5.3. Chi phí giao dịch và tác động tổng hợp

Ngoài thuế, mỗi lần giao dịch còn phát sinh:
- **Phí môi giới (Brokerage Fee):** 0.1% - 0.35% tùy công ty chứng khoán
- **Thuế 0.1%** trên giá trị bán
- **Spread giá (Bid-Ask Spread):** Chênh lệch giá mua/bán thực tế

Tổng chi phí một vòng mua-bán (round trip): ~0.3% - 0.8% giá trị giao dịch.

Nếu bạn giao dịch 10 lần/năm với mỗi lần chi phí 0.5%, bạn mất **5%/năm chỉ cho chi phí giao dịch** — trước khi tính xem bạn có chọn đúng cổ phiếu hay không! Đây là một trong những lý do tại sao chiến lược Buy & Hold (mua và nắm giữ dài hạn) thường vượt trội so với trading tần suất cao.

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **Portfolio Construction** bao gồm ba quyết định cốt lõi: Asset Allocation (phân bổ tài sản), Diversification (đa dạng hóa), và Position Sizing (định cỡ vị thế) — 90% hiệu suất dài hạn đến từ Asset Allocation.

2. **Diversification thông minh** không chỉ là mua nhiều cổ phiếu, mà là chọn tài sản có Correlation thấp với nhau — đa dạng hóa theo ngành, quy mô, địa lý.

3. **Rebalancing** là kỷ luật đưa danh mục về tỷ trọng mục tiêu — tự động thực hiện "bán cao, mua thấp" và kiểm soát rủi ro theo thời gian.

4. **Beta** đo độ nhạy cảm với thị trường: Beta >1 biến động mạnh hơn thị trường, Beta <1 ổn định hơn. Dùng để điều chỉnh mức độ rủi ro toàn danh mục.

5. **Sharpe Ratio** = lợi nhuận bù rủi ro / rủi ro — so sánh hiệu quả hai danh mục có mức rủi ro khác nhau. Sharpe >1 là tốt, >2 là xuất sắc.

6. **Maximum Drawdown** phản ánh "nỗi đau" thực tế — tài sản giảm 50% cần tăng 100% để hòa vốn. Kiểm soát MDD quan trọng hơn tối đa hóa lợi nhuận.

7. **Thuế chứng khoán Việt Nam:** 0.1% trên doanh thu bán + 5% thuế cổ tức. Giao dịch ít, nắm giữ dài hạn giúp tối ưu hóa chi phí thuế.

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|---------------------|------------------|-----------------|
| Portfolio | Danh mục đầu tư | Tập hợp tất cả tài sản tài chính đang nắm giữ |
| Portfolio Construction | Xây dựng danh mục | Quá trình chọn tài sản và phân bổ tỷ trọng |
| Asset Allocation | Phân bổ tài sản | Quyết định tỷ lệ phân chia vốn giữa các loại tài sản |
| Diversification | Đa dạng hóa | Phân tán rủi ro bằng cách đầu tư nhiều loại tài sản |
| Correlation | Tương quan | Mức độ di chuyển cùng chiều/ngược chiều giữa hai tài sản |
| Position Sizing | Định cỡ vị thế | Quyết định mỗi tài sản chiếm bao nhiêu % danh mục |
| Rebalancing | Tái cân bằng danh mục | Đưa danh mục về tỷ trọng mục tiêu ban đầu |
| Benchmark | Chỉ số tham chiếu | Thước đo hiệu suất để so sánh với danh mục |
| Alpha | Lợi nhuận vượt trội | Phần lợi nhuận vượt hơn benchmark sau điều chỉnh rủi ro |
| Beta | Hệ số biến động | Độ nhạy cảm của cổ phiếu/danh mục so với thị trường |
| Sharpe Ratio | Tỷ lệ Sharpe | Lợi nhuận điều chỉnh rủi ro: (Rp-Rf)/σ |
| Maximum Drawdown (MDD) | Mức giảm tối đa | % sụt giảm từ đỉnh xuống đáy trong kỳ phân tích |
| Volatility | Biến động giá | Độ lệch chuẩn của lợi nhuận, đo mức độ không ổn định |
| Value at Risk (VaR) | Giá trị rủi ro | Mức tổn thất tối đa với xác suất nhất định |
| Capital Gains | Lãi vốn | Lợi nhuận từ chênh lệch giá mua và giá bán |
| Tax-loss Harvesting | Thu hoạch lỗ thuế | Bán tài sản lỗ để giảm nghĩa vụ thuế |
| Risk-free Rate | Lợi suất phi rủi ro | Lãi suất không có rủi ro, thường là trái phiếu chính phủ |
| Equal Weight | Tỷ trọng đều | Phân bổ đều nhau cho mọi tài sản trong danh mục |
| Downside Deviation | Biến động âm | Độ lệch chuẩn chỉ tính các kết quả âm |

---

## Bài học tiếp theo

**Ngày 42: Thực hành tổng hợp chứng khoán** — Đây là ngày thực hành cuối cùng của Stock Module! Bạn sẽ áp dụng toàn bộ kiến thức từ Day 33 đến Day 41 để xây dựng danh mục đầu tư giả định với 100 triệu VND thực tế. Từ việc chọn mã cổ phiếu bằng phân tích cơ bản & kỹ thuật, phân bổ tỷ trọng theo các nguyên tắc portfolio management, đặt Stop-loss và Take-profit cụ thể, đến đăng ký tài khoản demo để luyện tập không rủi ro. Chuẩn bị sẵn danh sách 5-10 cổ phiếu bạn quan tâm nhé!
