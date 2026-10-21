# VPC mặc định, subnet public của nó: không NAT Gateway (tính tiền theo giờ), không VPC riêng.

# Một AZ có bán loại máy đã chọn: không phải AZ nào cũng có `m7i-flex`.
data "aws_ec2_instance_type_offerings" "lab" {
  location_type = "availability-zone"
  filter {
    name   = "instance-type"
    values = [var.instance_type]
  }
}

# Account mới có thể có VPC mặc định mà không có subnet nào (RunInstances báo "No subnets found for
# the default VPC"). Resource này nhận subnet mặc định của AZ nếu đã có, không có thì tạo; route
# table chính của VPC mặc định đã ra Internet Gateway. `force_destroy`: `destroy` xoá luôn subnet.
resource "aws_default_subnet" "lab" {
  availability_zone = sort(data.aws_ec2_instance_type_offerings.lab.locations)[0]
  force_destroy     = true
}

resource "aws_security_group" "lab" {
  name        = "aiafa-lab"
  description = "HTTP va HTTPS cua Caddy; SSH chi tu cac dai trong var.ssh_cidrs."

  ingress {
    description      = "HTTP: Caddy chuyen sang HTTPS va Lets Encrypt kiem tra qua cong nay"
    from_port        = 80
    to_port          = 80
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  ingress {
    description      = "HTTPS"
    from_port        = 443
    to_port          = 443
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  # SSH chỉ mở cho các dải trong `ssh_cidrs` (mạng của team); trống thì không có luật này.
  dynamic "ingress" {
    for_each = length(var.ssh_cidrs) > 0 ? [1] : []
    content {
      description = "SSH tu mang cua team"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.ssh_cidrs
    }
  }

  egress {
    description      = "Ra ngoai: apt, Docker Hub, GitHub, SSM, API model"
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}
