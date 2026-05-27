# Ngày 26: Candlestick Chart — Biểu Đồ Nến Nhật Cơ Bản

## Mục tiêu học tập
- [ ] Hiểu cấu tạo của một cây nến Nhật (Open, High, Low, Close)
- [ ] Phân biệt nến tăng và nến giảm
- [ ] Nhận diện và hiểu ý nghĩa 6 mô hình nến đơn quan trọng nhất
- [ ] Biết cách áp dụng phân tích nến trong thực tế giao dịch

---

## Nội dung bài giảng

### 1. Tại sao dùng Candlestick Chart?

Trước khi có biểu đồ nến, người ta dùng **Line Chart** (biểu đồ đường) — chỉ nối các điểm giá đóng cửa lại với nhau. Nhìn đơn giản nhưng mất rất nhiều thông tin.

Biểu đồ nến Nhật (Japanese Candlestick Chart) được phát minh bởi Munehisa Homma, một thương nhân gạo người Nhật vào thế kỷ 18. Ông dùng nó để theo dõi giá gạo ở thị trường Dojima, Osaka. Mãi đến những năm 1990, Steve Nison mới giới thiệu phương pháp này cho thế giới phương Tây qua cuốn sách "Japanese Candlestick Charting Techniques."

**Tại sao nến Nhật vượt trội hơn biểu đồ đường?**

Một cây nến chứa đựng **4 thông tin** trong một khoảng thời gian:
- **Open (O)** — Giá mở cửa
- **High (H)** — Giá cao nhất
- **Low (L)** — Giá thấp nhất
- **Close (C)** — Giá đóng cửa

Bốn con số này kể một câu chuyện hoàn chỉnh về cuộc chiến giữa bên mua (bulls — bò) và bên bán (bears — gấu) trong một phiên giao dịch.

---

### 2. Cấu tạo một cây nến Nhật

```
          │  ← Bóng trên (Upper Shadow / Upper Wick)
          │
       ┌──┴──┐
       │     │  ← Thân nến (Body)
       │     │
       └──┬──┘
          │  ← Bóng dưới (Lower Shadow / Lower Wick)
          │
```

**Các thành phần:**

| Thành phần | Tiếng Anh | Ý nghĩa |
|-----------|-----------|---------|
| Thân nến | Body | Khoảng từ giá mở đến giá đóng |
| Bóng trên | Upper Shadow / Wick | Từ đỉnh thân đến giá cao nhất |
| Bóng dưới | Lower Shadow / Wick | Từ đáy thân đến giá thấp nhất |

**Nến tăng (Bullish Candle):**
- Giá đóng cửa **cao hơn** giá mở cửa
- Màu xanh lá (hoặc trắng trong hệ thống cũ)
- Thân = Close - Open

**Nến giảm (Bearish Candle):**
- Giá đóng cửa **thấp hơn** giá mở cửa
- Màu đỏ (hoặc đen trong hệ thống cũ)
- Thân = Open - Close

```
Nến tăng (Bullish):        Nến giảm (Bearish):
     High                       High
      │                          │
   ┌──┴──┐  ← Close           ┌──┴──┐  ← Open
   │     │                    │     │
   │ 🟢  │                    │ 🔴  │
   │     │                    │     │
   └──┬──┘  ← Open            └──┬──┘  ← Close
      │                          │
     Low                        Low
```

**Ví dụ thực tế:**
Cổ phiếu FPT ngày 15/3/2024:
- Open: 95,000 VND
- High: 98,500 VND
- Low: 93,000 VND
- Close: 97,200 VND

→ Nến tăng màu xanh, thân nến = 2,200 VND, bóng trên = 1,300 VND, bóng dưới = 2,000 VND.

Câu chuyện: Buổi sáng mở cửa tại 95k, giá giảm xuống 93k (bears kiểm soát), nhưng sau đó bulls phản công mạnh, đẩy giá lên 98.5k, cuối phiên đóng cửa tại 97.2k. **Bulls thắng phiên đó.**

---

### 3. Thân nến nói lên điều gì?

**Thân nến to** → Sự kiểm soát rõ ràng của một bên:
- Thân xanh to = Bulls kiểm soát hoàn toàn, áp lực mua mạnh
- Thân đỏ to = Bears kiểm soát hoàn toàn, áp lực bán mạnh

**Thân nến nhỏ** → Thị trường do dự, cân bằng giữa hai bên

**Bóng nến nói lên điều gì?**
- Bóng trên dài = Giá đã lên cao nhưng bị đẩy xuống → Bears phản ứng ở vùng giá cao
- Bóng dưới dài = Giá đã xuống thấp nhưng bị kéo lên → Bulls bảo vệ ở vùng giá thấp

---

### 4. Các mô hình nến đơn quan trọng

#### 4.1. Doji

**Doji** là nến có giá mở và đóng gần bằng nhau → thân nến gần như không có.

```
     High
      │
      │  ← Bóng trên dài
      │
  ────┼────  ← Open ≈ Close (thân rất nhỏ hoặc không có)
      │
      │  ← Bóng dưới dài
      │
     Low
```

**Ý nghĩa:** Thị trường đang do dự. Bulls và Bears kéo giá lên xuống suốt phiên nhưng kết thúc ở mức ngang với mở đầu. **Không ai thắng.**

**Cách dùng:** Doji sau một xu hướng dài là tín hiệu cảnh báo xu hướng có thể đảo chiều. Nhưng phải **xác nhận bằng nến tiếp theo** — nếu nến sau là nến đỏ (khi đang uptrend), khả năng đảo chiều tăng cao.

**Các loại Doji:**

| Loại | Hình dạng | Ý nghĩa |
|------|-----------|---------|
| Standard Doji | Bóng trên = bóng dưới | Do dự |
| Long-legged Doji | Hai bóng rất dài | Biến động mạnh, không ai kiểm soát |
| Dragonfly Doji | Không có bóng trên, bóng dưới dài | Bulls bảo vệ mạnh → bullish reversal |
| Gravestone Doji | Bóng trên dài, không có bóng dưới | Bears kiểm soát → bearish reversal |

---

#### 4.2. Hammer (Nến Búa)

```
  ┌───┐  ← Thân nhỏ (ở đỉnh)
  └─┬─┘
    │
    │  ← Bóng dưới dài (≥ 2x thân)
    │
```

**Điều kiện:** Xuất hiện ở **cuối downtrend** (xu hướng giảm).
- Thân nhỏ ở phần trên của nến
- Bóng dưới dài (ít nhất gấp 2 lần thân nến)
- Bóng trên rất nhỏ hoặc không có

**Câu chuyện:** Giá mở cửa, giảm mạnh (bóng dưới dài), nhưng bulls đã vào mua ồ ạt và đẩy giá lên lại gần vùng mở cửa. **Tín hiệu bullish (đảo chiều tăng).**

**Màu sắc:** Hammer xanh mạnh hơn Hammer đỏ, nhưng cả hai đều có giá trị.

**Ví dụ:** VN-Index ngày 16/3/2020 (giữa COVID crash) xuất hiện Hammer tại vùng 650 điểm → đây là đáy cục bộ, sau đó index phục hồi mạnh.

---

#### 4.3. Inverted Hammer (Nến Búa Ngược)

```
    │
    │  ← Bóng trên dài (≥ 2x thân)
    │
  ┌─┴─┐  ← Thân nhỏ (ở đáy)
  └───┘
```

**Điều kiện:** Xuất hiện ở **cuối downtrend**.
- Thân nhỏ ở phần dưới
- Bóng trên dài
- Ít bóng dưới

**Câu chuyện:** Bulls cố đẩy giá lên nhưng bears đẩy xuống. Dù vậy, nỗ lực của bulls cho thấy có tiềm năng đảo chiều. **Cần xác nhận bằng nến xanh tiếp theo.**

---

#### 4.4. Shooting Star (Sao Băng)

```
    │
    │  ← Bóng trên dài (≥ 2x thân)
    │
  ┌─┴─┐  ← Thân nhỏ (ở đáy)
  └───┘
```

**Trông giống Inverted Hammer nhưng xuất hiện ở cuối UPTREND** — đây là điểm khác biệt cốt lõi.

**Điều kiện:** Xuất hiện ở **đỉnh uptrend**.
**Câu chuyện:** Bulls đẩy giá lên rất cao (bóng trên dài), nhưng bears vào mạnh và kéo giá xuống gần mức mở cửa. **Bears đang chiếm quyền kiểm soát → Tín hiệu bearish (đảo chiều giảm).**

**So sánh:**

| Nến | Vị trí | Tín hiệu |
|-----|--------|----------|
| Hammer | Cuối downtrend | Bullish reversal |
| Inverted Hammer | Cuối downtrend | Bullish reversal (yếu hơn) |
| Shooting Star | Cuối uptrend | Bearish reversal |
| Hanging Man | Cuối uptrend | Bearish reversal |

---

#### 4.5. Marubozu

**Marubozu** là nến có thân dài và **không có bóng** (hoặc bóng rất nhỏ).

```
Bullish Marubozu:     Bearish Marubozu:
┌─────────┐          ┌─────────┐
│         │          │         │
│   🟢    │          │   🔴    │
│         │          │         │
└─────────┘          └─────────┘
Open = Low            Open = High
Close = High          Close = Low
```

**Bullish Marubozu:**
- Mở cửa = Giá thấp nhất, đóng cửa = Giá cao nhất
- Bulls kiểm soát hoàn toàn từ đầu đến cuối phiên
- Tín hiệu tăng rất mạnh

**Bearish Marubozu:**
- Mở cửa = Giá cao nhất, đóng cửa = Giá thấp nhất
- Bears kiểm soát hoàn toàn
- Tín hiệu giảm rất mạnh

**Ứng dụng thực tế:** Khi cổ phiếu bứt phá khỏi vùng kháng cự với nến Marubozu xanh + khối lượng lớn → tín hiệu bullish đáng chú ý, cần kiểm tra thêm xu hướng, volume và rủi ro.

---

#### 4.6. Spinning Top (Con Quay)

```
      │  ← Bóng trên
   ┌──┴──┐
   │     │  ← Thân nhỏ
   └──┬──┘
      │  ← Bóng dưới (tương đương bóng trên)
```

**Đặc điểm:** Thân nhỏ, hai bóng tương đối đều nhau.
**Ý nghĩa:** Thị trường thiếu quyết đoán. Bulls và Bears đều thử sức nhưng không ai giành được lợi thế rõ rệt.

**Khác với Doji:** Spinning Top có thân nhỏ nhưng vẫn có, còn Doji thân gần như bằng 0.

**Cách dùng:** Spinning Top sau một xu hướng dài → cảnh báo xu hướng có thể yếu đi hoặc đảo chiều. Nhưng **không phải tín hiệu giao dịch độc lập** — cần kết hợp với context.

---

### 5. Quy tắc vàng khi đọc nến

**1. Context là vua:** Cùng một cây nến nhưng ý nghĩa khác nhau tùy vị trí:
- Hammer ở cuối downtrend = tín hiệu bullish tiềm năng, chưa phải lý do vào lệnh độc lập
- Hammer giữa sideway = không có ý nghĩa đặc biệt

**2. Luôn xác nhận:** Không vào lệnh chỉ dựa trên một cây nến. Đợi nến tiếp theo xác nhận.

**3. Volume quan trọng:** Mô hình nến đảo chiều + volume lớn = tín hiệu tin cậy hơn.

**4. Timeframe ảnh hưởng độ tin cậy:**
- Nến tuần > Nến ngày > Nến 4 giờ > Nến 1 giờ

**5. Kết hợp với Support/Resistance:** Hammer tại vùng hỗ trợ mạnh = tín hiệu rất đáng chú ý.

---

### 6. Ứng dụng thực tế — Cách nhìn biểu đồ nến

Khi mở biểu đồ, hãy hỏi mình 3 câu hỏi:

1. **Xu hướng hiện tại là gì?** (Tăng / Giảm / Đi ngang)
2. **Giá đang ở đâu trong xu hướng đó?** (Đầu / Giữa / Cuối?)
3. **Nến hiện tại nói gì?** (Ai đang kiểm soát — Bulls hay Bears?)

**Ví dụ phân tích thực tế:**
```
Biểu đồ VNM (Vinamilk) - Tháng 11/2023:
- Xu hướng: Downtrend kéo dài 3 tháng
- Giá về vùng hỗ trợ 55,000 VND
- Xuất hiện nến Hammer xanh với bóng dưới dài + volume tăng vọt
→ Đây là tín hiệu đáng chú ý. Nếu nến hôm sau tiếp tục xanh, 
  khả năng cao đã tạo đáy tạm thời.
```

---

## Tóm tắt kiến thức chính (Key Takeaways)

1. **Một cây nến = 4 thông tin (OHLC)** kể câu chuyện về cuộc chiến Bulls vs Bears.
2. **Thân nến** = mức độ kiểm soát; **Bóng nến** = vùng giá bị từ chối.
3. **6 mô hình nến đơn cần nhớ:** Doji, Hammer, Inverted Hammer, Shooting Star, Marubozu, Spinning Top.
4. **Context quyết định ý nghĩa** — cùng một nến, vị trí khác nhau thì tín hiệu khác nhau.
5. **Luôn xác nhận** bằng nến tiếp theo và kết hợp với volume.

---

## Thuật ngữ quan trọng

| Thuật ngữ (English) | Nghĩa tiếng Việt | Giải thích ngắn |
|--------------------|-------------------|-----------------|
| Candlestick Chart | Biểu đồ nến Nhật | Biểu đồ dùng "nến" để hiển thị OHLC |
| Open (O) | Giá mở cửa | Giá đầu tiên của phiên giao dịch |
| High (H) | Giá cao nhất | Mức giá cao nhất trong phiên |
| Low (L) | Giá thấp nhất | Mức giá thấp nhất trong phiên |
| Close (C) | Giá đóng cửa | Giá cuối cùng của phiên giao dịch |
| Body | Thân nến | Khoảng từ Open đến Close |
| Shadow / Wick | Bóng nến | Phần vượt ra ngoài thân nến |
| Bullish Candle | Nến tăng | Close > Open, màu xanh |
| Bearish Candle | Nến giảm | Close < Open, màu đỏ |
| Doji | Nến Doji | Open ≈ Close, thị trường do dự |
| Hammer | Nến búa | Bóng dưới dài, xuất hiện ở đáy |
| Shooting Star | Sao băng | Bóng trên dài, xuất hiện ở đỉnh |
| Marubozu | Nến không bóng | Thân dài, không có bóng — kiểm soát hoàn toàn |
| Spinning Top | Con quay | Thân nhỏ, hai bóng đều — thị trường do dự |
| Bullish Reversal | Đảo chiều tăng | Tín hiệu giá sẽ chuyển từ giảm sang tăng |
| Bearish Reversal | Đảo chiều giảm | Tín hiệu giá sẽ chuyển từ tăng sang giảm |

---

## Bài học tiếp theo

**Ngày 27** sẽ đưa bạn vào thế giới của **mô hình nến kép và ba nến** — những pattern mạnh hơn vì kết hợp nhiều cây nến kể một câu chuyện đảo chiều hoàn chỉnh hơn. Bạn sẽ học Engulfing, Harami, Morning Star, Evening Star và nhiều mô hình nữa.
