# Tài liệu thực hành: Chunking Strategies

File này là corpus mẫu để dùng trong bài tập Day 34. Mục tiêu là có một document đủ nhiều cấu trúc để test fixed-size, recursive và markdown-aware chunking trên cùng nguồn dữ liệu.

## Document metadata

```yaml
document_id: acme-refund-policy-v4
title: Chính sách hoàn tiền và giới hạn sử dụng ACME Cloud
source_uri: kb://policies/acme-refund-policy-v4.md
source_type: markdown
document_version: v4
effective_date: 2026-05-01
owner_team: customer-success
tenant_id: acme-public-demo
```

## Document source

````markdown
# Chính sách hoàn tiền và giới hạn sử dụng ACME Cloud

Tài liệu này mô tả điều kiện hoàn tiền, giới hạn request và quy trình xử lý exception cho khách hàng dùng ACME Cloud. Tài liệu áp dụng cho các gói Starter, Pro và Enterprise từ ngày 2026-05-01.

## 1. Phạm vi áp dụng

Chính sách này áp dụng cho khách hàng mua subscription trực tiếp từ ACME Cloud. Chính sách không áp dụng cho khách hàng mua qua marketplace của bên thứ ba, reseller hoặc hợp đồng enterprise có điều khoản riêng.

Nếu hợp đồng enterprise có điều khoản hoàn tiền riêng, điều khoản trong hợp đồng được ưu tiên hơn tài liệu này. Nhân viên support phải kiểm tra contract id trước khi trả lời khách hàng enterprise.

## 2. Cửa sổ hoàn tiền

Khách hàng được yêu cầu hoàn tiền trong vòng 30 ngày kể từ ngày thanh toán đầu tiên của subscription. Sau 30 ngày, ACME Cloud không hoàn tiền cho phí subscription đã phát sinh, trừ khi có lỗi hệ thống nghiêm trọng được xác nhận bởi đội Engineering.

Yêu cầu hoàn tiền chỉ được xử lý nếu tài khoản không vi phạm điều khoản sử dụng, không có dấu hiệu abuse và chưa sử dụng quá 20% quota tháng đầu tiên.

Ví dụ: nếu khách hàng Pro có quota 1,000,000 API calls mỗi tháng, khách hàng phải dùng không quá 200,000 API calls trong tháng đầu tiên để đủ điều kiện hoàn tiền tự động.

## 3. Bảng giới hạn request

| Gói | Request mỗi phút | Burst tối đa | Quota tháng |
|---|---:|---:|---:|
| Starter | 60 | 120 | 100,000 |
| Pro | 600 | 1,200 | 1,000,000 |
| Enterprise | 5,000 | 10,000 | Theo hợp đồng |

Nếu vượt giới hạn request mỗi phút, API trả về HTTP 429 và header `Retry-After`. Client nên dùng exponential backoff với jitter. ACME Cloud có thể giảm rate limit tạm thời nếu phát hiện traffic bất thường.

## 4. Điều kiện không được hoàn tiền

Khách hàng không được hoàn tiền nếu một trong các điều kiện sau xảy ra:

- Tài khoản bị khóa do vi phạm chính sách spam, scraping hoặc credential sharing.
- Khách hàng đã dùng quá 20% quota tháng đầu tiên.
- Yêu cầu hoàn tiền được gửi sau cửa sổ 30 ngày.
- Subscription được mua qua marketplace hoặc reseller.
- Invoice đã được điều chỉnh bằng credit note trước đó.

Support agent không được hứa hoàn tiền nếu chưa kiểm tra đầy đủ các điều kiện trên.

## 5. Exception do lỗi hệ thống

Nếu ACME Cloud gặp lỗi hệ thống nghiêm trọng làm khách hàng không thể dùng dịch vụ trên 4 giờ liên tục, Customer Success có thể tạo exception để hoàn tiền một phần hoặc cấp service credit.

Exception phải có incident id, thời gian ảnh hưởng, danh sách region bị ảnh hưởng và xác nhận từ Engineering Manager trực ca. Nếu thiếu incident id, yêu cầu phải được chuyển sang manual review.

## 6. Quy trình xử lý support ticket

Support agent cần thực hiện các bước sau:

1. Xác định `account_id`, `subscription_id`, `invoice_id` và ngày thanh toán đầu tiên.
2. Kiểm tra contract id nếu khách hàng thuộc gói Enterprise.
3. Kiểm tra usage trong tháng đầu tiên.
4. Kiểm tra trạng thái abuse hoặc policy violation.
5. Đối chiếu cửa sổ 30 ngày.
6. Nếu đủ điều kiện, tạo refund request trong billing system.
7. Nếu không đủ điều kiện, trả lời khách hàng bằng lý do cụ thể và trích dẫn chính sách.

## 7. Mẫu phản hồi cho khách hàng

Nếu khách hàng đủ điều kiện:

> Chúng tôi đã kiểm tra tài khoản của bạn và xác nhận yêu cầu hoàn tiền nằm trong cửa sổ 30 ngày, đồng thời usage chưa vượt quá 20% quota tháng đầu tiên. Yêu cầu hoàn tiền đã được tạo và thường được xử lý trong 5-10 ngày làm việc.

Nếu khách hàng không đủ điều kiện:

> Chúng tôi chưa thể xử lý hoàn tiền vì yêu cầu không đáp ứng điều kiện của chính sách hiện tại. Lý do cụ thể là: {reason}. Nếu bạn cho rằng đây là lỗi hệ thống, vui lòng cung cấp thêm thông tin để chúng tôi chuyển sang manual review.

## 8. Code ví dụ cho client retry

```python
import random
import time


def call_with_backoff(client, request, max_retries=5):
    for attempt in range(max_retries):
        response = client.send(request)
        if response.status_code != 429:
            return response

        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            sleep_seconds = float(retry_after)
        else:
            sleep_seconds = min(30, 2 ** attempt) + random.uniform(0, 0.5)

        time.sleep(sleep_seconds)

    raise TimeoutError("API vẫn trả về HTTP 429 sau khi retry")
```

Code trên chỉ minh họa client behavior. Production client nên có timeout, circuit breaker, request id, structured log và metric cho số lần retry.
````

## Ground-truth queries

Dùng các query này để so sánh retrieval result giữa các chiến lược.

| ID | Query | Expected evidence | Expected citation |
|---|---|---|---|
| Q1 | Gói Pro được gọi bao nhiêu request mỗi phút? | `Pro`, `600`, bảng giới hạn request | Section `3. Bảng giới hạn request` |
| Q2 | Khách hàng sau 30 ngày có được hoàn tiền không? | `Sau 30 ngày`, `không hoàn tiền`, exception lỗi hệ thống | Section `2. Cửa sổ hoàn tiền` |
| Q3 | Khi nào support phải chuyển manual review? | `thiếu incident id`, `manual review` | Section `5. Exception do lỗi hệ thống` |
| Q4 | Điều kiện usage để được hoàn tiền tự động là gì? | `không quá 20% quota tháng đầu tiên` | Section `2. Cửa sổ hoàn tiền` |
| Q5 | Client nên xử lý HTTP 429 như thế nào? | `Retry-After`, `exponential backoff`, `jitter` | Section `3` hoặc `8` |
| Q6 | Khách hàng mua qua reseller có được áp dụng chính sách này không? | `không áp dụng`, `reseller` | Section `1. Phạm vi áp dụng` |

## Expected observations

- Fixed-size có thể lấy đúng Q1 nếu table không bị cắt, nhưng dễ tách header khỏi row.
- Recursive thường tốt ở Q2, Q3, Q4 vì paragraph giữ đủ ý.
- Markdown-aware thường tốt hơn ở citation vì giữ heading path.
- Nếu overlap quá cao, Q5 có thể trả cả section rate limit và code retry, cần reranker hoặc context dedupe.
- Nếu chunk quá lớn, Q1 có thể bị noise vì section bảng và đoạn HTTP 429/code retry trộn với nhau.
