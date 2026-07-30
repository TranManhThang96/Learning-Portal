# Thực hành — Ngày 5: Terraform và Floci

## Chuẩn bị

1. Cài Terraform, verify bằng:

   ```bash
   terraform version
   ```

2. Cài và chạy Floci:

   ```bash
   curl -fsSL https://floci.io/install.sh | sh
   floci start
   floci doctor
   eval $(floci env)
   ```

3. Cài AWS CLI để test kết quả sau khi apply (dùng để verify, không phải để tạo hạ tầng thật):

   ```bash
   aws --version
   ```

Checklist chuẩn bị:

- [ ] `terraform version` chạy được, in ra version >= 1.9
- [ ] `floci start` chạy không lỗi
- [ ] `floci doctor` báo setup OK
- [ ] `eval $(floci env)` chạy xong không lỗi
- [ ] `aws --version` chạy được

---

## Bài 1 (Beginner): Tạo S3 bucket đầu tiên trên Floci

**Mục tiêu**: hiểu vòng đời init → plan → apply → destroy với 1 resource đơn giản nhất.

**Yêu cầu**: đã hoàn tất phần Chuẩn bị.

**Các bước**:

1. Tạo thư mục làm việc và file `main.tf`:

   ```bash
   mkdir -p ~/terraform-floci-demo/bai-1
   cd ~/terraform-floci-demo/bai-1
   ```

2. Tạo file `main.tf` với nội dung:

   ```txt
   terraform {
     required_providers {
       aws = {
         source  = "hashicorp/aws"
         version = "~> 5.0"
       }
     }
   }

   provider "aws" {
     region                      = "us-east-1"
     access_key                  = "test"
     secret_key                  = "test"
     skip_credentials_validation = true
     skip_metadata_api_check     = true
     skip_requesting_account_id  = true

     endpoints {
       s3 = "http://localhost:4566"
     }
   }

   resource "aws_s3_bucket" "demo" {
     bucket = "bai1-demo-bucket"
   }
   ```

3. Chạy vòng đời Terraform:

   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

   Khi được hỏi xác nhận, gõ `yes`.

4. Verify bucket đã được tạo trên Floci (không phải AWS thật):

   ```bash
   aws --endpoint-url=http://localhost:4566 s3 ls
   ```

   Kết quả mong đợi: thấy `bai1-demo-bucket` trong danh sách.

5. Dọn dẹp:

   ```bash
   terraform destroy
   ```

**Kết quả mong đợi**: bucket xuất hiện sau `apply`, biến mất sau `destroy`.

**Kiến thức luyện tập**: vòng đời init/plan/apply/destroy, cấu hình provider trỏ Floci, đọc output của `terraform plan`.

---

## Bài 2 (Practical): Thêm variable, output và resource thứ 2

**Mục tiêu**: hiểu variable/output, thấy `terraform plan` báo diff khi đổi cấu hình, xem state list.

**Yêu cầu**: đã hoàn thành Bài 1.

**Các bước**:

1. Tạo thư mục mới:

   ```bash
   mkdir -p ~/terraform-floci-demo/bai-2
   cd ~/terraform-floci-demo/bai-2
   ```

2. Tạo file `variables.tf`:

   ```txt
   variable "bucket_name" {
     type    = string
     default = "bai2-demo-bucket"
   }

   variable "table_name" {
     type    = string
     default = "bai2-demo-table"
   }
   ```

3. Tạo file `main.tf`:

   ```txt
   terraform {
     required_providers {
       aws = {
         source  = "hashicorp/aws"
         version = "~> 5.0"
       }
     }
   }

   provider "aws" {
     region                      = "us-east-1"
     access_key                  = "test"
     secret_key                  = "test"
     skip_credentials_validation = true
     skip_metadata_api_check     = true
     skip_requesting_account_id  = true

     endpoints {
       s3       = "http://localhost:4566"
       dynamodb = "http://localhost:4566"
     }
   }

   resource "aws_s3_bucket" "demo" {
     bucket = var.bucket_name
   }

   resource "aws_dynamodb_table" "demo" {
     name         = var.table_name
     billing_mode = "PAY_PER_REQUEST"
     hash_key     = "id"

     attribute {
       name = "id"
       type = "S"
     }
   }
   ```

4. Tạo file `outputs.tf`:

   ```txt
   output "bucket_arn" {
     value = aws_s3_bucket.demo.arn
   }

   output "table_name" {
     value = aws_dynamodb_table.demo.name
   }
   ```

5. Chạy:

   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

6. Xem output:

   ```bash
   terraform output
   ```

7. Xem danh sách resource trong state:

   ```bash
   terraform state list
   ```

   Kết quả mong đợi: thấy `aws_s3_bucket.demo` và `aws_dynamodb_table.demo`.

8. Đổi `bucket_name` trong `variables.tf` thành `"bai2-demo-bucket-v2"`, sau đó chạy lại:

   ```bash
   terraform plan
   ```

   Kết quả mong đợi: Terraform báo sẽ **destroy** bucket cũ và **create** bucket mới (vì đổi tên bucket = tạo resource mới, không phải update tại chỗ).

9. Áp dụng thay đổi rồi dọn dẹp:

   ```bash
   terraform apply
   terraform destroy
   ```

**Kiến thức luyện tập**: variable, output, nhiều resource trong 1 file, đọc diff của `plan` khi đổi cấu hình, `terraform state list`.

---

## Bài 3 (Advanced/Differentiating): Đóng gói module tái dùng

**Mục tiêu**: hiểu module — đóng gói 1 nhóm resource để gọi lại nhiều lần với tham số khác nhau; thảo luận remote state.

**Yêu cầu**: đã hoàn thành Bài 2.

**Các bước**:

1. Tạo cấu trúc thư mục:

   ```bash
   mkdir -p ~/terraform-floci-demo/bai-3/modules/s3-bucket
   cd ~/terraform-floci-demo/bai-3
   ```

2. Tạo module tại `modules/s3-bucket/main.tf`:

   ```txt
   variable "bucket_name" {
     type = string
   }

   resource "aws_s3_bucket" "this" {
     bucket = var.bucket_name
   }

   output "arn" {
     value = aws_s3_bucket.this.arn
   }
   ```

3. Tạo file `main.tf` ở thư mục gốc, gọi module 2 lần với tên khác nhau:

   ```txt
   terraform {
     required_providers {
       aws = {
         source  = "hashicorp/aws"
         version = "~> 5.0"
       }
     }
   }

   provider "aws" {
     region                      = "us-east-1"
     access_key                  = "test"
     secret_key                  = "test"
     skip_credentials_validation = true
     skip_metadata_api_check     = true
     skip_requesting_account_id  = true

     endpoints {
       s3 = "http://localhost:4566"
     }
   }

   module "bucket_logs" {
     source      = "./modules/s3-bucket"
     bucket_name = "bai3-logs-bucket"
   }

   module "bucket_backup" {
     source      = "./modules/s3-bucket"
     bucket_name = "bai3-backup-bucket"
   }
   ```

4. Chạy:

   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

5. Verify:

   ```bash
   aws --endpoint-url=http://localhost:4566 s3 ls
   ```

   Kết quả mong đợi: thấy cả `bai3-logs-bucket` và `bai3-backup-bucket`, được tạo từ cùng 1 module.

6. Dọn dẹp:

   ```bash
   terraform destroy
   ```

**Giới hạn cần biết**: Floci giả lập được S3, DynamoDB, RDS (dùng engine PostgreSQL/MySQL thật bên dưới) và nhiều dịch vụ khác trong số ~68 dịch vụ được hỗ trợ. Với các dịch vụ phức tạp như EKS, mức độ giả lập có thể không đầy đủ như S3/DynamoDB — nếu cần thực hành resource phức tạp hơn, ưu tiên dùng RDS hoặc kết hợp nhiều resource đơn giản (S3 + DynamoDB + SQS) thay vì giả định EKS hoạt động đầy đủ trên Floci.

**Thảo luận remote state**: trong bài thực hành này, state được lưu local (`terraform.tfstate` trong thư mục hiện tại). Khi làm nhóm thật, state nên chuyển sang remote backend (vd S3 bucket + DynamoDB table để lock) để nhiều người cùng `apply` mà không đè state của nhau. Cấu hình remote backend không nằm trong phạm vi bài thực hành này, nhưng cần biết khái niệm để áp dụng khi làm project thật.

**Kiến thức luyện tập**: viết module, gọi module nhiều lần với tham số khác nhau, giới hạn của môi trường giả lập, khái niệm remote state.

---

## Checklist tổng kết ngày 5

- [ ] Chạy được vòng đời init/plan/apply/destroy với Floci
- [ ] Hiểu vai trò của variable, output, resource, provider
- [ ] Đọc được diff của `terraform plan` khi đổi cấu hình
- [ ] Dùng được `terraform state list` để xem resource đang quản lý
- [ ] Viết được 1 module đơn giản và gọi lại nhiều lần
- [ ] Giải thích được vì sao remote state cần thiết khi làm nhóm
- [ ] Giải thích được vì sao Floci an toàn hơn AWS thật để thực hành
