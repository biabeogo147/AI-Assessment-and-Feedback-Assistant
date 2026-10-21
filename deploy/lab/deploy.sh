#!/usr/bin/env bash
# Đưa bản mới lên lab: lấy code của $AIAFA_REF (hay tham số đầu), dựng lại .env, dựng lại image và
# bật lại những container đổi. Chạy trên máy lab qua SSM Session Manager:
#
#   sudo bash /opt/aiafa/deploy/lab/deploy.sh [nhánh-hay-commit]
#
# Repo **không có migration** (plan `lab-deploy-aws`, D5): bản mới đổi model thì BE từ chối khởi
# động, và cách ra là `seed.sh` -- xoá dữ liệu lab rồi seed lại.

source "$(dirname "$0")/lib.sh"
ref=${1:-$AIAFA_REF}

say "lấy $ref"
git -C "$AIAFA_DIR" fetch --depth 1 origin "$ref"
git -C "$AIAFA_DIR" checkout --force FETCH_HEAD

bash "$LAB_DIR/render-env.sh"
say "dựng lại và bật stack"
"${COMPOSE[@]}" up -d --build --remove-orphans
# Image document dựng lại để lại vài GB build cache mỗi lần; ổ 30 GB không chịu được lâu.
docker image prune -f >/dev/null
docker builder prune -f --filter until=72h >/dev/null
"${COMPOSE[@]}" ps
