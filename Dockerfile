ARG BASE_IMAGE=boltz:221
ARG NODE_IMAGE=node:20-bullseye-slim

FROM ${NODE_IMAGE} AS node_runtime

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="BoltzUI 2.2.1"
LABEL org.opencontainers.image.description="BoltzUI web image layered on the cached Boltz 2.2.1 runtime"

ENV BOLTZ_CACHE=/opt/boltz-cache \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5173

WORKDIR /workspace/BoltzUI

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY server.js package.json ./
COPY public ./public

RUN set -eux; \
    boltz --help >/dev/null; \
    node --version; \
    python -c "from pathlib import Path; cache=Path('/opt/boltz-cache'); print('Boltz cache path:', cache, 'exists=', cache.exists())"

EXPOSE 5173

ENTRYPOINT ["node"]
CMD ["server.js"]
