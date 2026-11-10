FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10003 trainer
WORKDIR /opt/worker
COPY pyproject.toml README.md ./
COPY src ./src
RUN python3 -m pip install --break-system-packages --no-cache-dir .[qlora]

USER 10003:10003
ENTRYPOINT ["cerebellum-meta-training-worker"]
