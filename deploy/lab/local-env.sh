#!/usr/bin/env bash
# Dựng deploy/lab/.env và .env.overrides để chạy **stack lab ở máy mình** (Git Bash được), song
# song với stack dev mà không đụng nhau: project `aiafa-lab`, chỉ caddy mở cổng, và chỉ trên
# 127.0.0.1:8088. Mật khẩu hạ tầng sinh ngẫu nhiên; không gọi model, cookie không Secure (HTTP
# thuần).
#
#   bash deploy/lab/local-env.sh
#   docker compose -p aiafa-lab -f deploy/lab/docker-compose.lab.yml up -d --build
#   docker compose -p aiafa-lab -f deploy/lab/docker-compose.lab.yml exec -T be \
#     python -m be.lab_seed --reset < <(printf '%s\n' "$MAT_KHAU")
#
# Chạy lại thì mật khẩu đổi -- Postgres và Mongo đã khởi tạo giữ mật khẩu cũ, nên khi đó xoá
# volume trước: `docker compose -p aiafa-lab -f deploy/lab/docker-compose.lab.yml down -v`.

set -euo pipefail
lab=$(cd "$(dirname "$0")" && pwd)
random() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32; }

umask 077
cat >"$lab/.env" <<EOF
# Dựng bởi local-env.sh -- chỉ cho stack lab ở máy dev. Đừng commit.
SITE_ADDRESS=':80'
LAB_HTTP_PUBLISH='127.0.0.1:8088'
LAB_HTTPS_PUBLISH='127.0.0.1:8443'
POSTGRES_PASSWORD='$(random)'
MINIO_SECRET_KEY='$(random)'
MONGO_PASSWORD='$(random)'
EOF
cat >"$lab/.env.overrides" <<EOF
# Đè lên lab.env ở máy dev: không gọi model, cookie đi được trên HTTP thuần.
LLM_ENABLED=false
SESSION_COOKIE_SECURE=false
EOF
echo "đã dựng $lab/.env và $lab/.env.overrides"
