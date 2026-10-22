#!/usr/bin/env bash
# Kiểm một lab đang chạy **từ bên ngoài**, chạy ở máy mình (Git Bash cũng được). LAB_URL nhận một
# hay nhiều URL cách nhau bằng dấu cách; mỗi URL chạy đủ bộ kiểm:
#
#   tf="terraform -chdir=deploy/lab/terraform"
#   LAB_URL="$($tf output -raw teacher_url) $($tf output -raw student_url)" \
#     BASIC_AUTH_PASSWORD=… bash deploy/lab/smoke.sh
#
# Tuỳ chọn: LAB_ACCOUNT_PASSWORD=… để thử đăng nhập một giáo viên seed và xem cookie có cờ Secure.
# Stack lab ở local chạy LAB_AUTH=off thì đặt SMOKE_NO_AUTH=1 và bỏ BASIC_AUTH_PASSWORD.
#
# Lấy mật khẩu từ SSM, đừng gõ vào lịch sử shell:
#   export BASIC_AUTH_PASSWORD=$(aws ssm get-parameter --name /aiafa/lab/BASIC_AUTH_PASSWORD \
#     --with-decryption --query Parameter.Value --output text)

set -uo pipefail
: "${LAB_URL:?đặt LAB_URL, ví dụ https://teacher.example.com https://student.example.com}"
if [[ -z "${SMOKE_NO_AUTH:-}" ]]; then
	: "${BASIC_AUTH_PASSWORD:?đặt BASIC_AUTH_PASSWORD (hay SMOKE_NO_AUTH=1 cho stack local)}"
fi
failed=0
ports_scanned=""

check() { # nhãn, mong đợi, thực tế
	if [[ "$2" == "$3" ]]; then
		printf 'ok    %s\n' "$1"
	else
		printf 'FAIL  %s: mong %s, được %s\n' "$1" "$2" "$3"
		failed=1
	fi
}
status() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }

smoke_site() { # url
	local url=$1 host=${1#*://}
	host=${host%%[:/]*}
	echo "== $url"

	local auth=()
	if [[ -z "${SMOKE_NO_AUTH:-}" ]]; then
		check "thiếu basic auth thì bị chặn" 401 "$(status "$url/")"
		check "thiếu basic auth thì /api cũng bị chặn" 401 "$(status "$url/api/teacher/me")"
		auth=(-u "${BASIC_AUTH_USER:-lab}:$BASIC_AUTH_PASSWORD")
	fi

	check "trang chủ" 200 "$(status "${auth[@]}" "$url/")"
	check "đăng ký giáo viên đã tắt" 403 "$(status "${auth[@]}" -X POST \
		-H 'Content-Type: application/json' \
		-d '{"full_name":"Thử","phone":"0900000000","email":"thu@example.com","password":"12345678"}' \
		"$url/api/teacher/sign-up")"
	check "X-Actor không thay được đăng nhập" 401 "$(status "${auth[@]}" -H 'X-Actor: teacher:GV-001' \
		"$url/api/teacher/me")"

	if [[ -n "${LAB_ACCOUNT_PASSWORD:-}" ]]; then
		local headers secure
		headers=$(curl -s -D - -o /dev/null --max-time 15 "${auth[@]}" -X POST \
			-H 'Content-Type: application/json' \
			-d "{\"login\":\"0912000101\",\"password\":\"$LAB_ACCOUNT_PASSWORD\"}" \
			"$url/api/teacher/sign-in")
		check "giáo viên seed đăng nhập được" 204 "$(head -1 <<<"$headers" | awk '{print $2}')"
		if [[ "$url" == https://* ]]; then
			grep -qi '^set-cookie:.*; secure' <<<"$headers" && secure=yes || secure=no
			check "cookie phiên có cờ Secure" yes "$secure"
		fi
	fi

	if [[ "$url" == https://* ]]; then
		# curl không có -k: lệnh trang chủ ở trên qua được nghĩa là chứng chỉ hợp lệ. Thêm một lần
		# thử HTTP để chắc Caddy chuyển sang HTTPS.
		check "HTTP chuyển sang HTTPS" 308 "$(status "http://$host/")"
	fi

	if [[ "$host" == 127.0.0.1 || "$host" == localhost ]]; then
		# Ở máy dev, stack dev (docker-compose.infra.yml, BE ở 8000) giữ đúng những cổng này, nên quét
		# chúng không nói gì về stack lab. Phần ấy do `tools/tests/test_lab_deploy.py` canh.
		echo "bỏ qua quét cổng: $host là máy local"
		return
	fi
	# Mọi tên của lab trỏ về cùng một Elastic IP, nên quét một lần là đủ: security group bỏ gói, mỗi
	# cổng đóng tốn trọn `timeout 4`.
	if [[ -n "$ports_scanned" ]]; then
		echo "bỏ qua quét cổng: đã quét ở $ports_scanned"
		return
	fi
	ports_scanned=$host
	local port
	for port in 5432 6379 8000 9000 9001 27017; do
		if timeout 4 bash -c ">/dev/tcp/$host/$port" 2>/dev/null; then
			check "cổng $port đóng từ bên ngoài" đóng mở
		else
			check "cổng $port đóng từ bên ngoài" đóng đóng
		fi
	done
}

for url in $LAB_URL; do
	smoke_site "${url%/}"
done
exit $failed
