ARG PYTORCH_IMAGE=pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime
FROM ${PYTORCH_IMAGE}

LABEL org.opencontainers.image.title="Boltz 2.2.1 cached"
LABEL org.opencontainers.image.description="Boltz 2.2.1 Docker image with model and molecule cache pre-baked at /opt/boltz-cache"

ENV BOLTZ_CACHE=/opt/boltz-cache
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY --chown=root:root .boltz/ /opt/boltz-cache/

RUN set -eux; \
    test -s /opt/boltz-cache/boltz2_conf.ckpt; \
    test -s /opt/boltz-cache/boltz2_aff.ckpt; \
    test -s /opt/boltz-cache/mols.tar; \
    test -d /opt/boltz-cache/mols; \
    python -c "from pathlib import Path; cache=Path('/opt/boltz-cache'); print('Boltz cache files:', sum(1 for path in cache.rglob('*') if path.is_file()))"

ENTRYPOINT ["boltz"]
CMD ["--help"]
