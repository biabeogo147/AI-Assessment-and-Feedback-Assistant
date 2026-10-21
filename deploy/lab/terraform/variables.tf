variable "region" {
  description = "Region AWS. Singapore là region gần Việt Nam nhất."
  type        = string
  default     = "ap-southeast-1"
}

variable "instance_type" {
  description = "Loại máy. OCR (torch + paddle) cần RAM: 8 GB là thoải mái. Free plan không cho loại này thì thử c7i-flex.large (4 GB, bootstrap bật thêm swap)."
  type        = string
  default     = "m7i-flex.large"
}

variable "root_volume_gb" {
  description = "Dung lượng ổ gốc. Image document (torch, paddle, model OCR) chiếm vài GB."
  type        = number
  default     = 30
}

variable "repo_url" {
  description = "Repo **public** mà máy clone lúc khởi động."
  type        = string
  default     = "https://github.com/biabeogo147/AI-Assessment-and-Feedback-Assistant.git"
}

variable "git_ref" {
  description = "Nhánh máy clone lần đầu. Bản sau đưa lên bằng deploy.sh."
  type        = string
  default     = "main"
}

variable "ssm_prefix" {
  description = "Tiền tố mọi tham số SSM của lab."
  type        = string
  default     = "/aiafa/lab"
}

variable "alert_email" {
  description = "Email nhận cảnh báo chi phí của AWS Budgets. Để trống thì không tạo budget."
  type        = string
  default     = ""
}

variable "budget_usd" {
  description = "Mức chi một tháng (USD) mà AWS Budgets cảnh báo ở 50% và 100%."
  type        = number
  default     = 30
}

variable "ssh_cidrs" {
  description = "Dải IPv4 được SSH vào máy (cổng 22), dạng `1.2.3.4/32`. Để trống thì không mở cổng 22, chỉ vào bằng SSM. Repo public: đặt trong terraform.tfvars (gitignore), không ghi IP vào đây."
  type        = list(string)
  default     = []
}

variable "ssh_public_key" {
  description = "Khoá công khai (nội dung tệp .pub) cho user `ubuntu`. Để trống thì không tạo key pair."
  type        = string
  default     = ""
}
