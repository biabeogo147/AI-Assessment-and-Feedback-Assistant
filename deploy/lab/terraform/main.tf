# Lab trên một EC2 (plan `lab-deploy-aws`). Người dùng tự chạy `terraform apply`; xem
# docs/operation/deploy-lab.md. State để local -- một người vận hành -- và không bao giờ vào git: nó
# chứa các mật khẩu do `random_password` sinh.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project = "aiafa-lab"
    }
  }
}

data "aws_caller_identity" "me" {}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_instance" "lab" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.lab.name
  subnet_id              = aws_default_subnet.lab.id
  vpc_security_group_ids = [aws_security_group.lab.id]
  # Key pair chỉ có khi đặt `ssh_public_key`; luôn vào được bằng SSM Session Manager.
  key_name = one(aws_key_pair.lab[*].key_name)

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    delete_on_termination = true
  }

  metadata_options {
    http_tokens = "required" # IMDSv2
    # Một bước nhảy: process trên máy chủ gọi được IMDS, container trên docker bridge thì không.
    # Không thì `document`, thứ parse PDF người lạ tải lên, lấy được credential của role.
    http_put_response_hop_limit = 1
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url      = var.repo_url
    git_ref       = var.git_ref
    region        = var.region
    ssm_prefix    = var.ssm_prefix
    backup_bucket = aws_s3_bucket.backup.bucket
  })
  # Đổi user_data (repo, nhánh…) không dựng lại máy: cập nhật code bằng deploy.sh.
  lifecycle {
    ignore_changes = [ami, user_data]
  }

  # Bootstrap đọc SSM ngay lần khởi động đầu, nên mọi tham số phải có trước máy.
  depends_on = [
    aws_ssm_parameter.secret,
    aws_ssm_parameter.site_address,
    aws_ssm_parameter.basic_auth_user,
    aws_iam_role_policy.lab,
    aws_iam_role_policy_attachment.session_manager,
  ]

  tags = {
    Name = "aiafa-lab"
  }
}

resource "aws_key_pair" "lab" {
  count      = var.ssh_public_key == "" ? 0 : 1
  key_name   = "aiafa-lab"
  public_key = var.ssh_public_key
}

resource "aws_eip" "lab" {
  domain = "vpc"
  tags = {
    Name = "aiafa-lab"
  }
}

resource "aws_eip_association" "lab" {
  instance_id   = aws_instance.lab.id
  allocation_id = aws_eip.lab.id
}

locals {
  # Hai tiền tố là một quy ước với FE: `surfaceFor` ở services/fe/src/App.tsx chọn vai theo đúng
  # chúng (tools/tests/test_lab_deploy.py giữ hai bên khớp nhau).
  teacher_host = "teacher.${var.base_domain}"
  student_host = "student.${var.base_domain}"
}
