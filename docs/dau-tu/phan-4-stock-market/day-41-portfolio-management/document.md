# Tài liệu tham khảo — Ngày 41: Portfolio Management

## 1. Bảng tóm tắt Asset Allocation theo mục tiêu đầu tư

| Mục tiêu | Cổ phiếu | Trái phiếu/ETF bond | Tiền mặt | Phù hợp với |
|----------|----------|---------------------|----------|-------------|
| Tăng trưởng tích cực | 80-90% | 5-10% | 5-10% | Dưới 35 tuổi, chịu rủi ro cao, chân trời đầu tư >10 năm |
| Tăng trưởng cân bằng | 60-70% | 20-25% | 10-15% | 35-50 tuổi, chịu rủi ro trung bình, chân trời 5-10 năm |
| Bảo toàn và thu nhập | 30-40% | 40-50% | 15-20% | Trên 50 tuổi, ưu tiên bảo toàn vốn, cần thu nhập ổn định |
| Cực kỳ thận trọng | 10-20% | 50-60% | 25-30% | Gần hưu, không chịu được tổn thất lớn |

---

## 2. Cheat Sheet — Công thức Risk Metrics

### Beta
```
Beta = Cov(Ri, Rm) / Var(Rm)

Ri = Lợi nhuận cổ phiếu i
Rm = Lợi nhuận thị trường (benchmark)
Cov = Hiệp phương sai
Var = Phương sai

Phân loại:
• Beta < 0.5  → Cực kỳ phòng thủ (Defensive)
• Beta 0.5-1  → Phòng thủ (Low volatility)
• Beta 1      → Theo sát thị trường (Market-neutral)
• Beta 1-1.5  → Tăng trưởng (Cyclical)
• Beta > 1.5  → Đầu cơ cao (Aggressive)
```

### Sharpe Ratio
```
Sharpe = (Rp - Rf) / σp

Rp = Lợi nhuận danh mục (annualized)
Rf = Lãi suất phi rủi ro (~4-5% tại VN, trái phiếu CP 10 năm)
σp = Độ lệch chuẩn lợi nhuận danh mục (annualized)

Đánh giá:
• < 0    → Tệ (tốt hơn để tiền ngân hàng)
• 0-0.5  → Kém
• 0.5-1  → Chấp nhận được
• 1-2    → Tốt
• 2-3    → Rất tốt
• > 3    → Xuất sắc
```

### Maximum Drawdown
```
MDD = (Trough - Peak) / Peak × 100%

Trough = Giá trị thấp nhất sau khi đạt đỉnh
Peak = Giá trị cao nhất trước đó

Hồi phục từ MDD:
• MDD -10% → Cần tăng +11.1% để hòa vốn
• MDD -20% → Cần tăng +25% để hòa vốn
• MDD -33% → Cần tăng +50% để hòa vốn
• MDD -50% → Cần tăng +100% để hòa vốn
• MDD -75% → Cần tăng +300% để hòa vốn
```

### Portfolio Beta (Hệ số Beta tổng hợp)
```
Portfolio Beta = Σ (Tỷ trọng_i × Beta_i)

Ví dụ:
VCB: 25% × Beta 0.9 = 0.225
FPT: 30% × Beta 1.2 = 0.360
VHM: 20% × Beta 1.4 = 0.280
FUEVFVND: 15% × Beta 1.0 = 0.150
Tiền mặt: 10% × Beta 0.0 = 0.000
                             ─────
Portfolio Beta               = 1.015
```

---

## 3. Khung phân tích danh mục (Portfolio Review Framework)

### Kiểm tra định kỳ hàng quý — Checklist

**A. Hiệu suất (Performance)**
- [ ] Lợi nhuận YTD (từ đầu năm) là bao nhiêu %?
- [ ] So sánh với VN-Index: Alpha = ?
- [ ] Sharpe Ratio có cải thiện so với kỳ trước?

**B. Rủi ro (Risk)**
- [ ] Portfolio Beta hiện tại = ? (so với mục tiêu)
- [ ] Maximum Drawdown trong kỳ = ?
- [ ] Có cổ phiếu nào vi phạm ngưỡng Stop-loss?

**C. Tỷ trọng (Allocation)**
- [ ] Tỷ trọng từng cổ phiếu có lệch > 5% so với mục tiêu?
- [ ] Có ngành nào chiếm > 35% danh mục?
- [ ] Tỷ lệ tiền mặt có đủ để nắm bắt cơ hội?

**D. Fundamental Review**
- [ ] Có thay đổi gì về business của các công ty đang nắm giữ?
- [ ] Kết quả kinh doanh quý gần nhất có đáp ứng kỳ vọng?
- [ ] Có tin tức corporate actions (cổ tức, phát hành thêm) nào cần lưu ý?

---

## 4. Bảng tóm tắt thuế chứng khoán Việt Nam

| Loại thu nhập | Thuế suất | Cách tính | Thời điểm nộp |
|---------------|-----------|-----------|---------------|
| Chuyển nhượng cổ phiếu | 0.1% | × Giá trị bán (bất kể lãi/lỗ) | Khấu trừ tự động khi bán |
| Cổ tức tiền mặt | 5% | × Số tiền cổ tức nhận | Khấu trừ tại nguồn |
| Cổ tức bằng cổ phiếu | 0.1% | × Giá trị khi bán số CP cổ tức | Khi bán cổ phiếu cổ tức |
| Quyền mua thêm (Rights) | 0.1% | × Giá trị khi bán quyền | Khi thực hiện bán |

**Lưu ý phí môi giới** (tham khảo, thay đổi theo CTCK):
| Công ty CK | Phí mua | Phí bán | Ghi chú |
|------------|---------|---------|---------|
| VPS | 0.15% | 0.15% | Phổ biến nhất |
| SSI | 0.15-0.25% | 0.15-0.25% | Tùy gói |
| VND | 0.15% | 0.15% | |
| TCBS | 0.1% | 0.1% | Tối thiểu phí |
| FPTS | 0.15% | 0.15% | |

**Tổng chi phí 1 round trip** = Phí mua + Phí bán + Thuế 0.1% ≈ **0.4% - 0.7%**

---

## 5. Benchmark tham chiếu Việt Nam

| Benchmark | Mô tả | Phù hợp so sánh với |
|-----------|-------|---------------------|
| VN-Index | Tổng hợp HOSE (~360 cổ phiếu) | Danh mục đa dạng HOSE |
| VN30-Index | Top 30 cổ phiếu lớn nhất HOSE | Danh mục large-cap |
| HNX-Index | Tổng hợp HNX | Danh mục sàn HNX |
| VNMID | Cổ phiếu vốn hóa trung bình | Danh mục mid-cap |
| VNSML | Cổ phiếu vốn hóa nhỏ | Danh mục small-cap |
| Lãi suất tiết kiệm (~5%/năm) | Benchmark đơn giản nhất | Bất kỳ danh mục nào |
| FUEVFVND (ETF VN30) | ETF theo dõi VN30 | Danh mục chủ động |

---

## 6. Tài liệu và công cụ tham khảo

### Sách kinh điển
- **"The Intelligent Asset Allocator"** — William Bernstein: Kinh thánh về Asset Allocation
- **"A Random Walk Down Wall Street"** — Burton Malkiel: Lý thuyết thị trường hiệu quả và đầu tư chỉ số
- **"The Little Book of Common Sense Investing"** — John Bogle: Triết lý đầu tư ETF index fund
- **"All About Asset Allocation"** — Richard Ferri: Hướng dẫn thực hành asset allocation

### Công cụ phân tích
- **Simplize.vn / FireAnt.vn:** Dữ liệu cổ phiếu, screener, phân tích danh mục VN
- **Wifeed.vn:** Bản tin tài chính, dữ liệu doanh nghiệp niêm yết
- **Excel / Google Sheets:** Tự xây dựng portfolio tracker cá nhân
- **Portfolio Visualizer (portfoliovisualizer.com):** Công cụ phân tích backtesting, Sharpe Ratio, Drawdown (cho ETF quốc tế)

### Nguồn dữ liệu
- **HNX.vn / HoSE.vn:** Dữ liệu chính thức từ sàn chứng khoán
- **VietstockFinance.vn:** Dữ liệu lịch sử giá, fundamental data
- **CafeF.vn:** Tin tức thị trường, báo cáo doanh nghiệp

---

## 7. Các lỗi thường gặp trong Portfolio Management

| Lỗi | Mô tả | Cách khắc phục |
|-----|-------|----------------|
| Home Bias | Chỉ đầu tư trong nước, bỏ qua cơ hội quốc tế | Thêm ETF quốc tế (10-20% danh mục) |
| Concentration Risk | Tập trung quá nhiều vào 1-2 cổ phiếu | Không để cổ phiếu nào >20% danh mục |
| False Diversification | Mua nhiều cổ phiếu cùng ngành | Đa dạng theo ngành, không chỉ theo số lượng |
| Over-trading | Giao dịch quá nhiều, tốn phí | Đặt kế hoạch rebalancing định kỳ, không trade hàng ngày |
| Recency Bias | Chỉ mua cổ phiếu vừa tăng mạnh | Phân tích fundamental, không chạy theo trend |
| Neglecting Rebalancing | Không tái cân bằng, để drift | Đặt lịch kiểm tra định kỳ (hàng quý) |
| Ignoring Costs | Bỏ qua phí và thuế | Tính toán net return sau tất cả chi phí |
