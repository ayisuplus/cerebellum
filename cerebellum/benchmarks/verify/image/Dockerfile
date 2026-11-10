ARG PYTHON_BASE_IMAGE
FROM ${PYTHON_BASE_IMAGE}

RUN python -m pip install --no-cache-dir pytest==8.3.5

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTEST_ADDOPTS=-p no:cacheprovider

USER 65532:65532
WORKDIR /workspace
ENTRYPOINT []
