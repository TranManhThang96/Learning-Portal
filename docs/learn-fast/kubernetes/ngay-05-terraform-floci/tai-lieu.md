# Tài liệu tham khảo — Ngày 5: Terraform và Floci

## Cheatsheet lệnh Terraform

```bash
# Khởi tạo thư mục làm việc: tải provider, module khai báo trong .tf
terraform init

# Kiểm tra cú pháp HCL có hợp lệ không (không gọi API cloud)
terraform validate

# Format lại file .tf theo chuẩn HCL (thụt lề, khoảng trắng)
terraform fmt

# Xem trước thay đổi sẽ áp dụng, KHÔNG thay đổi gì thật
terraform plan

# Áp dụng thay đổi thật (tạo/sửa/xoá resource)
terraform apply

# Xoá toàn bộ resource đang được Terraform quản lý
terraform destroy

# Liệt kê các resource đang có trong state file
terraform state list

# Xem giá trị output đã khai báo (vd bucket_arn)
terraform output

# Truyền giá trị biến từ command line, không cần sửa file .tf
terraform plan -var="bucket_name=my-bucket-2"

# Chỉ apply/plan cho 1 resource cụ thể (dùng khi debug, hạn chế phạm vi)
terraform apply -target=aws_s3_bucket.demo
```

## Cheatsheet lệnh Floci

```bash
# Khởi động emulator AWS local (mặc định port 4566)
floci start

# Kiểm tra setup, phát hiện vấn đề cấu hình (giống "doctor" các CLI khác)
floci doctor

# Export biến môi trường để AWS CLI / Terraform tự trỏ về endpoint local
eval $(floci env)
```

## Snippet HCL: cấu hình AWS provider trỏ về Floci

Floci là drop-in replacement của LocalStack, nên pattern cấu hình provider giống LocalStack (kiểm chứng tại floci.io nếu cần chi tiết mới nhất):

```txt
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"   # Floci không cần credentials thật
  secret_key                  = "test"
  skip_credentials_validation = true      # Bỏ qua kiểm tra credentials với AWS thật
  skip_metadata_api_check     = true      # Bỏ qua gọi EC2 metadata API
  skip_requesting_account_id  = true      # Bỏ qua gọi API lấy account ID thật

  endpoints {
    s3       = "http://localhost:4566"    # Trỏ S3 về Floci
    dynamodb = "http://localhost:4566"    # Trỏ DynamoDB về Floci
    sqs      = "http://localhost:4566"    # Trỏ SQS về Floci
    rds      = "http://localhost:4566"    # Trỏ RDS về Floci
  }
}
```

## Tài liệu tham khảo chính thức

| Link | Đọc gì trước | Dùng để làm gì |
|---|---|---|
| [developer.hashicorp.com/terraform/tutorials](https://developer.hashicorp.com/terraform/tutorials) | Mục "AWS Get Started" | Thực hành theo bước, làm quen vòng đời init/plan/apply |
| [developer.hashicorp.com/terraform/language](https://developer.hashicorp.com/terraform/language) | Phần "Resources" và "Variables" | Tra cứu cú pháp HCL chính xác (provider, resource, variable, output, module) |
| [developer.hashicorp.com/terraform/cli](https://developer.hashicorp.com/terraform/cli) | Phần "Commands" | Tra cứu chi tiết từng lệnh CLI (init, plan, apply, state...) |
| [registry.terraform.io/providers/hashicorp/aws](https://registry.terraform.io/providers/hashicorp/aws/latest/docs) | Phần "Guides" rồi tra theo tên resource (vd `aws_s3_bucket`) | Tra cứu chính xác attribute của từng resource AWS khi viết .tf |
| [floci.io](https://floci.io) | Trang chủ, mục cài đặt (install) | Cài Floci, xem danh sách dịch vụ AWS được giả lập, xem hướng dẫn dùng với Terraform |

Ghi chú: chi tiết cấu hình provider AWS trỏ về Floci ở trên dựa theo pattern chuẩn của LocalStack — nếu Floci có tài liệu cấu hình riêng khác, nên đối chiếu lại tại floci.io (cần kiểm chứng).
