ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}

ARG SKILLOPT_COMMIT=3c8873f016397817dcd40c3e5436d92fe19372b8
ARG SKILLOPT_ARCHIVE_SHA256=abdc429fe2a59b30d36c3148a107dfb36184821c7996d67d98d362a6603b1999
ARG REGISTRATION_PATCH_SHA256=3f57e82c0518e18fd9ee33c337737f370e9d61c892715f7905b35c98590c1549
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --filter=blob:none https://github.com/microsoft/SkillOpt.git SkillOpt \
    && git -C SkillOpt checkout --detach "${SKILLOPT_COMMIT}" \
    && test "$(git -C SkillOpt rev-parse HEAD)" = "${SKILLOPT_COMMIT}" \
    && git -C SkillOpt archive --format=tar HEAD > /tmp/skillopt.tar \
    && echo "${SKILLOPT_ARCHIVE_SHA256}  /tmp/skillopt.tar" | sha256sum -c - \
    && sha256sum /tmp/skillopt.tar > /opt/skillopt-source.sha256

COPY patches/register-cerebellum-verify.patch /opt/register-cerebellum-verify.patch
RUN echo "${REGISTRATION_PATCH_SHA256}  /opt/register-cerebellum-verify.patch" | sha256sum -c - \
    && git -C /opt/SkillOpt apply --check /opt/register-cerebellum-verify.patch \
    && git -C /opt/SkillOpt apply /opt/register-cerebellum-verify.patch

COPY . /opt/cerebellum-worker
RUN python -m pip install --no-cache-dir /opt/SkillOpt \
    && python -m pip install --no-cache-dir --no-deps /opt/cerebellum-worker

ENV SKILLOPT_ROOT=/opt/SkillOpt \
    SKILLOPT_SOURCE_ARCHIVE_SHA256_FILE=/opt/skillopt-source.sha256 \
    CEREBELLUM_REGISTRATION_PATCH=/opt/register-cerebellum-verify.patch

ENTRYPOINT ["cerebellum-skillopt-worker"]
