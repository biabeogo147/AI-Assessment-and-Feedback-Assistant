# Tham số SSM mà Terraform quản. Khoá model (CLAUDE_API_KEY, JEV_API_KEY, OPENAI_API_KEY) **không**
# ở đây: người dùng tự thêm cùng tiền tố, để khoá thật không bao giờ đi qua state của Terraform.

locals {
  # Mật khẩu chỉ gồm chữ và số: chúng nằm trong URL kết nối (DATABASE_URL, MONGO_URL), nơi một ký
  # tự đặc biệt phải mã hoá.
  secrets = {
    POSTGRES_PASSWORD    = 32
    MINIO_SECRET_KEY     = 32
    MONGO_PASSWORD       = 32
    BASIC_AUTH_PASSWORD  = 20
    LAB_ACCOUNT_PASSWORD = 12 # mật khẩu chung của mọi tài khoản seed (D4)
  }
}

resource "random_password" "secret" {
  for_each = local.secrets
  length   = each.value
  special  = false
}

resource "aws_ssm_parameter" "secret" {
  for_each = local.secrets
  name     = "${var.ssm_prefix}/${each.key}"
  type     = "SecureString"
  value    = random_password.secret[each.key].result
}

resource "aws_ssm_parameter" "site_address" {
  name  = "${var.ssm_prefix}/SITE_ADDRESS"
  type  = "String"
  value = local.site_address
}

resource "aws_ssm_parameter" "basic_auth_user" {
  name  = "${var.ssm_prefix}/BASIC_AUTH_USER"
  type  = "String"
  value = "lab"
}
