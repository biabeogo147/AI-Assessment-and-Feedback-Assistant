# Dùng chung cho các script chạy **trên máy lab** (bootstrap, render-env, deploy, seed, backup).
# `source` file này, đừng chạy nó.
#
# /etc/aiafa-lab.conf do user_data của Terraform viết lúc máy khởi động lần đầu: thư mục repo,
# nhánh, region, tiền tố SSM, bucket backup. Không có gì bí mật trong đó.

set -euo pipefail

if [[ -f /etc/aiafa-lab.conf ]]; then
	# shellcheck disable=SC1091
	source /etc/aiafa-lab.conf
fi
AIAFA_DIR=${AIAFA_DIR:-/opt/aiafa}
AIAFA_REF=${AIAFA_REF:-main}
AWS_REGION=${AWS_REGION:-us-east-2}
SSM_PREFIX=${SSM_PREFIX:-/aiafa/lab}
export AWS_REGION AWS_DEFAULT_REGION=$AWS_REGION

LAB_DIR="$AIAFA_DIR/deploy/lab"

# Tên bản của lần `deploy.sh` gần nhất: mọi script dựng lại image (kể cả chạy lại `bootstrap.sh`)
# đưa nó vào build arg của caddy, nên FE không mất tên bản trong khi BE vẫn đọc file này.
# `deploy.sh` đặt tên bản mới **sau** khi nạp file này, nên tên mới thắng.
if [[ -z "${AIAFA_VERSION:-}" && -f "$LAB_DIR/.env.version" ]]; then
	# shellcheck disable=SC1091
	source "$LAB_DIR/.env.version"
	export AIAFA_VERSION
fi
COMPOSE=(docker compose -p aiafa-lab -f "$LAB_DIR/docker-compose.lab.yml")

say() { printf '==> %s\n' "$*"; }

# Một tham số SSM, đã giải mã. Không in ra.
ssm_value() {
	aws ssm get-parameter --name "$SSM_PREFIX/$1" --with-decryption \
		--query Parameter.Value --output text
}
