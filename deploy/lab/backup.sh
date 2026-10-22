#!/usr/bin/env bash
# Dump Postgres của lab lên S3, một tệp mỗi ngày; bucket tự xoá tệp cũ hơn 7 ngày (Terraform).
# Cron gọi hằng đêm (bootstrap.sh). Khôi phục: docs/operation/deploy-lab.md.
#
# Chỉ Postgres: tài liệu trong MinIO và bản đọc trong Mongo tải lại được, còn bài làm thì không.

source "$(dirname "$0")/lib.sh"
: "${BACKUP_BUCKET:?BACKUP_BUCKET chưa có trong /etc/aiafa-lab.conf}"

key="pg/$(date -u +%Y-%m-%d).sql.gz"
"${COMPOSE[@]}" exec -T postgres pg_dump -U aiafa --clean --if-exists aiafa |
	gzip | aws s3 cp - "s3://$BACKUP_BUCKET/$key"
say "đã lưu s3://$BACKUP_BUCKET/$key"
