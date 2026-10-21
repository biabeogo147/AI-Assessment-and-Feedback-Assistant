#!/usr/bin/env bash
# Dựng deploy/lab/.env từ SSM Parameter Store: đúng những bí mật mà docker-compose.lab.yml thay vào
# `${...}`. Chạy lại an toàn; chạy sau mỗi lần thêm hay đổi một khoá trong SSM, rồi
# `docker compose … up -d` để container nhận giá trị mới.
#
# Mật khẩu basic auth không vào .env: chỉ bản băm bcrypt của nó (`caddy hash-password`), cộng dấu
# vân tay sha256 để lần sau giữ nguyên bản băm khi mật khẩu không đổi. Mật khẩu chung của tài khoản
# lab cũng không: `seed.sh` đọc thẳng từ SSM khi cần.
#
# Cũng dựng deploy/lab/.env.overrides: thiếu CLAUDE_API_KEY thì tắt model (LLM_ENABLED=false), để
# Kriky trả nội dung dựng sẵn thay vì báo model hỏng ở mọi lượt.

source "$(dirname "$0")/lib.sh"

declare -A value
while IFS=$'\t' read -r name text; do
	[[ -n "$name" ]] && value[${name##*/}]=$text
done < <(aws ssm get-parameters-by-path --path "$SSM_PREFIX" --recursive --with-decryption \
	--query 'Parameters[].[Name,Value]' --output text)

for required in SITE_ADDRESS POSTGRES_PASSWORD MINIO_SECRET_KEY MONGO_PASSWORD BASIC_AUTH_PASSWORD; do
	if [[ -z "${value[$required]:-}" ]]; then
		echo "Thiếu $SSM_PREFIX/$required trong SSM -- Terraform tạo tham số này, hãy chạy lại apply." >&2
		exit 1
	fi
done

# Giữ bản băm cũ khi mật khẩu không đổi: bcrypt mỗi lần một salt mới, và một bản băm mới là một
# biến môi trường mới -- compose sẽ dựng lại caddy ở mỗi lần boot và mỗi lần deploy.
fingerprint=$(printf '%s' "${value[BASIC_AUTH_PASSWORD]}" | sha256sum | cut -d' ' -f1)
hash=
if [[ -f "$LAB_DIR/.env" ]] && grep -q "^BASIC_AUTH_FINGERPRINT='$fingerprint'$" "$LAB_DIR/.env"; then
	hash=$(sed -n "s/^BASIC_AUTH_HASH='\(.*\)'$/\1/p" "$LAB_DIR/.env")
fi
if [[ -z "$hash" ]]; then
	# `caddy hash-password` chỉ đọc stdin khi có terminal, nên mật khẩu đi qua một biến môi trường:
	# `-e PLAIN` không kèm giá trị, nên nó không nằm trên dòng lệnh docker. Trong container nó vẫn
	# là một tham số của `caddy` trong chưa tới một giây -- chấp nhận được với một máy chỉ root vào.
	hash=$(PLAIN=${value[BASIC_AUTH_PASSWORD]} docker run --rm -e PLAIN caddy:2.10-alpine \
		sh -c 'caddy hash-password --plaintext "$PLAIN"')
fi
[[ "$hash" == '$2'* ]] || { echo "caddy hash-password không trả về một bcrypt." >&2; exit 1; }

# Nháy đơn: compose đọc giá trị trong nháy đơn đúng từng ký tự, nên `$` của bcrypt không bị thay.
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
	echo "BASIC_AUTH_USER=$(quote "${value[BASIC_AUTH_USER]:-lab}")"
	echo "BASIC_AUTH_HASH=$(quote "$hash")"
	echo "BASIC_AUTH_FINGERPRINT=$(quote "$fingerprint")"
	echo "CLAUDE_API_KEY=$(quote "${value[CLAUDE_API_KEY]:-}")"
	echo "JEV_API_KEY=$(quote "${value[JEV_API_KEY]:-}")"
	echo "OPENAI_API_KEY=$(quote "${value[OPENAI_API_KEY]:-}")"
} >"$LAB_DIR/.env.tmp"
mv "$LAB_DIR/.env.tmp" "$LAB_DIR/.env"

{
	echo "# Dựng bởi render-env.sh. Đè lên lab.env."
	if [[ -z "${value[CLAUDE_API_KEY]:-}" ]]; then
		echo "Chưa có $SSM_PREFIX/CLAUDE_API_KEY: tắt model, Kriky trả nội dung dựng sẵn." >&2
		echo "LLM_ENABLED=false"
	fi
} >"$LAB_DIR/.env.overrides"
[[ -n "${value[JEV_API_KEY]:-}" ]] ||
	echo "Chưa có $SSM_PREFIX/JEV_API_KEY: chọn skill và xếp cấp tiêu đề đi đường luật." >&2

say "đã dựng $LAB_DIR/.env"
