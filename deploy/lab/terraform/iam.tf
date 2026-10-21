# Quyền của máy lab: vào bằng SSM Session Manager, đọc tham số, ghi và đọc lại backup.
#
# `AmazonSSMManagedInstanceCore` tự nó đã cho `ssm:GetParameter(s)` trên mọi tham số của account,
# nên giới hạn theo tiền tố dưới đây chỉ thật sự có tác dụng với `GetParametersByPath`. Account
# này chỉ dùng cho lab nên chấp nhận được; dùng chung với việc khác thì phải thay policy ấy.

resource "aws_iam_role" "lab" {
  name = "aiafa-lab"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "session_manager" {
  role       = aws_iam_role.lab.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

locals {
  parameter_arn = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.me.account_id}:parameter${var.ssm_prefix}"
}

resource "aws_iam_role_policy" "lab" {
  name = "aiafa-lab"
  role = aws_iam_role.lab.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadOwnParameters"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParametersByPath"]
        Resource = [local.parameter_arn, "${local.parameter_arn}/*"]
      },
      {
        # SecureString mã hoá bằng khoá mặc định aws/ssm; chỉ giải mã qua SSM.
        Sid      = "DecryptParameters"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = "ssm.${var.region}.amazonaws.com" }
        }
      },
      {
        Sid      = "WriteAndRestoreBackups"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = "${aws_s3_bucket.backup.arn}/*"
      },
      {
        Sid      = "ListBackups"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.backup.arn
      },
    ]
  })
}

resource "aws_iam_instance_profile" "lab" {
  name = "aiafa-lab"
  role = aws_iam_role.lab.name
}
