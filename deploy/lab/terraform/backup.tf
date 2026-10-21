# Bucket nhận pg_dump hằng đêm (deploy/lab/backup.sh). Giữ 7 ngày; destroy xoá cả bucket lẫn tệp.

resource "random_id" "backup" {
  byte_length = 4
}

resource "aws_s3_bucket" "backup" {
  bucket        = "aiafa-lab-backup-${random_id.backup.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "backup" {
  bucket                  = aws_s3_bucket.backup.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id
  rule {
    id     = "keep-a-week"
    status = "Enabled"
    filter {}
    expiration {
      days = 7
    }
  }
}
