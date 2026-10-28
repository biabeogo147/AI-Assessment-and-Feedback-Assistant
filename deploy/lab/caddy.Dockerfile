# syntax=docker/dockerfile:1
#
# Caddy của lab: FE đã build làm file tĩnh, cộng Caddyfile. Dựng từ gốc repo:
#
#   docker build -f deploy/lab/caddy.Dockerfile .

FROM node:22-slim AS fe
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY services/fe/package.json services/fe/
RUN pnpm install --frozen-lockfile --filter fe
COPY services/fe services/fe
# Tên bản lab (plan `lab-version`) vào bundle qua `define` của vite.config.ts. Đặt sau `pnpm install`
# để lớp cài đặt vẫn dùng cache khi chỉ tên bản đổi.
ARG AIAFA_VERSION="chưa có phiên bản"
ENV AIAFA_VERSION=$AIAFA_VERSION
RUN pnpm --filter fe build


FROM caddy:2.10-alpine
COPY deploy/lab/Caddyfile /etc/caddy/
COPY --from=fe /src/services/fe/dist /srv
