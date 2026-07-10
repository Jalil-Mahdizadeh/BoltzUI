ARG BASE_IMAGE=boltzui:221
ARG NODE_IMAGE=node:20-bullseye-slim

FROM ${NODE_IMAGE} AS node_runtime

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="BoltzUI 2.2.1 atom_contact"
LABEL org.opencontainers.image.description="BoltzUI web image with patched Boltz 2.2.1 atom_contact constraints"

ENV BOLTZ_CACHE=/opt/boltz-cache \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5173

WORKDIR /workspace/BoltzUI

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY server.js package.json ./
COPY public ./public
COPY patches ./patches

RUN set -eux; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py; \
    boltz --help >/dev/null; \
    node --version; \
    python -c "from pathlib import Path; cache=Path('/opt/boltz-cache'); print('Boltz cache path:', cache, 'exists=', cache.exists())"

EXPOSE 5173

ENTRYPOINT ["node"]
CMD ["server.js"]
