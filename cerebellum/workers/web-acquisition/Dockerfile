FROM python:3.11.13-slim-bookworm

RUN useradd --create-home --uid 10002 worker
WORKDIR /opt/worker
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

USER 10002:10002
ENTRYPOINT ["cerebellum-web-acquisition-worker"]
