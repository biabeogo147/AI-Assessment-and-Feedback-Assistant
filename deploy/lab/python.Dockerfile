# syntax=docker/dockerfile:1
#
# Hai image Python của lab (plan `lab-deploy-aws`, D3), dựng từ gốc repo:
#
#   docker build -f deploy/lab/python.Dockerfile --target app .
#   docker build -f deploy/lab/python.Dockerfile --target document .
#
# `app` chở be, agent, ingest. `document` chở thêm services/document với torch và paddle -- vài GB
# mà ba service kia không bao giờ import, nên chúng không đi chung một image.
#
# Cài **không editable**, đúng thứ tự của `dev.ps1 install`: contracts trước schema, cả hai trước
# mọi service, vì service khai chúng là dependency tên `aiafa-contracts` / `aiafa-schema` mà PyPI
# không có.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY packages/contracts packages/contracts
RUN pip install ./packages/contracts
COPY packages/schema packages/schema
RUN pip install ./packages/schema
RUN useradd --create-home --uid 10001 aiafa


FROM base AS app
COPY services/be services/be
COPY services/agent services/agent
COPY services/ingest services/ingest
RUN pip install ./services/be ./services/agent ./services/ingest
USER aiafa


FROM base AS document
# opencv (kéo theo paddlex) cần libGL và glib; paddle cần OpenMP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# torch **bản CPU**, cài trước và từ index riêng: máy lab không có GPU, và bản mặc định trên Linux
# kéo theo vài GB thư viện CUDA. Cài trước thì lúc cài services/document pip thấy đã đủ, không tải lại.
RUN pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
COPY services/document services/document
RUN pip install ./services/document
USER aiafa
# Tải sẵn model OCR (layout, detector của paddle, recognizer của easyocr) vào image: không thì lần
# đọc tệp scan đầu tiên sau mỗi lần khởi động phải đi tải chúng, và job 120 s hết giờ giữa chừng.
RUN python -c "from document.ocr.page import PageReader; PageReader(reader='easyocr', threads=1)"
