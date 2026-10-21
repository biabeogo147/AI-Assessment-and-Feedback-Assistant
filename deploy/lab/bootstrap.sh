#!/usr/bin/env bash
# Lần khởi động đầu của máy lab, gọi từ user_data của Terraform (đã clone repo vào $AIAFA_DIR):
# cài docker và aws CLI, cài unit systemd và cron backup, dựng .env từ SSM, dựng và bật stack,
# seed dữ liệu lab. Chạy lại an toàn -- hỏng ở bước nào thì sửa rồi chạy lại cả script:
#
#   sudo bash /opt/aiafa/deploy/lab/bootstrap.sh
#
# Seed chỉ chạy khi chưa có dấu `/var/lib/aiafa-lab/seeded`. Log ở /var/log/cloud-init-output.log.

source "$(dirname "$0")/lib.sh"

say "cài docker, compose, aws CLI"
export DEBIAN_FRONTEND=noninteractive
# Lần boot đầu, unattended-upgrades hay giữ khoá dpkg: chờ thay vì chết.
apt-get -o DPkg::Lock::Timeout=600 update -q
apt-get -o DPkg::Lock::Timeout=600 install -y -q docker.io docker-compose-v2 docker-buildx git
snap wait system seed.loaded
command -v aws >/dev/null || snap install aws-cli --classic
systemctl enable --now docker

# Instance profile có thể tới chậm vài giây sau lần khởi động đầu.
for _ in $(seq 30); do
	aws sts get-caller-identity >/dev/null 2>&1 && break
	sleep 5
done

# 2 GB swap: dựng image document (torch, paddle) cần nhiều bộ nhớ hơn lúc chạy.
if ! swapon --show | grep -q /swapfile; then
	say "bật swap 2 GB"
	fallocate -l 2G /swapfile
	chmod 600 /swapfile
	mkswap /swapfile
	swapon /swapfile
	echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

# Unit systemd và cron cài **trước** khi dựng: một bước sau có hỏng thì máy vẫn tự bật stack sau
# reboot và backup vẫn chạy.
say "cài unit systemd: dựng lại .env từ SSM rồi bật stack sau mỗi lần khởi động"
cat >/etc/systemd/system/aiafa-lab.service <<UNIT
[Unit]
Description=AIAFA lab stack
After=docker.service network-online.target snap.amazon-ssm-agent.amazon-ssm-agent.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash $LAB_DIR/render-env.sh
ExecStart=$(command -v docker) compose -p aiafa-lab -f $LAB_DIR/docker-compose.lab.yml up -d

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable aiafa-lab.service

if [[ -n "${BACKUP_BUCKET:-}" ]]; then
	say "cron backup Postgres lúc 2 giờ sáng giờ Việt Nam"
	# cron chỉ có /usr/bin:/bin trong PATH; aws CLI của snap ở /snap/bin.
	cat >/etc/cron.d/aiafa-lab-backup <<CRON
PATH=/snap/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 19 * * * root /bin/bash $LAB_DIR/backup.sh >>/var/log/aiafa-lab-backup.log 2>&1
CRON
fi

bash "$LAB_DIR/render-env.sh"

say "dựng và bật stack (lần đầu mất 15-25 phút: image document tải torch và model OCR)"
"${COMPOSE[@]}" up -d --build

say "chờ BE sẵn sàng"
healthy=
for _ in $(seq 60); do
	if [[ "$(docker inspect -f '{{.State.Health.Status}}' aiafa-lab-be-1 2>/dev/null)" == healthy ]]; then
		healthy=yes
		break
	fi
	sleep 5
done
if [[ -z "$healthy" ]]; then
	echo "BE không healthy sau 5 phút. Xem: ${COMPOSE[*]} logs be" >&2
	exit 1
fi

mkdir -p /var/lib/aiafa-lab
if [[ ! -f /var/lib/aiafa-lab/seeded ]]; then
	bash "$LAB_DIR/seed.sh"
	touch /var/lib/aiafa-lab/seeded
fi

say "xong"
