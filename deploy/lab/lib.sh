# Dùng chung cho các script chạy **trên máy lab** (bootstrap, render-env, deploy, seed, backup).
# `source` file này, đừng chạy nó.
#
# /etc/aiafa-lab.conf do user_data của Terraform viết lúc máy khởi động lần đầu: thư mục repo,
# nhánh, region, tiền tố SSM, bucket backup. Không có gì bí mật trong đó.

set -euo pipefail

# aws CLI cài bằng snap nằm ở /snap/bin, mà cron và systemd không có thư mục ấy trong PATH.
export PATH="/snap/bin:$PATH"

if [[ -f /etc/aiafa-lab.conf ]]; then
	# shellcheck disable=SC1091
	source /etc/aiafa-lab.conf
fi
AIAFA_DIR=${AIAFA_DIR:-/opt/aiafa}
AIAFA_REF=${AIAFA_REF:-main}
AWS_REGION=${AWS_REGION:-ap-southeast-1}
SSM_PREFIX=${SSM_PREFIX:-/aiafa/lab}
export AWS_REGION AWS_DEFAULT_REGION=$AWS_REGION

LAB_DIR="$AIAFA_DIR/deploy/lab"
COMPOSE=(docker compose -p aiafa-lab -f "$LAB_DIR/docker-compose.lab.yml")

say() { printf '==> %s\n' "$*"; }

# Một tham số SSM, đã giải mã. Không in ra.
ssm_value() {
	aws ssm get-parameter --name "$SSM_PREFIX/$1" --with-decryption \
		--query Parameter.Value --output text
}
