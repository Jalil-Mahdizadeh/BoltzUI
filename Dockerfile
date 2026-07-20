ARG BASE_IMAGE=boltzui:221
ARG NODE_IMAGE=node:20-bullseye-slim

FROM ${NODE_IMAGE} AS node_runtime

WORKDIR /node-app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="BoltzUI 2.2.1 atom contacts"
LABEL org.opencontainers.image.description="BoltzUI with exact and union atom-contact guidance and bounded Boltz 2.2.1 denoiser sample batches"

ENV BOLTZ_CACHE=/opt/boltz-cache \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5173

WORKDIR /workspace/BoltzUI

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /node-app/node_modules ./node_modules
COPY server.js package.json package-lock.json ./
COPY lib ./lib
COPY public ./public
COPY patches ./patches
COPY scripts ./scripts
COPY fixtures ./fixtures
COPY tests ./tests
COPY README.md REQUIREMENTS.md DOCKER_HUB.md ./

RUN set -eux; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py --check; \
    python patches/boltz_atom_contact/apply_atom_contact_patch.py; \
    node scripts/sync-docs.js --check; \
    node --test tests/*.test.js; \
    python -m unittest tests/test_boltz_patch.py; \
    boltz --help >/dev/null; \
    node --version; \
    python -c "from pathlib import Path; cache=Path('/opt/boltz-cache'); print('Boltz cache path:', cache, 'exists=', cache.exists())"

EXPOSE 5173

ENTRYPOINT ["node"]
CMD ["server.js"]
