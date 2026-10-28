#!/usr/bin/env bash
# Đưa một bản có tên lên lab: lấy code của tag, dựng lại .env, dựng lại image và bật lại những
# container đổi. Chạy trên máy lab qua SSM Session Manager:
#
#   sudo bash /opt/aiafa/deploy/lab/deploy.sh lab-2026.0.1
#
# Chỉ nhận một tag `lab-YYYY.z.x` (đặt bằng `.\dev.ps1 release` ở máy mình, plan `lab-version`):
# bản không tên thì ticket của tester không nói được lỗi thuộc bản nào. `AIAFA_REF` của
# /etc/aiafa-lab.conf chỉ còn là nhánh của lần clone đầu, không phải bản deploy mặc định.
#
# Repo **không có migration** (plan `lab-deploy-aws`, D5): bản mới đổi model thì BE từ chối khởi
# động, và cách ra là `seed.sh` -- xoá dữ liệu lab rồi seed lại.

source "$(dirname "$0")/lib.sh"
ref=${1:-}

if [[ ! "$ref" =~ ^lab-[0-9]{4}\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
	echo "deploy.sh chỉ deploy một tag lab-YYYY.z.x, không nhận '${ref:-(trống)}'. Đặt tên bằng" \
		".\dev.ps1 release ở máy mình, push tag rồi chạy lại: deploy.sh lab-…" >&2
	exit 1
fi

say "lấy $ref"
git -C "$AIAFA_DIR" fetch --depth 1 origin "refs/tags/$ref"
git -C "$AIAFA_DIR" checkout --force FETCH_HEAD

# Tên bản cho BE (env file của mọi service app, đọc lại ở mỗi lần `up`, kể cả unit systemd lúc boot)
# và cho build arg của image caddy (FE nhận tên lúc build). `.env.*` đã bị .gitignore bỏ qua.
umask 077
printf 'AIAFA_VERSION=%s\n' "$ref" >"$LAB_DIR/.env.version"
export AIAFA_VERSION=$ref

bash "$LAB_DIR/render-env.sh"
say "dựng lại và bật stack"
"${COMPOSE[@]}" up -d --build --remove-orphans
# Image document dựng lại để lại vài GB build cache mỗi lần; ổ 30 GB không chịu được lâu.
docker image prune -f >/dev/null
docker builder prune -f --filter until=72h >/dev/null
"${COMPOSE[@]}" ps
