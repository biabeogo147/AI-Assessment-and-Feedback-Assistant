#!/usr/bin/env bash
# **Xoá sạch** dữ liệu lab (Postgres và bucket tài liệu; bản đọc cũ trong Mongo ở lại nhưng không còn
# dòng `documents` nào trỏ tới) rồi seed lại: 5 giáo viên, 30 lớp, 1000
# học sinh, đề ở mọi trạng thái. Mật khẩu chung của mọi tài khoản đi thẳng từ SSM vào stdin của
# lệnh seed -- không qua dòng lệnh, không in ra.
#
#   sudo bash /opt/aiafa/deploy/lab/seed.sh

source "$(dirname "$0")/lib.sh"

say "seed lại dữ liệu lab (xoá hết dữ liệu cũ)"
ssm_value LAB_ACCOUNT_PASSWORD | "${COMPOSE[@]}" exec -T be python -m be.lab_seed --reset
