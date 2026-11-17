#!/usr/bin/env bash
# Dựng deploy/lab/.env từ SSM Parameter Store: đúng những bí mật mà docker-compose.lab.yml thay vào
# `${...}`. Chạy lại an toàn; chạy sau mỗi lần thêm hay đổi một khoá trong SSM, rồi
# `docker compose … up -d` để container nhận giá trị mới.
#
# Mật khẩu chung của tài khoản lab không vào .env: `seed.sh` đọc thẳng từ SSM khi cần.
#
# Cũng dựng deploy/lab/.env.overrides: thiếu khoá của LLM_PROVIDER thì tắt model
# (LLM_ENABLED=false), để Kriky trả nội dung dựng sẵn thay vì báo model hỏng ở mọi lượt.

source "$(dirname "$0")/lib.sh"

# Bỏ CR và khoảng trắng hai đầu mỗi giá trị: khoá chép từ Git Bash trên Windows từng mang `\r` vào
# SSM, `.env` chở nguyên nó, và mọi lượt Kriky hỏng vì header không hợp lệ (lab 11/11/2026).
trim() {
	local text=${1//$'\r'/}
	text=${text#"${text%%[![:space:]]*}"}
	printf '%s' "${text%"${text##*[![:space:]]}"}"
}

declare -A value
while IFS=$'\t' read -r name text; do
	[[ -n "$name" ]] && value[${name##*/}]=$(trim "$text")
done < <(aws ssm get-parameters-by-path --path "$SSM_PREFIX" --recursive --with-decryption \
	--query 'Parameters[].[Name,Value]' --output text)

for required in SITE_ADDRESS POSTGRES_PASSWORD MINIO_SECRET_KEY MONGO_PASSWORD; do
	if [[ -z "${value[$required]:-}" ]]; then
		echo "Thiếu $SSM_PREFIX/$required trong SSM -- Terraform tạo tham số này, hãy chạy lại apply." >&2
		exit 1
	fi
done

# lab.env là dữ liệu cấu hình, không source thành mã shell. Chỉ hai provider này có đường cấp
# credential trong compose; từ chối provider lạ thay vì âm thầm kiểm tra nhầm khoá.
provider=$(awk -F= '$1 ~ /^[[:space:]]*LLM_PROVIDER[[:space:]]*$/ {print $2}' "$LAB_DIR/lab.env")
provider=$(trim "$provider")
case "$provider" in
	\"*\"|\'*\') provider=${provider:1:${#provider}-2} ;;
esac
case "$provider" in
	openai) key_name=OPENAI_API_KEY ;;
	anthropic) key_name=CLAUDE_API_KEY ;;
	*) echo "LLM_PROVIDER trong lab.env phải là openai hoặc anthropic." >&2; exit 1 ;;
esac

# Nháy đơn: compose đọc giá trị trong nháy đơn đúng từng ký tự, nên một `$` không bị thay.
# Dotenv của compose không có cách thoát một nháy đơn bên trong, nên giá trị có nháy đơn bị từ chối.
quote() {
	if [[ "$1" == *"'"* ]]; then
		echo "Một giá trị trong SSM có dấu nháy đơn; .env không chở được nó." >&2
		exit 1
	fi
	printf "'%s'" "$1"
}
umask 077
{
	echo "# Dựng bởi render-env.sh từ SSM $SSM_PREFIX. Đừng sửa tay, đừng commit."
	echo "SITE_ADDRESS=$(quote "${value[SITE_ADDRESS]}")"
	echo "POSTGRES_PASSWORD=$(quote "${value[POSTGRES_PASSWORD]}")"
	echo "MINIO_SECRET_KEY=$(quote "${value[MINIO_SECRET_KEY]}")"
	echo "MONGO_PASSWORD=$(quote "${value[MONGO_PASSWORD]}")"
	echo "CLAUDE_API_KEY=$(quote "${value[CLAUDE_API_KEY]:-}")"
	echo "JEV_API_KEY=$(quote "${value[JEV_API_KEY]:-}")"
	echo "OPENAI_API_KEY=$(quote "${value[OPENAI_API_KEY]:-}")"
} >"$LAB_DIR/.env.tmp"
mv "$LAB_DIR/.env.tmp" "$LAB_DIR/.env"

{
	echo "# Dựng bởi render-env.sh. Đè lên lab.env."
	if [[ -z "${value[$key_name]:-}" ]]; then
		echo "Chưa có $SSM_PREFIX/$key_name: tắt model, Kriky trả nội dung dựng sẵn." >&2
		echo "LLM_ENABLED=false"
	fi
} >"$LAB_DIR/.env.overrides"
[[ -n "${value[JEV_API_KEY]:-}" ]] ||
	echo "Chưa có $SSM_PREFIX/JEV_API_KEY: chọn skill và xếp cấp tiêu đề đi đường luật." >&2

say "đã dựng $LAB_DIR/.env"
