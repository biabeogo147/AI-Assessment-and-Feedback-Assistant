output "teacher_url" {
  description = "Địa chỉ của giáo viên. Chứng chỉ HTTPS có sau vài phút đầu, khi Caddy đã bật."
  value       = "https://${local.teacher_host}"
}

output "student_url" {
  description = "Địa chỉ của học sinh."
  value       = "https://${local.student_host}"
}

output "public_ip" {
  description = "Elastic IP: hai bản ghi A, teacher và student, trỏ về đây."
  value       = aws_eip.lab.public_ip
}

output "instance_id" {
  value = aws_instance.lab.id
}

output "session" {
  description = "Vào máy lab (cần Session Manager plugin của aws CLI)."
  value       = "aws ssm start-session --region ${var.region} --target ${aws_instance.lab.id}"
}

output "ssh" {
  description = "SSH vào máy, khi đã đặt ssh_cidrs và ssh_public_key."
  value       = length(var.ssh_cidrs) > 0 && var.ssh_public_key != "" ? "ssh ubuntu@${aws_eip.lab.public_ip}" : "không mở SSH"
}

output "bootstrap_log" {
  description = "Xem bootstrap chạy tới đâu, sau khi vào máy."
  value       = "sudo tail -f /var/log/cloud-init-output.log"
}

output "read_password" {
  description = "Đọc mật khẩu chung của tài khoản seed."
  value       = "aws ssm get-parameter --region ${var.region} --name ${var.ssm_prefix}/LAB_ACCOUNT_PASSWORD --with-decryption --query Parameter.Value --output text"
}

output "backup_bucket" {
  value = aws_s3_bucket.backup.bucket
}
